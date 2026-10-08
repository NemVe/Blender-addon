# RigMoves handoff: everything a new session needs

Read this file and `CLAUDE.md` before touching anything. Then read the user
guide `rigmoves/README.md`, which is the source of truth for what the add-on
promises to the user.

## Who it's for and how they work

- **Author:** NemVe3D (https://creators.sa/nemve). The credit is in `bl_info`
  (`author`, `doc_url`) and in both READMEs. Keep it there.
- **The user's goal:** "make the most complicated animations super easy".
  They think in user flows (a finger curling, a flower blooming, a sword
  swing), not in code.
- **Standing rule:** after every change to the add-on, the user checks it in
  their own Blender. So every time:
  - bump `bl_info["version"]`, the guide's title, and the zip name in the
    guide;
  - add any bug you fixed to the guide's "Bugs found and fixed" list;
  - run the tests and ruff;
  - commit, then push to `claude/funny-hypatia-jnendi`;
  - run `python tools/build_zip.py` and send them `dist/RigMoves-<version>.zip`.
- They may upload `.blend` files when something doesn't work. Treat them as
  untrusted:
  - keep each one in its own directory;
  - open it with `bpy.ops.wm.open_mainfile(filepath=..., use_scripts=False)`;
  - run Python with `-I`.
  Reproduce the problem on their file before fixing it.
- Explain results in plain words: what was wrong, what changed, and how to
  check it in Blender. They aren't a programmer.
- Don't open a PR unless they ask. The only branch is
  `claude/funny-hypatia-jnendi` on `NemVe/Blender-addon`.

## Files

| | |
|---|---|
| `rigmoves/__init__.py` | the whole add-on, about 5,500 lines, one file |
| `rigmoves/README.md` | user guide. Keep it in step with what the panel shows |
| `tests/test_rigmoves.py` | 83 end-to-end tests, run headless |
| `tools/build_zip.py` | builds `dist/RigMoves-<version>.zip` from `bl_info` |
| `.claude/hooks/session-start.sh` | installs `bpy==5.2.2` into `.venv` in cloud sessions |
| `CLAUDE.md` | short rules: commands, drivers, style |

**Commands:**

    .venv/bin/python tests/test_rigmoves.py      # all tests, about 6 s
    .venv/bin/python tests/test_rigmoves.py TestFollowers   # one class
    ruff check rigmoves tests tools
    python tools/build_zip.py

**Blender:** the add-on targets 4.4+ and is tested on 5.2.2 as a Python
module. Chromium is available if you ever need to render a picture for the
user. The Cycles CPU renders made earlier were done with a small script that
builds a scene and calls `bpy.ops.render.render(write_still=True)`.

## What the add-on does

1. Select objects (or pose bones), then press **New Move**. Where they stand
   is recorded as **Before**.
2. Move them, then press **Record After**. Optionally add **Steps** in
   between; steps need one Build first.
3. **Build Sliders.** Each loose object gets its own bone in a rig the
   add-on creates. The object is bound to it with an Armature modifier and a
   full-weight vertex group. The poses become keys in an Action, and an
   Action constraint on each bone plays them. A scripted driver drives the
   constraint from one slider per move, either a custom property or a
   viewport handle bone sliding along a rail.

Features, in the order the user asked for them:

| Version | Feature | Where in the code |
|---|---|---|
| 0.10 | Speed per stretch, from -50 (snail) to +50 (lightning) | `timing_points`, `time_curve`: keys on the driver's own F-curve remap time |
| 0.11 | **Ride Along**: other objects copy the leader's move from their own place | `bind_riders`, `rider_turn`, `copy_path`, `follow_leaders` |
| 0.12 | Rider **Lead** -50..+50, and a **Play** slider in the panel for the whole animation | `part_window`, `eval_expression`, `_play_get`/`_play_set` |
| 0.13 | Animate over frames, pivot picker, mirror rider, motion path preview, editable curved path with ends pinned to A and B | `RIGMOVES_OT_animate`; `shift_pivot`/`apply_pivots`; `rider_reflection`; `trace`/`draw_paths`; `make_path_curve`/`bake_curves`/`pin_ends` |
| 0.14 | **Followers**: a Follows dropdown per part, so a part hangs from another, like a finger | `_follows_changed`, `hang`, `apply_parents`, `seen_poses` |
| 0.14.1–0.14.4 | Follower fixes after the user's bug report and two reviews | see the guide's bug list |
| 0.14.3 | Author credit | `bl_info` |

## The model underneath (read before changing any maths)

- **Rest is Before.** A bound object's own transform is its Before. The bone's
  rest (`matrix_local`) stands on the part's pivot at Before.
  `matrix_basis` is the pose. What the mesh shows in the world is
  `W @ C @ W⁻¹ @ O`, where:
  - `W` is the rig's world matrix;
  - `C` is the bone's deformation in armature space,
    `pb.matrix @ bone.matrix_local⁻¹`;
  - `O` is the object's world matrix, which stays at Before.

  Anything that drags `O` off Before is read as a pose by Record (a "drop",
  see `hand_moved`) and then put back. Build always reseats objects on
  Before (`reseat_bound`).
- **The deformation chain:** `C = C_parent @ rest @ basis @ rest⁻¹`
  (`deformation`, `above`). `deformation` takes `fresh` (bones posed but not
  keyed yet), `parents` (a hierarchy about to be made), and a frame that may
  be a function per bone, for delays.
- **Placing a bone:** `pose_bone_at(rig, part, target_world, above)` solves a
  bone's basis so its object lands on a world matrix.
- **Layered actions** (Blender 4.4+): curves live in slot, layer, strip,
  channelbag. Always reach them through `action_bits(move)` and
  `curve_for(bag, path, index)`.
- **Drivers must stay "simple expressions"** so they run with Auto Run
  Python Scripts off, and must stay under 256 characters, or Blender cuts
  them short.
  - Window bounds are written to 4 decimals (`decimal`).
  - `test_drivers_need_no_python` checks the first rule; Build reads the
    expression back to check the second.
  - Speeds don't go in the expression: they're keys on the driver curve.
- **Riders:**
  - A rider's bone is turned from the rider exactly as the leader's bone is
    turned from the leader (`leader_frame`, `standing`, which keeps frames
    right-handed).
  - The rider plays a copy of the leader's channels, conjugated by an
    orthogonal map for Mirror (`rider_turn`, `rider_reflection`).
  - The seat of a mirrored rider sits on the mirrored pivot.
- **Pivots:** a part's bone stands on its pivot. Changing the pivot re-keys
  the location with `loc' = loc − d + R·S·d` (`shift_pivot`), so the
  recorded poses don't change; only the way between them does.
- **Curves:** a Bezier or Poly curve object per part. Its ends are pinned to
  the pivot at Before and After, and it's sampled by arc length (40
  samples).
  - Write points with `foreach_set` (`points_of`/`set_points`). Setting
    `co` alone makes Blender recompute aligned handles.
  - A curved part can't follow. Followers can't be curved.
- **Followers:**
  - The follower's bone hangs from the leader's bone. Changing the parent
    re-keys every pose frame so world poses are kept:
    `B_new = rest⁻¹ @ carry⁻¹ @ kept @ rest` (`apply_parents`).
  - A part that never moved and has no After of its own (`stands_still`)
    rides along instead, as identity under its new parent.
  - Newly bound bones keep only their own key frames.
  - The follower's object also hangs from the leader's object, through
    `hang` and `hang_objects` and the `FOLLOW_MARK` custom property. That
    way, dragging the leader in object mode carries the chain on screen.
  - Bone hierarchy changes wait for Build. The panel says so in red
    (`parent_pending`).
- **Reading a drag** (`seen_poses`): with a finger shown bent, object
  parenting reaches a follower before its own bone bend, so the screen
  shears. Record reconstructs the intended pose parents first:
  - each part keeps `carry` (how far it was moved as an object) and
    `change` (how far it was moved as seen);
  - a follower's intended pose is `change[leader] @ shown @ own`;
  - a follower that was only carried, with its bone already hung, isn't a
    drop. It keeps its own keys: the "kept" rule.
- **The "kept" rule in Record:** only parts that were touched are keyed.
  Untouched, already-recorded parts keep their keys. Keying everything would
  flatten finished work.
- **Show (the eye):** pauses the sliders, reseats objects, and poses the
  bones at the frame (`pose_at`). It then uses `ride_shown` and
  `shown_places` for followers that aren't built yet, and puts objects in
  place parents first (`stand_parts`).
- **Set Pivot, Curve the Path, Straighten, Mirror, Ride Along and taking a
  rider out all run a Build.** They refuse while a drag is unrecorded
  (`keeps_drags`). Remember this when writing tests: a pivot set on new
  parts binds them.

## Code style (match it)

- Comments say why, in plain prose, without jargon. Docstrings explain
  intent.
- Use `str.format`, never f-strings.
- Reports go in `data.report` and `self.report`. The panel shows the last
  one, so it must say what happened and what to do next.
- Name helpers with plain words, as the existing ones do: `hang`,
  `stand_parts`, `seen_poses`, `recorded`.

## How to test a change

- Tests press the panel's operators on real cubes and measure the
  **evaluated, deformed vertices** (`world_points`, `drift`, `centre`), never
  object transforms.
- `drive(move, share)` slides the handle. `TOLERANCE = 1e-4`.
- Every bug fix gets a regression test that fails on the commit before.
  Check that by copying the old `rigmoves/__init__.py` into a temporary
  package and running the test against it.
- Useful fixtures:
  - `TestFollowers`: a three-segment finger, knuckles at x 0, 1 and 2,
    pivots on the knuckles. Helpers `bent`, `bent_by`, `check_places`,
    `built_curl`, `turn_the_base`.
  - `TestFollowersAdded`: parts added to a built move.
  - `TestRiders`, `TestMirror`, `TestPivot`, `TestCurve`: one per feature.
- Earlier sessions reviewed each version with a workflow: one reviewer per
  lens (regressions, user flows), then a skeptic per finding who reproduced
  it headless in Blender. That review found 25, 23 and 9 real bugs in
  successive versions. Run one after any substantial feature.

## Open items

1. **Check the 0.14.2 regression tests on 0.14.1.** This hasn't been done.
   Run these against the add-on from commit `90ec17b` and confirm they fail
   there:
   - in `TestFollowers`: `test_turning_the_base_*`,
     `test_followers_listed_first_*` and `test_a_follower_not_hung_*`;
   - every test in `TestFollowersAdded`.
2. **No independent review of 0.14.2–0.14.4 yet.**
3. **Known rough edges** (listed in the guide):
   - Dragging the base of a finger shown bent shears it on screen until
     Record. Record gets it right.
   - Posing before the Build that a Follows change waits for records what
     is seen, not the kept joint.
   - Also see the guide's full list: one bone per object, one combined
     control per move, and others.

## Feature ideas (not built; ask the user before choosing)

These follow the "super easy complicated animation" goal:

- **Stagger:** give many riders or followers evenly spread Leads in one
  click. A flower's petals would open one after another.
- **Overshoot and settle:** an ease that goes past After and springs back.
  It has to fit within the driver limits, so it would be keys on the driver
  curve, like Speed.
- **Loop or ping-pong** playback for Animate.
- **Copy a move to other parts**, or save and load a move as a preset.
- **Follower curl presets:** bend every joint of a chain by one slider, so
  the user records only the first joint.
- **A soft-body or jiggle follow-through** on followers, done as a delay
  plus overshoot per joint.
- **A "reset to Play 0" button** before posing, which avoids the posed-drag
  shear.

When adding a feature:
- put it on the panel where the user's eye already is;
- write its section in the guide;
- add tests that measure the deformed mesh;
- run a review workflow;
- then send the zip.
