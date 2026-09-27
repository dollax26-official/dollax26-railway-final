"""
Dollax Panel - FastAPI application (Railway build).

This file is the Python counterpart of the Cloudflare Worker's fetch() router.
Everything the Worker exposed under /api/* is re-implemented here against SQLite,
plus the WebSocket relay entry point that the Worker got from its Durable-Object
free runtime.

Deliberate difference vs the Worker: **there are no outbounds**. The Worker's
inbound could point at an outbound (direct / socks5 / http) to pick the exit;
this app is itself the endpoint, so an inbound is self-contained. See README.md.
"""
import asyncio
import base64
import hashlib
import os
import secrets
import sys
import time
from contextlib import asynccontextmanager
from urllib.parse import urlparse, parse_qs, quote

# --- make the entry point self-sufficient -------------------------------------
# `python main.py` must work on Railway, Nixpacks, Heroku, plain Docker and in
# Python's safe-path/isolated mode, none of which necessarily put the script's
# directory on sys.path (that is what breaks `import db` with ModuleNotFoundError).
_BOOT_DIR = os.path.dirname(os.path.abspath(__file__))
for _p in (_BOOT_DIR, os.getcwd()):
    if _p and _p not in sys.path:
        sys.path.insert(0, _p)

from fastapi import FastAPI, Request, WebSocket, Response
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

import api_extras
import db
import protocol
import relay
import tg_bot
import xray_core
import pages
from pages import dashboard_html, login_html, subscription_page

try:  # real QR codes on the subscription page (graceful without it)
    import qrcode
    import qrcode.image.svg as _qr_svg
except Exception:  # pragma: no cover
    qrcode = None
    _qr_svg = None

APP_VERSION = "2026.09.19-r1"

SESSION_SECRET = os.getenv("SECRET_KEY") or secrets.token_urlsafe(48)


def _materialise_presets():
    """Preset wallpapers may arrive as plain text instead of binaries:

      * static/bg/<name>.jpg.b64             (one base64 blob)
      * static/bg/<name>.jpg.b64.partNN      (the same blob split into chunks)

    so they can be stored through any text-only upload path. Decode them once into the
    real image files the picker serves (static/bg/<name>.jpg).
    """
    bgdir = os.path.join(_HERE, "static", "bg")
    if not os.path.isdir(bgdir):
        return
    names = sorted(os.listdir(bgdir))

    def unpack(label, payload, target):
        if os.path.exists(target):
            return
        try:
            raw = base64.b64decode(payload)
            with open(target, "wb") as fh:
                fh.write(raw)
            print(f"[dollax] preset background ready: {os.path.basename(target)} "
                  f"({len(raw) // 1024} KB, from {label})", flush=True)
        except Exception as exc:  # noqa: BLE001
            print(f"[dollax] preset {label} could not be decoded: {exc}", flush=True)

    # 1. chunked carriers: <image>.partNN - concatenate in order
    groups = {}
    for name in names:
        if ".part" in name:
            base, _, tail = name.rpartition(".part")
            if tail.isdigit():
                groups.setdefault(base, []).append(name)
    for base, parts in sorted(groups.items()):
        target_name = base[:-4] if base.endswith(".b64") else base
        try:
            payload = "".join(
                open(os.path.join(bgdir, p), "r", encoding="utf-8").read().strip()
                for p in sorted(parts)
            )
            unpack(f"{len(parts)} part(s)", payload, os.path.join(bgdir, target_name))
        except Exception as exc:  # noqa: BLE001
            print(f"[dollax] preset parts for {base} failed: {exc}", flush=True)

    # 2. single-file carriers: <image>.b64
    for name in names:
        if not name.endswith(".b64"):
            continue
        try:
            payload = open(os.path.join(bgdir, name), "r", encoding="utf-8").read().strip()
            unpack(os.path.basename(name), payload, os.path.join(bgdir, name[:-4]))
        except Exception as exc:  # noqa: BLE001
            print(f"[dollax] preset {name} could not be read: {exc}", flush=True)


async def _xray_boot():
    """Start the bundled core *after* the panel is already answering.

    The core start is blocking (process spawn + a version probe), and on a platform that
    probes an HTTP path to decide whether a deploy is alive, doing it before `yield` can
    turn a slow core into "application failed to respond". So: answer first, connect later.
    """
    try:
        res = await asyncio.to_thread(_xray_start_now)
        if res and res.get("ok"):
            print(f"[dollax] xray-core started: {len(res.get('port_map') or {})} inbound(s), "
                  f"base port {xray_core.base_port()}", flush=True)
        elif res and res.get("reason"):
            print(f"[dollax] xray-core not running: {res['reason']}", flush=True)
    except Exception as exc:  # noqa: BLE001
        print(f"[dollax] xray-core startup skipped: {exc.__class__.__name__}: {exc}", flush=True)


def _xray_start_now():
    inbounds = _xray_inbounds()
    return xray_core.start(inbounds, _xray_clients(inbounds),
                           outbound_rows=db.list_outbounds(), route_rows=db.list_routes())


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    try:
        _materialise_presets()
    except Exception as exc:  # noqa: BLE001
        print(f"[dollax] preset decode skipped: {exc}", flush=True)
    tasks = []
    try:
        tg_bot.register(sys.modules[__name__])
        if tg_bot.start():                                  # TL robot (only when configured)
            print("[dollax] TL robot started (telegram control bot)", flush=True)
        tasks.append(asyncio.create_task(_xray_boot()))     # never blocks the HTTP server
        tasks.append(asyncio.create_task(_xray_watch()))
    except Exception:  # noqa: BLE001
        pass
    try:
        yield
    finally:
        try:
            tg_bot.stop()
        except Exception:  # noqa: BLE001
            pass
        for t in tasks:
            try:
                t.cancel()
            except Exception:  # noqa: BLE001
                pass


app = FastAPI(title="Dollax Panel", docs_url=None, redoc_url=None, lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET, same_site="lax", https_only=False)
_HERE = os.path.dirname(os.path.abspath(__file__))
_STATIC_DIR = os.path.join(_HERE, "static")
if os.path.isdir(_STATIC_DIR):
    app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")
else:
    # Never kill startup because an asset folder is missing (e.g. a repo push that
    # forgot static/): warn loudly and keep the panel reachable so it can be fixed.
    print("[dollax] WARNING: the 'static' folder is missing next to main.py - the UI will "
          "load unstyled and /static/* will 404. Upload style.css, app.js (and optionally "
          "lost-soul.mp3) into static/. See README §8.", flush=True)


# ---------------------------------------------------------------- helpers
def authed(request: Request) -> bool:
    return bool(request.session.get("user"))


def current_user(request: Request) -> str:
    return str(request.session.get("user") or "")


def guard(request: Request):
    return None if authed(request) else RedirectResponse("/login", status_code=303)


def unauthorized():
    return JSONResponse({"error": "unauthorized"}, status_code=401)


def is_owner(request: Request) -> bool:
    row = db.get_admin(current_user(request))
    return bool(row and row["role"] == "owner" and row["enabled"])


def as_int(v, default=0, lo=0, hi=None):
    try:
        n = int(float(v))
    except Exception:
        n = default
    n = max(lo, n)
    return min(n, hi) if hi is not None else n


def as_float(v, default=0.0, lo=0.0):
    try:
        n = float(v)
    except Exception:
        n = default
    return max(lo, n)


def as_bool(v, default=False):
    if v is None:
        return default
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in ("1", "true", "on", "yes")


def expiry(days=0, expires_at=""):
    at = str(expires_at or "").strip()
    if at:
        return at
    return db.expiry_from_days(as_int(days, 0, 0, 3650))


async def form_data(request: Request) -> dict:
    """Parse an application/x-www-form-urlencoded body (no python-multipart needed)."""
    try:
        body = (await request.body()).decode("utf-8", "ignore")
    except Exception:
        return {}
    return {k: v[0] for k, v in parse_qs(body, keep_blank_values=True).items()}


def client_ip(request: Request) -> str:
    """Real client IP behind Railway's proxy."""
    fwd = request.headers.get("x-forwarded-for") or ""
    if fwd:
        return fwd.split(",")[0].strip()[:64]
    return str(request.headers.get("x-real-ip") or (request.client.host if request.client else "") or "")[:64]


def client_ip_ws(ws: WebSocket) -> str:
    """Same, for a WebSocket connection."""
    fwd = ws.headers.get("x-forwarded-for") or ""
    if fwd:
        return fwd.split(",")[0].strip()[:64]
    return str(ws.headers.get("x-real-ip") or (ws.client.host if ws.client else "") or "")[:64]


# ------------------------------------------------ live connection / IP accounting
# (Vodiwalker enforces per-client connection and IP limits in its relay; so do we now.)
_ACTIVE_CONNS = {}          # client key -> open connections
_SEEN_IPS = {}              # client key -> {ip: last_seen_ts}
_IP_WINDOW = 900           # seconds an IP keeps counting toward the ip limit


def _client_key(client_row) -> str:
    return str(client_row.get("id") or ("inbound:" + str(client_row.get("inbound_id") or "")))


def _admit(client_row, ip: str):
    """Return (ok, reason). Enforces connection_limit and ip_limit before the tunnel opens."""
    key = _client_key(client_row)
    limit_conn = int(client_row.get("connection_limit") or 0)
    limit_ip = int(client_row.get("ip_limit") or 0)
    if limit_conn and _ACTIVE_CONNS.get(key, 0) >= limit_conn:
        return False, f"connection limit ({limit_conn}) reached"
    if limit_ip:
        seen = _SEEN_IPS.setdefault(key, {})
        ts_now = time.time()
        for k, ts in list(seen.items()):
            if ts_now - ts > _IP_WINDOW:
                seen.pop(k, None)
        if ip and ip not in seen and len(seen) >= limit_ip:
            return False, f"ip limit ({limit_ip}) reached"
        if ip:
            seen[ip] = ts_now
    _ACTIVE_CONNS[key] = _ACTIVE_CONNS.get(key, 0) + 1
    return True, ""


def _release(client_row):
    key = _client_key(client_row)
    _ACTIVE_CONNS[key] = max(0, _ACTIVE_CONNS.get(key, 1) - 1)


def _looks_like_ip(value) -> bool:
    parts = str(value or "").strip().split(".")
    return len(parts) == 4 and all(p.isdigit() and 0 <= int(p) <= 255 for p in parts)


def client_remark(cl: dict) -> str:
    """Config names are just the inbound name - no extra traffic/day text.

    (The account summary lives in the separate SUB INFO entry, see info_config.)
    """
    return ""


def info_label(cl: dict) -> str:
    """The name of the SUB INFO entry: the account summary, clearly not a server."""
    if not cl:
        return "SUB INFO"

    limit = int(cl.get("limit_bytes") or 0)
    used = int(cl.get("used_bytes") or 0)
    left = protocol.fmt_bytes(max(0, limit - used)) if limit else "\u221e"
    parts = ["SUB INFO", f"\U0001F464 {str(cl.get('name') or 'client')[:32]}", f"\U0001F4E6 {left} left"]
    # how much has been used: percentage and the raw numbers
    if limit:
        pct = max(0, min(999, round(used / limit * 100)))
        parts.append(f"\U0001F4CA {pct}% used ({protocol.fmt_bytes(used)} / {protocol.fmt_bytes(limit)})")
    else:
        parts.append(f"\U0001F4CA {protocol.fmt_bytes(used)} used")
    if cl.get("expires_at"):
        d = db.days_left(cl.get("expires_at"))
        if d is None:
            parts.append("\u23F3 no expiry")
        elif d < 0:
            parts.append("\u23F3 expired")
        elif d == 0:
            parts.append("\u23F3 ends today")
        else:
            parts.append(f"\u23F3 {d}d left")
    else:
        parts.append("\u23F3 \u221e")
    return " · ".join(parts)


def effective_host(request: Request) -> str:
    base = db.setting("public_base_url", "").strip().rstrip("/")
    if base:
        return urlparse(base).hostname or base
    host = (request.headers.get("x-forwarded-host") or request.headers.get("host") or "localhost").split(":")[0]
    proto = (request.headers.get("x-forwarded-proto") or request.url.scheme or "http").split(",")[0].strip()
    # Remember the public host the first time we are reached over https, so generated
    # configs keep pointing at the real panel address (Railway domain / custom domain)
    # even when a later request arrives with a different Host header.
    if proto == "https" and "." in host and "localhost" not in host and not host.replace(".", "").isdigit():
        try:
            db.set_setting("public_base_url", f"https://{host}")
            print(f"[dollax] detected public base URL: https://{host}", flush=True)
        except Exception:  # noqa: BLE001
            pass
    return host


def base_url(request: Request) -> str:
    base = db.setting("public_base_url", "").strip().rstrip("/")
    if base:
        return base
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme or "https"
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or "localhost"
    return f"{proto}://{host}"


def inbound_dict(row) -> dict:
    d = dict(row)
    d["enabled"] = bool(d.get("enabled"))
    d["allow_insecure"] = bool(d.get("allow_insecure"))
    d["clean_ips"] = db.json_list(d.get("clean_ips"))
    d["native"] = protocol.clean_protocol(d.get("protocol")) in protocol.NATIVE_PROTOCOLS
    d["wg_conf"] = protocol.clean_protocol(d.get("protocol")) == "wireguard"
    d["warn"] = "" if d["native"] else "Served by the bundled Xray-core (not a WebSocket protocol)."
    d["used_bytes"] = int(d.get("used_bytes") or 0)
    d["up_bytes"] = int(d.get("up_bytes") or 0)
    d["down_bytes"] = int(d.get("down_bytes") or 0)
    d["used_human"] = protocol.fmt_bytes(d["used_bytes"])
    d["up_human"] = protocol.fmt_bytes(d["up_bytes"])
    d["down_human"] = protocol.fmt_bytes(d["down_bytes"])
    d["limit_human"] = protocol.fmt_bytes(d.get("limit_bytes") or 0)
    d["days_left"] = db.days_left(d.get("expires_at"))
    d["expired"] = db.is_expired(d.get("expires_at"))
    return d


def _client_inbound_refs(cl: dict) -> list:
    """The client's inbounds: its primary one plus up to four more (max 5 total)."""
    refs = [str(cl.get("inbound_id") or "")]
    for extra in db.json_raw(cl.get("extra_inbounds"), []):
        extra = str(extra or "")
        if extra and extra not in refs:
            refs.append(extra)
    return refs[:5]


def _client_entries(cl: dict, request: Request):
    """[(inbound_dict, uuid, address, location)] for every location this client uses."""
    host = effective_host(request)
    out = []
    for ref in _client_inbound_refs(cl):
        if ref.startswith("node:"):
            node, remote = api_extras.find_remote(ref)
            if not remote:
                continue
            ib = dict(remote)
            ib["_remote"] = True
            ib["_location"] = (node["location"] if node else "") or (node["name"] if node else "")
            uuid = remote.get("uuid") or cl.get("uuid")
            out.append((ib, uuid, remote.get("address") or host,
                        (node["location"] if node else "") or (node["name"] if node else "")))
            continue
        row = db.inbound_row(ref)
        if not row:
            continue
        ib = api_extras.link_inbound(dict(row), request)
        ib["clean_ips"] = db.json_list(ib.get("clean_ips"))
        ips = db.json_list(cl.get("clean_ips")) or ib.get("clean_ips") or []
        addr = ib.get("address") or host
        for candidate in (ips, ib.get("clean_ips")):
            items = db.json_list(candidate) if candidate else []
            if items:
                addr = str(items[0]).split("#")[0].split(":")[0]
                break
        out.append((ib, cl.get("uuid"), addr, ""))
    return out


def _client_links(cl: dict, request: Request):
    """Every config this client owns (2 per inbound by default, one per location)."""
    count = max(1, min(10, int(cl.get("config_count") or 2)))
    links, wg = [], False
    for ib, uuid, addr, location in _client_entries(cl, request):
        remark = client_remark(cl) + (f" · {location}" if location else "")
        if protocol.clean_protocol(ib.get("protocol")) == "wireguard":
            links.append(protocol.wireguard_conf(ib, uuid, addr, cl.get("name") or ""))
            wg = True
            continue
        links += protocol.link_list(ib, uuid, addr, cl.get("clean_ips") or ib.get("clean_ips"),
                                    remark=remark, count=count)
    return links, wg


def client_dict(row, request: Request, inbound=None) -> dict:
    d = dict(row)
    d["enabled"] = bool(d.get("enabled"))
    d["clean_ips"] = db.json_list(d.get("clean_ips"))
    d["used_bytes"] = int(d.get("used_bytes") or 0)
    d["up_bytes"] = int(d.get("up_bytes") or 0)
    d["down_bytes"] = int(d.get("down_bytes") or 0)
    d["used_human"] = protocol.fmt_bytes(d["used_bytes"])
    d["up_human"] = protocol.fmt_bytes(d["up_bytes"])
    d["down_human"] = protocol.fmt_bytes(d["down_bytes"])
    d["limit_human"] = protocol.fmt_bytes(d.get("limit_bytes") or 0)
    d["last_config_at"] = d.get("last_config_at") or ""
    d["sub_fetches"] = int(d.get("sub_fetches") or 0)
    d["created_by"] = d.get("created_by") or ""
    d["extra_inbounds"] = [str(x) for x in db.json_raw(d.get("extra_inbounds"), [])]
    d["config_count"] = max(1, min(10, int(d.get("config_count") or 2)))
    d["linked"] = [{"id": c["id"], "name": c["name"], "sub_token": c["sub_token"],
                    "config_count": int(c.get("config_count") or 2)}
                   for c in db.linked_clients(d["id"])]
    d["days_left"] = db.days_left(d.get("expires_at"))
    d["expired"] = db.is_expired(d.get("expires_at"))
    d["over_quota"] = bool(d.get("limit_bytes")) and d["used_bytes"] >= int(d["limit_bytes"])
    d["active"] = d["enabled"] and not d["expired"] and not d["over_quota"]
    ib = dict(inbound) if inbound is not None else dict(db.inbound_row(d["inbound_id"]) or {})
    ib["clean_ips"] = db.json_list(ib.get("clean_ips"))
    d["inbound_name"] = ib.get("name", "")
    d["inbound_protocol"] = ib.get("protocol", "")
    host = effective_host(request)
    ips = d["clean_ips"] or ib.get("clean_ips") or []
    links, wg_conf = _client_links(d, request)
    d["locations"] = [{"address": addr, "location": loc, "inbound": eib.get("name")}
                      for eib, _uuid, addr, loc in _client_entries(d, request)]
    if links:
        d["links"] = links
        d["link"] = links[0]
        d["wg_conf"] = wg_conf
        return d
    if ib and protocol.clean_protocol(ib.get("protocol")) == "wireguard":
        # WireGuard is not a URI: hand back a ready-to-use .conf block instead
        d["links"] = [protocol.wireguard_conf(ib, d["uuid"], host, d.get("name") or "")]
        d["link"] = d["links"][0]
        d["wg_conf"] = True
    else:
        links = protocol.link_list(ib, d["uuid"], host, ips, remark=client_remark(d)) if ib else []
        d["links"] = links
        d["link"] = links[0] if links else ""
        d["wg_conf"] = False
    d["sub_url"] = f"{base_url(request)}/sub/{d.get('sub_token') or ''}"
    d["usage_pct"] = int(min(100, (d["used_bytes"] / int(d["limit_bytes"]) * 100))) if d.get("limit_bytes") else 0
    return d


def entry_for(row, request: Request):
    """(inbound, client) pair used to build a config."""
    if row.keys() and "inbound_id" in row.keys():
        ib = db.inbound_row(row["inbound_id"])
        return (dict(ib) if ib else {}), dict(row)
    return dict(row), {}


# ---------------------------------------------------------------- pages
@app.get("/health")
async def health():
    """Cheap liveness probe: never raises, never touches the relay or the core."""
    try:
        info = db.db_status()
    except Exception as exc:  # noqa: BLE001
        info = {"path": "", "journal": "", "writable": False, "sqlite": "",
                "error": f"{exc.__class__.__name__}: {exc}"}
    return {
        "ok": True, "service": "dollax-panel", "version": APP_VERSION,
        "db": info.get("path", ""), "journal": info.get("journal", ""),
        "writable": bool(info.get("writable")), "sqlite": info.get("sqlite", ""),
        "core": "xray" if xray_core.is_running() else "internal-relay",
    }


@app.get("/login", response_class=HTMLResponse)
async def login_page():
    return login_html(db.setting("panel_name", "Dollax Panel"))


@app.post("/login")
async def do_login(request: Request):
    form = await form_data(request)
    username = str(form.get("username", "")).strip()
    password = str(form.get("password", ""))
    row = db.get_admin(username)
    if not row or not row["enabled"] or not db.verify_password(password, row["password_hash"]):
        return HTMLResponse(login_html(db.setting("panel_name", "Dollax Panel"), "Invalid username or password."), status_code=401)
    request.session["user"] = username
    request.session["ip"] = client_ip(request)
    db.log(username, "login", ip=client_ip(request))
    return RedirectResponse("/", status_code=303)


@app.post("/logout")
async def do_logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    r = guard(request)
    return r or dashboard_html(db.setting("panel_name", "Dollax Panel"), APP_VERSION)


# ---------------------------------------------------------------- session / account
@app.get("/api/me")
async def api_me(request: Request):
    if not authed(request):
        return unauthorized()
    user = current_user(request)
    row = db.get_admin(user)
    return {"username": user, "role": (row["role"] if row else "admin"), "prefs": db.get_prefs(user),
            "version": APP_VERSION, "host": effective_host(request),
            "sections": (sorted(api_extras.admin_scope(request)[1]) if api_extras.admin_scope(request)[1] is not None else "all"),
            "inbounds_scope": (sorted(api_extras.admin_scope(request)[0]) if api_extras.admin_scope(request)[0] is not None else "all")}


@app.post("/api/me/password")
async def api_change_password(request: Request):
    if not authed(request):
        return unauthorized()
    d = await request.json()
    user = current_user(request)
    row = db.get_admin(user)
    if not db.verify_password(str(d.get("current", "")), row["password_hash"] if row else ""):
        return JSONResponse({"error": "Current password is wrong."}, status_code=400)
    new = str(d.get("new", ""))
    if len(new) < 4:
        return JSONResponse({"error": "New password is too short."}, status_code=400)
    db.set_password(user, new)
    db.log(user, "password-change")
    return {"ok": True}


@app.post("/api/me/prefs")
async def api_me_prefs(request: Request):
    if not authed(request):
        return unauthorized()
    d = await request.json()
    prefs = db.get_prefs(current_user(request))
    prefs.update({k: v for k, v in (d or {}).items()
                 if k in ("language", "theme", "style", "font", "music", "music_volume", "music_track",
                          "accent", "motion", "background", "bg_dim", "bg_blur", "bg_enabled",
                          "sub_template", "reality_host", "reality_public_port")})
    db.set_prefs(current_user(request), prefs)
    return {"ok": True, "prefs": prefs}


# ------------------------------------------------- per-user appearance assets
BG_MIME = {"image/jpeg", "image/jpg", "image/png", "image/webp"}
BG_MAX = 3_500_000


@app.get("/api/backgrounds")
async def api_backgrounds(request: Request):
    """Preset wallpapers shipped in static/bg + whether this admin uploaded one."""
    if not authed(request):
        return unauthorized()
    presets = []
    bgdir = os.path.join(_HERE, "static", "bg")
    if os.path.isdir(bgdir):
        for name in sorted(os.listdir(bgdir)):
            if name.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                presets.append({"id": os.path.splitext(name)[0], "url": f"/static/bg/{name}",
                                "bytes": os.path.getsize(os.path.join(bgdir, name))})
    row = db.get_asset(current_user(request), "background")
    return {"presets": presets, "custom": row is not None,
            "custom_updated": (row["updated"] if row else "")}


@app.get("/api/me/background")
async def api_get_background(request: Request):
    """This admin's uploaded background only (no other user can read it)."""
    if not authed(request):
        return unauthorized()
    row = db.get_asset(current_user(request), "background")
    if not row:
        return Response(status_code=204)
    return Response(content=bytes(row["bytes"]), media_type=row["mime"] or "image/jpeg",
                    headers={"Cache-Control": "no-store"})


@app.post("/api/me/background")
async def api_set_background(request: Request):
    if not authed(request):
        return unauthorized()
    d = await request.json()
    payload = str((d or {}).get("data") or "")
    mime = str((d or {}).get("mime") or "image/jpeg").lower()
    b64 = payload
    if payload.startswith("data:") and "," in payload:
        head, b64 = payload.split(",", 1)
        mime = (head[5:].split(";")[0] or mime).lower()
    if mime not in BG_MIME:
        return JSONResponse({"error": "Only JPEG, PNG or WebP images."}, status_code=400)
    try:
        raw = base64.b64decode(b64, validate=False)
    except Exception:
        return JSONResponse({"error": "That is not valid image data."}, status_code=400)
    if not raw:
        return JSONResponse({"error": "Empty image."}, status_code=400)
    if len(raw) > BG_MAX:
        return JSONResponse({"error": f"Image too large ({len(raw) // 1024} KB). Keep it under 3 MB."},
                            status_code=413)
    db.set_asset(current_user(request), "background", raw, mime)
    db.log(current_user(request), "background-upload", f"{len(raw) // 1024} KB {mime}", ip=client_ip(request))
    return {"ok": True, "bytes": len(raw), "mime": mime}


@app.delete("/api/me/background")
async def api_delete_background(request: Request):
    if not authed(request):
        return unauthorized()
    removed = db.delete_asset(current_user(request), "background")
    prefs = db.get_prefs(current_user(request))
    prefs["background"] = "none"
    db.set_prefs(current_user(request), prefs)
    db.log(current_user(request), "background-remove", ip=client_ip(request))
    return {"ok": True, "removed": removed, "prefs": prefs}


# ------------------------------------------------- per-admin music library
TRACK_MIME = {"audio/mpeg", "audio/mp3", "audio/ogg", "audio/wav", "audio/x-wav", "audio/mp4",
              "audio/aac", "audio/webm", "audio/flac"}
TRACK_MAX = 9_000_000


@app.get("/api/me/tracks")
async def api_list_tracks(request: Request):
    if not authed(request):
        return unauthorized()
    return {"items": db.list_tracks(current_user(request))}


@app.post("/api/me/tracks")
async def api_add_track(request: Request):
    """Upload a track into the signed-in admin's own library (stored, not re-uploaded)."""
    if not authed(request):
        return unauthorized()
    d = await request.json()
    payload = str((d or {}).get("data") or "")
    mime = str((d or {}).get("mime") or "audio/mpeg").lower()
    name = str((d or {}).get("name") or "track")[:120]
    b64 = payload
    if payload.startswith("data:") and "," in payload:
        head, b64 = payload.split(",", 1)
        mime = (head[5:].split(";")[0] or mime).lower()
    if mime not in TRACK_MIME:
        return JSONResponse({"error": "Only audio files (mp3, ogg, wav, m4a, webm, flac)."}, status_code=400)
    try:
        raw = base64.b64decode(b64, validate=False)
    except Exception:
        return JSONResponse({"error": "That is not valid audio data."}, status_code=400)
    if not raw:
        return JSONResponse({"error": "Empty file."}, status_code=400)
    if len(raw) > TRACK_MAX:
        return JSONResponse({"error": f"File too large ({len(raw) // 1024} KB). Keep it under 9 MB."},
                            status_code=413)
    tid = db.add_track(current_user(request), name, mime, raw)
    db.log(current_user(request), "music-upload", f"{name} ({len(raw) // 1024} KB)", ip=client_ip(request))
    return {"ok": True, "id": tid, "bytes": len(raw), "items": db.list_tracks(current_user(request))}


@app.get("/api/me/tracks/{tid}/audio")
async def api_track_audio(request: Request, tid: str):
    if not authed(request):
        return unauthorized()
    row = db.get_track(current_user(request), tid)
    if not row:
        return Response(status_code=204)
    return Response(content=bytes(row["bytes"]), media_type=row["mime"] or "audio/mpeg",
                    headers={"Cache-Control": "no-store"})


@app.delete("/api/me/tracks/{tid}")
async def api_delete_track(request: Request, tid: str):
    if not authed(request):
        return unauthorized()
    removed = db.delete_track(current_user(request), tid)
    prefs = db.get_prefs(current_user(request))
    if prefs.get("music_track") == tid:
        prefs["music_track"] = "default"
        db.set_prefs(current_user(request), prefs)
    db.log(current_user(request), "music-remove", tid, ip=client_ip(request))
    return {"ok": True, "removed": removed, "items": db.list_tracks(current_user(request)), "prefs": prefs}


# ---------------------------------------------------------------- overview
@app.get("/api/summary")
async def api_summary(request: Request):
    if not authed(request):
        return unauthorized()
    inbounds = db.list_inbounds()
    clients = db.list_clients()
    total_used = sum(int(c.get("used_bytes") or 0) for c in clients)
    total_up = sum(int(c.get("up_bytes") or 0) for c in clients)
    total_down = sum(int(c.get("down_bytes") or 0) for c in clients)
    active = sum(1 for c in clients if c["enabled"] and not db.is_expired(c.get("expires_at")))
    native = sum(1 for i in inbounds if protocol.clean_protocol(i["protocol"]) in protocol.NATIVE_PROTOCOLS)
    return {
        "inbounds": len(inbounds), "clients": len(clients), "active_clients": active,
        "native_inbounds": native,
        "total_used_bytes": total_used, "total_used_human": protocol.fmt_bytes(total_used),
        "total_up_bytes": total_up, "total_up_human": protocol.fmt_bytes(total_up),
        "total_down_bytes": total_down, "total_down_human": protocol.fmt_bytes(total_down),
        "transport": "WSS", "host": effective_host(request), "version": APP_VERSION,
        "default_port": db.setting("default_port", "443"),
    }


@app.get("/api/diagnostics")
async def api_diagnostics(request: Request):
    if not authed(request):
        return unauthorized()
    inbounds = db.list_inbounds()
    clients = db.list_clients()
    checks = []

    def add(level, title, detail, fix=""):
        checks.append({"level": level, "title": title, "detail": detail, "fix": fix})

    if not db.setting("public_base_url"):
        add("warn", "Public base URL is not set",
            "Links fall back to the request host, which can be wrong behind a proxy.",
            "Settings → Public base URL → set your Railway domain.")
    else:
        add("ok", "Public base URL set", db.setting("public_base_url"))
    if not inbounds:
        add("warn", "No inbound yet", "Create one on the Inbounds page.", "Inbounds → Add inbound")
    else:
        add("ok", f"{len(inbounds)} inbound(s)", ", ".join(i["name"] for i in inbounds[:6]))
    if not clients:
        add("warn", "No client yet", "An inbound alone has no credentials.", "Clients → Add client")
    else:
        add("ok", f"{len(clients)} client(s)", f"{sum(1 for c in clients if c['enabled'])} enabled")
    xst = xray_core.status()
    non_native = [i["name"] for i in inbounds
                  if protocol.clean_protocol(i["protocol"]) not in protocol.NATIVE_PROTOCOLS]
    if xst["running"]:
        add("ok", "Xray-core is running",
            f"{xst['inbounds']} inbound(s) bridged on localhost:{xst['base_port']}+ | {xst['version']}")
        if non_native:
            add("ok", f"{len(non_native)} inbound(s) served by Xray-core",
                f"{', '.join(non_native[:6])} - VMess/Shadowsocks and UDP are handled by the core.")
    elif non_native:
        add("warn", "Xray-core is not running",
            f"{', '.join(non_native[:6])} are VMess/Shadowsocks and the core is unavailable "
            f"({xst['last_error'] or 'not installed'}).",
            "Set XRAY_MODE=on (it is installed in the image) or run an external Xray bridge.")
    else:
        add("ok", "All inbounds served by the built-in relay", "VLESS/Trojan over WebSocket.")
    host_touched = [i["name"] for i in inbounds if i.get("address") and _looks_like_ip(i["address"])]
    if host_touched:
        add("warn", "Inbound address is a bare IP",
            f"{', '.join(host_touched[:4])} - clients will connect to that IP, which only works if that "
            "IP actually fronts this panel (e.g. a Cloudflare-proxied domain). Railway's own domain works "
            "directly: leave Address empty or use the panel domain.",
            "Inbounds → Edit → Address → Use panel domain")
    with_clean = [i["name"] for i in inbounds if db.json_list(i.get("clean_ips"))]
    # Reality / port sanity: configs that cannot work through the public HTTPS port
    try:
        default_port = as_int(db.setting("default_port", "443"), 443, 1, 65535)
        rhost, rport = api_extras.reality_endpoint()
        panel_host = effective_host(request)
        for row in inbounds:
            ib = dict(row)
            if not ib.get("enabled") or protocol.clean_protocol(ib.get("protocol")) == "wireguard":
                continue
            addr = str(ib.get("address") or "")
            if str(ib.get("security") or "").lower() == "reality":
                if rport and (not addr or addr == panel_host):
                    add("ok", "Reality uses the raw TCP endpoint",
                        f"{ib['name']} -> {rhost}:{rport} (from Settings -> Xray-core)")
                elif not addr or addr == panel_host:
                    add("warn", "Reality has no raw TCP endpoint",
                        f"{ib['name']}: Reality cannot pass through the HTTPS port. Set the "
                        "Reality domain + public port in Settings -> Xray-core (after creating a "
                        "Railway TCP proxy), or put the TCP-proxy address in the inbound.",
                        "Settings -> Xray-core -> Reality TCP domain / public port")
                else:
                    add("ok", "Reality endpoint set on the inbound",
                        f"{ib['name']} -> {addr}:{ib.get('port')}")
            elif str(ib.get("flow") or "") and str(ib.get("network") or "ws").lower() != "tcp":
                add("warn", "Flow is set on a non-TCP transport",
                    f"{ib['name']}: flow=xtls-rprx-vision only works with TCP/Reality "
                    f"(this inbound uses {ib.get('network')}); clear the flow or switch to TCP.",
                    "Inbounds -> Edit -> Flow")
            elif int(ib.get("port") or 0) not in (default_port, 443):
                add("warn", "Inbound port is not reachable through the panel domain",
                    f"{ib['name']} uses port {ib.get('port')} while clients reach the panel on "
                    f"{default_port}; fix the inbound's port or the panel's default port.",
                    "Inbounds -> Edit -> Port")
    except Exception:  # noqa: BLE001
        pass

    if with_clean:
        add("ok", f"{len(with_clean)} inbound(s) rotate clean IPs", ", ".join(with_clean[:6]))
    else:
        add("info", "No clean IPs set", "Optionally paste edge IPs into an inbound to rotate addresses.",
            "Inbounds → Edit → Clean IPs")
    if not (request.headers.get("x-forwarded-proto") or "").startswith("https") and "https" not in str(request.url):
        add("warn", "Served over plain HTTP", "TLS is terminated by Railway's edge in production.", "")
    add("ok", "Relay",
        "VLESS/Trojan over WebSocket are served by the panel itself; with Xray-core running, VMess, Shadowsocks and UDP work through it as well.")
    return {"checks": checks, "version": APP_VERSION}


@app.get("/api/activity")
async def api_activity(request: Request):
    if not authed(request):
        return unauthorized()
    if not api_extras.section_allowed(request, "logs"):
        return JSONResponse({"error": "Your account cannot open that section."}, status_code=403)
    return {"items": db.activity(120)}


# ---------------------------------------------------------------- inbounds
@app.get("/api/subtemplates")
async def api_subtemplates(request: Request):
    if not authed(request):
        return unauthorized()
    mine = str((db.get_prefs(current_user(request)) or {}).get("sub_template") or "aurora")
    return {"items": pages.TEMPLATE_LIST, "current": mine,
            "preview_url": f"{base_url(request)}/info/{{token}}?template={{id}}"}


@app.get("/api/protocols")
async def api_protocols(request: Request):
    if not authed(request):
        return unauthorized()
    return {
        "protocols": protocol.PROTOCOLS, "networks": protocol.NETWORKS, "securities": protocol.SECURITIES,
        "fingerprints": protocol.FP_LIST, "ss_methods": protocol.SS_METHODS,
        "native": protocol.NATIVE_PROTOCOLS,
    }


def _inbound_payload(d: dict, existing=None):
    """Normalise + validate an inbound payload (shared by create and update)."""
    name = str(d.get("name") or d.get("label") or (existing["name"] if existing else "VLESS WS")).strip()[:80]
    proto = protocol.clean_protocol(d.get("protocol", existing["protocol"] if existing else "vless"))
    net = protocol.clean_network(d.get("network", existing["network"] if existing else "ws"))
    sec = protocol.clean_security(d.get("security", existing["security"] if existing else "tls"))
    path = str(d.get("path", existing["path"] if existing else "") or "").strip()
    if not path:
        path = "/ws/" + protocol.new_token(10)
    if not path.startswith("/"):
        path = "/" + path
    if len(path) > 180 or any(ch in path for ch in (" ", "?", "#")):
        return None, "Invalid WebSocket path."
    port = as_int(d.get("port", existing["port"] if existing else db.setting("default_port", "443")), 443, 1, 65535)
    host = str(d.get("host_header", existing["host_header"] if existing else "") or "").strip()[:253]
    sni = str(d.get("sni", existing["sni"] if existing else "") or "").strip()[:253]
    fields = {
        "name": name or "Inbound",
        "protocol": proto, "network": net, "security": sec,
        "address": str(d.get("address", existing["address"] if existing else "") or "").strip()[:253],
        "port": port, "path": path,
        "host_header": host, "sni": sni,
        "alpn": str(d.get("alpn", existing["alpn"] if existing else "http/1.1") or "")[:100],
        "fingerprint": protocol.clean_fingerprint(d.get("fingerprint", existing["fingerprint"] if existing else "chrome")),
        "flow": str(d.get("flow", existing["flow"] if existing else "") or "")[:60],
        "grpc_service_name": str(d.get("grpc_service_name", existing["grpc_service_name"] if existing else "") or "")[:80],
        "grpc_mode": str(d.get("grpc_mode", existing["grpc_mode"] if existing else "gun") or "gun")[:20],
        "xhttp_mode": str(d.get("xhttp_mode", existing["xhttp_mode"] if existing else "packet-up") or "packet-up")[:20],
        "header_type": str(d.get("header_type", existing["header_type"] if existing else "none") or "none")[:20],
        "allow_insecure": 1 if as_bool(d.get("allow_insecure", existing["allow_insecure"] if existing else 0)) else 0,
        "reality_public_key": str(d.get("reality_public_key", existing["reality_public_key"] if existing else "") or "")[:120],
        "reality_short_id": str(d.get("reality_short_id", existing["reality_short_id"] if existing else "") or "")[:40],
        "reality_spider_x": str(d.get("reality_spider_x", existing["reality_spider_x"] if existing else "/") or "/")[:120],
        "ss_method": str(d.get("ss_method", existing["ss_method"] if existing else "chacha20-ietf-poly1305") or "chacha20-ietf-poly1305")[:60],
        "ss_password": str(d.get("ss_password", existing["ss_password"] if existing else "") or "")[:120],
        "wg_public_key": str(d.get("wg_public_key", existing["wg_public_key"] if existing else "") or "")[:120],
        "wg_private_key": str(d.get("wg_private_key", existing["wg_private_key"] if existing and "wg_private_key" in existing.keys() else "") or "")[:120],
        "wg_address": str(d.get("wg_address", existing["wg_address"] if existing else "") or "")[:120],
        "reality_private_key": str(d.get("reality_private_key",
            existing["reality_private_key"] if existing and "reality_private_key" in existing.keys() else "") or "")[:120],
        "reality_dest": str(d.get("reality_dest",
            existing["reality_dest"] if existing and "reality_dest" in existing.keys() else "") or "")[:160],
        "fragment": str(d.get("fragment", existing["fragment"] if existing else "") or "")[:120],
        # the inbound may pick addresses from the Hosts pool: same rotation mechanism
        "clean_ips": db.json_list(d.get("hosts", d.get("clean_ips", existing["clean_ips"] if existing else []))),
        "note": str(d.get("note", existing["note"] if existing else "") or "")[:500],
    }
    if "limit_bytes" in d:
        fields["limit_bytes"] = as_int(d.get("limit_bytes"), 0, 0)
    elif "limit_value" in d:
        fields["limit_bytes"] = int(as_float(d.get("limit_value")) * 1024 ** 3)
    else:
        fields["limit_bytes"] = int(existing["limit_bytes"]) if existing else 0
    if "expires_at" in d and str(d.get("expires_at") or "").strip():
        fields["expires_at"] = str(d["expires_at"])[:40]
    elif "expires_days" in d:
        fields["expires_at"] = expiry(d.get("expires_days"))
    else:
        fields["expires_at"] = existing["expires_at"] if existing else ""
    fields["ip_limit"] = as_int(d.get("ip_limit", existing["ip_limit"] if existing else 0), 0, 0, 5000)
    fields["connection_limit"] = as_int(d.get("connection_limit", existing["connection_limit"] if existing else 0), 0, 0, 100000)
    fields["client_limit"] = as_int(d.get("client_limit", existing["client_limit"] if existing else 0), 0, 0, 10000)
    fields["config_count"] = as_int(d.get("config_count", existing["config_count"] if existing else 1), 1, 1, 40)
    fields["enabled"] = 1 if as_bool(d.get("enabled", existing["enabled"] if existing else 1), True) else 0
    # sensible defaults: a blank host header / SNI follows the inbound address
    if fields["address"]:
        # keep just the host: strip a scheme, a path and a port that duplicates the port field
        addr = str(fields["address"]).strip()
        for prefix in ("https://", "http://"):
            if addr.lower().startswith(prefix):
                addr = addr[len(prefix):]
        addr = addr.split("/")[0].strip()
        if addr.endswith(":" + str(fields["port"])):
            addr = addr[: -(len(str(fields["port"])) + 1)]
        fields["address"] = addr
    if fields["address"]:
        if not fields["host_header"]:
            fields["host_header"] = fields["address"]
        if not fields["sni"] and fields["security"] != "none":
            fields["sni"] = fields["address"]
    protocol.finalise_keys(fields)

    return fields, ""


@app.get("/api/inbounds")
async def api_list_inbounds(request: Request):
    if not authed(request):
        return unauthorized()
    rows = db.list_inbounds()
    remote = []
    for ib in api_extras.node_inbounds():
        ib = dict(ib)
        ib["remote"] = True
        ib["ref"] = f"node:{ib.get('node_id')}:{ib.get('id')}"
        ib["address"] = ib.get("address") or ""
        ib["used_human"] = protocol.fmt_bytes(int(ib.get("used_bytes") or 0))
        ib["limit_human"] = protocol.fmt_bytes(int(ib.get("limit_bytes") or 0))
        ib["client_count"] = int(ib.get("clients") or 0)
        remote.append(ib)
    items = [inbound_dict(r) for r in rows]
    allowed_ibs, _ = api_extras.admin_scope(request)
    if allowed_ibs is not None:            # an admin with a limited access list
        items = [i for i in items if str(i["id"]) in allowed_ibs]
        remote = []
    return {"items": items, "remote": remote,
            "nodes": [{"id": n["id"], "name": n["name"], "location": n["location"], "flag": n["flag"],
                       "status": n["status"]} for n in db.list_nodes()]}
@app.post("/api/inbounds")
async def api_create_inbound(request: Request):
    if not authed(request):
        return unauthorized()
    d = await request.json()
    fields, err = _inbound_payload(d or {})
    if err:
        return JSONResponse({"error": err}, status_code=400)
    try:
        iid = db.create_inbound(fields)
    except Exception:
        return JSONResponse({"error": "That WebSocket path already exists."}, status_code=409)
    db.log(current_user(request), "inbound-create", fields["name"], ip=client_ip(request))
    ib = inbound_dict(db.inbound_row(iid))
    self_uuid = db.inbound_row(iid)["uuid"]
    ib["links"] = protocol.link_list(api_extras.link_inbound(ib, request), self_uuid, effective_host(request))
    ib["link"] = ib["links"][0] if ib["links"] else ""
    ib["sub_url"] = f"{base_url(request)}/sub/{db.inbound_row(iid)['sub_token']}"
    return {"ok": True, "id": iid, "inbound": ib}


@app.patch("/api/inbounds/{iid}")
async def api_update_inbound(request: Request, iid: str):
    if not authed(request):
        return unauthorized()
    row = db.inbound_row(iid)
    if not row:
        return JSONResponse({"error": "Inbound not found"}, status_code=404)
    d = await request.json()
    fields, err = _inbound_payload(d or {}, existing=row)
    if err:
        return JSONResponse({"error": err}, status_code=400)
    try:
        db.update_inbound(iid, fields)
    except Exception:
        return JSONResponse({"error": "That WebSocket path already exists."}, status_code=409)
    db.log(current_user(request), "inbound-update", fields["name"], ip=client_ip(request))
    ib = inbound_dict(db.inbound_row(iid))
    self_uuid = db.inbound_row(iid)["uuid"]
    ib["links"] = protocol.link_list(ib, self_uuid, effective_host(request))
    ib["link"] = ib["links"][0] if ib["links"] else ""
    return {"ok": True, "inbound": ib}


@app.post("/api/inbounds/{iid}/toggle")
async def api_toggle_inbound(request: Request, iid: str):
    if not authed(request):
        return unauthorized()
    row = db.inbound_row(iid)
    if not row:
        return JSONResponse({"error": "Inbound not found"}, status_code=404)
    db.update_inbound(iid, {"enabled": 0 if row["enabled"] else 1})
    return {"ok": True, "enabled": not bool(row["enabled"])}


@app.post("/api/inbounds/{iid}/regenerate")
async def api_regenerate_inbound(request: Request, iid: str):
    if not authed(request):
        return unauthorized()
    if not db.inbound_row(iid):
        return JSONResponse({"error": "Inbound not found"}, status_code=404)
    new_path = "/ws/" + protocol.new_token(10)
    db.update_inbound(iid, {"path": new_path})
    for c in db.clients_for_inbound(iid):
        db.regenerate_client(c["id"])
    db.log(current_user(request), "inbound-regenerate", iid)
    return {"ok": True, "path": new_path}


@app.delete("/api/inbounds/{iid}")
async def api_delete_inbound(request: Request, iid: str):
    if not authed(request):
        return unauthorized()
    ok = db.delete_inbound(iid)
    db.log(current_user(request), "inbound-delete", iid)
    return {"ok": ok}


@app.post("/api/inbounds/bulk")
async def api_bulk_inbound(request: Request):
    if not authed(request):
        return unauthorized()
    d = await request.json()
    ids = [str(x) for x in (d.get("ids") or [])]
    action = str(d.get("action") or "")
    if not ids:
        return JSONResponse({"error": "Nothing selected."}, status_code=400)
    n = 0
    for iid in ids:
        if action == "delete":
            n += 1 if db.delete_inbound(iid) else 0
        elif action in ("enable", "disable"):
            db.update_inbound(iid, {"enabled": 1 if action == "enable" else 0})
            n += 1
        elif action == "reset-usage":
            import json
            with db.conn() as c:
                c.execute("UPDATE inbounds SET used_bytes=0 WHERE id=?", (iid,))
                c.commit()
            n += 1
    db.log(current_user(request), "inbound-bulk", f"{action} x{n}")
    return {"ok": True, "affected": n}


@app.get("/api/inbounds/{iid}/info")
async def api_inbound_info(request: Request, iid: str):
    if not authed(request):
        return unauthorized()
    row = db.inbound_row(iid)
    if not row:
        return JSONResponse({"error": "Inbound not found"}, status_code=404)
    ib = inbound_dict(row)
    clients = [client_dict(c, request, inbound=dict(row)) for c in db.clients_for_inbound(iid)]
    self_cl = _inbound_as_client(row)
    return {"inbound": ib, "clients": clients,
            "self_link": (protocol.link_list(api_extras.link_inbound(ib, request), self_cl["uuid"],
                                             effective_host(request)) or [""])[0] if self_cl["uuid"] else "",
            "sub_url": f"{base_url(request)}/sub/{row['sub_token']}",
            "config_count": int(row["config_count"] or 1)}


# ---------------------------------------------------------------- clients
@app.get("/api/clients")
async def api_list_clients(request: Request):
    if not authed(request):
        return unauthorized()
    rows = _visible_clients(request)
    ids = {r["inbound_id"] for r in rows}
    for r in rows:
        for ref in db.json_raw(r.get("extra_inbounds"), []):
            ref = str(ref)
            if ref and not ref.startswith("node:"):
                ids.add(ref)
    cache = {}
    for iid in ids:
        rec = db.inbound_row(iid)
        cache[iid] = dict(rec) if rec else {}
    return {"items": [client_dict(r, request, inbound=cache.get(r["inbound_id"], {})) for r in rows],
            "scope": "all" if is_owner(request) else "own"}
@app.get("/api/inbounds/{iid}/clients")
async def api_inbound_clients(request: Request, iid: str):
    if not authed(request):
        return unauthorized()
    row = db.inbound_row(iid)
    if not row:
        return JSONResponse({"error": "Inbound not found"}, status_code=404)
    items = [c for c in db.clients_for_inbound(iid) if _client_guard(request, c)]
    return {"items": [client_dict(c, request, inbound=dict(row)) for c in items]}
@app.post("/api/clients")
async def api_create_client(request: Request):
    if not authed(request):
        return unauthorized()
    d = await request.json()
    iid = str(d.get("inbound_id") or "")
    row = db.inbound_row(iid)
    if not row:
        return JSONResponse({"error": "Inbound not found"}, status_code=404)
    existing = db.clients_for_inbound(iid)
    if row["client_limit"] and len(existing) >= int(row["client_limit"]):
        return JSONResponse({"error": "This inbound reached its client limit."}, status_code=409)
    if not api_extras.inbound_allowed(request, iid):
        return JSONResponse({"error": "Your account cannot use that inbound."}, status_code=403)
    name = str(d.get("name") or "Client").strip()[:80] or "Client"
    extras = _clean_extra_refs(d.get("extra_inbounds"), iid)
    cid = db.create_client(
        iid, name,
        created_by=current_user(request),
        extra_inbounds=extras,
        config_count=max(1, min(10, as_int(d.get("config_count"), 2, 1, 10))),
        limit_bytes=int(as_float(d.get("limit_value")) * 1024 ** 3) if "limit_value" in d else as_int(d.get("limit_bytes"), 0, 0),
        expires_at=expiry(d.get("expires_days", 0), d.get("expires_at", "")),
        ip_limit=as_int(d.get("ip_limit"), 0, 0, 5000),
        connection_limit=as_int(d.get("connection_limit"), 0, 0, 100000),
        speed_limit_mbps=as_float(d.get("speed_limit_mbps"), 0),
        note=str(d.get("note") or "")[:500],
        enabled=1 if as_bool(d.get("enabled", 1), True) else 0,
    )
    db.log(current_user(request), "client-create", name)
    return {"ok": True, "client": client_dict(db.client_row(cid), request, inbound=dict(row))}


@app.patch("/api/clients/{cid}")
async def api_update_client(request: Request, cid: str):
    if not authed(request):
        return unauthorized()
    row = db.client_row(cid)
    if not row:
        return JSONResponse({"error": "Client not found"}, status_code=404)
    if not _client_guard(request, row):
        return JSONResponse({"error": "That client belongs to another admin."}, status_code=403)
    d = await request.json()
    fields = {}
    if "extra_inbounds" in d:
        fields["extra_inbounds"] = _clean_extra_refs(d.get("extra_inbounds"), row["inbound_id"])
    if "config_count" in d:
        fields["config_count"] = max(1, min(10, as_int(d.get("config_count"), 2, 1, 10)))
    if "name" in d:
        fields["name"] = str(d["name"]).strip()[:80] or row["name"]
    if "limit_value" in d:
        fields["limit_bytes"] = int(as_float(d["limit_value"]) * 1024 ** 3)
    elif "limit_bytes" in d:
        fields["limit_bytes"] = as_int(d["limit_bytes"], int(row["limit_bytes"]), 0)
    if "expires_days" in d and not str(row["expires_at"] or ""):
        fields["expires_at"] = expiry(d["expires_days"])
    if "expires_at" in d:
        fields["expires_at"] = str(d["expires_at"] or "")[:40]
    for k, caster in (("ip_limit", lambda v: as_int(v, row["ip_limit"], 0, 5000)),
                      ("connection_limit", lambda v: as_int(v, row["connection_limit"], 0, 100000)),
                      ("speed_limit_mbps", lambda v: as_float(v, row["speed_limit_mbps"], 0))):
        if k in d:
            fields[k] = caster(d[k])
    if "note" in d:
        fields["note"] = str(d["note"])[:500]
    if "enabled" in d:
        fields["enabled"] = 1 if as_bool(d["enabled"], True) else 0
    db.update_client(cid, fields)
    return {"ok": True, "client": client_dict(db.client_row(cid), request)}


@app.delete("/api/clients/{cid}")
async def api_delete_client(request: Request, cid: str):
    if not authed(request):
        return unauthorized()
    row = db.client_row(cid)
    if not row:
        return JSONResponse({"error": "Client not found"}, status_code=404)
    if not _client_guard(request, row):
        return JSONResponse({"error": "That client belongs to another admin."}, status_code=403)
    ok = db.delete_client(cid)
    db.log(current_user(request), "client-delete", cid)
    return {"ok": ok}
@app.post("/api/clients/{cid}/regenerate")
async def api_regenerate_client(request: Request, cid: str):
    if not authed(request):
        return unauthorized()
    row = db.client_row(cid)
    if not row:
        return JSONResponse({"error": "Client not found"}, status_code=404)
    if not _client_guard(request, row):
        return JSONResponse({"error": "That client belongs to another admin."}, status_code=403)
    db.regenerate_client(cid)
    return {"ok": True, "client": client_dict(db.client_row(cid), request)}
@app.post("/api/clients/{cid}/reset-usage")
async def api_reset_usage(request: Request, cid: str):
    if not authed(request):
        return unauthorized()
    if not db.client_row(cid):
        return JSONResponse({"error": "Client not found"}, status_code=404)
    db.reset_usage(cid, True)
    return {"ok": True, "client": client_dict(db.client_row(cid), request)}


# ---------------------------------------------------------------- ping (latency)
async def _tcp_ping(host: str, port: int, timeout: float = 4.0) -> dict:
    """Server-side TCP connect latency - the same mechanism Vodiwalker uses (/api/network/tcp-ping)."""
    started = time.perf_counter()
    try:
        reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=timeout)
        ms = round((time.perf_counter() - started) * 1000, 1)
        try:
            writer.close()
        except Exception:  # noqa: BLE001
            pass
        return {"ok": True, "host": host, "port": port, "latency_ms": ms}
    except asyncio.TimeoutError:
        return {"ok": False, "host": host, "port": port, "latency_ms": None, "error": "timeout"}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "host": host, "port": port, "latency_ms": None,
                "error": f"{exc.__class__.__name__}: {str(exc)[:120]}"}


@app.post("/api/ping")
async def api_ping(request: Request):
    if not authed(request):
        return unauthorized()
    d = await request.json()
    host = str((d or {}).get("host") or "").strip()[:253]
    port = as_int((d or {}).get("port"), 443, 1, 65535)
    timeout = min(10.0, as_float((d or {}).get("timeout"), 4.0, 0.5))
    if not host:
        return JSONResponse({"error": "host is required"}, status_code=400)
    return await _tcp_ping(host, port, timeout)


@app.post("/api/inbounds/{iid}/ping")
async def api_inbound_ping(request: Request, iid: str):
    if not authed(request):
        return unauthorized()
    row = db.inbound_row(iid)
    if not row:
        return JSONResponse({"error": "Inbound not found"}, status_code=404)
    return await _tcp_ping(row["address"] or effective_host(request), as_int(row["port"], 443, 1, 65535))


@app.post("/api/clients/{cid}/ping")
async def api_client_ping(request: Request, cid: str):
    if not authed(request):
        return unauthorized()
    row = db.client_row(cid)
    if not row:
        return JSONResponse({"error": "Client not found"}, status_code=404)
    ib = db.inbound_row(row["inbound_id"])
    if not ib:
        return JSONResponse({"error": "Inbound not found"}, status_code=404)
    return await _tcp_ping(ib["address"] or effective_host(request), as_int(ib["port"], 443, 1, 65535))


# ---------------------------------------------------------------- ledger
@app.get("/api/ledger")
async def api_ledger(request: Request):
    """Durable per-client record: quota, consumed, remaining, expiry, last config generation."""
    if not authed(request):
        return unauthorized()
    if not api_extras.section_allowed(request, "logs"):
        return JSONResponse({"error": "Your account cannot open that section."}, status_code=403)
    return {"generated_at": db.now(), "items": db.ledger_rows()}


@app.get("/api/ledger.csv")
async def api_ledger_csv(request: Request):
    if not authed(request):
        return unauthorized()
    cols = ["id", "name", "inbound_name", "protocol", "network", "security", "state",
            "limit_human", "used_human", "remaining_human", "days_left", "expires_at",
            "sub_fetches", "last_config_at", "last_seen", "created", "uuid", "sub_token"]
    rows = db.ledger_rows()
    lines = [",".join(cols)]
    for r in rows:
        lines.append(",".join('"' + str(r.get(c, "")).replace('"', '""') + '"' for c in cols))
    return Response("\n".join(lines) + "\n", media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="dollax-ledger.csv"'})


# ---------------------------------------------------------------- settings
@app.get("/api/settings")
async def api_get_settings(request: Request):
    if not authed(request):
        return unauthorized()
    owner = is_owner(request)
    s = db.all_settings() if owner else {}
    s.pop("iran_ips_v1", None)
    return {"settings": s, "editable": owner, "username": current_user(request),
            "role": "owner" if owner else "admin", "version": APP_VERSION,
            "public_base_url": db.setting("public_base_url", "")}


@app.post("/api/settings")
async def api_set_settings(request: Request):
    if not authed(request):
        return unauthorized()
    if not is_owner(request):
        return JSONResponse({"error": "Only the owner can change panel settings."}, status_code=403)
    d = await request.json()
    allowed = ("panel_name", "public_base_url", "default_port", "xray_bridge_host", "xray_bridge_port",
               "reality_host", "reality_public_port", "tg_token", "tg_owner_id",
               "tg_trial_inbound", "tg_trial_gb", "tg_trial_days")
    for key in allowed:
        if key in d:
            db.set_setting(key, str(d[key])[:200].strip())
    if "tg_token" in d or "tg_owner_id" in d:
        try:                                    # save -> the bot (re)starts itself
            tg_bot.register(sys.modules[__name__])
            tg_bot.start()
            print("[dollax] TL robot restarted after a settings change", flush=True)
        except Exception as exc:  # noqa: BLE001
            print(f"[dollax] TL robot could not start: {exc.__class__.__name__}: {exc}", flush=True)
    db.log(current_user(request), "settings-update",
           ",".join(k for k in d if k in allowed),
           ip=client_ip(request))
    s = db.all_settings()
    s.pop("iran_ips_v1", None)
    return {"ok": True, "settings": s}


@app.get("/api/xray/status")
async def api_xray_status(request: Request):
    if not authed(request):
        return unauthorized()
    st = xray_core.status()
    st["hint"] = ("Xray-core is bundled in the Docker image (XRAY_MODE=auto): VMess, "
                  "Shadowsocks, Reality and UDP work through the same public port."
                  if st["running"] else
                  "Xray-core is not running. It ships with the image; set XRAY_MODE=on (or install "
                  "'xray' in PATH) so VMess/Shadowsocks/xhttp/gRPC inbounds work.")
    return st


@app.post("/api/xray/restart")
async def api_xray_restart(request: Request):
    if not authed(request):
        return unauthorized()
    if not is_owner(request):
        return JSONResponse({"error": "Owner only."}, status_code=403)
    res = _xray_restart()
    db.log(current_user(request), "xray-restart", str(res.get("reason") or "ok"), ip=client_ip(request))
    return {"ok": bool(res.get("ok")), "status": xray_core.status(),
            "reason": res.get("reason") or "", "inbounds": len(res.get("port_map") or {})}


@app.get("/api/xray/setup")
async def api_xray_setup(request: Request):
    if not authed(request):
        return unauthorized()
    inbounds = db.list_inbounds()
    clients_by = {i["id"]: db.clients_for_inbound(i["id"]) for i in inbounds}
    host = db.setting("xray_bridge_host") or effective_host(request)
    port = as_int(db.setting("xray_bridge_port", "8080"), 8080, 1, 65535)
    bundle = protocol.xray_bridge_config(host, inbounds, socks_port=port, clients_by_inbound=clients_by)
    bundle["inbounds"] = len(inbounds)
    return bundle


# ---------------------------------------------------------------- admins (owner only)
@app.get("/api/admins")
async def api_list_admins(request: Request):
    if not authed(request):
        return unauthorized()
    if not is_owner(request):
        return JSONResponse({"error": "Only the owner can manage admins."}, status_code=403)
    return {"items": [api_extras.admin_dict(r) for r in db.list_admins()]}


@app.post("/api/admins")
async def api_create_admin(request: Request):
    if not authed(request):
        return unauthorized()
    if not is_owner(request):
        return JSONResponse({"error": "Only the owner can manage admins."}, status_code=403)
    d = await request.json()
    username = str(d.get("username") or "").strip()[:60]
    password = str(d.get("password") or "")
    if len(username) < 3 or len(password) < 4:
        return JSONResponse({"error": "Username (3+) and password (4+) are required."}, status_code=400)
    if db.get_admin(username):
        return JSONResponse({"error": "That username already exists."}, status_code=409)
    db.create_admin(username, password, "owner" if d.get("role") == "owner" else "admin")
    api_extras.save_access(username, d)
    db.log(current_user(request), "admin-create", username, ip=client_ip(request))
    return {"ok": True, "items": [api_extras.admin_dict(r) for r in db.list_admins()]}


@app.patch("/api/admins/{username}")
async def api_update_admin(request: Request, username: str):
    if not authed(request):
        return unauthorized()
    if not is_owner(request):
        return JSONResponse({"error": "Only the owner can manage admins."}, status_code=403)
    row = db.get_admin(username)
    if not row:
        return JSONResponse({"error": "Admin not found"}, status_code=404)
    d = await request.json()
    role = d.get("role", row["role"])
    enabled = row["enabled"] if "enabled" not in d else (1 if as_bool(d.get("enabled"), True) else 0)
    demoting = row["role"] == "owner" and (role != "owner" or not enabled)
    if demoting and db.owner_count() <= 1:
        return JSONResponse({"error": "The last owner cannot be demoted or disabled."}, status_code=400)
    db.update_admin(username, role=role, enabled=bool(enabled), password=str(d.get("password") or "") or None)
    api_extras.save_access(username, d)
    db.log(current_user(request), "admin-update", username, ip=client_ip(request))
    return {"ok": True, "items": [api_extras.admin_dict(r) for r in db.list_admins()]}


@app.delete("/api/admins/{username}")
async def api_delete_admin(request: Request, username: str):
    if not authed(request):
        return unauthorized()
    if not is_owner(request):
        return JSONResponse({"error": "Only the owner can manage admins."}, status_code=403)
    row = db.get_admin(username)
    if not row:
        return JSONResponse({"error": "Admin not found"}, status_code=404)
    if row["role"] == "owner" and db.owner_count() <= 1:
        return JSONResponse({"error": "The last owner cannot be deleted."}, status_code=400)
    db.delete_admin(username)
    db.log(current_user(request), "admin-delete", username, ip=client_ip(request))
    return {"ok": True, "items": db.list_admins()}


# ---------------------------------------------------------------- nodes (panel to panel)
# A node is another Dollax panel in a different location. The connecting panel reads that
# panel's inbounds (with its shared node token) so subscriptions can carry several
# locations, and those inbounds show up here tagged with the node's location/flag.
def _valid_client_ref(ref: str) -> bool:
    """A client's extra inbound is either a local inbound id or a node reference."""
    ref = str(ref or "")
    if not ref or ref == "undefined" or ref == "null":
        return False
    if ref.startswith("node:"):
        parts = ref.split(":", 2)
        return len(parts) == 3 and bool(parts[1]) and bool(parts[2]) and parts[2] != "undefined"
    return bool(db.inbound_row(ref))


def _clean_extra_refs(refs, primary: str) -> list:
    out = []
    for ref in refs or []:
        ref = str(ref or "")
        if ref in out or ref == primary:
            continue
        if not _valid_client_ref(ref):
            continue
        out.append(ref)
        if len(out) >= 4:
            break
    return out


import sys as _sys

# Hosts, client sub-links and the node (panel-to-panel) endpoints live in
# api_extras so this file stays small enough to move around.
api_extras.register(app, _sys.modules[__name__])


# ---------------------------------------------------------------- subscriptions
def _inbound_as_client(inbound_row) -> dict:
    """The inbound's own credential, used when no client exists (or alongside them)."""
    ib = dict(inbound_row)
    return {
        "id": "", "inbound_id": ib.get("id", ""), "name": ib.get("name", "inbound"),
        "uuid": ib.get("uuid", ""), "enabled": ib.get("enabled", 1),
        "expires_at": ib.get("expires_at", ""), "limit_bytes": ib.get("limit_bytes", 0),
        "used_bytes": ib.get("used_bytes", 0), "clean_ips": [], "sub_token": ib.get("sub_token", ""),
        "ip_limit": ib.get("ip_limit", 0), "connection_limit": ib.get("connection_limit", 0),
        "speed_limit_mbps": 0, "note": "", "is_inbound": True,
    }


def _client_sub_entries(cl: dict):
    """Every location a client owns: its primary inbound + up to four more (max 5)."""
    cl = dict(cl)
    out = []
    for ref in _client_inbound_refs(cl):
        if ref.startswith("node:"):
            node, remote = api_extras.find_remote(ref)
            if not remote:
                continue
            ib = dict(remote)
            ib["clean_ips"] = []
            ib["_remote"] = True
            ib["_location_label"] = (node["location"] if node else "") or (node["name"] if node else "")
            csub = dict(cl)
            csub["uuid"] = remote.get("uuid") or cl.get("uuid")
            out.append((ib, csub))
            continue
        row = db.inbound_row(ref)
        if not row:
            continue
        ib = dict(row)
        ib["clean_ips"] = db.json_list(ib.get("clean_ips"))
        out.append((ib, dict(cl)))
    # sub-links: another client's configs ride along in this client's subscription
    for other in db.linked_clients(cl.get("id") or ""):
        if str(other.get("id")) == str(cl.get("id")):
            continue
        for ib2, sub in _client_sub_entries(other):
            if len(out) >= 25:
                break
            sub = dict(sub)
            sub["_linked_from"] = other.get("name") or "linked"   # shown in the config name
            out.append((ib2, sub))
    return out


def _sub_entries(token: str):
    client = db.client_by_token(token)
    if client:
        db.touch_client_config(client["id"])           # ledger: config handed out
        return _client_sub_entries(client), f"client:{client['name']}"
    inbound = db.inbound_by_token(token)
    if inbound:
        # the inbound itself is always a usable config - clients are optional extras
        entries = [(dict(inbound), _inbound_as_client(inbound))]
        clients = db.clients_for_inbound(inbound["id"])
        for c in clients:
            db.touch_client_config(c["id"])
        entries += [(dict(inbound), dict(c)) for c in clients]
        return entries, f"inbound:{inbound['name']}"
    return [], ""


def _page_info(token: str, entries) -> str:
    """The informational entry rendered on the page in its own block (client tokens only)."""
    cl = db.client_by_token(token)
    if not cl or not entries:
        return ""
    return api_extras.info_config(dict(cl), entries[0][0].get("name") or "")


def _sub_lines(entries, host, info_for=None):
    lines = []
    for ib, cl in entries:
        if protocol.clean_protocol(ib.get("protocol")) == "wireguard":
            continue        # .conf text cannot live in a URI subscription
        loc = ib.get("_location_label") or ""
        # the inbound's own credential is not a client: keep its name plain
        remark = "" if cl.get("is_inbound") else client_remark(cl)
        if loc and not cl.get("is_inbound"):
            remark = (remark + f" \u00b7 {loc}") if remark else loc

        lines += protocol.link_list(ib, cl["uuid"], host, cl.get("clean_ips") or ib.get("clean_ips"),
                                    remark=remark, count=int(cl.get("config_count") or 2))
    if info_for:
        # a separate, non-connectable entry that only shows the account summary
        first_ib = entries[0][0] if entries else {}
        lines.append(api_extras.info_config(info_for, first_ib.get("name") or ""))
    return lines


def _userinfo_header(entries):
    """Real counters: upload = client->target, download = target->client."""
    upload = sum(int(cl.get("up_bytes") or 0) for _, cl in entries)
    download = sum(int(cl.get("down_bytes") or 0) for _, cl in entries)
    limit = sum(int(cl.get("limit_bytes") or 0) for _, cl in entries)
    expires = [cl.get("expires_at") for _, cl in entries if cl.get("expires_at")]
    expire_ts = 0
    if expires:
        try:
            from datetime import datetime
            expire_ts = int(datetime.fromisoformat(min(expires)).timestamp())
        except Exception:
            expire_ts = 0
    return f"upload={upload}; download={download}; total={limit}; expire={expire_ts}"


def _entry_host(ib: dict, cl: dict, request: Request) -> str:
    """Which address a config should point at: client clean IP → inbound clean IP → address → host."""
    for candidate in (cl.get("clean_ips"), ib.get("clean_ips")):
        items = db.json_list(candidate) if candidate else []
        if items:
            return str(items[0]).split("#")[0].split(":")[0]
    return ib.get("address") or effective_host(request)


@app.get("/sub/{token}")
async def subscription(token: str, request: Request, target: str = "auto", raw: int = 0):
    entries, label = _sub_entries(token)
    if not entries:
        return PlainTextResponse("not found", status_code=404)
    for _, cl in entries:
        if not (cl.get("enabled") and not db.is_expired(cl.get("expires_at"))):
            return PlainTextResponse("subscription disabled", status_code=403)
    host = effective_host(request)
    ua = (request.headers.get("user-agent") or "").lower()
    wants_browser = "mozilla" in ua and not any(k in ua for k in ("v2ray", "clash", "sing", "v2rayng", "nekobox", "shadowrocket"))
    if target == "auto" and wants_browser:
        return RedirectResponse(f"/info/{token}", status_code=307)
    tgt = target.lower()
    entries_named = [{"inbound": ib, "client": cl, "host": _entry_host(ib, cl, request),
                      "name": f"{ib.get('name')}-{cl.get('name')}"} for ib, cl in entries]
    if tgt in ("clash", "clash-meta", "mihomo"):
        return PlainTextResponse(protocol.clash_config(entries_named, db.setting("panel_name", "Dollax")))
    if tgt in ("singbox", "sing-box"):
        return PlainTextResponse(protocol.singbox_config(entries_named),
                                 media_type="application/json")
    lines = _sub_lines(entries, host, info_for=api_extras.info_target(token))
    if raw:                       # plain-text list for clients that prefer it
        return PlainTextResponse("\n".join(lines) + "\n", media_type="text/plain")
    body = protocol.subscription_body(lines)
    headers = {
        "Subscription-Userinfo": _userinfo_header(entries),
        "Profile-Update-Interval": "12",
        "Profile-Title": db.setting("panel_name", "Dollax Panel"),
    }
    return PlainTextResponse(body, headers=headers)


@app.get("/api/subscription/{token}")
async def subscription_stats(token: str, request: Request):
    entries, label = _sub_entries(token)
    if not entries:
        return JSONResponse({"error": "not found"}, status_code=404)
    host = effective_host(request)
    return {
        "label": label,
        "userinfo": _userinfo_header(entries),
        "links": api_extras.split_info(_sub_lines(entries, host, info_for=api_extras.info_target(token)))[0],
        "info_link": api_extras.split_info(_sub_lines(entries, host, info_for=api_extras.info_target(token)))[1],
        "counts": {"configs": len(_sub_lines(entries, host)), "locations": len(entries)},
    }


def _qr_svg_markup(text: str) -> str:
    """Inline SVG QR (white tile), or a placeholder when the lib is missing."""
    if not qrcode or not _qr_svg:
        return '<div style="display:grid;place-items:center;width:100%;height:100%;color:#333;font-size:10px">QR</div>'
    import io
    img = qrcode.make(text, image_factory=_qr_svg.SvgPathImage)
    buf = io.BytesIO()
    img.save(buf)
    svg = buf.getvalue().decode("utf-8", "ignore")
    # white tile so scanners lock on in dark themes
    return svg.replace("<svg ", "<svg style=\"background:#fff;width:100%;height:100%\" ", 1)


@app.get("/info/{token}", response_class=HTMLResponse)
async def subscription_info(token: str, request: Request, template: str = ""):
    """The graphical subscription page. `template` picks the design; each admin's choice
    applies to the clients they created."""
    entries, label = _sub_entries(token)
    if not entries:
        return HTMLResponse("<h1 style='font-family:sans-serif'>Not found</h1>", status_code=404)

    host = effective_host(request)
    prefs = db.get_prefs(current_user(request)) if authed(request) else {}
    if not prefs:
        owner = db.get_admin((os.getenv("ADMIN_USERNAME") or "dollax26").strip() or "dollax26")
        prefs = db.get_prefs(owner["username"]) if owner else {}

    # an inbound token shows every client; a client token shows just that client
    inbound = entries[0][0]
    used = sum(int(cl.get("used_bytes") or 0) for _, cl in entries)
    up_all = sum(int(cl.get("up_bytes") or 0) for _, cl in entries)
    down_all = sum(int(cl.get("down_bytes") or 0) for _, cl in entries)
    limit = sum(int(cl.get("limit_bytes") or 0) for _, cl in entries)
    pct = min(100, round(used / limit * 100)) if limit else 0
    expires_vals = [cl.get("expires_at") for _, cl in entries if cl.get("expires_at")]

    clients_view = []
    for ib, cl in entries:
        c_used = int(cl.get("used_bytes") or 0)
        c_up = int(cl.get("up_bytes") or 0)
        c_down = int(cl.get("down_bytes") or 0)
        c_limit = int(cl.get("limit_bytes") or 0)
        links = protocol.link_list(ib, cl["uuid"], host,
                                   cl.get("clean_ips") or ib.get("clean_ips"),
                                   remark=client_remark(cl) if not cl.get("is_inbound") else "")
        expired = db.is_expired(cl.get("expires_at"))
        if not cl.get("enabled"):
            status, status_class = "disabled", ""
        elif expired:
            status, status_class = "expired", "bad"
        elif c_limit and c_used >= c_limit:
            status, status_class = "quota", "warn"
        else:
            status, status_class = "active", "ok"
        clients_view.append({
            "name": cl.get("name"), "status": status, "status_class": status_class,
            "pct": min(100, round(c_used / c_limit * 100)) if c_limit else 0,
            "used": protocol.fmt_bytes(c_used),
            "up": protocol.fmt_bytes(c_up),
            "down": protocol.fmt_bytes(c_down),
            "remaining": protocol.fmt_bytes(max(0, c_limit - c_used)) if c_limit else "∞",
            "expires": (str(cl.get("expires_at"))[:10] if cl.get("expires_at") else "∞"),
            "sub_url": f"{base_url(request)}/sub/{cl.get('sub_token')}",
            "links": [{"link": l} for l in links],
        })

    sub_url = f"{base_url(request)}/sub/{token}"
    badges = [str(inbound.get("protocol") or "vless").upper(),
              str(inbound.get("network") or "ws").upper(),
              str(inbound.get("security") or "tls").upper()]
    data = {
        "panel_name": db.setting("panel_name", "Dollax Panel"),
        "title": inbound.get("name") or "Subscription",
        "badges": badges,
        "endpoint": f"{inbound.get('address') or host}:{inbound.get('port') or 443} · path {inbound.get('path')}",
        "protocol": str(inbound.get("protocol") or "vless"),
        "client_count": len(clients_view),
        "config_count": sum(max(1, int(ib.get("config_count") or 1)) for ib, _ in entries),
        "pct": pct,
        "up": protocol.fmt_bytes(up_all),
        "down": protocol.fmt_bytes(down_all),
        "sub_url": sub_url,
        "sub_clash": sub_url + "?target=clash",
        "sub_singbox": sub_url + "?target=singbox",
        "sub_base64": sub_url,
        "qr_svg": _qr_svg_markup(sub_url),
        "clients": clients_view,
        "info_link": "",
        "links_all": api_extras.links_all(entries, host, request),
        "language": prefs.get("language") or "en",
        "theme": prefs.get("theme") or "dark-green",
        "ui_style": prefs.get("style") or "solid",
    }
    tpl = (template or "").strip().lower()
    if tpl not in pages.TEMPLATE_IDS:
        creator = ""
        for _ib, _cl in entries:
            if str(_cl.get("created_by") or ""):
                creator = str(_cl["created_by"])
                break
        tpl = ""
        if creator:
            tpl = str((db.get_prefs(creator) or {}).get("sub_template") or "")
        if tpl not in pages.TEMPLATE_IDS:
            tpl = str(prefs.get("sub_template") or "")
        if tpl not in pages.TEMPLATE_IDS:
            tpl = "aurora"
    data["template"] = tpl
    data["sub_url_tpl"] = f"{sub_url}?template={tpl}"
    db.log("", "subpage-view", f"{label or token} [{tpl}]")
    return HTMLResponse(subscription_page(data, template=tpl))


# ---------------------------------------------------------------- xray-core
# The panel is the single public port; Xray-core (bundled in the image) does the protocol
# work for VMess / Shadowsocks / Reality / UDP and the extra transports (xhttp, gRPC,
# HTTPUpgrade). Bytes still flow through the panel so quotas and per-client accounting work.
def _visible_clients(request: Request) -> list:
    """Clients an admin may see: their own on their inbounds, everything for the owner."""
    rows = db.list_clients()
    if is_owner(request):
        return rows
    me = current_user(request)
    ibs, _ = api_extras.admin_scope(request)
    out = [r for r in rows if str(r.get("created_by") or "") == me]
    if ibs is not None:
        out = [r for r in out if str(r.get("inbound_id")) in ibs]
    return out


def _client_guard(request: Request, row) -> bool:
    """True when this admin may touch that client."""
    if is_owner(request):
        return True
    return str(row["created_by"] or "") == current_user(request)


def _xray_inbounds():
    return [dict(r) for r in db.list_inbounds()]


def _xray_clients(inbounds):
    out = {}
    for ib in inbounds:
        try:
            out[ib["id"]] = [dict(c) for c in db.clients_for_inbound(ib["id"])]
        except Exception:  # noqa: BLE001
            out[ib["id"]] = []
    return out


def _xray_fingerprint():
    """Cheap digest of everything that changes the Xray config."""
    try:
        inbounds = _xray_inbounds()
    except Exception:  # noqa: BLE001
        return ""
    parts = []
    keys = ("id", "uuid", "protocol", "network", "path", "port", "enabled", "security",
            "host_header", "sni", "ss_method", "ss_password", "grpc_service_name")
    for ib in inbounds:
        parts.append("|".join(str(ib.get(k) or "") for k in keys))
        for c in _xray_clients([ib]).get(ib["id"], []):
            parts.append("   " + "|".join(str(c.get(k) or "") for k in ("uuid", "enabled", "expires_at")))
    try:
        parts.append("|".join(str(o.get(k) or "") for o in db.list_outbounds() for k in ("tag", "protocol", "enabled")))
        parts.append("|".join(str(r.get(k) or "") for r in db.list_routes() for k in ("domain", "ip", "outbound_tag", "enabled")))
    except Exception:  # noqa: BLE001
        pass
    return hashlib.sha256("\n".join(parts).encode()).hexdigest()


def _xray_restart():
    """Rebuild + relaunch the core. Safe when the binary is missing."""
    try:
        inbounds = _xray_inbounds()
        return xray_core.start(inbounds, _xray_clients(inbounds))
    except Exception as exc:  # noqa: BLE001
        print(f"[dollax] xray restart failed: {exc}", flush=True)
        return {"ok": False, "running": False, "reason": f"{exc.__class__.__name__}: {exc}"}


async def _xray_watch():
    """Config watcher: relaunch the core whenever inbounds/clients change."""
    last = ""
    while True:
        try:
            if xray_core.enabled():
                fp = _xray_fingerprint()
                if fp and fp != last:
                    last = fp
                    res = _xray_restart()
                    if res.get("ok"):
                        print(f"[dollax] xray-core started: {res.get('port_map') and len(res['port_map'])} "
                              f"inbound(s), base port {xray_core.base_port()}", flush=True)
                    elif res.get("reason"):
                        print(f"[dollax] xray-core not running: {res['reason']}", flush=True)
        except Exception:  # noqa: BLE001
            pass
        await asyncio.sleep(12)


# ---------------------------------------------------------------- relay (WebSocket)
@app.websocket("/{full_path:path}")
async def ws_entry(ws: WebSocket, full_path: str):
    path = "/" + full_path
    ib = db.inbound_by_path(path)
    if not ib:
        await ws.close(code=1008)
        return
    inbound = dict(ib)
    if protocol.clean_protocol(inbound.get("protocol")) not in protocol.NATIVE_PROTOCOLS:
        # Not a WebSocket protocol the built-in relay speaks (VMess/SS/xhttp/gRPC/...):
        # hand the connection to the bundled Xray-core, still counting bytes here.
        xport = xray_core.local_port(inbound["id"])
        if not (xport and xray_core.is_running()):
            await ws.close(code=1003)
            return
        if db.is_expired(inbound.get("expires_at")):
            await ws.close(code=1008)
            return
        if inbound.get("limit_bytes") and int(inbound.get("used_bytes") or 0) >= int(inbound["limit_bytes"]):
            await ws.close(code=1008)
            return
        await ws.accept()
        reported = {"up": 0, "down": 0}

        def on_bridge_bytes(up_total, down_total, final=False):
            up_delta = int(up_total) - reported["up"]
            down_delta = int(down_total) - reported["down"]
            if up_delta <= 0 and down_delta <= 0:
                return
            reported["up"] = int(up_total)
            reported["down"] = int(down_total)
            db.add_inbound_usage(inbound["id"], up_delta, down_delta)

        try:
            await relay.bridge(ws, f"ws://127.0.0.1:{xport}{path}", on_bytes=on_bridge_bytes)
        except Exception:  # noqa: BLE001
            pass
        finally:
            try:
                await ws.close(code=1000)
            except Exception:  # noqa: BLE001
                pass
        return
    if db.is_expired(inbound.get("expires_at")):
        await ws.close(code=1008)
        return
    if inbound.get("limit_bytes") and int(inbound.get("used_bytes") or 0) >= int(inbound["limit_bytes"]):
        await ws.close(code=1008)
        return

    clients = db.clients_for_inbound(inbound["id"])

    # peek the first frame to identify the credential
    await ws.accept()
    try:
        first = await ws.receive()
    except Exception:
        await ws.close(code=1002)
        return
    data = first.get("bytes") if isinstance(first, dict) else None
    if not data:
        await ws.close(code=1002)
        return

    proto = protocol.clean_protocol(inbound["protocol"])
    self_client = _inbound_as_client(inbound)
    client = None
    if proto == "vless":
        parsed = protocol.parse_vless_header(data)
        if parsed:
            client = next((c for c in clients if c["uuid"] == parsed["uuid"]), None)
            if not client and parsed["uuid"] == inbound.get("uuid"):
                client = self_client          # the inbound's own credential
    else:  # trojan: the per-client secret is its uuid
        head = bytes(data[:56]).lower()
        candidates = {hashlib.sha224(str(c["uuid"]).encode()).hexdigest().encode(): c for c in clients}
        candidates[hashlib.sha224(str(inbound.get("uuid") or "").encode()).hexdigest().encode()] = self_client
        client = candidates.get(head)

    if not client:
        await ws.close(code=1008)
        return
    if not client["enabled"] or db.is_expired(client.get("expires_at")):
        await ws.close(code=1008)
        return
    if client.get("limit_bytes") and int(client.get("used_bytes") or 0) >= int(client["limit_bytes"]):
        await ws.close(code=1008)
        return

    peer = client_ip_ws(ws)
    admitted, why = _admit(client, peer)
    if not admitted:
        db.log(client.get("name") or "client", "reject", why, ip=peer)
        await ws.close(code=1008)
        return

    async def replay():
        """Give relay.handle() the frame we already consumed, once."""
        if not replayed["v"]:
            replayed["v"] = True
            return first
        return await original_receive()

    original_receive = ws.receive
    replayed = {"v": False}
    reported = {"up": 0, "down": 0}
    ws.receive = replay  # type: ignore[assignment]

    def on_bytes(up_total, down_total, final=False):
        up_delta = int(up_total) - reported["up"]
        down_delta = int(down_total) - reported["down"]
        if up_delta <= 0 and down_delta <= 0:
            return
        reported["up"] = int(up_total)
        reported["down"] = int(down_total)
        if client.get("id"):
            db.add_client_usage(client["id"], up_delta, down_delta)
        db.add_inbound_usage(inbound["id"], up_delta, down_delta)

    try:
        await relay.handle(ws, inbound, dict(client), on_bytes=on_bytes, already_accepted=True)
    except Exception:
        try:
            await ws.close(code=1011)
        except Exception:
            pass
    finally:
        ws.receive = original_receive  # type: ignore[assignment]
        _release(client)


# ---------------------------------------------------------------- entry point
# `python main.py` must work (Railway / Nixpacks / manual runs) - not only
# `uvicorn main:app`. Reads $PORT like every PaaS expects.
def _port_candidates():
    """The port to listen on. $PORT is what every PaaS injects, but a malformed or missing
    value must never crash the container: fall back to the usual suspects, in order."""
    raw = str(os.getenv("PORT") or "").strip()
    out = []
    try:
        value = int(raw)
        if 1 <= value <= 65535:
            out.append(value)
    except Exception:  # noqa: BLE001 - empty / non-numeric / whitespace
        if raw:
            print(f"[dollax] WARNING: PORT={raw!r} is not a usable port number; falling back", flush=True)
    for cand in (8080, 8000, 3000, 5000, 10000):
        if cand not in out:
            out.append(cand)
    return out


if __name__ == "__main__":
    import traceback
    import uvicorn

    print(f"[dollax] Dollax Panel {APP_VERSION} booting; PORT env = {os.getenv('PORT')!r}", flush=True)
    print(f"[dollax] data db: {db.DB_PATH}", flush=True)
    print(f"[dollax] SECRET_KEY from env: {'yes' if os.getenv('SECRET_KEY') else 'no (a random one is generated per boot)'}",
          flush=True)
    print(f"[dollax] owner seed: {os.getenv('ADMIN_USERNAME') or 'dollax26'} / "
          f"{'env password' if os.getenv('ADMIN_PASSWORD') else 'default dollax26'}", flush=True)

    def _serve(port, label):
        uvicorn.run(
            "main:app",
            host="0.0.0.0",
            port=port,
            proxy_headers=True,
            forwarded_allow_ips="*",
            log_level=(os.getenv("LOG_LEVEL") or "info"),
        )

    # Safety net: some platform setups route the public domain to a target port that does not
    # match the PORT they inject. Serving on both means the proxy always finds us. Two uvicorn
    # processes share the same SQLite DB (WAL) and the same generated config.
    # Optional second listener. Off by default: the platform injects the port it routes to,
    # and a second copy of the app would also start a second Telegram poller and Xray watcher.
    # Set DOLLAX_EXTRA_PORT=1 only if your proxy targets a fixed port other than $PORT.
    _ports = _port_candidates()
    _primary = _ports[0]
    _extra = 8080 if (os.getenv("DOLLAX_EXTRA_PORT") == "1" and _primary != 8080) else None
    if _extra:
        import threading
        def _extra_server():
            try:
                print(f"[dollax] also listening on 0.0.0.0:{_extra} (safety net for target-port mismatch)",
                      flush=True)
                _serve(_extra, "extra")
            except BaseException as exc:  # noqa: BLE001
                print(f"[dollax] extra listener on {_extra} stopped: {exc.__class__.__name__}", flush=True)
        threading.Thread(target=_extra_server, daemon=True).start()

    last_error = None
    for _port in _ports:
        try:
            print(f"[dollax] starting on 0.0.0.0:{_port}", flush=True)
            _serve(_port, "primary")
            break                      # clean shutdown
        except SystemExit:
            break
        except BaseException as exc:   # noqa: BLE001 - try the next port instead of dying
            last_error = exc
            print(f"[dollax] could not serve on port {_port}: {exc.__class__.__name__}: {exc}", flush=True)
            traceback.print_exc()
            continue
    if last_error is not None:
        print("[dollax] FATAL: no usable port - see the tracebacks above.", flush=True)
