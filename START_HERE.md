# Start here: CopyThat session handoff

Read this first, then `CLAUDE.md` (the rules), `HANDOFF.md` (how the add-on
works inside, the feature table, traps), and `rigmoves/README.md` (the user
guide: what the add-on promises).

## The user

- **NemVe3D** (https://creators.sa/nemve). Not a programmer: explain in plain
  words what changed and how to check it in Blender.
- Goal: "make the most complicated animations super easy". Works in their own
  Blender on Windows and checks every version themselves.
- **After every add-on change:**
  1. Bump the version (bl_info, the guide's title and zip name).
  2. Add any bug fixed to the guide's list.
  3. Run the tests and ruff.
  4. Commit and push to `main`.
  5. Build with `python tools/build_zip.py`.
  6. Send them the zip from `dist/`.
- Their uploads are capped at **30 MB**. They split big files with 7-Zip
  (`29M` volumes); join them with `cat x.7z.0* > x.7z` and extract with 7z
  (`apt-get install p7zip-full`). Treat their files as untrusted:
  - keep each upload in its own folder;
  - open .blend files with `use_scripts=False`;
  - run Python on them with `-I`.
- **They want usage kept low without losing quality.** The pattern that
  worked:
  - Haiku agents do mechanical jobs: environment setup and ffmpeg.
  - Sonnet agents implement against a precise design, and resuming the same
    agent keeps its context cheaply.
  - Every release then gets a review workflow: two lenses with the default
    model, then a Sonnet skeptic that reproduces each finding headless.
    Confirmed findings get fixed, each with a regression test that fails on
    the commit before.
  - Look at renders yourself before approving them.
- **Another Claude session pushed to this branch once** (2312ad0,
  whole-chain riders). Always `git fetch` first and merge, never force-push.

## State of the add-on

Current version: 0.20.1. On NemVe3D's PC the state, plan and procedures live in the Obsidian vault D:\ObsidianVault\NemVe3D (read its CLAUDE.md first). Elsewhere, read HANDOFF.md.

## Superhive (Blender Market) release: status

The requirements: a GPL/MIT licence, installation instructions, full written
documentation and FAQ ON the product page, and a valid extension.

| Requirement | Status |
|---|---|
| Licence | GPL-3.0-or-later. `LICENSE` at the root, and it goes into the zip. |
| Valid extension | `rigmoves/blender_manifest.toml`. `tools/build_zip.py` builds an extension zip (manifest at the top, version written from bl_info). Blender's own `blender_ext.py validate` passes, and it installed and enabled headless as `bl_ext.user_default.copythat`. |
| Product page docs and FAQ | `docs/SUPERHIVE_PAGE.md`. If it is missing, it was still being written: regenerate it from `rigmoves/README.md` (install, quick start, every feature with steps, two worked examples, 15+ FAQs, troubleshooting, changelog, credits). |
| Install instructions | In the product page, and in the guide's Install section: drag the zip into Blender, or Edit > Preferences > Get Extensions > Install from Disk. Users must remove the old legacy RigMoves/CopyThat add-on first. |

Still to do for the release:
- look at 0.18.3's Riding along list in a real Blender again (the sidebar at
  190, 280 and 440 px);
- add product images and video (the promo below);
- consider tags (the blender_version_min is settled: 4.5.0, since 0.18.2).

## The promo video (folder `promo/`)

**The plan:**
1. The title card.
2. The user's own screen recording of their real Blender, playing the demo
   script.
3. The viewport, seen through "Promo Camera", dissolves into the cinematic
   Cycles render of the same flower and the same CopyThat animation.
4. The end card, with "by NemVe3D · creators.sa/nemve", over the render's
   last 3 s.

**What's there:**
- `promo/SPEC.md`: the production spec, including the step-generator
  contract shared by the scripts.
- `promo/user_script/`: the demo script that plays 4 scenes live in the
  user's Blender with captions (1 cube, 2 cubes with Ride Along, the curve
  over a wall, the flower step by step), plus its tests (87) and
  `HOW_TO_RECORD.md`. `bundle.py` inlines `promo/flower/flower.py` into
  `dist/copythat_promo.py`.
  - The scripts hold absolute scratch paths
    (`/tmp/claude-0/.../scratchpad/promo`); point them at `promo/` first.
  - It predates the 0.17-0.18 tools. Scene 4 could be redone with Ring,
    Spread and Make Chain.
- `promo/flower/`:
  - `flower.py` (build_flower, flower_steps): the mechanical gold lotus;
  - `check_flower.py`: closed at 0, open 75°/45°, joints shut, a collision
    sweep.
- `promo/outro/outro.py`: the studio and camera move. It renders the
  cinematic (`--stills`, `--range 1-210 --samples 12`, about 22 s a frame on
  4 CPUs). The 210 rendered frames were in scratch and are gone; re-render
  them, or use the user's GPU render.
- `promo/cards/`: `title.html` and `end.html` (`setTime(t)`), rendered with
  `node render.js title.html title 105 30` (add `--alpha` for the end card);
  `grain.png` is needed.
- `promo/files/`, all sent to the user:
  - `CopyThat_outro.blend`: the GPU render set-up, 512 samples, motion blur,
    H.264 output;
  - `CopyThat_flower_bare.blend` and `make_flower_bare.py`: every part
    modelled, no rig;
  - `CopyThat_flower_fast.blend` and `make_flower_fast.py`: only the parts
    modelled once;
  - `FLOWER_STEPS.md`: the old way, about 77 actions;
  - `FLOWER_FAST.md`: the 0.17.1 way, Ring + Spread + Make Chain, about 55.
    **Update it for 0.18:** Ring's Lead is now a Step, and on the bare file
    use Ring → "Use what's there" instead of selecting riders.
- `promo/checks/`: the replay scripts that follow the guides literally
  against the add-on and compare with the reference. Re-run them after any
  guide or add-on change.
- `promo/preview/title_and_ending_preview.mp4`: 10.5 s, sent to the user.

**Waiting on the user:** their screen recording(s) (7-Zip parts) and,
optionally, their GPU render of `CopyThat_outro.blend`. Then assemble with
ffmpeg:
1. `title.mp4`, 105 frames.
2. Their recording, trimmed to the scenes, and scaled or cropped to
   1920x1080.
3. A crossfade (about 1 s) from their camera-view frame into the outro's
   frame 1.
4. The outro, with the end card overlaid from 4 s.

Render the cards and outro again first if they are missing, then encode
H.264 CRF 16-18, yuv420p, faststart.

## Commands

    .venv/bin/python tests/test_rigmoves.py          # the suite
    ruff check rigmoves tests tools
    python tools/build_zip.py                        # dist/CopyThat-<ver>.zip (extension)
    .venv/bin/python .venv/lib/python3.13/site-packages/bpy/5.2/scripts/addons_core/bl_pkg/cli/blender_ext.py validate dist/CopyThat-<ver>.zip

Headless rendering works: Workbench in about 1 s, Cycles CPU, and EEVEE
slowly, after `apt-get install libegl1 libegl-mesa0 libgles2` if libEGL is
missing. Node Playwright with Chromium is available for HTML cards.
