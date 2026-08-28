/**
 * BASPAR CMMS — application shell (§7 global layout, §8 global search,
 * §34 real-time, §20B connectivity indicator).
 */
import {
  Session, api, errText, h, $, mount, navigate, route, setNotFound,
  dispatch, toast, openModal, spinner,
} from './core.js?v=11';
import { toJalaliStr } from './jalali.js?v=11';
import { icon } from './icons.js?v=11';

import { renderLogin } from './pages/auth.js?v=11';
import { renderDashboard } from './pages/dashboard.js?v=11';
import { renderEquipmentList } from './pages/equipment.js?v=11';
import { renderEquipmentDetail } from './pages/equipment-detail.js?v=11';
import { renderWizard } from './pages/equipment-wizard.js?v=11';
import { renderBulkImport } from './pages/bulk-import.js?v=11';
import { renderPassport } from './pages/passport.js?v=11';
import {
  renderUsers, renderRoles, renderBaseData, renderAudit, renderBackup, renderSettings,
} from './pages/admin.js?v=11';
import { renderRequests } from './pages/requests.js?v=11';
import { renderWorkOrders } from './pages/workorders.js?v=11';
import { renderWorkOrderDetail } from './pages/workorder-detail.js?v=11';
import { renderNotifications } from './pages/notifications.js?v=11';
import { renderSelen } from './pages/selen.js?v=11';
import { renderChecklists, renderChecklistRun } from './pages/checklists.js?v=11';
import { renderRisks } from './pages/risks.js?v=11';
import { renderCalibration } from './pages/calibration.js?v=11';
import { renderParts } from './pages/parts.js?v=11';
import { renderSuppliers } from './pages/suppliers.js?v=11';
import { renderConsultation } from './pages/consultation.js?v=11';
import { renderReports } from './pages/reports.js?v=11';
import { renderBulkCharge } from './pages/bulk-charge.js?v=11';
import { watchConnectivity, pendingCount, flushQueue } from './offline.js?v=11';

/* ------------------------------------------------------------------ */
/* Navigation model (role-based §7)                                    */
/* ------------------------------------------------------------------ */
const NAV = [
  { section: 'عملیات' },
  { hash: '#/dashboard', icon: 'dashboard', label: 'داشبورد', perm: 'dashboard.view' },
  { hash: '#/equipment', icon: 'equipment', label: 'تجهیزات', perm: 'equipment.view' },
  { hash: '#/requests', icon: 'requests', label: 'درخواست‌ها', perm: 'requests.view' },
  { hash: '#/work-orders', icon: 'workorders', label: 'دستور کارها', perm: 'workorders.view' },
  { hash: '#/import', icon: 'import', label: 'ورود سریع (تک‌فایل)', perm: 'import.manage' },
  { hash: '#/bulk-charge', icon: 'charge', label: 'مرکز شارژ داده (§6B)', perm: 'bulk_charge.charge' },
  { hash: '#/checklists', icon: 'checklists', label: 'چک‌لیست بازرسی', perm: 'checklist.view' },
  { hash: '#/parts', icon: 'parts', label: 'قطعات و انبار', perm: 'parts.view' },
  { hash: '#/suppliers', icon: 'parts', label: 'تأمین‌کنندگان', perm: 'parts.view' },
  { hash: '#/notifications', icon: 'notifications', label: 'اعلان‌ها', perm: 'notifications.view' },
  { section: 'تحلیل و پیشگیری' },
  { hash: '#/selen', icon: 'selen', label: 'SELEN دستیار هوشمند', perm: 'selen.use' },
  { hash: '#/risks', icon: 'risks', label: 'ریسک و فرصت', perm: 'risks.view' },
  { hash: '#/calibration', icon: 'calibration', label: 'کالیبراسیون', perm: 'calibration.view' },
  { hash: '#/reports', icon: 'reports', label: 'گزارش‌ها و KPI', perm: 'reports.view' },
  { section: 'ارتباطات' },
  { hash: '#/consultation', icon: 'consultation', label: 'مشاوره داخلی', perm: 'messages.view' },
  { section: 'مدیریت' },
  { hash: '#/admin/users', icon: 'users', label: 'کاربران', perm: 'users.view' },
  { hash: '#/admin/roles', icon: 'roles', label: 'نقش‌ها و دسترسی‌ها', perm: 'roles.manage' },
  { hash: '#/admin/base', icon: 'base', label: 'داده‌های پایه', perm: 'base_data.manage' },
  { hash: '#/admin/audit', icon: 'audit', label: 'گزارش ممیزی', perm: 'audit.view' },
  { hash: '#/admin/backup', icon: 'backup', label: 'پشتیبان‌گیری', perm: 'backup.manage' },
  { section: 'سیستم' },
  { hash: '#/settings', icon: 'settings', label: 'تنظیمات', perm: null },
];

let sidebarCollapsed = localStorage.getItem('cmms_sidebar') === '1';
let sse = null;
let connState = 'online';

function setConn(state) {
  connState = state;
  const pill = $('#conn-pill');
  if (!pill) return;
  pill.className = `conn-pill ${state}`;
  const pending = pendingCount();
  pill.textContent = state === 'online'
    ? (pending ? `آنلاین · ${pending} در صف` : 'آنلاین')
    : state === 'offline'
      ? (pending ? `آفلاین · ${pending} در صف` : 'آفلاین')
      : 'در حال همگام‌سازی';
}

// connectivity + offline queue auto-flush (§20B)
watchConnectivity(setConn);

/* Header notification bell (§31) */
function bell() {
  const btn = h('button', { class: 'btn btn-ghost btn-icon', title: 'اعلان‌ها', onclick: () => navigate('#/notifications') }, '🔔');
  async function refresh() {
    try {
      const { unread } = await api('/notifications/unread-count');
      btn.replaceChildren('🔔');
      if (unread > 0) btn.append(h('span', {
        style: 'background:var(--c-danger);color:#fff;border-radius:99px;font-size:10px;padding:0 5px;margin-inline-start:-4px',
      }, unread > 99 ? '99+' : String(unread)));
    } catch { /* not logged in */ }
  }
  window.refreshBell = refresh;
  refresh();
  return btn;
}

/* ------------------------------------------------------------------ */
/* Shell                                                               */
/* ------------------------------------------------------------------ */
function shell(activeHash) {
  const u = Session.user || {};
  const sidebar = h('aside', { class: `sidebar ${sidebarCollapsed ? 'collapsed' : ''}` },
    h('nav', { class: 'sidebar-nav' },
      NAV.filter((n) => n.section || n.perm === null || Session.can(n.perm)).map((n) =>
        n.section
          ? h('div', { class: 'nav-section' }, n.section)
          : h('div', {
              class: `nav-item ${activeHash.startsWith(n.hash.slice(1)) ? 'active' : ''}`,
              onclick: () => { navigate(n.hash); document.body.classList.remove('sidebar-open'); },
            }, h('span', { class: 'nav-icon', html: icon(n.icon) }), h('span', { class: 'label' }, n.label)))),
    h('div', { class: 'sidebar-foot' }, 'نسخه ۰٫۳ — فاز ۰/۱/۲ آمادهٔ ممیزی'));

  const header = h('header', {},
    h('button', {
      class: 'btn btn-ghost btn-icon', title: 'منو',
      onclick: () => {
        if (window.innerWidth <= 720) sidebar.classList.toggle('mobile-open');
        else { sidebarCollapsed = !sidebarCollapsed; sidebar.classList.toggle('collapsed'); localStorage.setItem('cmms_sidebar', sidebarCollapsed ? '1' : '0'); }
      },
    }, '☰'),
    h('div', { class: 'brand' }, h('span', { class: 'brand-mark', html: icon('workorders') }),
      h('span', {}, 'سامانه مدیریت نت بسپار',
        h('small', {}, 'Enterprise Intelligent CMMS / EAM'))),
    h('button', { class: 'btn btn-secondary btn-sm', onclick: openSearch },
      h('span', { html: icon('search'), style: 'display:inline-flex;width:14px;height:14px' }),
      'جستجو  Ctrl+K'),
    h('div', { style: 'flex:1' }),
    bell(),
    h('span', { id: 'conn-pill', class: 'conn-pill online' }, 'آنلاین'),
    h('div', { class: 'small', style: 'text-align:left' },
      h('div', { style: 'font-weight:600' }, u.full_name || u.username),
      h('div', { class: 'faint', style: 'font-size:11px' },
        (u.roles || []).map((r) => r.title_fa).join('، '))),
    h('button', { class: 'btn btn-ghost btn-sm', onclick: logout }, 'خروج'));

  const main = h('main', { id: 'main' }, spinner());

  const el = h('div', { class: 'app-shell' }, header,
    h('div', { class: 'shell-body' }, sidebar, main));
  mount(el);
  return main;
}

async function logout() {
  try { await api('/auth/logout', { method: 'POST' }); } catch { /* noop */ }
  Session.clear();
  if (sse) { sse.close(); sse = null; }
  navigate('#/login');
}

/* ------------------------------------------------------------------ */
/* Global search (§8)                                                  */
/* ------------------------------------------------------------------ */
function openSearch() {
  let selected = 0;
  let results = [];
  const input = h('input', { class: 'input', placeholder: 'جستجو در تجهیزات، برنامه‌ها، کاربران…', autocomplete: 'off' });
  const box = h('div', { class: 'search-results' },
    h('div', { class: 'empty-state small faint' }, 'حداقل ۲ نویسه تایپ کنید'));
  const m = openModal({ title: '', body: h('div', {}, input, box), size: 'search-modal' });
  m.overlay.querySelector('.modal-head').remove();
  setTimeout(() => input.focus(), 40);

  let timer = null;
  input.addEventListener('input', () => {
    clearTimeout(timer);
    const q = input.value.trim();
    if (q.length < 2) { box.replaceChildren(h('div', { class: 'empty-state small faint' }, 'حداقل ۲ نویسه تایپ کنید')); return; }
    timer = setTimeout(() => runSearch(q), 250);
  });

  async function runSearch(q) {
    try {
      const data = await api(`/search?q=${encodeURIComponent(q)}`);
      results = [];
      box.replaceChildren();
      const groups = [
        ['equipment', 'تجهیزات', (x) => ({ label: `${x.code} — ${x.name}`, go: () => navigate(`#/equipment/${x.id}`) })],
        ['plans', 'برنامه‌های نت', (x) => ({ label: x.title, go: () => navigate(`#/equipment/${x.equipment_id}`) })],
        ['categories', 'دسته‌بندی‌ها', (x) => ({ label: x.name, go: () => navigate('#/admin/base') })],
        ['factories', 'کارخانه‌ها', (x) => ({ label: x.name, go: () => navigate('#/admin/base') })],
        ['users', 'کاربران', (x) => ({ label: `${x.full_name} (${x.username})`, go: () => navigate('#/admin/users') })],
      ];
      for (const [key, title, mk] of groups) {
        const items = data[key] || [];
        if (!items.length) continue;
        box.append(h('div', { class: 'search-group-title' }, title));
        for (const it of items) {
          const r = mk(it);
          const node = h('div', { class: 'search-item', onclick: () => { m.close(); r.go(); } }, r.label);
          results.push(node);
          box.append(node);
        }
      }
      selected = 0;
      markSelected();
      if (!results.length) box.replaceChildren(h('div', { class: 'empty-state small faint' }, 'نتیجه‌ای یافت نشد'));
    } catch (e) { /* ignore */ }
  }

  function markSelected() {
    results.forEach((n, i) => n.classList.toggle('selected', i === selected));
    if (results[selected]) results[selected].scrollIntoView({ block: 'nearest' });
  }

  input.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); selected = Math.min(selected + 1, results.length - 1); markSelected(); }
    if (e.key === 'ArrowUp') { e.preventDefault(); selected = Math.max(selected - 1, 0); markSelected(); }
    if (e.key === 'Enter' && results[selected]) results[selected].click();
    if (e.key === 'Escape') m.close();
  });
}

document.addEventListener('keydown', (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
    e.preventDefault();
    if (Session.token) openSearch();
  }
});

/* ------------------------------------------------------------------ */
/* Real-time SSE (§34)                                                 */
/* ------------------------------------------------------------------ */
function connectSSE() {
  if (sse) sse.close();
  if (!Session.token) return;
  sse = new EventSource(`/api/events/stream?token=${encodeURIComponent(Session.token)}`);
  sse.onopen = () => setConn('online');
  sse.onerror = () => setConn(navigator.onLine ? 'syncing' : 'offline');

  const refreshEvents = [
    'equipment.created', 'equipment.updated', 'equipment.deleted',
    'equipment.bulk_imported', 'equipment.bulk_rollback',
    'pm.created', 'pm.updated',
    'request.created', 'request.updated', 'request.approved', 'request.rejected',
    'workorder.created', 'workorder.updated', 'workorder.status_changed',
    'pm.completed',
  ];
  refreshEvents.forEach((ev) => sse.addEventListener(ev, () => {
    // Live refresh without page reload (§33): re-dispatch current route.
    const main = $('#main');
    if (main && !document.querySelector('.modal')) dispatch();
  }));
  sse.addEventListener('notification.created', () => {
    window.refreshBell?.();
    const ev = new CustomEvent('cmms:notification');
    window.dispatchEvent(ev);
  });
}

window.addEventListener('online', () => setConn('online'));
window.addEventListener('offline', () => setConn('offline'));

/* ------------------------------------------------------------------ */
/* Routes                                                              */
/* ------------------------------------------------------------------ */
function guard(perm, fn) {
  return async (params) => {
    if (!Session.token) return navigate('#/login');
    if (perm && !Session.can(perm)) {
      shell(location.hash.slice(1));
      $('#main').replaceChildren(
        h('div', { class: 'card' }, h('div', { class: 'card-body empty-state' },
          h('div', { class: 'empty-icon' }, '🔒'),
          h('h3', {}, 'دسترسی مجاز نیست'),
          h('p', { class: 'muted small' }, 'نقش شما اجازه مشاهده این بخش را ندارد.'))));
      return;
    }
    shell(location.hash.slice(1));
    await fn(params, $('#main'));
  };
}

route('/login', async (_p, _main) => renderLogin());
route('/', guard(null, () => navigate('#/dashboard')));
route('/dashboard', guard('dashboard.view', (_p, main) => renderDashboard(main)));
route('/equipment', guard('equipment.view', (_p, main) => renderEquipmentList(main)));
route('/equipment/new', guard('equipment.create', (_p, main) => renderWizard(main)));
route('/equipment/:id', guard('equipment.view', (p, main) => renderEquipmentDetail(main, p.id)));
route('/equipment/:id/passport', guard('equipment.view', (p, main) => renderPassport(main, p.id)));
route('/requests', guard('requests.view', (_p, main) => renderRequests(main)));
route('/work-orders', guard('workorders.view', (_p, main) => renderWorkOrders(main)));
route('/work-orders/:id', guard('workorders.view', (p, main) => renderWorkOrderDetail(main, p.id)));
route('/notifications', guard('notifications.view', (_p, main) => renderNotifications(main)));
route('/selen', guard('selen.use', (_p, main) => renderSelen(main)));
route('/checklists', guard('checklist.view', (_p, main) => renderChecklists(main)));
route('/checklists/:id', guard('checklist.view', (p, main) => renderChecklistRun(main, p.id)));
route('/risks', guard('risks.view', (_p, main) => renderRisks(main)));
route('/calibration', guard('calibration.view', (_p, main) => renderCalibration(main)));
route('/parts', guard('parts.view', (_p, main) => renderParts(main)));
route('/suppliers', guard('parts.view', (_p, main) => renderSuppliers(main)));
route('/consultation', guard('messages.view', (_p, main) => renderConsultation(main)));
route('/reports', guard('reports.view', (_p, main) => renderReports(main)));
route('/import', guard('import.manage', (_p, main) => renderBulkImport(main)));
route('/bulk-charge', guard('bulk_charge.charge', (_p, main) => renderBulkCharge(main)));
route('/admin/users', guard('users.view', (_p, main) => renderUsers(main)));
route('/admin/roles', guard('roles.manage', (_p, main) => renderRoles(main)));
route('/admin/base', guard('base_data.manage', (_p, main) => renderBaseData(main)));
route('/admin/audit', guard('audit.view', (_p, main) => renderAudit(main)));
route('/admin/backup', guard('backup.manage', (_p, main) => renderBackup(main)));
route('/settings', guard(null, (_p, main) => renderSettings(main)));
setNotFound(() => navigate('#/dashboard'));

/* ------------------------------------------------------------------ */
/* Boot                                                                */
/* ------------------------------------------------------------------ */
(async function boot() {
  if (!Session.token) { navigate('#/login'); return; }
  try {
    const me = await api('/auth/me');  // validate token at startup
    Session.user = me.user;
    Session.permissions = me.permissions;
    localStorage.setItem('cmms_user', JSON.stringify(me.user));
    localStorage.setItem('cmms_perms', JSON.stringify(me.permissions));
    connectSSE();
    dispatch();
  } catch {
    Session.clear();
    navigate('#/login');
  }
})();
