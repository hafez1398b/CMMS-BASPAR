/** Equipment شناسنامه/Passport (§9 MODULE EQUIPMENT) — official printable:
 *  logo, company, full identification, specs, structure, PM & history &
 *  calibration summaries.  Print / PDF export via browser. */
import { api, errText, h, faNum, navigate, spinner, LEVEL_FA } from '../core.js?v=11';
import { toJalaliStr, jalaliLong } from '../jalali.js?v=11';

const CRIT_FA = { low: 'کم', medium: 'متوسط', high: 'زیاد', critical: 'بحرانی' };

export async function renderPassport(main, id) {
  main.replaceChildren(spinner());
  let doc, calib = [];
  try {
    doc = await api(`/equipment/${id}/passport`);
    calib = (await api(`/calibration?equipment_id=${id}`)).items;
  } catch (e) { main.replaceChildren(h('div', { class: 'card' }, h('div', { class: 'card-body' }, '⚠️ ', errText(e)))); return; }

  const e = doc.equipment;
  const kv = (k, v) => h('tr', {}, h('td', {}, k), h('td', {}, v ?? '—'));

  const indent = (n) => h('span', { class: 'tree-indent', style: `width:${n * 18}px` });
  const structureRows = doc.structure.map((s) => h('tr', {},
    h('td', {}, indent(s.depth), s.name),
    h('td', { class: 'ltr small' }, s.code),
    h('td', { class: 'small' }, LEVEL_FA[s.level])));

  const planRows = doc.maintenance_plans.map((p) => h('tr', {},
    h('td', {}, p.work_title),
    h('td', { class: 'small' }, p.interval_code),
    h('td', { class: 'small' }, p.performer || '—'),
    h('td', { class: 'ltr small' }, toJalaliStr(p.last_execution)),
    h('td', { class: 'ltr small' }, toJalaliStr(p.next_due))));

  const calibStatus = calib.length
    ? (calib.some((c) => c.overdue) ? 'عقب‌افتاده' : 'در برنامه')
    : 'تعریف نشده';

  main.replaceChildren(h('div', { class: 'passport-doc' },
    h('div', { class: 'toolbar no-print' },
      h('button', { class: 'btn btn-secondary', onclick: () => navigate(`#/equipment/${id}`) }, '→ بازگشت به پرونده تجهیز'),
      h('div', { class: 'spacer' }),
      h('button', { class: 'btn btn-primary', onclick: () => window.print() }, '🖨 Print / PDF (§9)')),

    h('div', { class: 'card' }, h('div', { class: 'card-body' },
      // §9 header: logo + company name
      h('div', { class: 'passport-head' },
        h('div', { style: 'display:flex;gap:12px;align-items:center' },
          h('span', { class: 'brand-mark', style: 'display:inline-flex;width:48px;height:48px;border-radius:12px;font-size:24px' }, 'B'),
          h('div', {},
            h('div', { style: 'font-weight:800;font-size:16px' }, 'شرکت بسپار — BASPAR'),
            h('div', { class: 'faint small' }, 'سامانه مدیریت نت هوشمند CMMS/EAM'))),
        h('div', { class: 'small muted', style: 'text-align:left' },
          h('div', {}, 'شناسنامه تجهیز — Equipment Passport'),
          h('div', {}, `تاریخ صدور: ${jalaliLong(new Date().toISOString())}`))),

      h('h2', {}, '۱. شناسایی'),
      h('div', { class: 'passport-grid' },
        h('table', { class: 'table spec-table' }, h('tbody', {}, [
          kv('کد تجهیز', e.code), kv('نام تجهیز', e.name),
          kv('کارخانه', e.factory?.name), kv('دسته', e.category?.name),
          kv('وضعیت', e.status), kv('Criticality', CRIT_FA[e.criticality]),
        ])),
        h('table', { class: 'table spec-table' }, h('tbody', {}, [
          kv('سازنده', e.manufacturer), kv('مدل', e.model),
          kv('شماره سریال', e.serial_number), kv('سال ساخت', e.year && faNum(e.year)),
          kv('محل استقرار', [e.hall, e.dept, e.line, e.position].filter(Boolean).join(' / ') || e.location),
        ]))),

      h('h2', { class: 'mt-4' }, '۲. مشخصات فنی'),
      h('table', { class: 'table spec-table' }, h('tbody', {},
        Object.entries(e.technical_specs || {}).map(([k, v]) => kv(k, v))
          .concat([Object.keys(e.technical_specs || {}).length ? null :
            h('tr', {}, h('td', { colspan: '2', class: 'small faint' }, 'مشخصه فنی ثبت نشده'))]))),

      h('h2', { class: 'mt-4' }, '۳. ساختار تجهیز (زیرسیستم‌ها و قطعات اصلی)'),
      structureRows.length
        ? h('table', { class: 'table' },
            h('thead', {}, h('tr', {}, ['نام', 'کد', 'سطح'].map((x) => h('th', {}, x)))),
            h('tbody', {}, structureRows))
        : h('div', { class: 'small faint' }, 'زیرسیستم یا قطعه‌ای ثبت نشده است.'),

      h('h2', { class: 'mt-4' }, '۴. خلاصه برنامه نگهداری (PM)'),
      planRows.length
        ? h('table', { class: 'table' },
            h('thead', {}, h('tr', {}, ['عنوان', 'تناوب', 'مسئول', 'آخرین اجرا', 'اجرای بعدی'].map((x) => h('th', {}, x)))),
            h('tbody', {}, planRows))
        : h('div', { class: 'small faint' }, 'برنامه‌ای ثبت نشده است.'),

      h('div', { class: 'passport-grid mt-4' },
        h('div', {},
          h('h2', {}, '۵. خلاصه سوابق'),
          doc.maintenance_history.length
            ? h('table', { class: 'table' },
                h('thead', {}, h('tr', {}, ['عنوان', 'نوع', 'تکنسین', 'خاتمه'].map((x) => h('th', {}, x)))),
                h('tbody', {}, doc.maintenance_history.slice(0, 8).map((hh) => h('tr', {},
                  h('td', {}, hh.title), h('td', { class: 'small' }, hh.work_type),
                  h('td', { class: 'small' }, hh.technician_name || '—'),
                  h('td', { class: 'ltr small' }, toJalaliStr(hh.finished_at))))))
            : h('div', { class: 'small faint' }, 'سابقه‌ای ثبت نشده است.')),
        h('div', {},
          h('h2', {}, '۶. وضعیت کالیبراسیون'),
          h('div', { class: 'small' },
            `وضعیت: ${calibStatus}`,
            calib.length ? h('ul', {}, ...calib.map((c) =>
              h('li', {}, `${c.standard || '—'} — سررسید: ${toJalaliStr(c.next_due)}`))) : null),
          h('h2', { class: 'mt-4' }, '۷. اسناد'),
          doc.documents.length
            ? h('ul', { class: 'small' }, doc.documents.map((d) => h('li', {}, d.name)))
            : h('div', { class: 'small faint' }, 'مدرکی پیوست نشده است.'))),

      h('h2', { class: 'mt-4' }, '۸. خلاصه هزینه'),
      doc.cost_summary && doc.cost_summary.total > 0
        ? h('div', { class: 'small' },
            `جمع: ${Number(doc.cost_summary.total).toLocaleString('fa-IR')} ریال`,
            h('ul', {}, Object.entries(doc.cost_summary.by_type || {}).map(([t, v]) =>
              h('li', {}, `${t}: ${Number(v).toLocaleString('fa-IR')}`))))
        : h('div', { class: 'small faint' }, 'هزینه‌ای ثبت نشده است.'),

      h('div', { class: 'small faint mt-4', style: 'border-top:1px solid var(--c-border);padding-top:10px' },
        'این شناسنامه به‌صورت خودکار از پرونده دیجیتال تجهیز تولید شده است.')))));
}
