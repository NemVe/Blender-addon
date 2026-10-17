"""The media of CopyThat's store page, cut from the promo film's segments.

    python promo/store/make_store_media.py [--only name,name]

Writes into dist/store/:
  clips/<name>.mp4   1280x720 loops with no sound, for the page preview (small enough to publish),
                     and clips/<name>.jpg, a still of each for the page to show before it plays
  gifs/<name>.gif    the same loops as GIFs, for Superhive's description (it shows GIFs, not videos)
  images/<name>.jpg  2400x1200 gallery images: Superhive wants five or more at 2:1, at least 1200 px wide
  film_preview.mp4   the whole film at 960x540 with its sound, under 15 MB
  description.html   the product description to paste into Superhive's editor (its code view), with a yellow
                     box where each GIF goes: the editor's video button takes only links (YouTube and the
                     like), so the loops go in as GIFs through its picture button
  documentation.html the full user guide, for the page's documentation
(description and documentation need `pip install markdown`)

The segments are dist/promo/v2/segments/NN_<beat>.mp4 (2560x1440, 60 fps), made by promo/v2/build/finish.py.
"""

import argparse
import os
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SEGMENTS = os.path.join(ROOT, "dist", "promo", "v2", "segments")
FILM = os.path.join(ROOT, "dist", "promo", "v2", "CopyThat_promo_v2_1440p60.mp4")
OUT = os.path.join(ROOT, "dist", "store")

# name -> (segment, start s, end s or None for the whole segment, gif fps, gif width). The long walkthrough
# loops are lighter (fewer frames, narrower): Superhive shows the description's media as GIFs, all on one page.
CLIPS = {
    "rig_select": ("01_open", 2.8, 9.6, 10, 800),
    "rig_pose": ("01_open", 26.0, 34.4, 10, 800),
    "rig_ring": ("01_open", 34.8, 44.0, 10, 800),
    "rig_spread": ("01_open", 61.0, 69.6, 10, 800),
    "rig_build_bloom": ("01_open", 70.0, 78.15, 10, 800),
    "idea_record": ("03_idea1", 0.0, None, 15, 960),
    "idea_build": ("04_idea2", 0.0, None, 15, 960),
    "idea_many": ("05_idea3", 0.0, None, 15, 960),
    "f01_delays": ("06_f01", 0.0, None, 15, 960),
    "f02_spread": ("07_f02", 0.0, None, 15, 960),
    "f03_pivot": ("08_f03", 0.0, None, 15, 960),
    "f04_steps": ("09_f04", 0.0, None, 15, 960),
    "f05_curves": ("10_f05", 0.0, None, 15, 960),
    "f06_speed": ("11_f06", 0.0, None, 15, 960),
    "f07_chain": ("12_f07", 0.0, None, 15, 960),
    "f08_curl": ("13_f08", 0.0, None, 15, 960),
    "f09_ring": ("14_f09", 0.0, None, 15, 960),
    "f10_mirror": ("15_f10", 0.0, None, 15, 960),
    "f11_combine": ("16_f11", 0.0, None, 15, 960),
    "f12_animate": ("17_f12", 0.0, None, 15, 960),
    "together": ("18_together", 2.0, 8.0, 10, 800),
}

# name -> (segment, time s, top of the 2:1 window in the 1440-high frame). The window keeps
# the walkthrough's timer at the top and its status line at the bottom.
IMAGES = {
    "01_featured": ("02_logo", 3.6, 80),
    "02_rigged_in_1m10": ("01_open", 77.7, 110),
    "03_ring_dialog": ("01_open", 42.6, 110),
    "04_spread_dialog": ("01_open", 66.1, 110),
    "05_twenty_one_parts": ("18_together", 5.0, 80),
    "07_rendered": ("18_together", 9.0, 0),
    "06_ring_feature": ("14_f09", 2.2, 80),
}


def run(args):
    subprocess.run(["ffmpeg", "-v", "error", "-y"] + args, check=True)


def segment(name):
    return os.path.join(SEGMENTS, name + ".mp4")


def span(start, end):
    return ["-ss", "{:.3f}".format(start)] + (["-to", "{:.3f}".format(end)] if end else [])


def clip(name):
    seg, start, end, fps, width = CLIPS[name]
    src = segment(seg)
    mp4 = os.path.join(OUT, "clips", name + ".mp4")
    run(span(start, end) + ["-i", src, "-an", "-vf", "scale=1280:720:flags=lanczos,fps=30",
                            "-c:v", "libx264", "-preset", "slow", "-crf", "21", "-pix_fmt", "yuv420p",
                            "-movflags", "+faststart", mp4])
    # A still from late in the loop, where the move has happened, for the page to show before the clip plays.
    length = (end or float(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", src],
        capture_output=True, text=True, check=True).stdout)) - start
    run(["-ss", "{:.3f}".format(start + 0.85 * length), "-i", src, "-frames:v", "1",
         "-vf", "scale=1280:720:flags=lanczos", "-q:v", "4", os.path.join(OUT, "clips", name + ".jpg")])
    gif = os.path.join(OUT, "gifs", name + ".gif")
    # One palette for the whole loop, from what changes: the UI's greys and the gold stay clean.
    graph = ("fps={:d},scale={:d}:-2:flags=lanczos,split[a][b];[a]palettegen=max_colors=160:stats_mode=diff[p];"
             "[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle").format(fps, width)
    run(span(start, end) + ["-i", src, "-filter_complex", graph, "-loop", "0", gif])
    return mp4, gif


# The logo beat's kicker reads "A BLENDER ADD-ON", and Superhive takes no image with the word Blender
# or its logo as a design element: the line is covered with the dark ground just above it.
# (x, y, width, height) in the 2400x1200 image.
COVER = {"01_featured": (130, 228, 300, 48)}


def image(name):
    seg, at, top = IMAGES[name]
    jpg = os.path.join(OUT, "images", name + ".jpg")
    run(["-ss", "{:.3f}".format(at), "-i", segment(seg), "-frames:v", "1",
         "-vf", "crop=2560:1280:0:{:d},scale=2400:1200:flags=lanczos".format(top), "-q:v", "2", jpg])
    if name in COVER:
        from PIL import Image
        x, y, w, h = COVER[name]
        picture = Image.open(jpg)
        picture.paste(picture.crop((x, y - h, x + w, y)), (x, y))
        picture.save(jpg, quality=93)
    return jpg


def descriptions():
    import re
    import markdown

    def to_html(text):
        return markdown.markdown(text, extensions=["tables", "sane_lists"])

    listing = open(os.path.join(ROOT, "docs", "SUPERHIVE_LISTING.md"), encoding="utf-8").read()
    body = listing[listing.index("# Record a move. Get a slider."):]
    # One level down: the store's page has the product's name as its title.
    body = re.sub(r"^## ", "### ", body, flags=re.M)
    body = re.sub(r"^# ", "## ", body, flags=re.M)
    box = '<p style="background:#fff3b0;padding:8px 12px;border:2px dashed #c9a76a">{}</p>'

    def marker(match):
        name = os.path.splitext(os.path.basename(match.group(2)))[0]
        said = "<b>GIF HERE: {}.gif</b> - the picture button, from dist/store/gifs ({})".format(
            name, match.group(1))
        return "\n\n" + box.format(said) + "\n\n"

    body = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", marker, body)
    body = body.replace("▶ Watch the film: VIDEO_URL", box.format(
        "<b>YOUTUBE HERE</b> - the film's YouTube link, through the video button"))
    out = os.path.join(OUT, "description.html")
    open(out, "w", encoding="utf-8").write(to_html(body))
    guide = open(os.path.join(ROOT, "docs", "SUPERHIVE_PAGE.md"), encoding="utf-8").read()
    open(os.path.join(OUT, "documentation.html"), "w", encoding="utf-8").write(to_html(guide))
    return out


def film():
    out = os.path.join(OUT, "film_preview.mp4")
    # About 14 MB for 145 s: the page's files may be 15 MB each.
    run(["-i", FILM, "-vf", "scale=960:540:flags=lanczos,fps=30", "-c:v", "libx264", "-preset", "slow",
         "-b:v", "620k", "-maxrate", "900k", "-bufsize", "1800k", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "80k", "-movflags", "+faststart", out])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    args = ap.parse_args()
    only = set(n for n in args.only.split(",") if n)
    for folder in ("clips", "gifs", "images"):
        os.makedirs(os.path.join(OUT, folder), exist_ok=True)
    for name in CLIPS:
        if not only or name in only:
            mp4, gif = clip(name)
            print("{:18s} mp4 {:6.2f} MB  gif {:6.2f} MB".format(
                name, os.path.getsize(mp4) / 1e6, os.path.getsize(gif) / 1e6), flush=True)
    for name in IMAGES:
        if not only or name in only:
            jpg = image(name)
            print("{:18s} jpg {:6.2f} MB".format(name, os.path.getsize(jpg) / 1e6), flush=True)
    if not only or "description" in only:
        out = descriptions()
        print("description.html   {:d} GIF boxes".format(open(out, encoding="utf-8").read().count("GIF HERE")), flush=True)
    if not only or "film" in only:
        out = film()
        print("film_preview       mp4 {:6.2f} MB".format(os.path.getsize(out) / 1e6), flush=True)


if __name__ == "__main__":
    main()
