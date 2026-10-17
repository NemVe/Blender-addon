"""Cut the sidebar out of the whole-window screenshots ui_states.py took.

    python promo/tools/crop_shots.py <shots folder> <out folder>

Needs Pillow. Each <name>_sNNN.png in the shots folder is cropped to the sidebar
region recorded in geometry.jsonl and written to the out folder under the same
name. Blender's window origin is the bottom left; the image's is the top left.
"""

import json
import os
import sys

from PIL import Image

shots, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
with open(os.path.join(shots, "geometry.jsonl"), encoding="utf-8") as handle:
    for line in handle:
        info = json.loads(line)
        path = os.path.join(shots, info["file"])
        if not os.path.exists(path):
            continue
        image = Image.open(path)
        x, y, width, height = info["ui"]
        top = image.height - (y + height)
        crop = image.crop((x, max(top, 0), x + width, top + height))
        crop.save(os.path.join(out, info["file"]))
        print(info["file"], image.size, "->", crop.size)
