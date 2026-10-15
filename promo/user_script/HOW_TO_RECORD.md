# Recording the CopyThat demo

You run one script in Blender while your screen recorder is recording. The
script plays four demos by itself, with captions, in Blender as it normally
looks: the menus, the tabs, the outliner, the properties editor, the timeline
and the 3D view with its toolbar. The CopyThat panel is open on the right of
the 3D view, so you can watch it change as each step is done. It takes about
**2 minutes 50** from the countdown to the end. You do not click anything
while it plays.

The file to run is `copythat_promo.py`.

## Before you start (once)

1. Use **Blender 4.4 or newer**, with **CopyThat 0.15.0** (or newer) turned on
   (Edit > Preferences > Add-ons, tick CopyThat).
2. **File > New > General, and do not save it afterwards.** The script adds four
   demo scenes to the file, and changes the 3D view a little for the recording
   (Solid mode, the sidebar open). It puts the view, your scene and your tab
   back at the end, but the demo scenes stay in the file, so use a throwaway
   one.
3. Make the Blender window **fill the screen** (the maximise button in its
   corner, or double-click its title bar). Keep the menus and the tabs on
   screen: they are part of the picture.
4. Set your recorder to **1920 x 1080**, 30 frames per second. A 16:9 screen is
   best; the script frames the picture for the 3D view's own shape.
   - **Easiest:** set your screen to 1920x1080 for the session (Windows:
     Settings > System > Display; macOS: System Settings > Displays, pick a
     scaled setting that says 1920x1080). In **OBS**, Settings > Video: set
     *Base (Canvas) Resolution* and *Output (Scaled) Resolution* to 1920x1080
     and *FPS* to 30. Add a *Display Capture* (or a *Window Capture* of
     Blender).
   - **If you keep your screen's own size** (1440p, 4K, a laptop): in OBS set
     *Base (Canvas) Resolution* to your screen's size, and *Output (Scaled)
     Resolution* to 1920x1080 only if the screen is 16:9. Then right-click the
     capture in the Sources list, **Transform > Fit to Screen** (Ctrl+F). On a
     16:10 screen leave canvas and output the same size, and tell us when you
     send it. On a Retina Mac the capture is bigger than 1080p; fit it the
     same way.
   - In the capture's properties, **untick Capture Cursor**. Settings >
     Output > Recording: quality High, format MKV or MP4.
   - **Windows Game Bar** (Win+Alt+R) or **macOS** (Shift+Cmd+5) work too.
     Set your screen to 1920x1080 first if you can.
5. Turn on *Do Not Disturb* (Windows: Focus Assist) so no notification pops up
   in the video.

## Practice run

Do the **Recording** steps below once with the recorder **off**, to check that
all four scenes play on your computer. It takes under three minutes. Then do
it again for real.

## Recording

1. In Blender, click the **Scripting** tab (the row of tabs at the top).
2. In the text editor, click **Open** and pick `copythat_promo.py`.
3. **Press Record in your recorder first**, then click back into Blender. The
   first 8 seconds or so (the tab change, the countdown) get cut afterwards.
   - If you have a recorder hotkey (Game Bar: Win+Alt+R; OBS: Settings >
     Hotkeys > Start Recording) or a second screen, you can press Record
     during the countdown instead.
   - If you need longer to switch windows, change `COUNTDOWN = 5` near the top
     of the script to 12 or 15.
4. Click the **Run Script** button (the triangle in the text editor's
   header), or press **Alt+P** with the pointer over the text.
5. Move the mouse pointer to a bottom corner, out of the way.
6. Blender jumps to the **Layout** tab, and a big countdown shows in the 3D
   view: 5, 4, 3, 2, 1.
7. **Hands off the mouse and keyboard** until it is over. Do not press Ctrl+Z
   or Esc.
8. When the last scene has played and you are in your own scene and tab
   again, it is finished. **Stop the recording.**
9. Name the file something like `copythat_take1` and send it.

## What you will see

Captions sit inside the 3D view, clear of the toolbar on the left and the
panel on the right. The objects a step works on are selected, so their orange
outlines show what is happening, and each step stays on screen long enough to
read.

| Scene | What happens | About |
|---|---|---|
| 1 One cube | New Move, the cube glides up and turns, Record After, Build Sliders, then the Play slider goes 0, 1, 0 | 21 s |
| 2 Ride Along | One cube hops and turns, a second cube (turned a quarter) rides along from its own place, Lead +30 so it goes first, Play | 29 s |
| 3 Curved path | A cube goes from A to B, the path shows it cutting through a wall, Curve the Path, lift the middle in edit mode, Build, Play: it arcs over | 34 s |
| 4 Rig something real | The mechanical flower, step by step: name the parts, open one petal by hand, Ride Along, Lead, the inner ring's Delay, the leaves' Follows. After each step the Play slider goes 0, 1, 0 to show what it added. Then Animate, and the whole bloom plays with the 3D view made large, through the camera | 65 s |

Each demo is a **new scene** of its own ("CopyThat Promo 1 - One cube" and so
on). When it ends the script gives you back the 3D view's usual look, your own
scene and the tab you started in. The four demo scenes stay in the file; do
not save it.

## Sending the recording

The chat takes files up to 30 MB. Split the video with **7-Zip** (free, from
7-zip.org), so nothing is lost:

1. Right-click the video, then **7-Zip > Add to archive...**
2. In **Split to volumes, bytes**, type `29M`, then press **OK**.
3. Drag every part (`.7z.001`, `.7z.002`, and so on) into the chat.

Don't shrink the video with a converter: it lowers the quality, and this
footage goes into the final video.

## Doing it again

Just run it again, the same way. A run that is still going is stopped first,
and earlier takes are kept in the file, renamed with "(old)" at the end.

To record **one scene only**, open the script and change the line near the top
to, for example, `SCENES = [3]`. It starts with the countdown as usual.

## If something is not right

- **A box says "CopyThat is not switched on, or is older than 0.15.0"**:
  Edit > Preferences > Add-ons, tick CopyThat, run again. The box closes when
  the pointer moves away from it, so keep the pointer still until you have read
  it. The same words are in the console if you missed it.
- **Only scenes 1 to 3 play, and a box or a line under the countdown says
  "Scene 4 is left out"**: this copy of the script has no flower in it. Tell
  us, we will send a new one.
- **The side panel is not on the CopyThat tab**: click the *CopyThat* tab at
  the right edge of the panel once, then run again.
- **The captions are too small or too big**: they follow the height of the
  Blender window, so they match the picture on any screen. To trim them,
  change `CAPTION_SCALE = 1.0` near the top to 1.3 (bigger) or 0.8 (smaller).
- **The picture stutters**: close other programs. The script keeps real time,
  so a slow computer drops frames rather than slowing down.
- **You want to stop it early**: click the **Scripting** tab, change
  `STOP = False` to `STOP = True` at the top of the script, run it, then change
  it back to `False`. (If the 3D view is filling the window for the final
  bloom, press **Ctrl+Space** with the pointer over it first.)
- **The 3D view stays large after an error**: move the pointer over it and
  press **Ctrl+Space**.
- **Nothing happens, or a red caption says "Stopped"**:
  - Windows: open the console with Window > Toggle System Console, run it
    again, and send us a screenshot of what it says.
  - macOS or Linux: there is no such menu. Take a screenshot or a photo of the
    red caption, which holds the message, and if you can, start Blender from
    a Terminal and send what it prints.
