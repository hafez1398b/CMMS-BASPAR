/** گزارش‌ساز پیشرفته (§26/§27) — فیلترهای زیاد: کارخانه/دسته(همه کارخانه‌ها)/
 *  نوع قطعه(پمپ/تابلو برق/دینام…)/قسمت/سالن/تجهیز/اهمیت/وضعیت/بازه تاریخ.
 *  دو گزارش: تجهیزات و دستور کارها + خروجی CSV/Excel. */
import { api, errText, h, faNum, toast, spinner, jalaliInput, downloadUrl, critBadge, statusBadge } from '../core.js?v=11';
import { toJalaliStr } from '../jalali.js?v=11';

const CRIT_FA = { low: 'کم', medium: 'متوسط', high: 'زیاد', critical: 'بحرانی' };

export async function renderReports(main) {
  main.replaceChildren(spinner());
  let factories = [], categories = [], compTypes = [], equipments = [];
  try {
    [factories, categories, compTypes, equipments] = await Promise.all([
      api('/factories').then((d) => d.items),
      api('/categories').then((d) => d.items),
      api('/lookups?list_code=component_type').then((d) => d.items.filter((x) => x.is_active)),
      api('/equipment?level=equipment&page_size=500').then((d) => d.items),
    ]);
  } catch (e) { toast(errText(e), 'danger'); }

  const S = { type: 'equipment' };
  const out = h('div', { class: 'mt-4' });

  const sel = (opts, ph) => h('select', { class: 'select', style: 'max-width:170px' },
    h('option', { value: '' }, ph), ...opts.map(([v, l]) => h('option', { value: v }, l)));

  const fSel = sel(factories.map((f) => [String(f.id), f.name]), 'همه کارخانه‌ها');
  const cSel = sel(categories.map((c) => [String(c.id), c.name]), 'همه دسته‌ها');
  const tSel = sel(compTypes.map((t) => [t.code, t.title_fa]), 'همه انواع قطعه');
  const dSel = sel([...new Set(equipments.map((e) => e.dept).filter(Boolean))].map((d) => [d, d]), 'همه قسمت‌ها');
  const hSel = sel([...new Set(equipments.map((e) => e.hall).filter(Boolean))].map((x) => [x, x]), 'همه سالن‌ها');
  const eSel = sel(equipments.map((e) => [String(e.id), `${e.code} ${e.name}`]), 'همه تجهیزات');
  const crSel = sel(Object.entries(CRIT_FA), 'همه اهمیت‌ها');
  const stSel = sel([['active', 'فعال'], ['inactive', 'غیرفعال'], ['under_maintenance', 'در تعمیر'], ['scrapped', 'اسقاط']], 'همه وضعیت‌ها');
  const from = jalaliInput({ placeholder: 'از تاریخ' });
  const to = jalaliInput({ placeholder: 'تا تاریخ' });

  const typeBtn = (t, label) => h('button', {
    class: `btn btn-sm ${S.type === t ? 'btn-primary' : 'btn-secondary'}`,
    onclick: () => { S.type = t; run(); },
  }, label);

  const csvBtn = h('button', { class: 'btn btn-secondary', onclick: () => doCsv() }, '⬇ خروجی CSV/Excel');
  const runBtn = h('button', { class: 'btn btn-primary', onclick: run }, 'تهیه گزارش');

  main.replaceChildren(
    h('div', { class: 'page-head' }, h('h1', {}, 'گزارش‌ساز')),
    h('div', { class: 'card' }, h('div', { class: 'card-body' },
      h('div', { class: 'toolbar' }, typeBtn('equipment', 'گزارش تجهیزات'), typeBtn('wo', 'گزارش دستور کارها'),
        typeBtn('history', 'گزارش سوابق نت'),
        h('div', { class: 'spacer' }), csvBtn)),
      h('div', { class: 'toolbar', style: 'flex-wrap:wrap' },
        fSel, cSel, tSel, dSel, hSel, eSel, crSel, stSel,
        h('div', { class: 'field' }, h('label', { class: 'small' }, 'از'), from),
        h('div', { class: 'field' }, h('label', { class: 'small' }, 'تا'), to),
        runBtn)),
    out);

  function qs() {
    const q = new URLSearchParams();
    if (fSel.value) q.set('factory_id', fSel.value);
    if (cSel.value) q.set('category_id', cSel.value);
    if (tSel.value) q.set('component_type', tSel.value);
    if (dSel.value) q.set('dept', dSel.value);
    if (hSel.value) q.set('hall', hSel.value);
    if (eSel.value) q.set('equipment_id', eSel.value);
    if (crSel.value) q.set('criticality', crSel.value);
    if (stSel.value) q.set('status', stSel.value);
    if (from.querySelector('input').value) q.set('from_jalali', from.querySelector('input').value);
    if (to.querySelector('input').value) q.set('to_jalali', to.querySelector('input').value);
    return q;
  }

  async function run() {
    out.replaceChildren(spinner());
    try {
      if (S.type === 'equipment') {
        const d = await api(`/reports/equipment?${qs()}`);
        out.replaceChildren(summary(d.total), tableWrap(
          ['کد', 'نام', 'کارخانه', 'دسته', 'نوع قطعه', 'قسمت', 'سالن', 'اهمیت', 'وضعیت'],
          d.rows.map((r) => [
            h('td', { class: 'ltr' }, r.code), h('td', {}, r.name),
            h('td', { class: 'small' }, r.factory), h('td', { class: 'small' }, r.category),
            h('td', { class: 'small' }, r.component_type || '—'), h('td', { class: 'small' }, r.dept || '—'),
            h('td', { class: 'small' }, r.hall || '—'),
            h('td', {}, critBadge(r.criticality, CRIT_FA[r.criticality])), h('td', {}, statusBadge(r.status)),
          ])));
      } else if (S.type === 'history') {
        const d = await api(`/reports/maintenance-history?${qs()}`);
        out.replaceChildren(summary(d.total), barChart(d.by_type), tableWrap(
          ['کد تجهیز', 'تجهیز', 'کارخانه', 'دسته', 'عنوان', 'نوع', 'تکنسین', 'تاریخ'],
          d.rows.map((r) => [
            h('td', { class: 'ltr' }, r.equipment_code || '—'), h('td', {}, r.equipment_name || '—'),
            h('td', { class: 'small' }, r.factory_name || '—'), h('td', { class: 'small' }, r.category_name || '—'),
            h('td', {}, r.title), h('td', { class: 'small' }, r.work_type),
            h('td', { class: 'small' }, r.technician_name || '—'),
            h('td', { class: 'ltr small' }, toJalaliStr(r.finished_at)),
          ])));
      } else {
        const d = await api(`/reports/work-orders?${qs()}`);
        out.replaceChildren(summary(d.total), barChart(d.by_status), tableWrap(
          ['کد', 'عنوان', 'وضعیت', 'کلاس', 'تجهیز', 'هزینه'],
          d.rows.map((r) => [
            h('td', { class: 'ltr' }, r.code), h('td', {}, r.title),
            h('td', { class: 'small' }, r.status), h('td', { class: 'small' }, r.work_class || '—'),
            h('td', { class: 'small' }, r.equipment || '—'),
            h('td', { class: 'ltr small' }, Number(r.cost || 0).toLocaleString('fa-IR')),
          ])));
      }
    } catch (e) { out.replaceChildren(h('div', { class: 'small', style: 'color:var(--c-danger)' }, errText(e))); }
  }

  function doCsv() {
    const q = qs();
    const url = S.type === 'equipment' ? `/reports/equipment/export.csv?${q}`
      : S.type === 'history' ? `/reports/maintenance-history/export.csv?${q}`
      : `/reports/work-orders/export.csv?${q}`;
    downloadUrl(url).catch((e) => toast(errText(e), 'danger'));
  }

  const summary = (n) => h('div', { class: 'kpi primary', style: 'max-width:240px' },
    h('div', { class: 'kpi-label' }, 'تعداد نتایج'), h('div', { class: 'kpi-value' }, faNum(n)));

  function barChart(by) {
    const entries = Object.entries(by || {}).filter(([, v]) => v > 0);
    const max = Math.max(1, ...entries.map(([, v]) => v));
    return h('div', { class: 'card mt-4' }, h('div', { class: 'card-body' },
      entries.map(([k, v]) => h('div', { style: 'margin-bottom:8px' },
        h('div', { style: 'display:flex;justify-content:space-between;font-size:12px' }, h('span', {}, k), h('span', { class: 'muted' }, faNum(v))),
        h('div', { style: 'background:var(--c-neutral-soft);border-radius:6px' },
          h('div', { style: `width:${Math.max(4, v / max * 100)}%;height:10px;border-radius:6px;background:#1d4ed8` }))))));
  }

  function tableWrap(headers, rows) {
    return h('div', { class: 'table-wrap card mt-4' }, h('table', { class: 'table' },
      h('thead', {}, h('tr', {}, headers.map((x) => h('th', {}, x)))),
      h('tbody', {}, rows.length ? rows.map((r) => h('tr', {}, r)) :
        h('tr', {}, h('td', { colspan: String(headers.length) },
          h('div', { class: 'small faint', style: 'text-align:center;padding:16px' }, 'نتیجه‌ای نیست'))))));
  }

  run();
}
