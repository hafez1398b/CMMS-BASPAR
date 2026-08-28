/** Work Orders list (§18). */
import {
  api, errText, h, faNum, toast, navigate, spinner, table, pager, Session, openModal,
} from '../core.js?v=11';
import { toJalaliStr } from '../jalali.js?v=11';

export const WO_STATUS = {
  created: ['neutral', 'ایجاد شده'],
  pending_permit: ['warning', 'در انتظار Permit/HSE'],
  ready: ['info', 'آماده اجرا'],
  in_progress: ['primary', 'در حال اجرا'],
  paused: ['warning', 'توقف موقت'],
  awaiting_confirmation: ['warning', 'در انتظار تأیید درخواست‌دهنده'],
  final_approval: ['info', 'در انتظار تأیید نهایی'],
  closed: ['success', 'بسته شده'],
  rejected: ['danger', 'رد شده'],
  cancelled: ['neutral', 'لغو شده'],
};
const PRIO_BADGE = { low: 'neutral', normal: 'info', high: 'warning', emergency: 'danger' };

export async function renderWorkOrders(main) {
  let page = 1, statusFilter = '', q = '';
  main.replaceChildren(h('div', { class: 'page-head' }, h('h1', {}, 'دستور کارها')), spinner());

  const sel = h('select', { class: 'select', style: 'max-width:250px' },
    h('option', { value: '' }, 'همه وضعیت‌ها'),
    ...Object.entries(WO_STATUS).map(([k, v]) => h('option', { value: k }, v[1])));
  sel.onchange = () => { statusFilter = sel.value; page = 1; load(); };
  const search = h('input', { class: 'input', placeholder: 'جستجو: کد / عنوان', style: 'max-width:230px' });
  let t = null;
  search.addEventListener('input', () => { clearTimeout(t); t = setTimeout(() => { q = search.value.trim(); page = 1; load(); }, 300); });

  async function load() {
    try {
      const qs = new URLSearchParams({ page, page_size: 25 });
      if (statusFilter) qs.set('status', statusFilter);
      if (q) qs.set('q', q);
      const data = await api(`/work-orders?${qs}`);
      const rows = data.items.map((w) => h('tr', { class: 'clickable', onclick: () => navigate(`#/work-orders/${w.id}`) },
        h('td', { class: 'ltr' }, w.code),
        h('td', {}, h('strong', {}, w.title)),
        h('td', { class: 'small' }, w.equipment_name || '—'),
        h('td', {}, h('span', { class: `badge ${(WO_STATUS[w.status] || ['neutral'])[0]}` }, (WO_STATUS[w.status] || [null, w.status])[1])),
        h('td', {}, h('span', { class: `badge ${PRIO_BADGE[w.priority] || 'neutral'}` }, w.priority)),
        h('td', { class: 'small' }, w.assignee_name || '—'),
        h('td', { class: 'small' }, faNum(w.duration_minutes || 0) + ' دقیقه'),
        h('td', { class: 'ltr small' }, toJalaliStr(w.created_at, true))));
      main.replaceChildren(
        h('div', { class: 'page-head' },
          h('h1', {}, 'دستور کارها'),
          h('div', { class: 'spacer' }),
          search, sel,
          Session.can('workorders.create')
            ? h('button', { class: 'btn btn-primary', onclick: createModal }, '+ دستور کار جدید') : null),
        table(['کد', 'عنوان', 'تجهیز', 'وضعیت', 'اولویت', 'تکنسین', 'مدت اجرا', 'تاریخ'], rows),
        pager(page, data.total, 25, (p) => { page = p; load(); }));
    } catch (e) { toast(errText(e), 'danger'); }
  }

  async function createModal() {
    let equipment = [];
    try { equipment = (await api('/equipment?page_size=200&level=equipment')).items; } catch { }
    const title = h('input', { class: 'input' });
    const desc = h('textarea', { class: 'textarea' });
    const eqSel = h('select', { class: 'select' },
      h('option', { value: '' }, 'بدون تجهیز'),
      ...equipment.map((e) => h('option', { value: String(e.id) }, `${e.code} — ${e.name}`)));
    const saveBtn = h('button', { class: 'btn btn-primary' }, 'ایجاد');
    const m = openModal({
      title: 'دستور کار جدید',
      body: h('div', { class: 'form-grid' },
        h('div', { class: 'field span-2' }, h('label', {}, 'عنوان *'), title),
        h('div', { class: 'field span-2' }, h('label', {}, 'تجهیز'), eqSel),
        h('div', { class: 'field span-2' }, h('label', {}, 'شرح'), desc)),
      footer: [saveBtn],
    });
    saveBtn.onclick = async () => {
      try {
        const wo = await api('/work-orders', { method: 'POST', body: {
          title: title.value.trim(), description: desc.value || null,
          equipment_id: eqSel.value ? +eqSel.value : null,
          permit_required: false,
        } });
        toast(`دستور کار ${wo.code} ایجاد شد`, 'success');
        m.close(); navigate(`#/work-orders/${wo.id}`);
      } catch (e) { toast(errText(e), 'danger'); }
    };
  }

  await load();
}
