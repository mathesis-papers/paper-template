"""``./tbook new-book`` and ``./tbook new-chapter``: scaffold books and chapters."""

from __future__ import annotations

import datetime
import re
import shutil
from pathlib import Path

from . import config, paths
from .summary import parse_summary

TEMPLATE = paths.TEMPLATES / "book"


def _toml_str(v: str) -> str:
    return '"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _table(values: dict[str, str]) -> str:
    return "\n".join(f"{lang} = {_toml_str(text)}" for lang, text in values.items())


def new_book(slug: str, titles: dict[str, str], *, langs: list[str] | None = None, author: str = "",
             code: str = "", subtitles: dict[str, str] | None = None) -> Path:
    if not config.SLUG_RE.match(slug):
        raise config.ConfigError(f"slug {slug!r} must be kebab-case (a-z, 0-9, -)")
    site = config.load_site()
    langs = langs or list(site.languages)
    target = paths.BOOKS / slug
    if target.exists():
        raise config.ConfigError(f"{paths.rel(target)} already exists")
    for lang in langs:
        if lang not in titles:
            raise config.ConfigError(f"missing a title for the {lang!r} edition (use --title {lang}=…)")
    target.mkdir(parents=True)
    (target / "assets").mkdir()
    (target / "assets" / ".gitkeep").write_text("")
    for lang in langs:
        src = TEMPLATE / (lang if (TEMPLATE / lang).exists() else "en")
        shutil.copytree(src, target / lang)
        if lang not in ("zh", "en"):
            readme = target / lang / "README.md"
            readme.write_text(readme.read_text(encoding="utf-8").replace(
                "Every theorem", f"<!-- TODO: translate to {lang} -->\nEvery theorem"), encoding="utf-8")
    text = (TEMPLATE / "book.toml").read_text(encoding="utf-8")
    code = code or slug.upper().replace("-", "//", 1)
    text = (text.replace("{{AUTHOR}}", author or "The Omega Institute")
            .replace("{{EDITIONS}}", ", ".join(_toml_str(lang) for lang in langs))
            .replace("{{CODE}}", code)
            .replace("{{TITLES}}", _table({lang: titles[lang] for lang in langs}))
            .replace("{{SUBTITLES}}", _table({lang: (subtitles or {}).get(lang, "") for lang in langs}))
            .replace("{{DESCRIPTIONS}}", _table({lang: "" for lang in langs}))
            .replace("{{DATE}}", datetime.date.today().isoformat()))
    (target / "book.toml").write_text(text, encoding="utf-8")
    return target


CHAPTER_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def new_chapter(slug: str, name: str, titles: dict[str, str]) -> list[Path]:
    """Append ``- [title](name.md)`` to every edition's SUMMARY and create the files."""
    if not CHAPTER_RE.match(name):
        raise config.ConfigError(f"chapter file name {name!r} must be kebab-case")
    book = config.load_book(slug)
    created = []
    for ed in book.editions:
        title = titles.get(ed.lang) or titles.get("*")
        if not title:
            raise config.ConfigError(f"missing a title for the {ed.lang!r} edition (use --title {ed.lang}=…)")
        md = ed.dir / f"{name}.md"
        if md.exists():
            raise config.ConfigError(f"{paths.rel(md)} already exists")
        parse_summary(ed.summary)  # validate before editing
        summary = ed.summary.read_text(encoding="utf-8").rstrip("\n")
        summary += f"\n- [{title}]({name}.md)\n"
        ed.summary.write_text(summary, encoding="utf-8")
        md.write_text(f"# {title}\n\n", encoding="utf-8")
        created.append(md)
    return created
