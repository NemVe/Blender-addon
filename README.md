# RigMoves

A Blender add-on: move the parts of a machine by hand, record where they were
and where they ended up, and get one control that plays it. The user guide is
[rigmoves/README.md](rigmoves/README.md).

Needs Blender 4.4 or later.

By **NemVe3D** - <https://creators.sa/nemve>

## Install

    python tools/build_zip.py

writes `dist/RigMoves-<version>.zip`. In Blender: Edit > Preferences > Add-ons >
Install from Disk, pick the zip, tick it on. The panel is in the 3D view
sidebar (**N**), tab **Moves**.

## What is where

| | |
|---|---|
| `rigmoves/` | the add-on itself - this folder is what goes in the zip |
| `tests/test_rigmoves.py` | end-to-end tests, run in Blender without a window |
| `tools/build_zip.py` | makes the install zip |
| `.claude/` | sets up Claude Code cloud sessions to run the tests |

## Tests

They press the panel's buttons on real cubes and measure where the deformed
meshes end up. Either with Blender as a Python module (`bpy` 5.2 needs Python
3.13):

    python3.13 -m venv .venv
    .venv/bin/pip install bpy==5.2.2
    .venv/bin/python tests/test_rigmoves.py

or with a Blender you already have:

    blender --background --factory-startup --python tests/test_rigmoves.py

In a Claude Code cloud session `.venv` is made for you when the session
starts. Lint with `ruff check rigmoves tests tools`.
