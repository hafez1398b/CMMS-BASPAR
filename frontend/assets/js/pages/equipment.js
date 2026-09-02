/** BASPAR CMMS — Equipment Module v2
 * Dark First · Enterprise · Tree + List + Card
 * Spec: Company > Factory > Area > Line > Equipment > Subsystem > Component > Part
 */

import {
  Session, api, errText, h, navigate, toast, spinner, table, pager,
  critBadge, statusBadge, faNum, downloadUrl, confirmDialog,
} from '../core.js?v=12';
import { icon } from '../icons.js?v=12';

const CRIT_FA = { low: 'کم', medium: 'متوسط', high: 'زیاد', critical: 'بحرانی' };

export async function renderEquipmentList(main) {
  const state = {
    q: '', factory_id: '', category_id: '', criticality: '', status: '',
    page: 1, view: 'tree', selected: new Set(),
  };
  let factories = [], categories = [];

  main.replaceChildren(spinner('در حال بارگذاری تجهیزات...'));
  try {
    [factories, categories] = await Promise.all([
      api('/factories').then(d => d.items),
      api('/categories').then(d => d.items),
    ]);
  } catch {}

  const content = h('div', {});

  function toolbar() {
    const search = h('input', {
      class: 'input',
      placeholder: 'جستجو: کد، نام، سریال، مدل...',
      style: 'max-width:320px;height:36px',
      value: state.q,
    });
    let t = null;
    search.oninput = () => {
      clearTimeout(t);
      t = setTimeout(() => { state.q = search.value.trim(); state.page = 1; load(); }, 300);
    };

    const factorySel = h('select', { class: 'select', style: 'max-width:160px;height:36px' },
      h('option', { value: '' }, 'همه کارخانه‌ها'),
      ...factories.map(f => h('option', { value: String(f.id) }, f.name))
    );
    factorySel.value = state.factory_id;
    factorySel.onchange = () => { state.factory_id = factorySel.value; state.page = 1; load(); };

    const viewBtn = (view, label, ic) => h('button', {
      class: `btn btn-sm ${state.view === view ? 'btn-primary' : 'btn-secondary'}`,
      onclick: () => { state.view = view; load(); }
    }, h('span', { html: icon(ic), style: 'width:14px;height:14px' }), label);

    return h('div', { class: 'toolbar', style: 'background:var(--c-card);border:1px solid var(--c-border);border-radius:12px;padding:12px' },
      search,
      factorySel,
      h('div', { class: 'spacer' }),
      h('div', { style: 'display:flex;gap:6px' },
        viewBtn('tree', 'درخت', 'tree'),
        viewBtn('list', 'جدول', 'table'),
        viewBtn('card', 'کارت', 'card'),
      ),
      Session.can('equipment.export') ? h('button', { class: 'btn btn-secondary btn-sm', onclick: exportCsv },
        h('span', { html: icon('download'), style: 'width:14px;height:14px' }), 'خروجی'
      ) : null,
      Session.can('equipment.create') ? h('button', { class: 'btn btn-primary btn-sm', onclick: () => navigate('#/equipment/new') },
        h('span', { html: icon('plus'), style: 'width:14px;height:14px' }), 'افزودن تجهیز'
      ) : null
    );
  }

  function exportCsv() {
    const qs = new URLSearchParams();
    if (state.factory_id) qs.set('factory_id', state.factory_id);
    downloadUrl(`/equipment/export/csv?${qs}`).catch(e => toast(errText(e), 'danger'));
  }

  async function loadList() {
    const qs = new URLSearchParams({ page: state.page, page_size: 25, level: 'equipment' });
    if (state.q) qs.set('q', state.q);
    if (state.factory_id) qs.set('factory_id', state.factory_id);
    if (state.category_id) qs.set('category_id', state.category_id);
    if (state.criticality) qs.set('criticality', state.criticality);
    if (state.status) qs.set('status', state.status);
    const data = await api(`/equipment?${qs}`);

    const rows = data.items.map(e =>
      h('tr', { class: 'clickable', onclick: () => navigate(`#/equipment/${e.id}`) },
        h('td', {}, h('span', { class: `status-dot ${e.status === 'active' ? 'success' : e.status === 'under_maintenance' ? 'warning' : 'danger'}` })),
        h('td', { class: 'ltr mono small' }, e.code),
        h('td', {}, h('div', { style: 'font-weight:600' }, e.name), h('div', { class: 'small faint' }, e.model || '')),
        h('td', { class: 'small' }, e.category?.name || '—'),
        h('td', { class: 'small' }, e.factory?.name || '—'),
        h('td', { class: 'small' }, [e.hall, e.line].filter(Boolean).join(' / ') || e.location || '—'),
        h('td', {}, statusBadge(e.status)),
        h('td', {}, critBadge(e.criticality, CRIT_FA[e.criticality]))
      )
    );

    content.replaceChildren(
      h('div', { class: 'card' },
        h('div', { class: 'table-wrap' },
          table(['', 'کد', 'نام تجهیز', 'دسته', 'کارخانه', 'محل', 'وضعیت', 'اهمیت'], rows)
        )
      ),
      h('div', { style: 'display:flex;justify-content:space-between;align-items:center;margin-top:12px' },
        h('div', { class: 'small faint' }, `${faNum(data.total)} تجهیز`),
        pager(data.page, data.total, data.page_size, p => { state.page = p; load(); })
      )
    );
  }

  async function loadCard() {
    const qs = new URLSearchParams({ page: state.page, page_size: 12, level: 'equipment' });
    if (state.q) qs.set('q', state.q);
    if (state.factory_id) qs.set('factory_id', state.factory_id);
    const data = await api(`/equipment?${qs}`);

    const cards = data.items.map(e => h('div', {
      class: 'card hover-lift',
      style: 'cursor:pointer;padding:16px',
      onclick: () => navigate(`#/equipment/${e.id}`)
    },
      h('div', { style: 'display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:12px' },
        h('div', { style: 'display:flex;gap:10px;align-items:center' },
          h('div', { style: 'width:36px;height:36px;border-radius:10px;background:var(--c-surface-2);border:1px solid var(--c-border);display:flex;align-items:center;justify-content:center' },
            h('span', { html: icon('equipment'), style: 'width:18px;height:18px;color:var(--c-text-2)' })
          ),
          h('div', {},
            h('div', { class: 'ltr mono small faint' }, e.code),
            h('div', { style: 'font-weight:600;font-size:13px' }, e.name)
          )
        ),
        critBadge(e.criticality, CRIT_FA[e.criticality])
      ),
      h('div', { class: 'small', style: 'display:flex;flex-direction:column;gap:4px;color:var(--c-text-2)' },
        h('div', {}, `🏭 ${e.factory?.name || '—'} · 🗂 ${e.category?.name || '—'}`),
        h('div', { style: 'display:flex;gap:8px;align-items:center;margin-top:8px' },
          statusBadge(e.status),
          h('span', { class: 'small faint' }, e.location || '')
        )
      )
    ));

    content.replaceChildren(
      h('div', { style: 'display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:12px' }, cards),
      h('div', { style: 'margin-top:16px;display:flex;justify-content:center' },
        pager(data.page, data.total, data.page_size, p => { state.page = p; load(); })
      )
    );
  }

  async function loadTree() {
    const qs = state.factory_id ? `?factory_id=${state.factory_id}` : '';
    const data = await api(`/equipment/tree${qs}`);

    const searchBox = h('input', {
      class: 'input',
      placeholder: 'جستجو در درخت تجهیزات...',
      style: 'height:36px',
    });

    const treeWrap = h('div', { class: 'tree-content' });
    const ul = h('ul', {});
    data.tree.forEach(f => ul.append(factoryNode(f, searchBox.value)));
    if (!data.tree.length) ul.append(h('li', { class: 'small faint', style: 'padding:20px;text-align:center' }, 'تجهیزی ثبت نشده — 45 تجهیز بسپار۱ بارگذاری شده'));

    // Filter on search
    searchBox.oninput = () => {
      const q = searchBox.value.trim().toLowerCase();
      ul.replaceChildren();
      data.tree.forEach(f => {
        const node = factoryNode(f, q);
        // Simple filter: if factory or its children match, show
        if (!q || f.name.toLowerCase().includes(q) || f.categories.some(c => c.name.toLowerCase().includes(q) || c.equipment.some(e => e.name.toLowerCase().includes(q) || e.code.toLowerCase().includes(q)))) {
          ul.append(node);
        }
      });
    };

    treeWrap.append(ul);

    content.replaceChildren(
      h('div', { style: 'display:grid;grid-template-columns:320px 1fr;gap:16px' },
        h('div', { class: 'tree-panel' },
          h('div', { class: 'tree-search' }, searchBox),
          treeWrap
        ),
        h('div', { class: 'card' },
          h('div', { class: 'card-body empty-state' },
            h('div', { class: 'empty-icon', html: icon('equipment') }),
            h('h3', {}, 'درخت تجهیزات BASPAR'),
            h('div', { class: 'small muted' }, 'ساختار: شرکت → کارخانه → سالن → خط → تجهیز → زیرسیستم → جزء → قطعه'),
            h('div', { class: 'small faint', style: 'margin-top:12px' }, 'برای مشاهده جزئیات، روی تجهیز کلیک کنید')
          )
        )
      )
    );
  }

  function factoryNode(f, filter = '') {
    const kids = h('ul', {});
    const caret = h('span', { class: 'caret open' }, '▾');
    const row = h('div', { class: 'node-row' },
      caret,
      h('span', { html: icon('factory'), style: 'width:16px;height:16px;color:var(--c-gold)' }),
      h('span', { class: 'node-title' }, f.name),
      h('span', { class: 'badge neutral', style: 'margin-inline-start:auto' }, faNum(f.categories.reduce((s, c) => s + c.equipment.length, 0)))
    );
    row.onclick = () => {
      const isHidden = kids.style.display === 'none';
      kids.style.display = isHidden ? '' : 'none';
      caret.textContent = isHidden ? '▾' : '▸';
      caret.classList.toggle('open', isHidden);
    };
    const li = h('li', {}, row, kids);
    f.categories.forEach(c => kids.append(categoryNode(c, filter)));
    return li;
  }

  function categoryNode(c, filter) {
    const kids = h('ul', {});
    const caret = h('span', { class: 'caret open' }, '▾');
    const row = h('div', { class: 'node-row' },
      caret,
      h('span', { html: icon('base'), style: 'width:14px;height:14px;color:var(--c-text-3)' }),
      h('span', { class: 'node-title' }, c.name),
      h('span', { class: 'small faint' }, `(${faNum(c.equipment.length)})`)
    );
    row.onclick = (ev) => {
      ev.stopPropagation();
      const isHidden = kids.style.display === 'none';
      kids.style.display = isHidden ? '' : 'none';
      caret.textContent = isHidden ? '▾' : '▸';
    };
    const li = h('li', {}, row, kids);
    c.equipment.forEach(e => {
      if (!filter || e.name.toLowerCase().includes(filter) || e.code.toLowerCase().includes(filter)) {
        kids.append(eqNode(e));
      }
    });
    return li;
  }

  function eqNode(e) {
    const kids = h('ul', { style: 'display:none' });
    const has = e.children && e.children.length > 0;
    const caret = h('span', { class: 'caret', style: has ? '' : 'visibility:hidden' }, '▸');
    const row = h('div', { class: 'node-row' },
      caret,
      h('span', { class: `status-dot ${e.status === 'active' ? 'success' : 'warning'}`, style: 'width:6px;height:6px' }),
      h('span', { class: 'node-title', style: 'font-size:12px' }, e.name),
      h('span', { class: 'small faint ltr mono', style: 'font-size:10px' }, e.code),
      h('span', { style: 'margin-inline-start:auto' }, critBadge(e.criticality, CRIT_FA[e.criticality]))
    );
    row.onclick = (ev) => {
      if (has && ev.target === caret) {
        const isHidden = kids.style.display === 'none';
        kids.style.display = isHidden ? '' : 'none';
        caret.textContent = isHidden ? '▾' : '▸';
        return;
      }
      navigate(`#/equipment/${e.id}`);
    };
    const li = h('li', {}, row, kids);
    if (has) e.children.forEach(c => kids.append(eqNode(c)));
    return li;
  }

  async function load() {
    content.replaceChildren(spinner());
    main.replaceChildren(
      h('div', { class: 'page-head' },
        h('div', {},
          h('h1', {}, 'مدیریت تجهیزات و دارایی‌ها'),
          h('div', { class: 'page-desc' }, 'ساختار درختی Enterprise: شرکت → کارخانه → خط → تجهیز → زیرسیستم')
        )
      ),
      toolbar(),
      h('div', { style: 'margin-top:16px' }, content)
    );
    try {
      if (state.view === 'list') await loadList();
      else if (state.view === 'card') await loadCard();
      else await loadTree();
    } catch (e) {
      content.replaceChildren(h('div', { class: 'card' },
        h('div', { class: 'card-body', style: 'color:var(--c-danger)' }, errText(e))
      ));
    }
  }

  await load();
}
