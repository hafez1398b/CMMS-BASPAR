/** Notification Center (§31). */
import { api, errText, h, faNum, toast, spinner, pager, navigate } from '../core.js?v=12';
import { toJalaliStr } from '../jalali.js?v=12';

const KIND_ICON = { request: '📨', workorder: '🛠', pm: '🗓', system: '⚙', approval: '✔' };

export async function renderNotifications(main) {
  let page = 1, unreadOnly = false;
  main.replaceChildren(spinner());

  async function load() {
    try {
      const data = await api(`/notifications?unread_only=${unreadOnly}&page=${page}`);
      const rows = data.items.map((n) => h('tr', {
        class: 'clickable',
        style: n.is_read ? '' : 'background:var(--c-primary-soft)',
        onclick: async () => {
          if (!n.is_read) { try { await api(`/notifications/${n.id}/read`, { method: 'POST' }); } catch { } }
          if (n.link) navigate(n.link); else load();
          window.refreshBell?.();
        },
      },
        h('td', {}, KIND_ICON[n.kind] || '🔔'),
        h('td', {}, h('div', { style: n.is_read ? '' : 'font-weight:600' }, n.title),
          n.body ? h('div', { class: 'small muted' }, n.body) : null),
        h('td', { class: 'ltr small' }, toJalaliStr(n.created_at, true))));
      main.replaceChildren(
        h('div', { class: 'page-head' },
          h('h1', {}, 'مرکز اعلان‌ها'),
          h('div', { class: 'spacer' }),
          h('span', { class: 'small faint' }, `${faNum(data.unread)} خوانده‌نشده`),
          h('button', { class: 'btn btn-secondary btn-sm', onclick: async () => {
            try { await api('/notifications/read-all', { method: 'POST' }); toast('همه خوانده شدند', 'success'); window.refreshBell?.(); load(); }
            catch (e) { toast(errText(e), 'danger'); }
          } }, 'خواندن همه')),
        h('div', { class: 'toolbar' },
          h('label', { class: 'small', style: 'display:flex;gap:6px;align-items:center' },
            h('input', { type: 'checkbox', ...(unreadOnly ? { checked: true } : {}), onchange: (e) => { unreadOnly = e.target.checked; page = 1; load(); } }),
            'فقط خوانده‌نشده‌ها')),
        h('div', { class: 'table-wrap card' }, h('table', { class: 'table' },
          h('thead', {}, h('tr', {}, ['', 'اعلان', 'زمان'].map((x) => h('th', {}, x)))),
          h('tbody', {}, rows.length ? rows : h('tr', {}, h('td', { colspan: '3', class: 'small faint', style: 'text-align:center;padding:20px' }, 'اعلانی وجود ندارد'))))),
        pager(page, data.total, 20, (p) => { page = p; load(); }));
    } catch (e) { main.replaceChildren(h('div', { class: 'small', style: 'color:var(--c-danger)' }, errText(e))); }
  }

  await load();
}
