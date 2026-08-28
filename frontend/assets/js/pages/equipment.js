/** ماژول تجهیزات — فهرست / کارت / درخت (§4, §5, §30, §31, §40).
 *  Clean rewrite: simple, consistent, server-side filter + pagination. */
import {
  Session, api, errText, h, navigate, toast, spinner, table, pager,
  critBadge, statusBadge, faNum, downloadUrl, confirmDialog,
} from '../core.js?v=11';
import { icon } from '../icons.js?v=11';

const CRIT_FA = { low: 'کم', medium: 'متوسط', high: 'زیاد', critical: 'بحرانی' };

export async function renderEquipmentList(main) {
  const state = {
    q: '', factory_id: '', category_id: '', criticality: '', status: '',
    component_type: '', dept: '',
    page: 1, view: 'list', selected: new Set(),
  };
  let factories = [], categories = [], compTypes = [];

  main.replaceChildren(spinner());
  try {
    [factories, categories, compTypes] = await Promise.all([
      api('/factories').then((d) => d.items),
      api('/categories').then((d) => d.items),
      api('/lookups?list_code=component_type').then((d) => d.items.filter((x) => x.is_active)),
    ]);
  } catch { /* filters optional */ }

  const content = h('div', {});

  function sel(value, options, onChange) {
    const el = h('select', { class: 'select', style: 'max-width:180px' },
      h('option', { value: '' }, 'همه'),
      ...options.map(([v, label]) => h('option', { value: v }, label)));
    el.value = value;
    el.onchange = () => onChange(el.value);
    return el;
  }

  function viewBtn(view, name, ic) {
    return h('button', {
      class: `btn btn-sm ${state.view === view ? 'btn-primary' : 'btn-secondary'}`,
      onclick: () => { state.view = view; load(); },
    }, h('span', { html: icon(ic), style: 'display:inline-flex;width:14px;height:14px' }), name);
  }

  function toolbar() {
    const search = h('input', {
      class: 'input', placeholder: 'جستجو: کد / نام / سریال…', style: 'max-width:260px',
    });
    let t = null;
    search.oninput = () => { clearTimeout(t); t = setTimeout(() => { state.q = search.value.trim(); state.page = 1; load(); }, 300); };

    return h('div', { class: 'toolbar' },
      search,
      sel(state.factory_id, factories.map((f) => [String(f.id), f.name]), (v) => { state.factory_id = v; state.page = 1; load(); }),
      sel(state.category_id, categories.map((c) => [String(c.id), c.name]), (v) => { state.category_id = v; state.page = 1; load(); }),
      sel(state.criticality, Object.entries(CRIT_FA), (v) => { state.criticality = v; state.page = 1; load(); }),
      sel(state.status, [['active', 'فعال'], ['inactive', 'غیرفعال'], ['under_maintenance', 'در تعمیر'], ['scrapped', 'اسقاط']], (v) => { state.status = v; state.page = 1; load(); }),
      sel(state.component_type, compTypes.map((t) => [t.title_fa, t.title_fa]), (v) => { state.component_type = v; state.page = 1; load(); }),
      h('div', { class: 'spacer' }),
      viewBtn('list', 'جدول', 'table'),
      viewBtn('card', 'کارت', 'card'),
      viewBtn('tree', 'درخت', 'tree'),
      Session.can('equipment.export')
        ? h('button', { class: 'btn btn-secondary btn-sm', onclick: exportCsv },
            h('span', { html: icon('download'), style: 'display:inline-flex;width:14px;height:14px' }), 'خروجی')
        : null,
      Session.can('equipment.create')
        ? h('button', { class: 'btn btn-primary', onclick: () => navigate('#/equipment/new') },
            h('span', { html: icon('plus'), style: 'display:inline-flex;width:14px;height:14px' }), 'افزودن تجهیز')
        : null);
  }

  function exportCsv() {
    const qs = new URLSearchParams();
    if (state.factory_id) qs.set('factory_id', state.factory_id);
    if (state.category_id) qs.set('category_id', state.category_id);
    if (state.criticality) qs.set('criticality', state.criticality);
    if (state.status) qs.set('status', state.status);
    downloadUrl(`/equipment/export/csv?${qs}`).catch((e) => toast(errText(e), 'danger'));
  }

  function bulkBar() {
    if (!Session.can('equipment.edit') || state.selected.size === 0) return null;
    const set = (status) => async () => {
      if (!await confirmDialog(`وضعیت ${faNum(state.selected.size)} تجهیز تغییر کند؟`)) return;
      try {
        const r = await api('/equipment/bulk/status', { method: 'POST', body: { ids: [...state.selected], status } });
        toast(`${faNum(r.updated)} تجهیز به‌روزرسانی شد`, 'success');
        state.selected.clear(); load();
      } catch (e) { toast(errText(e), 'danger'); }
    };
    return h('div', { class: 'toolbar' },
      h('span', { class: 'small' }, `${faNum(state.selected.size)} انتخاب`),
      h('button', { class: 'btn btn-secondary btn-sm', onclick: set('active') }, 'فعال‌سازی'),
      h('button', { class: 'btn btn-secondary btn-sm', onclick: set('inactive') }, 'غیرفعال‌سازی'));
  }

  async function loadList() {
    const qs = new URLSearchParams({ page: state.page, page_size: 25, level: 'equipment' });
    if (state.q) qs.set('q', state.q);
    if (state.factory_id) qs.set('factory_id', state.factory_id);
    if (state.category_id) qs.set('category_id', state.category_id);
    if (state.criticality) qs.set('criticality', state.criticality);
    if (state.status) qs.set('status', state.status);
    if (state.component_type) qs.set('component_type', state.component_type);
    if (state.dept) qs.set('dept', state.dept);
    const data = await api(`/equipment?${qs}`);

    const rows = data.items.map((e) => {
      const cb = h('input', {
        type: 'checkbox', ...(state.selected.has(e.id) ? { checked: true } : {}),
        onclick: (ev) => { ev.stopPropagation(); state.selected.has(e.id) ? state.selected.delete(e.id) : state.selected.add(e.id); load(); },
      });
      return h('tr', { class: 'clickable', onclick: () => navigate(`#/equipment/${e.id}`) },
        h('td', { onclick: (ev) => ev.stopPropagation() }, cb),
        h('td', { class: 'ltr' }, e.code),
        h('td', {}, h('strong', {}, e.name)),
        h('td', { class: 'small muted' }, e.category ? e.category.name : '—'),
        h('td', { class: 'small muted' }, e.factory ? e.factory.name : '—'),
        h('td', { class: 'small muted' }, [e.hall, e.line].filter(Boolean).join(' / ') || e.location || '—'),
        h('td', {}, statusBadge(e.status)),
        h('td', {}, critBadge(e.criticality, CRIT_FA[e.criticality])));
    });

    content.replaceChildren(
      table(['', 'کد', 'نام تجهیز', 'دسته', 'کارخانه', 'محل', 'وضعیت', 'اهمیت'], rows),
      h('div', { class: 'small faint mt-2', style: 'text-align:center' }, `${faNum(data.total)} تجهیز`),
      pager(data.page, data.total, data.page_size, (p) => { state.page = p; load(); }));
  }

  async function loadCard() {
    const qs = new URLSearchParams({ page: state.page, page_size: 12, level: 'equipment' });
    if (state.q) qs.set('q', state.q);
    if (state.factory_id) qs.set('factory_id', state.factory_id);
    const data = await api(`/equipment?${qs}`);
    const cards = data.items.map((e) => h('div', { class: 'card', style: 'cursor:pointer', onclick: () => navigate(`#/equipment/${e.id}`) },
      h('div', { class: 'card-body' },
        h('div', { style: 'display:flex;justify-content:space-between' },
          h('div', {}, h('div', { class: 'ltr small faint' }, e.code), h('h3', {}, e.name)),
          critBadge(e.criticality, CRIT_FA[e.criticality])),
        h('div', { class: 'small muted mt-2' },
          h('div', {}, `🏭 ${e.factory ? e.factory.name : '—'} · 🗂 ${e.category ? e.category.name : '—'}`)),
        h('div', { class: 'mt-2' }, statusBadge(e.status)))));
    content.replaceChildren(
      h('div', { style: 'display:grid;grid-template-columns:repeat(auto-fill,minmax(270px,1fr));gap:14px' }, cards),
      pager(data.page, data.total, data.page_size, (p) => { state.page = p; load(); }));
  }

  async function loadTree() {
    const qs = state.factory_id ? `?factory_id=${state.factory_id}` : '';
    const data = await api(`/equipment/tree${qs}`);
    const tree = h('div', { class: 'tree card', style: 'padding:16px' });
    const ul = h('ul', {});
    data.tree.forEach((f) => ul.append(factoryNode(f)));
    if (!data.tree.length) ul.append(h('li', { class: 'small faint' }, 'تجهیزی ثبت نشده است'));
    tree.append(ul);
    content.replaceChildren(tree);
  }

  function factoryNode(f) {
    const kids = h('ul', {});
    const caret = h('span', { class: 'caret open' }, '▶');
    const row = h('div', { class: 'node-row' }, caret, h('span', {}, '🏭'), h('span', { class: 'node-title' }, f.name));
    row.onclick = () => { kids.style.display = kids.style.display === 'none' ? '' : 'none'; caret.classList.toggle('open'); };
    const li = h('li', {}, row, kids);
    f.categories.forEach((c) => kids.append(categoryNode(c)));
    return li;
  }

  function categoryNode(c) {
    const kids = h('ul', {});
    const caret = h('span', { class: 'caret open' }, '▶');
    const row = h('div', { class: 'node-row' }, caret, h('span', {}, '🗂'), h('span', { class: 'node-title' }, c.name),
      h('span', { class: 'small faint' }, `(${faNum(c.equipment.length)})`));
    row.onclick = (ev) => { ev.stopPropagation(); kids.style.display = kids.style.display === 'none' ? '' : 'none'; caret.classList.toggle('open'); };
    const li = h('li', {}, row, kids);
    c.equipment.forEach((e) => kids.append(eqNode(e)));
    return li;
  }

  function eqNode(e) {
    const kids = h('ul', {});
    const has = e.children.length > 0;
    const caret = h('span', { class: 'caret', style: has ? '' : 'visibility:hidden' }, '▶');
    const row = h('div', { class: 'node-row' }, caret,
      h('span', { class: 'node-title' }, e.name),
      h('span', { class: 'small faint ltr' }, e.code),
      critBadge(e.criticality, CRIT_FA[e.criticality]));
    row.onclick = (ev) => {
      if (has && ev.target === caret) { kids.style.display = kids.style.display === 'none' ? '' : 'none'; caret.classList.toggle('open'); return; }
      navigate(`#/equipment/${e.id}`);
    };
    const li = h('li', {}, row, kids);
    if (has) { kids.style.display = 'none'; e.children.forEach((c) => kids.append(eqNode(c))); }
    return li;
  }

  async function load() {
    content.replaceChildren(spinner());
    const bar = bulkBar();
    main.replaceChildren(
      h('div', { class: 'page-head' }, h('h1', {}, 'مدیریت تجهیزات')),
      toolbar(),
      bar || h('div', {}),
      content);
    try {
      if (state.view === 'list') await loadList();
      else if (state.view === 'card') await loadCard();
      else await loadTree();
    } catch (e) {
      content.replaceChildren(h('div', { class: 'card' }, h('div', { class: 'card-body small', style: 'color:var(--c-danger)' }, errText(e))));
    }
  }

  await load();
}
