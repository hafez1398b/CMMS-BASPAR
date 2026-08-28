/** Voice input (§38 MODULE EQUIPMENT) — cross-browser.
 *
 *  1) Where the Web Speech API exists (Chrome/Edge/Safari): live
 *     Speech-to-Text fa-IR into the target field.
 *  2) Firefox (no Web Speech): the button still works — it records a
 *     voice note via MediaRecorder and hands the audio File to the
 *     caller (attached as a voice-note file), with a clear status toast.
 *  The button is ALWAYS visible so the feature is discoverable. */
import { toast } from './core.js?v=11';

export function addVoiceInput(target, onAudio) {
  const btn = document.createElement('button');
  btn.type = 'button';
  btn.className = 'btn btn-ghost btn-sm';
  btn.title = 'ورود صوتی (تبدیل گفتار به متن / یادداشت صوتی)';
  btn.innerHTML =
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:15px;height:15px"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></svg>';

  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  let rec = null, active = false, chunks = [], mediaRec = null;

  const setOn = (on) => {
    active = on;
    btn.style.color = on ? 'var(--c-danger)' : '';
    btn.style.background = on ? 'var(--c-danger-soft)' : '';
    btn.title = on ? 'در حال ضبط… (کلیک برای پایان)' : btn.title;
  };

  btn.onclick = () => {
    if (active) { (rec || mediaRec)?.stop(); return; }

    if (SR) {
      /* ---------- live speech-to-text ---------- */
      rec = new SR();
      rec.lang = 'fa-IR';
      rec.continuous = true;
      rec.interimResults = true;
      let finalText = target.value ? target.value + ' ' : '';
      rec.onresult = (e) => {
        let interim = '';
        for (let i = e.resultIndex; i < e.results.length; i++) {
          const t = e.results[i][0].transcript;
          if (e.results[i].isFinal) finalText += t + ' ';
          else interim += t;
        }
        target.value = finalText + interim;
        target.dispatchEvent(new Event('input', { bubbles: true }));
      };
      rec.onend = () => setOn(false);
      rec.onerror = (e) => {
        setOn(false);
        if (e.error === 'not-allowed') toast('دسترسی میکروفون رد شد', 'warning');
      };
      try { rec.start(); setOn(true); toast('گوش می‌دهم… (فارسی)', 'info', 1800); }
      catch { setOn(false); }
      return;
    }

    /* ---------- Firefox fallback: record a voice note ---------- */
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
      toast('مرورگر شما از ورود صوتی پشتیبانی نمی‌کند (Chrome/Edge پیشنهاد می‌شود)', 'warning', 5000);
      return;
    }
    navigator.mediaDevices.getUserMedia({ audio: true })
      .then((stream) => {
        chunks = [];
        mediaRec = new MediaRecorder(stream);
        mediaRec.ondataavailable = (e) => chunks.push(e.data);
        mediaRec.onstop = () => {
          stream.getTracks().forEach((t) => t.stop());
          setOn(false);
          const blob = new Blob(chunks, { type: mediaRec.mimeType || 'audio/webm' });
          const file = new File([blob], `یادداشت-صوتی-${Date.now()}.webm`, { type: blob.type });
          toast('یادداشت صوتی ضبط شد و به‌صورت فایل پیوست می‌شود', 'success');
          if (onAudio) onAudio(file);
        };
        mediaRec.start();
        setOn(true);
        toast('در حال ضبط یادداشت صوتی… (کلیک برای پایان)', 'info', 2500);
      })
      .catch(() => toast('دسترسی میکروفون رد شد', 'warning'));
  };
  return btn;
}

/** Mount voice buttons on every textarea inside a root element. */
export function enableVoiceInputs(root, onAudio) {
  root.querySelectorAll('textarea').forEach((ta) => {
    if (ta.dataset.voiceAttached) return;
    ta.dataset.voiceAttached = '1';
    const btn = addVoiceInput(ta, onAudio);
    if (btn) ta.parentElement.appendChild(btn);
  });
}
