// Shared bits of the feature beats: the cursor's way in, a panel row of every kind, and small scene parts.
import { THREE, cardView, render, toStage, cube, ghost, fat, std, goldMat, GOLD, GOLD2 } from './stage3d.mjs';
import { ramp, e3, kf, mix, io } from './lib.mjs';
import { col, card, kick, row, btn, fld, lbl, cb, sec, note, I, qs, at } from './ui.mjs';

export { THREE, cardView, render, toStage, cube, ghost, fat, std, goldMat, GOLD, GOLD2 };
export const V3 = THREE.Vector3;
export const pt = ([x, y]) => ({ x, y });
export const IN = { x: 990, y: 1120 };                  // where the cursor comes in from (below the panel)
export const dim = (el, sel, on) => { qs(el, sel).classList.toggle('on', on); };

// the standard beat: kicker, headline, subline, mini UI on the left; the card on the right
export function feat(el, n, label, head, sub, mini, cardInner = '') {
  el.innerHTML = col(kick(n, label), head, sub, mini) + card(cardInner);
}
// one part row of the Timing list: a square, the name, the delay field
export const drow = (name, val, fill, id) => row(`<div class="lbl" style="flex:0 0 330px">${cb(false)}<span>${name}</span></div>${fld('', val, fill, { id, c: 'c' })}`);
export const drop = (text, id) => `<div class="fld" ${id ? `id="${id}"` : ''}><span>${text}</span><i class="chev"></i></div>`;
// a row of a dialog: label on the left, the control on the right
export const pr = (label, inner, id) => `<div class="pr"${id ? ` id="${id}"` : ''}><div class="l">${label}</div><div class="f">${inner}</div></div>`;

// ---- scene parts ----
export function setFat(line, pts) { line.geometry.setPositions(pts.flatMap(p => [p.x, p.y, p.z])); line.computeLineDistances && line.material.dashed && line.computeLineDistances(); }
export function ball(r = 0.38) { const m = new THREE.Mesh(new THREE.SphereGeometry(r, 48, 32), goldMat()); m.castShadow = true; return m; }
export function coin(r = 0.34) {                       // a disc facing the camera; spin it with rotation.z
  const g = new THREE.CylinderGeometry(r, r, 0.1, 64); g.rotateX(Math.PI / 2);
  const m = new THREE.Mesh(g, goldMat()); m.castShadow = true;
  const rim = new THREE.Mesh(new THREE.TorusGeometry(r * 0.78, 0.014, 8, 64), std(GOLD2, 0.3, 1)); rim.position.z = 0.052; m.add(rim);
  return m;
}
// a 3D cursor: a red and white ring with four ticks, facing the camera
export function cursor3d(v) {
  const g = new THREE.Group();
  const ring = [...Array(49)].map((_, i) => [Math.cos(i / 48 * Math.PI * 2) * 0.2, Math.sin(i / 48 * Math.PI * 2) * 0.2, 0]);
  const ticks = [[0.12, 0, 0], [0.34, 0, 0], [-0.12, 0, 0], [-0.34, 0, 0], [0, 0.12, 0], [0, 0.34, 0], [0, -0.12, 0], [0, -0.34, 0]];
  const a = fat(v, ring, { color: 0xffffff, w: 3.4 }), b = fat(v, ring.map(p => [p[0] * 1.0, p[1], 0]), { color: 0xff3a3a, w: 3.4, dashed: true, dash: 0.07, gap: 0.07 });
  const t = fat(v, ticks, { segments: true, color: 0xffffff, w: 3.4 });
  [a, b, t].forEach(o => { o.material.depthTest = false; o.renderOrder = 30; });
  g.add(a, b, t);
  return g;
}
export const stageXY = (v, p) => pt(toStage(v, p));
export function tagAt(el, v, sel, p, dx = 0, dy = 0) {                 // put a card tag at a scene point
  const [x, y] = toStage(v, p), t = qs(el, sel);
  t.style.left = `${x - 1075 + dx}px`; t.style.top = `${y - 150 + dy}px`; t.style.right = 'auto'; t.style.bottom = 'auto';
}
export { col, card, kick, row, btn, fld, lbl, cb, sec, note, I, qs, at, ramp, e3, kf, mix, io };
