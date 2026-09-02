/** Internal consultation / in-app messenger (§32 core — independent of
 *  any external service; external channels are add-ons only §32B). */
import { api, errText, h, toast, spinner, navigate } from '../core.js?v=12';
import { toJalaliStr } from '../jalali.js?v=12';

export async function renderConsultation(main) {
  main.replaceChildren(
    h('div', { class: 'page-head' },
      h('h1', {}, 'مشاوره و پیام‌رسانی داخلی'),
      h('div', { class: 'spacer' }),
      h('button', { class: 'btn btn-primary btn-sm', onclick: startConsultation }, 'مشاوره با مدیر فنی')),
    h('div', { style: 'display:grid;grid-template-columns:280px 1fr;gap:16px;min-height:60vh' },
      h('div', { class: 'card', id: 'conv-list' }, h('div', { class: 'card-body' }, spinner())),
      h('div', { class: 'card', id: 'chat-box' }, h('div', { class: 'card-body empty-state' },
        h('div', { class: 'empty-icon' }, '💬'),
        h('h3', {}, 'یک گفتگو انتخاب کنید')))));

  const listEl = main.querySelector('#conv-list');
  const chatEl = main.querySelector('#chat-box');
  let activeId = null;

  async function loadList() {
    try {
      const data = await api('/messages/conversations');
      if (!data.items.length) {
        listEl.replaceChildren(h('div', { class: 'card-body small faint' }, 'هنوز گفتگویی ندارید.'));
        return;
      }
      listEl.replaceChildren(h('div', { class: 'card-body' },
        ...data.items.map((c) => h('div', {
          class: 'node-row',
          style: `cursor:pointer;padding:10px;border-radius:8px;${c.id === activeId ? 'background:var(--c-primary-soft)' : ''}`,
          onclick: () => { activeId = c.id; loadList(); openChat(c.id); },
        },
          h('div', { style: 'display:flex;justify-content:space-between;width:100%' },
            h('strong', {}, c.other_name),
            c.unread ? h('span', { class: 'badge danger' }, String(c.unread)) : null),
          h('div', { class: 'small faint', style: 'white-space:nowrap;overflow:hidden;text-overflow:ellipsis' }, c.last_text || (c.subject || '')),
          h('div', { class: 'small faint ltr' }, toJalaliStr(c.last_at, true))))));
    } catch (e) { listEl.replaceChildren(h('div', { class: 'small', style: 'color:var(--c-danger)' }, errText(e))); }
  }

  async function openChat(cid) {
    chatEl.replaceChildren(h('div', { class: 'card-body' }, spinner()));
    try {
      const d = await api(`/messages/conversations/${cid}`);
      const msgs = h('div', { style: 'max-height:52vh;overflow-y:auto;display:flex;flex-direction:column;gap:8px' },
        ...d.messages.map((m) => h('div', {
          style: `max-width:75%;padding:8px 12px;border-radius:12px;font-size:13px;${m.mine
            ? 'background:var(--c-primary);color:#fff;align-self:flex-start;border-bottom-right-radius:2px'
            : 'background:var(--c-neutral-soft);align-self:flex-end;border-bottom-left-radius:2px'}`,
        },
          h('div', {}, m.text),
          h('div', { style: `font-size:10px;opacity:.7;margin-top:3px`, class: 'ltr' }, toJalaliStr(m.created_at, true)))));
      const inp = h('input', { class: 'input', placeholder: 'پیام خود را بنویسید…' });
      const sendBtn = h('button', { class: 'btn btn-primary' }, 'ارسال');
      async function send() {
        const text = inp.value.trim();
        if (!text) return;
        inp.value = '';
        try { await api(`/messages/conversations/${cid}/messages`, { method: 'POST', body: { text } }); openChat(cid); }
        catch (e) { toast(errText(e), 'danger'); }
      }
      sendBtn.onclick = send;
      inp.addEventListener('keydown', (e) => { if (e.key === 'Enter') send(); });
      chatEl.replaceChildren(
        h('div', { class: 'card-head' }, h('h2', {}, d.other_name),
          d.subject ? h('span', { class: 'small faint' }, d.subject) : null),
        h('div', { class: 'card-body' }, msgs),
        h('div', { class: 'card-body', style: 'display:flex;gap:8px;border-top:1px solid var(--c-border)' }, inp, sendBtn));
      msgs.scrollTop = msgs.scrollHeight;
      setTimeout(() => inp.focus(), 50);
      window.refreshBell?.();
    } catch (e) { chatEl.replaceChildren(h('div', { class: 'card-body small', style: 'color:var(--c-danger)' }, errText(e))); }
  }

  async function startConsultation() {
    try {
      const r = await api('/messages/conversations', { method: 'POST',
        body: { with_role: 'technical_manager', subject: 'مشاوره با مدیر فنی' } });
      activeId = r.id;
      loadList(); openChat(r.id);
    } catch (e) {
      // fall back to contact picker when no technical_manager exists
      const contacts = await api('/messages/contacts').catch(() => ({ items: [] }));
      if (!contacts.items.length) { toast(errText(e), 'danger'); return; }
      const sel = h('select', { class: 'select' },
        ...contacts.items.map((u) => h('option', { value: String(u.id) }, `${u.full_name} — ${u.roles.join('، ')}`)));
      const okBtn = h('button', { class: 'btn btn-primary', onclick: async () => {
        try {
          const r = await api('/messages/conversations', { method: 'POST',
            body: { with_user_id: +sel.value, subject: 'مشاوره' } });
          m.close(); activeId = r.id; loadList(); openChat(r.id);
        } catch (err) { toast(errText(err), 'danger'); }
      } }, 'شروع گفتگو');
      const m = openModal({ title: 'انتخاب مخاطب', body: sel, footer: [okBtn] });
    }
  }

  await loadList();
}
