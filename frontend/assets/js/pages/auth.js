/** BASPAR CMMS — Login v2.1
 * Dark First · BFG Logo Animation · Print-ready
 */

import { Session, api, errText, h, mount, navigate, toast } from '../core.js?v=12';
import { icon } from '../icons.js?v=12';

export function renderLogin() {
  const username = h('input', { class: 'input', autocomplete: 'username', placeholder: 'admin', dir: 'ltr', style: 'height:42px;font-size:14px' });
  const password = h('input', { class: 'input', type: 'password', autocomplete: 'current-password', placeholder: '••••••••', dir: 'ltr', style: 'height:42px;font-size:14px' });
  const btn = h('button', { class: 'btn btn-primary btn-lg', style: 'width:100%;margin-top:12px;height:44px;font-weight:700' }, 'ورود به سامانه');
  const errBox = h('div', { class: 'small', style: 'color:var(--c-danger);min-height:20px;margin-top:10px' });

  async function submit() {
    errBox.textContent = '';
    btn.disabled = true;
    btn.textContent = 'در حال ورود…';
    try {
      const data = await api('/auth/login', {
        method: 'POST',
        body: { username: username.value.trim(), password: password.value },
      });
      Session.save(data.access_token, data.user, data.permissions);
      toast(`خوش آمدید، ${data.user.full_name}`, 'success');
      // Animate out BFG logo to corner before reload
      const splash = document.getElementById('bfg-splash');
      if (splash) {
        splash.style.transition = 'all 0.6s cubic-bezier(0.16,1,0.3,1)';
        splash.style.transform = 'scale(0.2) translate(-120vw, -80vh)';
        splash.style.opacity = '0';
      }
      setTimeout(() => {
        navigate('#/dashboard');
        location.reload();
      }, 400);
    } catch (e) {
      errBox.textContent = errText(e) + (e && e.status ? ` (کد: ${e.status})` : '');
    } finally {
      btn.disabled = false;
      btn.textContent = 'ورود به سامانه';
    }
  }

  btn.onclick = submit;
  [username, password].forEach(el => el.addEventListener('keydown', e => { if (e.key === 'Enter') submit(); }));

  // Splash — BFG logo full screen → corner animation
  const splash = h('div', {
    id: 'bfg-splash',
    style: `
      position:fixed;inset:0;z-index:9999;
      background:var(--c-bg);
      display:flex;align-items:center;justify-content:center;
      flex-direction:column;gap:20px;
      animation: splashFade 1.8s var(--ease) forwards;
    `
  },
    h('img', {
      src: '/assets/bfg-logo.png',
      alt: 'BFG Logo',
      style: `
        width:280px;height:auto;
        filter: drop-shadow(0 0 30px rgba(212,175,55,0.3));
        animation: splashLogo 1.6s cubic-bezier(0.16,1,0.3,1) forwards;
      `,
      onerror: function() { this.style.display='none'; this.nextSibling.style.display='flex'; }
    }),
    h('div', {
      style: `
        width:80px;height:80px;border-radius:16px;
        background:var(--c-gold);color:#0A0A0A;
        display:none;align-items:center;justify-content:center;
        font-weight:900;font-size:28px;
        box-shadow:0 0 40px rgba(212,175,55,0.4);
        animation: splashLogo 1.6s cubic-bezier(0.16,1,0.3,1) forwards;
      `
    }, 'BFG'),
    h('div', { style: 'text-align:center;animation: splashText 1.2s ease 0.3s both' },
      h('div', { style: 'font-size:18px;font-weight:700;color:var(--c-text);letter-spacing:-0.02em' }, 'شرکت بسپار فوم غرب'),
      h('div', { style: 'font-size:12px;color:var(--c-text-3);margin-top:4px;letter-spacing:0.05em' }, 'BASPAR FOAM GHARB · Industrial CMMS')
    )
  );

  // Inject keyframes for splash
  const style = h('style', {}, `
    @keyframes splashLogo {
      0% { transform: scale(0.3); opacity:0; }
      40% { transform: scale(1.1); opacity:1; }
      70% { transform: scale(1); opacity:1; }
      100% { transform: scale(0.28) translate(-115vw, -42vh); opacity:0; }
    }
    @keyframes splashText {
      0% { opacity:0; transform:translateY(10px); }
      100% { opacity:1; transform:translateY(0); }
    }
    @keyframes splashFade {
      0% { background:var(--c-bg); }
      60% { background:var(--c-bg); }
      100% { background:transparent; pointer-events:none; }
    }
    .login-wrap {
      background-image: 
        radial-gradient(800px 400px at 20% 10%, rgba(212,175,55,0.06), transparent 60%),
        radial-gradient(600px 300px at 90% 90%, rgba(212,175,55,0.04), transparent 60%),
        url('/assets/bfg-logo.png');
      background-size: auto, auto, 600px;
      background-position: center, center, 95% 10%;
      background-repeat: no-repeat;
      background-blend-mode: normal, normal, soft-light;
    }
    .login-wrap::before {
      content:"";
      position:absolute;
      inset:0;
      background: var(--c-bg);
      opacity:0.92;
      pointer-events:none;
    }
    .login-card { position:relative; z-index:1; }
  `);

  // Auto-remove splash after animation
  setTimeout(() => {
    if (splash && splash.parentNode) {
      splash.style.opacity = '0';
      splash.style.pointerEvents = 'none';
      setTimeout(() => splash.remove(), 600);
    }
  }, 1800);

  mount(h('div', {},
    style,
    splash,
    h('div', { class: 'login-wrap' },
      h('div', { class: 'login-card' },
        h('div', { class: 'login-brand' },
          h('div', {},
            h('div', { class: 'logo-row', style: 'display:flex;align-items:center;gap:12px' },
              h('img', {
                src: '/assets/bfg-logo.png',
                alt: 'BFG',
                style: 'width:42px;height:42px;object-fit:contain;border-radius:10px;background:#fff;padding:4px;border:1px solid var(--c-border)',
                onerror: function() { this.outerHTML = `<span class="logo-mark" style="width:42px;height:42px">BFG</span>`; }
              }),
              h('div', {},
                h('div', { style: 'font-weight:800;color:#fff;font-size:14px;letter-spacing:-0.01em' }, 'BASPAR CMMS'),
                h('div', { style: 'font-size:10px;color:var(--c-text-3);letter-spacing:0.08em;text-transform:uppercase' }, 'AI Maintenance Platform')
              )
            ),
            h('h1', { style: 'margin-top:24px;font-size:22px;line-height:1.3' }, 'سامانه مدیریت نت هوشمند بسپار'),
            h('p', { style: 'color:var(--c-text-2);font-size:13px;line-height:1.8;margin-top:10px' },
              'پلتفرم Enterprise نگهداری و تعمیرات: تجهیزات، دستورکارها، بازرسی، قطعات، کالیبراسیون، ریسک و دستیار هوشمند SELEN — Dark First، Real-Time و چندکاربره.'
            )
          ),
          h('div', { class: 'login-feats' },
            h('span', {}, h('span', { class: 'feat-icon' }, '◐'), 'طراحی Dark First با Gold Accent'),
            h('span', {}, h('span', { class: 'feat-icon' }, '◑'), 'داشبورد Enterprise با KPI و آنالیتیکس'),
            h('span', {}, h('span', { class: 'feat-icon' }, '◒'), 'درخت تجهیزات و Workflow دستورکار'),
            h('span', {}, h('span', { class: 'feat-icon' }, '◓'), 'SELEN AI + تقویم شمسی + آفلاین'),
          ),
          h('div', { style: 'margin-top:28px;padding:12px;background:rgba(255,255,255,0.03);border:1px solid var(--c-border);border-radius:10px;display:flex;gap:10px;align-items:center' },
            h('img', {
              src: '/assets/bfg-logo.png',
              style: 'width:32px;height:32px;object-fit:contain;background:#fff;border-radius:6px;padding:2px',
              onerror: function() { this.style.display='none'; }
            }),
            h('div', {},
              h('div', { style: 'font-size:12px;font-weight:600;color:var(--c-text)' }, 'شرکت بسپار فوم غرب (سهامی خاص)'),
              h('div', { style: 'font-size:10px;color:var(--c-text-3)' }, 'BASPAR FOAM GHARB Co.')
            )
          )
        ),
        h('div', { class: 'login-form' },
          h('div', { style: 'display:flex;align-items:center;gap:12px;margin-bottom:24px' },
            h('img', {
              src: '/assets/bfg-logo.png',
              alt: 'BFG',
              style: 'width:40px;height:40px;object-fit:contain;border-radius:10px;background:#fff;padding:4px;border:1px solid var(--c-border)',
              onerror: function() { this.outerHTML = `<div style="width:40px;height:40px;border-radius:10px;background:var(--c-gold);color:#0A0A0A;display:flex;align-items:center;justify-content:center;font-weight:800">B</div>`; }
            }),
            h('div', {},
              h('h2', { style: 'margin:0;font-size:18px' }, 'ورود به سامانه'),
              h('div', { class: 'sub', style: 'margin:2px 0 0 0;font-size:12px' }, 'حساب کاربری خود را وارد کنید')
            )
          ),
          h('div', { class: 'field mb-4' }, h('label', {}, 'نام کاربری'), username),
          h('div', { class: 'field mb-4' }, h('label', {}, 'رمز عبور'), password),
          errBox,
          btn,
          h('div', { style: 'margin-top:20px;padding:12px;background:var(--c-surface-2);border:1px solid var(--c-border);border-radius:8px;font-size:12px;color:var(--c-text-2)' },
            h('div', { style: 'font-weight:600;margin-bottom:6px;display:flex;align-items:center;gap:6px' },
              h('span', { style: 'width:16px;height:16px;border-radius:4px;background:var(--c-gold);display:inline-flex;align-items:center;justify-content:center;color:#000;font-size:10px;font-weight:800' }, 'B'),
              'حساب پیش‌فرض:'
            ),
            h('div', { class: 'mono ltr', style: 'font-size:12px' }, 'admin / Admin@12345')
          ),
          h('div', { style: 'margin-top:20px;display:flex;justify-content:center;align-items:center;gap:8px' },
            h('img', { src: '/assets/selen-logo.png', style: 'width:24px;height:24px;object-fit:contain;opacity:0.8', onerror: function() { this.style.display='none'; } }),
            h('span', { style: 'font-size:11px;color:var(--c-text-3)' }, 'قدرت گرفته از SELEN AI · نسخه ۰٫۴ Enterprise')
          )
        )
      )
    )
  ));

  setTimeout(() => username.focus(), 2000);
}
