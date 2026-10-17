// The editors of the opening (promo v2.3), drawn at Blender's own pixel size and scaled up by a zoom on the wrapper: the Outliner,
// the Properties editor (Object tab, Transform), the CopyThat 0.20.2 panel at the sidebar's usual width (205 px), and the two
// dialogs, Ring and Spread. Copied from the real shots in dist/promo/live_test/shots (20_panel, 23_panel, 24_panel, 30_view) and the
// recording in dist/promo/rec/main; the wording is the add-on's (rigmoves/__init__.py, _draw_move and the dialogs' draw()).
// Every element that is pointed at or changes has an id; beats_walk.mjs moves them.
export const Z = 1.9;                                   // the stage pixels of one Blender pixel

const I = n => `<img src="/icons/${n}.png" alt="">`;
const sv = (inner, w = 12, h = w) => `<svg width="${w}" height="${h}" viewBox="0 0 12 12">${inner}</svg>`;
const G = {
  obj: sv('<path d="M1.3 2.4h9.4L6 10.3z" fill="none" stroke="#e8923a" stroke-width="1.6" stroke-linejoin="round"/>', 13),
  mesh: sv('<path d="M1.3 2.4h9.4L6 10.3z" fill="none" stroke="#7fcf7a" stroke-width="1.4" stroke-linejoin="round"/><circle cx="6" cy="2.6" r="1" fill="#7fcf7a"/><circle cx="1.5" cy="2.6" r="1" fill="#7fcf7a"/><circle cx="10.5" cy="2.6" r="1" fill="#7fcf7a"/>', 13),
  cam: sv('<rect x="1" y="3.4" width="7.6" height="6" rx="1.3" fill="none" stroke="#e8923a" stroke-width="1.5"/><path d="M8.8 5.6l2.4-1.5v4.8L8.8 7.7z" fill="#e8923a"/>', 13),
  arm: sv('<circle cx="6" cy="2.6" r="1.5" fill="none" stroke="#e8923a" stroke-width="1.3"/><path d="M6 4.3v3.6M2.5 5.2L6 6M9.5 5.2L6 6M6 7.9L3.5 11M6 7.9L8.5 11" stroke="#e8923a" stroke-width="1.3" fill="none" stroke-linecap="round"/>', 13),
  armw: sv('<circle cx="6" cy="2.6" r="1.5" fill="none" stroke="#e6e6e6" stroke-width="1.3"/><path d="M6 4.3v3.6M2.5 5.2L6 6M9.5 5.2L6 6M6 7.9L3.5 11M6 7.9L8.5 11" stroke="#e6e6e6" stroke-width="1.3" fill="none" stroke-linecap="round"/>', 14),
  eye: sv('<ellipse cx="6" cy="6" rx="5.2" ry="3.3" fill="none" stroke="#dcdcdc" stroke-width="1.3"/><circle cx="6" cy="6" r="1.6" fill="#dcdcdc"/>', 13),
  rcam: sv('<rect x="1" y="3.2" width="10" height="6.6" rx="1.4" fill="none" stroke="#dcdcdc" stroke-width="1.3"/><circle cx="6" cy="6.5" r="1.7" fill="none" stroke="#dcdcdc" stroke-width="1.2"/>', 13),
  coll: sv('<rect x="1.4" y="2.6" width="9.2" height="6.8" rx="1.1" fill="none" stroke="#d6d6d6" stroke-width="1.3"/>', 13),
  tick: sv('<path d="M2 6.4l2.8 2.8L10.2 3" fill="none" stroke="#e8e8e8" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"/>', 12),
  dot: sv('<circle cx="6" cy="6" r="1.7" fill="#e8e8e8"/>', 12),
  x: sv('<path d="M3 3l6 6M9 3l-6 6" stroke="#c4c4c4" stroke-width="1.5" stroke-linecap="round"/>', 11),
  link: sv('<path d="M5.2 6.8l1.6-1.6" stroke="#dcdcdc" stroke-width="1.3" stroke-linecap="round"/><path d="M4.4 8.6a2 2 0 010-2.8l.9-.9M7.6 3.4a2 2 0 012.8 2.8l-.9.9" stroke="#dcdcdc" stroke-width="1.3" fill="none" stroke-linecap="round"/>', 13),
  info: sv('<circle cx="6" cy="6" r="5.3" fill="#e6e6e6"/><rect x="5.2" y="5" width="1.6" height="4" rx=".4" fill="#262626"/><circle cx="6" cy="3.3" r=".95" fill="#262626"/>', 13),
  pause: sv('<rect x="2.4" y="2" width="2.2" height="8" fill="#dcdcdc"/><rect x="7.4" y="2" width="2.2" height="8" fill="#dcdcdc"/>', 12),
  back: sv('<path d="M4.2 3.4L2 5.6l2.2 2.2M2.3 5.6h5a2.7 2.7 0 010 5.4H5" stroke="#dcdcdc" stroke-width="1.4" fill="none" stroke-linecap="round" stroke-linejoin="round"/>', 13),
  plus: sv('<path d="M6 2v8M2 6h8" stroke="#dcdcdc" stroke-width="1.6" stroke-linecap="round"/>', 12),
  find: sv('<circle cx="5" cy="5" r="3.2" fill="none" stroke="#9a9a9a" stroke-width="1.4"/><path d="M7.4 7.4L10.4 10.4" stroke="#9a9a9a" stroke-width="1.5" stroke-linecap="round"/>', 12),
  lock: sv('<rect x="2.6" y="5.4" width="6.8" height="5" rx="1" fill="none" stroke="#9c9c9c" stroke-width="1.2"/><path d="M4 5.4V4a2 2 0 014 0" fill="none" stroke="#9c9c9c" stroke-width="1.2"/>', 12),
  key: sv('<path d="M6 2.2l3.6 3.8L6 9.8 2.4 6z" fill="none" stroke="#9c9c9c" stroke-width="1.1"/>', 12),
  sel: sv('<path d="M3 1.5l6.4 5.2-3 .5 1.7 3.2-1.4.7-1.7-3.2-2.3 1.9z" fill="#dcdcdc"/>', 12),
};
export const icons = G;

// ---------------------------------------------------------------- Outliner
// The scene's parts in the order Blender sorts them (by name); a copy's row shows when it is made. Leaf 2 and Leaf 3 have two rows
// each: where they stand beside Leaf 1 until the chain is made, and inside it (Leaf 3 inside Leaf 2) after.
export const OL_ROWS = [
  ['Core', 0], ['Inner Leader', 0], ...[2, 3, 4, 5, 6].map(k => ['Inner Leader ' + k, 0]),
  ['Leaf 1', 0], ['Leaf 2', 1], ['Leaf 3', 2], ['Leaf 2', 0], ['Leaf 3', 0], ['Leaf 1 2', 0],
  ['Outer Leader', 0], ...[2, 3, 4, 5, 6, 7, 8].map(k => ['Outer Leader ' + k, 0]),
  ['Pedestal', 0], ['Promo Camera', 0], ['Stem', 0], ['CopyThat Rig', -1],
];
export const olRowId = (name, depth) => name + (name.startsWith('Leaf 2') || name.startsWith('Leaf 3') ? (depth ? '~n' : '~f') : '');
export function outlinerHTML() {
  const rows = OL_ROWS.map(([n, d]) => {
    const cam = n === 'Promo Camera', rig = n === 'CopyThat Rig';
    const left = 6 + 14 * (d + (rig ? 1 : 0) + 1);
    const data = cam ? '' : rig ? '' : `<span class="di">${G.mesh}</span>`;
    return `<div class="or" data-id="${olRowId(n, d)}" data-n="${n}"><i class="ex" style="margin-left:${left}px"></i><span class="oi">${rig ? G.arm : cam ? G.cam : G.obj}</span>`
      + `<span class="nm">${n}</span>${data}<span class="vs"><span>${G.eye}</span><span>${G.rcam}</span></span></div>`;
  }).join('');
  return `<div class="ol">
    <div class="oh"><i class="ib"></i><i class="ib"></i><div class="srch">${G.find}<span>Search</span></div><i class="ib"></i></div>
    <div class="obody" id="olb">
      <div class="or top"><i class="ex open" style="margin-left:6px"></i><span class="oi">${G.coll}</span><span class="nm">Scene Collection</span></div>
      <div class="or top"><i class="ex open" style="margin-left:20px"></i><span class="oi">${G.coll}</span><span class="nm">CopyThat Flower</span><span class="vs"><span class="ckk">${G.tick}</span><span>${G.eye}</span><span>${G.rcam}</span></span></div>
      ${rows}
    </div></div>`;
}

// ---------------------------------------------------------------- Properties editor: Object tab, Transform panel
const TABS = ['#8a8a8a', '#8a8a8a', '#8a8a8a', '#8a8a8a', '#7e9bd0', '#c0605a', '#e8923a', '#5a8fd8', '#8a8a8a', '#8a8a8a', '#5aa6c8', '#7fcf7a', '#d86a5c'];
const fieldRow = (label, id, first, last) =>
  `<div class="pr"><div class="l">${label}</div><div class="f"><div class="fd ${first ? 'ft' : ''} ${last ? 'fb' : ''}" id="${id}"><span class="v"></span></div></div><div class="x2">${G.lock}</div><div class="x2">${G.key}</div></div>`;
export function propertiesHTML() {
  return `<div class="pp">
    <div class="pt">${TABS.map((c, i) => `<i style="background:${i === 6 ? '#e8923a' : c};${i === 6 ? 'outline:2px solid #5c4020;outline-offset:2px;border-radius:4px' : 'opacity:.75'}"></i>`).join('')}</div>
    <div class="pc">
      <div class="ph"><span class="oi">${G.obj}</span><span id="ppn">Stem</span><span class="pin">${G.key}</span></div>
      <div class="pdb"><span class="oi">${G.obj}</span><div class="dbn" id="ppn2">Stem</div></div>
      <div class="ppn"><div class="pth"><i class="ex open"></i>Transform</div>
        ${fieldRow('Location X', 'pp-locx', true, false)}${fieldRow('Y', 'pp-locy')}${fieldRow('Z', 'pp-locz', false, true)}
        <div class="gap"></div>
        ${fieldRow('Rotation X', 'pp-rotx', true, false)}${fieldRow('Y', 'pp-roty')}${fieldRow('Z', 'pp-rotz', false, true)}
        <div class="gap"></div>
        <div class="pr"><div class="l">Mode</div><div class="f"><div class="fd dd"><span>XYZ Euler</span><i class="cv2"></i></div></div><div class="x2"></div><div class="x2">${G.key}</div></div>
        <div class="gap"></div>
        ${fieldRow('Scale X', 'pp-scx', true, false)}${fieldRow('Y', 'pp-scy')}${fieldRow('Z', 'pp-scz', false, true)}
        <div class="pth sb2"><i class="ex"></i>Delta Transform</div>
      </div></div></div>`;
}

// ---------------------------------------------------------------- the CopyThat panel
const btn = (label, o = {}) => `<div class="bt ${o.c || ''}"${o.id ? ` id="${o.id}"` : ''}>${o.i ? I(o.i) : ''}${o.svg || ''}<span>${label}</span></div>`;
const sec = (id, title, icon, extra = '') => `<div class="sc" id="s-${id}"><i class="tg shut"></i>${I(icon)}<b>${title}</b>${extra}</div>`;
const hint = (t, id) => `<div class="hint"${id ? ` id="${id}"` : ''}>${t}</div>`;
const TIMING = ['Outer Leader', 'Inner Leader', 'Core', 'Leaf 1', 'Leaf 2', 'Leaf 3'];
const CHAINS = TIMING.map(n => [n, n === 'Outer Leader' ? 'Outer …' : n === 'Inner Leader' ? 'Inner …' : n]);
export const GROUPS = [
  { leader: 'Inner Leader', key: 'inner', rows: [['…ader 2'], ['…ader 3'], ['…ader 4'], ['…ader 5'], ['…ader 6']] },
  { leader: 'Leaf 1', key: 'leaf', rows: [['… 1 2 +2']] },
  { leader: 'Outer Leader', key: 'outer', rows: [['…ader 2'], ['…ader 3'], ['…ader 4'], ['…ader 5'], ['…ader 6'], ['…ader 7'], ['…ader 8']] },
];
export const TIMING_NAMES = TIMING;
export function panelHTML() {
  const groups = GROUPS.map(g => `<div class="grp" id="g-${g.key}" style="display:none"><div class="hint small">with '${g.leader}'</div>${g.rows.map((r, k) =>
    `<div class="rr"><span class="rn">${r[0]}</span><div class="fd n" id="ld-${g.key}${k}"><span class="v">0</span></div><div class="bt sm2"><span>-</span></div><i class="xx">${G.x}</i></div>`).join('')}</div>`).join('');
  return `<div class="pn"><div id="pnin">
    <div class="ph2"><i class="tg"></i>${I('logo')}<b>CopyThat</b><span class="grip">⁞⁞⁞</span></div>
    <div class="tagl">Record a move. Get a slider.</div>
    <div id="pre">
      <div class="say" id="presay">Select the objects that move.</div>
      <div class="pr2 tall" id="prenm-row"><div class="bt on" id="prenm">${I('new_move')}<span>New Move</span></div></div>
    </div>
    <div id="rig" style="display:none">
      <div class="rl"><span class="rl1">${G.armw}<span>CopyThat Rig</span></span><span class="rl2" id="rc">6 parts</span></div>
      <div class="mbox" id="mv">
        <div class="pr2"><i class="tg"></i>${I('slider')}<div class="fd txt grow"><span class="v">Move 1</span></div><i class="xx">${G.x}</i></div>
        <div class="pr2 tallish" id="playrow" style="display:none"><div class="fd grow bigf" id="play"><i class="fill" id="playfill"></i><span class="l">Move 1</span><span class="v" id="playv">0%</span></div><div class="bt sm3"><i class="keyd"></i></div></div>
        <div class="pr2 pose" id="rb"><span class="pk" id="ckb">${G.tick}</span><span class="pl">Before</span><div class="bt grow" id="recb"><span>Record</span></div><div class="bt sm4" id="eyeb">${G.eye}</div></div>
        <div class="pr2 pose" id="ra"><span class="pk" id="cka">${G.dot}</span><span class="pl">After</span><div class="bt grow" id="reca"><span>Record</span></div><div class="bt sm4" id="eyea" style="visibility:hidden">${G.eye}</div></div>
        <div class="gap2"></div>
        ${sec('parts', 'PARTS &amp; PIVOT', 'pivot')}
        ${sec('path', 'PATH', 'curve')}
        <div class="sb" id="b-path">
          <div class="pr2 g2"><div class="bt on" id="ez-Even speed"><span>Even speed</span></div><div class="bt" id="ez-Smooth"><span>Smooth</span></div></div>
          <div class="pr2 g2"><div class="bt"><span>Slow start</span></div><div class="bt"><span>Slow stop</span></div></div>
          <div class="pr2"><div class="bt">${I('curve')}<span>Curve the Path</span></div></div>
          <div class="pr2"><div class="bt dis" id="stepin">${I('steps')}<span>Step in between</span></div></div>
        </div>
        ${sec('timing', 'TIMING', 'timing')}
        <div class="sb" id="b-timing">
          <div class="pr2"><div class="bt" id="spt">${I('spread')}<span>Spread…</span></div></div>
          ${hint('how long each one waits before it starts')}
          <div class="hint lit" id="lit">${G.sel}<span>lit: what you have selected</span></div>
          ${TIMING.map(n => `<div class="tr" id="tr-${n}"><span class="tn">${G.sel}<span>${n}</span></span><div class="fd n" id="tm-${n}"><i class="fill"></i><span class="v">0.00</span></div></div>`).join('')}
        </div>
        ${sec('copies', 'COPIES', 'ring')}
        <div class="sb" id="b-copies">
          <div class="pr2"><div class="bt" id="rg">${I('ring')}<span>Ring…</span></div><div class="bt" id="spc" style="display:none">${I('spread')}<span>Spread…</span></div></div>
          <div id="riders" style="display:none">
            <div class="ride" id="ride">Riding along (7)</div>
            ${hint('lead: below 0 behind, above 0 ahead')}
            ${groups}
          </div>
        </div>
        ${sec('chains', 'CHAINS', 'chain')}
        <div class="sb" id="b-chains">
          <div class="pr2"><div class="bt" id="mc">${I('chain')}<span>Make Chain</span></div><div class="bt" id="cl">${I('curl')}<span>Curl</span></div></div>
          ${hint('moves with the part it follows')}
          ${CHAINS.map(([n, short]) => `<div class="cr"><span class="cn">${short}</span><div class="fd link" id="fw-${n}"><span class="lk">${G.link}</span><span class="v"></span><i class="xx">${G.x}</i></div></div>`).join('')}
        </div>
        <div class="sc" id="s-animate" style="display:none"><i class="tg shut"></i>${I('animate')}<b>ANIMATE</b></div>
      </div>
      <div class="pr2 big2"><div class="bt" id="bs">${I('build')}<span>Build Sliders</span></div></div>
      <div class="pr2"><div class="bt">${G.pause}<span>Pause</span></div><div class="bt">${G.back}<span>To Before</span></div></div>
      <div class="gap3"></div>
      <div class="pr2"><div class="bt" id="nm2">${G.plus}<span>New Move</span></div></div>
      <div class="mbox repb" id="repbox"><div class="rh"><i class="tg"></i>${G.info}<b>REPORT</b></div><div class="rt" id="rtxt"></div></div>
    </div>
    <div class="pfoot">CopyThat 0.20.2 · NemVe3D</div>
  </div></div>`;
}

// ---------------------------------------------------------------- the two dialogs (Blender draws them under the pointer)
const dprow = (label, inner, id) => `<div class="dr"${id ? ` id="${id}"` : ''}><div class="dl">${label}</div><div class="df">${inner}</div></div>`;
const nfld = (id, v) => `<div class="fd n dn" id="${id}"><span class="v">${v}</span></div>`;
const ddn = (id, v) => `<div class="fd dd" id="${id}"><span class="v">${v}</span><i class="cv2"></i></div>`;
export function ringDialogHTML() {
  return `<div class="dlgb" id="dR"><h4>Ring</h4>
    <div class="dl1">Use</div>
    <div class="dr"><div class="df3"><div class="bt"><span>Make copies</span></div><div class="bt"><span>Use what's there</span></div><div class="bt on"><span>Fill the gaps</span></div></div></div>
    ${dprow('Count', nfld('rc-count', '6'))}
    ${dprow('Round', ddn('rc-round', '3D Cursor') + '<div class="menu" id="rc-menu" style="display:none"><div class="mi" id="mi-cursor">3D Cursor</div><div class="mi" id="mi-origin">World Origin</div></div>')}
    ${dprow('About', ddn('rc-about', 'World Z'))}
    ${dprow('', `<div class="cbx"><i class="cbk on"></i><span>Linked copies</span></div>`)}
    ${dprow('Lead step', nfld('rc-lead', '0'))}
    <div class="bt on okb" id="rc-ok"><span>OK</span></div>
  </div>`;
}
export function spreadDialogHTML() {
  return `<div class="dlgb" id="dS"><h4>Spread</h4>
    ${dprow('Order', ddn('sp-order', 'Down a chain'))}
    ${dprow('', `<div class="cbx" id="sp-only"><i class="cbk" id="sp-cb"></i><span>Only the selected</span></div>`)}
    ${dprow('By', `<div class="df3 two"><div class="bt on"><span>Step</span></div><div class="bt"><span>Range</span></div></div>`)}
    <div class="gap2"></div>
    ${dprow('Start Delay', nfld('sp-start', '0.00'))}
    ${dprow('Delay step', nfld('sp-step', '0.10'))}
    <div class="bt on okb" id="sp-ok"><span>OK</span></div>
  </div>`;
}
