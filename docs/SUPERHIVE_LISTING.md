# CopyThat on Superhive: the product page

The product description in the order of Auto Unwrap 2's page. Paste it into the
description editor.

**The media files** are in `dist/store/`, made by
`promo/store/make_store_media.py`:
- `gifs/` (the description's GIFs);
- `images/` (the gallery, 2400x1200);
- `film_preview.mp4`.

**Before pasting:**
- At each `![...](gifs/...)` line, upload that file in the editor and keep its
  alt text.
- Replace `VIDEO_URL` with the film's YouTube link once it is uploaded.
- The full user guide goes in the Documentation tab (`docs/SUPERHIVE_PAGE.md`).

**The listing's fields:**
- **Title:** CopyThat – One-Slider Rigs for Machines and Mechanical Models
- **Short description:** Record a move. Get a slider. Pose your parts twice and
  CopyThat builds the rig: one slider plays the whole move, every part on its own
  timing.
- **Gallery** (featured first, all 2:1; none shows the Blender logo or the word
  Blender):
  1. `01_featured.jpg`
  2. `02_rigged_in_1m10.jpg`
  3. `03_ring_dialog.jpg`
  4. `04_spread_dialog.jpg`
  5. `05_twenty_one_parts.jpg`
  6. `06_ring_feature.jpg`
  7. `07_rendered.jpg`
- **Prices** (suggested, NemVe3D decides): Personal, 1 seat, $24; Studio, 5+
  seats, $79.
- **Licence:** GPL-3.0-or-later.
- **Blender:** 4.5 to 5.2.

---

# Record a move. Get a slider.

Pose your parts where they start and where they end, and press Build. CopyThat
makes the rig for you and gives back **one slider that plays the whole move**,
with every part on its own timing.

**No rig to build** · **Timing per part** · **Copies that follow**

- **No rig to build.** Works on loose objects. CopyThat adds the bones, binds
  the parts and wires the slider.
- **Timing per part.** A delay for each part, so they leave in order and
  overlap like a real machine.
- **Copies that follow.** Ring one petal, blade or bolt into many. Every copy
  rides along with the one you posed.

![Build Sliders, then one slider blooms the flower](gifs/rig_build_bloom.gif)

## Rig this flower in 1:10

21 parts, one slider, and the clock running. The film shows every click at a
normal pace, and **the flower file comes with the add-on**, so you can do the
same.

▶ Watch the film: VIDEO_URL

## How it works

**1 · Pose it, record it.** Select the parts and press **New Move**: where they
stand is Before. Move them and press **Record** on After.

![Pose it, record it](gifs/idea_record.gif)

**2 · Build: one slider.** **Build Sliders** makes the bones, binds the parts
and puts the move on one slider, in the panel and as a handle in the viewport.

![Build, one slider](gifs/idea_build.gif)

**3 · As many parts as you like.** Every selected part shares the move, and
each one can wait its turn.

![Many parts, one move](gifs/idea_many.gif)

## The flower, step by step

Every action below is one you can repeat with the included file.

**Select the six parts, New Move.** Click in the Outliner, Ctrl+click the
rest, press New Move.

![Select the parts and press New Move](gifs/rig_select.gif)

**Pose it open, one value at a time.** Type each rotation into the Properties
editor. The leaf's three joints are three edits.

![Pose one value at a time](gifs/rig_pose.gif)

**Ring the petals.** One petal becomes eight: Count 8, Round World Origin, Lead
step 9, OK. The copies open in a wave round the stem.

![Ring the outer petals](gifs/rig_ring.gif)

**Spread the timing.** Delays down the leaf in one dialog, then two typed
delays for the inner petals and the core.

![Spread the delays](gifs/rig_spread.gif)

**Build, and drag.** Smooth, Build Sliders, and one slider blooms all 21
parts.

## By hand, or with CopyThat

| The flower's 21 parts | By hand | With CopyThat |
|---|---|---|
| Bones | Add, place and parent 21 bones; bind every part | **New Move** makes them |
| One control | Add a control bone and a driver for every bone | **Build Sliders**: one slider and a viewport handle |
| Staggered timing | Offset 21 sets of keys | A **Delay** per part, filled in by **Spread** |
| 12 more petals and a second leaf | Duplicate, rig and key each one | **Ring**: copies ride along with their leader |
| Leaf joints | Parent the chain, rotate each joint | **Make Chain**, **Curl** |
| Change it later | Re-key everything | **Pause** or record again, then **Build** |
| Send the file | Hope they have the same tools | It plays and renders with nothing installed |

## Twelve tools for the moves machines make

**01 · TIMING. Give every part its own delay.** A Delay says how long a part
waits before it starts. Parts leave in order and overlap, so a machine reads as
built instead of as one rubber object.

![01 Timing](gifs/f01_delays.gif)

**02 · SPREAD. Spread the timing into a wave.** One dialog fills every Delay,
or every copy's Lead: round a ring, down a chain, along an axis, by distance or
at random.

![02 Spread](gifs/f02_spread.gif)

**03 · PIVOT. Turn around any point you want.** Each part turns about its
origin, the 3D cursor or its base. The poses stay as recorded; the way between
them swings about the pivot.

![03 Pivot](gifs/f03_pivot.gif)

**04 · STEPS. Add steps in between.** Pose the middle of the move as well. Each
stretch between two poses gets its own speed.

![04 Steps](gifs/f04_steps.gif)

**05 · CURVES. Curve the path, then edit the curve.** A part follows a curve
you bend in edit mode. Its two ends always stay on Before and After.

![05 Curves](gifs/f05_curves.gif)

**06 · SPEED. Smooth, or perfectly even.** Even speed, Smooth, Slow start or
Slow stop, for each move.

![06 Speed](gifs/f06_speed.gif)

**07 · CHAIN. Chain parts, so the joints follow.** Make Chain hangs each
segment from the one before it in one click: a finger, a leaf, a crane arm.

![07 Chain](gifs/f07_chain.gif)

**08 · CURL. Curl a whole chain at once.** Bend the first joint, and Curl
repeats the bend down the chain.

![08 Curl](gifs/f08_curl.gif)

**09 · RING. Ring one part into many.** Copies round a centre ride along with
the part, each moving from its own place. Fill the gaps keeps the copies you
already modelled.

![09 Ring](gifs/f09_ring.gif)

**10 · MIRROR. Mirror the copies.** A copy can mirror its leader's move across
its own X, Y or Z: the leader's left becomes the copy's right.

![10 Mirror](gifs/f10_mirror.gif)

**11 · COMBINE. Combine moves under one control.** Play several moves one after
another from a single slider, or overlap them with a delay.

![11 Combine](gifs/f11_combine.gif)

**12 · ANIMATE. And animate it all in one click.** Set the frames and press
Animate: the slider is keyed from the current frame. Or drag the handle in the
viewport.

![12 Animate](gifs/f12_animate.gif)

![21 parts, one slider](gifs/together.gif)

## Built for real files

- **Plays without the add-on.** The rig is plain bones, constraints and simple
  drivers. Files open, play and render anywhere, even with Auto Run Python
  Scripts off.
- **Copies keep working.** Alt+D a whole rigged model: the copy gets its own
  slider and its own animation.
- **Edit after Build.** Rename or delete a part, change a delay, or press Pause
  and pose again: the next Build takes it in.
- **Look before you build.** The eye shows Before or After. Pause lets you pose
  freely, and To Before puts everything back.
- **It tells you what happened.** The report box says what each button did and
  what to do next, and turns red for a warning.
- **Bones too.** Record poses of an armature's own bones, not only loose
  objects.

## Perfect for

- Product reveals and packaging that opens
- Machines: hatches, lids, landing gear, robot arms
- Flowers, fans, and anything that unfolds
- Motion graphics and kinetic logos
- Kitbash and hard-surface models
- Anyone who has never built a rig

## What's included

- **CopyThat 0.20.2**, a Blender extension: drag the zip into Blender.
- **The flower file**, ready to rig: follow the film or the guide.
- **The flower guide**, every click and value of the film.
- **The full user guide**, in the Documentation tab.
- **Free updates.**

## Compatibility

- **Blender:** 4.5 LTS to 5.2.
- **Systems:** Windows, macOS and Linux. It is pure Python with no extra
  libraries.
- **Render engines:** any. The motion is a plain rig.
- **Licence:** GPL-3.0-or-later.

## Install

1. Edit > Preferences > Get Extensions, then the drop-down at the top right >
   Install from Disk, and pick `CopyThat-0.20.2.zip`.
2. Restart Blender.
3. Press N in the 3D view and open the CopyThat tab.

## What's new

- **0.20.2:**
  - The panel reads in full at the sidebar's usual width.
  - It stays on its rig when a part is deleted.
  - An outer ring of petals comes out whole even when the inner ring was made
    first.
- **0.20.1:** A fix for an error the installed panel showed at every redraw.
- **0.20.0:** A new panel: a branded header, gold icons, a big slider for each
  move, sections that fold, and a report box that turns red for a warning.

## FAQ

**Do I need to know how to rig?**
No. Select the parts, pose them, press Build.

**Does the finished file need CopyThat?**
No. It plays and renders without it.

**Can I change the move after Build?**
Yes. Press Pause and pose freely, or record a pose again, then Build.

**Is it for characters?**
It records the poses of any bones. It is made for machines and objects that
move as solid parts. For a character's skin and face, use a character rigging
tool.

**Where is the full guide?**
In the Documentation tab: every button, every dialog, and the flower step by
step.

---

Made by NemVe3D · creators.sa/nemve
