"""CopyThat promo - plays the demo scenes by itself, live, in Blender.

HOW TO USE (the full steps are in HOW_TO_RECORD.md):

  1. Turn on the CopyThat add-on (0.15.0), in Blender 4.4 or later.
  2. Open this file in the Scripting tab's text editor and press Run Script.
  3. Start your screen recorder first, then run the script. A 5 second
     countdown shows in the 3D viewport; keep your hands off the mouse and
     keyboard from then on.
  4. Four demo scenes play one after another, each in a new scene of its own.
     Do this in a fresh file (File > New > General) and do not save it: the
     script changes the 3D view for the recording, and puts it back at the end.

Change the settings just below if you want fewer scenes, no captions, and so
on. To stop early, set STOP = True and run the script again.
"""

import math
import time
import traceback
from contextlib import contextmanager

import bmesh
import bpy
from bpy.app.handlers import persistent
from mathutils import Euler, Matrix, Quaternion, Vector

# ===========================================================================
# Things you may change
# ===========================================================================

SCENES = [1, 2, 3, 4]          # 1 one cube, 2 ride along, 3 curved path, 4 flower
CAPTIONS = True                # the chip and the step line drawn in the viewport
COUNTDOWN = 5                  # seconds to start your recorder
PAUSE_BETWEEN = 1.5            # seconds between one scene and the next
SPEED = 1.0                    # 1.0 as designed; 1.25 is a quarter faster
FULL_VIEWPORT = False          # True: the 3D view fills the whole window all through
MAXIMISE_FOR_BLOOM = True      # scene 4: the 3D view fills the window for the bloom
CAPTION_SCALE = 1.0            # captions follow the window's height; trim them here
RESTORE_VIEW_AT_END = True     # put the viewport's look back when it is done
RETURN_TO_START_SCENE = True   # go back to the scene and tab you started in
STOP = False                   # True: only stop a run that is still going

# ===========================================================================
# Fixed choices
# ===========================================================================

STATE_KEY = "copythat_promo_show"     # where a run is kept, so a rerun can end it
MARK = "copythat_promo"               # tag on scenes this script made
RETIRED = "copythat_promo_old"        # tag on the ones a later run renamed
TICK = 1.0 / 60.0                     # timer step: tweens run at about 60 Hz
FLOWER_FRAMES = 150                   # frames the flower's bloom is keyed over

ORANGE = "#E8833A"       # the cube
TEAL = "#2FB5A6"         # the rider, and the one accent colour of the captions
WALL = "#8591A5"         # cool grey
STRAIGHT = "#FF5C5C"     # the straight path through the wall

# ===========================================================================
# Flower code
#
# bundle.py replaces the line between the markers with the source of
# PROMO/flower/flower.py. Without it, scene 4 is left out.
# ===========================================================================

# >>> FLOWER BEGIN (bundle.py fills this in)
FLOWER_SOURCE = None
# <<< FLOWER END

FLOWER = None   # the flower module, once FLOWER_SOURCE has been compiled


def attach_flower(source, name="copythat_flower"):
    """Compile the flower's source into a module of its own.

    A module, not pasted into this file's namespace, so that nothing in it can
    shadow a name used here. Its lines are kept for tracebacks.
    """
    global FLOWER
    import linecache
    import types
    module = types.ModuleType(name)
    module.__file__ = name + ".py"
    linecache.cache[name] = (len(source), None, source.splitlines(True), name)
    exec(compile(source, name, "exec", dont_inherit=True), module.__dict__)
    for needed in ("build_flower", "flower_steps"):
        if not callable(getattr(module, needed, None)):
            raise ImportError("the flower code has no " + needed)
    FLOWER = module
    return module


if FLOWER_SOURCE:
    try:
        attach_flower(FLOWER_SOURCE)
    except Exception:
        traceback.print_exc()
        print("CopyThat promo: the flower code would not load, scene 4 is left out.")
        FLOWER = None


# ===========================================================================
# Small helpers
# ===========================================================================

def clamp01(x):
    return 0.0 if x < 0.0 else 1.0 if x > 1.0 else x


def smooth(u):
    """Smoothstep: starts and stops gently."""
    u = clamp01(u)
    return u * u * (3.0 - 2.0 * u)


def hex_rgb(code):
    code = code.lstrip("#")
    return tuple(int(code[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def to_linear(value):
    return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4


def linear(code, alpha=1.0):
    """A colour for a Blender property: those are stored linear, not as the
    sRGB hex a person reads."""
    r, g, b = hex_rgb(code)
    return (to_linear(r), to_linear(g), to_linear(b), alpha)


def lighter(code, amount):
    r, g, b = hex_rgb(code)
    return "#{:02X}{:02X}{:02X}".format(
        *(int(round(255 * (c + (1.0 - c) * amount))) for c in (r, g, b)))


def pose(location, degrees=(0.0, 0.0, 0.0)):
    """A matrix: where something stands and how it is turned (X, then Y, then Z)."""
    turn = Euler([math.radians(a) for a in degrees], "XYZ").to_matrix().to_4x4()
    return Matrix.Translation(Vector(location)) @ turn


def box_points(centre, half):
    """The eight corners of a box: what a view has to keep in frame."""
    centre = Vector(centre)
    return [centre + Vector((sx * half[0], sy * half[1], sz * half[2]))
            for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]


def short_error(exc):
    text = "{:s}: {:s}".format(type(exc).__name__, str(exc)) if str(exc) else type(exc).__name__
    return text if len(text) < 140 else text[:137] + "..."


# ===========================================================================
# Scene building: geometry, materials, the new scene itself
# ===========================================================================

def material(name, code):
    """A viewport colour as a material. Reused by name, so a rerun adds none."""
    found = bpy.data.materials.get(name)
    if found is None:
        found = bpy.data.materials.new(name)
        found.diffuse_color = linear(code)
        found.roughness = 0.55
    return found


def make_box(scene, name, size, location, code, degrees=(0.0, 0.0, 0.0),
             bevel=0.06, marked=True, selectable=True):
    """A rounded box in the scene.

    Its size is in the mesh, not in the object's scale, so a rider turned from
    its leader does not inherit a squash. When `marked`, a lighter stripe runs
    along X over the top: a plain cube turned a quarter looks the same, so
    this is what shows that it turned. (A square panel would not.)
    """
    maker = bmesh.new()
    bmesh.ops.create_cube(maker, size=1.0)
    bmesh.ops.scale(maker, vec=size, verts=maker.verts)
    if bevel:
        bmesh.ops.bevel(maker, geom=list(maker.edges), offset=bevel, segments=2,
                        profile=0.5, affect="EDGES")
    if marked:
        half = size[1] / 6.0
        for y in (-half, half):
            bmesh.ops.bisect_plane(maker, geom=maker.verts[:] + maker.edges[:] + maker.faces[:],
                                   plane_co=(0.0, y, 0.0), plane_no=(0.0, 1.0, 0.0))
        maker.normal_update()
        for face in maker.faces:
            if face.normal.z > 0.99 and abs(face.calc_center_median().y) < half:
                face.material_index = 1
    mesh = bpy.data.meshes.new(name)
    maker.to_mesh(mesh)
    maker.free()
    mesh.materials.append(material("CopyThat Promo " + code, code))
    mesh.materials.append(material("CopyThat Promo " + code + " light", lighter(code, 0.45)))
    obj = bpy.data.objects.new(name, mesh)
    obj.color = linear(code)
    obj.location = location
    obj.rotation_euler = [math.radians(a) for a in degrees]
    obj[MARK] = True
    scene.collection.objects.link(obj)
    # Valid at once: Blender works the world matrix out when it next
    # evaluates the scene, and a pose planned from it now would be the identity.
    obj.matrix_world = obj.matrix_basis.copy()
    if not selectable:
        obj.hide_select = True
    return obj


def make_scene(number, title):
    scene = bpy.data.scenes.new("CopyThat Promo {:d} - {:s}".format(number, title))
    scene[MARK] = number
    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1080
    scene.render.resolution_percentage = 100
    scene.render.fps = 30
    return scene


def retire_old_runs():
    """Rename what an earlier run of this script left behind.

    Names are unique across a file, so a second take would otherwise show
    "Leader.001" and "CopyThat Rig.001" on its panel. Only scenes carrying
    this script's tag are touched, each once, and nothing is deleted.
    """
    for scene in list(bpy.data.scenes):
        if scene.get(MARK) is None or scene.get(RETIRED) is not None:
            continue
        for item in (list(scene.collection.all_objects)
                     + list(scene.collection.children_recursive) + [scene]):
            item.name = item.name + " (old)"
        scene[RETIRED] = True


def earlier_runs_exist():
    return any(s.get(MARK) is not None for s in bpy.data.scenes)


# ---------------------------------------------------------------------------
# talking to CopyThat

def pick(scene, objects, active=None):
    """Select exactly these objects; `active` (or the first) is the active one."""
    layer = scene.view_layers[0]
    for obj in layer.objects:
        obj.select_set(False, view_layer=layer)
    for obj in objects:
        obj.select_set(True, view_layer=layer)
    if objects or active is not None:
        layer.objects.active = active if active is not None else objects[0]


def rig_data(scene):
    rig = scene.rigmoves_rig
    if rig is None:
        raise RuntimeError("CopyThat has not made a rig in this scene yet")
    return rig.rigmoves


def the_move(scene, index=0):
    return rig_data(scene).moves[index]


def need(result, what, scene=None):
    """Raise, with CopyThat's own words, if an operator did not go through."""
    if result != {"FINISHED"}:
        said = ""
        try:
            said = rig_data(scene or bpy.context.scene).report
        except Exception:
            pass
        raise RuntimeError("{:s} did not work. {:s}".format(what, said).strip())


def check_built(scene):
    """Build reports "N part(s) on M slider(s)" when it worked, and anything
    else when it did not; every move has to be built as well."""
    data = rig_data(scene)
    said = data.report
    words = said.split(" ")
    ok = (len(words) > 3 and words[0].isdigit() and words[1] == "part(s)" and words[2] == "on"
          and len(data.moves) > 0 and all(m.built for m in data.moves)
          and "cut short" not in said and "not recorded" not in said)
    if not ok:
        raise RuntimeError("Build Sliders reported: " + (said or "nothing"))
    return said


def scroll_panel(up=True):
    """Scroll the sidebar to its top (or bottom), where the section that
    matters is. A best effort: it is the same scroll the mouse wheel does, and
    nothing here depends on it having worked."""
    window, area = bpy.context.window, bpy.context.area
    if window is None or area is None:
        return False
    ui = next((r for r in area.regions if r.type == "UI"), None)
    if ui is None or ui.width <= 1:
        return False
    try:
        with bpy.context.temp_override(window=window, area=area, region=ui):
            (bpy.ops.view2d.scroll_up if up else bpy.ops.view2d.scroll_down)(deltay=5000)
        return True
    except Exception:
        return False


def op_panel_top():
    return ("call", scroll_panel)


def op_select(scene, objects, active=None):
    """Select them, as a click would: the panel then offers New Move."""
    def run():
        pick(scene, objects, active)
    return ("call", run)


def op_new_move(scene):
    def run():
        need(bpy.ops.rigmoves.new_move(), "New Move", scene)
    return ("call", run)


def op_record(scene, which, index=0):
    def run():
        need(bpy.ops.rigmoves.record(index=index, which=which), "Record " + which.title(), scene)
    return ("call", run)


def op_build(scene, dress=False):
    def run():
        need(bpy.ops.rigmoves.build(), "Build Sliders", scene)
        check_built(scene)
        if dress:
            dress_paths(scene)
    return ("call", run)


def tube(obj, radius, code):
    """Give a line of CopyThat's a thickness and a colour. A one pixel black
    line is lost on a recording; a tube of a few pixels is not."""
    curve = obj.data
    curve.bevel_depth = radius
    curve.bevel_resolution = 2
    if not len(curve.materials):
        curve.materials.append(material("CopyThat Promo " + code, code))
    obj.color = linear(code)


def dress_paths(scene, index=0):
    """The path lines, thick enough to see: the straight line red, a curve the
    part follows in the accent colour, a little thicker so it shows over it.
    Build draws the lines again, so this is done after every Build."""
    move = the_move(scene, index)
    if move.paths_object is not None:
        tube(move.paths_object, 0.03, STRAIGHT)
    for part in move.parts:
        if part.path_curve is not None:
            tube(part.path_curve, 0.045, TEAL)


def play_setter(scene, index=0):
    """A setter for the Play slider (0 to 100), read fresh on every tick."""
    def put(value):
        the_move(scene, index).play = value
    return put


def lead_setter(scene, rider, index=0):
    def put(value):
        the_move(scene, index).parts[rider.name].lead = int(round(value))
    return put


def open_sections(scene, riders=None, timing=None, chain=None, index=0):
    """Open or close the panel sections of a move: Riding along, Timing, Follows."""
    move = the_move(scene, index)
    if riders is not None:
        move.show_riders = riders
    if timing is not None:
        move.show_timing = timing
    if chain is not None:
        move.show_chain = chain


def glide_setter(obj, start, end, arc=0.0):
    """A setter that carries an object from one pose to another, with a hop of
    this height on the way. At 1 it is exactly on `end`."""
    a_loc, a_rot, a_size = start.decompose()
    b_loc, b_rot, b_size = end.decompose()

    def put(e):
        if e >= 1.0:
            obj.matrix_world = end
            return
        where = a_loc.lerp(b_loc, e)
        where.z += arc * math.sin(math.pi * e)
        obj.matrix_world = Matrix.LocRotScale(where, a_rot.slerp(b_rot, e),
                                              a_size.lerp(b_size, e))
    return put


# ---------------------------------------------------------------------------
# the scenes: each is a builder (makes the objects), a step generator (the
# contract in SPEC.md: it yields caption / wait / tween / tween_value / call /
# view actions) and a view

def build_1(scene):
    start = pose((0.0, 0.0, 0.65))
    cube = make_box(scene, "Cube", (1.3, 1.3, 1.3), start.translation, ORANGE)
    end = pose((1.5, -0.4, 2.1), (25.0, 0.0, 120.0))
    return {"scene": scene, "cube": cube, "start": start, "end": end}


def view_1(parts):
    points = box_points(parts["start"].translation, (0.85, 0.85, 0.85)) + \
        box_points(parts["end"].translation, (0.95, 0.95, 0.95))
    return {"frame": points, "azimuth": -32.0, "elevation": 22.0}


def steps_1(parts):
    scene, cube = parts["scene"], parts["cube"]
    yield ("wait", 0.6)
    yield ("caption", None, "New Move — where it stands is Before")
    yield op_select(scene, [cube])
    yield ("wait", 1.6)
    yield op_new_move(scene)
    yield ("wait", 2.8)
    yield ("caption", None, "Move it by hand — any way you like")
    yield ("tween", [(cube, parts["end"])], 2.2)
    yield ("wait", 1.5)
    yield ("caption", None, "Record After — where it ends up")
    yield op_record(scene, "AFTER")
    yield ("wait", 2.9)
    yield ("caption", None, "Build Sliders — one slider plays it")
    yield op_build(scene)
    yield op_panel_top()
    yield ("wait", 2.9)
    yield ("caption", None, "Play — one slider, the whole move")
    yield ("tween_value", play_setter(scene), 0.0, 100.0, 2.4)
    yield ("wait", 0.5)
    yield ("tween_value", play_setter(scene), 100.0, 0.0, 2.0)
    yield ("wait", 1.5)


def build_2(scene):
    leader = make_box(scene, "Leader", (1.0, 1.0, 1.0), (-2.0, -0.8, 0.5), ORANGE)
    rider = make_box(scene, "Rider", (1.0, 1.0, 1.0), (2.0, -2.4, 0.5), TEAL,
                     degrees=(0.0, 0.0, 90.0))
    start = leader.matrix_world.copy()
    # In its own frame the leader goes 2.8 ahead, 1.3 up, and turns 120. The
    # rider, turned a quarter, so goes 2.8 sideways of that, 1.3 up.
    end = start @ pose((2.8, 0.0, 1.3), (0.0, 0.0, 120.0))
    return {"scene": scene, "leader": leader, "rider": rider, "start": start, "end": end}


def view_2(parts):
    half = (0.8, 0.8, 0.8)
    points = (box_points(parts["start"].translation, half) + box_points(parts["end"].translation, half)
              + box_points(parts["rider"].matrix_world.translation, half)
              + box_points(parts["rider"].matrix_world.translation + Vector((0.0, 2.8, 1.3)), half))
    return {"frame": points, "azimuth": -30.0, "elevation": 25.0}


def steps_2(parts):
    scene, leader, rider = parts["scene"], parts["leader"], parts["rider"]

    def ride_along():
        need(bpy.ops.rigmoves.ride_along(index=0, leader=leader.name,
                                         rig_name=scene.rigmoves_rig.name),
             "Ride Along", scene)
        open_sections(scene, riders=True, timing=False)

    yield ("wait", 0.5)
    yield ("caption", None, "New Move — where it stands is Before")
    yield op_select(scene, [leader])
    yield ("wait", 1.6)
    yield op_new_move(scene)
    yield ("wait", 2.6)
    yield ("caption", None, "Hop and turn it by hand")
    yield ("tween_value", glide_setter(leader, parts["start"], parts["end"], arc=1.0),
           0.0, 1.0, 2.2)
    yield ("wait", 1.5)
    yield ("caption", None, "Record After")
    yield op_record(scene, "AFTER")
    yield ("wait", 2.9)
    yield ("caption", None, "Ride Along — copies the move from its own place")
    # The second cube first, then the leader last so it is the active one:
    # the panel then offers "Ride Along With 'Leader'", and that is the press.
    yield op_select(scene, [rider, leader], active=leader)
    yield ("wait", 2.6)
    yield ("call", ride_along)
    yield op_panel_top()
    yield ("wait", 2.4)
    yield ("caption", None, "Lead +30 — goes first")
    yield ("tween_value", lead_setter(scene, rider), 0.0, 30.0, 1.4)
    yield ("wait", 2.0)
    yield ("caption", None, "Build Sliders — one slider plays both")
    yield op_build(scene)
    yield op_panel_top()
    yield ("wait", 2.9)
    yield ("caption", None, "Play")
    yield ("tween_value", play_setter(scene), 0.0, 100.0, 2.8)
    yield ("wait", 0.4)
    yield ("tween_value", play_setter(scene), 100.0, 0.0, 1.8)
    yield ("wait", 1.5)


WALL_TOP = 2.0       # how tall the wall stands in scene 3
LIFT_TO = 3.1        # how high the cube's path is lifted over it


def build_3(scene):
    wall = make_box(scene, "Wall", (0.5, 3.0, WALL_TOP), (0.0, 0.0, WALL_TOP / 2.0), WALL,
                    marked=False)
    cube = make_box(scene, "Box", (1.1, 1.1, 1.1), (-3.0, 0.0, 0.55), ORANGE)
    start = cube.matrix_world.copy()
    end = pose((3.0, 0.0, 0.55), (0.0, 90.0, 0.0))
    return {"scene": scene, "cube": cube, "wall": wall, "start": start, "end": end}


def view_3(parts):
    half = (0.85, 0.85, 0.85)
    points = (box_points(parts["start"].translation, half)
              + box_points(parts["end"].translation, half)
              + box_points((0.0, 0.0, LIFT_TO), half)
              + box_points((0.0, 0.0, WALL_TOP / 2.0), (0.3, 1.6, WALL_TOP / 2.0)))
    return {"frame": points, "azimuth": -24.0, "elevation": 22.0}


def lift_setter(scene, cube):
    """Drag the middle point of the cube's curve straight up, handles and all,
    as grabbing it in edit mode and pulling would."""
    state = {}

    def put(e):
        curve = the_move(scene).parts[cube.name].path_curve
        spline = curve.data.splines[0]
        if "base" not in state:
            state["base"] = [[Vector(v) for v in row] for row in curve_rows(spline)]
        shift = Vector((0.0, 0.0, (LIFT_TO - state["base"][0][1].z) * e))
        points, left, right = [[Vector(v) for v in row] for row in state["base"]]
        for row in (points, left, right):
            row[1] = row[1] + shift
        write_curve_rows(spline, points, left, right)
    return put


def curve_rows(spline):
    """(points, left handles, right handles) of a Bezier spline."""
    rows = []
    for name in ("co", "handle_left", "handle_right"):
        flat = [0.0] * (3 * len(spline.bezier_points))
        spline.bezier_points.foreach_get(name, flat)
        rows.append([Vector(flat[i:i + 3]) for i in range(0, len(flat), 3)])
    return rows


def write_curve_rows(spline, points, left, right):
    """All at once: Blender swings an aligned handle off to one side when its
    point is set on its own."""
    for name, rows in (("co", points), ("handle_left", left), ("handle_right", right)):
        spline.bezier_points.foreach_set(name, [x for v in rows for x in v[:3]])
    spline.id_data.update_tag()


def steps_3(parts):
    scene, cube = parts["scene"], parts["cube"]

    def paths_on():
        need(bpy.ops.rigmoves.show_paths(index=0, show=True), "Paths", scene)
        dress_paths(scene)

    def curve_it():
        pick(scene, [cube])
        need(bpy.ops.rigmoves.curve_path(index=0), "Curve the Path", scene)
        dress_paths(scene)

    def edit_it():
        need(bpy.ops.rigmoves.edit_curve(index=0, part=0), "Edit", scene)
        spline = the_move(scene).parts[cube.name].path_curve.data.splines[0]
        # The middle point is the one to take hold of: selected, the rest not.
        for number, point in enumerate(spline.bezier_points):
            chosen = number == 1
            point.select_control_point = chosen
            point.select_left_handle = chosen
            point.select_right_handle = chosen

    def leave_edit():
        bpy.ops.object.mode_set(mode="OBJECT")
        pick(scene, [cube])

    yield ("wait", 0.5)
    yield ("caption", None, "New Move — A is Before")
    yield op_select(scene, [cube])
    yield ("wait", 1.6)
    yield op_new_move(scene)
    yield ("wait", 2.4)
    yield ("caption", None, "Move it to B")
    yield ("tween", [(cube, parts["end"])], 1.4)
    yield ("wait", 1.4)
    yield ("caption", None, "Record After — B is After")
    yield op_record(scene, "AFTER")
    yield ("wait", 2.7)
    yield ("caption", None, "Build Sliders")
    yield op_build(scene)
    yield op_panel_top()
    yield ("wait", 2.5)
    yield ("caption", None, "Paths — the way it goes")
    yield ("call", paths_on)
    yield ("wait", 2.7)
    yield ("caption", None, "Straight through the wall")
    yield ("tween_value", play_setter(scene), 0.0, 58.0, 1.1)
    yield ("wait", 0.3)
    yield ("tween_value", play_setter(scene), 58.0, 0.0, 0.7)
    yield ("wait", 1.4)
    yield ("caption", None, "Curve the Path — ends stay on A and B")
    yield ("call", curve_it)
    yield ("wait", 3.7)
    yield ("caption", None, "Edit mode — lift the middle over the wall")
    yield ("call", edit_it)
    yield ("wait", 1.0)
    yield ("tween_value", lift_setter(scene, cube), 0.0, 1.0, 1.4)
    yield ("wait", 1.2)
    yield ("call", leave_edit)
    yield ("caption", None, "Build Sliders")
    yield op_build(scene, dress=True)
    yield op_panel_top()
    yield ("wait", 2.5)
    yield ("caption", None, "Play — it arcs over")
    yield ("tween_value", play_setter(scene), 0.0, 100.0, 2.4)
    yield ("wait", 0.3)
    yield ("tween_value", play_setter(scene), 100.0, 0.0, 1.6)
    yield ("wait", 1.5)


# --- scene 4: the flower, from the flower module -----------------------------

def build_4(scene):
    return FLOWER.build_flower(scene)


def view_4(parts):
    """A 3/4 view of the bud, wide enough for the open flower, a little round
    from where the promo camera stands, so the glide into it swings."""
    points = []
    for obj in parts.get("all", ()):
        if obj.type == "MESH":
            points.extend(obj.matrix_world @ Vector(c) for c in obj.bound_box)
    if not points:
        return None
    low = Vector((min(p.x for p in points), min(p.y for p in points), min(p.z for p in points)))
    high = Vector((max(p.x for p in points), max(p.y for p in points), max(p.z for p in points)))
    half = max((high.x - low.x), (high.y - low.y), 0.6) * 0.5 * 1.05
    return {"frame": box_points((low + high) * 0.5, (half, half, (high.z - low.z) * 0.5)),
            "azimuth": -40.0, "elevation": 20.0}


def stop_playing():
    """Stop the bloom's playback and rest on its last frame."""
    scene = bpy.context.scene
    window = bpy.context.window
    if window is not None and window.screen.is_animation_playing:
        bpy.ops.screen.animation_cancel(restore_frame=False)
    scene.frame_set(scene.frame_end)


def play_out(scene, headless=None):
    """Wait for the bloom to finish playing, then stop on its last frame.

    Playback loops: left alone for the length of the bloom it would run on
    past the last key and start over, on screen. So it is watched, in short
    waits, and stopped the moment it gets there. Headless there is no playback
    to watch, and one wait of the right length stands in.
    """
    seconds = FLOWER_FRAMES / max(1.0, scene.render.fps / scene.render.fps_base)
    if headless is None:
        headless = bpy.app.background
    if headless:
        yield ("wait", seconds)
    else:
        waited, top = 0.0, 0
        while waited < seconds + 3.0:
            yield ("wait", 0.05)
            waited += 0.05
            top = max(top, scene.frame_current)
            if top >= scene.frame_end - 1 or scene.frame_current < top - 5:
                break
    yield ("call", stop_playing)


def steps_4(parts):
    """The flower, as beats a user could follow: the parts, one petal opened by
    hand, Ride Along, Lead, the inner ring's Delay, the leaves' Follows, then
    Animate and the bloom. Each beat shows the panel doing it and then a quick
    Play scrub of what it added.

    It does what FLOWER.flower_steps does - the same poses, Leads, Delays,
    Follows, pivots, ease and frames, from the same constants - in a different
    order and at a pace to read. test_headless.py plays both and compares the
    flower's mesh frame by frame, so the two cannot drift apart unseen.
    """
    flower = FLOWER
    scene = bpy.context.scene
    outer, inner, core = parts["outer"], parts["inner"], parts["core"]
    leaves = [seg for chain in parts["leaves"] for seg in chain]
    camera = parts["camera"]
    leader, inner_leader = outer[0], inner[0]
    riders, inner_riders = outer[1:], inner[1:]
    posed = [leader, inner_leader, core] + leaves     # what is opened by hand
    home = flower.closed_places(parts)
    frames = FLOWER_FRAMES

    def open_pose(obj, degrees):
        return home[obj.name] @ Matrix.Rotation(math.radians(degrees), 4, "Y")

    leader_open = open_pose(leader, flower.OUTER_OPEN)
    inner_open = open_pose(inner_leader, flower.INNER_OPEN)
    core_open = (Matrix.Translation((0.0, 0.0, flower.CORE_RISE)) @ home[core.name]
                 @ Matrix.Rotation(math.radians(flower.CORE_TURN), 4, "Z"))
    # The leaves go half way, then the rest: a tween turns a segment the short
    # way round, and a curled leaf is folded too far to cross in one.
    half_open, unfurled = [], []
    for spec, chain in zip(flower.leaf_layout(), parts["leaves"]):
        half_open += list(zip(chain, flower.leaf_poses(spec, "mid")))
        unfurled += list(zip(chain, flower.leaf_poses(spec, "opened")))

    def say(line):
        return ("caption", None, line)

    def select(objects, active=None):
        return op_select(scene, objects, active)

    def move():
        return the_move(scene)

    def new_move():
        need(bpy.ops.rigmoves.new_move(), "New Move", scene)

    def pivot(obj):
        # The 3D cursor on the joint, then Pivot: Cursor, as the guide says.
        def run():
            scene.cursor.location = obj.matrix_world.translation
            pick(scene, [obj])
            need(bpy.ops.rigmoves.set_pivot(index=0, kind="CURSOR"), "Pivot", scene)
        return ("call", run)

    def record_after():
        pick(scene, posed, leader)
        need(bpy.ops.rigmoves.record(index=0, which="AFTER"), "Record After", scene)

    def ride(head):
        def run():
            need(bpy.ops.rigmoves.ride_along(index=0, leader=head.name,
                                             rig_name=scene.rigmoves_rig.name),
                 "Ride Along", scene)
        return ("call", run)

    def sections(riding=None, timing=None, follows=None):
        def run():
            open_sections(scene, riders=riding, timing=timing, chain=follows)
        return ("call", run)

    def lead_of(obj, apart, per_step):
        azimuth = math.degrees(home[obj.name].to_euler().z)
        return round(flower.separation(azimuth) / apart) * per_step

    def delay_setter(obj):
        def put(value):
            move().parts[obj.name].start = value
        return put

    def follow(after, before):
        def run():
            pick(scene, [after])
            move().parts[after.name].follows = before.name
        return ("call", run)

    def ease():
        move().ease = flower.EASE

    def build():
        pick(scene, [leader], leader)
        need(bpy.ops.rigmoves.build(), "Build Sliders", scene)

    def animate():
        the = move()
        the.play_frames = frames
        scene.frame_start = 1
        scene.frame_set(1)
        need(bpy.ops.rigmoves.animate(index=0), "Animate", scene)
        scene.frame_end = 1 + frames
        scene.frame_set(1)

    def play():
        # Not when there is no window to play in: the headless runner.
        if bpy.app.background:
            return
        try:
            bpy.ops.screen.animation_play()
        except RuntimeError:
            pass

    def scrub(line):
        """The Play slider up and back down, to show what the beat added."""
        yield say(line)
        yield ("tween_value", play_setter(scene), 0.0, 100.0, 1.1)
        yield ("wait", 0.2)
        yield ("tween_value", play_setter(scene), 100.0, 0.0, 0.9)
        yield ("wait", 0.4)

    scene.frame_start = 1
    scene.frame_current = 1
    # Animate stretches the scene to hold the bloom, but never shortens it,
    # and playback would run on past the last key.
    scene.frame_end = 1 + frames
    try:
        scene.sync_mode = "FRAME_DROP"     # real time, even if the viewport is slow
    except Exception:
        pass

    # a. the parts, and New Move
    yield ("wait", 0.6)
    yield say("The parts \u2014 8 outer petals \u00b7 6 inner \u00b7 a core \u00b7 2 leaves of 3 segments")
    yield select([o for o in parts["all"] if o.type == "MESH" and o not in (
        parts["pedestal"], parts["stem"])])
    yield ("wait", 2.6)
    yield say("Select one petal of each ring, the core and the leaves")
    yield select(posed, leader)
    yield ("wait", 1.8)
    yield say("New Move \u2014 the closed bud is Before")
    yield ("call", new_move)
    yield ("wait", 2.0)

    # b. open ONE outer petal by hand, then the rest of what is posed
    yield say("Open ONE outer petal by hand")
    yield select([leader])
    yield ("wait", 0.3)
    yield ("tween", [(leader, leader_open)], 1.3)
    yield ("wait", 0.4)
    yield say("Then one inner petal")
    yield select([inner_leader])
    yield ("wait", 0.3)
    yield ("tween", [(inner_leader, inner_open)], 1.0)
    yield ("wait", 0.3)
    yield say("The core rises and turns")
    yield select([core])
    yield ("wait", 0.3)
    yield ("tween", [(core, core_open)], 1.0)
    yield ("wait", 0.3)
    yield say("Leaves \u2014 the 3D cursor on each joint, Pivot: Cursor")
    for obj in leaves:
        yield pivot(obj)
        yield ("wait", 0.3)
    yield ("wait", 0.3)
    yield say("Unfurl the leaves")
    yield select(leaves)
    yield ("wait", 0.3)
    yield ("tween", half_open, 1.2)
    yield ("tween", unfurled, 0.7)
    yield ("wait", 0.3)
    yield say("Record After \u2014 the open flower")
    yield ("call", record_after)
    yield ("wait", 1.6)

    # c. Ride Along, then the first Build and a scrub
    yield say("Ride Along \u2014 the other 7 copy it from their own place")
    yield select(riders + [leader], leader)
    yield ("wait", 1.4)
    yield ride(leader)
    yield sections(riding=True, timing=False, follows=False)
    yield op_panel_top()
    yield ("wait", 1.0)
    yield say("Build Sliders \u2014 one slider plays it")
    yield ("call", build)
    yield op_panel_top()
    yield ("wait", 1.0)
    yield from scrub("Play \u2014 all 8 open together")

    # d. Leads, one after another
    yield say("Lead \u2014 a wave runs round the ring")
    yield ("wait", 0.4)
    for obj in riders:
        yield select([obj])
        yield ("tween_value", lead_setter(scene, obj), 0.0,
               float(lead_of(obj, 45.0, flower.OUTER_LEAD_PER_STEP)), 0.3)
        yield ("wait", 0.1)
    yield ("wait", 0.3)
    yield ("call", build)
    yield from scrub("Play \u2014 they open in a wave")

    # e. the inner ring: the same, with a Delay, and the core's
    yield say("Inner ring \u2014 the same: Ride Along, then Leads")
    yield select(inner_riders + [inner_leader], inner_leader)
    yield ("wait", 1.2)
    yield ride(inner_leader)
    yield ("wait", 0.6)
    for obj in inner_riders:
        yield select([obj])
        yield ("tween_value", lead_setter(scene, obj), 0.0,
               float(lead_of(obj, 60.0, flower.INNER_LEAD_PER_STEP)), 0.3)
        yield ("wait", 0.1)
    yield ("wait", 0.3)
    yield say("A Delay for the inner petals and the core")
    yield sections(riding=False, timing=True, follows=False)
    yield op_panel_top()
    yield select([inner_leader])
    yield ("wait", 0.4)
    yield ("tween_value", delay_setter(inner_leader), 0.0, flower.INNER_DELAY, 0.6)
    yield ("wait", 0.3)
    yield select([core])
    yield ("wait", 0.2)
    yield ("tween_value", delay_setter(core), 0.0, flower.CORE_DELAY, 0.6)
    yield ("wait", 0.5)
    yield ("call", build)
    yield from scrub("Play \u2014 the inner ring and the core open later")

    # f. the leaves: Follows, and a Delay for each segment
    yield say("Leaves \u2014 each segment Follows the one before")
    yield sections(riding=False, timing=False, follows=True)
    yield op_panel_top()
    yield ("wait", 0.8)
    for chain in parts["leaves"]:
        for before, after in zip(chain, chain[1:]):
            yield follow(after, before)
            yield ("wait", 0.5)
    yield ("wait", 0.3)
    yield say("A Delay for each leaf segment")
    yield sections(riding=False, timing=True, follows=False)
    yield op_panel_top()
    yield ("wait", 0.5)
    for obj, delay in zip(parts["leaves"][0] + parts["leaves"][1], flower.LEAF_DELAYS * 2):
        yield select([obj])
        yield ("tween_value", delay_setter(obj), 0.0, delay, 0.25)
        yield ("wait", 0.1)
    yield ("wait", 0.4)
    yield say("Build Sliders \u2014 Follows waits for it")
    yield ("call", build)
    yield ("wait", 0.8)
    yield from scrub("Play \u2014 the leaves unfurl joint by joint")

    # g. ease, Animate, then the bloom through the camera, the view large
    yield say("Ease: Smooth \u2014 start and stop gently")
    yield ("call", ease)
    yield ("wait", 1.0)
    yield ("call", build)
    yield ("wait", 0.6)
    yield say("Animate \u2014 the bloom over {:d} frames".format(frames))
    yield ("call", animate)
    yield ("wait", 1.8)
    yield say("The 3D view large, through the camera")
    yield ("maximise", True)
    yield ("wait", 0.6)
    yield ("view", {"camera": camera})
    # Frame 1 through the promo camera, held still: the outro's render starts
    # on exactly this picture.
    yield ("wait", 1.0)
    yield say("Play \u2014 the whole bloom")
    yield ("call", play)
    yield from play_out(scene)
    yield ("wait", 1.5)
    yield ("maximise", False)
    yield ("wait", 1.0)


SCENE_DEFS = {
    1: {"title": "One cube", "chip": "1 · One cube", "build": build_1,
        "steps": steps_1, "view": view_1, "color": "MATERIAL"},
    2: {"title": "Ride Along", "chip": "2 · Ride Along", "build": build_2,
        "steps": steps_2, "view": view_2, "color": "MATERIAL"},
    3: {"title": "Curved path", "chip": "3 · Curved path", "build": build_3,
        "steps": steps_3, "view": view_3, "color": "MATERIAL"},
    4: {"title": "Mechanical flower", "chip": "4 · Rig something real",
        "build": build_4, "steps": steps_4, "view": view_4, "color": "OBJECT"},
}


def scenes_to_play():
    """(numbers that will play, notes about the ones that will not)."""
    numbers, notes = [], []
    for number in SCENES:
        if number not in SCENE_DEFS:
            notes.append("Scene {!s} does not exist.".format(number))
        elif number == 4 and FLOWER is None:
            notes.append("Scene 4 is left out: this copy has no flower code in it.")
        elif number not in numbers:
            numbers.append(number)
    return numbers, notes


# ===========================================================================
# The engine: plays a generator of actions, live or all at once
# ===========================================================================

def dwell(line):
    """Seconds a caption has to stay up to be read: 1.2 for a short one, up to
    2 for a long one."""
    words = len([w for w in line.split() if any(c.isalnum() for c in w)])
    return min(2.0, 1.2 + 0.2 * max(0, words - 4))


def action_seconds(action):
    """How long an action takes, as designed."""
    kind = action[0]
    if kind == "wait":
        return float(action[1])
    if kind == "tween":
        return float(action[2])
    if kind == "tween_value":
        return float(action[4])
    if kind == "view":
        spec = action[1] or {}
        return float(spec.get("seconds", 1.6 if spec.get("camera") is not None else 0.0))
    return 0.0


def readable(steps):
    """Pass a scene's actions through, holding every caption on screen long
    enough to read before the next one replaces it. A wait is put in where a
    scene would change the line too soon; the scenes' own waits are meant to
    make that rare."""
    shown, need, said = None, 0.0, ""
    for action in steps:
        if action[0] == "caption" and action[2] is not None:
            line = action[2]
            if line and shown is not None and shown < need - 1e-6 and line != said:
                yield ("wait", need - shown)
            shown, need, said = (0.0, dwell(line), line) if line else (None, 0.0, "")
        elif shown is not None:
            shown += action_seconds(action)
        yield action
    if shown is not None and shown < need - 1e-6:
        yield ("wait", need - shown)


class Timed:
    """An action in progress: lasts `seconds`, and `apply(e)` is told how far
    along it is, eased, from 0 to 1."""
    __slots__ = ("seconds", "started", "apply")

    def __init__(self, seconds, started, apply):
        self.seconds = seconds
        self.started = started
        self.apply = apply


class Player:
    """Runs one generator of action tuples (see SPEC.md).

    Live, `step(now)` is called on a timer and a tween follows the clock.
    Instant, every tween jumps to its end and every wait is skipped, which is
    how the tests run the very same scenes.
    """

    def __init__(self, stage, instant=False, speed=1.0):
        self.stage = stage
        self.instant = instant
        self.speed = max(0.05, float(speed))
        self.gen = None
        self.current = None
        self.chip = ""
        self.line = ""
        self.changed = 0.0          # when the line last changed, so it can fade in
        self.bar_changed = 0.0      # when the strip behind it last came up
        self.extras = {}            # actions only the Show knows: enter, countdown
        self.again = False          # the screen was swapped: find the viewport anew
        self.length = 0.0           # seconds of everything played, as designed
        self.captions = []          # (seconds in, chip, line), for the record

    def run(self, generator):
        self.gen = generator

    def timed(self, seconds, now, apply):
        self.length += max(0.0, seconds)
        if self.instant or seconds <= 0.0:
            if apply is not None:
                apply(1.0)
            return
        self.current = Timed(seconds / self.speed, now, apply)

    def begin(self, action, now):
        kind = action[0]
        if kind == "caption":
            _kind, chip, line = action
            if chip is not None:
                self.chip = chip
            if line is not None:
                if line and not self.line:
                    self.bar_changed = now
                self.line = line
                self.changed = now
                if line:
                    self.captions.append((round(self.length, 2), self.chip, line))
        elif kind == "wait":
            self.timed(float(action[1]), now, None)
        elif kind == "tween":
            self.begin_tween(action[1], float(action[2]), now)
        elif kind == "tween_value":
            _kind, setter, start, end, seconds = action
            self.timed(float(seconds), now,
                       lambda e: setter(end if e >= 1.0 else start + (end - start) * e))
        elif kind == "call":
            action[1]()
        elif kind == "view":
            moved = self.stage.view(action[1])
            if moved is not None:
                self.timed(moved[0], now, moved[1])
        elif kind in self.extras:
            self.extras[kind](action, now)
        else:
            raise ValueError("unknown action " + repr(kind))

    def begin_tween(self, pairs, seconds, now):
        # Read where everything stands now, not where it was when the scene
        # was planned: a Build can seat things somewhere else.
        self.stage.refresh()
        starts = []
        for obj, target in pairs:
            loc, rot, size = obj.matrix_world.decompose()
            t_loc, t_rot, t_size = target.decompose()
            starts.append((obj, loc, rot, size, target, t_loc, t_rot, t_size))

        def apply(e):
            for obj, loc, rot, size, target, t_loc, t_rot, t_size in starts:
                if e >= 1.0:
                    obj.matrix_world = target
                else:
                    obj.matrix_world = Matrix.LocRotScale(
                        loc.lerp(t_loc, e), rot.slerp(t_rot, e), size.lerp(t_size, e))
        self.timed(seconds, now, apply)

    def step(self, now):
        """Advance to `now`. Returns False once the generator has finished."""
        while True:
            current = self.current
            if current is not None:
                u = (now - current.started) / current.seconds
                if u < 1.0:
                    if current.apply is not None:
                        current.apply(smooth(u))
                    return True
                if current.apply is not None:
                    current.apply(1.0)
                self.current = None
            if self.gen is None:
                return False
            try:
                action = next(self.gen)
            except StopIteration:
                self.gen = None
                return False
            self.begin(action, now)
            if self.current is not None:
                return True
            if self.again:
                # The viewport the caller overrode is not the one in front now.
                self.again = False
                return True

    def run_instant(self):
        while self.step(0.0):
            pass


# ===========================================================================
# The stage: window, 3D viewport, look, sidebar, camera
# ===========================================================================

# Everyday Blender: Solid mode with the studio light, as it comes, and the
# sidebar open. Everything else - the menus, tabs, outliner, properties,
# timeline, header, toolbar, gizmo, grid, axes, theme - is left alone.
LOOK = (
    ("shading.type", "SOLID"),
    ("shading.light", "STUDIO"),
    ("show_region_ui", True),
)


def snapshot(value):
    """A value to keep: a colour or vector read from Blender is a live view of
    the setting, and would change with it."""
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    try:
        return tuple(value)
    except TypeError:
        return value


def get_path(root, path):
    for name in path.split("."):
        root = getattr(root, name)
    return root


def set_path(root, path, value):
    *head, last = path.split(".")
    for name in head:
        root = getattr(root, name)
    setattr(root, last, value)


class Stage:
    """Everything that touches the window. Finds the 3D viewport afresh on
    every call, because the user can change the layout under a long run."""

    def __init__(self, window):
        self.window_ptr = window.as_pointer()
        self.saved = {}             # look settings as they were before
        self.target_workspace = None
        self.state = "workspace"
        self.since = None
        self.full_by_us = False     # the whole run in the full view (FULL_VIEWPORT)
        self.bloom_by_us = False    # the maximised view for scene 4's bloom
        self.on_change = None       # called when the window's screen has been swapped
        self.start_scene = window.scene.name
        self.start_workspace = window.workspace.name if window.workspace else None
        self.saved_view = None      # the viewport's camera and zoom, as they were
        self.category_before = None
        self.category_ok = False
        self.complained = set()

    # --- finding things

    def window(self):
        for window in bpy.context.window_manager.windows:
            if window.as_pointer() == self.window_ptr:
                return window
        return None

    def find(self):
        """(window, area, window region) of the biggest 3D viewport, or None."""
        window = self.window()
        if window is None or window.screen is None:
            return None
        best = None
        for area in window.screen.areas:
            if area.type == "VIEW_3D" and (
                    best is None or area.width * area.height > best.width * best.height):
                best = area
        if best is None:
            return None
        region = next((r for r in best.regions if r.type == "WINDOW"), None)
        return None if region is None else (window, best, region)

    @contextmanager
    def override(self):
        found = self.find()
        if found is None:
            yield None
            return
        window, area, region = found
        with bpy.context.temp_override(window=window, area=area, region=region):
            yield found

    def refresh(self):
        bpy.context.view_layer.update()

    def complain(self, key, text):
        """Say a thing once: a setting that does not exist in this Blender."""
        if key not in self.complained:
            self.complained.add(key)
            print("CopyThat promo:", text)

    # --- getting the window ready

    def big_area(self):
        found = self.find()
        window = self.window()
        if found is None or window is None:
            return False
        area = found[1]
        return area.width * area.height >= 0.4 * window.width * window.height

    def is_full(self):
        window = self.window()
        return window is not None and (window.screen.is_temporary or window.screen.show_fullscreen)

    def settle(self, now, want_full):
        """Walk the window into shape: a workspace with a big 3D viewport, then
        the viewport over the whole window, then the sidebar. True once it is ready. Anything
        that does not go through is given up on after a few seconds, so the
        run still happens."""
        window = self.window()
        if window is None:
            raise RuntimeError("The Blender window went away.")
        if self.since is None:
            self.since = now
        if self.state == "workspace":
            if self.target_workspace is None and not self.big_area():
                # The Scripting tab's viewport is a postage stamp.
                for name in ("Layout", "Modeling", "Sculpting", "Animation", "Shading"):
                    found = bpy.data.workspaces.get(name)
                    if found is not None:
                        self.target_workspace = found
                        window.workspace = found
                        break
                else:
                    self.complain("workspace", "no workspace with a 3D viewport was found.")
            there = (self.target_workspace is None
                     or (window.workspace == self.target_workspace and self.big_area()))
            if not there and now - self.since < 3.0:
                return False
            self.state, self.since = "full", now
        if self.state == "full":
            if not want_full or self.is_full():
                self.state, self.since = "sidebar", now
            elif not self.full_by_us:
                self.full_by_us = self.toggle_full(hide=True)
                if not self.full_by_us:
                    self.state = "sidebar"
                self.since = now
                return False
            elif now - self.since < 1.5:
                return False
            else:
                self.state, self.since = "sidebar", now
        if self.state == "sidebar":
            # Open, and drawn once: until then it has no width, and the first
            # scene would be framed as if it were not there.
            found = self.find()
            if found is not None:
                self.keep(found)
                ui = next((r for r in found[1].regions if r.type == "UI"), None)
                if ui is None or ui.width > 1:
                    self.state = "ready"
            if self.state != "ready":
                if now - self.since < 1.5:
                    return False
                self.state = "ready"
        return True

    def toggle_full(self, hide=True):
        """The 3D viewport over the whole window. With `hide` it is Ctrl+Alt+Space,
        no menus; without, Ctrl+Space, which keeps the headers."""
        found = self.find()
        if found is None:
            return False
        window, area, region = found
        try:
            with bpy.context.temp_override(window=window, screen=window.screen,
                                           area=area, region=region):
                done = bpy.ops.screen.screen_full_area(use_hide_panels=hide)
            if done != {"FINISHED"}:
                return False
            # The area, and the window's screen, are different ones now.
            if self.on_change is not None:
                self.on_change()
            return True
        except Exception as exc:
            self.complain("full", "could not fill the window with the viewport: " + short_error(exc))
            return False

    def maximise(self):
        """Ctrl+Space: the 3D view fills the window, headers kept."""
        if not self.is_full() and self.toggle_full(hide=False):
            self.bloom_by_us = True

    def unmaximise(self):
        if self.bloom_by_us and self.is_full():
            self.toggle_full(hide=False)
        self.bloom_by_us = False

    def restore_full(self):
        """Put the window back as it was, if this run changed it. The same kind
        of toggle that went in has to come out: Blender turns the other kind
        down."""
        if self.is_full():
            if self.bloom_by_us:
                self.toggle_full(hide=False)
            elif self.full_by_us:
                self.toggle_full(hide=True)
        self.full_by_us = self.bloom_by_us = False

    # --- the look of the viewport

    def look(self, color_type):
        found = self.find()
        if found is None:
            return
        space = found[1].spaces.active
        self.save_view(space)
        settings = LOOK + (("shading.color_type", color_type),)
        for path, value in settings:
            try:
                self.remember(space, path)
                set_path(space, path, value)
            except Exception as exc:
                self.complain(path, "setting {:s} did not work here ({:s}).".format(
                    path, short_error(exc)))

    def remember(self, space, path):
        """A setting as the user had it, before the first time it is changed."""
        if path not in self.saved:
            self.saved[path] = snapshot(get_path(space, path))

    def save_view(self, space):
        """Where the viewport looked before the first scene, once."""
        if self.saved_view is None:
            rv3d = space.region_3d
            self.saved_view = {
                "view_location": rv3d.view_location.copy(),
                "view_rotation": rv3d.view_rotation.copy(),
                "view_distance": rv3d.view_distance,
                "lens": space.lens,
                "view_camera_zoom": rv3d.view_camera_zoom,
                "view_camera_offset": tuple(rv3d.view_camera_offset),
                "view_perspective": rv3d.view_perspective}

    def restore_look(self):
        """Give the viewport back: its settings, its sidebar tab, and where it
        looked, in camera view or not."""
        found = self.find()
        if found is None:
            return
        area = found[1]
        space = area.spaces.active
        for path, value in self.saved.items():
            try:
                set_path(space, path, value)
            except Exception:
                pass
        self.saved = {}
        if self.saved_view is not None:
            rv3d = space.region_3d
            try:
                for name, value in self.saved_view.items():
                    if name == "lens":
                        space.lens = value
                    elif name != "view_perspective":
                        setattr(rv3d, name, value)
                rv3d.view_perspective = self.saved_view["view_perspective"]
            except Exception as exc:
                self.complain("view", "could not put the view back ({:s}).".format(
                    short_error(exc)))
            self.saved_view = None
        if self.category_ok and self.category_before:
            ui = next((r for r in area.regions if r.type == "UI"), None)
            try:
                ui.active_panel_category = self.category_before
            except Exception:
                pass

    def keep(self, found):
        """The sidebar open, on the CopyThat tab. The tab can only be chosen
        once Blender has drawn the sidebar, so this is tried until it takes."""
        _window, area, _region = found
        space = area.spaces.active
        if not space.show_region_ui:
            self.remember(space, "show_region_ui")
            space.show_region_ui = True
        if not self.category_ok:
            ui = next((r for r in area.regions if r.type == "UI"), None)
            if ui is not None:
                try:
                    if self.category_before is None:
                        self.category_before = ui.active_panel_category
                    ui.active_panel_category = "CopyThat"
                    self.category_ok = ui.active_panel_category == "CopyThat"
                except Exception:
                    pass

    def metrics(self, area):
        """Pixels of the viewport that nothing covers: the sidebar and header
        float over it, so the captions have to keep clear."""
        window = next(r for r in area.regions if r.type == "WINDOW")
        ui = next((r for r in area.regions if r.type == "UI"), None)
        visible = window.width
        if ui is not None and ui.width > 1 and ui.x > window.x:
            visible = max(1, min(window.width, ui.x - window.x))
        top = left = 0
        for region in area.regions:
            if region.type in ("HEADER", "TOOL_HEADER") and region.height > 1 \
                    and region.y >= window.y + window.height * 0.5:
                top = max(top, window.y + window.height - region.y)
            elif region.type == "TOOLS" and region.width > 1:
                left = max(left, region.x + region.width - window.x)
        shown = self.window()
        return {"width": window.width, "height": window.height, "visible": visible,
                "top": top, "left": max(0, left),
                "window_height": shown.height if shown is not None and shown.height else window.height}

    # --- scenes and views

    def show(self, scene):
        window = self.window()
        window.scene = scene

    def back_to_start(self):
        window = self.window()
        scene = bpy.data.scenes.get(self.start_scene)
        if window is not None and scene is not None:
            window.scene = scene

    def back_to_workspace(self):
        """The tab the run started in, if it moved away from it. Blender takes
        this up on its next pass, which is why the show asks for it late."""
        window = self.window()
        if window is None or self.target_workspace is None or not self.start_workspace:
            return
        found = bpy.data.workspaces.get(self.start_workspace)
        if found is not None and window.workspace != found:
            window.workspace = found

    def view(self, spec):
        """Work out a viewport move from a spec: (seconds, apply), where
        apply(e) puts the view e of the way there, 0 to 1. None if there is
        no viewport to set.

        Specs: {"camera": obj}; {"location", "rotation", "distance"}; or
        {"frame": points, "azimuth", "elevation", "lens"}, which works out the
        view that keeps the points clear of the sidebar and the captions. Any
        of them may carry "seconds" for a glide there.
        """
        found = self.find()
        if spec is None or found is None:
            return None
        window, area, region = found
        space = area.spaces.active
        rv3d = space.region_3d
        seconds = float(spec.get("seconds", 0.0))
        goal_camera = spec.get("camera")
        if goal_camera is not None:
            if window.scene.camera != goal_camera:
                window.scene.camera = goal_camera
            seconds = float(spec.get("seconds", 1.6))
            target = self.camera_view(goal_camera, rv3d, space, region, window.scene)
            try:
                # The dimmed bands round the frame, off for the take. This
                # camera is one the scene made for itself, so it stays off.
                goal_camera.data.show_passepartout = False
            except Exception:
                pass
        elif "frame" in spec:
            metrics = self.metrics(area)
            target = frame_view(
                spec["frame"], spec.get("azimuth", 30.0), spec.get("elevation", 22.0),
                spec.get("lens", space.lens), metrics["width"] / max(1.0, metrics["height"]),
                margins(metrics)) + (None,)
        else:
            target = (Vector(spec["location"]), Quaternion(spec["rotation"]),
                      float(spec["distance"]), spec.get("lens", space.lens), None)

        if rv3d.view_perspective != "PERSP":
            rv3d.view_perspective = "PERSP"
        start = (rv3d.view_location.copy(), rv3d.view_rotation.copy(),
                 rv3d.view_distance, space.lens)

        def apply(e):
            # Found again each time: a glide can outlast a change of layout.
            now = self.find()
            if now is None:
                return
            space = now[1].spaces.active
            rv3d = space.region_3d
            rv3d.view_location = start[0].lerp(target[0], e)
            rv3d.view_rotation = start[1].slerp(target[1], e)
            rv3d.view_distance = start[2] + (target[2] - start[2]) * e
            space.lens = start[3] + (target[3] - start[3]) * e
            if e >= 1.0 and goal_camera is not None:
                # Whatever the viewport held, the frame fills it, centred.
                rv3d.view_camera_offset = (0.0, 0.0)
                rv3d.view_camera_zoom = target[4]
                rv3d.view_perspective = "CAMERA"

        return seconds, apply

    def view_now(self, spec):
        moved = self.view(spec)
        if moved is not None:
            moved[1](1.0)

    @staticmethod
    def camera_view(camera, rv3d, space, region, scene):
        """The free view that looks exactly where the camera does, to glide
        into before switching to the camera itself, and the camera-view zoom
        that makes the camera's frame fill the viewport.

        A free view has twice the field of view of a camera at the same lens
        (zoom 2.0), so its lens is doubled. See camera_fit() for the rest.
        """
        world = camera.matrix_world
        rotation = world.to_quaternion()
        distance = max(rv3d.view_distance, 3.0)
        fit, zoom = camera_fit(scene.render.resolution_x, scene.render.resolution_y,
                               region.width, region.height)
        if camera.data.type == "PERSP":
            lens = min(250.0, 2.0 * fit * camera.data.lens)
        else:
            lens = space.lens
        centre = world.translation + rotation @ Vector((0.0, 0.0, -distance))
        return centre, rotation, distance, lens, zoom


def camera_fit(res_x, res_y, width, height):
    """(f, view_camera_zoom) that fill a width x height viewport with a camera
    frame of res_x x res_y.

    In camera view the frame is 1 / (zoom_to_fac * 2) of the viewport's width
    at view_camera_zoom 0, and fills it at 29.289. A viewport wider than the
    frame would crop it top and bottom, so the zoom backs off by f until the
    frame's height fits instead. f = 1 for the usual 16:9 and narrower.
    """
    res_aspect = res_x / max(1.0, res_y)
    fit = min(1.0, res_aspect / ((width / max(1.0, height)) or res_aspect))
    return fit, 50.0 * (2.0 * math.sqrt(fit) - math.sqrt(2.0))


def margins(metrics):
    """Fractions of the viewport to keep clear: left, right, top, bottom."""
    width, height = max(1.0, metrics["width"]), max(1.0, metrics["height"])
    return (metrics.get("left", 0) / width + 0.03, 1.0 - metrics["visible"] / width + 0.03,
            metrics["top"] / height + 0.07, 0.17)


def view_rotation(azimuth, elevation):
    """A viewport rotation that looks at the target from the front, turned
    `azimuth` degrees towards +X (negative: towards -X) and `elevation` up.
    From the front left, the sides that show are the ones the studio light
    falls on; from the right they would come out nearly black."""
    az, el = math.radians(azimuth), math.radians(elevation)
    eye = Vector((math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el)))
    return eye.to_track_quat("Z", "Y")


def project(points, centre, rotation, distance, lens, aspect):
    """Where points land on screen, -1 to 1 each way, for a view."""
    right = rotation @ Vector((1.0, 0.0, 0.0))
    up = rotation @ Vector((0.0, 1.0, 0.0))
    back = rotation @ Vector((0.0, 0.0, 1.0))
    eye = centre + back * distance
    # A 3D viewport shows tan(half FOV) = 36 / lens on the longer side (zoom
    # 2.0 on a 36 mm sensor), twice a camera object's 18 / lens.
    half = 36.0 / lens
    tan_x, tan_y = (half, half / aspect) if aspect >= 1.0 else (half * aspect, half)
    out = []
    for point in points:
        v = point - eye
        depth = -v.dot(back)
        out.append((v.dot(right) / depth / tan_x, v.dot(up) / depth / tan_y))
    return out, (tan_x, tan_y), (right, up)


def frame_view(points, azimuth, elevation, lens, aspect, keep_clear):
    """The view (location, rotation, distance, lens) that shows all the points,
    centred in what the sidebar, header and captions leave free."""
    left, right_, top, bottom = keep_clear
    x0, x1 = -1.0 + 2.0 * left, 1.0 - 2.0 * right_
    y0, y1 = -1.0 + 2.0 * bottom, 1.0 - 2.0 * top
    rotation = view_rotation(azimuth, elevation)
    low = Vector((min(p.x for p in points), min(p.y for p in points), min(p.z for p in points)))
    high = Vector((max(p.x for p in points), max(p.y for p in points), max(p.z for p in points)))
    middle = (low + high) * 0.5

    def fit(distance):
        centre = middle.copy()
        for _ in range(4):
            shown, (tan_x, tan_y), (right, up) = project(
                points, centre, rotation, distance, lens, aspect)
            lo_x, hi_x = min(s[0] for s in shown), max(s[0] for s in shown)
            lo_y, hi_y = min(s[1] for s in shown), max(s[1] for s in shown)
            # Move the target so the picture's middle lands on the free
            # area's middle.
            centre = centre + right * (((lo_x + hi_x) / 2.0 - (x0 + x1) / 2.0) * tan_x * distance) \
                + up * (((lo_y + hi_y) / 2.0 - (y0 + y1) / 2.0) * tan_y * distance)
        shown, _tans, _axes = project(points, centre, rotation, distance, lens, aspect)
        lo_x, hi_x = min(s[0] for s in shown), max(s[0] for s in shown)
        lo_y, hi_y = min(s[1] for s in shown), max(s[1] for s in shown)
        ok = hi_x - lo_x <= x1 - x0 and hi_y - lo_y <= y1 - y0
        return ok, centre

    near, far = 1.0, 400.0
    for _ in range(40):
        mid = (near + far) / 2.0
        if fit(mid)[0]:
            far = mid
        else:
            near = mid
    distance = far
    return fit(distance)[1], rotation, distance, lens


# ===========================================================================
# Captions: drawn over the viewport with blf and gpu
# ===========================================================================

def rounded_fan(x, y, w, h, radius, steps=6):
    """Triangles for a rounded rectangle, as a flat list of 2D points."""
    radius = max(0.0, min(radius, w / 2.0, h / 2.0))
    edge = []
    for cx, cy, start in ((x + w - radius, y + radius, -90.0), (x + w - radius, y + h - radius, 0.0),
                          (x + radius, y + h - radius, 90.0), (x + radius, y + radius, 180.0)):
        for i in range(steps + 1):
            angle = math.radians(start + 90.0 * i / steps)
            edge.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    centre = (x + w / 2.0, y + h / 2.0)
    out = []
    for i in range(len(edge)):
        out.extend((centre, edge[i], edge[(i + 1) % len(edge)]))
    return out


class GpuPainter:
    """Draws rectangles and text in the region's pixels."""

    def __init__(self):
        import blf
        import gpu
        from gpu_extras.batch import batch_for_shader
        self.blf, self.gpu, self.batch_for_shader = blf, gpu, batch_for_shader
        try:
            self.shader = gpu.shader.from_builtin("UNIFORM_COLOR")
        except Exception:
            self.shader = gpu.shader.from_builtin("2D_UNIFORM_COLOR")
        self.font = 0
        gpu.state.blend_set("ALPHA")

    def finish(self):
        self.gpu.state.blend_set("NONE")

    def size(self, pixels):
        try:
            self.blf.size(self.font, pixels)
        except TypeError:
            self.blf.size(self.font, pixels, 72)

    def rect(self, x, y, w, h, radius, color):
        # Text drawing can leave blending off, so say it again every time.
        self.gpu.state.blend_set("ALPHA")
        batch = self.batch_for_shader(self.shader, "TRIS",
                                      {"pos": rounded_fan(x, y, w, h, radius)})
        self.shader.bind()
        self.shader.uniform_float("color", color)
        batch.draw(self.shader)

    def text(self, x, y, pixels, color, string):
        self.size(pixels)
        self.blf.color(self.font, *color)
        self.blf.position(self.font, x, y, 0)
        self.blf.draw(self.font, string)

    def width(self, pixels, string):
        self.size(pixels)
        return self.blf.dimensions(self.font, string)[0]

    def cap_height(self, pixels):
        self.size(pixels)
        return self.blf.dimensions(self.font, "H")[1]


DARK = (0.055, 0.065, 0.085)
WHITE = (1.0, 1.0, 1.0)
SOFT = (0.80, 0.84, 0.90)
ACCENT = hex_rgb(TEAL)
RED = (0.86, 0.26, 0.22)


def caption_scale(metrics):
    """How big the captions are drawn: 1.0 in a window 1080 pixels high, so
    they are the same size in the picture whatever the screen or its scaling.
    It is the window, not the 3D view, that is recorded."""
    return CAPTION_SCALE * max(1.0, float(metrics.get("window_height", metrics["height"]))) / 1080.0


def draw_overlay(painter, view, metrics, scale, now):
    """Lay out and paint the captions for one redraw.

    `view` holds what to say: chip, line, changed (when the line last
    changed), count (the countdown's number, or 0), note and error. It is
    drawn in the pixels the sidebar and header leave free. Sizes are for a
    1080p picture, read on a phone: bigger than the panel's own text.
    """
    pad = 30.0 * scale
    left = float(metrics.get("left", 0))
    safe = metrics["visible"] - left            # the width between toolbar and sidebar
    x0 = left + pad
    top = metrics["height"] - metrics["top"]

    # The chip, top left: the scene, in a dark pill with a number in the accent.
    chip = view.get("chip") or ""
    if chip:
        number, dot, title = chip.partition("\u00b7")
        size = 27.0 * scale
        h = 56.0 * scale
        y = top - pad - h
        cap = painter.cap_height(size)
        if dot:
            number, title = number.strip(), title.strip()
            inset = 6.0 * scale
            ball = h - 2.0 * inset
            gap = 14.0 * scale
            w = inset + ball + gap + painter.width(size, title) + 0.8 * pad
            painter.rect(x0, y, w, h, h / 2.0, DARK + (0.82,))
            painter.rect(x0 + inset, y + inset, ball, ball, ball / 2.0, ACCENT + (1.0,))
            painter.text(x0 + inset + (ball - painter.width(size, number)) / 2.0,
                         y + (h - cap) / 2.0, size, DARK + (1.0,), number)
            painter.text(x0 + inset + ball + gap, y + (h - cap) / 2.0, size,
                         WHITE + (1.0,), title)
        else:
            w = painter.width(size, chip) + 1.6 * pad
            painter.rect(x0, y, w, h, h / 2.0, DARK + (0.82,))
            painter.text(x0 + 0.3 * pad, y + (h - cap) / 2.0, size, WHITE + (1.0,), chip)

    # The step line, lower third: an accent stroke, a bold heading, the rest.
    error = view.get("error") or ""
    line = error or view.get("line") or ""
    if line:
        changed = view.get("changed", 0.0)
        # The text fades in on every change; the bar only when it first comes
        # up, so a new line does not make the whole strip blink.
        fade = 1.0 if error else smooth((now - changed) / 0.3)
        bar = 1.0 if error else smooth((now - view.get("bar_changed", changed)) / 0.3)
        heading, dash, rest = line.partition(" \u2014 ")
        rest = ("  \u2014  " + rest) if dash else ""
        size = 38.0 * scale
        indent = 34.0 * scale
        room = safe - 3.0 * pad - indent
        full = painter.width(size, heading + rest)
        if full > room > 0:
            size *= max(0.6, room / full)
        h = 80.0 * scale
        y = pad * 2.2
        head_w = painter.width(size, heading)
        w = indent + head_w + painter.width(size, rest) + 0.9 * pad
        painter.rect(x0, y, w, h, 14.0 * scale, DARK + (0.84 * bar,))
        painter.rect(x0 + 12.0 * scale, y + 14.0 * scale, 8.0 * scale, h - 28.0 * scale,
                     4.0 * scale, (RED if error else ACCENT) + (bar,))
        cap = painter.cap_height(size)
        text_y = y + (h - cap) / 2.0
        x = x0 + indent
        painter.text(x, text_y, size, WHITE + (fade,), heading)
        painter.text(x + 1.0 * scale, text_y, size, WHITE + (fade,), heading)
        if rest:
            painter.text(x + head_w, text_y, size, SOFT + (fade,), rest)

    # The countdown, in the middle of the free area.
    count = view.get("count") or 0
    if count:
        w, h = 540.0 * scale, 390.0 * scale
        x = left + max(pad, (safe - w) / 2.0)
        y = (metrics["height"] - h) / 2.0
        painter.rect(x, y, w, h, 40.0 * scale, DARK + (0.88,))
        small = 30.0 * scale
        label = "Starting in"
        painter.text(x + (w - painter.width(small, label)) / 2.0, y + h - 70.0 * scale,
                     small, SOFT + (1.0,), label)
        big = 220.0 * scale
        digit = str(count)
        painter.text(x + (w - painter.width(big, digit)) / 2.0, y + 92.0 * scale,
                     big, ACCENT + (1.0,), digit)
        hint = "hands off the mouse"
        painter.text(x + (w - painter.width(small, hint)) / 2.0, y + 34.0 * scale,
                     small, SOFT + (1.0,), hint)
        note = view.get("note") or ""
        if note:
            # On its own dark pill: white straight on a light viewport is hard
            # to read, and this is the one place a missing scene is said.
            tiny = 24.0 * scale
            inset = 0.8 * pad
            room = safe - 2.0 * pad - 2.0 * inset
            full = painter.width(tiny, note)
            if full > room > 0:
                tiny *= max(0.5, room / full)
                full = painter.width(tiny, note)
            ph = 46.0 * scale
            px = left + max(pad, (safe - full - 2.0 * inset) / 2.0)
            py = y - 28.0 * scale - ph
            painter.rect(px, py, full + 2.0 * inset, ph, ph / 2.0, DARK + (0.94,))
            painter.text(px + inset, py + (ph - painter.cap_height(tiny)) / 2.0, tiny,
                         WHITE + (1.0,), note)


# ===========================================================================
# The show: one run, from countdown to the last scene
# ===========================================================================

class ShowError(Exception):
    """Something to tell the user plainly, not a bug."""


def check_addon():
    """None if CopyThat is ready to be driven, else what to tell the user."""
    try:
        for name in ("new_move", "record", "build", "ride_along", "curve_path",
                     "edit_curve", "show_paths", "animate"):
            getattr(bpy.ops.rigmoves, name).get_rna_type()
        if not hasattr(bpy.types.Scene, "rigmoves_rig"):
            raise KeyError("no rig property")
    except Exception:
        return ("CopyThat is not switched on, or is older than 0.15.0. Open Edit > "
                "Preferences > Add-ons, tick CopyThat (0.15.0 or newer), then run this "
                "script again. Keep the pointer still until you have read this box.")
    return None


def tell(text):
    """Say something to the user: in the console, and as a popup."""
    print("CopyThat promo:", text)
    try:
        def draw(self, _context):
            for part in text.split(". "):
                self.layout.label(text=part.strip() + ("." if not part.endswith(".") else ""))
        bpy.context.window_manager.popup_menu(draw, title="CopyThat promo", icon="ERROR")
    except Exception:
        pass


class Show:
    def __init__(self, numbers=None, instant=False, clock=time.perf_counter, notes=None):
        if numbers is None:
            numbers, notes = scenes_to_play()
        self.numbers = list(numbers)
        self.notes = list(notes or [])
        self.instant = instant
        self.clock = clock
        self.stage = None
        self.player = None
        self.scenes = {}            # number -> the Scene made for it
        self.parts = {}             # number -> what its builder returned
        self.lengths = {}           # number -> seconds the scene plays for
        self.count_until = 0.0
        self.error = ""
        self.dead = False
        self.handle = None
        self.space_ptr = None
        self.drawing_ok = True
        self.lost = 0
        self.last_keep = -10.0
        # One object each, so a timer can be asked about and unregistered: a
        # bound method is a new object every time it is looked up.
        self.callback = self.on_timer
        self.remove_callback = self.remove_handle
        self.leave_callback = self.leave
        self.left = False
        self.guard = self.make_guard()
        self.painter_class = GpuPainter

    # --- the plan

    def master(self):
        for number in self.numbers:
            yield ("enter", number)
            if number == self.numbers[0] and COUNTDOWN > 0:
                yield ("countdown", COUNTDOWN)
            else:
                yield ("wait", PAUSE_BETWEEN)
            # Framed once more now that everything has been drawn: the sidebar
            # and the headers have their real size by here.
            spec = SCENE_DEFS[number]["view"](self.parts[number])
            if spec is not None:
                yield ("view", dict(spec, seconds=0.6))
            yield ("mark", "start", number)
            yield from readable(SCENE_DEFS[number]["steps"](self.parts[number]))
            yield ("mark", "end", number)
            yield ("wait", 1.0)

    def enter(self, action, now):
        number = action[1]
        spec = SCENE_DEFS[number]
        # Names are unique, and the rig's name is the first line of the panel:
        # the one before gives it up, so this scene's is plain "CopyThat Rig".
        for earlier, made in self.scenes.items():
            if made.rigmoves_rig is not None and made.rigmoves_rig.name == "CopyThat Rig":
                made.rigmoves_rig.name = "CopyThat Rig (scene {:d})".format(earlier)
        scene = make_scene(number, spec["title"])
        self.stage.show(scene)
        self.stage.look(spec["color"])
        self.scenes[number] = scene
        self.parts[number] = spec["build"](scene)
        found = self.stage.find()
        if found is not None:
            self.stage.keep(found)
            self.space_ptr = found[1].spaces.active.as_pointer()
        self.stage.view_now(spec["view"](self.parts[number]))
        self.player.chip = spec["chip"]
        self.player.line = ""
        self.player.changed = self.player.bar_changed = now

    def mark(self, action, now):
        _kind, what, number = action
        if what == "start":
            self.lengths[number] = -self.player.length
        else:
            self.lengths[number] += self.player.length

    def maximise(self, action, now):
        """("maximise", True): the 3D view fills the window; False: it is given back."""
        if action[1]:
            if MAXIMISE_FOR_BLOOM:
                self.stage.maximise()
        else:
            self.stage.unmaximise()

    def countdown(self, action, now):
        seconds = float(action[1])
        self.count_until = now + seconds
        self.player.timed(seconds * self.player.speed, now, None)

    # --- running

    def begin(self):
        """Everything except the timer and the drawing, so a test can walk it."""
        problem = check_addon()
        if problem:
            raise ShowError(problem)
        window = bpy.context.window
        if window is None:
            raise ShowError("Run this from Blender's Scripting tab, with a window open.")
        if not self.numbers:
            raise ShowError("There is nothing to play. " + " ".join(self.notes))
        old = earlier_runs_exist()
        retire_old_runs()
        if old:
            self.notes.append("Earlier takes are kept, renamed (old).")
        self.stage = Stage(window)
        self.player = Player(self.stage, instant=self.instant, speed=SPEED)
        self.player.extras = {"enter": self.enter, "mark": self.mark, "countdown": self.countdown,
                              "maximise": self.maximise}
        self.stage.on_change = lambda: setattr(self.player, "again", True)
        self.player.run(self.master())

    def run_instant(self, watch=None):
        """Play every scene at once, tweens jumped to their ends. `watch`, if
        given, is called with (action, show) just before each action runs, for
        a test to look in on the way."""
        self.begin()
        self.player.instant = True
        if watch is not None:
            original = self.player.begin

            def spy(action, now):
                watch(action, self)
                original(action, now)
            self.player.begin = spy
        while True:
            with self.stage.override():
                more = self.player.step(0.0)
            if not more:
                return

    def start(self):
        self.begin()
        # Always: with CAPTIONS off it still draws the countdown and any error.
        self.handle = bpy.types.SpaceView3D.draw_handler_add(
            self.draw, (), "WINDOW", "POST_PIXEL")
        bpy.app.driver_namespace[STATE_KEY] = self
        bpy.app.handlers.load_pre.append(self.guard)
        bpy.app.timers.register(self.callback, first_interval=0.3, persistent=False)
        print("CopyThat promo: starting scenes", self.numbers)
        for note in self.notes:
            print("CopyThat promo:", note)
        left_out = [n for n in self.notes if "left out" in n or "does not exist" in n]
        if left_out:
            tell(" ".join(left_out))

    def on_timer(self):
        return self.tick()

    def make_guard(self):
        """A handler that ends the run if another file is opened under it:
        the timer goes by itself then, but the drawing would not."""
        @persistent
        def guard(*_args):
            self.abandon()
        return guard

    def abandon(self):
        """End the run without touching the window, which is about to be replaced."""
        self.dead = True
        self.left = True
        if bpy.app.driver_namespace.get(STATE_KEY) is self:
            del bpy.app.driver_namespace[STATE_KEY]
        try:
            if bpy.app.timers.is_registered(self.callback):
                bpy.app.timers.unregister(self.callback)
        except Exception:
            pass
        self.remove_handle()
        self.unguard()

    def unguard(self):
        try:
            if self.guard in bpy.app.handlers.load_pre:
                bpy.app.handlers.load_pre.remove(self.guard)
        except Exception:
            pass

    def tick(self):
        """One step of the run. Returns the seconds until the next, or None to stop."""
        if self.dead:
            return None
        try:
            now = self.clock()
            if not self.stage.settle(now, FULL_VIEWPORT):
                self.redraw(None)
                return TICK
            with self.stage.override() as found:
                if found is None:
                    self.lost += 1
                    if self.lost > 300:
                        raise ShowError("There is no 3D viewport in this window.")
                    return TICK
                self.lost = 0
                if now - self.last_keep > 0.5:
                    self.stage.keep(found)
                    self.last_keep = now
                more = self.player.step(now)
            self.redraw(None)        # found again: the step may have swapped the screen
            if more:
                return TICK
            self.finish()
            return None
        except Exception as exc:
            self.fail(exc)
            return None

    def redraw(self, found):
        found = found or self.stage.find()
        if found is not None:
            area = found[1]
            area.tag_redraw()
            for region in area.regions:
                region.tag_redraw()

    def view_state(self, now):
        left = self.count_until - now
        return {"chip": self.player.chip if CAPTIONS else "",
                "line": self.player.line if CAPTIONS else "",
                "changed": self.player.changed, "bar_changed": self.player.bar_changed,
                "error": self.error,
                "count": int(math.ceil(left)) if left > 0 else 0,
                "note": " ".join(self.notes)}

    def draw(self):
        """The draw handler: called by Blender on every redraw of a 3D viewport."""
        if not self.drawing_ok or self.dead and not self.error:
            return
        context = bpy.context
        area, region = context.area, context.region
        if area is None or region is None or region.type != "WINDOW":
            return
        if self.space_ptr is not None and context.space_data is not None \
                and context.space_data.as_pointer() != self.space_ptr:
            return
        painter = None
        try:
            metrics = self.stage.metrics(area)
            painter = self.painter_class()
            draw_overlay(painter, self.view_state(self.clock()), metrics,
                         caption_scale(metrics), self.clock())
        except Exception:
            # Once, not on every redraw: a captions problem is no reason to
            # bury the console, or to stop the demo.
            self.drawing_ok = False
            traceback.print_exc()
            print("CopyThat promo: captions are off for this run.")
        finally:
            if painter is not None:
                painter.finish()

    # --- ending

    def finish(self):
        print("CopyThat promo: finished.")
        self.cancel()

    def fail(self, exc):
        traceback.print_exc()
        self.error = "Stopped: " + short_error(exc)
        print("CopyThat promo:", self.error)
        self.cancel(keep_error_for=10.0)

    def cancel(self, keep_error_for=0.0):
        """End the run: no more ticks, playback stopped, the window out of the
        full view, the captions gone (after a few seconds when there is an
        error to read). Then, a moment later, leave() gives the user's screen
        back."""
        if self.dead:
            return
        self.dead = True
        self.unguard()
        try:
            if bpy.app.timers.is_registered(self.callback):
                bpy.app.timers.unregister(self.callback)
        except Exception:
            pass
        # Left in the namespace until leave() has run, so that a rerun in
        # the meantime still finds this run and puts the screen back first.
        if self.stage is not None:
            try:
                with self.stage.override():
                    window = self.stage.window()
                    if window is not None and window.screen.is_animation_playing:
                        bpy.ops.screen.animation_cancel(restore_frame=False)
                    # Stopped while bending a curve: leave edit mode, or the
                    # next thing the user clicks behaves oddly.
                    active = bpy.context.object
                    if active is not None and active.mode != "OBJECT":
                        bpy.ops.object.mode_set(mode="OBJECT")
                self.stage.restore_full()
            except Exception:
                traceback.print_exc()
            # Late: the full view has to be left before the tab can change,
            # and an error is left on screen to be read first.
            try:
                bpy.app.timers.register(self.leave_callback,
                                        first_interval=max(0.25, keep_error_for),
                                        persistent=False)
            except Exception:
                self.leave()
        if keep_error_for > 0 and self.handle is not None:
            bpy.app.timers.register(self.remove_callback, first_interval=keep_error_for,
                                    persistent=False)
        else:
            self.remove_handle()
        if self.stage is not None:
            self.redraw(None)

    def leave(self):
        """Give the user's own screen back: the viewport as it was, the scene
        and the tab the run started in. Once only."""
        if bpy.app.driver_namespace.get(STATE_KEY) is self:
            del bpy.app.driver_namespace[STATE_KEY]
        if self.left or self.stage is None:
            return None
        self.left = True
        try:
            if RESTORE_VIEW_AT_END:
                self.stage.restore_look()
            if RETURN_TO_START_SCENE:
                self.stage.back_to_start()
                self.stage.back_to_workspace()
        except Exception:
            traceback.print_exc()
        self.redraw(None)
        return None

    def remove_handle(self):
        if self.handle is not None:
            try:
                bpy.types.SpaceView3D.draw_handler_remove(self.handle, "WINDOW")
            except Exception:
                pass
            self.handle = None
        self.error = ""
        return None


def main():
    previous = bpy.app.driver_namespace.get(STATE_KEY)
    if previous is not None:
        try:
            previous.cancel()
            # At once, not on its timer: this run is about to note where the
            # user's screen is, and it has to be theirs by then.
            previous.leave()
            print("CopyThat promo: the earlier run was stopped.")
        except Exception:
            traceback.print_exc()
        bpy.app.driver_namespace.pop(STATE_KEY, None)
    if STOP:
        print("CopyThat promo: stopped (STOP is True).")
        return None
    show = Show()
    try:
        show.start()
    except ShowError as exc:
        tell(str(exc))
    except Exception:
        traceback.print_exc()
        tell("Something went wrong while starting. The details are in the system console.")
        show.cancel()
    return show


# Headless (bpy as a Python module, or blender -b) has no window to draw in and
# no timers to run: the tests import this file and drive it themselves.
if not bpy.app.background:
    main()
