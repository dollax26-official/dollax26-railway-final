"""TL robot - a Telegram control bot for the panel.

Long polling against the Bot API with the httpx client the panel already ships, so there is
nothing extra to install. The owner id + bot token are stored in the panel settings; saving
them starts the bot automatically (and it is started on boot when they are present).

The bot is a *control* surface: it drives the same panel code the web UI uses - clients,
inbounds, hosts, nodes and the activity log - so there is one implementation of every rule.

Commands
    /help                      this list
    /status                    panel + core state
    /stats                     traffic + counts
    /inbounds                  list inbounds
    /newinbound NAME ADDR PORT [PROTO] [NET] [SEC]
    /hosts                     list the host pool
    /addhost ADDRESS
    /clients [INBOUND]         list clients
    /newclient INBOUND NAME [GB] [DAYS]
    /delclient NAME
    /link NAME                 the client's subscription + first config
    /logs [N]                  recent activity
    /nodes                     connected nodes and their status
"""
import asyncio
import os
import time

import httpx

DTOKEN = ""      # filled from settings on (re)start
DOWNER = ""
STATE = {
    "running": False,
    "task": None,
    "username": "",
    "last_error": "",
    "last_poll": 0.0,
    "handled": 0,
    "started_at": 0.0,
    "offset": 0,
}

_M: object = None          # the main module (panel helpers + db), set by register()


def register(main_module) -> None:
    global _M
    _M = main_module


def api_url(token: str, method: str) -> str:
    return f"https://api.telegram.org/bot{token}/{method}"


async def tg_call(token: str, method: str, request_timeout: float = 30.0, **params):
    """One Bot API call. Returns (ok, result_or_error_dict).

    `request_timeout` is the HTTP timeout; any other keyword (including Telegram's own
    `timeout` for long polling) is passed straight to the Bot API method.
    """
    try:
        async with httpx.AsyncClient(timeout=request_timeout) as c:
            r = await c.post(api_url(token, method), json=params)
        data = r.json()
        if data.get("ok"):
            return True, data.get("result")
        return False, {"error": str(data.get("description") or r.status_code)}
    except Exception as exc:  # noqa: BLE001
        return False, {"error": f"{exc.__class__.__name__}: {str(exc)[:120]}"}


async def send(token: str, chat_id, text: str, markdown: bool = False):
    payload = {"chat_id": chat_id, "text": text[:4000], "disable_web_page_preview": True}
    if markdown:
        payload["parse_mode"] = "Markdown"
    return await tg_call(token, "sendMessage", **payload)


# ---------------------------------------------------------------- helpers
def _fmt_bytes(n) -> str:
    try:
        return _M.protocol.fmt_bytes(int(n or 0))
    except Exception:  # noqa: BLE001
        return "0 B"


def _clients() -> list:
    return _M.db.list_clients()


def _inbounds() -> list:
    return [dict(r) for r in _M.db.list_inbounds()]


def find_inbound(key: str):
    key = str(key or "").strip().lower()
    for ib in _inbounds():
        if str(ib["id"]).lower() == key or str(ib.get("name") or "").lower() == key:
            return ib
    return None


def find_client(key: str):
    key = str(key or "").strip().lower()
    for c in _clients():
        if str(c["id"]).lower() == key or str(c.get("name") or "").lower() == key:
            return c
    return None


def help_text() -> str:
    return ("🤖 *TL robot* - panel control\n\n"
            "`/status` - panel + core state\n"
            "`/stats` - traffic and counts\n"
            "`/inbounds` - list inbounds\n"
            "`/newinbound NAME ADDRESS PORT [PROTO] [NET] [SEC]`\n"
            "`/hosts` - host pool\n"
            "`/addhost ADDRESS` - add a host\n"
            "`/clients [INBOUND]` - list clients\n"
            "`/newclient INBOUND NAME [GB] [DAYS]`\n"
            "`/delclient NAME`\n"
            "`/link NAME` - subscription + first config\n"
            "`/logs [N]` - recent activity (default 10)\n"
            "`/nodes` - connected nodes")


def _status_text() -> str:
    inbounds, clients = _inbounds(), _clients()
    core = _M.xray_core.status()
    used = sum(int(c.get("used_bytes") or 0) for c in clients)
    up = sum(int(c.get("up_bytes") or 0) for c in clients)
    down = sum(int(c.get("down_bytes") or 0) for c in clients)
    return (f"✅ *{_M.db.setting('panel_name', 'Dollax Panel')}* v{_M.APP_VERSION}\n"
            f"inbounds: *{len(inbounds)}* · clients: *{len(clients)}*\n"
            f"core: *{'xray running' if core.get('running') else 'built-in relay'}*\n"
            f"traffic: {_fmt_bytes(used)} (↑{_fmt_bytes(up)} / ↓{_fmt_bytes(down)})\n"
            f"nodes: *{len(_M.db.list_nodes())}* · hosts: *{len(_M.db.list_hosts())}*")


def _new_client(args: list) -> str:
    if len(args) < 2:
        return "usage: `/newclient INBOUND NAME [GB] [DAYS]`"
    ib = find_inbound(args[0])
    if not ib:
        return f"⛔ no inbound named `{args[0]}`. /inbounds lists them."
    name = args[1]
    limit = float(args[2]) if len(args) > 2 and str(args[2]).replace(".", "", 1).isdigit() else 0
    days = int(args[3]) if len(args) > 3 and str(args[3]).isdigit() else 0
    cid = _M.db.create_client(
        ib["id"], name,
        limit_bytes=int(limit * 1024 ** 3),
        expires_at=_M.expiry(days) if days else "",
        ip_limit=0, connection_limit=0, speed_limit_mbps=0, note="created via TL robot",
        enabled=1, created_by=DOWNER or "telegram", extra_inbounds=[], config_count=2,
    )
    row = _M.db.client_row(cid)
    cl = _M.client_dict(row, _FakeRequest())
    link = (cl.get("links") or [""])[0]
    return (f"✅ client *{name}* created on *{ib['name']}*\n"
            f"quota: {limit if limit else '∞'} GB · days: {days if days else '∞'}\n"
            f"configs: {len(cl.get('links') or [])}\n\n`{link}`")


def _new_inbound(args: list) -> str:
    if len(args) < 3:
        return "usage: `/newinbound NAME ADDRESS PORT [PROTO] [NET] [SEC]`"
    name, addr, port = args[0], args[1], args[2]
    if not str(port).isdigit():
        return "⛔ PORT must be a number"
    payload = {"name": name, "address": addr, "port": int(port),
               "protocol": args[3] if len(args) > 3 else "vless",
               "network": args[4] if len(args) > 4 else "ws",
               "security": args[5] if len(args) > 5 else "tls",
               "config_count": 2, "enabled": True}
    fields, err = _M._inbound_payload(payload)
    if err:
        return "⛔ " + err
    try:
        iid = _M.db.create_inbound(fields)
    except Exception as exc:  # noqa: BLE001
        return f"⛔ could not create: {exc.__class__.__name__}"
    ib = _M.inbound_dict(_M.db.inbound_row(iid))
    return (f"✅ inbound *{ib['name']}* created\n"
            f"{ib['protocol'].upper()} · {ib['network']} · {ib['security']} · "
            f"{ib['address'] or '(panel domain)'}:{ib['port']}\n"
            f"path `{ib['path']}` · configs {len(ib.get('links') or [])}")


class _FakeRequest:
    """Minimal request stand-in so link building works outside a HTTP call."""

    class _U:
        scheme = "https"
        netloc = ""

    def __init__(self):
        host = str(_M.db.setting("public_base_url") or "").replace("https://", "").replace("http://", "").split("/")[0]
        self.headers = {"host": host}
        self.url = self._U()
        self.url.netloc = host
        self.base_url = "https://" + host + "/" if host else "http://127.0.0.1/"


def _link(args: list) -> str:
    if not args:
        return "usage: `/link CLIENT`"
    c = find_client(" ".join(args))
    if not c:
        return f"⛔ no client named `{' '.join(args)}`"
    cl = _M.client_dict(c, _FakeRequest())
    sub = _M.base_url(_FakeRequest()) + "/sub/" + str(c.get("sub_token") or "")
    first = (cl.get("links") or [""])[0]
    return (f"🔗 *{c['name']}*\nquota {_fmt_bytes(c.get('limit_bytes'))} · "
            f"used {_fmt_bytes(c.get('used_bytes'))}\n\nsubscription:\n`{sub}`\n\nfirst config:\n`{first}`")


async def handle_command(text: str, chat_id) -> str:
    """Turn one message into a reply (the whole bot logic lives here)."""
    raw = str(text or "").strip()
    if not raw:
        return ""
    parts = raw.split()
    cmd = parts[0].lower().lstrip("/").split("@")[0]
    args = parts[1:]

    # ---- authorization: only the configured owner id may drive the panel
    if str(DOWNER) and str(chat_id) != str(DOWNER):
        return "⛔ This bot is private."

    if cmd in ("start", "help"):
        return help_text()
    if cmd == "status":
        return _status_text()
    if cmd == "stats":
        inbounds, clients = _inbounds(), _clients()
        active = sum(1 for c in clients if c.get("enabled") and not _M.db.is_expired(c.get("expires_at")))
        return (f"📊 *stats*\nclients: {len(clients)} (active {active})\n"
                f"inbounds: {len(inbounds)}\n"
                f"traffic: {_fmt_bytes(sum(int(c.get('used_bytes') or 0) for c in clients))}\n"
                f"subscriptions fetched: {sum(int(c.get('sub_fetches') or 0) for c in clients)}")
    if cmd == "inbounds":
        ibs = _inbounds()
        if not ibs:
            return "no inbounds yet - `/newinbound NAME ADDRESS PORT`"
        return "📶 *inbounds*\n" + "\n".join(
            f"• *{i['name']}* - {i['protocol']}/{i['network']}/{i['security']} · "
            f"{i['address'] or '(panel domain)'}:{i['port']} · {i.get('client_count', 0)} clients"
            for i in ibs[:25])
    if cmd == "newinbound":
        return _new_inbound(args)
    if cmd == "hosts":
        hs = _M.db.list_hosts()
        if not hs:
            return "host pool is empty - `/addhost 1.2.3.4`"
        return "🗂 *hosts*\n" + "\n".join(f"• `{h['address']}`{' · ' + h['label'] if h.get('label') else ''}"
                                          for h in hs[:25])
    if cmd == "addhost":
        if not args:
            return "usage: `/addhost ADDRESS`"
        _M.db.add_host(args[0], created_by=DOWNER or "telegram")
        return f"✅ host `{args[0]}` added ({len(_M.db.list_hosts())} total)"
    if cmd == "clients":
        target = find_inbound(args[0]) if args else None
        cs = [dict(c) for c in _clients() if not target or c["inbound_id"] == target["id"]]
        if not cs:
            return "no clients yet - `/newclient INBOUND NAME [GB] [DAYS]`"
        return "👥 *clients*\n" + "\n".join(
            f"• *{c['name']}* - {_fmt_bytes(c.get('used_bytes'))}"
            f"{'/' + _fmt_bytes(c.get('limit_bytes')) if c.get('limit_bytes') else ''}"
            f"{' · ' + str(_M.db.days_left(c.get('expires_at'))) + 'd left' if c.get('expires_at') else ''}"
            for c in cs[:25])
    if cmd == "newclient":
        return _new_client(args)
    if cmd == "delclient":
        if not args:
            return "usage: `/delclient NAME`"
        c = find_client(" ".join(args))
        if not c:
            return "⛔ client not found"
        _M.db.delete_client(c["id"])
        return f"🗑 client *{c['name']}* deleted"
    if cmd == "link":
        return _link(args)
    if cmd == "logs":
        n = int(args[0]) if args and str(args[0]).isdigit() else 10
        rows = _M.db.activity(min(40, max(1, n)))
        if not rows:
            return "no activity yet"
        out = []
        for r in rows:
            who = r.get("username") or "system"
            out.append(f"• `{str(r.get('created') or '')[5:19]}` {who} {r.get('action')} {r.get('detail') or ''}".rstrip())
        return "🧾 *recent activity*\n" + "\n".join(out)
    if cmd == "nodes":
        nodes = _M.db.list_nodes()
        if not nodes:
            return "no nodes connected"
        return "🛰 *nodes*\n" + "\n".join(
            f"• *{n['name']}* ({n['location'] or '-'}) - {n['status'] or 'never synced'} · "
            f"{len(_M.db.json_raw(n.get('snapshot'), []))} inbounds"
            for n in nodes[:15])
    return "🤔 unknown command. /help"


# ---------------------------------------------------------------- lifecycle
async def _poll_once(token: str) -> bool:
    ok, res = await tg_call(token, "getUpdates", request_timeout=35.0,
                            offset=STATE["offset"] + 1, timeout=25, allowed_updates=["message"])
    if not ok:
        STATE["last_error"] = str((res or {}).get("error") or "poll failed")[:160]
        return False
    STATE["last_error"] = ""
    STATE["last_poll"] = time.time()
    for upd in res or []:
        STATE["offset"] = max(STATE["offset"], int(upd.get("update_id") or 0))
        msg = upd.get("message") or {}
        text = msg.get("text") or ""
        chat = (msg.get("chat") or {}).get("id")
        if not text or chat is None:
            continue
        try:
            reply = await handle_command(text, chat)
            if reply:
                await send(token, chat, reply, markdown=True)
                STATE["handled"] += 1
        except Exception as exc:  # noqa: BLE001
            STATE["last_error"] = f"handler: {exc.__class__.__name__}: {exc}"[:160]
    return True


async def _loop(token: str):
    STATE["running"] = True
    ok, me = await tg_call(token, "getMe")
    if ok and isinstance(me, dict):
        STATE["username"] = me.get("username") or ""
    else:
        STATE["last_error"] = str((me or {}).get("error") or "getMe failed")[:160]
    while STATE["running"]:
        try:
            alive = await _poll_once(token)
            if not alive:
                await asyncio.sleep(5)
        except asyncio.CancelledError:
            break
        except Exception as exc:  # noqa: BLE001
            STATE["last_error"] = f"loop: {exc.__class__.__name__}: {exc}"[:160]
            await asyncio.sleep(5)
    STATE["running"] = False


def tokens() -> tuple:
    """(token, owner id) from the panel settings."""
    try:
        return (str(_M.db.setting("tg_token") or "").strip(),
                str(_M.db.setting("tg_owner_id") or "").strip())
    except Exception:  # noqa: BLE001
        return "", ""


def start() -> bool:
    """Start (or restart) polling when a token + owner id are configured."""
    global DTOKEN, DOWNER
    if _M is None:
        return False
    token, owner = tokens()
    DTOKEN, DOWNER = token, owner
    stop()
    STATE["last_error"] = ""
    STATE["handled"] = 0
    STATE["offset"] = 0
    STATE["started_at"] = time.time()
    if not token or not owner:
        STATE["running"] = False
        if token and not owner:
            STATE["last_error"] = "owner number id is missing"
        return False
    try:
        STATE["task"] = asyncio.get_event_loop().create_task(_loop(token))
    except RuntimeError:
        loop = asyncio.new_event_loop()
        STATE["task"] = loop.create_task(_loop(token))
    return True


def stop() -> None:
    STATE["running"] = False
    task = STATE.get("task")
    if task:
        try:
            task.cancel()
        except Exception:  # noqa: BLE001
            pass
    STATE["task"] = None


def status() -> dict:
    token, owner = tokens()
    return {
        "configured": bool(token and owner),
        "token_set": bool(token),
        "owner": owner,
        "running": bool(STATE["running"]),
        "username": STATE["username"],
        "last_error": STATE["last_error"],
        "handled": STATE["handled"],
        "last_poll": STATE["last_poll"],
        "started_at": STATE["started_at"],
    }


async def send_test() -> dict:
    """Send a confirmation message to the owner (used by the panel's test button)."""
    token, owner = tokens()
    if not token or not owner:
        return {"ok": False, "error": "Add the bot token and the owner number id first."}
    ok, res = await send(token, owner,
                         f"✅ *TL robot connected*\n{_M.db.setting('panel_name', 'Dollax Panel')} is under your control.\nSend /help for the command list.",
                         markdown=True)
    return {"ok": bool(ok), "error": "" if ok else str((res or {}).get("error") or "")}
