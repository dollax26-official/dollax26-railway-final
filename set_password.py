"""Reset (or create) a panel login from inside the container.

The owner account is seeded only ONCE, on the first boot of an empty database.
If you change ADMIN_PASSWORD afterwards, the stored hash does NOT change — this
script is how you set it directly.

    cd /app
    python set_password.py dollax26 'MyNewPassword'
    python set_password.py                # show the existing admins only

Works with the same DATA_DIR / volume the app uses.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import db  # noqa: E402


def show_admins():
    with db.conn() as c:
        rows = c.execute("SELECT username, role, enabled, created FROM admins ORDER BY username").fetchall()
    if not rows:
        print("no admins in", db.DB_PATH)
    for r in rows:
        print(f"  {r['username']:<20} role={r['role']:<6} enabled={r['enabled']}  created={str(r['created'])[:19]}")
    return rows


def main():
    db.init_db()
    print("database:", db.DB_PATH)
    user = sys.argv[1] if len(sys.argv) > 1 else ""
    pw = sys.argv[2] if len(sys.argv) > 2 else ""

    if not user or not pw:
        print("\nexisting admins:")
        show_admins()
        print("\nto set a password:  python set_password.py <username> <new-password>")
        return 0

    with db._write_lock, db.conn() as c:
        cur = c.execute("UPDATE admins SET password_hash=?, enabled=1 WHERE username=?",
                        (db.hash_password(pw), user))
        if cur.rowcount == 0:
            c.execute("INSERT INTO admins(username,password_hash,role,enabled,prefs_json,created) "
                      "VALUES(?,?,?,?,?,?)",
                      (user, db.hash_password(pw), "owner", 1, "{}", db.now()))
            print(f"created admin '{user}' (role=owner)")
        else:
            print(f"password updated for '{user}' (and enabled)")
        c.commit()

    if not db.verify_password(pw, db.get_admin(user)["password_hash"]):
        print("ERROR: verification failed — something is wrong with the database")
        return 1
    print("verified: the new password matches the stored hash")
    print("\nadmins now:")
    show_admins()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
