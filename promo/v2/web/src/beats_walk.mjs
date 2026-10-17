// The opening of promo v2.3: "Let's rig this flower from scratch. Clock's running!" An exact walkthrough of promo/files/FLOWER_FAST.md
// steps 1-9 with CopyThat_flower_fast.blend, at the pace of a person who knows the steps, and a running timer instead of a click counter.
// Every action on the stage is one a customer does in Blender: a click in the Outliner (Ctrl+click to add), a click on a panel button or
// a section's title, a double-click into a field and a typed number, a dialog filled in row by row, the slider dragged at the end. The
// flower follows each typed value (one part per value), a Ring's copies stand shut where they are made, and Build puts everything back
// to Before. The script is walk_schedule.mjs (shared with make_timeline.py); the editors are walk_ui.mjs (Blender's own pixel size).
import { THREE, mkView, render, instFlower } from './stage3d.mjs';
import { clamp, mix, ramp, e3, io, D2R } from './lib.mjs';
import { qs, at, pathPos, view } from './ui.mjs';
import { buildSchedule, clock } from './walk_schedule.mjs';
import { Z, outlinerHTML, propertiesHTML, panelHTML, ringDialogHTML, spreadDialogHTML, OL_ROWS, TIMING_NAMES, GROUPS, icons } from './walk_ui.mjs';

const pt = ([x, y]) => ({ x, y });
const OL = { x: 1481, y: 70 }, PP = { x: 1481, y: 765 }, PN = { x: 2016, y: 70 }, WIN = 1300;   // the editors' places on the stage
const IN = { x: 2330, y: 1405 };                       // where the pointer comes in from
const SHIFT = 330, DOLLY = 1.08, GLOW = 0.3;            // the flower stands left of the editors; the real camera, pulled back to fit them
const G6 = ['Outer Leader', 'Inner Leader', 'Core', 'Leaf 1', 'Leaf 2', 'Leaf 3'];

// the file's own values (CopyThat_flower_fast.blend, read with Blender 5.2): what the Properties editor says before anything is typed
const REST = {
  'Core': { loc: [0, 0, 1.29], rot: [0, 0, 0] }, 'Inner Leader': { loc: [0, -0.115, 1.275], rot: [0, 0, -3e-6] },
  'Leaf 1': { loc: [0.026964, -0.013151, 0.38], rot: [0, 0, 64] }, 'Leaf 2': { loc: [0.098551, -0.048067, 0.789755], rot: [0, 0, 64] },
  'Leaf 3': { loc: [0.111021, -0.054149, 0.39245], rot: [0, 0, 64] }, 'Outer Leader': { loc: [0, -0.185, 1.255], rot: [0, 0, -3e-6] },
  'Pedestal': { loc: [0, 0, 0], rot: [0, 0, 0] }, 'Stem': { loc: [0, 0, 0], rot: [0, 0, 0] }, 'Promo Camera': { loc: [-3.272114, -13.123734, 2.701587], rot: [84, 0, -14] },
};
const sig = v => { const s = String(parseFloat(Number(v).toPrecision(5))); return s === '-0' ? '0' : s; };       // Blender shows 5 significant digits
const fmtLoc = v => sig(v) + ' m', fmtRot = v => sig(v) + '°';
const FIELD = { locx: ['loc', 0], locy: ['loc', 1], locz: ['loc', 2], rotx: ['rot', 0], roty: ['rot', 1], rotz: ['rot', 2] };
const KEY = { 'Outer Leader': 'outer', 'Inner Leader': 'inner', 'Leaf 1': 'leaf' };

const REPORTS = {
  newmove: "'Move 1': 6 part(s). Where they stand now is Before. Move them, then Record After.",
  makechain: 'Chain: Leaf 1 > Leaf 2 > Leaf 3', after: "'Move 1': After recorded for 6 part(s).",
  build: '21 part(s) on 1 slider(s). 6 object(s) were given a bone and bound. 15 object(s) now ride along. 2 part(s) hung from the part they follow.',
};
const wrap = (text, width = 29) => {
  const out = []; let line = '';
  text.split(' ').forEach(w => { if ((line + ' ' + w).trim().length > width) { out.push(line); line = w; } else line = (line + ' ' + w).trim(); });
  if (line) out.push(line);
  return out.join('\n');
};

// ---- the state of Blender and the panel after each action ----
const newState = () => ({
  sel: [], active: 'Stem', rig: false, chain: false, leafOpen: false, after: false, built: false, parts: 0,
  open: { path: false, timing: false, copies: false, chains: false }, follows: {},
  vals: Object.fromEntries(Object.entries(REST).map(([n, r]) => [n, { loc: r.loc.slice(), rot: r.rot.slice() }])),
  ring: { outer: false, inner: false, leaf: false }, lead: { outer: 0, inner: 0, leaf: 0 }, cnt: { outer: 8, inner: 6, leaf: 2 },
  dlg: null, dlgAt: -1, dv: null, last: { count: 6, round: '3D Cursor' },                // Ring remembers its Count and Round from the last use
  delays: Object.fromEntries(G6.map(n => [n, 0])), ease: 'Even speed', report: '', reportAt: -1,
});
function reduce(S0, op) {
  const S = structuredClone(S0), at_ = op.target.indexOf(':'), k = op.target.slice(0, at_), a = op.target.slice(at_ + 1);
  op.active = S.active;
  const say = text => { S.report = text; S.reportAt = op.i; };
  if (op.kind === 'click') {
    if (k === 'ol') { if (op.mods.includes('ctrl')) { if (!S.sel.includes(a)) S.sel.push(a); } else S.sel = [a]; S.active = a; }
    else if (k === 'olx') S.leafOpen = true;
    else if (k === 'sec') S.open[a] = !S.open[a];
    else if (k === 'pn') {
      if (a === 'newmove') { S.rig = true; S.parts = 6; say(REPORTS.newmove); }
      else if (a === 'makechain') { S.chain = true; S.follows = { 'Leaf 2': 'Leaf 1', 'Leaf 3': 'Leaf 2' }; say(REPORTS.makechain); }
      else if (a === 'record_after') { S.after = true; say(REPORTS.after); }
      else if (a === 'ring') { S.dlg = 'ring'; S.dlgAt = op.i; S.dv = { leader: S.active, count: S.last.count, round: S.last.round, lead: 0, menu: false }; }
      else if (a === 'spread_timing') { S.dlg = 'spread'; S.dlgAt = op.i; S.dv = { only: false, start: 0, step: 0.1 }; }
      else if (a === 'smooth') S.ease = 'Smooth';
      else if (a === 'build') { S.built = true; say(REPORTS.build); }
    } else if (k === 'dlg') {
      if (a === 'round') S.dv.menu = !S.dv.menu;
      else if (a === 'round:World Origin') { S.dv.round = 'World Origin'; S.dv.menu = false; }
      else if (a === 'only') S.dv.only = !S.dv.only;
      else if (a === 'ok' && S.dlg === 'ring') {
        const dv = S.dv, key = KEY[dv.leader], n = dv.count - 1, where = dv.round === 'World Origin' ? 'the world origin' : 'the 3D cursor';
        S.ring[key] = true; S.lead[key] = dv.lead; S.cnt[key] = dv.count; S.last = { count: dv.count, round: dv.round };
        S.parts += key === 'leaf' ? 3 : n;
        say(key === 'leaf' ? `${n} ${n === 1 ? 'copy' : 'copies'} of '${dv.leader}' (3 joints each) round ${where} rides along with it, joint for joint.`
          : `${n} copies of '${dv.leader}' round ${where} ride along with it. Leads step by ${dv.lead}, out from it both ways round.`);
        S.dlg = null; S.dv = null;
      } else if (a === 'ok') {
        const dv = S.dv, names = dv.only ? ['Leaf 1', 'Leaf 2', 'Leaf 3'].filter(n => S.sel.includes(n)) : G6;
        names.forEach((n, i) => { S.delays[n] = +(dv.start + i * dv.step).toFixed(2); });
        say(`Spread the Delays of ${names.length} parts in steps of ${dv.step} from ${dv.start}, down the chain.`);
        S.dlg = null; S.dv = null;
      }
    }
  } else if (op.kind === 'edit') {
    const v = Number(op.text);
    if (k === 'pp') { const [grp, i] = FIELD[a]; S.vals[S.active][grp][i] = v; }
    else if (k === 'dlg') S.dv[{ count: 'count', lead: 'lead', start: 'start', step: 'step' }[a]] = v;
    else if (k === 'tim') S.delays[a] = v;
  }
  return S;
}
// what each editable field says in a state
function fieldText(target, S) {
  const i = target.indexOf(':'), k = target.slice(0, i), a = target.slice(i + 1);
  if (k === 'pp') { const [grp, j] = FIELD[a], v = (S.vals[S.active] || S.vals.Stem)[grp][j]; return grp === 'loc' ? fmtLoc(v) : fmtRot(v); }
  if (k === 'tim') return S.delays[a].toFixed(2);
  const d = S.dv;
  return a === 'count' ? String(d.count) : a === 'lead' ? String(d.lead) : a === 'start' ? d.start.toFixed(2) : d.step.toFixed(2);
}
const FIELD_ID = { count: 'rc-count', lead: 'rc-lead' };
const fieldId = (target, S) => {
  const i = target.indexOf(':'), k = target.slice(0, i), a = target.slice(i + 1);
  if (k === 'pp') return 'pp-' + a;
  if (k === 'tim') return 'tm-' + a;
  return S.dlg === 'spread' ? 'sp-' + a : FIELD_ID[a];
};
const leadsOf = (key, S) => Array.from({ length: S.cnt[key] - 1 }, (_, i) => S.lead[key] * Math.min(i + 1, S.cnt[key] - 1 - i));

const open = {
  id: 'open',
  make(ctx, tb) {
    const SC = buildSchedule(), GO = (tb.steps && tb.steps.go) || 3.6;
    const M = ctx.F.motion, Gp = M.groups, MO = M.motion, names = Object.keys(MO);
    const DUR = tb.end - tb.start;
    // the script, on the beat's clock
    const ops = SC.ops.map(o => ({ ...o, arrive: o.arrive + GO, t: o.t + GO, dbl: o.dbl && o.dbl.map(x => x + GO), chars: o.chars && o.chars.map(x => x + GO), end: o.end !== undefined ? o.end + GO : undefined }));
    const st = [newState()];
    ops.forEach(o => st.push(reduce(st[st.length - 1], o)));
    const idxAt = lt => { let n = 0; while (n < ops.length && ops[n].t <= lt) n++; return n; };
    const dragOp = ops[ops.length - 1], buildOp = ops.find(o => o.target === 'pn:build'), stopT = GO + SC.riggedIn;
    const slideAt = lt => (lt <= dragOp.t ? 0 : io(ramp(lt, dragOp.t, dragOp.end)));

    // cues for the sound: a click on every press, a soft key tick for each typed character and for Enter
    const cues = [], clicks = [];
    ops.forEach(o => {
      if (o.kind === 'click') { clicks.push({ t: o.t }); cues.push({ lt: o.t, kind: 'click', what: o.target }); }
      else if (o.kind === 'edit') {
        o.dbl.forEach(x => { clicks.push({ t: x }); cues.push({ lt: x, kind: 'click', what: o.target }); });
        o.chars.forEach(x => cues.push({ lt: x, kind: 'key', what: o.target })); cues.push({ lt: o.t, kind: 'key', what: o.target });
      } else if (o.kind === 'drag') { clicks.push({ t: o.t, up: o.end }); cues.push({ lt: o.t, kind: 'down', what: o.target }, { lt: o.end, kind: 'up', what: o.target }); }
    });
    // a key held down while a run of presses follows (Ctrl through the six rows of a selection, Shift for the one that opens the leaf)
    const chipRuns = [];
    ops.forEach(o => {
      if (!o.mods.length) return;
      const r = chipRuns[chipRuns.length - 1];
      if (r && r.key === o.mods[0] && o.i === r.last + 1) { r.last = o.i; r.t1 = o.t; } else chipRuns.push({ key: o.mods[0], last: o.i, t0: o.arrive, t1: o.t });
    });
    // where a gold pulse lights what, and when
    const pulses = [];
    ops.forEach((o, i) => {
      const after = st[i + 1];
      if (o.kind === 'edit' && o.target.startsWith('pp:')) pulses.push({ t: o.t, parts: [o.active], len: 0.8 });
      else if (o.target === 'pn:newmove') pulses.push({ t: o.t, parts: G6, len: 0.9 });
      else if (o.target === 'pn:makechain') pulses.push({ t: o.t, parts: ['Leaf 1', 'Leaf 2', 'Leaf 3'], len: 0.8 });
      else if (o.target === 'dlg:ok' && st[i].dlg === 'ring') {
        const key = KEY[st[i].dv.leader], copies = { outer: Gp.outer_petals.slice(1), inner: Gp.inner_petals.slice(1), leaf: Gp.leaf_b }[key];
        pulses.push({ t: o.t, parts: copies, len: 0.9 });
      } else if (o.target === 'pn:build') pulses.push({ t: o.t, parts: names, len: 0.6 });
      void after;
    });

    // ---- the flower: the real camera (pulled back to leave room for the editors), one part posed per typed value ----
    const mat = a => new THREE.Matrix4().compose(new THREE.Vector3(a[0], a[1], a[2]), new THREE.Quaternion(a[3], a[4], a[5], a[6]), new THREE.Vector3(a[7], a[8], a[9]));
    const rest = Object.fromEntries(names.map(n => [n, mat(MO[n][0])]));
    const rotX = deg => new THREE.Matrix4().makeRotationX(deg * D2R);
    const core0 = MO.Core[0];
    const poseOf = S => S.built ? [0, 0, REST.Core.loc[2], 0, 0, 0, 0] : [S.vals['Outer Leader'].rot[0], S.vals['Inner Leader'].rot[0], S.vals.Core.loc[2], S.vals.Core.rot[2],
      S.vals['Leaf 1'].rot[0], S.vals['Leaf 2'].rot[0], S.vals['Leaf 3'].rot[0]];
    // a part turned about its own X (the hinge is its origin); a leaf segment is carried by the one before it
    const worlds = p => {
      const W = {};
      W['Outer Leader'] = rest['Outer Leader'].clone().multiply(rotX(p[0]));
      W['Inner Leader'] = rest['Inner Leader'].clone().multiply(rotX(p[1]));
      W.Core = new THREE.Matrix4().compose(new THREE.Vector3(core0[0], p[2] - REST.Core.loc[2] + core0[1], core0[2]),
        new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), p[3] * D2R), new THREE.Vector3(1, 1, 1));
      W['Leaf 1'] = rest['Leaf 1'].clone().multiply(rotX(p[4]));
      W['Leaf 2'] = W['Leaf 1'].clone().multiply(rest['Leaf 1'].clone().invert()).multiply(rest['Leaf 2']).multiply(rotX(p[5]));
      W['Leaf 3'] = W['Leaf 2'].clone().multiply(rest['Leaf 2'].clone().invert()).multiply(rest['Leaf 3']).multiply(rotX(p[6]));
      return W;
    };
    const copyGroups = { outer: Gp.outer_petals.slice(1), inner: Gp.inner_petals.slice(1), leaf: Gp.leaf_b };
    const exists = (n, S) => G6.includes(n) || (S.ring.outer && copyGroups.outer.includes(n)) || (S.ring.inner && copyGroups.inner.includes(n)) || (S.ring.leaf && copyGroups.leaf.includes(n));
    const pulse = (lt, t0, len) => ramp(lt, t0, t0 + 0.06) * (1 - ramp(lt, t0 + 0.06, t0 + len));

    let v, FL, root;
    const mats = {}, keysList = [];
    let scrolls = [], dlgSize = {}, hovEl = null, lastIdx = -2, lastEdit = null;
    const $ = id => root.querySelector(`[id="${id}"]`);
    const setScroll = y => { $('pnin').style.transform = `translateY(${(-y).toFixed(2)}px)`; };
    const scrollAt = lt => {
      let y = 0;
      for (const s of scrolls) { if (lt < s.t0) break; y = lt >= s.t1 ? s.to : mix(s.from, s.to, io(ramp(lt, s.t0, s.t1))); }
      return y;
    };
    const txt = (id, s) => { const e = $(id); if (e.textContent !== s) e.textContent = s; };
    const setField = (id, s) => { const f = $(id); f.classList.remove('ed'); f.querySelector('.v').textContent = s; };

    // the element an action points at, in a state
    const elOf = (target, S) => {
      const i = target.indexOf(':'), k = target.slice(0, i), a = target.slice(i + 1);
      if (k === 'ol' || k === 'olx') {
        const id = a + (a === 'Leaf 2' || a === 'Leaf 3' ? (S.chain ? '~n' : '~f') : '');
        const row = root.querySelector(`.or[data-id="${id}"]`);
        return k === 'ol' ? row.querySelector('.nm') : row.querySelector('.ex');
      }
      if (k === 'pn') return $({ newmove: S.rig ? 'nm2' : 'prenm', makechain: 'mc', record_after: 'reca', ring: 'rg', spread_timing: 'spt', smooth: 'ez-Smooth', build: 'bs', slider: 'play' }[a]);
      if (k === 'sec') return $('s-' + a).querySelector('b');
      if (k === 'pp') return $('pp-' + a);
      if (k === 'tim') return $('tm-' + a);
      if (k === 'dlg') {
        const spread = S.dlg === 'spread';
        if (a === 'ok') return $(spread ? 'sp-ok' : 'rc-ok');
        if (a === 'round:World Origin') return $('mi-origin');
        if (a === 'only') return $('sp-cb');
        if (a === 'order') return $('sp-order');
        if (a === 'round') return $('rc-round');
        return $(spread ? 'sp-' + a : 'rc-' + a);
      }
      throw new Error('no element for ' + target);
    };

    // everything that a state decides (the continuous parts are laid over it in update)
    const applyState = S => {
      let k = 2;
      root.querySelectorAll('.or:not(.top)').forEach(r => {
        const id = r.dataset.id, nm = r.dataset.n;
        const show = id.startsWith('Inner Leader ') ? S.ring.inner : id.startsWith('Outer Leader ') ? S.ring.outer : id === 'Leaf 1 2' ? S.ring.leaf
          : id.endsWith('~f') ? !S.chain : id.endsWith('~n') ? S.chain && S.leafOpen : id === 'CopyThat Rig' ? S.rig : true;
        r.style.display = show ? 'flex' : 'none';
        if (!show) return;
        r.classList.toggle('alt', k++ % 2 === 1);
        r.classList.toggle('sel', S.sel.includes(nm)); r.classList.toggle('act', S.sel.includes(nm) && S.active === nm);
        const ex = r.querySelector('.ex');
        if (nm === 'Leaf 1') ex.classList.toggle('open', S.chain && S.leafOpen);
        if (id === 'Leaf 2~n') ex.classList.add('open');
      });
      // Properties
      txt('ppn', S.active); txt('ppn2', S.active);
      const val = S.vals[S.active] || S.vals.Stem;
      ['locx', 'locy', 'locz', 'rotx', 'roty', 'rotz'].forEach(f => { const [grp, j] = FIELD[f]; setField('pp-' + f, grp === 'loc' ? fmtLoc(val[grp][j]) : fmtRot(val[grp][j])); });
      ['scx', 'scy', 'scz'].forEach(f => setField('pp-' + f, '1.000'));
      // the panel
      $('pre').style.display = S.rig ? 'none' : 'block'; $('rig').style.display = S.rig ? 'block' : 'none';
      const n = S.sel.length;
      txt('presay', n ? `${n} ${n === 1 ? 'object' : 'objects'} selected.` : 'Select the objects that move.');
      $('prenm-row').style.display = n ? 'flex' : 'none';
      txt('rc', S.parts + ' parts' + (S.built ? ' · 1 slider' : '')); $('rc').parentNode.classList.toggle('two', S.built);
      $('cka').innerHTML = S.after ? icons.tick : icons.dot; $('eyea').style.visibility = S.after ? 'visible' : 'hidden';
      ['path', 'timing', 'copies', 'chains'].forEach(id => { $('s-' + id).querySelector('.tg').classList.toggle('shut', !S.open[id]); $('b-' + id).classList.toggle('open', S.open[id]); });
      $('s-animate').style.display = S.built ? 'flex' : 'none'; $('playrow').style.display = S.built ? 'flex' : 'none';
      $('ez-Even speed').classList.toggle('on', S.ease === 'Even speed'); $('ez-Smooth').classList.toggle('on', S.ease === 'Smooth');
      const lit = G6.filter(x => S.sel.includes(x));
      $('lit').style.display = lit.length ? 'flex' : 'none';
      G6.forEach(x => {
        $('tr-' + x).classList.toggle('dimr', lit.length > 0 && !lit.includes(x));
        setField('tm-' + x, S.delays[x].toFixed(2)); $('tm-' + x).querySelector('.fill').style.width = `${(S.delays[x] / 0.99 * 100).toFixed(1)}%`;
        const f = $('fw-' + x); f.querySelector('.v').textContent = S.follows[x] || ''; f.querySelector('.xx').style.display = S.follows[x] ? 'flex' : 'none';
      });
      const riders = GROUPS.reduce((c, g) => c + (S.ring[g.key] ? (g.key === 'leaf' ? 1 : S.cnt[g.key] - 1) : 0), 0);
      $('riders').style.display = riders ? 'block' : 'none'; $('spc').style.display = riders ? 'flex' : 'none';
      txt('ride', `Riding along (${riders})`);
      GROUPS.forEach(g => { $('g-' + g.key).style.display = S.ring[g.key] ? 'block' : 'none'; const L = leadsOf(g.key, S); g.rows.forEach((_, j) => { $(`ld-${g.key}${j}`).querySelector('.v').textContent = L[j] === undefined ? '0' : String(L[j]); }); });
      txt('rtxt', wrap(S.report));
      // the dialogs' rows
      if (S.dv && S.dlg === 'ring') {
        setField('rc-count', String(S.dv.count)); setField('rc-lead', String(S.dv.lead)); $('rc-round').querySelector('.v').textContent = S.dv.round;
        $('rc-menu').style.display = S.dv.menu ? 'block' : 'none';
      } else if (S.dv && S.dlg === 'spread') {
        $('sp-cb').classList.toggle('on', S.dv.only); setField('sp-start', S.dv.start.toFixed(2)); setField('sp-step', S.dv.step.toFixed(2));
      }
    };
    const placeDialog = (S, el_) => { const w = S.dlgAt >= 0 && ops[S.dlgAt].dlgPos; if (w) { el_.style.left = `${w.x}px`; el_.style.top = `${w.y}px`; } };

    return {
      cues,
      build(el) {
        root = el;
        const dots = Array.from({ length: 9 }, () => '<i></i>').join('');
        el.innerHTML = `
          <div class="full"></div><div class="shade"></div>
          <div class="tm" style="left:154px;top:132px">
            <div class="tm-k" id="tmk">RIG TIME</div><div class="tm-n" id="tmn">0:00</div><div class="tm-s" id="tms">READY</div><div class="tm-p" id="tmp">${dots}</div>
          </div>
          <div class="stat" id="stat" style="opacity:0">${icons.info.replace('width="13" height="13"', 'width="26" height="26"')}<span id="stxt"></span></div>
          <div id="olw" style="position:absolute;left:${OL.x}px;top:${OL.y}px"><div class="bl" style="zoom:${Z}">${outlinerHTML()}</div></div>
          <div id="ppw" style="position:absolute;left:${PP.x}px;top:${PP.y}px"><div class="bl" style="zoom:${Z}">${propertiesHTML()}</div></div>
          <div id="pnw" style="position:absolute;left:${PN.x}px;top:${PN.y}px"><div class="bl" style="zoom:${Z}">${panelHTML()}</div></div>
          <div id="dRw" style="position:absolute;left:0;top:0;opacity:0;visibility:hidden"><div class="bl" style="zoom:${Z}">${ringDialogHTML()}</div></div>
          <div id="dSw" style="position:absolute;left:0;top:0;opacity:0;visibility:hidden"><div class="bl" style="zoom:${Z}">${spreadDialogHTML()}</div></div>
          <div class="kc" id="kc">Ctrl</div>`;
        const cam = M.camera, f0 = cam.frames[0], look = new THREE.Vector3(0, 1.05, 0), p0 = new THREE.Vector3(f0[0], f0[1], f0[2]);
        const pos = look.clone().add(p0.sub(look).multiplyScalar(DOLLY));
        v = mkView({ w: 2560, h: 1440, fov: cam.fov_y_deg, pos: pos.toArray(), look: look.toArray(), slot: this.index % 2, bloom: 0.3, env: 0.65 });
        v.host = qs(el, '.full');
        v.camera.setViewOffset(2560, 1440, SHIFT, 0, 2560, 1440);
        FL = instFlower(ctx.F); FL.coreScale = 0.6; FL.pose(0);
        v.scene.add(FL.root);
        names.forEach(n => {                         // each part has its own materials, so a selection or a glow lights that part only
          FL.parts[n].traverse(o => {
            if (!o.isMesh || /core glow/i.test(o.material.name)) return;
            o.material = o.material.clone(); o.material.emissive.setRGB(0.95, 0.52, 0.12);
            (mats[n] = mats[n] || []).push(o.material);
          });
        });
      },
      measure(el) {
        const k = view.k, keys = [];
        const stageOf = e => pt(at(e));
        // the dialogs' sizes, once
        [['dRw', 'ring'], ['dSw', 'spread']].forEach(([id, key]) => { const r = $(id).querySelector('.dlgb').getBoundingClientRect(); dlgSize[key] = { w: r.width / k, h: r.height / k }; });
        let scroll = 0, prevEnd = null;
        const push = (t, p, o = {}) => keys.push({ t, x: p.x, y: p.y, ...o });
        const inPanel = t => /^(pn|sec|tim):/.test(t) && t !== 'pn:slider';        // the slider has its own scroll: back to the top
        ops.forEach((o, i) => {
          const S = st[i];
          applyState(S); setScroll(scroll);
          // a dialog that is open stands where it opened
          ['dRw', 'dSw'].forEach(id => { $(id).style.visibility = 'hidden'; });
          if (S.dlg) { const w = $(S.dlg === 'ring' ? 'dRw' : 'dSw'); placeDialog(S, w); w.style.visibility = 'visible'; w.style.opacity = 1; }
          let p = stageOf(elOf(o.target, S));
          if (inPanel(o.target)) {                   // the sidebar scrolls like Blender's: the wheel over it, before the press
            const card = $('pnw').querySelector('.pn').getBoundingClientRect(), top = PN.y + 90, bot = PN.y + Math.min(WIN, card.height / k) - 100;
            const content = $('pnin').getBoundingClientRect().height / k, max = Math.max(0, content - WIN) / Z;
            if (p.y < top || p.y > bot) {
              const to = clamp(scroll + (p.y < top ? p.y - top : p.y - bot) / Z, 0, max);
              if (Math.abs(to - scroll) > 0.5) {
                const t1 = o.arrive - 0.06, t0 = t1 - 0.5;
                scrolls.push({ t0, t1, from: scroll, to });
                console.log('LOG scroll panel', scroll.toFixed(1), '->', to.toFixed(1), 'before', o.target, 'at', (o.arrive - GO).toFixed(2));
                scroll = to; setScroll(scroll); p = stageOf(elOf(o.target, S));
              }
            }
          }
          if (o.target === 'pn:slider' && scroll > 0) { scrolls.push({ t0: o.arrive - 0.95, t1: o.arrive - 0.2, from: scroll, to: 0 }); scroll = 0; setScroll(0); p = stageOf(elOf(o.target, S)); }
          if (o.target === 'pn:ring' || o.target === 'pn:spread_timing') {           // the dialog opens under the pointer, as Blender's do
            const d = dlgSize[o.target === 'pn:ring' ? 'ring' : 'spread'];
            o.dlgPos = { x: clamp(p.x - d.w * 0.5, 30, 2560 - 30 - d.w), y: clamp(p.y - d.h * 0.42, 30, 1440 - 30 - d.h) };
          }
          if (o.kind === 'drag') {                    // the thumb of the slider follows the pointer: left edge to right edge
            const r = $('play').getBoundingClientRect();
            const at0 = u => ({ x: (r.left + u * r.width) / k, y: (r.top + r.height / 2) / k });
            push(o.arrive, at0(0)); push(o.t, at0(0));
            for (let t = o.t + 0.1; t < o.end; t += 0.1) push(t, at0(io(ramp(t, o.t, o.end))), { lin: true });
            push(o.end, at0(1), { lin: true });
            return;
          }
          if (i === 0) push(o.arrive - 1.0, IN);
          push(o.arrive, p);
          const last = o.kind === 'edit' ? o.t + 0.12 : o.kind === 'hover' ? o.t : o.t + 0.12;
          push(last, p);
          prevEnd = last;
        });
        this.cur = { keys, clicks, hold: 0.5 };
        this.keys = keys;
        applyState(st[0]); setScroll(0); lastIdx = -2;
      },
      update(lt, dur) {
        const el = this.el, n = idxAt(lt), S = st[n];
        if (lastEdit) { lastEdit = null; lastIdx = -2; }          // a field that was being typed into is put back to what the state says
        if (n !== lastIdx) { applyState(S); lastIdx = n; }
        el.style.opacity = ramp(lt, 0, 0.3).toFixed(3);
        // the sidebar's scroll
        setScroll(scrollAt(lt));

        // ---- the flower ----
        const prev = st[Math.max(0, n - 1)], u = n ? ramp(lt, ops[n - 1].t, ops[n - 1].t + 0.12) : 1;
        const p0 = poseOf(prev), p1 = poseOf(S), p = p0.map((x, i) => mix(x, p1[i], u));
        const s = slideAt(lt);
        if (S.built) { FL.pose(150 * s); names.forEach(nm => { FL.parts[nm].visible = true; }); }
        else {
          FL.pose(0);
          const W = worlds(p), q = new THREE.Quaternion(), ps = new THREE.Vector3(), sc = new THREE.Vector3();
          G6.forEach(nm => { W[nm].decompose(ps, q, sc); const nd = FL.parts[nm]; nd.position.copy(ps); nd.quaternion.copy(q); nd.scale.copy(sc); });
          names.forEach(nm => { FL.parts[nm].visible = exists(nm, S); });
        }
        names.forEach(nm => {
          let g = 0;
          pulses.forEach(pl => { if (pl.parts.includes(nm)) g = Math.max(g, pulse(lt, pl.t, pl.len) * GLOW); });
          const selected = S.sel.includes(nm) ? (S.active === nm ? 0.36 : 0.22) : 0;
          const e = Math.max(g, selected);
          (mats[nm] || []).forEach(m => { m.emissiveIntensity = e; });
        });
        render(v);

        // ---- the timer ----
        const run = clamp(lt - GO, 0, SC.riggedIn), stopped = lt >= stopT;
        const fin = ramp(lt, stopT, stopT + 0.3);
        const gold = `rgb(${Math.round(mix(255, 201, fin))},${Math.round(mix(255, 167, fin))},${Math.round(mix(255, 106, fin))})`;
        const tn = $('tmn'); tn.textContent = clock(run); tn.style.color = gold;
        const pop = 1 - ramp(lt, stopT, stopT + 0.5);
        tn.style.transformOrigin = '0 60%'; tn.style.transform = `scale(${(1 + 0.07 * pop * fin).toFixed(3)})`;
        tn.style.textShadow = stopped ? `0 0 ${(70 * pop).toFixed(1)}px rgba(232,206,150,${(0.9 * pop).toFixed(2)})` : 'none';
        txt('tmk', stopped ? 'RIGGED IN' : 'RIG TIME');
        const cur = ops.filter(o => lt >= o.arrive - 0.25);
        const lastOp = cur.length ? cur[cur.length - 1] : null;
        txt('tms', stopped ? 'DONE · ONE SLIDER' : lastOp ? lastOp.label : 'READY');
        const step = stopped ? 10 : lastOp ? lastOp.step : 0;
        [...$('tmp').children].forEach((d, i) => { const on = step > i; d.style.background = on ? (i + 1 === step && !stopped ? '#F3D9A0' : '#C9A76A') : 'rgba(255,255,255,.15)'; });
        const kin = ramp(lt, 0.05, 0.4);
        el.querySelector('.tm').style.opacity = kin.toFixed(3);

        // ---- the report in the status line, for a few seconds after each action ----
        let rep = null;
        for (let i = 0; i < ops.length; i++) if (st[i + 1].reportAt === i && st[i].report !== st[i + 1].report && ops[i].t <= lt) rep = ops[i];
        const stat = $('stat');
        if (rep) {
          const a = ramp(lt, rep.t, rep.t + 0.15), b = 1 - ramp(lt, rep.t + 5.4, rep.t + 6.0);
          stat.style.opacity = (a * b).toFixed(3); txt('stxt', st[rep.i + 1].report);
        } else stat.style.opacity = 0;

        // ---- the pointer: what it hovers, what is pressed, the key that is held ----
        const hov = ops.find(o => (o.kind === 'click' || o.kind === 'hover') && lt >= o.arrive && lt < o.t + (o.kind === 'click' ? 0.0 : 0.0));
        const he = hov ? hoverEl(hov, S) : null;
        if (he !== hovEl) { if (hovEl) hovEl.classList.remove('hov'); if (he) he.classList.add('hov'); hovEl = he; }
        const hot = new Set(ops.filter(o => o.kind === 'click' && lt >= o.t && lt < o.t + 0.2).map(o => o));
        root.querySelectorAll('.bt.hot').forEach(b => b.classList.remove('hot'));
        hot.forEach(o => { if (/^(pn|dlg):/.test(o.target) && !/round|only|order/.test(o.target)) { const b = elOf(o.target, st[o.i]); if (b && b.classList.contains('bt')) b.classList.add('hot'); } });
        const kc = $('kc'), chip = chipRuns.find(r => lt >= r.t0 - 0.12 && lt < r.t1 + 0.3);
        if (chip) {
          const [cx, cy] = pathPos(this.keys, lt), a = ramp(lt, chip.t0 - 0.12, chip.t0 + 0.04) * (1 - ramp(lt, chip.t1 + 0.12, chip.t1 + 0.3));
          kc.textContent = chip.key === 'ctrl' ? 'Ctrl' : 'Shift'; kc.style.opacity = a.toFixed(3);
          kc.style.transform = `translate(${(cx + 30).toFixed(1)}px,${(cy + 36).toFixed(1)}px)`;
        } else kc.style.opacity = 0;

        // ---- fields being typed into ----
        const ed = ops.find(o => o.kind === 'edit' && lt >= o.dbl[0] + 0.03 && lt < o.t);
        if (ed) {
          const Sb = st[ed.i], id = fieldId(ed.target, Sb), f = $(id), count = ed.chars.filter(c => c <= lt).length;
          lastEdit = { id, text: fieldText(ed.target, Sb) };
          f.classList.add('ed');
          f.querySelector('.v').innerHTML = count ? `${ed.text.slice(0, count)}<i class="caret"></i>` : `<span class="sl">${lastEdit.text}</span>`;
        }

        // ---- the dialogs ----
        let open1 = S.dlg ? S.dlg : null, a1 = 1;
        if (!open1 && n && st[n - 1].dlg && lt < ops[n - 1].t + 0.14) { open1 = st[n - 1].dlg; a1 = 1 - ramp(lt, ops[n - 1].t + 0.02, ops[n - 1].t + 0.14); }
        else if (open1) a1 = ramp(lt, ops[S.dlgAt].t + 0.02, ops[S.dlgAt].t + 0.14);
        [['ring', 'dRw'], ['spread', 'dSw']].forEach(([key, id]) => {
          const w = $(id), on = open1 === key;
          w.style.visibility = on ? 'visible' : 'hidden'; w.style.opacity = on ? a1.toFixed(3) : 0;
          if (on) { const Sx = S.dlg ? S : st[n - 1]; placeDialog(Sx, w); w.style.transform = `translate(0px,${((1 - a1) * 14).toFixed(1)}px)`; }
        });
        if (open1 === 'ring' && (S.dv || st[n - 1].dv)) {                                  // the menu's rows: the one under the pointer is lit
          const mo = ops.find(o => o.target === 'dlg:round:World Origin' && lt >= o.arrive && lt < o.t + 0.1);
          $('mi-origin').classList.toggle('mhl', !!mo); $('mi-cursor').classList.toggle('mhl', !mo && (S.dv || st[n - 1].dv).round === '3D Cursor');
        }

        // ---- the slider ----
        $('play').querySelector('.fill').style.width = `${(s * 100).toFixed(1)}%`; txt('playv', `${Math.round(s * 100)}%`);
      },
    };
    function hoverEl(o, S) {
      try { const e = elOf(o.target, S); return e.classList.contains('nm') ? e.parentNode : e; } catch (_) { return null; }
    }
  },
};

export default [open];
