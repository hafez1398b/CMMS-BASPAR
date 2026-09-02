/**
 * BASPAR CMMS — SPA core: session, API client, hash router, UI primitives.
 * Zero external dependencies: plain ES modules (§42 source portability).
 */
import {
  toJalaliStr, todayJalali, JALALI_MONTHS, WEEKDAYS_FA,
  jalaliMonthLength, jalaliToGregorian, gregorianToJalali,
} from './jalali.js?v=12';
export { toJalaliStr };

/* --------------------------------------------------------------------- *
 * Session / RBAC state
 * --------------------------------------------------------------------- */
export const Session = {
  token: localStorage.getItem('cmms_token') || null,
  user: JSON.parse(localStorage.getItem('cmms_user') || 'null'),
  permissions: JSON.parse(localStorage.getItem('cmms_perms') || '[]'),

  save(token, user, permissions) {
    this.token = token; this.user = user; this.permissions = permissions || [];
    localStorage.setItem('cmms_token', token);
    localStorage.setItem('cmms_user', JSON.stringify(user));
    localStorage.setItem('cmms_perms', JSON.stringify(this.permissions));
  },
  clear() {
    this.token = null; this.user = null; this.permissions = [];
    localStorage.removeItem('cmms_token');
    localStorage.removeItem('cmms_user');
    localStorage.removeItem('cmms_perms');
  },
  can(code) {
    if (!this.user) return false;
    if ((this.user.roles || []).some(r => r.name === 'admin')) return true;
    return this.permissions.includes(code);
  },
};

/* --------------------------------------------------------------------- *
 * API client
 * --------------------------------------------------------------------- */
/** Extract a readable message from any FastAPI error payload. */
export function detailText(detail) {
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    const msgs = detail.map((e) => (e && (e.message || e.msg)) || 'خطای نامشخص');
    return msgs.join('؛ ');
  }
  if (detail && typeof detail === 'object') {
    if (detail.message) return detail.message;
    if (Array.isArray(detail.detail)) return detailText(detail.detail);
    if (typeof detail.detail === 'string') return detail.detail;
  }
  return '';
}

export class ApiError extends Error {
  constructor(status, detail) {
    super(detailText(detail) || 'خطا در ارتباط با سرور');
    this.status = status;
    this.detail = detail;
  }
}

/** Convert Persian/Arabic-Indic digits to Latin digits (for numeric fields). */
export const faToEnDigits = (v) => String(v ?? '')
  .replace(/[۰-۹]/g, (c) => String('۰۱۲۳۴۵۶۷۸۹'.indexOf(c)))
  .replace(/[٠-٩]/g, (c) => String('٠١٢٣٤٥٦٧٨٩'.indexOf(c)));

export async function api(path, { method = 'GET', body, form, raw } = {}) {
  const headers = {};
  if (Session.token) headers['Authorization'] = `Bearer ${Session.token}`;
  let payload;
  if (form) { payload = form; }
  else if (body !== undefined) { headers['Content-Type'] = 'application/json'; payload = JSON.stringify(body); }

  // Sandboxed previews run inside cross-site iframes where reverse proxies
  // may strip Authorization and browsers reject third-party cookies.
  // The query-token fallback (already supported server-side for SSE) keeps
  // the session alive in any embedding. Same-origin production deployments
  // simply use the header.
  let url = `/api${path}`;
  if (Session.token) {
    url += (url.includes('?') ? '&' : '?') + 'token=' + encodeURIComponent(Session.token);
  }

  let res;
  try {
    res = await fetch(url, { method, headers, body: payload });
  } catch {
    throw new ApiError(0, 'اتصال به سرور برقرار نشد');
  }

  if (res.status === 401 && !path.startsWith('/auth/login')) {
    Session.clear();
    location.hash = '#/login';
    throw new ApiError(401, 'نشست منقضی شد؛ دوباره وارد شوید');
  }
  if (raw) { if (!res.ok) throw new ApiError(res.status, await safeDetail(res)); return res; }
  if (res.status === 204) return null;
  const data = await res.json().catch(() => null);
  if (!res.ok) throw new ApiError(res.status, data ? data.detail : 'خطای نامشخص');
  return data;
}

async function safeDetail(res) {
  try { const d = await res.json(); return d.detail || res.statusText; } catch { return res.statusText; }
}

export function errText(e) {
  if (e instanceof ApiError) return detailText(e.detail) || e.message || 'خطای نامشخص';
  return e.message || 'خطای نامشخص';
}

/* --------------------------------------------------------------------- *
 * Router (hash based — works from any static host, no server rewrites)
 * --------------------------------------------------------------------- */
const routes = [];
let notFoundHandler = null;

export function route(pattern, handler) {
  // '#/equipment/:id' -> regex
  const keys = [];
  const rx = new RegExp('^' + pattern.replace(/:[^/]+/g, (m) => { keys.push(m.slice(1)); return '([^/]+)'; }) + '$');
  routes.push({ rx, keys, handler });
}
export function setNotFound(h) { notFoundHandler = h; }

export function navigate(hash) { location.hash = hash; }

export async function dispatch() {
  const hash = location.hash.slice(1) || '/';
  for (const r of routes) {
    const m = hash.match(r.rx);
    if (m) {
      const params = {};
      r.keys.forEach((k, i) => params[k] = decodeURIComponent(m[i + 1]));
      try { await r.handler(params); }
      catch (e) {
        console.error(e);
        renderError(errText(e));
      }
      return;
    }
  }
  if (notFoundHandler) notFoundHandler(); else navigate('#/dashboard');
}

window.addEventListener('hashchange', dispatch);

/* --------------------------------------------------------------------- *
 * DOM helpers
 * --------------------------------------------------------------------- */
export const $ = (sel, root = document) => root.querySelector(sel);
export const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

export function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (k === 'class') el.className = v;
    else if (k === 'html') el.innerHTML = v;
    else if (k.startsWith('on') && typeof v === 'function') el.addEventListener(k.slice(2), v);
    else if (v === false || v === null || v === undefined) continue;
    else if (v === true) el.setAttribute(k, '');
    else el.setAttribute(k, v);
  }
  appendChildren(el, children);
  return el;
}

function appendChildren(el, children) {
  for (const c of children.flat(Infinity)) {
    if (c === null || c === undefined || c === false) continue;
    el.append(c.nodeType ? c : document.createTextNode(String(c)));
  }
}

export const mount = (el) => { const app = $('#app'); app.replaceChildren(el); };

export const faNum = (n) => n === null || n === undefined ? '—'
  : Number(n).toLocaleString('fa-IR');

export function fmtBytes(b) {
  if (!b && b !== 0) return '—';
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
  return `${(b / 1024 / 1024).toFixed(1)} MB`;
}

export function downloadUrl(path) {
  // auth-gated downloads: fetch as blob then trigger save
  return api(path, { raw: true }).then(async (res) => {
    const blob = await res.blob();
    const cd = res.headers.get('content-disposition') || '';
    const m = cd.match(/filename\*=UTF-8''([^;]+)/i);
    const name = m ? decodeURIComponent(m[1]) : 'download';
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = name; a.click();
    setTimeout(() => URL.revokeObjectURL(url), 4000);
  });
}

/* --------------------------------------------------------------------- *
 * Toast / Modal / Confirm
 * --------------------------------------------------------------------- */
export function toast(msg, type = 'info', ms = 3800) {
  const host = $('#toast-host');
  const t = h('div', { class: `toast ${type}` }, msg);
  host.append(t);
  setTimeout(() => { t.style.opacity = '0'; t.style.transition = 'opacity .3s'; setTimeout(() => t.remove(), 320); }, ms);
}

export function openModal({ title, body, footer, size = '' }) {
  const overlay = h('div', { class: 'overlay', onclick: (e) => { if (e.target === overlay) close(); } });
  const modal = h('div', { class: `modal ${size}` },
    h('div', { class: 'modal-head' },
      h('h2', {}, title),
      h('button', { class: 'btn btn-ghost btn-sm', onclick: close }, '✕')),
    h('div', { class: 'modal-body' }, body),
    footer ? h('div', { class: 'modal-foot' }, footer) : null,
  );
  overlay.append(modal);
  document.body.append(overlay);
  function close() { overlay.remove(); }
  return { close, modal, overlay };
}

export function confirmDialog(message, { danger = false, title = 'تأیید عملیات' } = {}) {
  return new Promise((resolve) => {
    const okBtn = h('button', { class: `btn ${danger ? 'btn-danger' : 'btn-primary'}` }, 'تأیید');
    const cancelBtn = h('button', { class: 'btn btn-secondary' }, 'انصراف');
    const m = openModal({ title, body: h('p', {}, message), footer: [okBtn, cancelBtn] });
    okBtn.onclick = () => { m.close(); resolve(true); };
    cancelBtn.onclick = () => { m.close(); resolve(false); };
  });
}

/* --------------------------------------------------------------------- *
 * Reusable components
 * --------------------------------------------------------------------- */
export function spinner(text = 'در حال بارگذاری…') {
  return h('div', { class: 'loading-block' }, h('div', { class: 'spinner' }), h('div', { class: 'small faint' }, text));
}

export function emptyState(icon, title, sub, action) {
  return h('div', { class: 'empty-state' },
    h('div', { class: 'empty-icon' }, icon),
    h('h3', {}, title),
    sub ? h('div', { class: 'small muted mb-4' }, sub) : null,
    action || null);
}

export function renderError(msg) {
  mount(h('div', { class: 'card', style: 'max-width:560px;margin:60px auto' },
    h('div', { class: 'card-body', style: 'text-align:center' },
      h('div', { style: 'font-size:38px' }, '⚠️'),
      h('h2', {}, 'خطا'),
      h('p', { class: 'muted' }, msg),
      h('button', { class: 'btn btn-secondary', onclick: () => dispatch() }, 'تلاش مجدد'))));
}

const CRIT_BADGE = { low: 'neutral', medium: 'info', high: 'warning', critical: 'danger' };
export const critBadge = (c, label) => h('span', { class: `badge ${CRIT_BADGE[c] || 'neutral'}` }, label || c);

const STATUS_BADGE = { active: 'success', inactive: 'neutral', under_maintenance: 'warning', scrapped: 'danger' };
const STATUS_FA = { active: 'فعال', inactive: 'غیرفعال', under_maintenance: 'در دست تعمیر', scrapped: 'اسقاط' };
export const statusBadge = (s) => h('span', { class: `badge ${STATUS_BADGE[s] || 'neutral'}` }, STATUS_FA[s] || s);

export const LEVEL_FA = { equipment: 'تجهیز', subsystem: 'زیرسیستم', component: 'جزء', subcomponent: 'زیرقطعه' };

export function table(headers, rows) {
  return h('div', { class: 'table-wrap card' },
    h('table', { class: 'table' },
      h('thead', {}, h('tr', {}, headers.map((x) => h('th', {}, x)))),
      h('tbody', {}, rows.length ? rows : h('tr', {}, h('td', { colspan: String(headers.length) },
        h('div', { class: 'small faint', style: 'text-align:center;padding:18px' }, 'موردی یافت نشد'))))));
}

export function pager(page, total, pageSize, onPage) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  if (pages <= 1) return null;
  return h('div', { class: 'pager' },
    h('button', { class: 'btn btn-secondary btn-sm', disabled: page <= 1, onclick: () => onPage(page - 1) }, 'قبلی'),
    h('span', { class: 'small muted' }, `صفحه ${faNum(page)} از ${faNum(pages)}`),
    h('button', { class: 'btn btn-secondary btn-sm', disabled: page >= pages, onclick: () => onPage(page + 1) }, 'بعدی'));
}

/* --------------------------------------------------------------------- *
 * Jalali date picker (input component) §30
 * --------------------------------------------------------------------- */
export function jalaliInput({ value = '', onChange, placeholder = 'مثال: ۱۴۰۴/۰۵/۲۶' } = {}) {
  const input = h('input', { class: 'input ltr', placeholder, value, autocomplete: 'off' });
  const wrap = h('div', { style: 'position:relative' }, input);
  let pop = null;
  let view = null; // {jy, jm}

  input.addEventListener('focus', () => open());
  input.addEventListener('blur', () => setTimeout(close, 180));
  input.addEventListener('change', () => { if (onChange) onChange(input.value.trim()); });

  function current() {
    const m = (input.value.trim().replace(/[۰-۹]/g, (c) => '۰۱۲۳۴۵۶۷۸۹'.indexOf(c))
      .match(/^(\d{4})[\/\-.](\d{1,2})[\/\-.](\d{1,2})$/));
    if (m) return { jy: +m[1], jm: +m[2], jd: +m[3] };
    return null;
  }

  function open() {
    if (pop) return;
    view = current() || todayJalali();
    pop = h('div', { class: 'datepicker-pop' });
    wrap.append(pop);
    renderCal();
  }

  function renderCal() {
    if (!pop) return;
    pop.replaceChildren();
    const head = h('div', { class: 'dp-head' },
      h('button', { class: 'btn btn-ghost btn-sm', type: 'button', onclick: () => { view.jm++; if (view.jm > 12) { view.jm = 1; view.jy++; } renderCal(); } }, '❮'),
      h('strong', {}, `${JALALI_MONTHS[view.jm - 1]} ${view.jy}`),
      h('button', { class: 'btn btn-ghost btn-sm', type: 'button', onclick: () => { view.jm--; if (view.jm < 1) { view.jm = 12; view.jy--; } renderCal(); } }, '❯'));
    const grid = h('div', { class: 'dp-grid' });
    WEEKDAYS_FA.forEach((w) => grid.append(h('div', { class: 'dp-wd' }, w)));
    const first = jalaliToGregorian(view.jy, view.jm, 1);
    // JS getDay(): Sun=0..Sat=6 ; Persian week starts Saturday
    const startOffset = (first.getDay() + 1) % 7;
    for (let i = 0; i < startOffset; i++) grid.append(h('div', { class: 'dp-day blank' }));
    const len = jalaliMonthLength(view.jy, view.jm);
    const sel = current();
    const today = todayJalali();
    for (let d = 1; d <= len; d++) {
      const isSel = sel && sel.jy === view.jy && sel.jm === view.jm && sel.jd === d;
      const isToday = today.jy === view.jy && today.jm === view.jm && today.jd === d;
      grid.append(h('div', {
        class: `dp-day ${isSel ? 'selected' : ''} ${isToday ? 'today' : ''}`,
        onclick: () => {
          const v = `${view.jy}/${String(view.jm).padStart(2, '0')}/${String(d).padStart(2, '0')}`;
          input.value = v;
          if (onChange) onChange(v);
          close();
        },
      }, String(d)));
    }
    pop.append(head, grid);
  }

  function close() { if (pop) { pop.remove(); pop = null; } }
  return wrap;
}
