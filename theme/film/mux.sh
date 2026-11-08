#!/usr/bin/env bash
# Concatenate out/seg_*.mp4 and mux the mixes: out/<outputs.narrated> (mix_voice.wav) and out/<outputs.music_only>
# (mix_music.wav), 1080p masters with AAC 192k and +faststart for streaming from a release asset.
# usage: theme/film/mux.sh <film dir>      Env: FFMPEG. Adapted from trureturing-film films/*/mux.sh (Apache-2.0).
set -euo pipefail
FILM="$(cd "$1" && pwd)"
OUT="$FILM/out"
FF="${FFMPEG:-ffmpeg}"
PYTHON="${PYTHON:-python3}"
name() { "$PYTHON" -c 'import json,sys;print(json.load(open(sys.argv[1]))["outputs"][sys.argv[2]])' "$FILM/film.json" "$1"; }
cd "$OUT"
N="$(cat segments.txt 2>/dev/null || ls seg_*.mp4 | wc -l)"
[ "$N" -ge 1 ] || { echo "film: no out/seg_*.mp4; run the frames step first" >&2; exit 1; }
: > segs.txt
for ((i = 0; i < N; i++)); do
  [ -f "seg_$i.mp4" ] || { echo "film: out/seg_$i.mp4 is missing" >&2; exit 1; }
  printf "file 'seg_%d.mp4'\n" "$i" >> segs.txt
done
for f in mix_voice.wav mix_music.wav; do [ -f "$f" ] || { echo "film: out/$f is missing; run the mix step" >&2; exit 1; }; done
"$FF" -y -loglevel error -f concat -safe 0 -i segs.txt -c copy video_only.mp4
NARRATED="$(name narrated)"; MUSIC="$(name music_only)"
"$FF" -y -loglevel error -i video_only.mp4 -i mix_voice.wav -map 0:v -map 1:a -c:v copy -c:a aac -b:a 192k -ar 48000 -shortest -movflags +faststart "$NARRATED"
"$FF" -y -loglevel error -i video_only.mp4 -i mix_music.wav -map 0:v -map 1:a -c:v copy -c:a aac -b:a 192k -ar 48000 -shortest -movflags +faststart "$MUSIC"
ls -la "$NARRATED" "$MUSIC"
echo MUX_OK
