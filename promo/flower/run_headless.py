"""Apply a scene generator at once, with no window: the headless half of the
contract in SPEC.md.

    from run_headless import run
    run(flower_steps(parts))

A tween jumps to its end, a wait is skipped, a call runs straight away (there
is no viewport to override), and captions are only collected. It returns the
captions, as (chip, line) pairs, in the order the steps asked for them.
`after_call(fn)`, if given, is run after every call, for a test to look in.
"""

import bpy


def run(steps, scene=None, verbose=False, after_call=None):
    scene = scene or bpy.context.scene
    chip, line = "", ""
    captions = []
    for action in steps:
        kind = action[0]
        if kind == "caption":
            _kind, new_chip, new_line = action
            chip = chip if new_chip is None else new_chip
            line = line if new_line is None else new_line
            captions.append((chip, line))
            if verbose:
                print("  caption:", chip, "|", line)
        elif kind == "wait":
            pass
        elif kind == "tween":
            for obj, matrix in action[1]:
                obj.matrix_world = matrix
            bpy.context.view_layer.update()
        elif kind == "tween_value":
            _kind, setter, _start, end, _seconds = action
            setter(end)
            bpy.context.view_layer.update()
        elif kind == "call":
            action[1]()
            bpy.context.view_layer.update()
            if after_call is not None:
                after_call(action[1])
        elif kind == "view":
            spec = action[1]
            if spec.get("camera") is not None:
                scene.camera = spec["camera"]
        else:
            raise ValueError("unknown action {!r}".format(kind))
    return captions
