"""The voiceover of promo v2.1: every line spoken by Kokoro, trimmed, at 48 kHz.

    python make_vo.py --models <folder with kokoro-v1.0.onnx and voices-v1.0.bin>
                      [--voice am_michael] [--speed 0.95] [--only f05,end]

It writes one mono WAV per line (hook1.wav ... end.wav) next to this script,
and vo.json (text, duration, speed, the phrases of each line). The lines,
their names and the 2.5 s limit of the feature lines come from
promo/v2/PLAN.md, section v2.1. align_vo.py then adds the time of every word.

A line made of several sentences is spoken one phrase at a time and joined
with a pause of a chosen length. Then the start of every phrase is known
exactly (a speech model's own pauses vary, and Whisper puts a word that
follows a pause up to 0.3 s too early), and the pacing is ours. vo.json keeps
the start and end of the speech of every phrase, in seconds from the start of
the WAV.

Kokoro (82M, Apache-2.0) runs on the CPU through kokoro-onnx; its voice
packs are Apache-2.0 too, so the audio carries no licence of its own.
Needs: pip install kokoro-onnx soundfile scipy pyloudnorm
"""

import argparse
import json
import os

import numpy as np
import pyloudnorm
import soundfile
from kokoro_onnx import Kokoro
from scipy.ndimage import minimum_filter1d, uniform_filter1d
from scipy.signal import resample_poly

HERE = os.path.dirname(os.path.abspath(__file__))
RATE = 48000
LUFS = -19.0        # every line is brought to this loudness; the film's mix lifts the voice to about -14 LUFS with the effects
PEAK_DB = -1.5      # the line's sample peak never goes above this: a limiter holds the peaks down
MAX_DIP = 2.5       # ...by this much at the most; a line with taller peaks ends up a little quieter instead,
                    # because the limiter would else thin out its s and t (Whisper heard "Constraint Driver's")
FEATURE_MAX = 2.5   # a feature beat is 2.5-3 s; its line must fit 2.5 s
HEAD = 0.04         # silence kept before the first phrase, and
TAIL = 0.10         # after the last one; between phrases only the chosen pause is left

# name, beat, what the screen shows (and what a caption may quote), what Kokoro is given, and the pauses.
# Kokoro's text has "|" between phrases; the pauses (s) run from the end of one phrase's speech to the
# start of the next one's. None instead of the pauses: the phrases are spoken in one go, because said one
# by one they take 3.5 s instead of 2.6 s (hook2), and where each starts is worked out (see natural()).
# "CopyThat" is given as two words: as one it is read "copythat", with the stress in the wrong place.
LINES = (
    ("hook1", "Hook 1", "Rigging takes hours.", None, ()),
    ("hook2", "Hook 2", "Bones. Constraints. Drivers. Keys.", "Bones.|Constraints.|Drivers.|Keys.", None),
    ("hook3", "Hook 3", "What if you just showed it the move?", None, ()),
    ("logo", "Logo", "This is CopyThat. Record a move, get a slider.", "This is Copy That.|Record a move, get a slider.", (0.32,)),
    ("idea1", "Idea 1/3", "Pose it, and record.", None, ()),
    ("idea2", "Idea 2/3", "Press Build. One slider plays the move.", "Press Build.|One slider plays the move.", (0.28,)),
    ("idea3", "Idea 3/3", "Select many parts: one move.", "Select many parts:|one move.", (0.25,)),
    ("f01", "01 Timing", "Give each part its own delay.", None, ()),
    ("f02", "02 Spread", "Spread the timing into a wave.", None, ()),
    ("f03", "03 Pivot", "Turn about any point.", None, ()),
    ("f04", "04 Steps", "Add steps in between.", None, ()),
    ("f05", "05 Curves", "Curve the path, and edit its curve.", None, ()),
    ("f06", "06 Speed", "Smooth, or even speed.", None, ()),
    ("f07", "07 Chain", "Chain parts, so joints follow.", None, ()),
    ("f08", "08 Curl", "Curl a whole chain at once.", None, ()),
    ("f09", "09 Ring", "Ring one part into many.", None, ()),
    ("f10", "10 Mirror", "Mirror the copies.", None, ()),
    ("f11", "11 Combine", "Combine moves under one control.", None, ()),
    ("f12", "12 Animate", "Animate it in one click.", None, ()),
    ("together", "Put it together", "Put it together: twenty-one parts, one slider.",
     "Put it together:|twenty-one parts,|one slider.", (0.3, 0.22)),
    ("real", "Real Blender", "All right in Blender's sidebar.", None, ()),
    ("end", "End card", "CopyThat. Now on Superhive.", "Copy That.|Now on Superhive.", (0.36,)),
)

# Words Kokoro gets wrong from the spelling: the phonemes espeak makes of them, and what to say instead.
# "copies" ends in a lax vowel, so Whisper (and a listener) hears "cop is"; "and" after a comma is swallowed.
PHON_FIX = {
    "f10": (("kˈɑːpɪz", "kˈɑːpiz"),),
    "idea1": (("ɪt, ænd", "ɪt, ˌænd"),),
}

# The longest each line may be (s), where the beat of the structure table leaves little room.
MAX_LEN = {"hook1": 2.5, "hook2": 2.6, "hook3": 2.6, "real": 2.6}
for _n in range(1, 13):
    MAX_LEN["f{:02d}".format(_n)] = FEATURE_MAX


def frame_levels(x, hop):
    """The level of x in dB (rms of 2 hops) at every hop."""
    n = len(x) // hop
    if n < 3:
        return np.full(1, -120.0)
    sq = x[: n * hop].reshape(n, hop) ** 2
    sq = np.sqrt(0.5 * (sq.mean(axis=1)[:-1] + sq.mean(axis=1)[1:]))
    return 20.0 * np.log10(np.maximum(sq, 1e-9))


def trim(x, rate, head, tail, below=42.0):
    """Cut the silence round the speech, keeping head and tail seconds of it so nothing is clipped.

    Also gives where the speech starts and ends inside what is left, in seconds.
    """
    hop = int(rate * 0.005)
    lv = frame_levels(x, hop)
    loud = np.nonzero(lv > lv.max() - below)[0]
    s0, s1 = loud[0] * hop, min(len(x), (loud[-1] + 2) * hop)
    first = max(0, s0 - int(head * rate))
    last = min(len(x), s1 + int(tail * rate))
    return x[first:last], (s0 - first) / rate, (s1 - first) / rate


def fade(x, rate, fade_in=0.006, fade_out=0.045):
    """A raised-cosine fade at both ends, so no click is left where the line was cut."""
    x = x.copy()
    a = min(int(fade_in * rate), len(x) // 2)
    b = min(int(fade_out * rate), len(x) // 2)
    x[:a] *= 0.5 - 0.5 * np.cos(np.linspace(0.0, np.pi, a))
    x[len(x) - b:] *= 0.5 + 0.5 * np.cos(np.linspace(0.0, np.pi, b))
    return x


def limit(x, ceiling):
    """A look-ahead limiter: the gain sinks smoothly before a peak that would pass the ceiling, then comes back.

    Kokoro's lines have tall, short peaks (plosives, sibilants): without the limiter they would
    cap how loud a line can be, and every line would end up at a different loudness.
    """
    hold = int(0.012 * RATE) | 1
    smooth = int(0.006 * RATE) | 1      # not wider than hold, so the gain never ends up above what a peak needs
    want = np.minimum(1.0, ceiling / np.maximum(np.abs(x), 1e-9))
    gain = uniform_filter1d(minimum_filter1d(want, size=hold, mode="nearest"), size=smooth, mode="nearest")
    return x * gain, gain.min()


def reach(x, target, meter):
    """x limited to the ceiling and brought to the target loudness; also the deepest limiter dip in dB."""
    ceiling = 10.0 ** (PEAK_DB / 20.0)
    gain = 10.0 ** ((target - meter.integrated_loudness(x)) / 20.0)
    for _ in range(6):
        y, lowest = limit(x * gain, ceiling)
        got = meter.integrated_loudness(y)
        if abs(got - target) < 0.1:
            break
        gain *= 10.0 ** ((target - got) / 20.0)   # the limiter took some loudness back: ask for more
    return y, -20.0 * np.log10(lowest)


def join(parts, pauses):
    """The phrases (samples, rate) as one 48 kHz line, with the chosen pauses between their speech.

    Gives the line and, for every phrase, where its speech starts and ends in seconds.
    """
    pieces, spans, at, last_tail = [], [], 0, 0.0
    for i, (raw, rate) in enumerate(parts):
        x, s0, s1 = trim(np.asarray(raw, dtype=np.float64), rate,
                         HEAD if i == 0 else 0.02, TAIL if i == len(parts) - 1 else 0.03)
        x = resample_poly(x, RATE // rate, 1)
        if i:   # silence that, with the tail of the last phrase and the head of this one, makes the pause
            gap = max(0, int(round((pauses[i - 1] - last_tail - s0) * RATE)))
            pieces.append(np.zeros(gap))
            at += gap
        spans.append((at / RATE + s0, at / RATE + s1))
        pieces.append(x)
        at += len(x)
        last_tail = len(x) / RATE - s1
    return np.concatenate(pieces), spans


def natural(kokoro, name, texts, voice, speed):
    """The phrases spoken in one go, as one 48 kHz line, with an estimate of where each phrase starts.

    Each phrase is also spoken alone, to know how big a share of the line it takes; the border between
    two phrases is put at that share of the speech, then moved to the quietest moment close to it (the
    closing of the mouth before the next word). Laid over the spectrogram of hook2 it falls where the
    words start, within about 0.03 s.
    """
    raw, rate = speak(kokoro, name, " ".join(texts), voice, speed)
    x, s0, s1 = trim(np.asarray(raw, dtype=np.float64), rate, HEAD, TAIL)
    alone = []
    for text in texts:
        one, one_rate = speak(kokoro, name, text, voice, speed)
        _x, a, b = trim(np.asarray(one, dtype=np.float64), one_rate, 0.0, 0.0)
        alone.append(b - a)
    lv = frame_levels(x, int(rate * 0.005))     # one value per 5 ms
    marks, done = [s0], 0.0
    for d in alone[:-1]:
        done += d
        i = int(round((s0 + (s1 - s0) * done / sum(alone)) / 0.005))
        lo, hi = max(0, i - 14), min(len(lv) - 1, i + 14)
        marks.append((lo + int(np.argmin(lv[lo:hi + 1]))) * 0.005 + 0.02)    # speech resumes just after the lowest point
    marks.append(s1)
    spans = [(marks[k], marks[k + 1] - (0.03 if k < len(texts) - 1 else 0.0)) for k in range(len(texts))]
    return resample_poly(x, RATE // rate, 1), spans


def finish(x):
    """A joined line at the target loudness, limited; also the deepest limiter dip in dB."""
    x = fade(x, RATE)
    meter = pyloudnorm.Meter(RATE)
    for target in np.arange(LUFS, LUFS - 6.0, -0.5):
        y, dip = reach(x, target, meter)
        if dip <= MAX_DIP:
            break
    return y, dip


def speak(kokoro, name, text, voice, speed):
    phonemes = name in PHON_FIX
    if phonemes:
        text = kokoro.tokenizer.phonemize(text, "en-us")
        for wrong, right in PHON_FIX[name]:
            if wrong not in text:
                raise SystemExit("{}: espeak no longer says {!r} in {!r}".format(name, wrong, text))
            text = text.replace(wrong, right)
    try:
        raw, rate = kokoro.create(text, voice=voice, speed=speed, lang="en-us", is_phonemes=phonemes, trim=False)
    except TypeError:
        raw, rate = kokoro.create(text, voice=voice, speed=speed, lang="en-us", is_phonemes=phonemes)
    return raw, rate


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", required=True, help="folder with kokoro-v1.0.onnx and voices-v1.0.bin")
    ap.add_argument("--voice", default="am_michael")
    ap.add_argument("--speed", type=float, default=0.95)
    ap.add_argument("--only", default="", help="comma-separated line names; the others are kept as they are")
    ap.add_argument("--out", default=HERE)
    args = ap.parse_args()

    kokoro = Kokoro(os.path.join(args.models, "kokoro-v1.0.onnx"), os.path.join(args.models, "voices-v1.0.bin"))
    voices = kokoro.get_voices()
    if args.voice not in voices:
        raise SystemExit("voice {} is not in the pack: {}".format(args.voice, ", ".join(sorted(voices))))

    json_path = os.path.join(args.out, "vo.json")
    old = {}
    if os.path.exists(json_path):
        with open(json_path, encoding="utf-8") as fh:
            old = json.load(fh).get("lines", {})
    only = set(s for s in args.only.split(",") if s)

    lines = {}
    for name, beat, shown, spoken, pauses in LINES:
        path = os.path.join(args.out, name + ".wav")
        if only and name not in only and name in old and os.path.exists(path):
            lines[name] = old[name]
            continue
        texts = (spoken or shown).split("|")
        speed = args.speed
        limit_s = MAX_LEN.get(name)
        while True:
            if pauses is None:
                x, spans = natural(kokoro, name, texts, args.voice, speed)
            else:
                x, spans = join([speak(kokoro, name, t, args.voice, speed) for t in texts], pauses)
            x, dip_db = finish(x)
            length = len(x) / RATE
            # A line that is too long for its beat is spoken a little faster, never cut.
            if limit_s is None or length <= limit_s or speed >= 1.2:
                break
            speed = round(speed + 0.025, 3)
        soundfile.write(path, x.astype(np.float32), RATE, subtype="PCM_16")
        lines[name] = {"beat": beat, "text": shown, "spoken": " ".join(texts), "file": name + ".wav",
                       "duration": round(length, 3), "speed": speed, "max": limit_s,
                       "lufs": round(float(pyloudnorm.Meter(RATE).integrated_loudness(x)), 1),
                       "peak_db": round(float(20.0 * np.log10(np.abs(x).max())), 1),
                       "limiter_dip_db": round(float(dip_db), 1),
                       "timing": "estimated" if pauses is None else "measured",
                       "phrases": [{"text": t, "start": round(a, 3), "end": round(b, 3)}
                                   for t, (a, b) in zip(texts, spans)]}
        print("{:9s} {:5.2f} s  speech {:4.2f}-{:4.2f}  speed {:5.3f}  limiter {:3.1f} dB  {}".format(
            name, length, spans[0][0], spans[-1][1], speed, dip_db, shown))

    total = sum(v["duration"] for v in lines.values())
    data = {"engine": "Kokoro-82M v1.0 (kokoro-onnx), CPU", "voice": args.voice, "speed": args.speed,
            "sample_rate": RATE, "channels": 1, "bit_depth": 16, "lufs_per_line": LUFS,
            "order": [row[0] for row in LINES], "lines": lines, "total": round(total, 3)}
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=1, ensure_ascii=False)
        fh.write("\n")
    print("total {:.1f} s of voice in {:d} lines".format(total, len(lines)))


if __name__ == "__main__":
    main()
