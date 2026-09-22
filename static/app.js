/* ============================================================================
   Dollax Panel — UI (ported from the Cloudflare Worker dashboard)
   Dark theme system, EN/FA, per-user preferences, background music.
   Pages: Overview · Inbounds · Clients · Logs · Admins(owner) · Settings
   No Outbounds. No Clean-IPs page. Clients belong to inbounds.
   ========================================================================== */
'use strict';

/* ------------------------------------------------------------------ i18n */
const I18N = {
  en: {
    brandSub: 'VPN MANAGEMENT', running: 'Running', logout: 'Logout', loading: 'Loading…',
    nav_overview: 'Overview', nav_inbounds: 'Inbounds', nav_clients: 'Clients',
    nav_logs: 'Logs', nav_admins: 'Admins', nav_settings: 'Settings',
    ov_clients: 'Clients', ov_inbounds: 'Inbounds', ov_active: 'Active', ov_traffic: 'Traffic',
    diagnostics: 'Diagnostics', recentActivity: 'Recent activity', gettingStarted: 'Getting started',
    addInbound: '+ Add inbound', addClient: '+ Add client', refresh: 'Refresh',
    search: 'Search…', allProtocols: 'All protocols', selectAll: 'Select all',
    enable: 'Enable', disable: 'Disable', deleteSelected: 'Delete selected',
    apiNoInbounds: 'No inbounds yet', apiNoInboundsSub: 'Create the first endpoint with “Add inbound”.',
    name: 'Name', protocol: 'Protocol', transport: 'Transport', security: 'Security',
    status: 'Status', traffic: 'Traffic', expiry: 'Expiry', actions: 'Actions', clients: 'Clients',
    edit: 'Edit', config: 'Config', del: 'Delete', newSecret: 'New secret', close: 'Close',
    copy: 'Copy', copySub: 'Copy subscription', openSub: 'Open subscription page',
    copyClash: 'Copy Clash', copySingbox: 'Copy sing-box', copied: 'Copied',
    inbound: 'Inbound', path: 'Path', expiryNever: 'never', unlimited: '∞',
    active: 'active', disabled: 'disabled', expired: 'expired', quota: 'quota',
    native: 'native', needsBridge: 'needs bridge',
    pickInbound: 'Select an inbound', pickInboundFirst: 'Create an inbound first.',
    inboundInfo: 'Inbound details', inboundSub: 'Inbound subscription', selfNode: 'Inbound node',
    createClient: 'Create client', clientName: 'Client name', limitGb: 'Traffic (GB, 0 = ∞)',
    days: 'Validity (days, 0 = ∞)', ipLimit: 'IP limit', connLimit: 'Connection limit',
    speed: 'Speed (Mbit/s)', note: 'Note', save: 'Save', cancel: 'Cancel',
    logsNote: 'Every sign-in records the admin and the IP address it came from.',
    time: 'Time', user: 'Admin', ip: 'IP', action: 'Action', detail: 'Detail', noLogs: 'No logs yet',
    adminsNote: 'Admins share the panel but each keeps their own language, theme and music.',
    addAdmin: '+ Add admin', role: 'Role', owner: 'Owner', admin: 'Admin', password: 'Password',
    newPassword: 'New password', lastOwner: 'The last owner cannot be removed.',
    settingsAppearance: 'Appearance', settingsAccount: 'Account', settingsPanel: 'Panel',
    settingsBridge: 'Xray bridge', language: 'Language', theme: 'Theme', uiStyle: 'Interface style',
    solid: 'Solid', glass: 'Glass', music: 'Background music', musicOn: 'On', musicOff: 'Off',
    volume: 'Volume', appearanceNote: 'These choices are stored on your admin account only — no other admin sees them.',
    currentPassword: 'Current password', changePassword: 'Change password', accountNote: 'Your username is fixed; you can change your own password.',
    panelName: 'Panel name', publicBaseUrl: 'Public base URL', defaultPort: 'Default port',
    saveSettings: 'Save settings', ownerOnly: 'Only the owner can change panel settings.',
    bridgeHost: 'Bridge host', bridgePort: 'SOCKS5 exit port', generate: 'Generate bundle',
    copyConfig: 'Copy config', copyCaddy: 'Copy Caddyfile', copySteps: 'Copy steps',
    diagOk: 'OK', diagWarn: 'WARN', diagInfo: 'INFO',
    confirmTitle: 'Are you sure?', yes: 'Yes, delete it', noSelection: 'Select something first',
    ping: 'Ping', latency: 'Latency', download: 'Download', upload: 'Upload', upShort: '↑', downShort: '↓',
    background: 'Background', bgNone: 'Default UI', bgCustom: 'My upload', bgDim: 'Darken',
    bgBlur: 'Blur', uploadBg: 'Upload image', removeBg: 'Remove my background',
    bgPerUser: 'Your background is private to your account — other admins never see it.',
    bgEnabled: 'Use background', saveAppearance: 'Save appearance', resetAppearance: 'Reset',
    fontFamily: 'Font', bgUploaded: 'Background saved', bgRemoved: 'Background removed',
    usePanelDomain: 'Use panel domain',
    exportLedger: 'Export ledger (CSV)', lastGenerated: 'Last config generated',
    addMusic: 'Add music', musicPerUser: 'Saved to your account - no re-upload next time.',
    defaultMusic: 'Panel default track', noMusic: 'No tracks yet', useMusic: 'Use this track',
    musicAdded: 'Music saved', musicRemoved: 'Track removed', readFailed: 'Could not read that file',
    unsavedChanges: 'Unsaved changes', restartCore: 'Restart core', refresh: 'Refresh',
    failed: 'Failed',
    xrayNote: 'Xray-core ships inside the Docker image and is restarted automatically when inbounds change.',
    wgPublicKey: 'WG server public key', wgAddress: 'WG peer address',
    nav_nodes: 'Nodes', nodesNote: 'Connect another Dollax panel (any location) with its node token. Its inbounds appear here and can be used in subscriptions, so one client can carry several locations.',
    nodeToken: 'This panel\u2019s node token', nodeTokenLbl: 'That panel\u2019s node token',
    nodeTokenHint: 'paste the token shown on the other panel', nodeName: 'Node name', nodeUrl: 'Panel address',
    nodeLocation: 'Location', nodeFlag: 'Flag / code', addNode: 'Add node', refreshAll: 'Refresh all',
    rotate: 'Rotate', remoteInbounds: 'Inbounds from connected nodes', noNodes: 'No nodes yet',
    noNodesHint: 'Add the other panel\u2019s address + node token to pull its inbounds in.',
    noRemoteInbounds: 'Nothing pulled yet \u2014 add a node or hit Refresh all.',
    nodeAdded: 'Node connected', nodeAddedWarn: 'Node saved but not reachable', refreshed: 'Refreshed',
    lastSeen: 'Last sync', subTemplates: 'Sub templates',
    subTemplatesNote: 'Pick the design used for the subscription pages of the clients you create.',
    subTemplatesApply: 'Applies to the clients you create (owner sees every design). Press Save appearance to store it.',
    primaryLocation: 'primary', extraLocations: 'Extra locations', upToThree: 'up to 3 inbounds per client',
    configsPerClient: 'Configs per client', connectNodeFirst: 'Connect a node to add more locations.',
    preview: 'Preview', needClientForPreview: 'Create a client first to preview a design.',
    wgNote: 'WireGuard configs are generated for your WG server. Railway exposes TCP only, so the WG endpoint itself must run on a host with UDP + TUN.',
    udpNote: 'QUIC/UDP protocol: configs and links are generated, but Railway only exposes TCP - point the endpoint at a host that allows UDP.',
    proxyNote: 'SOCKS5/HTTP proxy links are generated per client (no TLS layer is added by the panel).',
    fetches: 'subscription fetches', xrayCore: 'Xray-core',
    appearanceSaved: 'Appearance saved', appearanceReset: 'Appearance reset to defaults',
    uploading: 'Uploading…',
    created: 'Created', updated: 'Updated', deleted: 'Deleted', saved: 'Saved',
    step1: 'Base protocol', step1s: 'What kind of credential the client uses',
    step2: 'Transport', step2s: 'How traffic is carried over HTTPS',
    step3: 'Security', step3s: 'Independent of the transport',
    step4: 'Endpoint & advanced', step4s: 'Only the fields that apply are shown',
    step5: 'Limits & rotation', step5s: 'Quotas for the inbound and how many configs it hands out',
    fName: 'Name / remark', fAddress: 'Address / domain', fPort: 'Port', fFp: 'Fingerprint (uTLS)',
    fPath: 'WebSocket path', fHost: 'Host header', fXhttp: 'XHTTP mode', fGrpcSvc: 'gRPC service name',
    fGrpcMode: 'gRPC mode', fHeader: 'TCP header type', fFlow: 'Flow', fSni: 'SNI', fAlpn: 'ALPN',
    fAllow: 'Allow insecure', fFragment: 'Fragment', fReality: 'Reality', fRealitySni: 'Reality SNI',
    fPbk: 'Public key', fSid: 'Short id', fSpx: 'SpiderX', fSs: 'Shadowsocks', fSsMethod: 'Method',
    fSsPass: 'Password (bridge)', fLimit: 'Traffic (GB, 0 = ∞)', fDays: 'Validity (days, 0 = ∞)',
    fExpires: 'Exact expiry', fClientLimit: 'Client limit (0 = ∞)', fIpLimit: 'IP limit',
    fConnLimit: 'Connection limit', fCount: 'Configs per client (1–40)', fSpeed: 'Speed limit (Mbit/s, 0 = ∞)',
    fNote: 'Internal note', fEnabled: 'Enabled', enabledLbl: 'Accept connections',
    livePreview: 'Generated link preview', createInbound: 'Create inbound', editInbound: 'Edit inbound',
    vlessNote: 'VLESS and Trojan are served natively over WebSocket.',
    bridgeNote: 'VMess / Shadowsocks need the Xray bridge (Settings → Xray bridge).',
    autoPath: '(auto)', configs: 'configs', selfNodeHint: 'This inbound works on its own — clients are optional.',
    runTimes: 'times',
  },
  fa: {
    brandSub: 'مدیریت وی‌پی‌ان', running: 'فعال', logout: 'خروج', loading: 'در حال بارگذاری…',
    nav_overview: 'نمای کلی', nav_inbounds: 'ورودی‌ها', nav_clients: 'کاربران',
    nav_logs: 'گزارش‌ها', nav_admins: 'مدیران', nav_settings: 'تنظیمات',
    ov_clients: 'کاربران', ov_inbounds: 'ورودی‌ها', ov_active: 'فعال', ov_traffic: 'ترافیک',
    diagnostics: 'عیب‌یابی', recentActivity: 'فعالیت‌های اخیر', gettingStarted: 'شروع کار',
    addInbound: '+ افزودن ورودی', addClient: '+ افزودن کاربر', refresh: 'به‌روزرسانی',
    search: 'جست‌وجو…', allProtocols: 'همه پروتکل‌ها', selectAll: 'انتخاب همه',
    enable: 'فعال', disable: 'غیرفعال', deleteSelected: 'حذف انتخاب‌شده‌ها',
    apiNoInbounds: 'هنوز ورودی‌ای نیست', apiNoInboundsSub: 'اولین ورودی را با «افزودن ورودی» بسازید.',
    name: 'نام', protocol: 'پروتکل', transport: 'ترنسپورت', security: 'امنیت',
    status: 'وضعیت', traffic: 'ترافیک', expiry: 'انقضا', actions: 'عملیات', clients: 'کاربران',
    edit: 'ویرایش', config: 'کانفیگ', del: 'حذف', newSecret: 'کلید جدید', close: 'بستن',
    copy: 'کپی', copySub: 'کپی سابسکریپشن', openSub: 'بازکردن صفحه سابسکریپشن',
    copyClash: 'کپی کلش', copySingbox: 'کپی سینگ‌باکس', copied: 'کپی شد',
    inbound: 'ورودی', path: 'مسیر', expiryNever: 'ندارد', unlimited: '∞',
    active: 'فعال', disabled: 'غیرفعال', expired: 'منقضی', quota: 'اتمام حجم',
    native: 'بومی', needsBridge: 'نیازمند پل',
    pickInbound: 'یک ورودی انتخاب کنید', pickInboundFirst: 'اول یک ورودی بسازید.',
    inboundInfo: 'مشخصات ورودی', inboundSub: 'سابسکریپشن ورودی', selfNode: 'نود خود ورودی',
    createClient: 'ایجاد کاربر', clientName: 'نام کاربر', limitGb: 'حجم (GB، ۰ = بی‌نهایت)',
    days: 'اعتبار (روز، ۰ = بی‌نهایت)', ipLimit: 'سقف IP', connLimit: 'سقف اتصال',
    speed: 'سرعت (Mbit/s)', note: 'یادداشت', save: 'ذخیره', cancel: 'لغو',
    logsNote: 'هر ورود، مدیر و آی‌پی مبدأ را ثبت می‌کند.',
    time: 'زمان', user: 'مدیر', ip: 'آی‌پی', action: 'عملیات', detail: 'جزئیات', noLogs: 'گزارشی نیست',
    adminsNote: 'مدیران پنل مشترک دارند اما هرکدام زبان، تم و موسیقی خودش را.',
    addAdmin: '+ افزودن مدیر', role: 'نقش', owner: 'مالک', admin: 'مدیر', password: 'رمز',
    newPassword: 'رمز جدید', lastOwner: 'آخرین مالک قابل حذف نیست.',
    settingsAppearance: 'ظاهر', settingsAccount: 'حساب من', settingsPanel: 'پنل',
    settingsBridge: 'پل Xray', language: 'زبان', theme: 'تم', uiStyle: 'سبک رابط',
    solid: 'ساده', glass: 'شیشه‌ای', music: 'موسیقی پس‌زمینه', musicOn: 'روشن', musicOff: 'خاموش',
    volume: 'صدا', appearanceNote: 'این تنظیمات فقط روی حساب شما ذخیره می‌شود و مدیران دیگر نمی‌بینند.',
    currentPassword: 'رمز فعلی', changePassword: 'تغییر رمز', accountNote: 'نام کاربری ثابت است؛ می‌توانید رمز خودتان را عوض کنید.',
    panelName: 'نام پنل', publicBaseUrl: 'آدرس عمومی', defaultPort: 'پورت پیش‌فرض',
    saveSettings: 'ذخیره تنظیمات', ownerOnly: 'فقط مالک می‌تواند تنظیمات پنل را تغییر دهد.',
    bridgeHost: 'میزبان پل', bridgePort: 'پورت خروجی SOCKS5', generate: 'ساخت بسته',
    copyConfig: 'کپی کانفیگ', copyCaddy: 'کپی Caddyfile', copySteps: 'کپی مراحل',
    diagOk: 'سالم', diagWarn: 'هشدار', diagInfo: 'اطلاع',
    confirmTitle: 'مطمئنید؟', yes: 'بله، حذف کن', noSelection: 'چیزی انتخاب نشده',
    ping: 'پینگ', latency: 'تأخیر', download: 'دانلود', upload: 'آپلود', upShort: '↑', downShort: '↓',
    background: 'پس‌زمینه', bgNone: 'رابط پیش‌فرض', bgCustom: 'آپلود خودم', bgDim: 'تیره‌کردن',
    bgBlur: 'محو', uploadBg: 'آپلود تصویر', removeBg: 'حذف پس‌زمینه‌ی من',
    bgPerUser: 'پس‌زمینه‌ی شما فقط در حساب خودتان دیده می‌شود.',
    bgEnabled: 'استفاده از پس‌زمینه', saveAppearance: 'ذخیره‌ی ظاهر', resetAppearance: 'بازنشانی',
    fontFamily: 'فونت', bgUploaded: 'پس‌زمینه ذخیره شد', bgRemoved: 'پس‌زمینه حذف شد', usePanelDomain: 'دامنه‌ی پنل', exportLedger: 'خروجی لجند (CSV)', lastGenerated: 'آخرین زمان ساخت کانفیگ', fetches: 'دریافت سابسکریپشن', xrayCore: 'هستهٔ Xray', addMusic: 'افزودن موسیقی', musicPerUser: 'در حساب شما ذخیره می‌شود؛ دفعه بعد آپلود لازم نیست.', defaultMusic: 'آهنگ پیش‌فرض پنل', noMusic: 'هنوز آهنگی نیست', useMusic: 'استفاده از این آهنگ', musicAdded: 'موسیقی ذخیره شد', musicRemoved: 'آهنگ حذف شد', readFailed: 'خواندن فایل ممکن نشد', unsavedChanges: 'تغییرات ذخیره‌نشده', restartCore: 'راه‌اندازی مجدد هسته', refresh: 'بازخوانی', failed: 'ناموفق', xrayCore: 'هستهٔ Xray', xrayNote: 'هستهٔ Xray داخل ایمیج داکر است و با تغییر اینباندها خودکار ریستارت می‌شود.', wgPublicKey: 'کلید عمومی سرور WG', wgAddress: 'آدرس peer در WG', wgNote: 'کانفیگ‌های WireGuard برای سرور WG شما ساخته می‌شوند؛ Railway فقط TCP می‌دهد.', udpNote: 'پروتکل QUIC/UDP: کانفیگ‌ها ساخته می‌شوند اما Railway فقط TCP را باز می‌کند.', proxyNote: 'لینک‌های پروکسی SOCKS5/HTTP برای هر کلاینت ساخته می‌شوند.',
    appearanceSaved: 'ظاهر ذخیره شد', appearanceReset: 'ظاهر به حالت پیش‌فرض برگشت',
    uploading: 'در حال آپلود…',
    created: 'ساخته شد', updated: 'به‌روز شد', deleted: 'حذف شد', saved: 'ذخیره شد',
    step1: 'پروتکل پایه', step1s: 'نوع اعتباری که کاربر استفاده می‌کند',
    step2: 'ترنسپورت', step2s: 'نحوه انتقال ترافیک روی HTTPS',
    step3: 'امنیت', step3s: 'مستقل از ترنسپورت',
    step4: 'اندپوینت و پیشرفته', step4s: 'فقط فیلدهای مرتبط نمایش داده می‌شود',
    step5: 'محدودیت و چرخش', step5s: 'سقف‌های ورودی و تعداد کانفیگ‌ها',
    fName: 'نام / توضیح', fAddress: 'آدرس / دامنه', fPort: 'پورت', fFp: 'اثر انگشت (uTLS)',
    fPath: 'مسیر WebSocket', fHost: 'هدر Host', fXhttp: 'حالت XHTTP', fGrpcSvc: 'نام سرویس gRPC',
    fGrpcMode: 'حالت gRPC', fHeader: 'نوع هدر TCP', fFlow: 'Flow', fSni: 'SNI', fAlpn: 'ALPN',
    fAllow: 'اجازه ناامن', fFragment: 'Fragment', fReality: 'Reality', fRealitySni: 'SNI ریلیتی',
    fPbk: 'کلید عمومی', fSid: 'شناسه کوتاه', fSpx: 'SpiderX', fSs: 'Shadowsocks', fSsMethod: 'متد',
    fSsPass: 'رمز (برای پل)', fLimit: 'حجم (GB، ۰ = بی‌نهایت)', fDays: 'اعتبار (روز، ۰ = بی‌نهایت)',
    fExpires: 'انقضای دقیق', fClientLimit: 'سقف کاربر (۰ = بی‌نهایت)', fIpLimit: 'سقف IP',
    fConnLimit: 'سقف اتصال', fCount: 'تعداد کانفیگ هر کاربر (۱–۴۰)', fSpeed: 'محدودیت سرعت (Mbit/s)',
    fNote: 'یادداشت داخلی', fEnabled: 'فعال', enabledLbl: 'پذیرش اتصال',
    livePreview: 'پیش‌نمایش لینک', createInbound: 'ایجاد ورودی', editInbound: 'ویرایش ورودی',
    vlessNote: 'VLESS و Trojan به‌صورت بومی روی WebSocket سرو می‌شوند.',
    bridgeNote: 'VMess / Shadowsocks به پل Xray نیاز دارند (تنظیمات → پل Xray).',
    autoPath: '(خودکار)', configs: 'کانفیگ', selfNodeHint: 'این ورودی خودش کار می‌کند — کاربر اختیاری است.',
    runTimes: 'بار',
  },
};

const THEMES = [
  ['dark-green', '#26d0a8'], ['dark-cyan', '#22d3ee'], ['dark-blue', '#4f8cff'],
  ['green', '#22c55e'], ['cyan', '#06b6d4'], ['blue', '#3b82f6'], ['orange', '#f97316'],
];

const FP_CHOICES = ['chrome', 'firefox', 'safari', 'ios', 'android', 'edge', '360', 'qq', 'random', 'randomized'];

const S = {
  me: null, summary: {}, inbounds: [], clients: [], settings: {},
  protocols: {}, diag: [], activity: [], admins: [], bridge: null,
  prefs: { language: 'en', theme: 'dark-green', style: 'solid', music: 'off', music_volume: 40 },
  page: 'overview', ibSel: new Set(), ibQ: '', ibFilter: 'all', clientsIb: '',
};

let LANG = 'en';
const T = (k) => (I18N[LANG] && I18N[LANG][k]) || I18N.en[k] || k;

/* ------------------------------------------------------------------ helpers */
const $ = (id) => document.getElementById(id);
const $$ = (sel, root) => Array.from((root || document).querySelectorAll(sel));
const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const fmt = (n) => {
  n = Number(n || 0);
  const u = ['B', 'KB', 'MB', 'GB', 'TB'];
  let i = 0;
  while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
  return (i === 0 ? n.toFixed(0) : n.toFixed(2)) + ' ' + u[i];
};
const shortDate = (s) => (s ? String(s).slice(0, 10) : T('expiryNever'));

async function api(method, path, body) {
  const opt = { method, headers: {}, credentials: 'same-origin' };
  if (body !== undefined) { opt.headers['content-type'] = 'application/json'; opt.body = JSON.stringify(body); }
  const res = await fetch(path, opt);
  const text = await res.text();
  let data = null;
  try { data = text ? JSON.parse(text) : null; } catch (e) { data = { raw: text }; }
  if (!res.ok) throw new Error((data && (data.error || data.detail)) || ('HTTP ' + res.status));
  return data;
}

function toast(msg, kind) {
  const el = document.createElement('div');
  el.className = 'toast ' + (kind || '');
  el.textContent = msg;
  $('toasts').appendChild(el);
  setTimeout(() => el.remove(), 3400);
}

function confirmAsync(text, title) {
  return new Promise((resolve) => {
    openModal(title || T('confirmTitle'), `<p class="muted" style="font-size:12px">${esc(text || '')}</p>
      <div class="confirm-actions">
        <button class="btn" id="mCancel">${T('cancel')}</button>
        <button class="btn danger" id="mOk">${T('yes')}</button>
      </div>`, true);
    const done = (v) => { closeModal(); resolve(v); };
    $('mOk').onclick = () => done(true);
    $('mCancel').onclick = () => done(false);
  });
}

function openModal(title, bodyHtml, isConfirm) {
  $('modalTitle').textContent = title;
  $('modalBody').innerHTML = bodyHtml;
  $('modalBox').className = 'modal-box' + (isConfirm ? ' confirm-box' : '');
  $('modal').classList.remove('hidden');
}
function closeModal() { $('modal').classList.add('hidden'); $('modalBody').innerHTML = ''; }

async function copyText(text) {
  try { await navigator.clipboard.writeText(text); toast(T('copied'), 'ok'); }
  catch (e) { toast('Copy failed', 'bad'); }
}

/* ------------------------------------------------------------------ music */
const Music = { el: null, on: false };
function musicLevel() {
  let v = Number(S.prefs.music_volume);
  if (!isFinite(v)) v = 40;
  return Math.min(1, Math.max(0, v / 100));
}
function musicSrc() {
  const t = (S.prefs && S.prefs.music_track) || 'default';
  return (!t || t === 'default') ? '/static/lost-soul.mp3'
                                 : '/api/me/tracks/' + encodeURIComponent(t) + '/audio';
}
function musicStart() {
  const src = musicSrc();
  if (!Music.el || Music.src !== src) {
    try { if (Music.el) Music.el.pause(); } catch (e) {}
    Music.el = new Audio(src);
    Music.el.loop = true;
    Music.el.preload = 'auto';
    Music.src = src;
  }
  Music.el.volume = musicLevel();
  const p = Music.el.play();
  if (p && p.catch) p.catch(() => {});
}
function musicStop() { if (Music.el) { try { Music.el.pause(); } catch (e) {} } }
function musicApply() {
  Music.on = S.prefs.music === 'on';
  if (Music.on) {
    musicStart();
    if (!Music.el || Music.el.paused) {
      const kick = () => { musicStart(); if (Music.el && !Music.el.paused) document.removeEventListener('click', kick); };
      document.addEventListener('click', kick);
    }
  } else musicStop();
}

/* ------------------------------------------------------------------ prefs */
function applyPrefs(override) {
  const P = override || S.prefs || {};
  LANG = P.language === 'fa' ? 'fa' : 'en';
  const theme = THEMES.some((t) => t[0] === P.theme) ? P.theme : 'dark-green';
  const html = document.documentElement;
  html.setAttribute('data-theme', theme);
  html.setAttribute('data-style', P.style === 'glass' ? 'glass' : 'solid');
  const font = FONTS_LIST.some((f) => f[0] === P.font) ? P.font : 'inter';
  html.setAttribute('data-font', font);
  html.setAttribute('lang', LANG);
  html.setAttribute('dir', LANG === 'fa' ? 'rtl' : 'ltr');
  applyBackground(P);
  musicApply();
}

/* ---- per-user background (never shared with another admin) ---- */
const FONTS_LIST = [['inter', 'Inter'], ['vazirmatn', 'Vazirmatn'], ['poppins', 'Poppins'],
  ['roboto', 'Roboto'], ['space', 'Space Grotesk'], ['mono', 'JetBrains Mono'], ['system', 'System']];
const BG_DEFAULTS = { background: 'none', bg_dim: 35, bg_blur: 0, bg_enabled: true };
let APPR = null;          // appearance draft while the Settings page is open

function bgUrl(P) {
  const id = (P || {}).background;
  if (!id || id === 'none') return '';
  if (id === 'custom') return '/api/me/background?v=' + Date.now();
  return '/static/bg/' + id + '.jpg';
}

function applyBackground(P) {
  const layer = document.getElementById('bgLayer');
  if (!layer) return;
  const url = bgUrl(P);
  const on = !!url && P.bg_enabled !== false;
  layer.style.display = on ? 'block' : 'none';
  if (on) {
    layer.style.backgroundImage = `url("${url}")`;
    layer.style.filter = `blur(${Number(P.bg_blur) || 0}px)`;
    layer.style.setProperty('--bg-dim', String((Number(P.bg_dim ?? 35)) / 100));
  }
  document.documentElement.setAttribute('data-bg', on ? 'on' : 'off');
}

function downscaleImage(file, maxSide, quality) {
  return new Promise((resolve, reject) => {
    const fr = new FileReader();
    fr.onerror = () => reject(new Error('Could not read that file'));
    fr.onload = () => {
      const img = new Image();
      img.onerror = () => reject(new Error('That file is not an image'));
      img.onload = () => {
        const scale = Math.min(1, maxSide / Math.max(img.width, img.height));
        const cv = document.createElement('canvas');
        cv.width = Math.max(1, Math.round(img.width * scale));
        cv.height = Math.max(1, Math.round(img.height * scale));
        cv.getContext('2d').drawImage(img, 0, 0, cv.width, cv.height);
        resolve(cv.toDataURL('image/jpeg', quality));
      };
      img.src = fr.result;
    };
    fr.readAsDataURL(file);
  });
}

async function uploadBackground(file) {
  if (!file) return;
  try {
    toast(T('uploading'), '');
    const dataUrl = await downscaleImage(file, 1920, 0.82);
    const r = await api('POST', '/api/me/background', { data: dataUrl });
    toast(`${T('bgUploaded')} (${Math.round(r.bytes / 1024)} KB)`, 'ok');
    APPR.background = 'custom';
    APPR.bg_enabled = true;
    await persistAppearance();
    render();
  } catch (e) {
    toast(e.message, 'bad');
  }
}

async function removeBackground() {
  try {
    await api('DELETE', '/api/me/background');
    if (APPR) APPR.background = 'none';
    toast(T('bgRemoved'), 'ok');
    await persistAppearance();
    render();
  } catch (e) { toast(e.message, 'bad'); }
}

/* Everything below only touches the draft (APPR). The panel look changes when the admin
   presses Save appearance - that is what the button is for, and what it now reliably does. */
function markDraft() {
  const b = $('apprDirty');
  if (b) b.style.display = 'inline-block';
}

function tracksHtml() {
  const cur = (APPR && APPR.music_track) || 'default';
  const rows = (S.tracks || []).map((t) => `
    <div class="trk ${cur === t.id ? 'on' : ''}">
      <button class="btn sm" data-trk-use="${esc(t.id)}" title="${T('useMusic')}">${cur === t.id ? '\u2713' : '\u25b6'}</button>
      <span class="trk-name">${esc(t.name || 'track')}</span>
      <span class="muted trk-size">${Math.round((Number(t.size) || 0) / 1024)} KB</span>
      <button class="btn sm danger" data-trk-del="${esc(t.id)}" title="${T('remove')}">\u2715</button>
    </div>`).join('');
  const def = `<div class="trk ${cur === 'default' ? 'on' : ''}">
      <button class="btn sm" data-trk-use="default">${cur === 'default' ? '\u2713' : '\u25b6'}</button>
      <span class="trk-name">${T('defaultMusic')}</span></div>`;
  return def + (rows || `<div class="muted" style="font-size:10px;padding:5px">${T('noMusic')}</div>`);
}

function wireMusicLib() {
  $$('[data-trk-use]').forEach((b) => (b.onclick = () => {
    APPR.music_track = b.dataset.trkUse;
    if (b.dataset.trkUse !== 'default') APPR.music = 'on';
    markDraft();
    const lib = $('musicLib');
    if (lib) lib.innerHTML = tracksHtml();
    wireMusicLib();
  }));
  $$('[data-trk-del]').forEach((b) => (b.onclick = async () => {
    try {
      const r = await api('DELETE', '/api/me/tracks/' + encodeURIComponent(b.dataset.trkDel));
      S.tracks = r.items || [];
      if (APPR.music_track === b.dataset.trkDel) APPR.music_track = 'default';
      toast(T('musicRemoved'), 'ok');
      const lib = $('musicLib');
      if (lib) lib.innerHTML = tracksHtml();
      wireMusicLib();
    } catch (e) { toast(e.message, 'bad'); }
  }));
}

async function uploadTrack(file) {
  if (!file) return;
  try {
    toast(T('uploading'), '');
    const dataUrl = await new Promise((resolve, reject) => {
      const fr = new FileReader();
      fr.onerror = () => reject(new Error(T('readFailed')));
      fr.onload = () => resolve(fr.result);
      fr.readAsDataURL(file);
    });
    const r = await api('POST', '/api/me/tracks', { data: dataUrl, name: file.name });
    S.tracks = r.items || [];
    APPR.music_track = r.id;
    APPR.music = 'on';
    markDraft();
    toast(`${T('musicAdded')} (${Math.round(r.bytes / 1024)} KB)`, 'ok');
    const lib = $('musicLib');
    if (lib) lib.innerHTML = tracksHtml();
    wireMusicLib();
  } catch (e) { toast(e.message, 'bad'); }
}

async function loadXrayInto() {
  const box = $('xrayBox');
  if (!box) return;
  try {
    const st = await api('GET', '/api/xray/status');
    const rows = [['mode', st.mode], ['binary', st.installed ? 'found' : 'missing'],
                  ['running', st.running ? 'yes' : 'no'], ['inbounds', st.inbounds],
                  ['base port', st.base_port], ['last sync', st.last_sync ? new Date(st.last_sync * 1000).toLocaleTimeString() : '-'],
                  ['version', st.version || '-'], ['error', st.last_error || '-']];
    box.innerHTML = rows.map(([k, v]) => `<div class="diag-row"><span class="muted">${esc(k)}</span>` +
      `<code class="mono">${esc(String(v))}</code></div>`).join('') +
      (st.hint ? `<p class="muted" style="font-size:10px;margin-top:8px">${esc(st.hint)}</p>` : '');
  } catch (e) {
    box.innerHTML = `<p class="muted" style="font-size:10.5px">${esc(e.message)}</p>`;
  }
}

async function persistAppearance() {
  Object.assign(S.prefs, APPR);
  applyPrefs(S.prefs);
  const btn = $('apprSave');
  if (btn) { btn.disabled = true; btn.textContent = '…'; }
  try {
    await api('POST', '/api/me/prefs', S.prefs);
    const dirty = $('apprDirty');
    if (dirty) dirty.style.display = 'none';
    toast(T('appearanceSaved'), 'ok');
    if (btn) {
      btn.textContent = '✓ ' + T('saved');
      setTimeout(() => { if (btn) { btn.textContent = T('saveAppearance'); btn.disabled = false; } }, 1500);
    }
  } catch (e) {
    toast(e.message, 'bad');
    if (btn) { btn.textContent = T('saveAppearance'); btn.disabled = false; }
  }
}

function resetAppearance() {
  Object.assign(APPR, { language: 'en', theme: 'dark-green', style: 'solid', font: 'inter',
    music: 'off', music_volume: 40, background: 'none', bg_dim: 35, bg_blur: 0, bg_enabled: true });
  applyPrefs(APPR);
  render();
  toast(T('appearanceReset'), 'ok');
}

function bgOptionsHtml() {
  const cur = (APPR || {}).background || 'none';
  const presets = (S.bgPresets || []).map((p) => `
    <div class="bg-thumb ${cur === p.id ? 'on' : ''}" data-bg-pick="${esc(p.id)}"
         style="background-image:url('${esc(p.url)}')"><span>${esc(p.id)}</span></div>`).join('');
  const custom = S.bgCustom ? `
    <div class="bg-thumb ${cur === 'custom' ? 'on' : ''}" data-bg-pick="custom"
         style="background-image:url('/api/me/background?v=${Date.now()}')"><span>${T('bgCustom')}</span></div>` : '';
  return `<div class="bg-thumb none ${cur === 'none' ? 'on' : ''}" data-bg-pick="none">${T('bgNone')}</div>${custom}${presets}`;
}
async function savePrefs(patch) {
  Object.assign(S.prefs, patch);
  if (APPR) Object.assign(APPR, patch);      // keep the Settings draft in sync
  applyPrefs();
  render();
  try { await api('POST', '/api/me/prefs', S.prefs); } catch (e) { toast(e.message, 'bad'); }
}

/* highlight the picked theme / background in place (no full re-render, which used to look like a reset) */
function markThemePicks() {
  $$('[data-theme-pick]').forEach((b) => {
    const t = THEMES.find((x) => x[0] === b.dataset.themePick);
    b.style.borderColor = (APPR && APPR.theme === b.dataset.themePick)
      ? (t ? t[1] : 'var(--accent)') : 'var(--line)';
  });
}

function markBgPicks() {
  $$('[data-bg-pick]').forEach((el) => el.classList.toggle('on', !!(APPR && APPR.background === el.dataset.bgPick)));
}

