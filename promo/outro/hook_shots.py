"""Render the promo's three hook shots from CopyThat_outro.blend, in Cycles.

    blender -b promo/files/CopyThat_outro.blend --factory-startup
            --python promo/outro/hook_shots.py -- OUT_DIR [--shot A|B|C]
            [--samples N] [--stills] [--percent P]

The outro's camera stops at frame 151, and its wide shot closes the film, so
the opening needs shots of its own: close, moving, on the same flower and the
same CopyThat animation. Each shot is a camera that tracks an empty and focuses
on it, keyed over the part of the bloom it shows:

  A  the bud's tip as its petals part, close and from above (frames 30-90)
  B  down into the flower as the glowing core rises (frames 106-150)
  C  a slow push in on the open flower (frames 152-197)

Nothing is saved: the file on disk is untouched. The GPU (OptiX, else CUDA)
is switched on for this run only. --stills renders the first, middle and last
frame of each shot, to check the framing before the full run.
"""

import os
import sys

import bpy
from mathutils import Vector

SHOTS = {
    # name: (first frame, last frame, camera at first, camera at last,
    #        target at first, target at last, lens mm, f-stop)
    "A": (30, 90, (0.80, -2.45, 3.30), (0.58, -1.92, 3.00),
          (0.0, 0.0, 2.12), (0.0, 0.0, 1.98), 85.0, 2.0),
    "B": (106, 150, (1.50, -1.45, 3.00), (1.22, -1.18, 2.78),
          (0.0, 0.0, 1.55), (0.0, 0.0, 1.58), 85.0, 2.2),
    "C": (152, 197, (1.45, -10.30, 4.44), (1.08, -7.70, 3.38),
          (0.0, 0.0, 1.22), (0.0, 0.0, 1.20), 85.0, 3.5),
}


def arguments():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    out, shots, samples, stills, percent = None, list(SHOTS), None, False, 100
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--shot":
            shots = [argv[i + 1].upper()]
            i += 1
        elif a == "--samples":
            samples = int(argv[i + 1])
            i += 1
        elif a == "--percent":
            percent = int(argv[i + 1])
            i += 1
        elif a == "--stills":
            stills = True
        else:
            out = a
        i += 1
    if out is None:
        raise SystemExit("give an output folder")
    return out, shots, samples, stills, percent


def use_gpu(scene):
    prefs = bpy.context.preferences.addons["cycles"].preferences
    for kind in ("OPTIX", "CUDA"):
        try:
            prefs.compute_device_type = kind
        except TypeError:
            continue
        prefs.get_devices()
        if any(d.type == kind for d in prefs.devices):
            for d in prefs.devices:
                d.use = d.type == kind
            scene.cycles.device = "GPU"
            print("HOOK device", kind)
            return
    print("HOOK device CPU")


def make_shot(scene, name):
    first, last, cam_a, cam_b, aim_a, aim_b, lens, fstop = SHOTS[name]
    target = bpy.data.objects.new("Hook Target " + name, None)
    scene.collection.objects.link(target)
    data = bpy.data.cameras.new("Hook " + name)
    data.lens = lens
    data.dof.use_dof = True
    data.dof.focus_object = target
    data.dof.aperture_fstop = fstop
    data.clip_start = 0.05
    camera = bpy.data.objects.new("Hook " + name, data)
    scene.collection.objects.link(camera)
    track = camera.constraints.new("TRACK_TO")
    track.target = target
    track.track_axis = "TRACK_NEGATIVE_Z"
    track.up_axis = "UP_Y"
    for frame, cam, aim in ((first, cam_a, aim_a), (last, cam_b, aim_b)):
        camera.location = Vector(cam)
        target.location = Vector(aim)
        camera.keyframe_insert("location", frame=frame)
        target.keyframe_insert("location", frame=frame)
    # A move that starts and ends at rest, as a camera operator would.
    for obj in (camera, target):
        action = obj.animation_data.action
        for bag in (b for layer in action.layers for strip in layer.strips
                    for b in strip.channelbags):
            for curve in bag.fcurves:
                for key in curve.keyframe_points:
                    key.interpolation = "BEZIER"
                    key.easing = "AUTO"
    scene.camera = camera
    return first, last


def main():
    out, shots, samples, stills, percent = arguments()
    scene = bpy.context.scene
    use_gpu(scene)
    if samples:
        scene.cycles.samples = samples
    scene.render.resolution_x, scene.render.resolution_y = 2560, 1440
    scene.render.resolution_percentage = percent
    settings = scene.render.image_settings
    if hasattr(settings, "media_type"):
        settings.media_type = "IMAGE"
    settings.file_format = "PNG"
    settings.color_mode = "RGB"
    settings.color_depth = "16"
    for name in shots:
        first, last = make_shot(scene, name)
        folder = os.path.join(out, "hook_" + name)
        os.makedirs(folder, exist_ok=True)
        if stills:
            for frame in (first, (first + last) // 2, last):
                scene.frame_set(frame)
                scene.render.filepath = os.path.join(folder, "still_{:04d}.png".format(frame))
                bpy.ops.render.render(write_still=True)
                print("HOOK still", name, frame)
        else:
            scene.frame_start, scene.frame_end = first, last
            scene.render.filepath = os.path.join(folder, "hook_" + name + "_")
            bpy.ops.render.render(animation=True)
            print("HOOK shot", name, first, last)


main()
