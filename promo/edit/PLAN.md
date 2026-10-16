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

## Output
- Encode with ffmpeg: 2560x1440, 30 fps, H.264 High, `-crf 14 -preset slow`,
  yuv420p, bt709 tags, `+faststart`, no audio track.
- Then look at the contact sheet before calling it done.
