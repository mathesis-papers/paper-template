"""Load ``site.toml``, ``books/<slug>/book.toml`` and the i18n string tables."""

from __future__ import annotations

import os
import re
import subprocess
import tomllib
from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

from . import paths

SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
LANG_RE = re.compile(r"^[a-z]{2,3}(?:-[A-Za-z0-9]+)*$")
PDF_VARIANTS = ("screen", "print")


class ConfigError(Exception):
    pass


Localized = dict[str, str]


def localized(value: Any, where: str) -> Localized:
    """Accept either a plain string (same in all languages) or a {lang: text} table."""
    if value is None:
        return {}
    if isinstance(value, str):
        return {"*": value}
    if isinstance(value, dict) and all(isinstance(v, str) for v in value.values()):
        return dict(value)
    raise ConfigError(f"{where}: expected a string or a table of language = \"text\"")


def pick(text: Localized, lang: str, fallback: list[str] | None = None) -> str:
    """Return the text for ``lang``, falling back to '*' and then to the fallback languages."""
    if lang in text:
        return text[lang]
    if "*" in text:
        return text["*"]
    for other in fallback or []:
        if other in text:
            return text[other]
    return next(iter(text.values()), "")


# --------------------------------------------------------------------------- i18n


def _deep_merge(base: dict, extra: dict) -> dict:
    out = dict(base)
    for key, value in extra.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


@lru_cache(maxsize=None)
def i18n(lang: str) -> dict[str, Any]:
    """Strings for ``lang``: theme/i18n/<lang>.toml overridden by i18n/<lang>.toml.

    An unknown language falls back to English so a new edition still builds; ``check``
    reports the missing table.
    """
    table: dict[str, Any] = {}
    base = paths.I18N_THEME / f"{lang}.toml"
    if not base.exists():
        base = paths.I18N_THEME / "en.toml"
    with base.open("rb") as fh:
        table = tomllib.load(fh)
    local = paths.I18N_LOCAL / f"{lang}.toml"
    if local.exists():
        with local.open("rb") as fh:
            table = _deep_merge(table, tomllib.load(fh))
    return table


def has_i18n(lang: str) -> bool:
    return (paths.I18N_THEME / f"{lang}.toml").exists() or (paths.I18N_LOCAL / f"{lang}.toml").exists()


def s(lang: str, dotted: str) -> str:
    """Look up an i18n string such as ``s('zh', 'env.theorem')``."""
    node: Any = i18n(lang)
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            node = None
            break
        node = node[part]
    if node is None and lang != "en":
        return s("en", dotted)
    return "" if node is None else str(node)


def bcp47(lang: str) -> str:
    return s(lang, "meta.bcp47") or lang


# --------------------------------------------------------------------------- site


@dataclass
class Site:
    root: Path
    repo: str
    base_url: str
    languages: list[str]
    title: Localized
    tagline: Localized
    trureturing_repo: str
    trureturing_branch: str
    book_order: list[str]
    raw: dict[str, Any] = field(repr=False, default_factory=dict)

    @property
    def default_language(self) -> str:
        return self.languages[0]

    def text(self, value: Localized, lang: str) -> str:
        return pick(value, lang, self.languages)

    def book_url(self, slug: str, *parts: str) -> str:
        """Absolute public URL of a path under the published site (may be '' if unknown)."""
        if not self.base_url:
            return ""
        tail = "/".join(p.strip("/") for p in (slug, *parts) if p)
        return self.base_url.rstrip("/") + "/" + tail


def _git_remote_repo(root: Path) -> str:
    try:
        url = subprocess.run(
            ["git", "-C", str(root), "remote", "get-url", "origin"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""
    m = re.search(r"github\.com[:/]([^/]+/[^/.]+?)(?:\.git)?$", url)
    if m:
        return m.group(1)
    m = re.search(r"/git/([^/]+/[^/.]+?)(?:\.git)?$", url)  # local proxies such as http://host/git/owner/name
    return m.group(1) if m else ""


def pages_base_url(repo: str) -> str:
    if not repo or "/" not in repo:
        return ""
    owner, name = repo.split("/", 1)
    if name.lower() == f"{owner.lower()}.github.io":
        return f"https://{owner.lower()}.github.io/"
    return f"https://{owner.lower()}.github.io/{name}/"


@lru_cache(maxsize=1)
def load_site() -> Site:
    if not paths.SITE_TOML.exists():
        raise ConfigError("site.toml not found at the repository root")
    with paths.SITE_TOML.open("rb") as fh:
        raw = tomllib.load(fh)
    site = raw.get("site", {})
    tru = raw.get("trureturing", {})
    repo = os.environ.get("TBOOK_REPO") or site.get("repo") or os.environ.get("GITHUB_REPOSITORY") or _git_remote_repo(paths.ROOT)
    base_url = os.environ.get("TBOOK_BASE_URL") or site.get("base_url") or pages_base_url(repo)
    if base_url and not base_url.endswith("/"):
        base_url += "/"
    languages = list(site.get("languages") or ["zh", "en"])
    for lang in languages:
        if not LANG_RE.match(lang):
            raise ConfigError(f"site.toml: invalid language code {lang!r}")
    return Site(
        root=paths.ROOT,
        repo=repo,
        base_url=base_url,
        languages=languages,
        title=localized(site.get("title"), "site.title") or {"*": "Books"},
        tagline=localized(site.get("tagline"), "site.tagline"),
        trureturing_repo=tru.get("repo", "the-omega-institute/trureturing"),
        trureturing_branch=tru.get("branch", "dev"),
        book_order=list(raw.get("books", {}).get("order", [])),
        raw=raw,
    )


# --------------------------------------------------------------------------- books


@dataclass
class Edition:
    book: "Book"
    lang: str

    @property
    def dir(self) -> Path:
        return self.book.dir / self.lang

    @property
    def summary(self) -> Path:
        return self.dir / "SUMMARY.md"

    @property
    def primary(self) -> bool:
        return self.lang == self.book.languages[0]

    @property
    def bcp47(self) -> str:
        return bcp47(self.lang)

    @property
    def key(self) -> str:
        return f"{self.book.slug}/{self.lang}"

    def text(self, value: Localized) -> str:
        return pick(value, self.lang, self.book.languages)

    @property
    def title(self) -> str:
        return self.text(self.book.title)

    @property
    def subtitle(self) -> str:
        return self.text(self.book.subtitle)

    @property
    def description(self) -> str:
        return self.text(self.book.description)


@dataclass
class Book:
    slug: str
    dir: Path
    version: str
    title: Localized
    subtitle: Localized
    description: Localized
    authors: list[str]
    license: str
    languages: list[str]
    code: str
    date: str
    isbn: Localized
    outputs_html: bool
    outputs_pdf: list[str]
    outputs_epub: bool
    pdf: dict[str, Any]
    epub: dict[str, Any]
    raw: dict[str, Any] = field(repr=False, default_factory=dict)
    editions: list[Edition] = field(default_factory=list)

    def edition(self, lang: str) -> Edition:
        for ed in self.editions:
            if ed.lang == lang:
                return ed
        raise ConfigError(f"book {self.slug} has no {lang!r} edition")

    @property
    def primary(self) -> Edition:
        return self.editions[0]

    def artifact(self, lang: str, kind: str, variant: str = "") -> str:
        """Canonical download file name, e.g. example-monograph-0.1.0-zh-screen.pdf."""
        stem = f"{self.slug}-{self.version}-{lang}"
        if kind == "pdf":
            return f"{stem}-{variant or 'screen'}.pdf"
        if kind == "epub":
            return f"{stem}.epub"
        raise ValueError(kind)

    # Media directories owned by the book.
    @property
    def viz_dir(self) -> Path:
        return self.dir / "viz"

    @property
    def slides_dir(self) -> Path:
        return self.dir / "slides"

    @property
    def films_dir(self) -> Path:
        return self.dir / "films"

    @property
    def assets_dir(self) -> Path:
        return self.dir / "assets"


def load_book(slug_or_dir: str | Path) -> Book:
    bdir = Path(slug_or_dir)
    if not bdir.is_absolute():
        bdir = paths.BOOKS / str(slug_or_dir)
    slug = bdir.name
    toml_path = bdir / "book.toml"
    if not toml_path.exists():
        raise ConfigError(f"{paths.rel(toml_path)} not found")
    if not SLUG_RE.match(slug):
        raise ConfigError(f"book directory name {slug!r} must be kebab-case (a-z, 0-9, -)")
    with toml_path.open("rb") as fh:
        raw = tomllib.load(fh)
    meta = raw.get("book", {})
    outputs = raw.get("outputs", {})
    where = paths.rel(toml_path)
    languages = list(meta.get("editions") or load_site().languages)
    if not languages:
        raise ConfigError(f"{where}: book.editions must list at least one language")
    for lang in languages:
        if not LANG_RE.match(lang):
            raise ConfigError(f"{where}: invalid edition language {lang!r}")
    pdf_variants = outputs.get("pdf", list(PDF_VARIANTS))
    if pdf_variants is True:
        pdf_variants = list(PDF_VARIANTS)
    elif pdf_variants is False:
        pdf_variants = []
    for v in pdf_variants:
        if v not in PDF_VARIANTS:
            raise ConfigError(f"{where}: outputs.pdf entries must be among {PDF_VARIANTS}, got {v!r}")
    title = localized(meta.get("title"), f"{where} book.title")
    if not title:
        raise ConfigError(f"{where}: book.title is required")
    book = Book(
        slug=slug,
        dir=bdir,
        version=str(meta.get("version", "0.1.0")),
        title=title,
        subtitle=localized(meta.get("subtitle"), f"{where} book.subtitle"),
        description=localized(meta.get("description"), f"{where} book.description"),
        authors=list(meta.get("authors", [])),
        license=str(meta.get("license", "")),
        languages=languages,
        code=str(meta.get("code", slug.upper().replace("-", "//", 1))),
        date=str(meta.get("date") or date.today().isoformat()),
        isbn=localized(meta.get("isbn"), f"{where} book.isbn"),
        outputs_html=bool(outputs.get("html", True)),
        outputs_pdf=list(pdf_variants),
        outputs_epub=bool(outputs.get("epub", True)),
        pdf=dict(raw.get("pdf", {})),
        epub=dict(raw.get("epub", {})),
        raw=raw,
    )
    book.editions = [Edition(book, lang) for lang in languages]
    return book


def book_slugs() -> list[str]:
    if not paths.BOOKS.exists():
        return []
    found = sorted(p.name for p in paths.BOOKS.iterdir() if (p / "book.toml").exists())
    order = [s for s in load_site().book_order if s in found]
    return order + [s for s in found if s not in order]


def load_books(only: list[str] | None = None) -> list[Book]:
    slugs = book_slugs()
    if only:
        missing = [s for s in only if s not in slugs]
        if missing:
            raise ConfigError(f"unknown book(s): {', '.join(missing)}; known: {', '.join(slugs) or 'none'}")
        slugs = [s for s in slugs if s in only]
    return [load_book(s) for s in slugs]
