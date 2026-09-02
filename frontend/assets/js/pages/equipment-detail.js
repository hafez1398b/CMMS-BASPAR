/** BASPAR CMMS — Equipment Detail v2
 * Dark First · 12 Tabs · BFG Logo · Enterprise
 */

import {
  Session, api, errText, h, navigate, toast, spinner, faNum, fmtBytes,
  critBadge, statusBadge, LEVEL_FA, openModal, confirmDialog, jalaliInput, downloadUrl,
  faToEnDigits,
} from '../core.js?v=12';
import { toJalaliStr } from '../jalali.js?v=12';
import { icon } from '../icons.js?v=12';

const CRIT_FA = { low: 'کم', medium: 'متوسط', high: 'زیاد', critical: 'بحرانی' };
const TABS = [
  ['ident', 'شناسنامه', 'card'],
  ['tech', 'اطلاعات فنی', 'settings'],
  ['structure', 'ساختار', 'tree'],
  ['plans', 'برنامه نت', 'calendar'],
  ['checklists', 'چک‌لیست‌ها', 'checklists'],
  ['history', 'سوابق نت', 'activity'],
  ['parts', 'قطعات', 'parts'],
  ['costs', 'هزینه‌ها', 'cost'],
  ['docs', 'اسناد', 'audit'],
  ['calib', 'کالیبراسیون', 'calibration'],
  ['kpi', 'KPI', 'reports'],
  ['risks', 'ریسک و فرصت', 'risks'],
];

export async function renderEquipmentDetail(main, id) {
  main.replaceChildren(spinner('در حال بارگذاری پرونده تجهیز...'));
  let eq;
  try { eq = await api(`/equipment/${id}`); }
  catch (e) { main.replaceChildren(h('div', { class: 'card' }, h('div', { class: 'card-body' }, '⚠️ ', errText(e)))); return; }

  let actTypes = [], intervals = [];
  try {
    const l = await api('/lookups');
    actTypes = l.items.filter(x => x.list_code === 'activity_type' && x.is_active);
    intervals = l.items.filter(x => x.list_code === 'interval' && x.is_active);
  } catch {}

  const actFa = c => actTypes.find(x => x.code === c)?.title_fa || c;
  const intFa = c => intervals.find(x => x.code === c)?.title_fa || c;

  let activeTab = 'ident';
  const tabbar = h('div', { class: 'tabs', style: 'background:var(--c-card);border:1px solid var(--c-border);border-radius:12px 12px 0 0;padding:0 8px' });
  const panel = h('div', { class: 'tab-panel' });

  const header = h('div', { class: 'page-head', style: 'background:var(--c-card);border:1px solid var(--c-border);border-radius:12px;padding:16px' },
    h('div', { style: 'display:flex;gap:16px;align-items:center' },
      h('img', {
        src: '/assets/bfg-logo.png',
        style: 'width:48px;height:48px;object-fit:contain;background:#fff;border-radius:10px;padding:4px;border:1px solid var(--c-border)',
        onerror: function() { this.style.display='none'; }
      }),
      h('div', {},
        h('div', { class: 'breadcrumb', style: 'margin-bottom:4px' },
          h('a', { href: '#/equipment', style: 'color:var(--c-text-2)' }, 'تجهیزات'),
          h('span', { style: 'margin:0 6px;color:var(--c-text-3)' }, '›'),
          h('span', {}, LEVEL_FA[eq.level] || eq.level)
        ),
        h('div', { style: 'display:flex;gap:12px;align-items:center;flex-wrap:wrap' },
          h('h1', { style: 'font-size:20px' }, eq.name),
          h('span', { class: 'mono small ltr', style: 'background:var(--c-surface-2);border:1px solid var(--c-border);padding:2px 8px;border-radius:6px' }, eq.code),
          critBadge(eq.criticality, CRIT_FA[eq.criticality]),
          statusBadge(eq.status)
        ),
        h('div', { class: 'small faint', style: 'margin-top:4px' },
          `${eq.factory?.name || ''} ${eq.factory ? '·' : ''} ${eq.category?.name || ''} ${eq.location ? '· ' + eq.location : ''}`
        )
      )
    ),
    h('div', { class: 'spacer' }),
    h('div', { style: 'display:flex;gap:8px' },
      h('button', { class: 'btn btn-secondary btn-sm', onclick: () => navigate(`#/equipment/${eq.id}/passport`) },
        h('span', { html: icon('printer'), style: 'width:14px;height:14px' }), 'پاسپورت'
      ),
      Session.can('equipment.create') && eq.level !== 'subcomponent' ? h('button', { class: 'btn btn-secondary btn-sm', onclick: addChild }, '+ فرزند') : null,
      Session.can('equipment.delete') ? h('button', { class: 'btn btn-ghost btn-sm', style: 'color:var(--c-danger)', onclick: archive }, 'آرشیو') : null
    )
  );

  main.replaceChildren(header, h('div', { style: 'margin-top:12px' }, tabbar), panel);
  draw();

  function draw() {
    tabbar.replaceChildren(...TABS.map(([k, label, ic]) => h('button', {
      class: `tab ${k === activeTab ? 'active' : ''}`,
      onclick: () => { activeTab = k; draw(); },
    }, h('span', { html: icon(ic), style: 'width:14px;height:14px;margin-inline-end:6px;display:inline-flex;vertical-align:middle' }), label)));

    panel.replaceChildren(spinner());
    if (activeTab === 'ident') panel.replaceChildren(tabIdent());
    else if (activeTab === 'tech') panel.replaceChildren(tabTech());
    else if (activeTab === 'structure') panel.replaceChildren(tabStructure());
    else if (activeTab === 'plans') (async () => {
      try {
        const [d, cons] = await Promise.all([
          api(`/equipment/${id}/plans`),
          api(`/equipment/${id}/pm-consumables`).catch(() => ({ items: [] })),
        ]);
        panel.replaceChildren(renderPlans(d, cons.items));
      } catch (e) { panel.replaceChildren(errorBox(e)); }
    })();
    else if (activeTab === 'checklists') load(`/equipment/${id}/checklists`, renderChecklists);
    else if (activeTab === 'history') load(`/equipment/${id}/history`, renderHistory);
    else if (activeTab === 'parts') load(`/equipment/${id}/parts`, renderParts);
    else if (activeTab === 'costs') load(`/equipment/${id}/costs`, renderCosts);
    else if (activeTab === 'docs') panel.replaceChildren(tabDocs());
    else if (activeTab === 'calib') load(`/calibration?equipment_id=${id}`, renderCalib);
    else if (activeTab === 'kpi') load(`/equipment/${id}/kpi`, renderKpi);
    else if (activeTab === 'risks') load(`/risks?equipment_id=${id}`, renderRisks);
  }

  function errorBox(e) { return h('div', { class: 'card' }, h('div', { class: 'card-body', style: 'color:var(--c-danger)' }, errText(e))); }
  async function load(path, fn) {
    try { const d = await api(path); panel.replaceChildren(fn(d)); }
    catch (e) { panel.replaceChildren(errorBox(e)); }
  }

  function payload() {
    return {
      code: eq.code, name: eq.name, level: eq.level,
      factory_id: eq.factory ? eq.factory.id : null, category_id: eq.category ? eq.category.id : null,
      parent_id: eq.parent_id, location: eq.location, manufacturer: eq.manufacturer, model: eq.model,
      serial_number: eq.serial_number, year: eq.year, criticality: eq.criticality, status: eq.status,
      technical_specs: eq.technical_specs, hall: eq.hall, dept: eq.dept, line: eq.line,
      position: eq.position, component_type: eq.component_type, version: eq.version
    };
  }

  function validateBeforeSave() {
    if (!eq.code || !String(eq.code).trim()) return 'کد تجهیز نمی‌تواند خالی باشد';
    if (!eq.name || String(eq.name).trim().length < 2) return 'نام تجهیز حداقل ۲ نویسه لازم دارد';
    const raw = eq.year;
    if (raw !== null && raw !== undefined && raw !== '') {
      const n = Number(faToEnDigits(String(raw).trim()));
      if (!Number.isFinite(n)) return 'سال ساخت باید عدد باشد';
      if (n >= 1200 && n < 1500) return `سال ${faNum(n)} شمسی است؛ میلادی وارد کنید (۲۰۱۹)`;
      if (n < 1800 || n > 2200) return 'سال ساخت باید بین ۱۸۰۰ تا ۲۲۰۰ باشد';
      eq.year = Math.trunc(n);
    } else eq.year = null;
    return null;
  }

  function tabIdent() {
    const f = (k, label, ltr) => h('div', { class: 'field' }, h('label', {}, label),
      h('input', { class: 'input', dir: ltr ? 'ltr' : 'rtl', value: eq[k] || '', oninput: e => eq[k] = e.target.value || null })
    );
    const yearField = h('div', { class: 'field' }, h('label', {}, 'سال ساخت (میلادی)'),
      h('input', { class: 'input', dir: 'ltr', placeholder: 'مثال: 2019', value: eq.year ?? '', oninput: e => eq.year = e.target.value || null })
    );
    const save = Session.can('equipment.edit') ? h('button', { class: 'btn btn-primary', onclick: saveIdent }, 'ذخیره تغییرات') : null;

    return h('div', { class: 'card' },
      h('div', { class: 'card-head' },
        h('h2', { style: 'display:flex;gap:8px;align-items:center' },
          h('img', { src: '/assets/bfg-logo.png', style: 'width:20px;height:20px;object-fit:contain;background:#fff;border-radius:4px;padding:2px', onerror: function() { this.style.display='none'; } }),
          'شناسنامه تجهیز'
        ),
        h('span', { class: 'badge neutral' }, `نسخه: ${faNum(eq.version)}`)
      ),
      h('div', { class: 'card-body' },
        h('div', { class: 'form-grid' },
          f('code', 'کد تجهیز', true), f('name', 'نام تجهیز'),
          f('manufacturer', 'سازنده'), f('model', 'مدل'),
          f('serial_number', 'شماره سریال', true), yearField,
          f('hall', 'سالن'), f('dept', 'بخش'), f('line', 'خط'), f('position', 'موقعیت'),
          f('component_type', 'نوع قطعه')
        ),
        save ? h('div', { style: 'margin-top:20px' }, save) : null
      )
    );
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
      const rows = Object.entries(specs).map(([k, v]) => h('div', { style: 'display:flex;gap:8px;margin-bottom:8px' },
        h('input', { class: 'input', value: k, readonly: true, style: 'max-width:200px;background:var(--c-surface-2)' }),
        h('input', { class: 'input', value: v, oninput: e => specs[k] = e.target.value }),
        Session.can('equipment.edit') ? h('button', { class: 'btn btn-ghost btn-sm', onclick: () => { delete specs[k]; drawS(); } }, '✕') : null
      ));
      const kI = h('input', { class: 'input', placeholder: 'کلید (مثل: ظرفیت)', style: 'max-width:200px' });
      const vI = h('input', { class: 'input', placeholder: 'مقدار' });
      box.replaceChildren(
        rows.length ? h('div', { style: 'margin-bottom:16px' }, rows) : h('div', { class: 'small faint', style: 'padding:20px;text-align:center;border:1px dashed var(--c-border);border-radius:8px' }, 'مشخصه‌ای ثبت نشده'),
        Session.can('equipment.edit') ? h('div', { style: 'display:flex;gap:8px' }, kI, vI,
          h('button', { class: 'btn btn-secondary btn-sm', onclick: () => { if (kI.value.trim()) { specs[kI.value.trim()] = vI.value; kI.value = ''; vI.value = ''; drawS(); } } }, '+ افزودن')
        ) : null
      );
    }
    drawS();
    const save = Session.can('equipment.edit') ? h('button', { class: 'btn btn-primary', style: 'margin-top:16px', onclick: async () => {
      const vErr = validateBeforeSave();
      if (vErr) { toast(vErr, 'danger', 6000); return; }
      try { eq.technical_specs = specs; eq = await api(`/equipment/${eq.id}`, { method: 'PUT', body: payload() }); toast('ذخیره شد', 'success'); }
      catch (e) { toast(errText(e), 'danger', 6000); }
    } }, 'ذخیره مشخصات فنی') : null;

    return h('div', { class: 'card' },
      h('div', { class: 'card-head' }, h('h2', {}, 'مشخصات فنی')),
      h('div', { class: 'card-body' }, box, save)
    );
  }

  function tabStructure() {
    if (!eq.children.length) return h('div', { class: 'card' }, h('div', { class: 'card-body empty-state' },
      h('div', { class: 'empty-icon', html: icon('tree') }),
      h('h3', {}, 'زیرسیستم/جزئی ثبت نشده'),
      h('div', { class: 'small muted' }, 'از دکمه + فرزند استفاده کنید')
    ));
    const rows = eq.children.map(c => h('tr', { class: 'clickable', onclick: () => navigate(`#/equipment/${c.id}`) },
      h('td', { class: 'ltr mono small' }, c.code),
      h('td', { style: 'font-weight:500' }, c.name),
      h('td', {}, h('span', { class: 'badge neutral' }, LEVEL_FA[c.level])),
      h('td', {}, critBadge(c.criticality, CRIT_FA[c.criticality])),
      h('td', {}, statusBadge(c.status))
    ));
    return h('div', { class: 'card' },
      h('div', { class: 'card-head' }, h('h2', {}, 'ساختار تجهیز — زیرسیستم‌ها و قطعات')),
      h('div', { class: 'table-wrap' },
        h('table', { class: 'table' },
          h('thead', {}, h('tr', {}, ['کد', 'نام', 'سطح', 'اهمیت', 'وضعیت'].map(x => h('th', {}, x)))),
          h('tbody', {}, rows)
        )
      )
    );
  }

  function renderPlans(d, consumables = []) {
    const rows = d.items.map(p => h('tr', {},
      h('td', { style: 'font-weight:500' }, p.work_title),
      h('td', { class: 'small' }, actFa(p.activity_type)),
      h('td', { class: 'small' }, intFa(p.interval_code)),
      h('td', { class: 'small' }, p.performer || '—'),
      h('td', { class: 'ltr small' }, toJalaliStr(p.last_execution)),
      h('td', { class: 'ltr small' }, toJalaliStr(p.next_due)),
      h('td', {}, p.overdue ? h('span', { class: 'badge danger' }, 'عقب‌افتاده') : h('span', { class: 'badge success' }, 'در برنامه'))
    ));

    const consSection = consumables.length ? h('div', { class: 'card', style: 'margin-top:16px' },
      h('div', { class: 'card-head' }, h('h2', {}, 'قطعات مصرفی PM')),
      h('div', { class: 'table-wrap' },
        h('table', { class: 'table' },
          h('thead', {}, h('tr', {}, ['برنامه', 'قطعه', 'مقدار', 'دوره'].map(x => h('th', {}, x)))),
          h('tbody', {}, consumables.map(c => h('tr', {},
            h('td', { class: 'small' }, c.plan_title),
            h('td', {}, c.part_name),
            h('td', { class: 'small' }, `${faNum(c.quantity)} ${c.unit || ''}`),
            h('td', { class: 'small' }, intFa(c.interval_code))
          )))
        )
      )
    ) : null;

    return h('div', {},
      Session.can('plans.create') ? h('div', { class: 'toolbar' },
        h('div', { class: 'spacer' }),
        h('button', { class: 'btn btn-primary btn-sm', onclick: () => planModal(null) }, '+ فعالیت جدید')
      ) : null,
      d.items.length ? h('div', { class: 'card' },
        h('div', { class: 'table-wrap' },
          h('table', { class: 'table' },
            h('thead', {}, h('tr', {}, ['عنوان', 'نوع', 'تناوب', 'مجری', 'آخرین', 'بعدی', 'وضعیت'].map(x => h('th', {}, x)))),
            h('tbody', {}, rows)
          )
        )
      ) : h('div', { class: 'card' }, h('div', { class: 'card-body empty-state' },
        h('div', { class: 'empty-icon', html: icon('calendar') }),
        h('h3', {}, 'برنامه‌ای ثبت نشده')
      )),
      consSection
    );
  }

  function planModal(p) {
    const title = h('input', { class: 'input', value: p ? p.work_title : '', placeholder: 'عنوان فعالیت' });
    const ty = h('select', { class: 'select' }, ...actTypes.map(t => h('option', { value: t.code }, t.title_fa)));
    const iv = h('select', { class: 'select' }, ...intervals.map(t => h('option', { value: t.code }, t.title_fa)));
    if (p) { ty.value = p.activity_type; iv.value = p.interval_code; }
    const save = h('button', { class: 'btn btn-primary', onclick: async () => {
      const body = { equipment_id: eq.id, work_title: title.value.trim(), activity_type: ty.value, interval_code: iv.value, work_class: 'pm' };
      if (!body.work_title) { toast('عنوان الزامی است', 'warning'); return; }
      try {
        if (p) await api(`/plans/${p.id}`, { method: 'PUT', body: { ...body, version: p.version } });
        else await api('/plans', { method: 'POST', body });
        m.close(); draw();
      } catch (e) { toast(errText(e), 'danger'); }
    } }, 'ذخیره');
    const m = openModal({
      title: p ? 'ویرایش برنامه' : 'فعالیت PM جدید',
      body: h('div', { class: 'form-grid' },
        h('div', { class: 'field span-2' }, h('label', {}, 'عنوان *'), title),
        h('div', { class: 'field' }, h('label', {}, 'نوع'), ty),
        h('div', { class: 'field' }, h('label', {}, 'تناوب'), iv)
      ),
      footer: [save]
    });
  }

  function renderChecklists(d) {
    if (!d.items.length) return h('div', { class: 'card' }, h('div', { class: 'card-body empty-state' },
      h('div', { class: 'empty-icon', html: icon('checklists') }),
      h('h3', {}, 'چک‌لیست ثبت نشده'),
      Session.can('checklist.manage') ? h('button', { class: 'btn btn-secondary btn-sm', style: 'margin-top:12px', onclick: async (ev) => {
        ev.currentTarget.disabled = true;
        try {
          const t = await api(`/checklists/from-plans/${eq.id}`, { method: 'POST' });
          toast(`چک‌لیست با ${faNum(t.items.length)} آیتم ساخته شد`, 'success');
          draw();
        } catch (e) { toast(errText(e), 'danger'); ev.currentTarget.disabled = false; }
      } }, 'ساخت چک‌لیست از PM') : null
    ));

    const rows = d.items.map(r => h('tr', { class: 'clickable', onclick: () => navigate(`#/checklists/${r.id}`) },
      h('td', {}, r.template_name || '—'),
      h('td', {}, r.result_summary === 'fail' ? h('span', { class: 'badge danger' }, 'نامطلوب') : h('span', { class: 'badge success' }, 'سالم')),
      h('td', { class: 'small' }, r.technician_name || '—'),
      h('td', { class: 'ltr small' }, toJalaliStr(r.run_date))
    ));

    return h('div', { class: 'card' },
      h('div', { class: 'card-head' }, h('h2', {}, 'چک‌لیست‌های بازرسی')),
      h('div', { class: 'table-wrap' },
        h('table', { class: 'table' },
          h('thead', {}, h('tr', {}, ['قالب', 'نتیجه', 'تکنسین', 'تاریخ'].map(x => h('th', {}, x)))),
          h('tbody', {}, rows)
        )
      )
    );
  }

  function renderHistory(d) {
    if (!d.items.length) return h('div', { class: 'card' }, h('div', { class: 'card-body empty-state' },
      h('div', { class: 'empty-icon', html: icon('activity') }),
      h('h3', {}, 'سابقه‌ای ثبت نشده'),
      h('div', { class: 'small muted' }, 'با بستن دستورکار، سوابق اینجا ثبت می‌شوند')
    ));

    const rows = d.items.map(it => h('tr', { class: it.work_order_id ? 'clickable' : '', onclick: () => it.work_order_id && navigate(`#/work-orders/${it.work_order_id}`) },
      h('td', { style: 'font-weight:500' }, it.title),
      h('td', { class: 'small' }, it.work_type),
      h('td', { class: 'small' }, it.technician_name || '—'),
      h('td', { class: 'ltr small' }, toJalaliStr(it.finished_at)),
      h('td', { class: 'small' }, it.duration_minutes ? `${faNum(it.duration_minutes)} دقیقه` : '—')
    ));

    return h('div', { class: 'card' },
      h('div', { class: 'card-head' }, h('h2', {}, 'سوابق نگهداری')),
      h('div', { class: 'table-wrap' },
        h('table', { class: 'table' },
          h('thead', {}, h('tr', {}, ['عنوان', 'نوع', 'تکنسین', 'خاتمه', 'مدت'].map(x => h('th', {}, x)))),
          h('tbody', {}, rows)
        )
      )
    );
  }

  function renderParts(d) {
    if (!d.items.length) return h('div', { class: 'card' }, h('div', { class: 'card-body empty-state' },
      h('div', { class: 'empty-icon', html: icon('parts') }),
      h('h3', {}, 'قطعه‌ای مرتبط نیست')
    ));

    const rows = d.items.map(p => h('tr', {},
      h('td', { class: 'ltr mono small' }, p.part_number || p.code),
      h('td', { style: 'font-weight:500' }, p.name),
      h('td', { class: 'small' }, faNum(p.current_stock ?? p.quantity)),
      h('td', { class: 'small' }, faNum(p.min_stock)),
      h('td', {}, critBadge(p.criticality, CRIT_FA[p.criticality] || p.criticality)),
      h('td', { class: 'small' }, p.supplier || '—')
    ));

    return h('div', { class: 'card' },
      h('div', { class: 'card-head' }, h('h2', {}, 'قطعات و انبار')),
      h('div', { class: 'table-wrap' },
        h('table', { class: 'table' },
          h('thead', {}, h('tr', {}, ['Part No', 'نام', 'موجودی', 'حد سفارش', 'اهمیت', 'تأمین‌کننده'].map(x => h('th', {}, x)))),
          h('tbody', {}, rows)
        )
      )
    );
  }

  function renderCosts(d) {
    const total = d.total || 0;
    return h('div', {},
      h('div', { class: 'kpi-grid' },
        h('div', { class: 'kpi gold' },
          h('div', { class: 'kpi-label' }, 'هزینه تجمعی'),
          h('div', { class: 'kpi-value', style: 'font-size:22px' }, Number(total).toLocaleString('fa-IR')),
          h('div', { class: 'kpi-sub' }, 'ریال')
        )
      ),
      (d.by_type || []).length ? h('div', { class: 'card', style: 'margin-top:16px' },
        h('div', { class: 'table-wrap' },
          h('table', { class: 'table' },
            h('thead', {}, h('tr', {}, ['نوع', 'مبلغ'].map(x => h('th', {}, x)))),
            h('tbody', {}, (d.by_type || []).map(c => h('tr', {},
              h('td', {}, c.cost_type),
              h('td', { class: 'ltr mono' }, Number(c.amount).toLocaleString('fa-IR'))
            )))
          )
        )
      ) : h('div', { class: 'card', style: 'margin-top:16px' },
        h('div', { class: 'card-body empty-state' },
          h('div', { class: 'empty-icon', html: icon('cost') }),
          h('h3', {}, 'هزینه‌ای ثبت نشده')
        )
      )
    );
  }

  function tabDocs() {
    const list = h('div', {});
    function drawF() {
      list.replaceChildren(eq.files.length ? h('div', { class: 'card' },
        h('div', { class: 'table-wrap' },
          h('table', { class: 'table' },
            h('thead', {}, h('tr', {}, ['نام', 'حجم', 'تاریخ', ''].map(x => h('th', {}, x)))),
            h('tbody', {}, eq.files.map(f => h('tr', {},
              h('td', { style: 'font-weight:500' }, f.name),
              h('td', { class: 'small' }, fmtBytes(f.size)),
              h('td', { class: 'ltr small' }, toJalaliStr(f.created_at)),
              h('td', {}, h('button', { class: 'btn btn-ghost btn-sm', onclick: () => downloadUrl(`/files/${f.id}/download`) }, 'دانلود'))
            )))
          )
        )
      ) : h('div', { class: 'card' }, h('div', { class: 'card-body empty-state' },
        h('div', { class: 'empty-icon', html: icon('audit') }),
        h('h3', {}, 'مدرکی پیوست نشده')
      )));
    }
    const fi = h('input', { type: 'file', style: 'display:none' });
    fi.onchange = async () => {
      const f = fi.files[0]; if (!f) return;
      const fd = new FormData(); fd.append('file', f);
      try {
        await api(`/equipment/${eq.id}/files`, { method: 'POST', form: fd });
        toast('بارگذاری شد', 'success');
        eq = await api(`/equipment/${id}`);
        drawF();
      } catch (e) { toast(errText(e), 'danger'); }
    };
    drawF();
    const up = Session.can('files.upload') ? h('div', { style: 'margin-top:16px' },
      h('div', { class: 'upload-zone', style: 'border:1px dashed var(--c-border);border-radius:12px;padding:24px;text-align:center;cursor:pointer', onclick: () => fi.click() },
        h('div', { html: icon('import'), style: 'width:24px;height:24px;margin:0 auto 8px auto;color:var(--c-text-3)' }),
        h('div', { class: 'small' }, 'بارگذاری فایل — کلیک کنید')
      ),
      fi
    ) : null;
    return h('div', {}, list, up);
  }

  function renderCalib(d) {
    if (!d.items.length) return h('div', { class: 'card' }, h('div', { class: 'card-body empty-state' },
      h('div', { class: 'empty-icon', html: icon('calibration') }),
      h('h3', {}, 'کالیبراسیونی ثبت نشده')
    ));
    const rows = d.items.map(c => h('tr', {},
      h('td', {}, c.standard || '—'),
      h('td', { class: 'ltr small' }, toJalaliStr(c.last_calibration)),
      h('td', { class: 'small' }, `${faNum(c.interval_days)} روز`),
      h('td', { class: 'ltr small' }, toJalaliStr(c.next_due)),
      h('td', {}, c.overdue ? h('span', { class: 'badge danger' }, 'عقب‌افتاده') : h('span', { class: 'badge success' }, 'در برنامه'))
    ));
    return h('div', { class: 'card' },
      h('div', { class: 'card-head' }, h('h2', {}, 'کالیبراسیون')),
      h('div', { class: 'table-wrap' },
        h('table', { class: 'table' },
          h('thead', {}, h('tr', {}, ['استاندارد', 'آخرین', 'دوره', 'سررسید', 'وضعیت'].map(x => h('th', {}, x)))),
          h('tbody', {}, rows)
        )
      )
    );
  }

  function renderKpi(k) {
    const card = (label, value, sub, tone = 'gold') => h('div', { class: `kpi ${tone}` },
      h('div', { class: 'kpi-label' }, label),
      h('div', { class: 'kpi-value', style: 'font-size:20px' }, value == null ? '—' : faNum(value)),
      h('div', { class: 'kpi-sub' }, sub || '')
    );
    return h('div', { class: 'kpi-grid' },
      card('MTBF (ساعت)', k.mtbf_hours, 'میانگین زمان بین خرابی', 'info'),
      card('MTTR (دقیقه)', k.mttr_minutes, 'میانگین زمان تعمیر', 'info'),
      card('تعداد خرابی', k.failure_count, 'کل خرابی‌ها', 'danger'),
      card('دستورکارها', k.work_order_count, 'کل دستورکارها', 'warning'),
      card('انطباق PM ٪', k.pm_compliance_pct, 'درصد انطباق', 'success'),
      card('هزینه نت', k.maintenance_cost ? Math.round(k.maintenance_cost) : 0, 'ریال', 'gold')
    );
  }

  function renderRisks(d) {
    if (!d.items.length) return h('div', { class: 'card' }, h('div', { class: 'card-body empty-state' },
      h('div', { class: 'empty-icon', html: icon('risks') }),
      h('h3', {}, 'ریسکی ثبت نشده')
    ));
    const rows = d.items.map(r => h('tr', {},
      h('td', {}, h('span', { class: `badge ${r.kind === 'risk' ? 'danger' : 'success'}` }, r.kind === 'risk' ? 'ریسک' : 'فرصت')),
      h('td', { style: 'font-weight:500' }, r.title),
      h('td', {}, h('span', { class: 'badge neutral' }, faNum(r.risk_score))),
      h('td', { class: 'small' }, r.mitigation || '—'),
      h('td', { class: 'small' }, r.status)
    ));
    return h('div', { class: 'card' },
      h('div', { class: 'card-head' }, h('h2', {}, 'ریسک و فرصت')),
      h('div', { class: 'table-wrap' },
        h('table', { class: 'table' },
          h('thead', {}, h('tr', {}, ['نوع', 'عنوان', 'امتیاز', 'اقدام', 'وضعیت'].map(x => h('th', {}, x)))),
          h('tbody', {}, rows)
        )
      )
    );
  }

  function addChild() {
    const next = { equipment: 'subsystem', subsystem: 'component', component: 'subcomponent' }[eq.level];
    const code = h('input', { class: 'input ltr', placeholder: 'کد مثل B1P01.01' });
    const name = h('input', { class: 'input', placeholder: 'نام زیرسیستم' });
    const save = h('button', { class: 'btn btn-primary', onclick: async () => {
      try {
        const c = await api('/equipment', { method: 'POST', body: {
          code: code.value.trim(), name: name.value.trim(), level: next, parent_id: eq.id,
          factory_id: eq.factory ? eq.factory.id : null, category_id: eq.category ? eq.category.id : null,
          criticality: eq.criticality, status: 'active'
        }});
        m.close(); navigate(`#/equipment/${c.id}`);
      } catch (e) { toast(errText(e), 'danger'); }
    } }, 'ثبت');
    const m = openModal({
      title: `افزودن ${LEVEL_FA[next]}`,
      body: h('div', { class: 'form-grid' },
        h('div', { class: 'field' }, h('label', {}, 'کد *'), code),
        h('div', { class: 'field' }, h('label', {}, 'نام *'), name)
      ),
      footer: [save]
    });
  }

  async function archive() {
    if (!await confirmDialog(`تجهیز «${eq.name}» آرشیو شود؟`, { danger: true, title: 'آرشیو تجهیز' })) return;
    try { await api(`/equipment/${eq.id}`, { method: 'DELETE' }); toast('آرشیو شد', 'success'); navigate('#/equipment'); }
    catch (e) { toast(errText(e), 'danger'); }
  }
}
