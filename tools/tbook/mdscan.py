"""Small, dependency-free Markdown scanner shared by every renderer and by ``check``.

It understands just enough of Pandoc Markdown for the book conventions:

* fenced code blocks (backticks or tildes), also inside block quotes and list items —
  always passed through verbatim;
* HTML comments: a ``<!--`` that opens a line and is not closed on it starts a comment block
  that runs to the line holding ``-->`` (passed through verbatim, like code); a comment closed
  on its line is skipped like an inline code span. No target shows comments, so links and
  references inside them are neither rewritten nor checked;
* indented code blocks outside list items and footnotes (:func:`indented_code_lines`),
  which the PDF/EPUB stager and the math scanner leave alone;
* fenced divs ``::: {.theorem #thm-x lean="…"}`` … ``:::`` (and ``::: theorem``),
  nested by stack, as in Pandoc;
* inline code spans, so that ``[@ref]``, ``lean:`` links and math inside code are ignored;
* cross references ``[@id]``, links and images (:data:`LINK_RE`), link reference
  definitions (:data:`REFDEF_RE`, also in block quotes and list items) and Lean links
  ``[text](lean:GID)`` in every one-line form (:func:`lean_link_gids`), and those it cannot read
  because they run across lines (:func:`stray_lean_links`);
* titles as inline Markdown: :func:`unescape_markdown` gives their plain text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Iterator

# A top-level code fence. A backtick fence's info string cannot contain a backtick
# (CommonMark), so ```` ```x``` ```` at the start of a line is inline code, not a fence.
FENCE_RE = re.compile(r"^(?P<indent> {0,3})(?P<fence>`{3,}(?=[^`]*$)|~{3,})(?P<info>.*)$")
# A code fence in any container: after block-quote markers (``> ```…``) and/or the
# indentation of a list item. :func:`fence_end` decides where its block ends.
CONTAINER_FENCE_RE = re.compile(
    r"^(?P<quote>(?:[ \t]*>[ \t]?)*)(?P<indent>[ \t]*)(?P<fence>`{3,}(?=[^`]*$)|~{3,})(?P<info>.*)$")
_QUOTE_RE = re.compile(r"^(?:[ \t]*>[ \t]?)*")
# Quoted attribute values may contain braces (TeX in a title: ``title="$\mathbb{N}$"``).
DIV_OPEN_RE = re.compile(
    r"""^(?P<colons>:{3,})\s*(?:\{(?P<attrs>(?:[^{}"']|"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')*)\}"""
    r"""|(?P<word>[A-Za-z][\w-]*))\s*:*\s*$""")
# A line that starts like a div opener with attributes; if DIV_OPEN_RE rejects it, say so.
DIV_OPEN_LIKE_RE = re.compile(r"^:{3,}\s*\{")
DIV_CLOSE_RE = re.compile(r"^:{3,}\s*$")
ATTR_TOKEN_RE = re.compile(
    r"""\s*(?:
        \#(?P<id>[^\s{}#.="']+)
      | \.(?P<cls>[^\s{}#.="']+)
      | (?P<key>[A-Za-z_][\w:.-]*)\s*=\s*(?:"(?P<dq>(?:[^"\\]|\\.)*)"|'(?P<sq>(?:[^'\\]|\\.)*)'|(?P<bare>[^\s"'{}]+))
    )""",
    re.X,
)
REF_RE = re.compile(r"\[@(?P<id>[A-Za-z][A-Za-z0-9:_.-]*)\](?!\()")
# What may stand before a block's text on its line: block-quote markers, list markers and the
# indentation that continues a list item. CommonMark and Pandoc read a link reference definition
# there as at the left margin.
CONTAINER = r"(?:[ \t]*+(?:>|(?:[-*+]|\d{1,9}[.)])(?=[ \t])))*+[ \t]*+"
# Link text: code spans (they bind tighter than brackets), backslash escapes, other characters and
# balanced brackets nested up to three deep (``[x [y] z](…)``, an image inside a link). Possessive,
# so a line full of backticks or brackets cannot make the match backtrack exponentially.
LINK_TEXT = r"(?:`[^`]*`|\\.|[^\[\]\\])*+"
for _ in range(3):
    LINK_TEXT = r"(?:`[^`]*`|\\.|[^\[\]\\]|\[" + LINK_TEXT + r"\])*+"
# A link title as CommonMark writes it: "…", '…' or (…), with backslash escapes.
LINK_TITLE = r"""(?:"(?:[^"\\]|\\.)*+"|'(?:[^'\\]|\\.)*+'|\((?:[^()\\]|\\.)*+\))"""
# An inline link or image; ``url`` is the destination as written: ``<…>`` (may contain spaces) or a
# plain one (balanced parentheses allowed); ``title`` keeps the spaces before it.
LINK_RE = re.compile(r"(?P<bang>!?)\[(?P<text>" + LINK_TEXT + r")\]\([ \t]*"
                     r"(?P<url><[^<>\n]*>|(?:[^\s()\\]|\\.|\((?:[^\s()\\]|\\.)*+\))++)"
                     r"(?P<title>[ \t]+" + LINK_TITLE + r")?[ \t]*\)")
# A CommonMark autolink to a declaration, ``<lean:GID>`` (mdBook links it; Pandoc's Markdown does not).
LEAN_AUTOLINK_RE = re.compile(r"<lean:(?P<gid>[^\s<>]*)>")
# A link reference definition ``[label]: url "title"`` on one line, as CommonMark reads it: at the
# left margin or inside block quotes and list items (``lead`` keeps their markers); after the
# destination only an optional title ("…", '…' or (…), with backslash escapes; it may continue on
# the next line). ``[注]: 见 [图](a.svg)`` or ``[1]: Knuth, TAOCP.`` is a paragraph, not a
# definition, and so is a footnote ``[^x]:``.
REFDEF_RE = re.compile(
    r"""^(?P<lead>""" + CONTAINER + r"""\[(?!\^)(?:[^\[\]\\]|\\.)+\]:[ \t]*)(?P<url><[^<>\n]*>|\S+)"""
    r"""(?P<rest>(?:[ \t]+(?:"(?:[^"\\]|\\.)*+"?|'(?:[^'\\]|\\.)*+'?|\((?:[^()\\]|\\.)*+\)?))?[ \t]*)$""")
ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9:_-]*$")


@dataclass
class Attrs:
    id: str = ""
    classes: list[str] = field(default_factory=list)
    kv: dict[str, str] = field(default_factory=dict)

    def get(self, key: str, default: str = "") -> str:
        return self.kv.get(key, default)

    def to_pandoc(self) -> str:
        parts = []
        if self.id:
            parts.append("#" + self.id)
        parts += ["." + c for c in self.classes]
        for k, v in self.kv.items():
            parts.append(f'{k}="{escape_attr(v)}"')
        return "{" + " ".join(parts) + "}"


def escape_attr(v: str) -> str:
    return v.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


_ATTR_ESCAPE_RE = re.compile(r"""\\(["'\\])""")


def unescape_attr(v: str) -> str:
    """Undo the quoting escapes of an attribute value: only ``\\"``, ``\\'`` and ``\\\\``.

    Every other backslash is kept, so TeX in a title survives: ``title="$\\varphi$ in
    $\\{-1,0,1\\}$"`` stays ``$\\varphi$ in $\\{-1,0,1\\}$``. Inverse of :func:`escape_attr`.
    """
    return _ATTR_ESCAPE_RE.sub(r"\1", v)


class AttrError(ValueError):
    pass


def parse_attrs(text: str) -> Attrs:
    attrs = Attrs()
    pos = 0
    text = text.strip()
    while pos < len(text):
        m = ATTR_TOKEN_RE.match(text, pos)
        if not m or m.end() == pos:
            raise AttrError(f"cannot parse attributes near: {text[pos:pos + 30]!r}")
        if m.group("id"):
            if attrs.id:
                raise AttrError("more than one #id")
            attrs.id = m.group("id")
        elif m.group("cls"):
            attrs.classes.append(m.group("cls"))
        else:
            val = m.group("dq") if m.group("dq") is not None else m.group("sq") if m.group("sq") is not None else m.group("bare")
            attrs.kv[m.group("key")] = unescape_attr(val)
        pos = m.end()
        while pos < len(text) and text[pos].isspace():
            pos += 1
    return attrs


# --------------------------------------------------------------------------- block tree


@dataclass
class Text:
    lines: list[str]
    start: int  # 1-based line number of the first line


@dataclass
class Code:
    lines: list[str]
    start: int


@dataclass
class Comment(Code):
    """A multi-line HTML comment block (:func:`comment_end`): passed through verbatim, like code."""


@dataclass
class Div:
    attrs: Attrs
    children: list["Node"]
    start: int  # line of the opening fence
    end: int = 0  # line of the closing fence (0 if unclosed)
    fence: str = ":::"
    raw_open: str = ""

    @property
    def classes(self) -> list[str]:
        return self.attrs.classes


Node = Text | Code | Div


@dataclass
class ScanIssue:
    line: int
    message: str


def _width(space: str) -> int:
    return len(space.expandtabs(4))


def fence_end(lines: list[str], i: int) -> int | None:
    """If ``lines[i]`` opens a fenced code block, the index of the block's last line; else None.

    The opener may sit in block quotes or list items (``> ```…``, an indented fence). The
    block ends at its closing fence: the opener's block-quote depth and fence character, at
    least as many characters, no info string, and at most 3 more columns of indentation, so a
    ``> ```…`` or deeper-indented fence shown inside a code example is content, not a closer.
    Without one it ends with its container: before the first line with fewer ``>`` markers,
    or, nested in a list item, before the first non-blank line left of the item's content;
    otherwise at the end of the text.
    """
    m = CONTAINER_FENCE_RE.match(lines[i])
    if not m:
        return None
    depth, width = m.group("quote").count(">"), _width(m.group("indent"))
    char, length = m.group("fence")[0], len(m.group("fence"))
    for j in range(i + 1, len(lines)):
        line = lines[j]
        if depth and _QUOTE_RE.match(line).group(0).count(">") < depth:
            return j - 1
        if not depth and width >= 4 and line.strip() and _width(line[:len(line) - len(line.lstrip())]) < width - 3:
            return j - 1
        c = CONTAINER_FENCE_RE.match(line)
        if (c and c.group("quote").count(">") == depth and c.group("fence")[0] == char
                and len(c.group("fence")) >= length and not c.group("info").strip()
                and _width(c.group("indent")) <= width + 3):
            return j
    return len(lines) - 1


def comment_end(lines: list[str], i: int) -> int | None:
    """If ``lines[i]`` opens a multi-line HTML comment, the index of its last line; else None.

    A comment block starts with a line whose text begins with ``<!--`` and that does not close
    it (a CommonMark HTML block); it ends at the first later line that holds ``-->``, or with the
    text when none does. Its lines are raw HTML that no target shows (tbook.pandoc's staging
    masks them by the same rule). A comment closed on its own line is left to :func:`code_spans`.
    """
    stripped = lines[i].lstrip()
    if not stripped.startswith("<!--") or "-->" in stripped[4:]:
        return None
    for j in range(i + 1, len(lines)):
        if "-->" in lines[j]:
            return j
    return len(lines) - 1


def fenced_code_lines(lines: list[str]) -> list[bool]:
    """True for each line of a fenced code block (fences included), exactly as :func:`parse_blocks` sees them
    (so a fence inside an HTML comment block is not one)."""
    mask = [False] * len(lines)
    i = 0
    while i < len(lines):
        end = fence_end(lines, i)
        if end is None:
            comment = comment_end(lines, i)
            i = i + 1 if comment is None else comment + 1
            continue
        mask[i:end + 1] = [True] * (end + 1 - i)
        i = end + 1
    return mask


_ITEM_START_RE = re.compile(r"^[ \t]*(?:[-*+]|\d{1,9}[.)])(?:[ \t]|$)|^[ \t]*\[\^[^\]\s]+\]:")
_ATX_START_RE = re.compile(r"^ {0,3}#{1,6}(?:[ \t]|$)")


def indented_code_lines(lines: list[str], hidden: list[bool] | None = None) -> list[bool]:
    """True for each line of an indented code block (4 or more columns; a tab counts as 4).

    Such a block starts after a blank line, a heading or a fenced code block, outside list
    items and footnote definitions: there, indented text after a blank line continues the
    item, and a paragraph's next line is never code (CommonMark, Pandoc). Blank lines
    between its lines belong to the block. Lines in ``hidden`` (default:
    :func:`fenced_code_lines`) are never part of one.
    """
    hidden = hidden if hidden is not None else fenced_code_lines(lines)
    mask = [False] * len(lines)
    boundary = True  # the previous line ended a block
    nested = False  # inside a list item or a footnote definition
    code = False
    last = -1  # last line of the current indented block
    for i, line in enumerate(lines):
        indent = _width(line[:len(line) - len(line.lstrip(" \t"))])
        if hidden[i]:
            if indent == 0 and not (i and hidden[i - 1]):
                nested = False  # a fence at the left margin ends a list item
            boundary, code = True, False
            continue
        if not line.strip():
            boundary = True
            continue
        if indent >= 4 and (code or (boundary and not nested)):
            if code:
                mask[last + 1:i] = [True] * (i - last - 1)  # blank lines inside the block
            mask[i] = code = True
            boundary, last = False, i
            continue
        code = False
        heading = _ATX_START_RE.match(line) is not None
        if _ITEM_START_RE.match(line):
            nested = True
        elif indent == 0 and (boundary or heading):
            nested = False
        boundary = heading
    return mask


def parse_blocks(text: str, issues: list[ScanIssue] | None = None) -> list[Node]:
    """Split Markdown into Text / Code / Div nodes (divs nested)."""
    issues = issues if issues is not None else []
    root: list[Node] = []
    stack: list[Div] = []
    lines = text.split("\n")
    i = 0

    def container() -> list[Node]:
        return stack[-1].children if stack else root

    def add_text(line: str, lineno: int) -> None:
        nodes = container()
        if nodes and isinstance(nodes[-1], Text):
            nodes[-1].lines.append(line)
        else:
            nodes.append(Text([line], lineno))

    while i < len(lines):
        line = lines[i]
        lineno = i + 1
        end = fence_end(lines, i)
        if end is not None:
            container().append(Code(lines[i:end + 1], lineno))
            i = end + 1
            continue
        end = comment_end(lines, i)
        if end is not None:
            if "-->" not in lines[end]:
                issues.append(ScanIssue(lineno, "HTML comment is never closed (add '-->'); everything after it "
                                                "is part of the comment"))
            container().append(Comment(lines[i:end + 1], lineno))
            i = end + 1
            continue
        om = DIV_OPEN_RE.match(line)
        if om:
            try:
                attrs = parse_attrs(om.group("attrs")) if om.group("attrs") is not None else Attrs(classes=[om.group("word")])
            except AttrError as exc:
                issues.append(ScanIssue(lineno, f"fenced div attributes: {exc}"))
                attrs = Attrs()
            div = Div(attrs=attrs, children=[], start=lineno, fence=om.group("colons"), raw_open=line)
            container().append(div)
            stack.append(div)
            i += 1
            continue
        if DIV_OPEN_LIKE_RE.match(line):
            issues.append(ScanIssue(lineno, "cannot parse this fenced div opening line (unbalanced quotes or "
                                            "braces?); it is treated as text"))
        elif DIV_CLOSE_RE.match(line) and stack:
            stack.pop().end = lineno
            i += 1
            continue
        add_text(line, lineno)
        i += 1
    for div in stack:
        issues.append(ScanIssue(div.start, "fenced div is never closed (add a ':::' line)"))
    return root


def walk(nodes: list[Node]) -> Iterator[Node]:
    for node in nodes:
        yield node
        if isinstance(node, Div):
            yield from walk(node.children)


def render_blocks(nodes: list[Node], div_fn: Callable[[Div, str], str] | None = None,
                  text_fn: Callable[[Text], str] | None = None) -> str:
    """Serialise nodes back to Markdown. ``div_fn(div, inner)`` may replace a div."""
    out: list[str] = []
    for node in nodes:
        if isinstance(node, Code):
            out.append("\n".join(node.lines))
        elif isinstance(node, Text):
            out.append(text_fn(node) if text_fn else "\n".join(node.lines))
        else:
            inner = render_blocks(node.children, div_fn, text_fn)
            if div_fn is not None:
                out.append(div_fn(node, inner))
            else:
                close = node.fence if node.end else ""
                out.append(node.raw_open + "\n" + inner + ("\n" + close if close else ""))
    return "\n".join(out)


# --------------------------------------------------------------------------- inline


def code_spans(line: str, *, comments: bool = False) -> list[tuple[int, int]]:
    """Half-open intervals of inline code spans (CommonMark backtick rule, per line).

    With ``comments``, HTML comments ``<!-- … -->`` closed on the line are included: whichever of
    a code span and a comment starts first wins, as in CommonMark (`` `<!--` `` is code).
    """
    spans: list[tuple[int, int]] = []
    i = 0
    n = len(line)
    while i < n:
        if line[i] == "\\":
            i += 2
            continue
        if comments and line.startswith("<!--", i):
            close = line.find("-->", i + 4)
            if close >= 0:
                spans.append((i, close + 3))
                i = close + 3
                continue
        if line[i] == "`":
            j = i
            while j < n and line[j] == "`":
                j += 1
            ticks = j - i
            k = j
            found = -1
            while k < n:
                if line[k] == "`":
                    m = k
                    while m < n and line[m] == "`":
                        m += 1
                    if m - k == ticks:
                        found = m
                        break
                    k = m
                else:
                    k += 1
            if found < 0:
                i = j
                continue
            spans.append((i, found))
            i = found
            continue
        i += 1
    return spans


def _inside(pos: int, spans: list[tuple[int, int]]) -> bool:
    return any(a <= pos < b for a, b in spans)


def sub_outside_code(pattern: re.Pattern, repl: Callable[[re.Match], str], line: str) -> str:
    """Replace the matches of ``pattern`` that start outside code spans and HTML comments."""
    spans = code_spans(line, comments=True)
    out = []
    last = 0
    for m in pattern.finditer(line):
        if _inside(m.start(), spans):
            continue
        out.append(line[last:m.start()])
        out.append(repl(m))
        last = m.end()
    out.append(line[last:])
    return "".join(out)


def find_outside_code(pattern: re.Pattern, line: str) -> list[re.Match]:
    """The matches of ``pattern`` that start outside code spans and HTML comments."""
    spans = code_spans(line, comments=True)
    return [m for m in pattern.finditer(line) if not _inside(m.start(), spans)]


def unangle(url: str) -> str:
    """A destination as written (``<…>`` or plain) without its angle brackets."""
    return url[1:-1] if url.startswith("<") and url.endswith(">") else url


def refdef(line: str) -> re.Match | None:
    """``line`` as a link reference definition (:data:`REFDEF_RE`), or None (also for footnotes)."""
    return REFDEF_RE.match(line)


def quoted_title(title: str) -> str:
    """A link title group as written (:data:`LINK_RE`: spaces, then ``"…"``, ``'…'`` or ``(…)``) as
    `` "…"``, which CommonMark and Pandoc read alike (Pandoc's Markdown has no ``(…)`` titles)."""
    title = title.strip()
    if title.startswith('"'):
        return " " + title
    inner = re.sub(r'\\.|"', lambda m: '\\"' if m.group() == '"' else m.group(), title[1:-1])
    return f' "{inner}"'


def _inline_lean_urls(text: str) -> list[tuple[int, str]]:
    """(offset, destination) of the inline links, images and autolinks of ``text`` that point at
    ``lean:``, outside code spans and comments, links inside link text included."""
    found: list[tuple[int, str]] = []
    spans: list[tuple[int, int]] = []
    for m in find_outside_code(LINK_RE, text):
        found += [(m.start("text") + k, url) for k, url in _inline_lean_urls(m.group("text"))]
        found.append((m.start("url"), unangle(m.group("url"))))
        spans.append(m.span())
    found += [(m.start(), "lean:" + m.group("gid")) for m in find_outside_code(LEAN_AUTOLINK_RE, text)
              if not _inside(m.start(), spans)]
    return sorted((pos, url) for pos, url in found if url.startswith("lean:"))


def lean_link_gids(line: str) -> list[str]:
    """The GIDs that ``lean:`` links on ``line`` cite, read as tbook.render reads links: inline
    ``[text](lean:GID)`` and ``[text](<lean:GID>)`` (also images, any title, links in link text)
    and autolinks ``<lean:GID>`` outside code spans and comments, or the destination of a reference
    definition ``[label]: lean:GID`` (also in a block quote or list item). Links written across
    lines are not read: :func:`stray_lean_links` finds them."""
    rd = refdef(line)
    urls = [unangle(rd.group("url"))] if rd else [url for _, url in _inline_lean_urls(line)]
    return [url[len("lean:"):] for url in urls if url.startswith("lean:")]


@dataclass
class StrayLean:
    """A ``lean:`` destination that :func:`lean_link_gids` does not read (see :func:`stray_lean_links`)."""

    line: int  # index of the line that holds the destination
    start: int  # what to replace: offsets into the lines joined with "\n"
    end: int
    replacement: str


# Spaces or tabs with at most one line end, after which the block-quote markers of the next line.
_WS1 = r"[ \t]*+(?:\n[ \t>]*+)?"
_STRAY_LINK_RE = re.compile(
    r"\]\(" + _WS1 + r"(?:<lean:[^<>\n]*>|lean:(?:[^\s()\\]|\\.|\((?:[^\s()\\]|\\.)*+\))*+)"
    r"(?:(?:[ \t]++(?:\n[ \t>]*+)?|\n[ \t>]*+)" + LINK_TITLE + r")?" + _WS1 + r"\)")
_STRAY_DEF_RE = re.compile(
    r"^" + CONTAINER + r"\[(?!\^)(?:[^\[\]\\\n]|\\.|\n(?![ \t>]*\n))+\]:(?P<gap>" + _WS1
    + r")(?P<dest><lean:[^<>\n]*>|lean:\S*)", re.M)
_STRAY_HTML_RE = re.compile(r"""\b(?:href|src)[ \t]*=[ \t]*["']?(?P<dest>lean:[^"'\s>]*)""", re.I)
_BLANK_LINE_RE = re.compile(r"\n[ \t>]*\n")
_MASK = "\x00"


def _link_opener(text: str, close: int) -> int | None:
    """The offset of the ``[`` that the ``]`` at ``close`` closes, within its paragraph, or None."""
    depth = 0
    i = close
    while i > 0:
        i -= 1
        ch = text[i]
        if ch == "\n" and _BLANK_LINE_RE.match(text, i):
            return None  # a blank line ends the paragraph
        if ch not in "[]":
            continue
        k = i
        while k > 0 and text[k - 1] == "\\":
            k -= 1
        if (i - k) % 2:
            continue  # escaped
        if ch == "]":
            depth += 1
        elif depth:
            depth -= 1
        else:
            return i
    return None


def stray_lean_links(lines: list[str]) -> list[StrayLean]:
    """The ``lean:`` destinations of a block of text lines that :func:`lean_link_gids` does not read.

    A link whose text, destination or title runs across lines (``[a\\nb](lean:GID)``), a reference
    definition whose label runs across lines or whose destination is on the next line
    (``[x]:\\n  lean:GID``), and an ``href``/``src`` attribute of raw HTML. Code spans and HTML
    comments (also those that run across lines) and every link the line scanner reads are skipped.
    Each :class:`StrayLean` says what to write instead so no target shows a ``lean:`` destination: a
    link becomes its text, a definition gets the destination ``#`` (as an unresolved one does), an
    attribute gets ``#``.
    """
    original = "\n".join(lines)
    if "lean:" not in original:
        return []
    chars = list(original)
    spans: list[tuple[int, int]] = []
    offset = para = 0  # para: where the current paragraph starts
    for k, line in enumerate(lines + [""]):
        if not line.strip(" \t>"):  # a blank line (also in a block quote) ends a paragraph
            spans += [(para + a, para + b) for a, b in code_spans(original[para:max(para, offset - 1)], comments=True)]
            para = offset + len(line) + 1
        if k == len(lines):
            break
        if refdef(line):
            spans.append((offset, offset + len(line)))
        else:
            for pattern in (LINK_RE, LEAN_AUTOLINK_RE):
                spans += [(offset + m.start(), offset + m.end()) for m in find_outside_code(pattern, line)]
        offset += len(line) + 1
    for a, b in spans:
        chars[a:b] = _MASK * (b - a)
    text = "".join(chars)
    out: list[StrayLean] = []
    for m in _STRAY_LINK_RE.finditer(text):
        opener = _link_opener(text, m.start())
        if opener is None:
            continue  # no "[" opens it: plain text, not a link
        start = opener - 1 if opener and text[opener - 1] == "!" else opener
        out.append(StrayLean(text.count("\n", 0, text.index("lean:", m.start())), start, m.end(),
                             original[opener + 1:m.start()]))
    for m in _STRAY_DEF_RE.finditer(text):
        # " #" right after the label: a "#" opening the next line would be an (empty) ATX heading.
        out.append(StrayLean(text.count("\n", 0, m.start("dest")), m.start("gap"), m.end("dest"), " #"))
    for m in _STRAY_HTML_RE.finditer(text):
        out.append(StrayLean(text.count("\n", 0, m.start("dest")), m.start("dest"), m.end("dest"), "#"))
    return sorted(out, key=lambda s: s.start)


def without_stray_lean(lines: list[str]) -> tuple[list[str], list[StrayLean]]:
    """``lines`` with each :func:`stray_lean_links` replaced, and the strays (as found in ``lines``).

    A stray inside another (raw HTML in the text of a link written across lines) is replaced on a
    later pass, once the outer one no longer overlaps it."""
    found = strays = stray_lean_links(lines)
    for _ in range(8):
        if not strays:
            break
        text = "\n".join(lines)
        bound = len(text)
        for s in reversed(strays):  # last first, so earlier offsets stay valid
            if s.end > bound:
                continue  # overlaps one replaced already: the next pass
            text = text[:s.start] + s.replacement + text[s.end:]
            bound = s.start
        lines = text.split("\n")
        strays = stray_lean_links(lines)
    return lines, found


def strip_lean_links(text: str) -> str:
    """``text`` (one line of inline Markdown) with every ``lean:`` link replaced by its text (an
    autolink by its GID): for titles, which never link to Lean."""
    def link(m: re.Match) -> str:
        inner = strip_lean_links(m.group("text"))
        if unangle(m.group("url")).startswith("lean:"):
            return inner
        whole, at = m.group(0), m.start()
        return whole[:m.start("text") - at] + inner + whole[m.end("text") - at:]

    text = sub_outside_code(LINK_RE, link, text)
    return sub_outside_code(LEAN_AUTOLINK_RE, lambda m: escape_markdown(m.group("gid")), text)


def iter_text_lines(nodes: list[Node]) -> Iterator[tuple[int, str]]:
    """(line number, text) for every line outside code and comment blocks, including lines nested in divs."""
    for node in nodes:
        if isinstance(node, Text):
            for k, line in enumerate(node.lines):
                yield node.start + k, line
        elif isinstance(node, Div):
            yield from iter_text_lines(node.children)


# --------------------------------------------------------------------------- titles as inline Markdown

# CommonMark: a backslash before any ASCII punctuation character escapes it.
_ESCAPED_RE = re.compile(r"\\([!-/:-@\[-`{-~])")
_ASCII_PUNCT_RE = re.compile(r"([!-/:-@\[-`{-~])")


def inline_segments(text: str) -> list[tuple[str, str]]:
    """One line of inline Markdown as consecutive ``(kind, piece)`` pairs: ``"math"`` for a formula
    (``$…$`` / ``$$…$$``, found exactly as tbook.mathrender finds them), ``"code"`` for a code span,
    ``"text"`` for the rest."""
    from . import mathrender  # it imports this module

    marks = sorted([(s.start, s.end, "math") for s in mathrender.find_math(text)[0]]
                   + [(a, b, "code") for a, b in code_spans(text)])
    out: list[tuple[str, str]] = []
    pos = 0
    for a, b, kind in marks:
        if a < pos:  # cannot happen (math never overlaps code); keep the first
            continue
        if a > pos:
            out.append(("text", text[pos:a]))
        out.append((kind, text[a:b]))
        pos = b
    if pos < len(text):
        out.append(("text", text[pos:]))
    return out


def unescape_markdown(text: str) -> str:
    """The plain text of a title written as inline Markdown: backslash escapes of ASCII punctuation
    are undone (``C\\*-代数`` → ``C*-代数``, ``\\$5`` → ``$5``), except inside formulas and code spans,
    so TeX survives (``$\\{x\\}$`` stays). Everything else stays as written."""
    if "\\" not in text:
        return text
    return "".join(unescape_text(piece) if kind == "text" else piece for kind, piece in inline_segments(text))


def unescape_text(piece: str) -> str:
    """Undo the backslash escapes of a ``"text"`` piece of :func:`inline_segments`."""
    return _ESCAPED_RE.sub(r"\1", piece)


def escape_markdown(text: str) -> str:
    """Backslash-escape every ASCII punctuation character of plain ``text``, so that a CommonMark
    reader that knows no math (mdBook reading SUMMARY.md) gives ``text`` back unchanged."""
    return _ASCII_PUNCT_RE.sub(r"\\\1", text)


def transform_text(nodes: list[Node], fn: Callable[[str], str]) -> None:
    """Apply ``fn`` to every non-code line, in place."""
    for node in walk(nodes):
        if isinstance(node, Text):
            node.lines = [fn(line) for line in node.lines]
