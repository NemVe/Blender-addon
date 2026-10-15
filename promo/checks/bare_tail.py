

# ===========================================================================
# THE BARE SCENE: the flower shut, the studio, the camera move, no CopyThat
# ===========================================================================

SCENE_NAME = "CopyThat Flower"
BLOOM_END = 151          # Frames 150 and Animate from frame 1 key the bloom 1 to 151
LAST_FRAME = 210         # 7 seconds at 30 fps: the bloom, then a hold
GLOW_KEYS = ((1, 0.35, 0.3), (60, 0.5, 0.6), (100, 2.0, 1.5), (130, 3.2, 3.5), (151, 4.2, 6.0))

# What to type for each part, in the order of the guide: (object name, the
# field in the Properties editor > Object tab > Transform, the number). A
# rotation is typed in degrees. Rotation X is a turn about the part's own X
# axis, which is its hinge; the core is lifted (Location Z, the absolute
# height: shut 1.29 plus 0.18) and turned (Rotation Z, absolute: shut 0).
POSES = (
    ("Outer Leader", "Rotation X", OUTER_OPEN),
    ("Inner Leader", "Rotation X", INNER_OPEN),
    ("Core", "Location Z", CORE_BASE + CORE_RISE),
    ("Core", "Rotation Z", CORE_TURN),
    ("Leaf A1", "Rotation X", 28.0),
    ("Leaf A2", "Rotation X", -145.0),
    ("Leaf A3", "Rotation X", 172.0),
    ("Leaf B1", "Rotation X", 24.0),
    ("Leaf B2", "Rotation X", -145.0),
    ("Leaf B3", "Rotation X", 172.0),
)


def hinge_frame(obj):
    """Give a petal or leaf segment a frame in which opening it is ONE number:
    Rotation X, in the Properties editor, from exactly 0 when it is shut.

    Its origin is already on its hinge. The frame is turned about Z alone, so
    its local X is the hinge (horizontal, along the petal's width) and its
    Rotation X, Y, Z is (0, 0, a turn about Z) with XYZ Euler and a uniform
    scale of 1. Whatever tilt the part had in its frame goes into the mesh
    instead, so it looks exactly as it did. With XYZ Euler a change to
    Rotation X is a turn about the part's own X, whether or not it hangs from
    another part, which is how a leaf segment follows the one before it.
    """
    world = obj.matrix_world.copy()
    hinge = (world.to_3x3() @ Vector((0.0, 1.0, 0.0)))     # the old Y: the hinge
    turn = math.atan2(hinge.y, hinge.x) + 0.0
    if abs(turn) < 1e-9:
        turn = 0.0                   # a plain 0, not -0
    frame = Matrix.Translation(world.translation) @ Matrix.Rotation(turn, 4, "Z")
    obj.data.transform(frame.inverted() @ world)
    obj.data.update()
    obj.rotation_mode = "XYZ"
    obj.scale = (1.0, 1.0, 1.0)
    obj.location = world.translation
    obj.rotation_euler = (0.0, 0.0, turn)


def rename(obj, name):
    obj.name = name
    obj.data.name = name


def make_bare(parts):
    """Name the parts for the Outliner and give every hinge its frame."""
    for group, label in ((parts["outer"], "Outer"), (parts["inner"], "Inner")):
        for number, obj in enumerate(group):
            hinge_frame(obj)
            # "Outer Leader", not "Outer 1 (leader)": CopyThat cuts long names
            # short in its lists and buttons, and the cut would leave the
            # outer and the inner leader looking the same.
            rename(obj, "{:s} Leader".format(label) if not number
                   else "{:s} {:d}".format(label, number + 1))
    for chain in parts["leaves"]:
        for obj in chain:
            hinge_frame(obj)
    core = parts["core"]
    core.rotation_mode = "XYZ"
    core.rotation_euler = (0.0, 0.0, 0.0)
    rename(core, "Core")


# ---------------------------------------------------------------------------
# the studio

def cyclorama(collection):
    """A curved backdrop: a floor that sweeps up into the wall behind."""
    bm = bmesh.new()
    profile = [(-16.0, 0.0), (1.0, 0.0)]
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
    obj = bpy.data.objects.new("Cyclorama", mesh)
    collection.objects.link(obj)
    floor = material("Studio Floor", "#0B0B0E", metallic=0.0, roughness=0.3,
                     Specular_IOR_Level=0.45)
    fade_floor(floor)
    mesh.materials.append(floor)
    mesh.materials.append(material("Studio Wall", "#060608", metallic=0.0, roughness=0.75,
                                   Specular_IOR_Level=0.1))
    obj.color = (0.05, 0.05, 0.06, 1.0)
    return obj


def fade_floor(mat):
    """Glossy near the pedestal, where its reflection is wanted, and matte
    further out, so the softbox is not mirrored across the whole floor."""
    tree = mat.node_tree
    bsdf = principled(mat)
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
    """The dark studio: cyclorama, key softbox, cool rim strips, a soft fill,
    a small light from above, and the glow's light inside the flower."""
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
    area_light(collection, "Key Softbox", (-5.2, -6.4, 5.8), target, 600.0, 3.4,
               (1.0, 0.80, 0.60), size_y=2.4, spread=55.0)
    area_light(collection, "Rim Left", (-4.6, 5.0, 3.4), target, 340.0, 0.7,
               (0.62, 0.78, 1.0), size_y=4.2, spread=40.0)
    area_light(collection, "Rim Right", (5.0, 4.4, 3.0), target, 340.0, 0.7,
               (0.62, 0.78, 1.0), size_y=4.2, spread=40.0)
    area_light(collection, "Soft Fill", (6.2, -5.0, 1.8), target, 150.0, 4.0, (0.85, 0.9, 1.0))
    area_light(collection, "Top", (0.4, -1.0, 6.5), (0.0, 0.0, 1.3), 30.0, 1.6,
               (1.0, 0.95, 0.9), spread=60.0)

    # A small warm light in the middle of the bloom, so the glow lights the
    # pearl petals around it. Its power is keyed with the material's.
    data = bpy.data.lights.new("Core Light", "POINT")
    data.energy = 1.0
    data.color = (1.0, 0.72, 0.42)
    data.shadow_soft_size = 0.08
    light = bpy.data.objects.new("Core Light", data)
    collection.objects.link(light)
    light.location = (0.0, 0.0, CORE_BASE + CORE_RISE + 0.28)
    return collection, light


# ---------------------------------------------------------------------------
# the camera and the glow, keyed over frames 1 to 151 and then held

def smooth_keys(action):
    for fcurve in iter_fcurves(action):
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


def core_progress(share):
    """How far the core has risen and turned when the Play control is this
    far along (0 to 1), by the timing the guide sets up: the core's Delay
    inside the move, laid on the control between the first petal to set off
    and the last part to arrive, then the Smooth ease."""
    starts = [0.0,
              -4 * OUTER_LEAD_PER_STEP / 50.0,
              INNER_DELAY - 3 * INNER_LEAD_PER_STEP / 50.0 * (1.0 - INNER_DELAY)]
    low = min(starts)
    begin = (CORE_DELAY - low) / (1.0 - low)
    w = min(max((share - begin) / (1.0 - begin), 0.0), 1.0)
    return w * w * (3.0 - 2.0 * w)


def core_tips(core, share):
    """The middle of the core's glowing tips when the control is at `share`."""
    lift = core_progress(share)
    top = sorted((core.matrix_world @ v.co for v in core.data.vertices), key=lambda p: -p.z)[:200]
    middle = sum(top, top[0] * 0.0) / len(top)
    turned = Matrix.Rotation(math.radians(CORE_TURN) * lift, 3, "Z") @ Vector((middle.x, middle.y, 0.0))
    return Vector((turned.x, turned.y, middle.z + CORE_RISE * lift))


def key_camera(scene, parts):
    """Key the camera over the bloom: push-in, orbit, focus on the core.
    The pose is camera_pose, the same function that placed the camera at
    frame 1. Keyed every 5 frames with smooth handles, then held."""
    camera = parts["camera"]
    data = camera.data
    data.dof.use_dof = True
    data.dof.aperture_fstop = 3.5
    for frame in range(1, BLOOM_END + 1, 5):
        share = (frame - 1) / float(BLOOM_END - 1)
        matrix, _target = camera_pose(share)
        camera.matrix_world = matrix
        data.dof.focus_distance = (core_tips(parts["core"], share) - matrix.translation).length
        camera.keyframe_insert("location", frame=frame)
        camera.keyframe_insert("rotation_euler", frame=frame)
        data.dof.keyframe_insert("focus_distance", frame=frame)
    camera.matrix_world = camera_pose(0.0)[0]
    data.dof.focus_distance = (core_tips(parts["core"], 0.0) - camera.matrix_world.translation).length
    smooth_keys(camera.animation_data.action)
    smooth_keys(data.animation_data.action)


def key_glow(parts, light):
    """The core's glow rises as it opens: the emission strength of its
    material, and a small light with it."""
    material_ = parts["core"].data.materials[1]
    emission = principled(material_).inputs["Emission Strength"]
    for frame, strength, power in GLOW_KEYS:
        emission.default_value = strength
        emission.keyframe_insert("default_value", frame=frame)
        light.data.energy = power
        light.data.keyframe_insert("energy", frame=frame)
    emission.default_value = GLOW_KEYS[0][1]
    light.data.energy = GLOW_KEYS[0][2]
    for owner in (material_.node_tree, light.data):
        smooth_keys(owner.animation_data.action)


def add_bloom(scene, strength=0.9, size=0.5):
    """A soft bloom from the glowing tips of the core only: the Emission pass
    is blurred and added back to the picture in the compositor, after the
    denoise. Blender 5 keeps the compositor in a node group and sets the
    Glare node through its sockets; 4.x has scene.node_tree and properties.
    Nothing here is needed for the render, so a failure leaves the picture as
    it was."""
    try:
        scene.view_layers[0].use_pass_emit = True
        if hasattr(scene, "compositing_node_group"):
            tree = bpy.data.node_groups.new("Outro Compositor", "CompositorNodeTree")
            tree.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
            scene.compositing_node_group = tree
            source = tree.nodes.new("CompositorNodeRLayers")
            source.scene = scene     # not the scene being looked at, which may be another
            source.layer = scene.view_layers[0].name
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
            source.scene = scene
            source.layer = scene.view_layers[0].name
            glare = tree.nodes.new("CompositorNodeGlare")
            add = tree.nodes.new("CompositorNodeMixRGB")
            out = tree.nodes.new("CompositorNodeComposite")
            glare.glare_type = "FOG_GLOW"
            glare.threshold = 0.0
            glare.mix = 1.0              # the glow alone: the picture is added below
            glare.size = 8
            add.blend_type = "ADD"
            tree.links.new(source.outputs["Emit"], glare.inputs["Image"])
            tree.links.new(source.outputs["Image"], add.inputs[1])
            tree.links.new(glare.outputs["Image"], add.inputs[2])
            tree.links.new(add.outputs["Image"], out.inputs["Image"])
    except Exception as error:  # noqa: BLE001
        print("The glow bloom was not set up (the render is fine without it):", error)


# ---------------------------------------------------------------------------
# render settings: Cycles on the GPU, 512 samples, a perceptually lossless
# H.264 movie written next to the file

def configure_render(scene):
    render = scene.render
    render.engine = "CYCLES"
    render.resolution_x, render.resolution_y = 1920, 1080
    render.resolution_percentage = 100
    render.fps = 30
    cycles = scene.cycles
    cycles.device = "GPU"            # falls back to the CPU when no GPU is switched on
    cycles.samples = 512
    cycles.use_adaptive_sampling = True
    cycles.adaptive_threshold = 0.01
    cycles.adaptive_min_samples = 32
    cycles.use_denoising = True
    cycles.denoiser = "OPENIMAGEDENOISE"
    cycles.denoising_input_passes = "RGB_ALBEDO_NORMAL"
    cycles.denoising_prefilter = "ACCURATE"
    cycles.use_light_tree = True
    cycles.max_bounces = 6
    cycles.diffuse_bounces = 2
    cycles.glossy_bounces = 4
    cycles.transmission_bounces = 2
    cycles.transparent_max_bounces = 2
    cycles.caustics_reflective = False
    cycles.caustics_refractive = False
    cycles.sample_clamp_indirect = 6.0
    cycles.sample_clamp_direct = 0.0
    render.use_motion_blur = True
    render.motion_blur_shutter = 0.5
    render.film_transparent = False
    render.filter_size = 1.2
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
    scene.frame_start, scene.frame_end, scene.frame_current = 1, LAST_FRAME, 1
    try:
        render.image_settings.media_type = "VIDEO"      # Blender 5
    except (AttributeError, TypeError):
        pass
    render.image_settings.file_format = "FFMPEG"
    render.ffmpeg.format = "MPEG4"
    render.ffmpeg.codec = "H264"
    render.ffmpeg.constant_rate_factor = "PERC_LOSSLESS"
    try:
        render.ffmpeg.ffmpeg_preset = "BEST"
    except TypeError:
        pass
    render.ffmpeg.audio_codec = "NONE"
    # In the folder of the .blend: save the file first, then Render Animation.
    render.filepath = "//CopyThat_flower_"


def make_fast(parts):
    """The fast version keeps only the parts that are modelled once: the two
    leader petals, the core, and ONE leaf (Leaf 1, 2 and 3). Ring makes the
    rest, so everything else is taken out. The flower's axis is the world Z
    axis through the origin, so Ring round the World Origin lands every copy
    exactly where the full model has it."""
    outer, inner, chain = parts["outer"], parts["inner"], parts["leaves"][0]
    for obj in outer[1:] + inner[1:] + parts["leaves"][1]:
        mesh = obj.data
        bpy.data.objects.remove(obj, do_unlink=True)
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)
    for number, obj in enumerate(chain):
        rename(obj, "Leaf {:d}".format(number + 1))
    parts["outer"], parts["inner"], parts["leaves"] = outer[:1], inner[:1], [chain]
    parts["all"] = ([parts["pedestal"], parts["stem"], *parts["outer"], *parts["inner"],
                     parts["core"], *chain, parts["camera"]])


def build_bare_scene(make_current=True, fast=False):
    """Build the whole thing in a new scene "CopyThat Flower", leaving
    everything else in the file alone. Returns (scene, parts)."""
    scene = bpy.data.scenes.new(SCENE_NAME)
    configure_render(scene)
    parts = build_flower(scene)
    make_bare(parts)
    if fast:
        make_fast(parts)
    studio, light = build_studio(scene)
    key_camera(scene, parts)
    key_glow(parts, light)
    add_bloom(scene)
    scene.camera = parts["camera"]
    scene.frame_set(1)
    # The studio is for the render. Out of the way in the viewport, so the
    # recording shows the flower; the eye beside it in the Outliner brings it back.
    layer = scene.view_layers[0].layer_collection.children.get("Studio")
    if layer is not None:
        layer.hide_viewport = True
    if make_current and bpy.context.window is not None:
        bpy.context.window.scene = scene
    print("CopyThat flower: built scene '{:s}' with {:d} parts. Next: the steps in {:s}."
          .format(scene.name, len([o for o in parts["all"] if o.type == "MESH"]),
                  "FLOWER_FAST.md" if fast else "FLOWER_STEPS.md"))
    return scene, parts
