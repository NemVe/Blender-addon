"""Footage for the film's page: JPEG sequences in dist/promo/v2/footage, and the real slider's data.

    python promo/v2/build/prep_footage.py

hookC   dist/promo/hooks_1440/hook_C   the Cycles bloom behind the logo
outro   dist/promo/outro_frames_1440   the Cycles bloom the flower dissolves into
real    dist/promo/rec/slider_020/capture.mkv, from the end of the sync flash on: the real panel, new look
real.json   per frame of `real`: the slider's value (0-1), read off the blue fill of the Move 1 slider,
            so that the film's cursor can be drawn dragging it in step
"""

import json
import os
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
OUT = os.path.join(REPO, "dist", "promo", "v2", "footage")
CAPTURE = os.path.join(REPO, "dist", "promo", "rec", "slider_020", "capture.mkv")
ROW_Y, TRACK_X0, TRACK_X1 = 276, 1547, 2021   # the Move 1 slider's track in the 2560x1440 capture


def ffmpeg(*args):
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True)


def sequence(src_pattern, dst_dir, start=1, count=None):
    os.makedirs(dst_dir, exist_ok=True)
    cmd = ["-framerate", "30", "-start_number", str(start), "-i", src_pattern]
    if count:
        cmd += ["-frames:v", str(count)]
    ffmpeg(*cmd, "-q:v", "2", os.path.join(dst_dir, "%04d.jpg"))
    return len([f for f in os.listdir(dst_dir) if f.endswith(".jpg")])


def capture_rows():
    """Every frame's slider row (one pixel high) and its mean brightness (to find the flash)."""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", CAPTURE, "-vf",
                          "crop=520:1:1520:{:d},format=rgb24".format(ROW_Y), "-f", "rawvideo", "-"],
                         check=True, capture_output=True).stdout
    rows = np.frombuffer(raw, np.uint8).reshape(-1, 520, 3).astype(int)
    bright = subprocess.run(["ffmpeg", "-v", "error", "-i", CAPTURE, "-vf", "scale=32:18,format=gray",
                             "-f", "rawvideo", "-"], check=True, capture_output=True).stdout
    mean = np.frombuffer(bright, np.uint8).reshape(-1, 32 * 18).mean(axis=1)
    return rows, mean


def main():
    hooks = os.path.join(REPO, "dist", "promo", "hooks_1440", "hook_C", "hook_C_%04d.png")
    print("hookC", sequence(hooks, os.path.join(OUT, "hookC"), start=152))
    print("outro", sequence(os.path.join(REPO, "dist", "promo", "outro_frames_1440", "outro_%04d.png"),
                            os.path.join(OUT, "outro")))

    rows, mean = capture_rows()
    flash = np.nonzero(mean > 200)[0]
    if not len(flash):
        sys.exit("no sync flash in the capture")
    last_flash = int(flash[0])
    while last_flash + 1 in flash:
        last_flash += 1
    first = last_flash + 1                      # the move starts about 0.07 s after the flash
    n_frames = min(len(rows) - first, int(4.6 * 30))
    real = os.path.join(OUT, "real")
    os.makedirs(real, exist_ok=True)
    ffmpeg("-i", CAPTURE, "-vf", "select='between(n,{:d},{:d})',setpts=N/30/TB,format=yuvj444p".format(first, first + n_frames - 1),
           "-fps_mode", "passthrough", "-q:v", "2", "-strict", "unofficial", os.path.join(real, "%04d.jpg"))

    values = []
    for k in range(n_frames):
        row = rows[first + k]
        blue = (np.abs(row[:, 0] - 71) < 28) & (np.abs(row[:, 1] - 114) < 28) & (np.abs(row[:, 2] - 179) < 28)
        # The label "Move 1" is drawn over the fill, so take the last blue pixel on the track, not the first gap.
        inside = np.nonzero(blue[TRACK_X0 - 1520:TRACK_X1 - 1520 + 1])[0]
        end = TRACK_X0 + (inside[-1] + 1 if len(inside) else 0)
        values.append(round(float(np.clip((end - TRACK_X0) / (TRACK_X1 - TRACK_X0), 0, 1)), 4))
    info = {"fps": 30, "first_source_frame": first, "flash": [int(flash[0]), last_flash], "row_y": ROW_Y,
            "track": [TRACK_X0, TRACK_X1], "values": values}
    with open(os.path.join(OUT, "real.json"), "w") as fh:
        json.dump(info, fh)
    moved = [i for i, v in enumerate(values) if v > 0.01]
    print("real frames", n_frames, "flash", info["flash"], "slider moves frames",
          moved[0] if moved else None, "to", moved[-1] if moved else None, "max", max(values))


if __name__ == "__main__":
    main()
