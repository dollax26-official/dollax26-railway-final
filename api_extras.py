"""Hosts (address pool) and client sub-link endpoints.

Kept in their own module so the main application file stays small enough to move around;
`register()` is called from main.py with the application plus the main module itself, so
these routes use exactly the same helpers as the rest of the panel.
"""
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter()
m: Any = None


def register(app, main_module) -> None:
    """Attach the routes (main_module gives access to the panel's helpers and db)."""
    global m
    m = main_module
    app.include_router(router)


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


