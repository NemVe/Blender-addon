// 41.5-58 s, FEATURES 07-12: chain, curl, ring, mirror, combine, animate.
import { THREE, V3, pt, IN, feat, pr, drop, setFat, ball, stageXY, tagAt, cardView, render, toStage, cube, ghost, fat, std, goldMat, GOLD, GOLD2,
  row, btn, fld, lbl, cb, sec, note, I, qs, at, ramp, e3, kf, mix, io } from './kit.mjs';
import { animText, clickList, setOp, panel, dialog } from './ui.mjs';
import { clamp, bk, hump, pressed } from './lib.mjs';
import { instFlower } from './stage3d.mjs';
import { thumbAt } from './beats_idea.mjs';

// a finger of n blocks; angles are each joint's own bend, f says how much each joint follows the one before (0 none, 1 all the way)
function finger(v, n, L, base) {
  const grp = [], joints = [];
  for (let i = 0; i < n; i++) {
    const g = new THREE.Group(), c = cube(v, [L - 0.07, 0.56, 0.56]); c.position.x = L / 2; g.add(c); v.scene.add(g); grp.push(g);
    const j = new THREE.Mesh(new THREE.CylinderGeometry(0.1, 0.1, 0.86, 24), goldMat()); j.rotation.x = Math.PI / 2; j.castShadow = true; v.scene.add(j); joints.push(j);   // a hinge pin through the block
  }
  const link = fat(v, [...Array(n + 1)].map((_, i) => new V3(base.x + i * L, base.y, 0)), { color: GOLD2, w: 3.4, dashed: true, dash: 0.1, gap: 0.08 });
  v.scene.add(link);
  return {
    pose(angles, f) {
      let th = 0, p = base.clone();
      const pts = [];
      for (let i = 0; i < n; i++) {
        const rest = new V3(base.x + i * L, base.y, 0);
        const piv = i === 0 ? base.clone() : new V3().lerpVectors(rest, p, f);
        th = angles[i] + (i ? f * th : 0);
        grp[i].position.copy(piv); grp[i].rotation.z = th;
        joints[i].position.copy(piv); joints[i].visible = i === 0 || f > 0.02;
        pts.push(piv.clone().add(new V3(0, 0, 0.5)));      // the follow link runs in front of the blocks
        p = piv.clone().add(new V3(Math.cos(th), Math.sin(th), 0).multiplyScalar(L));
      }
      pts.push(p.clone().add(new V3(0, 0, 0.5)));
      setFat(link, pts); link.visible = f > 0.02;
    },
  };
}
const chainPanel = (count, hotId) => panel(sec('Chains', 'chain')
  + row(btn('Make Chain', { i: 'chain', id: 'mc' }) + btn('Curl', { i: 'curl', id: 'cu' })) + note('moves with the part it follows')
  + [...Array(count)].map((_, i) => row(`<div class="lbl" style="flex:0 0 250px"><span>Block ${i + 1}</span></div>${drop('', 'fw' + i)}`)).join(''));
const setFollows = (el, n, shown) => { for (let i = 1; i < n; i++) qs(el, `#fw${i} span`).textContent = shown(i) ? `Block ${i}` : ''; };

// ---- 07 chain ----
const f07 = {
  id: 'f07',
  make() {
    const ck = clickList([[0.95, 'Make Chain']]);
    const base = new V3(-1.8, 0.9, 0);
    let v, fg;
    return {
      cues: ck.cues,
      build(el) {
        feat(el, '07', 'Chain', 'Joints that\n**follow**.', 'Each part moves with the part it follows.', chainPanel(3), '<div class="tag g" id="tc">Moving alone</div>');
        v = cardView(this.index % 2, { pos: [0, 2.6, 10.6], look: [0, 1.7, 0] }); v.host = qs(el, '.cv');
        fg = finger(v, 3, 1.15, base);
      },
      measure(el) { this.cur = { keys: [{ t: 0.5, ...IN }, { t: 0.9, ...pt(at(qs(el, '#mc'))) }], clicks: ck.clicks, hold: 0.5 }; },
      update(lt, dur) {
        const el = this.el;
        animText(el, lt, dur);
        const f = io(ramp(lt, 0.95, 1.4));
        const u = [io(ramp(lt, 1.45, 2.4)), io(ramp(lt, 1.6, 2.5)), io(ramp(lt, 1.75, 2.6))];
        fg.pose([0.7 * io(ramp(lt, 0.25, 0.9)) + 0.2 * u[0], 0.8 * u[1], 0.8 * u[2]], f);
        setFollows(el, 3, i => lt >= 0.95 + 0.12 * (i - 1));
        qs(el, '#tc').textContent = lt >= 0.95 ? 'Chained' : 'Moving alone';
        qs(el, '#mc').classList.toggle('hot', pressed(lt, 0.95));
        render(v);
      },
    };
  },
};

// ---- 08 curl ----
const f08 = {
  id: 'f08',
  make() {
    const ck = clickList([[0.95, 'Curl']]);
    const base = new V3(-2.1, 0.9, 0), N = 4;
    let v, fg;
    return {
      cues: ck.cues,
      build(el) {
        feat(el, '08', 'Curl', '**Curl** it\nin one go.', "Repeat the first joint's bend down the chain.", chainPanel(N), '<div class="tag g">Curl</div>');
        v = cardView(this.index % 2, { pos: [0, 2.6, 9.2], look: [0, 1.5, 0] }); v.host = qs(el, '.cv');
        fg = finger(v, N, 1.05, base);
      },
      measure(el) {
        setFollows(el, N, i => true);
        this.cur = { keys: [{ t: 0.5, ...IN }, { t: 0.9, ...pt(at(qs(el, '#cu'))) }], clicks: ck.clicks, hold: 0.5 };
      },
      update(lt, dur) {
        const el = this.el;
        animText(el, lt, dur);
        const a0 = 0.62 * io(ramp(lt, 0.25, 0.85));
        fg.pose([a0, ...[1, 2, 3].map(i => a0 * io(ramp(lt, 1.0 + 0.1 * i, 1.7 + 0.1 * i)))], 1);
        qs(el, '#cu').classList.toggle('hot', pressed(lt, 0.95));
        render(v);
      },
    };
  },
};

// ---- 09 ring: one real petal becomes eight ----
const f09 = {
  id: 'f09',
  make(ctx) {
    const ck = clickList([[0.8, 1.15, 'Count'], [1.45, 'OK']]);
    const ang = ctx.F.motion.ring.outer_petals.angles_deg;
    const POPS = ['pop', 'pop_2', 'pop_3'];
    const cues = [...ck.cues, ...ang.slice(1).map((_, i) => ({ lt: 1.5 + 0.085 * i + 0.04, kind: 'pop', name: POPS[i % 3] }))];
    const Y = new V3(0, 1, 0);
    let v, root, leader, copies = [], pRest, qRest;
    return {
      cues,
      build(el) {
        feat(el, '09', 'Ring', 'One part,\na **ring**.', 'Copies ride along with their leader.',
          dialog('Ring', pr('Use', btn('Make copies', { c: 'on' }) + btn("Use what's there")) + pr('Count', fld('', '2', 0.1, { id: 'cn', c: 'c' }))
            + pr('Round', drop('3D Cursor')) + pr('About', drop('World Z'))
            + pr('', `<div style="display:flex;align-items:center;gap:12px">${cb(true)}<span>Linked copies</span></div>`), { okId: 'ok' }),
          '<div class="tag g" id="tr">1 part</div>');
        v = cardView(this.index % 2, { pos: [0, 3.8, 5.4], look: [0, 1.7, 0], fov: 30, env: 0.65 }); v.host = qs(el, '.cv');
        const FL = instFlower(ctx.F); FL.pose(0);
        FL.names.forEach(n => { if (n !== 'Outer Leader') FL.parts[n].visible = false; });
        root = FL.root; leader = FL.parts['Outer Leader'];
        pRest = leader.position.clone(); qRest = leader.quaternion.clone();
        ang.slice(1).forEach(() => { const c = leader.clone(true); root.add(c); copies.push(c); });
        v.scene.add(root);
      },
      measure(el) {
        const f = fx => pt(at(qs(el, '#cn'), fx, 0.5));
        this.cur = { keys: [{ t: 0.4, ...IN }, { t: 0.72, ...f(0.12) }, { t: 0.8, ...f(0.12) }, { t: 1.15, ...f(0.8), lin: true }, { t: 1.4, ...pt(at(qs(el, '#ok'))) }], clicks: ck.clicks, hold: 0.25 };
      },
      update(lt, dur) {
        const el = this.el;
        animText(el, lt, dur);
        const c = Math.round(kf(lt, [[0.8, 2], [1.15, 8]]));
        qs(el, '#cn .fill').style.width = `${(c / 8 * 80).toFixed(1)}%`; qs(el, '#cn .v').textContent = String(c);
        qs(el, '#ok').classList.toggle('hot', pressed(lt, 1.45));
        copies.forEach((m, i) => {
          const u = ramp(lt, 1.5 + 0.085 * i, 1.9 + 0.085 * i), a = ang[i + 1] * Math.PI / 180 * e3(u);
          m.visible = u > 0; m.scale.setScalar(Math.max(1e-3, bk(u)));
          m.position.copy(pRest).applyAxisAngle(Y, a); m.quaternion.setFromAxisAngle(Y, a).multiply(qRest);
        });
        const n = 1 + copies.filter((_, i) => lt >= 1.5 + 0.085 * i).length;
        qs(el, '#tr').textContent = n === 1 ? '1 part' : `${n} parts · 1 leader`;
        root.rotation.y = 0.55 * lt;
        const g = ramp(lt, 1.62, 1.85);
        qs(el, '.dlg').style.opacity = (1 - 0.7 * g).toFixed(3);
        render(v);
      },
    };
  },
};

// ---- 10 mirror: two doors, the second one mirrored ----
const f10 = {
  id: 'f10',
  make() {
    const ck = clickList([[0.95, 'Mirror X']]);
    const TH = lt => kf(lt, [[0.25, 0], [0.85, 1.25], [0.95, 1.25], [1.2, 0], [1.35, 0], [2.1, 1.25]]);
    let v, dl, dr;
    return {
      cues: ck.cues,
      build(el) {
        feat(el, '10', 'Mirror', 'Copies that\n**mirror**.', "Mirror a copy's move across X, Y or Z.",
          panel(sec('Copies', 'ring') + row('<div class="lbl"><span>Riding along (1)</span></div>') + note('lead: below 0 behind, above 0 ahead')
            + row(`<div class="lbl" style="flex:1.1"><span>…Leader 2</span></div>${fld('Lead', '0', 0.5, { c: '', id: 'ld' })}${btn('-', { i: 'mirror', id: 'mr' })}<div class="x">×</div>`)),
          '<div class="tag g">Leader</div><div class="tag g r" id="tm">Copy · not mirrored</div>');
        v = cardView(this.index % 2, { pos: [0, 3.4, 9.6], look: [0, 1.1, 0] }); v.host = qs(el, '.cv');
        const grp = new THREE.Group(); grp.rotation.y = -0.5; v.scene.add(grp);
        const back = cube(v, [3.0, 2.2, 0.3], { color: 0x2f2f35, rough: 0.5, metal: 0.3 }); back.position.set(0, 1.1, -0.2);
        const mk = side => {
          const pivot = new THREE.Group(); pivot.position.set(side * 1.5, 1.1, 0.1);
          const d = cube(v, [1.42, 2.0, 0.1]); d.position.x = -side * 0.72; pivot.add(d); grp.add(pivot); return pivot;
        };
        dl = mk(-1); dr = mk(1);
        grp.add(back);
      },
      measure(el) { this.cur = { keys: [{ t: 0.5, ...IN }, { t: 0.9, ...pt(at(qs(el, '#mr'))) }], clicks: ck.clicks, hold: 0.5 }; },
      update(lt, dur) {
        const el = this.el;
        animText(el, lt, dur);
        const th = TH(lt), m = lt >= 0.95;
        dl.rotation.y = -th; dr.rotation.y = m ? th : -th;
        const b = qs(el, '#mr'); b.classList.toggle('on', m); b.classList.toggle('hot', pressed(lt, 0.95)); qs(el, '#mr span').textContent = m ? 'X' : '-';
        qs(el, '#tm').textContent = m ? 'Copy · mirrored X' : 'Copy · not mirrored';
        render(v);
      },
    };
  },
};

// ---- 11 combine: a door and a drawer under one slider ----
const f11 = {
  id: 'f11',
  make() {
    const ck = clickList([[0.95, 'Combine'], [1.5, 2.5, 'drag the combined slider']]);
    const S = lt => kf(lt, [[1.5, 0], [2.5, 1]]);
    let v, door, drawer;
    return {
      cues: ck.cues,
      build(el) {
        const keyB = '<div class="btn sm"><i class="key"></i></div>';
        feat(el, '11', 'Combine', 'Many moves,\n**one control**.', 'Play several moves from one slider.',
          panel(`<div style="position:relative;height:330px">
            <div id="cA" style="position:absolute;left:0;right:0;top:0">${row(fld('Move 1', '0%', 0, { c: 'w3' }) + keyB)}${row(fld('Move 2', '0%', 0, { c: 'w3' }) + keyB)}
              ${row(btn('New Move', { i: 'new_move' }) + btn('Combine', { i: 'combine', id: 'cmb' }))}</div>
            <div id="cB" class="box" style="position:absolute;left:0;right:0;top:0;opacity:0"><div class="sec" style="margin:0">${I('combine')}<b style="font-weight:600;text-transform:none;font-size:25px">Combined</b></div>
              ${row(fld('Combined', '0%', 0, { id: 'cs', c: 'w3' }) + keyB)}${note('plays these, each after its own delay')}
              ${row('<div class="lbl" style="flex:1.2"><span>Move 1</span></div>' + fld('', '0.00', 0, { c: 'c' }))}${row('<div class="lbl" style="flex:1.2"><span>Move 2</span></div>' + fld('', '0.30', 0.3, { c: 'c' }))}</div></div>`),
          '<div class="tag g">Door</div><div class="tag g r">Drawer</div>');
        v = cardView(this.index % 2, { pos: [0.8, 3.0, 8.6], look: [0, 0.9, 0.2] }); v.host = qs(el, '.cv');
        const slab = cube(v, [4.2, 0.3, 2.4], { color: 0x35353b, rough: 0.5, metal: 0.3 }); slab.position.set(0, 0.15, 0);
        const piv = new THREE.Group(); piv.position.set(-1.8, 1.25, 0.5); door = piv;
        const d = cube(v, [1.5, 1.8, 0.1]); d.position.x = 0.75; piv.add(d);
        drawer = cube(v, [1.5, 0.6, 1.4]); drawer.userData.home = new V3(1.1, 0.6, 0.2); drawer.position.copy(drawer.userData.home);
        const shell = cube(v, [1.7, 0.2, 1.6], { color: 0x2c2c31, rough: 0.55, metal: 0.3, shadow: false }); shell.position.set(1.1, 0.4, 0.2);
        v.scene.add(slab, piv, drawer, shell);
      },
      measure(el) {
        const xy = thumbAt(el, '#cs');
        const keys = [{ t: 0.5, ...IN }, { t: 0.9, ...pt(at(qs(el, '#cmb'))) }, { t: 1.45, ...xy(0) }];
        for (let t = 1.5; t <= 2.501; t += 0.1) keys.push({ t, ...xy(S(t)), lin: true });
        this.cur = { keys, clicks: ck.clicks, hold: 0.25 };
      },
      update(lt, dur) {
        const el = this.el;
        animText(el, lt, dur);
        const s = S(lt), m = ramp(lt, 1.0, 1.3);
        qs(el, '#cA').style.opacity = (1 - ramp(lt, 1.0, 1.15)).toFixed(3); qs(el, '#cB').style.opacity = ramp(lt, 1.15, 1.35).toFixed(3);
        qs(el, '#cB').style.transform = `translate(0px,${((1 - e3(m)) * 24).toFixed(1)}px)`;
        qs(el, '#cs .fill').style.width = `${(s * 100).toFixed(1)}%`; qs(el, '#cs .v').textContent = `${Math.round(s * 100)}%`;
        qs(el, '#cmb').classList.toggle('hot', pressed(lt, 0.95));
        door.rotation.y = -1.7 * io(ramp(s, 0, 0.7));
        drawer.position.z = drawer.userData.home.z + 1.3 * io(ramp(s, 0.3, 1.0));
        render(v);
      },
    };
  },
};

// ---- 12 animate: keys appear on a timeline and it plays ----
const f12 = {
  id: 'f12',
  make() {
    const ck = clickList([[0.95, 'Animate']]);
    const BAR = [1.5, 0.62, 0.62], A = new V3(-1.5, 0.31, 0.3), B = new V3(1.5, 1.7, 0.3);
    const P = e => new V3(mix(A.x, B.x, e), mix(A.y, B.y, e) + 0.5 * Math.sin(Math.PI * e), mix(A.z, B.z, e));
    const W = 1331 - 120, fx = f => 60 + f / 60 * W;
    let v, blk;
    return {
      cues: ck.cues,
      build(el) {
        feat(el, '12', 'Animate', 'Keyed in\n**one click**.', 'Keys the whole move from the current frame.',
          panel(sec('Animate', 'animate') + row(fld('Frames', '48', 0, { c: 'w2' }) + btn('Animate', { i: 'animate', id: 'an', c: 'w2' }))),
          `<div class="tag g">Timeline</div><div class="tl"><div class="ruler">${[0, 10, 20, 30, 40, 50, 60].map(f => `<i class="tk" style="left:${fx(f)}px"><b>${f}</b></i>`).join('')}</div>
            <div class="lane"><i class="dm" id="k0" style="left:${fx(1)}px"></i><i class="dm" id="k1" style="left:${fx(49)}px"></i></div>
            <div class="ph" id="ph" style="left:${fx(1)}px"><b id="phn">1</b></div></div>`);
        v = cardView(this.index % 2, { pos: [0, 2.5, 9.4], look: [0, 0.6, 0] }); v.host = qs(el, '.cv');
        blk = cube(v, BAR);
        const gA = ghost(v, BAR), gB = ghost(v, BAR); gA.position.copy(P(0)); gB.position.copy(P(1)); gB.rotation.z = Math.PI / 2;
        v.scene.add(blk, gA, gB);
      },
      measure(el) { this.cur = { keys: [{ t: 0.5, ...IN }, { t: 0.9, ...pt(at(qs(el, '#an'))) }], clicks: ck.clicks, hold: 0.5 }; },
      update(lt, dur) {
        const el = this.el;
        animText(el, lt, dur);
        const play = ramp(lt, 1.55, 2.6), fr = 1 + 48 * play, e = io(play);
        blk.position.copy(P(e)); blk.rotation.z = e * Math.PI / 2;
        qs(el, '#ph').style.left = `${fx(fr)}px`; qs(el, '#phn').textContent = String(Math.round(fr));
        [['k0', 1.0], ['k1', 1.15]].forEach(([id, t]) => { const u = bk(ramp(lt, t, t + 0.3)); const k = qs(el, '#' + id); k.style.opacity = clamp(u * 3); k.style.transform = `rotate(45deg) scale(${(0.72 * Math.max(0, u)).toFixed(3)})`; });
        qs(el, '#an').classList.toggle('hot', pressed(lt, 0.95));
        render(v);
      },
    };
  },
};

export default [f07, f08, f09, f10, f11, f12];
