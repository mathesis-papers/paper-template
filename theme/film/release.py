"""Release helpers for .github/workflows/film.yml (stdlib only).

  python3 theme/film/release.py tag <book slug> <film>    film.json release_tag of books/<slug>/films/<film> (<NNN>-<name> or NNN)
  python3 theme/film/release.py resolve <tag>            film directory for a tag film-<slug>-<NNN>-v<k>;
                                                         prints key=value lines (dir, slug, num, title) for $GITHUB_OUTPUT
  python3 theme/film/release.py notes <film dir> [sha]   release notes (Markdown): subject commit, Lean citations, files
  python3 theme/film/release.py assets <film dir>        the release files under out/, one path per line (must all exist)

The tag must equal film.json "release_tag". Once the release exists, set film.json "published_tag" to it
(and commit): the book embeds https://github.com/<repo>/releases/download/<published_tag>/<asset>, and shows
the poster with a "not released yet" note while published_tag is null.
"""

from __future__ import annotations

import sys
from pathlib import Path

from common import ROOT, fail, load, tfilm


def tag(slug: str, which: str) -> int:
    films_dir = ROOT / "books" / slug / "films"
    if not films_dir.is_dir():
        fail(f"books/{slug}/films/ does not exist")
    found = [p for p in sorted(films_dir.iterdir()) if p.is_dir() and (p.name == which or p.name.startswith(f"{which}-"))]
    if len(found) != 1:
        fail(f"no unique film {which!r} in books/{slug}/films/ ({', '.join(p.name for p in found) or 'none'})")
    film = load(found[0])
    if not film.release_tag:
        fail(f"{found[0].relative_to(ROOT)}/film.json has no release_tag")
    print(film.release_tag)
    return 0


def resolve(tag: str) -> int:
    parsed = tfilm.parse_tag(tag)
    if not parsed:
        fail(f"tag {tag!r} does not look like film-<book slug>-<NNN>-v<k>")
    slug, num, _ = parsed
    films_dir = ROOT / "books" / slug / "films"
    found = sorted(p for p in films_dir.glob(f"{num}-*") if (p / "film.json").is_file()) if films_dir.is_dir() else []
    if not found:
        fail(f"no film {num} in books/{slug}/films/")
    if len(found) > 1:
        fail(f"film number {num} is used twice in books/{slug}/films/")
    film = load(found[0])
    if film.release_tag != tag:
        fail(f"{found[0].relative_to(ROOT)}/film.json has release_tag {film.release_tag!r}, not {tag!r}; "
             "update film.json (and commit) before tagging")
    issues = [i for i in tfilm.check_film(film, tfilm._lock()) if i.severity == "error"]
    if issues:
        fail("the film has errors:\n  " + "\n  ".join(i.format() for i in issues))
    print(f"dir={found[0].relative_to(ROOT).as_posix()}")
    print(f"slug={slug}")
    print(f"num={num}")
    print(f"title={film.title('en')} · {film.title('zh')}")
    return 0


def notes(film_dir: Path, sha: str = "") -> int:
    sys.stdout.write(tfilm.release_notes(load(film_dir), sha))
    return 0


def assets(film_dir: Path) -> int:
    film = load(film_dir)
    missing = []
    for key in ("narrated", "music_only", "narrated_720p", "music_only_720p", "cover"):
        path = film.out / film.output(key)
        if not path.is_file():
            missing.append(str(path))
        print(path)
    if missing:
        fail("missing release files:\n  " + "\n  ".join(missing))
    return 0


def main(argv: list[str]) -> int:
    if len(argv) >= 3 and argv[0] == "tag":
        return tag(argv[1], argv[2])
    if len(argv) >= 2 and argv[0] == "resolve":
        return resolve(argv[1])
    if len(argv) >= 2 and argv[0] == "notes":
        return notes(Path(argv[1]).resolve(), argv[2] if len(argv) > 2 else "")
    if len(argv) >= 2 and argv[0] == "assets":
        return assets(Path(argv[1]).resolve())
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
