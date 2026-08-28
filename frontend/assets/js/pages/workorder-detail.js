/** Work Order detail — full §18 workflow UI + §19 permit + §20 execution
 *  with §20B offline queueing. */
import {
  api, errText, h, faNum, toast, openModal, confirmDialog, spinner,
  Session, navigate, fmtBytes, downloadUrl,
} from '../core.js?v=11';
import { toJalaliStr } from '../jalali.js?v=11';
import { WO_STATUS } from './workorders.js?v=11';
import { enqueue, offlineQueue, flushQueue, pendingCount } from '../offline.js?v=11';
import { addVoiceInput } from '../voice.js?v=11';

const PRIO_BADGE = { low: 'neutral', normal: 'info', high: 'warning', emergency: 'danger' };

export async function renderWorkOrderDetail(main, id) {
  main.replaceChildren(spinner());
  let wo;
  try { wo = await api(`/work-orders/${id}`); }
  catch (e) { main.replaceChildren(h('div', { class: 'card' }, h('div', { class: 'card-body' }, '⚠️ ', errText(e)))); return; }

  const st = WO_STATUS[wo.status] || ['neutral', wo.status];
  const header = h('div', { class: 'page-head' },
    h('div', { class: 'breadcrumb' }, h('a', { href: '#/work-orders' }, 'دستور کارها'), '‹', h('span', { class: 'ltr' }, wo.code)),
    h('div', { class: 'spacer' }),
    h('h1', {}, wo.title),
    h('span', { class: `badge ${st[0]}` }, st[1]),
    h('span', { class: `badge ${PRIO_BADGE[wo.priority] || 'neutral'}` }, wo.priority),
    wo.equipment_id
      ? h('a', { class: 'btn btn-ghost btn-sm', href: `#/equipment/${wo.equipment_id}` }, `تجهیز: ${wo.equipment_code || ''} ${wo.equipment_name || ''}`)
      : null);

  const body = h('div', {}, spinner());
  main.replaceChildren(header, body);
  draw();

  async function refresh() {
    wo = await api(`/work-orders/${id}`);
    draw();
  }

  function draw() {
    const offlineItems = offlineQueue().filter((i) => String(i.woid) === String(wo.id));
    body.replaceChildren(
      workflowBar(),
      offlineItems.length
        ? h('div', { class: 'card mb-4', style: 'border-color:var(--c-warning)' },
            h('div', { class: 'card-body small' },
              `⏳ ${faNum(offlineItems.length)} رکورد آفلاین در صف همگام‌سازی این دستگاه نگهداری می‌شود (FIFO). `,
              h('button', { class: 'btn btn-secondary btn-sm', style: 'margin-inline-start:8px', onclick: async () => {
                const res = await flushQueue();
                toast(`همگام‌سازی: ${faNum(res.sent)} رکورد اعمال شد${res.conflicts ? ` · ${faNum(res.conflicts)} تعارض به مدیر اعلام شد` : ''}`, res.conflicts ? 'warning' : 'success');
                refresh();
              } }, 'همگام‌سازی اکنون')))
        : null,
      h('div', { style: 'display:grid;grid-template-columns:repeat(auto-fit,minmax(360px,1fr));gap:16px' },
        permitPanel(), executionPanel(), infoPanel()));
  }

  /* ---------- workflow actions ---------- */
  function workflowBar() {
    const bar = h('div', { class: 'toolbar' });
    const canManage = Session.can('workorders.manage');
    const me = Session.user;
    const isAssignee = wo.assigned_to && me && wo.assigned_to === me.id;

    if (canManage && ['created', 'pending_permit', 'ready'].includes(wo.status)) {
      bar.append(h('button', { class: 'btn btn-secondary', onclick: setupModal }, '⚙ پیکربندی (تخصیص/Permit)'));
    }
    if (canManage && wo.status === 'final_approval') {
      bar.append(h('button', { class: 'btn btn-primary', onclick: async () => {
        if (!await confirmDialog('با تأیید نهایی، این کار در سوابق نت تجهیز ثبت می‌شود.')) return;
        try { await api(`/work-orders/${wo.id}/final-approve`, { method: 'POST', body: { approve: true, version: wo.version } }); toast('تأیید نهایی شد', 'success'); refresh(); }
        catch (e) { toast(e.status === 409 ? 'تعارض نسخه — صفحه تازه شد' : errText(e), 'danger'); refresh(); }
      } }, '✔ تأیید نهایی و بستن'));
    }
    if (Session.can('workorders.confirm') && wo.status === 'awaiting_confirmation') {
      bar.append(
        h('button', { class: 'btn btn-primary', onclick: async () => {
          try { await api(`/work-orders/${wo.id}/confirm`, { method: 'POST', body: { approve: true, version: wo.version } }); toast('نتیجه کار تأیید شد', 'success'); refresh(); }
          catch (e) { toast(errText(e), 'danger'); refresh(); }
        } }, '✔ تأیید انجام کار'),
        h('button', { class: 'btn btn-danger', onclick: async () => {
          try { await api(`/work-orders/${wo.id}/confirm`, { method: 'POST', body: { approve: false, version: wo.version, note: 'مورد تأیید نیست' } }); toast('برای اصلاح به تکنسین بازگشت', 'warning'); refresh(); }
          catch (e) { toast(errText(e), 'danger'); refresh(); }
        } }, '✖ عدم تأیید'));
    }
    bar.append(h('span', { class: 'small faint' }, `نسخه: ${faNum(wo.version)} · مدت اجرا: ${faNum(wo.duration_minutes || 0)} دقیقه`));
    return bar;
  }

  /* ---------- setup modal ---------- */
  function setupModal() {
    let users = [];
    api('/users').then((d) => users = d.items).catch(() => { });
    const assignSel = h('select', { class: 'select' }, h('option', { value: '' }, 'در حال بارگذاری…'));
    setTimeout(async () => {
      try { users = (await api('/users')).items; } catch { users = []; }
      assignSel.replaceChildren(
        h('option', { value: '' }, 'بدون تخصیص'),
        ...users.map((u) => h('option', { value: String(u.id), selected: u.id === wo.assigned_to }, `${u.full_name} (${u.username})`)));
    }, 0);
    const permitChk = h('input', { type: 'checkbox', ...(wo.permit_required ? { checked: true } : {}) });
    const saveBtn = h('button', { class: 'btn btn-primary' }, 'ذخیره پیکربندی');
    const m = openModal({
      title: `پیکربندی ${wo.code}`,
      body: h('div', { class: 'form-grid' },
        h('div', { class: 'field span-2' }, h('label', {}, 'تکنسین مسئول'), assignSel),
        h('div', { class: 'field' }, h('label', {}, 'نیازمند Permit/HSE (§19)'), permitChk),
        h('div', { class: 'field' }, h('label', {}, 'حالت اجرا'),
          h('select', { class: 'select', id: 'exec-mode' },
            h('option', { value: 'internal', selected: wo.execution_mode === 'internal' }, 'داخلی'),
            h('option', { value: 'external', selected: wo.execution_mode === 'external' }, 'پیمانکار خارجی'))),
        h('div', { class: 'small faint span-2' }, 'در صورت فعال بودن Permit، تأییدکنندگان به‌صورت خودکار از نقش‌های سرپرست/مدیر فنی/مدیر نت ایجاد می‌شوند.')),
      footer: [saveBtn],
    });
    saveBtn.onclick = async () => {
      try {
        await api(`/work-orders/${wo.id}/setup`, { method: 'PUT', body: {
          title: wo.title, permit_required: permitChk.checked,
          assigned_to: assignSel.value ? +assignSel.value : null,
          approver_ids: [], execution_mode: m.modal.querySelector('#exec-mode').value,
          priority: wo.priority, version: wo.version,
        } });
        toast('پیکربندی ذخیره شد', 'success'); m.close(); refresh();
      } catch (e) { toast(e.status === 409 ? 'تعارض نسخه' : errText(e), 'danger'); }
    };
  }

  /* ---------- permit panel ---------- */
  function permitPanel() {
    const approvals = wo.approvals || [];
    const rows = approvals.length ? approvals.map((a) => h('div', { class: 'kv-row' },
      h('span', { style: 'flex:1' }, a.approver_name || `#${a.approver_id}`),
      a.status === 'pending'
        ? (Session.user && a.approver_id === Session.user.id
            ? h('span', {},
                h('button', { class: 'btn btn-primary btn-sm', style: 'margin-inline-end:6px', onclick: () => decide(a.id, true) }, 'تأیید'),
                h('button', { class: 'btn btn-danger btn-sm', onclick: () => decide(a.id, false) }, 'رد'))
            : h('span', { class: 'badge warning' }, 'در انتظار'))
        : h('span', { class: `badge ${a.status === 'approved' ? 'success' : 'danger'}` },
            a.status === 'approved' ? 'تأیید شده' : 'رد شده'),
      h('span', { class: 'small faint ltr' }, toJalaliStr(a.decided_at, true))))
      : h('div', { class: 'small faint' }, 'Permit تعریف نشده است.');

    async function decide(aid, approve) {
      try {
        await api(`/work-orders/approvals/${aid}/decide`, { method: 'POST',
          body: { approve, comment: null, signature: `web:${Session.user?.username}` } });
        toast(approve ? 'تأیید Permit ثبت شد' : 'Permit رد شد', approve ? 'success' : 'warning');
        refresh();
      } catch (e) { toast(errText(e), 'danger'); }
    }

    return h('div', { class: 'card' },
      h('div', { class: 'card-head' }, h('h2', {}, 'Permit / HSE (§19)')),
      h('div', { class: 'card-body' }, rows));
  }

  /* ---------- execution panel (§20 + §20B) ---------- */
  function executionPanel() {
    const me = Session.user;
    const isAssignee = wo.assigned_to && me && wo.assigned_to === me.id;
    const canExec = Session.can('workorders.execute') && isAssignee;
    const btns = h('div', { class: 'chip-row' });

    function exec(action) {
      return async () => {
        if (!navigator.onLine) {
          enqueue(wo.id, { type: 'time_log', action });
          toast('آفلاین: کنش در صف دستگاه ذخیره شد و پس از اتصال ارسال می‌شود', 'warning');
          draw();
          return;
        }
        try {
          await api(`/work-orders/${wo.id}/execution`, { method: 'POST',
            body: { action, base_version: wo.version } });
          toast({ start: 'اجرا شروع شد', pause: 'اجرا موقتاً متوقف شد', resume: 'اجرا ادامه یافت', finish: 'اجرا پایان یافت — در انتظار تأیید درخواست‌دهنده' }[action], 'success');
          refresh();
        } catch (e) {
          if (e.status === 409) { toast('نسخه سرور جدیدتر است — صفحه تازه‌سازی شد', 'warning'); refresh(); }
          else toast(errText(e), 'danger');
        }
      };
    }

    if (canExec) {
      if (wo.status === 'ready') btns.append(h('button', { class: 'btn btn-primary', onclick: exec('start') }, '▶ شروع اجرا'));
      if (wo.status === 'in_progress') {
        btns.append(h('button', { class: 'btn btn-secondary', onclick: exec('pause') }, '⏸ توقف موقت'));
        btns.append(h('button', { class: 'btn btn-primary', onclick: exec('finish') }, '⏹ پایان اجرا'));
      }
      if (wo.status === 'paused') {
        btns.append(h('button', { class: 'btn btn-primary', onclick: exec('resume') }, '▶ ادامه'));
        btns.append(h('button', { class: 'btn btn-secondary', onclick: exec('finish') }, '⏹ پایان اجرا'));
      }
    } else {
      btns.append(h('span', { class: 'small faint' },
        !wo.assigned_to ? 'تکنسین تخصیص نیافته است.' :
        !isAssignee ? 'اجرا فقط توسط تکنسین محول‌شده انجام می‌شود.' : ''));
    }

    // note composer — text with Voice→Text (§38)
    const noteInp = h('textarea', { class: 'textarea', placeholder: 'ثبت گزارش اجرا (متن یا صوت 🎤)…' });
    const micBtn = addVoiceInput(noteInp, async (file) => {
      const fd = new FormData(); fd.append('file', file);
      try {
        await api(`/work-orders/${wo.id}/files`, { method: 'POST', form: fd });
        toast('یادداشت صوتی به پیوست‌های دستور کار اضافه شد', 'success');
        refresh();
      } catch (e) { toast(errText(e), 'danger'); }
    });
    const noteBtn = h('button', { class: 'btn btn-secondary btn-sm mt-2', onclick: async () => {
      const text = noteInp.value.trim();
      if (!text) return;
      if (!navigator.onLine) {
        enqueue(wo.id, { type: 'note', text });
        noteInp.value = '';
        toast('آفلاین: یادداشت در صف دستگاه ذخیره شد', 'warning'); draw(); return;
      }
      try {
        await api(`/work-orders/${wo.id}/notes`, { method: 'POST', body: { text, base_version: wo.version } });
        noteInp.value = ''; refresh();
      } catch (e) { toast(errText(e), 'danger'); }
    } }, 'ثبت یادداشت');

    const timeline = (wo.time_logs || []).slice().reverse().map((t) =>
      h('div', { class: 'small', style: 'display:flex;gap:8px;padding:3px 0' },
        h('span', { class: 'badge neutral' }, { start: 'شروع', pause: 'توقف', resume: 'ادامه', finish: 'پایان' }[t.action] || t.action),
        h('span', { class: 'muted' }, t.user_name || ''),
        h('span', { class: 'faint ltr', style: 'margin-inline-start:auto' }, toJalaliStr(t.at, true))));

    return h('div', { class: 'card' },
      h('div', { class: 'card-head' }, h('h2', {}, 'اجرای تکنسین (§20)'),
        h('span', { class: 'small faint' }, wo.assignee_name ? `محول به: ${wo.assignee_name}` : '')),
      h('div', { class: 'card-body' },
        btns,
        h('hr', { class: 'hr' }),
        h('div', {}, noteInp, micBtn), noteBtn,
        timeline.length ? h('hr', { class: 'hr' }) : null,
        h('div', {}, timeline)));
  }

  /* ---------- info panel: notes / files / costs ---------- */
  function infoPanel() {
    const notes = (wo.notes || []).map((n) => h('div', { class: 'small', style: 'padding:4px 0' },
      h('div', {}, n.text),
      h('div', { class: 'faint' }, `${n.user_name || ''} · ${toJalaliStr(n.created_at, true)}`)));

    const files = (wo.files || []).map((f) => h('div', { class: 'kv-row' },
      h('span', { style: 'flex:1' }, f.name),
      h('span', { class: 'small faint' }, fmtBytes(f.size)),
      h('button', { class: 'btn btn-ghost btn-sm', onclick: () => downloadUrl(`/files/${f.id}/download`) }, 'دانلود')));

    const fileInput = h('input', { type: 'file', style: 'display:none' });
    fileInput.onchange = async () => {
      const f = fileInput.files[0];
      if (!f) return;
      const fd = new FormData(); fd.append('file', f);
      try { await api(`/work-orders/${wo.id}/files`, { method: 'POST', form: fd }); toast('فایل پیوست شد', 'success'); refresh(); }
      catch (e) { toast(errText(e), 'danger'); }
    };

    const costs = (wo.costs || []).map((c) => h('div', { class: 'kv-row small' },
      h('span', { style: 'flex:1' }, c.description || c.cost_type),
      h('span', { class: 'ltr' }, Number(c.amount).toLocaleString('fa-IR'))));

    return h('div', { class: 'card' },
      h('div', { class: 'card-head' }, h('h2', {}, 'یادداشت‌ها، فایل‌ها و هزینه‌ها')),
      h('div', { class: 'card-body' },
        notes.length ? h('div', { class: 'mb-4' }, h('h3', {}, 'یادداشت‌های اجرا'), notes) : null,
        h('h3', {}, 'فایل‌ها'),
        files.length ? files : h('div', { class: 'small faint' }, 'فایلی پیوست نشده'),
        Session.can('files.upload') ? h('div', { class: 'mt-2' },
          h('button', { class: 'btn btn-secondary btn-sm', onclick: () => fileInput.click() }, '📎 پیوست فایل'), fileInput) : null,
        h('hr', { class: 'hr' }),
        h('div', { style: 'display:flex;justify-content:space-between;align-items:center' },
          h('h3', {}, `هزینه‌ها (جمع: ${Number(wo.cost_total || 0).toLocaleString('fa-IR')})`),
          Session.can('workorders.manage') ? h('button', { class: 'btn btn-secondary btn-sm', onclick: costModal }, '+ هزینه') : null),
        costs.length ? costs : h('div', { class: 'small faint' }, 'هزینه‌ای ثبت نشده')));
  }

  function costModal() {
    const typeSel = h('select', { class: 'select' },
      [['preventive', 'پیشگیرانه'], ['corrective', 'اصلاحی'], ['emergency', 'اضطراری'],
       ['external_contractor', 'پیمانکار خارجی'], ['internal_labor', 'نیروی داخلی'],
       ['part', 'قطعه'], ['material', 'مواد'], ['service', 'سرویس'], ['other', 'سایر']]
        .map(([k, v]) => h('option', { value: k }, v)));
    const amount = h('input', { class: 'input ltr', type: 'number', min: '0' });
    const desc = h('input', { class: 'input', placeholder: 'شرح' });
    const saveBtn = h('button', { class: 'btn btn-primary' }, 'ثبت');
    const m = openModal({
      title: 'ثبت هزینه (§25)',
      body: h('div', { class: 'form-grid' },
        h('div', { class: 'field' }, h('label', {}, 'نوع هزینه'), typeSel),
        h('div', { class: 'field' }, h('label', {}, 'مبلغ (ریال)'), amount),
        h('div', { class: 'field span-2' }, h('label', {}, 'شرح'), desc)),
      footer: [saveBtn],
    });
    saveBtn.onclick = async () => {
      try {
        await api(`/work-orders/${wo.id}/costs`, { method: 'POST', body: {
          cost_type: typeSel.value, amount: +amount.value || 0, description: desc.value || null,
        } });
        toast('هزینه ثبت شد', 'success'); m.close(); refresh();
      } catch (e) { toast(errText(e), 'danger'); }
    };
  }
}
