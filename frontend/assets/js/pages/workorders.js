/** BASPAR CMMS — Work Orders v2
 * Dark First · Enterprise Workflow
 * Request → AI Analysis → Approval → Assignment → In Progress → Completed → Closed
 */

import {
  api, errText, h, faNum, toast, navigate, spinner, table, pager, Session, openModal,
} from '../core.js?v=12';
import { toJalaliStr } from '../jalali.js?v=12';
import { icon } from '../icons.js?v=12';

export const WO_STATUS = {
  created: ['neutral', 'ایجاد شده', 'var(--c-neutral)'],
  pending_permit: ['warning', 'در انتظار Permit/HSE', 'var(--c-warning)'],
  ready: ['info', 'آماده اجرا', 'var(--c-info)'],
  in_progress: ['gold', 'در حال اجرا', 'var(--c-gold)'],
  paused: ['warning', 'توقف موقت', 'var(--c-warning)'],
  awaiting_confirmation: ['warning', 'در انتظار تأیید', 'var(--c-warning)'],
  final_approval: ['info', 'در انتظار تأیید نهایی', 'var(--c-info)'],
  closed: ['success', 'بسته شده', 'var(--c-success)'],
  rejected: ['danger', 'رد شده', 'var(--c-danger)'],
  cancelled: ['neutral', 'لغو شده', 'var(--c-neutral)'],
  open: ['warning', 'باز', 'var(--c-warning)'],
};

const PRIO_BADGE = { low: 'neutral', normal: 'info', high: 'warning', emergency: 'danger' };

export async function renderWorkOrders(main) {
  let page = 1, statusFilter = '', q = '';
  main.replaceChildren(
    h('div', { class: 'page-head' },
      h('div', {},
        h('h1', {}, 'دستور کارها'),
        h('div', { class: 'page-desc' }, 'Workflow: درخواست → تحلیل AI → تأیید → تخصیص → اجرا → تکمیل')
      ),
      spinner()
    )
  );

  const statusSel = h('select', { class: 'select', style: 'max-width:200px;height:36px' },
    h('option', { value: '' }, 'همه وضعیت‌ها'),
    ...Object.entries(WO_STATUS).map(([k, v]) => h('option', { value: k }, v[1]))
  );
  statusSel.onchange = () => { statusFilter = statusSel.value; page = 1; load(); };

  const search = h('input', {
    class: 'input',
    placeholder: 'جستجو: کد، عنوان، تجهیز...',
    style: 'max-width:280px;height:36px'
  });
  let t = null;
  search.addEventListener('input', () => {
    clearTimeout(t);
    t = setTimeout(() => { q = search.value.trim(); page = 1; load(); }, 300);
  });

  async function load() {
    try {
      const qs = new URLSearchParams({ page, page_size: 25 });
      if (statusFilter) qs.set('status', statusFilter);
      if (q) qs.set('q', q);
      const data = await api(`/work-orders?${qs}`);

      // Workflow progress bar for top
      const workflow = h('div', { class: 'card', style: 'padding:16px;margin-bottom:16px' },
        h('div', { style: 'display:flex;align-items:center;gap:8px;overflow-x:auto' },
          ['درخواست', 'تحلیل AI', 'اولویت', 'تأیید', 'تخصیص', 'در حال انجام', 'بازرسی', 'تعمیر', 'تست', 'تکمیل', 'بسته'].map((step, i) =>
            h('div', { style: 'display:flex;align-items:center;gap:8px;flex-shrink:0' },
              h('div', {
                style: `width:28px;height:28px;border-radius:50%;background:${i < 5 ? 'var(--c-gold)' : 'var(--c-surface-2)'};border:1px solid ${i < 5 ? 'var(--c-gold)' : 'var(--c-border)'};color:${i < 5 ? '#0A0A0A' : 'var(--c-text-3)'};display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700`
              }, i + 1),
              h('span', { style: `font-size:11px;color:${i < 5 ? 'var(--c-text)' : 'var(--c-text-3)'};white-space:nowrap` }, step),
              i < 10 ? h('span', { style: 'width:24px;height:1px;background:var(--c-border);margin:0 4px' }) : null
            )
          )
        )
      );

      const rows = data.items.map(w => {
        const st = WO_STATUS[w.status] || ['neutral', w.status, 'var(--c-neutral)'];
        return h('tr', { class: 'clickable', onclick: () => navigate(`#/work-orders/${w.id}`) },
          h('td', {},
            h('div', { style: 'display:flex;align-items:center;gap:8px' },
              h('span', { style: `width:6px;height:6px;border-radius:50%;background:${st[2]};flex-shrink:0` }),
              h('span', { class: 'mono small ltr' }, w.code)
            )
          ),
          h('td', {}, h('div', { style: 'font-weight:500;max-width:260px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap' }, w.title)),
          h('td', { class: 'small' }, w.equipment_name || h('span', { class: 'faint' }, '—')),
          h('td', {}, h('span', { class: `badge ${st[0]}` }, st[1])),
          h('td', {}, h('span', { class: `badge ${PRIO_BADGE[w.priority] || 'neutral'}` }, w.priority)),
          h('td', { class: 'small' }, w.assignee_name || h('span', { class: 'faint' }, '—')),
          h('td', { class: 'small' }, w.duration_minutes ? `${faNum(w.duration_minutes)} دقیقه` : '—'),
          h('td', { class: 'small ltr' }, toJalaliStr(w.created_at, true))
        );
      });

      main.replaceChildren(
        h('div', { class: 'page-head' },
          h('div', {},
            h('h1', {}, 'دستور کارها'),
            h('div', { class: 'page-desc' }, `${faNum(data.total)} دستورکار · Workflow Enterprise`)
          ),
          h('div', { class: 'spacer' }),
          search,
          statusSel,
          Session.can('workorders.create') ? h('button', { class: 'btn btn-primary btn-sm', onclick: createModal },
            h('span', { html: icon('plus'), style: 'width:14px;height:14px' }), 'دستورکار جدید'
          ) : null
        ),
        workflow,
        h('div', { class: 'card' },
          h('div', { class: 'table-wrap' },
            table(['کد', 'عنوان', 'تجهیز', 'وضعیت', 'اولویت', 'تکنسین', 'مدت', 'تاریخ'], rows)
          )
        ),
        h('div', { style: 'display:flex;justify-content:center;margin-top:16px' },
          pager(page, data.total, 25, p => { page = p; load(); })
        )
      );
    } catch (e) {
      toast(errText(e), 'danger');
    }
  }

  async function createModal() {
    let equipment = [];
    try { equipment = (await api('/equipment?page_size=200&level=equipment')).items; } catch {}

    const title = h('input', { class: 'input', placeholder: 'مثال: تعویض بلبرینگ موتور اصلی' });
    const desc = h('textarea', { class: 'textarea', placeholder: 'شرح خرابی...' });
    const eqSel = h('select', { class: 'select' },
      h('option', { value: '' }, 'انتخاب تجهیز (اختیاری)'),
      ...equipment.map(e => h('option', { value: String(e.id) }, `${e.code} — ${e.name}`))
    );
    const prioSel = h('select', { class: 'select' },
      h('option', { value: 'normal' }, 'عادی'),
      h('option', { value: 'high' }, 'زیاد'),
      h('option', { value: 'emergency' }, 'اضطراری'),
      h('option', { value: 'low' }, 'کم')
    );

    const saveBtn = h('button', { class: 'btn btn-primary' }, 'ایجاد دستورکار');

    const m = openModal({
      title: 'دستورکار جدید — Workflow Enterprise',
      body: h('div', { class: 'form-grid' },
        h('div', { class: 'field span-2' }, h('label', {}, 'عنوان *'), title),
        h('div', { class: 'field' }, h('label', {}, 'تجهیز'), eqSel),
        h('div', { class: 'field' }, h('label', {}, 'اولویت'), prioSel),
        h('div', { class: 'field span-2' }, h('label', {}, 'شرح خرابی'), desc),
        h('div', { class: 'field span-2', style: 'background:var(--c-gold-soft);border:1px solid var(--c-gold-border);border-radius:8px;padding:12px' },
          h('div', { style: 'display:flex;gap:8px;align-items:center;font-size:12px;color:var(--c-gold)' },
            h('span', { html: icon('sparkles'), style: 'width:14px;height:14px' }),
            h('span', { style: 'font-weight:600' }, 'SELEN AI به صورت خودکار علت احتمالی و قطعات مورد نیاز را پیشنهاد می‌دهد')
          )
        )
      ),
      footer: [saveBtn],
      size: 'modal-lg'
    });

    saveBtn.onclick = async () => {
      if (!title.value.trim()) { toast('عنوان الزامی است', 'warning'); return; }
      try {
        const wo = await api('/work-orders', {
          method: 'POST',
          body: {
            title: title.value.trim(),
            description: desc.value || null,
            equipment_id: eqSel.value ? +eqSel.value : null,
            priority: prioSel.value,
            permit_required: false,
          }
        });
        toast(`دستورکار ${wo.code} ایجاد شد`, 'success');
        m.close();
        navigate(`#/work-orders/${wo.id}`);
      } catch (e) { toast(errText(e), 'danger'); }
    };
  }

  await load();
}
