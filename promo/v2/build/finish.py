"""Audio mix, captions and the final film of promo v2.1.

    python promo/v2/build/finish.py audio     vo.wav, sfx.wav (stems, no music) and the mix, about -14 LUFS, true peak -1 dB
    python promo/v2/build/finish.py srt       captions.srt
    python promo/v2/build/finish.py film      joins the rendered segments with the mix: H.264 High, AAC 320k 48 kHz, +faststart

Everything lands in dist/promo/v2/. The voice and the sound effects are placed on the film's clock by timeline.json:
the voice lines where the beats put them, a whoosh on every stripe wipe, a tick as each headline lands, a click on
every cursor click (a press and a release for a drag), a pop for every Ring copy.
"""

import json
import os
import re
import subprocess
import sys

import numpy as np
from scipy.io import wavfile
from scipy.signal import resample_poly

HERE = os.path.dirname(os.path.abspath(__file__))
V2 = os.path.dirname(HERE)
REPO = os.path.abspath(os.path.join(V2, "..", ".."))
OUT = os.path.join(REPO, "dist", "promo", "v2")
AUDIO = os.path.join(V2, "audio")
SR = 48000
TARGET_LUFS, CEILING_DB = -14.0, -1.8          # the limiter's ceiling leaves room for inter-sample peaks under -1 dBTP


def load(path):
    rate, data = wavfile.read(path)
    assert rate == SR, (path, rate)
    x = data.astype(np.float32)
    if data.dtype == np.int16:
        x /= 32768.0
    return x if x.ndim == 1 else x.mean(axis=1)


def place(track, clip, t, gain=1.0):
    i = int(round(t * SR))
    if i < 0:
        clip, i = clip[-i:], 0
    n = min(len(clip), len(track) - i)
    if n > 0:
        track[i:i + n] += clip[:n] * gain


def stems(T):
    n = int(round(T["duration"] * SR))
    vo, sfx = np.zeros(n, np.float32), np.zeros(n, np.float32)
    for line in T["lines"].values():
        place(vo, load(os.path.join(V2, line["file"])), line["start"])
    fx = {k: load(os.path.join(V2, p)) for k, p in T["sfx_files"].items()}
    for w in T["wipes"]:
        place(sfx, fx["whoosh"], w["whoosh"], 0.9)
    for tk in T["ticks"]:
        place(sfx, fx["tick"], tk["t"], 1.0)
    for c in T["clicks"]:
        place(sfx, fx[{"click": "click", "down": "click_down", "up": "click_up"}[c["kind"]]], c["t"], 1.0)
    for p in T.get("pops", []):
        place(sfx, fx[p["name"]], p["t"], 0.9)
    return vo, sfx


def limiter_gain(x, ceiling, look=0.003, release=0.12):
    """A look-ahead peak limiter's gain curve: it dips ahead of a peak and recovers slowly, so it stays out of the speech."""
    from scipy.ndimage import minimum_filter1d
    need = np.minimum(1.0, ceiling / np.maximum(np.abs(x), 1e-9))
    la = int(look * SR)
    need = minimum_filter1d(need, size=2 * la + 1, origin=-la)           # the dip starts `look` seconds before the peak
    k = np.exp(-1.0 / (release * SR))
    g = np.empty_like(need)
    cur = 1.0
    for i in range(len(need)):                                           # attack at once, release slowly
        cur = need[i] if need[i] < cur else need[i] + (cur - need[i]) * k
        g[i] = cur
    return np.minimum(g, need)


def true_peak_db(x):
    return 20 * np.log10(np.max(np.abs(resample_poly(x, 4, 1))) + 1e-12)


def audio():
    import pyloudnorm as pyln
    T = json.load(open(os.path.join(V2, "timeline.json")))
    vo, sfx = stems(T)
    meter = pyln.Meter(SR)
    ceiling = 10 ** (CEILING_DB / 20)
    g_db, mixed = 6.0, None
    for _ in range(8):                                                   # find the gain that lands on the target after limiting
        g = 10 ** (g_db / 20)
        pre = (vo + sfx) * g
        lim = limiter_gain(pre, ceiling)
        mixed = pre * lim
        loud = meter.integrated_loudness(np.stack([mixed, mixed], axis=1))
        print("gain {:+.2f} dB -> {:.2f} LUFS, true peak {:.2f} dB".format(g_db, loud, true_peak_db(mixed)))
        if abs(loud - TARGET_LUFS) < 0.1:
            break
        g_db += TARGET_LUFS - loud
    os.makedirs(OUT, exist_ok=True)

    def write(name, x):                                                  # 24-bit stereo, 48 kHz
        tmp = os.path.join(OUT, "_tmp_" + name)
        wavfile.write(tmp, SR, np.stack([x, x], axis=1).astype(np.float32))
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", tmp, "-c:a", "pcm_s24le", os.path.join(OUT, name)], check=True)
        os.remove(tmp)
    write("vo.wav", vo * g * lim)                                        # the same gain on both, so the stems add up to the mix
    write("sfx.wav", sfx * g * lim)
    write("mix.wav", mixed)
    print("mix: {:.2f} LUFS, true peak {:.2f} dB, {:.2f} s".format(loud, true_peak_db(mixed), len(mixed) / SR))


def srt_time(t):
    ms = int(round(t * 1000))
    return "{:02d}:{:02d}:{:02d},{:03d}".format(ms // 3600000, ms // 60000 % 60, ms // 1000 % 60, ms % 1000)


def srt():
    T = json.load(open(os.path.join(V2, "timeline.json")))
    cues = []
    for line in T["lines"].values():
        ph = line["phrases"]
        if len(ph) > 2:                                                  # "Bones. Constraints. Drivers. Keys." reads as one caption
            ph = [{"text": line["text"], "start": ph[0]["start"], "end": ph[-1]["end"]}]
        for p in ph:
            cues.append((p["start"], p["end"] + 0.25, re.sub(r"Copy That", "CopyThat", p["text"])))
    cues.sort()
    rows = []
    for i, (a, b, text) in enumerate(cues):
        if i + 1 < len(cues):
            b = min(b, cues[i + 1][0] - 0.04)
        rows.append("{:d}\n{:s} --> {:s}\n{:s}\n".format(i + 1, srt_time(a), srt_time(b), text))
    with open(os.path.join(OUT, "captions.srt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(rows))
    print(len(rows), "captions")


def film():
    seg = os.path.join(OUT, "segments")
    names = sorted(f for f in os.listdir(seg) if f.endswith(".mp4"))
    lst = os.path.join(OUT, "segments.txt")
    with open(lst, "w") as fh:
        for n in names:
            fh.write("file '{}'\n".format(os.path.join(seg, n).replace("\\", "/")))
    out = os.path.join(OUT, "CopyThat_promo_v2_1440p60.mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-i", os.path.join(OUT, "mix.wav"),
                    "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                    "-bsf:v", "h264_metadata=colour_primaries=1:transfer_characteristics=1:matrix_coefficients=1:video_full_range_flag=0",
                    "-c:a", "aac", "-b:a", "320k", "-ar", "48000",
                    "-movflags", "+faststart", "-shortest", out], check=True)
    info = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_name,profile,width,height,r_frame_rate,pix_fmt,color_space,duration,bit_rate",
                           "-show_entries", "format=duration,size", "-of", "default=nw=1", out], capture_output=True, text=True).stdout
    print(info)


if __name__ == "__main__":
    {"audio": audio, "srt": srt, "film": film}[sys.argv[1]]()
