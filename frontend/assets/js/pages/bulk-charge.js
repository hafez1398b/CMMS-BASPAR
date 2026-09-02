/** مرکز شارژ داده — Bulk Data Charge Center (§6B MODULE EQUIPMENT).
 *  Upload → SELEN mapping → staging diff → manual fixes → Commit → Rollback. */
import {
  api, errText, h, faNum, toast, openModal, confirmDialog, spinner,
  Session, downloadUrl,
} from '../core.js?v=12';
import { toJalaliStr } from '../jalali.js?v=12';

const STAGE_BADGE = {
  new: ['success', 'جدید'], update: ['info', 'بروزرسانی'],
  conflict: ['danger', 'Conflict'], rejected: ['neutral', 'رد شده'],
  resolved: ['warning', 'حل شده'],
};

export async function renderBulkCharge(main) {
  main.replaceChildren(
    h('div', { class: 'page-head' },
      h('h1', {}, 'مرکز شارژ داده (§6B)'),
      h('div', { class: 'spacer' }),
      h('button', { class: 'btn btn-secondary btn-sm', onclick: () =>
        downloadUrl('/equipment/bulk-charge/template').catch((e) => toast(errText(e), 'danger')) },
        '⬇ قالب ۶ شیت (تجهیزات/مشخصات/ساختار/قطعات/PM/سوابق)'),
      h('button', { class: 'btn btn-secondary btn-sm', onclick: loadBatches }, '🔄 تازه‌سازی')),
    h('div', { class: 'card mb-4' }, h('div', { class: 'card-body small muted' },
      'ورود داده‌های واقعی کارخانه با یک فایل Excel چندشیت: ',
      'تجهیزات + مشخصات فنی + ساختار + قطعات + برنامه‌های نگهداری + سوابق تعمیرات. ',
      'مسیر: آپلود ← Staging ← نگاشت پیشنهادی SELEN (تأیید با شما) ← پیش‌نمایش Diff ← ویرایش دستی ← Commit ← Rollback. ',
      'کد تجهیز با جداول پیشوند کارخانه و حوزه تجهیز (§7) رمزگشایی می‌شود.')),
    h('div', { id: 'bc-body' }));

  const body = main.querySelector('#bc-body');

  async function loadBatches() {
    body.replaceChildren(spinner());
    try {
      // quick-import listing doubles as the charge-batch ledger (same store)
      const data = await api('/equipment/bulk-import/batches');
      const charges = data.items.filter((b) => true); // batches of both kinds listed
      const rows = charges.map((b) => h('tr', {},
        h('td', {}, faNum(b.id)),
        h('td', {}, b.filename),
        h('td', {}, b.status === 'pending' ? h('span', { class: 'badge warning' }, 'در جریان')
          : b.status === 'confirmed' ? h('span', { class: 'badge success' }, 'Commit شده')
          : h('span', { class: 'badge neutral' }, 'Rollback شده')),
        h('td', { class: 'small' }, `${faNum(b.valid_rows ?? 0)}/${faNum(b.total_rows ?? 0)}`),
        h('td', { class: 'ltr small' }, toJalaliStr(b.created_at, true))));
      body.replaceChildren(
        uploadCard(),
        h('div', { class: 'card mt-4' },
          h('div', { class: 'card-head' }, h('h2', {}, 'بسته‌های شارژ')),
          h('div', { class: 'table-wrap' }, h('table', { class: 'table' },
            h('thead', {}, h('tr', {}, ['#', 'فایل', 'وضعیت', 'ردیف‌ها', 'تاریخ'].map((x) => h('th', {}, x)))),
            h('tbody', {}, rows.length ? rows : h('tr', {}, h('td', { colspan: '5', class: 'small faint', style: 'text-align:center' }, 'بسته‌ای وجود ندارد')))))));
    } catch (e) { body.replaceChildren(h('div', { class: 'small', style: 'color:var(--c-danger)' }, errText(e))); }
  }

  function uploadCard() {
    const fileInput = h('input', { type: 'file', accept: '.xlsx,.xls', style: 'display:none' });
    const zone = h('div', { class: 'upload-zone', onclick: () => fileInput.click() },
      '📤 فایل خام کارخانه (Excel — چند شیت: تجهیزات/مشخصات فنی/ساختار/قطعات) را انتخاب کنید',
      h('div', { class: 'small faint mt-2' }, 'فایل خام برای ردیابی در Audit نگهداری می‌شود (§6B)'));
    zone.addEventListener('dragover', (e) => { e.preventDefault(); zone.classList.add('drag'); });
    zone.addEventListener('dragleave', () => zone.classList.remove('drag'));
    zone.addEventListener('drop', (e) => {
      e.preventDefault(); zone.classList.remove('drag');
      if (e.dataTransfer.files[0]) upload(e.dataTransfer.files[0]);
    });
    fileInput.onchange = () => fileInput.files[0] && upload(fileInput.files[0]);

    async function upload(file) {
      const fd = new FormData(); fd.append('file', file);
      toast('در حال تحلیل فایل خام…', 'info', 2000);
      try {
        const res = await api('/equipment/bulk-charge/upload', { method: 'POST', form: fd });
        toast(`بسته #${faNum(res.batch_id)} در Staging ایجاد شد`, 'success');
        openMapping(res.batch_id, res.mapping);
      } catch (e) { toast(errText(e), 'danger'); }
    }
    return h('div', { class: 'card' }, h('div', { class: 'card-body' }, zone, fileInput));
  }

  /* ---------- step 2: SELEN mapping confirmation ---------- */
  function openMapping(batchId, mapping) {
    const FIELDS = [
      ['', '— نادیده بگیر —'], ['code', 'کد تجهیز'], ['name', 'نام تجهیز'],
      ['factory', 'کارخانه'], ['category', 'دسته'], ['equipment_type', 'نوع تجهیز'],
      ['manufacturer', 'سازنده'], ['model', 'مدل'], ['serial_number', 'شماره سریال'],
      ['year', 'سال ساخت'], ['country', 'کشور سازنده'], ['status', 'وضعیت'],
      ['criticality', 'Criticality'], ['hall', 'سالن'], ['dept', 'بخش'],
      ['line', 'خط'], ['location', 'موقعیت'], ['capacity', 'ظرفیت'], ['power', 'توان'],
    ];
    const selects = mapping.map((m) => {
      const sel = h('select', { class: 'select' },
        ...FIELDS.map(([v, label]) =>
          h('option', { value: v || 'ignore', selected: (m.field || '') === v }, label)));
      return { m, sel };
    });
    const confirmBtn = h('button', { class: 'btn btn-primary' }, 'تأیید Mapping و ادامه');
    const modal = openModal({
      title: `نگاشت ستون‌ها — بسته #${faNum(batchId)} (SELEN فقط پیشنهاد می‌دهد §14)`,
      size: 'modal-lg',
      body: h('div', {},
        h('div', { class: 'small muted mb-4' },
          'پیشنهاد SELEN بر اساس سربرگ‌ها و مقادیر شناخته‌شده تهیه شده است؛ هر ستون را تأیید، اصلاح یا نادیده بگیرید.'),
        h('div', { class: 'table-wrap' }, h('table', { class: 'table' },
          h('thead', {}, h('tr', {}, ['ستون خام', 'پیشنهاد SELEN', 'نگاشت نهایی'].map((x) => h('th', {}, x)))),
          h('tbody', {}, selects.map(({ m, sel }) => h('tr', {},
            h('td', {}, m.header || `(ستون ${m.index + 1})`),
            h('td', { class: 'small' }, m.field || '—',
              h('span', { class: 'badge ' + (m.confidence === 'high' ? 'success' : 'neutral'), style: 'margin-inline-start:6px' },
                m.confidence === 'high' ? 'اطمینان بالا' : 'نامشخص')),
            h('td', { style: 'min-width:200px' }, sel))))))),
      footer: [confirmBtn],
    });
    confirmBtn.onclick = async () => {
      const payload = {};
      selects.forEach(({ m, sel }) => payload[String(m.index)] = sel.value);
      try {
        await api(`/equipment/bulk-charge/${batchId}/mapping`, { method: 'POST', body: { mapping: payload } });
        modal.close();
        openPreview(batchId);
      } catch (e) { toast(errText(e), 'danger'); }
    };
  }

  /* ---------- step 3: diff preview + manual fixes ---------- */
  async function openPreview(batchId) {
    const modal = openModal({
      title: `پیش‌نمایش Diff — بسته #${faNum(batchId)}`, size: 'modal-lg',
      body: spinner('در حال تحلیل…'),
    });
    await drawPreview(modal, batchId);
  }

  async function drawPreview(modal, batchId) {
    let pv;
    try { pv = await api(`/equipment/bulk-charge/${batchId}/preview`); }
    catch (e) { modal.close(); toast(errText(e), 'danger'); return; }

    const counts = pv.counts;
    const chips = h('div', { class: 'chip-row mb-4' },
      chip('جدید', counts.new || 0, 'success'),
      chip('بروزرسانی', counts.update || 0, 'info'),
      chip('Conflict', counts.conflict || 0, 'danger'),
      chip('رد شده', counts.rejected || 0, 'neutral'));
    function chip(label, n, tone) {
      return h('span', { class: `badge ${tone}`, style: 'font-size:12.5px' }, `${label}: ${faNum(n)}`);
    }

    const extra = pv.extra_sheets || {};
    const hasExtra = extra.specs || extra.structure || extra.parts || extra.pm || extra.history;
    const extraInfo = hasExtra
      ? h('div', { class: 'small faint mb-2' },
          `شیت‌های همراه (با Commit اعمال می‌شوند): مشخصات فنی ${faNum(extra.specs || 0)} · ساختار ${faNum(extra.structure || 0)} · قطعات ${faNum(extra.parts || 0)} · برنامه نت ${faNum(extra.pm || 0)} · سوابق تعمیرات ${faNum(extra.history || 0)}`)
      : null;

    const rows = pv.rows.map((r) => {
      const meta = STAGE_BADGE[r.status] || ['neutral', r.status];
      return h('tr', {},
        h('td', {}, faNum(r.row_number)),
        h('td', { class: 'ltr' }, r.code || '—'),
        h('td', {}, r.name || '—'),
        h('td', { class: 'small' }, r.factory || '—'),
        h('td', {}, h('span', { class: `badge ${meta[0]}` }, meta[1])),
        h('td', { class: 'small', style: 'max-width:260px;color:var(--c-danger)' }, (r.errors || []).join('؛ ')),
        h('td', {},
          Session.can('bulk_charge.charge') && ['rejected', 'conflict'].includes(r.status)
            ? h('button', { class: 'btn btn-ghost btn-sm', onclick: () => editRow(modal, batchId, r) }, 'ویرایش') : null,
          Session.can('bulk_charge.approve') && r.status === 'conflict'
            ? h('span', {},
                h('button', { class: 'btn btn-ghost btn-sm', title: 'ایجاد به‌عنوان رکورد جدید', onclick: () => resolve(modal, batchId, r.id, 'create_new') }, 'جدید'),
                r.matched_equipment_id ? h('button', { class: 'btn btn-ghost btn-sm', title: 'ادغام با رکورد موجود', onclick: () => resolve(modal, batchId, r.id, 'merge') }, 'ادغام') : null,
                h('button', { class: 'btn btn-ghost btn-sm', style: 'color:var(--c-danger)', title: 'رد', onclick: () => resolve(modal, batchId, r.id, 'reject') }, 'رد'))
            : null));
    });

    const commitBtn = Session.can('bulk_charge.approve')
      ? h('button', { class: 'btn btn-primary', onclick: async () => {
          if (!await confirmDialog('رکوردهای بدون Conflict به دیتابیس اصلی منتقل می‌شوند. ادامه می‌دهید؟')) return;
          commitBtn.disabled = true;
          try {
            const res = await api(`/equipment/bulk-charge/${batchId}/commit`, { method: 'POST' });
            toast(`Commit شد: ${faNum(res.created)} تجهیز جدید، ${faNum(res.updated)} بروزرسانی، ` +
              `${faNum(res.plans_created || 0)} برنامه نت، ${faNum(res.history_created || 0)} سابقه تعمیرات`, 'success', 6000);
            modal.close(); loadBatches();
          } catch (e) { toast(errText(e), 'danger'); commitBtn.disabled = false; }
        } }, '✔ Commit (بدون Conflictها)')
      : null;
    const rollbackBtn = Session.can('bulk_charge.rollback')
      ? h('button', { class: 'btn btn-danger', onclick: async () => {
          if (!await confirmDialog('کل بسته بر اساس Batch ID بازگردانی می‌شود؛ رکوردهایی که بعداً تغییر کرده باشند بازگردانی نمی‌شوند.', { danger: true, title: 'Rollback بسته' })) return;
          try {
            const res = await api(`/equipment/bulk-charge/${batchId}/rollback`, { method: 'POST' });
            toast(`Rollback: ${faNum(res.removed)} حذف، ${faNum(res.restored)} بازگردانی${res.conflicts ? `، ${faNum(res.conflicts)} تعارض` : ''}`, 'warning');
            modal.close(); loadBatches();
          } catch (e) { toast(errText(e), 'danger'); }
        } }, '↩ Rollback')
      : null;

    modal.modal.querySelector('.modal-body').replaceChildren(
      chips, extraInfo,
      h('div', { class: 'table-wrap', style: 'max-height:46vh;overflow:auto' },
        h('table', { class: 'table' },
          h('thead', {}, h('tr', {}, ['ردیف', 'کد', 'نام', 'کارخانه', 'وضعیت', 'خطاها', ''].map((x) => h('th', {}, x)))),
          h('tbody', {}, rows))),
      h('div', { class: 'small faint mt-2' },
        'Commit فقط رکوردهای بدون Conflict را منتقل می‌کند؛ Conflictها باید جداگانه حل شوند (§6B).'),
      h('div', { class: 'mt-4', style: 'display:flex;gap:8px' }, commitBtn, rollbackBtn));
  }

  function editRow(modal, batchId, r) {
    const fields = [['code', 'کد تجهیز'], ['name', 'نام تجهیز'], ['factory', 'کارخانه'],
      ['category', 'دسته'], ['manufacturer', 'سازنده'], ['model', 'مدل'],
      ['serial_number', 'شماره سریال'], ['year', 'سال ساخت'], ['criticality', 'درجه اهمیت'],
      ['status', 'وضعیت'], ['hall', 'سالن'], ['line', 'خط']];
    const inputs = fields.map(([f, label]) => ({
      f, inp: h('input', { class: 'input', value: '', placeholder: label }),
    }));
    const saveBtn = h('button', { class: 'btn btn-primary' }, 'ذخیره (فیلد به فیلد)');
    const m2 = openModal({
      title: `ویرایش ردیف ${faNum(r.row_number)}`,
      body: h('div', { class: 'form-grid' },
        ...inputs.map(({ f, inp }) => h('div', { class: 'field' }, h('label', {}, f), inp)),
        h('div', { class: 'small faint span-2' }, 'فقط فیلدهایی که مقدار بدهید ذخیره می‌شوند.')),
      footer: [saveBtn],
    });
    saveBtn.onclick = async () => {
      let saved = 0;
      for (const { f, inp } of inputs) {
        const v = inp.value.trim();
        if (!v) continue;
        try {
          await api(`/equipment/bulk-charge/${batchId}/rows/${r.row_id}`, {
            method: 'POST', body: { field: f, value: v } });
          saved++;
        } catch (e) { toast(errText(e), 'danger'); break; }
      }
      if (saved) toast(`${faNum(saved)} فیلد ذخیره شد`, 'success');
      m2.close(); drawPreview(modal, batchId);
    };
  }

  async function resolve(modal, batchId, rowId, action) {
    try {
      await api(`/equipment/bulk-charge/${batchId}/rows/${rowId}/resolve`, {
        method: 'POST', body: { action } });
      drawPreview(modal, batchId);
    } catch (e) { toast(errText(e), 'danger'); }
  }

  await loadBatches();
}
