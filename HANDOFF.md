# Handoff: where RigMoves stands (v0.14.4)

Read `CLAUDE.md` first. It covers the test and lint commands, the driver
rules, and the routine after every change: bump `bl_info["version"]` and
the guide's title and zip name, add the bug to the guide's list, run the
tests, build with `python tools/build_zip.py`, and send the user the zip
from `dist/`. Work on branch `claude/funny-hypatia-jnendi`. Don't open a
PR unless the user asks.

## What the user is building

RigMoves records Before/After (and step) poses of objects and builds one
control (a viewport handle plus a Play slider) that plays them. Features
so far:

- speeds per stretch
- riders (Lead and Mirror)
- pivots
- curved paths
- motion paths
- Animate over frames
- **Followers**: a part hangs from another part, like the joints of a
  finger (`Follows` dropdown per part)

The user tests every version in their own Blender and reported followers
not following (`Doesnwork.blend`). 0.14.1 fixed that. A review then found
nine more problems, and 0.14.2 fixes them.

## What 0.14.2 changed (0.14.3 adds the author credit, 0.14.4 closes open issue 1) (all in `rigmoves/__init__.py`)

- **`seen_poses()`** is used by Record. It reads each object part where it
  is *meant* to be.
  - A bound follower's object hangs from its leader's object, but the
    leader's bone deforms after that. So dragging the base of a *posed*
    finger shears the followers on screen.
  - Record walks the parts parents first. For each part it keeps how far
    the part was carried as an object (`carry`) and as seen (`change`).
  - A follower takes `change[leader] @ shown @ own`.
  - A follower whose bone already hangs from its leader's bone and that was
    only carried is **not** a drop. It keeps its own keys, which is the
    "kept" rule for untouched parts.
- **`stand_parts()`** puts objects back on Before (bound parts) or where
  they were seen (loose parts), in follow order with an update after
  each. Record and Show both use it.
- **Show** poses the bones, calls `ride_shown()`, then places loose parts
  with `shown_places()`. A loose follower with no After is shown carried
  by its leader.
- **`bind_loose`** takes bound, marked objects off a pending (loose)
  parent before standing it on Before. `hang_objects` re-hangs them. It now
  returns `(count, new_bone_names)`.
- **`apply_parents(..., new)`**:
  - Newly bound bones re-key only on their own keys, not on step frames.
  - A part with no `has_after` whose keys are all rest (`stands_still`)
    rides along, keyed as identity under its new parent.
- **`parent_pending`** also reports a follower whose object doesn't hang
  from its leader's object. That covers 0.14.0 files, and the panel then
  says "Build".
- **`recorded(AFTER)`**: for object moves it is `any(has_after)` or
  `path_moves`. Record sets `has_after` for object parts it keys at After.
  Build warns "After not recorded yet".
- **Panel**: the eye beside After shows whenever the path has an After
  key.

## Open issues (start here)

1. **Resolved in 0.14.4:** `test_new_followers_are_shown_carried_on_after`
   was wrong, not the add-on. There the tip is already bound (Set Pivot
   runs a Build) and its bone carries it, so the test set its object to
   the wanted pose instead of dragging it from where it is seen. The add-on
   recorded what was on screen, as it should. The test now drags it from
   where it is shown, and it passes.
2. **Not done yet:** check that each new regression test fails on
   `90ec17b`, which is 0.14.1. Copy that commit's `rigmoves/__init__.py`
   into a temporary package and run the new tests against it. The new
   tests are:
   - `TestFollowers`: `test_turning_the_base_*`,
     `test_followers_listed_first_*`, `test_a_follower_not_hung_*`
   - all of `TestFollowersAdded`
3. **Not done yet:** a review pass of 0.14.2. Earlier versions were
   reviewed by a workflow with one reviewer per lens and a skeptic that
   reproduced each finding headlessly. Scratch scripts are under the
   session scratchpad and will be gone. Write new ones under
   `/tmp/.../scratchpad`.
4. The rough edges are listed in `rigmoves/README.md` under "Known rough
   edges". The main one: the on-screen shear while dragging the base of a
   posed finger. Record gets it right, but the screen doesn't.

## How to test

    .venv/bin/python tests/test_rigmoves.py      # 83 tests, all pass
    ruff check rigmoves tests tools
    python tools/build_zip.py                    # dist/RigMoves-0.14.4.zip
