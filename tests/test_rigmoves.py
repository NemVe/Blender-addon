"""RigMoves, driven end to end in Blender without a window.

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


class RigMovesCase(unittest.TestCase):

    def setUp(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)

    def our_drivers(self):
        animation = rig().animation_data
        return [d for d in (animation.drivers if animation else ())
                if "constraints[" in d.data_path]


class TestObjects(RigMovesCase):

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


class TestRiders(RigMovesCase):
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


class TestPivot(RigMovesCase):
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


class TestMirror(RigMovesCase):
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


class TestCurve(RigMovesCase):
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


class TestFollowers(RigMovesCase):
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
        out, carry = [], Matrix.Identity(4)
        for knuckle, home in zip(self.KNUCKLES, self.homes):
            carry = (carry @ Matrix.Translation(knuckle)
                     @ Matrix.Rotation(math.radians(degrees), 4, "Y")
                     @ Matrix.Translation(-knuckle))
            out.append(carry @ home)
        return out

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


class TestModelledHierarchy(RigMovesCase):
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


class TestCombined(RigMovesCase):

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
