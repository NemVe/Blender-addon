# Recording the CopyThat demo

`copythat_promo.py` plays demo scenes in Blender by itself, with nobody at the
mouse. It is used two ways:

- **The promo's recording** (scene 5, what it plays unless told otherwise): the
  fast flower of `promo/files/FLOWER_FAST.md` rigged from scratch with
  CopyThat, in a Blender window of exactly 2560x1440, which a screen capture
  records. This is shots 4 and 6 of `promo/STORYBOARD.md`. Read "The promo
  recording".
- **By hand**: scenes 1 to 4, the four older demos, or scene 5 without its
  dialogs, run from the Scripting tab of your own Blender. Read "By hand".

## The promo recording

### What it plays

Scene 5 builds a new scene, "CopyThat Promo 5 - Flower fast": the fast
flower (one outer petal, one inner petal, the core, one leaf of three
segments, stem, pedestal, camera; the studio is out of the viewport), in the
3D view's Solid shading with the parts' own colours, cavity and soft shadows,
and the sidebar open on the CopyThat tab. It then does the steps of
`FLOWER_FAST.md`, in its order. Each beat is a change a viewer can follow in
the panel, and its caption is the storyboard's lower third:

| Beat | What happens | Caption (put on in the edit) |
|---|---|---|
| `new_move` | the six parts are picked one after another, New Move | Select the parts. New Move. |
| `make_chain` | Leaf 3, Leaf 2, then Leaf 1 picked, Make Chain | Make Chain: the leaf's joints hang from one another. |
| `pose_record` | the parts glide into the open pose (75, 45, core up and turned, the leaf 28, -145, 172), Record After | Pose it once. Record. |
| `ring_outer` | Ring opens on Outer Leader with Count 8, World Origin, Lead step 9, and is confirmed | Ring: one petal becomes a ring of eight. |
| `ring_inner_leaf` | the same for Inner Leader (6, 14) and Leaf 1 (2, 0); the sidebar is scrolled down to read the last report | Ring the inner petals and the leaf. |
| `spread` | the three leaf parts picked, Spread opens (Down a chain, Only the selected, Step, 0.10, 0.15) and is confirmed; then the Delays 0.34 and 0.40 are typed | Spread: the timing, in one go. |
| `build` | Ease Smooth, Build Sliders, then the Play slider is dragged 0 to 100% and back, 3 s each way | Build: one slider plays all 21 parts. |
| `animate` | Frames goes to 150, Animate | Animate: keyed over 150 frames. |

The dialogs are pressed as a person presses them: the button is invoked, the
dialog stays up for 1.5 s with the beat's values filled in, and a simulated
Return confirms it. Poses glide, numbers run up to their value, the slider
slides. No caption is drawn in Blender (`FLOWER_FAST_CAPTIONS = False`).

After the beats comes the bloom: nothing is selected, the studio's lights come
on (its backdrop stays out), the 3D view fills the window with its header,
toolbar, sidebar and overlays gone, the view glides into "Promo Camera" in
Material Preview, rests on frame 1 for 3 s, and then frames 1 to 151 play in
real time (5 s). The last frame is held, and the script ends there: it does
not give the screen back, so that the last picture is the bloom.

### Start it

Blender 5.2.1, started with `--enable-event-simulate`: without it the dialogs
cannot be opened on screen, the sidebar is not dragged wider and the welcome
screen is not sent away (the same steps are then done without the dialogs).
`run_recording.py` starts the script, with the add-on and the flower code taken
from this repository, and sets the interface scale to 1.33:

    "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" --factory-startup ^
        --enable-event-simulate --window-geometry 0 0 2560 1440 ^
        --python promo\user_script\run_recording.py -- --out <folder>

Then, once the window is open, make it frameless and exactly 2560x1440
(Windows keeps a framed window above the taskbar, 1361 px tall):

    powershell -File promo\tools\frameless_window.ps1

`run_recording.py` waits for the window to be that size (`--wait`, 90 s), runs
the script, and quits Blender 4 s after it ends. The script itself counts down
5 s, then flashes the whole window white for two frames of a 30 fps recording
(time 0 of the timeline), and the first beat begins at once. The capture is
the window alone, with no cursor:

    ffmpeg -filter_complex "gfxcapture=window_exe='(?i)blender\.exe':capture_cursor=0:max_framerate=30,hwdownload,format=bgra" -c:v libx264 -crf 12 -preset slow -pix_fmt yuv420p <out>.mp4

(stop it with q after Blender has quit). Nobody touches the mouse or the
keyboard of the PC while it plays, about 90 s from the launch. The real
pointer is not recorded, but where it rests still counts: leave it outside the
window (the screen is wider than 2560 px), or Blender may show hover hints for
what is under it.

Options of `run_recording.py`, after the `--`: `--mode slider` (below),
`--shots` (a dress rehearsal), `--every SECONDS`, `--scale`, `--size WxH`,
`--wait`, `--script PATH` (`dist\copythat_promo.py` is the bundle), `--addon DIR`,
`--save-blend PATH` (below), `--leave` and `--stay`; the top of the file says
what each does.

### The timeline

The script writes a JSON file at every beat: `<folder>\timeline.json` with the
runner, else where `COPYTHAT_TIMELINE` says, else next to the .blend, else next
to the script, else in the temporary folder. The edit cuts and captions from
it, so nothing is timed by hand:

    {"t0_epoch": ..., "fps": 30, "mode": "main",
     "beats": [{"name": "new_move", "caption": "Select the parts. New Move.",
                "start": 0.1, "end": 4.4}, ...],
     "bloom_start": 63.6, "bloom_end": 68.7, "bloom_frame_rate": 30.0,
     "flash_seconds": 0.0667, "finished": true}

Times are seconds after time 0, the end of the countdown, which is also the
white flash. `bloom_start` is when the 3D view begins to play at frame 1, so
that shot 7 can dissolve into the Cycles render at the same frame.
`finished` is true only when the run got to its end.

### The finished flower as a file

To open and adjust the flower as the film ends it, ask the script to save it:
`SAVE_BLEND = "<path>"` near the top of the script, `COPYTHAT_SAVE_BLEND=<path>`
in the environment, or `--save-blend PATH` of `run_recording.py` (the
environment comes first). The rehearsal saved `promo/files/CopyThat_demo_result.blend`
this way: open it in Blender 5.2 with CopyThat turned on.

It is written as the bloom begins, the last moment the window still has its
ordinary layout, and as a copy: the session itself stays unsaved. The file
opens on the demo scene as the film ends it: the rigged flower (Move 1 with its
21 parts, Ease Smooth, Animate keyed over frames 1 to 151) on the last frame,
the studio lit, nothing selected, seen through "Promo Camera" in Material
Preview. The header, toolbar and the sidebar on the CopyThat tab are in place,
not gone as in the film's last frames, which would be hard to work in. Blender's
own default scene (Cube, Camera, Light) comes along from the factory start-up.
A path that cannot be written is said on the console, and the show goes on. The
slider recording (`--mode slider`) saves nothing.

### Shot 4: the slider alone

`--mode slider` (or `COPYTHAT_PROMO_MODE=slider` in the environment) records the
finished rig without its steps: the scene is built and rigged before the
countdown, as fast as it can be, with no dialogs; then, after the countdown
and the flash, the Play slider is dragged from 0 to 100% over 3 s, eased, and
held for 1 s. The timeline has one beat, `slider`, with the caption "This is
Blender. This is the whole rig.".

### A dress rehearsal

`--shots` saves a screenshot at every beat, and of each dialog just before it
is confirmed, as `NN_name.png` in the folder, with `bpy.ops.screen.screenshot`,
which also captures popups. It adds a line per picture to `log.txt`, how
steadily the script's timer ran in each beat, and how many of the bloom's frames
the viewport really showed. Look at the pictures before the real take: each
should show the panel's change for its beat, the dialogs open and filled in,
text that reads, and nothing over the 3D view that should not be there. Taking
the pictures slows the run a little, so a rehearsal's times are not the take's.

The log also has a line for every stall of the main loop over 60 ms, with what
the show was doing, and the frames the bloom's playback really showed. On this
PC, at 2560x1440, the script's timer runs at a steady 60 Hz through every beat.
The stalls that remain are CopyThat's own work (New Move takes about 0.2 s,
Build about 75 ms) and Blender's (the 3D view being made large takes about 0.15 s,
and the first play of the bloom about 0.2 s, in which frame 1 simply stays on
screen). Without `--shots` the bloom played at 30 frames a second, 147 of its 151
frames shown.

### Tests

    "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" --background ^
        --factory-startup --python promo\user_script\test_headless.py

runs every scene headless against this repository's add-on, with every tween
jumped to its end: every Build must succeed, the add-on must print no Warning or
Error and Python no traceback, the flower must end as `flower_steps` makes it
(frame by frame), the timeline must hold every beat, and the slider mode must
play the same flower. It also bundles the script (`bundle.py`) and runs the
bundle. Add `-- TestName` to run one class.

## By hand

For the four older demos, or to see scene 5 in your own Blender. Nothing here is
needed for the promo recording above.

### Before you start (once)

1. Use **Blender 4.5 or newer**, with **CopyThat** turned on (Edit >
   Preferences > Add-ons, tick CopyThat). Scene 5 needs 0.18.1 or newer (Ring,
   Spread and Make Chain); scenes 1 to 4 need 0.15.0.
2. **File > New > General, and do not save it afterwards.** The script adds its
   demo scenes to the file, and changes the 3D view a little for the recording
   (Solid mode, the sidebar open). It puts the view, your scene and your tab
   back at the end, but the demo scenes stay in the file, so use a throwaway
   one.
3. Make the Blender window **fill the screen**. Keep the menus and the tabs on
   screen: they are part of the picture.
4. Set your recorder to 1920 x 1080 (or the window's own size), 30 frames per
   second, with the cursor not captured. OBS, Windows Game Bar (Win+Alt+R) and
   macOS (Shift+Cmd+5) all work. Turn on *Do Not Disturb* so no notification
   pops up in the video.

### Running it

1. In Blender, click the **Scripting** tab. In the text editor click **Open**
   and pick `copythat_promo.py`.
2. Choose the scenes: near the top, `SCENES = [5]` is the flower fast (the
   default); `SCENES = [1, 2, 3, 4]` plays the four older demos; `[3]` plays one.
3. **Start the recorder first**, then click back into Blender. The first
   seconds (the tab change, the countdown) get cut afterwards. If you need
   longer, change `COUNTDOWN = 5`.
4. Click **Run Script** (or Alt+P over the text). Move the mouse pointer to a
   bottom corner. Blender jumps to the **Layout** tab and counts down 5, 4, 3,
   2, 1. **Hands off the mouse and keyboard** until it is over: do not press
   Ctrl+Z or Esc.
5. When the last scene has played and you are in your own scene and tab again,
   it is finished. Stop the recording.

Run by hand there is no simulated input, so scene 5 does its Ring and Spread
steps without opening their dialogs, and the sidebar keeps its width. Captions
are drawn in the viewport for scenes 1 to 4 (`CAPTIONS`, `CAPTION_SCALE`);
scene 5 draws none. Each demo is a **new scene** of its own ("CopyThat Promo 1
- One cube" and so on); a second take keeps the first, renamed "(old)". Scene 5
can also save the finished flower as a .blend (`SAVE_BLEND`, "The finished
flower as a file" above).

| Scene | What happens | About |
|---|---|---|
| 1 One cube | New Move, the cube glides up and turns, Record After, Build Sliders, then the Play slider goes 0, 1, 0 | 21 s |
| 2 Ride Along | One cube hops and turns, a second cube (turned a quarter) rides along from its own place, Lead +30 so it goes first, Play | 29 s |
| 3 Curved path | A cube goes from A to B, the path shows it cutting through a wall, Curve the Path, lift the middle in edit mode, Build, Play: it arcs over | 34 s |
| 4 Rig something real | The mechanical flower, step by step, then Animate and the whole bloom through the camera | 65 s |
| 5 Flower fast | The promo's recording, above | 60 s and the bloom |

### If something is not right

- **A box says "CopyThat is not switched on, or is older than 0.15.0"** (or
  0.18.1 for scene 5): Edit > Preferences > Add-ons, tick CopyThat, run again.
  The box closes when the pointer moves away from it, so keep the pointer still
  until you have read it. The same words are in the console.
- **A line under the countdown says "Scene 4 is left out" or "Scene 5 is left
  out"**: this copy of the script has no flower code in it. Use the repository's
  `promo/user_script/copythat_promo.py` (it finds `promo/flower` and
  `promo/checks` beside it) or run `python promo/user_script/bundle.py` for a
  single file in `dist/`.
- **The side panel is not on the CopyThat tab**: click the *CopyThat* tab once,
  then run again.
- **The captions are too small or too big**: they follow the height of the
  Blender window. Change `CAPTION_SCALE = 1.0` to 1.3 (bigger) or 0.8 (smaller).
- **The picture stutters**: close other programs. The script keeps real time, so
  a slow computer drops frames rather than slowing down.
- **You want to stop it early**: change `STOP = False` to `STOP = True` at the
  top of the script, run it, then change it back. (If the 3D view is filling
  the window for the final bloom, press **Ctrl+Space** over it first.)
- **The 3D view stays large after an error**: move the pointer over it and press
  **Ctrl+Space**.
- **Nothing happens, or a red caption says "Stopped"**: on Windows open the
  console with Window > Toggle System Console and run it again; the message is
  there, and in the red caption.
