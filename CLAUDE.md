# CopyThat (formerly RigMoves) - notes for Claude

- New session? Read `START_HERE.md` first (the session handoff), then
  `HANDOFF.md` and the guide.
- Working locally (Windows, the user's own PC)? Test with their real Blender:
  `"<path to>\blender.exe" --background --factory-startup --python tests/test_rigmoves.py`
  (or a Python 3.13 venv with `pip install bpy==5.2.2`, then
  `.venv\Scripts\python.exe tests\test_rigmoves.py`). The SessionStart
  hook is for cloud sessions only and does nothing locally. Locally you can
  also open Blender's window to check the panel and dialogs for real, and
  render on the user's GPU. The promo scripts in `promo/` still name the old
  cloud scratch folder; point them at `promo/` before running them.
- The zip is a Blender extension: `rigmoves/blender_manifest.toml`, whose
  version `tools/build_zip.py` writes from bl_info. Licence GPL-3.0-or-later
  (`LICENSE`).

- The add-on was renamed from RigMoves to CopyThat in 0.15.0. Only shown
  names changed: the folder `rigmoves`, the `rigmoves.*` operators and
  properties, and the markers stored in files ("RigMoves: " constraints,
  "RigMoves part", "RigMoves follows", "RigMoves rail") stay, so older
  .blend files keep working. Don't rename them.
- The add-on is one file, `rigmoves/__init__.py`, with its user guide
  `rigmoves/README.md`. Keep the guide in step with what the panel shows.
- Targets Blender 4.4+, which keeps action curves under slots, layers and
  strips (`action_bits` in the add-on). Tested headless on 5.2.2.
- Test: `.venv/bin/python tests/test_rigmoves.py` (the SessionStart hook puts
  `bpy` in `.venv`). Lint: `ruff check rigmoves tests tools`. Zip:
  `python tools/build_zip.py`.
- Driver expressions must stay Blender "simple expressions", so they run with
  Auto Run Python Scripts off, and under 256 characters, or Blender cuts them
  short. `test_drivers_need_no_python` checks the first; Build checks the
  second.
- Match the existing style: comments say why, in plain prose; `str.format`,
  not f-strings.
- After every change to the add-on, the user checks it in their own Blender:
  bump `bl_info["version"]` (and the guide's title and zip name with it), add
  any bug fixed to the guide's list, run the tests, build the zip with
  `python tools/build_zip.py`, and send them the zip from `dist/`.
