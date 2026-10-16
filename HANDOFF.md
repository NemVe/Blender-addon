# CopyThat (formerly RigMoves) handoff: everything a new session needs

**Renamed in 0.15.0.** The add-on is now called CopyThat: the name in
Preferences, the sidebar tab and panel, new rigs ("CopyThat Rig"), the
zip (`dist/CopyThat-<version>.zip`) and the docs. On purpose, these did
not change, so files made with RigMoves keep working:
- the package folder `rigmoves`;
- the `rigmoves.*` operator ids and the `rigmoves` properties;
- the markers stored in files: `CONSTRAINT` ("RigMoves: "), `PART_MARK`,
  `FOLLOW_MARK`, `RAIL`, the action and modifier names.
Don't rename these. Older rigs are still called "RigMoves Rig";
`rig_label` handles both names.

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
  - run `python tools/build_zip.py` and send them `dist/CopyThat-<version>.zip`.
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
| `rigmoves/__init__.py` | the whole add-on, about 8,100 lines, one file |
| `rigmoves/README.md` | user guide. Keep it in step with what the panel shows |
| `tests/test_rigmoves.py` | 334 end-to-end tests, run headless |
| `tools/build_zip.py` | builds `dist/CopyThat-<version>.zip` from `bl_info` |
| `.claude/hooks/session-start.sh` | installs `bpy==5.2.2` into `.venv` in cloud sessions |
| `CLAUDE.md` | short rules: commands, drivers, style |

**Commands:**

    .venv/bin/python tests/test_rigmoves.py      # all tests, about 16 s
    .venv/bin/python tests/test_rigmoves.py TestFollowers   # one class
    ruff check rigmoves tests tools
    python tools/build_zip.py

On the user's Windows PC (since 0.16) the venv is `.venv/Scripts/python.exe`
with ruff in `.venv/Scripts/ruff.exe`; make it with `py -3.13 -m venv .venv`
and `pip install bpy==5.2.2 ruff`. Their checkout is a clone in
`Desktop\AutoRigger\Moves\Blender-addon` with `core.autocrlf=false`, so files
and zips keep LF line endings. Their Blender is 5.2.1.

**Blender:** the add-on targets 4.5+ (4.4 has no Replace mode on the Action
constraint) and is tested headless on 4.5.14 LTS, 5.0.1 and 5.2.1, run all
three before a release (`CLAUDE.md` has the paths), and on 5.2.2 as a Python
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
| 0.15.0 | Renamed RigMoves to CopyThat | see the top of this file |
| 0.16.0 | **Copies of a whole finger** ride along joint for joint; a follower can lead riders; each part moved by its own bone only; a Ride Along crash fixed | `chain_of`, `match_copies`, `rides_on`, `riding_on`, `copy_root`, `rider_holder`, `holder_bone`; `own_binding`, `heal_bindings` |
| 0.17.0 | **Spread**: Leads or Delays filled in one go, by ring, distance, axis, chain or at random | `spread_shares`, `spread_values`, `ring_angles`, `ring_normal`, `part_spot`/`rider_spot`, `RIGMOVES_OT_spread` |
| 0.17.0 | **Make Chain**: Follows down a line, nearest neighbour from the active part; says which copied joints stop riding joint for joint | `chain_order`, `RIGMOVES_OT_make_chain` |
| 0.17.0 | **Curl**: the first joint's bend repeated down every follower, each joint `factor` times the one before | `bend_of`, `quaternion_power`, `shows_a_pose`, `RIGMOVES_OT_curl` |
| 0.17.0 | **Ring**: a part and the parts below it made into a ring of riders, through 0.16's Ride Along | `copy_for_ring`, `take_riders_out`, `RIGMOVES_OT_ring` |
| 0.17.0 | Merge of the two lines of work: Spread and Ring work on 0.16's copy roots and chains; one binding fix (`own_binding`) and one leader read-back fix | see "The four tools of 0.17" |
| 0.17.1 | Make Chain's order follows how joints are built (far end of the part before), not the nearest pivot, so a folded leaf chains right; plurals in the new tools' reports | `chain_order`, `touching_distance`, `counted` |
| 0.18.0 | **Ring uses what is already modelled**: a Use choice (Make copies, Use what's there, Fill the gaps - the default); objects that are exact copies of the part's mesh are taken up, stood on their frame if they are not on it | `find_standing`, `standing_candidates`, `reframe`, `put_back`, `RING_USES`, `RIGMOVES_OT_ring` |
| 0.18.1 | Review of 0.18.0, fourteen findings, mostly data safety: Ring takes up or re-frames an object only when provably safe (no keys/drivers, not linked, selectable, no frame-reading constraint/modifier/dependent, result compared and put back exactly); matching by point set (mirrored halves, unturned cubes); Fill never copies onto anything standing in a place, and is refused when copies stand near the ring on none of its places; Spread's default step sized to fit | `standing_pool`, `why_not_taken`, `Joint`/`Seen`/`Slot`, `fit_error`, `find_standing`, `reframe_blocker`, `look_of`, `looks_the_same`, `signed_volume`, `settle`, `sized_step` |
| 0.18.0 | **Spread by Step**: Start and Step for each place in the order (default, -10 for Leads and 0.1 for Delays), ties share a place; Range is the old First and Last; Ring's Lead step is the same | `spread_keys`, `tied_ranks`, `spread_ranks`, `spread_put`, `SPREAD_BY`, `RIGMOVES_OT_spread` |
| 0.18.2 | **Runs on Blender 4.5 LTS, 5.0 and 5.2; needs 4.5 or newer.** 4.4 has no Replace mode on the Action constraint, so every Build failed there. On 4.5 and 5.0 a healed copy was not redrawn (the mesh is tagged after a group is removed). On 4.4 and 4.5 every action curve was read twice (curves are read from the channelbags only). Guard test: the manifest and `bl_info` name one Blender and one version | `own_binding`, `own_transform_curves`, `rig_own_curves`, `action_curve`, `drop_empty_action`, `bl_info["blender"]`, `blender_manifest.toml`, `TestManifest` |
| 0.18.3 | **The Riding along list reads at the sidebar's usual width** (found in a real 5.2.1 window, sidebar at its default 280 px). The Spread... button of the Riding along and Timing headers sits in a right-aligned sub-row: it took half the header, and the count was cut ("Riding alon…"). A rider's name is cut from the front to the room its row has, measured with `blf` in the panel's font, so Ring's copy numbers show: it was `short(name, 13)`, which Blender then cut at the end as well, seven rows of "…ter Lead…". Tests draw the panel for a sidebar of a given width (`Sidebar`, `drawn_panel`, and the logging layout now notes labels and alignments) | `fitted`, `_draw_move`, `TestNamesBesideControls` |

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
  `curve_for(bag, path, index)`. Never read `action.fcurves` as well: 4.4 and
  4.5 still answer it with the first slot's curves again, so every curve was
  counted twice there (5.0 removed it).
- **An object's own keys are its own slot's** (0.19): `slot_curves(action, slot)`
  reads the one channelbag of a slot, `own_transform_curves(obj)` the slot in
  `obj.animation_data.action_slot` (none when it has no slot: it plays nothing).
  An Alt+D twin plays the same action AND slot; another object can have a slot of
  its own in the same action. `own_action(obj)` runs before keys are lifted: if any
  other ID uses the action (`bpy.data.user_map`) the object gets `action.copy()`,
  without the other slots and without a fake user, and the same slot, and the keys
  come out of the copy only (`drop_empty_action` then drops the empty copy).
- **Motion Build cannot lift** (0.19): `fighting_parts(data)` names the parts whose
  transform an unmuted NLA strip (`moved_by_nla`: the strip's own slot, tracks muted
  or put aside by a solo skipped, `use_nla` off skipped, meta strips followed) or an
  unmuted driver (`moved_by_driver`) works. They are the user's work: the panel's
  box (`_draw_own_keys`) says what to do, with no Lift button for them, Build adds
  `fighting_words` to its report and is a WARNING while any are left, and
  `clear_autokey` / Lift Those Keyframes never touch them. `has_own_motion` (Ring's
  "may it be taken up") is the wider test: any NLA track at all.
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
- **Copies of a chain (0.16):**
  - Ride Along on any part of a follower chain matches the selected
    newcomers to the chain joint for joint (`match_copies`): seeded from one
    (object, joint) pair, the chain is carried over joint by joint
    (`carried_to`, using `body`: facing with the mirror sign kept, mesh
    middle, size) and the nearest object to where each next joint lands is
    taken. Fullest copies first, then least distance. Leftovers ride the
    clicked part alone, as riders always did.
  - Each copy joint is an ordinary rider with `leader` = its joint, plus
    `rides_on` = the rider copying the joint before it. `riding_on` checks
    that link is still valid (the up-rider's leader is this leader's
    `follows`); a stale one falls back.
  - A rider's bone hangs from `rider_holder`: the valid up-rider, else the
    part its leader follows (a second claw hangs from the arm), else Root.
    `bind_riders` re-hangs bones whose holder changed, so a leader may now
    be given a Follows.
  - A copy plays by its first joint's (`copy_root`) Lead and Mirror. Mirror is one
    plane for the copy (`copy_mirror`): the first joint's own axis carried into
    each joint's leader frame, so a segment rolled about its length does not
    zigzag. `rider_turn`, the mirrored seat in `bind_riders` and `rider_spot` all
    read it through `rider_reflection`. Test a mirrored copy's *motion* (its
    deformation is the reflected one applied to where it stands): a cube rolled
    35 degrees is not its own mirror image, so its mesh is not the reflected one. Lead
    shifts every joint by the same amount (`base_window`), so the joints
    stay in step. The panel lists copy roots only, with `+N`; `drop_rider`
    takes a rider and everything riding on it (`copy_of`).
  - `ride_on_existing` and `adopt_riders` link joints added in a later press
    to the copy they belong to, in either order.
- **One bone per object (0.16):** vertex groups live on the *mesh* (Blender
  3.0+), so linked duplicates share them. `own_binding` gives a bound object
  its own mesh, removes groups named after other parts' bones (`PART_MARK`)
  and dead "RigMoves" Armature modifiers. `bind_object` calls it, and
  `heal_bindings` runs at the end of every Build, after every bone exists - a
  stale group only starts to pull when a bone of its name is made.
- **Show (the eye):** pauses the sliders, reseats objects, and poses the
  bones at the frame (`pose_at`). It then uses `ride_shown` and
  `shown_places` for followers that aren't built yet, and puts objects in
  place parents first (`stand_parts`).
- **Set Pivot, Curve the Path, Straighten, Mirror, Ride Along and taking a
  rider out all run a Build.** They refuse while a drag is unrecorded
  (`keeps_drags`). Remember this when writing tests: a pivot set on new
  parts binds them.

## The four tools of 0.17 (read before changing them)

The goal was "make building any multi-part animation as fast as possible".
The tools are generic (a finger, a fan, dominoes, a tentacle), not made for
the user's flower. Each is an operator with a button where the eye already
is: `Spread...` in the headers of Riding along and Timing, `Make Chain` and
`Curl` at the top of Follows, `Ring...` in the move's body under the path
buttons. Each refuses in words, reports what it did in `data.report`, and is
`REGISTER, UNDO`.

- **Spread (0.18 added By: Step or Range).** `spread_groups` says what is acted on: riders per leader for
  Leads, the Timing list for Delays - all of them by default, whatever the last
  tool left selected, and the selected ones (`held`) only with `only_selected`.
  Ring leaves its copies selected and Curl its first joint, so going by the
  selection reached part of a flower or a tentacle and said it had worked.
  `spread_keys` is the number each order sorts by (angle, distance, place along
  the axis, depth). By Range `spread_shares` scales it to 0..1 and `spread_values`
  writes First to Last. By Step (the default) `spread_ranks` gives each part its
  place in the order, parts the same to within a ten-thousandth of the spread
  (`tied_ranks`) sharing one, the chain's depth as it is, Random a seeded shuffle;
  a Lead's leader is place 0 so its riders start at 1, a Delay's first part is 0;
  the value is Start + Step x place. Both end in `spread_put`, which rounds Leads,
  holds both to the property limits and says how many were held.
  `step` has a registered default of 0; when it was not set (a script gave none,
  or `invoke` is about to) the step is `sized_step`: -10 / 0.1, less if the top
  place would pass 40 of 50 (Lead) or 0.9 of 0.99 (Delay). `invoke` also turns
  Both ways on for Leads around a ring when it was not set; `execute` does not
  (scripts keep the literal default). Ring's `lead_step` stays 0 unless typed:
  it is SKIP_SAVE (0.19) - Blender restores every property of an operator that is
  not, on the next invoke, so the outer petals' step reached the leaf's dialog -
  while Use, Count, Round, About and Linked copies are remembered on purpose.
  Blender stores the last use only when a dialog's OK runs the operator, not for a
  script's call (`window_manager.operator_properties_last` stays at the defaults
  headless), so the tests read the `is_skip_save` flag and a real window shows it.
  **The dialog keeps the step sized** (0.19): `invoke` writes it and sets the
  hidden SKIP_SAVE `sizing` flag; the `update=` callback `_spread_changed` on Order,
  By, Both ways, Only the selected, Axis and Seed sizes it again (`sized_for`, which
  the operator's `sized` calls too) while `sizing` is on, and `_step_typed` on Step
  turns it off - unless the write is ours (`SIZING["ours"]`). Blender calls these
  with `self` = the operator's PROPERTIES (no methods, no `plan`), and also when a
  script passes the settings, which then leave `sizing` off and are untouched.
  Blender applies a script's keywords in the order the properties are DEFINED, not
  written: `sizing` is defined before the settings it follows, and a Step passed
  with them is applied after it. Both ways and Only the selected are SKIP_SAVE,
  or Blender restores them (as "set") on the next invoke.
  Writes set `WRITING["many"]` so `_timing_changed` skips, and the caller runs
  `refresh_drivers` once; a built move plays the new values with no Build.
  - Leads go to *copy roots* (`copy_root`): a copied finger has one Lead, its
    first joint's, so that is what is spread, and a selected inner joint selects
    its copy.
  - A part's place is `part_spot`: its pivot at Before. A rider's pivot is its
    leader's carried over (`rider_spot`, the same maths as `bind_riders`). Using
    the rider's own origin put the leader's hinge on a different ring from the
    riders and the Leads came out lopsided.
  - If every pivot is the same point (a fan's blades about the hub), `spots_of`
    uses each part's middle. "The same point" is relative to how far apart the
    middles are (float rounding grows with the distance from the origin; a fixed
    1e-5 sorted the noise for hubs 45+ units out).
  - Around a ring: the plane is the SVD best fit (`ring_normal`, numpy), the
    sign picked so the answer is stable. The ring's centre is `circle_centre`, a
    least-squares circle in that plane through the *targets'* spots when there
    are three or more - the reference may be the hub, and an average of an arc is
    not its centre - else the average of all points, and also when the fit is ill
    conditioned. A reference sitting on the middle has no direction, so the first
    target gives it.
- **Make Chain** sets `part.follows` link by link, so `_follows_changed` does all
  the validating. The order is `chain_order`: from the part the chain has got to,
  among the unvisited parts whose *pivot touches its mesh* (`touching_distance`: a
  BVH tree of the mesh at Before, surface distance within 5% of the part's bounding
  diagonal), the one whose pivot is farthest from the part's own pivot - a joint is
  at the far end of the part before it; else the nearest pivot (`spots_of`). Nearest
  alone chains a leaf folded in pleats as 1 > 3 > 2: the third pivot is back by the
  first's. The flower's leaf is the real case. The chain stops at the first refusal and keeps what it made.
  A part that leads riders may be chained (0.16 allowed it). It first clears the
  links the chosen parts have to one another - kept, they refuse a chain made from
  the other end as a loop - and puts them back if the chain is refused at its first
  link, and puts back the links of the parts it never reached when it stops part
  way (only `linked` - the root included - counts as reached). It reports the old
  links it replaced, and how many copied joints `riding_on` no longer pairs, since
  a changed Follows undoes the pairing; those copies are riders already, so the
  advice is to take them out (their x) before Ride Along again.
- **Curl.** Part F following Q is put at `carried(Q) @ D_F @ B_F`, where
  `carried(Q) = W_Q B_Q^-1` and `D_F` is the root's bend (a quaternion in its own
  frame) raised to `factor**k`, applied about F's pivot in F's own frame
  *without scale*. The design wrote it as `W_Q B_Q^-1 B_F bend_F` with the bend
  in local axes, which shears any object that has non-uniform scale (all the
  test segments do). Parents first, a view-layer update after each.
  - Each joint is `factor` times the one before it: 20, 10, 5, 2.5, 1.25 at
    0.5 (`k` is the depth below the root, so the first follower already has
    `factor`). Chains with copies riding them say to Build after Record.
  - It refuses unless every chain bone shows no pose (`shows_a_pose`, the same
    read as Record), because `seen_poses` is exact only then. A Build is what
    clears a pose the eye left.
  - Followers whose new bend is none read as "only carried" in Record and keep
    their old keys (factor 0, which straightens everything below the root). Not
    handled.
  - A part whose object is gone (`carried_by` returns None): a lost tip is left
    out and reported; a lost part that parts with objects hang from refuses.
- **Ring.** Everything is checked in `plan` before anything is made, so a refusal
  leaves nothing. Copies are made with `copy_for_ring`, placed at
  `as_matrix(part.before)` turned about the axis (world Z by default: the cursor
  takes the view's rotation with Shift+right-click, so its Z tilts rings), then the
  existing `ride_along` runs (a Build when the move is built).
  - The part and the parts below it (`chain_below`) are copied, never the parts it
    follows. `ride_along` is given `pairing`, a JSON list of `{joint: copy}` for
    each whole copy, in place of `match_copies`: a copy of joints 2-3 of a finger
    of alike segments looks just like a copy of joints 1-2, and the matching, which
    is for objects the user made, took it for that. A blade that follows a hub is
    ringed alone and its copies hang from the hub's bone (`rider_holder`); a copy of
    a middle joint hangs from the joint above it.
  - Copies are numbered from 2 past every name in use, objects *and* parts of every
    rig (`names_in_use`): the parts of deleted copies stay in the move, and a new
    object under such a name is "already known" to `newcomers` and was never
    bound. A place already holding a rider of the part (its object still there) is
    skipped. After `ride_along` every copy must be a rider of the joint it was
    copied from, or `take_riders_out` (the part of `drop_rider` that unbinds and
    removes) takes the lot back and the ring is refused.
  - Leads are spread over the copy roots made now only (the ones taken up too),
    so an earlier ring keeps its own; `lead_step` is the Spread's Step with the
    same ranks, around both ways from the part. Never read a part held from
    before an `.add()` afterwards: `first_joint` is read first for that reason.
  - **Use** (0.18, `RING_USES`, default `FILL`; the safety rules are 0.18.1).
    Principle: an object is taken up or re-framed ONLY when that is provably safe,
    otherwise it is left as it is and named in "Left out". `standing_pool` lists
    every mesh in the scene with `why_not_taken` (in a move; library or not
    editable - object or mesh; keys, transform drivers or NLA of its own
    (`has_own_motion`); not in the view layer; hidden; and the `select_set`
    probe, because a collection's `hide_select` is not on the object). Those still
    take part in the survey, they just cannot be taken.
    `find_standing` fits each joint in each free place (`Slot`) against each
    object with its vertex count (`Seen`, lazy points): `fit_error` is vertex
    for vertex first (cheap, what copies satisfy), then as a point SET (two
    `KDTree`s, nearest distance both ways within 2% of the joint's bounding
    diagonal) - so Ctrl+M halves and unturned cubes fit and an asymmetric mirror
    image does not. One object per place, best fit first, a place `placed` only
    with every joint; `partial` places and any place with anything standing in it
    (`occupied`: ANY mesh, hidden or not, in a move or not, any vertex count, whose
    world box centre is within 0.25 x the joint's reach of the place's) are left
    alone, in Fill too - nothing is copied onto anything. `off` lists copies of the
    part (same local mesh in order AND same size, `Seen.like`; objects already in a
    move excluded) standing on no place; the operator refuses Fill when any is within
    1.5 x the ring's radius of the axis and the part's height (a wrong 3D cursor or
    Count), and appends it as a note in Use what's there. `left` is sorted nearest
    place first and only says "off the ring" when it is. `stacked` (0.19) lists the
    copies of the first joint standing on the part's OWN place (a `Slot` with the
    identity turn: a Shift+D cancelled with a right-click): not `off`, not in
    `left`, and `stacked_words` is Fill's refusal and Use what's there's note. Use
    what's there says "Fill the gaps would copy the part there" only when Fill
    would not be refused (no note).
    Before any change `reframe_blocker` refuses constraints, instancing, particles,
    a vertex/bone parent, any dependent in `bpy.data.user_map` but an OBJECT-parented
    child (and that child must have no `has_own_motion`: its keys, driver or NLA
    would rewrite the transform `reframe` holds it by - "has a child with keys or
    drivers of its own ('Bee')"), modifiers except Subsurf/Triangulate/Edge Split/Weighted Normal/an
    Armature of another rig (Bevel/Solidify only when both scales are 1), and a
    mirrored frame with custom normals. Then `reframe` (a NEW mesh from `old.copy()`
    is transformed - exact rollback by swapping `old` back, `put_back`; `settle`
    removes each distinct old mesh ONCE - Alt+D petals share one, found by
    `as_pointer()` before any removal, never touching a removed datablock - when
    nothing uses it, and names the new ones after it) and one `view_layer.update()`:
    `look_of` (evaluated world vertices and winding as shown, i.e. times the sign of
    the frame's determinant) must equal the look before to 1e-5 of the part's size,
    and the signed volume of the new mesh must have the leader's sign; otherwise the
    whole place is put back and left alone. A mirrored frame (negative determinant)
    gets its faces turned over (`Mesh.transform` does not). Only OBJECT-parented
    children are held in the world: `matrix_world` cannot be solved against a vertex
    parent. The whole thing is inside the operator, so Ctrl+Z restores meshes too.
    Everything of `execute` after Ride Along is in a `try` (0.19): anything that
    raises goes through `take_back` - the riders out, `put_back`, the copies
    discarded - and says "Ring could not be finished: <reason>. Nothing was
    changed.", because a Python error in an operator leaves what it did with no
    undo step. `settle` is the last call in it.
    Taken objects and copies share the `told` pairing. `bpy.data.objects.remove`
    leaves `None` in `view_layer.objects` (and in `scene.objects`) until an update:
    `standing_pool` skips them. Not checked (rough edge): materials using Object or
    Generated texture coordinates.
  - Vertex group names live on the mesh, so linked copies share groups with
    the leader. `own_binding` (0.16, called by `bind_object`) gives a bound
    object its own mesh and drops groups for other parts' bones; Build heals
    older files. Both lines wrote this fix; the merge kept this one, with one
    refinement from the other (a mesh whose only other user is a fake user is
    not shared).
  - Never keep a collection item across `.add()`: it can move all the parts in
    memory, and the stale pointer reads as empty. `ride_along` did; both lines
    fixed it, and `TestRiders.test_the_ninth_part_of_a_move_keeps_its_leader`
    fails deterministically on the old code.

Test helpers added: `ring_places` (a tilted ring), `turn_about`, `eased` (a bone
turn is blended as a quaternion between keys, so its angle is even only at the
ends and middle - check off-centre shares with it), `Sketch` and
`drawn_buttons()` (runs the panel's draw code against a layout that logs the
buttons, so placement is tested), and `undo_push`/`undo_once` (headless
Blender has no undo history until asked: push a step before and after, then
undo with a window override).

## Code style (match it)

- Comments say why, in plain prose, without jargon. Docstrings explain
  intent.
- Use `str.format`, never f-strings.
- Reports go in `data.report` and `self.report`. The panel shows the last
  one, so it must say what happened and what to do next.
- Name helpers with plain words, as the existing ones do: `hang`,
  `stand_parts`, `seen_poses`, `recorded`.
- Never hold a part (or any collection item) across `.add()` on its
  collection: Blender may move the items, and the old reference reads freed
  memory. 0.15's Ride Along read its leader that way and crashed Blender in
  five runs out of eight with six riders. Work things out first, keep names.

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
  - `TestChainRiders`: a tapering finger (lengths 1, 0.8, 0.6) curled 30
    degrees, and copies placed by a matrix (`made`, `check_copy`).
  - `TestCopiedParts`: Shift+D and Alt+D copies of bound parts.
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
2. **Reviewed, partly.** The four tools of 0.17.0 were reviewed on the code before
   the merge with 0.16.0 (two lenses, each finding reproduced headless): twelve
   findings, all fixed on the merged code and listed in the guide's bug list. The
   merged code itself has not been reviewed again, and 0.14.2-0.14.4 never was.
   Run the review workflow on the whole.
3. **The new buttons have not been seen in a real window.** Their placement is
   tested against a logging layout, not drawn: look at the `Spread...` button in
   the panel headers, which are narrow, and at the `Ring...` row. Also the 0.18
   dialogs: Ring's three-way **Use** (drawn expanded, in a column of its own) and
   Spread's **By** (expanded) with its Start/Step or First/Last.
4. **Known rough edges** (listed in the guide):
   - Dragging the base of a finger shown bent shears it on screen until
     Record. Record gets it right.
   - Posing before the Build that a Follows change waits for records what
     is seen, not the kept joint.
   - Also see the guide's full list: one bone per object, one combined
     control per move, and others.

## Feature ideas (not built; ask the user before choosing)

These follow the "super easy complicated animation" goal:

- **Overshoot and settle:** an ease that goes past After and springs back.
  It has to fit within the driver limits, so it would be keys on the driver
  curve, like Speed.
- **Loop or ping-pong** playback for Animate.
- **Copy a move to other parts**, or save and load a move as a preset.
- **A soft-body or jiggle follow-through** on followers, done as a delay
  plus overshoot per joint.
- **A "reset to Play 0" button** before posing, which avoids the posed-drag
  shear. Curl asks for rest, and a paused rig needs a Build to get there, so
  this would help it too.
- **Curl's factor on the panel**, and a Curl that also works from a posed rig.

When adding a feature:
- put it on the panel where the user's eye already is;
- write its section in the guide;
- add tests that measure the deformed mesh;
- run a review workflow;
- then send the zip.
