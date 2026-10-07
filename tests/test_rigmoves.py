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
from mathutils import Matrix  # noqa: E402

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
        half = (Matrix.Translation((0.5, 0.0, 0.0))
                @ Matrix.Rotation(math.radians(15.0), 4, "Y"))
        self.assertLess(drift(self.rider, self.expected(half)), TOLERANCE)
        drive(move, 1.0)
        full = (Matrix.Translation((1.0, 0.0, 0.0))
                @ Matrix.Rotation(math.radians(30.0), 4, "Y"))
        self.assertLess(drift(self.rider, self.expected(full)), TOLERANCE)
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
