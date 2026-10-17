"""The timeline of promo v2.2: the beat grid of the plan, the voiceover placed on it, the sound-effect cues.

    python promo/v2/make_timeline.py          writes promo/v2/timeline.json

Every time is in seconds from the start of the film (60 fps, so a frame is 1/60 s).
The beats are the Structure table of promo/v2/PLAN.md (section v2.1), with the
opening of section v2.2 in place of the three hooks. The features share their 33 s
evenly: 2.75 s each. The voice of a beat starts `lead` seconds into it, so the
headline is on screen as the first words are heard; a line that is too long for its
beat starts up to NUDGE s earlier. The line lengths come from audio/vo.json (made by
audio/gen_vo.py and audio/cut_vo.py, which also stretch a line that still does not fit).

The opening has no fixed length. Its first line ("Let's rig this flower in twelve
clicks. Watch this!") comes first, the cursor's clicks follow it (the schedule OPEN_STEPS,
read by web/src/beats_open.mjs from timeline.json), and its second line ("Done! One
slider, and it blooms.") lands on the last click. The beat ends a moment after that.

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
OPEN_GAP = 0.12     # the first click comes this long after "Watch this!"
OPEN_DONE = 0.1     # "Done!" starts this long after the last click
OPEN_TAIL = 0.5     # air after the last word of the opening, before the wipe
OPEN_DRAG = 1.8     # the slider drag of the last click (DRAG in web/src/beats_open.mjs)
# The cursor's clicks of the opening, in seconds after the first one. The twelve counted ones are new .. build; "pose" is the
# first of four quick drags (a drag every 0.25 s) that are shown and not counted; "drag" is the slider, once the flower is built.
OPEN_STEPS = (("new", 0.0), ("chain", 0.42), ("pose", 0.84), ("rec", 1.95), ("r1", 2.35), ("o1", 2.78), ("r2", 3.15), ("o2", 3.58),
              ("r3", 3.95), ("o3", 4.38), ("sp", 4.75), ("o4", 5.18), ("build", 5.6), ("drag", 5.95))

# id, name, section, length (s), voice line, seconds from the start of the beat to the first word.
BEATS = (
    ("open", "Opening", "Opening", None, "open_a", OPEN_LEAD),      # its length comes from the voice, see opening()
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


def opening(vo):
    """The opening's own clock (seconds from its start): where its two lines go, the cursor's schedule, and how long it lasts."""
    a, b = vo["lines"]["open_a"], vo["lines"]["open_b"]
    a_wav = OPEN_LEAD - a["phrases"][0]["start"]
    go = a_wav + a["phrases"][-1]["end"] + OPEN_GAP
    steps = {k: round(go + dt, 3) for k, dt in OPEN_STEPS}
    b_wav = steps["build"] + OPEN_DONE - b["phrases"][0]["start"]               # "Done!" lands on the last click
    length = max(steps["drag"] + OPEN_DRAG + 0.45, b_wav + b["phrases"][-1]["end"] + OPEN_TAIL)
    return math.ceil(length * FPS - 1e-6) / FPS, a_wav, b_wav, steps           # whole frames, so the beats after it stay on theirs


def main():
    with open(os.path.join(AUDIO, "vo.json"), encoding="utf-8") as fh:
        vo = json.load(fh)
    with open(os.path.join(AUDIO, "sfx.json"), encoding="utf-8") as fh:
        sfx = json.load(fh)["effects"]
    hit = sfx["whoosh"]["marks"]["hit"]     # the whoosh is loudest this far into its file

    beats, lines, wipes, ticks, markers = [], {}, [], [], []
    t = 0.0
    for i, (bid, name, section, length, line_id, lead) in enumerate(BEATS):
        start = t
        beat = {"id": bid, "name": name, "section": section}
        if bid == "open":
            length, a_wav, b_wav, steps = opening(vo)
            lines["open_a"] = put(vo, "open_a", bid, start + a_wav)
            lines["open_b"] = put(vo, "open_b", bid, start + b_wav)
            beat.update({"lines": ["open_a", "open_b"], "steps": steps})      # relative to the beat, for the page
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
        "version": "2.2", "fps": FPS, "width": 2560, "height": 1440, "duration": round(t, 3),
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
