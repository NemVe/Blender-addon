#!/usr/bin/env bash
# Installs a built zip into a throwaway Blender profile, as a user would, and
# draws the installed extension's panel. The test suite imports rigmoves/
# directly, so it cannot see what Blender changes when it installs an
# extension: it deletes bl_info, which 0.20.0's footer read at every redraw.
#
#   bash tools/check_installed.sh dist/CopyThat-<version>.zip [blender.exe]
#
# Your own Blender settings and extensions are not touched.
ZIP="$1"
BLENDER="${2:-/c/Program Files/Blender Foundation/Blender 5.2/blender.exe}"
HERE="$(cd "$(dirname "$0")" && pwd)"
PROFILE="$(cygpath -m "$(mktemp -d)")"
export PYTHONIOENCODING=utf-8 BLENDER_USER_RESOURCES="$PROFILE" \
    BLENDER_USER_CONFIG="$PROFILE/config" BLENDER_USER_SCRIPTS="$PROFILE/scripts" \
    BLENDER_USER_EXTENSIONS="$PROFILE/extensions" BLENDER_USER_DATAFILES="$PROFILE/datafiles"
"$BLENDER" --command extension install-file -r user_default -e "$ZIP" | tail -1
"$BLENDER" --background --python-exit-code 1 --python "$HERE/draw_installed.py" > "$PROFILE/log.txt" 2>&1
code=$?
grep -E "^(extension module|panel drawn)|Error|Traceback" "$PROFILE/log.txt"
rm -rf "$PROFILE"
if [ $code -eq 0 ]; then echo "OK: the installed panel draws"; else echo "FAILED (exit $code)"; fi
exit $code
