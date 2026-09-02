/** BASPAR CMMS — SELEN AI Assistant v2
 * Dark First · Gold Swan · Premium · Advisor
 * Provider-based, no auto-execution without human
 */

import { api, errText, h, toast, spinner, navigate } from '../core.js?v=12';
import { icon } from '../icons.js?v=12';

export async function renderSelen(main) {
  main.replaceChildren(
    h('div', { class: 'page-head' },
      h('div', { style: 'display:flex;gap:16px;align-items:center' },
        h('div', { style: 'width:48px;height:48px;border-radius:12px;background:var(--c-gold);display:flex;align-items:center;justify-content:center;box-shadow:var(--shadow-gold)' },
          h('span', { style: 'font-size:24px' }, '🦢')
        ),
        h('div', {},
          h('h1', { style: 'display:flex;gap:8px;align-items:center' },
            'SELEN',
            h('span', { style: 'font-family:var(--font-fa);font-weight:400;font-size:18px;color:var(--c-text-2)' }, 'سلن'),
            h('span', { class: 'badge gold', style: 'font-size:10px' }, 'AI')
          ),
          h('div', { class: 'page-desc' }, 'دستیار هوشمند نگهداری — تحلیل خرابی، پیشنهاد اقدام، تخمین قطعات')
        )
      ),
      h('div', { class: 'spacer' }),
      h('span', { class: 'badge neutral' }, 'Advisor · توصیه ≠ تصمیم نهایی')
    ),
    h('div', { class: 'card', style: 'background:linear-gradient(135deg,var(--c-card),var(--c-surface));border-color:var(--c-gold-border);margin-bottom:16px' },
      h('div', { class: 'card-body', style: 'display:flex;gap:16px;align-items:center' },
        h('div', { style: 'width:40px;height:40px;border-radius:10px;background:var(--c-gold-soft);border:1px solid var(--c-gold-border);display:flex;align-items:center;justify-content:center;color:var(--c-gold)' },
          h('span', { html: icon('sparkles'), style: 'width:20px;height:20px' })
        ),
        h('div', { class: 'small', style: 'flex:1' },
          h('div', { style: 'font-weight:600;color:var(--c-text)' }, 'SELEN چطور کمک می‌کند؟'),
          h('div', { style: 'color:var(--c-text-2);margin-top:4px;line-height:1.6' },
            'شرح مشکل + مشخصات تجهیز را بدهید؛ SELEN احتمال خرابی، چک‌لیست بررسی، اقدامات به ترتیب اولویت، قطعات احتمالی، ابزار و نکات ایمنی را پیشنهاد می‌دهد. تصمیم نهایی همیشه با انسان است.'
          )
        )
      )
    )
  );

  const content = h('div', {});
  main.append(content);
  content.append(spinner('در حال بارگذاری تجهیزات...'));

  let equipment = [];
  try { equipment = (await api('/equipment?level=equipment&page_size=200')).items; } catch {}

  const eqSel = h('select', { class: 'select', style: 'height:40px' },
    h('option', { value: '' }, 'انتخاب تجهیز...'),
    ...equipment.map(e => h('option', { value: String(e.id) }, `${e.code} — ${e.name} (${e.criticality_fa || e.criticality})`))
  );

  const desc = h('textarea', {
    class: 'textarea',
    placeholder: 'مثال: صدای غیرعادی از یاتاقان سمت کوپلینگ، افزایش دما به 85 درجه، لرزش زیاد...',
    style: 'min-height:100px'
  });

  const askBtn = h('button', { class: 'btn btn-primary btn-lg', style: 'width:100%' },
    h('span', { html: icon('sparkles'), style: 'width:16px;height:16px' }),
    'دریافت تحلیل هوشمند SELEN'
  );

  const out = h('div', { style: 'margin-top:20px' });

  askBtn.onclick = async () => {
    if (!eqSel.value || desc.value.trim().length < 3) {
      toast('تجهیز و شرح مشکل را وارد کنید', 'warning');
      return;
    }
    askBtn.disabled = true;
    askBtn.textContent = 'در حال تحلیل...';
    out.replaceChildren(spinner('SELEN در حال تحلیل با دانش فنی بسپار...'));
    try {
      const r = await api('/selen/diagnose', {
        method: 'POST',
        body: { equipment_id: +eqSel.value, description: desc.value.trim() }
      });
      out.replaceChildren(renderResult(r));
    } catch (e) {
      out.replaceChildren(h('div', { class: 'card', style: 'border-color:var(--c-danger-border)' },
        h('div', { class: 'card-body', style: 'color:var(--c-danger)' }, errText(e))
      ));
    }
    askBtn.disabled = false;
    askBtn.innerHTML = `${icon('sparkles')} دریافت تحلیل هوشمند SELEN`;
  };

  content.replaceChildren(
    h('div', { class: 'card' },
      h('div', { class: 'card-head' },
        h('h2', { style: 'display:flex;gap:8px;align-items:center' },
          h('span', { html: icon('ai'), style: 'width:16px;height:16px;color:var(--c-gold)' }),
          'سؤال فنی جدید'
        ),
        h('span', { class: 'badge gold' }, 'Powered by BASPAR KB')
      ),
      h('div', { class: 'card-body' },
        h('div', { class: 'form-grid' },
          h('div', { class: 'field span-2' }, h('label', {}, 'تجهیز مرتبط *'), eqSel),
          h('div', { class: 'field span-2' }, h('label', {}, 'شرح مشکل *'), desc)
        ),
        h('div', { style: 'margin-top:20px' }, askBtn)
      )
    ),
    out
  );

  function renderResult(r) {
    return h('div', { class: 'card', style: 'border-color:var(--c-gold-border);box-shadow:var(--shadow-gold)' },
      h('div', { class: 'card-head', style: 'background:var(--c-gold-soft)' },
        h('h2', { style: 'display:flex;gap:8px;align-items:center;color:var(--c-gold)' },
          h('span', { html: icon('sparkles'), style: 'width:16px;height:16px' }),
          'نتیجه تحلیل SELEN'
        ),
        h('span', { class: 'badge neutral small' }, `Provider: ${r.provider}`)
      ),
      h('div', { class: 'card-body' },
        h('div', { style: 'display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:20px' },
          h('div', {},
            h('h3', { style: 'display:flex;gap:6px;align-items:center;margin-bottom:12px' },
              h('span', { style: 'width:20px;height:20px;border-radius:6px;background:var(--c-danger-soft);color:var(--c-danger);display:flex;align-items:center;justify-content:center;font-size:10px' }, '1'),
              'خرابی‌های محتمل'
            ),
            h('div', { style: 'display:flex;flex-direction:column;gap:8px' },
              ...r.probable_failures.map(f => h('div', { style: 'display:flex;justify-content:space-between;align-items:center;padding:8px 12px;background:var(--c-surface-2);border:1px solid var(--c-border);border-radius:8px' },
                h('span', { style: 'font-size:12px' }, f.title),
                h('span', { class: `badge ${f.likelihood_pct >= 40 ? 'danger' : f.likelihood_pct >= 20 ? 'warning' : 'neutral'}` }, `${f.likelihood_pct}٪`)
              ))
            )
          ),
          h('div', {},
            h('h3', { style: 'display:flex;gap:6px;align-items:center;margin-bottom:12px' },
              h('span', { style: 'width:20px;height:20px;border-radius:6px;background:var(--c-warning-soft);color:var(--c-warning);display:flex;align-items:center;justify-content:center;font-size:10px' }, '2'),
              'موارد بررسی'
            ),
            h('ul', { style: 'margin:0;padding-inline-start:16px;font-size:12px;line-height:1.8;color:var(--c-text-2)' },
              ...(r.checklist || []).map(x => h('li', {}, typeof x === 'string' ? x : x.title))
            )
          )
        ),

        h('div', { style: 'display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:20px' },
          h('div', {},
            h('h3', { style: 'display:flex;gap:6px;align-items:center;margin-bottom:12px' },
              h('span', { style: 'width:20px;height:20px;border-radius:6px;background:var(--c-info-soft);color:var(--c-info);display:flex;align-items:center;justify-content:center;font-size:10px' }, '3'),
              'اقدامات پیشنهادی'
            ),
            h('ol', { style: 'margin:0;padding-inline-start:20px;font-size:12px;line-height:1.8' },
              ...(r.suggested_actions || []).map(x => h('li', {}, typeof x === 'string' ? x : x.title))
            )
          ),
          h('div', {},
            h('h3', { style: 'margin-bottom:12px' }, 'قطعات و ابزار'),
            h('div', { style: 'margin-bottom:12px' },
              h('div', { class: 'small faint', style: 'margin-bottom:6px' }, 'قطعات احتمالی:'),
              h('div', { class: 'chip-row' }, (r.probable_parts || []).map(p => h('span', { class: 'badge neutral' }, p)))
            ),
            h('div', {},
              h('div', { class: 'small faint', style: 'margin-bottom:6px' }, 'ابزار مورد نیاز:'),
              h('div', { class: 'chip-row' }, (r.required_tools || []).map(p => h('span', { class: 'badge info' }, p)))
            )
          )
        ),

        h('div', { style: 'background:var(--c-danger-soft);border:1px solid var(--c-danger-border);border-radius:8px;padding:12px' },
          h('h3', { style: 'color:var(--c-danger);font-size:12px;margin-bottom:8px;display:flex;gap:6px;align-items:center' },
            h('span', { html: icon('alert'), style: 'width:14px;height:14px' }), 'نکات ایمنی'
          ),
          h('ul', { style: 'margin:0;padding-inline-start:16px;font-size:11px;color:var(--c-danger);line-height:1.6' },
            ...(r.safety_notes || []).map(s => h('li', {}, s))
          )
        ),

        h('div', { class: 'small faint', style: 'margin-top:16px;border-top:1px solid var(--c-border-subtle);padding-top:12px' }, r.disclaimer),

        h('div', { style: 'margin-top:16px;display:flex;gap:8px' },
          h('button', { class: 'btn btn-primary btn-sm', onclick: () => navigate('#/requests') },
            h('span', { html: icon('plus'), style: 'width:12px;height:12px' }), 'ثبت درخواست بر اساس تحلیل'
          ),
          h('button', { class: 'btn btn-secondary btn-sm', onclick: () => { desc.value = ''; eqSel.value = ''; out.replaceChildren(); } }, 'سؤال جدید')
        )
      )
    );
  }
}
