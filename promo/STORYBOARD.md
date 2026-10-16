# CopyThat promo v2 - storyboard (2560x1440, 30 fps, about 60 s)

For artists. Hook first, proof second, then the workflow in a real Blender
window, then the payoff and the store. Everything at 2560x1440 (YouTube's
"1440p (2K)"), 30 fps, H.264 high quality, yuv420p, bt709, faststart.

Look: the dark studio and gold of the flower; type is Inter Display Light for
statements and Inter Medium for captions (shipped in promo/cards/fonts/); one
accent colour, gold #C9A76A; warm white #F2EADB. Never the Blender logo as a
design element (store rule for images; kept for the video too). Cuts land on a
steady 0.5 s grid so music can be laid under later (no music is made here: the
user adds a track, e.g. from YouTube Studio's Audio Library).

## Shot list

| # | Time | Picture | Text on screen |
|---|---|---|---|
| 1 | 0.0-1.5 | Cycles: the bloom, fast (render frames sped so the bud bursts open) | **21 moving parts.** |
| 2 | 1.5-3.0 | Cycles: the open flower turning, the core glowing | **No rig to build.** |
| 3 | 3.0-4.5 | Cycles: the camera pushes in on the open flower | **One slider.** |
| 4 | 4.5-8.0 | Blender window (recording): the finished flower in the viewport; the Play slider in the CopyThat panel dragged 0 to 100%: it blooms | lower third: "This is Blender. This is the whole rig." |
| 5 | 8.0-10.0 | Title card (short): CopyThat wordmark, "Record a move. Get a slider." | - |
| 6 | 10-52 | Blender window: the fast flower rigged from scratch (see "The recording"), tightly cut, sped where nothing new happens | lower thirds per beat (below) |
| 7 | 52-57 | Match cut: the viewport bloom (camera view) dissolves into the same frame of the Cycles render, which plays on | small: "Rendered in Cycles" |
| 8 | 57-61 | End card over the render's last frames: CopyThat / Record a move. Get a slider. / **Now on Superhive** / by NemVe3D · creators.sa/nemve | - |

Lower thirds for shot 6, one per beat, each 2-4 s, white on a dark
translucent bar with a thin gold rule (the cards' style):
1. "Select the parts. New Move."
2. "Make Chain: the leaf's joints hang from one another."
3. "Pose it once. Record."
4. "Ring: one petal becomes a ring of eight."
5. "Ring the inner petals and the leaf."
6. "Spread: the timing, in one go."
7. "Build: one slider plays all 21 parts."
8. "Animate: keyed over 150 frames."

## The recording (shot 4 and shot 6)

Recorded here, on the user's PC, from their Blender 5.2.1 with the repo's
CopyThat: a window of exactly 2560x1440 (no title bar), interface scale 1.33
(it looks like Blender at 1080p, only sharper), the default theme and layout,
captured with ffmpeg's gfxcapture (the window alone, no cursor, 30 fps,
near-lossless). The demo script drives it; nobody touches the PC.

What the script shows, from the FAST flower (one outer petal, one inner petal,
the core, one leaf of three segments - FLOWER_FAST.md's file and steps):
- the 3D view in Solid shading with the parts' own colours, cavity and soft
  shadows; the sidebar open on the CopyThat tab, wide enough to read; Outliner
  and Properties as Blender has them;
- each beat stays on screen long enough to read, and the panel visibly changes
  (the move's box appears, Follows fills in, Riding along (7) appears...);
- the Ring and Spread dialogs open on screen, filled in, for about 1.5 s, and
  are confirmed (the viewer sees exactly what to set);
- poses glide (eased), the slider slides;
- at the end: Animate, the camera view, Play: the bloom in the viewport, from
  frame 1, so shot 7 can dissolve into the render at the same frame.
- The script writes a timeline (JSON, seconds from the end of its countdown) of
  every beat: its name, start, end, and what is on screen - the edit cuts and
  captions from it, so nothing is timed by hand.
- Shot 4 is recorded separately: the finished rig (built by the script, no
  captions), the slider dragged slowly 0 to 1 over about 3 s.

## The edit (an assembly script, ffmpeg)

From: the hook renders (the outro's 1440p frames, or a separate close-up render),
the recording(s) with their timeline JSON, the card PNG sequences (title, lower
thirds, statements, end card - rendered by render.js at 2560x1440 with alpha),
and the outro frames. One script makes the whole film from an edit list (cuts,
speeds, dissolves, overlays) so it can be re-made after any change, and writes
contact sheets (one frame per second) for review. Output:
dist/promo/CopyThat_promo_1440p.mp4 (+ the contact sheet). No audio track (or a
silent one), ready for music.
