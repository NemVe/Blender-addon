// 13-25 s, THE IDEA: pose it and record it; build, one slider; many parts, one move.
import { THREE, cardView, render, toStage, cube, ghost, gizmo, select } from './stage3d.mjs';
import { clamp, mix, ramp, e3, io, kf, bk, pressed } from './lib.mjs';
import { animText, at, pathPos, panel, col, card, row, btn, fld, I, clickList, qs, setOp, view } from './ui.mjs';

const V3 = THREE.Vector3;
const BAR = [1.5, 0.62, 0.62];
const A = new V3(-1.2, 0.31, 0.3), B = new V3(1.1, 1.75, 0.3);
export const Pn = e => new V3(mix(A.x, B.x, e), mix(A.y, B.y, e) + 0.55 * Math.sin(Math.PI * e), mix(A.z, B.z, e));
export const setGhost = (g, u) => { g.visible = u > 0.01; g.material.opacity = 0.1 * u; g.userData.edge.material.opacity = 0.85 * u; };
const pt = ([x, y]) => ({ x, y });

export const recRow = (name, ico, k) =>
  row(`<div class="lbl" style="flex:0 0 205px">${I(ico)}<span>${name}</span><span class="ck" id="ck${k}" style="opacity:0"></span><span class="dot" id="dt${k}"></span></div>${btn('Record', { id: 'r' + k, c: 'w3' })}<div class="eye"></div>`);
const keyBtn = '<div class="btn sm"><i class="key"></i></div>';
export const sliderRow = (id = 'sl') => row(`${fld('Move 1', '0%', 0, { id, c: 'w3' })}${keyBtn}`, { id: id + 'row' });
// where the slider's thumb is, in stage pixels, for a value s from 0 to 1
export const thumbAt = (el, id) => { const r = qs(el, id).getBoundingClientRect(), k = view.k; return s => ({ x: (r.left + s * r.width) / k, y: (r.top + r.height / 2) / k }); };

const idea1 = {
  id: 'idea1',
  make() {
    const ck = clickList([[1.1, 'Record Before'], [1.85, 3.0, 'grab the part'], [3.45, 'Record After']]);
    let v, blk, gA, gB, giz;
    return {
      cues: ck.cues,
      build(el) {
        el.innerHTML = col('The idea · 1/3', 'Pose it.\n**Record** it.', 'Two poses are the whole move.', panel(recRow('Before', 'record_before', 'b') + recRow('After', 'record_after', 'a')))
          + card('<div class="tag g" id="tB">Before</div><div class="tag g r" id="tA">After</div>');
        v = cardView(this.index % 2); v.host = qs(el, '.cv');
        blk = cube(v, BAR); gA = ghost(v, BAR); gB = ghost(v, BAR); giz = gizmo(0.95);
        gA.position.copy(Pn(0)); gB.position.copy(Pn(1)); gB.rotation.z = Math.PI / 2;
        v.scene.add(blk, gA, gB, giz);
      },
      measure(el) {
        const g0 = new V3(0, 0, 0.31), keys = [{ t: 0.45, x: 1010, y: 1010 }, { t: 1.0, ...pt(at(qs(el, '#rb'))) }];
        keys.push({ t: 1.8, ...pt(toStage(v, Pn(0).add(g0))) });
        for (let i = 0; i <= 10; i++) keys.push({ t: 1.9 + i * 0.1, ...pt(toStage(v, Pn(io(i / 10)).add(g0))), lin: true });
        keys.push({ t: 3.38, ...pt(at(qs(el, '#ra'))) });
        this.cur = { keys, clicks: ck.clicks, hold: 0.25 };
      },
      update(lt, dur) {
        const el = this.el;
        animText(el, lt, dur);
        const e = io(ramp(lt, 1.9, 2.9));
        blk.position.copy(Pn(e)); blk.rotation.z = e * Math.PI / 2;
        blk.scale.setScalar(Math.max(1e-3, bk(ramp(lt, 0.0, 0.5))));
        setGhost(gA, ramp(lt, 1.1, 1.4)); setGhost(gB, ramp(lt, 3.45, 3.75));
        const drag = ramp(lt, 1.85, 1.95) * (1 - ramp(lt, 3.0, 3.1));
        giz.visible = drag > 0.01; giz.position.copy(blk.position); giz.userData.setOpacity(drag);
        qs(el, '#tB').style.opacity = ramp(lt, 1.1, 1.35); qs(el, '#tA').style.opacity = ramp(lt, 3.45, 3.7);
        [['b', 1.1], ['a', 3.45]].forEach(([k, t]) => {
          qs(el, '#ck' + k).style.opacity = lt >= t ? 1 : 0; qs(el, '#dt' + k).style.opacity = lt >= t ? 0 : 1;
          qs(el, '#r' + k).classList.toggle('hot', pressed(lt, t));
        });
        render(v);
      },
    };
  },
};

const idea2 = {
  id: 'idea2',
  make() {
    const ck = clickList([[0.9, 'Build Sliders'], [1.6, 3.65, 'drag the slider']]);
    const S = lt => kf(lt, [[1.6, 0], [2.65, 1], [3.0, 1], [3.6, 0.2]]);
    let v, blk;
    return {
      cues: ck.cues,
      build(el) {
        el.innerHTML = col('The idea · 2/3', 'Build.\nOne **slider**.', 'Press Build Sliders. The move lives on one control.',
          panel(row(btn('Build Sliders', { i: 'build', id: 'bb' })) + sliderRow()))
          + card('<div class="tag g">Move 1</div><div class="tag g r" id="tv">0%</div>');
        v = cardView(this.index % 2); v.host = qs(el, '.cv');
        blk = cube(v, BAR); const gA = ghost(v, BAR), gB = ghost(v, BAR);
        gA.position.copy(Pn(0)); gB.position.copy(Pn(1)); gB.rotation.z = Math.PI / 2; setGhost(gA, 1); setGhost(gB, 1);
        v.scene.add(blk, gA, gB);
      },
      measure(el) {
        const xy = thumbAt(el, '#sl');
        const keys = [{ t: 0.4, x: 1010, y: 1020 }, { t: 0.8, ...pt(at(qs(el, '#bb'))) }, { t: 1.5, ...xy(0) }];
        for (let t = 1.6; t <= 3.601; t += 0.1) keys.push({ t, ...xy(S(t)), lin: true });
        this.cur = { keys, clicks: ck.clicks, hold: 0.2 };
      },
      update(lt, dur) {
        const el = this.el;
        animText(el, lt, dur);
        const s = S(lt);
        blk.position.copy(Pn(s)); blk.rotation.z = s * Math.PI / 2;
        blk.scale.setScalar(Math.max(1e-3, bk(ramp(lt, 0.0, 0.5))));
        setOp(qs(el, '#slrow'), e3(ramp(lt, 1.0, 1.3)), 16);
        qs(el, '#sl .fill').style.width = `${(s * 100).toFixed(1)}%`; qs(el, '#sl .v').textContent = `${Math.round(s * 100)}%`;
        qs(el, '#tv').textContent = `${Math.round(s * 100)}%`;
        qs(el, '#bb').classList.toggle('hot', pressed(lt, 0.9));
        render(v);
      },
    };
  },
};

const idea3 = {
  id: 'idea3',
  make() {
    const ck = clickList([[1.95, 3.2, 'drag the slider']]);
    const S = lt => kf(lt, [[2.0, 0], [3.1, 1]]);
    const TILE = [0.62, 0.34, 0.62];
    let v, box;
    const cubes = [];
    return {
      cues: ck.cues,
      build(el) {
        el.innerHTML = col('The idea · 3/3', 'Many parts.\nOne **move**.', 'Select a dozen parts. They share the move.',
          panel(row('<div class="lbl"><span>CopyThat Rig</span></div><div class="lbl mute" style="justify-content:flex-end"><span id="cnt">0 parts</span></div>') + sliderRow()))
          + card('<div class="tag g">12 parts</div><div class="tag g r" id="tv">0%</div><div id="mq" style="position:absolute;display:none;border:3px dashed rgba(255,255,255,.9);background:rgba(255,255,255,.07);border-radius:3px"></div>');
        v = cardView(this.index % 2, { pos: [0, 4.4, 10.0], look: [0, 0.9, 0] }); v.host = qs(el, '.cv');
        for (let r = 0; r < 2; r++) for (let c = 0; c < 6; c++) {
          const m = cube(v, TILE); m.userData.home = new V3((c - 2.5) * 0.86, TILE[1] / 2, (r - 0.5) * 0.9); v.scene.add(m); cubes.push(m);
        }
      },
      measure(el) {
        this.pts = cubes.map(m => toStage(v, m.userData.home));
        const xs = this.pts.map(p => p[0]), ys = this.pts.map(p => p[1]);
        box = { x0: Math.min(...xs) - 70, y0: Math.min(...ys) - 80, x1: Math.max(...xs) + 70, y1: Math.max(...ys) + 60 };
        const xy = thumbAt(el, '#sl');
        const keys = [{ t: 0.4, x: box.x0 - 60, y: box.y0 - 80 }, { t: 0.62, x: box.x0, y: box.y0, straight: true }, { t: 1.4, x: box.x1, y: box.y1, lin: true }, { t: 1.9, ...xy(0) }];
        for (let t = 2.0; t <= 3.201; t += 0.1) keys.push({ t, ...xy(S(t)), lin: true });
        this.cur = { keys, clicks: ck.clicks, hold: 0.2 };
      },
      update(lt, dur) {
        const el = this.el;
        animText(el, lt, dur);
        const s = S(lt), e = io(clamp(s));
        let n = 0;
        const [cx, cy] = pathPos(this.cur.keys, lt);
        const drag = lt >= 0.62 && lt <= 1.45;
        const mq = qs(el, '#mq');
        mq.style.display = drag ? 'block' : 'none';
        mq.style.left = `${box.x0 - 1075}px`; mq.style.top = `${box.y0 - 150}px`;
        mq.style.width = `${Math.max(0, Math.min(cx, box.x1) - box.x0)}px`; mq.style.height = `${Math.max(0, Math.min(cy, box.y1) - box.y0)}px`;
        cubes.forEach((m, i) => {
          const home = m.userData.home, u = bk(ramp(lt, i * 0.03, 0.4 + i * 0.03));
          m.scale.setScalar(Math.max(1e-3, u));
          m.position.set(home.x, home.y + 1.25 * e + 0.35 * Math.sin(Math.PI * e), home.z);
          m.rotation.x = e * Math.PI / 2;
          const [px, py] = this.pts[i], sel = (lt >= 0.62 && px < cx && py < cy) || lt > 1.45;
          select(m, sel); if (sel) n++;
        });
        qs(el, '#cnt').textContent = `${n} parts`;
        qs(el, '#sl .fill').style.width = `${(s * 100).toFixed(1)}%`; qs(el, '#sl .v').textContent = `${Math.round(s * 100)}%`;
        qs(el, '#tv').textContent = `${Math.round(s * 100)}%`;
        render(v);
      },
    };
  },
};

export default [idea1, idea2, idea3];
