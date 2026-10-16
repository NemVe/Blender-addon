# Rig the mechanical flower with CopyThat, step by step

You will rig a gold flower by hand with CopyThat while your screen recorder
runs. It takes about 15 minutes. At the end one slider (and one keyed
timeline) opens the whole flower: 8 outer petals in a wave, 6 inner petals,
the glowing core rising and turning, and two leaves unrolling. Every number
you need is in this guide: type what it says.

The flower starts shut. It is already built, named, and set up so that each
petal or leaf opens by **typing one number** into one field.

## Before you start (once)

1. **Install CopyThat 0.18.1 or newer.** It is a Blender **extension**, and it
   needs **Blender 4.5 or newer** (4.4 cannot run it). If an older RigMoves or
   CopyThat is listed under Edit > Preferences > **Add-ons**, switch it off and
   remove it first. Then drag the zip (the newest, `CopyThat-0.18.x.zip`) into
   Blender, or use Edit > Preferences > **Get Extensions** > the drop-down at
   the top right > **Install from Disk**. **Restart Blender** after
   installing. Then open Preferences > Add-ons, find **CopyThat**, and check
   the version it shows. An older CopyThat shows **First Lead** and **Last
   Lead** in Ring's dialog instead of **Lead step**, and step 5 would not work
   with it.
2. Get the flower into Blender, either way:
   - **Blender 5.2:** File > Open `CopyThat_flower_bare.blend`.
   - **Any Blender from 4.5:** File > New > General. Open the **Scripting**
     tab, click **New**, paste all of `make_flower_bare.py`, and press
     **Run Script** (the triangle) once. It adds a scene called **CopyThat
     Flower** and switches to it. Everything else in the file is left alone.
3. **Save the file now** (Ctrl+S). The render at the end is written next to it.
4. Set up the window so the recording shows what matters:
   - **Outliner** (top right): all the parts are in the collection **CopyThat
     Flower**. Drag its edge to make it tall.
   - **Properties editor** (bottom right): click the **Object** tab (the
     orange square). Its **Transform** panel has Location, Rotation, Scale.
     You will type into it.
   - In the **3D view** press **N**, then click the **CopyThat** tab on the
     right edge of the sidebar. **Keep this panel visible for the whole
     recording**, and drag the sidebar's left edge to make it wider.
   - Hover over the 3D view and press **Numpad 0** to look through the camera
     (no Numpad: View > Cameras > Active Camera). You see the shut gold bud
     on its black pedestal. (The studio is hidden in the 3D view on purpose;
     it still renders.)
   - Shading **Solid**. In Overlays switch off **Relationship Lines**.
5. In the timeline the **Auto Keying** record dot must be **off**, and the
   current frame **1**.

### How to pose a part

Click the part in the **Outliner** (a plain click: only that one is selected).
In the Properties editor, **double-click the field** named in the table, type
the number, press **Enter**. Rotations are in degrees; for a minus, type the
minus sign first. Each part's **Rotation X** starts at 0 and turns it about
its own hinge: positive swings a petal **out**, away from the stem.

*Optional shortcut:* with only that part selected and the mouse over the 3D
view, `R X X 75 Enter` does the same as typing 75 into Rotation X. Check the
header says **local X**. If a part turns the wrong way, Ctrl+Z and use the
field instead.

## 1. Select the nine parts and press New Move

- **Do:** In the Outliner click **Outer Leader**. Hold **Ctrl** and click
  **Inner Leader**, **Core**, **Leaf A1**, **Leaf A2**, **Leaf A3**,
  **Leaf B1**, **Leaf B2**, **Leaf B3**. Nine objects are highlighted. In
  the CopyThat panel press **New Move** (the big button; the box above it
  says "9 object(s) selected").
- **You see:** a box **Move 1** with **Parts [9 selected]**, **Before** with
  a tick, **After** with a dot, and the report "'Move 1': 9 part(s). Where
  they stand now is Before. Move them, then Record After." A **CopyThat Rig**
  appears in the Outliner. Nothing moves. Leave **Pivot** on **Origin**:
  every hinge is already its part's origin.
- **Why these nine:** the two leaders are the petals you pose and record. The
  other 13 petals will ride along with them (step 5).

## 2. Follows: the leaves hang from each other

- **Do:** In the panel, open the **Follows** sub-panel (below the Move box). It
  has a dropdown beside each part. Click the dropdown and pick (cheat sheet,
  "Follows"): **Leaf A2** follows **Leaf A1**, **Leaf A3** follows **Leaf A2**,
  **Leaf B2** follows **Leaf B1**, **Leaf B3** follows **Leaf B2**. Leave the
  others empty.
- **You see:** nothing moves. In the Outliner each leaf segment now sits
  inside the one it follows. **Do this before posing the leaves**: turning
  Leaf A1 then carries A2 and A3, so each segment's angle is measured against
  the one before.

## 3. Pose the flower open

Click each part (Shift+click the little arrow beside **Leaf A1** and **Leaf B1**
to open the leaf segments in the Outliner), then type the number into the
field.

| Part | Field | Type | You see |
|---|---|---|---|
| **Outer Leader** | Rotation X | 75 | the front petal swings out and down; the other 7 stay shut |
| **Inner Leader** | Rotation X | 45 | one inner petal leans out, seen through the gap |
| **Core** | Location Z | 1.47 | the glowing core lifts 18 cm (it was 1.29) |
| **Core** | Rotation Z | 60 | the core turns 60 degrees |
| **Leaf A1** | Rotation X | 28 | the first segment swings out; A2 and A3 go with it |
| **Leaf A2** | Rotation X | -145 | the second segment unfolds, taking A3 with it |
| **Leaf A3** | Rotation X | 172 | the tip unfolds: the leaf is one arch |
| **Leaf B1** | Rotation X | 24 | as A1, on the other side |
| **Leaf B2** | Rotation X | -145 | as A2 |
| **Leaf B3** | Rotation X | 172 | as A3: the second leaf is one arch |

Mistake? Type the right number into the same field; the field always means
the final pose. At the end the two leaders, the core and both leaves are in
their bloom pose; the other 13 petals are still shut.

## 4. Record After

- **Do:** In the Move 1 box, on the **After** row, press **Record**.
- **You see:** the dot beside After becomes a tick, an eye icon appears beside
  it, and the report says "'Move 1': After recorded for 9 part(s)." Nothing
  moves.

## 5. Ring: the other petals are picked up

The other 13 petals are already modelled round the stem. **Ring** with **Use
what's there** finds them, makes each one ride along with its leader, and makes
nothing new. Two rounds, one for each ring of petals. The leader must be the
active object: a plain click on it in the Outliner. Blender keeps the numbers
of the last time a dialog was used, so a Ring dialog opens showing the last
Ring you did, even one from an earlier take, until you restart Blender. Check
every row against the table.

- **Outer petals. Do:** In the Outliner click **Outer Leader**. In the Move 1
  box press **Ring…** (in the row under **Curve the Path**). A dialog opens.
  Set:

  | Field | Set to |
  |---|---|
  | Use | **Use what's there** |
  | Count | **8** |
  | Round | **World Origin** |
  | About | World Z (leave it) |
  | Linked copies | greyed out (leave it) |
  | Lead step | **9** |

  Press **OK**.
- **You see:** nothing new in the Outliner: **Outer 2** to **Outer 8** are taken
  up as they are. The report begins "7 modelled copies of 'Outer Leader' round
  the world origin ride along with it (nothing new made)." It then names some
  inner petals under "Left out": Ring saw them standing near the ring, and
  left them alone because they are not copies of the outer petal. That is
  right; they are next. The report ends "Leads step by 9, out from it both
  ways round." A **Riding along (7)** section appears, one row per petal, with
  the Leads 9, 18, 27, 36, 27, 18, 9 round the ring: Ring wrote them, both
  sides alike.
- **Inner petals. Do:** click **Inner Leader**. Press **Ring…**. The dialog
  opens with the numbers of the outer Ring. Set:

  | Field | Set to |
  |---|---|
  | Use | Use what's there (it already says this: leave it) |
  | Count | **6** (it shows 8: type 6) |
  | Round | World Origin (it already says this: leave it) |
  | About | World Z (leave it) |
  | Linked copies | greyed out (leave it) |
  | Lead step | **14** (it shows 9) |

  Press **OK**.
- **You see:** nothing new again. The report "5 modelled copies of 'Inner
  Leader' round the world origin ride along with it (nothing new made). Leads
  step by 14, out from it both ways round." **Riding along (12)**, the new
  Leads 14, 28, 42, 28, 14.
- **Why World Origin:** the stem stands on the world's origin, so the ring goes
  round the flower exactly. The 3D cursor does not matter.
- **Why Use what's there:** Ring looks at what stands where a copy of the
  leader would stand and takes up the objects that are exact copies of the
  leader's mesh. It leaves anything else as it is and says so. Nothing is
  copied, so nothing is added.
- **Why Lead step:** each petal's Lead is the Lead step times how far it is out
  from the leader, both ways round: the two petals next to the leader get 9,
  the two next to those 18, then 27, and the petal opposite gets 36. Above 0
  means "goes first", so the **back** petals open first, a wave runs round both
  sides, and the front petal, the leader, opens last. Nothing moves until
  Build.

## 6. Timing: the Delays

- **Do:** Click the header **Timing** to open it. It lists the nine parts that
  are not riders. Double-click each **Delay** field, type the number, press
  Enter (cheat sheet, "Delay"). Outer Leader stays 0.
- **You see:** nothing moves. A Delay is "waits this long before starting": the
  inner petals, the core and the leaves start later, and each leaf segment
  starts after the one before.

## 7. Ease

- **Do:** In the Move 1 box, the dropdown under the After row says **Even
  speed**. Choose **Smooth**.

## 8. Build Sliders

- **Do:** Press the big **Build Sliders** button at the bottom of the panel.
- **You see:** the report "21 part(s) on 1 slider(s). 9 object(s) were given a
  bone and bound. 12 object(s) now ride along. 4 part(s) hung from the part
  they follow." (If it says something is too long, or not recorded, check the
  Lead step, the Delay numbers and step 4.) A **Move 1** slider appears in the
  box, with a key button, and a row **Frames [48] [Animate]**. A handle arrow
  stands over the flower.
- **Try it:** drag the **Move 1** slider from 0 to 100%. All 21 parts open as
  one: the wave round the petals, the core, the leaves. Drag it back to **0**.

## 9. Frames 150 and Animate

- **Do:** Timeline on **frame 1**. In the **Frames** field type **150**. Press
  **Animate**.
- **You see:** the report "'Move 1' plays over frames 1 to 151." Frames 151 to
  210 hold the open flower. The camera move and the core's glow are already
  keyed in the file over the same 1 to 151.

## 10. Camera view and Play

- **Do:** Over the 3D view press **Numpad 0** (camera view), then **Space** to
  play. Esc stops it; **Shift+Left** goes back to frame 1.
- **You see:** the back petals lift first, a wave runs round to the front, the
  inner petals and the core open last, the leaves unroll, the camera pushes in
  and orbits. For the glow, switch the viewport to **Material Preview**. The
  full look, with studio lights and bloom, is the Cycles render.

## Cheat sheet

Every value. **Shut** is what the field says before you type.

### Selections

| Step | Select | Active (selected last) |
|---|---|---|
| New Move | Outer Leader, Inner Leader, Core, Leaf A1, A2, A3, Leaf B1, B2, B3 | any |

### Pose

| # | Object | Field | Shut | Type |
|---|--------|-------|------|------|
| 1 | Outer Leader | Rotation X | 0 | 75 |
| 2 | Inner Leader | Rotation X | 0 | 45 |
| 3 | Core | Location Z | 1.29 | 1.47 |
| 4 | Core | Rotation Z | 0 | 60 |
| 5 | Leaf A1 | Rotation X | 0 | 28 |
| 6 | Leaf A2 | Rotation X | 0 | -145 |
| 7 | Leaf A3 | Rotation X | 0 | 172 |
| 8 | Leaf B1 | Rotation X | 0 | 24 |
| 9 | Leaf B2 | Rotation X | 0 | -145 |
| 10 | Leaf B3 | Rotation X | 0 | 172 |

### Follows

| Part | Follows |
|------|---------|
| Leaf A2 | Leaf A1 |
| Leaf A3 | Leaf A2 |
| Leaf B2 | Leaf B1 |
| Leaf B3 | Leaf B2 |

### Ring

Click the leader in the Outliner (a plain click), press **Ring…**, set these.
The dialog remembers the last Ring, so check every row.

| Part | Use | Count | Round | About | Lead step |
|------|-----|-------|-------|-------|-----------|
| Outer Leader | Use what's there | 8 | World Origin | World Z | 9 |
| Inner Leader | Use what's there | 6 | World Origin | World Z | 14 |

### Lead (Ring writes these; nothing to type)

| Object | Lead |
|--------|------|
| Outer 2 | 9 |
| Outer 3 | 18 |
| Outer 4 | 27 |
| Outer 5 | 36 |
| Outer 6 | 27 |
| Outer 7 | 18 |
| Outer 8 | 9 |
| Inner 2 | 14 |
| Inner 3 | 28 |
| Inner 4 | 42 |
| Inner 5 | 28 |
| Inner 6 | 14 |

### Delay

| Part | Delay |
|------|-------|
| Outer Leader | 0 |
| Inner Leader | 0.34 |
| Core | 0.40 |
| Leaf A1 | 0.10 |
| Leaf A2 | 0.20 |
| Leaf A3 | 0.40 |
| Leaf B1 | 0.10 |
| Leaf B2 | 0.20 |
| Leaf B3 | 0.40 |

### Other

| Setting | Value |
|---------|-------|
| Ease | Smooth |
| Frames | 150 |

Order: New Move, Follows, Pose, Record After, Ring (outer, then inner), Delay,
Ease, Build Sliders, frame 1, Frames, Animate, camera view, Play.

## If something looks wrong

| You see | Do |
|---|---|
| A petal leans in, or a leaf bends the wrong way | A field has the wrong number or sign. Type the right one from the cheat sheet into the same field. |
| The Rotation X field does not start at 0 | You rotated the part by hand before. Type 0, then the number. |
| **Ring…** is greyed out, or says a part "rides along" | The active object is not a leader. Click **Outer Leader** (or **Inner Leader**) in the Outliner, not "Outer 2". |
| Ring takes up nothing, or says copies stand off the ring | **Round** was left on 3D Cursor with the cursor off the origin, or **Count** is wrong. Ctrl+Z, press **Ring…** again with **World Origin** and the right **Count**. |
| Ring says "Every place round that ring already has a copy" | You pressed it twice. Nothing was added; carry on. |
| Ring's dialog shows **First Lead** and **Last Lead** | An older CopyThat is loaded. Install 0.18.1 or newer, **restart Blender**, and check the version under Preferences > Add-ons > CopyThat. |
| The report after Build says "not recorded yet" | You skipped step 4. Press Record on After, then Build again. |
| A red box "Auto Keying is on" | Switch off the record dot in the timeline, press **Lift Those Keyframes**, Build again. |
| The Play slider does nothing | Press Build Sliders again, after the last change. |
| After Build, a part was moved by hand | Ctrl+Z, or press **To Before**, then Build. Do not drag parts after Build. |

## Recording tips

- Keep the **CopyThat panel**, the **Outliner** and the **Properties editor**
  on screen the whole time: the viewer follows the buttons and the numbers,
  not only the flower.
- Pause a beat after each press and let the report line settle. Say, or write
  on screen, what each step is for: "record where it ends up", "Ring picks up
  the other petals", "back petals go first".
- When a dialog opens, leave the mouse where it is and read the field names
  aloud (or write them on screen): Use, Count, Round, Lead step.
- Zoom the recording to the three areas, not the whole desktop.
- Show the payoff twice: drag the **Move 1** slider after Build (the wave runs
  round the petals), then press Space after Animate (the camera move).

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
