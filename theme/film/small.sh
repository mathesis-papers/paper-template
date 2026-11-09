#!/usr/bin/env bash
# 720p two-pass copies of the masters: out/<outputs.narrated_720p>, out/<outputs.music_only_720p>.
# usage: theme/film/small.sh <film dir>      Env: FFMPEG. Adapted from trureturing-film films/*/small.sh (Apache-2.0).
set -euo pipefail
FILM="$(cd "$1" && pwd)"
OUT="$FILM/out"
FF="${FFMPEG:-ffmpeg}"
PYTHON="${PYTHON:-python3}"
name() {
  "$PYTHON" - "$FILM" "$1" <<'PY'
import sys
from pathlib import Path
sys.path.insert(0, str(Path(sys.argv[1]).resolve().parents[3] / "tools"))
from tbook import film
d = Path(sys.argv[1]).resolve()
print(film.load_film(film.book_of(d), d).output(sys.argv[2]))
PY
}
cd "$OUT"
[ -f video_only.mp4 ] || { echo "film: out/video_only.mp4 is missing; run the mux step first" >&2; exit 1; }
VF="hqdn3d=3:2:6:5,scale=1280:720:flags=lanczos"
"$FF" -y -loglevel error -i video_only.mp4 -vf "$VF" -c:v libx264 -preset slow -b:v 900k -pass 1 -passlogfile p720 -pix_fmt yuv420p -an -f mp4 /dev/null
"$FF" -y -loglevel error -i video_only.mp4 -vf "$VF" -c:v libx264 -preset slow -b:v 900k -pass 2 -passlogfile p720 -pix_fmt yuv420p -an v720.mp4
N720="$(name narrated_720p)"; M720="$(name music_only_720p)"
"$FF" -y -loglevel error -i v720.mp4 -i mix_voice.wav -map 0:v -map 1:a -c:v copy -c:a aac -b:a 128k -shortest -movflags +faststart "$N720"
"$FF" -y -loglevel error -i v720.mp4 -i mix_music.wav -map 0:v -map 1:a -c:v copy -c:a aac -b:a 128k -shortest -movflags +faststart "$M720"
rm -f p720-0.log p720-0.log.mbtree
ls -la "$N720" "$M720"
echo SMALL_OK
