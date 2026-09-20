# Dollax Panel — Railway edition (README_EMG.md)

> English guide. `README_EMG.md` is the filename the goal brief asks for; `README_ENG.md` ships the same document.

A complete FastAPI + SQLite **Python port of the Cloudflare Worker VPN panel**, made to run on
[Railway](https://railway.com). Same panel, same look (the Worker's dark theme system), same job:
manage inbounds, clients, quotas and subscriptions — but as normal Python files.

> **No TCP proxy.** Railway exposes one public HTTPS port, so every inbound rides `wss://` on that
> port and is selected by its **path**. No second listener, no `tcp_relay`, nothing else to open.

---

## 1. Files (only what Railway needs)

| File | Purpose |
|---|---|
| `main.py` | FastAPI app: auth, all `/api/*` routes, subscriptions, the graphical sub page, WebSocket relay entry |
| `db.py` | SQLite storage (schema, self-migrations, usage counters, admins) — replaces Cloudflare D1 |
| `protocol.py` | VLESS/VMess/Trojan/SS links, Clash, sing-box, Xray bridge bundle, wire parsing |
| `relay.py` | The proxy: terminates the WebSocket, opens TCP, pipes bytes, counts usage |
| `pages.py` | Server-rendered shells: login, dashboard, **per-inbound graphical subscription page** |
| `static/style.css` | The Worker's dark design system (7 themes, solid/glass, RTL) |
| `static/app.js` | Whole UI: Overview · Inbounds · Clients · Logs · Admins · Settings + EN/FA + music |
| `static/lost-soul.mp3` | Optional background music (per-admin toggle) |
| `Dockerfile`, `railway.json` | Railway build/deploy config |
| `.env.example` | Every environment variable |
| `requirements.txt` | Runtime dependencies |
| `README.md` / `README_ENG.md` / `README_FA.md` | This documentation |

---

## 2. What the panel does

### The look
Ported 1:1 from the Worker dashboard: dark glow background, gradient panels, the same 7 themes
(**dark-green** default, dark-cyan, dark-blue, green, cyan, blue, orange), a **solid/glass** interface
style, Inter + Vazirmatn fonts, and a **فارسی/EN** switch with full RTL support.

### Overview
Stat cards (inbounds, clients, active, traffic), a **Diagnostics** checklist with concrete fixes, and
the recent activity feed (with the admin IP).

### Inbounds — the builder
**Inbounds → “+ Add inbound”** opens a 5-step builder, closely modelled on the Vodiwalker panel:

1. **Base protocol** — VLESS · VMess · Trojan · Shadowsocks
2. **Transport** — WebSocket · XHTTP · gRPC · TCP
3. **Security** — TLS · Reality · None
4. **Endpoint & advanced** — only the fields that apply: name, address, port, fingerprint, path/host,
   XHTTP mode, gRPC service, header type, flow, SNI, ALPN, allow-insecure, fragment, Reality keys
5. **Limits & rotation** — traffic GB, validity days / exact expiry, client limit, IP limit,
   connection limit, **configs per client**, speed, note

A live summary strip and a sample link update as you type. The list supports search, protocol filter,
select-all, bulk enable/disable/delete, per-inbound **Edit**, **Config**, **Clients**, **Open
subscription page**, **New secret** (rotates path + all UUIDs) and **Delete**.

**An inbound needs no client.** Every inbound carries its own credential, so the moment you create it
you already have a working config — add clients only when you want separate users.

### Clients — under an inbound
The Clients page works like Vodiwalker's client manager: pick an inbound, see its details (address,
path, subscription link, “open subscription page”) and manage that inbound's clients — add, enable /
disable, copy config or subscription, regenerate the UUID, reset usage, delete. Quotas, expiry, IP and
connection limits are enforced at connect time.

### Logs
Every sign-in records **the admin and the IP address** it came from (behind Railway's proxy the real
client IP is read from `X-Forwarded-For`). Inbound / client / settings / admin changes are recorded too.

### Settings — per admin
* **Appearance** — language, theme, interface style, background music + volume. These are stored on
  **your own admin record**, so two admins can use different languages/themes and never see each
  other's changes.
* **Account** — change your own password.
* **Panel** (panel name, public base URL, default port) and **Xray bridge** — **owner only**. A
  non-owner gets a clear notice instead of the fields, and the API answers `403`.
* **Admins** (owner only) — create/disable/delete admins; the last owner can never be removed.

### Graphical subscription page (per inbound)
Opening an inbound's subscription URL in a browser shows its **own** page — themed to your
preferences, RTL when Farsi is selected — with:

* the inbound identity badges (protocol / transport / security) and endpoint,
* a **usage donut** and the numbers behind it,
* a live **QR code** (real SVG, generated server-side) for the subscription URL,
* copy buttons for the generic / Clash / sing-box subscription URLs,
* one card per client (status, traffic bar, expiry) with its own config lines and copy button.

`/sub/<token>` (import in a client) and `/info/<token>` (this page) are the same token — client tokens
show just that client, inbound tokens show the inbound node plus every client.

### Not served natively
VLESS-WS and Trojan-WS are handled by this app. **VMess, Shadowsocks, Reality and UDP** are not — the
panel still generates their configs and a ready Xray bridge bundle
(**Settings → Xray bridge → Generate bundle**: `config.json` + Caddyfile + steps).

---

## 3. Deploy on Railway

```bash
npm i -g @railway/cli
railway login
cd dollax-railway
railway init
railway up
```

Then in the Railway dashboard:

1. **Volume** → mount path **`/data`** (keeps `dollax.db` across deploys).
2. **Variables**:
   ```
   ADMIN_USERNAME=dollax26
   ADMIN_PASSWORD=*** pick>
   SECRET_KEY=*** -c "import secrets;print(secrets.token_urlsafe(48))">
   PUBLIC_BASE_URL=https://<your-domain>
   DATA_DIR=/data
   ```
3. **Settings → Networking → Generate Domain** (TLS is automatic).
4. Open `https://<your-domain>/health` → `{"ok":true,...}`.
5. Sign in at `/login` with `dollax26 / dollax26`, then change the password in **Settings → Account**.

### Local run

```bash
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000     # login: dollax26 / dollax26
```

---

## 4. Where to change things

| Want to change | File |
|---|---|
| Colours, spacing, radii, themes | `static/style.css` (`:root` and the `html[data-theme="…"]` blocks) |
| Any UI text / translations | `static/app.js` → the `I18N` object (`en` and `fa`) |
| Nav items, pages, builder fields | `static/app.js` (`navList`, `openBuilder`, `pageClients`, `pageSettings`) |
| Subscription page layout | `pages.py` → `subscription_page()` |
| Login / dashboard shell | `pages.py` → `login_html()`, `dashboard_html()` |
| API routes, quotas, relay rules | `main.py`, `relay.py` |
| Table columns / migrations | `db.py` (`SCHEMA`, `MIGRATIONS`) |
| Deploy parameters | `railway.json`, `Dockerfile`, `.env.example` |

---

## 5. Quality coverage

* **Responsive** — grids collapse at 1080/780/560 px, the sidebar and tables scroll, the builder is a
  modal that fits phones.
* **RTL** — the whole shell flips when Farsi is selected (`dir="rtl"`), including the sidebar border
  and notes.
* **States** — empty states for every list (“No inbounds yet”, “No clients”, “No logs”), loading
  spinners for diagnostics/logs, error toasts for every failed request, `disabled`/hover/active styles
  on all buttons.
* **Validation** — inbound name required, path normalised (leading `/`, no spaces/`?`/`#`), duplicate
  path → 409, port clamped 1–65535, numeric limits clamped; credential fields never silently reset.
* **Accessibility / keyboard** — `Esc` closes modals, focus outlines follow the accent colour, buttons
  are real `<button>`s, labels wrap every input, `prefers-reduced-motion` is honoured.
* **Security** — scrypt password hashing, signed session cookie, per-role API guards (`403` for
  non-owners), quotas/expiry checked before the tunnel opens.

---

## 6. Verification done

* `python -m py_compile` on every module, `node --check static/app.js` — clean.
* **67/67** end-to-end checks in-process (auth, inbound/client CRUD, base64/Clash/sing-box
  subscriptions, real VLESS **and** Trojan relay against a TCP echo server, usage accounting,
  inbound-with-no-clients relay, graphical page render, per-user prefs, admin role isolation,
  last-owner protection).
* **33/33** live checks against a running `uvicorn` server (health, login, inbound self-link, sub page
  contains donut + QR `<svg>` + copy buttons, `/sub` with zero clients, Clash, login IP in the log,
  prefs persistence, a second admin sees their own empty prefs and gets `403` on panel settings,
  static assets + the music file served).

These scripts were removed in the final Railway-only file set; the commands above reproduce the
results.

---

## 7. Troubleshooting

| Symptom | Fix |
|---|---|
| Healthcheck fails | Deploy logs; the app binds `0.0.0.0:$PORT` (already in `railway.json`) |
| Data resets on deploy | No volume — mount one at `/data` |
| Links contain `127.0.0.1` | Settings → Public base URL → your domain → Save (owner) |
| Client connects, no browsing | Use a `443/TLS` node, enable Fragment; SNI must equal your domain |
| VMess/SS never connects | Expected — they need the Xray bridge bundle |
| An admin can't change panel settings | By design: panel settings are owner-only; everyone can change their own Appearance |
| Sub page shows no client cards | That's fine — the inbound's own node is shown above them |

## 8. If the deploy crashes

The app prints bootstrap diagnostics **before** it serves anything — read those first
(Railway → your service → **Deployments → View Logs**, or `railway logs`):

```
[dollax] data dir: /data
[dollax] Dollax Panel 2026.09.19-r1 starting on 0.0.0.0:8080
[dollax] SECRET_KEY from env: yes
[dollax] owner seed: dollax26 / env password
```

| Log line / symptom | Cause | Fix |
|---|---|---|
| `can't open file 'main.py'` / “module not found” | the whole folder wasn't uploaded | deploy the folder, not single files |
| container exits right after startup | the start command runs something else | keep `"startCommand": "python main.py"` (railway.json) or Docker `CMD ["python","main.py"]` |
| `data dir '/data' unusable (PermissionError…)` then “using the TEMPORARY data dir” | `DATA_DIR=/data` with no volume mounted | add a **Volume** mounted at `/data`, or uncomment/remove `DATA_DIR` |
| `Address already in use` | a second replica or an old process holds the port | keep 1 replica — the image binds `$PORT` itself |
| Railway healthcheck fails but logs look fine | the app is still installing/starting | healthcheck timeout is 60 s in `railway.json`; check `/health` manually |
| everyone is logged out after every restart | `SECRET_KEY` is empty | set it (below) |
| `dollax26 / dollax26` rejected | `ADMIN_PASSWORD` differs, or an older database | the owner is seeded **once** — set `ADMIN_PASSWORD` before the first deploy, or delete `/data/dollax.db` and redeploy |

### How to get a SECRET_KEY

It is **optional** — if it is empty the app generates a random one at every boot, which only
means sessions (logins) are dropped on each restart. Any long random string works:

```bash
python -c "import secrets;print(secrets.token_urlsafe(48))"
```
```powershell
-join ((48..57)+(65..90)+(97..122) | Get-Random -Count 48 | % {[char]$_})
```
```bash
openssl rand -base64 48
```

No Python locally? Any 40+ character random string from a password manager is fine.
Then: Railway → your service → **Variables** → **New Variable** → name `SECRET_KEY`, paste the
value → **Deploy**. (While you are there, set `ADMIN_PASSWORD` and `PUBLIC_BASE_URL` too.)

## 9. Which port does the panel run on?

**You never pick a port on Railway — Railway picks it for you.** It injects a `PORT`
environment variable (8080 by convention) and forwards your public domain to exactly that
port. The app reads `$PORT` itself, so it always matches:

```
python main.py                    # binds 0.0.0.0:$PORT, falls back to 8080
```

Checklist:

1. **Variables** — nothing to do. `PORT` is injected. (If you *want* another number, set
   `PORT` yourself, e.g. `8080`.)
2. **Settings → Networking → Public Networking** — the generated domain has a **target port**.
   It must equal `$PORT` (8080 unless you changed it). If Railway asks and you leave the wrong
   number there, the site returns *"Application failed to respond"* even though the app is fine.
3. **Healthcheck** — `railway.json` already probes `/health` on that same port.
4. **Local runs** — `python main.py` uses 8080, or `PORT=3000 python main.py`, or
   `uvicorn main:app --port 8000` (uvicorn's own default). Then open `http://127.0.0.1:<port>`.

| Item | Port |
|---|---|
| Panel (Railway) | whatever `$PORT` is — **8080** by default |
| Panel (local) | 8080 via `python main.py`, else the `--port` you pass |
| Public HTTPS | **443** (Railway's edge terminates TLS) |
| Inbound `port` in the builder | **443** — see below |

### The inbound "Port" field is not a listening port

In **Inbounds → Port** you are choosing what ends up inside the client link
(`vless://…@your-domain:443`). Railway exposes **one** public HTTPS port, so:

* use **443** (TLS) for every inbound — the WebSocket **path** is what separates them;
* 2053 / 2083 / 2096 / 8443 etc. only work on Cloudflare's edge (the Worker build), not here;
* the only way to open extra raw TCP ports on Railway is its **TCP Proxy** feature, and this app
  doesn't listen on extras — one uvicorn process, one port, many paths.

---

_Document version: 2026.09.20 · shipped with the Railway build (Dollax Panel)._
