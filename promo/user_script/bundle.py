"""Make the one file the user runs: copythat_promo.py with the flower inlined.

    python3 bundle.py [--flower PATH] [--out PATH]

Reads copythat_promo.py (next to this file) and PROMO/flower/flower.py, and
writes dist/copythat_promo.py. The flower's source goes between the
">>> FLOWER BEGIN" and "<<< FLOWER END" markers as a list of lines, which the
script compiles into a module of its own when it starts.

If flower.py is missing, will not compile, or lacks build_flower or
flower_steps, the bundle is still written, with scene 4 left out, and this
says why. Plain Python, no Blender needed.
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


def block(flower_path):
    """(text for between the markers, a sentence saying what was done)."""
    if not os.path.isfile(flower_path):
        return ("# flower.py was not there when this was bundled: scene 4 is left out.\n"
                "FLOWER_SOURCE = None\n",
                "NOTE: {:s} not found. Scene 4 is LEFT OUT of the bundle.".format(flower_path))
    source = read(flower_path)
    problem = check_flower(source, os.path.basename(flower_path))
    if problem:
        return ("# The flower code could not be bundled ({:s}): scene 4 is left out.\n"
                "FLOWER_SOURCE = None\n".format(problem),
                "NOTE: {:s}. Scene 4 is LEFT OUT of the bundle.".format(problem))
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()[:12]
    lines = source.rstrip("\n").split("\n")
    # ascii(): a line with an accent or a dash in it stays safe in any editor.
    body = "".join("    {:s},\n".format(ascii(line)) for line in lines)
    text = ("# Inlined from flower.py ({:d} lines, sha256 {:s}).\n"
            "FLOWER_SOURCE = \"\\n\".join([\n{:s}])\n".format(len(lines), digest, body))
    return text, "Flower bundled: {:d} lines from {:s} (sha256 {:s}).".format(
        len(lines), flower_path, digest)


def bundle(flower_path, out_path):
    """Write the bundle. Returns (ok, messages)."""
    source = read(os.path.join(HERE, "copythat_promo.py"))
    start, end = source.find(BEGIN), source.find(END)
    if start < 0 or end < start:
        return False, ["The FLOWER markers are missing from copythat_promo.py."]
    after_begin = source.index("\n", start) + 1
    middle, message = block(flower_path)
    stamp = "# Bundled {:s} by bundle.py.\n".format(datetime.date.today().isoformat())
    result = source[:after_begin] + stamp + middle + source[end:]
    try:
        compile(result, out_path, "exec", dont_inherit=True)
    except SyntaxError as exc:
        return False, ["The bundle does not compile: line {!s}: {:s}".format(exc.lineno, exc.msg)]
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(result)
    return True, [message, "Wrote {:s} ({:d} lines).".format(out_path, result.count("\n"))]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--flower", default=os.path.join(HERE, "..", "flower", "flower.py"))
    parser.add_argument("--out", default=os.path.join(HERE, "dist", "copythat_promo.py"))
    args = parser.parse_args(argv)
    ok, messages = bundle(os.path.normpath(args.flower), os.path.normpath(args.out))
    for line in messages:
        print(line)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
