#!/bin/bash
# Wait for the 1440p outro render to finish (its log gets "RENDER SECONDS"),
# then render the three hook shots on the GPU, one after another.
S="C:/Users/ADMINI~1/AppData/Local/Temp/claude/C--Users-Administrator-Desktop-AutoRigger-CopyThat/06edfcac-c07f-4302-96bc-7fc6916a0fd8/scratchpad"
until grep -q "RENDER SECONDS" "$S/outro_render_1440.log" 2>/dev/null; do sleep 20; done
for shot in A B C; do
  "/c/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --factory-startup "C:/Users/Administrator/Desktop/AutoRigger/CopyThat/promo/files/CopyThat_outro.blend" --python "C:/Users/Administrator/Desktop/AutoRigger/CopyThat/promo/outro/hook_shots.py" -- "$S/hooks_1440" --shot $shot >> "$S/hooks_render.log" 2>&1
  echo "shot $shot done $(date +%H:%M)" >> "$S/hooks_render.log"
done
echo "ALL HOOKS DONE $(date +%H:%M)" >> "$S/hooks_render.log"
