// Writes promo/v2/walk_schedule.json (make_timeline.py reads it) from the opening's script, and prints its pace.
//     node promo/v2/build/walk_schedule_json.mjs
import { writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { buildSchedule, clock } from '../web/src/walk_schedule.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
{
  const S = buildSchedule();
  const out = path.resolve(here, '..', 'walk_schedule.json');
  writeFileSync(out, JSON.stringify({ marks: S.marks, riggedIn: S.riggedIn, end: S.end, drag: S.drag, ops: S.ops.map(o => ({ i: o.i, kind: o.kind, target: o.target, t: +o.t.toFixed(3), arrive: +o.arrive.toFixed(3), step: o.step, label: o.label })) }, null, 1) + '\n');
  let gaps = 0, minGap = 9, prev = null;
  for (const o of S.ops) {
    const presses = o.kind === 'edit' ? o.dbl : o.kind === 'click' || o.kind === 'drag' ? [o.t] : [];
    for (const p of presses) { if (prev !== null && p - prev < 0.35 - 1e-9 && !(o.kind === 'edit' && p === o.dbl[1])) gaps++; if (prev !== null) minGap = Math.min(minGap, p - prev); prev = p; }
  }
  console.log('ops', S.ops.length, ' build at', S.riggedIn.toFixed(2), 's =', clock(S.riggedIn), ' end', S.end.toFixed(2), ' presses closer than 0.35 s:', gaps, ' closest', minGap.toFixed(2), 's');
  for (const k of ['newmove', 'makechain', 'pose', 'record', 'ring1', 'ring2', 'ring3', 'spread', 'delays', 'path', 'build', 'grab']) console.log(k.padEnd(10), S.marks[k].toFixed(2));
}
