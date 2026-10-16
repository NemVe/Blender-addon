"""Do what FLOWER_STEPS.md says, to the bare .blend, and prove it blooms the same.

    blender --background --factory-startup --python promo/checks/replay_guide.py -- [--no-render] [--shortcut]

Run from the repo root. It checks this repo's add-on; set COPYTHAT_ADDON to a
folder that holds another copy of rigmoves/ (a frozen version) to check that.

1. Builds the reference: the normal flower rigged by flower_steps(parts, 150),
   and records every part's evaluated mesh at frames 1, 38, 75, 112 and 151.
2. Opens the bare .blend with CopyThat registered and performs the guide's
   steps literally, in the guide's order: selections by select_set with the
   right object active; every pose typed into the Properties editor's fields,
   which is `rotation_euler.x` (degrees), `location.z` and `rotation_euler.z`
   on the objects as the Follows hang them; Ring with Use what's there for the
   other petals, its dialog filled in from the cheat sheet; the same panel
   values; the same operators. The numbers are read from the guide's cheat
   sheet, so they cannot drift from the text. With --shortcut the rotations
   are made by the optional R X X instead, through Blender's own rotate
   operator.
3. Prints the largest difference, which must be under 1e-3.
4. Checks what Ring did (nothing new in the scene; the seven outer and five
   inner petals ride along with their leaders, with the Leads the guide
   lists), that every report the steps quote is the add-on's, that each
   dialog's table in the steps says what the dialog needs, and that what the
   guide asks of the user adds up to the count it states.
5. Renders frame 120 from the replayed bare file (CPU, 16 samples, 50% size).

replay_fast.py builds on this file: the cheat sheet reader, what a user does
and how it is counted, the checks of the dialogs' tables.
"""

import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROMO = os.path.dirname(HERE)
# This repo's add-on (promo/ -> the repo root), unless one is named.
ADDON = os.environ.get("COPYTHAT_ADDON", os.path.dirname(PROMO))
sys.path.insert(0, os.path.join(PROMO, "flower"))
sys.path.insert(0, ADDON)

import bpy  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import flower  # noqa: E402
import rigmoves  # noqa: E402
import run_headless  # noqa: E402

BLEND = os.path.join(PROMO, "files", "CopyThat_flower_bare.blend")
GUIDE = os.path.join(PROMO, "files", "FLOWER_STEPS.md")
FRAMES = (1, 38, 75, 112, 151)
LIMIT = 1e-3
STILL = os.path.join(HERE, "test_frame_0120.png")
OLDEST = (0, 18, 1)              # the oldest CopyThat the guides are written for

# What the guides call a choice in a dialog, and what it is inside.
USES = {"Make copies": "COPY", "Use what's there": "ADOPT", "Fill the gaps": "FILL"}
CENTRES = {"3D Cursor": "CURSOR", "World Origin": "ORIGIN"}
AXES = {"World Z": "Z", "3D Cursor's Z": "CURSOR_Z", "World X": "X", "World Y": "Y"}
ORDERS = {"Around a ring": "AROUND", "By distance": "DISTANCE", "Along an axis": "AXIS",
          "Down a chain": "CHAIN", "Random": "RANDOM"}
BYS = {"Step": "STEP", "Range": "RANGE"}
# The names the guides give the rows of a dialog, in the order the dialog
# shows them, and the property behind each.
FIELDS = {
    "rigmoves.ring": {"Use": "use", "Count": "count", "Round": "center", "About": "axis",
                      "Linked copies": "linked", "Lead step": "lead_step"},
    "rigmoves.spread": {"Order": "order", "Only the selected": "only_selected", "By": "by",
                        "Start Delay": "start", "Delay step": "step"},
}
# The numbers of a dialog that are Leads or Delays, for the count of those.
NUMBERS = ("lead_step", "start", "step", "first", "last")
RING_COLUMNS = ["Part", "Use", "Count", "Round", "About", "Lead step"]
LEAD_TABLE = "Lead (Ring writes these; nothing to type)"


# ---------------------------------------------------------------------------
# the guide's cheat sheet

def read_cheat_sheet(path):
    """The tables under "## Cheat sheet", as {heading: [row cells]}, the
    header row first."""
    with open(path, encoding="utf-8") as handle:
        lines = handle.read().splitlines()
    start = next(i for i, line in enumerate(lines) if line.strip() == "## Cheat sheet")
    tables, name = {}, None
    for line in lines[start + 1:]:
        if line.startswith("## "):
            break                                # the next section: not the cheat sheet
        if line.startswith("### "):
            name = line[4:].strip()
            tables[name] = []
        elif name and line.startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if set("".join(cells)) <= set("-: "):
                continue
            tables[name].append(cells)
    return tables


def cheat_sheet(path=GUIDE):
    """The tables under "## Cheat sheet", as {heading: [row cells]}."""
    return {name: rows[1:] for name, rows in read_cheat_sheet(path).items()}


def cheat_headers(path=GUIDE):
    """The column names of each table under "## Cheat sheet"."""
    return {name: rows[0] for name, rows in read_cheat_sheet(path).items()}


def pose_rows(tables):
    """The Pose table as [(object, field, shut value, typed value)]."""
    return [(name, field, float(shut), float(value))
            for _number, name, field, shut, value in tables["Pose"]]


def pose_table_in_the_steps(path=GUIDE):
    """The same poses as step 3 gives them, before the cheat sheet:
    [(object, field, typed value)]. They must say what the cheat sheet says."""
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    steps = text[:text.index("## Cheat sheet")]
    return [(match.group(1), match.group(2).strip(), float(match.group(3)))
            for match in re.finditer(r"^\| \*\*([^*]+)\*\* \| ([^|]+) \| (-?[0-9.]+) \|", steps, re.M)]


def ring_properties(columns, row):
    """One row of a Ring table as (the part, the dialog's properties, what the
    table says for each). The bare file's table has no Linked copies column:
    with Use what's there the dialog greys that row out."""
    cells = dict(zip(columns, row))
    properties = {"use": USES[cells["Use"]], "count": int(cells["Count"]),
                  "center": CENTRES[cells["Round"]], "axis": AXES[cells["About"]],
                  "lead_step": int(cells["Lead step"])}
    if "Linked copies" in cells:
        properties["linked"] = cells["Linked copies"].lower() == "on"
    words = {FIELDS["rigmoves.ring"][label]: cells[label] for label in FIELDS["rigmoves.ring"]
             if label in cells}
    return cells["Part"], properties, words


def spread_properties(columns, row):
    """One row of a Spread table (by Step) as (the parts to select first, the
    dialog's properties, what the table says for each)."""
    cells = dict(zip(columns, row))
    assert cells["By"] == "Step", "the replay presses Spread by Step: " + cells["By"]
    properties = {"what": "DELAY", "order": ORDERS[cells["Order"]],
                  "only_selected": cells["Only the selected"].lower() == "on", "by": BYS[cells["By"]],
                  "start": float(cells["Start Delay"]), "step": float(cells["Delay step"])}
    words = {FIELDS["rigmoves.spread"][label]: cells[label] for label in FIELDS["rigmoves.spread"]}
    return [n.strip() for n in cells["Select first"].split(",") if n.strip()], properties, words


# ---------------------------------------------------------------------------
# measuring

def world_points(obj):
    """Where the mesh really is, after the rig has deformed it."""
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    points = [tuple(evaluated.matrix_world @ v.co) for v in mesh.vertices]
    evaluated.to_mesh_clear()
    return points


def snapshot(scene, names, frames=FRAMES):
    out = {}
    for frame in frames:
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        out[frame] = {name: world_points(bpy.data.objects[name]) for name in names}
    return out


def difference(a, b):
    return max(math.dist(p, q) for p, q in zip(a, b))


# Bare name -> the flower_steps flower's name.
def names_of_reference():
    out = {"Core": "Core", "Stem": "Stem", "Pedestal": "Pedestal"}
    for k in range(8):
        out["Outer Leader" if not k else "Outer {:d}".format(k + 1)] = "Petal {:d}".format(k + 1)
    for k in range(6):
        out["Inner Leader" if not k else "Inner {:d}".format(k + 1)] = "Inner {:d}".format(k + 1)
    for leaf in "AB":
        for k in "123":
            out["Leaf {:s}{:s}".format(leaf, k)] = "Leaf {:s}{:s}".format(leaf, k)
    return out


def reference():
    """The normal flower rigged by flower_steps: the shut shape, and the
    bloom at each frame, by the bare file's names."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    parts = flower.build_flower(scene)
    bpy.context.view_layer.update()
    mapping = names_of_reference()
    shut = {bare: world_points(bpy.data.objects[ref]) for bare, ref in mapping.items()}
    run_headless.run(flower.flower_steps(parts, 150), scene=scene)
    bloom = {}
    for frame in FRAMES:
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        bloom[frame] = {bare: world_points(bpy.data.objects[ref]) for bare, ref in mapping.items()}
    return shut, bloom


# ---------------------------------------------------------------------------
# what a user does

def select(*objects, active=None):
    """Click the objects in the Outliner: these, and only these, selected."""
    layer = bpy.context.view_layer
    for obj in layer.objects:
        obj.select_set(False)
    for obj in objects:
        obj.select_set(True)
    layer.objects.active = active or objects[0]


def local_turn_expected(obj, degrees):
    return obj.matrix_world @ Matrix.Rotation(math.radians(degrees), 4, "X")


def same_matrix(a, b, tolerance=1e-5):
    return max(abs(x - y) for ra, rb in zip(a, b) for x, y in zip(ra, rb)) < tolerance


def type_field(obj, field, shut, value, shortcut=False):
    """Click the part, then type into a field of the Properties editor >
    Object tab > Transform (or, with `shortcut`, use R X X over the 3D view).
    Checks what a user relies on: the field starts at the number the guide
    says, the part's rotation is XYZ Euler at scale 1 (nothing can shear), and
    Rotation X turns the part about its own local X, hanging from another
    part or not."""
    select(obj)
    assert obj.rotation_mode == "XYZ", obj.name
    assert tuple(obj.scale) == (1.0, 1.0, 1.0), obj.name
    now = {"Rotation X": math.degrees(obj.rotation_euler.x), "Location Z": obj.location.z,
           "Rotation Z": math.degrees(obj.rotation_euler.z)}[field]
    assert abs(now - shut) < 1e-6, "{} {} is {} not {}".format(obj.name, field, now, shut)
    bpy.context.view_layer.update()
    before = obj.matrix_world.copy()
    if field == "Rotation X":
        if shortcut:
            assert bpy.ops.transform.rotate(value=math.radians(value), orient_axis="X",
                                            orient_type="LOCAL",
                                            constraint_axis=(True, False, False)) == {"FINISHED"}
        else:
            obj.rotation_euler.x = math.radians(value)
        bpy.context.view_layer.update()
        assert same_matrix(obj.matrix_world, before @ Matrix.Rotation(math.radians(value), 4, "X")), \
            "{} did not turn about its own X".format(obj.name)
    elif field == "Location Z":
        obj.location.z = value
        bpy.context.view_layer.update()
        assert same_matrix(obj.matrix_world, Matrix.Translation((0, 0, value - shut)) @ before)
    elif field == "Rotation Z":
        obj.rotation_euler.z = math.radians(value)
        bpy.context.view_layer.update()
        assert same_matrix(obj.matrix_world, before @ Matrix.Rotation(math.radians(value - shut), 4, "Z"))
    else:
        raise ValueError(field)


def rig():
    return bpy.context.scene.rigmoves_rig


# ---------------------------------------------------------------------------
# what the guide asks of the user, counted: clicks on objects, values typed or
# chosen, buttons pressed. Opening a dialog is the press of its button; its OK
# is not a press of its own. Not counted: moving the view, opening a section,
# the keys that play it.

DONE = {"clicks": 0, "typed": 0, "presses": 0, "numbers": 0}   # numbers: Leads and Delays


def click(*objects, active=None):
    """Click objects in the Outliner (the first, then Ctrl+click the others)."""
    DONE["clicks"] += len(objects)
    select(*objects, active=active)


def typed(number=False):
    """A value typed or chosen: a number, a dropdown, a tick."""
    DONE["typed"] += 1
    DONE["numbers"] += bool(number)


class Dialogs:
    """What Ring's and Spread's dialogs show when they open, as Blender does
    it, so that a value counts as typed only when it is not there already.

    A property that is not SKIP_SAVE opens with the value it was last
    confirmed with - Blender keeps those for the session, so the second Ring
    opens with the numbers of the first - and with its default the first time.
    (Not when a Python script opens the dialog: that is how this was found
    out, in a real window.) Spread's SKIP_SAVE fields are filled in by its
    own invoke: the order that suits the move, a first and last, and a step
    sized to fit the parts."""

    def __init__(self):
        self.last = {}              # operator -> {property: value} as last confirmed
        self.history = []           # (operator, fields changed, shown, properties) of each press

    @staticmethod
    def own(operator):
        """The dialog's own properties: not the hidden ones a button sets."""
        return [p for p in operator.get_rna_type().properties if not p.is_hidden]

    def shows(self, operator, move, what=None):
        kept = self.last.get(operator.idname_py(), {})
        shown = {p.identifier: kept[p.identifier] if p.identifier in kept and not p.is_skip_save
                 else p.default for p in self.own(operator)}
        if operator.idname_py() == "rigmoves.spread":
            assert what == "DELAY", "the replays press Spread on the Timing header only"
            shown["order"] = "CHAIN" if any(p.follows for p in move.parts) else "AXIS"
            shown["first"], shown["last"], shown["start"] = 0.0, 0.5, 0.0
            groups = rigmoves.spread_groups(bpy.context, move, what, shown["only_selected"])
            ranks = rigmoves.spread_ranks(rig(), move, groups, what, shown["order"], shown["axis"],
                                          shown["both_ways"], shown["seed"])
            shown["step"] = rigmoves.sized_step(what, max(ranks.values()))
        return shown

    def confirm(self, operator, shown, properties):
        self.last[operator.idname_py()] = {
            p.identifier: properties.get(p.identifier, shown[p.identifier])
            for p in self.own(operator) if not p.is_skip_save}


DIALOGS = Dialogs()


def press(operator, **properties):
    """Press a panel button. For Ring and Spread this is the button that opens
    the dialog, the dialog filled in and OK: only the fields that differ from
    what the dialog shows were touched by the user."""
    DONE["presses"] += 1
    name = operator.idname_py()
    if name in FIELDS:
        shown = DIALOGS.shows(operator, rig().rigmoves.moves[properties.get("index", 0)],
                              properties.get("what"))
        fields = [key for key, value in properties.items() if key in shown and value != shown[key]]
        DONE["typed"] += len(fields)
        DONE["numbers"] += len([key for key in fields if key in NUMBERS])
    result = operator(**properties)
    assert result == {"FINISHED"}, (name, properties, result)
    if name in FIELDS:
        DIALOGS.confirm(operator, shown, properties)
        DIALOGS.history.append((name, fields, shown, properties))
    return result


def pose(tables, shortcut=False):
    """Step 3: click each part (once for the core's two fields), type into its
    fields."""
    last = None
    for name, field, shut, value in pose_rows(tables):
        if name != last:
            DONE["clicks"] += 1
        last = name
        typed()
        type_field(bpy.data.objects[name], field, shut, value, shortcut)


def long_way_counts(tables):
    """What FLOWER_STEPS.md asks of the user, worked out from its own tables
    and not by doing it: (object clicks, values typed or chosen, buttons
    pressed, of the values the Lead and Delay numbers). replay_guide.py does
    it and counts; the two must agree."""
    poses = tables["Pose"]
    columns = cheat_headers()["Ring"]
    dialogs, fields, numbers = Dialogs(), 0, 0
    operator = bpy.ops.rigmoves.ring
    for row in tables["Ring"]:
        _part, properties, _words = ring_properties(columns, row)
        shown = dialogs.shows(operator, None)
        changed = [key for key, value in properties.items() if value != shown[key]]
        fields += len(changed)
        numbers += len([key for key in changed if key in NUMBERS])
        dialogs.confirm(operator, shown, properties)
    delays = len([r for r in tables["Delay"] if float(r[1]) != 0.0])      # Outer Leader stays 0
    clicks = 9 + len({row[1] for row in poses}) + len(tables["Ring"])     # New Move, each part posed, each Ring
    values = len(tables["Follows"]) + len(poses) + fields + delays + 2    # + Ease, Frames
    presses = 4 + len(tables["Ring"])                                     # New Move, Record, Build, Animate, each Ring
    return clicks, values, presses, numbers + delays


# ---------------------------------------------------------------------------
# checking the guide's text against what the add-on does

def check_install_text(check, text, version):
    """The install paragraph names the version the guides were written for
    and the Blender it needs, and says what an older CopyThat shows."""
    flat = " ".join(text.split())
    check(version >= OLDEST, "CopyThat {:s} is {:s} or newer".format(
        ".".join(str(v) for v in version[:3]), ".".join(map(str, OLDEST))))
    for words in ("0.18.1 or newer", "CopyThat-0.18.x.zip", "Blender 4.5 or newer", "First Lead", "Lead step"):
        check(words in flat, "the guide says: " + words)


def quoted_reports(text):
    """Every report the steps quote - 'the report "..."' - before the cheat sheet."""
    steps = " ".join(text[:text.index("## Cheat sheet")].split())
    return re.findall(r'[Rr]eport[^"]{0,25}"([^"]+)"', steps)


def check_reports(check, text, notes, at_least):
    """Each quoted report is part of one the add-on said while the guide was followed."""
    said = [" ".join(words.split()) for _step, words in notes]
    quoted = quoted_reports(text)
    print("reports quoted in the steps:", len(quoted))
    for quote in quoted:
        check(any(quote in words for words in said), "the add-on said: " + quote)
    check(len(quoted) >= at_least, "the steps quote at least {:d} reports ({:d} found)".format(
        at_least, len(quoted)))


def dialog_tables(text):
    """The Field | Set to tables of the steps, before the cheat sheet, in the
    order the guide gives them: each a list of (field, what the cell says)."""
    steps = text[:text.index("## Cheat sheet")]
    found, rows = [], None
    for line in steps.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            rows = None
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if cells[0] == "Field":
            rows = []
            found.append(rows)
        elif rows is not None and not set("".join(cells)) <= set("-: "):
            rows.append((cells[0], cells[1]))
    return found


def check_dialogs(check, text, expected):
    """The table of each dialog in the steps is what the user needs, in the
    order the dialogs were pressed. `expected` is, for each, what the cheat
    sheet says for each property. Each table
      * lists every row the dialog shows, and nothing else;
      * says what the cheat sheet says in each row it has a value for;
      * puts in bold exactly the rows the user changes - the others are left
        as they are, which is only right if the dialog really shows that;
      * says "it shows N" only where the dialog shows N."""
    tables = dialog_tables(text)
    check(len(tables) == len(DIALOGS.history), "the steps have one Field | Set to table for each of "
          "the {:d} dialogs ({:d} found)".format(len(DIALOGS.history), len(tables)))
    if len(tables) != len(DIALOGS.history):
        return
    for number, (rows, (name, fields, shown, _properties), (_name, words)) in enumerate(
            zip(tables, DIALOGS.history, expected), 1):
        labels = FIELDS[name]
        title = "dialog {:d} ({:s})".format(number, name)
        check([field for field, _cell in rows] == list(labels),
              "{:s}: the table lists {}".format(title, ", ".join(labels)))
        bold = {labels[field] for field, cell in rows if "**" in cell and field in labels}
        check(bold == set(fields), "{:s}: the steps put in bold {}; the user changes {}".format(
            title, sorted(bold), sorted(fields)))
        for field, cell in rows:
            prop = labels.get(field)
            plain = cell.replace("**", "").strip()
            if prop in words:
                check(plain.startswith(words[prop]), "{:s}: {:s} says {:s} ({:s})".format(
                    title, field, words[prop], plain))
            seen = re.search(r"it shows (-?[0-9.]+)", plain)
            if seen:
                check(prop is not None and float(seen.group(1)) == float(shown[prop]),
                      "{:s}: {:s} says it shows {:s}; the dialog shows {}".format(
                          title, field, seen.group(1), shown.get(prop)))


# ---------------------------------------------------------------------------
# the steps

def replay(tables, log, shortcut=False):
    scene = bpy.context.scene
    objects = bpy.data.objects
    leader, inner_leader = objects["Outer Leader"], objects["Inner Leader"]
    leaves = [objects["Leaf {:s}{:d}".format(side, k)] for side in "AB" for k in (1, 2, 3)]

    # 1. Select the nine parts and press New Move.
    click(leader, inner_leader, objects["Core"], *leaves, active=leader)
    assert len(bpy.context.selected_objects) == 9
    press(bpy.ops.rigmoves.new_move)
    move = rig().rigmoves.moves[0]
    log("1 New Move", rig().rigmoves.report)

    # 2. Follows: the leaves hang from each other, each picked from a dropdown.
    for part, follows in tables["Follows"]:
        typed()
        move.parts[part].follows = follows
        assert move.parts[part].follows == follows, (part, follows)

    # 3. Pose the flower open, one field at a time.
    pose(tables, shortcut)

    # 4. Record After.
    press(bpy.ops.rigmoves.record, index=0, which="AFTER")
    log("4 Record After", rig().rigmoves.report)

    # 5. Ring: click the leader (a plain click), press Ring..., fill in the
    # dialog, OK. The outer petals, then the inner.
    columns = cheat_headers()["Ring"]
    made, expected = {}, []
    for row in tables["Ring"]:
        name, properties, words = ring_properties(columns, row)
        click(objects[name])
        before = {o.name for o in objects}
        press(bpy.ops.rigmoves.ring, index=0, **properties)
        made[name] = sorted(o.name for o in objects if o.name not in before)
        expected.append(("rigmoves.ring", words))
        log("5 Ring " + name, rig().rigmoves.report)

    # 6. Timing: the Delays, typed into each part's field (Outer Leader stays 0).
    for name, delay in tables["Delay"]:
        if float(delay) != 0.0:
            typed(number=True)
        move.parts[name].start = float(delay)

    # 7. Ease, 8. Build Sliders.
    other = dict(tables["Other"])
    typed()
    move.ease = {"Smooth": "SMOOTH", "Even speed": "LINEAR"}[other["Ease"]]
    press(bpy.ops.rigmoves.build)
    log("8 Build Sliders", rig().rigmoves.report)

    # 9. Frame 1, Frames 150, Animate.
    scene.frame_set(1)
    typed()
    move.play_frames = int(other["Frames"])
    press(bpy.ops.rigmoves.animate, index=0)
    log("9 Animate", rig().rigmoves.report)
    scene.frame_set(1)
    return move, made, expected


def main():
    render = "--no-render" not in sys.argv
    shortcut = "--shortcut" in sys.argv
    rigmoves.register()
    version = rigmoves.bl_info["version"]
    print("CopyThat", ".".join(str(v) for v in version), "from", os.path.dirname(rigmoves.__file__))
    failures = []

    def check(ok, text):
        print(("  ok   " if ok else "  FAIL ") + text)
        if not ok:
            failures.append(text)

    with open(GUIDE, encoding="utf-8") as handle:
        guide_text = handle.read()
    check_install_text(check, guide_text, version)
    tables = cheat_sheet()
    print("cheat sheet:", {k: len(v) for k, v in tables.items()})
    check(cheat_headers()["Ring"] == RING_COLUMNS, "the Ring table's columns are " + ", ".join(RING_COLUMNS))
    in_steps = pose_table_in_the_steps()
    in_sheet = [(name, field, value) for name, field, _shut, value in pose_rows(tables)]
    assert in_steps == in_sheet, "step 3 and the cheat sheet disagree:\n{}\n{}".format(in_steps, in_sheet)
    print("step 3 and the cheat sheet agree on all {:d} poses".format(len(in_sheet)))

    shut, bloom = reference()
    print("reference built and rigged with flower_steps(parts, 150)")

    bpy.ops.wm.open_mainfile(filepath=BLEND)
    scene = bpy.context.scene
    names = sorted(names_of_reference())
    assert not any(hasattr(o, "rigmoves") and len(o.rigmoves.moves) for o in bpy.data.objects
                   if o.type == "ARMATURE"), "the bare file has CopyThat data"
    assert not [o for o in bpy.data.objects if o.type == "ARMATURE" or o.modifiers or o.constraints], \
        "the bare file has a rig, modifiers or constraints"
    bpy.context.view_layer.update()
    start = snapshot(scene, names, frames=(1,))[1]
    gap = max(difference(start[n], shut[n]) for n in names)
    print("bare file against the normal flower, shut: largest difference {:.2e}".format(gap))

    notes = []
    move, made, expected = replay(tables, lambda step, text: notes.append((step, text)), shortcut)
    for step, text in notes:
        print("  {:22s} {:s}".format(step, text))

    # What the guide asks of the user, counted as it was done, and worked out
    # from the tables.
    print("this guide asks for {:d} object clicks, {:d} values typed or chosen, {:d} buttons pressed = {:d}; "
          "{:d} of the values are Lead and Delay numbers".format(
              DONE["clicks"], DONE["typed"], DONE["presses"],
              DONE["clicks"] + DONE["typed"] + DONE["presses"], DONE["numbers"]))
    counted = long_way_counts(tables)
    check((DONE["clicks"], DONE["typed"], DONE["presses"], DONE["numbers"]) == counted,
          "done as the guide says, that is what its tables add up to: {}".format(counted))

    # What Ring did: it made nothing, and took up the petals that stand there.
    leads = dict(tables[LEAD_TABLE])
    taken = {leader: [name for name in leads if name.startswith(leader.split()[0] + " ")]
             for leader in ("Outer Leader", "Inner Leader")}
    check(made == {"Outer Leader": [], "Inner Leader": []}, "Ring made nothing new: {}".format(made))
    for leader, riders in taken.items():
        got = sorted(p.name for p in move.parts if p.leader == leader)
        check(got == sorted(riders), "{:s} has {:d} riders: {:s}".format(leader, len(got), ", ".join(got)))
    check(len(move.parts) == 21 and len([p for p in move.parts if p.leader]) == 12,
          "21 parts in the move, 12 of them riders")
    wrong = {name: move.parts[name].lead for name in leads if move.parts[name].lead != int(leads[name])}
    check(not wrong, "every Lead is the one the guide lists (wrong: {})".format(wrong))
    print("   Leads:", {p.name: p.lead for p in move.parts if p.leader})
    outer = dict(notes)["5 Ring Outer Leader"]
    left_out = re.search(r"Left out: (.*?)\. Leads step", outer)
    named = re.findall(r"'([^']+)' is not a copy of 'Outer Leader'", left_out.group(1)) if left_out else []
    check(bool(named) and all(n.startswith("Inner ") for n in named),
          "what the outer Ring left out are inner petals, as the steps say: " + ", ".join(named))

    check_reports(check, guide_text, notes, 7)
    check_dialogs(check, guide_text, expected)

    got = snapshot(scene, names)
    worst, where = 0.0, None
    for frame in FRAMES:
        top = max((difference(got[frame][n], bloom[frame][n]), n) for n in names)
        print("frame {:3d}: largest difference {:.2e}  ({:s})".format(frame, top[0], top[1]))
        if top[0] > worst:
            worst, where = top[0], (frame, top[1])
    print("LARGEST DIFFERENCE {:.2e} at frame {:d}, {:s}   (limit {:.0e})".format(
        worst, where[0], where[1], LIMIT))
    ok = worst < LIMIT and gap < 1e-5 and not failures
    print("REPLAY MATCHES" if ok else "REPLAY DIFFERS")
    if failures:
        print("FAILED {:d}:".format(len(failures)))
        for text in failures:
            print("  " + text)

    # How near the camera's focus is to the real core, at the keyed frames.
    core = bpy.data.objects["Core"]
    camera = scene.camera
    off = 0.0
    for frame in (1, 56, 101, 126, 151):
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        top = sorted((Vector(p) for p in world_points(core)), key=lambda p: -p.z)[:200]
        middle = sum(top, top[0] * 0.0) / len(top)
        want = (middle - camera.matrix_world.translation).length
        off = max(off, abs(want - camera.data.dof.focus_distance))
    print("camera focus against the evaluated core: largest difference {:.3f} m".format(off))

    if render:
        scene.frame_set(120)
        cycles = scene.cycles
        cycles.device, cycles.samples = "CPU", 16
        scene.render.resolution_percentage = 50
        try:
            scene.render.image_settings.media_type = "IMAGE"
        except (AttributeError, TypeError):
            pass
        scene.render.image_settings.file_format = "PNG"
        scene.render.filepath = STILL
        bpy.ops.render.render(write_still=True)
        print("rendered frame 120 to", STILL)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
