"""Small, dependency-free Markdown scanner shared by every renderer and by ``check``.

It understands just enough of Pandoc Markdown for the book conventions:

* the block structure (:func:`scan_blocks`), one model for every consumer (:func:`parse_blocks`,
  the PDF/EPUB stager, the math scanner): block quotes, list items, footnote and definition
  bodies as containers, and in them fenced code blocks (backticks or tildes), indented code
  blocks (4 columns past the container's content) and HTML comment blocks — all passed
  through verbatim;
* HTML comments: a ``<!--`` that opens a block (at most 3 columns into its container) and is not
  closed on its line starts a comment block that runs to the line holding ``-->``; any other
  ``<!--`` is an inline comment, which may go on over the following lines of its paragraph
  (:func:`close_comments`). No target shows comments, so links and references inside them
  are neither rewritten nor checked;
* fenced divs ``::: {.theorem #thm-x lean="…"}`` … ``:::`` (and ``::: theorem``),
  nested by stack, as in Pandoc;
* inline code spans, so that ``[@ref]``, ``lean:`` links and math inside code are ignored;
* cross references ``[@id]``, links and images (:data:`LINK_RE`), link reference
  definitions (:data:`REFDEF_RE`, also in block quotes and list items) and Lean links
  ``[text](lean:GID)`` in every one-line form (:func:`lean_link_gids`), and those it cannot read
  because they run across lines (:func:`stray_lean_links`; a ``<lean:GID>`` destination of one is
  no autolink, :func:`hide_lean_destinations`);
* titles as inline Markdown: :func:`unescape_markdown` gives their plain text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Iterator

# A top-level code fence. A backtick fence's info string cannot contain a backtick
# (CommonMark), so ```` ```x``` ```` at the start of a line is inline code, not a fence.
# :func:`scan_blocks` finds fences in containers too and decides where their blocks end.
FENCE_RE = re.compile(r"^(?P<indent> {0,3})(?P<fence>`{3,}(?=[^`]*$)|~{3,})(?P<info>.*)$")
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
# An inline link or image; ``url`` is the destination as written: ``<…>`` (may contain spaces), a
# plain one (balanced parentheses allowed) or empty (``[x]()``, a link to the page itself, as in
# CommonMark and Pandoc); ``title`` keeps the spaces before it.
LINK_RE = re.compile(r"(?P<bang>!?)\[(?P<text>" + LINK_TEXT + r")\]\([ \t]*"
                     r"(?P<url><[^<>\n]*>|(?:[^\s()\\]|\\.|\((?:[^\s()\\]|\\.)*+\))*+)"
                     r"(?P<title>[ \t]+" + LINK_TITLE + r")?[ \t]*\)")
# A CommonMark autolink to a declaration, ``<lean:GID>`` (mdBook links it; Pandoc's Markdown does not).
LEAN_AUTOLINK_RE = re.compile(r"<lean:(?P<gid>[^\s<>]*)>")
# A link reference definition ``[label]: url "title"`` on one line, as CommonMark reads it: at the
# left margin or inside block quotes and list items (``lead`` keeps their markers); after the
# destination only an optional title ("…", '…' or (…), with backslash escapes; it may continue on
# the next line). ``[注]: 见 [图](a.svg)`` or ``[1]: Knuth, TAOCP.`` is a paragraph, not a
# definition, and so is a footnote ``[^x]:``. REFDEF_DEST is what follows the label: the destination
# and the optional title, to the end of the line.
REFDEF_DEST = (r"""(?P<url><[^<>\n]*>|\S+)"""
               r"""(?P<rest>(?:[ \t]+(?:"(?:[^"\\]|\\.)*+"?|'(?:[^'\\]|\\.)*+'?|\((?:[^()\\]|\\.)*+\)?))?[ \t]*)$""")
REFDEF_RE = re.compile(r"""^(?P<lead>""" + CONTAINER + r"""\[(?!\^)(?:[^\[\]\\]|\\.)+\]:[ \t]*)""" + REFDEF_DEST)
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
    # Per line: an inline HTML comment is open at its start / at its end (:attr:`BlockScan.carry`);
    # read the lines through :func:`text_views` / :func:`map_text`.
    carry: list[tuple[bool, bool]] = field(default_factory=list)


@dataclass
class Code:
    """A fenced or indented code block (:func:`scan_blocks`): passed through verbatim."""
    lines: list[str]
    start: int


@dataclass
class Comment(Code):
    """A multi-line HTML comment block (:func:`scan_blocks`): passed through verbatim, like code."""


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
    severity: str = "error"


# --------------------------------------------------------------------------- block structure
#
# One line-based scanner (:func:`scan_blocks`) decides for every consumer which lines are code
# or HTML comment blocks and which lines go on with a paragraph: parse_blocks (and so check,
# the model and tbook.render), the PDF/EPUB stager (tbook.pandoc._code_mask) and the math
# scanner (tbook.mathrender). It follows the CommonMark block rules, which mdBook
# (pulldown-cmark) and Pandoc share for these constructs. Tabs count to the next multiple of
# 4 columns. Not modelled: the inside of raw HTML blocks (Pandoc reads Markdown there, mdBook
# does not), link reference definitions over several lines, and Pandoc-only list markers
# (``a.``, ``(1)``, ``#.``).

TEXT, BLANK, FENCE, CODE, COMMENT = "text", "blank", "fence", "code", "comment"

_QUOTE_MARK_RE = re.compile(r" {0,3}>")
_FENCE_OPEN_RE = re.compile(r"`{3,}(?=[^`]*$)|~{3,}")  # a backtick fence's info string has no backtick
_FENCE_CLOSE_RE = re.compile(r" {0,3}(`{3,}|~{3,}) *$")
_HR_RE = re.compile(r"(?:(?:\* *){3,}|(?:- *){3,}|(?:_ *){3,})$")
_SETEXT_RE = re.compile(r"(?:=+|-+) *$")
_LIST_RE = re.compile(r"(?:[-+*]|([0-9]{1,9})[.)])(?= |$)")
_DEFINITION_RE = re.compile(r"[:~](?= )")  # a definition (Pandoc, pulldown-cmark): its body is a container
_FOOTNOTE_START_RE = re.compile(r"\[\^[^\]\s]+\]:")  # a footnote definition: its body is indented 4 columns
_ATX_RE = re.compile(r"#{1,6}(?= |$)")
# HTML blocks that may interrupt a paragraph (CommonMark types 1 and 3-6; type 2 is a comment).
_HTML_BLOCK_RE = re.compile(
    r"<(?:(?:script|pre|style|textarea)(?=[\s>]|$)|\?|![A-Za-z]|!\[CDATA\[|/?(?:address|article|aside|base|"
    r"basefont|blockquote|body|caption|center|col|colgroup|dd|details|dialog|dir|div|dl|dt|fieldset|figcaption|"
    r"figure|footer|form|frame|frameset|h[1-6]|head|header|hr|html|iframe|legend|li|link|main|menu|menuitem|nav|"
    r"noframes|ol|optgroup|option|p|param|search|section|summary|table|tbody|td|tfoot|th|thead|title|tr|track|"
    r"ul)(?=[\s/>]|$))", re.I)


@dataclass
class BlockScan:
    """The block structure of a text, line by line (:func:`scan_blocks`)."""

    lines: list[str]
    kinds: list[str]  # per line: TEXT, BLANK, FENCE (fences included), CODE (indented) or COMMENT
    blocks: dict[int, int]  # first line of each fenced code, indented code and comment block → its last line
    # Per line: an inline HTML comment is open at its start / at its end. A ``<!--`` left open on a
    # line goes on over the following lines of its paragraph up to ``-->`` (CommonMark raw HTML may
    # span lines; mdBook and Pandoc both hide it).
    carry: list[tuple[bool, bool]]
    # (line, column) of each ``<!--`` that its paragraph never closes: text, not a comment.
    unclosed: list[tuple[int, int]] = field(default_factory=list)

    @property
    def hidden(self) -> list[bool]:
        """True for each line that no target shows as Markdown text: code and comment blocks, and
        the lines wholly inside an inline comment that spans lines."""
        return [k in (FENCE, CODE, COMMENT) or (lead and "-->" not in line)
                for k, (lead, _), line in zip(self.kinds, self.carry, self.lines)]


def scan_blocks(lines: list[str]) -> BlockScan:
    """The block structure of ``lines``: which are code or comment blocks, and the inline comments
    that go on from line to line.

    Containers: a block quote (``>``), a list item (its content starts after the marker and 1-4
    spaces), a definition (``:`` or ``~`` after its term, like a list item) and a footnote
    definition ``[^x]:`` (its body is indented 4 columns). A line belongs to a container while it
    is indented to the container's content (blank lines too), or as lazy text going on with a
    paragraph. In a container:

    * a line indented 4 columns past the content is indented code, unless it goes on with a
      paragraph; blank lines between such lines belong to the block;
    * a fence (at least three backticks or tildes, indented at most 3 columns) opens a fenced
      code block, which ends at a fence of the same character, at least as long and with nothing
      after it, or when its container ends;
    * a line that starts with ``<!--`` (indented at most 3 columns) and does not close it opens an
      HTML comment block, which ends at the first line holding ``-->`` (or with the text);
    * anything else is text: headings, thematic breaks, ``:::`` div fences and HTML blocks end
      the paragraph before them, other lines start or go on with one.
    """
    n = len(lines)
    kinds = [TEXT] * n
    blocks: dict[int, int] = {}
    cont = [False] * n  # a text line going on with the paragraph of the line before it
    # open containers: -1 a block quote, otherwise the columns of its content after its container's
    stack: list[int] = []
    leaf: object = None  # None, "p" (paragraph), "c" (indented code), ("f", char, length, first), ("m", first)
    before_blank: object = None  # the leaf at the last non-blank line (a definition follows its term)
    empty_item = 0  # len(stack) after a list item whose first line is blank, on the next line
    code = -1  # first line of the indented code block a code line after blank lines would go on with
    for i, raw in enumerate(lines):
        line = raw.expandtabs(4)
        pos = keep = 0  # keep: containers this line continues
        fresh, empty_item = empty_item, 0
        for col in stack:
            if col < 0:
                m = _QUOTE_MARK_RE.match(line, pos)
                if not m:
                    break
                pos = m.end() + (line[m.end():m.end() + 1] == " ")
            elif line[pos:].strip(" "):
                if len(line) - pos - len(line[pos:].lstrip(" ")) < col:
                    break
                pos += col
            keep += 1
        if fresh and keep >= fresh and not line[pos:].strip(" "):
            keep = fresh - 1  # a list item can begin with at most one blank line
        if isinstance(leaf, tuple):
            if leaf[0] == "m":  # a comment block ends at the first line holding -->, whatever the containers
                kinds[i] = COMMENT
                blocks[leaf[1]] = i
                if "-->" in raw:
                    leaf = None
                continue
            if keep == len(stack):
                kinds[i] = FENCE
                blocks[leaf[3]] = i
                m = _FENCE_CLOSE_RE.match(line, pos)
                if m and m.group(1)[0] == leaf[1] and len(m.group(1)) >= leaf[2]:
                    leaf = None
                continue
            leaf = None  # its container ended, so did the fence
        while True:  # the blocks this line starts
            rest = line[pos:]
            body = rest.lstrip(" ")
            ind = len(rest) - len(body)
            inner = keep == len(stack)
            if not body:
                if keep < len(stack):
                    code = -1
                del stack[keep:]
                kinds[i] = BLANK
                if i == 0 or kinds[i - 1] != BLANK:
                    before_blank = leaf
                leaf = None
                break
            if ind >= 4:
                if leaf == "p":
                    cont[i] = True  # indented code cannot interrupt a paragraph
                    break
                del stack[keep:]
                kinds[i] = CODE
                if code >= 0 and all(kinds[k] == BLANK for k in range(blocks[code] + 1, i)):
                    kinds[blocks[code] + 1:i] = [CODE] * (i - blocks[code] - 1)
                    blocks[code] = i
                else:
                    code = blocks[i] = i
                leaf = "c"
                break
            m = _FENCE_OPEN_RE.match(body)
            if m:
                del stack[keep:]
                leaf = ("f", m.group(0)[0], len(m.group(0)), i)
                kinds[i] = FENCE
                blocks[i] = i
                break
            if body[0] == ">":
                del stack[keep:]
                stack.append(-1)
                keep = len(stack)
                pos += ind + 1 + (body[1:2] == " ")
                leaf, code = None, -1
                continue
            if body.startswith("<!--"):
                del stack[keep:]
                if "-->" in body[4:]:  # closed on its line: left to the inline scanners (code_spans)
                    leaf = None
                else:
                    leaf = ("m", i)
                    kinds[i] = COMMENT
                    blocks[i] = i
                break
            if (leaf == "p" and inner and _SETEXT_RE.match(body)) or _HR_RE.match(body):
                del stack[keep:]
                leaf = None
                break
            m = _LIST_RE.match(body)
            after = body[m.end():] if m else ""
            empty = not after.strip(" ")
            if m and not (leaf == "p" and inner and (empty or (m.group(1) is not None and int(m.group(1)) != 1))):
                del stack[keep:]
                gap = len(after) - len(after.lstrip(" "))
                stack.append(ind + m.end() + (1 if empty or gap > 4 else gap))
                keep = len(stack)
                leaf, code = None, -1
                if empty:
                    empty_item = len(stack)
                    break
                pos += stack[-1]
                continue
            m = _DEFINITION_RE.match(body)
            if m and (leaf == "p" or (leaf is None and i and kinds[i - 1] == BLANK and before_blank in ("p", "c"))):
                del stack[keep:]
                after = body[m.end():]
                gap = len(after) - len(after.lstrip(" "))
                stack.append(ind + m.end() + (1 if gap > 4 else gap))
                keep = len(stack)
                leaf, code = None, -1
                pos += stack[-1]
                continue
            m = _FOOTNOTE_START_RE.match(body)
            if m:
                del stack[keep:]
                stack.append(4)
                keep = len(stack)
                leaf, code = None, -1
                pos += ind + m.end()
                pos = len(line) - len(line[pos:].lstrip(" "))
                continue
            if _ATX_RE.match(body) or (pos == 0 and (DIV_OPEN_RE.match(raw) or DIV_CLOSE_RE.match(raw))):
                del stack[keep:]
                leaf = None
                break
            if _HTML_BLOCK_RE.match(body):  # its lines follow as one block, like a paragraph's
                del stack[keep:]
                leaf = "p"
                break
            if leaf == "p":
                cont[i] = True  # lazily, when containers ended
            else:
                del stack[keep:]
                leaf = "p"
            break
        if kinds[i] not in (CODE, BLANK):
            code = -1
    carry: list[tuple[bool, bool]] = [(False, False)] * n
    unclosed: list[tuple[int, int]] = []
    i = 0
    while i < n:
        if kinds[i] != TEXT:
            i += 1
            continue
        j = i + 1
        while j < n and kinds[j] == TEXT and cont[j]:
            j += 1
        flags, opened = _paragraph_comments(lines[i:j])
        carry[i:j] = flags
        if opened is not None:
            unclosed.append((i + opened[0], opened[1]))
        i = j
    return BlockScan(list(lines), kinds, blocks, carry, unclosed)


def _open_comment(line: str) -> int | None:
    """Column of the first ``<!--`` on ``line`` that the line does not close (not escaped, outside
    code spans), or None."""
    spans = code_spans(line, comments=True)
    i = line.find("<!--")
    while i >= 0:
        backslashes = i - len(line[:i].rstrip("\\"))
        if backslashes % 2 == 0 and not _inside(i, spans):
            return i
        i = line.find("<!--", i + 1)
    return None


def _paragraph_comments(lines: list[str]) -> tuple[list[tuple[bool, bool]], tuple[int, int] | None]:
    """:attr:`BlockScan.carry` for the lines of one paragraph, and where a ``<!--`` the paragraph
    never closes stands (then it is text, as are the lines after it)."""
    out: list[tuple[bool, bool]] = []
    inside = False
    opened: tuple[int, int] | None = None
    for k, line in enumerate(lines):
        lead = inside
        if inside:
            if "-->" not in line:
                out.append((True, True))
                continue
            inside = False
        col = _open_comment(close_comments(line, (lead, False)))
        if col is not None:
            inside = True
            opened = (k, col - 4 if lead else col)
        out.append((lead, inside))
    if inside and opened is not None:
        k = opened[0]
        out[k] = (out[k][0], False)
        out[k + 1:] = [(False, False)] * (len(out) - k - 1)
        return out, opened
    return out, None


def close_comments(line: str, carry: tuple[bool, bool]) -> str:
    """``line`` as the per-line scanners must read it: an inline comment open at its start
    (``carry[0]``) gets a ``<!--`` before it, one open at its end (``carry[1]``) a ``-->`` after it,
    so that :func:`code_spans` (and everything built on it) sees the comment closed on the line."""
    lead, trail = carry
    return ("<!--" if lead else "") + line + ("-->" if trail else "")


def map_closed(fn: Callable[[str], str], line: str, carry: tuple[bool, bool]) -> str:
    """``fn(line)`` with the inline comments that span lines closed on the line (:func:`close_comments`)
    while ``fn`` runs; ``fn`` leaves comments alone, so the added marks are taken off again."""
    lead, trail = carry
    if not (lead or trail):
        return fn(line)
    out = fn(close_comments(line, carry))
    if (lead and not out.startswith("<!--")) or (trail and not out.endswith("-->")):
        return fn(line)
    return out[4 if lead else 0:len(out) - 3 if trail else len(out)]


def hidden_spans(line: str, carry: tuple[bool, bool] = (False, False)) -> list[tuple[int, int]]:
    """Half-open intervals of ``line`` inside code spans and HTML comments, also comments that
    go on from the line before (``carry[0]``) or to the next (``carry[1]``)."""
    shift = 4 if carry[0] else 0
    spans = code_spans(close_comments(line, carry), comments=True)
    return [(max(a - shift, 0), min(b - shift, len(line))) for a, b in spans if b > shift and a - shift < len(line)]


def fenced_code_lines(lines: list[str]) -> list[bool]:
    """True for each line of a fenced code block (fences included), exactly as :func:`parse_blocks` sees them
    (so a fence inside an HTML comment block is not one)."""
    return [k == FENCE for k in scan_blocks(lines).kinds]


def indented_code_lines(lines: list[str]) -> list[bool]:
    """True for each line of an indented code block (:func:`scan_blocks`): 4 or more columns past
    the content of its container (top level, block quote, list item, footnote or definition
    body), not going on with a paragraph. Blank lines between its lines belong to the block."""
    return [k == CODE for k in scan_blocks(lines).kinds]


def parse_blocks(text: str, issues: list[ScanIssue] | None = None) -> list[Node]:
    """Split Markdown into Text / Code / Comment / Div nodes (divs nested), by :func:`scan_blocks`."""
    issues = issues if issues is not None else []
    root: list[Node] = []
    stack: list[Div] = []
    lines = text.split("\n")
    scan = scan_blocks(lines)
    i = 0

    def container() -> list[Node]:
        return stack[-1].children if stack else root

    def add_text(line: str, lineno: int) -> None:
        nodes = container()
        if nodes and isinstance(nodes[-1], Text):
            nodes[-1].lines.append(line)
            nodes[-1].carry.append(scan.carry[lineno - 1])
        else:
            nodes.append(Text([line], lineno, [scan.carry[lineno - 1]]))

    for k, col in scan.unclosed:
        later = next((j for j in range(k + 1, len(lines)) if "-->" in lines[j]), None)
        if later is not None:
            issues.append(ScanIssue(k + 1, f"'<!--' (column {col + 1}) is not closed in its paragraph: the HTML "
                                           f"edition shows it as text, while Pandoc (PDF/EPUB) may hide everything "
                                           f"up to the '-->' on line {later + 1}; close it in the paragraph, or write "
                                           f"it as inline code `<!--`", "warning"))
    while i < len(lines):
        line = lines[i]
        lineno = i + 1
        end = scan.blocks.get(i)
        if end is not None:
            if scan.kinds[i] == COMMENT:
                if "-->" not in lines[end]:
                    issues.append(ScanIssue(lineno, "HTML comment is never closed (add '-->'); everything after it "
                                                    "is part of the comment"))
                container().append(Comment(lines[i:end + 1], lineno))
            else:
                container().append(Code(lines[i:end + 1], lineno))
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
    lines are not read: :func:`stray_lean_links` finds them. Read a text node's lines through
    :func:`text_views`, where the ``<lean:GID>`` destination of such a link is no autolink."""
    rd = refdef(line)
    urls = [unangle(rd.group("url"))] if rd else [url for _, url in _inline_lean_urls(line)]
    return [url[len("lean:"):] for url in urls if url.startswith("lean:")]


def _node_carry(node: Text) -> list[tuple[bool, bool]]:
    return node.carry if len(node.carry) == len(node.lines) else [(False, False)] * len(node.lines)


def text_views(node: Text) -> list[str]:
    """The lines of ``node`` as the per-line scanners must read them (:func:`close_comments`,
    :func:`hide_lean_destinations`)."""
    return [close_comments(line, carry) for line, carry in zip(hide_lean_destinations(node.lines), _node_carry(node))]


def map_text(node: Text, fn: Callable[[str], str]) -> list[str]:
    """``fn`` applied to each line of ``node``, inline comments that span lines kept out of its reach
    (:func:`map_closed`), and so are the ``<lean:…>`` destinations of links written across lines
    (:func:`hide_lean_destinations`; they come back as written)."""
    lines = hide_lean_destinations(node.lines)
    out = [map_closed(fn, line, carry) for line, carry in zip(lines, _node_carry(node))]
    return out if lines is node.lines else [line.replace(_HIDDEN_LT, "<") for line in out]


@dataclass
class StrayLean:
    """A ``lean:`` destination that :func:`lean_link_gids` does not read (see :func:`stray_lean_links`)."""

    line: int  # index of the line that holds the destination
    start: int  # what to replace: offsets into the lines joined with "\n"
    end: int
    replacement: str
    dest: int = -1  # offset of the destination (``<lean:…>`` or ``lean:…``)


# Spaces or tabs with at most one line end, after which the block-quote markers of the next line.
_WS1 = r"[ \t]*+(?:\n[ \t>]*+)?"
_STRAY_LINK_RE = re.compile(
    r"\]\(" + _WS1 + r"(?P<dest><lean:[^<>\n]*>|lean:(?:[^\s()\\]|\\.|\((?:[^\s()\\]|\\.)*+\))*+)"
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
    (``[x]:\\n  lean:GID``), and an ``href``/``src`` attribute of raw HTML. The destination may be
    written ``<lean:GID>``: CommonMark reads it as the link's destination, not as an autolink (the
    line scanners do not either, :func:`hide_lean_destinations`). Code spans and HTML comments (also
    those that run across lines) and every link the line scanner reads are skipped. Each
    :class:`StrayLean` says what to write instead so no target shows a ``lean:`` destination: a link
    becomes its text, a definition gets the destination ``#`` (as an unresolved one does), an
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
        else:  # not the autolinks: the patterns below find one only where it is a destination
            spans += [(offset + m.start(), offset + m.end()) for m in find_outside_code(LINK_RE, line)]
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
        out.append(StrayLean(text.count("\n", 0, m.start("dest")), start, m.end(),
                             original[opener + 1:m.start()], m.start("dest")))
    for m in _STRAY_DEF_RE.finditer(text):
        # " #" right after the label: a "#" opening the next line would be an (empty) ATX heading.
        out.append(StrayLean(text.count("\n", 0, m.start("dest")), m.start("gap"), m.end("dest"), " #",
                             m.start("dest")))
    for m in _STRAY_HTML_RE.finditer(text):
        out.append(StrayLean(text.count("\n", 0, m.start("dest")), m.start("dest"), m.end("dest"), "#",
                             m.start("dest")))
    return sorted(out, key=lambda s: s.start)


# Stands for the "<" of a ``<lean:…>`` destination while the line scanners read a line (a private-use
# character, so never in a book; :func:`hide_lean_destinations` leaves text that has one alone).
_HIDDEN_LT = "\ue000"


def hide_lean_destinations(lines: list[str]) -> list[str]:
    """``lines`` (consecutive text lines) with the ``<`` of each ``<lean:…>`` that is the destination of
    a link or definition written across lines (:func:`stray_lean_links`) replaced by U+E000, so that
    the line scanners do not read it as an autolink; ``lines`` itself when there is none. The line
    scanners see ``b](<lean:GID>)`` or ``<lean:GID>`` alone on its line, while CommonMark reads it as
    the destination of the link or definition begun on an earlier line."""
    text = "\n".join(lines)
    if "<lean:" not in text or _HIDDEN_LT in text:
        return lines
    marks = [s.dest for s in stray_lean_links(lines) if text.startswith("<lean:", s.dest)]
    if not marks:
        return lines
    chars = list(text)
    for k in marks:
        chars[k] = _HIDDEN_LT
    return "".join(chars).split("\n")


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
    """(line number, text) for every line outside code and comment blocks, including lines nested in
    divs; an inline comment that spans lines is closed on each of them (:func:`text_views`)."""
    for node in nodes:
        if isinstance(node, Text):
            for k, line in enumerate(text_views(node)):
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
    """Apply ``fn`` to every line outside code and comment blocks, in place (:func:`map_text`)."""
    for node in walk(nodes):
        if isinstance(node, Text):
            node.lines = map_text(node, fn)
