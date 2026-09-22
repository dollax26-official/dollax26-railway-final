"""
Dollax Panel — storage layer.

Ported from the Cloudflare Worker worker.js (single D1 database) to SQLite so the
same panel can run on Railway / any VPS. Every helper here has a counterpart in
the Worker; see README.md "Port map" for the mapping.

Deliberately NOT ported: outbounds. In the Worker an inbound pointed at an
outbound (direct / socks5 / http) that decided the exit. The Railway build is the
endpoint itself (it terminates the WebSocket and relays TCP), so the whole
outbound concept is removed — see README.md.
"""
import os
import json
import sys
import time
import sqlite3
import secrets
import hashlib
import hmac
import tempfile
import traceback
import threading
from pathlib import Path
from datetime import datetime, timezone, timedelta

import protocol

JOURNAL_ACTIVE = ""

# ---------------------------------------------------------------- paths / conn
# The Worker used a D1 binding; here we need a writable directory. Never crash on
# this: if the configured path is not writable (e.g. DATA_DIR=/data without a
# volume, or /data on Windows), fall back and say so loudly in the logs.
def _pick_data_dir() -> Path:
    fallback = Path(tempfile.gettempdir()) / "dollax"
    for raw in (os.getenv("RAILWAY_VOLUME_MOUNT_PATH"), os.getenv("DATA_DIR"), "./data", str(fallback)):
        if not raw:
            continue
        p = Path(raw).expanduser()
        try:
            p.mkdir(parents=True, exist_ok=True)
            probe = p / ".write-test"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
        except Exception as exc:  # noqa: BLE001
            print(f"[dollax] data dir {raw!r} unusable ({exc.__class__.__name__}: {exc})", flush=True)
            continue
        if p == fallback:
            print(f"[dollax] WARNING: using the TEMPORARY data dir {p}. "
                  "Set DATA_DIR to a writable path (on Railway: mount a volume at /data) "
                  "or your data is lost on every restart.", flush=True)
        else:
            print(f"[dollax] data dir: {p}", flush=True)
        return p
    raise RuntimeError("Dollax: no writable data directory found")


DATA_DIR = _pick_data_dir()
DB_PATH = DATA_DIR / "dollax.db"

_write_lock = threading.RLock()


def conn():
    """Open the DB. Never let a filesystem quirk crash the app.

    WAL is faster but needs shared-memory support; some mounted volumes / network
    filesystems reject it ("database is locked", "disk I/O error"). We try, then
    fall back to DELETE. Force it with SQLITE_JOURNAL_MODE=delete if needed.
    """
    c = sqlite3.connect(DB_PATH, timeout=30)
    c.row_factory = sqlite3.Row
    wanted = (os.getenv("SQLITE_JOURNAL_MODE") or "wal").strip().lower()
    if wanted not in ("wal", "delete", "truncate", "persist", "memory", "off"):
        wanted = "wal"
    try:
        row = c.execute(f"PRAGMA journal_mode={wanted}").fetchone()
        global JOURNAL_ACTIVE
        JOURNAL_ACTIVE = (row[0] if row else wanted) or wanted
    except Exception as exc:  # noqa: BLE001
        print(f"[dollax] journal_mode={wanted} rejected here ({exc.__class__.__name__}: {exc}); "
              "falling back to DELETE", flush=True)
        try:
            # use a fresh handle: the failed statement above can leave the original
            # one mid-flight, and changing journal mode then needs an exclusive lock
            probe = sqlite3.connect(DB_PATH, timeout=30)
            try:
                row = probe.execute("PRAGMA journal_mode=DELETE").fetchone()
                JOURNAL_ACTIVE = (row[0] if row else "delete") or "delete"
            finally:
                probe.close()
        except Exception as exc2:  # noqa: BLE001
            print(f"[dollax] journal_mode=DELETE also refused ({exc2.__class__.__name__}: {exc2}); "
                  "keeping the filesystem default (the panel still works)", flush=True)
            JOURNAL_ACTIVE = "default"
    for pragma in ("PRAGMA busy_timeout=8000", "PRAGMA foreign_keys=ON"):
        try:
            c.execute(pragma)
        except Exception:  # noqa: BLE001
            pass
    return c


def now():
    return datetime.now(timezone.utc).isoformat()


def enc(v):
    """SQLite only accepts scalars: encode lists/dicts/bools."""
    if isinstance(v, (list, tuple, set, dict)):
        return json.dumps(list(v) if isinstance(v, (list, tuple, set)) else v)
    if isinstance(v, bool):
        return 1 if v else 0
    return v


# ---------------------------------------------------------------- passwords
def hash_password(pw: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(pw.encode(), salt=salt, n=2 ** 14, r=8, p=1)
    return salt.hex() + "$" + digest.hex()


def verify_password(pw: str, stored: str) -> bool:
    try:
        salt, digest = str(stored).split("$", 1)
        got = hashlib.scrypt(pw.encode(), salt=bytes.fromhex(salt), n=2 ** 14, r=8, p=1).hex()
        return hmac.compare_digest(got, digest)
    except Exception:
        return False


# ---------------------------------------------------------------- schema
SCHEMA = """
CREATE TABLE IF NOT EXISTS admins(
  username TEXT PRIMARY KEY,
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'admin',
  enabled INTEGER NOT NULL DEFAULT 1,
  prefs_json TEXT NOT NULL DEFAULT '{}',
  created TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS inbounds(
  id TEXT PRIMARY KEY,
  uuid TEXT NOT NULL DEFAULT '',
  name TEXT NOT NULL,
  protocol TEXT NOT NULL DEFAULT 'vless',
  network TEXT NOT NULL DEFAULT 'ws',
  security TEXT NOT NULL DEFAULT 'tls',
  address TEXT NOT NULL DEFAULT '',
  port INTEGER NOT NULL DEFAULT 443,
  path TEXT NOT NULL UNIQUE,
  host_header TEXT NOT NULL DEFAULT '',
  sni TEXT NOT NULL DEFAULT '',
  alpn TEXT NOT NULL DEFAULT 'http/1.1',
  fingerprint TEXT NOT NULL DEFAULT 'chrome',
  flow TEXT NOT NULL DEFAULT '',
  grpc_service_name TEXT NOT NULL DEFAULT '',
  grpc_mode TEXT NOT NULL DEFAULT 'gun',
  xhttp_mode TEXT NOT NULL DEFAULT 'packet-up',
  header_type TEXT NOT NULL DEFAULT 'none',
  allow_insecure INTEGER NOT NULL DEFAULT 0,
  reality_public_key TEXT NOT NULL DEFAULT '',
  reality_short_id TEXT NOT NULL DEFAULT '',
  reality_spider_x TEXT NOT NULL DEFAULT '/',
  ss_method TEXT NOT NULL DEFAULT 'chacha20-ietf-poly1305',
  ss_password TEXT NOT NULL DEFAULT '',
  wg_public_key TEXT NOT NULL DEFAULT '',
  wg_address TEXT NOT NULL DEFAULT '',
  fragment TEXT NOT NULL DEFAULT '',
  limit_bytes INTEGER NOT NULL DEFAULT 0,
  expires_at TEXT NOT NULL DEFAULT '',
  ip_limit INTEGER NOT NULL DEFAULT 0,
  connection_limit INTEGER NOT NULL DEFAULT 0,
  client_limit INTEGER NOT NULL DEFAULT 0,
  config_count INTEGER NOT NULL DEFAULT 1,
  clean_ips TEXT NOT NULL DEFAULT '[]',
  note TEXT NOT NULL DEFAULT '',
  enabled INTEGER NOT NULL DEFAULT 1,
  used_bytes INTEGER NOT NULL DEFAULT 0,
  up_bytes INTEGER NOT NULL DEFAULT 0,
  down_bytes INTEGER NOT NULL DEFAULT 0,
  sub_token TEXT NOT NULL DEFAULT '',
  created TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS clients(
  id TEXT PRIMARY KEY,
  inbound_id TEXT NOT NULL,
  name TEXT NOT NULL,
  uuid TEXT NOT NULL UNIQUE,
  limit_bytes INTEGER NOT NULL DEFAULT 0,
  expires_at TEXT NOT NULL DEFAULT '',
  ip_limit INTEGER NOT NULL DEFAULT 0,
  connection_limit INTEGER NOT NULL DEFAULT 0,
  speed_limit_mbps REAL NOT NULL DEFAULT 0,
  clean_ips TEXT NOT NULL DEFAULT '[]',
  note TEXT NOT NULL DEFAULT '',
  enabled INTEGER NOT NULL DEFAULT 1,
  used_bytes INTEGER NOT NULL DEFAULT 0,
  up_bytes INTEGER NOT NULL DEFAULT 0,
  down_bytes INTEGER NOT NULL DEFAULT 0,
  sub_token TEXT NOT NULL DEFAULT '',
  last_seen TEXT NOT NULL DEFAULT '',
  last_config_at TEXT NOT NULL DEFAULT '',
  sub_fetches INTEGER NOT NULL DEFAULT 0,
  created_by TEXT NOT NULL DEFAULT '',
  extra_inbounds TEXT NOT NULL DEFAULT '[]',
  config_count INTEGER NOT NULL DEFAULT 2,
  created TEXT NOT NULL,
  FOREIGN KEY(inbound_id) REFERENCES inbounds(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS clean_ips(
  id TEXT PRIMARY KEY,
  address TEXT NOT NULL UNIQUE,
  label TEXT NOT NULL DEFAULT '',
  rtt_ms INTEGER NOT NULL DEFAULT 0,
  loss_pct REAL NOT NULL DEFAULT 0,
  note TEXT NOT NULL DEFAULT '',
  created TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS settings(
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS admin_assets(
  username TEXT NOT NULL,
  kind TEXT NOT NULL,
  mime TEXT NOT NULL DEFAULT 'image/jpeg',
  bytes BLOB NOT NULL,
  updated TEXT NOT NULL,
  PRIMARY KEY(username, kind)
);
CREATE TABLE IF NOT EXISTS tracks(
  id TEXT PRIMARY KEY,
  username TEXT NOT NULL,
  name TEXT NOT NULL DEFAULT '',
  mime TEXT NOT NULL DEFAULT 'audio/mpeg',
  bytes BLOB NOT NULL,
  size INTEGER NOT NULL DEFAULT 0,
  created TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS hosts(
  id TEXT PRIMARY KEY,
  address TEXT NOT NULL,
  label TEXT NOT NULL DEFAULT '',
  remark TEXT NOT NULL DEFAULT '',
  enabled INTEGER NOT NULL DEFAULT 1,
  created_by TEXT NOT NULL DEFAULT '',
  created TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS client_links(
  client_id TEXT NOT NULL,
  linked_id TEXT NOT NULL,
  created TEXT NOT NULL,
  PRIMARY KEY(client_id, linked_id)
);
CREATE TABLE IF NOT EXISTS nodes(
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL DEFAULT '',
  url TEXT NOT NULL DEFAULT '',
  token TEXT NOT NULL DEFAULT '',
  location TEXT NOT NULL DEFAULT '',
  flag TEXT NOT NULL DEFAULT '',
  enabled INTEGER NOT NULL DEFAULT 1,
  status TEXT NOT NULL DEFAULT '',
  snapshot TEXT NOT NULL DEFAULT '[]',
  last_seen TEXT NOT NULL DEFAULT '',
  created_by TEXT NOT NULL DEFAULT '',
  created TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS activity(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  username TEXT NOT NULL DEFAULT '',
  ip TEXT NOT NULL DEFAULT '',
  action TEXT NOT NULL,
  detail TEXT NOT NULL DEFAULT ''
);
"""

# columns added after the first Dollax schema was published (upgrade path)
MIGRATIONS = [
    ("inbounds", "uuid", "TEXT NOT NULL DEFAULT ''"),
    ("inbounds", "up_bytes", "INTEGER NOT NULL DEFAULT 0"),
    ("inbounds", "down_bytes", "INTEGER NOT NULL DEFAULT 0"),
    ("clients", "up_bytes", "INTEGER NOT NULL DEFAULT 0"),
    ("clients", "down_bytes", "INTEGER NOT NULL DEFAULT 0"),
    ("activity", "ip", "TEXT NOT NULL DEFAULT ''"),
    ("inbounds", "network", "TEXT NOT NULL DEFAULT 'ws'"),
    ("inbounds", "security", "TEXT NOT NULL DEFAULT 'tls'"),
    ("inbounds", "address", "TEXT NOT NULL DEFAULT ''"),
    ("inbounds", "port", "INTEGER NOT NULL DEFAULT 443"),
    ("inbounds", "host_header", "TEXT NOT NULL DEFAULT ''"),
    ("inbounds", "sni", "TEXT NOT NULL DEFAULT ''"),
    ("inbounds", "alpn", "TEXT NOT NULL DEFAULT 'http/1.1'"),
    ("inbounds", "fingerprint", "TEXT NOT NULL DEFAULT 'chrome'"),
    ("inbounds", "flow", "TEXT NOT NULL DEFAULT ''"),
    ("inbounds", "grpc_service_name", "TEXT NOT NULL DEFAULT ''"),
    ("inbounds", "grpc_mode", "TEXT NOT NULL DEFAULT 'gun'"),
    ("inbounds", "xhttp_mode", "TEXT NOT NULL DEFAULT 'packet-up'"),
    ("inbounds", "header_type", "TEXT NOT NULL DEFAULT 'none'"),
    ("inbounds", "allow_insecure", "INTEGER NOT NULL DEFAULT 0"),
    ("inbounds", "reality_public_key", "TEXT NOT NULL DEFAULT ''"),
    ("inbounds", "reality_short_id", "TEXT NOT NULL DEFAULT ''"),
    ("inbounds", "reality_spider_x", "TEXT NOT NULL DEFAULT '/'"),
    ("inbounds", "ss_method", "TEXT NOT NULL DEFAULT 'chacha20-ietf-poly1305'"),
    ("inbounds", "ss_password", "TEXT NOT NULL DEFAULT ''"),
    ("inbounds", "reality_private_key", "TEXT NOT NULL DEFAULT ''"),
    ("inbounds", "reality_dest", "TEXT NOT NULL DEFAULT ''"),
    ("inbounds", "wg_public_key", "TEXT NOT NULL DEFAULT ''"),
    ("inbounds", "wg_address", "TEXT NOT NULL DEFAULT ''"),
    ("clients", "created_by", "TEXT NOT NULL DEFAULT ''"),
    ("clients", "extra_inbounds", "TEXT NOT NULL DEFAULT '[]'"),
    ("clients", "config_count", "INTEGER NOT NULL DEFAULT 2"),
    ("inbounds", "fragment", "TEXT NOT NULL DEFAULT ''"),
    ("inbounds", "limit_bytes", "INTEGER NOT NULL DEFAULT 0"),
    ("inbounds", "expires_at", "TEXT NOT NULL DEFAULT ''"),
    ("inbounds", "ip_limit", "INTEGER NOT NULL DEFAULT 0"),
    ("inbounds", "connection_limit", "INTEGER NOT NULL DEFAULT 0"),
    ("inbounds", "client_limit", "INTEGER NOT NULL DEFAULT 0"),
    ("inbounds", "config_count", "INTEGER NOT NULL DEFAULT 1"),
    ("inbounds", "clean_ips", "TEXT NOT NULL DEFAULT '[]'"),
    ("inbounds", "note", "TEXT NOT NULL DEFAULT ''"),
    ("inbounds", "used_bytes", "INTEGER NOT NULL DEFAULT 0"),
    ("inbounds", "sub_token", "TEXT NOT NULL DEFAULT ''"),
    ("clients", "limit_bytes", "INTEGER NOT NULL DEFAULT 0"),
    ("clients", "expires_at", "TEXT NOT NULL DEFAULT ''"),
    ("clients", "ip_limit", "INTEGER NOT NULL DEFAULT 0"),
    ("clients", "connection_limit", "INTEGER NOT NULL DEFAULT 0"),
    ("clients", "speed_limit_mbps", "REAL NOT NULL DEFAULT 0"),
    ("clients", "clean_ips", "TEXT NOT NULL DEFAULT '[]'"),
    ("clients", "note", "TEXT NOT NULL DEFAULT ''"),
    ("clients", "used_bytes", "INTEGER NOT NULL DEFAULT 0"),
    ("clients", "sub_token", "TEXT NOT NULL DEFAULT ''"),
    ("clients", "last_seen", "TEXT NOT NULL DEFAULT ''"),
    ("clients", "last_config_at", "TEXT NOT NULL DEFAULT ''"),
    ("clients", "sub_fetches", "INTEGER NOT NULL DEFAULT 0"),
]

# 12 Cloudflare edge addresses that answered from an Iranian (FRA-routed) line.
# Same list the Worker seeds (IRAN_CLEAN_IPS); re-applyable from the Clean IPs page.
IRAN_CLEAN_IPS = [
    "104.18.149.200", "104.21.4.186", "104.24.129.155", "162.159.241.179",
    "104.19.242.236", "104.18.104.34", "172.65.212.49", "104.17.25.193",
    "104.25.63.63", "162.159.206.6", "104.24.205.98", "104.21.91.142",
]

DEFAULT_SETTINGS = {
    "panel_name": "Dollax Panel",
    "public_base_url": os.getenv("PUBLIC_BASE_URL", ""),
    "default_port": "443",
    "xray_bridge_host": "",
    "xray_bridge_port": "8080",
}


def _columns(c, table):
    return {r[1] for r in c.execute(f"PRAGMA table_info({table})").fetchall()}


def _add_column(c, table, column, definition):
    if column not in _columns(c, table):
        c.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def db_status() -> dict:
    """Small health block so the Railway log / /health can show what is going on."""
    return {
        "path": str(DB_PATH),
        "dir": str(DATA_DIR),
        "journal": JOURNAL_ACTIVE or "?",
        "sqlite": sqlite3.sqlite_version,
        "writable": os.access(str(DATA_DIR), os.W_OK),
    }


def init_db():
    """Create/migrate the schema. If the configured directory fails (volume not
    writable, filesystem without WAL/shm support, locked file…) switch to the temp
    dir and keep serving instead of crash-looping."""
    global DATA_DIR, DB_PATH
    try:
        _init_db_once()
        print(f"[dollax] database ready: {DB_PATH} | journal={JOURNAL_ACTIVE} | sqlite={sqlite3.sqlite_version}",
              flush=True)
        return
    except Exception as exc:  # noqa: BLE001
        print(f"[dollax] FATAL-ish: database init failed on {DB_PATH} "
              f"({exc.__class__.__name__}: {exc})", flush=True)
        traceback.print_exc()

    alt_dir = Path(tempfile.gettempdir()) / "dollax"
    try:
        alt_dir.mkdir(parents=True, exist_ok=True)
        if Path(DB_PATH).parent == alt_dir:
            raise RuntimeError("already using the temporary directory")
        print(f"[dollax] WARNING: falling back to the TEMPORARY database at {alt_dir} — "
              "data will be lost on restart. Fix: mount a Railway volume and point DATA_DIR at it, "
              "or set SQLITE_JOURNAL_MODE=delete for filesystems without WAL support.", flush=True)
        DATA_DIR = alt_dir
        DB_PATH = alt_dir / "dollax.db"
        _init_db_once()
        print(f"[dollax] database ready (temporary): {DB_PATH} | journal={JOURNAL_ACTIVE}", flush=True)
    except Exception as exc2:  # noqa: BLE001
        print(f"[dollax] cannot initialise any database: {exc2.__class__.__name__}: {exc2}", flush=True)
        traceback.print_exc()
        raise


def _init_db_once():
    with _write_lock, conn() as c:
        c.executescript(SCHEMA)
        for table, col, definition in MIGRATIONS:
            _add_column(c, table, col, definition)
        for k, v in DEFAULT_SETTINGS.items():
            c.execute("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)", (k, v))

        admin = (os.getenv("ADMIN_USERNAME") or "dollax26").strip() or "dollax26"
        pw = os.getenv("ADMIN_PASSWORD") or "dollax26"
        if not c.execute("SELECT username FROM admins WHERE username=?", (admin,)).fetchone():
            c.execute(
                "INSERT INTO admins(username,password_hash,role,enabled,prefs_json,created) VALUES(?,?,?,?,?,?)",
                (admin, hash_password(pw), "owner", 1, "{}", now()),
            )
        # backfill tokens + per-inbound credentials for rows created before those columns
        for r in c.execute("SELECT id FROM inbounds WHERE sub_token='' OR sub_token IS NULL").fetchall():
            c.execute("UPDATE inbounds SET sub_token=? WHERE id=?", (protocol.new_token(16), r["id"]))
        for r in c.execute("SELECT id FROM inbounds WHERE uuid='' OR uuid IS NULL").fetchall():
            c.execute("UPDATE inbounds SET uuid=? WHERE id=?", (protocol.new_uuid(), r["id"]))
        for r in c.execute("SELECT id FROM clients WHERE sub_token='' OR sub_token IS NULL").fetchall():
            c.execute("UPDATE clients SET sub_token=? WHERE id=?", (protocol.new_token(16), r["id"]))
        c.commit()


# ---------------------------------------------------------------- settings
def setting(key, default=""):
    with conn() as c:
        r = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return r["value"] if r else default


def all_settings():
    with conn() as c:
        return {r["key"]: r["value"] for r in c.execute("SELECT key,value FROM settings").fetchall()}


def set_setting(key, value):
    with _write_lock, conn() as c:
        c.execute(
            "INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, str(value)),
        )
        c.commit()


# ---------------------------------------------------------------- admins
def get_admin(username):
    with conn() as c:
        return c.execute("SELECT * FROM admins WHERE username=?", (username,)).fetchone()


def set_password(username, password):
    with _write_lock, conn() as c:
        c.execute("UPDATE admins SET password_hash=? WHERE username=?", (hash_password(password), username))
        c.commit()


def set_prefs(username, prefs: dict):
    with _write_lock, conn() as c:
        c.execute("UPDATE admins SET prefs_json=? WHERE username=?", (json.dumps(prefs), username))
        c.commit()


def get_prefs(username) -> dict:
    row = get_admin(username)
    try:
        return json.loads(row["prefs_json"]) if row and row["prefs_json"] else {}
    except Exception:
        return {}


def list_admins():
    with conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT username, role, enabled, created FROM admins ORDER BY (role='owner') DESC, username").fetchall()]


def create_admin(username, password, role="admin"):
    with _write_lock, conn() as c:
        c.execute("INSERT INTO admins(username,password_hash,role,enabled,prefs_json,created) VALUES(?,?,?,?,?,?)",
                  (username, hash_password(password), "owner" if role == "owner" else "admin", 1, "{}", now()))
        c.commit()


def update_admin(username, role=None, enabled=None, password=None):
    with _write_lock, conn() as c:
        if role is not None:
            c.execute("UPDATE admins SET role=? WHERE username=?", ("owner" if role == "owner" else "admin", username))
        if enabled is not None:
            c.execute("UPDATE admins SET enabled=? WHERE username=?", (1 if enabled else 0, username))
        if password:
            c.execute("UPDATE admins SET password_hash=? WHERE username=?", (hash_password(password), username))
        c.commit()


def delete_admin(username) -> bool:
    with _write_lock, conn() as c:
        cur = c.execute("DELETE FROM admins WHERE username=?", (username,))
        c.commit()
        return cur.rowcount > 0


def owner_count() -> int:
    with conn() as c:
        r = c.execute("SELECT COUNT(*) n FROM admins WHERE role='owner' AND enabled=1").fetchone()
        return int(r["n"] if r else 0)


# ---------------------------------------------------------------- per-user assets
# e.g. a custom dashboard background: stored per admin, never shared between users.
def set_asset(username, kind, data: bytes, mime="image/jpeg"):
    with _write_lock, conn() as c:
        c.execute(
            "INSERT INTO admin_assets(username,kind,mime,bytes,updated) VALUES(?,?,?,?,?) "
            "ON CONFLICT(username,kind) DO UPDATE SET mime=excluded.mime, bytes=excluded.bytes, "
            "updated=excluded.updated",
            (username, kind, mime, sqlite3.Binary(data), now()))
        c.commit()


def get_asset(username, kind):
    with conn() as c:
        return c.execute("SELECT mime, bytes, updated FROM admin_assets WHERE username=? AND kind=?",
                         (username, kind)).fetchone()


def delete_asset(username, kind) -> bool:
    with _write_lock, conn() as c:
        cur = c.execute("DELETE FROM admin_assets WHERE username=? AND kind=?", (username, kind))
        c.commit()
        return cur.rowcount > 0


# ---------------------------------------------------------------- music library
# Each admin keeps their own tracks: upload once, then it stays in their account.
def list_tracks(username):
    with conn() as c:
        rows = c.execute("SELECT id, name, mime, size, created FROM tracks WHERE username=? "
                         "ORDER BY created DESC", (username,)).fetchall()
    return [dict(r) for r in rows]


def add_track(username, name, mime, data: bytes) -> str:
    tid = secrets.token_hex(8)
    with _write_lock, conn() as c:
        c.execute("INSERT INTO tracks(id,username,name,mime,bytes,size,created) VALUES(?,?,?,?,?,?,?)",
                  (tid, username, str(name)[:120], str(mime)[:60], sqlite3.Binary(data), len(data), now()))
        c.commit()
    return tid


def get_track(username, tid):
    with conn() as c:
        return c.execute("SELECT id, name, mime, bytes, size FROM tracks WHERE id=? AND username=?",
                         (tid, username)).fetchone()


def delete_track(username, tid) -> bool:
    with _write_lock, conn() as c:
        cur = c.execute("DELETE FROM tracks WHERE id=? AND username=?", (tid, username))
        c.commit()
        return cur.rowcount > 0



# ---------------------------------------------------------------- hosts (address pool)
# An admin keeps the addresses they want their VLESS configs to hand out. An inbound can
# then use any of them (stored in its clean_ips list) and the generated configs rotate
# over exactly those addresses.
def list_hosts():
    with conn() as c:
        rows = c.execute("SELECT * FROM hosts ORDER BY created").fetchall()
    return [dict(r) for r in rows]


def host_row(hid):
    with conn() as c:
        return c.execute("SELECT * FROM hosts WHERE id=?", (hid,)).fetchone()


def add_host(address, label="", remark="", created_by=""):
    hid = secrets.token_hex(8)
    with _write_lock, conn() as c:
        c.execute("INSERT INTO hosts(id,address,label,remark,enabled,created_by,created) VALUES(?,?,?,?,?,?,?)",
                  (hid, str(address).strip()[:200], str(label or "")[:60], str(remark or "")[:200], 1,
                   str(created_by or ""), now()))
        c.commit()
    return hid


def update_host(hid, fields: dict) -> bool:
    allowed = ("address", "label", "remark", "enabled")
    sets, vals = [], []
    for k in allowed:
        if k in fields:
            v = (1 if fields[k] else 0) if k == "enabled" else fields[k]
            sets.append(f"{k}=?")
            vals.append(v)
    if not sets:
        return False
    vals.append(hid)
    with _write_lock, conn() as c:
        cur = c.execute(f"UPDATE hosts SET {', '.join(sets)} WHERE id=?", vals)
        c.commit()
        return cur.rowcount > 0


def delete_host(hid) -> bool:
    with _write_lock, conn() as c:
        cur = c.execute("DELETE FROM hosts WHERE id=?", (hid,))
        c.commit()
        return cur.rowcount > 0


# ---------------------------------------------------------------- client sub-links
# Attach another client's subscription to this one: when the main client's sub is fetched,
# the linked clients' configs are included as extra locations.
def list_client_links(cid):
    with conn() as c:
        rows = c.execute("SELECT linked_id FROM client_links WHERE client_id=? ORDER BY created", (cid,)).fetchall()
    return [r["linked_id"] for r in rows]


def add_client_link(cid, linked) -> bool:
    if not cid or not linked or cid == linked:
        return False
    with _write_lock, conn() as c:
        c.execute("INSERT OR IGNORE INTO client_links(client_id,linked_id,created) VALUES(?,?,?)",
                  (cid, linked, now()))
        c.commit()
    return True


def remove_client_link(cid, linked) -> bool:
    with _write_lock, conn() as c:
        cur = c.execute("DELETE FROM client_links WHERE client_id=? AND linked_id=?", (cid, linked))
        c.commit()
        return cur.rowcount > 0


def linked_clients(cid):
    out = []
    for lid in list_client_links(cid):
        row = client_row(lid)
        if row:
            out.append(dict(row))
    return out

# ---------------------------------------------------------------- nodes (panel to panel)
# A node is another Dollax panel in a different location. The connecting panel pulls that
# panel's inbounds (via /api/node/export with the shared node token) so subs can carry
# several locations, and its inbounds show up here tagged with the node's location.
def list_nodes():
    with conn() as c:
        rows = c.execute("SELECT * FROM nodes ORDER BY created").fetchall()
    return [dict(r) for r in rows]


def node_row(nid):
    with conn() as c:
        return c.execute("SELECT * FROM nodes WHERE id=?", (nid,)).fetchone()


def add_node(fields: dict) -> str:
    nid = fields.get("id") or secrets.token_hex(6)
    with _write_lock, conn() as c:
        c.execute("INSERT INTO nodes(id,name,url,token,location,flag,enabled,status,snapshot,last_seen,"
                  "created_by,created) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                  (nid, str(fields.get("name") or "")[:60], str(fields.get("url") or "")[:300],
                   str(fields.get("token") or "")[:200], str(fields.get("location") or "")[:60],
                   str(fields.get("flag") or "")[:8], 1 if fields.get("enabled", True) else 0,
                   "", "[]", "", str(fields.get("created_by") or ""), now()))
        c.commit()
    return nid


def update_node(nid, fields: dict) -> bool:
    allowed = ("name", "url", "token", "location", "flag", "enabled")
    sets, vals = [], []
    for k in allowed:
        if k in fields:
            v = fields[k]
            if k == "enabled":
                v = 1 if v else 0
            sets.append(f"{k}=?")
            vals.append(v)
    if not sets:
        return False
    vals.append(nid)
    with _write_lock, conn() as c:
        cur = c.execute(f"UPDATE nodes SET {', '.join(sets)} WHERE id=?", vals)
        c.commit()
        return cur.rowcount > 0


def delete_node(nid) -> bool:
    with _write_lock, conn() as c:
        cur = c.execute("DELETE FROM nodes WHERE id=?", (nid,))
        c.commit()
        return cur.rowcount > 0


def set_node_snapshot(nid, status, items, seen="") -> None:
    with _write_lock, conn() as c:
        c.execute("UPDATE nodes SET status=?, snapshot=?, last_seen=? WHERE id=?",
                  (str(status)[:200], json.dumps(items or []), seen or now(), nid))
        c.commit()


def node_token() -> str:
    """The token other panels must present to read this panel's inbounds."""
    tok = setting("node_token")
    if not tok:
        tok = secrets.token_urlsafe(24)
        set_setting("node_token", tok)
    return tok


# ---------------------------------------------------------------- activity
def log(username, action, detail="", ip=""):
    try:
        with _write_lock, conn() as c:
            c.execute("INSERT INTO activity(ts,username,ip,action,detail) VALUES(?,?,?,?,?)",
                      (now(), username, str(ip)[:64], action, str(detail)[:400]))
            c.commit()
    except Exception:
        pass


def activity(limit=100):
    with conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM activity ORDER BY id DESC LIMIT ?", (limit,)).fetchall()]


# ---------------------------------------------------------------- serialisation helpers
def json_raw(value, default=None):
    """Decode arbitrary stored JSON (lists/dicts) without the IP-list clean-up."""
    if isinstance(value, (list, dict)):
        return value
    try:
        parsed = json.loads(value) if value else default
        return parsed if parsed is not None else (default if default is not None else [])
    except Exception:
        return default if default is not None else []


def json_list(value):
    if isinstance(value, list):
        items = value
    elif isinstance(value, (tuple, set)):
        items = list(value)
    else:
        try:
            parsed = json.loads(value) if value else []
            items = parsed if isinstance(parsed, list) else str(value or "").splitlines()
        except Exception:
            items = str(value or "").replace(",", "\n").splitlines()
    return clean_ip_list(items)


def clean_ip_list(items, limit=200):
    out = []
    for item in items or []:
        s = str(item).strip()
        if not s or s in out:
            continue
        # accept "ip", "ip#port", "ip:port", "host"
        s = s.replace("https://", "").replace("http://", "").strip("/")
        if " " in s:
            s = s.split()[0]
        if len(s) > 253:
            continue
        out.append(s)
        if len(out) >= limit:
            break
    return out


# ---------------------------------------------------------------- inbounds
INBOUND_FIELDS = [
    "name", "protocol", "network", "security", "address", "port", "path", "host_header", "sni", "alpn",
    "fingerprint", "flow", "grpc_service_name", "grpc_mode", "xhttp_mode", "header_type", "allow_insecure",
    "reality_public_key", "reality_short_id", "reality_spider_x", "reality_private_key", "reality_dest",
    "ss_method", "ss_password", "fragment", "wg_public_key", "wg_address",
    "limit_bytes", "expires_at", "ip_limit", "connection_limit", "client_limit", "config_count",
    "clean_ips", "note", "enabled",
]


def inbound_row(iid):
    with conn() as c:
        return c.execute("SELECT * FROM inbounds WHERE id=?", (iid,)).fetchone()


def inbound_by_path(path):
    with conn() as c:
        return c.execute("SELECT * FROM inbounds WHERE path=? AND enabled=1", (path,)).fetchone()


def inbound_by_token(token):
    with conn() as c:
        return c.execute("SELECT * FROM inbounds WHERE sub_token=?", (token,)).fetchone()


def list_inbounds():
    with conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM inbounds ORDER BY created DESC").fetchall()]


def create_inbound(fields: dict) -> str:
    iid = secrets.token_hex(12)
    fields = dict(fields)
    fields.setdefault("path", "/ws/" + protocol.new_token(10))
    fields["uuid"] = fields.get("uuid") or protocol.new_uuid()
    with _write_lock, conn() as c:
        cols = ["id", "sub_token", "created"] + list(fields.keys())
        vals = [iid, protocol.new_token(16), now()] + [enc(v) for v in fields.values()]
        sql = f"INSERT INTO inbounds({','.join(cols)}) VALUES({','.join('?' * len(cols))})"
        c.execute(sql, vals)
        c.commit()
    return iid


def update_inbound(iid, fields: dict):
    fields = {k: v for k, v in fields.items() if k in INBOUND_FIELDS}
    if not fields:
        return False
    with _write_lock, conn() as c:
        sets = ",".join(f"{k}=?" for k in fields)
        c.execute(f"UPDATE inbounds SET {sets} WHERE id=?", (*[enc(v) for v in fields.values()], iid))
        c.commit()
        return c.total_changes > 0


def delete_inbound(iid) -> bool:
    with _write_lock, conn() as c:
        cur = c.execute("DELETE FROM inbounds WHERE id=?", (iid,))
        c.commit()
        return cur.rowcount > 0


def add_inbound_usage(iid, up=0, down=0):
    """Client->target is upload, target->client is download."""
    up, down = int(up or 0), int(down or 0)
    if up <= 0 and down <= 0:
        return
    with _write_lock, conn() as c:
        c.execute("UPDATE inbounds SET used_bytes=used_bytes+?, up_bytes=up_bytes+?, down_bytes=down_bytes+? "
                  "WHERE id=?", (up + down, up, down, iid))
        c.commit()


# ---------------------------------------------------------------- clients
CLIENT_FIELDS = [
    "name", "limit_bytes", "expires_at", "ip_limit", "connection_limit", "speed_limit_mbps",
    "clean_ips", "note", "enabled", "created_by", "extra_inbounds", "config_count",
]


def client_row(cid):
    with conn() as c:
        return c.execute("SELECT * FROM clients WHERE id=?", (cid,)).fetchone()


def client_by_token(token):
    with conn() as c:
        return c.execute("SELECT * FROM clients WHERE sub_token=?", (token,)).fetchone()


def clients_for_inbound(iid):
    with conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM clients WHERE inbound_id=? ORDER BY created DESC", (iid,)).fetchall()]


def list_clients():
    with conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM clients ORDER BY created DESC").fetchall()]


def create_client(iid, name, **kw):
    cid = secrets.token_hex(12)
    uid = protocol.new_uuid()
    fields = {
        "limit_bytes": 0, "expires_at": "", "ip_limit": 0, "connection_limit": 0,
        "speed_limit_mbps": 0, "clean_ips": "[]", "note": "", "enabled": 1,
    }
    fields.update({k: v for k, v in kw.items() if k in CLIENT_FIELDS})
    with _write_lock, conn() as c:
        c.execute(
            """INSERT INTO clients(id,inbound_id,name,uuid,limit_bytes,expires_at,ip_limit,connection_limit,
               speed_limit_mbps,clean_ips,note,enabled,used_bytes,sub_token,last_seen,created)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (cid, iid, name, uid, enc(fields["limit_bytes"]), enc(fields["expires_at"]), enc(fields["ip_limit"]),
             enc(fields["connection_limit"]), enc(fields["speed_limit_mbps"]), enc(fields["clean_ips"]), enc(fields["note"]),
             enc(fields["enabled"]), 0, protocol.new_token(16), "", now()),
        )
        # ownership + multi-location + per-client config count
        c.execute("UPDATE clients SET created_by=?, extra_inbounds=?, config_count=? WHERE id=?",
                  (str(fields.get("created_by") or ""), enc(fields.get("extra_inbounds") or []),
                   max(1, min(10, int(fields.get("config_count") or 2))), cid))
        c.commit()
    return cid


def update_client(cid, fields: dict):
    fields = {k: v for k, v in fields.items() if k in CLIENT_FIELDS}
    if not fields:
        return False
    with _write_lock, conn() as c:
        sets = ",".join(f"{k}=?" for k in fields)
        c.execute(f"UPDATE clients SET {sets} WHERE id=?", (*[enc(v) for v in fields.values()], cid))
        c.commit()
        return c.total_changes > 0


def delete_client(cid) -> bool:
    with _write_lock, conn() as c:
        cur = c.execute("DELETE FROM clients WHERE id=?", (cid,))
        c.commit()
        return cur.rowcount > 0


def regenerate_client(cid) -> str:
    uid = protocol.new_uuid()
    with _write_lock, conn() as c:
        c.execute("UPDATE clients SET uuid=? WHERE id=?", (uid, cid))
        c.commit()
    return uid


def reset_usage(cid, reset_traffic=True):
    with _write_lock, conn() as c:
        if reset_traffic:
            c.execute("UPDATE clients SET used_bytes=0, up_bytes=0, down_bytes=0 WHERE id=?", (cid,))
        c.commit()


def add_client_usage(cid, up=0, down=0):
    up, down = int(up or 0), int(down or 0)
    if up <= 0 and down <= 0:
        return
    with _write_lock, conn() as c:
        c.execute("UPDATE clients SET used_bytes=used_bytes+?, up_bytes=up_bytes+?, down_bytes=down_bytes+?, "
                  "last_seen=? WHERE id=?", (up + down, up, down, now(), cid))
        c.commit()


def touch_client_config(cid):
    """Ledger: every time a config/subscription is generated for this client."""
    if not cid:
        return
    try:
        with _write_lock, conn() as c:
            c.execute("UPDATE clients SET last_config_at=?, sub_fetches=sub_fetches+1 WHERE id=?",
                      (now(), cid))
            c.commit()
    except Exception:
        pass


def ledger_rows():
    """Full per-client ledger: quota, consumed, remaining, expiry, last generation."""
    with conn() as c:
        rows = c.execute(
            """SELECT c.id, c.name, c.uuid, c.inbound_id, i.name AS inbound_name, i.protocol, i.network,
                      i.security, c.enabled, c.limit_bytes, c.used_bytes, c.up_bytes, c.down_bytes,
                      c.expires_at, c.sub_token, c.last_seen, c.last_config_at, c.sub_fetches, c.created
               FROM clients c LEFT JOIN inbounds i ON i.id = c.inbound_id
               ORDER BY c.created DESC""").fetchall()
    out = []
    for r in rows:
        d = dict(r)
        limit = int(d.get("limit_bytes") or 0)
        used = int(d.get("used_bytes") or 0)
        d["remaining_bytes"] = max(0, limit - used) if limit else 0
        d["remaining_human"] = fmt_bytes(d["remaining_bytes"]) if limit else "unlimited"
        d["used_human"] = fmt_bytes(used)
        d["limit_human"] = fmt_bytes(limit) if limit else "unlimited"
        d["days_left"] = days_left(d.get("expires_at"))
        d["state"] = ("disabled" if not d.get("enabled") else
                      "expired" if (d["days_left"] is not None and d["days_left"] < 0) else
                      "quota" if (limit and used >= limit) else "active")
        out.append(d)
    return out


# ---------------------------------------------------------------- clean IPs
def list_clean_ips():
    with conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM clean_ips ORDER BY created DESC").fetchall()]


def add_clean_ip(address, label="", rtt_ms=0, loss_pct=0.0, note=""):
    with _write_lock, conn() as c:
        c.execute(
            "INSERT OR IGNORE INTO clean_ips(id,address,label,rtt_ms,loss_pct,note,created) VALUES(?,?,?,?,?,?,?)",
            (secrets.token_hex(8), str(address)[:253], str(label)[:80], int(rtt_ms or 0), float(loss_pct or 0), str(note)[:200], now()),
        )
        c.commit()


def delete_clean_ips(ids):
    ids = [str(i) for i in (ids or [])]
    if not ids:
        return 0
    with _write_lock, conn() as c:
        q = ",".join("?" * len(ids))
        cur = c.execute(f"DELETE FROM clean_ips WHERE id IN ({q})", ids)
        c.commit()
        return cur.rowcount


def delete_all_clean_ips():
    with _write_lock, conn() as c:
        cur = c.execute("DELETE FROM clean_ips")
        c.commit()
        return cur.rowcount


# ---------------------------------------------------------------- expiry helpers
def expiry_from_days(days):
    days = int(days or 0)
    if days <= 0:
        return ""
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def days_left(expires_at):
    if not expires_at:
        return None
    try:
        dt = datetime.fromisoformat(str(expires_at))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int((dt - datetime.now(timezone.utc)).total_seconds() // 86400)
    except Exception:
        return None


def is_expired(expires_at):
    d = days_left(expires_at)
    return d is not None and d < 0


def fmt_bytes(n):
    n = float(n or 0)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.2f} {unit}" if unit != "B" else f"{int(n)} B"
        n /= 1024
    return f"{n:.2f} TB"


def uptime():
    return time.time()
