"""PDF (Pandoc → Typst) and EPUB 3 (Pandoc, for Apple Books) pipeline.

Both outputs share one staging directory, ``build/stage/<slug>/<lang>/pandoc/``::

    book.md          every chapter in SUMMARY order (drafts skipped) + the verification ledger
    _book/…          files the chapters link to (book assets, edition-local images), by their
                     path relative to the book directory
    _theme/…         copies of theme/typst/*, theme/generated/tokens.typ and derived code themes
    meta.json        book/edition metadata read by theme/typst/book.typ
    main.typ         Pandoc's Typst output (PDF)
    cover.png        the EPUB cover (1600×2560, tbook.cover.render_cover)
    epub/…           EPUB-only inputs: stylesheet, metadata, colophon; pandoc.epub before post-processing

Staging (:func:`stage`):

* each chapter goes through :func:`tbook.render.chapter_markdown` with ``target="pandoc"``
  (environment divs, ``[@id]`` references, Lean permalinks, ``_book/`` paths);
* the chapter title (its first level-1 heading, or the SUMMARY title when the file has
  none) gets a stable id (``ch-<file stem>`` unless it has one) and ``.tr-chapter``
  attributes; prefix/suffix chapters are ``.unnumbered``; nested chapters (depth > 0)
  have every heading shifted down by their depth; SUMMARY part titles become
  ``.tr-part`` headings;
* chapters are separate pages in HTML but one document here, so names that are only unique
  per chapter are scoped: footnote labels become ``[^<chapter id>--<label>]``
  (:func:`scope_footnotes`), and every heading without an explicit id gets one
  (:func:`heading_slugs` — its mdBook / Pandoc slug, or ``<chapter id>--<slug>`` when another
  chapter already uses that slug);
* links between chapter files (``other.md``, ``other.md#x``, ``#x``) become internal ``#ids``
  (a heading slug resolves within the linked chapter, as in HTML); relative images of
  nested chapters are rebased onto the staging root and files inside the edition are
  copied to ``_book/<lang>/…`` (looked up by the decoded path, so ``<a b.png>`` and
  ``a%20b.png`` both work, and written percent-encoded); plain links to files (not
  images) cannot work inside a PDF or EPUB, so they point to the file's published copy
  on the site (``site.book_url``) or, without a known base URL, are dropped with a
  warning (their text is kept);
* :data:`tbook.mathrender.TEX_MACROS` is written at the top as ``\\newcommand`` definitions
  (expanded by Pandoc's ``latex_macros``; tr-env.lua gets them as ``tr-tex-macros`` for
  environment titles), so macros render as they do in HTML;
* the ledger from :func:`tbook.ledger.ledger_markdown` is appended as the last,
  unnumbered back-matter chapter.

The reader is Pandoc Markdown without ``citations``: ``[@id]`` is resolved by
:mod:`tbook.render` before Pandoc runs, and a bare ``@word`` in prose is text.

Rendering: ``tools/filters/tr-book.lua`` (book structure) and ``tools/filters/tr-env.lua``
(environments) run inside Pandoc. The PDF is compiled by the ``typst`` Python module with
``theme/typst/book.typ`` (``sys.inputs["tr-variant"]`` = ``screen`` | ``print``); the EPUB
is written by Pandoc with ``theme/epub/book.css`` and post-processed for Apple Books
(``META-INF/com.apple.ibooks.display-options.xml``, deterministic zip) and validated with
epubcheck when Java is available.

Environment variables: ``TBOOK_EPUBCHECK`` (``1`` default: validate and fail on errors;
``warn``: report only; ``0``: skip), ``SOURCE_DATE_EPOCH`` (overrides the date derived
from ``book.date``).
"""

from __future__ import annotations

import json
import os
import posixpath
import re
import shutil
import struct
import subprocess
import sys
import unicodedata
import uuid
import zipfile
import zlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, unquote

from . import config, lean, ledger, mathrender, mdscan, paths, render
from .model import OPEN, EditionModel, Env, load_edition
from .summary import chapter_prefix

# No `citations`: [@id] references are resolved by tbook.render before Pandoc runs, and a
# bare "@word" (or a leftover "[@x]") must stay text instead of becoming a Typst #cite.
READER = "markdown+gfm_auto_identifiers-citations"
FILTERS = paths.TOOLS / "filters"
TYPST_THEME = paths.THEME / "typst"
EPUB_THEME = paths.THEME / "epub"
FONT_CACHE = paths.CACHE / "fonts"
THEME_FONTS = TYPST_THEME / "fonts"


class PandocError(RuntimeError):
    pass


# --------------------------------------------------------------------------- strings
#
# Strings used only by the PDF/EPUB front matter. A key present in theme/i18n/<lang>.toml
# (or the downstream i18n/<lang>.toml) wins; these tables are the fallback until the keys
# are merged into the shared i18n files. Languages other than zh fall back to en.

LOCAL_STRINGS: dict[str, dict[str, str]] = {
    "zh": {
        "pdf.colophon": "版权信息",
        "pdf.date": "日期",
        "pdf.authors": "作者",
        "pdf.license": "许可",
        "pdf.isbn": "ISBN",
        "pdf.publisher": "出版",
        "pdf.edition": "版本说明",
        "pdf.variant_screen": "屏幕版（深色）",
        "pdf.variant_print": "印刷版（浅色）",
        "pdf.typeset": "排版",
        "pdf.typeset_value": "Pandoc 与 Typst，由 trureturing 书籍模板构建",
        "pdf.source": "源文件",
        "pdf.online": "在线阅读",
        "pdf.verified_statement": "本书共有 {n} 条形式结论（定理、引理、命题、推论），每一条都引用 trureturing 中已由 Lean 内核验证并冻结的声明；书末“形式化验证账本”逐条列出对应关系与永久链接。",
        "pdf.no_formal": "本书没有形式结论。",
        "pdf.open_statement": "明确标为开放的问题与猜想：{n} 条。书中不把它们当作已证结论使用。",
        "pdf.lean_label": "Lean",
        "cover.series": "TRURETURING · 形式化专著",
        "cover.stamp_caption": "条形式结论 · 内核验证",
        "cover.pinned": "冻结于",
        "epub.colophon": "版权信息",
    },
    "en": {
        "pdf.colophon": "Colophon",
        "pdf.date": "Date",
        "pdf.authors": "Authors",
        "pdf.license": "License",
        "pdf.isbn": "ISBN",
        "pdf.publisher": "Published by",
        "pdf.edition": "Edition",
        "pdf.variant_screen": "Screen edition (dark)",
        "pdf.variant_print": "Print edition (light)",
        "pdf.typeset": "Typeset with",
        "pdf.typeset_value": "Pandoc and Typst, built with the trureturing books template",
        "pdf.source": "Source",
        "pdf.online": "Read online",
        "pdf.verified_statement": "Formal results in this book (theorems, lemmas, propositions and corollaries): {n}. Each one cites a declaration in trureturing that the Lean kernel has verified and that is frozen; the verification ledger at the end lists them with permanent links.",
        "pdf.no_formal": "This book states no formal results.",
        "pdf.open_statement": "Open problems and conjectures, explicitly marked as such: {n}. The book never uses them as proved.",
        "pdf.lean_label": "Lean",
        "cover.series": "TRURETURING · FORMAL MONOGRAPH",
        "cover.stamp_caption": "formal results · kernel-verified",
        "cover.pinned": "frozen at",
        "epub.colophon": "Colophon",
    },
}


def t(lang: str, key: str, **fmt) -> str:
    """Localized string: shared i18n first, then :data:`LOCAL_STRINGS` (zh/en)."""
    text = config.s(lang, key)
    if not text:
        table = LOCAL_STRINGS.get(lang) or LOCAL_STRINGS.get(lang.split("-")[0]) or LOCAL_STRINGS["en"]
        text = table.get(key) or LOCAL_STRINGS["en"].get(key, key)
    return text.format(**fmt) if fmt else text


# --------------------------------------------------------------------------- tools


def pandoc_path() -> str:
    """The Pandoc executable: $PANDOC, the pypandoc_binary copy, then PATH."""
    env = os.environ.get("PANDOC")
    if env:
        return env
    try:
        import pypandoc  # type: ignore

        return pypandoc.get_pandoc_path()
    except (ImportError, OSError):
        pass
    found = shutil.which("pandoc")
    if not found:
        raise PandocError("pandoc not found: install requirements.txt (pypandoc_binary) or set $PANDOC")
    return found


# Pandoc warnings that are expected for this pipeline and only add noise.
_PANDOC_NOISE = (
    re.compile(r"Could not load translations for"),
    re.compile(r"data file translations/"),
    re.compile(r"has no translation defined"),
)


def run_pandoc(args: list[str], *, cwd: Path, env: dict | None = None) -> str:
    cmd = [pandoc_path(), *args]
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env={**os.environ, **(env or {})})
    lines = [ln for ln in proc.stderr.splitlines()
             if ln.strip() and not any(p.search(ln) for p in _PANDOC_NOISE) and not ln.startswith("  ")]
    if proc.returncode != 0:
        raise PandocError(f"pandoc failed ({proc.returncode}) in {paths.rel(cwd)}:\n{proc.stderr.strip()}")
    for ln in lines:
        print(f"  pandoc: {ln}", file=sys.stderr)
    return proc.stdout


def source_date_epoch(book: config.Book) -> int:
    env = os.environ.get("SOURCE_DATE_EPOCH")
    if env and env.isdigit():
        return int(env)
    try:
        d = datetime.strptime(book.date[:10], "%Y-%m-%d")
    except ValueError:
        return 0
    return int(d.replace(tzinfo=timezone.utc).timestamp())


# --------------------------------------------------------------------------- fonts


def _woff_to_sfnt(data: bytes) -> bytes:
    """Decode a WOFF 1.0 file into the TrueType/OpenType font it wraps (W3C WOFF §5)."""
    if data[:4] != b"wOFF":
        raise ValueError("not a WOFF 1.0 file")
    (flavor,) = struct.unpack(">I", data[4:8])
    (num,) = struct.unpack(">H", data[12:14])
    entries = []
    for i in range(num):
        tag, off, comp, orig, cks = struct.unpack(">4sIIII", data[44 + 20 * i:64 + 20 * i])
        raw = data[off:off + comp]
        if comp < orig:
            raw = zlib.decompress(raw)
        entries.append((tag, raw, cks))
    entries.sort(key=lambda e: e[0])
    es = 1
    while es * 2 <= num:
        es *= 2
    header = struct.pack(">IHHHH", flavor, num, es * 16, es.bit_length() - 1, num * 16 - es * 16)
    directory, body = bytearray(), bytearray()
    offset = 12 + 16 * num
    for tag, raw, cks in entries:
        directory += struct.pack(">4sIII", tag, cks, offset + len(body), len(raw))
        body += raw + b"\0" * (-len(raw) % 4)
    return bytes(header + directory + body)


# @fontsource packages (installed by npm for the site and slides) ship WOFF only; Typst
# needs TTF/OTF. When neither tools/fetch-fonts.sh, theme/typst/fonts nor the system
# provides a family, its Latin subset is unpacked into .cache/fonts-fontsource/ so the
# cyberpunk display/data faces still reach the PDF offline. CJK families are not
# converted (fontsource splits them into unicode-range shards); install fonts-noto-cjk
# or run tools/fetch-fonts.sh for those.
FONTSOURCE = {
    "Chakra Petch": ("chakra-petch", "ChakraPetch", (400, 500, 600, 700)),
    "JetBrains Mono": ("jetbrains-mono", "JetBrainsMono", (400, 600, 700)),
}
FONTSOURCE_CACHE = paths.CACHE / "fonts-fontsource"


def _font_files(dirs: list[Path]) -> list[Path]:
    out = []
    for d in dirs:
        if d.is_dir():
            out += sorted(p for p in d.rglob("*") if p.suffix.lower() in (".ttf", ".otf", ".ttc", ".otc"))
    return out


_FAMILIES: dict[tuple[str, ...], set[str]] = {}


def _families(dirs: list[Path]) -> set[str]:
    """Font families Typst sees with ``dirs`` plus system fonts (cached per process)."""
    key = tuple(str(d) for d in dirs)
    if key not in _FAMILIES:
        try:
            import typst  # type: ignore

            _FAMILIES[key] = set(typst.Fonts(include_embedded_fonts=False, font_paths=list(key)).families())
        except Exception:  # noqa: BLE001 - informational only
            _FAMILIES[key] = set()
    return _FAMILIES[key]


def font_dirs() -> list[Path]:
    """Font directories handed to Typst: .cache/fonts, theme/typst/fonts, fontsource fallbacks."""
    dirs = [d for d in (FONT_CACHE, THEME_FONTS) if d.is_dir()]
    have = _families(dirs)
    fs_root = paths.ROOT / "node_modules" / "@fontsource"
    use_fallback = False
    for family, (pkg, stem, weights) in FONTSOURCE.items():
        if family in have:
            continue
        for w in weights:
            src = fs_root / pkg / "files" / f"{pkg}-latin-{w}-normal.woff"
            dst = FONTSOURCE_CACHE / f"{stem}-{w}.ttf"
            if dst.exists():
                use_fallback = True
                continue
            if not src.exists():
                continue
            try:
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_bytes(_woff_to_sfnt(src.read_bytes()))
                use_fallback = True
            except (OSError, ValueError, zlib.error) as exc:
                print(f"  fonts: cannot convert {src.name}: {exc}", file=sys.stderr)
    return dirs + ([FONTSOURCE_CACHE] if use_fallback else [])


def epub_font_files() -> list[Path]:
    """Font files that may be embedded in the EPUB (fetched fonts first, then fallbacks)."""
    font_dirs()  # make sure the fontsource fallbacks exist when nothing better is installed
    found = _font_files([FONT_CACHE, THEME_FONTS])
    families = {(_font_face(p) or ("",))[0] for p in found}
    return found + [p for p in _font_files([FONTSOURCE_CACHE]) if (_font_face(p) or ("",))[0] not in families]


# --------------------------------------------------------------------------- staging


ATX_RE = re.compile(r"^(?P<indent> {0,3})(?P<hashes>#{1,6})(?P<rest>(?:[ \t].*)?)$")
ATTR_TAIL_RE = re.compile(r"\s*\{(?P<attrs>[^{}]*)\}\s*$")
CLOSING_HASHES_RE = re.compile(r"(?:^|\s+)#+\s*$")
SETEXT_RE = re.compile(r"^ {0,3}(?P<ch>=+|-+)[ \t]*$")
REFDEF_RE = re.compile(r"^(?P<lead> {0,3}\[(?:[^\]\\]|\\.)+\]:[ \t]*)(?P<url><[^>]*>|\S+)(?P<rest>.*)$")
NOT_PARAGRAPH_RE = re.compile(r"^(?: {4,}|\s*$|\s*[#>|<]|\s*:{3,}|\s*[-*+][ \t]|\s*\d+[.)][ \t]|\s*(?:`{3,}|~{3,}))")
SAFE_ID_RE = re.compile(r"[^A-Za-z0-9_-]+")
# Pandoc footnote labels: no whitespace, "^", "[" or "]".
FOOTNOTE_REF_RE = re.compile(r"\[\^(?P<label>[^\s^\[\]]+)\]")
FOOTNOTE_DEF_RE = re.compile(r"^ {0,3}\[\^(?P<label>[^\s^\[\]]+)\]:")
# Inline link or image (text kept), raw HTML tags and a trailing attribute block that
# mdscan cannot parse ({-}): what heading_slugs strips before slugifying.
_HEADING_LINK_RE = re.compile(r"!?\[((?:[^\[\]\\]|\\.)*)\]\([^)]*\)")
_HEADING_TAG_RE = re.compile(r"</?[A-Za-z][^>]*>")
_UNPARSED_ATTRS_RE = re.compile(r"\{[^{}]*\}\s*$")
_ATTR_BLOCK_RE = re.compile(r"\{([^{}\n]*)\}")
_ATTR_ID_RE = re.compile(r"(?:^|\s)#([^\s{}#.=\"']+)")
# Files a Pandoc image can embed (a reference definition to anything else is a plain link).
IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp")
# What a written destination percent-encodes, as tbook.render does: a fragment (whitespace,
# angle brackets, parentheses) and a decoded file path (also "%", "#", "?" and backslashes).
_DEST_UNSAFE_RE = re.compile(r"[\s<>()]")
_PATH_UNSAFE_RE = re.compile(r"[\s<>()%#?\\]")


def _url_quote(pattern: re.Pattern, text: str) -> str:
    return pattern.sub(lambda m: quote(m.group(), safe=""), text)


@dataclass
class Heading:
    index: int  # line index
    level: int
    text: str
    attrs: mdscan.Attrs | None


@dataclass
class StagedChapter:
    path: str  # relative to the edition
    id: str
    section: str
    depth: int
    title: str


@dataclass
class Stage:
    dir: Path
    book_md: Path
    chapters: list[StagedChapter] = field(default_factory=list)
    files: list[str] = field(default_factory=list)  # staged support files (relative)
    warnings: list[str] = field(default_factory=list)
    formal_count: int = 0
    open_count: int = 0
    meta: dict = field(default_factory=dict)


def _code_mask(lines: list[str]) -> list[bool]:
    """True for lines inside fenced code blocks (also in block quotes and list items) or HTML
    comments (never rewritten); fences are found exactly as :func:`tbook.mdscan.parse_blocks`
    finds them (:func:`tbook.mdscan.fence_end`)."""
    mask = [False] * len(lines)
    comment = False
    i = 0
    while i < len(lines):
        line = lines[i]
        if comment:
            mask[i] = True
            if "-->" in line:
                comment = False
            i += 1
            continue
        end = mdscan.fence_end(lines, i)
        if end is not None:
            mask[i:end + 1] = [True] * (end + 1 - i)
            i = end + 1
            continue
        stripped = line.lstrip()
        if stripped.startswith("<!--") and "-->" not in stripped[4:]:
            comment = True
            mask[i] = True
        i += 1
    return mask


def normalize_setext(md: str) -> str:
    """Rewrite setext headings (``Title`` + ``===``/``---``) as ATX so later passes see one form."""
    lines = md.split("\n")
    mask = _code_mask(lines)
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if (not mask[i] and i + 1 < len(lines) and not mask[i + 1] and SETEXT_RE.match(lines[i + 1])
                and not NOT_PARAGRAPH_RE.match(line) and (i == 0 or not lines[i - 1].strip())):
            level = 1 if SETEXT_RE.match(lines[i + 1]).group("ch")[0] == "=" else 2
            out.append("#" * level + " " + line.strip())
            i += 2
            continue
        out.append(line)
        i += 1
    return "\n".join(out)


def parse_heading(line: str) -> tuple[int, str, mdscan.Attrs | None] | None:
    m = ATX_RE.match(line)
    if not m:
        return None
    level = len(m.group("hashes"))
    rest = m.group("rest").strip()
    attrs = None
    am = ATTR_TAIL_RE.search(rest)
    if am:
        try:
            attrs = mdscan.parse_attrs(am.group("attrs"))
            rest = rest[:am.start()].rstrip()
        except mdscan.AttrError:
            attrs = None
    rest = CLOSING_HASHES_RE.sub("", rest).strip() if rest.strip("#").strip() or not rest else ""
    return level, rest, attrs


def format_heading(level: int, text: str, attrs: mdscan.Attrs | None) -> str:
    line = "#" * level + " " + text
    if attrs and (attrs.id or attrs.classes or attrs.kv):
        line += " " + attrs.to_pandoc()
    return line


def find_headings(md: str) -> list[Heading]:
    lines = md.split("\n")
    mask = _code_mask(lines)
    out = []
    for i, line in enumerate(lines):
        if mask[i]:
            continue
        h = parse_heading(line)
        if h:
            out.append(Heading(i, h[0], h[1], h[2]))
    return out


def chapter_slug(path: str) -> str:
    stem = path[:-3] if path.endswith(".md") else path
    return "ch-" + (SAFE_ID_RE.sub("-", stem).strip("-").lower() or "chapter")


def scope_footnotes(md: str, prefix: str) -> str:
    """Rename the footnotes defined in this chapter: ``[^n]`` → ``[^<prefix>--n]``.

    Each chapter is its own page in HTML, so ``[^1]`` is reused from chapter to chapter;
    book.md holds every chapter and Pandoc would give every ``[^1]`` the text of the last
    definition in the book. Only labels defined in the chapter are renamed; fenced code,
    HTML comments and inline code are left alone.
    """
    lines = md.split("\n")
    mask = _code_mask(lines)
    labels = {m.group("label") for i, line in enumerate(lines)
              if not mask[i] and (m := FOOTNOTE_DEF_RE.match(line))}
    if not labels:
        return md

    def repl(m: re.Match) -> str:
        label = m.group("label")
        return f"[^{prefix}--{label}]" if label in labels else m.group(0)

    return "\n".join(line if mask[i] else mdscan.sub_outside_code(FOOTNOTE_REF_RE, repl, line)
                     for i, line in enumerate(lines))


def _heading_plain(text: str) -> str:
    """Heading Markdown as the plain text its automatic id is made from (approximately)."""
    text = FOOTNOTE_REF_RE.sub("", text)
    text = _HEADING_LINK_RE.sub(r"\1", text)
    text = _HEADING_TAG_RE.sub("", text)
    text = re.sub(r"(?<!\w)_+|_+(?!\w)", "", text)  # _emphasis_ (intraword "_" stays)
    return re.sub(r"\\(.)", r"\1", text)


def heading_slugs(text: str) -> list[str]:
    """The automatic ids of a heading before de-duplication: mdBook's (the HTML edition,
    which authors link to) first, then Pandoc's ``gfm_auto_identifiers`` when it differs."""
    plain = _heading_plain(text)
    mdbook = "".join("-" if ch.isspace() else ch for ch in plain.strip().lower()
                     if ch.isalnum() or ch in "-_" or ch.isspace())
    gfm = "".join("-" if ch.isspace() else ch for ch in plain.lower()
                  if ch.isspace() or ch.isalnum() or ch in "-_"
                  or unicodedata.category(ch) in ("Mn", "Mc", "Me", "Pc"))
    return [s for i, s in enumerate((mdbook, gfm)) if s and s not in (mdbook, gfm)[:i]]


def _unique(base: str, used: set[str]) -> str:
    """``base``, else ``base-1``, ``base-2``… (mdBook's and Pandoc's de-duplication)."""
    candidate, n = base, 1
    while candidate in used:
        candidate, n = f"{base}-{n}", n + 1
    used.add(candidate)
    return candidate


def _safe_id(slug: str) -> str:
    """A slug as an id Pandoc's attribute syntax accepts (starts with a letter or digit)."""
    return "".join(ch for ch in slug if ch.isalnum() or ch in "-_").lstrip("-_") or "section"


def explicit_ids(md: str) -> set[str]:
    """Ids written as ``{#id …}`` attributes (headings, divs, spans) in a chapter."""
    out: set[str] = set()
    for block in _ATTR_BLOCK_RE.finditer(md):
        out.update(_ATTR_ID_RE.findall(block.group(1)))
    return out


@dataclass
class HeadingIds:
    """Ids given to the headings without one, and the fragments that reach them."""

    by_line: dict[str, dict[int, str]] = field(default_factory=dict)  # chapter → line → id
    anchors: dict[str, dict[str, str]] = field(default_factory=dict)  # chapter → fragment → id


def assign_heading_ids(chapters: list[tuple[str, str]], chapter_ids: dict[str, str],
                       taken: set[str]) -> HeadingIds:
    """Give every heading without an explicit id one that is unique in the whole book.

    ``chapters`` is ``(path, rendered Markdown)`` in book order; ``taken`` holds the ids
    already in use (environments, chapters, parts…) and receives the new ones. A heading
    keeps its slug when no other chapter uses it, otherwise it becomes
    ``<chapter id>--<slug>``. ``anchors`` resolves a fragment within its chapter as the
    chapter's HTML page does (its own explicit ids first, then its automatic heading ids),
    so ``other.md#summary`` reaches the "Summary" of ``other.md``, not the first in the book.
    """
    parsed = [(posixpath.normpath(path), md, find_headings(normalize_setext(md))) for path, md in chapters]
    for _, _, heads in parsed:
        taken |= {h.attrs.id for h in heads if h.attrs and h.attrs.id}
    out = HeadingIds()
    for path, md, heads in parsed:
        cid = chapter_ids[path]
        own = explicit_ids(md)
        lines = out.by_line.setdefault(path, {})
        anchors = out.anchors.setdefault(path, {})
        local: set[str] = set()  # automatic ids of this chapter, de-duplicated as mdBook does
        title = next((h for h in heads if h.level == 1), None)
        for h in heads:
            if h.attrs and h.attrs.id:
                continue
            if h.attrs is None and _UNPARSED_ATTRS_RE.search(h.text):
                continue  # `{-}` and similar: left to Pandoc
            slugs = [_unique(s, local) for s in heading_slugs(h.text)]
            if h is title:
                new = cid  # restructure_chapter gives the chapter title its id
            else:
                base = _safe_id(slugs[0] if slugs else "")
                new = _unique(base if base not in taken else f"{cid}--{base}", taken)
                lines[h.index] = new
            for s in slugs:
                if s not in own:
                    anchors.setdefault(s, new)
    return out


class _Linker:
    """Rewrites a chapter's relative links for the flattened book.md at the staging root.

    ``anchors`` (chapter → fragment → id, :func:`assign_heading_ids`) resolves heading
    fragments per chapter; ``env_ids`` are the environment ids that ``[@id]`` references
    point to (never re-resolved); ``online`` is the published edition's URL
    (``site.book_url(slug, lang)``, '' when unknown), where plain links to files point.
    """

    def __init__(self, stage_dir: Path, edition: config.Edition, chapter_ids: dict[str, str],
                 warnings: list[str], files: set[str], *, anchors: dict[str, dict[str, str]] | None = None,
                 env_ids: set[str] | None = None, online: str = ""):
        self.stage_dir = stage_dir
        self.edition = edition
        self.chapter_ids = chapter_ids
        self.warnings = warnings
        self.files = files
        self.anchors = anchors or {}
        self.env_ids = env_ids or set()
        self.online = online.rstrip("/")

    def anchor(self, chapter: str, frag: str) -> str:
        """The book-wide id that ``frag`` names on the page of ``chapter``."""
        return self.anchors.get(chapter, {}).get(unquote(frag), frag)

    def published(self, rel: str, hash_: str, frag: str, chapter_path: str, url: str) -> str | None:
        """Absolute URL of the HTML edition's copy of ``rel`` (a plain link to a file: Pandoc
        embeds images only, so a relative link would be dead in the PDF and break the EPUB)."""
        if self.online:
            return f"{self.online}/{quote(rel)}" + (hash_ + frag if hash_ else "")
        self.warnings.append(f"{self.edition.key}/{chapter_path}: link to the file {url} needs the site's "
                             "base_url (site.toml) in PDF/EPUB; kept as text")
        return None

    def target(self, url: str, chapter_path: str, *, image: bool | None) -> str | None:
        """New URL, or None to drop the link (keeping its text).

        ``url`` is the destination as written: ``<…>`` (may contain spaces) or a plain,
        possibly percent-encoded one (:mod:`tbook.render` writes ``<…>`` that way). Files are
        looked up by the decoded path; a staged path is written percent-encoded. ``image``
        is True for images, False for links and None for reference definitions (decided by
        the file type).
        """
        raw = url
        if url.startswith("<") and url.endswith(">"):
            url = url[1:-1]
        if render.EXTERNAL_RE.match(url) and not url.startswith("#"):
            return raw
        path_part, hash_, frag = url.partition("#")
        if not path_part:
            if frag and unquote(frag) not in self.env_ids:
                return "#" + self.anchor(posixpath.normpath(chapter_path), frag)
            return raw
        frag = _url_quote(_DEST_UNSAFE_RE, frag)
        tail = hash_ + frag if hash_ else ""
        path = unquote(path_part)
        chapter_dir = posixpath.dirname(chapter_path)
        joined = posixpath.normpath(posixpath.join(chapter_dir, path))
        embed = image if image is not None else joined.lower().endswith(IMAGE_SUFFIXES)
        if joined == "_book" or joined.startswith("_book/"):
            if not embed:
                return self.published(joined, hash_, frag, chapter_path, url)
            return _url_quote(_PATH_UNSAFE_RE, joined) + tail
        if joined.startswith(("../", "/")) or joined == "..":
            self.warnings.append(f"{self.edition.key}/{chapter_path}: link leaves the edition: {url}")
            return raw
        if joined in self.chapter_ids:
            return "#" + (self.anchor(joined, frag) if frag else self.chapter_ids[joined])
        if joined.endswith(".md") and image is False:
            self.warnings.append(f"{self.edition.key}/{chapter_path}: link to {path}, which is not a "
                                 "chapter of this edition; kept as text")
            return None
        src = self.edition.dir / joined
        if src.is_file():
            if not embed:
                return self.published(joined, hash_, frag, chapter_path, url)
            staged = posixpath.join("_book", self.edition.lang, joined)
            dst = self.stage_dir / staged
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            self.files.add(staged)
            return _url_quote(_PATH_UNSAFE_RE, staged) + tail
        self.warnings.append(f"{self.edition.key}/{chapter_path}: linked file not found: {url}")
        return raw

    def rewrite_line(self, line: str, chapter_path: str) -> str:
        def link(m: re.Match) -> str:
            image = bool(m.group("bang"))
            new = self.target(m.group("url"), chapter_path, image=image)
            if new is None:
                return m.group("text")
            return f"{m.group('bang')}[{m.group('text')}]({new}{m.group('title') or ''})"

        rd = REFDEF_RE.match(line)
        if rd and not line.lstrip().startswith("[^"):
            raw = rd.group("url")
            new = self.target(raw, chapter_path, image=None)  # keep reference definitions as links
            return f"{rd.group('lead')}{new or raw}{rd.group('rest')}"
        return mdscan.sub_outside_code(render.LINK_RE, link, line)


def restructure_chapter(md: str, *, chapter_path: str, depth: int, chapter_id: str, title: str,
                        classes: list[str], kv: dict[str, str], linker: _Linker | None,
                        heading_ids: dict[int, str] | None = None) -> str:
    """Shift headings by ``depth``, decorate the chapter title heading, rewrite links.

    ``heading_ids`` maps line numbers (of the setext-normalized text) to the ids that
    :func:`assign_heading_ids` gave headings without one.
    """
    md = normalize_setext(md)
    lines = md.split("\n")
    mask = _code_mask(lines)
    title_done = False
    out: list[str] = []
    for i, line in enumerate(lines):
        if mask[i]:
            out.append(line)
            continue
        h = parse_heading(line)
        if h:
            level, text, attrs = h
            if linker:
                text = linker.rewrite_line(text, chapter_path)
            if not title_done and level == 1:
                attrs = attrs or mdscan.Attrs()
                attrs.id = attrs.id or chapter_id
                attrs.classes = [*classes, *[c for c in attrs.classes if c not in classes]]
                attrs.kv = {**kv, **attrs.kv}
                title_done = True
            elif heading_ids and i in heading_ids and not (attrs and attrs.id):
                attrs = attrs or mdscan.Attrs()
                attrs.id = heading_ids[i]
            out.append(format_heading(min(6, level + depth), text, attrs))
            continue
        out.append(linker.rewrite_line(line, chapter_path) if linker else line)
    if not title_done:
        attrs = mdscan.Attrs(id=chapter_id, classes=list(classes), kv=dict(kv))
        out = [format_heading(min(6, 1 + depth), title, attrs), ""] + out
    return "\n".join(out).strip("\n") + "\n"


def verified_formal_envs(model: EditionModel, lock: lean.Lock | None) -> list[Env]:
    """Formal results shown with the green LEAN ✓: every Lean citation resolves in the lock to
    a frozen theorem (:func:`tbook.render.lean_verified`). Only these are counted in the ledger
    kicker, the colophon and on the cover; the others are UNVERIFIED (``check`` rejects them)."""
    return [e for e in model.formal_envs()
            if render.lean_verified([render.lean_view(g, lock) for g in e.lean])]


def _kicker(model: EditionModel, chapter, book: config.Book) -> str:
    if model.summary is None:
        return ""
    prefix = chapter_prefix(model.summary, chapter)
    if chapter.section == "numbered":
        return f"§ {int(prefix):02d}" if prefix.isdigit() else f"§ {prefix}"
    if chapter.section == "suffix":
        return f"§ {prefix}"
    return book.code


def stage_dir_for(book: config.Book, edition: config.Edition) -> Path:
    return paths.BUILD / "stage" / book.slug / edition.lang / "pandoc"


def stage(site: config.Site, book: config.Book, edition: config.Edition, model: EditionModel | None,
          lock: lean.Lock | None, out_dir: Path | None = None) -> Stage:
    """Write book.md, _book/, _theme/ and meta.json into the staging directory."""
    model = model if model is not None else load_edition(edition)
    out_dir = Path(out_dir) if out_dir else stage_dir_for(book, edition)
    # Clear what staging owns; main.typ and cover.png stay for inspection until rebuilt.
    for name in ("_book", "_theme", "epub"):
        if (out_dir / name).exists():
            shutil.rmtree(out_dir / name)
    for name in ("book.md", "meta.json"):
        (out_dir / name).unlink(missing_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    result = Stage(dir=out_dir, book_md=out_dir / "book.md")
    ctx = render.RenderContext(site=site, book=book, edition=edition, model=model, lock=lock, target="pandoc")
    rendered = [(doc, render.chapter_markdown(doc, ctx)) for doc in model.chapters]
    result.warnings += ctx.issues

    # Pass 1: one stable id per chapter title, then ids for the other headings.
    env_ids = {e.id for e in model.all_envs() + [m for ch in model.chapters for m in ch.media] if e.id}
    taken = set(env_ids)
    taken.add(ledger.LEDGER_ID)
    taken.add("tr-colophon")
    taken.update(f"tr-part-{n}" for n in range(1, len(rendered) + 1))
    chapter_ids: dict[str, str] = {}
    for doc, md in rendered:
        heads = [h for h in find_headings(normalize_setext(md)) if h.level == 1]
        cid = heads[0].attrs.id if heads and heads[0].attrs and heads[0].attrs.id else ""
        if not cid:
            base = cid = chapter_slug(doc.chapter.path)
            n = 2
            while cid in taken:
                cid, n = f"{base}-{n}", n + 1
        taken.add(cid)
        chapter_ids[posixpath.normpath(doc.chapter.path)] = cid
    heading_ids = assign_heading_ids([(doc.chapter.path, md) for doc, md in rendered], chapter_ids, taken)

    # Pass 2: restructure and concatenate.
    staged_files: set[str] = set()
    linker = _Linker(out_dir, edition, chapter_ids, result.warnings, staged_files, anchors=heading_ids.anchors,
                     env_ids=env_ids, online=site.book_url(book.slug, edition.lang))
    # Macros first: Pandoc's latex_macros expands them in all math that follows.
    pieces: list[str] = [mathrender.newcommands() + "\n"]
    prev_part = ""
    parts = 0
    for doc, md in rendered:
        ch = doc.chapter
        if ch.depth == 0:
            if ch.part and ch.part != prev_part:
                parts += 1
                attrs = mdscan.Attrs(id=f"tr-part-{parts}", classes=["tr-part", "unnumbered"],
                                     kv={"tr-section": "part", "tr-kicker": book.code})
                pieces.append(format_heading(1, ch.part, attrs) + "\n")
            prev_part = ch.part
        cid = chapter_ids[posixpath.normpath(ch.path)]
        classes = ["tr-chapter"] + ([] if ch.section == "numbered" else ["unnumbered"])
        kv = {"tr-section": ch.section, "tr-depth": str(ch.depth), "tr-kicker": _kicker(model, ch, book) if ch.depth == 0 else ""}
        if ch.depth == 0 and ch.section == "prefix":
            kv["epub:type"] = "preface"
        elif ch.depth == 0 and ch.section == "suffix":
            kv["epub:type"] = "appendix"
        path = posixpath.normpath(ch.path)
        pieces.append(restructure_chapter(scope_footnotes(md, cid), chapter_path=ch.path, depth=ch.depth,
                                          chapter_id=cid, title=ch.title, classes=classes, kv=kv, linker=linker,
                                          heading_ids=heading_ids.by_line.get(path)))
        heads = [h for h in find_headings(pieces[-1]) if h.attrs and h.attrs.id == cid]
        result.chapters.append(StagedChapter(path=ch.path, id=cid, section=ch.section, depth=ch.depth,
                                             title=heads[0].text if heads else ch.title))

    result.formal_count = len(verified_formal_envs(model, lock))
    result.open_count = len([e for e in model.all_envs() if e.kind in OPEN])
    ledger_md = ledger.ledger_markdown(model, lock)
    pieces.append(restructure_chapter(
        ledger_md, chapter_path=ledger.LEDGER_FILE, depth=0, chapter_id=ledger.LEDGER_ID,
        title=config.s(edition.lang, "ledger.title"),
        classes=["tr-chapter", "tr-ledger", "unnumbered"],
        kv={"tr-section": "back", "tr-depth": "0", "tr-kicker": f"LEAN ✓ {result.formal_count}",
            "epub:type": "appendix"},
        linker=None))
    result.chapters.append(StagedChapter(path=ledger.LEDGER_FILE, id=ledger.LEDGER_ID, section="back",
                                         depth=0, title=config.s(edition.lang, "ledger.title")))
    result.book_md.write_text("\n".join(pieces), encoding="utf-8")

    # Files the renderer collected from the book directory (../assets/…).
    book_dir = book.dir.resolve()
    for src in sorted(ctx.book_files):
        src = Path(src)
        try:
            rel = src.resolve().relative_to(book_dir).as_posix()
        except ValueError:
            continue
        if not src.is_file():
            if not src.exists():
                result.warnings.append(f"{edition.key}: linked book file not found: {rel}")
            continue
        dst = out_dir / "_book" / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        staged_files.add(f"_book/{rel}")
    result.files = sorted(staged_files)
    _stage_theme(out_dir)
    result.meta = book_meta(site, book, edition, model, lock, result)
    (out_dir / "meta.json").write_text(json.dumps(result.meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for w in result.warnings:
        print(f"  warning: {w}", file=sys.stderr)
    return result


# --------------------------------------------------------------------------- theme copies


def _stage_theme(out_dir: Path) -> None:
    """Copy the Typst theme so imports resolve inside the Typst root (the staging dir)."""
    dst = out_dir / "_theme" / "typst"
    dst.mkdir(parents=True, exist_ok=True)
    for p in sorted(TYPST_THEME.iterdir()):
        if p.is_file() and p.suffix in (".typ", ".typst", ".tmTheme", ".svg", ".png"):
            shutil.copy2(p, dst / p.name)
    gen = out_dir / "_theme" / "generated"
    gen.mkdir(parents=True, exist_ok=True)
    shutil.copy2(paths.GENERATED / "tokens.typ", gen / "tokens.typ")
    tokens = json.loads(paths.TOKENS.read_text(encoding="utf-8"))
    for variant, palette in (("screen", tokens["screen"]), ("print", tokens["paper"])):
        (dst / f"code-{variant}.tmTheme").write_text(code_theme(palette, variant), encoding="utf-8")


def _hex(colour: str) -> str:
    """#rrggbb for a token colour (rgba() is flattened to its rgb part)."""
    colour = colour.strip()
    if colour.startswith("#"):
        return colour
    m = re.match(r"rgba?\(([^)]*)\)", colour)
    if not m:
        raise ValueError(colour)
    r, g, b = (int(float(x)) for x in m.group(1).split(",")[:3])
    return f"#{r:02x}{g:02x}{b:02x}"


def code_theme(palette: dict, variant: str) -> str:
    """A TextMate theme for Typst's code highlighting, coloured from theme/tokens.json.

    Green and amber are reserved (Lean-verified / current focus), so code uses cyan,
    magenta, orange, blue and the neutral inks.
    """
    rules = [
        ("Comment", "comment", "dim", "italic"),
        ("Keyword", "keyword, storage, keyword.control, keyword.other", "magenta", ""),
        ("Operator", "keyword.operator, punctuation", "dim", ""),
        ("String", "string, string.quoted", "sigma" if variant == "screen" else "blue", ""),
        ("Number", "constant.numeric, constant.language, constant.character", "orange", ""),
        ("Function", "entity.name.function, support.function, meta.function-call", "cyan", ""),
        ("Type", "entity.name.type, support.type, storage.type, entity.name.class", "blue", ""),
        ("Variable", "variable, variable.parameter", "ink", ""),
        ("Tag", "entity.name.tag, markup.heading", "cyan", "bold"),
        ("Attribute", "entity.other.attribute-name", "orange", ""),
    ]

    def dict_xml(d: dict[str, str]) -> str:
        return "".join(f"<key>{k}</key><string>{v}</string>" for k, v in d.items())

    items = [f"<dict><key>settings</key><dict>{dict_xml({'foreground': _hex(palette['ink']), 'background': _hex(palette['panel-solid'])})}</dict></dict>"]
    for name, scope, colour, style in rules:
        settings = {"foreground": _hex(palette[colour])}
        if style:
            settings["fontStyle"] = style
        items.append(f"<dict><key>name</key><string>{name}</string><key>scope</key><string>{scope}</string>"
                     f"<key>settings</key><dict>{dict_xml(settings)}</dict></dict>")
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<!-- generated by tools/tbook/pandoc.py from theme/tokens.json — do not edit -->\n'
            '<plist version="1.0"><dict><key>name</key><string>trureturing-' + variant + '</string>'
            '<key>settings</key><array>' + "".join(items) + "</array></dict></plist>\n")


# --------------------------------------------------------------------------- metadata


def _region(bcp47: str) -> str:
    parts = bcp47.split("-")
    for p in parts[1:]:
        if len(p) == 2 and p.isalpha():
            return p.upper()
    return ""


def edition_isbn(book: config.Book, edition: config.Edition) -> str:
    return edition.text(book.isbn).strip() if book.isbn else ""


def edition_identifier(book: config.Book, edition: config.Edition) -> str:
    """ISBN when given, otherwise a deterministic urn:uuid (uuid5 of slug, language and version)."""
    isbn = edition_isbn(book, edition)
    if isbn:
        return "urn:isbn:" + re.sub(r"[^0-9Xx]", "", isbn)
    return "urn:uuid:" + str(uuid.uuid5(uuid.NAMESPACE_URL, f"trureturing-books:{book.slug}:{edition.lang}:{book.version}"))


def book_meta(site: config.Site, book: config.Book, edition: config.Edition, model: EditionModel,
              lock: lean.Lock | None, staged: Stage | None = None) -> dict:
    """Everything theme/typst/book.typ and cover.typ need, as plain JSON data."""
    lang = edition.lang
    formal = staged.formal_count if staged else len(verified_formal_envs(model, lock))
    opens = staged.open_count if staged else len([e for e in model.all_envs() if e.kind in OPEN])
    try:
        d = datetime.strptime(book.date[:10], "%Y-%m-%d")
        date = {"year": d.year, "month": d.month, "day": d.day, "iso": book.date[:10]}
    except ValueError:
        date = {"year": 1970, "month": 1, "day": 1, "iso": book.date}
    online = site.book_url(book.slug, lang) + "/" if site.base_url else ""
    s = lambda key: config.s(lang, key)  # noqa: E731
    return {
        "schema": "trureturing-books.pdf-meta.v1",
        "slug": book.slug,
        "lang": lang.split("-")[0],
        "bcp47": edition.bcp47,
        "region": _region(edition.bcp47),
        "cjk": lang.split("-")[0] in ("zh", "ja", "ko"),
        "title": edition.title,
        "subtitle": edition.subtitle,
        "description": edition.description,
        "authors": list(book.authors),
        "code": book.code,
        "version": book.version,
        "date": date,
        "license": book.license,
        "isbn": edition_isbn(book, edition),
        "identifier": edition_identifier(book, edition),
        "publisher": site.text(site.title, lang),
        "keywords": _keywords(book, edition),
        "paper": str(book.pdf.get("paper", "a4")),
        "online_url": online,
        "repo_url": f"https://github.com/{site.repo}" if site.repo else "",
        "formal_count": formal,
        "open_count": opens,
        "trureturing": {
            "repo": lock.repo if lock else site.trureturing_repo,
            "commit": lock.commit if lock else "",
            "short": lock.commit[:12] if lock else "",
            "url": lock.tree_url if lock else "",
        },
        "strings": {
            "lang_name": s("meta.name"),
            "lang_short": s("meta.short") or lang.upper(),
            "contents": s("ui.contents"),
            "version": s("ui.version"),
            "language": s("ui.language"),
            "pinned_at": s("ui.pinned_at"),
            "title_open": s("punct.title_open"),
            "title_close": s("punct.title_close"),
            "badge_lean": s("badge.lean"),
            "lean_label": t(lang, "pdf.lean_label"),
            "colophon": t(lang, "pdf.colophon"),
            "date": t(lang, "pdf.date"),
            "authors": t(lang, "pdf.authors"),
            "license": t(lang, "pdf.license"),
            "isbn": t(lang, "pdf.isbn"),
            "publisher": t(lang, "pdf.publisher"),
            "edition": t(lang, "pdf.edition"),
            "variant_screen": t(lang, "pdf.variant_screen"),
            "variant_print": t(lang, "pdf.variant_print"),
            "typeset": t(lang, "pdf.typeset"),
            "typeset_value": t(lang, "pdf.typeset_value"),
            "source": t(lang, "pdf.source"),
            "online": t(lang, "pdf.online"),
            "verified_statement": t(lang, "pdf.verified_statement", n=formal) if formal else t(lang, "pdf.no_formal"),
            "open_statement": t(lang, "pdf.open_statement", n=opens) if opens else "",
            "series": t(lang, "cover.series"),
            "stamp_caption": t(lang, "cover.stamp_caption"),
            "pinned_short": t(lang, "cover.pinned"),
        },
    }


def _keywords(book: config.Book, edition: config.Edition) -> list[str]:
    raw = book.raw.get("book", {}).get("keywords")
    if isinstance(raw, dict):
        raw = raw.get(edition.lang) or next(iter(raw.values()), [])
    words = [str(k) for k in raw] if isinstance(raw, list) else []
    for k in ("trureturing", "Lean 4"):
        if k not in words:
            words.append(k)
    return words


def _filter_meta(lang: str) -> list[str]:
    """Strings the Lua filters need that are not carried by the environment divs."""
    pairs = {
        "tr-punct-open": config.s(lang, "punct.title_open"),
        "tr-punct-close": config.s(lang, "punct.title_close"),
        "tr-lean-label": t(lang, "pdf.lean_label"),
        "tr-badge-lean-title": config.s(lang, "badge.lean_title"),
        "tr-badge-open-title": config.s(lang, "badge.open_title"),
        # Environment titles are read by a separate pandoc.read in tr-env.lua.
        "tr-tex-macros": mathrender.newcommands(),
    }
    out = []
    for k, v in pairs.items():
        out += ["--metadata", f"{k}={v}"]
    return out


def _filters() -> list[str]:
    return ["--lua-filter", str(FILTERS / "tr-book.lua"), "--lua-filter", str(FILTERS / "tr-env.lua")]


# --------------------------------------------------------------------------- PDF


def typst_source(site, book, edition, model, lock, staged: Stage | None = None,
                 stage_dir: Path | None = None) -> Stage:
    """Stage the edition and convert book.md to main.typ (variant-independent)."""
    staged = staged or stage(site, book, edition, model, lock, out_dir=stage_dir)
    run_pandoc([
        "book.md", "--from", READER, "--to", "typst",
        "--template", str((staged.dir / "_theme" / "typst" / "pandoc-template.typst")),
        "--output", "main.typ", "--wrap", "preserve",
        "--metadata", f"lang={edition.bcp47}",
        *_filter_meta(edition.lang), *_filters(),
    ], cwd=staged.dir, env={"SOURCE_DATE_EPOCH": str(source_date_epoch(book))})
    return staged


_TYPST_FONT_WARNING = re.compile(r"unknown font family: (.+)")


def compile_typst(main: Path, out_path: Path, *, root: Path, fmt: str = "pdf", ppi: float | None = None,
                  sys_inputs: dict[str, str] | None = None, timestamp: int | None = None) -> Path:
    """Compile with the typst Python module; font fallbacks are reported in one line."""
    import typst  # type: ignore

    out_path.parent.mkdir(parents=True, exist_ok=True)
    kwargs = dict(output=str(out_path), root=str(root), font_paths=[str(d) for d in font_dirs()],
                  format=fmt, sys_inputs=sys_inputs or {})
    if ppi:
        kwargs["ppi"] = ppi
    if timestamp:
        kwargs["timestamp"] = timestamp
    try:
        _, warnings = typst.compile_with_warnings(str(main), **kwargs)
    except (typst.TypstError, RuntimeError, OSError) as exc:
        raise PandocError(f"typst failed for {paths.rel(main)}:\n{exc}") from exc
    missing: set[str] = set()
    for w in warnings or []:
        msg = getattr(w, "message", str(w))
        m = _TYPST_FONT_WARNING.search(msg)
        if m:
            missing.add(m.group(1))
        elif "is not a valid typst font" not in msg:
            print(f"  typst: {msg}", file=sys.stderr)
    if missing and os.environ.get("TBOOK_VERBOSE"):
        print(f"  typst: fonts not installed, using fallbacks: {', '.join(sorted(missing))}", file=sys.stderr)
    return out_path


def build_pdf(site, book, edition, model, lock, variant: str, out_path: Path, *,
              stage_dir: Path | None = None) -> Path:
    """Build ``out_path`` (PDF, variant ``screen`` = dark neon or ``print`` = white paper).

    ``stage_dir`` overrides build/stage/<slug>/<lang>/pandoc/ (tests).
    """
    if variant not in config.PDF_VARIANTS:
        raise PandocError(f"unknown PDF variant {variant!r}; expected one of {config.PDF_VARIANTS}")
    staged = typst_source(site, book, edition, model, lock, stage_dir=stage_dir)
    return compile_typst(staged.dir / "main.typ", Path(out_path), root=staged.dir,
                         sys_inputs={"tr-variant": variant}, timestamp=source_date_epoch(book) or None)


# --------------------------------------------------------------------------- EPUB


def epub_palette_css() -> str:
    """CSS custom properties for the EPUB: paper tokens by default, screen tokens in dark themes."""
    tokens = json.loads(paths.TOKENS.read_text(encoding="utf-8"))

    def block(selector: str, palette: dict, indent: str = "") -> str:
        body = "".join(f"{indent}  --tr-{k}: {v};\n" for k, v in palette.items())
        sem = "".join(f"{indent}  --tr-sem-{k}: var(--tr-{v});\n" for k, v in tokens["semantic"].items())
        return f"{indent}{selector} {{\n{body}{sem}{indent}}}\n"

    dark_sel = (':root[__ibooks_internal_theme*="Night"], :root[__ibooks_internal_theme*="Gray"], '
                ':root[__ibooks_internal_theme*="night"], :root[__ibooks_internal_theme*="gray"]')
    fonts = "".join(f"  --tr-font-{k}: {', '.join(_css_font(f) for f in v)};\n"
                    for k, v in tokens["font"].items() if isinstance(v, list))
    return ("/* generated by tools/tbook/pandoc.py from theme/tokens.json — do not edit */\n"
            + block(":root", tokens["paper"])
            + f":root {{\n{fonts}}}\n"
            + "@media (prefers-color-scheme: dark) {\n" + block(":root", tokens["screen"], "  ") + "}\n"
            + block(dark_sel, tokens["screen"]))


def _css_font(name: str) -> str:
    generic = {"serif", "sans-serif", "monospace", "system-ui", "ui-monospace", "cursive", "fantasy"}
    return name if name in generic else f'"{name}"'


_FONT_FACE_NAMES = {
    "chakrapetch": "Chakra Petch",
    "jetbrainsmono": "JetBrains Mono",
    "notosanssc": "Noto Sans SC",
    "notoserifsc": "Noto Serif SC",
}
_WEIGHTS = {"thin": 100, "extralight": 200, "light": 300, "regular": 400, "medium": 500,
            "semibold": 600, "demibold": 600, "bold": 700, "extrabold": 800, "black": 900}


def _font_face(path: Path) -> tuple[str, int, str] | None:
    """(family, weight, style) from a file name such as ChakraPetch-SemiBold.ttf."""
    stem = path.stem.lower().replace("_", "-")
    key = stem.split("-")[0].replace(" ", "")
    family = _FONT_FACE_NAMES.get(key)
    if not family:
        return None
    rest = stem[len(stem.split("-")[0]):].strip("-")
    style = "italic" if "italic" in rest else "normal"
    rest = rest.replace("italic", "")
    weight = 400
    if rest.isdigit():
        weight = int(rest)
    else:
        for name, w in _WEIGHTS.items():
            if rest == name:
                weight = w
    return family, weight, style


def _epub_fonts(book: config.Book) -> list[tuple[Path, str, int, str]]:
    mode = book.epub.get("embed_fonts", False)
    if not mode:
        return []
    cjk = mode == "all"
    out = []
    for p in epub_font_files():
        face = _font_face(p)
        if not face:
            continue
        if face[0].endswith(" SC") and not cjk:
            continue  # CJK faces are large; Apple Books ships PingFang / Songti
        out.append((p, *face))
    return out


def stage_epub(site, book, edition, model, lock, staged: Stage) -> dict:
    """Write epub/ inputs (stylesheet, metadata, colophon, cover) next to book.md."""
    from . import cover

    lang = edition.lang
    edir = staged.dir / "epub"
    edir.mkdir(parents=True, exist_ok=True)
    meta = staged.meta
    fonts = _epub_fonts(book)
    font_css = "".join(
        f'@font-face {{ font-family: "{fam}"; font-weight: {w}; font-style: {st}; src: url("../fonts/{p.name}"); }}\n'
        for p, fam, w, st in fonts)
    css = epub_palette_css() + font_css + (EPUB_THEME / "book.css").read_text(encoding="utf-8")
    (edir / "book.css").write_text(css, encoding="utf-8")

    cover_png = cover.render_cover(site, book, edition, staged.dir / "cover.png", fmt="png", variant="screen",
                                   model=model, lock=lock, meta=meta)

    isbn = meta["isbn"]
    identifier = [{"scheme": "ISBN-13", "text": re.sub(r"[^0-9Xx]", "", isbn)}] if isbn else [{"text": meta["identifier"]}]
    title = [{"type": "main", "text": meta["title"]}]
    if meta["subtitle"]:
        title.append({"type": "subtitle", "text": meta["subtitle"]})
    md_meta = {
        "title": title,
        "creator": [{"role": "author", "text": a} for a in meta["authors"]],
        "identifier": identifier,
        "lang": edition.bcp47,
        "date": meta["date"]["iso"],
        "rights": meta["license"],
        "publisher": meta["publisher"],
        "description": meta["description"],
        "subject": meta["keywords"],
        "toc-title": config.s(lang, "ui.contents"),
        "ibooks": {"version": book.version, "specified-fonts": "true" if fonts else "false"},
    }
    # epubcheck rejects empty dc:* elements: leave out what the book does not define.
    md_meta = {k: v for k, v in md_meta.items() if v not in ("", [], None)}
    (edir / "metadata.json").write_text(json.dumps(md_meta, ensure_ascii=False, indent=2), encoding="utf-8")
    (edir / "colophon.md").write_text(epub_colophon(meta), encoding="utf-8")
    return {"cover": cover_png, "fonts": [f[0] for f in fonts]}


def _md_escape(text: str) -> str:
    return re.sub(r"([\\`*_{}\[\]<>#|$])", r"\\\1", text)


def epub_colophon(meta: dict) -> str:
    """Front-matter copyright page (the PDF draws the same data in book.typ)."""
    s = meta["strings"]
    rows = [(s["version"], meta["version"]), (s["date"], meta["date"]["iso"])]
    if meta["authors"]:
        rows.append((s["authors"], config.s(meta["lang"], "punct.list_sep").join(meta["authors"])))
    if meta["license"]:
        rows.append((s["license"], meta["license"]))
    if meta["isbn"]:
        rows.append((s["isbn"], meta["isbn"]))
    if meta["publisher"]:
        rows.append((s["publisher"], meta["publisher"]))
    tru = meta["trureturing"]
    out = [f"# {_md_escape(s['colophon'])} {{#tr-colophon .unnumbered .unlisted .tr-colophon epub:type=\"copyright-page\"}}", ""]
    out += [f"**{_md_escape(meta['title'])}**" + (f"  \n{_md_escape(meta['subtitle'])}" if meta["subtitle"] else ""), ""]
    out.append("::: {.tr-colophon-table}")
    for k, v in rows:
        out.append(f"[{_md_escape(k)}]{{.tr-k}} [{_md_escape(v)}]{{.tr-v}}  ")
    if tru["commit"]:
        out.append(f"[{_md_escape(s['pinned_at'])}]{{.tr-k}} [`{tru['short']}`]({tru['url']}) · `{tru['repo']}`  ")
    if meta["online_url"]:
        out.append(f"[{_md_escape(s['online'])}]{{.tr-k}} <{meta['online_url']}>  ")
    if meta["repo_url"]:
        out.append(f"[{_md_escape(s['source'])}]{{.tr-k}} <{meta['repo_url']}>  ")
    out += [":::", ""]
    out += ["::: {.tr-verified}", _md_escape(s["verified_statement"]), ":::", ""]
    if s["open_statement"]:
        out += [_md_escape(s["open_statement"]), ""]
    return "\n".join(out)


DISPLAY_OPTIONS = "META-INF/com.apple.ibooks.display-options.xml"


def display_options_xml(specified_fonts: bool) -> str:
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<display_options>\n  <platform name="*">\n'
            f'    <option name="specified-fonts">{"true" if specified_fonts else "false"}</option>\n'
            '  </platform>\n</display_options>\n')


_XHTML_TITLE_RE = re.compile(rb"<title>[^<]*\.xhtml</title>")
_H1_RE = re.compile(rb"<h1[^>]*>(.*?)</h1>", re.S)


def _page_title(xhtml: bytes, fallback: str) -> bytes:
    """Pandoc titles chapter files after their file name; use the chapter heading instead."""
    m = _H1_RE.search(xhtml)
    text = re.sub(rb"<annotation[^>]*>.*?</annotation>", b"", m.group(1), flags=re.S) if m else b""
    text = re.sub(rb"<[^>]+>", b"", text).strip()
    if not text:
        text = fallback.replace("&", "&amp;").replace("<", "&lt;").encode("utf-8")
    return _XHTML_TITLE_RE.sub(lambda _: b"<title>" + re.sub(rb"\s+", b" ", text) + b"</title>", xhtml, count=1)


_ROOTFILE_RE = re.compile(rb'<rootfile\b[^>]*\bfull-path="([^"]+)"')
_ITEM_RE = re.compile(rb"<item\b[^>]*>")
_HREF_RE = re.compile(rb'\bhref="([^"]+)"')
_PROPERTIES_RE = re.compile(rb'\bproperties="([^"]*)"')


def declare_mathml(opf: bytes, opf_name: str, data: dict[str, bytes]) -> bytes:
    """Add the ``mathml`` property to every manifest item whose XHTML contains MathML.

    Pandoc declares it for chapters but not for nav.xhtml, which copies the MathML of
    headings into the table of contents (epubcheck OPF-014).
    """
    base = posixpath.dirname(opf_name)

    def fix(m: re.Match) -> bytes:
        item = m.group(0)
        href = _HREF_RE.search(item)
        if not href:
            return item
        name = posixpath.normpath(posixpath.join(base, unquote(href.group(1).decode("utf-8"))))
        if b"<math" not in data.get(name, b""):
            return item
        props = _PROPERTIES_RE.search(item)
        if props is None:
            end = len(item) - (2 if item.endswith(b"/>") else 1)
            return item[:end].rstrip() + b' properties="mathml"' + item[end:]
        if b"mathml" in props.group(1).split():
            return item
        value = (props.group(1) + b" mathml").strip()
        return item[:props.start(1)] + value + item[props.end(1):]

    return _ITEM_RE.sub(fix, opf)


def finalize_epub(src: Path, dst: Path, *, specified_fonts: bool, epoch: int, title: str = "") -> Path:
    """Rewrite the zip: ``mimetype`` first and stored, Apple display options, chapter titles,
    ``mathml`` declared wherever MathML occurs, fixed timestamps (from ``epoch``) for a
    byte-reproducible file."""
    when = datetime.fromtimestamp(max(epoch, 315532800), tz=timezone.utc).timetuple()[:6]
    with zipfile.ZipFile(src) as zin:
        names = [n for n in zin.namelist() if n != "mimetype" and n != DISPLAY_OPTIONS]
        data = {n: zin.read(n) for n in names}
    for n in names:
        if n.endswith(".xhtml"):
            data[n] = _page_title(data[n], title)
    rootfile = _ROOTFILE_RE.search(data.get("META-INF/container.xml", b""))
    opf_name = rootfile.group(1).decode("utf-8") if rootfile else next((n for n in names if n.endswith(".opf")), "")
    if opf_name in data:
        data[opf_name] = declare_mathml(data[opf_name], opf_name, data)
    order = []
    for n in names:
        order.append(n)
        if n == "META-INF/container.xml":
            order.append(DISPLAY_OPTIONS)
    if DISPLAY_OPTIONS not in order:
        order.insert(0, DISPLAY_OPTIONS)
    data[DISPLAY_OPTIONS] = display_options_xml(specified_fonts).encode("utf-8")
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(dst.suffix + ".tmp")
    with zipfile.ZipFile(tmp, "w") as zout:
        info = zipfile.ZipInfo("mimetype", date_time=when)
        info.compress_type = zipfile.ZIP_STORED
        info.external_attr = 0o644 << 16
        zout.writestr(info, b"application/epub+zip")
        for n in order:
            info = zipfile.ZipInfo(n, date_time=when)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zout.writestr(info, data[n], compresslevel=9)
    tmp.replace(dst)
    return dst


@dataclass
class EpubReport:
    valid: bool
    errors: list[str]
    warnings: list[str]
    skipped: str = ""


def check_epub(path: Path) -> EpubReport:
    """Run epubcheck (Python package, needs Java). ``skipped`` explains when it could not run."""
    if not shutil.which("java"):
        return EpubReport(True, [], [], skipped="java not found")
    try:
        from epubcheck import EpubCheck  # type: ignore
    except ImportError:
        return EpubReport(True, [], [], skipped="epubcheck package not installed")
    result = EpubCheck(str(path))
    errors, warnings = [], []
    for msg in result.messages:
        level = str(getattr(msg, "level", "")).upper()
        text = f"{getattr(msg, 'id', '')} {getattr(msg, 'location', '')}: {getattr(msg, 'message', msg)}".strip()
        if level in ("ERROR", "FATAL"):
            errors.append(text)
        elif level in ("WARNING",):
            warnings.append(text)
    return EpubReport(bool(result.valid) and not errors, errors, warnings)


def build_epub(site, book, edition, model, lock, out_path: Path, *, stage_dir: Path | None = None) -> Path:
    """Build an EPUB 3 for Apple Books at ``out_path`` and validate it with epubcheck.

    ``stage_dir`` overrides build/stage/<slug>/<lang>/pandoc/ (tests).
    """
    out_path = Path(out_path)
    staged = stage(site, book, edition, model, lock, out_dir=stage_dir)
    extra = stage_epub(site, book, edition, model, lock, staged)
    epoch = source_date_epoch(book)
    raw = staged.dir / "epub" / "pandoc.epub"
    args = [
        "epub/colophon.md", "book.md", "--from", READER, "--to", "epub3", "--output", str(raw.relative_to(staged.dir)),
        "--mathml", "--toc", "--toc-depth", "2", "--split-level", "1",
        "--epub-cover-image", str(Path(extra["cover"]).relative_to(staged.dir)),
        "--css", "epub/book.css", "--metadata-file", "epub/metadata.json", "--syntax-highlighting", "none",
        "--resource-path", ".", "--wrap", "none",
        *_filter_meta(edition.lang), *_filters(),
    ]
    for font in extra["fonts"]:
        args += ["--epub-embed-font", str(font)]
    run_pandoc(args, cwd=staged.dir, env={"SOURCE_DATE_EPOCH": str(epoch)})
    finalize_epub(raw, out_path, specified_fonts=bool(extra["fonts"]), epoch=epoch, title=staged.meta["title"])
    mode = os.environ.get("TBOOK_EPUBCHECK", "1").lower()
    if mode not in ("0", "false", "no", "off"):
        report = check_epub(out_path)
        if report.skipped:
            print(f"  epubcheck skipped: {report.skipped}", file=sys.stderr)
        else:
            for w in report.warnings:
                print(f"  epubcheck warning: {w}", file=sys.stderr)
            for e in report.errors:
                print(f"  epubcheck error: {e}", file=sys.stderr)
            if report.errors and mode != "warn":
                raise PandocError(f"epubcheck: {len(report.errors)} error(s) in {paths.rel(out_path)}")
    return out_path
