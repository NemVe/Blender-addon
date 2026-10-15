"""Build the flower, rig it with CopyThat headless, and check the rig.

    /home/user/Blender-addon/.venv/bin/python check_flower.py [--sweep [--step N]] [--frames N]

Asserts that
  * Build reports no cramped driver and every driver is a simple expression;
  * at Play 0 every part is within 1e-3 of its Before, the bud is closed;
  * at Play 1 every outer petal has opened by its own leaning angle (75
    degrees) from its own place, every inner petal by 45, the core has risen
    and turned, the leaves are in their open poses;
  * the leaves' segments stay joined at their joints at Play 0, 0.5 and 1;
  * no two parts cut through each other at Play 0 and 1.
With --sweep it also steps the whole bloom and lists any overlap or joint
that comes apart on the way.
"""

import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ADDON = os.environ.get("COPYTHAT_ADDON", "/home/user/Blender-addon")
sys.path.insert(0, HERE)
sys.path.insert(0, ADDON)

import bpy  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402
from mathutils.bvhtree import BVHTree  # noqa: E402

import flower  # noqa: E402
import rigmoves  # noqa: E402
import run_headless  # noqa: E402

TOLERANCE = 1e-3


def world_points(obj):
    """Where the mesh really is, after the rig has deformed it."""
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    points = [evaluated.matrix_world @ v.co for v in mesh.vertices]
    evaluated.to_mesh_clear()
    return points


def rest_points(obj):
    return [obj.matrix_world @ v.co for v in obj.data.vertices]


def drift(obj, expected):
    return max((a - b).length for a, b in zip(world_points(obj), expected))


def bvh_of(obj):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    verts = [evaluated.matrix_world @ v.co for v in mesh.vertices]
    polys = [tuple(p.vertices) for p in mesh.polygons]
    evaluated.to_mesh_clear()
    return BVHTree.FromPolygons(verts, polys, epsilon=0.0)


def nearest_two(obj, point):
    """The two skin vertices of a leaf segment on its centre line that are
    nearest to a point in its own frame (the middle of them is the joint)."""
    verts = obj.data.vertices
    centre = [i for i, v in enumerate(verts) if abs(v.co.y) < 1e-6]
    centre.sort(key=lambda i: (verts[i].co - point).length)
    return centre[:2]


def joints_gap(leaf, spec):
    """The worst distance between a segment's far end and the next one's
    joint, measured on the evaluated meshes (the middle of the two skins)."""
    worst = 0.0
    ends = flower.leaf_ends(spec)
    for a, b, end in zip(leaf, leaf[1:], ends):
        pa, pb = world_points(a), world_points(b)
        ends_a = [pa[i] for i in nearest_two(a, end)]
        ends_b = [pb[i] for i in nearest_two(b, Vector((0.0, 0.0, 0.0)))]
        ca = sum(ends_a, ends_a[0] * 0.0) / len(ends_a)
        cb = sum(ends_b, ends_b[0] * 0.0) / len(ends_b)
        worst = max(worst, (ca - cb).length)
    return worst


def all_joints_gap(parts):
    return max(joints_gap(leaf, spec) for leaf, spec in zip(parts["leaves"], flower.leaf_layout()))


def overlaps(objects, skip=()):
    """Pairs of objects whose evaluated meshes cut through each other."""
    trees = {obj.name: bvh_of(obj) for obj in objects}
    found = []
    names = [o.name for o in objects]
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if (a, b) in skip or (b, a) in skip:
                continue
            hits = trees[a].overlap(trees[b])
            if hits:
                found.append((a, b, len(hits)))
    return found


def main():
    sweep = "--sweep" in sys.argv
    frames = 150
    if "--frames" in sys.argv:
        frames = int(sys.argv[sys.argv.index("--frames") + 1])

    bpy.ops.wm.read_factory_settings(use_empty=True)
    rigmoves.register()
    scene = bpy.context.scene
    parts = flower.build_flower(scene)
    bpy.context.view_layer.update()
    everything = [o for o in parts["all"] if o.type == "MESH"]
    before = {o.name: rest_points(o) for o in everything}
    home = {o.name: o.matrix_world.copy() for o in everything}
    local = {o.name: [v.co.copy() for v in o.data.vertices] for o in everything}

    reports = []
    run_headless.run(flower.flower_steps(parts, frames), after_call=lambda fn: reports.append(
        (fn.__name__, scene.rigmoves_rig.rigmoves.report if scene.rigmoves_rig else "")))
    rig = scene.rigmoves_rig
    move = rig.rigmoves.moves[0]
    failures = []

    def check(ok, text):
        print(("  ok   " if ok else "  FAIL ") + text)
        if not ok:
            failures.append(text)

    print("Build and drivers")
    build_report = dict(reports)["build"]
    print("  report:", build_report)
    check("too long" not in build_report and "cut short" not in build_report,
          "Build reports no cramped driver")
    check("not recorded" not in build_report and "animated by hand" not in build_report,
          "Build reports nothing else wrong")
    drivers = [d for d in rig.animation_data.drivers if "constraints[" in d.data_path]
    check(len(drivers) == len(move.parts), "{:d} drivers for {:d} parts".format(len(drivers), len(move.parts)))
    longest = max(len(d.driver.expression) for d in drivers)
    check(all(d.driver.is_valid and d.driver.is_simple_expression for d in drivers),
          "every driver is a valid simple expression (longest {:d} characters)".format(longest))
    check(longest < 256, "no driver reaches 256 characters")
    check(not [d for d in drivers if len(d.driver.expression) >= 256], "none cut at the limit")
    for p in ("Petal 2", "Inner 2", "Core", "Leaf A2"):
        print("   {:8s} start {:.3f} lead {:d}".format(p, move.parts[p].start, move.parts[p].lead))

    def at(share):
        frame = 1 + int(round(share * frames))
        scene.frame_set(frame)
        bpy.context.view_layer.update()

    def angle_about_y(obj, rest_local, now_world):
        """How far a petal has turned about its own Y, from its own place."""
        inverse = home[obj.name].inverted()
        tip = max(range(len(rest_local)), key=lambda i: rest_local[i].length)
        x0, z0 = rest_local[tip].x, rest_local[tip].z
        now = inverse @ now_world[tip]
        return math.degrees(math.atan2(now.x * z0 - now.z * x0, now.x * x0 + now.z * z0))

    print("Play 0: the bud is closed")
    at(0.0)
    check(abs(move.play) < 0.01, "the Play slider reads 0 (it is {:.2f})".format(move.play))
    worst = max(max((a - b).length for a, b in zip(world_points(o), before[o.name])) for o in everything)
    check(worst < TOLERANCE, "every part is within {:.1e} of its Before (worst {:.1e})".format(TOLERANCE, worst))
    leaf_worst = all_joints_gap(parts)
    check(leaf_worst < TOLERANCE, "leaf joints joined (worst gap {:.1e})".format(leaf_worst))
    closed_hits = overlaps(everything, skip=allowed_pairs(parts))
    check(not closed_hits, "no parts cut through each other when closed {:s}".format(str(closed_hits[:6])))

    print("Play 0.5")
    at(0.5)
    check(abs(move.play - 50.0) < 0.1, "the Play slider reads 50 (it is {:.2f})".format(move.play))
    mid_gap = all_joints_gap(parts)
    check(mid_gap < TOLERANCE, "leaf joints joined (worst gap {:.1e})".format(mid_gap))
    mid_angles = [angle_about_y(o, local[o.name], world_points(o)) for o in parts["outer"]]
    print("   outer petals at half: " + " ".join("{:5.1f}".format(a) for a in mid_angles))

    print("Play 1: open")
    at(1.0)
    check(abs(move.play - 100.0) < 0.1, "the Play slider reads 100 (it is {:.2f})".format(move.play))
    angles = []
    for o in parts["outer"]:
        angles.append(angle_about_y(o, local[o.name], world_points(o)))
    inner_angles = [angle_about_y(o, local[o.name], world_points(o)) for o in parts["inner"]]
    print("   outer petals open by: " + " ".join("{:6.2f}".format(a) for a in angles))
    print("   inner petals open by: " + " ".join("{:6.2f}".format(a) for a in inner_angles))
    check(all(abs(a - flower.OUTER_OPEN) < 0.1 for a in angles),
          "every outer petal opened by its own {:.0f} degrees from its own place".format(flower.OUTER_OPEN))
    for o in parts["outer"]:
        expected = [home[o.name] @ Matrix.Rotation(math.radians(flower.OUTER_OPEN), 4, "Y") @ c
                    for c in local[o.name]]
        err = drift(o, expected)
        check(err < TOLERANCE, "{:s} lands on its pose (error {:.1e})".format(o.name, err))
    check(all(abs(a - flower.INNER_OPEN) < 0.1 for a in inner_angles),
          "every inner petal opened by {:.0f} degrees".format(flower.INNER_OPEN))
    core = parts["core"]
    expected = [Matrix.Translation((0, 0, flower.CORE_RISE)) @ home[core.name]
                @ Matrix.Rotation(math.radians(flower.CORE_TURN), 4, "Z") @ c for c in local[core.name]]
    err = drift(core, expected)
    check(err < TOLERANCE, "the core rose {:.2f} and turned {:.0f} (error {:.1e})".format(
        flower.CORE_RISE, flower.CORE_TURN, err))
    leaf_err = 0.0
    for spec, chain in zip(flower.leaf_layout(), parts["leaves"]):
        for obj, pose in zip(chain, flower.leaf_poses(spec, "opened")):
            leaf_err = max(leaf_err, drift(obj, [pose @ c for c in local[obj.name]]))
    check(leaf_err < TOLERANCE, "the leaves are in their open poses (error {:.1e})".format(leaf_err))
    end_gap = all_joints_gap(parts)
    check(end_gap < TOLERANCE, "leaf joints joined (worst gap {:.1e})".format(end_gap))
    open_hits = overlaps(everything, skip=allowed_pairs(parts))
    check(not open_hits, "no parts cut through each other when open {:s}".format(str(open_hits[:6])))

    scene.frame_set(1 + frames + 30)
    bpy.context.view_layer.update()
    print("After the bloom: it holds")
    held = max(max((a - b).length for a, b in zip(world_points(o), [home[o.name] @ c for c in local[o.name]]))
               for o in parts["outer"][:1])
    check(held > 0.5, "the last pose is held past the end of the keys")

    if sweep:
        step = int(sys.argv[sys.argv.index("--step") + 1]) if "--step" in sys.argv else max(1, frames // 30)
        print("Sweep: every {:d}th frame of the bloom".format(step))
        bad = []
        for frame in range(1, frames + 2, step):
            scene.frame_set(frame)
            bpy.context.view_layer.update()
            hits = overlaps(everything, skip=allowed_pairs(parts))
            gap = all_joints_gap(parts)
            if hits or gap > TOLERANCE:
                bad.append(frame)
                print("   frame {:3d}: {:s} joint gap {:.1e}".format(frame, str(hits[:5]), gap))
        check(not bad, "no overlaps and no loose joints along the bloom (frames: {:s})".format(str(bad)))

    print()
    print("FAILED {:d}".format(len(failures)) if failures else "ALL CHECKS PASSED")
    return 1 if failures else 0


def allowed_pairs(parts):
    """Parts that touch on purpose: a leaf's neighbouring segments overlap at
    their joint, and the first segment is pinned on the stem."""
    skip = set()
    for chain in parts["leaves"]:
        skip.add((chain[0].name, parts["stem"].name))
        for a, b in zip(chain, chain[1:]):
            skip.add((a.name, b.name))
    return skip


if __name__ == "__main__":
    sys.exit(main())
