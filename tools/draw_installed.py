"""Draws the panel of CopyThat as installed from its zip, the way Blender loaded it (run by check_installed.sh).

Blender changes an extension as it loads it - it deletes bl_info, for one - and the test suite, which imports rigmoves/
directly, cannot see that. Any error here ends Blender with exit code 1 (check_installed.sh passes --python-exit-code).
"""
import sys

import bpy

name = next((n for n in sys.modules if n.startswith("bl_ext.") and n.endswith(".copythat")), None)
if name is None:
    raise SystemExit("CopyThat is not loaded as an extension")
module = sys.modules[name]
print("extension module: {:s}; bl_info kept by Blender: {}".format(name, hasattr(module, "bl_info")))
said = []


class Layout:
    """Takes any call or setting a panel makes, and keeps what the labels say."""

    def label(self, text="", **_kwargs):
        said.append(text)

    def __getattr__(self, attr):
        if attr.startswith("__"):
            raise AttributeError(attr)
        return lambda *_args, **_kwargs: Layout()

    def __setattr__(self, attr, value):
        pass


class Panel:
    layout = Layout()


for attr in dir(module.RIGMOVES_PT_panel):
    if attr == "draw" or attr.startswith("_draw"):
        setattr(Panel, attr, getattr(module.RIGMOVES_PT_panel, attr))
Panel().draw(bpy.context)
print("panel drawn; its last line: {:s}".format([text for text in said if text][-1]))
