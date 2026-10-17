"""The voiceover script of promo v2.3: what the voice is given, in continuous passages, and the lines that are cut out of them.

A line is (id, what the screen and the captions show, what is said). The id names the beat it goes on (promo/v2/make_timeline.py).
"CopyThat" is said as two words: as one it is read "copythat", with the stress in the wrong place.
Each passage is spoken in one take, so its sentences carry one intonation from start to end (v2.1's lines were made one by
one, and each reset its pitch: "like reading from a script"). gen_vo.py speaks the passages; cut_vo.py cuts the lines out.
"""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ONES = ("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen "
        "nineteen").split()
TENS = "x x twenty thirty forty fifty".split()


def number_words(n):
    return ONES[n] if n < 20 else TENS[n // 10] + ("-" + ONES[n % 10] if n % 10 else "")


def spoken_time(seconds):
    """The time the timer stops at, as a person says it: 'a minute and ten seconds', 'fifty-eight seconds'."""
    whole = int(seconds + 1e-9)
    minutes, rest = divmod(whole, 60)
    parts = []
    if minutes:
        parts.append("a minute" if minutes == 1 else number_words(minutes) + " minutes")
    if rest or not minutes:
        parts.append(number_words(rest) + (" second" if rest == 1 else " seconds"))
    return " and ".join(parts)


def rigged_in():
    """What the opening's last line says: the real time of the walkthrough, from promo/v2/walk_schedule.json (walk_schedule_json.mjs)."""
    with open(os.path.join(HERE, "..", "walk_schedule.json"), encoding="utf-8") as fh:
        return spoken_time(json.load(fh)["riggedIn"])


# passage id -> its lines
PASSAGES = {
    # v2.3: the walkthrough's narration, one continuous passage. Each line is placed at its step by make_timeline.py. The sentence
    # "Spread the timing down the leaf, and give ..." is cut in two at its comma: the second half is said as the delays are typed.
    "open": (
        ("open_1", "Let's rig this flower from scratch. Clock's running!", None),
        ("open_2", "Select the six parts, and hit New Move.", None),
        ("open_3", "Make the leaf a chain.", None),
        ("open_4", "Now pose it open, one part at a time.", None),
        ("open_5", "Record After.", None),
        ("open_6", "Ring the outer petals.", None),
        ("open_7", "Now the inner ones.", None),
        ("open_8", "And the leaf.", None),
        ("open_9a", "Spread the timing down the leaf", "Spread the timing down the leaf,"),
        ("open_9b", "and give the inner petals and the core a delay.", None),
        ("open_10", "Smooth... and Build!", None),
        ("open_11", "One slider, and it blooms. Rigged in " + rigged_in() + "!", None),
    ),
    "idea": (
        ("logo", "This is CopyThat: record a move, and get a slider.", "This is Copy That: record a move, and get a slider."),
        ("idea1", "Pose your object, and hit Record.", None),
        ("idea2", "Press Build, and the whole move lives on one slider.", None),
        ("idea3", "Select as many parts as you like; they all share one move.", None),
    ),
    "feat_a": (
        ("f01", "Give every part its own delay.", None),
        ("f02", "Spread the timing into a wave.", None),
        ("f03", "Turn around any point you want.", None),
        ("f04", "Add steps in between.", None),
        ("f05", "Curve the path, then edit the curve.", None),
        ("f06", "Smooth, or perfectly even.", None),
    ),
    "feat_b": (
        ("f07", "Chain parts, so the joints follow.", None),
        ("f08", "Curl a whole chain at once.", None),
        ("f09", "Ring one part into many.", None),
        ("f10", "Mirror the copies.", None),
        ("f11", "Combine moves under one control.", None),
        ("f12", "And animate it all in one click.", None),
    ),
    "close": (
        ("together", "Put it all together: twenty-one parts, one slider.", None),
        ("real", "And it all happens right in Blender's sidebar.", None),
        ("end", "CopyThat. Now on Superhive!", "Copy That. Now on Superhive!"),
    ),
}

# the settings of Chatterbox (the plan: more exaggeration and a lower cfg than the defaults, 0.5 and 0.5, for livelier pacing)
SETTINGS = {"exaggeration": 0.65, "cfg_weight": 0.4, "temperature": 0.8}
TAKES = 4           # seeds tried for each passage; cut_vo.py keeps the one that Whisper hears closest to the script
