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
    fontFamily: 'فونت', bgUploaded: 'پس‌زمینه ذخیره شد', bgRemoved: 'پس‌زمینه حذف شد',
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
function musicStart() {
  if (!Music.el) { Music.el = new Audio('/static/lost-soul.mp3'); Music.el.loop = true; Music.el.preload = 'auto'; }
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

async function persistAppearance() {
  Object.assign(S.prefs, APPR);
  applyPrefs(S.prefs);
  try { await api('POST', '/api/me/prefs', S.prefs); toast(T('appearanceSaved'), 'ok'); }
  catch (e) { toast(e.message, 'bad'); }
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
  applyPrefs();
  render();
  try { await api('POST', '/api/me/prefs', S.prefs); } catch (e) { toast(e.message, 'bad'); }
}

/* ------------------------------------------------------------------ shell */
function navList() {
  const items = [['overview', T('nav_overview'), '◈'], ['inbounds', T('nav_inbounds'), '≋'],
    ['clients', T('nav_clients'), '☰'], ['logs', T('nav_logs'), '≡']];
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
        </div>
      </header>
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
  S.bgPresets = (backgrounds && backgrounds.presets) || [];
  S.bgCustom = !!(backgrounds && backgrounds.custom);
  S.me = me;
  S.summary = summary;
  S.settings = settings.settings || {};
  S.protocols = protocols;
  S.inbounds = inbounds.items || [];
  S.clients = clients.items || [];
  S.prefs = Object.assign({ language: 'en', theme: 'dark-green', style: 'solid', music: 'off', music_volume: 40 }, me.prefs || {});
  if (!S.clientsIb && S.inbounds.length) S.clientsIb = S.inbounds[0].id;
  applyPrefs();
  buildShell();
  render();
}

function render() {
  const page = $('page');
  if (!page) return;
  const inEl = $('sbIn'), clEl = $('sbCl');
  if (inEl) inEl.textContent = S.inbounds.length + ' inbounds';
  if (clEl) clEl.textContent = S.clients.length + ' clients';
  if (S.page === 'overview') pageOverview(page);
  else if (S.page === 'inbounds') pageInbounds(page);
  else if (S.page === 'clients') pageClients(page);
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

  const body = `<div class="builder">
    <div class="form-grid">
      ${opt('bProto', T('protocol'), [['vless', 'VLESS'], ['vmess', 'VMess'], ['trojan', 'Trojan'], ['shadowsocks', 'Shadowsocks']], b.protocol || 'vless')}
      ${opt('bNet', T('transport'), [['ws', 'WebSocket'], ['xhttp', 'XHTTP'], ['grpc', 'gRPC'], ['tcp', 'TCP']], b.network || 'ws')}
      ${opt('bSec', T('security'), [['tls', 'TLS'], ['reality', 'Reality'], ['none', 'None']], b.security || 'tls')}
      ${opt('bFp', T('fFp'), FP_CHOICES.map((f) => [f, f]), b.fingerprint || 'chrome')}
    </div>

    <div class="form-grid" style="margin-top:12px">
      <label class="field"><span>${T('fName')}</span><input id="bName" value="${esc(b.name || '')}" placeholder="Frankfurt-01"></label>
      <label class="field"><span>${T('fAddress')}</span><input id="bAddress" value="${esc(b.address || '')}" placeholder="panel.up.railway.app"></label>
      <label class="field"><span>${T('fPort')}</span><input id="bPort" type="number" min="1" max="65535" value="${esc(b.port || 443)}"></label>
      <label class="field" id="grpPath"><span>${T('fPath')}</span><input id="bPath" value="${esc(b.path || '')}" placeholder="/ws/x (empty = auto)"></label>
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
  ['bName', 'bAddress', 'bPort', 'bPath', 'bConfigCount', 'bDays', 'bLimitGb',
   'bProto', 'bNet', 'bSec', 'bFp'].forEach((id) => {
    const el = $(id);
    if (el) el.addEventListener(el.tagName === 'SELECT' ? 'change' : 'input', syncBuilder);
  });
  syncBuilder();
}

function syncBuilder() {
  const net = ($('bNet') || {}).value || 'ws';
  show('grpPath', net === 'ws' || net === 'xhttp');
  const proto = ($('bProto') || {}).value || 'vless';
  const w = $('bWarn');
  if (w) {
    w.textContent = (proto === 'vless' || proto === 'trojan') ? T('vlessNote') : T('bridgeNote');
    w.style.color = (proto === 'vless' || proto === 'trojan') ? 'var(--muted)' : 'var(--warning)';
  }
  builderSummary();
}

function builderPayload() {
  const g = (id) => { const el = $(id); return el ? el.value : ''; };
  return {
    name: g('bName'), protocol: g('bProto'), network: g('bNet'), security: g('bSec'),
    address: g('bAddress'), port: g('bPort'), path: g('bPath'), fingerprint: g('bFp'),
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
      </div>` : ''}
    </div>
    <div class="tblwrap">
      ${list.length ? `<table>
        <thead><tr><th>${T('name')}</th><th>${T('status')}</th><th>${T('ping')}</th><th>${T('download')}</th><th>${T('upload')}</th><th>${T('traffic')}</th><th>${T('expiry')}</th><th>${T('actions')}</th></tr></thead>
        <tbody>${list.map((c) => `<tr>
          <td><b style="font-weight:700">${esc(c.name)}</b><span class="sub mono">${esc(c.uuid)}</span></td>
          <td><span class="badge ${c.expired ? 'bad' : !c.enabled ? '' : c.over_quota ? 'warn' : 'ok'}">${c.expired ? T('expired') : !c.enabled ? T('disabled') : c.over_quota ? T('quota') : T('active')}</span></td>
          <td class="mono muted" id="ping-${esc(c.id)}">—</td>
          <td class="mono">${T('downShort')} ${esc(c.down_human || '0 B')}</td>
          <td class="mono">${T('upShort')} ${esc(c.up_human || '0 B')}</td>
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
      <label class="field span-2"><span>${T('inbound')}</span>
        <select id="cInboundSel">${S.inbounds.map((x) => `<option value="${esc(x.id)}" ${x.id === target.id ? 'selected' : ''}>${esc(x.name)} · ${esc((x.protocol || '').toUpperCase())}</option>`).join('')}</select></label>
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
  $('cSave').onclick = async () => {
    try {
      await api('POST', '/api/clients', {
        inbound_id: $('cInboundSel').value, name: $('cName').value || 'Client',
        limit_value: $('cLimit').value || 0, expires_days: $('cDays').value || 0,
        ip_limit: $('cIp').value || 0, connection_limit: $('cConn').value || 0,
        speed_limit_mbps: $('cSpeed').value || 0, note: $('cNote').value,
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
  const links = (c.links || []).map((l) => `<div class="cc-link"><code>${esc(l)}</code></div>`).join('');
  openModal(c.name, `
    <div class="summary-strip">${esc(c.inbound_name)} · ${esc(c.used_human)}${c.limit_bytes ? ' / ' + esc(c.limit_human) : ' / ∞'} · ${esc(shortDate(c.expires_at))}</div>
    <div class="toolbar" style="margin:12px 0">
      <button class="btn sm" data-copy="${esc(c.sub_url)}">${T('copySub')}</button>
      <button class="btn sm" id="clRegen">${T('newSecret')}</button>
      <button class="btn sm" id="clReset">Reset</button>
    </div>
    <div class="card">${links || '<span class="muted">—</span>'}</div>
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
        </div>
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
        <div class="card-head"><h2>${T('settingsBridge')}</h2></div>
        <div class="form-grid">
          <label class="field"><span>${T('bridgeHost')}</span><input id="bHost2" value="${esc(S.settings.xray_bridge_host || '')}"></label>
          <label class="field"><span>${T('bridgePort')}</span><input id="bPort2" value="${esc(S.settings.xray_bridge_port || '8080')}"></label>
        </div>
        <div class="toolbar" style="margin-top:12px">
          <button class="btn" id="bSave2">${T('save')}</button>
          <button class="btn" id="bLoad">${T('generate')}</button>
          <button class="btn sm" id="bCopyCfg">${T('copyConfig')}</button>
          <button class="btn sm" id="bCopyCaddy">${T('copyCaddy')}</button>
          <button class="btn sm" id="bCopySteps">${T('copySteps')}</button>
        </div>
        <div class="live-preview" style="margin-top:11px"><code id="bOut">—</code></div>
      </div>` : `<div class="card"><div class="card-head"><h2>${T('diagnostics')}</h2></div>
        <div id="diagBox2"><p class="muted"><span class="spin"></span></p></div></div>`}
    </div>`;

  APPR = Object.assign({}, BG_DEFAULTS, S.prefs);
  $('sLang').onchange = (e) => { APPR.language = e.target.value; applyPrefs(APPR); };
  $('sStyle').onchange = (e) => { APPR.style = e.target.value; applyPrefs(APPR); };
  $('sFont').onchange = (e) => { APPR.font = e.target.value; applyPrefs(APPR); };
  $$('[data-theme-pick]').forEach((b) => (b.onclick = () => { APPR.theme = b.dataset.themePick; applyPrefs(APPR); render(); }));
  $('sMusic').onchange = (e) => { APPR.music = e.target.checked ? 'on' : 'off'; applyPrefs(APPR); };
  $('sVol').oninput = (e) => { $('volVal').textContent = e.target.value; if (Music.el) Music.el.volume = Math.min(1, Math.max(0, e.target.value / 100)); };
  $('sVol').onchange = (e) => { APPR.music_volume = Number(e.target.value); };
  $('sDim').oninput = (e) => { APPR.bg_dim = Number(e.target.value); $('dimVal').textContent = e.target.value + '%'; applyPrefs(APPR); };
  $('sBlur').oninput = (e) => { APPR.bg_blur = Number(e.target.value); $('blurVal').textContent = e.target.value + 'px'; applyPrefs(APPR); };
  $('bgEnabled').onchange = (e) => { APPR.bg_enabled = e.target.checked; applyPrefs(APPR); };
  $$('[data-bg-pick]').forEach((el) => (el.onclick = () => { APPR.background = el.dataset.bgPick; APPR.bg_enabled = true; applyPrefs(APPR); render(); }));
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
  if ($('bSave2')) $('bSave2').onclick = async () => {
    try {
      await api('POST', '/api/settings', { xray_bridge_host: $('bHost2').value, xray_bridge_port: $('bPort2').value });
      toast(T('saved'), 'ok');
    } catch (e) { toast(e.message, 'bad'); }
  };
  if ($('bLoad')) $('bLoad').onclick = async () => {
    S.bridge = await api('GET', '/api/xray/setup');
    $('bOut').textContent = S.bridge.config;
    toast(T('generated') || T('saved'), 'ok');
  };
  if ($('bCopyCfg')) $('bCopyCfg').onclick = () => copyText((S.bridge && S.bridge.config) || '');
  if ($('bCopyCaddy')) $('bCopyCaddy').onclick = () => copyText((S.bridge && S.bridge.caddyfile) || '');
  if ($('bCopySteps')) $('bCopySteps').onclick = () => copyText((S.bridge && S.bridge.steps) || '');
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
