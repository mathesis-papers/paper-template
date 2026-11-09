#!/usr/bin/env bash
# Render every frame of a film in parallel headless-Chromium workers → out/seg_<i>.mp4. Writes nothing outside
# out/: the cover is the `cover` step (film.sh), the committed poster.jpg the `poster` step, run by hand.
# usage: theme/film/render_all.sh <film dir>
# Env: FILM_WORKERS (default: min(3, CPUs)), FFMPEG, PW_CHROMIUM_PATH, FILM_STRICT=1 (no provisional timing).
# Adapted from trureturing-film films/*/render_all.sh (Apache-2.0, the-omega-institute).
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FILM="$(cd "$1" && pwd)"; shift
OUT="$FILM/out"
PYTHON="${PYTHON:-python3}"
"$PYTHON" "$HERE/build.py" "$FILM"
CPUS="$(getconf _NPROCESSORS_ONLN 2>/dev/null || echo 2)"
N="${FILM_WORKERS:-$(( CPUS < 3 ? CPUS : 3 ))}"
[ "$N" -ge 1 ] || N=1
rm -f "$OUT"/seg_*.mp4 "$OUT"/r*.log
pids=()
for ((w = 0; w < N; w++)); do
  node "$HERE/render.js" "$OUT" --worker "$w" --workers "$N" > "$OUT/r$w.log" 2>&1 & pids+=($!)
done
fail=0
for i in "${!pids[@]}"; do
  if ! wait "${pids[$i]}"; then fail=1; echo "film: worker $i failed:" >&2; tail -n 20 "$OUT/r$i.log" >&2; fi
done
[ "$fail" = 0 ] || exit 1
grep -h done "$OUT"/r*.log
printf "%s\n" "$N" > "$OUT/segments.txt"
