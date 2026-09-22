"""Hosts (address pool) and client sub-link endpoints.

Kept in their own module so the main application file stays small enough to move around;
`register()` is called from main.py with the application plus the main module itself, so
these routes use exactly the same helpers as the rest of the panel.
"""
import secrets
import asyncio
import json
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter()      # hosts + client sub-links
nodes = APIRouter()       # node (panel-to-panel) endpoints
m: Any = None


def register(app, main_module) -> None:
    """Attach the routes (main_module gives access to the panel's helpers and db)."""
    global m
    m = main_module
    app.include_router(router)
    app.include_router(nodes)


@router.get("/api/hosts")
async def api_list_hosts(request: Request):
    """The address pool an admin wants their configs to hand out (x-ui style hosts list)."""
    if not m.authed(request):
        return m.unauthorized()
    return {"items": [dict(r) for r in m.db.list_hosts()]}


@router.post("/api/hosts")
async def api_add_host(request: Request):
    if not m.authed(request):
        return m.unauthorized()
    d = await request.json()
    addrs = d.get("addresses")
    if isinstance(addrs, str):
        addrs = addrs.replace(",", "\n").splitlines()
    if not addrs:
        one = str(d.get("address") or "").strip()
        addrs = [one] if one else []
    known = {h["address"] for h in m.db.list_hosts()}
    added = 0
    for a in addrs:
        a = str(a or "").strip()
        if not a or a in known:
            continue
        m.db.add_host(a, d.get("label", ""), d.get("remark", ""), m.current_user(request))
        known.add(a)
        added += 1
    m.db.log(m.current_user(request), "host-add", str(added), ip=m.client_ip(request))
    return {"ok": True, "added": added, "items": [dict(r) for r in m.db.list_hosts()]}


@router.patch("/api/hosts/{hid}")
async def api_update_host(request: Request, hid: str):
    if not m.authed(request):
        return m.unauthorized()
    if not m.db.host_row(hid):
        return JSONResponse({"error": "Host not found"}, status_code=404)
    d = await request.json()
    fields = {}
    for k in ("address", "label", "remark"):
        if k in d:
            fields[k] = str(d[k] or "")[:200]
    if "enabled" in d and m.as_bool(d.get("enabled"), True):
        fields.pop("enabled", None)
    elif "enabled" in d:
        fields["enabled"] = False
    m.db.update_host(hid, fields)
    m.db.log(m.current_user(request), "host-update", hid, ip=m.client_ip(request))
    return {"ok": True, "items": [dict(r) for r in m.db.list_hosts()]}


@router.delete("/api/hosts/{hid}")
async def api_delete_host(request: Request, hid: str):
    if not m.authed(request):
        return m.unauthorized()
    ok = m.db.delete_host(hid)
    m.db.log(m.current_user(request), "host-remove", hid, ip=m.client_ip(request))
    return {"ok": ok, "items": [dict(r) for r in m.db.list_hosts()]}



@router.get("/api/clients/{cid}/links")
async def api_client_links(request: Request, cid: str):
    if not m.authed(request):
        return m.unauthorized()
    if not m.db.client_row(cid):
        return JSONResponse({"error": "Client not found"}, status_code=404)
    return {"items": [{"id": c["id"], "name": c["name"], "sub_token": c["sub_token"]}
                      for c in m.db.linked_clients(cid)]}


@router.post("/api/clients/{cid}/links")
async def api_client_link_add(request: Request, cid: str):
    """Attach another client's subscription to this one: its configs join this client's sub."""
    if not m.authed(request):
        return m.unauthorized()
    row = m.db.client_row(cid)
    if not row:
        return JSONResponse({"error": "Client not found"}, status_code=404)
    if not m._client_guard(request, row):
        return JSONResponse({"error": "That client belongs to another admin."}, status_code=403)
    d = await request.json()
    target = str(d.get("client_id") or d.get("linked_id") or "")
    other = m.db.client_row(target) if target else None
    if not other:
        return JSONResponse({"error": "Pick a client to link."}, status_code=400)
    if not m._client_guard(request, other):
        return JSONResponse({"error": "That client belongs to another admin."}, status_code=403)
    if not m.db.add_client_link(cid, target):
        return JSONResponse({"error": "That link cannot be added."}, status_code=400)
    m.db.log(m.current_user(request), "client-link", row["name"] + " <- " + other["name"], ip=m.client_ip(request))
    return {"ok": True, "client": m.client_dict(m.db.client_row(cid), request)}


@router.delete("/api/clients/{cid}/links/{linked}")
async def api_client_link_remove(request: Request, cid: str, linked: str):
    if not m.authed(request):
        return m.unauthorized()
    row = m.db.client_row(cid)
    if not row or not m._client_guard(request, row):
        return JSONResponse({"error": "Client not found"}, status_code=404)
    ok = m.db.remove_client_link(cid, linked)
    m.db.log(m.current_user(request), "client-unlink", row["name"] + " -/-> " + linked, ip=m.client_ip(request))
    return {"ok": ok, "client": m.client_dict(m.db.client_row(cid), request)}

# ---------------------------------------------------------------- nodes
def node_base(url: str) -> str:
    base = str(url or "").strip().rstrip("/")
    if not base:
        return ""
    if not base.startswith(("http://", "https://")):
        base = "https://" + base
    return base


def node_export_payload(request: Request) -> dict:
    """What another panel may read when it presents this panel's node token."""
    inbounds = []
    for row in m.db.list_inbounds():
        ib = m.inbound_dict(row)
        if m.protocol.clean_protocol(ib.get("protocol")) == "wireguard":
            continue                      # .conf, not a URI entry
        inbounds.append({
            "id": ib["id"], "name": ib.get("name"), "protocol": ib.get("protocol"),
            "network": ib.get("network"), "security": ib.get("security"),
            "address": ib.get("address") or m.effective_host(request), "port": ib.get("port"),
            "path": ib.get("path"), "host_header": ib.get("host_header"), "sni": ib.get("sni"),
            "alpn": ib.get("alpn"), "fingerprint": ib.get("fingerprint"),
            "grpc_service_name": ib.get("grpc_service_name"), "grpc_mode": ib.get("grpc_mode"),
            "xhttp_mode": ib.get("xhttp_mode"), "header_type": ib.get("header_type"),
            "flow": ib.get("flow"), "allow_insecure": ib.get("allow_insecure"),
            "reality_public_key": ib.get("reality_public_key"),
            "reality_short_id": ib.get("reality_short_id"),
            "reality_spider_x": ib.get("reality_spider_x"),
            "ss_method": ib.get("ss_method"), "ss_password": ib.get("ss_password"),
            "uuid": ib.get("uuid"), "enabled": bool(ib.get("enabled")),
            "clients": len(m.db.clients_for_inbound(ib["id"])),
            "used_bytes": int(ib.get("used_bytes") or 0),
            "limit_bytes": int(ib.get("limit_bytes") or 0),
        })
    return {
        "ok": True,
        "panel": {"name": m.db.setting("panel_name", "Dollax Panel"), "host": m.effective_host(request),
                  "version": m.APP_VERSION},
        "inbounds": inbounds,
    }


def fetch_node_export(url: str, token: str, timeout: float = 10.0):
    """GET <panel>/api/node/export?token=… → (payload | None, error)."""
    base = node_base(url)
    if not base:
        return None, "no url"
    try:
        import httpx
        with httpx.Client(timeout=timeout, follow_redirects=True) as c:
            r = c.get(base + "/api/node/export", params={"token": token})
        if r.status_code == 403:
            return None, "token rejected (HTTP 403)"
        if r.status_code != 200:
            return None, f"HTTP {r.status_code}"
        data = r.json()
        if not isinstance(data, dict) or "inbounds" not in data:
            return None, "unexpected payload"
        return data, ""
    except Exception as exc:  # noqa: BLE001
        return None, f"{exc.__class__.__name__}: {str(exc)[:120]}"


def refresh_node(nid: str) -> dict:
    row = m.db.node_row(nid)
    if not row:
        return {"ok": False, "error": "Node not found"}
    data, err = fetch_node_export(row["url"], row["token"])
    if not data:
        m.db.set_node_snapshot(nid, f"error: {err}", [], "")
        return {"ok": False, "error": err, "node": node_view(m.db.node_row(nid))}
    items = []
    for ib in data.get("inbounds", []):
        ib = dict(ib)
        ib["node_id"] = nid
        items.append(ib)
    panel = data.get("panel") or {}
    m.db.set_node_snapshot(nid, "ok", items, "")
    if panel.get("name") and not row["name"]:
        m.db.update_node(nid, {"name": panel["name"]})
    return {"ok": True, "node": node_view(m.db.node_row(nid)), "count": len(items)}


def node_view(row) -> dict:
    if not row:
        return {}
    d = dict(row)
    d["enabled"] = bool(d.get("enabled"))
    d["inbounds"] = m.db.json_raw(d.get("snapshot"), [])
    d["inbound_count"] = len(d["inbounds"])
    d.pop("snapshot", None)
    return d


def node_ref(node_id, inbound_id) -> str:
    """The canonical reference of a remote inbound: node:<node id>:<inbound id>."""
    return f"node:{node_id}:{inbound_id}"


def node_inbounds() -> list:
    out = []
    for row in m.db.list_nodes():
        if not row["enabled"]:
            continue
        for ib in m.db.json_raw(row["snapshot"], []):
            ib = dict(ib)
            ib["node_id"] = row["id"]
            ib["node_name"] = row["name"]
            ib["location"] = row["location"]
            ib["flag"] = row["flag"]
            # the reference a client stores to select this remote inbound
            ib["ref"] = node_ref(row["id"], ib.get("id"))
            out.append(ib)
    return out


def find_remote(ref: str):
    """ref = 'node:<node_id>:<inbound_id>' → (node_row, m.inbound_dict) or (None, None)."""
    parts = str(ref or "").split(":", 2)
    if len(parts) != 3 or parts[0] != "node":
        return None, None
    node = m.db.node_row(parts[1])
    if not node:
        return None, None
    for ib in m.db.json_raw(node["snapshot"], []):
        if str(ib.get("id")) == parts[2]:
            return node, dict(ib)
    return node, None


@nodes.get("/api/node/export")
async def api_node_export(request: Request, token: str = ""):
    """Read-only inbound catalogue for another panel (shared node token)."""
    if not token or token != m.db.node_token():
        return JSONResponse({"error": "Invalid node token."}, status_code=403)
    return node_export_payload(request)


# Hosts + client sub-links live in api_extras (keeps this file portable).


@nodes.get("/api/node/token")
async def api_node_token(request: Request):
    if not m.authed(request):
        return m.unauthorized()
    if not m.is_owner(request):
        return JSONResponse({"error": "Owner only."}, status_code=403)
    return {"token": m.db.node_token(), "host": m.effective_host(request)}


@nodes.post("/api/node/token/rotate")
async def api_node_token_rotate(request: Request):
    if not m.authed(request):
        return m.unauthorized()
    if not m.is_owner(request):
        return JSONResponse({"error": "Owner only."}, status_code=403)
    m.db.set_setting("node_token", secrets.token_urlsafe(24))
    m.db.log(m.current_user(request), "node-token-rotate", "", ip=m.client_ip(request))
    return {"token": m.db.node_token()}


@nodes.get("/api/nodes")
async def api_list_nodes(request: Request):
    if not m.authed(request):
        return m.unauthorized()
    items = [node_view(r) for r in m.db.list_nodes()]
    return {"items": items, "remote_inbounds": node_inbounds(),
            "token": m.db.node_token() if m.is_owner(request) else "",
            "share": {"host": m.effective_host(request), "path": "/api/node/export"}}


@nodes.post("/api/nodes")
async def api_add_node(request: Request):
    if not m.authed(request):
        return m.unauthorized()
    d = await request.json()
    url = str(d.get("url") or "")
    token = str(d.get("token") or "").strip()
    if not node_base(url):
        return JSONResponse({"error": "Enter the other panel's address."}, status_code=400)
    if not token:
        return JSONResponse({"error": "Enter that panel's node token (Nodes → Node token)."}, status_code=400)
    nid = m.db.add_node({"name": str(d.get("name") or "")[:60], "url": url, "token": token,
                       "location": str(d.get("location") or "")[:60], "flag": str(d.get("flag") or "")[:8],
                       "enabled": True, "created_by": m.current_user(request)})
    # the fetch is blocking (httpx) - keep it off the event loop so the panel stays responsive
    res = await asyncio.to_thread(refresh_node, nid)
    m.db.log(m.current_user(request), "node-add", f"{d.get('name') or url}", ip=m.client_ip(request))
    if not res.get("ok"):
        return {"ok": True, "id": nid, "node": res.get("node"), "warning": res.get("error"),
                "items": [node_view(r) for r in m.db.list_nodes()]}
    return {"ok": True, "id": nid, "node": res["node"], "items": [node_view(r) for r in m.db.list_nodes()]}


@nodes.patch("/api/nodes/{nid}")
async def api_update_node(request: Request, nid: str):
    if not m.authed(request):
        return m.unauthorized()
    if not m.db.node_row(nid):
        return JSONResponse({"error": "Node not found"}, status_code=404)
    d = await request.json()
    fields = {}
    for k in ("name", "url", "token", "location", "flag"):
        if k in d:
            fields[k] = str(d[k] or "")[:300]
    if "enabled" in d:
        fields["enabled"] = m.as_bool(d.get("enabled"), True)
    if fields.get("enabled") is True:
        fields.pop("enabled")
    m.db.update_node(nid, fields)
    m.db.log(m.current_user(request), "node-update", nid, ip=m.client_ip(request))
    return {"ok": True, "items": [node_view(r) for r in m.db.list_nodes()]}


@nodes.post("/api/nodes/{nid}/refresh")
async def apirefresh_node(request: Request, nid: str):
    if not m.authed(request):
        return m.unauthorized()
    if not m.db.node_row(nid):
        return JSONResponse({"error": "Node not found"}, status_code=404)
    res = await asyncio.to_thread(refresh_node, nid)
    return {"ok": bool(res.get("ok")), "error": res.get("error") or "",
            "items": [node_view(r) for r in m.db.list_nodes()], "remote_inbounds": node_inbounds()}


@nodes.delete("/api/nodes/{nid}")
async def api_delete_node(request: Request, nid: str):
    if not m.authed(request):
        return m.unauthorized()
    ok = m.db.delete_node(nid)
    m.db.log(m.current_user(request), "node-delete", nid, ip=m.client_ip(request))
    return {"ok": ok, "items": [node_view(r) for r in m.db.list_nodes()]}


