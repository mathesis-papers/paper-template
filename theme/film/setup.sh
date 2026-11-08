#!/usr/bin/env bash
# Fetch build-time dependencies of the film pipeline (nothing here is committed):
#   - Python packages for narration, score and mixing (pip; set PIP_ARGS to e.g. --user),
#   - the Kokoro-82M v1.0 ONNX model and voices (≈ 340 MB) into $KOKORO_MODEL_DIR (default .cache/film/models),
#   - fonts: @fontsource packages from node_modules (npm ci); when absent, `npm pack` into .cache/film/fonts.
# Adapted from trureturing-film films/*/setup.sh (Apache-2.0, the-omega-institute).
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
PYTHON="${PYTHON:-python3}"
CACHE="${FILM_CACHE:-$ROOT/.cache/film}"
MODELS="${KOKORO_MODEL_DIR:-$CACHE/models}"
KOKORO_URL="https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0"

"$PYTHON" -m pip install ${PIP_ARGS:-} kokoro-onnx soundfile scipy numpy pillow imageio-ffmpeg

mkdir -p "$MODELS"
for f in kokoro-v1.0.onnx voices-v1.0.bin; do
  if [ ! -s "$MODELS/$f" ]; then
    echo "setup: downloading $f"
    curl -fL --retry 3 -o "$MODELS/$f.part" "$KOKORO_URL/$f"
    mv "$MODELS/$f.part" "$MODELS/$f"
  fi
done

missing=()
for p in orbitron chakra-petch jetbrains-mono rajdhani noto-sans-sc; do
  [ -d "$ROOT/node_modules/@fontsource/$p/files" ] || missing+=("$p")
done
if [ ${#missing[@]} -gt 0 ]; then
  echo "setup: @fontsource packages missing from node_modules (${missing[*]}); fetching them into $CACHE/fonts"
  VERSIONS="$(cd "$ROOT" && node -e 'const d=require("./package.json").devDependencies;for(const[k,v]of Object.entries(d))if(k.startsWith("@fontsource/"))console.log(k+"@"+v)')"
  mkdir -p "$CACHE/fonts" && cd "$CACHE/fonts"
  for spec in $VERSIONS; do
    pkg="${spec#@fontsource/}"; pkg="${pkg%@*}"
    [ -d "$pkg/files" ] && continue
    tgz="$(npm pack "$spec" --silent | tail -n 1)"
    rm -rf "$pkg" && mkdir "$pkg" && tar xzf "$tgz" -C "$pkg" --strip-components=1 && rm -f "$tgz"
  done
fi
echo SETUP_OK
