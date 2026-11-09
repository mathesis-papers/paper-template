"""What a render makes, as shell assignments for film.sh, render_all.sh and mux.sh (`eval`).

Usage: python3 theme/film/plan.py <film dir>

The requested outputs are $FILM_OUTPUTS (output keys separated by spaces or commas; `film.sh <dir> all <key>…`
sets it, and so does the build, from film.json) or, when it is unset or empty, the outputs film.json lists.
Prints:

  OUTPUTS='narrated_720p cover'   the requested output keys
  RENDITIONS='720p'               what every frames worker encodes, comma-separated: master (the 1920x1080
                                  frames, CRF 17) only for a 1080p video, 720p (scaled in the same pass) for
                                  a 720p video
  MUSIC_MIX=0                     1 when a music-only video is requested (mix.py writes out/mix_music.wav)
  NARRATED='' MUSIC_ONLY='' NARRATED_720P='<file>' MUSIC_ONLY_720P='' COVER='<file>'
                                  the file names in out/ ('' when not requested)

The decisions are tools/tbook/film.py render_plan(). Exits 1 on an unknown output key.
"""

from __future__ import annotations

import shlex
import sys

from common import film_dir_arg, load, plan

VARS = {"narrated": "NARRATED", "music_only": "MUSIC_ONLY", "narrated_720p": "NARRATED_720P",
        "music_only_720p": "MUSIC_ONLY_720P", "cover": "COVER"}


def main(argv: list[str]) -> int:
    film = load(film_dir_arg(argv))
    p = plan(film)
    lines = [f"OUTPUTS={shlex.quote(' '.join(p['outputs']))}",
             f"RENDITIONS={shlex.quote(','.join(p['renditions']))}",
             f"MUSIC_MIX={1 if p['music'] else 0}"]
    for key, var in VARS.items():
        lines.append(f"{var}={shlex.quote(film.output(key) if key in p['outputs'] else '')}")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
