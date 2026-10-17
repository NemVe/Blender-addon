// 0-12 s, the opening: "Let's rig this flower in twelve clicks." The real flower, a copy of the 0.20 panel, and a counter that
// ticks with every button or OK the cursor presses. Pose drags are shown but not counted. The cursor's schedule is tb.steps
// (seconds into the beat), which make_timeline.py sets a little after the first line of the voice.
import { THREE, mkView, render, instFlower, toStage } from './stage3d.mjs';
import { clamp, mix, ramp, e3, io, kf, bk, hump, pressed, D2R } from './lib.mjs';
import { panel, row, btn, sec, note, fld, clickList, qs, at, dialog, prow, cb } from './ui.mjs';
import { thumbAt, sliderRow, recRow } from './beats_idea.mjs';
import { drop } from './kit.mjs';

const Y = new THREE.Vector3(0, 1, 0);
const pt = ([x, y]) => ({ x, y });
const IN = { x: 2020, y: 1330 };                           // where the cursor comes in from, below the panel
const SHIFT = 320;                                         // the flower stands this far left of the middle of the frame
const DRAG = 1.8;                                          // the last click drags the slider for this long
const GLOW = 0.28;                                          // emissive strength of a part that is lit gold
const POSE_GAP = 0.25, POSE_LEN = 0.2;                     // four pose drags, one every 0.25 s

// the click that the counter shows, in order: [step, what it says under the counter]
const COUNTED = [['new', 'New Move'], ['chain', 'Make Chain'], ['rec', 'Record After'], ['r1', 'Ring… · outer petals'], ['o1', 'OK · 7 copies'],
  ['r2', 'Ring… · inner petals'], ['o2', 'OK · 5 copies'], ['r3', 'Ring… · the leaf'], ['o3', 'OK · 1 copy'], ['sp', 'Spread… · timing'],
  ['o4', 'OK · delays filled in'], ['build', 'Build Sliders']];
// what the panel's report line says after each one (the add-on's own words, shortened)
const REPORT = ['Select the parts that move.', "6 part(s). Where they stand now is Before.", 'Chain: Leaf 1 > Leaf 2 > Leaf 3',
  'After recorded for 6 part(s).', '', "7 copies of 'Outer Leader' ride along with it.", '', "5 copies of 'Inner Leader' ride along with it.", '',
  "1 copy of 'Leaf 1' (3 joints each) rides along.", '', 'Spread the Delays of 3 parts in steps of 0.15.', '', '21 part(s) on 1 slider(s).'];

const open = {
  id: 'open',
  make(ctx, tb) {
    const S = tb.steps, M = ctx.F.motion, G = M.groups;
    const DUR = tb.end - tb.start;
    const names = Object.keys(M.motion);                                   // the 21 moving parts
    const lead = [G.outer_petals.slice(0, 1), G.inner_petals.slice(0, 1), G.core, G.leaf_a];   // what each pose drag grabs: the parts made once
    const bare = new Set(lead.flat());
    const f0 = lead.map(g => 150 * Math.min(...g.map(n => M.parts[n].window[0])));   // a part moves only in its window of the slider
    const kOf = n => lead.findIndex(g => g.includes(n));
    const poseT = k => S.pose + k * POSE_GAP;
    const poseU = (k, lt) => io(ramp(lt, poseT(k), poseT(k) + POSE_LEN)) * (1 - e3(ramp(lt, S.build, S.build + 0.3)));   // Build puts every part back to Before
    const ang = n => (M.parts[n].ring_angle_deg || 0) * D2R;
    const copies = [];
    G.outer_petals.slice(1).forEach((n, i) => copies.push({ n, L: G.outer_petals[0], t: S.o1 + 0.04 + i * 0.05, a: ang(n) }));
    G.inner_petals.slice(1).forEach((n, i) => copies.push({ n, L: G.inner_petals[0], t: S.o2 + 0.04 + i * 0.05, a: ang(n) }));
    G.leaf_b.forEach((n, i) => copies.push({ n, L: G.leaf_a[i], t: S.o3 + 0.04 + i * 0.08, a: Math.PI }));   // the second leaf is the first, turned 180
    const joinOf = {}; copies.forEach(c => { joinOf[c.n] = c.t; });
    const POPS = ['pop', 'pop_2', 'pop_3'];
    const popCues = copies.map((c, i) => ({ lt: c.t + 0.04, kind: 'pop', name: POPS[i % 3] }));
    // the counted clicks, the pose drags (soft: no ripple) and the slider drag
    const counted = clickList(COUNTED.map(([id, what]) => [S[id], what]));
    const drags = clickList(['Outer Leader', 'Inner Leader', 'Core', 'Leaf'].map((w, k) => [poseT(k), poseT(k) + POSE_LEN, 'pose: ' + w]));
    drags.clicks.forEach(c => { c.soft = true; });
    const slide = clickList([[S.drag, S.drag + DRAG, 'drag the slider']]);
    const clicks = [...counted.clicks, ...drags.clicks, ...slide.clicks].sort((a, b) => a.t - b.t);
    const w12 = (ctx.T.lines.open_a.words.find(w => /twelve|12/i.test(w.w)) || { start: tb.start + 1.9 }).start - tb.start;
    const rest = {}, qrest = {};
    let v, FL, bars = [];
    const mats = {};

    // the camera orbits a little all the way, and rises for the bloom; the flower stands left of the panel
    const setCam = lt => {
      const az = mix(-0.8, 0.3, clamp(lt / DUR)), up = io(ramp(lt, S.build, S.drag + DRAG)), el = D2R * (8 + 10 * up), R = 8.6 + 0.6 * up, ty = 1.15 + 0.15 * up;
      v.camera.position.set(R * Math.sin(az) * Math.cos(el), ty + R * Math.sin(el), R * Math.cos(az) * Math.cos(el));
      v.camera.lookAt(0, ty, 0);
      v.camera.setViewOffset(2560, 1440, SHIFT, 0, 2560, 1440);
    };
    // a part is lit gold by what is being done to it: the move, the chain, its own pose drag, its ring, the spread, the build
    const pulse = (lt, t0, len) => ramp(lt, t0, t0 + 0.05) * (1 - ramp(lt, t0 + 0.05, t0 + len));
    const glowOf = (n, lt, i) => {
      let g = pulse(lt, S.build, 0.5);
      if (bare.has(n)) g = Math.max(g, pulse(lt, S.new, 0.9), pulse(lt, poseT(kOf(n)), 0.55));
      if (G.leaf_a.includes(n)) g = Math.max(g, pulse(lt, S.chain, 0.8));
      if (joinOf[n] !== undefined) g = Math.max(g, pulse(lt, joinOf[n], 0.7));
      return Math.max(g, pulse(lt, S.o4 + i * 0.012, 0.5));
    };

    return {
      cues: [...counted.cues, ...drags.cues, ...slide.cues, ...popCues],
      build(el) {
        const dlgRow = (label, inner) => prow(label, inner);
        const ringDlg = dialog('Ring', dlgRow('Count', fld('', '2', 0.2, { id: 'cn', c: 'c' })) + dlgRow('Round', drop('World Origin'))
          + dlgRow('Lead step', fld('', '0', 0, { id: 'ls', c: 'c' })), { okId: 'ok1' });
        const spreadDlg = dialog('Spread', dlgRow('Order', drop('Down a chain'))
          + dlgRow('', `<div style="display:flex;align-items:center;gap:12px">${cb(true)}<span>Only the selected</span></div>`)
          + dlgRow('Start Delay', fld('', '0.10', 0.1, { c: 'c' })) + dlgRow('Delay step', fld('', '0.10', 0.1, { id: 'ds', c: 'c' })), { okId: 'ok2' });
        const mini = panel(note('Record a move. Get a slider.')
          + row('<div class="lbl"><span>CopyThat Rig</span></div><div class="lbl mute" style="justify-content:flex-end"><span id="cnt">6 objects selected</span></div>')
          + row(btn('New Move', { i: 'new_move', id: 'nm', c: 'on' }), { c: 'tall' })
          + `<div class="box" id="mv">${recRow('Before', 'record_before', 'b')}${recRow('After', 'record_after', 'a')}</div>`
          + sec('Timing', 'timing', { right: btn('Spread…', { i: 'spread', id: 'sp' }) })
          + sec('Copies', 'ring', { right: btn('Ring…', { i: 'ring', id: 'rg' }) })
          + sec('Chains', 'chain', { right: btn('Make Chain', { i: 'chain', id: 'mc' }) })
          + row(btn('Build Sliders', { i: 'build', id: 'bs', c: 'on' }), { c: 'tall' })
          + sliderRow()
          + '<div class="rep" id="rep"></div>', { sub: '' });
        const pips = COUNTED.map(() => '<i></i>').join('');
        const barsHTML = names.map((n, i) => {
          const [a, b] = M.parts[n].window;
          return `<i style="position:absolute;left:${(a * 100).toFixed(2)}%;width:${((b - a) * 100).toFixed(2)}%;top:${i * 6}px;height:4px;border-radius:2px;background:#C9A76A"></i>`;
        }).join('');
        el.innerHTML = `
          <div class="full"></div><div class="shade"></div>
          <div class="ct" style="left:154px;top:150px">
            <div class="ct-k">Let's rig this flower in</div>
            <div class="ct-n"><span id="cn0">00</span><span class="of">/12</span></div>
            <div class="ct-w">CLICKS</div>
            <div class="ct-p">${pips}</div>
            <div class="ct-s" id="cs"></div>
          </div>
          <div class="tag g" id="ptag" style="left:154px;top:742px">Pose it: drags, not clicks</div>
          <div id="bars" style="position:absolute;left:170px;width:1260px;top:1236px;height:${names.length * 6}px">${barsHTML}<i id="bph" style="position:absolute;top:-14px;bottom:-14px;width:3px;background:#fff;left:0"></i></div>
          <div id="op" style="position:absolute;left:1706px;top:150px;width:700px"><div style="zoom:1.2">${mini}</div></div>
          <div id="dR" style="position:absolute;left:1490px;top:640px;width:580px;opacity:0"><div style="zoom:1.2">${ringDlg}</div></div>
          <div id="dS" style="position:absolute;left:1490px;top:600px;width:580px;opacity:0"><div style="zoom:1.2">${spreadDlg}</div></div>`;
        v = mkView({ w: 2560, h: 1440, fov: 26, pos: [0, 2, 8.6], look: [0, 1.15, 0], slot: this.index % 2, bloom: 0.3, env: 0.65 });
        v.host = qs(el, '.full');
        FL = instFlower(ctx.F); FL.coreScale = 0.6; FL.pose(0);
        v.scene.add(FL.root);
        names.forEach(n => {                       // each part gets its own materials, so a glow lights that part only
          rest[n] = FL.parts[n].position.clone(); qrest[n] = FL.parts[n].quaternion.clone();
          FL.parts[n].traverse(o => {
            if (!o.isMesh || /core glow/i.test(o.material.name)) return;
            o.material = o.material.clone();
            o.material.emissive.setRGB(0.9, 0.58, 0.16);
            (mats[n] = mats[n] || []).push(o.material);
          });
        });
        bars = [...qs(el, '#bars').querySelectorAll('i')];
      },
      measure(el) {
        const P = (sel, fx = 0.5, fy = 0.5) => pt(at(qs(el, sel), fx, fy));
        const keys = [];
        const hit = (t, p) => keys.push({ t: t - 0.03, ...p }, { t: t + 0.1, ...p });   // arrive just before the click, stay for the press
        // the dialogs open beside their buttons, as Blender's do
        const place = (id, btnSel, dy) => { const p = at(qs(el, btnSel)); qs(el, id).style.top = `${p[1] - 1 + dy}px`; };
        place('#dR', '#rg', -60); place('#dS', '#sp', -60);
        // where a pose drag holds its part, at a time (the camera and the part are put where they are then)
        const grab = (k, t) => {
          setCam(t);
          lead[k].forEach(n => FL.part(n, mix(f0[k], 150, poseU(k, t))));
          const box = new THREE.Box3();
          lead[k].forEach(n => box.expandByObject(FL.parts[n]));
          const c = box.getCenter(new THREE.Vector3());
          return pt(toStage(v, new THREE.Vector3(c.x, mix(box.min.y, box.max.y, k === 3 ? 0.5 : 0.62), c.z)));
        };
        keys.push({ t: S.new - 0.8, ...IN });
        hit(S.new, P('#nm')); hit(S.chain, P('#mc'));
        for (let k = 0; k < 4; k++) {
          const t0 = poseT(k), t1 = t0 + POSE_LEN;
          keys.push({ t: t0 - 0.02, ...grab(k, t0 + 0.01) });
          for (let i = 1; i <= 4; i++) keys.push({ t: mix(t0, t1, i / 4), ...grab(k, mix(t0, t1, i / 4)), lin: true });
        }
        hit(S.rec, P('#ra'));
        [['r1', 'o1', '#cn'], ['r2', 'o2', '#cn'], ['r3', 'o3', '#cn']].forEach(([a, b, f]) => {
          hit(S[a], P('#rg')); keys.push({ t: S[a] + 0.2, ...P(f, 0.5, 0.5) }); hit(S[b], P('#ok1'));
        });
        hit(S.sp, P('#sp')); keys.push({ t: S.sp + 0.2, ...P('#ds', 0.5, 0.5) }); hit(S.o4, P('#ok2'));
        hit(S.build, P('#bs'));
        const xy = thumbAt(el, '#sl');
        keys.push({ t: S.drag - 0.04, ...xy(0) });
        for (let t = S.drag; t <= S.drag + DRAG + 0.001; t += 0.1) keys.push({ t, ...xy(kf(t, [[S.drag, 0], [S.drag + DRAG, 1]])), lin: true });
        this.cur = { keys, clicks, hold: 0.3 };
      },
      update(lt, dur) {
        const el = this.el;
        el.style.opacity = ramp(lt, 0, 0.3).toFixed(3);
        setCam(lt);
        const s = lt >= S.drag ? kf(lt, [[S.drag, 0], [S.drag + DRAG, 1]]) : 0;
        // the parts: the six made once, posed by hand one drag at a time; the ring copies spin in; then the real motion on the slider
        if (lt >= S.drag) {
          FL.pose(150 * s);
          names.forEach(n => { FL.parts[n].visible = true; });
        } else {
          FL.pose(0);
          names.forEach(n => { FL.parts[n].visible = bare.has(n); });
          lead.forEach((g, k) => { const u = poseU(k, lt); if (u > 0) g.forEach(n => FL.part(n, mix(f0[k], 150, u))); });
          copies.forEach(c => {
            const node = FL.parts[c.n], u = ramp(lt, c.t, c.t + 0.32);
            node.visible = u > 0;
            if (u > 0) {
              const a = c.a * e3(u);
              node.position.copy(rest[c.L]).applyAxisAngle(Y, a);
              node.quaternion.setFromAxisAngle(Y, a).multiply(qrest[c.L]);
              node.scale.setScalar(Math.max(1e-3, bk(u)));
            }
          });
        }
        names.forEach((n, i) => { const g = glowOf(n, lt, i) * GLOW; (mats[n] || []).forEach(m => { m.emissiveIntensity = g; }); });
        FL.root.visible = true;
        render(v);

        // the counter
        let count = 0, last = -9;
        COUNTED.forEach(([id], i) => { if (lt >= S[id]) { count = i + 1; last = S[id]; } });
        const pop = 1 - ramp(lt, last, last + 0.3), fin = ramp(lt, S.build, S.build + 0.25);
        const gold = `rgb(${Math.round(mix(255, 201, fin))},${Math.round(mix(255, 167, fin))},${Math.round(mix(255, 106, fin))})`;      // white, turning gold at 12/12
        const ein = u => e3(ramp(lt, ...u));
        const ck = qs(el, '.ct-k'), ku = ein([0.05, 0.3]);
        ck.style.opacity = ku.toFixed(3); ck.style.transform = `translate(${((1 - ku) * -26).toFixed(1)}px,0px)`;
        const cn = qs(el, '.ct-n'), cu = ein([0.12, 0.5]);
        cn.style.opacity = cu.toFixed(3);
        cn.style.transform = `translate(0px,${((1 - cu) * 70).toFixed(1)}px) scale(${(1 + 0.1 * pop).toFixed(3)})`;
        cn.style.textShadow = `0 0 ${(52 * pop).toFixed(1)}px rgba(232,206,150,${(0.85 * pop).toFixed(2)})`;
        qs(el, '#cn0').textContent = String(count).padStart(2, '0');
        qs(el, '#cn0').style.color = gold;
        qs(el, '.of').style.textShadow = `0 0 ${(60 * hump(ramp(lt, w12 - 0.1, w12 + 0.7))).toFixed(1)}px rgba(232,206,150,.9)`;
        const cw = qs(el, '.ct-w'), cwu = ein([0.22, 0.55]);
        cw.style.opacity = cwu.toFixed(3); cw.style.transform = `translate(0px,${((1 - cwu) * 40).toFixed(1)}px)`; cw.style.color = gold;
        qs(el, '.ct-p').style.opacity = ein([0.3, 0.6]).toFixed(3);
        [...qs(el, '.ct-p').children].forEach((p, i) => {
          const on = lt >= S[COUNTED[i][0]], u = on ? 1 - ramp(lt, S[COUNTED[i][0]], S[COUNTED[i][0]] + 0.3) : 0;
          p.style.background = on ? (i === 11 ? '#F3D9A0' : '#C9A76A') : 'rgba(255,255,255,.15)';
          p.style.transform = `scaleY(${(1 + 0.8 * u).toFixed(3)})`; p.style.boxShadow = on ? `0 0 ${(18 * u).toFixed(1)}px rgba(232,206,150,${(0.9 * u).toFixed(2)})` : 'none';
        });
        const cs = qs(el, '#cs');
        cs.textContent = lt >= S.drag ? 'Done · 21 parts · one slider' : count ? COUNTED[count - 1][1] : 'Select the parts that move';
        cs.style.opacity = (ein([0.4, 0.7])).toFixed(3);
        qs(el, '#ptag').style.opacity = (ramp(lt, S.pose - 0.12, S.pose + 0.04) * (1 - ramp(lt, S.rec - 0.25, S.rec - 0.05))).toFixed(3);

        // the panel: it slides in, its buttons light as they are pressed, the report line says what was done
        const op = qs(el, '#op'), pu = ein([0.1, 0.6]);
        op.style.opacity = pu.toFixed(3); op.style.transform = `translate(${((1 - pu) * 140).toFixed(1)}px,0)`;
        const on = lt >= S.new;
        qs(el, '#nm').classList.toggle('hot', pressed(lt, S.new));
        qs(el, '#nm').classList.toggle('dim', on && !pressed(lt, S.new));
        qs(el, '#mv').style.opacity = (0.35 + 0.65 * ramp(lt, S.new, S.new + 0.25)).toFixed(3);
        [['b', S.new], ['a', S.rec]].forEach(([k, t]) => {
          qs(el, '#ck' + k).style.opacity = lt >= t ? 1 : 0; qs(el, '#dt' + k).style.opacity = lt >= t ? 0 : 1;
        });
        qs(el, '#ra').classList.toggle('hot', pressed(lt, S.rec));
        [['#mc', S.chain], ['#rg', S.r1], ['#sp', S.sp]].forEach(([id, t]) => {
          qs(el, id).classList.toggle('dim', !on);
          qs(el, id).classList.toggle('hot', pressed(lt, t) || (id === '#rg' && (pressed(lt, S.r2) || pressed(lt, S.r3))));
        });
        qs(el, '#bs').classList.toggle('dim', lt < S.o4 + 0.2);
        qs(el, '#bs').classList.toggle('hot', pressed(lt, S.build));
        ['#ok1', '#ok2'].forEach(id => qs(el, id).classList.toggle('hot', ['o1', 'o2', 'o3', 'o4'].some(k => pressed(lt, S[k]) && (id === '#ok1') === (k !== 'o4'))));
        qs(el, '#slrow').style.opacity = ramp(lt, S.build, S.build + 0.25).toFixed(3);
        qs(el, '#sl .fill').style.width = `${(s * 100).toFixed(1)}%`; qs(el, '#sl .v').textContent = `${Math.round(s * 100)}%`;
        const parts = lt >= S.build ? 21 : lt >= S.o3 ? 21 : lt >= S.o2 ? 18 : lt >= S.o1 ? 13 : on ? 6 : 0;
        qs(el, '#cnt').textContent = lt >= S.build ? '21 parts · 1 slider' : on ? `${parts} parts` : '6 objects selected';
        qs(el, '#rep').textContent = REPORT[count];

        // the dialogs: open on their button, the field runs to its number while the cursor crosses it, close on OK
        const dlgAt = (a, b) => ramp(lt, a + 0.04, a + 0.13) * (1 - ramp(lt, b + 0.07, b + 0.15));
        const shows = [dlgAt(S.r1, S.o1), dlgAt(S.r2, S.o2), dlgAt(S.r3, S.o3)];
        const dR = qs(el, '#dR'), dS = qs(el, '#dS'), ru = Math.max(...shows), su = dlgAt(S.sp, S.o4);
        [[dR, ru], [dS, su]].forEach(([d, u]) => { d.style.opacity = u.toFixed(3); d.style.transform = `translate(0px,${((1 - u) * 18).toFixed(1)}px) scale(${(0.96 + 0.04 * u).toFixed(3)})`; });
        const r = lt >= S.r3 ? 2 : lt >= S.r2 ? 1 : 0, ta = [S.r1, S.r2, S.r3][r];
        const cnt = Math.round(kf(lt, [[ta + 0.1, [2, 8, 6][r]], [ta + 0.2, [8, 6, 2][r]]])), ls = Math.round(kf(lt, [[ta + 0.1, [0, 9, 14][r]], [ta + 0.2, [9, 14, 0][r]]]));
        qs(el, '#cn .fill').style.width = `${(cnt / 8 * 85).toFixed(1)}%`; qs(el, '#cn .v').textContent = String(cnt);
        qs(el, '#ls .fill').style.width = `${(ls / 14 * 85).toFixed(1)}%`; qs(el, '#ls .v').textContent = String(ls);
        const dd = kf(lt, [[S.sp + 0.1, 0.1], [S.sp + 0.2, 0.15]]);
        qs(el, '#ds .fill').style.width = `${(dd / 0.15 * 85).toFixed(1)}%`; qs(el, '#ds .v').textContent = dd.toFixed(2);

        // the timing bars fill at Spread's OK, then the playhead follows the slider
        const bw = ramp(lt, S.o4, S.o4 + 0.2);
        bars.forEach((b, i) => {
          if (i === bars.length - 1) { b.style.left = `${(s * 100).toFixed(2)}%`; b.style.opacity = (bw * ramp(lt, S.drag - 0.1, S.drag)).toFixed(3); return; }
          const w = M.parts[names[i]].window, u = ramp(lt, S.o4 + i * 0.012, S.o4 + 0.2 + i * 0.012), lit = lt >= S.drag && s >= w[0] && s <= w[1];
          b.style.opacity = u.toFixed(3); b.style.background = lit ? '#F3D9A0' : '#C9A76A';
          b.style.transform = `scaleX(${u.toFixed(3)})`; b.style.transformOrigin = 'left';
        });
      },
    };
  },
};

export default [open];
