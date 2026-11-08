"""Server-side KaTeX for the staged mdBook sources (``$…$`` and ``$$…$$``).

The HTML edition ships no client-side math: every formula is rendered at build time by
the pinned KaTeX package, in ONE Node process per edition
(``tools/node/katex-render.mjs --macros <json>``, JSON lines ``{id, tex, display}`` →
``{id, html}`` / ``{id, error}``), and spliced into the Markdown before mdBook runs.

Which ``$`` are math follows Pandoc's ``tex_math_dollars`` (the PDF and EPUB pipelines
read the same sources with Pandoc, so all targets agree on what is a formula):

* ``$…$`` is inline math: the opening ``$`` is not followed by whitespace, the closing
  ``$`` is not preceded by whitespace and not followed by a digit (so ``$5 and $6`` is
  text); a closer that fails these tests is skipped and the search continues;
* ``$$…$$`` is display math and may span lines;
* neither crosses a blank line; ``\\$`` (a ``$`` after an odd number of backslashes) is a
  literal dollar; ``\\|`` inside a formula stays ``\\|`` (the norm bar), in table rows too:
  Pandoc keeps it, and the formula is rendered before mdBook splits the row into cells;
* nothing inside fenced code blocks, inline code spans, HTML comments, ``<code>``/``<pre>``
  /``<script>``/``<style>`` elements, HTML tags (attribute values), autolinks or link
  destinations is math. A candidate span that would contain such a region is not math.

Inside raw HTML blocks (for example the ``<header>`` of a theorem environment written by
:func:`tbook.render.mdbook_env`, whose title is HTML-escaped) the TeX is entity-decoded
before rendering.

Replacement: display math that occupies whole lines becomes an HTML block
``<div class="tr-math">…</div>`` surrounded by blank lines (raw HTML, so Markdown never
touches it); any other formula is replaced in place by KaTeX's one-line HTML, with the
ASCII punctuation of its text nodes written as character references so that Markdown
(emphasis, tables, smart punctuation) cannot alter it. Punctuation right after (or an
opening bracket right before) an inline formula is bound to it with a nowrap span, so a
line never starts with "，" or ")" (:func:`glue`). A formula KaTeX cannot render is
kept as its TeX source in ``<code class="katex-fallback">`` and reported as a warning.

Macros: :data:`TEX_MACROS` (commands from LaTeX packages that KaTeX and Pandoc's texmath do
not define) is the one macro table of the book. KaTeX receives it as its ``macros`` option;
the Pandoc pipeline (:mod:`tbook.pandoc`) writes it as ``\\newcommand`` definitions
(:func:`newcommands`) that Pandoc's ``latex_macros`` expands, so a formula renders the same
in HTML, PDF and EPUB.

Adapted from trureturing-mdbook (scripts/math_scan.py and scripts/render_katex.py,
Apache-2.0, https://github.com/the-omega-institute/trureturing-mdbook).
"""

from __future__ import annotations

import bisect
import html
import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from . import mdscan, paths

RENDERER = paths.TOOLS / "node" / "katex-render.mjs"
FALLBACK_CLASS = "katex-fallback"
BLOCK_CLASS = "tr-math"

COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
RAW_ELEMENT_RE = re.compile(r"<(code|pre|script|style|textarea|kbd|samp|math|svg)\b[^>]*>.*?</\1\s*>", re.S | re.I)
TAG_RE = re.compile(
    r"""</?[A-Za-z][A-Za-z0-9-]*"""
    r"""(?:\s+[^\s"'>/=]+(?:\s*=\s*(?:"[^"]*"|'[^']*'|[^\s"'=<>`]+))?)*\s*/?>"""
)
AUTOLINK_RE = re.compile(r"<[A-Za-z][A-Za-z0-9+.-]{1,31}:[^\s<>]*>")
LINK_DEST_RE = re.compile(r"(?<=\])\((?:[^()\s]|\([^()\s]*\))*(?:\s+(?:\"[^\"]*\"|'[^']*'))?\)")
# Lines that open a CommonMark HTML block: type 6 (block-level tag names) or type 7 (a
# single complete tag alone on its line). Inside such blocks Markdown is not parsed.
_BLOCK_TAGS = ("address|article|aside|base|basefont|blockquote|body|caption|center|col|colgroup|dd|details|"
               "dialog|dir|div|dl|dt|fieldset|figcaption|figure|footer|form|frame|frameset|h[1-6]|head|"
               "header|hr|html|iframe|legend|li|link|main|menu|menuitem|nav|noframes|ol|optgroup|option|p|"
               "param|search|section|summary|table|tbody|td|tfoot|th|thead|title|tr|track|ul")
HTML_LINE_RE = re.compile(
    rf"^[ ]{{0,3}}(?:</?(?:{_BLOCK_TAGS})(?:[\s/>]|$)|<!--"
    r"|</?[A-Za-z][A-Za-z0-9-]*(?:\s+[^\s\"'>/=]+(?:\s*=\s*(?:\"[^\"]*\"|'[^']*'|[^\s\"'=<>`]+))?)*\s*/?>\s*$)",
    re.I,
)
BLANK_LINE_RE = re.compile(r"\n[ \t>]*\n")
# What may stand before ``$$`` / after the closing ``$$`` for the formula to be a block:
# indentation (fewer than 4 spaces, or it would become an indented code block) and
# block-quote markers.
BLOCK_PREFIX_RE = re.compile(r"^(?:[ ]{0,3}>[ \t]?)*[ ]{0,3}$")
# Markdown-significant ASCII punctuation, and character references to keep as they are.
_PUNCT_RE = re.compile(r"&(?:#[0-9]+|#[xX][0-9a-fA-F]+|[A-Za-z][A-Za-z0-9]*);|[\\`*_\[\]~|$<>!#^\"'.{}&-]")
_TEXT_NODE_RE = re.compile(r">([^<]+)<")
# Punctuation that must stay on the line of the adjacent inline formula. Chromium breaks
# freely around KaTeX's inline-block boxes (even across U+2060 WORD JOINER), so the
# punctuation and the formula's first/last box are wrapped in a white-space: nowrap span
# (:func:`glue`). ASCII members are limited to characters Markdown never treats as syntax
# next to a formula (no brackets, quotes, '!' or '*').
CLOSING_PUNCT = frozenset(",.;:?)%\u2019\u201d\u2026\u3001\u3002\uff0c\uff0e\uff1b\uff1a\uff1f\uff01\uff09"
                          "\uff3d\uff5d\u300d\u300f\u3011\u3009\u300b\u3015\u3017")
OPENING_PUNCT = frozenset("(\u2018\u201c\uff08\uff3b\uff5b\u300c\u300e\u3010\u3008\u300a\u3014\u3016")
NOBR_CLASS = "tr-nobr"
_SPAN_TAG_RE = re.compile(r"<(/?)span\b[^>]*>")

# Commands from LaTeX packages that upstream quotes use (amsmath, dsfont, physics,
# mathtools-style delimiters, esvect, nicefrac) and that neither KaTeX nor Pandoc's texmath
# define. ``#n`` is the n-th argument (KaTeX syntax; :func:`newcommands` counts them).
TEX_MACROS: dict[str, str] = {
    "\\Tr": "\\operatorname{Tr}",
    "\\tr": "\\operatorname{tr}",
    "\\trace": "\\operatorname{Tr}",
    "\\diag": "\\operatorname{diag}",
    "\\Tilde": "\\tilde",
    "\\wt": "\\widetilde",
    "\\mathds": "\\mathbb",
    "\\mathpzc": "\\mathcal",
    "\\ketbra": "\\lvert #1\\rangle\\langle #2\\rvert",
    "\\dyad": "\\lvert #1\\rangle\\langle #1\\rvert",
    "\\floor": "\\left\\lfloor #1\\right\\rfloor",
    "\\ceil": "\\left\\lceil #1\\right\\rceil",
    "\\norm": "\\left\\lVert #1\\right\\rVert",
    "\\vv": "\\vec{#1}",
    "\\nicefrac": "{}^{#1}\\!/\\!{}_{#2}",
    "\\mbox": "\\text{#1}",
    "\\emph": "\\textit{#1}",
    "\\normalfont": "",
}
_MACRO_ARG_RE = re.compile(r"#([1-9])")


def newcommands(macros: dict[str, str] | None = None) -> str:
    """:data:`TEX_MACROS` as LaTeX ``\\newcommand`` lines, one per macro (for Pandoc)."""
    lines = []
    for name, body in (TEX_MACROS if macros is None else macros).items():
        args = max((int(n) for n in _MACRO_ARG_RE.findall(body)), default=0)
        lines.append(f"\\newcommand{{{name}}}" + (f"[{args}]" if args else "") + f"{{{body}}}")
    return "\n".join(lines)


class MathError(RuntimeError):
    """The renderer could not run or answered inconsistently (not a bad formula)."""


@dataclass(frozen=True)
class MathSpan:
    start: int  # offset of the opening delimiter
    end: int  # offset just past the closing delimiter
    tex: str  # the body as KaTeX should see it
    display: bool
    block: bool  # display math on lines of its own → emitted as an HTML block
    line: int  # 1-based line of the opening delimiter
    prefix: str = ""  # block quote / indentation prefix of a block formula


@dataclass
class MathReport:
    files: int = 0
    formulas: int = 0
    unique: int = 0
    lenient: int = 0
    failures: int = 0
    warnings: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------- scanning


def _escaped(text: str, index: int) -> bool:
    """True if ``text[index]`` follows an odd number of backslashes."""
    count = 0
    k = index - 1
    while k >= 0 and text[k] == "\\":
        count += 1
        k -= 1
    return count % 2 == 1


def _mask(text: str) -> tuple[bytearray, list[bool]]:
    """Per-character mask (1 = cannot be part of a formula) and per-line HTML-block flags."""
    mask = bytearray(len(text))
    lines = text.split("\n")
    html_lines: list[bool] = []
    offset = 0
    in_html = False
    # Fenced code (also in block quotes and list items) exactly as every other scanner sees it:
    # a "> ```" line shown inside a top-level code example does not close the example.
    for line, hidden in zip(lines, mdscan.fenced_code_lines(lines)):
        end = offset + len(line)
        if hidden:
            mask[offset:end] = b"\x01" * (end - offset)
            in_html = False
        else:
            for a, b in mdscan.code_spans(line):
                mask[offset + a:offset + b] = b"\x01" * (b - a)
            if not line.strip():
                in_html = False
            elif not in_html and HTML_LINE_RE.match(line):
                in_html = True
        html_lines.append(in_html and not hidden)
        offset = end + 1
    for pattern in (COMMENT_RE, RAW_ELEMENT_RE, TAG_RE, AUTOLINK_RE, LINK_DEST_RE):
        for m in pattern.finditer(text):
            if mask[m.start()]:
                continue
            mask[m.start():m.end()] = b"\x01" * (m.end() - m.start())
    return mask, html_lines


def _find_close(text: str, mask: bytearray, start: int, display: bool) -> int | None:
    """Offset of the closing delimiter of a formula whose body starts at ``start``."""
    n = len(text)
    blank = BLANK_LINE_RE.search(text, start)
    limit = blank.start() if blank else n
    k = start
    while k < limit:
        if mask[k]:
            return None
        if text[k] == "$" and not _escaped(text, k):
            if display:
                if k + 1 < n and text[k + 1] == "$" and not mask[k + 1]:
                    return k
            else:
                if not text[k - 1].isspace() and not (k + 1 < n and text[k + 1].isdigit()):
                    return k
        k += 1
    return None


def find_math(text: str) -> tuple[list[MathSpan], list[tuple[int, str]]]:
    """Formulas of ``text`` in order, and (line, message) notes about unpaired ``$$``."""
    mask, html_lines = _mask(text)
    starts = [0] + [m.end() for m in re.finditer("\n", text)]

    def line_of(pos: int) -> int:
        return bisect.bisect_right(starts, pos)

    spans: list[MathSpan] = []
    notes: list[tuple[int, str]] = []
    n = len(text)
    i = 0
    while i < n:
        if text[i] != "$" or mask[i] or _escaped(text, i):
            i += 1
            continue
        display = i + 1 < n and text[i + 1] == "$" and not mask[i + 1]
        width = 2 if display else 1
        if not display and (i + 1 >= n or text[i + 1].isspace()):
            i += 1
            continue
        close = _find_close(text, mask, i + width, display)
        if close is None:
            if display:
                notes.append((line_of(i), "unpaired $$ left as text"))
            i += width
            continue
        body = text[i + width:close]
        end = close + width
        if not body.strip():
            i = end
            continue
        line = line_of(i)
        if html_lines[line - 1]:
            body = html.unescape(body)
        # "\|" in a table row stays the norm bar: the formula is replaced by KaTeX HTML (whose
        # "|" are character references) before mdBook ever splits the row, and Pandoc, which
        # reads the same source for PDF/EPUB, keeps "\|" in the math as well.
        block = False
        prefix = ""
        if display:
            line_start = starts[line - 1]
            nl = text.find("\n", end)
            line_end = n if nl < 0 else nl
            prefix = text[line_start:i]
            block = bool(BLOCK_PREFIX_RE.match(prefix)) and not text[end:line_end].strip()
            if ">" in prefix:
                # Continuation lines of a formula inside a block quote carry the markers.
                body = re.sub(r"\n[ \t]*(?:>[ \t]?)+", "\n", body)
        spans.append(MathSpan(i, end, body.strip() if display else body, display, block, line, prefix))
        i = end
    return spans, notes


# --------------------------------------------------------------------------- output


def inert(markup: str) -> str:
    """KaTeX HTML as one line whose text nodes Markdown leaves alone."""

    def encode(m: re.Match) -> str:
        tok = m.group(0)
        return tok if len(tok) > 1 else f"&#{ord(tok)};"

    markup = markup.replace("\r", " ").replace("\n", " ")
    markup = _TEXT_NODE_RE.sub(lambda m: ">" + _PUNCT_RE.sub(encode, m.group(1)) + "<", markup)
    # A raw "|" left in an attribute (the TeX in aria-label) would split a table cell.
    return markup.replace("|", "&#124;")


def fallback_html(tex: str, display: bool) -> str:
    """The TeX source as one line of inert HTML (every ASCII punctuation as a reference)."""
    text = "".join(
        " " if ch in "\r\n\t"
        else f"&#{ord(ch)};" if ch.isascii() and not ch.isalnum() and ch != " "
        else ch
        for ch in tex
    )
    attr = ' data-display="true"' if display else ""
    return f'<code class="{FALLBACK_CLASS}"{attr}>{text}</code>'


def _children(markup: str, start: int) -> list[tuple[int, int]]:
    """(start, end) of the span elements directly inside the element whose content starts at ``start``."""
    kids: list[tuple[int, int]] = []
    depth = 0
    open_at = -1
    for m in _SPAN_TAG_RE.finditer(markup, start):
        if m.group(1):  # </span>
            if depth == 0:
                break
            depth -= 1
            if depth == 0:
                kids.append((open_at, m.end()))
        else:
            if depth == 0:
                open_at = m.start()
            depth += 1
    return kids


def _punct(ch: str) -> str:
    return f"&#{ord(ch)};" if ch.isascii() else ch


def glue(markup: str, before: str, after: str) -> str:
    """Keep ``before``/``after`` punctuation on the line of the formula's first/last box.

    KaTeX splits an inline formula into ``.katex-base`` boxes with break opportunities
    between them; the outer boxes are moved into separate (aria-hidden) ``.katex`` wrappers
    that share a nowrap span with the punctuation, so the formula still breaks inside.
    """
    nobr = f'<span class="{NOBR_CLASS}">'
    m = re.search(r'<span class="katex-html"[^>]*>', markup)
    kids = _children(markup, m.end()) if m else []
    if len(kids) <= bool(before) + bool(after):
        return f"{nobr}{_punct(before) if before else ''}{markup}{_punct(after) if after else ''}</span>"

    def piece(a: int, b: int) -> str:
        return ('<span class="katex" aria-hidden="true"><span class="katex-html" aria-hidden="true">'
                f"{markup[a:b]}</span></span>")

    head = tail = ""
    first, last = kids[0][0], kids[-1][1]
    if before:
        head = f"{nobr}{_punct(before)}{piece(*kids[0])}</span>"
        first = kids[1][0]
    if after:
        tail = f"{nobr}{piece(*kids[-1])}{_punct(after)}</span>"
        last = kids[-2][1]
    return head + markup[:m.end()] + markup[first:last] + markup[kids[-1][1]:] + tail


def splice(text: str, spans: list[MathSpan], rendered: list[str]) -> str:
    """Replace each span by its rendered HTML (``rendered`` is in span order)."""
    if len(spans) != len(rendered):
        raise ValueError("one rendering per span is required")
    out: list[str] = []
    cursor = 0
    for span, markup in zip(spans, rendered):
        if span.block:
            line_start = text.rfind("\n", 0, span.start) + 1
            nl = text.find("\n", span.end)
            line_end = len(text) if nl < 0 else nl
            out.append(text[cursor:line_start])
            blank = span.prefix.rstrip() if ">" in span.prefix else ""
            out.append(f"{blank}\n{span.prefix}<div class=\"{BLOCK_CLASS}\">{markup}</div>\n{blank}")
            cursor = line_end
        else:
            before = text[span.start - 1] if span.start > cursor and text[span.start - 1] in OPENING_PUNCT else ""
            after = text[span.end] if span.end < len(text) and text[span.end] in CLOSING_PUNCT else ""
            out.append(text[cursor:span.start - len(before)])
            out.append(glue(markup, before, after) if before or after else markup)
            cursor = span.end + len(after)
    out.append(text[cursor:])
    return "".join(out)


# --------------------------------------------------------------------------- renderer


def node_binary() -> str:
    node = os.environ.get("NODE") or shutil.which("node")
    if not node:
        raise MathError("node is not installed (Node >= 22.12 is required to render math with KaTeX)")
    return node


def render_formulas(items: list[tuple[str, bool]]) -> list[dict]:
    """Render ``(tex, display)`` pairs in one Node process; one answer dict per item."""
    if not items:
        return []
    if not RENDERER.exists():
        raise MathError(f"KaTeX renderer missing: {paths.rel(RENDERER)}")
    payload = "".join(json.dumps({"id": k, "tex": tex, "display": display}, ensure_ascii=False) + "\n"
                      for k, (tex, display) in enumerate(items))
    macros = json.dumps(TEX_MACROS, ensure_ascii=False)
    try:
        proc = subprocess.run([node_binary(), str(RENDERER), "--macros", macros], input=payload,
                              capture_output=True, text=True, encoding="utf-8", cwd=paths.ROOT)
    except OSError as exc:
        raise MathError(f"cannot start node: {exc}") from exc
    if proc.returncode != 0:
        raise MathError(proc.stderr.strip() or f"katex-render exited with status {proc.returncode}")
    answers: list[dict] = []
    # Split on "\n" only: JSON leaves U+2028 and other line separators unescaped.
    for raw in proc.stdout.split("\n"):
        if not raw.strip():
            continue
        try:
            answers.append(json.loads(raw))
        except ValueError as exc:
            raise MathError(f"katex-render returned malformed output: {exc}") from None
    if len(answers) != len(items) or any(a.get("id") != k for k, a in enumerate(answers)):
        raise MathError("katex-render answered a different set of formulas than it was given")
    for a in answers:
        if not (isinstance(a.get("html"), str) or isinstance(a.get("error"), str)):
            raise MathError("katex-render answered without html or error")
    return answers


def render_files(files: list[Path], *, where=None) -> MathReport:
    """Render the math of ``files`` in place (one Node process for all of them).

    ``where(path)`` names a file in warnings (default: repository-relative path).
    """
    where = where or paths.rel
    report = MathReport(files=len(files))
    texts: dict[Path, str] = {}
    found: dict[Path, list[MathSpan]] = {}
    unique: dict[tuple[str, bool], int] = {}
    for path in files:
        text = path.read_text(encoding="utf-8")
        spans, notes = find_math(text)
        texts[path], found[path] = text, spans
        for line, message in notes:
            report.warnings.append(f"{where(path)}:{line}: {message}")
        for span in spans:
            unique.setdefault((span.tex, span.display), len(unique))
        report.formulas += len(spans)
    report.unique = len(unique)
    answers = render_formulas(list(unique))
    for path in files:
        spans = found[path]
        if not spans:
            continue
        rendered: list[str] = []
        for span in spans:
            answer = answers[unique[(span.tex, span.display)]]
            if isinstance(answer.get("html"), str):
                rendered.append(inert(answer["html"]))
                if answer.get("lenient"):
                    report.lenient += 1
            else:
                report.failures += 1
                report.warnings.append(f"{where(path)}:{span.line}: KaTeX cannot render "
                                       f"{_clip(span.tex)!r}: {answer['error']}")
                rendered.append(fallback_html(span.tex, span.display))
        path.write_text(splice(texts[path], spans, rendered), encoding="utf-8")
    if report.lenient:
        report.warnings.append(f"{report.lenient} formula(s) use a macro KaTeX does not know; "
                               "its name is shown in red")
    return report


def _clip(tex: str, limit: int = 80) -> str:
    tex = " ".join(tex.split())
    return tex if len(tex) <= limit else tex[:limit - 1] + "…"
