// The film's page. window.setTime(t) poses everything for second t (nothing runs on its own), and returns when the frame is
// ready to be captured. Query: ?k=0.25 scales the 2560x1440 stage for previews.
import * as ui from './ui.mjs';
import { K as K3, loadFlower, render, THREE } from './stage3d.mjs';
import { clamp, ramp } from './lib.mjs';
import openBeats from './beats_open.mjs';
import hookBeats from './beats_hook.mjs';
import ideaBeats from './beats_idea.mjs';
import featBeats from './beats_feat.mjs';
import endBeats from './beats_end.mjs';

const q = new URLSearchParams(location.search);
const k = parseFloat(q.get('k') || '1');
ui.view.k = k; K3.v = k;
ui.stage.style.transform = `scale(${k})`;

const pending = [];
const ctx = {
  ui, THREE, K3, render, k,
  // A <img> shows a footage frame; its decode is awaited before the frame is captured.
  show(img, url) { if (img.dataset.u !== url) { img.dataset.u = url; img.src = url; pending.push(img.decode().catch(() => {})); } },
  frameUrl: (set, i) => `/footage/${set}/${String(i).padStart(4, '0')}.jpg`,
};

const ready = (async () => {
  ctx.T = await (await fetch('/v2/timeline.json')).json();
  ctx.F = await loadFlower();
  ctx.real = await (await fetch('/footage/real.json')).json();
  await Promise.all(['800 80px Inter', '700 22px Inter', '600 22px Inter', '500 24px Inter', '400 26px Inter'].map(f => document.fonts.load(f)));
  await document.fonts.ready;
  // film grain: a tile of noise, moved every frame
  const c = document.createElement('canvas'); c.width = c.height = 256;
  const g = c.getContext('2d'), d = g.createImageData(256, 256);
  let s = 12345;
  for (let i = 0; i < d.data.length; i += 4) { s = (s * 1664525 + 1013904223) >>> 0; const v = s >>> 24; d.data[i] = d.data[i + 1] = d.data[i + 2] = v; d.data[i + 3] = 255; }
  g.putImageData(d, 0, 0);
  document.getElementById('grain').style.backgroundImage = `url(${c.toDataURL()})`;

  const factories = [...openBeats, ...hookBeats, ...ideaBeats, ...featBeats, ...endBeats];
  const byId = Object.fromEntries(factories.map(f => [f.id, f]));
  ctx.beats = ctx.T.beats.map((tb, i) => {
    const f = byId[tb.id];
    const b = f ? f.make(ctx, tb) : placeholder(tb);
    return Object.assign(b, { id: tb.id, start: tb.start, end: tb.end, dur: tb.end - tb.start, index: i, built: false });
  });
  ctx.byId = Object.fromEntries(ctx.beats.map(b => [b.id, b]));
  document.getElementById('beats').innerHTML = '';
  return true;
})();

function placeholder(tb) {
  return { build(el) { el.innerHTML = `<div class="big" style="top:600px"><div class="ln">${tb.id}</div></div>`; }, update() {} };
}

function ensure(b) {
  if (!b.built) {
    const el = document.createElement('section');
    el.className = 'beat'; el.id = 'b-' + b.id; el.style.zIndex = 10 + b.index;
    document.getElementById('beats').appendChild(el);
    b.el = el;
    el.style.display = 'block';
    const t0 = performance.now();
    b.build(el);
    console.log('LOG built ' + b.id + ' in ' + Math.round(performance.now() - t0) + ' ms');
    ui.animText(el, 5, 99);                       // text settled, so the cursor's marks can be measured
    if (b.measure) b.measure(el);
    b.built = true;
  }
}

window.setTime = async t => {
  await ready;
  const T = ctx.T;
  const live = ctx.beats.filter(b => t >= b.start - 0.22 && t <= b.end + 0.22);
  ctx.beats.forEach(b => { if (b.built && !live.includes(b)) b.el.style.display = 'none'; });
  for (const b of live) {
    ensure(b);
    b.el.style.display = 'block';
    b.update(t - b.start, b.dur);
  }
  const w = T.wipes.find(x => t >= x.start && t <= x.end);
  const clip = ui.wipeSet(w ? ramp(t, w.start, w.end) : null);
  ctx.beats.forEach(b => { if (b.built) b.el.style.clipPath = w && b.id === w.to ? clip : ''; });
  const owner = ctx.beats.find(b => t >= b.start && t < b.end);
  if (owner && owner.built && owner.cur) ui.cursor(t - owner.start, owner.cur.keys, owner.cur.clicks, owner.cur.hold);
  else ui.cursor(0, null);
  const f = Math.round(t * 60);
  document.getElementById('grain').style.backgroundPosition = `${(f * 97) % 256}px ${(f * 57) % 256}px`;
  await Promise.all(pending.splice(0));
  return true;
};

// Every sound cue the beats declare (clicks, pops), in film time: the audio mix reads this.
window.getCues = async () => {
  await ready;
  const out = [];
  for (const b of ctx.beats) {
    for (const c of b.cues || []) out.push({ t: +(b.start + c.lt).toFixed(3), beat: b.id, kind: c.kind, name: c.name || '', what: c.what || '' });
  }
  return out.sort((a, b) => a.t - b.t);
};
window.ready = ready;
