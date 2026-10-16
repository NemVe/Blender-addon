"""Make the one file the user runs: copythat_promo.py with the flower inlined.

    python promo/user_script/bundle.py [--flower PATH] [--tail PATH] [--out PATH]

Reads copythat_promo.py (next to this file), PROMO/flower/flower.py and
PROMO/checks/bare_tail.py, and writes dist/copythat_promo.py. The flower's
source goes between the ">>> FLOWER BEGIN" and "<<< FLOWER END" markers as a
list of lines, and the tail's (the studio, the camera's move and the part
names of the fast flower: make_flower_fast.py is these two files one after the
other) between ">>> FAST BEGIN" and "<<< FAST END". The script compiles them
into a module of its own when it starts.

If flower.py is missing, will not compile, or lacks build_flower or
flower_steps, the bundle is still written, with scenes 4 and 5 left out, and
this says why. If the tail is missing or will not compile, scene 5 alone is
left out. Plain Python, no Blender needed.
"""

import argparse
import ast
import datetime
import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BEGIN = "# >>> FLOWER BEGIN"
END = "# <<< FLOWER END"
FAST_BEGIN = "# >>> FAST BEGIN"
FAST_END = "# <<< FAST END"
# What the tail has to define for scene 5.
TAIL_NEEDS = ("make_bare", "make_fast", "build_studio", "key_camera", "key_glow",
              "add_bloom", "configure_render")


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def check_flower(source, name):
    """None if the flower code can be bundled, else why not."""
    try:
        tree = ast.parse(source, name)
        compile(source, name, "exec", dont_inherit=True)
    except SyntaxError as exc:
        return "{:s} does not compile: line {!s}: {:s}".format(name, exc.lineno, exc.msg)
    defined = {node.name for node in tree.body
               if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    missing = [n for n in ("build_flower", "flower_steps") if n not in defined]
    if missing:
        return "{:s} has no {:s}".format(name, " or ".join(missing))
    return None


def check_tail(source, name):
    """None if the tail can be bundled, else why not: it has to compile (it
    runs after the flower, in the same names) and define what scene 5 uses."""
    try:
        tree = ast.parse(source, name)
        compile(source, name, "exec", dont_inherit=True)
    except SyntaxError as exc:
        return "{:s} does not compile: line {!s}: {:s}".format(name, exc.lineno, exc.msg)
    defined = {node.name for node in tree.body
               if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    missing = [n for n in TAIL_NEEDS if n not in defined]
    if missing:
        return "{:s} has no {:s}".format(name, " or ".join(missing))
    return None


def inlined(source, filename, variable):
    """(the source as a statement, how many lines, its checksum): ascii(), so a
    line with an accent or a dash in it stays safe in any editor."""
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()[:12]
    lines = source.rstrip("\n").split("\n")
    body = "".join("    {:s},\n".format(ascii(line)) for line in lines)
    return ("# Inlined from {:s} ({:d} lines, sha256 {:s}).\n"
            "{:s} = \"\\n\".join([\n{:s}])\n".format(filename, len(lines), digest, variable, body),
            len(lines), digest)


def block(flower_path):
    """(text for between the markers, a sentence saying what was done)."""
    if not os.path.isfile(flower_path):
        return ("# flower.py was not there when this was bundled: scenes 4 and 5 are left out.\n"
                "FLOWER_SOURCE = None\n",
                "NOTE: {:s} not found. Scenes 4 and 5 are LEFT OUT of the bundle.".format(flower_path))
    source = read(flower_path)
    problem = check_flower(source, os.path.basename(flower_path))
    if problem:
        return ("# The flower code could not be bundled ({:s}): scenes 4 and 5 are left out.\n"
                "FLOWER_SOURCE = None\n".format(problem),
                "NOTE: {:s}. Scenes 4 and 5 are LEFT OUT of the bundle.".format(problem))
    text, count, digest = inlined(source, "flower.py", "FLOWER_SOURCE")
    return text, "Flower bundled: {:d} lines from {:s} (sha256 {:s}).".format(
        count, flower_path, digest)


def fast_block(tail_path):
    """The same for the tail of the fast flower's file, which carries on in the
    flower's module."""
    if not os.path.isfile(tail_path):
        return ("# bare_tail.py was not there when this was bundled: scene 5 is left out.\n"
                "FAST_SOURCE = None\n",
                "NOTE: {:s} not found. Scene 5 is LEFT OUT of the bundle.".format(tail_path))
    source = read(tail_path)
    problem = check_tail(source, os.path.basename(tail_path))
    if problem:
        return ("# The tail of the fast flower could not be bundled ({:s}): scene 5 is left out.\n"
                "FAST_SOURCE = None\n".format(problem),
                "NOTE: {:s}. Scene 5 is LEFT OUT of the bundle.".format(problem))
    text, count, digest = inlined(source, "bare_tail.py", "FAST_SOURCE")
    return text, "Fast flower tail bundled: {:d} lines from {:s} (sha256 {:s}).".format(
        count, tail_path, digest)


def between(source, begin, end):
    start, stop = source.find(begin), source.find(end)
    if start < 0 or stop < start:
        return None
    return source.index("\n", start) + 1, stop


def bundle(flower_path, out_path, tail_path=None):
    """Write the bundle. Returns (ok, messages)."""
    if tail_path is None:
        tail_path = os.path.join(HERE, "..", "checks", "bare_tail.py")
    source = read(os.path.join(HERE, "copythat_promo.py"))
    flower_at = between(source, BEGIN, END)
    fast_at = between(source, FAST_BEGIN, FAST_END)
    if flower_at is None or fast_at is None or flower_at[1] > fast_at[0]:
        return False, ["The FLOWER and FAST markers are missing from copythat_promo.py."]
    stamp = "# Bundled {:s} by bundle.py.\n".format(datetime.date.today().isoformat())
    flower_text, flower_message = block(flower_path)
    fast_text, fast_message = fast_block(tail_path)
    result = (source[:flower_at[0]] + stamp + flower_text + source[flower_at[1]:fast_at[0]]
              + fast_text + source[fast_at[1]:])
    try:
        compile(result, out_path, "exec", dont_inherit=True)
    except SyntaxError as exc:
        return False, ["The bundle does not compile: line {!s}: {:s}".format(exc.lineno, exc.msg)]
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(result)
    return True, [flower_message, fast_message,
                  "Wrote {:s} ({:d} lines).".format(out_path, result.count("\n"))]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--flower", default=os.path.join(HERE, "..", "flower", "flower.py"))
    parser.add_argument("--tail", default=os.path.join(HERE, "..", "checks", "bare_tail.py"))
    parser.add_argument("--out", default=os.path.join(HERE, "dist", "copythat_promo.py"))
    args = parser.parse_args(argv)
    ok, messages = bundle(os.path.normpath(args.flower), os.path.normpath(args.out),
                          os.path.normpath(args.tail))
    for line in messages:
        print(line)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
