/** Login page — real JWT authentication (Phase 0). */
import { Session, api, errText, h, mount, navigate, toast } from '../core.js?v=11';
import { icon } from '../icons.js?v=11';

export function renderLogin() {
  const username = h('input', { class: 'input', autocomplete: 'username', placeholder: 'نام کاربری', dir: 'ltr' });
  const password = h('input', { class: 'input', type: 'password', autocomplete: 'current-password', placeholder: 'رمز عبور', dir: 'ltr' });
  const btn = h('button', { class: 'btn btn-primary', style: 'width:100%' }, 'ورود به سامانه');
  const errBox = h('div', { class: 'small', style: 'color:var(--c-danger);min-height:20px' });

  async function submit() {
    errBox.textContent = '';
    btn.disabled = true; btn.textContent = 'در حال ورود…';
    try {
      const data = await api('/auth/login', {
        method: 'POST',
        body: { username: username.value.trim(), password: password.value },
      });
      Session.save(data.access_token, data.user, data.permissions);
      toast(`خوش آمدید، ${data.user.full_name}`, 'success');
      navigate('#/dashboard');
      location.reload(); // boot SSE + guards cleanly
    } catch (e) {
      errBox.textContent = errText(e) + (e && e.status ? ` (کد خطا: ${e.status})` : '');
    } finally {
      btn.disabled = false; btn.textContent = 'ورود به سامانه';
    }
  }

  btn.onclick = submit;
  [username, password].forEach((el) => el.addEventListener('keydown', (e) => { if (e.key === 'Enter') submit(); }));

  const feat = (t) => h('span', { html: icon('check') }, t);
  mount(h('div', { class: 'login-wrap' },
    h('div', { class: 'login-card' },
      h('div', { class: 'login-brand' },
        h('div', {},
          h('div', { class: 'logo-row' },
            h('span', { class: 'logo-mark', html: icon('workorders') }),
            h('div', {},
              h('div', { style: 'font-weight:800;color:#fff' }, 'BASPAR CMMS'),
              h('div', { style: 'font-size:11px;color:#8fa2c4' }, 'Industrial Maintenance Intelligence'))),
          h('h1', {}, 'سامانه مدیریت نت بسپار'),
          h('p', {}, 'پلتفرم یکپارچهٔ نگهداری و تعمیرات: تجهیزات، دستور کارها، بازرسی، قطعات، کالیبراسیون، ریسک و دستیار هوشمند SELEN — Real-Time و چندکاربره.')),
        h('div', { class: 'login-feats' },
          feat('پرونده دیجیتال تجهیز با ۱۲ تب'),
          feat('مرکز شارژ داده‌های قدیمی (Excel چندشیت)'),
          feat('تقویم شمسی + شناسنامهٔ چاپی/PDF'),
          feat('حالت آفلاین تکنسین با همگام‌سازی خودکار'))),
      h('div', { class: 'login-form' },
        h('h2', {}, 'ورود به سامانه'),
        h('div', { class: 'sub' }, 'برای ادامه، حساب کاربری خود را وارد کنید'),
        h('div', { class: 'field mb-4' }, h('label', {}, 'نام کاربری'), username),
        h('div', { class: 'field mb-4' }, h('label', {}, 'رمز عبور'), password),
        errBox,
        btn))));
  setTimeout(() => username.focus(), 60);
}
