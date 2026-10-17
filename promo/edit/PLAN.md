# The promo edit in After Effects

NemVe3D asked for the film to be edited in After Effects, with the project
kept so they can open and change it themselves. This replaces the ffmpeg
assembly that `../STORYBOARD.md` first planned. The shot list, the look and
the captions in the storyboard still hold.

## What is made
- `CopyThat_promo.aep`: the After Effects 2025 project, committed. Tidy enough
  to hand to an editor:
  - folders in the Project panel: `Footage/Hooks`, `Footage/Recording`,
    `Footage/Render`, `Cards` (with `Solids`), `Shots`;
  - one precomp per shot, named like the storyboard ("01 Bloom", "04
    Slider"...), and the main comp "CopyThat Promo" (61 s, 30 fps, 2560x1440,
    16 bits per channel) that lays them end to end;
  - one precomp per card, in `Cards`: three statements, the title, nine lower
    thirds (eight beats and the slider), the tag, the end card;
  - every layer named, and coloured in the demo: orange a dialog, green
    moving, blue a pause;
  - a marker on the main comp at every shot and at every beat;
  - no audio: NemVe3D lays the music.
- `build_promo.jsx`: the ExtendScript that builds the project from scratch.
  Run it again after any change; never hand-edit the project and the script
  apart. It takes about 10 s.
- `edit_list.py`: reads the recording's timeline JSON and the fixed shots, and
  writes `edit_list.jsxinc`, the cuts, speeds, captions and markers as plain
  data that `build_promo.jsx` includes. ExtendScript has no JSON, and the
  timing logic is easier to get right in Python. It looks at the recording
  itself (the sync flash, what moves, where the dialogs are) and takes about
  three minutes. The y of each hook line is in it too (`STATEMENTS`).
- `render_bloom.py`: step 0, the clean viewport bloom of shot 7 (below).
- `render_promo.sh`:
  1. `aerender` renders the main comp to a PNG sequence in
     `dist/promo/edit_frames/`;
  2. ffmpeg encodes it to `dist/promo/CopyThat_promo_1440p.mp4`;
  3. it writes a contact sheet (one frame a second) and one still of each shot
     into `dist/promo/edit_review/` (or `$REVIEW`).

## Running After Effects from a script
- After Effects 2025 (25.3.1):
  `C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\AfterFX.exe -r <absolute path>\build_promo.jsx`.
  `aerender.exe` is in the same folder. It starts in a few seconds and the
  script quits it itself; never kill it (that brings up a crash-repair dialog).
- The script:
  - starts with `app.beginSuppressDialogs()` and wraps its body in try/catch;
    every error, with its line, goes to `dist/promo/edit_build_log.txt`: read
    that file back after a run;
  - builds a new project, saves it with `app.project.save(File)` (the
    partial project too, when it fails), queues the film for `aerender`, and
    quits.
- Do not start After Effects on top of one that is open: `render_promo.sh`
  refuses to.
- Fonts: "Inter Medium" (PostScript `Inter-Medium`) and "Inter Display Light"
  (`InterDisplay-Light`) are installed for the user from `../cards/fonts/`
  (converted to TTF, 2026-10-16). Set them on text layers by PostScript name.
- NemVe3D allows clearing caches and freeing RAM for the render. Purge After
  Effects' disk cache and close what the agent itself opened. Ask before
  closing anything else.
- The render goes out as a PNG sequence through a hidden output module
  template, `_HIDDEN X-Factor 8` (`16` for 16 bits): this After Effects lists
  no PNG template and `setSettings` says the format is read-only.
- Things that went wrong once, so they do not again:
  - a script appends to the bottom of a shape group, and a fill above its path
    fills nothing: the path is moved to the top (`pathFirst` in the script);
  - reading `.value` of a mask feather or of a property with an expression,
    from a script, throws "invalid numeric result"; the render is fine, so
    those are not read back;
  - Scale of a 2D layer is a three-value property for `setTemporalEaseAtKey`;
  - taking every key off a layer's time remap turns it off: move the two it
    starts with instead;
  - `CompItem.saveFrameToPng` saves nothing here. To look at a frame, queue it
    with the hidden PNG template and call `renderQueue.render()`;
  - a text layer's `sourceRectAtTime` is the tight box round the ink, and its
    Position is the baseline.
  - a stretched, trimmed footage layer whose in point is exactly the right frame can start one source frame
    late, and that comp frame renders transparent (it did at the start of every sped-up cut): `placeClip`
    sets the layer a twentieth of a frame early and its in and out points a quarter early, and the build
    logs a coverage check of every shot ("every frame is covered");
  - to render a few frames again, queue each under its own file name (one shared name writes every frame
    to `_00000`), then copy them over the frames in `edit_frames/` and encode with `SKIP_AE=1`;
  - in `render_promo.sh`, `ls | head -1` under `pipefail` ends the script silently (SIGPIPE): use `sed -n 1p`.
- Calibrated against a render of known shapes (so a CSS number becomes an After
  Effects one): Gaussian Blur has a sigma of 0.275 x its blurriness; Drop
  Shadow, 0.2 x its softness, with its opacity running 0-255; the feather of a
  mask and of Linear Wipe is the width of the 10-90% edge, in pixels; Linear
  Wipe at 90 degrees takes a layer away from the left, so a wipe in from the
  left is 270 degrees, completion 100 to 0.

## The look: the cards rebuilt as native layers
The cards in `../cards/` (HTML, posed frame by frame by `setTime(t)`) are the
specification. Each is rebuilt in After Effects:
- same sizes and positions, scaled from 1920x1080 to 2560x1440 (x 1.3333),
  text placed by the baseline the CSS gives it and centred by its ink;
- same colours (gold `#C9A76A`, warm white `#F2EADB`), fonts and tracking;
- same timeline: each `T = {...}` entry becomes keyframes, and the easing
  curves become matching keyframe influence (outCubic is a fast start and a
  long settle; inOutSine is gentle at both ends).

| Card | Used for | Built as |
|---|---|---|
| `statement.html` | the three hook lines | text, three drop shadows and a focus blur, a gold rule (a solid with a feathered mask) |
| `title_short.html` | shot 5 | backdrop (a radial Gradient Ramp), gold glow, `grain.png` tiled, the wordmark (Linear Wipe, focus blur), rule, tagline, push-in null, fade |
| `lower_third.html` | the demo's captions | a dark slab (a shape layer, blurred, sized to the caption by an expression, cut at the rule by an alpha matte), the sharp gold rule (a two-stop gradient), the text |
| `tag.html` | "Rendered in Cycles" | text with a shadow and a fade |
| `end.html` | the end card | the shade and pool (a feathered mask, a blurred ellipse), four lines rising, the credit in two colours |

Not carried over: the CSS word spacing of the statements, the gold sheen that
rides the title's wipe, and the gradients' middle stops (the ramps have two
colours). The backdrop and the rule differ from the HTML by a few levels.

Text layers stay live text, so NemVe3D can retype a caption: open the card's
precomp (double click it in the Project panel) and edit the text. The
lower third's slab follows the text by itself. A card's length is its
precomp's length; its fade out is keyed from the end, so after a new length,
move those keys.

## The shots (storyboard)

| Shot | Time | Footage |
|---|---|---|
| 1 | 0.0-1.5 | `dist/promo/hooks_1440/hook_A` (frames 30-90, 61 frames), sped to fit (1.36x) |
| 2 | 1.5-3.0 | `hook_B` (106-150, 45 frames) |
| 3 | 3.0-4.5 | `hook_C` (152-197, 46 frames, 1.02x) |
| 4 | 4.5-8.0 | the slider recording: the whole move (4 s and a few frames after it) at 1.18x |
| 5 | 8.0-10.0 | the title card |
| 6 | 10-52 | the demo recording, cut and sped from its timeline JSON, a lower third per beat |
| 7 | 52-57 | the viewport bloom dissolving, over 1 s from 1.5 s in, into the same frame of the Cycles render (`dist/promo/outro_frames_1440`, 210 frames), with the tag from 2.4 s |
| 8 | 57-61 | the end card over the outro's last 60 frames, which play on at normal speed and ease to a stop on the last one (no jump of speed at the cut, no hard freeze) |

- The hook frames are 16-bit PNG sequences: imported as sequences at 30 fps.
- Cuts land on the storyboard's 0.5 s grid, for music.
- The hook lines: "21 moving parts." and "No rig to build." stand high in the
  frame (y 170 of 1080) over the close-ups, which have no clear place;
  "One slider." stands low (y 770), over the dark pedestal, because the flower
  reaches the top of the frame there.
- Shot 6 (42 s = 1260 frames): `edit_list.py` cuts the pauses between beats
  and plays what moves at 1.5x at most; a dialog is never touched (it stays 1x,
  about 1.5 s); a pause where something was read (the panel's report after a
  button) keeps its first `hold` frames. The cuts are separate trimmed layers
  of the one recording in `06 Demo`, one per segment, so they can be moved by
  hand. The recording's sync flash is two white frames (315-316 in the main,
  317 in the slider's); the cuts start two frames after it.

## The viewport bloom (step 0)
The live capture of the bloom (the recording from +64.5 s) repeats a frame every
12 frames and its white petals are grainy. `render_bloom.py` renders the
camera view in Material Preview, frame by frame, with
`bpy.ops.render.opengl(animation=True, view_context=True)` from a real Blender
window (not `--background`), into `dist/promo/viewport_bloom/` (151 frames,
2560x1440, 16-bit PNG, about 3 s a frame). Checked: no repeated frames, no
grain, the look of the capture, and the same framing as `outro_frames_1440` at
every frame number, so the dissolve is a match cut. Give `--out` as an
absolute path: Blender reads a relative render path from the root of the drive.

## Re-rendering a shot
The Cycles footage comes from one Blender file,
`../files/CopyThat_promo_shots.blend` (Blender 5.2), so NemVe3D can adjust a
shot and render it again. Each of its four scenes renders to the folder the
edit already reads, with the same file names: a re-render replaces the footage
in place.

**Which scene makes which footage**

| Scene | Frames | Output folder | Shots |
|---|---|---|---|
| Outro | 1-210 | `dist/promo/outro_frames_1440/` (`outro_0001.png`...) | 7, 8 |
| Hook A | 30-90 | `dist/promo/hooks_1440/hook_A/` (`hook_A_0030.png`...) | 1 |
| Hook B | 106-150 | `dist/promo/hooks_1440/hook_B/` (`hook_B_0106.png`...) | 2 |
| Hook C | 152-197 | `dist/promo/hooks_1440/hook_C/` (`hook_C_0152.png`...) | 3 |

All four: 2560x1440 at 100%, 16-bit RGB PNG, Cycles, 512 samples, 30 fps.
- Hook A, B and C are linked copies of Outro. The flower and its animation, the
  lights and the world are shared, so a change to them shows in all four. Each
  scene has its own camera, frame range, output folder and compositor (the
  bloom is a Glare node in it), so change the bloom in each scene.
- A hook camera ("Hook A Camera") is keyed at the first and last frame of its
  shot, and always looks at its empty ("Hook A Aim"), which is also where it
  focuses. Move either at those two frames, or change the lens and f-stop in
  the camera's properties. If you change the frame range, move the keys too.

**How to re-render**
1. Open the .blend. It opens on Outro; pick the scene at the top right.
2. Adjust it, and look at a frame with Render > Render Image (F12).
3. Render > Render Animation. The frames overwrite the old ones in the output
   folder; to keep the old ones, set a new output folder first (Output
   properties).
4. Cycles uses the GPU only if OptiX (or CUDA) is chosen in Edit > Preferences
   > System. Otherwise it renders on the CPU, far slower. On the RTX 3090 a
   frame takes 45 to 60 s: a hook shot 35 to 50 minutes, the outro about 2.5
   hours.
- From a script or the command line, make the scene the active one first:
  `blender -b CopyThat_promo_shots.blend -S "Hook A" -a` does. A script that
  calls `bpy.ops.render.render(scene="Hook A")` while another scene is active
  gets the flower in a stale pose.

**How to bring it into After Effects**
- Same folder, same file names: select the footage item in the Project panel
  and File > Reload Footage.
- A new folder, other names or a changed frame range: select the item, File >
  Replace Footage > File, pick the first frame and tick PNG Sequence. Then check
  the layer's length in its shot precomp.
- If the number of frames of a hook or the outro changes, run `edit_list.py`
  and `build_promo.jsx` again: they count the frames.

## Output
- Encode with ffmpeg: 2560x1440, 30 fps, H.264 High, `-crf 14 -preset slow`,
  yuv420p, bt709 tags (and the bt709 matrix, which ffmpeg does not assume for
  RGB), `+faststart`, no audio track.
- A full render takes about 70 minutes (2.3 s a frame; aerender uses a quarter of this PC's CPU), the encode
  a minute and a half.
- Then look at the contact sheet before calling it done.
