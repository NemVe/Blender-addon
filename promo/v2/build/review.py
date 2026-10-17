"""The review folder of v2.3: a contact sheet of the opening at 1 frame a second, and stills of its key moments, from the finished film.

    python promo/v2/build/review.py <review folder>

The opening is the film's first beat (the walkthrough with a timer). The stills are taken where the schedule says things happen, from
timeline.json (where the first click is) and walk_schedule.json (the marks of the walkthrough): the six parts selected, a typed value,
each Ring dialog with its values set, the Spread dialog, the typed delays, Build, the timer's final card, and the bloom.
"""
import json
import os
import subprocess
import sys

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
FILM = os.path.join(REPO, "dist", "promo", "v2", "CopyThat_promo_v2_1440p60.mp4")
TIMELINE = os.path.join(HERE, "..", "timeline.json")
SCHEDULE = os.path.join(HERE, "..", "walk_schedule.json")
FPS, TILE = 1, 320                       # the contact sheet: one frame a second, 320 px wide each


def stills(go, marks):
    return [("six_parts_selected", go + marks["newmove"] - 0.4), ("typing_leaf2_minus145", go + marks["v_leaf2"] - 0.5),
            ("ring1_outer_dialog", go + marks["ring1_ok"] - 0.3), ("ring2_inner_dialog", go + marks["ring2_ok"] - 0.3),
            ("ring3_leaf_dialog", go + marks["ring3_ok"] - 0.25), ("spread_dialog", go + marks["spread_ok"] - 0.3),
            ("typed_delays", go + marks["delays"] - 0.05), ("build", go + marks["build"] + 0.7),
            ("bloom", go + marks["grab"] + 1.4), ("timer_final_card", go + marks["end"] + 0.6)]


def main():
    dest = sys.argv[1]
    os.makedirs(dest, exist_ok=True)
    T = json.load(open(TIMELINE, encoding="utf-8"))
    marks = json.load(open(SCHEDULE, encoding="utf-8"))["marks"]
    opening = T["beats"][0]
    go, length = opening["steps"]["go"], opening["end"] - opening["start"]
    tmp = os.path.join(dest, "_secs")
    os.makedirs(tmp, exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", FILM, "-t", "{:.3f}".format(length), "-vf", "fps={:d},scale={:d}:-1".format(FPS, TILE),
                    os.path.join(tmp, "%03d.png")], check=True)
    files = sorted(os.listdir(tmp))
    cols = 10
    with Image.open(os.path.join(tmp, files[0])) as first:
        th = first.height
    rows = (len(files) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * TILE, rows * th), (20, 20, 20))
    draw = ImageDraw.Draw(sheet)
    for i, f in enumerate(files):
        x, y = (i % cols) * TILE, (i // cols) * th
        with Image.open(os.path.join(tmp, f)) as im:
            sheet.paste(im.convert("RGB"), (x, y))
        draw.rectangle([x, y, x + 40, y + 15], fill=(0, 0, 0))
        draw.text((x + 4, y + 2), "{:d} s".format(i), fill=(255, 220, 140))
        os.remove(os.path.join(tmp, f))
    os.rmdir(tmp)
    sheet.save(os.path.join(dest, "contact_sheet_opening_1fps.png"))
    for n, (name, t) in enumerate(stills(go, marks), 1):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "{:.3f}".format(t), "-i", FILM, "-frames:v", "1",
                        os.path.join(dest, "still_{:02d}_{:s}_{:.1f}s.png".format(n, name, t))], check=True)
    print(sheet.size, len(stills(go, marks)), "stills in", dest)


if __name__ == "__main__":
    main()
