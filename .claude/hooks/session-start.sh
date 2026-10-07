#!/bin/bash
# Cloud sessions only: install Blender as a Python module into .venv, so the
# add-on can be loaded and tested without a Blender window:
#
#     .venv/bin/python tests/test_rigmoves.py
#
# On your own machine, test in your own Blender (see README.md).
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "$CLAUDE_PROJECT_DIR"
VENV=.venv
# bpy 5.2 is built for Python 3.13 only.
BPY_VERSION=5.2.2

if "$VENV/bin/python" -c "import bpy, sys; sys.exit(not bpy.app.version_string.startswith('$BPY_VERSION'))" >/dev/null 2>&1; then
  echo "Blender $BPY_VERSION already in $VENV"
  exit 0
fi

if command -v uv >/dev/null 2>&1; then
  uv venv -q --allow-existing -p 3.13 "$VENV"
  uv pip install -q -p "$VENV/bin/python" "bpy==$BPY_VERSION"
else
  python3.13 -m venv "$VENV"
  "$VENV/bin/pip" install -q "bpy==$BPY_VERSION"
fi
echo "Installed Blender $BPY_VERSION into $VENV"
