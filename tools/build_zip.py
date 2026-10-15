"""Pack the add-on into the zip Blender installs from.

    python tools/build_zip.py

Writes dist/CopyThat-<version>.zip, a Blender extension: the manifest, the
add-on and its guide at the top of the zip, with the licence. The version is
read from bl_info and written into the manifest as it goes in, so the file
name, the add-on and the manifest can never disagree. Needs no Blender.
"""

import ast
import pathlib
import re
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "rigmoves"
MANIFEST = "blender_manifest.toml"


def version():
    """bl_info's version, read without importing bpy."""
    tree = ast.parse((PACKAGE / "__init__.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
                getattr(target, "id", None) == "bl_info" for target in node.targets):
            return ".".join(str(n) for n in ast.literal_eval(node.value)["version"])
    raise SystemExit("rigmoves/__init__.py has no bl_info version")


def main():
    number = version()
    out = ROOT / "dist" / "CopyThat-{:s}.zip".format(number)
    out.parent.mkdir(exist_ok=True)
    manifest = (PACKAGE / MANIFEST).read_text(encoding="utf-8")
    manifest, found = re.subn(r'(?m)^version = "[^"]*"$',
                              'version = "{:s}"'.format(number), manifest)
    if found != 1:
        raise SystemExit("{:s} has no single version line".format(MANIFEST))
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(MANIFEST, manifest)
        for path in sorted(PACKAGE.rglob("*")):
            if (path.is_file() and "__pycache__" not in path.parts
                    and path.name != MANIFEST):
                archive.write(path, path.relative_to(PACKAGE).as_posix())
        archive.write(ROOT / "LICENSE", "LICENSE")
    print(out.relative_to(ROOT))


if __name__ == "__main__":
    main()
