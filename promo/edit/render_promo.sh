#!/usr/bin/env bash
# Renders the promo film: After Effects (aerender) makes the frames, ffmpeg encodes them, and a contact
# sheet and one still of each shot are written for looking at.
#
#   bash promo/edit/render_promo.sh
#
# It needs After Effects 2025 (aerender.exe) and ffmpeg. The project's render queue holds one item, the main
# comp "CopyThat Promo", which writes dist/promo/edit_frames/promo_#####.png (8 bits; the project itself
# works in 16 and dithers down). The film goes to dist/promo/CopyThat_promo_1440p.mp4: 2560x1440, 30 fps,
# H.264 High, crf 14, yuv420p, bt709, faststart, no audio.
#
# Environment variables:
#   AERENDER   the path of aerender.exe
#   AE_MFR     multi-frame rendering, "ON 100" (all cores) by default; "ON 50" or "OFF" if memory is short
#   REVIEW     the folder for the contact sheet and the stills (default dist/promo/edit_review)
#   SKIP_AE=1  do not render: encode the frames already in dist/promo/edit_frames
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
PROMO="$ROOT/dist/promo"
FRAMES="$PROMO/edit_frames"
FILM="$PROMO/CopyThat_promo_1440p.mp4"
REVIEW="${REVIEW:-$PROMO/edit_review}"
AERENDER="${AERENDER:-/c/Program Files/Adobe/Adobe After Effects 2025/Support Files/aerender.exe}"
FRAME_COUNT=1830                                  # 61 s at 30 fps

win() { cygpath -w "$1" 2>/dev/null || echo "$1"; }

if [ "${SKIP_AE:-0}" != "1" ]; then
    # Never start a second After Effects on top of one that is open (it may be somebody's own work).
    if tasklist 2>/dev/null | grep -qi "AfterFX.exe"; then
        echo "After Effects is open: close it (or run again with SKIP_AE=1 to only encode)." >&2
        exit 2
    fi
    mkdir -p "$FRAMES"
    rm -f "$FRAMES"/promo_*.png
    echo "== aerender: $(date +%H:%M:%S)"
    # shellcheck disable=SC2086   # AE_MFR is two words on purpose ("ON 100", "OFF")
    "$AERENDER" -project "$(win "$HERE/CopyThat_promo.aep")" -mem_usage 40 70 -mfr ${AE_MFR:-ON 100}
fi

count=$(ls "$FRAMES"/promo_*.png 2>/dev/null | wc -l)
if [ "$count" -ne "$FRAME_COUNT" ]; then
    echo "expected $FRAME_COUNT frames in $FRAMES, found $count" >&2
    exit 1
fi
first=$(ls "$FRAMES"/promo_*.png | sed -n 1p)   # not head -1: with pipefail its SIGPIPE ends the script
first=${first##*promo_}
first=$((10#${first%.png}))

echo "== ffmpeg: $(date +%H:%M:%S)"
# The frames are sRGB pictures: the BT.709 matrix and tags say how the encoder read them
ffmpeg -y -v error -stats -framerate 30 -start_number "$first" -i "$FRAMES/promo_%05d.png" \
    -vf "scale=out_color_matrix=bt709:out_range=tv,format=yuv420p" \
    -c:v libx264 -profile:v high -preset slow -crf 14 \
    -color_primaries bt709 -color_trc bt709 -colorspace bt709 -color_range tv \
    -movflags +faststart -an "$FILM"

# For review: a contact sheet (one frame a second, left to right, 8 to a row) and one still of each shot
mkdir -p "$REVIEW"
ffmpeg -y -v error -i "$FILM" -vf "fps=1,scale=480:-1:flags=area,tile=8x8:padding=4:color=0x202020" \
    -frames:v 1 "$REVIEW/contact_sheet.png"
# the shot's time (s) where its card or caption is on screen: bloom, turn, push-in, slider, title, demo
# (a dialog), match cut (the tag), end card
n=0
for t in 0.9 2.4 3.9 6.5 9.4 26.6 55.6 59.6; do
    n=$((n + 1))
    frame=$(awk -v t="$t" -v f="$first" 'BEGIN { printf "%d", t * 30 + f + 0.5 }')
    ffmpeg -y -v error -i "$FRAMES/promo_$(printf %05d "$frame").png" -vf format=rgb24 -frames:v 1 \
        "$REVIEW/shot_$n.png"
done

ffprobe -v error -show_entries format=duration,size -of default=nw=1 "$FILM"
echo "film: $FILM"
echo "review: $REVIEW"
