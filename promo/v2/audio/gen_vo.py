"""Speak the passages of promo v2.2 with Chatterbox (Resemble AI, MIT) on the GPU: a few takes of each, for cut_vo.py to choose from.

    <python 3.11 venv with chatterbox-tts>  gen_vo.py --out <folder for the takes> [--only open,close] [--takes 4] [--seed0 1000]

Chatterbox does not install on Python 3.13 (it pins numpy<1.26 and torch 2.6), so it lives in a 3.11 venv made with uv:
    uv venv --python 3.11 cb_venv
    uv pip install --python cb_venv/Scripts/python.exe chatterbox-tts --extra-index-url https://download.pytorch.org/whl/cu124 --index-strategy unsafe-best-match
(torch from PyPI is the CPU build on Windows; the cu124 index has the CUDA one.)

It writes <passage>_<seed>.wav (24 kHz) and <passage>_<seed>.json: the text, the settings, the length, and how lively the pitch
is (its spread in semitones over the voiced frames, a rough measure of "not read from a script"). The text and the settings are
those of vo_script.py.
"""

import argparse
import json
import os
import random
import sys

import librosa
import numpy as np
import soundfile
import torch
from chatterbox.tts import ChatterboxTTS

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from vo_script import PASSAGES, SETTINGS, TAKES  # noqa: E402


def liveliness(x, rate):
    """The spread of the pitch in semitones over the voiced frames."""
    f0 = librosa.yin(x, fmin=70, fmax=400, sr=rate, frame_length=2048)
    rms = librosa.feature.rms(y=x, frame_length=2048, hop_length=512)[0][: len(f0)]
    voiced = (rms > 0.25 * np.median(rms[rms > 0.02 * rms.max()])) & (f0 > 75) & (f0 < 380)
    return float(np.std(12.0 * np.log2(f0[voiced]))) if voiced.sum() > 20 else 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--only", default="")
    ap.add_argument("--takes", type=int, default=TAKES)
    ap.add_argument("--seed0", type=int, default=1000, help="the first seed: a second run with 1004 adds four more takes")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    only = set(s for s in args.only.split(",") if s)

    model = ChatterboxTTS.from_pretrained(device="cuda" if torch.cuda.is_available() else "cpu")
    for name, lines in PASSAGES.items():
        if only and name not in only:
            continue
        text = " ".join(spoken or shown for _id, shown, spoken in lines)
        for take in range(args.takes):
            seed = args.seed0 + take
            random.seed(seed)
            np.random.seed(seed)
            torch.manual_seed(seed)
            torch.cuda.manual_seed_all(seed)
            wav = model.generate(text, **SETTINGS).squeeze().cpu().numpy()
            base = os.path.join(args.out, "{}_{}".format(name, seed))
            soundfile.write(base + ".wav", wav, model.sr, subtype="PCM_16")
            info = {"passage": name, "seed": seed, "text": text, "settings": SETTINGS, "seconds": round(len(wav) / model.sr, 3),
                    "pitch_spread_st": round(liveliness(wav, model.sr), 2)}
            with open(base + ".json", "w", encoding="utf-8") as fh:
                json.dump(info, fh, indent=1)
            print("{:8s} seed {}  {:5.2f} s  pitch spread {:4.2f} st".format(name, seed, info["seconds"], info["pitch_spread_st"]), flush=True)


if __name__ == "__main__":
    main()
