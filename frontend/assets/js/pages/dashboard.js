/** داشبورد Enterprise CMMS (§9, §27) — KPI rows + charts + tables. */
import { api, errText, h, faNum, navigate, renderError, spinner, critBadge, statusBadge } from '../core.js?v=11';
import { toJalaliStr, jalaliLong } from '../jalali.js?v=11';
import { icon } from '../icons.js?v=11';

const CRIT_FA = { low: 'کم', medium: 'متوسط', high: 'زیاد', critical: 'بحرانی' };

export async function renderDashboard(main) {
  main.replaceChildren(h('div', { class: 'page-head' }, h('h1', {}, 'داشبورد')), spinner());
  try {
    const [kpis, adv, critical, due] = await Promise.all([
      api('/dashboard/kpis'),
      api('/reports/kpis-advanced').catch(() => null),
      api('/dashboard/critical-equipment'),
      api('/plans/due?days=30'),
    ]);

    const wo = kpis.work_orders || {};
    const req = kpis.requests || {};
    const today = jalaliLong(new Date().toISOString());

    // ---- KPI row 1: operational ----
    const row1 = h('div', { class: 'kpi-grid' },
      kpi('کل تجهیزات', kpis.equipment.total, `${faNum(kpis.equipment.active)} فعال`, 'primary', 'equipment'),
      kpi('تجهیزات بحرانی', kpis.equipment.critical_count, `${faNum(kpis.equipment.high_count)} اهمیت زیاد`, 'danger', 'risks'),
      kpi('انطباق PM', pct(kpis.pm.pm_compliance_pct), `${faNum(kpis.pm.overdue)} عقب‌افتاده`, kpis.pm.overdue > 0 ? 'danger' : 'success', 'calendar'),
      kpi('دستور کار باز', wo.open ?? 0, `${faNum(wo.in_progress ?? 0)} در اجرا`, (wo.open ?? 0) > 0 ? 'warning' : 'success', 'workorders'),
      kpi('درخواست باز', req.open ?? 0, `${faNum(req.converted ?? 0)} تبدیل‌شده`, 'info', 'requests'),
      kpi('قطعات زیر حد', adv ? adv.critical_parts_low_stock : '—', 'نیازمند تأمین', 'warning', 'parts'));

    // ---- KPI row 2: reliability (§27) ----
    const row2 = adv ? h('div', { class: 'kpi-grid mt-4' },
      kpi('MTBF', adv.mtbf_hours_per_failure != null ? faNum(adv.mtbf_hours_per_failure) : '—', 'ساعت بین خرابی‌ها', 'info', 'calibration'),
      kpi('MTTR', adv.mttr_minutes != null ? faNum(adv.mttr_minutes) : '—', 'دقیقه تعمیر', 'info', 'workorders'),
      kpi('دسترس‌پذیری', pct(adv.availability_pct), '٪', 'success', 'equipment'),
      kpi('کار اضطراری', pct(adv.emergency_pct), 'از کل دستورکارها', 'danger', 'risks'),
      kpi('هزینه نت', Number(adv.maintenance_cost_total || 0).toLocaleString('fa-IR'), 'ریال', 'warning', 'reports'),
      kpi('Backlog', adv.backlog != null ? faNum(adv.backlog) : '—', 'دستورکار معوق', 'warning', 'workorders')) : null;

    // ---- charts ----
    const charts = h('div', { style: 'display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:16px;margin-top:20px' },
      barCard('توزیع اهمیت تجهیزات', kpis.equipment.by_criticality, CRIT_FA),
      barCard('وضعیت دستور کارها', woByStatus(wo), null));

    // ---- tables ----
    const tables = h('div', { style: 'display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:16px;margin-top:20px' },
      tableCard('برنامه‌های نت پیش رو / عقب‌افتاده (۳۰ روز)', ['فعالیت', 'تجهیز', 'سررسید', 'وضعیت'],
        due.items.slice(0, 8).map((p) => [
          h('td', {}, p.work_title),
          h('td', { class: 'small muted' }, p.equipment_name || '—'),
          h('td', { class: 'ltr small' }, toJalaliStr(p.next_due)),
          h('td', {}, p.overdue ? h('span', { class: 'badge danger' }, 'عقب‌افتاده') : h('span', { class: 'badge warning' }, 'پیش رو')),
        ]), () => navigate('#/equipment')),
      tableCard('تجهیزات بحرانی و حساس', ['کد', 'نام', 'اهمیت', 'وضعیت'],
        critical.items.slice(0, 8).map((e) => [
          h('td', { class: 'ltr' }, e.code),
          h('td', {}, e.name),
          h('td', {}, critBadge(e.criticality, CRIT_FA[e.criticality])),
          h('td', {}, statusBadge(e.status)),
        ]), () => navigate('#/equipment')));

    main.replaceChildren(
      h('div', { class: 'page-head' },
        h('div', {}, h('h1', {}, 'داشبورد مدیریت نت'), h('div', { class: 'small faint' }, today)),
        h('div', { class: 'spacer' }),
        h('button', { class: 'btn btn-secondary btn-sm', onclick: () => navigate('#/reports') },
          h('span', { html: icon('reports'), style: 'display:inline-flex;width:14px;height:14px' }), 'گزارش‌ها')),
      row1, row2, charts, tables);
  } catch (e) { renderError(errText(e)); }
}

const pct = (v) => v == null ? '—' : `${faNum(v)}٪`;
function woByStatus(wo) {
  return { 'باز': wo.open ?? 0, 'در اجرا': wo.in_progress ?? 0, 'بسته': wo.closed ?? 0 };
}

function kpi(label, value, sub, tone, ic) {
  return h('div', { class: `kpi ${tone}` },
    ic ? h('span', { class: 'kpi-icon', html: icon(ic) }) : null,
    h('div', { class: 'kpi-label' }, label),
    h('div', { class: 'kpi-value' }, value),
    h('div', { class: 'kpi-sub' }, sub || ''));
}

function barCard(title, data, labelMap) {
  const entries = Object.entries(data || {}).filter(([, v]) => v > 0);
  const max = Math.max(1, ...entries.map(([, v]) => v));
  const colors = ['#1d4ed8', '#dc2626', '#d97706', '#16a34a', '#0891b2', '#64748b'];
  const rows = entries.map(([k, v], i) => h('div', { style: 'margin-bottom:10px' },
    h('div', { style: 'display:flex;justify-content:space-between;font-size:12px', },
      h('span', {}, labelMap ? (labelMap[k] || k) : k), h('span', { class: 'muted' }, faNum(v))),
    h('div', { style: 'background:var(--c-neutral-soft);border-radius:6px;overflow:hidden' },
      h('div', { style: `width:${Math.max(4, v / max * 100)}%;height:10px;border-radius:6px;background:${colors[i % colors.length]}` }))));
  return h('div', { class: 'card' },
    h('div', { class: 'card-head' }, h('h2', {}, title)),
    h('div', { class: 'card-body' }, rows.length ? rows : h('div', { class: 'small faint' }, 'داده‌ای نیست')));
}

function tableCard(title, headers, rows, onAll) {
  const emptyRow = h('tr', {}, h('td', { colspan: String(headers.length) },
    h('div', { class: 'small faint', style: 'text-align:center;padding:16px' }, 'موردی ثبت نشده')));
  const body = rows.length ? rows.map((r) => h('tr', {}, r)) : [emptyRow];
  return h('div', { class: 'card' },
    h('div', { class: 'card-head' }, h('h2', {}, title),
      h('button', { class: 'btn btn-ghost btn-sm', onclick: onAll }, 'همه')),
    h('div', { class: 'table-wrap' }, h('table', { class: 'table' },
      h('thead', {}, h('tr', {}, headers.map((x) => h('th', {}, x)))),
      h('tbody', {}, body))));
}
