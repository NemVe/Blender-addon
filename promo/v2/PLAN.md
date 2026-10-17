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

## v2.2 as built
- **The opening** is `web/src/beats_open.mjs`; its cursor schedule is `OPEN_STEPS` in `make_timeline.py`, which places it after the
  first line of the voice and ends the beat after the second (11.27 s). v2.1's three hooks are gone from `beats_hook.mjs`.
- **N = 12**, the buttons and dialog OKs of `FLOWER_FAST.md` that the film shows: New Move, Make Chain, Record After, Ring... and OK
  three times (outer petals, inner petals, the leaf), Spread... and OK, Build Sliders. New Move records Before by itself, so there is no
  Record Before click. Selecting parts, typing numbers, the four pose drags and the final slider drag are not counted; the drags are
  tagged "drags, not clicks" on screen.
- **The voice** is Chatterbox 0.1.7 (exaggeration 0.65, cfg 0.4, temperature 0.8) in five continuous passages (`audio/vo_script.py`,
  `gen_vo.py`); `cut_vo.py` picks the take Whisper hears best line by line, cuts it at the quietest moments, and levels each line to
  -16 LUFS. No line needed stretching, and none was nudged.
- **The whooshes** are 9 dB below v2.1's in the finished mix (measured: -8.9 dB); the clicks, ticks and pops are as loud as before.
- **Re-rendered:** the opening and the logo (its glow follows the word "slider"). The other segments are v2.1's, renamed to their new
  numbers (`dist/promo/v2/segments_v21/` keeps the old set).

---

# v2.3 (NemVe3D, 2026-10-17): the opening as an exact walkthrough, with a timer

NemVe3D, on v2.2's opening:
- "I saw you pull the 3 leaves with one pull, same with inner and outer ...
  that's not realistic Blender behavior."
- "I want the intro to EXACTLY show how the customer can do it too, because
  there will be a blend file attached where they can also rig it this fast, so
  anything that the user can't do, remove it."
- "instead of clicks it's a timer"
- "no speed clicks like clicking 3 things in 1 second, make it normal like what
  a normal user would do"
- "keep the same voice", "keep the artistic style", "100% (can be copied)
  walkthrough".

Everything from the logo beat on stays as v2.2.

## The rule
Every action on screen is one a customer does with
`promo/files/CopyThat_flower_fast.blend` and CopyThat 0.20.2:
- in the order of `promo/files/FLOWER_FAST.md` steps 1-9, leaving out Animate
  and Play;
- at the pace of a person who knows the steps.

Nothing is done that Blender does not do: one part posed per typed value, each
dialog field set on screen, each selection a click.

## Layout (the artistic style kept)
The dark stage and gold accents of v2.1/v2.2, at 2560x1440:
- **The flower** (`assets/flower.glb`), in the camera's view, centre-left.
- **An Outliner card.**
  - It lists the scene's parts under "CopyThat Flower": Core, Inner Leader,
    Leaf 1, Leaf 2, Leaf 3, Outer Leader, Pedestal, Promo Camera, Stem.
  - The copies and "CopyThat Rig" join the list as they are made.
  - Selected rows highlight the way Blender does, the active one brighter.
- **A Properties card:** the Object tab's Transform panel for the active part.
  - Location X/Y/Z and Rotation X/Y/Z.
  - The real file's values: Core Location Z 1.29, rotations 0.
- **The CopyThat panel as 0.20.2 draws it at the sidebar's usual width.**
  - References: the real screenshots `20_panel.png`, `23_panel.png`,
    `24_panel.png` and `30_view.png` in `dist/promo/live_test/shots/`.
  - Before and After as a checklist: "✓ Before [Record] [eye]".
  - Spread… at the top of TIMING.
  - In COPIES: Ring… and Spread… side by side, then "Riding along (N)", then
    rows with the Lead as a number.
  - The rig line "CopyThat Rig", with "N parts" under it.
- **The real dialogs,** where Blender opens them, by the panel.
  - **Ring:**
    - "Use" with three buttons: Make copies | Use what's there | Fill the gaps,
      the last one lit;
    - then Count, Round (3D Cursor / World Origin), About (World Z), Linked
      copies (ticked) and Lead step;
    - then OK.
  - **Spread (Delays):**
    - Order (Down a chain), Only the selected (a tick box), By (Step | Range),
      Start Delay, Delay step;
    - then OK.
  - For their look, use frames of the real recording
    `dist/promo/rec/main/capture.mkv`. Its panel is older, but the dialogs and
    editors are the same.

## The timer (replaces the click counter)
"RIG TIME" and a big mm:ss in the counter's place, running at real time:
- it starts at the first click and stops when Build Sliders is pressed;
- then it turns gold and reads "RIGGED IN m:ss", the real time of the
  walkthrough as it plays;
- the step label under it says what is being done: SELECT THE PARTS, NEW MOVE,
  MAKE CHAIN, POSE · OUTER LEADER, RECORD AFTER, RING · OUTER PETALS, SPREAD ·
  DELAYS, BUILD SLIDERS, and so on.

## The walkthrough, click by click (FLOWER_FAST.md)
1. **New Move.**
   - In the Outliner, click Outer Leader, then Ctrl+click Inner Leader, Core,
     Leaf 1, Leaf 2 and Leaf 3. Press **New Move**.
   - Panel: Move 1, "✓ Before", "• After", "6 parts".
   - Report: "'Move 1': 6 part(s). Where they stand now is Before. Move them,
     then Record After."
2. **Make Chain.**
   - In the Outliner, click Leaf 3, then Ctrl+click Leaf 2 and Leaf 1.
   - Click the **CHAINS** title and press **Make Chain**.
   - Report: "Chain: Leaf 1 > Leaf 2 > Leaf 3".
   - In the Outliner, Leaf 2 sits inside Leaf 1 and Leaf 3 inside Leaf 2.
3. **Pose, one value at a time.** For each value:
   - click the part in the Outliner;
   - double-click its field in the Properties card;
   - type the value and press Enter; the part moves at Enter.

   The values:
   - Outer Leader Rotation X 75; Inner Leader Rotation X 45; Core Location
     Z 1.47; Core Rotation Z 60.
   - Leaf 1 Rotation X 28: the whole leaf swings, carried by the chain.
   - Leaf 2 Rotation X -145: it and Leaf 3 unfold.
   - Leaf 3 Rotation X 172.

   The leaf's three segments are three separate edits; nothing is pulled.
4. **Record After.** Press **Record** on the After row.
   - Panel: "✓ After".
   - Report: "'Move 1': After recorded for 6 part(s)."
5. **Ring the outer petals.** Click the **COPIES** title, click Outer Leader,
   press **Ring…**. In the dialog:
   - Count: double-click, type 8, Enter (it showed 6);
   - Round: open it and pick World Origin;
   - Lead step: type 9;
   - OK.

   Seven shut petals appear. Panel: "Riding along (7)", "13 parts". Report: "7
   copies of 'Outer Leader' round the world origin ride along with it. Leads
   step by 9, out from it both ways round."
6. **Ring the inner petals.** Click Inner Leader, press **Ring…**. In the
   dialog:
   - Count shows 8: type 6;
   - Round already says World Origin;
   - Lead step opens at 0: type 14;
   - OK.

   Panel: "Riding along (12)", "18 parts". Report: "5 copies of 'Inner
   Leader'…".
7. **Ring the leaf.** Click Leaf 1, press **Ring…**. In the dialog:
   - Count shows 6: type 2;
   - Lead step stays 0;
   - OK.

   Panel: "Riding along (13)", "21 parts". Report: "1 copy of 'Leaf 1' (3
   joints each) round the world origin rides along with it, joint for joint."
8. **Spread on the leaf.**
   - In the Outliner, click Leaf 3, then Ctrl+click Leaf 2 and Leaf 1.
   - Click the **TIMING** title, then **Spread…** at its top.
   - In the dialog: Order says Down a chain. Tick Only the selected. Start Delay
     0.10, Delay step 0.15. OK.
   - Report: "Spread the Delays of 3 parts in steps of 0.15 from 0.1, down the
     chain."
   - Then in the TIMING list, double-click Inner Leader's delay, type 0.34,
     Enter. Then Core's: 0.40.
9. **Build.** Click the **PATH** title, click **Smooth**, press **Build
   Sliders**.
   - The flower goes back to its shut pose, and the Move 1 slider appears at
     0%.
   - Panel: "21 parts · 1 slider".
   - Report: "21 part(s) on 1 slider(s). 6 object(s) were given a bone and
     bound. 15 object(s) now ride along. 2 part(s) hung from the part they
     follow."
   - The timer stops.
10. **Bloom.** Drag the Move 1 slider to 100 % over about 2.5 s: the real bloom
    (`flower_motion.json`).

## Pace: a normal user who knows the steps
- **Cursor travel:** 0.45-0.8 s on a gently curved, eased path, with a short
  pause (0.15-0.3 s) before each click.
- **Never two clicks within 0.35 s,** except a double-click into a field.
- **Typing:** about 7 characters a second, with the caret shown, then Enter.
- **Dialogs:** they stay open while their fields are set, one by one, then OK.
- **Sections:** they open by a click on their title, as a user must.
- **Length:** about 60-80 s from the first click to Build. Do not hurry to
  shorten it, and do not pad it.

## The voice: the same voice
Chatterbox 0.1.7, default voice, exaggeration 0.65, cfg 0.4, temperature 0.8,
as in v2.2: `gen_vo.py`, `cut_vo.py`, and the venv `cb_venv` in the session
scratchpad.

The new opening lines are one continuous passage. Each line is cut out and
placed at the start of its step. Keep them short, so the steps can be seen and
heard:
- "Let's rig this flower from scratch. Clock's running!"
- "Select the six parts, and hit New Move."
- "Make the leaf a chain."
- "Now pose it open, one part at a time."
- "Record After."
- "Ring the outer petals." / "Now the inner ones." / "And the leaf."
- "Spread the timing down the leaf, and give the inner petals and the core a
  delay."
- "Smooth... and Build!"
- "One slider, and it blooms. Rigged in" + the real time, said naturally
  ("fifty-eight seconds", "a minute and twelve seconds") + "!"

The lines from the logo on stay v2.2's.

## Sound
- Mouse clicks on every click, as before.
- Soft, quiet keyboard ticks for typed values.
- Whooshes as in v2.2.
- No click-counter sound.

## Outputs
- **The opening,** rebuilt in `web/src/beats_open.mjs` or a new
  `beats_walk.mjs`, with its timeline and captions.
- **The film,** `dist/promo/v2/CopyThat_promo_v2_1440p60.mp4`. Keep v2.2 as
  `CopyThat_promo_v2.2_1440p60.mp4`.
- **The After Effects project,** rebuilt.
- **A review folder,** `promo_v2_review/v23/` in the session scratchpad:
  - a contact sheet of the opening at 1 fps;
  - stills of:
    - the six-part selection in the Outliner;
    - typing Leaf 2's -145;
    - each Ring dialog with its values set;
    - the Spread dialog;
    - the typed delays;
    - Build;
    - the timer's final card;
    - the bloom.
