# RigMoves (experiment) - v0.9.2

Move the parts of a machine by hand, record where they were and where they
ended up, and get one control that plays it. There is no rig to build first:
select the objects, and the tool makes the bones, binds them and drives them.

A control can be a slider in the panel or a handle you grab in the viewport.
Several recordings can be combined under one control, each starting when you
say.

Separate from RigKit / Rigthebot. Shares no code with it and never touches it.

## Install

Edit > Preferences > Add-ons > Install from Disk, pick `RigMoves-0.9.2.zip`,
tick it on. Panel: 3D view sidebar (**N**), tab **Moves**.

## Use

Starting from loose objects, with no rig anywhere:

1. In object mode, select the objects that move together.
2. **New Move**. Where they stand now is recorded as Before.
3. Move and rotate them by hand, however you like. **Record** on the After row.
4. **Build Sliders**.

That last press is where the rig appears: each object is given a bone of its
own, bound to it, and put on the path between its two recordings. From then on
the move behaves exactly like one recorded on bones, so everything below
applies to it.

If the model already has an armature, work in pose mode and select bones
instead at step 1. The rest is identical.

That is the whole of the simple case. The five things below are what make it
worth having over a pair of poses.

### Panel or viewport

Every move gets a **handle in the viewport** by default: an arrow on a rail
over the parts it drives. A move's handle has **one** arrowhead, a combined
control has **two** and is drawn larger, so the one that plays everything is
never mistaken for one that plays a part of it.

A handle stands at the middle of the parts it drives and is sized from them,
so it sits on the machine rather than hanging in the air above it. The rig is
drawn in front of the mesh, so a control inside the machine is still there to
click. Where two would land on top of each other they are stacked upwards,
just far enough to clear. Grab it, slide it, key it with **I**. Under **Where to
drive it** you can turn the handle off, and the move becomes a slider in the
panel instead.

Both write the same number, so switching between them changes nothing about
how the move plays, and the panel shows the handle's position either way - so
it can still be typed in and keyed without hunting for it in the viewport. The
handle is held to its rail, so it cannot be dragged past either end.

### Starting the next thing

Select an object the rig has never been told about and the panel says so. What
it offers depends on what else is selected, because that is what says where
the object belongs:

- **Selected with a group** - one of that group's own parts, or its handle -
  and the panel names it and offers **Add To This Group**. Where the object
  stands now becomes its Before; then press the eye beside After, put it
  where it should end up, and Record After.
- **Selected on its own**, and the panel offers **New Rig**, with **New Group
  On This Rig** underneath for when that is what was meant.

There is no menu of every group on the rig. The selection has already said
which one.

Without this the panel simply went on showing the finished rig, with nothing
on screen to say how to begin the next thing.

### Several moves under one control

Record one group of parts, then another, then press **Combine**. A new control
appears that plays them both. Every member gets its own **Delay**, as a
fraction of the combined control's travel, so the second group can start when
the first is half way, or wait until it has finished.

The moves keep their own controls as well. The two are combined by taking
whichever is further along, so a move can be played alone or as part of the
sequence and neither blocks the other. Take a move out of the combination with
the **x** on its row; delete the combination and its members are untouched.

### Steps in between

Left alone, a move goes straight from Before to After. A **step** is where you
say it should go some other way round - a hatch that swings clear before it
slides, a lid that overshoots and settles back, an arm that lifts before it
reaches.

Press **+ Step in between**, on the row between Before and After. A **Step 1**
row appears with a Record of its own, and from there it is the same gesture as
the other two:

1. move the parts to where they should be part way through;
2. press that step's **Record**.

Add as many as you like; they play in the order they are listed and are spread
evenly between the two ends. Each has an eye to check it and an **x** to take
it off. The control replays your steps instead of a straight line, and still
lands on Before and After exactly at its two ends.

Only the parts you actually moved are saved into a step. Anything you leave
alone carries on through that point on its own path, so a step can speak for
one part of a group without disturbing the rest.

The frames are only a place to draw the shape in. The control always runs the
whole of it, however many frames long it is.

Measured: with one key placed half way, the control at 0.50 reproduced that
key's pose instead of the 0.50 a blend would have given, and still landed on
Before and After exactly.

### Who moves when

Open **Timing**. Every part has a **Delay**, as a fraction of the control's
travel. Delay 0.2 means that part waits until the control is a fifth of the
way across before it starts, and then runs to the end. That is what stops a
machine reading as one rubber object: the parts leave in order, and overlap.

A combined control has the same box per member.

### How it gets there

The **Ease** menu shapes the whole move: even speed, smooth, slow start, slow
stop. It sits on top of whatever path was recorded, so a hand-shaped path with
Smooth on it eases into and out of your own curve.

## Everything else on the card

- **Record** either row saves where the parts are standing at that moment. The
  eye icon beside it puts the model back into that pose so you can check it.
- **Parts** replaces the move's bones with whatever is selected now, keeping
  the timing of the ones that stay.
  two ends read as (0 and 1 by default, 0 and 360 reads better for a spin) and
  how many frames the path is drawn over. Changing the length stretches the
  path without losing its shape.
- **x** on a move deletes it, its control, its path and its constraints, and
  leaves the rig exactly as it was.
- **Pause** switches the move off so the bones can be posed by hand again;
  Build puts it back. Recording does this for you.
- **To Before** returns every control to its start.

## What it does underneath

Each move owns an **Action** holding the path. Each part gets an **Action
constraint** carrying that action, sitting at the top of the bone's constraint
stack, with its evaluation time driven from the move's number:

    t = (number - from) / (to - from)         how far across the move
    t = (t - delay) / (done - delay)          this part's own window, clamped
    t = ease(t)                               the shaping

Top of the stack matters: whatever constraints the bone already had still run
afterwards, so a hand-built rig can be given a control without being taken
apart. The first move on a bone replaces its pose, any later move composes on
top, so two moves can share a part.

The Action constraint is also why an arbitrary path is possible at all. A
plain driver can only interpolate a straight line between two numbers; an
action can hold any curve, and it can be edited in the graph editor like any
other animation.

The viewport handle is a non-deforming bone with a Limit Location constraint
for its rail, which drives the move's custom property. So the property stays
the one number everything reads, whichever way it is written.

The armature is seated on the middle of the parts it drives, so Blender's
relationship lines run to the machine rather than to the world centre, and the
root bone sits with it. The bones move back by exactly what the object gains,
so nothing on screen shifts.

An object that had no rig keeps its two placements on the move itself until
the first build. That build stands it where Before was recorded, makes a bone
there, binds the whole object to that bone with one vertex group at full
weight, and writes the two placements as the ends of the path. Before is
therefore the rig's rest pose, and the bone carries only the difference to
After. Removing the move takes the group, the modifier and the parent off
again and leaves the object exactly where it stands.

## Tested on

`10_mechanicalEye.blend` - a hand-built rig whose four eyelids are moved by
three controller bones through Transform constraints on Limit Location rails.

| | |
|---|---|
| control at its ends, against the recorded poses | 0.0000 degrees |
| staggered parts (0-0.5, 0.2-0.8, 0.5-1.0) | each waits, travels its own window, holds |
| one hand-placed key half way | control at 0.50 gives 0.933 through, not 0.500 |
| ease at 0.25 | even 0.467, smooth 0.292, slow start 0.117, slow stop 0.817 |
| handle dragged along its rail | slider follows 0.000 to 1.000 |
| handle dragged three times past the end | clamped to the rail, control capped at 1.000 |
| handle switched off and on again | bone removed, slider editable, then back |
| two moves combined, second delayed to 0.4 | at 0.3 only the first has moved, at 0.5 the first is 0.84 and the second 0.16, at 1.0 both are home |
| each move's own control, with the combined one at 0 | plays only its own parts |
| combined at 0.5 and a member's own control at 1.0 | the member goes fully, the other still 0.16 |
| rename a built move | constraints follow, drivers keep working |
| remove a move | 0 drivers, 0 constraints, 0 properties, 0 actions left; the rig's own 13 constraints untouched |

And on two loose cubes with no armature in the file, one rotated 90 degrees
and one lifted 1 m:

| | |
|---|---|
| New Move with objects selected | an armature with a Root bone appears |
| Build | a bone per object, bound, both placements written |
| control at 0 and at 1 | 0.000000 m and 0.000001 m from the recordings |
| in between | a true 90 degree arc, not a straight line through the middle |

## Bugs found and fixed while building this

- **A delay plus easing silently killed the driver.** A driver expression
  lives in a fixed 256-character string, and Blender cuts a longer one off
  where it stands without a word - leaving an unclosed bracket, a driver that
  fails to parse, and a part that simply never moves. Easing writes the whole
  expression three times, so it was reached easily: a delay and Smooth on a
  move inside a combined control came to 284 characters. Ten-digit floats
  printing 0.2 as 0.200000003 were much of the rest. The expression is now
  written without the clamps that only repeat what the last one does - it is
  monotonic throughout, so they never did anything - and numbers are written
  to six figures. Worst case across every delay, ease and grouping is 212
  characters, and the build now reads the expression back and says so if one
  was ever cut short.
- **Which delay row belonged to which part was guesswork.** Four lids off one
  machine differ in the last character of a truncated name. The row for
  whatever is selected in the viewport is now the one left at full strength
  while the others go quiet, and the icon on any row selects that part - so
  picking a part and setting its delay is one gesture in either direction.

- **Where to drive it is gone.** The panel held the handle switch, the slider's
  bone and range, and the path length - settings that were read far less often
  than they were scrolled past. Every one of them still works; none of them is
  on screen any more.

- **A new rig could inherit a deleted rig's path.** A move claimed an action
  named after its rig, and actions are kept alive by a fake user so a path
  survives saving - so a rig landing on a deleted one's name picked up its old
  action and started life with somebody else's keys already on it. The name is
  made free before it is taken now.

- **A newcomer could only be offered the groups on one rig.** The panel shows
  one rig at a time, but each cluster of parts in the viewport reads as a
  group whatever armature happens to hold it - so somebody with two rigs on
  screen, selecting a new block, was told only "New Rig" or "New Group On This
  Rig", and the group they were pointing at was not on the list at all. Every
  group on every rig the user can see is now named, with the rig it belongs to
  beside it, and joining one moves the panel across to that rig. Rigs whose
  parts have been deleted are left off, so the list is places something can
  actually go.
- **Adding a part to a finished group flattened the parts already in it.**
  Record keyed every part in the move, and the ones already there are standing
  at their Before - so "no change" was saved over the motion they had, and
  every one of them silently stopped moving. Only what was actually posed this
  time is recorded now; the rest are left alone and counted in the report.

- **Auto Keying broke the rig twice over, and a warning was not enough.** With
  it on, every drag this tool asks for leaves a keyframe behind. Dragging a
  part into its After pose keys the part, and a bound object's own transform
  is the rest the move is measured from - so the rest became the After pose
  and the slider played from the wrong end, travelling twice as far. Dragging
  a handle in pose mode keys the handle, which then springs back on the next
  frame change, so the control appeared to do nothing at all. The first pass
  at this only named the fault in the panel, which still left a broken rig on
  screen. Build now lifts both kinds itself: a key on a bound object's own
  transform is never valid, and a lone contentless key on one of our bones is
  what a drag leaves behind. Handles carrying a real curve are somebody's
  animation and are left alone, and said so. The panel shows the Auto Keying
  switch while it is on.
- **An object with keyframes of its own played the wrong move.** Binding makes
  an object's own transform the rest the modifier measures the move from, so a
  keyframe on that transform rewrites it on every frame change. The part then
  sits where the rig never put it and the slider is out by exactly the
  Before-to-After distance - for good, with nothing on screen saying why. Easy
  to hit by accident: with Auto Keying on, dragging a part into its After pose
  keys it, which is the very gesture this tool asks for. The panel now names
  the parts, offers to lift those keys, and shows the Auto Keying switch; the
  build refuses to report success while any are left.
- **Moving a bound object by hand recorded nothing.** Before the first build a
  part is posed by dragging the object; after it, the same drag was ignored -
  Record read the bone instead, found it at rest, and saved After as "no
  change", while the drag had quietly redefined the object's rest. The move
  then started at the wrong end and travelled twice as far. A drag off the
  Before is now read as the pose it plainly is, and the object is put back on
  its rest.
- **A drifted rig stayed broken.** Nothing ever put a bound object back where
  binding left it, so once the rest had moved there was no way back short of
  deleting the rig. Build re-seats every bound object on its Before, so a rig
  that has gone wrong comes right on the next Build.

- **Two moves could share one control.** Names were turned into property names
  with no check, so two moves called the same thing drove each other and
  removing either deleted the control of both. Names are now made unique.
- **Renaming a built move stranded its constraints.** They were looked up by
  the move's current name, so after a rename nothing could find or remove
  them. The name a build really used is now remembered, and a rename carries
  through to the rig.
- **Two moves with the same name collided on one bone.** Blender makes a
  constraint name unique by itself, so the driver was written against a name
  that did not exist. The name is now read back after it is set.
- **The panel vanished when a non-rigged object was clicked**, which reads as
  the add-on failing to load. It now stays and offers the rigs in the scene.
- **An Armature modifier pointing at nothing counted as a rig.**
- **Handles were stacked on top of each other.** Two moves over the same
  machine, and the combined control over both, all landed within a few
  centimetres, identical to look at - so grabbing one and getting another
  read as the combined control simply not working. They are laid out in a
  column above the machine now, and the combined one is larger with two
  arrowheads. Spreading them along a world axis was tried first and was
  invisible the moment the camera looked down that axis.
- **Forgetting a dead rig crashed the panel.** The check that drops a
  remembered rig once it is deleted did the forgetting inside the lookup the
  panel calls while drawing, and Blender refuses writes to a scene mid-draw:
  `Writing to ID classes in this context is not allowed`. Every redraw threw
  and took the panel with it, so there was no way to start anything new. The
  lookup only reads now; the forgetting happens in the operators.
- **An empty rig was a dead end.** The rig being worked on is remembered, and
  a rig whose moves had all been removed was still remembered - so the panel
  showed an armature with nothing on it, a newcomer had nothing to join, and
  the only way on was to add to the very rig that was the problem. A rig with
  no moves is no longer remembered.
- **A rig deleted from the scene went on being used.** This add-on keeps
  its data on the armature, so a deleted rig still answered questions about
  its moves while being impossible to select - and every button raised
  `ViewLayer does not contain object`. Nothing hands back a rig that is not in
  the view layer now, the remembered one is forgotten when it goes, and Build
  says so instead of failing.
- **Removing a move could leave its bones behind.** The mode switch that
  deletes them works on whatever object is *active*, so with a mesh selected
  it put that mesh into edit mode and the bones were never touched. The rig is
  made active first now, and every build also sweeps bones that no move claims
  any more - they carry a stamp saying this add-on made them.
- **The handle was sized from the parts it drives.** A move usually drives
  small controller bones on a big machine - the eyelid controllers are a tenth
  of the test rig - so the handle came out too small to grab. It is sized from
  the whole rig now.
- **Long bone names truncated from the front**, so two controllers read as the
  same row in Timing. They are cut from the front with an ellipsis instead.

## Known rough edges

- Before should be the rest pose. Nothing warns when it is not, and a machine
  recorded from a half-posed start will be wrong at the ends.
- Steps are only offered once a move has bones, so for objects that means
  after the first build.
- An object is bound whole, to one bone. Parts that bend need a rig of their
  own and the bone workflow.
- Two moves sharing a part compose in the order they were made, which is not
  shown anywhere.
- A move can be in only one combined control at a time.
- Combining always takes every move that is not already in one, laid end to
  end. There is no way to pick which ones from the panel yet, only to take
  them out again afterwards.
- Handles are always laid along the rig's up axis and placed above the parts.
  There is no way to move one somewhere better yet.
