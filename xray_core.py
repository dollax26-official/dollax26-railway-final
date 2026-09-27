"""
Dollax Panel — Xray-core integration.

The panel can either serve VLESS/Trojan itself (its own WebSocket relay) or hand every
inbound to a bundled Xray-core process. With Xray in the container we get the protocols the
pure-Python relay cannot do — VMess, Shadowsocks, Reality, and UDP — while the panel stays
the only public port (Railway gives us one HTTPS port): the panel keeps the WebSocket path
and pipes the connection into Xray's local ws inbound.

Layout inside the container:

    client ──wss://<railway-domain>/ws/<path>──▶ panel (FastAPI)
                                                   │  (bridge, still counts bytes/quotas)
                                                   ▼
                                        xray ws inbound 127.0.0.1:10000+i
                                                   ▼
                                          freedom (direct out) ──▶ internet

Env knobs:
    XRAY_MODE   auto (default) | on | off      auto = use Xray when the binary is present
    XRAY_BIN    path to the binary (default: "xray" from PATH)
    XRAY_BASE_PORT  first local port (default 10000)
    XRAY_CONFIG path of the generated config (default: <data>/xray/config.json)
"""
import json
import os
import shutil
import subprocess
import threading
import time

STATE = {
    "mode": (os.getenv("XRAY_MODE") or "auto").strip().lower(),
    "proc": None,
    "port_map": {},        # inbound id -> local (bridged) port
    "reality_ports": {},   # inbound id -> raw TCP port (Reality)
    "config_path": "",
    "last_sync": 0.0,
    "last_error": "",
    "version": "",
}
_lock = threading.Lock()
_sync_timer = None


def binary() -> str:
    return os.getenv("XRAY_BIN") or "xray"


def available() -> bool:
    return bool(shutil.which(binary()))


def enabled() -> bool:
    mode = STATE["mode"]
    if mode == "off":
        return False
    if mode == "on":
        return True
    return available()


def base_port() -> int:
    try:
        return int(os.getenv("XRAY_BASE_PORT") or 10000)
    except Exception:
        return 10000


def config_path() -> str:
    if STATE["config_path"]:
        return STATE["config_path"]
    import db  # local import: main imports this module early
    path = os.getenv("XRAY_CONFIG") or str(db.DATA_DIR / "xray" / "config.json")
    STATE["config_path"] = path
    return path


def json_or_none(raw):
    """Parse a stored JSON fragment; None when empty/invalid (then the rows are used)."""
    txt = str(raw or "").strip()
    if not txt:
        return None
    try:
        val = json.loads(txt)
    except Exception:  # noqa: BLE001
        return None
    return val if isinstance(val, list) else None


def _list(value) -> list:
    if isinstance(value, list):
        return [str(v) for v in value if str(v).strip()]
    return [v.strip() for v in str(value or "").replace(",", "\n").splitlines() if v.strip()]


def build_outbounds(rows) -> list:
    """Turn the panel's Outbounds page into Xray outbounds (3x-ui style)."""
    out = []
    for r in rows or []:
        if not int(r.get("enabled") or 0):
            continue
        proto = str(r.get("protocol") or "freedom").lower()
        tag = str(r.get("tag") or proto)
        addr = str(r.get("address") or "")
        port = int(r.get("port") or 0)
        if proto in ("freedom", "blackhole"):
            out.append({"tag": tag, "protocol": proto,
                        "settings": {"domainStrategy": "UseIPv4"} if proto == "freedom" else {}})
            continue
        if proto in ("socks", "http"):
            servers = [{"address": addr, "port": port}]
            if r.get("username"):
                servers[0]["users"] = [{"user": r["username"], "pass": r.get("password") or ""}]
            out.append({"tag": tag, "protocol": proto, "settings": {"servers": servers}})
            continue
        if proto == "shadowsocks":
            out.append({"tag": tag, "protocol": "shadowsocks",
                        "settings": {"servers": [{"address": addr, "port": port,
                                                  "method": r.get("method") or "chacha20-ietf-poly1305",
                                                  "password": r.get("password") or ""}]}})
            continue
        if proto in ("vless", "vmess", "trojan"):
            user = {"encryption": "none"} if proto == "vless" else {}
            user["id" if proto != "trojan" else "password"] = r.get("uuid") or r.get("password") or ""
            out.append({"tag": tag, "protocol": proto,
                        "settings": {"vnext" if proto != "trojan" else "servers":
                                     [{"address": addr, "port": port, "users": [user]}]}})
            continue
        if proto == "wireguard":
            out.append({"tag": tag, "protocol": "wireguard",
                        "settings": {"secretKey": r.get("password") or "",
                                     "address": [r.get("method") or "10.0.0.2/32"],
                                     "peers": [{"publicKey": r.get("uuid") or "", "endpoint": f"{addr}:{port}"}]}})
            continue
        out.append({"tag": tag, "protocol": proto, "settings": {}})
    return out


def build_routes(rows) -> list:
    """Turn the Routing page into Xray routing rules (checked before the defaults)."""
    rules = []
    for r in rows or []:
        if not int(r.get("enabled") or 0):
            continue
        target = str(r.get("outbound_tag") or "") or ("block" if str(r.get("action")) == "block" else "direct")
        rule = {"type": "field", "outboundTag": target}
        dom = _list(r.get("domain"))
        ips = _list(r.get("ip"))
        ports = _list(r.get("port"))
        nets = _list(r.get("network"))
        protos = _list(r.get("protocols"))
        if dom:
            rule["domain"] = dom
        if ips:
            rule["ip"] = ips
        if ports:
            rule["port"] = ",".join(ports)
        if nets:
            rule["network"] = ",".join(nets)
        if protos:
            rule["protocol"] = protos
        if r.get("inbound_tag"):
            rule["inboundTag"] = _list(r.get("inbound_tag"))
        if len(rule) > 2:                     # a rule with no matcher would swallow everything
            rules.append(rule)
    return rules


def build_config(inbounds, clients_by_inbound, base=None, outbound_rows=None, route_rows=None,
                 outbounds_json=None, routing_json=None) -> dict:
    """One local ws inbound per panel inbound, plus freedom/block outbounds."""
    import protocol
    base = base or base_port()
    port_map = {}
    reality_ports = {}
    xs = []
    for i, ib in enumerate(inbounds):
        ib = dict(ib)
        proto = (ib.get("protocol") or "vless").lower()
        # ---- Reality inbounds cannot be bridged through the HTTPS port (Railway/TLS would
        # terminate the handshake), so they listen on their own raw TCP port. Expose that
        # port with a Railway "TCP Proxy" and put the resulting domain:port in the inbound's
        # address/port fields.
        if (ib.get("security") or "").lower() == "reality":
            rclients = clients_by_inbound.get(ib["id"], [])
            # one raw port per Reality inbound (two inbounds must never share a listener)
            rport = (int(os.getenv("XRAY_REALITY_PORT") or 0) or (base + 1000)) + len(reality_ports)
            reality_ports[ib["id"]] = rport
            rnet = (ib.get("network") or "tcp").lower()
            rs = protocol.reality_settings(ib)
            rstream = {"network": rnet, "security": "reality",
                       "realitySettings": {"show": False, "dest": rs["dest"], "xver": 0,
                                           "serverNames": rs["serverNames"],
                                           "privateKey": rs["privateKey"],
                                           "shortIds": rs["shortIds"]}}
            if rnet == "ws":
                rstream["wsSettings"] = {"path": ib.get("path") or f"/ws/{i}"}
                if ib.get("host_header"):
                    rstream["wsSettings"]["headers"] = {"Host": ib["host_header"]}
            rentry = {"tag": f"reality{i}", "listen": "0.0.0.0", "port": rport,
                      "streamSettings": rstream,
                      "sniffing": {"enabled": True, "destOverride": ["http", "tls", "quic"]}}
            if proto == "vless":
                rentry["protocol"] = "vless"
                rentry["settings"] = {"decryption": "none",
                                      "clients": [{"id": c["uuid"], "email": c.get("name") or c["id"],
                                                   "flow": rs["flow"] or ""} for c in rclients] or
                                                 ([{"id": ib["uuid"], "email": "inbound", "flow": rs["flow"] or ""}]
                                                  if ib.get("uuid") else [])}
            elif proto == "trojan":
                rentry["protocol"] = "trojan"
                rentry["settings"] = {"clients": [{"password": c["uuid"], "email": c.get("name") or c["id"],
                                                   "flow": rs["flow"] or ""} for c in rclients] or
                                                 ([{"password": ib["uuid"], "email": "inbound",
                                                    "flow": rs["flow"] or ""}] if ib.get("uuid") else [])}
            else:
                rentry["protocol"] = proto
                rentry["settings"] = {"clients": []}
            xs.append(rentry)
            continue
        if proto == "wireguard":
            # WireGuard needs a TUN device + NET_ADMIN, which a Railway container does not
            # give us: the panel generates the peer configs, but WG itself must run elsewhere.
            continue
        port = base + i
        port_map[ib["id"]] = port
        clients = clients_by_inbound.get(ib["id"], [])
        net = (ib.get("network") or "ws").lower()
        # Xray terminates TLS? No: Railway does, so every local inbound is plain.
        stream = {"security": "none"}
        if net == "xhttp":
            stream["network"] = "xhttp"
            stream["xhttpSettings"] = {"path": ib.get("path") or f"/xhttp/{i}",
                                       "mode": ib.get("xhttp_mode") or "auto"}
            if ib.get("host_header"):
                stream["xhttpSettings"]["host"] = ib["host_header"]
        elif net == "grpc":
            stream["network"] = "grpc"
            stream["grpcSettings"] = {"serviceName": ib.get("grpc_service_name") or f"grpc{i}"}
        elif net == "httpupgrade":
            stream["network"] = "httpupgrade"
            stream["httpupgradeSettings"] = {"path": ib.get("path") or f"/hu/{i}"}
            if ib.get("host_header"):
                stream["httpupgradeSettings"]["host"] = ib["host_header"]
        elif net == "raw":
            # Xray's modern name for TCP: same idea, rawSettings carries the header type
            stream["network"] = "raw"
            stream["rawSettings"] = {"header": {"type": ib.get("header_type") or "none"}}
        elif net == "tcp":
            stream["network"] = "tcp"
            stream["tcpSettings"] = {"header": {"type": ib.get("header_type") or "none"}}
        else:
            stream["network"] = "ws"
            stream["wsSettings"] = {"path": ib.get("path") or f"/ws/{i}"}
            if ib.get("host_header"):
                stream["wsSettings"]["headers"] = {"Host": ib["host_header"]}
        entry = {"tag": f"in{i}", "listen": "127.0.0.1", "port": port, "streamSettings": stream,
                 "sniffing": {"enabled": True, "destOverride": ["http", "tls", "quic"]}}
        if proto == "vless":
            entry["protocol"] = "vless"
            entry["settings"] = {"decryption": "none",
                                 "clients": [{"id": c["uuid"], "email": c.get("name") or c["id"], "level": 0}
                                             for c in clients] or
                                            ([{"id": ib["uuid"], "email": "inbound", "level": 0}] if ib.get("uuid") else [])}
        elif proto == "vmess":
            entry["protocol"] = "vmess"
            entry["settings"] = {"clients": [{"id": c["uuid"], "alterId": 0, "email": c.get("name") or c["id"]}
                                             for c in clients] or
                                            ([{"id": ib["uuid"], "alterId": 0, "email": "inbound"}] if ib.get("uuid") else [])}
        elif proto == "trojan":
            entry["protocol"] = "trojan"
            entry["settings"] = {"clients": [{"password": c["uuid"], "email": c.get("name") or c["id"]}
                                             for c in clients] or
                                            ([{"password": ib["uuid"], "email": "inbound"}] if ib.get("uuid") else [])}
        else:  # shadowsocks (one password per inbound by design)
            entry["protocol"] = "shadowsocks"
            entry["settings"] = {"method": ib.get("ss_method") or "chacha20-ietf-poly1305",
                                 "password": ib.get("ss_password") or ib.get("uuid") or "dollax",
                                 "network": "tcp,udp"}
        xs.append(entry)
    STATE["reality_ports"] = reality_ports
    cfg = {
        "log": {"loglevel": os.getenv("XRAY_LOGLEVEL") or "warning"},
        # Resolve through public resolvers: the big services (YouTube, Instagram, Telegram)
        # are CDN-heavy, and a broken/blocked container resolver makes them load slowly or
        # not at all even though the tunnel itself is fine.
        "dns": {
            "servers": [
                "1.1.1.1",
                "8.8.8.8",
                {"address": "https://1.1.1.1/dns-query", "domains": ["geosite:geolocation-!cn"]},
            ],
            "queryStrategy": "UseIPv4",
            "disableFallback": False,
        },
        "inbounds": xs,
        "outbounds": (json_or_none(outbounds_json) or build_outbounds(outbound_rows)) + [
            {"tag": "direct", "protocol": "freedom",
             "settings": {"domainStrategy": "UseIPv4"},
             "streamSettings": {"sockopt": {"tcpFastOpen": True, "tcpNoDelay": True}}},
            {"tag": "block", "protocol": "blackhole"},
        ],
        "routing": {
            "domainStrategy": "AsIs",
            "rules": (json_or_none(routing_json) or build_routes(route_rows)) + [
                # QUIC/HTTP3 is UDP: the WebSocket tunnel carries TCP, so let browsers fall
                # back to TCP+TLS instead of stalling on a UDP flow that cannot be relayed.
                # This is what makes YouTube/Instagram/Telegram feel normal through the panel.
                {"type": "field", "network": "udp", "port": "443", "outboundTag": "block"},
                {"type": "field", "ip": ["geoip:private"], "outboundTag": "block"},
                {"type": "field", "protocol": ["bittorrent"], "outboundTag": "block"},
            ],
        },
    }
    return cfg, port_map


def write_config(inbounds, clients_by_inbound, outbound_rows=None, route_rows=None,
                 outbounds_json=None, routing_json=None) -> dict:
    cfg, port_map = build_config(inbounds, clients_by_inbound, None, outbound_rows, route_rows,
                                 outbounds_json, routing_json)
    path = config_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, indent=1)
    os.replace(tmp, path)
    STATE["port_map"] = port_map
    return {"config": cfg, "port_map": port_map, "path": path}


def start(inbounds, clients_by_inbound, outbound_rows=None, route_rows=None,
          outbounds_json=None, routing_json=None) -> dict:
    """Write the config and (re)start the Xray process. Safe to call repeatedly."""
    with _lock:
        if not enabled():
            STATE["last_error"] = ("XRAY_MODE=off" if STATE["mode"] == "off"
                                   else "xray binary not found in PATH")
            return {"ok": False, "running": False, "reason": STATE["last_error"]}
        info = write_config(inbounds, clients_by_inbound, outbound_rows=outbound_rows,
                             route_rows=route_rows, outbounds_json=outbounds_json,
                             routing_json=routing_json)
        proc = STATE.get("proc")
        if proc and proc.poll() is None:
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        try:
            log_dir = os.path.dirname(info["path"])
            log_file = open(os.path.join(log_dir, "xray.log"), "ab", buffering=0)
            STATE["proc"] = subprocess.Popen([binary(), "run", "-c", info["path"]],
                                             stdout=log_file, stderr=log_file)
            time.sleep(1.2)
            if STATE["proc"].poll() is not None:
                STATE["last_error"] = f"xray exited immediately (code {STATE['proc'].returncode})"
                return {"ok": False, "running": False, "reason": STATE["last_error"], **info}
            STATE["last_error"] = ""
            STATE["last_sync"] = time.time()
            try:
                v = subprocess.run([binary(), "version"], capture_output=True, text=True, timeout=5)
                STATE["version"] = (v.stdout or v.stderr or "").splitlines()[0][:80]
            except Exception:
                STATE["version"] = "unknown"
            return {"ok": True, "running": True, **info}
        except Exception as exc:  # noqa: BLE001
            STATE["last_error"] = f"{exc.__class__.__name__}: {exc}"
            return {"ok": False, "running": False, "reason": STATE["last_error"], **info}


def is_running() -> bool:
    proc = STATE.get("proc")
    return bool(proc and proc.poll() is None)


def status() -> dict:
    return {
        "mode": STATE["mode"], "installed": available(), "running": is_running(),
        "version": STATE["version"], "base_port": base_port(),
        "inbounds": len(STATE["port_map"]), "reality": STATE.get("reality_ports", {}),
        "config": config_path(),
        "last_sync": STATE["last_sync"], "last_error": STATE["last_error"],
    }


def local_port(inbound_id) -> int:
    return int(STATE["port_map"].get(inbound_id) or 0)


def sync_soon(get_inbounds, get_clients_by_inbound, delay=1.5):
    """Debounced config refresh: call after any inbound/client change."""
    global _sync_timer
    if not enabled():
        return

    def _run():
        try:
            start(get_inbounds(), get_clients_by_inbound())
        except Exception:
            pass

    with _lock:
        if _sync_timer:
            try:
                _sync_timer.cancel()
            except Exception:
                pass
        _sync_timer = threading.Timer(delay, _run)
        _sync_timer.daemon = True
        _sync_timer.start()
