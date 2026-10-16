"""Build the FAST CopyThat flower scene: the parts modelled once, ready to rig.

For Blender 4.5 or newer, with CopyThat 0.18.1 or newer. In Blender: open the
Scripting tab, click New, paste this whole file, and press Run Script (the
triangle, or Alt+P) ONCE.

It adds ONE new scene, "CopyThat Flower", to the file you have open and
switches to it. Nothing you already have is changed or deleted. The scene has:

  * the flower, shut, with only the parts that are modelled once: "Outer
    Leader" (a petal), "Inner Leader", "Core", and a leaf of three segments,
    "Leaf 1", "Leaf 2", "Leaf 3", on a stem and a pedestal. The flower stands
    on the world origin with the world Z axis through its middle, so CopyThat's
    Ring round the World Origin puts every other petal exactly in its place;
  * every hinge is the part's own X axis: opening a part is one number typed
    into Rotation X in the Properties editor (Object tab > Transform);
  * the dark studio, its lights, and the "Promo Camera" with its move keyed
    over frames 1 to 151 and then held to frame 210; the core's glow keyed to
    rise with the bloom;
  * Cycles set up to render it: GPU (the CPU if no GPU is switched on in
    Preferences), 512 adaptive samples, OpenImageDenoise, motion blur, and an
    H.264 movie written next to the .blend as CopyThat_flower_####.mp4. Save
    the file before you render.

There is NO CopyThat data in it: no rig, no moves. That is your part, and it
is in FLOWER_FAST.md.

The "Studio" collection is hidden in the 3D view so the recording shows the
flower (it still renders). Click its eye in the Outliner to see it.
"""

# ===========================================================================
# The flower, inlined from flower.py (sha256 d8d1ce48852c), unchanged.
# ===========================================================================

# The mechanical flower of the CopyThat promo: geometry, materials and rig.
#
# Plain bpy with no imports from the rest of the promo, so the same file can be
# pasted into the in-Blender demo script and imported by the outro render. It
# needs Blender 4.4 or later and no add-on but CopyThat.
#
#     parts = build_flower(scene)           # the closed bud, plus "Promo Camera"
#     for action in flower_steps(parts):    # a scene generator: see SPEC.md
#         ...
#
# The flower stands on the world origin, Z up. The front, the side the camera
# looks from, is the -Y side. Every moving part has its origin on its hinge or
# joint, so the default Pivot (Origin) turns it there.
#
# Why the timing is what it is. A rider's window is its leader's, shifted by its
# Lead; a part with a Delay runs from the delay to the end of the leader's
# window. So the leader of a wave finishes last, and everything with a delay
# finishes with it. The wave is therefore run towards the leader: the petals
# farthest from the front are sent ahead (a positive Lead), and the front petal,
# the one that was recorded, opens last, together with the core, the leaves and
# the inner petals.

import math

import bpy
import bmesh  # after bpy: as a Python module, bpy is what makes bmesh importable
from mathutils import Matrix, Vector

COLLECTION = "CopyThat Flower"

# --- sizes, in metres ------------------------------------------------------
PEDESTAL_RADIUS = 1.45
PEDESTAL_TOP = 0.30
HUB_Z = 1.20                   # the rim of the cup on top of the stem
OUTER_COUNT = 8
INNER_COUNT = 6

OUTER_HINGE = (0.185, HUB_Z + 0.055)    # distance from the axis, height
OUTER_LENGTH = 1.25
OUTER_LEAN = (34.0, -61.0)     # lean from upright at the base and at the tip
OUTER_HALF = 0.200             # half the width at the widest, if there is room
OUTER_OPEN = 75.0              # how far each outer petal leans out when open

INNER_HINGE = (0.115, HUB_Z + 0.075)
INNER_LENGTH = 0.92
INNER_LEAN = (22.0, -42.0)
INNER_HALF = 0.130
INNER_OPEN = 45.0

CORE_BASE = HUB_Z + 0.09       # height of the middle of the core's dome
CORE_RISE = 0.18               # about 15% of the bud's height
CORE_TURN = 60.0               # degrees, about the vertical axis

FRONT = -90.0                  # azimuth of the leader petal: towards -Y

# The timing. Leads are in the add-on's own units (-50 to 50); Delays are
# fractions of the leader's travel.
OUTER_LEAD_PER_STEP = 9        # per 45 degrees the petal stands from the front
INNER_DELAY = 0.34             # the inner leader waits this long
INNER_LEAD_PER_STEP = 14       # per 60 degrees away from the front
CORE_DELAY = 0.40
LEAF_DELAYS = (0.10, 0.20, 0.40)
EASE = "SMOOTH"

CAMERA_LENS = 85.0


# ---------------------------------------------------------------------------
# colours and materials

def srgb(hexcode):
    """'#C9A76A' as the linear RGBA Blender wants."""
    text = hexcode.lstrip("#")
    out = []
    for i in (0, 2, 4):
        c = int(text[i:i + 2], 16) / 255.0
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return (out[0], out[1], out[2], 1.0)


def _put(node, name, value):
    socket = node.inputs.get(name)
    if socket is not None:
        socket.default_value = value
    return socket


def material(name, colour, metallic=0.0, roughness=0.5, view=None, **inputs):
    """A Principled BSDF material, with its viewport display set to match.

    `view` is the colour the Solid viewport shows; by default it is the base
    colour, which is what the recorded demo should look like.
    """
    mat = bpy.data.materials.new(name)
    if not mat.use_nodes:
        mat.use_nodes = True
    tree = mat.node_tree
    bsdf = next(n for n in tree.nodes if n.type == "BSDF_PRINCIPLED")
    _put(bsdf, "Base Color", srgb(colour))
    _put(bsdf, "Metallic", metallic)
    _put(bsdf, "Roughness", roughness)
    for key, value in inputs.items():
        if isinstance(value, str) and value.startswith("#"):
            value = srgb(value)
        _put(bsdf, key.replace("_", " "), value)
    mat.diffuse_color = srgb(view or colour)
    # The viewport's own metallic and roughness are only what Solid mode
    # shades with. A metal there is dark with nothing to reflect, so they
    # stay matte, and the colour above carries the look.
    mat.metallic = 0.0
    mat.roughness = 0.5
    return mat


def principled(mat):
    return next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")


def satin_gold(name="Champagne Gold"):
    """Satin champagne-gold metal with a faint brushed grain along each petal
    and an anisotropic sheen."""
    mat = material(name, "#C9A76A", metallic=1.0, roughness=0.27,
                   Anisotropic=0.35, Specular_Tint="#FFE9C0")
    tree = mat.node_tree
    bsdf = principled(mat)
    nodes, links = tree.nodes, tree.links
    coords = nodes.new("ShaderNodeTexCoord")
    mapping = nodes.new("ShaderNodeMapping")
    # Stretched across the petal, so the grain runs along its length.
    mapping.inputs["Scale"].default_value = (2.0, 90.0, 1.0)
    noise = nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 3.0
    noise.inputs["Detail"].default_value = 4.0
    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.03
    bump.inputs["Distance"].default_value = 0.01
    tangent = nodes.new("ShaderNodeTangent")
    tangent.direction_type = "UV_MAP"
    tangent.uv_map = "UVMap"
    links.new(coords.outputs["UV"], mapping.inputs["Vector"])
    links.new(mapping.outputs["Vector"], noise.inputs["Vector"])
    links.new(noise.outputs["Fac"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    links.new(tangent.outputs["Tangent"], bsdf.inputs["Tangent"])
    return mat


def pearl(name="Pearl"):
    mat = material(name, "#DCCFBA", metallic=0.0, roughness=0.36,
                   Coat_Weight=0.7, Coat_Roughness=0.06,
                   Sheen_Weight=0.6, Sheen_Tint="#FFD9E8",
                   Specular_IOR_Level=0.6)
    # A hint of thin-film shimmer where Blender has it (Cycles, 4.2 and up).
    _put(principled(mat), "Thin Film Thickness", 380.0)
    _put(principled(mat), "Thin Film IOR", 1.35)
    return mat


def graphite(name="Graphite"):
    return material(name, "#17181B", metallic=1.0, roughness=0.42, view="#5B5F66")


def leaf_graphite(name="Leaf Graphite"):
    """Darker and rougher than the stem, so a leaf never flares in the key."""
    return material(name, "#0C0D0F", metallic=1.0, roughness=0.62, view="#4E5258")


def leaf_bronze(name="Leaf Bronze"):
    """The leaves' little hinge caps: dark and rough, so they stay tucked."""
    return material(name, "#6E5731", metallic=1.0, roughness=0.5, view="#8A6F3E")


def brass(name="Brass"):
    return material(name, "#B8955A", metallic=1.0, roughness=0.22)


def glow(name="Core Glow"):
    """The core's warm light. Its Emission Strength is what the outro keys."""
    return material(name, "#FFB86B", metallic=0.0, roughness=0.4,
                    Emission_Color="#FFB86B", Emission_Strength=3.0)


def black_gloss(name="Black Gloss"):
    return material(name, "#050506", metallic=0.0, roughness=0.06, view="#34353B",
                    Coat_Weight=1.0, Coat_Roughness=0.02, Specular_IOR_Level=0.7)


def gold_ring(name="Gold Ring"):
    return material(name, "#D2AE6C", metallic=1.0, roughness=0.16)


# ---------------------------------------------------------------------------
# meshes

def _face(bm, verts, material_index=0, smooth=True):
    """A face from a loop of verts, skipping repeats (a fan around a pole)."""
    loop = []
    for vert in verts:
        if not loop or loop[-1] is not vert:
            loop.append(vert)
    if len(loop) > 1 and loop[0] is loop[-1]:
        loop.pop()
    if len(loop) < 3 or len(set(loop)) != len(loop):
        return None
    try:
        face = bm.faces.new(loop)
    except ValueError:
        return None
    face.material_index = material_index
    face.smooth = smooth
    return face


def _mesh(name, bm):
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    return mesh


def lathe(bm, profile, steps=72, material_index=0, sharp=()):
    """Spin a profile of (radius, height) points about Z.

    A point on the axis becomes one vertex. `sharp` lists profile points
    whose ring is a crease; everything else is smooth shaded.
    """
    rings = []
    for r, z in profile:
        if r < 1e-6:
            rings.append([bm.verts.new((0.0, 0.0, z))] * steps)
        else:
            rings.append([bm.verts.new((r * math.cos(2 * math.pi * k / steps),
                                        r * math.sin(2 * math.pi * k / steps), z))
                          for k in range(steps)])
    for i in range(len(profile) - 1):
        for k in range(steps):
            k2 = (k + 1) % steps
            _face(bm, [rings[i][k], rings[i][k2], rings[i + 1][k2], rings[i + 1][k]],
                  material_index)
    for i in sharp:
        for k in range(steps):
            a, b = rings[i][k], rings[i][(k + 1) % steps]
            if a is not b:
                edge = bm.edges.get((a, b))
                if edge is not None:
                    edge.smooth = False
    return rings


def torus_ring(bm, radius, z, minor, material_index=1, steps=160, sides=14):
    """A thin ring lying flat: a lathe of a small circle."""
    profile = [(radius + minor * math.cos(2 * math.pi * s / sides),
                z + minor * math.sin(2 * math.pi * s / sides)) for s in range(sides)]
    profile.append(profile[0])
    lathe(bm, profile, steps, material_index)


def cylinder_y(bm, radius, length, material_index=1, segments=20):
    """A hinge barrel along the local Y axis, centred on the origin."""
    ring_a, ring_b = [], []
    for k in range(segments):
        a = 2 * math.pi * k / segments
        x, z = radius * math.cos(a), radius * math.sin(a)
        ring_a.append(bm.verts.new((x, -length / 2, z)))
        ring_b.append(bm.verts.new((x, length / 2, z)))
    for k in range(segments):
        k2 = (k + 1) % segments
        _face(bm, [ring_a[k], ring_b[k], ring_b[k2], ring_a[k2]], material_index)
    _face(bm, list(reversed(ring_a)), material_index, smooth=False)
    _face(bm, ring_b, material_index, smooth=False)


def ellipsoid(bm, centre, radii, axis, material_index=0, segments=12, rings=7):
    """An ellipsoid whose long radius (the last) lies along `axis`."""
    rx, ry, rz = radii
    axis = Vector(axis).normalized()
    helper = Vector((1, 0, 0)) if abs(axis.x) < 0.9 else Vector((0, 1, 0))
    side = axis.cross(helper).normalized()
    up = axis.cross(side).normalized()
    basis = Matrix(((side.x, up.x, axis.x), (side.y, up.y, axis.y), (side.z, up.z, axis.z)))
    rows = []
    for j in range(rings + 1):
        phi = math.pi * j / rings
        r, z = math.sin(phi), math.cos(phi)
        if j in (0, rings):
            rows.append([bm.verts.new(Vector(centre) + basis @ Vector((0, 0, rz * z)))] * segments)
        else:
            rows.append([bm.verts.new(Vector(centre) + basis @ Vector(
                (rx * r * math.cos(2 * math.pi * k / segments),
                 ry * r * math.sin(2 * math.pi * k / segments), rz * z)))
                for k in range(segments)])
    for j in range(rings):
        for k in range(segments):
            k2 = (k + 1) % segments
            _face(bm, [rows[j][k], rows[j][k2], rows[j + 1][k2], rows[j + 1][k]],
                  material_index)


def tube(bm, points, radii, material_index=0, segments=6):
    """A tapered tube through a list of points, closed at both ends."""
    rings = []
    for i, (p, r) in enumerate(zip(points, radii)):
        tangent = ((points[i + 1] - p) if i < len(points) - 1 else (p - points[i - 1])).normalized()
        helper = Vector((1, 0, 0)) if abs(tangent.x) < 0.9 else Vector((0, 1, 0))
        side = tangent.cross(helper).normalized()
        up = tangent.cross(side).normalized()
        rings.append([bm.verts.new(p + (side * math.cos(2 * math.pi * k / segments)
                                        + up * math.sin(2 * math.pi * k / segments)) * r)
                      for k in range(segments)])
    for i in range(len(rings) - 1):
        for k in range(segments):
            k2 = (k + 1) % segments
            _face(bm, [rings[i][k], rings[i][k2], rings[i + 1][k2], rings[i + 1][k]],
                  material_index)
    _face(bm, list(reversed(rings[0])), material_index)
    _face(bm, rings[-1], material_index)


def spine(length, lean, bend, steps):
    """A petal's spine in its own plane: (outward, up, lean angle) per step.

    The lean is the angle from upright, positive leaning outwards. It goes
    from the first value at the base to the second at the tip, and `bend`
    keeps more of the turn for the tip, so the bud closes like a tulip.
    """
    a0, a1 = math.radians(lean[0]), math.radians(lean[1])

    def angle(u):
        return a0 + (a1 - a0) * ((1.0 - bend) * u + bend * u * u)

    x = z = 0.0
    out = [(0.0, 0.0, a0)]
    for i in range(1, steps + 1):
        a = angle((i - 0.5) / steps)
        x += math.sin(a) * length / steps
        z += math.cos(a) * length / steps
        out.append((x, z, angle(i / steps)))
    return out


def outline(u, base=0.16, belly=1.12, power=0.62):
    """How wide a petal is at u (0 base, 1 tip), as a share of its widest."""
    return base + (1.0 - base) * math.sin(math.pi * u ** belly) ** power


def _grid_surface(bm, rows, nv, uv_layer, cup, thickness, taper, flip=False):
    """A cupped, rounded shell from rows of (centre, lateral, inward, half).

    Each row is (point, along, lateral, inward, half-width, tapered): the
    centre of the row, the unit vectors along the spine and across it, the
    unit vector to the concave side, and the half-width. The shell is two
    skins that meet along the rim, thickness fading to nothing in a
    quarter-ellipse so the edge is round.
    """
    count = len(rows)
    base = []
    for centre, _along, lateral, inward, half, _share in rows:
        line = []
        for j in range(nv + 1):
            xi = -math.cos(math.pi * j / nv)
            line.append(centre + lateral * (half * xi) + inward * (cup * half * xi * xi))
        base.append(line)
    top, bottom, coords = [], [], {}
    last = count - 1
    for i, line in enumerate(base):
        trow, brow = [], []
        share = rows[i][5]
        for j, p in enumerate(line):
            xi = -math.cos(math.pi * j / nv)
            fade = math.sqrt(max(0.0, 1.0 - abs(xi) ** 6))
            t = thickness * fade * (1.0 - taper * share)
            i0, i1 = max(i - 1, 0), min(i + 1, last)
            j0, j1 = max(j - 1, 0), min(j + 1, nv)
            normal = (base[i1][j] - base[i0][j]).cross(line[j1] - line[j0])
            if normal.length < 1e-12:
                normal = rows[i][3].copy()
            normal.normalize()
            if normal.dot(rows[i][3]) < 0:
                normal = -normal
            uv = (share, 0.5 + 0.5 * xi)
            if t < 1e-7 or (i == last and rows[i][4] == 0.0) or j in (0, nv):
                vert = bm.verts.new(p)
                trow.append(vert)
                brow.append(vert)
                coords[vert] = uv
            else:
                a = bm.verts.new(p + normal * (t / 2))
                b = bm.verts.new(p - normal * (t / 2))
                trow.append(a)
                brow.append(b)
                coords[a] = coords[b] = uv
        if i == last and rows[i][4] == 0.0:
            # A real tip: the whole row is one point.
            tip = trow[nv // 2]
            trow = [tip] * (nv + 1)
            brow = [tip] * (nv + 1)
        top.append(trow)
        bottom.append(brow)
    for i in range(count - 1):
        for j in range(nv):
            _face(bm, [top[i][j], top[i][j + 1], top[i + 1][j + 1], top[i + 1][j]])
            _face(bm, [bottom[i][j], bottom[i + 1][j], bottom[i + 1][j + 1], bottom[i][j + 1]])
    boundary = [e for e in bm.edges if e.is_boundary]
    if boundary:
        bmesh.ops.holes_fill(bm, edges=boundary, sides=0)
    return coords


def _apply_uvs(bm, uv_layer, coords):
    for face in bm.faces:
        for loop in face.loops:
            loop[uv_layer].uv = coords.get(loop.vert, (0.0, 0.0))


def petal_mesh(name, length, lean, hinge_r, count, half_max, cup=0.42,
               thickness=0.016, bend=0.4):
    """One petal, in its own frame: origin on the hinge, X outwards, Z up.

    Spoon-curved (cupped across, bent along), tapered to a tip, thick with a
    round rim, and a hinge barrel at the base. How wide it can be is set by
    the room the others leave when the bud is shut: at each height, the
    ring's circumference divided among `count` petals, less what the cupping
    takes off the edges. A closed ring therefore never touches itself.
    """
    steps, nv = 56, 20
    path = spine(length, lean, bend, steps)
    room = math.tan(math.pi / count) * 0.96
    rows = []
    for i, (x, z, a) in enumerate(path):
        u = i / steps
        radius = hinge_r + x
        # Cupping tucks the edges towards the axis by cup * half * cos(lean).
        fit = max(radius, 0.0) * room / (1.0 + cup * math.cos(a) * room)
        half = min(half_max * outline(u), fit)
        if u > 0.985:
            half = 0.0
        else:
            half = max(half, 0.006)
        rows.append((Vector((x, 0.0, z)), Vector((math.sin(a), 0.0, math.cos(a))),
                     Vector((0.0, 1.0, 0.0)), Vector((-math.cos(a), 0.0, math.sin(a))),
                     half, u))
    bm = bmesh.new()
    uv_layer = bm.loops.layers.uv.new("UVMap")
    coords = _grid_surface(bm, rows, nv, uv_layer, cup, thickness, 0.55)
    cylinder_y(bm, 0.024, rows[0][4] * 2 + 0.04, material_index=1)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    _apply_uvs(bm, uv_layer, coords)
    return _mesh(name, bm)


def leaf_half_width(share):
    """Half-width of a whole leaf along its length (0 at the stem)."""
    return 0.014 + 0.120 * math.sin(math.pi * share ** 0.85) ** 0.8


def arc_end(length, bow):
    """The far end of an arc of this length that bends down by `bow` degrees,
    in the arc's own frame (X along its start, Z up): (x, z)."""
    if abs(bow) < 1e-6:
        return length, 0.0
    b = math.radians(bow)
    radius = length / b
    return radius * math.sin(b), -radius * (1.0 - math.cos(b))


def leaf_mesh(name, start, end, length, bow, thickness=0.008, steps=16, nv=12):
    """One segment of a leaf, in its own frame: origin on its joint, X along
    the leaf's start, Z towards the concave side. The segment is an arc that
    bends down by `bow` degrees, so with the joints straight the three make
    one smooth arch. It takes the slice `start`..`end` of the leaf's outline,
    is cupped a little about the midrib, and carries a hinge barrel at its
    joint.
    """
    seg_len = length * (end - start)
    kappa = math.radians(bow) / seg_len
    rows = []
    for i in range(steps + 1):
        u = i / steps
        share = start + (end - start) * u
        half = leaf_half_width(share) if share < 0.995 else 0.0
        s_len = u * seg_len
        x, z = arc_end(s_len, bow * u)
        theta = -kappa * s_len
        rows.append((Vector((x, 0.0, z)), Vector((math.cos(theta), 0.0, math.sin(theta))),
                     Vector((0.0, 1.0, 0.0)), Vector((-math.sin(theta), 0.0, math.cos(theta))),
                     half, share))
    bm = bmesh.new()
    uv_layer = bm.loops.layers.uv.new("UVMap")
    coords = _grid_surface(bm, rows, nv, uv_layer, 0.26, thickness, 0.4)
    cylinder_y(bm, 0.011, max(rows[0][4] * 2 - 0.024, 0.028), material_index=1, segments=16)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    _apply_uvs(bm, uv_layer, coords)
    return _mesh(name, bm)


def stem_mesh(name):
    """The graphite stem: a collar on the pedestal, a slim shaft, and the cup
    at the top that the petals hinge on. Origin on the world's, so the cup
    stays where the hinge heights say."""
    bm = bmesh.new()
    z0 = PEDESTAL_TOP + 0.001
    rim = HUB_Z
    profile = [
        (0.0, z0),
        (0.20, z0), (0.205, z0 + 0.005), (0.19, z0 + 0.03), (0.15, z0 + 0.05),
        (0.075, z0 + 0.09), (0.045, z0 + 0.15), (0.034, z0 + 0.26),
        (0.030, z0 + 0.5), (0.030, rim - 0.30),
        (0.036, rim - 0.20), (0.06, rim - 0.12), (0.11, rim - 0.065),
        (0.17, rim - 0.035), (0.215, rim - 0.012), (0.232, rim + 0.012),
        (0.222, rim + 0.026), (0.205, rim + 0.026), (0.19, rim + 0.012),
        (0.14, rim - 0.015), (0.09, rim - 0.06), (0.04, rim - 0.10), (0.0, rim - 0.105),
    ]
    lathe(bm, profile, 72, 0)
    return _mesh(name, bm)


def pedestal_mesh(name):
    """A black glossy plinth with a thin gold ring set into its top."""
    bm = bmesh.new()
    top, r = PEDESTAL_TOP, PEDESTAL_RADIUS
    profile = [
        (0.0, 0.0), (r - 0.03, 0.0), (r - 0.012, 0.004), (r, 0.025),
        (r, 0.19), (r - 0.012, 0.215), (r - 0.04, 0.226),
        (r - 0.09, 0.226), (r - 0.10, 0.228), (r - 0.10, 0.262),
        (r - 0.108, 0.275), (r - 0.125, 0.285), (r - 0.145, top - 0.004),
        (r - 0.16, top), (0.0, top),
    ]
    lathe(bm, profile, 120, 0, sharp=(3, 4, 7, 8))
    torus_ring(bm, r - 0.34, top + 0.0005, 0.011, material_index=1)
    return _mesh(name, bm)


def core_mesh(name, count=34, seed=7):
    """A dome of stamens on a short post: thin filaments, each ending in a
    glowing capsule. Origin on the middle of the dome, so it turns about the
    flower's axis. Slots: 0 brass (dome, post, filaments), 1 the glowing tips.
    """
    import random
    rng = random.Random(seed)
    bm = bmesh.new()
    lathe(bm, [(0.0, -0.19), (0.024, -0.186), (0.026, -0.16), (0.026, -0.04), (0.05, -0.024),
               (0.074, -0.01), (0.084, 0.008), (0.078, 0.03), (0.05, 0.047), (0.0, 0.052)],
          40, 0)
    golden = math.pi * (3.0 - math.sqrt(5.0))
    for k in range(count):
        # A sunflower spiral over the dome: even spread, nothing in a line.
        share = (k + 0.5) / count
        radius = 0.050 * math.sqrt(share)
        angle = k * golden
        base = Vector((radius * math.cos(angle), radius * math.sin(angle),
                       0.05 - 3.0 * radius * radius))
        # The outer stamens lean out and the tallest stand in the middle, all
        # of them inside the shut inner petals.
        lean = math.radians(3.0 + 11.0 * math.sqrt(share)) * rng.uniform(0.85, 1.1)
        direction = Vector((math.sin(lean) * math.cos(angle), math.sin(lean) * math.sin(angle),
                            math.cos(lean))).normalized()
        height = (0.34 - 0.11 * share) * rng.uniform(0.92, 1.06)
        tip = base + direction * height
        tube(bm, [base, base + direction * height * 0.5, tip], [0.0042, 0.0034, 0.0030], 0)
        ellipsoid(bm, tip + direction * 0.014, (0.0165, 0.0165, 0.040), direction, 1)
    return _mesh(name, bm)


# ---------------------------------------------------------------------------
# the objects

def _new(collection, name, mesh, location, azimuth, mats):
    obj = bpy.data.objects.new(name, mesh)
    collection.objects.link(obj)
    obj.location = location
    obj.rotation_euler = (0.0, 0.0, math.radians(azimuth))
    for mat in mats:
        mesh.materials.append(mat)
    # What the Solid viewport shows: the material's own display colour, so
    # the recording reads well without a render.
    obj.color = tuple(mats[0].diffuse_color)
    # Valid at once, without waiting for the scene to be evaluated.
    obj.matrix_world = obj.matrix_basis.copy()
    return obj


def ring_azimuths(count, offset=0.0):
    return [FRONT + offset + 360.0 * k / count for k in range(count)]


def separation(azimuth):
    """The angle between an azimuth and the front, 0 to 180."""
    return abs((azimuth - FRONT + 180.0) % 360.0 - 180.0)


def leaf_layout():
    """Where each leaf stands on the stem and how it bends.

    Each leaf: azimuth, height on the stem, the length of each segment, how
    far each segment bows down along its own length, and for the curled and
    the open pose the pitch the first segment starts at (degrees from
    horizontal, positive up) and the bend added at each joint beyond keeping
    the line going. Open, the joints are straight and the three bowed
    segments make one smooth arch. Curled, the leaf is folded up close
    against the stem in three pleats: up, back down, and up again, each pleat
    nearly touching the last and none bent more than a joint can turn the
    short way round (under 180 degrees), so it sits in a column the width of
    the stem's collar instead of reaching out. A leaf is longer than the stem
    below the cup is tall, so it cannot simply stand straight up.
    """
    return [
        dict(name="Leaf A", azimuth=FRONT + 64.0, z=0.38, lengths=(0.42, 0.40, 0.36), bow=22.0,
             curled=dict(pitch=90.0, bends=(-145.0, 172.0)),
             opened=dict(pitch=62.0, bends=(0.0, 0.0))),
        dict(name="Leaf B", azimuth=FRONT - 64.0, z=0.58, lengths=(0.38, 0.36, 0.32), bow=22.0,
             curled=dict(pitch=90.0, bends=(-145.0, 172.0)),
             opened=dict(pitch=66.0, bends=(0.0, 0.0))),
    ]


def leaf_pose_params(spec, which):
    """The pitch and joint bends of a pose: "curled", "opened", or "mid", half
    way between, which the viewport tween goes through so that no segment is
    asked to turn more than about 96 degrees in one go."""
    if which != "mid":
        return spec[which]
    shut, open_ = spec["curled"], spec["opened"]
    return dict(pitch=(shut["pitch"] + open_["pitch"]) / 2.0,
                bends=tuple((a + b) / 2.0 for a, b in zip(shut["bends"], open_["bends"])))


def leaf_chain(spec, which):
    """Each segment of a leaf as (pitch, joint) in the leaf's own plane: the
    pitch it starts at and where its joint is, (x, z) from the stem."""
    pose = leaf_pose_params(spec, which)
    pitch, x, z = pose["pitch"], 0.0, 0.0
    out = []
    for i, length in enumerate(spec["lengths"]):
        out.append((pitch, (x, z)))
        ex, ez = arc_end(length, spec["bow"])
        p = math.radians(pitch)
        x += math.cos(p) * ex - math.sin(p) * ez
        z += math.sin(p) * ex + math.cos(p) * ez
        if i < len(pose["bends"]):
            pitch += -spec["bow"] + pose["bends"][i]
    return out


def leaf_poses(spec, which):
    """World matrices for the three segments of a leaf, curled or open. Each
    origin is a joint; each segment turns about its own Y."""
    azimuth = math.radians(spec["azimuth"])
    frame = (Matrix.Translation((0.030 * math.cos(azimuth), 0.030 * math.sin(azimuth), spec["z"]))
             @ Matrix.Rotation(azimuth, 4, "Z"))
    # A positive pitch lifts the leaf, which is a negative turn about Y.
    return [frame @ Matrix.Translation((x, 0.0, z)) @ Matrix.Rotation(-math.radians(pitch), 4, "Y")
            for pitch, (x, z) in leaf_chain(spec, which)]


def leaf_ends(spec):
    """Where each segment's far end is, in that segment's own frame."""
    out = []
    for length in spec["lengths"]:
        x, z = arc_end(length, spec["bow"])
        out.append(Vector((x, 0.0, z)))
    return out


def camera_pose(t):
    """The Promo Camera's world matrix, t = 0 at the closed bud and 1 when
    the bloom has finished: a slow push-in, about 20 degrees round, and a
    little rise to look into the open flower. Returns (matrix, target)."""
    t = min(max(t, 0.0), 1.0)
    k = t * t * (3.0 - 2.0 * t)
    azimuth = math.radians(FRONT - 14.0 + 22.0 * k)
    elevation = math.radians(6.0 + 13.0 * k)
    distance = 13.6 - 2.6 * k
    target = Vector((0.0, 0.0, 1.28 - 0.42 * k))
    offset = Vector((math.cos(elevation) * math.cos(azimuth),
                     math.cos(elevation) * math.sin(azimuth), math.sin(elevation)))
    location = target + offset * distance
    forward = (target - location).normalized()
    rotation = forward.to_track_quat("-Z", "Y").to_matrix().to_4x4()
    return Matrix.Translation(location) @ rotation, target


def build_flower(scene):
    """Build the closed bud in a new collection "CopyThat Flower" linked to
    `scene`, with the "Promo Camera" at the outro's first frame. Returns the
    parts in named groups; see the module docstring.
    """
    collection = bpy.data.collections.new(COLLECTION)
    scene.collection.children.link(collection)
    gold, pale, dark, bronze = satin_gold(), pearl(), graphite(), brass()
    leaf_dark, leaf_cap = leaf_graphite(), leaf_bronze()
    tips = glow()

    pedestal = _new(collection, "Pedestal", pedestal_mesh("Pedestal"), (0, 0, 0), 0,
                    [black_gloss(), gold_ring()])
    stem = _new(collection, "Stem", stem_mesh("Stem"), (0, 0, 0), 0, [dark])

    outer = []
    for k, azimuth in enumerate(ring_azimuths(OUTER_COUNT)):
        a = math.radians(azimuth)
        mesh = petal_mesh("Petal {:d}".format(k + 1), OUTER_LENGTH, OUTER_LEAN, OUTER_HINGE[0],
                          OUTER_COUNT, OUTER_HALF)
        outer.append(_new(collection, "Petal {:d}".format(k + 1), mesh,
                          (OUTER_HINGE[0] * math.cos(a), OUTER_HINGE[0] * math.sin(a), OUTER_HINGE[1]),
                          azimuth, [gold, dark]))
    inner = []
    for k, azimuth in enumerate(ring_azimuths(INNER_COUNT)):
        a = math.radians(azimuth)
        mesh = petal_mesh("Inner {:d}".format(k + 1), INNER_LENGTH, INNER_LEAN, INNER_HINGE[0],
                          INNER_COUNT, INNER_HALF, cup=0.38, thickness=0.011)
        inner.append(_new(collection, "Inner {:d}".format(k + 1), mesh,
                          (INNER_HINGE[0] * math.cos(a), INNER_HINGE[0] * math.sin(a), INNER_HINGE[1]),
                          azimuth, [pale, bronze]))
    core = _new(collection, "Core", core_mesh("Core"), (0, 0, CORE_BASE), 0, [bronze, tips])

    leaves = []
    for spec in leaf_layout():
        poses = leaf_poses(spec, "curled")
        shares = [0.0]
        for length in spec["lengths"]:
            shares.append(shares[-1] + length)
        shares = [s / shares[-1] for s in shares]
        chain = []
        for n, (pose, start, end) in enumerate(zip(poses, shares, shares[1:])):
            name = "{:s}{:d}".format(spec["name"], n + 1)
            obj = _new(collection, name,
                       leaf_mesh(name, start, end, sum(spec["lengths"]), spec["bow"]),
                       (0, 0, 0), 0, [leaf_dark, leaf_cap])
            obj.matrix_world = pose
            chain.append(obj)
        leaves.append(chain)

    camera_data = bpy.data.cameras.new("Promo Camera")
    camera_data.lens = CAMERA_LENS
    camera_data.sensor_width = 36.0
    camera_data.clip_start = 0.1
    camera_data.clip_end = 200.0
    camera = bpy.data.objects.new("Promo Camera", camera_data)
    collection.objects.link(camera)
    camera.matrix_world = camera_pose(0.0)[0]
    # The camera is the user's to look through, not to drag; it also gets the
    # Solid viewport's own colour so it is not drawn black.
    scene.camera = camera

    everything = [pedestal, stem, *outer, *inner, core]
    everything += [obj for chain in leaves for obj in chain] + [camera]
    return {"outer": outer, "inner": inner, "core": core, "stem": stem,
            "pedestal": pedestal, "leaves": leaves, "camera": camera,
            "all": everything}


# ---------------------------------------------------------------------------
# the rig, as a scene generator

def closed_places(parts):
    """Where every moving part stands now, by name."""
    bpy.context.view_layer.update()
    return {obj.name: obj.matrix_world.copy() for obj in parts["all"]}


def _select(objects, active=None):
    layer = bpy.context.view_layer
    for obj in layer.objects:
        obj.select_set(False)
    for obj in objects:
        obj.select_set(True)
    layer.objects.active = active or objects[0]


def _rig():
    return bpy.context.scene.rigmoves_rig


def _move():
    return _rig().rigmoves.moves[0]


def flower_steps(parts, frames=150):
    """Rig the flower with CopyThat exactly as a user would, as a scene
    generator (the contract is in SPEC.md): New Move on the leaders, the core
    and the leaves; pose them open and Record After; Ride Along for the
    other petals with a Lead each; Follows and Timing; Build Sliders; Frames
    and Animate. Only `bpy.ops.rigmoves.*` does the work.
    """
    outer, inner, core = parts["outer"], parts["inner"], parts["core"]
    leaves = [seg for chain in parts["leaves"] for seg in chain]
    camera = parts["camera"]
    leader, inner_leader = outer[0], inner[0]
    riders = outer[1:]
    inner_riders = inner[1:]
    home = closed_places(parts)

    def open_pose(obj, degrees):
        return home[obj.name] @ Matrix.Rotation(math.radians(degrees), 4, "Y")

    targets = [(leader, open_pose(leader, OUTER_OPEN)),
               (inner_leader, open_pose(inner_leader, INNER_OPEN)),
               (core, Matrix.Translation((0.0, 0.0, CORE_RISE)) @ home[core.name]
                @ Matrix.Rotation(math.radians(CORE_TURN), 4, "Z"))]
    unfurled = []
    for spec, chain in zip(leaf_layout(), parts["leaves"]):
        # Parents first, so a follower is never dragged by its leader after
        # it has been put in place. The leaves go half way with the others,
        # then the rest of the way: a tween turns each segment by the short
        # way round and straight in the viewport, and the curled leaf is
        # folded too far to cross in one.
        targets += list(zip(chain, leaf_poses(spec, "mid")))
        unfurled += list(zip(chain, leaf_poses(spec, "opened")))

    def new_move():
        _select([leader, inner_leader, core] + leaves, active=leader)
        assert bpy.ops.rigmoves.new_move() == {"FINISHED"}

    def pivots():
        # The 3D cursor on each joint, then Pivot: Cursor, as the guide says.
        scene = bpy.context.scene
        for obj in leaves:
            scene.cursor.location = obj.matrix_world.translation
            _select([obj])
            assert bpy.ops.rigmoves.set_pivot(index=0, kind="CURSOR") == {"FINISHED"}

    def record_after():
        _select([leader, inner_leader, core] + leaves, active=leader)
        assert bpy.ops.rigmoves.record(index=0, which="AFTER") == {"FINISHED"}

    def ride(group, head):
        def go():
            _select(list(group) + [head], active=head)
            assert bpy.ops.rigmoves.ride_along(
                index=0, leader=head.name, rig_name=_rig().name) == {"FINISHED"}
        return go

    def leads():
        move = _move()
        for group, apart, per_step in ((riders, 45.0, OUTER_LEAD_PER_STEP),
                                       (inner_riders, 60.0, INNER_LEAD_PER_STEP)):
            for obj in group:
                azimuth = math.degrees(home[obj.name].to_euler().z)
                move.parts[obj.name].lead = round(separation(azimuth) / apart) * per_step

    def follows_and_timing():
        move = _move()
        for chain in parts["leaves"]:
            for before, after in zip(chain, chain[1:]):
                move.parts[after.name].follows = before.name
        move.parts[inner_leader.name].start = INNER_DELAY
        move.parts[core.name].start = CORE_DELAY
        for obj, delay in zip(parts["leaves"][0] + parts["leaves"][1], LEAF_DELAYS * 2):
            move.parts[obj.name].start = delay
        move.ease = EASE

    def build():
        _select([leader], active=leader)
        assert bpy.ops.rigmoves.build() == {"FINISHED"}

    def animate():
        scene = bpy.context.scene
        move = _move()
        move.play_frames = frames
        scene.frame_start = 1
        scene.frame_set(1)
        assert bpy.ops.rigmoves.animate(index=0) == {"FINISHED"}
        scene.frame_end = 1 + frames
        scene.frame_set(1)

    def play():
        # Not when there is no window to play in: the headless runner.
        if bpy.app.background:
            return
        try:
            bpy.ops.screen.animation_play()
        except RuntimeError:
            pass

    yield ("caption", "4 · Rig something real", "New Move: where it stands is Before")
    yield ("call", new_move)
    yield ("wait", 0.8)
    yield ("caption", None, "Pivot on each leaf joint: the 3D cursor")
    yield ("call", pivots)
    yield ("wait", 0.6)
    yield ("caption", None, "Pose one petal, the core and the leaves open")
    yield ("tween", targets, 1.6)
    yield ("tween", unfurled, 0.9)
    yield ("caption", None, "Record After")
    yield ("call", record_after)
    yield ("wait", 0.7)
    yield ("caption", None, "Ride Along: the other petals copy it, from their own place")
    yield ("call", ride(riders, leader))
    yield ("wait", 0.5)
    yield ("call", ride(inner_riders, inner_leader))
    yield ("wait", 0.6)
    yield ("caption", None, "Lead: a wave runs round the ring")
    yield ("call", leads)
    yield ("wait", 0.6)
    yield ("caption", None, "Follows and Timing: the leaves hang from each other")
    yield ("call", follows_and_timing)
    yield ("wait", 0.6)
    yield ("caption", None, "Build Sliders: one slider plays it all")
    yield ("call", build)
    yield ("wait", 0.6)
    yield ("caption", None, "Animate: the flower blooms in {:d} frames".format(frames))
    yield ("call", animate)
    yield ("view", {"camera": camera})
    yield ("wait", 0.5)
    yield ("call", play)


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


if __name__ == "__main__":
    build_bare_scene(fast=True)
