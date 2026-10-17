// 0-13 s: the hook (the flower tangled in a rig; Bones. Constraints. Drivers. Keys.; a cube and its trail) and the logo over the Cycles bloom.
import { THREE, mkView, render, instFlower, fat, edgesOf, cube, ghost, GOLD, GOLD2 } from './stage3d.mjs';
import { clamp, mix, ramp, e3, io, hump, rng, bk } from './lib.mjs';
import { animText } from './ui.mjs';

const V3 = THREE.Vector3;
const lin = hex => { const c = new THREE.Color(hex); return [c.r, c.g, c.b]; };
const GL = lin(GOLD), GL2 = lin(GOLD2);

// ---- the rig: wireframe flower, bones, dashed constraint lines, driver curves, keyframe diamonds. rt = seconds from the film's start ----
function rigScene(ctx, slot) {
  const v = mkView({ w: 2560, h: 1440, fov: 26, pos: [0, 2.4, 8.4], look: [-1.0, 1.3, 0], slot, bloom: 0.6 });
  const flower = instFlower(ctx.F);
  flower.pose(0);
  // the surfaces draw nothing; only their creases and outlines, as thin gold lines (the stamens would only be a haze)
  const hide = new THREE.MeshBasicMaterial({ colorWrite: false, depthWrite: false });
  const outline = [];
  const meshes = [];
  flower.root.traverse(o => { if (o.isMesh) meshes.push(o); });      // collected first: the lines added below are meshes too
  meshes.forEach(o => {
    if (!/core/i.test(o.name)) { const e = edgesOf(v, o.geometry, { color: GOLD, w: 1.8, op: 0.75 }); o.add(e); outline.push(e); }
    o.material = hide; o.castShadow = false;
  });
  const wireMat = { set opacity(x) { outline.forEach(e => { e.material.opacity = x; }); } };
  const g = new THREE.Group(); g.add(flower.root); v.scene.add(g);
  const heart = new THREE.Mesh(new THREE.SphereGeometry(0.13, 24, 16), new THREE.MeshBasicMaterial({ color: new THREE.Color(2.6, 1.7, 0.7) }));
  heart.position.set(...ctx.F.motion.parts['Core'].rest.slice(0, 3)); g.add(heart);
  const R = rng(7);
  const P = ctx.F.motion.parts;
  const names = Object.keys(P).filter(n => P[n].moving);
  const pos = n => new V3(P[n].rest[0], P[n].rest[1], P[n].rest[2]);

  const octa = () => {                              // an octahedral bone, 1 long along +Y
    const w = 0.13, r = [[w, .14, 0], [0, .14, w], [-w, .14, 0], [0, .14, -w]], pts = [];
    r.forEach((p, i) => { const q = r[(i + 1) % 4]; pts.push([0, 0, 0], p, [0, 1, 0], p, p, q); });
    return pts;
  };
  const bones = names.map((n, i) => {
    const from = /Leaf/.test(n) ? new V3(0, 0.45, 0) : new V3(0, 1.0, 0);
    const to = pos(n), d = to.clone().sub(from), len = Math.max(0.25, d.length());
    const b = fat(v, octa(), { segments: true, color: GOLD2, w: 2.4, op: 0.95 });
    b.position.copy(from); b.quaternion.setFromUnitVectors(new V3(0, 1, 0), d.clone().normalize());
    g.add(b);
    return { b, len, t: 0.6 + i * 0.075 };
  });
  const spine = [[0, 0.3, 0.9, 0.5], [0, 0.95, 0.6, 0.62]].map(([x, y, l, t]) => {
    const b = fat(v, octa(), { segments: true, color: GOLD2, w: 2.8 });
    b.position.set(x, y - 0.65, 0); g.add(b); return { b, len: 0.7, t };
  });
  bones.push(...spine);

  // controller rings around the stem, and long dashed constraint lines from the parts out to them
  const rings = [[0.15, 1.7], [0.3, 0.55], [1.0, 0.9], [1.65, 1.3], [2.1, 1.0], [2.6, 0.6], [0.6, 2.1]].map(([y, r], i) => {
    const pts = [...Array(65)].map((_, j) => new V3(Math.cos(j / 64 * Math.PI * 2) * r, 0, Math.sin(j / 64 * Math.PI * 2) * r));
    const c = fat(v, pts, { color: GOLD, w: 2.4, op: 0.9 });
    c.position.y = y; c.rotation.x = (R() - 0.5) * 0.4; c.rotation.z = (R() - 0.5) * 0.4; g.add(c);
    return { c, r, y, t: 0.9 + i * 0.2 };
  });
  const onRing = () => { const o = rings[Math.floor(R() * rings.length)], a = R() * Math.PI * 2; return new V3(Math.cos(a) * o.r, o.y, Math.sin(a) * o.r); };
  const cons = [];
  for (let i = 0; i < 56; i++) {
    const a = i < 46 ? pos(names[Math.floor(R() * names.length)]) : onRing(), b = onRing();
    if (a.distanceTo(b) < 0.4) continue;
    const mid = a.clone().add(b).multiplyScalar(0.5).add(new V3((R() - 0.5) * 1.2, R() * 1.2 - 0.1, (R() - 0.5) * 1.2));
    const pts = new THREE.QuadraticBezierCurve3(a, mid, b).getPoints(46);
    const line = fat(v, pts, { dashed: true, dash: 0.07, gap: 0.06, w: 2.0, op: 0.85, color: GOLD2 });
    g.add(line);
    cons.push({ line, n: pts.length - 1, t: 1.3 + cons.length * 0.032 });
  }
  const drivers = [];
  for (let i = 0; i < 9; i++) {
    const pts = [...Array(56)].map((_, j) => { const x = j / 55; return new V3((x - 0.5) * 1.0, Math.sin(x * Math.PI * 2.4 + i) * 0.17 * (0.6 + x * 0.8), 0); });
    const c = fat(v, pts, { color: GOLD2, w: 2.6 });
    const a = R() * Math.PI * 2, rad = 1.7 + R() * 0.9;
    c.position.set(Math.cos(a) * rad, 0.4 + R() * 1.9, Math.sin(a) * rad); c.rotation.y = -a + Math.PI / 2;
    const rule = fat(v, [new V3(-0.5, -0.3, 0), new V3(0.5, -0.3, 0), new V3(0.5, 0.3, 0), new V3(-0.5, 0.3, 0), new V3(-0.5, -0.3, 0)], { color: GOLD, w: 1.6, op: 0.55 });
    c.add(rule); g.add(c);
    drivers.push({ c, t: 4.5 + i * 0.05 });
  }
  const keys = [];
  for (let i = 0; i < 30; i++) {
    const s = 0.075, d = fat(v, [[0, s, 0], [s, 0, 0], [0, -s, 0], [-s, 0, 0], [0, s, 0]], { color: GOLD2, w: 3.0 });
    const a = R() * Math.PI * 2, rad = 0.5 + R() * 2.0;
    d.position.set(Math.cos(a) * rad, 0.25 + R() * 2.3, Math.sin(a) * rad); d.rotation.y = -a;
    g.add(d); keys.push({ d, t: 5.15 + i * 0.012 });
  }
  const hot = (rt, t0) => hump(ramp(rt, t0, t0 + 0.7));          // a category flashes as its word is said

  return {
    v,
    pose(rt) {
      g.rotation.y = 0.35 + 0.1 * rt;
      rings.forEach(o => { const u = e3(ramp(rt, o.t, o.t + 0.7)); o.c.visible = u > 0; o.c.scale.setScalar(Math.max(1e-4, u)); });
      v.camera.position.set(0, 2.4 - 0.03 * rt, 8.4 - 0.1 * rt); v.camera.lookAt(-1.0, 1.3, 0);
      wireMat.opacity = 0.75 * ramp(rt, 0, 0.9);
      const fb = hot(rt, 3.25), fc = hot(rt, 3.81), fd = hot(rt, 4.5), fk = hot(rt, 5.15);
      bones.forEach(o => {
        const u = e3(ramp(rt, o.t, o.t + 0.55));
        o.b.visible = u > 0; o.b.scale.setScalar(Math.max(1e-4, o.len * u));
        const m = o.b.material; m.color.setRGB(mix(GL2[0], 2.6, fb), mix(GL2[1], 2.0, fb), mix(GL2[2], 1.1, fb));
      });
      cons.forEach(o => {
        const u = ramp(rt, o.t, o.t + 0.7);
        o.line.visible = u > 0; o.line.geometry.instanceCount = Math.max(0, Math.floor(o.n * u));
        o.line.material.dashOffset = -rt * 0.4;
        o.line.material.color.setRGB(mix(GL2[0], 2.6, fc), mix(GL2[1], 2.0, fc), mix(GL2[2], 1.1, fc));
      });
      drivers.forEach(o => {
        const u = e3(ramp(rt, o.t, o.t + 0.5));
        o.c.visible = u > 0; o.c.scale.set(u, u, 1);
        o.c.children.forEach(c => c.visible = u > 0.5);
        o.c.material.color.setRGB(mix(GL2[0], 2.6, fd), mix(GL2[1], 2.0, fd), mix(GL2[2], 1.1, fd));
      });
      keys.forEach(o => {
        const u = bk(ramp(rt, o.t, o.t + 0.35));
        o.d.visible = u > 0; o.d.scale.setScalar(Math.max(1e-4, u));
        o.d.material.color.setRGB(mix(GL2[0], 2.8, fk), mix(GL2[1], 2.2, fk), mix(GL2[2], 1.2, fk));
      });
    },
  };
}

const hookHTML = (head, top, extra = '') =>
  `<div class="full"></div><div class="shade"></div>
   <div class="kick" style="left:154px;top:${top - 62}px">RIGGING</div>
   <div class="big" style="top:${top}px">${head}</div>${extra}`;
const lines = s => s.split('\n').map(l => `<div class="ln"><span>${l.replace(/\*\*(.+?)\*\*/g, '<em>$1</em>')}</span></div>`).join('');

const hook1 = {
  id: 'hook1',
  make(ctx) {
    let rig;
    return {
      cues: [],
      build(el) {
        el.innerHTML = hookHTML(lines('Hours of\nbuilding **rigs**.'), 560);
        rig = rigScene(ctx, 0); rig.v.host = el.querySelector('.full');
      },
      update(lt, dur) { rig.pose(lt); render(rig.v); animText(this.el, lt, dur); },
    };
  },
};

const hook2 = {
  id: 'hook2',
  make(ctx, tb) {
    let rig;
    const words = ctx.T.lines.hook2.words.map(w => w.start - tb.start);
    return {
      cues: [],
      build(el) {
        el.innerHTML = hookHTML(lines('Bones.\nConstraints.\nDrivers.\n**Keys.**'), 430).replace('class="big"', 'class="big stack"');
        rig = rigScene(ctx, 1); rig.v.host = el.querySelector('.full');
      },
      update(lt, dur) {
        rig.pose(lt + 3); render(rig.v);
        const ex = 1 - ramp(lt, dur - 0.3, dur - 0.08);
        this.el.querySelector('.kick').style.opacity = 1;
        this.el.querySelectorAll('.ln').forEach((l, i) => {
          const u = ramp(lt, words[i] - 0.06, words[i] + 0.2);
          l.style.opacity = (clamp(u * 1.8) * ex).toFixed(3);
          l.style.transform = `translate(0px,${((1 - e3(u)) * 60).toFixed(1)}px)`;
        });
      },
    };
  },
};

const hook3 = {
  id: 'hook3',
  make(ctx) {
    let v, c, ghosts = [];
    const A = new V3(-1.9, 0.55, 0.5), B = new V3(3.0, 2.7, -0.4), N = 15;
    const path = e => new V3(mix(A.x, B.x, e), mix(A.y, B.y, e) + 1.5 * Math.sin(Math.PI * e), mix(A.z, B.z, e));
    const spin = (o, e) => o.rotation.set(e * Math.PI * 0.5, e * Math.PI * 1.0, e * Math.PI * 0.25);
    return {
      cues: [],
      build(el) {
        el.innerHTML = hookHTML(lines('What if you just\n**showed** it the move?'), 560).replace('RIGGING', 'WHAT IF');
        v = mkView({ w: 2560, h: 1440, fov: 28, pos: [-0.9, 3.0, 12.5], look: [-0.7, 1.4, 0], slot: 0, bloom: 0.45 });
        v.host = el.querySelector('.full');
        c = cube(v, [1.15, 1.15, 1.15]); v.scene.add(c);
        for (let j = 0; j < N; j++) {
          const gh = ghost(v, [1.15, 1.15, 1.15]); const e = (j + 1) / (N + 1);
          gh.position.copy(path(e)); spin(gh, e); gh.userData.e = e; v.scene.add(gh); ghosts.push(gh);
        }
      },
      update(lt, dur) {
        const e = io(ramp(lt, 0.85, 2.35));
        c.position.copy(path(e)); spin(c, e);
        ghosts.forEach(gh => {
          const on = e > gh.userData.e + 0.01, age = clamp(1 - (e - gh.userData.e) * 1.2);
          gh.visible = on;
          gh.material.opacity = 0.03 + 0.12 * age;
          gh.userData.edge.material.opacity = 0.3 + 0.6 * age; gh.userData.edge.material.transparent = true;
        });
        v.camera.position.x = -0.9 + 0.15 * lt; v.camera.lookAt(-0.7, 1.4, 0);
        render(v);
        animText(this.el, lt, dur);
      },
    };
  },
};

// ---- the logo, over the Cycles bloom (hook C), the flower pushed to the right so the name has room ----
const logo = {
  id: 'logo',
  make(ctx, tb) {
    const slider = ctx.T.lines.logo.words.find(w => /slider/i.test(w.w)).start - tb.start;
    const letters = 'COPYTHAT'.split('');
    return {
      cues: [],
      build(el) {
        const word = (w, top, gold) => `<div class="wm" style="position:absolute;left:146px;top:${top}px;font:800 212px/1 Inter;letter-spacing:-.035em;white-space:nowrap;${gold ? 'color:#C9A76A' : 'color:#fff'}">${
          w.split('').map(l => `<span style="display:inline-block">${l}</span>`).join('')}</div>`;
        el.innerHTML = `
          <div class="full" style="-webkit-mask-image:linear-gradient(90deg,transparent 0,#000 34%);mask-image:linear-gradient(90deg,transparent 0,#000 34%)">
            <img class="foot a" style="transform-origin:68% 62%"><img class="foot b" style="transform-origin:68% 62%"></div>
          <div class="shade"></div>
          <div class="kick" style="left:154px;top:342px">A Blender add-on</div>
          ${word('COPY', 390, false)}${word('THAT', 585, true)}
          <div class="rule" style="position:absolute;left:154px;top:826px;height:4px;background:#C9A76A;width:0"></div>
          <div class="tagl" style="position:absolute;left:154px;top:864px;font:500 60px/1.1 Inter;letter-spacing:-.01em;color:#F2EADB;white-space:nowrap">Record a move. Get a <em style="font-style:normal;color:#C9A76A">slider</em>.</div>`;
        this.a = el.querySelector('.foot.a'); this.b = el.querySelector('.foot.b');
      },
      update(lt, dur) {
        const el = this.el;
        // 46 frames of the bloom, slowed to 0.4x and held at the end; two images crossfade for smooth slow motion
        const f = clamp(lt - 0.1, 0, 3.7) * 30 * 0.4;
        const i0 = Math.min(45, Math.floor(f)), i1 = Math.min(45, i0 + 1);
        ctx.show(this.a, ctx.frameUrl('hookC', i0 + 1)); ctx.show(this.b, ctx.frameUrl('hookC', i1 + 1));
        this.b.style.opacity = (f - i0).toFixed(3); this.a.style.opacity = 1;
        const z = 1.0 + 0.045 * (lt / dur), tx = 400 - 20 * lt;
        [this.a, this.b].forEach(im => { im.style.transform = `translate(${tx.toFixed(1)}px,0px) scale(${z.toFixed(4)})`; });
        const ex = 1 - ramp(lt, dur - 0.3, dur - 0.08);
        const kk = el.querySelector('.kick'); const ku = ramp(lt, 0.1, 0.3); kk.style.opacity = ku * ex; kk.style.transform = `translate(${(1 - e3(ku)) * -26}px,0)`;
        el.querySelectorAll('.wm').forEach((w, r) => w.querySelectorAll('span').forEach((s, i) => {
          const t0 = (r ? 0.8 : 0.45) + i * 0.045, u = ramp(lt, t0, t0 + 0.42);
          s.style.opacity = (clamp(u * 2) * ex).toFixed(3);
          s.style.transform = `translate(0px,${((1 - bk(u)) * 120).toFixed(1)}px)`;
        }));
        const ru = e3(ramp(lt, 1.3, 1.9));
        el.querySelector('.rule').style.width = `${(ru * 260).toFixed(1)}px`; el.querySelector('.rule').style.opacity = ex;
        const tg = el.querySelector('.tagl'), tu = ramp(lt, 1.55, 1.95);
        tg.style.opacity = (tu * ex).toFixed(3); tg.style.transform = `translate(0px,${((1 - e3(tu)) * 28).toFixed(1)}px)`;
        el.querySelector('.tagl em').style.textShadow = `0 0 ${(40 * hump(ramp(lt, slider - 0.1, slider + 0.8))).toFixed(1)}px rgba(201,167,106,.9)`;
      },
    };
  },
};

export default [hook1, hook2, hook3, logo];
