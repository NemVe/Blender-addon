"""The review folder of v2.2: a contact sheet of the first 20 s of the finished film at 2 frames a second, and 4 stills of the opening.

    python promo/v2/build/review.py <review folder>

The stills are taken where the opening's clicks are, from timeline.json: the first click, a pose drag, a Ring's copies, the bloom.
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
SECONDS, FPS = 20, 2                    # the contact sheet: the first 20 s, two frames a second


def stills():
    steps = json.load(open(TIMELINE, encoding="utf-8"))["beats"][0]["steps"]
    return [(steps["new"] + 0.2, "first_click"), (steps["pose"] + 0.45, "pose_drag"), (steps["o2"] + 0.3, "ring_copies"),
            (steps["drag"] + 1.5, "bloom")]


def main():
    dest = sys.argv[1]
    os.makedirs(dest, exist_ok=True)
    tmp = os.path.join(dest, "_secs")
    os.makedirs(tmp, exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", FILM, "-t", str(SECONDS), "-vf", "fps={:d},scale=480:-1".format(FPS), os.path.join(tmp, "%03d.png")], check=True)
    files = sorted(os.listdir(tmp))
    cols, tw = 8, 480
    with Image.open(os.path.join(tmp, files[0])) as first:
        th = first.height
    rows = (len(files) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * tw, rows * th), (20, 20, 20))
    draw = ImageDraw.Draw(sheet)
    for i, f in enumerate(files):
        x, y = (i % cols) * tw, (i // cols) * th
        with Image.open(os.path.join(tmp, f)) as im:
            sheet.paste(im.convert("RGB"), (x, y))
        draw.rectangle([x, y, x + 46, y + 16], fill=(0, 0, 0))
        draw.text((x + 4, y + 2), "{:.1f} s".format(i / FPS), fill=(255, 220, 140))
        os.remove(os.path.join(tmp, f))
    os.rmdir(tmp)
    sheet.save(os.path.join(dest, "contact_sheet_first20s_2fps.png"))
    for n, (t, name) in enumerate(stills(), 1):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(t), "-i", FILM, "-frames:v", "1",
                        os.path.join(dest, "still_{:02d}_{:s}_{:.1f}s.png".format(n, name, t))], check=True)
    print(sheet.size, len(stills()), "stills in", dest)


if __name__ == "__main__":
    main()
