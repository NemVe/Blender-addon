"""The edit list of the promo: every cut, speed, caption and marker, as plain data.

    python promo/edit/edit_list.py            (from the repository root, or anywhere)

It reads the timeline JSON of the two recordings, looks at the recordings
themselves, counts the frames of the Cycles footage, and writes
`promo/edit/edit_list.jsxinc`, which `build_promo.jsx` includes. ExtendScript
has no JSON and the timing is easier to get right here, so the project is
built from this file and nothing in it is timed by hand.

What it looks at in a recording (the capture of Blender's window):
  * the sync flash: the first frame that is nearly white. The timeline's times
    are seconds after it;
  * how much of the picture changes from frame to frame, in three places (the
    3D view, the CopyThat sidebar, the Outliner and Properties): a change is
    action, no change is a pause;
  * the Ring and Spread dialogs: each has a blue OK button, so a dialog is on
    screen while that blue is there.

How shot 6 (the demo) is cut from that, beat by beat:
  * a dialog is never touched: it stays at 1x, as long as it was up;
  * a pause that was long enough to read something (the panel's report after a
    button) keeps HOLD frames at 1x, and the rest of it is cut;
  * a shorter pause keeps PAUSE frames; the frame of a click or a press that
    began it stays;
  * everything that moves (the view turning, a part gliding, the slider)
    plays at SPEED, never more than 1.5x;
  * HOLD is the longest that makes the shot exactly 42 s (1260 frames), and
    the few frames left over go to the last hold.

Needs ffmpeg and numpy. The recording's capture (`capture.mkv`) is looked at
when it is there (it decodes faster); the ProRes file otherwise.
"""

import argparse
import json
import os
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
FPS = 30

# The storyboard's shots on its 0.5 s grid: (number, name, start s, length s)
SHOTS = (
    (1, "01 Bloom", 0.0, 1.5),
    (2, "02 Turn", 1.5, 1.5),
    (3, "03 Push-in", 3.0, 1.5),
    (4, "04 Slider", 4.5, 3.5),
    (5, "05 Title", 8.0, 2.0),
    (6, "06 Demo", 10.0, 42.0),
    (7, "07 Match cut", 52.0, 5.0),
    (8, "08 End card", 57.0, 4.0),
)

# How shot 6 is cut (frames at 30 fps unless it says seconds)
SPEED = 1.5               # at most: what moves plays this fast
PAUSE = 6                 # frames kept of a short pause
HOLD_MIN, HOLD_MAX = 30, 60   # frames kept of a long pause, searched for the fit
LONG_PAUSE = 30           # a pause this long (frames) is a report being read, or a wait before a press
WAIT = 15                 # frames kept of a wait before a press
STRONG = 3.0              # a change this big (the mean change of a region, in levels) is a press, not a click
EVENT = 3                 # a change this short (frames) is a click or a press, not motion
GAP = 2                   # a gap this short (frames) inside motion is a repeated frame of the capture
THRESHOLD = 0.006         # mean change per frame, in levels of 255, that counts as motion
LT_MIN, LT_MAX = 60, 120  # a lower third lasts 2 to 4 s
LT_GAP = 3                # and ends this many frames before the beat does
SLIDER_TAIL = 4           # frames kept after the slider reaches 100%

# The three hook lines (shots 1 to 3) and where each stands in the picture: y is the line's centre in a
# 1080-high frame (the cards' ?y=), chosen from the dark part of each shot, off the flower
STATEMENTS = (
    {"text": "21 moving parts.", "y": 170},
    {"text": "No rig to build.", "y": 170},
    {"text": "One slider.", "y": 770},
)

# Where things are in the 2560x1440 capture (x, y, width, height)
REGIONS = {"view": (0, 100, 1500, 1250), "side": (1530, 90, 560, 1250), "right": (2110, 60, 450, 1300)}
DIALOG_BOX = (1000, 100, 600, 560)        # where the Ring and Spread dialogs open
BLUE = (71, 114, 179)                     # Blender's selected-button blue: the dialogs' OK button
BLUE_PIXELS = 600                         # in the box at half size, more than this is a dialog


def say(*parts):
    print(" ".join(str(p) for p in parts))
    sys.stdout.flush()


def ffmpeg_frames(path, vf, width, height, channels, frames):
    """The first `frames` frames of a video as numpy arrays, one at a time."""
    command = ["ffmpeg", "-v", "error", "-i", path, "-frames:v", str(frames), "-vf", vf,
               "-f", "rawvideo", "-pix_fmt", "gray" if channels == 1 else "rgb24", "-"]
    size = width * height * channels
    process = subprocess.Popen(command, stdout=subprocess.PIPE)
    try:
        while True:
            buffer = process.stdout.read(size)
            if len(buffer) < size:
                break
            yield np.frombuffer(buffer, dtype=np.uint8).reshape(
                (height, width) if channels == 1 else (height, width, channels))
    finally:
        process.stdout.close()
        process.wait()


def analyse(path, frames):
    """(flash frame, activity per frame, dialog on screen per frame) of a recording."""
    width, height = 480, 270
    scale = width / 2560.0
    boxes = {}
    for name, (x, y, w, h) in REGIONS.items():
        boxes[name] = (int(x * scale), int(y * scale), max(1, int(w * scale)), max(1, int(h * scale)))
    flash = None
    activity = np.zeros(frames)
    previous = None
    count = 0
    for index, frame in enumerate(ffmpeg_frames(
            path, "scale={:d}:{:d}:flags=area,format=gray".format(width, height), width, height, 1, frames)):
        count += 1
        if flash is None and index < FPS * 30 and frame.mean() > 200:
            flash = index
        current = frame.astype(np.float32)
        if previous is not None:
            levels = []
            for x, y, w, h in boxes.values():
                levels.append(np.abs(current[y:y + h, x:x + w] - previous[y:y + h, x:x + w]).mean())
            activity[index] = max(levels)
        previous = current
    activity = activity[:count]

    # the dialogs: the blue OK button in the box where they open
    x, y, w, h = DIALOG_BOX
    small_w, small_h = w // 2, h // 2
    blue = np.array(BLUE)
    dialog = np.zeros(count, dtype=bool)
    vf = "crop={:d}:{:d}:{:d}:{:d},scale={:d}:{:d}:flags=area".format(w, h, x, y, small_w, small_h)
    for index, frame in enumerate(ffmpeg_frames(path, vf, small_w, small_h, 3, count)):
        near = np.abs(frame.astype(np.int32) - blue).max(axis=2) <= 8
        dialog[index] = near.sum() > BLUE_PIXELS
    return flash, activity, dialog


def runs_of(flags):
    """[(start, end, value)] of equal values in a list."""
    out = []
    start = 0
    for index in range(1, len(flags) + 1):
        if index == len(flags) or flags[index] != flags[start]:
            out.append((start, index, flags[start]))
            start = index
    return out


def cut_beat(first, last, activity, dialog, hold):
    """The segments of one beat, file frames [first, last): a list of
    [source start, source frames, speed, kind], kind D (a dialog), M (motion),
    or P (a pause)."""
    flags = []
    for frame in range(first, last):
        if dialog[frame]:
            flags.append("D")
        elif activity[frame] > THRESHOLD:
            flags.append("M")
        else:
            flags.append("P")
    # the capture repeats a frame now and then while the picture moves: a gap of a frame
    # or two inside motion is not a pause
    for start, end, kind in runs_of(flags):
        if kind == "P" and end - start <= GAP and 0 < start and end < len(flags)                 and flags[start - 1] == "M" and flags[end] == "M":
            for frame in range(start, end):
                flags[frame] = "M"
    runs = [list(r) for r in runs_of(flags)]
    # a click or a press is a change of a frame or two between pauses: it joins the
    # pause that follows it, which is what it started
    merged = []
    index = 0
    while index < len(runs):
        start, end, kind = runs[index][0], runs[index][1], runs[index][2]
        if kind == "M" and end - start <= EVENT and index + 1 < len(runs) and runs[index + 1][2] == "P"                 and (not merged or merged[-1][2] in ("P", "D")):
            runs[index + 1][0] = start
            runs[index + 1].append("event")
        else:
            merged.append(runs[index])
        index += 1

    def peak(a, b):
        a, b = max(0, a), min(len(activity), b)
        return float(activity[a:b].max()) if b > a else 0.0

    segments = []
    previous = None
    for number, run in enumerate(merged):
        start, end, kind = run[0] + first, run[1] + first, run[2]
        length = end - start
        event = len(run) > 3
        if kind == "D":
            segments.append([start, length, 1.0, "D"])
        elif kind == "M":
            segments.append([start, length, SPEED, "M"])
        elif length >= LONG_PAUSE:
            # A long pause is either something being read (the panel's report after a button, a dialog's
            # result, what a scroll brought up), which keeps HOLD frames, or only a wait before the next
            # press, which keeps WAIT. What was pressed last makes the difference: a pause that follows a
            # dialog, a strong change of the panel or the end of the beat is read; a pause that follows
            # nothing but small changes and ends in a strong one is a wait.
            is_last = number == len(merged) - 1
            lead = peak(start, start + EVENT + 1)
            following = peak(end, end + 2)
            wait = following >= STRONG and lead < STRONG and not is_last and previous != "D"
            segments.append([start, min(length, WAIT if wait else hold), 1.0, "P"])
        else:
            segments.append([start, min(length, PAUSE + (EVENT if event else 0)), 1.0, "P"])
        previous = kind
    # a frame or two of pause in front of motion is part of the motion; neighbours of one kind and
    # speed are one segment
    joined = []
    for segment in segments:
        if joined and joined[-1][3] == "P" and joined[-1][1] <= GAP and segment[3] == "M"                 and joined[-1][0] + joined[-1][1] == segment[0]:
            segment = [joined[-1][0], joined[-1][1] + segment[1], SPEED, "M"]
            joined.pop()
        if joined and joined[-1][3] == segment[3] and joined[-1][2] == segment[2]                 and joined[-1][0] + joined[-1][1] == segment[0]:
            joined[-1][1] += segment[1]
        else:
            joined.append(segment)
    return joined


def out_frames(segment):
    """Frames a segment takes in the film: a moving one plays at SPEED at most."""
    return int(np.ceil(segment[1] / segment[2] - 1e-9))


def plan_demo(timeline, flash, activity, dialog, target):
    beats = timeline["beats"]
    spans = []
    for beat in beats:
        spans.append((flash + int(round(beat["start"] * FPS)), flash + int(round(beat["end"] * FPS))))

    def build(hold):
        return [cut_beat(first, last, activity, dialog, hold) for first, last in spans]

    chosen = None
    for hold in range(HOLD_MAX, HOLD_MIN - 1, -1):
        plan = build(hold)
        total = sum(out_frames(s) for beat in plan for s in beat)
        if total <= target:
            chosen = (hold, plan, total)
            break
    if chosen is None:
        raise SystemExit("the demo does not fit {:d} frames even with holds of {:d}".format(target, HOLD_MIN))
    hold, plan, total = chosen
    # the frames left over make the last hold longer (or, if the beat has no hold, the last segment)
    spare = target - total
    last = plan[-1][-1]
    if last[3] == "P":
        last[1] += spare
    else:
        last[1] += spare * int(last[2])
    say("shot 6: hold {:d} frames, {:d} frames added to the last segment, {:.2f} s".format(
        hold, spare, target / float(FPS)))
    return hold, plan


def count_frames(folder, prefix):
    names = sorted(n for n in os.listdir(folder) if n.startswith(prefix) and n.endswith(".png"))
    return names[0], names[-1], len(names)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--promo", default=os.path.join(ROOT, "dist", "promo"), help="the folder with the footage")
    parser.add_argument("--out", default=os.path.join(HERE, "edit_list.jsxinc"))
    args = parser.parse_args()
    promo = args.promo

    data = {"fps": FPS, "shots": [], "markers": []}
    for number, name, start, length in SHOTS:
        data["shots"].append({"n": number, "name": name, "start": int(round(start * FPS)),
                              "frames": int(round(length * FPS))})
    data["frames"] = sum(s["frames"] for s in data["shots"])

    # --- the hooks, the outro and the bloom: only how many frames each has
    hooks = {}
    for letter in "ABC":
        first, last, count = count_frames(os.path.join(promo, "hooks_1440", "hook_" + letter), "hook_" + letter + "_")
        hooks[letter] = {"folder": "hooks_1440/hook_" + letter, "first": first, "last": last, "frames": count}
    data["hooks"] = hooks
    data["statements"] = list(STATEMENTS)
    first, last, count = count_frames(os.path.join(promo, "outro_frames_1440"), "outro_")
    data["outro"] = {"folder": "outro_frames_1440", "first": first, "last": last, "frames": count}
    first, last, count = count_frames(os.path.join(promo, "viewport_bloom"), "bloom_")
    data["bloom"] = {"folder": "viewport_bloom", "first": first, "last": last, "frames": count}
    # Shot 7: the viewport bloom, and the render dissolving in over a second a little way in
    data["match_cut"] = {"dissolve_start": 45, "dissolve_frames": 30, "tag_start": 72}

    # --- the slider (shot 4)
    slider_dir = os.path.join(promo, "rec", "slider")
    slider_file = pick_recording(slider_dir, "CopyThat_rec_slider")
    slider_timeline = json.load(open(os.path.join(slider_dir, "timeline.json")))
    say("slider: reading", os.path.basename(slider_file))
    flash, _activity, _dialog = analyse(analysis_source(slider_dir, slider_file), FPS * 30)
    beat = slider_timeline["beats"][0]
    start = flash + int(round(beat["start"] * FPS))
    length = data["shots"][3]["frames"]
    # The whole slider move fits the shot: it is 4 s long and the shot 3.5 s, so it plays a little
    # faster (a few frames after the end keep the open flower on screen for a moment).
    src_frames = int(round((beat["end"] - beat["start"]) * FPS)) + SLIDER_TAIL
    data["slider"] = {"file": "rec/slider/" + os.path.basename(slider_file), "flash": flash, "start": start,
                      "frames": length, "src_frames": src_frames, "caption": beat["caption"],
                      "move_ends": beat["end"]}
    say("slider: flash at frame {:d} ({:.3f} s), the move from frame {:d}, {:d} frames into {:d} ({:.2f}x)".format(
        flash, flash / float(FPS), start, src_frames, length, src_frames / float(length)))

    # --- the demo (shot 6)
    main_dir = os.path.join(promo, "rec", "main")
    main_file = pick_recording(main_dir, "CopyThat_rec_main")
    timeline = json.load(open(os.path.join(main_dir, "timeline.json")))
    last_end = max(b["end"] for b in timeline["beats"])
    say("demo: reading", os.path.basename(main_file), "(this takes a minute)")
    needed = int((last_end + 15) * FPS) + 10 * FPS
    flash, activity, dialog = analyse(analysis_source(main_dir, main_file), needed)
    say("demo: flash at frame {:d} ({:.3f} s)".format(flash, flash / float(FPS)))
    target = data["shots"][5]["frames"]
    hold, plan = plan_demo(timeline, flash, activity, dialog, target)

    segments = []
    beats = []
    position = 0
    for number, (beat, beat_segments) in enumerate(zip(timeline["beats"], plan)):
        beat_start = position
        for source, frames, speed, kind in beat_segments:
            taken = int(np.ceil(frames / speed - 1e-9))
            segments.append({"beat": number, "kind": kind, "src": int(source), "src_frames": int(frames),
                             "start": position, "frames": taken})
            position += taken
        length = position - beat_start
        lt = max(min(length - LT_GAP, LT_MAX), min(LT_MIN, length))
        beats.append({"name": beat["name"], "caption": beat["caption"], "start": beat_start, "frames": length,
                      "lt_frames": lt})
        data["markers"].append({"frame": data["shots"][5]["start"] + beat_start,
                                "comment": "Beat {:d}: {:s} - {:s}".format(number + 1, beat["name"], beat["caption"])})
    assert position == target, (position, target)
    data["demo"] = {"file": "rec/main/" + os.path.basename(main_file), "flash": flash, "frames": position,
                    "hold": hold, "segments": segments, "beats": beats}

    # a marker at every shot too, for laying music on the grid
    for shot in data["shots"]:
        data["markers"].append({"frame": shot["start"], "comment": "Shot {:s}".format(shot["name"])})
    data["markers"].sort(key=lambda m: (m["frame"], m["comment"]))

    # --- a readable summary, and the include
    say("")
    say("shot 6, beat by beat (film frames in shot 6; source = frames of the recording after the flash):")
    for number, beat in enumerate(beats):
        said = [s for s in segments if s["beat"] == number]
        kinds = {"D": "dialog", "M": "moves", "P": "pause"}
        say("  {:d} {:16s} {:5.2f} s  lower third {:4.2f} s  | {:s}".format(
            number + 1, beat["name"], beat["frames"] / float(FPS), beat["lt_frames"] / float(FPS), beat["caption"]))
        for s in said:
            say("       {:6s} source {:6.2f}-{:6.2f} s ({:3d} frames) -> {:3d} frames, {:.2f}x".format(
                kinds[s["kind"]], (s["src"] - flash) / float(FPS), (s["src"] + s["src_frames"] - flash) / float(FPS),
                s["src_frames"], s["frames"], s["src_frames"] / float(s["frames"])))
    dialogs = [s for s in segments if s["kind"] == "D"]
    say("dialogs kept at 1x:", ", ".join("{:.2f} s".format(s["frames"] / float(FPS)) for s in dialogs))

    with open(args.out, "w", encoding="utf-8") as handle:
        handle.write("// Written by edit_list.py: the cuts, speeds, captions and markers of the promo. Do not edit;\n"
                     "// change edit_list.py and run it again. Frames are 30 fps; \"src\" is a frame of the recording's\n"
                     "// file, \"start\" a frame of the shot (or the film).\n")
        handle.write("var EDIT = ")
        handle.write(json.dumps(data, indent=1, sort_keys=True))
        handle.write(";\n")
    say("wrote", args.out)


def pick_recording(folder, stem):
    """The recording to build from: the BT.709 ProRes if it is there (the capture's colour matrix is BT.601,
    which the corrected file has converted), else the plain one."""
    for name in (stem + "_709.mov", stem + ".mov"):
        if os.path.isfile(os.path.join(folder, name)):
            return os.path.join(folder, name)
    raise SystemExit("no ProRes recording of {:s} in {:s}".format(stem, folder))


def analysis_source(folder, prores):
    capture = os.path.join(folder, "capture.mkv")
    return capture if os.path.isfile(capture) else prores


if __name__ == "__main__":
    main()
