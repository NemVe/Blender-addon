"""The voiceover script of promo v2.2: what the voice is given, in continuous passages, and the lines that are cut out of them.

A line is (id, what the screen and the captions show, what is said). The id names the beat it goes on (promo/v2/make_timeline.py).
"CopyThat" is said as two words: as one it is read "copythat", with the stress in the wrong place.
Each passage is spoken in one take, so its sentences carry one intonation from start to end (v2.1's lines were made one by
one, and each reset its pitch: "like reading from a script"). gen_vo.py speaks the passages; cut_vo.py cuts the lines out.
"""

# passage id -> its lines
PASSAGES = {
    "open": (
        ("open_a", "Let's rig this flower in twelve clicks. Watch this!", None),
        ("open_b", "Done! One slider, and it blooms.", None),
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
