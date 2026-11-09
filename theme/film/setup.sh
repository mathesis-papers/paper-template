#!/usr/bin/env bash
# Install the film toolchain (nothing here is committed). No film argument: run it once per machine.
#   theme/film/setup.sh
#
#   - the pinned Python packages of theme/film/requirements.txt (narration, score, mixing). With PYTHON set,
#     into that interpreter ("$PYTHON -m pip install -r", PIP_ARGS adds pip options); without it, into the
#     film venv $FILM_CACHE/venv (default .cache/film/venv), created from python3 (Python 3.12 or 3.13), so the
#     tbook venv stays lean. theme/film/film.sh and ./tbook build prefer that venv when PYTHON is not set.
#   - the Kokoro-82M ONNX model and voices (≈ 340 MB) into $KOKORO_MODEL_DIR (default $FILM_CACHE/models),
#     unless present;
#   - fonts: the @fontsource packages come from node_modules (npm ci); when absent, `npm pack` into
#     $FILM_CACHE/fonts.
# ffmpeg comes from the system (apt-get install ffmpeg; or set FFMPEG), Chromium from Playwright or
# PW_CHROMIUM_PATH. ./tbook build films checks the whole toolchain before it renders.
# Adapted from trureturing-film films/*/setup.sh (Apache-2.0, the-omega-institute).
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
CACHE="${FILM_CACHE:-$ROOT/.cache/film}"
MODELS="${KOKORO_MODEL_DIR:-$CACHE/models}"
# The model release; tools/tbook/film.py KOKORO_RELEASE names the same one (part of every film's build key).
KOKORO_RELEASE="model-files-v1.0"
KOKORO_URL="https://github.com/thewh1teagle/kokoro-onnx/releases/download/$KOKORO_RELEASE"

if [ -z "${PYTHON:-}" ]; then
  VENV="$CACHE/venv"
  if [ ! -x "$VENV/bin/python" ]; then
    echo "setup: creating the film venv $VENV"
    python3 -m venv "$VENV"
  fi
  PYTHON="$VENV/bin/python"
fi
echo "setup: Python packages for $PYTHON"
# shellcheck disable=SC2086  # PIP_ARGS holds several options
"$PYTHON" -m pip install --disable-pip-version-check ${PIP_ARGS:-} -r "$HERE/requirements.txt"

mkdir -p "$MODELS"
for f in kokoro-v1.0.onnx voices-v1.0.bin; do
  if [ ! -s "$MODELS/$f" ]; then
    echo "setup: downloading $f into $MODELS"
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
