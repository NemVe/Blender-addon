# CopyThat promo v2: an explainer, built in Three.js

## What NemVe3D asked for (2026-10-17)
v1 showed the flower being rigged, but the viewer did not know what was
happening. v2 must:
- explain the tool;
- build up from simple shapes: one cube, then many cubes, then a chain,
  then the flower, with the flower's steps explained;
- show a cursor that moves and clicks, with a click sound effect;
- carry an AI voiceover;
- look professional, using Three.js and whatever else it takes.

No checkers or re-testers. Nobody asks NemVe3D anything: decide, and
download what is needed.

## The film: about 80 s, 2560x1440, 60 fps, voiceover-led
- **Look:** the flower's dark studio and gold.
  - Background #0B0B0E to #15151A, with a soft vignette.
  - Gold #C9A76A. Warm white #F2EADB. Cubes in warm cream with gold edges, or
    soft gold metal.
  - PBR materials under RoomEnvironment light, a key light with soft
    shadows, and a subtle floor grid that fades out.
  - Post: SMAA or FXAA, a light bloom on highlights, a touch of grain.
- **The CopyThat panel:**
  - a faithful, simplified copy of Blender's N-panel, on the right;
  - Blender's dark theme: panel #303030, headers #3D3D3D, text #E6E6E6,
    sliders and selection #4772B3;
  - Blender 4's UI font is Inter, so use Inter, already installed;
  - real labels: New Move, Record (Before / After), Build Sliders,
    Spread..., Ring..., Make Chain, and the "Move 1" slider with its %.
- **The cursor:**
  - an arrow cursor (SVG), moving on eased curves between targets;
  - a click is a press-scale pulse, a soft ripple, and the click sound;
  - a drag moves the cursor and the thing dragged together.
- **Captions:** short key phrases (Inter Medium, white, with a gold rule),
  in sync with the voiceover. These are not full subtitles; those go in an
  .srt.

## Script (voiceover lines, in order)
| ID | Segment | Voiceover | On screen |
|---|---|---|---|
| V1 | 0 Hook (Cycles hooks A, B, C) | Twenty-one moving parts. One slider. | "21 moving parts." then "One slider." |
| V2 | 1 Title | This is CopyThat, a Blender add-on that turns a move you record into a slider. | CopyThat wordmark; "Record a move. Get a slider." |
| V3 | 2 One cube | Pose your object where the move starts, and record. Pose it where it ends, and record again. | Cursor: New Move, then Record (Before). It drags the cube up and turns it 90 degrees with a gizmo, then Record (After). Captions: "Record Before", "Record After". |
| V4 | 2 | Press Build, and the whole move lives on one slider. | Cursor: Build Sliders. The "Move 1" slider appears; the cursor drags it 0 to 100% and back, and the cube glides with it. Caption: "Build: one slider". |
| V5 | 3 Many cubes | Select a dozen cubes, and they share one move. | 12 cubes in a row; a box-select; they lift and flip together on the slider. |
| V6 | 3 | Spread their timing, and the same slider plays a wave. | Cursor: Spread..., a small dialog (Delay 0.00 to 0.60, left to right), OK. The Timing list fills in. A slider drag gives a cascading wave. Caption: "Spread: a wave". |
| V7 | 4 Chain | Make Chain hangs parts from one another, so each joint adds its own turn. | A three-block finger. Cursor: Make Chain; the Follows list fills in. A slider drag curls it joint by joint. Caption: "Make Chain". |
| V8 | 5 Ring | Ring turns one petal into a ring of eight. The copies ride along with it. | The real flower geometry. One outer petal; cursor: Ring... with a dialog (Count 8, About World Z); seven copies spin in. Caption: "Ring: 1 to 8". |
| V9 | 5 | Ring the inner petals, chain the leaf, spread the timing... | Quick: inner ring, leaf chain, Spread. |
| V10 | 5 | ...and one slider blooms all twenty-one parts. | Cursor: Build, then drag: the flower blooms with its real motion. Caption: "21 parts, 1 slider". |
| V11 | 6 Real Blender | It all happens right in Blender's sidebar. No rig to build. | The real recording `dist/promo/rec/slider/CopyThat_rec_slider.mov`, with a cursor drawn dragging the real slider in sync. Caption: "The real panel, in Blender". |
| V12 | 7 Cycles | Animate it with one key, and render it however you like. | The Cycles outro footage, with the tag "Rendered in Cycles". |
| V13 | 8 End card | CopyThat. Record a move, get a slider. Now on Superhive. | CopyThat / Record a move. Get a slider. / Now on Superhive / by NemVe3D · creators.sa/nemve |

Each segment lasts its voiceover plus about 0.6 s, but never less than its
action needs. Leave 0.3-0.5 s of air between lines.

## Assets and audio (agent A): `promo/v2/assets/`, `promo/v2/audio/`
1. **The flower for Three.js**, from `promo/files/CopyThat_demo_result.blend`
   (headless Blender 5.2, the add-on loaded from the repo):
   - glTF of every part at rest (its world transform, simple materials,
     names kept);
   - `flower_motion.json`: for frames 1-151, each part's rigid world
     transform. Bound parts follow one bone at weight 1:
     `rig.matrix_world @ pose_bone.matrix @ bone.matrix_local.inverted() @ rig.matrix_world.inverted()`
     on the part's world rest. Check it against the evaluated mesh at
     frames 1, 75 and 151.
   - Group the parts (outer petals, inner petals, core, leaf segments, stem,
     pedestal), with a leader-first order for the ring.
2. **The voiceover:** Kokoro TTS (Apache-2.0, local, `pip install kokoro
   soundfile`; misaki brings its own espeak-ng).
   - Voice `am_michael`, or `af_heart` if that fails; speed about 0.95.
   - One 48 kHz WAV per line V1-V13, trimmed, and `vo.json` with each
     duration.
   - If Kokoro will not install: Piper TTS, then edge-tts.
3. **Sound effects:** a mouse click (down and up), a soft whoosh, a light pop.
   Synthesise them with numpy, or use a CC0 pack (Kenney UI Audio). Keep the
   licence notes.
4. **`promo/v2/timeline.json`:** each segment's start and end, each V line's
   start, and the click times as they become known.

## The film (agent B): `promo/v2/web/` (Three.js) and `promo/v2/build/`
1. **The app:** three@0.170.0 and playwright, installed locally with npm.
   - Every scene is posed only by `window.setTime(t)`. There is no realtime
     clock, so renders are deterministic.
   - One page per segment, or a router.
2. **Rendering:** Playwright, the frame captured at 2560x1440 for each 1/60
   s. Use the GPU: Chromium flags `--use-angle=d3d11 --ignore-gpu-blocklist`.
   Preview at 25% while working; render at full size once.
3. **Footage:** the hooks (`dist/promo/hooks_1440`), the outro
   (`dist/promo/outro_frames_1440`, 30 fps, each frame doubled), and the
   real slider recording, with the cursor layer drawn over it.
4. **Audio:** place the V lines and a click at every cursor click, then
   whooshes and pops. Mix to about -14 LUFS, true peak -1 dB, AAC 320k 48 kHz.
5. **Outputs:**
   - `dist/promo/v2/CopyThat_promo_v2_1440p60.mp4`: H.264 High, CRF 16,
     yuv420p, bt709, +faststart;
   - `captions.srt`;
   - stems: `vo.wav` and `sfx.wav`, with no music (NemVe3D may add some).
6. **For NemVe3D:** a simple After Effects 2025 project,
   `promo/v2/CopyThat_promo_v2.aep`. It holds the rendered segments and the
   two stems on a timeline, with a marker per voiceover line. Adapt
   `promo/edit/build_promo.jsx`. Do this last, and only if time allows.
   - Never force-close After Effects. Log errors; never alert.
7. **Review:** a contact sheet (one frame a second) and 12 stills in the
   scratchpad's `promo_v2_review/`, for the planner.

## Rules for both agents
- Decide and go on: never stop to ask. If something is blocked, find another
  way.
- Downloads are allowed: pip `--user`, npm local, CC0 or OFL assets only.
- No admin installers, nothing deleted outside the repo and the scratchpad.
- Commit `promo/v2/` sources by explicit path, with
  `git -c user.name=Claude -c user.email=noreply@anthropic.com`, after
  `git pull --rebase`; never force-push. Large renders stay in `dist/`, which
  git does not track.
- Progress lines go to the Board, `D:\ObsidianVault\NemVe3D\02 - CopyThat\Board\promo v2 - <agent>.md`.
  Never commit the vault.
- No checkers, no second opinions. Look at your own renders before calling
  them done.
