// 58-76 s: put it together (the real flower: ring, chain, spread, one slider, then the Cycles render), the real Blender, the end card.
import { THREE, mkView, render, instFlower, GOLD } from './stage3d.mjs';
import { clamp, mix, ramp, e3, io, kf, bk, hump, pressed } from './lib.mjs';
import { animText, at, panel, col, card, row, btn, fld, sec, I, clickList, qs, setOp, kick } from './ui.mjs';
import { thumbAt, sliderRow } from './beats_idea.mjs';

const pt = ([x, y]) => ({ x, y });
const IN = { x: 990, y: 1120 };
const Y = new THREE.Vector3(0, 1, 0);
// the exported camera is Blender's: its forward is the object's local -Y, so turn it a quarter about X to be a Three.js camera
const QX = new THREE.Quaternion(-Math.SQRT1_2, 0, 0, Math.SQRT1_2);

// ---- put it together ----
const together = {
  id: 'together',
  make(ctx) {
    const M = ctx.F.motion;
    const S = lt => kf(lt, [[3.8, 0], [6.2, 1]]);
    const names = Object.keys(M.motion);                       // the 21 moving parts
    const grp = n => M.parts[n].group;
    // when each part joins in, and what turns it in (a ring turns the leader, the second leaf is a copy of the first turned 180)
    const join = {};
    M.groups.outer_petals.forEach((n, i) => { join[n] = i === 0 ? 0.3 : 0.85 + (i - 1) * 0.09; });
    M.groups.inner_petals.forEach((n, i) => { join[n] = i === 0 ? 1.5 : 1.7 + (i - 1) * 0.09; });
    join[M.groups.core[0]] = 1.45;
    M.groups.leaf_a.forEach((n, i) => { join[n] = 2.2 + i * 0.15; });
    M.groups.leaf_b.forEach((n, i) => { join[n] = 2.75 + i * 0.1; });
    const popNames = ['pop', 'pop_2', 'pop_3'];
    const popCues = names.filter(n => join[n] > 0.7 && /Petal|Leader|Leaf/.test(n) || /Leader/.test(n)).filter(n => join[n] > 0.3)
      .map((n, i) => ({ lt: join[n] + 0.04, kind: 'pop', name: popNames[i % 3] }));
    const ck = clickList([[3.8, 6.2, 'drag the slider']]);
    const rest = {}, qrest = {};
    let v, FL, cv, cardEl, bars = [], cams, foot = {};
    const ringAngle = n => (M.parts[n].ring_angle_deg || 0) * Math.PI / 180;
    const leaderOf = n => {
      const g = M.groups[grp(n)];
      return g ? g[0] : n;
    };
    return {
      cues: [...ck.cues, ...popCues],
      build(el) {
        const rows = [['Parts & Pivot', 'pivot'], ['Path', 'curve'], ['Timing', 'timing'], ['Copies', 'ring'], ['Chains', 'chain'], ['Animate', 'animate']]
          .map(([t, i]) => sec(t, i, { open: false })).join('');
        el.innerHTML = col('Put it together', '21 parts.\n**One slider.**', 'Ring, chain, spread: then one slider blooms it all.',
          panel(row('<div class="lbl"><span>CopyThat Rig</span></div><div class="lbl mute" style="justify-content:flex-end"><span id="cnt">0 parts · 1 slider</span></div>') + sliderRow() + rows))
          + card('<div class="tag g" id="tp">1 part</div><div class="tag g r" id="ts">Ring</div>'
            + `<div id="bars" style="position:absolute;left:70px;right:70px;bottom:46px;height:${names.length * 6}px">${names.map((n, i) => {
              const [a, b] = M.parts[n].window; return `<i style="position:absolute;left:${(a * 100).toFixed(2)}%;width:${((b - a) * 100).toFixed(2)}%;top:${i * 6}px;height:4px;border-radius:2px;background:#C9A76A"></i>`;
            }).join('')}<i id="bph" style="position:absolute;top:-14px;bottom:-14px;width:3px;background:#fff;left:0"></i></div>`)
          + '<div class="full" id="cyc" style="display:block"><img class="foot a"><img class="foot b"></div><div class="tag g" id="rc" style="left:154px;top:auto;bottom:120px;font-size:30px;padding:18px 26px 16px">Rendered in Cycles</div>';
        cardEl = qs(el, '.card'); cv = qs(el, '.cv');
        bars = [...qs(el, '#bars').querySelectorAll('i')];
        v = mkView({ w: 1331, h: 1140, fov: M.camera.fov_y_deg, pos: [0, 2, 13], look: [0, 1, 0], slot: 1, bloom: 0.14, env: 0.65 });
        v.camera.aspect = 2560 / 1440;
        v.host = cv;
        FL = instFlower(ctx.F); FL.coreScale = 0.5; FL.pose(0);
        v.scene.add(FL.root);
        names.forEach(n => { rest[n] = FL.parts[n].position.clone(); qrest[n] = FL.parts[n].quaternion.clone(); });
        foot.a = qs(el, '#cyc .a'); foot.b = qs(el, '#cyc .b');
      },
      measure(el) {
        const xy = thumbAt(el, '#sl');
        const keys = [{ t: 3.2, ...IN }, { t: 3.7, ...xy(0) }];
        for (let t = 3.8; t <= 6.201; t += 0.1) keys.push({ t, ...xy(S(t)), lin: true });
        this.cur = { keys, clicks: ck.clicks, hold: 0.3 };
      },
      update(lt, dur) {
        const el = this.el;
        animText(el, lt, dur);
        const s = S(lt), f = s * 150;
        // the parts: at rest while they are being made, the real motion once the slider moves
        let count = 0;
        names.forEach(n => {
          const node = FL.parts[n], u = ramp(lt, join[n], join[n] + 0.45);
          node.visible = u > 0;
          if (u > 0) count++;
        });
        FL.pose(f);
        if (lt < 3.8) names.forEach(n => {
          const node = FL.parts[n], u = ramp(lt, join[n], join[n] + 0.45), L = leaderOf(n);
          let a = 0, p = rest[n], q = qrest[n];
          if (grp(n) === 'leaf_b') { a = Math.PI * e3(u); p = rest[M.groups.leaf_a[M.groups.leaf_b.indexOf(n)]].clone(); q = qrest[M.groups.leaf_a[M.groups.leaf_b.indexOf(n)]]; }
          else if (L !== n) { a = ringAngle(n) * e3(u); p = rest[L]; q = qrest[L]; }
          if (a) { node.position.copy(p).applyAxisAngle(Y, a); node.quaternion.setFromAxisAngle(Y, a).multiply(q); }
          node.scale.setScalar(Math.max(1e-3, bk(u)));
        });
            // the camera of the Cycles render, so the dissolve at the end lines up with it
        const cf = M.camera.frames[Math.round(clamp(f, 0, 150))];
        v.camera.position.set(cf[0], cf[1], cf[2]); v.camera.quaternion.set(cf[3], cf[4], cf[5], cf[6]).multiply(QX);
        qs(el, '#tp').textContent = count ? `${count} part${count > 1 ? 's' : ''}` : 'Start';
        const step = lt < 1.45 ? 'Ring · outer petals' : lt < 2.2 ? 'Ring · inner petals' : lt < 2.9 ? 'Chain · the leaf' : lt < 3.75 ? 'Spread · the timing' : 'One slider';
        qs(el, '#ts').textContent = step;
        qs(el, '#cnt').textContent = `${count} parts · 1 slider`;
        qs(el, '#sl .fill').style.width = `${(s * 100).toFixed(1)}%`; qs(el, '#sl .v').textContent = `${Math.round(s * 100)}%`;
        // the timing bars (each part's window on the slider), then the playhead
        const bw = ramp(lt, 2.9, 3.6) * (1 - ramp(lt, 6.3, 6.6));
        bars.forEach((b, i) => {
          if (i === bars.length - 1) { b.style.left = `${(s * 100).toFixed(2)}%`; b.style.opacity = bw; return; }
          const w = M.parts[names[i]].window, u = ramp(lt, 2.9 + i * 0.03, 3.1 + i * 0.03), on = s >= w[0] && s <= w[1];
          b.style.opacity = (u * (1 - ramp(lt, 6.3, 6.6))).toFixed(3); b.style.background = on ? '#F3D9A0' : '#C9A76A';
          b.style.transform = `scaleX(${u.toFixed(3)})`; b.style.transformOrigin = 'left';
        });
        // the card grows to fill the frame, then the Cycles render dissolves in over it
        const g = io(ramp(lt, 6.55, 7.45));
        const w = mix(1331, 2560, g), h = mix(1140, 1440, g);
        Object.assign(cardEl.style, { left: `${mix(1075, 0, g)}px`, top: `${mix(150, 0, g)}px`, width: `${w}px`, height: `${h}px`, borderRadius: `${mix(18, 0, g)}px` });
        v.w = Math.round(w); v.h = Math.round(h);
        v.camera.zoom = mix(0.8, 1, g);                 // a little wider while it is a card, the exact Cycles camera once it fills the frame
        v.camera.setViewOffset(2560, 1440, (2560 - v.w) / 2, (1440 - v.h) / 2, v.w, v.h);
        qs(el, '.col').style.opacity = (1 - ramp(lt, 6.3, 6.75)).toFixed(3);
        const fo = clamp((lt - 7.2) * 30 + 150, 140, 209), i0 = Math.floor(fo), i1 = Math.min(209, i0 + 1);
        ctx.show(foot.a, ctx.frameUrl('outro', i0 + 1)); ctx.show(foot.b, ctx.frameUrl('outro', i1 + 1));
        foot.b.style.opacity = (fo - i0).toFixed(3);
        const fade = ramp(lt, 7.3, 8.1);
        qs(el, '#cyc').style.opacity = fade.toFixed(3); qs(el, '#cyc').style.display = fade > 0 ? 'block' : 'none';
        const rc = qs(el, '#rc'); rc.style.opacity = (ramp(lt, 7.9, 8.3) * (1 - ramp(lt, dur - 0.3, dur - 0.08))).toFixed(3);
        render(v);
      },
    };
  },
};

// ---- the real recording, with the cursor dragging the real slider (magnified in a lens, so it can be read) ----
const real = {
  id: 'real',
  make(ctx) {
    const R = ctx.real, V = R.values, [T0, T1] = R.track, RY = R.row_y;
    const CX = 640, CY = 70, SC = 1331 / 1500;                    // the card shows this part of the 2560x1440 take
    const LX = 1535, LY = 226, LZ = 1.9, LW = 960, LH = 190;       // the lens: the slider row, 1.9 times larger
    const lens0 = { x: 1075 + 48 + 2, y: 150 + (1140 - 48 - LH) + 2 };
    const frameAt = lt => clamp((lt - 0.12) * 42, 0, V.length - 1);
    const valAt = lt => { const f = frameAt(lt), i = Math.floor(f); return mix(V[i], V[Math.min(V.length - 1, i + 1)], f - i); };
    const st = (x, y) => ({ x: lens0.x + (x - LX) * LZ, y: lens0.y + (y - LY) * LZ });
    const ck = clickList([[0.5, 2.4, 'drag the real slider']]);
    let imgs;
    return {
      cues: ck.cues,
      build(el) {
        const img = `<img style="position:absolute;left:0;top:0;width:2560px;height:1440px;transform-origin:0 0;`;
        el.innerHTML = col('Real Blender', 'Right in the\n**sidebar**.', 'The real panel, recorded in Blender 5.', '')
          + card('<div class="tag g">Real Blender</div><div class="tag r" id="rv">Move 1 · 0%</div>'
            + `<div class="lens" style="position:absolute;left:48px;bottom:48px;width:${LW}px;height:${LH}px;box-sizing:border-box;border:2px solid #C9A76A;border-radius:16px;overflow:hidden;background:#222;box-shadow:0 24px 70px rgba(0,0,0,.65)">
                ${img}transform:scale(${LZ}) translate(${-LX}px,${-LY}px)"></div></div>`);
        const cv = qs(el, '.cv');
        const main = document.createElement('img');
        main.style.cssText = `position:absolute;left:0;top:0;width:2560px;height:1440px;transform-origin:0 0;transform:scale(${SC}) translate(${-CX}px,${-CY}px)`;
        cv.appendChild(main);
        imgs = [main, qs(el, '.lens img')];
      },
      measure() {
        const keys = [{ t: 0.1, x: lens0.x + 120, y: lens0.y + LH + 90 }, { t: 0.42, ...st(T0 + 6, RY) }];
        for (let t = 0.5; t <= 2.401; t += 0.05) keys.push({ t, ...st(T0 + valAt(t) * (T1 - T0), RY), lin: true });
        this.cur = { keys, clicks: ck.clicks, hold: 0.25 };
      },
      update(lt, dur) {
        const el = this.el;
        animText(el, lt, dur);
        const url = ctx.frameUrl('real', Math.round(frameAt(lt)) + 1);
        imgs.forEach(im => ctx.show(im, url));
        qs(el, '#rv').textContent = `Move 1 · ${Math.round(valAt(lt) * 100)}%`;
        setOp(qs(el, '.lens'), e3(ramp(lt, 0.1, 0.5)), 30);
      },
    };
  },
};

// ---- the end card ----
const end = {
  id: 'end',
  make(ctx, tb) {
    return {
      cues: [],
      build(el) {
        const word = (w, gold) => w.split('').map(l => `<span style="display:inline-block;${gold ? 'color:#C9A76A' : ''}">${l}</span>`).join('');
        el.innerHTML = `
          <div class="full" style="filter:blur(10px) brightness(.5)"><img class="foot a" style="transform-origin:50% 60%"></div>
          <div class="shade" style="background:radial-gradient(ellipse at 50% 50%,rgba(10,10,12,.35) 0,rgba(10,10,12,.85) 100%)"></div>
          <div style="position:absolute;left:0;top:0;width:2560px;text-align:center">
            <div class="wm" style="margin-top:360px;font:800 250px/1 Inter;letter-spacing:-.035em;color:#fff;white-space:nowrap">${word('COPY', false)}${word('THAT', true)}</div>
            <div class="tagl" style="margin-top:34px;font:500 64px/1.1 Inter;letter-spacing:-.01em;color:#F2EADB">Record a move. Get a <em style="font-style:normal;color:#C9A76A">slider</em>.</div>
            <div class="pill" style="display:inline-block;margin-top:86px;padding:26px 66px 24px;border-radius:999px;background:#C9A76A;color:#0B0B0E;font:800 46px/1 Inter;letter-spacing:-.01em;position:relative;overflow:hidden">Now on Superhive<i class="shine" style="position:absolute;top:0;bottom:0;width:90px;left:-120px;background:linear-gradient(100deg,transparent,rgba(255,255,255,.65),transparent);transform:skewX(-20deg)"></i></div>
            <div class="by" style="margin-top:58px;font:500 32px/1 Inter;letter-spacing:.04em;color:#9A968E">by NemVe3D · creators.sa/nemve</div>
          </div>
          <div id="blk" style="position:absolute;left:0;top:0;width:2560px;height:1440px;background:#000;opacity:0"></div>`;
        this.a = qs(el, '.foot.a');
      },
      update(lt, dur) {
        const el = this.el;
        ctx.show(this.a, ctx.frameUrl('outro', 210));
        this.a.style.transform = `scale(${(1.04 + 0.05 * lt / dur).toFixed(4)})`;
        el.querySelectorAll('.wm span').forEach((s, i) => {
          const t0 = 0.35 + i * 0.045, u = ramp(lt, t0, t0 + 0.45);
          s.style.opacity = clamp(u * 2).toFixed(3); s.style.transform = `translate(0px,${((1 - bk(u)) * 130).toFixed(1)}px)`;
        });
        const tg = qs(el, '.tagl'), tu = ramp(lt, 1.1, 1.5); setOp(tg, tu, 26);
        const pl = qs(el, '.pill'), pu = bk(ramp(lt, 1.7, 2.1)); pl.style.opacity = clamp(pu * 3).toFixed(3); pl.style.transform = `scale(${(0.7 + 0.3 * pu).toFixed(3)})`;
        qs(el, '.shine').style.left = `${mix(-120, 560, ramp(lt, 2.3, 2.9)).toFixed(1)}px`;
        setOp(qs(el, '.by'), ramp(lt, 2.4, 2.8), 14);
        qs(el, '#blk').style.opacity = ramp(lt, dur - 0.6, dur - 0.05).toFixed(3);
      },
    };
  },
};

export default [together, real, end];
