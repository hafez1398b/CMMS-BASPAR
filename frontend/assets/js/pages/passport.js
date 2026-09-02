/** BASPAR CMMS — Equipment Passport v2.1
 * Dark First · Print with BFG Logo in header right corner
 */

import { api, errText, h, faNum, navigate, spinner, LEVEL_FA } from '../core.js?v=12';
import { toJalaliStr, jalaliLong } from '../jalali.js?v=12';

const CRIT_FA = { low: 'کم', medium: 'متوسط', high: 'زیاد', critical: 'بحرانی' };

export async function renderPassport(main, id) {
  main.replaceChildren(spinner());
  let doc, calib = [];
  try {
    doc = await api(`/equipment/${id}/passport`);
    calib = (await api(`/calibration?equipment_id=${id}`)).items;
  } catch (e) {
    main.replaceChildren(h('div', { class: 'card' }, h('div', { class: 'card-body' }, '⚠️ ', errText(e))));
    return;
  }

  const e = doc.equipment;
  const kv = (k, v) => h('tr', {}, h('td', { style: 'width:160px;color:var(--c-text-2);font-size:12px' }, k), h('td', {}, v ?? '—'));

  const indent = (n) => h('span', { style: `display:inline-block;width:${n * 18}px` });
  const structureRows = doc.structure.map(s => h('tr', {},
    h('td', {}, indent(s.depth), s.name),
    h('td', { class: 'ltr small mono' }, s.code),
    h('td', { class: 'small' }, LEVEL_FA[s.level])
  ));

  const planRows = doc.maintenance_plans.map(p => h('tr', {},
    h('td', {}, p.work_title),
    h('td', { class: 'small' }, p.interval_code),
    h('td', { class: 'small' }, p.performer || '—'),
    h('td', { class: 'ltr small' }, toJalaliStr(p.last_execution)),
    h('td', { class: 'ltr small' }, toJalaliStr(p.next_due))
  ));

  const calibStatus = calib.length ? (calib.some(c => c.overdue) ? 'عقب‌افتاده' : 'در برنامه') : 'تعریف نشده';

  main.replaceChildren(h('div', { class: 'passport-doc' },
    h('div', { class: 'toolbar no-print', style: 'background:var(--c-card);border:1px solid var(--c-border);border-radius:12px;padding:12px' },
      h('button', { class: 'btn btn-secondary btn-sm', onclick: () => navigate(`#/equipment/${id}`) }, '→ بازگشت به پرونده'),
      h('div', { class: 'spacer' }),
      h('button', { class: 'btn btn-primary btn-sm', onclick: () => window.print() },
        h('span', { style: 'display:inline-flex;width:14px;height:14px' }, '🖨'), ' چاپ / PDF'
      )
    ),

    h('div', { class: 'card', style: 'margin-top:16px' },
      h('div', { class: 'card-body' },
        // Header with BFG logo right corner as per spec
        h('div', { class: 'passport-head', style: 'display:flex;justify-content:space-between;align-items:flex-start;gap:16px;border-bottom:2px solid var(--c-gold);padding-bottom:16px;margin-bottom:20px' },
          h('div', { style: 'display:flex;gap:16px;align-items:center' },
            h('img', {
              src: '/assets/bfg-logo.png',
              alt: 'BFG Logo',
              style: 'width:64px;height:64px;object-fit:contain;background:#fff;border-radius:12px;padding:6px;border:1px solid var(--c-border);box-shadow:var(--shadow-1)',
              onerror: function() { this.style.display='none'; this.nextSibling.style.display='flex'; }
            }),
            h('div', {
              style: 'width:48px;height:48px;border-radius:12px;background:var(--c-gold);color:#0A0A0A;display:none;align-items:center;justify-content:center;font-weight:900;font-size:18px'
            }, 'BFG'),
            h('div', {},
              h('div', { style: 'font-weight:800;font-size:18px;letter-spacing:-0.02em' }, 'شرکت بسپار فوم غرب (سهامی خاص)'),
              h('div', { style: 'font-size:11px;color:var(--c-text-2);letter-spacing:0.05em;text-transform:uppercase' }, 'BASPAR FOAM GHARB Co. — Industrial CMMS'),
              h('div', { style: 'font-size:12px;color:var(--c-text-3);margin-top:4px' }, 'شناسنامه تجهیز — Equipment Passport')
            )
          ),
          h('div', { class: 'small', style: 'text-align:left;line-height:1.6' },
            h('div', { style: 'font-weight:600' }, `تاریخ صدور: ${jalaliLong(new Date().toISOString())}`),
            h('div', { class: 'faint' }, `کد تجهیز: ${e.code}`),
            h('div', { class: 'faint' }, `شناسه: ${e.id}`),
            h('div', { style: 'margin-top:8px' },
              h('img', {
                src: '/assets/bfg-logo.png',
                alt: 'BFG',
                style: 'width:40px;height:40px;object-fit:contain;opacity:0.9',
                onerror: function() { this.style.display='none'; }
              })
            )
          )
        ),

        h('h2', { style: 'font-size:14px;font-weight:700;border-inline-start:3px solid var(--c-gold);padding-inline-start:10px;margin:20px 0 12px 0' }, '۱. شناسایی'),
        h('div', { style: 'display:grid;grid-template-columns:1fr 1fr;gap:16px' },
          h('table', { class: 'table spec-table' }, h('tbody', {}, [
            kv('کد تجهیز', h('span', { class: 'mono ltr' }, e.code)),
            kv('نام تجهیز', h('strong', {}, e.name)),
            kv('کارخانه', e.factory?.name),
            kv('دسته', e.category?.name),
            kv('وضعیت', e.status),
            kv('اهمیت', CRIT_FA[e.criticality]),
          ])),
          h('table', { class: 'table spec-table' }, h('tbody', {}, [
            kv('سازنده', e.manufacturer),
            kv('مدل', e.model),
            kv('شماره سریال', e.serial_number),
            kv('سال ساخت', e.year && faNum(e.year)),
            kv('محل استقرار', [e.hall, e.dept, e.line, e.position].filter(Boolean).join(' / ') || e.location),
          ]))
        ),

        h('h2', { style: 'font-size:14px;font-weight:700;border-inline-start:3px solid var(--c-gold);padding-inline-start:10px;margin:20px 0 12px 0' }, '۲. مشخصات فنی'),
        h('table', { class: 'table spec-table' }, h('tbody', {},
          Object.entries(e.technical_specs || {}).map(([k, v]) => kv(k, v))
            .concat(Object.keys(e.technical_specs || {}).length ? [] : [h('tr', {}, h('td', { colspan: '2', class: 'small faint', style: 'padding:20px;text-align:center' }, 'مشخصه فنی ثبت نشده'))])
        )),

        h('h2', { style: 'font-size:14px;font-weight:700;border-inline-start:3px solid var(--c-gold);padding-inline-start:10px;margin:20px 0 12px 0' }, '۳. ساختار تجهیز'),
        structureRows.length ? h('div', { class: 'table-wrap' },
          h('table', { class: 'table' },
            h('thead', {}, h('tr', {}, ['نام', 'کد', 'سطح'].map(x => h('th', {}, x)))),
            h('tbody', {}, structureRows)
          )
        ) : h('div', { class: 'small faint', style: 'padding:20px;text-align:center;border:1px dashed var(--c-border);border-radius:8px' }, 'زیرسیستم یا قطعه‌ای ثبت نشده'),

        h('h2', { style: 'font-size:14px;font-weight:700;border-inline-start:3px solid var(--c-gold);padding-inline-start:10px;margin:20px 0 12px 0' }, '۴. برنامه نگهداری (PM)'),
        planRows.length ? h('div', { class: 'table-wrap' },
          h('table', { class: 'table' },
            h('thead', {}, h('tr', {}, ['عنوان', 'تناوب', 'مسئول', 'آخرین اجرا', 'اجرای بعدی'].map(x => h('th', {}, x)))),
            h('tbody', {}, planRows)
          )
        ) : h('div', { class: 'small faint', style: 'padding:20px;text-align:center;border:1px dashed var(--c-border);border-radius:8px' }, 'برنامه‌ای ثبت نشده'),

        h('div', { style: 'display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:20px' },
          h('div', {},
            h('h2', { style: 'font-size:14px;font-weight:700;border-inline-start:3px solid var(--c-gold);padding-inline-start:10px;margin:0 0 12px 0' }, '۵. سوابق'),
            doc.maintenance_history.length ? h('div', { class: 'table-wrap' },
              h('table', { class: 'table' },
                h('thead', {}, h('tr', {}, ['عنوان', 'نوع', 'تکنسین', 'خاتمه'].map(x => h('th', {}, x)))),
                h('tbody', {}, doc.maintenance_history.slice(0, 8).map(hh => h('tr', {},
                  h('td', {}, hh.title),
                  h('td', { class: 'small' }, hh.work_type),
                  h('td', { class: 'small' }, hh.technician_name || '—'),
                  h('td', { class: 'ltr small' }, toJalaliStr(hh.finished_at))
                )))
              )
            ) : h('div', { class: 'small faint' }, 'سابقه‌ای ثبت نشده')
          ),
          h('div', {},
            h('h2', { style: 'font-size:14px;font-weight:700;border-inline-start:3px solid var(--c-gold);padding-inline-start:10px;margin:0 0 12px 0' }, '۶. کالیبراسیون'),
            h('div', { class: 'small', style: 'background:var(--c-surface-2);border:1px solid var(--c-border);border-radius:8px;padding:12px' },
              `وضعیت: ${calibStatus}`,
              calib.length ? h('ul', { style: 'margin:8px 0 0 0;padding-inline-start:16px' }, ...calib.map(c => h('li', {}, `${c.standard || '—'} — سررسید: ${toJalaliStr(c.next_due)}`))) : null
            ),
            h('h2', { style: 'font-size:14px;font-weight:700;border-inline-start:3px solid var(--c-gold);padding-inline-start:10px;margin:16px 0 12px 0' }, '۷. اسناد'),
            doc.documents.length ? h('ul', { class: 'small' }, ...doc.documents.map(d => h('li', {}, d.name))) : h('div', { class: 'small faint' }, 'مدرکی پیوست نشده')
          )
        ),

        h('h2', { style: 'font-size:14px;font-weight:700;border-inline-start:3px solid var(--c-gold);padding-inline-start:10px;margin:20px 0 12px 0' }, '۸. خلاصه هزینه'),
        doc.cost_summary && doc.cost_summary.total > 0 ? h('div', { class: 'small', style: 'background:var(--c-surface-2);border:1px solid var(--c-border);border-radius:8px;padding:12px' },
          `جمع: ${Number(doc.cost_summary.total).toLocaleString('fa-IR')} ریال`,
          h('ul', {}, ...Object.entries(doc.cost_summary.by_type || {}).map(([t, v]) => h('li', {}, `${t}: ${Number(v).toLocaleString('fa-IR')}`)))
        ) : h('div', { class: 'small faint' }, 'هزینه‌ای ثبت نشده'),

        // Footer with BFG logo for print
        h('div', { style: 'margin-top:24px;border-top:2px solid var(--c-gold);padding-top:12px;display:flex;justify-content:space-between;align-items:center' },
          h('div', { style: 'display:flex;gap:12px;align-items:center' },
            h('img', { src: '/assets/bfg-logo.png', style: 'width:32px;height:32px;object-fit:contain;background:#fff;border-radius:6px;padding:2px', onerror: function() { this.style.display='none'; } }),
            h('div', { style: 'font-size:10px;color:var(--c-text-3)' },
              h('div', {}, 'شرکت بسپار فوم غرب (سهامی خاص)'),
              h('div', {}, 'BASPAR FOAM GHARB Co.')
            )
          ),
          h('div', { class: 'small faint', style: 'font-size:10px' }, 'این شناسنامه به‌صورت خودکار از پرونده دیجیتال تجهیز تولید شده است.')
        )
      )
    )
  ));
}
