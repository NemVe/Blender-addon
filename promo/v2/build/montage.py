"""Tile the PNGs of a folder into one contact sheet:  python montage.py DIR OUT.png [columns] [thumb_width]"""
import os
import sys

from PIL import Image, ImageDraw

folder, out = sys.argv[1], sys.argv[2]
cols = int(sys.argv[3]) if len(sys.argv) > 3 else 4
tw = int(sys.argv[4]) if len(sys.argv) > 4 else 640
files = sorted(f for f in os.listdir(folder) if f.lower().endswith(".png"))
first = Image.open(os.path.join(folder, files[0]))
th = round(tw * first.height / first.width)
rows = (len(files) + cols - 1) // cols
sheet = Image.new("RGB", (cols * tw, rows * th), (30, 30, 30))
draw = ImageDraw.Draw(sheet)
for i, f in enumerate(files):
    im = Image.open(os.path.join(folder, f)).convert("RGB").resize((tw, th), Image.LANCZOS)
    x, y = (i % cols) * tw, (i // cols) * th
    sheet.paste(im, (x, y))
    draw.rectangle([x, y, x + 100, y + 16], fill=(0, 0, 0))
    draw.text((x + 4, y + 2), f.rsplit(".", 1)[0][-5:] + " s", fill=(255, 220, 140))
sheet.save(out)
print(out, sheet.size)
