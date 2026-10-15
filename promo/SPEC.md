# CopyThat promo video - production spec

The add-on is CopyThat (repository `/home/user/Blender-addon`: add-on in
`rigmoves/__init__.py`, guide in `rigmoves/README.md`, tests in
`tests/test_rigmoves.py`), by NemVe3D (https://creators.sa/nemve). Read the
guide to learn the features. The tests show how to drive the add-on from
Python:

- `bpy.ops.rigmoves.new_move()`, `record(index, which)`, `build()`,
  `ride_along(...)`, `set_pivot(index, kind)`, `curve_path(index)`,
  `animate(...)`, and so on;
- the Play value is on the move (see `_play_set` and the `drive()` helper
  in the tests);
- selection: the first object passed to the tests' `select()` is the
  active one.

Blender 5.2.2 runs headless here as a Python module:
`/home/user/Blender-addon/.venv/bin/python script.py`. Register the add-on
with `sys.path.insert(0, "/home/user/Blender-addon"); import rigmoves;
rigmoves.register()`. The user runs Blender 4.4 or later with CopyThat 0.15.0
installed.

All promo work goes under
`/tmp/claude-0/-home-user-Blender-addon/b9831a8c-0477-5b8e-9806-eecafd2be0a8/scratchpad/promo/`
(called PROMO below). Never modify `/home/user/Blender-addon`.

## The video (1920x1080, 30 fps, about 75 s)

1. **Title** (3 s), made here: the CopyThat wordmark, "Record a move. Get a
   slider.", and "by NemVe3D".
2. **Scenes 1-4, recorded by the user** in their real Blender. A script we
   give them builds each demo and plays it on its own, with captions drawn in
   the viewport:
   1. **One cube:** New Move, the cube glides up and turns, Record After,
      Build Sliders, then Play slides 0 → 1 → 0.
   2. **Two cubes:** the leader hops and turns. The second cube, standing
      turned 90°, rides along from its own place, with Lead +30 so it goes
      first. Play.
   3. **Curve:** a cube goes from A to B, and a wall stands in the way. The
      straight path goes through the wall (shown with Paths). Curve the Path,
      edit mode, lift the curve's middle over the wall, Build. Play: it
      arcs over.
   4. **Rig something real:** the mechanical flower, set up quickly (see
      below). Build, Animate, then Play: it blooms in the viewport, seen
      through the promo camera.
3. **Outro** (about 7 s plus a 3 s end card), rendered here in Cycles: the
   same flower, the same CopyThat animation, the same camera at frame 1, so
   the viewport dissolves straight into the cinematic render. It ends on the
   card: the CopyThat wordmark, the tagline, and "by NemVe3D ·
   creators.sa/nemve".

## The mechanical flower (shared code: PROMO/flower/flower.py)

One module, used both by the user's script and by the outro render, so they
match exactly. It must work on Blender 4.4+ with no add-ons but CopyThat.

`build_flower(collection)` makes the geometry and materials with the flower
**closed** (the bud), and returns the objects in named groups.
`rig_flower(...)` then records it with CopyThat, using only the add-on's
operators, as a user would:

- **Outer ring:** 8 petals. Each petal's origin sits on its hinge at the base,
  so it turns about it. The bud is nearly upright with the tips meeting above
  the core; open, each petal leans out about 75°. One leader petal is
  recorded Before (closed) and After (open). The other 7 Ride Along with it,
  each copying the move from its own place, with Leads staggered so a wave
  runs round the ring (for example 0, -6, -12 … -42).
- **Inner ring:** 6 petals, offset by half a petal, opening less (about 45°)
  and later. One inner leader is a part of the same move with a Timing
  delay; the other 5 ride along with it, with staggered Leads.
- **Core:** a cluster of stamens (small capsules on a dome) that rises about
  15% of the flower's height and turns 60° as it opens, with a delay. Its
  glow can be animated by ordinary keyframes in the outro only (not part of
  the add-on demo).
- **Leaves:** two leaves on the stem, each a chain of 3 segments with
  **Follows** (segment 2 follows 1, 3 follows 2). Pivots sit on the joints
  (3D cursor, Pivot: Cursor). They unfurl from curled to open.
- **Look:** a premium product render. Outer petals in satin champagne-gold
  metal (about #C9A76A, metallic 1, roughness 0.25-0.3) with a slight
  anisotropic sheen if cheap. Inner petals pearlescent (#EEE6DA, coat). The
  core glows warm (#FFB86B emission, rising as it opens). The stem and leaves
  are graphite metal. A black glossy pedestal with a thin gold ring. Petals
  are real modelled shapes: spoon-curved, tapered, with thickness and soft
  bevels or subdivision. No raw planes or cubes.
- **Viewport look** (the user's recording, Solid mode): set each object's
  viewport display colour to match its material, so it reads well in Solid
  shading.

## Outro render (made here)

- A dark studio: a near-black curved cyclorama, a warm key softbox, cool rim
  lights, a soft fill, and subtle floor reflections.
- Camera "Promo Camera": a slow push-in plus about 20° of orbit over the
  bloom, with depth of field focused on the core. The add-on's Animate keys
  the control over the bloom's frames (about 150), then it holds.
- Cycles CPU with OpenImageDenoise. Pick samples so a 1920x1080 frame takes
  about 25 s or less on 4 CPUs. Benchmark first.
- Frames go to PROMO/outro/frames/####.png. Render stills for review
  BEFORE any full sequence: frames 1, 75 and 150 at full resolution.

## The user's in-Blender demo script (PROMO/user_script/copythat_promo.py)

One file, run from Blender's Scripting tab with CopyThat 0.15.0 enabled. It
embeds the flower code.

- It never deletes or changes the user's data. Each demo is a new scene
  ("CopyThat Promo 1 - One cube", and so on), switched to in the window. It
  refuses with a clear message if CopyThat isn't enabled.
- On start: a 5-second countdown in the viewport, so the user can start
  recording. Then it plays the chosen scenes (`SCENES = [1, 2, 3, 4]` at the
  top) one after another, with a short pause between. Everything runs on
  `bpy.app.timers`, so the real UI stays live and is recorded. Operators run
  inside `context.temp_override(window, area, region)` of the 3D viewport.
- The view: the sidebar (N panel) open on the **CopyThat** tab, Solid
  shading with studio light, cavity and shadows, a pleasant 3/4 view per
  scene. Scene 4 ends looking through "Promo Camera", whose frame-1 view is
  the outro's.
- Moves look like a person doing them: objects glide (eased tweens at about
  60 Hz) to their After pose, the Play value slides smoothly, and the curve's
  middle points lift visibly in edit mode.
- Captions, drawn with `blf`/`gpu` in the viewport (they can be switched off
  with `CAPTIONS = True`):
  - a chip top-left with the scene ("1 · One cube");
  - a lower-third step line, for example "New Move — where it stands is
    Before", "Record After", "Build Sliders — one slider plays it",
    "Ride Along — copies the move from its own place", "Lead +30 — goes
    first", "Curve the Path — the ends stay on A and B".

  Keep it short and clean: white text on a dark translucent bar, one accent
  colour.
- Pacing: each scene is about 12-16 s on screen. Scene 4 can move faster (a
  montage of steps), then it plays the full bloom.
- Testability: the scene steps are a list of plain functions that a headless
  harness can call one after another, with tweens jumped to their end. That
  harness (PROMO/user_script/test_headless.py) runs all four scenes against
  the add-on here and checks that each Build succeeds and that Play moves
  the parts.

## Contract between the flower code and the user script (binding)

**Scenes are generators.** A scene is a generator function that yields
action tuples. The in-Blender engine plays them live on timers. A headless
runner applies them at once: a tween jumps to its end, and a wait is
skipped.

| Action | What it does |
|---|---|
| `("caption", chip, line)` | Sets the top-left chip and the lower-third line. `None` keeps a value; `""` clears it. |
| `("wait", seconds)` | Pauses. |
| `("tween", [(obj, target_matrix_world), ...], seconds)` | Glides the objects to their targets, eased smoothstep. Rotations interpolate with quaternion slerp; location and scale interpolate linearly. |
| `("tween_value", setter, start, end, seconds)` | Calls `setter(v)` each tick with an eased value. Use it for Play. |
| `("call", fn)` | Runs `fn()` inside the 3D-viewport context override. Use it for operators and selection. |
| `("view", spec)` | Sets the viewport. `spec` is `{"camera": obj}` to look through a camera, or `{"location": Vector, "rotation": Quaternion, "distance": float}`. |

The user-script engine may add more actions for its own scenes (curve point
lifting, for example). The flower code uses only the actions above.

**Flower module API** (PROMO/flower/flower.py), plain bpy with no imports
from PROMO:

- `build_flower(scene) -> dict`: builds the closed bud in a new collection
  "CopyThat Flower" linked to `scene`. It returns:
  - `{"outer": [8 petals], "inner": [6 petals], "core": obj, "stem": obj,
    "pedestal": obj, "leaves": [[seg1, seg2, seg3], [seg1, seg2, seg3]],
    "camera": promo_camera_obj, "all": [every object]}`;
  - It also adds the "Promo Camera" with the outro's frame-1 placement.

  Every moving part has its origin on its hinge or joint, so the default
  Pivot (Origin) turns it there.
- `flower_steps(parts, frames=150)`: a scene generator (contract above)
  that rigs the flower with CopyThat exactly as a user would:
  1. select the parts, then New Move;
  2. glide the leaders and the core and the leaves to their open poses,
     then Record After;
  3. select the riders with the leader active, Ride Along, and set the
     Leads;
  4. set the Follows and the Timing delays;
  5. Build Sliders;
  6. set Frames, then Animate.

  It ends with a `("view", {"camera": camera})` and a `("call", ...)` that
  starts playback, `bpy.ops.screen.animation_play()`, guarded so a headless
  runner skips it. Captions describe each step in a few words.
