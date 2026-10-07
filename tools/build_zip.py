"""Pack the add-on into the zip Blender installs from.

    python tools/build_zip.py

Writes dist/RigMoves-<version>.zip, the version read from bl_info, so the
file name and the add-on it holds can never disagree. Needs no Blender.
"""

import ast
import pathlib
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "rigmoves"


def version():
    """bl_info's version, read without importing bpy."""
    tree = ast.parse((PACKAGE / "__init__.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
                getattr(target, "id", None) == "bl_info" for target in node.targets):
            return ".".join(str(n) for n in ast.literal_eval(node.value)["version"])
    raise SystemExit("rigmoves/__init__.py has no bl_info version")


def main():
    out = ROOT / "dist" / "RigMoves-{:s}.zip".format(version())
    out.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(PACKAGE.rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts:
                archive.write(path, path.relative_to(ROOT).as_posix())
    print(out.relative_to(ROOT))


if __name__ == "__main__":
    main()
