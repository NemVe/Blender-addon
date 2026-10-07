"""RigMoves - record how a machine moves between two poses, get one slider.

An experiment. It shares no code with RigKit / Rigthebot and never touches it.

A machine's parts travel between two places - shut and open, retracted and
extended, parked and deployed - and the animator wants one number for that, not
eight bones dragged in the right order.

Two poses is the start of it, not the end. Between them there is usually a
*path*: a hatch that swings clear before it slides, an arm that lifts before it
reaches, a jaw that overshoots and settles. And the parts rarely all move at
once - one follows another a beat later. So a move here is:

  * the parts that take part, each with its own delay and finish time;
  * an Action holding the whole path between Before and After, which the
    animator can open in the timeline and shape however they like;
  * one slider that scrubs the lot.

How it is driven. Each part gets an Action constraint carrying the move's own
action, with its evaluation time driven from the slider. That is the standard
way a rig replays a canned motion, and it is what makes an arbitrary path and a
per-part delay possible at all - a plain driver can only interpolate a straight
line between two numbers. The constraint sits at the *top* of the bone's stack,
so whatever constraints the bone already carries still run afterwards, and a
hand-built rig can be given a slider without being taken apart first.
"""

import bpy
from mathutils import Matrix, Vector

bl_info = {
    "name": "RigMoves - Record a Move, Get a Slider",
    "author": "AutoRigger experiments",
    "version": (0, 9, 9),
    "blender": (4, 4, 0),
    "location": "View3D > Sidebar > Moves",
    "description": "Record a path between two poses of any bones, with per-part "
                   "delays. Works on loose objects with no rig at all, and makes one",
    "category": "Rigging",
}

# Everything this add-on makes is named with these, so its own work can always
# be told from somebody else's on the same bone.
CONSTRAINT = "RigMoves: "
RAIL = "RigMoves rail"
PART_MARK = "RigMoves part"
WIDGET = "RM_arrow_solid"
WIDGET_DOUBLE = "RM_arrow_solid_double"
VAR = "rm_v"
GROUP_VAR = "rm_g"
HANDLE_VAR = "rm_h"
FIRST_FRAME = 1


# ---------------------------------------------------------------------------
# reading a pose


def channels_of(pose_bone):
    """The channels that make up this bone's pose, as (path, index, value).

    Whatever rotation mode the bone is already in is respected. Changing it
    would silently alter curves an existing rig already has.
    """
    out = [("location", i, pose_bone.location[i]) for i in range(3)]
    mode = pose_bone.rotation_mode
    if mode == "QUATERNION":
        out += [("rotation_quaternion", i, pose_bone.rotation_quaternion[i])
                for i in range(4)]
    elif mode == "AXIS_ANGLE":
        out += [("rotation_axis_angle", i, pose_bone.rotation_axis_angle[i])
                for i in range(4)]
    else:
        out += [("rotation_euler", i, pose_bone.rotation_euler[i]) for i in range(3)]
    out += [("scale", i, pose_bone.scale[i]) for i in range(3)]
    return out


def flat(matrix):
    out = []
    for row in matrix:
        out.extend(row)
    return out


def as_matrix(values):
    """Rebuild a 4x4 from sixteen floats, element by element.

    Not Matrix(values): a Blender float array does not slice into rows the way
    the constructor wants, and the MATRIX property subtype reads back in a
    different order than it was written - which silently transposes a pose and
    drops the part at the world origin.
    """
    matrix = Matrix()
    for row in range(4):
        for column in range(4):
            matrix[row][column] = float(values[row * 4 + column])
    return matrix


def part_bone(part):
    """The bone a part is driven through.

    A part that started as a bone is its own; a part that started as a loose
    object gets one made for it at the first build, and answers to that from
    then on.
    """
    if part.kind == "OBJECT" and part.bone_name:
        return part.bone_name
    return part.name


def bone_path(bone_name, path):
    return 'pose.bones["{:s}"].{:s}'.format(
        bpy.utils.escape_identifier(bone_name), path)


def property_path(bone_name, prop):
    return 'pose.bones["{:s}"]["{:s}"]'.format(
        bpy.utils.escape_identifier(bone_name), bpy.utils.escape_identifier(prop))


# ---------------------------------------------------------------------------
# the action that holds the path
#
# Blender 4.4 onwards keeps an action's curves under a slot, a layer and a
# strip rather than in one flat list, so every touch of one goes through here.


def action_bits(move, make=False):
    """(action, slot, channelbag) for a move, made on demand."""
    action = bpy.data.actions.get(move.action_name) if move.action_name else None
    if action is None:
        if not make:
            return None, None, None
        action = bpy.data.actions.new(move.action_name or "RigMoves")
        # Nothing points at it until the move is built, and an action with no
        # users is thrown away when the file is saved.
        action.use_fake_user = True
        move.action_name = action.name
    if len(action.slots):
        slot = action.slots[0]
    elif make:
        slot = action.slots.new(id_type="OBJECT", name="Rig")
    else:
        return action, None, None
    layer = action.layers[0] if len(action.layers) else (
        action.layers.new("Path") if make else None)
    if layer is None:
        return action, slot, None
    strip = layer.strips[0] if len(layer.strips) else (
        layer.strips.new(type="KEYFRAME") if make else None)
    if strip is None:
        return action, slot, None
    return action, slot, strip.channelbag(slot, ensure=make)


def curve_for(bag, path, index, make=False):
    for curve in bag.fcurves:
        if curve.data_path == path and curve.array_index == index:
            return curve
    return bag.fcurves.new(path, index=index) if make else None


def last_frame(move):
    return FIRST_FRAME + max(1, move.frames)


def key_pose(rig, move, frame, only=None):
    """Write where every taking-part bone stands right now, at this frame.

    `only` narrows it to certain bones, so binding a set of loose objects does
    not also re-key the bones of a move that was recorded by hand.
    """
    _action, _slot, bag = action_bits(move, make=True)
    if bag is None:
        return 0
    count = 0
    for part in move.parts:
        pose_bone = rig.pose.bones.get(part_bone(part))
        if pose_bone is None or (only is not None and part_bone(part) not in only):
            continue
        for path, index, value in channels_of(pose_bone):
            curve = curve_for(bag, bone_path(part_bone(part), path), index, make=True)
            point = curve.keyframe_points.insert(float(frame), value)
            # Straight lines between the keys, so the only shaping is the one
            # that was asked for - the Ease setting, or curves bent by hand in
            # the graph editor. Blender's default bezier would quietly add an
            # ease nobody chose, on top of the one they did.
            point.interpolation = "LINEAR"
            curve.update()
        count += 1
    return count


def pose_at(rig, move, frame):
    """Put the bones into the path's pose at this frame."""
    _action, _slot, bag = action_bits(move)
    if bag is None:
        return
    for part in move.parts:
        pose_bone = rig.pose.bones.get(part_bone(part))
        if pose_bone is None:
            continue
        for path, index, _value in channels_of(pose_bone):
            curve = curve_for(bag, bone_path(part_bone(part), path), index)
            if curve is None or not len(curve.keyframe_points):
                continue
            try:
                getattr(pose_bone, path)[index] = curve.evaluate(float(frame))
            except (AttributeError, IndexError):
                pass


def keyed_at(move, frame):
    """Whether the path has anything recorded at this frame."""
    _action, _slot, bag = action_bits(move)
    if bag is None:
        return False
    for curve in bag.fcurves:
        for point in curve.keyframe_points:
            if abs(point.co[0] - frame) < 0.5:
                return True
    return False


def path_keys(move):
    """Every frame the path has a key on, in order."""
    _action, _slot, bag = action_bits(move)
    frames = set()
    if bag is not None:
        for curve in bag.fcurves:
            for point in curve.keyframe_points:
                frames.add(round(point.co[0]))
    return sorted(frames)


GAP = 4  # frames between one step and the next, so rounding never merges them


def shift_keys(move, frm, to):
    """Move every key sitting on one frame onto another."""
    _action, _slot, bag = action_bits(move)
    if bag is None or abs(frm - to) < 1e-4:
        return
    for curve in bag.fcurves:
        for point in curve.keyframe_points:
            if abs(point.co[0] - frm) < 0.5:
                shift = to - point.co[0]
                point.handle_left[0] += shift
                point.handle_right[0] += shift
                point.co[0] = to
        curve.update()


def drop_keys_at(move, frame):
    """Take out every key on one frame, and say how many went."""
    _action, _slot, bag = action_bits(move)
    if bag is None:
        return 0
    gone = 0
    for curve in bag.fcurves:
        doomed = [p for p in curve.keyframe_points if abs(p.co[0] - frame) < 0.5]
        for point in reversed(doomed):
            try:
                curve.keyframe_points.remove(point)
                gone += 1
            except (RuntimeError, ReferenceError):
                pass
        curve.update()
    return gone


def respace_steps(move):
    """Put the steps in even order between Before and After.

    Their spacing is not something to fuss over - the slider runs the whole
    path whatever its length, and Timing is where a part is told to start
    late. Even is simply the answer that needs no explaining.
    """
    count = len(move.steps)
    # Long enough that the steps never round onto one another, and never
    # shorter than the length a path has always had.
    want = max(20, GAP * (count + 1))
    if move.frames != want:
        # Setting this rescales every key that is already down, Before and
        # After included, so the steps come along with it.
        was = float(max(1, move.frames))
        move.frames = want
        for step in move.steps:
            if step.done:
                share = (step.frame - FIRST_FRAME) / was
                step.frame = FIRST_FRAME + share * want
    if not count:
        return
    # Two passes through a parking frame, so a step on its way to a slot
    # never lands on one another step has not left yet.
    park = FIRST_FRAME + want + 1000.0
    moving = []
    for position, step in enumerate(move.steps):
        target = FIRST_FRAME + want * (position + 1) / float(count + 1)
        if step.done and abs(step.frame - target) > 0.01:
            shift_keys(move, step.frame, park + position)
            moving.append((park + position, target))
        step.frame = target
    for frm, to in moving:
        shift_keys(move, frm, to)


def rescale_keys(move, was, now):
    """Stretch the path when its length is changed, keeping its shape."""
    _action, _slot, bag = action_bits(move)
    if bag is None or was <= 0 or now <= 0 or was == now:
        return
    for curve in bag.fcurves:
        for point in curve.keyframe_points:
            share = (point.co[0] - FIRST_FRAME) / float(was)
            moved = FIRST_FRAME + share * now
            shift = moved - point.co[0]
            point.handle_left[0] += shift
            point.handle_right[0] += shift
            point.co[0] = moved
        curve.update()


# ---------------------------------------------------------------------------
# the handle: a bone on a rail, for driving a move in the viewport instead of
# from the panel. Both are the same number underneath - the handle drives the
# move's property and everything else goes on reading that property - so
# choosing one or the other changes nothing about how the move plays.


def handle_widget(double=False):
    """An arrow pointing along the rail: one head for a move, two for a
    combined control.

    Two shapes rather than one size, because a rig ends up with a handle per
    move and one more that plays the lot, and at a glance they were the same
    object in the same place. An arrow also says which way to drag, which a
    box does not.

    Drawn in two planes at right angles so it reads from any angle - a flat
    arrow disappears when the camera lines up with it. Not linked into the
    scene: a custom shape is only ever drawn, never rendered or selected in
    its own right, and an extra object in the outliner of somebody else's
    file is rude.
    """
    name = WIDGET_DOUBLE if double else WIDGET
    found = bpy.data.objects.get(name)
    if found is not None:
        return found

    def ring(along, half):
        return [(-half, along, -half), (half, along, -half),
                (half, along, half), (-half, along, half)]

    # A square shaft with a pyramid head on it - solid enough to see and to
    # click on from any angle, where a single line of an arrow disappears
    # edge-on and is a pixel wide to hit.
    shaft, spread = 0.11, 0.32
    low, high = (-0.55, 0.3) if double else (-0.45, 0.35)
    heads = ((0.3, 0.8), (-0.3, 0.2)) if double else ((0.35, 0.9),)
    bottom, top = ring(low, shaft), ring(high, shaft)
    strokes = [bottom + [bottom[0]], top + [top[0]]]
    strokes.extend([bottom[i], top[i]] for i in range(4))
    for base, tip in heads:
        edge = ring(base, spread)
        strokes.append(edge + [edge[0]])
        strokes.extend([corner, (0.0, tip, 0.0)] for corner in edge)

    points, edges = [], []
    for stroke in strokes:
        first = len(points)
        points.extend(stroke)
        edges.extend((first + i, first + i + 1) for i in range(len(stroke) - 1))
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(points, edges, [])
    mesh.update()
    made = bpy.data.objects.new(name, mesh)
    made.use_fake_user = True
    return made


def rig_reach(rig):
    """How big the whole rig is, in world units."""
    points = []
    for bone in rig.data.bones:
        points.append(rig.matrix_world @ bone.head_local)
        points.append(rig.matrix_world @ bone.tail_local)
    if not points:
        return 1.0
    low = Vector((min(p.x for p in points), min(p.y for p in points),
                  min(p.z for p in points)))
    high = Vector((max(p.x for p in points), max(p.y for p in points),
                   max(p.z for p in points)))
    return max((high - low).length, 1e-3)


def handle_place(rig, names):
    """Where a handle over these bones should stand, and how long its rail is.

    Over the middle of what it moves and clear of it, so a rig with several
    controls gets a handle beside each one rather than a row of them somewhere
    else. A combined control takes the middle of everything it plays.

    Its length is a share of the whole rig, not of the bones. A move often
    drives small controller bones on a big machine - the eyelid controllers on
    the test rig are a tenth of it - and a handle scaled to those is a speck
    nobody can grab.
    """
    points = []
    for name in names:
        bone = rig.data.bones.get(name)
        if bone is None:
            continue
        points.append(rig.matrix_world @ bone.head_local)
        points.append(rig.matrix_world @ bone.tail_local)
        # The bone of a bound object stands at its origin and says nothing
        # about how big it is, so the object's own corners are what decide.
        for child in rig.children:
            if child.type == "MESH" and child.vertex_groups.get(name) is not None:
                points.extend(child.matrix_world @ Vector(c) for c in child.bound_box)
    if not points:
        return None, 0.1
    low = Vector((min(p.x for p in points), min(p.y for p in points),
                  min(p.z for p in points)))
    high = Vector((max(p.x for p in points), max(p.y for p in points),
                   max(p.z for p in points)))
    centre = (low + high) * 0.5
    # Sized from what it drives, with a floor so it is never a speck on a big
    # machine. Standing at the middle of those parts rather than above them:
    # the rig is drawn in front of the mesh, so a control inside the machine
    # is still clickable, and one hanging in the air above it is just far
    # away from the thing it moves.
    rail = max((high - low).length * 0.11, rig_reach(rig) * 0.04, 1e-3)
    return centre, rail


def carriers(data):
    """Everything that can carry a control, with the bones it ends up moving.

    A move carries its own parts; a combined control carries everything its
    members do, so its handle lands in the middle of the whole sequence.
    """
    out = []
    for move in data.moves:
        out.append((move, [part_bone(p) for p in move.parts]))
    for group in data.groups:
        names = []
        for member in group.members:
            move = move_by_uid(data, member.uid)
            if move is not None:
                names.extend(part_bone(p) for p in move.parts)
        out.append((group, names))
    return out


def sync_handles(rig, data):
    """Make, move or unmake every handle in one trip through edit mode."""
    wanted = {}
    # Moves first, combined controls after, so a combined one is placed
    # knowing where its members already are.
    for carrier, names in carriers(data):
        if carrier.handle and names:
            wanted[carrier.handle_name or (carrier.name + " handle")] = (carrier, names)
    wanted = dict(sorted(wanted.items(),
                         key=lambda row: 1 if hasattr(row[1][0], "members") else 0))
    stale = [b.name for b in rig.data.bones
             if b.get(RAIL) is not None and b.name not in wanted]
    if not wanted and not stale:
        return

    was_mode = rig.mode
    view_layer = bpy.context.view_layer
    was_active = view_layer.objects.active
    if not activate(bpy.context, rig):
        return
    if rig.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.mode_set(mode="EDIT")
    edit = rig.data.edit_bones
    for name in stale:
        bone = edit.get(name)
        if bone is not None:
            edit.remove(bone)
    into_armature = rig.matrix_world.inverted_safe()
    # Where each one goes is worked out before any of them is made, so two
    # controls over the same parts get pushed apart instead of stacked. Two
    # moves on one machine sit over the same middle, and a combined control
    # sits over both - three handles within a few centimetres of each other,
    # identical to look at. Grabbing one and getting another reads as the
    # control simply not working.
    placed = []
    for name, (move, names) in list(wanted.items()):
        where, rail = handle_place(rig, names)
        if where is None:
            continue
        if hasattr(move, "members"):
            # A combined control plays everything its members do, so it is
            # drawn larger. It needs no lift of its own - being bigger and
            # two-headed is enough to tell it apart.
            rail *= 1.25
        # Upwards, never sideways. A row spread along a world axis vanishes
        # the moment the camera looks down that axis, which is exactly what
        # happened on the test rig. Only as far as it takes to clear the last
        # one, so the controls stay among the parts they move.
        step = Vector((0.0, 0.0, rail * 1.35))
        for _try in range(16):
            if not any((where - other).length < max(rail, other_rail) * 1.3
                       for other, other_rail in placed):
                break
            where = where + step
        placed.append((where, rail))

        move.rail = rail
        bone = edit.get(name) or edit.new(name)
        head = into_armature @ where
        bone.head = head
        # Along the rig's own up, so dragging the handle feels like a fader.
        bone.tail = head + Vector((0.0, 0.0, rail))
        bone.roll = 0.0
        bone.use_deform = False
        bone.use_connect = False
        holder = edit.get(move.control)
        bone.parent = holder if (holder is not None and holder.name != bone.name) else None
        move.handle_name = bone.name
    bpy.ops.object.mode_set(mode="OBJECT")

    # The rail length is written on the bone as well, so a handle can be known
    # for ours later without consulting the panel.
    for carrier, _names in carriers(data):
        bone = rig.data.bones.get(carrier.handle_name) if carrier.handle else None
        if bone is not None:
            bone[RAIL] = float(carrier.rail)

    if was_mode != "OBJECT":
        try:
            bpy.ops.object.mode_set(mode=was_mode)
        except RuntimeError:
            pass
    if was_active is not None and was_active is not rig:
        view_layer.objects.active = was_active


def dress_handle(rig, move):
    """The handle's rail, locks and shape, once its bone exists."""
    pose_bone = rig.pose.bones.get(move.handle_name)
    if pose_bone is None:
        return None
    for constraint in list(pose_bone.constraints):
        if constraint.name == RAIL:
            pose_bone.constraints.remove(constraint)
    limit = pose_bone.constraints.new("LIMIT_LOCATION")
    limit.name = RAIL
    limit.owner_space = "LOCAL"
    # Held to the rail, not merely read along it: a handle that can be dragged
    # past its own ends looks broken even though the move itself is clamped.
    limit.use_transform_limit = True
    for axis in ("x", "z"):
        setattr(limit, "use_min_" + axis, True)
        setattr(limit, "use_max_" + axis, True)
        setattr(limit, "min_" + axis, 0.0)
        setattr(limit, "max_" + axis, 0.0)
    limit.use_min_y, limit.use_max_y = True, True
    limit.min_y, limit.max_y = 0.0, float(move.rail)
    pose_bone.lock_location = (True, False, True)
    pose_bone.lock_rotation = (True, True, True)
    pose_bone.lock_rotation_w = True
    pose_bone.lock_scale = (True, True, True)
    pose_bone.custom_shape = handle_widget(double=hasattr(move, "members"))
    pose_bone.use_custom_shape_bone_size = True
    pose_bone.custom_shape_wire_width = 4.0
    rig.data.bones[move.handle_name]["what"] = (
        "Drag it along its rail to play '{:s}'".format(move.name))
    return pose_bone


def drive_property_from_handle(rig, move):
    """Let the handle write the move's slider, so both read the same number."""
    path = property_path(move.control, move.prop)
    rig.driver_remove(path)
    if not (move.handle and move.handle_name in rig.pose.bones):
        return False
    curve = rig.driver_add(path)
    for modifier in list(curve.modifiers):
        curve.modifiers.remove(modifier)
    driver = curve.driver
    driver.type = "SCRIPTED"
    for variable in list(driver.variables):
        driver.variables.remove(variable)
    variable = driver.variables.new()
    variable.name = HANDLE_VAR
    variable.type = "TRANSFORMS"
    target = variable.targets[0]
    target.id = rig
    target.bone_target = move.handle_name
    target.transform_type = "LOC_Y"
    target.transform_space = "LOCAL_SPACE"
    rail = move.rail or 1.0
    driver.expression = "{:.10g}+({:.10g})*({:s}/{:.10g})".format(
        move.low, move.high - move.low, HANDLE_VAR, rail)
    return True


def ensure_slider(rig, carrier):
    """The custom property a move or a combined control is driven by."""
    control = carrier.control if carrier.control in rig.pose.bones else default_control(rig)
    carrier.control = control
    if not control:
        return None
    if not carrier.prop:
        carrier.prop = unique_prop_name(rig, carrier, safe_prop_name(carrier.name))
    bone = rig.pose.bones[control]
    if carrier.prop not in bone.keys():
        bone[carrier.prop] = float(carrier.low)
    low, high = sorted((carrier.low, carrier.high))
    bone.id_properties_ui(carrier.prop).update(
        default=float(carrier.low),
        min=low - 1000.0, max=high + 1000.0,
        soft_min=low, soft_max=high,
        description="{:s}: {:g} is Before, {:g} is After".format(
            carrier.name, carrier.low, carrier.high))
    return bone


def add_slider_variable(driver, rig, name, bone_name, prop):
    variable = driver.variables.new()
    variable.name = name
    variable.type = "SINGLE_PROP"
    target = variable.targets[0]
    target.id_type = "OBJECT"
    target.id = rig
    target.data_path = property_path(bone_name, prop)
    return variable


def move_by_uid(data, uid):
    for move in data.moves:
        if move.uid == uid:
            return move
    return None


def group_of(data, move):
    """The combined control this move belongs to, and its place in it."""
    for group in data.groups:
        for member in group.members:
            if member.uid and member.uid == move.uid:
                return group, member
    return None, None


# ---------------------------------------------------------------------------
# the data, stored on the armature so it travels with the rig


class RIGMOVES_Part(bpy.types.PropertyGroup):
    """One thing in a move, and when it takes its turn.

    Either a bone of a rig that already exists, or a loose object that has no
    rig yet - in which case the two poses are kept here until the first build,
    which makes it a bone and binds the object to it.
    """
    name: bpy.props.StringProperty()
    kind: bpy.props.EnumProperty(
        items=[("BONE", "Bone", ""), ("OBJECT", "Object", "")], default="BONE")
    bone_name: bpy.props.StringProperty()
    before: bpy.props.FloatVectorProperty(size=16)
    after: bpy.props.FloatVectorProperty(size=16)
    has_before: bpy.props.BoolProperty(default=False)
    has_after: bpy.props.BoolProperty(default=False)
    start: bpy.props.FloatProperty(
        name="Delay", default=0.0, min=0.0, max=0.99, subtype="FACTOR",
        description="How far along the slider this part waits before it starts. "
                    "0 moves with everything else, 0.5 starts half way")
    end: bpy.props.FloatProperty(
        name="Done", default=1.0, min=0.01, max=1.0, subtype="FACTOR",
        description="How far along the slider this part has arrived. Below 1 it "
                    "gets there early and then waits")


def safe_prop_name(text):
    kept = "".join(c if (c.isalnum() or c in " _-") else "_" for c in text).strip()
    return kept or "Move"


def unique_prop_name(rig, move, wanted):
    """A slider name nothing else on this rig is already using.

    Two moves that ended up with the same name shared one custom property and
    silently drove each other, and removing either deleted the slider of both.
    Combined controls are in the same pot, for the same reason.
    """
    mine = move.as_pointer()
    taken = {m.prop for m in rig.rigmoves.moves if m.as_pointer() != mine}
    taken |= {g.prop for g in rig.rigmoves.groups if g.as_pointer() != mine}
    if wanted not in taken:
        return wanted
    number = 2
    while "{:s} {:d}".format(wanted, number) in taken:
        number += 1
    return "{:s} {:d}".format(wanted, number)


def _renamed(self, context):
    """Keep the slider's name in step with the move's, until it is built.

    After a build the name is what the drivers point at, so it is left alone -
    renaming then would strand every driver on a property nobody writes.
    """
    if not self.built:
        self.prop = unique_prop_name(self.id_data, self, safe_prop_name(self.name))
        return
    # Already built: the slider keeps the name its drivers point at, but the
    # constraints are renamed with the move so the panel and the rig agree.
    rig = self.id_data
    for pose_bone, constraint in our_constraints(rig, self):
        constraint.name = CONSTRAINT + self.name
        self.con_name = constraint.name


def _frames_changed(self, context):
    """Keep the recorded path when its length is changed."""
    wanted = max(1, self.frames)
    if self.frames_applied and self.frames_applied != wanted:
        rescale_keys(self, self.frames_applied, wanted)
    self.frames_applied = wanted


class RIGMOVES_Step(bpy.types.PropertyGroup):
    """One pose between Before and After.

    Kept as data rather than worked out from the keys on the path, because a
    step has to exist before it holds anything: pressing + puts an empty one
    up with its own Record, and there is nothing on the path to find until
    that Record is pressed.
    """
    frame: bpy.props.FloatProperty(default=0.0)
    done: bpy.props.BoolProperty(default=False)


class RIGMOVES_Move(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(name="Name", default="Move", update=_renamed)
    parts: bpy.props.CollectionProperty(type=RIGMOVES_Part)
    action_name: bpy.props.StringProperty()
    # A name of its own that never changes, so a combined control can point at
    # this move and go on pointing at it after somebody renames it.
    uid: bpy.props.StringProperty()
    frames: bpy.props.IntProperty(
        name="Path length", default=20, min=1, max=500, update=_frames_changed,
        description="How many frames the path is drawn over. Only its shape "
                    "matters - the slider always runs the whole of it")
    frames_applied: bpy.props.IntProperty(default=20)
    steps: bpy.props.CollectionProperty(type=RIGMOVES_Step)
    ease: bpy.props.EnumProperty(
        name="Ease",
        items=[("LINEAR", "Even speed", "The same speed the whole way"),
               ("SMOOTH", "Smooth", "Starts and stops gently"),
               ("IN", "Slow start", "Starts gently, arrives at full speed"),
               ("OUT", "Slow stop", "Starts at full speed, arrives gently")],
        default="LINEAR")
    # The bone that carries the slider. Any bone will do; the root is the one
    # an animator can always find.
    control: bpy.props.StringProperty(name="On")
    prop: bpy.props.StringProperty()
    # The name the constraints actually ended up with. Blender makes a
    # constraint name unique on its bone, so two moves called the same thing
    # do not both answer to "RigMoves: Close" - and the drivers address a
    # constraint by name, so the one that was really used has to be kept.
    con_name: bpy.props.StringProperty()
    low: bpy.props.FloatProperty(name="From", default=0.0)
    high: bpy.props.FloatProperty(name="To", default=1.0)
    # A handle in the viewport instead of the panel's slider. Both write
    # the same number; this only decides where the animator reaches.
    handle: bpy.props.BoolProperty(
        name="Handle in the viewport", default=True,
        description="Put a bone on a rail over these parts, to drag in the "
                    "3D view. The panel shows its position either way")
    handle_name: bpy.props.StringProperty()
    rail: bpy.props.FloatProperty(default=0.1)
    built: bpy.props.BoolProperty(default=False)
    expanded: bpy.props.BoolProperty(default=True)
    show_timing: bpy.props.BoolProperty(default=False)


def _group_renamed(self, context):
    """Until it is built the slider is named after the control; after that the
    drivers point at that name, so it is left alone."""
    if not self.built:
        self.prop = unique_prop_name(self.id_data, self, safe_prop_name(self.name))


class RIGMOVES_Member(bpy.types.PropertyGroup):
    """One move inside a combined control, and when it takes its turn."""
    uid: bpy.props.StringProperty()
    start: bpy.props.FloatProperty(
        name="Delay", default=0.0, min=0.0, max=0.99, subtype="FACTOR",
        description="How far along the combined control this move waits before "
                    "it starts. 0 plays with the first one, 0.5 starts half way")
    end: bpy.props.FloatProperty(
        name="Done", default=1.0, min=0.01, max=1.0, subtype="FACTOR",
        description="How far along the combined control this move has finished")


class RIGMOVES_Group(bpy.types.PropertyGroup):
    """One control that plays several recorded moves, in order.

    Its members keep their own controls: the two are combined with a max, so a
    move can be played on its own or as part of the sequence, and neither
    blocks the other.
    """
    name: bpy.props.StringProperty(name="Name", default="Together",
                                   update=_group_renamed)
    members: bpy.props.CollectionProperty(type=RIGMOVES_Member)
    control: bpy.props.StringProperty(name="On")
    prop: bpy.props.StringProperty()
    low: bpy.props.FloatProperty(name="From", default=0.0)
    high: bpy.props.FloatProperty(name="To", default=1.0)
    handle: bpy.props.BoolProperty(
        name="Handle in the viewport", default=True,
        description="Put a bone on a rail over everything this plays, to drag "
                    "in the 3D view")
    handle_name: bpy.props.StringProperty()
    rail: bpy.props.FloatProperty(default=0.1)
    built: bpy.props.BoolProperty(default=False)
    expanded: bpy.props.BoolProperty(default=True)


class RIGMOVES_Rig(bpy.types.PropertyGroup):
    moves: bpy.props.CollectionProperty(type=RIGMOVES_Move)
    groups: bpy.props.CollectionProperty(type=RIGMOVES_Group)
    next_uid: bpy.props.IntProperty(default=1)
    active: bpy.props.IntProperty(default=0)
    report: bpy.props.StringProperty()
    posing: bpy.props.BoolProperty(default=False)
    # While a path is open in the timeline: which move, and what the rig was
    # playing before, so it can be handed back untouched.
    editing: bpy.props.IntProperty(default=-1)
    kept_action: bpy.props.StringProperty()
    kept_slot: bpy.props.StringProperty()
    kept_range: bpy.props.IntVectorProperty(size=3, default=(1, 250, 1))


# ---------------------------------------------------------------------------
# helpers over the rig


def here(context, rig):
    """Whether this rig is actually in front of the user.

    An object deleted from the scene lives on in the file for as long as
    something still points at it, and this add-on's own data is stored on the
    armature - so a deleted rig goes on answering questions about its moves
    while being impossible to select, activate or edit. Everything that
    reaches for a rig has to ask this first.
    """
    return rig is not None and rig.name in context.view_layer.objects


def activate(context, rig):
    """Make the rig the active object, or say plainly that it cannot be."""
    if not here(context, rig):
        return False
    if context.object is not None and context.object.mode != "OBJECT":
        try:
            bpy.ops.object.mode_set(mode="OBJECT")
        except RuntimeError:
            pass
    context.view_layer.objects.active = rig
    return True


def rig_of(context):
    """The armature being worked on, whether it or one of its meshes is active."""
    obj = context.object
    if obj is None:
        return None
    if obj.type == "ARMATURE":
        return obj
    if obj.parent is not None and obj.parent.type == "ARMATURE" and here(context, obj.parent):
        return obj.parent
    for modifier in obj.modifiers:
        # An Armature modifier with no object in it points at nothing - a
        # leftover on a mesh whose rig was deleted - and must not count.
        if modifier.type == "ARMATURE" and here(context, modifier.object):
            return modifier.object
    # The active object is not always the last one clicked; an armature
    # anywhere in the selection is still plainly what is meant.
    for other in getattr(context, "selected_objects", ()):
        if other.type == "ARMATURE":
            return other
    # A loose object that some rig has already taken as a part of a move. This
    # is what keeps the panel on the right rig while the objects, not the
    # armature, are the things being selected and moved.
    chosen = {o.name for o in getattr(context, "selected_objects", ())}
    if chosen:
        for candidate in bpy.data.objects:
            if candidate.type != "ARMATURE" or not here(context, candidate):
                continue
            for move in candidate.rigmoves.moves:
                for part in move.parts:
                    if part.kind == "OBJECT" and part.name in chosen:
                        return candidate
    kept = getattr(context.scene, "rigmoves_rig", None)
    # Only while it still has something on it. An empty rig - one whose moves
    # were all removed, or one made and then undone - is a dead end: the panel
    # shows it, a newcomer has nothing to join, and the only way on is to add
    # to the very rig that is the problem.
    if here(context, kept) and len(kept.rigmoves.moves):
        return kept
    # A dead one is simply not returned. It is NOT cleared here: this runs
    # from the panel's draw, and Blender forbids writing to a scene while it
    # is being drawn - doing so threw on every redraw and took the panel with
    # it. forget_dead_rig does the clearing, from an operator, where writing
    # is allowed.
    return None


def forget_dead_rig(context):
    """Drop the remembered rig once it is deleted or emptied.

    Called from operators only. Nothing depends on it having run - rig_of
    ignores a dead pointer either way - it just stops one hanging about.
    """
    kept = getattr(context.scene, "rigmoves_rig", None)
    if kept is not None and not (here(context, kept) and len(kept.rigmoves.moves)):
        try:
            context.scene.rigmoves_rig = None
        except (AttributeError, RuntimeError):
            pass


def loose_parts(move):
    """Parts that are still objects, with no bone made for them yet."""
    return [p for p in move.parts if p.kind == "OBJECT" and not p.bone_name]


def bound_parts(move):
    """Parts that started as objects and now have a bone of their own."""
    return [p for p in move.parts if p.kind == "OBJECT" and p.bone_name
            and p.has_before]


def hand_moved(part):
    """A bound object's own transform, if it has been dragged off its Before.

    Binding makes the object's own transform the rig's rest: the modifier
    moves the mesh by how far the bone has travelled *from* there. So an
    object nudged in object mode after the build has not been posed - it has
    quietly redefined where the move starts, and every slider on it is then
    wrong by that much. Spotting the drift is what lets it be read as a pose
    instead, which is what somebody dragging it plainly meant.
    """
    obj = bpy.data.objects.get(part.name)
    if obj is None:
        return None, None
    rest = as_matrix(part.before)
    world = obj.matrix_world.copy()
    moved = max(abs(a - b)
                for row_a, row_b in zip(world, rest)
                for a, b in zip(row_a, row_b))
    return obj, (world if moved > 1e-5 else None)


TRANSFORM_PATHS = ("location", "rotation_euler", "rotation_quaternion",
                   "rotation_axis_angle", "scale", "delta_location",
                   "delta_rotation_euler", "delta_rotation_quaternion",
                   "delta_scale")


def own_transform_curves(obj):
    """An object's own keyframes on its own transform, wherever they live.

    These beat everything this add-on does. Binding makes the object's
    transform the rest the modifier measures the move from; a keyframe on that
    transform rewrites it on every frame change, so the part sits somewhere
    the rig never put it and the slider is out by that much for good. Blender
    gives no warning - the rig looks built and simply plays the wrong thing.

    Easy to end up with by accident: with Auto Keying on, dragging a part into
    its After pose keys it, which is exactly the gesture this tool asks for.
    """
    found = []
    if obj is None or obj.animation_data is None:
        return found
    action = obj.animation_data.action
    if action is None:
        return found
    for layer in action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                for curve in bag.fcurves:
                    if curve.data_path in TRANSFORM_PATHS:
                        found.append((bag, curve))
    # Blender 4.3 and older, and any action that never got a slot.
    for curve in getattr(action, "fcurves", ()):
        if curve.data_path in TRANSFORM_PATHS:
            found.append((action, curve))
    return found


def our_bone_names(data):
    """Every bone this add-on made: the parts' own, and the handles."""
    names = set()
    for move in data.moves:
        for part in move.parts:
            names.add(part_bone(part))
        if move.handle_name:
            names.add(move.handle_name)
    for group in data.groups:
        if getattr(group, "handle_name", ""):
            names.add(group.handle_name)
    names.discard("")
    return names


def rig_own_curves(rig, data):
    """Keys on the rig's own bones, as (holder, curve).

    The other half of the same trouble. Dragging a handle in pose mode with
    Auto Keying on keys that bone, and a keyed handle is pinned: it springs
    back to the keyed value on the next frame change, so the control appears
    to do nothing at all. The part bones are worse - they are held by Action
    constraints, and a key on top of one fights it.
    """
    out = []
    action = rig.animation_data.action if rig.animation_data else None
    if action is None:
        return out
    names = our_bone_names(data)

    def ours(path):
        if not path.startswith('pose.bones["'):
            return False
        try:
            bone = path.split('"')[1]
        except IndexError:
            return False
        return bone in names and path.rsplit("].", 1)[-1] in TRANSFORM_PATHS

    for layer in action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                out.extend((bag, c) for c in bag.fcurves if ours(c.data_path))
    out.extend((action, c) for c in getattr(action, "fcurves", ())
               if ours(c.data_path))
    return out


def lift_curves(pairs):
    """Take these F-curves out, and say how many went."""
    gone = 0
    for holder, curve in pairs:
        try:
            holder.fcurves.remove(curve)
            gone += 1
        except (RuntimeError, ReferenceError):
            pass
    return gone


def drop_empty_action(holder):
    """Unlink an action with nothing left in it, and bin it if nobody wants it."""
    animation = getattr(holder, "animation_data", None)
    action = animation.action if animation else None
    if action is None:
        return
    if any(len(bag.fcurves) for layer in action.layers
           for strip in layer.strips for bag in strip.channelbags):
        return
    if len(getattr(action, "fcurves", ())):
        return
    animation.action = None
    if action.users == 0 and not action.use_fake_user:
        bpy.data.actions.remove(action)


def clear_autokey(rig, data):
    """Take off the keyframes Auto Keying leaves on a rig as it is set up.

    Both kinds go, but not on the same terms. A key on a bound object's own
    transform is never right: binding makes that transform the rest the move
    is measured from, so a key on it is a rest that moves, and the slider is
    wrong by however far it moved. Nothing is lost either - wherever that key
    held the part is exactly what was recorded as Before or After.

    A key on one of our own bones is different, because keying a handle is how
    the finished machine gets animated. Only the contentless ones go: a single
    key, which is what a drag leaves behind and what pins the handle where it
    stands. Anything with a real curve on it is somebody's animation and is
    left alone, with a word said about it.
    """
    objects, bones, kept = 0, 0, []
    for move in data.moves:
        for part in move.parts:
            if part.kind != "OBJECT":
                continue
            obj = bpy.data.objects.get(part.name)
            if obj is None:
                continue
            found = own_transform_curves(obj)
            if found:
                objects += lift_curves(found)
                drop_empty_action(obj)

    ours = rig_own_curves(rig, data)
    spare = [pair for pair in ours if len(pair[1].keyframe_points) <= 1]
    real = [pair for pair in ours if len(pair[1].keyframe_points) > 1]
    bones = lift_curves(spare)
    if bones:
        drop_empty_action(rig)
    for _holder, curve in real:
        try:
            kept.append(curve.data_path.split('"')[1])
        except IndexError:
            pass
    return objects, bones, sorted(set(kept))


def keyed_parts(data, move=None):
    """Parts whose object carries transform keys of its own."""
    moves = [move] if move is not None else list(data.moves)
    out = []
    for one in moves:
        for part in one.parts:
            if part.kind != "OBJECT":
                continue
            obj = bpy.data.objects.get(part.name)
            if obj is not None and own_transform_curves(obj):
                out.append((one, part, obj))
    return out


def posed_away(rig, name):
    """Whether this bone is sitting somewhere other than its rest."""
    pose_bone = rig.pose.bones.get(name)
    if pose_bone is None:
        return False
    basis = pose_bone.matrix_basis
    return max(abs(a - b)
               for row_a, row_b in zip(basis, Matrix.Identity(4))
               for a, b in zip(row_a, row_b)) > 1e-5


def reseat_bound(data, move=None):
    """Put every bound object back on its Before, where binding left it.

    Called before anything is recorded or built, so a rig that has already
    drifted heals itself rather than staying broken for good.
    """
    moves = [move] if move is not None else list(data.moves)
    count = 0
    for one in moves:
        for part in bound_parts(one):
            obj, world = hand_moved(part)
            if obj is not None and world is not None:
                obj.matrix_world = as_matrix(part.before)
                count += 1
    return count


def recorded_for(move, part, which):
    """Whether this one part already has this end of the move saved.

    keyed_at answers for the path as a whole, which is no use when the
    question is whether *this* part would lose something by being keyed over.
    """
    frame = FIRST_FRAME if which == "BEFORE" else last_frame(move)
    _action, _slot, bag = action_bits(move)
    if bag is None:
        return False
    mine = 'pose.bones["{:s}"].'.format(
        bpy.utils.escape_identifier(part_bone(part)))
    for curve in bag.fcurves:
        if not curve.data_path.startswith(mine):
            continue
        for point in curve.keyframe_points:
            if abs(point.co[0] - frame) < 0.5:
                return True
    return False


def recorded(move, which):
    """Whether this state has been taken down, for objects or for bones."""
    loose = loose_parts(move)
    if loose:
        return all(p.has_before if which == "BEFORE" else p.has_after for p in loose)
    return keyed_at(move, FIRST_FRAME if which == "BEFORE" else last_frame(move))


def ensure_rig(context, chosen, force_new=False):
    """The rig to hang everything on, made from scratch if there is none.

    This is the whole of "the tool does the rig": pick objects, and an
    armature appears with a root over the middle of them. Nothing is bound
    yet, so the objects stay free to be moved by hand until the build.

    `force_new` is for a second machine in the same file: without it the rig
    already being worked on is reused, which is right nearly always and wrong
    the moment somebody starts something unrelated.
    """
    rig = None if force_new else rig_of(context)
    if rig is not None:
        return rig
    points = []
    for obj in chosen:
        points.extend(obj.matrix_world @ Vector(c) for c in obj.bound_box)
    if points:
        low = Vector((min(p.x for p in points), min(p.y for p in points),
                      min(p.z for p in points)))
        high = Vector((max(p.x for p in points), max(p.y for p in points),
                       max(p.z for p in points)))
        centre = Vector(((low.x + high.x) * 0.5, (low.y + high.y) * 0.5, low.z))
        reach = max((high - low).length * 0.12, 1e-3)
    else:
        centre, reach = Vector((0.0, 0.0, 0.0)), 1.0

    armature = bpy.data.armatures.new("RigMoves")
    rig = bpy.data.objects.new("RigMoves Rig", armature)
    context.collection.objects.link(rig)
    rig.show_in_front = True
    if context.object is not None and context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")
    root = armature.edit_bones.new("Root")
    root.head = centre
    root.tail = centre + Vector((0.0, 0.0, reach))
    root.use_deform = False
    bpy.ops.object.mode_set(mode="OBJECT")
    context.scene.rigmoves_rig = rig
    return rig


def seat_rig(rig, data=None):
    """Move the armature object onto the middle of the parts it drives.

    Blender draws a relationship line from every child to its *parent
    object's* origin, so an armature left at the world centre hangs a dashed
    line from every part of the model back to the middle of the scene, and
    reads as though the machine is tied to nothing. The bones move back by
    exactly what the object gains, so nothing ends up anywhere new.

    The middle is taken from the bones that actually drive something, not from
    every bone there is. A root left over where some deleted parts used to be
    would otherwise drag the whole rig half way to them.

    Skipped on a rig somebody has turned or scaled, where "move the object and
    shift the bones back" is no longer a plain subtraction.
    """
    if not len(rig.data.bones):
        return False
    turn = rig.matrix_world.to_3x3()
    if (turn - turn.Identity(3)).median_scale > 1e-6:
        return False
    driving = set()
    for move in (data.moves if data is not None else ()):
        for part in move.parts:
            driving.add(part_bone(part))
    bones = [b for b in rig.data.bones if b.name in driving] or list(rig.data.bones)
    points = []
    for bone in bones:
        points.append(rig.matrix_world @ bone.head_local)
        points.append(rig.matrix_world @ bone.tail_local)
    low = Vector((min(p.x for p in points), min(p.y for p in points),
                  min(p.z for p in points)))
    high = Vector((max(p.x for p in points), max(p.y for p in points),
                   max(p.z for p in points)))
    target = Vector(((low.x + high.x) * 0.5, (low.y + high.y) * 0.5, low.z))
    shift = target - rig.matrix_world.translation
    if shift.length < 1e-6:
        return False

    held = [(child, child.matrix_world.copy()) for child in rig.children]
    was_mode = rig.mode
    view_layer = bpy.context.view_layer
    was_active = view_layer.objects.active
    if not activate(bpy.context, rig):
        return False
    if rig.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.mode_set(mode="EDIT")
    for bone in rig.data.edit_bones:
        bone.head -= shift
        bone.tail -= shift
    # The root belongs at the middle of the machine, which is where the object
    # now is. Left where it was it would sit off in space on its own, which is
    # the same complaint as the object being at the world centre.
    root = rig.data.edit_bones.get("Root")
    if root is not None and not root.use_deform and root.parent is None:
        length = max(root.length, 1e-3)
        root.head = Vector((0.0, 0.0, 0.0))
        root.tail = Vector((0.0, 0.0, length))
    bpy.ops.object.mode_set(mode="OBJECT")
    rig.location = rig.location + shift
    bpy.context.view_layer.update()
    for child, world in held:
        child.matrix_parent_inverse = rig.matrix_world.inverted_safe()
        child.matrix_world = world
    if was_mode != "OBJECT":
        try:
            bpy.ops.object.mode_set(mode=was_mode)
        except RuntimeError:
            pass
    if was_active is not None and was_active is not rig:
        view_layer.objects.active = was_active
    return True


def bind_object(rig, obj, bone_name):
    """Tie a whole object to one bone, and let it travel with the rig.

    A vertex group at full weight rather than bone parenting: bone parenting
    hangs a child off the bone's *tail* and through its pose, which is a
    second frame of reference to keep straight for no gain on a rigid part.
    One group, one modifier, and the object's own transform is left alone.
    """
    group = obj.vertex_groups.get(bone_name) or obj.vertex_groups.new(name=bone_name)
    group.add(range(len(obj.data.vertices)), 1.0, "REPLACE")
    modifier = next((m for m in obj.modifiers
                     if m.type == "ARMATURE" and m.object is rig), None)
    if modifier is None:
        modifier = obj.modifiers.new("RigMoves", "ARMATURE")
        modifier.object = rig
    world = obj.matrix_world.copy()
    obj.parent = rig
    obj.parent_type = "OBJECT"
    obj.matrix_parent_inverse = rig.matrix_world.inverted_safe()
    obj.matrix_world = world


def pose_bone_at(rig, part, target):
    """Put a bound object's bone where the object's world matrix should be.

    The modifier moves the mesh by the bone's travel from its rest, so to land
    the object on `target` the bone has to carry exactly the difference
    between that and where the object stood when it was bound.
    """
    pose_bone = rig.pose.bones.get(part.bone_name)
    if pose_bone is None:
        return
    rest = as_matrix(part.before)
    world = rig.matrix_world
    pose_bone.matrix = (world.inverted_safe() @ target @ rest.inverted_safe()
                        @ world @ pose_bone.bone.matrix_local)


def drop_stale_bones(context, rig, data):
    """Delete bones made for objects that no move asks for any more.

    Belt and braces for the moment a move is removed while something other
    than the rig is the active object: the mode switch that deletes its bones
    would land on that other object instead, and the bones would sit there
    afterwards with nothing pointing at them.
    """
    wanted = {p.bone_name for move in data.moves for p in move.parts
              if p.kind == "OBJECT" and p.bone_name}
    stale = [b.name for b in rig.data.bones
             if b.get(PART_MARK) and b.name not in wanted]
    if not stale:
        return 0
    view_layer = context.view_layer
    was_active, was_mode = view_layer.objects.active, rig.mode
    if not activate(context, rig):
        return 0
    if rig.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.mode_set(mode="EDIT")
    for name in stale:
        bone = rig.data.edit_bones.get(name)
        if bone is not None:
            rig.data.edit_bones.remove(bone)
    bpy.ops.object.mode_set(mode="OBJECT")
    if was_mode != "OBJECT":
        try:
            bpy.ops.object.mode_set(mode=was_mode)
        except RuntimeError:
            pass
    if was_active is not None and was_active is not rig:
        view_layer.objects.active = was_active
    return len(stale)


def bind_loose(context, rig, data):
    """Give every loose object a bone, bind it, and write its two poses."""
    jobs = []
    for move in data.moves:
        pending = [p for p in loose_parts(move) if p.has_before]
        if pending:
            jobs.append((move, pending))
    if not jobs:
        return 0

    if not activate(context, rig):
        return 0
    # Stand every object where Before was recorded, so its bone is made there
    # and that pose becomes the rig's rest.
    for _move, pending in jobs:
        for part in pending:
            obj = bpy.data.objects.get(part.name)
            if obj is not None:
                obj.matrix_world = as_matrix(part.before)
    context.view_layer.update()

    if not activate(context, rig):
        return 0
    bpy.ops.object.mode_set(mode="EDIT")
    edit = rig.data.edit_bones
    root = edit.get("Root") or (edit[0] if len(edit) else None)
    into = rig.matrix_world.inverted_safe()
    reach = max(rig_reach(rig) * 0.12, 1e-3)
    for _move, pending in jobs:
        for part in pending:
            obj = bpy.data.objects.get(part.name)
            if obj is None:
                continue
            bone = edit.new(obj.name)
            head = into @ obj.matrix_world.translation
            bone.head = head
            bone.tail = head + Vector((0.0, 0.0, reach))
            bone.use_deform = True
            bone.parent = root if (root is not None and root.name != bone.name) else None
            part.bone_name = bone.name
    bpy.ops.object.mode_set(mode="OBJECT")

    made = 0
    for _move, pending in jobs:
        for part in pending:
            obj = bpy.data.objects.get(part.name)
            if obj is not None:
                bind_object(rig, obj, part.bone_name)
                made += 1
            # Stamped, so a bone this add-on made for an object can be told
            # from one somebody put there by hand, and swept when its move is
            # gone. Without the stamp the only clue is the name, which is a
            # guess on a rig that has bones of its own.
            bone = rig.data.bones.get(part.bone_name)
            if bone is not None:
                bone[PART_MARK] = True
    context.view_layer.update()

    # Before is the rest pose, so it keys with the bones untouched; After is
    # the difference the object was moved by.
    for move, pending in jobs:
        names = {p.bone_name for p in pending}
        for part in pending:
            pose_bone = rig.pose.bones.get(part.bone_name)
            if pose_bone is not None:
                pose_bone.matrix_basis = Matrix()
        context.view_layer.update()
        key_pose(rig, move, FIRST_FRAME, only=names)
        for part in pending:
            if part.has_after:
                pose_bone_at(rig, part, as_matrix(part.after))
        context.view_layer.update()
        key_pose(rig, move, last_frame(move), only=names)
        for part in pending:
            pose_bone = rig.pose.bones.get(part.bone_name)
            if pose_bone is not None:
                pose_bone.matrix_basis = Matrix()
    context.view_layer.update()
    return made


def armatures_in(context):
    return [o for o in context.view_layer.objects if o.type == "ARMATURE"]


def default_control(rig):
    for bone in rig.pose.bones:
        if bone.parent is None:
            return bone.name
    return rig.pose.bones[0].name if len(rig.pose.bones) else ""


def our_constraints(rig, move=None):
    """Every Action constraint this add-on made, as (pose_bone, constraint).

    For one move, by the name its last build really used. Matching on the
    move's current name instead would lose every constraint the moment the
    move was renamed, stranding them on the rig with nothing to remove them.
    """
    wanted = (move.con_name or CONSTRAINT + move.name) if move is not None else None
    found = []
    for pose_bone in rig.pose.bones:
        for constraint in pose_bone.constraints:
            if constraint.type != "ACTION" or not constraint.name.startswith(CONSTRAINT):
                continue
            if wanted is not None and constraint.name != wanted:
                continue
            found.append((pose_bone, constraint))
    return found


def set_paused(rig, data, paused):
    touched = 0
    for _bone, constraint in our_constraints(rig):
        constraint.mute = paused
        touched += 1
    data.posing = bool(paused and touched)
    rig.update_tag()
    return touched


# ---------------------------------------------------------------------------
# the driver that scrubs a move's path
#
#   slider  ->  0..1 across the move's range
#           ->  this part's own window, so it can start late or arrive early
#           ->  eased
#           ->  the Action constraint's evaluation time


EASE = {
    "LINEAR": "{t}",
    "SMOOTH": "({t})*({t})*(3-2*({t}))",
    "IN": "({t})*({t})",
    "OUT": "({t})*(2-({t}))",
}


def window(inner, start, end):
    """Clamp a 0..1 number into somebody's own slice of the travel.

    Written as short as it can be said. A driver expression is held in a fixed
    string, and Blender cuts anything longer off where it stands rather than
    complaining - which leaves an unclosed bracket, a driver that reads as a
    syntax error, and a part that simply never moves. Easing repeats this
    whole expression three times, so every character saved here is saved three
    times over, and ten-digit floats printed as 0.200000003 were most of it.
    """
    start = max(0.0, min(0.98, start))
    end = max(start + 0.01, min(1.0, end))
    if start <= 1e-6 and end >= 1.0 - 1e-6:
        # No slice to take, but the clamp still earns its place: the control
        # itself can be dragged past either end.
        return "min(max({:s},0),1)".format(inner)
    # start and the span are both positive by the clamps above, so neither
    # needs brackets of its own to keep a minus sign apart from a minus.
    return "min(max(({:s}-{:.6g})/{:.6g},0),1)".format(inner, start, end - start)


def scaled(name, low, span):
    """A control's reading as 0..1, with nothing written that does nothing."""
    if abs(low) < 1e-9 and abs(span - 1.0) < 1e-9:
        return name
    return "(({:s}-({:.6g}))/({:.6g}))".format(name, low, span)


def travels_to_end(thing):
    """Everything runs to the end of its control now.

    A separate "arrives early and then waits" number was one more thing to
    explain for something nobody reached for; a delay on its own says what an
    animator means. The property is still here so setups made while it existed
    still load, but it is not read and not shown.
    """
    return 1.0


def eval_expression(data, move, part):
    """How far through its path this part is, for the driver.

    Three things fold together, in this order:

      the move's own control, 0 to 1 across its range;
      the combined control it belongs to, if any, through this move's delay
        window - whichever of the two is further along wins, so a move can be
        played on its own or as part of a sequence without one blocking the
        other;
      the part's own delay window inside the move, then the easing.
    """
    # No clamping on the way in. Everything from here to the last window is
    # monotonic, and that last window clamps - so an inner min/max can only
    # repeat what it already does. They are not free: easing writes this whole
    # expression three times, and Blender cuts one over 256 characters off
    # mid-bracket without a word.
    span = (move.high - move.low) or 1.0
    own = scaled(VAR, move.low, span)
    group, member = group_of(data, move)
    if group is not None:
        reach = (group.high - group.low) or 1.0
        own = "max({:s},{:s})".format(
            own, window(scaled(GROUP_VAR, group.low, reach),
                        member.start, travels_to_end(member)))
    return EASE.get(move.ease, "{t}").replace(
        "{t}", window(own, part.start, travels_to_end(part)))


# ---------------------------------------------------------------------------
# operators


class RIGMOVES_OT_new_move(bpy.types.Operator):
    bl_idname = "rigmoves.new_move"
    bl_label = "New Move"
    bl_description = ("Start a move from the bones selected in pose mode. Where "
                      "they stand now is recorded as Before")
    bl_options = {"REGISTER", "UNDO"}
    fresh: bpy.props.BoolProperty(
        default=False,
        description="Start a rig of its own rather than adding to the one "
                    "already being worked on")

    @classmethod
    def poll(cls, context):
        if context.selected_pose_bones:
            return rig_of(context) is not None
        return any(o.type == "MESH" for o in context.selected_objects)

    def execute(self, context):
        forget_dead_rig(context)
        # Bones if some are selected in pose mode; otherwise the objects that
        # are selected, and the rig gets made for them.
        chosen_bones = list(context.selected_pose_bones or [])
        chosen_objects = [o for o in context.selected_objects if o.type == "MESH"]
        if chosen_bones:
            rig = rig_of(context)
        else:
            rig = ensure_rig(context, chosen_objects, force_new=self.fresh)
        if rig is None:
            return {"CANCELLED"}
        data = rig.rigmoves
        move = data.moves.add()
        move.name = "Move {:d}".format(len(data.moves))
        move.prop = unique_prop_name(rig, move, safe_prop_name(move.name))
        move.control = default_control(rig)
        # An action outlives the rig it was made for: they are kept by a fake
        # user so a path is not thrown away when the file is saved. So a name
        # worked out from the rig's is not free for the taking - a new rig
        # that lands on a deleted one's name would pick up its old action and
        # start life with somebody else's path already keyed onto it.
        base = "RigMoves {:s} {:s}".format(rig.name, move.name)
        name, tries = base, 1
        while bpy.data.actions.get(name) is not None:
            tries += 1
            name = "{:s} {:d}".format(base, tries)
        move.action_name = name
        for pose_bone in chosen_bones:
            move.parts.add().name = pose_bone.name
        for obj in chosen_objects:
            part = move.parts.add()
            part.name = obj.name
            part.kind = "OBJECT"
        data.active = len(data.moves) - 1
        bpy.ops.rigmoves.record(index=data.active, which="BEFORE")
        data.report = ("'{:s}': {:d} part(s). Where they stand now is Before. "
                       "Move them, then Record After."
                       .format(move.name, len(move.parts)))
        self.report({"INFO"}, data.report)
        return {"FINISHED"}


def newcomers(context, rig):
    """Selected meshes this rig has never been told about."""
    if rig is None:
        return []
    known = {p.name for move in rig.rigmoves.moves for p in move.parts}
    return [o for o in context.selected_objects
            if o.type == "MESH" and o.name not in known and o is not rig]


def rig_label(rig):
    """A rig's name, short enough to sit on a button beside a move's."""
    name = rig.name
    return name[len("RigMoves "):] if name.startswith("RigMoves ") else name


def working_rigs(context):
    """Every rig of ours the user can actually see and use.

    A rig whose parts were deleted, or that never bound anything, is still an
    object in the file and goes on answering questions about its moves. Those
    would otherwise crowd this list with places nothing can usefully go, which
    is worse than not offering a choice at all.
    """
    out = []
    for obj in context.view_layer.objects:
        if obj.type != "ARMATURE":
            continue
        data = getattr(obj, "rigmoves", None)
        if data is None or not len(data.moves):
            continue
        if len(obj.children) or any(p.kind != "OBJECT"
                                    for m in data.moves for p in m.parts):
            out.append(obj)
    return out


def join_targets(context, current):
    """Every group a newcomer could be put into, as (rig, index, move).

    The panel shows one rig at a time, but the user is looking at a viewport
    where each cluster of parts reads as a group whatever armature happens to
    hold it. Offering only the shown rig's groups means the one they are
    pointing at may not be on the list at all.
    """
    out = []
    if current is not None and here(context, current):
        out.extend((current, i, m) for i, m in enumerate(current.rigmoves.moves))
    for rig in working_rigs(context):
        if rig is current:
            continue
        out.extend((rig, i, m) for i, m in enumerate(rig.rigmoves.moves))
    return out


def held(context, move):
    """Which of a move's parts the user has hold of in the viewport.

    The delay list is the one place where a row has to be matched to a thing
    on screen, and the names are long and alike - four lids off one machine
    differ in their last character. Reading the selection means the answer is
    already there: pick the part, and its row is the lit one.
    """
    chosen = {o.name for o in context.selected_objects}
    bones = {b.name for b in (context.selected_pose_bones or [])}
    return {part.name for part in move.parts
            if part.name in chosen or part_bone(part) in bones}


def indicated(context, rig):
    """The groups the selection points at, as (index, move).

    Selecting a newcomer on its own says "this is something new". Selecting it
    together with a part of an existing group - or with that group's handle -
    says "this belongs with those", and that is the whole of how the target is
    chosen. No menu of every group on the rig: the selection already said it.
    """
    if rig is None:
        return []
    chosen = {o.name for o in context.selected_objects}
    found = [(index, move) for index, move in enumerate(rig.rigmoves.moves)
             if any(part.name in chosen for part in move.parts)]
    if found:
        return found
    bones = {b.name for b in (context.selected_pose_bones or [])}
    if not bones:
        return []
    return [(index, move) for index, move in enumerate(rig.rigmoves.moves)
            if (move.handle_name and move.handle_name in bones)
            or any(part_bone(part) in bones for part in move.parts)]


class RIGMOVES_OT_add_to_move(bpy.types.Operator):
    bl_idname = "rigmoves.add_to_move"
    bl_label = "Add To This Move"
    bl_description = ("Put the selected objects into this move as well. Where "
                      "they stand now is their Before")
    bl_options = {"REGISTER", "UNDO"}
    index: bpy.props.IntProperty()
    rig_name: bpy.props.StringProperty(
        default="",
        description="The rig holding the group to join. Empty means the one "
                    "the panel is showing")

    def execute(self, context):
        rig = bpy.data.objects.get(self.rig_name) if self.rig_name else None
        if rig is None:
            rig = rig_of(context)
        if not here(context, rig) or rig.type != "ARMATURE":
            return {"CANCELLED"}
        data = rig.rigmoves
        if not 0 <= self.index < len(data.moves):
            return {"CANCELLED"}
        move = data.moves[self.index]
        fresh = newcomers(context, rig)
        if not fresh:
            data.report = "Nothing selected that is not already in this rig."
            self.report({"WARNING"}, data.report)
            return {"CANCELLED"}
        # Joining a group on another rig moves the panel over to it, or the
        # next thing the user presses would land back on the rig they left.
        if getattr(context.scene, "rigmoves_rig", None) is not rig:
            context.scene.rigmoves_rig = rig
        # Everything already in this move is being held by its constraints, so
        # they go quiet while the newcomers are measured.
        set_paused(rig, data, True)
        for obj in fresh:
            part = move.parts.add()
            part.name = obj.name
            part.kind = "OBJECT"
            part.before = flat(obj.matrix_world)
            part.has_before = True
        data.report = ("{:d} object(s) added to '{:s}', where they stand now. "
                       "Press the eye beside After, put them where they should "
                       "end up, then Record After."
                       .format(len(fresh), move.name))
        self.report({"INFO"}, data.report)
        return {"FINISHED"}


class RIGMOVES_OT_pick_part(bpy.types.Operator):
    bl_idname = "rigmoves.pick_part"
    bl_label = "Select this part"
    bl_description = ("Select this part in the viewport, so which row belongs "
                      "to which piece needs no reading")
    bl_options = {"REGISTER", "UNDO"}
    index: bpy.props.IntProperty()
    part: bpy.props.IntProperty()

    def execute(self, context):
        rig = rig_of(context)
        if not here(context, rig):
            return {"CANCELLED"}
        data = rig.rigmoves
        if not 0 <= self.index < len(data.moves):
            return {"CANCELLED"}
        move = data.moves[self.index]
        if not 0 <= self.part < len(move.parts):
            return {"CANCELLED"}
        part = move.parts[self.part]

        # A bone part can be picked without leaving pose mode, and an object
        # part cannot be picked inside it. Changing somebody's mode out from
        # under them to answer a question about a list would be its own kind
        # of rude, so it is asked for rather than done.
        if part.kind != "OBJECT":
            if context.mode != "POSE":
                data.report = "Go into pose mode on the rig to pick '{:s}'.".format(
                    short(part.name, 20))
                self.report({"WARNING"}, data.report)
                return {"CANCELLED"}
            for pose_bone in rig.pose.bones:
                pose_bone.bone.select = pose_bone.name == part_bone(part)
            rig.data.bones.active = rig.data.bones.get(part_bone(part))
            data.report = "Selected '{:s}'.".format(short(part.name, 24))
            return {"FINISHED"}

        if context.mode != "OBJECT":
            data.report = "Leave pose mode to pick '{:s}'.".format(
                short(part.name, 20))
            self.report({"WARNING"}, data.report)
            return {"CANCELLED"}
        obj = bpy.data.objects.get(part.name)
        if obj is None or obj.name not in context.view_layer.objects:
            data.report = "'{:s}' is not in this scene any more.".format(
                short(part.name, 24))
            self.report({"WARNING"}, data.report)
            return {"CANCELLED"}
        for other in context.selected_objects:
            other.select_set(False)
        obj.select_set(True)
        context.view_layer.objects.active = obj
        data.report = "Selected '{:s}'.".format(short(part.name, 24))
        return {"FINISHED"}


class RIGMOVES_OT_free_keys(bpy.types.Operator):
    bl_idname = "rigmoves.free_keys"
    bl_label = "Lift Their Own Keyframes"
    bl_description = ("Take the transform keyframes off the parts themselves, "
                      "so the rig is what moves them. Their other keyframes, "
                      "and every other object, are left alone")
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        rig = rig_of(context)
        if not here(context, rig):
            return {"CANCELLED"}
        data = rig.rigmoves
        objects, bones, still_keyed = clear_autokey(rig, data)
        if not (objects or bones):
            data.report = "Nothing is carrying stray keyframes."
            self.report({"INFO"}, data.report)
            return {"CANCELLED"}

        # With the keys gone the rest can finally be put where it belongs.
        put_back = reseat_bound(data)
        context.view_layer.update()
        data.report = ("{:d} keyframe track(s) lifted off the parts, {:d} off "
                       "the rig.".format(objects, bones))
        if still_keyed:
            data.report += (" {:s} is animated by hand and was left alone."
                            .format(", ".join(still_keyed[:3])))
        if put_back:
            data.report += (" {:d} put back on its Before.".format(put_back)
                            if put_back == 1 else
                            " {:d} put back on their Before.".format(put_back))
        data.report += " Build to finish."
        self.report({"INFO"}, data.report)
        return {"FINISHED"}


class RIGMOVES_OT_use_selected(bpy.types.Operator):
    bl_idname = "rigmoves.use_selected"
    bl_label = "Use Selected Bones"
    bl_description = "Replace this move's parts with the bones selected now"
    bl_options = {"REGISTER", "UNDO"}
    index: bpy.props.IntProperty()

    @classmethod
    def poll(cls, context):
        return bool(context.selected_pose_bones)

    def execute(self, context):
        rig = rig_of(context)
        data = rig.rigmoves
        move = data.moves[self.index]
        taken = [b.name for b in context.selected_pose_bones]
        # Keep the timing already set for parts that stay in.
        timing = {p.name: (p.start, p.kind, p.bone_name) for p in move.parts}
        move.parts.clear()
        for name in taken:
            part = move.parts.add()
            part.name = name
            if name in timing:
                part.start, part.kind, part.bone_name = timing[name]
        # Curves for bones that no longer take part would replay channels
        # nobody asked for, so they go with them.
        _action, _slot, bag = action_bits(move)
        if bag is not None:
            keep = [bone_path(part_bone(p), "") for p in move.parts]
            for curve in list(bag.fcurves):
                if not any(curve.data_path.startswith(k) for k in keep):
                    bag.fcurves.remove(curve)
        data.report = "'{:s}': {:d} part(s). Record Before and After again.".format(
            move.name, len(taken))
        return {"FINISHED"}


class RIGMOVES_OT_record(bpy.types.Operator):
    bl_idname = "rigmoves.record"
    bl_label = "Record"
    bl_description = "Remember where every part of this move is standing right now"
    bl_options = {"REGISTER", "UNDO"}
    index: bpy.props.IntProperty()
    which: bpy.props.EnumProperty(
        items=[("BEFORE", "Before", ""), ("AFTER", "After", ""),
               ("STEP", "Step", "")], default="BEFORE")
    step: bpy.props.IntProperty(default=-1)

    def execute(self, context):
        rig = rig_of(context)
        data = rig.rigmoves
        if not 0 <= self.index < len(data.moves):
            return {"CANCELLED"}
        move = data.moves[self.index]
        if not len(move.parts):
            data.report = "'{:s}': no parts yet.".format(move.name)
            self.report({"WARNING"}, data.report)
            return {"CANCELLED"}

        # A bone under a live Action constraint cannot be posed - the
        # constraint writes it again on every update - so what is on screen
        # would not be what gets recorded. Switch ours off first and say so,
        # rather than quietly saving a pose nobody set.
        paused = set_paused(rig, data, True)
        step = None
        if self.which == "STEP":
            if not 0 <= self.step < len(move.steps):
                return {"CANCELLED"}
            step = move.steps[self.step]
            frame = step.frame
        else:
            frame = FIRST_FRAME if self.which == "BEFORE" else last_frame(move)
        count = 0

        # A part that is already bound can still be posed the way it was the
        # first time - by dragging the object itself - and that has to mean
        # the same thing it meant then. Its bone is put where the object is
        # standing and the object goes back to its Before, which is the rest
        # the modifier measures from. Without this the drag is read as nothing
        # at all: the bone is at rest, so After gets saved as "no change",
        # while the object's own rest has moved to where it was dropped. The
        # slider then starts at the wrong end and travels twice as far.
        dragged, touched = 0, set()
        for part in bound_parts(move):
            obj, world = hand_moved(part)
            if world is None:
                continue
            touched.add(part_bone(part))
            obj.matrix_world = as_matrix(part.before)
            if self.which == "AFTER":
                part.after = flat(world)
                part.has_after = True
            context.view_layer.update()
            pose_bone_at(rig, part, world)
            dragged += 1
        if dragged:
            context.view_layer.update()

        # Objects with no bone yet are read straight off the object, which is
        # the point: they are moved by hand in object mode, not posed.
        loose = loose_parts(move) if self.which != "STEP" else []
        for part in loose:
            obj = bpy.data.objects.get(part.name)
            if obj is None:
                continue
            if self.which == "BEFORE":
                part.before = flat(obj.matrix_world)
                part.has_before = True
            else:
                part.after = flat(obj.matrix_world)
                part.has_after = True
            count += 1
        # Only what was actually touched this time. A part already in the
        # group is standing at its Before, because that is where the build
        # puts it - so keying the lot would save "no change" over the motion
        # it already had and quietly flatten it. That is what happens the
        # moment somebody adds a part to a finished group and records: every
        # part that was working stops working, with nothing said.
        loose_names = {p.name for p in loose}
        bones, kept = set(), 0
        for part in move.parts:
            if part.name in loose_names and not part.bone_name:
                continue
            name = part_bone(part)
            if part.kind != "OBJECT":
                # Bones are posed by hand in pose mode, where whatever they
                # are showing is the answer - including being put back to rest.
                bones.add(name)
            elif name in touched or posed_away(rig, name):
                bones.add(name)
            elif not recorded_for(move, part, self.which):
                bones.add(name)
            else:
                kept += 1
        if bones:
            count += key_pose(rig, move, frame, only=bones)
        move.frames_applied = max(1, move.frames)
        if step is not None:
            if not count:
                data.report = ("Nothing was moved, so there is nothing to save "
                               "for this step. Drag the parts where they should "
                               "be part way through, then press Record.")
                self.report({"WARNING"}, data.report)
                return {"CANCELLED"}
            step.done = True

        said = ("Step {:d}".format(self.step + 1) if step is not None
                else self.which.title())
        data.report = "'{:s}': {:s} recorded for {:d} part(s).".format(
            move.name, said, count)
        if dragged:
            data.report += (" {:d} moved by hand, read as a pose."
                            .format(dragged))
        if kept:
            data.report += (" 1 left as it was - nothing moved it."
                            if kept == 1 else
                            " {:d} left as they were - nothing moved them."
                            .format(kept))
        if paused:
            data.report += " Sliders paused while you pose - Build puts them back."
        self.report({"INFO"}, data.report)
        return {"FINISHED"}


class RIGMOVES_OT_show(bpy.types.Operator):
    bl_idname = "rigmoves.show"
    bl_label = "Show"
    bl_description = "Put the bones back into this recorded pose, to check it"
    bl_options = {"REGISTER", "UNDO"}
    index: bpy.props.IntProperty()
    which: bpy.props.EnumProperty(
        items=[("BEFORE", "Before", ""), ("AFTER", "After", ""),
               ("STEP", "Step", "")], default="BEFORE")
    step: bpy.props.IntProperty(default=-1)

    def execute(self, context):
        rig = rig_of(context)
        data = rig.rigmoves
        move = data.moves[self.index]
        set_paused(rig, data, True)
        # Anything dragged since the build is standing off its rest, so the
        # pose would be shown measured from the wrong place.
        reseat_bound(data, move)
        context.view_layer.update()
        if self.which == "STEP":
            if not 0 <= self.step < len(move.steps):
                return {"CANCELLED"}
            pose_at(rig, move, move.steps[self.step].frame)
            context.view_layer.update()
            data.report = ("Showing '{:s}' at step {:d}. Build puts the "
                           "sliders back.".format(move.name, self.step + 1))
            return {"FINISHED"}
        for part in loose_parts(move):
            obj = bpy.data.objects.get(part.name)
            done = part.has_before if self.which == "BEFORE" else part.has_after
            if obj is not None and done:
                obj.matrix_world = as_matrix(
                    part.before if self.which == "BEFORE" else part.after)
        pose_at(rig, move, FIRST_FRAME if self.which == "BEFORE" else last_frame(move))
        context.view_layer.update()
        data.report = "Showing '{:s}' at {:s}. Build puts the sliders back.".format(
            move.name, self.which.title())
        return {"FINISHED"}


class RIGMOVES_OT_add_step(bpy.types.Operator):
    bl_idname = "rigmoves.add_step"
    bl_label = "Add a step in between"
    bl_description = ("Put another pose between Before and After. It arrives "
                      "empty, with a Record of its own - move the parts where "
                      "you want them part way through, then press it")
    bl_options = {"REGISTER", "UNDO"}
    index: bpy.props.IntProperty()

    def execute(self, context):
        rig = rig_of(context)
        if not here(context, rig):
            return {"CANCELLED"}
        data = rig.rigmoves
        if not 0 <= self.index < len(data.moves):
            return {"CANCELLED"}
        move = data.moves[self.index]
        move.steps.add()
        respace_steps(move)
        set_paused(rig, data, True)
        data.report = ("'{:s}': step {:d} added. Put the parts where they "
                       "should be part way through, then press its Record."
                       .format(move.name, len(move.steps)))
        self.report({"INFO"}, data.report)
        return {"FINISHED"}


class RIGMOVES_OT_drop_step(bpy.types.Operator):
    bl_idname = "rigmoves.drop_step"
    bl_label = "Remove this step"
    bl_description = "Take this in-between pose off the path"
    bl_options = {"REGISTER", "UNDO"}
    index: bpy.props.IntProperty()
    step: bpy.props.IntProperty()

    def execute(self, context):
        rig = rig_of(context)
        if not here(context, rig):
            return {"CANCELLED"}
        data = rig.rigmoves
        if not 0 <= self.index < len(data.moves):
            return {"CANCELLED"}
        move = data.moves[self.index]
        if not 0 <= self.step < len(move.steps):
            return {"CANCELLED"}
        step = move.steps[self.step]
        if step.done:
            drop_keys_at(move, step.frame)
        move.steps.remove(self.step)
        respace_steps(move)
        data.report = "Step removed from '{:s}'. Build to play it.".format(move.name)
        self.report({"INFO"}, data.report)
        return {"FINISHED"}


class RIGMOVES_OT_build(bpy.types.Operator):
    bl_idname = "rigmoves.build"
    bl_label = "Build Sliders"
    bl_description = ("Make one slider per move and put every part on the "
                      "recorded path, each with its own delay")
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        rig = rig_of(context)
        if not here(context, rig):
            if rig is not None:
                self.report({"WARNING"},
                            "'{:s}' is not in this scene any more. Select the "
                            "objects and start a new move.".format(rig.name))
            return {"CANCELLED"}
        data = rig.rigmoves
        if not len(data.moves):
            return {"CANCELLED"}

        # Loose objects first: each gets a bone, gets bound to it, and has its
        # two recorded placements written into the move's path. After this a
        # move that started from objects is no different from one recorded on
        # bones, and everything below treats them alike.
        drop_stale_bones(context, rig, data)
        # First, because everything under it is undone by a keyframe: with
        # Auto Keying on, every drag this tool asks for leaves one behind, and
        # they hold the parts and the handles where the rig cannot move them.
        keyed_objects, keyed_bones, still_keyed = clear_autokey(rig, data)
        if keyed_objects or keyed_bones:
            context.view_layer.update()
        # Bound objects belong on their Before: that is the rest every slider
        # is measured from, and a rig where one has been nudged off it plays
        # the move from the wrong end. Putting them back here means a rig that
        # has already gone wrong comes right on the next Build.
        reseated = reseat_bound(data)
        if reseated:
            context.view_layer.update()
        bound = bind_loose(context, rig, data)

        # Every move needs a stable name of its own, because a combined
        # control refers to its members by one - names change, this does not.
        for move in data.moves:
            if not move.uid:
                move.uid = "m{:d}".format(data.next_uid)
                data.next_uid += 1

        # The sliders: one custom property per move and per combined control,
        # on whichever bone it names.
        for carrier, _names in carriers(data):
            ensure_slider(rig, carrier)

        # Handles: make, move or unmake them, then hand each one its rail and
        # let it write its own slider. Anything with no handle has that driver
        # taken off again, so its slider goes back to being draggable in the
        # panel.
        sync_handles(rig, data)
        for carrier, _names in carriers(data):
            if carrier.handle:
                dress_handle(rig, carrier)
            drive_property_from_handle(rig, carrier)
        for group in data.groups:
            group.built = True

        # Start from nothing of ours, so a part taken out of a move does not
        # keep a constraint the panel no longer shows.
        for pose_bone, constraint in our_constraints(rig):
            pose_bone.constraints.remove(constraint)

        made, empty, cramped = 0, [], []
        for move in data.moves:
            action, slot, bag = action_bits(move)
            if bag is None or not len(bag.fcurves):
                empty.append(move.name)
                continue
            for part in move.parts:
                pose_bone = rig.pose.bones.get(part_bone(part))
                if pose_bone is None:
                    continue
                # How many of ours are already on this bone decides both the
                # mix and where in the stack this one goes.
                already = sum(1 for c in pose_bone.constraints
                              if c.type == "ACTION" and c.name.startswith(CONSTRAINT))
                constraint = pose_bone.constraints.new("ACTION")
                constraint.name = CONSTRAINT + move.name
                # Read it back: Blender will have made it unique if another
                # constraint on this bone already had that name.
                move.con_name = constraint.name
                constraint.action = action
                try:
                    constraint.action_slot = slot
                except Exception:
                    pass
                constraint.use_eval_time = True
                constraint.frame_start = FIRST_FRAME
                constraint.frame_end = last_frame(move)
                # The first move on a part sets its pose; any move after it
                # composes on top, so two moves sharing a part add up instead
                # of the second wiping out the first.
                constraint.mix_mode = "REPLACE" if not already else "AFTER"
                # At the top of the stack: whatever the bone already carried
                # then runs on top of the path, exactly as it ran on top of a
                # pose put in by hand.
                pose_bone.constraints.move(len(pose_bone.constraints) - 1, already)

                curve = rig.driver_add(
                    'pose.bones["{:s}"].constraints["{:s}"].eval_time'.format(
                        bpy.utils.escape_identifier(part_bone(part)),
                        bpy.utils.escape_identifier(constraint.name)))
                # A fresh driver curve can arrive carrying a Generator
                # modifier, and a modifier overrides the expression outright.
                # That is the classic "my driver always reads zero".
                for modifier in list(curve.modifiers):
                    curve.modifiers.remove(modifier)
                driver = curve.driver
                driver.type = "SCRIPTED"
                for variable in list(driver.variables):
                    driver.variables.remove(variable)
                add_slider_variable(driver, rig, VAR, move.control, move.prop)
                group, _member = group_of(data, move)
                if group is not None:
                    add_slider_variable(driver, rig, GROUP_VAR,
                                        group.control, group.prop)
                wanted = eval_expression(data, move, part)
                driver.expression = wanted
                # Blender holds an expression in a fixed string and cuts a
                # long one off where it stands, with no complaint - the driver
                # then fails to parse and the part never moves. Reading it
                # back is the only way to know it all arrived.
                if driver.expression != wanted:
                    cramped.append(part_bone(part))
                made += 1
            move.built = True

        set_paused(rig, data, False)
        # The wire box these handles used to wear kept a fake user, so it
        # would sit in the file for ever once nothing wore it.
        stale_shape = bpy.data.objects.get("RM_handle_shape")
        if stale_shape is not None and not any(
                pb.custom_shape is stale_shape
                for arm in bpy.data.objects if arm.type == "ARMATURE"
                for pb in arm.pose.bones):
            mesh = stale_shape.data
            bpy.data.objects.remove(stale_shape, do_unlink=True)
            if mesh is not None and mesh.users == 0:
                bpy.data.meshes.remove(mesh)

        # Drawn over the mesh, or a handle standing inside the machine - which
        # is where it belongs - would be buried in it.
        rig.show_in_front = True

        # Last of all, so it takes in every bone this build made.
        seat_rig(rig, data)
        rig.update_tag()
        context.view_layer.update()

        if not made:
            data.report = "Nothing recorded yet. Record Before and After, then Build."
            self.report({"WARNING"}, data.report)
            return {"FINISHED"}
        data.report = "{:d} part(s) on {:d} slider(s).".format(made, len(data.moves))
        if bound:
            data.report += " {:d} object(s) were given a bone and bound.".format(bound)
        if reseated:
            data.report += (" {:d} put back on its Before.".format(reseated)
                            if reseated == 1 else
                            " {:d} put back on their Before.".format(reseated))
        if keyed_objects or keyed_bones:
            data.report += (" Auto Keying had left {:d} keyframe track(s) on "
                            "the parts and {:d} on the rig; both were lifted, "
                            "or the rig could not move them."
                            .format(keyed_objects, keyed_bones))
        if still_keyed:
            data.report += (" {:s} is animated by hand and was left as it is."
                            .format(", ".join(still_keyed[:3])))
            self.report({"WARNING"}, data.report)
            return {"FINISHED"}
        if empty:
            data.report += " Nothing recorded for: " + ", ".join(empty[:3])
        if cramped:
            data.report += (" The driver for {:s} was too long for Blender to "
                            "hold and got cut short. Use fewer delays, or Even "
                            "speed, on this move."
                            .format(", ".join(sorted(set(cramped))[:3])))
            self.report({"WARNING"}, data.report)
            return {"FINISHED"}
        self.report({"INFO"}, data.report)
        return {"FINISHED"}


class RIGMOVES_OT_pause(bpy.types.Operator):
    bl_idname = "rigmoves.pause"
    bl_label = "Pause"
    bl_description = "Switch the sliders off so the bones can be posed by hand again"
    bl_options = {"REGISTER", "UNDO"}
    off: bpy.props.BoolProperty(default=True)

    def execute(self, context):
        rig = rig_of(context)
        count = set_paused(rig, rig.rigmoves, self.off)
        context.view_layer.update()
        rig.rigmoves.report = "{:d} part(s) {:s}.".format(
            count, "paused - pose freely, then Build" if self.off else "live again")
        return {"FINISHED"}


class RIGMOVES_OT_reset(bpy.types.Operator):
    bl_idname = "rigmoves.reset"
    bl_label = "To Before"
    bl_description = "Put every slider back to its Before end"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        rig = rig_of(context)
        for carrier, _names in carriers(rig.rigmoves):
            # With a handle the slider is driven and cannot be written to, so
            # the handle is what gets put back.
            handle = rig.pose.bones.get(carrier.handle_name) if carrier.handle else None
            if handle is not None:
                handle.location.y = 0.0
                continue
            bone = rig.pose.bones.get(carrier.control)
            if bone is not None and carrier.prop in bone.keys():
                bone[carrier.prop] = float(carrier.low)
        rig.update_tag()
        context.view_layer.update()
        return {"FINISHED"}


class RIGMOVES_OT_remove(bpy.types.Operator):
    bl_idname = "rigmoves.remove"
    bl_label = "Remove"
    bl_description = ("Delete this move, its slider, its path and its "
                      "constraints. The rig is left as it was")
    bl_options = {"REGISTER", "UNDO"}
    index: bpy.props.IntProperty()

    def execute(self, context):
        rig = rig_of(context)
        data = rig.rigmoves
        if not 0 <= self.index < len(data.moves):
            return {"CANCELLED"}
        move = data.moves[self.index]
        gone = []
        for pose_bone, constraint in our_constraints(rig, move):
            pose_bone.constraints.remove(constraint)
        # Objects this move bound get their freedom back: the group, the
        # modifier and the parent all go, and they stay exactly where they are.
        for part in move.parts:
            if part.kind != "OBJECT" or not part.bone_name:
                continue
            obj = bpy.data.objects.get(part.name)
            if obj is None:
                continue
            world = obj.matrix_world.copy()
            for modifier in list(obj.modifiers):
                if modifier.type == "ARMATURE" and modifier.object is rig:
                    obj.modifiers.remove(modifier)
            group = obj.vertex_groups.get(part.bone_name)
            if group is not None:
                obj.vertex_groups.remove(group)
            if obj.parent is rig:
                obj.parent = None
            obj.matrix_world = world
            gone.append(part.bone_name)
        # The handle's driver goes with the slider it writes. Left behind it
        # points at a property that is gone and a handle about to be, and
        # Blender complains about it on every update from then on.
        rig.driver_remove(property_path(move.control, move.prop))
        bone = rig.pose.bones.get(move.control)
        if bone is not None and move.prop in bone.keys():
            del bone[move.prop]
        action = bpy.data.actions.get(move.action_name) if move.action_name else None
        # Out of any combined control that was playing it, first: a member
        # pointing at a move that is gone would draw as a blank row.
        for group in data.groups:
            for position in reversed(range(len(group.members))):
                if group.members[position].uid == move.uid:
                    group.members.remove(position)
        data.moves.remove(self.index)
        data.active = max(0, min(data.active, len(data.moves) - 1))
        if action is not None and action.users <= 1:
            bpy.data.actions.remove(action)
        # Its handle bone is now nobody's, so it goes too. Done here as well as
        # in the build, because removing the last move never rebuilds.
        sync_handles(rig, data)
        # The rig has to be the active object first. mode_set works on
        # whatever is active, so with a mesh selected this switched *that*
        # into edit mode and the bones were never touched.
        was_active, was = context.view_layer.objects.active, rig.mode
        if gone and activate(context, rig):
            if rig.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")
            bpy.ops.object.mode_set(mode="EDIT")
            for name in gone:
                bone = rig.data.edit_bones.get(name)
                if bone is not None:
                    rig.data.edit_bones.remove(bone)
            bpy.ops.object.mode_set(mode="OBJECT")
            if was != "OBJECT":
                try:
                    bpy.ops.object.mode_set(mode=was)
                except RuntimeError:
                    pass
            if was_active is not None and was_active is not rig:
                context.view_layer.objects.active = was_active
        if len(data.moves):
            bpy.ops.rigmoves.build()
        rig.update_tag()
        context.view_layer.update()
        data.report = "Removed. The rig is back to how it was."
        return {"FINISHED"}


class RIGMOVES_OT_combine(bpy.types.Operator):
    bl_idname = "rigmoves.combine"
    bl_label = "Combine Moves"
    bl_description = ("One control that plays every move in order. Each keeps "
                      "its own control as well, and gets a delay of its own")
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        rig = rig_of(context)
        return rig is not None and len(rig.rigmoves.moves) >= 2

    def execute(self, context):
        rig = rig_of(context)
        data = rig.rigmoves
        for move in data.moves:
            if not move.uid:
                move.uid = "m{:d}".format(data.next_uid)
                data.next_uid += 1
        spare = [m for m in data.moves if group_of(data, m)[0] is None]
        if len(spare) < 2:
            data.report = "Every move is already in a combined control."
            self.report({"WARNING"}, data.report)
            return {"CANCELLED"}
        group = data.groups.add()
        group.name = ("Together" if len(data.groups) == 1
                      else "Together {:d}".format(len(data.groups)))
        group.prop = unique_prop_name(rig, group, safe_prop_name(group.name))
        group.control = default_control(rig)
        for number, move in enumerate(spare):
            member = group.members.add()
            member.uid = move.uid
            # Laid end to end to start with, so pulling the new control plays
            # them one after another. Set every delay to 0 for all at once.
            member.start = number * (1.0 / len(spare))
        data.report = ("'{:s}' plays {:d} move(s), one after another. Change the "
                       "delays to overlap them, then Build."
                       .format(group.name, len(spare)))
        self.report({"INFO"}, data.report)
        return {"FINISHED"}


class RIGMOVES_OT_remove_group(bpy.types.Operator):
    bl_idname = "rigmoves.remove_group"
    bl_label = "Remove"
    bl_description = ("Delete this combined control. The moves it played keep "
                      "their own controls")
    bl_options = {"REGISTER", "UNDO"}
    index: bpy.props.IntProperty()

    def execute(self, context):
        rig = rig_of(context)
        data = rig.rigmoves
        if not 0 <= self.index < len(data.groups):
            return {"CANCELLED"}
        group = data.groups[self.index]
        # Same as a move: the handle's driver goes with its slider.
        rig.driver_remove(property_path(group.control, group.prop))
        bone = rig.pose.bones.get(group.control)
        if bone is not None and group.prop in bone.keys():
            del bone[group.prop]
        data.groups.remove(self.index)
        sync_handles(rig, data)
        bpy.ops.rigmoves.build()
        data.report = "Combined control removed."
        return {"FINISHED"}


class RIGMOVES_OT_drop_member(bpy.types.Operator):
    bl_idname = "rigmoves.drop_member"
    bl_label = "Take Out"
    bl_description = "Take this move out of the combined control"
    bl_options = {"REGISTER", "UNDO"}
    group_index: bpy.props.IntProperty()
    member_index: bpy.props.IntProperty()

    def execute(self, context):
        rig = rig_of(context)
        data = rig.rigmoves
        group = data.groups[self.group_index]
        group.members.remove(self.member_index)
        bpy.ops.rigmoves.build()
        return {"FINISHED"}


class RIGMOVES_OT_pick_rig(bpy.types.Operator):
    bl_idname = "rigmoves.pick_rig"
    bl_label = "Use This Rig"
    bl_description = "Select this armature and go into pose mode, ready to record"
    bl_options = {"REGISTER", "UNDO"}
    name: bpy.props.StringProperty()

    def execute(self, context):
        rig = bpy.data.objects.get(self.name)
        if rig is None or rig.type != "ARMATURE":
            return {"CANCELLED"}
        if context.object is not None and context.object.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        for obj in context.selected_objects:
            obj.select_set(False)
        try:
            rig.hide_set(False)
            rig.select_set(True)
        except RuntimeError:
            self.report({"WARNING"}, "That rig is not in this view layer.")
            return {"CANCELLED"}
        if not activate(context, rig):
            self.report({"WARNING"}, "That rig is not in this view layer.")
            return {"CANCELLED"}
        try:
            bpy.ops.object.mode_set(mode="POSE")
        except RuntimeError:
            pass
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# the panel - which is the rig's UI once the sliders exist


def short(name, keep=15):
    """The tail of a long bone name, which is the part that differs.

    Cut from the front, two controllers called '..._top_controller' and
    '..._top_controller.001' read as the same row.
    """
    return name if len(name) <= keep else "…" + name[-(keep - 1):]


def wrapped(text, width=34, most=6):
    words, line, out = text.split(), "", []
    for word in words:
        if len(line) + len(word) + 1 > width:
            out.append(line)
            line = word
        else:
            line = (line + " " + word).strip()
    if line:
        out.append(line)
    return out[:most]


class RIGMOVES_PT_panel(bpy.types.Panel):
    bl_idname = "RIGMOVES_PT_panel"
    bl_label = "Moves"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Moves"

    # No poll on purpose. A panel that vanishes when the wrong thing is
    # clicked reads as the add-on being broken, and the one moment somebody
    # needs to be told "pick the armature" is the moment it would be gone.

    def draw(self, context):
        layout = self.layout
        layout.use_property_decorate = False
        rig = rig_of(context)
        if rig is None:
            self._draw_no_rig(layout, context)
            return
        data = rig.rigmoves
        layout.label(text=rig.name, icon="ARMATURE_DATA")
        self._draw_own_keys(layout, context, rig, data)
        self._draw_newcomers(layout, context, rig, data)

        for index, move in enumerate(data.moves):
            self._draw_move(layout, context, rig, move, index)

        for index, group in enumerate(data.groups):
            self._draw_group(layout, context, rig, data, group, index)

        layout.separator(factor=0.5)
        row = layout.row(align=True)
        row.operator(RIGMOVES_OT_new_move.bl_idname, text="New Move", icon="ADD")
        if len(data.moves) >= 2:
            row.operator(RIGMOVES_OT_combine.bl_idname, text="Combine", icon="LINKED")
        if len(data.moves):
            run = layout.row()
            run.scale_y = 1.6
            run.operator(RIGMOVES_OT_build.bl_idname, text="Build Sliders", icon="PLAY")
            tools = layout.row(align=True)
            if data.posing:
                tools.alert = True
                tools.operator(RIGMOVES_OT_pause.bl_idname,
                               text="Paused", icon="PAUSE").off = False
            else:
                tools.operator(RIGMOVES_OT_pause.bl_idname,
                               text="Pause", icon="PAUSE").off = True
            tools.operator(RIGMOVES_OT_reset.bl_idname, text="To Before",
                           icon="LOOP_BACK")
        self._draw_report(layout, data)

    def _draw_no_rig(self, layout, context):
        chosen = [o for o in context.selected_objects if o.type == "MESH"]
        if chosen:
            box = layout.box().column(align=True)
            box.label(text="{:d} object(s) selected.".format(len(chosen)), icon="INFO")
            for line in wrapped("Record them where they are, move them, record "
                                "again, and the rig is made for you."):
                box.label(text=line)
            run = layout.row()
            run.scale_y = 1.6
            run.operator(RIGMOVES_OT_new_move.bl_idname, text="New Move", icon="ADD")
            return
        found = armatures_in(context)
        box = layout.box().column(align=True)
        if found:
            box.label(text="Pick the rig to work on:", icon="INFO")
        else:
            box.label(text="Select the objects that move,", icon="INFO")
            box.label(text="or an armature to work on.")
        for armature in found[:8]:
            layout.operator(RIGMOVES_OT_pick_rig.bl_idname, text=armature.name,
                            icon="ARMATURE_DATA").name = armature.name

    def _draw_own_keys(self, layout, context, rig, data):
        """The one fault that makes a correct rig play the wrong move.

        Worth the loudest box on the panel: nothing else here is wrong, so
        there is nothing to find by reading the rest of it.
        """
        auto = context.scene.tool_settings.use_keyframe_insert_auto
        names = sorted({obj.name for _m, _p, obj in keyed_parts(data)})
        ours = len(rig_own_curves(rig, data))
        if not (names or ours or auto):
            return
        box = layout.box().column(align=True)

        if auto:
            head = box.row()
            head.alert = True
            head.label(text="Auto Keying is on", icon="ERROR")
            for line in wrapped("Every drag this tool asks for leaves a "
                                "keyframe behind, and a keyed part or handle "
                                "is one the rig cannot move."):
                box.label(text=line)
            box.prop(context.scene.tool_settings, "use_keyframe_insert_auto",
                     text="Auto Keying", toggle=True)

        if names or ours:
            if auto:
                box.separator(factor=0.5)
            said = "'{:s}'".format(short(names[0], 18)) if len(names) == 1 else \
                   "{:d} parts".format(len(names))
            told = box.column(align=True)
            told.enabled = False
            if names:
                told.label(text="{:s} keyed on its own transform".format(said))
            if ours:
                told.label(text="{:d} key track(s) on this rig's bones".format(ours))
            run = box.row()
            run.scale_y = 1.4
            run.operator(RIGMOVES_OT_free_keys.bl_idname,
                         text="Lift Those Keyframes", icon="KEY_DEHLT")
            note = box.column(align=True)
            note.enabled = False
            for line in wrapped("Build does this too. Handles you have really "
                                "animated are left alone."):
                note.label(text=line)

    def _draw_newcomers(self, layout, context, rig, data):
        """What to do with objects this rig has never been told about.

        Without this the panel simply goes on showing the finished rig, and
        there is nothing on screen that says how to start the next thing.
        """
        fresh = newcomers(context, rig)
        if not fresh or not len(data.moves):
            return
        box = layout.box().column(align=True)
        said = "'{:s}'".format(short(fresh[0].name, 18)) if len(fresh) == 1 else \
               "{:d} objects".format(len(fresh))
        box.label(text="{:s} not in this rig".format(said), icon="INFO")

        # Selecting the newcomer together with a group says which one is
        # meant, so that one is offered first and large. It is a shortcut,
        # not the only way in - the full list is underneath either way.
        singled = {index for index, _move in indicated(context, rig)}
        for index, move in indicated(context, rig)[:2]:
            note = box.row()
            note.enabled = False
            note.label(text="with: {:s}".format(short(move.name, 20)))
            run = box.row()
            run.scale_y = 1.3
            joining = run.operator(RIGMOVES_OT_add_to_move.bl_idname,
                                   text="Add To This Group", icon="ADD")
            joining.index = index
            joining.rig_name = rig.name

        targets = join_targets(context, rig)
        if targets:
            if singled:
                box.separator(factor=0.4)
            said = box.row()
            said.enabled = False
            said.label(text="or add it to:" if singled else "add it to:")
            listed = box.column(align=True)
            for owner, index, move in targets[:8]:
                if owner is rig and index in singled:
                    continue
                name = short(move.name, 18)
                if owner is not rig:
                    name = "{:s}  -  {:s}".format(name, short(rig_label(owner), 14))
                joining = listed.operator(RIGMOVES_OT_add_to_move.bl_idname,
                                          text=name, icon="ADD")
                joining.index = index
                joining.rig_name = owner.name

        box.separator(factor=0.4)
        row = box.row(align=True)
        row.operator(RIGMOVES_OT_new_move.bl_idname,
                     text="New Group Here", icon="ADD").fresh = False
        row.operator(RIGMOVES_OT_new_move.bl_idname,
                     text="New Rig", icon="ARMATURE_DATA").fresh = True

    def _draw_move(self, layout, context, rig, move, index):
        header, body = layout.panel_prop(move, "expanded")
        header.prop(move, "name", text="")
        header.operator(RIGMOVES_OT_remove.bl_idname, text="", icon="X",
                        emboss=False).index = index
        if body is None:
            return

        before = recorded(move, "BEFORE")
        after = recorded(move, "AFTER")

        objects = len(loose_parts(move))
        row = body.split(factor=0.4, align=True)
        row.label(text="Parts", icon="OBJECT_DATA" if objects else "BONE_DATA")
        row.operator(RIGMOVES_OT_use_selected.bl_idname,
                     text="{:d} selected".format(len(move.parts)),
                     icon="CHECKMARK" if len(move.parts) else "ADD").index = index

        row = body.split(factor=0.4, align=True)
        row.scale_y = 1.15
        row.label(text="Before", icon="CHECKMARK" if before else "DOT")
        row = row.row(align=True)
        press = row.operator(RIGMOVES_OT_record.bl_idname, text="Record")
        press.index, press.which = index, "BEFORE"
        if before:
            look = row.operator(RIGMOVES_OT_show.bl_idname, text="", icon="HIDE_OFF")
            look.index, look.which = index, "BEFORE"

        # The poses in between, each with a Record of its own. A step is put
        # up empty by the + below and filled in afterwards, which is the whole
        # of it: the same gesture as Before and After, one row further in.
        for position, step in enumerate(move.steps):
            row = body.split(factor=0.4, align=True)
            row.scale_y = 1.15
            gap = row.row(align=True)
            gap.label(text="", icon="BLANK1")
            gap.label(text="Step {:d}".format(position + 1),
                      icon="CHECKMARK" if step.done else "DOT")
            row = row.row(align=True)
            press = row.operator(RIGMOVES_OT_record.bl_idname, text="Record")
            press.index, press.which, press.step = index, "STEP", position
            if step.done:
                look = row.operator(RIGMOVES_OT_show.bl_idname, text="",
                                    icon="HIDE_OFF")
                look.index, look.which, look.step = index, "STEP", position
            away = row.operator(RIGMOVES_OT_drop_step.bl_idname, text="", icon="X")
            away.index, away.step = index, position

        # Only once the parts have bones and a path of their own, which the
        # first build gives them - until then there is nothing to key onto.
        add = body.row(align=True)
        add.enabled = bool(before and after and not objects)
        add.operator(RIGMOVES_OT_add_step.bl_idname,
                     text="Step in between", icon="ADD").index = index

        row = body.split(factor=0.4, align=True)
        row.scale_y = 1.15
        row.label(text="After", icon="CHECKMARK" if after else "DOT")
        row = row.row(align=True)
        press = row.operator(RIGMOVES_OT_record.bl_idname, text="Record")
        press.index, press.which = index, "AFTER"
        if after:
            look = row.operator(RIGMOVES_OT_show.bl_idname, text="", icon="HIDE_OFF")
            look.index, look.which = index, "AFTER"

        if not len(move.steps) and before and after and not objects:
            said = body.row()
            said.enabled = False
            said.label(text="+ adds a pose in between, for a path that bends")
        body.prop(move, "ease", text="")

        # Who moves when. The reason a machine reads as built rather than
        # animated: the parts do not all leave at once.
        head, timing = layout.panel_prop(move, "show_timing")
        head.label(text="Timing", icon="TIME")
        if timing is not None:
            note = timing.row()
            note.enabled = False
            note.label(text="how long each one waits before it starts")
            lit = held(context, move)
            if lit:
                said = timing.row()
                said.enabled = False
                said.label(text="lit: what you have selected", icon="RESTRICT_SELECT_OFF")
            for position, part in enumerate(move.parts):
                line = timing.split(factor=0.45, align=True)
                # Everything else goes quiet rather than the chosen one being
                # shouted: the eye lands on the one row still at full strength.
                line.active = part.name in lit or not lit
                name = line.row(align=True)
                pick = name.operator(
                    RIGMOVES_OT_pick_part.bl_idname, text="", emboss=False,
                    icon="RESTRICT_SELECT_OFF" if part.name in lit
                    else ("OBJECT_DATA" if part.kind == "OBJECT" else "BONE_DATA"))
                pick.index, pick.part = index, position
                name.label(text=short(part.name))
                line.prop(part, "start", text="")

        # What the animator actually reaches for. With a handle that is the
        # bone's own position, shown here as well so it can be typed and keyed
        # without hunting for it in the viewport.
        handle = rig.pose.bones.get(move.handle_name) if move.handle else None
        bone = rig.pose.bones.get(move.control)
        if move.built and handle is not None:
            row = body.row(align=True)
            row.scale_y = 1.3
            row.use_property_decorate = True
            row.prop(handle, "location", index=1, text=move.name)
            said = body.row()
            said.enabled = False
            share = min(1.0, max(0.0, handle.location.y / (move.rail or 1.0)))
            said.label(text="{:.0f}% through - or drag it in the viewport".format(
                share * 100))
        elif move.built and bone is not None and move.prop in bone.keys():
            row = body.row(align=True)
            row.scale_y = 1.3
            row.use_property_decorate = True
            row.prop(bone, '["{:s}"]'.format(bpy.utils.escape_identifier(move.prop)),
                     text=move.name)

    def _draw_group(self, layout, context, rig, data, group, index):
        header, body = layout.panel_prop(group, "expanded")
        header.label(text="", icon="LINKED")
        header.prop(group, "name", text="")
        header.operator(RIGMOVES_OT_remove_group.bl_idname, text="", icon="X",
                        emboss=False).index = index
        if body is None:
            return
        note = body.row()
        note.enabled = False
        note.label(text="plays these, each after its own delay")
        for position, member in enumerate(group.members):
            move = move_by_uid(data, member.uid)
            line = body.split(factor=0.45, align=True)
            if move is not None and held(context, move):
                line.label(text=short(move.name, 14), icon="RESTRICT_SELECT_OFF")
            else:
                line.label(text=short(move.name if move is not None else "(gone)", 14))
            line = line.row(align=True)
            line.prop(member, "start", text="")
            drop = line.operator(RIGMOVES_OT_drop_member.bl_idname, text="",
                                 icon="X", emboss=False)
            drop.group_index, drop.member_index = index, position

        handle = rig.pose.bones.get(group.handle_name) if group.handle else None
        bone = rig.pose.bones.get(group.control)
        if group.built and handle is not None:
            row = body.row(align=True)
            row.scale_y = 1.3
            row.use_property_decorate = True
            row.prop(handle, "location", index=1, text=group.name)
            said = body.row()
            said.enabled = False
            share = min(1.0, max(0.0, handle.location.y / (group.rail or 1.0)))
            said.label(text="{:.0f}% through - or drag it in the viewport".format(
                share * 100))
        elif group.built and bone is not None and group.prop in bone.keys():
            row = body.row(align=True)
            row.scale_y = 1.3
            row.use_property_decorate = True
            row.prop(bone, '["{:s}"]'.format(bpy.utils.escape_identifier(group.prop)),
                     text=group.name)

    def _draw_report(self, layout, data):
        if not data.report:
            return
        note = layout.box().column(align=True)
        note.enabled = False
        for line in wrapped(data.report):
            note.label(text=line)


CLASSES = (
    RIGMOVES_Part,
    RIGMOVES_Step,
    RIGMOVES_Move,
    RIGMOVES_Member,
    RIGMOVES_Group,
    RIGMOVES_Rig,
    RIGMOVES_OT_new_move,
    RIGMOVES_OT_add_to_move,
    RIGMOVES_OT_pick_part,
    RIGMOVES_OT_free_keys,
    RIGMOVES_OT_use_selected,
    RIGMOVES_OT_record,
    RIGMOVES_OT_show,
    RIGMOVES_OT_add_step,
    RIGMOVES_OT_drop_step,
    RIGMOVES_OT_build,
    RIGMOVES_OT_pause,
    RIGMOVES_OT_reset,
    RIGMOVES_OT_remove,
    RIGMOVES_OT_combine,
    RIGMOVES_OT_remove_group,
    RIGMOVES_OT_drop_member,
    RIGMOVES_OT_pick_rig,
    RIGMOVES_PT_panel,
)


def registered_copy(cls):
    """The copy of this class Blender already has registered, if any.

    Asked of its base type, not looked up in bpy.types: property groups are
    not listed there, so a reloaded script found nothing to take down and
    registering stopped at the first one with "already registered".
    """
    for base in (bpy.types.PropertyGroup, bpy.types.Operator, bpy.types.Panel):
        if issubclass(cls, base):
            return base.bl_rna_get_subclass_py(cls.__name__)
    return None


def take_down():
    """Remove whatever copy of this add-on is registered, newest dependants
    first, so a property group is never taken down while a pointer still
    holds it."""
    if hasattr(bpy.types.Scene, "rigmoves_rig"):
        del bpy.types.Scene.rigmoves_rig
    if hasattr(bpy.types.Object, "rigmoves"):
        del bpy.types.Object.rigmoves
    for cls in reversed(CLASSES):
        existing = registered_copy(cls)
        if existing is not None:
            try:
                bpy.utils.unregister_class(existing)
            except RuntimeError:
                pass


def register():
    # A script reload registers again without unregistering first, so a
    # copy may still be there.
    take_down()
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Object.rigmoves = bpy.props.PointerProperty(type=RIGMOVES_Rig)
    # Which rig the panel is on while loose objects, not the armature, are
    # what the user has selected.
    bpy.types.Scene.rigmoves_rig = bpy.props.PointerProperty(
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == "ARMATURE")


def unregister():
    take_down()
