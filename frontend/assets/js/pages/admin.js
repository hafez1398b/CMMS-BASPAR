/** Admin module (§37, §38): users, roles/permissions, base data,
 *  audit log, backup/restore, settings. */
import {
  api, errText, h, faNum, toast, openModal, confirmDialog, spinner,
  Session, table, pager, downloadUrl, fmtBytes,
} from '../core.js?v=11';
import { toJalaliStr } from '../jalali.js?v=11';

/* ================================================================== *
 * USERS
 * ================================================================== */
export async function renderUsers(main) {
  main.replaceChildren(h('div', { class: 'page-head' }, h('h1', {}, 'مدیریت کاربران')), spinner());
  let roles = [];
  try { roles = await api('/roles').then((d) => d.items); } catch { }

  async function load() {
    try {
      const data = await api('/users');
      const rows = data.items.map((u) => h('tr', {},
        h('td', { class: 'ltr' }, u.username),
        h('td', {}, h('strong', {}, u.full_name)),
        h('td', { class: 'small' }, (u.roles || []).map((r) => r.title_fa).join('، ') || '—'),
        h('td', {}, u.is_active ? h('span', { class: 'badge success' }, 'فعال') : h('span', { class: 'badge neutral' }, 'غیرفعال')),
        h('td', { class: 'ltr small' }, toJalaliStr(u.created_at)),
        h('td', {},
          Session.can('users.edit') ? h('button', { class: 'btn btn-ghost btn-sm', onclick: () => userModal(u) }, 'ویرایش') : null,
          Session.can('users.delete') && u.username !== Session.user.username
            ? h('button', { class: 'btn btn-ghost btn-sm', style: 'color:var(--c-danger)', onclick: async () => {
                if (!await confirmDialog(`کاربر «${u.full_name}» حذف (غیرفعال) شود؟`, { danger: true })) return;
                try { await api(`/users/${u.id}`, { method: 'DELETE' }); toast('کاربر حذف شد', 'success'); load(); }
                catch (e) { toast(errText(e), 'danger'); }
              } }, 'حذف') : null)));
      main.replaceChildren(
        h('div', { class: 'page-head' },
          h('h1', {}, 'مدیریت کاربران'),
          h('div', { class: 'spacer' }),
          Session.can('users.create') ? h('button', { class: 'btn btn-primary', onclick: () => userModal(null) }, '+ کاربر جدید') : null),
        table(['نام کاربری', 'نام کامل', 'نقش‌ها', 'وضعیت', 'تاریخ ایجاد', ''], rows));
    } catch (e) { main.replaceChildren(h('div', { class: 'small', style: 'color:var(--c-danger)' }, errText(e))); }
  }

  function userModal(u) {
    const isNew = !u;
    const uname = h('input', { class: 'input ltr', value: u?.username || '', ...(isNew ? {} : { readonly: true }) });
    const fname = h('input', { class: 'input', value: u?.full_name || '' });
    const email = h('input', { class: 'input ltr', value: u?.email || '' });
    const phone = h('input', { class: 'input ltr', value: u?.phone || '' });
    const pass = h('input', { class: 'input ltr', type: 'password', placeholder: isNew ? 'الزامی' : 'برای تغییر وارد کنید' });
    const activeChk = h('input', { type: 'checkbox', ...(u && !u.is_active ? {} : { checked: true }) });
    const roleChecks = roles.map((r) => {
      const chk = h('input', { type: 'checkbox', ...(u?.roles?.some((x) => x.name === r.name) ? { checked: true } : {}) });
      return { r, chk };
    });
    const saveBtn = h('button', { class: 'btn btn-primary' }, 'ذخیره');
    const m = openModal({
      title: isNew ? 'کاربر جدید' : `ویرایش ${u.full_name}`,
      body: h('div', {},
        h('div', { class: 'form-grid' },
          h('div', { class: 'field' }, h('label', {}, 'نام کاربری *'), uname),
          h('div', { class: 'field' }, h('label', {}, 'نام کامل *'), fname),
          h('div', { class: 'field' }, h('label', {}, 'ایمیل'), email),
          h('div', { class: 'field' }, h('label', {}, 'تلفن'), phone),
          h('div', { class: 'field' }, h('label', {}, 'رمز عبور'), pass),
          h('div', { class: 'field' }, h('label', {}, 'فعال'), activeChk)),
        h('div', { class: 'field mt-4' }, h('label', {}, 'نقش‌ها'),
          h('div', { class: 'chip-row' }, roleChecks.map(({ r, chk }) =>
            h('label', { class: 'perm-item', style: 'cursor:pointer' }, chk, r.title_fa))))),
      footer: [saveBtn],
    });
    saveBtn.onclick = async () => {
      const body = {
        username: uname.value.trim().toLowerCase(),
        full_name: fname.value.trim(),
        email: email.value.trim() || null,
        phone: phone.value.trim() || null,
        password: pass.value || null,
        is_active: activeChk.checked,
        role_names: roleChecks.filter((x) => x.chk.checked).map((x) => x.r.name),
      };
      if (isNew && !body.password) { toast('رمز عبور اولیه الزامی است', 'warning'); return; }
      try {
        if (isNew) await api('/users', { method: 'POST', body });
        else await api(`/users/${u.id}`, { method: 'PUT', body });
        toast('ذخیره شد', 'success'); m.close(); load();
      } catch (e) { toast(errText(e), 'danger'); }
    };
  }

  await load();
}

/* ================================================================== *
 * ROLES & PERMISSIONS
 * ================================================================== */
export async function renderRoles(main) {
  main.replaceChildren(h('div', { class: 'page-head' }, h('h1', {}, 'نقش‌ها و دسترسی‌ها')), spinner());
  try {
    const data = await api('/roles');
    const cards = data.items.map((r) => {
      const permSet = new Set(r.permissions);
      const boxes = data.all_permissions.map((p) => {
        const chk = h('input', { type: 'checkbox', ...(permSet.has(p.code) ? { checked: true } : {}) });
        if (r.name === 'admin') chk.disabled = true;
        else chk.onchange = () => permSet.has(p.code) ? permSet.delete(p.code) : permSet.add(p.code);
        return h('label', { class: 'perm-item' }, chk, p.title_fa, h('span', { class: 'faint small ltr' }, p.code));
      });
      const saveBtn = r.name === 'admin' ? null : h('button', { class: 'btn btn-primary btn-sm', onclick: async () => {
        saveBtn.disabled = true;
        try {
          await api(`/roles/${r.id}/permissions`, { method: 'PUT', body: { permissions: [...permSet] } });
          toast(`دسترسی‌های «${r.title_fa}» ذخیره شد`, 'success');
        } catch (e) { toast(errText(e), 'danger'); }
        saveBtn.disabled = false;
      } }, 'ذخیره دسترسی‌ها');
      return h('div', { class: 'card mb-4' },
        h('div', { class: 'card-head' },
          h('div', {}, h('h2', {}, r.title_fa), h('div', { class: 'small faint ltr' }, r.name)),
          saveBtn),
        h('div', { class: 'card-body' },
          r.name === 'admin'
            ? h('div', { class: 'small muted' }, 'نقش مدیر سیستم به‌صورت ذاتی تمام دسترسی‌ها را دارد (§38).')
            : h('div', { class: 'perm-grid' }, boxes)));
    });
    main.replaceChildren(
      h('div', { class: 'page-head' }, h('h1', {}, 'نقش‌ها و دسترسی‌ها')),
      h('div', { class: 'small muted mb-4' }, 'تغییر دسترسی‌ها بلافاصله در ورودهای بعدی کاربران اعمال می‌شود و در گزارش ممیزی ثبت می‌گردد.'),
      ...cards);
  } catch (e) { main.replaceChildren(h('div', { class: 'small', style: 'color:var(--c-danger)' }, errText(e))); }
}

/* ================================================================== *
 * BASE DATA (factories / categories / lookups)
 * ================================================================== */
export async function renderBaseData(main) {
  main.replaceChildren(h('div', { class: 'page-head' }, h('h1', {}, 'داده‌های پایه')), spinner());

  async function draw() {
    const [f, c, l] = await Promise.all([api('/factories'), api('/categories'), api('/lookups')]);

    const simpleTable = (items, cols, onEdit) => h('div', { class: 'table-wrap card' },
      h('table', { class: 'table' },
        h('thead', {}, h('tr', {}, [...cols.map((x) => h('th', {}, x)), h('th', {}, '')])),
        h('tbody', {}, items.map((it) => h('tr', {},
          ...cols.map((_, i) => h('td', { class: i === 0 ? 'small' : '' }, it[['_c0', '_c1', '_c2'][i]] ?? '')),
          h('td', {}, h('button', { class: 'btn btn-ghost btn-sm', onclick: () => onEdit(it) }, 'ویرایش')))))));

    const fRows = f.items.map((x) => ({ ...x, _c0: x.code, _c1: x.name, _c2: x.is_active ? 'فعال' : 'غیرفعال' }));
    const cRows = c.items.map((x) => ({ ...x, _c0: x.code, _c1: x.name, _c2: x.is_active ? 'فعال' : 'غیرفعال' }));

    const listCodes = [...new Set(l.items.map((x) => x.list_code))];
    const lookupTabs = h('div', { class: 'tabs mb-4' });
    const lookupBody = h('div', {});
    let activeList = listCodes[0];
    function drawLookups() {
      lookupTabs.replaceChildren(...listCodes.map((lc) =>
        h('button', { class: `tab ${lc === activeList ? 'active' : ''}`, onclick: () => { activeList = lc; drawLookups(); } }, LIST_FA[lc] || lc)));
      const items = l.items.filter((x) => x.list_code === activeList);
      lookupBody.replaceChildren(simpleTable(
        items.map((x) => ({ ...x, _c0: x.code, _c1: x.title_fa, _c2: x.is_active ? 'فعال' : 'غیرفعال' })),
        ['کد', 'عنوان', 'وضعیت'],
        (it) => editModal('/lookups', it, ['list_code', 'code', 'title_fa'])));
    }
    drawLookups();

    main.replaceChildren(
      h('div', { class: 'page-head' },
        h('h1', {}, 'داده‌های پایه'),
        h('div', { class: 'spacer' }),
        h('button', { class: 'btn btn-secondary btn-sm', onclick: () => editModal('/factories', null, ['code', 'name', 'address']) }, '+ کارخانه'),
        h('button', { class: 'btn btn-secondary btn-sm', onclick: () => editModal('/categories', null, ['code', 'name']) }, '+ دسته‌بندی'),
        h('button', { class: 'btn btn-secondary btn-sm', onclick: () => editModal('/lookups', null, ['list_code', 'code', 'title_fa']) }, '+ آیتم فهرست')),
      h('div', { style: 'display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:16px' },
        h('div', {}, h('h2', {}, 'کارخانه‌ها'), simpleTable(fRows, ['کد', 'نام', 'وضعیت'], (it) => editModal('/factories', it, ['code', 'name', 'address']))),
        h('div', {}, h('h2', {}, 'دسته‌بندی تجهیزات'), simpleTable(cRows, ['کد', 'نام', 'وضعیت'], (it) => editModal('/categories', it, ['code', 'name'])))),
      h('h2', { class: 'mt-4' }, 'فهرست‌های کشویی (Activity Types، Intervals، …)'),
      lookupTabs, lookupBody);
  }

  const LIST_FA = {
    activity_type: 'انواع فعالیت', interval: 'دوره‌های تکرار', work_class: 'کلاس کار',
    equipment_status: 'وضعیت تجهیز', criticality: 'درجه اهمیت',
    request_type: 'انواع درخواست', cost_type: 'انواع هزینه',
  };
  const FIELD_FA = { code: 'کد', name: 'نام', address: 'آدرس', list_code: 'فهرست', title_fa: 'عنوان فارسی' };

  function editModal(base, item, fields) {
    const inps = fields.map((f) => {
      const inp = h('input', { class: 'input', dir: f === 'title_fa' || f === 'name' || f === 'address' ? 'rtl' : 'ltr', value: item?.[f] || '' });
      if (f === 'list_code' && !item) inp.value = activeList || 'activity_type';
      return { f, inp };
    });
    const saveBtn = h('button', { class: 'btn btn-primary' }, 'ذخیره');
    const m = openModal({
      title: item ? 'ویرایش' : 'افزودن',
      body: h('div', { class: 'form-grid' }, ...inps.map(({ f, inp }) =>
        h('div', { class: 'field' }, h('label', {}, FIELD_FA[f] || f), inp))),
      footer: [saveBtn],
    });
    saveBtn.onclick = async () => {
      const body = {};
      inps.forEach(({ f, inp }) => body[f] = inp.value.trim());
      try {
        if (item) await api(`${base}/${item.id}`, { method: 'PUT', body });
        else await api(base, { method: 'POST', body });
        toast('ذخیره شد', 'success'); m.close(); draw();
      } catch (e) { toast(errText(e), 'danger'); }
    };
  }

  try { await draw(); } catch (e) { main.replaceChildren(h('div', { class: 'small', style: 'color:var(--c-danger)' }, errText(e))); }
}

/* ================================================================== *
 * AUDIT LOG
 * ================================================================== */
export async function renderAudit(main) {
  main.replaceChildren(h('div', { class: 'page-head' }, h('h1', {}, 'گزارش ممیزی')), spinner());
  let page = 1;
  async function load() {
    try {
      const data = await api(`/audit-logs?page=${page}&page_size=30`);
      const rows = data.items.map((a) => h('tr', {},
        h('td', { class: 'ltr small' }, toJalaliStr(a.created_at, true)),
        h('td', { class: 'small' }, a.user_name || '—'),
        h('td', {}, h('code', { class: 'mono' }, a.action)),
        h('td', { class: 'small' }, a.entity_type),
        h('td', { class: 'small' }, a.entity_id || '—'),
        h('td', { class: 'ltr small' }, a.ip || '—'),
        h('td', {}, h('button', { class: 'btn btn-ghost btn-sm', onclick: () => openModal({
          title: `جزئیات رویداد #${a.id}`,
          size: 'modal-lg',
          body: h('div', { class: 'ltr small', style: 'font-family:monospace;white-space:pre-wrap;max-height:60vh;overflow:auto' },
            JSON.stringify({ old: a.old_values, new: a.new_values }, null, 2)),
        }) }, 'جزئیات'))));
      main.replaceChildren(
        h('div', { class: 'page-head' }, h('h1', {}, 'گزارش ممیزی'),
          h('div', { class: 'spacer' }),
          h('span', { class: 'small faint' }, `${faNum(data.total)} رویداد ثبت شده`)),
        table(['زمان', 'کاربر', 'عملیات', 'موجودیت', 'شناسه', 'IP', ''], rows),
        pager(page, data.total, 30, (p) => { page = p; load(); }));
    } catch (e) { main.replaceChildren(h('div', { class: 'small', style: 'color:var(--c-danger)' }, errText(e))); }
  }
  await load();
}

/* ================================================================== *
 * BACKUP / RESTORE
 * ================================================================== */
export async function renderBackup(main) {
  main.replaceChildren(h('div', { class: 'page-head' }, h('h1', {}, 'پشتیبان‌گیری و بازیابی')), spinner());
  async function load() {
    try {
      const data = await api('/backup');
      const rows = data.items.map((b) => h('tr', {},
        h('td', { class: 'ltr small' }, b.filename),
        h('td', { class: 'small' }, fmtBytes(b.size)),
        h('td', { class: 'ltr small' }, toJalaliStr(b.created_at, true)),
        h('td', {}, h('button', { class: 'btn btn-ghost btn-sm', style: 'color:var(--c-danger)', onclick: async () => {
          if (!await confirmDialog('بازیابی این پشتیبان، داده‌های فعلی را جایگزین می‌کند (یک کاپی قبل از بازیابی نگهداری می‌شود). ادامه می‌دهید؟', { danger: true, title: 'بازیابی پشتیبان' })) return;
          try { const r = await api(`/backup/restore?filename=${encodeURIComponent(b.filename)}`, { method: 'POST' }); toast(r.note, 'success'); }
          catch (e) { toast(errText(e), 'danger'); }
        } }, 'بازیابی'))));
      const createBtn = h('button', { class: 'btn btn-primary', onclick: async () => {
        createBtn.disabled = true;
        try { await api('/backup', { method: 'POST' }); toast('پشتیبان ساخته شد', 'success'); load(); }
        catch (e) { toast(errText(e), 'danger'); }
        createBtn.disabled = false;
      } }, '+ پشتیبان کامل جدید');
      main.replaceChildren(
        h('div', { class: 'page-head' }, h('h1', {}, 'پشتیبان‌گیری و بازیابی'), h('div', { class: 'spacer' }), createBtn),
        h('div', { class: 'small muted mb-4' },
          `محل ذخیره: `, h('code', { class: 'mono' }, data.location),
          ' — هر پشتیبان شامل پایگاه داده و تمام فایل‌های بارگذاری‌شده است.'),
        table(['فایل', 'حجم', 'تاریخ', ''], rows));
    } catch (e) { main.replaceChildren(h('div', { class: 'small', style: 'color:var(--c-danger)' }, errText(e))); }
  }
  await load();
}

/* ================================================================== *
 * SETTINGS
 * ================================================================== */
export async function renderSettings(main) {
  let health = { checks: {} };
  try { health = await api('/health/detailed'); } catch { try { health = await api('/health'); } catch { } }

  const kv = (k, v, ok) => h('tr', {},
    h('td', { class: 'muted small', style: 'width:240px' }, k),
    h('td', {}, ok === undefined ? v : (ok ? h('span', { class: 'badge success' }, 'سالم') : h('span', { class: 'badge danger' }, 'خطا')), ok === undefined ? '' : h('span', { class: 'small faint', style: 'margin-inline-start:8px' }, v)));

  const c = health.checks || {};
  main.replaceChildren(
    h('div', { class: 'page-head' }, h('h1', {}, 'تنظیمات سامانه')),
    h('div', { style: 'display:grid;grid-template-columns:repeat(auto-fit,minmax(360px,1fr));gap:16px' },
      h('div', { class: 'card' },
        h('div', { class: 'card-head' }, h('h2', {}, 'سلامت سامانه (§48)')),
        h('div', { class: 'card-body table-wrap' },
          h('table', { class: 'table' }, h('tbody', {}, [
            kv('پایگاه داده', c.database?.url || '', c.database?.ok),
            kv('فضای ذخیره‌سازی', c.storage?.root || '', c.storage?.ok),
            kv('لایه Real-Time', `${c.realtime?.subscribers ?? 0} مشترک`, c.realtime?.ok),
            kv('محیط اجرا', c.app?.environment || '—'),
          ])))),
      h('div', { class: 'card' },
        h('div', { class: 'card-head' }, h('h2', {}, 'درباره سامانه')),
        h('div', { class: 'card-body small muted' },
          h('p', {}, 'سامانه مدیریت نت هوشمند بسپار — Enterprise Intelligent CMMS/EAM'),
          h('p', {}, 'فاز جاری: فاز ۰ (آماده برای ممیزی). تقویم شمسی در تمام بخش‌ها فعال است؛ ذخیره‌سازی تاریخ‌ها به‌صورت ISO-8601 میلادی انجام می‌شود.'),
          h('p', {}, 'ماژول‌های دستور کار، آفلاین، اعلان‌ها و SELEN AI طبق فازبندی سند کارفرما در فازهای ۱ و ۲ فعال می‌شوند.')))),
    );
}
