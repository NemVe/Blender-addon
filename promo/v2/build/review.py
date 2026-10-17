"""The review folder: a contact sheet (a frame a second) and 12 stills, taken from the finished film.

    python promo/v2/build/review.py <review folder>
"""
import os
import subprocess
import sys

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
FILM = os.path.join(REPO, "dist", "promo", "v2", "CopyThat_promo_v2_1440p60.mp4")
STILLS = [(4.4, "hook2_rig"), (11.6, "logo"), (15.7, "idea1_record"), (19.4, "idea2_slider"), (29.6, "f02_spread"), (38.1, "f05_curves"),
          (43.7, "f07_chain"), (48.8, "f09_ring"), (57.0, "f12_animate"), (63.4, "together_bloom"), (69.9, "real_blender"), (74.6, "end_card")]


def main():
    dest = sys.argv[1]
    os.makedirs(dest, exist_ok=True)
    tmp = os.path.join(dest, "_secs")
    os.makedirs(tmp, exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", FILM, "-vf", "fps=1,scale=480:-1", os.path.join(tmp, "%03d.png")], check=True)
    files = sorted(os.listdir(tmp))
    cols, tw = 8, 480
    first = Image.open(os.path.join(tmp, files[0]))
    th = first.height
    rows = (len(files) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * tw, rows * th), (20, 20, 20))
    draw = ImageDraw.Draw(sheet)
    for i, f in enumerate(files):
        x, y = (i % cols) * tw, (i // cols) * th
        sheet.paste(Image.open(os.path.join(tmp, f)).convert("RGB"), (x, y))
        draw.rectangle([x, y, x + 46, y + 16], fill=(0, 0, 0))
        draw.text((x + 4, y + 2), "{:d} s".format(i), fill=(255, 220, 140))
        os.remove(os.path.join(tmp, f))
    os.rmdir(tmp)
    sheet.save(os.path.join(dest, "contact_sheet_1fps.png"))
    for n, (t, name) in enumerate(STILLS, 1):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(t), "-i", FILM, "-frames:v", "1",
                        os.path.join(dest, "still_{:02d}_{:s}_{:.1f}s.png".format(n, name, t))], check=True)
    print(sheet.size, len(STILLS), "stills in", dest)


if __name__ == "__main__":
    main()
