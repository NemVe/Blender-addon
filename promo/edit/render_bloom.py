"""Render the demo's bloom from the 3D view, one frame at a time, for shot 7.

The recording of the bloom plays in real time, so it repeats a frame every 12
frames and its white petals are grainy (few viewport samples while playing).
This renders the same view frame by frame instead, with Blender's viewport
render, which needs a real window (not --background):

    blender --factory-startup --window-geometry 80 80 1500 900
            promo/files/CopyThat_demo_result.blend
            --python promo/edit/render_bloom.py -- --out dist/promo/viewport_bloom

It opens the demo result, turns the 3D view to "Promo Camera" in Material
Preview with the studio's light and no overlays (the look the recording ends
on), makes the picture 2560x1440, and calls
bpy.ops.render.opengl(animation=True, view_context=True) for frames 1 to 151.
Nothing is saved: the file stays as it is in the repository.

Options (after the "--"):
  --out DIR       where the frames go (default dist/promo/viewport_bloom)
  --size WxH      the picture (default 2560x1440)
  --frames A-B    which frames (default 1-151)
  --samples N     EEVEE samples (default: what the file has): the viewport ones, which a
                  viewport render uses, and the render ones with them
  --depth 8|16    PNG bit depth (default 16, as the Cycles frames)
  --prefix NAME   file name before the frame number (default bloom_)
  --addon DIR     a folder that holds rigmoves/ (default: this repository)
  --stay          do not quit when it is done
  --watchdog S    quit after this long whatever happens (default 1500)
"""

import argparse
import os
import sys
import time
import traceback

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))

parser = argparse.ArgumentParser()
parser.add_argument("--out", default=os.path.join(ROOT, "dist", "promo", "viewport_bloom"))
parser.add_argument("--size", default="2560x1440")
parser.add_argument("--frames", default="1-151")
parser.add_argument("--samples", type=int, default=0)
parser.add_argument("--depth", default="16", choices=("8", "16"))
parser.add_argument("--prefix", default="bloom_")
parser.add_argument("--addon", default=ROOT)
parser.add_argument("--stay", action="store_true")
parser.add_argument("--watchdog", type=float, default=1500.0)
ARGS, _unknown = parser.parse_known_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
# Blender reads a render path that is not absolute from the root of the drive, not from here.
ARGS.out = os.path.abspath(ARGS.out)
WIDTH, HEIGHT = (int(n) for n in ARGS.size.lower().split("x"))
FIRST, LAST = (int(n) for n in ARGS.frames.split("-"))

os.makedirs(ARGS.out, exist_ok=True)
LOG = os.path.join(ARGS.out, "render_bloom_log.txt")
START = time.time()
STATE = {"tries": 0}


def log(*parts):
    with open(LOG, "a", encoding="utf-8") as handle:
        handle.write("{:7.2f} {:s}\n".format(time.time() - START, " ".join(str(p) for p in parts)))


def quit_now(why):
    log("quit:", why)
    try:
        bpy.ops.wm.quit_blender()
    except Exception:
        log("quit failed", traceback.format_exc())


def three_d_area(window):
    areas = [a for a in window.screen.areas if a.type == "VIEW_3D"]
    return max(areas, key=lambda a: a.width * a.height) if areas else None


def run():
    """Once the window and its 3D view are there: set the look, render, quit."""
    manager = bpy.context.window_manager
    window = manager.windows[0] if len(manager.windows) else None
    area = three_d_area(window) if window is not None else None
    STATE["tries"] += 1
    if (window is None or area is None) and STATE["tries"] < 60:
        return 0.5
    try:
        log("Blender", bpy.app.version_string, "| file", os.path.basename(bpy.data.filepath),
            "| window", window.width, "x", window.height, "| 3D view", area.width, "x", area.height)
        scene = window.scene
        render = scene.render
        log("scene", repr(scene.name), "| camera", scene.camera.name if scene.camera else None,
            "| engine", render.engine, "| was", render.resolution_x, "x", render.resolution_y)

        # The same two lines the demo script's bloom beat gives the view
        space = area.spaces.active
        space.shading.type = "MATERIAL"
        space.shading.use_scene_lights = True
        space.shading.use_scene_world = True
        space.overlay.show_overlays = False
        space.show_gizmo = False
        space.region_3d.view_perspective = "CAMERA"

        render.resolution_x, render.resolution_y, render.resolution_percentage = WIDTH, HEIGHT, 100
        render.use_border = False
        # The file is set to make a video; since Blender 5.0 a picture is a media type of its own.
        if hasattr(render.image_settings, "media_type"):
            render.image_settings.media_type = "IMAGE"
        render.image_settings.file_format = "PNG"
        render.image_settings.color_mode = "RGB"
        render.image_settings.color_depth = ARGS.depth
        render.image_settings.compression = 15
        render.use_file_extension = True
        render.use_overwrite = True
        render.filepath = os.path.join(ARGS.out, ARGS.prefix)
        scene.frame_start, scene.frame_end = FIRST, LAST
        scene.frame_set(FIRST)
        if ARGS.samples:
            scene.eevee.taa_samples = ARGS.samples
            scene.eevee.taa_render_samples = ARGS.samples
        log("EEVEE samples: viewport", scene.eevee.taa_samples, "render", scene.eevee.taa_render_samples,
            "| view transform",
            scene.view_settings.view_transform, "/", scene.view_settings.look,
            "| shading", space.shading.type, "| overlays", space.overlay.show_overlays,
            "| frames", FIRST, "to", LAST, "| out", render.filepath)

        region = next(r for r in area.regions if r.type == "WINDOW")
        began = time.time()
        with bpy.context.temp_override(window=window, screen=window.screen, area=area, region=region,
                                       scene=scene):
            result = bpy.ops.render.opengl(animation=True, view_context=True)
        seconds = time.time() - began
        written = sorted(f for f in os.listdir(ARGS.out) if f.startswith(ARGS.prefix) and f.endswith(".png"))
        log("render.opengl returned", result, "| {:.1f} s".format(seconds), "|", len(written), "frames written",
            "({:s} to {:s})".format(written[0], written[-1]) if written else "")
    except Exception:
        log("FAILED", traceback.format_exc())
    if not ARGS.stay:
        quit_now("done")
    return None


def watchdog():
    quit_now("watchdog")
    return None


try:
    bpy.context.preferences.filepaths.use_auto_save_temporary_files = False
    sys.path.insert(0, ARGS.addon)
    import rigmoves  # noqa: E402

    rigmoves.register()
    log("CopyThat", ".".join(str(n) for n in rigmoves.bl_info["version"]), "from", os.path.dirname(rigmoves.__file__))
except Exception:
    log("add-on not registered", traceback.format_exc())

bpy.app.timers.register(run, first_interval=2.0)
bpy.app.timers.register(watchdog, first_interval=ARGS.watchdog)
