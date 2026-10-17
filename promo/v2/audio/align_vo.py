"""Listen to the voiceover lines (Whisper) and write the time of every word into vo.json.

    python align_vo.py [--cache <folder to keep the Whisper model in>]

It is both the check and the timing. Each phrase of each line is cut out of
its WAV and transcribed; the transcripts are compared with the text the line
was made from, and the words (start and end in seconds from the start of that
line's WAV) go into vo.json under "words", so a caption or a click can be tied
to the word it belongs to.

Whisper's word times are good inside a run of speech and poor at its edges
(a word after a pause comes up to 0.3 s early, and the last word's end is
cut short). So the first word of a phrase starts where make_vo.py measured the
phrase's speech to start, and the last word ends where that ended.
Needs: pip install faster-whisper soundfile scipy (the base.en model is
downloaded the first time, about 150 MB).
"""

import argparse
import json
import os
import re

import soundfile
from faster_whisper import WhisperModel
from scipy.signal import resample_poly

HERE = os.path.dirname(os.path.abspath(__file__))


def plain(text):
    """Words only, so 'Twenty-one parts.' and 'twenty one parts' compare equal."""
    text = text.lower().replace("copythat", "copy that").replace("-", " ")
    return re.findall(r"[a-z0-9']+", text)


def hear(model, x, rate, offset):
    """The words Whisper finds in x, with their times moved by offset seconds."""
    x = resample_poly(x, 1, rate // 16000).astype("float32")
    segments, _info = model.transcribe(x, language="en", word_timestamps=True, beam_size=5,
                                       condition_on_previous_text=False, vad_filter=False)
    return [{"w": w.word.strip(), "start": offset + w.start, "end": offset + w.end}
            for seg in segments for w in seg.words]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", default=None)
    ap.add_argument("--model", default="base.en")
    args = ap.parse_args()

    path = os.path.join(HERE, "vo.json")
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    model = WhisperModel(args.model, device="cpu", compute_type="int8", download_root=args.cache)

    bad = 0
    for name in data["order"]:
        line = data["lines"][name]
        x, rate = soundfile.read(os.path.join(HERE, line["file"]), dtype="float32")
        words = []
        if line.get("timing") == "estimated":
            # Phrases of one word said in one go: cutting one out would take bits of its neighbours along, so
            # the times are the estimates make_vo.py worked out, and Whisper only checks the words.
            words = [{"w": ph["text"].strip(".,:;?! "), "start": ph["start"], "end": ph["end"]} for ph in line["phrases"]]
            heard_words = hear(model, x, rate, 0.0)
        else:
            heard_words = None
        for ph in ([] if heard_words is not None else line["phrases"]):
            a = max(0.0, ph["start"] - 0.08)
            b = min(len(x) / rate, ph["end"] + 0.12)
            got = hear(model, x[int(a * rate):int(b * rate)], rate, a)
            if got:
                got[0]["start"] = ph["start"]
                got[-1]["end"] = ph["end"]
            else:
                got = [{"w": ph["text"], "start": ph["start"], "end": ph["end"]}]
            for w in got:   # inside the phrase, in order
                w["start"] = min(max(w["start"], ph["start"]), ph["end"])
                w["end"] = min(max(w["end"], w["start"]), ph["end"])
            for first, second in zip(got, got[1:]):
                first["end"] = min(first["end"], second["start"])
            words += got
        for w in words:
            w["start"], w["end"] = round(w["start"], 3), round(w["end"], 3)
        heard = " ".join(w["w"] for w in (heard_words if heard_words is not None else words))
        # A number written as a numeral is still the right words.
        said = plain(re.sub(r"\b21\b", "twenty one", re.sub(r"\b1\b", "one", heard)))
        same = said == plain(line["spoken"]) or said == plain(line["text"])
        line["words"] = words
        line["heard"] = heard
        bad += 0 if same else 1
        print("{:9s} {:5.2f} s  {}  | {}".format(name, line["duration"], "ok  " if same else "DIFF", heard))
        print("          " + "  ".join("{}@{:.2f}".format(w["w"], w["start"]) for w in words))

    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=1, ensure_ascii=False)
        fh.write("\n")
    print("{:d} line(s) differ from their text".format(bad))


if __name__ == "__main__":
    main()
