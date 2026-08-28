/** Risk & Opportunity register (§28). */
import {
  api, errText, h, faNum, toast, openModal, confirmDialog, spinner, Session, jalaliInput,
} from '../core.js?v=11';
import { toJalaliStr } from '../jalali.js?v=11';

const STATUS_FA = { open: 'باز', mitigating: 'در حال کنترل', closed: 'بسته', realized: 'محقق‌شده' };

export async function renderRisks(main) {
  main.replaceChildren(spinner());
  let equipment = [];
  try { equipment = (await api('/equipment?level=equipment&page_size=200')).items; } catch { }

  async function load() {
    try {
      const data = await api('/risks');
      const rows = data.items.map((r) => h('tr', {},
        h('td', {}, h('span', { class: `badge ${r.kind === 'risk' ? 'danger' : 'success'}` }, r.kind === 'risk' ? 'ریسک' : 'فرصت')),
        h('td', {}, h('strong', {}, r.title)),
        h('td', { class: 'small' }, r.equipment_name || 'فرآیند'),
        h('td', {}, scoreBadge(r.risk_score)),
        h('td', { class: 'small' }, `${faNum(r.probability)} × ${faNum(r.impact)}`),
        h('td', { class: 'small' }, r.owner_name || '—'),
        h('td', { class: 'ltr small' }, toJalaliStr(r.due_date)),
        h('td', {}, h('span', { class: `badge ${r.status === 'closed' ? 'neutral' : 'warning'}` }, STATUS_FA[r.status] || r.status)),
        h('td', {}, Session.can('risks.manage') ? h('span', {},
          h('button', { class: 'btn btn-ghost btn-sm', onclick: () => riskModal(r) }, 'ویرایش'),
          r.status !== 'closed' ? h('button', { class: 'btn btn-ghost btn-sm', style: 'color:var(--c-danger)', onclick: async () => {
            if (!await confirmDialog('این مورد بسته شود؟')) return;
            try { await api(`/risks/${r.id}`, { method: 'DELETE' }); toast('بسته شد', 'success'); load(); }
            catch (e) { toast(errText(e), 'danger'); }
          } }, 'بستن') : null) : null)));
      main.replaceChildren(
        h('div', { class: 'page-head' },
          h('h1', {}, 'ریسک و فرصت (§28)'),
          h('div', { class: 'spacer' }),
          Session.can('risks.manage') ? h('button', { class: 'btn btn-primary', onclick: () => riskModal(null) }, '+ مورد جدید') : null),
        h('div', { class: 'table-wrap card' }, h('table', { class: 'table' },
          h('thead', {}, h('tr', {}, ['نوع', 'عنوان', 'دامنه', 'امتیاز', 'احتمال×اثر', 'مالک', 'سررسید', 'وضعیت', ''].map((x) => h('th', {}, x)))),
          h('tbody', {}, rows.length ? rows : h('tr', {}, h('td', { colspan: '9', class: 'small faint', style: 'text-align:center;padding:18px' }, 'موردی ثبت نشده'))))));
    } catch (e) { main.replaceChildren(h('div', { class: 'small', style: 'color:var(--c-danger)' }, errText(e))); }
  }

  function scoreBadge(s) {
    const tone = s >= 15 ? 'danger' : s >= 8 ? 'warning' : 'neutral';
    return h('span', { class: `badge ${tone}` }, faNum(s));
  }

  function riskModal(r) {
    const isNew = !r;
    const title = h('input', { class: 'input', value: r?.title || '' });
    const kind = h('select', { class: 'select' },
      h('option', { value: 'risk', selected: r?.kind !== 'opportunity' }, 'ریسک'),
      h('option', { value: 'opportunity', selected: r?.kind === 'opportunity' }, 'فرصت'));
    const scope = h('select', { class: 'select' },
      h('option', { value: 'equipment', selected: r?.scope_type !== 'process' }, 'تجهیز'),
      h('option', { value: 'process', selected: r?.scope_type === 'process' }, 'فرآیند'));
    const eqSel = h('select', { class: 'select' },
      h('option', { value: '' }, 'بدون تجهیز'),
      ...equipment.map((e) => h('option', { value: String(e.id), selected: r?.equipment_id === e.id }, `${e.code} — ${e.name}`)));
    const prob = h('select', { class: 'select' }, ...[1, 2, 3, 4, 5].map((n) =>
      h('option', { value: String(n), selected: r?.probability === n }, faNum(n))));
    const impact = h('select', { class: 'select' }, ...[1, 2, 3, 4, 5].map((n) =>
      h('option', { value: String(n), selected: r?.impact === n }, faNum(n))));
    const mit = h('textarea', { class: 'textarea' }, r?.mitigation || '');
    const status = h('select', { class: 'select' },
      ...Object.entries(STATUS_FA).map(([k, v]) => h('option', { value: k, selected: r?.status === k }, v)));
    const due = jalaliInput({ value: r?.due_date ? toJalaliStr(r.due_date) : '' });
    const saveBtn = h('button', { class: 'btn btn-primary' }, 'ذخیره');
    const m = openModal({
      title: isNew ? 'ثبت ریسک/فرصت جدید' : 'ویرایش',
      size: 'modal-lg',
      body: h('div', { class: 'form-grid' },
        h('div', { class: 'field span-2' }, h('label', {}, 'عنوان *'), title),
        h('div', { class: 'field' }, h('label', {}, 'نوع'), kind),
        h('div', { class: 'field' }, h('label', {}, 'دامنه'), scope),
        h('div', { class: 'field' }, h('label', {}, 'تجهیز'), eqSel),
        h('div', { class: 'field' }, h('label', {}, 'احتمال (۱-۵)'), prob),
        h('div', { class: 'field' }, h('label', {}, 'اثر (۱-۵)'), impact),
        h('div', { class: 'field' }, h('label', {}, 'سررسید (شمسی)'), due),
        h('div', { class: 'field' }, h('label', {}, 'وضعیت'), status),
        h('div', { class: 'field span-2' }, h('label', {}, 'اقدام کنترلی / بهره‌برداری از فرصت'), mit)),
      footer: [saveBtn],
    });
    saveBtn.onclick = async () => {
      const body = {
        title: title.value.trim(), kind: kind.value, scope_type: scope.value,
        equipment_id: eqSel.value ? +eqSel.value : null,
        probability: +prob.value, impact: +impact.value,
        mitigation: mit.value || null, status: status.value,
        due_date_jalali: due.querySelector('input').value.trim() || null,
      };
      try {
        if (isNew) await api('/risks', { method: 'POST', body });
        else await api(`/risks/${r.id}`, { method: 'PUT', body });
        toast('ذخیره شد', 'success'); m.close(); load();
      } catch (e) { toast(errText(e), 'danger'); }
    };
  }

  await load();
}
