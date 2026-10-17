# CopyThat

**Record a move, get a slider. Animate machines, flowers, fingers and fans without building a rig first.**

CopyThat is a Blender add-on for the kind of animation where parts go from one place to another: a lid that swings open, a flower that blooms, a finger that curls, a fan that unfolds. You select the objects that move together, press **New Move** (that records where they stand), move them by hand to where they should end up, and record that. Press **Build Sliders** and CopyThat does the rigging for you: it makes the bones, binds each object to its bone and wires everything to one **Play** slider and a handle you can grab in the viewport.

Then it helps with everything that makes a move look designed instead of slid across: steps in between, a speed for each stretch, easing, delays, curved paths, and parts that hang from other parts. Four tools (**Ring**, **Spread**, **Make Chain** and **Curl**) remove the copying and typing that eight petals, three finger joints or a dozen dominoes would otherwise cost. Record one petal and the rest copy it, each from its own place and facing its own way.

Everything is explained below, step by step. You do not need to know rigging.

- Author: **NemVe3D** (https://creators.sa/nemve)
- Licence: **GPL-3.0-or-later** (the GNU General Public License, version 3 or any later version)
- Needs: **Blender 4.5 or newer**
- In the download: one `.zip` file, `CopyThat-0.19.3.zip`, which is the Blender extension (see Installation)
- Support: through this product's page on Superhive, or at https://creators.sa/nemve (see Support and credits at the end)
- Where it lives: the 3D Viewport sidebar (press **N**), tab **CopyThat**

## What you can make

- **Machines:** lids, hatches, doors, drawers, pistons, panels that slide out and swing clear.
- **Flowers:** record one petal, make a ring of them, and let them open one after another in a wave.
- **Fingers and tentacles:** joints that each bend at their own knuckle and carry the ones after them.
- **Fans:** blades round a hub that open all together or one by one.
- **Dominoes:** a row that topples in a wave, with no typing a number into every domino.
- **Robot arms:** segments that each turn at their own joint, so moving the first brings the rest along.

## Requirements

- Blender 4.5 or newer. CopyThat is tested on Blender 4.5 LTS, 5.0 and 5.2. Blender will not install it on an older version.
- Mesh objects, or the bones of an armature you already have. Other object types (curves, text and so on) need converting to mesh first.
- Nothing else. It does not need the internet, other add-ons, or **Auto Run Python Scripts** to be switched on.

## Installation

CopyThat is installed as a Blender **extension**. You do not unzip anything: keep the download as a `.zip` file (named like `CopyThat-0.19.3.zip`).

**What is in the download.** One file: that `.zip`, which is the extension itself. Inside it are the add-on (plain Python, so it is also the full source code), its manifest, the user guide (`README.md`) and the licence (`LICENSE`).

### Removing an older version first (RigMoves or an old CopyThat)

Older versions of this add-on (called **RigMoves**, or an earlier **CopyThat**) were installed under **Add-ons** as a "legacy" add-on. The old and new versions cannot be switched on together, so take the old one out first. If you have never installed it before, skip to "First install".

1. In Blender, open **Edit > Preferences > Add-ons**.
2. Type **CopyThat** in the search box, and look for any entry with that name. Then search **RigMoves**.
3. For each entry you find, untick its box to switch it off, click the small arrow on its left to open it, and press **Uninstall**.
4. Close Blender completely and open it again.

If there is no Uninstall button, delete the folder called `rigmoves` from Blender's add-ons folder instead and restart Blender. On Windows that folder is `C:\Users\<your name>\AppData\Roaming\Blender Foundation\Blender\<version>\scripts\addons`, on macOS it is `~/Library/Application Support/Blender/<version>/scripts/addons`, and on Linux it is `~/.config/blender/<version>/scripts/addons`.

### First install

1. Open **Edit > Preferences** and click **Get Extensions** on the left.
2. Click the small **drop-down menu** (the arrow at the far right of the top row of that tab).
3. Choose **Install from Disk...**
4. Pick the `CopyThat` zip and confirm.

**Or drag and drop:** drag the zip file from your file browser and drop it anywhere on the Blender window, then confirm the pop-up that appears. Leave its default choices as they are. On Superhive, a product with a valid extension zip is marked **Extension**, and you can drag it from your receipt straight into the Blender window to install it.

You do not need to turn on online access: Install from Disk works offline. (If Blender shows an **Online Extensions** box, press **Continue Offline**.) When it is done, CopyThat is in the **Add-ons** list with its box ticked.

### Find the panel

1. Move the mouse over the 3D Viewport and press **N** to open the sidebar.
2. Click the **CopyThat** tab on the right edge of the sidebar.

If you do not see the tab, check that the sidebar is open (View > Sidebar), that you are in a **3D Viewport** (not another editor), and that the sidebar is tall enough to show its tabs.

### Updating to a newer version

1. Download the new zip.
2. Install it the same way as the first time: **Edit > Preferences > Get Extensions > drop-down menu > Install from Disk...**, or drag and drop the zip into Blender.
3. **Close Blender and open it again.** This matters: until you restart, Blender may keep running the old code, and you will not see the new buttons.
4. To check which version you have, open **Edit > Preferences > Get Extensions**, find CopyThat and click the small arrow on its left to open its entry: the **Version** is listed there.

Your scenes are not touched by an update: everything CopyThat makes is saved inside your `.blend` file.

### Uninstalling

Open **Edit > Preferences > Get Extensions**, find CopyThat, click the small drop-down arrow at the right end of its row and choose **Uninstall**. Scenes you made keep their animation (see the FAQ).

### Files made with older versions

Files made with RigMoves or earlier CopyThat versions keep working. You will still see the word "RigMoves" in a few places inside the file (rig names such as "RigMoves Rig", and bone constraints that start with "RigMoves:"). That is on purpose, so old files do not break. The panel is simply the **CopyThat** tab now. If an old file ever looks off, press **Build Sliders** once: it tidies up rigs made by older versions.

## Quick start: one cube in about 2 minutes

1. Open a new scene. In **Object Mode**, click the cube so it is selected.
2. Open the sidebar (**N**) and click the **CopyThat** tab. The panel says one object is selected.
3. Press **New Move**. A rig called **CopyThat Rig** appears, and a box called **Move 1** appears in the panel. The tick on its **Before** row shows that where the cube stands now is recorded as the start.
4. With the mouse over the 3D Viewport, move and turn the cube to where it should end up. For example: **G**, **X**, type **3**, **Enter** to slide it, then **R**, **Z**, type **90**, **Enter** to turn it.
5. In the Move 1 box, on the **After** row, press **Record**. The dot becomes a tick.
6. Press the big **Build Sliders** button at the bottom.
7. A **Play** slider appears, 0 to 100%. It carries the move's name, so here it reads **Move 1**. Drag it. The cube goes from where it started to where you put it.
8. To animate it on the timeline: set **Frames** (under Play) to 48, make sure the timeline is on the frame you want it to start, and press **Animate**. Press **Space** to play.

That is the whole idea. Everything below is what you can add on top.

## How it works: the workflow in one picture

A few words first, because the panel uses them:

- A **move** is a group of parts that play together under one control. The box in the panel is the move.
- A **part** is one thing in a move: an object (a petal, a lid) or a bone.
- A **leader** is a part you recorded. A **rider** is an object that copies a leader's move from where the rider stands.
- A **follower** is a part that hangs from another part, like the second joint of a finger.

The loop you repeat for every move:

1. **Select** the objects that move together (in Object Mode).
2. **New Move.** Where they stand is Before.
3. **Pose** them where they should end up, and press **Record** on the After row.
4. **Build Sliders.** This is where the rig appears.
5. **Play.** Drag the Play slider or the handle.

After that, you shape the move:

- **Shape the path:** Steps in between, Speed, Ease, Pivot, Curve the Path.
- **Shape the timing:** Timing (Delay), Lead, Spread.
- **Multiply it:** Ride Along, Ring.
- **Connect it:** Follows, Make Chain, Curl.
- **Put moves together:** Combine.

At the bottom of the panel there is always a grey box with a **report**. It says what the last button did and what to do next. If something does not work, read it first.

### Which buttons need a Build?

- **Take effect at once, no Build:** Delay, Lead, Speed, Ease, Spread, Play, Animate, Paths.
- **Wait for Build Sliders:** a change to Follows (the panel says so in red), a change to a combined control's delays, and anything you Record (Recording pauses the sliders so you can pose; Build puts them back).
- **Build for you:** the Pivot buttons, Curve the Path, Straighten, Mirror, Ride Along, taking a rider out with its x, and Ring on a built move. These refuse, and tell you why, if you have dragged a part and not recorded it yet, because Build would put it back.

## Features, one by one

### 1. Before, After and Steps

**What it is.** **Before** is where the parts start. **After** is where they end. A **step** is a pose in between, for when the parts should not go in a straight line from one to the other: a hatch that swings clear before it slides, an arm that lifts before it reaches, a lid that overshoots and settles.

**When to use it.** Before and After for every move. Steps when the straight way is wrong.

**Record and the eye.** The **Record** button on any row saves where the parts are standing right now. The eye icon beside it puts the model back into that pose so you can check it. Recording and the eye pause the sliders so you can pose freely, and **Build Sliders** puts them back.

**Steps to record Before and After**

1. Select the objects and press **New Move**. Before is recorded for you.
2. Move and turn them to where they should end up.
3. Press **Record** on the **After** row.
4. Press **Build Sliders**.

To change a pose later, click the eye to see it, move the parts, press **Record** again, and **Build Sliders**.

**Steps to add a step in between**

1. Press **Build Sliders** once, so the parts have bones. (For loose objects the step button only works after the first Build, and only once Before and After are both recorded.)
2. Press **Step in between** (the button with the + on it). A **Step 1** row appears, empty.
3. Move the parts to where they should be part way through.
4. Press the **Record** on the Step 1 row.
5. Press **Build Sliders** to put the sliders back.

Add as many steps as you like. They play in the order they are listed and are spread evenly between Before and After. Each has an eye to check it and an **x** to take it off. The move still lands on Before and After exactly at its two ends.

Only the parts you actually moved are saved into a step. Anything you leave alone carries on along its own path, so a step can speak for one part of a group without disturbing the rest.

### 2. Build Sliders

**What it is.** The big button that turns your recordings into something that plays. For loose objects, this is where the rig is made: each object is given a bone of its own, bound to it, and put on the path between its two recordings. From then on the move behaves exactly like one recorded on bones.

**When to use it.** After you record, and after anything that waits for a Build. It is safe to press at any time.

**Steps**

1. Record Before and After.
2. Press **Build Sliders**.
3. Read the report at the bottom of the panel. It says how many parts are on how many sliders, and warns about anything it found.
4. Drag **Play** to test.

**Good to know.** Build always puts bound objects back on their Before. If you dragged an object off its place and did not record it, Build puts it back and the drag is lost. Record first. If a rig has drifted out of place, the next Build puts it right.

### 3. Play and the handle

**What it is.** Every built move gets two ways to play it, and they are the same control:

- A **Play** slider in the panel, from 0 to 100%. It carries your move's name (for example "Move 1").
- A **handle in the viewport**: an arrow on a rail over the parts it drives. A move's handle has one arrowhead. A combined control (see Combining) has two and is drawn larger, so the one that plays everything is never mistaken for one that plays a part. The handle is held to its rail, so it cannot be dragged past either end.

Drag either and the other follows. The Play slider plays the whole move, from the first part to set off to the last one to arrive, including riders that were sent ahead or behind. The key button beside Play keys the control at the current frame, the same key as pressing **I** on the handle.

**When to use it.** Play to test and scrub. The handle when you want to animate by hand in the viewport.

**Steps to use the handle**

1. Click the **CopyThat Rig** in the viewport or the Outliner.
2. Switch to **Pose Mode** (Ctrl+Tab).
3. Grab the arrow and slide it along its rail.
4. Press **I** over the viewport to key it, move to another frame, slide again and key again.

The handle stands at the middle of the parts it drives, and the rig is drawn in front of the mesh, so a handle inside the machine can still be clicked. Where two handles would land on top of each other they are stacked upwards.

### 4. Speed per stretch

**What it is.** Steps cut a move into stretches: Before to Step 1, Step 1 to Step 2, and on into After. Between every two rows is a **Speed** slider for the stretch that joins them, from -50 to 50. 0 is even. Every 15 points is about twice as fast, 50 is about ten times, and below 0 is slower the same way. The note beside the slider says by how much.

**When to use it.** To make a move gather slowly and then strike, or to rush through one part and take its time on another. For example, a sword swing: Before is the raised sword, Step 1 mid swing, After the follow-through. Set the speed into Step 1 to -30 and the speed into After to +30, and it gathers slowly and then strikes.

**Steps**

1. Add at least one step (see Before, After and Steps). The Speed sliders only appear once there is more than one stretch.
2. Find the Speed slider above the row it leads into. The slider above a row is the speed of the stretch that arrives at that row.
3. Drag it. It takes effect as soon as you change it, so scrub **Play** to judge it.

**Good to know.** The move always fills its whole control, so a speed only counts against the other stretches. Every stretch at -50 plays exactly like every stretch at 0. How fast the whole move plays is still how fast you move the control.

### 5. Ease

**What it is.** The **Ease** menu under the After row (the drop-down that reads **Even speed** until you change it) shapes the whole move: **Even speed**, **Smooth**, **Slow start** or **Slow stop**. It sits on top of whatever path you recorded, so a hand-shaped path with Smooth on it eases into and out of your own curve.

**When to use it.** Smooth for almost everything that should feel soft. Slow start or Slow stop when only one end should be gentle.

**Steps**

1. Open the **Ease** menu in the move's box.
2. Pick one. It takes effect at once.

For exact control of each stretch use the Speed sliders instead, with Ease left on Even speed. The two stack, the ease first.

### 6. Timing (Delay)

**What it is.** The **Timing** section gives every part a **Delay**: a fraction of the control's travel. Delay 0.2 means that part waits until the control is a fifth of the way across, then runs to the end. That is what stops a machine reading as one rubber object: the parts leave in order, and overlap.

**When to use it.** Whenever parts should not all leave together: a lid that waits for the latch.

**Steps**

1. Click the **Timing** header to open it.
2. Select a part in the viewport. Its row stays bright while the others go quiet. (Or click the icon on a row to select that part.)
3. Type a **Delay** from 0 to 0.99 in its box.
4. Drag **Play** to see it.

It takes effect at once. Riders are not listed here: their **Lead** does the same job (see Ride Along). **Spread…** in the Timing header fills all the Delays in at once (see Spread). A combined control has the same box for each move it plays.

### 7. Ride Along, with Lead and Mirror

**What it is.** Record one part and let others copy it. Select the parts that should follow, then the recorded one last, and press **Ride Along With '...'**. Each of them now does what the recorded part does, but from where it stands and facing its own way: whatever the leader does to its own left, a rider does to its own left. Eight petals round a centre all open outwards, each in its own direction, from one control.

**When to use it.** Petals, doors, wheels, drawers, any set of similar parts. If the copies are not modelled yet, **Ring** can make them for you (see Ring).

**Steps**

1. Record the leader's move (built or not).
2. Select the objects that should ride along. They must not be in the move yet.
3. Last of all, click the recorded part so it is the **active** object (the brightest highlight).
4. A box in the panel says the objects are not in this rig. Press **Ride Along With 'Name'**.
5. The riders appear under **Riding along**, each in a row of its own.

A rider turns about its leader's pivot, carried over to where the rider stands. Set the pivot on the leader and every rider swings about the same point on itself. Riders follow everything the leader's path does: steps, speeds, Ease, a curved path. A rider half the size of its leader still travels as far. You can set riding up before the leader's After is recorded; it takes effect at the next Build.

**Lead.** Each rider has a **Lead** slider from -50 to 50 that says when it moves against its leader.

- 0 moves with the leader.
- Below 0 it follows behind. -25 sets off when the leader is half way. -50 sets off only once the leader has finished.
- Above 0 it goes first. 50 has finished before the leader starts.

Either way it travels at the leader's speed, for as long as the leader does: only *when* changes. A lead takes effect as soon as you change it. The Play slider always covers the whole of it, so a rider sent ahead has somewhere to go: the leader simply starts later along the control. Petals at -8, -16, -24 and on round the flower open one after another in a wave. **Spread…** in the **Riding along** header fills these in for you.

**Mirror.** A rider that is a mirrored copy of its leader (negative scale, the way **Ctrl+M** leaves one) mirrors its leader's move by itself: the left wing does the mirror image of what the right one does. A rider that only *faces* the other way, such as the second of a pair of doors turned round to fit, has a **Mirror** button on its row. Each press steps it on: **-** (none), **X**, **Y**, **Z**, and rebuilds. X, Y or Z mirrors the leader's move across that axis of the rider, so what is the leader's left becomes the rider's right.

**Taking one out.** The **x** on a rider's row takes it out again and leaves it where it stands. A rider copies its leader from where it stood when it joined, so to move one somewhere else, take it out and add it again. A rider cannot lead other riders.

**Copies of a whole finger.** If the leader has followers (a finger of three segments), select every segment of the other fingers, in any order, and last any segment of the recorded finger. Press **Ride Along With '...'**. Each copy is matched to the recorded finger joint for joint, by where its pieces stand, and curls from where it stands. A copied finger is one row under Riding along, marked **+2** for the joints that come with it. Its Lead sends the whole finger ahead or behind with its joints in step: fingers at 0, -10, -20 and -30 close one after another.

### 8. Pivot

**What it is.** A part turns about its **pivot**. Between two recorded poses the pivot goes in a straight line and everything else swings round it, so it decides the way from one pose to the next. The poses themselves never change. A lid turning about its middle cuts through the box on the way; turning about its hinge, it swings open.

**When to use it.** Whenever a part has a hinge, a knuckle or a base it should turn on.

**Steps**

1. Select the parts in the viewport.
2. On the **Pivot** row, press one:
   - **Origin:** the object's own origin.
   - **Cursor:** wherever the 3D cursor is. Put it on the hinge first: select the hinge edge in Edit Mode and press **Shift+S > Cursor to Selected**.
   - **Base:** the middle of the bottom of the object's bounding box.

You can pick a pivot before the first Build or any time after. On a built move the path is re-keyed so every recorded pose (Before, After and every step) stays exactly where it was. No origins need moving. The Pivot buttons are greyed out until you select a part. Riders turn about their leader's pivot, carried over to where each one stands.

### 9. Curve the Path

**What it is.** From A to B a part goes in a straight line, which is no use when something is in the way. **Curve the Path** gives it a curved route.

**When to use it.** To go round an obstacle, or to make a swooping path.

**Steps**

1. Select the part and press **Curve the Path**. (Loose parts need their After recorded first.)
2. A curve appears along the path the part has, through its steps if it has any, with a point in the middle to take hold of.
3. Press **Edit** beside it in the panel (or press Tab on the curve). Drag the curve round the obstacle. Add points if it needs them.
4. Leave Edit Mode (Tab) and press **Build Sliders**.

The part's pivot now travels along the curve, evenly by distance, and turns from pose to pose as it did before.

The two ends of the curve always belong to Before and After. Every Build puts them back there: drag an end away, or record After again, and the curve's ends follow the part, not the other way round. The **x** beside the curve (**Straighten**) deletes it and the path goes straight again. A curve takes over the in-between locations of its part, steps included, so going back to straight also drops the locations of its steps. Riders follow a curved leader along the same curve, carried over to their own place.

**Good to know.** A follower goes where it is carried, so its path is not curved: curve the part it follows instead. Only a curve's first spline is followed (Bezier or Poly).

### 10. Paths

**What it is.** The **Paths** button draws a line in the viewport through where every part of the move goes, from Before to After, through the middle of each part, taking in steps, pivots, curves and mirrors.

**When to use it.** To see what you have made, or to check a curve.

**Steps**

1. Build the move.
2. Press **Paths**. The button stays pressed while the lines are shown.
3. Press it again to hide them.

The lines are drawn again at every Build. They can't be clicked and don't render. The button only appears on a built move with objects in it.

### 11. Follows

**What it is.** A finger is three segments, each turning at its own knuckle, each carried by the one before. In the **Follows** section, beside every part is a dropdown listing the move's other parts. A part that follows another goes wherever that part takes it, and does its own move on top.

**When to use it.** Fingers, tentacles, robot arms, a hand on a forearm: anything where moving one part must bring others along.

**Steps**

1. Put all the segments in one move (select them all and press **New Move**).
2. Open the **Follows** section.
3. Beside the second segment, pick the first. Beside the third, pick the second. (Or select the segments and press **Make Chain**: see the next section.)
4. Give each segment its knuckle as its **Pivot**: put the 3D cursor on the joint and press **Cursor**.
5. Pose the segments and record as usual. Every recorded pose lands exactly where you put it. In between, each joint turns about its own knuckle while the joint before carries it, so the finger curls instead of its pieces sliding apart.
6. If the panel says **Build to put it into effect** in red, press **Build Sliders**.

A follower's object hangs from the object it follows, so dragging the first segment brings the others along on screen. A pick that cannot be (the part itself, a rider, a loop) is turned down with the reason, and the choice it had stays. Objects already parented to one another in the file (a finger modelled joint by joint) follow the same way without being asked. **Timing** still gives each segment a delay of its own, so the tip can wait for the base.

### 12. Make Chain

**What it is.** One click that fills in Follows down a line of parts.

**When to use it.** A finger, a tentacle or a spine: parts end to end, where choosing each Follows by hand is the slow part.

**Steps**

1. Set each part's **Pivot** on its joint first (it helps Make Chain tell the order).
2. Select the parts, and click the one the chain starts from **last**, so it is the active object.
3. Open the **Follows** section and press **Make Chain**.
4. Read the report: for example "Chain: Seg1 > Seg2 > Seg3". If it is the wrong order, press Ctrl+Z, check that you clicked the first part last, and try again.

From the first part, each next part is found by how joints are built: a joint sits at the far end of the part before it. Where nothing touches (gaps between the parts), it uses the nearest pivot. Each part is set to follow the one before.

It replaces the links the chosen parts already have to one another, so a chain made from the wrong end can be made again from the right one; the report says which old links it replaced. A part the chain starts from may follow something that is not chosen (a finger on a palm) and keeps that. If the chain meets something it cannot link (such as a rider), it stops there and keeps the links already made. On a built move, press **Build Sliders** afterwards, like any Follows change.

### 13. Curl

**What it is.** Bend one joint and the whole chain bends. **Curl** takes the first segment's bend and repeats it down every part that follows it, each about its own pivot and carried by the part before it, so the joints stay together.

**When to use it.** Every joint of a finger or tentacle bends the same way and you would rather pose one than all of them.

**Steps**

1. Make it a chain first (**Make Chain**, or Follows by hand) and set the pivots on the joints.
2. Make sure everything is at rest: **Play** at 0, or press **To Before**.
3. Turn the first segment about its joint, by hand.
4. With the first segment still the active object, press **Curl** (beside **Make Chain**, at the top of **Follows**).
5. Press **Record** on the After row (or a Step's Record) to keep it.
6. If the finger has copies riding along, press **Build Sliders** too.

**Each next joint ×.** Right after pressing Curl, open the **Adjust Last Operation** panel: it is the small panel at the bottom left of the 3D Viewport, and it is also under **Edit > Adjust Last Operation...** (or press **F9**). **Each next joint ×** says how much of the bend each joint keeps from the one before it. The default is 1: every joint bends as much as the first. Blender remembers the last value you used until you close Blender, so the next Curl starts from that one: set it back to 1 for an even curl. At 0.5 a 20 degree bend runs 20, 10, 5, 2.5, 1.25 down the root and four followers, so the tip curls least.

**When Curl says no.** Curl works from rest. It refuses while any joint is showing a pose (the eye on After, or Play above 0) and tells you to drag Play to 0, building first if the sliders are paused. It also refuses when nothing follows the part, when the part rides along, and when the part has not been turned. It puts every part below the root where its bend says, replacing whatever bend it had.

### 14. Ring

**What it is.** One part becomes a ring of riders: the petals of a flower, the blades of a fan, the teeth of a gear, a crown of spikes. Either the other copies are not modelled yet and Ring makes them, or they are modelled already and Ring picks them up.

**When to use it.** Whenever the same part goes round a centre, and you would rather not select them all for Ride Along.

**Steps**

1. Record the part's move (built or not).
2. Put the 3D cursor on the centre of the ring. (Or use **World Origin** in the dialog, if the centre is the world origin.)
3. Select the part so it is the active object.
4. In the move's box, press **Ring…** (in the row under **Curve the Path**). It is greyed out until the active object is a part of the move that is not a rider.
5. Pick **Use**, set **Count**, and press **OK**.

**The three Use choices**

- **Make copies:** a new copy for every place round the ring, whatever already stands there. Use it when nothing is modelled but the one part.
- **Use what's there:** takes up the objects already standing in the places, and makes nothing. Use it when every petal is modelled already and you do not want one more object.
- **Fill the gaps** (the default): takes up what stands in a place, and copies the part only into the places where nothing does. Use it when most are modelled and a few are missing, or when you are not sure. It never puts a copy on top of a petal that is there.

**The other fields**

- **Count:** how many places round the ring, including the original. 6 means the part and five more (the dialog first opens at 6).
- **Round:** the **3D Cursor** or the **World Origin**.
- **About:** **World Z** (a ring lying flat, the default), **World X**, **World Y**, or the **3D Cursor's Z** for a ring that is tipped. Take care with the last one: placing the cursor with Shift+right-click turns it to face the view, and a ring made about its Z then faces the view too.
- **Linked copies** (on by default): the copies share the original's mesh, so editing one in Edit Mode edits them all. They share it until Build, which gives each part a mesh of its own. Untick it to give copies their own meshes from the start.
- **Lead step:** if you set anything but 0, the Leads are stepped from the original both ways round the ring, so the blades open one after another. 0 sends all the copies together. (Spread, below, can also do this later.)

The defaults named here are what the dialog shows the first time. Blender remembers your last choices in it until you close Blender, so the next time it opens with those: check the fields before you press **OK**.

**How it picks up what is already modelled**

Ring takes an object up, or stands it on a new frame, only when that is provably safe. Anything else is left exactly as it is, and the report says why.

- **It has to be a copy of the part's mesh.** The same number of vertices, and every vertex of one within a fiftieth of the part's size of a vertex of the other, both ways round, once it stands in the place. The numbering does not matter, so a half of a flower made with Ctrl+M, or the teeth of a gear copied with Shift+D and moved with G and never turned, are taken. A mirror image of a petal that is not the same on both sides is not a copy, and nor is a different petal with the same vertex count.
- **Who may be taken.** A mesh object that is visible, free to select (a collection with selection switched off counts), local and editable, in no move yet, and with no keys, drivers or NLA of its own. Left alone, and named in the report: "has keys or drivers of its own", "is linked from a library", "cannot be edited", "is hidden", "cannot be selected", "is already part of a move".
- **Standing an object on a new frame.** A rider copies its leader's move from its own origin and axes, so a petal modelled with its origin somewhere else, or its rotation or scale applied, would swing about the wrong point. Such an object is stood on the frame a copy would have, and its mesh is moved the other way. It gets a mesh of its own, so objects that shared the old one stay as they were. This is done only to plain objects. An object with constraints, instancing, particles, other objects depending on it (a Child Of, a Shrinkwrap target, a child hung from its vertices), or a modifier that reads its frame (anything but Subdivision, Triangulate, Edge Split, Weighted Normal or an Armature of another rig; Bevel and Solidify only at a scale of 1) is left alone.
- **Then it is checked.** After the change the result is compared with what it was: where every vertex is in the world, and which way every face faces. If anything differs, the object is put back exactly and left alone: "cannot be re-framed safely (re-framing it would change how it looks): set its origin and rotation like the leader's, or use Make copies". The report says how many were re-framed. Textures that use an object's own or generated coordinates are not checked.
- **A finger or a leaf (a part with parts that follow it)** is taken only when every joint of the place is found and can be re-framed. Found in part, the place is left alone, and the report says so.
- **Where two objects stand on one place,** the closer fit is taken and the other is named in the report.
- **Nothing is copied on top of anything.** In **Fill the gaps**, a place is skipped when any mesh object at all stands in it: hidden, in a move, with any number of vertices, a petal scaled a little or with a vertex nudged. The report says how many places had something standing there that is not a copy. **Use what's there** says how many places were empty, and that **Fill the gaps** would copy the part there.
- **A wrong centre, About or Count is caught.** If copies of the part stand near the ring but on none of its places, the ring is round the wrong point, about the wrong axis or has the wrong Count, and copying between them would double the flower. **Fill the gaps** is turned down: "7 copies of 'Petal' stand near the ring but off its places: check the centre (3D cursor), About and Count. Nothing done." **Use what's there** says the same as a note. **Make copies** is never turned down.
- **The report names what was left out and why,** up to three, the nearest to the ring's places first. When nothing can be taken or made, Ring is turned down with those names and nothing is changed.

**What Ring makes**

- Copies are named "Petal 2" and on, and put in the same collections. Objects picked up keep their names.
- Nothing that bound or hung the original comes with a copy: no Armature modifier, no vertex group for the original's bone, no Follows, no parent, no keys on the transform.
- The copies and the objects picked up ride along with the part, exactly as if you had pressed Ride Along on them.
- A part is ringed with the parts that follow it, never the ones it follows. Ring a finger's first joint and every finger comes whole, each curling from where it stands. Ring a fan blade that follows a hub, and the hub is not copied: every copy hangs from the hub as the blade does.
- A second Ring over the first, or a bigger one, adds only the missing places. Ring 4 then Ring 8 adds the 4 missing ones.
- Ring asks before it makes anything. A part that is not in the move, a rider, a part with no Before, or a part dragged and not recorded on a built move are each turned down in words, and nothing is left behind. It is one Ctrl+Z.

### 15. Spread

**What it is.** Fills in the Leads of all the riders, or the Delays of all the parts, in one go, instead of typing a number into every row.

**When to use it.** A ring of riders should open one after another, a finger's joints should go one after the next, a row should topple in a wave.

**Steps**

1. Press **Spread…** in the header of **Riding along** (to set Leads) or of **Timing** (to set Delays).
2. Pick an **Order** (below). For Leads the dialog opens on **Around a ring**. For Delays it opens on **Down a chain** if the move has Follows links, and on **Along an axis** if not.
3. Pick **By**: **Step** or **Range**.
4. Set the values and press **OK**.

It writes once for all of them, and a built move plays the new values at once. No Build. If any value hits the limit (Leads are whole numbers from -50 to 50, Delays from 0 to 0.99), the report says how many were held at the limit.

The dialog works out its Order, Start, Step, First and Last afresh every time. Blender remembers your last **By**, **Both ways**, **Only the selected**, **Axis** and **Seed** until you close Blender.

**By Step (the default).** You give a **Start** and a **Step** (the dialog calls them "Start Lead" and "Lead step", or "Start Delay" and "Delay step"). Every part takes a place in the order, and gets Start + Step x its place, counting from 0. The dialog opens with a Step of -10 for Leads and 0.1 for Delays, made smaller when the last place would run past 40 of the 50 a Lead can be (0.9 of the 0.99 a Delay can be): a wave held at the limit stops dead there. Twelve spikes one way round get -3, both ways -6, and eight petals both ways keep -10. For Leads, **Around a ring** first opens with **Both ways** on. A Step you type is kept as you typed it, and what it holds at the limit is still counted. For Leads, below 0 each rider waits more than the one before it; above 0 each goes earlier. For Delays, each waits that much longer. It is a *step*, so adding a petal later gives it the next value and leaves the rest as they were: a Step of -10 gives -10, -20, -30 whether there are four petals or forty.

**By Range.** You give a first and a last value (the dialog calls them "First Lead" and "Last Lead", or "First Delay" and "Last Delay"), and the parts between are spread evenly from one to the other, however many there are. Handy when it is the last that matters: the last petal opens at -40 and whatever is between is shared out. (A part added later changes the share of the others.)

**The orders.** Parts the order cannot tell apart share a place and get the same value.

- **Around a ring:** the further round the ring a part stands from the start, one way round, the later it comes. Tick **Both ways** to fold the ring in half, so the two sides match: the parts either side of the start go together. The ring is wherever the parts lie, so a tipped ring works. Parts scattered over a field are not a ring: for those use **By distance** or **Along an axis**.
- **By distance:** the further a part is from the start, the later it comes. A ripple.
- **Along an axis:** the further along world **X**, **Y** or **Z** (you pick which under **Axis**). Dominoes, a wave across a grid.
- **Down a chain:** the further down a Follows chain it hangs. A finger or a tentacle. Delays only, because riders have no Follows chain of their own.
- **Random:** no order, but the same every time for the same **Seed**. The places are dealt out, none shared.

**Example.** Eight petals round a flower, Step -10, **Around a ring**, **Both ways**: the leader plays at 0 as it always does, and the seven riders get -10, -20, -30, -40, -30, -20, -10. The pair next to the leader go together, and the petal opposite is the last.

**Only the selected.** By default Spread takes all of them, whatever is selected. Tick **Only the selected** to spread just the parts selected now.

**Good to know.** Leads belong to riders; each leader's riders are put in order among themselves, and a copied finger has one Lead (its first joint's), so it counts as one. Delays belong to the parts in the Timing list. For Delays the start is the active part, or the first one. Parts are placed by their pivot at Before; where every pivot is the same point (the blades of a fan turning about its hub), the middle of each part is used instead.

### 16. Animate over frames

**What it is.** Turns the control into keyframes on the timeline in one press.

**When to use it.** When you want the move to play as an animation over so many frames.

**Steps**

1. Build the move.
2. Put the timeline on the frame where the move should start.
3. Under **Play**, set **Frames** (the default is 48).
4. Press **Animate**.
5. Press **Space** to play.

The control is keyed to play the whole thing from the current frame, over that many frames, and the scene is made long enough to hold it. Pressing Animate again replaces those keys rather than adding to them. The keys are even in time, so the shape of the move is still its own Ease and Speeds.

**Keying by hand.** For anything more complicated (slow, fast, hold, play back), key the control yourself: put the Play slider where you want it and press the key button beside it, or press **I** on the handle. Keyed handles are left alone by Build. When a Build makes a handle's rail longer or shorter, its keys are stretched with it, so the animation still runs from end to end.

### 17. Combining moves under one control

**What it is.** Record one group of parts, then another, then press **Combine**. A new control appears that plays them both. Every member gets its own **Delay**, as a fraction of the combined control's travel, so the second group can start when the first is half way, or wait until it has finished.

**When to use it.** One button that opens the whole machine: lid first, then the inner panel, then the lights.

**Steps**

1. Make two or more moves. For the second, select the next group of objects and press **New Move** (or **New Group Here**, see "Adding more parts later").
2. Press **Combine** (it appears at the bottom of the panel once there are two moves).
3. A new box (named **Together**) appears, with a row for each move and a **Delay** box. The moves start laid end to end. Set every Delay to 0 to play them all at once, or change them to overlap.
4. Press **Build Sliders**. The combined control gets its own **Play** slider and a larger handle with two arrowheads.

The moves keep their own controls as well. The two are combined by taking whichever is further along, so a move can be played alone or as part of the sequence and neither blocks the other. Take a move out of the combination with the **x** on its row. Delete the combination with the **x** in its header, and its members are untouched. A move can be in only one combined control at a time, and Combine takes every move that is not already in one.

### 18. Pause, To Before and Remove

- **Pause:** switches the sliders off so you can pose the parts by hand. While paused, the button reads **Paused** and turns red. Press it again to make the sliders live, or press **Build Sliders**. Recording and the eye pause for you.
- **To Before:** returns every control to its start.
- **Remove (the x on a move's header):** deletes the move, its control, its path and its constraints, and leaves the rig exactly as it was. Objects that were bound to bones are freed and stay exactly where they are.

### 19. Adding more parts later

When you select an object the rig has never been told about, the panel says so, in a box at the top, and offers what makes sense. What it offers depends on what else is selected.

- **Selected together with a part that already moves:** **Ride Along With 'Name'** is offered first (see Ride Along).
- **Selected together with a group's part or its handle:** the box names the group and offers **Add To This Group**. Where the object stands now becomes its Before. Press the eye beside After, put the object where it should end up, and press Record on After. Only the part you posed this time is recorded; the rest are left alone.
- **Selected on its own:** **New Group Here** (a new move in this rig) and **New Rig** (a brand new rig, for something unrelated).
- Every other group on every rig in view is listed underneath ("add it to:") for when the one it picked is not the one you meant.

### 20. Using the bones of your own rig

You do not need to let CopyThat make the rig. If your model already has an armature, go into **Pose Mode**, select the bones, and press **New Move**. The rest is identical: Record, Build Sliders, steps, speeds, Ease, Timing, combining.

- The Action constraint CopyThat adds sits at the top of the bone's stack, so any constraints the bone already has still run afterwards. A hand-built rig can be given a control without being taken apart.
- Pivots, Curve the Path, Paths, Ride Along and the Ring, Make Chain and Curl tools work on objects. Bones of a hand-built rig turn about their own heads, as they always did.
- The **Parts** button (it reads "N selected") replaces the move's bones with whatever is selected now, keeping the timing of the ones that stay.

### 21. Auto Keying warning

If Blender's Auto Keying is on, every drag this tool asks for leaves a keyframe behind, and a keyed part or handle is one the rig cannot move. The panel shows a red box saying **Auto Keying is on**, with a toggle to switch it off. If parts have keys on their own transform, the box offers **Lift Those Keyframes**. Build lifts them too. Handles you have really animated are left alone.

## Worked example 1: a blooming flower (Ring + Spread + Make Chain)

One petal, recorded once, becomes a bud of eight petals that open one after another. You need a petal modelled in two pieces, **Petal Base** and **Petal Tip**, standing in a closed bud. The tip sits on top of the base like the second joint of a finger. Put each piece's origin on its hinge (Object > Set Origin > Origin to 3D Cursor, with the cursor on the hinge): it makes turning the pieces by hand easy. Put the flower's centre on the world origin so the ring is easy too.

1. **New Move.** Select **Petal Base** and **Petal Tip** and press **New Move**. Rename the box to "Bloom" by double-clicking its name.
2. **Pivots.** Because each origin is already on its hinge, leave **Pivot** on **Origin**. (If you cannot move origins: put the 3D cursor on a hinge, select that piece, press **Pivot > Cursor**, and do the same for the other.)
3. **Make Chain.** Select both pieces, clicking **Petal Base** last so it is the active object. Open **Follows** and press **Make Chain**. The report says "Chain: Petal Base > Petal Tip". The tip now follows the base.
4. **Open the petal.** Select **Petal Base** alone and tilt it outward about its hinge: press **R**, press the axis key the hinge runs along, type an angle such as **60**, and press Enter. The tip comes along on screen. Now select **Petal Tip** and bend it further out about its own hinge in the same way (an angle such as **40**).
5. **Record After.** Press **Record** on the **After** row.
6. **Build Sliders.** Drag **Play** from 0 to 100%. One petal opens. Fix anything that looks wrong before you multiply it.
7. **Ring.** Put the 3D cursor on the flower's centre (Shift+S > Cursor to World Origin if the flower is at the origin). Click **Petal Base** so it is the only selected object and the active one. Press **Ring…** and set: **Use** Fill the gaps, **Count** 8, **Round** 3D Cursor, **About** World Z, **Linked copies** on, **Lead step** 0. Press **OK**. (The first time, the dialog already opens with all of these except **Count**, which opens at 6.)
   - Seven more petals appear round the centre, named "Petal Base 2" and so on (and "Petal Tip 2"). They are whole petals: Ring copied the tip too, because it follows the base.
   - A **Riding along (7)** section appears, one row per petal, marked **+1** for the tip that comes with it.
8. **Spread.** Press **Spread…** in the **Riding along** header. Set **Order** to **Around a ring**, tick **Both ways**, set **By** to **Step**, **Start Lead** 0 and **Lead step** -10. Press **OK**. (The first time, for a ring of eight, the dialog already opens with all of these.) The Leads become -10, -20, -30, -40, -30, -20, -10. Nothing needs a Build.
9. **Ease and animate.** Set **Ease** to **Smooth**. Under **Play**, set **Frames** to 120, put the timeline on frame 1, press **Animate** and **Space**. The recorded petal opens first, the petals either side follow, and the opposite petal is last.

**Variations.**

- If the other petals are already modelled, leave **Use** on **Fill the gaps** (or pick **Use what's there**): Ring takes them up and makes nothing new.
- A second ring of smaller inner petals: select the inner petal, press **Ring…** again with another **Count** and **Lead step**.
- Stagger the leaf or the core with **Timing**: type a **Delay** such as 0.3 so they open after the petals have started.

## Worked example 2: a curling finger (Make Chain + Curl)

You need three segments, **Seg1**, **Seg2** and **Seg3**, laid end to end like a finger. Put each segment's origin on its knuckle.

1. **New Move.** Select the three segments and press **New Move**. Rename the box "Curl".
2. **Pivots.** With the origins on the knuckles, leave **Pivot** on **Origin**. (Otherwise, put the 3D cursor on each knuckle and press **Pivot > Cursor** for that segment.)
3. **Make Chain.** Select all three, clicking **Seg1** last. Open **Follows** and press **Make Chain**. The report says "Chain: Seg1 > Seg2 > Seg3".
4. **Bend the first joint.** Select **Seg1** alone and turn it about its knuckle by hand: press **R**, press the axis key the knuckle bends around, type an angle such as **40**, and press Enter. The others come along on screen. Keep **Seg1** the active object.
5. **Curl.** Press **Curl**, next to **Make Chain** at the top of **Follows**. **Seg2** and **Seg3** bend by the same amount, each about its own knuckle, carried by the one before it. To taper the curl so the tip bends least, open **Adjust Last Operation** (bottom left of the viewport, or **Edit > Adjust Last Operation...**) and set **Each next joint ×** to 0.8.
6. **Record After.** Press **Record** on the **After** row.
7. **Build Sliders.** Drag **Play**. The finger curls from the base to the tip together.

**Make it feel like a finger.**

- Open **Timing**, press **Spread…**, choose **Down a chain**, **By** Step, and a small **Delay step** such as 0.1. Each segment now waits a little longer than the one before.
- Add the other fingers. Model them with the same segments. Select every segment of the other fingers, then click a segment of the recorded finger last, and press **Ride Along With '...'**. Each finger copies the curl from where it stands. Then press **Spread…** in the **Riding along** header, choose **By distance** (the further a finger is from the recorded one, the later it closes) with a Lead step such as -10, so the fingers close one after another.

## Tips for good results

- **Before should be the rest pose.** Nothing warns you if it is not, and a move recorded from a half-posed start will be wrong at the ends.
- **Test with one part first.** Get one petal or one finger working, then copy it with Ride Along or Ring.
- **Record before you press anything that Builds.** Pivot, Curve the Path, Straighten, Mirror, Ride Along, taking a rider out and Ring on a built move each Build, and Build puts a dragged part back. They refuse if a part has been moved and not recorded.
- **Keep Auto Keying off** while you set a move up.
- **Turn hinges about the hinge.** The Pivot buttons shape the way between poses. The poses themselves are wherever you put the parts, so move parts about their hinges: put the origin on the hinge, or set Blender's Transform Pivot Point to 3D Cursor (press the . key in the viewport) with the cursor on the hinge.
- **Use the eye.** The eye icon beside a row shows that pose, so you can check it. Press **Build Sliders** afterwards to put the sliders back.
- **Use steps for arcs and Curve the Path for obstacles.** A straight line from A to B is rarely right for something heavy.
- **Use Speed or Ease, not both at once.** For exact control of each stretch use Speed with Ease left on Even speed.
- **Spread beats typing.** Use Spread for Leads and Delays, and Step rather than Range when you might add more parts later.
- **Name your moves.** Double-click the name in the box. Long part names are shortened from the front in the panel, so make the endings different.
- **Keep the rig.** Do not delete the CopyThat Rig or its bones: they are what moves your objects.
- **Parent the rig, not the parts.** An object parented to something outside the rig (a finger to a hand that is not in the move) is taken off that parent while it is bound. Parent the rig to the hand instead.
- **Save before big steps.** Every button is a normal undo step, but a saved file is the safest undo.

## FAQ

**Nothing moves when I drag the slider. Why?**
Work down this list.
1. Have you pressed **Build Sliders**? The Play slider only appears after the first Build.
2. Did the Build report say "After not recorded yet"? Press **Record** on the After row, then Build again.
3. Is the **Pause** button red and reading **Paused**? Press it, or press Build Sliders.
4. Is Auto Keying on? The panel shows a red box if it is. Switch it off and press **Lift Those Keyframes**.
5. Is the part's Delay very high, or is the Lead of a rider set far to one side? Check **Timing** and **Riding along**.
6. Is After the same as Before? If you did not move anything, there is nothing to play.

**I see no new buttons after updating. What do I do?**
Close Blender completely and open it again; until then it may be running the old code. Then check that only one copy of CopyThat is installed (remove any legacy RigMoves or CopyThat entry under Add-ons) and that the version is what you expect (Edit > Preferences > Get Extensions). Some buttons only show when they make sense: **Spread…** is in the headers of **Riding along** (which appears once a move has riders) and **Timing**; **Make Chain** and **Curl** are at the top of **Follows** (which appears when a move has two or more parts); **Ring…** is under **Curve the Path** and is greyed out until the active object is a part of the move.

**Can I use my own rig's bones?**
Yes. Go into Pose Mode, select the bones, and press **New Move**. Everything else works the same. See "Using the bones of your own rig". Pivots, curves, Paths and the Ring, Make Chain and Curl tools are for objects; bones turn about their own heads.

**Does it need "Auto Run Python Scripts"?**
No. The rig CopyThat builds uses Blender's own constraints and drivers, in the simple kind that runs with Auto Run Python Scripts switched off. You can leave that setting off.

**Will my file work without the add-on?**
The animation will. The bones, the Armature modifiers, the constraints and the drivers are all standard Blender, so a file made with CopyThat plays on a computer that does not have it, and the handle in the viewport still works. What you lose without the add-on is the panel: you cannot record, rebuild, or use Spread, Ring and the rest. Install CopyThat again and the panel picks up where you left off.

**Why do Leads stop at 50 and -50?**
A Lead is measured in "a whole trip by the leader". At -50 a rider sets off only when its leader has finished; at +50 it has finished before the leader starts. That is the furthest apart two parts can usefully be, so the slider stops there. Leads are whole numbers. (Delays, in the same way, stop at 0.99.) If a Spread would go past the limit, the report says how many values were held at the limit.

**Can I render with Cycles or EEVEE?**
Yes. After a Build your parts are ordinary meshes deformed by an ordinary armature, so any render engine works: Cycles, EEVEE or Workbench. To render an animation, key the control first (press **Animate**, or key the Play slider or the handle), so the timeline plays the move. The rig, the handles and the Paths lines are helpers and do not appear in a render.

**What happens to my modelled petals when I use Ring?**
It depends on the **Use** choice in the dialog. **Make copies** makes new petals whatever is there. **Use what's there** takes up the petals you already modelled and makes nothing. **Fill the gaps** (the default) takes up the ones that are there and copies only into the places that are empty; it never puts a copy on top of a petal that is there. A modelled petal is taken up only if it is a copy of the part: the same number of vertices, each within a fiftieth of the part's size of a vertex of the part, once it stands where a copy would. The numbering of the vertices does not matter. Ones that are not are left alone and named in the report. If a petal's origin is somewhere else, its mesh is moved the other way so nothing is seen to move. Your modelled petals keep their names.

**How do I undo?**
Press Ctrl+Z. Every CopyThat button is a normal Blender undo step. Ring, Spread, Make Chain and Curl are each exactly one Ctrl+Z, and a Ring that cannot be finished puts everything back as it found it. **Edit > Undo History** lists the steps.

**Which Blender versions does it work with?**
Blender 4.5 and newer. It is tested on Blender 4.5 LTS, 5.0 and 5.2. It does not work on versions older than 4.5.

**The New Move button is greyed out.**
Select one or more **mesh objects** in Object Mode, or bones in Pose Mode on a rig. Other object types (curves and text, for example) need converting to mesh first.

**The Step in between button is greyed out.**
Both Before and After must be recorded, and for loose objects you must have pressed **Build Sliders** at least once, so the parts have bones.

**Can parts bend, like a tentacle with smooth bending?**
Each object is bound whole to one bone, so it moves rigidly. For something that bends, model it in segments and use **Follows** (or **Make Chain**) and **Curl**. For smooth skin deformation, build a rig of your own with bones and use the bone workflow.

**Can I put the same part in two moves?**
Yes. Two moves that share a part are combined in the order they were made. A move can be in only one combined control at a time.

**Can I change how a move is built later?**
Yes. Record again over Before, After or a step; change the Pivot; add a Step; curve the path; add more parts. Then press **Build Sliders**.

**How many petals can Ring make?**
Count goes from 2 to 200, and it includes the original.

**Why do I see "RigMoves" in bone constraints and properties?**
CopyThat used to be called RigMoves. Only the shown names changed. The names stored inside files stay the same, so older files keep working.

**Do I need Build after Spread?**
No. Spread writes the new values and a built move plays them at once. The same is true of Delay, Lead, Speed and Ease.

**Can I look at the animation in the Graph Editor?**
Each move's path is an ordinary Blender Action, so you can open it in the Graph Editor and look at it like any other animation. Shape the move inside CopyThat with Steps, Speed, Ease and Curve the Path.

**Can I use it for commercial work?**
Yes. CopyThat is licensed GPL-3.0-or-later, which covers the add-on's own code. The scenes and animations you make with it are yours.

**Can I use it on Windows, macOS and Linux?**
CopyThat is plain Python with nothing to compile, so it does not depend on your operating system, and it has been run on both Windows and Linux. You only need Blender 4.5 or newer.

## Troubleshooting

**The CopyThat tab is missing from the sidebar.**
Open the sidebar with N while the mouse is over a 3D Viewport. Make sure CopyThat is ticked in Edit > Preferences > Add-ons. If you also have a legacy RigMoves or CopyThat add-on, remove it (see Installation) and restart Blender.

**The panel says "Select the objects that move, or an armature to work on."**
Nothing usable is selected. Select the mesh objects that move together in Object Mode, or pick the rig it offers.

**A part plays from the wrong end, or travels twice as far.**
Usually Auto Keying left a keyframe on the part itself. Switch Auto Keying off, press **Lift Those Keyframes** if the panel offers it, and press **Build Sliders**. Build puts every part back on its Before, so a rig that has gone wrong comes right on the next Build.

**The handle springs back or does nothing.**
Auto Keying is on, and keyed the handle on a drag. Switch it off. Build removes a lone key left by a drag.

**"... has been moved and not recorded. Record it first - this would Build, and Build puts it back."**
You moved a bound part and pressed a button that Builds. Press **Record** on the right row first, then try again. Or press Ctrl+Z to undo the move.

**A red "Build to put it into effect" under Follows.**
You changed what a part follows. Press **Build Sliders**.

**The report says a driver "was too long for Blender to hold and got cut short".**
Blender cuts a driver off at 256 characters. A move with many delays, an Ease and a combined control can come close. Use fewer delays, or set Ease to Even speed, on that move.

**Curl says "Curl works from rest".**
Drag **Play** to 0 or press **To Before**, then pose the first joint and press Curl again. If the sliders are paused with a pose showing, press **Build Sliders** first.

**Curl says nothing follows the part, or the part has not been turned.**
Make a chain first (Make Chain, or Follows), and turn the first segment about its pivot before pressing Curl.

**Make Chain chained the parts in the wrong order.**
The chain starts from the active object: click the first part last. Put each pivot on its joint, and try again. Make Chain replaces the old links, so you can simply do it again.

**Ring says "Every place round that ring already has a copy".**
You pressed it twice, or the ring is already full. Nothing was added. To add more, raise **Count**.

**The ring is lopsided or tipped toward the camera.**
The **Round** point is probably not where you thought. Press Ctrl+Z, check where the 3D cursor is (or use **World Origin**), and set **About** to **World Z**. Placing the cursor with Shift+right-click turns it to face the view, which tips a ring made about the cursor's Z.

**Use what's there says nothing is an exact copy.**
The petals must have the same number of vertices as the part, each within a fiftieth of the part's size of a vertex of the part, once they stand where a copy would. The numbering of the vertices does not matter. A petal with a vertex more or fewer, or one sculpted further off than that, is not a copy; the report names what was left out. Choose **Fill the gaps** to copy into empty places instead.

**Spread says there are no riders to spread Leads over.**
Leads belong to riders. Select the objects to ride along, then the part they copy, and press **Ride Along** first. Or use **Spread…** in the **Timing** header to spread Delays instead.

**A rider does the move the wrong way round (a door opens inward).**
Press the **Mirror** button on its row until it reads X, Y or Z and the motion is right. A rider that is a Ctrl+M mirrored copy needs no setting; leave it at **-**.

**Dragging the base of a finger shown bent tears its joints on screen.**
That is a display quirk. What is recorded is the finger carried whole. Pose it at Play 0 to see it as it will be.

**A change to Follows seems to be ignored.**
Changing Follows on a built move waits for **Build Sliders**. If you posed before that Build, the follower is recorded as it is seen. Build first, then pose.

**I opened an old file and the panel asks for a Build.**
Press **Build Sliders** once. It brings older rigs up to date.

**Something else is wrong.**
Read the grey report box at the bottom of the panel first. It says what happened and what to do. If it does not help, write to support (below) with the report text, your Blender version, your CopyThat version, and if you can a small `.blend` that shows the problem.

## Version history

- **0.19.3:** The light review of 0.19.2, fixed: a model scaled or turned on its rig and then applied, meshes joined into a built part, and the curves of an Alt+D copy.
- **0.19.2:** The review of 0.19.1, fixed: copies and deleted parts, old files, very large or very thin models, added geometry, long names, hand-built rigs.
- **0.19.1:** deleting a part no longer risks closing Blender or slowing a big scene, and the part leaves its move; a copy of a whole model made with Alt+D is independent of the original; Set Origin and Apply (Ctrl+A) on a built part or on the rig no longer throw the move off, and neither does a model carried far from the origin, a rig with keys of its own, or one scaled to nothing; and the advice for a part moved by an NLA strip says to mute its track, which works, instead of the strip, which does not.
- **0.19.0:** a full review's fixes. A finished model can be moved, hung on something that moves, copied whole with Shift+D, or have its parts renamed, and it keeps playing right. Set Origin or Apply Scale on a built part no longer throws it off: it is put back on its frame, and nothing moves. An object takes part in one move (a second move is turned down with the reason, instead of breaking both), and a part's unselected children are named. Ring no longer stops with an error on petals copied with Alt+D, and Build never takes animation away from other objects; parts moved by an NLA strip or a driver are named. Spread's Step follows what you change in its dialog, and Ring's Lead step starts at 0 every time. Clearer reports.
- **0.18.3:** the list under **Riding along** can be read at the sidebar's usual width. Its header keeps its count ("Riding along (7)") instead of being cut off, and each row keeps the end of the part's name, where the number of a Ring's copy is, so seven copies no longer all read the same.
- **0.18.2:** CopyThat needs **Blender 4.5 or newer** (on 4.4 every Build stopped with an error) and is tested on Blender 4.5 LTS, 5.0 and 5.2. On 4.5 and 5.0 a file tidied by Build is redrawn at once, instead of showing the old pull until it was reopened, and on 4.5 each stray keyframe is counted once.
- **0.18.1:** Ring takes up or re-frames an object only when that is provably safe. It leaves alone, and names, objects with keys or drivers of their own, linked from a library, or that cannot be selected; it re-frames only plain objects and puts back anything that would look different. Objects are matched as sets of points, so a Ctrl+M half of a flower and the teeth of a gear copied and never turned are taken. Fill the gaps never copies onto anything standing in a place, and is turned down when copies stand near the ring but off its places (a wrong 3D cursor or Count). Spread's default Step is sized to fit, and Both ways opens on for Leads around a ring.
- **0.18.0:** Ring can use what is already modelled: a **Use** choice (Make copies, Use what's there, Fill the gaps). Spread works by **Step** (a start and a step for each place in the order) or **Range**. Ring's Lead step works the same way.
- **0.17.1:** Make Chain follows the way joints are built, so a leaf folded in pleats is chained in the right order. Reports use the right singular and plural.
- **0.17.0:** the four tools: **Spread**, **Make Chain**, **Curl** and **Ring**.
- **0.16.0:** copies of a whole finger ride along joint for joint. A follower can lead riders of its own. Each part is moved by its own bone only. Fixed a crash when several objects rode along at once.
- **0.15.0:** renamed from RigMoves to CopyThat. Files made before keep working.
- **0.14.x:** **Follows**: parts that hang from parts, like a finger. Fixes for followers. The author credit.
- **0.13.0:** **Animate** over frames, the **Pivot** picker (Origin, Cursor, Base), **Mirror** for riders, **Paths** preview, and **Curve the Path**.
- **0.12.0:** a **Lead** for riders and the **Play** slider for the whole move. Timing changes take effect at once.
- **0.11.0:** **Ride Along**: other objects copy the leader's move from their own place.
- **0.10.0:** **Speed** per stretch.
- **Before 0.10 (as RigMoves):** the foundation. Record Before and After, Steps in between, Build, Ease, per-part Timing, Combine, and the viewport handle. Works on loose objects with no rig and makes one.

Each release also fixes the bugs found while testing it. The full list is in the user guide that comes in the download.

## Support and credits

**Support.** If something does not work, first read the report box at the bottom of the panel, then the Troubleshooting section above. For anything else, ask through this product's page on Superhive, or visit the author's site at https://creators.sa/nemve. To help us help you, include:

- your Blender version and your CopyThat version;
- the text of the report box;
- what you pressed, in order;
- if you can, a small `.blend` file that shows the problem.

**Credits.** CopyThat is made by **NemVe3D** (https://creators.sa/nemve). It was called RigMoves before version 0.15.0, which renamed it.

**Licence.** CopyThat is free software under the **GNU General Public License, version 3 or (at your option) any later version (GPL-3.0-or-later)**. The licence text is included in the download. You may use, study, change and share it under those terms. The scenes and animations you make with it are yours.

Copyright 2026 NemVe3D.
