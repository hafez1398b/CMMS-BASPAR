/** پرونده دیجیتال تجهیز — ۱۲ تب (§8, §12). Clean rewrite. */
import {
  Session, api, errText, h, navigate, toast, spinner, faNum, fmtBytes,
  critBadge, statusBadge, LEVEL_FA, openModal, confirmDialog, jalaliInput, downloadUrl,
  faToEnDigits,
} from '../core.js?v=11';
import { toJalaliStr } from '../jalali.js?v=11';
import { icon } from '../icons.js?v=11';

const CRIT_FA = { low: 'کم', medium: 'متوسط', high: 'زیاد', critical: 'بحرانی' };
const TABS = [
  ['ident', 'شناسنامه'], ['tech', 'اطلاعات فنی'], ['structure', 'ساختار'],
  ['plans', 'برنامه نت'], ['checklists', 'چک‌لیست‌ها'], ['history', 'سوابق نت'],
  ['parts', 'قطعات'], ['costs', 'هزینه‌ها'], ['docs', 'اسناد'],
  ['calib', 'کالیبراسیون'], ['kpi', 'KPI'], ['risks', 'ریسک و فرصت'],
];

export async function renderEquipmentDetail(main, id) {
  main.replaceChildren(spinner());
  let eq;
  try { eq = await api(`/equipment/${id}`); }
  catch (e) { main.replaceChildren(h('div', { class: 'card' }, h('div', { class: 'card-body' }, '⚠️ ', errText(e)))); return; }

  let actTypes = [], intervals = [];
  try {
    const l = await api('/lookups');
    actTypes = l.items.filter((x) => x.list_code === 'activity_type' && x.is_active);
    intervals = l.items.filter((x) => x.list_code === 'interval' && x.is_active);
  } catch { }
  const actFa = (c) => actTypes.find((x) => x.code === c)?.title_fa || c;
  const intFa = (c) => intervals.find((x) => x.code === c)?.title_fa || c;

  let activeTab = 'ident';
  const tabbar = h('div', { class: 'tabs' });
  const panel = h('div', { class: 'tab-panel' });

  const header = h('div', { class: 'page-head' },
    h('div', { class: 'breadcrumb' }, h('a', { href: '#/equipment' }, 'تجهیزات'), '‹', h('span', {}, LEVEL_FA[eq.level] || eq.level)),
    h('div', { class: 'spacer' }),
    h('h1', {}, eq.name), h('span', { class: 'ltr mono muted small' }, eq.code),
    critBadge(eq.criticality, CRIT_FA[eq.criticality]), statusBadge(eq.status),
    h('div', { class: 'spacer' }),
    h('button', { class: 'btn btn-secondary btn-sm', onclick: () => navigate(`#/equipment/${eq.id}/passport`) },
      h('span', { html: icon('printer'), style: 'display:inline-flex;width:14px;height:14px' }), 'پاسپورت'),
    Session.can('equipment.create') && eq.level !== 'subcomponent'
      ? h('button', { class: 'btn btn-secondary btn-sm', onclick: addChild }, '+ فرزند') : null,
    Session.can('equipment.delete')
      ? h('button', { class: 'btn btn-ghost btn-sm', style: 'color:var(--c-danger)', onclick: archive }, '🗄 آرشیو') : null);

  main.replaceChildren(header, h('div', { class: 'card', style: 'padding:0 16px' }, tabbar), panel);
  draw();

  function draw() {
    tabbar.replaceChildren(...TABS.map(([k, label]) => h('button', {
      class: `tab ${k === activeTab ? 'active' : ''}`, onclick: () => { activeTab = k; draw(); },
    }, label)));
    panel.replaceChildren(spinner());
    if (activeTab === 'ident') panel.replaceChildren(tabIdent());
    else if (activeTab === 'tech') panel.replaceChildren(tabTech());
    else if (activeTab === 'structure') panel.replaceChildren(tabStructure());
    else if (activeTab === 'plans') (async () => {
      try {
        const [d, cons] = await Promise.all([
          api('/equipment/' + id + '/plans'),
          api('/equipment/' + id + '/pm-consumables').catch(() => ({ items: [] })),
        ]);
        panel.replaceChildren(renderPlans(d, cons.items));
      } catch (e) { panel.replaceChildren(h('div', { class: 'small', style: 'color:var(--c-danger)' }, errText(e))); }
    })();
    else if (activeTab === 'checklists') load('/equipment/' + id + '/checklists', renderChecklists);
    else if (activeTab === 'history') load('/equipment/' + id + '/history', renderHistory);
    else if (activeTab === 'parts') load('/equipment/' + id + '/parts', renderParts);
    else if (activeTab === 'costs') load('/equipment/' + id + '/costs', renderCosts);
    else if (activeTab === 'docs') panel.replaceChildren(tabDocs());
    else if (activeTab === 'calib') load('/calibration?equipment_id=' + id, renderCalib);
    else if (activeTab === 'kpi') load('/equipment/' + id + '/kpi', renderKpi);
    else if (activeTab === 'risks') load('/risks?equipment_id=' + id, renderRisks);
  }

  async function load(path, fn) {
    try { const d = await api(path); panel.replaceChildren(fn(d)); }
    catch (e) { panel.replaceChildren(h('div', { class: 'small', style: 'color:var(--c-danger)' }, errText(e))); }
  }

  function payload() {
    return { code: eq.code, name: eq.name, level: eq.level,
      factory_id: eq.factory ? eq.factory.id : null, category_id: eq.category ? eq.category.id : null,
      parent_id: eq.parent_id, location: eq.location, manufacturer: eq.manufacturer, model: eq.model,
      serial_number: eq.serial_number, year: eq.year, criticality: eq.criticality, status: eq.status,
      technical_specs: eq.technical_specs, hall: eq.hall, dept: eq.dept, line: eq.line,
      position: eq.position, component_type: eq.component_type, version: eq.version };
  }

  /** نرمال‌سازی/اعتبارسنجی قبل از ذخیره — با پیام فارسی واضح.
   *  مقدار بازگشتی: رشته خطا یا null اگر همه‌چیز درست باشد. */
  function validateBeforeSave() {
    if (!eq.code || !String(eq.code).trim()) return 'کد تجهیز نمی‌تواند خالی باشد';
    if (!eq.name || String(eq.name).trim().length < 2) return 'نام تجهیز حداقل ۲ نویسه لازم دارد';
    if (String(eq.name).trim().length > 190) return 'نام تجهیز حداکثر ۱۹۰ نویسه مجاز است';
    const raw = eq.year;
    if (raw !== null && raw !== undefined && raw !== '') {
      const n = Number(faToEnDigits(String(raw).trim()));
      if (!Number.isFinite(n)) return 'سال ساخت باید عدد باشد (ارقام انگلیسی یا فارسی)';
      if (n >= 1200 && n < 1500) return `سال «${faNum(n)}» شمسی به نظر می‌رسد؛ سال ساخت باید میلادی باشد (مثلاً ۲۰۱۹)`;
      if (n < 1800 || n > 2200) return 'سال ساخت باید میلادی و بین ۱۸۰۰ تا ۲۲۰۰ باشد (مثلاً ۲۰۱۹)';
      eq.year = Math.trunc(n);
    } else eq.year = null;
    return null;
  }

  function tabIdent() {
    const f = (k, label, ltr) => h('div', { class: 'field' }, h('label', {}, label),
      h('input', { class: 'input', dir: ltr ? 'ltr' : 'rtl', value: eq[k] || '', oninput: (e) => eq[k] = e.target.value || null }));
    const yearField = h('div', { class: 'field' }, h('label', {}, 'سال ساخت'),
      h('input', { class: 'input', dir: 'ltr', placeholder: 'میلادی — مثال: 2019', value: eq.year ?? '',
        oninput: (e) => eq.year = e.target.value || null }));
    const save = Session.can('equipment.edit') ? h('button', { class: 'btn btn-primary mt-4', onclick: saveIdent }, 'ذخیره تغییرات') : null;
    return h('div', { class: 'card' }, h('div', { class: 'card-body' },
      h('div', { class: 'form-grid' },
        f('code', 'کد تجهیز', true), f('name', 'نام تجهیز'),
        f('manufacturer', 'سازنده'), f('model', 'مدل'),
        f('serial_number', 'شماره سریال', true), yearField,
        f('hall', 'سالن'), f('dept', 'بخش'), f('line', 'خط'), f('position', 'موقعیت'),
        f('component_type', 'نوع قطعه')),
      h('div', { class: 'small faint mt-4' }, `نسخه رکورد: ${faNum(eq.version)}`), save));
  }
  async function saveIdent() {
    const vErr = validateBeforeSave();
    if (vErr) { toast(vErr, 'danger', 6000); return; }
    try { eq = await api(`/equipment/${eq.id}`, { method: 'PUT', body: payload() }); toast('ذخیره شد', 'success'); draw(); }
    catch (e) { toast(e.status === 409 ? 'تعارض نسخه — تازه‌سازی شد' : errText(e), 'danger', 6000); renderEquipmentDetail(main, id); }
  }

  function tabTech() {
    const specs = { ...(eq.technical_specs || {}) };
    const box = h('div', {});
    function drawS() {
      const rows = Object.entries(specs).map(([k, v]) => h('div', { class: 'kv-row' },
        h('input', { class: 'input', value: k, readonly: true, style: 'max-width:220px' }),
        h('input', { class: 'input', value: v, oninput: (e) => specs[k] = e.target.value }),
        Session.can('equipment.edit') ? h('button', { class: 'btn btn-ghost btn-sm', onclick: () => { delete specs[k]; drawS(); } }, '✕') : null));
      const kI = h('input', { class: 'input', placeholder: 'کلید', style: 'max-width:220px' });
      const vI = h('input', { class: 'input', placeholder: 'مقدار' });
      box.replaceChildren(rows.length ? h('div', { class: 'mb-4' }, rows) : h('div', { class: 'small faint mb-4' }, 'مشخصه‌ای ثبت نشده.'),
        Session.can('equipment.edit') ? h('div', { class: 'kv-row' }, kI, vI,
          h('button', { class: 'btn btn-secondary btn-sm', onclick: () => { if (kI.value.trim()) { specs[kI.value.trim()] = vI.value; drawS(); } } }, '+ افزودن')) : null);
    }
    drawS();
    const save = Session.can('equipment.edit') ? h('button', { class: 'btn btn-primary mt-4', onclick: async () => {
      const vErr = validateBeforeSave();
      if (vErr) { toast(vErr, 'danger', 6000); return; }
      try { eq.technical_specs = specs; eq = await api(`/equipment/${eq.id}`, { method: 'PUT', body: payload() }); toast('ذخیره شد', 'success'); }
      catch (e) { toast(errText(e), 'danger', 6000); }
    } }, 'ذخیره مشخصات') : null;
    return h('div', { class: 'card' }, h('div', { class: 'card-body' }, box, save));
  }

  function tabStructure() {
    if (!eq.children.length) return h('div', { class: 'card' }, h('div', { class: 'card-body' }, empty('▣', 'زیرسیستم/جزئی ثبت نشده', 'از «+ فرزند» استفاده کنید.')));
    const rows = eq.children.map((c) => h('tr', { class: 'clickable', onclick: () => navigate(`#/equipment/${c.id}`) },
      h('td', { class: 'ltr' }, c.code), h('td', {}, c.name),
      h('td', {}, h('span', { class: 'badge neutral' }, LEVEL_FA[c.level])),
      h('td', {}, critBadge(c.criticality, CRIT_FA[c.criticality])), h('td', {}, statusBadge(c.status))));
    return h('div', { class: 'table-wrap card' }, h('table', { class: 'table' },
      h('thead', {}, h('tr', {}, ['کد', 'نام', 'سطح', 'اهمیت', 'وضعیت'].map((x) => h('th', {}, x)))), h('tbody', {}, rows)));
  }

  function renderPlans(d, consumables = []) {
    const rows = d.items.map((p) => h('tr', {},
      h('td', {}, h('strong', {}, p.work_title)), h('td', { class: 'small' }, actFa(p.activity_type)),
      h('td', { class: 'small' }, intFa(p.interval_code)), h('td', { class: 'small' }, p.performer || '—'),
      h('td', { class: 'ltr small' }, toJalaliStr(p.last_execution)), h('td', { class: 'ltr small' }, toJalaliStr(p.next_due)),
      h('td', {}, p.overdue ? h('span', { class: 'badge danger' }, 'عقب‌افتاده') : h('span', { class: 'badge success' }, 'برنامه‌ریزی'))));
    const consSection = consumables.length ? h('div', { class: 'card mt-4' },
      h('div', { class: 'card-head' }, h('h2', {}, 'قطعات مصرفی برنامه نت')),
      h('div', { class: 'table-wrap' }, h('table', { class: 'table' },
        h('thead', {}, h('tr', {}, ['برنامه', 'قطعه مصرفی', 'مقدار', 'دوره'].map((x) => h('th', {}, x)))),
        h('tbody', {}, consumables.map((c) => h('tr', {},
          h('td', { class: 'small' }, c.plan_title),
          h('td', {}, c.part_name),
          h('td', { class: 'small' }, `${faNum(c.quantity)} ${c.unit || ''}`),
          h('td', { class: 'small' }, intFa(c.interval_code)))))))) : null;
    return h('div', {},
      Session.can('plans.create') ? h('div', { class: 'toolbar' }, h('div', { class: 'spacer' }),
        h('button', { class: 'btn btn-primary', onclick: () => planModal(null) }, '+ فعالیت جدید')) : null,
      d.items.length ? h('div', { class: 'table-wrap card' }, h('table', { class: 'table' },
        h('thead', {}, h('tr', {}, ['عنوان', 'نوع', 'تناوب', 'مجری', 'آخرین اجرا', 'سررسید', 'وضعیت'].map((x) => h('th', {}, x)))),
        h('tbody', {}, rows))) : h('div', { class: 'card' }, h('div', { class: 'card-body' }, empty('🗓', 'برنامه‌ای ثبت نشده', ''))),
      consSection);
  }
  function planModal(p) {
    const title = h('input', { class: 'input', value: p ? p.work_title : '' });
    const ty = h('select', { class: 'select' }, ...actTypes.map((t) => h('option', { value: t.code }, t.title_fa)));
    const iv = h('select', { class: 'select' }, ...intervals.map((t) => h('option', { value: t.code }, t.title_fa)));
    const save = h('button', { class: 'btn btn-primary', onclick: async () => {
      const body = { equipment_id: eq.id, work_title: title.value.trim(), activity_type: ty.value, interval_code: iv.value, work_class: 'pm' };
      try { if (p) await api(`/plans/${p.id}`, { method: 'PUT', body: { ...body, version: p.version } }); else await api('/plans', { method: 'POST', body }); m.close(); draw(); }
      catch (e) { toast(errText(e), 'danger'); }
    } }, 'ذخیره');
    const m = openModal({ title: p ? 'ویرایش برنامه' : 'فعالیت جدید', body: h('div', { class: 'form-grid' },
      h('div', { class: 'field span-2' }, h('label', {}, 'عنوان *'), title),
      h('div', { class: 'field' }, h('label', {}, 'نوع'), ty), h('div', { class: 'field' }, h('label', {}, 'تناوب'), iv)), footer: [save] });
  }

  function renderChecklists(d) {
    const genBtn = Session.can('checklist.manage') ? h('div', { class: 'toolbar' },
      h('div', { class: 'spacer' }),
      h('button', { class: 'btn btn-secondary', onclick: async (ev) => {
        ev.currentTarget.disabled = true;
        try {
          const t = await api(`/checklists/from-plans/${eq.id}`, { method: 'POST' });
          toast(`چک‌لیست «${t.name}» با ${faNum(t.items.length)} آیتم از برنامه نت ساخته شد`, 'success');
          draw();
        } catch (e) { toast(errText(e), 'danger'); ev.currentTarget.disabled = false; }
      } }, '🤖 ساخت چک‌لیست چکاپ از برنامه نت')) : null;
    if (!d.items.length) return h('div', {}, genBtn,
      h('div', { class: 'card' }, h('div', { class: 'card-body' }, empty('☑', 'بازرسی ثبت نشده', ''))));
    const rows = d.items.map((r) => h('tr', { class: 'clickable', onclick: () => navigate(`#/checklists/${r.id}`) },
      h('td', {}, r.template_name || '—'),
      h('td', {}, r.result_summary === 'fail' ? h('span', { class: 'badge danger' }, 'نامطلوب') : h('span', { class: 'badge success' }, 'سالم')),
      h('td', { class: 'small' }, r.technician_name || '—'), h('td', { class: 'ltr small' }, toJalaliStr(r.run_date))));
    return h('div', {}, genBtn, h('div', { class: 'table-wrap card' }, h('table', { class: 'table' },
      h('thead', {}, h('tr', {}, ['قالب', 'نتیجه', 'تکنسین', 'تاریخ'].map((x) => h('th', {}, x)))), h('tbody', {}, rows))));
  }

  function renderHistory(d) {
    if (!d.items.length) return h('div', { class: 'card' }, h('div', { class: 'card-body' }, empty('🧾', 'سابقه‌ای ثبت نشده', 'با بستن دستور کار، سوابق اینجا ثبت می‌شوند.')));
    const rows = d.items.map((it) => h('tr', { class: it.work_order_id ? 'clickable' : '', onclick: () => it.work_order_id && navigate(`#/work-orders/${it.work_order_id}`) },
      h('td', {}, h('strong', {}, it.title)), h('td', { class: 'small' }, it.work_type),
      h('td', { class: 'small' }, it.technician_name || '—'), h('td', { class: 'ltr small' }, toJalaliStr(it.finished_at)),
      h('td', { class: 'small' }, it.duration_minutes ? `${faNum(it.duration_minutes)} دقیقه` : '—')));
    return h('div', { class: 'table-wrap card' }, h('table', { class: 'table' },
      h('thead', {}, h('tr', {}, ['عنوان', 'نوع', 'تکنسین', 'خاتمه', 'مدت'].map((x) => h('th', {}, x)))), h('tbody', {}, rows)));
  }

  function renderParts(d) {
    if (!d.items.length) return h('div', { class: 'card' }, h('div', { class: 'card-body' }, empty('🔩', 'قطعه‌ای مرتبط نیست', '')));
    const rows = d.items.map((p) => h('tr', {}, h('td', { class: 'ltr' }, p.part_number || p.code), h('td', {}, p.name),
      h('td', { class: 'small' }, faNum(p.current_stock ?? p.quantity)), h('td', { class: 'small' }, faNum(p.min_stock)),
      h('td', {}, critBadge(p.criticality, CRIT_FA[p.criticality] || p.criticality)), h('td', { class: 'small' }, p.supplier || '—')));
    return h('div', { class: 'table-wrap card' }, h('table', { class: 'table' },
      h('thead', {}, h('tr', {}, ['Part Number', 'نام', 'موجودی', 'حد سفارش', 'اهمیت', 'تأمین‌کننده'].map((x) => h('th', {}, x)))), h('tbody', {}, rows)));
  }

  function renderCosts(d) {
    const total = d.total || 0;
    const rows = (d.by_type || []).map((c) => h('tr', {}, h('td', {}, c.cost_type), h('td', { class: 'ltr' }, Number(c.amount).toLocaleString('fa-IR'))));
    return h('div', {},
      h('div', { class: 'kpi info', style: 'max-width:320px' }, h('div', { class: 'kpi-label' }, 'هزینه تجمعی'),
        h('div', { class: 'kpi-value', style: 'font-size:20px' }, Number(total).toLocaleString('fa-IR')), h('div', { class: 'kpi-sub' }, 'ریال')),
      rows.length ? h('div', { class: 'table-wrap card mt-4' }, h('table', { class: 'table' },
        h('thead', {}, h('tr', {}, ['نوع', 'مبلغ'].map((x) => h('th', {}, x)))), h('tbody', {}, rows))) :
      h('div', { class: 'card mt-4' }, h('div', { class: 'card-body' }, empty('💰', 'هزینه‌ای ثبت نشده', ''))));
  }

  function tabDocs() {
    const list = h('div', {});
    function drawF() {
      list.replaceChildren(eq.files.length ? h('div', { class: 'table-wrap card' }, h('table', { class: 'table' },
        h('thead', {}, h('tr', {}, ['نام', 'حجم', 'تاریخ', ''].map((x) => h('th', {}, x)))),
        h('tbody', {}, eq.files.map((f) => h('tr', {}, h('td', {}, f.name), h('td', { class: 'small' }, fmtBytes(f.size)),
          h('td', { class: 'ltr small' }, toJalaliStr(f.created_at)),
          h('td', {}, h('button', { class: 'btn btn-ghost btn-sm', onclick: () => downloadUrl(`/files/${f.id}/download`) }, 'دانلود'))))))) :
        h('div', { class: 'card' }, h('div', { class: 'card-body' }, empty('📎', 'مدرکی پیوست نشده', ''))));
    }
    const fi = h('input', { type: 'file', style: 'display:none' });
    fi.onchange = async () => { const f = fi.files[0]; if (!f) return; const fd = new FormData(); fd.append('file', f);
      try { await api(`/equipment/${eq.id}/files`, { method: 'POST', form: fd }); toast('بارگذاری شد', 'success'); eq = await api(`/equipment/${id}`); drawF(); } catch (e) { toast(errText(e), 'danger'); } };
    drawF();
    const up = Session.can('files.upload')
      ? h('div', {}, h('div', { class: 'upload-zone mt-4', onclick: () => fi.click() }, '📤 بارگذاری فایل'), fi)
      : null;
    return h('div', {}, list, up);
  }

  function renderCalib(d) {
    if (!d.items.length) return h('div', { class: 'card' }, h('div', { class: 'card-body' }, empty('🎚', 'کالیبراسیونی ثبت نشده', '')));
    const rows = d.items.map((c) => h('tr', {}, h('td', {}, c.standard || '—'), h('td', { class: 'ltr small' }, toJalaliStr(c.last_calibration)),
      h('td', { class: 'small' }, `${faNum(c.interval_days)} روز`), h('td', { class: 'ltr small' }, toJalaliStr(c.next_due)),
      h('td', {}, c.overdue ? h('span', { class: 'badge danger' }, 'عقب‌افتاده') : h('span', { class: 'badge success' }, 'در برنامه'))));
    return h('div', { class: 'table-wrap card' }, h('table', { class: 'table' },
      h('thead', {}, h('tr', {}, ['استاندارد', 'آخرین', 'دوره', 'سررسید', 'وضعیت'].map((x) => h('th', {}, x)))), h('tbody', {}, rows)));
  }

  function renderKpi(k) {
    const card = (label, value, sub) => h('div', { class: 'kpi primary' }, h('div', { class: 'kpi-label' }, label),
      h('div', { class: 'kpi-value', style: 'font-size:20px' }, value === null || value === undefined ? '—' : faNum(value)), h('div', { class: 'kpi-sub' }, sub || ''));
    return h('div', { class: 'kpi-grid' },
      card('MTBF (ساعت)', k.mtbf_hours), card('MTTR (دقیقه)', k.mttr_minutes),
      card('تعداد خرابی', k.failure_count), card('دستورکارها', k.work_order_count),
      card('انطباق PM (٪)', k.pm_compliance_pct), card('هزینه نت', Math.round(k.maintenance_cost || 0)));
  }

  function renderRisks(d) {
    if (!d.items.length) return h('div', { class: 'card' }, h('div', { class: 'card-body' }, empty('⚠', 'ریسکی ثبت نشده', '')));
    const rows = d.items.map((r) => h('tr', {},
      h('td', {}, h('span', { class: `badge ${r.kind === 'risk' ? 'danger' : 'success'}` }, r.kind === 'risk' ? 'ریسک' : 'فرصت')),
      h('td', {}, r.title), h('td', {}, h('span', { class: 'badge neutral' }, faNum(r.risk_score))),
      h('td', { class: 'small' }, r.mitigation || '—'), h('td', { class: 'small' }, r.status)));
    return h('div', { class: 'table-wrap card' }, h('table', { class: 'table' },
      h('thead', {}, h('tr', {}, ['نوع', 'عنوان', 'امتیاز', 'اقدام', 'وضعیت'].map((x) => h('th', {}, x)))), h('tbody', {}, rows)));
  }

  function empty(ic, t, s) { return h('div', { class: 'empty-state' }, h('div', { class: 'empty-icon' }, ic), h('h3', {}, t), h('div', { class: 'small muted' }, s)); }

  function addChild() {
    const next = { equipment: 'subsystem', subsystem: 'component', component: 'subcomponent' }[eq.level];
    const code = h('input', { class: 'input ltr', placeholder: 'کد' });
    const name = h('input', { class: 'input', placeholder: 'نام' });
    const save = h('button', { class: 'btn btn-primary', onclick: async () => {
      try { const c = await api('/equipment', { method: 'POST', body: { code: code.value.trim(), name: name.value.trim(), level: next, parent_id: eq.id, factory_id: eq.factory ? eq.factory.id : null, category_id: eq.category ? eq.category.id : null, criticality: eq.criticality, status: 'active' } }); m.close(); navigate(`#/equipment/${c.id}`); }
      catch (e) { toast(errText(e), 'danger'); }
    } }, 'ثبت');
    const m = openModal({ title: `افزودن ${LEVEL_FA[next]}`, body: h('div', { class: 'form-grid' },
      h('div', { class: 'field' }, h('label', {}, 'کد *'), code), h('div', { class: 'field' }, h('label', {}, 'نام *'), name)), footer: [save] });
  }

  async function archive() {
    if (!await confirmDialog(`تجهیز «${eq.name}» آرشیو شود؟ سوابق حفظ می‌مانند (§34).`, { danger: true, title: 'آرشیو تجهیز' })) return;
    try { await api(`/equipment/${eq.id}`, { method: 'DELETE' }); toast('آرشیو شد', 'success'); navigate('#/equipment'); }
    catch (e) { toast(errText(e), 'danger'); }
  }
}
