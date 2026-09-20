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
import time
import sqlite3
import secrets
import hashlib
import hmac
import tempfile
import threading
from pathlib import Path
from datetime import datetime, timezone, timedelta

import protocol

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
    c = sqlite3.connect(DB_PATH, timeout=15)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA foreign_keys=ON")
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
  sub_token TEXT NOT NULL DEFAULT '',
  last_seen TEXT NOT NULL DEFAULT '',
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


def init_db():
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
    "reality_public_key", "reality_short_id", "reality_spider_x", "ss_method", "ss_password", "fragment",
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


def add_inbound_usage(iid, nbytes):
    if nbytes <= 0:
        return
    with _write_lock, conn() as c:
        c.execute("UPDATE inbounds SET used_bytes=used_bytes+? WHERE id=?", (int(nbytes), iid))
        c.commit()


# ---------------------------------------------------------------- clients
CLIENT_FIELDS = [
    "name", "limit_bytes", "expires_at", "ip_limit", "connection_limit", "speed_limit_mbps",
    "clean_ips", "note", "enabled",
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
            c.execute("UPDATE clients SET used_bytes=0 WHERE id=?", (cid,))
        c.commit()


def add_client_usage(cid, nbytes):
    if nbytes <= 0:
        return
    with _write_lock, conn() as c:
        c.execute("UPDATE clients SET used_bytes=used_bytes+?, last_seen=? WHERE id=?", (int(nbytes), now(), cid))
        c.commit()


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
