# The promo edit in After Effects

NemVe3D asked for the film to be edited in After Effects, with the project
kept so they can open and change it themselves. This replaces the ffmpeg
assembly that `../STORYBOARD.md` first planned. The shot list, the look and
the captions in the storyboard still hold.

## What is made
- `CopyThat_promo.aep`: the After Effects 2025 project, committed. Tidy enough
  to hand to an editor:
  - folders in the Project panel: `Footage/Hooks`, `Footage/Recording`,
    `Footage/Render`, `Cards`, `Shots`;
  - one precomp per shot, named like the storyboard ("01 Bloom", "04
    Slider"...);
  - every layer named;
  - a marker on the main comp at every beat;
  - no audio: NemVe3D lays the music.
- `build_promo.jsx`: the ExtendScript that builds the project from scratch.
  Run it again after any change; never hand-edit the project and the script
  apart.
- `edit_list.py`: reads the recording's timeline JSON and the fixed shots, and
  writes `edit_list.jsxinc`, the cuts, speeds, captions and markers as plain
  data that `build_promo.jsx` includes. ExtendScript has no JSON, and the
  timing logic is easier to get right in Python.
- `render_promo.sh`:
  1. `aerender` renders the main comp to a PNG sequence in
     `dist/promo/edit_frames/`;
  2. ffmpeg encodes it to `dist/promo/CopyThat_promo_1440p.mp4`;
  3. it writes a contact sheet (one frame a second) for review.

## Running After Effects from a script
- After Effects 2025 (25.3.1):
  `C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\AfterFX.exe -r <absolute path>\build_promo.jsx`.
  `aerender.exe` is in the same folder.
- The script:
  - starts with `app.beginSuppressDialogs()`;
  - builds a new project and saves it with `app.project.save(File)`;
  - adds the render-queue item for `aerender`;
  - saves again and quits.
- Watch for anything modal: a sign-in, a crash-recovery prompt, the Home
  screen. Look at the screen (a PowerShell screenshot) when a run hangs.
  Close only After Effects windows; nothing else of NemVe3D's.
- Fonts: "Inter Medium" (PostScript `Inter-Medium`) and "Inter Display Light"
  (`InterDisplay-Light`) are installed for the user from `../cards/fonts/`
  (converted to TTF, 2026-10-16). Set them on text layers by PostScript name.
- NemVe3D allows clearing caches and freeing RAM for the render. Purge After
  Effects' disk cache and close what the agent itself opened. Ask before
  closing anything else.

## The look: the cards rebuilt as native layers
The cards in `../cards/` (HTML, posed frame by frame by `setTime(t)`) are the
specification. Read each one and rebuild it in After Effects:
- same sizes and positions, scaled from 1920x1080 to 2560x1440 (x 1.3333);
- same colours (gold `#C9A76A`, warm white `#F2EADB`), fonts and tracking;
- same timeline: each `T = {...}` entry becomes keyframes, and the easing
  curves become matching keyframe influence (outCubic is a fast start and a
  long settle; inOutSine is gentle at both ends).

| Card | Used for |
|---|---|
| `statement.html` | the three hook lines |
| `title_short.html` | shot 5 |
| `lower_third.html` | the demo's captions: a dark slab with soft edges (a shape layer, blurred), a sharp 3 px gold rule with its gradient, the text |
| `tag.html` | "Rendered in Cycles" |
| `end.html` | the end card |

`grain.png` is the cards' grain: lay it over the cards the same way.

Text layers stay live text, so NemVe3D can retype a caption. One precomp per
card kind, with the text as the only thing that changes; or Essential
Graphics, if that stays simple.

## The shots (storyboard)

| Shot | Time | Footage |
|---|---|---|
| 1 | 0.0-1.5 | `dist/promo/hooks_1440/hook_A` (frames 30-90, 61 frames), sped to fit |
| 2 | 1.5-3.0 | `hook_B` (106-150, 45 frames) |
| 3 | 3.0-4.5 | `hook_C` (152-197, 46 frames) |
| 4 | 4.5-8.0 | the slider recording |
| 5 | 8.0-10.0 | the title card |
| 6 | 10-52 | the demo recording, cut and sped from its timeline JSON, a lower third per beat |
| 7 | 52-57 | the viewport bloom dissolving into the same frame of the Cycles outro (`dist/promo/outro_frames_1440`, 210 frames), with the tag |
| 8 | 57-61 | the end card over the outro's last frames |

- The hook frames are 16-bit PNG sequences: import them as sequences at 30
  fps.
- Cuts land on the storyboard's 0.5 s grid, for music.

## Output
- Encode with ffmpeg: 2560x1440, 30 fps, H.264 High, `-crf 14 -preset slow`,
  yuv420p, bt709 tags, `+faststart`, no audio track.
- Then look at the contact sheet before calling it done.
