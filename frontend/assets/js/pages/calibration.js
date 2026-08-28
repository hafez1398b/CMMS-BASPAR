/** Calibration (§29). */
import {
  api, errText, h, faNum, toast, openModal, spinner, Session, jalaliInput,
} from '../core.js?v=11';
import { toJalaliStr } from '../jalali.js?v=11';

const RESULT_FA = { pass: 'قبول', fail: 'مردود', adjusted: 'نیازمند تنظیم' };

export async function renderCalibration(main) {
  main.replaceChildren(spinner());
  let equipment = [];
  try { equipment = (await api('/equipment?level=equipment&page_size=200')).items; } catch { }

  async function load() {
    try {
      const data = await api('/calibration');
      const rows = data.items.map((c) => h('tr', {},
        h('td', {}, h('strong', {}, c.equipment_name || `#${c.equipment_id}`)),
        h('td', { class: 'small' }, c.standard || '—'),
        h('td', { class: 'ltr small' }, toJalaliStr(c.last_calibration)),
        h('td', { class: 'small' }, `${faNum(c.interval_days)} روز`),
        h('td', { class: 'ltr small' }, toJalaliStr(c.next_due)),
        h('td', {}, c.overdue ? h('span', { class: 'badge danger' }, 'عقب‌افتاده')
          : c.next_due ? h('span', { class: 'badge success' }, 'در برنامه')
          : h('span', { class: 'badge neutral' }, 'بدون مبنا')),
        h('td', { class: 'small' }, RESULT_FA[c.result] || '—'),
        h('td', {}, Session.can('calibration.manage')
          ? h('button', { class: 'btn btn-ghost btn-sm', onclick: () => calModal(c) }, 'ویرایش') : null)));
      main.replaceChildren(
        h('div', { class: 'page-head' },
          h('h1', {}, 'کالیبراسیون تجهیزات اندازه‌گیری (§29)'),
          h('div', { class: 'spacer' }),
          Session.can('calibration.manage') ? h('button', { class: 'btn btn-primary', onclick: () => calModal(null) }, '+ برنامه کالیبراسیون') : null),
        h('div', { class: 'table-wrap card' }, h('table', { class: 'table' },
          h('thead', {}, h('tr', {}, ['تجهیز', 'استاندارد', 'آخرین کالیبره', 'دوره', 'سررسید بعد', 'وضعیت', 'نتیجه', ''].map((x) => h('th', {}, x)))),
          h('tbody', {}, rows.length ? rows : h('tr', {}, h('td', { colspan: '8', class: 'small faint', style: 'text-align:center;padding:18px' }, 'برنامه‌ای ثبت نشده'))))));
    } catch (e) { main.replaceChildren(h('div', { class: 'small', style: 'color:var(--c-danger)' }, errText(e))); }
  }

  function calModal(c) {
    const isNew = !c;
    const eqSel = h('select', { class: 'select' },
      ...equipment.map((e) => h('option', { value: String(e.id), selected: c?.equipment_id === e.id }, `${e.code} — ${e.name}`)));
    const std = h('input', { class: 'input', value: c?.standard || '', placeholder: 'مثلاً ISO 17025' });
    const interval = h('input', { class: 'input ltr', type: 'number', value: c?.interval_days ?? 365 });
    const last = jalaliInput({ value: c?.last_calibration ? toJalaliStr(c.last_calibration) : '' });
    const result = h('select', { class: 'select' },
      h('option', { value: '' }, '—'),
      ...Object.entries(RESULT_FA).map(([k, v]) => h('option', { value: k, selected: c?.result === k }, v)));
    const notes = h('textarea', { class: 'textarea' }, c?.notes || '');
    const saveBtn = h('button', { class: 'btn btn-primary' }, 'ذخیره');
    const m = openModal({
      title: isNew ? 'برنامه کالیبراسیون جدید' : 'ویرایش کالیبراسیون',
      body: h('div', { class: 'form-grid' },
        h('div', { class: 'field span-2' }, h('label', {}, 'تجهیز *'), eqSel),
        h('div', { class: 'field' }, h('label', {}, 'استاندارد'), std),
        h('div', { class: 'field' }, h('label', {}, 'دوره (روز)'), interval),
        h('div', { class: 'field' }, h('label', {}, 'آخرین کالیبره (شمسی)'), last),
        h('div', { class: 'field' }, h('label', {}, 'نتیجه'), result),
        h('div', { class: 'field span-2' }, h('label', {}, 'یادداشت'), notes)),
      footer: [saveBtn],
    });
    saveBtn.onclick = async () => {
      const body = {
        equipment_id: +eqSel.value, standard: std.value || null,
        interval_days: +interval.value || 365,
        last_calibration_jalali: last.querySelector('input').value.trim() || null,
        result: result.value || null, notes: notes.value || null, status: 'active',
      };
      try {
        if (isNew) await api('/calibration', { method: 'POST', body });
        else await api(`/calibration/${c.id}`, { method: 'PUT', body });
        toast('ذخیره شد', 'success'); m.close(); load();
      } catch (e) { toast(errText(e), 'danger'); }
    };
  }

  await load();
}
