/* Dollax panel - part 2: the secondary pages (clients, logs, admins, settings).
   app.js alone is a fully working panel (overview/inbounds/nodes + boot); this file
   only adds the sections below. */
/* The absolute subscription URL of an inbound (works for node/remote inbounds too). */
function inboundSubUrl(ib) {
  if (ib && ib.sub_url) return ib.sub_url;
  const tok = (ib && ib.sub_token) || '';
  if (!tok) return '';
  return location.origin + '/sub/' + tok;
}

function pageClients(view) {
  const ib = S.inbounds.find((i) => i.id === S.clientsIb) || S.inbounds[0];
  if (ib && !S.clientsIb) S.clientsIb = ib.id;
  const list = S.clients.filter((c) => !ib || c.inbound_id === ib.id);
  view.innerHTML = `
    <div class="card">
      <div class="form-grid">
        <label class="field"><span>${T('pickInbound')}</span>
          <select id="cIb">${S.inbounds.length
            ? S.inbounds.map((x) => `<option value="${esc(x.id)}" ${ib && x.id === ib.id ? 'selected' : ''}>${esc(x.name)} · ${esc((x.protocol || '').toUpperCase())} · ${x.client_count || 0} ${T('clients')}</option>`).join('')
            : `<option>${T('pickInboundFirst')}</option>`}</select></label>
        <label class="field"><span>${T('inboundInfo')}</span>
          <div class="summary-strip" style="margin:0">${ib ? `${esc(ib.address || '')}:${esc(ib.port)} · ${T('path')} <code>${esc(ib.path)}</code>` : '—'}</div></label>
      </div>
      ${ib ? `<div class="toolbar" style="margin-top:12px">
        <button class="btn primary" id="cAdd">${T('addClient')}</button>
        <button class="btn sm" id="cInboundCfg">${T('config')}</button>
        <button class="btn sm" id="cInboundSub">${T('copySub')}</button>
        <button class="btn sm" id="cInboundPage">${T('openSub')}</button>
        <button class="btn sm" id="clLedger">${T('exportLedger')}</button>
      </div>` : ''}
    </div>
    <div class="tblwrap">
      ${list.length ? `<table>
        <thead><tr><th>${T('name')}</th><th>${T('status')}</th><th>${T('ping')}</th><th>${T('download')}</th><th>${T('upload')}</th><th>${T('traffic')}</th><th>${T('expiry')}</th><th>${T('actions')}</th></tr></thead>
        <tbody>${list.map((c) => `<tr>
          <td><b style="font-weight:700">${esc(c.name)}</b><span class="sub mono">${esc(c.uuid)}</span></td>
          <td><span class="badge ${c.expired ? 'bad' : !c.enabled ? '' : c.over_quota ? 'warn' : 'ok'}">${c.expired ? T('expired') : !c.enabled ? T('disabled') : c.over_quota ? T('quota') : T('active')}</span></td>
          <td class="mono muted num" id="ping-${esc(c.id)}">—</td>
          <td class="mono num">${T('downShort')} ${esc(c.down_human || '0 B')}</td>
          <td class="mono num">${T('upShort')} ${esc(c.up_human || '0 B')}</td>
          <td style="min-width:130px"><span class="sub">${esc(c.used_human)}${c.limit_bytes ? ' / ' + esc(c.limit_human) : ' / ∞'}</span>
            <div class="bar"><i style="width:${c.limit_bytes ? Math.min(100, c.usage_pct) : 0}%"></i></div></td>
          <td class="muted">${esc(shortDate(c.expires_at))}</td>
          <td><div style="display:flex;gap:5px;flex-wrap:wrap">
            <button class="btn sm" data-cact="ping" data-id="${esc(c.id)}">${T('ping')}</button>
            <button class="btn sm" data-cact="edit" data-id="${esc(c.id)}">${T('edit')}</button>
        <button class="btn sm" data-cact="links" data-id="${esc(c.id)}">${T('config')}</button>
            <button class="btn sm" data-cact="toggle" data-id="${esc(c.id)}">${c.enabled ? T('disable') : T('enable')}</button>
            <button class="btn sm danger" data-cact="delete" data-id="${esc(c.id)}">${T('del')}</button>
          </div></td></tr>`).join('')}</tbody></table>`
        : `<div class="empty"><b>${T('noClients') || 'No clients'}</b>${T('selfNodeHint')}</div>`}
    </div>`;

  if ($('cIb')) $('cIb').onchange = (e) => { S.clientsIb = e.target.value; pageClients(view); };
  if ($('cAdd')) $('cAdd').onclick = () => openClientDrawer(ib);
  if ($('clLedger')) $('clLedger').onclick = () => window.open('/api/ledger.csv', '_blank');
  if ($('cInboundCfg')) $('cInboundCfg').onclick = () => showInboundConfig(ib);
  // the inbound list has no absolute sub_url, so build it from the token
  if ($('cInboundSub')) $('cInboundSub').onclick = () => copyText(inboundSubUrl(ib));
  if ($('cInboundPage')) $('cInboundPage').onclick = () => window.open(`/info/${ib.sub_token}`, '_blank');
  if ($('cSubPreview')) $('cSubPreview').onclick = () => window.open(inboundSubUrl(ib), '_blank');
  $$('[data-cact]', view).forEach((b) => (b.onclick = () => clientAction(b.dataset.cact, b.dataset.id)));
}

async function clientAction(act, id) {
  const c = S.clients.find((x) => x.id === id);
  if (!c) return;
  if (act === 'ping') return pingClient(id);
  if (act === 'links') return showClientLinks(c);
  if (act === 'edit') return openEditClient(c);
  if (act === 'toggle') { await api('PATCH', `/api/clients/${id}`, { enabled: !c.enabled }); return loadAll(); }
  if (act === 'delete') {
    if (!(await confirmAsync(`${T('del')} “${c.name}”?`, T('confirmTitle')))) return;
    await api('DELETE', `/api/clients/${id}`);
    toast(T('deleted'), 'ok');
    return loadAll();
  }
}

/* ------------------------------------------------------------------ edit client */
async function openEditClient(c) {
  let linked = [];
  try { linked = (await api('GET', `/api/clients/${c.id}/links`)).items || []; } catch (e) { linked = []; }
  const others = (S.clients || []).filter((x) => x.id !== c.id);
  const exp = String(c.expires_at || '').slice(0, 16);
  const extra = c.extra_inbounds || [];
  const pick = (list, selected, kind) => list.map((x) => {
    const val = kind === 'remote' ? x.ref : x.id;
    const on = selected.includes(val) ? 'checked' : '';
    const name = kind === 'remote'
      ? `${esc(x.flag || '')} ${esc(x.node_name || 'node')} · ${esc(x.name || '')}`
      : esc(x.name);
    return `<label class="chk pick"><input type="checkbox" value="${esc(val)}" ${on}> <span>${name}</span></label>`;
  }).join('');

  openModal(`${T('editClient')} — ${esc(c.name)}`, `
    <div class="form-grid">
      <label class="field"><span>${T('clientName')}</span><input id="eName" value="${esc(c.name)}"></label>
      <label class="field"><span>${T('limitGb')}</span>
        <input id="eLimit" type="number" min="0" value="${c.limit_bytes ? (c.limit_bytes / 1073741824).toFixed(2) : ''}"></label>
      <label class="field"><span>${T('expiresAt')}</span><input id="eExp" type="datetime-local" value="${esc(exp)}"></label>
      <label class="field"><span>${T('days')}</span><input id="eDays" type="number" min="0" placeholder="+ days"></label>
      <label class="field"><span>${T('ipLimit')}</span><input id="eIp" type="number" min="0" value="${esc(c.ip_limit || 0)}"></label>
      <label class="field"><span>${T('connLimit')}</span><input id="eConn" type="number" min="0" value="${esc(c.connection_limit || 0)}"></label>
      <label class="field"><span>${T('speed')}</span><input id="eSpeed" type="number" min="0" value="${esc(c.speed_limit_mbps || 0)}"></label>
      <label class="field"><span>${T('configsPerClient')}</span><input id="eCount" type="number" min="1" max="10" value="${esc(c.config_count || 2)}"></label>
      <label class="field span-2"><span>${T('note')}</span><input id="eNote" value="${esc(c.note || '')}"></label>
    </div>

    <div class="card" style="margin-top:14px">
      <div class="card-head"><h2 style="font-size:13px">${T('inbound')}</h2></div>
      <label class="field"><span>${T('primaryLocation')}</span>
        <select id="ePrimary">${(S.inbounds || []).map((x) => `<option value="${esc(x.id)}" ${x.id === c.inbound_id ? 'selected' : ''}>${esc(x.name)}</option>`).join('')}</select></label>
      <label class="field" style="margin-top:10px"><span>${T('extraLocations')} <span class="muted">(${T('upToFive')})</span></span>
        <div class="pick-list" id="eExtra">
          ${pick((S.inbounds || []).filter((x) => x.id !== c.inbound_id), extra, 'local')}
          ${pick(S.remoteInbounds || [], extra, 'remote')}
        </div></label>
    </div>

    <div class="card" style="margin-top:14px">
      <div class="card-head"><h2 style="font-size:13px">${T('subLinks')}</h2></div>
      <p class="muted" style="font-size:10.5px">${T('subLinksNote')}</p>
      <div class="pick-list" id="eSubLinks" style="margin-top:9px">
        ${linked.length ? linked.map((l) => `<div class="trk">
            <span class="trk-name">${esc(l.name)}</span>
            <span class="muted trk-size">${T('linkedSubs')}</span>
            <button class="btn sm danger" type="button" data-unlink="${esc(l.id)}">${T('del')}</button></div>`).join('')
          : `<span class="muted">${T('noSubLinks')}</span>`}
      </div>
      <div class="toolbar" style="margin-top:9px">
        <select id="eLinkPick" style="max-width:240px;flex:1 1 auto">
          ${others.length ? others.map((x) => `<option value="${esc(x.id)}">${esc(x.name)}</option>`).join('')
                          : `<option value="">${T('noOtherClients')}</option>`}
        </select>
        <button class="btn sm" type="button" id="eLinkAdd">${T('linkThisSub')}</button>
      </div>
    </div>

    <div class="modal-foot"><span class="grow"></span>
      <button class="btn" id="eCancel">${T('cancel')}</button>
      <button class="btn primary" id="eSave">${T('save')}</button></div>`);

  const refresh = async () => { await loadAll(); await openEditClient(dbRowFor(c.id) || c); };
  $('eCancel').onclick = closeModal;
  $$('#eExtra input').forEach((el) => (el.onchange = () => {
    if ($$('#eExtra input:checked').length > 4) { el.checked = false; toast(T('upToFive'), 'bad'); }
  }));
  $$('[data-unlink]').forEach((b) => (b.onclick = async () => {
    try { await api('DELETE', `/api/clients/${c.id}/links/${b.dataset.unlink}`); toast(T('saved'), 'ok'); refresh(); }
    catch (e) { toast(e.message, 'bad'); }
  }));
  if ($('eLinkAdd')) $('eLinkAdd').onclick = async () => {
    const pickId = $('eLinkPick').value;
    if (!pickId) { toast(T('noOtherClients'), 'bad'); return; }
    try { await api('POST', `/api/clients/${c.id}/links`, { client_id: pickId }); toast(T('linkedSubs'), 'ok'); refresh(); }
    catch (e) { toast(e.message, 'bad'); }
  };
  $('eSave').onclick = async () => {
    const btn = $('eSave');
    btn.disabled = true;
    try {
      await api('PATCH', `/api/clients/${c.id}`, {
        name: $('eName').value || c.name,
        limit_value: $('eLimit').value || 0,
        expires_at: $('eExp').value || '',
        expires_days: $('eDays').value || 0,
        ip_limit: $('eIp').value || 0,
        connection_limit: $('eConn').value || 0,
        speed_limit_mbps: $('eSpeed').value || 0,
        config_count: $('eCount').value || 2,
        note: $('eNote').value,
        extra_inbounds: $$('#eExtra input:checked').map((el) => el.value).slice(0, 4),
      });
      toast(T('saved'), 'ok');
      closeModal();
      await loadAll();
    } catch (e) { toast(e.message, 'bad'); btn.disabled = false; }
  };
}

function dbRowFor(id) {
  return (S.clients || []).find((x) => x.id === id) || null;
}

function openClientDrawer(ib) {
  const target = ib || S.inbounds.find((i) => i.id === S.clientsIb) || S.inbounds[0];
  if (!target) { toast(T('pickInboundFirst'), 'bad'); return goto('inbounds'); }
  openModal(T('createClient'), `
    <div class="form-grid">
      <label class="field span-2"><span>${T('inbound')} — ${T('primaryLocation')}</span>
        <select id="cInboundSel">${S.inbounds.map((x) => `<option value="${esc(x.id)}" ${x.id === target.id ? 'selected' : ''}>${esc(x.name)} · ${esc((x.protocol || '').toUpperCase())}</option>`).join('')}</select></label>
      <label class="field span-2"><span>${T('extraLocations')} <span class="muted">(${T('upToFive')})</span></span>
        <div class="pick-list" id="cExtra">
          ${(S.inbounds || []).filter((x) => x.id !== target.id).map((x) =>
            `<label class="chk pick"><input type="checkbox" value="${esc(x.id)}" data-kind="local">
             <span>${esc(x.name)} · ${esc((x.protocol || '').toUpperCase())}</span></label>`).join('')}
          ${(S.remoteInbounds || []).map((x) =>
            `<label class="chk pick"><input type="checkbox" value="${esc(x.ref)}" data-kind="remote">
             <span>${esc(x.flag || '')} ${esc(x.node_name || 'node')} · ${esc(x.name || '')} · ${esc((x.protocol || '').toUpperCase())}</span></label>`).join('')}
          ${((S.inbounds || []).length + (S.remoteInbounds || []).length) < 2 ? `<span class="muted">${T('connectNodeFirst')}</span>` : ''}
        </div></label>
      <label class="field"><span>${T('configsPerClient')}</span><input id="cCount" type="number" min="1" max="10" value="2"></label>
      <label class="field"><span>${T('clientName')}</span><input id="cName" placeholder="Ali-phone"></label>
      <label class="field"><span>${T('limitGb')}</span><input id="cLimit" type="number" min="0" placeholder="0"></label>
      <label class="field"><span>${T('days')}</span><input id="cDays" type="number" min="0" placeholder="0"></label>
      <label class="field"><span>${T('expiresAt')}</span><input id="cExp" type="datetime-local"></label>
      <label class="field"><span>${T('ipLimit')}</span><input id="cIp" type="number" min="0" value="0"></label>
      <label class="field"><span>${T('connLimit')}</span><input id="cConn" type="number" min="0" value="0"></label>
      <label class="field"><span>${T('speed')}</span><input id="cSpeed" type="number" min="0" value="0"></label>
      <label class="field span-2"><span>${T('note')}</span><input id="cNote"></label>
    </div>
    <div class="modal-foot"><span class="grow"></span>
      <button class="btn" id="cCancel">${T('cancel')}</button>
      <button class="btn primary" id="cSave">${T('createClient')}</button></div>`);
  $('cCancel').onclick = closeModal;
  $$('#cExtra input').forEach((el) => (el.onchange = () => {
    const on = $$('#cExtra input:checked');
    if (on.length > 4) { el.checked = false; toast(T('upToFive'), 'bad'); }
  }));
  $('cSave').onclick = async () => {
    try {
      const extras = $$('#cExtra input:checked').map((el) => el.value).slice(0, 2);
      await api('POST', '/api/clients', {
        inbound_id: $('cInboundSel').value, name: $('cName').value || 'Client',
        limit_value: $('cLimit').value || 0, expires_days: $('cDays').value || 0,
        expires_at: ($('cExp') && $('cExp').value) ? $('cExp').value : '', 
        ip_limit: $('cIp').value || 0, connection_limit: $('cConn').value || 0,
        speed_limit_mbps: $('cSpeed').value || 0, note: $('cNote').value,
        extra_inbounds: extras, config_count: $('cCount') ? $('cCount').value || 2 : 2,
      });
      toast(T('created'), 'ok');
      closeModal();
      loadAll();
    } catch (e) { toast(e.message, 'bad'); }
  };
}

async function pingClient(id) {
  const cell = $('ping-' + id);
  const buttons = Array.from(document.querySelectorAll(`[data-cact="ping"][data-id="${id}"]`));
  buttons.forEach((b) => (b.disabled = true));
  if (cell) cell.textContent = '…';
  try {
    const r = await api('POST', `/api/clients/${id}/ping`);
    if (cell) cell.textContent = r.ok ? `${r.latency_ms} ms` : 'timeout';
    toast(r.ok ? `${T('latency')} ${r.host}:${r.port} → ${r.latency_ms} ms` : `Ping: ${r.error}`, r.ok ? 'ok' : 'bad');
  } catch (e) {
    if (cell) cell.textContent = '—';
    toast(e.message, 'bad');
  } finally {
    buttons.forEach((b) => (b.disabled = false));
  }
}

function showClientLinks(c) {
  const links = (c.links || []).map((l, i) => `
    <div class="cfg-row">
      <span class="cfg-idx">#${i + 1}</span>
      <code class="cfg-code">${esc(l)}</code>
      <button class="btn sm" data-copy="${esc(l)}">${T('copy')}</button>
    </div>`).join('');
  openModal(c.name, `
    <div class="summary-strip">${esc(c.inbound_name)} · ${esc(c.used_human)}${c.limit_bytes ? ' / ' + esc(c.limit_human) : ' / ∞'} · ${esc(shortDate(c.expires_at))}</div>
    <div class="toolbar" style="margin:12px 0">
      <button class="btn sm" data-copy="${esc(c.sub_url || (location.origin + '/sub/' + (c.sub_token || '')))}">${T('copySub')}</button>
      <button class="btn sm" id="clRegen">${T('newSecret')}</button>
      <button class="btn sm" id="clReset">Reset</button>
    </div>
    ${(c.locations || []).length > 1 ? `<div class="card">
        <div class="f-label" style="margin-bottom:8px">${T('extraLocations')} (${(c.locations || []).length})</div>
        <div class="kv-line">${(c.locations || []).map((loc) => `<span>${esc(loc.inbound || '')}
          → <b class="mono">${esc(loc.address || '')}</b>${loc.location ? ' · ' + esc(loc.location) : ''}</span>`).join('')}</div>
    </div>` : ''}
    <div class="card">
        <div class="f-label" style="margin-bottom:10px">${(c.links || []).length} config(s) · ${(c.locations || []).length || 1} ${T('extraLocations').toLowerCase()}</div>
        ${links || '<span class="muted">—</span>'}</div>
    <div class="muted" style="font-size:10.5px;margin-top:12px">
      ${T('lastGenerated')}: ${esc(c.last_config_at ? String(c.last_config_at).slice(0, 19).replace('T', ' ') : '\u2014')}
      &nbsp;·&nbsp; ${c.sub_fetches || 0} ${T('fetches')}
    </div>
    <div class="modal-foot"><span class="grow"></span><button class="btn" id="clClose">${T('close')}</button></div>`);
  $('clClose').onclick = closeModal;
  $$('[data-copy]').forEach((b) => (b.onclick = () => copyText(b.dataset.copy)));
  $('clRegen').onclick = async () => {
    if (!(await confirmAsync(T('newSecret'), T('confirmTitle')))) return;
    await api('POST', `/api/clients/${c.id}/regenerate`);
    closeModal(); loadAll();
  };
  $('clReset').onclick = async () => { await api('POST', `/api/clients/${c.id}/reset-usage`); closeModal(); loadAll(); };
}

/* ================================================================== LOGS */
async function pageLogs(view) {
  view.innerHTML = `<div class="notice">${T('logsNote')}</div>
    <div class="card"><div class="card-head"><h2>${T('nav_logs')}</h2><span class="grow"></span>
      <button class="btn sm" id="logRefresh">${T('refresh')}</button></div>
      <div id="logFull"><p class="muted"><span class="spin"></span></p></div></div>`;
  $('logRefresh').onclick = () => pageLogs(view);
  const r = await api('GET', '/api/activity');
  S.activity = r.items || [];
  const box = $('logFull');
  box.innerHTML = S.activity.length ? `<div class="tblwrap" style="border:0"><table>
    <thead><tr><th>${T('time')}</th><th>${T('user')}</th><th>${T('ip')}</th><th>${T('action')}</th><th>${T('detail')}</th></tr></thead>
    <tbody>${S.activity.map((a) => `<tr>
      <td class="muted">${esc((a.ts || '').slice(0, 19).replace('T', ' '))}</td>
      <td>${esc(a.username || '—')}</td><td class="mono">${esc(a.ip || '—')}</td>
      <td>${esc(a.action)}</td><td class="muted">${esc(a.detail || '')}</td></tr>`).join('')}</tbody></table></div>`
    : `<div class="empty"><b>${T('noLogs')}</b></div>`;
}

/* ================================================================== ADMINS */
async function pageAdmins(view) {
  view.innerHTML = `<div class="notice">${T('adminsNote')}</div>
    <div class="toolbar"><button class="btn primary" id="aAdd">${T('addAdmin')}</button>
      <span class="grow"></span><button class="btn sm" id="aRefresh">${T('refresh')}</button></div>
    <div class="tblwrap" id="adminsBox"><p class="muted" style="padding:12px"><span class="spin"></span></p></div>`;
  $('aAdd').onclick = () => adminModal();
  $('aRefresh').onclick = () => pageAdmins(view);
  await loadAdmins();
  const box = $('adminsBox');
  if (!box) return;
  box.innerHTML = `<table><thead><tr><th>${T('user')}</th><th>${T('role')}</th><th>${T('status')}</th><th>${T('actions')}</th></tr></thead>
    <tbody>${S.admins.map((a) => `<tr>
      <td><b style="font-weight:700">${esc(a.username)}</b>${a.username === (S.me && S.me.username) ? ' <span class="badge acc">you</span>' : ''}</td>
      <td><span class="badge ${a.role === 'owner' ? 'acc' : ''}">${a.role === 'owner' ? T('owner') : T('admin')}</span></td>
      <td><span class="badge ${a.enabled ? 'ok' : ''}">${a.enabled ? T('active') : T('disabled')}</span></td>
      <td><div style="display:flex;gap:5px;flex-wrap:wrap">
        <button class="btn sm" data-aact="edit" data-u="${esc(a.username)}">${T('edit')}</button>
        <button class="btn sm" data-aact="toggle" data-u="${esc(a.username)}" data-en="${a.enabled ? 1 : 0}">${a.enabled ? T('disable') : T('enable')}</button>
        <button class="btn sm danger" data-aact="delete" data-u="${esc(a.username)}">${T('del')}</button>
      </div></td></tr>`).join('')}</tbody></table>`;
  $$('[data-aact]', box).forEach((b) => (b.onclick = () => adminAction(b.dataset.aact, b.dataset.u, b.dataset.en)));
}

async function loadAdmins() {
  const r = await api('GET', '/api/admins');
  S.admins = r.items || [];
}

function adminModal(a) {
  const editing = !!a;
  openModal(editing ? `${T('edit')} · ${a.username}` : T('addAdmin'), `
    <div class="form-grid">
      <label class="field"><span>${T('user')}</span><input id="adUser" value="${esc(a ? a.username : '')}" ${editing ? 'readonly' : ''}></label>
      <label class="field"><span>${T('role')}</span><select id="adRole">
        <option value="admin" ${a && a.role === 'admin' ? 'selected' : ''}>${T('admin')}</option>
        <option value="owner" ${a && a.role === 'owner' ? 'selected' : ''}>${T('owner')}</option></select></label>
      <label class="field span-2"><span>${editing ? T('newPassword') : T('password')}</span><input id="adPass" type="password" placeholder="${editing ? '••••' : ''}"></label>
    </div>
    <div class="modal-foot"><span class="grow"></span>
      <button class="btn" id="adCancel">${T('cancel')}</button>
      <button class="btn primary" id="adSave">${T('save')}</button></div>`);
  $('adCancel').onclick = closeModal;
  $('adSave').onclick = async () => {
    try {
      const payload = { role: $('adRole').value };
      if ($('adPass').value) payload.password = $('adPass').value;
      if (editing) await api('PATCH', `/api/admins/${encodeURIComponent(a.username)}`, payload);
      else {
        payload.username = $('adUser').value;
        payload.password = $('adPass').value;
        await api('POST', '/api/admins', payload);
      }
      toast(T('saved'), 'ok');
      closeModal();
      goto('admins');
    } catch (e) { toast(e.message, 'bad'); }
  };
}

async function adminAction(act, username, enabled) {
  if (act === 'edit') {
    const a = S.admins.find((x) => x.username === username);
    return adminModal(a);
  }
  if (act === 'toggle') {
    try { await api('PATCH', `/api/admins/${encodeURIComponent(username)}`, { enabled: enabled === '1' ? false : true }); toast(T('saved'), 'ok'); goto('admins'); }
    catch (e) { toast(e.message, 'bad'); }
    return;
  }
  if (act === 'delete') {
    if (!(await confirmAsync(`${T('del')} ${username}?`, T('confirmTitle')))) return;
    try { await api('DELETE', `/api/admins/${encodeURIComponent(username)}`); toast(T('deleted'), 'ok'); goto('admins'); }
    catch (e) { toast(e.message, 'bad'); }
  }
}

/* ================================================================== SETTINGS */
function pageSettings(view) {
  const owner = isOwner();
  if (!APPR) APPR = Object.assign({}, BG_DEFAULTS, S.prefs || {});
  view.innerHTML = `
    <div class="grid2">
      <div class="card">
        <div class="card-head"><h2>${T('settingsAppearance')}</h2></div>
        <p class="muted" style="font-size:10.5px;margin-bottom:11px">${T('appearanceNote')}</p>
        <div class="form-grid">
          <label class="field"><span>${T('language')}</span>
            <select id="sLang"><option value="en" ${APPR.language === 'en' ? 'selected' : ''}>English</option>
            <option value="fa" ${APPR.language === 'fa' ? 'selected' : ''}>فارسی</option></select></label>
          <label class="field"><span>${T('uiStyle')}</span>
            <select id="sStyle"><option value="solid" ${APPR.style !== 'glass' ? 'selected' : ''}>${T('solid')}</option>
            <option value="glass" ${APPR.style === 'glass' ? 'selected' : ''}>${T('glass')}</option></select></label>
          <label class="field span-2"><span>${T('fontFamily')}</span>
            <select id="sFont">${FONTS_LIST.map(([id, label]) => `<option value="${id}" ${APPR.font === id ? 'selected' : ''}>${label}</option>`).join('')}</select></label>
        </div>
        <div class="field" style="margin-top:12px"><span>${T('theme')}</span>
          <div style="display:flex;gap:9px;flex-wrap:wrap" id="themeRow">
            ${THEMES.map(([id, col]) => `<button class="btn sm" data-theme-pick="${id}" style="border-color:${APPR.theme === id ? col : 'var(--line)'}">
              <span style="display:inline-block;width:9px;height:9px;border-radius:50%;background:${col};margin-inline-end:6px"></span>${id.replace('dark-', '')}</button>`).join('')}
          </div></div>
        <div class="field" style="margin-top:12px"><span>${T('music')}</span>
          <div class="music-row">
            <label class="chk"><input type="checkbox" id="sMusic" ${APPR.music === 'on' ? 'checked' : ''}> ${T('musicOn')}</label>
            <input type="range" id="sVol" min="0" max="100" value="${esc(APPR.music_volume || 40)}">
            <span class="muted" id="volVal">${esc(APPR.music_volume || 40)}</span>
          </div>
          <div class="music-lib" id="musicLib" style="margin-top:10px">${tracksHtml()}</div>
          <div class="toolbar" style="margin-top:9px">
            <label class="btn sm" style="cursor:pointer">${T('addMusic')}
              <input type="file" id="trkFile" accept="audio/*" style="display:none"></label>
            <span class="muted" style="font-size:10px">${T('musicPerUser')}</span>
          </div></div>

        <div class="field" style="margin-top:14px"><span>${T('background')}</span>
          <div class="bg-grid" id="bgGrid">${bgOptionsHtml()}</div>
          <div class="range-row" style="margin-top:10px">
            <span class="muted" style="font-size:10px;min-width:52px">${T('bgDim')}</span>
            <input type="range" id="sDim" min="0" max="80" value="${Number(APPR.bg_dim ?? 35)}">
            <span class="val" id="dimVal">${Number(APPR.bg_dim ?? 35)}%</span></div>
          <div class="range-row" style="margin-top:6px">
            <span class="muted" style="font-size:10px;min-width:52px">${T('bgBlur')}</span>
            <input type="range" id="sBlur" min="0" max="20" value="${Number(APPR.bg_blur ?? 0)}">
            <span class="val" id="blurVal">${Number(APPR.bg_blur ?? 0)}px</span></div>
          <div class="toolbar" style="margin-top:10px">
            <label class="btn sm" style="cursor:pointer">${T('uploadBg')}
              <input type="file" id="bgFile" accept="image/*" style="display:none"></label>
            <button class="btn sm danger" id="bgRemove">${T('removeBg')}</button>
            <label class="chk" style="margin-inline-start:8px"><input type="checkbox" id="bgEnabled" ${APPR.bg_enabled !== false ? 'checked' : ''}> ${T('bgEnabled')}</label>
          </div>
          <p class="muted" style="font-size:10px;margin-top:8px">${T('bgPerUser')}</p>
        </div>

        <div class="toolbar" style="margin-top:14px">
          <button class="btn primary" id="apprSave">${T('saveAppearance')}</button>
          <button class="btn" id="apprReset">${T('resetAppearance')}</button>
          <span class="badge warn" id="apprDirty" style="display:none">${T('unsavedChanges')}</span>
        </div>
      </div>

      <div class="card">
        <div class="card-head"><h2>${T('subTemplates')}</h2></div>
        <p class="muted" style="font-size:10.5px;margin-bottom:11px">${T('subTemplatesNote')}</p>
        <div class="tpl-grid">
          ${(S.subTemplates || []).map((t) => `
            <div class="tpl-card ${(APPR.sub_template || 'aurora') === t.id ? 'on' : ''}" data-tpl-pick="${esc(t.id)}">
              <div class="tpl-thumb tpl-${esc(t.id)}">${esc(t.name)}</div>
              <b>${esc(t.name)}</b>
              <span class="muted">${esc(t.hint || '')}</span>
              <span class="tpl-actions">
                <button class="btn sm" type="button" data-tpl-preview="${esc(t.id)}">${T('preview')}</button>
              </span>
            </div>`).join('')}
        </div>
        <p class="muted" style="font-size:10px;margin-top:9px">${T('subTemplatesApply')}</p>
      </div>

      <div class="card">
        <div class="card-head"><h2>${T('settingsAccount')}</h2></div>
        <p class="muted" style="font-size:10.5px;margin-bottom:11px">${T('accountNote')}</p>
        <div class="form-grid">
          <label class="field span-2"><span>${T('user')}</span><input value="${esc((S.me && S.me.username) || '')}" readonly></label>
          <label class="field"><span>${T('currentPassword')}</span><input id="aCur" type="password"></label>
          <label class="field"><span>${T('newPassword')}</span><input id="aNew" type="password"></label>
        </div>
        <div class="toolbar" style="margin-top:12px"><button class="btn" id="aSave">${T('changePassword')}</button></div>
      </div>
    </div>

    <div class="grid2">
      <div class="card">
        <div class="card-head"><h2>${T('settingsPanel')}</h2>${owner ? '' : `<span class="badge warn">${T('ownerOnly')}</span>`}</div>
        ${owner ? `<div class="form-grid">
          <label class="field span-2"><span>${T('publicBaseUrl')}</span><input id="sBase" value="${esc(S.settings.public_base_url || '')}" placeholder="https://your-app.up.railway.app"></label>
          <label class="field"><span>${T('defaultPort')}</span><input id="sPort" value="${esc(S.settings.default_port || '443')}"></label>
        </div>
        <div class="toolbar" style="margin-top:12px"><button class="btn primary" id="sSave">${T('saveSettings')}</button></div>`
      : `<p class="muted" style="font-size:11px">${T('ownerOnly')}</p>`}
      </div>

      ${owner ? `<div class="card">
        <div class="card-head"><h2>${T('xrayCore')}</h2></div>
        <div id="xrayBox"><p class="muted"><span class="spin"></span></p></div>
        <div class="toolbar" style="margin-top:11px">
          <button class="btn sm" id="xrayRefresh">${T('refresh')}</button>
          <button class="btn sm" id="xrayRestart">${T('restartCore')}</button>
        </div>
        <p class="muted" style="font-size:10px;margin-top:9px">${T('xrayNote')}</p>
      </div>` : `<div class="card"><div class="card-head"><h2>${T('diagnostics')}</h2></div>
        <div id="diagBox2"><p class="muted"><span class="spin"></span></p></div></div>`}
    </div>`;

  $('sLang').onchange = (e) => { APPR.language = e.target.value; markDraft(); };
  $('sStyle').onchange = (e) => { APPR.style = e.target.value; markDraft(); };
  $('sFont').onchange = (e) => { APPR.font = e.target.value; markDraft(); };
  $$('[data-theme-pick]').forEach((b) => (b.onclick = () => { APPR.theme = b.dataset.themePick; markThemePicks(); markDraft(); }));
  $('sMusic').onchange = (e) => { APPR.music = e.target.checked ? 'on' : 'off'; markDraft(); };
  $('sVol').oninput = (e) => { APPR.music_volume = Number(e.target.value); $('volVal').textContent = e.target.value; markDraft(); };
  $('sDim').oninput = (e) => { APPR.bg_dim = Number(e.target.value); $('dimVal').textContent = e.target.value + '%'; markDraft(); };
  $('sBlur').oninput = (e) => { APPR.bg_blur = Number(e.target.value); $('blurVal').textContent = e.target.value + 'px'; markDraft(); };
  $('bgEnabled').onchange = (e) => { APPR.bg_enabled = e.target.checked; markDraft(); };
  $$('[data-bg-pick]').forEach((el) => (el.onclick = () => { APPR.background = el.dataset.bgPick; APPR.bg_enabled = true; markBgPicks(); markDraft(); }));
  $('trkFile').onchange = (e) => uploadTrack(e.target.files && e.target.files[0]);
  wireMusicLib();
  $$('[data-tpl-pick]').forEach((el) => (el.onclick = (e) => {
    if (e.target.closest('[data-tpl-preview]')) return;
    APPR.sub_template = el.dataset.tplPick;
    $$('[data-tpl-pick]').forEach((x) => x.classList.toggle('on', x.dataset.tplPick === APPR.sub_template));
    markDraft();
  }));
  $$('[data-tpl-preview]').forEach((b) => (b.onclick = () => {
    const tok = (S.clients[0] || {}).sub_token || (S.inbounds[0] || {}).sub_token || '';
    if (!tok) { toast(T('needClientForPreview'), 'bad'); return; }
    window.open('/info/' + tok + '?template=' + b.dataset.tplPreview, '_blank');
  }));
  $('bgFile').onchange = (e) => uploadBackground(e.target.files && e.target.files[0]);
  $('bgRemove').onclick = () => removeBackground();
  $('apprSave').onclick = () => persistAppearance();
  $('apprReset').onclick = () => resetAppearance();
  $('aSave').onclick = async () => {
    try { await api('POST', '/api/me/password', { current: $('aCur').value, new: $('aNew').value }); toast(T('saved'), 'ok'); }
    catch (e) { toast(e.message, 'bad'); }
  };
  if ($('sSave')) $('sSave').onclick = async () => {
    try {
      await api('POST', '/api/settings', {
        public_base_url: $('sBase').value, default_port: $('sPort').value,
      });
      toast(T('saved'), 'ok');
      loadAll();
    } catch (e) { toast(e.message, 'bad'); }
  };
  if ($('xrayRefresh')) $('xrayRefresh').onclick = () => loadXrayInto();
  if ($('xrayRestart')) $('xrayRestart').onclick = async () => {
    try {
      const r = await api('POST', '/api/xray/restart');
      toast(r.ok ? `${T('restartCore')}: ${T('saved')} (${r.inbounds})` : (r.reason || T('failed')), r.ok ? 'ok' : 'bad');
      loadXrayInto();
    } catch (e) { toast(e.message, 'bad'); }
  };
  if ($('xrayBox')) loadXrayInto();
  if ($('diagBox2')) loadDiagInto('diagBox2');
}

async function loadDiagInto(id) {
  const box = $(id);
  if (!box) return;
  const r = await api('GET', '/api/diagnostics');
  box.innerHTML = (r.checks || []).map((c) => `
    <div style="display:flex;gap:9px;align-items:flex-start;padding:8px 0;border-bottom:1px solid var(--line)">
      <span class="badge ${c.level === 'ok' ? 'ok' : c.level === 'warn' ? 'warn' : ''}">${c.level}</span>
      <div style="min-width:0"><b style="font-weight:700;font-size:11px">${esc(c.title)}</b>
      <div class="muted" style="font-size:10px">${esc(c.detail)}</div></div></div>`).join('');
}

/* ================================================================== boot */
