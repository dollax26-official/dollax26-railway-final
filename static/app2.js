/* Dollax panel - part 2: nodes (panel-to-panel), sub-template picker, settings, boot.
   Loaded after app.js by pages.dashboard_html(). */
/* ------------------------------------------------------------------ nodes */
async function pageNodes(view) {
  const nodes = S.nodes || [];
  const remote = S.remoteInbounds || [];
  const rows = nodes.map((n) => `
    <tr>
      <td><b>${esc(n.flag || '')} ${esc(n.name || '(node)')}</b>
        <span class="sub mono">${esc(n.url || '')}</span></td>
      <td>${esc(n.location || '—')}</td>
      <td><span class="badge ${n.status === 'ok' ? 'ok' : n.status ? 'bad' : ''}">${esc(n.status || 'never synced')}</span></td>
      <td class="num">${n.inbound_count || 0}</td>
      <td class="muted sub">${esc((n.last_seen || '').slice(0, 19).replace('T', ' ') || '—')}</td>
      <td class="num" style="white-space:nowrap">
        <button class="btn sm" data-nact="refresh" data-id="${esc(n.id)}">${T('refresh')}</button>
        <button class="btn sm" data-nact="toggle" data-id="${esc(n.id)}">${n.enabled ? T('disable') : T('enable')}</button>
        <button class="btn sm danger" data-nact="del" data-id="${esc(n.id)}">${T('remove')}</button></td>
    </tr>`).join('');
  const rrows = remote.map((ib) => `
    <tr>
      <td>${esc(ib.flag || '')} ${esc(ib.node_name || '')}</td>
      <td>${esc(ib.location || '—')}</td>
      <td><b>${esc(ib.name || '')}</b><span class="sub mono">${esc((ib.protocol || '').toUpperCase())} · ${esc(ib.address || '')}:${esc(ib.port || '')}</span></td>
      <td>${esc((ib.network || '').toUpperCase())}/${esc((ib.security || '').toUpperCase())}</td>
      <td class="num">${ib.clients || 0}</td>
    </tr>`).join('');

  view.innerHTML = `
    <div class="card">
      <div class="card-head"><h2>${T('nav_nodes')}</h2></div>
      <p class="muted" style="font-size:10.5px;margin-bottom:11px">${T('nodesNote')}</p>
      <div class="form-grid">
        <label class="field span-2"><span>${T('nodeToken')}</span>
          <span class="inline-input"><input id="nToken" readonly value="${esc(S.nodeToken || '')}">
          <button class="btn sm" type="button" id="nCopyToken">${T('copy')}</button>
          <button class="btn sm" type="button" id="nRotate">${T('rotate')}</button></span></label>
      </div>
      <div class="form-grid" style="margin-top:12px">
        <label class="field"><span>${T('nodeName')}</span><input id="nName" placeholder="Frankfurt"></label>
        <label class="field"><span>${T('nodeUrl')}</span><input id="nUrl" placeholder="https://other-panel.up.railway.app"></label>
        <label class="field"><span>${T('nodeTokenLbl')}</span><input id="nTok" placeholder="${T('nodeTokenHint')}"></label>
        <label class="field"><span>${T('nodeLocation')}</span><input id="nLoc" placeholder="Germany"></label>
        <label class="field"><span>${T('nodeFlag')}</span><input id="nFlag" maxlength="6" placeholder="DE"></label>
      </div>
      <div class="toolbar" style="margin-top:12px">
        <button class="btn primary" id="nAdd">${T('addNode')}</button>
        <button class="btn sm" id="nRefreshAll">${T('refreshAll')}</button>
      </div>
    </div>
    <div class="tblwrap">
      ${nodes.length ? `<table><thead><tr><th>${T('nodeName')}</th><th>${T('nodeLocation')}</th>
        <th>${T('status')}</th><th>${T('inbounds')}</th><th>${T('lastSeen')}</th><th>${T('actions')}</th></tr></thead>
        <tbody>${rows}</tbody></table>` : `<div class="empty"><b>${T('noNodes')}</b>${T('noNodesHint')}</div>`}
    </div>
    <div class="tblwrap">
      <div class="card-head" style="padding:12px 14px 0"><h2 style="font-size:13px">${T('remoteInbounds')}</h2></div>
      ${rrows ? `<table><thead><tr><th>${T('nav_nodes')}</th><th>${T('nodeLocation')}</th><th>${T('inbound')}</th>
        <th>${T('transport')}</th><th>${T('clients')}</th></tr></thead><tbody>${rrows}</tbody></table>`
        : `<div class="empty">${T('noRemoteInbounds')}</div>`}
    </div>`;

  if ($('nCopyToken')) $('nCopyToken').onclick = () => copyText($('nToken').value);
  if ($('nRotate')) $('nRotate').onclick = async () => {
    try {
      const r = await api('POST', '/api/node/token/rotate');
      S.nodeToken = r.token;
      $('nToken').value = r.token;
      toast(T('rotate') + ': ' + T('saved'), 'ok');
    } catch (e) { toast(e.message, 'bad'); }
  };
  if ($('nAdd')) $('nAdd').onclick = async () => {
    const btn = $('nAdd');
    btn.disabled = true;
    try {
      const r = await api('POST', '/api/nodes', {
        name: $('nName').value, url: $('nUrl').value, token: $('nTok').value,
        location: $('nLoc').value, flag: $('nFlag').value,
      });
      toast(r.warning ? T('nodeAddedWarn') + ': ' + r.warning : T('nodeAdded'), r.warning ? 'bad' : 'ok');
      S.nodes = r.items || [];
      await loadAll();
      goto('nodes');
    } catch (e) { toast(e.message, 'bad'); btn.disabled = false; }
  };
  if ($('nRefreshAll')) $('nRefreshAll').onclick = async () => {
    for (const n of nodes) { try { await api('POST', '/api/nodes/' + n.id + '/refresh'); } catch (e) {} }
    await loadAll();
    goto('nodes');
    toast(T('refreshed'), 'ok');
  };
  $$('[data-nact]').forEach((b) => (b.onclick = async () => {
    const id = b.dataset.id;
    try {
      if (b.dataset.nact === 'refresh') { const r = await api('POST', '/api/nodes/' + id + '/refresh'); S.nodes = r.items || []; }
      else if (b.dataset.nact === 'toggle') {
        const n = (S.nodes || []).find((x) => x.id === id) || {};
        await api('PATCH', '/api/nodes/' + id, { enabled: !n.enabled });
      } else if (b.dataset.nact === 'del') {
        if (!(await confirmAsync(T('confirmDelete')))) return;
        await api('DELETE', '/api/nodes/' + id);
      }
      await loadAll();
      goto('nodes');
    } catch (e) { toast(e.message, 'bad'); }
  }));
}

/* ------------------------------------------------------------------ shell */
function navList() {
  const items = [['overview', T('nav_overview'), '◈'], ['inbounds', T('nav_inbounds'), '≋'],
    ['clients', T('nav_clients'), '☰'], ['nodes', T('nav_nodes'), '⬢'], ['logs', T('nav_logs'), '≡']];
  if (isOwner()) items.push(['admins', T('nav_admins'), '★']);
  items.push(['settings', T('nav_settings'), '⚙']);
  return items.map(([p, label, ic]) =>
    `<button data-p="${p}" class="${S.page === p ? 'on' : ''}"><span class="ic">${ic}</span>${esc(label)}</button>`).join('');
}
const isOwner = () => !!(S.me && S.me.role === 'owner');

function buildShell() {
  const el = $('root');
  el.innerHTML = `
  <div class="bg-layer" id="bgLayer" style="display:none"></div>
  <div class="shell">
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-mark">D</div>
        <div>
          <div class="brand-name">${esc((S.settings && S.settings.panel_name) || 'Dollax')}</div>
          <div class="brand-sub">${T('brandSub')}${S.me && S.me.version ? ' · v' + esc(S.me.version) : ''}</div>
        </div>
      </div>
      <nav class="nav" id="nav">${navList()}</nav>
      <div class="side-meta"><span id="sbIn">0</span><span id="sbCl">0</span></div>
      <div class="side-foot"><button class="logout" id="logout">${T('logout')}</button></div>
    </aside>
    <main class="main">
      <header class="topbar">
        <div class="top-title" id="pageTitle">${T('nav_overview')}</div>
        <div class="top-right">
          <span class="pill link" id="langPill">${LANG === 'fa' ? 'EN' : 'فارسی'}</span>
          <span class="pill" id="hostPill">${esc((S.me && S.me.host) || 'host')}</span>
          <span class="pill ok">● ${T('running')}</span>
        </div>      </header>
      <div class="content" id="page"></div>
    </main>
  </div>`;

  $$('#nav button').forEach((b) => (b.onclick = () => goto(b.dataset.p)));
  $('langPill').onclick = () => savePrefs({ language: LANG === 'fa' ? 'en' : 'fa' });
  $('logout').onclick = async () => { await fetch('/logout', { method: 'POST', credentials: 'same-origin' }); location.href = '/login'; };
}

function goto(page) {
  const allowed = ['overview', 'inbounds', 'clients', 'logs', 'settings'];
  if (page === 'admins' && !isOwner()) page = 'overview';
  S.page = allowed.concat(['admins']).includes(page) ? page : 'overview';
  const titles = { overview: T('nav_overview'), inbounds: T('nav_inbounds'), clients: T('nav_clients'), logs: T('nav_logs'), admins: T('nav_admins'), settings: T('nav_settings') };
  $('pageTitle').textContent = titles[S.page];
  $$('#nav button').forEach((b) => b.classList.toggle('on', b.dataset.p === S.page));
  render();
}

/* ------------------------------------------------------------------ data */
async function loadAll() {
  const [me, summary, settings, protocols, inbounds, clients, backgrounds] = await Promise.all([
    api('GET', '/api/me'), api('GET', '/api/summary'), api('GET', '/api/settings'),
    api('GET', '/api/protocols'), api('GET', '/api/inbounds'), api('GET', '/api/clients'),
    api('GET', '/api/backgrounds'),
  ]);
  try { const trk = await api('GET', '/api/me/tracks'); S.tracks = trk.items || []; }
  catch (e) { S.tracks = S.tracks || []; }
  try {
    const nd = await api('GET', '/api/nodes');
    S.nodes = nd.items || [];
    S.remoteInbounds = nd.remote_inbounds || [];
    S.nodeToken = nd.token || S.nodeToken || '';
  } catch (e) { S.nodes = S.nodes || []; S.remoteInbounds = S.remoteInbounds || []; }
  try { const tp = await api('GET', '/api/subtemplates'); S.subTemplates = tp.items || []; }
  catch (e) { S.subTemplates = S.subTemplates || []; }
  S.bgPresets = (backgrounds && backgrounds.presets) || [];
  S.bgCustom = !!(backgrounds && backgrounds.custom);
  S.me = me;
  S.summary = summary;
  S.settings = settings.settings || {};
  S.protocols = protocols;
  S.inbounds = inbounds.items || [];
  S.clients = clients.items || [];
  S.prefs = Object.assign({ language: 'en', theme: 'dark-green', style: 'solid', music: 'off', music_volume: 40 }, me.prefs || {});
  // NOTE: the appearance draft (APPR) is deliberately NOT cleared here — clearing it made
  // unsaved tweaks vanish whenever anything reloaded the data.
  if (!S.clientsIb && S.inbounds.length) S.clientsIb = S.inbounds[0].id;
  applyPrefs();
  buildShell();
  render();
}

function render() {
  const page = $('page');
  if (!page) return;
  const inEl = $('sbIn'), clEl = $('sbCl');
  if (inEl) inEl.textContent = S.inbounds.length + ' inbounds' +
    ((S.remoteInbounds && S.remoteInbounds.length) ? ' + ' + S.remoteInbounds.length + ' node' : '');
  if (clEl) clEl.textContent = S.clients.length + ' clients';
  if (S.page === 'overview') pageOverview(page);
  else if (S.page === 'inbounds') pageInbounds(page);
  else if (S.page === 'clients') pageClients(page);
  else if (S.page === 'nodes') pageNodes(page);
  else if (S.page === 'logs') pageLogs(page);
  else if (S.page === 'admins') pageAdmins(page);
  else pageSettings(page);
}

/* ================================================================== OVERVIEW */
function pageOverview(view) {
  const s = S.summary || {};
  view.innerHTML = `
    <div class="grid4">
      <div class="stat"><div class="lbl">${T('ov_inbounds')}</div><div class="val">${s.inbounds || 0}</div><div class="sub">${s.native_inbounds || 0} ${T('native')}</div></div>
      <div class="stat"><div class="lbl">${T('ov_clients')}</div><div class="val">${s.clients || 0}</div><div class="sub">${s.active_clients || 0} ${T('active')}</div></div>
      <div class="stat"><div class="lbl">${T('ov_traffic')}</div><div class="val">${esc(s.total_used_human || '0 B')}</div><div class="sub">${esc(s.transport || 'WSS')}</div></div>
      <div class="stat"><div class="lbl">${T('path')}</div><div class="val" style="font-size:14px">${esc(s.host || '')}</div><div class="sub">:${esc(s.default_port || '443')}</div></div>
    </div>

    <div class="grid2">
      <div class="card">
        <div class="card-head"><h2>${T('diagnostics')}</h2><span class="grow"></span>
          <button class="btn sm" id="diagRun">${T('refresh')}</button></div>
        <div id="diagBox"><p class="muted">${T('loading')}</p></div>
      </div>
      <div class="card">
        <div class="card-head"><h2>${T('gettingStarted')}</h2></div>
        <ol class="muted" style="padding-inline-start:18px;display:grid;gap:7px;font-size:11.5px">
          <li>${T('nav_inbounds')} → ${T('addInbound')}</li>
          <li>${T('nav_clients')} → ${T('addClient')} <span class="muted">(${T('selfNodeHint')})</span></li>
          <li>${T('copySub')} → ${T('importInClient') || 'import in the client app'}</li>
        </ol>
        <div class="toolbar" style="margin-top:14px">
          <button class="btn primary" id="ovAdd">${T('addInbound')}</button>
          <button class="btn" id="ovClient">${T('addClient')}</button>
        </div>
      </div>
    </div>

    <div class="card">
      <div class="card-head"><h2>${T('recentActivity')}</h2><span class="grow"></span>
        <button class="btn sm" id="ovLogs">${T('nav_logs')}</button></div>
      <div id="logBox"><p class="muted">${T('loading')}</p></div>
    </div>`;

  $('ovAdd').onclick = () => { goto('inbounds'); setTimeout(() => openBuilder(), 20); };
  $('ovClient').onclick = () => { goto('clients'); setTimeout(() => openClientDrawer(), 20); };
  $('ovLogs').onclick = () => goto('logs');
  $('diagRun').onclick = loadDiag;
  loadDiag();
  loadActivityBox();
}

async function loadDiag() {
  const box = $('diagBox');
  if (!box) return;
  box.innerHTML = `<p class="muted"><span class="spin"></span></p>`;
  const r = await api('GET', '/api/diagnostics');
  S.diag = r.checks || [];
  box.innerHTML = S.diag.map((c) => `
    <div style="display:flex;gap:10px;align-items:flex-start;padding:9px 0;border-bottom:1px solid var(--line)">
      <span class="badge ${c.level === 'ok' ? 'ok' : c.level === 'warn' ? 'warn' : ''}">${c.level === 'ok' ? T('diagOk') : c.level === 'warn' ? T('diagWarn') : T('diagInfo')}</span>
      <div style="min-width:0"><b style="font-weight:700;font-size:11.5px">${esc(c.title)}</b>
        <div class="muted" style="font-size:10.5px">${esc(c.detail)}</div>
        ${c.fix ? `<div style="font-size:10.5px;color:var(--accent-2)">${esc(c.fix)}</div>` : ''}</div>
    </div>`).join('');
}

async function loadActivityBox(limit) {
  const box = $('logBox');
  if (!box) return;
  const r = await api('GET', '/api/activity');
  S.activity = r.items || [];
  const rows = S.activity.slice(0, limit || 8);
  box.innerHTML = rows.length ? `<div class="tblwrap" style="border:0;background:transparent"><table>
      <thead><tr><th>${T('time')}</th><th>${T('user')}</th><th>${T('ip')}</th><th>${T('action')}</th></tr></thead>
      <tbody>${rows.map((a) => `<tr>
        <td class="muted">${esc((a.ts || '').slice(0, 19).replace('T', ' '))}</td>
        <td>${esc(a.username || '—')}</td><td class="mono">${esc(a.ip || '—')}</td><td>${esc(a.action)}</td>
      </tr>`).join('')}</tbody></table></div>`
    : `<div class="empty"><b>${T('noLogs')}</b></div>`;
}

/* ================================================================== INBOUNDS */
function inboundCard(ib) {
  const badges = [
    `<span class="badge acc">${esc((ib.protocol || '').toUpperCase())}</span>`,
    `<span class="badge">${esc((ib.network || 'ws').toUpperCase())}</span>`,
    `<span class="badge">${esc((ib.security || 'none').toUpperCase())}</span>`,
  ];
  badges.push(ib.expired ? `<span class="badge bad">${T('expired')}</span>`
    : !ib.enabled ? `<span class="badge">${T('disabled')}</span>`
      : ib.native ? `<span class="badge ok">${T('native')}</span>` : `<span class="badge warn">${T('needsBridge')}</span>`);
  const pct = ib.limit_bytes ? Math.min(100, Math.round((ib.used_bytes / ib.limit_bytes) * 100)) : 0;
  return `
  <article class="ib-card ${ib.enabled ? '' : 'off'}" data-id="${esc(ib.id)}">
    <div class="ib-row">
      <input type="checkbox" data-sel="${esc(ib.id)}" ${S.ibSel.has(ib.id) ? 'checked' : ''} style="width:auto;margin-top:4px">
      <div style="min-width:0;flex:1">
        <div class="ib-name">${esc(ib.name)} ${badges.join('')}</div>
        <div class="ib-meta">${esc(ib.address || '—')}:${esc(ib.port)} · ${T('path')} <code>${esc(ib.path)}</code> · ${esc(ib.config_count || 1)} ${T('configs')}</div>
      </div>
      <div style="display:flex;gap:6px">
        <button class="btn sm" data-act="edit" data-id="${esc(ib.id)}">${T('edit')}</button>
        <button class="btn sm" data-act="config" data-id="${esc(ib.id)}">${T('config')}</button>
      </div>
    </div>
    <div class="ib-kv">
      <div><div class="lbl">${T('clients')}</div><b>${ib.client_count == null ? 0 : ib.client_count}</b></div>
      <div><div class="lbl">${T('traffic')}</div><b>${T('downShort')} ${esc(ib.down_human || '0 B')} &nbsp; ${T('upShort')} ${esc(ib.up_human || '0 B')}${ib.limit_bytes ? ' / ' + esc(ib.limit_human) : ''}</b></div>
      <div><div class="lbl">${T('expiry')}</div><b>${esc(shortDate(ib.expires_at))}</b></div>
      <div><div class="lbl">${T('status')}</div><b>${ib.enabled ? T('active') : T('disabled')}</b></div>
    </div>
    <div class="bar"><i style="width:${pct}%"></i></div>
    <div class="ib-foot">
      <button class="btn sm" data-act="toggle" data-id="${esc(ib.id)}">${ib.enabled ? T('disable') : T('enable')}</button>
      <button class="btn sm" data-act="clients" data-id="${esc(ib.id)}">${T('clients')}</button>
      <button class="btn sm" data-act="ping" data-id="${esc(ib.id)}">${T('ping')}</button>
      <button class="btn sm" data-act="regenerate" data-id="${esc(ib.id)}">${T('newSecret')}</button>
      <span class="grow"></span>
      <button class="btn sm danger" data-act="delete" data-id="${esc(ib.id)}">${T('del')}</button>
    </div>
  </article>`;
}

function pageInbounds(view) {
  const q = S.ibQ.toLowerCase();
  const list = S.inbounds.filter((ib) => {
    if (S.ibFilter !== 'all' && (ib.protocol || '') !== S.ibFilter) return false;
    if (!q) return true;
    return (ib.name + ' ' + ib.path + ' ' + (ib.address || '') + ' ' + ib.protocol).toLowerCase().includes(q);
  });
  view.innerHTML = `
    <div class="toolbar">
      <button class="btn primary" id="addInbound">${T('addInbound')}</button>
      <input id="ibSearch" placeholder="${T('search')}" value="${esc(S.ibQ)}" style="max-width:230px">
      <select id="ibFilter" style="max-width:180px">
        ${['all', 'vless', 'vmess', 'trojan', 'shadowsocks'].map((p) => `<option value="${p}" ${S.ibFilter === p ? 'selected' : ''}>${p === 'all' ? T('allProtocols') : p.toUpperCase()}</option>`).join('')}
      </select>
      <span class="grow"></span>
      <button class="btn sm" id="ibSelAll">${T('selectAll')}</button>
      <button class="btn sm" id="ibEnable">${T('enable')}</button>
      <button class="btn sm" id="ibDisable">${T('disable')}</button>
      <button class="btn sm danger" id="ibDelete">${T('deleteSelected')}</button>
      <button class="btn sm" id="ibRefresh">${T('refresh')}</button>
    </div>
    <div class="ib-list">
      ${list.length ? list.map(inboundCard).join('') : `<div class="empty"><b>${T('apiNoInbounds')}</b>${T('apiNoInboundsSub')}</div>`}
    </div>`;

  $('addInbound').onclick = () => openBuilder();
  $('ibRefresh').onclick = loadAll;
  $('ibSearch').oninput = (e) => { S.ibQ = e.target.value; pageInbounds(view); };
  $('ibFilter').onchange = (e) => { S.ibFilter = e.target.value; pageInbounds(view); };
  $('ibSelAll').onclick = () => {
    const ids = list.map((i) => i.id);
    const all = ids.length && ids.every((id) => S.ibSel.has(id));
    ids.forEach((id) => (all ? S.ibSel.delete(id) : S.ibSel.add(id)));
    pageInbounds(view);
  };
  $('ibEnable').onclick = () => bulkInbound('enable');
  $('ibDisable').onclick = () => bulkInbound('disable');
  $('ibDelete').onclick = async () => {
    if (!S.ibSel.size) return toast(T('noSelection'), 'bad');
    if (!(await confirmAsync(`${T('del')} ${S.ibSel.size}?`, T('confirmTitle')))) return;
    bulkInbound('delete');
  };
  $$('[data-sel]', view).forEach((cb) => (cb.onchange = () => {
    cb.checked ? S.ibSel.add(cb.dataset.sel) : S.ibSel.delete(cb.dataset.sel);
  }));
  $$('[data-act]', view).forEach((b) => (b.onclick = () => inboundAction(b.dataset.act, b.dataset.id)));
}

async function bulkInbound(action) {
  await api('POST', '/api/inbounds/bulk', { ids: Array.from(S.ibSel), action });
  S.ibSel.clear();
  toast(T('saved'), 'ok');
  loadAll();
}

async function inboundAction(act, id) {
  const ib = S.inbounds.find((i) => i.id === id);
  if (!ib) return;
  if (act === 'edit') return openBuilder(ib);
  if (act === 'config') return showInboundConfig(ib);
  if (act === 'clients') { S.clientsIb = id; goto('clients'); return; }
  if (act === 'subpage') return window.open(`/info/${ib.sub_token}`, '_blank');
  if (act === 'toggle') { await api('POST', `/api/inbounds/${id}/toggle`); return loadAll(); }
  if (act === 'ping') {
    const r = await api('POST', `/api/inbounds/${id}/ping`);
    toast(r.ok ? `${T('latency')} ${r.host}:${r.port} → ${r.latency_ms} ms` : `Ping: ${r.error}`, r.ok ? 'ok' : 'bad');
    return;
  }
  if (act === 'regenerate') {
    if (!(await confirmAsync(T('newSecret'), T('confirmTitle')))) return;
    await api('POST', `/api/inbounds/${id}/regenerate`);
    toast(T('updated'), 'ok');
    return loadAll();
  }
  if (act === 'delete') {
    if (!(await confirmAsync(`${T('del')} “${ib.name}”?`, T('confirmTitle')))) return;
    await api('DELETE', `/api/inbounds/${id}`);
    toast(T('deleted'), 'ok');
    return loadAll();
  }
}

/* -------------------------------------------------- builder (Vodiwalker-style) */
function optCard(group, value, label, sub, icon, on) {
  return `<label class="ib-opt ${on ? 'on' : ''}" data-${group}="${value}">
    <input type="radio" name="b-${group}" value="${value}" ${on ? 'checked' : ''}>
    <span class="ib-opt-icon">${icon}</span><span><b>${label}</b><small>${sub}</small></span></label>`;
}

const B = { proto: 'vless', net: 'ws', sec: 'tls' };

function openBuilder(ib) {
  const editing = !!ib;
  const b = ib || { port: (S.settings && S.settings.default_port) || 443, fingerprint: 'chrome', config_count: 1, enabled: 1 };
  const opt = (id, label, pairs, val) => `<label class="field"><span>${label}</span><select id="${id}">${
    pairs.map((p) => `<option value="${p[0]}" ${String(val) === String(p[0]) ? 'selected' : ''}>${p[1]}</option>`).join('')}</select></label>`;
  const panelHost = ((S.settings && S.settings.public_base_url) || '')
    .replace(/^https?:\/\//, '').replace(/\/.*$/, '')
    || ((S.me && S.me.host) || '');

  const body = `<div class="builder">
    <div class="form-grid">
      ${opt('bProto', T('protocol'), [['vless', 'VLESS'], ['vmess', 'VMess'], ['trojan', 'Trojan'], ['shadowsocks', 'Shadowsocks'], ['wireguard', 'WireGuard'], ['hysteria2', 'Hysteria2'], ['tuic', 'TUIC'], ['socks', 'SOCKS5'], ['http', 'HTTP']], b.protocol || 'vless')}
      ${opt('bNet', T('transport'), [['ws', 'WebSocket'], ['xhttp', 'XHTTP'], ['grpc', 'gRPC'], ['httpupgrade', 'HTTPUpgrade'], ['tcp', 'TCP']], b.network || 'ws')}
      ${opt('bSec', T('security'), [['tls', 'TLS'], ['reality', 'Reality'], ['none', 'None']], b.security || 'tls')}
      ${opt('bFp', T('fFp'), FP_CHOICES.map((f) => [f, f]), b.fingerprint || 'chrome')}
    </div>

    <div class="form-grid" style="margin-top:12px">
      <label class="field"><span>${T('fName')}</span><input id="bName" value="${esc(b.name || '')}" placeholder="Frankfurt-01"></label>
      <label class="field"><span>${T('fAddress')}</span>
        <span class="inline-input"><input id="bAddress" value="${esc(b.address || '')}" placeholder="${esc(panelHost || 'panel.up.railway.app')}">
        <button class="btn sm" type="button" id="bUsePanel">${T('usePanelDomain')}</button></span></label>
      <label class="field"><span>${T('fPort')}</span><input id="bPort" type="number" min="1" max="65535" value="${esc(b.port || 443)}"></label>
      <label class="field" id="grpPath"><span>${T('fPath')}</span><input id="bPath" value="${esc(b.path || '')}" placeholder="/ws/x (empty = auto)"></label>
      <label class="field" id="grpHost"><span>${T('fHost')}</span><input id="bHost" value="${esc(b.host_header || '')}" placeholder="empty = address"></label>
      <label class="field" id="grpSni"><span>${T('fSni')}</span><input id="bSni" value="${esc(b.sni || '')}" placeholder="empty = host"></label>
      <label class="field" id="grpWgPub"><span>${T('wgPublicKey')}</span><input id="bWgPub" value="${esc(b.wg_public_key || '')}" placeholder="server public key"></label>
      <label class="field" id="grpWgAddr"><span>${T('wgAddress')}</span><input id="bWgAddr" value="${esc(b.wg_address || '')}" placeholder="10.7.0.2/32"></label>
    </div>

    <div class="form-grid" style="margin-top:12px">
      <label class="field"><span>${T('fLimit')}</span><input id="bLimitGb" type="number" min="0" value="${b.limit_bytes ? Math.round(b.limit_bytes / 1073741824) : ''}" placeholder="0"></label>
      <label class="field"><span>${T('fDays')}</span><input id="bDays" type="number" min="0" value="${b.expires_at ? Math.max(0, Math.ceil((new Date(b.expires_at) - Date.now()) / 86400000)) : ''}" placeholder="0"></label>
      <label class="field"><span>${T('fCount')}</span><input id="bConfigCount" type="number" min="1" max="40" value="${esc(b.config_count || 1)}"></label>
      <label class="field"><span>${T('fClientLimit')}</span><input id="bClientLimit" type="number" min="0" value="${esc(b.client_limit || 0)}"></label>
    </div>

    <div class="field" style="margin-top:12px"><span>${T('fNote')}</span><input id="bNote" value="${esc(b.note || '')}"></div>
    <label class="chk" style="margin-top:12px"><input type="checkbox" id="bEnabled" ${b.enabled === 0 || b.enabled === false ? '' : 'checked'}> ${T('enabledLbl')}</label>

    <div class="summary-strip" id="bSummary" style="margin-top:14px"></div>
    <div class="live-preview" style="margin-top:10px"><code id="bPreview"></code></div>
    <p class="muted" id="bWarn" style="margin-top:10px;font-size:10.5px"></p>
  </div>
  <div class="modal-foot">
    <span class="grow"></span>
    <button class="btn" id="bCancel">${T('cancel')}</button>
    <button class="btn primary" id="bSave">${editing ? T('editInbound') : T('createInbound')}</button>
  </div>`;

  openModal(editing ? T('editInbound') : T('createInbound'), body);
  $('bCancel').onclick = closeModal;
  $('bSave').onclick = () => saveInbound(editing ? ib.id : null);
  if ($('bUsePanel')) $('bUsePanel').onclick = () => {
    $('bAddress').value = panelHost;
    if ($('bHost')) $('bHost').value = panelHost;
    if ($('bSni')) $('bSni').value = panelHost;
    syncBuilder();
  };
  ['bName', 'bAddress', 'bPort', 'bPath', 'bHost', 'bSni', 'bConfigCount', 'bDays', 'bLimitGb',
   'bProto', 'bNet', 'bSec', 'bFp', 'bWgPub', 'bWgAddr'].forEach((id) => {
    const el = $(id);
    if (el) el.addEventListener(el.tagName === 'SELECT' ? 'change' : 'input', syncBuilder);
  });
  syncBuilder();
}

function show(id, on) { const el = $(id); if (el) el.style.display = on ? '' : 'none'; }

function syncBuilder() {
  const net = ($('bNet') || {}).value || 'ws';
  const sec = ($('bSec') || {}).value || 'tls';
  const urlLike = net === 'ws' || net === 'xhttp' || net === 'httpupgrade';
  show('grpPath', urlLike);
  show('grpHost', urlLike);
  show('grpSni', sec !== 'none' && net !== 'xhttp');
  const proto = ($('bProto') || {}).value || 'vless';
  show('grpWgPub', proto === 'wireguard');
  show('grpWgAddr', proto === 'wireguard');
  const w = $('bWarn');
  if (w) {
    const external = (proto === 'wireguard' || proto === 'hysteria2' || proto === 'tuic');
    const fallback = (proto === 'socks' || proto === 'http');
    if (proto === 'wireguard') w.textContent = T('wgNote');
    else if (external) w.textContent = T('udpNote');
    else if (fallback) w.textContent = T('proxyNote');
    else w.textContent = (proto === 'vless' || proto === 'trojan') ? T('vlessNote') : T('bridgeNote');
    w.style.color = external ? 'var(--warning)' : 'var(--muted)';
  }
  builderSummary();
}

function builderPayload() {
  const g = (id) => { const el = $(id); return el ? el.value : ''; };
  return {
    name: g('bName'), protocol: g('bProto'), network: g('bNet'), security: g('bSec'),
    address: g('bAddress'), port: g('bPort'), path: g('bPath'), fingerprint: g('bFp'),
    host_header: g('bHost'), sni: g('bSni'),
    wg_public_key: g('bWgPub'), wg_address: g('bWgAddr'),
    limit_value: g('bLimitGb'), expires_days: g('bDays'),
    client_limit: g('bClientLimit'), config_count: g('bConfigCount'),
    note: g('bNote'), enabled: $('bEnabled') ? $('bEnabled').checked : true,
  };
}

function builderSummary() {
  const d = builderPayload();
  const strip = $('bSummary');
  if (!strip) return;
  const cnt = Math.max(1, Math.min(40, parseInt(d.config_count || '1', 10) || 1));
  strip.innerHTML = `<b>${esc(d.protocol.toUpperCase())}</b> · ${esc(d.network.toUpperCase())} · ${esc(d.security.toUpperCase())}
    &nbsp;→&nbsp; <b>${esc(d.address || '(address)')}:${esc(d.port || 443)}</b>
    &nbsp;·&nbsp; ${T('path')} <b>${esc(d.path || T('autoPath'))}</b>
    &nbsp;·&nbsp; <b>${cnt}</b> ${T('configs')}
    ${d.limit_value ? `&nbsp;·&nbsp; ${esc(d.limit_value)} GB` : ''}
    ${d.expires_days ? `&nbsp;·&nbsp; ${esc(d.expires_days)} d` : ''}`;
  const pre = $('bPreview');
  if (pre) pre.textContent = `${d.protocol}://<credential>@${d.address || 'your-host'}:${d.port || 443}?type=${d.network}&security=${d.security}&path=${encodeURIComponent(d.path || '/ws/demo')}&sni=${encodeURIComponent(d.sni || d.address || 'your-host')}&fp=${d.fingerprint}`;
}

async function saveInbound(id) {
  const d = builderPayload();
  if (!d.name) return toast(T('fName'), 'bad');
  try {
    if (id) { await api('PATCH', `/api/inbounds/${id}`, d); toast(T('updated'), 'ok'); }
    else { await api('POST', '/api/inbounds', d); toast(T('created'), 'ok'); }
    closeModal();
    loadAll();
  } catch (e) { toast(e.message, 'bad'); }
}

async function showInboundConfig(ib) {
  const r = await api('GET', `/api/inbounds/${ib.id}/info`);
  const sub = r.sub_url;
  const self = r.self_link || '';
  const cards = (r.clients || []).map((c) => `
    <div class="client-card">
      <div class="cc-head"><span class="cc-name">${esc(c.name)}</span>
        <span class="badge ${c.active ? 'ok' : 'bad'}">${c.active ? T('active') : T('disabled')}</span>
        <span class="cc-grow"></span>
        <button class="btn sm" data-copy="${esc(c.link || '')}">${T('copy')}</button></div>
      <div class="bar"><i style="width:${c.usage_pct}%"></i></div>
      <div class="kv-line"><span>${T('ov_traffic')} <b>${esc(c.used_human)}</b>${c.limit_bytes ? ' / ' + esc(c.limit_human) : ''}</span>
        <span>${T('expiry')} <b>${esc(shortDate(c.expires_at))}</b></span></div>
      <div class="cc-link"><code>${esc(c.link || '—')}</code></div>
    </div>`).join('');
  openModal(ib.name, `
    <div class="summary-strip"><b>${esc((ib.protocol || '').toUpperCase())}</b> · ${esc((ib.network || '').toUpperCase())} · ${esc((ib.security || '').toUpperCase())}
      &nbsp;→&nbsp; ${esc(ib.address || '')}:${esc(ib.port)} · ${T('path')} <code>${esc(ib.path)}</code></div>
    <div class="card" style="margin-bottom:12px">
      <div class="lbl" style="font-size:8.5px;letter-spacing:1.2px;color:var(--muted);text-transform:uppercase">${T('selfNode')}</div>
      <div class="cc-link" style="margin-top:7px"><code>${esc(self || '—')}</code></div>
      <p class="muted" style="font-size:10.5px;margin-top:7px">${T('selfNodeHint')}</p>
    </div>
    <div class="sub-grid">${cards || `<div class="empty"><b>${T('apiNoClients') || 'No clients'}</b>${T('selfNodeHint')}</div>`}</div>
    <div class="modal-foot"><span class="grow"></span><button class="btn" id="cfgClose">${T('close')}</button></div>`);
  $('cfgClose').onclick = closeModal;
  $$('[data-copy]').forEach((b) => (b.onclick = () => copyText(b.dataset.copy)));
}

/* ================================================================== CLIENTS */
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
  if ($('cInboundSub')) $('cInboundSub').onclick = () => copyText(ib.sub_url);
  if ($('cInboundPage')) $('cInboundPage').onclick = () => window.open(`/info/${ib.sub_token}`, '_blank');
  $$('[data-cact]', view).forEach((b) => (b.onclick = () => clientAction(b.dataset.cact, b.dataset.id)));
}

async function clientAction(act, id) {
  const c = S.clients.find((x) => x.id === id);
  if (!c) return;
  if (act === 'ping') return pingClient(id);
  if (act === 'links') return showClientLinks(c);
  if (act === 'toggle') { await api('PATCH', `/api/clients/${id}`, { enabled: !c.enabled }); return loadAll(); }
  if (act === 'delete') {
    if (!(await confirmAsync(`${T('del')} “${c.name}”?`, T('confirmTitle')))) return;
    await api('DELETE', `/api/clients/${id}`);
    toast(T('deleted'), 'ok');
    return loadAll();
  }
}

function openClientDrawer(ib) {
  const target = ib || S.inbounds.find((i) => i.id === S.clientsIb) || S.inbounds[0];
  if (!target) { toast(T('pickInboundFirst'), 'bad'); return goto('inbounds'); }
  openModal(T('createClient'), `
    <div class="form-grid">
      <label class="field span-2"><span>${T('inbound')} — ${T('primaryLocation')}</span>
        <select id="cInboundSel">${S.inbounds.map((x) => `<option value="${esc(x.id)}" ${x.id === target.id ? 'selected' : ''}>${esc(x.name)} · ${esc((x.protocol || '').toUpperCase())}</option>`).join('')}</select></label>
      <label class="field span-2"><span>${T('extraLocations')} <span class="muted">(${T('upToThree')})</span></span>
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
    if (on.length > 2) { el.checked = false; toast(T('upToThree'), 'bad'); }
  }));
  $('cSave').onclick = async () => {
    try {
      const extras = $$('#cExtra input:checked').map((el) => el.value).slice(0, 2);
      await api('POST', '/api/clients', {
        inbound_id: $('cInboundSel').value, name: $('cName').value || 'Client',
        limit_value: $('cLimit').value || 0, expires_days: $('cDays').value || 0,
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
      <button class="btn sm" data-copy="${esc(c.sub_url)}">${T('copySub')}</button>
      <button class="btn sm" id="clRegen">${T('newSecret')}</button>
      <button class="btn sm" id="clReset">Reset</button>
    </div>
    <div class="card">
        <div class="f-label" style="margin-bottom:10px">${(c.links || []).length} config(s)</div>
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
function boot() {
  $('modalClose').onclick = closeModal;
  $('modal').onclick = (e) => { if (e.target === $('modal')) closeModal(); };
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeModal(); });
  loadAll().catch((e) => toast(e.message, 'bad'));
}

document.addEventListener('DOMContentLoaded', boot);
