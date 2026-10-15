"""CopyThat, driven end to end in Blender without a window.

Run from the repository root, with Blender as a Python module (`pip install
bpy`, see README.md):

    python tests/test_rigmoves.py

or inside a Blender install:

    blender --background --factory-startup --python tests/test_rigmoves.py

Every test starts from an empty scene, presses the same buttons a user would,
and measures where the meshes actually end up - the evaluated, deformed
vertices, not the objects' own transforms, which the rig never moves.
"""

import importlib
import math
import os
import sys
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bpy  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import rigmoves  # noqa: E402

TOLERANCE = 1e-4


def setUpModule():
    rigmoves.register()


def tearDownModule():
    rigmoves.unregister()


def cube(name, location):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=location)
    obj = bpy.context.object
    obj.name = name
    return obj


def select(*objects):
    for obj in bpy.context.view_layer.objects:
        obj.select_set(False)
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]


def world_points(obj):
    """Where the mesh really is, after the rig has deformed it."""
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    points = [evaluated.matrix_world @ v.co for v in mesh.vertices]
    evaluated.to_mesh_clear()
    return points


def rest_points(obj):
    """Where the mesh is by its own transform alone, before any rig."""
    return [obj.matrix_world @ v.co for v in obj.data.vertices]


def centre(obj):
    points = world_points(obj)
    return sum(points, points[0] * 0.0) / len(points)


def drift(obj, expected):
    return max((a - b).length for a, b in zip(world_points(obj), expected))


def rig():
    return bpy.context.scene.rigmoves_rig


def drive(carrier, share):
    """Slide a move's handle to this share of its rail, as a drag would."""
    handle = rig().pose.bones[carrier.handle_name]
    handle.location.y = carrier.rail * share
    bpy.context.view_layer.update()


def undo_push():
    """A step to undo back to. Headless Blender keeps no undo history unless
    asked to, and does not push a step of its own for an operator."""
    window = bpy.context.window_manager.windows[0]
    with bpy.context.temp_override(window=window, screen=window.screen):
        assert bpy.ops.ed.undo_push(message="test") == {"FINISHED"}


def undo_once():
    """Ctrl+Z. Everything held from before it - objects, parts - is stale."""
    window = bpy.context.window_manager.windows[0]
    with bpy.context.temp_override(window=window, screen=window.screen):
        assert bpy.ops.ed.undo() == {"FINISHED"}


def record_move(objects, pose):
    """New Move on these objects, pose them by hand, Record After."""
    select(*objects)
    assert bpy.ops.rigmoves.new_move() == {"FINISHED"}
    before = {o.name: rest_points(o) for o in objects}
    pose()
    bpy.context.view_layer.update()
    after = {o.name: rest_points(o) for o in objects}
    index = len(rig().rigmoves.moves) - 1
    assert bpy.ops.rigmoves.record(index=index, which="AFTER") == {"FINISHED"}
    return before, after


def ring_places(centre, count, radius, start=0.0):
    """Places on a ring round `centre`, on a plane tipped off the world's:
    tilted 30 degrees about X and then turned 20 about Z, so that a ring read
    as flat on the ground - the world's Z for an axis - gives itself away."""
    turn = Matrix.Rotation(math.radians(20.0), 3, "Z") @ Matrix.Rotation(
        math.radians(30.0), 3, "X")
    along, across = turn @ Vector((1.0, 0.0, 0.0)), turn @ Vector((0.0, 1.0, 0.0))
    out = []
    for number in range(count):
        angle = math.radians(start + 360.0 * number / count)
        out.append(Vector(centre) + radius * (math.cos(angle) * along
                                              + math.sin(angle) * across))
    return out


def turn_about(point, axis, degrees):
    """A turn of this many degrees about an axis through a point."""
    return (Matrix.Translation(point)
            @ Matrix.Rotation(math.radians(degrees), 4, axis)
            @ Matrix.Translation(-Vector(point)))


class Sketch:
    """A stand-in for a panel layout that notes what is drawn, and where.

    The panel cannot be drawn without a window, but its code can run against
    this: every row, column and sub-panel is another sketch, and every button
    is logged with the path of sub-panels it was put in.
    """

    def __init__(self, log, where=()):
        self.log, self.where = log, where

    def child(self, name):
        return Sketch(self.log, self.where + (name,))

    def row(self, **_kwargs):
        return self.child("row")

    column = split = box = row

    def panel_prop(self, _data, prop):
        return self.child("head:" + prop), self.child("body:" + prop)

    def operator(self, idname, text="", **_kwargs):
        self.log.append((self.where, idname, text))
        return types.SimpleNamespace()

    def __getattr__(self, name):
        # label, prop, separator and the rest: nothing to note.
        if name.startswith("__"):
            raise AttributeError(name)
        return lambda *args, **kwargs: None


def drawn_buttons():
    """Every button the panel draws now, as (path, operator id, text)."""
    log = []

    class Drawing:
        layout = Sketch(log)

    for name in dir(rigmoves.RIGMOVES_PT_panel):
        if name == "draw" or name.startswith("_draw"):
            setattr(Drawing, name, getattr(rigmoves.RIGMOVES_PT_panel, name))
    Drawing().draw(bpy.context)
    return log


class CopyThatCase(unittest.TestCase):

    def setUp(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)

    def our_drivers(self):
        animation = rig().animation_data
        return [d for d in (animation.drivers if animation else ())
                if "constraints[" in d.data_path]


class TestObjects(CopyThatCase):

    def setUp(self):
        super().setUp()
        self.lid = cube("Lid", (0.0, 0.0, 1.0))
        self.arm = cube("Arm", (3.0, 0.0, 1.0))

        def pose():
            self.lid.rotation_euler.x = math.radians(90.0)
            self.arm.location.z += 1.0

        self.before, self.after = record_move([self.lid, self.arm], pose)
        self.assertEqual(bpy.ops.rigmoves.build(), {"FINISHED"})
        self.move = rig().rigmoves.moves[0]

    def test_ends_land_on_the_recordings(self):
        drive(self.move, 0.0)
        self.assertLess(drift(self.lid, self.before["Lid"]), TOLERANCE)
        self.assertLess(drift(self.arm, self.before["Arm"]), TOLERANCE)
        drive(self.move, 1.0)
        self.assertLess(drift(self.lid, self.after["Lid"]), TOLERANCE)
        self.assertLess(drift(self.arm, self.after["Arm"]), TOLERANCE)

    def test_half_way_is_half_way(self):
        drive(self.move, 0.5)
        self.assertAlmostEqual(centre(self.arm).z, 1.5, places=4)

    def test_delay_holds_then_travels(self):
        self.move.parts["Arm"].start = 0.3
        self.move.ease = "SMOOTH"
        bpy.ops.rigmoves.build()
        drive(self.move, 0.3)
        self.assertAlmostEqual(centre(self.arm).z, 1.0, places=4)
        drive(self.move, 1.0)
        self.assertAlmostEqual(centre(self.arm).z, 2.0, places=4)

    def test_drivers_need_no_python(self):
        # A simple expression runs with Auto Run Python Scripts off, which is
        # how most people open a file they were sent. Anything else stops.
        self.move.parts["Arm"].start = 0.3
        self.move.ease = "SMOOTH"
        bpy.ops.rigmoves.build()
        drivers = self.our_drivers()
        self.assertEqual(len(drivers), 2)
        for curve in drivers:
            self.assertTrue(curve.driver.is_valid, curve.driver.expression)
            self.assertTrue(curve.driver.is_simple_expression, curve.driver.expression)

    def test_longest_usual_expression_fits(self):
        # A part in a combined control, eased, with a rider-made window of
        # awkward fractions: the longest a driver gets without hidden From/To
        # settings. Blender cuts anything past 256 characters.
        own = "max({:s},{:s})".format(
            rigmoves.VAR, rigmoves.window(rigmoves.GROUP_VAR, 1.0 / 3.0, 1.0))
        expression = rigmoves.EASE["SMOOTH"].replace(
            "{t}", rigmoves.window(own, 17.0 / 67.0, 50.0 / 67.0))
        self.assertLess(len(expression), 256, expression)

    def test_step_is_passed_through(self):
        self.assertEqual(bpy.ops.rigmoves.add_step(index=0), {"FINISHED"})
        # Drag the object itself, as a user would, overshooting the After.
        self.arm.location.z = 3.0
        bpy.context.view_layer.update()
        self.assertEqual(bpy.ops.rigmoves.record(index=0, which="STEP", step=0),
                         {"FINISHED"})
        bpy.ops.rigmoves.build()
        drive(self.move, 0.5)
        self.assertAlmostEqual(centre(self.arm).z, 3.0, places=4)
        drive(self.move, 1.0)
        self.assertLess(drift(self.arm, self.after["Arm"]), TOLERANCE)
        # The lid was not moved for the step, so it keeps its own path.
        self.assertLess(drift(self.lid, self.after["Lid"]), TOLERANCE)

    def test_delay_takes_effect_without_a_build(self):
        self.move.parts["Arm"].start = 0.5
        drive(self.move, 0.5)
        self.assertAlmostEqual(centre(self.arm).z, 1.0, places=4)

    def test_play_slider_is_the_handle(self):
        self.move.play = 50.0
        bpy.context.view_layer.update()
        self.assertAlmostEqual(centre(self.arm).z, 1.5, places=4)
        handle = rig().pose.bones[self.move.handle_name]
        self.assertAlmostEqual(handle.location.y, self.move.rail * 0.5, places=6)
        # Dragging the handle shows on the slider.
        drive(self.move, 0.25)
        self.assertAlmostEqual(self.move.play, 25.0, places=3)

    def test_play_slider_without_a_handle(self):
        self.move.handle = False
        bpy.ops.rigmoves.build()
        self.move.play = 100.0
        bpy.context.view_layer.update()
        self.assertLess(drift(self.arm, self.after["Arm"]), TOLERANCE)
        self.assertAlmostEqual(self.move.play, 100.0, places=3)

    def test_key_button_keys_the_handle(self):
        bpy.context.scene.frame_set(12)
        self.move.play = 40.0
        self.assertEqual(bpy.ops.rigmoves.key_control(index=0), {"FINISHED"})
        curves = [c for _h, c in rigmoves.rig_own_curves(rig(), rig().rigmoves)]
        self.assertEqual([(c.data_path.rsplit(".", 1)[-1], c.array_index) for c in curves],
                         [("location", 1)])
        key = curves[0].keyframe_points[0]
        self.assertAlmostEqual(key.co[0], 12.0)
        self.assertAlmostEqual(key.co[1], self.move.rail * 0.4, places=6)

    def test_animate_keys_the_whole_move(self):
        scene = bpy.context.scene
        scene.frame_set(10)
        scene.frame_end = 20
        self.move.play_frames = 40
        self.assertEqual(bpy.ops.rigmoves.animate(index=0), {"FINISHED"})
        self.assertEqual(scene.frame_end, 50)
        scene.frame_set(30)
        self.assertAlmostEqual(centre(self.arm).z, 1.5, places=4)
        scene.frame_set(50)
        self.assertLess(drift(self.arm, self.after["Arm"]), TOLERANCE)
        # Pressed again it replaces the keys rather than piling more on.
        scene.frame_set(1)
        self.assertEqual(bpy.ops.rigmoves.animate(index=0), {"FINISHED"})
        curves = [c for _h, c in rigmoves.rig_own_curves(rig(), rig().rigmoves)]
        self.assertEqual([len(c.keyframe_points) for c in curves], [2])
        # A Build keeps the keys, and does not call them a fault.
        bpy.ops.rigmoves.build()
        self.assertNotIn("animated by hand", rig().rigmoves.report)
        scene.frame_set(21)
        self.assertAlmostEqual(centre(self.arm).z, 1.5, places=4)

    def test_drag_after_the_eye_is_read_where_it_is_seen(self):
        # The eye leaves the bones posed; Build hides that under live sliders.
        bpy.ops.rigmoves.show(index=0, which="AFTER")
        bpy.ops.rigmoves.build()
        drive(self.move, 0.0)
        self.arm.location.z = 3.0
        bpy.context.view_layer.update()
        self.assertAlmostEqual(centre(self.arm).z, 3.0, places=4)
        bpy.ops.rigmoves.record(index=0, which="AFTER")
        bpy.ops.rigmoves.build()
        drive(self.move, 1.0)
        self.assertAlmostEqual(centre(self.arm).z, 3.0, places=4)

    def test_animate_survives_a_longer_rail(self):
        bpy.context.scene.frame_set(1)
        self.move.play_frames = 40
        bpy.ops.rigmoves.animate(index=0)
        was = self.move.rail
        # A pivot far off lengthens the handle's rail at the next Build.
        bpy.context.scene.cursor.location = (3.0, 0.0, 5.0)
        select(self.arm)
        bpy.ops.rigmoves.set_pivot(index=0, kind="CURSOR")
        self.assertNotAlmostEqual(self.move.rail, was, places=3)
        bpy.context.scene.frame_set(41)
        self.assertLess(drift(self.arm, self.after["Arm"]), TOLERANCE)

    def test_buttons_that_build_keep_an_unrecorded_drag(self):
        # Dragged to a new After but not recorded yet: a button that would
        # Build on the side must not throw the drag away.
        self.arm.location.z = 5.0
        bpy.context.view_layer.update()
        select(self.arm)
        self.assertEqual(bpy.ops.rigmoves.set_pivot(index=0, kind="BASE"), {"CANCELLED"})
        self.assertAlmostEqual(self.arm.location.z, 5.0)
        self.assertEqual(bpy.ops.rigmoves.record(index=0, which="AFTER"), {"FINISHED"})
        bpy.ops.rigmoves.build()
        drive(self.move, 1.0)
        self.assertAlmostEqual(centre(self.arm).z, 5.0, places=4)

    def test_a_handle_keyed_once_by_hand_is_kept(self):
        bpy.context.scene.tool_settings.use_keyframe_insert_auto = False
        self.move.play = 40.0
        bpy.ops.rigmoves.key_control(index=0)
        bpy.ops.rigmoves.build()
        curves = [c for _h, c in rigmoves.rig_own_curves(rig(), rig().rigmoves)]
        self.assertEqual([len(c.keyframe_points) for c in curves], [1])
        self.assertNotIn("lifted", rig().rigmoves.report)
        # With Auto Keying on, a lone key is what a drag leaves behind.
        bpy.context.scene.tool_settings.use_keyframe_insert_auto = True
        bpy.ops.rigmoves.build()
        self.assertEqual(rigmoves.rig_own_curves(rig(), rig().rigmoves), [])

    def test_animate_raises_no_alarm(self):
        bpy.ops.rigmoves.animate(index=0)
        self.assertEqual(rigmoves.stray_curves(rig(), rig().rigmoves), [])

    def test_removed_control_takes_its_keys(self):
        bpy.ops.rigmoves.animate(index=0)
        bpy.ops.rigmoves.remove(index=0)
        animation = rig().animation_data
        action = animation.action if animation else None
        left = [c.data_path for _h, c in rigmoves.rig_own_curves(rig(), rig().rigmoves)]
        self.assertEqual(left, [])
        if action is not None:
            for layer in action.layers:
                for strip in layer.strips:
                    for bag in strip.channelbags:
                        self.assertFalse([c for c in bag.fcurves if "handle" in c.data_path])

    def test_animate_refuses_a_slider_still_driven(self):
        self.move.handle = False
        self.assertEqual(bpy.ops.rigmoves.animate(index=0), {"CANCELLED"})
        bpy.ops.rigmoves.build()
        self.assertEqual(bpy.ops.rigmoves.animate(index=0), {"FINISHED"})

    def test_paths_show_where_the_parts_go(self):
        self.assertEqual(bpy.ops.rigmoves.show_paths(index=0, show=True), {"FINISHED"})
        drawn = self.move.paths_object
        self.assertIsNotNone(drawn)
        self.assertEqual(len(drawn.data.splines), 2)
        arm = drawn.data.splines[1].points
        self.assertLess((Vector(arm[0].co[:3]) - Vector((3.0, 0.0, 1.0))).length, TOLERANCE)
        self.assertLess((Vector(arm[-1].co[:3]) - Vector((3.0, 0.0, 2.0))).length, TOLERANCE)
        # Drawn again by a Build - from the rest shape, wherever the control
        # stands - and gone when hidden.
        drive(self.move, 1.0)
        bpy.ops.rigmoves.build()
        drawn = self.move.paths_object
        self.assertIsNotNone(drawn)
        arm = drawn.data.splines[1].points
        self.assertLess((Vector(arm[0].co[:3]) - Vector((3.0, 0.0, 1.0))).length, TOLERANCE)
        name = drawn.name
        self.assertEqual(bpy.ops.rigmoves.show_paths(index=0, show=False), {"FINISHED"})
        self.assertIsNone(bpy.data.objects.get(name))
        self.assertIsNone(self.move.paths_object)

    def add_mid_step(self, z):
        """One step, with the arm dragged to this height for it, then Build."""
        self.assertEqual(bpy.ops.rigmoves.add_step(index=0), {"FINISHED"})
        self.arm.location.z = z
        bpy.context.view_layer.update()
        self.assertEqual(bpy.ops.rigmoves.record(index=0, which="STEP", step=0),
                         {"FINISHED"})
        bpy.ops.rigmoves.build()

    def test_slow_stretch_takes_more_of_the_control(self):
        # The step half way up, so at even speed the arm climbs steadily.
        self.add_mid_step(1.5)
        # Ten times slower into the step: it takes ten parts of the control
        # to the last stretch's one. Takes effect without a Build.
        self.move.steps[0].speed = -50
        reach = 10.0 / 11.0
        drive(self.move, reach / 2.0)
        self.assertAlmostEqual(centre(self.arm).z, 1.25, places=4)
        drive(self.move, reach)
        self.assertAlmostEqual(centre(self.arm).z, 1.5, places=4)
        drive(self.move, 1.0)
        self.assertLess(drift(self.arm, self.after["Arm"]), TOLERANCE)
        drive(self.move, 0.0)
        self.assertLess(drift(self.arm, self.before["Arm"]), TOLERANCE)
        # And a Build keeps it.
        bpy.ops.rigmoves.build()
        drive(self.move, reach)
        self.assertAlmostEqual(centre(self.arm).z, 1.5, places=4)

    def test_part_without_a_step_key_keeps_the_same_time(self):
        self.add_mid_step(1.5)
        self.move.steps[0].speed = -50
        # The lid was never moved for the step, so it has no key there - but
        # the move's time is what is bent, so it is half way round exactly
        # when the arm reaches the step.
        drive(self.move, 10.0 / 11.0)
        half_turn = [Matrix.Translation((0.0, 0.0, 1.0))
                     @ Matrix.Rotation(math.radians(45.0), 4, "X") @ v.co
                     for v in self.lid.data.vertices]
        self.assertLess(drift(self.lid, half_turn), TOLERANCE)

    def test_equal_speeds_play_as_even(self):
        self.add_mid_step(1.5)
        self.move.steps[0].speed = 30
        self.move.speed_after = 30
        drive(self.move, 0.25)
        self.assertAlmostEqual(centre(self.arm).z, 1.25, places=4)

    def test_even_speeds_leave_the_drivers_plain(self):
        self.add_mid_step(1.5)
        self.assertEqual([len(c.keyframe_points) for c in self.our_drivers()], [0, 0])
        self.move.steps[0].speed = -20
        self.assertEqual([len(c.keyframe_points) for c in self.our_drivers()], [3, 3])
        # With the step gone there is one stretch again, and nothing to share.
        self.assertEqual(bpy.ops.rigmoves.drop_step(index=0, step=0), {"FINISHED"})
        self.assertEqual([len(c.keyframe_points) for c in self.our_drivers()], [0, 0])

    def test_remove_leaves_nothing_behind(self):
        drive(self.move, 0.0)
        self.assertEqual(bpy.ops.rigmoves.remove(index=0), {"FINISHED"})
        animation = rig().animation_data
        self.assertEqual([d.data_path for d in (animation.drivers if animation else ())], [])
        for pose_bone in rig().pose.bones:
            self.assertFalse([c for c in pose_bone.constraints if c.type == "ACTION"])
        for obj, before in ((self.lid, self.before["Lid"]), (self.arm, self.before["Arm"])):
            self.assertIsNone(obj.parent)
            self.assertFalse([m for m in obj.modifiers if m.type == "ARMATURE"])
            self.assertLess(drift(obj, before), TOLERANCE)


class TestRiders(CopyThatCase):
    """One petal recorded, another riding along from its own place.

    The leader is turned 20 degrees and the rider 110 and half its size, so
    the leader's own left, the rider's own left and the world's all differ:
    copying the move in the wrong frame cannot pass by accident.
    """

    def setUp(self):
        super().setUp()
        self.petal = cube("Petal", (1.0, 0.0, 0.0))
        self.petal.rotation_euler.z = math.radians(20.0)
        self.rider = cube("Rider", (0.0, 1.0, 0.0))
        self.rider.rotation_euler.z = math.radians(110.0)
        self.rider.scale = (0.5, 0.5, 0.5)
        bpy.context.view_layer.update()
        self.home = self.petal.matrix_world.copy()
        self.seat = self.rider.matrix_world.copy()

        def pose():
            # Out along its own X, and tipped about its own Y.
            self.petal.matrix_world = (self.home @ Matrix.Translation((1.0, 0.0, 0.0))
                                       @ Matrix.Rotation(math.radians(30.0), 4, "Y"))

        self.before, self.after = record_move([self.petal], pose)
        self.half = (Matrix.Translation((0.5, 0.0, 0.0))
                     @ Matrix.Rotation(math.radians(15.0), 4, "Y"))
        self.full = (Matrix.Translation((1.0, 0.0, 0.0))
                     @ Matrix.Rotation(math.radians(30.0), 4, "Y"))

    def ride(self):
        select(self.rider, self.petal)
        bpy.context.view_layer.objects.active = self.petal
        return bpy.ops.rigmoves.ride_along(index=0, leader="Petal", rig_name=rig().name)

    def expected(self, travel):
        """The rider's mesh after the leader's own-frame travel, from its seat.

        The travel goes between the rider's frame and its size: a half-size
        rider still goes as far as the leader does, not half as far.
        """
        location, rotation, size = self.seat.decompose()
        frame = Matrix.Translation(location) @ rotation.to_matrix().to_4x4()
        return [frame @ travel @ Matrix.Diagonal(size).to_4x4() @ v.co
                for v in self.rider.data.vertices]

    def check_rides(self):
        move = rig().rigmoves.moves[0]
        drive(move, 0.0)
        self.assertLess(drift(self.rider, self.expected(Matrix())), TOLERANCE)
        drive(move, 0.5)
        self.assertLess(drift(self.rider, self.expected(self.half)), TOLERANCE)
        drive(move, 1.0)
        self.assertLess(drift(self.rider, self.expected(self.full)), TOLERANCE)
        self.assertLess(drift(self.petal, self.after["Petal"]), TOLERANCE)

    def test_rider_copies_the_move_from_its_own_place(self):
        bpy.ops.rigmoves.build()
        self.assertEqual(self.ride(), {"FINISHED"})
        self.check_rides()

    def test_the_ninth_part_of_a_move_keeps_its_leader(self):
        # A move's parts can move in memory when one is added, from the ninth
        # on: the leader, read after that, was a dead pointer, and the last
        # rider was left riding with nobody.
        for number in range(8):
            extra = cube("Extra{:d}".format(number), (float(number), 5.0, 0.0))
            select(self.petal, extra)
            self.assertEqual(bpy.ops.rigmoves.ride_along(index=0, leader="Petal",
                                                         rig_name=rig().name),
                             {"FINISHED"})
        move = rig().rigmoves.moves[0]
        self.assertEqual([p.leader for p in move.parts if p.name != "Petal"],
                         ["Petal"] * 8)
        self.assertEqual(bpy.ops.rigmoves.build(), {"FINISHED"})
        self.assertNotIn("no longer in its move", rig().rigmoves.report)

    def test_rider_added_before_the_first_build(self):
        self.assertEqual(self.ride(), {"FINISHED"})
        bpy.ops.rigmoves.build()
        self.check_rides()

    def test_rider_follows_a_step_added_later(self):
        bpy.ops.rigmoves.build()
        self.ride()
        self.assertEqual(bpy.ops.rigmoves.add_step(index=0), {"FINISHED"})
        self.petal.matrix_world = self.home @ Matrix.Translation((2.0, 0.0, 0.0))
        bpy.context.view_layer.update()
        self.assertEqual(bpy.ops.rigmoves.record(index=0, which="STEP", step=0),
                         {"FINISHED"})
        bpy.ops.rigmoves.build()
        drive(rig().rigmoves.moves[0], 0.5)
        self.assertLess(drift(self.rider, self.expected(Matrix.Translation((2.0, 0.0, 0.0)))),
                        TOLERANCE)

    def riding(self):
        bpy.ops.rigmoves.build()
        self.ride()
        move = rig().rigmoves.moves[0]
        return move, next(p for p in move.parts if p.leader)

    def test_lead_behind_waits_for_the_leader(self):
        move, rider = self.riding()
        # Takes effect without a Build. The control now plays two leader
        # lengths: the leader in the first half, the rider in the second.
        rider.lead = -50
        drive(move, 0.5)
        self.assertLess(drift(self.petal, self.after["Petal"]), TOLERANCE)
        self.assertLess(drift(self.rider, self.expected(Matrix())), TOLERANCE)
        drive(move, 0.75)
        self.assertLess(drift(self.rider, self.expected(self.half)), TOLERANCE)
        drive(move, 1.0)
        self.assertLess(drift(self.rider, self.expected(self.full)), TOLERANCE)

    def test_lead_ahead_goes_first(self):
        move, rider = self.riding()
        rider.lead = 50
        drive(move, 0.25)
        self.assertLess(drift(self.rider, self.expected(self.half)), TOLERANCE)
        self.assertLess(drift(self.petal, self.before["Petal"]), TOLERANCE)
        drive(move, 0.5)
        self.assertLess(drift(self.rider, self.expected(self.full)), TOLERANCE)
        self.assertLess(drift(self.petal, self.before["Petal"]), TOLERANCE)
        drive(move, 1.0)
        self.assertLess(drift(self.petal, self.after["Petal"]), TOLERANCE)
        # And a Build keeps it.
        bpy.ops.rigmoves.build()
        drive(move, 0.5)
        self.assertLess(drift(self.rider, self.expected(self.full)), TOLERANCE)

    def test_rider_can_be_taken_out_again(self):
        bpy.ops.rigmoves.build()
        self.ride()
        move = rig().rigmoves.moves[0]
        position = next(i for i, p in enumerate(move.parts) if p.leader)
        self.assertEqual(bpy.ops.rigmoves.drop_rider(index=0, part=position), {"FINISHED"})
        self.assertIsNone(self.rider.parent)
        self.assertFalse([m for m in self.rider.modifiers if m.type == "ARMATURE"])
        self.assertIsNone(rig().data.bones.get("Rider"))
        for curve in rig().animation_data.drivers:
            self.assertTrue(curve.driver.is_valid, curve.data_path)
        # The leader plays on as before, and the rider stays put.
        drive(move, 1.0)
        self.assertLess(drift(self.petal, self.after["Petal"]), TOLERANCE)
        self.assertLess(drift(self.rider, self.expected(Matrix())), TOLERANCE)


class TestPivot(CopyThatCase):
    """A lid hinged on its top back edge, opened a quarter turn about it.

    Recorded by its two poses only, which are the same whatever the pivot -
    so it is the way between them that tells a hinge from an origin.
    """

    def setUp(self):
        super().setUp()
        self.lid = cube("Lid", (0.0, 0.0, 1.0))
        self.hinge = Vector((0.0, 0.5, 1.5))
        self.home = self.lid.matrix_world.copy()

        def pose():
            self.lid.matrix_world = self.swing(90.0) @ self.home

        self.before, self.after = record_move([self.lid], pose)
        self.move = rig().rigmoves.moves[0]

    def swing(self, degrees):
        return (Matrix.Translation(self.hinge) @ Matrix.Rotation(math.radians(degrees), 4, "X")
                @ Matrix.Translation(-self.hinge))

    def swung(self, degrees):
        return [self.swing(degrees) @ self.home @ v.co for v in self.lid.data.vertices]

    def hinge_on_cursor(self):
        bpy.context.scene.cursor.location = self.hinge
        select(self.lid)
        return bpy.ops.rigmoves.set_pivot(index=0, kind="CURSOR")

    def test_pivot_picked_before_the_first_build(self):
        self.assertEqual(self.hinge_on_cursor(), {"FINISHED"})
        bpy.ops.rigmoves.build()
        drive(self.move, 0.5)
        self.assertLess(drift(self.lid, self.swung(45.0)), TOLERANCE)
        drive(self.move, 1.0)
        self.assertLess(drift(self.lid, self.after["Lid"]), TOLERANCE)

    def test_pivot_picked_after_a_build_keeps_the_poses(self):
        bpy.ops.rigmoves.build()
        drive(self.move, 0.5)
        # About its origin the lid's middle slides straight: not a hinge.
        self.assertGreater(drift(self.lid, self.swung(45.0)), 0.05)
        # A step at 60 degrees, recorded before the pivot moves.
        self.assertEqual(bpy.ops.rigmoves.add_step(index=0), {"FINISHED"})
        self.lid.matrix_world = self.swing(60.0) @ self.home
        bpy.context.view_layer.update()
        bpy.ops.rigmoves.record(index=0, which="STEP", step=0)
        bpy.ops.rigmoves.build()
        self.assertEqual(self.hinge_on_cursor(), {"FINISHED"})
        # Every recorded pose is where it was...
        drive(self.move, 0.0)
        self.assertLess(drift(self.lid, self.before["Lid"]), TOLERANCE)
        drive(self.move, 0.5)
        self.assertLess(drift(self.lid, self.swung(60.0)), TOLERANCE)
        drive(self.move, 1.0)
        self.assertLess(drift(self.lid, self.after["Lid"]), TOLERANCE)
        # ...and in between it swings about the hinge.
        drive(self.move, 0.25)
        self.assertLess(drift(self.lid, self.swung(30.0)), TOLERANCE)
        drive(self.move, 0.75)
        self.assertLess(drift(self.lid, self.swung(75.0)), TOLERANCE)

    def test_base_pivot(self):
        select(self.lid)
        self.assertEqual(bpy.ops.rigmoves.set_pivot(index=0, kind="BASE"), {"FINISHED"})
        self.assertLess((Vector(self.move.parts[0].pivot) - Vector((0.0, 0.0, -0.5))).length,
                        1e-6)

    def test_paths_before_a_build_are_left_off(self):
        self.assertEqual(bpy.ops.rigmoves.show_paths(index=0, show=True), {"FINISHED"})
        self.assertFalse(self.move.show_paths)
        self.assertIsNone(self.move.paths_object)

    def test_base_pivot_picked_with_the_lid_open(self):
        # Blender's own bounding box follows the rig; the base has to be the
        # part's own, as modelled, wherever the control stands.
        bpy.ops.rigmoves.build()
        drive(self.move, 1.0)
        select(self.lid)
        self.assertEqual(bpy.ops.rigmoves.set_pivot(index=0, kind="BASE"), {"FINISHED"})
        self.assertLess((Vector(self.move.parts[0].pivot) - Vector((0.0, 0.0, -0.5))).length,
                        1e-6)

    def test_rider_turns_about_its_leaders_pivot_carried_over(self):
        self.hinge_on_cursor()
        bpy.ops.rigmoves.build()
        other = cube("Other", (5.0, 0.0, 1.0))
        other.rotation_euler.z = math.radians(90.0)
        bpy.context.view_layer.update()
        seat = other.matrix_world.copy()
        select(other, self.lid)
        bpy.context.view_layer.objects.active = self.lid
        bpy.ops.rigmoves.ride_along(index=0, leader="Lid", rig_name=rig().name)
        drive(self.move, 0.5)
        carry = seat @ self.home.inverted()
        expected = [carry @ self.swing(45.0) @ self.home @ v.co for v in other.data.vertices]
        self.assertLess(drift(other, expected), TOLERANCE)


class TestMirror(CopyThatCase):
    """A wing that moves out and tips, and a second one that mirrors it."""

    def setUp(self):
        super().setUp()
        self.wing = cube("Wing", (1.5, 0.0, 0.0))
        self.wing.rotation_euler.z = math.radians(20.0)
        bpy.context.view_layer.update()
        self.home = self.wing.matrix_world.copy()

        def pose():
            self.wing.matrix_world = (self.home @ Matrix.Translation((1.0, 0.0, 0.0))
                                      @ Matrix.Rotation(math.radians(30.0), 4, "Y"))

        record_move([self.wing], pose)
        bpy.ops.rigmoves.build()
        self.move = rig().rigmoves.moves[0]

    def ride(self, other):
        select(other, self.wing)
        bpy.context.view_layer.objects.active = self.wing
        self.assertEqual(bpy.ops.rigmoves.ride_along(index=0, leader="Wing",
                                                     rig_name=rig().name), {"FINISHED"})
        return next(p for p in self.move.parts if p.leader)

    def test_mirrored_copy_mirrors_by_itself(self):
        # The other wing as Ctrl+M leaves it: the same wing, mirrored across X.
        other = cube("Other", (0.0, 0.0, 0.0))
        across = Matrix.Diagonal((-1.0, 1.0, 1.0, 1.0))
        other.matrix_world = across @ self.home
        bpy.context.view_layer.update()
        self.assertLess(other.matrix_world.determinant(), 0.0)
        self.ride(other)
        for share in (0.5, 1.0):
            drive(self.move, share)
            expected = [across @ p for p in world_points(self.wing)]
            self.assertLess(drift(other, expected), TOLERANCE)

    def test_mirror_setting_for_a_rider_facing_the_other_way(self):
        # The second of a pair of doors: turned round, not mirrored.
        other = cube("Other", (-1.5, 0.0, 0.0))
        other.rotation_euler.z = math.radians(160.0)
        bpy.context.view_layer.update()
        seat = other.matrix_world.copy()
        rider = self.ride(other)
        across = Matrix.Diagonal((-1.0, 1.0, 1.0, 1.0))
        travel = (Matrix.Translation((0.5, 0.0, 0.0))
                  @ Matrix.Rotation(math.radians(15.0), 4, "Y"))
        drive(self.move, 0.5)
        plain = [seat @ travel @ v.co for v in other.data.vertices]
        self.assertLess(drift(other, plain), TOLERANCE)
        position = list(self.move.parts).index(rider)
        self.assertEqual(bpy.ops.rigmoves.set_mirror(index=0, part=position, axis="X"),
                         {"FINISHED"})
        drive(self.move, 0.5)
        mirrored = [seat @ across @ travel @ across @ v.co for v in other.data.vertices]
        self.assertLess(drift(other, mirrored), TOLERANCE)
        bpy.ops.rigmoves.build()
        drive(self.move, 0.5)
        self.assertLess(drift(other, mirrored), TOLERANCE)

    def test_mirrored_copy_turns_about_the_mirrored_pivot(self):
        # The leader turns about its root edge, well off its own middle. A
        # Ctrl+M copy has to turn about the mirror image of that edge.
        bpy.context.scene.cursor.location = self.home @ Vector((-0.5, 0.0, 0.0))
        select(self.wing)
        self.assertEqual(bpy.ops.rigmoves.set_pivot(index=0, kind="CURSOR"), {"FINISHED"})
        other = cube("Other", (0.0, 0.0, 0.0))
        across = Matrix.Diagonal((-1.0, 1.0, 1.0, 1.0))
        other.matrix_world = across @ self.home
        bpy.context.view_layer.update()
        self.ride(other)
        for share in (0.5, 1.0):
            drive(self.move, share)
            expected = [across @ p for p in world_points(self.wing)]
            self.assertLess(drift(other, expected), TOLERANCE)

    def test_mirror_setting_turns_about_the_mirrored_pivot(self):
        # The door case with the leader turning about an edge: the rider has
        # to turn about the mirror image of that edge, on itself.
        bpy.context.scene.cursor.location = self.home @ Vector((-0.5, 0.0, 0.0))
        select(self.wing)
        bpy.ops.rigmoves.set_pivot(index=0, kind="CURSOR")
        other = cube("Other", (-1.5, 0.0, 0.0))
        other.rotation_euler.z = math.radians(160.0)
        bpy.context.view_layer.update()
        seat = other.matrix_world.copy()
        rider = self.ride(other)
        position = list(self.move.parts).index(rider)
        self.assertEqual(bpy.ops.rigmoves.set_mirror(index=0, part=position, axis="X"),
                         {"FINISHED"})
        across = Matrix.Diagonal((-1.0, 1.0, 1.0, 1.0))
        # Each rider corner plays what the leader's mirrored corner does.
        lead_corners = [v.co.copy() for v in self.wing.data.vertices]
        partner = [min(range(len(lead_corners)),
                       key=lambda j, v=v: (lead_corners[j] - across.to_3x3() @ v.co).length)
                   for v in other.data.vertices]
        for share in (0.5, 1.0):
            drive(self.move, share)
            lead = world_points(self.wing)
            expected = [seat @ across @ self.home.inverted() @ lead[j] for j in partner]
            self.assertLess(drift(other, expected), TOLERANCE)

    def test_mirrored_copy_of_a_hand_eased_leader(self):
        # Keys eased in the graph editor bend between keys; the mirrored copy
        # has to bend with them, not run straight.
        _action, _slot, bag = rigmoves.action_bits(self.move)
        for curve in bag.fcurves:
            for point in curve.keyframe_points:
                point.interpolation = "BEZIER"
                point.handle_left_type = point.handle_right_type = "AUTO_CLAMPED"
            curve.update()
        other = cube("Other", (0.0, 0.0, 0.0))
        across = Matrix.Diagonal((-1.0, 1.0, 1.0, 1.0))
        other.matrix_world = across @ self.home
        bpy.context.view_layer.update()
        self.ride(other)
        for share in (0.25, 0.75):
            drive(self.move, share)
            expected = [across @ p for p in world_points(self.wing)]
            self.assertLess(drift(other, expected), 2e-3)


class TestCurve(CopyThatCase):
    """A box slid from A to B, then sent round an obstacle by a curve."""

    def setUp(self):
        super().setUp()
        self.box = cube("Box", (0.0, 0.0, 0.5))

        def pose():
            self.box.location.x = 4.0

        self.before, self.after = record_move([self.box], pose)
        bpy.ops.rigmoves.build()
        self.move = rig().rigmoves.moves[0]
        select(self.box)
        self.assertEqual(bpy.ops.rigmoves.curve_path(index=0), {"FINISHED"})
        self.curve = self.move.parts[0].path_curve

    def bend(self, offset):
        """Drag the middle point, handles and all, as grabbing it would."""
        spline = self.curve.data.splines[0]
        points, left, right = rigmoves.points_of(spline)
        for row in (points, left, right):
            row[1] = row[1] + offset
        rigmoves.set_points(spline, points, left, right)

    def test_curve_starts_on_the_path(self):
        points = self.curve.data.splines[0].bezier_points
        self.assertEqual(len(points), 3)
        self.assertLess((points[0].co - Vector((0.0, 0.0, 0.5))).length, TOLERANCE)
        self.assertLess((points[-1].co - Vector((4.0, 0.0, 0.5))).length, TOLERANCE)
        drive(self.move, 0.5)
        self.assertLess((centre(self.box) - Vector((2.0, 0.0, 0.5))).length, TOLERANCE)

    def test_part_follows_the_bent_curve(self):
        self.bend(Vector((0.0, 3.0, 0.0)))
        bpy.ops.rigmoves.build()
        drive(self.move, 0.5)
        self.assertLess((centre(self.box) - Vector((2.0, 3.0, 0.5))).length, 1e-3)
        drive(self.move, 0.0)
        self.assertLess(drift(self.box, self.before["Box"]), TOLERANCE)
        drive(self.move, 1.0)
        self.assertLess(drift(self.box, self.after["Box"]), TOLERANCE)

    def test_ends_are_pinned_to_before_and_after(self):
        points = self.curve.data.splines[0].bezier_points
        points[0].co = Vector((-5.0, -5.0, -5.0))
        points[-1].co = Vector((9.0, 9.0, 9.0))
        bpy.ops.rigmoves.build()
        self.assertLess((points[0].co - Vector((0.0, 0.0, 0.5))).length, TOLERANCE)
        self.assertLess((points[-1].co - Vector((4.0, 0.0, 0.5))).length, TOLERANCE)
        drive(self.move, 1.0)
        self.assertLess(drift(self.box, self.after["Box"]), TOLERANCE)

    def test_rider_follows_the_curve_from_its_place(self):
        self.bend(Vector((0.0, 3.0, 0.0)))
        other = cube("Other", (0.0, 10.0, 0.5))
        other.rotation_euler.z = math.radians(90.0)
        bpy.context.view_layer.update()
        select(other, self.box)
        bpy.context.view_layer.objects.active = self.box
        bpy.ops.rigmoves.ride_along(index=0, leader="Box", rig_name=rig().name)
        drive(self.move, 0.5)
        # (2, 3) on the leader's way, turned a quarter round onto the rider.
        self.assertLess((centre(other) - Vector((-3.0, 12.0, 0.5))).length, 1e-3)

    def test_pivot_change_takes_the_curve_along(self):
        # The box never turns, so a new pivot must not change where it goes.
        self.bend(Vector((0.0, 3.0, 0.0)))
        bpy.ops.rigmoves.build()
        select(self.box)
        self.assertEqual(bpy.ops.rigmoves.set_pivot(index=0, kind="BASE"), {"FINISHED"})
        for share, where in ((0.5, (2.0, 3.0, 0.5)), (1.0, (4.0, 0.0, 0.5))):
            drive(self.move, share)
            self.assertLess((centre(self.box) - Vector(where)).length, 1e-3)

    def test_second_curve_is_pointed_to_the_first(self):
        select(self.box)
        self.assertEqual(bpy.ops.rigmoves.curve_path(index=0), {"CANCELLED"})
        self.assertIn("already", rig().rigmoves.report)

    def test_panel_keeps_the_rig_while_the_curve_is_edited(self):
        bpy.context.scene.rigmoves_rig = None
        self.assertEqual(bpy.ops.rigmoves.edit_curve(index=0, part=0), {"FINISHED"})
        self.assertEqual(bpy.context.object, self.curve)
        bpy.ops.object.mode_set(mode="OBJECT")
        bpy.context.scene.rigmoves_rig = None
        self.assertEqual(rigmoves.rig_of(bpy.context), self.move.id_data)

    def test_straighten_takes_the_curve_away(self):
        self.bend(Vector((0.0, 3.0, 0.0)))
        bpy.ops.rigmoves.build()
        name = self.curve.name
        self.assertEqual(bpy.ops.rigmoves.drop_curve(index=0, part=0), {"FINISHED"})
        self.assertIsNone(bpy.data.objects.get(name))
        drive(self.move, 0.5)
        self.assertLess((centre(self.box) - Vector((2.0, 0.0, 0.5))).length, TOLERANCE)


class TestFollowers(CopyThatCase):
    """A finger: three segments end to end, each hinged on its knuckle and
    hanging from the one before. Closed, every joint bends 30 degrees."""

    KNUCKLES = (Vector((0.0, 0.0, 0.0)), Vector((1.0, 0.0, 0.0)), Vector((2.0, 0.0, 0.0)))

    def setUp(self):
        super().setUp()
        self.segments = []
        for number in range(3):
            segment = cube("Seg{:d}".format(number + 1), (number + 0.5, 0.0, 0.0))
            segment.scale = (1.0, 0.3, 0.3)
            self.segments.append(segment)
        bpy.context.view_layer.update()
        self.homes = [s.matrix_world.copy() for s in self.segments]
        select(*self.segments)
        self.assertEqual(bpy.ops.rigmoves.new_move(), {"FINISHED"})
        self.move = rig().rigmoves.moves[0]
        for segment, knuckle in zip(self.segments, self.KNUCKLES):
            bpy.context.scene.cursor.location = knuckle
            select(segment)
            bpy.ops.rigmoves.set_pivot(index=0, kind="CURSOR")

    def bent(self, degrees):
        """Each segment's place with every joint bent this far, carried down
        the finger."""
        return self.bent_by((degrees,) * len(self.KNUCKLES))

    def bent_by(self, angles):
        """Each segment's place with each joint bent by its own angle."""
        out, carry = [], Matrix.Identity(4)
        for knuckle, home, degrees in zip(self.KNUCKLES, self.homes, angles):
            carry = (carry @ Matrix.Translation(knuckle)
                     @ Matrix.Rotation(math.radians(degrees), 4, "Y")
                     @ Matrix.Translation(-knuckle))
            out.append(carry @ home)
        return out

    def check_places(self, places):
        for segment, place in zip(self.segments, places):
            expected = [place @ v.co for v in segment.data.vertices]
            self.assertLess(drift(segment, expected), TOLERANCE, segment.name)

    def chain(self):
        self.move.parts["Seg2"].follows = "Seg1"
        self.move.parts["Seg3"].follows = "Seg2"

    def close(self, which=(0, 1, 2)):
        for number in which:
            self.segments[number].matrix_world = self.bent(30.0)[number]
        bpy.context.view_layer.update()
        self.assertEqual(bpy.ops.rigmoves.record(index=0, which="AFTER"), {"FINISHED"})

    def check_curl(self, share, degrees):
        drive(self.move, share)
        for segment, place in zip(self.segments, self.bent(degrees)):
            expected = [place @ v.co for v in segment.data.vertices]
            self.assertLess(drift(segment, expected), TOLERANCE, segment.name)

    def test_finger_curls_joint_by_joint(self):
        self.chain()
        self.close()
        bpy.ops.rigmoves.build()
        self.check_curl(0.0, 0.0)
        self.check_curl(0.5, 15.0)
        self.check_curl(1.0, 30.0)
        # Bone by bone, as asked: each hangs from the one before.
        bones = rig().data.bones
        self.assertEqual(bones[self.move.parts["Seg2"].bone_name].parent.name,
                         self.move.parts["Seg1"].bone_name)
        self.assertEqual(bones[self.move.parts["Seg3"].bone_name].parent.name,
                         self.move.parts["Seg2"].bone_name)

    def test_follows_set_after_a_build(self):
        self.close()
        bpy.ops.rigmoves.build()
        # Each on its own, the middle of the way pulls the joints apart.
        drive(self.move, 0.5)
        tip = [self.bent(15.0)[2] @ v.co for v in self.segments[2].data.vertices]
        self.assertGreater(drift(self.segments[2], tip), 0.01)
        self.chain()
        self.assertTrue(rigmoves.parent_pending(rig(), rig().rigmoves, self.move))
        bpy.ops.rigmoves.build()
        self.assertFalse(rigmoves.parent_pending(rig(), rig().rigmoves, self.move))
        self.check_curl(0.0, 0.0)
        self.check_curl(0.5, 15.0)
        self.check_curl(1.0, 30.0)
        # And let go again, it keeps its poses too.
        self.move.parts["Seg3"].follows = ""
        bpy.ops.rigmoves.build()
        self.check_curl(1.0, 30.0)

    def test_a_follower_left_alone_rides_along(self):
        # Only the first segment is bent: the rest go with it, unbent.
        self.chain()
        self.close(which=(0,))
        bpy.ops.rigmoves.build()
        drive(self.move, 1.0)
        carry = self.bent(30.0)[0] @ self.homes[0].inverted()
        for segment, home in zip(self.segments[1:], self.homes[1:]):
            expected = [carry @ home @ v.co for v in segment.data.vertices]
            self.assertLess(drift(segment, expected), TOLERANCE, segment.name)

    def test_dragging_a_follower_from_where_it_is_seen(self):
        self.chain()
        self.close(which=(0,))
        bpy.ops.rigmoves.build()
        # On After, the second segment is seen carried by the first. It is
        # dragged from there to bend its own joint, as a user would.
        bpy.ops.rigmoves.show(index=0, which="AFTER")
        bpy.context.view_layer.update()
        posed = {pb.name: pb.matrix_basis.copy() for pb in rig().pose.bones}
        world = rig().matrix_world
        carried = (world @ rigmoves.deformation(
            rig(), None, self.move.parts["Seg2"].bone_name, 0.0, posed) @ world.inverted())
        wanted = self.bent(30.0)
        self.segments[1].matrix_world = carried.inverted() @ wanted[1]
        bpy.context.view_layer.update()
        self.assertEqual(bpy.ops.rigmoves.record(index=0, which="AFTER"), {"FINISHED"})
        bpy.ops.rigmoves.build()
        drive(self.move, 1.0)
        expected = [wanted[1] @ v.co for v in self.segments[1].data.vertices]
        self.assertLess(drift(self.segments[1], expected), TOLERANCE)
        # The third, never bent itself, rides on the second.
        carry = wanted[1] @ self.homes[1].inverted()
        expected = [carry @ self.homes[2] @ v.co for v in self.segments[2].data.vertices]
        self.assertLess(drift(self.segments[2], expected), TOLERANCE)

    def test_a_loose_follower_hangs_from_the_part_it_follows(self):
        # Before the first Build: dragging the first segment carries the
        # others along on screen, which is what gets recorded.
        self.chain()
        self.assertEqual(self.segments[1].parent, self.segments[0])
        self.segments[0].matrix_world = self.bent(30.0)[0]
        bpy.context.view_layer.update()
        carry = self.bent(30.0)[0] @ self.homes[0].inverted()
        self.assertLess(drift(self.segments[2], [carry @ self.homes[2] @ v.co
                                                 for v in self.segments[2].data.vertices]),
                        TOLERANCE)
        # Let go of, it stays where it is.
        self.move.parts["Seg3"].follows = ""
        self.assertIsNone(self.segments[2].parent)
        self.assertLess(drift(self.segments[2], [carry @ self.homes[2] @ v.co
                                                 for v in self.segments[2].data.vertices]),
                        TOLERANCE)

    def built_curl(self):
        self.chain()
        self.close()
        bpy.ops.rigmoves.build()

    def test_a_chain_turned_round(self):
        self.built_curl()
        parts = self.move.parts
        for name in ("Seg2", "Seg3"):
            parts[name].follows = ""
        parts["Seg2"].follows = "Seg3"
        parts["Seg1"].follows = "Seg2"
        bpy.ops.rigmoves.build()
        self.assertFalse(rigmoves.parent_pending(rig(), rig().rigmoves, self.move))
        bones = rig().data.bones
        self.assertEqual(bones[parts["Seg1"].bone_name].parent.name, parts["Seg2"].bone_name)
        self.check_curl(1.0, 30.0)
        self.check_curl(0.0, 0.0)
        bpy.ops.rigmoves.build()
        self.check_curl(1.0, 30.0)

    def test_dragged_follower_on_a_step_lands_where_seen(self):
        self.built_curl()
        bpy.ops.rigmoves.show(index=0, which="AFTER")
        bpy.ops.rigmoves.add_step(index=0)
        bpy.context.view_layer.update()
        # Seen with its own joint bent 60 instead of 30.
        wanted = (self.bent(30.0)[0] @ self.homes[0].inverted()
                  @ Matrix.Translation(self.KNUCKLES[1])
                  @ Matrix.Rotation(math.radians(60.0), 4, "Y")
                  @ Matrix.Translation(-self.KNUCKLES[1]) @ self.homes[1])
        bone = self.move.parts["Seg2"].bone_name
        pose_bone = rig().pose.bones[bone]
        carried = (rig().matrix_world @ pose_bone.matrix @ pose_bone.bone.matrix_local.inverted()
                   @ rig().matrix_world.inverted())
        self.segments[1].matrix_world = carried.inverted() @ wanted
        bpy.context.view_layer.update()
        expected = [wanted @ v.co for v in self.segments[1].data.vertices]
        self.assertLess(drift(self.segments[1], expected), TOLERANCE)
        self.assertEqual(bpy.ops.rigmoves.record(index=0, which="STEP", step=0), {"FINISHED"})
        bpy.context.view_layer.update()
        self.assertLess(drift(self.segments[1], expected), TOLERANCE)
        bpy.ops.rigmoves.build()
        drive(self.move, 0.5)
        self.assertLess(drift(self.segments[1], expected), TOLERANCE)

    def step_on(self, number, degrees):
        """Record a step with one segment dragged to bend its joint further."""
        bpy.ops.rigmoves.add_step(index=0)
        bpy.ops.rigmoves.pause(off=True)
        bpy.context.view_layer.update()
        name = self.move.parts["Seg{:d}".format(number + 1)].bone_name
        pose_bone = rig().pose.bones[name]
        carried = (rig().matrix_world @ pose_bone.matrix @ pose_bone.bone.matrix_local.inverted()
                   @ rig().matrix_world.inverted())
        knuckle = carried @ self.KNUCKLES[number]
        turn = (Matrix.Translation(knuckle) @ Matrix.Rotation(math.radians(degrees), 4, "Y")
                @ Matrix.Translation(-knuckle))
        self.segments[number].matrix_world = carried.inverted() @ turn @ carried @ self.homes[number]
        bpy.context.view_layer.update()
        self.assertEqual(bpy.ops.rigmoves.record(index=0, which="STEP", step=0), {"FINISHED"})
        bpy.ops.rigmoves.build()
        drive(self.move, 0.5)
        return [world_points(segment) for segment in self.segments]

    def test_a_new_pivot_keeps_a_followers_step(self):
        self.built_curl()
        seen = self.step_on(1, 40.0)
        select(self.segments[0])
        self.assertEqual(bpy.ops.rigmoves.set_pivot(index=0, kind="ORIGIN"), {"FINISHED"})
        drive(self.move, 0.5)
        for segment, points in zip(self.segments, seen):
            self.assertLess(drift(segment, points), TOLERANCE, segment.name)

    def test_letting_go_keeps_a_step_below(self):
        self.built_curl()
        seen = self.step_on(2, 40.0)
        self.move.parts["Seg2"].follows = ""
        bpy.ops.rigmoves.build()
        self.assertIn("let go", rig().rigmoves.report)
        drive(self.move, 0.5)
        for segment, points in zip(self.segments, seen):
            self.assertLess(drift(segment, points), TOLERANCE, segment.name)

    def test_followers_and_curves_do_not_mix(self):
        self.built_curl()
        select(self.segments[1])
        self.assertEqual(bpy.ops.rigmoves.curve_path(index=0), {"CANCELLED"})
        self.assertIn("carried", rig().rigmoves.report)
        select(self.segments[0])
        self.assertEqual(bpy.ops.rigmoves.curve_path(index=0), {"FINISHED"})
        self.move.parts["Seg1"].follows = "Seg3"
        self.assertEqual(self.move.parts["Seg1"].follows, "")

    def test_a_slip_keeps_the_choice_it_had(self):
        self.chain()
        self.move.parts["Seg3"].follows = "Seg3"
        self.assertEqual(self.move.parts["Seg3"].follows, "Seg2")
        self.assertEqual(self.segments[2].parent, self.segments[1])

    def test_remove_before_a_build_lets_go_of_the_objects(self):
        self.chain()
        bpy.ops.rigmoves.remove(index=0)
        for segment in self.segments[1:]:
            self.assertIsNone(segment.parent)
            self.assertIsNone(segment.get(rigmoves.FOLLOW_MARK))

    def test_paths_with_delays_go_where_the_parts_go(self):
        self.built_curl()
        self.move.parts["Seg2"].start = 0.25
        self.move.parts["Seg3"].start = 0.5
        bpy.ops.rigmoves.show_paths(index=0, show=True)
        line = [Vector(p.co[:3]) for p in self.move.paths_object.data.splines[2].points]
        for number in range(11):
            drive(self.move, number / 10.0)
            here = centre(self.segments[2])
            self.assertLess(min((here - p).length for p in line), 0.02)

    def test_built_leader_dragged_carries_its_followers(self):
        # The way it was used: Follows set, Build first, then pose the
        # leader. Dragging it has to bring the rest along, on screen.
        self.chain()
        bpy.ops.rigmoves.build()
        self.assertEqual(self.segments[1].parent, self.segments[0])
        self.assertEqual(self.segments[2].parent, self.segments[1])
        bent = self.bent(30.0)[0]
        self.segments[0].matrix_world = bent
        bpy.context.view_layer.update()
        carry = bent @ self.homes[0].inverted()
        for segment, home in zip(self.segments[1:], self.homes[1:]):
            expected = [carry @ home @ v.co for v in segment.data.vertices]
            self.assertLess(drift(segment, expected), TOLERANCE, segment.name)
        self.assertEqual(bpy.ops.rigmoves.record(index=0, which="AFTER"), {"FINISHED"})
        bpy.ops.rigmoves.build()
        drive(self.move, 1.0)
        for segment, home in zip(self.segments, self.homes):
            expected = [carry @ home @ v.co for v in segment.data.vertices]
            self.assertLess(drift(segment, expected), TOLERANCE, segment.name)
        drive(self.move, 0.5)
        half = (Matrix.Translation(self.KNUCKLES[0]) @ Matrix.Rotation(math.radians(15.0), 4, "Y")
                @ Matrix.Translation(-self.KNUCKLES[0]))
        for segment, home in zip(self.segments, self.homes):
            expected = [half @ home @ v.co for v in segment.data.vertices]
            self.assertLess(drift(segment, expected), TOLERANCE, segment.name)

    def turn_the_base(self, degrees):
        """Turn the first segment's object further about its knuckle, from
        wherever its bone is showing it - as dragging it in the viewport would."""
        knuckle = self.KNUCKLES[0]
        turn = (Matrix.Translation(knuckle) @ Matrix.Rotation(math.radians(degrees), 4, "Y")
                @ Matrix.Translation(-knuckle))
        self.segments[0].matrix_world = turn @ self.homes[0]
        bpy.context.view_layer.update()

    def test_turning_the_base_of_a_shown_finger_keeps_its_joints(self):
        # Shown closed by the eye, as the panel says to, then the base turned
        # further: the rest of the finger is carried whole, joints shut.
        self.built_curl()
        bpy.ops.rigmoves.show(index=0, which="AFTER")
        self.turn_the_base(20.0)
        self.assertEqual(bpy.ops.rigmoves.record(index=0, which="AFTER"), {"FINISHED"})
        bpy.context.view_layer.update()
        self.check_places(self.bent_by((50.0, 30.0, 30.0)))
        self.assertEqual(rigmoves.unrecorded(rig().rigmoves), [])
        bpy.ops.rigmoves.build()
        drive(self.move, 1.0)
        self.check_places(self.bent_by((50.0, 30.0, 30.0)))
        drive(self.move, 0.0)
        self.check_places(self.homes)

    def test_turning_the_base_with_the_slider_up_keeps_its_joints(self):
        self.built_curl()
        drive(self.move, 1.0)
        self.turn_the_base(20.0)
        self.assertEqual(bpy.ops.rigmoves.record(index=0, which="AFTER"), {"FINISHED"})
        bpy.ops.rigmoves.build()
        drive(self.move, 1.0)
        self.check_places(self.bent_by((50.0, 30.0, 30.0)))

    def test_followers_listed_first_go_back_after_their_leader(self):
        # Modelled tip first, so the tip comes first in the list, and Follows
        # set on a built move: the objects hang at once, the bones at Build.
        for segment, home in zip(self.segments, self.homes):
            segment.matrix_world = home
        bpy.ops.rigmoves.remove(index=0)
        select(*reversed(self.segments))
        self.assertEqual(bpy.ops.rigmoves.new_move(), {"FINISHED"})
        self.move = rig().rigmoves.moves[0]
        self.move.parts.move(2, 0)
        names = [p.name for p in self.move.parts]
        self.assertLess(names.index("Seg3"), names.index("Seg1"))
        bpy.ops.rigmoves.build()
        self.chain()
        self.assertTrue(rigmoves.parent_pending(rig(), rig().rigmoves, self.move))
        drive(self.move, 0.0)
        self.turn_the_base(30.0)
        carry = self.bent(30.0)[0] @ self.homes[0].inverted()
        seen = [carry @ home for home in self.homes]
        self.assertEqual(bpy.ops.rigmoves.record(index=0, which="AFTER"), {"FINISHED"})
        bpy.context.view_layer.update()
        self.assertEqual(rigmoves.unrecorded(rig().rigmoves), [])
        self.check_places(seen)
        self.assertEqual(bpy.ops.rigmoves.record(index=0, which="AFTER"), {"FINISHED"})
        bpy.ops.rigmoves.build()
        drive(self.move, 1.0)
        self.check_places(seen)
        drive(self.move, 0.0)
        self.check_places(self.homes)

    def test_a_follower_not_hung_asks_for_a_build(self):
        # As a file built before followers' objects were hung is opened.
        self.built_curl()
        self.assertFalse(rigmoves.parent_pending(rig(), rig().rigmoves, self.move))
        for segment in self.segments[1:]:
            rigmoves.keep_world(segment, rig())
            del segment[rigmoves.FOLLOW_MARK]
        self.assertTrue(rigmoves.parent_pending(rig(), rig().rigmoves, self.move))
        bpy.ops.rigmoves.build()
        self.assertFalse(rigmoves.parent_pending(rig(), rig().rigmoves, self.move))
        self.assertEqual(self.segments[1].parent, self.segments[0])
        self.assertEqual(self.segments[2].parent, self.segments[1])

    def test_following_set_and_cleared_on_a_built_move(self):
        bpy.ops.rigmoves.build()
        holder = self.segments[1].parent
        self.move.parts["Seg2"].follows = "Seg1"
        self.assertEqual(self.segments[1].parent, self.segments[0])
        self.move.parts["Seg2"].follows = ""
        self.assertEqual(self.segments[1].parent, holder)
        self.assertIsNone(self.segments[1].get(rigmoves.FOLLOW_MARK))

    def test_remove_lets_go_of_built_followers(self):
        self.chain()
        self.close()
        bpy.ops.rigmoves.build()
        drive(self.move, 0.0)
        bpy.ops.rigmoves.remove(index=0)
        for segment, home in zip(self.segments, self.homes):
            self.assertIsNone(segment.parent)
            self.assertIsNone(segment.get(rigmoves.FOLLOW_MARK))
            self.assertLess(drift(segment, [home @ v.co for v in segment.data.vertices]),
                            TOLERANCE)

    def test_impossible_choices_are_turned_down(self):
        self.chain()
        parts = self.move.parts
        parts["Seg1"].follows = "Seg3"          # a loop
        self.assertEqual(parts["Seg1"].follows, "")
        parts["Seg1"].follows = "Seg1"          # itself
        self.assertEqual(parts["Seg1"].follows, "")
        parts["Seg1"].follows = "Nothing"
        self.assertEqual(parts["Seg1"].follows, "")
        self.assertEqual(parts["Seg3"].follows, "Seg2")

    def test_a_follower_does_not_lead_riders(self):
        self.chain()
        self.close()
        bpy.ops.rigmoves.build()
        other = cube("Other", (0.0, 5.0, 0.0))
        select(other, self.segments[1])
        bpy.context.view_layer.objects.active = self.segments[1]
        self.assertEqual([p.name for _i, _m, p in rigmoves.leaders(bpy.context, rig())], [])
        self.assertEqual(bpy.ops.rigmoves.ride_along(index=0, leader="Seg2",
                                                     rig_name=rig().name), {"CANCELLED"})

    def test_paths_go_down_the_finger(self):
        self.chain()
        self.close()
        bpy.ops.rigmoves.build()
        bpy.ops.rigmoves.show_paths(index=0, show=True)
        tip = self.move.paths_object.data.splines[2].points
        middle = self.bent(30.0)[2] @ Vector((0.0, 0.0, 0.0))
        self.assertLess((Vector(tip[-1].co[:3]) - middle).length, TOLERANCE)


class TestModelledHierarchy(CopyThatCase):
    """A finger already parented joint by joint in the file."""

    def test_parents_become_follows_and_come_back(self):
        hand = cube("Hand", (0.0, 0.0, -3.0))
        one = cube("One", (0.5, 0.0, 0.0))
        two = cube("Two", (1.5, 0.0, 0.0))
        rigmoves.keep_world(one, hand)
        rigmoves.keep_world(two, one)
        select(one, two)
        bpy.ops.rigmoves.new_move()
        move = rig().rigmoves.moves[0]
        self.assertEqual(move.parts["Two"].follows, "One")
        self.assertEqual(move.parts["One"].follows, "")
        one.location.z += 1.0
        bpy.context.view_layer.update()
        bpy.ops.rigmoves.record(index=0, which="AFTER")
        bpy.ops.rigmoves.build()
        drive(move, 1.0)
        self.assertAlmostEqual(centre(two).z, 1.0, places=4)
        # Taken out of the rig, each hangs from its own parent again.
        drive(move, 0.0)
        bpy.ops.rigmoves.remove(index=0)
        self.assertEqual(one.parent, hand)
        self.assertEqual(two.parent, one)
        self.assertAlmostEqual(two.matrix_world.translation.x, 1.5, places=5)


class TestFollowersJoining(CopyThatCase):
    """A tip added to a finger that is already built."""

    def test_loose_follower_of_a_built_part_is_recorded_where_seen(self):
        base = cube("Base", (0.5, 0.0, 0.0))
        tip = cube("Tip", (1.5, 0.0, 0.0))
        select(base)
        bpy.ops.rigmoves.new_move()
        base.location.z += 0.5
        bpy.context.view_layer.update()
        bpy.ops.rigmoves.record(index=0, which="AFTER")
        bpy.ops.rigmoves.build()
        move = rig().rigmoves.moves[0]
        select(tip, base)
        bpy.ops.rigmoves.add_to_move(index=0, rig_name=rig().name)
        move.parts["Tip"].follows = "Base"
        self.assertEqual(tip.parent, base)
        drive(move, 0.0)
        # Dragging the base object carries the tip along on screen.
        base.location.z += 2.0
        bpy.context.view_layer.update()
        seen = world_points(tip)
        bpy.ops.rigmoves.record(index=0, which="AFTER")
        bpy.ops.rigmoves.build()
        drive(move, 1.0)
        self.assertLess(drift(tip, seen), TOLERANCE)

    def test_add_to_group_takes_up_a_modelled_hierarchy(self):
        one = cube("One", (0.5, 0.0, 0.0))
        two = cube("Two", (1.5, 0.0, 0.0))
        rigmoves.keep_world(two, one)
        select(one)
        bpy.ops.rigmoves.new_move()
        select(two, one)
        bpy.ops.rigmoves.add_to_move(index=0, rig_name=rig().name)
        self.assertEqual(rig().rigmoves.moves[0].parts["Two"].follows, "One")

    def test_following_keeps_the_objects_own_parent(self):
        hand = cube("Hand", (0.0, 0.0, -3.0))
        one = cube("One", (0.5, 0.0, 0.0))
        two = cube("Two", (1.5, 0.0, 0.0))
        rigmoves.keep_world(two, hand)
        select(one, two)
        bpy.ops.rigmoves.new_move()
        move = rig().rigmoves.moves[0]
        move.parts["Two"].follows = "One"
        self.assertEqual(two.parent, one)
        move.parts["Two"].follows = ""
        self.assertEqual(two.parent, hand)
        move.parts["Two"].follows = "One"
        one.location.z += 1.0
        bpy.context.view_layer.update()
        bpy.ops.rigmoves.record(index=0, which="AFTER")
        bpy.ops.rigmoves.build()
        drive(move, 0.0)
        bpy.ops.rigmoves.remove(index=0)
        self.assertEqual(two.parent, hand)


class TestFollowersAdded(CopyThatCase):
    """A finger put together around a part that is already built."""

    KNUCKLES = TestFollowers.KNUCKLES

    def setUp(self):
        super().setUp()
        self.segments = []
        for number in range(3):
            segment = cube("Seg{:d}".format(number + 1), (number + 0.5, 0.0, 0.0))
            segment.scale = (1.0, 0.3, 0.3)
            self.segments.append(segment)
        bpy.context.view_layer.update()
        self.homes = [s.matrix_world.copy() for s in self.segments]

    def turn(self, number, degrees):
        knuckle = self.KNUCKLES[number]
        return (Matrix.Translation(knuckle) @ Matrix.Rotation(math.radians(degrees), 4, "Y")
                @ Matrix.Translation(-knuckle))

    def pivots(self, numbers):
        for number in numbers:
            bpy.context.scene.cursor.location = self.KNUCKLES[number]
            select(self.segments[number])
            bpy.ops.rigmoves.set_pivot(index=0, kind="CURSOR")

    def check(self, places, numbers=(0, 1, 2)):
        for number in numbers:
            segment = self.segments[number]
            expected = [places[number] @ v.co for v in segment.data.vertices]
            self.assertLess(drift(segment, expected), TOLERANCE, segment.name)

    def base_built(self, steps=False):
        """The first segment alone, turned 30 at After - 10 at a step in
        between, if asked - and built."""
        select(self.segments[0])
        bpy.ops.rigmoves.new_move()
        self.move = rig().rigmoves.moves[0]
        self.pivots((0,))
        self.segments[0].matrix_world = self.turn(0, 30.0) @ self.homes[0]
        bpy.context.view_layer.update()
        bpy.ops.rigmoves.record(index=0, which="AFTER")
        bpy.ops.rigmoves.build()
        if steps:
            bpy.ops.rigmoves.add_step(index=0)
            bpy.ops.rigmoves.pause(off=True)
            self.segments[0].matrix_world = self.turn(0, 10.0) @ self.homes[0]
            bpy.context.view_layer.update()
            self.assertEqual(bpy.ops.rigmoves.record(index=0, which="STEP", step=0),
                             {"FINISHED"})
            bpy.ops.rigmoves.build()

    def join_the_rest(self):
        select(self.segments[1], self.segments[2])
        self.assertEqual(bpy.ops.rigmoves.add_to_move(index=0, rig_name=rig().name),
                         {"FINISHED"})
        self.pivots((1, 2))
        self.move.parts["Seg2"].follows = "Seg1"
        self.move.parts["Seg3"].follows = "Seg2"

    def test_new_followers_ride_along_after_a_build(self):
        self.base_built()
        self.join_the_rest()
        self.assertTrue(rigmoves.recorded(self.move, "AFTER"))
        bpy.ops.rigmoves.build()
        for share, degrees in ((0.0, 0.0), (0.5, 15.0), (1.0, 30.0)):
            drive(self.move, share)
            self.check([self.turn(0, degrees) @ home for home in self.homes])

    def test_new_followers_ride_along_through_a_step(self):
        self.base_built(steps=True)
        self.join_the_rest()
        bpy.ops.rigmoves.build()
        drive(self.move, 0.5)
        self.check([self.turn(0, 10.0) @ home for home in self.homes])
        drive(self.move, 1.0)
        self.check([self.turn(0, 30.0) @ home for home in self.homes])

    def test_new_followers_are_shown_carried_on_after(self):
        self.base_built()
        self.join_the_rest()
        bpy.ops.rigmoves.show(index=0, which="AFTER")
        carried = [self.turn(0, 30.0) @ home for home in self.homes]
        self.check(carried)
        # The tip bent on its own from there, the middle left where carried.
        wanted = carried[:2] + [self.turn(0, 30.0) @ self.turn(2, 40.0) @ self.homes[2]]
        # Bound already, by the Build that Set Pivot runs, so its bone carries
        # it: it is dragged from where it is seen, as a user would.
        shown = Matrix.Identity(4)
        pose_bone = rig().pose.bones.get(self.move.parts["Seg3"].bone_name or "-")
        if pose_bone is not None:
            world = rig().matrix_world
            shown = (world @ pose_bone.matrix @ pose_bone.bone.matrix_local.inverted()
                     @ world.inverted())
        self.segments[2].matrix_world = shown.inverted() @ wanted[2]
        bpy.context.view_layer.update()
        self.assertEqual(bpy.ops.rigmoves.record(index=0, which="AFTER"), {"FINISHED"})
        bpy.ops.rigmoves.build()
        drive(self.move, 1.0)
        self.check(wanted)
        drive(self.move, 0.0)
        self.check(self.homes)

    def test_a_base_added_under_a_built_finger(self):
        # The second and third built first, then a first segment put under
        # them: turned, it carries both, and the first Build keeps that.
        select(self.segments[1], self.segments[2])
        bpy.ops.rigmoves.new_move()
        self.move = rig().rigmoves.moves[0]
        self.pivots((1, 2))
        self.move.parts["Seg3"].follows = "Seg2"
        bpy.ops.rigmoves.build()
        select(self.segments[0])
        bpy.ops.rigmoves.add_to_move(index=0, rig_name=rig().name)
        self.pivots((0,))
        self.move.parts["Seg2"].follows = "Seg1"
        self.assertEqual(self.segments[1].parent, self.segments[0])
        drive(self.move, 0.0)
        self.segments[0].matrix_world = self.turn(0, 30.0) @ self.homes[0]
        bpy.context.view_layer.update()
        seen = [self.turn(0, 30.0) @ home for home in self.homes]
        self.check(seen)
        self.assertEqual(bpy.ops.rigmoves.record(index=0, which="AFTER"), {"FINISHED"})
        bpy.ops.rigmoves.build()
        self.assertEqual(rigmoves.unrecorded(rig().rigmoves), [])
        drive(self.move, 0.0)
        self.check(self.homes)
        drive(self.move, 1.0)
        self.check(seen)
        self.assertEqual(self.segments[1].parent, self.segments[0])

    def test_build_before_after_is_recorded_says_so(self):
        select(*self.segments)
        bpy.ops.rigmoves.new_move()
        self.move = rig().rigmoves.moves[0]
        self.move.parts["Seg2"].follows = "Seg1"
        bpy.ops.rigmoves.build()
        self.assertFalse(rigmoves.recorded(self.move, "AFTER"))
        self.assertIn("After not recorded", rig().rigmoves.report)
        self.segments[0].location.z += 1.0
        bpy.context.view_layer.update()
        bpy.ops.rigmoves.record(index=0, which="AFTER")
        self.assertTrue(rigmoves.recorded(self.move, "AFTER"))
        bpy.ops.rigmoves.build()
        self.assertNotIn("After not recorded", rig().rigmoves.report)


class TestSpread(CopyThatCase):
    """Leads and Delays filled in from where the parts stand."""

    def lifted(self, objects):
        """A move over these objects, each raised a metre and recorded."""
        select(*objects)
        self.assertEqual(bpy.ops.rigmoves.new_move(), {"FINISHED"})
        for obj in objects:
            obj.location.z += 1.0
        bpy.context.view_layer.update()
        self.assertEqual(bpy.ops.rigmoves.record(index=0, which="AFTER"), {"FINISHED"})
        self.move = rig().rigmoves.moves[0]
        return self.move

    def ride(self, leader, where, name):
        obj = cube(name, where)
        select(leader, obj)
        self.assertEqual(bpy.ops.rigmoves.ride_along(index=0, leader=leader.name,
                                                     rig_name=rig().name), {"FINISHED"})
        return obj

    def leads(self, leader=None):
        return [p.lead for p in self.move.parts
                if p.leader and (leader is None or p.leader == leader)]

    def delays(self):
        return [round(p.start, 4) for p in self.move.parts if not p.leader]

    def spread(self, what, **kwargs):
        return bpy.ops.rigmoves.spread(index=0, what=what, **kwargs)

    def ring_of_riders(self, count=8, start=0.0, leader_on_ring=False):
        """A leader and a ring of riders round it, on the tilted plane."""
        centre = (2.0, 1.0, 3.0)
        places = ring_places(centre, count + (1 if leader_on_ring else 0), 3.0, start)
        leader = cube("Leader", places.pop(0) if leader_on_ring else centre)
        self.lifted([leader])
        riders = [self.ride(leader, where, "R{:d}".format(number))
                  for number, where in enumerate(places)]
        select(leader)
        return leader, riders

    # -- Leads --------------------------------------------------------------

    def test_leads_round_a_tilted_ring_both_ways(self):
        self.ring_of_riders()
        self.assertEqual(self.spread("LEAD", order="AROUND", first=0.0, last=36.0,
                                     both_ways=True), {"FINISHED"})
        self.assertEqual(self.leads(), [0, 9, 18, 27, 36, 27, 18, 9])
        self.assertIn("Spread the Leads of 8 riders from 0 to 36", rig().rigmoves.report)

    def test_leads_with_the_leader_on_the_ring_itself(self):
        # Nine places, the leader on one: its neighbours are a ninth of the
        # way round, so nobody shares its value, and the far two share theirs.
        self.ring_of_riders(count=8, leader_on_ring=True)
        self.assertEqual(self.spread("LEAD", order="AROUND", first=0.0, last=36.0,
                                     both_ways=True), {"FINISHED"})
        self.assertEqual(self.leads(), [9, 18, 27, 36, 36, 27, 18, 9])

    def test_leads_run_one_way_round_without_both_ways(self):
        # Counter-clockwise looking down the ring's normal, which is up.
        self.ring_of_riders(count=4)
        self.spread("LEAD", order="AROUND", first=0.0, last=30.0)
        self.assertEqual(self.leads(), [0, 10, 20, 30])

    def test_leads_follow_the_ring_not_the_order_they_were_added_in(self):
        # The same four places, added 0, 270, 180, 90 degrees.
        leader = cube("Leader", (2.0, 1.0, 3.0))
        self.lifted([leader])
        places = ring_places((2.0, 1.0, 3.0), 4, 3.0)
        for number, where in enumerate([places[0], places[3], places[2], places[1]]):
            self.ride(leader, where, "R{:d}".format(number))
        select(leader)
        self.spread("LEAD", order="AROUND", first=0.0, last=30.0)
        self.assertEqual(self.leads(), [0, 30, 20, 10])

    def test_each_leader_spreads_its_own_riders(self):
        # Two rings, a leader each: both get the whole range, not half of it.
        one, two = cube("One", (0.0, 0.0, 0.0)), cube("Two", (20.0, 0.0, 0.0))
        self.lifted([one, two])
        for leader, centre in ((one, (0.0, 0.0, 0.0)), (two, (20.0, 0.0, 0.0))):
            for number, where in enumerate(ring_places(centre, 4, 3.0)):
                self.ride(leader, where, "{:s}{:d}".format(leader.name, number))
        select(one)
        self.assertEqual(self.spread("LEAD", order="AROUND", first=0.0, last=30.0),
                         {"FINISHED"})
        self.assertEqual(self.leads("One"), [0, 10, 20, 30])
        self.assertEqual(self.leads("Two"), [0, 10, 20, 30])

    def test_leads_play_at_once_on_a_built_move(self):
        leader = cube("Leader", (0.0, 5.0, 0.0))
        self.lifted([leader])
        riders = [self.ride(leader, (x, 0.0, 0.0), "R{:d}".format(x)) for x in (1, 2, 3)]
        bpy.ops.rigmoves.build()
        select(leader)
        self.assertEqual(self.spread("LEAD", order="AXIS", axis="X", first=0.0,
                                     last=-50.0), {"FINISHED"})
        self.assertEqual(self.leads(), [0, -25, -50])
        # No Build since. Behind by 0, half and a whole leader: the windows
        # on the control are 0-.5, .25-.75 and .5-1, so at half way the first
        # has arrived, the second is half way and the third has not set off.
        drive(self.move, 0.5)
        self.assertEqual([round(centre(r).z, 3) for r in riders], [1.0, 0.5, 0.0])
        bpy.ops.rigmoves.build()
        drive(self.move, 0.5)
        self.assertEqual([round(centre(r).z, 3) for r in riders], [1.0, 0.5, 0.0])

    def test_one_write_for_all_of_them(self):
        # The drivers are rewritten once, not once for every rider.
        leader = cube("Leader", (0.0, 5.0, 0.0))
        self.lifted([leader])
        for x in (1, 2, 3, 4):
            self.ride(leader, (x, 0.0, 0.0), "R{:d}".format(x))
        bpy.ops.rigmoves.build()
        select(leader)
        calls = []
        was = rigmoves.refresh_drivers

        def counting(*args):
            calls.append(1)
            return was(*args)

        rigmoves.refresh_drivers = counting
        try:
            self.spread("LEAD", order="AXIS", axis="X", first=0.0, last=-40.0)
        finally:
            rigmoves.refresh_drivers = was
        self.assertEqual(len(calls), 1)

    def test_leads_along_a_row_only_ever_step_one_way(self):
        leader = cube("Leader", (0.0, 5.0, 0.0))
        self.lifted([leader])
        for x in (3, 1, 4, 2):
            self.ride(leader, (x, 0.0, 0.0), "R{:d}".format(x))
        select(leader)
        self.spread("LEAD", order="AXIS", axis="X", first=0.0, last=-30.0)
        by_place = sorted((p.lead for p in self.move.parts if p.leader), reverse=True)
        self.assertEqual(by_place, [0, -10, -20, -30])
        self.assertEqual({p.name: p.lead for p in self.move.parts if p.leader},
                         {"R1": 0, "R2": -10, "R3": -20, "R4": -30})

    def test_leads_by_distance(self):
        leader = cube("Leader", (0.0, 0.0, 0.0))
        self.lifted([leader])
        for x in (1, 2, 4):
            self.ride(leader, (x, 0.0, 3.0), "R{:d}".format(x))
        select(leader)
        self.spread("LEAD", order="DISTANCE", first=0.0, last=-40.0)
        # Straight ahead of 3 up the sides, 4 out: nearest to farthest.
        far = [math.sqrt(x * x + 9.0) for x in (1, 2, 4)]
        self.assertEqual(self.leads(),
                         [round(-40.0 * d / max(far)) for d in far])

    def test_only_the_selected_riders_take_part(self):
        leader, riders = self.ring_of_riders(count=4)
        for part in self.move.parts:
            if part.leader:
                part.lead = 7
        select(leader, riders[1], riders[3])
        self.spread("LEAD", order="AROUND", first=0.0, last=30.0)
        self.assertEqual(self.leads(), [7, 0, 7, 30])

    def test_leads_are_held_to_what_a_lead_can_be(self):
        self.ring_of_riders(count=4)
        self.spread("LEAD", order="AROUND", first=-100.0, last=100.0)
        self.assertEqual(self.leads(), [-50, -33, 33, 50])
        self.assertIn("held at the limit", rig().rigmoves.report)

    def test_leads_need_riders(self):
        part = cube("Alone", (0.0, 0.0, 0.0))
        self.lifted([part])
        select(part)
        self.assertEqual(self.spread("LEAD", order="AROUND", first=0.0, last=9.0),
                         {"CANCELLED"})
        self.assertIn("no riders", rig().rigmoves.report)

    def test_riders_have_no_chain_to_spread_down(self):
        self.ring_of_riders(count=4)
        self.assertEqual(self.spread("LEAD", order="CHAIN", first=0.0, last=9.0),
                         {"CANCELLED"})
        self.assertIn("no chain", rig().rigmoves.report)
        self.assertEqual(self.leads(), [0, 0, 0, 0])

    # -- Delays -------------------------------------------------------------

    def parts_at(self, places):
        objects = [cube("P{:d}".format(n), where) for n, where in enumerate(places)]
        self.lifted(objects)
        return objects

    def test_delays_take_effect_on_a_built_move(self):
        objects = self.parts_at([(x, 0.0, 0.0) for x in (0, 1, 2)])
        bpy.ops.rigmoves.build()
        select(*objects)
        self.assertEqual(self.spread("DELAY", order="AXIS", axis="X", first=0.0,
                                     last=0.5), {"FINISHED"})
        self.assertEqual(self.delays(), [0.0, 0.25, 0.5])
        # Waiting 0, a quarter and a half of the control: at half way the
        # first is half way through its path, the second a third, the last
        # has not set off.
        drive(self.move, 0.5)
        self.assertEqual([round(centre(o).z, 3) for o in objects], [0.5, 0.333, 0.0])

    def test_delays_down_a_chain_follow_the_depth(self):
        objects = self.parts_at([(x + 0.5, 0.0, 0.0) for x in range(4)])
        for number in range(1, 4):
            self.move.parts[number].follows = "P{:d}".format(number - 1)
        select(*objects)
        self.assertEqual(self.spread("DELAY", order="CHAIN", first=0.0, last=0.6),
                         {"FINISHED"})
        self.assertEqual(self.delays(), [0.0, 0.2, 0.4, 0.6])

    def test_delays_by_distance_from_the_active_part(self):
        objects = self.parts_at([(x, 0.0, 0.0) for x in (0, 1, 3, 6)])
        select(*objects)
        self.spread("DELAY", order="DISTANCE", first=0.0, last=0.6)
        self.assertEqual(self.delays(), [0.0, 0.1, 0.3, 0.6])
        # Measured from another part when that one is active.
        select(*reversed(objects))
        self.spread("DELAY", order="DISTANCE", first=0.0, last=0.6)
        self.assertEqual(self.delays(), [0.6, 0.5, 0.3, 0.0])

    def test_delays_round_a_ring_from_the_active_part(self):
        # Six parts on the ring, the third active: it goes first, and the
        # delay climbs round the ring from it.
        places = ring_places((0.0, 0.0, 0.0), 6, 3.0)
        objects = self.parts_at(places)
        select(objects[2], *[o for o in objects if o is not objects[2]])
        self.spread("DELAY", order="AROUND", first=0.0, last=0.5)
        self.assertEqual(self.delays(), [0.4, 0.5, 0.0, 0.1, 0.2, 0.3])
        self.spread("DELAY", order="AROUND", first=0.0, last=0.6, both_ways=True)
        self.assertEqual(self.delays(), [0.4, 0.2, 0.0, 0.2, 0.4, 0.6])

    def test_parts_turning_about_one_hub_are_ordered_by_where_they_are(self):
        # Every pivot the same point - a fan's blades about its hub - says
        # nothing about who stands where, so the blades' own places count.
        objects = self.parts_at(ring_places((0.0, 0.0, 0.0), 4, 3.0))
        bpy.context.scene.cursor.location = (0.0, 0.0, 0.0)
        select(*objects)
        self.assertEqual(bpy.ops.rigmoves.set_pivot(index=0, kind="CURSOR"), {"FINISHED"})
        self.spread("DELAY", order="AROUND", first=0.0, last=0.3)
        self.assertEqual(self.delays(), [0.0, 0.1, 0.2, 0.3])

    def test_random_is_the_same_every_time_for_a_seed(self):
        objects = self.parts_at([(x, 0.0, 0.0) for x in range(6)])
        select(*objects)
        self.spread("DELAY", order="RANDOM", first=0.1, last=0.9, seed=5)
        again = self.delays()
        self.assertTrue(all(0.1 <= d <= 0.9 for d in again), again)
        self.assertGreater(len(set(again)), 3)
        for part in self.move.parts:
            part.start = 0.0
        self.spread("DELAY", order="RANDOM", first=0.1, last=0.9, seed=5)
        self.assertEqual(self.delays(), again)
        self.spread("DELAY", order="RANDOM", first=0.1, last=0.9, seed=6)
        self.assertNotEqual(self.delays(), again)

    def test_only_the_selected_parts_take_a_delay(self):
        objects = self.parts_at([(x, 0.0, 0.0) for x in range(4)])
        for part in self.move.parts:
            part.start = 0.05
        select(objects[3], objects[1])
        self.spread("DELAY", order="AXIS", axis="X", first=0.2, last=0.4)
        self.assertEqual(self.delays(), [0.05, 0.2, 0.05, 0.4])

    def test_delays_are_held_to_what_a_delay_can_be(self):
        objects = self.parts_at([(x, 0.0, 0.0) for x in range(3)])
        select(*objects)
        self.spread("DELAY", order="AXIS", axis="X", first=-1.0, last=5.0)
        self.assertEqual(self.delays(), [0.0, 0.99, 0.99])
        self.assertIn("held at the limit", rig().rigmoves.report)

    def test_a_spread_can_be_undone(self):
        objects = self.parts_at([(x, 0.0, 0.0) for x in range(3)])
        select(*objects)
        undo_push()
        self.spread("DELAY", order="AXIS", axis="X", first=0.1, last=0.5)
        undo_push()
        self.assertEqual(self.delays(), [0.1, 0.3, 0.5])
        undo_once()
        self.assertEqual([round(p.start, 4) for p in rig().rigmoves.moves[0].parts],
                         [0.0, 0.0, 0.0])

    # -- the pieces ---------------------------------------------------------

    def test_a_rings_plane_is_found_and_a_line_falls_back_to_up(self):
        up = Vector((0.0, 0.0, 1.0))
        turn = Matrix.Rotation(math.radians(20.0), 3, "Z") @ Matrix.Rotation(
            math.radians(30.0), 3, "X")
        found = rigmoves.ring_normal(ring_places((1.0, 2.0, 3.0), 7, 2.0))
        self.assertLess((found - turn @ up).length, 1e-5)
        # A ring on its side has no up to point along: Y breaks the tie, the
        # same way every time.
        side = rigmoves.ring_normal([Vector((math.cos(a), 0.0, math.sin(a)))
                                     for a in (0.0, 1.5, 3.0, 4.5)])
        self.assertLess((side - Vector((0.0, 1.0, 0.0))).length, 1e-5)
        for points in ([], [Vector((1.0, 2.0, 3.0))],
                       [Vector((0.0, 0.0, 0.0)), Vector((1.0, 1.0, 1.0))],
                       [Vector((n, 2.0 * n, 3.0 * n)) for n in range(5)]):
            self.assertEqual(rigmoves.ring_normal(points), up)

    # -- the panel ----------------------------------------------------------

    def test_spread_buttons_sit_in_the_headers_of_riding_along_and_timing(self):
        self.ring_of_riders(count=4)
        found = [(where, text, idname) for where, idname, text in drawn_buttons()
                 if idname == "rigmoves.spread"]
        self.assertEqual(sorted(found), sorted([
            (("head:show_riders",), "Spread…", "rigmoves.spread"),
            (("head:show_timing",), "Spread…", "rigmoves.spread")]))


class TestMakeChain(CopyThatCase):
    """Four segments end to end, made - and so listed - in no order at all."""

    KNUCKLES = [Vector((float(n), 0.0, 0.0)) for n in range(4)]

    def setUp(self):
        super().setUp()
        self.segments = {}
        for number in (3, 1, 4, 2):
            segment = cube("Seg{:d}".format(number), (number - 0.5, 0.0, 0.0))
            segment.scale = (1.0, 0.3, 0.3)
            self.segments[number] = segment
        bpy.context.view_layer.update()
        self.homes = {n: s.matrix_world.copy() for n, s in self.segments.items()}
        select(*self.segments.values())
        self.assertEqual(bpy.ops.rigmoves.new_move(), {"FINISHED"})
        self.move = rig().rigmoves.moves[0]

    def everything(self, first=1):
        """Every segment selected, this one active."""
        select(self.segments[first], *[s for n, s in self.segments.items() if n != first])

    def chain(self, first=1):
        self.everything(first)
        return bpy.ops.rigmoves.make_chain(index=0)

    def follows(self):
        return {p.name: p.follows for p in self.move.parts}

    def bent(self, degrees):
        out, carry = [], Matrix.Identity(4)
        for number, knuckle in enumerate(self.KNUCKLES):
            carry = (carry @ Matrix.Translation(knuckle)
                     @ Matrix.Rotation(math.radians(degrees), 4, "Y")
                     @ Matrix.Translation(-knuckle))
            out.append(carry @ self.homes[number + 1])
        return out

    def check_curl(self, share, degrees):
        drive(self.move, share)
        for number, place in enumerate(self.bent(degrees)):
            segment = self.segments[number + 1]
            expected = [place @ v.co for v in segment.data.vertices]
            self.assertLess(drift(segment, expected), TOLERANCE, segment.name)

    def test_follows_come_out_in_spatial_order(self):
        names = [p.name for p in self.move.parts]
        self.assertNotEqual(names, ["Seg1", "Seg2", "Seg3", "Seg4"])
        self.assertEqual(self.chain(), {"FINISHED"})
        self.assertEqual(self.follows(),
                         {"Seg1": "", "Seg2": "Seg1", "Seg3": "Seg2", "Seg4": "Seg3"})
        self.assertEqual(rig().rigmoves.report, "Chain: Seg1 > Seg2 > Seg3 > Seg4")
        # The objects hang from one another at once, as a Follows pick does.
        self.assertEqual(self.segments[2].parent, self.segments[1])
        self.assertEqual(self.segments[4].parent, self.segments[3])

    def test_the_chain_runs_from_the_active_end(self):
        # From the other end the same four parts chain the other way.
        self.assertEqual(self.chain(first=4), {"FINISHED"})
        self.assertEqual(self.follows(),
                         {"Seg4": "", "Seg3": "Seg4", "Seg2": "Seg3", "Seg1": "Seg2"})

    def test_a_chain_then_a_finger_that_curls(self):
        for number, knuckle in enumerate(self.KNUCKLES):
            bpy.context.scene.cursor.location = knuckle
            select(self.segments[number + 1])
            bpy.ops.rigmoves.set_pivot(index=0, kind="CURSOR")
        self.assertEqual(self.chain(), {"FINISHED"})
        for number, place in enumerate(self.bent(30.0)):
            self.segments[number + 1].matrix_world = place
            bpy.context.view_layer.update()
        self.assertEqual(bpy.ops.rigmoves.record(index=0, which="AFTER"), {"FINISHED"})
        bpy.ops.rigmoves.build()
        self.check_curl(0.0, 0.0)
        self.check_curl(0.5, 15.0)
        self.check_curl(1.0, 30.0)

    def test_on_a_built_move_it_waits_for_build(self):
        bpy.ops.rigmoves.build()
        self.assertEqual(self.chain(), {"FINISHED"})
        self.assertTrue(rigmoves.parent_pending(rig(), rig().rigmoves, self.move))
        self.assertIn("Build to put it into effect", rig().rigmoves.report)
        bpy.ops.rigmoves.build()
        self.assertFalse(rigmoves.parent_pending(rig(), rig().rigmoves, self.move))
        bones = rig().data.bones
        for number in (2, 3, 4):
            part, ahead = self.move.parts["Seg{:d}".format(number)], \
                self.move.parts["Seg{:d}".format(number - 1)]
            self.assertEqual(bones[part.bone_name].parent.name, ahead.bone_name)

    def test_a_rider_in_the_selection_stops_the_chain_there(self):
        # Seg1 leads a rider that stands between Seg3 and Seg4. The rider
        # cannot follow, and the chain stops there, with the reason said.
        rider = cube("Rider", (3.0, 0.0, 0.0))
        select(self.segments[1], rider)
        self.assertEqual(bpy.ops.rigmoves.ride_along(index=0, leader="Seg1",
                                                     rig_name=rig().name), {"FINISHED"})
        select(self.segments[1], self.segments[2], self.segments[3], rider,
               self.segments[4])
        self.assertEqual(bpy.ops.rigmoves.make_chain(index=0), {"FINISHED"})
        self.assertEqual(self.follows(), {"Seg1": "", "Seg2": "Seg1", "Seg3": "Seg2",
                                          "Seg4": "", "Rider": ""})
        said = rig().rigmoves.report
        self.assertIn("Chain: Seg1 > Seg2 > Seg3", said)
        self.assertIn("'Rider' cannot follow 'Seg3'", said)
        self.assertIn("riders copy their leader instead", said)

    def test_a_chain_refused_at_its_first_link_changes_nothing(self):
        rider = cube("Rider", (1.0, 3.0, 0.0))
        select(self.segments[1], rider)
        bpy.ops.rigmoves.ride_along(index=0, leader="Seg1", rig_name=rig().name)
        select(self.segments[1], rider)
        self.assertEqual(bpy.ops.rigmoves.make_chain(index=0), {"CANCELLED"})
        self.assertEqual(set(self.follows().values()), {""})
        self.assertIn("riders copy their leader instead", rig().rigmoves.report)

    def test_it_asks_for_what_it_needs(self):
        select(self.segments[1])
        self.assertEqual(bpy.ops.rigmoves.make_chain(index=0), {"CANCELLED"})
        self.assertIn("two at least", rig().rigmoves.report)
        # The active object has to be one of the selected parts.
        outsider = cube("Outsider", (9.0, 9.0, 0.0))
        select(outsider, self.segments[1], self.segments[2])
        self.assertEqual(bpy.ops.rigmoves.make_chain(index=0), {"CANCELLED"})
        self.assertIn("starts from the active", rig().rigmoves.report)
        self.assertEqual(set(self.follows().values()), {""})

    def test_a_rider_cannot_start_a_chain(self):
        rider = cube("Rider", (1.0, 3.0, 0.0))
        select(self.segments[1], rider)
        bpy.ops.rigmoves.ride_along(index=0, leader="Seg1", rig_name=rig().name)
        select(rider, self.segments[1], self.segments[2])
        self.assertEqual(bpy.ops.rigmoves.make_chain(index=0), {"CANCELLED"})
        self.assertIn("rides along", rig().rigmoves.report)

    def test_a_chain_can_be_undone(self):
        self.everything()
        undo_push()
        bpy.ops.rigmoves.make_chain(index=0)
        undo_push()
        undo_once()
        self.assertEqual({p.follows for p in rig().rigmoves.moves[0].parts}, {""})

    def test_the_button_is_in_the_follows_section(self):
        found = [(where, text) for where, idname, text in drawn_buttons()
                 if idname == "rigmoves.make_chain"]
        self.assertEqual(found, [(("body:show_chain", "row"), "Make Chain")])


class TestCurl(CopyThatCase):
    """A tentacle of five segments end to end, each hinged on its own joint
    and hanging from the one before. Only the first is ever posed by hand."""

    KNUCKLES = [Vector((float(n), 0.0, 0.0)) for n in range(5)]

    def setUp(self):
        super().setUp()
        self.segments = []
        for number in range(5):
            segment = cube("Seg{:d}".format(number + 1), (number + 0.5, 0.0, 0.0))
            segment.scale = (1.0, 0.3, 0.3)
            self.segments.append(segment)
        bpy.context.view_layer.update()
        self.homes = [s.matrix_world.copy() for s in self.segments]
        select(*self.segments)
        self.assertEqual(bpy.ops.rigmoves.new_move(), {"FINISHED"})
        self.move = rig().rigmoves.moves[0]
        for segment, knuckle in zip(self.segments, self.KNUCKLES):
            bpy.context.scene.cursor.location = knuckle
            select(segment)
            bpy.ops.rigmoves.set_pivot(index=0, kind="CURSOR")
        for number in range(1, 5):
            self.move.parts["Seg{:d}".format(number + 1)].follows = "Seg{:d}".format(number)

    def bent_by(self, angles):
        """Each segment's place with each joint bent by its own angle, each
        carried by the ones before it."""
        out, carry = [], Matrix.Identity(4)
        for knuckle, home, degrees in zip(self.KNUCKLES, self.homes, angles):
            carry = carry @ turn_about(knuckle, "Y", degrees)
            out.append(carry @ home)
        return out

    def check_places(self, places):
        for segment, place in zip(self.segments, places):
            expected = [place @ v.co for v in segment.data.vertices]
            self.assertLess(drift(segment, expected), TOLERANCE, segment.name)

    def check_joints(self):
        """No gap where one segment meets the next: the middle of the far end
        of each is the middle of the near end of the one after - the joint,
        which they both turn about. (Bent, the corners open like a hinge.)"""
        def middle(number, far):
            segment, points = self.segments[number], world_points(self.segments[number])
            ends = [p for v, p in zip(segment.data.vertices, points)
                    if (v.co.x > 0) == far]
            return sum(ends, Vector()) / len(ends)

        for number in range(4):
            self.assertLess((middle(number, True) - middle(number + 1, False)).length,
                            TOLERANCE, number)

    def pose_root(self, degrees):
        """Turn the first segment about its own joint by hand."""
        self.segments[0].matrix_world = turn_about(self.KNUCKLES[0], "Y", degrees) @ self.homes[0]
        bpy.context.view_layer.update()

    def curl(self, **kwargs):
        select(self.segments[0])
        return bpy.ops.rigmoves.curl(index=0, **kwargs)

    def close(self, degrees):
        """Every segment bent to this, recorded as After."""
        for segment, place in zip(self.segments, self.bent_by((degrees,) * 5)):
            segment.matrix_world = place
            bpy.context.view_layer.update()
        self.assertEqual(bpy.ops.rigmoves.record(index=0, which="AFTER"), {"FINISHED"})

    def play(self, share, degrees):
        drive(self.move, share)
        self.check_places(self.bent_by((degrees,) * 5))

    # -- loose --------------------------------------------------------------

    def test_loose_every_joint_bends_like_the_first(self):
        self.pose_root(20.0)
        self.assertEqual(self.curl(), {"FINISHED"})
        self.check_places(self.bent_by((20.0,) * 5))
        self.check_joints()
        self.assertIn("4 part(s) below 'Seg1' now bend 20 degrees like it",
                      rig().rigmoves.report)
        # Kept: recorded, built, and played.
        self.assertEqual(bpy.ops.rigmoves.record(index=0, which="AFTER"), {"FINISHED"})
        bpy.ops.rigmoves.build()
        self.play(1.0, 20.0)
        self.check_joints()
        self.play(0.5, 10.0)
        self.play(0.0, 0.0)
        self.check_places(self.homes)

    def test_loose_each_joint_after_the_first_keeps_a_share(self):
        self.pose_root(20.0)
        self.assertEqual(self.curl(factor=0.5), {"FINISHED"})
        # The first joint after the root repeats its bend, and each one past
        # that keeps half of the one before: 20, 10, 5, 2.5 below the root.
        self.check_places(self.bent_by((20.0, 20.0, 10.0, 5.0, 2.5)))
        self.check_joints()
        self.assertIn("each joint after the first x0.5", rig().rigmoves.report)
        self.assertEqual(bpy.ops.rigmoves.record(index=0, which="AFTER"), {"FINISHED"})
        bpy.ops.rigmoves.build()
        drive(self.move, 1.0)
        self.check_places(self.bent_by((20.0, 20.0, 10.0, 5.0, 2.5)))

    def test_a_factor_above_one_bends_the_tip_most(self):
        self.pose_root(10.0)
        self.assertEqual(self.curl(factor=2.0), {"FINISHED"})
        self.check_places(self.bent_by((10.0, 10.0, 20.0, 40.0, 80.0)))
        self.check_joints()

    def test_a_turn_about_the_pivot_is_all_that_is_repeated(self):
        # The first segment turned and slid: only the turn is carried down.
        self.segments[0].matrix_world = (Matrix.Translation((0.0, 0.0, 0.7))
                                         @ turn_about(self.KNUCKLES[0], "Y", 20.0)
                                         @ self.homes[0])
        bpy.context.view_layer.update()
        self.assertEqual(self.curl(), {"FINISHED"})
        slide = Matrix.Translation((0.0, 0.0, 0.7))
        places = self.bent_by((20.0,) * 5)
        # The first stands where it was put; the rest are bent on their own
        # joints and carried by it, slid with it.
        self.check_places([slide @ p for p in places])

    # -- built --------------------------------------------------------------

    def test_built_from_play_zero_through_record_after(self):
        bpy.ops.rigmoves.build()
        drive(self.move, 0.0)
        self.pose_root(20.0)
        self.assertEqual(self.curl(), {"FINISHED"})
        self.check_places(self.bent_by((20.0,) * 5))
        self.assertEqual(bpy.ops.rigmoves.record(index=0, which="AFTER"), {"FINISHED"})
        bpy.context.view_layer.update()
        # What Record keeps is exactly what Curl made.
        self.check_places(self.bent_by((20.0,) * 5))
        self.assertEqual(rigmoves.unrecorded(rig().rigmoves), [])
        bpy.ops.rigmoves.build()
        self.play(1.0, 20.0)
        self.check_joints()
        self.play(0.5, 10.0)
        self.play(0.0, 0.0)
        self.check_places(self.homes)

    def test_a_second_curl_replaces_the_after_that_was_there(self):
        self.close(30.0)
        bpy.ops.rigmoves.build()
        drive(self.move, 0.0)
        self.pose_root(20.0)
        self.assertEqual(self.curl(), {"FINISHED"})
        self.assertEqual(bpy.ops.rigmoves.record(index=0, which="AFTER"), {"FINISHED"})
        bpy.ops.rigmoves.build()
        self.play(1.0, 20.0)
        self.play(0.5, 10.0)

    def test_built_through_a_step(self):
        self.close(30.0)
        bpy.ops.rigmoves.build()
        drive(self.move, 0.0)
        bpy.ops.rigmoves.add_step(index=0)
        self.pose_root(20.0)
        self.assertEqual(self.curl(), {"FINISHED"})
        self.assertEqual(bpy.ops.rigmoves.record(index=0, which="STEP", step=0),
                         {"FINISHED"})
        bpy.ops.rigmoves.build()
        self.play(0.5, 20.0)
        self.play(1.0, 30.0)
        self.play(0.0, 0.0)

    def test_refused_while_the_eye_shows_after(self):
        self.close(30.0)
        bpy.ops.rigmoves.build()
        bpy.ops.rigmoves.show(index=0, which="AFTER")
        self.assertEqual(self.curl(), {"CANCELLED"})
        said = rig().rigmoves.report
        self.assertIn("Curl works from rest", said)
        self.assertIn("Build first", said)
        # Nothing was moved, and a Build puts the sliders back.
        bpy.ops.rigmoves.build()
        drive(self.move, 0.0)
        self.pose_root(20.0)
        self.assertEqual(self.curl(), {"FINISHED"})

    def test_refused_with_play_above_zero(self):
        self.close(30.0)
        bpy.ops.rigmoves.build()
        drive(self.move, 0.5)
        self.assertEqual(self.curl(), {"CANCELLED"})
        self.assertIn("Curl works from rest: drag Play to 0", rig().rigmoves.report)
        self.assertNotIn("Build first", rig().rigmoves.report)
        drive(self.move, 0.0)
        self.pose_root(20.0)
        self.assertEqual(self.curl(), {"FINISHED"})

    # -- where it begins ----------------------------------------------------

    def test_from_a_joint_in_the_middle_of_the_chain(self):
        # Seg3 bent by hand, on its own joint: it and what follows it bend;
        # what it hangs from is left as it was.
        self.segments[2].matrix_world = turn_about(self.KNUCKLES[2], "Y", 20.0) @ self.homes[2]
        bpy.context.view_layer.update()
        select(self.segments[2])
        self.assertEqual(bpy.ops.rigmoves.curl(index=0), {"FINISHED"})
        self.check_places(self.bent_by((0.0, 0.0, 20.0, 20.0, 20.0)))
        self.check_joints()

    def test_it_asks_for_what_it_needs(self):
        outsider = cube("Outsider", (9.0, 9.0, 0.0))
        select(outsider)
        self.assertEqual(bpy.ops.rigmoves.curl(index=0), {"CANCELLED"})
        self.assertIn("first joint", rig().rigmoves.report)
        # Not turned yet.
        self.assertEqual(self.curl(), {"CANCELLED"})
        self.assertIn("has not been turned", rig().rigmoves.report)
        # Nothing follows the last one.
        select(self.segments[4])
        self.assertEqual(bpy.ops.rigmoves.curl(index=0), {"CANCELLED"})
        self.assertIn("Nothing follows 'Seg5'", rig().rigmoves.report)
        self.check_places(self.homes)

    def test_a_rider_has_no_bend_to_repeat(self):
        rider = cube("Rider", (0.5, 4.0, 0.0))
        select(self.segments[0], rider)
        # The leader may not follow anything, so first let it go.
        self.move.parts["Seg2"].follows = ""
        self.assertEqual(bpy.ops.rigmoves.ride_along(index=0, leader="Seg1",
                                                     rig_name=rig().name), {"FINISHED"})
        select(rider)
        self.assertEqual(bpy.ops.rigmoves.curl(index=0), {"CANCELLED"})
        self.assertIn("rides along", rig().rigmoves.report)

    def test_a_curl_can_be_undone(self):
        self.pose_root(20.0)
        select(self.segments[0])
        undo_push()
        bpy.ops.rigmoves.curl(index=0)
        undo_push()
        self.assertEqual(rigmoves.same_matrix(
            bpy.data.objects["Seg5"].matrix_world, self.bent_by((20.0,) * 5)[4], 1e-4), True)
        undo_once()
        # Back to the first segment bent by hand, the rest carried whole.
        carry = turn_about(self.KNUCKLES[0], "Y", 20.0)
        for number in range(5):
            seat = bpy.data.objects["Seg{:d}".format(number + 1)].matrix_world
            self.assertTrue(rigmoves.same_matrix(seat, carry @ self.homes[number], 1e-4),
                            number)

    def test_the_button_sits_beside_make_chain(self):
        found = [(where, text) for where, idname, text in drawn_buttons()
                 if idname == "rigmoves.curl"]
        self.assertEqual(found, [(("body:show_chain", "row"), "Curl")])


class TestCurlOwnAxes(CopyThatCase):
    """A tentacle that curves as it goes: every segment faces a different way,
    so its own axes are not the world's, and each bends about its own."""

    def setUp(self):
        super().setUp()
        self.segments, self.frames, self.knuckles = [], [], []
        end = Vector((0.0, 0.0, 0.0))
        for number in range(4):
            turn = Matrix.Rotation(math.radians(25.0 * number), 3, "Z")
            segment = cube("Seg{:d}".format(number + 1), end + turn @ Vector((0.5, 0.0, 0.0)))
            segment.rotation_euler.z = math.radians(25.0 * number)
            segment.scale = (1.0, 0.3, 0.3)
            self.segments.append(segment)
            self.frames.append(turn)
            self.knuckles.append(end.copy())
            end = end + turn @ Vector((1.0, 0.0, 0.0))
        bpy.context.view_layer.update()
        self.homes = [s.matrix_world.copy() for s in self.segments]
        select(*self.segments)
        bpy.ops.rigmoves.new_move()
        self.move = rig().rigmoves.moves[0]
        for segment, knuckle in zip(self.segments, self.knuckles):
            bpy.context.scene.cursor.location = knuckle
            select(segment)
            bpy.ops.rigmoves.set_pivot(index=0, kind="CURSOR")
        for number in range(1, 4):
            self.move.parts["Seg{:d}".format(number + 1)].follows = "Seg{:d}".format(number)

    def bent_by(self, angles):
        """Each bends about its own local Y, through its own knuckle."""
        out, carry = [], Matrix.Identity(4)
        for frame, knuckle, home, degrees in zip(self.frames, self.knuckles, self.homes, angles):
            carry = carry @ turn_about(knuckle, frame @ Vector((0.0, 1.0, 0.0)), degrees)
            out.append(carry @ home)
        return out

    def test_each_joint_bends_about_its_own_axes(self):
        self.segments[0].matrix_world = self.bent_by((20.0,))[0]
        bpy.context.view_layer.update()
        select(self.segments[0])
        self.assertEqual(bpy.ops.rigmoves.curl(index=0, factor=0.5), {"FINISHED"})
        for segment, place in zip(self.segments, self.bent_by((20.0, 20.0, 10.0, 5.0))):
            expected = [place @ v.co for v in segment.data.vertices]
            self.assertLess(drift(segment, expected), TOLERANCE, segment.name)


class TestCurlBranches(CopyThatCase):
    """A palm with two fingers of two joints each: the palm is bent by hand
    and the bend runs down both."""

    def setUp(self):
        super().setUp()
        spots = {"Palm": (0.0, 0.0, 0.0), "A1": (1.0, 0.3, 0.0), "A2": (2.0, 0.3, 0.0),
                 "B1": (1.0, -0.3, 0.0), "B2": (2.0, -0.3, 0.0)}
        self.knuckles = {"Palm": Vector((0.5, 0.0, 0.0)), "A1": Vector((0.5, 0.3, 0.0)),
                         "A2": Vector((1.5, 0.3, 0.0)), "B1": Vector((0.5, -0.3, 0.0)),
                         "B2": Vector((1.5, -0.3, 0.0))}
        self.objects = {}
        for name, where in spots.items():
            obj = cube(name, where)
            obj.scale = (1.0, 0.25, 0.25) if name != "Palm" else (1.0, 1.0, 0.25)
            self.objects[name] = obj
        bpy.context.view_layer.update()
        self.homes = {n: o.matrix_world.copy() for n, o in self.objects.items()}
        select(*self.objects.values())
        bpy.ops.rigmoves.new_move()
        self.move = rig().rigmoves.moves[0]
        for name, knuckle in self.knuckles.items():
            bpy.context.scene.cursor.location = knuckle
            select(self.objects[name])
            bpy.ops.rigmoves.set_pivot(index=0, kind="CURSOR")
        for name, ahead in (("A1", "Palm"), ("A2", "A1"), ("B1", "Palm"), ("B2", "B1")):
            self.move.parts[name].follows = ahead

    def test_the_bend_runs_down_both_fingers(self):
        palm = turn_about(self.knuckles["Palm"], "Y", 20.0)
        self.objects["Palm"].matrix_world = palm @ self.homes["Palm"]
        bpy.context.view_layer.update()
        select(self.objects["Palm"])
        self.assertEqual(bpy.ops.rigmoves.curl(index=0), {"FINISHED"})
        carried = {"Palm": palm}
        for name, ahead in (("A1", "Palm"), ("B1", "Palm"), ("A2", "A1"), ("B2", "B1")):
            carried[name] = carried[ahead] @ turn_about(self.knuckles[name], "Y", 20.0)
        for name, obj in self.objects.items():
            expected = [carried[name] @ self.homes[name] @ v.co for v in obj.data.vertices]
            self.assertLess(drift(obj, expected), TOLERANCE, name)
        self.assertIn("4 part(s) below 'Palm'", rig().rigmoves.report)
        # And it plays: recorded, built, closed at 1 and home at 0.
        self.assertEqual(bpy.ops.rigmoves.record(index=0, which="AFTER"), {"FINISHED"})
        bpy.ops.rigmoves.build()
        drive(self.move, 1.0)
        for name, obj in self.objects.items():
            expected = [carried[name] @ self.homes[name] @ v.co for v in obj.data.vertices]
            self.assertLess(drift(obj, expected), TOLERANCE, name)
        drive(self.move, 0.0)
        for name, obj in self.objects.items():
            expected = [self.homes[name] @ v.co for v in obj.data.vertices]
            self.assertLess(drift(obj, expected), TOLERANCE, name)


class TestCombined(CopyThatCase):

    def test_combined_control_plays_members_in_order(self):
        first = cube("First", (0.0, 0.0, 1.0))
        second = cube("Second", (3.0, 0.0, 1.0))

        def lift(obj):
            def pose():
                obj.location.z += 1.0
            return pose

        record_move([first], lift(first))
        record_move([second], lift(second))
        self.assertEqual(bpy.ops.rigmoves.combine(), {"FINISHED"})
        bpy.ops.rigmoves.build()
        data = rig().rigmoves
        group = data.groups[0]
        self.assertEqual([m.start for m in group.members], [0.0, 0.5])

        # Each member waits for its delay and then runs to the end of the
        # combined control, so a quarter of the way the first is a quarter
        # along and the second has not started.
        drive(group, 0.25)
        self.assertAlmostEqual(centre(first).z, 1.25, places=4)
        self.assertAlmostEqual(centre(second).z, 1.0, places=4)
        drive(group, 1.0)
        self.assertAlmostEqual(centre(first).z, 2.0, places=4)
        self.assertAlmostEqual(centre(second).z, 2.0, places=4)

        # A member's own control still plays it alone.
        drive(group, 0.0)
        drive(data.moves[1], 1.0)
        self.assertAlmostEqual(centre(first).z, 1.0, places=4)
        self.assertAlmostEqual(centre(second).z, 2.0, places=4)

        # Removing the combined control takes its handle's driver with it.
        slider = group.prop
        self.assertEqual(bpy.ops.rigmoves.remove_group(index=0), {"FINISHED"})
        left = [d.data_path for d in rig().animation_data.drivers
                if '["{:s}"]'.format(slider) in d.data_path]
        self.assertEqual(left, [])


class TestRegistration(unittest.TestCase):

    def test_reload_registers_again(self):
        # What a script reload does: a fresh copy of the module registers
        # while the old one is still in.
        global rigmoves
        rigmoves = importlib.reload(rigmoves)
        rigmoves.register()
        self.assertTrue(hasattr(bpy.types.Object, "rigmoves"))


if __name__ == "__main__":
    # Inside a Blender binary sys.argv is Blender's own command line; only what
    # follows "--" is meant for the tests.
    argv = sys.argv
    if "--" in argv:
        argv = [argv[0]] + argv[argv.index("--") + 1:]
    elif not argv[0].endswith(".py"):
        argv = [argv[0]]
    unittest.main(argv=argv, verbosity=2)
