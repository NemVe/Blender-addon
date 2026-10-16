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
import re
import sys
import tempfile
import types
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bpy  # noqa: E402
import bmesh  # noqa: E402
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
    is logged with the path of sub-panels it was put in. So is every label,
    and every row that is told how to align: those say how much of the width
    something takes, and what a person reads on the row.
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

    def label(self, text="", icon="NONE", **_kwargs):
        self.log.append((self.where, "label:" + icon, text))

    def __setattr__(self, name, value):
        if name == "alignment":
            self.log.append((self.where, "alignment", value))
        super().__setattr__(name, value)

    def __getattr__(self, name):
        # prop, separator and the rest: nothing to note.
        if name.startswith("__"):
            raise AttributeError(name)
        return lambda *args, **kwargs: None


def drawn_panel(context=None):
    """Everything the panel draws now, as (path, kind, text). A button's kind
    is its operator id, a label's is "label:" and its icon, and a row that is
    aligned has "alignment" and the alignment for its text. Drawn for the real
    context, or for the one given."""
    log = []

    class Drawing:
        layout = Sketch(log)

    for name in dir(rigmoves.RIGMOVES_PT_panel):
        if name == "draw" or name.startswith("_draw"):
            setattr(Drawing, name, getattr(rigmoves.RIGMOVES_PT_panel, name))
    Drawing().draw(bpy.context if context is None else context)
    return log


def drawn_buttons():
    """Every button the panel draws now, as (path, operator id, text)."""
    return [row for row in drawn_panel() if "." in row[1]]


class Sidebar:
    """The real context, as a panel sees it from a sidebar this wide. A run
    with no window has no region, and Blender's own UI scale reads 0 there, so
    both are given; the font and its size are the real ones."""

    def __init__(self, width, scale=1.0):
        self.region = types.SimpleNamespace(width=width)
        self.preferences = types.SimpleNamespace(
            system=types.SimpleNamespace(ui_scale=scale),
            ui_styles=bpy.context.preferences.ui_styles)

    def __getattr__(self, name):
        return getattr(bpy.context, name)


def text_width(text, scale=1.0):
    """How wide Blender draws this text in the font and size its widgets use,
    in pixels - 0 where the font is not there to measure with."""
    import blf
    blf.size(0, bpy.context.preferences.ui_styles[0].widget.points * scale)
    return blf.dimensions(0, text)[0]


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

    def test_many_ride_along_at_once(self):
        # 0.15 read the leader back after adding the riders, and adding can
        # move the list it was read from: six at once crashed Blender more
        # often than not.
        bpy.ops.rigmoves.build()
        others = [cube("Other{:d}".format(n), (0.0, 3.0 + 2.0 * n, 0.0)) for n in range(6)]
        rest = [rest_points(o) for o in others]
        select(*others, self.petal)
        bpy.context.view_layer.objects.active = self.petal
        self.assertEqual(bpy.ops.rigmoves.ride_along(index=0, leader="Petal",
                                                     rig_name=rig().name), {"FINISHED"})
        move = rig().rigmoves.moves[0]
        self.assertEqual(sorted(p.leader for p in move.parts if p.leader), ["Petal"] * 6)
        # Each does the petal's move to its own left, from where it stands.
        drive(move, 1.0)
        for other, points in zip(others, rest):
            seat = other.matrix_world
            travel = seat @ self.full @ seat.inverted()
            self.assertLess(drift(other, [travel @ p for p in points]), TOLERANCE)

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

    def other_beside_the_middle(self):
        """A copy of the middle segment, five along Y: Seg1 turns about the
        Y axis through its knuckle, which carries anything along Y the same
        way - so the copy should do exactly what the middle does, five over."""
        other = cube("Other", (1.5, 5.0, 0.0))
        other.scale = (1.0, 0.3, 0.3)
        bpy.context.view_layer.update()
        return other

    def check_beside_the_middle(self, other):
        for share in (0.5, 1.0):
            drive(self.move, share)
            expected = [p + Vector((0.0, 5.0, 0.0)) for p in world_points(self.segments[1])]
            self.assertLess(drift(other, expected), TOLERANCE)

    def test_a_follower_leads_riders_from_what_it_hangs_on(self):
        # A second claw on the same arm: it rides along with the first, and
        # the arm carries it, as the arm carries the first.
        self.built_curl()
        other = self.other_beside_the_middle()
        select(other, self.segments[1])
        bpy.context.view_layer.objects.active = self.segments[1]
        self.assertEqual([p.name for _i, _m, p in rigmoves.leaders(bpy.context, rig())],
                         ["Seg2"])
        self.assertEqual(bpy.ops.rigmoves.ride_along(index=0, leader="Seg2",
                                                     rig_name=rig().name), {"FINISHED"})
        bone = rig().data.bones[self.move.parts["Other"].bone_name]
        self.assertEqual(bone.parent.name, self.move.parts["Seg1"].bone_name)
        self.check_beside_the_middle(other)

    def test_a_part_leading_riders_may_follow(self):
        # Turned down before, as its riders would have been left behind. They
        # hang from what it follows now, from the next Build.
        self.close()
        bpy.ops.rigmoves.build()
        other = self.other_beside_the_middle()
        select(other, self.segments[1])
        bpy.context.view_layer.objects.active = self.segments[1]
        bpy.ops.rigmoves.ride_along(index=0, leader="Seg2", rig_name=rig().name)
        self.chain()
        self.assertEqual(self.move.parts["Seg2"].follows, "Seg1")
        bpy.ops.rigmoves.build()
        bone = rig().data.bones[self.move.parts["Other"].bone_name]
        self.assertEqual(bone.parent.name, self.move.parts["Seg1"].bone_name)
        self.check_beside_the_middle(other)

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
        # These tests are about the Range: a first and a last, and what falls
        # between. The Step has its own tests below.
        kwargs.setdefault("by", "RANGE")
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

    def test_riders_are_placed_by_the_pivot_they_inherit(self):
        # The leader hinged well off its middle. A rider turns about that
        # hinge carried over to it, so the ring to measure is of those - not
        # of the leader's hinge against the riders' middles, which is lopsided.
        leader, _riders = self.ring_of_riders(count=5, leader_on_ring=True)
        bpy.context.scene.cursor.location = leader.location + Vector((0.4, 0.2, 0.3))
        select(leader)
        self.assertEqual(bpy.ops.rigmoves.set_pivot(index=0, kind="CURSOR"), {"FINISHED"})
        select(leader)
        self.spread("LEAD", order="AROUND", first=0.0, last=30.0, both_ways=True)
        self.assertEqual(self.leads(), [10, 20, 30, 20, 10])

    def test_leads_along_an_arc_of_a_ring(self):
        # A half-open fan: the leader and riders every 30 degrees from 0 to
        # 150 round the origin. The middle of an arc is not the average of its
        # parts, which put the 150 degree blade before the 120 degree one.
        leader = cube("Leader", (4.0, 0.0, 0.0))
        self.lifted([leader])
        for number in range(1, 6):
            angle = math.radians(30.0 * number)
            self.ride(leader, (4.0 * math.cos(angle), 4.0 * math.sin(angle), 0.0),
                      "R{:d}".format(number))
        select(leader)
        self.spread("LEAD", order="AROUND", first=0.0, last=50.0)
        self.assertEqual(self.leads(), [10, 20, 30, 40, 50])
        self.spread("LEAD", order="AROUND", first=0.0, last=50.0, both_ways=True)
        self.assertEqual(self.leads(), [10, 20, 30, 40, 50])

    def test_leads_for_a_few_picked_out_of_a_ring(self):
        leader = cube("Leader", (4.0, 0.0, 0.0))
        self.lifted([leader])
        riders = {}
        for number in range(1, 8):
            angle = math.radians(45.0 * number)
            riders[number] = self.ride(leader, (4.0 * math.cos(angle),
                                                4.0 * math.sin(angle), 0.0),
                                       "R{:d}".format(number))
        select(riders[1], riders[2], riders[3])
        for both_ways in (True, False):
            self.spread("LEAD", order="AROUND", first=0.0, last=30.0,
                        both_ways=both_ways, only_selected=True)
            self.assertEqual([self.move.parts[riders[n].name].lead for n in (1, 2, 3)],
                             [10, 20, 30])

    def test_a_spread_reaches_every_rider_whatever_was_left_selected(self):
        # Two rings with a leader each, and the second ring's copies selected,
        # as Ring leaves them: the first ring still gets its whole range.
        one, two = cube("One", (0.0, 0.0, 0.0)), cube("Two", (20.0, 0.0, 0.0))
        self.lifted([one, two])
        second = []
        for leader, centre in ((one, (0.0, 0.0, 0.0)), (two, (20.0, 0.0, 0.0))):
            for number, where in enumerate(ring_places(centre, 4, 3.0)):
                made = self.ride(leader, where, "{:s}{:d}".format(leader.name, number))
                if leader is two:
                    second.append(made)
        select(two, *second)
        self.assertEqual(self.spread("LEAD", order="AROUND", first=0.0, last=30.0),
                         {"FINISHED"})
        self.assertEqual(self.leads("One"), [0, 10, 20, 30])
        self.assertEqual(self.leads("Two"), [0, 10, 20, 30])

    def test_delays_reach_every_part_whatever_was_left_selected(self):
        # A tentacle after a Curl has only its first joint selected.
        objects = self.parts_at([(x + 0.5, 0.0, 0.0) for x in range(4)])
        for number in range(1, 4):
            self.move.parts[number].follows = "P{:d}".format(number - 1)
        select(objects[0])
        self.assertEqual(self.spread("DELAY", order="CHAIN", first=0.0, last=0.6),
                         {"FINISHED"})
        self.assertEqual(self.delays(), [0.0, 0.2, 0.4, 0.6])

    def test_only_the_selected_says_so_when_none_is(self):
        self.parts_at([(x, 0.0, 0.0) for x in range(3)])
        select_none()
        self.assertEqual(self.spread("DELAY", order="AXIS", axis="X", first=0.0,
                                     last=0.5, only_selected=True), {"CANCELLED"})
        self.assertIn("None of the parts", rig().rigmoves.report)
        self.assertEqual(self.delays(), [0.0, 0.0, 0.0])

    def test_the_report_counts_one_in_the_singular(self):
        self.parts_at([(0.0, 0.0, 0.0)])
        self.assertEqual(self.spread("DELAY", order="AXIS", axis="X", first=0.0,
                                     last=0.5), {"FINISHED"})
        self.assertIn("Delays of 1 part from", rig().rigmoves.report)
        self.assertNotIn("1 parts", rig().rigmoves.report)

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
        self.spread("LEAD", order="AROUND", first=0.0, last=30.0, only_selected=True)
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
        self.spread("DELAY", order="AXIS", axis="X", first=0.2, last=0.4,
                    only_selected=True)
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

    # -- by Step ------------------------------------------------------------

    def stepped(self, what, **kwargs):
        """The Spread as it comes: by Step, whatever the tests above asked."""
        return bpy.ops.rigmoves.spread(index=0, what=what, **kwargs)

    def test_by_step_is_what_a_spread_does_unless_told_otherwise(self):
        props = bpy.ops.rigmoves.spread.get_rna_type().properties
        self.assertEqual(props["by"].default, "STEP")
        self.assertEqual({item.identifier for item in props["by"].enum_items},
                         {"STEP", "RANGE"})
        self.assertIn("each waits more", props["step"].description)
        self.assertIn("each goes earlier", props["step"].description)

    def test_leads_step_ten_each_both_ways_round_eight_petals(self):
        # Eight on the ring, the leader one of them, so seven riders: the two
        # next to the leader are a step out, and the one opposite four.
        self.ring_of_riders(count=7, leader_on_ring=True)
        self.assertEqual(self.stepped("LEAD", order="AROUND", both_ways=True),
                         {"FINISHED"})
        self.assertEqual(self.leads(), [-10, -20, -30, -40, -30, -20, -10])
        self.assertIn("Spread the Leads of 7 riders in steps of -10 from 0, round the "
                      "ring from 'Leader', both ways.", rig().rigmoves.report)

    def test_leads_step_one_way_round_gives_every_rider_a_step_of_its_own(self):
        self.ring_of_riders(count=7, leader_on_ring=True)
        self.stepped("LEAD", order="AROUND", step=5.0)
        self.assertEqual(self.leads(), [5, 10, 15, 20, 25, 30, 35])

    def test_the_leader_is_rank_zero_so_start_is_added_to_the_riders_only(self):
        self.ring_of_riders(count=4)
        self.stepped("LEAD", order="AROUND", start=-5.0, step=-10.0)
        self.assertEqual(self.leads(), [-15, -25, -35, -45])
        self.assertEqual(self.move.parts["Leader"].lead, 0)

    def test_a_step_of_a_half_goes_outwards_to_the_next_lead(self):
        self.ring_of_riders(count=4)
        self.stepped("LEAD", order="AROUND", step=-2.5)
        self.assertEqual(self.leads(), [-3, -5, -8, -10])

    def test_delays_step_a_tenth_each_along_an_axis_by_default(self):
        objects = self.parts_at([(x, 0.0, 0.0) for x in range(5)])
        select(*objects)
        self.assertEqual(self.stepped("DELAY", order="AXIS", axis="X"), {"FINISHED"})
        self.assertEqual(self.delays(), [0.0, 0.1, 0.2, 0.3, 0.4])
        self.assertIn("in steps of 0.1 from 0", rig().rigmoves.report)

    def test_the_first_part_gets_the_start_and_each_next_one_a_step_more(self):
        objects = self.parts_at([(x, 0.0, 0.0) for x in range(4)])
        select(*objects)
        self.stepped("DELAY", order="AXIS", axis="X", start=0.2, step=0.15)
        self.assertEqual(self.delays(), [0.2, 0.35, 0.5, 0.65])

    def test_delays_sort_the_order_not_the_order_they_were_listed_in(self):
        objects = self.parts_at([(x, 0.0, 0.0) for x in (3, 0, 2, 1)])
        select(*objects)
        self.stepped("DELAY", order="AXIS", axis="X")
        self.assertEqual(self.delays(), [0.3, 0.0, 0.2, 0.1])

    def test_parts_at_the_same_place_along_an_axis_share_a_step(self):
        objects = self.parts_at([(x, 0.0, 0.0) for x in (0, 1, 1, 2)])
        select(*objects)
        self.stepped("DELAY", order="AXIS", axis="X")
        self.assertEqual(self.delays(), [0.0, 0.1, 0.1, 0.2])

    def test_a_hair_between_two_places_is_not_a_step(self):
        # Float rounding puts the two sides of a ring a hair apart.
        objects = self.parts_at([(x, 0.0, 0.0) for x in (0.0, 1.0, 1.0 + 1e-7, 2.0)])
        select(*objects)
        self.stepped("DELAY", order="AXIS", axis="X")
        self.assertEqual(self.delays(), [0.0, 0.1, 0.1, 0.2])
        self.assertEqual(rigmoves.tied_ranks([0.0, 1.0, 1.0 + 1e-7, 2.0, 0.5]),
                         [0, 2, 2, 3, 1])

    def test_distance_ties_parts_the_same_distance_from_the_active_one(self):
        objects = self.parts_at([(x, 0.0, 0.0) for x in (0, 1, -1, 2)])
        select(*objects)
        self.stepped("DELAY", order="DISTANCE")
        self.assertEqual(self.delays(), [0.0, 0.1, 0.1, 0.2])

    def test_delays_round_a_ring_both_ways_share_a_step_with_their_mirror(self):
        objects = self.parts_at(ring_places((0.0, 0.0, 0.0), 6, 3.0))
        select(*objects)
        self.stepped("DELAY", order="AROUND", both_ways=True)
        self.assertEqual(self.delays(), [0.0, 0.1, 0.2, 0.3, 0.2, 0.1])
        # One way round nobody shares.
        self.stepped("DELAY", order="AROUND")
        self.assertEqual(self.delays(), [0.0, 0.1, 0.2, 0.3, 0.4, 0.5])

    def test_down_a_chain_each_joint_is_a_step_deeper_and_branches_share(self):
        objects = self.parts_at([(x + 0.5, 0.0, 0.0) for x in range(4)])
        self.move.parts[1].follows = "P0"
        self.move.parts[2].follows = "P0"
        self.move.parts[3].follows = "P1"
        select(*objects)
        self.stepped("DELAY", order="CHAIN")
        self.assertEqual(self.delays(), [0.0, 0.1, 0.1, 0.2])

    def test_random_deals_out_the_steps_the_same_way_for_a_seed(self):
        objects = self.parts_at([(x, 0.0, 0.0) for x in range(6)])
        select(*objects)
        self.stepped("DELAY", order="RANDOM", seed=5)
        dealt = self.delays()
        self.assertEqual(sorted(dealt), [0.0, 0.1, 0.2, 0.3, 0.4, 0.5])
        self.stepped("DELAY", order="RANDOM", seed=5)
        self.assertEqual(self.delays(), dealt)
        self.stepped("DELAY", order="RANDOM", seed=6)
        self.assertNotEqual(self.delays(), dealt)

    def test_steps_past_what_a_lead_can_be_are_held_and_counted(self):
        self.ring_of_riders(count=4)
        self.stepped("LEAD", order="AROUND", step=-30.0)
        self.assertEqual(self.leads(), [-30, -50, -50, -50])
        self.assertIn("3 held at the limit", rig().rigmoves.report)

    def test_steps_past_what_a_delay_can_be_are_held_and_counted(self):
        objects = self.parts_at([(x, 0.0, 0.0) for x in range(4)])
        select(*objects)
        self.stepped("DELAY", order="AXIS", axis="X", step=0.5)
        self.assertEqual(self.delays(), [0.0, 0.5, 0.99, 0.99])
        self.assertIn("2 held at the limit", rig().rigmoves.report)

    def test_a_step_that_is_not_held_says_nothing_of_a_limit(self):
        self.ring_of_riders(count=4)
        self.stepped("LEAD", order="AROUND", step=-10.0)
        self.assertNotIn("limit", rig().rigmoves.report)

    def test_by_range_is_still_there_with_its_first_and_last(self):
        objects = self.parts_at([(x, 0.0, 0.0) for x in range(5)])
        select(*objects)
        self.stepped("DELAY", order="AXIS", axis="X", by="RANGE", first=0.0, last=0.8)
        self.assertEqual(self.delays(), [0.0, 0.2, 0.4, 0.6, 0.8])
        self.assertIn("from 0 to 0.8", rig().rigmoves.report)

    def test_a_step_spread_can_be_undone(self):
        objects = self.parts_at([(x, 0.0, 0.0) for x in range(3)])
        select(*objects)
        undo_push()
        self.stepped("DELAY", order="AXIS", axis="X")
        undo_push()
        self.assertEqual(self.delays(), [0.0, 0.1, 0.2])
        undo_once()
        self.assertEqual([round(p.start, 4) for p in rig().rigmoves.moves[0].parts],
                         [0.0, 0.0, 0.0])

    def test_the_dialog_shows_a_start_and_a_step_or_a_first_and_a_last(self):
        # What the dialog draws, run against a stand-in for its layout.
        for by, shown in (("STEP", ["Start Lead", "Lead step"]),
                          ("RANGE", ["First Lead", "Last Lead"])):
            texts = []

            class Column:
                def prop(self, _data, name, text=None, **_kwargs):
                    texts.append(text)

            class Layout(Sketch):
                def column(self, **_kwargs):
                    return Column()

            stand_in = types.SimpleNamespace(
                layout=Layout([]), order="AROUND", what="LEAD", by=by)
            rigmoves.RIGMOVES_OT_spread.draw(stand_in, bpy.context)
            self.assertEqual(texts, shown)

    # -- the step, sized to fit ---------------------------------------------

    def test_sized_steps_for_the_places_there_are(self):
        # Leads: -10, or less if the last place would pass 40 of the 50.
        self.assertEqual([rigmoves.sized_step("LEAD", top) for top in (1, 4, 7, 11, 40, 99)],
                         [-10.0, -10.0, -5.0, -3.0, -1.0, -1.0])
        # Delays: 0.1, or less if the last place would pass 0.9 of the 0.99.
        self.assertEqual([rigmoves.sized_step("DELAY", top) for top in (1, 4, 9, 13, 20, 500)],
                         [0.1, 0.1, 0.1, 0.06, 0.04, 0.01])

    def test_a_ring_of_twelve_spikes_gets_a_step_that_fits_not_a_wave_that_stops(self):
        # Eleven riders one way round: ten each ran past 50 from the sixth.
        self.ring_of_riders(count=11, leader_on_ring=True)
        self.stepped("LEAD", order="AROUND")
        self.assertEqual(self.leads(), [-3 * n for n in range(1, 12)])
        self.assertNotIn("limit", rig().rigmoves.report)
        self.assertIn("in steps of -3 from 0 (sized to fit)", rig().rigmoves.report)

    def test_the_two_sides_of_the_crown_together_need_a_step_of_six(self):
        self.ring_of_riders(count=11, leader_on_ring=True)
        self.stepped("LEAD", order="AROUND", both_ways=True)
        self.assertEqual(max(self.leads(), key=abs), -36)
        self.assertEqual(self.leads()[:6], [-6, -12, -18, -24, -30, -36])
        self.assertNotIn("limit", rig().rigmoves.report)

    def test_eight_petals_both_ways_keep_the_step_of_ten_and_say_nothing_of_sizing(self):
        self.ring_of_riders(count=7, leader_on_ring=True)
        self.stepped("LEAD", order="AROUND", both_ways=True)
        self.assertEqual(self.leads(), [-10, -20, -30, -40, -30, -20, -10])
        self.assertNotIn("sized", rig().rigmoves.report)

    def test_delays_for_fourteen_parts_are_sized_to_fit(self):
        objects = self.parts_at([(x, 0.0, 0.0) for x in range(14)])
        select(*objects)
        self.stepped("DELAY", order="AXIS", axis="X")
        self.assertEqual(self.delays(), [round(0.06 * n, 4) for n in range(14)])
        self.assertNotIn("limit", rig().rigmoves.report)
        self.assertIn("(sized to fit)", rig().rigmoves.report)

    def test_a_step_that_was_typed_is_kept_and_the_limit_still_reported(self):
        self.ring_of_riders(count=11, leader_on_ring=True)
        self.stepped("LEAD", order="AROUND", step=-10.0)
        self.assertEqual(self.leads(), [-10, -20, -30, -40] + [-50] * 7)
        self.assertIn("6 held at the limit", rig().rigmoves.report)
        self.assertNotIn("sized", rig().rigmoves.report)

    def test_the_dialog_opens_with_both_ways_on_for_leads_and_a_step_that_fits(self):
        self.ring_of_riders(count=11, leader_on_ring=True)
        stand_in = types.SimpleNamespace(
            index=0, what="LEAD", order="AROUND", axis="X", seed=1, only_selected=False,
            both_ways=False, start=0.0, step=0.0, first=0.0, last=0.0,
            properties=types.SimpleNamespace(is_property_set=lambda name: False),
            report=lambda *args: None)
        stand_in.plan = lambda context: rigmoves.RIGMOVES_OT_spread.plan(stand_in, context)
        stand_in.sized = lambda *args: rigmoves.RIGMOVES_OT_spread.sized(stand_in, *args)
        dialog = types.SimpleNamespace(
            window_manager=types.SimpleNamespace(invoke_props_dialog=lambda op: {"RUNNING_MODAL"}),
            scene=bpy.context.scene, view_layer=bpy.context.view_layer,
            selected_objects=bpy.context.selected_objects,
            selected_pose_bones=None)
        stand_in.plan = lambda context: rigmoves.RIGMOVES_OT_spread.plan(stand_in, bpy.context)
        self.assertEqual(rigmoves.RIGMOVES_OT_spread.invoke(stand_in, dialog, None),
                         {"RUNNING_MODAL"})
        self.assertTrue(stand_in.both_ways)
        self.assertEqual(stand_in.step, -6.0)
        # Said already, the choice is the user's.
        stand_in.properties = types.SimpleNamespace(is_property_set=lambda name: True)
        stand_in.both_ways, stand_in.step = False, -7.0
        rigmoves.RIGMOVES_OT_spread.invoke(stand_in, dialog, None)
        self.assertFalse(stand_in.both_ways)
        self.assertEqual(stand_in.step, -7.0)

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
            (("head:show_riders", "row"), "Spread…", "rigmoves.spread"),
            (("head:show_timing", "row"), "Spread…", "rigmoves.spread")]))

    def test_the_spread_buttons_take_only_their_own_width_in_the_headers(self):
        # Set straight in a header, the button and the label share it half and
        # half, and "Riding along (7)" was cut to "Riding alon…". In a row of
        # its own, aligned right, the button takes what it needs and the label
        # keeps the rest.
        self.ring_of_riders(count=4)
        log = drawn_panel()
        spread = sorted(where for where, kind, _text in log if kind == "rigmoves.spread")
        aligned = sorted(where for where, kind, text in log
                         if kind == "alignment" and text == "RIGHT")
        self.assertEqual(spread, [("head:show_riders", "row"), ("head:show_timing", "row")])
        self.assertEqual(aligned, spread)


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

    def test_a_chain_made_from_the_wrong_end_can_be_made_again(self):
        self.assertEqual(self.chain(first=4), {"FINISHED"})
        self.assertEqual(self.follows(),
                         {"Seg4": "", "Seg3": "Seg4", "Seg2": "Seg3", "Seg1": "Seg2"})
        # The first press left Seg1 following Seg2; from the other end that
        # would close a loop with the first link. The old links are replaced.
        self.assertEqual(self.chain(first=1), {"FINISHED"})
        self.assertEqual(self.follows(),
                         {"Seg1": "", "Seg2": "Seg1", "Seg3": "Seg2", "Seg4": "Seg3"})
        said = rig().rigmoves.report
        self.assertIn("Chain: Seg1 > Seg2 > Seg3 > Seg4", said)
        self.assertIn("Replaced: ", said)
        self.assertIn("Seg1 followed Seg2", said)
        self.assertEqual(self.segments[2].parent, self.segments[1])

    def test_a_built_chain_made_again_waits_for_one_build(self):
        bpy.ops.rigmoves.build()
        self.chain(first=4)
        bpy.ops.rigmoves.build()
        self.assertEqual(self.chain(first=1), {"FINISHED"})
        self.assertTrue(rigmoves.parent_pending(rig(), rig().rigmoves, self.move))
        bpy.ops.rigmoves.build()
        self.assertFalse(rigmoves.parent_pending(rig(), rig().rigmoves, self.move))
        bones = rig().data.bones
        for number in (2, 3, 4):
            part = self.move.parts["Seg{:d}".format(number)]
            ahead = self.move.parts["Seg{:d}".format(number - 1)]
            self.assertEqual(bones[part.bone_name].parent.name, ahead.bone_name)

    def test_a_chain_made_again_over_one_with_a_link_outside_keeps_that_link(self):
        # Seg1 follows a palm that is not among the chosen: that stays.
        palm = cube("Palm", (-2.0, 0.0, 0.0))
        select(palm, self.segments[1])
        bpy.ops.rigmoves.add_to_move(index=0, rig_name=rig().name)
        self.move.parts["Seg1"].follows = "Palm"
        self.assertEqual(self.chain(first=1), {"FINISHED"})
        self.assertEqual(self.follows()["Seg1"], "Palm")
        self.assertEqual(self.follows()["Seg2"], "Seg1")

    def test_a_chain_that_stops_leaves_the_parts_it_did_not_reach_as_they_were(self):
        # A lone rider of Seg1 stands between the second and third segments, so
        # the chain runs Seg1 > Seg2 and is turned down at the rider. Seg3 and
        # Seg4 were only cleared to make room for links that never came: they
        # keep theirs, and nothing is said to be replaced.
        self.chain()
        rider = cube("Rider", (2.0, 0.3, 0.0))
        rider.scale = (0.2, 0.2, 0.2)
        select(self.segments[1], rider)
        bpy.ops.rigmoves.ride_along(index=0, leader="Seg1", rig_name=rig().name)
        before = {n: f for n, f in self.follows().items() if n != "Rider"}
        select(self.segments[1], self.segments[2], self.segments[3], self.segments[4], rider)
        self.assertEqual(bpy.ops.rigmoves.make_chain(index=0), {"FINISHED"})
        said = rig().rigmoves.report
        self.assertIn("Chain: Seg1 > Seg2. Stopped there.", said)
        self.assertNotIn("Replaced", said)
        self.assertEqual({n: f for n, f in self.follows().items() if n != "Rider"}, before)
        self.assertEqual(self.segments[3].parent, self.segments[2])

    def test_a_chain_refused_at_its_first_link_puts_the_old_links_back(self):
        self.chain(first=4)
        before = self.follows()
        rider = cube("Rider", (0.7, 0.0, 0.0))
        select(self.segments[3], rider)
        bpy.ops.rigmoves.ride_along(index=0, leader="Seg4", rig_name=rig().name)
        select(self.segments[1], self.segments[2], self.segments[3], self.segments[4],
               rider)
        self.assertEqual(bpy.ops.rigmoves.make_chain(index=0), {"CANCELLED"})
        self.assertIn("riders copy their leader instead", rig().rigmoves.report)
        self.assertEqual({n: f for n, f in self.follows().items() if n != "Rider"}, before)

    def test_a_part_that_leads_riders_may_follow(self):
        # It used to be turned down: its riders would be left behind. They
        # hang from what it hangs from now, so it is chained like any other.
        rider = cube("Rider", (2.0, 4.0, 0.0))
        select(self.segments[2], rider)
        self.assertEqual(bpy.ops.rigmoves.ride_along(index=0, leader="Seg2",
                                                     rig_name=rig().name), {"FINISHED"})
        self.assertEqual(self.chain(), {"FINISHED"})
        self.assertEqual(self.follows()["Seg2"], "Seg1")
        self.assertNotIn("Stopped", rig().rigmoves.report)

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

    def check_places_of(self, numbers, places):
        """Only these segments, by their place in the list - the others have
        been deleted, and what is left of them is not an object any more."""
        for number in numbers:
            segment = bpy.data.objects["Seg{:d}".format(number + 1)]
            expected = [places[number] @ v.co for v in segment.data.vertices]
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
        self.assertIn("4 parts below 'Seg1' now bend 20 degrees like it",
                      rig().rigmoves.report)
        # Kept: recorded, built, and played.
        self.assertEqual(bpy.ops.rigmoves.record(index=0, which="AFTER"), {"FINISHED"})
        bpy.ops.rigmoves.build()
        self.play(1.0, 20.0)
        self.check_joints()
        self.play(0.5, 10.0)
        self.play(0.0, 0.0)
        self.check_places(self.homes)

    def test_loose_each_joint_keeps_a_share_of_the_one_before(self):
        self.pose_root(20.0)
        self.assertEqual(self.curl(factor=0.5), {"FINISHED"})
        # Each joint is half the one before it: 20 at the root, then 10, 5,
        # 2.5 and 1.25 down the four that follow.
        self.check_places(self.bent_by((20.0, 10.0, 5.0, 2.5, 1.25)))
        self.check_joints()
        self.assertIn("each joint x0.5 of the one before", rig().rigmoves.report)
        self.assertEqual(bpy.ops.rigmoves.record(index=0, which="AFTER"), {"FINISHED"})
        bpy.ops.rigmoves.build()
        drive(self.move, 1.0)
        self.check_places(self.bent_by((20.0, 10.0, 5.0, 2.5, 1.25)))

    def test_a_factor_above_one_bends_the_tip_most(self):
        self.pose_root(10.0)
        self.assertEqual(self.curl(factor=1.5), {"FINISHED"})
        self.check_places(self.bent_by((10.0, 15.0, 22.5, 33.75, 50.625)))
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

    def lose(self, number):
        """The object of this segment deleted, as in the viewport."""
        bpy.data.objects.remove(self.segments[number], do_unlink=True)
        bpy.context.view_layer.update()

    def test_a_lost_tip_is_left_out_and_the_rest_bend(self):
        self.lose(4)
        self.pose_root(20.0)
        self.assertEqual(self.curl(), {"FINISHED"})
        self.check_places_of(range(4), self.bent_by((20.0,) * 5))
        self.assertIn("1 left out: its object is gone", rig().rigmoves.report)
        self.assertIn("3 parts below", rig().rigmoves.report)

    def test_the_report_counts_one_in_the_singular(self):
        # Two segments in the chain: one part below the first, which bends.
        for number in ("Seg3", "Seg4", "Seg5"):
            self.move.parts[number].follows = ""
        self.pose_root(20.0)
        self.assertEqual(self.curl(), {"FINISHED"})
        self.assertIn("1 part below 'Seg1' now bends 20 degrees like it",
                      rig().rigmoves.report)

    def test_two_lost_tips_are_counted_in_the_plural(self):
        self.lose(4)
        self.lose(3)
        self.pose_root(20.0)
        self.assertEqual(self.curl(), {"FINISHED"})
        self.assertIn("(2 left out: their objects are gone)", rig().rigmoves.report)

    def test_a_lost_part_with_parts_below_it_is_a_refusal_and_nothing_moves(self):
        self.lose(2)
        self.pose_root(20.0)
        stood = {n: bpy.data.objects[n].matrix_world.copy() for n in ("Seg2", "Seg4", "Seg5")}
        self.assertEqual(self.curl(), {"CANCELLED"})
        self.assertIn("'Seg3' has lost its object", rig().rigmoves.report)
        for name, place in stood.items():
            self.assertTrue(rigmoves.same_matrix(bpy.data.objects[name].matrix_world,
                                                 place, 1e-6), name)

    def test_a_chain_lost_below_the_first_has_nothing_to_bend(self):
        for number in (1, 2, 3, 4):
            self.lose(number)
        self.pose_root(20.0)
        self.assertEqual(self.curl(), {"CANCELLED"})
        self.assertIn("Nothing is left to bend", rig().rigmoves.report)

    def test_a_curl_from_a_joint_whose_parent_is_lost_bends_from_where_it_is(self):
        self.lose(0)
        self.segments[1].matrix_world = turn_about(self.KNUCKLES[1], "Y", 20.0) @ self.homes[1]
        bpy.context.view_layer.update()
        select(self.segments[1])
        self.assertEqual(bpy.ops.rigmoves.curl(index=0), {"FINISHED"})
        # Nothing carries the second any more: its own bend and the ones below.
        places = self.bent_by((0.0,) * 5)
        carry = Matrix.Identity(4)
        for number in range(1, 5):
            carry = carry @ turn_about(self.KNUCKLES[number], "Y", 20.0)
            places[number] = carry @ self.homes[number]
        self.check_places_of(range(1, 5), places)

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
        for segment, place in zip(self.segments, self.bent_by((20.0, 10.0, 5.0, 2.5))):
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
        self.assertIn("4 parts below 'Palm'", rig().rigmoves.report)
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


class TestRing(CopyThatCase):
    """One blade on a hinge, made into a fan round a tilted 3D cursor."""

    def setUp(self):
        super().setUp()
        scene = bpy.context.scene
        self.centre = Vector((2.0, -1.0, 1.0))
        scene.cursor.location = self.centre
        scene.cursor.rotation_euler = (math.radians(30.0), math.radians(-20.0),
                                       math.radians(15.0))
        bpy.context.view_layer.update()
        self.axis = (scene.cursor.matrix.to_3x3() @ Vector((0.0, 0.0, 1.0))).normalized()
        self.assertGreater(abs(self.axis.x) + abs(self.axis.y), 0.3)   # not the world's Z
        self.blade = cube("Blade", self.centre + Vector((3.0, 0.0, 0.0)))
        self.blade.scale = (0.2, 1.0, 0.05)
        bpy.context.view_layer.update()
        self.home = self.blade.matrix_world.copy()
        # Hinged on its inner end, and flapped 50 degrees about it.
        self.hinge = self.home @ Vector((0.0, -0.5, 0.0))
        self.flap_axis = Vector((1.0, 0.0, 0.0))

        def pose():
            self.blade.matrix_world = self.flap(50.0) @ self.home

        record_move([self.blade], pose)
        scene.cursor.location = self.hinge
        select(self.blade)
        self.assertEqual(bpy.ops.rigmoves.set_pivot(index=0, kind="CURSOR"), {"FINISHED"})
        scene.cursor.location = self.centre
        self.move = rig().rigmoves.moves[0]

    def flap(self, degrees):
        return turn_about(self.hinge, self.flap_axis, degrees)

    def turned(self, number, count=6):
        """Where the part number `number` round a ring of `count` stands."""
        return turn_about(self.centre, self.axis, 360.0 * number / count)

    def ring(self, **kwargs):
        select(self.blade)
        # About the tilted cursor's own Z, as this fixture is built for.
        kwargs.setdefault("axis", "CURSOR_Z")
        return bpy.ops.rigmoves.ring(index=0, **kwargs)

    def copies(self):
        return [bpy.data.objects["Blade {:d}".format(n)] for n in range(2, 7)]

    def check_ring_at(self, flap_degrees, count=6):
        """Every blade in the ring, in the leader's pose of this much flap
        turned round to its own place."""
        for number in range(count):
            blade = self.blade if not number else self.copies()[number - 1]
            expected = [self.turned(number, count) @ self.flap(flap_degrees)
                        @ self.home @ v.co for v in blade.data.vertices]
            self.assertLess(drift(blade, expected), TOLERANCE, blade.name)

    # -- what it makes ------------------------------------------------------

    def test_copies_stand_round_the_cursor_at_the_rotated_before(self):
        # The blade is standing at its After: the ring is made from its Before.
        self.assertEqual(self.ring(count=6), {"FINISHED"})
        for number, copy in enumerate(self.copies(), start=1):
            expected = [self.turned(number) @ self.home @ v.co for v in copy.data.vertices]
            self.assertLess(max((a - b).length for a, b in zip(rest_points(copy), expected)),
                            TOLERANCE, copy.name)
        self.assertEqual(rig().rigmoves.report,
                         "5 copies of 'Blade' round the 3D cursor ride along with it.")

    def test_copies_share_the_mesh_and_carry_nothing_of_the_rig(self):
        self.ring(count=6)
        for copy in self.copies():
            self.assertIs(copy.data, self.blade.data)
            self.assertEqual(list(copy.modifiers), [])
            self.assertEqual(list(copy.vertex_groups), [])
            self.assertIsNone(copy.parent)
            self.assertIsNone(copy.get(rigmoves.FOLLOW_MARK))
        self.assertEqual(self.blade.data.users, 6)

    def test_copies_ride_along_with_it(self):
        self.ring(count=6)
        parts = rig().rigmoves.moves[0].parts
        self.assertEqual([p.leader for p in parts if p.name != "Blade"], ["Blade"] * 5)
        self.assertEqual([p.name for p in parts if p.leader],
                         ["Blade {:d}".format(n) for n in range(2, 7)])

    def test_the_blade_is_left_selected_and_active(self):
        self.ring(count=6)
        self.assertEqual(bpy.context.view_layer.objects.active, self.blade)
        self.assertEqual({o.name for o in bpy.context.selected_objects},
                         {"Blade"} | {"Blade {:d}".format(n) for n in range(2, 7)})

    def test_each_copy_makes_the_move_from_its_own_place(self):
        self.ring(count=6)
        bpy.ops.rigmoves.build()
        drive(self.move, 0.0)
        self.check_ring_at(0.0)
        drive(self.move, 0.5)
        self.check_ring_at(25.0)
        drive(self.move, 1.0)
        self.check_ring_at(50.0)

    def test_build_gives_each_part_a_mesh_and_a_group_of_its_own(self):
        self.ring(count=6)
        bpy.ops.rigmoves.build()
        everyone = [self.blade] + self.copies()
        self.assertEqual(len({o.data.name for o in everyone}), 6)
        for blade in everyone:
            self.assertEqual([g.name for g in blade.vertex_groups], [blade.name])
            self.assertEqual([m.object for m in blade.modifiers if m.type == "ARMATURE"],
                             [rig()])
            self.assertEqual(blade.parent, rig())

    def test_a_ring_on_a_built_move_builds_on_the_side(self):
        bpy.ops.rigmoves.build()
        self.assertEqual(self.ring(count=6), {"FINISHED"})
        # No Build since: the copies are bound, and play at once.
        for blade in self.copies():
            self.assertEqual([g.name for g in blade.vertex_groups], [blade.name])
            self.assertEqual(len([m for m in blade.modifiers if m.type == "ARMATURE"]), 1)
        self.assertEqual([g.name for g in self.blade.vertex_groups], ["Blade"])
        drive(self.move, 1.0)
        self.check_ring_at(50.0)
        drive(self.move, 0.0)
        self.check_ring_at(0.0)

    def test_unlinked_copies_have_meshes_of_their_own(self):
        self.ring(count=4, linked=False)
        for number in (2, 3, 4):
            copy = bpy.data.objects["Blade {:d}".format(number)]
            self.assertIsNot(copy.data, self.blade.data)
            self.assertEqual(len(copy.data.vertices), len(self.blade.data.vertices))
            self.assertEqual(copy.data.users, 1)

    def test_a_ring_round_the_world_origin_about_an_axis(self):
        self.assertEqual(self.ring(count=4, center="ORIGIN", axis="X"), {"FINISHED"})
        for number in (1, 2, 3):
            copy = bpy.data.objects["Blade {:d}".format(number + 1)]
            expected = [Matrix.Rotation(math.radians(90.0 * number), 4, "X") @ self.home
                        @ v.co for v in copy.data.vertices]
            self.assertLess(max((a - b).length for a, b in zip(rest_points(copy), expected)),
                            TOLERANCE, copy.name)
        self.assertIn("round the world origin", rig().rigmoves.report)

    def test_names_that_are_taken_are_made_unique(self):
        cube("Blade 2", (9.0, 9.0, 9.0))
        self.assertEqual(self.ring(count=3), {"FINISHED"})
        parts = rig().rigmoves.moves[0].parts
        riders = [p.name for p in parts if p.leader]
        self.assertEqual(len(riders), 2)
        self.assertNotIn("Blade 2", riders)

    def test_leads_are_spread_out_from_the_blade_both_ways(self):
        self.assertEqual(self.ring(count=6, lead_step=-10), {"FINISHED"})
        parts = rig().rigmoves.moves[0].parts
        self.assertEqual({p.name: p.lead for p in parts if p.leader},
                         {"Blade 2": -10, "Blade 3": -20, "Blade 4": -30,
                          "Blade 5": -20, "Blade 6": -10})
        self.assertIn("Leads step by -10", rig().rigmoves.report)

    def test_no_spread_of_leads_without_a_lead_step(self):
        self.ring(count=6, lead_step=0)
        parts = rig().rigmoves.moves[0].parts
        self.assertEqual({p.lead for p in parts if p.leader}, {0})

    # -- what it will not do, and leaves nothing behind ---------------------

    def stock(self):
        return (sorted(o.name for o in bpy.data.objects), sorted(m.name for m in bpy.data.meshes),
                len(rig().rigmoves.moves[0].parts))

    def test_an_unrecorded_drag_is_refused_and_nothing_is_made(self):
        bpy.ops.rigmoves.build()
        self.blade.location.z += 2.0
        bpy.context.view_layer.update()
        stock = self.stock()
        self.assertEqual(self.ring(count=6), {"CANCELLED"})
        self.assertIn("moved and not recorded", rig().rigmoves.report)
        self.assertEqual(self.stock(), stock)

    def test_only_a_part_that_can_lead_will_do(self):
        outsider = cube("Outsider", (9.0, 9.0, 0.0))
        stock = self.stock()
        select(outsider)
        self.assertEqual(bpy.ops.rigmoves.ring(index=0), {"CANCELLED"})
        self.assertIn("Select the part", rig().rigmoves.report)
        self.assertEqual(self.stock(), stock)
        # A rider, and a part that follows, cannot lead copies.
        other = cube("Other", (9.0, 5.0, 0.0))
        select(other, self.blade)
        bpy.ops.rigmoves.ride_along(index=0, leader="Blade", rig_name=rig().name)
        stock = self.stock()
        select(other)
        self.assertEqual(bpy.ops.rigmoves.ring(index=0), {"CANCELLED"})
        self.assertIn("rides along with 'Blade'", rig().rigmoves.report)
        self.assertEqual(self.stock(), stock)

    def test_the_ring_is_flat_by_default_even_with_the_cursor_tilted(self):
        # Shift+right-click turns the cursor to face the view: the default is
        # the world's up, and the cursor's own Z is a choice.
        select(self.blade)
        self.assertEqual(bpy.ops.rigmoves.ring(index=0, count=6), {"FINISHED"})
        for copy in self.copies():
            self.assertAlmostEqual(copy.matrix_world.translation.z,
                                   self.home.translation.z, places=4)

    def test_a_second_ring_adds_only_the_places_that_are_missing(self):
        self.assertEqual(self.ring(count=4), {"FINISHED"})
        self.assertEqual(self.ring(count=8), {"FINISHED"})
        riders = [p.name for p in self.move.parts if p.leader]
        self.assertEqual(len(riders), 7)
        places = [bpy.data.objects[n].matrix_world.translation.copy() for n in riders]
        places.append(self.home.translation.copy())
        for number, here in enumerate(places):
            for there in places[number + 1:]:
                self.assertGreater((here - there).length, 0.1)
        said = rig().rigmoves.report
        self.assertIn("4 copies of 'Blade'", said)
        self.assertIn("3 places already held a copy and were skipped", said)

    def test_the_report_counts_one_copy_in_the_singular(self):
        self.assertEqual(self.ring(count=2), {"FINISHED"})
        self.assertEqual(rig().rigmoves.report,
                         "1 copy of 'Blade' round the 3D cursor rides along with it.")
        # And a ring that finds one place held says so in the singular.
        self.assertEqual(self.ring(count=4), {"FINISHED"})
        self.assertIn("1 place already held a copy and was skipped", rig().rigmoves.report)
        self.assertIn("2 copies of 'Blade'", rig().rigmoves.report)

    def test_the_same_ring_again_is_refused_and_leaves_nothing(self):
        self.ring(count=4)
        stock = self.stock()
        self.assertEqual(self.ring(count=4), {"CANCELLED"})
        self.assertIn("nothing to add", rig().rigmoves.report)
        self.assertEqual(self.stock(), stock)

    def test_a_second_ring_leaves_the_leads_of_the_first_alone(self):
        self.ring(count=4, lead_step=-15)
        self.move.parts["Blade 2"].lead = 7
        self.assertEqual(self.ring(count=8, lead_step=-20), {"FINISHED"})
        leads = {p.name: p.lead for p in self.move.parts if p.leader}
        self.assertEqual((leads["Blade 2"], leads["Blade 3"], leads["Blade 4"]), (7, -30, -15))
        new = sorted(v for n, v in leads.items() if n not in ("Blade 2", "Blade 3", "Blade 4"))
        self.assertEqual(new, [-40, -40, -20, -20])

    def test_a_ring_made_again_after_the_copies_were_deleted_is_all_new(self):
        # The parts of deleted copies stay in the move; a new copy that took
        # one's name was never bound, and stood at the old place for good.
        bpy.ops.rigmoves.build()
        self.assertEqual(self.ring(count=4), {"FINISHED"})
        for number in (2, 3, 4):
            bpy.data.objects.remove(bpy.data.objects["Blade {:d}".format(number)],
                                    do_unlink=True)
        self.assertEqual(self.ring(count=6), {"FINISHED"})
        news = {"Blade {:d}".format(n): n - 4 for n in range(5, 10)}
        self.assertEqual({p.name for p in self.move.parts if p.leader and p.name in news},
                         set(news))
        drive(self.move, 1.0)
        leader_points = world_points(self.blade)
        for name, number in news.items():
            copy = bpy.data.objects[name]
            self.assertEqual(len([m for m in copy.modifiers if m.type == "ARMATURE"]), 1, name)
            turn = self.turned(number, 6)
            self.assertLess(max((a - turn @ b).length
                                for a, b in zip(world_points(copy), leader_points)),
                            TOLERANCE, name)

    def hide_the_last_copy_from_ride_along(self, **kwargs):
        was = rigmoves.newcomers
        rigmoves.newcomers = lambda context, rig_: was(context, rig_)[:-1]
        try:
            return self.ring(**kwargs)
        finally:
            rigmoves.newcomers = was

    def test_a_copy_that_is_not_taken_up_takes_the_whole_ring_back(self):
        stock = self.stock()
        self.assertEqual(self.hide_the_last_copy_from_ride_along(count=4), {"CANCELLED"})
        self.assertIn("none were kept", rig().rigmoves.report)
        self.assertEqual(self.stock(), stock)

    def test_the_same_on_a_built_move_leaves_the_rig_as_it_was(self):
        bpy.ops.rigmoves.build()
        stock = self.stock()
        bones = sorted(b.name for b in rig().data.bones)
        constraints = sum(len(pb.constraints) for pb in rig().pose.bones)
        self.assertEqual(self.hide_the_last_copy_from_ride_along(count=4), {"CANCELLED"})
        self.assertEqual(self.stock(), stock)
        self.assertEqual(sorted(b.name for b in rig().data.bones), bones)
        self.assertEqual(sum(len(pb.constraints) for pb in rig().pose.bones), constraints)
        drive(self.move, 1.0)
        self.assertLess(drift(self.blade, rest_points(self.blade)), 5.0)
        self.check_ring_at(50.0, count=1)

    def test_a_ring_can_be_undone(self):
        select(self.blade)
        stock = self.stock()
        undo_push()
        bpy.ops.rigmoves.ring(index=0, count=6)
        undo_push()
        self.assertEqual(len(bpy.data.objects), len(stock[0]) + 5)
        undo_once()
        self.assertEqual(self.stock(), stock)
        self.assertIsNone(bpy.data.objects.get("Blade 2"))

    def test_a_ring_on_a_built_move_can_be_undone(self):
        bpy.ops.rigmoves.build()
        select(self.blade)
        stock = self.stock()
        undo_push()
        bpy.ops.rigmoves.ring(index=0, count=6)
        undo_push()
        undo_once()
        self.assertEqual(self.stock(), stock)
        self.assertEqual([g.name for g in bpy.data.objects["Blade"].vertex_groups], ["Blade"])

    def test_the_button_is_in_the_moves_body(self):
        found = [(where, text) for where, idname, text in drawn_buttons()
                 if idname == "rigmoves.ring"]
        self.assertEqual(found, [(("body:expanded", "row"), "Ring…")])


class TestRingAroundAFarHub(CopyThatCase):
    """Blades pivoting on a hub a long way from the world's origin: the pivots
    carried over to each blade are one point, a hair apart from float rounding,
    which grows with the distance."""

    def test_leads_come_out_even_whatever_the_distance_from_the_origin(self):
        for hub, rotation in (((60.0, 25.0, 0.0), (0.0, 0.0, 0.0)),
                              ((37.3, -21.7, 12.9), (0.5, -0.3, 0.2))):
            with self.subTest(hub=hub):
                bpy.ops.wm.read_factory_settings(use_empty=True)
                scene = bpy.context.scene
                hub = Vector(hub)
                scene.cursor.location = hub
                scene.cursor.rotation_euler = rotation
                bpy.context.view_layer.update()
                axis = (scene.cursor.matrix.to_3x3() @ Vector((0.0, 0.0, 1.0))).normalized()
                side = axis.orthogonal().normalized()
                blade = cube("Blade", hub + side * 3.0)
                blade.scale = (0.3, 0.3, 1.0)
                bpy.context.view_layer.update()
                select(blade)
                bpy.ops.rigmoves.new_move()
                blade.matrix_world = (turn_about(hub + side, axis.cross(side), 40.0)
                                      @ blade.matrix_world)
                bpy.context.view_layer.update()
                bpy.ops.rigmoves.record(index=0, which="AFTER")
                select(blade)
                bpy.ops.rigmoves.set_pivot(index=0, kind="CURSOR")
                bpy.ops.rigmoves.build()
                select(blade)
                self.assertEqual(bpy.ops.rigmoves.ring(index=0, count=12, axis="CURSOR_Z",
                                                       lead_step=5),
                                 {"FINISHED"})
                leads = {p.name: p.lead for p in rig().rigmoves.moves[0].parts if p.leader}
                self.assertEqual([leads["Blade {:d}".format(n)] for n in range(2, 13)],
                                 [5, 10, 15, 20, 25, 30, 25, 20, 15, 10, 5])


class TestRingABladeOnAHub(CopyThatCase):
    """A fan made the usual way: the blade follows the hub, which has a spin of
    its own, and the blade a flap of its own. The blade is ringed and the hub
    never is; each copy hangs from what the blade hangs from."""

    def setUp(self):
        super().setUp()
        scene = bpy.context.scene
        self.centre = Vector((0.0, 0.0, 1.0))
        self.hub = cube("Hub", self.centre)
        self.hub.scale = (0.5, 0.5, 0.1)
        self.blade = cube("Blade", (1.5, 0.0, 1.0))
        self.blade.scale = (1.5, 0.3, 0.04)
        bpy.context.view_layer.update()
        self.hub_home = self.hub.matrix_world.copy()
        self.blade_home = self.blade.matrix_world.copy()
        self.hinge = Vector((0.75, 0.0, 1.0))
        select(self.hub, self.blade)
        bpy.ops.rigmoves.new_move()
        self.move = rig().rigmoves.moves[0]
        self.move.parts["Blade"].follows = "Hub"
        scene.cursor.location = self.hinge
        select(self.blade)
        bpy.ops.rigmoves.set_pivot(index=0, kind="CURSOR")
        scene.cursor.location = self.centre
        # The hub spins 72 degrees and the blade, on top of being carried by
        # it, flaps 50 about its hinge.
        self.hub.matrix_world = self.spin(72.0) @ self.hub_home
        bpy.context.view_layer.update()
        self.blade.matrix_world = self.spin(72.0) @ self.flap(50.0) @ self.blade_home
        bpy.context.view_layer.update()
        self.assertEqual(bpy.ops.rigmoves.record(index=0, which="AFTER"), {"FINISHED"})
        bpy.ops.rigmoves.build()

    def spin(self, degrees):
        return turn_about(self.centre, "Z", degrees)

    def flap(self, degrees):
        return turn_about(self.hinge, "Y", degrees)

    def ring(self):
        select(self.blade)
        return bpy.ops.rigmoves.ring(index=0, count=5)

    def test_the_blade_is_ringed_the_hub_is_not_and_the_copies_hang_from_the_hub(self):
        self.assertEqual(self.ring(), {"FINISHED"})
        self.assertIsNone(bpy.data.objects.get("Hub 2"))
        riders = [p for p in self.move.parts if p.leader]
        self.assertEqual(len(riders), 4)
        self.assertEqual({p.leader for p in riders}, {"Blade"})
        bones = rig().data.bones
        for rider in riders:
            self.assertEqual(bones[rider.bone_name].parent.name,
                             self.move.parts["Hub"].bone_name, rider.name)
        self.assertEqual(self.move.parts["Blade"].follows, "Hub")

    def test_every_blade_is_carried_by_the_hub_and_flaps_from_its_own_place(self):
        self.assertEqual(self.ring(), {"FINISHED"})
        for share in (0.0, 0.5, 1.0):
            drive(self.move, share)
            carried = (self.spin(eased(72.0, share)) @ self.flap(eased(50.0, share))
                       @ self.blade_home)
            for number in range(5):
                blade = self.blade if not number else bpy.data.objects[
                    "Blade {:d}".format(number + 1)]
                turn = turn_about(self.centre, "Z", 72.0 * number)
                # Round the hub, carried by it: the same as the recorded blade
                # turned to where it stands - not a flap alone.
                expected = [turn @ carried @ self.blade_home.inverted() @ self.blade_home
                            @ v.co for v in blade.data.vertices]
                self.assertLess(drift(blade, expected), TOLERANCE,
                                "{:s} at {:g}".format(blade.name, share))


class TestMirrorARolledFinger(CopyThatCase):
    """A copied finger mirrors across one plane, the first joint's, whichever
    way its segments are rolled about their own length: a cube looks the same
    rolled, but its own axes are not the finger's."""

    KNUCKLES = [Vector((float(n), 0.0, 0.0)) for n in range(3)]
    BESIDE = Matrix.Translation((0.0, 3.0, 0.0))
    ACROSS = Matrix.Diagonal((1.0, 1.0, -1.0, 1.0))

    def finger(self, prefix, where, roll):
        segments = []
        for number in range(3):
            segment = cube("{:s}{:d}".format(prefix, number + 1), (number + 0.5, 0.0, 0.0))
            segment.scale = (1.0, 0.3, 0.3)
            segments.append(segment)
        bpy.context.view_layer.update()
        segments[1].matrix_world = (segments[1].matrix_world
                                    @ Matrix.Rotation(math.radians(roll), 4, "X"))
        bpy.context.view_layer.update()
        for segment in segments:
            segment.matrix_world = where @ segment.matrix_world
        bpy.context.view_layer.update()
        return segments

    def bent(self, degrees):
        out, carry = [], Matrix.Identity(4)
        for knuckle, home in zip(self.KNUCKLES, self.homes):
            carry = carry @ turn_about(knuckle, "Y", degrees)
            out.append(carry @ home)
        return out

    def made(self, roll):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        self.segments = self.finger("Seg", Matrix.Identity(4), roll)
        self.homes = [s.matrix_world.copy() for s in self.segments]
        select(*self.segments)
        bpy.ops.rigmoves.new_move()
        self.move = rig().rigmoves.moves[0]
        for segment, knuckle in zip(self.segments, self.KNUCKLES):
            bpy.context.scene.cursor.location = knuckle
            select(segment)
            bpy.ops.rigmoves.set_pivot(index=0, kind="CURSOR")
        self.move.parts["Seg2"].follows = "Seg1"
        self.move.parts["Seg3"].follows = "Seg2"
        for segment, place in zip(self.segments, self.bent(30.0)):
            segment.matrix_world = place
            bpy.context.view_layer.update()
        bpy.ops.rigmoves.record(index=0, which="AFTER")
        bpy.ops.rigmoves.build()
        self.copy = self.finger("Copy", self.BESIDE, roll)
        select(self.segments[0], *self.copy)
        bpy.context.view_layer.objects.active = self.segments[0]
        self.assertEqual(bpy.ops.rigmoves.ride_along(index=0, leader="Seg1",
                                                     rig_name=rig().name), {"FINISHED"})

    def check_copy(self, mirrored, share, roll):
        """The copy moves as the finger does, or as its reflection does: its
        own deformation is the finger's reflected across the plane of the first
        joint. Where a rolled cube looks the same reflected - 0 and 90 degrees -
        its mesh is also the reflected finger's, as a set of points: the
        vertices are numbered another way round."""
        drive(self.move, share)
        for number, obj in enumerate(self.copy):
            moved = self.bent(30.0 * share)[number] @ self.homes[number].inverted()
            if mirrored:
                moved = self.ACROSS @ moved @ self.ACROSS
            moved = self.BESIDE @ moved @ self.BESIDE.inverted()
            stands = self.BESIDE @ self.homes[number]
            expected = [moved @ stands @ v.co for v in obj.data.vertices]
            label = "{:s} at {:g}, rolled {:g}".format(obj.name, share, roll)
            self.assertLess(drift(obj, expected), TOLERANCE, label)
            if mirrored and roll in (0.0, 90.0):
                place = self.bent(30.0 * share)[number]
                reflected = [self.BESIDE @ self.ACROSS @ place @ self.ACROSS @ v.co
                             for v in obj.data.vertices]
                actual = world_points(obj)
                for point in reflected:
                    self.assertLess(min((point - other).length for other in actual),
                                    TOLERANCE, label)

    def test_a_mirrored_copy_is_the_reflection_of_the_finger_however_its_segments_roll(self):
        for roll in (0.0, 90.0, 35.0):
            with self.subTest(roll=roll):
                self.made(roll)
                for share in (0.5, 1.0):
                    self.check_copy(False, share, roll)
                self.assertEqual(bpy.ops.rigmoves.set_mirror(
                    index=0, part=self.move.parts.find("Copy1"), axis="Z"), {"FINISHED"})
                for share in (0.0, 0.5, 1.0):
                    self.check_copy(True, share, roll)


class TestLinkedParts(CopyThatCase):
    """Two parts that are linked duplicates share one mesh, and so its groups."""

    def test_linked_duplicates_each_land_on_their_own_after(self):
        one = cube("One", (0.0, 0.0, 0.0))
        two = one.copy()
        bpy.context.collection.objects.link(two)
        two.name = "Two"
        two.location = (5.0, 0.0, 0.0)
        bpy.context.view_layer.update()
        self.assertIs(one.data, two.data)
        select(one, two)
        bpy.ops.rigmoves.new_move()
        one.location.z += 1.0
        two.location.z += 3.0
        bpy.context.view_layer.update()
        after = {o.name: rest_points(o) for o in (one, two)}
        bpy.ops.rigmoves.record(index=0, which="AFTER")
        bpy.ops.rigmoves.build()
        drive(rig().rigmoves.moves[0], 1.0)
        self.assertLess(drift(one, after["One"]), TOLERANCE)
        self.assertLess(drift(two, after["Two"]), TOLERANCE)
        self.assertIsNot(one.data, two.data)

    def share_as_0_15_left_them(self, objects, names):
        """The state 0.15 left Alt+D copies in once they were bound: one mesh,
        and on it a full-weight group for the bone of every one of them."""
        for obj in objects[1:]:
            obj.data = objects[0].data
        for name in names:
            group = objects[0].vertex_groups.get(name) or objects[0].vertex_groups.new(name=name)
            group.add(range(len(objects[0].data.vertices)), 1.0, "REPLACE")

    def test_a_build_gives_linked_duplicates_bound_long_ago_meshes_of_their_own(self):
        one, two = cube("One", (0.0, 0.0, 0.0)), cube("Two", (5.0, 0.0, 0.0))
        select(one, two)
        bpy.ops.rigmoves.new_move()
        one.location.z += 1.0
        two.location.y += 2.0
        bpy.context.view_layer.update()
        after = {o.name: rest_points(o) for o in (one, two)}
        bpy.ops.rigmoves.record(index=0, which="AFTER")
        bpy.ops.rigmoves.build()
        move = rig().rigmoves.moves[0]
        self.share_as_0_15_left_them([one, two], ["One", "Two"])
        # As the file plays in 0.15: each pulled by both bones.
        drive(move, 1.0)
        self.assertGreater(drift(one, after["One"]), 0.1)
        bpy.ops.rigmoves.build()
        drive(move, 1.0)
        self.assertLess(drift(one, after["One"]), TOLERANCE)
        self.assertLess(drift(two, after["Two"]), TOLERANCE)
        self.assertIsNot(one.data, two.data)
        self.assertEqual([g.name for g in one.vertex_groups], ["One"])
        self.assertEqual([g.name for g in two.vertex_groups], ["Two"])

    def test_a_build_heals_a_flower_of_linked_petals_bound_long_ago(self):
        # Each petal faces its own way, so each bone moves it differently: with
        # every bone pulling every petal, none of them goes where it should.
        petal = cube("Petal", (0.0, 0.0, 0.0))
        select(petal)
        bpy.ops.rigmoves.new_move()
        petal.location += Vector((1.0, 0.0, 1.0))
        bpy.context.view_layer.update()
        bpy.ops.rigmoves.record(index=0, which="AFTER")
        riders = []
        for number in range(1, 4):
            rider = cube("R{:d}".format(number), (3.0 * number, 0.0, 0.0))
            rider.rotation_euler.z = math.radians(90.0 * number)
            bpy.context.view_layer.update()
            select(petal, rider)
            bpy.ops.rigmoves.ride_along(index=0, leader="Petal", rig_name=rig().name)
            riders.append(rider)
        bpy.ops.rigmoves.build()
        move = rig().rigmoves.moves[0]
        petals = [petal] + riders
        self.share_as_0_15_left_them(petals, [o.name for o in petals])
        rest = {o.name: rest_points(o) for o in petals}

        def moved(obj, turn):
            by = Matrix.Rotation(math.radians(turn), 3, "Z") @ Vector((1.0, 0.0, 1.0))
            return [p + by for p in rest[obj.name]]

        turns = {o.name: 90.0 * n for n, o in enumerate(petals)}
        drive(move, 1.0)
        self.assertGreater(max(drift(o, moved(o, turns[o.name])) for o in petals), 0.1)
        bpy.ops.rigmoves.build()
        drive(move, 1.0)
        for obj in petals:
            self.assertLess(drift(obj, moved(obj, turns[obj.name])), TOLERANCE, obj.name)
            self.assertEqual([g.name for g in obj.vertex_groups], [obj.name])
        self.assertEqual(len({o.data.name for o in petals}), 4)


def select_none():
    for obj in bpy.context.view_layer.objects:
        obj.select_set(False)


def eased(degrees, progress):
    """How far a turn of this many degrees has got when its bone is this far
    along its path. A pose is keyed as a quaternion and blended straight
    between the keys, so the angle is not even along the way: it is what the
    share says only at the two ends and the middle, which is where the other
    tests look. Anywhere else this is the angle Blender really shows."""
    half = math.radians(degrees) / 2.0
    return math.degrees(2.0 * math.atan2(progress * math.sin(half),
                                         1.0 - progress + progress * math.cos(half)))


class TestEndToEnd(CopyThatCase):
    """Three different models, each made with the new tools and checked by
    where the deformed meshes really are."""

    def meshes_match(self, pairs, label=""):
        """Each (object, expected world matrix) lands where it should."""
        for obj, place in pairs:
            expected = [place @ v.co for v in obj.data.vertices]
            self.assertLess(drift(obj, expected), TOLERANCE, "{:s} {:s}".format(obj.name, label))

    def test_every_new_tool_is_one_undo_step(self):
        for name in ("spread", "make_chain", "curl", "ring"):
            operator = getattr(rigmoves, "RIGMOVES_OT_{:s}".format(name))
            self.assertTrue({"REGISTER", "UNDO"} <= set(operator.bl_options), name)
            self.assertEqual(operator.bl_idname, "rigmoves." + name)

    def test_a_fan_from_one_blade(self):
        # One blade that sweeps open about a hinge on its inner end. Ring it
        # eight times round the hub, the Leads spread out from it both ways
        # round, and the fan opens from the blade outwards.
        blade = cube("Blade", (2.0, 0.0, 0.0))
        blade.scale = (1.2, 0.3, 0.04)
        bpy.context.view_layer.update()
        home = blade.matrix_world.copy()
        hinge = Vector((1.4, 0.0, 0.0))

        def sweep(degrees):
            return turn_about(hinge, "Z", degrees)

        record_move([blade], lambda: setattr(blade, "matrix_world", sweep(60.0) @ home))
        bpy.context.scene.cursor.location = hinge
        select(blade)
        self.assertEqual(bpy.ops.rigmoves.set_pivot(index=0, kind="CURSOR"), {"FINISHED"})
        bpy.context.scene.cursor.location = (0.0, 0.0, 0.0)
        select(blade)
        self.assertEqual(bpy.ops.rigmoves.ring(index=0, count=8, lead_step=-10),
                         {"FINISHED"})
        bpy.ops.rigmoves.build()
        move = rig().rigmoves.moves[0]
        leads = {p.name: p.lead for p in move.parts if p.leader}
        self.assertEqual([leads["Blade {:d}".format(n)] for n in range(2, 9)],
                         [-10, -20, -30, -40, -30, -20, -10])
        # Behind by a fifth of a leader per ten points of Lead: on a control
        # that now runs 1.8 leaders long, each blade's own share is its
        # progress on the leader's, less its lead.
        waits = [0.0] + [-leads["Blade {:d}".format(n)] / 50.0 for n in range(2, 9)]
        blades = [blade] + [bpy.data.objects["Blade {:d}".format(n)] for n in range(2, 9)]
        for share in (0.0, 0.3, 0.5, 0.8, 1.0):
            drive(move, share)
            pairs = []
            for number, (obj, wait) in enumerate(zip(blades, waits)):
                progress = min(1.0, max(0.0, 1.8 * share - wait))
                turn = turn_about((0.0, 0.0, 0.0), "Z", 45.0 * number)
                pairs.append((obj, turn @ sweep(eased(60.0, progress)) @ home))
            self.meshes_match(pairs, "at {:g}".format(share))

    def test_dominoes_topple_in_a_wave(self):
        # A standing domino that topples forward about its front foot, and
        # six more along the row riding with it - made in no order - then
        # Spread along X, so each goes over a little after the last.
        def domino(name, x):
            obj = cube(name, (x, 0.0, 1.0))
            obj.scale = (0.2, 1.0, 2.0)
            return obj

        lead = domino("Lead", 0.0)
        riders = {x: domino("D{:d}".format(i), x)
                  for i, x in ((4, 6.0), (1, 1.5), (6, 9.0), (2, 3.0), (5, 7.5), (3, 4.5))}
        bpy.context.view_layer.update()
        home = {o.name: o.matrix_world.copy() for o in [lead] + list(riders.values())}

        def foot(x):
            return Vector((x + 0.1, 0.0, 0.0))

        def topple(x, degrees):
            return turn_about(foot(x), "Y", degrees)

        record_move([lead], lambda: setattr(lead, "matrix_world",
                                            topple(0.0, 90.0) @ home["Lead"]))
        bpy.context.scene.cursor.location = foot(0.0)
        select(lead)
        bpy.ops.rigmoves.set_pivot(index=0, kind="CURSOR")
        select(lead, *riders.values())
        self.assertEqual(bpy.ops.rigmoves.ride_along(index=0, leader="Lead",
                                                     rig_name=rig().name), {"FINISHED"})
        select(lead)
        self.assertEqual(bpy.ops.rigmoves.spread(index=0, what="LEAD", order="AXIS",
                                                 axis="X", by="RANGE",
                                                 first=-10.0, last=-50.0),
                         {"FINISHED"})
        move = rig().rigmoves.moves[0]
        by_place = [move.parts[riders[x].name].lead for x in sorted(riders)]
        self.assertEqual(by_place, [-10, -18, -26, -34, -42, -50])
        bpy.ops.rigmoves.build()
        waits = {x: -move.parts[riders[x].name].lead / 50.0 for x in riders}
        for share in (0.0, 0.25, 0.5, 0.75, 1.0):
            drive(move, share)
            # The control runs two leaders long: the last domino waits for
            # the first to finish, so each one's share is 2 x share less its wait.
            pairs = [(lead, topple(0.0, eased(90.0, min(1.0, 2.0 * share))) @ home["Lead"])]
            for x, obj in riders.items():
                progress = min(1.0, max(0.0, 2.0 * share - waits[x]))
                pairs.append((obj, topple(x, eased(90.0, progress)) @ home[obj.name]))
            self.meshes_match(pairs, "at {:g}".format(share))
        # Half way: the leader is down, and the rest are further over the
        # nearer they are - a wave along the row.
        drive(move, 0.5)
        tops = [centre(riders[x]).x for x in sorted(riders)]
        self.assertEqual(tops, sorted(tops))

    def test_a_tentacle_from_a_chain_a_curl_and_a_delay(self):
        # Five segments made in no order. Make Chain strings them together,
        # one turn of the first joint is Curl'd down the rest (tapering), and
        # Spread gives each joint further down a longer Delay.
        segments = {}
        for number in (4, 1, 5, 3, 2):
            seg = cube("Seg{:d}".format(number), (number - 0.5, 0.0, 0.0))
            seg.scale = (1.0, 0.3, 0.3)
            segments[number] = seg
        bpy.context.view_layer.update()
        homes = {n: o.matrix_world.copy() for n, o in segments.items()}
        select(*segments.values())
        bpy.ops.rigmoves.new_move()
        move = rig().rigmoves.moves[0]
        for number, seg in segments.items():
            bpy.context.scene.cursor.location = (number - 1.0, 0.0, 0.0)
            select(seg)
            bpy.ops.rigmoves.set_pivot(index=0, kind="CURSOR")
        select(segments[1], *[o for n, o in segments.items() if n != 1])
        self.assertEqual(bpy.ops.rigmoves.make_chain(index=0), {"FINISHED"})

        def bends(angles, shares=(1.0,) * 5):
            out, carry = {}, Matrix.Identity(4)
            for number, (degrees, share) in enumerate(zip(angles, shares), start=1):
                carry = carry @ turn_about((number - 1.0, 0.0, 0.0), "Y", eased(degrees, share))
                out[number] = carry @ homes[number]
            return out

        angles = (20.0, 10.0, 5.0, 2.5, 1.25)
        segments[1].matrix_world = bends((20.0,))[1]
        bpy.context.view_layer.update()
        select(segments[1])
        self.assertEqual(bpy.ops.rigmoves.curl(index=0, factor=0.5), {"FINISHED"})
        self.meshes_match([(segments[n], p) for n, p in bends(angles).items()], "curled")
        self.assertEqual(bpy.ops.rigmoves.record(index=0, which="AFTER"), {"FINISHED"})
        bpy.ops.rigmoves.build()
        select(*segments.values())
        self.assertEqual(bpy.ops.rigmoves.spread(index=0, what="DELAY", order="CHAIN",
                                                 by="RANGE", first=0.0, last=0.4),
                         {"FINISHED"})
        delays = [round(move.parts["Seg{:d}".format(n)].start, 4) for n in range(1, 6)]
        self.assertEqual(delays, [0.0, 0.1, 0.2, 0.3, 0.4])
        for share in (0.0, 0.5, 1.0):
            drive(move, share)
            # Each joint waits its own delay, then runs to the end; the ones
            # before it carry it as far as they have got.
            progress = [min(1.0, max(0.0, (share - d) / (1.0 - d))) for d in delays]
            self.meshes_match([(segments[n], p) for n, p in bends(angles, progress).items()],
                              "at {:g}".format(share))
class TestChainRiders(CopyThatCase):
    """Fingers copied from a recorded one, riding along with it joint for joint.

    The recorded finger tapers like a real one, each segment shorter than
    the one before, and curls 30 degrees at every knuckle. Each copy is placed
    by a matrix of its own - moved, turned or mirrored - so a joint matched to
    the wrong segment, or a copy played in the wrong frame, cannot pass.
    """

    LENGTHS = (1.0, 0.8, 0.6)
    KNUCKLES = (Vector((0.0, 0.0, 0.0)), Vector((1.0, 0.0, 0.0)), Vector((1.8, 0.0, 0.0)))
    BESIDE = Matrix.Translation((0.0, 3.0, 0.0))

    def setUp(self):
        super().setUp()
        self.finger = self.made("Seg", Matrix())
        self.homes = [s.matrix_world.copy() for s in self.finger]
        select(*self.finger)
        self.assertEqual(bpy.ops.rigmoves.new_move(), {"FINISHED"})
        self.move = rig().rigmoves.moves[0]
        for segment, knuckle in zip(self.finger, self.KNUCKLES):
            bpy.context.scene.cursor.location = knuckle
            select(segment)
            bpy.ops.rigmoves.set_pivot(index=0, kind="CURSOR")
        self.move.parts["Seg2"].follows = "Seg1"
        self.move.parts["Seg3"].follows = "Seg2"
        for segment, place in zip(self.finger, self.bent(30.0)):
            segment.matrix_world = place
        bpy.context.view_layer.update()
        self.assertEqual(bpy.ops.rigmoves.record(index=0, which="AFTER"), {"FINISHED"})
        bpy.ops.rigmoves.build()

    def made(self, names, where):
        """A finger like the recorded one, placed by `where`. `names` is a
        prefix to number, or one name for each segment."""
        out = []
        for number, (knuckle, length) in enumerate(zip(self.KNUCKLES, self.LENGTHS)):
            name = (names[number] if isinstance(names, (list, tuple))
                    else "{:s}{:d}".format(names, number + 1))
            segment = cube(name, (0.0, 0.0, 0.0))
            segment.matrix_world = (where @ Matrix.Translation(knuckle + Vector((length * 0.5, 0.0, 0.0)))
                                    @ Matrix.Diagonal((length, 0.3, 0.3, 1.0)))
            out.append(segment)
        bpy.context.view_layer.update()
        return out

    def bent(self, degrees):
        """Each segment of the recorded finger with every joint bent this far."""
        out, carry = [], Matrix.Identity(4)
        for knuckle, home in zip(self.KNUCKLES, self.homes):
            carry = (carry @ Matrix.Translation(knuckle)
                     @ Matrix.Rotation(math.radians(degrees), 4, "Y")
                     @ Matrix.Translation(-knuckle))
            out.append(carry @ home)
        return out

    def ride(self, objects, clicked="Seg1"):
        select(*objects, bpy.data.objects[clicked])
        bpy.context.view_layer.objects.active = bpy.data.objects[clicked]
        return bpy.ops.rigmoves.ride_along(index=0, leader=clicked, rig_name=rig().name)

    def check_copy(self, copy, where, share, degrees):
        """Every segment of a copy where `where` puts the recorded finger's
        segment, bent this far, with the control at `share`."""
        drive(self.move, share)
        for segment, place in zip(copy, self.bent(degrees)):
            expected = [where @ place @ v.co for v in segment.data.vertices]
            self.assertLess(drift(segment, expected), TOLERANCE, segment.name)

    def test_a_copied_finger_curls_joint_by_joint(self):
        copy = self.made("Copy", self.BESIDE)
        self.assertEqual(self.ride(copy), {"FINISHED"})
        parts = self.move.parts
        self.assertEqual([parts[s.name].leader for s in copy], ["Seg1", "Seg2", "Seg3"])
        self.assertEqual([parts[s.name].rides_on for s in copy], ["", "Copy1", "Copy2"])
        bones = rig().data.bones
        self.assertEqual(bones[parts["Copy2"].bone_name].parent.name, parts["Copy1"].bone_name)
        self.assertEqual(bones[parts["Copy3"].bone_name].parent.name, parts["Copy2"].bone_name)
        for share, degrees in ((0.0, 0.0), (0.5, 15.0), (1.0, 30.0)):
            self.check_copy(copy, self.BESIDE, share, degrees)

    def test_copies_are_found_by_where_they_stand(self):
        # Turned a quarter round, named against their order, picked in a
        # jumble, and the tip of the recorded finger the part clicked last.
        where = Matrix.Translation((4.0, -2.0, 0.0)) @ Matrix.Rotation(math.radians(90.0), 4, "Z")
        copy = self.made(["Zed", "Alpha", "Mid"], where)
        self.assertEqual(self.ride([copy[2], copy[0], copy[1]], clicked="Seg3"), {"FINISHED"})
        parts = self.move.parts
        self.assertEqual([parts[s.name].leader for s in copy], ["Seg1", "Seg2", "Seg3"])
        for share, degrees in ((0.5, 15.0), (1.0, 30.0)):
            self.check_copy(copy, where, share, degrees)

    def test_several_fingers_in_one_go(self):
        turned = (Matrix.Translation((0.0, -3.0, 0.0))
                  @ Matrix.Rotation(math.radians(-40.0), 4, "Z"))
        one, two = self.made("One", self.BESIDE), self.made("Two", turned)
        self.assertEqual(self.ride(one + two), {"FINISHED"})
        self.assertIn("2 copies", rig().rigmoves.report)
        for share, degrees in ((0.5, 15.0), (1.0, 30.0)):
            self.check_copy(one, self.BESIDE, share, degrees)
            self.check_copy(two, turned, share, degrees)

    def test_a_mirrored_copy_curls_the_mirror_way(self):
        # The way Ctrl+M leaves one: the whole finger mirrored across X, so it
        # points the other way, then set to one side.
        where = self.BESIDE @ Matrix.Diagonal((-1.0, 1.0, 1.0, 1.0))
        copy = self.made("Copy", where)
        self.assertLess(copy[0].matrix_world.determinant(), 0.0)
        self.assertEqual(self.ride(copy), {"FINISHED"})
        for share, degrees in ((0.5, 15.0), (1.0, 30.0)):
            self.check_copy(copy, where, share, degrees)

    def test_a_copy_sent_behind_moves_as_one(self):
        copy = self.made("Copy", self.BESIDE)
        self.ride(copy)
        # The Lead is its first joint's - the panel shows no other - and the
        # whole finger waits for the recorded one.
        self.move.parts["Copy1"].lead = -50
        self.check_copy(copy, self.BESIDE, 0.5, 0.0)
        self.check_copy(copy, self.BESIDE, 0.75, 15.0)
        self.check_copy(copy, self.BESIDE, 1.0, 30.0)

    def test_a_late_copy_keeps_its_joints_in_step(self):
        # The recorded middle joint waits a quarter. A copy a whole finger
        # behind plays the very same, half a control later, joints in step.
        copy = self.made("Copy", self.BESIDE)
        self.ride(copy)
        self.move.parts["Seg2"].start = 0.25
        self.move.parts["Copy1"].lead = -50
        for early in (0.1, 0.3, 0.45):
            drive(self.move, early)
            seen = [[self.BESIDE @ p for p in world_points(s)] for s in self.finger]
            drive(self.move, early + 0.5)
            for segment, expected in zip(copy, seen):
                self.assertLess(drift(segment, expected), TOLERANCE, segment.name)

    def test_mirror_on_a_copy_mirrors_every_joint(self):
        copy = self.made("Copy", self.BESIDE)
        self.ride(copy)
        self.assertEqual(bpy.ops.rigmoves.set_mirror(
            index=0, part=self.move.parts.find("Copy1"), axis="Z"), {"FINISHED"})
        # Across its own Z the curl goes the other way round, every joint.
        across = Matrix.Diagonal((1.0, 1.0, -1.0, 1.0))
        drive(self.move, 1.0)
        for segment, place in zip(copy, self.bent(30.0)):
            expected = [self.BESIDE @ across @ place @ across @ v.co
                        for v in segment.data.vertices]
            self.assertLess(drift(segment, expected), TOLERANCE, segment.name)

    def test_a_copy_taken_out_goes_whole(self):
        copy = self.made("Copy", self.BESIDE)
        rest = [rest_points(s) for s in copy]
        self.ride(copy)
        self.assertEqual(bpy.ops.rigmoves.drop_rider(
            index=0, part=self.move.parts.find("Copy1")), {"FINISHED"})
        for segment, points in zip(copy, rest):
            self.assertIsNone(self.move.parts.get(segment.name))
            self.assertIsNone(rig().data.bones.get(segment.name))
            self.assertFalse([m for m in segment.modifiers if m.type == "ARMATURE"])
            drive(self.move, 1.0)
            self.assertLess(drift(segment, points), TOLERANCE, segment.name)
        self.check_copy(self.finger, Matrix(), 1.0, 30.0)

    def test_one_button_for_a_finger_selected_whole(self):
        copy = self.made("Copy", self.BESIDE)
        select(*copy, *self.finger)
        bpy.context.view_layer.objects.active = self.finger[1]
        found = rigmoves.leaders(bpy.context, rig())
        self.assertEqual([p.name for _i, _m, p in found], ["Seg2"])

    def test_joints_added_later_ride_on_their_copy(self):
        copy = self.made("Copy", self.BESIDE)
        self.assertEqual(self.ride(copy[:1]), {"FINISHED"})
        self.assertEqual(self.ride(copy[1:]), {"FINISHED"})
        parts = self.move.parts
        self.assertEqual([parts[s.name].rides_on for s in copy], ["", "Copy1", "Copy2"])
        self.check_copy(copy, self.BESIDE, 1.0, 30.0)

    def test_a_first_joint_added_later_takes_up_the_rest(self):
        copy = self.made("Copy", self.BESIDE)
        self.assertEqual(self.ride(copy[1:]), {"FINISHED"})
        self.assertEqual(self.ride(copy[:1]), {"FINISHED"})
        parts = self.move.parts
        self.assertEqual([parts[s.name].rides_on for s in copy], ["", "Copy1", "Copy2"])
        self.check_copy(copy, self.BESIDE, 1.0, 30.0)

    def test_copies_ridden_before_the_first_build(self):
        # Set up before the recorded finger is built, they ride from the
        # first Build.
        bpy.ops.rigmoves.remove(index=0)
        for segment, home in zip(self.finger, self.homes):
            segment.matrix_world = home
        select(*self.finger)
        bpy.ops.rigmoves.new_move()
        self.move = rig().rigmoves.moves[0]
        self.move.parts["Seg2"].follows = "Seg1"
        self.move.parts["Seg3"].follows = "Seg2"
        copy = self.made("Copy", self.BESIDE)
        self.assertEqual(self.ride(copy), {"FINISHED"})
        for segment, knuckle in zip(self.finger, self.KNUCKLES):
            bpy.context.scene.cursor.location = knuckle
            select(segment)
            bpy.ops.rigmoves.set_pivot(index=0, kind="CURSOR")
        for segment, place in zip(self.finger, self.bent(30.0)):
            segment.matrix_world = place
        bpy.context.view_layer.update()
        self.assertEqual(bpy.ops.rigmoves.record(index=0, which="AFTER"), {"FINISHED"})
        bpy.ops.rigmoves.build()
        for share, degrees in ((0.5, 15.0), (1.0, 30.0)):
            self.check_copy(copy, self.BESIDE, share, degrees)


class TestCopiedParts(CopyThatCase):
    """Parts copied after they were bound: Shift+D copies the binding with the
    part, and Alt+D shares the mesh the binding is kept on."""

    def setUp(self):
        super().setUp()
        self.lead = cube("Lead", (0.0, 0.0, 0.0))

        def pose():
            self.lead.location = (2.0, 0.0, 1.0)

        self.before, self.after = record_move([self.lead], pose)
        bpy.ops.rigmoves.build()
        self.move = rig().rigmoves.moves[0]

    def copy(self, obj, offset, linked=False):
        """Duplicate an object as the viewport does, and move the copy along."""
        select(obj)
        self.assertEqual(bpy.ops.object.duplicate(linked=linked), {"FINISHED"})
        made = bpy.context.view_layer.objects.active
        made.matrix_world = Matrix.Translation(offset) @ made.matrix_world
        bpy.context.view_layer.update()
        return made

    def ride(self, *others):
        select(*others, self.lead)
        bpy.context.view_layer.objects.active = self.lead
        self.assertEqual(bpy.ops.rigmoves.ride_along(index=0, leader="Lead",
                                                     rig_name=rig().name), {"FINISHED"})

    def check_travel(self, obj, rest, share):
        """The object as far along the leader's straight move as `share`."""
        travel = Vector((2.0, 0.0, 1.0)) * share
        self.assertLess(drift(obj, [p + travel for p in rest]), TOLERANCE, obj.name)

    def test_a_copy_of_a_rider_moves_by_its_own_bone_only(self):
        # As it was found: one rider, copied with Shift+D for the next, and
        # the first then mirrored. The copy ran straight, half and half
        # between its own bone and the first rider's.
        first = cube("First", (0.0, 3.0, 0.0))
        self.ride(first)
        second = self.copy(first, (0.0, 3.0, 0.0))
        self.assertIn("First", [g.name for g in second.vertex_groups])
        rest = rest_points(second)
        self.ride(second)
        self.assertEqual([g.name for g in second.vertex_groups], [second.name])
        self.assertEqual(bpy.ops.rigmoves.set_mirror(
            index=0, part=self.move.parts.find("First"), axis="Z"), {"FINISHED"})
        for share in (0.5, 1.0):
            drive(self.move, share)
            self.check_travel(second, rest, share)

    def test_linked_copies_move_by_their_own_bones(self):
        # Alt+D shares the mesh, and vertex groups live on the mesh: binding
        # the copy gave the leader the copy's group as well, and each was
        # moved half by the other's bone.
        other = self.copy(self.lead, (0.0, 3.0, 0.0), linked=True)
        self.assertEqual(other.data.name, self.lead.data.name)
        rest = rest_points(other)
        self.ride(other)
        self.assertNotEqual(other.data.name, self.lead.data.name)
        self.assertEqual([g.name for g in self.lead.vertex_groups], ["Lead"])
        self.move.parts[other.name].lead = -50
        drive(self.move, 0.5)
        self.assertLess(drift(self.lead, self.after["Lead"]), TOLERANCE)
        self.check_travel(other, rest, 0.0)
        drive(self.move, 1.0)
        self.check_travel(other, rest, 1.0)

    def test_a_group_for_a_part_that_joins_later(self):
        # Copied from a part of a rig since deleted, the leader still carries
        # that part's group, under a name no bone has - until an object of
        # that name joins, and its bone is made in the same Build.
        group = self.lead.vertex_groups.new(name="First")
        group.add(range(len(self.lead.data.vertices)), 1.0, "REPLACE")
        first = cube("First", (0.0, 3.0, 0.0))
        self.ride(first)
        self.assertEqual([g.name for g in self.lead.vertex_groups], ["Lead"])
        self.move.parts["First"].lead = -50
        drive(self.move, 0.5)
        self.assertLess(drift(self.lead, self.after["Lead"]), TOLERANCE)

    def test_build_heals_a_copy_bound_before(self):
        # As a file saved by 0.15 opens: a rider still carrying the vertex
        # group of the part it was copied from.
        first = cube("First", (0.0, 3.0, 0.0))
        self.ride(first)
        rest = rest_points(first)
        group = first.vertex_groups.new(name="Lead")
        group.add(range(len(first.data.vertices)), 1.0, "REPLACE")
        self.move.parts["First"].lead = -50
        drive(self.move, 0.5)
        self.assertGreater(drift(first, rest), 0.1)
        bpy.ops.rigmoves.build()
        self.assertIn("copied from another", rig().rigmoves.report)
        self.assertEqual([g.name for g in first.vertex_groups], ["First"])
        drive(self.move, 0.5)
        self.check_travel(first, rest, 0.0)
        drive(self.move, 1.0)
        self.check_travel(first, rest, 1.0)


class WatchedObjects:
    """bpy.data.objects, noting every removal made while a loop over it is going
    on. Iterating it goes through a generator that counts the loops that are
    live: a `for` that is still running is suspended inside the generator."""

    def __init__(self, real):
        self.real, self.live, self.removals = real, 0, []

    def __iter__(self):
        return self.loop()

    def loop(self):
        self.live += 1
        try:
            yield from self.real
        finally:
            self.live -= 1

    def remove(self, obj, *args, **kwargs):
        self.removals.append((obj.name, self.live))
        return self.real.remove(obj, *args, **kwargs)

    def __getattr__(self, name):
        return getattr(self.real, name)


class WatchedData:
    """bpy.data with its objects watched; all else is the real one's."""

    def __init__(self, real):
        self.real, self.objects = real, WatchedObjects(real.objects)

    def __getattr__(self, name):
        return getattr(self.real, name)


class WatchedBpy:
    """The bpy the add-on sees: its data watched, all else the real bpy's."""

    def __init__(self):
        self.data = WatchedData(bpy.data)

    def __getattr__(self, name):
        return getattr(bpy, name)


class TestTheTimerRemovesNothingWhileItLoops(CopyThatCase):
    """A part deleted in the viewport is let go of by a timer, which removes its
    object from the file. It did so from inside a loop over every object in the
    file, and a loop over a collection that loses a member goes on to hand out
    the member it has just lost: the next rig was read off freed memory, and
    Blender could crash on it."""

    def test_the_object_of_a_deleted_part_is_removed_after_the_loop_is_over(self):
        # "Cube" sorts right after "CopyThat Rig" in bpy.data.objects: the very
        # next object the loop would hand out.
        part = cube("Cube", (0.0, 0.0, 1.0))

        def pose():
            part.location.z += 1.0

        record_move([part], pose)
        self.assertEqual(bpy.ops.rigmoves.build(), {"FINISHED"})
        self.assertEqual([o.name for o in bpy.data.objects][:2], ["CopyThat Rig", "Cube"])
        select(part)
        # X in the viewport: out of every collection, kept by the part's pointer.
        self.assertEqual(bpy.ops.object.delete(), {"FINISHED"})
        bpy.context.view_layer.update()
        self.assertEqual(len(bpy.data.objects["Cube"].users_collection), 0)

        watched = WatchedBpy()
        with mock.patch.object(rigmoves, "bpy", watched):
            rigmoves.let_deleted_go()
        objects = watched.data.objects
        self.assertEqual([name for name, _live in objects.removals], ["Cube"])
        self.assertEqual([live for _name, live in objects.removals], [0],
                         "removed while a loop over the objects was going on")
        self.assertIsNone(rig().rigmoves.moves[0].parts[0].object)
        self.assertNotIn("Cube", bpy.data.objects)


def delete_in_the_viewport(*objects):
    """X on these, and what Blender does about it half a second later: the
    depsgraph handler sees them and a timer lets go of them. The rig is
    selected after, as the panel has nothing to say without an active object."""
    select(*objects)
    assert bpy.ops.object.delete() == {"FINISHED"}
    bpy.context.view_layer.update()
    rigmoves.follow_renames_handler()
    rigmoves.let_deleted_go()
    select(rig())


class TestANewObjectTakesTheNameOfADeletedPart(CopyThatCase):
    """Two cubes are a move, built; one is deleted, and the cube added next is
    given the name it left free. The part of the deleted cube took the new one
    for its object: the panel said it was in the rig, New Move and Add To This
    Group refused it ("already in Move 1"), and Build moved it onto the deleted
    cube's Before, unbound."""

    def setUp(self):
        super().setUp()
        self.first = cube("Cube", (0.0, 0.0, 0.0))
        second = cube("Cube.001", (3.0, 0.0, 0.0))
        select(self.first, second)
        self.assertEqual(bpy.ops.rigmoves.new_move(), {"FINISHED"})
        self.first.location.z += 1.0
        bpy.context.view_layer.update()
        select(self.first)
        self.assertEqual(bpy.ops.rigmoves.record(index=0, which="AFTER"), {"FINISHED"})
        self.assertEqual(bpy.ops.rigmoves.build(), {"FINISHED"})
        self.move = rig().rigmoves.moves[0]
        delete_in_the_viewport(second)
        self.assertNotIn("Cube.001", bpy.data.objects)
        # The next cube added is given the name that was left.
        self.new = cube("Cube.001", (20.0, 0.0, 0.0))
        self.assertEqual(self.new.name, "Cube.001")
        bpy.context.view_layer.update()
        self.where = rest_points(self.new)

    def test_the_part_of_the_deleted_cube_is_not_the_new_one(self):
        self.assertIsNone(rigmoves.part_object(self.move.parts["Cube.001"]))
        select(self.new)
        self.assertEqual(rigmoves.newcomers(bpy.context, rig()), [self.new])

    def test_add_to_this_group_takes_it_and_build_leaves_it_where_it_stands(self):
        select(self.new)
        self.assertEqual(bpy.ops.rigmoves.add_to_move(index=0, rig_name=rig().name),
                         {"FINISHED"})
        self.assertEqual([p.name for p in self.move.parts], ["Cube", "Cube.001"])
        self.assertIs(rigmoves.part_object(self.move.parts["Cube.001"]), self.new)
        self.assertIn("'Cube.001' was deleted, so it was taken out of 'Move 1'.",
                      rig().rigmoves.report)
        self.assertEqual(bpy.ops.rigmoves.build(), {"FINISHED"})
        self.assertLess(drift(self.new, self.where), TOLERANCE)
        self.assertEqual([g.name for g in self.new.vertex_groups], ["Cube.001"])
        # And it plays a move of its own once one is recorded.
        self.new.location.z += 1.0
        bpy.context.view_layer.update()
        select(self.new)
        self.assertEqual(bpy.ops.rigmoves.record(index=0, which="AFTER"), {"FINISHED"})
        self.assertEqual(bpy.ops.rigmoves.build(), {"FINISHED"})
        for share in (0.0, 0.5, 1.0):
            drive(self.move, share)
            self.assertLess(drift(self.new, [p + Vector((0.0, 0.0, share)) for p in self.where]),
                            TOLERANCE, share)
        self.assertLess(drift(self.first, [p + Vector((0.0, 0.0, 1.0))
                                           for p in rest_points(self.first)]), TOLERANCE)

    def test_new_move_takes_it_too(self):
        select(self.new)
        self.assertEqual(bpy.ops.rigmoves.new_move(), {"FINISHED"})
        self.assertEqual([p.name for p in rig().rigmoves.moves[1].parts], ["Cube.001"])
        self.assertEqual([p.name for p in rig().rigmoves.moves[0].parts], ["Cube"])


class TestADeletedPartLeavesItsMove(CopyThatCase):
    """A part whose object was deleted stayed in its move for good: Ring said it
    "has no Before recorded yet", the reports counted it, a part that followed
    it was left hung from nothing, and every call for the part's object looked
    through the whole file for it."""

    KNUCKLES = (Vector((0.0, 0.0, 0.0)), Vector((1.0, 0.0, 0.0)), Vector((2.0, 0.0, 0.0)))

    def finger(self):
        """Three segments end to end, each hanging from the one before, every
        joint closed 30 degrees; built."""
        self.segments = []
        for number in range(3):
            segment = cube("Seg{:d}".format(number + 1), (number + 0.5, 0.0, 0.0))
            segment.scale = (1.0, 0.3, 0.3)
            self.segments.append(segment)
        bpy.context.view_layer.update()
        homes = [s.matrix_world.copy() for s in self.segments]
        self.rest = [rest_points(s) for s in self.segments]
        select(*self.segments)
        self.assertEqual(bpy.ops.rigmoves.new_move(), {"FINISHED"})
        self.move = rig().rigmoves.moves[0]
        for segment, knuckle in zip(self.segments, self.KNUCKLES):
            bpy.context.scene.cursor.location = knuckle
            select(segment)
            self.assertEqual(bpy.ops.rigmoves.set_pivot(index=0, kind="CURSOR"), {"FINISHED"})
        self.move.parts["Seg2"].follows = "Seg1"
        self.move.parts["Seg3"].follows = "Seg2"
        carry = Matrix.Identity(4)
        for segment, knuckle, home in zip(self.segments, self.KNUCKLES, homes):
            carry = (carry @ Matrix.Translation(knuckle)
                     @ Matrix.Rotation(math.radians(30.0), 4, "Y") @ Matrix.Translation(-knuckle))
            segment.matrix_world = carry @ home
        bpy.context.view_layer.update()
        self.assertEqual(bpy.ops.rigmoves.record(index=0, which="AFTER"), {"FINISHED"})
        self.assertEqual(bpy.ops.rigmoves.build(), {"FINISHED"})
        self.assertLess(drift(self.segments[2], self.rest[2]), TOLERANCE)

    def petals(self):
        """One petal that moves outwards, ringed four times round the world's
        origin, built; the petal, and where each copy is at 50% and 100%."""
        petal = cube("Petal", (2.0, 0.0, 0.5))
        petal.scale = (0.8, 0.3, 0.1)
        bpy.context.view_layer.update()

        def pose():
            petal.location.x += 1.0

        record_move([petal], pose)
        self.assertEqual(bpy.ops.rigmoves.build(), {"FINISHED"})
        bpy.context.scene.cursor.location = (0.0, 0.0, 0.0)
        select(petal)
        self.assertEqual(bpy.ops.rigmoves.ring(index=0, count=4), {"FINISHED"})
        self.move = rig().rigmoves.moves[0]
        self.copies = [bpy.data.objects["Petal {:d}".format(n)] for n in (2, 3, 4)]
        self.plays = {}
        for share in (0.5, 1.0):
            drive(self.move, share)
            self.plays[share] = [world_points(c) for c in self.copies]
        drive(self.move, 0.0)
        return petal

    def test_a_deleted_middle_joint_leaves_the_tip_where_it_stands_and_following_nothing(self):
        self.finger()
        delete_in_the_viewport(self.segments[1])
        self.assertLess(drift(self.segments[2], self.rest[2]), TOLERANCE)
        self.assertEqual(bpy.ops.rigmoves.build(), {"FINISHED"})
        self.assertEqual([p.name for p in self.move.parts], ["Seg1", "Seg3"])
        self.assertEqual(self.move.parts["Seg3"].follows, "")
        self.assertEqual(self.move.parts["Seg3"].follows_kept, "")
        self.assertNotIn("Seg2", rig().data.bones)
        self.assertLess(drift(self.segments[2], self.rest[2]), TOLERANCE)
        self.assertIn("'Seg2' was deleted, so it was taken out of 'Move 1'.",
                      rig().rigmoves.report)
        # What is left plays.
        drive(self.move, 1.0)
        self.assertGreater(drift(self.segments[2], self.rest[2]), 0.1)

    def test_a_follower_does_not_jump_when_the_part_it_hung_from_is_let_go(self):
        # Before the first Build a follower's object hangs from its leader's, and
        # is carried when the leader is dragged. Blender frees what hung from an
        # object without keeping it where it stood.
        leader = cube("Leader", (0.0, 0.0, 0.0))
        follower = cube("Follower", (3.0, 0.0, 0.0))
        select(leader, follower)
        self.assertEqual(bpy.ops.rigmoves.new_move(), {"FINISHED"})
        move = rig().rigmoves.moves[0]
        move.parts["Follower"].follows = "Leader"
        self.assertIs(follower.parent, leader)
        leader.location.z += 1.0
        bpy.context.view_layer.update()
        carried = world_points(follower)
        self.assertGreater(carried[0].z, 0.4)
        delete_in_the_viewport(leader)
        self.assertLess(drift(follower, carried), TOLERANCE)
        # What it says is for the next button to put in the report.
        self.addCleanup(lambda: rigmoves.HEARD.update(notes=[]))
        rigmoves.catch_up(rig())
        self.assertEqual([p.name for p in move.parts], ["Follower"])
        self.assertEqual(move.parts["Follower"].follows, "")
        self.assertIsNone(follower.parent)
        self.assertLess(drift(follower, carried), TOLERANCE)

    def test_several_are_said_together(self):
        self.finger()
        delete_in_the_viewport(self.segments[1], self.segments[2])
        self.assertEqual(bpy.ops.rigmoves.build(), {"FINISHED"})
        self.assertEqual([p.name for p in self.move.parts], ["Seg1"])
        self.assertIn("'Seg2' and 'Seg3' were deleted, so they were taken out of 'Move 1'.",
                      rig().rigmoves.report)

    def test_a_deleted_leader_with_riders_stays_under_a_name_that_is_free(self):
        petal = self.petals()
        delete_in_the_viewport(petal)
        self.assertEqual(bpy.ops.rigmoves.build(), {"FINISHED"})
        self.assertEqual([p.name for p in self.move.parts],
                         ["Petal (deleted)", "Petal 2", "Petal 3", "Petal 4"])
        self.assertEqual({p.leader for p in self.move.parts if p.leader}, {"Petal (deleted)"})
        self.assertIn("'Petal' was deleted, but 3 riders copy its move, so it is kept as "
                      "'Petal (deleted)'", rig().rigmoves.report)
        # The riders play as they did.
        for share in (0.5, 1.0):
            drive(self.move, share)
            for copy, points in zip(self.copies, self.plays[share]):
                self.assertLess(drift(copy, points), TOLERANCE, "{:s} at {:.0%}".format(
                    copy.name, share))
        drive(self.move, 0.0)
        # Said once: the next Build has nothing new to say.
        self.assertEqual(bpy.ops.rigmoves.build(), {"FINISHED"})
        self.assertNotIn("was deleted", rig().rigmoves.report)
        # And the name is free for a new object.
        new = cube("Petal", (9.0, 0.0, 0.5))
        self.assertEqual(new.name, "Petal")
        select(new)
        self.assertEqual(bpy.ops.rigmoves.add_to_move(index=0, rig_name=rig().name),
                         {"FINISHED"})
        self.assertIs(rigmoves.part_object(self.move.parts["Petal"]), new)
        self.assertIsNone(rigmoves.part_object(self.move.parts["Petal (deleted)"]))

    def test_removing_the_move_takes_the_bone_of_a_deleted_leader_too(self):
        petal = self.petals()
        delete_in_the_viewport(petal)
        self.assertEqual(bpy.ops.rigmoves.build(), {"FINISHED"})
        self.assertIn("Petal", rig().data.bones)
        select(rig())
        self.assertEqual(bpy.ops.rigmoves.remove(index=0), {"FINISHED"})
        self.assertEqual(sorted(b.name for b in rig().data.bones), ["Root"])

    def test_ring_on_a_chain_whose_last_joint_was_deleted_does_not_blame_a_before(self):
        self.finger()
        delete_in_the_viewport(self.segments[2])
        self.assertEqual(bpy.ops.rigmoves.build(), {"FINISHED"})
        bpy.context.scene.cursor.location = (0.0, 0.0, -3.0)
        select(self.segments[0])
        done = bpy.ops.rigmoves.ring(index=0, count=3)
        self.assertNotIn("has no Before recorded yet", rig().rigmoves.report)
        self.assertEqual(done, {"FINISHED"}, rig().rigmoves.report)
        self.assertIn("2 joints each", rig().rigmoves.report)

    def test_a_move_left_with_no_parts_stays_and_the_panel_build_and_remove_cope(self):
        part = cube("Cube", (0.0, 0.0, 1.0))

        def pose():
            part.location.z += 1.0

        record_move([part], pose)
        self.assertEqual(bpy.ops.rigmoves.build(), {"FINISHED"})
        delete_in_the_viewport(part)
        drawn_panel()
        self.assertEqual(bpy.ops.rigmoves.build(), {"FINISHED"})
        self.assertEqual(len(rig().rigmoves.moves), 1)
        self.assertEqual(len(rig().rigmoves.moves[0].parts), 0)
        select(rig())
        drawn_panel()
        self.assertEqual(bpy.ops.rigmoves.remove(index=0), {"FINISHED"})
        self.assertEqual(len(rig().rigmoves.moves), 0)

    def test_a_button_drawn_before_a_part_was_taken_out_works_on_the_part_it_was_drawn_for(self):
        # The riders' rows are drawn by their place in the move's list, and a
        # deleted part ahead of them is taken out when the button is pressed.
        ahead = cube("Ahead", (-4.0, 0.0, 0.5))
        petal = cube("Petal", (2.0, 0.0, 0.5))
        petal.scale = (0.8, 0.3, 0.1)
        bpy.context.view_layer.update()
        select(ahead, petal)
        self.assertEqual(bpy.ops.rigmoves.new_move(), {"FINISHED"})
        petal.location.x += 1.0
        bpy.context.view_layer.update()
        select(petal)
        self.assertEqual(bpy.ops.rigmoves.record(index=0, which="AFTER"), {"FINISHED"})
        self.assertEqual(bpy.ops.rigmoves.build(), {"FINISHED"})
        bpy.context.scene.cursor.location = (0.0, 0.0, 0.0)
        select(petal)
        self.assertEqual(bpy.ops.rigmoves.ring(index=0, count=4), {"FINISHED"})
        move = rig().rigmoves.moves[0]
        self.assertEqual([p.name for p in move.parts],
                         ["Ahead", "Petal", "Petal 2", "Petal 3", "Petal 4"])
        delete_in_the_viewport(ahead)
        # Drawn now, "Petal 3" is the fourth row: index 3.
        self.assertEqual(bpy.ops.rigmoves.drop_rider(index=0, part=3), {"FINISHED"})
        self.assertEqual([p.name for p in move.parts], ["Petal", "Petal 2", "Petal 4"])


class TestABigSceneStaysQuick(CopyThatCase):
    """A rig of fifty parts in a file with a thousand other meshes in sixty
    collections. Every question about a part's object looked through the
    collections of the whole file, and the handler that runs after every update
    asked it of every part, so the panel and every drag slowed down - and one
    deleted part, not yet let go of, made each of those questions look at every
    object in the file."""

    def setUp(self):
        super().setUp()
        scene = bpy.context.scene
        collections = []
        for number in range(60):
            collection = bpy.data.collections.new("Col{:02d}".format(number))
            scene.collection.children.link(collection)
            collections.append(collection)
        shape = bpy.data.meshes.new("Shape")
        shape.from_pydata([(0, 0, 0), (1, 0, 0), (0, 1, 0)], [], [(0, 1, 2)])
        for number in range(1000):
            collections[number % 60].objects.link(
                bpy.data.objects.new("Other{:04d}".format(number), shape))
        self.parts = [cube("Part{:02d}".format(number), (number * 2.0, 0.0, 1.0))
                      for number in range(50)]
        select(*self.parts)
        self.assertEqual(bpy.ops.rigmoves.new_move(), {"FINISHED"})
        for part in self.parts:
            part.location.z += 1.0
        bpy.context.view_layer.update()
        self.assertEqual(bpy.ops.rigmoves.record(index=0, which="AFTER"), {"FINISHED"})
        self.assertEqual(bpy.ops.rigmoves.build(), {"FINISHED"})

    def times(self):
        """(milliseconds a handler call takes on average, milliseconds the panel
        takes to draw). The processor's time, not the clock's: the machine may
        be busy with something else, and the limits below are wide for the same
        reason."""
        import time
        select(self.parts[1])
        drawn_panel()
        rigmoves.follow_renames_handler()
        start = time.process_time()
        for _ in range(20):
            rigmoves.follow_renames_handler()
        handler = (time.process_time() - start) * 1000.0 / 20
        start = time.process_time()
        for _ in range(3):
            drawn_panel()
        return handler, (time.process_time() - start) * 1000.0 / 3

    def test_the_handler_and_the_panel_take_a_few_milliseconds(self):
        handler, panel = self.times()
        self.assertLess(handler, 30.0, "the handler took {:.1f} ms".format(handler))
        self.assertLess(panel, 150.0, "the panel took {:.1f} ms".format(panel))
        # With one part deleted and not yet let go of, which is for half a second
        # after X and for as long as the timer is not run.
        select(self.parts[0])
        self.assertEqual(bpy.ops.object.delete(), {"FINISHED"})
        bpy.context.view_layer.update()
        handler, panel = self.times()
        self.assertLess(handler, 30.0, "the handler took {:.1f} ms with a part deleted".format(handler))
        self.assertLess(panel, 150.0, "the panel took {:.1f} ms with a part deleted".format(panel))

    def test_the_handler_follows_a_rename_and_otherwise_leaves_the_parts_alone(self):
        with mock.patch.object(rigmoves, "follow_renames", wraps=rigmoves.follow_renames) as asked:
            rigmoves.follow_renames_handler()
            self.assertEqual(asked.call_count, 0)
            self.parts[3].name = "Renamed"
            rigmoves.follow_renames_handler()
            self.assertEqual(asked.call_count, 1)
        self.assertEqual(rig().rigmoves.moves[0].parts[3].name, "Renamed")


class CopiedModel(CopyThatCase):
    """A built model, and copies made of it by the rig and its parts being
    selected and duplicated, then moved 6 m. (ChestCase, further down, is a
    chest too; these classes have to come before it.)"""

    OFF = Matrix.Translation((6.0, 0.0, 0.0))

    def chest(self):
        """A lid hinged on its back edge, swung 100 degrees, built."""
        self.lid = cube("Lid", (0.0, 0.0, 1.1))
        self.lid.scale = (2.0, 1.2, 0.2)
        bpy.context.view_layer.update()
        home = self.lid.matrix_world.copy()
        hinge = Vector((0.0, 0.6, 1.0))
        select(self.lid)
        self.assertEqual(bpy.ops.rigmoves.new_move(), {"FINISHED"})
        bpy.context.scene.cursor.location = hinge
        select(self.lid)
        self.assertEqual(bpy.ops.rigmoves.set_pivot(index=0, kind="CURSOR"), {"FINISHED"})
        self.lid.matrix_world = turn_about(hinge, "X", -100.0) @ home
        bpy.context.view_layer.update()
        self.assertEqual(bpy.ops.rigmoves.record(index=0, which="AFTER"), {"FINISHED"})
        self.assertEqual(bpy.ops.rigmoves.build(), {"FINISHED"})
        self.keep(self.lid)

    def keep(self, part):
        """Remember the model as it is: the part (the original) and its rig,
        how the part plays, and what the rig is made of."""
        self.part, self.rig1 = part, rig()
        self.plays = self.play(self.rig1, part)
        self.made = self.made_of()

    def play(self, owner, part):
        """Where the part is at the ends and half way."""
        move = owner.rigmoves.moves[0]
        out = {}
        for share in (0.0, 0.5, 1.0):
            owner.pose.bones[move.handle_name].location.y = move.rail * share
            bpy.context.view_layer.update()
            out[share] = world_points(part)
        owner.pose.bones[move.handle_name].location.y = 0.0
        bpy.context.view_layer.update()
        return out

    def made_of(self):
        """The original rig's bones, the part's groups and the constraints."""
        return (sorted(b.name for b in self.rig1.data.bones),
                [g.name for g in self.part.vertex_groups],
                sorted((pb.name, c.name) for pb in self.rig1.pose.bones for c in pb.constraints))

    def copy_everything(self, linked):
        """Duplicate the rig and its part, as Alt+D (linked) or Shift+D does,
        and move the copy off. Returns the copy's rig and part."""
        for obj in bpy.context.view_layer.objects:
            obj.select_set(False)
        self.rig1.select_set(True)
        self.part.select_set(True)
        bpy.context.view_layer.objects.active = self.rig1
        if linked:
            self.assertEqual(bpy.ops.object.duplicate_move_linked(
                TRANSFORM_OT_translate={"value": (6.0, 0.0, 0.0)}), {"FINISHED"})
        else:
            self.assertEqual(bpy.ops.object.duplicate(linked=False), {"FINISHED"})
            self.assertEqual(bpy.ops.transform.translate(value=(6.0, 0.0, 0.0)), {"FINISHED"})
        bpy.context.view_layer.update()
        rig2 = next(o for o in bpy.context.selected_objects if o.type == "ARMATURE")
        part2 = next(o for o in bpy.context.selected_objects if o.type == "MESH")
        self.assertIsNot(rig2, self.rig1)
        bpy.context.scene.rigmoves_rig = rig2
        return rig2, part2

    def check_original(self):
        """The original is made of what it was and plays as it did."""
        self.assertEqual(self.made_of(), self.made)
        now = self.play(self.rig1, self.part)
        for share, points in self.plays.items():
            self.assertLess(max((a - b).length for a, b in zip(now[share], points)), TOLERANCE,
                            "the original at {:.0%}".format(share))

    def check_copy(self, rig2, part2):
        """The copy plays what the original does, 6 m along."""
        now = self.play(rig2, part2)
        for share, points in self.plays.items():
            wanted = [self.OFF @ p for p in points]
            self.assertLess(max((a - b).length for a, b in zip(now[share], wanted)), TOLERANCE,
                            "the copy at {:.0%}".format(share))


class TestAnAltDCopyOfAWholeModelIsAModelOfItsOwn(CopiedModel):
    """Alt+D of the rig and its parts links the Armature as well as the meshes,
    so the copy and the original had one set of bones: building the copy, ringing
    its lid or removing its move changed the original, which ended up a metre
    off, or lost its bone, its group and its constraints."""

    def setUp(self):
        super().setUp()
        self.chest()
        self.rig2, self.part2 = self.copy_everything(linked=True)
        self.assertIs(self.rig2.data, self.rig1.data)
        self.assertIs(self.part2.data, self.part.data)

    def test_the_copy_takes_an_armature_of_its_own_and_keeps_its_pose_constraints_and_drivers(self):
        def made_of(owner):
            return ([(pb.name, [c.name for c in pb.constraints]) for pb in owner.pose.bones],
                    sorted(d.data_path for d in owner.animation_data.drivers),
                    {pb.name: sorted(pb.keys()) for pb in owner.pose.bones},
                    {b.name: sorted(b.keys()) for b in owner.data.bones},
                    owner.pose.bones["Move 1 handle"].location.y)

        self.rig2.pose.bones["Move 1 handle"].location.y = 0.05
        bpy.context.view_layer.update()
        before = made_of(self.rig2)
        rigmoves.catch_up(self.rig2)
        self.assertIsNot(self.rig2.data, self.rig1.data)
        self.assertEqual(self.rig1.data.users, 1)
        self.assertIn(self.rig2.name, self.rig2.data.name)
        self.assertEqual(made_of(self.rig2), before)
        self.assertEqual(made_of(self.rig1)[:4], before[:4])
        # Once is enough.
        own = self.rig2.data
        rigmoves.catch_up(self.rig2)
        self.assertIs(self.rig2.data, own)

    def test_building_the_copy_with_another_part_leaves_the_original_alone(self):
        coin = cube("Coin", (6.3, 0.0, 0.6))
        coin.scale = (0.3, 0.3, 0.05)
        bpy.context.view_layer.update()
        select(coin, self.part2)
        self.assertEqual(bpy.ops.rigmoves.add_to_move(index=0, rig_name=self.rig2.name),
                         {"FINISHED"})
        coin.location.z += 1.0
        bpy.context.view_layer.update()
        select(coin)
        self.assertEqual(bpy.ops.rigmoves.record(index=0, which="AFTER"), {"FINISHED"})
        self.assertEqual(bpy.ops.rigmoves.build(), {"FINISHED"})
        self.check_original()
        self.check_copy(self.rig2, self.part2)
        self.assertIn("Coin", self.rig2.data.bones)
        self.assertIsNot(self.rig2.data, self.rig1.data)

    def test_a_ring_on_the_copy_leaves_the_original_alone(self):
        bpy.context.scene.cursor.location = (6.0, 4.0, 0.0)
        select(self.part2)
        self.assertEqual(bpy.ops.rigmoves.ring(index=0, count=4), {"FINISHED"})
        self.assertEqual(len(self.rig2.rigmoves.moves[0].parts), 4)
        self.check_original()
        self.check_copy(self.rig2, self.part2)

    def test_removing_the_copys_move_leaves_the_original_its_bones_groups_and_constraints(self):
        select(self.part2)
        self.assertEqual(bpy.ops.rigmoves.remove(index=0), {"FINISHED"})
        self.assertEqual(len(self.rig2.rigmoves.moves), 0)
        self.assertEqual([g.name for g in self.part2.vertex_groups], [])
        self.check_original()


class TestACopyOfAWholeModelHasPathCurvesOfItsOwn(CopiedModel):
    """A path curve and the line Show Paths draws are objects of their own, and
    are not selected with "the rig and its parts": the copy's parts pointed at
    the original's. Building the copy pinned the original's curve to the copy's
    ends, removing the copy's move deleted it, and the copy's Build deleted the
    original's path line."""

    def setUp(self):
        super().setUp()
        coin = cube("Coin", (3.0, 0.0, 0.6))
        coin.scale = (0.3, 0.3, 0.05)
        bpy.context.view_layer.update()
        home = coin.matrix_world.copy()
        select(coin)
        self.assertEqual(bpy.ops.rigmoves.new_move(), {"FINISHED"})
        coin.matrix_world = Matrix.Translation((0.0, -2.2, 0.0)) @ home
        bpy.context.view_layer.update()
        self.assertEqual(bpy.ops.rigmoves.record(index=0, which="AFTER"), {"FINISHED"})
        self.assertEqual(bpy.ops.rigmoves.build(), {"FINISHED"})
        select(coin)
        self.assertEqual(bpy.ops.rigmoves.curve_path(index=0), {"FINISHED"})
        curve = rig().rigmoves.moves[0].parts["Coin"].path_curve
        middle = curve.data.splines[0].bezier_points[1]
        for point in (middle.co, middle.handle_left, middle.handle_right):
            point.z += 1.5
        select(coin)
        self.assertEqual(bpy.ops.rigmoves.build(), {"FINISHED"})
        self.curve_name = curve.name
        self.keep(coin)
        # Bent: half way along it is well above where a straight path goes.
        self.assertGreater(self.plays[0.5][0].z - rest_points(coin)[0].z, 1.0)

    def where_the_curve_is(self):
        curve = bpy.data.objects[self.curve_name]
        return [tuple(round(c, 5) for c in p) for p in rigmoves.curve_line(curve)]

    def test_building_the_copy_leaves_the_original_s_curve_where_it_is(self):
        before = self.where_the_curve_is()
        rig2, part2 = self.copy_everything(linked=False)
        # The curve is an object of its own, not selected: the copy shares it.
        self.assertEqual(rig2.rigmoves.moves[0].parts[0].path_curve.name, self.curve_name)
        select(part2)
        self.assertEqual(bpy.ops.rigmoves.build(), {"FINISHED"})
        self.assertNotEqual(rig2.rigmoves.moves[0].parts[0].path_curve.name, self.curve_name)
        self.assertEqual(self.where_the_curve_is(), before)
        self.check_original()
        self.check_copy(rig2, part2)

    def test_removing_the_copy_leaves_the_original_s_curve_and_path(self):
        rig2, part2 = self.copy_everything(linked=False)
        select(part2)
        self.assertEqual(bpy.ops.rigmoves.remove(index=0), {"FINISHED"})
        self.assertIn(self.curve_name, bpy.data.objects)
        bpy.context.scene.rigmoves_rig = self.rig1
        select(self.part)
        self.assertEqual(bpy.ops.rigmoves.build(), {"FINISHED"})
        self.assertEqual(self.rig1.rigmoves.moves[0].parts[0].path_curve.name, self.curve_name)
        self.check_original()

    def test_the_copys_build_leaves_the_original_s_path_line(self):
        select(self.part)
        self.assertEqual(bpy.ops.rigmoves.show_paths(index=0, show=True), {"FINISHED"})
        line_name = self.rig1.rigmoves.moves[0].paths_object.name
        rig2, part2 = self.copy_everything(linked=False)
        select(part2)
        self.assertEqual(bpy.ops.rigmoves.build(), {"FINISHED"})
        self.assertIn(line_name, bpy.data.objects)
        self.assertIs(self.rig1.rigmoves.moves[0].paths_object, bpy.data.objects[line_name])
        own = rig2.rigmoves.moves[0].paths_object
        self.assertIsNotNone(own)
        self.assertNotEqual(own.name, line_name)


class TestMakeChainOrder(CopyThatCase):
    """The order follows how a joint is built, at the far end of the part before
    it: not whichever pivot happens to be nearest."""

    def made(self, specs):
        """New Move on cubes of (name, centre, size, pivot); the objects."""
        objects = []
        for name, centre, size, pivot in specs:
            obj = cube(name, centre)
            obj.scale = size
            objects.append((obj, pivot))
        bpy.context.view_layer.update()
        select(*[obj for obj, _pivot in objects])
        self.assertEqual(bpy.ops.rigmoves.new_move(), {"FINISHED"})
        for obj, pivot in objects:
            bpy.context.scene.cursor.location = pivot
            select(obj)
            bpy.ops.rigmoves.set_pivot(index=0, kind="CURSOR")
        return {obj.name: obj for obj, _pivot in objects}

    def chain_from(self, objects, first):
        select(objects[first], *[o for n, o in objects.items() if n != first])
        return bpy.ops.rigmoves.make_chain(index=0)

    def test_a_leaf_folded_in_pleats_chains_in_the_order_it_is_built(self):
        # Three plates hinged end to end, shut in a Z: the second folds back
        # under the first and the third out again under that, so the third's
        # pivot stands by the first's, nearer than the second's.
        plate = (1.0, 0.4, 0.04)
        objects = self.made([("Leaf3", (0.5, 0.0, -0.08), plate, (0.0, 0.0, -0.06)),
                             ("Leaf1", (0.5, 0.0, 0.0), plate, (0.0, 0.0, 0.0)),
                             ("Leaf2", (0.5, 0.0, -0.04), plate, (1.0, 0.0, -0.02))])
        move = rig().rigmoves.moves[0]
        spots = {p.name: rigmoves.part_spot(rig(), move, p) for p in move.parts}
        self.assertLess((spots["Leaf3"] - spots["Leaf1"]).length,
                        (spots["Leaf2"] - spots["Leaf1"]).length)
        self.assertEqual(self.chain_from(objects, "Leaf1"), {"FINISHED"})
        self.assertEqual(rig().rigmoves.report, "Chain: Leaf1 > Leaf2 > Leaf3")
        self.assertEqual({p.name: p.follows for p in move.parts},
                         {"Leaf1": "", "Leaf2": "Leaf1", "Leaf3": "Leaf2"})

    def test_a_straight_tentacle_made_in_no_order_with_pivots_on_the_joints(self):
        sizes = (1.0, 0.3, 0.3)
        objects = self.made([("Seg{:d}".format(n + 1), (n + 0.5, 0.0, 0.0), sizes,
                              (float(n), 0.0, 0.0)) for n in (3, 0, 4, 2, 1)])
        self.assertEqual(self.chain_from(objects, "Seg1"), {"FINISHED"})
        self.assertEqual(rig().rigmoves.report, "Chain: Seg1 > Seg2 > Seg3 > Seg4 > Seg5")

    def test_a_chain_with_gaps_between_its_segments_goes_by_the_nearest_pivot(self):
        # Nothing touches, so it is the nearest pivot, as before.
        sizes = (1.0, 0.3, 0.3)
        objects = self.made([("Seg{:d}".format(n + 1), (1.4 * n + 0.5, 0.0, 0.0), sizes,
                              (1.4 * n, 0.0, 0.0)) for n in (2, 0, 3, 1)])
        self.assertEqual(self.chain_from(objects, "Seg1"), {"FINISHED"})
        self.assertEqual(rig().rigmoves.report, "Chain: Seg1 > Seg2 > Seg3 > Seg4")

    def test_a_pivot_that_touches_an_earlier_part_is_not_taken_for_the_next(self):
        # Seg3's pivot stands on Seg1's far end too, as a branch would: of the
        # two that touch, the one whose pivot is farther from Seg1's own is next.
        sizes = (1.0, 0.3, 0.3)
        objects = self.made([("Seg1", (0.5, 0.0, 0.0), sizes, (0.0, 0.0, 0.0)),
                             ("Branch", (1.0, 0.0, 0.0), (0.2, 0.3, 0.3), (0.9, 0.0, 0.0)),
                             ("Seg2", (1.5, 0.0, 0.0), sizes, (1.0, 0.0, 0.0))])
        self.assertEqual(self.chain_from(objects, "Seg1"), {"FINISHED"})
        self.assertEqual(rig().rigmoves.report, "Chain: Seg1 > Seg2 > Branch")


class TestRingAFinger(CopyThatCase):
    """A finger of three segments, closed 30 degrees at After, made into five
    fingers round a tilted cursor: Ride Along takes whole copies of a chain,
    joint for joint, so a ring of one is a ring of whole fingers."""

    KNUCKLES = [Vector((float(n), 0.0, 0.0)) for n in range(3)]

    def setUp(self):
        super().setUp()
        scene = bpy.context.scene
        self.centre = Vector((-2.0, -1.0, 0.0))
        scene.cursor.rotation_euler = (math.radians(25.0), 0.0, 0.0)
        scene.cursor.location = self.centre
        bpy.context.view_layer.update()
        self.axis = (scene.cursor.matrix.to_3x3() @ Vector((0.0, 0.0, 1.0))).normalized()
        self.segments = []
        for number in range(3):
            segment = cube("Seg{:d}".format(number + 1), (number + 0.5, 0.0, 0.0))
            segment.scale = (1.0, 0.3, 0.3)
            self.segments.append(segment)
        bpy.context.view_layer.update()
        self.homes = [s.matrix_world.copy() for s in self.segments]
        select(*self.segments)
        bpy.ops.rigmoves.new_move()
        self.move = rig().rigmoves.moves[0]
        for segment, knuckle in zip(self.segments, self.KNUCKLES):
            scene.cursor.location = knuckle
            select(segment)
            bpy.ops.rigmoves.set_pivot(index=0, kind="CURSOR")
        scene.cursor.location = self.centre
        select(*self.segments)
        self.assertEqual(bpy.ops.rigmoves.make_chain(index=0), {"FINISHED"})
        for segment, place in zip(self.segments, self.bent(30.0)):
            segment.matrix_world = place
            bpy.context.view_layer.update()
        self.assertEqual(bpy.ops.rigmoves.record(index=0, which="AFTER"), {"FINISHED"})

    def bent_by(self, angles):
        out, carry = [], Matrix.Identity(4)
        for knuckle, home, degrees in zip(self.KNUCKLES, self.homes, angles):
            carry = carry @ turn_about(knuckle, "Y", degrees)
            out.append(carry @ home)
        return out

    def bent(self, degrees):
        return self.bent_by((degrees,) * 3)

    def turned(self, finger, count=5):
        return turn_about(self.centre, self.axis, 360.0 * finger / count)

    def ring(self, active=0, **kwargs):
        select(self.segments[active])
        kwargs.setdefault("axis", "CURSOR_Z")
        return bpy.ops.rigmoves.ring(index=0, **kwargs)

    def joint(self, number, finger):
        """The segment of this finger: 0 is the recorded one."""
        name = "Seg{:d}".format(number + 1)
        return bpy.data.objects[name if not finger else "{:s} {:d}".format(name, finger + 1)]

    def check_fingers(self, angles, count=5, fingers=None, tolerance=TOLERANCE):
        """Every finger in the pose of the recorded one at these angles,
        turned round to where it stands."""
        for finger in (range(count) if fingers is None else fingers):
            for number, place in enumerate(self.bent_by(angles[finger] if
                                                        isinstance(angles[0], tuple)
                                                        else angles)):
                obj = self.joint(number, finger)
                expected = [self.turned(finger, count) @ place @ v.co
                            for v in obj.data.vertices]
                self.assertLess(drift(obj, expected), tolerance,
                                "{:s} at finger {:d}".format(obj.name, finger))

    def test_whole_fingers_stand_round_the_cursor_joint_matched_to_joint(self):
        self.assertEqual(self.ring(count=5), {"FINISHED"})
        parts = self.move.parts
        self.assertEqual(len([p for p in parts if p.leader]), 12)
        for finger in range(1, 5):
            for number in range(3):
                part = parts["Seg{:d} {:d}".format(number + 1, finger + 1)]
                self.assertEqual(part.leader, "Seg{:d}".format(number + 1))
                self.assertEqual(part.rides_on, "" if not number else
                                 "Seg{:d} {:d}".format(number, finger + 1))
        self.assertIn("4 copies of 'Seg1' (3 joints each)", rig().rigmoves.report)
        self.assertIn("joint for joint", rig().rigmoves.report)
        # They stand at the part's Before, turned about the cursor's Z.
        for finger in range(1, 5):
            for number in range(3):
                obj = self.joint(number, finger)
                expected = [self.turned(finger) @ self.homes[number] @ v.co
                            for v in obj.data.vertices]
                self.assertLess(max((a - b).length
                                    for a, b in zip(rest_points(obj), expected)),
                                TOLERANCE, obj.name)

    def test_every_finger_curls_like_the_recorded_one_from_its_own_place(self):
        self.assertEqual(self.ring(count=5), {"FINISHED"})
        bpy.ops.rigmoves.build()
        drive(self.move, 0.0)
        self.check_fingers((0.0, 0.0, 0.0))
        drive(self.move, 0.5)
        self.check_fingers((15.0, 15.0, 15.0))
        drive(self.move, 1.0)
        self.check_fingers((30.0, 30.0, 30.0))

    def test_a_ring_on_a_built_move_builds_on_the_side(self):
        bpy.ops.rigmoves.build()
        self.assertEqual(self.ring(count=5), {"FINISHED"})
        drive(self.move, 1.0)
        self.check_fingers((30.0, 30.0, 30.0))
        drive(self.move, 0.0)
        self.check_fingers((0.0, 0.0, 0.0))

    def test_ringing_a_joint_in_the_middle_rings_it_and_the_ones_below_it(self):
        # The second segment and the third, not the first: the copies hang from
        # the first, as the second does, and are carried by it.
        self.assertEqual(self.ring(active=1, count=5), {"FINISHED"})
        riders = [p.name for p in self.move.parts if p.leader]
        self.assertEqual(len(riders), 8)
        self.assertFalse([n for n in riders if n.startswith("Seg1")])
        self.assertIsNone(bpy.data.objects.get("Seg1 2"))
        for finger in range(1, 5):
            self.assertEqual(self.move.parts["Seg3 {:d}".format(finger + 1)].rides_on,
                             "Seg2 {:d}".format(finger + 1))
            self.assertEqual(self.move.parts["Seg2 {:d}".format(finger + 1)].rides_on, "")
        bpy.ops.rigmoves.build()
        drive(self.move, 0.0)
        for finger in range(1, 5):
            for number in (1, 2):
                obj = self.joint(number, finger)
                expected = [self.turned(finger) @ self.homes[number] @ v.co
                            for v in obj.data.vertices]
                self.assertLess(drift(obj, expected), TOLERANCE, obj.name)
        # Closed, each copy is carried by the first segment's 30 degrees and
        # bends its own joints from where it stands.
        drive(self.move, 1.0)
        carried = turn_about(self.KNUCKLES[0], "Y", 30.0)
        for finger in range(1, 5):
            own = turn_about(self.KNUCKLES[1], "Y", 30.0)
            places = [carried @ self.turned(finger) @ own @ self.homes[1],
                      carried @ self.turned(finger) @ own
                      @ turn_about(self.KNUCKLES[2], "Y", 30.0) @ self.homes[2]]
            for number, place in zip((1, 2), places):
                obj = self.joint(number, finger)
                expected = [place @ v.co for v in obj.data.vertices]
                self.assertLess(drift(obj, expected), TOLERANCE, obj.name)

    def test_leads_go_to_whole_fingers_by_their_first_joint(self):
        self.assertEqual(self.ring(count=5, lead_step=-20), {"FINISHED"})
        leads = {p.name: p.lead for p in self.move.parts if p.leader}
        self.assertEqual({n: v for n, v in leads.items() if n.startswith("Seg1")},
                         {"Seg1 2": -20, "Seg1 3": -40, "Seg1 4": -40, "Seg1 5": -20})
        self.assertEqual({v for n, v in leads.items() if not n.startswith("Seg1")}, {0})
        bpy.ops.rigmoves.build()
        # Behind the recorded finger by 0, .4, .8, .8 and .4 of its travel, on
        # a control that runs 1.8 of it long.
        waits = [0.0, 0.4, 0.8, 0.8, 0.4]
        for share in (0.0, 0.5, 1.0):
            drive(self.move, share)
            angles = []
            for wait in waits:
                degrees = eased(30.0, min(1.0, max(0.0, 1.8 * share - wait)))
                angles.append((degrees,) * 3)
            # A window is written to four decimals in the driver: on a control
            # 1.8 long that is a hair under a thousandth of a unit at the tip.
            self.check_fingers(angles, tolerance=5e-4)

    def test_a_finger_with_a_joint_not_taken_up_takes_the_whole_ring_back(self):
        stock = (sorted(o.name for o in bpy.data.objects),
                 sorted(m.name for m in bpy.data.meshes), len(self.move.parts))
        was = rigmoves.newcomers
        rigmoves.newcomers = lambda context, rig_: was(context, rig_)[:-1]
        try:
            self.assertEqual(self.ring(count=5), {"CANCELLED"})
        finally:
            rigmoves.newcomers = was
        self.assertIn("none were kept", rig().rigmoves.report)
        self.assertEqual((sorted(o.name for o in bpy.data.objects),
                          sorted(m.name for m in bpy.data.meshes),
                          len(rig().rigmoves.moves[0].parts)), stock)

    def test_the_copies_of_a_joint_and_the_ones_below_it_are_not_taken_for_the_first_two(self):
        # Segments alike: a copy of the second and third looks just like a copy
        # of the first and second, and is told which it is.
        self.assertEqual(self.ring(active=1, count=3), {"FINISHED"})
        for finger in (2, 3):
            self.assertEqual(self.move.parts["Seg2 {:d}".format(finger)].leader, "Seg2")
            self.assertEqual(self.move.parts["Seg3 {:d}".format(finger)].leader, "Seg3")

    def test_a_part_that_follows_may_be_ringed_and_nothing_is_refused_for_it(self):
        # The last segment has nothing below it: it is ringed alone, and the
        # two copies ride along with it, hanging from the second segment.
        select(self.segments[2])
        self.assertEqual(bpy.ops.rigmoves.ring(index=0, count=3), {"FINISHED"})
        self.assertEqual(len([p for p in self.move.parts if p.leader]), 2)

    # -- the other tools, with copied fingers about --------------------------

    def test_spread_gives_each_copied_finger_one_lead(self):
        self.ring(count=5)
        select(self.segments[0])
        self.assertEqual(bpy.ops.rigmoves.spread(index=0, what="LEAD", order="AROUND",
                                                 by="RANGE", first=0.0, last=-40.0,
                                                 both_ways=True),
                         {"FINISHED"})
        leads = {p.name: p.lead for p in self.move.parts if p.leader}
        self.assertEqual({n: v for n, v in leads.items() if n.startswith("Seg1")},
                         {"Seg1 2": -20, "Seg1 3": -40, "Seg1 4": -40, "Seg1 5": -20})
        self.assertEqual({v for n, v in leads.items() if not n.startswith("Seg1")}, {0})
        self.assertIn("Spread the Leads of 4 riders", rig().rigmoves.report)
        self.assertIn("first joint's Lead", rig().rigmoves.report)

    def test_copies_of_a_rechained_finger_are_taken_out_and_ridden_again(self):
        self.ring(count=3)
        select(self.segments[0], self.segments[2])
        self.assertEqual(bpy.ops.rigmoves.make_chain(index=0), {"FINISHED"})
        self.assertIn("take those copies out", rig().rigmoves.report)
        names = [p.name for p in self.move.parts if p.leader]
        # What Ride Along would say to the advice as it used to read: the
        # copies are riders already, so there is nothing new to ride along.
        select(*[bpy.data.objects[n] for n in names], self.segments[0])
        self.assertEqual(bpy.ops.rigmoves.ride_along(index=0, leader="Seg1",
                                                     rig_name=rig().name), {"CANCELLED"})
        for name in names:
            index = self.move.parts.find(name)
            if index >= 0:
                self.assertEqual(bpy.ops.rigmoves.drop_rider(index=0, part=index),
                                 {"FINISHED"})
        self.assertFalse([p for p in self.move.parts if p.leader])
        select(*[bpy.data.objects[n] for n in names], self.segments[0])
        self.assertEqual(bpy.ops.rigmoves.ride_along(index=0, leader="Seg1",
                                                     rig_name=rig().name), {"FINISHED"})
        self.assertTrue([p for p in self.move.parts if p.leader])

    def test_one_copied_joint_unpaired_is_said_in_the_singular(self):
        self.ring(count=2)
        select(self.segments[0], self.segments[2])
        self.assertEqual(bpy.ops.rigmoves.make_chain(index=0), {"FINISHED"})
        self.assertIn("1 joint of a copied chain no longer rides joint for joint: "
                      "take that copy out with its x", rig().rigmoves.report)

    def test_a_selected_inner_joint_selects_its_whole_finger_for_a_spread(self):
        self.ring(count=5)
        select(self.joint(1, 2))
        self.assertEqual(bpy.ops.rigmoves.spread(index=0, what="LEAD", order="RANDOM",
                                                 by="RANGE", first=-10.0, last=-10.0,
                                                 only_selected=True), {"FINISHED"})
        leads = {p.name: p.lead for p in self.move.parts if p.leader}
        self.assertEqual({n: v for n, v in leads.items() if v}, {"Seg1 3": -10})

    def test_a_curl_is_played_by_the_copies_too(self):
        self.ring(count=5)
        bpy.ops.rigmoves.build()
        drive(self.move, 0.0)
        self.segments[0].matrix_world = turn_about(self.KNUCKLES[0], "Y", 20.0) @ self.homes[0]
        bpy.context.view_layer.update()
        select(self.segments[0])
        self.assertEqual(bpy.ops.rigmoves.curl(index=0), {"FINISHED"})
        self.assertIn("then Build", rig().rigmoves.report)
        self.assertEqual(bpy.ops.rigmoves.record(index=0, which="AFTER"), {"FINISHED"})
        bpy.ops.rigmoves.build()
        drive(self.move, 1.0)
        self.check_fingers((20.0, 20.0, 20.0))
        drive(self.move, 0.0)
        self.check_fingers((0.0, 0.0, 0.0))

    def test_a_curl_cannot_start_from_a_copied_joint(self):
        self.ring(count=3)
        select(self.joint(0, 1))
        self.assertEqual(bpy.ops.rigmoves.curl(index=0), {"CANCELLED"})
        self.assertIn("rides along with 'Seg1'", rig().rigmoves.report)

    def test_a_new_chain_says_which_copies_stop_riding_joint_for_joint(self):
        self.ring(count=5)
        # Seg3 now follows Seg1 directly: its four copies were made riding on
        # the copy of Seg2.
        select(self.segments[0], self.segments[2])
        self.assertEqual(bpy.ops.rigmoves.make_chain(index=0), {"FINISHED"})
        self.assertEqual(self.move.parts["Seg3"].follows, "Seg1")
        self.assertIn("4 joints of copied chains no longer ride joint for joint",
                      rig().rigmoves.report)


def prism(name, sides, radius, length, twist=0.25, radii=None):
    """A closed shape with no symmetry at all, so a copy of it can be told from
    a mirror image of it, or from another shape with as many vertices: the
    bottom ring's vertices are unevenly far out, and the top ring is smaller
    and turned. With `radii` all alike and no twist it is the same on both
    sides instead."""
    radii = radii or [1.0, 0.55, 0.9, 0.45, 1.1, 0.7]
    verts = []
    for scale, turn, height in ((1.0, 0.0, 0.0), (0.6, twist, length)):
        for i in range(sides):
            angle = 2.0 * math.pi * i / sides + turn
            reach = radius * scale * radii[i % len(radii)]
            verts.append((reach * math.cos(angle), reach * math.sin(angle), height))
    faces = [tuple(reversed(range(sides))), tuple(range(sides, 2 * sides))]
    for i in range(sides):
        j = (i + 1) % sides
        faces.append((i, j, sides + j, sides + i))
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    return mesh


def stood(name, mesh, matrix):
    """An object of this mesh in the scene, standing on this matrix."""
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.matrix_world = matrix
    return obj


def faces_out(mesh):
    """Whether every face of a mesh faces away from the middle of it."""
    middle = sum((v.co for v in mesh.vertices), Vector()) / len(mesh.vertices)
    return all((p.center - middle).dot(p.normal) > 0.0 for p in mesh.polygons)


class TestRingWhatIsThere(CopyThatCase):
    """The bare flower: every petal is modelled already. Ring takes them up
    instead of making copies on top of them.

    Eight outer petals on a ring about the world's Z, a leader and seven; six
    inner petals of another shape, offset round the same ring; a leaf of three
    segments with five copies of it round the same axis, and a second leaf of
    the same number of vertices and another shape. Nothing is in a move yet.
    """

    OPEN = 60.0
    BEND = 25.0
    KNUCKLES = [Vector((2.0 + 0.5 * n, 0.0, 0.3)) for n in range(3)]

    def setUp(self):
        super().setUp()
        # The leader hinged on its base, facing outwards from the world's Z.
        azimuth = math.radians(-90.0)
        self.base = (Matrix.Translation((0.4 * math.cos(azimuth), 0.4 * math.sin(azimuth),
                                         1.0))
                     @ Matrix.Rotation(azimuth, 4, "Z"))
        shape = prism("Outer Shape", 4, 0.15, 1.0)
        self.leader = stood("Outer Leader", shape, self.base)
        self.outer = [self.leader] + [
            stood("Outer {:d}".format(k + 1), shape.copy(), self.turn(k) @ self.base)
            for k in range(1, 8)]
        self.inner = []
        for k in range(6):
            spot = Matrix.Rotation(math.radians(30.0 + 60.0 * k), 4, "Z")
            self.inner.append(stood(
                "Inner {:d}".format(k + 1) if k else "Inner Leader",
                prism("Inner Shape {:d}".format(k), 4, 0.1, 0.7),
                spot @ Matrix.Translation((0.25, 0.0, 1.05))))
        # Leaf A lies along X, each segment hinged on its base about Y.
        lay = Matrix.Rotation(math.radians(90.0), 4, "Y")
        self.leaf_homes = [Matrix.Translation(k) @ lay for k in self.KNUCKLES]
        sizes = [(0.12, 0.5), (0.1, 0.44), (0.08, 0.38)]
        leaf_shape = [prism("Leaf Shape {:d}".format(n), 6, *sizes[n]) for n in range(3)]
        self.leaf = [stood("Leaf {:d}".format(n + 1), leaf_shape[n], self.leaf_homes[n])
                     for n in range(3)]
        self.leaf_copies = {}
        for k in range(1, 6):
            self.leaf_copies[k] = [
                stood("Leaf {:d} copy {:d}".format(n + 1, k + 1), leaf_shape[n].copy(),
                      self.turn(k, 6) @ self.leaf_homes[n]) for n in range(3)]
        # Leaf B: three segments as big as leaf A's, with as many vertices,
        # twisted the other way, standing between two places of the ring.
        self.other_leaf = [
            stood("Leaf B{:d}".format(n + 1),
                  prism("Leaf B Shape {:d}".format(n), 6, *sizes[n], twist=-0.5),
                  Matrix.Rotation(math.radians(30.0), 4, "Z") @ self.leaf_homes[n])
            for n in range(3)]
        bpy.context.view_layer.update()

    @staticmethod
    def turn(number, count=8):
        return Matrix.Rotation(math.radians(360.0 * number / count), 4, "Z")

    @staticmethod
    def drop(objects):
        """Delete these from the scene, as a user would."""
        for obj in objects:
            bpy.data.objects.remove(obj, do_unlink=True)
        bpy.context.view_layer.update()

    def rig_the_flower(self):
        """The leader and leaf A in one move: the leader opened, the leaf
        bent at each joint, and After recorded."""
        select(self.leader, *self.leaf)
        self.assertEqual(bpy.ops.rigmoves.new_move(), {"FINISHED"})
        self.move = rig().rigmoves.moves[0]
        select(*self.leaf)
        self.assertEqual(bpy.ops.rigmoves.make_chain(index=0), {"FINISHED"})
        self.leader.matrix_world = self.base @ Matrix.Rotation(
            math.radians(self.OPEN), 4, "X")
        carry = Matrix.Identity(4)
        for knuckle, home, segment in zip(self.KNUCKLES, self.leaf_homes, self.leaf):
            carry = carry @ turn_about(knuckle, "Y", self.BEND)
            segment.matrix_world = carry @ home
            bpy.context.view_layer.update()
        self.after_leader = rest_points(self.leader)
        self.after_leaf = [rest_points(segment) for segment in self.leaf]
        self.assertEqual(bpy.ops.rigmoves.record(index=0, which="AFTER"), {"FINISHED"})

    def ring(self, active=None, **kwargs):
        select(active or self.leader)
        kwargs.setdefault("count", 8)
        return bpy.ops.rigmoves.ring(index=0, **kwargs)

    def stock(self):
        return (sorted(o.name for o in bpy.data.objects), sorted(m.name for m in bpy.data.meshes),
                len(rig().rigmoves.moves[0].parts))

    def report(self):
        return rig().rigmoves.report

    def check_petals(self, petals, share):
        """Every petal of the ring where it should be at this share of the
        move: the leader's After, turned round the ring to its own place."""
        for number, petal in petals.items():
            if share == 0.0:
                expected = [self.turn(number) @ self.base @ v.co for v in self.leader.data.vertices]
            else:
                expected = [self.turn(number) @ p for p in self.after_leader]
            self.assertLess(drift(petal, expected), TOLERANCE, petal.name)

    def petals(self):
        return {k: self.outer[k] for k in range(1, 8)}

    # -- Use what's there ---------------------------------------------------

    def test_the_default_is_to_fill_the_gaps(self):
        props = bpy.ops.rigmoves.ring.get_rna_type().properties
        self.assertEqual(props["use"].default, "FILL")
        self.assertEqual([item.name for item in props["use"].enum_items],
                         ["Make copies", "Use what's there", "Fill the gaps"])

    def test_the_petals_that_are_there_ride_along_and_nothing_is_made(self):
        self.rig_the_flower()
        names = sorted(o.name for o in bpy.data.objects)
        meshes = len(bpy.data.meshes)
        self.assertEqual(self.ring(use="ADOPT"), {"FINISHED"})
        self.assertEqual(sorted(o.name for o in bpy.data.objects), names)
        self.assertEqual(len(bpy.data.meshes), meshes)
        riders = {p.name: p.leader for p in self.move.parts if p.leader}
        self.assertEqual(riders, {"Outer {:d}".format(k + 1): "Outer Leader"
                                  for k in range(1, 8)})
        self.assertIn("7 modelled copies of 'Outer Leader' round the 3D cursor ride "
                      "along with it (nothing new made).", self.report())

    def test_the_default_does_the_same_where_nothing_is_missing(self):
        self.rig_the_flower()
        names = sorted(o.name for o in bpy.data.objects)
        self.assertEqual(self.ring(), {"FINISHED"})
        self.assertEqual(sorted(o.name for o in bpy.data.objects), names)
        self.assertEqual(len([p for p in self.move.parts if p.leader]), 7)

    def test_what_is_left_out_is_named_and_the_reason_given(self):
        self.rig_the_flower()
        self.ring(use="ADOPT")
        # The inner petals have as many vertices and are another shape.
        report = self.report()
        self.assertEqual(report.count("is not a copy of 'Outer Leader'"), 3, report)
        for name in ("Inner 2", "Inner 4", "Inner Leader"):
            self.assertIn("'{:s}' is not a copy of 'Outer Leader'".format(name), report)
        self.assertIn("; and 3 more.", report)

    def test_adopted_petals_open_like_the_leader_turned_to_their_own_place(self):
        self.rig_the_flower()
        self.ring(use="ADOPT")
        bpy.ops.rigmoves.build()
        drive(self.move, 0.0)
        self.check_petals(self.petals(), 0.0)
        drive(self.move, 1.0)
        self.check_petals(self.petals(), 1.0)
        self.assertLess(drift(self.leader, self.after_leader), TOLERANCE)

    def test_petals_taken_up_on_a_built_move_play_at_once(self):
        self.rig_the_flower()
        bpy.ops.rigmoves.build()
        self.assertEqual(self.ring(use="ADOPT"), {"FINISHED"})
        drive(self.move, 1.0)
        self.check_petals(self.petals(), 1.0)
        drive(self.move, 0.0)
        self.check_petals(self.petals(), 0.0)

    def test_a_chain_is_taken_up_whole_and_a_second_leaf_is_left_out(self):
        self.rig_the_flower()
        names = sorted(o.name for o in bpy.data.objects)
        self.assertEqual(self.ring(active=self.leaf[0], use="ADOPT", count=6),
                         {"FINISHED"})
        self.assertEqual(sorted(o.name for o in bpy.data.objects), names)
        for k in range(1, 6):
            for n, obj in enumerate(self.leaf_copies[k]):
                part = self.move.parts[obj.name]
                self.assertEqual(part.leader, "Leaf {:d}".format(n + 1))
                self.assertEqual(part.rides_on, "" if not n else
                                 self.leaf_copies[k][n - 1].name)
        self.assertIn("5 modelled copies of 'Leaf 1' (3 joints each) round the 3D "
                      "cursor ride along with it, joint for joint (nothing new made).",
                      self.report())
        for n in range(3):
            self.assertIn("'Leaf B{:d}' is not a copy of 'Leaf {:d}'".format(n + 1, n + 1),
                          self.report())
        bpy.ops.rigmoves.build()
        drive(self.move, 1.0)
        for k, joints in self.leaf_copies.items():
            for obj, after in zip(joints, self.after_leaf):
                expected = [self.turn(k, 6) @ p for p in after]
                self.assertLess(drift(obj, expected), TOLERANCE, obj.name)

    def test_both_rings_of_the_flower_one_after_the_other_make_nothing(self):
        self.rig_the_flower()
        names = sorted(o.name for o in bpy.data.objects)
        self.assertEqual(self.ring(use="ADOPT"), {"FINISHED"})
        self.assertEqual(self.ring(active=self.leaf[0], use="ADOPT", count=6),
                         {"FINISHED"})
        self.assertEqual(sorted(o.name for o in bpy.data.objects), names)
        self.assertEqual(len([p for p in self.move.parts if p.leader]), 7 + 15)

    def test_a_chain_with_one_wrong_joint_is_left_alone_whole(self):
        # The second segment of the third copy is a mirror image: the place
        # has only part of its chain, and nothing is taken up or made there.
        wrong = self.leaf_copies[3][1]
        wrong.data.transform(Matrix.Scale(-1.0, 4, Vector((1.0, 0.0, 0.0))))
        self.rig_the_flower()
        names = sorted(o.name for o in bpy.data.objects)
        for use in ("ADOPT", "FILL"):
            self.assertEqual(self.ring(active=self.leaf[0], use=use, count=6),
                             {"FINISHED"}, use)
            self.assertEqual(sorted(o.name for o in bpy.data.objects), names, use)
            riders = {p.name for p in self.move.parts if p.leader}
            self.assertFalse(riders & {o.name for o in self.leaf_copies[3]}, use)
            self.assertEqual(len(riders), 12, use)
            self.assertIn("'Leaf 2 copy 4' stands in a place and is not a copy of 'Leaf 2'",
                          self.report())
            self.assertIn("1 place had only part of a chain standing and was left alone",
                          self.report())
            break

    def test_a_petal_off_by_a_hair_is_taken_and_one_well_off_is_not(self):
        self.rig_the_flower()
        self.outer[2].location.x += 0.005
        self.outer[5].location.x += 0.15
        bpy.context.view_layer.update()
        self.assertEqual(self.ring(use="ADOPT"), {"FINISHED"})
        riders = {p.name for p in self.move.parts if p.leader}
        self.assertIn("Outer 3", riders)
        self.assertNotIn("Outer 6", riders)
        self.assertEqual(len(riders), 6)
        # Off a hair, it is stood on its place, and says so.
        self.assertIn("1 object re-framed", self.report())

    def test_a_mirrored_petal_is_not_taken(self):
        self.drop(self.inner)
        mirror = self.outer[3]
        mirror.data.transform(Matrix.Scale(-1.0, 4, Vector((1.0, 0.0, 0.0))))
        self.rig_the_flower()
        self.assertEqual(self.ring(use="ADOPT"), {"FINISHED"})
        riders = {p.name for p in self.move.parts if p.leader}
        self.assertNotIn(mirror.name, riders)
        self.assertEqual(len(riders), 6)
        self.assertIn("Left out: '{:s}' stands in a place and is not a copy of "
                      "'Outer Leader'".format(mirror.name), self.report())

    def test_a_petal_that_is_a_copy_standing_off_the_ring_is_named_so(self):
        self.drop(self.inner)
        stray = stood("Stray", self.leader.data.copy(),
                      self.turn(0.5) @ self.base)
        self.rig_the_flower()
        self.ring(use="ADOPT")
        self.assertIn("'Stray' is a copy of 'Outer Leader' that stands off the ring",
                      self.report())
        self.assertNotIn(stray.name, {p.name for p in self.move.parts})

    def test_two_petals_on_one_place_take_it_once(self):
        self.drop(self.inner)
        twin = stood("Twin", self.outer[2].data.copy(), self.turn(2) @ self.base)
        self.rig_the_flower()
        self.ring(use="ADOPT")
        riders = {p.name for p in self.move.parts if p.leader}
        self.assertEqual(len(riders), 7)
        self.assertEqual(len(riders & {"Twin", "Outer 3"}), 1)
        self.assertIn("stands on the same place as", self.report())
        self.assertIsNotNone(twin)

    def test_what_a_move_already_plays_is_never_taken(self):
        self.rig_the_flower()
        # A petal that is a part of the move already, riding along on another
        # leader, is not for taking.
        select(self.leader, self.outer[1])
        self.assertEqual(bpy.ops.rigmoves.ride_along(index=0, leader="Outer Leader",
                                                     rig_name=rig().name), {"FINISHED"})
        riders = lambda: {p.name: p.leader for p in self.move.parts if p.leader}  # noqa: E731
        self.assertEqual(riders(), {"Outer 2": "Outer Leader"})
        # The ring starts at the place that rider holds, and skips it.
        self.assertEqual(self.ring(use="ADOPT"), {"FINISHED"})
        self.assertEqual(len(riders()), 7)
        self.assertIn("1 place already held a copy and was skipped", self.report())

    def test_nothing_that_fits_is_refused_and_leaves_nothing(self):
        self.drop(self.outer[1:])
        self.rig_the_flower()
        stock = self.stock()
        self.assertEqual(self.ring(use="ADOPT"), {"CANCELLED"})
        self.assertEqual(self.stock(), stock)
        self.assertIn("Nothing standing in the places round that ring is an exact copy of "
                      "'Outer Leader'", self.report())

    def test_hidden_petals_are_not_taken(self):
        self.drop(self.inner)
        self.outer[4].hide_set(True)
        self.rig_the_flower()
        self.assertEqual(self.ring(use="ADOPT"), {"FINISHED"})
        self.assertNotIn("Outer 5", {p.name for p in self.move.parts})
        self.assertEqual(len([p for p in self.move.parts if p.leader]), 6)

    def test_a_place_already_taken_up_is_skipped_the_next_time(self):
        self.rig_the_flower()
        self.assertEqual(self.ring(use="ADOPT"), {"FINISHED"})
        self.assertEqual(self.ring(use="ADOPT"), {"CANCELLED"})
        self.assertIn("nothing to add", self.report())

    # -- Fill the gaps ------------------------------------------------------

    def test_filling_the_gaps_makes_exactly_the_petals_that_are_missing(self):
        gone = [3, 4, 6]
        self.drop([self.outer[k] for k in gone])
        self.drop(self.inner)
        self.rig_the_flower()
        before = {o.name for o in bpy.data.objects}
        self.assertEqual(self.ring(use="FILL"), {"FINISHED"})
        made = {o.name for o in bpy.data.objects} - before
        self.assertEqual(len(made), 3)
        self.assertEqual(len([p for p in self.move.parts if p.leader]), 7)
        self.assertIn("4 modelled copies of 'Outer Leader' and 3 new ones round the 3D "
                      "cursor ride along with it.", self.report())
        # Each missing place has one petal, and none stands on another.
        spots = []
        for part in self.move.parts:
            if part.leader:
                spots.append(as_matrix_of(part.before).translation)
        for i, one in enumerate(spots):
            for other in spots[i + 1:]:
                self.assertGreater((one - other).length, 0.1)
        bpy.ops.rigmoves.build()
        drive(self.move, 1.0)
        petals = {k: self.outer[k] if k not in gone else
                  bpy.data.objects["Outer Leader {:d}".format(2 + gone.index(k))]
                  for k in range(1, 8)}
        self.check_petals(petals, 1.0)

    def test_filling_the_gaps_with_nothing_missing_makes_nothing(self):
        self.drop(self.inner)
        self.rig_the_flower()
        names = sorted(o.name for o in bpy.data.objects)
        self.ring(use="FILL")
        self.assertEqual(sorted(o.name for o in bpy.data.objects), names)

    def test_filling_the_gaps_of_a_leaf_copies_the_whole_chain_where_none_stands(self):
        self.drop(self.leaf_copies[2] + self.leaf_copies[4])
        self.rig_the_flower()
        before = {o.name for o in bpy.data.objects}
        self.assertEqual(self.ring(active=self.leaf[0], use="FILL", count=6), {"FINISHED"})
        self.assertEqual(len({o.name for o in bpy.data.objects} - before), 6)
        self.assertIn("3 modelled copies of 'Leaf 1' and 2 new ones", self.report())
        bpy.ops.rigmoves.build()
        drive(self.move, 1.0)
        riders = [p for p in self.move.parts if p.leader]
        self.assertEqual(len(riders), 15)
        for part in riders:
            self.assertTrue(part.rides_on == "" or self.move.parts[part.rides_on].leader)

    def test_making_copies_makes_one_for_every_place_whatever_stands_there(self):
        self.rig_the_flower()
        before = {o.name for o in bpy.data.objects}
        self.assertEqual(self.ring(use="COPY"), {"FINISHED"})
        self.assertEqual(len({o.name for o in bpy.data.objects} - before), 7)
        self.assertEqual({p.name for p in self.move.parts if p.leader} & before, set())
        self.assertEqual(self.report(),
                         "7 copies of 'Outer Leader' round the 3D cursor ride along with it.")

    # -- stood on the place a copy would have -------------------------------

    def bake(self, petals):
        """Apply every transform: the mesh holds the world's coordinates and
        the object is at the world's origin, unturned."""
        for petal in petals:
            world = petal.matrix_world.copy()
            petal.data.transform(world)
            petal.matrix_world = Matrix.Identity(4)

    def test_petals_with_their_transforms_applied_are_re_framed(self):
        self.drop(self.inner)
        self.bake(self.outer[1:])
        stood_at = {p.name: rest_points(p) for p in self.outer[1:]}
        self.rig_the_flower()
        self.assertEqual(self.ring(use="ADOPT"), {"FINISHED"})
        self.assertIn("7 objects re-framed to stand on their place", self.report())
        for number, petal in self.petals().items():
            self.assertTrue(same_matrix_of(petal.matrix_world, self.turn(number) @ self.base),
                            petal.name)
            # Nothing is seen to move, and the mesh is the leader's again.
            self.assertLess(max((a - b).length for a, b in
                                zip(rest_points(petal), stood_at[petal.name])), 1e-5)
            self.assertLess(max((a.co - b.co).length for a, b in
                                zip(petal.data.vertices, self.leader.data.vertices)), 1e-5)
            self.assertTrue(same_matrix_of(
                rigmoves.as_matrix(self.move.parts[petal.name].before), petal.matrix_world))
        bpy.ops.rigmoves.build()
        drive(self.move, 0.0)
        self.check_petals(self.petals(), 0.0)
        drive(self.move, 1.0)
        self.check_petals(self.petals(), 1.0)

    def test_petals_with_only_their_rotation_applied_are_re_framed_and_radiate(self):
        # Origin still on the hinge, but turned to the world's axes: a frame
        # the move would turn about the wrong way.
        self.drop(self.inner)
        for petal in self.outer[1:]:
            world = petal.matrix_world.copy()
            petal.data.transform(world.to_3x3().to_4x4())
            petal.matrix_world = Matrix.Translation(world.translation)
        self.rig_the_flower()
        self.assertEqual(self.ring(use="ADOPT"), {"FINISHED"})
        # The third petal faces along the world's X, with no rotation to
        # apply: it is on its frame already.
        self.assertIn("6 objects re-framed", self.report())
        bpy.ops.rigmoves.build()
        drive(self.move, 1.0)
        self.check_petals(self.petals(), 1.0)

    def test_a_shared_mesh_is_made_single_user_before_it_is_moved(self):
        self.drop(self.inner)
        # Seven petals and a twin elsewhere, all on one mesh whose origin is
        # off the hinge: each is on the right place with the wrong origin.
        shared = self.leader.data.copy()
        shared.name = "Shared Shape"
        slide = Matrix.Translation((0.0, 0.1, 0.0))
        shared.transform(slide.inverted())
        for k, petal in zip(range(1, 8), self.outer[1:]):
            petal.data = shared
            petal.matrix_world = self.turn(k) @ self.base @ slide
        twin = stood("Twin", shared, Matrix.Translation((5.0, 5.0, 0.0)))
        stood_at = {p.name: rest_points(p) for p in self.outer[1:] + [twin]}
        self.assertEqual(shared.users, 8)
        self.rig_the_flower()
        self.assertEqual(self.ring(use="ADOPT"), {"FINISHED"})
        self.assertIn("7 objects re-framed", self.report())
        meshes = {p.data.name for p in self.outer[1:]}
        self.assertEqual(len(meshes), 7)
        self.assertNotIn("Shared Shape", meshes)
        for petal in self.outer[1:]:
            self.assertEqual(petal.data.users, 1, petal.name)
            self.assertLess(max((a - b).length for a, b in
                                zip(rest_points(petal), stood_at[petal.name])), 1e-5)
        # The twin still has the mesh it had, where it was.
        self.assertIs(twin.data, shared)
        self.assertEqual(shared.users, 1)
        self.assertLess(max((a - b).length for a, b in
                            zip(rest_points(twin), stood_at["Twin"])), 1e-6)
        bpy.ops.rigmoves.build()
        drive(self.move, 1.0)
        self.check_petals(self.petals(), 1.0)

    def test_what_hangs_from_a_re_framed_petal_stays_where_it_is(self):
        self.drop(self.inner)
        self.bake(self.outer[1:])
        drop = stood("Dew", prism("Dew Shape", 3, 0.03, 0.05), Matrix.Translation((0.3, 0.2, 1.2)))
        drop.parent = self.outer[2]
        drop.matrix_parent_inverse = self.outer[2].matrix_world.inverted()
        bpy.context.view_layer.update()
        where = drop.matrix_world.copy()
        self.rig_the_flower()
        self.assertEqual(self.ring(use="ADOPT"), {"FINISHED"})
        self.assertTrue(same_matrix_of(drop.matrix_world, where))

    def test_a_mirrored_object_with_negative_scale_is_stood_up_with_its_faces_out(self):
        # The mesh is mirrored in the object's own space and the object scaled
        # by -1 to make up for it: it looks like the copy, with a frame that is
        # a mirror. Stood on a plain frame its faces have to be turned.
        self.drop(self.inner)
        flip = Matrix.Scale(-1.0, 4, Vector((1.0, 0.0, 0.0)))
        petal = self.outer[2]
        petal.data.transform(flip)
        rigmoves.turn_faces_over(petal.data)
        petal.matrix_world = self.turn(2) @ self.base @ flip
        self.assertLess(petal.matrix_world.determinant(), 0.0)
        self.assertTrue(faces_out(petal.data))
        stood_at = rest_points(petal)
        self.rig_the_flower()
        self.assertEqual(self.ring(use="ADOPT"), {"FINISHED"})
        self.assertIn("Outer 3", {p.name for p in self.move.parts if p.leader})
        self.assertGreater(petal.matrix_world.determinant(), 0.0)
        # The mesh was mirrored back, so its faces were turned back with it.
        self.assertTrue(faces_out(petal.data))
        self.assertLess(max((a - b).length for a, b in zip(rest_points(petal), stood_at)),
                        1e-5)

    def test_a_petal_already_on_its_place_is_not_re_framed(self):
        self.rig_the_flower()
        self.ring(use="ADOPT")
        self.assertNotIn("re-framed", self.report())

    # -- undo, and a ring that cannot be finished ---------------------------

    def test_a_ring_that_re_framed_petals_can_be_undone(self):
        self.drop(self.inner)
        self.bake(self.outer[1:])
        self.rig_the_flower()
        select(self.leader)
        was = {o.name: (rest_points(o), o.matrix_world.copy(), o.data.name)
               for o in self.outer}
        stock = self.stock()
        undo_push()
        self.assertEqual(bpy.ops.rigmoves.ring(index=0, count=8, use="ADOPT"), {"FINISHED"})
        undo_push()
        self.assertEqual(len([p for p in rig().rigmoves.moves[0].parts if p.leader]), 7)
        undo_once()
        self.assertEqual(self.stock(), stock)
        for name, (points, matrix, mesh) in was.items():
            obj = bpy.data.objects[name]
            self.assertLess(max((a - b).length for a, b in zip(rest_points(obj), points)),
                            1e-6, name)
            self.assertTrue(same_matrix_of(obj.matrix_world, matrix, 1e-6), name)
            self.assertEqual(obj.data.name, mesh)

    def test_a_ring_that_fails_puts_every_petal_back_as_it_found_it(self):
        self.drop(self.inner)
        self.bake(self.outer[1:])
        self.rig_the_flower()
        was = {o.name: (rest_points(o), o.matrix_world.copy()) for o in self.outer}
        real = rigmoves.take_riders_out
        # Ride Along is made to take none of them up.
        shy = rigmoves.RIGMOVES_OT_ride_along.execute
        rigmoves.RIGMOVES_OT_ride_along.execute = lambda self, context: {"CANCELLED"}
        try:
            self.assertEqual(self.ring(use="ADOPT"), {"CANCELLED"})
        finally:
            rigmoves.RIGMOVES_OT_ride_along.execute = shy
            rigmoves.take_riders_out = real
        self.assertIn("none were kept", self.report())
        for name, (points, matrix) in was.items():
            obj = bpy.data.objects[name]
            self.assertLess(max((a - b).length for a, b in zip(rest_points(obj), points)),
                            1e-6, name)
            self.assertTrue(same_matrix_of(obj.matrix_world, matrix, 1e-6), name)
        self.assertEqual(len([p for p in rig().rigmoves.moves[0].parts if p.leader]), 0)

    # -- the Lead step ------------------------------------------------------

    def test_a_lead_step_goes_to_the_petals_taken_up_both_ways_round(self):
        self.rig_the_flower()
        self.assertEqual(self.ring(use="ADOPT", lead_step=-10), {"FINISHED"})
        leads = {p.name: p.lead for p in self.move.parts if p.leader}
        self.assertEqual([leads["Outer {:d}".format(k + 1)] for k in range(1, 8)],
                         [-10, -20, -30, -40, -30, -20, -10])
        self.assertIn("Leads step by -10", self.report())

    def test_a_lead_step_past_the_limit_is_held_and_counted(self):
        self.rig_the_flower()
        self.ring(use="ADOPT", lead_step=-20)
        leads = {p.name: p.lead for p in self.move.parts if p.leader}
        self.assertEqual(sorted(leads.values()), [-50, -50, -50, -40, -40, -20, -20])
        self.assertIn("3 held at the limit", self.report())

    # -- 0.18.1: only what is safe to take, and nothing copied on top ---------

    def new_names(self, before):
        return {o.name for o in bpy.data.objects} - before

    def key_a_sway(self, petal):
        bpy.context.scene.frame_set(1)
        petal.keyframe_insert("rotation_euler", frame=1)
        petal.rotation_euler.x += 0.2
        petal.keyframe_insert("rotation_euler", frame=20)
        petal.rotation_euler.x -= 0.2
        bpy.context.scene.frame_set(1)
        bpy.context.view_layer.update()

    def test_a_petal_with_keys_of_its_own_is_left_alone_and_keeps_them(self):
        self.drop(self.inner)
        petal = self.outer[3]
        self.key_a_sway(petal)
        self.rig_the_flower()
        before = {o.name for o in bpy.data.objects}
        self.assertEqual(self.ring(), {"FINISHED"})
        self.assertEqual(self.new_names(before), set())
        self.assertNotIn(petal.name, {p.name for p in self.move.parts})
        self.assertEqual(len(rigmoves.own_transform_curves(petal)), 3)
        self.assertIn("'Outer 4' has keys or drivers of its own", self.report())
        self.assertIn("1 place had something standing there that is not a copy",
                      self.report())

    def test_a_keyed_petal_on_a_built_move_keeps_its_keys_through_the_ring(self):
        # Ride Along builds, and a build lifts the keys off every part.
        self.drop(self.inner)
        petal = self.outer[3]
        self.key_a_sway(petal)
        self.rig_the_flower()
        bpy.ops.rigmoves.build()
        self.assertEqual(self.ring(use="ADOPT"), {"FINISHED"})
        self.assertEqual(len(rigmoves.own_transform_curves(petal)), 3)
        self.assertIsNotNone(petal.animation_data.action)
        self.assertEqual(len([p for p in self.move.parts if p.leader]), 6)

    def test_a_petal_with_a_driver_of_its_own_is_left_alone(self):
        self.drop(self.inner)
        petal = self.outer[2]
        curve = petal.driver_add("location", 2)
        curve.driver.type = "SCRIPTED"
        curve.driver.expression = "1.0"
        bpy.context.view_layer.update()
        self.rig_the_flower()
        before = {o.name for o in bpy.data.objects}
        self.assertEqual(self.ring(), {"FINISHED"})
        self.assertEqual(self.new_names(before), set())
        self.assertNotIn(petal.name, {p.name for p in self.move.parts})
        self.assertIn("'Outer 3' has keys or drivers of its own", self.report())

    def link_from_a_library(self, names, local_objects=False):
        """Save the named petals alone in a library file, start the scene
        again with the leader, and link the petals in: what a flower looks
        like when its petals come from a library."""
        folder = tempfile.mkdtemp()
        path = os.path.join(folder, "petals.blend")
        keep = set(names)
        self.drop([o for o in bpy.data.objects if o.name not in keep])
        bpy.ops.wm.save_as_mainfile(filepath=path)
        bpy.ops.wm.read_factory_settings(use_empty=True)
        self.leader = stood("Outer Leader", prism("Outer Shape", 4, 0.15, 1.0), self.base)
        with bpy.data.libraries.load(path, link=True) as (source, target):
            target.objects = [n for n in source.objects if n in keep]
        for obj in target.objects:
            bpy.context.scene.collection.objects.link(obj)
            if local_objects:
                obj.make_local()
        bpy.context.view_layer.update()
        self.outer = [self.leader] + [bpy.data.objects[n] for n in sorted(names)]
        select(self.leader)
        self.assertEqual(bpy.ops.rigmoves.new_move(), {"FINISHED"})
        self.move = rig().rigmoves.moves[0]
        self.leader.matrix_world = self.base @ Matrix.Rotation(math.radians(self.OPEN), 4, "X")
        bpy.context.view_layer.update()
        self.assertEqual(bpy.ops.rigmoves.record(index=0, which="AFTER"), {"FINISHED"})

    def test_petals_linked_from_a_library_are_left_out_and_nothing_stacked(self):
        names = ["Outer {:d}".format(k) for k in range(2, 9)]
        self.link_from_a_library(names)
        self.assertIsNotNone(bpy.data.objects["Outer 3"].library)
        before = {o.name for o in bpy.data.objects}
        for use in ("FILL", "ADOPT"):
            self.assertEqual(self.ring(use=use), {"CANCELLED"}, use)
            self.assertEqual(self.new_names(before), set(), use)
            self.assertIn("is linked from a library", self.report(), use)
        self.assertEqual(len([p for p in self.move.parts if p.leader]), 0)

    def test_local_petals_with_a_linked_mesh_are_left_out_too(self):
        names = ["Outer {:d}".format(k) for k in range(2, 9)]
        self.link_from_a_library(names, local_objects=True)
        petal = bpy.data.objects["Outer 3"]
        self.assertIsNone(petal.library)
        self.assertIsNotNone(petal.data.library)
        before = {o.name for o in bpy.data.objects}
        self.assertEqual(self.ring(use="FILL"), {"CANCELLED"})
        self.assertEqual(self.new_names(before), set())
        self.assertIsNotNone(petal.data.library)
        self.assertIn("is linked from a library", self.report())

    def test_petals_in_a_collection_that_cannot_be_selected_are_left_out(self):
        self.drop(self.inner)
        locked = bpy.data.collections.new("Locked")
        bpy.context.scene.collection.children.link(locked)
        for petal in (self.outer[3], self.outer[4]):
            for owner in list(petal.users_collection):
                owner.objects.unlink(petal)
            locked.objects.link(petal)
        locked.hide_select = True
        bpy.context.view_layer.update()
        self.rig_the_flower()
        before = {o.name for o in bpy.data.objects}
        for use in ("FILL", "ADOPT"):
            self.assertEqual(self.ring(use=use), {"FINISHED"}, use)
            self.assertEqual(self.new_names(before), set(), use)
            riders = {p.name for p in self.move.parts if p.leader}
            self.assertEqual(len(riders), 5, use)
            self.assertIn("'Outer 4' cannot be selected", self.report(), use)
            break

    def blocked_by(self, how, why):
        """Bake the petals off their frames, give the third one something
        that reads its frame, and ring: it is left exactly as it was."""
        self.drop(self.inner)
        self.bake(self.outer[1:])
        petal = self.outer[2]
        if how == "constraint":
            petal.constraints.new("COPY_LOCATION").influence = 0.0
        elif how == "modifier":
            petal.modifiers.new("Bend", "SIMPLE_DEFORM")
        elif how == "instances":
            petal.instance_type = "VERTS"
        elif how == "follower":
            follower = bpy.data.objects.new("Follower", None)
            bpy.context.scene.collection.objects.link(follower)
            follower.constraints.new("CHILD_OF").target = petal
        elif how == "wrapped":
            skin = stood("Skin", prism("Skin Shape", 3, 0.2, 0.2),
                         Matrix.Translation((4.0, 4.0, 0.0)))
            skin.modifiers.new("Wrap", "SHRINKWRAP").target = petal
        elif how == "thick":
            # Scaled by 2 with its mesh made half the size: the solidify
            # thickness, in the object's units, would double.
            petal.data.transform(Matrix.Scale(0.5, 4))
            petal.matrix_world = Matrix.Scale(2.0, 4)
            petal.modifiers.new("Skin Depth", "SOLIDIFY")
        bpy.context.view_layer.update()
        stood_at = (petal.matrix_world.copy(), petal.data, rest_points(petal))
        meshes = len(bpy.data.meshes)
        self.rig_the_flower()
        before = {o.name for o in bpy.data.objects}
        self.assertEqual(self.ring(use="FILL"), {"FINISHED"}, how)
        self.assertEqual(self.new_names(before), set(), how)
        riders = {p.name for p in self.move.parts if p.leader}
        self.assertEqual(riders, {"Outer {:d}".format(k) for k in (2, 4, 5, 6, 7, 8)}, how)
        self.assertIs(petal.data, stood_at[1], how)
        self.assertEqual(len(bpy.data.meshes), meshes, how)
        self.assertTrue(same_matrix_of(petal.matrix_world, stood_at[0], 1e-9), how)
        self.assertLess(max((a - b).length for a, b in zip(rest_points(petal), stood_at[2])),
                        1e-9, how)
        self.assertIn("'Outer 3' cannot be re-framed safely ({:s})".format(why), self.report())

    def test_a_petal_with_a_constraint_is_left_where_it_stands(self):
        self.blocked_by("constraint", "it has constraints")

    def test_a_petal_with_a_modifier_that_reads_its_frame_is_left_where_it_stands(self):
        self.blocked_by("modifier", "its Bend modifier depends on its frame")

    def test_a_petal_that_instances_is_left_where_it_stands(self):
        self.blocked_by("instances", "it instances other objects")

    def test_a_petal_another_object_is_constrained_to_is_left_where_it_stands(self):
        self.blocked_by("follower", "'Follower' depends on it")

    def test_a_petal_another_object_wraps_onto_is_left_where_it_stands(self):
        self.blocked_by("wrapped", "'Skin' depends on it")

    def test_a_thickened_petal_at_another_scale_is_left_where_it_stands(self):
        self.blocked_by("thick", "its Skin Depth modifier depends on its frame")

    def test_the_rest_of_the_petals_are_still_re_framed_beside_the_ones_left_out(self):
        self.drop(self.inner)
        self.bake(self.outer[1:])
        self.outer[2].modifiers.new("Bend", "SIMPLE_DEFORM")
        self.rig_the_flower()
        self.assertEqual(self.ring(use="ADOPT"), {"FINISHED"})
        riders = {p.name for p in self.move.parts if p.leader}
        self.assertEqual(riders, {"Outer {:d}".format(k) for k in (2, 4, 5, 6, 7, 8)})
        self.assertIn("6 objects re-framed", self.report())
        self.assertIn("'Outer 3' cannot be re-framed safely (its Bend modifier depends on "
                      "its frame)", self.report())

    def test_what_looks_the_same_when_re_framed_is_taken(self):
        # Subdivision, a bevel at a scale of 1, an armature of another rig, a
        # child hung by its object: none of them reads the object's frame.
        self.drop(self.inner)
        self.bake(self.outer[1:])
        petal = self.outer[2]
        petal.modifiers.new("Smooth", "SUBSURF")
        petal.modifiers.new("Round", "BEVEL")
        other = bpy.data.objects.new("Other Rig", bpy.data.armatures.new("Other"))
        bpy.context.scene.collection.objects.link(other)
        petal.modifiers.new("Pose", "ARMATURE").object = other
        dew = stood("Dew", prism("Dew Shape", 3, 0.03, 0.05), Matrix.Translation((0.3, 0.2, 1.2)))
        dew.parent = petal
        dew.matrix_parent_inverse = petal.matrix_world.inverted()
        bpy.context.view_layer.update()
        looked = rigmoves.look_of(petal)
        where = dew.matrix_world.copy()
        self.rig_the_flower()
        self.assertEqual(self.ring(use="ADOPT"), {"FINISHED"})
        self.assertIn("Outer 3", {p.name for p in self.move.parts if p.leader})
        self.assertTrue(rigmoves.looks_the_same(looked, rigmoves.look_of(petal), 1e-5))
        self.assertTrue(same_matrix_of(dew.matrix_world, where, 1e-6))
        self.assertTrue(same_matrix_of(petal.matrix_world, self.turn(2) @ self.base))

    def test_a_re_frame_that_changes_the_look_is_put_back_exactly(self):
        # Past the checks made beforehand, the result is looked at: this
        # modifier bends about the object's own origin.
        self.drop(self.inner)
        self.bake(self.outer[1:])
        petal = self.outer[2]
        petal.modifiers.new("Bend", "SIMPLE_DEFORM")
        stood_at = (petal.matrix_world.copy(), petal.data, rest_points(petal))
        meshes = len(bpy.data.meshes)
        self.rig_the_flower()
        with mock.patch.object(rigmoves, "reframe_blocker", lambda *args: ""):
            self.assertEqual(self.ring(use="ADOPT"), {"FINISHED"})
        self.assertNotIn("Outer 3", {p.name for p in self.move.parts})
        self.assertIs(petal.data, stood_at[1])
        self.assertTrue(same_matrix_of(petal.matrix_world, stood_at[0], 1e-9))
        self.assertLess(max((a - b).length for a, b in zip(rest_points(petal), stood_at[2])),
                        1e-9)
        self.assertEqual(len(bpy.data.meshes), meshes)
        self.assertIn("'Outer 3' cannot be re-framed safely (re-framing it would change "
                      "how it looks)", self.report())

    def test_a_petal_wound_the_other_way_to_the_leader_is_left_out(self):
        self.drop(self.inner)
        self.bake(self.outer[1:])
        rigmoves.turn_faces_over(self.outer[2].data)
        self.rig_the_flower()
        self.assertEqual(self.ring(use="ADOPT"), {"FINISHED"})
        self.assertNotIn("Outer 3", {p.name for p in self.move.parts})
        self.assertIn("its faces point the other way to the leader's", self.report())

    def test_a_petal_with_a_child_hung_from_its_vertices_is_left_where_it_stands(self):
        # The child follows the vertices, which re-framing keeps in place; but
        # solving a vertex parent against a mesh that has just changed is
        # unreliable, and it jumped. Only a child hung by the object is held.
        self.drop(self.inner)
        self.bake(self.outer[1:])
        petal = self.outer[2]
        kids = {}
        for kind, vertices in (("VERTEX", (3, 0, 0)), ("VERTEX_3", (3, 2, 1))):
            kid = bpy.data.objects.new("Dew " + kind, None)
            bpy.context.scene.collection.objects.link(kid)
            kid.parent = petal
            kid.parent_type = kind
            kid.parent_vertices = vertices
            kid.location = (0.0, 0.0, 0.05)
            kids[kind] = kid
        bpy.context.view_layer.update()
        where = {kind: kid.matrix_world.copy() for kind, kid in kids.items()}
        stood_at = petal.matrix_world.copy()
        self.rig_the_flower()
        self.assertEqual(self.ring(use="ADOPT"), {"FINISHED"})
        self.assertNotIn("Outer 3", {p.name for p in self.move.parts if p.leader})
        bpy.context.view_layer.update()
        self.assertTrue(same_matrix_of(petal.matrix_world, stood_at, 1e-9))
        for kind, kid in kids.items():
            self.assertTrue(same_matrix_of(kid.matrix_world, where[kind], 1e-5), kind)
        self.assertIn("depends on it", self.report())

    def test_a_mirrored_petal_with_custom_normals_is_left_out(self):
        self.drop(self.inner)
        flip = Matrix.Scale(-1.0, 4, Vector((1.0, 0.0, 0.0)))
        petal = self.outer[2]
        petal.data.transform(flip)
        rigmoves.turn_faces_over(petal.data)
        petal.matrix_world = self.turn(2) @ self.base @ flip
        petal.data.normals_split_custom_set_from_vertices(
            [Vector((0.0, 0.0, 1.0)) for _v in petal.data.vertices])
        self.assertTrue(petal.data.has_custom_normals)
        self.rig_the_flower()
        self.assertEqual(self.ring(use="ADOPT"), {"FINISHED"})
        self.assertNotIn("Outer 3", {p.name for p in self.move.parts})
        self.assertIn("'Outer 3' cannot be re-framed safely (it is mirrored and has custom "
                      "normals)", self.report())

    def near_miss(self, how):
        """Make the fourth petal a near miss of the leader, rig the flower and
        fill the gaps: nothing may be copied onto the place it stands in."""
        self.drop(self.inner)
        petal = self.outer[3]
        if how == "scaled":
            petal.data.transform(Matrix.Scale(1.06, 4))
        elif how == "nudged":
            petal.data.vertices[3].co.x += 0.08
        elif how == "cut":
            editing = bmesh.new()
            editing.from_mesh(petal.data)
            editing.edges.ensure_lookup_table()
            bmesh.ops.bisect_edges(editing, edges=[editing.edges[0]], cuts=1)
            editing.to_mesh(petal.data)
            editing.free()
        elif how == "hidden":
            petal.hide_set(True)
        self.rig_the_flower()
        if how == "in a move":
            select(petal)
            self.assertEqual(bpy.ops.rigmoves.add_to_move(index=0), {"FINISHED"})
        before = {o.name for o in bpy.data.objects}
        self.assertEqual(self.ring(use="FILL"), {"FINISHED"})
        self.assertEqual(self.new_names(before), set(), how)
        self.assertEqual(len([p for p in self.move.parts if p.leader]), 6, how)
        self.assertIn("1 place had something standing there that is not a copy",
                      self.report(), how)

    def test_a_petal_scaled_a_little_occupies_its_place(self):
        self.near_miss("scaled")

    def test_a_petal_with_a_vertex_nudged_occupies_its_place(self):
        self.near_miss("nudged")

    def test_a_petal_with_an_extra_cut_occupies_its_place(self):
        self.near_miss("cut")

    def test_a_hidden_petal_occupies_its_place(self):
        self.near_miss("hidden")

    def test_a_petal_a_move_already_plays_occupies_its_place(self):
        self.near_miss("in a move")

    def test_fill_is_refused_when_the_ring_is_round_the_wrong_point(self):
        self.drop(self.inner)
        self.rig_the_flower()
        bpy.context.scene.cursor.location = (0.27, 0.0, 0.0)
        before = {o.name for o in bpy.data.objects}
        self.assertEqual(self.ring(use="FILL"), {"CANCELLED"})
        self.assertEqual(self.new_names(before), set())
        self.assertIn("7 copies of 'Outer Leader' stand near the ring but off its places: "
                      "check the centre (3D cursor), About and Count. Nothing done.",
                      self.report())
        self.assertEqual(len([p for p in self.move.parts if p.leader]), 0)

    def test_fill_is_refused_when_the_count_is_wrong(self):
        self.drop(self.inner)
        self.rig_the_flower()
        before = {o.name for o in bpy.data.objects}
        self.assertEqual(self.ring(use="FILL", count=6), {"CANCELLED"})
        self.assertEqual(self.new_names(before), set())
        self.assertIn("copies of 'Outer Leader' stand near the ring but off its places",
                      self.report())

    def test_use_what_is_there_says_the_same_as_a_note_only(self):
        self.drop(self.inner)
        self.rig_the_flower()
        bpy.context.scene.cursor.location = (0.27, 0.0, 0.0)
        self.assertEqual(self.ring(use="ADOPT"), {"CANCELLED"})
        self.assertIn("stand near the ring but off its places: check the centre (3D cursor), "
                      "About and Count.", self.report())
        self.assertNotIn("Nothing done", self.report())
        self.assertIn("Nothing standing in the places", self.report())

    def test_use_what_is_there_with_a_wrong_count_takes_what_fits_and_notes_the_rest(self):
        self.drop(self.inner)
        self.rig_the_flower()
        self.assertEqual(self.ring(use="ADOPT", count=6), {"FINISHED"})
        self.assertEqual({p.name for p in self.move.parts if p.leader}, {"Outer 5"})
        self.assertIn("stand near the ring but off its places", self.report())

    def test_making_copies_is_never_refused_for_standing_copies(self):
        self.drop(self.inner)
        self.rig_the_flower()
        bpy.context.scene.cursor.location = (0.27, 0.0, 0.0)
        self.assertEqual(self.ring(use="COPY"), {"FINISHED"})

    def test_a_ring_where_every_place_has_only_part_of_a_chain_is_refused(self):
        self.drop([self.leaf_copies[k][2] for k in range(1, 6)])
        self.rig_the_flower()
        before = {o.name for o in bpy.data.objects}
        for use in ("FILL", "ADOPT"):
            self.assertEqual(self.ring(active=self.leaf[0], use=use, count=6),
                             {"CANCELLED"}, use)
            self.assertEqual(self.new_names(before), set(), use)
            self.assertIn("Every place round that ring has only part of a chain of 'Leaf 1' "
                          "standing, so nothing was taken up or made.", self.report(), use)
            self.assertIn("fits a place where the rest of the chain is missing",
                          self.report(), use)

    def test_the_nearest_to_the_ring_are_named_first(self):
        # The inner petals, with as many vertices, come first by name.
        mirror = self.outer[3]
        mirror.data.transform(Matrix.Scale(-1.0, 4, Vector((1.0, 0.0, 0.0))))
        self.rig_the_flower()
        self.ring(use="ADOPT")
        words = self.report()
        self.assertIn("'Outer 4' ", words)
        self.assertLess(words.index("'Outer 4' "), words.index("'Inner"))

    def test_a_copy_standing_on_a_place_is_not_said_to_be_off_the_ring(self):
        self.drop(self.inner)
        self.drop([self.outer[3]])
        # On the place, with the leader's own turn: not turned to it.
        stood("Unturned", self.leader.data.copy(),
              Matrix.Translation((self.turn(3) @ self.base).translation) @ self.base.to_4x4()
              .to_3x3().to_4x4())
        # Well away from the ring.
        stood("Far Off", self.leader.data.copy(), Matrix.Translation((9.0, 9.0, 1.0)) @ self.base)
        bpy.context.view_layer.update()
        self.rig_the_flower()
        self.ring(use="ADOPT")
        words = self.report()
        self.assertIn("'Unturned' is a copy of 'Outer Leader' that is not turned to its place",
                      words)
        self.assertIn("'Far Off' is a copy of 'Outer Leader' that stands off the ring", words)
        self.assertNotIn("'Unturned' is a copy of 'Outer Leader' that stands off", words)

    def test_use_what_is_there_says_how_many_places_were_empty(self):
        self.drop(self.inner)
        self.drop([self.outer[3], self.outer[5]])
        self.rig_the_flower()
        self.assertEqual(self.ring(use="ADOPT"), {"FINISHED"})
        self.assertIn("2 places had nothing standing in them: Fill the gaps would copy the "
                      "part there.", self.report())

    def test_fill_the_gaps_does_not_say_places_were_empty_for_the_ones_it_filled(self):
        self.drop(self.inner)
        self.drop([self.outer[3]])
        self.rig_the_flower()
        self.assertEqual(self.ring(use="FILL"), {"FINISHED"})
        self.assertNotIn("had nothing standing", self.report())

    def test_the_dialog_shows_the_three_ways_to_use_and_a_lead_step(self):
        shown = []

        class Layout(Sketch):
            def prop(self, _data, name, **_kwargs):
                shown.append(name)

            def row(self, **_kwargs):
                return Layout(self.log, self.where)

        stand_in = types.SimpleNamespace(layout=Layout([]), use="FILL")
        rigmoves.RIGMOVES_OT_ring.draw(stand_in, bpy.context)
        self.assertEqual(shown, ["use", "count", "center", "axis", "linked", "lead_step"])


def as_matrix_of(values):
    return rigmoves.as_matrix(values)


def same_matrix_of(a, b, tolerance=1e-4):
    return rigmoves.same_matrix(a, b, tolerance)


def rigmoves_part(move, obj):
    return move.parts[obj.name]


class TestRingTurnedAndMirrored(CopyThatCase):
    """Petals that are the right shape on the right place with their vertices
    numbered in another order: the far half of a flower made with Ctrl+M, the
    teeth of a gear made with Shift+D and G and never turned. The same points,
    so the same copy."""

    OPEN = 50.0

    def setUp(self):
        super().setUp()
        azimuth = math.radians(-90.0)
        self.base = (Matrix.Translation((0.4 * math.cos(azimuth), 0.4 * math.sin(azimuth), 1.0))
                     @ Matrix.Rotation(azimuth, 4, "Z"))

    @staticmethod
    def turn(number, count=8):
        return Matrix.Rotation(math.radians(360.0 * number / count), 4, "Z")

    def flower_with_a_mirrored_half(self):
        """A leader and seven petals the same on both sides; petals 6, 7 and 8
        are the mirror images, across the world's X, of petals 4, 3 and 2."""
        shape = prism("Even Shape", 4, 0.15, 1.0, twist=0.0, radii=[1.0])
        self.leader = stood("Outer Leader", shape, self.base)
        self.outer = [self.leader]
        flip = Matrix.Scale(-1.0, 4, Vector((1.0, 0.0, 0.0)))
        for k in range(1, 8):
            if k <= 4:
                matrix = self.turn(k) @ self.base
            else:
                matrix = flip @ self.turn(8 - k) @ self.base
            self.outer.append(stood("Outer {:d}".format(k + 1), shape.copy(), matrix))
        bpy.context.view_layer.update()

    def rig_the_leader(self):
        select(self.leader)
        self.assertEqual(bpy.ops.rigmoves.new_move(), {"FINISHED"})
        self.move = rig().rigmoves.moves[0]
        self.leader.matrix_world = self.base @ Matrix.Rotation(math.radians(self.OPEN), 4, "X")
        bpy.context.view_layer.update()
        self.after = rest_points(self.leader)
        self.assertEqual(bpy.ops.rigmoves.record(index=0, which="AFTER"), {"FINISHED"})

    def same_points(self, one, other, tolerance=1e-4):
        """Whether two objects' points are the same set, in any order."""
        a, b = world_points(one), other
        return (all(min((p - q).length for q in b) <= tolerance for p in a)
                and all(min((p - q).length for q in a) <= tolerance for p in b))

    def check_opening(self, share):
        for number in range(1, 8):
            petal = self.outer[number]
            if share == 0.0:
                expected = [self.turn(number) @ self.base @ v.co
                            for v in self.leader.data.vertices]
            else:
                expected = [self.turn(number) @ p for p in self.after]
            self.assertTrue(self.same_points(petal, expected), petal.name)

    def test_a_mirrored_half_made_with_ctrl_m_is_taken_up_in_either_mode(self):
        for use in ("ADOPT", "FILL"):
            bpy.ops.wm.read_factory_settings(use_empty=True)
            self.flower_with_a_mirrored_half()
            self.rig_the_leader()
            before = {o.name for o in bpy.data.objects}
            self.assertEqual(self.ring_it(use), {"FINISHED"}, use)
            self.assertEqual({o.name for o in bpy.data.objects}, before, use)
            self.assertEqual({p.name for p in self.move.parts if p.leader},
                             {"Outer {:d}".format(k) for k in range(2, 9)}, use)
            self.assertIn("3 objects re-framed", rig().rigmoves.report, use)

    def ring_it(self, use, **kwargs):
        select(self.leader)
        return bpy.ops.rigmoves.ring(index=0, count=8, use=use, **kwargs)

    def test_a_mirrored_half_is_stood_on_a_plain_frame_with_its_faces_out(self):
        self.flower_with_a_mirrored_half()
        self.rig_the_leader()
        mirrored = self.outer[5]
        self.assertLess(mirrored.matrix_world.determinant(), 0.0)
        volume = rigmoves.signed_volume(self.leader.data)
        self.assertNotEqual(volume, 0.0)
        self.assertEqual(self.ring_it("ADOPT"), {"FINISHED"})
        for number in (5, 6, 7):
            petal = self.outer[number]
            self.assertGreater(petal.matrix_world.determinant(), 0.0, petal.name)
            self.assertTrue(same_matrix_of(petal.matrix_world,
                                           self.turn(number) @ self.base), petal.name)
            self.assertAlmostEqual(rigmoves.signed_volume(petal.data), volume, places=6,
                                   msg=petal.name)

    def test_a_mirrored_half_opens_like_the_leader_from_its_own_place(self):
        self.flower_with_a_mirrored_half()
        self.rig_the_leader()
        self.ring_it("ADOPT")
        bpy.ops.rigmoves.build()
        drive(self.move, 0.0)
        self.check_opening(0.0)
        drive(self.move, 1.0)
        self.check_opening(1.0)

    def test_fill_the_gaps_stacks_nothing_on_a_mirrored_half(self):
        self.flower_with_a_mirrored_half()
        self.rig_the_leader()
        before = {o.name for o in bpy.data.objects}
        self.assertEqual(self.ring_it("FILL"), {"FINISHED"})
        self.assertEqual({o.name for o in bpy.data.objects} - before, set())

    def gear(self):
        """Four cube teeth made with Shift+D and G, never turned."""
        self.leader = cube("Tooth", (3.0, 0.0, 0.0))
        self.teeth = [self.leader] + [
            cube("Tooth.00{:d}".format(k), where)
            for k, where in enumerate([(0.0, 3.0, 0.0), (-3.0, 0.0, 0.0), (0.0, -3.0, 0.0)],
                                      start=1)]
        select(self.leader)
        self.assertEqual(bpy.ops.rigmoves.new_move(), {"FINISHED"})
        self.move = rig().rigmoves.moves[0]
        self.leader.matrix_world = Matrix.Translation((3.0, 0.0, 0.0)) @ Matrix.Rotation(
            math.radians(40.0), 4, "Y")
        bpy.context.view_layer.update()
        self.after = rest_points(self.leader)
        self.assertEqual(bpy.ops.rigmoves.record(index=0, which="AFTER"), {"FINISHED"})

    def test_cubes_moved_without_being_turned_are_taken_up_as_a_gear(self):
        self.gear()
        before = {o.name for o in bpy.data.objects}
        select(self.leader)
        self.assertEqual(bpy.ops.rigmoves.ring(index=0, count=4, use="ADOPT", center="ORIGIN"),
                         {"FINISHED"})
        self.assertEqual({o.name for o in bpy.data.objects}, before)
        self.assertEqual(len([p for p in self.move.parts if p.leader]), 3)
        self.assertIn("3 objects re-framed", rig().rigmoves.report)
        bpy.ops.rigmoves.build()
        drive(self.move, 1.0)
        for number, tooth in enumerate(self.teeth[1:], start=1):
            expected = [Matrix.Rotation(math.radians(90.0 * number), 4, "Z") @ p
                        for p in self.after]
            self.assertTrue(self.same_points(tooth, expected), tooth.name)

    def test_fill_the_gaps_makes_no_tooth_on_top_of_a_tooth(self):
        self.gear()
        before = {o.name for o in bpy.data.objects}
        select(self.leader)
        self.assertEqual(bpy.ops.rigmoves.ring(index=0, count=4, center="ORIGIN"),
                         {"FINISHED"})
        self.assertEqual({o.name for o in bpy.data.objects} - before, set())

    def test_an_asymmetric_petal_mirrored_is_still_never_taken(self):
        shape = prism("Odd Shape", 4, 0.15, 1.0)
        self.leader = stood("Outer Leader", shape, self.base)
        flip = Matrix.Scale(-1.0, 4, Vector((1.0, 0.0, 0.0)))
        stood("Outer 2", shape.copy(), flip @ self.turn(7) @ self.base)
        bpy.context.view_layer.update()
        self.rig_the_leader()
        before = {o.name for o in bpy.data.objects}
        self.assertEqual(self.ring_it("ADOPT"), {"CANCELLED"})
        self.assertEqual({o.name for o in bpy.data.objects}, before)


class RingFlows(CopyThatCase):
    """What the 0.19 review of Ring found, played the way a person would: the
    petals, the frames and the cursor are the ones the review used."""

    def setUp(self):
        super().setUp()
        bpy.context.scene.cursor.location = (0.0, 0.0, 0.0)
        azimuth = math.radians(-90.0)
        self.base = (Matrix.Translation((0.4 * math.cos(azimuth), 0.4 * math.sin(azimuth), 1.0))
                     @ Matrix.Rotation(azimuth, 4, "Z"))

    @staticmethod
    def turn(number, count=8):
        return Matrix.Rotation(math.radians(360.0 * number / count), 4, "Z")

    def report(self):
        return rig().rigmoves.report

    def riders(self):
        return {p.name: p.lead for p in rig().rigmoves.moves[0].parts if p.leader}

    def record_after(self, leader, turned=50.0, build=False):
        """New Move on the leader, opened by hand, Record After."""
        select(leader)
        self.assertEqual(bpy.ops.rigmoves.new_move(), {"FINISHED"})
        self.rest = rest_points(leader)
        leader.matrix_world = leader.matrix_world @ Matrix.Rotation(math.radians(turned), 4, "X")
        bpy.context.view_layer.update()
        self.after = rest_points(leader)
        self.assertEqual(bpy.ops.rigmoves.record(index=0, which="AFTER"), {"FINISHED"})
        if build:
            self.assertEqual(bpy.ops.rigmoves.build(), {"FINISHED"})
        self.move = rig().rigmoves.moves[0]

    def ring(self, leader, **kwargs):
        select(leader)
        kwargs.setdefault("count", 8)
        return bpy.ops.rigmoves.ring(index=0, **kwargs)

    def what_is_there(self):
        """Everything a ring could change, to compare before and after: each
        object's frame, its mesh and where its vertices are, and the meshes
        there are."""
        return ({o.name: (o.matrix_world.copy(), o.data.name if o.data else None,
                          rest_points(o) if o.type == "MESH" else None)
                 for o in bpy.data.objects},
                sorted((m.name, m.users) for m in bpy.data.meshes),
                len(rig().rigmoves.moves[0].parts))

    def assert_as_found(self, was):
        frames, meshes, parts = self.what_is_there()
        self.assertEqual(sorted(frames), sorted(was[0]))
        for name, (matrix, mesh, points) in was[0].items():
            self.assertTrue(same_matrix_of(frames[name][0], matrix, 1e-6), name)
            self.assertEqual(frames[name][1], mesh, name)
            if points is not None:
                self.assertLess(max((a - b).length for a, b in zip(frames[name][2], points)),
                                1e-6, name)
        self.assertEqual(meshes, was[1])
        self.assertEqual(parts, was[2])


class TestRingPetalsSharingOneMesh(RingFlows):
    """Petals made with Alt+D share one mesh. With Apply Rotation on the leader
    alone, every one of the seven stands on a frame of its own, and is re-framed
    to a mesh of its own: the mesh they shared goes once, not once for each."""

    def alt_d_flower(self):
        mesh = prism("Petal Shape", 4, 0.15, 1.0)
        self.petal = stood("Petal", mesh,
                           Matrix.Translation((0.0, -0.4, 1.0))
                           @ Matrix.Rotation(math.radians(-90.0), 4, "Z")
                           @ Matrix.Rotation(math.radians(20.0), 4, "Y"))
        bpy.context.view_layer.update()
        for k in range(1, 8):
            select(self.petal)
            self.assertEqual(bpy.ops.object.duplicate(linked=True), {"FINISHED"})
            bpy.context.view_layer.objects.active.matrix_world = (
                self.turn(k) @ self.petal.matrix_world)
        bpy.context.view_layer.update()
        self.assertEqual(mesh.users, 8)
        # Ctrl+A > Rotation: Blender gives the leader a mesh of its own to do it.
        select(self.petal)
        self.assertEqual(bpy.ops.object.transform_apply(
            location=False, rotation=True, scale=False, isolate_users=True), {"FINISHED"})
        bpy.context.view_layer.update()
        self.assertEqual(mesh.users, 7)
        self.record_after(self.petal, build=True)
        self.others = [bpy.data.objects["Petal.{:03d}".format(k)] for k in range(1, 8)]

    def test_the_ring_finishes_and_each_petal_has_a_mesh_of_its_own(self):
        self.alt_d_flower()
        stood_at = {o.name: rest_points(o) for o in self.others}
        self.assertEqual(self.ring(self.petal, lead_step=-10), {"FINISHED"})
        self.assertEqual(len(self.riders()), 7)
        self.assertEqual(sorted(self.riders().values()), [-40, -30, -30, -20, -20, -10, -10])
        self.assertIn("7 objects re-framed", self.report())
        self.assertEqual(len({o.data.name for o in self.others}), 7)
        for petal in self.others:
            self.assertEqual(petal.data.users, 1, petal.name)
            self.assertLess(max((a - b).length for a, b in zip(rest_points(petal),
                                                              stood_at[petal.name])), 1e-5)
        # The mesh they shared is gone, and nothing is left unused.
        self.assertEqual([m.name for m in bpy.data.meshes if m.users == 0], [])

    def test_the_petals_then_play_like_the_leader_from_their_own_places(self):
        self.alt_d_flower()
        self.assertEqual(self.ring(self.petal), {"FINISHED"})
        for number, petal in enumerate(self.others, start=1):
            drive(self.move, 0.0)
            self.assertLess(drift(petal, [self.turn(number) @ p for p in self.rest]),
                            TOLERANCE, petal.name)
            drive(self.move, 1.0)
            self.assertLess(drift(petal, [self.turn(number) @ p for p in self.after]),
                            TOLERANCE, petal.name)

    def test_one_undo_takes_the_whole_ring_back(self):
        self.alt_d_flower()
        select(self.petal)
        was = self.what_is_there()
        undo_push()
        self.assertEqual(bpy.ops.rigmoves.ring(index=0, count=8, lead_step=-10),
                         {"FINISHED"})
        undo_push()
        self.assertEqual(len(self.riders()), 7)
        undo_once()
        self.assertEqual(len([p for p in rig().rigmoves.moves[0].parts if p.leader]), 0)
        self.assert_as_found(was)
        self.assertEqual(bpy.data.meshes["Petal Shape"].users, 7)

    def test_a_ring_that_fails_at_the_end_puts_everything_back(self):
        # Whatever goes wrong after Ride Along - here the mesh clean-up - takes
        # the riders out and puts every petal back as it was found, and says so.
        self.alt_d_flower()
        was = self.what_is_there()
        with mock.patch.object(rigmoves, "settle", side_effect=RuntimeError("boom")):
            self.assertEqual(self.ring(self.petal, lead_step=-10), {"CANCELLED"})
        self.assertEqual(self.report(),
                         "Ring could not be finished: boom. Nothing was changed.")
        self.assertEqual(self.riders(), {})
        self.assert_as_found(was)
        self.assertEqual(bpy.data.meshes["Petal Shape"].users, 7)

    def test_a_ring_that_fails_while_stepping_the_leads_puts_everything_back(self):
        self.alt_d_flower()
        was = self.what_is_there()
        with mock.patch.object(rigmoves, "spread_put", side_effect=ValueError("no good.")):
            self.assertEqual(self.ring(self.petal, lead_step=-10), {"CANCELLED"})
        self.assertEqual(self.report(),
                         "Ring could not be finished: no good. Nothing was changed.")
        self.assertEqual(self.riders(), {})
        self.assert_as_found(was)

    def test_copies_made_for_a_ring_that_fails_are_taken_away_again(self):
        self.alt_d_flower()
        was = self.what_is_there()
        with mock.patch.object(rigmoves, "spread_put", side_effect=ValueError("no good")):
            self.assertEqual(self.ring(self.petal, use="COPY", lead_step=-10),
                             {"CANCELLED"})
        self.assertIn("Ring could not be finished: no good. Nothing was changed.",
                      self.report())
        self.assert_as_found(was)

    def test_the_mesh_of_petals_still_used_elsewhere_is_kept(self):
        # A twin that is not part of the ring still has the mesh the petals
        # shared: it stays, with its name, and the petals get names of their own.
        self.alt_d_flower()
        shared = self.others[0].data
        twin = stood("Twin", shared, Matrix.Translation((6.0, 6.0, 0.0)))
        self.assertEqual(self.ring(self.petal), {"FINISHED"})
        self.assertIs(twin.data, shared)
        self.assertEqual(shared.users, 1)
        for petal in self.others:
            self.assertIsNot(petal.data, shared)
            self.assertEqual(petal.data.users, 1, petal.name)


def curves_in(action, slot=None):
    """(data path, index) of every curve an action holds - of one slot, or of
    all of them - read from the channelbags."""
    return sorted((curve.data_path, curve.array_index)
                  for layer in action.layers for strip in layer.strips
                  for bag in strip.channelbags
                  if slot is None or bag.slot_handle == slot.handle
                  for curve in bag.fcurves)


class TestSharedActions(CopyThatCase):
    """A part keyed on its own transform has the keys lifted when it is built. An
    action another object plays too is that object's as much as the part's: it
    must keep what it has."""

    def keyed_gear(self):
        """A gear that rises from 1 to 3 over twenty frames, keyed on location."""
        self.gear = cube("Gear", (0.0, 0.0, 1.0))
        scene = bpy.context.scene
        scene.frame_set(1)
        self.gear.keyframe_insert("location", frame=1)
        self.gear.location.z = 3.0
        self.gear.keyframe_insert("location", frame=20)
        scene.frame_set(1)

    def lamp_in_the_same_action(self):
        """Another object plays the gear's action under a slot of its own, as
        the Action editor leaves it: assigned, then keyed on its height."""
        self.keyed_gear()
        self.lamp = cube("Lamp", (5.0, 0.0, 1.0))
        scene = bpy.context.scene
        self.lamp.animation_data_create()
        self.lamp.animation_data.action = self.gear.animation_data.action
        self.lamp.keyframe_insert("location", index=2, frame=1)
        self.lamp.location.z = 4.0
        self.lamp.keyframe_insert("location", index=2, frame=20)
        scene.frame_set(1)
        self.assertEqual(len(self.gear.animation_data.action.slots), 2)

    def twin_by_alt_d(self):
        self.keyed_gear()
        select(self.gear)
        self.assertEqual(bpy.ops.object.duplicate(linked=True), {"FINISHED"})
        self.twin = bpy.context.view_layer.objects.active
        self.twin.location.x += 4.0
        self.assertEqual(self.twin.animation_data.action, self.gear.animation_data.action)
        self.assertEqual(self.twin.animation_data.action_slot.identifier,
                         self.gear.animation_data.action_slot.identifier)

    @staticmethod
    def height_at(obj, frame):
        bpy.context.scene.frame_set(frame)
        return obj.matrix_world.translation.z

    def build_the_gear(self):
        """The gear turned a quarter about X for its After, and Build."""
        bpy.context.scene.frame_set(1)
        select(self.gear)
        self.assertEqual(bpy.ops.rigmoves.new_move(), {"FINISHED"})
        self.gear.rotation_euler.x = math.radians(90.0)
        bpy.context.view_layer.update()
        self.after = rest_points(self.gear)
        self.assertEqual(bpy.ops.rigmoves.record(index=0, which="AFTER"), {"FINISHED"})
        self.assertEqual(bpy.ops.rigmoves.build(), {"FINISHED"})

    def test_a_part_reads_only_the_curves_of_its_own_slot(self):
        self.lamp_in_the_same_action()
        self.assertEqual(len(rigmoves.own_transform_curves(self.gear)), 3)
        self.assertEqual(len(rigmoves.own_transform_curves(self.lamp)), 1)
        # Nothing to play: no slot, no keys of its own.
        spare = cube("Spare", (9.0, 0.0, 0.0))
        spare.animation_data_create()
        spare.animation_data.action = self.gear.animation_data.action
        self.assertIsNone(spare.animation_data.action_slot)
        self.assertEqual(rigmoves.own_transform_curves(spare), [])

    def test_building_the_gear_leaves_the_twin_its_keys(self):
        self.twin_by_alt_d()
        frames = (1, 10, 20)
        was = [self.height_at(self.twin, f) for f in frames]
        self.assertGreater(was[1], 1.5)
        self.build_the_gear()
        self.assertEqual([round(self.height_at(self.twin, f), 6) for f in frames],
                         [round(z, 6) for z in was])
        self.assertEqual(len(rigmoves.own_transform_curves(self.twin)), 3)
        # The gear's own keys are lifted, and it plays the move at any frame.
        self.assertEqual(rigmoves.own_transform_curves(self.gear), [])
        self.assertIn("3 stray keyframe track(s) on the parts", rig().rigmoves.report)
        move = rig().rigmoves.moves[0]
        for frame in frames:
            bpy.context.scene.frame_set(frame)
            drive(move, 1.0)
            self.assertLess(drift(self.gear, self.after), TOLERANCE, frame)

    def test_the_part_given_a_copy_has_none_left_over(self):
        self.twin_by_alt_d()
        original = self.twin.animation_data.action
        self.build_the_gear()
        # The copy made for the gear was emptied and went; the twin has the
        # action the two shared, to itself now.
        self.assertIsNone(self.gear.animation_data.action)
        self.assertEqual(self.twin.animation_data.action.name, original.name)
        self.assertEqual(original.users, 1)
        self.assertEqual([a.name for a in bpy.data.actions if a.name.startswith(original.name)
                          and a.name != original.name], [])

    def test_building_the_gear_leaves_another_slot_of_its_action_its_curve(self):
        self.lamp_in_the_same_action()
        action = self.gear.animation_data.action
        everything = curves_in(action)
        self.assertEqual(len(everything), 4)
        was = [self.height_at(self.lamp, f) for f in (1, 10, 20)]
        self.assertAlmostEqual(was[2], 4.0, places=5)
        self.build_the_gear()
        self.assertEqual([round(self.height_at(self.lamp, f), 6) for f in (1, 10, 20)],
                         [round(z, 6) for z in was])
        self.assertEqual(curves_in(action), everything)
        self.assertEqual(curves_in(action, self.lamp.animation_data.action_slot),
                         [("location", 2)])
        self.assertEqual(rigmoves.own_transform_curves(self.gear), [])
        # Counted: the gear's three tracks, not the lamp's as a fourth.
        self.assertIn("3 stray keyframe track(s) on the parts", rig().rigmoves.report)
        self.assertNotIn("4 stray", rig().rigmoves.report)

    def test_the_lift_button_takes_only_the_parts_own_keys_and_counts_them(self):
        self.lamp_in_the_same_action()
        select(self.gear)
        self.assertEqual(bpy.ops.rigmoves.new_move(), {"FINISHED"})
        was = [self.height_at(self.lamp, f) for f in (1, 10, 20)]
        self.assertEqual(bpy.ops.rigmoves.free_keys(), {"FINISHED"})
        self.assertIn("3 keyframe track(s) lifted off the parts", rig().rigmoves.report)
        self.assertEqual(rigmoves.own_transform_curves(self.gear), [])
        self.assertEqual([round(self.height_at(self.lamp, f), 6) for f in (1, 10, 20)],
                         [round(z, 6) for z in was])

    def test_an_action_played_by_one_object_is_lifted_in_place_as_before(self):
        # Nobody else plays it: no copy is made, and the action is emptied and
        # taken off the part, as it always was.
        self.keyed_gear()
        name = self.gear.animation_data.action.name
        self.build_the_gear()
        self.assertIsNone(self.gear.animation_data.action)
        self.assertIsNone(bpy.data.actions.get(name))
        self.assertIn("3 stray keyframe track(s) on the parts", rig().rigmoves.report)


class TestRingAnimatedChild(RingFlows):
    """Eight petals modelled in place, with every origin left at the world's
    origin - the most ordinary way to model them - and something hung from the
    petals. Ring stands the petals on their frames, and holds what hangs from
    them where it is by rewriting its own transform: not an animated child,
    which its own keys, drivers or NLA strips rewrite on the next frame."""

    def modelled_flower(self):
        shape = prism("Petal Shape", 4, 0.15, 1.0)
        self.petals = []
        for k in range(8):
            mesh = shape.copy()
            mesh.transform(self.turn(k) @ self.base)
            self.petals.append(stood("Petal" if not k else "Petal {:d}".format(k + 1),
                                     mesh, Matrix.Identity(4)))
        bpy.context.view_layer.update()
        self.leader = self.petals[0]

    def hang(self, name, petal):
        """A small object parented to a petal with Ctrl+P > Object."""
        kid = stood(name, prism(name + " Shape", 3, 0.03, 0.05), Matrix.Translation((0.0, 0.0, 0.0)))
        select(kid, petal)
        bpy.context.view_layer.objects.active = petal
        self.assertEqual(bpy.ops.object.parent_set(type="OBJECT", keep_transform=False),
                         {"FINISHED"})
        return kid

    def key_a_flight(self, kid):
        scene = bpy.context.scene
        scene.frame_set(1)
        kid.keyframe_insert("location", frame=1)
        kid.location.x += 0.3
        kid.location.z += 0.2
        kid.keyframe_insert("location", frame=10)
        kid.location.x -= 0.3
        kid.location.z -= 0.2
        scene.frame_set(1)

    def worked_by_a_driver(self, kid):
        curve = kid.driver_add("location", 2)
        curve.driver.type = "SCRIPTED"
        curve.driver.expression = "0.1 * frame"

    def worked_by_the_nla(self, kid):
        self.key_a_flight(kid)
        action = kid.animation_data.action
        kid.animation_data.nla_tracks.new().strips.new("Flight", 1, action)
        kid.animation_data.action = None

    def seen_at(self, kids, frames=(1, 10)):
        out = {}
        for frame in frames:
            bpy.context.scene.frame_set(frame)
            out[frame] = {kid.name: world_points(kid) for kid in kids}
        bpy.context.scene.frame_set(1)
        return out

    def ring_it(self, **kwargs):
        self.record_after(self.leader, turned=60.0)
        return self.ring(self.leader, **kwargs)

    def check_the_bee(self, how):
        self.modelled_flower()
        bee = self.hang("Bee", self.petals[3])
        how(bee)
        dew = self.hang("Dewdrop", self.petals[2])
        bpy.context.scene.frame_set(1)
        bpy.context.view_layer.update()
        was = self.seen_at([bee, dew])
        self.assertEqual(self.ring_it(), {"FINISHED"})
        # Petal 4 is left where it stands, and named, with the reason.
        self.assertNotIn("Petal 4", self.riders())
        self.assertEqual(len(self.riders()), 6)
        self.assertIn("'Petal 4' cannot be re-framed safely (has a child with keys or "
                      "drivers of its own ('Bee'))", self.report())
        # The bee plays exactly as before. So does the dewdrop, that is held
        # where it hung by the petal that was re-framed.
        now = self.seen_at([bee, dew])
        for frame in (1, 10):
            for kid in (bee, dew):
                self.assertLess(drift_of(now[frame][kid.name], was[frame][kid.name]), 1e-5,
                                (kid.name, frame))
        # The leader's frame is the world's, so a petal's is its place's turn.
        self.assertIn("Petal 3", self.riders())
        self.assertTrue(same_matrix_of(self.petals[2].matrix_world, self.turn(2)))

    def test_a_petal_with_a_keyed_child_is_left_out_and_the_child_plays_as_before(self):
        self.check_the_bee(self.key_a_flight)

    def test_a_petal_with_a_child_driven_by_a_driver_is_left_out_too(self):
        self.check_the_bee(self.worked_by_a_driver)

    def test_a_petal_with_a_child_in_the_nla_is_left_out_too(self):
        self.check_the_bee(self.worked_by_the_nla)

    def test_a_child_that_is_not_animated_is_still_held_where_it_is(self):
        self.modelled_flower()
        dew = self.hang("Dewdrop", self.petals[3])
        bpy.context.view_layer.update()
        was = world_points(dew)
        self.assertEqual(self.ring_it(), {"FINISHED"})
        self.assertEqual(len(self.riders()), 7)
        self.assertNotIn("child with keys", self.report())
        self.assertLess(drift_of(world_points(dew), was), 1e-5)

    def test_without_the_blocker_the_keyed_bee_would_fly_off(self):
        # What happens to a keyed child of a petal that is re-framed anyway:
        # the fault the blocker keeps away, to show the others test something.
        self.modelled_flower()
        bee = self.hang("Bee", self.petals[3])
        self.key_a_flight(bee)
        was = self.seen_at([bee])
        with mock.patch.object(rigmoves, "has_own_motion", lambda obj: False):
            self.assertEqual(self.ring_it(), {"FINISHED"})
        self.assertGreater(drift_of(self.seen_at([bee])[10]["Bee"], was[10]["Bee"]), 0.1)


def drift_of(points, expected):
    """How far the furthest of these points is from the same one of the others."""
    return max((a - b).length for a, b in zip(points, expected))


class TestSpreadDialogFollowsItsSettings(CopyThatCase):
    """The dialog sizes its Step for the way it opens. Until somebody types a Step
    of their own, every setting that changes the places the parts take sizes it
    again, so what the dialog shows is what OK does. The callbacks Blender runs
    when a field is changed are run here by hand, against what the dialog holds."""

    def lifted(self, objects):
        select(*objects)
        self.assertEqual(bpy.ops.rigmoves.new_move(), {"FINISHED"})
        for obj in objects:
            obj.location.z += 1.0
        bpy.context.view_layer.update()
        self.assertEqual(bpy.ops.rigmoves.record(index=0, which="AFTER"), {"FINISHED"})
        self.move = rig().rigmoves.moves[0]

    def ride(self, leader, where, name):
        obj = cube(name, where)
        select(leader, obj)
        self.assertEqual(bpy.ops.rigmoves.ride_along(index=0, leader=leader.name,
                                                     rig_name=rig().name), {"FINISHED"})
        return obj

    def crown(self, count=11):
        """A leader on a ring of count + 1 places, and a rider on each of the rest."""
        places = ring_places((2.0, 1.0, 3.0), count + 1, 3.0)
        self.leader = cube("Leader", places.pop(0))
        self.lifted([self.leader])
        self.riders = [self.ride(self.leader, where, "R{:d}".format(number))
                       for number, where in enumerate(places)]
        select(self.leader)

    def dominoes(self, count=8):
        """A leader at one end of a row along X, and a rider on each of the next places."""
        self.leader = cube("Leader", (0.0, 0.0, 0.0))
        self.lifted([self.leader])
        self.riders = [self.ride(self.leader, (float(number + 1), 0.0, 0.0),
                                 "R{:d}".format(number)) for number in range(count)]
        select(self.leader)

    def leads(self):
        return [p.lead for p in self.move.parts if p.leader]

    @staticmethod
    def dialog(what="LEAD", **given):
        """What Spread... holds when its dialog is opened (invoke has run), and
        how it was run: `given` are settings the caller passed, which are set."""
        stand_in = types.SimpleNamespace(
            index=0, what=what, order="AROUND", axis="X", seed=1, only_selected=False,
            both_ways=False, start=0.0, step=0.0, first=0.0, last=0.0, by="STEP",
            sizing=False, report=lambda *args: None,
            properties=types.SimpleNamespace(is_property_set=lambda name: name in given))
        for name, value in given.items():
            setattr(stand_in, name, value)
        stand_in.plan = lambda context: rigmoves.RIGMOVES_OT_spread.plan(stand_in, bpy.context)
        stand_in.sized = lambda *args: rigmoves.RIGMOVES_OT_spread.sized(stand_in, *args)
        opened = types.SimpleNamespace(
            window_manager=types.SimpleNamespace(invoke_props_dialog=lambda op: {"RUNNING_MODAL"}),
            scene=bpy.context.scene, view_layer=bpy.context.view_layer,
            selected_objects=bpy.context.selected_objects, selected_pose_bones=None)
        assert rigmoves.RIGMOVES_OT_spread.invoke(stand_in, opened, None) == {"RUNNING_MODAL"}
        return stand_in

    @staticmethod
    def change(dialog, **settings):
        """A field changed in the dialog: what Blender does, and then calls."""
        for name, value in settings.items():
            setattr(dialog, name, value)
            if name == "step":
                rigmoves._step_typed(dialog, bpy.context)
            else:
                rigmoves._spread_changed(dialog, bpy.context)

    def test_unticking_both_ways_sizes_the_step_again(self):
        # Twelve spikes: one way round there are eleven places, and ten each
        # would hold the last six at the limit. Both ways it is -6, and one way -3.
        self.crown()
        dialog = self.dialog()
        self.assertTrue(dialog.both_ways)
        self.assertEqual(dialog.step, -6.0)
        self.change(dialog, both_ways=False)
        self.assertEqual(dialog.step, -3.0)
        self.change(dialog, both_ways=True)
        self.assertEqual(dialog.step, -6.0)

    def test_changing_the_order_sizes_the_step_again(self):
        # Dominoes in a row: round a ring, both ways, the places are few and
        # ten each fits. Along an axis there are eight, and it is -5.
        self.dominoes()
        dialog = self.dialog()
        self.assertEqual(dialog.step, -10.0)
        self.change(dialog, order="AXIS")
        self.assertEqual(dialog.step, -5.0)
        self.change(dialog, order="DISTANCE")
        self.assertEqual(dialog.step, -5.0)
        self.change(dialog, order="AROUND")
        self.assertEqual(dialog.step, -10.0)

    def test_only_the_selected_sizes_the_step_for_those(self):
        self.crown()
        dialog = self.dialog()
        self.assertEqual(dialog.step, -6.0)
        select(self.riders[0], self.riders[1], self.riders[2])
        self.change(dialog, only_selected=True)
        self.assertEqual(dialog.step, -10.0)
        self.change(dialog, only_selected=False)
        self.assertEqual(dialog.step, -6.0)

    def test_axis_seed_and_by_keep_the_step_sized_too(self):
        self.dominoes()
        dialog = self.dialog()
        self.change(dialog, order="AXIS")
        self.assertEqual(dialog.step, -5.0)
        # Along Y the row stands in one place: nobody waits for anybody.
        self.change(dialog, axis="Y")
        self.assertEqual(dialog.step, -10.0)
        for setting in ({"axis": "X"}, {"seed": 7}, {"by": "RANGE"}, {"by": "STEP"}):
            self.change(dialog, **setting)
            self.assertEqual(dialog.step, -5.0, setting)
        # Random deals out the places, none shared: the same count as along X.
        self.change(dialog, order="RANDOM")
        self.assertEqual(dialog.step, -5.0)
        self.change(dialog, seed=3)
        self.assertEqual(dialog.step, -5.0)

    def test_a_step_that_was_typed_is_kept(self):
        self.crown()
        dialog = self.dialog()
        self.change(dialog, step=-8.0)
        self.assertFalse(dialog.sizing)
        self.change(dialog, both_ways=False)
        self.change(dialog, order="DISTANCE")
        self.change(dialog, only_selected=True)
        self.assertEqual(dialog.step, -8.0)

    def test_the_dialogs_own_writes_are_not_taken_for_a_typed_step(self):
        self.crown()
        dialog = self.dialog()
        self.assertTrue(dialog.sizing)
        self.change(dialog, both_ways=False)
        self.assertTrue(dialog.sizing)
        # And once typed over, the dialog's own sizing is no longer the one in force.
        self.change(dialog, step=-4.0)
        self.change(dialog, both_ways=True)
        self.assertEqual(dialog.step, -4.0)

    def test_a_step_the_caller_gave_is_never_sized(self):
        self.crown()
        dialog = self.dialog(step=-7.0)
        self.assertFalse(dialog.sizing)
        self.change(dialog, both_ways=False)
        self.assertEqual(dialog.step, -7.0)

    def test_the_callbacks_are_wired_to_the_properties_of_the_operator(self):
        # Through Blender's own machinery: the settings a script passes call
        # them, and with the dialog's flag on, the Step is sized as the last of
        # them leaves things.
        self.crown()
        self.assertEqual(bpy.ops.rigmoves.spread(
            index=0, what="LEAD", sizing=True, order="AROUND", both_ways=True), {"FINISHED"})
        self.assertEqual(self.leads(), [-6 * n for n in range(1, 7)] + [-30, -24, -18, -12, -6])
        self.assertIn("in steps of -6 from 0,", rig().rigmoves.report)
        self.assertEqual(bpy.ops.rigmoves.spread(
            index=0, what="LEAD", sizing=True, order="AROUND", both_ways=False), {"FINISHED"})
        self.assertEqual(self.leads(), [-3 * n for n in range(1, 12)])
        self.assertIn("in steps of -3 from 0,", rig().rigmoves.report)
        # A Step passed with them is the caller's, and is kept.
        self.assertEqual(bpy.ops.rigmoves.spread(
            index=0, what="LEAD", sizing=True, order="AROUND", step=-10.0, both_ways=False),
            {"FINISHED"})
        self.assertEqual(self.leads(), [-10, -20, -30, -40] + [-50] * 7)

    def test_a_script_that_does_not_open_a_dialog_is_not_touched(self):
        self.crown()
        self.assertEqual(bpy.ops.rigmoves.spread(
            index=0, what="LEAD", order="AROUND", both_ways=False), {"FINISHED"})
        self.assertEqual(self.leads(), [-3 * n for n in range(1, 12)])
        self.assertIn("(sized to fit)", rig().rigmoves.report)

    def test_both_ways_and_only_the_selected_are_not_remembered(self):
        # Blender keeps every property of an operator that is not marked
        # otherwise, for the next time the dialog opens: Both ways, whose smart
        # default then worked only the first time, and Only the selected, which
        # a spread of Delays left on for the next spread of Leads.
        props = bpy.ops.rigmoves.spread.get_rna_type().properties
        for name in ("order", "start", "step", "first", "last", "both_ways",
                     "only_selected", "sizing"):
            self.assertTrue(props[name].is_skip_save, name)
        self.assertTrue(props["sizing"].is_hidden)


def shift_d(obj, name):
    """Shift+D: a copy of the object with a mesh of its own."""
    copy = obj.copy()
    copy.data = obj.data.copy()
    copy.name = name
    for collection in obj.users_collection:
        collection.objects.link(copy)
    return copy


class TestRingReports(RingFlows):
    """Reports of Ring that named the wrong thing or gave the wrong advice, each
    played from the flow the review found it in."""

    KNUCKLES = [Vector((float(n), 0.0, 0.0)) for n in range(3)]

    def modelled_flower(self, count=8):
        """A leader and a copy on every other place round the world's Z, each
        made with Shift+D and turned about the centre."""
        shape = prism("Petal Shape", 4, 0.15, 1.0)
        self.leader = stood("Petal", shape, self.base)
        self.petals = [self.leader] + [
            stood("Petal {:d}".format(k + 1), shape.copy(), self.turn(k, count) @ self.base)
            for k in range(1, count)]
        bpy.context.view_layer.update()
        self.record_after(self.leader, turned=60.0)

    def finger(self):
        """A finger of three segments, chained and bent 30 degrees at After, built,
        with the cursor on the centre of the ring it is going to be one of."""
        scene = bpy.context.scene
        scene.cursor.location = (-2.0, 0.0, 0.0)
        self.segments = []
        for number in range(3):
            segment = cube("Seg{:d}".format(number + 1), (number + 0.5, 0.0, 0.0))
            segment.scale = (1.0, 0.3, 0.3)
            self.segments.append(segment)
        bpy.context.view_layer.update()
        self.homes = [s.matrix_world.copy() for s in self.segments]
        select(*self.segments)
        self.assertEqual(bpy.ops.rigmoves.new_move(), {"FINISHED"})
        for segment, knuckle in zip(self.segments, self.KNUCKLES):
            scene.cursor.location = knuckle
            select(segment)
            bpy.ops.rigmoves.set_pivot(index=0, kind="CURSOR")
        scene.cursor.location = (-2.0, 0.0, 0.0)
        select(*self.segments)
        self.assertEqual(bpy.ops.rigmoves.make_chain(index=0), {"FINISHED"})
        carry = Matrix.Identity(4)
        for knuckle, home, segment in zip(self.KNUCKLES, self.homes, self.segments):
            carry = carry @ turn_about(knuckle, "Y", 30.0)
            segment.matrix_world = carry @ home
            bpy.context.view_layer.update()
        self.assertEqual(bpy.ops.rigmoves.record(index=0, which="AFTER"), {"FINISHED"})
        self.assertEqual(bpy.ops.rigmoves.build(), {"FINISHED"})

    # -- a second Ring of a finger ------------------------------------------

    def test_a_second_ring_of_a_finger_does_not_list_its_own_copies_as_left_out(self):
        self.finger()
        select(self.segments[0])
        self.assertEqual(bpy.ops.rigmoves.ring(index=0, count=4), {"FINISHED"})
        select(self.segments[0])
        self.assertEqual(bpy.ops.rigmoves.ring(index=0, count=8), {"FINISHED"})
        report = self.report()
        self.assertNotIn("is already part of a move", report)
        self.assertNotIn("Left out", report)
        self.assertIn("4 copies of 'Seg1' (3 joints each) round the 3D cursor ride along "
                      "with it, joint for joint.", report)
        self.assertIn("3 places already held a copy and were skipped", report)

    def test_a_stray_leaf_is_named_not_hidden_behind_the_fingers_own_copies(self):
        self.finger()
        select(self.segments[0])
        self.assertEqual(bpy.ops.rigmoves.ring(index=0, count=4), {"FINISHED"})
        stood("Stray Leaf", prism("Leaf Shape", 5, 0.12, 0.8),
              turn_about(Vector((-2.0, 0.0, 0.0)), "Z", 135.0) @ self.homes[0])
        bpy.context.view_layer.update()
        select(self.segments[0])
        self.assertEqual(bpy.ops.rigmoves.ring(index=0, count=8), {"FINISHED"})
        report = self.report()
        self.assertIn("Left out: 'Stray Leaf' stands in a place and is not a copy of 'Seg1'",
                      report)
        self.assertNotIn("is already part of a move", report)
        self.assertNotIn("and 3 more", report)

    # -- Ride Along with copies of a palm's finger --------------------------

    def test_copies_of_a_palms_finger_are_said_to_be_of_the_finger_not_the_palm(self):
        palm = cube("Palm", (1.5, 0.0, 0.0))
        palm.scale = (4.0, 3.0, 0.5)
        segs, y = [], 1.5
        for number, length in enumerate((1.0, 0.7, 0.5)):
            seg = cube("F1_{:d}".format(number + 1), (0.0, y + length / 2.0, 0.0))
            seg.scale = (0.4, length, 0.3)
            segs.append(seg)
            y += length
        bpy.context.view_layer.update()
        copies = []
        for finger, shift in ((2, 1.0), (3, 2.0), (4, 3.0)):
            for number, seg in enumerate(segs):
                made = shift_d(seg, "F{:d}_{:d}".format(finger, number + 1))
                made.location.x += shift
                copies.append(made)
        bpy.context.view_layer.update()
        select(palm, *segs)
        self.assertEqual(bpy.ops.rigmoves.new_move(), {"FINISHED"})
        select(palm, *segs)
        self.assertEqual(bpy.ops.rigmoves.make_chain(index=0), {"FINISHED"})
        move = rig().rigmoves.moves[0]
        self.assertEqual(move.parts["F1_1"].follows, "Palm")
        for where, seg in zip((Vector((0, 1.5, 0)), Vector((0, 2.5, 0)), Vector((0, 3.2, 0))),
                              segs):
            bpy.context.scene.cursor.location = where
            select(seg)
            bpy.ops.rigmoves.set_pivot(index=0, kind="CURSOR")
        segs[0].matrix_world = turn_about((0, 1.5, 0), "X", 30.0) @ segs[0].matrix_world
        bpy.context.view_layer.update()
        select(segs[0])
        self.assertEqual(bpy.ops.rigmoves.curl(index=0), {"FINISHED"})
        self.assertEqual(bpy.ops.rigmoves.record(index=0, which="AFTER"), {"FINISHED"})
        self.assertEqual(bpy.ops.rigmoves.build(), {"FINISHED"})
        select(*copies, segs[0])
        self.assertEqual(bpy.ops.rigmoves.ride_along(index=0, leader="F1_1",
                                                     rig_name=rig().name), {"FINISHED"})
        self.assertIn("3 copies of 'F1_1' ride along, joint for joint.", self.report())
        self.assertNotIn("'Palm'", self.report())

    # -- the advice for copies that are off the ring ------------------------

    def test_a_ring_about_the_wrong_axis_is_told_to_check_About_too(self):
        self.modelled_flower()
        before = {o.name for o in bpy.data.objects}
        self.assertEqual(self.ring(self.leader, axis="X"), {"CANCELLED"})
        self.assertEqual({o.name for o in bpy.data.objects}, before)
        self.assertEqual(self.report(),
                         "7 copies of 'Petal' stand near the ring but off its places: check "
                         "the centre (3D cursor), About and Count. Nothing done.")

    def test_use_what_is_there_does_not_promise_a_fill_that_would_be_refused(self):
        self.modelled_flower()
        self.assertEqual(self.ring(self.leader, axis="X", use="ADOPT"), {"CANCELLED"})
        report = self.report()
        self.assertIn("check the centre (3D cursor), About and Count.", report)
        self.assertNotIn("Fill the gaps would copy", report)
        self.assertNotIn("had nothing standing", report)

    def test_use_what_is_there_still_says_so_when_fill_the_gaps_would_copy(self):
        self.modelled_flower()
        for petal in (self.petals[3], self.petals[5]):
            bpy.data.objects.remove(petal, do_unlink=True)
        self.assertEqual(self.ring(self.leader, use="ADOPT"), {"FINISHED"})
        self.assertIn("2 places had nothing standing in them: Fill the gaps would copy the "
                      "part there.", self.report())

    def test_the_advice_for_a_refused_ring_comes_before_what_was_left_out(self):
        self.modelled_flower()
        self.assertEqual(self.ring(self.leader, axis="X", use="ADOPT"), {"CANCELLED"})
        report = self.report()
        self.assertIn("Left out:", report)
        self.assertLess(report.index("check the centre (3D cursor)"), report.index("Left out:"))
        # And in the panel's first lines, which is all a long report shows.
        lines = rigmoves.wrapped(report, most=1000)
        shown = " ".join(lines[:9])
        self.assertIn("check the centre", shown)

    def test_a_report_with_notes_and_a_success_puts_them_before_what_was_left_out(self):
        self.modelled_flower()
        # Seven copies stand where they should, and three more near the ring where
        # no place is: a Count of 6 takes the ones that fit and notes the rest.
        self.assertEqual(self.ring(self.leader, use="ADOPT", count=6), {"FINISHED"})
        report = self.report()
        self.assertIn("stand near the ring but off its places", report)
        if "Left out:" in report:
            self.assertLess(report.index("stand near the ring"), report.index("Left out:"))

    # -- the panel's box ----------------------------------------------------

    @staticmethod
    def drawn_report(text):
        lines = []

        class Column:
            enabled = True

            def label(self, text="", **_kwargs):
                lines.append(text)

        class Box:
            def column(self, **_kwargs):
                return Column()

        class Layout:
            def box(self):
                return Box()

        rigmoves.RIGMOVES_PT_panel._draw_report(None, Layout(), types.SimpleNamespace(report=text))
        return lines

    def test_a_report_the_box_has_room_for_is_shown_whole(self):
        text = "Spread the Leads of 11 riders in steps of -3 from 0, round the ring."
        self.assertEqual(self.drawn_report(text), rigmoves.wrapped(text))
        # Seven words of four letters fill a line, so sixty-three are nine lines.
        nine = " ".join(["word"] * 63)
        self.assertEqual(len(rigmoves.wrapped(nine, most=1000)), 9)
        self.assertEqual(self.drawn_report(nine), rigmoves.wrapped(nine, most=1000))
        ten = " ".join(["word"] * 64)
        self.assertEqual(len(rigmoves.wrapped(ten, most=1000)), 10)
        self.assertEqual(len(self.drawn_report(ten)), 10)
        self.assertEqual(self.drawn_report(ten)[-1], "(the full report is in the Info editor)")

    def test_a_longer_report_ends_with_a_sign_and_says_where_the_rest_is(self):
        text = " ".join("word{:d}".format(n) for n in range(80))
        whole = rigmoves.wrapped(text, most=1000)
        self.assertGreater(len(whole), 9)
        lines = self.drawn_report(text)
        self.assertEqual(len(lines), 10)
        self.assertTrue(lines[8].endswith("…"), lines[8])
        self.assertTrue(whole[8].startswith(lines[8][:-1].rstrip()), (whole[8], lines[8]))
        self.assertEqual(lines[:8], whole[:8])
        self.assertEqual(lines[9], "(the full report is in the Info editor)")
        self.assertLessEqual(len(lines[8]), 34)

    # -- a half made with Ctrl+M that is not the same on both sides ---------

    def test_an_asymmetric_ctrl_m_half_is_said_to_be_a_mirror_image(self):
        shape = prism("Odd Shape", 4, 0.15, 1.0)
        self.leader = stood("Outer Leader", shape, self.base)
        flip = Matrix.Scale(-1.0, 4, Vector((1.0, 0.0, 0.0)))
        stood("Outer 2", shape.copy(), flip @ self.turn(7) @ self.base)
        bpy.context.view_layer.update()
        self.record_after(self.leader, turned=50.0)
        for use in ("ADOPT", "FILL"):
            self.ring(self.leader, use=use)
            self.assertIn("'Outer 2' is a mirror image of 'Outer Leader' (not the same on "
                          "both sides), so it is not a copy - it can ride along with Ride "
                          "Along, which mirrors by itself", self.report(), use)
            self.assertNotIn("not turned to its place", self.report(), use)

    def test_a_copy_that_is_only_not_turned_to_its_place_is_still_said_so(self):
        shape = prism("Odd Shape", 4, 0.15, 1.0)
        self.leader = stood("Outer Leader", shape, self.base)
        stood("Unturned", shape.copy(),
              Matrix.Translation((self.turn(2) @ self.base).translation) @ self.base.to_3x3().to_4x4())
        bpy.context.view_layer.update()
        self.record_after(self.leader, turned=50.0)
        self.ring(self.leader, use="ADOPT")
        self.assertIn("'Unturned' is a copy of 'Outer Leader' that is not turned to its place",
                      self.report())
        self.assertNotIn("mirror image", self.report())


class TestRingDialogMemory(CopyThatCase):
    """Blender opens an operator's dialog with what it was last used with, for
    every property not marked SKIP_SAVE. Ring keeps Use, Count, Round, About and
    Linked copies from the last Ring - the next flower is likely to be made the
    same way - but not the Lead step: after the outer petals' step, the leaf's
    Ring opened with it and, left alone, the second leaf opened ahead of the
    first."""

    @staticmethod
    def next_dialog_opens_with(used):
        """What Blender puts back from the last use, as a script can see it: the
        properties that are not marked SKIP_SAVE. The rest are the default."""
        props = bpy.ops.rigmoves.ring.get_rna_type().properties
        return {name: value for name, value in used.items() if not props[name].is_skip_save}

    def test_two_rings_in_a_row_the_second_opens_with_no_lead_step(self):
        outer_petals = {"use": "ADOPT", "count": 8, "center": "ORIGIN", "axis": "X",
                        "linked": False, "lead_step": -9}
        reopened = self.next_dialog_opens_with(outer_petals)
        self.assertEqual(reopened, {"use": "ADOPT", "count": 8, "center": "ORIGIN",
                                    "axis": "X", "linked": False})
        self.assertNotIn("lead_step", reopened)
        self.assertEqual(bpy.ops.rigmoves.ring.get_rna_type().properties["lead_step"].default, 0)

    def test_what_a_ring_keeps_it_keeps(self):
        props = bpy.ops.rigmoves.ring.get_rna_type().properties
        for name in ("use", "count", "center", "axis", "linked"):
            self.assertFalse(props[name].is_skip_save, name)
        self.assertTrue(props["lead_step"].is_skip_save)


class TestRingDuplicateOnTop(RingFlows):
    """Shift+D, then a right-click to cancel the move, leaves a copy exactly on
    the part. That is not a copy off the ring - the advice for those, the centre
    and the Count, is wrong for it - but a slip, and is said to be one."""

    SAID = ("'Petal.001' stands exactly where 'Petal' is - a duplicate left on top of "
            "it? Delete it, then Ring again.")

    def one_petal_with_a_duplicate_on_it(self):
        self.leader = stood("Petal", prism("Petal Shape", 4, 0.15, 1.0), self.base)
        self.record_after(self.leader, turned=60.0)
        self.leader.matrix_world = self.base
        bpy.context.view_layer.update()
        select(self.leader)
        self.assertEqual(bpy.ops.object.duplicate(linked=False), {"FINISHED"})
        self.dup = bpy.context.view_layer.objects.active
        self.assertEqual(self.dup.name, "Petal.001")
        self.assertTrue(same_matrix_of(self.dup.matrix_world, self.base))

    def made_by(self, **kwargs):
        before = {o.name for o in bpy.data.objects}
        result = self.ring(self.leader, **kwargs)
        return result, {o.name for o in bpy.data.objects} - before

    def test_fill_refuses_and_names_the_duplicate(self):
        self.one_petal_with_a_duplicate_on_it()
        result, made = self.made_by(use="FILL")
        self.assertEqual(result, {"CANCELLED"})
        self.assertEqual(made, set())
        self.assertEqual(self.report(), self.SAID + " Nothing done.")
        self.assertEqual(self.riders(), {})

    def test_use_what_is_there_names_it_too_and_does_not_call_it_off_the_ring(self):
        self.one_petal_with_a_duplicate_on_it()
        result, made = self.made_by(use="ADOPT")
        self.assertEqual(result, {"CANCELLED"})
        self.assertEqual(made, set())
        self.assertIn(self.SAID, self.report())
        self.assertNotIn("off the ring", self.report())
        self.assertNotIn("off its places", self.report())
        self.assertNotIn("Left out", self.report())
        # Fill the gaps is not what it would be sent to: it refuses the same.
        self.assertNotIn("Fill the gaps would copy", self.report())

    def test_use_what_is_there_takes_what_fits_and_adds_it_as_a_note(self):
        self.one_petal_with_a_duplicate_on_it()
        shape = self.leader.data
        for k in (2, 5):
            stood("Petal {:d}".format(k + 1), shape.copy(), self.turn(k) @ self.base)
        bpy.context.view_layer.update()
        result, made = self.made_by(use="ADOPT")
        self.assertEqual(result, {"FINISHED"})
        self.assertEqual(made, set())
        self.assertEqual(sorted(self.riders()), ["Petal 3", "Petal 6"])
        self.assertTrue(self.report().endswith(self.SAID), self.report())
        self.assertNotIn("off the ring", self.report())

    def test_after_the_duplicate_is_deleted_fill_makes_seven(self):
        self.one_petal_with_a_duplicate_on_it()
        self.assertEqual(self.made_by(use="FILL")[0], {"CANCELLED"})
        bpy.data.objects.remove(self.dup, do_unlink=True)
        bpy.context.view_layer.update()
        result, made = self.made_by(use="FILL")
        self.assertEqual(result, {"FINISHED"})
        self.assertEqual(len(made), 7)
        self.assertEqual(self.report(),
                         "7 copies of 'Petal' round the 3D cursor ride along with it.")

    def test_making_copies_is_not_refused_for_it(self):
        self.one_petal_with_a_duplicate_on_it()
        result, made = self.made_by(use="COPY")
        self.assertEqual(result, {"FINISHED"})
        self.assertEqual(len(made), 7)
        self.assertNotIn("exactly where", self.report())

    def test_two_duplicates_are_named_together(self):
        self.one_petal_with_a_duplicate_on_it()
        select(self.leader)
        self.assertEqual(bpy.ops.object.duplicate(linked=False), {"FINISHED"})
        result, made = self.made_by(use="FILL")
        self.assertEqual(result, {"CANCELLED"})
        self.assertEqual(self.report(),
                         "'Petal.001' and 'Petal.002' stand exactly where 'Petal' is - "
                         "duplicates left on top of it? Delete them, then Ring again. "
                         "Nothing done.")

    def test_a_copy_off_the_ring_is_still_said_to_be_off_it(self):
        # What the old sentence is for: a copy that stands near the ring and on
        # none of its places, and is not on the part.
        self.one_petal_with_a_duplicate_on_it()
        bpy.data.objects.remove(self.dup, do_unlink=True)
        stood("Stray", self.leader.data.copy(), self.turn(0.5) @ self.base)
        bpy.context.view_layer.update()
        self.assertEqual(self.made_by(use="FILL")[0], {"CANCELLED"})
        self.assertIn("1 copy of 'Petal' stands near the ring but off its places",
                      self.report())
        self.assertNotIn("exactly where", self.report())


class TestPartsMovedByTheirOwn(CopyThatCase):
    """A part whose transform is worked by an NLA strip or a driver of its own
    plays the wrong move: the rig is measured from where it stands, and what it
    stands on is worked out again on every frame. Build cannot lift those, as it
    lifts keys - they are somebody's work - so it names them, and says what to
    do."""

    NLA = ("'Lid' is moved by an NLA strip of its own, which fights the rig: mute or "
           "remove it in the NLA editor, then Build.")
    DRIVER = ("'Lid' is moved by a driver on its transform: remove it in the Drivers "
              "editor, then Build.")

    def keyed(self, obj):
        bpy.context.scene.frame_set(1)
        obj.keyframe_insert("location", frame=1)
        obj.location.z = 3.0
        obj.keyframe_insert("location", frame=20)

    def in_the_nla(self, obj):
        self.keyed(obj)
        action = obj.animation_data.action
        track = obj.animation_data.nla_tracks.new()
        self.strip = track.strips.new("Idle", 1, action)
        self.track = track
        obj.animation_data.action = None

    @staticmethod
    def by_a_driver(obj):
        curve = obj.driver_add("location", 2)
        curve.driver.type = "SCRIPTED"
        curve.driver.expression = "1 + frame / 10"
        return curve

    def lid_with(self, how, name="Lid", where=(0.0, 0.0, 1.0)):
        lid = cube(name, where)
        how(lid)
        bpy.context.scene.frame_set(1)
        bpy.context.view_layer.update()
        return lid

    def start(self, *lids):
        select(*lids)
        self.assertEqual(bpy.ops.rigmoves.new_move(), {"FINISHED"})
        for lid in lids:
            lid.rotation_euler.x = math.radians(90.0)
        bpy.context.view_layer.update()
        self.assertEqual(bpy.ops.rigmoves.record(index=0, which="AFTER"), {"FINISHED"})

    @staticmethod
    def said_by_the_panel():
        return " ".join(text for _where, kind, text in drawn_panel()
                        if kind.startswith("label"))

    @staticmethod
    def build_and_hear():
        """Run what Build does, and keep how it reported: (kinds, text) of the
        last. Blender hands an operator's reports to the Info editor and does
        not let a script ask for them, so it is run against a stand-in that
        keeps them."""
        heard = []
        stand_in = types.SimpleNamespace(
            report=lambda kinds, text: heard.append((set(kinds), text)))
        assert rigmoves.RIGMOVES_OT_build.execute(stand_in, bpy.context) == {"FINISHED"}
        return heard[-1]

    def lift_button(self):
        return [text for _where, idname, text in drawn_buttons()
                if idname == "rigmoves.free_keys"]

    # -- named in the panel -------------------------------------------------

    def test_a_part_moved_by_an_nla_strip_is_named_in_the_panel(self):
        self.lid = self.lid_with(self.in_the_nla)
        self.start(self.lid)
        self.assertIn(self.NLA, self.said_by_the_panel())
        # Nothing to lift: no button that would not do anything.
        self.assertEqual(self.lift_button(), [])

    def test_a_part_moved_by_a_driver_is_named_in_the_panel(self):
        self.lid = self.lid_with(self.by_a_driver)
        self.start(self.lid)
        self.assertIn(self.DRIVER, self.said_by_the_panel())
        self.assertEqual(self.lift_button(), [])

    def test_a_part_with_keys_in_its_action_has_the_box_it_always_had(self):
        self.lid = self.lid_with(self.keyed)
        self.start(self.lid)
        said = self.said_by_the_panel()
        self.assertIn("'Lid' keyed on its own transform", said)
        self.assertEqual(self.lift_button(), ["Lift Those Keyframes"])
        self.assertNotIn("fights the rig", said)
        self.assertNotIn("Drivers editor", said)

    def test_a_renamed_part_moved_by_an_nla_strip_is_still_found(self):
        # A part is found by its object, not its name (0.19.0): asked before
        # the rename has reached the move's own records, the strip is still
        # named, under the object's new name.
        self.lid = self.lid_with(self.in_the_nla)
        self.start(self.lid)
        self.lid.name = "Hatch"
        self.assertEqual(rigmoves.fighting_parts(rig().rigmoves), (["Hatch"], []))

    def test_keys_and_an_nla_strip_on_different_parts_are_each_said(self):
        keyed = self.lid_with(self.keyed, "Keyed", (0.0, 3.0, 1.0))
        self.lid = self.lid_with(self.in_the_nla)
        self.start(keyed, self.lid)
        said = self.said_by_the_panel()
        self.assertIn("'Keyed' keyed on its own transform", said)
        self.assertIn(self.NLA, said)
        self.assertEqual(self.lift_button(), ["Lift Those Keyframes"])

    def test_a_part_that_is_both_is_said_both_ways(self):
        self.lid = self.lid_with(self.in_the_nla)
        self.by_a_driver(self.lid)
        self.start(self.lid)
        said = self.said_by_the_panel()
        self.assertIn(self.NLA, said)
        self.assertIn(self.DRIVER, said)

    def test_several_parts_are_named_together(self):
        lids = [self.lid_with(self.in_the_nla, "Lid {:d}".format(n), (0.0, 3.0 * n, 1.0))
                for n in range(4)]
        self.start(*lids)
        self.assertIn("'Lid 0', 'Lid 1', 'Lid 2' and 1 more are moved by NLA strips of "
                      "their own, which fight the rig: mute or remove them in the NLA "
                      "editor, then Build.", self.said_by_the_panel())

    def test_nothing_is_said_of_what_plays_nothing(self):
        # A muted strip, a muted track, the NLA switched off, a muted driver, a
        # strip with no transform in it: none of them moves the part.
        cases = []
        lid = self.lid_with(self.in_the_nla, "Muted Strip", (0.0, 0.0, 1.0))
        self.strip.mute = True
        cases.append(lid)
        lid = self.lid_with(self.in_the_nla, "Muted Track", (0.0, 3.0, 1.0))
        self.track.mute = True
        cases.append(lid)
        lid = self.lid_with(self.in_the_nla, "No NLA", (0.0, 6.0, 1.0))
        lid.animation_data.use_nla = False
        cases.append(lid)
        lid = self.lid_with(self.by_a_driver, "Muted Driver", (0.0, 9.0, 1.0))
        lid.animation_data.drivers[0].mute = True
        cases.append(lid)

        def hidden_only(obj):
            obj.hide_render = False
            obj.keyframe_insert("hide_render", frame=1)
            obj.animation_data.nla_tracks.new().strips.new(
                "Hide", 1, obj.animation_data.action)
            obj.animation_data.action = None

        cases.append(self.lid_with(hidden_only, "Hide Only", (0.0, 12.0, 1.0)))
        self.start(*cases)
        said = self.said_by_the_panel()
        self.assertNotIn("fights the rig", said)
        self.assertNotIn("Drivers editor", said)
        self.assertEqual(rigmoves.fighting_parts(rig().rigmoves), ([], []))

    def test_only_the_part_whose_own_slot_has_the_transform_is_named(self):
        # One action holds a slot for the lid (a keyed visibility) and one for
        # the lamp (its height); each has a strip of it. The lid's strip plays
        # the lid's slot, which moves nothing.
        lid = cube("Lid", (0.0, 0.0, 1.0))
        lamp = cube("Lamp", (4.0, 0.0, 1.0))
        bpy.context.scene.frame_set(1)
        lid.keyframe_insert("hide_render", frame=1)
        action = lid.animation_data.action
        lamp.animation_data_create()
        lamp.animation_data.action = action
        lamp.keyframe_insert("location", index=2, frame=1)
        for obj in (lid, lamp):
            obj.animation_data.nla_tracks.new().strips.new("Play", 1, action)
            obj.animation_data.action = None
        self.assertEqual(rigmoves.moved_by_nla(lid), False)
        self.assertEqual(rigmoves.moved_by_nla(lamp), True)
        self.start(lid, lamp)
        said = self.said_by_the_panel()
        self.assertIn("'Lamp' is moved by an NLA strip of its own", said)
        self.assertNotIn("'Lid' is moved", said)

    # -- named by Build -----------------------------------------------------

    def test_build_names_a_part_moved_by_an_nla_strip_and_is_not_a_success(self):
        self.lid = self.lid_with(self.in_the_nla)
        self.start(self.lid)
        kinds, text = self.build_and_hear()
        self.assertEqual(kinds, {"WARNING"})
        self.assertIn(self.NLA, text)
        self.assertIn(self.NLA, rig().rigmoves.report)

    def test_build_names_a_part_moved_by_a_driver_and_is_not_a_success(self):
        self.lid = self.lid_with(self.by_a_driver)
        self.start(self.lid)
        kinds, text = self.build_and_hear()
        self.assertEqual(kinds, {"WARNING"})
        self.assertIn(self.DRIVER, text)

    def test_build_of_keys_lifts_them_and_is_a_success_as_it_was(self):
        self.lid = self.lid_with(self.keyed)
        self.start(self.lid)
        kinds, text = self.build_and_hear()
        self.assertEqual(kinds, {"INFO"})
        self.assertIn("3 stray keyframe track(s) on the parts", text)
        self.assertNotIn("fights the rig", text)
        self.assertEqual(rigmoves.own_transform_curves(self.lid), [])

    def test_build_keeps_saying_so_until_the_strip_is_muted(self):
        self.lid = self.lid_with(self.in_the_nla)
        self.start(self.lid)
        self.assertEqual(self.build_and_hear()[0], {"WARNING"})
        self.strip.mute = True
        kinds, text = self.build_and_hear()
        self.assertEqual(kinds, {"INFO"})
        self.assertNotIn("fights the rig", text)

    # -- left alone ---------------------------------------------------------

    def test_lifting_keyframes_leaves_the_strip_and_the_driver_alone(self):
        self.lid = self.lid_with(self.in_the_nla)
        curve = self.by_a_driver(self.lid)
        self.start(self.lid)
        self.assertEqual(bpy.ops.rigmoves.free_keys(), {"CANCELLED"})
        self.assertIn("Nothing is carrying stray keyframes", rig().rigmoves.report)
        animation = self.lid.animation_data
        self.assertEqual(len(animation.nla_tracks), 1)
        self.assertEqual(len(animation.nla_tracks[0].strips), 1)
        self.assertEqual(len(animation.drivers), 1)
        self.assertEqual(animation.drivers[0].data_path, curve.data_path)
        # Nor does Build.
        self.build_and_hear()
        self.assertEqual(len(animation.nla_tracks[0].strips), 1)
        self.assertEqual(len(animation.drivers), 1)


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


class TestNamesBesideControls(CopyThatCase):
    """A name is cut to the room its row gives it, from the front, so that the
    number which tells the copies of a petal apart stays on the row. Measured
    in the font the panel draws in, which a run with no window can still do."""

    NAME = "Outer Leader 2"

    def setUp(self):
        super().setUp()
        if not text_width(self.NAME):
            self.skipTest("this Blender has no font to measure text with here")

    @staticmethod
    def room(width, share=0.42, scale=1.0):
        """What a label may take of a sidebar this wide: the rows are the
        region less 53 px, and the label loses 32 px of its share to its icon
        and its padding (both measured in a real window)."""
        return share * (width - 53.0 * scale) - 32.0 * scale

    def test_a_long_name_is_cut_from_the_front_only_as_far_as_it_must(self):
        got = rigmoves.fitted(Sidebar(280), self.NAME, 0.42)
        self.assertTrue(got.startswith("…"), got)
        self.assertTrue(self.NAME.endswith(got[1:]), got)
        self.assertTrue(got.endswith(" 2"), got)
        self.assertLessEqual(text_width(got), self.room(280), got)
        # And no further than it had to: one more letter would not have fitted.
        more = "…" + self.NAME[-len(got):]
        self.assertGreater(text_width(more), self.room(280), more)

    def test_a_name_that_fits_is_left_whole(self):
        self.assertEqual(rigmoves.fitted(Sidebar(440), self.NAME, 0.42), self.NAME)
        self.assertEqual(rigmoves.fitted(Sidebar(280), "Petal 2", 0.42), "Petal 2")

    def test_a_wider_sidebar_never_shows_less_of_the_name(self):
        shown = [len(rigmoves.fitted(Sidebar(width), self.NAME, 0.42))
                 for width in range(120, 460, 20)]
        self.assertEqual(shown, sorted(shown))

    def test_the_tail_after_the_name_is_never_cut(self):
        for width in (60, 120, 200, 280, 360, 440):
            got = rigmoves.fitted(Sidebar(width), self.NAME, 0.42, " +2")
            self.assertTrue(got.endswith(" +2"), (width, got))
        got = rigmoves.fitted(Sidebar(280), self.NAME, 0.42, " +2")
        self.assertTrue(got.startswith("…"), got)
        self.assertLessEqual(text_width(got), self.room(280), got)
        # With no room at all the last letter stays, and the tail.
        self.assertEqual(rigmoves.fitted(Sidebar(60), self.NAME, 0.42, " +2"),
                         "…2 +2")

    def test_the_ui_scale_is_allowed_for(self):
        # Twice the scale: a sidebar twice as wide in pixels, a font twice as big.
        got = rigmoves.fitted(Sidebar(560, scale=2.0), self.NAME, 0.42)
        self.assertTrue(got.startswith("…"), got)
        self.assertTrue(got.endswith(" 2"), got)
        self.assertLessEqual(text_width(got, scale=2.0), self.room(560, scale=2.0), got)

    def test_without_a_region_it_is_cut_as_it_always_was(self):
        for context in (types.SimpleNamespace(region=None), bpy.context,
                        types.SimpleNamespace(region=types.SimpleNamespace(width=1))):
            self.assertEqual(rigmoves.fitted(context, self.NAME, 0.42),
                             rigmoves.short(self.NAME, 13))
            self.assertEqual(rigmoves.fitted(context, self.NAME, 0.42, " +2"),
                             rigmoves.short(self.NAME, 10) + " +2")

    def test_a_ring_of_seven_copies_reads_as_seven_rows_at_the_usual_width(self):
        # As found in a real window: the sidebar at its default width, Ring
        # having made seven copies of 'Outer Leader', and every row under
        # Riding along read the same, the number cut off the end.
        leader = cube("Outer Leader", (3.0, 0.0, 0.0))
        record_move([leader], lambda: setattr(leader, "location", (3.0, 0.0, 1.0)))
        select(leader)
        self.assertEqual(bpy.ops.rigmoves.ring(index=0, count=8), {"FINISHED"})
        rows = [text for where, kind, text in drawn_panel(Sidebar(280))
                if kind == "label:OBJECT_DATA" and where[:1] == ("body:show_riders",)]
        self.assertEqual(len(rows), 7)
        self.assertEqual(len(set(rows)), 7, rows)
        for number, row in zip(range(2, 9), rows):
            self.assertTrue(row.endswith(" {:d}".format(number)), row)
            # What Blender draws is what fits: a longer label is cut at its
            # end, which is where the number is.
            self.assertLessEqual(text_width(row), self.room(280), row)


class ChestCase(CopyThatCase):
    """A chest with a lid hinged on its back edge, built: the lid swings open
    100 degrees about X. The model the second round of review was made on, and
    the one the tests of what happens to a finished model are made on."""

    SWING = 100.0

    def setUp(self):
        super().setUp()
        self.lid = cube("Lid", (0.0, 0.0, 1.1))
        self.lid.scale = (2.0, 1.2, 0.2)
        bpy.context.view_layer.update()
        self.home = self.lid.matrix_world.copy()
        self.hinge = Vector((0.0, 0.6, 1.0))
        select(self.lid)
        self.assertEqual(bpy.ops.rigmoves.new_move(), {"FINISHED"})
        bpy.context.scene.cursor.location = self.hinge
        select(self.lid)
        self.assertEqual(bpy.ops.rigmoves.set_pivot(index=0, kind="CURSOR"), {"FINISHED"})
        self.lid.matrix_world = turn_about(self.hinge, "X", -self.SWING) @ self.home
        bpy.context.view_layer.update()
        self.assertEqual(bpy.ops.rigmoves.record(index=0, which="AFTER"), {"FINISHED"})
        self.assertEqual(bpy.ops.rigmoves.build(), {"FINISHED"})
        self.move = rig().rigmoves.moves[0]
        # Where the shut lid is, point by point: what every later place of it
        # is measured from, however its mesh is framed.
        self.shut = rest_points(self.lid)

    def lid_at(self, share, shift=None, shut=None, hinge=None):
        """Where the lid should be this far along its move, with the whole
        model moved by `shift`."""
        shift = Matrix.Identity(4) if shift is None else shift
        turn = turn_about(self.hinge if hinge is None else hinge, "X",
                          -eased(self.SWING, share))
        return [shift @ turn @ point for point in (self.shut if shut is None else shut)]

    def check_lid(self, shift=None, lid=None, move=None, shut=None, hinge=None,
                  shares=(0.0, 0.5, 1.0)):
        """The lid on the recording at both ends and half way."""
        lid = self.lid if lid is None else lid
        move = self.move if move is None else move
        for share in shares:
            drive(move, share)
            self.assertLess(drift(lid, self.lid_at(share, shift, shut, hinge)), TOLERANCE,
                            "{:s} at {:.0%}".format(lid.name, share))
        drive(move, 0.0)


class TestAModelMovedAsAWhole(ChestCase):
    """A finished model is moved - everything selected and dragged, or the rig
    parented to a hand and the hand moved - and then Built, or something that
    Builds is pressed. The parts used to jump back to where the model had
    been, because every Before and After it remembers is a place in the world."""

    MOVE = Matrix.Translation((5.0, 2.0, 0.0))

    def move_everything(self):
        bpy.ops.object.select_all(action="SELECT")
        self.assertEqual(bpy.ops.transform.translate(value=(5.0, 2.0, 0.0)), {"FINISHED"})
        bpy.context.view_layer.update()

    def test_a_model_moved_as_a_whole_builds_where_it_now_stands(self):
        self.move_everything()
        self.assertEqual(bpy.ops.rigmoves.build(), {"FINISHED"})
        self.check_lid(self.MOVE)

    def test_a_rig_parented_to_a_hand_that_is_moved_builds_where_it_now_stands(self):
        # The guide's own advice for a model that is carried: parent the rig
        # to what carries it.
        hand = bpy.data.objects.new("Hand", None)
        bpy.context.scene.collection.objects.link(hand)
        bpy.context.view_layer.update()
        select(hand, rig())
        self.assertEqual(bpy.ops.object.parent_set(type="OBJECT", keep_transform=True),
                         {"FINISHED"})
        hand.location = (5.0, 2.0, 0.0)
        bpy.context.view_layer.update()
        self.assertEqual(bpy.ops.rigmoves.build(), {"FINISHED"})
        self.check_lid(self.MOVE)

    def test_set_pivot_after_the_whole_model_was_moved_is_not_refused(self):
        self.move_everything()
        bpy.context.scene.cursor.location = self.MOVE @ self.hinge
        select(self.lid)
        self.assertEqual(bpy.ops.rigmoves.set_pivot(index=0, kind="CURSOR"), {"FINISHED"})
        self.assertNotIn("moved and not recorded", rig().rigmoves.report)
        self.check_lid(self.MOVE)

    def test_a_ring_and_a_spread_after_the_whole_model_was_moved(self):
        self.move_everything()
        centre = self.MOVE @ Vector((0.0, 0.0, 0.0))
        bpy.context.scene.cursor.location = centre
        select(self.lid)
        self.assertEqual(bpy.ops.rigmoves.ring(index=0, count=4), {"FINISHED"})
        select(self.lid)
        self.assertEqual(bpy.ops.rigmoves.spread(index=0, what="LEAD", by="RANGE",
                                                 first=0.0, last=-20.0, order="AROUND"),
                         {"FINISHED"})
        copies = sorted((o for o in bpy.data.objects if o.name.startswith("Lid ")),
                        key=lambda o: o.name)
        self.assertEqual(len(copies), 3)
        for number, copy in enumerate(copies, start=1):
            turn = turn_about(centre, "Z", 90.0 * number)
            for share in (0.0, 1.0):
                drive(self.move, share)
                self.assertLess(drift(copy, [turn @ p for p in self.lid_at(share, self.MOVE)]),
                                TOLERANCE, "{:s} at {:.0%}".format(copy.name, share))
        # Riders sent behind lengthen the control, so only its ends are the
        # leader's own.
        self.check_lid(self.MOVE, shares=(0.0, 1.0))

    def test_a_part_added_but_not_built_yet_goes_with_the_model(self):
        # Added to the move and not built: a loose object, moved with the rest.
        coin = cube("Coin", (0.3, 0.0, 0.6))
        coin.scale = (0.3, 0.3, 0.05)
        bpy.context.view_layer.update()
        where = rest_points(coin)
        select(coin, self.lid)
        self.assertEqual(bpy.ops.rigmoves.add_to_move(index=0, rig_name=rig().name),
                         {"FINISHED"})
        self.move_everything()
        self.assertEqual(bpy.ops.rigmoves.build(), {"FINISHED"})
        self.assertLess(drift(coin, [self.MOVE @ p for p in where]), TOLERANCE)
        self.check_lid(self.MOVE)

    def test_the_whole_model_moved_twice_is_still_exact(self):
        self.move_everything()
        self.assertEqual(bpy.ops.rigmoves.build(), {"FINISHED"})
        self.move_everything()
        self.assertEqual(bpy.ops.rigmoves.build(), {"FINISHED"})
        self.check_lid(self.MOVE @ self.MOVE)

    def test_a_path_curve_left_behind_comes_along(self):
        # Made with the lid, bent in edit mode, and not moved with the rest:
        # a Build pins its ends to the pivot, so a curve left behind would be
        # dragged out of shape between two places.
        select(self.lid)
        self.assertEqual(bpy.ops.rigmoves.curve_path(index=0), {"FINISHED"})
        curve = self.move.parts["Lid"].path_curve

        def starts():
            return curve.matrix_world @ curve.data.splines[0].bezier_points[0].co

        was = starts()
        select(rig(), self.lid)
        self.assertEqual(bpy.ops.transform.translate(value=(5.0, 2.0, 0.0)), {"FINISHED"})
        bpy.context.view_layer.update()
        # Only the model moved: the curve is an object of its own.
        self.assertLess((starts() - was).length, 1e-6)
        self.assertEqual(bpy.ops.rigmoves.build(), {"FINISHED"})
        self.assertLess((starts() - self.MOVE @ was).length, 1e-4)
        self.check_lid(self.MOVE)

    def test_a_rig_animated_along_a_path_is_caught_up_at_the_frame_it_is_at(self):
        scene = bpy.context.scene
        scene.frame_set(1)
        rig().keyframe_insert("location", frame=1)
        here_ = rig().location.copy()
        rig().location = here_ + Vector((5.0, 2.0, 0.0))
        rig().keyframe_insert("location", frame=10)
        scene.frame_set(10)
        bpy.context.view_layer.update()
        self.assertEqual(bpy.ops.rigmoves.build(), {"FINISHED"})
        self.check_lid(self.MOVE)
        scene.frame_set(1)
        bpy.context.view_layer.update()
        self.assertEqual(bpy.ops.rigmoves.build(), {"FINISHED"})
        self.check_lid()

    def test_a_rig_made_before_the_seat_was_kept_takes_where_it_stands_as_it_is(self):
        # A file from before: nothing remembered of where the rig stood, so
        # the first catch-up only notes it, and nothing is carried.
        rig().rigmoves.seated = False
        self.assertEqual(bpy.ops.rigmoves.build(), {"FINISHED"})
        self.assertTrue(rig().rigmoves.seated)
        self.check_lid()


class TestAReframedPart(ChestCase):
    """The origin of a built part is set, or its scale or rotation applied.
    Nothing moves on screen, but the object's own transform and the numbers
    in its mesh both change, and the rig - measuring from the transform the
    object had at Before - read that as a part dragged and put it back: the
    mesh ended up somewhere else, with "moved and not recorded" for an answer."""

    SAID = "had its origin, scale or rotation changed after it was bound"

    def reframe_with_the_cursor(self):
        bpy.context.scene.cursor.location = Vector((0.7, 0.3, 1.4))
        select(self.lid)
        self.assertEqual(bpy.ops.object.origin_set(type="ORIGIN_CURSOR"), {"FINISHED"})
        bpy.context.view_layer.update()

    def apply(self, **kinds):
        select(self.lid)
        self.assertEqual(bpy.ops.object.transform_apply(**kinds), {"FINISHED"})
        bpy.context.view_layer.update()

    def test_set_origin_to_the_cursor_is_put_back_on_the_frame_and_nothing_moves(self):
        self.reframe_with_the_cursor()
        self.assertLess(drift(self.lid, self.shut), TOLERANCE)
        self.assertEqual(bpy.ops.rigmoves.build(), {"FINISHED"})
        self.check_lid()
        self.assertIn(self.SAID, rig().rigmoves.report)
        self.assertIn("To change where it turns, use Pivot.", rig().rigmoves.report)
        # On the frame it was recorded in again.
        self.assertTrue(rigmoves.same_matrix(
            self.lid.matrix_world, rigmoves.as_matrix(self.move.parts["Lid"].before), 1e-5))

    def test_applying_the_scale_is_put_back_on_the_frame_and_nothing_moves(self):
        self.apply(location=False, rotation=False, scale=True)
        self.assertEqual(bpy.ops.rigmoves.build(), {"FINISHED"})
        self.check_lid()
        self.assertIn(self.SAID, rig().rigmoves.report)

    def test_applying_location_rotation_and_scale_together(self):
        self.apply(location=True, rotation=True, scale=True)
        self.assertEqual(bpy.ops.rigmoves.build(), {"FINISHED"})
        self.check_lid()

    def test_set_pivot_after_a_set_origin_is_not_refused_as_a_part_moved(self):
        # What the refusal used to say, and what it asked for: record it first.
        self.reframe_with_the_cursor()
        bpy.context.scene.cursor.location = self.hinge
        select(self.lid)
        self.assertEqual(bpy.ops.rigmoves.set_pivot(index=0, kind="CURSOR"), {"FINISHED"})
        self.assertNotIn("moved and not recorded", rig().rigmoves.report)
        self.check_lid()

    def test_a_record_after_a_set_origin_keeps_the_move_as_it_was(self):
        self.reframe_with_the_cursor()
        select(self.lid)
        self.assertEqual(bpy.ops.rigmoves.record(index=0, which="AFTER"), {"FINISHED"})
        self.assertNotIn("moved by hand", rig().rigmoves.report)
        self.assertEqual(bpy.ops.rigmoves.build(), {"FINISHED"})
        self.check_lid()

    def test_a_reframe_and_a_move_of_the_whole_model_together(self):
        bpy.ops.object.select_all(action="SELECT")
        self.assertEqual(bpy.ops.transform.translate(value=(5.0, 2.0, 0.0)), {"FINISHED"})
        bpy.context.view_layer.update()
        bpy.context.scene.cursor.location = Vector((5.7, 2.3, 1.4))
        select(self.lid)
        self.assertEqual(bpy.ops.object.origin_set(type="ORIGIN_CURSOR"), {"FINISHED"})
        bpy.context.view_layer.update()
        self.assertEqual(bpy.ops.rigmoves.build(), {"FINISHED"})
        self.check_lid(Matrix.Translation((5.0, 2.0, 0.0)))

    def test_a_drag_is_still_read_as_a_drag(self):
        # Moved, its mesh not moved the other way: nobody framed anything.
        self.lid.location.z += 0.5
        bpy.context.view_layer.update()
        select(self.lid)
        self.assertEqual(bpy.ops.rigmoves.set_pivot(index=0, kind="CURSOR"), {"CANCELLED"})
        self.assertIn("moved and not recorded", rig().rigmoves.report)

    def test_what_cannot_be_checked_is_refused_with_the_mesh_left_as_it_was(self):
        # A constraint reads the frame an object stands in: its look cannot be
        # told in advance to stay the same.
        self.lid.constraints.new("COPY_LOCATION")
        self.reframe_with_the_cursor()
        was = (self.lid.matrix_world.copy(), rigmoves.mesh_points(self.lid), self.lid.data.name)
        select(self.lid)
        self.assertEqual(bpy.ops.rigmoves.build(), {"CANCELLED"})
        self.assertIn("was given a new origin, scale or rotation after it was bound, and "
                      "cannot be put back safely: press Ctrl+Z to undo that, or take it "
                      "out of its move (x) and add it again.", rig().rigmoves.report)
        self.assertEqual(self.lid.data.name, was[2])
        self.assertTrue(rigmoves.same_matrix(self.lid.matrix_world, was[0], 1e-9))
        self.assertEqual(rigmoves.mesh_points(self.lid), was[1])
        # And taking it out is never held up by it.
        self.assertEqual(bpy.ops.rigmoves.remove(index=0), {"FINISHED"})
        self.assertLess(drift(self.lid, self.shut), TOLERANCE)

    def test_a_part_bound_before_the_fingerprint_was_kept_gets_one_at_the_next_build(self):
        part = self.move.parts["Lid"]
        self.assertEqual(part.rest_count, 8)
        part.rest_count = 0
        self.assertEqual(bpy.ops.rigmoves.build(), {"FINISHED"})
        self.assertEqual(part.rest_count, 8)
        # And with one it is told when it is next framed another way.
        self.reframe_with_the_cursor()
        self.assertEqual(bpy.ops.rigmoves.build(), {"FINISHED"})
        self.check_lid()


class TestARenamedPart(ChestCase):
    """The lid of a built chest is renamed with F2. The move named it, and
    looked it up by that name: the panel called it "not in this rig", Record
    recorded no part, Build took the drag for the rest, Ring refused, and
    taking it out left the binding behind."""

    def rename(self, name="Cover"):
        self.lid.name = name
        bpy.context.view_layer.update()
        select(self.lid)

    def test_the_part_takes_the_new_name_and_is_no_newcomer(self):
        self.rename()
        self.assertEqual(self.move.parts[0].name, "Cover")
        self.assertEqual(rigmoves.newcomers(bpy.context, rig()), [])
        buttons = [kind for _where, kind, _text in drawn_panel() if "." in kind]
        self.assertNotIn("rigmoves.add_to_move", buttons)

    def test_the_part_is_found_by_its_object_before_anything_renames_it(self):
        # Between a rename and the next update nothing has caught up yet.
        self.lid.name = "Cover"
        part = self.move.parts[0]
        self.assertEqual(part.name, "Lid")
        self.assertIs(rigmoves.part_object(part), self.lid)
        select(self.lid)
        self.assertEqual(rigmoves.newcomers(bpy.context, rig()), [])

    def test_record_after_of_a_drag_records_the_part(self):
        self.rename()
        self.lid.matrix_world = turn_about(self.hinge, "X", -60.0) @ self.lid.matrix_world
        bpy.context.view_layer.update()
        self.assertEqual(bpy.ops.rigmoves.record(index=0, which="AFTER"), {"FINISHED"})
        self.assertIn("recorded for 1 part(s)", rig().rigmoves.report)
        self.assertEqual(bpy.ops.rigmoves.build(), {"FINISHED"})
        drive(self.move, 1.0)
        self.assertLess(drift(self.lid, [turn_about(self.hinge, "X", -60.0) @ p
                                         for p in self.shut]), TOLERANCE)

    def test_a_drag_after_a_rename_is_put_back_by_build_like_any_other(self):
        # Build took it for the rest, and the move then started from there.
        self.rename()
        self.lid.location.z += 1.0
        bpy.context.view_layer.update()
        self.assertEqual(bpy.ops.rigmoves.build(), {"FINISHED"})
        self.check_lid()

    def test_ring_works_on_a_renamed_part(self):
        self.rename()
        bpy.context.scene.cursor.location = Vector((0.0, 0.0, 0.0))
        self.assertEqual(bpy.ops.rigmoves.ring(index=0, count=3), {"FINISHED"})
        self.assertEqual(sorted(p.name for p in self.move.parts), ["Cover", "Cover 2", "Cover 3"])

    def test_taking_the_move_out_leaves_nothing_of_the_binding(self):
        self.rename()
        self.assertEqual(bpy.ops.rigmoves.remove(index=0), {"FINISHED"})
        self.assertIsNone(self.lid.parent)
        self.assertEqual([m.type for m in self.lid.modifiers], [])
        self.assertEqual([g.name for g in self.lid.vertex_groups], [])
        self.assertLess(drift(self.lid, self.shut), TOLERANCE)

    def test_what_names_the_part_follows_it(self):
        # A rider copies "Lid"; Follows and Lead keep their meaning when the
        # leader is renamed.
        copy = cube("Copy", (4.0, 0.0, 1.1))
        copy.scale = (2.0, 1.2, 0.2)
        bpy.context.view_layer.update()
        select(copy, self.lid)
        self.assertEqual(bpy.ops.rigmoves.ride_along(index=0, leader="Lid", rig_name=rig().name),
                         {"FINISHED"})
        self.assertEqual(self.move.parts["Copy"].leader, "Lid")
        self.lid.name = "Cover"
        bpy.context.view_layer.update()
        self.assertEqual(bpy.ops.rigmoves.build(), {"FINISHED"})
        self.assertEqual(self.move.parts["Copy"].leader, "Cover")
        self.assertEqual(self.move.parts[0].name, "Cover")

    def test_a_part_renamed_before_the_first_build_builds_and_records(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        lid = cube("Cube", (0.0, 0.0, 1.1))
        lid.scale = (2.0, 1.2, 0.2)
        bpy.context.view_layer.update()
        home = lid.matrix_world.copy()
        select(lid)
        self.assertEqual(bpy.ops.rigmoves.new_move(), {"FINISHED"})
        lid.name = "Lid"
        bpy.context.view_layer.update()
        select(lid)
        lid.matrix_world = turn_about(self.hinge, "X", -self.SWING) @ home
        bpy.context.view_layer.update()
        self.assertEqual(bpy.ops.rigmoves.record(index=0, which="AFTER"), {"FINISHED"})
        self.assertIn("recorded for 1 part(s)", rig().rigmoves.report)
        self.assertEqual(bpy.ops.rigmoves.build(), {"FINISHED"})
        move = rig().rigmoves.moves[0]
        self.assertEqual(move.parts[0].name, "Lid")
        shut = [home @ v.co for v in lid.data.vertices]
        for share in (0.0, 1.0):
            drive(move, share)
            turn = turn_about(self.hinge, "X", -self.SWING * share)
            self.assertLess(drift(lid, [turn @ p for p in shut]), TOLERANCE, share)

    def test_an_object_deleted_in_the_viewport_is_let_go_and_its_name_is_free(self):
        # The pointer a part keeps is a user of the object: deleting it with X
        # leaves it in the file, in no scene, keeping its name.
        select(self.lid)
        self.assertEqual(bpy.ops.object.delete(), {"FINISHED"})
        bpy.context.view_layer.update()
        self.assertIsNone(rigmoves.part_object(self.move.parts[0]))
        rigmoves.catch_up(rig())
        self.assertIsNone(bpy.data.objects.get("Lid"))
        self.assertEqual(cube("Lid", (9.0, 0.0, 0.0)).name, "Lid")


class TestACopyOfAWholeModel(ChestCase):
    """A chest, its rig and its lid are duplicated together (Shift+D) and the
    copy is moved off. The copy's parts still named the original's objects,
    and both rigs played one Action, so building the copy re-keyed the
    original, which then played several metres away from its lid."""

    OFF = Matrix.Translation((6.0, 4.0, 0.0))

    def duplicate(self, **kinds):
        self.rig1 = rig()
        bpy.ops.object.select_all(action="SELECT")
        self.assertEqual(bpy.ops.object.duplicate(**kinds), {"FINISHED"})
        self.assertEqual(bpy.ops.transform.translate(value=(6.0, 4.0, 0.0)), {"FINISHED"})
        bpy.context.view_layer.update()
        self.rig2 = next(o for o in bpy.context.selected_objects if o.type == "ARMATURE")
        self.lid2 = next(o for o in bpy.context.selected_objects if o.type == "MESH")
        self.move2 = self.rig2.rigmoves.moves[0]

    def handle(self, owner, move, share):
        owner.pose.bones[move.handle_name].location.y = move.rail * share
        bpy.context.view_layer.update()

    def check_both(self, original=Matrix.Identity(4)):
        for share in (0.0, 0.5, 1.0):
            self.handle(self.rig1, self.move, share)
            self.handle(self.rig2, self.move2, share)
            self.assertLess(drift(self.lid, self.lid_at(share, original)), TOLERANCE,
                            "the original at {:.0%}".format(share))
            self.assertLess(drift(self.lid2, self.lid_at(share, self.OFF)), TOLERANCE,
                            "the copy at {:.0%}".format(share))
        self.handle(self.rig1, self.move, 0.0)
        self.handle(self.rig2, self.move2, 0.0)

    def build(self, owner, obj):
        select(obj)
        bpy.context.scene.rigmoves_rig = owner
        self.assertEqual(bpy.ops.rigmoves.build(), {"FINISHED"})

    def test_what_blender_does_to_the_pointer_of_a_copied_rig(self):
        # Verified on 5.2 and 4.5: copied with its parts, the copied rig's
        # pointers are re-pointed to the copies (Shift+D and Alt+D alike);
        # copied alone, they go on pointing at the originals.
        self.duplicate()
        self.assertIs(self.move2.parts[0].object, self.lid2)
        self.assertIs(self.move.parts[0].object, self.lid)
        for kinds in ({"linked": False}, {"linked": True}):
            select(rig())
            self.assertEqual(bpy.ops.object.duplicate(**kinds), {"FINISHED"})
            alone = bpy.context.view_layer.objects.active
            self.assertIs(alone.rigmoves.moves[0].parts[0].object, self.lid)

    def test_the_original_is_untouched_by_building_the_copy(self):
        self.duplicate()
        self.check_both()
        self.build(self.rig2, self.lid2)
        self.assertEqual(self.move2.parts[0].name, "Lid.001")
        self.check_both()

    def test_the_copy_plays_an_action_of_its_own_and_the_original_keeps_its_own(self):
        was = self.move.action_name
        self.duplicate()
        self.assertEqual(self.move2.action_name, was)
        self.build(self.rig2, self.lid2)
        self.assertNotEqual(self.move2.action_name, was)
        self.assertEqual(self.move.action_name, was)
        played = {c.action.name for pb in self.rig2.pose.bones for c in pb.constraints
                  if c.type == "ACTION"}
        self.assertEqual(played, {self.move2.action_name})

    def test_building_the_original_afterwards_changes_nothing_for_the_copy(self):
        self.duplicate()
        self.build(self.rig2, self.lid2)
        self.build(self.rig1, self.lid)
        self.check_both()


class TestOneObjectOneMove(ChestCase):
    """An object is bound to one bone, so it can be in one move. A second move
    on an object that a built move plays gave it a second bone, took the first
    group off it, and left it moved by neither move, with a Build report about
    "copied" parts that was not true."""

    SAID = ("'Lid' is already in 'Move 1', so it was left out: an object moves in "
            "one move. For a second motion, add a Step to 'Move 1'.")

    def coin(self):
        coin = cube("Coin", (0.3, 0.0, 0.6))
        coin.scale = (0.3, 0.3, 0.05)
        bpy.context.view_layer.update()
        return coin

    def test_a_second_move_on_the_lid_is_refused_and_nothing_changes(self):
        select(self.lid)
        before = set(bpy.data.objects.keys())
        self.assertEqual(bpy.ops.rigmoves.new_move(), {"CANCELLED"})
        self.assertEqual(rig().rigmoves.report, self.SAID)
        self.assertEqual(len(rig().rigmoves.moves), 1)
        self.assertEqual(set(bpy.data.objects.keys()), before)
        self.assertEqual([g.name for g in self.lid.vertex_groups], ["Lid"])
        self.check_lid()

    def test_the_coin_is_taken_and_the_lid_is_left_out_with_the_sentence(self):
        coin = self.coin()
        coin_home = coin.matrix_world.copy()
        select(self.lid, coin)
        self.assertEqual(bpy.ops.rigmoves.new_move(), {"FINISHED"})
        second = rig().rigmoves.moves[1]
        self.assertEqual([p.name for p in second.parts], ["Coin"])
        self.assertIn(self.SAID, rig().rigmoves.report)
        coin.matrix_world = Matrix.Translation((0.0, -2.2, -0.575)) @ coin_home
        bpy.context.view_layer.update()
        self.assertEqual(bpy.ops.rigmoves.record(index=1, which="AFTER"), {"FINISHED"})
        self.assertEqual(bpy.ops.rigmoves.build(), {"FINISHED"})
        self.assertEqual([g.name for g in self.lid.vertex_groups], ["Lid"])
        self.check_lid()
        drive(second, 1.0)
        self.assertLess(drift(coin, [Matrix.Translation((0.0, -2.2, -0.575)) @ coin_home @ v.co
                                     for v in coin.data.vertices]), TOLERANCE)

    def test_add_to_this_group_leaves_out_an_object_of_another_move(self):
        coin = self.coin()
        select(coin)
        self.assertEqual(bpy.ops.rigmoves.new_move(), {"FINISHED"})
        select(self.lid, coin)
        self.assertEqual(bpy.ops.rigmoves.add_to_move(index=1, rig_name=rig().name),
                         {"CANCELLED"})
        self.assertEqual(rig().rigmoves.report, self.SAID)
        self.assertEqual([p.name for p in rig().rigmoves.moves[1].parts], ["Coin"])

    def test_ride_along_leaves_out_an_object_of_another_rigs_move(self):
        coin = self.coin()
        select(coin)
        self.assertEqual(bpy.ops.rigmoves.new_move(fresh=True), {"FINISHED"})
        other = rig()
        self.assertNotEqual(other.name, self.move.id_data.name)
        copy = cube("Copy", (4.0, 0.0, 1.1))
        copy.scale = (2.0, 1.2, 0.2)
        bpy.context.view_layer.update()
        select(copy, coin, self.lid)
        bpy.context.scene.rigmoves_rig = self.move.id_data
        self.assertEqual(bpy.ops.rigmoves.ride_along(index=0, leader="Lid",
                                                     rig_name=self.move.id_data.name),
                         {"FINISHED"})
        riders = [p.name for p in self.move.parts if p.leader]
        self.assertEqual(riders, ["Copy"])
        self.assertIn("'Coin' is already in 'Move 1', so it was left out",
                      self.move.id_data.rigmoves.report)

    def test_several_objects_left_out_are_named_together(self):
        one, two = self.coin(), cube("Penny", (0.9, 0.0, 0.6))
        select(one, two)
        self.assertEqual(bpy.ops.rigmoves.new_move(), {"FINISHED"})
        select(self.lid, one, two)
        held = rigmoves.moves_holding(bpy.context, [self.lid, one, two])
        self.assertEqual(sorted(o.name for o in held), ["Coin", "Lid", "Penny"])
        said = rigmoves.left_out_words(held)
        self.assertIn("'Lid'", said)
        self.assertIn("are already in a move, so they were left out", said)
        only = rigmoves.left_out_words({one: held[one], two: held[two]})
        self.assertIn("are already in 'Move 2', so they were left out", only)
        self.assertTrue(only.endswith("add a Step to 'Move 2'."), only)

    def test_a_file_with_an_object_in_two_moves_is_reported_and_not_stripped_further(self):
        # Made the way 0.18.3 let it be made: the guard is off for the setup.
        with mock.patch.object(rigmoves, "moves_holding", create=True, return_value={}):
            select(self.lid)
            self.assertEqual(bpy.ops.rigmoves.new_move(), {"FINISHED"})
        self.lid.location.z += 0.2
        bpy.context.view_layer.update()
        self.assertEqual(bpy.ops.rigmoves.record(index=1, which="AFTER"), {"FINISHED"})
        self.assertEqual(bpy.ops.rigmoves.build(), {"FINISHED"})
        self.assertIn("'Lid' is a part of 'Move 1' and 'Move 2', and an object moves in "
                      "one move", rig().rigmoves.report)
        self.assertEqual([g.name for g in self.lid.vertex_groups], ["Lid"])
        self.assertEqual([m.type for m in self.lid.modifiers], ["ARMATURE"])
        self.check_lid()


class TestACopyAddedToAMove(ChestCase):
    """A Shift+D or Alt+D copy of a built part carries its vertex group and its
    Armature modifier, which is how Blender copies a rigged mesh: it swings
    about the original's hinge until it is bound to a bone of its own. Added to
    the move with Add To This Group, the eye on After then showed it seven
    metres from where it stands, and an After posed by that eye played
    somewhere else."""

    OFF = Matrix.Translation((4.0, 0.0, 0.0))

    def copy_of_the_lid(self, linked=False):
        select(self.lid)
        self.assertEqual(bpy.ops.object.duplicate(linked=linked), {"FINISHED"})
        copy = bpy.context.view_layer.objects.active
        copy.matrix_world = self.OFF @ copy.matrix_world
        bpy.context.view_layer.update()
        return copy

    def test_the_eye_shows_the_copy_where_it_stands_and_an_after_posed_by_it_plays_there(self):
        copy = self.copy_of_the_lid()
        copy_home = copy.matrix_world.copy()
        select(copy, self.lid)
        self.assertEqual(bpy.ops.rigmoves.add_to_move(index=0, rig_name=rig().name),
                         {"FINISHED"})
        self.assertEqual([g.name for g in copy.vertex_groups], [])
        self.assertEqual([m.type for m in copy.modifiers], [])
        self.assertEqual(bpy.ops.rigmoves.show(index=0, which="AFTER"), {"FINISHED"})
        self.assertLess(drift(copy, rest_points(copy)), TOLERANCE)
        # Dragged until it looks right on screen, and recorded.
        wanted = turn_about(self.OFF @ self.hinge, "X", -45.0) @ copy_home
        copy.matrix_world = wanted
        bpy.context.view_layer.update()
        self.assertLess(drift(copy, [wanted @ v.co for v in copy.data.vertices]), TOLERANCE)
        select(copy)
        self.assertEqual(bpy.ops.rigmoves.record(index=0, which="AFTER"), {"FINISHED"})
        self.assertEqual(bpy.ops.rigmoves.build(), {"FINISHED"})
        drive(self.move, 1.0)
        self.assertLess(drift(copy, [wanted @ v.co for v in copy.data.vertices]), TOLERANCE)

    def test_an_alt_d_copy_is_freed_without_taking_the_original_s_binding(self):
        # Its mesh is the original's, and the groups live on the mesh.
        copy = self.copy_of_the_lid(linked=True)
        self.assertIs(copy.data, self.lid.data)
        select(copy, self.lid)
        self.assertEqual(bpy.ops.rigmoves.add_to_move(index=0, rig_name=rig().name),
                         {"FINISHED"})
        self.assertIsNot(copy.data, self.lid.data)
        self.assertEqual([g.name for g in copy.vertex_groups], [])
        self.assertEqual([g.name for g in self.lid.vertex_groups], ["Lid"])
        # The sliders were paused for the newcomer: Build puts them back.
        self.assertEqual(bpy.ops.rigmoves.build(), {"FINISHED"})
        self.assertEqual([g.name for g in self.lid.vertex_groups], ["Lid"])
        self.check_lid()

    def test_a_copy_started_as_a_move_of_its_own_stands_still_too(self):
        copy = self.copy_of_the_lid()
        drive(self.move, 1.0)
        select(copy)
        self.assertEqual(bpy.ops.rigmoves.new_move(fresh=True), {"FINISHED"})
        self.assertEqual([g.name for g in copy.vertex_groups], [])
        self.assertLess(drift(copy, rest_points(copy)), TOLERANCE)


class TestAChildLeftBehind(CopyThatCase):
    """A handle is parented to a lid (Ctrl+P), only the lid is selected, and the
    lid is swung. The rig moves the lid by deforming its mesh, so the lid's
    object stays where it is and so does the handle: it stayed where the shut
    lid was, two metres off at the end, and nothing said so."""

    SAID = ("'Handle' hangs from 'Lid' but is not in a move, so it will not move with "
            "it: select it too and press Add To This Group.")

    def setUp(self):
        super().setUp()
        self.lid = cube("Lid", (0.0, 0.0, 1.1))
        self.lid.scale = (2.0, 1.2, 0.2)
        self.handle = cube("Handle", (0.0, -0.66, 1.1))
        self.handle.scale = (0.3, 0.1, 0.08)
        bpy.context.view_layer.update()
        self.hang(self.handle)

    def hang(self, child):
        select(child, self.lid)
        bpy.context.view_layer.objects.active = self.lid
        self.assertEqual(bpy.ops.object.parent_set(type="OBJECT", keep_transform=False),
                         {"FINISHED"})
        bpy.context.view_layer.update()

    def test_new_move_on_the_lid_alone_names_the_handle(self):
        select(self.lid)
        self.assertEqual(bpy.ops.rigmoves.new_move(), {"FINISHED"})
        self.assertIn(self.SAID, rig().rigmoves.report)

    def test_with_the_handle_selected_too_nothing_is_said(self):
        select(self.handle, self.lid)
        self.assertEqual(bpy.ops.rigmoves.new_move(), {"FINISHED"})
        self.assertNotIn("hangs from", rig().rigmoves.report)
        self.assertEqual(sorted(p.name for p in rig().rigmoves.moves[0].parts),
                         ["Handle", "Lid"])

    def test_build_says_it_again_while_the_handle_is_left_behind(self):
        select(self.lid)
        self.assertEqual(bpy.ops.rigmoves.new_move(), {"FINISHED"})
        self.lid.rotation_euler.x = math.radians(-100.0)
        bpy.context.view_layer.update()
        self.assertEqual(bpy.ops.rigmoves.record(index=0, which="AFTER"), {"FINISHED"})
        self.assertEqual(bpy.ops.rigmoves.build(), {"FINISHED"})
        self.assertIn(self.SAID, rig().rigmoves.report)

    def test_add_to_this_group_names_the_children_of_what_it_adds(self):
        coin = cube("Coin", (5.0, 0.0, 0.6))
        select(coin)
        self.assertEqual(bpy.ops.rigmoves.new_move(), {"FINISHED"})
        self.assertNotIn("hangs from", rig().rigmoves.report)
        select(self.lid, coin)
        self.assertEqual(bpy.ops.rigmoves.add_to_move(index=0, rig_name=rig().name),
                         {"FINISHED"})
        self.assertIn(self.SAID, rig().rigmoves.report)

    def test_a_child_that_is_not_a_mesh_cannot_move_with_it(self):
        self.handle.select_set(False)
        bpy.data.objects.remove(self.handle, do_unlink=True)
        lamp = bpy.data.objects.new("Lamp", None)
        bpy.context.scene.collection.objects.link(lamp)
        bpy.context.view_layer.update()
        self.hang(lamp)
        select(self.lid)
        self.assertEqual(bpy.ops.rigmoves.new_move(), {"FINISHED"})
        self.assertIn("'Lamp' hangs from 'Lid' but is not a mesh, so it cannot move with it.",
                      rig().rigmoves.report)
        self.assertNotIn("press Add To This Group", rig().rigmoves.report)

    def test_up_to_three_are_named(self):
        for number in range(4):
            knob = cube("Knob {:d}".format(number), (float(number) * 0.3, -0.66, 1.1))
            knob.scale = (0.1, 0.1, 0.1)
            self.hang(knob)
        select(self.lid)
        self.assertEqual(bpy.ops.rigmoves.new_move(), {"FINISHED"})
        said = rig().rigmoves.report
        self.assertIn("hang from 'Lid' but are not in a move, so they will not move with "
                      "it: select them too and press Add To This Group.", said)
        self.assertIn(" and 2 more hang", said)
        self.assertEqual(said.count("'Knob") + said.count("'Handle'"), 3)


class TestAPartNextToAnotherModel(ChestCase):
    """What is in another rig's model is told by the rig that deforms it or holds
    it, not by a part of that model somewhere above it."""

    def test_a_handle_hung_on_the_lid_can_start_a_move_of_its_own(self):
        handle = cube("Handle", (0.0, -0.66, 1.1))
        handle.scale = (0.3, 0.1, 0.08)
        bpy.context.view_layer.update()
        select(handle, self.lid)
        bpy.context.view_layer.objects.active = self.lid
        self.assertEqual(bpy.ops.object.parent_set(type="OBJECT", keep_transform=False),
                         {"FINISHED"})
        bpy.context.view_layer.update()
        home = handle.matrix_world.copy()
        select(handle)
        self.assertEqual(bpy.ops.rigmoves.new_move(fresh=True), {"FINISHED"})
        other = rig()
        self.assertNotEqual(other.name, self.move.id_data.name)
        move = other.rigmoves.moves[0]
        self.assertIs(rigmoves.part_object(move.parts[0]), handle)
        handle.matrix_world = Matrix.Translation((0.0, 0.0, 0.5)) @ home
        bpy.context.view_layer.update()
        self.assertEqual(bpy.ops.rigmoves.record(index=0, which="AFTER"), {"FINISHED"})
        self.assertEqual(bpy.ops.rigmoves.build(), {"FINISHED"})
        self.assertIs(handle.parent, other)
        handle_points = [home @ v.co for v in handle.data.vertices]
        for share, lift in ((0.0, 0.0), (1.0, 0.5)):
            drive(move, share)
            self.assertLess(drift(handle, [Matrix.Translation((0.0, 0.0, lift)) @ p
                                           for p in handle_points]), TOLERANCE, share)


class TestRegistration(unittest.TestCase):

    def test_reload_registers_again(self):
        # What a script reload does: a fresh copy of the module registers
        # while the old one is still in.
        global rigmoves
        rigmoves = importlib.reload(rigmoves)
        rigmoves.register()
        self.assertTrue(hasattr(bpy.types.Object, "rigmoves"))


class TestManifest(unittest.TestCase):
    """What Blender installs the extension by must say what the add-on says.

    The oldest Blender is typed twice, and a release once claimed 4.4 while a
    part of it only worked from 4.5: the manifest is what keeps an older
    Blender from installing it, so it must not drift from bl_info."""

    def manifest_line(self, key):
        path = os.path.join(os.path.dirname(os.path.abspath(rigmoves.__file__)),
                            "blender_manifest.toml")
        with open(path, encoding="utf-8") as handle:
            found = re.findall(r'(?m)^{:s}\s*=\s*"([^"]*)"\s*$'.format(key), handle.read())
        self.assertEqual(len(found), 1, key)
        return found[0]

    def test_the_manifest_and_bl_info_name_one_blender(self):
        minimum = self.manifest_line("blender_version_min")
        self.assertEqual(minimum, ".".join(map(str, rigmoves.bl_info["blender"])))
        # The Blender running the tests is one the add-on claims to work on.
        self.assertGreaterEqual(tuple(bpy.app.version),
                                tuple(int(number) for number in minimum.split(".")))
        # build_zip writes the version into the zip's own copy of the manifest,
        # but the copy in the tree must not be left behind either.
        self.assertEqual(self.manifest_line("version"),
                         ".".join(map(str, rigmoves.bl_info["version"])))


if __name__ == "__main__":
    # Inside a Blender binary sys.argv is Blender's own command line; only what
    # follows "--" is meant for the tests.
    argv = sys.argv
    if "--" in argv:
        argv = [argv[0]] + argv[argv.index("--") + 1:]
    elif not argv[0].endswith(".py"):
        argv = [argv[0]]
    unittest.main(argv=argv, verbosity=2)
