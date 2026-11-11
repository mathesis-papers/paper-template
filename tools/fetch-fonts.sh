#!/usr/bin/env bash
# tools/fetch-fonts.sh — fetch the fonts the PDF (Typst) and EPUB pipeline prefers into .cache/fonts/.
#
# Usage: tools/fetch-fonts.sh [--latin-only] [--force] [--list] [--dest DIR]
#
#   Chakra Petch  Regular/Medium/SemiBold/Bold   display face  (google/fonts, OFL)
#   JetBrains Mono Regular/Bold/Italic           data face     (JetBrains/JetBrainsMono, OFL)
#   Noto Serif SC / Noto Sans SC Regular/Bold    Chinese body / headings (notofonts/noto-cjk, OFL)
#
# The build never requires these files: theme/typst/book.typ and cover.typ fall back to
# system fonts (Noto CJK from fonts-noto-cjk, DejaVu, Libertinus bundled with Typst), and
# tools/tbook/pandoc.py unpacks the Latin WOFF files of node_modules/@fontsource into
# .cache/fonts-fontsource/ when Chakra Petch is missing.
#
# Safety: downloads go to a temporary file over HTTPS only, are checked for a TrueType/OpenType
# signature, verified against theme/typst/fonts.sha256 when it pins a checksum, and only then
# moved into place. Nothing downloaded is ever executed. The script is idempotent: files that
# are present (and match their pinned checksum) are skipped.
#
# Checksums: theme/typst/fonts.sha256 ("<sha256>  <file name>" per line) is optional. Files
# without a pinned checksum are accepted with a warning and their computed sums are written to
# <dest>/SHA256SUMS — copy those lines into theme/typst/fonts.sha256 to pin them.
#
# Environment overrides (pin these to commit SHAs for fully reproducible fonts):
#   GOOGLE_FONTS_REF (default: main — TODO pin to a google/fonts commit SHA)
#   JETBRAINS_MONO_REF (default: v2.304)
#   NOTO_CJK_SANS_REF (default: Sans2.004)   NOTO_CJK_SERIF_REF (default: Serif2.003)
#   FONTS_SHA256 (default: theme/typst/fonts.sha256)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="${FONTS_DIR:-$ROOT/.cache/fonts}"
SUMS_FILE="${FONTS_SHA256:-$ROOT/theme/typst/fonts.sha256}"
GOOGLE_FONTS_REF="${GOOGLE_FONTS_REF:-main}"
JETBRAINS_MONO_REF="${JETBRAINS_MONO_REF:-v2.304}"
NOTO_CJK_SANS_REF="${NOTO_CJK_SANS_REF:-Sans2.004}"
NOTO_CJK_SERIF_REF="${NOTO_CJK_SERIF_REF:-Serif2.003}"

LATIN_ONLY=0
FORCE=0
LIST=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --latin-only) LATIN_ONLY=1 ;;
    --force) FORCE=1 ;;
    --list) LIST=1 ;;
    --dest) DEST="$2"; shift ;;
    -h|--help) sed -n '2,30p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "fetch-fonts: unknown option $1 (try --help)" >&2; exit 2 ;;
  esac
  shift
done

GF="https://raw.githubusercontent.com/google/fonts/${GOOGLE_FONTS_REF}/ofl/chakrapetch"
JB="https://raw.githubusercontent.com/JetBrains/JetBrainsMono/${JETBRAINS_MONO_REF}/fonts/ttf"
NS="https://raw.githubusercontent.com/notofonts/noto-cjk/${NOTO_CJK_SANS_REF}/Sans/SubsetOTF/SC"
NR="https://raw.githubusercontent.com/notofonts/noto-cjk/${NOTO_CJK_SERIF_REF}/Serif/SubsetOTF/SC"

# "<file name> <url>"
FONTS=(
  "ChakraPetch-Regular.ttf $GF/ChakraPetch-Regular.ttf"
  "ChakraPetch-Medium.ttf $GF/ChakraPetch-Medium.ttf"
  "ChakraPetch-SemiBold.ttf $GF/ChakraPetch-SemiBold.ttf"
  "ChakraPetch-Bold.ttf $GF/ChakraPetch-Bold.ttf"
  "JetBrainsMono-Regular.ttf $JB/JetBrainsMono-Regular.ttf"
  "JetBrainsMono-Bold.ttf $JB/JetBrainsMono-Bold.ttf"
  "JetBrainsMono-Italic.ttf $JB/JetBrainsMono-Italic.ttf"
)
if [[ $LATIN_ONLY -eq 0 ]]; then
  FONTS+=(
    "NotoSansSC-Regular.otf $NS/NotoSansSC-Regular.otf"
    "NotoSansSC-Bold.otf $NS/NotoSansSC-Bold.otf"
    "NotoSerifSC-Regular.otf $NR/NotoSerifSC-Regular.otf"
    "NotoSerifSC-Bold.otf $NR/NotoSerifSC-Bold.otf"
  )
fi

if [[ $LIST -eq 1 ]]; then
  printf '%s\n' "${FONTS[@]}"
  exit 0
fi

command -v curl >/dev/null || { echo "fetch-fonts: curl is required" >&2; exit 1; }
if command -v sha256sum >/dev/null; then SHA=(sha256sum); else SHA=(shasum -a 256); fi

pinned_sum() {  # pinned_sum <file name> → checksum or empty
  [[ -f "$SUMS_FILE" ]] || return 0
  awk -v f="$1" '!/^#/ && NF >= 2 && $2 == f { print $1; exit }' "$SUMS_FILE"
}

is_font() {  # TrueType (00010000 / "true") or OpenType CFF ("OTTO") signature
  local magic
  magic="$(head -c 4 "$1" | od -An -tx1 | tr -d ' \n')"
  [[ "$magic" == "00010000" || "$magic" == "74727565" || "$magic" == "4f54544f" ]]
}

mkdir -p "$DEST"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/fetch-fonts.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT
: > "$TMP/SHA256SUMS"
failed=0
unpinned=0

for entry in "${FONTS[@]}"; do
  name="${entry%% *}"
  url="${entry#* }"
  target="$DEST/$name"
  want="$(pinned_sum "$name")"
  if [[ -f "$target" && $FORCE -eq 0 ]]; then
    have="$("${SHA[@]}" "$target" | awk '{print $1}')"
    if [[ -z "$want" || "$have" == "$want" ]]; then
      echo "ok      $name"
      echo "$have  $name" >> "$TMP/SHA256SUMS"
      continue
    fi
    echo "stale   $name (checksum differs from $(basename "$SUMS_FILE")); refetching"
  fi
  if ! curl --fail --silent --show-error --location --retry 3 --proto '=https' --tlsv1.2 \
        --max-time 300 -o "$TMP/$name" "$url"; then
    echo "FAILED  $name ← $url" >&2
    failed=1
    continue
  fi
  if ! is_font "$TMP/$name"; then
    echo "FAILED  $name: not a TrueType/OpenType file (got $(head -c 16 "$TMP/$name" | tr -dc '[:print:]'))" >&2
    failed=1
    continue
  fi
  have="$("${SHA[@]}" "$TMP/$name" | awk '{print $1}')"
  if [[ -n "$want" && "$have" != "$want" ]]; then
    echo "FAILED  $name: sha256 $have does not match pinned $want" >&2
    failed=1
    continue
  fi
  if [[ -z "$want" ]]; then
    unpinned=1
    echo "fetched $name (no pinned checksum — TODO: pin it in $(basename "$SUMS_FILE"))"
  else
    echo "fetched $name (sha256 verified)"
  fi
  mv -f "$TMP/$name" "$target"
  echo "$have  $name" >> "$TMP/SHA256SUMS"
done

sort -k2 "$TMP/SHA256SUMS" > "$DEST/SHA256SUMS"
if [[ $unpinned -eq 1 ]]; then
  echo "note: computed checksums are in ${DEST#$ROOT/}/SHA256SUMS; copy them into ${SUMS_FILE#$ROOT/} to pin."
fi
if [[ $failed -ne 0 ]]; then
  echo "fetch-fonts: some fonts could not be fetched; the build still works with fallback fonts." >&2
  exit 1
fi
echo "fonts in ${DEST#$ROOT/}: $(ls "$DEST" | grep -ciE '\.(ttf|otf)$') file(s)"
