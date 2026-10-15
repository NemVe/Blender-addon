"""Do what FLOWER_STEPS.md says, to the bare .blend, and prove it blooms the same.

    /home/user/Blender-addon/.venv/bin/python replay_guide.py [--no-render] [--shortcut]

1. Builds the reference: the normal flower rigged by flower_steps(parts, 150),
   and records every part's evaluated mesh at frames 1, 38, 75, 112 and 151.
2. Opens the bare .blend with CopyThat registered and performs the guide's
   steps literally, in the guide's order: selections by select_set with the
   right object active; every pose typed into the Properties editor's fields,
   which is `rotation_euler.x` (degrees), `location.z` and `rotation_euler.z`
   on the objects as the Follows hang them; the same panel values; the same
   operators. The numbers are read from the guide's cheat sheet, so they
   cannot drift from the text. With --shortcut the rotations are made by the
   optional R X X instead, through Blender's own rotate operator.
3. Prints the largest difference, which must be under 1e-3.
4. Renders frame 120 from the replayed bare file (CPU, 16 samples, 50% size).
"""

import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROMO = os.path.dirname(HERE)
ADDON = os.environ.get("COPYTHAT_ADDON", "/home/user/Blender-addon")
sys.path.insert(0, os.path.join(PROMO, "flower"))
sys.path.insert(0, ADDON)

import bpy  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import flower  # noqa: E402
import rigmoves  # noqa: E402
import run_headless  # noqa: E402

BLEND = os.path.join(PROMO, "outbox", "CopyThat_flower_bare.blend")
GUIDE = os.path.join(PROMO, "outbox", "FLOWER_STEPS.md")
FRAMES = (1, 38, 75, 112, 151)
LIMIT = 1e-3
STILL = os.path.join(HERE, "test_frame_0120.png")


# ---------------------------------------------------------------------------
# the guide's cheat sheet

def cheat_sheet(path=GUIDE):
    """The tables under "## Cheat sheet", as {heading: [row cells]}."""
    with open(path, encoding="utf-8") as handle:
        lines = handle.read().splitlines()
    start = next(i for i, line in enumerate(lines) if line.strip() == "## Cheat sheet")
    tables, name = {}, None
    for line in lines[start + 1:]:
        if line.startswith("## "):
            break                                # the next section: not the cheat sheet
        if line.startswith("### "):
            name = line[4:].strip()
            tables[name] = []
        elif name and line.startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if set("".join(cells)) <= set("-: "):
                continue
            tables[name].append(cells)
    for name in tables:
        tables[name] = tables[name][1:]          # the header row
    return tables


def pose_rows(tables):
    """The Pose table as [(object, field, shut value, typed value)]."""
    return [(name, field, float(shut), float(value))
            for _number, name, field, shut, value in tables["Pose"]]


def pose_table_in_the_steps(path=GUIDE):
    """The same poses as step 3 gives them, before the cheat sheet:
    [(object, field, typed value)]. They must say what the cheat sheet says."""
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    steps = text[:text.index("## Cheat sheet")]
    return [(match.group(1), match.group(2).strip(), float(match.group(3)))
            for match in re.finditer(r"^\| \*\*([^*]+)\*\* \| ([^|]+) \| (-?[0-9.]+) \|", steps, re.M)]


# ---------------------------------------------------------------------------
# measuring

def world_points(obj):
    """Where the mesh really is, after the rig has deformed it."""
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    points = [tuple(evaluated.matrix_world @ v.co) for v in mesh.vertices]
    evaluated.to_mesh_clear()
    return points


def snapshot(scene, names, frames=FRAMES):
    out = {}
    for frame in frames:
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        out[frame] = {name: world_points(bpy.data.objects[name]) for name in names}
    return out


def difference(a, b):
    return max(math.dist(p, q) for p, q in zip(a, b))


# Bare name -> the flower_steps flower's name.
def names_of_reference():
    out = {"Core": "Core", "Stem": "Stem", "Pedestal": "Pedestal"}
    for k in range(8):
        out["Outer Leader" if not k else "Outer {:d}".format(k + 1)] = "Petal {:d}".format(k + 1)
    for k in range(6):
        out["Inner Leader" if not k else "Inner {:d}".format(k + 1)] = "Inner {:d}".format(k + 1)
    for leaf in "AB":
        for k in "123":
            out["Leaf {:s}{:s}".format(leaf, k)] = "Leaf {:s}{:s}".format(leaf, k)
    return out


def reference():
    """The normal flower rigged by flower_steps: the shut shape, and the
    bloom at each frame, by the bare file's names."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    parts = flower.build_flower(scene)
    bpy.context.view_layer.update()
    mapping = names_of_reference()
    shut = {bare: world_points(bpy.data.objects[ref]) for bare, ref in mapping.items()}
    run_headless.run(flower.flower_steps(parts, 150), scene=scene)
    bloom = {}
    for frame in FRAMES:
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        bloom[frame] = {bare: world_points(bpy.data.objects[ref]) for bare, ref in mapping.items()}
    return shut, bloom


# ---------------------------------------------------------------------------
# what a user does

def select(*objects, active=None):
    """Click the objects in the Outliner: these, and only these, selected."""
    layer = bpy.context.view_layer
    for obj in layer.objects:
        obj.select_set(False)
    for obj in objects:
        obj.select_set(True)
    layer.objects.active = active or objects[0]


def local_turn_expected(obj, degrees):
    return obj.matrix_world @ Matrix.Rotation(math.radians(degrees), 4, "X")


def same_matrix(a, b, tolerance=1e-5):
    return max(abs(x - y) for ra, rb in zip(a, b) for x, y in zip(ra, rb)) < tolerance


def type_field(obj, field, shut, value, shortcut=False):
    """Click the part, then type into a field of the Properties editor >
    Object tab > Transform (or, with `shortcut`, use R X X over the 3D view).
    Checks what a user relies on: the field starts at the number the guide
    says, the part's rotation is XYZ Euler at scale 1 (nothing can shear), and
    Rotation X turns the part about its own local X, hanging from another
    part or not."""
    select(obj)
    assert obj.rotation_mode == "XYZ", obj.name
    assert tuple(obj.scale) == (1.0, 1.0, 1.0), obj.name
    now = {"Rotation X": math.degrees(obj.rotation_euler.x), "Location Z": obj.location.z,
           "Rotation Z": math.degrees(obj.rotation_euler.z)}[field]
    assert abs(now - shut) < 1e-6, "{} {} is {} not {}".format(obj.name, field, now, shut)
    bpy.context.view_layer.update()
    before = obj.matrix_world.copy()
    if field == "Rotation X":
        if shortcut:
            assert bpy.ops.transform.rotate(value=math.radians(value), orient_axis="X",
                                            orient_type="LOCAL",
                                            constraint_axis=(True, False, False)) == {"FINISHED"}
        else:
            obj.rotation_euler.x = math.radians(value)
        bpy.context.view_layer.update()
        assert same_matrix(obj.matrix_world, before @ Matrix.Rotation(math.radians(value), 4, "X")), \
            "{} did not turn about its own X".format(obj.name)
    elif field == "Location Z":
        obj.location.z = value
        bpy.context.view_layer.update()
        assert same_matrix(obj.matrix_world, Matrix.Translation((0, 0, value - shut)) @ before)
    elif field == "Rotation Z":
        obj.rotation_euler.z = math.radians(value)
        bpy.context.view_layer.update()
        assert same_matrix(obj.matrix_world, before @ Matrix.Rotation(math.radians(value - shut), 4, "Z"))
    else:
        raise ValueError(field)


def rig():
    return bpy.context.scene.rigmoves_rig


def replay(tables, log, shortcut=False):
    scene = bpy.context.scene
    objects = bpy.data.objects
    leader, inner_leader = objects["Outer Leader"], objects["Inner Leader"]
    leaves = [objects["Leaf {:s}{:d}".format(side, k)] for side in "AB" for k in (1, 2, 3)]

    # 1. Select the nine parts and press New Move.
    select(leader, inner_leader, objects["Core"], *leaves, active=leader)
    assert len(bpy.context.selected_objects) == 9
    assert bpy.ops.rigmoves.new_move() == {"FINISHED"}
    move = rig().rigmoves.moves[0]
    log("1 New Move", rig().rigmoves.report)

    # 2. Follows: the leaves hang from each other.
    for part, follows in tables["Follows"]:
        move.parts[part].follows = follows
        assert move.parts[part].follows == follows, (part, follows)

    # 3. Pose the flower open, one field at a time.
    for name, field, shut, value in pose_rows(tables):
        type_field(objects[name], field, shut, value, shortcut)

    # 4. Record After.
    assert bpy.ops.rigmoves.record(index=0, which="AFTER") == {"FINISHED"}
    log("4 Record After", rig().rigmoves.report)

    # 5. Ride Along: the riders selected, the leader selected last (active).
    riders = [objects["Outer {:d}".format(k)] for k in range(2, 9)]
    select(*riders, leader, active=leader)
    assert bpy.ops.rigmoves.ride_along(index=0, leader=leader.name, rig_name=rig().name) == {"FINISHED"}
    log("5 Ride Along (outer)", rig().rigmoves.report)
    riders = [objects["Inner {:d}".format(k)] for k in range(2, 7)]
    select(*riders, inner_leader, active=inner_leader)
    assert bpy.ops.rigmoves.ride_along(index=0, leader=inner_leader.name,
                                       rig_name=rig().name) == {"FINISHED"}
    log("5 Ride Along (inner)", rig().rigmoves.report)

    # 6. Lead for every rider.
    for name, lead in tables["Lead"]:
        move.parts[name].lead = int(lead)

    # 7. Timing: the Delays.
    for name, delay in tables["Delay"]:
        move.parts[name].start = float(delay)

    # 8. Ease, 9. Build Sliders.
    other = dict(tables["Other"])
    move.ease = {"Smooth": "SMOOTH", "Even speed": "LINEAR"}[other["Ease"]]
    select(leader)
    assert bpy.ops.rigmoves.build() == {"FINISHED"}
    log("9 Build Sliders", rig().rigmoves.report)

    # 10. Frame 1, Frames 150, Animate.
    scene.frame_set(1)
    move.play_frames = int(other["Frames"])
    assert bpy.ops.rigmoves.animate(index=0) == {"FINISHED"}
    log("10 Animate", rig().rigmoves.report)
    scene.frame_set(1)
    return move


def main():
    render = "--no-render" not in sys.argv
    shortcut = "--shortcut" in sys.argv
    rigmoves.register()
    tables = cheat_sheet()
    print("cheat sheet:", {k: len(v) for k, v in tables.items()})
    in_steps = pose_table_in_the_steps()
    in_sheet = [(name, field, value) for name, field, _shut, value in pose_rows(tables)]
    assert in_steps == in_sheet, "step 3 and the cheat sheet disagree:\n{}\n{}".format(in_steps, in_sheet)
    print("step 3 and the cheat sheet agree on all {:d} poses".format(len(in_sheet)))

    shut, bloom = reference()
    print("reference built and rigged with flower_steps(parts, 150)")

    bpy.ops.wm.open_mainfile(filepath=BLEND)
    scene = bpy.context.scene
    names = sorted(names_of_reference())
    assert not any(hasattr(o, "rigmoves") and len(o.rigmoves.moves) for o in bpy.data.objects
                   if o.type == "ARMATURE"), "the bare file has CopyThat data"
    assert not [o for o in bpy.data.objects if o.type == "ARMATURE" or o.modifiers or o.constraints], \
        "the bare file has a rig, modifiers or constraints"
    bpy.context.view_layer.update()
    start = snapshot(scene, names, frames=(1,))[1]
    gap = max(difference(start[n], shut[n]) for n in names)
    print("bare file against the normal flower, shut: largest difference {:.2e}".format(gap))

    notes = []
    replay(tables, lambda step, text: notes.append((step, text)), shortcut)
    for step, text in notes:
        print("  {:22s} {:s}".format(step, text))

    got = snapshot(scene, names)
    worst, where = 0.0, None
    for frame in FRAMES:
        top = max((difference(got[frame][n], bloom[frame][n]), n) for n in names)
        print("frame {:3d}: largest difference {:.2e}  ({:s})".format(frame, top[0], top[1]))
        if top[0] > worst:
            worst, where = top[0], (frame, top[1])
    print("LARGEST DIFFERENCE {:.2e} at frame {:d}, {:s}   (limit {:.0e})".format(
        worst, where[0], where[1], LIMIT))
    ok = worst < LIMIT and gap < 1e-5
    print("REPLAY MATCHES" if ok else "REPLAY DIFFERS")

    # How near the camera's focus is to the real core, at the keyed frames.
    core = bpy.data.objects["Core"]
    camera = scene.camera
    off = 0.0
    for frame in (1, 56, 101, 126, 151):
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        top = sorted((Vector(p) for p in world_points(core)), key=lambda p: -p.z)[:200]
        middle = sum(top, top[0] * 0.0) / len(top)
        want = (middle - camera.matrix_world.translation).length
        off = max(off, abs(want - camera.data.dof.focus_distance))
    print("camera focus against the evaluated core: largest difference {:.3f} m".format(off))

    if render:
        scene.frame_set(120)
        cycles = scene.cycles
        cycles.device, cycles.samples = "CPU", 16
        scene.render.resolution_percentage = 50
        try:
            scene.render.image_settings.media_type = "IMAGE"
        except (AttributeError, TypeError):
            pass
        scene.render.image_settings.file_format = "PNG"
        scene.render.filepath = STILL
        bpy.ops.render.render(write_still=True)
        print("rendered frame 120 to", STILL)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
