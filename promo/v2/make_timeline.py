"""The timeline of promo v2.1: the beat grid of the plan, the voiceover placed on it, the sound-effect cues.

    python promo/v2/make_timeline.py          writes promo/v2/timeline.json

Every time is in seconds from the start of the film (60 fps, so a frame is 1/60 s).
The beats are the Structure table of promo/v2/PLAN.md (section v2.1), 76 s. The
features share their 33 s evenly: 2.75 s each. The voice of a beat starts `lead`
seconds into it, so the headline is on screen as the first words are heard; the
line lengths come from audio/vo.json (made by audio/make_vo.py and align_vo.py).

Written for the film's builder to read and to change:
  beats    id, name, section, start, end, the voice lines in it
  lines    when each WAV starts and ends, when its speech does, and its words
  wipes    the diagonal stripe wipe at every border between beats, and when its whoosh starts
  ticks    the soft tick of each headline landing (a default 0.3 s into the beat)
  clicks   empty: the film's builder adds {"t", "beat", "what"} for every cursor click as it is fixed
  markers  the beat grid, for the After Effects timeline
"""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
AUDIO = os.path.join(HERE, "audio")

FPS = 60
WIPE = 0.35         # the stripe wipe lasts this long, and is centred on the border between two beats
TICK_AT = 0.3       # a headline has landed this long after its beat starts
FEATURE = 2.75      # 33 s for the 12 features: inside the plan's 2.5-3 s each
MIN_TAIL = 0.15     # the voice is done at least this long before its beat ends

# id, name, section, length (s), voice line, seconds from the start of the beat to the first word.
BEATS = (
    ("hook1", "Hook 1", "Hook", 3.0, "hook1", 0.4),
    ("hook2", "Hook 2", "Hook", 3.0, "hook2", 0.25),
    ("hook3", "Hook 3", "Hook", 3.0, "hook3", 0.3),
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


def main():
    with open(os.path.join(AUDIO, "vo.json"), encoding="utf-8") as fh:
        vo = json.load(fh)
    with open(os.path.join(AUDIO, "sfx.json"), encoding="utf-8") as fh:
        sfx = json.load(fh)["effects"]
    hit = sfx["whoosh"]["marks"]["hit"]     # the whoosh is loudest this far into its file

    beats, lines, wipes, ticks, markers = [], {}, [], [], []
    t = 0.0
    for i, (bid, name, section, length, line_id, lead) in enumerate(BEATS):
        start, end = t, t + length
        line = vo["lines"][line_id]
        first = line["phrases"][0]["start"]     # the WAV has a little silence before the speech
        wav_start = start + lead - first
        words = [{"w": w["w"], "start": round(wav_start + w["start"], 3), "end": round(wav_start + w["end"], 3)}
                 for w in line["words"]]
        speech_end = wav_start + line["phrases"][-1]["end"]
        if speech_end > end - MIN_TAIL:
            raise SystemExit("{}: the voice runs to {:.2f} s, the beat ends at {:.2f} s".format(bid, speech_end, end))
        beats.append({"id": bid, "name": name, "section": section, "start": round(start, 3), "end": round(end, 3),
                      "lines": [line_id]})
        lines[line_id] = {"beat": bid, "file": "audio/" + line["file"], "text": line["text"],
                          "start": round(wav_start, 3), "end": round(wav_start + line["duration"], 3),
                          "speech_start": round(start + lead, 3), "speech_end": round(speech_end, 3),
                          "duration": line["duration"],
                          "phrases": [{"text": p["text"], "start": round(wav_start + p["start"], 3),
                                       "end": round(wav_start + p["end"], 3)} for p in line["phrases"]],
                          "words": words}
        ticks.append({"t": round(start + TICK_AT, 3), "beat": bid})
        markers.append({"t": round(start, 3), "name": name})
        if i:
            wipes.append({"t": round(start, 3), "start": round(start - WIPE / 2, 3), "end": round(start + WIPE / 2, 3),
                          "whoosh": round(start - hit, 3), "from": BEATS[i - 1][0], "to": bid})
        t = end

    data = {
        "version": "2.1", "fps": FPS, "width": 2560, "height": 1440, "duration": round(t, 3),
        "voice": {"engine": vo["engine"], "voice": vo["voice"], "speed": vo["speed"], "lufs_per_line": vo["lufs_per_line"],
                  "total": vo["total"], "sample_rate": vo["sample_rate"]},
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
        ln = lines[b["lines"][0]]
        print("{:9s} {:6.2f} {:6.2f}   {:5.2f}-{:5.2f}   {:5.2f}".format(
            b["id"], b["start"], b["end"], ln["speech_start"], ln["speech_end"], b["end"] - ln["speech_end"]))
    print("film {:.2f} s, {:d} beats, {:d} wipes".format(t, len(beats), len(wipes)))


if __name__ == "__main__":
    main()
