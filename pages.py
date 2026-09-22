"""Dollax Panel — HTML shells (login, dashboard, graphical subscription page).

The dashboard markup mirrors the Cloudflare Worker's dashboard (same class
names, same structure) so the ported style.css applies 1:1. The subscription
page is a standalone, per-inbound graphical page with a real QR code.
"""
from html import escape
import os

FONTS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800;900&'
    'family=Vazirmatn:wght@400;600;700;800;900&'
    'family=Poppins:wght@400;600;700;800&'
    'family=Roboto:wght@400;500;700;900&'
    'family=Space+Grotesk:wght@400;600;700&'
    'family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">'
)


def _doc(title, body, lang="en", theme="dark-green", style="solid", extra_head=""):
    rtl = "rtl" if lang == "fa" else "ltr"
    return f"""<!doctype html>
<html lang="{lang}" dir="{rtl}" data-theme="{escape(theme)}" data-style="{escape(style)}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="dark">
<title>{escape(title)}</title>
{FONTS}
<link rel="stylesheet" href="/static/style.css">
{extra_head}
</head>
<body>
{body}
</body>
</html>"""


# ---------------------------------------------------------------- dashboard
def dashboard_html(panel_name="Dollax Panel", version="dev"):
    body = f"""<div id="root"></div>
<div class="modal hidden" id="modal">
  <div class="modal-box" id="modalBox">
    <div class="modal-head">
      <div class="modal-title" id="modalTitle">-</div>
      <button class="close" id="modalClose" type="button">&times;</button>
    </div>
    <div id="modalBody"></div>
  </div>
</div>
<div class="toasts" id="toasts"></div>
<script src="/static/app.js"></script>
<script src="/static/app2.js"></script>"""
    # the whole shell is rendered by app.js, like the Worker does
    return _doc(panel_name, body)


# ---------------------------------------------------------------- login
def login_html(panel_name="Dollax Panel", error="", lang="en", theme="dark-green", style="solid"):
    t = _T(lang)
    err = f'<div class="err show">{escape(error)}</div>' if error else '<div class="err" id="loginErr"></div>'
    body = f"""<div class="login-wrap">
  <form class="login-box" method="post" action="/login" autocomplete="on">
    <div class="login-logo">D</div>
    <div class="login-name">{escape(panel_name)}</div>
    <div class="login-sub">{t("secureSub")}</div>
    {err}
    <div style="display:flex;flex-direction:column;gap:11px;margin-top:16px">
      <label class="field"><span>{t("user")}</span>
        <input name="username" autocomplete="username" required autofocus></label>
      <label class="field"><span>{t("password")}</span>
        <input name="password" type="password" autocomplete="current-password" required></label>
      <button class="btn primary wide" type="submit" style="height:38px">{t("signIn")}</button>
    </div>
    <div class="login-hint">dollax26 / dollax26 &middot; {t("changeAfter")}</div>
  </form>
</div>"""
    return _doc(f"{panel_name} — {t('signIn')}", body, lang=lang, theme=theme, style=style)


# ---------------------------------------------------------------- subscription pages
def _tpl_aurora(data):
    """Aurora - the built-in graphical page (donut, QR, per-config copy rows)."""
    lang = data.get("language", "en")
    t = _T(lang)
    esc = escape

    badges = "".join(
        f'<span class="badge acc">{esc(b)}</span>' for b in data.get("badges", [])
    )

    clients_html = ""
    for c in data.get("clients", []):
        rows = []
        for i, l in enumerate(c.get("links", []) or [], 1):
            link = l if isinstance(l, str) else str((l or {}).get("link") or "")
            if not link:
                continue
            rows.append(
                f'<div class="cfg-row"><span class="cfg-idx">#{i}</span>'
                f'<code class="cfg-code">{esc(link)}</code>'
                f'<button class="btn sm" type="button" data-copy="{esc(link, quote=True)}">{t("copy")}</button>'
                f'</div>')
        links = "".join(rows)
        clients_html += f"""
    <div class="client-card fade-in">
      <div class="cc-head">
        <span class="cc-name">{esc(c["name"])}</span>
        <span class="badge {c["status_class"]}">{esc(c["status"])}</span>
        <span class="cc-grow"></span>
        <button class="btn sm" type="button" data-copy="{esc(c["sub_url"], quote=True)}">{t("copySub")}</button>
      </div>
      <div class="bar"><i style="width:{c["pct"]}%"></i></div>
      <div class="kv-line">
        <span>{t("used")} <b>{esc(c["used"])}</b></span>
        <span>{t("download")} <b>{esc(c.get("down", "\u2014"))}</b></span>
        <span>{t("upload")} <b>{esc(c.get("up", "\u2014"))}</b></span>
        <span>{t("remaining")} <b>{esc(c["remaining"])}</b></span>
        <span>{t("expires")} <b>{esc(c["expires"])}</b></span>
      </div>
      {links}
    </div>"""

    body = f"""<div class="sub-wrap">
  <div class="sub-head">
    <div class="sub-logo">
      <div class="logo-mark">D</div>
      <div><div class="name">{esc(data["panel_name"])}</div>
      <div class="mini">{t("brandSub")}</div></div>
    </div>
    <div style="display:flex;gap:7px;flex-wrap:wrap">
      <span class="pill ok">● {t("running")}</span>
    </div>
  </div>

  <div class="hero fade-in">
    <div class="hero-info">
      <div class="hero-title">{esc(data["title"])} {badges}</div>
      <div class="hero-meta">{esc(data["endpoint"])}</div>
      <div class="kv-line" style="margin-top:9px">
        <span>{t("protocol")} <b>{esc(data["protocol"].upper())}</b></span>
        <span>{t("clients")} <b>{esc(str(data["client_count"]))}</b></span>
        <span>{t("configNodes")} <b>{esc(str(data["config_count"]))}</b></span>
        <span>{t("download")} <b>{esc(data.get("down", "\u2014"))}</b></span>
        <span>{t("upload")} <b>{esc(data.get("up", "\u2014"))}</b></span>
      </div>
      <div class="sub-url">
        <code id="subUrl">{esc(data["sub_url"])}</code>
        <button class="btn primary sm" type="button" data-copy="{esc(data["sub_url"], quote=True)}">{t("copy")}</button>
      </div>
      <div class="fmt-row">
        <button class="btn sm" type="button" data-copy="{esc(data["sub_clash"], quote=True)}">{t("clashSub")}</button>
        <button class="btn sm" type="button" data-copy="{esc(data["sub_singbox"], quote=True)}">{t("singboxSub")}</button>
        <button class="btn sm" type="button" data-copy="{esc(data["sub_base64"], quote=True)}">{t("genericSub")}</button>
      </div>
    </div>
    <div class="donut" style="--pct:{data["pct"]}">
      <div class="donut-in">
        <div class="donut-val">{data["pct"]}%</div>
        <div class="donut-lbl">{t("used")}</div>
      </div>
    </div>
    <div class="hero-qr">{data["qr_svg"]}</div>
  </div>

  <div class="sub-grid">
    {clients_html or f'<div class="empty"><b>{t("noClients")}</b>{t("subEmptyHint")}</div>'}
  </div>

  <p class="muted" style="text-align:center;margin-top:20px;font-size:10px">
    {t("subFooter")} &middot; {esc(data["panel_name"])}
  </p>
</div>
<script>
document.addEventListener('click', function (e) {{
  var b = e.target.closest('[data-copy]');
  if (!b) return;
  navigator.clipboard.writeText(b.getAttribute('data-copy')).then(function () {{
    var old = b.textContent; b.textContent = '{t("copied")}';
    setTimeout(function () {{ b.textContent = old; }}, 1200);
  }});
}});
</script>"""
    return _doc(f"{data['panel_name']} — {data['title']}", body, lang=lang,
                theme=data.get("theme", "dark-green"), style=data.get("ui_style", "solid"))



# ---------------------------------------------------------------- template registry
# Designs live as plain HTML files in static/sub-templates/ (edit them freely).
# Placeholders use string.Template syntax: $panel, $title, $endpoint, $protocol,
# $clients, $configs, $pct, $used, $up, $down, $remaining, $expires, $sub_url,
# $sub_clash, $sub_singbox, $qr, $tags, $cards, $lang, $dir, $theme, $style, $l_*.
TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "sub-templates")

TEMPLATE_LIST = [
    {"id": "xui", "name": "X-UI / 3x-ui", "hint": "The familiar x-ui layout - dark header, big counters, per-config rows."},
    {"id": "aurora", "name": "Aurora", "hint": "Gradient hero with a usage donut, QR tile and config cards."},
    {"id": "neon", "name": "Neon Glass", "hint": "Glassy hero, glowing usage ring, neon accents."},
    {"id": "terminal", "name": "Terminal", "hint": "Monospace console look, green on black."},
    {"id": "minimal", "name": "Minimal", "hint": "White, quiet, typography first."},
    {"id": "bento", "name": "Bento", "hint": "Modular stat tiles in a 12-column grid."},
]
TEMPLATE_IDS = [t["id"] for t in TEMPLATE_LIST]
DASH, INF = chr(8212), chr(8734)


def _read_template(tid: str) -> str:
    try:
        with open(os.path.join(TEMPLATE_DIR, tid + ".html"), encoding="utf-8") as fh:
            return fh.read()
    except Exception:
        return ""


def _label_map(t) -> dict:
    return {
        "l_used": t("used"), "l_up": t("upload"), "l_down": t("download"),
        "l_remaining": t("remaining"), "l_expires": t("expires"), "l_copy": t("copy"),
        "l_copied": t("copied"), "l_sub": t("genericSub"), "l_clash": t("clashSub"),
        "l_singbox": t("singboxSub"), "l_clients": t("clients"), "l_configs": t("configNodes"),
        "l_none": t("noClients"), "l_footer": t("subFooter"),
    }


def _tags_html(t, esc, data, cls="xs-tile", kcls="xs-k", vcls="xs-v"):
    tiles = [
        (t("used"), data.get("used_human") or data.get("used") or DASH),
        (t("download"), data.get("down") or DASH),
        (t("upload"), data.get("up") or DASH),
        (t("remaining"), data.get("remaining_human") or INF),
        (t("expires"), data.get("expires_human") or INF),
    ]
    parts = []
    for k, v in tiles:
        parts.append('<div class="' + cls + '"><div class="' + kcls + '">' + esc(k) + '</div>' +
                     '<div class="' + vcls + '">' + esc(str(v)) + '</div></div>')
    return "".join(parts)


def _cards_html(t, esc, clients, wrap="sc-card", wide=False):
    extra = " full" if wide else ""
    if not clients:
        return '<div class="' + wrap + extra + '"><p class="sc-meta">' + t("noClients") + '</p></div>'
    out = []
    for c in clients:
        rows = []
        for i, l in enumerate(c.get("links") or [], 1):
            l = l if isinstance(l, str) else str((l or {}).get("link") or "")
            if not l:
                continue
            rows.append('<div class="sc-row"><span class="sc-idx">#' + str(i) + '</span>' +
                        '<code class="sc-code">' + esc(l) + '</code>' +
                        '<button class="sc-btn" type="button" data-copy="' + esc(l, quote=True) + '">' +
                        t("copy") + '</button></div>')
        if not rows:
            rows = ['<div class="sc-row"><span class="sc-idx">-</span><code class="sc-code">' +
                    t("noClients") + '</code></div>']
        out.append(
            '<div class="' + wrap + extra + '">'
            '<div class="sc-head"><span class="sc-name">' + esc(c.get("name") or "client") + '</span>'
            '<span class="sc-badge ' + esc(c.get("status_class") or "") + '">' + esc(c.get("status") or "") + '</span>'
            '<span class="sc-grow"></span>'
            '<button class="sc-btn" type="button" data-copy="' + esc(c.get("sub_url") or "", quote=True) + '">' +
            t("copySub") + '</button></div>'
            '<div class="sc-bar"><i style="width:' + str(int(c.get("pct") or 0)) + '%"></i></div>'
            '<div class="sc-meta"><span>' + t("used") + ' <b>' + esc(str(c.get("used") or DASH)) + '</b></span>'
            '<span>' + t("remaining") + ' <b>' + esc(str(c.get("remaining") or INF)) + '</b></span>'
            '<span>' + t("expires") + ' <b>' + esc(str(c.get("expires") or INF)) + '</b></span></div>'
            + "".join(rows) + '</div>')
    return "".join(out)


def subscription_page(data, template="aurora"):
    """Render with the chosen template. Files in static/sub-templates win; Aurora is the
    built-in fallback, so the page never breaks when a design file is missing."""
    from string import Template
    tid = str(template or "").strip().lower()
    if tid not in TEMPLATE_IDS:
        return _tpl_aurora(data)
    raw = _read_template(tid)
    if not raw:
        return _tpl_aurora(data)
    lang = data.get("language", "en")
    t = _T(lang)
    esc = escape
    clients = data.get("clients") or []
    shared = {
        "panel": esc(str(data.get("panel_name") or "")),
        "title": esc(str(data.get("title") or "")),
        "endpoint": esc(str(data.get("endpoint") or "")),
        "protocol": esc(str(data.get("protocol") or "").upper()),
        "clients": esc(str(data.get("client_count") or 0)),
        "configs": esc(str(data.get("config_count") or 0)),
        "pct": esc(str(data.get("pct") or 0)),
        "used": esc(str(data.get("used_human") or data.get("used") or DASH)),
        "up": esc(str(data.get("up") or DASH)),
        "down": esc(str(data.get("down") or DASH)),
        "remaining": esc(str(data.get("remaining_human") or INF)),
        "expires": esc(str(data.get("expires_human") or INF)),
        "sub_url": esc(str(data.get("sub_url") or "")),
        "sub_clash": esc(str(data.get("sub_clash") or "")),
        "sub_singbox": esc(str(data.get("sub_singbox") or "")),
        "lang": lang, "dir": "rtl" if lang == "fa" else "ltr",
        "theme": esc(str(data.get("theme") or "dark-green")),
        "style": esc(str(data.get("ui_style") or "solid")),
        "qr": data.get("qr_svg") or "",
    }
    if tid == "bento":
        tags = _tags_html(t, esc, data, "bn-tile", "bn-k", "bn-v")
        cards = _cards_html(t, esc, clients, "bn-tile", wide=True)
    elif tid == "terminal":
        tags = ""
        cards = _cards_html(t, esc, clients, "tm-box")
    else:
        tags = _tags_html(t, esc, data)
        cards = _cards_html(t, esc, clients)
    return Template(raw).safe_substitute({**shared, **_label_map(t), "tags": tags, "cards": cards})



# ---------------------------------------------------------------- tiny i18n
_FA = {
    "secureSub": "مدیریت امن ویپیان", "brandSub": "مدیریت ویپیان",
    "signIn": "ورود", "user": "نام کاربری", "password": "رمز عبور",
    "changeAfter": "بعد از ورود رمز را عوض کنید",
    "running": "فعال", "copy": "کپی", "copied": "کپی شد",
    "copySub": "کپی سابسکریپشن", "clashSub": "سابسکریپشن کلش",
    "singboxSub": "سابسکریپشن سینگ‌باکس", "genericSub": "عمومی / base64",
    "used": "مصرف", "remaining": "باقیمانده", "expires": "انقضا", "upload": "آپلود", "download": "دانلود",
    "protocol": "پروتکل", "clients": "کاربران", "configNodes": "تعداد کانفیگ",
    "noClients": "کاربری وجود ندارد", "subEmptyHint": "از پنل یک کاربر به این اینباند اضافه کنید.",
    "subFooter": "این صفحه مخصوص این اینباند است",
}
_EN = {
    "secureSub": "Secure VPN management", "brandSub": "VPN MANAGEMENT",
    "signIn": "Sign in", "user": "Username", "password": "Password",
    "changeAfter": "change the password after the first login",
    "running": "Running", "copy": "Copy", "copied": "Copied",
    "copySub": "Copy subscription", "clashSub": "Clash subscription",
    "singboxSub": "sing-box subscription", "genericSub": "Generic / base64",
    "used": "Used", "remaining": "Remaining", "expires": "Expires", "upload": "Upload", "download": "Download",
    "protocol": "Protocol", "clients": "Clients", "configNodes": "Configs",
    "noClients": "No clients", "subEmptyHint": "Add a client to this inbound from the panel.",
    "subFooter": "This page belongs to this inbound",
}


def _T(lang):
    table = _FA if lang == "fa" else _EN

    def t(key):
        return table.get(key, _EN.get(key, key))

    return t
