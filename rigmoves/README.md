# RigMoves (experiment) - v0.14.2

Move the parts of a machine by hand, record where they were and where they
ended up, and get one control that plays it. There is no rig to build first:
select the objects, and the tool makes the bones, binds them and drives them.

A control can be a slider in the panel or a handle you grab in the viewport.
Several recordings can be combined under one control, each starting when you
say.

Separate from RigKit / Rigthebot. Shares no code with it and never touches it.

## Install

Edit > Preferences > Add-ons > Install from Disk, pick `RigMoves-0.14.2.zip`,
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
just far enough to clear. Grab it, slide it, key it with **I**. The handle can
be turned off, and the move becomes a slider in the panel instead - that switch
is no longer on the panel, but still works from Python (`handle` on the move,
then Build).

Both write the same number, so switching between them changes nothing about
how the move plays. The handle is held to its rail, so it cannot be dragged
past either end.

Every built move, and every combined control, also has a **Play** slider in
the panel, 0 to 100%. It plays the whole thing - from the first part to set
off to the last one to arrive, riders ahead of or behind their leader
included - and it is the same control as the handle: drag either and the
other follows. The key button beside it keyframes the control at the current
frame, the same key as **I** on the handle.

### Playing it on the timeline

Under Play, set **Frames** and press **Animate**: the control is keyed to play
the whole thing from the current frame, over that many frames, and the scene
is made long enough to hold it. Pressing it again replaces those keys rather
than adding to them. The keys are even in time, so the shape of the move is
still its own Ease and speeds. Keyed handles are left alone by Build - that
is how the finished machine is meant to be animated; only a single key left
by a drag with Auto Keying on is lifted - and when a Build makes
a handle's rail longer or shorter, its keys are stretched with it, so the
animation still runs from end to end.

### Where a part turns: the pivot

A part turns about its **pivot**. Between two recorded poses the pivot goes
in a straight line and everything else swings round it, so it decides the way
from one pose to the next - the poses themselves never change. A lid turning
about its middle cuts through the box on the way; turning about its hinge, it
swings open.

Select the parts and press one of the **Pivot** buttons:

- **Origin** - the object's own origin, as before.
- **Cursor** - wherever the 3D cursor is. Put it on the hinge first: select
  the hinge edge in edit mode and **Shift+S > Cursor to Selected**.
- **Base** - the middle of the bottom of the object's bounding box.

No origins need moving. A pivot can be picked before the first Build or any
time after; on a built move the path is re-keyed so every recorded pose -
Before, After and every step - stays exactly where it was. Riders turn about
their leader's pivot, carried over to where each one stands.

### Starting the next thing

Select an object the rig has never been told about and the panel says so. What
it offers depends on what else is selected, because that is what says where
the object belongs:

- **Selected with a group** - one of that group's own parts, or its handle -
  and the panel names it and offers **Add To This Group**. Where the object
  stands now becomes its Before; then press the eye beside After, put it
  where it should end up, and Record After.
- **Selected on its own**, and the panel offers **New Group Here** and **New
  Rig**, for whichever was meant.

The group the selection points at is offered first and large. Every other
group on every rig in view is listed underneath, for when it is not.

When one of the selected objects is a part that already moves, **Ride Along**
is offered first - see below.

### Riding along

For a flower, record one petal and let the others copy it. Select the petals
that should follow, then the recorded one last, so it is the active object,
and press **Ride Along With '...'**. Each of them now does what the recorded
petal does, but from where it stands and facing its own way: whatever the
leader does to its own left, a rider does to *its* own left. Eight petals
round a centre all open outwards, each in its own direction, from one
control.

A rider turns about its leader's pivot, carried over to where it stands:
set the pivot on the leader - its hinge, its base - and every rider swings
about the same point on itself. No origins need moving.

Riders are listed under **Riding along**, each with a **Lead** slider from -50
to 50 that says when it moves against its leader. 0 moves with it. Below 0 it
follows behind: -25 sets off when the leader is half way, -50 only once the
leader has finished. Above 0 it goes first, and at 50 it has finished before
the leader starts. Either way it travels at the leader's speed, for as long
as the leader does - only when changes. Petals at -8, -16, -24 and on round
the flower open one after another, in a wave.

The move's control, and the **Play** slider, always cover the whole of it, so
a rider sent ahead has somewhere to go: the leader simply starts later along
the control. A lead takes effect as soon as it is changed.

Riders follow everything the leader's path does - steps in between, speeds,
Ease, a curved path - and a rider half the size of its leader still travels
as far. The **x** on a rider's row takes it out again and leaves it where it
stands.

**Mirroring.** A rider that is a mirrored copy of its leader - negative
scale, the way **Ctrl+M** leaves one - mirrors its leader's move by itself:
the left wing does the mirror image of what the right one does. A rider that
only *faces* the other way, such as the second of a pair of doors turned round
to fit, has a **Mirror** button on its row. Each press steps it on - none, X,
Y, Z - and rebuilds: X, Y or Z mirrors the leader's move across that axis of
its own, so what is the leader's left becomes the rider's right. A mirrored
rider turns about the mirror image of its leader's pivot.

Riding along can be set up before the leader's After is recorded as well;
it takes effect at the next Build.

Without this the panel simply went on showing the finished rig, with nothing
on screen to say how to begin the next thing.

### Followers: parts that hang from parts

A finger is three segments, each turning at its own knuckle, each carried by
the one before. Put them in one move and open **Follows**: beside every part
is a list of the move's other parts. Pick the first segment for the second,
and the second for the third. A follower goes wherever the part it follows
takes it, and does its own move on top.

Give each segment its knuckle as its **Pivot** (3D cursor on the joint,
**Cursor**), so each one turns where a finger bends. Then pose and record as
usual. Every recorded pose lands exactly where it was put; in between, each
joint turns about its own knuckle while the joint before carries it, so the
finger curls instead of its pieces sliding apart. **Timing** still gives each
segment a delay of its own - the tip can wait for the base.

A follower's object hangs from the object it follows, before the first
Build and after it, so dragging the first segment brings the others along
on screen. Leave a follower where it was carried and it keeps its own joint
as it was and rides along; drag it from there to bend its own joint. A
follower added to a built move with no After of its own rides along with
what it follows - the eye on After shows it carried. The bones play the
move; the objects hanging from one another only keep the dragging honest.
A file built with 0.14.0 shows "Build to put it into effect" under
**Follows**: press **Build** once, so the objects hang from one another.
Changing **Follows** on a built move waits for **Build**, which says so in
red. A pick that cannot be - the part itself, a rider, a loop - is turned
down with the reason, and the choice it had stays. Objects already parented
to one another in the file - a finger modelled joint by joint - follow the
same way without being asked, by **New Move** or **Add To This Group**, and
are hung from their old parents again if the move is removed.

A follower goes where it is carried, so its path is not curved: curve the
part it follows instead, and a part with a curved path straightens it
before it follows.

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

### How fast each stretch goes

Steps cut the move into stretches: Before to Step 1, Step 1 to Step 2, and on
into After. Between every two rows is a **Speed** slider for the stretch that
joins them, from -50 to 50. 0 is even. Every 15 points is about twice as fast,
50 is ten times, and below 0 is slower the same way; the note beside the
slider says by how much.

A sword swing: Before is the raised sword, Step 1 mid swing, After the
follow-through. Speed -30 into Step 1 and +30 into After, and it gathers
slowly and then strikes.

The move always fills its whole control, so a speed only counts against the
other stretches - every stretch at -50 plays exactly like every stretch at 0.
How fast the whole move plays is still how fast the control is moved. A
speed takes effect as soon as it is changed, so scrub the control to judge
it, and it slows or hurries every part of the move together, including the
ones that have no key at that step.

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
A delay, like an ease or a speed, takes effect as soon as it is changed.
Riders are not listed here; their **Lead** does the same job.

A combined control has the same box per member.

### How it gets there

The **Ease** menu shapes the whole move: even speed, smooth, slow start, slow
stop. It sits on top of whatever path was recorded, so a hand-shaped path with
Smooth on it eases into and out of your own curve.

For exact control of each stretch use the speeds instead, with Ease left on
Even speed. The two stack, the ease first.

### Going round things: curved paths

From A to B a part goes in a straight line, which is no use when something
is in the way. Select it and press **Curve the Path**: a curve appears along
the path it has - through its steps, if it has any - with a point in the
middle to take hold of. Press **Edit** beside it (or Tab into it), drag the
curve round the obstacle, add points if it needs them, and Build. The part's
pivot now travels along the curve, evenly by distance, and turns from pose to
pose as it did before.

The two ends of the curve always belong to Before and After. Every Build puts
them back there - drag an end away, or record After again, and the curve's
ends follow the part, not the other way round. The **x** beside the curve
deletes it and the path goes straight again. Riders follow a curved leader
along the same curve, carried over to their own place.

### Seeing the path

**Paths** draws a line through where every part of the move goes, Before to
After, through the middle of each part: steps, pivots, curves, mirrors and
all. It is drawn again at every Build, can't be clicked or rendered, and goes
when Paths is pressed again.

## Everything else on the card

- **Record** either row saves where the parts are standing at that moment. The
  eye icon beside it puts the model back into that pose so you can check it.
- **Parts** replaces the move's bones with whatever is selected now, keeping
  the timing of the ones that stay.
- **From / To** and **Path length** - what numbers the control's two ends read
  as (0 and 1 by default, 0 and 360 reads better for a spin) and how many
  frames the path is drawn over - are no longer on the panel, but still work
  when set from Python. Changing the length stretches the path without losing
  its shape.
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
    t = (t - start) / (end - start)           this part's own window, clamped
    t = ease(t)                               the shaping
    t = speeds(t)                             the stretches' shares, with steps

A part's window is its delay to the end. A rider's is its leader's, shifted
by its lead - a whole leader's travel at 50 either way - so it can begin
before the move does or finish after it. The windows are then laid on the
control from the earliest start to the latest finish, which is why the
control always plays everything. Without riders that is 0 to 1 and nothing
changes.

The speeds are not in the expression, which a delay and an ease already bring
close to the 256 characters Blender will hold. They are keys on the driver's
own curve - Blender reads a driver curve that has keys as a map from what the
expression says to the value written - one key per pose, at the share of the
control the speeds give it. With every stretch even the curve has no keys at
all, and the driver is exactly what it was before speeds existed.

A rider gets a bone of its own, turned from the rider exactly as the leader's
bone is turned from the leader, and every Build gives it a copy of the
leader's channels. The same channels on a bone turned the same way are the
same move, seen from the rider - at every point along the path, not only at
the recorded poses.

A follower's bone hangs from the bone of the part it follows, so it plays its
own path in its parent's space. Choosing a part to follow on a built move
keeps every recorded pose: each key is worked out again as what the parent
does at that key, undone, then the pose that was there - and parents are
redone before the parts that hang from them, so each is worked against its
parent's new keys. A part that never follows hangs from the root.

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

The bone stands on the part's pivot. A pivot is kept in the object's own
space at Before, so it goes with the object when Before is taken again. When
a built part's pivot moves, every key is worked out again before the bone is
moved: a bone moved by d along its own axes, posed with turn R, has to be
carried R*d - d less far for the part to land where it did. So every key
holds its pose, and only the way between keys changes.

A curve is laid onto the path at every Build as 40 location keys between
Before and After, evenly by distance along it, after its ends are pinned to
where the pivot starts and stops. Those in-between keys belong to the curve:
a step's location on a curved part is the curve's, and its turn stays the
step's.

A mirrored rider plays its leader's channels turned by a mirror, worked out
in the leader bone's own axes. Mirroring a location or a quaternion is
linear in the numbers on the curves, so keying the mirrored values on every
frame the leader has a key on mirrors every frame in between too. A mirror
image's frame is left-handed, which no bone can be, so its X is turned round
to stand the bone in, and a mirror across X puts it back - which is why a
Ctrl+M copy needs no setting, and why mirroring one of those across X again
undoes it.

The path preview is read off the action, not played: no frame changes, nothing
moves while it is drawn.

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
  monotonic throughout, so they never did anything - and a part's window is
  written to four decimals. Six figures were enough until riders: a rider's
  window lands on fractions like a twelfth, and a combined, eased driver
  printed that way came to 262. Worst case across every delay, lead, ease and
  grouping is now 236 characters, and the build - and any live change - reads
  the expression back and says so if one was ever cut short.
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
- **Removing a move left its handle's driver behind.** The slider went, but
  the driver that wrote it from the handle stayed, pointing at a property and
  a bone that no longer existed - and Blender warned about it on every update
  from then on. Removing a combined control did the same. Both drivers now go
  with their sliders.
- **One warning hid the others in the Build report.** A part keyed by hand
  ended the report early, so a driver cut short on the same Build was never
  mentioned. Every finding is reported now, and the warning stands if any of
  them is one.
- **A keyed handle was called a fault.** Build warned that a handle with a
  real curve on it was "animated by hand" - which is exactly how the
  finished machine is meant to be animated. Only a part's own bone keyed on
  top of its path is worth a word now.
- **A mirrored rider turned about the wrong point.** Its bone was stood on
  its leader's pivot carried straight over, then the move was mirrored about
  that - but the mirror image of a pivot off the mirror's plane is somewhere
  else. With the pivot on a wing's root the copy drifted 0.68 off its true
  After. The bone stands on the mirrored pivot now; and since a mirror moves
  the bone, the Mirror button rebuilds.
- **A Build could stop an animation half way.** Every Build sizes the handle's
  rail again, and a new pivot or rider changes it, while the handle's keys
  stayed in the old length: a move animated over 40 frames reached 69% of
  the way. The keys are stretched with the rail now, and so is an unkeyed
  handle's place on it.
- **The Base pivot and the path preview read the part where it stood, not as
  it was made.** Blender 5's bounding box follows the rig, so with the lid
  open Base landed on its top and the drawn path was a whole move off, and
  handles were sized from wherever the control happened to stand. All three
  read the mesh as modelled now.
- **A mirrored copy of a hand-eased leader ran straight between keys.** Keys
  shaped in the graph editor bend between keys; the mirrored copy is keyed
  every half frame when they do.
- **A removed control left its animation behind.** Its keys stayed on the
  rig, and the next control that landed on the same name played them. They
  go with the control now.
- **Editing a curve lost the rig.** With only the curve selected the panel
  could show another rig, or none, and Build built the wrong one. A path
  curve now belongs to its part's rig.
- **Animate set off the stray-key alarm**, whose Lift button then did
  nothing. Only keys worth a word raise it now.
- **Animate keyed a slider still driven by a handle switched off since the
  last Build**, said it had worked, and nothing played. It asks for a Build
  first now.
- **Hiding one rig's paths could delete another's.** They were found by name;
  they are held by reference now.
- **A new pivot on a curved part bent its path.** Only the curve's ends were
  pinned to the moved pivot, its middle stayed where it was, and a box that
  never turns rose half a metre mid-way. The whole curve moves with the
  pivot now.
- **Buttons that Build on the side threw away a drag.** Set Pivot, Curve the
  Path, Straighten, Mirror, Ride Along and taking a rider out all run a
  Build, which puts a dragged part back on its Before - so a new After
  dragged into place and not yet recorded was lost without a word. They
  refuse now, and say to record it first.
- **A handle keyed once was deleted by the next Build**, and the report
  blamed Auto Keying even with it off. A lone key on a handle is what a drag
  with Auto Keying on leaves behind - but also the first press of the key
  button. It is lifted only while Auto Keying is on now.
- **Paths was offered where it could draw nothing**, said to record and
  Build when both were done, and stayed pressed. It is offered only on moves
  with objects, and goes back off when there is nothing to draw.
- **Curve the Path on a part that had a curve** said to select the part. It
  says the part has one already, and where to edit it.
- **Turning the base of a finger shown bent tore its joints open** (0.14.1).
  With the finger posed, a drag of the base reached each bent follower
  before its own bend. A follower that was only carried is now read as
  carried whole, keeping its own joint.
- **A built finger was thrown off by the first Build after a base was added
  under it** (0.14.1): standing the new base on its Before carried the
  finger off its own. It is let go of first and hung again after.
- **Record put objects back in the wrong order** while a Follows change
  waited on Build, throwing the followers off. Parents go first now.
- **A file from 0.14.0 gave no sign it needed a Build** for its followers'
  objects to hang. The panel says so now.
- **Parts added to a built move as followers never rode along.** Built
  straight away they stayed at home, and the eye on After showed them
  there. They ride along now, and are shown carried.
- **Build without Record After ticked the After row** and said nothing, and
  the control moved nothing. The row keeps its dot and Build says After is
  not recorded yet.
- **After a Build, dragging the leader left its followers behind.** Only
  the bones hung from one another once built; the objects all hung from the
  rig, so the first segment moved alone and there was no closed finger to
  record. A follower's object hangs from its leader's after a Build too.
- **A pose hidden under live sliders was counted into the next drag.** The
  eye, or a Record, leaves the bones posed, and Build only hides that under
  the sliders. A part dragged to z 2 played at z 3. Record reads what is on
  screen before it pauses anything now, and Build clears those poses.
- **Turning a chain round on a built move lost its poses for good.** The
  bones were hung one at a time, so one was asked to hang from its own child,
  which Blender refuses without a word - after its keys had been worked out
  for the new parent. Every bone is let go first and hung parents first now,
  and read back.
- **A follower dragged on a step was keyed against the wrong parent pose** -
  its parent's path, while the parent was keyed at the pose it was showing.
  It is solved against the pose its parent is about to be keyed at, parents
  first by the bones that carry them, not by a Follows change still waiting.
- **A loose follower of a built part was pulled back before it was read.**
  Record put the dragged parent back on its Before first, carrying the
  follower with it. Every loose part is read where it was seen, first.
- **A new pivot, or a Follows change, moved the steps of the parts below.**
  A parent was re-keyed only on its own keys, and a follower's step stood on
  where the parent was between them. Every pose frame of the move is kept
  now.
- **A slip in the Follows list undid the choice that was there**, and the
  object's own parent was forgotten. The choice it had stays now, and the
  parent is given back when following stops or the move goes.
- **Removing a move before its first Build left its objects hung on one
  another.** They are let go.
- **The path preview drew a delayed follower where it never goes.** It is
  traced along the control now, each joint on its own frame.
- **Build said parts were hung when they had been let go.** It says which.
- **A part dragged while its bone was posed was recorded somewhere else.**
  Record read a dragged object's own transform - but with its bone posed, by
  the eye on After or by a Record just before, the part is seen carried by
  the bone, and the drag was made from there. It is read where it is seen
  now, bones and all.
- **Setting a curve's point from code bent its handles.** Blender recomputes
  an aligned handle whenever its point is set on its own, and swings it off
  to one side. Curve points are written all at once now.
- **Reloading the add-on failed with "already registered".** Registering
  looked for an old copy in `bpy.types`, which does not list property groups,
  so nothing was taken down and the first class refused to register again. The
  old copy is now asked for through its base type, which does find it.

## Known rough edges

- While a finger is shown bent, dragging its base opens the bent joints on
  screen. What is recorded is the finger carried whole, joints shut; pose
  at Play 0 to see it as it will be.
- Changing **Follows** waits for **Build**. Posed before that Build, a
  follower is recorded as it is seen, not with its own joint kept - and a
  follower bent by hand then is not recorded right. Build first.

- Before should be the rest pose. Nothing warns when it is not, and a machine
  recorded from a half-posed start will be wrong at the ends.
- Steps are only offered once a move has bones, so for objects that means
  after the first build.
- An object is bound whole, to one bone. Parts that bend need a rig of their
  own and the bone workflow.
- Two moves sharing a part compose in the order they were made, which is not
  shown anywhere.
- A move can be in only one combined control at a time.
- A part follows another part of the same move. A follower cannot lead
  riders - they would copy only its own move and be left behind - and a part
  that leads riders cannot follow.
- An object parented to something outside the rig - a finger to a hand that
  is not in the move - is taken off that parent while it is bound, so moving
  the hand leaves it behind. Parent the rig to the hand instead.
- A rider copies its leader from where it stood when it joined. To move one,
  take it out and add it again. A rider cannot lead others, and only objects
  can lead - a bone of a hand-built rig is not offered.
- A mirrored rider is exact for moves and turns. A part that also changes
  size unevenly on the way is copied unmirrored in its size.
- Pivots, curves and the path preview are for objects; bones of a hand-built
  rig turn about their own heads, as they always did.
- A curve takes over the in-between location of its part, steps included,
  and going back to straight drops the steps' locations with it.
- Only a curve's first spline is followed, Bezier or Poly.
- Animate replaces whatever keys the control had. For anything more, key it
  by hand with the key button.
- Combining always takes every move that is not already in one, laid end to
  end. There is no way to pick which ones from the panel yet, only to take
  them out again afterwards.
- Handles are always laid along the rig's up axis and placed above the parts.
  There is no way to move one somewhere better yet.
