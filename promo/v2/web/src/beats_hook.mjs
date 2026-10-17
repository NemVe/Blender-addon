// 9-13 s: the logo over the Cycles bloom. (The opening that comes before it is beats_walk.mjs; v2.1's three hooks and v2.2's opening, beats_open.mjs, are in git history.)
import { clamp, ramp, e3, hump, bk } from './lib.mjs';

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

export default [logo];
