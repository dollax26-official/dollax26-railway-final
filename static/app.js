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
    nothingToCopy: 'Nothing to copy here yet', copyFailed: 'Copy blocked by the browser - select and copy manually',
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
    editClient: 'Edit client',
    expiresAt: 'Expires exactly at (date & time)',
    subLinks: 'Sub links',
    subLinksNote: 'Attach other clients\' subscriptions here: their VLESS configs are then delivered inside this client\'s subscription too.',
    linkThisSub: 'Link subscription',
    noSubLinks: 'No linked subscriptions yet',
    linkedSubs: 'linked',
    noOtherClients: 'No other clients yet',
    optional: 'optional',
    enabled: 'Enabled',
    confirmDelete: 'Delete this?',
    nav_nodes: 'Nodes', nav_hosts: 'Hosts', nav_bot: 'TL robot',
    botNote: 'Control this panel from Telegram: create clients and inbounds, manage hosts, read the log.',
    botToken: 'Bot token', botOwner: 'Owner number id', botSaveStart: 'Save & start bot',
    botStatus: 'Bot status', botRunning: 'running', botStopped: 'stopped',
    botTest: 'Send test message', botStop: 'Stop bot', botStartNow: 'Start bot',
    botHandled: 'commands handled', botLastError: 'last error', botUsername: 'bot username',
    botHowto: 'Create a bot with @BotFather, paste its token here, put your numeric Telegram id in Owner number id, then press Save - the bot starts by itself. Send /help to the bot for the command list.',
    botCommands: 'Commands', botTrialInbound: 'Trial inbound',
    botTrialAuto: 'first available inbound', botTrialGb: 'Trial GB (Get config)',
    botTrialDays: 'Trial days (Get config)',
    hostsNote: 'The addresses your VLESS configs should hand out (like x-ui hosts). Pick any of them per inbound and every generated config rotates over exactly those addresses.',
    addHost: 'Add host(s)', hostAddress: 'Address / host',
    hostsPlaceholder: 'de1.example.com\n104.18.149.200',
    hostsForInbound: 'Addresses for this inbound (from Hosts)', onePerLine: 'one address per line',
    hostAdded: 'Host(s) saved', hostRemoved: 'Host removed', noHosts: 'No hosts yet',
    noHostsHint: 'Add addresses in the Hosts page first.', nodesNote: 'Connect another Dollax panel (any location) with its node token. Its inbounds appear here and can be used in subscriptions, so one client can carry several locations.',
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
    primaryLocation: 'primary', extraLocations: 'Extra locations', upToFive: 'up to 5 inbounds per client',
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
    fontFamily: 'فونت', bgUploaded: 'پس‌زمینه ذخیره شد', bgRemoved: 'پس‌زمینه حذف شد', usePanelDomain: 'دامنه‌ی پنل', exportLedger: 'خروجی لجند (CSV)', lastGenerated: 'آخرین زمان ساخت کانفیگ', fetches: 'دریافت سابسکریپشن', xrayCore: 'هستهٔ Xray', addMusic: 'افزودن موسیقی', musicPerUser: 'در حساب شما ذخیره می‌شود؛ دفعه بعد آپلود لازم نیست.', defaultMusic: 'آهنگ پیش‌فرض پنل', noMusic: 'هنوز آهنگی نیست', useMusic: 'استفاده از این آهنگ', musicAdded: 'موسیقی ذخیره شد', musicRemoved: 'آهنگ حذف شد', readFailed: 'خواندن فایل ممکن نشد', unsavedChanges: 'تغییرات ذخیره‌نشده', restartCore: 'راه‌اندازی مجدد هسته', refresh: 'بازخوانی', failed: 'ناموفق', xrayCore: 'هستهٔ Xray', xrayNote: 'هستهٔ Xray داخل ایمیج داکر است و با تغییر اینباندها خودکار ریستارت می‌شود.', wgPublicKey: 'کلید عمومی سرور WG', wgAddress: 'آدرس peer در WG', wgNote: 'کانفیگ‌های WireGuard برای سرور WG شما ساخته می‌شوند؛ Railway فقط TCP می‌دهد.', udpNote: 'پروتکل QUIC/UDP: کانفیگ‌ها ساخته می‌شوند اما Railway فقط TCP را باز می‌کند.', proxyNote: 'لینک‌های پروکسی SOCKS5/HTTP برای هر کلاینت ساخته می‌شوند.', realityNote: 'پروتکل Reality به یک پورت TCP خام نیاز دارد (از پورت HTTPS عبور نمی‌کند). در Railway یک TCP Proxy به پورتی که در تنظیمات → هستهٔ Xray نشان داده می‌شود (پیش‌فرض 8443) بسازید و همان دامنه و پورت را در Address/Port وارد کنید. کلید و short id خودکار ساخته می‌شوند.', realityPorts: 'پورت‌های TCP رلیتی', nothingToCopy: 'چیزی برای کپی نیست', copyFailed: 'مرورگر اجازهٔ کپی نداد؛ دستی انتخاب و کپی کنید', edit: 'ویرایش', editClient: 'ویرایش کاربر', expiresAt: 'انقضای دقیق (تاریخ و ساعت)', subLinks: 'ساب‌لینک‌ها', linkThisSub: 'افزودن ساب‌لینک', noSubLinks: 'ساب‌لینک متصل نیست', linkedSubs: 'متصل', noOtherClients: 'کاربر دیگری نیست', created: 'ساخته شده', subLinksNote: 'ساب‌سکریپشن بقیهٔ کاربران را اینجا وصل کنید؛ کانفیگ‌های VLESS آن‌ها هم داخل ساب این کاربر می‌آید.', optional: 'اختیاری', enabled: 'فعال', confirmDelete: 'حذف شود؟', nav_bot: 'ربات تلگرام', botToken: 'توکن ربات', botOwner: 'آیدی عددی مدیر', botSaveStart: 'ذخیره و اجرای ربات', botStatus: 'وضعیت ربات', botRunning: 'فعال', botStopped: 'متوقف', botTest: 'ارسال پیام تست', botStop: 'توقف ربات', botStartNow: 'اجرای ربات', botHandled: 'دستور اجراشده', botLastError: 'آخرین خطا', botUsername: 'نام کاربری ربات', botCommands: 'دستورها',
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

/* Copy helper used by every button in the panel.
   Browsers only allow the async Clipboard API in a secure context with the document
   focused, so fall back to the legacy selection+execCommand path (which also works over
   plain http / inside webviews) and always report the outcome. */
function legacyCopy(value) {
  try {
    const ta = document.createElement('textarea');
    ta.value = value;
    ta.setAttribute('readonly', '');
    ta.style.position = 'fixed';
    ta.style.top = '-1000px';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    ta.setSelectionRange(0, value.length);
    let ok = false;
    try { ok = document.execCommand('copy'); } catch (err) { ok = false; }
    document.body.removeChild(ta);
    return ok;
  } catch (err) {
    return false;
  }
}

async function copyText(text) {
  const value = String(text == null ? '' : text).trim();
  if (!value || value === 'undefined' || value === 'null') {
    toast(T('nothingToCopy'), 'bad');
    return false;
  }
  const ok = () => { toast(T('copied'), 'ok'); return true; };
  if (navigator.clipboard && navigator.clipboard.writeText) {
    try {
      await navigator.clipboard.writeText(value);
      return ok();
    } catch (e) {
      /* fall through to the legacy path (permission denied, no focus, old browser) */
    }
  }
  if (legacyCopy(value)) return ok();
  toast(T('copyFailed'), 'bad');
  return false;
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
                  [T('realityPorts'), Object.values(st.reality || {}).join(', ') || '—'],
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

/* ------------------------------------------------------------------ hosts */
async function pageHosts(view) {
  const hosts = S.hosts || [];
  const rows = hosts.map((h) => `
    <tr>
      <td><b class="mono">${esc(h.address)}</b>${h.label ? `<span class="sub">${esc(h.label)}</span>` : ''}</td>
      <td class="muted">${esc(h.remark || '—')}</td>
      <td><span class="badge ${h.enabled ? 'ok' : ''}">${h.enabled ? T('enabled') : T('disabled')}</span></td>
      <td class="muted sub">${esc((h.created || '').slice(0, 10))}</td>
      <td class="num" style="white-space:nowrap">
        <button class="btn sm" data-hact="toggle" data-id="${esc(h.id)}">${h.enabled ? T('disable') : T('enable')}</button>
        <button class="btn sm danger" data-hact="del" data-id="${esc(h.id)}">${T('del')}</button></td>
    </tr>`).join('');
  view.innerHTML = `
    <div class="card">
      <div class="card-head"><h2>${T('nav_hosts')}</h2></div>
      <p class="muted" style="font-size:10.5px;margin-bottom:11px">${T('hostsNote')}</p>
      <div class="form-grid">
        <label class="field span-2"><span>${T('hostAddress')}</span>
          <textarea id="hAddresses" rows="3" placeholder="${T('hostsPlaceholder')}"
            style="width:100%;font-family:var(--mono);font-size:11px"></textarea></label>
        <label class="field"><span>${T('label') || 'Label'}</span><input id="hLabel" placeholder="Frankfurt"></label>
        <label class="field"><span>${T('note')}</span><input id="hRemark" placeholder="${T('optional') || 'optional'}"></label>
      </div>
      <div class="toolbar" style="margin-top:12px">
        <button class="btn primary" id="hAdd">${T('addHost')}</button>
        <span class="muted" style="font-size:10px">${T('onePerLine')}</span>
      </div>
    </div>
    <div class="tblwrap">
      ${hosts.length ? `<table><thead><tr><th>${T('hostAddress')}</th><th>${T('note')}</th><th>${T('status')}</th>
        <th>${T('created') || 'Created'}</th><th>${T('actions')}</th></tr></thead><tbody>${rows}</tbody></table>`
        : `<div class="empty"><b>${T('noHosts')}</b>${T('noHostsHint')}</div>`}
    </div>`;

  if ($('hAdd')) $('hAdd').onclick = async () => {
    const btn = $('hAdd');
    btn.disabled = true;
    try {
      const r = await api('POST', '/api/hosts', { addresses: $('hAddresses').value, label: $('hLabel').value,
                                                  remark: $('hRemark').value });
      S.hosts = r.items || [];
      toast(r.added ? `${T('hostAdded')} (${r.added})` : T('nothingToCopy'), r.added ? 'ok' : 'bad');
      goto('hosts');
    } catch (e) { toast(e.message, 'bad'); btn.disabled = false; }
  };
  $$('[data-hact]').forEach((b) => (b.onclick = async () => {
    const id = b.dataset.id;
    try {
      if (b.dataset.hact === 'toggle') {
        const h = (S.hosts || []).find((x) => x.id === id) || {};
        await api('PATCH', '/api/hosts/' + id, { enabled: !h.enabled });
      } else {
        if (!(await confirmAsync(T('confirmDelete')))) return;
        await api('DELETE', '/api/hosts/' + id);
        toast(T('hostRemoved'), 'ok');
      }
      await loadAll();
      goto('hosts');
    } catch (e) { toast(e.message, 'bad'); }
  }));
}

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
  // an admin with a limited access list only sees the sections they were given
  const allowed = (S.me && S.me.sections && S.me.sections !== 'all') ? S.me.sections : null;
  const items = [['overview', T('nav_overview'), '◈'], ['inbounds', T('nav_inbounds'), '≋'],
    ['clients', T('nav_clients'), '☰'], ['hosts', T('nav_hosts'), '⛁'],
    ['nodes', T('nav_nodes'), '⬢'], ['bot', T('nav_bot'), '🤖'], ['logs', T('nav_logs'), '≡']]
    .filter(([id]) => !allowed || allowed.includes(id));
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
  const allowed = ['overview', 'inbounds', 'clients', 'hosts', 'nodes', 'bot', 'logs', 'settings'];
  if (page === 'admins' && !isOwner()) page = 'overview';
  S.page = allowed.concat(['admins']).includes(page) ? page : 'overview';
  const titles = { overview: T('nav_overview'), inbounds: T('nav_inbounds'), clients: T('nav_clients'),
    hosts: T('nav_hosts'), nodes: T('nav_nodes'), bot: T('nav_bot'), logs: T('nav_logs'), admins: T('nav_admins'),
    settings: T('nav_settings') };
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
  try { const hs = await api('GET', '/api/hosts'); S.hosts = hs.items || []; }
  catch (e) { S.hosts = S.hosts || []; }
  try { S.bot = await api('GET', '/api/bot'); } catch (e) { S.bot = S.bot || {}; }
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

/* Sections that live in app2.js (clients, logs, admins, settings). If that file did not
   load the panel still works and says what to do instead of showing a blank page. */
function needPage(name, fn) {
  if (typeof fn === 'function') return true;
  const page = $('page');
  if (page) {
    page.innerHTML = '<div class="card"><div class="card-head"><h2>' + esc(name) + '</h2></div>' +
      '<p class="muted" style="font-size:11px">This section could not be loaded. Refresh with Ctrl+F5 ' +
      '(Cmd+Shift+R on macOS). If it stays empty, /static/app2.js is missing from the deployment.</p></div>';
  }
  return false;
}

function render() {
  const page = $('page');
  if (!page) return;
  const inEl = $('sbIn'), clEl = $('sbCl');
  if (inEl) inEl.textContent = S.inbounds.length + ' inbounds' +
    ((S.remoteInbounds && S.remoteInbounds.length) ? ' + ' + S.remoteInbounds.length + ' node' : '');
  if (clEl) clEl.textContent = S.clients.length + ' clients';
  if (S.page === 'overview') pageOverview(page);
  else if (S.page === 'inbounds') { if (needPage(T('nav_inbounds'), pageInbounds)) pageInbounds(page); }
  else if (S.page === 'clients') { if (needPage(T('nav_clients'), pageClients)) pageClients(page); }
  else if (S.page === 'hosts') { if (needPage(T('nav_hosts'), pageHosts)) pageHosts(page); }
  else if (S.page === 'bot') { if (needPage(T('nav_bot'), pageBot)) pageBot(page); }
  else if (S.page === 'nodes') { if (needPage(T('nav_nodes'), pageNodes)) pageNodes(page); }
  else if (S.page === 'logs') { if (needPage(T('nav_logs'), pageLogs)) pageLogs(page); }
  else if (S.page === 'admins') { if (needPage(T('nav_admins'), pageAdmins)) pageAdmins(page); }
  else { if (needPage(T('nav_settings'), pageSettings)) pageSettings(page); }
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
      ${opt('bNet', T('transport'), [['ws', 'WebSocket'], ['xhttp', 'XHTTP'], ['grpc', 'gRPC'], ['httpupgrade', 'HTTPUpgrade'], ['raw', 'RAW (TCP, modern)'], ['tcp', 'TCP (legacy)']], b.network || 'ws')}
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
    <div class="field" style="margin-top:12px"><span>${T('hostsForInbound')}</span>
      <div class="pick-list" id="bHosts">
        ${(S.hosts || []).length ? (S.hosts || []).map((h) => `<label class="chk pick"><input type="checkbox" value="${esc(h.address)}"
          ${(b.clean_ips || []).includes(h.address) ? 'checked' : ''}> <span class="mono">${esc(h.address)}</span>${h.label ? ' · ' + esc(h.label) : ''}</label>`).join('')
          : `<span class="muted">${T('noHostsHint')}</span>`}
      </div></div>
    <div class="form-grid" style="margin-top:0">
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
    if (sec === 'reality') w.textContent = T('realityNote');
    else if (proto === 'wireguard') w.textContent = T('wgNote');
    else if (external) w.textContent = T('udpNote');
    else if (fallback) w.textContent = T('proxyNote');
    else w.textContent = (proto === 'vless' || proto === 'trojan') ? T('vlessNote') : T('bridgeNote');
    w.style.color = external ? 'var(--warning)' : 'var(--muted)';
    if (sec === 'reality') w.style.color = 'var(--muted)';
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
    hosts: $$('#bHosts input:checked').map((el) => el.value),
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

/* ================================================================== boot */
if (typeof window !== 'undefined' && window.addEventListener) {
  window.addEventListener('error', function (e) {
    try { toast('JS error: ' + (e.message || 'unknown'), 'bad'); } catch (err) {}
  });
  window.addEventListener('unhandledrejection', function (e) {
    try { toast('Request failed: ' + ((e.reason && e.reason.message) || e.reason || ''), 'bad'); } catch (err) {}
  });
}

function boot() {
  $('modalClose').onclick = closeModal;
  $('modal').onclick = (e) => { if (e.target === $('modal')) closeModal(); };
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeModal(); });
  loadAll().catch((e) => toast(e.message, 'bad'));
}

document.addEventListener('DOMContentLoaded', boot);
