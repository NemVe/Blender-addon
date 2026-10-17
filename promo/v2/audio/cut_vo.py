"""Cut the takes of Chatterbox into the lines of promo v2.3, and write vo.json.

    python cut_vo.py --takes <folder of gen_vo.py's takes> [--model small.en] [--cache <folder for the Whisper model>] [--only open]

Run it where kokoro-onnx (make_vo.py's audio helpers need it), faster-whisper, soundfile, scipy and pyloudnorm are installed.
For each passage of vo_script.py:
  1. Every take gets light compression and a little presence as a whole (a high-pass, a gentle lift near 3 kHz, a 1.6:1
     compressor), so every line of it is treated alike, and is cut where one line ends and the next begins, at the quietest
     moment between their last and first words.
  2. Whisper listens to the finished lines of every take one by one, as a listener who has not heard the sentences round them
     would. The take with the fewest words wrong wins; among equals, the liveliest pitch (gen_vo.py measured it) that is not much
     slower than the fastest.
  3. Each line of it is sped up (by at most 8%) if it is too long for its beat, brought to about -16 LUFS and limited, and
     written as <line>.wav (48 kHz, mono) next to this script.
vo.json gets the words and phrases of every line, in seconds from the start of its WAV: what make_timeline.py reads.
With --only <passage ids> only those passages are cut, and every other line of vo.json (and its WAV) is kept as it was: v2.3 re-spoke
the opening alone, and the lines from the logo on are v2.2's.
At the end Whisper listens to the finished WAVs and says whether each one still says what the script says.
"""

import argparse
import difflib
import glob
import json
import os
import re
import subprocess
import sys
import tempfile

import numpy as np
import pyloudnorm
import soundfile
from faster_whisper import WhisperModel
from scipy.signal import butter, lfilter, resample_poly, sosfilt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import make_timeline  # noqa: E402  (the beat grid: how long a line may be)
import make_vo  # noqa: E402  (its audio helpers: levels, fades, the limiter)
from vo_script import PASSAGES, SETTINGS  # noqa: E402

RATE = make_vo.RATE
LUFS = -16.0            # the voice before the mix; the film's mixer lifts it to about -14 LUFS with the effects
MAX_STRETCH = 0.08      # a line is sped up by this much at the most
make_vo.LUFS = LUFS
make_vo.MAX_DIP = 6.0   # make_vo's 2.5 dB would pull a line with tall consonants below -16 LUFS (f04 was -20): the lines are compressed first,
                        # and a dip of a few ms on a plosive is not heard, but a line 4 dB quieter than the next one is


def tokens(text):
    """The words of a text, as Whisper and the script both spell them: 'Copy That' and 'CopyThat', '21' and 'twenty-one' alike."""
    text = text.lower().replace("copythat", "copy that").replace("superhive", "super hive").replace("-", " ")
    text = re.sub(r"\b\d+\b", lambda m: {"12": "twelve", "21": "twenty one"}.get(m.group(), m.group()), text)
    return re.findall(r"[a-z']+", text)


def hear(model, x):
    """The words Whisper finds in x (48 kHz), one entry per token, with times in seconds."""
    y = resample_poly(x, 1, RATE // 16000).astype("float32")
    segments, _info = model.transcribe(y, language="en", word_timestamps=True, beam_size=5,
                                       condition_on_previous_text=False, vad_filter=False)
    out = []
    for seg in segments:
        for w in seg.words:
            toks = tokens(w.word)
            for k, t in enumerate(toks):                       # a word of several tokens shares its time
                out.append({"w": t, "start": w.start + (w.end - w.start) * k / len(toks),
                            "end": w.start + (w.end - w.start) * (k + 1) / len(toks)})
    return out


def align(script, heard):
    """The time of every script token, and how many tokens were heard wrong (replaced, missed or added)."""
    if not heard:
        return [(0.0, 0.0)] * len(script), len(script)
    sm = difflib.SequenceMatcher(None, script, [h["w"] for h in heard], autojunk=False)
    at, bad = [None] * len(script), 0
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                at[i1 + k] = (heard[j1 + k]["start"], heard[j1 + k]["end"])
            continue
        bad += max(i2 - i1, j2 - j1)
        for k in range(i2 - i1):
            if j2 > j1:                                        # a wrong stretch: its script words share the time of what was heard
                a, b = heard[j1]["start"], heard[j2 - 1]["end"]
                at[i1 + k] = (a + (b - a) * k / (i2 - i1), a + (b - a) * (k + 1) / (i2 - i1))
            else:                                              # nothing was heard there: a moment at the border
                edge = heard[j1 - 1]["end"] if j1 else heard[0]["start"]
                at[i1 + k] = (edge, edge)
    return at, bad


def peaking(x, f0, gain_db, q):
    """A bell filter (RBJ cookbook)."""
    a_ = 10.0 ** (gain_db / 40.0)
    w0 = 2.0 * np.pi * f0 / RATE
    alpha = np.sin(w0) / (2.0 * q)
    b = np.array([1 + alpha * a_, -2 * np.cos(w0), 1 - alpha * a_])
    a = np.array([1 + alpha / a_, -2 * np.cos(w0), 1 - alpha / a_])
    return lfilter(b / a[0], a / a[0], x)


def compress(x, threshold_db, ratio, attack, release):
    """A feed-forward compressor on the peak of every millisecond: the gain goes down fast and comes back slowly."""
    hop = RATE // 1000
    n = len(x) // hop
    level = 20.0 * np.log10(np.maximum(np.abs(x[: n * hop]).reshape(n, hop).max(axis=1), 1e-6))
    want = -np.maximum(level - threshold_db, 0.0) * (1.0 - 1.0 / ratio)
    ka, kr = np.exp(-1.0 / (attack * 1000.0)), np.exp(-1.0 / (release * 1000.0))
    gain, cur = np.empty(n), 0.0
    for i in range(n):
        k = ka if want[i] < cur else kr
        cur = want[i] + (cur - want[i]) * k
        gain[i] = cur
    return x * 10.0 ** (np.interp(np.arange(len(x)) / hop, np.arange(n), gain) / 20.0)


def polish(x):
    """Light compression and a little presence, on the whole take."""
    x = sosfilt(butter(2, 70.0, "highpass", fs=RATE, output="sos"), x)
    x = peaking(x, 3000.0, 2.5, 0.9)
    meter = pyloudnorm.Meter(RATE)
    x = x * 10.0 ** ((-20.0 - meter.integrated_loudness(x)) / 20.0)      # a known level in, so the threshold means the same for every take
    return compress(x, -22.0, 1.6, 0.006, 0.12)


def bounds(seg, below=42.0):
    """Where the speech starts and ends in a segment, in seconds (the quiet round it is left out)."""
    hop = int(RATE * 0.005)
    lv = make_vo.frame_levels(seg, hop)
    loud = np.nonzero(lv > lv.max() - below)[0]
    return loud[0] * hop / RATE, min(len(seg), (loud[-1] + 2) * hop) / RATE


def stretch(x, tempo):
    """x played `tempo` times faster at the same pitch (ffmpeg's atempo), which is fine up to about 10%."""
    with tempfile.TemporaryDirectory() as tmp:
        a, b = os.path.join(tmp, "a.wav"), os.path.join(tmp, "b.wav")
        soundfile.write(a, x.astype(np.float32), RATE, subtype="FLOAT")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", a, "-filter:a", "atempo={:.5f}".format(tempo), b], check=True)
        return soundfile.read(b, dtype="float64")[0]


def phrases_of(spoken, shown):
    """The sentences of a line: (shown text, number of tokens). Spoken and shown differ only in how CopyThat is written."""
    cut = lambda s: [p.strip() for p in re.split(r"(?<=[.!?:;])\s+", s.strip()) if p.strip()]   # noqa: E731
    sp, sh = cut(spoken), cut(shown)
    assert len(sp) == len(sh), (spoken, shown)
    return [(b, len(tokens(a))) for a, b in zip(sp, sh)]


def split_take(x, at, plines):
    """The lines of a polished take, cut at the quietest moment between them: for each, its samples (trimmed to the speech) and the
    time of every word in it, in seconds from the start of those samples."""
    ranges, n = [], 0
    for _id, shown, spoken in plines:
        k = len(tokens(spoken or shown))
        ranges.append((n, n + k))
        n += k
    lv = make_vo.frame_levels(x, int(RATE * 0.005))
    cuts = [0.0]
    for (_a0, a1), (b0, _b1) in zip(ranges, ranges[1:]):
        t0, t1 = at[a1 - 1][1], at[b0][0]
        i0 = int(max(0.0, t0 - 0.03) / 0.005)
        i1 = int(max(t1 + 0.03, t0 + 0.01) / 0.005) + 1
        cuts.append((i0 + int(np.argmin(lv[i0:i1])) + 1) * 0.005)
    cuts.append(len(x) / RATE)
    out = []
    for (a0, a1), c0, c1 in zip(ranges, cuts, cuts[1:]):
        seg = x[int(c0 * RATE):int(c1 * RATE)]
        s0, s1 = bounds(seg)
        first = max(0.0, s0 - make_vo.HEAD)
        y = seg[int(first * RATE):min(len(seg), int((s1 + make_vo.TAIL) * RATE))]
        shift = c0 + first                                              # a time of the take, less this, is a time of the line's WAV
        times = [(at[i][0] - shift, at[i][1] - shift) for i in range(a0, a1)]
        # Whisper puts a word that follows a pause too early and ends the last word too soon, so the line's speech
        # starts and ends where the levels say it does
        times[0] = (s0 - first, max(times[0][1], s0 - first + 0.05))
        times[-1] = (min(times[-1][0], s1 - first - 0.05), s1 - first)
        out.append({"y": y, "times": times})
    return out


def choose(model, name, takes_dir):
    """The best take of a passage, already cut into its lines (see the top of this file for what 'best' is)."""
    plines = PASSAGES[name]
    script = tokens(" ".join(spoken or shown for _i, shown, spoken in plines))
    rows = []
    for path in sorted(glob.glob(os.path.join(takes_dir, name + "_*.wav"))):
        raw, rate = soundfile.read(path, dtype="float64")
        x = polish(resample_poly(raw, RATE // rate, 1))
        at, bad = align(script, hear(model, x))
        with open(path[:-4] + ".json", encoding="utf-8") as fh:
            info = json.load(fh)
        rows.append({"x": x, "at": at, "bad": bad, "seconds": len(x) / RATE, "spread": info["pitch_spread_st"],
                     "name": os.path.basename(path)[:-4], "wrong": None})
    fewest = min(r["bad"] for r in rows)
    for r in rows:
        if r["bad"] <= fewest + 1:                                     # the lines of the takes that heard well as a whole, one by one
            r["cut"] = split_take(r["x"], r["at"], plines)
            # heard as it will be in the film: finished (levelled and limited), because that can tip a word Whisper is unsure of ("slider")
            r["wrong"] = sum(align(tokens(spoken or shown), hear(model, make_vo.finish(c["y"])[0]))[1] for (_i, shown, spoken), c in zip(plines, r["cut"]))
    rows = [r for r in rows if r["wrong"] is not None]
    fewest = min(r["wrong"] for r in rows)
    fastest = min(r["seconds"] for r in rows if r["wrong"] == fewest)
    for r in rows:
        print("   {:12s} {:2d} wrong in the lines  {:5.2f} s  pitch spread {:4.2f} st".format(r["name"], r["wrong"], r["seconds"], r["spread"]))
    ok = [r for r in rows if r["wrong"] == fewest and r["seconds"] <= 1.25 * fastest]
    best = max(ok, key=lambda r: r["spread"])
    print("   -> {}".format(best["name"]))
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--takes", required=True)
    ap.add_argument("--model", default="small.en")
    ap.add_argument("--cache", default=None)
    ap.add_argument("--only", default="", help="comma-separated passage ids to cut; the other lines of vo.json are kept")
    args = ap.parse_args()
    only = set(x for x in args.only.split(",") if x)

    model = WhisperModel(args.model, device="cpu", compute_type="int8", download_root=args.cache)
    room = {}                       # the longest speech a beat takes: its length less the lead and the tail, plus the nudge
    for _bid, _name, _section, length, line_id, lead in make_timeline.BEATS:
        if length:
            room[line_id] = length - make_timeline.MIN_TAIL - lead + min(make_timeline.NUDGE, lead)

    lines, final, too_long = {}, {}, []
    for name, plines in PASSAGES.items():
        if only and name not in only:
            continue
        print(name)
        best = choose(model, name, args.takes)
        for (line_id, shown, spoken), cut in zip(plines, best["cut"]):
            y, times = cut["y"], cut["times"]
            toks = tokens(spoken or shown)
            speech = times[-1][1] - times[0][0]
            tempo = 1.0
            if line_id in room and speech > room[line_id]:
                tempo = speech / room[line_id]
                if tempo > 1.0 + MAX_STRETCH:
                    too_long.append("{}: {:.2f} s of speech for a room of {:.2f} s".format(line_id, speech, room[line_id]))
                    tempo = 1.0 + MAX_STRETCH
                y = stretch(y, tempo)
                times = [(a / tempo, b / tempo) for a, b in times]
            y, dip = make_vo.finish(y)
            words = [{"w": w, "start": round(a, 3), "end": round(b, 3)} for w, (a, b) in zip(toks, times)]
            k, phrases = 0, []
            for text, count in phrases_of(spoken or shown, shown):
                phrases.append({"text": text, "start": words[k]["start"], "end": words[k + count - 1]["end"]})
                k += count
            soundfile.write(os.path.join(HERE, line_id + ".wav"), y.astype(np.float32), RATE, subtype="PCM_16")
            meter = pyloudnorm.Meter(RATE)
            lines[line_id] = {"beat": line_id, "text": shown, "spoken": spoken or shown, "file": line_id + ".wav",
                              "duration": round(len(y) / RATE, 3), "tempo": round(tempo, 4), "take": best["name"],
                              "lufs": round(float(meter.integrated_loudness(y)), 1),
                              "peak_db": round(float(20.0 * np.log10(np.abs(y).max())), 1), "limiter_dip_db": round(float(dip), 1),
                              "phrases": phrases, "words": words}
            final[line_id] = y
            gap = max([q["start"] - p["end"] for p, q in zip(words, words[1:])] + [0.0])
            print("   {:9s} {:5.2f} s  speech {:4.2f}-{:4.2f}  x{:5.3f}  {:5.1f} LUFS  peak {:5.1f} dB  dip {:3.1f} dB  {:3.1f} words/s  "
                  "longest gap {:4.2f} s  {}".format(line_id, lines[line_id]["duration"], words[0]["start"], words[-1]["end"], tempo,
                                                      lines[line_id]["lufs"], lines[line_id]["peak_db"], dip,
                                                      len(words) / (words[-1]["end"] - words[0]["start"]), gap, shown))

    print("the listening check: Whisper on the finished WAVs")
    wrong = 0
    for line_id, y in final.items():
        said = [h["w"] for h in hear(model, y)]
        same = said == tokens(lines[line_id]["spoken"])
        wrong += 0 if same else 1
        lines[line_id]["heard"] = " ".join(said)
        print("   {:9s} {}  {}".format(line_id, "ok  " if same else "DIFF", " ".join(said)))

    order = [lid for plines in PASSAGES.values() for lid, _s, _p in plines]
    if only:                                    # the lines that were not cut are the ones already in vo.json
        with open(os.path.join(HERE, "vo.json"), encoding="utf-8") as fh:
            old = json.load(fh)["lines"]
        for lid in order:
            if lid not in lines:
                lines[lid] = old[lid]
    data = {"engine": "Chatterbox (Resemble AI, MIT), local on an RTX 3090", "voice": "the default voice, in continuous passages cut at the word times",
            "settings": SETTINGS, "sample_rate": RATE, "channels": 1, "bit_depth": 16, "lufs_per_line": LUFS,
            "processing": "high-pass 70 Hz, +2.5 dB at 3 kHz, 1.6:1 compressor, limiter at -1.5 dBFS",
            "order": order, "lines": {lid: lines[lid] for lid in order}, "total": round(sum(lines[lid]["duration"] for lid in order), 3)}
    with open(os.path.join(HERE, "vo.json"), "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=1, ensure_ascii=False)
        fh.write("\n")
    print("{:d} line(s) differ from the script; {:.1f} s of voice in {:d} lines".format(wrong, data["total"], len(data["lines"])))
    for msg in too_long:
        print("TOO LONG", msg)


if __name__ == "__main__":
    main()
