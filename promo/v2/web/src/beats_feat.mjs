// 25-41.5 s, FEATURES 01-06: timing, spread, pivot, steps, curves, speed. Each is 2.75 s: the cursor clicks near 1 s and the card shows the effect.
import { THREE, V3, pt, IN, feat, drow, drop, pr, setFat, ball, coin, cursor3d, stageXY, tagAt, cardView, render, toStage, cube, ghost, fat, std, goldMat, GOLD, GOLD2,
  row, btn, fld, lbl, cb, sec, note, I, qs, at, ramp, e3, kf, mix, io } from './kit.mjs';
import { animText, clickList, setOp, panel, dialog } from './ui.mjs';
import { clamp, bk, hump, pressed } from './lib.mjs';
import more from './beats_feat2.mjs';

// ---- 01 timing: three cubes start one after another ----
const f01 = {
  id: 'f01',
  make() {
    const ck = clickList([[0.95, 1.4, 'drag the delay']]);
    const D = lt => kf(lt, [[0.95, 0], [1.4, 0.6]]);
    const X = [-1.7, 0, 1.7];
    let v; const cubes = [];
    return {
      cues: ck.cues,
      build(el) {
        feat(el, '01', 'Timing', 'Each part,\nits own **delay**.', 'How long each part waits before it starts.',
          panel(sec('Timing', 'timing', { right: btn('Spread…', { i: 'spread' }) }) + note('how long each one waits before it starts')
            + drow('Block A', '0.00', 0, 'dA') + drow('Block B', '0.30', 0.5, 'dB') + drow('Block C', '0.00', 0, 'dC')),
          '<div class="tag g">Delay</div>' + X.map((_, i) => `<div class="tag g bd" id="bd${i}">0.00 s</div>`).join(''));
        v = cardView(this.index % 2); v.host = qs(el, '.cv');
        X.forEach(x => { const c = cube(v, [0.95, 0.95, 0.95]); c.position.set(x, 0.475, 0); v.scene.add(c); cubes.push(c); });
      },
      measure(el) {
        X.forEach((x, i) => tagAt(el, v, '#bd' + i, new V3(x, 2.9, 0)));
        const f = fx => pt(at(qs(el, '#dC'), fx, 0.5));
        this.cur = { keys: [{ t: 0.4, ...IN }, { t: 0.85, ...f(0.1) }, { t: 0.95, ...f(0.1) }, { t: 1.4, ...f(0.92), lin: true }], clicks: ck.clicks, hold: 0.4 };
      },
      update(lt, dur) {
        const el = this.el;
        animText(el, lt, dur);
        const d = D(lt), delays = [0, 0.3, d];
        qs(el, '#dC .fill').style.width = `${(d / 0.6 * 92).toFixed(1)}%`; qs(el, '#dC .v').textContent = d.toFixed(2);
        cubes.forEach((c, i) => {
          const u = io(ramp(lt, 1.5 + delays[i], 2.2 + delays[i]));
          c.position.y = 0.475 + 1.5 * u; c.rotation.y = u * Math.PI / 2; c.rotation.z = u * 0.5;
          const b = qs(el, '#bd' + i); b.textContent = `${delays[i].toFixed(2)} s`; b.style.opacity = ramp(lt, 0.4 + i * 0.1, 0.75 + i * 0.1);
        });
        render(v);
      },
    };
  },
};

// ---- 02 spread: the dialog, then a wave ----
const f02 = {
  id: 'f02',
  make() {
    const ck = clickList([[1.45, 'OK']]);
    const tiles = [];
    let v;
    return {
      cues: ck.cues,
      build(el) {
        feat(el, '02', 'Spread', 'A **wave**\nin one click.', "Fill in every part's delay from one dialog.",
          dialog('Spread', pr('Order', drop('Along an axis')) + pr('', `<div style="display:flex;align-items:center;gap:12px">${cb(false)}<span>Only the selected</span></div>`)
            + pr('', btn('X', { c: 'on' }) + btn('Y') + btn('Z')) + pr('By', btn('Step', { c: 'on' }) + btn('Range'))
            + pr('Start Delay', fld('', '0.00', 0, { c: 'c' })) + pr('Delay step', fld('', '0.00', 0, { id: 'ds', c: 'c' })), { okId: 'ok', id: 'dg' }),
          '<div class="tag g">Delay</div><div class="tag g r" id="tw">+0.09 s each</div>');
        v = cardView(this.index % 2, { pos: [0, 2.6, 9.4], look: [0, 0.9, 0] }); v.host = qs(el, '.cv');
        for (let i = 0; i < 8; i++) { const c = cube(v, [0.5, 0.5, 0.5]); c.position.set((i - 3.5) * 0.64, 0.25, 0); v.scene.add(c); tiles.push(c); }
      },
      measure(el) {
        const f = fx => pt(at(qs(el, '#ds'), fx, 0.5));
        this.cur = { keys: [{ t: 0.4, ...IN }, { t: 0.72, ...f(0.12) }, { t: 0.8, ...f(0.12) }, { t: 1.2, ...f(0.78), lin: true }, { t: 1.4, ...pt(at(qs(el, '#ok'))) }], clicks: ck.clicks, hold: 0.25 };
      },
      update(lt, dur) {
        const el = this.el;
        animText(el, lt, dur);
        const d = kf(lt, [[0.8, 0], [1.2, 0.09]]);
        qs(el, '#ds .fill').style.width = `${(d / 0.09 * 78).toFixed(1)}%`; qs(el, '#ds .v').textContent = d.toFixed(2);
        qs(el, '#ok').classList.toggle('hot', pressed(lt, 1.45));
        const dg = qs(el, '#dg'), gone = ramp(lt, 1.62, 1.85);
        dg.style.opacity = (1 - 0.7 * gone).toFixed(3);
        qs(el, '#tw').style.opacity = ramp(lt, 1.5, 1.8);
        tiles.forEach((c, i) => {
          const h = hump(ramp(lt, 1.5 + 0.09 * i, 2.15 + 0.09 * i));
          c.position.y = 0.25 + 1.4 * h; c.rotation.z = h * 0.5; c.rotation.x = h * 0.3;
        });
        render(v);
      },
    };
  },
};

// ---- 03 pivot: a lid that turns about the 3D cursor ----
const f03 = {
  id: 'f03',
  make() {
    const ck = clickList([[0.95, 'Pivot: 3D Cursor']]);
    const PIV = new V3(0, 1.0, -0.9), LC = new V3(0, 0.99, 0), AX = new V3(1, 0, 0);
    let v, lid, c3;
    return {
      cues: ck.cues,
      build(el) {
        feat(el, '03', 'Pivot', 'Turn about\n**any point**.', 'Origin, the 3D cursor or the base.',
          panel(sec('Parts & Pivot', 'pivot') + row('<div class="lbl" style="flex:0 0 150px"><span>Parts</span></div>' + btn('1 selected'))
            + row('<div class="lbl" style="flex:0 0 150px"><span>Pivot</span></div>' + btn('Origin', { id: 'pO', c: 'on' }) + btn('3D Cursor', { id: 'pC' }) + btn('Base', { id: 'pB' }))),
          '<div class="tag g" id="pt">Origin</div>');
        v = cardView(this.index % 2, { pos: [1.6, 3.4, 7.6], look: [0, 1.1, 0] }); v.host = qs(el, '.cv');
        const base = cube(v, [2.8, 0.9, 1.9], { color: 0x3a3a41, rough: 0.5, metal: 0.35 }); base.position.set(0, 0.45, 0);
        lid = cube(v, [2.8, 0.18, 1.9]); lid.position.copy(LC);
        const pin = new THREE.Mesh(new THREE.CylinderGeometry(0.085, 0.085, 3.0, 28), goldMat()); pin.rotation.z = Math.PI / 2; pin.position.copy(PIV); pin.castShadow = true;
        c3 = cursor3d(v); c3.position.copy(PIV);
        v.scene.add(base, lid, pin, c3);
      },
      measure(el) {
        this.cur = { keys: [{ t: 0.4, ...IN }, { t: 0.9, ...pt(at(qs(el, '#pC'))) }], clicks: ck.clicks, hold: 0.4 };
      },
      update(lt, dur) {
        const el = this.el;
        animText(el, lt, dur);
        const after = lt >= 0.95;
        const ang = after ? kf(lt, [[1.05, 0], [2.05, 1.75]]) : 0.5 * hump(ramp(lt, 0.25, 0.95));
        if (after) lid.position.copy(PIV).add(LC.clone().sub(PIV).applyAxisAngle(AX, -ang)); else lid.position.copy(LC);
        lid.rotation.x = -ang;
        c3.visible = after; c3.scale.setScalar(Math.max(1e-3, bk(ramp(lt, 0.95, 1.2)))); c3.quaternion.copy(v.camera.quaternion);
        qs(el, '#pO').classList.toggle('on', !after); qs(el, '#pC').classList.toggle('on', after); qs(el, '#pC').classList.toggle('hot', pressed(lt, 0.95));
        qs(el, '#pt').textContent = after ? '3D Cursor' : 'Origin';
        render(v);
      },
    };
  },
};

// ---- 04 steps: the path bends through an added pose ----
const f04 = {
  id: 'f04',
  make() {
    const ck = clickList([[1.0, 'Step in between']]);
    const Ap = new V3(-2.3, 0.5, 0), Bp = new V3(2.3, 0.5, 0), M = new V3(0.1, 2.1, 0.3);
    let v, mover, mid, line;
    const midAt = lt => new V3().lerpVectors(new V3(0, 0.5, 0), M, e3(ramp(lt, 1.05, 1.55)));
    const along = (s, m) => (s < 0.5 ? new V3().lerpVectors(Ap, m, s * 2) : new V3().lerpVectors(m, Bp, (s - 0.5) * 2));
    return {
      cues: ck.cues,
      build(el) {
        feat(el, '04', 'Steps', 'Steps\n**in between**.', 'Add a pose between Before and After.',
          panel(sec('Path', 'curve') + row(btn('Step in between', { i: 'steps', id: 'sb' })) + row(`<div class="lbl mute" style="flex:0 0 170px" id="s1l"><span>Step 1</span></div>${fld('Speed', '0', 0.5, { id: 's1' })}`, { id: 's1r' })),
          '<div class="tag g">Before</div><div class="tag g r">After</div><div class="tag g bd" id="ts">Step 1</div>');
        v = cardView(this.index % 2, { pos: [0, 3.2, 9.4], look: [0, 1.2, 0] }); v.host = qs(el, '.cv');
        const size = [0.9, 0.9, 0.9], gA = ghost(v, size), gB = ghost(v, size);
        gA.position.copy(Ap); gB.position.copy(Bp);
        mid = ghost(v, size); mid.position.copy(M);
        mover = cube(v, size);
        line = fat(v, [Ap, new V3(0, 0.5, 0), Bp], { color: GOLD2, w: 3, dashed: true, dash: 0.12, gap: 0.1 });
        v.scene.add(gA, gB, mid, mover, line);
      },
      measure(el) {
        const m = this.m = { x: 0, y: 0 };
        this.cur = { keys: [{ t: 0.5, ...IN }, { t: 0.95, ...pt(at(qs(el, '#sb'))) }], clicks: ck.clicks, hold: 0.5 };
      },
      update(lt, dur) {
        const el = this.el;
        animText(el, lt, dur);
        const m = midAt(lt);
        setFat(line, [Ap, m, Bp]);
        const s = lt < 1.6 ? io(ramp(lt, 0.25, 0.85)) * (1 - ramp(lt, 1.0, 1.5)) : io(ramp(lt, 1.6, 2.6));
        mover.position.copy(along(s, m)); mover.rotation.z = -s * 0.8; mover.rotation.y = s * 0.6;
        const u = bk(ramp(lt, 1.0, 1.35));
        mid.visible = u > 0.01; mid.scale.setScalar(Math.max(1e-3, u)); mid.position.copy(m);
        mid.material.opacity = 0.12; mid.userData.edge.material.opacity = 0.9;
        tagAt(el, v, '#ts', m.clone().add(new V3(1.1, 0.4, 0)));
        qs(el, '#ts').style.opacity = ramp(lt, 1.2, 1.5);
        setOp(qs(el, '#s1r'), e3(ramp(lt, 1.15, 1.45)), 14);
        qs(el, '#sb').classList.toggle('hot', pressed(lt, 1.0));
        render(v);
      },
    };
  },
};

// ---- 05 curves: a coin on a bezier path, a handle dragged ----
const f05 = {
  id: 'f05',
  make() {
    const ck = clickList([[0.95, 'Curve the Path'], [1.4, 2.0, 'drag the handle']]);
    const Ap = new V3(-2.4, 0.55, 0), Bp = new V3(2.4, 0.55, 0);
    const C1a = new V3(-0.8, 0.55, 0), C1b = new V3(-1.3, 2.5, 0.2), C2 = new V3(0.8, 0.55, 0);
    const C1 = lt => new V3().lerpVectors(C1a, C1b, io(ramp(lt, 1.45, 2.0)));
    let v, line, coinM, h1, h2, l1, l2;
    const curve = lt => new THREE.CubicBezierCurve3(Ap, C1(lt), C2, Bp);
    return {
      cues: ck.cues,
      build(el) {
        feat(el, '05', 'Curves', 'Curve the path.\n**Edit its curve.**', 'Bend the path in edit mode, then Build.',
          panel(sec('Path', 'curve') + row(btn('Curve the Path', { i: 'curve', id: 'cp' }))
            + row(`<div class="lbl" style="flex:0 0 270px">${I('curve')}<span>Outer Leader</span></div>${btn('Edit', { id: 'ed' })}<div class="x">×</div>`, { id: 'crow' })
            + note('bend it in edit mode, then Build')),
          '<div class="tag g">Path</div>');
        v = cardView(this.index % 2, { pos: [0, 3.0, 9.4], look: [0, 1.3, 0] }); v.host = qs(el, '.cv');
        line = fat(v, curve(0).getPoints(80), { color: GOLD2, w: 4 });
        coinM = coin(); h1 = ball(0.12); h2 = ball(0.12);
        h1.material = std(0xffffff, 0.3, 0); h2.material = std(0xffffff, 0.3, 0);
        l1 = fat(v, [Ap, C1a], { color: 0xffffff, w: 1.8, op: 0.7 }); l2 = fat(v, [Bp, C2], { color: 0xffffff, w: 1.8, op: 0.7 });
        const ga = ghost(v, [0.7, 0.7, 0.7]), gb = ghost(v, [0.7, 0.7, 0.7]); ga.position.copy(Ap); gb.position.copy(Bp);
        v.scene.add(line, coinM, h1, h2, l1, l2, ga, gb);
      },
      measure(el) {
        const keys = [{ t: 0.5, ...IN }, { t: 0.9, ...pt(at(qs(el, '#cp'))) }, { t: 1.35, ...stageXY(v, C1(0)) }];
        for (let t = 1.4; t <= 2.001; t += 0.05) keys.push({ t, ...stageXY(v, C1(t)), lin: true });
        this.cur = { keys, clicks: ck.clicks, hold: 0.3 };
      },
      update(lt, dur) {
        const el = this.el;
        animText(el, lt, dur);
        const c = curve(lt), c1 = C1(lt);
        setFat(line, c.getPoints(80));
        const hs = bk(ramp(lt, 0.95, 1.25)), vis = lt >= 0.95;
        [h1, h2, l1, l2].forEach(o => { o.visible = vis; });
        h1.position.copy(c1); h2.position.copy(C2); h1.scale.setScalar(Math.max(1e-3, hs)); h2.scale.setScalar(Math.max(1e-3, hs));
        setFat(l1, [Ap, c1]); setFat(l2, [Bp, C2]);
        const u = io(ramp(lt, 1.95, 2.65)), p = c.getPoint(u);
        coinM.position.copy(p); coinM.rotation.z = u * 7;
        setOp(qs(el, '#crow'), e3(ramp(lt, 1.0, 1.3)), 14);
        qs(el, '#cp').classList.toggle('hot', pressed(lt, 0.95));
        render(v);
      },
    };
  },
};

// ---- 06 speed: even against smooth ----
const f06 = {
  id: 'f06',
  make() {
    const ck = clickList([[0.95, 'Smooth']]);
    const Y = [1.95, 0.75], X0 = -2.3, X1 = 2.3;
    let v; const balls = [];
    return {
      cues: ck.cues,
      build(el) {
        feat(el, '06', 'Speed', '**Smooth**\nor even.', 'Even speed, smooth, slow start or slow stop.',
          panel(sec('Path', 'curve') + row(btn('Even speed', { id: 'e0', c: 'on' }) + btn('Smooth', { id: 'e1' })) + row(btn('Slow start') + btn('Slow stop'))),
          '<div class="tag g bd" id="t0">Even speed</div><div class="tag g bd" id="t1">Even speed</div>');
        v = cardView(this.index % 2, { pos: [0, 2.7, 9.2], look: [0, 1.3, 0] }); v.host = qs(el, '.cv');
        Y.forEach(y => {
          v.scene.add(fat(v, [[X0, y, 0], [X1, y, 0]], { color: GOLD, w: 3, op: 0.55 }));
          [X0, X1].forEach(x => v.scene.add(fat(v, [[x, y - 0.18, 0], [x, y + 0.18, 0]], { color: GOLD, w: 3, op: 0.7 })));
          const b = ball(0.36); b.position.set(X0, y, 0); v.scene.add(b); balls.push(b);
        });
      },
      measure(el) {
        Y.forEach((y, i) => tagAt(el, v, '#t' + i, new V3(X0 + 0.35, y + 0.75, 0)));
        this.cur = { keys: [{ t: 0.5, ...IN }, { t: 0.9, ...pt(at(qs(el, '#e1'))) }], clicks: ck.clicks, hold: 0.5 };
      },
      update(lt, dur) {
        const el = this.el;
        animText(el, lt, dur);
        const after = lt >= 0.95;
        const loop = (a, ez) => { const ph = ((lt - a) % 1.5 + 1.5) % 1.5, u = clamp(ph / 1.05); return lt < a ? 0 : ez(u); };
        const u0 = loop(0.25, x => x), u1 = loop(0.25, after ? io : x => x);
        [u0, u1].forEach((u, i) => { balls[i].position.x = mix(X0, X1, u); balls[i].rotation.z = -u * 9; });
        qs(el, '#e0').classList.toggle('on', !after); qs(el, '#e1').classList.toggle('on', after); qs(el, '#e1').classList.toggle('hot', pressed(lt, 0.95));
        qs(el, '#t1').textContent = after ? 'Smooth' : 'Even speed';
        qs(el, '#t0').style.opacity = ramp(lt, 0.2, 0.5); qs(el, '#t1').style.opacity = ramp(lt, 0.25, 0.55);
        render(v);
      },
    };
  },
};

export default [f01, f02, f03, f04, f05, f06, ...more];
