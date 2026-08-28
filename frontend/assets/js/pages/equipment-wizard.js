/** ویزارد افزودن تجهیز — ۹ مرحله (§6). Clean rewrite. */
import { Session, api, errText, h, navigate, toast, faNum, faToEnDigits } from '../core.js?v=11';
import { icon } from '../icons.js?v=11';
import { enableVoiceInputs } from '../voice.js?v=11';

const CRIT_FA = { low: 'کم', medium: 'متوسط', high: 'زیاد', critical: 'بحرانی' };
const STEPS = ['شناسایی', 'اطلاعات فنی', 'ساختار', 'برنامه نت', 'چک‌لیست', 'اسناد', 'کالیبراسیون', 'بحرانی‌بودن/ریسک', 'تأیید'];

export async function renderWizard(main) {
  const S = {
    step: 0,
    code: '', name: '', category_id: '', factory_id: '', component_type: '', status: 'active',
    manufacturer: '', model: '', serial_number: '', year: '', country: '',
    specs: {}, hall: '', dept: '', line: '', position: '',
    structure: [], selen: null, plans: [], checklist_tpl: '', files: [],
    calib: { enabled: false, standard: '', date: '', interval_days: 365 },
    criticality: 'medium', risk_title: '', risk_prob: 3, risk_impact: 3,
  };
  let factories = [], categories = [], types = [], actTypes = [], intervals = [], tpl = [];
  try {
    [factories, categories] = await Promise.all([api('/factories').then((d) => d.items), api('/categories').then((d) => d.items)]);
    const lk = await api('/lookups');
    types = lk.items.filter((x) => x.list_code === 'component_type' && x.is_active);
    actTypes = lk.items.filter((x) => x.list_code === 'activity_type' && x.is_active);
    intervals = lk.items.filter((x) => x.list_code === 'interval' && x.is_active);
    tpl = (await api('/checklists/templates')).items;
  } catch (e) { toast(errText(e), 'danger'); }

  const body = h('div', {});
  main.replaceChildren(
    h('div', { class: 'page-head' },
      h('div', { class: 'breadcrumb' }, h('a', { href: '#/equipment' }, 'تجهیزات'), '‹', h('span', {}, 'افزودن تجهیز')),
      h('div', { class: 'spacer' }),
      h('h1', {}, 'ایجاد پرونده تجهیز')),
    h('div', { class: 'card' }, h('div', { class: 'card-body' }, body))
  );

  const field = (label, node, req) => h('div', { class: 'field' }, h('label', {}, label + (req ? ' *' : '')), node);
  const inp = (key, ltr, ph) => h('input', { class: 'input', dir: ltr ? 'ltr' : 'rtl', value: S[key] || '', placeholder: ph || '', oninput: (e) => S[key] = e.target.value });

  /** بررسی زنده تکراری‌نبودن کد تجهیز (با تأخیر برای جلوگیری از فشار روی سرور) */
  let codeTimer = null;
  function watchCodeDup(input, hint) {
    input.addEventListener('blur', () => check());
    input.addEventListener('input', () => { clearTimeout(codeTimer); codeTimer = setTimeout(check, 600); });
    async function check() {
      const code = input.value.trim();
      if (!code) { hint.textContent = ''; return; }
      try {
        const d = await api(`/equipment?q=${encodeURIComponent(code)}&level=all&page_size=20`);
        const hit = (d.items || []).find((x) => x.code.toLowerCase() === code.toLowerCase());
        if (hit) {
          hint.textContent = `⚠ کد «${code}» قبلاً برای «${hit.name}» ثبت شده است`;
          hint.className = 'small';
          hint.style.color = 'var(--c-danger)';
        } else {
          hint.textContent = '✔ کد یکتا است';
          hint.className = 'small';
          hint.style.color = 'var(--c-success)';
        }
      } catch { hint.textContent = ''; }
    }
  }

  function stepper() {
    return h('div', { class: 'chip-row mb-4', style: 'flex-wrap:wrap' },
      ...STEPS.map((s, i) => h('span', {
        class: `badge ${i === S.step ? 'primary' : i < S.step ? 'success' : 'neutral'}`,
        style: 'font-size:12px;cursor:pointer', onclick: () => { if (i < S.step) { S.step = i; draw(); } },
      }, `${faNum(i + 1)} ${s}`)));
  }

  function nav(skip) {
    const skippable = S.step >= 1 && S.step <= 7;
    return h('div', { class: 'mt-4', style: 'display:flex;gap:10px' },
      S.step > 0 ? h('button', { class: 'btn btn-secondary', onclick: () => { S.step--; draw(); } }, '→ قبلی') : null,
      h('button', { class: 'btn btn-primary', onclick: () => {
        if (S.step === 0) {
          if (!S.code.trim() || !S.name.trim() || !S.factory_id || !S.category_id) {
            toast('کد، نام، کارخانه و دسته الزامی است', 'warning'); return;
          }
          api(`/equipment?q=${encodeURIComponent(S.code.trim())}&level=all&page_size=20`)
            .then((d) => {
              const hit = (d.items || []).find((x) => x.code.toLowerCase() === S.code.trim().toLowerCase());
              if (hit) { toast(`کد تکراری است — قبلاً برای «${hit.name}» ثبت شده`, 'danger', 6000); return; }
              S.step++; draw();
            })
            .catch(() => { S.step++; draw(); });
          return;
        }
        S.step++; draw();
      } }, S.step === STEPS.length - 2 ? 'مشاهده خلاصه' : 'ادامه ←'),
      skip && skippable ? h('button', { class: 'btn btn-ghost', onclick: () => { S.step++; draw(); } }, 'رد شدن') : null);
  }

  const steps = [];
  steps[0] = () => {
    const f = h('select', { class: 'select' }, h('option', { value: '' }, 'انتخاب…'), ...factories.map((x) => h('option', { value: String(x.id) }, x.name)));
    f.value = S.factory_id; f.onchange = () => S.factory_id = f.value;
    const c = h('select', { class: 'select' }, h('option', { value: '' }, 'انتخاب…'), ...categories.map((x) => h('option', { value: String(x.id) }, x.name)));
    c.value = S.category_id; c.onchange = () => S.category_id = c.value;
    const t = h('select', { class: 'select' }, h('option', { value: '' }, '—'), ...types.map((x) => h('option', { value: x.title_fa }, x.title_fa)));
    t.value = S.component_type; t.onchange = () => S.component_type = t.value;
    const st = h('select', { class: 'select' }, ...[['active', 'فعال'], ['inactive', 'غیرفعال'], ['under_maintenance', 'در تعمیر'], ['scrapped', 'اسقاط']].map(([k, v]) => h('option', { value: k }, v)));
    st.value = S.status; st.onchange = () => S.status = st.value;
    const codeInput = inp('code', true, 'B1PT-001');
    const codeHint = h('div', { class: 'small' });
    watchCodeDup(codeInput, codeHint);
    return [h('div', { class: 'form-grid' },
      field('کد تجهیز', h('div', {}, codeInput, codeHint), true),
      field('نام تجهیز', inp('name', false), true),
      field('کارخانه', f, true), field('دسته', c, true),
      field('نوع قطعه', t), field('وضعیت', st))];
  };
  steps[1] = () => {
    const specBox = h('div', {});
    function drawSpecs() {
      const rows = Object.entries(S.specs).map(([k, v]) => h('div', { class: 'kv-row' },
        h('input', { class: 'input', value: k, readonly: true, style: 'max-width:200px' }),
        h('input', { class: 'input', value: v, oninput: (e) => S.specs[k] = e.target.value }),
        h('button', { class: 'btn btn-ghost btn-sm', onclick: () => { delete S.specs[k]; drawSpecs(); } }, '✕')));
      const kI = h('input', { class: 'input', placeholder: 'مشخصه', style: 'max-width:200px' });
      const vI = h('input', { class: 'input', placeholder: 'مقدار' });
      specBox.replaceChildren(rows, h('div', { class: 'kv-row' }, kI, vI,
        h('button', { class: 'btn btn-secondary btn-sm', onclick: () => { if (kI.value.trim()) { S.specs[kI.value.trim()] = vI.value; drawSpecs(); } } }, '+ مشخصه')));
    }
    drawSpecs();
    return [h('div', { class: 'form-grid' },
      field('سازنده', inp('manufacturer')), field('مدل', inp('model')),
      field('شماره سریال', inp('serial_number', true)), field('سال ساخت', inp('year', true, 'میلادی — مثال: 2019')),
      field('کشور سازنده', inp('country')), field('سالن', inp('hall')),
      field('بخش', inp('dept')), field('خط', inp('line')), field('موقعیت', inp('position'))),
      h('h3', { class: 'mt-4' }, 'مشخصات فنی پویا (§10)'), specBox];
  };
  steps[2] = () => {
    const box = h('div', {});
    const inStructure = (level, name) => S.structure.some((it) => it.level === level && it.name === name);

    function addSelenSubsystem(name) {
      if (!inStructure('subsystem', name)) { S.structure.push({ level: 'subsystem', name }); draw(); }
    }
    function addSelenComponent(subName, compName) {
      if (inStructure('component', compName)) return;
      // جزء حتماً زیر یک زیرسیستم است؛ اگر والد پیشنهادی هنوز اضافه نشده، اول آن را اضافه کن
      if (!inStructure('subsystem', subName)) S.structure.push({ level: 'subsystem', name: subName });
      S.structure.push({ level: 'component', name: compName });
      draw();
    }

    async function fetchSelen(btn) {
      btn.disabled = true; btn.textContent = 'در حال تحلیل…';
      try {
        const cat = categories.find((c) => String(c.id) === S.category_id)?.name || '';
        const d = await api('/selen/structure-suggestions', { method: 'POST', body: {
          name: S.name || null, category: cat || null,
          component_type: S.component_type || null, model: S.model || null,
        } });
        S.selen = d;
        toast(`SELEN بر اساس ${d.basis} پیشنهاد داد`, 'info', 4000);
      } catch (e) { toast(errText(e), 'danger'); }
      btn.disabled = false; draw();
    }

    function draw() {
      const tbl = h('div', { class: 'table-wrap card mb-4' },
        h('table', { class: 'table' },
          h('thead', {}, h('tr', {}, ['سطح', 'نام', ''].map((x) => h('th', {}, x)))),
          h('tbody', {}, S.structure.map((it, i) => {
            const row = h('tr', {},
              h('td', { class: 'small' }, it.level === 'subsystem' ? 'زیرسیستم' : 'جزء'),
              h('td', {}, it.name),
              h('td', {}, h('button', { class: 'btn btn-ghost btn-sm', onclick: () => { S.structure.splice(i, 1); draw(); } }, '−')));
            return row;
          }))));
      const none = h('div', { class: 'small faint mb-4' }, 'ساختاری تعریف نشده — از «🤖 پیشنهادات SELEN» استفاده کنید یا دستی اضافه کنید.');
      const onlyComp = S.structure.length > 0 && !S.structure.some((it) => it.level === 'subsystem');
      const hint = onlyComp
        ? h('div', { class: 'small mb-4', style: 'color:var(--c-warning, #b45309)' },
          'ℹ فقط «جزء» تعریف شده؛ هنگام ثبت، زیرسیستم ظرف «اجزای تجهیز» به‌صورت خودکار ساخته می‌شود.')
        : h('div', { class: 'small faint mb-4' },
          'الگوی کد: زیرسیستم «{کد}-S۱»، جزء «{کد}.۱» (سند ۰۳)');

      // §3B — دکمه ثابت پیشنهادات SELEN در بالای کارت ساختار
      const selenBtn = h('button', { class: 'btn btn-secondary mb-4', onclick: (e) => fetchSelen(e.currentTarget) },
        '🤖 پیشنهادات SELEN');

      const parts = [selenBtn];
      if (S.selen) {
        const sRows = [];
        for (const sub of S.selen.subsystems || []) {
          const added = inStructure('subsystem', sub.name);
          sRows.push(h('div', { class: 'kv-row', style: 'margin-bottom:4px' },
            h('strong', { style: 'flex:1' }, '▣ ', sub.name),
            added ? h('span', { class: 'badge success' }, 'اضافه شد')
                  : h('button', { class: 'btn btn-secondary btn-sm', onclick: () => addSelenSubsystem(sub.name) }, '+')));
          for (const c of sub.components || []) {
            const cAdded = inStructure('component', c);
            sRows.push(h('div', { class: 'kv-row', style: 'margin-bottom:4px;padding-inline-start:28px' },
              h('span', { class: 'small', style: 'flex:1' }, '◦ ', c),
              cAdded ? h('span', { class: 'badge success' }, 'اضافه شد')
                     : h('button', { class: 'btn btn-ghost btn-sm', onclick: () => addSelenComponent(sub.name, c) }, '+')));
          }
        }
        parts.push(h('div', { class: 'card mb-4', style: 'border:1px dashed var(--c-border)' },
          h('div', { class: 'card-body' },
            h('div', { style: 'display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;flex-wrap:wrap;gap:6px' },
              h('strong', {}, 'پیشنهادات ساختار'),
              h('span', { class: 'badge neutral' }, `مبنای پیشنهاد: ${S.selen.basis}`)),
            sRows,
            h('div', { class: 'small faint mt-2' }, 'SELEN فقط پیشنهاد می‌دهد؛ افزودن تنها با کلیک «+» انجام می‌شود (§14)'))));
      }
      parts.push(S.structure.length ? tbl : none, hint, addForm());
      box.replaceChildren(...parts);
    }
    function addForm() {
      const lvl = h('select', { class: 'select' }, h('option', { value: 'subsystem' }, 'زیرسیستم'), h('option', { value: 'component' }, 'جزء'));
      const nm = h('input', { class: 'input', placeholder: 'نام' });
      return h('div', { class: 'kv-row' }, lvl, nm,
        h('button', { class: 'btn btn-secondary btn-sm', onclick: () => { if (nm.value.trim()) { S.structure.push({ level: lvl.value, name: nm.value.trim() }); draw(); } } }, '+ افزودن دستی'));
    }
    draw();
    return [box];
  };
  steps[3] = () => {
    const box = h('div', {});
    function draw() {
      const tbl = h('div', { class: 'table-wrap card mb-4' },
        h('table', { class: 'table' },
          h('thead', {}, h('tr', {}, ['عنوان', 'نوع', 'تناوب', ''].map((x) => h('th', {}, x)))),
          h('tbody', {}, S.plans.map((p, i) => {
            const row = h('tr', {},
              h('td', {}, p.title),
              h('td', { class: 'small' }, actTypes.find((t) => t.code === p.type)?.title_fa || p.type),
              h('td', { class: 'small' }, intervals.find((t) => t.code === p.interval)?.title_fa || p.interval),
              h('td', {}, h('button', { class: 'btn btn-ghost btn-sm', onclick: () => { S.plans.splice(i, 1); draw(); } }, '✕')));
            return row;
          }))));
      const none = h('div', { class: 'small faint mb-4' }, 'برنامه‌ای تعریف نشده.');
      box.replaceChildren(S.plans.length ? tbl : none, addForm());
    }
    function addForm() {
      const ti = h('input', { class: 'input', placeholder: 'عنوان فعالیت' });
      const ty = h('select', { class: 'select' }, ...actTypes.map((t) => h('option', { value: t.code }, t.title_fa)));
      const iv = h('select', { class: 'select' }, ...intervals.map((t) => h('option', { value: t.code }, t.title_fa)));
      return h('div', { class: 'kv-row' }, ti, ty, iv,
        h('button', { class: 'btn btn-secondary btn-sm', onclick: () => { if (ti.value.trim()) { S.plans.push({ title: ti.value.trim(), type: ty.value, interval: iv.value }); draw(); } } }, '+ فعالیت'));
    }
    draw();
    return [box];
  };
  steps[4] = () => {
    const sel = h('select', { class: 'select' }, h('option', { value: '' }, '— بدون چک‌لیست —'), ...tpl.map((t) => h('option', { value: String(t.id) }, t.name)));
    sel.onchange = () => S.checklist_tpl = sel.value;
    return [field('چک‌لیست بازرسی مرتبط (§16)', sel)];
  };
  steps[5] = () => {
    const fi = h('input', { type: 'file', multiple: true, style: 'display:none' });
    fi.onchange = () => { S.files.push(...fi.files); draw(); };
    const list = h('div', {});
    function draw() {
      list.replaceChildren(S.files.length ? S.files.map((f, i) => h('div', { class: 'kv-row' },
        h('span', { style: 'flex:1' }, `📎 ${f.name}`),
        h('button', { class: 'btn btn-ghost btn-sm', onclick: () => { S.files.splice(i, 1); draw(); } }, '✕'))) :
        h('div', { class: 'small faint' }, 'فایلی انتخاب نشده.'));
    }
    draw();
    return [h('div', { class: 'upload-zone', onclick: () => fi.click() }, '📤 انتخاب فایل‌ها (§23)'), fi, list];
  };
  steps[6] = () => {
    const chk = h('input', { type: 'checkbox', ...(S.calib.enabled ? { checked: true } : {}) });
    chk.onchange = () => S.calib.enabled = chk.checked;
    const std = h('input', { class: 'input', value: S.calib.standard, placeholder: 'ISO 17025' });
    std.oninput = (e) => S.calib.standard = e.target.value;
    const iv = h('input', { class: 'input ltr', type: 'number', value: S.calib.interval_days });
    iv.oninput = (e) => S.calib.interval_days = +e.target.value || 365;
    return [h('div', { class: 'form-grid' },
      field('تجهیز اندازه‌گیری است؟ (§24)', chk),
      field('استاندارد', std), field('دوره (روز)', iv))];
  };
  steps[7] = () => {
    const crit = h('select', { class: 'select' }, ...Object.entries(CRIT_FA).map(([k, v]) => h('option', { value: k }, v)));
    crit.value = S.criticality; crit.onchange = () => S.criticality = crit.value;
    const risk = h('input', { class: 'input', value: S.risk_title, placeholder: 'ریسک اولیه (اختیاری)' });
    risk.oninput = (e) => S.risk_title = e.target.value;
    return [h('div', { class: 'form-grid' }, field('درجه بحرانی بودن', crit), field('ریسک اولیه (§26)', risk))];
  };
  steps[8] = () => {
    const kv = (k, v) => h('tr', {}, h('td', { class: 'muted small', style: 'width:190px' }, k), h('td', {}, v || '—'));
    const btn = h('button', { class: 'btn btn-primary' }, '✔ ایجاد پرونده تجهیز');
    btn.onclick = () => createAll(btn);
    return [h('div', { class: 'table-wrap card' }, h('table', { class: 'table spec-table' }, h('tbody', {}, [
      kv('کد', S.code), kv('نام', S.name),
      kv('کارخانه', factories.find((f) => String(f.id) === S.factory_id)?.name),
      kv('دسته', categories.find((c) => String(c.id) === S.category_id)?.name),
      kv('سازنده/مدل', [S.manufacturer, S.model].filter(Boolean).join(' / ')),
      kv('ساختار', `${faNum(S.structure.length)} آیتم`), kv('برنامه PM', `${faNum(S.plans.length)} فعالیت`),
      kv('اسناد', `${faNum(S.files.length)} فایل`), kv('بحرانی‌بودن', CRIT_FA[S.criticality]),
    ]))),
      h('div', { class: 'mt-4', style: 'display:flex;gap:10px' },
        h('button', { class: 'btn btn-secondary', onclick: () => { S.step--; draw(); } }, '→ قبلی'), btn)];
  };

  async function createAll(btn) {
    if (S.year) {
      const y = Number(faToEnDigits(String(S.year).trim()));
      if (!Number.isFinite(y)) { toast('سال ساخت باید عدد باشد', 'danger', 6000); S.step = 1; draw(); return; }
      if (y >= 1200 && y < 1500) { toast(`سال «${faNum(y)}» شمسی به نظر می‌رسد؛ سال ساخت باید میلادی باشد (مثلاً ۲۰۱۹)`, 'danger', 7000); S.step = 1; draw(); return; }
      if (y < 1800 || y > 2200) { toast('سال ساخت باید میلادی و بین ۱۸۰۰ تا ۲۲۰۰ باشد', 'danger', 6000); S.step = 1; draw(); return; }
      S.year = String(Math.trunc(y));
    }
    btn.disabled = true; btn.textContent = 'در حال ایجاد…';
    try {
      const eq = await api('/equipment', { method: 'POST', body: {
        code: S.code.trim(), name: S.name.trim(), level: 'equipment',
        factory_id: +S.factory_id, category_id: +S.category_id,
        component_type: S.component_type || null,
        manufacturer: S.manufacturer || null, model: S.model || null,
        serial_number: S.serial_number || null, year: S.year ? +S.year : null,
        criticality: S.criticality, status: S.status,
        hall: S.hall || null, dept: S.dept || null, line: S.line || null, position: S.position || null,
        technical_specs: S.specs,
      } });
      // ساختار: زیرسیستم → جزء (طبق §۱ سلسله‌مراتب، جزء حتماً زیر یک زیرسیستم است)
      const factoryId = eq.factory ? eq.factory.id : null;
      const categoryId = eq.category ? eq.category.id : null;
      let lastSub = null; let subSeq = 0; let compSeq = 0;
      const needsContainer = S.structure.length > 0
        && !S.structure.some((it) => it.level === 'subsystem');
      if (needsContainer) {
        // اگر فقط «جزء» تعریف شده باشد، یک زیرسیستم ظرف خودکار ساخته می‌شود
        const cont = await api('/equipment', { method: 'POST', body: {
          code: `${eq.code}-S1`, name: 'اجزای تجهیز', level: 'subsystem',
          parent_id: eq.id, factory_id: factoryId, category_id: categoryId,
          criticality: S.criticality, status: 'active',
        } });
        lastSub = cont.id; subSeq = 1;
      }
      for (const it of S.structure) {
        let code; let parentId;
        if (it.level === 'subsystem') {
          subSeq++;
          code = `${eq.code}-S${subSeq}`;
          parentId = eq.id;
        } else {
          // الگوی کد جزء: {کد تجهیز}.{شماره ترتیبی} — سند ۰۳
          compSeq++;
          code = `${eq.code}.${compSeq}`;
          parentId = lastSub || eq.id;
        }
        const child = await api('/equipment', { method: 'POST', body: {
          code, name: it.name, level: it.level,
          parent_id: parentId,
          factory_id: factoryId, category_id: categoryId,
          criticality: S.criticality, status: 'active',
        } });
        if (it.level === 'subsystem') lastSub = child.id;
      }
      for (const p of S.plans) await api('/plans', { method: 'POST', body: { equipment_id: eq.id, work_title: p.title, activity_type: p.type, interval_code: p.interval, work_class: 'pm' } });
      for (const f of S.files) { const fd = new FormData(); fd.append('file', f); await api(`/equipment/${eq.id}/files`, { method: 'POST', form: fd }); }
      if (S.calib.enabled && S.calib.date) await api('/calibration', { method: 'POST', body: { equipment_id: eq.id, standard: S.calib.standard || null, last_calibration_jalali: S.calib.date, interval_days: S.calib.interval_days } });
      if (S.risk_title.trim()) await api('/risks', { method: 'POST', body: { scope_type: 'equipment', kind: 'risk', equipment_id: eq.id, title: S.risk_title.trim(), probability: S.risk_prob, impact: S.risk_impact } });
      toast('پرونده تجهیز ایجاد شد', 'success');
      navigate(`#/equipment/${eq.id}`);
    } catch (e) {
      toast(errText(e), 'danger', 6000); btn.disabled = false; btn.textContent = '✔ ایجاد پرونده تجهیز';
    }
  }

  function draw() {
    body.replaceChildren(stepper(), ...steps[S.step](), S.step !== 8 ? nav(true) : h('div', {}));
    enableVoiceInputs(body, (file) => { S.files.push(file); toast('یادداشت صوتی به اسناد اضافه شد', 'success'); });
  }
  draw();
}
