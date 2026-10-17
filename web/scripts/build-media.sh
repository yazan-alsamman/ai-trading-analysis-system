#!/usr/bin/env bash
# Builds the website's cinematic video loops and posters from licensed source clips.
#
#   bash scripts/build-media.sh <source-dir>
#
# Sources (download the 1080p files into <source-dir>; licences in docs/CINEMATIC_MOTION_IMPLEMENTATION.md):
#   Coverr (free for commercial use, no attribution required — https://coverr.co/license)
#     a-broker-works-with-a-cryptocurrency-candlestick-chart-9867.mp4
#     a-businessman-working-on-a-stock-market-trading-platform-4862.mp4
#     a-screen-showing-financial-analysis-of-a-cryptocurrency-3490.mp4
#     a-trader-writing-analytical-data-in-a-notebook-652.mp4
#     a-man-analyzing-the-stock-market-5128.mp4
#   Mixkit Stock Video FREE License (commercial use allowed — https://mixkit.co/license/)
#     mixkit-reflection-of-a-screen-in-glasses-221.mp4
#
# Output: public/media/*.mp4 (H.264, no audio, faststart) + *.webp posters.
#  - Clips with a camera move loop as PING-PONG (forward + reversed): no visible jump.
#  - Near-static clips loop with a 1 s CROSSFADE of the tail into the head.
#  - The colour grade is baked in (no runtime CSS filters on video).
set -euo pipefail
SRC="${1:?source dir}"
OUT="$(cd "$(dirname "$0")/.." && pwd)/public/media"
mkdir -p "$OUT"
X264=(-c:v libx264 -preset slow -pix_fmt yuv420p -movflags +faststart -an -r 24)

# Ink grade: slightly lower saturation, deeper shadows, a touch of contrast.
INK="eq=saturation=0.82:contrast=1.06:brightness=-0.035:gamma=0.96,colorbalance=bs=0.05:bm=0.02:rh=0.02"
# Violet grade for the AI scene: mostly desaturated and darkened (the source is a bright close-up), pushed to violet.
VIOLET="eq=saturation=0.25:contrast=1.12:brightness=-0.14:gamma=0.74,colorbalance=rs=0.05:bs=0.18:rm=0.04:bm=0.14:rh=0.02:bh=0.06"

pingpong() { # name src start seconds width crf grade
  local name=$1 src=$2 ss=$3 len=$4 w=$5 crf=$6 grade=$7
  ffmpeg -v error -y -ss "$ss" -t "$len" -i "$SRC/$src" \
    -filter_complex "[0:v]scale=${w}:-2:flags=lanczos,${grade},split[a][b];[b]reverse[r];[a][r]concat=n=2:v=1:a=0[v]" \
    -map "[v]" "${X264[@]}" -crf "$crf" "$OUT/$name.mp4"
  ffmpeg -v error -y -i "$OUT/$name.mp4" -frames:v 1 -c:v libwebp -quality 72 "$OUT/$name.webp"
  echo "$name: $(du -h "$OUT/$name.mp4" | cut -f1)"
}

crossfade() { # name src start seconds width crf grade
  local name=$1 src=$2 ss=$3 len=$4 w=$5 crf=$6 grade=$7
  local main off; main=$(awk "BEGIN{print $len-1}"); off=$(awk "BEGIN{print $len-2}")
  ffmpeg -v error -y -ss "$ss" -t "$len" -i "$SRC/$src" \
    -filter_complex "[0:v]scale=${w}:-2:flags=lanczos,${grade},split[m][h];[m]trim=start=1,setpts=PTS-STARTPTS[body];[h]trim=end=1,setpts=PTS-STARTPTS[head];[body][head]xfade=transition=fade:duration=1:offset=${off}[v]" \
    -map "[v]" "${X264[@]}" -crf "$crf" "$OUT/$name.mp4"
  ffmpeg -v error -y -i "$OUT/$name.mp4" -frames:v 1 -c:v libwebp -quality 72 "$OUT/$name.webp"
  echo "$name: $(du -h "$OUT/$name.mp4" | cut -f1) (body ${main}s)"
}

# Hero: broker at a desk, monitor + laptop with candle charts (slow dolly → ping-pong).
pingpong hero-trader-desk        a-broker-works-with-a-cryptocurrency-candlestick-chart-9867.mp4      3   6 1280 26 "$INK"
pingpong hero-trader-desk-sm     a-broker-works-with-a-cryptocurrency-candlestick-chart-9867.mp4      3   6  720 29 "$INK"
# Workflow: laptop chart + hands, close.
pingpong workflow-laptop-chart   a-businessman-working-on-a-stock-market-trading-platform-4862.mp4    0.4 5  960 29 "$INK"
# Information overload: out-of-focus price board.
pingpong overload-price-board    a-screen-showing-financial-analysis-of-a-cryptocurrency-3490.mp4     2   6  960 30 "$INK"
# Methodology: hands writing analysis in a notebook.
pingpong method-notebook         a-trader-writing-analytical-data-in-a-notebook-652.mp4               4   6  960 29 "$INK"
# Closing: trader in profile at the screen (static camera → crossfade).
crossfade closing-trader-profile a-man-analyzing-the-stock-market-5128.mp4                           4   9 1280 27 "$INK"
# AI assistant: screen light reflected in glasses (violet grade).
crossfade assistant-reflection   mixkit-reflection-of-a-screen-in-glasses-221.mp4                    2   9  960 29 "$VIOLET"

ls -la "$OUT"
