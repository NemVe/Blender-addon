"""The outro of the CopyThat promo: the flower blooming in a dark studio.

    /home/user/Blender-addon/.venv/bin/python outro.py [options]

Builds the studio, the lights and the camera move; builds the flower with
flower.build_flower and rigs it with flower.flower_steps, run headless, so the
bloom is the real CopyThat animation keyed by Animate (frames 1 to 150, then
it holds). The outro's own touches are only the glow of the core, keyed on
its material, the camera and the studio. Saves outro.blend next to this file.

Options:
  --stills 1,75,150   render those frames, at full resolution, to stills/
  --range A-B         render a sequence to frames/####.png
  --samples N         Cycles samples per frame (default {samples})
  --res WxH           render size, default 1920x1080
  --resume            with --range: skip frames that already exist
  --no-save           do not write outro.blend
"""

import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PROMO = os.path.dirname(HERE)
ADDON = os.environ.get("COPYTHAT_ADDON", "/home/user/Blender-addon")
sys.path.insert(0, os.path.join(PROMO, "flower"))
sys.path.insert(0, ADDON)

import bpy  # noqa: E402  (first: the bpy module is what makes bmesh importable)
import bmesh  # noqa: E402
from mathutils import Vector  # noqa: E402

import flower  # noqa: E402
import rigmoves  # noqa: E402
import run_headless  # noqa: E402

BLOOM_FRAMES = 149             # keys 1 to 150
LAST_FRAME = 210               # 7 seconds at 30 fps; the card is made elsewhere
SAMPLES = 10
__doc__ = __doc__.format(samples=SAMPLES)


# ---------------------------------------------------------------------------
# the studio

def cyclorama(collection):
    """A curved backdrop: a floor that sweeps up into the wall behind."""
    bm = bmesh.new()
    profile = []
    profile.append((-16.0, 0.0))
    profile.append((1.0, 0.0))
    radius = 5.5
    for k in range(1, 25):
        a = math.radians(-90.0 + 90.0 * k / 24.0)
        profile.append((1.0 + radius * math.cos(a), radius + radius * math.sin(a)))
    profile.append((1.0 + radius, 16.0))
    columns = []
    for x in (-26.0, 26.0):
        columns.append([bm.verts.new((x, y, z)) for y, z in profile])
    for i in range(len(profile) - 1):
        face = bm.faces.new([columns[0][i], columns[1][i], columns[1][i + 1], columns[0][i + 1]])
        # The floor is a little glossy, for the pedestal's reflection; the
        # curve and the wall are matte, or they mirror the lights.
        face.material_index = 0 if profile[i + 1][0] < 1.01 else 1
    for face in bm.faces:
        face.smooth = True
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    mesh = bpy.data.meshes.new("Cyclorama")
    bm.to_mesh(mesh)
    bm.free()
    # Subdivide across so the soft light falls off smoothly, not per face.
    obj = bpy.data.objects.new("Cyclorama", mesh)
    collection.objects.link(obj)
    floor = flower.material("Studio Floor", "#0B0B0E", metallic=0.0, roughness=0.3,
                            Specular_IOR_Level=0.45)
    fade_floor(floor)
    mesh.materials.append(floor)
    mesh.materials.append(flower.material("Studio Wall", "#060608", metallic=0.0, roughness=0.75,
                                          Specular_IOR_Level=0.1))
    obj.color = (0.05, 0.05, 0.06, 1.0)
    return obj


def fade_floor(mat):
    """Glossy near the pedestal, where its reflection is wanted, and matte
    further out, so the softbox is not mirrored across the whole floor."""
    tree = mat.node_tree
    bsdf = next(n for n in tree.nodes if n.type == "BSDF_PRINCIPLED")
    coords = tree.nodes.new("ShaderNodeTexCoord")
    length = tree.nodes.new("ShaderNodeVectorMath")
    length.operation = "LENGTH"
    rough = tree.nodes.new("ShaderNodeMapRange")
    rough.inputs["From Min"].default_value = 2.5
    rough.inputs["From Max"].default_value = 5.5
    rough.inputs["To Min"].default_value = 0.30
    rough.inputs["To Max"].default_value = 0.9
    spec = tree.nodes.new("ShaderNodeMapRange")
    spec.inputs["From Min"].default_value = 2.5
    spec.inputs["From Max"].default_value = 5.5
    spec.inputs["To Min"].default_value = 0.30
    spec.inputs["To Max"].default_value = 0.02
    tree.links.new(coords.outputs["Object"], length.inputs[0])
    tree.links.new(length.outputs["Value"], rough.inputs["Value"])
    tree.links.new(length.outputs["Value"], spec.inputs["Value"])
    tree.links.new(rough.outputs["Result"], bsdf.inputs["Roughness"])
    tree.links.new(spec.outputs["Result"], bsdf.inputs["Specular IOR Level"])


def area_light(collection, name, location, target, energy, size, colour=(1.0, 1.0, 1.0),
               size_y=None, spread=None):
    data = bpy.data.lights.new(name, "AREA")
    data.energy = energy
    data.shape = "RECTANGLE" if size_y else "SQUARE"
    data.size = size
    if size_y:
        data.size_y = size_y
    data.color = colour
    if spread is not None:
        data.spread = math.radians(spread)
    obj = bpy.data.objects.new(name, data)
    collection.objects.link(obj)
    obj.location = location
    direction = Vector(target) - Vector(location)
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    return obj


def build_studio(scene):
    collection = bpy.data.collections.new("Studio")
    scene.collection.children.link(collection)
    cyclorama(collection)

    world = bpy.data.worlds.new("Studio World")
    scene.world = world
    world.use_nodes = True
    background = world.node_tree.nodes["Background"]
    background.inputs["Color"].default_value = (0.004, 0.004, 0.006, 1.0)
    background.inputs["Strength"].default_value = 1.0

    target = (0.0, 0.0, 1.35)
    lights = {}
    # The key: a big warm softbox, high on the front left. It is what the
    # pedestal's top shows.
    lights["key"] = area_light(collection, "Key Softbox", (-5.2, -6.4, 5.8), target, 600.0, 3.4,
                               (1.0, 0.80, 0.60), size_y=2.4, spread=55.0)
    # Cool rim strips behind, left and right, to draw the petals' edges.
    lights["rim_left"] = area_light(collection, "Rim Left", (-4.6, 5.0, 3.4), target, 340.0, 0.7,
                                    (0.62, 0.78, 1.0), size_y=4.2, spread=40.0)
    lights["rim_right"] = area_light(collection, "Rim Right", (5.0, 4.4, 3.0), target, 340.0, 0.7,
                                     (0.62, 0.78, 1.0), size_y=4.2, spread=40.0)
    # A soft fill from the right, low, so the shadows are not black, and a
    # small one from above for the inside of the open flower.
    lights["fill"] = area_light(collection, "Soft Fill", (6.2, -5.0, 1.8), target, 150.0, 4.0,
                                (0.85, 0.9, 1.0))
    lights["top"] = area_light(collection, "Top", (0.4, -1.0, 6.5), (0.0, 0.0, 1.3), 30.0, 1.6,
                               (1.0, 0.95, 0.9), spread=60.0)
    return collection, lights


def add_core_light(collection, scene):
    """A small warm light in the middle of the bloom, so the glow lights the
    pearl petals around it. Its power is keyed with the material's."""
    data = bpy.data.lights.new("Core Light", "POINT")
    data.energy = 1.0
    data.color = (1.0, 0.72, 0.42)
    data.shadow_soft_size = 0.08
    obj = bpy.data.objects.new("Core Light", data)
    collection.objects.link(obj)
    obj.location = (0.0, 0.0, flower.CORE_BASE + flower.CORE_RISE + 0.28)
    return obj


# ---------------------------------------------------------------------------
# the camera and the glow

def smooth(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3.0 - 2.0 * x)


def key_camera(scene, parts):
    """Key the camera over the bloom: push-in, orbit, focus on the core.

    The pose is flower.camera_pose, the same function that placed the camera
    at frame 1. It is keyed every 5 frames with smooth handles over the bloom
    and then held.
    """
    camera = parts["camera"]
    data = camera.data
    data.dof.use_dof = True
    data.dof.aperture_fstop = 3.5
    core = parts["core"]
    frames = list(range(1, BLOOM_FRAMES + 2, 5))
    if frames[-1] != BLOOM_FRAMES + 1:
        frames.append(BLOOM_FRAMES + 1)
    # First every place and focus, with nothing keyed yet: a frame change
    # after the first key would put the held key back over the camera.
    poses = []
    for frame in frames:
        t = (frame - 1) / float(BLOOM_FRAMES)
        matrix, _target = flower.camera_pose(t)
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        # Focus on the core as it is at this frame: the middle of its tips.
        top = sorted(evaluated_points(core), key=lambda p: -p.z)[:200]
        focus = sum(top, top[0] * 0.0) / len(top)
        poses.append((frame, matrix, (focus - matrix.translation).length))
    for frame, matrix, distance in poses:
        camera.matrix_world = matrix
        data.dof.focus_distance = distance
        camera.keyframe_insert("location", frame=frame)
        camera.keyframe_insert("rotation_euler", frame=frame)
        data.dof.keyframe_insert("focus_distance", frame=frame)
    scene.frame_set(1)
    # Smooth, with no overshoot, so the push-in has no wobble in it.
    action = camera.animation_data.action
    for fcurve in iter_fcurves(action):
        for key in fcurve.keyframe_points:
            key.interpolation = "BEZIER"
            key.handle_left_type = key.handle_right_type = "AUTO_CLAMPED"
    focus_action = data.animation_data.action
    for fcurve in iter_fcurves(focus_action):
        for key in fcurve.keyframe_points:
            key.interpolation = "BEZIER"
            key.handle_left_type = key.handle_right_type = "AUTO_CLAMPED"


def iter_fcurves(action):
    """Every F-curve of an action, on Blender 4.4 (slots and layers) or older."""
    if action is None:
        return
    if hasattr(action, "fcurves"):
        yield from action.fcurves
    for layer in getattr(action, "layers", ()):
        for strip in layer.strips:
            for bag in strip.channelbags:
                yield from bag.fcurves


def evaluated_points(obj):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    points = [evaluated.matrix_world @ v.co for v in mesh.vertices]
    evaluated.to_mesh_clear()
    return points


def key_glow(parts, light):
    """The core's glow rises as it opens: the emission strength of its
    material, and a small light with it. The core itself starts to rise at
    about frame 99, so the glow begins a little before."""
    material = parts["core"].data.materials[1]
    emission = next(n for n in material.node_tree.nodes if n.type == "BSDF_PRINCIPLED").inputs["Emission Strength"]
    steps = ((1, 0.35, 0.3), (60, 0.5, 0.6), (100, 2.0, 1.5), (130, 3.2, 3.5), (150, 4.2, 6.0))
    for frame, strength, power in steps:
        emission.default_value = strength
        emission.keyframe_insert("default_value", frame=frame)
        light.data.energy = power
        light.data.keyframe_insert("energy", frame=frame)
    for owner in (material.node_tree, light.data):
        for fcurve in iter_fcurves(owner.animation_data.action):
            for key in fcurve.keyframe_points:
                key.interpolation = "BEZIER"
                key.handle_left_type = key.handle_right_type = "AUTO_CLAMPED"


# ---------------------------------------------------------------------------
# render settings

def configure_render(scene, samples, width, height):
    render = scene.render
    render.engine = "CYCLES"
    render.resolution_x, render.resolution_y = width, height
    render.resolution_percentage = 100
    render.fps = 30
    render.image_settings.file_format = "PNG"
    render.image_settings.color_depth = "8"
    render.image_settings.compression = 15
    cycles = scene.cycles
    cycles.device = "CPU"
    cycles.samples = samples
    cycles.use_adaptive_sampling = True
    cycles.adaptive_threshold = 0.03
    cycles.adaptive_min_samples = 4
    cycles.use_denoising = True
    cycles.denoiser = "OPENIMAGEDENOISE"
    cycles.denoising_input_passes = "RGB_ALBEDO_NORMAL"
    # Measured at 1080p: the accurate prefilter costs 11 s of a 36 s frame at
    # 10 samples, the fast one looks the same on this scene.
    cycles.denoising_prefilter = "FAST"
    cycles.max_bounces = 6
    cycles.diffuse_bounces = 2
    cycles.glossy_bounces = 4
    cycles.transmission_bounces = 2
    cycles.transparent_max_bounces = 2
    cycles.caustics_reflective = False
    cycles.caustics_refractive = False
    cycles.sample_clamp_indirect = 6.0
    cycles.sample_clamp_direct = 0.0
    # A handful of lights: the light tree costs more than it saves.
    cycles.use_light_tree = False
    cycles.blur_glossy = 0.0
    scene.render.film_transparent = False
    scene.render.filter_size = 1.2
    view = scene.view_settings
    for name in ("AgX", "Filmic", "Standard"):
        try:
            view.view_transform = name
            break
        except TypeError:
            continue
    for look in ("AgX - Medium High Contrast", "Medium High Contrast", "None"):
        try:
            view.look = look
            break
        except TypeError:
            continue
    view.exposure = 0.0
    scene.frame_start = 1
    scene.frame_end = LAST_FRAME


def add_bloom(scene, strength=0.9, size=0.5):
    """A soft bloom from the glowing tips of the core only: the Emission pass
    is blurred and added back to the picture in the compositor, after the
    denoise, so the gold's highlights do not glow. Blender 5 keeps the
    compositor in a node group and sets the Glare node through its sockets;
    4.x has scene.node_tree and properties. Nothing here is needed for the
    render, so any failure leaves the picture as it was."""
    try:
        scene.view_layers[0].use_pass_emit = True
        if hasattr(scene, "compositing_node_group"):
            tree = bpy.data.node_groups.new("Outro Compositor", "CompositorNodeTree")
            tree.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
            scene.compositing_node_group = tree
            source = tree.nodes.new("CompositorNodeRLayers")
            glare = tree.nodes.new("CompositorNodeGlare")
            add = tree.nodes.new("ShaderNodeMix")
            out = tree.nodes.new("NodeGroupOutput")
            glare.inputs["Type"].default_value = "Bloom"
            glare.inputs["Threshold"].default_value = 0.0
            glare.inputs["Strength"].default_value = strength
            glare.inputs["Size"].default_value = size
            add.data_type = "RGBA"
            add.blend_type = "ADD"
            add.inputs[0].default_value = 1.0
            tree.links.new(source.outputs["Emission"], glare.inputs["Image"])
            tree.links.new(source.outputs["Image"], add.inputs[6])
            tree.links.new(glare.outputs["Glare"], add.inputs[7])
            tree.links.new(add.outputs[2], out.inputs[0])
        else:
            scene.use_nodes = True
            tree = scene.node_tree
            tree.nodes.clear()
            source = tree.nodes.new("CompositorNodeRLayers")
            glare = tree.nodes.new("CompositorNodeGlare")
            add = tree.nodes.new("CompositorNodeMixRGB")
            out = tree.nodes.new("CompositorNodeComposite")
            glare.glare_type = "FOG_GLOW"
            glare.threshold = 0.0
            glare.mix = 0.0
            glare.size = 8
            add.blend_type = "ADD"
            tree.links.new(source.outputs["Emit"], glare.inputs["Image"])
            tree.links.new(source.outputs["Image"], add.inputs[1])
            tree.links.new(glare.outputs["Image"], add.inputs[2])
            tree.links.new(add.outputs["Image"], out.inputs["Image"])
    except Exception as error:  # noqa: BLE001
        print("no bloom:", error)


# ---------------------------------------------------------------------------

def build(samples, width, height):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    rigmoves.register()
    scene = bpy.context.scene
    scene.name = "CopyThat Outro"
    configure_render(scene, samples, width, height)
    add_bloom(scene)

    parts = flower.build_flower(scene)
    bpy.context.view_layer.update()
    collection, lights = build_studio(scene)
    core_light = add_core_light(collection, scene)

    # The real CopyThat animation: New Move, Ride Along, Build, Animate.
    captions = run_headless.run(flower.flower_steps(parts, BLOOM_FRAMES), scene=scene)
    scene.frame_start, scene.frame_end = 1, LAST_FRAME
    rig = scene.rigmoves_rig
    # The rig has nothing to show a camera, and its handle is not part of the
    # picture.
    rig.hide_render = True
    for obj in scene.objects:
        if obj.type == "ARMATURE":
            obj.hide_render = True

    key_camera(scene, parts)
    key_glow(parts, core_light)
    scene.camera = parts["camera"]
    scene.frame_set(1)
    return scene, parts, captions


def parse(argv):
    options = {"stills": [], "range": None, "samples": SAMPLES, "res": (1920, 1080),
               "resume": False, "save": True}
    args = list(argv)
    while args:
        arg = args.pop(0)
        if arg == "--stills":
            options["stills"] = [int(x) for x in args.pop(0).split(",") if x]
        elif arg == "--range":
            first, last = args.pop(0).split("-")
            options["range"] = (int(first), int(last))
        elif arg == "--samples":
            options["samples"] = int(args.pop(0))
        elif arg == "--res":
            width, height = args.pop(0).lower().split("x")
            options["res"] = (int(width), int(height))
        elif arg == "--resume":
            options["resume"] = True
        elif arg == "--no-save":
            options["save"] = False
        else:
            raise SystemExit("unknown option: " + arg)
    return options


def main(argv=None):
    options = parse(sys.argv[1:] if argv is None else argv)
    started = time.perf_counter()
    scene, parts, _captions = build(options["samples"], *options["res"])
    print("built in {:.1f} s".format(time.perf_counter() - started), flush=True)
    if options["save"]:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "outro.blend"), compress=True)
        print("saved", os.path.join(HERE, "outro.blend"), flush=True)

    for frame in options["stills"]:
        folder = os.path.join(HERE, "stills")
        os.makedirs(folder, exist_ok=True)
        scene.frame_set(frame)
        scene.render.filepath = os.path.join(folder, "{:04d}.png".format(frame))
        began = time.perf_counter()
        bpy.ops.render.render(write_still=True)
        print("frame {:d}: {:.1f} s  {:s}".format(frame, time.perf_counter() - began,
                                                  scene.render.filepath), flush=True)

    if options["range"]:
        folder = os.path.join(HERE, "frames")
        os.makedirs(folder, exist_ok=True)
        first, last = options["range"]
        scene.frame_start, scene.frame_end = first, last
        scene.render.filepath = folder + os.sep
        # One render call for the whole run, with the scene kept in memory
        # between frames, which saves the set-up of every frame after the
        # first. With --resume, a frame that already exists is left alone.
        scene.render.use_overwrite = not options["resume"]
        scene.render.use_placeholder = False
        scene.render.use_persistent_data = True
        clock = {}

        def began(scene_, *_args):
            clock["t"] = time.perf_counter()

        def ended(scene_, *_args):
            print("frame {:d}: {:.1f} s".format(scene_.frame_current, time.perf_counter() - clock["t"]),
                  flush=True)

        bpy.app.handlers.render_pre.append(began)
        bpy.app.handlers.render_post.append(ended)
        bpy.ops.render.render(animation=True)


if __name__ == "__main__":
    main()
