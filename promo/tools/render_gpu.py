"""Render a .blend's animation on this PC's GPU, as 16-bit PNG frames.

    blender -b --factory-startup FILE.blend --python promo/tools/render_gpu.py
            -- OUT_DIR [FIRST LAST] [--res 2560x1440] [--prefix outro_]

--factory-startup keeps the user's own add-ons out, and it also forgets which
GPU Cycles should use, so this turns OptiX on (CUDA if OptiX is missing) for
this run only; preferences are not saved. Frames, not a movie: a sequence
survives a crash and can be resumed from the last frame, and ffmpeg encodes
it afterwards.
"""

import os
import sys
import time

import bpy

args = sys.argv[sys.argv.index("--") + 1:]
res, prefix = None, "frame_"
if "--prefix" in args:
    at = args.index("--prefix")
    prefix = args[at + 1]
    del args[at:at + 2]
if "--res" in args:
    at = args.index("--res")
    res = tuple(int(n) for n in args[at + 1].lower().split("x"))
    del args[at:at + 2]
out = args[0]
first, last = (int(args[1]), int(args[2])) if len(args) >= 3 else (None, None)

prefs = bpy.context.preferences.addons["cycles"].preferences
for kind in ("OPTIX", "CUDA"):
    try:
        prefs.compute_device_type = kind
    except TypeError:
        continue
    prefs.get_devices()
    gpus = [d for d in prefs.devices if d.type == kind]
    if gpus:
        for d in prefs.devices:
            d.use = d.type == kind
        print("RENDER DEVICE", kind, [d.name for d in gpus])
        break
scene = bpy.context.scene
scene.cycles.device = "GPU"
if res:
    scene.render.resolution_x, scene.render.resolution_y = res
    scene.render.resolution_percentage = 100
settings = scene.render.image_settings
if hasattr(settings, "media_type"):
    settings.media_type = "IMAGE"
settings.file_format = "PNG"
settings.color_mode = "RGB"
settings.color_depth = "16"
# Blender reads a relative path from the drive root, not the current folder.
scene.render.filepath = os.path.abspath(out).rstrip("/\\") + "/" + prefix
if first is not None:
    scene.frame_start, scene.frame_end = first, last
start = time.time()
bpy.ops.render.render(animation=True)
print("RENDER SECONDS", round(time.time() - start, 1), "frames", scene.frame_start, scene.frame_end)
