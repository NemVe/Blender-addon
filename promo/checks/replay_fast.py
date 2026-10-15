"""Do what FLOWER_FAST.md says, to the fast .blend, with CopyThat 0.17.1, and prove it.

    /home/user/Blender-addon/.venv/bin/python replay_fast.py [--no-render] [--no-sweep]

The repo's CopyThat is registered (sys.path.insert(0, ADDON)). The steps are
done literally, in the guide's order: selections by select_set with the right
object active, as a click and Ctrl+clicks in the Outliner leave them; fields
typed as the guide says (rotation_euler, location); the operators Make Chain,
Ring, Spread, Record, Build and Animate called with the dialog properties set
as the guide says and the rest left at the dialog's defaults. The numbers are
read from the guide's cheat sheet, so they cannot drift from the text.

Then it checks:
  * Build reports success and no driver is cramped;
  * Play 0: every part on its Before;
  * Play 1 (and frames 38, 75, 112): the 8 outer and 6 inner petals, the core
    and Leaf 1-3 against flower_steps(parts, 150) on the normal flower;
  * the second leaf (the ring copy) is Leaf 1 turned 180 degrees about Z, at
    Play 0, 0.5 and 1;
  * the wave is symmetric, the leaf joints are closed, and no parts overlap on
    any of the 151 frames.
"""

import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROMO = os.path.dirname(HERE)
ADDON = os.environ.get("COPYTHAT_ADDON", "/home/user/Blender-addon")
sys.path.insert(0, os.path.join(PROMO, "flower"))
sys.path.insert(0, HERE)
sys.path.insert(0, ADDON)

import bpy  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402
from mathutils.bvhtree import BVHTree  # noqa: E402

import flower  # noqa: E402
import replay_guide as old  # noqa: E402
import rigmoves  # noqa: E402
import run_headless  # noqa: E402

BLEND = os.path.join(PROMO, "outbox", "CopyThat_flower_fast.blend")
GUIDE = os.path.join(PROMO, "outbox", "FLOWER_FAST.md")
STILL = os.path.join(HERE, "test_frame_fast_0120.png")
FRAMES = (1, 38, 75, 112, 151)
LIMIT = 1e-3

CENTRES = {"3D Cursor": "CURSOR", "World Origin": "ORIGIN"}
AXES = {"World Z": "Z", "3D Cursor's Z": "CURSOR_Z", "World X": "X", "World Y": "Y"}
ORDERS = {"Around a ring": "AROUND", "By distance": "DISTANCE", "Along an axis": "AXIS",
          "Down a chain": "CHAIN", "Random": "RANDOM"}

DONE = {"clicks": 0, "typed": 0, "presses": 0}


# ---------------------------------------------------------------------------
# the guide

def cheat_sheet():
    tables = old.cheat_sheet(GUIDE)
    return tables


def old_counts():
    """The same count for FLOWER_STEPS.md, the long way, from its own tables:
    object clicks, values typed or chosen, buttons pressed."""
    sheet = old.cheat_sheet(os.path.join(PROMO, "outbox", "FLOWER_STEPS.md"))
    poses = sheet["Pose"]
    clicks = 9 + len({row[1] for row in poses}) + 8 + 6          # New Move, each part posed, two Ride Alongs
    typed = (len(sheet["Follows"]) + len(poses) + len(sheet["Lead"])
             + len([r for r in sheet["Delay"] if float(r[1]) != 0.0]) + 2)   # + Ease, Frames
    presses = 6 + 3                       # New Move, Record, 2 x Ride Along, Build, Animate; Numpad 7, H, Alt+H
    return clicks, typed, presses


def names(text):
    return [n.strip() for n in text.split(",") if n.strip()]


# ---------------------------------------------------------------------------
# the flower_steps reference, by the fast file's names

def reference_names():
    out = {"Core": "Core", "Stem": "Stem", "Pedestal": "Pedestal",
           "Outer Leader": "Petal 1", "Inner Leader": "Inner 1",
           "Leaf 1": "Leaf A1", "Leaf 2": "Leaf A2", "Leaf 3": "Leaf A3"}
    for k in range(2, 9):
        out["Outer Leader {:d}".format(k)] = "Petal {:d}".format(k)
    for k in range(2, 7):
        out["Inner Leader {:d}".format(k)] = "Inner {:d}".format(k)
    return out


def reference():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    parts = flower.build_flower(scene)
    bpy.context.view_layer.update()
    mapping = reference_names()
    shut = {fast: old.world_points(bpy.data.objects[ref]) for fast, ref in mapping.items()}
    run_headless.run(flower.flower_steps(parts, 150), scene=scene)
    bloom = {}
    for frame in FRAMES:
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        bloom[frame] = {fast: old.world_points(bpy.data.objects[ref]) for fast, ref in mapping.items()}
    return shut, bloom


# ---------------------------------------------------------------------------
# what a user does

def select(*objects, active=None):
    DONE["clicks"] += len(objects)
    old.select(*objects, active=active)


def press(operator, **properties):
    """Press a panel button, or OK in a dialog whose fields were set: only the
    fields that differ from the dialog's own defaults were touched by the user."""
    DONE["presses"] += 1
    rna = operator.get_rna_type()
    for key, value in properties.items():
        if key == "index":
            continue
        default = rna.properties[key].default
        if value != default:
            DONE["typed"] += 1
    result = operator(**properties)
    assert result == {"FINISHED"}, (rna.identifier, properties, result)
    return result


def rig():
    return bpy.context.scene.rigmoves_rig


def report():
    return rig().rigmoves.report


def replay(tables, log):
    scene = bpy.context.scene
    objects = bpy.data.objects
    parts6 = [objects[n] for n in ("Outer Leader", "Inner Leader", "Core", "Leaf 1", "Leaf 2", "Leaf 3")]

    # 1. Select the six parts and press New Move.
    select(*parts6, active=objects["Outer Leader"])
    press(bpy.ops.rigmoves.new_move)
    move = rig().rigmoves.moves[0]
    log("1 New Move", report())

    # 2. Make Chain: select the three leaf parts, Leaf 1 clicked last (active),
    # and press it once.
    assert len(tables["Make Chain"]) == 1, tables["Make Chain"]
    for _press, chosen, active in tables["Make Chain"]:
        select(*[objects[n] for n in names(chosen)], active=objects[active])
        press(bpy.ops.rigmoves.make_chain, index=0)
        log("2 Make Chain", report())
    assert move.parts["Leaf 2"].follows == "Leaf 1" and move.parts["Leaf 3"].follows == "Leaf 2", \
        {p.name: p.follows for p in move.parts}

    # 3. Pose the flower open, one field at a time: click the part (once for
    # the core's two fields), then type.
    last = None
    for name, field, shut, value in old.pose_rows(tables):
        if name != last:
            DONE["clicks"] += 1
        last = name
        DONE["typed"] += 1
        old.type_field(objects[name], field, shut, value)

    # 4. Record After.
    press(bpy.ops.rigmoves.record, index=0, which="AFTER")
    log("4 Record After", report())

    # 5. Ring: click the part, press Ring..., fill in the dialog, OK.
    copies = {}
    for name, count, centre, about, linked, lead_first, lead_last in tables["Ring"]:
        select(objects[name])
        before = {o.name for o in objects}
        press(bpy.ops.rigmoves.ring, index=0, count=int(count), center=CENTRES[centre],
              axis=AXES[about], linked=(linked.lower() == "on"),
              lead_first=int(lead_first), lead_last=int(lead_last))
        copies[name] = sorted(o.name for o in objects if o.name not in before)
        log("5 Ring " + name, report())

    # 6. Delays: select the leaf, Spread... on Timing, then type the other two.
    for order, only, first, last, chosen in tables["Spread"]:
        select(*[objects[n] for n in names(chosen)])
        press(bpy.ops.rigmoves.spread, index=0, what="DELAY", order=ORDERS[order],
              only_selected=(only.lower() == "on"), first=float(first), last=float(last))
        log("6 Spread Delays", report())
    for name, delay in tables["Delay"]:
        DONE["typed"] += 1
        move.parts[name].start = float(delay)

    # 7. Ease, Build Sliders.
    other = dict(tables["Other"])
    DONE["typed"] += 1
    move.ease = {"Smooth": "SMOOTH", "Even speed": "LINEAR"}[other["Ease"]]
    select(objects["Outer Leader"])
    press(bpy.ops.rigmoves.build)
    log("7 Build Sliders", report())

    # 8. Frame 1, Frames 150, Animate.
    scene.frame_set(1)
    DONE["typed"] += 1
    move.play_frames = int(other["Frames"])
    press(bpy.ops.rigmoves.animate, index=0)
    log("8 Animate", report())
    scene.frame_set(1)
    return move, copies


# ---------------------------------------------------------------------------
# checks

def rest_points(obj):
    return [tuple(obj.matrix_world @ v.co) for v in obj.data.vertices]


def angle_about_x(obj, home, local, now_world):
    """How far a part has turned about its own X (its hinge), from its place."""
    inverse = home.inverted()
    tip = max(range(len(local)), key=lambda i: local[i].length)
    y0, z0 = local[tip].y, local[tip].z
    now = inverse @ Vector(now_world[tip])
    return math.degrees(math.atan2(y0 * now.z - z0 * now.y, y0 * now.y + z0 * now.z))


def bvh_of(obj):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    verts = [evaluated.matrix_world @ v.co for v in mesh.vertices]
    polys = [tuple(p.vertices) for p in mesh.polygons]
    evaluated.to_mesh_clear()
    return BVHTree.FromPolygons(verts, polys, epsilon=0.0)


def joint_ends(leaf):
    """For each joint of a leaf (segment i to segment i+1), the indices of the
    two skin vertices nearest the joint on each side, found on the shut mesh in
    the world: the end of segment i, and the start of segment i+1."""
    pairs = []
    for a, b in zip(leaf, leaf[1:]):
        joint = Vector(b.matrix_world.translation)
        ends = []
        for obj in (a, b):
            points = rest_points(obj)
            order = sorted(range(len(points)), key=lambda i: (Vector(points[i]) - joint).length)
            ends.append(order[:2])
        pairs.append((a, ends[0], b, ends[1]))
    return pairs


def joints_gap(pairs):
    worst = 0.0
    for a, ia, b, ib in pairs:
        pa, pb = old.world_points(a), old.world_points(b)
        ca = sum((Vector(pa[i]) for i in ia), Vector()) / len(ia)
        cb = sum((Vector(pb[i]) for i in ib), Vector()) / len(ib)
        worst = max(worst, (ca - cb).length)
    return worst


def main():
    render = "--no-render" not in sys.argv
    sweep = "--no-sweep" not in sys.argv
    rigmoves.register()
    version = rigmoves.bl_info["version"]
    print("CopyThat", ".".join(str(v) for v in version))
    assert version >= (0, 17, 1)
    shown = ".".join(str(v) for v in version[:3])
    with open(GUIDE, encoding="utf-8") as handle:
        guide_text = handle.read()
    flat_text = " ".join(guide_text.split())
    assert "Version 0.17.1" in flat_text and "CopyThat-0.17.1.zip" in flat_text and shown == "0.17.1", \
        "the guide names a version other than the add-on's {}".format(shown)
    tables = cheat_sheet()
    print("cheat sheet:", {k: len(v) for k, v in tables.items()})
    in_steps = old.pose_table_in_the_steps(GUIDE)
    in_sheet = [(name, field, value) for name, field, _shut, value in old.pose_rows(tables)]
    assert in_steps == in_sheet, "step 3 and the cheat sheet disagree:\n{}\n{}".format(in_steps, in_sheet)
    print("step 3 and the cheat sheet agree on all {:d} poses".format(len(in_sheet)))

    shut, bloom = reference()
    print("reference built and rigged with flower_steps(parts, 150)")

    bpy.ops.wm.open_mainfile(filepath=BLEND)
    scene = bpy.context.scene
    objects = bpy.data.objects
    assert not [o for o in objects if o.type == "ARMATURE" or o.modifiers or o.constraints]
    flowers = [o for o in objects if o.type == "MESH" and o.name != "Cyclorama"]
    assert sorted(o.name for o in flowers) == [
        "Core", "Inner Leader", "Leaf 1", "Leaf 2", "Leaf 3", "Outer Leader", "Pedestal", "Stem"]
    bpy.context.view_layer.update()
    first = {o.name: rest_points(o) for o in flowers}
    mapping = reference_names()
    gap = max(old.difference(first[n], shut[n]) for n in first)
    print("fast file against the normal flower, shut: largest difference {:.2e}".format(gap))

    notes = []
    move, copies = replay(tables, lambda step, text: notes.append((step, text)))
    for step, text in notes:
        print("  {:22s} {:s}".format(step, text))
    print("this guide asks for {:d} object clicks, {:d} values typed or chosen, {:d} buttons pressed = {:d}"
          .format(DONE["clicks"], DONE["typed"], DONE["presses"], sum(DONE.values())))
    before = old_counts()
    print("FLOWER_STEPS.md, the long way: {:d} object clicks, {:d} values, {:d} buttons = {:d}"
          .format(*before, sum(before)))
    failures = []

    def check(ok, text):
        print(("  ok   " if ok else "  FAIL ") + text)
        if not ok:
            failures.append(text)

    # What the Ring made: where each copy stands, and its name.
    print("copies:", {k: v for k, v in copies.items()})
    want_outer = ["Outer Leader {:d}".format(k) for k in range(2, 9)]
    check(copies["Outer Leader"] == want_outer, "Outer Leader made " + ", ".join(copies["Outer Leader"]))
    check(copies["Inner Leader"] == ["Inner Leader {:d}".format(k) for k in range(2, 7)],
          "Inner Leader made " + ", ".join(copies["Inner Leader"]))
    check(copies["Leaf 1"] == ["Leaf 1 2", "Leaf 2 2", "Leaf 3 2"],
          "Leaf 1 made " + ", ".join(copies["Leaf 1"]))

    chain = dict(notes)["2 Make Chain"]
    check(chain.startswith("Chain: Leaf 1 > Leaf 2 > Leaf 3"), "one Make Chain press: " + chain)
    check({p.name: p.follows for p in move.parts if p.follows} == {"Leaf 2": "Leaf 1", "Leaf 3": "Leaf 2"},
          "Leaf 2 follows Leaf 1 and Leaf 3 follows Leaf 2, nothing else follows")

    # Every report the steps quote ("the report "..."") is what the add-on said.
    steps = " ".join(guide_text[:guide_text.index("## Cheat sheet")].split())
    said = [" ".join(text.split()) for _step, text in notes]
    quoted = re.findall(r'[Rr]eport[^"]{0,25}"([^"]+)"', steps)
    print("reports quoted in the steps:", len(quoted))
    for quote in quoted:
        check(any(quote in text for text in said), "the add-on said: " + quote)
    check(len(quoted) >= 9, "the steps quote the reports of New Move, Make Chain, Record After, "
          "three Rings, Spread, Build and Animate ({:d} found)".format(len(quoted)))

    print("Build and drivers")
    build_report = dict(notes)["7 Build Sliders"]
    check("too long" not in build_report and "cut short" not in build_report,
          "Build reports no cramped driver")
    check("not recorded" not in build_report and "animated by hand" not in build_report,
          "Build reports nothing else wrong")
    check(build_report.startswith("21 part(s) on 1 slider(s)"), "21 parts on 1 slider: " + build_report)
    drivers = [d for d in rig().animation_data.drivers if "constraints[" in d.data_path]
    longest = max(len(d.driver.expression) for d in drivers)
    check(len(drivers) == 21 and all(d.driver.is_valid and d.driver.is_simple_expression for d in drivers)
          and longest < 256, "21 valid simple drivers, longest {:d} characters".format(longest))
    print("   Leads:", {p.name: p.lead for p in move.parts if p.leader and p.name.startswith(("Outer", "Inner"))})
    print("   Delays:", {p.name: round(p.start, 4) for p in move.parts if not p.leader})

    mesh_objects = [o for o in objects if o.type == "MESH" and o.name != "Cyclorama"]
    everything = sorted(o.name for o in mesh_objects)
    home = {o.name: o.matrix_world.copy() for o in mesh_objects}
    local = {o.name: [v.co.copy() for v in o.data.vertices] for o in mesh_objects}
    petals = ["Outer Leader"] + want_outer
    inners = ["Inner Leader"] + ["Inner Leader {:d}".format(k) for k in range(2, 7)]
    leaf1 = ["Leaf 1", "Leaf 2", "Leaf 3"]
    leaf2 = ["Leaf 1 2", "Leaf 2 2", "Leaf 3 2"]

    # Everything on its Before at Play 0: the shut shape of each part.
    rest = {n: first[n] for n in first}
    for name in copies["Outer Leader"] + copies["Inner Leader"] + copies["Leaf 1"]:
        rest[name] = rest_points(objects[name])           # a copy stands shut where it was made
    scene.frame_set(1)
    bpy.context.view_layer.update()
    print("Play 0")
    worst = max(old.difference(old.world_points(objects[n]), rest[n]) for n in rest)
    check(worst < LIMIT, "every part is within {:.0e} of its Before (worst {:.1e})".format(LIMIT, worst))

    mapped = [n for n in mapping if n in objects]
    print("Against flower_steps(parts, 150) on the normal flower")
    for frame in FRAMES:
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        got = {n: old.world_points(objects[n]) for n in mapped}
        biggest = max(((old.difference(got[n], bloom[frame][n]), n) for n in petals + inners + ["Core"]
                       if n in got))
        leaves = max(((old.difference(got[n], bloom[frame][n]), n) for n in leaf1))
        print("   frame {:3d}: petals and core {:.2e} ({:s});  Leaf 1-3 {:.2e} ({:s})".format(
            frame, biggest[0], biggest[1], leaves[0], leaves[1]))
        if frame == 151:
            check(biggest[0] < LIMIT, "at Play 1 the 8 outer and 6 inner petals and the core match to {:.1e}"
                  .format(biggest[0]))
            check(leaves[0] < LIMIT, "at Play 1 Leaf 1-3 match the reference leaf to {:.1e}".format(leaves[0]))
        if frame == 1:
            check(max(biggest[0], leaves[0]) < LIMIT, "at Play 0 they match the shut flower")

    print("The second leaf is Leaf 1 turned 180 degrees about Z")
    turn = Matrix.Rotation(math.pi, 4, "Z")
    for frame in (1, 76, 151):
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        worst = 0.0
        for a, b in zip(leaf1, leaf2):
            pa, pb = old.world_points(objects[a]), old.world_points(objects[b])
            worst = max(worst, max((turn @ Vector(p) - Vector(q)).length for p, q in zip(pa, pb)))
        check(worst < LIMIT, "frame {:3d} (Play {:.1f}): worst {:.1e}".format(frame, (frame - 1) / 150.0, worst))

    print("The wave")
    symmetric = True
    for frame in (20, 38, 75, 112):
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        now = {n: old.world_points(objects[n]) for n in petals + inners}
        outer_angles = [angle_about_x(objects[n], home[n], local[n], now[n]) for n in petals]
        inner_angles = [angle_about_x(objects[n], home[n], local[n], now[n]) for n in inners]
        pairs = [(1, 7), (2, 6), (3, 5)]
        spread = max(max(abs(outer_angles[i] - outer_angles[j]) for i, j in pairs),
                     max(abs(inner_angles[i] - inner_angles[j]) for i, j in ((1, 5), (2, 4))))
        symmetric = symmetric and spread < 0.01
        print("   frame {:3d} outer {}  inner {}  (mirror pairs differ by {:.4f})".format(
            frame, " ".join("{:5.1f}".format(a) for a in outer_angles),
            " ".join("{:5.1f}".format(a) for a in inner_angles), spread))
    check(symmetric, "mirror pairs of petals are at the same angle at every frame: the wave is symmetric")
    scene.frame_set(151)
    bpy.context.view_layer.update()
    now = {n: old.world_points(objects[n]) for n in petals + inners}
    final = ([angle_about_x(objects[n], home[n], local[n], now[n]) for n in petals],
             [angle_about_x(objects[n], home[n], local[n], now[n]) for n in inners])
    check(all(abs(a - 75.0) < 0.05 for a in final[0]) and all(abs(a - 45.0) < 0.05 for a in final[1]),
          "at Play 1 every outer petal is open 75 and every inner petal 45 degrees")

    print("Leaf joints")
    pairs = {1: joint_ends([objects[n] for n in leaf1]), 2: joint_ends([objects[n] for n in leaf2])}
    # The shut positions were read at Before, before the frame was moved.
    for frame in (1, 76, 151):
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        gap_now = max(joints_gap(pairs[1]), joints_gap(pairs[2]))
        check(gap_now < LIMIT, "frame {:3d}: leaf joints joined (worst gap {:.1e})".format(frame, gap_now))

    if sweep:
        print("Sweep over all 151 frames")
        skip = set()
        for leaf in (leaf1, leaf2):
            skip.add((leaf[0], "Stem"))
            for a, b in zip(leaf, leaf[1:]):
                skip.add((a, b))
        bad = []
        for frame in range(1, 152):
            scene.frame_set(frame)
            bpy.context.view_layer.update()
            trees = {n: bvh_of(objects[n]) for n in everything}
            hits = []
            for i, a in enumerate(everything):
                for b in everything[i + 1:]:
                    if (a, b) in skip or (b, a) in skip:
                        continue
                    if trees[a].overlap(trees[b]):
                        hits.append((a, b))
            if hits:
                bad.append(frame)
                print("   frame {:3d}: {}".format(frame, hits[:5]))
        check(not bad, "no parts overlap on any of the 151 frames (bad frames: {})".format(bad[:12]))

    print()
    print("FAILED {:d}".format(len(failures)) if failures else "ALL CHECKS PASSED")

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
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
