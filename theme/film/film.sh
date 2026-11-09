#!/usr/bin/env bash
# The film pipeline, one entry point for every film directory (books/<slug>/films/<NNN>-<name>).
#
#   theme/film/film.sh <film dir> <step> [args…]
#
# steps (all outputs go to <film dir>/out/, which is git-ignored):
#   setup      Python packages, the Kokoro model (cached in .cache/film/models) and fonts      → setup.sh
#   tts        narration line by line with Kokoro-82M → out/tts/, out/narration.wav, out/timeline.json
#   timeline   provisional timing from script.json (no TTS) → out/timeline.provisional.json
#   build      out/index.html (engine + scenes + data + fonts + timeline)
#   music      procedural score and SFX synced to the timeline → out/music_bed.wav
#   mix        ducked narration mix and music-only mix → out/mix_voice.wav, out/mix_music.wav
#   frames     every frame through headless Chromium → out/seg_<i>.mp4 (parallel workers)
#   render     frames + poster
#   mux        out/<outputs.narrated>, out/<outputs.music_only> (1080p masters, CRF 17)
#   small      out/<outputs.narrated_720p>, out/<outputs.music_only_720p> (720p two-pass)
#   poster     out/<outputs.cover> (1920×1080) and <film dir>/poster.jpg (≤ 300 KB, committed)
#   clip       a short silent preview: clip [start s] [seconds] [WxH] → out/clip.mp4
#   shot       stills for review: shot <t1> <t2> … [--size WxH] [--poster] → out/shots/
#   serve      preview at http://127.0.0.1:<port>/index.html?play (or ?t=12.5, ?poster)
#   notes      release notes (Markdown) on stdout
#   all        tts, music, mix, render, mux, small (run setup first)
#
# Environment: PYTHON (default python3), PW_CHROMIUM_PATH (Chromium for Playwright), FFMPEG, FILM_WORKERS,
# FILM_STRICT=1 (fail instead of using provisional timing), FILM_CACHE, KOKORO_MODEL_DIR.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"

usage() { sed -n '2,30p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 2; }
[ $# -ge 2 ] || usage
FILM="$(cd "$1" 2>/dev/null && pwd)" || { echo "film: no such directory: $1" >&2; exit 2; }
STEP="$2"; shift 2
[ -f "$FILM/film.json" ] || { echo "film: $FILM has no film.json" >&2; exit 2; }
OUT="$FILM/out"
mkdir -p "$OUT"

if [ -z "${PYTHON:-}" ]; then
  if [ -x "$ROOT/.venv/bin/python" ] && "$ROOT/.venv/bin/python" -c 'import numpy' 2>/dev/null; then PYTHON="$ROOT/.venv/bin/python"; else PYTHON=python3; fi
fi
export PYTHON
py() { "$PYTHON" "$HERE/$1" "${@:2}"; }
meta() { "$PYTHON" -c 'import json,sys;d=json.load(open(sys.argv[1]));print(d.get("outputs",{}).get(sys.argv[2],""))' "$FILM/film.json" "$1"; }
ffmpeg_bin() {
  if [ -n "${FFMPEG:-}" ]; then echo "$FFMPEG"; return; fi
  if command -v ffmpeg >/dev/null 2>&1; then command -v ffmpeg; return; fi
  "$PYTHON" -c 'import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())' 2>/dev/null || { echo "film: ffmpeg not found (install ffmpeg or pip install imageio-ffmpeg)" >&2; exit 1; }
}
export -f ffmpeg_bin 2>/dev/null || true

case "$STEP" in
  setup)    "$HERE/setup.sh" ;;
  tts)      py tts.py "$FILM" "$@" ;;
  timeline) py build.py "$FILM" --timeline-only ;;
  build)    py build.py "$FILM" "$@" ;;
  music)    py music.py "$FILM" "$@" ;;
  mix)      py mix.py "$FILM" "$@" ;;
  frames)   FFMPEG="$(ffmpeg_bin)" "$HERE/render_all.sh" "$FILM" --no-poster ;;
  render)   FFMPEG="$(ffmpeg_bin)" "$HERE/render_all.sh" "$FILM" ;;
  mux)      FFMPEG="$(ffmpeg_bin)" "$HERE/mux.sh" "$FILM" ;;
  small)    FFMPEG="$(ffmpeg_bin)" "$HERE/small.sh" "$FILM" ;;
  poster)   py build.py "$FILM" && node "$HERE/poster.js" "$OUT" "$(meta cover)" "$FILM/poster.jpg" ;;
  clip)
    START="${1:-0}"; SECS="${2:-3}"; SIZE="${3:-960x540}"
    py build.py "$FILM"
    END="$("$PYTHON" -c 'import sys;print(float(sys.argv[1])+float(sys.argv[2]))' "$START" "$SECS")"
    FFMPEG="$(ffmpeg_bin)" node "$HERE/render.js" "$OUT" --start "$START" --end "$END" --size "$SIZE" --crf 23 --preset veryfast --output clip.mp4 ;;
  shot)     py build.py "$FILM" && node "$HERE/shot.js" "$OUT" "$@" ;;
  serve)
    py build.py "$FILM"
    PORT="${PORT:-$("$PYTHON" -c 'import socket;s=socket.socket();s.bind(("127.0.0.1",0));print(s.getsockname()[1]);s.close()')}"
    echo "film: http://127.0.0.1:$PORT/index.html?play  (?t=12.5 for one frame, ?poster for the poster)"
    exec "$PYTHON" -m http.server "$PORT" --bind 127.0.0.1 --directory "$OUT" ;;
  notes)    py release.py notes "$FILM" "$@" ;;
  all)
    py tts.py "$FILM"
    py music.py "$FILM"
    py mix.py "$FILM"
    FILM_STRICT=1 FFMPEG="$(ffmpeg_bin)" "$HERE/render_all.sh" "$FILM"
    FFMPEG="$(ffmpeg_bin)" "$HERE/mux.sh" "$FILM"
    FFMPEG="$(ffmpeg_bin)" "$HERE/small.sh" "$FILM" ;;
  *) echo "film: unknown step '$STEP'" >&2; usage ;;
esac
