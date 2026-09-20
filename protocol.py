"""
Dollax Panel — protocol / config generation.

This is the Python port of the Worker's link + subscription + bridge code
(vless_link / vmess_link / trojan_link / ss_link / buildClash / buildSingbox /
xraySetup). Nothing here talks to the network; it is pure string work so it can
be unit-tested.

Only VLESS-over-WS and Trojan-over-WS can be *served* by this Railway app (the
relay in relay.py). VMess and Shadowsocks configs are still generated so an
inbound can carry them, but they need the external Xray bridge bundle from
xray_bridge_config() — the same limitation the Worker had.
"""
import base64
import hashlib
import json
import secrets
import struct
import uuid
from urllib.parse import quote, urlencode

FP_LIST = ["chrome", "firefox", "safari", "ios", "android", "edge", "360", "qq", "random", "randomized"]
SS_METHODS = [
    "chacha20-ietf-poly1305", "aes-128-gcm", "aes-256-gcm",
    "2022-blake3-aes-128-gcm", "2022-blake3-aes-256-gcm",
]
PROTOCOLS = ["vless", "vmess", "trojan", "shadowsocks"]
NETWORKS = ["ws", "xhttp", "grpc", "tcp"]
SECURITIES = ["tls", "reality", "none"]
# what the built-in relay can actually terminate
NATIVE_PROTOCOLS = ["vless", "trojan"]


# ---------------------------------------------------------------- generators
def new_uuid():
    return str(uuid.uuid4())


def new_password(length=24):
    return secrets.token_urlsafe(length)[:length]


def new_token(length=16):
    return secrets.token_urlsafe(length).replace("-", "").replace("_", "")[:length]


def clean_fingerprint(fp):
    fp = str(fp or "").strip().lower()
    return fp if fp in FP_LIST else "chrome"


def clean_protocol(p):
    p = str(p or "vless").strip().lower()
    return p if p in PROTOCOLS else "vless"


def clean_network(n):
    n = str(n or "ws").strip().lower()
    return n if n in NETWORKS else "ws"


def clean_security(s):
    s = str(s or "tls").strip().lower()
    return s if s in SECURITIES else "tls"


def b64(data: str) -> str:
    return base64.b64encode(data.encode()).decode()


def url_b64(data: str) -> str:
    return base64.urlsafe_b64encode(data.encode()).decode().rstrip("=")


# ---------------------------------------------------------------- link builders
def _common_query(inbound, fp, extra=None):
    q = {"type": inbound.get("network") or "ws", "security": inbound.get("security") or "tls"}
    sec = q["security"]
    if sec == "tls":
        q["sni"] = inbound.get("sni") or ""
        if inbound.get("alpn"):
            q["alpn"] = inbound.get("alpn")
    if sec == "reality":
        q["sni"] = inbound.get("sni") or ""
        q["pbk"] = inbound.get("reality_public_key") or ""
        q["sid"] = inbound.get("reality_short_id") or ""
        q["spx"] = inbound.get("reality_spider_x") or "/"
    net = q["type"]
    if net in ("ws", "xhttp"):
        q["host"] = inbound.get("host_header") or ""
        q["path"] = inbound.get("path") or "/"
        if net == "xhttp":
            q["mode"] = inbound.get("xhttp_mode") or "packet-up"
    elif net == "grpc":
        q["serviceName"] = inbound.get("grpc_service_name") or ""
        q["mode"] = inbound.get("grpc_mode") or "gun"
    elif net == "tcp":
        q["headerType"] = inbound.get("header_type") or "none"
    if inbound.get("flow"):
        q["flow"] = inbound["flow"]
    if sec != "none":
        q["fp"] = fp
    if inbound.get("allow_insecure"):
        q["allowInsecure"] = "1"
    if inbound.get("fragment"):
        q["fragment"] = inbound["fragment"]
    if extra:
        q.update({k: v for k, v in extra.items() if v not in (None, "")})
    return urlencode({k: v for k, v in q.items() if v not in (None, "")}, quote_via=quote)


def vless_link(uuid_or_row, address, port, path=None, host=None, sni=None, name="Dollax", **kw):
    """vless://…  Accepts either explicit args (legacy helper) or a dict-ish row."""
    if isinstance(uuid_or_row, dict):
        return vless_link_for(uuid_or_row, uuid_or_row.get("uuid", ""), address, name)
    q = {"type": "ws", "security": "tls", "encryption": "none", "host": host or address,
         "sni": sni or host or address, "path": path or "/", "fp": kw.get("fp") or "chrome"}
    q.update({k: v for k, v in kw.items() if v not in (None, "")})
    return f"vless://{uuid_or_row}@{address}:{port}?{urlencode(q, quote_via=quote)}#{quote(str(name), safe='')}"


def vless_link_for(inbound: dict, client_uuid: str, address: str, name: str) -> str:
    port = inbound.get("port") or 443
    q = _common_query(inbound, clean_fingerprint(inbound.get("fingerprint")))
    q = "encryption=none&" + q
    return f"vless://{client_uuid}@{address}:{port}?{q}#{quote(str(name), safe='')}"


def vmess_link_for(inbound: dict, client_uuid: str, address: str, name: str) -> str:
    payload = {
        "v": "2",
        "ps": str(name),
        "add": address,
        "port": str(inbound.get("port") or 443),
        "id": client_uuid,
        "aid": "0",
        "scy": "auto",
        "net": inbound.get("network") or "ws",
        "type": inbound.get("header_type") or "none",
        "host": inbound.get("host_header") or "",
        "path": inbound.get("path") or "/",
        "tls": "tls" if (inbound.get("security") or "tls") == "tls" else "",
        "sni": inbound.get("sni") or "",
        "alpn": inbound.get("alpn") or "",
        "fp": clean_fingerprint(inbound.get("fingerprint")),
    }
    return "vmess://" + b64(json.dumps(payload, ensure_ascii=False))


def client_secret(inbound: dict, client_uuid: str) -> str:
    """Per-client shared secret for trojan / shadowsocks.

    The Worker used one password per inbound; here every client gets its own
    (its UUID) so the relay can attribute traffic per client.
    """
    return str(client_uuid)


def trojan_link_for(inbound: dict, client_uuid: str, address: str, name: str) -> str:
    q = _common_query(inbound, clean_fingerprint(inbound.get("fingerprint")))
    pw = quote(client_secret(inbound, client_uuid), safe="")
    return f"trojan://{pw}@{address}:{inbound.get('port') or 443}?{q}#{quote(str(name), safe='')}"


def ss_link_for(inbound: dict, client_uuid: str, address: str, name: str) -> str:
    method = inbound.get("ss_method") or "chacha20-ietf-poly1305"
    userinfo = url_b64(f"{method}:{client_secret(inbound, client_uuid)}")
    tag = quote(str(name), safe="")
    return f"ss://{userinfo}@{address}:{inbound.get('port') or 443}#{tag}"


def build_link(inbound: dict, client_uuid: str, address: str, name: str) -> str:
    p = clean_protocol(inbound.get("protocol"))
    if p == "vmess":
        return vmess_link_for(inbound, client_uuid, address, name)
    if p == "trojan":
        return trojan_link_for(inbound, client_uuid, address, name)
    if p == "shadowsocks":
        return ss_link_for(inbound, client_uuid, address, name)
    return vless_link_for(inbound, client_uuid, address, name)


def config_names(inbound: dict, count: int):
    """Deterministic, human-friendly names for the N configs of one inbound."""
    base = str(inbound.get("name") or "Dollax").replace("#", " ").strip()
    css = ["", "-2", "-3", "-4", "-5", "-6", "-7", "-8", "-9", "-10", "-11", "-12"]
    return [base + css[i] if i < len(css) else f"{base}-{i + 1}" for i in range(count)]


def _listify(value):
    """Accept a JSON string, a plain string or a list; return a clean list."""
    if value is None:
        return []
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return []
        if s.startswith("["):
            try:
                parsed = json.loads(s)
            except Exception:
                parsed = None
            if isinstance(parsed, list):
                return [str(x).strip() for x in parsed if str(x).strip()]
        return [line.strip() for line in s.replace(",", "\n").splitlines() if line.strip()]
    try:
        return [str(x).strip() for x in value if str(x).strip()]
    except TypeError:
        return []


def link_list(inbound: dict, client_uuid: str, default_host: str, clean_ips=None):
    """The N configs of one inbound: rotate over clean IPs when present."""
    count = max(1, min(40, int(inbound.get("config_count") or 1)))
    ips = _listify(clean_ips) or _listify(inbound.get("clean_ips"))
    names = config_names(inbound, count)
    links = []
    for i in range(count):
        if ips:
            host = ips[i % len(ips)].split("#")[0].split(":")[0]
        else:
            host = inbound.get("address") or default_host
        links.append(build_link(inbound, client_uuid, host, names[i]))
    return links


def subscription_body(links):
    return b64("\n".join(links))


# ---------------------------------------------------------------- Clash / sing-box
def _yaml_str(v):
    s = str(v)
    if s == "" or any(ch in s for ch in ":#{}[]&*!|>'\"%@`,") or s.strip() != s:
        return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return s


def clash_config(entries, panel_name="Dollax"):
    """entries: [{inbound, client, host, name}]"""
    out = ["proxies:"]
    for e in entries:
        ib, cl = e["inbound"], e["client"]
        p = clean_protocol(ib["protocol"])
        sec = ib.get("security") or "tls"
        lines = [f"  - name: {_yaml_str(e['name'])}", f"    type: {p}", f"    server: {_yaml_str(e['host'])}",
                 f"    port: {ib.get('port') or 443}"]
        if p in ("vless", "vmess"):
            lines.append(f"    uuid: {_yaml_str(cl['uuid'])}")
            if p == "vmess":
                lines += ["    alterId: 0", "    cipher: auto"]
            else:
                lines.append("    udp: true")
                if ib.get("flow"):
                    lines.append(f"    flow: {_yaml_str(ib['flow'])}")
        elif p == "trojan":
            lines.append(f"    password: {_yaml_str(client_secret(ib, cl['uuid']))}")
        elif p == "shadowsocks":
            lines.append(f"    cipher: {_yaml_str(ib.get('ss_method') or 'chacha20-ietf-poly1305')}")
            lines.append(f"    password: {_yaml_str(client_secret(ib, cl['uuid']))}")
        if sec in ("tls", "reality"):
            lines.append("    tls: true")
            if ib.get("sni"):
                lines.append(f"    servername: {_yaml_str(ib['sni'])}")
            if sec == "tls":
                lines.append(f"    client-fingerprint: {_yaml_str(clean_fingerprint(ib.get('fingerprint')))}")
                if ib.get("alpn"):
                    lines.append("    alpn:")
                    for a in str(ib["alpn"]).split(","):
                        lines.append(f"      - {_yaml_str(a.strip())}")
                if ib.get("allow_insecure"):
                    lines.append("    skip-cert-verify: true")
        if ib.get("network") == "ws":
            lines.append("    network: ws")
            lines.append("    ws-opts:")
            lines.append(f"      path: {_yaml_str(ib.get('path') or '/')}")
            if ib.get("host_header"):
                lines.append("      headers:")
                lines.append(f"        Host: {_yaml_str(ib['host_header'])}")
        elif ib.get("network") == "grpc":
            lines.append("    network: grpc")
            lines.append("    grpc-opts:")
            lines.append(f"      grpc-service-name: {_yaml_str(ib.get('grpc_service_name') or '')}")
        out += lines
    out += ["", "proxy-groups:", "  - name: Dollax", "    type: select", "    proxies:"]
    out += [f"      - {_yaml_str(e['name'])}" for e in entries] or ["      - DIRECT"]
    out += ["      - DIRECT", "", "rules:", "  - MATCH,Dollax", ""]
    return "\n".join(out)


def singbox_config(entries):
    outs = []
    tags = []
    for e in entries:
        ib, cl = e["inbound"], e["client"]
        p = clean_protocol(ib["protocol"])
        sec = ib.get("security") or "tls"
        tag = e["name"]
        tags.append(tag)
        o = {"type": p, "tag": tag, "server": e["host"], "server_port": int(ib.get("port") or 443)}
        if p in ("vless", "vmess"):
            o["uuid"] = cl["uuid"]
            if p == "vmess":
                o["security"] = "auto"
                o["alter_id"] = 0
            elif ib.get("flow"):
                o["flow"] = ib["flow"]
        elif p == "trojan":
            o["password"] = client_secret(ib, cl["uuid"])
        elif p == "shadowsocks":
            o["method"] = ib.get("ss_method") or "chacha20-ietf-poly1305"
            o["password"] = client_secret(ib, cl["uuid"])
        if sec in ("tls", "reality"):
            tls = {"enabled": True}
            if ib.get("sni"):
                tls["server_name"] = ib["sni"]
            if sec == "tls":
                tls["utls"] = {"enabled": True, "fingerprint": clean_fingerprint(ib.get("fingerprint"))}
                if ib.get("allow_insecure"):
                    tls["insecure"] = True
                if ib.get("alpn"):
                    tls["alpn"] = [a.strip() for a in str(ib["alpn"]).split(",") if a.strip()]
            else:
                tls["reality"] = {"enabled": True, "public_key": ib.get("reality_public_key") or "",
                                  "short_id": ib.get("reality_short_id") or ""}
            o["tls"] = tls
        if ib.get("network") == "ws":
            o["transport"] = {"type": "ws", "path": ib.get("path") or "/"}
            if ib.get("host_header"):
                o["transport"]["headers"] = {"Host": ib["host_header"]}
        elif ib.get("network") == "grpc":
            o["transport"] = {"type": "grpc", "service_name": ib.get("grpc_service_name") or ""}
        outs.append(o)
    cfg = {
        "log": {"level": "warn"},
        "outbounds": outs + [{"type": "direct", "tag": "direct"}],
        "route": {"rules": [], "final": tags[0] if tags else "direct"},
    }
    return json.dumps(cfg, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------- Xray bridge bundle
def xray_bridge_config(host, inbounds, socks_port=1080, socks_user="dollax", socks_pass="dollax", clients_by_inbound=None):
    """One ws inbound per panel inbound + a SOCKS5 exit, mirroring /api/xray/setup."""
    clients_by_inbound = clients_by_inbound or {}
    inbounds_cfg = [{
        "tag": "socks-in",
        "listen": "127.0.0.1",
        "port": int(socks_port),
        "protocol": "socks",
        "settings": {"auth": "password", "accounts": [{"user": socks_user, "pass": socks_pass}], "udp": True},
    }]
    routing_rules = []
    for i, ib in enumerate(inbounds):
        path = ib.get("path") or f"/ws/{i}"
        tag = f"ws{10000 + i}"
        proto = clean_protocol(ib.get("protocol"))
        if proto in ("vless", "vmess"):
            clients = [{"id": c["uuid"]} for c in clients_by_inbound.get(ib["id"], [])]
            core_protocol = "vless"
            settings = {"clients": clients, "decryption": "none"}
        elif proto == "trojan":
            clients = [{"password": c["uuid"]} for c in clients_by_inbound.get(ib["id"], [])]
            core_protocol = "trojan"
            settings = {"clients": clients}
        else:  # shadowsocks
            core_protocol = "shadowsocks"
            settings = {"method": ib.get("ss_method") or "chacha20-ietf-poly1305",
                        "password": ib.get("ss_password") or "dollax"}
        inbounds_cfg.append({
            "tag": tag,
            "listen": "127.0.0.1",
            "port": 10000 + i,
            "protocol": core_protocol,
            "settings": settings,
            "streamSettings": {
                "network": "ws",
                "wsSettings": {"path": path},
                "security": "none",
            },
            "sniffing": {"enabled": True, "destOverride": ["http", "tls", "quic"]},
        })
        routing_rules.append({"type": "field", "inboundTag": [tag], "outboundTag": "socks-out"})
    cfg = {
        "log": {"loglevel": "warning"},
        "inbounds": inbounds_cfg,
        "outbounds": [
            {"tag": "socks-out", "protocol": "socks", "settings": {"servers": [{"address": "127.0.0.1", "port": int(socks_port)}]}},
            {"tag": "direct", "protocol": "freedom"},
            {"tag": "block", "protocol": "blackhole"},
        ],
        "routing": {"domainStrategy": "AsIs", "rules": routing_rules},
    }
    caddyfile = (
        f"{host} {{\n"
        f"    @dollax {{\n"
        f"        path " + " ".join([f"{(ib.get('path') or '/ws')}*" for ib in inbounds]) + "\n"
        f"    }}\n"
        f"    reverse_proxy @dollax 127.0.0.1:10000\n"
        f"}}\n"
    )
    steps = [
        "1. Install Xray-core on a VPS outside Iran (Germany/France recommended).",
        "2. Save the JSON above as /usr/local/etc/xray/config.json.",
        "3. Start it: xray run -c /usr/local/etc/xray/config.json",
        "4. Put Caddy (or nginx) in front for the TLS certificate (Caddyfile above), or run the ws inbound directly on 443 with your own certs.",
        "5. In this panel, set the inbound Address to that VPS host so the generated configs point at it.",
        f"6. The SOCKS5 exit listens on 127.0.0.1:{socks_port} (user {socks_user}); change it in Settings if needed.",
    ]
    return {
        "host": host,
        "config": json.dumps(cfg, indent=2, ensure_ascii=False),
        "caddyfile": caddyfile,
        "steps": "\n".join(steps),
        "socks": {"port": int(socks_port), "user": socks_user, "pass": socks_pass},
    }


# ---------------------------------------------------------------- wire parsing
def parse_vless_header(data: bytes):
    """VLESS request: [ver=0][uuid16][addon_len][addons…][cmd][port2][atyp][addr][data]"""
    if len(data) < 24 or data[0] != 0:
        return None
    try:
        uid = uuid.UUID(bytes=bytes(data[1:17]))
    except Exception:
        return None
    i = 18 + data[17]
    if len(data) < i + 4:
        return None
    command = data[i]
    if command not in (1, 2):
        return None
    port = struct.unpack(">H", data[i + 1:i + 3])[0]
    atyp = data[i + 3]
    i += 4
    if atyp == 1:
        if len(data) < i + 4:
            return None
        host = ".".join(str(b) for b in data[i:i + 4])
        i += 4
    elif atyp == 2:
        n = data[i] if len(data) > i else 0
        i += 1
        if len(data) < i + n:
            return None
        try:
            host = bytes(data[i:i + n]).decode("utf-8")
        except UnicodeDecodeError:
            return None
        i += n
    elif atyp == 3:
        if len(data) < i + 16:
            return None
        host = ":".join(data[i + j:i + j + 2].hex() for j in range(0, 16, 2))
        i += 16
    else:
        return None
    return {"uuid": str(uid), "command": command, "host": host, "port": port, "offset": i}


def parse_trojan_header(data: bytes, password: str):
    """Trojan request: hex(sha224(password))[56] CRLF cmd atyp addr port CRLF data"""
    if len(data) < 60:
        return None
    expect = hashlib.sha224(str(password).encode()).hexdigest().encode()
    if bytes(data[:56]).lower() != expect:
        return None
    if bytes(data[56:58]) != b"\r\n":
        return None
    cmd = data[58]
    if cmd not in (1, 3):
        return None
    atyp = data[59]
    i = 60
    if atyp == 1:
        if len(data) < i + 4:
            return None
        host = ".".join(str(b) for b in data[i:i + 4])
        i += 4
    elif atyp == 3:
        n = data[i] if len(data) > i else 0
        i += 1
        if len(data) < i + n:
            return None
        try:
            host = bytes(data[i:i + n]).decode("utf-8")
        except UnicodeDecodeError:
            return None
        i += n
    elif atyp == 4:
        if len(data) < i + 16:
            return None
        host = ":".join(data[i + j:i + j + 2].hex() for j in range(0, 16, 2))
        i += 16
    else:
        return None
    if len(data) < i + 4:
        return None
    port = struct.unpack(">H", data[i:i + 2])[0]
    i += 2
    if bytes(data[i:i + 2]) == b"\r\n":
        i += 2
    return {"command": cmd, "host": host, "port": port, "offset": i}


# ---------------------------------------------------------------- misc
def fmt_bytes(n):
    n = float(n or 0)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.2f} {unit}" if unit != "B" else f"{int(n)} B"
        n /= 1024
    return f"{n:.2f} TB"


def random_config_name(used=None):
    """Human-friendly name for one config in a subscription (Vodiwalker-style)."""
    used = used if used is not None else set()
    adjs = ["Rapid", "Silver", "Nova", "Amber", "Quartz", "Onyx", "Iris", "Vega", "Lunar", "Zephyr", "Cobalt", "Ember"]
    nouns = ["Falcon", "Comet", "Cedar", "Harbor", "Lynx", "Orchid", "Summit", "Voyage", "Garnet", "Willow"]
    for _ in range(200):
        name = f"{secrets.choice(adjs)}-{secrets.choice(nouns)}-{secrets.randbelow(90) + 10}"
        if name not in used:
            return name
    return "Dollax-" + new_token(6)
