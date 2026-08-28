/** Inspection Checklists (§15): templates, execution, escalation. */
import {
  api, errText, h, faNum, toast, openModal, spinner, navigate, Session,
} from '../core.js?v=11';
import { toJalaliStr } from '../jalali.js?v=11';

const RESULT_META = {
  ok: ['success', 'سالم'], not_ok: ['danger', 'نامطلوب'],
  na: ['neutral', 'N/A'], requires_action: ['warning', 'نیازمند اقدام'],
  pending: ['neutral', 'بی‌پاسخ'],
};

export async function renderChecklists(main) {
  main.replaceChildren(spinner());
  let equipment = [];
  try { equipment = (await api('/equipment?level=equipment&page_size=200')).items; } catch { }

  async function load() {
    main.replaceChildren(
      h('div', { class: 'page-head' },
        h('h1', {}, 'چک‌لیست‌های بازرسی'),
        h('div', { class: 'spacer' }),
        Session.can('checklist.manage') ? h('button', { class: 'btn btn-secondary', onclick: tplModal }, '+ قالب جدید') : null,
        Session.can('checklist.execute') ? h('button', { class: 'btn btn-primary', onclick: runModal }, '▶ اجرای بازرسی') : null));
    try {
      const [tpls, runs] = await Promise.all([api('/checklists/templates'), api('/checklists/runs')]);
      main.append(
        h('div', { style: 'display:grid;grid-template-columns:repeat(auto-fit,minmax(360px,1fr));gap:16px' },
          h('div', { class: 'card' },
            h('div', { class: 'card-head' }, h('h2', {}, 'قالب‌ها')),
            h('div', { class: 'card-body' },
              tpls.items.length ? tpls.items.map((t) =>
                h('div', { class: 'mb-4', style: 'border-bottom:1px solid var(--c-border);padding-bottom:10px' },
                  h('div', { style: 'display:flex;justify-content:space-between' },
                    h('strong', {}, t.name),
                    h('span', { class: 'badge neutral' }, t.period_code)),
                  h('div', { class: 'small faint' }, `${faNum(t.items.length)} آیتم${t.equipment_name ? ` · ${t.equipment_name}` : ''}`),
                  h('div', { class: 'small mt-2' }, t.items.map((i) => `• ${i.text}`).join('  '))))
                : h('div', { class: 'small faint' }, 'قالبی تعریف نشده است.'))),
          h('div', { class: 'card' },
            h('div', { class: 'card-head' }, h('h2', {}, 'اجراهای اخیر')),
            h('div', { class: 'card-body' },
              runs.items.length ? runs.items.map((r) =>
                h('div', { class: 'mb-2', style: 'display:flex;align-items:center;gap:8px' },
                  h('a', { href: `#/checklists/${r.id}`, style: 'flex:1' },
                    `${r.template_name} — ${r.equipment_name || ''}`),
                  h('span', { class: `badge ${r.status === 'complete' ? (r.result_summary === 'fail' ? 'danger' : 'success') : 'warning'}` },
                    r.status === 'complete' ? (r.result_summary === 'fail' ? 'نامطلوب' : 'سالم') : 'باز'),
                  h('span', { class: 'small faint ltr' }, toJalaliStr(r.run_date))))
                : h('div', { class: 'small faint' }, 'اجرایی ثبت نشده است.')))));
    } catch (e) { toast(errText(e), 'danger'); }
  }

  /** §5B — قالب چک‌لیست با ناوبری مرحله‌ای (بازگشت / بعدی / تأیید نهایی)
   *  + پیشنهاد فرم توسط SELEN. داده‌ها بین مراحل حفظ می‌شوند. */
  function tplModal() {
    const ST = { step: 0, name: '', period: 'monthly', days: '', eqId: '', items: [], selen: null };
    const STEPS_FA = ['مشخصات قالب', 'آیتم‌های بازرسی', 'بازبینی و تأیید'];

    const bodyBox = h('div', {});
    const backBtn = h('button', { class: 'btn btn-secondary' }, 'بازگشت →');
    const nextBtn = h('button', { class: 'btn btn-primary' }, '← بعدی');
    const finalBtn = h('button', { class: 'btn btn-primary' }, '✔ تأیید نهایی');

    const m = openModal({
      title: 'قالب چک‌لیست بازرسی جدید (§15 — مرحله‌ای)',
      body: bodyBox,
      footer: [backBtn, nextBtn, finalBtn],
    });

    backBtn.onclick = () => { if (ST.step > 0) { ST.step--; draw(); } };
    nextBtn.onclick = () => {
      if (ST.step === 0 && !ST.name.trim()) { toast('نام قالب الزامی است', 'warning'); return; }
      if (ST.step === 1 && ST.items.length === 0) { toast('حداقل یک آیتم بازرسی اضافه کنید', 'warning'); return; }
      if (ST.step < 2) { ST.step++; draw(); }
    };
    finalBtn.onclick = async () => {
      finalBtn.disabled = true;
      try {
        await api('/checklists/templates', { method: 'POST', body: {
          name: ST.name.trim(), period_code: ST.period,
          custom_days: ST.days ? +ST.days : null,
          items: ST.items,
        } });
        toast('قالب چک‌لیست ذخیره شد', 'success'); m.close(); load();
      } catch (e) { toast(errText(e), 'danger'); finalBtn.disabled = false; }
    };

    async function fetchSelen(btn) {
      btn.disabled = true; btn.textContent = 'در حال تحلیل…';
      try {
        const eq = equipment.find((e) => String(e.id) === ST.eqId);
        const d = await api('/selen/checklist-suggestions', { method: 'POST', body: {
          name: eq ? eq.name : ST.name, category: eq?.category?.name || null,
          component_type: eq?.component_type || null,
        } });
        ST.selen = d;
        toast(`SELEN بر اساس ${d.basis} پیشنهاد داد`, 'info', 4000);
      } catch (e) { toast(errText(e), 'danger'); }
      btn.disabled = false; draw();
    }

    function draw() {
      backBtn.disabled = ST.step === 0;
      nextBtn.style.display = ST.step === 2 ? 'none' : '';
      finalBtn.style.display = ST.step === 2 ? '' : 'none';

      const stepper = h('div', { class: 'chip-row mb-4', style: 'flex-wrap:wrap' },
        ...STEPS_FA.map((s, i) => h('span', {
          class: `badge ${i === ST.step ? 'primary' : i < ST.step ? 'success' : 'neutral'}`,
          style: 'font-size:12px',
        }, `${faNum(i + 1)} ${s}`)));

      let content;
      if (ST.step === 0) {
        const nameI = h('input', { class: 'input', value: ST.name, oninput: (e) => ST.name = e.target.value });
        const periodS = h('select', { class: 'select' },
          h('option', { value: 'monthly' }, 'ماهانه'), h('option', { value: 'yearly' }, 'سالانه'),
          h('option', { value: 'custom' }, 'سفارشی'));
        periodS.value = ST.period; periodS.onchange = () => ST.period = periodS.value;
        const daysI = h('input', { class: 'input ltr', type: 'number', placeholder: 'روز (سفارشی)',
          value: ST.days, oninput: (e) => ST.days = e.target.value });
        const eqS = h('select', { class: 'select' },
          h('option', { value: '' }, '— بدون تجهیز مرجع —'),
          ...equipment.map((e) => h('option', { value: String(e.id) }, `${e.code} — ${e.name}`)));
        eqS.value = ST.eqId; eqS.onchange = () => ST.eqId = eqS.value;
        content = h('div', { class: 'form-grid' },
          h('div', { class: 'field span-2' }, h('label', {}, 'نام قالب *'), nameI),
          h('div', { class: 'field' }, h('label', {}, 'دوره'), periodS),
          h('div', { class: 'field' }, h('label', {}, 'روز (سفارشی)'), daysI),
          h('div', { class: 'field span-2' },
            h('label', {}, 'تجهیز مرجع (برای پیشنهاد هوشمند آیتم‌ها — اختیاری)'), eqS));
      } else if (ST.step === 1) {
        const selenBtn = h('button', { class: 'btn btn-secondary mb-4', onclick: (e) => fetchSelen(e.currentTarget) },
          '🤖 پیشنهاد فرم چک‌لیست SELEN');
        const rows = ST.items.map((v, i) => h('div', { class: 'kv-row' },
          h('input', { class: 'input', value: v, placeholder: `آیتم ${faNum(i + 1)}`, oninput: (e) => ST.items[i] = e.target.value }),
          h('button', { class: 'btn btn-ghost btn-sm', onclick: () => { ST.items.splice(i, 1); draw(); } }, '−')));
        const addI = h('input', { class: 'input', placeholder: 'آیتم جدید…' });
        const manualAdd = h('button', { class: 'btn btn-secondary btn-sm', onclick: () => {
          if (addI.value.trim()) { ST.items.push(addI.value.trim()); draw(); }
        } }, '+ افزودن');
        const selenPanel = ST.selen ? h('div', { class: 'card mb-4', style: 'border:1px dashed var(--c-border)' },
          h('div', { class: 'card-body' },
            h('div', { style: 'display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;flex-wrap:wrap;gap:6px' },
              h('strong', {}, 'آیتم‌های پیشنهادی بازرسی'),
              h('span', { class: 'badge neutral' }, `مبنای پیشنهاد: ${ST.selen.basis}`)),
            (ST.selen.items || []).map((it) => {
              const added = ST.items.includes(it);
              return h('div', { class: 'kv-row', style: 'margin-bottom:4px' },
                h('span', { class: 'small', style: 'flex:1' }, '◦ ', it),
                added ? h('span', { class: 'badge success' }, 'اضافه شد')
                      : h('button', { class: 'btn btn-ghost btn-sm', onclick: () => { ST.items.push(it); draw(); } }, '+'));
            }),
            h('div', { class: 'small faint mt-2' }, 'SELEN فقط پیشنهاد می‌دهد؛ افزودن تنها با کلیک «+» انجام می‌شود (§14)'))) : null;
        content = h('div', {}, selenBtn, selenPanel,
          h('label', { class: 'small', style: 'display:block;margin-bottom:6px' }, `آیتم‌های فرم (${faNum(ST.items.length)})`),
          rows.length ? h('div', {}, rows) : h('div', { class: 'small faint mb-2' }, 'آیتمی اضافه نشده است.'),
          h('div', { class: 'kv-row mt-2' }, addI, manualAdd));
      } else {
        content = h('div', {},
          h('div', { class: 'table-wrap card' }, h('table', { class: 'table' }, h('tbody', {},
            h('tr', {}, h('td', { class: 'muted small', style: 'width:140px' }, 'نام قالب'), h('td', {}, ST.name)),
            h('tr', {}, h('td', { class: 'muted small' }, 'دوره'),
              h('td', {}, ST.period === 'monthly' ? 'ماهانه' : ST.period === 'yearly' ? 'سالانه' : `سفارشی — ${faNum(ST.days)} روز`)),
            h('tr', {}, h('td', { class: 'muted small' }, 'تعداد آیتم‌ها'), h('td', {}, faNum(ST.items.length)))))),
          h('div', { class: 'card mt-4' }, h('div', { class: 'card-body' },
            ST.items.map((it, i) => h('div', { class: 'small mb-2' }, `${faNum(i + 1)}. ${it}`)))));
      }
      bodyBox.replaceChildren(stepper, content);
    }
    draw();
  }

  function runModal() {
    const eqSel = h('select', { class: 'select' },
      h('option', { value: '' }, 'انتخاب تجهیز…'),
      ...equipment.map((e) => h('option', { value: String(e.id) }, `${e.code} — ${e.name}`)));
    const tplSel = h('select', { class: 'select' }, h('option', { value: '' }, 'در حال بارگذاری…'));
    api('/checklists/templates').then((d) => tplSel.replaceChildren(
      h('option', { value: '' }, 'انتخاب قالب…'),
      ...d.items.map((t) => h('option', { value: String(t.id) }, t.name))));
    const saveBtn = h('button', { class: 'btn btn-primary' }, 'شروع بازرسی');
    const m = openModal({
      title: 'اجرای بازرسی جدید',
      body: h('div', { class: 'form-grid' },
        h('div', { class: 'field' }, h('label', {}, 'تجهیز *'), eqSel),
        h('div', { class: 'field' }, h('label', {}, 'قالب *'), tplSel)),
      footer: [saveBtn],
    });
    saveBtn.onclick = async () => {
      if (!eqSel.value || !tplSel.value) { toast('تجهیز و قالب را انتخاب کنید', 'warning'); return; }
      try {
        const run = await api('/checklists/runs', { method: 'POST', body: {
          template_id: +tplSel.value, equipment_id: +eqSel.value,
        } });
        m.close(); navigate(`#/checklists/${run.id}`);
      } catch (e) { toast(errText(e), 'danger'); }
    };
  }

  await load();
}

export async function renderChecklistRun(main, id) {
  main.replaceChildren(spinner());
  async function load() {
    try {
      const runs = (await api('/checklists/runs')).items;
      const run = runs.find((r) => String(r.id) === String(id));
      if (!run) { main.replaceChildren(h('div', { class: 'card' }, h('div', { class: 'card-body' }, 'یافت نشد'))); return; }
      const complete = run.status === 'complete';
      const rows = run.items.map((it) => {
        const meta = RESULT_META[it.result] || RESULT_META.pending;
        return h('tr', {},
          h('td', {}, it.text),
          h('td', {}, complete
            ? h('span', { class: `badge ${meta[0]}` }, meta[1])
            : h('span', {}, ...['ok', 'not_ok', 'na', 'requires_action'].map((res) =>
                h('button', {
                  class: `btn btn-sm ${it.result === res ? 'btn-primary' : 'btn-secondary'}`,
                  style: 'margin-inline-end:4px',
                  onclick: async () => {
                    try { await api(`/checklists/runs/${run.id}/items/${it.id}`, { method: 'POST', body: { result: res } }); load(); }
                    catch (e) { toast(errText(e), 'danger'); }
                  },
                }, RESULT_META[res][1])))),
          h('td', { class: 'small' }, it.comment || ''));
      });
      const pendingCount = run.items.filter((i) => i.result === 'pending').length;
      main.replaceChildren(
        h('div', { class: 'page-head' },
          h('div', { class: 'breadcrumb' }, h('a', { href: '#/checklists' }, 'چک‌لیست‌ها'), '‹', h('span', {}, run.template_name)),
          h('div', { class: 'spacer' }),
          h('h1', {}, `${run.template_name} — ${run.equipment_name || ''}`),
          h('span', { class: `badge ${complete ? (run.result_summary === 'fail' ? 'danger' : 'success') : 'warning'}` },
            complete ? (run.result_summary === 'fail' ? 'نامطلوب' : 'سالم') : 'در حال اجرا')),
        h('div', { class: 'card' },
          h('div', { class: 'card-head' },
            h('h2', {}, 'نتایج آیتم‌ها (§15: سالم / نامطلوب / N/A / نیازمند اقدام)'),
            h('div', {},
              !complete && Session.can('checklist.execute') ? h('button', { class: 'btn btn-primary btn-sm', onclick: async () => {
                try {
                  const r = await api(`/checklists/runs/${run.id}/finish`, { method: 'POST', body: {} });
                  toast(`بسته شد: ${r.result_summary === 'fail' ? 'دارای مورد نامطلوب' : 'سالم'}`, r.result_summary === 'fail' ? 'warning' : 'success');
                  load();
                } catch (e) { toast(errText(e), 'danger'); }
              } }, `پایان بازرسی (${faNum(pendingCount)} بی‌پاسخ)`) : null,
              complete && run.result_summary === 'fail' && Session.can('requests.create')
                ? h('button', { class: 'btn btn-danger btn-sm', style: 'margin-inline-start:8px', onclick: async () => {
                    try { const r = await api(`/checklists/runs/${run.id}/to-request`, { method: 'POST' }); toast('درخواست کار ثبت شد', 'success'); navigate(`#/requests`); }
                    catch (e) { toast(errText(e), 'danger'); }
                  } }, '⚠ ثبت درخواست کار برای موارد نامطلوب') : null,
              complete && run.result_summary === 'fail' && Session.can('workorders.create')
                ? h('button', { class: 'btn btn-danger btn-sm', style: 'margin-inline-start:8px', onclick: async () => {
                    try { const r = await api(`/checklists/runs/${run.id}/to-workorder`, { method: 'POST' }); toast(`دستورکار ${r.code} ایجاد شد`, 'success'); navigate(`#/work-orders/${r.work_order_id}`); }
                    catch (e) { toast(errText(e), 'danger'); }
                  } }, '🛠 ایجاد دستورکار مستقیم') : null)),
          h('div', { class: 'table-wrap' }, h('table', { class: 'table' },
            h('thead', {}, h('tr', {}, ['آیتم بازرسی', 'نتیجه', 'توضیح'].map((x) => h('th', {}, x)))),
            h('tbody', {}, rows)))),
        run.general_comment ? h('div', { class: 'card mt-4' }, h('div', { class: 'card-body small' }, run.general_comment)) : null);
    } catch (e) { main.replaceChildren(h('div', { class: 'small', style: 'color:var(--c-danger)' }, errText(e))); }
  }
  await load();
}
