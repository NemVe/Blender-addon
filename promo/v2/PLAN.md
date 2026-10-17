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

---

# v2.1 (NemVe3D, 2026-10-17): flash style. This SUPERSEDES the script and shot list above.

The reference is "Auto Unwrap 2 Teaser" by 3DRedBox
(youtube.com/watch?v=p1TyTzM_1ag). The planner studied its frames; this
section describes the template, so there is no need to watch it.
- Every feature is shown "flash style", 2-3 s each, with a stylish delivery.
- The screen recording is only one ingredient among others.
- Everything above still holds unless this section says otherwise: the
  rules, the outputs, the cursor, the voiceover tool and the sound effects.

## The template: one beat per feature, 2-3 s
- **Background:** #0A0A0C, a warm gold glow from one corner (a radial, about
  12%), and subtle grain.
- **Left column** (x 6-38%), top to bottom:
  - **Kicker:** small caps, Inter SemiBold, about 22 px at 1440, tracking
    0.18 em. A gold number and label, "07 · CHAIN".
  - **Headline:** Inter ExtraBold, about 76 px, white, 2 lines at most,
    with the key word in gold #C9A76A.
  - **Subline:** Inter Regular, about 26 px, #9A968E, one line.
  - **Mini UI card:** one row of the CopyThat panel (Blender dark theme),
    showing that feature's real control and animating the setting.
- **Right** (x 42-94%): a rounded card (18 px radius, soft shadow) showing
  the action. It is a Three.js mini-scene, or a crop of the real Blender
  recording, with the cursor clicking. Small caps labels in a card corner
  when useful ("BEFORE", "AFTER", "REAL BLENDER").
- **Text motion:** the kicker fades and slides in (0.15 s), the headline
  lines slide up with a small stagger, then the subline; all fade out fast.
- **Between beats:** a diagonal stripe wipe, a white band then a gold band
  slanted about 20°, 0.35 s, with a whoosh.
- **Fonts:** download the Inter family (OFL, rsms/inter releases) for the
  web: SemiBold, ExtraBold, Regular.

## Structure, about 76 s
| Time | Beat | On screen | Voiceover |
|---|---|---|---|
| 0-3 | Hook 1 | kicker "RIGGING"; "Hours of building rigs." over a Three.js shot of the flower tangled in bones and constraint lines (wireframe, gold) | Rigging takes hours. |
| 3-6 | Hook 2 | "Bones." / "Constraints." / "Drivers." / "Keys." stacking, the last in gold | Bones. Constraints. Drivers. Keys. |
| 6-9 | Hook 3 | "What if you just showed it the move?" over a cube leaving a gold ghost trail | What if you just showed it the move? |
| 9-13 | Logo | the COPYTHAT wordmark (ExtraBold, gold accent) and "Record a move. Get a slider." over the Cycles bloom (hook C) | This is CopyThat. Record a move, get a slider. |
| 13-17 | THE IDEA 1/3 | "Pose it. Record it." The cube: Record Before, a drag, Record After | Pose it, and record. |
| 17-21 | THE IDEA 2/3 | "Build. One slider." Build Sliders, then the slider dragged as the cube glides | Press Build. One slider plays the move. |
| 21-25 | THE IDEA 3/3 | "Many parts. One move." 12 cubes rise and flip | Select many parts: one move. |
| 25-58 | FEATURES 01-12 | 2.5-3 s each (list below) | one short line each |
| 58-68 | PUT IT TOGETHER | "21 parts. One slider." The Three.js flower (real geometry and motion): ring, spread, bloom on the slider, then a dissolve into the Cycles render | Put it together: twenty-one parts, one slider. |
| 68-71 | REAL BLENDER | "Right in the sidebar." The real slider take in the card, with the cursor dragging the real slider | All right in Blender's sidebar. |
| 71-76 | End card | the wordmark; "Record a move. Get a slider."; a gold pill "Now on Superhive"; "by NemVe3D · creators.sa/nemve" | CopyThat. Now on Superhive. |

## Features: kicker · headline (key word in gold) · mini UI · the card · voiceover
1. **01 · TIMING.** "Each part, its own **delay**."
   - Mini UI: a Delay slider row.
   - Card: three cubes start one after another.
   - Voiceover: "Give each part its own delay."
2. **02 · SPREAD.** "A **wave** in one click."
   - Mini UI: the Spread... dialog.
   - Card: the real recording's Spread dialog crop, then a cube wave.
   - Voiceover: "Spread the timing into a wave."
3. **03 · PIVOT.** "Turn about **any point**."
   - Mini UI: Origin | Cursor | Base.
   - Card: a lid turning on its hinge.
   - Voiceover: "Turn about any point."
4. **04 · STEPS.** "Steps **in between**."
   - Mini UI: "+ Step in between".
   - Card: a path bending through an added pose.
   - Voiceover: "Add steps in between."
5. **05 · CURVES.** "Curve the path. **Edit its curve.**"
   - Mini UI: Curve the Path / Edit the Curve.
   - Card: a coin on a bezier, the cursor dragging a handle.
   - Voiceover: "Curve the path, and edit its curve."
6. **06 · SPEED.** "**Smooth** or even."
   - Mini UI: Smooth / Even speed.
   - Card: two balls, eased and linear.
   - Voiceover: "Smooth, or even speed."
7. **07 · CHAIN.** "Joints that **follow**."
   - Mini UI: Make Chain plus the Follows list.
   - Card: a three-block finger, or the real Make Chain crop.
   - Voiceover: "Chain parts, so joints follow."
8. **08 · CURL.** "**Curl** it in one go."
   - Mini UI: Curl.
   - Card: the finger curls.
   - Voiceover: "Curl a whole chain at once."
9. **09 · RING.** "One part, a **ring**."
   - Mini UI: the Ring... dialog, Count 8.
   - Card: the real Ring dialog crop, then a petal becoming 8.
   - Voiceover: "Ring one part into many."
10. **10 · MIRROR.** "Copies that **mirror**."
    - Mini UI: Mirror X.
    - Card: left and right doors opening mirrored.
    - Voiceover: "Mirror the copies."
11. **11 · COMBINE.** "Many moves, **one control**."
    - Mini UI: two sliders merging.
    - Card: two moves under one control.
    - Voiceover: "Combine moves under one control."
12. **12 · ANIMATE.** "Keyed in **one click**."
    - Mini UI: Frames 48 ▶ Animate.
    - Card: timeline keys appear and it plays.
    - Voiceover: "Animate it in one click."

## Real recording crops (from `dist/promo/rec/main`)
Use them where they fit:
- Spread's dialog, about +37.4-38.9 s after the flash at 10.50 s;
- Ring's dialog, +22.6-24.1;
- Make Chain, +4.4-7.4;
- Build and the slider, +44-55.

Scale the region of interest up inside the card.

## Audio
- Voiceover lines as in the tables (Kokoro). The feature lines must fit 2.5 s.
- Sound effects: a click on every UI click, a whoosh on every wipe, pops for
  ring copies, a soft tick as each headline lands.
- No music, as before; NemVe3D adds a track. Put markers on the beat grid.

---

# v2.2 (NemVe3D, 2026-10-17): a new opening, a lively voice, quieter whooshes

NemVe3D likes the v2.1 film; three changes only. Everything else stays: the
logo, the idea beats, the features 01-12, "21 parts", real Blender and the
end card.

## 1. The opening replaces hook1-3 (0-9 s)
- **"Let's rig this flower in N clicks."**
  - N is the honest count of the button clicks and dialog OKs shown on
    screen, taken from the fast flower's steps
    (`promo/files/FLOWER_FAST.md`) and the add-on's real buttons.
  - Pose drags are not counted, but they are shown, quickly.
- **About 10-12 s, fast and fun:**
  - the real flower (`assets/flower.glb`) and a copy of the 0.20 panel;
  - a big counter, "CLICKS 0/N", that ticks with every click, each with
    the click sound;
  - the cursor races through New Move, Record (Before / After), Ring... OK
    (outer), Ring... OK (inner), Make Chain (leaf), Spread... OK, Build
    Sliders;
  - each step lights its parts gold (the ring copies spin in, the timing
    bars fill);
  - the last click drags the slider, and the flower blooms with its real
    motion (`flower_motion.json`).
- **Then the logo beat, as before.**

## 2. The voice: enthusiastic, one continuous flow
NemVe3D: v2.1's voice was "boring, not enthusiastic, like reading from a
script". The lines were made one by one, so each reset its intonation.
- **Engine:** Chatterbox (Resemble AI, MIT, local on the RTX 3090), with
  more exaggeration (about 0.6-0.7) and a lower cfg (about 0.35-0.45) for
  livelier pacing.
  - If it will not install on Python 3.13, make a 3.11 venv with `uv` (it
    downloads its own Python).
  - Fallback: Kokoro with a livelier voice (am_puck or af_bella), speed
    1.08.
- **Generate passages, not lines:** a few continuous takes (the opening, the
  idea, the features, the close). Then cut them at the word times with
  faster-whisper, and place each cut on its beat. Nudge beats by at most
  ±0.3 s, or time-stretch a cut by at most ±8%.
- **The script,** conversational:
  - Opening: "Let's rig this flower in N clicks. Watch this!", then the
    clicks with no voice, then "Done! One slider, and it blooms."
  - Logo: "This is CopyThat: record a move, and get a slider."
  - Ideas: "Pose your object, and hit Record." / "Press Build, and the whole
    move lives on one slider." / "Select as many parts as you like; they all
    share one move."
  - Features:
    - "Give every part its own delay."
    - "Spread the timing into a wave."
    - "Turn around any point you want."
    - "Add steps in between."
    - "Curve the path, then edit the curve."
    - "Smooth, or perfectly even."
    - "Chain parts, so the joints follow."
    - "Curl a whole chain at once."
    - "Ring one part into many."
    - "Mirror the copies."
    - "Combine moves under one control."
    - "And animate it all in one click."
  - Close: "Put it all together: twenty-one parts, one slider." / "And it
    all happens right in Blender's sidebar." / "CopyThat. Now on Superhive!"
- **Processing:** light compression, a little presence; the voice at about
  -16 LUFS before the mix.

## 3. Whooshes about 9 dB quieter
Keep them under the voice. The ticks and pops stay as they are.

## Re-render only what changed
1. The opening segment.
2. The audio mix.
3. The film assembly.
4. The After Effects project, rebuilt with its script.
5. A new contact sheet and stills for the opening, in
   `promo_v2_review/v22/`.
