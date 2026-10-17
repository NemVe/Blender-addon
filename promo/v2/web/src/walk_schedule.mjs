// The opening's script (promo v2.3): every action of promo/files/FLOWER_FAST.md steps 1-9 that a customer does with
// CopyThat_flower_fast.blend, in order, with its time in seconds after the first click. Pure data and no DOM, so the page
// (beats_walk.mjs) and make_timeline.py (through walk_schedule.json) read the same times:
//
//     node promo/v2/build/walk_schedule_json.mjs       writes promo/v2/walk_schedule.json and prints the pace
//
// The pace is a person who knows the steps: the pointer travels 0.4-0.9 s and rests a moment before each press; typing is
// 6-7 characters a second, then Enter; a dialog stays open while its rows are set one by one. No two presses are closer than
// 0.35 s except the two of a double-click into a field.
export const DRAG = 2.5;             // the slider drag of the bloom
export const GRAB = 1.25;            // from the press on Build to the grab of the slider (scroll the panel up, move over)
export const CPS = 0.15;             // seconds per typed character (6.7 a second)
const REGION = { ol: 'ol', olx: 'ol', pn: 'pn', sec: 'pn', tim: 'pn', pp: 'pp', dlg: 'dlg' };
const region = t => (t === 'in' ? 'in' : REGION[t.split(':')[0]]);

export function buildSchedule() {
  const ops = [], marks = { go: 0 };
  let free = -1.0, here = 'in', step = 0, label = '';
  const reach = (target, o) => {
    const same = region(here) === region(target);
    const trav = o.trav !== undefined ? o.trav : here === 'in' ? 1.0 : same ? 0.42 : 0.72;
    return free + trav;
  };
  const put = (op, o) => {
    Object.assign(op, { i: ops.length, step, label: o.label || label, from: here });
    if (o.label) label = o.label;
    if (o.mark) { marks[o.mark] = op.t; marks[o.mark + '_arrive'] = op.arrive; }
    ops.push(op);
  };
  const begin = (n, text) => { step = n; label = text; };
  const click = (target, o = {}) => {
    const arrive = reach(target, o), t = arrive + (o.dwell !== undefined ? o.dwell : 0.18);
    put({ kind: 'click', target, arrive, t, mods: o.mods || [] }, o);
    free = t + 0.12; here = target;
    return t;
  };
  const edit = (target, text, o = {}) => {
    const arrive = reach(target, { trav: o.trav !== undefined ? o.trav : region(here) === region(target) ? 0.55 : 0.8 }), d1 = arrive + 0.18, d2 = d1 + 0.17, first = d2 + 0.34;
    const chars = [...text].map((_, k) => +(first + k * CPS).toFixed(3));
    const enter = chars[chars.length - 1] + 0.30;
    put({ kind: 'edit', target, text, arrive, dbl: [d1, d2], chars, t: enter, mods: [] }, o);
    free = enter + 0.12; here = target;
    return enter;
  };
  const hover = (target, hold, o = {}) => {                       // the pointer rests on a row to let it be read: nothing is pressed
    const arrive = reach(target, o);
    put({ kind: 'hover', target, arrive, t: arrive + hold, mods: [] }, o);
    free = arrive + hold; here = target;
  };
  const ctrl = { mods: ['ctrl'], trav: 0.4 };

  // 1. Select the six parts and press New Move
  begin(1, 'SELECT THE PARTS');
  click('ol:Outer Leader', { mark: 'first' });
  click('ol:Inner Leader', ctrl); click('ol:Core', ctrl); click('ol:Leaf 1', ctrl); click('ol:Leaf 2', ctrl); click('ol:Leaf 3', ctrl);
  click('pn:newmove', { label: 'NEW MOVE', mark: 'newmove' });

  // 2. Make Chain: the leaf segments hang from each other (Leaf 1 clicked last, so it is the active one)
  begin(2, 'MAKE CHAIN');
  click('ol:Leaf 3', { mark: 'chain' });
  click('ol:Leaf 2', ctrl); click('ol:Leaf 1', ctrl);
  click('sec:chains'); click('pn:makechain', { mark: 'makechain' });

  // 3. Pose the flower open: one part at a time, one typed value at a time
  begin(3, 'POSE · OUTER LEADER');
  click('ol:Outer Leader', { mark: 'pose' }); edit('pp:rotx', '75', { mark: 'v_outer' });
  click('ol:Inner Leader', { label: 'POSE · INNER LEADER' }); edit('pp:rotx', '45');
  click('ol:Core', { label: 'POSE · CORE' }); edit('pp:locz', '1.47'); edit('pp:rotz', '60', { trav: 0.45 });
  click('ol:Leaf 1', { label: 'POSE · LEAF 1' }); edit('pp:rotx', '28');
  click('olx:Leaf 1', { mods: ['shift'], trav: 0.5, label: 'OPEN THE LEAF' });
  click('ol:Leaf 2', { label: 'POSE · LEAF 2' }); edit('pp:rotx', '-145', { mark: 'v_leaf2' });
  click('ol:Leaf 3', { label: 'POSE · LEAF 3' }); edit('pp:rotx', '172', { mark: 'v_leaf3' });

  // 4. Record After
  begin(4, 'RECORD AFTER');
  click('pn:record_after', { mark: 'record', trav: 0.85 });

  // 5. Ring the outer petals
  begin(5, 'RING · OUTER PETALS');
  click('sec:copies', { mark: 'ring1' });
  click('ol:Outer Leader'); click('pn:ring', { mark: 'ring1_press' });
  edit('dlg:count', '8', { trav: 0.8 }); click('dlg:round'); click('dlg:round:World Origin', { trav: 0.4 });
  edit('dlg:lead', '9', { trav: 0.55 }); click('dlg:ok', { mark: 'ring1_ok' });

  // 6. Ring the inner petals
  begin(6, 'RING · INNER PETALS');
  click('ol:Inner Leader', { mark: 'ring2' }); click('pn:ring');
  edit('dlg:count', '6', { trav: 0.8 }); hover('dlg:round', 0.4, { trav: 0.4 });
  edit('dlg:lead', '14', { trav: 0.45 }); click('dlg:ok', { mark: 'ring2_ok' });

  // 7. Ring the leaf
  begin(7, 'RING · THE LEAF');
  click('ol:Leaf 1', { mark: 'ring3' }); click('pn:ring');
  edit('dlg:count', '2', { trav: 0.8 }); hover('dlg:lead', 0.4, { trav: 0.4 });
  click('dlg:ok', { mark: 'ring3_ok', trav: 0.4 });

  // 8. Spread on the leaf, then two delays typed by hand
  begin(8, 'SPREAD · DELAYS');
  click('ol:Leaf 3', { mark: 'spread' });
  click('ol:Leaf 2', ctrl); click('ol:Leaf 1', ctrl);
  click('sec:timing'); click('pn:spread_timing', { mark: 'spread_press' });
  hover('dlg:order', 0.45, { trav: 0.7 });
  click('dlg:only', { trav: 0.4 });
  edit('dlg:start', '0.10', { trav: 0.55 }); edit('dlg:step', '0.15', { trav: 0.45 });
  click('dlg:ok', { mark: 'spread_ok', trav: 0.45 });
  edit('tim:Inner Leader', '0.34', { label: 'TYPE THE DELAYS', mark: 'delays', trav: 0.8 }); edit('tim:Core', '0.40', { trav: 0.45 });

  // 9. Smooth, Build
  begin(9, 'EASE · SMOOTH');
  click('sec:path', { mark: 'path' }); click('pn:smooth', { trav: 0.4, mark: 'smooth' });
  click('pn:build', { label: 'BUILD SLIDERS', mark: 'build', trav: 0.9 });

  // 10. The bloom: drag the Move 1 slider from 0 to 100 %
  const tB = marks.build, grab = tB + GRAB;
  step = 10; label = 'DONE · ONE SLIDER';
  ops.push({ kind: 'drag', target: 'pn:slider', arrive: grab - 0.18, t: grab, end: grab + DRAG, mods: [], i: ops.length, step, label, from: here });
  marks.grab = grab; marks.end = grab + DRAG;

  const riggedIn = tB;                                            // the timer starts at the first click (0) and stops on Build
  return { ops, marks, riggedIn, drag: DRAG, end: grab + DRAG };
}

// the time as the timer shows it: m:ss
export const clock = s => { const k = Math.max(0, Math.floor(s + 1e-9)); return Math.floor(k / 60) + ':' + String(k % 60).padStart(2, '0'); };
