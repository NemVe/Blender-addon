// The film's furniture: the panel's widgets (Blender's dark theme), the template's text motion, the cursor and the stripe wipe.
import { clamp, mix, ramp, e3, io, hump } from './lib.mjs';

export const stage = document.getElementById('stage');
export const view = { k: 1 };                 // the page's scale of the stage, set by main

export const h = html => { const t = document.createElement('template'); t.innerHTML = html.trim(); return t.content.firstElementChild; };
export const I = name => `<img src="/icons/${name}.png" alt="">`;
const id = o => (o && o.id ? ` id="${o.id}"` : '');

// ---- widgets: strings of HTML ----
export const btn = (label, o = {}) => `<div class="btn ${o.c || ''}"${id(o)}>${o.i ? I(o.i) : ''}<span>${label}</span></div>`;
export const fld = (label, val, fill = 0, o = {}) =>
  `<div class="fld ${o.c || ''}"${id(o)}><i class="fill" style="width:${(fill * 100).toFixed(1)}%"></i>${label !== '' ? `<span class="l">${label}</span>` : ''}<span class="v">${val}</span></div>`;
export const sec = (title, icon, o = {}) =>
  `<div class="sec"><i class="tri ${o.open === false ? 'shut' : ''}"></i>${I(icon)}<b>${title}</b>${o.right || ''}</div>`;
export const note = t => `<div class="note">${t}</div>`;
export const row = (inner, o = {}) => `<div class="row ${o.c || ''}"${id(o)}>${inner}</div>`;
export const lbl = (t, o = {}) => `<div class="lbl ${o.c || ''}"${id(o)}>${o.i ? I(o.i) : ''}<span>${t}</span></div>`;
export const cb = (on, o = {}) => `<i class="cb ${on ? 'on' : ''}"${id(o)}></i>`;
export const panel = (inner, o = {}) =>
  `<div class="ui"${id(o)}><div class="mh">${I('logo')}<b>CopyThat</b><span>${o.sub === undefined ? 'Move 1' : o.sub}</span></div>${inner}</div>`;
export const dialog = (title, rows, o = {}) =>
  `<div class="dlg"${id(o)}><h4>${title}</h4>${rows}<div class="btn on ok"${o.okId ? ` id="${o.okId}"` : ''}>OK</div></div>`;
export const prow = (label, inner, o = {}) => `<div class="pr"${id(o)}><div class="l">${label}</div><div class="f">${inner}</div></div>`;

// ---- the template: kicker, headline (**gold** key word), subline ----
export const kick = (n, label) => `<i>${n}</i>·&nbsp; ${label}`;
export const headHTML = s => s.split('\n').map(l => `<div class="ln"><span>${l.replace(/\*\*(.+?)\*\*/g, '<em>$1</em>')}</span></div>`).join('');
export const col = (k, hd, sub, mini) =>
  `<div class="col"><div class="kick">${k}</div><div class="hl">${headHTML(hd)}</div><div class="sub">${sub}</div>${mini ? `<div class="mini">${mini}</div>` : ''}</div>`;
export const card = (inner, o = {}) =>
  `<div class="card"${id(o)}><div class="cv"></div>${inner || ''}<div class="vig"></div></div>`;

const place = (el, op, dx, dy) => { el.style.opacity = op.toFixed(3); el.style.transform = `translate(${dx.toFixed(1)}px,${dy.toFixed(1)}px)`; };

// The text of a beat: the kicker fades and slides in, the headline lines slide up with a small stagger, then the subline and the
// mini UI; all of it fades out fast at the end. `dur` is the beat's length.
export function animText(root, lt, dur) {
  const ex = 1 - ramp(lt, dur - 0.3, dur - 0.08);
  const kk = root.querySelector('.kick');
  if (kk) { const u = ramp(lt, 0.0, 0.16); place(kk, u * ex, (1 - e3(u)) * -28, 0); }
  const lines = root.querySelectorAll('.ln');
  lines.forEach((el, i) => { const u = ramp(lt, 0.02 + 0.07 * i, 0.30 + 0.07 * i); place(el, clamp(u * 1.7) * ex, 0, (1 - e3(u)) * 52); });
  const sub = root.querySelector('.sub');
  const n = lines.length;
  if (sub) { const u = ramp(lt, 0.2 + 0.07 * n, 0.5 + 0.07 * n); place(sub, u * ex, 0, (1 - e3(u)) * 22); }
  const mini = root.querySelector('.mini');
  if (mini) { const u = ramp(lt, 0.32, 0.78); place(mini, u * ex, 0, (1 - e3(u)) * 34); }
}

// Where an element is, in stage pixels (the middle by default, or a fraction of its box). Call it with the beat shown and its
// text settled, so no entrance has it off its mark.
export function at(el, fx = 0.5, fy = 0.5) {
  const r = el.getBoundingClientRect();
  return [(r.left + r.width * fx) / view.k, (r.top + r.height * fy) / view.k];
}

// ---- the cursor: eased moves on gentle arcs, a press-scale pulse, a ripple and (for the audio) a list of clicks ----
const cur = document.getElementById('cur');
const rips = [...document.querySelectorAll('#rips i')];

export function pathPos(keys, lt) {
  if (lt <= keys[0].t) return [keys[0].x, keys[0].y];
  for (let i = 1; i < keys.length; i++) {
    const a = keys[i - 1], b = keys[i];
    if (lt <= b.t) {
      const u = ramp(lt, a.t, b.t);
      const e = b.lin ? u : io(u);
      const dx = b.x - a.x, dy = b.y - a.y, d = Math.hypot(dx, dy) || 1;
      const arc = b.straight || b.lin ? 0 : hump(e) * 0.09 * d * (i % 2 ? 1 : -1);
      return [mix(a.x, b.x, e) + (-dy / d) * arc, mix(a.y, b.y, e) + (dx / d) * arc];
    }
  }
  const z = keys[keys.length - 1];
  return [z.x, z.y];
}

// keys: [{t, x, y, straight?, lin?}], clicks: [{t, up?}], hold: seconds the cursor stays after its last key before it fades.
export function cursor(lt, keys, clicks = [], hold = 0.35) {
  if (!keys || !keys.length) { cur.style.opacity = 0; rips.forEach(r => { r.style.opacity = 0; }); return; }
  const [x, y] = pathPos(keys, lt);
  const t0 = keys[0].t, t1 = keys[keys.length - 1].t;
  const vis = ramp(lt, t0 - 0.22, t0) * (1 - ramp(lt, t1 + hold, t1 + hold + 0.2));
  let s = 1;
  clicks.forEach(c => {
    const up = c.up === undefined ? c.t + 0.13 : c.up;
    s -= 0.2 * ramp(lt, c.t, c.t + 0.05) * (1 - ramp(lt, up, up + 0.1));
  });
  cur.style.opacity = vis.toFixed(3);
  cur.style.transform = `translate(${(x - 3).toFixed(1)}px,${(y - 3).toFixed(1)}px) scale(${s.toFixed(3)})`;
  rips.forEach((r, i) => {
    const c = clicks[i];
    if (!c || lt < c.t) { r.style.opacity = 0; return; }
    const u = ramp(lt, c.t, c.t + 0.6);
    const [px, py] = pathPos(keys, c.t);
    r.style.opacity = ((1 - u) * 0.9 * vis).toFixed(3);
    r.style.transform = `translate(${px.toFixed(1)}px,${py.toFixed(1)}px) scale(${(0.6 + 3.6 * e3(u)).toFixed(3)})`;
  });
}

// A beat's clicks: [lt, what] is a click, [lt, up, what] a press held until `up` (a drag). Returns the cursor's clicks and the audio's cues.
export function clickList(list) {
  const clicks = [], cues = [];
  list.forEach(c => {
    if (typeof c[1] === 'number') { clicks.push({ t: c[0], up: c[1] }); cues.push({ lt: c[0], kind: 'down', what: c[2] }, { lt: c[1], kind: 'up', what: c[2] }); }
    else { clicks.push({ t: c[0] }); cues.push({ lt: c[0], kind: 'click', what: c[1] }); }
  });
  return { clicks, cues };
}
export const qs = (el, s) => el.querySelector(s);
export const setOp = (el, u, dy = 0) => { el.style.opacity = u.toFixed(3); el.style.transform = `translate(0px,${((1 - u) * dy).toFixed(1)}px)`; };

// ---- the stripe wipe: a white band then a gold one, slanted 20 degrees, sweeping left to right; the new beat shows behind it ----
const SH = Math.tan(20 * Math.PI / 180) * 720, WG = 130, WW = 250;
const wW = document.getElementById('wW'), wG = document.getElementById('wG'), wipeEl = document.getElementById('wipe');
export function wipeSet(p) {            // p: 0..1, or null for none; returns the clip-path for the incoming beat
  if (p === null) { wipeEl.style.display = 'none'; return ''; }
  wipeEl.style.display = 'block';
  const e = p < 0.5 ? 2 * p * p : 1 - 2 * (1 - p) * (1 - p);       // sweeps in, then out, quickly through the middle
  const xl = mix(-SH - 20, 2560 + SH + WG + WW + 20, e);
  const poly = (xa, xb) => `${(xb + SH).toFixed(1)},0 ${(xa + SH).toFixed(1)},0 ${(xa - SH).toFixed(1)},1440 ${(xb - SH).toFixed(1)},1440`;
  wG.setAttribute('points', poly(xl - WG, xl));
  wW.setAttribute('points', poly(xl - WG - WW, xl - WG));
  const t = xl - WG - WW + 6;
  return `polygon(0px 0px, ${(t + SH).toFixed(1)}px 0px, ${(t - SH).toFixed(1)}px 1440px, 0px 1440px)`;
}
