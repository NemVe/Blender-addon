"""Assemble PROMO/files/make_flower_bare.py and make_flower_fast.py: each one
self-contained script.

    python promo/checks/assemble.py

It is flower.py, verbatim (so the flower is the very one flower_steps was
checked on), followed by bare_tail.py: the bare scene, the studio, the camera
and the settings. Run again whenever either changes.
"""

import hashlib
import os

HERE = os.path.dirname(os.path.abspath(__file__))
PROMO = os.path.dirname(HERE)
FLOWER = os.path.join(PROMO, "flower", "flower.py")
OUT = os.path.join(PROMO, "files", "make_flower_bare.py")
OUT_FAST = os.path.join(PROMO, "files", "make_flower_fast.py")

HEADER = '''"""Build the bare CopyThat flower scene: the flower shut, ready for you to rig.

For Blender 4.5 or newer. In Blender: open the Scripting tab, click New,
paste this whole file, and press Run Script (the triangle, or Alt+P).

It adds ONE new scene, "CopyThat Flower", to the file you have open and
switches to it. Nothing you already have is changed or deleted. The scene has:

  * the flower, shut: 8 outer petals, 6 inner petals, the core, a stem with
    two leaves of three segments each, and a pedestal. Every moving part has
    its origin on its hinge or joint, and its hinge is its own X axis, so
    opening it is one number: type the angle into Rotation X in the
    Properties editor (Object tab > Transform);
  * the dark studio, its lights, and the "Promo Camera" with its move (a slow
    push-in and orbit, focused on the core) keyed over frames 1 to 151 and
    then held to frame 210; the core's glow keyed to rise with the bloom;
  * Cycles set up to render it: GPU (the CPU if no GPU is switched on in
    Preferences), 512 adaptive samples, OpenImageDenoise, motion blur, and
    an H.264 movie written next to the .blend as CopyThat_flower_####.mp4.
    Save the file before you render, so "next to the .blend" means something.

There is NO CopyThat data in it: no rig, no moves. That is your part, and it
is in FLOWER_STEPS.md. CopyThat 0.18.1 or newer must be turned on.

The "Studio" collection is hidden in the 3D view so the recording shows the
flower (it still renders). Click its eye in the Outliner to see it.
"""

'''

HEADER_FAST = '''"""Build the FAST CopyThat flower scene: the parts modelled once, ready to rig.

For Blender 4.5 or newer, with CopyThat 0.18.1 or newer. In Blender: open the
Scripting tab, click New, paste this whole file, and press Run Script (the
triangle, or Alt+P) ONCE.

It adds ONE new scene, "CopyThat Flower", to the file you have open and
switches to it. Nothing you already have is changed or deleted. The scene has:

  * the flower, shut, with only the parts that are modelled once: "Outer
    Leader" (a petal), "Inner Leader", "Core", and a leaf of three segments,
    "Leaf 1", "Leaf 2", "Leaf 3", on a stem and a pedestal. The flower stands
    on the world origin with the world Z axis through its middle, so CopyThat's
    Ring round the World Origin puts every other petal exactly in its place;
  * every hinge is the part's own X axis: opening a part is one number typed
    into Rotation X in the Properties editor (Object tab > Transform);
  * the dark studio, its lights, and the "Promo Camera" with its move keyed
    over frames 1 to 151 and then held to frame 210; the core's glow keyed to
    rise with the bloom;
  * Cycles set up to render it: GPU (the CPU if no GPU is switched on in
    Preferences), 512 adaptive samples, OpenImageDenoise, motion blur, and an
    H.264 movie written next to the .blend as CopyThat_flower_####.mp4. Save
    the file before you render.

There is NO CopyThat data in it: no rig, no moves. That is your part, and it
is in FLOWER_FAST.md.

The "Studio" collection is hidden in the 3D view so the recording shows the
flower (it still renders). Click its eye in the Outliner to see it.
"""

'''

def main():
    with open(FLOWER, encoding="utf-8") as handle:
        flower = handle.read()
    with open(os.path.join(HERE, "bare_tail.py"), encoding="utf-8") as handle:
        tail = handle.read()
    digest = hashlib.sha256(flower.encode("utf-8")).hexdigest()[:12]
    # Its own docstring becomes comments, so the imports below stay at the top.
    if flower.startswith('"""'):
        end = flower.index('"""', 3) + 3
        doc = flower[3:end - 3].strip("\n")
        flower = "\n".join(("# " + line).rstrip() for line in doc.splitlines()) + flower[end:]
    middle = ("# ===========================================================================\n"
              "# The flower, inlined from flower.py (sha256 {:s}), unchanged.\n"
              "# ===========================================================================\n\n"
              .format(digest))
    body = middle + flower.rstrip("\n") + "\n" + tail
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    for path, header, call in ((OUT, HEADER, "build_bare_scene()"),
                               (OUT_FAST, HEADER_FAST, "build_bare_scene(fast=True)")):
        text = header + body + '\n\nif __name__ == "__main__":\n    {:s}\n'.format(call)
        # newline="\n": on Windows the default would write CR LF, and every
        # line of the file would show as changed in git.
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        print("wrote", path, len(text.splitlines()), "lines; flower.py sha256", digest)


if __name__ == "__main__":
    main()
