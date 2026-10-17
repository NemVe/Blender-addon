"""The timeline of promo v2.3: the beat grid of the plan, the voiceover placed on it, the sound-effect cues.

    python promo/v2/make_timeline.py          writes promo/v2/timeline.json

Every time is in seconds from the start of the film (60 fps, so a frame is 1/60 s).
The beats are the Structure table of promo/v2/PLAN.md (section v2.1), with the
opening of section v2.2 in place of the three hooks. The features share their 33 s
evenly: 2.75 s each. The voice of a beat starts `lead` seconds into it, so the
headline is on screen as the first words are heard; a line that is too long for its
beat starts up to NUDGE s earlier. The line lengths come from audio/vo.json (made by
audio/gen_vo.py and audio/cut_vo.py, which also stretch a line that still does not fit).

The opening has no fixed length. Its first line ("Let's rig this flower from scratch. Clock's running!") comes first and the first click
follows it. From there the walkthrough runs on its own clock, walk_schedule.json (made from web/src/walk_schedule.mjs by
build/walk_schedule_json.mjs, and read by the page too): every other line of the opening is placed at its step (OPEN_LINES), and the beat
ends a moment after the slider's drag and the last line.

Written for the film's builder to read and to change:
  beats    id, name, section, start, end, the voice lines in it
  lines    when each WAV starts and ends, when its speech does, and its words
  wipes    the diagonal stripe wipe at every border between beats, and when its whoosh starts
  ticks    the soft tick of each headline landing (a default 0.3 s into the beat)
  clicks   empty: the film's builder adds {"t", "beat", "what"} for every cursor click as it is fixed
  markers  the beat grid, for the After Effects timeline
"""

import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
AUDIO = os.path.join(HERE, "audio")

FPS = 60
WIPE = 0.35         # the stripe wipe lasts this long, and is centred on the border between two beats
TICK_AT = 0.3       # a headline has landed this long after its beat starts
FEATURE = 2.75      # 33 s for the 12 features: inside the plan's 2.5-3 s each
MIN_TAIL = 0.15     # the voice is done at least this long before its beat ends
NUDGE = 0.3         # a line that does not fit may start this much earlier than its lead says

OPEN_LEAD = 0.35    # the first word of the opening comes this long into it
OPEN_GAP = 0.35     # the first click comes this long after "Clock's running!"
OPEN_APART = 0.12   # a line of the opening starts at least this long after the one before it ended
OPEN_HOLD = 1.0     # the picture stays this long after the slider's drag
OPEN_TAIL = 0.5     # air after the last word of the opening, before the wipe
# The lines of the opening after the first: (id, mark of walk_schedule.json, "start" or "end", offset in seconds). The line's speech
# starts (or ends) at that mark, in seconds after the first click, plus the offset. The marks of the walkthrough are its presses
# ("newmove", "record", "build", ...) and the moments the pointer arrives at a step ("pose_arrive", ...).
OPEN_LINES = (
    ("open_2", "newmove", "end", 0.20),          # "... and hit New Move." ends as the button is pressed
    ("open_3", "makechain", "end", 0.20),        # "Make the leaf a chain." ends on Make Chain
    ("open_4", "pose_arrive", "start", 0.0),     # said as the first part is clicked
    ("open_5", "record", "end", 0.15),           # "Record After." ends on the press
    ("open_6", "ring1_arrive", "start", 0.0),
    ("open_7", "ring2_arrive", "start", 0.0),
    ("open_8", "ring3_arrive", "start", 0.0),
    ("open_9a", "spread_arrive", "start", 0.0),
    ("open_9b", "delays_arrive", "start", -0.2),  # said while the two delays are typed
    ("open_10", "smooth_arrive", "start", 0.05),  # "Smooth" as Smooth is pressed; "... and Build!" then ends on Build Sliders
    ("open_11", "grab", "start", 0.0),           # "One slider, and it blooms." as the slider is dragged
)

# id, name, section, length (s), voice line, seconds from the start of the beat to the first word.
BEATS = (
    ("open", "Opening", "Opening", None, "open_1", OPEN_LEAD),      # its length comes from the walkthrough, see opening()
    ("logo", "Logo", "Logo", 4.0, "logo", 0.35),
    ("idea1", "The idea 1/3", "The idea", 4.0, "idea1", 0.4),
    ("idea2", "The idea 2/3", "The idea", 4.0, "idea2", 0.3),
    ("idea3", "The idea 3/3", "The idea", 4.0, "idea3", 0.3),
) + tuple(
    ("f{:02d}".format(n), "Feature {:02d} {}".format(n, name), "Features", FEATURE, "f{:02d}".format(n), 0.2)
    for n, name in enumerate(("Timing", "Spread", "Pivot", "Steps", "Curves", "Speed", "Chain", "Curl", "Ring",
                              "Mirror", "Combine", "Animate"), 1)
) + (
    ("together", "Put it together", "Put it together", 10.0, "together", 0.6),
    ("real", "Real Blender", "Real Blender", 3.0, "real", 0.3),
    ("end", "End card", "End card", 5.0, "end", 0.3),
)


def put(vo, line_id, beat_id, wav_start):
    """One line of the voice on the film's clock: where its WAV starts, where its speech does, its phrases and words."""
    line = vo["lines"][line_id]
    at = lambda x: round(wav_start + x, 3)
    return {"beat": beat_id, "file": "audio/" + line["file"], "text": line["text"],
            "start": at(0.0), "end": at(line["duration"]),
            "speech_start": at(line["phrases"][0]["start"]), "speech_end": at(line["phrases"][-1]["end"]),
            "duration": line["duration"],
            "phrases": [{"text": p["text"], "start": at(p["start"]), "end": at(p["end"])} for p in line["phrases"]],
            "words": [{"w": w["w"], "start": at(w["start"]), "end": at(w["end"])} for w in line["words"]]}


def opening(vo, sched):
    """The opening's own clock (seconds from its start): where each line goes, when the first click is, and how long it lasts."""
    marks = sched["marks"]
    first = vo["lines"]["open_1"]
    speech = lambda line: (line["phrases"][0]["start"], line["phrases"][-1]["end"])      # noqa: E731
    s0, s1 = speech(first)
    wavs = {"open_1": OPEN_LEAD - s0}
    go = OPEN_LEAD + (s1 - s0) + OPEN_GAP                                              # the first click
    prev_end = OPEN_LEAD + (s1 - s0)
    for line_id, mark, edge, offset in OPEN_LINES:
        a, b = speech(vo["lines"][line_id])
        at = go + marks[mark] + offset
        begin = at if edge == "start" else at - (b - a)
        if begin < prev_end + OPEN_APART:                                              # a line never talks over the one before it
            print("  note: {} is moved {:.2f} s later, after the line before it".format(line_id, prev_end + OPEN_APART - begin))
            begin = prev_end + OPEN_APART
        wavs[line_id] = begin - a
        prev_end = begin + (b - a)
    length = max(go + sched["end"] + OPEN_HOLD, prev_end + OPEN_TAIL)
    return math.ceil(length * FPS - 1e-6) / FPS, wavs, go        # whole frames, so the beats after it stay on theirs


def main():
    with open(os.path.join(AUDIO, "vo.json"), encoding="utf-8") as fh:
        vo = json.load(fh)
    with open(os.path.join(AUDIO, "sfx.json"), encoding="utf-8") as fh:
        sfx = json.load(fh)["effects"]
    with open(os.path.join(HERE, "walk_schedule.json"), encoding="utf-8") as fh:
        sched = json.load(fh)
    hit = sfx["whoosh"]["marks"]["hit"]     # the whoosh is loudest this far into its file

    beats, lines, wipes, ticks, markers = [], {}, [], [], []
    t = 0.0
    for i, (bid, name, section, length, line_id, lead) in enumerate(BEATS):
        start = t
        beat = {"id": bid, "name": name, "section": section}
        if bid == "open":
            length, wavs, go = opening(vo, sched)
            ids = ["open_1"] + [x[0] for x in OPEN_LINES]
            for lid in ids:
                lines[lid] = put(vo, lid, bid, start + wavs[lid])
            beat.update({"lines": ids, "steps": {"go": round(go, 3)}})          # relative to the beat, for the page
        else:
            line = vo["lines"][line_id]
            first, last = line["phrases"][0]["start"], line["phrases"][-1]["end"]   # the WAV has a little silence round the speech
            wav_start = start + lead - first
            over = wav_start + last - (start + length - MIN_TAIL)
            if over > 0:                                                      # a line that is long for its beat starts a little earlier
                wav_start -= min(over, NUDGE, lead)
            if wav_start + last > start + length - MIN_TAIL:
                raise SystemExit("{}: the voice runs to {:.2f} s, the beat ends at {:.2f} s".format(bid, wav_start + last, start + length))
            lines[line_id] = put(vo, line_id, bid, wav_start)
            beat["lines"] = [line_id]
        end = start + length
        beat.update({"start": round(start, 3), "end": round(end, 3)})
        beats.append(beat)
        ticks.append({"t": round(start + TICK_AT, 3), "beat": bid})
        markers.append({"t": round(start, 3), "name": name})
        if i:
            wipes.append({"t": round(start, 3), "start": round(start - WIPE / 2, 3), "end": round(start + WIPE / 2, 3),
                          "whoosh": round(start - hit, 3), "from": BEATS[i - 1][0], "to": bid})
        t = end

    data = {
        "version": "2.3", "fps": FPS, "width": 2560, "height": 1440, "duration": round(t, 3),
        "voice": {k: vo[k] for k in ("engine", "voice", "settings", "lufs_per_line", "total", "sample_rate") if k in vo},
        "defaults": {"wipe_length": WIPE, "tick_after_beat_start": TICK_AT, "feature_beat": FEATURE,
                     "whoosh_loudest_at": hit, "min_tail_after_voice": MIN_TAIL},
        "sfx_files": {k: "audio/" + v["file"] for k, v in sfx.items()},
        "beats": beats, "lines": lines, "wipes": wipes, "ticks": ticks,
        "clicks": [],
        "markers": markers,
    }
    out = os.path.join(HERE, "timeline.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=1, ensure_ascii=False)
        fh.write("\n")

    print("{:9s} {:>6s} {:>6s}   {:>11s}   {:>5s}".format("beat", "start", "end", "speech", "tail"))
    for b in beats:
        ln = lines[b["lines"][-1]]
        print("{:9s} {:6.2f} {:6.2f}   {:5.2f}-{:5.2f}   {:5.2f}".format(
            b["id"], b["start"], b["end"], lines[b["lines"][0]]["speech_start"], ln["speech_end"], b["end"] - ln["speech_end"]))
    print("film {:.2f} s, {:d} beats, {:d} wipes".format(t, len(beats), len(wipes)))
    print("run `node promo/v2/build/render.js cues` next: it writes the clicks and pops the beats declare into timeline.json")


if __name__ == "__main__":
    main()
