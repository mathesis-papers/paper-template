"""One block model for every target: :func:`tbook.mdscan.scan_blocks`.

Which lines are code (fenced or indented, in any container: block quote, list item, footnote or
definition body), HTML comment blocks, or inside an inline comment that spans lines is decided once,
by the CommonMark block rules that mdBook and Pandoc share. :func:`tbook.mdscan.parse_blocks` (and
so check, the model and both render targets), the PDF/EPUB stager (:func:`tbook.pandoc._code_mask`)
and the math scanner (:func:`tbook.mathrender.find_math`) all read it, so nothing inside code or a
comment is rewritten, checked or typeset as math by one of them and not by the others.

Run: PYTHONPATH=tools:tools/tests .venv/bin/python -m unittest test_blocks
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

from tbook import check, config, mathrender, mdscan, model
from tbook import pandoc as tp
from test_followups_pandoc import MDBOOK, math_hidden_lines, stage_chapters
from test_markdown import GID_OK, Repo, write
from test_pandoc import have_pandoc


def parse_hidden(text: str) -> list[bool]:
    """The lines parse_blocks keeps away from rewriting and checking: code and comment nodes, and
    text lines wholly inside an inline comment that spans lines."""
    lines = text.split("\n")
    hidden = [False] * len(lines)
    for node in mdscan.walk(mdscan.parse_blocks(text)):
        if isinstance(node, mdscan.Code):
            hidden[node.start - 1:node.start - 1 + len(node.lines)] = [True] * len(node.lines)
        elif isinstance(node, mdscan.Text):
            for k, (line, (lead, _)) in enumerate(zip(node.lines, node.carry)):
                hidden[node.start - 1 + k] = lead and "-->" not in line
    return hidden


# A varied corpus: code and comments in every container, and the text around them.
CORPUS = {
    "top-level indented code": "段落 $a$\n\n    代码 $x$ [@t]\n\n    仍是代码 [一](ch02.md)\n\n正文 $b$\n",
    "paragraph continuation is text": "文字 $a$\n    续行 $b$ [@t]\n",
    "comment opener in indented code": "示例：\n\n    <!-- 待补 $x$\n\n之后 [@t] $a$。\n\n::: {.theorem #t}\n内容。\n:::\n",
    "list item code": "1. 运行：\n\n       echo $HOME/$USER\n       见[一](ch02.md)与[^n]\n\n正文 $a$[^n]。\n\n[^n]: 脚注。\n",
    "list item paragraph": "- 项 $a$\n\n    项的续段 $b$ [@t]\n\n结束\n",
    "nested list code": "- 甲\n  - 乙\n\n        乙的代码 $x$\n\n  甲的续段 $a$\n",
    "definition paragraph": "黄金比\n\n:   满足 $a$ 的正数。\n\n    它的倒数是 $b$，见[第二章](ch02.md)。\n\n        定义里的代码 $x$\n",
    "footnote body": "正文[^n]。\n\n[^n]: 注 $a$\n\n    注的第二段 $b$\n\n        注里的代码 $x$\n",
    "block quote code": "> 引文 $a$\n>\n>     引文里的代码 $x$\n",
    "quote in item": "- 项\n\n  > 引 $a$\n  >\n  >     代码 $x$\n",
    "fences in containers": "> ```\n> $x$\n> ```\n\n- 项\n\n  ```\n  $y$ [@t]\n  ```\n\n正文 $a$\n",
    "comment block": "正文 $a$\n\n<!--\n![图](fig.svg) $x$\n\n[@t]\n-->\n后文 $b$\n",
    "inline comment over lines": "正文 <!-- 待补 $x$\n![图 5](fig5.svg) [@t]\n还在注释里 $y$ --> 可见 $a$\n",
    "inline comment never closed": "段落 <!-- 未闭合 $a$\n下一行 $b$\n\n再下一段 $c$\n",
    "inline comment in list item": "- 项 <!-- 跨行 $x$\n  续行 --> 可见 $a$\n- 新项 $b$\n",
    "code span opener": "`<!--` 不是注释 $a$\n下一行 $b$ -->\n",
    "div with code": "::: {.theorem #t}\n陈述 $a$。\n\n    代码 $x$\n:::\n\n后文 $b$\n",
}


class ScannersAgreeTest(unittest.TestCase):
    """parse_blocks, the Pandoc stager's mask and the math scanner hide the same lines."""

    def test_same_hidden_lines(self):
        for name, text in CORPUS.items():
            lines = text.split("\n")
            want = parse_hidden(text)
            with self.subTest(name):
                self.assertEqual(tp._code_mask(lines), want)
                self.assertEqual(mdscan.scan_blocks(lines).hidden, want)
                math = math_hidden_lines(text)
                self.assertEqual([h for h, line in zip(math, lines) if line.strip()],
                                 [h for h, line in zip(want, lines) if line.strip()])

    def test_corpus_math(self):
        """Formulas in code and comments ($x$, $y$ in the corpus) are not math; the others are."""
        for name, text in CORPUS.items():
            with self.subTest(name):
                found = [s.tex for s in mathrender.find_math(text)[0]]
                self.assertNotIn("x", found)
                self.assertNotIn("y", found)
        self.assertEqual([s.tex for s in mathrender.find_math(CORPUS["definition paragraph"])[0]], ["a", "b"])
        self.assertEqual([s.tex for s in mathrender.find_math(CORPUS["inline comment over lines"])[0]], ["a"])
        self.assertEqual([s.tex for s in mathrender.find_math(CORPUS["inline comment never closed"])[0]],
                         ["a", "b", "c"])


# --------------------------------------------------------------------------- finding 8: definition lists

DEFINITION = textwrap.dedent("""\
    # 第一章 甲

    黄金比

    :   满足 $\\varphi^2=\\varphi+1$ 的正数。

        它的倒数是 $\\varphi-1$，见[第二章](ch02.md)与脚注[^n]。

    [^n]: 脚注。
    """)


class DefinitionListTest(unittest.TestCase):
    """A definition's second paragraph (indented like its first line) is not indented code."""

    def test_not_code(self):
        lines = DEFINITION.split("\n")
        self.assertFalse(any(mdscan.indented_code_lines(lines)))
        self.assertFalse(any(tp._code_mask(lines)))
        self.assertEqual([s.tex for s in mathrender.find_math(DEFINITION)[0]],
                         ["\\varphi^2=\\varphi+1", "\\varphi-1"])
        for marker in (":", "~", "  :"):
            text = f"术语\n\n{marker} 定义\n\n  第二段\n\n      定义里的代码\n"
            with self.subTest(marker):
                self.assertEqual(mdscan.indented_code_lines(text.split("\n")),
                                 [False] * 6 + [True, False])

    def test_staged_links_and_footnotes(self):
        with tempfile.TemporaryDirectory() as tmp:
            staged = stage_chapters(Path(tmp), {"ch01.md": DEFINITION, "ch02.md": "# 第二章 乙\n\n正文。\n"})
            md = staged.book_md.read_text(encoding="utf-8")
        self.assertIn("    它的倒数是 $\\varphi-1$，见[第二章](#ch-ch02)与脚注[^ch-ch01--n]。", md)
        self.assertEqual(staged.warnings, [])


# --------------------------------------------------------------------------- findings 3 and 5: indented code

INDENTED_COMMENT = textwrap.dedent(f"""\
    # 第一章

    ::: {{.theorem #thm-ok lean="{GID_OK}"}}
    陈述。
    :::

    HTML 注释以这样的一行开头：

        <!-- 待补

    之后的引用 [@thm-nonexistent] 与 [Lean](lean:Fake/Module.fake)。

    ::: {{.theorem #thm-extra title="补充" lean="Fake/Module.not_a_theorem"}}
    内容。
    :::
    """)

INDENTED_LINKS = textwrap.dedent(f"""\
    # 第一章

    ::: {{.theorem #thm-ok lean="{GID_OK}"}}
    陈述。
    :::

    引用的写法（缩进代码块）：

        见 [@thm-ok] 与 [名](lean:D5/X/Y.z)，图 ![图](../assets/nope.svg)，章 [一](README.md)。

    1. 列表项里的代码：

           见 [@thm-ok] 与 [名](lean:D5/X/Y.z)，图 ![图](../assets/nope.svg)，$HOME/$USER

    > 引文里的代码：
    >
    >     见 [@thm-ok] 与 ![图](../assets/nope.svg)

    正文 [@thm-ok]，[一](README.md)。
    """)
CODE_LINES = [line for line in INDENTED_LINKS.split("\n") if "[@thm-ok] 与" in line]


def checked(m: model.EditionModel) -> list[str]:
    """What ``./tbook check`` says about one edition's chapters (no lock needed)."""
    issues = list(m.issues)
    check.check_env_policy(m, issues)
    check.check_links(m, config.load_site(), issues)
    return [i.format() for i in issues]


class IndentedCodeCommentTest(unittest.TestCase):
    """Finding 3: ``    <!--`` in an indented code block is code, not the start of a comment block."""

    def test_scanner(self):
        issues: list[mdscan.ScanIssue] = []
        blocks = mdscan.parse_blocks(INDENTED_COMMENT, issues)
        self.assertEqual(issues, [])
        self.assertEqual([type(b).__name__ for b in blocks], ["Text", "Div", "Text", "Code", "Text", "Div", "Text"])
        self.assertEqual(blocks[3].lines, ["    <!-- 待补"])
        self.assertIn("thm-extra", [d.attrs.id for d in mdscan.walk(blocks) if isinstance(d, mdscan.Div)])
        lines = INDENTED_COMMENT.split("\n")
        self.assertEqual([line for line, h in zip(lines, tp._code_mask(lines)) if h], ["    <!-- 待补"])
        # Without a later comment there is no false "never closed" error either.
        issues.clear()
        mdscan.parse_blocks("示例：\n\n    <!-- 待补\n\n之后 [@x]。\n", issues)
        self.assertEqual(issues, [])

    def test_check_sees_what_follows(self):
        with Repo() as repo:
            write(repo.edition.dir / "ch01.md", INDENTED_COMMENT)
            m = model.load_edition(repo.edition)
            self.assertIn("thm-extra", m.envs)
            out = "\n".join(checked(m))
            self.assertIn("[@thm-nonexistent] refers to no environment", out)
            self.assertIn("'Fake/Module.fake'", out)
            self.assertIn("'Fake/Module.not_a_theorem'", out)
            self.assertNotIn("never closed", out)


class IndentedCodeVerbatimTest(unittest.TestCase):
    """Findings 5 and 9: links, references, images and math in indented code — top level, in a
    list item or a block quote — are neither rewritten nor checked, by every target."""

    def test_model_and_check_skip_code(self):
        with Repo() as repo:
            write(repo.edition.dir / "ch01.md", INDENTED_LINKS)
            m = model.load_edition(repo.edition)
            doc = next(d for d in m.chapters if d.chapter.path == "ch01.md")
            self.assertEqual([r for _, r in doc.refs], ["thm-ok"])
            self.assertEqual(doc.lean_links, [])
            self.assertEqual(checked(m), [])

    def test_render_leaves_code_alone(self):
        with Repo() as repo:
            write(repo.edition.dir / "ch01.md", INDENTED_LINKS)
            repo.model = model.load_edition(repo.edition)
            for target in ("mdbook", "pandoc"):
                with self.subTest(target):
                    out, ctx = repo.render("ch01.md", target)
                    for line in CODE_LINES:
                        self.assertIn("\n" + line + "\n", out)
                    self.assertNotIn("[@thm-ok]", out.replace(CODE_LINES[0], "").replace(CODE_LINES[1], "")
                                     .replace(CODE_LINES[2], ""))
                    self.assertEqual(ctx.issues, [])

    def test_math_and_staging_leave_code_alone(self):
        self.assertEqual(mathrender.find_math(INDENTED_LINKS)[0], [])
        with tempfile.TemporaryDirectory() as tmp:
            text = "# 第一章\n\n1. 运行：\n\n       见[一](ch02.md)与[^n]\n\n正文[^n]，[一](ch02.md)。\n\n[^n]: 脚注。\n"
            staged = stage_chapters(Path(tmp), {"ch01.md": text, "ch02.md": "# 第二章\n"})
            md = staged.book_md.read_text(encoding="utf-8")
        self.assertIn("\n       见[一](ch02.md)与[^n]\n", md)
        self.assertIn("正文[^ch-ch01--n]，[一](#ch-ch02)。", md)

    def test_containers(self):
        cases = {
            "list item, content column + 4": ("1. a\n\n       code\n", [False, False, True, False]),
            "list item paragraph": ("- a\n\n    para\n", [False, False, False, False]),
            "nested list": ("- a\n  - b\n\n        code\n", [False, False, False, True, False]),
            "code on the marker line": ("-     code\n", [True, False]),
            "block quote": ("> a\n>\n>     code\n", [False, False, True, False]),
            "quote in a list item": ("- a\n\n  > q\n  >\n  >     code\n", [False] * 4 + [True, False]),
            "footnote body": ("[^n]: a\n\n    para\n\n        code\n", [False] * 4 + [True, False]),
            "item ends at a blank line": ("- a\n\n  b\n\n    c\n\nd\n\n    code\n", [False] * 8 + [True, False]),
            "lazy line": ("- a\nlazy\n\n      code\n", [False] * 3 + [True, False]),
            "paragraph continuation": ("text\n    more\n", [False, False, False]),
            "blank lines inside the block": ("x\n\n    a\n\n    b\n", [False, False, True, True, True, False]),
        }
        for name, (text, want) in cases.items():
            with self.subTest(name):
                self.assertEqual(mdscan.indented_code_lines(text.split("\n")), want)


# --------------------------------------------------------------------------- finding 7: comments over lines

COMMENT_OVER_LINES = textwrap.dedent(f"""\
    # 第一章

    ::: {{.theorem #thm-ok lean="{GID_OK}"}}
    陈述。
    :::

    正文继续 <!-- TODO: 以后补图
    ![图 5](fig5.svg) 与 [@thm-todo3] $x$
    还没完 [名](lean:Fake/Module.fake) --> 见 [@thm-ok] 与 ![图](../assets/fig.svg)。
    """)


class CommentOverLinesTest(unittest.TestCase):
    """Finding 7: a ``<!--`` left open on a line goes on over the following lines of its
    paragraph up to ``-->``; if the paragraph ends first, it was text."""

    def test_carry(self):
        lines = COMMENT_OVER_LINES.split("\n")
        scan = mdscan.scan_blocks(lines)
        self.assertEqual(scan.carry[6:9], [(False, True), (True, True), (True, False)])
        self.assertEqual(scan.hidden[6:9], [False, True, False])
        self.assertEqual(mdscan.hidden_spans(lines[6], scan.carry[6]), [(5, len(lines[6]))])
        self.assertEqual(mdscan.hidden_spans(lines[8], scan.carry[8]), [(0, lines[8].index("-->") + 3)])
        text = [line for _, line in mdscan.iter_text_lines(mdscan.parse_blocks(COMMENT_OVER_LINES))]
        self.assertEqual([m.group("id") for line in text for m in mdscan.find_outside_code(mdscan.REF_RE, line)],
                         ["thm-ok"])
        self.assertEqual([s.tex for s in mathrender.find_math(COMMENT_OVER_LINES)[0]], [])

    def test_paragraph_end_makes_it_text(self):
        cases = {
            "blank line": "段落 <!-- 未闭合\n下一行 [@a]\n\n再下一段 [@b] -->\n",
            "new list item": "- 项 <!-- 不闭合\n- 新项 [@a] --> [@b]\n",
            "heading": "段落 <!-- 未闭合\n# 标题 [@a] -->\n[@b]\n",
            "fence": "段落 <!-- 未闭合\n```\n-->\n```\n[@a] [@b]\n",
        }
        for name, text in cases.items():
            with self.subTest(name):
                issues: list[mdscan.ScanIssue] = []
                blocks = mdscan.parse_blocks(text, issues)
                refs = [m.group("id") for _, line in mdscan.iter_text_lines(blocks)
                        for m in mdscan.find_outside_code(mdscan.REF_RE, line)]
                self.assertEqual(refs, ["a", "b"])
                lines = text.split("\n")
                self.assertEqual(tp._code_mask(lines), parse_hidden(text))
                # mdBook shows such a "<!--" as text; Pandoc hides everything up to the next "-->".
                self.assertEqual([(i.line, i.severity, "not closed in its paragraph" in i.message)
                                  for i in issues], [(1, "warning", True)])
        issues = []
        mdscan.parse_blocks("段落 <!-- 未闭合\n\n再下一段\n", issues)
        self.assertEqual(issues, [], "no later '-->': text in every target")

    def test_model_check_render_and_staging(self):
        with Repo() as repo:
            write(repo.edition.dir / "ch01.md", COMMENT_OVER_LINES)
            m = model.load_edition(repo.edition)
            doc = next(d for d in m.chapters if d.chapter.path == "ch01.md")
            self.assertEqual([r for _, r in doc.refs], ["thm-ok"])
            self.assertEqual(doc.lean_links, [])
            self.assertEqual(checked(m), [])
            repo.model = m
            for target in ("mdbook", "pandoc"):
                with self.subTest(target):
                    out, ctx = repo.render("ch01.md", target)
                    self.assertIn("正文继续 <!-- TODO: 以后补图\n![图 5](fig5.svg) 与 [@thm-todo3] $x$\n"
                                  "还没完 [名](lean:Fake/Module.fake) --> 见 [定理1.1](", out)
                    self.assertIn("与 ![图](_book/assets/fig.svg)。", out)
                    self.assertEqual(ctx.issues, [])
            with tempfile.TemporaryDirectory() as tmp:
                warnings: list[str] = []
                linker = tp._Linker(Path(tmp), repo.edition, {"ch01.md": "ch-ch01"}, warnings, set(), online="")
                md = "正文 <!-- 待补\n![图 5](fig5.svg) [二](ch02.md)\n还在 --> [一](ch01.md)\n"
                out = tp.restructure_chapter(md, chapter_path="ch01.md", depth=0, chapter_id="ch-ch01", title="一",
                                             classes=["tr-chapter"], kv={}, linker=linker)
                self.assertIn("正文 <!-- 待补\n![图 5](fig5.svg) [二](ch02.md)\n还在 --> [一](#ch-ch01)\n", out)
                self.assertEqual(warnings, [])
        scoped = tp.scope_footnotes("正文[^n] <!-- 待补[^n]\n仍在[^n] --> 之后[^n]\n\n[^n]: 注。\n", "ch-ch01")
        self.assertEqual(scoped, "正文[^ch-ch01--n] <!-- 待补[^n]\n仍在[^n] --> 之后[^ch-ch01--n]\n\n"
                                 "[^ch-ch01--n]: 注。\n")

    def test_map_closed(self):
        def upper(line: str) -> str:  # like every per-line rewrite: comments and code spans are left alone
            return mdscan.sub_outside_code(re.compile("[a-z]"), lambda m: m.group().upper(), line)

        self.assertEqual(mdscan.map_closed(upper, "a <!-- b", (False, True)), "A <!-- b")
        self.assertEqual(mdscan.map_closed(upper, "x --> x <!-- x", (True, True)), "x --> X <!-- x")
        self.assertEqual(mdscan.map_closed(upper, "x --> x `y`", (True, False)), "x --> X `y`")
        self.assertEqual(mdscan.map_closed(upper, "plain <!-- c -->", (False, False)), "PLAIN <!-- c -->")
        self.assertEqual(mdscan.close_comments("x --> y <!-- z", (True, True)), "<!--x --> y <!-- z-->")


# --------------------------------------------------------------------------- the renderers themselves

# Every token zNN is code, hidden (in a comment) or text for mdBook and Pandoc alike; the cases
# where the two disagree (raw HTML blocks, unclosed fences) are left out.
AGREED = {
    "top-level indented": "z01 para\n\n    z02 code\n\n    z03 code\n\nz04 text\n",
    "paragraph continuation": "z01 text\n    z02 more text\n",
    "after heading": "# z01 T\n    z02 code\n",
    "after fence": "```\nz01\n```\n    z02 code\n",
    "list item code": "1. z01 运行：\n\n       z02 echo $HOME\n       z03 见[一](ch02.md)\n\nz04 正文\n",
    "list item para": "- z01 item\n\n    z02 para in item\n\nz03 out\n",
    "nested list code": "- z01 a\n  - z02 b\n\n        z03 code under b\n",
    "nested list para": "- z01 a\n\n  - z02 b\n\n    z03 para in b\n",
    "four after marker": "-    z01 four after\n\n         z02 code\n",
    "code on marker line": "-     z01 code on marker line\n",
    "ordered ten": "10. z01 ten\n\n        z02 code\n",
    "lazy continuation": "- z01 c\nz02 lazy c\n\n      z03 code under c\n",
    "definition": "z01 Term\n\n:   z02 def\n\n    z03 second para\n\n        z04 code in def\n",
    "definition short": "z01 Term2\n\n: z02 short\n\n  z03 second2\n\n      z04 code2\n\nz05 after\n",
    "definition no blank": "z01 Term3\n:   z02 no blank def\n\n        z03 code under def\n",
    "footnote": "z00 Text[^n].\n\n[^n]: z01 note\n\n    z02 second note para\n\n        z03 code in note\n",
    "footnote ends": "z00 Text[^k].\n\n[^k]: z01 note k\n\n  z02 two-space para\n\n     z03 five-space code\n",
    "quote code": "> z01 quote\n>\n>     z02 code in quote\n",
    "quote item code": "> - z01 qi\n>\n>       z02 code in quote item\n",
    "item quote code": "- z01 li\n\n  > z02 q in li\n  >\n  >     z03 code in q in li\n",
    "quote lazy": "> z01 a\n    z02 lazy\n",
    "comment in indented code": "z01 示例：\n\n    <!-- z02 待补\n\nz03 之后。\n",
    "comment block": "z01 a\n\n<!--\nz02 hidden\n\nz03 hidden\n-->\nz04 after\n",
    "comment block in item": "- z01 a\n\n  <!-- z02\n  z03 -->\n\nz04 out\n",
    "comment indented 4 in paragraph": "z01 text\n    <!-- z02 四格续行\n    z03 中间\n    --> z04 visible\n",
    "inline comment over lines": "z01 正文 <!-- z02 TODO\nz03 ![图](fig5.svg) --> z04 可见\n",
    "inline comment in item": "- z01 项 <!-- z02 跨行\n  z03 续行 --> z04 可见\n",
    "inline comment items": "- z01 项 <!-- z02 不闭合\n- z03 新项 z04\n",
    "inline comment quote": "> z01 引 <!-- z02 跨行\n> z03 续 --> z04 可见\n",
    "inline comment three lines": "z01 a <!-- z02\nz03\nz04 --> z05 b <!-- z06 --> z07\n",
    "code span opener": "z01 `<!--` z02 不是注释\nz03 下一行 -->\n",
    "fence in nested item": "- z01 item\n\n  - z02 nested\n\n    ```\n    z03 code\n    ```\n\nz04 out\n",
    "indented fence in paragraph": "z01 text\n    ```\n    z02 still text\n    ```\n",
    "fence indented four": "z01 text\n\n    ```\n    z02 code\n    ```\n",
    "tab indented": "z01 a\n\n\tz02 code\n",
    "list after paragraph": "z01 para\n- z02 b\n\n      z03 code\n",
    "heading in item": "- z01 a\n\n  # z02 h\n      z03 code\n",
    "setext": "z01 a\n---\n    z02 code\n",
    "empty item": "-\n  z01 foo\n\n      z02 code\n",
}
TOKEN_RE = re.compile(r"z\d\d")


def ours(md: str) -> dict[str, str]:
    lines = md.split("\n")
    scan = mdscan.scan_blocks(lines)
    out = {}
    for line, kind, carry in zip(lines, scan.kinds, scan.carry):
        view = mdscan.close_comments(line, carry)
        shift = 4 if carry[0] else 0
        comments = [(a - shift, b - shift) for a, b in mdscan.code_spans(view, comments=True) if view[a] == "<"]
        for m in TOKEN_RE.finditer(line):
            if kind in (mdscan.FENCE, mdscan.CODE):
                out[m.group()] = "code"
            elif kind == mdscan.COMMENT or any(a <= m.start() < b for a, b in comments):
                out[m.group()] = "hidden"
            else:
                out[m.group()] = "text"
    return out


def pandoc_kinds(md: str) -> dict[str, str]:
    proc = subprocess.run([tp.pandoc_path(), "--from", tp.READER, "--to", "json"], input=md, capture_output=True,
                          text=True, check=True)
    out: dict[str, str] = {}

    def walk(x) -> None:
        if isinstance(x, list):
            for y in x:
                walk(y)
        elif isinstance(x, dict):
            kind, c = x.get("t"), x.get("c")
            if kind == "CodeBlock":
                out.update(dict.fromkeys(TOKEN_RE.findall(c[1]), "code"))
            elif kind in ("RawBlock", "RawInline"):
                out.update(dict.fromkeys(TOKEN_RE.findall(c[1]), "hidden"))
            elif kind in ("Str", "Code"):
                for tok in TOKEN_RE.findall(c if kind == "Str" else c[1]):
                    out.setdefault(tok, "text")
            elif c is not None:
                walk(c)

    walk(json.loads(proc.stdout)["blocks"])
    return out


def mdbook_kinds(html: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for m in re.finditer(r"<pre><code[^>]*>(.*?)</code></pre>", html, re.S):
        out.update(dict.fromkeys(TOKEN_RE.findall(m.group(1)), "code"))
    html = re.sub(r"<pre><code[^>]*>.*?</code></pre>", "", html, flags=re.S)
    for m in re.finditer(r"<!--(.*?)-->", html, re.S):
        out.update(dict.fromkeys(TOKEN_RE.findall(m.group(1)), "hidden"))
    for tok in TOKEN_RE.findall(re.sub(r"<!--.*?-->", "", html, flags=re.S)):
        out.setdefault(tok, "text")
    return out


class RenderersAgreeTest(unittest.TestCase):
    """The block model is the one mdBook and Pandoc apply (checked against both when installed)."""

    @unittest.skipUnless(have_pandoc(), "pandoc needed")
    def test_pandoc(self):
        for name, md in AGREED.items():
            with self.subTest(name):
                self.assertEqual(pandoc_kinds(md), ours(md))

    @unittest.skipUnless(MDBOOK and (shutil.which(MDBOOK) or os.path.exists(MDBOOK)), "mdBook needed")
    def test_mdbook(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "book.toml").write_text('[book]\ntitle = "t"\n\n[output.html]\n', encoding="utf-8")
            names = {f"c{k:02d}": name for k, name in enumerate(AGREED)}
            (root / "src" / "SUMMARY.md").write_text(
                "# Summary\n\n" + "".join(f"- [{c}]({c}.md)\n" for c in names), encoding="utf-8")
            for c, name in names.items():
                (root / "src" / f"{c}.md").write_text(AGREED[name], encoding="utf-8")
            subprocess.run([MDBOOK, "build"], cwd=root, capture_output=True, check=True)
            for c, name in names.items():
                page = (root / "book" / f"{c}.html").read_text(encoding="utf-8")
                main = page[page.index("<main>"):page.index("</main>")]
                with self.subTest(name):
                    self.assertEqual(mdbook_kinds(main), ours(AGREED[name]))


if __name__ == "__main__":
    unittest.main()
