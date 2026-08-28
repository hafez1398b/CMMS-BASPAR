/** SELEN — دستیار هوشمند (§21/§22). Advisor only: AI Recommendation ≠ Final
 *  Decision; no sensitive operation ever runs without a human (§21). */
import { api, errText, h, toast, spinner, navigate } from '../core.js?v=11';

export async function renderSelen(main) {
  main.replaceChildren(
    h('div', { class: 'page-head' },
      h('h1', {}, 'SELEN — دستیار هوشمند نت'),
      h('div', { class: 'spacer' }),
      h('span', { class: 'badge info' }, 'Advisor · توصیه‌ها جایگزین تصمیم انسان نیست')),
    h('div', { class: 'card mb-4' }, h('div', { class: 'card-body small muted' },
      'شرح مشکل + مشخصات تجهیز را به SELEN بدهید؛ پیشنهاد شامل احتمال خرابی، موارد بررسی، ',
      'اقدامات به ترتیب، قطعات احتمالی، ابزار و نکات ایمنی است (§22). عکس و صوت در فاز بعدی اضافه می‌شوند.')));

  const content = h('div', {});
  main.append(content);
  content.append(spinner('در حال بارگذاری تجهیزات…'));

  let equipment = [];
  try { equipment = (await api('/equipment?level=equipment&page_size=200')).items; } catch { }

  const eqSel = h('select', { class: 'select' },
    h('option', { value: '' }, 'انتخاب تجهیز…'),
    ...equipment.map((e) => h('option', { value: String(e.id) },
      `${e.code} — ${e.name} (${e.criticality_fa || e.criticality})`)));
  const desc = h('textarea', { class: 'textarea', placeholder: 'شرح مشکل: مثلاً «صدای غیرعادی از یاتاقان سمت کوپلینگ و افزایش دما…»' });
  const askBtn = h('button', { class: 'btn btn-primary' }, '🧠 دریافت تحلیل SELEN');
  const out = h('div', { class: 'mt-4' });

  askBtn.onclick = async () => {
    if (!eqSel.value || desc.value.trim().length < 3) {
      toast('تجهیز و شرح مشکل را وارد کنید', 'warning'); return;
    }
    askBtn.disabled = true;
    out.replaceChildren(spinner('SELEN در حال تحلیل…'));
    try {
      const r = await api('/selen/diagnose', { method: 'POST', body: {
        equipment_id: +eqSel.value, description: desc.value.trim(),
      } });
      out.replaceChildren(renderResult(r));
    } catch (e) {
      out.replaceChildren(h('div', { class: 'small', style: 'color:var(--c-danger)' }, errText(e)));
    }
    askBtn.disabled = false;
  };

  content.replaceChildren(
    h('div', { class: 'card' },
      h('div', { class: 'card-head' }, h('h2', {}, 'سؤال فنی جدید')),
      h('div', { class: 'card-body' },
        h('div', { class: 'form-grid' },
          h('div', { class: 'field span-2' }, h('label', {}, 'تجهیز مرتبط *'), eqSel),
          h('div', { class: 'field span-2' }, h('label', {}, 'شرح مشکل *'), desc)),
        h('div', { class: 'mt-4' }, askBtn))),
    out);

  function renderResult(r) {
    const list = (items, cls = '') => h('ol', { class: `small ${cls}`, style: 'margin:6px 0;padding-inline-start:22px' },
      ...items.map((x) => h('li', {}, typeof x === 'string' ? x : x.title)));
    return h('div', { class: 'card', style: 'border-color:var(--c-primary)' },
      h('div', { class: 'card-head' },
        h('h2', {}, 'نتیجه تحلیل SELEN'),
        h('span', { class: 'small faint' }, `Provider: ${r.provider}`)),
      h('div', { class: 'card-body' },
        h('h3', {}, '۱. خرابی‌های محتمل'),
        h('div', { class: 'mb-4' }, r.probable_failures.map((f) =>
          h('div', { class: 'kv-row' },
            h('span', { style: 'flex:1' }, f.title),
            h('span', { class: `badge ${f.likelihood_pct >= 40 ? 'danger' : f.likelihood_pct >= 20 ? 'warning' : 'neutral'}` },
              `${f.likelihood_pct}٪`)))),
        h('div', { style: 'display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px' },
          h('div', {}, h('h3', {}, '۲. موارد بررسی'), list(r.checklist || [])),
          h('div', {}, h('h3', {}, '۳. اقدامات پیشنهادی (به ترتیب)'), list(r.suggested_actions || []))),
        h('div', { style: 'display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px' },
          h('div', {}, h('h3', {}, '۴. قطعات احتمالی'),
            h('div', { class: 'chip-row' }, (r.probable_parts || []).map((p) => h('span', { class: 'badge neutral' }, p)))),
          h('div', {}, h('h3', {}, '۵. ابزار موردنیاز'),
            h('div', { class: 'chip-row' }, (r.required_tools || []).map((p) => h('span', { class: 'badge info' }, p))))),
        h('h3', { class: 'mt-4' }, '۶. نکات ایمنی'),
        h('ul', { class: 'small', style: 'color:var(--c-danger);margin:6px 0' },
          ...(r.safety_notes || []).map((s) => h('li', {}, s))),
        h('div', { class: 'small muted mt-4', style: 'border-top:1px solid var(--c-border);padding-top:10px' },
          r.disclaimer),
        h('div', { class: 'mt-2' },
          h('button', { class: 'btn btn-secondary btn-sm', onclick: () => navigate('#/requests') },
            'ثبت درخواست کار بر اساس این تحلیل →'))));
  }
}
