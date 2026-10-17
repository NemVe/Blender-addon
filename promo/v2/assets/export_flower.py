"""Export the flower of the demo result for the Three.js film: flower.glb and flower_motion.json.

    blender --background --factory-startup promo/files/CopyThat_demo_result.blend \
            --python promo/v2/assets/export_flower.py -- promo/v2/assets

Blender 5.2 (the file is the finished rig: 21 parts, 22 deform bones, one slider).

flower.glb      every part at rest (the shut bud), flat under a few group nodes that sit at the origin,
                so a part's node transform is its world transform. Names are the object names, the
                materials are the file's, simple (base colour, metal, roughness, coat, emission).
flower_motion.json
                for the frames 1-151 (30 fps in Blender) the world transform of each moving part, as
                [px, py, pz, qx, qy, qz, qw, sx, sy, sz] in the same space as the glb: glTF's, Y up
                (x, z, -y of Blender). Also the slider (0 at frame 1, 1 at frame 151, linear), the groups
                with the leader first, the ring angles, the core glow and the camera.

A bound part follows one bone with weight 1, so its mesh moves rigidly:
    M = rig.matrix_world @ pose_bone.matrix @ bone.matrix_local.inverted() @ rig.matrix_world.inverted()
    world transform of the part at frame f = M @ its world transform at rest
That is checked against the mesh Blender evaluates (the Armature modifier), and then again the way Three.js
will use it: the vertices in the glb, moved by the transforms as written in the json, against the evaluated
mesh. The largest errors are printed and stored in the json.
"""

import json
import math
import os
import re
import struct
import sys

import bpy
import numpy as np
from mathutils import Matrix
from mathutils.kdtree import KDTree

OUT = sys.argv[sys.argv.index("--") + 1]
CHECK_FRAMES = (1, 38, 75, 113, 151)
DECIMALS = 6

scene = bpy.context.scene
rig = bpy.data.objects["CopyThat Rig"]
camera = bpy.data.objects["Promo Camera"]
FIRST, LAST = scene.frame_start, scene.frame_end

# Blender (Z up) to glTF (Y up): x, z, -y. A proper rotation, so it keeps the handedness.
C = Matrix(((1, 0, 0, 0), (0, 0, 1, 0), (0, -1, 0, 0), (0, 0, 0, 1)))
C_INV = C.inverted()
C3 = np.array(C)[:3, :3]


def to_gltf(m):
    return C @ m @ C_INV


def trs(m, previous=None):
    """[px, py, pz, qx, qy, qz, qw, sx, sy, sz] of a matrix; the quaternion keeps the sign of the last one."""
    loc, rot, sc = m.decompose()
    q = [rot.x, rot.y, rot.z, rot.w]
    if previous is not None and sum(a * b for a, b in zip(q, previous[3:7])) < 0:
        q = [-v for v in q]
    return [round(v, DECIMALS) + 0.0 for v in (loc.x, loc.y, loc.z, *q, sc.x, sc.y, sc.z)]    # + 0.0: no -0.0 in the file


def compose(t):
    x, y, z, w = (v / math.sqrt(sum(u * u for u in t[3:7])) for v in t[3:7])
    r = np.array(((1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)),
                  (2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)),
                  (2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y))))
    m = np.eye(4)
    m[:3, :3] = r * np.array(t[7:10])
    m[:3, 3] = t[0:3]
    return m


# ---------------------------------------------------------------- the parts
meshes = [o for o in scene.objects if o.type == "MESH" and o.name != "Cyclorama"]
moving = [o for o in meshes if any(m.type == "ARMATURE" for m in o.modifiers)]
static = [o for o in meshes if o not in moving]
names_moving = [o.name for o in moving]
assert len(moving) == 21, names_moving

bone_of = {}
for o in moving:
    assert len(o.vertex_groups) == 1, o.name
    bone = o.vertex_groups[0].name
    assert bone in rig.data.bones, bone
    for v in o.data.vertices:    # bound to that one bone, at weight 1: the mesh moves as one piece
        assert len(v.groups) == 1 and abs(v.groups[0].weight - 1.0) < 1e-6, (o.name, v.index)
    bone_of[o.name] = bone

GROUPS = (   # key, node name (None: the part hangs straight on the root), parts in chain order
    ("outer_petals", "Outer Petals", [n for n in names_moving if n.startswith("Outer Leader")]),
    ("inner_petals", "Inner Petals", [n for n in names_moving if n.startswith("Inner Leader")]),
    ("core", None, ["Core"]),
    ("leaf_a", "Leaf A", ["Leaf 1", "Leaf 2", "Leaf 3"]),
    ("leaf_b", "Leaf B", ["Leaf 1 2", "Leaf 2 2", "Leaf 3 2"]),
    ("stem", None, ["Stem"]),
    ("pedestal", None, ["Pedestal"]),
)
assert sorted(n for _k, _g, ns in GROUPS for n in ns) == sorted(o.name for o in meshes)

scene.frame_set(FIRST)
rest_world = {o.name: o.matrix_world.copy() for o in meshes}
rest_co = {o.name: np.array([tuple(v.co) for v in o.data.vertices], dtype=np.float64) for o in meshes}

# Ring order: the leader first, then by the angle about the world Z axis from the leader.
leader_names = {"outer_petals": "Outer Leader", "inner_petals": "Inner Leader", "leaf_b": "Leaf 1 2"}


def z_angle(m):
    return math.degrees(math.atan2(m[1][0], m[0][0]))


ring = {}
ordered = {}
for key, _node, names in GROUPS:
    if key in ("outer_petals", "inner_petals"):
        lead = rest_world[leader_names[key]]
        angles = {n: round((z_angle(rest_world[n]) - z_angle(lead)) % 360.0, 3) for n in names}
        # the copies are the leader turned about world Z through the origin: that is how Ring made them
        worst = 0.0
        for n in names:
            turned = Matrix.Rotation(math.radians(angles[n]), 4, "Z") @ lead
            worst = max(worst, max(abs(a - b) for ra, rb in zip(turned, rest_world[n]) for a, b in zip(ra, rb)))
        ordered[key] = sorted(names, key=lambda n: angles[n])
        ring[key] = {"count": len(names), "step_deg": round(360.0 / len(names), 3), "about_gltf": [0, 1, 0],
                     "centre": [0, 0, 0], "angles_deg": [angles[n] for n in ordered[key]],
                     "max_error_turning_the_leader": round(worst, 7)}
        assert ordered[key][0] == leader_names[key], ordered[key]
    else:
        ordered[key] = list(names)
# the second leaf is the first one turned about world Z, too
leaf_angle = (z_angle(rest_world["Leaf 1 2"]) - z_angle(rest_world["Leaf 1"])) % 360.0
worst = 0.0
for a, b in (("Leaf 1", "Leaf 1 2"), ("Leaf 2", "Leaf 2 2"), ("Leaf 3", "Leaf 3 2")):
    turned = Matrix.Rotation(math.radians(leaf_angle), 4, "Z") @ rest_world[a]
    worst = max(worst, max(abs(p - q) for ra, rb in zip(turned, rest_world[b]) for p, q in zip(ra, rb)))
ring["leaf_b"] = {"copy_of": "leaf_a", "angle_deg": round(leaf_angle, 3), "about_gltf": [0, 1, 0], "centre": [0, 0, 0],
                  "max_error_turning_leaf_a": round(worst, 7)}

# When each part moves along the slider: the drivers of the Action constraints hold a window of it.
window = {}
for d in rig.animation_data.drivers:
    m = re.match(r'pose\.bones\["(.+)"\]\.constraints\["RigMoves: Move 1"\]\.eval_time', d.data_path)
    if m:
        e = d.driver.expression
        s = re.search(r"\(rm_v-([0-9.]+)\)/([0-9.]+)", e)
        if s:
            a, w = float(s.group(1)), float(s.group(2))
        else:
            a, w = 0.0, float(re.search(r"rm_v/([0-9.]+)", e).group(1))
        window[m.group(1)] = [round(a, 4), round(min(1.0, a + w), 4)]

# ---------------------------------------------------------------- sample the frames
motion = {n: [] for n in names_moving}
slider, glow, cam = [], [], []
check_world = {}    # frame -> part -> evaluated vertices in Blender world space
glow_curve = None
mat = bpy.data.materials["Core Glow"]
for lay in mat.node_tree.animation_data.action.layers:
    for st in lay.strips:
        for cb in st.channelbags:
            for fc in cb.fcurves:
                if "default_value" in fc.data_path:
                    glow_curve = fc
assert glow_curve is not None
glow_color = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED").inputs["Emission Color"].default_value[:3]

cam_fov = None
for frame in range(FIRST, LAST + 1):
    scene.frame_set(frame)
    dg = bpy.context.evaluated_depsgraph_get()
    rig_eval = rig.evaluated_get(dg)
    slider.append(round(rig_eval.pose.bones["Root"]["Move 1"], 6))
    glow.append(round(glow_curve.evaluate(frame), 5))
    for o in moving:
        bone = bone_of[o.name]
        skin = rig.matrix_world @ rig_eval.pose.bones[bone].matrix @ rig.data.bones[bone].matrix_local.inverted() @ rig.matrix_world.inverted()
        prev = motion[o.name][-1] if motion[o.name] else None
        motion[o.name].append(trs(to_gltf(skin @ rest_world[o.name]), prev))
    cam_eval = camera.evaluated_get(dg)
    cam.append(trs(to_gltf(cam_eval.matrix_world.copy()), cam[-1] if cam else None))
    if frame in CHECK_FRAMES:
        check_world[frame] = {}
        for o in moving:
            oe = o.evaluated_get(dg)
            me = oe.to_mesh()
            co = np.empty(len(me.vertices) * 3)
            me.vertices.foreach_get("co", co)
            co = co.reshape(-1, 3)
            assert len(co) == len(rest_co[o.name])
            w = np.array(o.matrix_world)
            check_world[frame][o.name] = co @ w[:3, :3].T + w[:3, 3]
            oe.to_mesh_clear()

# a long lens on a wide sensor, 16:9: Blender fits the sensor to the longer side
cd = camera.data
aspect = scene.render.resolution_x / scene.render.resolution_y
fov_x = 2 * math.atan(cd.sensor_width / (2 * cd.lens))
fov_y = 2 * math.atan(math.tan(fov_x / 2) / aspect)

# 1) the formula against the mesh Blender evaluates (Blender space, no glTF involved)
C_N = np.array(C)
worst_formula = 0.0
for frame in CHECK_FRAMES:
    for o in moving:
        mb = np.linalg.inv(C_N) @ compose(motion[o.name][frame - FIRST]) @ C_N     # the written transform, back in Blender space
        pred = rest_co[o.name] @ mb[:3, :3].T + mb[:3, 3]
        worst_formula = max(worst_formula, np.abs(pred - check_world[frame][o.name]).max())
print("CHECK formula vs evaluated mesh (frames {}): worst vertex error {:.2e} m".format(CHECK_FRAMES, worst_formula))

# ---------------------------------------------------------------- the glb
scene.frame_set(FIRST)
col = bpy.data.collections.new("Flower Export")
scene.collection.children.link(col)
root = bpy.data.objects.new("Flower", None)
col.objects.link(root)
group_node = {}
for key, node, _names in GROUPS:
    if node:
        e = bpy.data.objects.new(node, None)
        col.objects.link(e)
        e.parent = root
        group_node[key] = e
by_name = {o.name: o for o in meshes}
for o in meshes:        # the originals make room for the copies that carry their names
    o.name = "~" + o.name
    o.data.name = "~" + o.data.name
for key, _node, names in GROUPS:
    for n in ordered[key]:
        src = by_name[n]
        me = src.data.copy()
        me.name = n
        c = bpy.data.objects.new(n, me)
        col.objects.link(c)
        c.parent = group_node.get(key, root)
        c.matrix_world = rest_world[n]
bpy.context.view_layer.update()
for o in scene.objects:
    o.select_set(o.name == "Flower" or o.name in col.objects)
props = bpy.ops.export_scene.gltf.get_rna_type().properties.keys()
want = {"filepath": os.path.join(OUT, "flower.glb"), "export_format": "GLB", "use_selection": True, "export_yup": True,
        "export_apply": False, "export_materials": "EXPORT", "export_normals": True, "export_texcoords": True,
        "export_cameras": False, "export_lights": False, "export_animations": False, "export_skins": False,
        "export_morph": False}
bpy.ops.export_scene.gltf(**{k: v for k, v in want.items() if k in props})
glb_path = os.path.join(OUT, "flower.glb")
print("GLB", os.path.getsize(glb_path), "bytes")

# ---------------------------------------------------------------- read the glb back, as Three.js will
raw = open(glb_path, "rb").read()
length = struct.unpack_from("<I", raw, 8)[0]
off, js, blob = 12, None, None
while off < length:
    clen, ctype = struct.unpack_from("<II", raw, off)
    off += 8
    if ctype == 0x4E4F534A:
        js = json.loads(raw[off:off + clen])
    elif ctype == 0x004E4942:
        blob = raw[off:off + clen]
    off += clen


def accessor(i):
    a = js["accessors"][i]
    assert a["componentType"] == 5126 and a["type"] == "VEC3" and "sparse" not in a
    bv = js["bufferViews"][a["bufferView"]]
    start = bv.get("byteOffset", 0) + a.get("byteOffset", 0)
    stride = bv.get("byteStride", 12)
    if stride == 12:
        return np.frombuffer(blob, dtype=np.float32, count=a["count"] * 3, offset=start).reshape(-1, 3).astype(np.float64)
    return np.array([struct.unpack_from("<3f", blob, start + k * stride) for k in range(a["count"])])


def node_matrix(n):
    if "matrix" in n:
        return np.array(n["matrix"]).reshape(4, 4).T
    return compose(list(n.get("translation", (0, 0, 0))) + list(n.get("rotation", (0, 0, 0, 1))) + list(n.get("scale", (1, 1, 1))))


glb_nodes = {}      # name -> (world matrix at rest, the mesh's positions)


def walk(i, parent):
    n = js["nodes"][i]
    m = parent @ node_matrix(n)
    if "mesh" in n:
        pos = np.concatenate([accessor(p["attributes"]["POSITION"]) for p in js["meshes"][n["mesh"]]["primitives"]])
        glb_nodes[n["name"]] = (m, pos)
    for c in n.get("children", []):
        walk(c, m)


for r in js["scenes"][js.get("scene", 0)]["nodes"]:
    walk(r, np.eye(4))
assert sorted(glb_nodes) == sorted(by_name), (sorted(glb_nodes), sorted(by_name))

# 2) the glb and the json as Three.js uses them against the evaluated mesh
worst_rest = worst_glb = 0.0
vertices_checked = 0
for n, (m_rest, pos) in glb_nodes.items():
    kd = KDTree(len(rest_co[n]))
    for i, p in enumerate(rest_co[n] @ C3.T):       # a vertex of the mesh as the glb stores it
        kd.insert(tuple(p), i)
    kd.balance()
    index = np.empty(len(pos), dtype=int)
    for i, p in enumerate(pos):
        _co, j, dist = kd.find(tuple(p))
        assert dist < 1e-5, (n, i, dist)
        index[i] = j
    world_rest = C_N @ np.array(rest_world[n])
    ref_rest = rest_co[n][index] @ world_rest[:3, :3].T + world_rest[:3, 3]      # C @ rest_world @ vertex
    got_rest = pos @ m_rest[:3, :3].T + m_rest[:3, 3]
    worst_rest = max(worst_rest, np.abs(ref_rest - got_rest).max())
    vertices_checked += len(pos)
    if n in motion:
        for frame in CHECK_FRAMES:
            mf = compose(motion[n][frame - FIRST])
            got = pos @ mf[:3, :3].T + mf[:3, 3]
            ref = check_world[frame][n][index] @ C3.T       # the evaluated vertex, in glTF space
            worst_glb = max(worst_glb, np.abs(got - ref).max())
print("CHECK glb at rest vs the file: worst vertex error {:.2e} m over {:d} vertices".format(worst_rest, vertices_checked))
print("CHECK glb + json vs evaluated mesh (frames {}): worst vertex error {:.2e} m".format(CHECK_FRAMES, worst_glb))
frame1_vs_rest = max(np.abs(compose(motion[n][0]) - glb_nodes[n][0]).max() for n in names_moving)
print("CHECK frame 1 equals the rest pose: {:.2e}".format(frame1_vs_rest))

# ---------------------------------------------------------------- the json
parts = {}
mats = {n: [s.material.name for s in o.material_slots if s.material] for n, o in by_name.items()}
for key, _node, names in GROUPS:
    for i, n in enumerate(ordered[key]):
        bone = bone_of.get(n)
        parent_bone = rig.data.bones[bone].parent.name if bone and rig.data.bones[bone].parent.name != "Root" else None
        parts[n] = {"group": key, "index": i, "moving": n in bone_of, "bone": bone,
                    "follows": parent_bone, "window": window.get(bone), "materials": mats[n],
                    "rest": trs(to_gltf(rest_world[n]))}
for key in ("outer_petals", "inner_petals"):
    for n, a in zip(ordered[key], ring[key]["angles_deg"]):
        parts[n]["ring_angle_deg"] = a

lo = np.array([1e9] * 3)
hi = np.array([-1e9] * 3)
for n, (m, pos) in glb_nodes.items():
    p = pos @ m[:3, :3].T + m[:3, 3]
    lo, hi = np.minimum(lo, p.min(axis=0)), np.maximum(hi, p.max(axis=0))

data = {
    "meta": {
        "source": "promo/files/CopyThat_demo_result.blend, Blender " + bpy.app.version_string,
        "glb": "flower.glb",
        "frames": {"first": FIRST, "last": LAST, "count": LAST - FIRST + 1, "fps": scene.render.fps},
        "space": "glTF, Y up, metres: (x, z, -y) of Blender. The glb parts sit at rest; a part's node transform is its world transform.",
        "transform": "[px, py, pz, qx, qy, qz, qw, sx, sy, sz]; motion[name][frame - first] is the part's world transform at that frame. Moving parts are 21, the stem and pedestal never move.",
        "slider": "slider[frame - first]: the Move 1 value, 0 at the first frame and 1 at the last, linear in the frame",
        "sampling": "30 fps. For 60 fps lerp the position and scale and slerp the quaternion between two samples (the quaternion keeps its sign from one sample to the next).",
        "bounds_at_rest": {"min": [round(v, 4) for v in lo], "max": [round(v, 4) for v in hi]},
        "checks": {"frames": list(CHECK_FRAMES), "formula_vs_evaluated_mesh_m": float("{:.3g}".format(worst_formula)),
                   "glb_and_json_vs_evaluated_mesh_m": float("{:.3g}".format(worst_glb)),
                   "glb_at_rest_vs_file_m": float("{:.3g}".format(worst_rest)), "vertices": vertices_checked},
    },
    "groups": {key: ordered[key] for key, _n, _ns in GROUPS},
    "group_nodes": {key: (node or None) for key, node, _ns in GROUPS},
    "ring": ring,
    "parts": parts,
    "slider": slider,
    "core_glow": {"what": "emission strength of the Core Glow material, per frame. The glb holds colour x strength at the first frame "
                          "(0.35); in Three.js set emissive to colour and emissiveIntensity to values[frame - first]",
                  "color": [round(v, 5) for v in glow_color], "values": glow},
    "camera": {"what": "Promo Camera, per frame, same transform layout; it looks down -Z like a Three.js camera",
               "fov_y_deg": round(math.degrees(fov_y), 4), "aspect": round(aspect, 5), "near": round(cd.clip_start, 4),
               "far": round(cd.clip_end, 3), "frames": cam},
    "motion": motion,
}
path = os.path.join(OUT, "flower_motion.json")
with open(path, "w", encoding="utf-8") as fh:
    fh.write("{\n")
    items = list(data.items())
    for i, (k, v) in enumerate(items):
        if k == "motion":
            fh.write(' "motion": {\n')
            rows = list(v.items())
            for j, (n, frames) in enumerate(rows):
                fh.write('  {}: {}{}\n'.format(json.dumps(n), json.dumps(frames, separators=(",", ":")), "," if j < len(rows) - 1 else ""))
            fh.write(" }\n")
        else:
            fh.write(" {}: {}{}\n".format(json.dumps(k), json.dumps(v, separators=(",", ":")), "," if i < len(items) - 1 else ""))
    fh.write("}\n")
print("JSON", os.path.getsize(path), "bytes")
