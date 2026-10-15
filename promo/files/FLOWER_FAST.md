# Rig the mechanical flower fast, with CopyThat 0.17.1

The same flower as `FLOWER_STEPS.md`, rigged in far fewer steps. This file
holds only the parts that are modelled **once**: one outer petal, one inner
petal, the core, and one leaf of three segments. CopyThat 0.17.1 makes the
rest: **Ring** makes the other 7 outer petals, 5 inner petals and the second
leaf, **Make Chain** hangs the leaf segments from each other, and **Spread**
fills in the timing. It takes a few minutes. At the end one slider opens the
whole flower, exactly as the long way does.

|  | Long way (`FLOWER_STEPS.md`) | This way |
|---|---|---|
| Parts you select and pose | 9 | 6 |
| Clicks on objects, values typed or chosen, buttons pressed | about 77 | about 55 |
| Of those, Lead and Delay numbers typed | 20 | 6 |

## Before you start (once)

1. **Install CopyThat 0.17.1 (or newer):** Edit > Preferences > Add-ons >
   Install from Disk > `CopyThat-0.17.1.zip`, and tick it on. **Restart
   Blender** after installing, or the old version stays loaded. Then open
   Preferences > Add-ons, find **CopyThat**, and check that it says **Version
   0.17.1**, or a newer one. 0.17.0 chains the folded leaf in the wrong order,
   so step 2 would not work with it.
2. Get the flower into Blender, either way:
   - **Blender 5.2:** File > Open `CopyThat_flower_fast.blend`.
   - **Any Blender from 4.4:** File > New > General. Open the **Scripting**
     tab, click **New**, paste all of `make_flower_fast.py`, and press **Run
     Script** once. It adds a scene called **CopyThat Flower** and switches
     to it. Everything else in the file is left alone.
3. **Save the file now** (Ctrl+S). The render at the end is written next to it.
4. Set up the window so the recording shows what matters:
   - **Outliner** (top right): the parts are in the collection **CopyThat
     Flower**. Make it tall.
   - **Properties editor** (bottom right): the **Object** tab (orange square),
     **Transform** panel. You type into it.
   - 3D view: press **N**, click the **CopyThat** tab. **Keep the panel in
     view for the whole recording.** Make the sidebar wide.
   - Over the 3D view press **Numpad 0** (camera view; no Numpad: View >
     Cameras > Active Camera). You see the shut bud with a stem, one leaf and a
     pedestal. Shading **Solid**; Overlays: **Relationship Lines** off.
   - Timeline: **Auto Keying** off, current frame **1**.
5. Where the new buttons are (they appear once you have pressed New Move):

   | Button | Where |
   |---|---|
   | **Ring…** | in the Move 1 box, in the row under **Curve the Path** (greyed out until a part of the move is the active object) |
   | **Spread…** | on the **Timing** header (spreads Delays) and on the **Riding along** header (spreads Leads) |
   | **Make Chain** and **Curl** | at the top of the **Follows** section (click its header if it is closed). You use Make Chain; Curl is not needed here |

### How to pose a part

Click the part in the **Outliner** (a plain click selects only it). In the
Properties editor double-click the field named in the table, type the number,
press **Enter**. Rotations are in degrees; for a minus type the minus sign
first. **Rotation X** starts at 0 and turns the part about its own hinge:
positive swings a petal **out**, away from the stem. (Optional shortcut:
`R X X 75 Enter` over the 3D view does the same as typing 75 into Rotation X;
check the header says local X, and if it turns the wrong way press Ctrl+Z and
use the field.)

## 1. Select the six parts and press New Move

- **Do:** In the Outliner click **Outer Leader**, then Ctrl+click **Inner
  Leader**, **Core**, **Leaf 1**, **Leaf 2**, **Leaf 3**. Six objects are
  highlighted. In the CopyThat panel press **New Move**.
- **You see:** a box **Move 1** with **Parts [6 selected]**, **Before** with a
  tick, and the report "'Move 1': 6 part(s). Where they stand now is Before."
  A **CopyThat Rig** appears in the Outliner. Nothing moves. Leave **Pivot** on
  Origin: every hinge is already its part's origin.

## 2. Make Chain: the leaf segments hang from each other

- **Do:** in the Outliner click **Leaf 3**, Ctrl+click **Leaf 2**, then
  Ctrl+click **Leaf 1** last, so Leaf 1 is the active one (the brightest
  highlight). In the **Follows** section press **Make Chain**.
- **You see:** the report "Chain: Leaf 1 > Leaf 2 > Leaf 3". In the Outliner
  Leaf 2 now sits inside Leaf 1 and Leaf 3 inside Leaf 2, and each one's
  dropdown under Follows names the part before it.
- **Why Leaf 1 last:** the chain starts from the active part and goes on from
  each part to the one built from its far end. One press does all three.

## 3. Pose the flower open

Click each part (Shift+click the little arrow beside **Leaf 1** in the
Outliner to open the leaf), then type the number into the field.

| Part | Field | Type | You see |
|---|---|---|---|
| **Outer Leader** | Rotation X | 75 | the front petal swings out and down; the rest of the bud is just this one petal |
| **Inner Leader** | Rotation X | 45 | one inner petal leans out, seen through the gap |
| **Core** | Location Z | 1.47 | the glowing core lifts 18 cm (it was 1.29) |
| **Core** | Rotation Z | 60 | the core turns 60 degrees |
| **Leaf 1** | Rotation X | 28 | the first segment swings out; Leaf 2 and Leaf 3 go with it |
| **Leaf 2** | Rotation X | -145 | the second segment unfolds, taking Leaf 3 with it |
| **Leaf 3** | Rotation X | 172 | the tip unfolds: the leaf is one arch |

Mistake? Type the right number into the same field. The leader petals, the
core and the leaf are now in their bloom pose.

## 4. Record After

- **Do:** In the Move 1 box, on the **After** row, press **Record**.
- **You see:** the dot beside After becomes a tick, and the report says
  "'Move 1': After recorded for 6 part(s)."

## 5. Ring: the outer petals

- **Do:** In the Outliner click **Outer Leader** (a plain click: it is now the
  only selected part and the active one). In the Move 1 box press **Ring…**.
  A dialog opens. Set:

  | Field | Set to |
  |---|---|
  | Count | **8** |
  | Round | **World Origin** |
  | About | World Z (leave it) |
  | Linked copies | on (leave it) |
  | First Lead | 0 (leave it) |
  | Last Lead | **36** |

  Press **OK**.
- **You see:** seven shut petals appear in a ring round the stem, with the
  open Outer Leader standing out in front. In the Outliner: **Outer Leader 2**
  to **Outer Leader 8**. The report: "7 copies of 'Outer Leader' round the
  world origin ride along with it. Leads 0 to 36 out from it, both ways round."
  A **Riding along (7)** section appears, its Leads 9, 18, 27, 36, 27, 18, 9
  round the ring: Ring filled them in, both sides alike.
- **Why World Origin:** the stem stands on the world's origin, so the ring goes
  round the flower exactly. The 3D cursor does not matter.

## 6. Ring: the inner petals

- **Do:** click **Inner Leader**. Press **Ring…**. Set **Count 6** (that is the
  dialog's default), **Round: World Origin**, **Last Lead 42**. Press **OK**.
- **You see:** the report "5 copies of 'Inner Leader' round the world origin
  ride along with it. Leads 0 to 42 out from it, both ways round."
  **Inner Leader 2** to **6** appear, and **Riding along (12)**, the new
  Leads 14, 28, 42, 28, 14.

## 7. Ring: the second leaf

- **Do:** click **Leaf 1**. Press **Ring…**. Set **Count 2**, **Round: World
  Origin**. Leave the Leads at 0. Press **OK**.
- **You see:** the report "1 copy of 'Leaf 1' (3 joints each) round the
  world origin rides along with it, joint for joint." Ring copied the whole
  leaf, because Leaf 2 and Leaf 3 follow Leaf 1: **Leaf 1 2**, **Leaf 2 2**,
  **Leaf 3 2** stand on the opposite side of the stem. **Riding along (13)**
  has one row for it, "Leaf 1 2 +2".

## 8. Delays: Spread on the leaf, then two numbers

- **Do:** select the three leaf parts: click **Leaf 3**, Ctrl+click **Leaf 2**,
  Ctrl+click **Leaf 1**. Open the **Timing** section (click its header) and
  press **Spread…** on its header. A dialog opens. Set:

  | Field | Set to |
  |---|---|
  | Order | **Down a chain** (it should already say this) |
  | Only the selected | **tick it** |
  | First Delay | **0.10** |
  | Last Delay | **0.40** |

  Press **OK**.
- **You see:** the report "Spread the Delays of 3 parts from 0.1 to 0.4, down
  the chain." In Timing, **Leaf 1** reads 0.1, **Leaf 2** 0.25, **Leaf 3** 0.4;
  the others are still 0. (The long way types 0.2 for Leaf 2. 0.25 is what a
  straight spread gives, and nothing collides with it.)
- **Do:** in Timing double-click the Delay of **Inner Leader**, type **0.34**,
  Enter; and **Core**, type **0.40**, Enter. **Outer Leader** stays 0.
- **You see:** nothing moves yet. A Delay is "waits this long before starting".
  The riders (the ring copies) have no Delay: they follow their leader.

## 9. Ease, Build, Animate, Play

- **Do:** In the Move 1 box, the dropdown under the After row says **Even
  speed**. Choose **Smooth**. Press the big **Build Sliders** button.
- **You see:** the report "21 part(s) on 1 slider(s). 6 object(s) were given a
  bone and bound. 15 object(s) now ride along. 2 part(s) hung from the part
  they follow." A **Move 1** slider appears, with **Frames [48] [Animate]**.
- **Try it:** drag **Move 1** from 0 to 100%. All 21 parts open together: the
  wave round the outer petals, the inner petals, the core, both leaves. Drag it
  back to **0**.
- **Do:** timeline on **frame 1**. Type **150** in **Frames**. Press
  **Animate**. Over the 3D view press **Numpad 0**, then **Space**.
- **You see:** the report "'Move 1' plays over frames 1 to 151." The flower
  blooms: back petals first, the wave round to the front, the inner petals and
  the core last, the leaves unrolling, the camera pushing in and orbiting. Esc
  stops it; Shift+Left goes back to frame 1. For the glow, use **Material
  Preview**; the full look is the Cycles render.

## Cheat sheet

Every value. **Shut** is what the field says before you type.

### Pose

| # | Object | Field | Shut | Type |
|---|--------|-------|------|------|
| 1 | Outer Leader | Rotation X | 0 | 75 |
| 2 | Inner Leader | Rotation X | 0 | 45 |
| 3 | Core | Location Z | 1.29 | 1.47 |
| 4 | Core | Rotation Z | 0 | 60 |
| 5 | Leaf 1 | Rotation X | 0 | 28 |
| 6 | Leaf 2 | Rotation X | 0 | -145 |
| 7 | Leaf 3 | Rotation X | 0 | 172 |

### Make Chain

Select all three leaf parts, Leaf 1 clicked last (the active one), then press
Make Chain once.

| Press | Select | Active |
|-------|--------|--------|
| 1 | Leaf 1, Leaf 2, Leaf 3 | Leaf 1 |

### Ring

Click the part so it is the only one selected, press **Ring…**, set these:

| Part | Count | Round | About | Linked copies | First Lead | Last Lead |
|------|-------|-------|-------|---------------|------------|-----------|
| Outer Leader | 8 | World Origin | World Z | on | 0 | 36 |
| Inner Leader | 6 | World Origin | World Z | on | 0 | 42 |
| Leaf 1 | 2 | World Origin | World Z | on | 0 | 0 |

### Spread

On the **Timing** header, with these parts selected first.

| Order | Only the selected | First Delay | Last Delay | Select first |
|-------|-------------------|-------------|------------|--------------|
| Down a chain | on | 0.10 | 0.40 | Leaf 1, Leaf 2, Leaf 3 |

### Delay

Typed by hand in Timing. Outer Leader stays 0.

| Part | Delay |
|------|-------|
| Inner Leader | 0.34 |
| Core | 0.40 |

### Other

| Setting | Value |
|---------|-------|
| Ease | Smooth |
| Frames | 150 |

Order: New Move, Make Chain, Pose, Record After, Ring (Outer Leader,
Inner Leader, Leaf 1), Spread on the leaf, two Delays, Ease, Build Sliders,
frame 1, Frames, Animate, camera view, Play.

## If something looks wrong

| You see | Do |
|---|---|
| The Chain report says "Leaf 1 > Leaf 3 > Leaf 2" | The old CopyThat 0.17.0 is still loaded. Ctrl+Z, install 0.17.1, **restart Blender**, check the version, and press Make Chain again. |
| The Chain report starts from another leaf part | Leaf 1 was not the active one. Ctrl+Z, select the three again with Leaf 1 clicked last. |
| **Ring…** is greyed out, or says a part "rides along" | The active object is not a leader. Click **Outer Leader** (not "Outer Leader 2"), **Inner Leader** or **Leaf 1** in the Outliner. |
| Ring says "Every place round that ring already has a copy" | You pressed it twice. Nothing was added; carry on. |
| The ring is lopsided, or is round the wrong point | **Round** was left on 3D Cursor with the cursor off the origin. Ctrl+Z, press Ring… again and choose **World Origin**. |
| Spread says none of the parts is selected | Select the three leaf parts first, or untick Only the selected (then it also writes Outer Leader, Inner Leader and Core: retype those). |
| A Delay or Lead did not change | The Timing section was not open when you looked, or Spread was pressed on the Riding along header instead (that one spreads Leads). |
| Report after Build says "not recorded yet" | You skipped step 4. Press Record on After, then Build again. |
| A red "Build to put it into effect" under Follows | Press **Build Sliders**. |
| A red box "Auto Keying is on" | Switch off the record dot in the timeline, press **Lift Those Keyframes**, Build again. |
| The Play slider does nothing | Press Build Sliders again after the last change. |
| After Build, a part was moved by hand | Ctrl+Z, or press **To Before**, then Build. Do not drag parts after Build. |

## Recording tips

- Keep the **CopyThat panel**, the **Outliner** and the **Properties editor**
  on screen. When a dialog opens, leave the mouse where it is and read the
  field names aloud (or write them on screen): Count, Round, Last Lead.
- Pause a beat after each press and let the report line settle. Say what each
  step is for: "one petal becomes a ring", "Spread fills in the timing".
- Show the payoff twice: drag the **Move 1** slider after Build, then press
  Space after Animate.
- The long way is `FLOWER_STEPS.md`. If you show both, show the counts in the
  table at the top.

## Render it

1. **Save the file** (Ctrl+S). The movie is written next to it.
2. **GPU:** Edit > Preferences > System > **Cycles Render Devices**: pick OptiX
   or CUDA (NVIDIA), HIP (AMD), Metal (Apple) or oneAPI (Intel), and tick your
   graphics card. The scene is already set to **GPU Compute**, and falls back
   to the CPU if no GPU is ticked.
3. **Render > Render Animation** (Ctrl+F12). It renders frames 1 to 210 at
   1920 x 1080 into one H.264 movie, `CopyThat_flower_0001-0210.mp4`, in the
   folder of the .blend. Already set: 512 samples with adaptive sampling
   (noise threshold 0.01), OpenImageDenoise, motion blur, perceptually
   lossless quality.
4. **Slow?** Go to frame 120 and press **F12** to time one frame (times 210).
   To go faster lower **Max Samples** in Render Properties > Sampling > Render
   (512 down to 128, or 64): the denoiser keeps it clean. Leave the rest alone.
5. If Blender cannot write the file, the .blend was not saved. Save it, or set
   the path under Output Properties > Output.

## Sending the files

If the movie or the .blend is over 30 MB, split it with 7-Zip: right-click the
file > 7-Zip > **Add to archive...** > set **Split to volumes, bytes** to
`29M` > OK. Send all the parts (`.7z.001`, `.7z.002`, ...) together. The
receiver puts them in one folder and opens the `.001` with 7-Zip.
