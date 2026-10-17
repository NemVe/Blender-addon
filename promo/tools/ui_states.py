"""Screenshots of the CopyThat sidebar panel in a real window, in the states of
docs/UI_0.20.md, each at UI scale 1.0 and 1.33.

Run with the fast flower file, a window, simulated input only:
  blender --factory-startup --enable-event-simulate --no-window-focus
          --window-geometry 0 0 1500 1390 promo/files/CopyThat_flower_fast.blend
          --python promo/tools/ui_states.py -- <folder holding rigmoves/> <out folder>

It writes one PNG of the whole window per shot, and geometry.jsonl with where
the sidebar stood in each, which crop_shots.py cuts the sidebar out by. The
sidebar is at Blender's default width: a simulated drag like the one in
window_screenshots.py did not widen it when tried here.
"""

import json
import math
import os
import sys
import traceback

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ADDON = argv[0] if len(argv) > 0 else os.path.dirname(os.path.dirname(HERE))
OUT = argv[1] if len(argv) > 1 else os.path.join(HERE, "shots")
os.makedirs(OUT, exist_ok=True)
LOG = os.path.join(OUT, "log.txt")
GEOMETRY = os.path.join(OUT, "geometry.jsonl")
open(LOG, "w").close()
open(GEOMETRY, "w").close()

sys.path.insert(0, ADDON)
import rigmoves  # noqa: E402

rigmoves.register()


def log(*parts):
    with open(LOG, "a", encoding="utf-8") as handle:
        handle.write(" ".join(str(p) for p in parts) + "\n")


def places():
    win = bpy.context.window_manager.windows[0]
    area = max((a for a in win.screen.areas if a.type == "VIEW_3D"),
               key=lambda a: a.width * a.height)
    region = next(r for r in area.regions if r.type == "WINDOW")
    ui = next(r for r in area.regions if r.type == "UI")
    return win, area, region, ui


def override():
    win, area, region, _ui = places()
    return bpy.context.temp_override(window=win, screen=win.screen, area=area, region=region)


def objects(*names):
    return [bpy.data.objects[n] for n in names]


def select(*chosen, active=None):
    for obj in bpy.context.view_layer.objects:
        obj.select_set(False)
    for obj in chosen:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = (active or chosen[-1]) if chosen else None


def rig():
    return bpy.context.scene.rigmoves_rig


def move():
    return rig().rigmoves.moves[0]


def report():
    return rig().rigmoves.report if rig() else ""


def flags(**names):
    """Open or close the panel's sections of the first move, for the ones this
    version of the add-on has."""
    for name, value in names.items():
        if hasattr(move(), name):
            setattr(move(), name, value)


def run(label, result):
    log(label, result, "|", report())


def shoot(name, scale):
    win, _area, _region, ui = places()
    path = os.path.join(OUT, "{:s}_s{:d}.png".format(name, round(scale * 100)))
    with bpy.context.temp_override(window=win, screen=win.screen):
        bpy.ops.screen.screenshot(filepath=path)
    with open(GEOMETRY, "a", encoding="utf-8") as handle:
        handle.write(json.dumps({"file": os.path.basename(path), "scale": scale,
                                 "window": [win.width, win.height],
                                 "ui": [ui.x, ui.y, ui.width, ui.height]}) + "\n")
    log("shot", os.path.basename(path), "sidebar", ui.x, ui.y, ui.width, ui.height)


def at_scale(scale):
    bpy.context.preferences.view.ui_scale = scale


def shots(name):
    """The steps that take one state at both UI scales."""
    return [(lambda: at_scale(1.0), 0.8), (lambda: shoot(name, 1.0), 0.3),
            (lambda: at_scale(1.33), 0.9), (lambda: shoot(name, 1.33), 0.3),
            (lambda: at_scale(1.0), 0.6)]


# -- the steps ---------------------------------------------------------------

def setup():
    win, area, region, ui = places()
    space = area.spaces.active
    space.show_region_ui = True
    space.region_3d.view_perspective = "CAMERA"
    log("window", win.width, win.height, "area", area.width, area.height, "sidebar", ui.width)


def show_tab():
    _win, _area, _region, ui = places()
    try:
        ui.active_panel_category = "CopyThat"
    except Exception as error:   # the panel has to have been drawn once first
        log("tab", repr(error))
    log("tab now", ui.active_panel_category)


def nothing_selected():
    select()


def parts_selected():
    select(*objects("Outer Leader", "Inner Leader", "Core", "Leaf 1", "Leaf 2", "Leaf 3"),
           active=bpy.data.objects["Outer Leader"])


def new_move():
    with override():
        parts_selected()
        run("new move", bpy.ops.rigmoves.new_move())


def recorded():
    """Chain the leaf, pose the parts, Record After: the guide's steps 2 to 4."""
    with override():
        select(*objects("Leaf 3", "Leaf 2", "Leaf 1"), active=bpy.data.objects["Leaf 1"])
        run("make chain", bpy.ops.rigmoves.make_chain(index=0))
        poses = (("Outer Leader", "rx", 75), ("Inner Leader", "rx", 45), ("Core", "lz", 1.47),
                 ("Core", "rz", 60), ("Leaf 1", "rx", 28), ("Leaf 2", "rx", -145),
                 ("Leaf 3", "rx", 172))
        for name, field, value in poses:
            obj = bpy.data.objects[name]
            if field == "rx":
                obj.rotation_euler.x = math.radians(value)
            elif field == "rz":
                obj.rotation_euler.z = math.radians(value)
            else:
                obj.location.z = value
            bpy.context.view_layer.update()
        run("record after", bpy.ops.rigmoves.record(index=0, which="AFTER"))
        select(bpy.data.objects["Outer Leader"])


def built():
    with override():
        run("build", bpy.ops.rigmoves.build())


def outer_ring():
    with override():
        select(bpy.data.objects["Outer Leader"])
        run("ring", bpy.ops.rigmoves.ring(index=0, count=8, center="ORIGIN", lead_step=9))


def delays():
    """A few Delays, as Spread would leave them."""
    for number, part in enumerate(p for p in move().parts if not p.leader):
        part.start = round(0.12 * number, 2)
    log("delays set")


def inner_ring():
    with override():
        select(bpy.data.objects["Inner Leader"])
        run("inner ring", bpy.ops.rigmoves.ring(index=0, count=6, center="ORIGIN"))


def leaf_ring():
    with override():
        select(bpy.data.objects["Leaf 1"])
        run("leaf ring", bpy.ops.rigmoves.ring(index=0, count=2, center="ORIGIN"))


def refused():
    """A button that turns itself down: Curl with a part that nothing follows."""
    with override():
        select(bpy.data.objects["Core"])
        run("curl", bpy.ops.rigmoves.curl(index=0))


def auto_keying_and_newcomer():
    bpy.context.scene.tool_settings.use_keyframe_insert_auto = True
    bpy.ops.mesh.primitive_cube_add(size=0.3, location=(2.0, 2.0, 0.0))
    bpy.context.object.name = "Newcomer"
    log("auto keying on, a newcomer selected")


def auto_keying_off():
    bpy.context.scene.tool_settings.use_keyframe_insert_auto = False
    bpy.data.objects.remove(bpy.data.objects["Newcomer"])
    select(bpy.data.objects["Outer Leader"])


def second_move_combined():
    """Two cubes as a second move, built, and one control for both moves."""
    for name, x in (("Stem A", 3.0), ("Stem B", 3.6)):
        bpy.ops.mesh.primitive_cube_add(size=0.3, location=(x, 2.0, 0.0))
        bpy.context.object.name = name
    with override():
        select(*objects("Stem A", "Stem B"), active=bpy.data.objects["Stem A"])
        run("new move 2", bpy.ops.rigmoves.new_move())
        for name in ("Stem A", "Stem B"):
            bpy.data.objects[name].location.z += 0.8
        bpy.context.view_layer.update()
        run("record after 2", bpy.ops.rigmoves.record(index=1, which="AFTER"))
        run("build", bpy.ops.rigmoves.build())
        run("combine", bpy.ops.rigmoves.combine())
        run("build", bpy.ops.rigmoves.build())
    flags(expanded=False)


def open_sections():
    flags(expanded=True, show_parts=True, show_path=True, show_timing=True,
          show_riders=True, show_chain=True, show_animate=True)


def close_sections():
    flags(show_parts=False, show_path=False, show_timing=False, show_riders=False,
          show_chain=False, show_animate=False)


def timing_and_copies():
    flags(show_parts=False, show_path=False, show_timing=True, show_riders=True,
          show_chain=False, show_animate=False)


def quit_blender():
    log("quit")
    bpy.ops.wm.quit_blender()


STEPS = [
    (setup, 1.0), (show_tab, 1.0), (show_tab, 1.0),
    # 1. empty: no rig yet
    (nothing_selected, 0.6), *shots("01a_empty_nothing_selected"),
    (parts_selected, 0.6), *shots("01b_empty_parts_selected"),
    # 2. one move, unbuilt
    (new_move, 1.0), *shots("02_one_move_unbuilt"),
    # 3. built, with riders and timing
    (recorded, 1.5), (built, 1.5), (outer_ring, 1.5), (delays, 0.5),
    (timing_and_copies, 1.0), *shots("03_built_riders_timing"),
    (open_sections, 1.0), *shots("03b_all_sections_open"),
    # 4. after Ring
    (close_sections, 0.3), (inner_ring, 1.5), (leaf_ring, 1.5),
    (timing_and_copies, 1.0), *shots("04_after_ring"),
    # 5. a warning report
    (close_sections, 0.3), (refused, 1.0), *shots("05_warning_report"),
    # the loud boxes
    (auto_keying_and_newcomer, 1.0), *shots("06_auto_keying_and_newcomer"),
    (auto_keying_off, 0.5),
    # two moves, and one control that plays both
    (second_move_combined, 1.5), *shots("07_two_moves_combined"),
    (quit_blender, None),
]
STATE = {"next": 0}


def tick():
    if STATE["next"] >= len(STEPS):
        return None
    step, wait = STEPS[STATE["next"]]
    STATE["next"] += 1
    try:
        step()
    except Exception:
        log("FAILED at step", STATE["next"] - 1, traceback.format_exc())
    return wait if wait is not None else None


def give_up():
    log("timed out")
    bpy.ops.wm.quit_blender()


bpy.app.timers.register(tick, first_interval=3.0)
bpy.app.timers.register(give_up, first_interval=240.0)
