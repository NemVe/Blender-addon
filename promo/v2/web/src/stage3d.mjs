// The Three.js side: two renderers (consecutive beats use different ones, so a wipe can show both), PBR under RoomEnvironment,
// a warm key light with soft shadows, a grid that fades out, bloom, and fat gold edge lines. Every scene is posed by the
// caller from the time; nothing here runs on a clock.
import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { Line2 } from 'three/addons/lines/Line2.js';
import { LineGeometry } from 'three/addons/lines/LineGeometry.js';
import { LineSegments2 } from 'three/addons/lines/LineSegments2.js';
import { LineSegmentsGeometry } from 'three/addons/lines/LineSegmentsGeometry.js';
import { LineMaterial } from 'three/addons/lines/LineMaterial.js';
import { mix } from './lib.mjs';

export { THREE };
export const GOLD = 0xC9A76A, GOLD2 = 0xE8CE96, CREAM = 0xD2C6AB, INK = 0x0d0d10;
export const K = { v: 1 };                      // the page's scale of the stage: the drawing buffers follow it

const slots = [];
function slot(i) {
  if (slots[i]) return slots[i];
  const renderer = new THREE.WebGLRenderer({ antialias: false, powerPreference: 'high-performance' });
  renderer.setPixelRatio(1);
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.0;
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  const env = new THREE.PMREMGenerator(renderer).fromScene(new RoomEnvironment(), 0.04).texture;
  const target = new THREE.WebGLRenderTarget(16, 16, { type: THREE.HalfFloatType, samples: 4 });
  const composer = new EffectComposer(renderer, target);
  const pass = new RenderPass(null, null);
  const bloom = new UnrealBloomPass(new THREE.Vector2(16, 16), 0.22, 0.5, 0.9);
  composer.addPass(pass); composer.addPass(bloom); composer.addPass(new OutputPass());
  return (slots[i] = { renderer, composer, pass, bloom, env, w: 0, h: 0 });
}

// A scene with its camera, in a box of w x h stage pixels. `host` is the element whose canvas it draws into.
export function mkView({ w, h, fov = 30, pos = [0, 3, 10], look = [0, 1, 0], slot: s = 0, bg = INK, bloom = 0.22, floor: fl = true, grid = true, rim = true, env = 0.4 }) {
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(bg);
  scene.environmentIntensity = env;
  const camera = new THREE.PerspectiveCamera(fov, w / h, 0.1, 200);
  camera.position.set(...pos); camera.lookAt(...look);
  const v = { w, h, slot: s, scene, camera, fats: [], host: null, bloom, ox: 0, oy: 0 };
  scene.add(new THREE.HemisphereLight(0xfff1dd, 0x16161c, 0.22));
  const key = new THREE.DirectionalLight(0xffe6c8, 1.7);
  key.position.set(4.5, 8, 5.5); key.castShadow = true;
  key.shadow.mapSize.set(2048, 2048); key.shadow.bias = -0.0004; key.shadow.normalBias = 0.02; key.shadow.radius = 5;
  Object.assign(key.shadow.camera, { left: -9, right: 9, top: 9, bottom: -9, near: 1, far: 30 });
  scene.add(key);
  if (rim) { const r = new THREE.DirectionalLight(GOLD, 1.3); r.position.set(-6, 3.5, -5); scene.add(r); }
  if (fl) floor(v, { grid });
  return v;
}

export function floor(v, { r = 11, grid = true, shadow = 0.55, y = 0 } = {}) {
  const plane = new THREE.Mesh(new THREE.CircleGeometry(r, 64), new THREE.ShadowMaterial({ opacity: shadow }));
  plane.rotation.x = -Math.PI / 2; plane.position.y = y; plane.receiveShadow = true;
  v.scene.add(plane);
  if (!grid) return;
  const g = new THREE.Mesh(new THREE.PlaneGeometry(r * 2, r * 2), new THREE.ShaderMaterial({
    transparent: true, depthWrite: false,
    uniforms: { R: { value: r * 0.78 }, col: { value: new THREE.Color(GOLD) } },
    vertexShader: 'varying vec3 vP; void main(){ vP = (modelMatrix*vec4(position,1.)).xyz; gl_Position = projectionMatrix*viewMatrix*vec4(vP,1.); }',
    fragmentShader: `uniform float R; uniform vec3 col; varying vec3 vP;
      void main(){ vec2 c = vP.xz; vec2 g = abs(fract(c - .5) - .5)/fwidth(c); float l = 1. - min(min(g.x, g.y), 1.);
        vec2 g5 = abs(fract(c/5. - .5) - .5)/fwidth(c/5.); float l5 = 1. - min(min(g5.x, g5.y), 1.);
        float fade = 1. - smoothstep(R*.12, R, length(c)); gl_FragColor = vec4(col, (l*.13 + l5*.2)*fade); }`,
  }));
  g.rotation.x = -Math.PI / 2; g.position.y = y + 0.003;
  v.scene.add(g);
}

export function render(v) {
  const s = slot(v.slot), k = K.v;
  const bw = Math.max(2, Math.round(v.w * k)), bh = Math.max(2, Math.round(v.h * k));
  if (s.w !== bw || s.h !== bh) { s.renderer.setSize(bw, bh, false); s.composer.setSize(bw, bh); s.bloom.resolution.set(bw, bh); s.w = bw; s.h = bh; }
  const cv = s.renderer.domElement;
  cv.style.width = v.w + 'px'; cv.style.height = v.h + 'px';
  if (cv.parentNode !== v.host) v.host.appendChild(cv);
  if (!v.camera.view || !v.camera.view.enabled) v.camera.aspect = v.w / v.h;     // a view offset keeps the full frame's aspect
  v.camera.updateProjectionMatrix();
  v.scene.environment = s.env;
  s.pass.scene = v.scene; s.pass.camera = v.camera;
  s.bloom.strength = v.bloom;
  v.fats.forEach(m => { m.resolution.set(bw, bh); m.linewidth = Math.max(0.6, m.userData.w * k); });
  s.composer.render();
}

// Where a point of the scene lands on the stage, for the cursor to find it.
const _p = new THREE.Vector3();
export function toStage(v, p) {
  v.camera.aspect = v.w / v.h; v.camera.updateProjectionMatrix(); v.camera.updateMatrixWorld();
  _p.copy(p).project(v.camera);
  return [v.ox + (_p.x * 0.5 + 0.5) * v.w, v.oy + (-_p.y * 0.5 + 0.5) * v.h];
}

// ---- things to put in a scene ----
export const std = (color = CREAM, rough = 0.42, metal = 0.0, extra = {}) =>
  new THREE.MeshStandardMaterial({ color, roughness: rough, metalness: metal, ...extra });
export const goldMat = () => std(GOLD, 0.26, 1.0);

function fatMat(v, { color = GOLD, w = 3, op = 1, dashed = false, dash = 0.14, gap = 0.1 }) {
  const m = new LineMaterial({ color, linewidth: w, transparent: op < 1, opacity: op, dashed, dashSize: dash, gapSize: gap });
  m.userData.w = w;
  v.fats.push(m);
  return m;
}
const flat = pts => pts.flatMap(p => (Array.isArray(p) ? p : [p.x, p.y, p.z]));
export function fat(v, pts, o = {}) {              // a line through points, `segments: true` for pairs
  const seg = !!o.segments;
  const geo = seg ? new LineSegmentsGeometry() : new LineGeometry();
  geo.setPositions(flat(pts));
  const l = seg ? new LineSegments2(geo, fatMat(v, o)) : new Line2(geo, fatMat(v, o));
  if (o.dashed) l.computeLineDistances();
  return l;
}
export function edgesOf(v, geo, o = {}) {
  const g = new LineSegmentsGeometry().fromEdgesGeometry(new THREE.EdgesGeometry(geo, 30));
  return new LineSegments2(g, fatMat(v, o));
}

// A cube of warm cream with gold edges. Its edge line is cube.userData.edge (colour and width can be driven).
export function cube(v, size = [1, 1, 1], o = {}) {
  const g = new THREE.BoxGeometry(...size);
  const mat = std(o.color ?? CREAM, o.rough ?? 0.42, o.metal ?? 0, { polygonOffset: true, polygonOffsetFactor: 1, polygonOffsetUnits: 1, ...(o.mat || {}) });
  const m = new THREE.Mesh(g, mat);
  m.castShadow = o.shadow !== false; m.receiveShadow = true;
  const e = edgesOf(v, g, { color: o.edge ?? GOLD, w: o.ew ?? 3.4, op: o.eop ?? 1 });
  m.add(e); m.userData.edge = e;
  return m;
}
// A see-through gold outline of a pose that was recorded.
export function ghost(v, size = [1, 1, 1], o = {}) {
  const g = new THREE.BoxGeometry(...size);
  const m = new THREE.Mesh(g, new THREE.MeshBasicMaterial({ color: GOLD, transparent: true, opacity: o.fill ?? 0.1, depthWrite: false }));
  const e = edgesOf(v, g, { color: o.edge ?? GOLD2, w: o.ew ?? 2.6, op: o.eop ?? 0.8 });
  m.add(e); m.userData.edge = e;
  return m;
}
export function setEdge(c, color, w, op) {
  const m = c.userData.edge.material;
  m.color.set(color);
  if (w !== undefined) m.userData.w = w;
  if (op !== undefined) { m.opacity = op; m.transparent = op < 1; }
}
export function setGlow(c, rgb) { c.userData.edge.material.color.setRGB(...rgb); }   // above 1 for the bloom to pick up

// ---- the flower ----
export async function loadFlower() {
  const gltf = await new GLTFLoader().loadAsync('/assets/flower.glb');
  const motion = await (await fetch('/assets/flower_motion.json')).json();
  return { gltf, motion };
}
const _q0 = new THREE.Quaternion(), _q1 = new THREE.Quaternion();
export function instFlower(F, { material = null } = {}) {
  const root = F.gltf.scene.clone(true);
  const byName = {};
  root.traverse(o => { if (o.name) byName[o.name] = o; });
  // GLTFLoader writes spaces in node names as underscores; the motion file keeps the Blender names
  const parts = {};
  [...Object.keys(F.motion.motion), 'Stem', 'Pedestal'].forEach(n => { parts[n] = byName[THREE.PropertyBinding.sanitizeNodeName(n)]; });
  if (material) root.traverse(o => { if (o.isMesh) o.material = material; });
  root.traverse(o => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } });
  const names = Object.keys(F.motion.motion);
  const core = (() => { let m = null; root.traverse(o => { if (o.isMesh && o.material && /core glow/i.test(o.material.name)) m = o.material; }); return m; })();
  return {
    root, parts, names, core, coreScale: 1,
    pose(f) {                                       // f: frame index from 0 to 150 (fractional is fine)
      const i0 = Math.floor(Math.max(0, Math.min(150, f))), i1 = Math.min(150, i0 + 1), u = Math.max(0, Math.min(150, f)) - i0;
      for (const n of names) {
        const node = parts[n]; if (!node) continue;
        const a = F.motion.motion[n][i0], b = F.motion.motion[n][i1];
        node.position.set(mix(a[0], b[0], u), mix(a[1], b[1], u), mix(a[2], b[2], u));
        node.quaternion.slerpQuaternions(_q0.set(a[3], a[4], a[5], a[6]), _q1.set(b[3], b[4], b[5], b[6]), u);
        node.scale.set(mix(a[7], b[7], u), mix(a[8], b[8], u), mix(a[9], b[9], u));
      }
      if (core) {
        const g = F.motion.core_glow, v = g.values;
        const ii = Math.floor(Math.max(0, Math.min(v.length - 1, f)));
        core.emissive.setRGB(g.color[0], g.color[1], g.color[2]);
        core.emissiveIntensity = mix(v[ii], v[Math.min(v.length - 1, ii + 1)], f - ii) * this.coreScale;
      }
    },
  };
}

// The template's right-hand card: 1331 x 1140 at (1075, 150) on the stage.
export function cardView(slot, o = {}) {
  const v = mkView({ w: 1331, h: 1140, fov: 28, pos: [0, 3.0, 9.6], look: [0, 1.0, 0], slot, bloom: 0.22, ...o });
  v.ox = 1075; v.oy = 150;
  return v;
}

// Blender's move-and-turn gizmo: a blue arrow up, red and green across, a blue ring; drawn over everything.
export function gizmo(len = 1.0) {
  const g = new THREE.Group();
  const arrow = (color, dir) => {
    const m = new THREE.MeshBasicMaterial({ color, depthTest: false, transparent: true });
    const a = new THREE.Group();
    const shaft = new THREE.Mesh(new THREE.CylinderGeometry(0.02, 0.02, len * 0.8, 12), m); shaft.position.y = len * 0.4;
    const tip = new THREE.Mesh(new THREE.ConeGeometry(0.075, 0.22, 16), m); tip.position.y = len * 0.9;
    a.add(shaft, tip); a.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir);
    return a;
  };
  g.add(arrow(0x2f83ff, new THREE.Vector3(0, 1, 0)), arrow(0xff3652, new THREE.Vector3(1, 0, 0)), arrow(0x7cd324, new THREE.Vector3(0, 0, 1)));
  const ring = new THREE.Mesh(new THREE.TorusGeometry(len * 0.78, 0.014, 8, 72), new THREE.MeshBasicMaterial({ color: 0x4a9bff, depthTest: false, transparent: true, opacity: 0.85 }));
  ring.rotation.x = Math.PI / 2; g.add(ring);
  g.traverse(o => { if (o.isMesh) o.renderOrder = 20; });
  g.userData.setOpacity = x => g.traverse(o => { if (o.isMesh) { o.material.opacity = x * (o === ring ? 0.85 : 1); } });
  return g;
}

// Selected parts: bright edges that bloom.
export function select(c, on) {
  if (on) { setGlow(c, [2.6, 2.0, 1.1]); c.userData.edge.material.userData.w = 5; } else { c.userData.edge.material.color.set(GOLD); c.userData.edge.material.userData.w = 3.4; }
}
