/**
 * BASPAR CMMS — Application Shell v2
 * Dark First · Enterprise · ServiceNow + Vercel
 * Layout: Header (global search + AI + notifications) + Sidebar (collapsible + nested) + Main
 */

import {
  Session, api, errText, h, $, mount, navigate, route, setNotFound,
  dispatch, toast, openModal, spinner,
} from './core.js?v=12';
import { icon } from './icons.js?v=12';

import { renderLogin } from './pages/auth.js?v=12';
import { renderDashboard } from './pages/dashboard.js?v=12';
import { renderEquipmentList } from './pages/equipment.js?v=12';
import { renderEquipmentDetail } from './pages/equipment-detail.js?v=12';
import { renderWizard } from './pages/equipment-wizard.js?v=12';
import { renderBulkImport } from './pages/bulk-import.js?v=12';
import { renderPassport } from './pages/passport.js?v=12';
import {
  renderUsers, renderRoles, renderBaseData, renderAudit, renderBackup, renderSettings,
} from './pages/admin.js?v=12';
import { renderRequests } from './pages/requests.js?v=12';
import { renderWorkOrders } from './pages/workorders.js?v=12';
import { renderWorkOrderDetail } from './pages/workorder-detail.js?v=12';
import { renderNotifications } from './pages/notifications.js?v=12';
import { renderSelen } from './pages/selen.js?v=12';
import { renderChecklists, renderChecklistRun } from './pages/checklists.js?v=12';
import { renderRisks } from './pages/risks.js?v=12';
import { renderCalibration } from './pages/calibration.js?v=12';
import { renderParts } from './pages/parts.js?v=12';
import { renderSuppliers } from './pages/suppliers.js?v=12';
import { renderConsultation } from './pages/consultation.js?v=12';
import { renderReports } from './pages/reports.js?v=12';
import { renderBulkCharge } from './pages/bulk-charge.js?v=12';
import { watchConnectivity, pendingCount } from './offline.js?v=12';

/* ------------------------------------------------------------------ */
/* Navigation — Enterprise, Role-based, Nested Factories              */
/* ------------------------------------------------------------------ */
const NAV = [
  { section: 'عملیات اصلی' },
  { hash: '#/dashboard', icon: 'dashboard', label: 'داشبورد', perm: 'dashboard.view' },
  {
    icon: 'equipment', label: 'تجهیزات و دارایی‌ها', perm: 'equipment.view',
    children: [
      { hash: '#/equipment?factory=بسپار۱', label: 'بسپار ۱ (فوم)', icon: 'factory' },
      { hash: '#/equipment?factory=بسپار۲', label: 'بسپار ۲ (کارتن)', icon: 'factory' },
      { hash: '#/equipment?factory=بسپار۳', label: 'بسپار ۳ (اسفنج)', icon: 'factory' },
      { hash: '#/equipment?factory=بسپار۴', label: 'بسپار ۴', icon: 'factory' },
      { hash: '#/equipment?factory=بسپار۵', label: 'بسپار ۵', icon: 'factory' },
      { hash: '#/equipment?factory=بسپار۶', label: 'بسپار ۶', icon: 'factory' },
      { hash: '#/equipment', label: 'همه تجهیزات', icon: 'equipment' },
    ]
  },
  {
    icon: 'workorders', label: 'دستورکارها', perm: 'workorders.view',
    children: [
      { hash: '#/requests', label: 'درخواست تعمیر', icon: 'requests' },
      { hash: '#/work-orders?status=open', label: 'در انتظار تأیید', icon: 'clock' },
      { hash: '#/work-orders?status=in_progress', label: 'در حال انجام', icon: 'activity' },
      { hash: '#/work-orders?status=completed', label: 'تکمیل شده', icon: 'check' },
      { hash: '#/work-orders', label: 'همه دستورکارها', icon: 'workorders' },
    ]
  },
  { hash: '#/import', icon: 'import', label: 'ورود سریع', perm: 'import.manage' },
  { hash: '#/bulk-charge', icon: 'charge', label: 'مرکز شارژ داده', perm: 'bulk_charge.charge', badge: '6B' },
  { hash: '#/checklists', icon: 'checklists', label: 'چک‌لیست بازرسی', perm: 'checklist.view' },
  { hash: '#/parts', icon: 'parts', label: 'انبار و قطعات', perm: 'parts.view' },
  { hash: '#/suppliers', icon: 'parts', label: 'خرید و تامین‌کنندگان', perm: 'parts.view' },
  { hash: '#/notifications', icon: 'notifications', label: 'اعلان‌ها', perm: 'notifications.view' },

  { section: 'تحلیل و پیشگیری' },
  { hash: '#/selen', icon: 'selen', label: 'دستیار هوشمند SELEN', perm: 'selen.use', accent: 'gold' },
  { hash: '#/risks', icon: 'risks', label: 'ریسک و فرصت', perm: 'risks.view' },
  { hash: '#/calibration', icon: 'calibration', label: 'کالیبراسیون', perm: 'calibration.view' },
  { hash: '#/reports', icon: 'reports', label: 'گزارشات و KPI', perm: 'reports.view' },

  { section: 'ارتباطات' },
  { hash: '#/consultation', icon: 'consultation', label: 'مشاوره داخلی', perm: 'messages.view' },

  { section: 'مدیریت سیستم' },
  { hash: '#/admin/users', icon: 'users', label: 'کاربران و تیم‌ها', perm: 'users.view' },
  { hash: '#/admin/roles', icon: 'roles', label: 'نقش‌ها و دسترسی‌ها', perm: 'roles.manage' },
  { hash: '#/admin/base', icon: 'base', label: 'داده‌های پایه', perm: 'base_data.manage' },
  { hash: '#/admin/audit', icon: 'audit', label: 'گزارش ممیزی', perm: 'audit.view' },
  { hash: '#/admin/backup', icon: 'backup', label: 'پشتیبان‌گیری', perm: 'backup.manage' },
  { hash: '#/settings', icon: 'settings', label: 'تنظیمات سیستم', perm: null },
];

let sidebarCollapsed = localStorage.getItem('cmms_sidebar') === '1';
let sidebarOpenMap = JSON.parse(localStorage.getItem('cmms_sidebar_open') || '{}');
let currentTheme = localStorage.getItem('cmms_theme') || 'dark';
let sse = null;

function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem('cmms_theme', theme);
  currentTheme = theme;
}

applyTheme(currentTheme);

function toggleTheme() {
  applyTheme(currentTheme === 'dark' ? 'light' : 'dark');
  const iconEl = $('#theme-icon');
  if (iconEl) iconEl.innerHTML = icon(currentTheme === 'dark' ? 'moon' : 'sun');
  toast(`حالت ${currentTheme === 'dark' ? 'تاریک' : 'روشن'} فعال شد`, 'info');
}

function setConn(state) {
  const pill = $('#conn-pill');
  if (!pill) return;
  pill.className = `conn-pill ${state}`;
  const pending = pendingCount();
  pill.textContent = state === 'online'
    ? (pending ? `آنلاین · ${pending} در صف` : 'آنلاین')
    : state === 'offline'
      ? (pending ? `آفلاین · ${pending} در صف` : 'آفلاین')
      : 'همگام‌سازی';
}

watchConnectivity(setConn);

/* Notification bell */
function bell() {
  const btn = h('button', { class: 'btn btn-ghost btn-icon', title: 'اعلان‌ها', onclick: () => navigate('#/notifications') },
    h('span', { html: icon('notifications') })
  );
  async function refresh() {
    try {
      const { unread } = await api('/notifications/unread-count');
      btn.replaceChildren(h('span', { html: icon('notifications') }));
      if (unread > 0) {
        btn.append(h('span', {
          style: 'position:absolute;top:2px;right:2px;background:var(--c-danger);color:#fff;border-radius:99px;font-size:10px;min-width:16px;height:16px;display:flex;align-items:center;justify-content:center;padding:0 4px;font-weight:700',
        }, unread > 99 ? '99+' : String(unread)));
        btn.style.position = 'relative';
      }
    } catch {}
  }
  window.refreshBell = refresh;
  refresh();
  return btn;
}

/* Global search */
function globalSearch() {
  const wrap = h('div', { class: 'global-search' },
    h('span', { class: 'search-icon', html: icon('search') }),
    h('input', {
      class: 'search-input',
      placeholder: 'جستجو در تجهیزات، دستورکارها، قطعات... (Ctrl+K)',
      onclick: () => openSearch(),
      readonly: true,
    })
  );
  return wrap;
}

/* ------------------------------------------------------------------ */
/* Shell v2 — Premium Dark                                            */
/* ------------------------------------------------------------------ */
function shell(activeHash) {
  const u = Session.user || {};
  const activePath = activeHash.split('?')[0];

  // Sidebar nav builder
  const navNodes = [];
  NAV.filter(n => n.section || n.perm === null || Session.can(n.perm)).forEach(n => {
    if (n.section) {
      navNodes.push(h('div', { class: 'nav-section' }, n.section));
    } else if (n.children) {
      const isOpen = sidebarOpenMap[n.label] || activePath.startsWith(n.hash?.slice(1).split('?')[0] || '') || n.children.some(c => activeHash.startsWith(c.hash.slice(1).split('?')[0]));
      const parentActive = n.children.some(c => activeHash.startsWith(c.hash.slice(1).split('?')[0])) || activeHash.startsWith((n.hash || '').slice(1));
      const parent = h('div', {
        class: `nav-item ${parentActive ? 'active' : ''} ${isOpen ? 'open' : ''}`,
        onclick: () => {
          sidebarOpenMap[n.label] = !isOpen;
          localStorage.setItem('cmms_sidebar_open', JSON.stringify(sidebarOpenMap));
          const childWrap = parent.nextSibling;
          if (childWrap && childWrap.classList.contains('nav-children')) {
            childWrap.style.display = isOpen ? 'none' : 'block';
            parent.classList.toggle('open', !isOpen);
          }
        }
      },
        h('span', { class: 'nav-icon', html: icon(n.icon) }),
        h('span', { class: 'label' }, n.label),
        h('span', { class: 'nav-chevron', html: icon('chevron_right') })
      );
      const childrenWrap = h('div', {
        class: 'nav-children',
        style: `display:${isOpen ? 'block' : 'none'}`
      },
        n.children.map(ch =>
          h('div', {
            class: `nav-child ${activeHash.startsWith(ch.hash.slice(1).split('?')[0]) ? 'active' : ''}`,
            onclick: (e) => { e.stopPropagation(); navigate(ch.hash); }
          },
            h('span', { class: 'nav-icon', html: icon(ch.icon || 'chevron_right'), style: 'width:14px;height:14px' }),
            h('span', {}, ch.label)
          )
        )
      );
      navNodes.push(parent, childrenWrap);
    } else {
      const isActive = activeHash.startsWith(n.hash.slice(1).split('?')[0]) || activePath === n.hash.slice(1);
      navNodes.push(
        h('div', {
          class: `nav-item ${isActive ? 'active' : ''} ${n.accent === 'gold' ? 'gold-accent' : ''}`,
          onclick: () => { navigate(n.hash); document.body.classList.remove('sidebar-open'); }
        },
          h('span', { class: 'nav-icon', html: icon(n.icon) }),
          h('span', { class: 'label' }, n.label),
          n.badge ? h('span', { class: 'badge gold', style: 'margin-inline-start:auto;font-size:10px' }, n.badge) : null
        )
      );
    }
  });

  const sidebar = h('aside', { class: `sidebar ${sidebarCollapsed ? 'collapsed' : ''}` },
    h('nav', { class: 'sidebar-nav' }, navNodes),
    h('div', { class: 'sidebar-foot' },
      h('div', { class: 'version' },
        h('span', { class: 'dot' }),
        h('span', { class: 'label' }, 'BASPAR CMMS v0.4 · Enterprise · Dark First')
      )
    )
  );

  // Check if we should show intro animation (once per session)
  const showIntro = !sessionStorage.getItem('bfg_intro_done');

  const header = h('header', {},
    h('button', {
      class: 'btn btn-ghost btn-icon', title: 'منو',
      onclick: () => {
        if (window.innerWidth <= 900) {
          sidebar.classList.toggle('mobile-open');
        } else {
          sidebarCollapsed = !sidebarCollapsed;
          sidebar.classList.toggle('collapsed');
          localStorage.setItem('cmms_sidebar', sidebarCollapsed ? '1' : '0');
        }
      }
    }, h('span', { html: icon('menu') })),

    h('div', { class: 'brand' },
      h('span', { class: 'brand-mark', style: 'background:#fff;padding:2px;border:1px solid var(--c-border);overflow:hidden' },
        h('img', {
          src: '/assets/bfg-logo.png',
          alt: 'BFG',
          style: 'width:100%;height:100%;object-fit:contain',
          onerror: function() { this.parentNode.textContent='B'; this.parentNode.style.background='var(--c-gold)'; }
        })
      ),
      h('div', { class: 'brand-text' },
        h('strong', {}, 'BASPAR CMMS'),
        h('small', {}, 'AI Maintenance Platform')
      )
    ),

    globalSearch(),

    h('div', { class: 'header-actions' },
      h('button', {
        class: 'btn btn-ghost btn-sm ai-pulse',
        style: 'border-color:var(--c-gold-border);color:var(--c-gold)',
        onclick: () => navigate('#/selen'),
        title: 'دستیار هوشمند SELEN'
      },
        h('span', { html: icon('sparkles'), style: 'width:14px;height:14px' }),
        h('span', { class: 'label', style: 'font-size:12px' }, 'دستیار هوشمند')
      ),

      h('div', { class: 'header-divider' }),

      h('button', { class: 'btn btn-ghost btn-icon', title: 'تقویم', onclick: () => toast('تقویم شمسی فعال است', 'info') },
        h('span', { html: icon('calendar') })
      ),

      h('button', {
        class: 'btn btn-ghost btn-icon', title: 'تغییر تم',
        onclick: toggleTheme
      },
        h('span', { id: 'theme-icon', html: icon(currentTheme === 'dark' ? 'moon' : 'sun') })
      ),

      bell(),

      h('span', { id: 'conn-pill', class: 'conn-pill online' }, 'آنلاین'),

      h('div', { class: 'header-divider' }),

      h('div', { style: 'display:flex;align-items:center;gap:10px' },
        h('div', { style: 'text-align:left;line-height:1.2' },
          h('div', { style: 'font-weight:600;font-size:12px' }, u.full_name || u.username || 'کاربر'),
          h('div', { class: 'faint', style: 'font-size:10px' }, (u.roles || []).map(r => r.title_fa).join('، ') || 'مدیر نگهداری')
        ),
        h('div', {
          class: 'activity-avatar',
          style: 'background:var(--c-gold);color:#0A0A0A;font-weight:700;width:32px;height:32px'
        }, (u.full_name || 'م ب').slice(0, 2))
      ),

      h('button', { class: 'btn btn-ghost btn-sm', onclick: logout, title: 'خروج' },
        h('span', { html: icon('x'), style: 'width:14px;height:14px' })
      )
    )
  );

  const main = h('main', { id: 'main', class: 'page-enter' }, spinner());

  const el = h('div', { class: 'app-shell' }, header,
    h('div', { class: 'shell-body' }, sidebar, main)
  );

  mount(el);

  // BFG intro animation — full screen → corner (once per session)
  if (showIntro) {
    const intro = h('div', {
      style: `
        position:fixed;inset:0;z-index:9998;
        background:var(--c-bg);
        display:flex;align-items:center;justify-content:center;
        flex-direction:column;gap:16px;
      `
    },
      h('img', {
        src: '/assets/bfg-logo.png',
        style: 'width:320px;height:auto;filter:drop-shadow(0 0 40px rgba(220,38,38,0.3));animation:introLogo 1.8s cubic-bezier(0.16,1,0.3,1) forwards',
        onerror: function() { this.style.display='none'; }
      }),
      h('div', { style: 'font-size:14px;color:var(--c-text-2);animation:introText 0.8s ease 0.6s both' }, 'شرکت بسپار فوم غرب · BASPAR CMMS')
    );

    const introStyle = h('style', {}, `
      @keyframes introLogo {
        0% { transform:scale(0.4); opacity:0; }
        30% { transform:scale(1.1); opacity:1; }
        60% { transform:scale(1); opacity:1; }
        100% { transform:scale(0.12) translate(-110vw, -42vh); opacity:0; }
      }
      @keyframes introText {
        0% { opacity:0; transform:translateY(8px); }
        100% { opacity:1; transform:translateY(0); }
      }
    `);
    document.body.append(introStyle, intro);
    sessionStorage.setItem('bfg_intro_done', '1');
    setTimeout(() => {
      intro.style.transition = 'opacity 0.5s ease';
      intro.style.opacity = '0';
      setTimeout(() => { intro.remove(); introStyle.remove(); }, 500);
    }, 1600);
  }

  return main;
}

async function logout() {
  try { await api('/auth/logout', { method: 'POST' }); } catch {}
  Session.clear();
  if (sse) { sse.close(); sse = null; }
  navigate('#/login');
}

/* ------------------------------------------------------------------ */
/* Global search — Command palette                                    */
/* ------------------------------------------------------------------ */
function openSearch() {
  let selected = 0;
  let results = [];
  const input = h('input', { class: 'input', placeholder: 'جستجو در تجهیزات، برنامه‌ها، کاربران… (حداقل ۲ حرف)', autocomplete: 'off' });
  const box = h('div', { class: 'search-results' },
    h('div', { class: 'empty-state small faint' }, 'برای جستجو تایپ کنید — Ctrl+K')
  );
  const m = openModal({ title: '', body: h('div', {}, input, box), size: 'search-modal' });
  const head = m.overlay.querySelector('.modal-head');
  if (head) head.remove();
  setTimeout(() => input.focus(), 40);

  let timer = null;
  input.addEventListener('input', () => {
    clearTimeout(timer);
    const q = input.value.trim();
    if (q.length < 2) {
      box.replaceChildren(h('div', { class: 'empty-state small faint' }, 'حداقل ۲ نویسه تایپ کنید'));
      return;
    }
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
    } catch {}
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
/* Real-time SSE                                                      */
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
  refreshEvents.forEach(ev => sse.addEventListener(ev, () => {
    const main = $('#main');
    if (main && !document.querySelector('.modal')) dispatch();
  }));
  sse.addEventListener('notification.created', () => {
    window.refreshBell?.();
    window.dispatchEvent(new CustomEvent('cmms:notification'));
  });
}

window.addEventListener('online', () => setConn('online'));
window.addEventListener('offline', () => setConn('offline'));

/* ------------------------------------------------------------------ */
/* Routes                                                             */
/* ------------------------------------------------------------------ */
function guard(perm, fn) {
  return async (params) => {
    if (!Session.token) return navigate('#/login');
    if (perm && !Session.can(perm)) {
      shell(location.hash.slice(1));
      $('#main').replaceChildren(
        h('div', { class: 'card' }, h('div', { class: 'card-body empty-state' },
          h('div', { class: 'empty-icon', html: icon('roles') }),
          h('h3', {}, 'دسترسی مجاز نیست'),
          h('p', { class: 'muted small' }, 'نقش شما اجازه مشاهده این بخش را ندارد.')
        ))
      );
      return;
    }
    shell(location.hash.slice(1));
    await fn(params, $('#main'));
  };
}

route('/login', async () => renderLogin());
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

/* Boot */
(async function boot() {
  if (!Session.token) { navigate('#/login'); return; }
  try {
    const me = await api('/auth/me');
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
