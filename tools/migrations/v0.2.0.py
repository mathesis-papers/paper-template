"""v0.2.0: films build only the outputs film.json lists; film.json must list narrated_720p and cover.

Changes (books/*/films/*/film.json, repository-owned):
- adds the missing ``outputs.narrated_720p`` and ``outputs.cover`` with their default file names
  (``./tbook check`` now requires both: the players play the 720p narrated video, the films page shows the cover);
- removes ``release_tag`` and ``published_tag`` (per-film releases ended; films are built with the site).
The outputs a film already lists stay as they are, so an existing film keeps its 1080p and music-only videos.

Notes only (nothing is changed): adopting the new default of a film (720p narrated only); hiding the template's
example books with site.toml [books].hide; granting ``pages: read`` to the repository's own workflows that call
ci.yml.
"""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

LEGACY_KEYS = ("release_tag", "published_tag")
OPTIONAL_1080P_OR_MUSIC = ("narrated", "music_only", "music_only_720p")


def _default_outputs(slug: str, num: str, meta: dict) -> dict[str, str]:
    from tbook import film  # the new template's module (see tools/migrations/README.md)

    narration = (meta.get("narration") or {}).get("language", "en") if isinstance(meta.get("narration"), dict) else "en"
    subtitles = meta.get("subtitles") if isinstance(meta.get("subtitles"), list) else None
    return film.default_outputs(slug, num, narration, subtitles)


def _films(root: Path) -> list[Path]:
    return sorted(root.glob("books/*/films/*/film.json"))


def _migrate_film(root: Path, path: Path) -> list[str]:
    rel = path.relative_to(root).as_posix()
    try:
        meta = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [f"{rel}: not readable as JSON ({exc}); fix it by hand, then run ./tbook check"]
    if not isinstance(meta, dict):
        return [f"{rel}: not a JSON object; fix it by hand"]
    slug = path.parents[2].name
    m = re.match(r"(\d{3})-", path.parent.name)
    num = m.group(1) if m else "000"
    changes: list[str] = []
    outputs = meta.get("outputs")
    if outputs is None:
        outputs = {}
    if not isinstance(outputs, dict):
        return [f"{rel}: outputs is not an object; fix it by hand (it must list narrated_720p and cover)"]
    defaults = _default_outputs(slug, num, meta)
    for key in ("narrated_720p", "cover"):
        if not outputs.get(key):
            outputs[key] = defaults[key]
            changes.append(f"outputs.{key} = {defaults[key]}")
    meta["outputs"] = outputs
    for key in LEGACY_KEYS:
        if key in meta:
            del meta[key]
            changes.append(f"removed {key}")
    notes = []
    if changes:
        path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        notes.append(f"{rel}: " + "; ".join(changes))
    extra = [k for k in OPTIONAL_1080P_OR_MUSIC if outputs.get(k)]
    if extra:
        notes.append(f"{rel}: still builds {', '.join(extra)} besides the 720p narrated video. To use the new default "
                     "(720p narrated only, about a tenth of the size on Pages), remove them from outputs and set "
                     'resolution to "1280x720@30"; keep them if readers should download them.')
    return notes


def _hide_note(root: Path) -> list[str]:
    examples = sorted(p.parent.name for p in root.glob("books/example-*/book.toml"))
    if not examples:
        return []
    try:
        site = tomllib.loads((root / "site.toml").read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return []
    hide = (site.get("books") or {}).get("hide") if isinstance(site.get("books"), dict) else None
    if hide:
        return []
    return [f"the template's example books ({', '.join(examples)}) are published with your books. To keep them "
            'for reference without publishing them, set hide = ["example-*"] under [books] in site.toml, remove '
            "them from [books].order and run ./tbook pin --refresh (docs/UPGRADING.md §6, skills/book-new)."]


def _pages_read_note(root: Path) -> list[str]:
    notes = []
    managed = {"ci.yml", "pages.yml", "release.yml", "lean-verify.yml", "trureturing-bump.yml", "template-sync.yml",
               "template-release.yml"}
    for wf in sorted((root / ".github" / "workflows").glob("*.y*ml")):
        if wf.name in managed:
            continue
        try:
            text = wf.read_text(encoding="utf-8")
        except OSError:
            continue
        if re.search(r"uses:\s*\./\.github/workflows/ci\.ya?ml", text) and not re.search(r"pages:\s*read", text):
            notes.append(f"{wf.relative_to(root).as_posix()} calls ci.yml: grant it pages: read (its build and media "
                         "jobs read the Pages address with actions/configure-pages).")
    return notes


def migrate(root: Path) -> list[str]:
    root = Path(root)
    notes: list[str] = []
    for path in _films(root):
        notes += _migrate_film(root, path)
    notes += _hide_note(root)
    notes += _pages_read_note(root)
    return notes or ["nothing to migrate"]
