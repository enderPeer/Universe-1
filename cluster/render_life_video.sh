#!/bin/sh
# Encode the periodic frames of a Life run (out-dir/t%08d.ppm from `--ppm-every k`) into an H.264 video with a tick counter.
# usage: cluster/render_life_video.sh <run-dir> <ppm-every> <fps> [<out.mp4>] [<scale-px>]
# Example (on the node that holds the frames): cluster/render_life_video.sh results/life/jc_s1 100 30
set -e
dir=$1; every=$2; fps=${3:-30}; out=${4:-$dir/video.mp4}; scale=${5:-0}
[ -d "$dir" ] && [ -n "$every" ] || { echo "usage: $0 <run-dir> <ppm-every> [fps] [out.mp4] [scale-px]"; exit 2; }
frames=$(ls "$dir"/t[0-9]*.ppm | wc -l); echo "$frames frames in $dir"
vf="drawtext=text='tick %{eif\\:n*$every\\:d}':x=16:y=16:fontsize=28:fontcolor=white:box=1:boxcolor=black@0.5:boxborderw=8"
[ "$scale" != "0" ] && vf="scale=$scale:$scale:flags=area,$vf"
ffmpeg -hide_banner -loglevel error -y -framerate "$fps" -pattern_type glob -i "$dir/t[0-9]*.ppm" \
  -vf "$vf" -c:v libx264 -preset slow -crf 20 -pix_fmt yuv420p -movflags +faststart "$out"
ffprobe -v error -show_entries format=duration,size -of default=nw=1 "$out"
