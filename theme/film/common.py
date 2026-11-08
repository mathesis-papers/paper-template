"""Shared helpers for the film pipeline scripts in theme/film/ (stdlib only).

Every script takes the film directory (``books/<slug>/films/<NNN>-<name>``) as its first
argument and writes into ``<film dir>/out/`` (git-ignored). Film metadata, validation and the
provisional timeline come from ``tools/tbook/film.py`` so the pipeline and ``./tbook check``
agree on one schema.

Environment:
  FILM_CACHE        shared cache for models and fallback fonts (default <repo>/.cache/film)
  KOKORO_MODEL_DIR  directory with kokoro-v1.0.onnx and voices-v1.0.bin (default $FILM_CACHE/models)
  FFMPEG            ffmpeg binary (default: ffmpeg on PATH, else imageio-ffmpeg's)
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

from tbook import film as tfilm  # noqa: E402  (after the sys.path insert)


class PipelineError(Exception):
    pass


def fail(msg: str) -> "NoReturn":  # type: ignore[name-defined]
    print(f"film: {msg}", file=sys.stderr)
    raise SystemExit(1)


def film_dir_arg(argv: list[str]) -> Path:
    if not argv:
        fail("usage: <script> <film dir> [options]")
    d = Path(argv[0]).resolve()
    if not (d / "film.json").is_file():
        fail(f"{d}: not a film directory (no film.json)")
    return d


def load(film_dir: Path) -> tfilm.Film:
    book = tfilm.book_of(film_dir)
    return tfilm.load_film(book, film_dir)


def out_dir(film_dir: Path) -> Path:
    out = film_dir / "out"
    out.mkdir(parents=True, exist_ok=True)
    return out


def cache_dir() -> Path:
    return Path(os.environ.get("FILM_CACHE") or ROOT / ".cache" / "film")


def model_dir() -> Path:
    return Path(os.environ.get("KOKORO_MODEL_DIR") or cache_dir() / "models")


def ffmpeg() -> str:
    exe = os.environ.get("FFMPEG") or shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg  # type: ignore

        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        fail("ffmpeg not found: install ffmpeg, set FFMPEG, or pip install imageio-ffmpeg")


def timeline(film: tfilm.Film, *, allow_provisional: bool = True) -> tuple[dict, bool]:
    """(timeline, provisional). out/timeline.json from tts.py when it matches script.json, else a provisional one."""
    if film.script is None:
        fail(f"{film.dir}/script.json is unreadable")
    path = film.dir / "out" / "timeline.json"
    if path.is_file():
        tl = json.loads(path.read_text(encoding="utf-8"))
        stale = tfilm.timeline_matches(tl, film.script)
        if not stale:
            return tl, False
        if not allow_provisional:
            fail(f"out/timeline.json is stale ({stale}); rerun: theme/film/film.sh {film.dir} tts")
        print(f"film: warning: out/timeline.json is stale ({stale}); using a provisional timeline", file=sys.stderr)
    elif not allow_provisional:
        fail(f"no out/timeline.json; run theme/film/film.sh {film.dir} tts first")
    else:
        print("film: warning: no narration yet (out/timeline.json); timing is provisional "
              f"({tfilm.WORDS_PER_SECOND} words/s)", file=sys.stderr)
    return tfilm.provisional_timeline(film.script), True
