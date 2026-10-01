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
        await tg_call(DTOKEN, "sendMessage", request_timeout=15.0, chat_id=chat_id,
                      text=main_text(chat_id), parse_mode="Markdown",
                      reply_markup=main_keyboard(chat_id))
        return ""
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
        return "⛔ activity log is not available from the bot."
    if cmd == "nodes":
        nodes = _M.db.list_nodes()
        if not nodes:
            return "no nodes connected"
        return "🛰 *nodes*\n" + "\n".join(
            f"• *{n['name']}* ({n['location'] or '-'}) - {n['status'] or 'never synced'} · "
            f"{len(_M.db.json_raw(n.get('snapshot'), []))} inbounds"
            for n in nodes[:15])
    return "🤔 unknown command. /help"


# ================================================================== button UI
# Telegram has no button colours, so the green profile button is marked with a green
# square instead: 🟩 پروفایل من. Everything is reachable by tapping - no typing commands.
L = {
    "fa": {"panel": "🌐 دسترسی به پنل", "inbound": "اینباند", "status": "وضعیت", "enabled": "فعال", "disabled": "غیرفعال",
           "name": "نام", "quota": "حجم (گیگ)", "reset": "صفر کردن مصرف", "link": "کانفیگ",
           "config": "📥 دریافت کانفیگ", "profile": "🟩 پروفایل من", "clients": "👥 کاربران",
           "inbounds": "📶 اینباندها", "hosts": "🗂 هاست‌ها", "nodes": "🛰 نودها",
           "admins": "🛡 ادمین‌ها", "bot": "⚙️ ربات", "back": "⬅️ بازگشت", "lang": "🌐 زبان",
           "new": "➕ ساخت", "list": "📋 فهرست", "used": "مصرف‌شده", "left": "باقی‌مانده",
           "days": "روز باقی‌مانده", "no_client": "حساب شما به پنل متصل نیست؛ به مدیر بگویید.",
           "sub": "لینک اشتراک", "configs": "کانفیگ‌ها", "created": "ساخته شد",
           "ask_newclient": "بنویسید: نام‌اینباند | نام‌کاربر | گیگابایت | روز",
           "ask_newinbound": "بنویسید: نام | آدرس | پورت | پروتکل | شبکه | امنیت",
           "ask_host": "آدرس هاست را بنویسید", "ask_node": "بنویسید: نام | آدرس‌پنل | توکن | کشور",
           "ask_admin": "بنویسید: نام‌کاربری | رمز", "done": "انجام شد", "usage": "مصرف شما",
           "self": "👤 پروفایل من"},
    "en": {"panel": "🌐 Access panel", "inbound": "Inbound", "status": "Status", "enabled": "active", "disabled": "disabled",
           "name": "Name", "quota": "Quota (GB)", "reset": "Reset usage", "link": "Config",
           "config": "📥 Get config", "profile": "🟩 My profile", "clients": "👥 Clients",
           "inbounds": "📶 Inbounds", "hosts": "🗂 Hosts", "nodes": "🛰 Nodes",
           "admins": "🛡 Admins", "bot": "⚙️ Bot", "back": "⬅️ Back", "lang": "🌐 Language",
           "new": "➕ New", "list": "📋 List", "used": "Used", "left": "Left",
           "days": "days left", "no_client": "Your account is not linked to the panel yet - ask your admin.",
           "sub": "Subscription", "configs": "Configs", "created": "created",
           "ask_newclient": "Send: inbound | client | GB | days",
           "ask_newinbound": "Send: name | address | port | protocol | network | security",
           "ask_host": "Send the host address", "ask_node": "Send: name | panel url | token | country",
           "ask_admin": "Send: username | password", "done": "done", "usage": "Your usage",
           "self": "👤 My profile"},
}
PENDING = {}          # chat_id -> what the next text message is for


def tr(lang, key):
    return L.get(lang, L["fa"]).get(key, L.get("en", {}).get(key, key))


def _lang(chat_id) -> str:
    try:
        return str(_M.db.get_bot_user(chat_id).get("lang") or "fa")
    except Exception:  # noqa: BLE001
        return "fa"


def _is_owner(chat_id) -> bool:
    return bool(DOWNER) and str(chat_id) == str(DOWNER)


def kb(rows):
    return {"inline_keyboard": rows}


def main_keyboard(chat_id) -> dict:
    lg = _lang(chat_id)
    if _is_owner(chat_id):
        return kb([[{"text": tr(lg, "clients"), "callback_data": "menu:clients"},
                    {"text": tr(lg, "inbounds"), "callback_data": "menu:inbounds"}],
                   [{"text": tr(lg, "hosts"), "callback_data": "menu:hosts"},
                    {"text": tr(lg, "nodes"), "callback_data": "menu:nodes"}],
                   [{"text": tr(lg, "admins"), "callback_data": "menu:admins"},
                    {"text": tr(lg, "bot"), "callback_data": "menu:bot"}],
                   [{"text": tr(lg, "panel"), "callback_data": "menu:panel"}],
                   [{"text": tr(lg, "lang"), "callback_data": "menu:lang"}]])
    return kb([[{"text": tr(lg, "config"), "callback_data": "act:get"}],
               [{"text": tr(lg, "profile"), "callback_data": "act:me"}]])


def main_text(chat_id) -> str:
    lg = _lang(chat_id)
    if _is_owner(chat_id):
        return ("🤖 *TL robot*\\n" + _status_text() + "\\n\\n" + tr(lg, "bot") + " → " +
                " · ".join([tr(lg, "clients"), tr(lg, "inbounds"), tr(lg, "hosts"),
                            tr(lg, "nodes"), tr(lg, "admins")]))
    return ("🤖 *TL robot*\\n\\n" + tr(lg, "config") + "  |  " + tr(lg, "profile"))


def _bound_clients(chat_id):
    return _M.db.clients_for_tg(chat_id)


def _bar(pct: int) -> str:
    """A slim ten-cell usage bar for pretty progress lines."""
    pct = max(0, min(100, int(pct or 0)))
    filled = int(round(pct / 10.0))
    return "\u25b0" * filled + "\u25b1" * (10 - filled)


def profile_text(chat_id) -> str:
    lg = _lang(chat_id)
    rows = _bound_clients(chat_id)
    if not rows:
        return "\U0001f464 " + tr(lg, "self") + "\n\n" + tr(lg, "no_client")
    out = ["\U0001f464 *" + tr(lg, "self") + "*", "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501"]
    for c in rows:
        limit = int(c.get("limit_bytes") or 0)
        used = int(c.get("used_bytes") or 0)
        pct = round(used / limit * 100) if limit else 0
        left = _fmt_bytes(max(0, limit - used)) if limit else "\u221e"
        d = _M.db.days_left(c.get("expires_at")) if c.get("expires_at") else None
        out.append("*" + str(c.get("name")) + "*")
        out.append(_bar(pct) + "  " + str(pct) + "%")
        out.append(tr(lg, "used") + ": " + _fmt_bytes(used) + "  \u00b7  " + tr(lg, "left") + ": " + left)
        out.append("\u23f3 " + tr(lg, "days") + ": " + (str(d) if d is not None else "\u221e"))
        out.append("\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501")
    return "\n".join(out)


def trial_settings() -> tuple:
    """(trial inbound id or '', GB, days) - how a new bot user is provisioned."""
    ib = str(_M.db.setting("tg_trial_inbound") or "").strip()
    gb = _M.as_int(_M.db.setting("tg_trial_gb", "5"), 5, 1, 1000)
    days = _M.as_int(_M.db.setting("tg_trial_days", "30"), 30, 1, 3650)
    return ib, gb, days


def _trial_inbound(ib_setting: str):
    """The inbound a new bot user gets a client on."""
    if ib_setting:
        found = find_inbound(ib_setting)
        if found:
            return found
    for i in _inbounds():                       # first usable inbound
        if i.get("enabled") and str(i.get("security") or "").lower() != "wireguard":
            return i
    return None


def provision_for(chat_id, display_name: str = ""):
    """Give this Telegram user their own client (once) and return (client, error)."""
    rows = _bound_clients(chat_id)
    if rows:
        return rows[0], ""                      # already has one - never create a second
    ib_setting, gb, days = trial_settings()
    ib = _trial_inbound(ib_setting)
    if not ib:
        return None, "no inbound is available for new accounts yet"
    name = (display_name or "").strip()[:26] or ("tg-" + str(chat_id)[-6:])
    try:
        cid = _M.db.create_client(
            ib["id"], name,
            limit_bytes=int(gb) * 1024 ** 3,
            expires_at=_M.expiry(days),
            ip_limit=0, connection_limit=0, speed_limit_mbps=0,
            note="tg:" + str(chat_id),           # this is what /profile reads
            enabled=1, created_by="telegram", extra_inbounds=[], config_count=2,
        )
    except Exception as exc:  # noqa: BLE001
        return None, f"{exc.__class__.__name__}: {str(exc)[:100]}"
    row = _M.db.client_row(cid)
    return dict(row) if row else None, ""


def config_text(chat_id) -> str:
    lg = _lang(chat_id)
    rows = _bound_clients(chat_id)
    if not rows:
        return tr(lg, "no_client")
    c = rows[0]
    cl = _M.client_dict(c, _FakeRequest())
    sub = _M.base_url(_FakeRequest()) + "/sub/" + str(c.get("sub_token") or "")
    first = (cl.get("links") or [""])[0]
    return (f"📥 *{c.get('name')}*\\n\\n{tr(lg, 'sub')}:\\n`{sub}`\\n\\n"
            f"{tr(lg, 'configs')}: {len(cl.get('links') or [])}\\n`{first}`")


def lang_keyboard() -> dict:
    return kb([[{"text": "🇮🇷 فارسی", "callback_data": "lang:fa"},
                {"text": "🇬🇧 English", "callback_data": "lang:en"}],
               [{"text": "⬅️", "callback_data": "menu:main"}]])


def list_keyboard(what, chat_id) -> tuple:
    """(text, keyboard) for the owner listing screens."""
    lg = _lang(chat_id)
    rows = []
    if what == "clients":
        items = _M.db.list_clients()
        lines = [f"👥 *{tr(lg, 'clients')}* ({len(items)})",
                 "👆 " + ("برای جزئیات روی کاربر بزنید" if lg == "fa" else "tap a client for details")]
        for c in items[:18]:                      # every client is its own button
            used = _fmt_bytes(c.get("used_bytes"))
            cap = "/" + _fmt_bytes(c.get("limit_bytes")) if c.get("limit_bytes") else ""
            rows.append([{"text": "👤 " + str(c["name"])[:24] + " — " + used + cap,
                          "callback_data": "cl:" + str(c["id"])}])
        rows.append([{"text": tr(lg, "new") + " " + tr(lg, "clients"), "callback_data": "act:new:client"}])
    elif what == "inbounds":
        items = _inbounds()
        lines = [f"📶 *{tr(lg, 'inbounds')}* ({len(items)})"]
        for i in items[:20]:
            lines.append(f"• {i['name']} — {i['protocol']}/{i['network']}/{i['security']} · "
                         f"{i['address'] or '(panel domain)'}:{i['port']}")
        rows.append([{"text": tr(lg, "new") + " " + tr(lg, "inbounds"), "callback_data": "act:new:inbound"}])
    elif what == "hosts":
        items = _M.db.list_hosts()
        lines = [f"🗂 *{tr(lg, 'hosts')}* ({len(items)})"] + [f"• `{h['address']}`" for h in items[:20]]
        rows.append([{"text": tr(lg, "new") + " " + tr(lg, "hosts"), "callback_data": "act:new:host"}])
    elif what == "nodes":
        items = _M.db.list_nodes()
        lines = [f"🛰 *{tr(lg, 'nodes')}* ({len(items)})"]
        for n in items[:20]:
            lines.append(f"• {n['name']} ({n['location'] or '-'}) — {n['status'] or 'never synced'}")
        rows.append([{"text": "🔗 " + tr(lg, "new"), "callback_data": "act:new:node"}])
    elif what == "admins":
        items = _M.db.list_admins()
        lines = [f"🛡 *{tr(lg, 'admins')}* ({len(items)})"]
        for a in items[:20]:
            lines.append(f"• {a['username']} — {a.get('role') or 'admin'}")
        rows.append([{"text": tr(lg, "new") + " " + tr(lg, "admins"), "callback_data": "act:new:admin"}])
    else:
        lines, rows = ["?"], []
    rows.append([{"text": tr(lg, "back"), "callback_data": "menu:main"}])
    return "\\n".join(lines), kb(rows)


async def handle_callback(token: str, query: dict):
    """A button was tapped: answer it and (re)render the right screen."""
    chat_id = str((query.get("message") or {}).get("chat", {}).get("id") or (query.get("from") or {}).get("id") or "")
    msg_id = (query.get("message") or {}).get("message_id")
    data = str(query.get("data") or "")
    await tg_call(token, "answerCallbackQuery", request_timeout=15.0, callback_query_id=query.get("id"))

    if not _is_owner(chat_id) and not data.startswith(("act:get", "act:me", "lang:", "menu:main", "menu:lang")):
        # everyone else only has the two buttons
        await tg_call(token, "sendMessage", request_timeout=15.0, chat_id=chat_id,
                      text=main_text(chat_id), reply_markup=main_keyboard(chat_id))
        STATE["handled"] += 1
        return

    text, markup = None, None
    if data == "menu:main":
        text, markup = main_text(chat_id), main_keyboard(chat_id)
    elif data == "menu:panel":
        lgx = _lang(chat_id)
        host = str(_M.db.setting("public_base_url") or "").rstrip("/")
        if not host:
            host = _FakeRequest().base_url.rstrip("/")
        text = (f"{tr(lgx, 'panel')}\n\n"
                f"🏷 {_M.db.setting('panel_name', 'Dollax Panel')} v{_M.APP_VERSION}\n"
                f"🔗 `{host}`\n"
                f"🖥 `{host}/login`\n"
                f"📡 `{host}/sub/<token>`")
        markup = kb([[{"text": tr(lgx, "back"), "callback_data": "menu:main"}]])
    elif data == "menu:lang":
        text, markup = tr(_lang(chat_id), "lang"), lang_keyboard()
    elif data.startswith("lang:"):
        new = data.split(":", 1)[1]
        _M.db.set_bot_user(chat_id, lang=new)
        text, markup = tr(new, "done") + " · " + tr(new, "bot"), main_keyboard(chat_id)
    elif data == "act:me":
        text = profile_text(chat_id)
        markup = kb([[{"text": tr(_lang(chat_id), "lang"), "callback_data": "menu:lang"}],
                     [{"text": tr(_lang(chat_id), "back"), "callback_data": "menu:main"}]])
    elif data == "act:get":
        display = " ".join(filter(None, [((query.get("from") or {}).get("first_name") or ""),
                                         ((query.get("from") or {}).get("last_name") or "")]))
        created, err = provision_for(chat_id, display)
        if err or not created:
            lgx = _lang(chat_id)
            text = "⚠️ " + (err or tr(lgx, "no_client"))
            markup = main_keyboard(chat_id)
        else:
            lgx = _lang(chat_id)
            gb = int(created.get("limit_bytes") or 0) // 1024 ** 3
            d = _M.db.days_left(created.get("expires_at")) if created.get("expires_at") else None
            text = (f"🎁 *{tr(lgx, 'config')}*\n\n"
                    f"👤 {created.get('name')}\n📦 {gb} GB\n⏳ {d} {tr(lgx, 'days')}\n\n"
                    + config_text(chat_id).split("\n\n", 1)[-1])
            markup = main_keyboard(chat_id)
        STATE["handled"] += 1
        if msg_id:
            ok, _ = await tg_call(token, "editMessageText", request_timeout=20.0, chat_id=chat_id,
                                  message_id=msg_id, text=text[:4000], parse_mode="Markdown",
                                  reply_markup=markup, disable_web_page_preview=True)
            if ok:
                return
        await tg_call(token, "sendMessage", request_timeout=20.0, chat_id=chat_id, text=text[:4000],
                      parse_mode="Markdown", reply_markup=markup, disable_web_page_preview=True)
        return
    elif data.startswith("cl:"):
        cid = data.split(":", 1)[1]
        text, markup = client_detail_text(cid), client_detail_keyboard(cid, chat_id)
    elif data.startswith("editc:"):
        cid = data.split(":", 1)[1]
        text = "✏️ *" + tr(_lang(chat_id), "edit") + "*"
        markup = client_edit_keyboard(cid, chat_id)
    elif data.startswith("delc:"):
        cid = data.split(":", 1)[1]
        row = _M.db.client_row(cid)
        text = "🗑 " + (str(row["name"]) if row else "?") + " — ?"
        markup = kb([[{"text": "✅ " + tr(_lang(chat_id), "del"), "callback_data": "confirmdel:" + cid},
                      {"text": tr(_lang(chat_id), "back"), "callback_data": "cl:" + cid}]])
    elif data.startswith("confirmdel:"):
        cid = data.split(":", 1)[1]
        row = _M.db.client_row(cid)
        name = str(row["name"]) if row else "?"
        _M.db.delete_client(cid)
        text, markup = "🗑 *" + name + "* " + tr(_lang(chat_id), "deleted"), main_keyboard(chat_id)
    elif data.startswith("linkc:"):
        cid = data.split(":", 1)[1]
        row = _M.db.client_row(cid)
        text = _link([str(row["name"])]) if row else "⚠️ not found"
        markup = client_detail_keyboard(cid, chat_id)
    elif data.startswith("prof:"):
        cid = data.split(":", 1)[1]
        text = profile_text(chat_id)
        markup = client_detail_keyboard(cid, chat_id)
    elif data.startswith("e:toggle:") or data.startswith("e:reset:"):
        _, field, cid = data.split(":", 2)
        row = _M.db.client_row(cid)
        if field == "toggle" and row:
            _M.db.update_client(cid, {"enabled": 0 if row["enabled"] else 1})
        elif field == "reset" and row:
            _M.db.reset_client_usage(cid)
        text, markup = client_detail_text(cid), client_detail_keyboard(cid, chat_id)
    elif data.startswith("e:"):
        _, field, cid = data.split(":", 2)
        PENDING[chat_id] = "edit:" + field + ":" + cid
        text = "✏️ " + tr(_lang(chat_id), field if field != "count" else "configs")
        markup = kb([[{"text": tr(_lang(chat_id), "back"), "callback_data": "editc:" + cid}]])
    elif data.startswith("menu:"):
        what = data.split(":", 1)[1]
        if what == "bot":
            text = (_status_text() + "\\n\\n" + tr(_lang(chat_id), "lang"))
            markup = kb([[{"text": tr(_lang(chat_id), "lang"), "callback_data": "menu:lang"}],
                         [{"text": tr(_lang(chat_id), "back"), "callback_data": "menu:main"}]])
        else:
            text, markup = list_keyboard(what, chat_id)
    elif data.startswith("act:new:"):
        what = data.split(":")[2]
        PENDING[chat_id] = "new:" + what
        text = tr(_lang(chat_id), "ask_" + ("newclient" if what == "client" else
                                           "newinbound" if what == "inbound" else
                                           "host" if what == "host" else
                                           "node" if what == "node" else "admin"))
        markup = kb([[{"text": tr(_lang(chat_id), "back"), "callback_data": "menu:main"}]])
    else:
        text, markup = main_text(chat_id), main_keyboard(chat_id)

    if msg_id:
        ok, info = await tg_call(token, "editMessageText", request_timeout=20.0, chat_id=chat_id,
                                 message_id=msg_id, text=text[:4000], parse_mode="Markdown",
                                 reply_markup=markup, disable_web_page_preview=True)
        if ok or "not modified" in str((info or {}).get("error", "")).lower():
            STATE["handled"] += 1
            return
    await tg_call(token, "sendMessage", request_timeout=20.0, chat_id=chat_id, text=text[:4000],
                  parse_mode="Markdown", reply_markup=markup, disable_web_page_preview=True)
    STATE["handled"] += 1


async def handle_text(token: str, chat_id, text: str):
    """A message arrived: either a pending form (after a button) or a menu action."""
    chat_id = str(chat_id)
    lg = _lang(chat_id)
    pending = PENDING.pop(chat_id, None)
    raw = str(text or "").strip()

    if pending and pending.startswith("edit:") and _is_owner(chat_id):
        _, field, cid = pending.split(":", 2)
        reply = _apply_edit(chat_id, field, cid, raw)
        await tg_call(token, "sendMessage", request_timeout=20.0, chat_id=chat_id, text=reply[:4000],
                      parse_mode="Markdown", reply_markup=client_detail_keyboard(cid, chat_id))
        STATE["handled"] += 1
        return reply

    if pending and _is_owner(chat_id):
        parts = [p.strip() for p in raw.split("|")] if "|" in raw else raw.split()
        try:
            if pending == "new:client":
                if len(parts) < 2:
                    PENDING[chat_id] = pending
                    return tr(lg, "ask_newclient")
                reply = _new_client(parts)
            elif pending == "new:inbound":
                reply = _new_inbound(parts)
            elif pending == "new:host":
                _M.db.add_host(parts[0], created_by="telegram")
                reply = "✅ " + tr(lg, "done") + " · " + parts[0]
            elif pending == "new:node":
                if len(parts) < 3:
                    PENDING[chat_id] = pending
                    return tr(lg, "ask_node")
                nid = _M.db.add_node({"name": parts[0], "url": parts[1], "token": parts[2],
                                      "location": parts[3] if len(parts) > 3 else "",
                                      "created_by": "telegram"})
                res = await asyncio.to_thread(_M.api_extras.refresh_node, nid)
                reply = ("✅ " + parts[0] + " " + tr(lg, "done") if res.get("ok")
                         else "⚠️ " + str(res.get("error")))
            elif pending == "new:admin":
                if len(parts) < 2:
                    PENDING[chat_id] = pending
                    return tr(lg, "ask_admin")
                _M.db.create_admin(parts[0], parts[1], role="admin")
                reply = "✅ " + parts[0] + " " + tr(lg, "done")
            else:
                reply = main_text(chat_id)
        except Exception as exc:  # noqa: BLE001
            reply = "⚠️ " + exc.__class__.__name__ + ": " + str(exc)[:120]
        await tg_call(token, "sendMessage", request_timeout=20.0, chat_id=chat_id, text=reply[:4000],
                      parse_mode="Markdown", reply_markup=main_keyboard(chat_id))
        STATE["handled"] += 1
        return reply

    if _is_owner(chat_id):
        # a plain message from the owner: still allow the classic commands
        reply = await handle_command(raw, chat_id)
        if reply:
            await tg_call(token, "sendMessage", request_timeout=20.0, chat_id=chat_id, text=reply[:4000],
                          parse_mode="Markdown", reply_markup=main_keyboard(chat_id))
            STATE["handled"] += 1
        return reply

    # non-owner: only the two buttons
    await tg_call(token, "sendMessage", request_timeout=20.0, chat_id=chat_id, text=main_text(chat_id),
                  parse_mode="Markdown", reply_markup=main_keyboard(chat_id))
    STATE["handled"] += 1
    return main_text(chat_id)


def client_detail_text(cid: str) -> str:
    row = _M.db.client_row(cid)
    if not row:
        return "\u26a0\ufe0f client not found"
    c = dict(row)
    limit = int(c.get("limit_bytes") or 0)
    used = int(c.get("used_bytes") or 0)
    pct = round(used / limit * 100) if limit else 0
    left = _fmt_bytes(max(0, limit - used)) if limit else "\u221e"
    d = _M.db.days_left(c.get("expires_at")) if c.get("expires_at") else None
    ib = _M.db.inbound_row(c.get("inbound_id")) if c.get("inbound_id") else None
    labels = L.get(_lang("0"), L["fa"])
    return ("\U0001f464 *" + str(c.get("name")) + "*\n"
            "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
            + _bar(pct) + "  " + str(pct) + "%\n"
            + "\U0001f4f6 " + labels["inbound"] + ": " + (ib["name"] if ib else "-") + "\n"
            + "\U0001f4ca " + labels["used"] + ": " + _fmt_bytes(used) + "\n"
            + "\U0001f4e6 " + labels["left"] + ": " + left + "\n"
            + "\u23f3 " + labels["days"] + ": " + (str(d) if d is not None else "\u221e") + "\n"
            + "\U0001f50c " + labels["status"] + ": " + (labels["enabled"] if c.get("enabled") else labels["disabled"]) + "\n"
            + "\U0001f9e9 " + labels["configs"] + ": " + str(int(c.get("config_count") or 2)))


def client_detail_keyboard(cid: str, chat_id) -> dict:
    lg = _lang(chat_id)
    r = []
    r.append([{"text": "✏️ " + tr(lg, "edit"), "callback_data": "editc:" + cid},
              {"text": "🗑 " + tr(lg, "del"), "callback_data": "delc:" + cid}])
    r.append([{"text": "🔗 " + tr(lg, "link"), "callback_data": "linkc:" + cid},
              {"text": "🟩 " + tr(lg, "self"), "callback_data": "prof:" + cid}])
    r.append([{"text": tr(lg, "back"), "callback_data": "menu:clients"}])
    return kb(r)


def client_edit_keyboard(cid: str, chat_id) -> dict:
    lg = _lang(chat_id)
    row = _M.db.client_row(cid)
    on = bool(row and row["enabled"])
    return kb([
        [{"text": "✏️ " + tr(lg, "name"), "callback_data": "e:name:" + cid},
         {"text": "📦 " + tr(lg, "quota"), "callback_data": "e:quota:" + cid}],
        [{"text": "⏳ " + tr(lg, "days"), "callback_data": "e:days:" + cid},
         {"text": "🧩 " + tr(lg, "configs"), "callback_data": "e:count:" + cid}],
        [{"text": ("🚫 " + tr(lg, "disable")) if on else ("✅ " + tr(lg, "enable")),
          "callback_data": "e:toggle:" + cid},
         {"text": "🔄 " + tr(lg, "reset"), "callback_data": "e:reset:" + cid}],
        [{"text": tr(lg, "back"), "callback_data": "cl:" + cid}],
    ])


def _apply_edit(chat_id, field: str, cid: str, value: str) -> str:
    """Apply one edited field to a client and answer with the result."""
    lg = _lang(chat_id)
    row = _M.db.client_row(cid)
    if not row:
        return "⚠️ client not found"
    v = str(value or "").strip()
    if field == "name":
        _M.db.update_client(cid, {"name": v[:80] or row["name"]})
        return "✅ " + tr(lg, "name") + ": " + v[:40]
    if field == "quota":
        gb = float(v.replace("gb", "").strip() or 0) if v else 0
        _M.db.update_client(cid, {"limit_bytes": int(max(0.0, gb) * 1024 ** 3)})
        return "✅ " + tr(lg, "quota") + ": " + (str(gb) + " GB" if gb else "∞")
    if field == "days":
        n = int(v) if v.isdigit() else 0
        _M.db.update_client(cid, {"expires_at": _M.expiry(n) if n else ""})
        return "✅ " + tr(lg, "days") + ": " + (str(n) if n else "∞")
    if field == "count":
        n = max(1, min(10, int(v) if v.isdigit() else 2))
        _M.db.update_client(cid, {"config_count": n})
        return "✅ " + tr(lg, "configs") + ": " + str(n)
    return "⚠️ " + field


# ---------------------------------------------------------------- lifecycle
async def _poll_once(token: str) -> bool:
    # NB: callback_query must be included (or the field omitted) or Telegram never delivers
    # button taps - the bot would look dead even though the menu renders.
    ok, res = await tg_call(token, "getUpdates", request_timeout=35.0,
                            offset=STATE["offset"] + 1, timeout=25,
                            allowed_updates=["message", "callback_query"])
    if not ok:
        STATE["last_error"] = str((res or {}).get("error") or "poll failed")[:160]
        return False
    STATE["last_error"] = ""
    STATE["last_poll"] = time.time()
    for upd in res or []:
        STATE["offset"] = max(STATE["offset"], int(upd.get("update_id") or 0))
        if upd.get("callback_query"):
            try:
                await handle_callback(token, upd["callback_query"])
            except Exception as exc:  # noqa: BLE001
                STATE["last_error"] = f"callback: {exc.__class__.__name__}: {exc}"[:160]
            continue
        msg = upd.get("message") or {}
        text = msg.get("text") or ""
        chat = (msg.get("chat") or {}).get("id")
        if not text or chat is None:
            continue
        try:
            await handle_text(token, chat, text)
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


_LOCK_HANDLE = {"fh": None}


def _acquire_single_instance() -> bool:
    """Only one process may poll a bot token; a second one gets 409 Conflict and upsets
    Telegram's update cursor. The panel can run two listeners (a port safety net), so this
    makes the first one win and the others stay quiet."""
    try:
        path = os.path.join(str(_M.db.DATA_DIR), "tg_bot.lock")   # works for Path or str
        fh = open(path, "a+")
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except Exception:  # noqa: BLE001
            fh.close()
            return False
        _LOCK_HANDLE["fh"] = fh
        return True
    except Exception:  # noqa: BLE001
        return True                     # cannot lock (no fs): better to run than not


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
    if not _acquire_single_instance():
        STATE["running"] = False
        STATE["last_error"] = "another panel listener is already polling this bot (single instance lock)"
        print("[dollax] TL robot: another instance holds the poll lock - not polling here", flush=True)
        return False
    try:
        STATE["task"] = asyncio.get_event_loop().create_task(_loop(token))
    except RuntimeError:
        loop = asyncio.new_event_loop()
        STATE["task"] = loop.create_task(_loop(token))
    return True


def stop() -> None:
    """Stop polling and release the single-instance lock so a restart can take it again."""
    STATE["running"] = False
    task = STATE.get("task")
    if task:
        try:
            task.cancel()
        except Exception:  # noqa: BLE001
            pass
    STATE["task"] = None
    fh = _LOCK_HANDLE.get("fh")
    if fh:
        try:
            if os.name == "nt":
                import msvcrt
                fh.seek(0)
                msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        except Exception:  # noqa: BLE001
            pass
        try:
            fh.close()
        except Exception:  # noqa: BLE001
            pass
        _LOCK_HANDLE["fh"] = None


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
