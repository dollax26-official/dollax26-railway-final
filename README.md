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

## Traffic & ping
Upload and download are counted separately per client (real bytes from the relay) and shown in
Clients, on inbound cards, on the subscription page and in the client's `Subscription-Userinfo` header.
**Ping** is a server-side TCP connect (Clients/Inbounds → Ping). The Add-inbound form is now 10 inputs
with plain selects; SNI/Host/ALPN/Reality/gRPC extras were removed from the UI. Details: README_ENG.md §10.
## Appearance
Settings → Appearance is per admin and saved with **Save appearance**: language, style,
7 themes, 7 fonts, music, and a **background** (Default UI, three shipped wallpapers,
or your own private upload with darken/blur and an on/off switch). Panel-name field and
the inbound sub-link buttons were removed. Details: README_ENG.md §11.

## Bundled protocol cores (Docker)

The image installs two engines so every protocol the panel offers has a real implementation.
Both downloads are **non-fatal**: without network at build time the image still builds and the
panel falls back to its built-in VLESS/Trojan-over-WebSocket relay.

| Engine | Version | Serves | Notes |
|---|---|---|---|
| **Xray-core** | `v26.3.27` | VLESS · VMess · Trojan · Shadowsocks, over WebSocket / XHTTP / gRPC / HTTPUpgrade / TCP+header | Driven automatically. The panel stays the only public port and bridges each connection into a local inbound on `127.0.0.1:10000+i`, so quotas, connection/IP limits and per-client accounting keep working. |
| **sing-box** | `1.14.1` | Hysteria2 · TUIC · ShadowTLS (QUIC/UDP family) | Railway exposes TCP only, so these inbounds become reachable when the same image runs on a host that allows UDP. The panel generates their links/configs either way. |

Flow for a non-WebSocket inbound:

```
client ──wss://<railway-domain>/<path>──▶ panel (quotas · IP/conn limits · traffic)
                                              │  bridge
                                              ▼
                                   Xray-core 127.0.0.1:10000+i  ──▶ freedom ──▶ internet
```

Environment knobs: `XRAY_MODE` (`auto` | `on` | `off`, default `auto`), `XRAY_BIN`,
`XRAY_BASE_PORT` (10000), `SINGBOX_MODE`, `SINGBOX_BASE_PORT` (11000).
Status and restart live in Settings → **Xray-core** (`GET /api/xray/status`, `POST /api/xray/restart`, owner only).

**WireGuard** cannot run in a Railway container (it needs a TUN device + `NET_ADMIN`), so the
panel generates standard peer `.conf` files (private key derived from the client UUID, so it is
stable) for a WireGuard endpoint you host; the server public key and peer address are fields on
the inbound.

## Per-admin music

Settings → Music lets each admin upload their own tracks (mp3, ogg, wav, m4a, webm, flac, ≤ 9 MB).
Tracks are stored per admin in the `tracks` table and streamed from `/api/me/tracks/<id>/audio`,
so they stay in the account and never need re-uploading. The chosen track is part of the admin's
own preferences (`music_track`), and `default` means the bundled panel track.

## Settings apply on Save

Every control in Settings (language, theme, interface style, font, music + track, background and
its dim/blur/enable) edits a local **draft**. The panel's look changes and the preference is
persisted only when **Save appearance** is pressed — the button reports `✓ Saved`, and an
"unsaved changes" badge marks the draft until then. Panel settings (base URL, port) and the
Xray-core controls keep their own explicit Save/restart buttons.
