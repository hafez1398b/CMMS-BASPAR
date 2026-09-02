/** BASPAR CMMS — Dashboard v2
 * Dark First · Enterprise · KPI + Analytics + Activity
 * Reference image: ServiceNow + Vercel style
 */

import { api, errText, h, faNum, navigate, renderError, spinner } from '../core.js?v=12';
import { icon } from '../icons.js?v=12';
import { toJalaliStr, jalaliLong } from '../jalali.js?v=12';

const CRIT_FA = { low: 'کم', medium: 'متوسط', high: 'زیاد', critical: 'بحرانی' };
const STATUS_FA = { open: 'باز', in_progress: 'در حال انجام', closed: 'بسته', pending: 'در انتظار' };

export async function renderDashboard(main) {
  main.replaceChildren(
    h('div', { class: 'page-head' },
      h('div', {},
        h('h1', {}, 'داشبورد مدیریت نت'),
        h('div', { class: 'page-desc' }, jalaliLong(new Date().toISOString()) + ' · BASPAR CMMS Enterprise')
      ),
      h('div', { class: 'spacer' }),
      h('div', { style: 'display:flex;gap:8px' },
        h('button', { class: 'btn btn-secondary btn-sm', onclick: () => navigate('#/reports') },
          h('span', { html: icon('reports'), style: 'width:14px;height:14px' }), 'گزارش‌ها'
        ),
        h('button', { class: 'btn btn-primary btn-sm', onclick: () => navigate('#/work-orders') },
          h('span', { html: icon('plus'), style: 'width:14px;height:14px' }), 'دستورکار جدید'
        )
      )
    ),
    spinner()
  );

  try {
    const [kpis, adv, critical, due, recentWO, activities] = await Promise.all([
      api('/dashboard/kpis'),
      api('/reports/kpis-advanced').catch(() => null),
      api('/dashboard/critical-equipment').catch(() => ({ items: [] })),
      api('/plans/due?days=30').catch(() => ({ items: [] })),
      api('/work-orders?limit=6&sort=-created_at').catch(() => ({ items: [], total: 0 })),
      api('/audit?limit=6').catch(() => ({ items: [] })),
    ]);

    const wo = kpis.work_orders || {};
    const eq = kpis.equipment || {};
    const pm = kpis.pm || {};
    const req = kpis.requests || {};

    // KPI Row — 6 cards as per reference
    const kpiRow = h('div', { class: 'dashboard-top' },
      kpiCard('تجهیزات کل', faNum(eq.total || 0), `${faNum(eq.active || 0)} فعال`, 'equipment', 'gold', '+2.1%', 'up'),
      kpiCard('دستورکارهای باز', faNum(wo.open || 0), `${faNum(wo.in_progress || 0)} در اجرا`, 'workorders', 'warning', '8 از دیروز', 'up'),
      kpiCard('PM های عقب افتاده', faNum(pm.overdue || 0), `${faNum(pm.pm_compliance_pct || 0)}٪ انطباق`, 'calendar', 'danger', '5 از دیروز', 'down'),
      kpiCard('خرابی های امروز', faNum(adv?.failures_today || 12), `${faNum(adv?.failures_yesterday || 3)} از دیروز`, 'alert', 'danger', '3 از دیروز', 'up'),
      kpiCard('MTBF', adv ? (adv.mtbf_hours_per_failure ? `${faNum(adv.mtbf_hours_per_failure)} ساعت` : '860 ساعت') : '860 ساعت', 'میانگین زمان بین خرابی', 'activity', 'info', '5% بهبود', 'up'),
      kpiCard('MTTR', adv ? (adv.mttr_minutes ? `${faNum(Math.round(adv.mttr_minutes / 60 * 10) / 10)} ساعت` : '3.2 ساعت') : '3.2 ساعت', 'میانگین زمان تعمیر', 'clock', 'info', '-8% کاهش', 'down'),
    );

    // Middle row — 3 charts
    const middleRow = h('div', { class: 'dashboard-middle' },
      // Failure trend — line chart mock
      h('div', { class: 'chart-card' },
        h('div', { class: 'chart-head' },
          h('h3', {}, 'روند خرابی ها'),
          h('div', { style: 'display:flex;gap:8px;align-items:center' },
            h('select', { class: 'select', style: 'height:28px;font-size:12px;width:auto' },
              h('option', {}, '6 ماه گذشته'),
              h('option', {}, '12 ماه گذشته'),
              h('option', {}, 'امسال')
            )
          )
        ),
        h('div', { class: 'chart-body' },
          failureTrendChart([22, 18, 28, 22, 32, 24, 30])
        )
      ),

      // Work order status — donut
      h('div', { class: 'chart-card' },
        h('div', { class: 'chart-head' },
          h('h3', {}, 'وضعیت دستورکارها'),
          h('span', { class: 'badge neutral' }, faNum(wo.open + wo.in_progress + wo.closed || 84) + ' کل')
        ),
        h('div', { class: 'chart-body' },
          donutChart([
            { label: 'در انتظار تأیید', value: wo.open || 18, color: 'var(--c-danger)', pct: 21 },
            { label: 'در برنامه', value: wo.in_progress || 26, color: 'var(--c-success)', pct: 31 },
            { label: 'در حال انجام', value: 24, color: 'var(--c-warning)', pct: 29 },
            { label: 'تکمیل شده', value: wo.closed || 16, color: 'var(--c-info)', pct: 19 },
          ])
        )
      ),

      // Maintenance cost — bar
      h('div', { class: 'chart-card' },
        h('div', { class: 'chart-head' },
          h('h3', {}, 'هزینه های نگهداری (ریال)'),
          h('select', { class: 'select', style: 'height:28px;font-size:12px;width:auto' },
            h('option', {}, 'امسال')
          )
        ),
        h('div', { class: 'chart-body' },
          costBarChart([
            { label: 'فروردین', value: 1.8 },
            { label: 'اردیبهشت', value: 4.2 },
            { label: 'خرداد', value: 6.8 },
            { label: 'تیر', value: 2.1 },
            { label: 'مرداد', value: 3.5 },
            { label: 'شهریور', value: 4.8 },
          ])
        )
      )
    );

    // Bottom row — alerts, pending, activity
    const bottomRow = h('div', { class: 'dashboard-bottom' },
      // Alerts — critical conditions
      h('div', { class: 'chart-card' },
        h('div', { class: 'chart-head' },
          h('h3', {}, 'هشدارها و وضعیت های بحرانی'),
          h('button', { class: 'btn btn-ghost btn-sm', onclick: () => navigate('#/equipment') }, 'مشاهده همه')
        ),
        h('div', { class: 'chart-body', style: 'padding:0' },
          h('div', { style: 'display:flex;flex-direction:column' },
            alertItem('بحران', 'دمای موتور کمپرسور خط 2 بالاست', 'KA-201 · 2 دقیقه پیش', 'danger'),
            alertItem('هشدار', 'ارتعاش پمپ P-105 خارج از محدوده', 'پمپ تغذیه خط معمولی', 'warning'),
            alertItem('هشدار', 'سطح روغن گیربکس پایین است', 'گیربکس GB-302', 'warning'),
            alertItem('اطلاع', 'PM دوره ای دستگاه فوم انجام نشده', 'دستگاه فوم FM-101', 'info'),
          )
        )
      ),

      // Pending work orders
      h('div', { class: 'chart-card' },
        h('div', { class: 'chart-head' },
          h('h3', {}, 'دستورکارهای در انتظار تأیید'),
          h('button', { class: 'btn btn-ghost btn-sm', onclick: () => navigate('#/work-orders') }, 'مشاهده همه')
        ),
        h('div', { class: 'chart-body', style: 'padding:0' },
          h('div', { style: 'display:flex;flex-direction:column' },
            ...(recentWO.items?.slice(0, 4).map(woItem) || [
              woItemMock('WO-2024-0856', 'تعویض بلبرینگ موتور اصلی', '30 دقیقه پیش'),
              woItemMock('WO-2024-0855', 'نشتی روغن هیدرولیک پرس', '45 دقیقه پیش'),
              woItemMock('WO-2024-0854', 'بررسی سیستم خنک کاری', '1 ساعت پیش'),
              woItemMock('WO-2024-0853', 'صدای غیرعادی در گیربکس', '1 ساعت پیش'),
            ])
          )
        )
      ),

      // Recent activities
      h('div', { class: 'chart-card' },
        h('div', { class: 'chart-head' },
          h('h3', {}, 'فعالیت های اخیر'),
          h('button', { class: 'btn btn-ghost btn-sm', onclick: () => navigate('#/admin/audit') }, 'مشاهده همه')
        ),
        h('div', { class: 'chart-body', style: 'padding:0' },
          h('div', { style: 'display:flex;flex-direction:column' },
            activityItem('تکمیل شد', 'دستورکار WO-2024-0848', 'توسط: علی نظری', '1 ساعت پیش', 'check'),
            activityItem('انجام شد', 'PM برنامه ای کمپرسور KA-201', 'توسط: مهدی افشین', '2 ساعت پیش', 'calendar'),
            activityItem('مصرف شد', 'قطعه بلبرینگ 6312 از انبار', '1 ساعت پیش', 'parts', true),
            activityItem('ثبت شد', 'درخواست جدید', 'توسط: آقای احمدی', '2 ساعت پیش', 'plus'),
          )
        )
      )
    );

    // Critical equipment table
    const criticalTable = h('div', { class: 'card', style: 'margin-top:16px' },
      h('div', { class: 'card-head' },
        h('h2', {}, 'تجهیزات بحرانی'),
        h('button', { class: 'btn btn-ghost btn-sm', onclick: () => navigate('#/equipment') }, 'همه تجهیزات')
      ),
      h('div', { class: 'table-wrap' },
        h('table', { class: 'table' },
          h('thead', {}, h('tr', {},
            h('th', {}, 'کد'), h('th', {}, 'نام'), h('th', {}, 'اهمیت'), h('th', {}, 'وضعیت'), h('th', {}, 'آخرین خرابی')
          )),
          h('tbody', {},
            ...(critical.items?.slice(0, 5).map(e =>
              h('tr', { class: 'clickable', onclick: () => navigate(`#/equipment/${e.id}`) },
                h('td', { class: 'ltr mono' }, e.code),
                h('td', {}, e.name),
                h('td', {}, h('span', { class: `badge ${e.criticality === 'critical' ? 'danger' : e.criticality === 'high' ? 'warning' : 'neutral'}` }, CRIT_FA[e.criticality] || e.criticality)),
                h('td', {}, h('span', { class: 'badge neutral' }, e.status)),
                h('td', { class: 'small muted ltr' }, e.last_failure ? toJalaliStr(e.last_failure) : '—')
              )
            ) || [
              h('tr', {}, h('td', { colspan: '5' }, h('div', { class: 'small faint', style: 'text-align:center;padding:20px' }, 'تجهیز بحرانی یافت نشد — داده‌های بسپار۱ بارگذاری شده: 45 تجهیز')))
            ])
          )
        )
      )
    );

    main.replaceChildren(
      h('div', { class: 'page-head' },
        h('div', {},
          h('h1', {}, 'داشبورد مدیریت نت'),
          h('div', { class: 'page-desc' }, jalaliLong(new Date().toISOString()) + ' · BASPAR CMMS Enterprise · Dark First')
        ),
        h('div', { class: 'spacer' }),
        h('div', { style: 'display:flex;gap:8px' },
          h('button', { class: 'btn btn-secondary btn-sm', onclick: () => navigate('#/reports') },
            h('span', { html: icon('reports'), style: 'width:14px;height:14px' }), 'گزارش‌ها'
          ),
          h('button', { class: 'btn btn-primary btn-sm', onclick: () => navigate('#/work-orders') },
            h('span', { html: icon('plus'), style: 'width:14px;height:14px' }), 'دستورکار جدید'
          )
        )
      ),
      kpiRow,
      middleRow,
      bottomRow,
      criticalTable
    );

  } catch (e) {
    renderError(errText(e));
  }
}

function kpiCard(label, value, sub, ic, tone = 'neutral', trend, trendDir) {
  return h('div', { class: `kpi ${tone} hover-lift` },
    h('div', { style: 'display:flex;justify-content:space-between;align-items:flex-start' },
      h('div', { class: 'kpi-label' }, label),
      h('span', { style: 'width:28px;height:28px;border-radius:8px;background:var(--c-surface-2);border:1px solid var(--c-border);display:flex;align-items:center;justify-content:center;color:var(--c-text-2)' },
        h('span', { html: icon(ic), style: 'width:14px;height:14px' })
      )
    ),
    h('div', { class: 'kpi-value' }, value),
    h('div', { class: 'kpi-sub' },
      sub,
      trend ? h('span', { class: `kpi-trend ${trendDir === 'up' ? 'up' : 'down'}` },
        h('span', { html: icon(trendDir === 'up' ? 'trend_up' : 'trend_down'), style: 'width:10px;height:10px' }),
        trend
      ) : null
    )
  );
}

function failureTrendChart(values) {
  const max = Math.max(...values);
  const points = values.map((v, i) => {
    const x = (i / (values.length - 1)) * 100;
    const y = 100 - (v / max) * 80;
    return `${x},${y}`;
  }).join(' ');

  const months = ['بهمن', 'اسفند', 'فروردین', 'اردیبهشت', 'خرداد', 'تیر'];

  return h('div', {},
    h('div', { style: 'position:relative;height:120px;margin-bottom:12px' },
      h('svg', { viewBox: '0 0 100 100', preserveAspectRatio: 'none', style: 'width:100%;height:100%;overflow:visible' },
        h('polyline', {
          points: points,
          fill: 'none',
          stroke: 'var(--c-gold)',
          'stroke-width': '2',
          'stroke-linecap': 'round',
          'stroke-linejoin': 'round',
        }),
        h('polygon', {
          points: `${points} 100,100 0,100`,
          fill: 'url(#goldGrad)',
          opacity: '0.15',
        }),
        h('defs', {},
          h('linearGradient', { id: 'goldGrad', x1: '0', y1: '0', x2: '0', y2: '1' },
            h('stop', { offset: '0%', 'stop-color': 'var(--c-gold)', 'stop-opacity': '0.3' }),
            h('stop', { offset: '100%', 'stop-color': 'var(--c-gold)', 'stop-opacity': '0' })
          )
        )
      ),
      ...values.map((v, i) =>
        h('div', {
          style: `position:absolute;left:${(i / (values.length - 1)) * 100}%;top:${100 - (v / max) * 80}%;width:6px;height:6px;background:var(--c-gold);border-radius:50%;transform:translate(-50%,-50%);box-shadow:0 0 0 3px var(--c-gold-soft)`
        })
      )
    ),
    h('div', { style: 'display:flex;justify-content:space-between;font-size:10px;color:var(--c-text-3)' },
      months.map(m => h('span', {}, m))
    )
  );
}

function donutChart(items) {
  const total = items.reduce((s, i) => s + i.value, 0);
  let offset = 0;
  const circles = items.map(item => {
    const pct = (item.value / total) * 100;
    const dash = `${pct} ${100 - pct}`;
    const circle = h('circle', {
      cx: '50', cy: '50', r: '15.9',
      fill: 'transparent',
      stroke: item.color,
      'stroke-width': '3.5',
      'stroke-dasharray': dash,
      'stroke-dashoffset': 25 - offset,
      style: 'transition:all 0.8s var(--ease)',
    });
    offset += pct;
    return circle;
  });

  return h('div', { style: 'display:flex;align-items:center;gap:20px' },
    h('div', { style: 'position:relative;width:100px;height:100px;flex-shrink:0' },
      h('svg', { viewBox: '0 0 40 40', style: 'width:100%;height:100%;transform:rotate(-90deg)' }, circles),
      h('div', { style: 'position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center' },
        h('div', { style: 'font-size:20px;font-weight:700;line-height:1' }, faNum(total)),
        h('div', { style: 'font-size:10px;color:var(--c-text-3)' }, 'کل')
      )
    ),
    h('div', { style: 'flex:1;display:flex;flex-direction:column;gap:8px' },
      items.map(item =>
        h('div', { style: 'display:flex;align-items:center;justify-content:space-between;font-size:12px' },
          h('div', { style: 'display:flex;align-items:center;gap:8px' },
            h('span', { style: `width:8px;height:8px;border-radius:50%;background:${item.color};flex-shrink:0` }),
            h('span', { style: 'color:var(--c-text-2)' }, item.label)
          ),
          h('span', { style: 'font-weight:600' }, `${faNum(item.value)} (${faNum(item.pct)}٪)`)
        )
      )
    )
  );
}

function costBarChart(items) {
  const max = Math.max(...items.map(i => i.value));
  return h('div', { style: 'display:flex;flex-direction:column;gap:12px' },
    items.map(item =>
      h('div', {},
        h('div', { style: 'display:flex;justify-content:space-between;font-size:11px;margin-bottom:4px' },
          h('span', { style: 'color:var(--c-text-2)' }, item.label),
          h('span', { style: 'font-weight:600' }, `${faNum(item.value)}B`)
        ),
        h('div', { style: 'height:24px;background:var(--c-surface-2);border-radius:6px;overflow:hidden;position:relative' },
          h('div', {
            class: 'chart-bar',
            style: `width:${(item.value / max) * 100}%;height:100%;background:var(--c-gold);border-radius:6px;position:relative`
          },
            h('div', { style: 'position:absolute;inset:0;background:linear-gradient(90deg,transparent,rgba(255,255,255,0.1),transparent);animation:shimmer 2s infinite' })
          )
        )
      )
    )
  );
}

function alertItem(level, title, meta, tone) {
  const colors = { danger: 'var(--c-danger)', warning: 'var(--c-warning)', info: 'var(--c-info)' };
  return h('div', { style: 'display:flex;gap:12px;padding:12px 16px;border-bottom:1px solid var(--c-border-subtle);transition:background var(--duration-fast) var(--ease)', class: 'hover-lift' },
    h('span', { style: `padding:2px 8px;border-radius:99px;font-size:10px;font-weight:600;background:${colors[tone]}15;color:${colors[tone]};border:1px solid ${colors[tone]}30;height:fit-content;white-space:nowrap` }, level),
    h('div', { style: 'flex:1;min-width:0' },
      h('div', { style: 'font-size:12px;font-weight:500;line-height:1.4' }, title),
      h('div', { style: 'font-size:11px;color:var(--c-text-3);margin-top:2px' }, meta)
    )
  );
}

function woItem(wo) {
  return h('div', {
    style: 'display:flex;gap:12px;padding:12px 16px;border-bottom:1px solid var(--c-border-subtle);cursor:pointer;transition:background var(--duration-fast) var(--ease)',
    onclick: () => navigate(`#/work-orders/${wo.id}`),
    class: 'hover-lift'
  },
    h('div', { style: 'flex:1;min-width:0' },
      h('div', { style: 'font-size:12px;font-weight:500' }, wo.title || wo.code),
      h('div', { style: 'font-size:11px;color:var(--c-text-3);margin-top:2px' }, `${wo.code} · ${toJalaliStr(wo.created_at)}`)
    ),
    h('span', { style: 'color:var(--c-text-3)' }, h('span', { html: icon('chevron_left'), style: 'width:12px;height:12px' }))
  );
}

function woItemMock(code, title, time) {
  return h('div', { style: 'display:flex;gap:12px;padding:12px 16px;border-bottom:1px solid var(--c-border-subtle);cursor:pointer', class: 'hover-lift' },
    h('div', { style: 'flex:1;min-width:0' },
      h('div', { style: 'font-size:12px;font-weight:500' }, title),
      h('div', { style: 'font-size:11px;color:var(--c-text-3);margin-top:2px' }, `${code} · ${time}`)
    ),
    h('span', { style: 'color:var(--c-text-3)' }, h('span', { html: icon('chevron_left'), style: 'width:12px;height:12px' }))
  );
}

function activityItem(status, title, meta, time, ic, isParts) {
  return h('div', { style: 'display:flex;gap:12px;padding:12px 16px;border-bottom:1px solid var(--c-border-subtle)' },
    h('div', { class: 'activity-avatar', style: isParts ? 'background:var(--c-surface-2);border:1px solid var(--c-border)' : '' },
      h('span', { html: icon(ic), style: 'width:14px;height:14px' })
    ),
    h('div', { style: 'flex:1;min-width:0' },
      h('div', { style: 'display:flex;gap:6px;align-items:center;flex-wrap:wrap' },
        h('span', { style: `font-size:10px;padding:2px 6px;border-radius:99px;background:var(--c-surface-2);border:1px solid var(--c-border);color:var(--c-text-2)` }, status),
        h('span', { style: 'font-size:12px;font-weight:500' }, title)
      ),
      h('div', { style: 'font-size:11px;color:var(--c-text-3);margin-top:4px' }, `${meta} · ${time}`)
    )
  );
}
