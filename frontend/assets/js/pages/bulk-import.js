/** Equipment Bulk Data Charge (MODULE EQUIPMENT — BASPAR):
 *  Excel/Markdown → Preview + Validation → Confirm → Rollback. */
import {
  api, errText, h, faNum, toast, confirmDialog, downloadUrl, toJalaliStr,
} from '../core.js?v=12';

const MD_SAMPLE = `| کد تجهیز | نام تجهیز | سطح | کارخانه | دسته‌بندی | نوع قطعه | درجه اهمیت |
|---|---|---|---|---|---|---|
| B3P1 | پمپ شماره ۱ اسفنج | تجهیز | بسپار۳ | ماشین‌آلات تولید | پمپ | زیاد |

یا به‌صورت سرفصل:

## B3P2 — پمپ شماره ۲
- کارخانه: بسپار۳
- دسته‌بندی: ماشین‌آلات تولید
- درجه اهمیت: زیاد`;

export async function renderBulkImport(main) {
  main.replaceChildren(
    h('div', { class: 'page-head' },
      h('h1', {}, 'ورود گروهی داده تجهیزات'),
      h('div', { class: 'spacer' }),
      h('button', { class: 'btn btn-secondary btn-sm', onclick: () => downloadUrl('/equipment/bulk-import/template').catch((e) => toast(errText(e), 'danger')) },
        '⬇ دانلود قالب Excel')),
    h('div', { class: 'card mb-4' }, h('div', { class: 'card-body small muted' },
      'برای داده‌های قدیمی و آشفته: فایل Excel یا Markdown بارگذاری کنید، یا متن را مستقیم بچسبانید؛ ',
      'سامانه ابتدا پیش‌نمایش و اعتبارسنجی ارائه می‌دهد، سپس با تأیید شما داده‌ها به‌صورت تراکنشی ثبت ',
      'می‌شوند و در صورت نیاز قابل بازگردانی (Rollback) هستند.')),
    h('div', { id: 'import-body' }));

  const body = main.querySelector('#import-body');
  const autoChk = h('input', { type: 'checkbox', id: 'auto-lookups' });
  const autoLabel = h('label', { style: 'display:inline-flex;gap:6px;align-items:center;cursor:pointer' },
    autoChk, 'ایجاد خودکار کارخانه/دسته‌بندیِ یافت‌نشده');

  // ------------------------------------------------------------------ tabs
  const tabs = h('div', { class: 'chip-row mb-4' });
  const panels = { file: h('div', {}), text: h('div', {}) };
  let active = 'file';
  function drawTabs() {
    tabs.replaceChildren(
      ...[['file', '📊 فایل Excel / Markdown'], ['text', '📝 چسباندن متن / Markdown']].map(([key, label]) =>
        h('button', {
          class: `btn btn-sm ${active === key ? 'btn-primary' : 'btn-secondary'}`,
          onclick: () => { active = key; drawTabs(); },
        }, label)));
    panels.file.style.display = active === 'file' ? '' : 'none';
    panels.text.style.display = active === 'text' ? '' : 'none';
  }

  // ------------------------------------------------------------- file panel
  const fileInput = h('input', { type: 'file', accept: '.xlsx,.xls,.md,.markdown,.txt', style: 'display:none' });
  const zone = h('div', { class: 'upload-zone', onclick: () => fileInput.click() },
    '📊 فایل Excel یا Markdown تجهیزات را انتخاب یا اینجا رها کنید',
    h('div', { class: 'small faint mt-2' }, 'ستون‌های الزامی: کد تجهیز، نام تجهیز، سطح — فرمت‌ها: xlsx / md / txt'),
    h('div', { class: 'small mt-2' }, autoLabel));
  zone.addEventListener('dragover', (e) => { e.preventDefault(); zone.classList.add('drag'); });
  zone.addEventListener('dragleave', () => zone.classList.remove('drag'));
  zone.addEventListener('drop', (e) => {
    e.preventDefault(); zone.classList.remove('drag');
    if (e.dataTransfer.files[0]) upload(e.dataTransfer.files[0]);
  });
  fileInput.onchange = () => fileInput.files[0] && upload(fileInput.files[0]);
  panels.file.append(h('div', { class: 'card' }, h('div', { class: 'card-body' }, zone)), fileInput);

  // ------------------------------------------------------------- text panel
  const ta = h('textarea', {
    class: 'input', dir: 'rtl', rows: '12',
    style: 'width:100%;font-family:inherit;line-height:1.9',
    placeholder: 'متن Markdown را اینجا بچسبانید (جدول یا سرفصل‌بندی)…',
  });
  const parseBtn = h('button', { class: 'btn btn-primary' }, 'تحلیل و پیش‌نمایش');
  parseBtn.onclick = async () => {
    const text = ta.value.trim();
    if (!text) { toast('ابتدا متن را وارد کنید', 'warning'); return; }
    parseBtn.disabled = true;
    try {
      const preview = await api('/equipment/bulk-import/text', {
        method: 'POST',
        body: { text, filename: 'چسباندن-متن.md', auto_create_lookups: autoChk.checked },
      });
      renderPreview(preview);
    } catch (e) { toast(errText(e), 'danger', 6000); }
    parseBtn.disabled = false;
  };
  const sampleBtn = h('button', { class: 'btn btn-ghost btn-sm', onclick: () => { ta.value = MD_SAMPLE; } },
    'درج نمونه');
  panels.text.append(h('div', { class: 'card' }, h('div', { class: 'card-body' },
    h('div', { style: 'display:flex;justify-content:space-between;align-items:center;margin-bottom:8px' },
      h('div', { class: 'small muted' },
        'هر دو فرمت پشتیبانی می‌شود: جدول Markdown (| ستون |) و سرفصل‌بندی (## کد — نام + فهرست «- فیلد: مقدار»)'),
      sampleBtn),
    ta,
    h('div', { class: 'mt-2', style: 'display:flex;gap:10px;align-items:center;flex-wrap:wrap' },
      parseBtn, autoLabel))));

  const batchesBox = h('div', { class: 'mt-4' });
  body.append(tabs, panels.file, panels.text, batchesBox);
  drawTabs();
  loadBatches();

  async function loadBatches() {
    try {
      const data = await api('/equipment/bulk-import/batches');
      const rows = data.items.map((b) => h('tr', {},
        h('td', {}, b.filename),
        h('td', { class: 'small' }, b.summary?.source === 'markdown'
          ? h('span', { class: 'badge neutral' }, 'Markdown')
          : h('span', { class: 'badge neutral' }, 'Excel')),
        h('td', {}, faNum(b.total_rows)),
        h('td', {}, h('span', { class: 'badge success' }, `${faNum(b.valid_rows)} معتبر`)),
        h('td', {}, b.error_rows ? h('span', { class: 'badge danger' }, `${faNum(b.error_rows)} خطا`) : h('span', { class: 'faint small' }, '—')),
        h('td', {}, b.status === 'pending' ? h('span', { class: 'badge warning' }, 'در انتظار تأیید')
          : b.status === 'confirmed' ? h('span', { class: 'badge success' }, 'تأیید شده')
          : h('span', { class: 'badge neutral' }, 'بازگردانی شده')),
        h('td', { class: 'ltr small' }, toJalaliStr(b.created_at, true)),
        h('td', {},
          b.status === 'confirmed' ? h('button', { class: 'btn btn-ghost btn-sm', style: 'color:var(--c-danger)', onclick: () => rollback(b.id) }, 'بازگردانی') : null)));
      batchesBox.replaceChildren(
        h('div', { class: 'card' },
          h('div', { class: 'card-head' }, h('h2', {}, 'بسته‌های ورودی اخیر')),
          h('div', { class: 'table-wrap' },
            h('table', { class: 'table' },
              h('thead', {}, h('tr', {}, ['فایل', 'منبع', 'ردیف‌ها', 'معتبر', 'خطا', 'وضعیت', 'تاریخ', ''].map((x) => h('th', {}, x)))),
              h('tbody', {}, rows.length ? rows : h('tr', {}, h('td', { colspan: '8', class: 'small faint', style: 'text-align:center' }, 'هنوز بسته‌ای بارگذاری نشده')))))));
    } catch { /* ignore */ }
  }

  async function upload(file) {
    const fd = new FormData();
    fd.append('file', file);
    toast('در حال تحلیل فایل…', 'info', 2000);
    try {
      const preview = await api(`/equipment/bulk-import?auto_create_lookups=${autoChk.checked}`, { method: 'POST', form: fd });
      renderPreview(preview);
    } catch (e) { toast(errText(e), 'danger'); }
  }

  function renderPreview(p) {
    const rows = p.rows.map((r) => h('tr', {},
      h('td', {}, faNum(r.row_number)),
      h('td', { class: 'ltr' }, r.code || '—'),
      h('td', {}, r.name || '—'),
      h('td', { class: 'small' }, r.level || '—'),
      h('td', {}, r.is_valid
        ? h('span', { class: 'badge success' }, 'معتبر')
        : h('span', { class: 'badge danger', title: r.errors.join('؛ ') }, 'خطا')),
      h('td', { class: 'small', style: 'color:var(--c-danger)' }, r.is_valid ? '' : r.errors.join('؛ '))));

    const confirmBtn = h('button', { class: 'btn btn-primary' }, `تأیید و ثبت ${faNum(p.valid_rows)} ردیف معتبر`);
    const card = h('div', { class: 'card' },
      h('div', { class: 'card-head' },
        h('h2', {}, `پیش‌نمایش بسته #${faNum(p.batch_id)}`),
        h('div', {},
          h('span', { class: 'badge success', style: 'margin-inline-end:8px' }, `${faNum(p.valid_rows)} معتبر`),
          p.error_rows ? h('span', { class: 'badge danger' }, `${faNum(p.error_rows)} خطا`) : null)),
      h('div', { class: 'table-wrap', style: 'max-height:420px;overflow-y:auto' },
        h('table', { class: 'table' },
          h('thead', {}, h('tr', {}, ['ردیف', 'کد', 'نام', 'سطح', 'وضعیت', 'پیام خطا'].map((x) => h('th', {}, x)))),
          h('tbody', {}, rows))),
      h('div', { class: 'card-body', style: 'display:flex;gap:10px' },
        confirmBtn,
        h('button', { class: 'btn btn-secondary', onclick: () => { card.remove(); } }, 'انصراف')));

    confirmBtn.onclick = async () => {
      confirmBtn.disabled = true;
      try {
        const res = await api(`/equipment/bulk-import/${p.batch_id}/confirm`, { method: 'POST' });
        toast(`${faNum(res.created)} تجهیز ثبت شد`, 'success');
        if (res.skipped?.length) toast(`${faNum(res.skipped.length)} ردیف رد شد`, 'warning');
        card.remove();
        loadBatches();
      } catch (e) {
        toast(errText(e), 'danger');
        confirmBtn.disabled = false;
      }
    };

    body.prepend(card);
    card.scrollIntoView({ behavior: 'smooth' });
  }

  async function rollback(batchId) {
    if (!await confirmDialog('تمام تجهیزات ایجادشده توسط این بسته حذف می‌شوند. ادامه می‌دهید؟', { danger: true, title: 'بازگردانی بسته ورودی' })) return;
    try {
      const res = await api(`/equipment/bulk-import/${batchId}/rollback`, { method: 'POST' });
      toast(`${faNum(res.removed)} تجهیز بازگردانی شد`, 'success');
      loadBatches();
    } catch (e) { toast(errText(e), 'danger'); }
  }
}
