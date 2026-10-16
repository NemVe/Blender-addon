"""CopyThat - record how a machine moves between two poses, get one slider.

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

import json
import math
import random

import bpy
import bmesh  # after bpy: as a module, bpy is what makes bmesh importable
from mathutils import Euler, Matrix, Quaternion, Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree
from mathutils.geometry import interpolate_bezier

bl_info = {
    "name": "CopyThat - Record a Move, Get a Slider",
    "author": "NemVe3D",
    "version": (0, 18, 3),
    "blender": (4, 5, 0),
    "location": "View3D > Sidebar > CopyThat",
    "description": "Record a path between two poses of any bones, with per-part "
                   "delays. Works on loose objects with no rig at all, and makes one. "
                   "Other objects can ride along, each from its own place - "
                   "copies of a whole finger joint for joint. Spread, Make "
                   "Chain, Curl and Ring do the repetitive work",
    "doc_url": "https://creators.sa/nemve",
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


def corners_of(obj):
    """An object's bounding corners in its own space, as it was modelled.

    Not obj.bound_box: in Blender 5 that is the evaluated box, which on a
    bound part already holds wherever the rig has moved it. Read with the
    machine half open it put a Base pivot on the top of a lid, drew the path
    preview a whole move off, and sized and placed the handles differently
    depending on where the control happened to be.
    """
    if obj.type == "MESH" and len(obj.data.vertices):
        values = [0.0] * (3 * len(obj.data.vertices))
        obj.data.vertices.foreach_get("co", values)
        low = [min(values[axis::3]) for axis in range(3)]
        high = [max(values[axis::3]) for axis in range(3)]
        return [Vector((x, y, z)) for x in (low[0], high[0])
                for y in (low[1], high[1]) for z in (low[2], high[2])]
    return [Vector(c) for c in obj.bound_box]


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
        for child in rig.children_recursive:
            if child.type == "MESH" and child.vertex_groups.get(name) is not None:
                points.extend(child.matrix_world @ c for c in corners_of(child))
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
    rails = [(carrier, carrier.rail) for carrier, _names in carriers(data)]
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

    # A rail that changed length - a pivot moved, a rider joined - takes the
    # handle's keys with it, so a control keyed by Animate or by hand still
    # runs from end to end, and an unkeyed handle stays as far along.
    for carrier, was in rails:
        if was > 1e-9 and abs(carrier.rail - was) > 1e-9:
            stretch_handle(rig, carrier, carrier.rail / was)

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


def stretch_handle(rig, carrier, factor):
    """Scale a handle's place along its rail, and its keys, by `factor`."""
    pose_bone = rig.pose.bones.get(carrier.handle_name) if carrier.handle else None
    if pose_bone is None:
        return
    pose_bone.location.y *= factor
    _holder, curve = action_curve(rig, pose_bone.path_from_id("location"), 1)
    if curve is not None:
        for point in curve.keyframe_points:
            point.co[1] *= factor
            point.handle_left[1] *= factor
            point.handle_right[1] *= factor
        curve.update()


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


# Set while a tool writes many Leads or Delays in one go. Each write would
# otherwise rewrite every driver of the move; once at the end is enough.
WRITING = {"many": False}


def _timing_changed(self, context):
    """Put a timing change into effect at once - a delay, a lead, an ease, a
    speed - so it can be judged by scrubbing the control rather than by
    pressing Build after every nudge."""
    if WRITING["many"]:
        return
    rig = self.id_data
    if hasattr(self, "steps"):
        move = self
    else:
        mine = self.as_pointer()
        move = next((m for m in rig.rigmoves.moves
                     if any(x.as_pointer() == mine
                            for x in list(m.steps) + list(m.parts))), None)
    if move is not None:
        refresh_drivers(rig, rig.rigmoves, move)


def control_of(carrier):
    """(handle pose bone, slider bone) for a move or combined control - the
    handle None when it has none."""
    rig = carrier.id_data
    handle = rig.pose.bones.get(carrier.handle_name) if carrier.handle else None
    return handle, rig.pose.bones.get(carrier.control)


def _play_get(self):
    """How far through the control is, 0 to 100, read off whatever drives it."""
    handle, bone = control_of(self)
    if handle is not None:
        share = handle.location.y / (self.rail or 1.0)
    elif bone is not None and self.prop in bone.keys():
        share = (bone[self.prop] - self.low) / ((self.high - self.low) or 1.0)
    else:
        share = 0.0
    return 100.0 * min(1.0, max(0.0, share))


def _play_set(self, value):
    """Write it back to the same place, so the panel and the viewport handle
    are one control and never disagree."""
    handle, bone = control_of(self)
    share = min(1.0, max(0.0, value / 100.0))
    if handle is not None:
        handle.location.y = share * (self.rail or 1.0)
    elif bone is not None and self.prop in bone.keys():
        bone[self.prop] = self.low + share * (self.high - self.low)
    self.id_data.update_tag()


PLAY_HELP = ("Play the whole of it, from the first part that moves to the last "
             "one to arrive. The handle in the viewport follows")

FRAMES_HELP = "How many frames Animate spreads the whole of it over"


def holder_of(rig, part):
    """The move a part belongs to."""
    mine = part.as_pointer()
    for move in rig.rigmoves.moves:
        if any(p.as_pointer() == mine for p in move.parts):
            return move
    return None


def _follows_changed(self, context):
    """Turn down a choice that cannot be, and say why.

    Itself, a rider, a part of a rig's own, a curved part, or a loop - a part
    that ends up following itself. A part that leads riders may follow: its
    riders hang from what it follows too, at the next Build, so they are
    carried along with it.
    """
    if not self.follows:
        self.follows_kept = ""
        hang(self)
        return
    rig = self.id_data
    move = holder_of(rig, self)
    target = move.parts.get(self.follows) if move is not None else None
    why = ""
    if target is None or target.name == self.name:
        why = "pick another part of this move"
    elif self.leader or target.leader:
        why = "riders copy their leader instead"
    elif self.kind != "OBJECT" or target.kind != "OBJECT":
        why = "only objects can follow and be followed"
    elif curve_alive(self.path_curve):
        why = "its path is curved - Straighten it first, as a follower goes where it is carried"
    else:
        seen, chain = {self.name}, target
        while chain is not None and chain.follows:
            if chain.follows in seen:
                why = "that would make a loop"
                break
            seen.add(chain.follows)
            chain = move.parts.get(chain.follows)
    if why:
        rig.rigmoves.report = "'{:s}' cannot follow '{:s}': {:s}.".format(
            short(self.name, 16), short(self.follows, 16), why)
        # Back to the choice it had, not to none: a slip in the list must not
        # quietly undo a finger that was working.
        self.follows = self.follows_kept
        return
    self.follows_kept = self.follows
    hang(self)


FOLLOW_MARK = "RigMoves follows"


def keep_world(obj, parent):
    """Give an object a new parent, or none, without it moving."""
    world = obj.matrix_world.copy()
    obj.parent = parent
    if parent is not None:
        obj.parent_type = "OBJECT"
        obj.matrix_parent_inverse = parent.matrix_world.inverted_safe()
    obj.matrix_world = world


def hang(part):
    """Let a part's object hang from the object of the part it follows, so
    that dragging that one carries it along on screen - and what is recorded
    is what was seen.

    Before the first Build that is all that carries it. After it the bones
    play the move, but the object still hangs there: dragged off its Before
    the leader would otherwise leave its followers standing, and a pose that
    cannot be seen cannot be recorded. A part that stops following goes back
    to what held it - the rig, once bound; its own old parent before.
    """
    if part.kind != "OBJECT":
        return
    obj = bpy.data.objects.get(part.name)
    if obj is None:
        return
    target = bpy.data.objects.get(part.follows) if part.follows else None
    if target is not None and target is not obj:
        if obj.parent is not target:
            # The parent it had of its own is remembered, to be given back.
            if (not part.bone_name and obj.parent is not None
                    and not obj.get(FOLLOW_MARK)):
                part.home_parent = obj.parent.name
            keep_world(obj, target)
            obj[FOLLOW_MARK] = True
    else:
        unhang(part)


def rig_holding(obj):
    """The rig a bound object's Armature modifier points at."""
    for modifier in obj.modifiers:
        if modifier.type == "ARMATURE" and modifier.object is not None:
            return modifier.object
    return None


def unhang(part):
    """Take an object off the part it was hung from to follow, and give it to
    what held it before: the rig if it is bound, else the parent it had of
    its own, if any."""
    obj = bpy.data.objects.get(part.name)
    if obj is None or not obj.get(FOLLOW_MARK):
        return
    if part.bone_name and rig_holding(obj) is not None:
        keep_world(obj, rig_holding(obj))
    else:
        home = bpy.data.objects.get(part.home_parent) if part.home_parent else None
        keep_world(obj, home if home is not obj else None)
    del obj[FOLLOW_MARK]


def hang_objects(context, data):
    """Hang every bound follower's object from its leader's, parents first.

    Binding hangs a new part's object from the rig; this hangs it on from the
    part it follows, standing where it stands.
    """
    for move in data.moves:
        for part in follow_order(move, bound_parts(move)):
            if not part.leader:
                hang(part)
    context.view_layer.update()


AXES = ("X", "Y", "Z")
MIRRORS = [("NONE", "-", "Copies the leader's move as it is, from where it stands"),
           ("X", "X", "Mirrors the leader's move across its own X: its left "
                      "becomes the rider's right"),
           ("Y", "Y", "Mirrors the leader's move across its own Y"),
           ("Z", "Z", "Mirrors the leader's move across its own Z")]
PIVOTS = [("ORIGIN", "Origin", "Turn about the object's own origin"),
          ("CURSOR", "3D Cursor", "Turn about the point the 3D cursor is on - "
                                  "put it on the hinge first"),
          ("BASE", "Base", "Turn about the middle of the bottom of its "
                           "bounding box")]


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
        update=_timing_changed,
        description="How far along the slider this part waits before it starts. "
                    "0 moves with everything else, 0.5 starts half way")
    end: bpy.props.FloatProperty(
        name="Done", default=1.0, min=0.01, max=1.0, subtype="FACTOR",
        description="How far along the slider this part has arrived. Below 1 it "
                    "gets there early and then waits")
    # A rider: an object with no path of its own, that copies the path of the
    # part named here from where it stands itself. Empty for every other part.
    leader: bpy.props.StringProperty()
    # A rider's place in time against its leader; it travels at the leader's
    # speed either way. Takes the place of the delay, which riders do not use.
    lead: bpy.props.IntProperty(
        name="Lead", default=0, min=-50, max=50, update=_timing_changed,
        description="When this rider moves, against its leader. 0 moves with "
                    "it. Below 0 it follows behind: -25 sets off when the "
                    "leader is half way, -50 when it has finished. Above 0 it "
                    "goes first: 50 has finished before the leader starts")
    # A rider that faces the other way to its leader - the second of a pair
    # of doors - can play its move mirrored. A rider that is a mirrored copy
    # already (negative scale) mirrors by itself, with this left at "-".
    mirror: bpy.props.EnumProperty(name="Mirror", items=MIRRORS, default="NONE")
    # A rider copying one joint of a chain - the middle of a finger - rides
    # on the rider copying the joint before it, so a copied finger bends
    # joint by joint as the recorded one does. Empty for the first joint of
    # a copy, which hangs where its leader hangs, and for every other part.
    # A copy's Lead and Mirror are its first joint's.
    rides_on: bpy.props.StringProperty()
    # The point this part turns about, in its own space where it stands at
    # Before, so it goes with the object if Before is taken again. The kind
    # is only which button set it, for the panel to show.
    pivot: bpy.props.FloatVectorProperty(size=3, default=(0.0, 0.0, 0.0))
    pivot_kind: bpy.props.EnumProperty(items=PIVOTS, default="ORIGIN")
    # A curve the pivot travels along from Before to After, and whether the
    # path was last laid from one - so taking the curve away straightens it.
    path_curve: bpy.props.PointerProperty(type=bpy.types.Object)
    curved: bpy.props.BoolProperty(default=False)
    # The object this one hung from before the first Build took it over, so
    # taking it out of the rig can hang it there again.
    home_parent: bpy.props.StringProperty()
    # The part this one hangs from, like the joints of a finger: it moves
    # with that part and plays its own move on top. Empty for none. Put
    # into effect at the next Build, which hangs the bone from that part's.
    follows_kept: bpy.props.StringProperty()
    follows: bpy.props.StringProperty(
        name="Follows", update=_follows_changed,
        description="The part this one moves with, as the next joint of a "
                    "finger moves with the one before: it goes wherever that "
                    "part takes it, and does its own move on top. Build to "
                    "put it into effect")


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


SPEED_HELP = ("How fast the parts travel on this stretch, against the rest of "
              "the move. 0 is even; 15 is about twice as fast and 50 ten times, "
              "below 0 slower the same way. The move always fills its whole "
              "control, so only the differences between stretches count")


class RIGMOVES_Step(bpy.types.PropertyGroup):
    """One pose between Before and After.

    Kept as data rather than worked out from the keys on the path, because a
    step has to exist before it holds anything: pressing + puts an empty one
    up with its own Record, and there is nothing on the path to find until
    that Record is pressed.
    """
    frame: bpy.props.FloatProperty(default=0.0)
    done: bpy.props.BoolProperty(default=False)
    # The stretch on the way into this step. The one into After is the
    # move's own.
    speed: bpy.props.IntProperty(
        name="Speed", default=0, min=-50, max=50, update=_timing_changed,
        description=SPEED_HELP)


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
    # The last stretch, from the last step into After. Each step carries the
    # stretch into itself, so this is the one left over.
    speed_after: bpy.props.IntProperty(
        name="Speed", default=0, min=-50, max=50, update=_timing_changed,
        description=SPEED_HELP)
    ease: bpy.props.EnumProperty(
        name="Ease",
        items=[("LINEAR", "Even speed", "The same speed the whole way"),
               ("SMOOTH", "Smooth", "Starts and stops gently"),
               ("IN", "Slow start", "Starts gently, arrives at full speed"),
               ("OUT", "Slow stop", "Starts at full speed, arrives gently")],
        default="LINEAR", update=_timing_changed)
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
    # Not stored: it reads and writes the handle, or the slider when there is
    # no handle, so it is the same control seen from the panel.
    play: bpy.props.FloatProperty(
        name="Play", min=0.0, max=100.0, subtype="PERCENTAGE", precision=0,
        get=_play_get, set=_play_set, description=PLAY_HELP)
    play_frames: bpy.props.IntProperty(
        name="Frames", default=48, min=1, max=100000, description=FRAMES_HELP)
    built: bpy.props.BoolProperty(default=False)
    expanded: bpy.props.BoolProperty(default=True)
    show_timing: bpy.props.BoolProperty(default=False)
    show_riders: bpy.props.BoolProperty(default=True)
    show_chain: bpy.props.BoolProperty(default=True)
    # The line drawn through where every part goes, while it is shown.
    show_paths: bpy.props.BoolProperty(default=False)
    # Held by pointer, not by name: a name freed by one rig's deleted line
    # can be taken by another rig's, and the wrong one would go.
    paths_object: bpy.props.PointerProperty(type=bpy.types.Object)


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
    play: bpy.props.FloatProperty(
        name="Play", min=0.0, max=100.0, subtype="PERCENTAGE", precision=0,
        get=_play_get, set=_play_set, description=PLAY_HELP)
    play_frames: bpy.props.IntProperty(
        name="Frames", default=48, min=1, max=100000, description=FRAMES_HELP)
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
    # Where the rig stood when the world matrices a move keeps - every part's
    # Before and After - were last true. The rig and its parts can be moved
    # as a whole after that, and catch_up carries what is kept by however far
    # the rig has gone since. False for a rig made before this was kept.
    seat: bpy.props.FloatVectorProperty(size=16)
    seated: bpy.props.BoolProperty(default=False)


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
    chosen.add(obj.name)
    if chosen:
        for candidate in bpy.data.objects:
            if candidate.type != "ARMATURE" or not here(context, candidate):
                continue
            for move in candidate.rigmoves.moves:
                for part in move.parts:
                    if part.kind == "OBJECT" and part.name in chosen:
                        return candidate
                    # A part's path curve, being bent in edit mode, still
                    # belongs to that part's rig.
                    curve = part.path_curve
                    if curve is not None and curve.name in chosen:
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
    """Parts that are still objects, with no bone made for them yet.

    Riders are not among them: they are never posed or recorded, so nothing
    about Before and After waits on them.
    """
    return [p for p in move.parts if p.kind == "OBJECT" and not p.bone_name
            and not p.leader]


def bound_parts(move):
    """Parts that started as objects and now have a bone of their own.

    Riders included: they are bound the same way, and put back on their
    Before the same way when they drift.
    """
    return [p for p in move.parts if p.kind == "OBJECT" and p.bone_name
            and p.has_before]


def riders_of(move):
    """The parts that copy another part's path, as (index, part)."""
    return [(i, p) for i, p in enumerate(move.parts) if p.leader]


def unbind_object(rig, part):
    """Give a bound object its freedom back.

    The group, the modifier and the parent all go, and it stays exactly where
    it is.
    """
    obj = bpy.data.objects.get(part.name)
    if obj is None:
        return False
    world = obj.matrix_world.copy()
    for modifier in list(obj.modifiers):
        if modifier.type == "ARMATURE" and modifier.object is rig:
            obj.modifiers.remove(modifier)
    group = obj.vertex_groups.get(part.bone_name)
    if group is not None:
        obj.vertex_groups.remove(group)
    if obj.parent is rig or obj.get(FOLLOW_MARK):
        obj.parent = None
    if obj.get(FOLLOW_MARK):
        del obj[FOLLOW_MARK]
    obj.matrix_world = world
    # Hung back from whatever it hung from before the rig took it.
    home = bpy.data.objects.get(part.home_parent) if part.home_parent else None
    if home is not None and home is not obj:
        keep_world(obj, home)
    return True


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
    # Only the channelbags are read. From Blender 4.4 every action keeps its
    # curves in them (a file made before is converted when it opens), but 4.4
    # and 4.5 still answer `action.fcurves` as well, with the first slot's
    # curves over again, so reading both counted every curve twice. 5.0 took
    # that list away.
    for layer in action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                for curve in bag.fcurves:
                    if curve.data_path in TRANSFORM_PATHS:
                        found.append((bag, curve))
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

    # Channelbags only, for the reason given in own_transform_curves.
    for layer in action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                out.extend((bag, c) for c in bag.fcurves if ours(c.data_path))
    return out


def is_handle(rig, name):
    bone = rig.data.bones.get(name)
    return bone is not None and bone.get(RAIL) is not None


def curve_bone(curve):
    try:
        return curve.data_path.split('"')[1]
    except IndexError:
        return ""


def lone_key(rig, curve, auto):
    """Whether a curve on our bones is a lone key a drag left behind.

    On a part's own bone a single key is never wanted: it pins the bone
    against its path. On a handle it is what a drag leaves with Auto Keying
    on - but also what one press of the key button makes, on purpose, as the
    first key of an animation. So a handle's lone key counts as stray only
    while Auto Keying is on.
    """
    if len(curve.keyframe_points) > 1:
        return False
    return auto or not is_handle(rig, curve_bone(curve))


def stray_curves(rig, data, auto=True):
    """The keys on our bones worth a word: a lone key a drag left behind, or a
    part's own bone keyed on top of its path. A handle with a real curve on
    it is the machine being animated, which is what it is for."""
    out = []
    for holder, curve in rig_own_curves(rig, data):
        name = curve_bone(curve)
        if not name:
            continue
        if lone_key(rig, curve, auto) or (len(curve.keyframe_points) > 1
                                          and not is_handle(rig, name)):
            out.append((holder, curve))
    return out


def drop_control_keys(rig, carrier):
    """Take a control's keys off the rig along with the control, so a later
    one that lands on the same name does not play an animation nobody gave
    it."""
    paths = []
    if carrier.handle_name:
        paths.append(bone_path(carrier.handle_name, "location"))
    if carrier.control and carrier.prop:
        paths.append(property_path(carrier.control, carrier.prop))
    for path in paths:
        while True:
            holder, curve = action_curve(rig, path, -1)
            if curve is None:
                break
            holder.fcurves.remove(curve)
    drop_empty_action(rig)


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
    # Channelbags only, for the reason given in own_transform_curves.
    if any(len(bag.fcurves) for layer in action.layers
           for strip in layer.strips for bag in strip.channelbags):
        return
    animation.action = None
    if action.users == 0 and not action.use_fake_user:
        bpy.data.actions.remove(action)


def clear_autokey(rig, data, auto=True):
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
    spare = [pair for pair in ours if lone_key(rig, pair[1], auto)]
    real = [pair for pair in ours if len(pair[1].keyframe_points) > 1]
    bones = lift_curves(spare)
    if bones:
        drop_empty_action(rig)
    for _holder, curve in real:
        try:
            name = curve.data_path.split('"')[1]
        except IndexError:
            continue
        # A handle with a real curve on it is the finished machine being
        # animated - by hand, or by Animate - which is what it is for. Only a
        # part's own bone keyed on top of its path is worth a word.
        bone = rig.data.bones.get(name)
        if bone is None or bone.get(RAIL) is None:
            kept.append(name)
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
        # Parents first: a follower's object hangs from its leader's, so
        # putting the leader back moves it, and it is only then put right.
        for part in follow_order(one, bound_parts(one)):
            obj, world = hand_moved(part)
            if obj is not None and world is not None:
                obj.matrix_world = as_matrix(part.before)
                bpy.context.view_layer.update()
                count += 1
    return count


def curve_start(obj):
    """Where a path curve begins, in the world."""
    spline = obj.data.splines[0]
    first = (spline.bezier_points[0].co if spline.type == "BEZIER"
             else Vector(spline.points[0].co[:3]))
    return obj.matrix_world @ first


def carry_stored(data, shift):
    """Carry every world matrix a rig remembers by `shift`, a matrix.

    A part's Before and After are where its object stood in the world, and
    the rig and everything bound to it move as one: when the whole model is
    moved, or the rig is parented to something that is, they are moved by the
    same amount. A bone's own pose is in the rig's space and goes with the rig
    by itself, so only objects have anything to carry. A path curve is an
    object of its own, which comes along only if it was moved with the rest;
    it is told by its start, which every Build pins to the pivot at Before.
    """
    for move in data.moves:
        for part in move.parts:
            if part.kind != "OBJECT":
                continue
            curve = part.path_curve
            if part.has_before and curve_alive(curve):
                pivot = as_matrix(part.before) @ Vector(part.pivot)
                slack = 1e-4 * (1.0 + max(abs(c) for c in pivot))
                if ((curve_start(curve) - pivot).length <= slack
                        and (shift @ pivot - pivot).length > slack):
                    curve.matrix_world = shift @ curve.matrix_world
            if part.has_before:
                part.before = flat(shift @ as_matrix(part.before))
            if part.has_after:
                part.after = flat(shift @ as_matrix(part.after))


def catch_up(rig, data=None):
    """Bring what a rig remembers of where its parts stand into step with
    where the rig stands now. Run first by every operator that reads or writes
    it; never from drawing, where nothing may be written.

    Returns a sentence saying why the operator must not go on, or "".

    Every part's Before and After are world matrices, true for as long as the
    rig stood where it did when they were taken. Move the rig - on its own,
    with everything selected, or by parenting it to a hand and moving the
    hand - and the parts go with it, but what is remembered stayed behind: a
    Build then put every part back where the model used to be.
    """
    data = rig.rigmoves if data is None else data
    bpy.context.view_layer.update()
    now = rig.matrix_world.copy()
    if not data.seated:
        # A new rig, or one from before this was kept: it stands where it
        # stands, and what it remembers is taken to be true of that.
        data.seat, data.seated = flat(now), True
        return ""
    shift = now @ as_matrix(data.seat).inverted_safe()
    if not same_matrix(shift, Matrix.Identity(4), 1e-6):
        carry_stored(data, shift)
        data.seat = flat(now)
    return ""


def ready(operator, rig, data):
    """Catch a rig up, and say why if the operator may not go on."""
    refusal = catch_up(rig, data)
    if not refusal:
        return True
    data.report = refusal
    operator.report({"WARNING"}, refusal)
    return False


def chain_parts(move):
    """The parts that can follow and be followed: objects, riders aside."""
    return [p for p in move.parts if p.kind == "OBJECT" and not p.leader]


def is_bound(part):
    return bool(part.bone_name) and part.has_before


def hangs_from(part, leader):
    """Whether a part's object hangs from the object of the part it follows."""
    obj = bpy.data.objects.get(part.name)
    held = bpy.data.objects.get(leader.name) if leader is not None else None
    return obj is not None and held is not None and obj.parent is held


def seen_poses(rig, move, shown):
    """Where every object part of a move is seen to stand, as a world matrix,
    and which bound followers were only carried there.

    A bound part is seen where its bone carries its object - `shown`, every
    bone's deformation as it was on screen. A follower's object hangs from
    its leader's, but the leader's bone acts after that, so with the finger
    posed a drag of the leader reaches a bent follower before its own bend:
    on screen the joint opens. What was meant is the follower carried whole,
    by what the drag did to the leader as seen. So, parents first, each part
    leaves behind how far it was carried as an object and how far as seen,
    and a follower hanging from it takes the second for the first.
    """
    world = rig.matrix_world
    into = world.inverted_safe()
    seen, carried = {}, set()
    carry, change = {}, {}
    for part in follow_order(move, chain_parts(move)):
        obj = bpy.data.objects.get(part.name)
        if obj is None:
            continue
        here = obj.matrix_world.copy()
        bound = is_bound(part)
        shown_here = (world @ shown.get(part.bone_name, Matrix.Identity(4)) @ into
                      if bound else Matrix.Identity(4))
        leader = move.parts.get(part.follows) if part.follows else None
        if leader is not None and leader.name in carry and hangs_from(part, leader):
            own = carry[leader.name].inverted_safe() @ here
            seen[part.name] = change[leader.name] @ shown_here @ own
        else:
            own = here
            seen[part.name] = shown_here @ here
        # Where it would stand had nothing been dragged: a bound object on its
        # Before; a loose one wherever it is, less what carried it.
        rest = as_matrix(part.before) if bound else own
        carry[part.name] = here @ rest.inverted_safe()
        change[part.name] = seen[part.name] @ (shown_here @ rest).inverted_safe()
        if (bound and leader is not None and leader.name in carry
                and hangs_from(part, leader) and same_matrix(own, rest, 1e-4)):
            carried.add(part.name)
    return seen, carried


def stand_parts(context, move, places):
    """Every bound object of a move back on its Before, and every loose one
    where `places` puts it - parents first, as a follower's object hangs from
    its leader's and goes wherever that is put."""
    count = 0
    for part in follow_order(move, chain_parts(move)):
        obj = bpy.data.objects.get(part.name)
        target = as_matrix(part.before) if is_bound(part) else places.get(part.name)
        if obj is None or target is None or same_matrix(obj.matrix_world, target):
            continue
        obj.matrix_world = target
        context.view_layer.update()
        count += 1
    return count


def bone_hangs_from(rig, part, leader):
    """Whether a part's bone already hangs from the bone of the part it follows."""
    bone = rig.data.bones.get(part.bone_name) if part.bone_name else None
    return (bone is not None and leader is not None and bone.parent is not None
            and bone.parent.name == leader.bone_name)


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


def path_moves(move):
    """Whether the path ends anywhere but where it starts."""
    _action, _slot, bag = action_bits(move)
    if bag is None:
        return False
    end = float(last_frame(move))
    return any(abs(curve.evaluate(float(FIRST_FRAME)) - curve.evaluate(end)) > 1e-5
               for curve in bag.fcurves)


def recorded(move, which):
    """Whether this state has been taken down, for objects or for bones.

    A loose follower with no After of its own rides along with the part it
    follows, so it waits on nothing. And a key on the After frame is not an
    After by itself: a Build writes one for every object it binds, recorded
    or not, so a move of objects asks whether any of them was - or whether
    the path goes anywhere, for one recorded before that was kept.
    """
    loose = loose_parts(move)
    if which == "BEFORE":
        if loose:
            return all(p.has_before for p in loose)
        return keyed_at(move, FIRST_FRAME)
    if any(not (p.has_after or p.follows) for p in loose):
        return False
    mine = [p for p in move.parts if not p.leader]
    objects = [p for p in mine if p.kind == "OBJECT"]
    if objects and len(objects) == len(mine):
        return any(p.has_after for p in objects) or path_moves(move)
    return keyed_at(move, last_frame(move))


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

    armature = bpy.data.armatures.new("CopyThat")
    rig = bpy.data.objects.new("CopyThat Rig", armature)
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
    rig.rigmoves.seat = flat(rig.matrix_world)
    rig.rigmoves.seated = True
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
    # Moved on purpose, with every child held where it stood: nothing a move
    # remembers has gone anywhere, so this is where the rig stands now.
    rig.rigmoves.seat = flat(rig.matrix_world)
    rig.rigmoves.seated = True
    if was_mode != "OBJECT":
        try:
            bpy.ops.object.mode_set(mode=was_mode)
        except RuntimeError:
            pass
    if was_active is not None and was_active is not rig:
        view_layer.objects.active = was_active
    return True


def copied_groups(rig, obj, keep):
    """The vertex groups on an object for bones of other parts of this rig.

    A part copied after it was bound - Shift+D - brings its binding with it:
    its vertex group at full weight, named after its own bone. Bound to a
    bone of its own as well, the copy is then moved by both bones and lands
    half way between them. That looks right for exactly as long as the two
    bones do the same thing: mirror one, or send it ahead, and the copy runs
    straight or stands still. Only bones this add-on made count - a group for
    any other bone is somebody's own weights, and is left alone.
    """
    out = []
    for group in obj.vertex_groups:
        bone = rig.data.bones.get(group.name)
        if group.name != keep and bone is not None and bone.get(PART_MARK):
            out.append(group.name)
    return out


def own_binding(rig, obj, keep):
    """Leave a bound object moved by its own bone and nothing else, and say
    how many other bones were moving it as well.

    Its mesh is made its own first, if another object shares it. Vertex
    groups live on the mesh, so two linked copies - Alt+D - share them too:
    binding the second gave the first its group as well, and each was moved
    by both bones. Armature modifiers this add-on left pointing at a rig that
    has since been deleted go too; they do nothing but clutter the stack.
    """
    # A fake user alone does not make a mesh shared.
    if (obj.type == "MESH" and obj.data is not None
            and obj.data.users - int(obj.data.use_fake_user) > 1):
        obj.data = obj.data.copy()
    stale = copied_groups(rig, obj, keep)
    for name in stale:
        obj.vertex_groups.remove(obj.vertex_groups[name])
    if stale:
        # Blender 4.5 and 5.0 do not work the mesh out again when a group is
        # taken off it from Python (5.2 does), so a healed copy went on showing
        # the other bone's pull until the file was opened again.
        obj.data.update_tag()
    for modifier in list(obj.modifiers):
        if (modifier.type == "ARMATURE" and modifier.object is None
                and modifier.name.startswith("RigMoves")):
            obj.modifiers.remove(modifier)
    return len(stale)


def heal_bindings(rig, data):
    """Every bound object moved by its own bone only - for files bound before
    copies were looked out for. Returns how many were being moved by another
    part's bone as well."""
    healed = 0
    for move in data.moves:
        for part in bound_parts(move):
            obj = bpy.data.objects.get(part.name)
            # Two parts sharing a mesh show up here as well: each carries the
            # other's group, and the first one healed takes a mesh of its own.
            if (obj is not None and obj.type == "MESH"
                    and copied_groups(rig, obj, part.bone_name)):
                own_binding(rig, obj, part.bone_name)
                healed += 1
    return healed


def bind_object(rig, obj, bone_name):
    """Tie a whole object to one bone, and let it travel with the rig.

    A vertex group at full weight rather than bone parenting: bone parenting
    hangs a child off the bone's *tail* and through its pose, which is a
    second frame of reference to keep straight for no gain on a rigid part.
    One group, one modifier, and the object's own transform is left alone.
    One group only: a copy of a bound part arrives with that part's as well.
    """
    own_binding(rig, obj, bone_name)
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


def pose_bone_at(rig, part, target, above=None):
    """Put a bound object's bone where the object's world matrix should be.

    The modifier moves the mesh by the bone's travel from its rest, so to land
    the object on `target` the bone has to carry exactly the difference
    between that and where the object stood when it was bound - less what
    the bones above it carry it by already, `above`, for a part that follows
    another. Worked out straight into the bone's own channels, so it does not
    wait on Blender to have evaluated the parent first. Returns the pose.
    """
    pose_bone = rig.pose.bones.get(part.bone_name)
    if pose_bone is None:
        return None
    rest = pose_bone.bone.matrix_local
    world = rig.matrix_world
    travel = (world.inverted_safe() @ target @ as_matrix(part.before).inverted_safe()
              @ world)
    if above is not None:
        travel = above.inverted_safe() @ travel
    basis = rest.inverted_safe() @ travel @ rest
    pose_bone.matrix_basis = basis
    return basis


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
    """Give every loose object a bone, bind it, and write its two poses.

    Returns how many were bound, and the names of the bones made for them.
    """
    jobs = []
    for move in data.moves:
        pending = [p for p in loose_parts(move) if p.has_before]
        if pending:
            jobs.append((move, pending))
    if not jobs:
        return 0, set()

    if not activate(context, rig):
        return 0, set()
    # A bound part that follows one of these hangs from its object, and would
    # be carried off its own Before when that one is stood on its. Back on
    # the rig until the bones are hung; hang_objects hangs it again after.
    waiting = {p.name for _move, pending in jobs for p in pending}
    for move in data.moves:
        for part in bound_parts(move):
            obj = bpy.data.objects.get(part.name)
            if (obj is not None and obj.get(FOLLOW_MARK) and obj.parent is not None
                    and obj.parent.name in waiting):
                keep_world(obj, rig_holding(obj) or rig)
                del obj[FOLLOW_MARK]
    # Out of any object hierarchy first - the user's own, remembered to give
    # back, or the one hang made - or standing a parent on its Before
    # would carry its children off theirs. Bones carry them from here.
    for _move, pending in jobs:
        for part in pending:
            obj = bpy.data.objects.get(part.name)
            if obj is None or obj.parent is None or obj.parent is rig:
                continue
            if not obj.get(FOLLOW_MARK):
                part.home_parent = obj.parent.name
            else:
                del obj[FOLLOW_MARK]
            keep_world(obj, None)
    # Stand every object where Before was recorded, so its bone is made there
    # and that pose becomes the rig's rest.
    for _move, pending in jobs:
        for part in pending:
            obj = bpy.data.objects.get(part.name)
            if obj is not None:
                obj.matrix_world = as_matrix(part.before)
    context.view_layer.update()

    if not activate(context, rig):
        return 0, set()
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
            # On its pivot - its origin unless one was picked - which the
            # object is standing on, at Before, right now.
            head = into @ pivot_world(part)
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
    return made, {p.bone_name for _move, pending in jobs for p in pending
                  if p.bone_name}


# ---------------------------------------------------------------------------
# riders: objects that copy a part's move from where they stand
#
# A flower is eight petals doing one thing, each from its own place: open
# outwards. Recorded once on one petal, the others ride along - whatever the
# leader does to its own left, a rider does to *its* own left, not the
# leader's.
#
# Each rider gets a bone turned from the rider exactly as the leader's bone is
# turned from the leader, and that bone plays a copy of the leader's channels.
# The same channels on a bone turned the same way are the same move, seen from
# the rider - at every point along the path, not only at the recorded poses,
# so steps, delays and speeds all carry over for nothing.


def standing(matrix):
    """Where something stands and which way it faces, without its size - and
    whether it is a mirror image.

    A half-size petal is still meant to travel as far as the leader does, so
    scale is kept out of the frames a move is carried between. A mirrored copy
    - negative scale, as Ctrl+M leaves one - faces a left-handed way no bone
    can stand in. Its X is turned round to give a frame a bone can have, and
    the caller is told, so the move can be mirrored back to match.
    """
    turn = matrix.to_3x3()
    mirrored = turn.determinant() < 0.0
    if mirrored:
        for row in range(3):
            turn[row][0] = -turn[row][0]
    frame = turn.normalized().to_4x4()
    frame.translation = matrix.to_translation()
    return frame, mirrored


def frame_of(matrix):
    return standing(matrix)[0]


def leader_frame(rig, leader):
    """The frame a leader's move is measured in, in world space, and whether
    the leader is a mirror image."""
    if leader.kind == "OBJECT":
        return standing(as_matrix(leader.before))
    bone = rig.data.bones.get(part_bone(leader))
    return standing(rig.matrix_world @ bone.matrix_local)


def leader_of(move, rider):
    """The part a rider copies, if it is still a part that leads."""
    leader = move.parts.get(rider.leader)
    if leader is None or leader.leader:
        return None
    return leader


def riding_on(move, rider):
    """The rider this one rides on, while that one still copies the very part
    this one's leader follows - else None, and it hangs where its leader
    hangs. A Follows changed since the copy was made undoes the pairing."""
    up = move.parts.get(rider.rides_on) if rider.rides_on else None
    leader = leader_of(move, rider)
    if (up is None or not up.leader or up.name == rider.name or leader is None
            or not leader.follows or up.leader != leader.follows):
        return None
    return up


def copy_root(move, rider):
    """The first joint of the copy a rider belongs to: the one whose Lead and
    Mirror the whole copy plays by. A rider on its own is its own."""
    seen = {rider.name}
    while True:
        up = riding_on(move, rider)
        if up is None or up.name in seen:
            return rider
        seen.add(up.name)
        rider = up


def copy_of(move, root):
    """A copy's riders, its first joint first, each before the ones riding on
    it."""
    out, names = [root], {root.name}
    for here_ in out:
        for part in move.parts:
            if part.leader and part.name not in names:
                up = riding_on(move, part)
                if up is not None and up.name == here_.name:
                    out.append(part)
                    names.add(part.name)
    return out


def rider_holder(move, rider):
    """The part whose bone a rider's bone hangs from - None for the rig's root.

    The copy of the part its leader follows, riding in the same copy: the
    joint before it, in a copied finger. Failing that, the very part its
    leader follows, so a second claw on the same arm swings with that arm.
    A rider of a part that follows nothing hangs from the root, as ever.
    """
    leader = leader_of(move, rider)
    target = move.parts.get(leader.follows) if leader is not None and leader.follows else None
    if target is None or target.leader:
        return None
    return riding_on(move, rider) or target


def reflection(axis):
    """A mirror across the plane square to one of the three axes."""
    return Matrix.Diagonal([-1.0 if name == axis else 1.0 for name in AXES])


def copy_mirror(rig, move, leader, root, axis):
    """A copy's Mirror - a reflection across the plane square to one of the
    first joint's own axes - as it reads in the own axes of `leader`, the part
    one of its joints copies.

    Every joint of a copied finger has to mirror across that one plane. Taken
    across each joint's own axis, as a lone rider's is, a finger whose segments
    do not all face the same way - a middle one rolled about its own length -
    mirrors each joint across a different plane, and zigzags. So the plane is
    the first joint's, carried into each joint's own axes. Where the axes
    agree, which is nearly always, it is the plain reflection.
    """
    top = leader_of(move, root)
    if top is None or top.name == leader.name:
        return reflection(axis)
    normal = (leader_frame(rig, top)[0].to_3x3()
              @ Vector([1.0 if name == axis else 0.0 for name in AXES]))
    here = leader_frame(rig, leader)[0].to_3x3().transposed() @ normal
    if here.length < 1e-9:
        return reflection(axis)
    here.normalize()
    for number, name in enumerate(AXES):
        if abs(abs(here[number]) - 1.0) < 1e-5:
            return reflection(name)
    return Matrix.Identity(3) - 2.0 * Matrix(((here.x * here.x, here.x * here.y, here.x * here.z),
                                              (here.y * here.x, here.y * here.y, here.y * here.z),
                                              (here.z * here.x, here.z * here.y, here.z * here.z)))


def rider_reflection(rig, move, leader, rider):
    """The mirror between a leader and a rider, in their own axes - None
    when there is none. Whether each is a mirror image is its own; the Mirror
    setting is the copy's, so every joint of a copied finger mirrors across
    the same plane."""
    lead_mirrored = leader_frame(rig, leader)[1]
    mirrored = standing(as_matrix(rider.before))[1]
    local = Matrix.Identity(3)
    if mirrored != lead_mirrored:
        local = local @ reflection("X")
    root = copy_root(move, rider) if rider.rides_on else rider
    if root.mirror in AXES:
        local = local @ copy_mirror(rig, move, leader, root, root.mirror)
    return None if local == Matrix.Identity(3) else local


def rider_turn(rig, move, leader, rider):
    """What a rider's copy of the path is turned by, in the leader bone's own
    axes - None for a plain copy.

    A rider moves as its leader would, standing where the rider stands. If one
    of the two is a mirror image of the other, that includes the mirroring:
    each frame here was kept right-handed by turning a mirror image's X round,
    so it is put back as a mirror across X - and two of them, a mirrored rider
    of a mirrored leader, cancel. The Mirror setting adds one more, across
    the axis it names, for a rider that faces the other way without being a
    mirror image: the second of a pair of doors.
    """
    local = rider_reflection(rig, move, leader, rider)
    if local is None:
        return None
    lead_frame = leader_frame(rig, leader)[0]
    bone = rig.data.bones[part_bone(leader)]
    rest = (rig.matrix_world @ bone.matrix_local).to_3x3().normalized()
    into_bone = rest.transposed() @ lead_frame.to_3x3()
    return into_bone @ local @ into_bone.transposed()


def same_matrix(a, b, tolerance=1e-5):
    return max(abs(x - y) for row_a, row_b in zip(a, b)
               for x, y in zip(row_a, row_b)) <= tolerance


def holder_bone(move, rider, bones):
    """The name of the bone a rider's bone should hang from, among `bones` -
    the rig's bones, or its edit bones while those are being changed."""
    holder = rider_holder(move, rider)
    names = []
    if holder is not None:
        names.append(holder.bone_name)
        if holder.leader:
            # The joint before it in its copy has no bone yet, or none any
            # more: hung where its leader hangs, rather than from nothing.
            names.append(move.parts[leader_of(move, rider).follows].bone_name)
    names.append("Root")
    for name in names:
        if name and name != rider.bone_name and bones.get(name) is not None:
            return name
    first = bones[0].name if len(bones) else ""
    return first if first != rider.bone_name else ""


def bind_riders(context, rig, data):
    """Give every new rider its bone, turned like its leader's, and bind it -
    and turn an existing rider's bone again when its leader's has moved, and
    hang it again when what it should hang from has changed.

    After bind_loose and the pivots, so a leader that was a loose object a
    moment ago, or whose pivot has just been picked, already has the bone its
    riders are turned from. A rider's own pivot is its leader's, carried over.
    Its bone hangs where rider_holder says: from the root, or for a copied
    finger from the copy of the joint before it.
    """
    world = rig.matrix_world
    into = world.inverted_safe()
    fresh, moved, riders = [], [], []
    for move in data.moves:
        for _index, rider in riders_of(move):
            leader = leader_of(move, rider)
            if (not rider.has_before or leader is None
                    or rig.data.bones.get(part_bone(leader)) is None
                    or bpy.data.objects.get(rider.name) is None):
                continue
            bone = rig.data.bones[part_bone(leader)]
            # The leader's bone as the leader sees it, then stood on the rider.
            own_frame = frame_of(as_matrix(rider.before))
            lead_frame = leader_frame(rig, leader)[0].inverted_safe()
            carried = own_frame @ lead_frame @ world @ bone.matrix_local
            seat = frame_of(into @ carried)
            # A mirrored rider turns about the mirror image of its leader's
            # pivot, not the pivot carried straight over: off the mirror's
            # plane the two are apart, and the rider swung about the wrong
            # point and ended up out of place.
            local = rider_reflection(rig, move, leader, rider)
            if local is not None:
                seat.translation = into @ (own_frame @ local.to_4x4() @ lead_frame
                                           @ world @ bone.head_local)
            riders.append((move, rider))
            own = rig.data.bones.get(rider.bone_name) if rider.bone_name else None
            if own is None:
                fresh.append((rider, leader, seat, bone.length))
            elif not same_matrix(own.matrix_local, seat):
                moved.append((rider, seat))
    # Hanging changes too: a Follows set on a leader since the last Build, or
    # a rig from before copies rode on one another.
    rehung = []
    for move, rider in riders:
        own = rig.data.bones.get(rider.bone_name) if rider.bone_name else None
        if own is not None:
            have = own.parent.name if own.parent is not None else ""
            if have != holder_bone(move, rider, rig.data.bones):
                rehung.append(rider)
    if not (fresh or moved or rehung):
        return 0

    for rider, _leader, _seat, _length in fresh:
        bpy.data.objects[rider.name].matrix_world = as_matrix(rider.before)
    context.view_layer.update()

    if not activate(context, rig):
        return 0
    bpy.ops.object.mode_set(mode="EDIT")
    edit = rig.data.edit_bones
    # A bone's rest can change under a bound object without moving it: at rest
    # the modifier moves nothing, and the path is copied onto the new rest
    # after this.
    for rider, seat in moved:
        bone = edit.get(rider.bone_name)
        if bone is not None:
            bone.matrix = seat
    for rider, _leader, seat, length in fresh:
        bone = edit.new(rider.name)
        bone.head = Vector((0.0, 0.0, 0.0))
        bone.tail = Vector((0.0, max(length, 1e-3), 0.0))
        bone.matrix = seat
        bone.use_deform = True
        rider.bone_name = bone.name
    # Hung once every bone is there, as the joint a rider hangs from may
    # have been made a moment ago. Hanging moves no bone: only the pose to
    # come is carried, and that is a copy of the leader's, which already
    # plays against the part its leader hangs from.
    for move, rider in riders:
        bone = edit.get(rider.bone_name)
        if bone is not None:
            want = holder_bone(move, rider, edit)
            bone.use_connect = False
            bone.parent = edit.get(want) if want else None
    bpy.ops.object.mode_set(mode="OBJECT")

    for rider, leader, _seat, _length in fresh:
        obj = bpy.data.objects[rider.name]
        bind_object(rig, obj, rider.bone_name)
        # A copy of a follower comes marked as hung; a rider never hangs.
        if obj.get(FOLLOW_MARK) is not None:
            del obj[FOLLOW_MARK]
        rig.data.bones[rider.bone_name][PART_MARK] = True
        pose_bone = rig.pose.bones[rider.bone_name]
        pose_bone.rotation_mode = rig.pose.bones[part_bone(leader)].rotation_mode
        pose_bone.matrix_basis = Matrix()
    context.view_layer.update()
    return len(fresh)


def copy_curve(bag, curve, data_path):
    """One channel, key for key, under another path."""
    copy = bag.fcurves.new(data_path, index=curve.array_index)
    copy.keyframe_points.add(len(curve.keyframe_points))
    for was, now in zip(curve.keyframe_points, copy.keyframe_points):
        now.co = was.co
        now.interpolation = was.interpolation
        now.handle_left_type = was.handle_left_type
        now.handle_right_type = was.handle_right_type
        now.handle_left = was.handle_left
        now.handle_right = was.handle_right
    copy.update()


def write_turned(bag, source, target, turn, rotation):
    """A leader's location - and its quaternion, if `rotation` - turned by an
    orthogonal map, written onto a rider's channels.

    Both are linear in the numbers on the curves - a mirror is - so keying the
    turned values at every frame either has a key on reproduces the turned
    move at every frame in between as well, not only at the keys.
    """
    channels = ["location"] + (["rotation_quaternion"] if rotation else [])
    curves = {(c.data_path[len(source):], c.array_index): c
              for c in bag.fcurves if c.data_path.startswith(source)}
    used = [c for (channel, _index), c in curves.items() if channel in channels]
    frames = sorted({p.co[0] for c in used for p in c.keyframe_points})
    if not frames:
        return
    # Straight keys mirror exactly through the keys alone. A shaped one - a
    # key eased by hand in the graph editor - bends between keys, and a
    # mirrored copy keyed only on the keys would run straight there; so it is
    # keyed every half frame instead, closer than anyone can see.
    if any(p.interpolation != "LINEAR" for c in used for p in c.keyframe_points[:-1]):
        first, last = frames[0], frames[-1]
        count = max(1, int((last - first) / 0.5))
        frames = sorted(set(frames) | {first + (last - first) * n / count
                                       for n in range(count + 1)})
    # A mirror turns a rotation the same way as the half turn that is minus
    # it, and the half turn is one a quaternion can hold.
    proper = turn * (1.0 if turn.determinant() > 0.0 else -1.0)
    spin = proper.to_quaternion()
    layout = [("location", i) for i in range(3)]
    if rotation:
        layout += [("rotation_quaternion", i) for i in range(4)]
    rows = []
    for frame in frames:
        def value(channel, index, rest):
            curve = curves.get((channel, index))
            if curve is None or not len(curve.keyframe_points):
                return rest
            return curve.evaluate(frame)
        row = list(turn @ Vector([value("location", i, 0.0) for i in range(3)]))
        if rotation:
            held = Quaternion([value("rotation_quaternion", i, (1.0, 0.0, 0.0, 0.0)[i])
                               for i in range(4)])
            row += list(spin @ held @ spin.conjugated())
        rows.append(row)
    for column, (channel, index) in enumerate(layout):
        curve = bag.fcurves.new(target + channel, index=index)
        curve.keyframe_points.add(len(frames))
        for point, frame, row in zip(curve.keyframe_points, frames, rows):
            point.co = (frame, row[column])
            point.interpolation = "LINEAR"
        curve.update()


def copy_path(rig, move, leader, rider):
    """Give a rider its leader's channels, key for key - turned, when the rider
    mirrors its leader."""
    _action, _slot, bag = action_bits(move, make=True)
    if bag is None:
        return
    source = bone_path(part_bone(leader), "")
    target = bone_path(part_bone(rider), "")
    for curve in list(bag.fcurves):
        if curve.data_path.startswith(target):
            bag.fcurves.remove(curve)
    leading = rig.pose.bones.get(part_bone(leader))
    originals = [c for c in bag.fcurves if c.data_path.startswith(source)]
    turn = rider_turn(rig, move, leader, rider) if leading is not None else None
    turned = set()
    if turn is not None:
        # Rotation is turned only as a quaternion, the mode this add-on's own
        # bones use; any other mode is copied as it is.
        rotation = leading.rotation_mode == "QUATERNION"
        write_turned(bag, source, target, turn, rotation)
        turned = {"location", "rotation_quaternion"} if rotation else {"location"}
    for curve in originals:
        channel = curve.data_path[len(source):]
        if channel not in turned:
            copy_curve(bag, curve, target + channel)
    pose_bone = rig.pose.bones.get(part_bone(rider))
    if pose_bone is not None and leading is not None:
        pose_bone.rotation_mode = leading.rotation_mode


def follow_leaders(rig, data):
    """Copy every leader's path onto its riders, as it stands now.

    Every build, because the leader's path is recorded and re-recorded on
    its own - a step added, After taken again - and a rider is only ever its
    leader's path, never anything of its own. Returns the riders whose leader
    has gone.
    """
    lost = []
    for move in data.moves:
        for _index, rider in riders_of(move):
            leader = leader_of(move, rider)
            if leader is None:
                lost.append(rider.name)
            elif rider.bone_name:
                copy_path(rig, move, leader, rider)
    return lost


# ---------------------------------------------------------------------------
# copies of a chain: a finger riding along with a finger
#
# Four fingers, one of them recorded. The other three are copies of it, joint
# for joint, so each joint of a copy rides along with the matching joint of
# the recorded finger - and hangs from the copy of the joint before it, as
# the recorded one hangs. Every joint then turns as its own does, about its
# own knuckle, carried by the joints before it: the whole copy curls, from
# where it stands. Which object copies which joint is read off where they
# stand and which way they face, so the copies need no names and no order.


def chain_of(move, part):
    """Every part of the chain a part belongs to, parents first: the part at
    its root and every part that hangs below that one. Riders aside."""
    own = {p.name: p for p in chain_parts(move)}
    if part.name not in own:
        return [part]
    root, seen = part, {part.name}
    while root.follows in own and root.follows not in seen:
        seen.add(root.follows)
        root = own[root.follows]
    out, names = [root], {root.name}
    for here_ in out:
        for other in own.values():
            if other.follows == here_.name and other.name not in names:
                out.append(other)
                names.add(other.name)
    return out


def body(obj, matrix):
    """(turn, middle, size) of an object standing at `matrix`: which way it
    faces, without its size and with a mirror image kept as one; where the
    middle of its mesh is; and how big that is - all in the world."""
    corners = corners_of(obj)
    low = Vector([min(c[axis] for c in corners) for axis in range(3)])
    high = Vector([max(c[axis] for c in corners) for axis in range(3)])
    turn = matrix.to_3x3().normalized()
    return (turn, matrix @ ((low + high) * 0.5),
            max((matrix.to_3x3() @ (high - low)).length, 1e-6))


def part_body(part):
    """A part's body where it stands at Before, or None without its object."""
    obj = bpy.data.objects.get(part.name)
    return body(obj, as_matrix(part.before)) if obj is not None else None


def carried_to(source, target, point):
    """Where `point`, near the body `source`, lands near the body `target` -
    turned and sized as `target` is against `source`."""
    turn = target[0] @ source[0].inverted_safe()
    return target[1] + (target[2] / source[2]) * (turn @ (point - source[1]))


def alike(size, wanted):
    """Whether two sizes are near enough for one to be a copy of the other."""
    return 0.5 <= size / max(wanted, 1e-9) <= 2.0


def match_copies(chain, objects):
    """Sort objects into copies of a chain, joint for joint.

    A copy is grown from one pair - an object and the joint it copies - by
    carrying the chain over from that joint to that object, one joint at a
    time, and taking whatever object stands where each next joint lands: near
    enough, against how far apart the two joints are, and about its size. The
    fullest copies are taken first, and of those the closest. Returns the
    copies, each a dict from a joint's name to its object, and the objects
    left over, which copy no more than one joint each.
    """
    shapes = {part.name: part_body(part) for part in chain}
    if any(shape is None for shape in shapes.values()):
        return [], list(objects)
    seen = {obj.name: (obj, body(obj, obj.matrix_world)) for obj in objects}
    above_ = {part.name: part.follows for part in chain if part.follows in shapes}
    near = {name: [other for other, up in above_.items() if up == name]
            + ([above_[name]] if name in above_ else []) for name in shapes}

    def grow(seed, first, free):
        match, cost, todo = {seed: first}, 0.0, [seed]
        while todo:
            joint = todo.pop(0)
            source, target = shapes[joint], seen[match[joint]][1]
            ratio = target[2] / source[2]
            for other in near[joint]:
                if other in match:
                    continue
                spot = carried_to(source, target, shapes[other][1])
                reach = max(0.5 * ratio * (shapes[other][1] - source[1]).length, 1e-6)
                best, gap, taken = None, reach, set(match.values())
                for name in free:
                    there = seen[name][1]
                    if (name not in taken and alike(there[2], shapes[other][2] * ratio)
                            and (there[1] - spot).length <= gap):
                        best, gap = name, (there[1] - spot).length
                if best is not None:
                    match[other] = best
                    cost += gap / reach
                    todo.append(other)
        return match, cost

    copies, free = [], [obj.name for obj in objects]
    while len(free) > 1:
        best = None
        for first in free:
            for seed in shapes:
                if not alike(seen[first][1][2], shapes[seed][2]):
                    continue
                match, cost = grow(seed, first, free)
                if len(match) > 1 and (best is None or (-len(match), cost) < best[0]):
                    best = ((-len(match), cost), match)
            # A whole copy standing exactly where it should is as good as it
            # gets; no need to try every other pair against it.
            if best is not None and -best[0][0] == len(shapes) and best[0][1] < 1e-3:
                break
        if best is None:
            break
        copies.append({joint: seen[name][0] for joint, name in best[1].items()})
        free = [name for name in free if name not in best[1].values()]
    return copies, [seen[name][0] for name in free]


def ride_on_existing(move, leader, seat, among=None):
    """The rider copying the part `leader` follows that stands where that
    part's copy would stand, seen from `seat` - the body of a rider of
    `leader`. For a joint added to a copy whose other joints ride already.
    `among` narrows the riders looked at to those names. Empty for none."""
    up = move.parts.get(leader.follows) if leader.follows else None
    lead = part_body(leader)
    top = part_body(up) if up is not None and not up.leader else None
    if lead is None or top is None:
        return ""
    spot = carried_to(lead, seat, top[1])
    best, gap = "", max(0.5 * (seat[2] / lead[2]) * (top[1] - lead[1]).length, 1e-6)
    for other in move.parts:
        if other.leader != up.name or (among is not None and other.name not in among):
            continue
        there = part_body(other)
        if there is not None and (there[1] - spot).length <= gap:
            best, gap = other.name, (there[1] - spot).length
    return best


def adopt_riders(move, names):
    """Let riders already there ride on new ones that copy the joint before
    them - a finger's first joint added to a copy whose other joints ride
    already. `names` are the new riders. Returns how many were taken up."""
    taken = 0
    for part in move.parts:
        if not part.leader or part.name in names or riding_on(move, part) is not None:
            continue
        leader, seat = leader_of(move, part), part_body(part)
        if leader is None or seat is None:
            continue
        up = ride_on_existing(move, leader, seat, among=set(names))
        if up:
            part.rides_on = up
            taken += 1
    return taken


# ---------------------------------------------------------------------------
# reading a path without playing it


def basis_at(bag, bone_name, rotation_mode, frame):
    """A bone's pose on a path at one frame, read straight off the curves."""
    prefix = bone_path(bone_name, "")

    def value(channel, index, rest):
        curve = curve_for(bag, prefix + channel, index)
        if curve is None or not len(curve.keyframe_points):
            return rest
        return curve.evaluate(frame)

    location = Vector([value("location", i, 0.0) for i in range(3)])
    if rotation_mode == "QUATERNION":
        turn = Quaternion([value("rotation_quaternion", i, (1.0, 0.0, 0.0, 0.0)[i])
                           for i in range(4)]).normalized().to_matrix()
    elif rotation_mode == "AXIS_ANGLE":
        held = [value("rotation_axis_angle", i, (0.0, 0.0, 1.0, 0.0)[i]) for i in range(4)]
        axis = Vector(held[1:])
        turn = (Matrix.Rotation(held[0], 3, axis.normalized()) if axis.length > 1e-9
                else Matrix.Identity(3))
    else:
        turn = Euler([value("rotation_euler", i, 0.0) for i in range(3)],
                     rotation_mode).to_matrix()
    size = Matrix.Diagonal([value("scale", i, 1.0) for i in range(3)])
    return Matrix.Translation(location) @ (turn @ size).to_4x4()


def put_key(curve, frame, value):
    """Set a curve's key on this frame, adding a straight one if it has none."""
    for point in curve.keyframe_points:
        if abs(point.co[0] - frame) < 1e-4:
            shift = value - point.co[1]
            point.co[1] = value
            point.handle_left[1] += shift
            point.handle_right[1] += shift
            return
    point = curve.keyframe_points.insert(frame, value, options={"FAST"})
    point.interpolation = "LINEAR"


def key_frames(bag, bone_name):
    """Every frame a bone has a key on, in order."""
    prefix = bone_path(bone_name, "")
    return sorted({p.co[0] for c in bag.fcurves if c.data_path.startswith(prefix)
                   for p in c.keyframe_points})


def deformation(rig, bag, bone_name, frame, fresh=None, parents=None):
    """What one of our bones does to the world at a frame of its path - in
    armature space, with whatever the bones above it carry it by.

    `fresh` holds bones whose pose has been worked out and is not on the path
    yet, or every bone's pose as it stands; `parents`, a hierarchy about to
    be made, in place of the one the rig has. A bone with nothing on this
    path stands at rest, as every move but the one being played does.
    `frame` may be a function of the bone's name, for bones that stand on
    different frames of the path at once - a follower with a delay.
    """
    fresh = fresh if fresh is not None else {}
    parents = parents if parents is not None else {}
    out = Matrix.Identity(4)
    seen, name = set(), bone_name
    while name and name not in seen:
        seen.add(name)
        bone = rig.data.bones.get(name)
        if bone is None:
            break
        if name in fresh:
            basis = fresh[name]
        elif bag is not None and name in rig.pose.bones:
            at = frame(name) if callable(frame) else frame
            basis = basis_at(bag, name, rig.pose.bones[name].rotation_mode, at)
        else:
            basis = Matrix.Identity(4)
        rest = bone.matrix_local
        out = rest @ basis @ rest.inverted_safe() @ out
        if name in parents:
            name = parents[name]
        else:
            name = bone.parent.name if bone.parent is not None else ""
    return out


def above(rig, bag, bone_name, frame, fresh=None, parents=None):
    """What the bones a bone hangs from carry it by, at a frame."""
    bone = rig.data.bones.get(bone_name)
    if parents is not None and bone_name in parents:
        name = parents[bone_name]
    else:
        name = bone.parent.name if bone is not None and bone.parent is not None else ""
    if not name:
        return Matrix.Identity(4)
    return deformation(rig, bag, name, frame, fresh, parents)


def write_basis_keys(bag, bone_name, rotation_mode, rows):
    """Key a bone's whole pose, one matrix per frame, into its channels.

    A quaternion is kept on the same side as the one before it, and an euler
    turned as little as it can be, or the way between two keys would go the
    long way round.
    """
    turn_before, euler_before = None, None
    for frame in sorted(rows):
        location, turn, size = rows[frame].decompose()
        if rotation_mode == "QUATERNION":
            if turn_before is not None and turn_before.dot(turn) < 0.0:
                turn.negate()
            turn_before = turn.copy()
            held = [("rotation_quaternion", i, turn[i]) for i in range(4)]
        elif rotation_mode == "AXIS_ANGLE":
            axis, angle = turn.to_axis_angle()
            held = [("rotation_axis_angle", 0, angle)]
            held += [("rotation_axis_angle", i + 1, axis[i]) for i in range(3)]
        else:
            euler = (turn.to_euler(rotation_mode, euler_before) if euler_before is not None
                     else turn.to_euler(rotation_mode))
            euler_before = euler.copy()
            held = [("rotation_euler", i, euler[i]) for i in range(3)]
        channels = ([("location", i, location[i]) for i in range(3)] + held
                    + [("scale", i, size[i]) for i in range(3)])
        for path, index, value in channels:
            put_key(curve_for(bag, bone_path(bone_name, path), index, make=True),
                    frame, value)
    prefix = bone_path(bone_name, "")
    for curve in bag.fcurves:
        if curve.data_path.startswith(prefix):
            curve.update()


# ---------------------------------------------------------------------------
# followers: a part that hangs from another, like the joints of a finger
#
# A follower's bone hangs from the bone of the part it follows, so it goes
# wherever that part takes it and plays its own move on top. Its path is kept
# relative to its parent: every recorded pose lands where it was put, and in
# between each joint turns about its own knuckle while the joint before
# carries it - a finger curls, rather than its pieces sliding apart.


def pose_frames(move):
    """The frames a move's poses are recorded on: Before, every step, After."""
    return sorted({float(FIRST_FRAME), float(last_frame(move))}
                  | {float(s.frame) for s in move.steps if s.done})


def follow_depth(move, part):
    """How many parts a part hangs below, through its follows."""
    depth, seen, name = 0, {part.name}, part.follows
    while name and name not in seen:
        seen.add(name)
        depth += 1
        above_part = move.parts.get(name)
        name = above_part.follows if above_part is not None else ""
    return depth


def bone_depth(rig, name):
    """How many bones a bone hangs below, as the rig is now."""
    depth, seen = 0, set()
    bone = rig.data.bones.get(name)
    while bone is not None and bone.parent is not None and bone.name not in seen:
        seen.add(bone.name)
        depth += 1
        bone = bone.parent
    return depth


def follow_order(move, parts):
    """Parts ordered so that every part comes after the one it follows."""
    return sorted(parts, key=lambda part: follow_depth(move, part))


def wanted_parent(rig, move, part, part_bones):
    """The bone a part's bone should hang from.

    The bone of the part it follows; otherwise the one it hangs from now -
    unless that is a part's bone it no longer follows, when it goes back to
    the rig's root.
    """
    bone = rig.data.bones.get(part.bone_name)
    have = bone.parent.name if bone is not None and bone.parent is not None else ""
    target = move.parts.get(part.follows) if part.follows else None
    if (target is not None and target.name != part.name and not target.leader
            and target.bone_name in rig.data.bones):
        return target.bone_name
    if have in part_bones:
        root = rig.data.bones.get("Root")
        return root.name if root is not None else ""
    return have


def stands_still(rig, bag, bone_name):
    """Whether a bone is at rest at every key it has - posed by nothing."""
    mode = rig.pose.bones[bone_name].rotation_mode
    return all(same_matrix(basis_at(bag, bone_name, mode, frame), Matrix.Identity(4))
               for frame in key_frames(bag, bone_name))


def our_part_bones(data):
    return {p.bone_name for m in data.moves for p in m.parts
            if p.kind == "OBJECT" and p.bone_name}


def parent_pending(rig, data, move):
    """Whether any part of a move waits on a Build to hang where it follows.

    Its object as well as its bone: a follower whose object does not hang
    from its leader's is left behind when the leader is dragged - which is
    how every follower of a file built before objects were hung stands.
    """
    part_bones = our_part_bones(data)
    for part in bound_parts(move):
        bone = rig.data.bones.get(part.bone_name)
        if part.leader or bone is None:
            continue
        have = bone.parent.name if bone.parent is not None else ""
        if wanted_parent(rig, move, part, part_bones) != have:
            return True
        obj = bpy.data.objects.get(part.name)
        target = bpy.data.objects.get(part.follows) if part.follows else None
        if obj is None or target is obj:
            continue
        if target is not None and obj.parent is not target:
            return True
        if target is None and obj.get(FOLLOW_MARK):
            return True
    return False


def apply_parents(context, rig, data, new=()):
    """Hang every follower's bone from the bone of the part it follows - and
    let go of one that no longer follows - keeping every recorded pose.

    Every pose to keep is read before anything changes. Then, parents first,
    each bone is re-keyed against what its new parent does at each of its
    keys - its parent's own keys already redone - and last the bones are
    hung. A new part bound this Build hangs from the root until here, so its
    two poses are the plain ones it was recorded with. `new` names those
    bones: they keep only their own keys, Before and After, as no step was
    ever recorded for them - so in between they turn on their own joint
    while what they follow carries them, steps and all.

    A part with no After of its own that has never moved - added to a built
    move and not posed yet - has nothing to keep. It was keyed standing
    still only because every bound part is keyed, and kept still in the
    world it would stay behind as what it follows moves off. It rides along
    instead: no move of its own, wherever its parent goes.
    """
    part_bones = our_part_bones(data)
    jobs, parents = [], {}
    for move in data.moves:
        for part in bound_parts(move):
            bone = rig.data.bones.get(part.bone_name)
            if part.leader or bone is None:
                continue
            have = bone.parent.name if bone.parent is not None else ""
            want = wanted_parent(rig, move, part, part_bones)
            if want != have:
                jobs.append((move, part, want))
                parents[part.bone_name] = want
    if not jobs:
        return 0, 0, []
    # Kept on every pose of the move - Before, every step, After - and not
    # only the bone's own keys: a part that hangs below it was recorded
    # against wherever it stood at those, keyed or not. Not on the in-between
    # keys a curve lays, which would stay behind as turns of their own;
    # bake_curves lays those again after this.
    frames = {}
    kept = {}
    riding = set()
    for move, part, want in jobs:
        _action, _slot, bag = action_bits(move)
        if bag is None:
            continue
        name = part.bone_name
        if (part.kind == "OBJECT" and not part.has_after and want in part_bones
                and stands_still(rig, bag, name)):
            riding.add(name)
            frames[name] = key_frames(bag, name)
            continue
        prefix = bone_path(name, "")
        turned = {p.co[0] for c in bag.fcurves if c.data_path.startswith(prefix)
                  and not c.data_path.endswith("location") for p in c.keyframe_points}
        frames[name] = (key_frames(bag, name) if name in new
                        else sorted(set(pose_frames(move)) | turned))
        for frame in frames[name]:
            kept[(name, frame)] = deformation(rig, bag, name, frame)
    for move, part, _want in sorted(jobs, key=lambda job: follow_depth(job[0], job[1])):
        _action, _slot, bag = action_bits(move)
        name = part.bone_name
        if bag is None or name not in frames:
            continue
        rest = rig.data.bones[name].matrix_local
        rows = {}
        for frame in frames[name]:
            if name in riding:
                rows[frame] = Matrix.Identity(4)
                continue
            carry = above(rig, bag, name, frame, parents=parents)
            rows[frame] = (rest.inverted_safe() @ carry.inverted_safe()
                           @ kept[(name, frame)] @ rest)
        write_basis_keys(bag, name, rig.pose.bones[name].rotation_mode, rows)
    if not activate(context, rig):
        return 0, 0, []
    bpy.ops.object.mode_set(mode="EDIT")
    edit = rig.data.edit_bones
    # Every bone that changes parent is let go first, then hung parents
    # first. Hung one at a time in list order, a chain turned round asked a
    # bone to hang from its own child - which Blender refuses without a word,
    # after the keys had been worked out for the new parent.
    for _move, part, _want in jobs:
        bone = edit.get(part.bone_name)
        if bone is not None:
            bone.use_connect = False
            bone.parent = None
    for move, part, want in sorted(jobs, key=lambda job: follow_depth(job[0], job[1])):
        bone = edit.get(part.bone_name)
        if bone is not None and want:
            bone.parent = edit.get(want)
    bpy.ops.object.mode_set(mode="OBJECT")
    context.view_layer.update()
    # Read back, so a hanging Blender would not make is said, not hidden.
    hung, let_go, refused = 0, 0, []
    for move, part, want in jobs:
        bone = rig.data.bones.get(part.bone_name)
        have = bone.parent.name if bone is not None and bone.parent is not None else ""
        if have != want:
            refused.append(part.name)
        elif want in part_bones:
            hung += 1
        else:
            let_go += 1
    return hung, let_go, refused


# ---------------------------------------------------------------------------
# pivots: the point a part turns about
#
# A part's bone stands on its pivot, and the path is played in the bone's own
# space: between two recorded poses the pivot travels in a straight line and
# everything else turns about it. With the pivot on a lid's hinge the hinge
# stays put and the lid swings; with it in the middle of the lid, the middle
# slides straight across and the lid cuts through the box. The recorded poses
# are the same either way - only the way between them changes.


def pivot_world(part):
    """A part's pivot in the world, standing where it stands at Before."""
    return as_matrix(part.before) @ Vector(part.pivot)


def shift_pivot(rig, move, part, shift):
    """Re-key a part's path for its bone standing `shift` further along.

    Every key keeps the pose it holds: a bone moved by d along its own axes,
    posed with turn R, has to be carried R*d - d less far for the part to end
    up where it was. Only the way between keys changes, which is the point.
    """
    name = part_bone(part)
    bone = rig.data.bones[name]
    pose_bone = rig.pose.bones[name]
    _action, _slot, bag = action_bits(move)
    if bag is None:
        return
    offset = bone.matrix_local.to_3x3().inverted_safe() @ shift
    # Every pose of the move as well as the bone's own keys: a follower was
    # recorded against where this one stood at every step, keyed or not.
    frames = sorted(set(key_frames(bag, name)) | set(pose_frames(move)))
    # Every new value worked out first: each one reads the path, which the
    # writing would change under the ones still to come.
    wanted = {}
    for frame in frames:
        basis = basis_at(bag, name, pose_bone.rotation_mode, frame)
        wanted[frame] = basis.translation - offset + basis.to_3x3() @ offset
    for index in range(3):
        curve = curve_for(bag, bone_path(name, "location"), index, make=True)
        for frame in frames:
            put_key(curve, frame, wanted[frame][index])
        curve.update()


def apply_pivots(context, rig, data):
    """Stand every bound object's bone on its pivot, keeping its path.

    Riders are not done here: their bones are turned from their leaders' in
    bind_riders, so a rider's pivot is its leader's, carried over.
    """
    into = rig.matrix_world.inverted_safe()
    jobs = []
    for move in data.moves:
        for part in bound_parts(move):
            bone = rig.data.bones.get(part.bone_name)
            if part.leader or bone is None:
                continue
            shift = into @ pivot_world(part) - bone.head_local
            if shift.length > 1e-6:
                jobs.append((move, part, shift))
    if not jobs:
        return 0
    # The path first, while the old rest is still there to read it against.
    # A curve the pivot follows moves with it, all of it: only its ends would
    # be pinned again, and a part that never turns would hump up between them.
    for move, part, shift in jobs:
        shift_pivot(rig, move, part, shift)
        if curve_alive(part.path_curve):
            move_curve(part.path_curve, rig.matrix_world.to_3x3() @ shift)
    if not activate(context, rig):
        return 0
    bpy.ops.object.mode_set(mode="EDIT")
    for _move, part, shift in jobs:
        bone = rig.data.edit_bones.get(part.bone_name)
        if bone is not None:
            bone.head = bone.head + shift
            bone.tail = bone.tail + shift
    bpy.ops.object.mode_set(mode="OBJECT")
    context.view_layer.update()
    return len(jobs)


def chosen_parts(context, move):
    """The parts a pivot or a curve button acts on: the move's own objects
    that are selected - or its only one, when it has just one."""
    own = [p for p in move.parts if p.kind == "OBJECT" and not p.leader]
    chosen = {o.name for o in context.selected_objects}
    picked = [p for p in own if p.name in chosen]
    if picked:
        return picked
    return own if len(own) == 1 else []


# ---------------------------------------------------------------------------
# curved paths: a pivot that goes from A to B by way of a curve
#
# Left alone, a pivot travels from Before to After in a straight line, or
# through its steps. A curve can bend that round whatever is in the way: made
# for the part from the path it has, edited by hand in edit mode, and laid
# onto the path at every Build - its two ends pinned back onto the pivot's
# Before and After first, so however it is edited it starts at A and ends at
# B. Turning still goes from pose to pose as before; only where the pivot
# travels is the curve's.

CURVE_SAMPLES = 40


def pivot_at(rig, bag, part, frame):
    """Where a part's pivot is on its path at this frame, in the world - its
    parents' carrying included, for a part that follows another."""
    name = part_bone(part)
    bone = rig.data.bones[name]
    return rig.matrix_world @ deformation(rig, bag, name, frame) @ bone.head_local


def make_path_curve(rig, move, part):
    """A curve along a part's path as it is now, for the hand to bend."""
    _action, _slot, bag = action_bits(move)
    frames = ([FIRST_FRAME] + [s.frame for s in move.steps if s.done]
              + [last_frame(move)])
    points = [pivot_at(rig, bag, part, frame) for frame in frames]
    if len(points) == 2:
        # A point in the middle to take hold of, or there is nothing to drag.
        points.insert(1, (points[0] + points[1]) * 0.5)
    data = bpy.data.curves.new(part.name + " path", "CURVE")
    data.dimensions = "3D"
    spline = data.splines.new("BEZIER")
    spline.bezier_points.add(len(points) - 1)
    for point in spline.bezier_points:
        point.handle_left_type = point.handle_right_type = "ALIGNED"
    # Handles a third of the way to each neighbour, along the line through
    # both: smooth through the points, and dead straight while they are.
    left, right = [], []
    for number, where in enumerate(points):
        before = points[max(number - 1, 0)]
        after = points[min(number + 1, len(points) - 1)]
        reach = (after - before) / (6.0 if 0 < number < len(points) - 1 else 3.0)
        left.append(where - reach)
        right.append(where + reach)
    set_points(spline, points, left, right)
    obj = bpy.data.objects.new(data.name, data)
    for collection in rig.users_collection:
        collection.objects.link(obj)
        break
    obj.show_in_front = True
    obj.hide_render = True
    part.path_curve = obj
    return obj


def curve_alive(obj):
    """Whether a part's curve is still something in the scene to follow."""
    return (obj is not None and obj.type == "CURVE" and len(obj.users_collection)
            and len(obj.data.splines))


def points_of(spline):
    """(points, left handles, right handles) of a Bezier spline."""
    out = []
    for name in ("co", "handle_left", "handle_right"):
        values = [0.0] * (3 * len(spline.bezier_points))
        spline.bezier_points.foreach_get(name, values)
        out.append([Vector(values[i:i + 3]) for i in range(0, len(values), 3)])
    return out


def set_points(spline, points, left, right):
    """Write a Bezier spline's points and handles all at once.

    Not point by point: Blender recomputes an aligned handle whenever its
    point is set on its own, and swings it off to one side.
    """
    for name, values in (("co", points), ("handle_left", left),
                         ("handle_right", right)):
        spline.bezier_points.foreach_set(
            name, [x for value in values for x in value[:3]])
    spline.id_data.update_tag()


def move_curve(obj, shift):
    """Move every point of a curve's first spline by a world-space shift."""
    spline = obj.data.splines[0]
    local = obj.matrix_world.inverted_safe().to_3x3() @ shift
    if spline.type == "BEZIER":
        points, left, right = points_of(spline)
        set_points(spline, [p + local for p in points], [p + local for p in left],
                   [p + local for p in right])
    else:
        for point in spline.points:
            point.co = (point.co[0] + local.x, point.co[1] + local.y,
                        point.co[2] + local.z, point.co[3])


def pin_ends(obj, start, end):
    """Put a curve's two ends back on A and B, handles and all."""
    spline = obj.data.splines[0]
    into = obj.matrix_world.inverted_safe()
    if spline.type == "BEZIER":
        points, left, right = points_of(spline)
        for number, where in ((0, start), (len(points) - 1, end)):
            shift = into @ where - points[number]
            points[number] = points[number] + shift
            left[number] = left[number] + shift
            right[number] = right[number] + shift
        set_points(spline, points, left, right)
    else:
        for point, where in ((spline.points[0], start), (spline.points[-1], end)):
            here_ = into @ where
            point.co = (here_.x, here_.y, here_.z, point.co[3])


def curve_line(obj):
    """A curve's first spline as a close-set line of world points, A to B."""
    spline = obj.data.splines[0]
    if spline.type == "BEZIER":
        points = spline.bezier_points
        line = [points[0].co.copy()]
        for a, b in zip(points[:-1], points[1:]):
            line.extend(interpolate_bezier(a.co, a.handle_right, b.handle_left,
                                           b.co, 24)[1:])
    else:
        line = [Vector(p.co[:3]) for p in spline.points]
    return [obj.matrix_world @ p for p in line]


def along(line, share):
    """The point this share of the way along a line, by distance travelled."""
    lengths = [0.0]
    for a, b in zip(line[:-1], line[1:]):
        lengths.append(lengths[-1] + (b - a).length)
    if lengths[-1] <= 1e-12:
        return line[0].copy()
    goal = share * lengths[-1]
    for number in range(1, len(line)):
        if lengths[number] >= goal:
            span = lengths[number] - lengths[number - 1]
            part = (goal - lengths[number - 1]) / span if span > 1e-12 else 0.0
            return line[number - 1].lerp(line[number], part)
    return line[-1].copy()


def straighten(bag, part, move):
    """Take a part's location keys off the way between Before and After."""
    first, last = FIRST_FRAME + 1e-3, last_frame(move) - 1e-3
    for index in range(3):
        curve = curve_for(bag, bone_path(part_bone(part), "location"), index)
        if curve is None:
            continue
        for point in reversed([p for p in curve.keyframe_points
                               if first < p.co[0] < last]):
            curve.keyframe_points.remove(point, fast=True)
        curve.update()


def lay_curve(rig, bag, move, part, line):
    """Key a part's pivot along a line, evenly by distance, A to B."""
    name = part_bone(part)
    rest = rig.data.bones[name].matrix_local
    into = rig.matrix_world.inverted_safe()
    unrest = rest.inverted_safe()
    straighten(bag, part, move)
    curves = [curve_for(bag, bone_path(name, "location"), i, make=True)
              for i in range(3)]
    first, last = FIRST_FRAME, last_frame(move)
    for number in range(1, CURVE_SAMPLES):
        share = number / float(CURVE_SAMPLES)
        # Where the pivot has to be, undone through whatever its parents
        # carry it by at that frame, into the bone's own space.
        frame = first + share * (last - first)
        carry = above(rig, bag, name, frame)
        location = unrest @ (carry.inverted_safe() @ (into @ along(line, share)))
        for index, curve in enumerate(curves):
            point = curve.keyframe_points.insert(first + share * (last - first),
                                                 location[index], options={"FAST"})
            point.interpolation = "LINEAR"
    for curve in curves:
        curve.update()


def bake_curves(rig, data):
    """Lay every part's curve onto its path, its ends pinned to A and B first.

    Before the riders copy their leaders, so a rider of a curved part follows
    the curve too, from its own place. A part whose curve has gone - deleted,
    or never there - and that was laid from one is put back on the straight
    way. Returns how many were laid.
    """
    laid = 0
    for move in data.moves:
        _action, _slot, bag = action_bits(move)
        if bag is None:
            continue
        # Parents first: a follower's curve is laid against where its
        # parent's path, curve and all, now takes it.
        for part in follow_order(move, list(move.parts)):
            if part.leader or not part.bone_name or part.bone_name not in rig.data.bones:
                continue
            obj = part.path_curve
            if not curve_alive(obj):
                if part.curved:
                    straighten(bag, part, move)
                    part.curved = False
                if obj is not None:
                    part.path_curve = None
                continue
            start = pivot_at(rig, bag, part, FIRST_FRAME)
            end = pivot_at(rig, bag, part, last_frame(move))
            pin_ends(obj, start, end)
            lay_curve(rig, bag, move, part, curve_line(obj))
            part.curved = True
            laid += 1
    return laid


# ---------------------------------------------------------------------------
# the path preview: a line through where each part goes

PATH_SAMPLES = 96


def trace(rig, bag, move, part):
    """The world points the middle of a part passes through, Before to After.

    Read off the path rather than played, so drawing it moves nothing on
    screen and needs no frame changes; every key is among the points, so a
    corner at a step is a corner on the line.
    """
    obj = bpy.data.objects.get(part.name)
    name = part_bone(part)
    bone = rig.data.bones.get(name)
    pose_bone = rig.pose.bones.get(name)
    if (part.kind != "OBJECT" or not part.has_before or obj is None
            or obj.type != "MESH" or bone is None or pose_bone is None):
        return []
    middle = as_matrix(part.before) @ (sum(corners_of(obj), Vector()) / 8.0)
    world = rig.matrix_world
    into = world.inverted_safe()
    # Sampled along the control, not the path: each bone in the chain stands
    # on the frame its own delay, lead, ease and speeds put it on, so a
    # follower that waits for its parent is drawn where it really goes.
    owners = {part_bone(p): p for p in move.parts}
    out = []
    for number in range(PATH_SAMPLES + 1):
        share = number / float(PATH_SAMPLES)

        def frame(bone_name, share=share):
            owner = owners.get(bone_name)
            return path_frame(move, owner, share) if owner is not None else FIRST_FRAME

        out.append(world @ deformation(rig, bag, name, frame) @ into @ middle)
    return out


def path_frame(move, part, share):
    """The frame of its path a part stands on with the move's own control at
    this share: its window, its ease and the stretch speeds, as its driver
    works them out."""
    start, end = part_window(move, part)
    start = round(max(0.0, min(0.98, start)), 4)
    end = round(max(start + 0.01, min(1.0, end)), 4)
    t = min(max((share - start) / (end - start), 0.0), 1.0)
    if move.ease == "SMOOTH":
        t = t * t * (3.0 - 2.0 * t)
    elif move.ease == "IN":
        t = t * t
    elif move.ease == "OUT":
        t = t * (2.0 - t)
    points = timing_points(move)
    if points:
        for (c0, p0), (c1, p1) in zip(points[:-1], points[1:]):
            if t <= c1 or (c1, p1) == points[-1]:
                t = p0 + (p1 - p0) * ((t - c0) / (c1 - c0) if c1 > c0 else 0.0)
                break
    return FIRST_FRAME + t * (last_frame(move) - FIRST_FRAME)


def drop_paths(move):
    obj = move.paths_object
    move.paths_object = None
    if obj is not None:
        data = obj.data
        bpy.data.objects.remove(obj, do_unlink=True)
        if data is not None and data.users == 0:
            bpy.data.curves.remove(data)


def draw_paths(rig, move):
    """Draw - or draw again - the line through where every part of a move goes."""
    drop_paths(move)
    _action, _slot, bag = action_bits(move)
    if bag is None:
        return 0
    lines = [trace(rig, bag, move, part) for part in move.parts]
    lines = [line for line in lines if len(line) > 1]
    if not lines:
        return 0
    data = bpy.data.curves.new("RigMoves paths: " + move.name, "CURVE")
    data.dimensions = "3D"
    for line in lines:
        spline = data.splines.new("POLY")
        spline.points.add(len(line) - 1)
        for point, where in zip(spline.points, line):
            point.co = (where.x, where.y, where.z, 1.0)
    obj = bpy.data.objects.new(data.name, data)
    for collection in rig.users_collection:
        collection.objects.link(obj)
        break
    # Something to look at, never to click or render.
    obj.show_in_front = True
    obj.hide_render = True
    obj.hide_select = True
    move.paths_object = obj
    return len(lines)


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
    # Four decimals: a ten-thousandth of the control, far finer than it can
    # be dragged, where a rider's window - a twelfth, a seventh - printed to
    # six figures took a combined, eased driver over the limit. The span is
    # taken between the rounded ends, so a window that ends at 1 still does.
    start = round(max(0.0, min(0.98, start)), 4)
    end = round(max(start + 0.01, min(1.0, end)), 4)
    if start <= 1e-6 and end >= 1.0 - 1e-6:
        # No slice to take, but the clamp still earns its place: the control
        # itself can be dragged past either end.
        return "min(max({:s},0),1)".format(inner)
    if start <= 1e-6:
        return "min(max({:s}/{:s},0),1)".format(inner, decimal(end))
    # start and the span are both positive by the clamps above, so neither
    # needs brackets of its own to keep a minus sign apart from a minus.
    return "min(max(({:s}-{:s})/{:s},0),1)".format(
        inner, decimal(start), decimal(end - start))


def decimal(value):
    """At most four decimals, and none that say nothing: 0.5, not 0.5000."""
    return "{:.4f}".format(value).rstrip("0").rstrip(".") or "0"


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


def base_window(move, part):
    """When a part travels, on the move's own time: (start, end).

    For a part of its own that is its delay to the end, 0 to 1 at most. A
    rider travels for exactly as long as its leader - the same move at the
    same speed - shifted by its lead, a whole leader's travel at 50 either
    way. So a rider can start before 0 or finish after 1.

    Every joint of a copied finger is shifted by its first joint's lead, and
    by the same amount: shifted each by its own leader's travel, the joints
    of a late finger would drift apart in time, and it would not curl the
    way the recorded one does.
    """
    if part.leader:
        leader = leader_of(move, part)
        if leader is not None:
            # Asked of every part for every part, so a rider on its own -
            # sixty petals round a flower - skips looking for a copy.
            root = copy_root(move, part) if part.rides_on else part
            first = leader_of(move, root) or leader
            start = min(max(leader.start, 0.0), 0.99)
            begin = min(max(first.start, 0.0), 0.99)
            shift = -root.lead / 50.0 * (1.0 - begin)
            return start + shift, 1.0 + shift
    return part.start, travels_to_end(part)


def part_window(move, part):
    """A part's share of the control, (start, end) inside 0 to 1.

    The control always plays the whole move: from the first part that sets
    off - a rider going ahead of its leader - to the last one to arrive. Left
    as it was when nothing rides ahead or behind, so a move without riders
    plays exactly as it always has.
    """
    windows = [base_window(move, p) for p in move.parts]
    low = min([0.0] + [w[0] for w in windows])
    high = max([1.0] + [w[1] for w in windows])
    start, end = base_window(move, part)
    span = high - low
    return (start - low) / span, (end - low) / span


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
        "{t}", window(own, *part_window(move, part)))


# ---------------------------------------------------------------------------
# how fast each stretch goes
#
# A move with steps in it has stretches - Before to the first step, one step
# to the next, the last into After - and each has a speed. A speed decides
# how much of the control's travel its stretch takes: the poses stay where
# they are on the path, only the control is shared out differently.


def speed_factor(speed):
    """Every 50 points is ten times, so 15 is about twice."""
    return 10.0 ** (speed / 50.0)


def speed_note(speed):
    """A stretch's speed in words, against even."""
    if not speed:
        return "even"
    return "{:.1f}× {:s}".format(speed_factor(abs(speed)),
                                 "faster" if speed > 0 else "slower")


def timing_points(move):
    """Where each pose falls on the control, against where it falls on the
    path, as (control, path) pairs - or None while every stretch is even.

    Each stretch keeps the share of the path it has, and takes a share of the
    control that is that much shorter for a fast one and longer for a slow
    one. So 0 everywhere is the path exactly as recorded, and every stretch
    at the same speed is too: the move always fills the whole control.
    """
    if not len(move.steps):
        return None
    speeds = [step.speed for step in move.steps] + [move.speed_after]
    if not any(speeds):
        return None
    span = float(last_frame(move) - FIRST_FRAME)
    marks = [0.0]
    marks.extend((step.frame - FIRST_FRAME) / span for step in move.steps)
    marks.append(1.0)
    shares = [max(marks[i + 1] - marks[i], 1e-6) / speed_factor(speed)
              for i, speed in enumerate(speeds)]
    total = sum(shares)
    points, reached = [], 0.0
    for i, mark in enumerate(marks):
        points.append((reached / total, mark))
        if i < len(shares):
            reached += shares[i]
    return points


def time_curve(curve, points):
    """Share the control out between the stretches, on one part's driver.

    Done with keys on the driver's own curve, which Blender reads as a map
    from what the expression says to the value it writes. Not in the
    expression: a delay and an ease already bring that close to the 256
    characters Blender will hold. And because it is the move's time that is
    bent rather than any one path, a part with no key at a step still slows
    and speeds up with the rest.
    """
    keys = curve.keyframe_points
    while len(keys):
        keys.remove(keys[0], fast=True)
    for control, along in points or ():
        key = keys.insert(control, along, options={"FAST"})
        key.interpolation = "LINEAR"
    curve.update()


def timing_curves(rig, move):
    """The driver curve of every part this move plays, as (part, curve).

    Found by the move's own action, not by constraint name: a name can have
    been made unique on one bone and not another, but the action is the
    move's alone.
    """
    action = bpy.data.actions.get(move.action_name) if move.action_name else None
    animation = rig.animation_data
    if action is None or animation is None:
        return []
    out = []
    for part in move.parts:
        name = part_bone(part)
        pose_bone = rig.pose.bones.get(name)
        if pose_bone is None:
            continue
        for constraint in pose_bone.constraints:
            if (constraint.type != "ACTION" or constraint.action != action
                    or not constraint.name.startswith(CONSTRAINT)):
                continue
            curve = animation.drivers.find(
                'pose.bones["{:s}"].constraints["{:s}"].eval_time'.format(
                    bpy.utils.escape_identifier(name),
                    bpy.utils.escape_identifier(constraint.name)))
            if curve is not None:
                out.append((part, curve))
    return out


def refresh_drivers(rig, data, move):
    """Rewrite what a built move's drivers say, without a Build.

    Every part of the move, whichever setting changed: a rider's lead can
    widen the whole move, and that changes every part's share of the control.
    """
    points = timing_points(move)
    cramped = []
    for part, curve in timing_curves(rig, move):
        driver = curve.driver
        wanted = eval_expression(data, move, part)
        # A move combined since its last Build reads a slider its driver has
        # no variable for yet; that waits for the Build.
        if (GROUP_VAR in wanted) == (driver.variables.get(GROUP_VAR) is not None):
            driver.expression = wanted
            if driver.expression != wanted:
                cramped.append(part_bone(part))
        time_curve(curve, points)
    if cramped:
        data.report = ("The driver for {:s} was too long for Blender to hold and "
                       "got cut short. Use fewer delays, or Even speed, on this "
                       "move.".format(", ".join(sorted(set(cramped))[:3])))
    rig.update_tag()


# ---------------------------------------------------------------------------
# spreading: one gesture instead of a number for every part
#
# A flower's eight petals each want a Lead of their own, a finger's joints a
# Delay each, a row of dominoes a start each. Typing them is the slowest part
# of a move that was recorded once, so Spread works them out from where the
# parts stand and writes them all together.

SPREAD_WHAT = [("LEAD", "Leads", "Fill in the Lead of every rider"),
               ("DELAY", "Delays", "Fill in the Delay of every part")]
SPREAD_ORDERS = [
    ("AROUND", "Around a ring",
     "By angle round the ring the parts stand on, measured from the leader "
     "(for Delays, from the active part)"),
    ("DISTANCE", "By distance",
     "By how far each part is from the leader (for Delays, from the active "
     "part): a ripple"),
    ("AXIS", "Along an axis",
     "By position along the world X, Y or Z: dominoes, a wave across a grid"),
    ("CHAIN", "Down a chain",
     "By how far down a Follows chain each part hangs: a finger, a tentacle"),
    ("RANDOM", "Random", "In no order, the same every time for the same seed")]
AXIS_ITEMS = [(name, name, "World " + name) for name in AXES]
SPREAD_BY = [
    ("STEP", "Step",
     "A start, and how much each place in the order adds to the one before: "
     "parts that stand in the same place share one"),
    ("RANGE", "Range",
     "A first and a last value, and the parts between spread evenly from one "
     "to the other, however many there are")]

# The same limits the Lead and Delay properties have, which a spread has to
# keep to however wide the First and Last it was given.
LEAD_LIMITS = (-50, 50)
DELAY_LIMITS = (0.0, 0.99)


def rider_spot(rig, move, leader, rider):
    """Where a rider turns, in the world, standing where it stands at Before:
    its leader's pivot carried over to it, the way its bone is stood on it -
    through the frames the two stand in, and mirrored if it mirrors."""
    own = frame_of(as_matrix(rider.before))
    back = leader_frame(rig, leader)[0].inverted_safe()
    local = rider_reflection(rig, move, leader, rider)
    mirror = local.to_4x4() if local is not None else Matrix.Identity(4)
    return own @ mirror @ back @ pivot_world(leader)


def part_spot(rig, move, part, middle=False):
    """Where a part stands, in the world, for putting parts in order: its
    pivot at Before - where it turns, not where it happens to be drawn now -
    or, with `middle`, the middle of it. A rider's pivot is its leader's,
    carried over: measured from its own origin it would not be on the same
    ring as the leader's."""
    if part.kind == "OBJECT" and part.has_before:
        before = as_matrix(part.before)
        if not middle:
            leader = leader_of(move, part) if part.leader else None
            if leader is not None and leader.kind == "OBJECT" and leader.has_before:
                return rider_spot(rig, move, leader, part)
            return pivot_world(part)
        obj = bpy.data.objects.get(part.name)
        if obj is not None and obj.type == "MESH":
            return before @ (sum(corners_of(obj), Vector()) / 8.0)
        return before.translation.copy()
    bone = rig.data.bones.get(part_bone(part))
    if bone is not None:
        return rig.matrix_world @ bone.head_local
    obj = bpy.data.objects.get(part.name)
    return obj.matrix_world.translation.copy() if obj is not None else Vector()


def spots_of(rig, move, parts):
    """Where each of these parts stands.

    Their pivots - unless every one of them is the same point, as with the
    blades of a fan all turning about the hub. Then the pivots say nothing
    about who stands where, and the middle of each part is used instead.

    "The same point" is measured against how far apart the parts stand, not in
    absolute units: the pivots of blades about a hub far from the world's
    origin come out a hair apart from float rounding, which grows with the
    distance, and that noise was being sorted into an order.
    """
    spots = [part_spot(rig, move, p) for p in parts]
    if len(spots) < 2:
        return spots
    spread = max((s - spots[0]).length for s in spots)
    far = max(max(abs(c) for c in s) for s in spots)
    # Only worth reading the parts' middles when the pivots are close enough
    # to be the same point.
    if spread < 0.01 * max(1.0, far):
        middles = [part_spot(rig, move, p, middle=True) for p in parts]
        reach = max((m - middles[0]).length for m in middles)
        if spread < max(1e-5, 1e-3 * reach):
            return middles
    return spots


def ring_normal(points):
    """The direction square to the plane that fits these points best: the
    way they vary least. Straight up when there are too few to say - under
    three - or they all lie on a line."""
    up = Vector((0.0, 0.0, 1.0))
    if len(points) < 3:
        return up
    try:
        import numpy
    except ImportError:
        return up
    array = numpy.array([tuple(p) for p in points], dtype=float)
    _left, sizes, rows = numpy.linalg.svd(array - array.mean(axis=0),
                                          full_matrices=False)
    if sizes[0] < 1e-9 or sizes[1] < 1e-4 * sizes[0]:
        return up
    normal = Vector(tuple(float(x) for x in rows[-1])).normalized()
    # The same line is its own reverse, and which way round the angle runs
    # depends on it: always the one that points up, or along Y or X for a
    # ring on its side, so the answer does not change from run to run.
    for axis in (2, 1, 0):
        if abs(normal[axis]) > 1e-6:
            return normal if normal[axis] > 0.0 else -normal
    return up


def circle_centre(points, axis):
    """The centre of the circle that fits these points best, in the plane
    square to `axis` - or just their average when there are too few to say
    (under three), they lie on a line, or the fit is not to be trusted.

    An average is the centre of a full ring and of nothing else: the parts of
    a half-open fan, a wing, or a few picked out of a ring all lie on an arc,
    and the average of an arc is off to one side of its circle.
    """
    average = sum(points, Vector()) / len(points)
    if len(points) < 3:
        return average
    try:
        import numpy
    except ImportError:
        return average
    along = axis.orthogonal().normalized()
    up = axis.cross(along)
    placed = [((p - average).dot(along), (p - average).dot(up)) for p in points]
    reach = max(max(abs(x), abs(y)) for x, y in placed)
    if reach < 1e-9:
        return average
    # In units of the points' own size, so what counts as ill-conditioned does
    # not depend on how big the model is.
    rows = numpy.array([[x / reach, y / reach, 1.0] for x, y in placed])
    wanted = numpy.array([(x * x + y * y) / (reach * reach) for x, y in placed])
    answer, _gone, rank, sizes = numpy.linalg.lstsq(rows, wanted, rcond=None)
    if rank < 3 or sizes[-1] < 1e-6 * sizes[0]:
        return average
    # x^2 + y^2 = a x + b y + c is a circle of centre (a/2, b/2).
    x, y = answer[0] * reach / 2.0, answer[1] * reach / 2.0
    if math.hypot(x, y) > 100.0 * reach:
        return average
    return average + along * x + up * y


def ring_angles(spots, reference, reference_stands_in, both_ways):
    """How far round a ring each spot is from the reference, in radians.

    The ring is where the spots (and the reference, unless it is one of
    them) lie: its plane the best fit through them, and its middle the circle
    fitted to the spots in that plane - the reference left out of that, as it
    may be the hub - or the average of them all, when there are fewer than
    three spots. The angle runs one way round, 0 to a full turn - or, `both_ways`,
    is folded to 0 to a half turn, so the two sides of the ring match.
    A reference that sits on the middle has no direction to measure from, so
    the first spot gives it, as it does for parts all in one place.
    """
    points = list(spots) + ([] if reference_stands_in else [reference])
    axis = ring_normal(points)
    middle = circle_centre(list(spots) if len(spots) >= 3 else points, axis)

    def in_plane(where):
        offset = where - middle
        return offset - axis * offset.dot(axis)

    start = in_plane(reference)
    if start.length < 1e-6:
        start = in_plane(spots[0])
    if start.length < 1e-6:
        return [0.0] * len(spots)
    across = axis.cross(start.normalized())
    out = []
    for where in spots:
        offset = in_plane(where)
        angle = math.atan2(offset.dot(across), offset.dot(start.normalized()))
        angle %= 2.0 * math.pi
        # A part exactly on the reference can land a hair below a full turn.
        if angle > 2.0 * math.pi - 1e-5:
            angle = 0.0
        if both_ways:
            angle = min(angle, 2.0 * math.pi - angle)
        out.append(angle)
    return out


def scaled_to_one(values):
    """Each value as a share of the biggest, or all 0 when none is above 0."""
    top = max(values)
    return [v / top if top > 1e-9 else 0.0 for v in values]


def spread_keys(rig, move, reference, parts, order, axis, both_ways):
    """The number that puts each of these parts in order, for an order that
    goes by position: the angle round the ring, the distance from the
    reference, the place along the axis, or how far down a chain it hangs.

    The reference is the part the others are measured from; None means the
    first of the parts.
    """
    names = [p.name for p in parts]
    if order == "CHAIN":
        return [float(follow_depth(move, p)) for p in parts]
    stands_in = reference is None or reference.name in names
    ahead = reference if reference is not None else parts[0]
    everyone = parts if stands_in else parts + [ahead]
    spots = spots_of(rig, move, everyone)
    where = spots[:len(parts)]
    start = spots[names.index(ahead.name)] if stands_in else spots[-1]
    if order == "DISTANCE":
        return [(w - start).length for w in where]
    if order == "AXIS":
        return [w[AXES.index(axis)] for w in where]
    return ring_angles(where, start, stands_in, both_ways)


def spread_shares(rig, move, groups, order, axis, both_ways, seed):
    """Where in the spread each part falls, 0 to 1, as {part name: share}.

    `groups` is a list of (reference part or None, parts): each group is put
    in order among itself, so two rings with a leader each both get the whole
    range. The reference is the part the others are measured from; None means
    the first of the group.
    """
    chance = random.Random(seed)
    shares = {}
    for reference, parts in groups:
        names = [p.name for p in parts]
        if order == "RANDOM":
            values = [chance.random() for _part in parts]
        else:
            keys = spread_keys(rig, move, reference, parts, order, axis, both_ways)
            if order == "AXIS":
                low, high = min(keys), max(keys)
                values = [(a - low) / (high - low) if high - low > 1e-9 else 0.0
                          for a in keys]
            else:
                values = scaled_to_one(keys)
        shares.update(zip(names, values))
    return shares


def tied_ranks(keys):
    """Each key's place in the order, counting from 0, with keys that are the
    same - to within a small tolerance - sharing one place.

    The tolerance is a ten-thousandth of how far the keys run, because the
    two sides of a ring, or a row of parts all at one height, come out a hair
    apart from float rounding, and that noise must not be taken for an order.
    """
    order = sorted(range(len(keys)), key=lambda n: keys[n])
    tolerance = max(1e-6, 1e-4 * (keys[order[-1]] - keys[order[0]]))
    out, rank = [0] * len(keys), 0
    for before, now in zip(order, order[1:]):
        if keys[now] - keys[before] > tolerance:
            rank += 1
        out[now] = rank
    return out


def spread_ranks(rig, move, groups, what, order, axis, both_ways, seed):
    """Which place in the order each part takes, as {part name: rank}.

    Parts the order cannot tell apart share a rank: the two sides of a ring
    folded in half, parts at the same height along an axis, joints at the same
    depth down a chain. Random deals the places out, none shared, the same
    way for the same seed.

    For Leads the leader is rank 0, with the Lead of 0 it always has, so its
    riders start at rank 1. For Delays the first part is rank 0.
    """
    chance = random.Random(seed)
    ranks = {}
    for reference, parts in groups:
        if order == "RANDOM":
            found = list(range(len(parts)))
            chance.shuffle(found)
        else:
            keys = spread_keys(rig, move, reference, parts, order, axis, both_ways)
            if order == "CHAIN":
                # The depth itself, not the place among those that are here:
                # a joint two down waits two steps even with the one between
                # not in the spread.
                found = [int(round(k - min(keys))) for k in keys]
            else:
                found = tied_ranks(keys)
        after = 1 if what == "LEAD" else 0
        ranks.update((p.name, rank + after) for p, rank in zip(parts, found))
    return ranks


def sized_step(what, top):
    """The step a spread takes when none was asked for: -10 for Leads and 0.1
    for Delays, made smaller if the last place - `top` steps on - would run
    past 40 of the 50 a Lead can be, or 0.9 of the 0.99 a Delay can be. A
    ring of twelve spikes one way round has eleven places; ten each would
    leave six of them held at the limit and the wave stopped dead there."""
    top = max(top, 1)
    if what == "LEAD":
        return -float(min(10, max(1, 40 // top)))
    return max(0.01, min(0.1, math.floor(0.9 / top * 100.0 + 1e-9) / 100.0))


def spread_put(what, parts, values):
    """Write these values - one for each part - into the Leads or Delays of
    the parts, rounded and held to the limits, and say how many were held.

    Every value goes in with the drivers left alone, and the caller refreshes
    them once at the end: a ring of twelve riders was twelve full rewrites.
    """
    limited = 0
    WRITING["many"] = True
    try:
        for part, value in zip(parts, values):
            if what == "LEAD":
                # Half a step goes outwards either way, so two sides of a ring
                # round alike.
                whole = int(math.copysign(math.floor(abs(value) + 0.5), value))
                put = max(LEAD_LIMITS[0], min(LEAD_LIMITS[1], whole))
                limited += put != whole
                part.lead = put
            else:
                put = max(DELAY_LIMITS[0], min(DELAY_LIMITS[1], round(value, 4)))
                limited += abs(put - round(value, 4)) > 1e-9
                part.start = put
    finally:
        WRITING["many"] = False
    return limited


def spread_values(what, parts, shares, first, last):
    """Write the spread - `first` to `last` by each part's share - into the
    Leads or Delays of these parts, and say how many were held to the limit."""
    return spread_put(what, parts, [first + (last - first) * shares[part.name]
                                    for part in parts])


def spread_groups(context, move, what, only_selected=False):
    """What a spread acts on, as [(reference part or None, parts)].

    Leads belong to riders, and each leader's riders are spread among
    themselves. A copied finger has one Lead, its first joint's, which every
    joint of it plays by - so it is that joint that is spread, and any joint
    of the copy that is selected selects it. Delays belong to the parts that
    have one - the Timing list - measured from the active part.

    All of them, unless `only_selected`: whatever the last tool left selected
    is not something to go by - Ring leaves its own copies selected, Curl its
    first joint - and a spread that quietly reached only those left the rest
    of a flower or a tentacle untouched.
    """
    chosen = held(context, move)
    if what == "LEAD":
        riders = [p for p in move.parts if p.leader and leader_of(move, p) is not None
                  and copy_root(move, p).name == p.name]
        picked = {copy_root(move, p).name for p in move.parts
                  if p.leader and p.name in chosen}
        use = [p for p in riders if p.name in picked] if only_selected else riders
        grouped = {}
        for part in use:
            grouped.setdefault(part.leader, []).append(part)
        return [(move.parts[name], parts) for name, parts in grouped.items()]
    own = [p for p in move.parts if not p.leader]
    use = [p for p in own if p.name in chosen] if only_selected else own
    active = context.view_layer.objects.active
    ahead = next((p for p in own if active is not None and p.name == active.name), None)
    return [(ahead, use)] if use else []


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
        if not ready(self, rig, data):
            return {"CANCELLED"}
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
        # Objects already parented to one another - a finger modelled joint
        # by joint - follow the same way here without being asked.
        for obj in chosen_objects:
            if obj.parent is not None and obj.parent in chosen_objects:
                move.parts[obj.name].follows = obj.parent.name
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
    # Rigs made before the rename are still called "RigMoves Rig".
    for prefix in ("CopyThat ", "RigMoves "):
        if name.startswith(prefix):
            return name[len(prefix):]
    return name


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
        if len(obj.children_recursive) or any(p.kind != "OBJECT"
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
        if not ready(self, rig, data):
            return {"CANCELLED"}
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
        # A joint modelled hanging from a part of this move, or from another
        # newcomer, follows it here too, as New Move does.
        for obj in fresh:
            if obj.parent is not None and move.parts.get(obj.parent.name) is not None:
                move.parts[obj.name].follows = obj.parent.name
        data.report = ("{:d} object(s) added to '{:s}', where they stand now. "
                       "Press the eye beside After, put them where they should "
                       "end up, then Record After. A follower left as it is "
                       "rides along with what it follows."
                       .format(len(fresh), move.name))
        self.report({"INFO"}, data.report)
        return {"FINISHED"}


def leaders(context, rig):
    """Parts in the selection that newcomers could ride along with, as
    (index, move, part) - the active object first, since that is the one
    somebody clicked last and so most likely means.

    One for each chain: every joint of a finger offers the same thing, a
    ride on the whole finger, so a finger selected whole is one button, not
    three. A follower may lead: its riders hang from what it hangs from.
    """
    if rig is None:
        return []
    chosen = {o.name for o in context.selected_objects}
    active = context.view_layer.objects.active
    rows = [(index, move, part)
            for index, move in enumerate(rig.rigmoves.moves)
            for part in move.parts
            if part.kind == "OBJECT" and not part.leader and part.name in chosen]
    rows.sort(key=lambda row: active is None or row[2].name != active.name)
    out, chains = [], set()
    for index, move, part in rows:
        key = (index, chain_of(move, part)[0].name)
        if key not in chains:
            chains.add(key)
            out.append((index, move, part))
    return out


class RIGMOVES_OT_ride_along(bpy.types.Operator):
    bl_idname = "rigmoves.ride_along"
    bl_label = "Ride Along"
    bl_description = ("Have the selected objects copy this part's move, each "
                      "from where it stands: whatever it does to its own "
                      "left, each of them does to theirs. Copies of a whole "
                      "chain - a finger - ride along joint for joint")
    bl_options = {"REGISTER", "UNDO"}
    index: bpy.props.IntProperty()
    leader: bpy.props.StringProperty()
    rig_name: bpy.props.StringProperty()
    # For a caller that made the copies itself and knows which is which:
    # [{joint: object}, ...], one entry for each whole copy, in place of
    # guessing from where the objects stand. Said, even empty, it is final;
    # left empty, which joint each object copies is worked out from where it
    # stands. Ring makes copies of a part of a chain - a finger's second
    # joint and its tip - that look just like a copy of the first two.
    pairing: bpy.props.StringProperty(options={"HIDDEN", "SKIP_SAVE"})

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
        if not ready(self, rig, data):
            return {"CANCELLED"}
        leader = move.parts.get(self.leader)
        if leader is None or leader.leader or leader.kind != "OBJECT":
            return {"CANCELLED"}
        fresh = newcomers(context, rig)
        if not fresh:
            data.report = "Select the objects to ride along, then the part they follow."
            self.report({"WARNING"}, data.report)
            return {"CANCELLED"}
        if move.built and not keeps_drags(self, data):
            return {"CANCELLED"}
        if getattr(context.scene, "rigmoves_rig", None) is not rig:
            context.scene.rigmoves_rig = rig
        # Whole copies of the chain the leader is part of first, joint for
        # joint, each joint riding on the copy of the joint before it. Any
        # object that copies no more than one joint rides along with the
        # part that was clicked, as a rider always has. All of it worked out
        # before anything is added: adding to the list of parts can move
        # them, and a part held from before would point at nothing.
        chain = chain_of(move, leader)
        if self.pairing:
            by_name = {obj.name: obj for obj in fresh}
            joints_ = {joint.name for joint in chain}
            copies = []
            for told in json.loads(self.pairing):
                found = {joint: by_name[name] for joint, name in told.items()
                         if joint in joints_ and name in by_name}
                if found:
                    copies.append(found)
            used = {obj.name for copy in copies for obj in copy.values()}
            alone = [obj for obj in fresh if obj.name not in used]
        elif len(chain) > 1:
            copies, alone = match_copies(chain, fresh)
        else:
            copies, alone = [], list(fresh)
        joining = []
        for copy in copies:
            for joint in chain:
                obj = copy.get(joint.name)
                if obj is None:
                    continue
                up = copy.get(joint.follows)
                joining.append((obj, joint.name, up.name if up is not None else
                                ride_on_existing(move, joint,
                                                 body(obj, obj.matrix_world))))
        for obj in alone:
            joining.append((obj, leader.name,
                            ride_on_existing(move, leader, body(obj, obj.matrix_world))))
        lead_name, root_name = leader.name, chain[0].name
        # Where each stands now is the place it copies the move from. That is
        # all there is to record: the path itself is the leader's.
        for obj, joint, rides in joining:
            part = move.parts.add()
            part.name = obj.name
            part.kind = "OBJECT"
            part.leader = joint
            part.rides_on = rides
            part.before = flat(obj.matrix_world)
            part.has_before = True
            # A joint modelled hanging from another is hung there again if it
            # stops riding along - unless that was this add-on's own hanging,
            # which a copy of a follower brings with it.
            if (obj.parent is not None and obj.parent.type != "ARMATURE"
                    and not obj.get(FOLLOW_MARK)):
                part.home_parent = obj.parent.name
        adopt_riders(move, {obj.name for obj, _joint, _rides in joining})

        def ride(count):
            if not move.built:
                return "will ride"
            return "rides" if count == 1 else "ride"

        told = []
        if copies:
            told.append("{:s} of '{:s}' {:s} along, joint for joint".format(
                "1 copy" if len(copies) == 1 else "{:d} copies".format(len(copies)),
                short(root_name, 18), ride(len(copies))))
        if alone:
            said = ("'{:s}'".format(short(alone[0].name, 18)) if len(alone) == 1
                    else "{:d} objects".format(len(alone)))
            told.append("{:s} {:s} along with '{:s}'".format(
                said, ride(len(alone)), short(lead_name, 18)))
        if move.built:
            bpy.ops.rigmoves.build()
            data.report = ("{:s}. Set each one's Lead under Riding along to send "
                           "it ahead or behind.".format(", and ".join(told)))
        else:
            data.report = "{:s}. Record its After, then Build.".format(", and ".join(told))
        self.report({"INFO"}, data.report)
        return {"FINISHED"}


class RIGMOVES_OT_set_mirror(bpy.types.Operator):
    bl_idname = "rigmoves.set_mirror"
    bl_label = "Mirror"
    bl_description = ("Mirror this rider's copy of its leader's move across one "
                      "of its own axes - press again for the next: none, X, Y, "
                      "Z. A mirrored copy (negative scale) mirrors by itself "
                      "with this at none")
    bl_options = {"REGISTER", "UNDO"}
    index: bpy.props.IntProperty()
    part: bpy.props.IntProperty()
    axis: bpy.props.EnumProperty(items=MIRRORS, default="NONE")

    def execute(self, context):
        rig = rig_of(context)
        if not here(context, rig):
            return {"CANCELLED"}
        data = rig.rigmoves
        if not 0 <= self.index < len(data.moves):
            return {"CANCELLED"}
        move = data.moves[self.index]
        if not 0 <= self.part < len(move.parts) or not move.parts[self.part].leader:
            return {"CANCELLED"}
        if not ready(self, rig, data) or not keeps_drags(self, data):
            return {"CANCELLED"}
        # A copied finger mirrors as one, by the setting on its first joint.
        rider = copy_root(move, move.parts[self.part])
        rider.mirror = self.axis
        bpy.ops.rigmoves.build()
        data.report = ("'{:s}' mirrors its leader across {:s}.".format(
            short(rider.name, 18), self.axis) if self.axis != "NONE" else
            "'{:s}' copies its leader unmirrored.".format(short(rider.name, 18)))
        self.report({"INFO"}, data.report)
        return {"FINISHED"}


def take_riders_out(rig, move, names):
    """Take these riders out of a move: their constraints and drivers, their
    bones' curves, their binding, and the parts themselves. The bones are
    swept by the next Build.

    Their constraints, and with them their drivers, go before the bones do: a
    driver left on a bone that is gone is one Blender warns about on every
    update. The parts are taken out by name, one at a time, as each removal
    moves the ones after it.
    """
    _action, _slot, bag = action_bits(move)
    for name in names:
        rider = move.parts.get(name)
        if rider is None:
            continue
        pose_bone = rig.pose.bones.get(part_bone(rider)) if rider.bone_name else None
        if pose_bone is not None:
            for constraint in list(pose_bone.constraints):
                if constraint.type == "ACTION" and constraint.name.startswith(CONSTRAINT):
                    rig.driver_remove(
                        'pose.bones["{:s}"].constraints["{:s}"].eval_time'
                        .format(bpy.utils.escape_identifier(pose_bone.name),
                                bpy.utils.escape_identifier(constraint.name)))
                    pose_bone.constraints.remove(constraint)
        if rider.bone_name:
            unbind_object(rig, rider)
            if bag is not None:
                mine = bone_path(rider.bone_name, "")
                for curve in [c for c in bag.fcurves if c.data_path.startswith(mine)]:
                    bag.fcurves.remove(curve)
    for name in names:
        if move.parts.find(name) >= 0:
            move.parts.remove(move.parts.find(name))


class RIGMOVES_OT_drop_rider(bpy.types.Operator):
    bl_idname = "rigmoves.drop_rider"
    bl_label = "Stop Riding Along"
    bl_description = ("Take this object out of the move - with the rest of its "
                      "copy, for a copied finger. It is unbound and stays where "
                      "it is")
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
        if not 0 <= self.part < len(move.parts) or not move.parts[self.part].leader:
            return {"CANCELLED"}
        catch_up(rig, data)
        if not keeps_drags(self, data):
            return {"CANCELLED"}
        # The joints riding on it go with it: left behind they would hang
        # from a bone about to be swept, and play only half a finger.
        names = [p.name for p in copy_of(move, move.parts[self.part])]
        take_riders_out(rig, move, names)
        # The build sweeps the bones, now that nothing claims them.
        bpy.ops.rigmoves.build()
        data.report = ("'{:s}' no longer rides along.".format(short(names[0], 24))
                       if len(names) == 1 else
                       "'{:s}' and the {:d} joint(s) riding on it no longer ride along."
                       .format(short(names[0], 18), len(names) - 1))
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
        if not ready(self, rig, data):
            return {"CANCELLED"}
        objects, bones, still_keyed = clear_autokey(
            rig, data, context.scene.tool_settings.use_keyframe_insert_auto)
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
        catch_up(rig, data)
        taken = [b.name for b in context.selected_pose_bones]
        # Objects going out of the move come off what they were hung from to
        # follow; bones never were.
        for part in move.parts:
            if part.name not in taken:
                unhang(part)
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
        if not ready(self, rig, data):
            return {"CANCELLED"}
        if not len(move.parts):
            data.report = "'{:s}': no parts yet.".format(move.name)
            self.report({"WARNING"}, data.report)
            return {"CANCELLED"}

        # What is on screen, read before anything is paused or put back: every
        # bone as Blender is showing it - sliders live or not, parents and all
        # - and every loose part where it stands. A loose follower hangs from
        # the object it follows, which may be about to go back to its Before.
        context.view_layer.update()
        shown = {pb.name: pb.matrix @ pb.bone.matrix_local.inverted_safe()
                 for pb in rig.pose.bones}
        seen, carried = seen_poses(rig, move, shown)

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
        #
        # A drag is read where it was seen: the object's own transform,
        # carried by its bone and the bones above it as they were showing.
        # A follower that was only carried by the part it follows, its bone
        # already hanging from that part's, is no drag of its own: it keeps
        # its own joint and rides on its leader's new pose, as one left where
        # it was carried should.
        drops = []
        for part in bound_parts(move):
            # A rider is never posed: its path is its leader's, copied at
            # every Build, which also puts a dragged one back.
            if part.leader or part.name not in seen:
                continue
            obj, world = hand_moved(part)
            if world is None:
                continue
            leader = move.parts.get(part.follows) if part.follows else None
            if part.name in carried and bone_hangs_from(rig, part, leader):
                continue
            drops.append((part, obj, seen[part.name]))
        touched = {part_bone(part) for part, _obj, _seen in drops}

        # Objects with no bone yet are read straight off the object, which is
        # the point: they are moved by hand in object mode, not posed.
        loose = loose_parts(move) if self.which != "STEP" else []
        for part in loose:
            place = seen.get(part.name)
            if place is None:
                continue
            if self.which == "BEFORE":
                part.before = flat(place)
                part.has_before = True
            else:
                part.after = flat(place)
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
            if part.leader or (part.name in loose_names and not part.bone_name):
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

        # The dragged parts posed last, parents first by the bones that carry
        # them now - not by Follows, which waits on a Build - and each against
        # the pose its parent is about to be keyed at: its new one if it was
        # dragged too, the one it is showing if it is keyed as it stands, its
        # path otherwise. Solved against anything else, a follower would be
        # keyed somewhere it was not seen.
        #
        # Every object goes back first, parents first by what holds the
        # objects - Follows, which hangs them at once - as putting a leader
        # back carries its followers. A loose part carried off by that goes
        # back where it was seen.
        _action, _slot, path = action_bits(move)
        fresh = {name: rig.pose.bones[name].matrix_basis.copy()
                 for name in bones - touched if name in rig.pose.bones}
        stand_parts(context, move, seen)
        dragged = 0
        for part, _obj, place in sorted(drops,
                                        key=lambda d: bone_depth(rig, part_bone(d[0]))):
            if self.which == "AFTER":
                part.after = flat(place)
                part.has_after = True
            carry = above(rig, path, part_bone(part), frame, fresh)
            fresh[part_bone(part)] = pose_bone_at(rig, part, place, carry)
            dragged += 1
        if dragged:
            context.view_layer.update()
        if bones:
            count += key_pose(rig, move, frame, only=bones)
            # Said of objects as well as bones, so the After row can tell an
            # After that was recorded from the key every Build writes there.
            if self.which == "AFTER":
                for part in move.parts:
                    if part.kind == "OBJECT" and part_bone(part) in bones:
                        part.has_after = True
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


def ride_shown(rig, data, move):
    """Pose each bound follower that will ride along once built - no After
    of its own, never moved, its bone not hung yet - as it will ride, so a
    part added to a built move is seen carried before that Build."""
    _action, _slot, bag = action_bits(move)
    if bag is None:
        return
    part_bones = our_part_bones(data)
    posed = {pb.name: pb.matrix_basis.copy() for pb in rig.pose.bones}
    for part in follow_order(move, bound_parts(move)):
        bone = rig.data.bones.get(part.bone_name)
        if part.leader or part.has_after or bone is None:
            continue
        want = wanted_parent(rig, move, part, part_bones)
        have = bone.parent.name if bone.parent is not None else ""
        if want == have or want not in part_bones or not stands_still(rig, bag, bone.name):
            continue
        rest = bone.matrix_local
        carry = (above(rig, None, bone.name, 0.0, posed).inverted_safe()
                 @ deformation(rig, None, want, 0.0, posed))
        posed[bone.name] = rest.inverted_safe() @ carry @ rest
        rig.pose.bones[bone.name].matrix_basis = posed[bone.name]


def shown_places(rig, move, which):
    """Where each loose part of a move stands to show one of its poses.

    Its own Before or After where it has one. A follower with no After of
    its own rides along with what it follows, as it will once built: carried
    by however far that part is shown from its Before. Read off the bones as
    they are posed, so the bones have to be posed first.
    """
    world = rig.matrix_world
    into = world.inverted_safe()
    places, change = {}, {}
    for part in follow_order(move, chain_parts(move)):
        if is_bound(part):
            pose_bone = rig.pose.bones.get(part.bone_name)
            change[part.name] = (
                world @ pose_bone.matrix @ pose_bone.bone.matrix_local.inverted_safe()
                @ into if pose_bone is not None else Matrix.Identity(4))
            continue
        before = as_matrix(part.before)
        if which == "BEFORE" and part.has_before:
            place = before
        elif which == "AFTER" and part.has_after:
            place = as_matrix(part.after)
        elif part.has_before and not part.has_after and part.follows in change:
            place = change[part.follows] @ before
        else:
            continue
        places[part.name] = place
        if part.has_before:
            change[part.name] = place @ before.inverted_safe()
    return places


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
        if not ready(self, rig, data):
            return {"CANCELLED"}
        set_paused(rig, data, True)
        # Anything dragged since the build is standing off its rest, so the
        # pose would be shown measured from the wrong place.
        reseat_bound(data, move)
        context.view_layer.update()
        if self.which == "STEP":
            if not 0 <= self.step < len(move.steps):
                return {"CANCELLED"}
            frame = move.steps[self.step].frame
        else:
            frame = FIRST_FRAME if self.which == "BEFORE" else last_frame(move)
        pose_at(rig, move, frame)
        ride_shown(rig, data, move)
        context.view_layer.update()
        stand_parts(context, move, shown_places(rig, move, self.which))
        if self.which == "STEP":
            data.report = ("Showing '{:s}' at step {:d}. Build puts the "
                           "sliders back.".format(move.name, self.step + 1))
        else:
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
        refresh_drivers(rig, data, move)
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
        # One stretch fewer, so the speeds are shared out again.
        refresh_drivers(rig, data, move)
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
        if not ready(self, rig, data):
            return {"CANCELLED"}

        # Loose objects first: each gets a bone, gets bound to it, and has its
        # two recorded placements written into the move's path. After this a
        # move that started from objects is no different from one recorded on
        # bones, and everything below treats them alike.
        drop_stale_bones(context, rig, data)
        # First, because everything under it is undone by a keyframe: with
        # Auto Keying on, every drag this tool asks for leaves one behind, and
        # they hold the parts and the handles where the rig cannot move them.
        keyed_objects, keyed_bones, still_keyed = clear_autokey(
            rig, data, context.scene.tool_settings.use_keyframe_insert_auto)
        if keyed_objects or keyed_bones:
            context.view_layer.update()
        # Bound objects belong on their Before: that is the rest every slider
        # is measured from, and a rig where one has been nudged off it plays
        # the move from the wrong end. Putting them back here means a rig that
        # has already gone wrong comes right on the next Build.
        reseated = reseat_bound(data)
        if reseated:
            context.view_layer.update()
        bound, new_bones = bind_loose(context, rig, data)
        # Followers hung from the parts they follow, their poses kept.
        hung, let_go, refused = apply_parents(context, rig, data, new_bones)
        hang_objects(context, data)
        # Every bone onto its pivot, then every curve onto its path - its ends
        # pinned to wherever the pivot now starts and stops.
        pivoted = apply_pivots(context, rig, data)
        laid = bake_curves(rig, data)
        # Riders after, because each is turned from its leader's bone, which
        # may only just have been made or moved; then every rider takes its
        # leader's path - curve and all - as it stands now.
        riding = bind_riders(context, rig, data)
        lost = follow_leaders(rig, data)
        # Each part moved by its own bone alone. A copy of a part made after
        # it was bound, or a linked copy sharing its mesh, was moved by the
        # other part's bone as well, half and half. Once every bone is made:
        # a group left from a deleted rig only starts to pull when a part of
        # its name joins, and its bone is made in this very Build.
        healed = heal_bindings(rig, data)

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
            timing = timing_points(move)
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
                # Always written, even with every stretch even: a curve that
                # was here before can still carry the last build's keys.
                time_curve(curve, timing)
                made += 1
            move.built = True

        set_paused(rig, data, False)
        # Sliders live again, so whatever pose the bones were left in - by the
        # eye, by a Record - is hidden under them. Cleared, or the next Record
        # would count a pose nobody can see, or key one into a part nobody
        # touched. Only bones this add-on made: a hand-built rig keeps its own.
        for bone in rig.data.bones:
            if bone.get(PART_MARK) and bone.name in rig.pose.bones:
                rig.pose.bones[bone.name].matrix_basis = Matrix()
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
        # Last, so the lines go through where everything now really goes.
        for move in data.moves:
            if move.show_paths:
                draw_paths(rig, move)

        if not made:
            data.report = "Nothing recorded yet. Record Before and After, then Build."
            self.report({"WARNING"}, data.report)
            return {"FINISHED"}
        data.report = "{:d} part(s) on {:d} slider(s).".format(made, len(data.moves))
        if bound:
            data.report += " {:d} object(s) were given a bone and bound.".format(bound)
        if riding:
            data.report += " {:d} object(s) now ride along.".format(riding)
        if lost:
            data.report += (" {:s} rides with a part that is no longer in its "
                            "move, and was left as it was."
                            .format(", ".join(lost[:3])))
        if reseated:
            data.report += (" {:d} put back on its Before.".format(reseated)
                            if reseated == 1 else
                            " {:d} put back on their Before.".format(reseated))
        if keyed_objects or keyed_bones:
            data.report += (" {:d} stray keyframe track(s) on the parts and "
                            "{:d} on the rig were lifted, or the rig could not "
                            "move them.".format(keyed_objects, keyed_bones))
        if healed:
            data.report += (" {:d} part(s) copied from another were being moved "
                             "by its bone as well as their own; now only by their "
                             "own.".format(healed))
        if hung:
            data.report += " {:d} part(s) hung from the part they follow.".format(hung)
        if let_go:
            data.report += " {:d} part(s) let go to move on their own.".format(let_go)
        if refused:
            data.report += (" Blender would not hang {:s} where it follows."
                            .format(", ".join(refused[:3])))
            warn_parents = True
        else:
            warn_parents = False
        if pivoted:
            data.report += " {:d} turned about a new pivot.".format(pivoted)
        if laid:
            data.report += " {:d} path(s) laid along a curve.".format(laid)
        warn = warn_parents
        if still_keyed:
            data.report += (" {:s} is animated by hand and was left as it is."
                            .format(", ".join(still_keyed[:3])))
            warn = True
        if empty:
            data.report += " Nothing recorded for: " + ", ".join(empty[:3])
        # Build keys an After for every object it binds, so the path is all
        # there and the control moves nothing. Said, or it looks finished.
        no_after = [m.name for m in data.moves
                    if m.name not in empty and not recorded(m, "AFTER")]
        if no_after:
            data.report += (" {:s}: After not recorded yet - move the parts, then "
                            "Record After.".format(", ".join(
                                "'{:s}'".format(name) for name in no_after[:3])))
            warn = True
        if cramped:
            data.report += (" The driver for {:s} was too long for Blender to "
                            "hold and got cut short. Use fewer delays, or Even "
                            "speed, on this move."
                            .format(", ".join(sorted(set(cramped))[:3])))
            warn = True
        self.report({"WARNING"} if warn else {"INFO"}, data.report)
        return {"FINISHED"}


def unrecorded(data):
    """Bound parts dragged off their Before and not recorded yet."""
    return [part.name for move in data.moves for part in bound_parts(move)
            if not part.leader and hand_moved(part)[1] is not None]


def keeps_drags(operator, data):
    """Refuse a button that would Build while a dragged pose is unrecorded.

    Build puts every bound object back on its Before, which is right for a
    Build somebody asked for and wrong for one a button runs on the side: the
    drag - a new After, a step - was gone, with nothing said. Returns True
    when it is safe to go on.
    """
    dragged = unrecorded(data)
    if not dragged:
        return True
    data.report = ("'{:s}' has been moved and not recorded. Record it first - "
                   "this would Build, and Build puts it back.".format(
                       short(dragged[0], 18)))
    operator.report({"WARNING"}, data.report)
    return False


def move_at(context, index, operator=None):
    """(rig, data, move) for a move index on the rig in front of the user.

    Given the operator that asks, it also catches the rig up first, and the
    move is None, with the reason said, when the operator must not go on.
    """
    rig = rig_of(context)
    if not here(context, rig):
        return None, None, None
    data = rig.rigmoves
    if not 0 <= index < len(data.moves):
        return rig, data, None
    if operator is not None and not ready(operator, rig, data):
        return rig, data, None
    return rig, data, data.moves[index]


class RIGMOVES_OT_set_pivot(bpy.types.Operator):
    bl_idname = "rigmoves.set_pivot"
    bl_label = "Set Pivot"
    bl_description = ("Turn the selected parts of this move about this point. "
                      "The poses stay as recorded; the way between them swings "
                      "about the pivot")
    bl_options = {"REGISTER", "UNDO"}
    index: bpy.props.IntProperty()
    kind: bpy.props.EnumProperty(items=PIVOTS, default="ORIGIN")

    def execute(self, context):
        rig, data, move = move_at(context, self.index, self)
        if move is None:
            return {"CANCELLED"}
        parts = [p for p in chosen_parts(context, move) if p.has_before]
        if not parts:
            data.report = "Select the parts to set a pivot for."
            self.report({"WARNING"}, data.report)
            return {"CANCELLED"}
        if move.built and not keeps_drags(self, data):
            return {"CANCELLED"}
        cursor = context.scene.cursor.location.copy()
        for part in parts:
            obj = bpy.data.objects.get(part.name)
            if obj is None:
                continue
            if self.kind == "CURSOR":
                part.pivot = as_matrix(part.before).inverted_safe() @ cursor
            elif self.kind == "BASE":
                corners = corners_of(obj)
                part.pivot = ((min(c.x for c in corners) + max(c.x for c in corners)) * 0.5,
                              (min(c.y for c in corners) + max(c.y for c in corners)) * 0.5,
                              min(c.z for c in corners))
            else:
                part.pivot = (0.0, 0.0, 0.0)
            part.pivot_kind = self.kind
        said = ("'{:s}'".format(short(parts[0].name, 18)) if len(parts) == 1
                else "{:d} parts".format(len(parts)))
        label = dict((k, n) for k, n, _d in PIVOTS)[self.kind]
        if move.built:
            bpy.ops.rigmoves.build()
            data.report = "{:s} now turn about: {:s}.".format(said, label)
        else:
            data.report = "{:s} will turn about: {:s}, from the first Build.".format(
                said, label)
        self.report({"INFO"}, data.report)
        return {"FINISHED"}


class RIGMOVES_OT_curve_path(bpy.types.Operator):
    bl_idname = "rigmoves.curve_path"
    bl_label = "Curve the Path"
    bl_description = ("Make a curve along the path of each selected part. Bend "
                      "it in edit mode, then Build: the part follows it, and "
                      "its two ends always stay on Before and After")
    bl_options = {"REGISTER", "UNDO"}
    index: bpy.props.IntProperty()

    def execute(self, context):
        rig, data, move = move_at(context, self.index, self)
        if move is None:
            return {"CANCELLED"}
        chosen = chosen_parts(context, move)
        # A follower's pivot goes where the part it follows carries it; a curve
        # fixed in the world would pull it off its parent's joint.
        if chosen and all(p.follows for p in chosen):
            data.report = ("'{:s}' follows '{:s}' and goes where it is carried: "
                           "curve the path of the part it follows instead.".format(
                               short(chosen[0].name, 16), short(chosen[0].follows, 16)))
            self.report({"WARNING"}, data.report)
            return {"CANCELLED"}
        chosen = [p for p in chosen if not p.follows]
        parts = [p for p in chosen if not curve_alive(p.path_curve)]
        if not parts:
            data.report = ("'{:s}' has a curve already: press Edit beside it.".format(
                short(chosen[0].name, 18)) if chosen else
                "Select the parts to give a curved path.")
            self.report({"WARNING"}, data.report)
            return {"CANCELLED"}
        if not keeps_drags(self, data):
            return {"CANCELLED"}
        # The curve is drawn along the path the part has, so it has to have
        # one: a part still waiting for its first Build gets it now.
        if any(not p.bone_name for p in parts):
            if not all(p.has_after for p in parts):
                data.report = "Record After first: a curve runs from Before to After."
                self.report({"WARNING"}, data.report)
                return {"CANCELLED"}
            bpy.ops.rigmoves.build()
        names = [p.name for p in parts]
        made = 0
        for name in names:
            part = move.parts.get(name)
            if part is not None and part.bone_name in rig.data.bones:
                make_path_curve(rig, move, part)
                made += 1
        # Remembered, so the panel stays on this rig while a curve is edited.
        context.scene.rigmoves_rig = rig
        bpy.ops.rigmoves.build()
        data.report = ("{:d} curve(s) made along the path. Bend one in edit mode "
                       "(Tab), then Build; its ends stay on Before and After."
                       .format(made))
        self.report({"INFO"}, data.report)
        return {"FINISHED"}


class RIGMOVES_OT_edit_curve(bpy.types.Operator):
    bl_idname = "rigmoves.edit_curve"
    bl_label = "Edit the Curve"
    bl_description = "Select this part's curve and go into edit mode on it"
    bl_options = {"REGISTER", "UNDO"}
    index: bpy.props.IntProperty()
    part: bpy.props.IntProperty()

    def execute(self, context):
        rig, _data, move = move_at(context, self.index)
        if move is None or not 0 <= self.part < len(move.parts):
            return {"CANCELLED"}
        obj = move.parts[self.part].path_curve
        if not curve_alive(obj) or obj.name not in context.view_layer.objects:
            return {"CANCELLED"}
        if context.object is not None and context.object.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        for other in context.selected_objects:
            other.select_set(False)
        obj.hide_set(False)
        obj.select_set(True)
        context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode="EDIT")
        # Remembered too, for a rig the panel only knew from its selection.
        context.scene.rigmoves_rig = rig
        return {"FINISHED"}


class RIGMOVES_OT_drop_curve(bpy.types.Operator):
    bl_idname = "rigmoves.drop_curve"
    bl_label = "Straighten"
    bl_description = ("Delete this part's curve. Its path goes straight from "
                      "Before to After again")
    bl_options = {"REGISTER", "UNDO"}
    index: bpy.props.IntProperty()
    part: bpy.props.IntProperty()

    def execute(self, context):
        _rig, data, move = move_at(context, self.index, self)
        if move is None or not 0 <= self.part < len(move.parts):
            return {"CANCELLED"}
        if not keeps_drags(self, data):
            return {"CANCELLED"}
        part = move.parts[self.part]
        obj = part.path_curve
        part.path_curve = None
        if obj is not None:
            if obj.mode == "EDIT":
                bpy.ops.object.mode_set(mode="OBJECT")
            curve = obj.data
            bpy.data.objects.remove(obj, do_unlink=True)
            if curve is not None and curve.users == 0:
                bpy.data.curves.remove(curve)
        # The Build sees the curve gone and straightens the path.
        bpy.ops.rigmoves.build()
        data.report = "'{:s}' goes straight from Before to After again.".format(
            short(part.name, 20))
        return {"FINISHED"}


class RIGMOVES_OT_show_paths(bpy.types.Operator):
    bl_idname = "rigmoves.show_paths"
    bl_label = "Show Paths"
    bl_description = ("Draw a line in the viewport through where each part of "
                      "this move goes, from Before to After")
    bl_options = {"REGISTER", "UNDO"}
    index: bpy.props.IntProperty()
    show: bpy.props.BoolProperty(default=True)

    def execute(self, context):
        rig, data, move = move_at(context, self.index, self)
        if move is None:
            return {"CANCELLED"}
        move.show_paths = self.show
        if not self.show:
            drop_paths(move)
            return {"FINISHED"}
        if not draw_paths(rig, move):
            # Left off, or the button stays pressed with nothing drawn.
            move.show_paths = False
            data.report = ("Nothing to draw yet: record Before and After, then Build."
                           if any(p.kind == "OBJECT" for p in move.parts) else
                           "Paths are drawn for objects, and this move has none.")
            self.report({"WARNING"}, data.report)
        return {"FINISHED"}


def spread_words(what, order, groups, axis, both_ways, seed):
    """How a spread was ordered, in plain words, for the report."""
    several = len(groups) > 1
    ahead = groups[0][0] or groups[0][1][0]
    who = "each leader" if several else "'{:s}'".format(short(ahead.name, 18))
    if order == "AROUND":
        return "round the ring from {:s}{:s}".format(
            who, ", both ways" if both_ways else "")
    if order == "DISTANCE":
        return "by distance from {:s}".format(who)
    if order == "AXIS":
        return "along {:s}".format(axis)
    if order == "CHAIN":
        return "down the chain"
    return "at random (seed {:d})".format(seed)


class RIGMOVES_OT_spread(bpy.types.Operator):
    bl_idname = "rigmoves.spread"
    bl_label = "Spread"
    bl_description = ("Fill in every rider's Lead - or every part's Delay - in "
                      "one go, in order round a ring, by distance, along an "
                      "axis, down a chain or at random")
    bl_options = {"REGISTER", "UNDO"}
    index: bpy.props.IntProperty(options={"HIDDEN"})
    what: bpy.props.EnumProperty(items=SPREAD_WHAT, default="LEAD",
                                 options={"HIDDEN"})
    # Not remembered from one use to the next: what is sensible for a Lead is
    # not for a Delay, and invoke picks the right ones.
    order: bpy.props.EnumProperty(name="Order", items=SPREAD_ORDERS,
                                  default="AROUND", options={"SKIP_SAVE"})
    by: bpy.props.EnumProperty(
        name="By", items=SPREAD_BY, default="STEP",
        description="How the values are given: a start and a step for each "
                    "place in the order, or a first and a last with the rest "
                    "spread between them")
    start: bpy.props.FloatProperty(
        name="Start", default=0.0, min=-1000.0, max=1000.0, soft_min=-50.0,
        soft_max=50.0, precision=2, options={"SKIP_SAVE"},
        description="The value of the first place in the order. A leader is "
                    "that place for its riders, and always plays at 0, so a "
                    "rider's value is this plus its step for each place after "
                    "the leader")
    step: bpy.props.FloatProperty(
        name="Step", default=0.0, min=-1000.0, max=1000.0, soft_min=-50.0,
        soft_max=50.0, precision=2, options={"SKIP_SAVE"},
        description="What each place in the order adds to the one before. For "
                    "Leads, below 0 each waits more than the one before it and "
                    "above 0 each goes earlier; for Delays, above 0 each waits "
                    "that much longer")
    first: bpy.props.FloatProperty(
        name="First", default=0.0, min=-1000.0, max=1000.0, soft_min=-50.0,
        soft_max=50.0, precision=2, options={"SKIP_SAVE"},
        description="The value for the part that comes first in the order")
    last: bpy.props.FloatProperty(
        name="Last", default=0.0, min=-1000.0, max=1000.0, soft_min=-50.0,
        soft_max=50.0, precision=2, options={"SKIP_SAVE"},
        description="The value for the part that comes last in the order")
    both_ways: bpy.props.BoolProperty(
        name="Both ways", default=False,
        description="Fold the ring in half, so the two sides of it match: "
                    "the parts either side of the start go together")
    only_selected: bpy.props.BoolProperty(
        name="Only the selected", default=False,
        description="Spread only the parts that are selected now. Off, it is "
                    "every rider (or every part) of the move")
    axis: bpy.props.EnumProperty(name="Axis", items=AXIS_ITEMS, default="X")
    seed: bpy.props.IntProperty(name="Seed", default=1, min=0, max=100000)

    def sized(self, rig, move, groups):
        """The step to use when none was given: see sized_step."""
        ranks = spread_ranks(rig, move, groups, self.what, self.order, self.axis,
                             self.both_ways, self.seed)
        return sized_step(self.what, max(ranks.values()))

    def plan(self, context):
        """(rig, data, move, groups) - or None, with the reason said."""
        rig, data, move = move_at(context, self.index, self)
        if move is None:
            return None
        groups = spread_groups(context, move, self.what, self.only_selected)
        if not groups:
            if self.only_selected:
                data.report = ("None of the {:s} of '{:s}' is selected. Select some, "
                               "or untick Only the selected.".format(
                                   "riders" if self.what == "LEAD" else "parts", move.name))
            else:
                data.report = ("'{:s}' has no riders to spread Leads over. Select the "
                               "objects to ride along, then the part they copy, and "
                               "press Ride Along first.".format(move.name)
                               if self.what == "LEAD" else
                               "'{:s}' has no parts to give a Delay.".format(move.name))
            self.report({"WARNING"}, data.report)
            return None
        return rig, data, move, groups

    def invoke(self, context, event):
        found = self.plan(context)
        if found is None:
            return {"CANCELLED"}
        rig, _data, move, groups = found
        props = self.properties
        if self.what == "LEAD":
            wanted = ("AROUND", 0.0, -40.0)
        else:
            wanted = ("CHAIN" if any(p.follows for p in move.parts) else "AXIS",
                      0.0, 0.5)
        if not props.is_property_set("order"):
            self.order = wanted[0]
        if not props.is_property_set("first"):
            self.first = wanted[1]
        if not props.is_property_set("last"):
            self.last = wanted[2]
        if not props.is_property_set("start"):
            self.start = 0.0
        # The two sides of a ring open together unless said otherwise: a wave
        # that runs once round has twice the places, and the last runs out.
        if self.what == "LEAD" and not props.is_property_set("both_ways"):
            self.both_ways = self.order == "AROUND"
        if not props.is_property_set("step"):
            self.step = self.sized(rig, move, groups)
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        layout.prop(self, "order")
        layout.prop(self, "only_selected")
        if self.order == "AROUND":
            layout.prop(self, "both_ways")
        elif self.order == "AXIS":
            layout.prop(self, "axis", expand=True)
        elif self.order == "RANDOM":
            layout.prop(self, "seed")
        layout.prop(self, "by", expand=True)
        noun = "Lead" if self.what == "LEAD" else "Delay"
        column = layout.column(align=True)
        if self.by == "STEP":
            column.prop(self, "start", text="Start " + noun)
            column.prop(self, "step", text=noun + " step")
        else:
            column.prop(self, "first", text="First " + noun)
            column.prop(self, "last", text="Last " + noun)

    def execute(self, context):
        found = self.plan(context)
        if found is None:
            return {"CANCELLED"}
        rig, data, move, groups = found
        if self.what == "LEAD" and self.order == "CHAIN":
            data.report = ("Riders have no Follows chain of their own, so there is "
                           "no chain to spread down. Pick another order.")
            self.report({"WARNING"}, data.report)
            return {"CANCELLED"}
        parts = [part for _ahead, group in groups for part in group]
        if self.by == "STEP":
            ranks = spread_ranks(rig, move, groups, self.what, self.order,
                                 self.axis, self.both_ways, self.seed)
            if self.properties.is_property_set("step"):
                step, sized = self.step, ""
            else:
                step = sized_step(self.what, max(ranks.values()))
                base = 10.0 if self.what == "LEAD" else 0.1
                sized = " (sized to fit)" if abs(step) < base - 1e-9 else ""
            limited = spread_put(self.what, parts,
                                 [self.start + step * ranks[p.name] for p in parts])
            given = "in steps of {:g} from {:g}{:s}".format(step, self.start, sized)
        else:
            shares = spread_shares(rig, move, groups, self.order, self.axis,
                                   self.both_ways, self.seed)
            limited = spread_values(self.what, parts, shares, self.first, self.last)
            given = "from {:g} to {:g}".format(self.first, self.last)
        # Once, for all of them: a built move plays the new values at once.
        data.report = ""
        refresh_drivers(rig, data, move)
        cramped = data.report
        data.report = "Spread the {:s} of {:s} {:s}, {:s}.".format(
            "Leads" if self.what == "LEAD" else "Delays",
            counted(len(parts), "rider" if self.what == "LEAD" else "part"),
            given,
            spread_words(self.what, self.order, groups, self.axis,
                         self.both_ways, self.seed))
        if limited:
            data.report += " {:d} held at the limit.".format(limited)
        if self.what == "LEAD" and any(len(copy_of(move, p)) > 1 for p in parts):
            data.report += " A copied finger takes its first joint's Lead, joints in step."
        if cramped:
            data.report += " " + cramped
        self.report({"WARNING"} if cramped else {"INFO"}, data.report)
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# chains: a finger, a tentacle, a spine - parts that hang from one another
#
# Picking Follows one dropdown at a time is the other slow part of a move
# made of many joints, and each joint then wants its bend recorded too. Make
# Chain sets the dropdowns down a line in one click, and Curl takes the bend
# of the first joint and repeats it down the rest.


def touching_distance(part):
    """How far a point is from the mesh of a part standing where it stood at
    Before, as (function of a world point, how big the part is across) - or
    None for a part with no mesh to measure against.

    The distance is to the surface, not to the nearest vertex: a box has eight
    vertices, and a hinge in the middle of one of its faces is a long way from
    all of them.
    """
    obj = bpy.data.objects.get(part.name)
    if (obj is None or obj.type != "MESH" or not part.has_before
            or not len(obj.data.vertices)):
        return None
    before = as_matrix(part.before)
    values = [0.0] * (3 * len(obj.data.vertices))
    obj.data.vertices.foreach_get("co", values)
    world = [before @ Vector(values[i:i + 3]) for i in range(0, len(values), 3)]
    across = (Vector([max(v[a] for v in world) for a in range(3)])
              - Vector([min(v[a] for v in world) for a in range(3)])).length
    polygons = [tuple(poly.vertices) for poly in obj.data.polygons]
    if polygons:
        tree = BVHTree.FromPolygons(world, polygons)

        def distance(point):
            found = tree.find_nearest(point)
            return (point - found[0]).length if found[0] is not None else math.inf
    else:
        def distance(point):
            return min((point - v).length for v in world)
    return distance, across


def chain_order(rig, move, parts, root):
    """The parts in the order a chain runs through them, from the root.

    A joint is built at the far end of the part before it, so from the part
    the chain has got to, the next is the one whose pivot touches that part's
    mesh - within a twentieth of how big it is across - and, of those, the one
    whose pivot is farthest from the part's own: the far end, not the near one.
    That is what tells the pleats of a folded leaf apart, where the third
    segment's pivot is back by the first's and no nearness can say which comes
    next. When nothing touches, as with gaps between the parts or pivots left
    in the middle of them, it is the nearest pivot, measured between pivots at
    Before; parts equally near keep the order they were listed in.
    """
    spots = {p.name: where for p, where in zip(parts, spots_of(rig, move, parts))}
    # The pivots as they are, not the middles spots_of falls back on.
    pivots = {p.name: part_spot(rig, move, p) for p in parts}
    order = [root]
    left = [p for p in parts if p.name != root.name]
    while left:
        here = order[-1]
        measure = touching_distance(here)
        near = []
        if measure is not None:
            distance, across = measure
            near = [n for n in range(len(left))
                    if distance(pivots[left[n].name]) <= 0.05 * across]
        if near:
            pick = max(near, key=lambda n: (pivots[left[n].name] - pivots[here.name]).length)
        else:
            where = spots[here.name]
            pick = min(range(len(left)), key=lambda n: (spots[left[n].name] - where).length)
        order.append(left.pop(pick))
    return order


class RIGMOVES_OT_make_chain(bpy.types.Operator):
    bl_idname = "rigmoves.make_chain"
    bl_label = "Make Chain"
    bl_description = ("Make the selected parts follow one another down a line, "
                      "starting from the active one: each joint is the one "
                      "built at the far end of the part before it - failing "
                      "that, the nearest pivot")
    bl_options = {"REGISTER", "UNDO"}
    index: bpy.props.IntProperty(options={"HIDDEN"})

    def refuse(self, data, said):
        data.report = said
        self.report({"WARNING"}, said)
        return {"CANCELLED"}

    def execute(self, context):
        rig, data, move = move_at(context, self.index, self)
        if move is None:
            return {"CANCELLED"}
        chosen = {o.name for o in context.selected_objects}
        parts = [p for p in move.parts if p.kind == "OBJECT" and p.name in chosen]
        active = context.view_layer.objects.active
        root = move.parts.get(active.name) if active is not None else None
        if len(parts) < 2:
            return self.refuse(data, "Select the parts that make the chain - two at "
                                     "least - with the one it starts from active.")
        if root is None or root.name not in {p.name for p in parts}:
            return self.refuse(data, "Make the part the chain starts from the active "
                                     "object, and keep it selected with the others.")
        if root.leader:
            return self.refuse(data, "'{:s}' rides along with '{:s}', so a chain cannot "
                                     "start from it.".format(short(root.name, 18),
                                                              short(root.leader, 18)))
        order = chain_order(rig, move, parts, root)
        # Copies of a whole chain ride joint for joint only while the chain
        # they copy is the one they were made against.
        paired = {p.name for p in move.parts if p.leader and riding_on(move, p)}
        # The links the chosen parts already have to one another are replaced:
        # kept, they are what refuses a chain made from the other end - the
        # last link of the old one closes a loop with the first of the new.
        # A part the chain starts from may follow something outside the
        # chosen parts - a finger on a palm - and keeps that.
        chosen_names = {p.name for p in parts}
        old = {p.name: p.follows for p in parts if p.follows in chosen_names}
        was = {p.name: p.follows for p in parts if p.follows}
        for name in old:
            move.parts[name].follows = ""
        # One link at a time, through the same choice the Follows list makes:
        # a rider, a curved part, a loop - each is turned down there, with its
        # reason, and the chain stops at that point.
        linked, stopped = [root], ""
        for before, part in zip(order[:-1], order[1:]):
            data.report = ""
            part.follows = before.name
            if part.follows != before.name:
                stopped = data.report
                break
            linked.append(part)
        if len(linked) < 2:
            # A chain refused at its first link changes nothing.
            for name, follows in old.items():
                move.parts[name].follows = follows
            return self.refuse(data, stopped)
        # A chain that stopped part way leaves the parts it did not reach as
        # they were: their old links were only cleared to make room for new
        # ones, and no new one came. Put back through the property, so a link
        # that would now close a loop is still turned down.
        reached = {p.name for p in linked}
        for name, follows in old.items():
            if name not in reached:
                move.parts[name].follows = follows
        said = "Chain: " + " > ".join(short(p.name, 14) for p in linked)
        notes = []
        if stopped:
            notes.append("Stopped there. " + stopped)
        elif move.built and parent_pending(rig, data, move):
            notes.append("Build to put it into effect.")
        replaced = ["{:s} followed {:s}".format(short(name, 12), short(follows, 12))
                    for name, follows in was.items() if move.parts[name].follows != follows]
        if replaced:
            notes.append("Replaced: {:s}{:s}.".format(
                ", ".join(replaced[:3]),
                " and {:d} more".format(len(replaced) - 3) if len(replaced) > 3 else ""))
        loosened = paired - {p.name for p in move.parts if p.leader and riding_on(move, p)}
        if loosened:
            one = len(loosened) == 1
            notes.append("{:s} no longer {:s} joint for joint: take {:s} out with "
                         "{:s} under Riding along, then Ride Along again to copy the "
                         "new chain.".format(
                             "1 joint of a copied chain" if one else
                             "{:d} joints of copied chains".format(len(loosened)),
                             "rides" if one else "ride",
                             "that copy" if one else "those copies",
                             "its x" if one else "their x"))
        if notes:
            said += ". " + " ".join(notes)
        data.report = said
        self.report({"WARNING"} if stopped else {"INFO"}, said)
        return {"FINISHED"}


def chain_below(move, root):
    """Every part that follows `root`, directly or not, as (part, how many
    parts below it), parents first."""
    out = []
    for part in follow_order(move, chain_parts(move)):
        if part.name == root.name:
            continue
        steps, name, seen = 1, part.follows, {part.name}
        while name and name not in seen:
            if name == root.name:
                out.append((part, steps))
                break
            seen.add(name)
            above_part = move.parts.get(name)
            name = above_part.follows if above_part is not None else ""
            steps += 1
    return out


def carried_by(part):
    """How far a part has been moved from its Before, as a matrix in the
    world: where it stands now, less where it started. None for a part whose
    object is gone - deleted or renamed, which the rest of the add-on lives
    with."""
    obj = bpy.data.objects.get(part.name)
    if obj is None:
        return None
    return obj.matrix_world @ as_matrix(part.before).inverted_safe()


def bend_of(move, root):
    """How far the root has been turned from its Before, as a quaternion in
    its own axes - about its own pivot, the way a joint bends. Where the
    root's pivot has gone is not part of it. A root that itself follows
    something is measured from what carries it."""
    moved = carried_by(root)
    ahead = move.parts.get(root.follows) if root.follows else None
    carrying = carried_by(ahead) if ahead is not None else None
    # A part it follows that has lost its object carries it nowhere.
    if carrying is not None:
        moved = carrying.inverted_safe() @ moved
    turn = moved.decompose()[1].normalized()
    frame = standing(as_matrix(root.before))[0].to_quaternion()
    return frame.inverted() @ turn @ frame


def turn_angle(turn):
    """How far a turn goes, in radians, taking the short way round."""
    size = math.sqrt(turn.x * turn.x + turn.y * turn.y + turn.z * turn.z)
    return 2.0 * math.atan2(size, abs(turn.w))


def quaternion_power(turn, power):
    """A turn made `power` times as far, about the same axis, the short way
    round: half of it, or twice, or none. Slerp only goes between 0 and 1."""
    if turn.w < 0.0:
        turn = -turn
    size = math.sqrt(turn.x * turn.x + turn.y * turn.y + turn.z * turn.z)
    if size < 1e-12:
        return Quaternion()
    return Quaternion((turn.x / size, turn.y / size, turn.z / size),
                      turn_angle(turn) * power)


def shows_a_pose(rig, parts):
    """The bound parts of this list whose bone is not standing at rest on
    screen - read the way Record reads it, as what the bone does to the
    world as it is showing now."""
    bent = []
    for part in parts:
        pose_bone = rig.pose.bones.get(part.bone_name) if is_bound(part) else None
        if pose_bone is None:
            continue
        shown = pose_bone.matrix @ pose_bone.bone.matrix_local.inverted_safe()
        if not same_matrix(shown, Matrix.Identity(4)):
            bent.append(part)
    return bent


class RIGMOVES_OT_curl(bpy.types.Operator):
    bl_idname = "rigmoves.curl"
    bl_label = "Curl"
    bl_description = ("Repeat the active part's bend down every part that "
                      "follows it, each about its own pivot: pose the first "
                      "joint of a finger or tentacle and the rest bend with "
                      "it. Record After afterwards to keep it. How much each "
                      "joint keeps of the one before can be set in the Adjust "
                      "Last Operation panel")
    bl_options = {"REGISTER", "UNDO"}
    index: bpy.props.IntProperty(options={"HIDDEN"})
    factor: bpy.props.FloatProperty(
        name="Each next joint ×", default=1.0, min=0.0, max=10.0, soft_max=2.0,
        description="How much of the bend each joint keeps from the one before "
                    "it: 1 bends every joint as much as the first, 0.5 halves "
                    "it at each joint, so the tip curls least")

    def refuse(self, data, said):
        data.report = said
        self.report({"WARNING"}, said)
        return {"CANCELLED"}

    def execute(self, context):
        rig, data, move = move_at(context, self.index, self)
        if move is None:
            return {"CANCELLED"}
        active = context.view_layer.objects.active
        root = move.parts.get(active.name) if active is not None else None
        if root is None or root.kind != "OBJECT" or not root.has_before:
            return self.refuse(data, "Make the first joint of the chain - an object "
                                     "of this move - the active object, then Curl.")
        if root.leader:
            return self.refuse(data, "'{:s}' rides along with '{:s}', so it has no "
                                     "bend of its own to repeat.".format(
                                         short(root.name, 18), short(root.leader, 18)))
        below = [(p, steps) for p, steps in chain_below(move, root) if p.has_before]
        if not below:
            return self.refuse(data, "Nothing follows '{:s}'. Set Follows first, or "
                                     "select the parts and press Make Chain."
                                     .format(short(root.name, 18)))
        # A part whose object is gone cannot be bent. At the end of a chain it
        # is left out; in the middle, what hangs from it cannot be carried to
        # where it would be, and nothing is guessed.
        lost = [p for p, _steps in below if bpy.data.objects.get(p.name) is None]
        gone = {p.name for p in lost}
        for part in lost:
            if any(other.follows == part.name and other.name not in gone
                   for other, _steps in below):
                return self.refuse(data, "'{:s}' has lost its object, and parts hang from "
                                         "it. Put it back, or take it out of the move, "
                                         "then Curl.".format(short(part.name, 18)))
        below = [(p, steps) for p, steps in below if p.name not in gone]
        if not below:
            return self.refuse(data, "Nothing is left to bend below '{:s}': the objects "
                                     "of the parts that follow it are gone."
                                     .format(short(root.name, 18)))
        # A joint already showing a pose has its own bend on top of its rest
        # position, and what Record would then read is not what Curl made.
        context.view_layer.update()
        if shows_a_pose(rig, [root] + [p for p, _steps in below]):
            said = ("Curl works from rest: drag Play to 0 (or press To Before), "
                    "pose the first joint, then Curl.")
            # The eye, and a Record, leave the sliders paused with the pose
            # still showing, and To Before does not clear that: a Build does.
            if data.posing:
                said += " The sliders are paused with a pose showing, so Build first."
            return self.refuse(data, said)
        turn = bend_of(move, root)
        if turn_angle(turn) < 1e-4:
            return self.refuse(data, "'{:s}' has not been turned. Turn it about its "
                                     "pivot, then Curl.".format(short(root.name, 18)))
        names = [(p.name, steps) for p, steps in below]
        # Parents first, one at a time: each is placed from where the part it
        # follows now stands, so a bend is carried down the chain and the
        # joints stay together.
        for name, steps in names:
            part = move.parts[name]
            obj = bpy.data.objects.get(name)
            ahead = move.parts.get(part.follows)
            carry = carried_by(ahead) if ahead is not None else None
            if obj is None or carry is None:
                continue
            before = as_matrix(part.before)
            frame = standing(before)[0].to_3x3()
            spin = (frame @ quaternion_power(turn, self.factor ** steps).to_matrix()
                    @ frame.inverted_safe()).to_4x4()
            pivot = before @ Vector(part.pivot)
            about = Matrix.Translation(pivot) @ spin @ Matrix.Translation(-pivot)
            obj.matrix_world = carry @ about @ before
            context.view_layer.update()
        said = "{:s} below '{:s}' now {:s} {:g} degrees like it".format(
            counted(len(names), "part"), short(root.name, 18),
            "bends" if len(names) == 1 else "bend",
            round(math.degrees(turn_angle(turn)), 1))
        if abs(self.factor - 1.0) > 1e-9:
            said += ", each joint x{:g} of the one before".format(self.factor)
        if gone:
            said += " ({:d} left out: {:s} gone)".format(
                len(gone), "its object is" if len(gone) == 1 else "their objects are")
        # Copies of the chain play what is recorded, once a Build has copied
        # it onto them: Record alone leaves them on the old path.
        named = {root.name} | {name for name, _steps in names}
        if any(p.leader in named for p in move.parts):
            said += ". Record After, or a Step, then Build, to keep it and let the copies follow."
        else:
            said += ". Record After, or a Step, to keep it."
        data.report = said
        self.report({"INFO"}, data.report)
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# rings: a fan, a gear, a crown of spikes - one part, made many times round
#
# Modelling the same part eight times and selecting them for Ride Along is the
# first slow part of a flower. Ring makes the copies, stands them round a
# point, and sets them riding along with the part they came from.

RING_CENTRES = [("CURSOR", "3D Cursor", "Round the point the 3D cursor is on"),
                ("ORIGIN", "World Origin", "Round the world's origin")]
RING_AXES = [("Z", "World Z", "About the world's up axis: a ring lying flat"),
             ("CURSOR_Z", "3D Cursor's Z",
              "About the 3D cursor's own Z axis, turned however the cursor is: "
              "for a ring that is tipped. Placing the cursor with Shift+right-click "
              "turns it to face the view, which tips every ring made with this"),
             ("X", "World X", "About the world's X axis"),
             ("Y", "World Y", "About the world's Y axis")]


RING_USES = [
    ("COPY", "Make copies",
     "Make a new copy of the part for every place round the ring, whatever "
     "already stands there"),
    ("ADOPT", "Use what's there",
     "Take up the objects already modelled in the places round the ring, and "
     "make nothing. Only a copy of the part's mesh, standing where a copy "
     "would, and safe to take, is taken; anything else is left as it is and "
     "named"),
    ("FILL", "Fill the gaps",
     "Take up what is already modelled in a place, and copy the part only "
     "into the places where nothing stands: never a copy on top of a petal "
     "that is there")]


def ring_centre(scene, which):
    """The point a ring goes round."""
    if which == "CURSOR":
        return scene.cursor.location.copy()
    return Vector((0.0, 0.0, 0.0))


def ring_axis(scene, which):
    """The direction a ring goes round."""
    if which == "CURSOR_Z":
        return (scene.cursor.matrix.to_3x3() @ Vector((0.0, 0.0, 1.0))).normalized()
    return Vector([1.0 if name == which else 0.0 for name in AXES])


def copy_for_ring(source, name, linked):
    """A copy of a part's object that has nothing of the rig about it.

    Everything that bound or hung the original is taken off: the Armature
    modifier of any rig of ours, the groups named after our bones, the mark
    of a follower, the parent. Groups are on the mesh, so a copy that shares
    the original's mesh cannot lose them without the original losing them
    too; it is left with them, and Build gives it a mesh of its own when it
    binds it.
    """
    copy = source.copy()
    if not linked and source.data is not None:
        copy.data = source.data.copy()
    copy.name = name
    for collection in source.users_collection:
        collection.objects.link(copy)
    rigs = [o for o in bpy.data.objects if o.type == "ARMATURE" and len(o.rigmoves.moves)]
    ours = {o.name for o in rigs}
    for modifier in list(copy.modifiers):
        if (modifier.type == "ARMATURE" and modifier.object is not None
                and modifier.object.name in ours):
            copy.modifiers.remove(modifier)
    if copy.data is not None and copy.data.users == 1:
        bones = set()
        for owner in rigs:
            bones |= our_part_bones(owner.rigmoves) | our_bone_names(owner.rigmoves)
        for group in [g for g in copy.vertex_groups if g.name in bones]:
            copy.vertex_groups.remove(group)
    if copy.get(FOLLOW_MARK):
        del copy[FOLLOW_MARK]
    copy.parent = None
    copy.matrix_parent_inverse = Matrix.Identity(4)
    # Keys on its own transform would send every copy back to the original's.
    if own_transform_curves(copy):
        copy.animation_data_clear()
    return copy


def names_in_use():
    """Every name a new copy must not take: each object's, and each part's of
    every rig of ours - a part whose object was deleted is still in its move,
    and an object that comes back under its name is taken for that part, not
    for something new."""
    taken = {o.name for o in bpy.data.objects}
    for owner in bpy.data.objects:
        if owner.type == "ARMATURE":
            for move in owner.rigmoves.moves:
                taken.update(p.name for p in move.parts)
    return taken


def free_ring_number(joints, taken):
    """The lowest number, from 2, with every one of these names free: the
    joints of a copied finger share a number, "Seg1 2", "Seg2 2"."""
    number = 2
    while any("{:s} {:d}".format(joint, number) in taken for joint in joints):
        number += 1
    return number


def discard_copies(copies):
    """Take copies made for a ring away again, and their meshes."""
    for copy in copies:
        mesh = copy.data
        bpy.data.objects.remove(copy, do_unlink=True)
        if mesh is not None and mesh.users == 0:
            bpy.data.meshes.remove(mesh)


def mesh_points(obj):
    """The vertices of a mesh object, in its own space, in vertex order."""
    values = [0.0] * (3 * len(obj.data.vertices))
    obj.data.vertices.foreach_get("co", values)
    return [Vector(values[i:i + 3]) for i in range(0, len(values), 3)]


def diagonal(points):
    """How far across the box round these points is, corner to corner."""
    if not points:
        return 0.0
    low = Vector([min(p[a] for p in points) for a in range(3)])
    high = Vector([max(p[a] for p in points) for a in range(3)])
    return (high - low).length


def parts_of_ours():
    """The name of every part of every move of every rig of ours."""
    known = set()
    for owner in bpy.data.objects:
        if owner.type == "ARMATURE":
            for move in owner.rigmoves.moves:
                known.update(p.name for p in move.parts)
    return known


def world_stats(obj, matrix):
    """(average, low, high) of an object's vertices carried by `matrix`: where
    the middle of them is, and the corners of the box round them, in the
    world."""
    values = [0.0] * (3 * len(obj.data.vertices))
    obj.data.vertices.foreach_get("co", values)
    try:
        import numpy
    except ImportError:
        numpy = None
    if numpy is not None:
        world = (numpy.array(values).reshape(-1, 3) @ numpy.array(matrix.to_3x3()).T
                 + numpy.array(matrix.translation))
        return (Vector(world.mean(axis=0).tolist()), Vector(world.min(axis=0).tolist()),
                Vector(world.max(axis=0).tolist()))
    points = [matrix @ Vector(values[i:i + 3]) for i in range(0, len(values), 3)]
    return (sum(points, Vector()) / len(points),
            Vector([min(p[a] for p in points) for a in range(3)]),
            Vector([max(p[a] for p in points) for a in range(3)]))


def has_own_motion(obj):
    """Whether an object moves itself: keys on its transform, a driver on it,
    or an animation in the NLA. Binding it would lift them, or the rig would
    play against them."""
    if obj.animation_data is None:
        return False
    return bool(own_transform_curves(obj)
                or any(d.data_path in TRANSFORM_PATHS for d in obj.animation_data.drivers)
                or len(obj.animation_data.nla_tracks))


def why_not_taken(obj, known, layer):
    """Why a ring may not take an object up, in a few words - or "" when it
    may. Taking one up binds it, and may stand it on a new frame: only an
    object this add-on can change for good, and the user can select, is safe
    to take unasked."""
    if obj.name in known:
        return "is already part of a move"
    if obj.library is not None or obj.data.library is not None:
        return "is linked from a library"
    if not obj.is_editable or not obj.data.is_editable:
        return "cannot be edited"
    if has_own_motion(obj):
        return "has keys or drivers of its own"
    if layer.objects.get(obj.name) is None:
        return "is not in this view layer"
    if not obj.visible_get():
        return "is hidden"
    # Whether it can be selected is asked of Blender: a collection with
    # selection switched off says nothing on the object itself, and Ride Along
    # works on what is selected.
    was = obj.select_get()
    try:
        obj.select_set(True)
        selectable = obj.select_get()
        obj.select_set(was)
    except RuntimeError:
        return "cannot be selected"
    return "" if selectable else "cannot be selected"


def standing_pool(context, rig, sources):
    """Every mesh object in the scene that could stand in a place of a ring,
    as (object, why it may not be taken up - "" if it may). The parts being
    ringed are not among them, and nor are meshes with no vertices."""
    known = parts_of_ours()
    layer = context.view_layer
    out = []
    for obj in context.scene.objects:
        # An object deleted from a script can leave a None in the layer's list
        # until the next update.
        if (obj is None or obj.type != "MESH" or obj is rig or obj.name in sources
                or obj.data is None or not len(obj.data.vertices)):
            continue
        out.append((obj, why_not_taken(obj, known, layer)))
    return out


def same_shape(mine, wanted, tolerance):
    """Whether two lists of points are the same vertices, in the same order."""
    return len(mine) == len(wanted) and all((a - b).length <= tolerance
                                            for a, b in zip(mine, wanted))


def reach_signature(points):
    """How far each point is from the middle of them all, shortest first: the
    same for a shape standing anywhere, turned any way (or mirrored), and not
    for another shape or another size."""
    if not points:
        return []
    middle = sum(points, Vector()) / len(points)
    return sorted((p - middle).length for p in points)


def alike_in_reach(one, other, tolerance):
    """Whether two signatures (see reach_signature) agree to within `tolerance`."""
    return len(one) == len(other) and all(abs(a - b) <= tolerance for a, b in zip(one, other))


def tree_of(points):
    """A tree to ask for the nearest of these points."""
    tree = KDTree(len(points))
    for number, point in enumerate(points):
        tree.insert(point, number)
    tree.balance()
    return tree


class Joint:
    """One joint of the part being ringed: where it stood at Before, its mesh,
    and how close a copy has to be."""

    def __init__(self, name, seat, source):
        self.name, self.seat = name, seat
        self.local = mesh_points(source)
        self.middle = sum(self.local, Vector()) / len(self.local) if self.local else Vector()
        world = [seat @ p for p in self.local]
        self.across = diagonal(world)
        # A fiftieth of how big it is across: what a vertex may be out by.
        self.tolerance = max(0.02 * self.across, 1e-6)
        # How far out it reaches from its middle, the same whichever way round
        # it stands, which a box round it is not.
        centre = seat @ self.middle
        self.reach = max(((w - centre).length for w in world), default=0.0)
        self.signature = reach_signature(world)


class Seen:
    """An object in the scene as a ring sees it: what it is made of, where it
    stands, and why it may not be taken up. Its points are read when wanted."""

    def __init__(self, obj, why):
        self.obj, self.why, self.name = obj, why, obj.name
        self.count = len(obj.data.vertices)
        self.matrix = obj.matrix_world.copy()
        self.mean, low, high = world_stats(obj, self.matrix)
        self.box = (low + high) * 0.5
        self.half = (high - low).length * 0.5
        self.local = self.world = self.tree = self.signature = None

    def like(self, joint):
        """Whether it is a copy of the joint wherever it stands: the same
        mesh, vertex for vertex - a duplicate, not a lookalike - and the same
        size in the world, which the mesh alone does not say."""
        if self.count != len(joint.local):
            return False
        if not same_shape(self.local_points(), joint.local, joint.tolerance):
            return False
        if self.signature is None:
            self.signature = reach_signature(self.world_points())
        return alike_in_reach(self.signature, joint.signature, joint.tolerance)

    def local_points(self):
        if self.local is None:
            self.local = mesh_points(self.obj)
        return self.local

    def world_points(self):
        if self.world is None:
            self.world = [self.matrix @ p for p in self.local_points()]
        return self.world

    def nearest(self):
        if self.tree is None:
            self.tree = tree_of(self.world_points())
        return self.tree


class Slot:
    """Where a joint would stand in one place of the ring."""

    def __init__(self, joint, turn):
        self.joint = joint
        self.there = turn @ joint.seat
        self.mean = self.there @ joint.middle
        self.points = self.tree = self.centre = None

    def world_points(self):
        if self.points is None:
            self.points = [self.there @ p for p in self.joint.local]
        return self.points

    def box(self):
        """The middle of the box round it, in the world."""
        if self.centre is None:
            points = self.world_points()
            self.centre = Vector([(min(p[a] for p in points) + max(p[a] for p in points)) / 2.0
                                  for a in range(3)])
        return self.centre

    def nearest(self):
        if self.tree is None:
            self.tree = tree_of(self.world_points())
        return self.tree

    def release(self):
        """Forget the points, which a ring of two hundred joints cannot all
        keep; the middle of the box, once worked out, is kept."""
        self.points = self.tree = None


def fit_error(one, slot):
    """How far an object is from being the joint, standing in a place: None if
    it is not a copy of it, else the greatest distance from any of its vertices
    to the nearest of the joint's, or the other way round.

    Vertex for vertex first - the cheap way, for a copy made by copying. Then
    as a set of points, because a mirrored half, or a cube moved without being
    turned, has the very same points with its vertices numbered in another
    order. A mirror image of a shape that is not the same on both sides has
    other points, and never fits.
    """
    joint = slot.joint
    if one.count != len(joint.local):
        return None
    if (one.box - slot.box()).length > 2.0 * joint.tolerance:
        return None
    worst = 0.0
    for have, wanted in zip(one.world_points(), slot.world_points()):
        worst = max(worst, (have - wanted).length)
        if worst > joint.tolerance:
            break
    else:
        return worst
    worst, tree = 0.0, slot.nearest()
    for have in one.world_points():
        worst = max(worst, tree.find(have)[2])
        if worst > joint.tolerance:
            return None
    tree = one.nearest()
    for wanted in slot.world_points():
        worst = max(worst, tree.find(wanted)[2])
        if worst > joint.tolerance:
            return None
    return worst


class Standing:
    """What a look round a ring found.

    placed: {place: {joint name: (object, where it should stand)}} for the
    places whose every joint was found; partial: the places found in part;
    occupied: {place: names} for the places, of those not placed, with
    something standing in them; left: (distance, words) for each object that
    was looked at and is not taken up; off: (name, middle) for each copy of
    the part standing on none of the places; first: (middle, reach) of the
    part; empty: the places with nothing in them.
    """

    def __init__(self):
        self.placed, self.partial, self.occupied = {}, [], {}
        self.left, self.off, self.empty = [], [], []
        self.first = (Vector(), 0.0)
        self.joints = []


def find_standing(pool, joints, turns, free, ours=()):
    """Which of these objects already stand in the places of a ring.

    `joints` are the (name, Before, object) of the part being ringed, one for
    each joint of its chain, `turns` the turn that takes the part to each
    place of the ring, `free` the numbers of those that are to be filled (the
    rest hold a rider already) and `ours` the names of the riders there are.

    An object that may be taken up stands in a place when it is a copy of the
    joint there (see fit_error). The best fit takes each place, and an object
    fits one place only. A place is taken only when every joint of it is
    found; one found in part is left alone, with whatever else is there.

    Nothing else may be copied on top of, taken or not: a place is occupied
    when any mesh object at all - hidden, in a move, of any number of
    vertices - has the middle of the box round it within a quarter of the
    joint's reach of where the joint would be. And the copies of the part that
    stand on none of the places are listed in `off`, for a ring that has been
    made round the wrong centre.
    """
    found = Standing()
    shapes = [Joint(name, seat, source) for name, seat, source in joints]
    found.first = (shapes[0].seat @ shapes[0].middle, shapes[0].reach)
    found.joints = shapes
    seen = [Seen(obj, why) for obj, why in pool]
    slots = {}

    def slot(number, index):
        if (number, index) not in slots:
            slots[(number, index)] = Slot(shapes[index], turns[number])
        return slots[(number, index)]

    hits, others = [], []
    for number in free:
        for index, shape in enumerate(shapes):
            there = slot(number, index)
            for one in seen:
                error = fit_error(one, there)
                if error is not None:
                    (others if one.why else hits).append((error, number, index, one.name))
            there.release()
    hits.sort()
    owner, holder = {}, {}
    for _error, number, index, name in hits:
        if name not in owner and (number, index) not in holder:
            owner[name] = (number, index)
            holder[(number, index)] = name
    by_name = {one.name: one for one in seen}
    for number in free:
        got = [index for index in range(len(shapes)) if (number, index) in holder]
        if len(got) == len(shapes):
            found.placed[number] = {shapes[index].name: (by_name[holder[(number, index)]].obj,
                                                         slot(number, index).there)
                                    for index in got}
        elif got:
            found.partial.append(number)
    used = {obj.name for got in found.placed.values() for obj, _where in got.values()}

    # Standing in a place without being a copy of it.
    standing_in = set()
    for number in free:
        if number in found.placed:
            continue
        names = set()
        for index, shape in enumerate(shapes):
            there = slot(number, index)
            for one in seen:
                if one.name in used:
                    continue
                # Cheap first: the box round it cannot be near unless its
                # average is.
                if (one.mean - there.mean).length > one.half + 2.0 * shape.reach:
                    continue
                if (one.box - there.box()).length <= 0.25 * shape.reach:
                    names.add(one.name)
            there.release()
        if names or number in found.partial:
            found.occupied[number] = sorted(names)
            standing_in |= names
        else:
            found.empty.append(number)

    # Copies of the part, standing on no place at all.
    first = shapes[0]
    for one in seen:
        # What a move plays already is not a stray copy.
        if (one.name in used or one.why == "is already part of a move"
                or not one.like(first)):
            continue
        def on_a_place(number):
            there = slot(number, 0)
            close = (one.box - there.box()).length <= 0.25 * first.reach
            there.release()
            return close

        if not any(on_a_place(number) for number in range(len(turns))):
            found.off.append((one.name, one.mean))

    # What was left out, and why: those most like a copy, or standing in a
    # place, and those nearest the ring's places first.
    rival = {}
    for _error, number, index, name in hits + others:
        if holder.get((number, index), name) != name:
            rival.setdefault(name, holder[(number, index)])
    for one in seen:
        if one.name in used or one.name in ours:
            continue
        likes = [shape for shape in shapes if len(shape.local) == one.count]
        near = min((((one.mean - slot(number, index).mean).length, shape)
                    for number in range(len(turns)) for index, shape in enumerate(shapes)),
                   key=lambda pair: pair[0])
        fits = one.name in owner or any(name == one.name for _e, _n, _i, name in others)
        in_a_place = one.name in standing_in or near[0] <= 0.25 * near[1].reach
        # Something that is not a copy and is not by the ring is not news, and
        # nor is something already part of a move that does not fit or stand
        # in a place.
        if not (fits or in_a_place or (likes and not one.why)):
            continue
        like = (min(likes, key=lambda shape: (
            int(abs(max((w - one.mean).length for w in one.world_points()) - shape.reach)
                / max(shape.reach, 1e-6) / 0.1),
            min((one.mean - slot(number, shapes.index(shape)).mean).length
                for number in range(len(turns))))) if likes else near[1])
        copy = one.like(like)
        if one.why:
            why = one.why
        elif one.name in rival:
            why = "stands on the same place as '{:s}'".format(short(rival[one.name], 18))
        elif one.name in owner:
            why = "fits a place where the rest of the chain is missing"
        elif in_a_place:
            why = ("is a copy of '{:s}' that is not turned to its place" if copy else
                   "stands in a place and is not a copy of '{:s}'").format(
                short(like.name, 18))
        elif copy:
            why = "is a copy of '{:s}' that stands off the ring".format(short(like.name, 18))
        else:
            why = "is not a copy of '{:s}'".format(short(like.name, 18))
        found.left.append((near[0], one.name, "'{:s}' {:s}".format(short(one.name, 18), why)))
    found.left.sort()
    return found


def turn_faces_over(mesh):
    """Reverse the winding of every face, so that a mesh that was mirrored
    faces outwards again."""
    editing = bmesh.new()
    editing.from_mesh(mesh)
    bmesh.ops.reverse_faces(editing, faces=list(editing.faces))
    editing.to_mesh(mesh)
    editing.free()


def signed_volume(mesh):
    """The volume a mesh's faces enclose, counted from its own origin: positive
    when they face outwards, negative inside out. For a shell that is open
    it is no volume, but the same shape wound the other way gives the
    opposite sign all the same."""
    values = [0.0] * (3 * len(mesh.vertices))
    mesh.vertices.foreach_get("co", values)
    points = [Vector(values[i:i + 3]) for i in range(0, len(values), 3)]
    total = 0.0
    for poly in mesh.polygons:
        ring = [points[i] for i in poly.vertices]
        for a, b in zip(ring[1:], ring[2:]):
            total += ring[0].dot(a.cross(b)) / 6.0
    return total


def look_of(obj):
    """How an object looks now, from what Blender evaluates: where its
    vertices are in the world, and which way each face faces as it is shown -
    the way it winds, turned back by a mirrored frame."""
    graph = bpy.context.evaluated_depsgraph_get()
    shown = obj.evaluated_get(graph)
    mesh = shown.to_mesh()
    try:
        matrix = shown.matrix_world.copy()
        sign = -1.0 if matrix.determinant() < 0.0 else 1.0
        points = [matrix @ v.co for v in mesh.vertices]
        facing = []
        for poly in mesh.polygons:
            ring = [points[i] for i in poly.vertices]
            normal = Vector()
            for a, b in zip(ring, ring[1:] + ring[:1]):
                normal += a.cross(b)
            facing.append(normal.normalized() * sign if normal.length > 1e-12 else normal)
    finally:
        shown.to_mesh_clear()
    return points, facing


def looks_the_same(before, now, tolerance):
    """Whether two looks (see look_of) are the same, to within `tolerance`."""
    if len(before[0]) != len(now[0]) or len(before[1]) != len(now[1]):
        return False
    if any((a - b).length > tolerance for a, b in zip(before[0], now[0])):
        return False
    return all(a.length < 0.5 or b.length < 0.5 or a.dot(b) > 0.99
               for a, b in zip(before[1], now[1]))


SAFE_MODIFIERS = ("SUBSURF", "TRIANGULATE", "EDGE_SPLIT", "WEIGHTED_NORMAL")

# What is said of an object that is not on its frame and cannot be put there.
REFRAME_ADVICE = ("cannot be re-framed safely ({:s}): set its origin and rotation like "
                  "the leader's, or use Make copies")


def reframe_blocker(obj, where, rig, users):
    """Why an object cannot safely be stood on a new frame, in a few words - or
    "" if nothing in it depends on the frame it stands in.

    Its look is worked out from the mesh and the frame alone only if nothing
    else reads the frame: not a constraint, a modifier that measures from the
    object, an instance, a particle system, a hook, another object that follows
    it. What is left is also checked on the evaluated result, after.
    """
    if obj.constraints:
        return "it has constraints"
    if obj.instance_type != "NONE":
        return "it instances other objects"
    if len(obj.particle_systems):
        return "it has particles"
    if obj.parent is not None and obj.parent_type != "OBJECT":
        return "it hangs from a vertex or a bone"
    for user in users.get(obj, ()):
        if not (isinstance(user, bpy.types.Object) and user.parent is obj
                and user.parent_type == "OBJECT"):
            return "'{:s}' depends on it".format(short(user.name, 14))
    plain = all(abs(abs(s) - 1.0) < 1e-4
                for s in list(obj.matrix_world.to_scale()) + list(where.to_scale()))
    for modifier in obj.modifiers:
        if modifier.type in SAFE_MODIFIERS:
            continue
        if modifier.type == "ARMATURE" and modifier.object is not None and modifier.object is not rig:
            continue
        # These measure in the object's own units, so only a scale of 1 is the
        # same before and after.
        if modifier.type in ("BEVEL", "SOLIDIFY") and plain:
            continue
        return "its {:s} modifier depends on its frame".format(modifier.name)
    if (where.inverted_safe() @ obj.matrix_world).determinant() < 0.0 and obj.data.has_custom_normals:
        return "it is mirrored and has custom normals"
    return ""


def reframe(obj, matrix):
    """Stand an object on `matrix`, and move its mesh the other way, so that
    nothing is seen to move: its origin and axes become the ones a copy would
    have, with its vertices where they are in the world.

    Its mesh is a new one, and the old one is kept until the ring is settled:
    anything else that shares the old one stays as it was, and putting it back
    is exact. Whatever hangs from the object by its object is held where it
    is; what hangs from a vertex follows the vertices, which have not moved.
    Returns what put_back needs to undo it.
    """
    was = obj.matrix_world.copy()
    old = obj.data
    mesh = old.copy()
    obj.data = mesh
    inside = matrix.inverted_safe() @ was
    mesh.transform(inside, shape_keys=True)
    # A mirrored object (negative scale) shows its faces turned back the
    # right way; stood on a plain matrix they need turning by hand.
    if inside.determinant() < 0.0:
        turn_faces_over(mesh)
    mesh.update()
    kept = [(kid, kid.matrix_world.copy()) for kid in obj.children
            if kid.parent_type == "OBJECT"]
    obj.matrix_world = matrix
    for kid, world in kept:
        kid.matrix_world = world
    return obj, was, old, kept


def put_back(framed):
    """Undo reframe, last first: the old mesh, the old frame, the children."""
    for obj, was, old, kept in reversed(framed):
        fresh = obj.data
        obj.data = old
        if fresh.users == 0:
            bpy.data.meshes.remove(fresh)
        obj.matrix_world = was
        for kid, world in kept:
            kid.matrix_world = world


def settle(framed):
    """Let a re-frame stand: the old meshes nobody uses any more go, and the
    new ones take their names."""
    for obj, _was, old, _kept in framed:
        if old.users == 0:
            name = old.name
            bpy.data.meshes.remove(old)
            obj.data.name = name


class RIGMOVES_OT_ring(bpy.types.Operator):
    bl_idname = "rigmoves.ring"
    bl_label = "Ring"
    bl_description = ("Make copies of the active part - or of the whole chain "
                      "it is part of, a finger - round the 3D cursor and let "
                      "them ride along with it, each doing its move from its "
                      "own place: one blade becomes a fan. Or take up the "
                      "copies already modelled there. Select the part first")
    bl_options = {"REGISTER", "UNDO"}
    index: bpy.props.IntProperty(options={"HIDDEN"})
    use: bpy.props.EnumProperty(
        name="Use", items=RING_USES, default="FILL",
        description="Whether to make the copies, take up the ones already "
                    "modelled, or both: copies only where nothing stands")
    count: bpy.props.IntProperty(
        name="Count", default=6, min=2, max=200,
        description="How many there are round the ring, the original included")
    center: bpy.props.EnumProperty(name="Round", items=RING_CENTRES, default="CURSOR")
    axis: bpy.props.EnumProperty(name="About", items=RING_AXES, default="Z")
    linked: bpy.props.BoolProperty(
        name="Linked copies", default=True,
        description="Share the original's mesh, so editing one edits them all. "
                    "Build gives each part a mesh of its own, because Blender "
                    "keeps a mesh's vertex groups with the mesh")
    lead_step: bpy.props.IntProperty(
        name="Lead step", default=0, min=-50, max=50,
        description="What each copy's Lead is stepped by, further from the "
                    "original round the ring: the two next to it are 1 step "
                    "out, the two next to those 2, and so on, both ways round. "
                    "Below 0 each waits more than the one before it; above 0 "
                    "each goes earlier. 0 sends them all together")

    def refuse(self, data, said):
        data.report = said
        self.report({"WARNING"}, said)
        return None

    def plan(self, context):
        """(rig, data, move, part, members, chain) - or None, with the reason
        said. Everything that can be refused is asked here, before a thing is
        made.

        The part and every part that follows it, below it, are made into the
        ring; the parts it follows are not. A blade that hangs from a hub is
        ringed without the hub, and each copy then hangs from what the blade
        does. A finger's first joint is the whole finger, and Ride Along takes
        the copies joint for joint.
        """
        rig, data, move = move_at(context, self.index, self)
        if move is None:
            return None
        active = context.view_layer.objects.active
        part = move.parts.get(active.name) if active is not None else None
        if part is None or part.kind != "OBJECT":
            return self.refuse(data, "Select the part to make a ring from - an object "
                                     "of '{:s}' - and make it the active one."
                                     .format(move.name))
        if part.leader:
            return self.refuse(data, "'{:s}' rides along with '{:s}'. Make the ring from "
                                     "that part instead.".format(
                                         short(part.name, 18), short(part.leader, 18)))
        members = [part] + [p for p, _steps in chain_below(move, part)]
        for joint in members:
            obj = bpy.data.objects.get(joint.name)
            if not joint.has_before or obj is None or obj.type != "MESH":
                return self.refuse(data, "'{:s}' has no Before recorded yet.".format(
                    short(joint.name, 18)))
        # Riding along on a built move is a Build, and Build puts a dragged
        # part back: refused now, with nothing made, rather than half way.
        if move.built and not keeps_drags(self, data):
            return None
        return rig, data, move, part, members, chain_of(move, part)

    def invoke(self, context, event):
        if self.plan(context) is None:
            return {"CANCELLED"}
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = False
        layout.label(text="Use")
        layout.prop(self, "use", expand=True)
        layout.use_property_split = True
        layout.use_property_decorate = False
        layout.prop(self, "count")
        layout.prop(self, "center")
        layout.prop(self, "axis")
        copying = layout.row()
        copying.active = self.use != "ADOPT"
        copying.prop(self, "linked")
        layout.prop(self, "lead_step")

    def execute(self, context):
        found = self.plan(context)
        if found is None:
            return {"CANCELLED"}
        rig, data, move, part, members, chain = found
        # Read before anything is added: adding parts can move the list.
        name = part.name
        first_joint = members[0].name
        seat = as_matrix(part.before)
        joints = [(joint.name, as_matrix(joint.before), bpy.data.objects[joint.name])
                  for joint in members]
        scene = context.scene
        centre, axis = ring_centre(scene, self.center), ring_axis(scene, self.axis)

        # The places round the ring, from the part's Before - not from where it
        # stands now, which may be its After. A place that already holds a
        # rider of this part is left alone: a second ring over the first, or
        # a bigger one, adds the places that are missing and not a copy on
        # top of a copy. A copy that has been deleted holds nothing.
        held = [as_matrix(p.before) for p in move.parts
                if p.leader == name and bpy.data.objects.get(p.name) is not None]
        turns, free, skipped = [], [], 0
        for number in range(1, self.count):
            turn = (Matrix.Translation(centre)
                    @ Matrix.Rotation(math.radians(360.0 * number / self.count), 4, axis)
                    @ Matrix.Translation(-centre))
            turns.append(turn)
            where = turn @ seat
            slack = 1e-4 * (1.0 + max(abs(c) for c in where.translation))
            if any(same_matrix(have, where, slack) for have in held):
                skipped += 1
            else:
                free.append(len(turns) - 1)
        if not free:
            self.refuse(data, "Every place round that ring already has a copy of '{:s}': "
                              "there is nothing to add.".format(short(name, 18)))
            return {"CANCELLED"}

        # What already stands in those places, when it is to be used.
        standing, notes = Standing(), ""
        if self.use != "COPY":
            context.view_layer.update()
            ours = {p.name for p in move.parts if p.leader == name}
            standing = find_standing(standing_pool(context, rig, {j[0] for j in joints}),
                                     joints, turns, free, ours)
            # Copies of the part standing near the ring and on none of its
            # places mean the ring is round the wrong point, or has the wrong
            # count: copying into the places between them doubles the flower.
            middle, reach = standing.first
            along = middle - centre
            radius = max((along - axis * along.dot(axis)).length, reach)

            def in_the_ring(spot):
                """Within the disc of the ring, and not above or below it: a
                second ring at another height is another ring."""
                off = spot - centre
                return ((off - axis * off.dot(axis)).length <= 1.5 * radius
                        and abs(off.dot(axis) - along.dot(axis)) <= 1.5 * radius)

            near = [n for n, spot in standing.off if in_the_ring(spot)]
            if near:
                notes = "{:s} of '{:s}' {:s} near the ring but off its places: check the centre (3D cursor) and Count.".format(
                    counted(len(near), "copy", "copies"), short(name, 18),
                    "stands" if len(near) == 1 else "stand")
                if self.use == "FILL":
                    self.refuse(data, notes + " Nothing done.")
                    return {"CANCELLED"}

        # Objects to be taken up that are not on the frame a copy would have
        # are stood on it - but only those where that is provably safe: the
        # result is looked at, and anything that looks different is put back.
        placed = dict(standing.placed)
        gave_up, framed, far = {}, [], 0.0
        sizes = {joint.name: joint.across for joint in standing.joints}
        volumes = {joint_name: signed_volume(source.data) for joint_name, _seat, source in joints}
        if placed:
            users = bpy.data.user_map(
                subset={obj for got in placed.values() for obj, _where in got.values()},
                value_types={"OBJECT"})
            jobs = {}
            for number in list(placed):
                work = []
                for joint_name, (obj, where) in placed[number].items():
                    slack = 1e-4 * (1.0 + max(abs(c) for c in where.translation))
                    if same_matrix(obj.matrix_world, where, slack):
                        continue
                    why = reframe_blocker(obj, where, rig, users)
                    if why:
                        gave_up[number] = (obj.name, REFRAME_ADVICE.format(why))
                        break
                    work.append((joint_name, obj, where))
                else:
                    jobs[number] = work
            if any(jobs.values()):
                context.view_layer.update()
                before = {obj.name: look_of(obj)
                          for work in jobs.values() for _joint, obj, _where in work}
                done = {number: [reframe(obj, where) for _joint, obj, where in work]
                        for number, work in jobs.items() if work}
                context.view_layer.update()
                for number, records in done.items():
                    problem = ""
                    for (joint_name, obj, _where), _record in zip(jobs[number], records):
                        points = before[obj.name][0]
                        far = max([abs(c) for p in points for c in p] or [0.0])
                        tolerance = 1e-5 * sizes[joint_name] + 1e-6 * far
                        now = signed_volume(obj.data)
                        if not looks_the_same(before[obj.name], look_of(obj), tolerance):
                            problem = "re-framing it would change how it looks"
                        elif (min(abs(now), abs(volumes[joint_name])) > 1e-9 * sizes[joint_name] ** 3
                              and (now > 0.0) != (volumes[joint_name] > 0.0)):
                            problem = "its faces point the other way to the leader's"
                        if problem:
                            gave_up[number] = (obj.name, REFRAME_ADVICE.format(problem))
                            break
                    if number in gave_up:
                        put_back(records)
                    else:
                        framed.extend(records)
            for number in gave_up:
                placed.pop(number, None)
        left = standing.left + [(0.0, object_name, "'{:s}' {:s}".format(short(object_name, 18), why))
                                for object_name, why in gave_up.values()]
        left.sort()
        outs = ""
        if left:
            outs = " Left out: {:s}{:s}.".format(
                "; ".join(words for _distance, _object, words in left[:3]),
                "; and {:d} more".format(len(left) - 3) if len(left) > 3 else "")
        elsewhere = [n for n in standing.occupied if n not in standing.partial]
        empty = standing.empty if self.use == "ADOPT" else []

        taken = names_in_use()
        copies, riders, told = [], [], []
        for number in free:
            whole = {}
            if number in placed:
                for joint_name, (obj, _where) in placed[number].items():
                    riders.append((obj, joint_name))
                    whole[joint_name] = obj.name
            elif (self.use == "ADOPT" or number in standing.occupied or number in gave_up):
                # Something stands here, or this is no place to make copies.
                continue
            else:
                copy_number = free_ring_number([joint for joint, _seat, _source in joints],
                                               taken)
                for joint_name, joint_seat, source in joints:
                    made = "{:s} {:d}".format(joint_name, copy_number)
                    taken.add(made)
                    copy = copy_for_ring(source, made, self.linked)
                    copies.append(copy)
                    riders.append((copy, joint_name))
                    whole[joint_name] = copy.name
                    copy.matrix_world = turns[number] @ joint_seat
            told.append(whole)
        if not riders:
            put_back(framed)
            if standing.partial and len(standing.partial) == len(free):
                said = ("Every place round that ring has only part of a chain of '{:s}' "
                        "standing, so nothing was taken up or made.".format(short(name, 18)))
            elif self.use == "ADOPT":
                said = ("Nothing standing in the places round that ring is an exact copy "
                        "of '{:s}', so nothing was taken up.".format(short(name, 18)))
            else:
                said = ("Every place round that ring already holds something, so nothing was "
                        "taken up or made.")
            if empty:
                said += " {:s} had nothing standing in {:s}: Fill the gaps would copy the part there.".format(
                    counted(len(empty), "place"), "it" if len(empty) == 1 else "them")
            self.refuse(data, said + outs + (" " + notes if notes else ""))
            return {"CANCELLED"}
        context.view_layer.update()
        objects = [obj for obj, _joint in riders]
        # Read before the riders are added: they are not the same afterwards.
        made_whole = len(copies) // len(joints)

        for other in context.selected_objects:
            other.select_set(False)
        for obj in objects:
            obj.select_set(True)
        leading = bpy.data.objects[name]
        leading.select_set(True)
        context.view_layer.objects.active = leading
        try:
            # Told which object is which joint: what is made here is known, and
            # a copy of the last joints of a chain is not to be taken for one
            # of the first.
            done = bpy.ops.rigmoves.ride_along(index=self.index, leader=name,
                                               rig_name=rig.name,
                                               pairing=json.dumps(told))
        except RuntimeError:
            done = {"CANCELLED"}
        data = rig.rigmoves
        move = data.moves[self.index]
        # Every copy has to be a rider of the joint it was copied from. One
        # that is not - an object Ride Along took for already known - stands
        # still, or is put back where an old part stood, and the report would
        # still say it rides along. Taken out again, with nothing left.
        stranded = [obj.name for obj, joint in riders
                    if move.parts.get(obj.name) is None
                    or move.parts[obj.name].leader != joint]
        if done != {"FINISHED"} or stranded:
            take_riders_out(rig, move, [obj.name for obj in objects
                                        if move.parts.find(obj.name) >= 0])
            if move.built:
                bpy.ops.rigmoves.build()
            # Objects that were taken up are put back as they were found.
            put_back(framed)
            discard_copies(copies)
            self.refuse(data, "Not every copy of '{:s}' could be made to ride along, so "
                              "none were kept.".format(short(name, 18)))
            return {"CANCELLED"}
        settle(framed)

        said = self.first_sentence(name, joints, len(placed), made_whole)
        if framed:
            said += (" {:s} re-framed to stand on {:s} place, the mesh moved the "
                     "other way so nothing shifted.".format(
                         counted(len(framed), "object"),
                         "its" if len(framed) == 1 else "their"))
        said += outs
        if standing.partial:
            said += " {:s} had only part of a chain standing and {:s} left alone.".format(
                counted(len(standing.partial), "place"),
                "was" if len(standing.partial) == 1 else "were")
        if elsewhere:
            said += " {:s} had something standing there that is not a copy and {:s} left alone.".format(
                counted(len(elsewhere), "place"), "was" if len(elsewhere) == 1 else "were")
        if gave_up:
            said += " {:s} hold{:s} a copy that could not safely be re-framed and {:s} left alone.".format(
                counted(len(gave_up), "place"), "s" if len(gave_up) == 1 else "",
                "was" if len(gave_up) == 1 else "were")
        if empty:
            said += " {:s} had nothing standing in {:s}: Fill the gaps would copy the part there.".format(
                counted(len(empty), "place"), "it" if len(empty) == 1 else "them")
        if notes:
            said += " " + notes
        if skipped:
            said += " {:s} already held a copy and {:s} skipped.".format(
                counted(skipped, "place"), "was" if skipped == 1 else "were")
        if self.lead_step:
            # Out from the original both ways round: the two sides match. Only
            # for the copies made now: the Leads of riders already there are
            # theirs. A copied finger has the one Lead, its first joint's.
            roots = [move.parts[obj.name] for obj, joint in riders
                     if joint == first_joint]
            ranks = spread_ranks(rig, move, [(move.parts[name], roots)], "LEAD",
                                 "AROUND", "Z", True, 0)
            limited = spread_put("LEAD", roots,
                                 [self.lead_step * ranks[r.name] for r in roots])
            refresh_drivers(rig, data, move)
            said += " Leads step by {:d}, out from it both ways round.".format(
                self.lead_step)
            if limited:
                said += " {:d} held at the limit.".format(limited)
        data.report = said
        self.report({"INFO"}, said)
        return {"FINISHED"}

    def first_sentence(self, name, joints, taken, made):
        """The first sentence of the report: what rides along with the part."""
        if taken:
            which = "{:s} of '{:s}'".format(
                counted(taken, "modelled copy", "modelled copies"), short(name, 18))
            if made:
                which += " and {:s}".format(counted(made, "new one"))
        else:
            which = "{:s} of '{:s}'".format(counted(made, "copy", "copies"), short(name, 18))
        return "{:s}{:s} round {:s} {:s} along with it{:s}{:s}.".format(
            which,
            " ({:s} each)".format(counted(len(joints), "joint")) if len(joints) > 1 else "",
            "the 3D cursor" if self.center == "CURSOR" else "the world origin",
            "rides" if taken + made == 1 else "ride",
            ", joint for joint" if len(joints) > 1 else "",
            " (nothing new made)" if taken and not made else "")


def control_channel(carrier):
    """(owner, data path, index) of what a control's keys go on: the handle's
    place along its rail, or the slider itself when there is no handle."""
    handle, bone = control_of(carrier)
    if handle is not None:
        return handle, "location", 1
    if bone is not None and carrier.prop in bone.keys():
        # Still driven by a handle switched off since the last Build: a key on
        # it would be overruled by the driver and nothing would play.
        animation = carrier.id_data.animation_data
        if animation is not None and animation.drivers.find(
                property_path(carrier.control, carrier.prop)) is not None:
            return None, None, None
        return bone, '["{:s}"]'.format(bpy.utils.escape_identifier(carrier.prop)), -1
    return None, None, None


def action_curve(rig, data_path, index):
    """(holder, F-curve) for one channel of the rig's own animation, or Nones."""
    action = rig.animation_data.action if rig.animation_data else None
    if action is None:
        return None, None
    # Channelbags only, for the reason given in own_transform_curves.
    holders = [bag for layer in action.layers for strip in layer.strips
               for bag in strip.channelbags]
    for holder in holders:
        for curve in holder.fcurves:
            if curve.data_path == data_path and (index < 0 or curve.array_index == index):
                return holder, curve
    return None, None


class RIGMOVES_OT_animate(bpy.types.Operator):
    bl_idname = "rigmoves.animate"
    bl_label = "Animate"
    bl_description = ("Key the control to play the whole of it from the "
                      "current frame, over this many frames. Replaces any keys "
                      "the control had")
    bl_options = {"REGISTER", "UNDO"}
    index: bpy.props.IntProperty()
    combined: bpy.props.BoolProperty(default=False)

    def execute(self, context):
        rig = rig_of(context)
        if not here(context, rig):
            return {"CANCELLED"}
        data = rig.rigmoves
        carriers_ = data.groups if self.combined else data.moves
        if not 0 <= self.index < len(carriers_):
            return {"CANCELLED"}
        carrier = carriers_[self.index]
        owner, path, index = control_channel(carrier)
        if owner is None:
            data.report = "Build first: there is no control to animate yet."
            self.report({"WARNING"}, data.report)
            return {"CANCELLED"}
        # Whatever the control was keyed to do before goes: two keys, start
        # and end, are the whole of the instruction.
        full = owner.path_from_id(path)
        holder, curve = action_curve(rig, full, index)
        if curve is not None:
            holder.fcurves.remove(curve)
        scene = context.scene
        start = scene.frame_current
        end = start + max(1, carrier.play_frames)
        for frame, share in ((start, 0.0), (end, 100.0)):
            carrier.play = share
            owner.keyframe_insert(path, index=index, frame=frame)
        _holder, curve = action_curve(rig, full, index)
        if curve is not None:
            # Even in time: the shape of the move is the move's own Ease and
            # speeds, not a second ease laid on top by the keys.
            for point in curve.keyframe_points:
                point.interpolation = "LINEAR"
            curve.update()
        carrier.play = 0.0
        if end > scene.frame_end:
            scene.frame_end = end
        data.report = "'{:s}' plays over frames {:d} to {:d}.".format(
            carrier.name, start, end)
        self.report({"INFO"}, data.report)
        return {"FINISHED"}


class RIGMOVES_OT_key_control(bpy.types.Operator):
    bl_idname = "rigmoves.key_control"
    bl_label = "Key the Control"
    bl_description = ("Keyframe the control where it stands, on the current "
                      "frame - the same key as pressing I on its handle")
    bl_options = {"REGISTER", "UNDO"}
    index: bpy.props.IntProperty()
    combined: bpy.props.BoolProperty(default=False)

    def execute(self, context):
        rig = rig_of(context)
        if not here(context, rig):
            return {"CANCELLED"}
        data = rig.rigmoves
        carriers = data.groups if self.combined else data.moves
        if not 0 <= self.index < len(carriers):
            return {"CANCELLED"}
        carrier = carriers[self.index]
        handle, bone = control_of(carrier)
        frame = context.scene.frame_current
        if handle is not None:
            handle.keyframe_insert("location", index=1, frame=frame)
        elif bone is not None and carrier.prop in bone.keys():
            bone.keyframe_insert('["{:s}"]'.format(
                bpy.utils.escape_identifier(carrier.prop)), frame=frame)
        else:
            return {"CANCELLED"}
        data.report = "'{:s}' keyed at {:.0f}% on frame {:d}.".format(
            carrier.name, carrier.play, frame)
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
        # Never held up by what it is taking out: whatever is wrong with a part
        # is no reason to keep it.
        catch_up(rig, data)
        gone = []
        for pose_bone, constraint in our_constraints(rig, move):
            pose_bone.constraints.remove(constraint)
        # Objects this move bound get their freedom back: the group, the
        # modifier and the parent all go, and they stay exactly where they are.
        # One never bound only comes off the object it was hung from to follow.
        for part in move.parts:
            if part.kind == "OBJECT" and not part.bone_name:
                unhang(part)
            if part.kind != "OBJECT" or not part.bone_name:
                continue
            if unbind_object(rig, part):
                gone.append(part.bone_name)
        # The handle's driver goes with the slider it writes. Left behind it
        # points at a property that is gone and a handle about to be, and
        # Blender complains about it on every update from then on.
        rig.driver_remove(property_path(move.control, move.prop))
        drop_control_keys(rig, move)
        bone = rig.pose.bones.get(move.control)
        if bone is not None and move.prop in bone.keys():
            del bone[move.prop]
        # Its drawn paths and its curves were made for it and go with it.
        drop_paths(move)
        for part in move.parts:
            obj = part.path_curve
            part.path_curve = None
            if obj is not None:
                curve = obj.data
                bpy.data.objects.remove(obj, do_unlink=True)
                if curve is not None and curve.users == 0:
                    bpy.data.curves.remove(curve)
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
        drop_control_keys(rig, group)
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


def counted(number, one, many=None):
    """A count with its noun in the right number: "1 copy", "5 copies"."""
    return "{:d} {:s}".format(number, one if number == 1 else (many or one + "s"))


def short(name, keep=15):
    """The tail of a long bone name, which is the part that differs.

    Cut from the front, two controllers called '..._top_controller' and
    '..._top_controller.001' read as the same row.
    """
    return name if len(name) <= keep else "…" + name[-(keep - 1):]


def fitted(context, name, share, tail=""):
    """A name as it fits beside a row's controls, cut from the front only as
    far as it has to be, with the tail after it kept whole.

    The end is what is kept because it is where copies differ: Ring numbers
    them "Petal 2", "Petal 3", and Shift+D adds ".001", ".002". A fixed count
    of letters cannot know the room there is - it depends on how wide the
    sidebar has been dragged and on the UI scale - and a label that does not
    fit is cut off by Blender at its END, which is the number: seven copies
    then read as seven identical rows. So the room is worked out, and the
    name measured against it in the panel's own font.

    `share` is how much of the row the label has (the factor of its split),
    `tail` something that must show whole, such as a copied finger's " +2".
    """
    region = getattr(context, "region", None)
    if region is None or region.width <= 1:
        # A script, or a run with no window: there is no room to measure.
        return short(name, 13 if not tail else 10) + tail
    import blf
    scale = context.preferences.system.ui_scale
    # Measured in a real window: the panel's rows are the region less about
    # 53 px, and a label loses about 32 px of its share to its icon and its
    # padding.
    room = share * (region.width - 53.0 * scale) - 32.0 * scale
    blf.size(0, context.preferences.ui_styles[0].widget.points * scale)

    def width(text):
        return blf.dimensions(0, text)[0]

    if width(name + tail) <= room:
        return name + tail
    for keep in range(len(name) - 1, 0, -1):
        cut = "…" + name[-keep:] + tail
        if width(cut) <= room:
            return cut
    # Not even one letter fits: the last is still the one that tells it from
    # the row above.
    return "…" + name[-1:] + tail


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
    bl_label = "CopyThat"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "CopyThat"

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
        ours = len(stray_curves(rig, data, auto))
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
        # Selected with a part that already moves, the newcomers are most
        # likely meant to do what it does - a petal beside the one that was
        # recorded - so riding along is offered first.
        for number, (index, move, part) in enumerate(leaders(context, rig)[:2]):
            run = box.row()
            run.scale_y = 1.3
            riding = run.operator(
                RIGMOVES_OT_ride_along.bl_idname,
                text="Ride Along With '{:s}'".format(short(part.name, 14)),
                icon="LINKED")
            riding.index, riding.leader, riding.rig_name = index, part.name, rig.name
            if not number:
                note = box.row()
                note.enabled = False
                note.label(text="each copies its move from where it stands"
                           if len(chain_of(move, part)) < 2 else
                           "copies of the whole chain ride joint for joint")

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
        self._draw_pivot(body, context, move, index)

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
            self._draw_speed(body, step, "speed")
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
        if len(move.steps):
            self._draw_speed(body, move, "speed_after")

        row = body.split(factor=0.4, align=True)
        row.scale_y = 1.15
        row.label(text="After", icon="CHECKMARK" if after else "DOT")
        row = row.row(align=True)
        press = row.operator(RIGMOVES_OT_record.bl_idname, text="Record")
        press.index, press.which = index, "AFTER"
        # Offered on a path with an After to show, too, recorded or not: parts
        # added to a built move are put where they should end up from there.
        if after or keyed_at(move, last_frame(move)):
            look = row.operator(RIGMOVES_OT_show.bl_idname, text="", icon="HIDE_OFF")
            look.index, look.which = index, "AFTER"

        if not len(move.steps) and before and after and not objects:
            said = body.row()
            said.enabled = False
            said.label(text="+ adds a pose in between, for a path that bends")
        body.prop(move, "ease", text="")
        self._draw_path(body, context, move, index)
        self._draw_ring(body, context, move, index)

        # Riders have no delay of their own: each is placed against its
        # leader instead, ahead or behind, and travels at the leader's speed.
        # A copied finger is one row, its first joint's: the joints riding on
        # it play by its Lead and Mirror, and go when it goes.
        riders = sorted([(i, p) for i, p in riders_of(move)
                         if copy_root(move, p).name == p.name],
                        key=lambda row: row[1].leader)
        if riders:
            head, listed = layout.panel_prop(move, "show_riders")
            head.label(text="Riding along ({:d})".format(len(riders)), icon="LINKED")
            # The button in a row of its own, aligned right, so that it takes
            # only its own width: set straight in the header it shares it with
            # the label half and half, and at the sidebar's usual width the
            # count was the first thing cut off.
            side = head.row()
            side.alignment = "RIGHT"
            spreading = side.operator(RIGMOVES_OT_spread.bl_idname, text="Spread…")
            spreading.index, spreading.what = index, "LEAD"
            if listed is not None:
                note = listed.row()
                note.enabled = False
                note.label(text="lead: below 0 behind, above 0 ahead")
                shown = None
                for position, part in riders:
                    if part.leader != shown:
                        shown = part.leader
                        said = listed.row()
                        said.enabled = False
                        said.label(text="with '{:s}'".format(short(part.leader, 22)))
                    joints = len(copy_of(move, part)) - 1
                    # The copies of a petal are named alike but for the number
                    # at the end, so that is what the name is cut to keep.
                    share = 0.42
                    line = listed.split(factor=share, align=True)
                    line.label(text=fitted(context, part.name, share,
                                           " +{:d}".format(joints) if joints else ""),
                               icon="OBJECT_DATA")
                    right = line.row(align=True)
                    right.prop(part, "lead", text="Lead", slider=True)
                    # One button that steps through the choices: a mirror
                    # moves the rider's bone, so each one is a Build.
                    labels = [label for _key, label, _description in MIRRORS]
                    keys = [key for key, _label, _description in MIRRORS]
                    step = right.operator(RIGMOVES_OT_set_mirror.bl_idname,
                                          text=labels[keys.index(part.mirror)],
                                          icon="MOD_MIRROR",
                                          depress=part.mirror != "NONE")
                    step.index, step.part = index, position
                    step.axis = keys[(keys.index(part.mirror) + 1) % len(keys)]
                    drop = right.operator(RIGMOVES_OT_drop_rider.bl_idname, text="",
                                          icon="X", emboss=False)
                    drop.index, drop.part = index, position

        # Which part hangs from which: a dropdown beside every part, listing
        # the move's parts to follow.
        chain = [p for p in move.parts if p.kind == "OBJECT" and not p.leader]
        if len(chain) >= 2:
            head, listed = layout.panel_prop(move, "show_chain")
            head.label(text="Follows", icon="CONSTRAINT_BONE")
            if listed is not None:
                note = listed.row()
                note.enabled = False
                note.label(text="moves with the part it follows")
                # Two tools for the whole chain at once: the dropdowns set
                # down a line, and the first joint's bend repeated down it.
                tools = listed.row(align=True)
                tools.operator(RIGMOVES_OT_make_chain.bl_idname, text="Make Chain",
                               icon="LINKED").index = index
                tools.operator(RIGMOVES_OT_curl.bl_idname, text="Curl",
                               icon="MOD_SIMPLEDEFORM").index = index
                for part in chain:
                    line = listed.split(factor=0.42, align=True)
                    line.label(text=short(part.name, 13), icon="OBJECT_DATA")
                    line.prop_search(part, "follows", move, "parts", text="",
                                     icon="LINKED")
                if move.built and parent_pending(rig, rig.rigmoves, move):
                    waiting = listed.row()
                    waiting.alert = True
                    waiting.label(text="Build to put it into effect", icon="INFO")

        # Who moves when. The reason a machine reads as built rather than
        # animated: the parts do not all leave at once.
        head, timing = layout.panel_prop(move, "show_timing")
        head.label(text="Timing", icon="TIME")
        # In a row of its own, as in the header of Riding along.
        side = head.row()
        side.alignment = "RIGHT"
        spreading = side.operator(RIGMOVES_OT_spread.bl_idname, text="Spread…")
        spreading.index, spreading.what = index, "DELAY"
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
                if part.leader:
                    continue
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

        self._draw_play(body, move, index, False)

    def _draw_play(self, body, carrier, index, combined):
        """What the animator actually reaches for: one slider that plays the
        whole thing, from the first part to set off to the last to arrive.

        The same control as the handle in the viewport, read and written in
        the same place, so dragging either moves both. A key button beside
        it, since the slider itself is not something Blender can key.
        """
        handle, bone = control_of(carrier)
        if not carrier.built or (handle is None and (
                bone is None or carrier.prop not in bone.keys())):
            return
        row = body.row(align=True)
        row.scale_y = 1.4
        row.prop(carrier, "play", text=carrier.name, slider=True)
        key = row.operator(RIGMOVES_OT_key_control.bl_idname, text="",
                           icon="DECORATE_KEYFRAME")
        key.index, key.combined = index, combined
        # Keys the whole of it from the current frame, so nobody has to key
        # the start and the end by hand to get it playing.
        row = body.row(align=True)
        row.prop(carrier, "play_frames", text="Frames")
        run = row.operator(RIGMOVES_OT_animate.bl_idname, text="Animate",
                           icon="PLAY")
        run.index, run.combined = index, combined

    def _draw_pivot(self, body, context, move, index):
        """Where the selected parts turn about: three buttons, the one in
        use pressed in."""
        if not any(p.kind == "OBJECT" and not p.leader for p in move.parts):
            return
        chosen = chosen_parts(context, move)
        row = body.split(factor=0.4, align=True)
        row.label(text="Pivot", icon="PIVOT_CURSOR")
        buttons = row.row(align=True)
        buttons.enabled = bool(chosen)
        current = chosen[0].pivot_kind if chosen else ""
        for kind, label, _description in PIVOTS:
            press = buttons.operator(RIGMOVES_OT_set_pivot.bl_idname,
                                     text="Cursor" if kind == "CURSOR" else label,
                                     depress=kind == current)
            press.index, press.kind = index, kind
        if not chosen:
            said = body.row()
            said.enabled = False
            said.label(text="select a part to set where it turns")

    def _draw_ring(self, body, context, move, index):
        """One button for making a ring of copies of the selected part, which
        ride along with it. Dimmed until the active object is a part that can
        lead them."""
        if not any(p.kind == "OBJECT" and not p.leader for p in move.parts):
            return
        active = context.view_layer.objects.active
        part = move.parts.get(active.name) if active is not None else None
        row = body.row(align=True)
        row.enabled = bool(part is not None and part.kind == "OBJECT" and not part.leader)
        row.operator(RIGMOVES_OT_ring.bl_idname, text="Ring…",
                     icon="MESH_CIRCLE").index = index

    def _draw_path(self, body, context, move, index):
        """Curving the path, and the line that shows where it goes."""
        row = body.row(align=True)
        if any(p.kind == "OBJECT" and not p.leader for p in move.parts):
            run = row.operator(RIGMOVES_OT_curve_path.bl_idname,
                               text="Curve the Path", icon="CURVE_BEZCURVE")
            run.index = index
        if move.built and any(p.kind == "OBJECT" for p in move.parts):
            shown = row.operator(RIGMOVES_OT_show_paths.bl_idname,
                                 text="Paths", icon="IPO_LINEAR",
                                 depress=move.show_paths)
            shown.index, shown.show = index, not move.show_paths
        curved = [(i, p) for i, p in enumerate(move.parts) if curve_alive(p.path_curve)]
        for position, part in curved:
            line = body.split(factor=0.55, align=True)
            line.label(text=short(part.name, 16), icon="CURVE_BEZCURVE")
            right = line.row(align=True)
            edit = right.operator(RIGMOVES_OT_edit_curve.bl_idname, text="Edit",
                                  icon="EDITMODE_HLT")
            edit.index, edit.part = index, position
            drop = right.operator(RIGMOVES_OT_drop_curve.bl_idname, text="",
                                  icon="X", emboss=False)
            drop.index, drop.part = index, position
        if curved:
            said = body.row()
            said.enabled = False
            said.label(text="bend it in edit mode, then Build")

    def _draw_speed(self, body, holder, prop):
        """The speed of one stretch, drawn between the two poses it joins.

        Only once there is a step: with Before and After alone the move is a
        single stretch, and it always fills the whole control whatever its
        speed, so a slider there would do nothing.
        """
        row = body.split(factor=0.4, align=True)
        note = row.row(align=True)
        note.enabled = False
        note.label(text="", icon="BLANK1")
        note.label(text=speed_note(getattr(holder, prop)))
        row.prop(holder, prop, text="Speed", slider=True)

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

        self._draw_play(body, group, index, True)

    def _draw_report(self, layout, data):
        if not data.report:
            return
        note = layout.box().column(align=True)
        note.enabled = False
        # Room for the names of what a ring left out.
        for line in wrapped(data.report, most=9):
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
    RIGMOVES_OT_ride_along,
    RIGMOVES_OT_set_mirror,
    RIGMOVES_OT_drop_rider,
    RIGMOVES_OT_pick_part,
    RIGMOVES_OT_free_keys,
    RIGMOVES_OT_use_selected,
    RIGMOVES_OT_record,
    RIGMOVES_OT_show,
    RIGMOVES_OT_add_step,
    RIGMOVES_OT_drop_step,
    RIGMOVES_OT_build,
    RIGMOVES_OT_set_pivot,
    RIGMOVES_OT_curve_path,
    RIGMOVES_OT_edit_curve,
    RIGMOVES_OT_drop_curve,
    RIGMOVES_OT_show_paths,
    RIGMOVES_OT_spread,
    RIGMOVES_OT_make_chain,
    RIGMOVES_OT_curl,
    RIGMOVES_OT_ring,
    RIGMOVES_OT_animate,
    RIGMOVES_OT_key_control,
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
