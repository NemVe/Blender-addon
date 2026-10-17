"""The sound effects of promo v2.1, made from nothing: numpy noise and sine waves.

    python make_sfx.py            (writes the WAVs and sfx.json next to this script)

Nothing is sampled from a recording, so the files are CC0 (see LICENSES.txt).
All are mono, 48 kHz, 16 bit. The peak of each is set for a mix in which the
voice sits near -16 LUFS: the film's mixer may still scale them.

  click_down  the mouse button going down (a short tick with a small thock under it)
  click_up    the button coming back up: softer, higher
  click       both, 100 ms apart: one plain click
  whoosh      a soft sweep for the stripe wipe between two beats; its loudest point is 0.26 s in
  pop         a light bubble pop, for each copy a Ring makes; pop_2 and pop_3 are a little higher
  tick        a soft wooden tick, for a headline landing
Needs: pip install numpy scipy soundfile
"""

import json
import os

import numpy as np
import soundfile
from scipy import signal

HERE = os.path.dirname(os.path.abspath(__file__))
RATE = 48000


def times(seconds):
    return np.arange(int(round(seconds * RATE))) / RATE


def noise(n, seed):
    return np.random.default_rng(seed).standard_normal(n)


def band(x, low, high, order=3):
    sos = signal.butter(order, [low, high], btype="bandpass", fs=RATE, output="sos")
    return signal.sosfilt(sos, x)


def lowpass(x, cutoff, order=3):
    sos = signal.butter(order, cutoff, btype="lowpass", fs=RATE, output="sos")
    return signal.sosfilt(sos, x)


def peak_to(x, db):
    """Scale x so that its largest sample is at db dBFS."""
    return x * (10.0 ** (db / 20.0) / np.abs(x).max())


def attack(t, seconds):
    """A very short rise, so the start of a sound does not click."""
    return 1.0 - np.exp(-t / seconds)


def click_down():
    t = times(0.07)
    tick = band(noise(len(t), 11), 1800, 7500) * np.exp(-t / 0.0022)
    body = (0.55 * np.sin(2 * np.pi * 2100 * t) * np.exp(-t / 0.0045)
            + 0.8 * np.sin(2 * np.pi * 380 * t) * np.exp(-t / 0.010))
    return peak_to((0.9 * tick / np.abs(tick).max() + body) * attack(t, 0.0002), -9.0)


def click_up():
    t = times(0.05)
    tick = band(noise(len(t), 12), 2500, 9000) * np.exp(-t / 0.0016)
    body = (0.5 * np.sin(2 * np.pi * 2900 * t) * np.exp(-t / 0.003)
            + 0.4 * np.sin(2 * np.pi * 520 * t) * np.exp(-t / 0.006))
    return peak_to((0.9 * tick / np.abs(tick).max() + body) * attack(t, 0.0002), -14.0)


def click():
    down, up = click_down(), click_up()
    out = np.zeros(int(0.2 * RATE))
    out[:len(down)] += down
    start = int(0.1 * RATE)
    out[start:start + len(up)] += up
    return out


def whoosh(seconds=0.6, peak_at=0.26, low=450.0, high=4200.0):
    """Noise through a band that sweeps up, under a swell that peaks at peak_at."""
    n = int(seconds * RATE)
    f, tt, z = signal.stft(noise(n, 21), fs=RATE, nperseg=1024, noverlap=768)
    p = np.clip(tt / seconds, 0.0, 1.0)
    p = p * p * (3.0 - 2.0 * p)
    centre = np.log2(low * (high / low) ** p)
    mask = np.exp(-0.5 * ((np.log2(np.maximum(f, 20.0))[:, None] - centre[None, :]) / 1.1) ** 2)
    y = signal.istft(z * mask, fs=RATE, nperseg=1024, noverlap=768)[1]
    y = np.pad(y, (0, max(0, n - len(y))))[:n]
    t = times(seconds)
    swell = np.where(t < peak_at, np.sin(0.5 * np.pi * t / peak_at) ** 2,
                     np.cos(0.5 * np.pi * (t - peak_at) / (seconds - peak_at)) ** 2)
    rumble = lowpass(noise(n, 22), 170.0) * 0.35 * np.abs(y).max() / 0.25
    return peak_to((y + rumble) * swell, -12.0)


def pop(semitones=0.0):
    t = times(0.16)
    end = 330.0 * 2.0 ** (semitones / 12.0)
    freq = end + (3.0 * end - end) * np.exp(-t / 0.014)
    body = np.sin(2 * np.pi * np.cumsum(freq) / RATE) * np.exp(-t / 0.032) * attack(t, 0.0008)
    bite = band(noise(len(t), 31), 1500, 6000) * np.exp(-t / 0.0015)
    return peak_to(body + 0.25 * bite / np.abs(bite).max(), -10.0)


def tick():
    t = times(0.09)
    x = (np.sin(2 * np.pi * 1250 * t) * np.exp(-t / 0.012)
         + 0.4 * np.sin(2 * np.pi * 1250 * 2.76 * t) * np.exp(-t / 0.005)) * attack(t, 0.0006)
    return peak_to(x, -17.0)


# name -> (samples, what it is for, moment inside the file that must meet the picture)
EFFECTS = {
    "click_down": (click_down(), "mouse button down: the press-scale pulse", {"hit": 0.0}),
    "click_up": (click_up(), "mouse button up: the release, the end of a drag", {"hit": 0.0}),
    "click": (click(), "a whole click, down then up", {"hit": 0.0, "up": 0.1}),
    "whoosh": (whoosh(), "the stripe wipe between two beats", {"hit": 0.26}),
    "pop": (pop(0.0), "a Ring copy appears", {"hit": 0.0}),
    "pop_2": (pop(2.0), "a Ring copy appears, a little higher", {"hit": 0.0}),
    "pop_3": (pop(4.0), "a Ring copy appears, higher still", {"hit": 0.0}),
    "tick": (tick(), "a headline lands", {"hit": 0.0}),
}


def main():
    info = {}
    for name, (x, use, marks) in EFFECTS.items():
        soundfile.write(os.path.join(HERE, name + ".wav"), x.astype(np.float32), RATE, subtype="PCM_16")
        info[name] = {"file": name + ".wav", "duration": round(len(x) / RATE, 3), "use": use,
                      "peak_db": round(float(20 * np.log10(np.abs(x).max())), 1), "marks": marks}
        print("{:10s} {:5.3f} s  peak {:5.1f} dB  {}".format(name, len(x) / RATE, info[name]["peak_db"], use))
    with open(os.path.join(HERE, "sfx.json"), "w", encoding="utf-8") as fh:
        json.dump({"sample_rate": RATE, "channels": 1, "bit_depth": 16, "effects": info}, fh, indent=1)
        fh.write("\n")


if __name__ == "__main__":
    main()
