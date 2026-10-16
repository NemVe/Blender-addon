"""Drive a real Blender window through FLOWER_FAST.md's first steps and save a
screenshot of the panel and of every dialog: Ring (Fill / Use what's there),
Spread for Leads, Spread for Delays (Step and Range).

Run with the fast flower file, a window, simulated input only:
  blender --factory-startup --enable-event-simulate --no-window-focus
          --window-geometry 0 0 1920 1080 CopyThat_flower_fast.blend --python dialogs.py
Optional after "--": the add-on folder to load (default: the frozen 0.18.1
copy next to this script) and the output folder.
"""

import math
import os
import sys
import traceback

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ADDON = argv[0] if len(argv) > 0 else os.path.join(HERE, "addon_0181")
OUT = argv[1] if len(argv) > 1 else os.path.join(HERE, "shots")
os.makedirs(OUT, exist_ok=True)
LOG = os.path.join(OUT, "log.txt")
open(LOG, "w").close()

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
    bpy.context.view_layer.objects.active = active or chosen[-1]


def rig():
    return bpy.context.scene.rigmoves_rig


def move():
    return rig().rigmoves.moves[0]


def report():
    return rig().rigmoves.report if rig() else ""


def shoot(name):
    win, _area, _region, _ui = places()
    path = os.path.join(OUT, name + ".png")
    with bpy.context.temp_override(window=win, screen=win.screen):
        bpy.ops.screen.screenshot(filepath=path)
    log("shot", name, "report:", report())


def mouse_to_view():
    win, area, _region, ui = places()
    # The middle of the 3D view, left of the sidebar: where a user's mouse is
    # when they press a button in the sidebar is near the sidebar, so aim there.
    x = area.x + area.width - ui.width - 40
    y = area.y + area.height // 2 + 200
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=x, y=y)


def escape():
    win = places()[0]
    win.event_simulate(type="ESC", value="PRESS")
    win.event_simulate(type="ESC", value="RELEASE")


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


def guide_1_to_4():
    with override():
        select(*objects("Outer Leader", "Inner Leader", "Core", "Leaf 1", "Leaf 2", "Leaf 3"),
               active=bpy.data.objects["Outer Leader"])
        assert bpy.ops.rigmoves.new_move() == {"FINISHED"}
        log("1", report())
        select(*objects("Leaf 3", "Leaf 2", "Leaf 1"), active=bpy.data.objects["Leaf 1"])
        assert bpy.ops.rigmoves.make_chain(index=0) == {"FINISHED"}
        log("2", report())
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
        assert bpy.ops.rigmoves.record(index=0, which="AFTER") == {"FINISHED"}
        log("4", report())
        m = move()
        m.show_chain = True
        m.show_timing = True
        select(bpy.data.objects["Outer Leader"])


def ring_dialog():
    with override():
        select(bpy.data.objects["Outer Leader"])
        log("ring invoke", bpy.ops.rigmoves.ring("INVOKE_DEFAULT", index=0))


def ring_adopt_dialog():
    with override():
        select(bpy.data.objects["Inner Leader"])
        log("ring adopt invoke", bpy.ops.rigmoves.ring("INVOKE_DEFAULT", index=0, use="ADOPT"))


def ring_for_real():
    with override():
        select(bpy.data.objects["Outer Leader"])
        log("ring", bpy.ops.rigmoves.ring(index=0, count=8, center="ORIGIN", lead_step=9))
        m = move()
        m.show_riders = True


def spread_leads_dialog():
    with override():
        log("spread lead invoke",
            bpy.ops.rigmoves.spread("INVOKE_DEFAULT", index=0, what="LEAD"))


def spread_delays_dialog():
    with override():
        select(*objects("Leaf 3", "Leaf 2", "Leaf 1"), active=bpy.data.objects["Leaf 1"])
        log("spread delay invoke",
            bpy.ops.rigmoves.spread("INVOKE_DEFAULT", index=0, what="DELAY"))


def spread_delays_range_dialog():
    with override():
        log("spread delay range invoke",
            bpy.ops.rigmoves.spread("INVOKE_DEFAULT", index=0, what="DELAY", by="RANGE"))


def quit_blender():
    log("quit")
    bpy.ops.wm.quit_blender()




def widen(by):
    win, _area, _region, ui = places()
    before = ui.width
    y = ui.y + ui.height // 2
    x = ui.x + 1
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=x, y=y)
    win.event_simulate(type="LEFTMOUSE", value="PRESS", x=x, y=y)
    for k in range(1, 11):
        win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=x - by * k // 10, y=y)
    win.event_simulate(type="LEFTMOUSE", value="RELEASE", x=x - by, y=y)
    log("widen from", before)


def width_now():
    log("sidebar now", places()[3].width)


def leaf_ring():
    with override():
        select(bpy.data.objects["Leaf 1"])
        log("leaf ring", bpy.ops.rigmoves.ring(index=0, count=2, center="ORIGIN"))
        log("report", report())




DRAG = {}


def drag_start(by, offset):
    win, _area, _region, ui = places()
    DRAG.update(win=win, x=ui.x + offset, y=ui.y + ui.height // 2, by=by, before=ui.width)
    log("drag at", ui.x + offset, "region x", ui.x, "width", ui.width)
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=DRAG["x"], y=DRAG["y"])


def drag_press():
    DRAG["win"].event_simulate(type="LEFTMOUSE", value="PRESS", x=DRAG["x"], y=DRAG["y"])


def drag_move(k):
    DRAG["win"].event_simulate(type="MOUSEMOVE", value="NOTHING",
                               x=DRAG["x"] - DRAG["by"] * k // 4, y=DRAG["y"])


def drag_release():
    DRAG["win"].event_simulate(type="LEFTMOUSE", value="RELEASE",
                               x=DRAG["x"] - DRAG["by"], y=DRAG["y"])


def measure():
    import blf
    scale = bpy.context.preferences.system.ui_scale
    points = bpy.context.preferences.ui_styles[0].widget.points
    blf.size(0, points * scale)
    for text in ("…er Leader 2", "…r Leader 2", "Outer Leader 2", "Leaf 1 2 +2"):
        log("blf", repr(text), round(blf.dimensions(0, text)[0], 1), "scale", scale, "points", points)


STEPS = [
    (setup, 1.0), (show_tab, 1.0), (show_tab, 1.0), (measure, 0.2),
    (guide_1_to_4, 1.5), (ring_for_real, 1.0), (leaf_ring, 1.5),
    (lambda: shoot("20_ui_default_width"), 0.5),
    (lambda: drag_start(160, 0), 0.3), (drag_press, 0.3),
    (lambda: drag_move(1), 0.2), (lambda: drag_move(2), 0.2), (lambda: drag_move(3), 0.2),
    (lambda: drag_move(4), 0.2), (drag_release, 0.8), (width_now, 0.3),
    (lambda: shoot("21_ui_wider"), 0.5),
    (lambda: drag_start(-250, 0), 0.3), (drag_press, 0.3),
    (lambda: drag_move(1), 0.2), (lambda: drag_move(2), 0.2), (lambda: drag_move(3), 0.2),
    (lambda: drag_move(4), 0.2), (drag_release, 0.8), (width_now, 0.3),
    (lambda: shoot("22_ui_narrow"), 0.5),
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
bpy.app.timers.register(give_up, first_interval=120.0)
