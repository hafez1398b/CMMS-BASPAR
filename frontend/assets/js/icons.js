/** BASPAR CMMS — Icon System v2
 *  Minimal · Premium · Enterprise — Feather style + Custom logos
 *  Gold accent for brand, consistent stroke
 */

const P = (inner, size = 24) =>
  `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${size} ${size}" width="${size}" height="${size}" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${inner}</svg>`;

const F = (inner, size = 24) =>
  `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${size} ${size}" width="${size}" height="${size}" fill="currentColor">${inner}</svg>`;

export const ICONS = {
  // Core navigation
  dashboard: P('<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/>'),
  equipment: P('<path d="M12 20a8 8 0 1 0 0-16 8 8 0 0 0 0 16Z"/><path d="M12 14a2 2 0 1 0 0-4 2 2 0 0 0 0 4Z"/><path d="M12 2v2"/><path d="M12 20v2"/><path d="M2 12h2"/><path d="M20 12h2"/><path d="M4.93 4.93l1.41 1.41"/><path d="M17.66 17.66l1.41 1.41"/><path d="M19.07 4.93l-1.41 1.41"/><path d="M6.34 17.66l-1.41 1.41"/>'),
  factory: P('<path d="M2 20V8l4-4h4l2 2h6v14H2Z"/><path d="M6 20v-6"/><path d="M10 20v-8"/><path d="M14 20v-4"/><path d="M18 20v-10"/>'),
  requests: P('<path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><rect x="8" y="2" width="8" height="4" rx="1"/>'),
  workorders: P('<path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/>'),
  import: P('<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>'),
  charge: P('<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/>'),
  checklists: P('<polyline points="9 11 12 14 22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/>'),
  parts: P('<path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/>'),
  notifications: P('<path d="M6 8a6 6 0 0 1 12 0c0 7 6 5 6 10H0s6-3 6-10"/><path d="M10 20a2 2 0 0 0 4 0"/>'),
  selen: P('<path d="M12 2a7 7 0 0 0-7 7c0 3.5 2 6 7 10 5-4 7-6.5 7-10a7 7 0 0 0-7-7Z"/><path d="M9 9c0-1 1.2-2 3-2s3 1 3 2-1.2 2-3 2-3-1-3-2Z"/>'),
  risks: P('<path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>'),
  calibration: P('<circle cx="12" cy="12" r="10"/><polyline points="16 12 12 8 8 12"/><line x1="12" y1="16" x2="12" y2="8"/>'),
  reports: P('<line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/>'),
  consultation: P('<path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/>'),
  users: P('<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>'),
  roles: P('<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>'),
  base: P('<line x1="4" y1="21" x2="4" y2="14"/><line x1="4" y1="10" x2="4" y2="3"/><line x1="12" y1="21" x2="12" y2="12"/><line x1="12" y1="8" x2="12" y2="3"/><line x1="20" y1="21" x2="20" y2="16"/><line x1="20" y1="12" x2="20" y2="3"/><line x1="1" y1="14" x2="7" y2="14"/><line x1="9" y1="8" x2="15" y2="8"/><line x1="17" y1="16" x2="23" y2="16"/>'),
  audit: P('<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/>'),
  backup: P('<polyline points="21 8 21 21 3 21 3 8"/><rect x="1" y="3" width="22" height="5"/><line x1="10" y1="12" x2="14" y2="12"/>'),
  settings: P('<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/>'),
  search: P('<circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>'),
  plus: P('<line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>'),
  calendar: P('<rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/>'),
  clock: P('<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>'),
  trend_up: P('<polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/>'),
  trend_down: P('<polyline points="23 18 13.5 8.5 8.5 13.5 1 6"/><polyline points="17 18 23 18 23 12"/>'),
  activity: P('<path d="M22 12h-4l-3 9L9 3l-3 9H2"/>'),
  cost: P('<line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>'),
  alert: P('<path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>'),
  check: P('<polyline points="20 6 9 17 4 12"/>'),
  x: P('<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>'),
  chevron_down: P('<polyline points="6 9 12 15 18 9"/>'),
  chevron_right: P('<polyline points="9 18 15 12 9 6"/>'),
  chevron_left: P('<polyline points="15 18 9 12 15 6"/>'),
  menu: P('<line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="18" x2="21" y2="18"/>'),
  sun: P('<circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>'),
  moon: P('<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>'),
  ai: P('<path d="M12 2a10 10 0 0 0-9.95 9h11.64L9.74 7.05a1 1 0 0 1 1.5-1.32L16 10l-4.76 4.27a1 1 0 0 1-1.5-1.32L13.69 9H2.05A10 10 0 1 0 12 2Z"/>'),
  sparkles: P('<path d="M12 3l1.88 3.88L18 8.76l-4.12 1.88L12 14.5l-1.88-3.86L6 8.76l4.12-1.88L12 3Z"/><path d="M19 11l1 2 2 1-2 1-1 2-1-2-2-1 2-1 1-2Z"/><path d="M5 11l1 2 2 1-2 1-1 2-1-2-2-1 2-1 1-2Z"/>'),

  // Logos — custom
  bfg: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 60" width="100" height="60">
    <g fill="#DC2626">
      <path d="M15 18 L17 14 L21 13 L24 15 L26 11 L30 10 L33 13 L32 17 L35 20 L33 24 L29 26 L27 30 L23 31 L19 29 L16 26 L12 24 L14 20 Z M20 22 A4 4 0 1 1 20 22.1 Z"/>
      <path d="M50 8 L52 4 L56 3 L59 5 L61 1 L65 0 L68 3 L67 7 L70 10 L68 14 L64 16 L62 20 L58 21 L54 19 L51 16 L47 14 L49 10 Z M55 12 A4 4 0 1 1 55 12.1 Z"/>
      <path d="M40 32 L42 28 L46 27 L49 29 L51 25 L55 24 L58 27 L57 31 L60 34 L58 38 L54 40 L52 44 L48 45 L44 43 L41 40 L37 38 L39 34 Z M45 36 A4 4 0 1 1 45 36.1 Z"/>
    </g>
    <text x="18" y="25" font-family="sans-serif" font-weight="800" font-size="10" fill="white" text-anchor="middle">F</text>
    <text x="55" y="15" font-family="sans-serif" font-weight="800" font-size="10" fill="white" text-anchor="middle">B</text>
    <text x="45" y="39" font-family="sans-serif" font-weight="800" font-size="12" fill="white" text-anchor="middle">G</text>
  </svg>`,

  bfg_simple: F('<path d="M12 2L14 8H20L15 12L17 18L12 14L7 18L9 12L4 8H10L12 2Z"/>'),

  selen: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120" width="120" height="120">
    <defs><linearGradient id="gold" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#FDE68A"/><stop offset="50%" stop-color="#D4AF37"/><stop offset="100%" stop-color="#B8941F"/></linearGradient></defs>
    <path d="M60 10 C40 10, 20 25, 20 50 C20 75, 35 90, 60 95 C85 90, 100 75, 100 50 C100 35, 90 20, 75 15 C75 25, 80 35, 85 45 C80 40, 70 35, 60 35 C50 35, 40 40, 35 45 C35 35, 40 25, 45 15 C45 10, 50 10, 60 10 Z" fill="url(#gold)"/>
    <path d="M45 20 C42 15, 38 12, 35 18 C33 22, 35 26, 40 28 C42 24, 44 22, 45 20 Z" fill="url(#gold)"/>
  </svg>`,

  selen_simple: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="#D4AF37" stroke-width="1.8"><path d="M12 3 C8 3, 4 7, 4 12 C4 17, 7 20, 12 21 C17 20, 20 17, 20 12 C20 9, 18 5, 15 4 C15 7, 16 9, 17 11 C16 10, 14 9, 12 9 C10 9, 8 10, 7 11 C7 9, 8 7, 9 4 C9 3, 10 3, 12 3 Z"/></svg>`,

  baspar: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" width="32" height="32"><rect width="32" height="32" rx="8" fill="#D4AF37"/><text x="16" y="22" font-family="sans-serif" font-weight="800" font-size="18" text-anchor="middle" fill="#0A0A0A">B</text></svg>`,
};

export function icon(name) {
  return ICONS[name] || ICONS.dashboard;
}

export function iconWithColor(name, color) {
  const svg = ICONS[name] || ICONS.dashboard;
  if (!svg.includes('stroke="currentColor"')) return svg;
  return svg.replace('stroke="currentColor"', `stroke="${color}"`);
}
