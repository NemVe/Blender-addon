"""The in-Blender promo script, run against the real add-on with no screen.

    /home/user/Blender-addon/.venv/bin/python test_headless.py

Every scene generator is run by the same Player the live show uses, with each
tween jumped to its end and each wait skipped. After a scene the tests check
that Build said it worked, and that Play puts the parts where they belong - in
the evaluated, deformed mesh, not in the objects' own transforms, which the
rig never moves. The live path (timer ticks on a fake clock, the real window,
area and viewport objects Blender keeps even without a screen) and the bundled
dist file are run as well. Only the drawing itself needs a real screen, and
even that is run against a recording painter.
"""

import importlib.util
import math
import os
import runpy
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PROMO = os.path.dirname(HERE)
FLOWER_PATH = os.path.join(PROMO, "flower", "flower.py")
DIST = os.path.join(HERE, "dist", "copythat_promo.py")
ADDON = os.environ.get("COPYTHAT_ADDON", "/home/user/Blender-addon")

sys.path.insert(0, ADDON)
sys.path.insert(0, HERE)

import bpy  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import bundle  # noqa: E402
import rigmoves  # noqa: E402

TOLERANCE = 1e-3

# Only used when the real flower.py is not there yet: just enough of the
# contract to run scene 4's wrapper. The real thing is used whenever it exists.
STAND_IN = '''
import bpy
from mathutils import Matrix, Vector

def build_flower(scene):
    collection = bpy.data.collections.new("CopyThat Flower")
    scene.collection.children.link(collection)
    objects = []
    for k in range(3):
        mesh = bpy.data.meshes.new("Petal {:d}".format(k))
        mesh.from_pydata([(-.1, 0, 0), (.1, 0, 0), (.1, 0, .5), (-.1, 0, .5)], [], [(0, 1, 2, 3)])
        obj = bpy.data.objects.new("Petal {:d}".format(k), mesh)
        obj.location = (k * 0.5, 0, 0)
        collection.objects.link(obj)
        objects.append(obj)
    cam = bpy.data.objects.new("Promo Camera", bpy.data.cameras.new("Promo Camera"))
    cam.location = (0, -8, 2)
    cam.rotation_euler = (1.4, 0, 0)
    collection.objects.link(cam)
    scene.camera = cam
    return {"outer": objects, "camera": cam, "all": objects + [cam]}

def flower_steps(parts, frames=150):
    leader, rider = parts["outer"][0], parts["outer"][1]
    def select(objs, active):
        for o in bpy.context.view_layer.objects:
            o.select_set(False)
        for o in objs:
            o.select_set(True)
        bpy.context.view_layer.objects.active = active
    yield ("caption", "4 \\u00b7 Rig something real", "New Move")
    yield ("call", lambda: (select([leader], leader), bpy.ops.rigmoves.new_move()))
    yield ("tween", [(leader, Matrix.Translation((0, 0, 1)) @ leader.matrix_world)], 1.0)
    yield ("call", lambda: bpy.ops.rigmoves.record(index=0, which="AFTER"))
    yield ("call", lambda: (select([rider, leader], leader), bpy.ops.rigmoves.ride_along(
        index=0, leader=leader.name, rig_name=bpy.context.scene.rigmoves_rig.name)))
    yield ("call", lambda: bpy.ops.rigmoves.build())
    yield ("view", {"camera": parts["camera"]})
    yield ("wait", 0.5)
'''


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


HAVE_FLOWER = os.path.isfile(FLOWER_PATH)
promo = None


def setUpModule():
    global promo
    rigmoves.register()
    promo = load(os.path.join(HERE, "copythat_promo.py"), "copythat_promo_source")
    promo.attach_flower(read(FLOWER_PATH) if HAVE_FLOWER else STAND_IN)
    promo.FULL_VIEWPORT = False


def tearDownModule():
    rigmoves.unregister()


# ---------------------------------------------------------------------------
# measuring, the way tests/test_rigmoves.py does

def world_points(obj):
    """Where the mesh really is, after the rig has deformed it."""
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    points = [evaluated.matrix_world @ v.co for v in mesh.vertices]
    evaluated.to_mesh_clear()
    return points


def placed(obj, matrix):
    """The object's own mesh, standing at this matrix."""
    return [matrix @ v.co for v in obj.data.vertices]


def drift(obj, expected):
    return max((a - b).length for a, b in zip(world_points(obj), expected))


def centre(obj):
    points = world_points(obj)
    return sum(points, Vector()) / len(points)


def play(move, percent):
    move.play = percent
    bpy.context.view_layer.update()


def window():
    return bpy.context.window


def viewport():
    area = next(a for a in window().screen.areas if a.type == "VIEW_3D")
    return area, area.spaces.active


def switch(scene):
    window().scene = scene


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


class Case(unittest.TestCase):

    def setUp(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        promo.SCENES = [1, 2, 3, 4]
        promo.FULL_VIEWPORT = False
        promo.SPEED = 1.0
        promo.COUNTDOWN = 5

    def run_scenes(self, numbers, watch=None):
        show = promo.Show(numbers, instant=True)
        show.run_instant(watch)
        return show

    def the_move(self, show, number):
        data = show.scenes[number].rigmoves_rig.rigmoves
        self.assertEqual(len(data.moves), 1)
        return data.moves[0]

    def check_drivers(self, show, number):
        """Every driver the build made runs with Auto Run Python Scripts off,
        and fits the 256 characters Blender keeps."""
        rig = show.scenes[number].rigmoves_rig
        ours = [c for c in rig.animation_data.drivers if "constraints[" in c.data_path]
        self.assertTrue(ours)
        for curve in ours:
            self.assertTrue(curve.driver.is_valid, curve.driver.expression)
            self.assertTrue(curve.driver.is_simple_expression, curve.driver.expression)
            self.assertLess(len(curve.driver.expression), 256)


class TestSceneOne(Case):

    def test_one_cube_plays_from_before_to_after(self):
        show = self.run_scenes([1])
        parts = show.parts[1]
        cube = parts["cube"]
        move = self.the_move(show, 1)
        data = move.id_data.rigmoves
        # Build said it worked, in the add-on's own words.
        self.assertRegex(data.report, r"^1 part\(s\) on 1 slider\(s\)\.")
        self.assertTrue(move.built)
        self.check_drivers(show, 1)
        # The tween ended exactly on the After that was recorded, and Build
        # put the cube back on its Before.
        self.assertLess(drift(cube, placed(cube, parts["start"])), TOLERANCE)
        play(move, 100.0)
        self.assertLess(drift(cube, placed(cube, parts["end"])), TOLERANCE)
        play(move, 0.0)
        self.assertLess(drift(cube, placed(cube, parts["start"])), TOLERANCE)

    def test_the_slide_ends_at_zero_and_half_way_is_between(self):
        show = self.run_scenes([1])
        parts, move = show.parts[1], self.the_move(show, 1)
        self.assertAlmostEqual(move.play, 0.0, places=3)
        play(move, 50.0)
        low, high = parts["start"].translation.z, parts["end"].translation.z
        self.assertTrue(low + 0.2 < centre(parts["cube"]).z < high - 0.2)

    def test_scene_is_new_and_has_the_look(self):
        before = {s.name for s in bpy.data.scenes}
        show = self.run_scenes([1])
        scene = show.scenes[1]
        self.assertNotIn(scene.name, before)
        self.assertEqual(scene.name, "CopyThat Promo 1 - One cube")
        self.assertIs(window().scene, scene)
        area, space = viewport()
        self.assertEqual(space.shading.type, "SOLID")
        self.assertEqual(space.shading.light, "STUDIO")
        self.assertEqual(space.shading.color_type, "MATERIAL")
        self.assertTrue(space.show_region_ui)
        self.assertEqual(space.region_3d.view_perspective, "PERSP")
        # The orange cube, as the Solid viewport will show it.
        material = show.parts[1]["cube"].data.materials[0]
        r, g, b, _a = material.diffuse_color
        self.assertAlmostEqual(r, promo.to_linear(0xE8 / 255.0), places=3)
        self.assertAlmostEqual(g, promo.to_linear(0x83 / 255.0), places=3)
        self.assertAlmostEqual(b, promo.to_linear(0x3A / 255.0), places=3)


class TestEverydayBlender(Case):
    """The recording is of Blender as it comes: only Solid mode, the studio
    light and the sidebar are touched."""

    UNTOUCHED = ("shading.background_type", "shading.show_cavity", "shading.show_shadows",
                 "shading.show_object_outline", "shading.show_xray", "shading.use_world_space_lighting",
                 "overlay.show_overlays", "overlay.show_floor", "overlay.show_axis_x",
                 "overlay.show_axis_y", "overlay.show_axis_z", "overlay.show_text",
                 "overlay.show_stats", "overlay.show_relationship_lines",
                 "overlay.show_object_origins", "overlay.show_cursor", "overlay.show_extras",
                 "overlay.show_bones", "show_region_toolbar", "show_region_tool_header",
                 "show_region_header", "show_gizmo", "show_gizmo_navigate", "lens")

    def test_nothing_but_solid_studio_and_the_sidebar_is_changed(self):
        area, space = viewport()
        space.show_region_ui = False
        before = {path: promo.snapshot(promo.get_path(space, path)) for path in self.UNTOUCHED}
        self.run_scenes([1, 2, 3])
        area, space = viewport()
        for path in self.UNTOUCHED:
            self.assertEqual(promo.snapshot(promo.get_path(space, path)), before[path], path)
        self.assertTrue(space.show_region_ui)
        self.assertEqual((space.shading.type, space.shading.light), ("SOLID", "STUDIO"))

    def test_and_all_of_it_is_put_back_after_the_flower_too(self):
        area, space = viewport()
        space.show_region_ui = False
        before = {path: promo.snapshot(promo.get_path(space, path)) for path in self.UNTOUCHED}
        show = self.run_scenes([1, 2, 3, 4])
        show.leave()
        area, space = viewport()
        for path in self.UNTOUCHED:
            self.assertEqual(promo.snapshot(promo.get_path(space, path)), before[path], path)
        self.assertFalse(space.show_region_ui)

    def test_the_standard_layout_is_not_rearranged(self):
        screen = window().screen
        before = [a.type for a in screen.areas]
        self.run_scenes([1, 2, 3])
        self.assertIs(window().screen, screen)
        self.assertEqual([a.type for a in screen.areas], before)
        self.assertFalse(window().screen.show_fullscreen)

    def test_the_grid_is_the_floor_and_there_is_no_slab(self):
        show = self.run_scenes([1, 2, 3])
        for number in (1, 2, 3):
            self.assertFalse([o.name for o in show.scenes[number].objects
                              if o.name.startswith("Floor")])

    def test_full_viewport_is_off_by_default(self):
        self.assertFalse(promo.FULL_VIEWPORT)
        self.assertTrue(promo.MAXIMISE_FOR_BLOOM)

    def test_the_selection_shows_what_each_step_works_on(self):
        picked = {}

        def watch(action, show):
            if action[0] == "caption" and action[2]:
                scene = show.scenes[1]
                layer = scene.view_layers[0]
                picked[action[2].split(" \u2014 ")[0]] = (
                    sorted(o.name for o in layer.objects if o.select_get(view_layer=layer)))
        self.run_scenes([1], watch)
        # Selected from New Move on, so the outline is there through every step.
        self.assertEqual(picked["Move it by hand"], ["Cube"])
        self.assertEqual(picked["Record After"], ["Cube"])
        self.assertEqual(picked["Build Sliders"], ["Cube"])


class TestSceneTwo(Case):

    def run_it(self):
        show = self.run_scenes([2])
        parts = show.parts[2]
        move = self.the_move(show, 2)
        rider_name = parts["rider"].name
        # Where each stands at Before, and what the leader does in its own frame.
        self.leader, self.rider = parts["leader"], parts["rider"]
        self.l_start, self.l_end = parts["start"], parts["end"]
        self.r_start = self.rider.matrix_world.copy()
        travel = self.l_start.inverted() @ self.l_end
        self.r_end = self.r_start @ travel
        return show, move, move.parts[rider_name]

    def test_the_rider_copies_the_move_from_its_own_place(self):
        show, move, part = self.run_it()
        data = move.id_data.rigmoves
        self.assertRegex(data.report, r"^2 part\(s\) on 1 slider\(s\)\.")
        self.assertIn("now ride along", data.report)
        self.check_drivers(show, 2)
        self.assertEqual(part.leader, self.leader.name)
        play(move, 0.0)
        self.assertLess(drift(self.leader, placed(self.leader, self.l_start)), TOLERANCE)
        self.assertLess(drift(self.rider, placed(self.rider, self.r_start)), TOLERANCE)
        play(move, 100.0)
        self.assertLess(drift(self.leader, placed(self.leader, self.l_end)), TOLERANCE)
        self.assertLess(drift(self.rider, placed(self.rider, self.r_end)), TOLERANCE)
        # Turned a quarter, the rider goes off at a right angle to its leader.
        away_leader = self.l_end.translation - self.l_start.translation
        away_rider = self.r_end.translation - self.r_start.translation
        away_leader.z = away_rider.z = 0.0
        self.assertAlmostEqual(away_leader.normalized().dot(away_rider.normalized()), 0.0, places=3)

    def test_lead_30_sends_the_rider_first(self):
        show, move, part = self.run_it()
        self.assertEqual(part.lead, 30)
        # Early on only the rider has set off...
        play(move, 15.0)
        self.assertLess(drift(self.leader, placed(self.leader, self.l_start)), TOLERANCE)
        self.assertGreater((centre(self.rider) - self.r_start.translation).length, 0.3)
        # ...and it has arrived while the leader is still on the way. (A lead
        # of 30 shifts it 30/50 of a leader's travel, so the control plays
        # 1.6 travels: the rider is done at 62.5%, the leader starts at 37.5%.)
        play(move, 70.0)
        self.assertLess(drift(self.rider, placed(self.rider, self.r_end)), TOLERANCE)
        self.assertGreater(drift(self.leader, placed(self.leader, self.l_end)), 0.3)

    def test_the_riding_along_section_is_open(self):
        _show, move, _part = self.run_it()
        self.assertTrue(move.show_riders)
        self.assertFalse(move.show_timing)


class TestSceneThree(Case):

    def run_it(self):
        seen = {}

        def watch(action, show):
            if action[0] == "caption" and action[2] and action[2].startswith("Curve the Path"):
                # The straight path, before the curve: through the wall.
                move = show.scenes[3].rigmoves_rig.rigmoves.moves[0]
                seen["paths_on"] = move.show_paths
                drawn = move.paths_object
                seen["straight"] = [Vector(p.co[:3]) for p in drawn.data.splines[0].points]
                seen["no_curve_yet"] = move.parts[0].path_curve is None
            if action[0] == "caption" and action[2] and action[2].startswith("Edit mode"):
                seen["mode_before_edit"] = bpy.context.object.mode
            if action[0] == "call" and seen.get("edited") is None and "mode_before_edit" in seen:
                seen["edited"] = True
        show = self.run_scenes([3], watch)
        self.seen = seen
        parts = show.parts[3]
        return show, parts, self.the_move(show, 3)

    def test_the_cube_arcs_over_the_wall(self):
        show, parts, move = self.run_it()
        cube, wall = parts["cube"], parts["wall"]
        data = move.id_data.rigmoves
        self.assertRegex(data.report, r"^1 part\(s\) on 1 slider\(s\)\.")
        self.check_drivers(show, 3)
        top = max(p.z for p in world_points(wall))
        self.assertAlmostEqual(top, promo.WALL_TOP, places=3)
        play(move, 0.0)
        self.assertLess(drift(cube, placed(cube, parts["start"])), TOLERANCE)
        play(move, 50.0)
        # Half way along, the whole cube - its lowest corner too - is above
        # the wall's top: it goes over, not through.
        self.assertGreater(min(p.z for p in world_points(cube)), top + 0.2)
        self.assertLess(abs(centre(cube).x), 0.1)
        play(move, 100.0)
        self.assertLess(drift(cube, placed(cube, parts["end"])), TOLERANCE)

    def test_the_straight_path_goes_through_the_wall_first(self):
        show, parts, move = self.run_it()
        seen = self.seen
        self.assertTrue(seen["paths_on"], "Paths was not on before the curve")
        self.assertTrue(seen["no_curve_yet"])
        half = promo.WALL_TOP / 2.0
        inside = [p for p in seen["straight"]
                  if abs(p.x) < 0.25 and abs(p.y) < 1.5 and 0.0 < p.z < 2.0 * half]
        self.assertTrue(inside, "the straight path does not cut through the wall")

    def test_stopping_in_the_middle_of_edit_mode_leaves_it(self):
        class Stop(Exception):
            pass
        show = promo.Show([3], instant=True)

        def watch(action, shown):
            if action[0] == "tween_value" and bpy.context.object is not None \
                    and bpy.context.object.mode == "EDIT":
                raise Stop()
        with self.assertRaises(Stop):
            show.run_instant(watch)
        self.assertEqual(bpy.context.object.mode, "EDIT")
        show.cancel()
        self.assertEqual(bpy.context.object.mode, "OBJECT")

    def test_edit_mode_was_used_and_left(self):
        show, parts, move = self.run_it()
        self.assertEqual(self.seen["mode_before_edit"], "OBJECT")
        self.assertEqual(bpy.context.object.mode, "OBJECT")
        curve = move.parts[0].path_curve
        points = curve.data.splines[0].bezier_points
        self.assertEqual(len(points), 3)
        # The ends stayed on A and B, the middle was lifted.
        self.assertLess((points[0].co - parts["start"].translation).length, TOLERANCE)
        self.assertLess((points[2].co - parts["end"].translation).length, TOLERANCE)
        self.assertAlmostEqual(points[1].co.z, promo.LIFT_TO, places=3)

    def test_the_lines_are_thick_enough_to_see_on_a_recording(self):
        show, parts, move = self.run_it()
        drawn, curve = move.paths_object, move.parts[0].path_curve
        self.assertGreater(drawn.data.bevel_depth, 0.01)
        self.assertGreater(curve.data.bevel_depth, drawn.data.bevel_depth)
        self.assertTrue(len(drawn.data.materials) and len(curve.data.materials))

    def test_paths_stay_on_and_now_arc(self):
        show, parts, move = self.run_it()
        self.assertTrue(move.show_paths)
        line = [Vector(p.co[:3]) for p in move.paths_object.data.splines[0].points]
        self.assertGreater(max(p.z for p in line), promo.WALL_TOP + 0.5)


class TestSceneFour(Case):

    def run_it(self):
        actions = []
        seen = {"captions": [], "sections": {}, "picked": {}}

        def watch(action, show):
            actions.append(action)
            if action[0] == "caption" and action[2]:
                line = action[2]
                seen["captions"].append(line)
                rig = show.scenes[4].rigmoves_rig
                layer = show.scenes[4].view_layers[0]
                seen["picked"][line] = ([o.name for o in layer.objects if o.select_get(view_layer=layer)],
                                        layer.objects.active.name if layer.objects.active else None)
                if rig is not None and len(rig.rigmoves.moves):
                    move = rig.rigmoves.moves[0]
                    seen["sections"][line] = (move.show_riders, move.show_chain, move.show_timing)
                    if line.startswith("Animate"):
                        seen["build_report"] = rig.rigmoves.report
                    if line.startswith("Play"):
                        seen["built"] = move.built
        show = self.run_scenes([4], watch)
        self.actions = actions
        self.seen = seen
        return show, show.parts[4]

    def starts(self, prefix):
        return next(line for line in self.seen["captions"] if line.startswith(prefix))

    def test_the_beats_come_in_the_order_a_user_would_follow(self):
        self.run_it()
        order = ["The parts", "Select one petal", "New Move", "Open ONE outer petal",
                 "Then one inner petal", "The core rises", "Leaves \u2014 the 3D cursor",
                 "Unfurl the leaves", "Record After", "Ride Along", "Build Sliders",
                 "Play \u2014 all 8", "Lead", "Play \u2014 they open in a wave", "Inner ring",
                 "A Delay for the inner", "Play \u2014 the inner ring", "Leaves \u2014 each segment",
                 "A Delay for each leaf", "Build Sliders", "Play \u2014 the leaves", "Ease",
                 "Animate", "The 3D view large", "Play \u2014 the whole bloom"]
        at = -1
        for prefix in order:
            later = [i for i, line in enumerate(self.seen["captions"]) if line.startswith(prefix)
                     and i > at]
            self.assertTrue(later, prefix)
            at = later[0]
        self.assertIn("8 outer petals", self.starts("The parts"))
        self.assertIn("2 leaves of 3 segments", self.starts("The parts"))

    def test_four_scrubs_and_one_full_bloom(self):
        self.run_it()
        scrubs = [line for line in self.seen["captions"] if line.startswith("Play")]
        self.assertEqual(len(scrubs), 5)

    def test_each_step_selects_what_it_works_on(self):
        show, parts = self.run_it()
        picked = self.seen["picked"]
        leader, inner_leader = parts["outer"][0], parts["inner"][0]
        # The caption comes first and the step selects after it, so what a
        # step selected is read at the next caption.
        self.assertEqual(picked[self.starts("Then one inner")][0], [leader.name])
        self.assertEqual(picked[self.starts("The core rises")][0], [inner_leader.name])
        self.assertEqual(picked[self.starts("Leaves \u2014 the 3D cursor")][0], [parts["core"].name])
        self.assertEqual(picked[self.starts("Unfurl")][0], [parts["leaves"][1][2].name])
        self.assertEqual(sorted(picked[self.starts("Record After")][0]),
                         sorted(o.name for o in [x for chain in parts["leaves"] for x in chain]))
        # Ride Along: the seven, with the leader selected last, so active.
        seven, active = picked[self.starts("Build Sliders")]
        self.assertEqual(sorted(seven), sorted(o.name for o in parts["outer"]))
        self.assertEqual(active, leader.name)

    def test_the_panel_sections_follow_the_beat(self):
        show, _parts = self.run_it()
        sections = self.seen["sections"]
        # (Riding along, Follows, Timing), read as the next beat begins.
        self.assertEqual(sections[self.starts("Lead")], (True, False, False))
        self.assertEqual(sections[self.starts("Inner ring")], (True, False, False))
        self.assertEqual(sections[self.starts("Leaves \u2014 each")], (False, False, True))
        self.assertEqual(sections[self.starts("A Delay for each")], (False, True, False))
        self.assertEqual(sections[self.starts("Ease")], (False, False, True))
        # Riding along open while the riders are listed and given their Leads.
        self.assertEqual(sections[self.starts("Play \u2014 all 8")], (True, False, False))

    def test_flower_builds_and_blooms(self):
        show, parts = self.run_it()
        scene = show.scenes[4]
        data = scene.rigmoves_rig.rigmoves
        self.assertEqual(len(data.moves), 1)
        move = data.moves[0]
        self.assertTrue(move.built)
        self.assertRegex(data.report, r"plays over frames 1 to")
        # Build, in its own words, just before Animate.
        self.assertRegex(self.seen["build_report"], r"^\d+ part\(s\) on 1 slider\(s\)\.")
        self.assertNotIn("cut short", self.seen["build_report"])
        self.check_drivers(show, 4)
        # Animate keyed the bloom; the scene rests on its last frame.
        self.assertEqual(scene.frame_current, scene.frame_end)
        end = scene.frame_end
        scene.frame_set(1)
        closed = {o.name: world_points(o) for o in parts["all"] if o.type == "MESH"}
        scene.frame_set(end)
        moved = 0
        for obj in parts["outer"] + parts["inner"] + [parts["core"]]:
            gone = max((a - b).length for a, b in zip(closed[obj.name], world_points(obj)))
            self.assertGreater(gone, 0.05, obj.name + " did not move")
            moved += 1
        for chain in parts["leaves"]:
            gone = max((a - b).length for a, b in zip(closed[chain[-1].name], world_points(chain[-1])))
            self.assertGreater(gone, 0.05, chain[-1].name + " did not move")
        self.assertEqual(moved, len(parts["outer"]) + len(parts["inner"]) + 1)

    @unittest.skipUnless(HAVE_FLOWER, "needs the real flower.py")
    def test_every_petal_ends_where_the_flower_says(self):
        show, parts = self.run_it()
        flower = promo.FLOWER
        scene = show.scenes[4]
        scene.frame_set(scene.frame_end)
        for ring, degrees in ((parts["outer"], flower.OUTER_OPEN), (parts["inner"], flower.INNER_OPEN)):
            for obj in ring:
                home = obj.matrix_world.copy()
                want = placed(obj, home @ Matrix.Rotation(math.radians(degrees), 4, "Y"))
                self.assertLess(drift(obj, want), 2e-3, obj.name)
        core = parts["core"]
        want = placed(core, Matrix.Translation((0.0, 0.0, flower.CORE_RISE)) @ core.matrix_world
                      @ Matrix.Rotation(math.radians(flower.CORE_TURN), 4, "Z"))
        self.assertLess(drift(core, want), 2e-3)
        scene.frame_set(1)
        for obj in parts["outer"] + parts["inner"] + [core]:
            self.assertLess(drift(obj, placed(obj, obj.matrix_world)), 2e-3, obj.name)

    def test_it_ends_through_the_promo_camera_after_a_still(self):
        show, parts = self.run_it()
        area, space = viewport()
        self.assertEqual(space.region_3d.view_perspective, "CAMERA")
        self.assertIs(show.scenes[4].camera, parts["camera"])
        self.assertEqual(parts["camera"].name, "Promo Camera")
        kinds = [a[0] for a in self.actions]
        at = next(i for i, a in enumerate(self.actions)
                  if a[0] == "view" and "camera" in a[1])
        # A still on frame 1 before playback: the outro starts from this picture.
        self.assertEqual(self.actions[at + 1][0], "wait")
        self.assertGreaterEqual(self.actions[at + 1][1], 1.0)
        self.assertIn("call", kinds[at + 1:])
        # The 3D view is made large just before the camera, and given back after.
        big = [i for i, a in enumerate(self.actions) if a[0] == "maximise"]
        self.assertEqual([self.actions[i][1] for i in big], [True, False])
        self.assertLess(big[0], at)
        self.assertGreater(big[1], at)
        self.assertFalse(window().screen.show_fullscreen)

    def test_look_for_the_flower(self):
        show, _parts = self.run_it()
        _area, space = viewport()
        self.assertEqual(space.shading.color_type, "OBJECT")

    def test_the_view_is_not_made_large_if_that_is_switched_off(self):
        promo.MAXIMISE_FOR_BLOOM = False
        seen = []

        def watch(action, show):
            if action[0] == "maximise":
                seen.append(window().screen.show_fullscreen)
        try:
            self.run_scenes([4], watch)
        finally:
            promo.MAXIMISE_FOR_BLOOM = True
        self.assertEqual(seen, [False, False])


@unittest.skipUnless(HAVE_FLOWER, "needs the real flower.py")
class TestFlowerRegression(Case):
    """Scene 4 builds the rig in beats, in a different order from the flower
    module's own flower_steps. The cinematic outro is rendered from
    flower_steps, so the two have to end in the same flower: the same poses,
    Leads, Delays, Follows, pivots, ease and frames. Compared here on the
    evaluated mesh of every part at five frames."""

    def bloom(self, old, frames):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        promo.FULL_VIEWPORT = False
        promo.FLOWER_FRAMES = frames
        original = promo.SCENE_DEFS[4]["steps"]
        if old:
            def old_steps(parts):
                scene = bpy.context.scene
                scene.frame_start, scene.frame_current, scene.frame_end = 1, 1, 1 + frames
                yield from promo.FLOWER.flower_steps(parts, frames=frames)
            promo.SCENE_DEFS[4]["steps"] = old_steps
        try:
            show = promo.Show([4], instant=True)
            show.run_instant()
        finally:
            promo.SCENE_DEFS[4]["steps"] = original
            promo.FLOWER_FRAMES = 150
        scene = show.scenes[4]
        window().scene = scene
        rig = scene.rigmoves_rig
        move = rig.rigmoves.moves[0]
        meshes = {}
        for frame in (1, 38, 75, 112, frames + 1):
            scene.frame_set(frame)
            meshes[frame] = {o.name: [tuple(p) for p in world_points(o)]
                             for o in scene.objects if o.type == "MESH"}
        settings = {
            "parts": {p.name: (p.lead, round(p.start, 6), p.follows, p.leader,
                               tuple(round(x, 6) for x in p.pivot), p.pivot_kind, p.mirror)
                      for p in move.parts},
            "ease": move.ease, "frames": move.play_frames, "end": scene.frame_end,
            "drivers": sorted((c.data_path.split("[")[1], c.driver.expression)
                              for c in rig.animation_data.drivers if "constraints[" in c.data_path)}
        return meshes, settings

    def compare(self, frames):
        old_meshes, old_settings = self.bloom(True, frames)
        new_meshes, new_settings = self.bloom(False, frames)
        self.assertEqual(sorted(old_meshes), sorted(new_meshes))
        worst = 0.0
        for frame, parts in old_meshes.items():
            self.assertEqual(sorted(parts), sorted(new_meshes[frame]))
            for name, points in parts.items():
                other = new_meshes[frame][name]
                self.assertEqual(len(points), len(other), name)
                for a, b in zip(points, other):
                    worst = max(worst, math.dist(a, b))
        self.assertLess(worst, 1e-4, "largest difference {:.3g}".format(worst))
        self.assertEqual(old_settings, new_settings)
        return worst

    def test_the_beats_end_in_the_same_flower_as_flower_steps_149(self):
        self.compare(149)        # what the outro renders from

    def test_and_with_the_150_frames_scene_4_uses(self):
        self.compare(150)


class TestPlayOut(Case):
    """Waiting for the bloom to play, without a viewport to play it in."""

    class Scene:
        frame_current, frame_end = 1, 151

        class render:
            fps, fps_base = 30, 1.0

    def walk(self, frames_per_wait, start=1, limit=400):
        """Drive play_out the way a viewport would: the frame advances between waits."""
        scene = self.Scene()
        scene.frame_current = start
        steps = promo.play_out(scene, headless=False)
        waits, stopped = 0, False
        action = next(steps)
        while True:
            if action[0] == "call":
                stopped = True
                break
            waits += 1
            self.assertLess(waits, limit)
            scene.frame_current += frames_per_wait
            if scene.frame_current > scene.frame_end:     # playback loops
                scene.frame_current = 3
            try:
                action = next(steps)
            except StopIteration:
                break
        return waits, stopped

    def test_it_stops_as_soon_as_the_last_frame_is_reached(self):
        waits, stopped = self.walk(frames_per_wait=1.5)       # 30 fps, in 50 ms waits
        self.assertTrue(stopped)
        self.assertAlmostEqual(waits, 100, delta=3)

    def test_it_stops_when_playback_skips_over_the_end_and_loops(self):
        waits, stopped = self.walk(frames_per_wait=40)
        self.assertTrue(stopped)
        self.assertLess(waits, 10)

    def test_it_gives_up_if_nothing_ever_plays(self):
        waits, stopped = self.walk(frames_per_wait=0, limit=2000)
        self.assertTrue(stopped)
        self.assertAlmostEqual(waits * 0.05, 5.0 + 3.0, delta=0.2)

    def test_headless_it_is_one_wait_of_the_bloom_s_length(self):
        steps = list(promo.play_out(self.Scene(), headless=True))
        self.assertEqual(steps[0], ("wait", 5.0))
        self.assertEqual(steps[1][0], "call")


class TestLiveEngine(Case):
    """The very same scenes on timer ticks, with a clock the test winds."""

    def walk(self, numbers, step=1.0 / 30.0, sample=None):
        clock = FakeClock()
        show = promo.Show(numbers, clock=clock)
        show.begin()
        ticks = 0
        while True:
            clock.now += step
            ticks += 1
            self.assertLess(ticks, 100000, "the show never ended")
            if show.tick() is None:
                break
            if sample is not None:
                sample(show, clock)
        return show, ticks, clock

    def test_all_three_scenes_run_to_the_end(self):
        show, ticks, _clock = self.walk([1, 2, 3])
        self.assertTrue(show.dead)
        self.assertEqual(show.error, "")
        self.assertEqual(sorted(show.scenes), [1, 2, 3])
        # Everything the instant run checks, in the last scene: Build said it worked.
        scene = show.scenes[3]
        self.assertRegex(scene.rigmoves_rig.rigmoves.report, r"^1 part\(s\) on 1 slider")
        # About 30 ticks a second of designed time, plus the countdown.
        # The countdown, two pauses, a held second after each scene, the
        # sidebar's wait before the first, and each scene's view glide.
        seconds = (sum(show.lengths.values()) + promo.COUNTDOWN + 2 * promo.PAUSE_BETWEEN + 3.0
                   + 1.5 + 3 * 0.6)
        self.assertAlmostEqual(ticks / 30.0, seconds, delta=3.0)

    def test_uneven_ticks_end_in_the_same_place(self):
        # A slow machine: ticks anywhere from 16 ms to a third of a second apart.
        import random
        rng = random.Random(7)
        clock = FakeClock()
        show = promo.Show([1, 2, 3], clock=clock)
        show.begin()
        for _ in range(100000):
            clock.now += rng.choice((1 / 60.0, 1 / 30.0, 0.1, 0.33))
            if show.tick() is None:
                break
        self.assertTrue(show.dead)
        self.assertEqual(show.error, "")
        scene = show.scenes[3]
        move = scene.rigmoves_rig.rigmoves.moves[0]
        self.assertTrue(move.built)
        play(move, 100.0)
        cube, end = show.parts[3]["cube"], show.parts[3]["end"]
        self.assertLess(drift(cube, placed(cube, end)), TOLERANCE)
        curve = move.parts[0].path_curve
        self.assertAlmostEqual(curve.data.splines[0].bezier_points[1].co.z, promo.LIFT_TO, places=3)

    def test_a_tween_glides_eased_from_start_to_end(self):
        samples = []

        def sample(show, clock):
            player = show.player
            if player.line.startswith("Move it by hand") and 1 in show.parts:
                samples.append(show.parts[1]["cube"].matrix_world.translation.z)
        show, _ticks, _clock = self.walk([1], sample=sample)
        low, high = 0.6, show.parts[1]["end"].translation.z
        self.assertGreater(len(samples), 40)
        self.assertTrue(all(low - 1e-6 <= z <= high + 1e-6 for z in samples))
        self.assertEqual(samples, sorted(samples), "the glide went backwards")
        # Eased: slow at the start, quick in the middle.
        first, middle = samples[1] - samples[0], samples[len(samples) // 2] - samples[len(samples) // 2 - 1]
        self.assertGreater(middle, first * 3.0)

    def test_the_countdown_shows_5_to_1_before_anything_happens(self):
        counts = []

        def sample(show, clock):
            counts.append((show.view_state(clock())["count"], show.player.line))
        _show, _ticks, _clock = self.walk([1], sample=sample)
        shown = [c for c, _line in counts if c]
        self.assertEqual(shown[0], 5)
        self.assertEqual(sorted(set(shown), reverse=True), [5, 4, 3, 2, 1])
        # Nothing was said, and no caption line, while it counted down.
        self.assertTrue(all(line == "" for c, line in counts if c))

    def test_speed_makes_it_shorter(self):
        promo.COUNTDOWN = 0
        _slow, slow_ticks, _c = self.walk([1])
        bpy.ops.wm.read_factory_settings(use_empty=True)
        promo.SPEED = 2.0
        _fast, fast_ticks, _c = self.walk([1])
        self.assertLess(fast_ticks, slow_ticks * 0.65)

    def test_fullscreen_is_taken_and_given_back(self):
        promo.FULL_VIEWPORT = True
        before = window().screen.name
        seen = []

        def sample(show, clock):
            seen.append((window().screen.show_fullscreen, window().scene.name))
        show, _ticks, _clock = self.walk([1], sample=sample)
        # The scenes were made, and switched to, while the viewport was full.
        self.assertIn((True, "CopyThat Promo 1 - One cube"), seen)
        self.assertIs(window().scene, show.scenes[1])
        self.assertFalse(window().screen.show_fullscreen)
        self.assertEqual(window().screen.name, before)
        self.assertFalse(show.stage.full_by_us)

    def test_scene_four_runs_live_too(self):
        show, _ticks, _clock = self.walk([4])
        self.assertEqual(show.error, "")
        scene = show.scenes[4]
        self.assertEqual(scene.frame_current, scene.frame_end)

    def test_the_bloom_is_played_in_the_enlarged_view_and_handed_back(self):
        seen = []

        def sample(show, clock):
            if 4 in show.scenes:
                space = viewport()[1]
                seen.append((window().screen.show_fullscreen, space.region_3d.view_perspective))
        show, _ticks, _clock = self.walk([4], sample=sample)
        self.assertIn((True, "CAMERA"), seen)                 # large, through the camera
        self.assertNotIn((False, "CAMERA"), seen[:seen.index((True, "CAMERA"))])
        self.assertFalse(window().screen.show_fullscreen)     # given back at the end
        self.assertFalse(show.stage.bloom_by_us)

    def test_an_error_while_the_view_is_large_gives_it_back(self):
        original = promo.SCENE_DEFS[4]["steps"]

        def broken(parts):
            yield ("maximise", True)
            yield ("wait", 0.2)
            raise RuntimeError("boom")
        promo.SCENE_DEFS[4]["steps"] = broken
        try:
            show, _ticks, _clock = self.walk([4])
        finally:
            promo.SCENE_DEFS[4]["steps"] = original
        self.assertTrue(show.dead)
        self.assertFalse(window().screen.show_fullscreen)
        for callback in (show.leave_callback, show.remove_callback):
            if bpy.app.timers.is_registered(callback):
                bpy.app.timers.unregister(callback)
        show.leave()

    def test_the_view_glides_into_the_camera(self):
        modes = []

        def sample(show, clock):
            if 4 in show.scenes:
                space = viewport()[1]
                modes.append((space.region_3d.view_perspective, space.lens))
        show, _ticks, _clock = self.walk([4], sample=sample)
        names = [m for m, _lens in modes]
        self.assertIn("PERSP", names)
        self.assertEqual(names[-1], "CAMERA")
        self.assertEqual(names.index("CAMERA"), len([m for m in names if m == "PERSP"]))
        # The free view it glides to has twice the camera's lens, because a
        # viewport shows twice a camera's field of view; then camera view is
        # zoomed until the camera's frame fills the viewport, centred.
        area, space = viewport()
        region = next(r for r in area.regions if r.type == "WINDOW")
        scene, camera = show.scenes[4], show.parts[4]["camera"]
        fit, zoom = promo.camera_fit(scene.render.resolution_x, scene.render.resolution_y,
                                     region.width, region.height)
        last_free = [lens for m, lens in modes if m == "PERSP"][-1]
        self.assertAlmostEqual(last_free, min(250.0, 2.0 * fit * camera.data.lens), delta=0.5)
        rv3d = space.region_3d
        self.assertAlmostEqual(rv3d.view_camera_zoom, zoom, places=3)
        self.assertEqual(tuple(rv3d.view_camera_offset), (0.0, 0.0))
        self.assertFalse(camera.data.show_passepartout)


def luminance(rgb):
    """Relative luminance of an sRGB colour, 0 to 1."""
    def lin(c):
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


class TestReviewFindings(Case):
    METRICS = {"width": 1574, "height": 954, "visible": 1250, "top": 60}

    def test_the_viewport_sees_36_over_lens_not_18(self):
        rotation = promo.view_rotation(0.0, 0.0)
        right, up = rotation @ Vector((1.0, 0.0, 0.0)), rotation @ Vector((0.0, 1.0, 0.0))
        aspect, centre = 16.0 / 9.0, Vector()
        # Blender's own startup viewport: lens 50, tan(half FOV) 0.72 across.
        edge = centre + right * (0.72 * 10.0)
        shown, _tans, _axes = promo.project([edge], centre, rotation, 10.0, 50.0, aspect)
        self.assertAlmostEqual(shown[0][0], 1.0, places=3)
        top = centre + up * (0.72 / aspect * 10.0)
        shown, _tans, _axes = promo.project([top], centre, rotation, 10.0, 50.0, aspect)
        self.assertAlmostEqual(shown[0][1], 1.0, places=3)

    def test_scenes_are_framed_to_fill_the_free_area(self):
        # Scene 1 should fill most of the width left by the sidebar, not half.
        scene = bpy.data.scenes.new("views")
        window().scene = scene
        parts = promo.SCENE_DEFS[1]["build"](scene)
        spec = promo.SCENE_DEFS[1]["view"](parts)
        aspect = 1920.0 / 1080.0
        metrics = {"width": 1920.0, "height": 1080.0, "visible": 1560.0, "top": 0.0, "left": 60.0}
        centre, rotation, distance, lens = promo.frame_view(
            spec["frame"], spec["azimuth"], spec["elevation"], 50.0, aspect,
            promo.margins(metrics))
        shown, _tans, _axes = promo.project(spec["frame"], centre, rotation, distance, lens, aspect)
        wide = max(x for x, _y in shown) - min(x for x, _y in shown)
        left, right, _top, _bottom = promo.margins(metrics)
        free = 2.0 - 2.0 * (left + right)
        self.assertGreater(wide / free, 0.5)
        self.assertLess(distance, 24.0)

    def test_camera_fit_fills_the_viewport(self):
        fit, zoom = promo.camera_fit(1920, 1080, 1574, 954)       # narrower than 16:9
        self.assertEqual(fit, 1.0)
        self.assertAlmostEqual(zoom, 29.289, places=2)
        fit, zoom = promo.camera_fit(1920, 1080, 2400, 1000)      # wider: back off
        self.assertAlmostEqual(fit, (1920 / 1080.0) / 2.4, places=6)
        # Blender turns view_camera_zoom into the factor (sqrt2 + z/50)^2 / 4,
        # which has to equal the fit.
        self.assertAlmostEqual((math.sqrt(2.0) + zoom / 50.0) ** 2 / 4.0, fit, places=6)

    def test_every_caption_is_up_long_enough_to_read(self):
        ends = {}

        def watch(action, show):
            if action[0] == "mark" and action[1] == "end":
                ends[action[2]] = show.player.length
        show = self.run_scenes([1, 2, 3, 4], watch)
        caps = show.player.captions
        self.assertGreater(len(caps), 25)
        for (t0, chip0, line0), (t1, chip1, line1) in zip(caps, caps[1:]):
            if chip0 == chip1:
                self.assertGreaterEqual(t1 - t0 + 0.011, promo.dwell(line0), (line0, t1 - t0))
                self.assertGreaterEqual(t1 - t0 + 0.011, 1.2, (line0, t1 - t0))
        # And the last line of each scene, up to the scene's end.
        last = {}
        for t0, chip, line in caps:
            last[chip[0]] = (t0, line)
        for number, (t0, line) in last.items():
            self.assertGreaterEqual(ends[int(number)] - t0 + 0.011, promo.dwell(line), line)

    def test_a_long_caption_gets_about_two_seconds_and_a_short_one_1_2(self):
        self.assertEqual(promo.dwell("Play"), 1.2)
        self.assertEqual(promo.dwell("Build Sliders"), 1.2)
        self.assertEqual(promo.dwell("Ride Along \u2014 copies the move from its own place"), 2.0)
        self.assertEqual(promo.dwell("Curve the Path \u2014 ends stay on A and B"), 2.0)

    def test_readable_holds_a_caption_that_would_go_too_soon(self):
        steps = [("caption", None, "Build Sliders"), ("wait", 0.3),
                 ("caption", None, "Play"), ("wait", 5.0), ("caption", None, "Done"),
                 ("caption", None, "Done"), ("caption", None, ""), ("caption", None, "Next")]
        out = list(promo.readable(iter(steps)))
        # 0.9 s made up before "Play"; nothing added after the long wait; a
        # repeated line is not held; and the last line is held to the end.
        self.assertEqual(out[0:2], [steps[0], steps[1]])
        self.assertEqual(out[2][0], "wait")
        self.assertAlmostEqual(out[2][1], 0.9)
        self.assertEqual(out[3], steps[2])
        self.assertEqual(out[-1], ("wait", 1.2))
        self.assertEqual(sum(1 for a in out if a[0] == "wait"), 4)

    def test_a_new_line_fades_its_text_but_not_the_bar(self):
        painter = FakePainter()
        # The strip came up long ago; the words changed just now.
        promo.draw_overlay(painter, {"line": "Record After", "changed": 100.0,
                                     "bar_changed": 90.0},
                           self.METRICS, 1.0, 100.0)
        self.assertAlmostEqual(painter.colors[0][3], 0.84, places=2)
        self.assertLess(painter.text_colors[0][3], 0.05)
        # From an empty line the strip fades in as well.
        painter = FakePainter()
        promo.draw_overlay(painter, {"line": "Record After", "changed": 100.0,
                                     "bar_changed": 100.0},
                           self.METRICS, 1.0, 100.0)
        self.assertLess(painter.colors[0][3], 0.05)

    def test_the_player_keeps_the_bar_when_only_the_words_change(self):
        player = promo.Player(None, instant=True)
        player.begin(("caption", None, "One"), 5.0)
        self.assertEqual(player.bar_changed, 5.0)
        player.begin(("caption", None, "Two"), 9.0)
        self.assertEqual((player.bar_changed, player.changed), (5.0, 9.0))
        player.begin(("caption", None, ""), 12.0)
        player.begin(("caption", None, "Three"), 14.0)
        self.assertEqual(player.bar_changed, 14.0)

    def test_captions_scale_with_the_viewport_height(self):
        for height, expected in ((1080, 1.0), (2160, 2.0), (540, 0.5), (954, 954 / 1080.0)):
            self.assertAlmostEqual(promo.caption_scale({"height": height}), expected)
        promo.CAPTION_SCALE = 1.3
        try:
            self.assertAlmostEqual(promo.caption_scale({"height": 1080}), 1.3)
        finally:
            promo.CAPTION_SCALE = 1.0

    def test_the_note_under_the_countdown_is_readable(self):
        painter = FakePainter()
        note = "Scene 4 is left out: this copy has no flower code in it."
        promo.draw_overlay(painter, {"count": 3, "note": note}, self.METRICS, 1.0, 100.0)
        at = painter.texts.index(next(t for t in painter.texts if t[3] == note))
        text_colour, pill = painter.text_colors[at], painter.colors[-1]
        pale = (1.0, 1.0, 1.0)          # the worst case: a white viewport behind it
        backed = tuple(pill[3] * c + (1.0 - pill[3]) * p for c, p in zip(pill[:3], pale))
        self.assertGreaterEqual(contrast(text_colour[:3], backed), 7.0)
        # The pill is behind the words and inside the free part of the viewport.
        x, y, w, h = painter.rects[-1]
        tx, ty = painter.texts[at][0], painter.texts[at][1]
        self.assertTrue(x <= tx and y <= ty <= y + h)
        self.assertLessEqual(x + w, self.METRICS["visible"])

    def test_leaving_gives_the_users_screen_back(self):
        area, space = viewport()
        rv3d = space.region_3d
        space.shading.type = "WIREFRAME"
        space.shading.color_type = "TEXTURE"
        space.shading.light = "FLAT"
        space.show_region_ui = False
        space.lens = 35.0
        before = {"type": space.shading.type, "color": space.shading.color_type,
                  "light": space.shading.light, "ui": space.show_region_ui,
                  "persp": rv3d.view_perspective, "loc": tuple(rv3d.view_location),
                  "dist": rv3d.view_distance, "lens": space.lens,
                  "zoom": rv3d.view_camera_zoom, "scene": window().scene.name}
        clock = FakeClock()
        show = promo.Show([4], clock=clock)
        show.begin()
        for _ in range(100000):
            clock.now += 1.0 / 30.0
            if show.tick() is None:
                break
        self.assertEqual(viewport()[1].region_3d.view_perspective, "CAMERA")
        self.assertNotEqual(window().scene.name, before["scene"])
        self.assertTrue(bpy.app.timers.is_registered(show.leave_callback))
        bpy.app.timers.unregister(show.leave_callback)
        show.leave()
        area, space = viewport()
        rv3d = space.region_3d
        self.assertEqual(space.shading.type, before["type"])
        self.assertEqual(space.shading.color_type, before["color"])
        self.assertEqual(space.shading.light, before["light"])
        self.assertEqual(space.show_region_ui, before["ui"])
        self.assertEqual(rv3d.view_perspective, before["persp"])
        self.assertEqual(tuple(rv3d.view_location), before["loc"])
        self.assertAlmostEqual(rv3d.view_distance, before["dist"], places=4)
        self.assertAlmostEqual(space.lens, before["lens"], places=4)
        self.assertAlmostEqual(rv3d.view_camera_zoom, before["zoom"], places=4)
        self.assertEqual(window().scene.name, before["scene"])
        show.leave()                 # a second time changes nothing

    def test_running_again_after_an_error_still_puts_the_screen_back_first(self):
        promo.SCENES = [1]
        promo.COUNTDOWN = 0
        original = promo.SCENE_DEFS[1]["steps"]

        def broken(parts):
            yield ("wait", 0.1)
            raise RuntimeError("boom")
        promo.SCENE_DEFS[1]["steps"] = broken
        try:
            first = promo.main()
            clock = FakeClock()
            first.clock = clock
            for _ in range(500):
                clock.now += 1.0 / 30.0
                if first.tick() is None:
                    break
        finally:
            promo.SCENE_DEFS[1]["steps"] = original
        self.assertTrue(first.dead)
        self.assertFalse(first.left)
        self.assertIs(window().scene, first.scenes[1])
        second = promo.main()          # inside the ten seconds the message stays up
        self.assertTrue(first.left)
        self.assertEqual(second.stage.start_scene, "Scene")
        for show in (first, second):
            show.cancel()
            show.leave()
            for callback in (show.leave_callback, show.remove_callback):
                if bpy.app.timers.is_registered(callback):
                    bpy.app.timers.unregister(callback)

    def test_leaving_can_be_switched_off(self):
        promo.RESTORE_VIEW_AT_END = promo.RETURN_TO_START_SCENE = False
        try:
            show = self.run_scenes([1])
            show.leave()
        finally:
            promo.RESTORE_VIEW_AT_END = promo.RETURN_TO_START_SCENE = True
        self.assertIs(window().scene, show.scenes[1])
        self.assertEqual(viewport()[1].shading.type, "SOLID")

    def test_defaults_leave_the_users_file_as_it_was(self):
        self.assertTrue(promo.RESTORE_VIEW_AT_END)
        self.assertTrue(promo.RETURN_TO_START_SCENE)

    def test_running_again_gives_the_screen_back_before_the_new_run_looks(self):
        promo.SCENES = [1]
        first = promo.main()
        clock = FakeClock()
        first.clock = clock
        for _ in range(500):
            clock.now += 1.0 / 30.0
            first.tick()
            if first.scenes:
                break
        self.assertTrue(first.scenes)
        self.assertIs(window().scene, first.scenes[1])
        second = promo.main()
        # Their scene, at once: the new run noted it as where to go back to.
        self.assertTrue(first.left)
        self.assertEqual(second.stage.start_scene, "Scene")
        second.cancel()
        second.leave()
        bpy.app.timers.unregister(second.leave_callback) if bpy.app.timers.is_registered(
            second.leave_callback) else None
        if bpy.app.timers.is_registered(first.leave_callback):
            bpy.app.timers.unregister(first.leave_callback)


class TestRobustness(Case):

    def test_user_data_is_never_touched(self):
        mine = bpy.data.scenes.new("Mine")
        mesh = bpy.data.meshes.new("Mine mesh")
        mesh.from_pydata([(0, 0, 0), (1, 0, 0), (0, 1, 0)], [], [(0, 1, 2)])
        obj = bpy.data.objects.new("Cube", mesh)
        obj.location = (3.0, 4.0, 5.0)
        mine.collection.objects.link(obj)
        original = bpy.data.scenes["Scene"]
        snapshot = (sorted(o.name for o in bpy.data.objects), tuple(obj.location),
                    sorted(s.name for s in bpy.data.scenes), len(bpy.data.meshes))
        first = self.run_scenes([1, 2, 3])
        second = self.run_scenes([1, 2, 3])
        self.assertEqual(tuple(obj.location), (3.0, 4.0, 5.0))
        self.assertEqual(obj.name, "Cube")
        self.assertIn("Mine", bpy.data.scenes)
        self.assertEqual(list(mine.collection.objects), [obj])
        self.assertEqual(len(original.objects), 0)
        for name in snapshot[2]:
            self.assertIn(name, bpy.data.scenes)
        new = sorted(s.name for s in bpy.data.scenes if s.name not in snapshot[2])
        self.assertEqual(len(new), 6)
        self.assertTrue(all(n.startswith("CopyThat Promo") for n in new), new)
        # The second take is clean; the first one is kept, renamed.
        self.assertEqual(sum(1 for n in new if n.endswith("(old)")), 3)
        self.assertEqual(second.scenes[2].name, "CopyThat Promo 2 - Ride Along")
        self.assertEqual(second.parts[2]["leader"].name, "Leader")
        self.assertEqual(second.scenes[1].rigmoves_rig.name, "CopyThat Rig (scene 1)")
        self.assertEqual(second.scenes[3].rigmoves_rig.name, "CopyThat Rig")
        self.assertEqual(first.parts[2]["leader"].name, "Leader (old)")

    def test_a_third_take_does_not_pile_up_old_tags(self):
        for _ in range(3):
            self.run_scenes([1])
        names = sorted(s.name for s in bpy.data.scenes if s.name.startswith("CopyThat Promo"))
        self.assertEqual(names, ["CopyThat Promo 1 - One cube",
                                 "CopyThat Promo 1 - One cube (old)",
                                 "CopyThat Promo 1 - One cube (old).001"])
        self.assertFalse([o.name for o in bpy.data.objects if o.name.count("(old)") > 1])

    def test_each_scene_names_its_own_rig_plainly(self):
        show = self.run_scenes([1, 2, 3])
        names = [show.scenes[n].rigmoves_rig.name for n in (1, 2, 3)]
        self.assertEqual(names, ["CopyThat Rig (scene 1)", "CopyThat Rig (scene 2)", "CopyThat Rig"])

    def test_refuses_clearly_when_copythat_is_off(self):
        rigmoves.unregister()
        try:
            problem = promo.check_addon()
            self.assertIsNotNone(problem)
            self.assertIn("CopyThat is not switched on, or is older than 0.15.0", problem)
            with self.assertRaises(promo.ShowError):
                promo.Show([1]).begin()
        finally:
            rigmoves.register()
        self.assertIsNone(promo.check_addon())

    def test_scene_four_is_left_out_with_a_message_without_flower(self):
        saved = promo.FLOWER
        promo.FLOWER = None
        try:
            numbers, notes = promo.scenes_to_play()
        finally:
            promo.FLOWER = saved
        self.assertEqual(numbers, [1, 2, 3])
        self.assertTrue(any("Scene 4 is left out" in n for n in notes))

    def test_an_error_becomes_a_caption_and_stops_cleanly(self):
        original = promo.SCENE_DEFS[1]["steps"]

        def broken(parts):
            yield ("caption", None, "About to fail")
            yield ("wait", 0.1)
            raise RuntimeError("boom")
        promo.SCENE_DEFS[1]["steps"] = broken
        clock = FakeClock()
        promo.COUNTDOWN = 0
        try:
            show = promo.Show([1], clock=clock)
            show.start()
            self.assertTrue(bpy.app.timers.is_registered(show.callback))
            self.assertIs(bpy.app.driver_namespace[promo.STATE_KEY], show)
            result = 0
            for _ in range(2000):
                clock.now += 1.0 / 30.0
                result = show.tick()
                if result is None:
                    break
            self.assertIsNone(result)
        finally:
            promo.SCENE_DEFS[1]["steps"] = original
        self.assertTrue(show.dead)
        self.assertTrue(show.error.startswith("Stopped:"))
        self.assertIn("boom", show.error)
        self.assertFalse(bpy.app.timers.is_registered(show.callback))
        # Kept until the screen has been given back, so a rerun finds it.
        self.assertIs(bpy.app.driver_namespace[promo.STATE_KEY], show)
        # The caption stays up for a while, then the drawing handler goes.
        self.assertIsNotNone(show.handle)
        self.assertTrue(bpy.app.timers.is_registered(show.remove_callback))
        # The screen is given back after the message has been up for a while.
        self.assertTrue(bpy.app.timers.is_registered(show.leave_callback))
        show.remove_handle()
        bpy.app.timers.unregister(show.remove_callback)
        bpy.app.timers.unregister(show.leave_callback)
        show.leave()
        self.assertNotIn(promo.STATE_KEY, bpy.app.driver_namespace)
        self.assertIsNone(show.handle)

    def test_no_viewport_to_be_found_ends_the_run_with_a_reason(self):
        clock = FakeClock()
        show = promo.Show([1], clock=clock)
        show.start()
        show.stage.find = lambda: None
        show.stage.state = "ready"
        result = 0
        for _ in range(1000):
            clock.now += 1.0 / 60.0
            result = show.tick()
            if result is None:
                break
        self.assertIsNone(result)
        self.assertTrue(show.dead)
        self.assertIn("no 3D viewport", show.error)
        show.remove_handle()
        bpy.app.timers.unregister(show.remove_callback)

    def test_a_refused_button_is_reported_in_the_add_ons_words(self):
        show = promo.Show([1], clock=FakeClock())
        show.begin()
        scene = bpy.data.scenes.new("empty")
        with self.assertRaises(RuntimeError) as caught:
            promo.need({"CANCELLED"}, "Record After", scene)
        self.assertIn("Record After did not work", str(caught.exception))

    def test_running_again_ends_the_earlier_run(self):
        promo.SCENES = [1]
        first = promo.main()
        self.assertIsNotNone(first)
        self.assertTrue(bpy.app.timers.is_registered(first.callback))
        self.assertIsNotNone(first.handle)
        second = promo.main()
        self.assertTrue(first.dead)
        self.assertFalse(bpy.app.timers.is_registered(first.callback))
        self.assertIsNone(first.handle)
        self.assertIs(bpy.app.driver_namespace[promo.STATE_KEY], second)
        second.cancel()
        self.assertIsNone(second.handle)
        second.leave()
        self.assertNotIn(promo.STATE_KEY, bpy.app.driver_namespace)

    def test_opening_another_file_ends_the_run_and_its_drawing(self):
        promo.SCENES = [1]
        show = promo.main()
        self.assertIn(show.guard, bpy.app.handlers.load_pre)
        show.guard("other.blend")
        self.assertTrue(show.dead)
        self.assertIsNone(show.handle)
        self.assertFalse(bpy.app.timers.is_registered(show.callback))
        self.assertNotIn(show.guard, bpy.app.handlers.load_pre)
        # An ordinary end takes the guard off as well.
        again = promo.main()
        again.cancel()
        self.assertNotIn(again.guard, bpy.app.handlers.load_pre)

    def test_stop_only_stops(self):
        promo.SCENES = [1]
        first = promo.main()
        promo.STOP = True
        try:
            self.assertIsNone(promo.main())
        finally:
            promo.STOP = False
        self.assertTrue(first.dead)
        self.assertNotIn(promo.STATE_KEY, bpy.app.driver_namespace)

    def test_captions_off_still_leaves_the_countdown(self):
        promo.CAPTIONS = False
        try:
            show = promo.Show([1])
            show.begin()
            show.player.chip, show.player.line = "1 · One cube", "New Move"
            show.count_until = show.clock() + 3.0
            state = show.view_state(show.clock())
        finally:
            promo.CAPTIONS = True
        self.assertEqual(state["chip"], "")
        self.assertEqual(state["line"], "")
        self.assertEqual(state["count"], 3)


class TestViewsAndCaptions(Case):

    ASPECTS = ((1574 / 954.0, 0.20), (1920 / 1080.0, 0.17), (1.2, 0.30))

    def test_every_scene_keeps_its_action_in_the_clear(self):
        scene = bpy.data.scenes.new("views")
        window().scene = scene
        for number in (1, 2, 3):
            parts = promo.SCENE_DEFS[number]["build"](scene)
            spec = promo.SCENE_DEFS[number]["view"](parts)
            for aspect, sidebar in self.ASPECTS:
                metrics = {"width": 1000.0, "height": 1000.0 / aspect,
                           "visible": 1000.0 * (1.0 - sidebar), "top": 60.0, "left": 40.0}
                clear = promo.margins(metrics)
                centre, rotation, distance, lens = promo.frame_view(
                    spec["frame"], spec["azimuth"], spec["elevation"], 50.0, aspect, clear)
                shown, _tans, _axes = promo.project(
                    spec["frame"], centre, rotation, distance, lens, aspect)
                left, right, top, bottom = clear
                for x, y in shown:
                    self.assertTrue(-1.0 + 2.0 * left - 1e-3 <= x <= 1.0 - 2.0 * right + 1e-3, (number, x))
                    self.assertTrue(-1.0 + 2.0 * bottom - 1e-3 <= y <= 1.0 - 2.0 * top + 1e-3, (number, y))
                self.assertTrue(4.0 < distance < 60.0, distance)
                # Clear of the toolbar on the left as well.
                self.assertGreaterEqual(min(x for x, _y in shown), -1.0 + 2.0 * (40.0 / 1000.0) - 1e-3)

    def test_the_view_looks_from_the_front_left_and_above(self):
        rotation = promo.view_rotation(-30.0, 24.0)
        eye = rotation @ Vector((0.0, 0.0, 1.0))
        self.assertLess(eye.x, 0.0)
        self.assertLess(eye.y, 0.0)
        self.assertGreater(eye.z, 0.0)
        # The picture is the right way up, and +X runs from left to right.
        self.assertGreater((rotation @ Vector((0.0, 1.0, 0.0))).z, 0.5)
        self.assertGreater((rotation @ Vector((1.0, 0.0, 0.0))).x, 0.5)

    def test_the_viewport_is_set_to_a_framed_three_quarter_view(self):
        self.run_scenes([2])
        _area, space = viewport()
        rv3d = space.region_3d
        self.assertGreater(rv3d.view_distance, 4.0)
        self.assertEqual(space.lens, 50.0)       # the viewport's own

    def paint(self, view, metrics=None, scale=1.0):
        painter = FakePainter()
        metrics = metrics or {"width": 1574, "height": 954, "visible": 1250, "top": 60}
        promo.draw_overlay(painter, view, metrics, scale, 100.0)
        return painter, metrics

    def test_captions_stay_inside_the_free_part_of_the_viewport(self):
        lines = ["New Move — where it stands is Before",
                 "Ride Along: the other petals copy it, from their own place",
                 "Curve the Path — the ends stay on A and B", "Play"]
        for scale in (0.8, 1.0, 1.5, 2.0):
            for line in lines:
                painter, metrics = self.paint(
                    {"chip": "3 · Curved path", "line": line, "changed": 0.0},
                    {"width": 1574 * scale, "height": 954 * scale, "visible": 1250 * scale,
                     "top": 60 * scale}, scale)
                self.assertTrue(painter.texts)
                for x, y, w, h in painter.rects:
                    self.assertGreaterEqual(x, 0.0)
                    self.assertGreaterEqual(y, 0.0)
                    self.assertLessEqual(x + w, metrics["visible"], (line, scale))
                    self.assertLessEqual(y + h, metrics["height"] - metrics["top"] + 1e-6)

    def test_captions_clear_the_toolbar_on_the_left(self):
        metrics = {"width": 1574, "height": 954, "visible": 1250, "top": 60, "left": 58}
        for view in ({"chip": "2 \u00b7 Ride Along", "line": "Lead +30 \u2014 goes first", "changed": 0.0},
                     {"count": 3, "note": "Earlier takes are kept, renamed (old).", "changed": 0.0}):
            painter = FakePainter()
            promo.draw_overlay(painter, view, metrics, 1.0, 100.0)
            for x, y, w, h in painter.rects:
                self.assertGreaterEqual(x, metrics["left"])
                self.assertLessEqual(x + w, metrics["visible"])
            for x, y, size, string in painter.texts:
                self.assertGreaterEqual(x, metrics["left"], string)

    def test_the_stage_measures_the_toolbar_the_header_and_the_sidebar(self):
        show = promo.Show([1], clock=FakeClock())
        show.begin()
        area = viewport()[0]
        measured = show.stage.metrics(area)
        for key in ("width", "height", "visible", "top", "left", "window_height"):
            self.assertIn(key, measured)
        self.assertGreater(measured["left"], 0)        # the toolbar is there
        self.assertGreater(measured["top"], 0)         # and the header and tool header
        self.assertGreater(measured["width"], measured["left"])
        clear = promo.margins(measured)
        self.assertGreater(clear[0], 0.03)             # the toolbar is kept clear in framing too

    def test_scrolling_the_sidebar_is_a_best_effort_that_never_raises(self):
        show = promo.Show([1], clock=FakeClock())
        show.begin()
        with show.stage.override():
            self.assertIn(promo.scroll_panel(True), (True, False))
            self.assertIn(promo.scroll_panel(False), (True, False))
        self.assertIsNone(self.promo_call_without_window())

    def promo_call_without_window(self):
        # Outside any override there is no area to scroll: quietly nothing.
        promo.scroll_panel()

    def test_chip_sits_top_left_below_the_header_and_line_at_the_bottom(self):
        painter, metrics = self.paint({"chip": "1 · One cube", "line": "Record After",
                                       "changed": 0.0})
        chip = painter.rects[0]
        self.assertLess(chip[0], 40.0)
        self.assertGreater(chip[1], metrics["height"] * 0.8)
        self.assertLessEqual(chip[1] + chip[3], metrics["height"] - metrics["top"])
        line = next(r for r in painter.rects if r[3] > 50.0 and r[1] < 200.0)
        self.assertLess(line[1], 200.0)

    def test_a_new_line_fades_in(self):
        faint = FakePainter()
        promo.draw_overlay(faint, {"line": "Record After", "changed": 100.0},
                           {"width": 1574, "height": 954, "visible": 1250, "top": 60}, 1.0, 100.0)
        full = FakePainter()
        promo.draw_overlay(full, {"line": "Record After", "changed": 90.0},
                           {"width": 1574, "height": 954, "visible": 1250, "top": 60}, 1.0, 100.0)
        self.assertLess(faint.colors[0][3], 0.1)
        self.assertGreater(full.colors[0][3], 0.7)

    def test_countdown_and_error_are_drawn(self):
        painter, _metrics = self.paint({"count": 4, "note": "Scene 4 is left out."})
        self.assertIn("4", [t[3] for t in painter.texts])
        painter, _metrics = self.paint({"error": "Stopped: RuntimeError: boom", "line": "x",
                                        "changed": 0.0})
        self.assertIn("Stopped: RuntimeError: boom", " ".join(t[3] for t in painter.texts))

    def test_drawing_through_the_handler_with_a_recording_painter(self):
        show = promo.Show([1], clock=FakeClock())
        show.begin()
        show.painter_class = FakePainter
        painters = []
        original = FakePainter.__init__

        def remember(self):
            original(self)
            painters.append(self)
        FakePainter.__init__ = remember
        try:
            show.player.chip, show.player.line = "1 · One cube", "New Move — where it stands"
            with show.stage.override():
                show.draw()
        finally:
            FakePainter.__init__ = original
        self.assertTrue(show.drawing_ok)
        self.assertEqual(len(painters), 1)
        self.assertTrue(painters[0].texts and painters[0].finished)

    def test_a_drawing_error_switches_captions_off_but_not_the_show(self):
        class Broken(FakePainter):
            def rect(self, *args):
                raise RuntimeError("no gpu")
        show = promo.Show([1], clock=FakeClock())
        show.begin()
        show.painter_class = Broken
        show.player.chip = "1 · One cube"
        with show.stage.override():
            show.draw()
        self.assertFalse(show.drawing_ok)
        self.assertFalse(show.dead)


class FakePainter:
    """Records what would be drawn."""

    def __init__(self):
        self.rects, self.texts, self.colors, self.finished = [], [], [], False
        self.text_colors = []

    def finish(self):
        self.finished = True

    def rect(self, x, y, w, h, radius, color):
        self.rects.append((x, y, w, h))
        self.colors.append(color)

    def text(self, x, y, pixels, color, string):
        self.texts.append((x, y, pixels, string))
        self.text_colors.append(color)

    def width(self, pixels, string):
        return 0.55 * pixels * len(string)

    def cap_height(self, pixels):
        return 0.7 * pixels


class TestBundle(Case):

    def test_the_bundle_compiles_imports_cleanly_and_plays(self):
        ok, messages = bundle.bundle(FLOWER_PATH, DIST)
        self.assertTrue(ok, messages)
        source = read(DIST)
        compile(source, DIST, "exec")
        before = dict(bpy.app.driver_namespace)
        # Run as a script would be, but headless: no timers, no drawing.
        scope = runpy.run_path(DIST, run_name="copythat_promo_dist")
        self.assertTrue(bpy.app.background)
        self.assertNotIn(scope["STATE_KEY"], bpy.app.driver_namespace)
        self.assertEqual(before.keys(), bpy.app.driver_namespace.keys())
        self.assertIn(">>> FLOWER BEGIN", source)
        self.assertIn("<<< FLOWER END", source)
        if HAVE_FLOWER:
            self.assertIsNotNone(scope["FLOWER_SOURCE"])
            self.assertIsNotNone(scope["FLOWER"])
            self.assertEqual(scope["scenes_to_play"]()[0], [1, 2, 3, 4])
        # The bundled file plays a scene as well as the source does.
        scope["FULL_VIEWPORT"] = False
        show = scope["Show"]([1, 2, 3, 4] if HAVE_FLOWER else [1, 2, 3], instant=True)
        show.run_instant()
        for number in show.scenes:
            data = show.scenes[number].rigmoves_rig.rigmoves
            self.assertTrue(all(m.built for m in data.moves), number)

    def test_the_flower_is_inlined_as_lines_that_match_the_file(self):
        if not HAVE_FLOWER:
            self.skipTest("needs the real flower.py")
        ok, _messages = bundle.bundle(FLOWER_PATH, DIST)
        self.assertTrue(ok)
        scope = runpy.run_path(DIST, run_name="copythat_promo_dist")
        self.assertEqual(scope["FLOWER_SOURCE"], read(FLOWER_PATH).rstrip("\n"))

    def test_without_flower_scene_four_is_left_out_with_a_message(self):
        with tempfile.TemporaryDirectory() as folder:
            out = os.path.join(folder, "dist", "copythat_promo.py")
            ok, messages = bundle.bundle(os.path.join(folder, "nothing.py"), out)
            self.assertTrue(ok)
            self.assertTrue(any("LEFT OUT" in m for m in messages), messages)
            scope = runpy.run_path(out, run_name="copythat_promo_dist")
            self.assertIsNone(scope["FLOWER_SOURCE"])
            self.assertIsNone(scope["FLOWER"])
            numbers, notes = scope["scenes_to_play"]()
            self.assertEqual(numbers, [1, 2, 3])
            self.assertTrue(any("Scene 4 is left out" in n for n in notes))

    def test_a_flower_that_does_not_compile_is_left_out_too(self):
        with tempfile.TemporaryDirectory() as folder:
            bad = os.path.join(folder, "flower.py")
            with open(bad, "w", encoding="utf-8") as handle:
                handle.write("def build_flower(scene:\n    pass\n")
            out = os.path.join(folder, "copythat_promo.py")
            ok, messages = bundle.bundle(bad, out)
            self.assertTrue(ok)
            self.assertTrue(any("does not compile" in m and "LEFT OUT" in m for m in messages))
            self.assertIsNone(runpy.run_path(out, run_name="x")["FLOWER_SOURCE"])
        with tempfile.TemporaryDirectory() as folder:
            partial = os.path.join(folder, "flower.py")
            with open(partial, "w", encoding="utf-8") as handle:
                handle.write("def build_flower(scene):\n    return {}\n")
            ok, messages = bundle.bundle(partial, os.path.join(folder, "out.py"))
            self.assertTrue(any("flower_steps" in m and "LEFT OUT" in m for m in messages))

    def test_the_dist_file_is_ascii_safe_where_it_inlines(self):
        if not HAVE_FLOWER:
            self.skipTest("needs the real flower.py")
        bundle.bundle(FLOWER_PATH, DIST)
        source = read(DIST)
        inlined = source[source.index(">>> FLOWER BEGIN"):source.index("<<< FLOWER END")]
        inlined.encode("ascii")
        # The 256-character limit applies to drivers, not to this file; but
        # lines long enough to choke a text editor would be a mistake.
        self.assertLess(max(len(line) for line in source.split("\n")), 400)


if __name__ == "__main__":
    unittest.main(verbosity=2)
