# CopyThat - v0.20.2

Move the parts of a machine by hand, record where they were and where they
ended up, and get one control that plays it. There is no rig to build first:
select the objects, and the tool makes the bones, binds them and drives them.

A control can be a slider in the panel or a handle you grab in the viewport.
Several recordings can be combined under one control, each starting when you
say.

Separate from RigKit / Rigthebot. Shares no code with it and never touches it.

By **NemVe3D** - <https://creators.sa/nemve>

Formerly called RigMoves. Installing CopyThat replaces it, and files made
with RigMoves keep working: the panel is now the **CopyThat** tab.

## Install

CopyThat is a Blender extension, and it needs Blender 4.5 or newer: Blender
will not install it on an older one. First, if an older RigMoves or CopyThat
is listed under Edit > Preferences > **Add-ons**, switch it off and remove it:
the two cannot be on at once. Then drag `CopyThat-0.20.2.zip` into Blender,
or use Edit > Preferences > **Get Extensions** > the drop-down at the top
right > **Install from Disk**. Panel: 3D view sidebar (**N**), tab
**CopyThat**. Files made with older versions keep working.

## Use

Starting from loose objects, with no rig anywhere:

1. In object mode, select the objects that move together.
2. **New Move**. Where they stand now is recorded as Before.
3. Move and rotate them by hand, however you like. **Record** on the After row.
4. **Build Sliders**.

Select the whole machine at step 1. A handle parented (Ctrl+P) to a lid hangs from
the lid's object, but the rig moves the lid by deforming its mesh: the handle moves
with it only if it is a part of the move too. Left out, it stays where the shut lid
was, and New Move, Add To This Group and Build say so, naming it (up to three at a
time): select it too and press Add To This Group.

That last press is where the rig appears: each object is given a bone of its
own, bound to it, and put on the path between its two recordings. From then on
the move behaves exactly like one recorded on bones, so everything below
applies to it.

If the model already has an armature, work in pose mode and select bones
instead at step 1. The rest is identical.

That is the whole of the simple case. The five things below are what make it
worth having over a pair of poses.

### The panel, top to bottom

- **The header** has the gold flower and the name, and under it the line
  "Record a move. Get a slider.". The rig is on the next line, with how many
  parts and sliders it holds ("21 parts · 1 slider"), or under it where the
  sidebar is too narrow for both.
- **A box for each move.** Its first row is the move's name: the arrow folds
  the box, a click in the name renames it, and the **x** deletes the move. Under
  it, once it is built, is the **Play** slider with its key button, big. Then
  **Before** and **After**, each with its **Record** and the eye, and the **Step**
  rows between them if there are any; a tick says the pose is recorded (at the
  sidebar's usual width it stands before the name, as in a checklist). The rest
  folds away, in the order it is reached for: **PARTS & PIVOT**, **PATH**,
  **TIMING**, **COPIES**, **CHAINS** and **ANIMATE**. A new move has all of them
  shut. Click a title to open it. **COPIES** is there once a part can be ringed,
  **CHAINS** once two parts can be chained, **ANIMATE** once the move is built.
- **Under the moves:** **Build Sliders**, big, then **Pause** and **To Before**,
  then **New Move** (and **Combine**, with two moves or more), then the
  **REPORT**, and last, small, the add-on's name, version and author.
- **With no rig yet** the panel says what to select; with objects selected
  there is one big **New Move**.

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
the panel, 0 to 100%, first in its box. It plays the whole thing - from the
first part to set off to the last one to arrive, riders ahead of or behind their leader
included - and it is the same control as the handle: drag either and the
other follows. The key button beside it keyframes the control at the current
frame, the same key as **I** on the handle.

### Playing it on the timeline

Open **ANIMATE** (a combined control has **Frames** and **Animate** right under
its Play slider), set **Frames** and press **Animate**: the control is keyed to play
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

Select the parts, open **PARTS & PIVOT** and press one of the **Pivot** buttons:

- **Origin** - the object's own origin, as before.
- **Cursor** - wherever the 3D cursor is. Put it on the hinge first: select
  the hinge edge in edit mode and **Shift+S > Cursor to Selected**.
- **Base** - the middle of the bottom of the object's bounding box.

No origins need moving. A pivot can be picked before the first Build or any
time after; on a built move the path is re-keyed so every recorded pose -
Before, After and every step - stays exactly where it was. Riders turn about
their leader's pivot, carried over to where each one stands.

If an origin is moved anyway - Set Origin, or Apply Scale or Rotation, on a part
that is already built - nothing moves on screen, and CopyThat sees that the mesh
did not move: it puts the object back on the frame its move was recorded in, the
mesh moved the other way, and says so in the report. That is not a drag, so it is
never recorded as one. A part that was dragged as well, before the next button was
pressed, keeps the drag, which is recorded as the pose it is, and the report says
so. To change where a part turns, use Pivot.

### Moving the finished model

A built model can be moved as a whole: select everything - the rig and its
parts - and move, turn or scale it, or parent the rig to a hand, a car, an
Empty, and move that. Everything recorded goes with it. The next button you
press - Build, Record, Set Pivot, Ride Along, Ring, Spread - finds the model
where it now stands, so nothing jumps back and nothing has to be recorded
again. The rig can be animated too: it is caught up at the frame it is at. Only
the parts moved *without* the rig, one at a time, are read as a pose to record.
A curve for a part's path that is left behind is carried along with the rest.
Moving the rig alone carries the parts that are not built yet with the model, so
Build puts them back in their place in it; select them with the rig to move them
all. Ctrl+A and Set Origin on the rig are not a move: nothing moves on screen, and
CopyThat follows the Root bone, which they leave where it is.

### Renaming, and copying a finished model

A part is its object, whatever the object is called. Rename it (F2) and the part
takes the new name, and so does everything that named the old one - a rider's
leader, a Follows - at once. Copy a finished model - select the rig and its parts
and press Shift+D (or Alt+D) - and the copy is a model of its own: its parts are
its own objects, its path curves too, and it plays a path of its own, so building
the copy never changes the original, or the other way round. Duplicate the rig on
its own and you have a rig whose parts are the original's: duplicate them together.

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

A copy of a built part, made with Shift+D or Alt+D, comes into a move free of the
original's binding, so it stands where it is, and the eye shows it there: Blender
copies a rigged mesh with its group and modifier, which swing it about the
original's hinge until it has a bone of its own. (A copy never added to a move still
swings with the original: that is how Blender copies it.)

An object is in one move only, because it is bound to one bone. New Move, Add To
This Group and Ride Along leave out any object that is a part of a move already,
and say so by name; with nothing left to take, they refuse and change nothing. For
a second motion of the same object, add a Step to its move.

When one of the selected objects is a part that already moves, **Ride Along**
is offered first - see below.

### Riding along

For a flower, record one petal and let the others copy it. Select the petals
that should follow, then the recorded one last, so it is the active object,
and press **Ride Along With '...'**. Each of them now does what the recorded
petal does, but from where it stands and facing its own way: whatever the
leader does to its own left, a rider does to *its* own left. Eight petals
round a centre all open outwards, each in its own direction, from one
control. If the petals are modelled already and stand round a centre, you need
not select them by hand: **Ring** with **Use what's there** finds them and sets
them riding for you (see Ring, below).

A rider turns about its leader's pivot, carried over to where it stands:
set the pivot on the leader - its hinge, its base - and every rider swings
about the same point on itself. No origins need moving.

Riders are listed in **COPIES**, under **Riding along**, each with a **Lead**
from -50 to 50 (a slider in a wide sidebar, a number at its usual width) that
says when it moves against its leader. 0 moves with
it. Below 0 it follows behind: -25 sets off when the leader is half way, -50 only once the
leader has finished. Above 0 it goes first, and at 50 it has finished before
the leader starts. Either way it travels at the leader's speed, for as long
as the leader does - only when changes. Petals at -8, -16, -24 and on round
the flower open one after another, in a wave. **Spread...** beside
**Ring...** in **COPIES** fills those in for you, and **Ring** makes the petals as
well - see below.

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

### Four tools that cut the repetitive work

A flower is eight petals, a finger is three joints, a row of dominoes is a
dozen boxes. Recording the move is quick; what costs the time is making the
copies, choosing **Follows** one dropdown at a time, and typing a Lead, a
Delay or a bend for every part. Four buttons do that in one go. Each works
whether or not the move is built, says in the panel what it did, refuses with
the reason when it cannot, and is one Ctrl+Z.

### Ring: one part becomes a ring of riders

*When:* the same part goes round a centre - the petals of a flower, the
blades of a fan, the teeth of a gear, a crown of spikes - and you would rather
not select them all for Ride Along. Either the other copies are not modelled
yet and Ring makes them, or they are modelled already and Ring picks them up.

*Recipe:* record the part's move, put the 3D cursor on the centre, select the
part so it is the active object, press **Ring...** (in the move's **COPIES**
section), pick **Use**, set the **Count**, **OK**.

**Use** is one of three:

| Use | What it does | When |
|---|---|---|
| **Make copies** | a new copy for every place round the ring, whatever already stands there | nothing is modelled but the one part |
| **Use what's there** | takes up the objects already standing in the places, and makes nothing | every petal is modelled already, and you do not want one more object |
| **Fill the gaps** (the default) | takes up what stands in a place, and copies the part only into the places where nothing does | most are modelled and a few are missing - or you are not sure. It never puts a copy on top of a mesh object that is there (other kinds of object are not seen: see the rough edges) |

How an object already there is told from one that is not. Ring takes an object
up, or stands it on a new frame, only when that is **provably safe**; anything
else is left exactly as it is, and the report says why:

- **A copy of the part's mesh.** The same number of vertices, and every vertex of
  one within a fiftieth of how big the part is across of a vertex of the other,
  both ways round, once it stands in the place. Vertex numbering does not matter,
  so a mirrored half made with Ctrl+M, or the teeth of a gear made with Shift+D and
  G and never turned, are taken. A mirror image of a petal that is not the same on
  both sides is another shape, and is not.
- **Who may be taken.** A mesh object that is in view, free to select (Blender
  is asked, so a collection with selection switched off counts), local and
  editable, in no move of this add-on, and with no keys, drivers or NLA of its
  own. Left alone, and named: "has keys or drivers of its own" (Build lifts a
  part's own keys, and a re-framed object would jump when they play: use Lift
  Those Keyframes first), "is linked from a library" or "cannot be edited"
  (the change would be lost when the file is saved and opened), "is hidden",
  "cannot be selected", "is already part of a move".
- **Stood on a frame, only when plain.** A rider copies its leader's move from
  its own origin and axes, so a petal modelled with its origin somewhere else, or
  with its rotation or scale applied, would swing about the wrong point. Such an
  object is stood on the frame a copy would have - its origin and axes where the
  part's are, turned to its place - and its mesh is moved the other way. It
  gets a mesh of its own, so what shares the old one stays as it was. It is
  **not** re-framed if it has constraints, instances other objects, has
  particles, hangs from a vertex or a bone, has another object depending on it
  (a Child Of, a Shrinkwrap target, a modifier's target, a child hung from its
  vertices - only a child hung by the object is held in place, and not one with
  keys, a driver or an NLA strip of its own, which would throw it off on the next
  frame), has a modifier
  that reads its frame (anything but Subdivision, Triangulate, Edge Split,
  Weighted Normal or an Armature of another rig; Bevel and Solidify only at a
  scale of 1, before and after), or is mirrored and has custom normals. Textures
  that use the object's own or generated coordinates are not looked at: check
  those.
- **And then looked at.** After the change the evaluated result is compared with
  what it was - where every vertex is in the world, and which way every face
  faces as shown, a mirrored frame turned back - and the mesh's volume must wind
  the way the leader's does. Anything that moved by more than a hundred-thousandth
  of the part's size, or faces the other way, is put back exactly - frame, mesh and
  children - and left out: "cannot be re-framed safely (re-framing it would change
  how it looks): set its origin and rotation like the leader's, or use Make copies".
  It is all one Ctrl+Z, and a ring that cannot be finished puts every object back
  as found.
- **A chain is taken whole or not at all.** For a finger or a leaf (the part with
  the parts that follow it) a place is taken only when **every** joint of it is
  found and every joint that needs it can be re-framed. Found in part, the place
  is left alone and the report says so. When every place is like that, Ring is
  turned down with that reason.
- **Where two objects stand on one place**, the closer fit is taken and the other is
  named.
- **Nothing is copied on top of a mesh object.** In **Fill the gaps** a place is
  occupied, and no copy is made there, when any mesh object at all - hidden, in a
  move, of any number of vertices, a near miss scaled or nudged or cut - has the
  middle of the box round it within a quarter of the part's reach of where the
  part would stand. Only mesh objects are seen: a collection instance, a curve, a
  text or an empty standing in a place is not, and a copy is made on top of it. The
  report says how many places "had something standing there that is not a copy". **Use what's there** says how many places had nothing
  standing in them, and that **Fill the gaps** would copy the part there - but only
  when it would: where Fill the gaps would be turned down, as below, it gives that
  advice instead.
- **A wrong centre, About or Count is caught.** When copies of the part stand near
  the ring - within a ring's radius and a half of its middle, at its height - and
  on none of its places, the ring is round the wrong point, about the wrong axis or
  has the wrong Count, and copying between them would double the flower. **Fill the
  gaps** is turned down: "7 copies of 'Petal' stand near the ring but off its
  places: check the centre (3D cursor), About and Count. Nothing done." **Use
  what's there** takes what fits and says the same as a note. **Make copies** is
  never turned down. Copies a move plays already do not count.
- **A duplicate left on top of the part is a case of its own.** Shift+D, then a
  right-click to cancel the move, leaves a copy exactly where the part stands. That
  is no place of the ring, and no copy off it: "'Petal.001' stands exactly where
  'Petal' is - a duplicate left on top of it? Delete it, then Ring again."
  **Fill the gaps** is turned down with that, and nothing is done; **Use what's
  there** takes what fits and says it as a note; **Make copies** is not turned
  down.
- **The report names what was left out**, up to three, the nearest to the ring's
  places first: "'Leaf B1' is not a copy of 'Leaf A1'", "'Petal 4' stands in a place
  and is not a copy of 'Petal'", "'Stray' is a copy of 'Petal' that is not turned to
  its place", "'Far' is a copy of 'Petal' that stands off the ring" (only when it
  does), "'Twin' stands on the same place as 'Petal 3'". A half made with Ctrl+M of
  a petal that is not the same on both sides is none of those, and is told so:
  "'Petal.M5' is a mirror image of 'Petal' (not the same on both sides), so it is
  not a copy - it can ride along with Ride Along, which mirrors by itself". The
  copies a ring made earlier - every joint of them - are not left out. Ring looks at
  objects with as many vertices as a joint of the part, because those are the ones
  you may have meant, and at any object standing in a place. When nothing can be
  taken or made, Ring is turned down with those names and nothing is changed. What
  to do about it comes before the names: the panel's box shows nine lines of a
  report, and the end of a long one was cut.

What it makes, and the rest:

- **Count** includes the original: 6 is the part and five more.
- The places stand at the part's **Before** - not where it is standing now,
  so it may be showing its After - turned round the centre a share of a full
  turn each. **Round** is the 3D cursor or the world origin. **About** is the
  world's Z by default - a ring lying flat - or the world's X or Y, or the **3D
  Cursor's Z** for a ring that is tipped. Mind that last one: placing the cursor
  with Shift+right-click turns it to face the view, and a ring made about its Z
  stands facing the view too.
- Copies are named "Petal 2" and on, the lowest numbers free - free among the
  objects and among the parts of every rig, so a copy that takes the name of one
  deleted from the move is never mistaken for it - and put in the same
  collections. Objects picked up keep their names.
- **Linked copies** (the default) share the original's mesh, so editing one in
  edit mode edits them all. They share it until Build: Blender keeps a mesh's
  vertex groups with the mesh, and each part is bound by a group of its own,
  so Build gives every one a mesh of its own. Untick it and the copies have
  their own from the start. It has nothing to do with objects picked up.
- Nothing that bound or hung the original comes with a copy: not its Armature
  modifier, its bone's vertex group, its Follows mark, its parent, or keys on
  its own transform.
- Copies and objects picked up then ride along with the part, exactly as if you
  had pressed Ride Along on them. On a built move that is a Build.
- The part is ringed with the parts that follow it, below it - never with the
  ones it follows. Ring a finger's first joint and every finger comes whole,
  each curling from where it stands (see Copies of a whole finger); the copies
  are named per joint, "Seg1 2", "Seg2 2", "Seg3 2". Ring the blade of a fan that
  follows its hub, and the hub is not copied: every copy hangs from the hub as
  the blade does, so blades ringed round a spinning hub spin with it, and each
  flaps from its own place. Ring a joint in the middle of a finger and its copies
  hang from the joint above, which they are carried by.
- A second Ring over the first - or a bigger one - adds only the places that are
  missing: a place that already holds a rider of the part is skipped, and the
  report says how many. Ring 4 then Ring 8 adds the 4 missing. A ring with
  nothing to add is turned down.
- **Lead step**: set to anything but 0, the Leads are stepped from the original
  both ways round the ring (see Spread, Around a ring, both ways), so the blades
  open one after another, the two sides alike: -10 is 10 later for each step out
  from the original. The report counts any held at the limit. Only the places
  filled now are given a Lead; those of an earlier ring keep theirs. A copied
  finger has one Lead, its first joint's, so the fingers go one after another
  with their joints in step. Leave it at 0 and every copy moves with the
  original. The dialog keeps Use, Count, Round, About and Linked copies from the
  last Ring; Lead step always opens at 0.

It asks before it makes anything: a part that is not in the move, a rider, a
part with no Before, or a part dragged and not recorded on a built move are
each turned down in words, and nothing is left behind. So is a ring that cannot
be finished: if an object does not become a rider of the part it stands for, none
are kept. A part that follows another is not turned down.

### Spread: Leads and Delays in one go

*When:* a ring of riders should open one after another, a finger's joints
should go one after the next, a row should topple in a wave - and you do not
want to type a number into every row.

*Recipe:* press **Spread...** beside **Ring...** in **COPIES** (Leads) or at the top
of **TIMING** (Delays), pick an **Order**, pick **By**, set the values, **OK**.

**By** says how the values are given:

- **Step** (the default): a **Start** and a **Step**. Every part takes a place in
  the order, and gets Start + Step x its place, counting from 0. The default is a
  Start of 0 and a Step of **-10** for Leads, **0.1** for Delays - sized down
  when the last place would run past 40 of the 50 a Lead can be (or 0.9 of the
  0.99 a Delay can be), because a wave that is held at the limit stops dead
  there: twelve spikes one way round get -3, both ways -6, eight petals both ways
  keep -10. For Leads **Around a ring** opens with **Both ways** on. The Step
  follows the dialog while you have not typed one: untick **Both ways**, or change
  the **Order**, **Axis**, **Seed**, **By** or **Only the selected**, and the field
  reads the Step that fits now, before you press OK (twelve spikes: -6.00, and -3.00
  with Both ways unticked). A Step you type is kept as you typed it, whatever you
  change after, and what it holds at the limit is still counted. The dialog does
  not remember **Both ways** or **Only the selected** from the last time. Below 0 each
  rider waits more than the one before it, above 0 each goes earlier; for Delays
  each waits that much longer. It is a *step*, so adding a petal gives it the next
  value and leaves the rest as they were - **+10 each** is +10, +20, +30 whether
  there are four petals or forty.
- **Range**: a **First** and a **Last**, and the parts between are spread evenly
  from one to the other, however many there are. Handy when it is the last that
  matters: the last petal opens at -40, and whatever is between is shared out.

Parts the order cannot tell apart share a place, so they get the same value:

| Order | The part comes later the... | Parts that share a place |
|---|---|---|
| **Around a ring** | further round the ring it stands from the start, one way round. **Both ways** folds it in half, so the two sides of the ring match: the parts either side of the start go together | the two sides of the ring, with **Both ways** |
| **By distance** | further it is from the start: a ripple | parts the same distance away |
| **Along an axis** | further along world X, Y or Z: dominoes, a wave across a grid | parts at the same place along it |
| **Down a chain** | further down a **Follows** chain it hangs: a finger or a tentacle (Delays only: refused for Leads, riders have no Follows chain of their own) | joints at the same depth - the branches of a tree |
| **Random** | no order - the same every time for the same **Seed**. The places are dealt out, none shared | none |

"The same" is to within a ten-thousandth of how far the parts run, so the two
sides of a ring, a hair apart from rounding, are one place.

Eight petals round a flower, **Step** -10, **Around a ring**, **Both ways**:
the leader is place 0 and plays at 0 as it always does; the riders start at place
1 and get -10, -20, -30, -40, -30, -20, -10 - the pair next to the leader go
together, and the petal opposite it is the last.

- Leads are whole numbers held to -50 to 50, Delays held to 0 to 0.99; if any
  were held the report says how many ("3 held at the limit").
- Leads belong to riders. Each leader's riders are put in order among
  themselves, so two rings with a leader each both get the whole range. The
  start is the leader, which is place 0, so a rider's Lead is Start + Step x its
  place with the first rider at place 1. A copied finger has one Lead, its first
  joint's, so that is what is spread and counted - one for a whole finger - and
  selecting any joint of a copy selects the copy. **Down a chain** is listed for
  Leads, and refused when you press OK: riders have no Follows chain of their own,
  so there is none to spread down.
- Delays belong to the parts in the **TIMING** list. **Around a ring** and **By
  distance** are measured from the active part (or the first one), which is place
  0 and gets Start. **Along an axis** the part lowest along it is place 0; **down
  a chain** the joints at the top are; at **random** no part is, because the places
  are dealt out.
- **All** of them, by default, whatever is selected: Ring leaves its own copies
  selected and Curl its first joint, and a spread that went only by that left the
  rest of a flower or a tentacle as it was. Tick **Only the selected** to spread
  just the parts selected now.
- Parts are placed by their pivot at Before - a rider's is its leader's,
  carried over to where it stands. Where every pivot is the same point, as with
  the blades of a fan all turning about its hub, the middle of each part is
  used instead.
- Round a ring: the ring is wherever the parts lie - its plane is the best
  fit through them, so a tipped ring works - and a start that sits on its
  middle is measured from the first part instead. Fewer than three parts, or
  all in a line, and it is the world's Z.
- Written once for all of them, and a built move plays the new values at once.
  No Build.

### Followers: parts that hang from parts

A finger is three segments, each turning at its own knuckle, each carried by
the one before. Put them in one move and open **CHAINS**: beside every part
is a dropdown of the move's other parts, the one it follows. Pick the first
segment for the second,
and the second for the third - or select the segments and press **Make
Chain**, below. A follower goes wherever the part it follows
takes it, and does its own move on top.

Give each segment its knuckle as its **Pivot** (3D cursor on the joint,
**Cursor**), so each one turns where a finger bends. Then pose and record as
usual. Every recorded pose lands exactly where it was put; in between, each
joint turns about its own knuckle while the joint before carries it, so the
finger curls instead of its pieces sliding apart. **TIMING** still gives each
segment a delay of its own - the tip can wait for the base.

A follower's object hangs from the object it follows, before the first
Build and after it, so dragging the first segment brings the others along
on screen. Leave a follower where it was carried and it keeps its own joint
as it was and rides along; drag it from there to bend its own joint. A
follower added to a built move with no After of its own rides along with
what it follows - the eye on After shows it carried. The bones play the
move; the objects hanging from one another only keep the dragging honest.
A file built with 0.14.0 shows "Build to put it into effect" under
**CHAINS**: press **Build** once, so the objects hang from one another.
Changing **Follows** on a built move waits for **Build**, which says so in
red. A pick that cannot be - the part itself, a rider, a loop - is turned
down with the reason, and the choice it had stays. Objects already parented
to one another in the file - a finger modelled joint by joint - follow the
same way without being asked, by **New Move** or **Add To This Group**, and
are hung from their old parents again if the move is removed.

A follower goes where it is carried, so its path is not curved: curve the
part it follows instead, and a part with a curved path straightens it
before it follows.

### Copies of a whole finger

Four fingers, and only the first one recorded. Set it up as above - the
second segment follows the first, the third the second, each turning on its
knuckle - record its curl and Build. Then select every segment of the other
fingers, in any order, as many fingers as you like, and last any segment of
the recorded finger, so it is the active object. Press **Ride Along With
'...'**: the other fingers curl with it, every one from where it stands.

Each copy is matched to the recorded finger joint for joint, by where its
pieces stand and which way they face - names and the order you clicked in
do not matter. Its first segment rides along with the first, its second
with the second, hanging from its own first, and so on. Every joint bends
as the recorded one does, about its own knuckle, carried by the joints
before it. A copy can stand anywhere and face any way; one mirrored with
**Ctrl+M** curls the mirror way by itself.

A copied finger is one row under **Riding along**, with **+2** for the
joints that come with it. Its **Lead** sends the whole finger ahead or
behind, its joints in step - fingers at 0, -10, -20 and -30 close one after
another. Its **Mirror** mirrors every joint, and its **x** takes the whole
finger out. A joint added later finds the copy it belongs to. An object
that copies no more than one joint rides along with the part you clicked,
as a rider always has.

A follower can lead a rider of its own too: a second claw riding along with
the first hangs from the same arm, and swings with it. And a part that
leads riders can be given a part to follow; its riders hang from that part
too, from the next Build.

### Make Chain: Follows down a line in one click

*When:* a finger, a tentacle or a spine - parts end to end - and choosing
each one's **Follows** by hand is the slow part.

*Recipe:* select the parts, with the one the chain starts from the active
object, and press **Make Chain** at the top of the **CHAINS** section.

From the first, each next part is found by how joints are built: a joint sits
at the far end of the part before it. So of the parts not in the chain yet, the
next is one whose pivot touches the mesh of the part the chain has got to - within
a twentieth of how big that part is across - and of those, the one whose pivot is
farthest from that part's own pivot. A leaf folded in pleats, which puts the third
segment's pivot back by the first's, chains in the order it is built, not by which
pivot is nearest. Where nothing touches - gaps between the parts, or pivots left
in the middle of them - it is the nearest pivot at Before. Each is set to follow
the one before. It goes
through the same choice as the dropdowns, so a rider, a curved part and a loop
are turned down with their reason, and the chain stops there, keeping the
links already made. A part that leads riders may be chained: its riders hang
from what it hangs from.

It replaces the links the chosen parts already have to one another, so a chain
made from the wrong end is made again from the right one, and the report says
which old links it replaced. A part the chain starts from may follow something
that is not chosen - a finger on a palm - and keeps that. A chain refused at
its first link changes nothing; one that stops part way - at a rider in the
selection - leaves the parts it did not reach with the links they had, and
says it stopped. The report names the order: "Chain: Seg1 > Seg2 > Seg3 > Seg4". On a loose move the objects hang from one another at once; on a
built one the red note waits for Build, like any **Follows** change.

Copies of a whole finger ride joint for joint only while the finger they copy
is the chain they were made against. A new chain that changes what a copied
part follows says how many copied joints stop riding joint for joint. Those
copies are riders already, so Ride Along has nothing new to take: take them out
with their **x** under **Riding along**, then press **Ride Along** on them again
to take the new chain.

### Curl: bend one joint and the whole chain bends

*When:* every joint of a finger or tentacle bends the same way and you would
rather pose one than all of them.

*Recipe:* **Make Chain** if it is not a chain yet. Set the pivots on the
joints. Turn the first segment about its joint by hand, then press **Curl**
(beside **Make Chain**) with it active. **Record After**, or a Step, to keep
it.

The bend is the first segment's turn from its Before, about its own pivot, in
its own axes; where its pivot went is not part of it. It is repeated on every
part that follows it, directly or not, branches included, each about its own
pivot in its own axes and carried by the part before it, so the joints stay
together. Each joint keeps **Each next joint x** of the bend of the one before
it, so the bend is the factor to the power of how far below the root a joint
is. The default is 1: every joint bends as much as the first. At 0.5 a 20
degree bend runs 20, 10, 5, 2.5, 1.25 down the root and four followers, so the
tip curls least. The factor is in the Adjust Last Operation panel, bottom left
of the viewport, right after pressing Curl.

Curl works from rest. Joints already showing a pose have their own bend on top
of where they stand, and Record would then not read what Curl made. So it
refuses while any bone of the chain is showing one - the eye on After, or Play
above 0 - and says to drag Play to 0 (and to Build first, if the sliders are
paused). Record After or Step then reads exactly the curled pose, built or not.
It also refuses when nothing follows the part, when the part rides along, and
when the part has not been turned.

Curl puts every part below the root where its bend says, replacing whatever
bend it had. A part whose object has been deleted leaves its move at the button
press, and the report says so; the parts that followed it follow nothing, and stay
where they stand. One that riders copy or hang from stays, as "Name (deleted)": it
is left out of the bend if it is at the end of the chain, and the report says so;
if parts hang from it, Curl is turned down, saying which, and nothing is moved.
Copies of the finger ride along with it once a Build has copied the new path onto
them, so after **Record After** press **Build**; the report says so when there are
copies.

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

Open **PATH** and press **Step in between**. A **Step 1** row appears between
Before and After with a Record of its own, and from there it is the same gesture
as the other two:

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

Open **TIMING**. Every part has a **Delay**, as a fraction of the control's
travel. Delay 0.2 means that part waits until the control is a fifth of the
way across before it starts, and then runs to the end. That is what stops a
machine reading as one rubber object: the parts leave in order, and overlap.
A delay, like an ease or a speed, takes effect as soon as it is changed.
Riders are not listed here; their **Lead** does the same job. **Spread...** at
the top of this section fills all the Delays in at once - see Spread.

A combined control has the same box per member.

### How it gets there

The four **Ease** buttons at the top of **PATH** shape the whole move: even
speed, smooth, slow start, slow stop. The one in use is lit. It sits on top of whatever path was recorded, so a hand-shaped path with
Smooth on it eases into and out of your own curve.

For exact control of each stretch use the speeds instead, with Ease left on
Even speed. The two stack, the ease first.

### Going round things: curved paths

From A to B a part goes in a straight line, which is no use when something
is in the way. Select it and press **Curve the Path** (in **PATH**): a curve
appears along the path it has - through its steps, if it has any - with a point in the
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

**Paths**, at the foot of **PATH**, draws a line through where every part of
the move goes, Before to After, through the middle of each part: steps, pivots,
curves, mirrors and all. It is drawn again at every Build, can't be clicked or
rendered, and goes when Paths is pressed again.

## Everything else on the card

- **Record** either row saves where the parts are standing at that moment. The
  eye icon beside it puts the model back into that pose so you can check it.
- **Parts**, in **PARTS & PIVOT**, with how many are selected on its button,
  replaces the move's bones with whatever is selected now, keeping the timing
  of the ones that stay.
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
- **The box at the top of the panel** appears when something would make the rig
  play the wrong move. Auto Keying on, which leaves a keyframe behind with every
  drag. Parts with keys of their own on their location, rotation or scale: **Lift
  Those Keyframes** takes them off (Build does too), only the keys the part itself
  plays. And parts moved by an NLA strip or a driver of their own. Those two are
  your work, so nothing lifts them: the box says to mute the strip's track, or
  delete the strip, in the NLA editor, or to remove the driver in the Drivers
  editor, and then to Build.
  Build names them as well, and is a warning, not a success, until they are gone.
- **The REPORT** box, under the buttons, says what the last button did, and what to
  do next. It is open until you fold it with its arrow. A warning - a button that
  turned itself down, or a Build that is not a success - gets a warning icon and a
  red title, so that it is seen even with the box folded. The box shows nine lines.
  A longer report ends with "…" and a last line, "(the full report is in the Info
  editor)", where all of it is.

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

A copied finger's joints are riders like any other, each with a bone turned
from its own leader's. The bone of each hangs from the bone of the joint
before it in the same copy, and plays its leader's own channels - which are
that joint's move against the joint before it - so the copy bends joint by
joint, carried as the recorded finger is. A rider of a follower with no
copy of what its leader follows hangs from that very part. Every joint of a
copy is shifted in time by one amount, its first joint's Lead, so the copy
keeps the recorded finger's timing between its joints.

Each bound object is moved by its own bone and nothing else. Blender keeps
vertex groups on the mesh, not the object, so an object sharing its mesh
with another is given a mesh of its own when it is bound; and the group a
copy of a bound part brings for the other part's bone is taken off - when
it is bound, and at every Build.

A follower's bone hangs from the bone of the part it follows, so it plays its
own path in its parent's space. Choosing a part to follow on a built move
keeps every recorded pose: each key is worked out again as what the parent
does at that key, undone, then the pose that was there - and parents are
redone before the parts that hang from them, so each is worked against its
parent's new keys. A part that never follows hangs from the root.

Top of the stack matters: whatever constraints the bone already had still run
afterwards, so a hand-built rig can be given a control without being taken
apart. The first move on a bone replaces its pose, any later move composes on
top, so two moves can share a bone of a hand-built rig. An object is bound to one
bone, so it is in one move: for a second motion, add a Step.

The Action constraint is also why an arbitrary path is possible at all. A
plain driver can only interpolate a straight line between two numbers; an
action can hold any curve, and it can be edited in the graph editor like any
other animation.

The viewport handle is a non-deforming bone with a Limit Location constraint
for its rail, which drives the move's custom property. So the property stays
the one number everything reads, whichever way it is written.

The armature is seated on the middle of the parts it drives, so Blender's
relationship lines run to the machine rather than to the world centre, and the
root bone sits with it. A rig that moves itself (keys, a driver or an NLA strip on its
own transform) is left where it is. The bones move back by exactly what the object
gains, so nothing on screen shifts.

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

Curl keeps each part's relation to the one it follows and adds its own bend.
Part F, following Q, is put at

    W_F = (W_Q B_Q^-1) D_F B_F

where B is the part's Before, W_Q B_Q^-1 is how far Q has been carried, and
D_F is the turn about F's pivot in the world at Before, about F's own axes -
its Before frame without its scale, so a part stretched in one direction is
turned rigidly and not sheared. The turn is the root's quaternion raised to
the power factor^k for a part k below it, taken the short way round.

Spread works out an angle round a ring from the best-fit plane of the parts'
spots and writes the values with the drivers left alone, then refreshes them
once. By Range each part's share of the way is its angle, distance, place or
depth over the biggest; by Step it is its place in the order, where parts the
order cannot tell apart share one. Ring copies the object - every joint of it,
for a chain - takes off what the original was bound by, sets each copy on the
original's Before turned about the axis, and presses Ride Along on them, told
which copy is which joint. Use what's there looks instead at the meshes in the
scene with as many vertices as a joint has: one stands in a place when every
vertex of one is within a fiftieth of the part's size of a vertex of the other, both
ways round (a k-d tree, after a vertex-by-vertex pass that most copies already
satisfy), with the joint's own vertices put there. The best fit takes each place, a
place is taken only with all its joints, and anything with a mesh whose middle is
near a place stands in it. An object not on its frame is stood on it with its mesh
moved the other way (`reframe`) only if nothing in it reads its frame
(`reframe_blocker`), the evaluated look is compared before and after (`look_of`), and
a difference puts it back by swapping the old mesh in again; then the same Ride Along.

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
- **A copy of a rigged part was moved by the original's bone as well**
  (0.16.0). Shift+D on a part that is already bound copies its binding with
  it: the original's vertex group, at full weight. Bound to a bone of its
  own as well, the copy was moved by both bones, half and half - which looks
  right only while the two do the same thing. Four cubes riding round a
  curve, three of them copied from the second: mirror the second across Z
  and the other three ran straight from A to B. The copied group is taken
  off when the copy is bound now, and every Build heals a file made before.
- **Linked copies moved each other** (0.16.0). Alt+D copies share one mesh,
  and Blender keeps vertex groups on the mesh, so binding the copy gave the
  original the copy's group too: each was moved half by the other's bone,
  the leader included. A bound object gets a mesh of its own now. So did two
  Alt+D copies of one part put in a move together and bound in one Build: each
  was pulled by both bones, and neither landed where it was recorded.
- **A group left from a deleted rig pulled a part once a part of its name
  joined** (0.16.0). Copied from a part of an old rig, a segment kept that
  part's group under a name no bone had - until an object of that name rode
  along, and its bone was made. The first finger was then pulled by the
  second finger's bones as well. Bindings are healed after every bone of a
  Build is made.
- **Ride Along with several objects at once could crash Blender** (0.16.0).
  It read the leader back after adding the new riders to the list of parts,
  and adding can move that list in memory. Six at once crashed it in five
  runs out of eight. In the runs that did not crash, the last rider of a move
  from its ninth part on was left riding with nobody: "rides with a part that
  is no longer in its move". Everything is worked out before anything is added
  now.

- **Leads came out scrambled for blades turning about a far-off hub.** Blades whose
  pivots are all one point - the hub - are ordered by where they stand instead,
  but "one point" was an absolute 0.00001: far from the world's origin the pivots
  carried over to each blade differ by float rounding that is larger than that, and
  the rounding was put in order. It is measured against how far apart the blades
  stand now.
- **Spread round an arc, or a few picked out of a ring, was lopsided.** The middle
  of the ring was the average of the parts, which is the middle of a full ring only:
  the blades of a half-open fan or a wing came out in the wrong order, and the
  third of three picked from a ring before the second. The ring is a circle fitted
  to the parts now - the hub the Leads are measured from left out of it.
- **A ring made again after its copies were deleted never bound the new copies.**
  The deleted copies' parts stayed in the move (they are taken out of it at the next
  button now), and a new copy that took the name of one was taken for it: not bound,
  put back where the old one stood, and the report said it rode along. Copies are
  numbered past every name in use, in the objects and in the parts of every rig, and
  a ring that cannot be finished takes itself back.
- **Make Chain could not be done again from the other end.** The old links, which
  closed a loop with the new ones, were the reason it was refused. It replaces the
  links among the chosen parts, and says which.
- **Curl failed with a Python error when an object of the chain was gone.** A lost
  tip is left out now, and a lost part with parts hanging from it is turned down
  with its name.
- **A Spread after a Ring or a Curl reached only what that tool had left
  selected.** The first ring of a flower was never given its Leads, and a tentacle
  its Delays, and the report said it had worked. A spread takes every rider or part
  unless **Only the selected** is ticked.
- **Ring tipped toward the camera after the usual Shift+right-click.** That puts the
  cursor on the spot and turns it to face the view, and a ring about the cursor's Z
  stood facing the view too. About the world's Z is the default now.
- **A fan blade that follows its hub could not be ringed**, and the way out the
  refusal gave stacked hubs on the centre. A part is ringed with the parts below it,
  never above, and each copy hangs from what the part hangs from.
- **A second Ring stacked copies on top of the first's.** A place that already
  holds a copy is skipped; the report says how many, and the Leads of the earlier
  copies are left alone.
- **Files bound before 0.16 with Alt+D copies stayed broken.** Already healed by every
  Build in this version - the check for parts moved by another part's bone as well
  covers copies that share one mesh - and now tested from the state 0.15 left.

- **Make Chain that stopped at a rider dropped the old links of the parts it had not
  reached, and called them replaced.** Every link among the chosen parts is cleared
  to make room for the new chain, and was put back only when the chain was refused at
  its first link: stopped part way, the tip of a finger lost its Follows and played a
  path of its own. The parts the chain did not reach keep their links.
- **Make Chain's advice for copies that stop riding joint for joint did not work.**
  It said to Ride Along again, but the copies are riders already, so Ride Along
  turned them down. It says to take them out with their x first.
- **Mirror on a copied finger zigzagged when a segment was rolled about its own
  length.** Each joint mirrored across its own axis, and a cube rolled 90 degrees
  looks the same with its axes turned: the rolled joint's curl was not mirrored while
  the others' were. Every joint mirrors across the first joint's plane now, carried
  into its own axes.

- **Make Chain chained a leaf folded in pleats in the wrong order.** It took the
  nearest pivot, and a leaf shut in pleats puts the third segment's pivot back by the
  first's: Leaf 1 > Leaf 3 > Leaf 2. A joint is built at the far end of the part before
  it, so the next part is now the one whose pivot touches the last part's mesh and is
  farthest from its own pivot; the nearest pivot is only the fallback.
- **Reports said "1 copies", "1 joints" and "part(s)".** Ring, Make Chain, Curl and
  Spread count in the right number now: "1 copy ... rides along", "2 places ... were
  skipped", "1 part below ... bends".

- **Ring made a copy on top of every petal that was modelled already.** A flower with
  its eight petals modelled got eight more on top, and the six inner petals the same,
  to be deleted by hand. Ring has a **Use** choice now: **Fill the gaps**, the default,
  copies only where nothing stands, and **Use what's there** makes nothing.
- **Spread by First and Last changed every value when a petal was added.** Round a
  ring, the last petal always got the Last, so a ninth petal moved the other eight.
  **By Step** gives a part the value of its place in the order, and nothing else moves.

- **Ring took up animated, linked and unsafe objects, and copied onto near misses.**
  0.18.0 adopted a petal with keys of its own (Build then lifted them, and a
  re-framed one jumped on the next frame change), objects linked from a library (the
  change was lost on save), objects that cannot be selected (Ride Along then
  failed), and re-framed objects whose look depends on their frame - a bend, a
  hook, a constraint, a Child Of - or whose children hang from vertices, saying
  "nothing shifted". It also made a copy on top of a petal that was a hair off
  (scaled 6%, a vertex nudged, an extra cut), hidden or already in a move. Now only
  what is provably safe is taken up or re-framed, the result is checked and put
  back exactly if it differs, and a place with anything standing in it is not
  copied into.
- **Fill the gaps stacked copies on mirrored halves and unturned cubes.** A Ctrl+M
  half of a flower, or the teeth of a gear moved with G, have the very points of the
  copy that belongs there with the vertices numbered another way, and were not
  recognised. Objects are matched as sets of points now.
- **Fill the gaps doubled a flower when the 3D cursor or the Count was off.** The
  copies standing off the ring were reported and then copied between. Fill is turned
  down when copies of the part stand near the ring and on none of its places.
- **Spread's first run on a ring of more than five riders stopped the wave.** The
  default step of -10 held the last riders at -50 together. The default is sized to
  the number of places now, and Both ways opens on for Leads around a ring.
- **Ring said "none were kept" when every place had only part of a chain.** It
  names the real reason now, and lists what was left out, nearest first.

- **Blender 4.4 was named as enough, and every Build failed there with a Python
  error.** Each part is played through the Action constraint's Replace mode,
  which Blender added in 4.5. CopyThat asks for Blender 4.5 or newer now, and
  Blender will not install it on an older one.
- **On Blender 4.5 and 5.0 a file healed by Build still looked broken.** A copy
  bound before 0.16, moved by two bones, was given back its own group, but those
  versions did not redraw it, so it went on being pulled half by the other bone
  until the file was opened again. It is redrawn now.
- **On Blender 4.5 every key was found twice.** The red box that warns about
  stray keys said "2 key track(s) on this rig's bones" for a single stray key,
  and "6" for a bone keyed on three channels. Lift Those Keyframes and Build
  reported the right numbers, but Blender's console printed "F-Curve not found"
  once for every track they took off. Each track is counted once now. Blender
  5.0 and newer never did it.

- **At the sidebar's usual width every row under Riding along read the same.**
  Ring's copies are named alike but for the number at the end, and the name was
  cut at both ends: seven rows of "…ter Lead…". The name is now cut from the
  front only as far as it has to be, so the number shows, and the header keeps
  its count: "Riding along (7)", not "Riding alon…".

- **A finished model that was moved as a whole jumped back on the next Build.**
  Select everything and move it five metres, or parent the rig to a hand and
  move the hand, and the next Build put every part back where the model had
  stood. Set Pivot, Ride Along, Ring and Mirror refused with "has been moved and
  not recorded", and doing as that said - Record After - baked the move into the
  animation. The rig now remembers where it stood, and carries what it recorded
  along when it has been moved, however it was moved.
- **Set Origin, or Apply Scale, on a built part broke its move.** Nothing moved on
  screen, but the next Build left the part up to a metre off, and Set Pivot and the
  rest refused with "has been moved and not recorded", which was not true: it had
  been given a new origin, not dragged. A part keeps where three of its vertices
  were; when the object is off its place but they are not, it was only framed
  differently, and it is put back on its frame with the mesh moved the other way.
  If that cannot be done safely - a constraint, a modifier that reads the frame -
  the button says so by name and changes nothing.
- **Renaming a built part (F2) broke its move.** The panel called it "not in this
  rig", Record saved no part at all, Build took a drag for the rest, Ring turned it
  down, and taking the move out left the binding behind. The move found its parts by
  their names. It finds them by their objects now: the part takes the new name, and
  so does everything that mentioned the old one.
- **Copying a whole finished model broke the original.** Select the rig and its parts,
  Shift+D, move the copy and Build it, and the original played several metres from its
  lid. The copy's parts still named the original's objects, and both rigs played one
  Action, which the copy's Build rewrote. The copy's parts are its own objects now, and
  it plays a path of its own.
- **A second move on an object took it away from the first.** Select the lid of a built
  chest, press New Move, lift it, Record, Build: the lid lost both of its groups and was
  moved by neither move, and Build said some parts "copied from another" had been put
  right, which was not so. An object is in one move now: New Move, Add To This Group and
  Ride Along leave out what is in one, say so, and refuse if nothing is left. Build
  reports an object that a file already has in two moves, and leaves it alone.
- **A copy of a built part, added to its move, was drawn swung about the original's
  hinge.** Shift+D a built door, move the copy, Add To This Group, the eye beside After:
  the copy was drawn seven metres from where it stands, and an After posed by that eye
  played somewhere else. An object that joins a move is taken off what bound it to
  another part first, so it stands still where it is.
- **A handle parented to a lid stayed behind, and nothing said so.** Ctrl+P a handle to
  a lid, select only the lid, New Move, pose, Record, Build: at the end the handle was
  two metres from where it should be. It is not in the move, so it is left where it is;
  that is not changed, but New Move, Add To This Group and Build now name it and say
  what to do. An empty or a light cannot be in a move, and the report says that.

- **Ring stopped with a Python error when the petals it stood on a new frame
  shared one mesh.** Petals made with Alt+D share a mesh, and applying the
  rotation of the leader alone puts each of the other seven on a frame of its own,
  so Ring re-frames all seven. The first one settled took the shared mesh away, and
  the next one asked it a question: "StructRNA of type Mesh has been removed". The
  riders were left bound with a Lead of 0, and there was no step to undo. The old
  mesh now goes once, after every petal is settled, and only if nothing else uses
  it. And if anything at all goes wrong once the riders are made, Ring takes them
  out again, puts every petal back as it found it, and says "Ring could not be
  finished: ... Nothing was changed."
- **Build took the animation of other objects away.** A part keyed on its own
  transform has those keys lifted when it is built, and they were taken out of the
  action the part plays. Where another object plays the same action - an Alt+D twin,
  or a lamp with a slot of its own in it - that object lost its animation too, and
  the report counted its tracks as the part's. Now only the keys of the slot the part
  itself plays are looked at, lifted and counted, and an action another object plays
  too is copied for the part first, so the keys come out of the copy: the others keep
  theirs exactly. **Lift Those Keyframes** does the same.
- **A bee on a petal that Ring re-framed flew off.** Ring stands a petal on its frame
  and holds what hangs from it where it is by rewriting the child's own transform,
  which the child's own keys, drivers or NLA strips rewrite again on the next
  frame, from the petal's new frame: a keyed bee was half a unit off by frame 10. A
  petal with a child like that is now left out, and named: "'Petal 4' cannot be
  re-framed safely (has a child with keys or drivers of its own ('Bee'))". A child
  with nothing of its own is held where it is, as before.
- **A part moved by an NLA strip or a driver played the wrong move, and nothing said
  so.** The warning looked only at keys in the part's own action, so a part whose
  animation had been pushed down into the NLA, or that had a driver on its location,
  rotation or scale, was not named anywhere, and played the wrong move by up to
  two units. The box at the top of the panel, and Build, now name those parts and
  say what to do: "'Gear' is moved by an NLA strip of its own, which fights the rig:
  in the NLA editor, mute its track (the checkbox on the track) or delete the strip,
  then Build", or "... by a driver on its transform: remove it in the Drivers
  editor, then Build". They are your work, so Lift Those Keyframes does not touch
  them, and Build is a warning, not a success, until they are gone. A muted track and
  a muted driver play nothing, and are not named. A muted strip is not played either,
  but Blender still sets everything it works to its default on every frame, so it is
  named like any other.
- **A duplicate left on top of the part was blamed on the centre and the Count.**
  Shift+D, then a right-click, leaves a copy exactly on the part. Ring looked at the
  places round the ring but not the part's own, so Fill the gaps refused with "1
  copy of 'Petal' stands near the ring but off its places: check the centre (3D
  cursor) and Count" - wrong, and with no name - and Use what's there called it "a
  copy that stands off the ring". A copy standing where the part does now has a
  sentence of its own that names it and says what to do, in Fill the gaps and in Use
  what's there. Use what's there no longer says "Fill the gaps would copy the part
  there" when Fill the gaps would be turned down.
- **Spread kept a Step sized for the settings the dialog opened with.** The Step is
  sized to fit when the dialog opens, and changing **Both ways**, **Order**,
  **Axis**, **Seed**, **By** or **Only the selected** afterwards kept it, so the
  riders were held at the limit: twelve spikes one way round got -6 instead of -3,
  dominoes along an axis -10 instead of -5, and the end of the wave stopped dead. The
  Step now follows those settings, and the dialog shows the new one before you press
  OK, until you type a Step of your own, which is kept. The dialog also stopped
  remembering **Both ways** and **Only the selected** from the last time: the smart
  default of Both ways worked only the first time, and an **Only the selected** left
  on after a spread of Delays reached only the riders Ring had left selected, which
  is what 0.17 had stopped it doing.
- **Ring's Lead step was remembered from the last Ring.** Blender opens a dialog
  with what it was last used with, and the Lead step was not marked otherwise: after
  the outer petals' step of 9, the Ring dialog of the leaf opened with 9 as well,
  and, left alone, the second leaf opened ahead of the first. The Lead step always
  opens at 0 now. Use, Count, Round, About and Linked copies are still remembered.
- **A second Ring of a finger listed its own earlier copies as left out, and hid a
  real stray behind them.** "'Seg2 2' is already part of a move; 'Seg2 3' ...; and 3
  more": only the first joint of each copy was known to be the ring's own, so the
  inner joints took up the three names the report gives, and an object that really
  was in the way was one of the "more". Every joint of the copies the part already
  has is the ring's own now.
- **Ride Along said "3 copies of 'Palm' ride along" when the palm was never
  copied.** The sentence named the root of the Follows chain. It names the first
  joint any of the copies has - the finger's, here.
- **Copies off the ring were blamed on the centre and the Count alone.** A ring about
  the wrong axis shows the same picture, so the advice is "check the centre (3D
  cursor), About and Count".
- **Use what's there promised "Fill the gaps would copy the part there" when Fill
  the gaps would have been turned down** for copies standing off the ring. It says
  so only when Fill the gaps would copy.
- **The advice at the end of a long report never showed.** The panel's box shows
  nine lines and cut the rest without a sign, so the advice that ended a long Ring
  report was lost. In a refused Ring the advice now comes before the names of what
  was left out, and a report the box has to cut ends with "…" and "(the full report
  is in the Info editor)".
- **A half made with Ctrl+M that is not the same on both sides was "a copy that is
  not turned to its place".** It is a mirror image, and turning it would not help:
  "is a mirror image of 'Petal' (not the same on both sides), so it is not a copy -
  it can ride along with Ride Along, which mirrors by itself".

- **Deleting a part could close Blender.** About half a second after X, a timer lets
  go of the deleted part's object. It removed the object from the very list it was
  looping over, and a loop over a list that loses a member goes on to read the one it
  has just lost: usually nothing showed, sometimes Blender crashed, and the rigs after
  the one that lost an object were skipped. The rigs are collected first and the
  objects let go of after.
- **A new object that took a deleted part's name was taken for that part.** Two cubes
  are a move, built; delete one and add a cube, and Blender names it after the deleted
  one. The panel said it was already in the rig, New Move and Add To This Group
  refused it ("already in Move 1"), and Build moved it onto the deleted cube's Before,
  unbound. A part whose object has been deleted and let go of is marked gone and
  stands for nothing from then on, whatever has its name.
- **A deleted part stayed in its move for good.** Ring said "'Hand' has no Before
  recorded yet" of a hand that was deleted, the reports counted it, and what followed
  it was left hung from nothing. The next button takes the part out of its move - its
  constraints, drivers and curves, and at the next Build its bone. What followed it
  follows nothing and stays where it stands, and the report says so: "'Cube.001' was
  deleted, so it was taken out of 'Move 1'." A deleted part that riders copy, or that
  riders hang from (the middle joint of a copied finger), stays for them, as "Petal
  (deleted)", since its bone plays their path; it goes when its last rider does. A
  follower hung from a leader that was deleted does not jump when the leader is freed.
- **A big scene slowed Blender, and a deleted part made it crawl.** In a file with a
  rig of fifty parts and a thousand other meshes in sixty collections, every update
  ran a check that looked through the collections of the whole file for every part,
  and the panel took three times as long as in 0.18.3. With one part deleted and not
  yet let go of, each update took about 150 ms and the panel about a second. The check
  asks an object how many users it has instead, and the scan for a renamed object asks
  its cheap questions first: an update takes under a millisecond, and the panel what
  it did in 0.18.3, with a part deleted too.
- **A copy of a whole model made with Alt+D was not independent of the original.**
  Alt+D links the Armature as well as the meshes, so building the copy, ringing its
  lid or setting a pivot edited the original's bones - the original lid ended up
  0.89 m off - and removing the copy's move took away the original's bones, its vertex
  group and its constraints. A rig that shares its Armature takes a copy of it for
  itself the first time a button is pressed on it, its pose, constraints and drivers
  with it; Remove makes a shared mesh the object's own before it takes the group off.
- **A copy of a whole model shared the original's path curves and path line.** They
  are objects of their own, and not selected with "the rig and its parts", so the
  copy's Build pinned the original's curve to its own ends, removing the copy deleted
  the original's curve (its path went straight at its next Build), and the copy's
  Build deleted the original's path line. The copy gets curves of its own, and lets go
  of a path line it shares.
- **Remove hung a part back on the wrong parent, or on none.** A lid modelled hanging
  from a body goes back to hanging from it, but the body was kept by name: Remove on a
  Shift+D copy of the chest hung the copy's lid on the original body, so moving that
  moved the copy's lid, and after the body was renamed it hung it on nothing and said
  "The rig is back to how it was". The body is kept by pointer, which follows a rename
  and, in a copied model, points at the copy's own. If it is gone, Remove says so:
  "'Lid' hung from 'Body', which is gone, so it was left standing free."
- **Build emptied an NLA strip that played the part's own keys.** A part whose
  animation had been stashed or pushed down, so that its action is also in a strip of
  its own NLA, had "3 stray keyframe track(s)" lifted - out of the strip too, which
  Build is never meant to touch. The part now takes a copy of the action to lift the
  keys from first, whether the strip is muted or not.
- **"Mute the NLA strip" did not make a part play its move.** A muted strip is not
  played, but Blender still sets everything it works to its default on every frame, so
  the coin sat at the origin at every frame - and the part was no longer named, so
  nothing said it was still wrong. A muted strip on a track that plays is named like
  any other, and the advice says what works: "in the NLA editor, mute its track (the
  checkbox on the track) or delete the strip, then Build".
- **After New Rig, every New Move started another rig.** Blender gives an operator the
  choices it was last used with, and New Rig is New Move with one choice made; it is
  not remembered now.
- **Ring blamed a deleted part on a missing Before.** It said "has no Before recorded
  yet" of a part below the one chosen that was deleted, or that was no mesh. Each has
  its own sentence: "'Hand' was deleted, so the chain cannot be ringed", "'Hand' is
  not a mesh, so it cannot be ringed", and the old one for a part that has none.

- **Set Origin, or Apply Scale, on a built part and then dragging it broke the move.**
  Give a built lid a new origin, or apply its scale, and drag it to a new After before
  pressing any button: Record said "moved by hand, read as a pose" and the next Build
  left the lid up to a metre off at rest, because the new origin and the drag were
  taken together for one big drag - an origin change is never meant to be recorded as
  one. A forearm in a chain was nearly half a metre off. A part with no bone yet -
  after New Move, or added with Add To This Group - moved by a whole part at its first
  Build, and the report said it had worked. A part now fits three of its vertices,
  picked to stand far apart, onto where they are now: what the mesh did is the drag,
  and only the frame is put back. The drag is kept and recorded as the pose it is.
- **A mesh edited after it was built was taken for a drag by Set Origin.** Nudge a
  vertex, or subdivide a built lid, in Edit Mode, give it a new origin and Build: the
  lid stood 0.82 m off at rest, "1 put back on its Before". A part kept the vertices
  it is told by from the day it was built. They are taken again whenever the part
  stands on its Before and they no longer fit - at the next button, and as soon as
  Edit Mode is left, also when the whole model has been moved since and no button has
  caught up with it yet.
- **Ctrl+A or Set Origin on the rig made the next button move the model.** Nothing
  moves on screen - Blender shifts the bones the other way - but the rig's new matrix
  was read as the whole model having moved, and everything it remembered was carried
  by it: the lid 1.2 to 1.5 m off at the next Build, Record, eye, Add To This Group or
  Lift, a robot arm's forearm five. (0.18.3 did not do this to the rig alone.) The rig
  now tells where the model stands by its Root bone, which Apply and Set Origin leave
  where it is (and, for Apply Scale on a rig that was itself scaled, by the bone's
  length as well); a file saved by 0.19.0 is caught up once the old way and then kept
  the new one.
- **A refused re-frame blamed the wrong thing, and blocked the cure.** Set Origin on a
  built forearm and a stray Auto Key on its hand: Lift Those Keyframes, Build and
  Record were all refused with a message about the forearm's origin that never
  mentioned the key. The refusal now names what stops it - "it has a child with keys
  or drivers of its own ('Hand')" - and for keys says to press Lift Those Keyframes,
  which takes the keys off first and puts the forearm back after.
- **Ctrl+A Scale on a built chain sheared the follower.** Two unevenly scaled boxes,
  chained and built, both scaled by Apply: Build said nothing had moved, but a forearm
  dragged 50 degrees and recorded turned 8 degrees on screen and came out sheared, and
  Curl 0.8 gave 83 degrees for the 81 it was asked for. Putting the parts back on
  their frames left each child hung by an inverse that no longer cancelled its
  parent's scale. Children are hung again the way Build hangs a follower.
- **A rig with keys on its own location lost its place at the next Build.** A car
  driving off with its model, keys at three frames, a coin added at frame 20: Build
  moved the rig onto the middle of its bones, the keys put it back on the next frame,
  and the whole model stood half a metre off at every frame - after Set Pivot, Ride
  Along, Mirror and the rest as well. A rig that moves itself (keys, a driver, an NLA
  strip) is left where it is.
- **A model carried a few hundred metres read as dragged.** Select everything and
  carry it 300 m with a turn: Set Pivot, Ride Along and Ring refused with "has been
  moved and not recorded", and Record wrote "moved by hand, read as a pose" for a lid
  nobody touched. A rig keyed along a 214 m path was refused even back near the
  origin. Blender keeps seven digits of a matrix, so what is carried far out is
  rounded, and that stays when the rig comes home. How much two places may differ now
  grows with the distance from the origin, and the rig remembers the farthest it was
  carried.
- **A rig animated from scale 0 ruined what the move remembered.** A button pressed on
  the frame where it is nothing squeezed every Before and After to a point, and the
  next Build at scale 1 left the lid nearly five metres off. A rig with no size is
  left alone, and Record and Build ask for a frame where it has one.
- **A rig switched off in the viewport was half changed by Build, Remove and Ring.**
  With Show in Viewports off (the screen icon) they stopped at "Cannot edit hidden
  object" half way: a first Build had taken the lid off its parent, Remove had left
  the bones and the handle's constraint, Ring left eight unbound copies. They now say
  it first, and change nothing: "Show 'CopyThat Rig' in the viewport first (the screen
  icon in the Outliner)".
- **Ring's copies were put in the wrong place under a stretched parent.** Ring(4) on a
  lid, the rig hung from an Empty scaled (1, 2, 1), turned and moved: after Build two
  of the petals stood 0.9 m off. A model stretched as a whole is sheared, and a shear
  is not a place a bone can stand; the riders' seats are worked out in the rig's own
  space now, for mirrored riders too.

- **Delete a part of a copy of a whole model (Shift+D or Alt+D) and press Build,
  Record or Remove on the copy:** the model it was copied from no longer loses
  that part's keys and stays at rest; the same the other way round.
- **Moving, lengthening, rolling or renaming the Root bone in Edit Mode is no
  longer taken for the whole model having moved:** the next Build or Record no
  longer throws every part off by that much.
- **A file made by 0.19.0:** Ctrl+A or Set Origin on the rig before pressing any
  CopyThat button no longer throws the parts off at the next Build, and Set
  Origin on a part whose old marks lie in a line (a grid of 4 by 4) is no longer
  read as the part being dragged. The file is settled when it opens.
- **A lid that hung from a body in a file made by 0.19.0 is hung back on that
  body by Remove even after the body was renamed.**
- **Geometry added to a built part stayed behind when the part moved.** A built
  lid; in Edit Mode a cube made with Shift+A, or a handle joined to it with
  Ctrl+J; Build. The lid swung open and the new vertices stayed where they were
  (1.96 m behind it at full share), and Build said nothing. Build now puts the
  vertices that are in no vertex group into the part's group, and says "'Lid'
  had new geometry; it moves with it now." A vertex that is in a group already -
  extruded or subdivided from a weighted one, or painted for another bone - is
  somebody's weight and is left alone.
- **A move named with 64 bytes or more broke Build half way.** A move renamed to
  92 letters, 32 accented letters or 22 CJK characters, then Build: "KeyError:
  the length of IDProperty names is limited to 63 characters", the parts bound
  and given bones and no slider to play them. Two moves named alike at 62 bytes
  did the same (the second slider is given a " 2"), and so did a combined
  control named with 70 characters. The slider's name is now cut to 56 bytes, on
  the edge of a letter; a file saved after a failed Build is put right by its
  next Build.
- **A move named with accented letters still failed to build on Blender 4.5.**
  The handle's bone ("<name> handle") was cut through a letter by 4.5, and its
  name could not be read ("UnicodeDecodeError ... position 62"). It is cut on
  the edge of a letter now.
- **Remove, Make Chain and the eye wrecked a model on the frame where its rig is
  scaled to nothing.** A chest whose rig (or an Empty above it) grows in from
  scale 0: Remove on frame 1 left the lid and latch at scale 0 with their places
  lost and said "The rig is back to how it was"; Make Chain gave the follower a
  scale of 0 and a parent inverse of 3e8, so after the next Build the lid
  travelled 4.8 m instead of 0.9; the eye scaled the parts to nothing (the next
  Build gave them back); and Set Pivot and Ring blamed "has been moved and not
  recorded". Remove, Set Pivot and Ring now ask for a frame where the rig has a
  size, in the words Record and Build use; Make Chain only notes the chain, and
  the next Build hangs it; the eye shows the pose and leaves the parts alone.
- **A hand-built chain whose first bone is a part played a step behind its
  slider.** An armature Upper > Fore > Hand with no root bone of its own: the
  slider's property and the handle went on Upper, the first bone with no parent,
  which is a part itself. The handle became Upper's child, the slider's driver
  looped through it ("Dependency cycle detected"), and on frame 42, with the
  slider at 0.85, Upper stood at 0 degrees where 34.2 was wanted. The handle now
  hangs from no part and from nothing below one: from the nearest bone above the
  control that is clear of the parts, or from none. A rig with a root bone of
  its own keeps its handle on it. (A file built before this is put right by its
  next Build.)
- **A model scaled up 130 times or more was read as dragged at every button,**
  and Record then lost its move. How much two places may differ now grows with
  the model's size as well as its distance from the origin.
- **Set Origin on a very thin part moved it at the next Build** (a rod 10,000
  times longer than it is thick). Such parts are told right now.
- **After the whole model was carried far, Build said parts had turned about a
  new pivot** and keyed their paths again, though nothing had changed.
- **An Alt+D copy of an animated model shared the rig's own keys.** Remove,
  Animate or the key button on the copy, or a new Path length, changed the
  original's animation.
- **An Alt+D copy made with its path curves selected shared the curves' shape
  with the original:** bending the copy's curve bent the original's path too.
- **On Blender 5.0 and 5.2 the select icon beside a bone part in the Timing list
  raised an error.**

- **Scaling or turning the whole model on its rig and then applying it made the
  next Build put the parts back.** S 2 or R Z 90 on the rig, then Ctrl+A >
  Scale or Rotation with no button pressed in between, and the lid ended up
  1.6 m or 2.2 m off. The model is carried by the scale or the turn now, as it
  is when the rig is moved; editing the Root bone in Edit Mode is still no move.
- **A mesh joined into a built part with Ctrl+J stayed behind if it had a vertex
  group of its own** - a knob that was a part of the move too, or a mesh with a
  group such as "Pin". A vertex counts as weighted now only by a weight on a
  bone of the rig that deforms; the rest join the part's group and keep their
  other groups.
- **On an Alt+D copy of a whole model, bending its curve - with Edit the Curve,
  or with Tab - bent the original's curve too.** The copy's curves are its own
  as soon as the copy is made.

- **Installed from the zip, 0.20.0's panel raised an error each time it was
  drawn** ("name 'bl_info' is not defined"), and its last line, the version,
  was missing. Blender takes that information away from an extension once it
  is loaded; the panel keeps its own copy of the version now.

- **At the sidebar's usual width the panel cut its words short:** "Before" read
  "Be" and "After" "Af", Spread "Spr…", Make Chain "Make C…", the pivot's
  "Origin" "Or…", Frames "Fra…" and the rig's name "Cop…"; the copies' Leads did
  not show at all, and the hints and the report lost words out of their middle
  or off their end. Each row now measures what it has room for, in the panel's
  own font: what does not fit side by side goes one under the other, the poses
  read as a checklist, Spread sits in the sections it spreads for, and the hints
  and the report are broken into lines that fit.
- **Deleting the active part with X turned the panel into "Pick the rig to work
  on"**, a list of one, and picking it put a rig made of objects into pose mode,
  where its parts cannot be clicked. The panel stays on the rig being worked on,
  and such a rig is picked in object mode.
- **Ringing the inner petals of a bud before the outer ones left the outer ring
  with 2 of its 7 copies**: the shut inner petals stood near enough to its
  places to count as something standing there. Only something about the size of
  the part being ringed counts now.
- **Ring, used after Record After, said "Record its After, then Build" in the
  status bar** for a moment, though After was recorded.

## Known rough edges

- While a finger is shown bent, dragging its base opens the bent joints on
  screen. What is recorded is the finger carried whole, joints shut; pose
  at Play 0 to see it as it will be.
- Changing **Follows** waits for **Build**. Posed before that Build, a
  follower is recorded as it is seen, not with its own joint kept. Build
  first to keep it.

- Before should be the rest pose. Nothing warns when it is not, and a machine
  recorded from a half-posed start will be wrong at the ends.
- Steps are only offered once a move has bones, so for objects that means
  after the first build.
- Use what's there compares the points, not the numbering, with a fiftieth of the
  part's size as leeway. A petal sculpted a little further off than that, or with a
  vertex more or fewer, is not a copy of it: it is named as left out, and its place
  is left alone rather than copied on top. A leaf with one joint different is left
  alone as a whole place. Materials that use an object's own or generated texture
  coordinates are not checked when an object is re-framed.
- An object is bound whole, to one bone. Parts that bend need a rig of their
  own and the bone workflow.
- Two moves on one bone of a hand-built rig compose in the order they were made,
  which is not shown anywhere. An object can be in one move only: a file that already
  has one in two is reported by Build, which leaves it as it is until it is taken out
  of all but one.
- A move can be in only one combined control at a time.
- A part follows another part of the same move.
- Copies of a finger are matched to it by where their pieces stand. A copy
  built differently - a joint more or fewer, segments of very different
  lengths, or bent at the knuckles - may be matched only in part, and what
  is left over rides along with the part you clicked. The **+** under Riding
  along says how many joints each copy got.
- Mirror on a copied finger mirrors every joint across one plane, the first
  joint's, whichever way the other segments are rolled about their own length.
  Across an axis along the finger the curl goes the other way, as meant; across
  the finger's length it is no mirror image of the whole finger. For that, copy
  it with Ctrl+M, which mirrors by itself. The copy's pieces stand where you put
  them: Mirror turns how they move, not where they are.
- An object parented to something outside the rig - a finger to a hand that
  is not in the move - is taken off that parent while it is bound, so moving
  the hand leaves it behind. Parent the rig to the hand instead.
- A child of a part - a handle Ctrl+P'd to a lid - moves with it only if it is a part
  of the move too. Only meshes can be: an empty or a light parented to a part stays
  where it is, and is named in the report as one that cannot move with it.
- A part whose origin, scale or rotation was changed after it was bound is put
  back on its frame only if what Blender shows is the same before and after. With
  a constraint on it, or a modifier that measures from its frame, it is not: undo
  the change, or take the part out of its move and add it again.
- Set Origin on a built part, then an edit of its mesh before any CopyThat button,
  can be read as a drag, and Build puts the part back. Press any CopyThat button
  between the two (the eye will do).
- Apply Scale on a rig that is scaled unevenly is still read as a move of the model.
- Every vertex of a part moves with it at full weight: a Build sets a vertex painted to
  0 in the part's own group back to 1. CopyThat moves parts whole.
- On a frame where the rig is scaled to nothing, Record, Build, Remove, Set Pivot and Ring
  are refused. Go to a frame where it has a size.
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
- Curl puts every part below the root where the bend says, replacing the bend
  it had. A joint whose new bend is none at all - a factor of 0, which leaves
  everything below the root straight - is read by Record as only carried, and
  keeps the keys it had.
- Curl works only from rest, and the factor is only in the Adjust Last Operation
  panel, not on the button.
- Ring's linked copies share one mesh only until Build, which gives every bound
  part a mesh of its own; edit-mode changes after that are one part's alone.
- Ring sees mesh objects only. A collection instance, a curve, a text object or an
  empty standing in a place of the ring is not seen: **Fill the gaps** makes its
  copy on top of it, and **Use what's there** never takes it up.
- Spread's ring takes the best-fit plane of the parts' spots. Parts that are not
  roughly on one ring - a scatter - get an order that is the plane's, and is
  seldom what was meant: use By distance or Along an axis instead.
- Ctrl+A > Scale on the rig of a model that was scaled keeps the moves at their
  old length: Blender does not scale bone keys when it applies an armature's
  scale, with or without CopyThat. Scale the model with its rig instead, or
  apply the scale before you record.
- Two moves with exactly the same name: the first loses its slider handle. Give
  each move its own name.
- Moved the whole model, or edited the rig's Root bone, and want to save? Press
  any CopyThat button first (the eye will do), so the change is taken in before
  the file is saved.
