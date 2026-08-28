/** Inventory parts (§23 gateway) + SELEN critical-parts view (§24). */
import {
  api, errText, h, faNum, toast, openModal, confirmDialog, spinner, Session, downloadUrl,
} from '../core.js?v=11';

const CRIT_FA = { low: 'کم', medium: 'متوسط', high: 'زیاد', critical: 'بحرانی' };
const CRIT_BADGE = { low: 'neutral', medium: 'info', high: 'warning', critical: 'danger' };

export async function renderParts(main) {
  main.replaceChildren(spinner());
  let tab = 'parts';

  async function load() {
    main.replaceChildren(
      h('div', { class: 'page-head' },
        h('h1', {}, 'قطعات و انبار'),
        h('div', { class: 'spacer' }),
        h('button', { class: 'btn btn-secondary btn-sm', onclick: () => downloadUrl('/parts/import/template').catch((e) => toast(errText(e), 'danger')) }, '⬇ قالب Excel'),
        Session.can('parts.manage') ? h('button', { class: 'btn btn-secondary btn-sm', onclick: importModal }, '⇪ ورود از انبار خارجی') : null,
        Session.can('parts.manage') ? h('button', { class: 'btn btn-primary btn-sm', onclick: () => partModal(null) }, '+ قطعه جدید') : null),
      h('div', { class: 'tabs mb-4' },
        h('button', { class: `tab ${tab === 'parts' ? 'active' : ''}`, onclick: () => { tab = 'parts'; load(); } }, 'فهرست قطعات'),
        h('button', { class: `tab ${tab === 'selen' ? 'active' : ''}`, onclick: () => { tab = 'selen'; load(); } }, '🧠 پیشنهاد SELEN (§24)')),
      h('div', { id: 'parts-body' }, spinner()));

    const body = main.querySelector('#parts-body');
    try {
      if (tab === 'parts') {
        const data = await api('/parts');
        const rows = data.items.map((p) => h('tr', {},
          h('td', { class: 'ltr' }, p.code),
          h('td', {}, h('strong', {}, p.name)),
          h('td', { class: 'small' }, p.equipment_name || '—'),
          h('td', {}, p.low_stock ? h('span', { class: 'badge danger' }, `${faNum(p.stock_qty)} (زیر حد سفارش)`) : faNum(p.stock_qty)),
          h('td', { class: 'small' }, faNum(p.min_qty)),
          h('td', {}, h('span', { class: `badge ${CRIT_BADGE[p.criticality] || 'neutral'}` }, CRIT_FA[p.criticality] || p.criticality)),
          h('td', { class: 'small' }, p.lead_time_days ? `${faNum(p.lead_time_days)} روز` : '—'),
          h('td', { class: 'small' }, p.supplier || '—'),
          h('td', {}, Session.can('parts.manage') ? h('span', {},
            h('button', { class: 'btn btn-ghost btn-sm', onclick: () => partModal(p) }, 'ویرایش'),
            h('button', { class: 'btn btn-ghost btn-sm', style: 'color:var(--c-danger)', onclick: async () => {
              if (!await confirmDialog(`قطعه «${p.name}» حذف شود؟ (§24: کاربران مجاز می‌توانند Override کنند)`)) return;
              try { await api(`/parts/${p.id}`, { method: 'DELETE' }); toast('حذف شد', 'success'); load(); }
              catch (e) { toast(errText(e), 'danger'); }
            } }, 'حذف')) : null)));
        body.replaceChildren(h('div', { class: 'table-wrap card' }, h('table', { class: 'table' },
          h('thead', {}, h('tr', {}, ['کد', 'نام', 'تجهیز مرتبط', 'موجودی', 'حد سفارش', 'اهمیت', 'زمان تأمین', 'تأمین‌کننده', ''].map((x) => h('th', {}, x)))),
          h('tbody', {}, rows.length ? rows : h('tr', {}, h('td', { colspan: '9', class: 'small faint', style: 'text-align:center;padding:18px' }, 'قطعه‌ای ثبت نشده — از درگاه ورود Excel استفاده کنید'))))));
      } else {
        const data = await api('/selen/spare-suggestions');
        const rows = data.items.map((p) => h('tr', {},
          h('td', { class: 'ltr' }, p.code),
          h('td', {}, p.name),
          h('td', {}, h('span', { class: `badge ${p.selen_score >= 60 ? 'danger' : p.selen_score >= 40 ? 'warning' : 'neutral'}` }, faNum(p.selen_score))),
          h('td', {}, p.suggested === 'بله' ? h('span', { class: 'badge danger' }, 'پیشنهاد ذخیره حیاتی') : h('span', { class: 'badge neutral' }, 'عادی')),
          h('td', { class: 'small' }, (p.selen_reasons || []).join('؛ ') || '—')));
        body.replaceChildren(
          h('div', { class: 'small muted mb-2' },
            'SELEN بر اساس مصرف، فراوانی خرابی، زمان تأمین، اهمیت تجهیز، سطح موجودی، قطعه جایگزین و تأمین‌کننده امتیاز می‌دهد. تصمیم نهایی و Add/Edit/Delete/Override با کاربر مجاز است (§24).'),
          h('div', { class: 'table-wrap card' }, h('table', { class: 'table' },
            h('thead', {}, h('tr', {}, ['کد', 'قطعه', 'امتیاز SELEN', 'پیشنهاد', 'دلایل'].map((x) => h('th', {}, x)))),
            h('tbody', {}, rows.length ? rows : h('tr', {}, h('td', { colspan: '5', class: 'small faint', style: 'text-align:center;padding:18px' }, 'داده‌ای نیست'))))));
      }
    } catch (e) { body.replaceChildren(h('div', { class: 'small', style: 'color:var(--c-danger)' }, errText(e))); }
  }

  function partModal(p) {
    const isNew = !p;
    const f = (label, node) => h('div', { class: 'field' }, h('label', {}, label), node);
    const code = h('input', { class: 'input ltr', value: p?.code || '' });
    const name = h('input', { class: 'input', value: p?.name || '' });
    const stock = h('input', { class: 'input ltr', type: 'number', value: p?.stock_qty ?? 0 });
    const minq = h('input', { class: 'input ltr', type: 'number', value: p?.min_qty ?? 0 });
    const crit = h('select', { class: 'select' },
      ...Object.entries(CRIT_FA).map(([k, v]) => h('option', { value: k, selected: p?.criticality === k }, v)));
    const lt = h('input', { class: 'input ltr', type: 'number', value: p?.lead_time_days ?? '' });
    const sup = h('input', { class: 'input', value: p?.supplier || '' });
    const alt = h('input', { class: 'input', value: p?.alternative_part || '' });
    const saveBtn = h('button', { class: 'btn btn-primary' }, 'ذخیره');
    const m = openModal({
      title: isNew ? 'قطعه جدید' : `ویرایش ${p.name}`,
      size: 'modal-lg',
      body: h('div', { class: 'form-grid' },
        f('کد *', code), f('نام *', name), f('موجودی', stock), f('حد سفارش', minq),
        f('درجه اهمیت', crit), f('زمان تأمین (روز)', lt), f('تأمین‌کننده', sup),
        f('قطعه جایگزین', alt)),
      footer: [saveBtn],
    });
    saveBtn.onclick = async () => {
      const body = {
        code: code.value.trim(), name: name.value.trim(),
        stock_qty: +stock.value || 0, min_qty: +minq.value || 0,
        criticality: crit.value, lead_time_days: lt.value ? +lt.value : null,
        supplier: sup.value || null, alternative_part: alt.value || null,
        equipment_id: p?.equipment_id ?? null,
      };
      try {
        if (isNew) await api('/parts', { method: 'POST', body });
        else await api(`/parts/${p.id}`, { method: 'PUT', body });
        toast('ذخیره شد', 'success'); m.close(); load();
      } catch (e) { toast(errText(e), 'danger'); }
    };
  }

  function importModal() {
    const fileInput = h('input', { type: 'file', accept: '.xlsx,.xls', style: 'display:none' });
    const preview = h('div', {});
    const zone = h('div', { class: 'upload-zone', onclick: () => fileInput.click() },
      '📦 فایل Excel انبار خارجی را انتخاب کنید (§23: Preview → تأیید → Rollback)');
    fileInput.onchange = async () => {
      const f = fileInput.files[0];
      if (!f) return;
      const fd = new FormData(); fd.append('file', f);
      try {
        const p = await api('/parts/import', { method: 'POST', form: fd });
        const rows = p.rows.map((r) => h('tr', {},
          h('td', {}, faNum(r.row_number)), h('td', { class: 'ltr' }, r.code || '—'),
          h('td', {}, r.name || '—'),
          h('td', {}, r.is_valid ? h('span', { class: 'badge success' }, 'معتبر') : h('span', { class: 'badge danger' }, 'خطا')),
          h('td', { class: 'small', style: 'color:var(--c-danger)' }, r.is_valid ? '' : r.errors.join('؛ '))));
        const confirmBtn = h('button', { class: 'btn btn-primary', onclick: async () => {
          confirmBtn.disabled = true;
          try { const res = await api(`/parts/import/${p.batch_id}/confirm`, { method: 'POST' }); toast(`${faNum(res.created)} قطعه ثبت شد`, 'success'); m.close(); load(); }
          catch (e) { toast(errText(e), 'danger'); confirmBtn.disabled = false; }
        } }, `تأیید و ثبت ${faNum(p.valid_rows)} قطعه`);
        preview.replaceChildren(
          h('div', { class: 'chip-row mb-2' },
            h('span', { class: 'badge success' }, `${faNum(p.valid_rows)} معتبر`),
            p.error_rows ? h('span', { class: 'badge danger' }, `${faNum(p.error_rows)} خطا`) : null),
          h('div', { class: 'table-wrap', style: 'max-height:300px;overflow:auto' },
            h('table', { class: 'table' },
              h('thead', {}, h('tr', {}, ['ردیف', 'کد', 'نام', 'وضعیت', 'خطا'].map((x) => h('th', {}, x)))),
              h('tbody', {}, rows))),
          h('div', { class: 'mt-4' }, confirmBtn));
      } catch (e) { toast(errText(e), 'danger'); }
    };
    const m = openModal({
      title: 'درگاه ورود داده انبار (§23)', size: 'modal-lg',
      body: h('div', {}, zone, fileInput, h('div', { class: 'mt-4' }, preview)),
    });
  }

  await load();
}
