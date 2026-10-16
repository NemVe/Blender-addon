#!/bin/bash
# Run the whole suite on every Blender this PC has for it, all at once, and
# print one line per Blender. The full logs are kept for when a line says
# FAILED.
#
#     bash tools/test_all_blenders.sh [repo or worktree] [log folder]
#
# The Blender paths are this PC's (see CLAUDE.md, "Working locally"); a path
# that does not exist is skipped and said so.

REPO="${1:-$(cd "$(dirname "$0")/.." && pwd)}"
LOGS="${2:-${TMPDIR:-/tmp}/copythat_tests}"
mkdir -p "$LOGS"
rm -f "$LOGS"/summary_*.txt

declare -A BLENDERS=(
  ["5.2"]="/c/Program Files/Blender Foundation/Blender 5.2/blender.exe"
  ["5.0"]="/c/Program Files/Blender Foundation/Blender 5.0/blender.exe"
  ["4.5"]="/d/Tools/blender-4.5.14-windows-x64/blender.exe"
)

cd "$REPO" || exit 2
for version in "${!BLENDERS[@]}"; do
  exe="${BLENDERS[$version]}"
  if [ ! -x "$exe" ]; then
    echo "$version: skipped, no Blender at $exe" > "$LOGS/summary_$version.txt"
    continue
  fi
  (
    start=$(date +%s)
    "$exe" --background --factory-startup --python tests/test_rigmoves.py > "$LOGS/tests_$version.log" 2>&1
    ran=$(grep -E "^Ran " "$LOGS/tests_$version.log" | tail -1)
    result=$(grep -E "^(OK|FAILED)" "$LOGS/tests_$version.log" | tail -1)
    echo "$version: ${ran:-no result} - ${result:-crashed} ($(( $(date +%s) - start )) s)" > "$LOGS/summary_$version.txt"
  ) &
done
wait
cat "$LOGS"/summary_*.txt
if grep -qE "FAILED|crashed|no result" "$LOGS"/summary_*.txt; then
  echo "logs: $LOGS"
  exit 1
fi
