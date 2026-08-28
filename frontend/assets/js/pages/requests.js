/** Work Requests (§17, §18 steps 1–3). */
import {
  api, errText, h, faNum, toast, openModal, spinner, table, pager,
  Session, navigate,
} from '../core.js?v=11';
import { toJalaliStr } from '../jalali.js?v=11';

const STATUS_BADGE = {
  pending_supervisor: ['warning', 'در انتظار سرپرست'],
  pending_manager: ['warning', 'در انتظار مدیر فنی'],
  converted: ['success', 'تبدیل به دستور کار'],
  rejected: ['danger', 'رد شده'],
  draft: ['neutral', 'پیش‌نویس'],
};
const TYPE_FA = {
  repair: 'تعمیر', service: 'سرویس', modification: 'اصلاح', inspection: 'بازرسی',
  improvement: 'بهبود', emergency: 'اضطراری', other: 'سایر',
};
const PRIO_BADGE = { low: 'neutral', normal: 'info', high: 'warning', emergency: 'danger' };
const PRIO_FA = { low: 'کم', normal: 'عادی', high: 'زیاد', emergency: 'اضطراری' };

export async function renderRequests(main) {
  let page = 1, statusFilter = '';
  main.replaceChildren(h('div', { class: 'page-head' }, h('h1', {}, 'درخواست‌های کار')), spinner());

  const sel = h('select', { class: 'select', style: 'max-width:220px' },
    h('option', { value: '' }, 'همه وضعیت‌ها'),
    ...Object.entries(STATUS_BADGE).map(([k, v]) => h('option', { value: k }, v[1])));
  sel.onchange = () => { statusFilter = sel.value; page = 1; load(); };

  async function load() {
    try {
      const qs = new URLSearchParams({ page, page_size: 25 });
      if (statusFilter) qs.set('status', statusFilter);
      const data = await api(`/requests?${qs}`);
      const rows = data.items.map((r) => h('tr', { class: 'clickable', onclick: () => openDetail(r.id) },
        h('td', {}, faNum(r.id)),
        h('td', {}, h('strong', {}, r.title)),
        h('td', { class: 'small' }, TYPE_FA[r.request_type] || r.request_type),
        h('td', { class: 'small' }, r.equipment_name || '—'),
        h('td', {}, h('span', { class: `badge ${PRIO_BADGE[r.priority] || 'neutral'}` }, PRIO_FA[r.priority] || r.priority)),
        h('td', {}, h('span', { class: `badge ${(STATUS_BADGE[r.status] || ['neutral'])[0]}` }, (STATUS_BADGE[r.status] || [null, r.status])[1])),
        h('td', { class: 'small muted' }, r.requester_name || '—'),
        h('td', { class: 'ltr small' }, toJalaliStr(r.created_at, true))));
      main.replaceChildren(
        h('div', { class: 'page-head' },
          h('h1', {}, 'درخواست‌های کار'),
          h('div', { class: 'spacer' }),
          sel,
          Session.can('requests.create')
            ? h('button', { class: 'btn btn-primary', onclick: createModal }, '+ درخواست جدید') : null),
        table(['#', 'عنوان', 'نوع', 'تجهیز', 'اولویت', 'وضعیت', 'درخواست‌دهنده', 'تاریخ'], rows),
        pager(page, data.total, 25, (p) => { page = p; load(); }));
    } catch (e) { toast(errText(e), 'danger'); }
  }

  async function createModal() {
    let equipment = [];
    try { equipment = (await api('/equipment?page_size=200&level=equipment')).items; } catch { }
    const title = h('input', { class: 'input', placeholder: 'شرح کوتاه درخواست' });
    const desc = h('textarea', { class: 'textarea', placeholder: 'توضیحات تکمیلی…' });
    const typeSel = h('select', { class: 'select' },
      ...Object.entries(TYPE_FA).map(([k, v]) => h('option', { value: k }, v)));
    const prioSel = h('select', { class: 'select' },
      ...Object.entries(PRIO_FA).map(([k, v]) => h('option', { value: k }, v)));
    const eqSel = h('select', { class: 'select' },
      h('option', { value: '' }, 'بدون تجهیز'),
      ...equipment.map((e) => h('option', { value: String(e.id) }, `${e.code} — ${e.name}`)));
    const saveBtn = h('button', { class: 'btn btn-primary' }, 'ثبت درخواست');
    const m = openModal({
      title: 'درخواست کار جدید (§17)',
      body: h('div', { class: 'form-grid' },
        h('div', { class: 'field span-2' }, h('label', {}, 'عنوان *'), title),
        h('div', { class: 'field' }, h('label', {}, 'نوع درخواست'), typeSel),
        h('div', { class: 'field' }, h('label', {}, 'اولویت'), prioSel),
        h('div', { class: 'field span-2' }, h('label', {}, 'تجهیز مرتبط'), eqSel),
        h('div', { class: 'field span-2' }, h('label', {}, 'توضیحات'), desc)),
      footer: [saveBtn],
    });
    saveBtn.onclick = async () => {
      try {
        await api('/requests', { method: 'POST', body: {
          title: title.value.trim(), description: desc.value || null,
          request_type: typeSel.value, priority: prioSel.value,
          equipment_id: eqSel.value ? +eqSel.value : null,
        } });
        toast('درخواست ثبت شد و برای سرپرست ارسال گردید', 'success');
        m.close(); load();
      } catch (e) { toast(errText(e), 'danger'); }
    };
  }

  async function openDetail(rid) {
    const items = (await api(`/requests?page_size=200`)).items;
    const r = items.find((x) => x.id === rid);
    if (!r) return;
    const foot = [];
    if (r.status === 'pending_supervisor' && Session.can('requests.approve')) {
      foot.push(decisionBtn(rid, 'supervisor-decision', true, 'تأیید (سرپرست)'));
      foot.push(decisionBtn(rid, 'supervisor-decision', false, 'رد (سرپرست)', true));
    }
    if (r.status === 'pending_manager' && Session.can('requests.approve')) {
      foot.push(decisionBtn(rid, 'manager-decision', true, 'تأیید و صدور دستور کار'));
      foot.push(decisionBtn(rid, 'manager-decision', false, 'رد (مدیر فنی)', true));
    }
    const kv = (k, v) => h('tr', {}, h('td', { class: 'muted small', style: 'width:150px' }, k), h('td', {}, v ?? '—'));
    openModal({
      title: `درخواست #${faNum(r.id)} — ${r.title}`,
      body: h('div', {},
        h('table', { class: 'table spec-table' }, h('tbody', {}, [
          kv('نوع', TYPE_FA[r.request_type]),
          kv('اولویت', PRIO_FA[r.priority]),
          kv('تجهیز', r.equipment_name && `${r.equipment_code} — ${r.equipment_name}`),
          kv('وضعیت', (STATUS_BADGE[r.status] || [null, r.status])[1]),
          kv('درخواست‌دهنده', r.requester_name),
          kv('تاریخ', toJalaliStr(r.created_at, true)),
          kv('یادداشت تصمیم', r.decision_note),
        ])),
        r.description ? h('p', { class: 'mt-4' }, r.description) : null),
      footer: foot,
    });
  }

  function decisionBtn(rid, endpoint, approve, label, danger = false) {
    return h('button', { class: `btn ${danger ? 'btn-danger' : 'btn-primary'}`, onclick: async () => {
      try {
        const res = await api(`/requests/${rid}/${endpoint}`, { method: 'POST', body: { approve } });
        toast(approve ? 'تأیید شد' : 'رد شد', approve ? 'success' : 'warning');
        document.querySelector('.overlay')?.remove();
        if (res.work_order_id) navigate(`#/work-orders/${res.work_order_id}`);
        else load();
      } catch (e) { toast(errText(e), 'danger'); }
    } }, label);
  }

  await load();
}
