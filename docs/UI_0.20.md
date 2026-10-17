# CopyThat 0.20: a branded, cleaner sidebar panel

NemVe3D asked (2026-10-17) for a panel that looks better than the current
one and feels like CopyThat. The promo shows this panel, so it comes first.

The reference is Auto Unwrap's sidebar (3DRedBox):
- a branded header: a logo, the name, a one-line subtitle;
- big primary buttons with icons;
- compact secondary rows;
- UPPERCASE section headers with an icon, which collapse;
- segmented choices with the active one lit;
- a progress bar;
- a dim footer with counts, credit and version.

Ours keeps CopyThat's identity: gold #C9A76A, the flower, "Record a move.
Get a slider."

## Hard constraints
- Blender's own Python UI only: `Panel` and sub-panels (`bl_parent_id`),
  `box` / `row` / `column` / `split`, `scale_y`, `alignment`, enums with
  `expand=True`, `layout.progress` (4.0+), and icons from
  `bpy.utils.previews`. No GPU-drawn UI.
  - Buttons cannot be coloured gold; the gold comes from our icons.
- **Behaviour does not change.** No operator, property or report changes,
  except new UI-state booleans for new collapsible sections. Those are
  stored per move, default collapsed, with a comment saying why.
- **Every button keeps its label text.** The guide and the tests name them.
  If a label truly must change, change the guide (`rigmoves/README.md`) and
  the tests with it. The guide must stay true to what the panel shows: check
  every passage that describes the panel's layout or order.
- Reads well at the sidebar's default width at UI scale 1.0, and at 1.33.
  Keep the `fitted()` name-cutting working.
- Works on Blender 4.5, 5.0 and 5.2.

## The design
1. **Header.**
   - The panel header shows the CopyThat logo, a custom gold icon, via
     `draw_header`, with the title "CopyThat".
   - The first line inside is a dim subtitle: "Record a move. Get a
     slider."
2. **Rig line.** A compact row: the rig icon and the rig's name, and
   right-aligned and dim, "21 parts · 1 slider".
3. **Empty state** (no move yet): a one-line hint and a big primary New Move
   button (`scale_y` 1.5, our icon).
4. **Each move**, in a box:
   - **Its header row:** expand arrow, name, remove x, as today.
   - **First inside:** the move's slider, made prominent: full width,
     `scale_y` about 1.35, with its key button beside it.
   - **Then Before and After** as two clear rows, each with our icon, the
     Record button and the eye.
   - **Then the sections, as collapsible rows,** each an UPPERCASE label
     with an icon and a chevron. Use the existing expanders where they
     exist; add booleans where needed:
     - PARTS & PIVOT: Parts, Pivot (Origin | Cursor | Base, segmented);
     - PATH: Smooth / Even (segmented if it is an enum), Curve the Path,
       Edit the Curve, Straighten, Step in between, Paths;
     - TIMING: the Delay / Done list, Spread...;
     - COPIES: Ring..., Riding along (n), Mirror;
     - CHAINS: Follows, Make Chain, Curl;
     - ANIMATE: Frames, Animate, the key button.
   - Order the rows the way a user works through them.
5. **Primary actions** under the moves:
   - a big Build Sliders (`scale_y` about 1.6, our build icon);
   - under it, Pause | To Before;
   - New Move as a secondary button with a + icon when moves exist.
6. **The report:** a collapsible REPORT box, with an info or warning icon.
   It is open by default when the last report is a warning.
7. **Footer:** dim and small (`scale_y` 0.8),
   "CopyThat <version from bl_info> · NemVe3D".
8. **Spacing:** `separator(factor=0.5)` between groups; aligned groups for
   buttons that belong together; no orphan hints. Keep each hint to one line
   and only where it helps.

## The icons (our identity)
- **The set:** about 16 gold line icons, #C9A76A on transparent, PNG
  64x64. Draw them with Pillow at 4x and downsample, or draw SVG and
  rasterise. Same stroke weight throughout, simple and readable at 16 px:
  - logo: a flower mark or "CT" with a slider;
  - new move (+), record before, record after, build (play in a rounded
    square), slider;
  - ring, spread, chain, curl, curve, steps, mirror, combine, animate (a
    keyframe diamond), timing, pivot.
- **The files:** `rigmoves/icons/`.
  - Load them in `register` with one `bpy.utils.previews` collection, and
    free it in `unregister`.
  - Fall back to built-in icons if a file is missing.
  - Make sure `tools/build_zip.py` ships them, and that Blender's extension
    validator accepts the zip.

## Checking it
- **Real-window screenshots:** use `promo/tools/window_screenshots.py` (it
  needs `-- <addon folder> <out folder>`, and widens the sidebar by a
  simulated drag), at UI scale 1.0 and 1.33, in these states:
  1. empty;
  2. one move, unbuilt;
  3. built, with riders and timing;
  4. after Ring;
  5. a warning report.
- **Look at them yourself:** text is not clipped, the hierarchy is clear,
  the icons are crisp. Put the final set in the scratchpad's
  `ui_020_review/` for the planner.
- **Tests:** the whole suite on 4.5, 5.0 and 5.2 with
  `bash tools/test_all_blenders.sh`, and ruff. Update the drawing tests that
  pin the old layout. Add one test that the icons load, and that the panel
  draws in every state above without error.
