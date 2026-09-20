# Dollax Panel — Railway edition

A complete FastAPI + SQLite **Python port of the Cloudflare Worker VPN panel**, ready for
[Railway](https://railway.com). Same dark UI as the Worker, same job — but split into normal Python
files and using one public HTTPS port (**no TCP proxy**, everything rides `wss://` paths).

**Guides:** [README_ENG.md](README_ENG.md) · [README_FA.md](README_FA.md)

```
main.py       FastAPI app: auth, /api/*, subscriptions, graphical sub page, relay entry
db.py         SQLite storage + migrations (replaces Cloudflare D1)
protocol.py   links / Clash / sing-box / Xray bridge bundle + wire parsing
relay.py      the proxy: WebSocket → TCP with usage accounting and quotas
pages.py      login, dashboard, per-inbound graphical subscription page
static/       style.css (Worker dark theme, 7 themes) · app.js (whole UI) · lost-soul.mp3
Dockerfile · railway.json · .env.example · requirements.txt · README*.md
```

**UI** (ported from the Worker): Overview · Inbounds · Clients · Logs · Admins · Settings — with the
فارسی/EN switch, 7 themes, solid/glass style and optional background music, all **per admin**.
No Outbounds page, no Clean-IPs page.

**Inbounds** use a Vodiwalker-style 5-step builder (protocol → transport → security → endpoint →
limits). Every inbound carries its own credential, so **it works with zero clients**, and it has its
own **graphical subscription page** at `/info/<token>` with a usage donut and a real QR code.

**Clients** are managed under a selected inbound; **Logs** record the admin and the IP of every
sign-in; **panel settings are owner-only** while each admin keeps their own appearance.

## Deploy

```bash
railway up            # or push to GitHub
```

1. Volume mounted at **`/data`**
2. Variables: `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `SECRET_KEY`, `PUBLIC_BASE_URL`, `DATA_DIR=/data`
3. Generate Domain (TLS automatic) → open `/health`, then `/login` (`dollax26 / dollax26`)

## Local

```bash
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

**Natively served:** VLESS/WS + Trojan/WS.
**Needs the Xray bridge bundle** (Settings → Xray bridge): VMess, Shadowsocks, Reality, UDP.

Verified: `py_compile` clean, `node --check app.js` clean, **67/67** in-process end-to-end checks
(incl. real VLESS + Trojan relay against a TCP echo server) and **33/33** live checks against a running
uvicorn (sub page donut + QR, per-admin prefs, owner-only settings, login IP logged).

## Deploy crashed?
The app prints `[dollax] …` diagnostics before it serves — read those first (Railway → Deployments → View Logs). Common causes: no volume mounted while `DATA_DIR=/data`, a start command that is not `python main.py`, or an empty `SECRET_KEY` (optional — it only drops logins on restart). Full table: README_ENG.md §8.

## Which port?
Railway injects `$PORT` (8080 by convention) and forwards your domain to it — the app reads it
itself, so there is nothing to configure. The domain's **target port** in Settings → Networking
must equal `$PORT`. Public HTTPS is 443; inbounds should use port **443** too (paths separate them).
Details: README_ENG.md §9.
