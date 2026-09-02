/** مدیریت تأمین‌کنندگان قطعات یدکی (بخش ۴.۵ سند بارگذاری نهایی). */
import {
  api, errText, h, faNum, toast, openModal, confirmDialog, spinner,
  Session, table,
} from '../core.js?v=12';
import { toJalaliStr } from '../jalali.js?v=12';

export async function renderSuppliers(main) {
  main.replaceChildren(h('div', { class: 'page-head' }, h('h1', {}, 'تأمین‌کنندگان')), spinner());

  async function load() {
    try {
      const data = await api('/suppliers');
      const rows = data.items.map((s) => h('tr', {},
        h('td', {}, h('strong', {}, s.name)),
        h('td', { class: 'small' }, s.contact || '—'),
        h('td', { class: 'ltr small' }, s.phone || '—'),
        h('td', { class: 'small' }, s.notes || '—'),
        h('td', {}, s.is_active
          ? h('span', { class: 'badge success' }, 'فعال')
          : h('span', { class: 'badge neutral' }, 'غیرفعال')),
        h('td', { class: 'ltr small' }, toJalaliStr(s.created_at)),
        h('td', {},
          Session.can('parts.manage') ? h('button', { class: 'btn btn-ghost btn-sm', onclick: () => modal(s) }, 'ویرایش') : null,
          Session.can('parts.manage') ? h('button', {
            class: 'btn btn-ghost btn-sm', style: 'color:var(--c-danger)',
            onclick: async () => {
              if (!await confirmDialog(`تأمین‌کننده «${s.name}» حذف شود؟`, { danger: true })) return;
              try { await api(`/suppliers/${s.id}`, { method: 'DELETE' }); toast('حذف شد', 'success'); load(); }
              catch (e) { toast(errText(e), 'danger'); }
            },
          }, 'حذف') : null)));
      main.replaceChildren(
        h('div', { class: 'page-head' },
          h('h1', {}, 'تأمین‌کنندگان'),
          h('div', { class: 'spacer' }),
          Session.can('parts.manage') ? h('button', { class: 'btn btn-primary', onclick: () => modal(null) }, '+ تأمین‌کننده جدید') : null),
        h('div', { class: 'card mb-4' }, h('div', { class: 'card-body small muted' },
          'فهرست تأمین‌کنندگان قطعات یدکی — هنگام بارگذاری نهایی، قطعات به‌صورت خودکار به تأمین‌کننده هم‌نام متصل می‌شوند.')),
        table(['نام', 'مسئول فروش', 'تلفن', 'یادداشت', 'وضعیت', 'تاریخ ایجاد', ''], rows));
    } catch (e) { main.replaceChildren(h('div', { class: 'small', style: 'color:var(--c-danger)' }, errText(e))); }
  }

  function modal(s) {
    const name = h('input', { class: 'input', value: s ? s.name : '' });
    const contact = h('input', { class: 'input', value: s ? (s.contact || '') : '' });
    const phone = h('input', { class: 'input ltr', value: s ? (s.phone || '') : '' });
    const notes = h('textarea', { class: 'input', rows: '3' }, s ? (s.notes || '') : '');
    const active = h('input', { type: 'checkbox', ...(s && !s.is_active ? {} : { checked: true }) });
    const save = h('button', { class: 'btn btn-primary' }, 'ذخیره');
    const m = openModal({
      title: s ? 'ویرایش تأمین‌کننده' : 'تأمین‌کننده جدید',
      body: h('div', { class: 'form-grid' },
        h('div', { class: 'field span-2' }, h('label', {}, 'نام *'), name),
        h('div', { class: 'field' }, h('label', {}, 'مسئول فروش'), contact),
        h('div', { class: 'field' }, h('label', {}, 'تلفن'), phone),
        h('div', { class: 'field span-2' }, h('label', {}, 'یادداشت'), notes),
        h('div', { class: 'field' }, h('label', {}, 'فعال'), active)),
      footer: [save],
    });
    save.onclick = async () => {
      if (!name.value.trim()) { toast('نام الزامی است', 'warning'); return; }
      save.disabled = true;
      try {
        await api(s ? `/suppliers/${s.id}` : '/suppliers', {
          method: s ? 'PUT' : 'POST',
          body: { name: name.value.trim(), contact: contact.value || null,
                  phone: phone.value || null, notes: notes.value || null,
                  is_active: active.checked },
        });
        toast('ذخیره شد', 'success'); m.close(); load();
      } catch (e) { toast(errText(e), 'danger'); save.disabled = false; }
    };
  }

  await load();
}
