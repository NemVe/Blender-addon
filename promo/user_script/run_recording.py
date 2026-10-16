"""Start the promo script in a real Blender window, the way the recording is made.

    blender --factory-startup --enable-event-simulate
            --window-geometry 0 0 2560 1440
            --python promo/user_script/run_recording.py -- [options]

Then, once Blender's window is open, make it frameless at exactly 2560x1440
(Windows keeps a framed window above the taskbar, 1361 px tall):

    powershell -File promo/tools/frameless_window.ps1

This waits for the window to be that size (up to --wait seconds, then it goes
on with whatever size there is), sets the interface scale (and switches
autosave off), loads the add-on from this repository, runs copythat_promo.py,
and quits Blender a few seconds after the show is over. Nothing is saved. The
first ten seconds of the show (the welcome screen sent away, the sidebar
dragged wider, the countdown) are cut away by the edit, so the capture can be
started as the window appears.

Options (after the "--"):
  --out DIR        where the timeline, the log and the screenshots go
                   (default: promo/user_script/dist/recording)
  --mode MODE      main (the whole rigging) or slider (storyboard shot 4)
  --shots          a dress rehearsal: save a screenshot at every beat, with
                   bpy.ops.screen.screenshot, which also captures popups
  --every SECONDS  with --shots, one more now and then (default 0: none)
  --scale X        the interface scale (default 1.33)
  --size WxH       the window size to wait for (default 2560x1440)
  --wait SECONDS   how long to wait for it (default 90)
  --script PATH    the script to run (default copythat_promo.py beside this file;
                   dist/copythat_promo.py is the bundle)
  --addon DIR      a folder that holds rigmoves/ (default: this repository;
                   COPYTHAT_ADDON does the same)
  --save-blend PATH  save the finished flower, rigged and animated, as a .blend there,
                   as the bloom begins (a copy: nothing else is saved)
  --leave          give the screen back at the end, as a run by hand does, and log
                   how it was left (the recording itself stays in the demo)
  --stay           do not quit when the show is over
  --watchdog SECONDS  quit after this long whatever happens (default 400)
"""

import argparse
import importlib.util
import os
import sys
import time
import traceback

import bpy
from bpy.app.handlers import persistent

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))

parser = argparse.ArgumentParser()
parser.add_argument("--out", default=os.path.join(HERE, "dist", "recording"))
parser.add_argument("--mode", default="main", choices=("main", "slider"))
parser.add_argument("--shots", action="store_true")
parser.add_argument("--every", type=float, default=0.0)
parser.add_argument("--scale", type=float, default=1.33)
parser.add_argument("--size", default="2560x1440")
parser.add_argument("--wait", type=float, default=90.0)
parser.add_argument("--script", default=os.path.join(HERE, "copythat_promo.py"))
parser.add_argument("--addon", default=os.environ.get("COPYTHAT_ADDON", ROOT))
parser.add_argument("--save-blend", default="")
parser.add_argument("--leave", action="store_true")
parser.add_argument("--stay", action="store_true")
parser.add_argument("--watchdog", type=float, default=400.0)
ARGS, _unknown = parser.parse_known_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
WIDTH, HEIGHT = (int(n) for n in ARGS.size.lower().split("x"))

os.makedirs(ARGS.out, exist_ok=True)
LOG = os.path.join(ARGS.out, "log.txt")
TIMELINE = os.path.join(ARGS.out, "timeline.json")
START = time.time()


def log(*parts):
    with open(LOG, "a", encoding="utf-8") as handle:
        handle.write("{:7.2f} {:s}\n".format(time.time() - START, " ".join(str(p) for p in parts)))


open(LOG, "w").close()
for stale in (TIMELINE, TIMELINE + ".part"):
    if os.path.exists(stale):
        os.remove(stale)
os.environ["COPYTHAT_TIMELINE"] = TIMELINE
os.environ["COPYTHAT_PROMO_MODE"] = ARGS.mode
if ARGS.save_blend:
    os.environ["COPYTHAT_SAVE_BLEND"] = os.path.abspath(ARGS.save_blend)

sys.path.insert(0, ARGS.addon)
import rigmoves  # noqa: E402

rigmoves.register()
bpy.context.preferences.view.ui_scale = ARGS.scale
# An autosave, two minutes after Blender starts, would stall the picture while it is written.
bpy.context.preferences.filepaths.use_auto_save_temporary_files = False
# And a file that is saved over is not to leave a .blend1 beside it.
bpy.context.preferences.filepaths.save_version = 0
log("Blender", bpy.app.version_string, "| CopyThat", ".".join(str(n) for n in rigmoves.bl_info["version"]),
    "from", os.path.dirname(rigmoves.__file__), "| scale", ARGS.scale, "| mode", ARGS.mode)

STATE = {"module": None, "show": None, "started": False, "ended": None, "shots": 0,
         "later": [], "done": set(), "beat": None, "dialogs": 0, "last_every": 0.0,
         "ticks": [], "shot_times": [], "frames": [], "bloom_on": False, "acts": []}

# Pictures taken a while into a beat, where it is a glide and not a press:
# {beat: ((seconds after it begins, name), ...)}
IN_BEAT = {"new_move": ((1.7, "six_selected"),),
           "make_chain": ((1.2, "three_selected"),),
           "pose_record": ((2.0, "outer_opening"), (4.6, "inner_opening"), (7.4, "core_rising"),
                           (10.6, "leaf_unfolding")),
           "build": ((5.2, "slider_rising"), (6.6, "slider_at_100"))}


def window():
    return bpy.context.window_manager.windows[0]


def quit_now(why):
    log("quit:", why)
    try:
        bpy.ops.wm.quit_blender()
    except Exception:
        log("quit failed", traceback.format_exc())


# ---------------------------------------------------------------------------
# screenshots

def area_report():
    """The 3D view's shape, as a line for the log: what covers what."""
    try:
        win = window()
        areas = [a for a in win.screen.areas if a.type == "VIEW_3D"]
        area = max(areas, key=lambda a: a.width * a.height)
        space = area.spaces.active
        regions = [(r.type, r.x, r.y, r.width, r.height) for r in area.regions if r.width > 1 and r.height > 1]
        return "window {:d}x{:d} scene {:s} screen {:s} shading {:s} regions {!s}".format(
            win.width, win.height, win.scene.name, win.screen.name, space.shading.type, regions)
    except Exception as exc:
        return "(no area report: {!r})".format(exc)


def space_report():
    """The 3D view's switches, for the log, to see what a run left behind."""
    try:
        win = window()
        area = max((a for a in win.screen.areas if a.type == "VIEW_3D"), key=lambda a: a.width * a.height)
        space = area.spaces.active
        return ("workspace {:s} | scene {:s} | screen {:s} | {:s} | header {!s} tool_header {!s} toolbar {!s} "
                "ui {!s} hud {!s} gizmo {!s} overlays {!s} | shading {:s} color {:s} cavity {!s} shadows {!s} "
                "scene_lights {!s} scene_world {!s}").format(
            win.workspace.name, win.scene.name, win.screen.name, space.region_3d.view_perspective,
            space.show_region_header, space.show_region_tool_header, space.show_region_toolbar,
            space.show_region_ui, space.show_region_hud, space.show_gizmo, space.overlay.show_overlays,
            space.shading.type, space.shading.color_type, space.shading.show_cavity, space.shading.show_shadows,
            space.shading.use_scene_lights, space.shading.use_scene_world)
    except Exception as exc:
        return "(no space report: {!r})".format(exc)


def shoot(name):
    if not ARGS.shots:
        return
    STATE["shots"] += 1
    path = os.path.join(ARGS.out, "{:02d}_{:s}.png".format(STATE["shots"], name))
    STATE["shot_times"].append(time.perf_counter())
    try:
        win = window()
        with bpy.context.temp_override(window=win, screen=win.screen):
            bpy.ops.screen.screenshot(filepath=path)
        STATE["shot_times"].append(time.perf_counter())
        show = STATE["show"]
        scene = show.scenes.get(5) if show is not None else None
        log("shot", os.path.basename(path), "| frame", scene.frame_current if scene else "-", "|", area_report())
    except Exception:
        log("shot failed", name, traceback.format_exc())


def shoot_later(seconds, name):
    if ARGS.shots:
        STATE["later"].append((time.time() + seconds, name))


def once(key, name, delay=0.0):
    if key in STATE["done"]:
        return
    STATE["done"].add(key)
    if delay:
        shoot_later(delay, name)
    else:
        shoot(name)


# ---------------------------------------------------------------------------
# what the show does, as it does it: a spy on the player's actions

def on_action(show, action, now):
    kind = action[0]
    STATE["acts"].append(kind if kind != "call" else getattr(action[1], "__qualname__", "?").split(".")[-1])
    if kind == "beat":
        # The picture now is the last one of the beat before: its end.
        if STATE["beat"] is not None:
            shoot(STATE["beat"] + "_end")
        STATE["beat"] = action[1]
        STATE["dialogs"] = 0
        log("beat", action[1], "|", action[2])
    elif kind == "beat_end":
        if STATE["beat"] is not None:
            shoot(STATE["beat"] + "_end")
            STATE["beat"] = None
        log("beat_end")
    elif kind == "go":
        shoot_later(0.03, "flash")
        log("go: t0, the flash")
    elif kind == "bloom":
        log("bloom", action[1])
        STATE["bloom_on"] = action[1] == "start"
        if action[1] == "start":
            STATE["frames"].clear()
            shoot_later(0.5, "bloom_frame_1")
    elif kind == "call":
        name = getattr(action[1], "__qualname__", "?").split(".")[-1]
        beat = STATE["beat"] or "before"
        if name == "open_it":
            STATE["dialogs"] += 1
            shoot_later(1.2, "{:s}_dialog_{:d}".format(beat, STATE["dialogs"]))
        elif name == "confirm":
            shoot_later(0.9, "{:s}_confirmed_{:d}".format(beat, STATE["dialogs"]))
        elif name in ("new_move", "make_chain", "record_after", "ease", "build", "animate", "pick_rig"):
            shoot_later(0.6, "{:s}_{:s}".format(beat, name))
        elif "op_panel_bottom" in getattr(action[1], "__qualname__", ""):
            shoot_later(0.5, "{:s}_sidebar_scrolled_down".format(beat))
    elif kind in ("countdown", "sidebar", "splash"):
        log(kind, action[1:])
        if kind == "countdown":
            shoot_later(2.2, "countdown")


@persistent
def frame_changed(*_args):
    if STATE["bloom_on"]:
        STATE["frames"].append(time.perf_counter())


bpy.app.handlers.frame_change_post.append(frame_changed)


def install_spy(show):
    tick = show.tick

    def counted():
        now = time.perf_counter()
        beat = STATE["beat"] or ("bloom" if show.timeline and show.timeline.data["bloom_start"] is not None
                                 else "before")
        # What the show did in the tick that has just been: what a long gap was spent on.
        acts, STATE["acts"] = STATE["acts"], []
        if STATE["ticks"] and now - STATE["ticks"][-1][0] > 0.06                 and not any(STATE["ticks"][-1][0] <= t <= now for t in STATE["shot_times"]):
            # Something took the main loop for more than three frames of a 60 Hz timer.
            log("long gap {:5.0f} ms in {:s}, the tick before ran: {:s}".format(
                (now - STATE["ticks"][-1][0]) * 1000.0, beat, ", ".join(acts) or "no action"))
        STATE["ticks"].append((now, beat))
        return tick()
    show.tick = counted
    player = show.player
    original = player.begin

    def spy(action, now):
        try:
            on_action(show, action, now)
        except Exception:
            log("spy failed", traceback.format_exc())
        original(action, now)
    player.begin = spy


# ---------------------------------------------------------------------------
# starting, watching, ending

def start():
    """Once the window is the size asked for (or --wait is up): run the script."""
    win = window()
    waited = time.time() - START
    if (win.width, win.height) != (WIDTH, HEIGHT) and waited < ARGS.wait:
        if int(waited) % 5 == 0 and STATE.get("told") != int(waited):
            STATE["told"] = int(waited)
            log("waiting for a {:d}x{:d} window, it is {:d}x{:d}".format(WIDTH, HEIGHT, win.width, win.height))
        return 0.25
    log("starting: window {:d}x{:d}".format(win.width, win.height), "scale", bpy.context.preferences.view.ui_scale)
    log("view before:", space_report())
    try:
        spec = importlib.util.spec_from_file_location("copythat_promo_run", ARGS.script)
        module = importlib.util.module_from_spec(spec)
        sys.modules["copythat_promo_run"] = module
        spec.loader.exec_module(module)
        STATE["module"] = module
        if ARGS.leave:
            module.LEAVE_IN_DEMO = False
        STATE["show"] = bpy.app.driver_namespace.get(module.STATE_KEY)
        log("script ran: show", STATE["show"] is not None, "| simulated input", module.EVENTS,
            "| scenes", module.SCENES)
        if STATE["show"] is None:
            quit_now("the script did not start a show")
            return None
        install_spy(STATE["show"])
        if ARGS.shots:
            confirm_spy(module)
        STATE["started"] = True
    except Exception:
        log("FAILED to start", traceback.format_exc())
        quit_now("start failed")
    return None


def confirm_spy(module):
    """The picture just before Return confirms a dialog: how it stood for a second and a half."""
    original = module.key_tap

    def tap(window_, key):
        if key == "RET":
            shoot("{:s}_dialog_{:d}_before_return".format(STATE["beat"] or "before", STATE["dialogs"]))
        original(window_, key)
    module.key_tap = tap


def monitor():
    """Screenshots that were asked for later, a few more by what is happening,
    and the end."""
    now = time.time()
    due = [item for item in STATE["later"] if item[0] <= now]
    if due:
        STATE["later"] = [item for item in STATE["later"] if item[0] > now]
        for _when, name in due:
            shoot(name)
    show = STATE["show"]
    if not STATE["started"] or show is None:
        return 0.02
    try:
        scene = show.scenes.get(5)
        if ARGS.shots and ARGS.every > 0 and show.timeline is not None \
                and now - STATE["last_every"] >= ARGS.every:
            STATE["last_every"] = now
            shoot("tick")
        if ARGS.shots and scene is not None and show.timeline is not None \
                and show.timeline.data["bloom_start"] is not None:
            for frame in (40, 75, 110, 150):
                if scene.frame_current >= frame:
                    once("frame{:d}".format(frame), "bloom_frame_{:d}".format(frame))
        if ARGS.shots and show.mode == "main" and show.timeline is not None and show.timeline.data["beats"]:
            beat = show.timeline.data["beats"][-1]
            if beat["end"] is None:
                since = show.since_t0(show.clock()) - beat["start"]
                for seconds, name in IN_BEAT.get(beat["name"], ()):
                    if since >= seconds:
                        once("{:s}@{:.1f}".format(beat["name"], seconds), "{:s}_{:s}".format(beat["name"], name))
        if show.mode == "slider" and show.timeline is not None and show.timeline.data["beats"]:
            beat = show.timeline.data["beats"][-1]
            since = show.since_t0(show.clock()) - beat["start"]
            for seconds in (0.2, 1.0, 2.0, 3.0, 3.8):
                if since >= seconds:
                    once("slider{:.1f}".format(seconds), "slider_{:.1f}s".format(seconds))
        if show.dead:
            if STATE["ended"] is None:
                STATE["ended"] = now
                log("the show is over; error: {!r}".format(show.error))
                if ARGS.save_blend:
                    saved = os.environ["COPYTHAT_SAVE_BLEND"]
                    log("saved flower:", saved, "|", "{:d} bytes".format(os.path.getsize(saved))
                        if os.path.isfile(saved) else "NOT THERE")
                tick_report()
                frame_report()
                shoot("end")
                if not ARGS.stay:
                    shoot_later(2.5, "last")
            elif ARGS.leave and not STATE.get("left_told") and show.left:
                STATE["left_told"] = True
                STATE["left_at"] = now
                log("view after leave:", space_report())
            elif ARGS.leave and STATE.get("left_at") and not STATE.get("left_told_again")                     and now - STATE["left_at"] > 2.0:
                # A region that is hidden slides away first: this is where it ended.
                STATE["left_told_again"] = True
                log("view 2 s after leave:", space_report())
            elif now - STATE["ended"] > 4.0 and not ARGS.stay:
                quit_now("the show is over")
                return None
    except Exception:
        log("monitor error", traceback.format_exc())
    return 0.02


def frame_report():
    """How many of the bloom's frames the viewport really showed, and the
    longest wait between two of them: playback drops frames to keep the time,
    and a recording at 30 fps wants all of them."""
    stamps = STATE["frames"]
    if len(stamps) < 2:
        log("bloom frames: none seen")
        return
    gaps = [(b - a) * 1000.0 for a, b in zip(stamps, stamps[1:])]
    log("bloom frames: {:d} shown in {:.2f} s ({:.1f} a second) | longest gap {:.0f} ms | median {:.1f} ms".format(
        len(stamps), stamps[-1] - stamps[0], (len(stamps) - 1) / (stamps[-1] - stamps[0]), max(gaps),
        sorted(gaps)[len(gaps) // 2]))


def tick_report():
    """How steadily the show's timer ran, per beat: the gaps between its ticks, in
    milliseconds, leaving out the ones a screenshot made longer. The show moves
    things by the clock, so a gap is not a mistake in time, only a step in the
    picture: at 30 fps a recording wants about 33 ms or less."""
    ticks, shots = STATE["ticks"], STATE["shot_times"]
    by = {}
    for (before, _name), (now, name) in zip(ticks, ticks[1:]):
        if any(before <= t <= now for t in shots):
            continue
        by.setdefault(name, []).append((now - before) * 1000.0)
    for name, gaps in by.items():
        gaps.sort()
        log("ticks {:16s} n {:5d} | mean {:5.1f} ms | median {:5.1f} | p95 {:5.1f} | max {:6.1f}".format(
            name, len(gaps), sum(gaps) / len(gaps), gaps[len(gaps) // 2],
            gaps[min(len(gaps) - 1, int(len(gaps) * 0.95))], gaps[-1]))


def watchdog():
    quit_now("watchdog")
    return None


bpy.app.timers.register(start, first_interval=1.0)
bpy.app.timers.register(monitor, first_interval=1.5)
bpy.app.timers.register(watchdog, first_interval=ARGS.watchdog)
