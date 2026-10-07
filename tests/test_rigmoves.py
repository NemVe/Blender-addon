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
