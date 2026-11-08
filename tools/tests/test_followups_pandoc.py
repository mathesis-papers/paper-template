"""Fenced code is seen the same way by every scanner: mdscan, the Pandoc stager, the math scanner.

A fence may sit in a block quote or a list item, and a ``> ```…`` line shown inside a
top-level code example is content, not a closing fence (:func:`tbook.mdscan.fence_end`).
:mod:`tbook.render` (via ``mdscan.parse_blocks``), :func:`tbook.pandoc._code_mask` and
:func:`tbook.mathrender.find_math` must agree on that, or a link or formula inside a code
example is rewritten by one target and shown as written by another.

The PDF/EPUB stager also agrees with mdBook on headings: ids follow mdBook's (formulas as
KaTeX shows them, footnote references as their numbers, ``{-}`` and other attribute forms), a
heading right under a paragraph line is a heading, and indented code blocks stay as written.

Run: PYTHONPATH=tools .venv/bin/python -m unittest discover -s tools/tests -p 'test_followups_pandoc.py'
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tbook import config, mathrender, mdscan, paths
from tbook import pandoc as tp
from tbook.model import load_edition
from test_pandoc import HAVE_KATEX, fixture_site, have_pandoc

MDBOOK = os.environ.get("MDBOOK") or shutil.which("mdbook")

# A Markdown tutorial shows a quoted code block inside a top-level code example.
QUOTED_FENCE_IN_EXAMPLE = """\
Before $a$ here.

```markdown
> ```
> $x$ inside the example
> ```
$y$ still inside the example
```

After $b$ here.
"""

SAMPLES = {
    "quoted fence in an example": QUOTED_FENCE_IN_EXAMPLE,
    "fence in a block quote": "> ```\n> $x$\n> ```\n\n$b$\n",
    "fence in a nested list item": "- item\n\n  - nested\n\n    ```\n    $x$\n    ```\n\n$b$\n",
    "unclosed quoted fence ends with the quote": "> ```\n> $x$\n\n$b$\n",
    "longer closing fence": "````\n```\n$x$\n```\n`````\n$b$\n",
    "tilde fence with backticks inside": "~~~\n```\n$x$\n~~~\n$b$\n",
}


def math_hidden_lines(text: str) -> list[bool]:
    """Lines the math scanner masks completely (every character, or an empty line)."""
    mask, _ = mathrender._mask(text)
    out, offset = [], 0
    for line in text.split("\n"):
        out.append(all(mask[offset:offset + len(line)]))
        offset += len(line) + 1
    return out


class MathInCodeExampleTest(unittest.TestCase):
    def test_quoted_fence_line_does_not_close_the_example(self):
        spans, notes = mathrender.find_math(QUOTED_FENCE_IN_EXAMPLE)
        self.assertEqual([s.tex for s in spans], ["a", "b"])
        self.assertEqual(notes, [])

    def test_example_is_spliced_unchanged(self):
        spans, _ = mathrender.find_math(QUOTED_FENCE_IN_EXAMPLE)
        out = mathrender.splice(QUOTED_FENCE_IN_EXAMPLE, spans, ["<A>", "<B>"])
        self.assertIn("```markdown\n> ```\n> $x$ inside the example\n> ```\n$y$ still inside the example\n```", out)
        self.assertIn("Before <A> here.", out)
        self.assertIn("After <B> here.", out)

    def test_math_in_container_fences_is_not_math(self):
        for name, text in SAMPLES.items():
            with self.subTest(name):
                self.assertEqual([s.tex for s in mathrender.find_math(text)[0]],
                                 ["a", "b"] if "$a$" in text else ["b"])


class ScannersAgreeTest(unittest.TestCase):
    def test_same_fenced_lines(self):
        for name, text in SAMPLES.items():
            lines = text.split("\n")
            fenced = mdscan.fenced_code_lines(lines)
            with self.subTest(name):
                self.assertTrue(any(fenced))
                self.assertEqual(tp._code_mask(lines), fenced)
                hidden = math_hidden_lines(text)
                # Every fenced line is masked for math; blank lines outside code may be too.
                self.assertEqual([h for h, f, line in zip(hidden, fenced, lines) if line.strip()],
                                 [f for f, line in zip(fenced, lines) if line.strip()])

    def test_parse_blocks_sees_the_same_code(self):
        for name, text in SAMPLES.items():
            lines = text.split("\n")
            fenced = mdscan.fenced_code_lines(lines)
            code = [line for node in mdscan.parse_blocks(text) if isinstance(node, mdscan.Code) for line in node.lines]
            with self.subTest(name):
                self.assertEqual(code, [line for line, f in zip(lines, fenced) if f])


# --------------------------------------------------------------------------- re-review follow-ups

BOOK_TOML = """\
[book]
version = "1.0.0"
authors = ["A. Author"]
license = "CC-BY-4.0"
editions = ["zh"]
code = "TEST//IDS"
date = "2026-01-02"

[book.title]
zh = "测试"
"""


def write_book(root: Path, chapters: dict[str, str], slug: str = "ids-book") -> config.Edition:
    """A zh book whose chapters are ``chapters`` (file → Markdown, in SUMMARY order)."""
    bdir = root / slug
    (bdir / "zh").mkdir(parents=True, exist_ok=True)
    (bdir / "book.toml").write_text(BOOK_TOML, encoding="utf-8")
    summary = "# Summary\n\n" + "".join(f"- [{name}]({name})\n" for name in chapters)
    (bdir / "zh" / "SUMMARY.md").write_text(summary, encoding="utf-8")
    for name, md in chapters.items():
        (bdir / "zh" / name).write_text(md, encoding="utf-8")
    return config.load_book(bdir).edition("zh")


def stage_chapters(root: Path, chapters: dict[str, str]) -> tp.Stage:
    """Stage (PDF/EPUB) a zh book whose chapters are ``chapters``."""
    ed = write_book(root, chapters)
    model = load_edition(ed)
    assert not model.issues, [i.format() for i in model.issues]
    return tp.stage(fixture_site(), ed.book, ed, model, None, out_dir=root / "stage")


def heading_ids(md: str) -> list[str]:
    """The ids of the headings of book.md, in order."""
    out = []
    for line in md.split("\n"):
        h = tp.parse_heading(line)
        if h and h[2] and h[2].id:
            out.append(h[2].id)
    return out


def pandoc_stderr(staged: tp.Stage, fmt: str = "typst") -> str:
    """Pandoc's warnings when book.md goes through the book filters (as for the PDF/EPUB)."""
    proc = subprocess.run([tp.pandoc_path(), "book.md", "-f", tp.READER, "-t", fmt, "-o", os.devnull,
                           *tp._filter_meta("zh"), *tp._filters()],
                          cwd=staged.dir, capture_output=True, text=True, check=True)
    return proc.stderr


class UnnumberedHeadingIdsTest(unittest.TestCase):
    """Headings with ``{-}`` (Pandoc's ``.unnumbered``) and other attribute forms get the same
    book-wide id as every other heading, so no id is used twice (Typst rejects a repeated
    label and the EPUB table of contents would point to the wrong chapter)."""

    def test_pandoc_attribute_forms(self):
        cases = {
            "## 小结 {-}": ("小结", "", ["unnumbered"], {}),
            "## 小结 {.unnumbered}": ("小结", "", ["unnumbered"], {}),
            "## 丙 {- #c1}": ("丙", "c1", ["unnumbered"], {}),
            "## 丁 {.x -}": ("丁", "", ["x", "unnumbered"], {}),
            # Pandoc and mdBook both keep the last of several ids.
            "## 乙 {#a1 #b1}": ("乙", "b1", [], {}),
            # A "-" inside a quoted value is text.
            '## 戊 {k="a - b" -}': ("戊", "", ["unnumbered"], {"k": "a - b"}),
        }
        for line, want in cases.items():
            with self.subTest(line):
                _, text, attrs = tp.parse_heading(line)
                self.assertEqual((text, attrs.id, attrs.classes, attrs.kv), want)
        # Not an attribute block for Pandoc: the braces stay in the text.
        self.assertEqual(tp.parse_heading("## 甲 {weird stuff}"), (2, "甲 {weird stuff}", None))

    def test_unnumbered_headings_get_book_wide_ids(self):
        chapters = [("ch01.md", "# 甲\n\n## 小结 {-}\n\n## 小结 {-}\n\n## 结语 {weird stuff}\n"),
                    ("ch02.md", "# 乙\n\n## 小结\n\n## 小结 {.unnumbered}\n\n## 结语\n")]
        taken = {"ch-ch01", "ch-ch02"}
        ids = tp.assign_heading_ids(chapters, {"ch01.md": "ch-ch01", "ch02.md": "ch-ch02"}, taken)
        self.assertEqual(list(ids.by_line["ch01.md"].values()), ["小结", "小结-1", "结语"])
        self.assertEqual(list(ids.by_line["ch02.md"].values()),
                         ["ch-ch02--小结", "ch-ch02--小结-1", "ch-ch02--结语"])
        # mdBook drops a trailing {…} from the text (and the id); Pandoc shows it.
        self.assertEqual(ids.anchors["ch01.md"]["结语"], "结语")
        self.assertEqual(ids.anchors["ch01.md"]["结语-weird-stuff"], "结语")
        self.assertEqual(ids.anchors["ch02.md"]["小结"], "ch-ch02--小结")

    def test_staged_book_has_unique_ids_and_links_reach_their_chapter(self):
        with tempfile.TemporaryDirectory() as tmp:
            staged = stage_chapters(Path(tmp), {
                "ch01.md": "# 甲\n\n## 小结 {-}\n\n正文。\n\n## 结语 {weird stuff}\n",
                "ch02.md": "# 乙\n\n## 小结\n\n见[乙的小结](ch02.md#小结)、[甲的小结](ch01.md#小结)与[本章小结](#小结)。\n",
            })
            md = staged.book_md.read_text(encoding="utf-8")
            ids = heading_ids(md)
            self.assertEqual(len(ids), len(set(ids)), ids)
            self.assertIn("## 小结 {#小结 .unnumbered}", md)
            self.assertIn("## 小结 {#ch-ch02--小结}", md)
            self.assertIn("## 结语 {weird stuff} {#结语}", md)
            self.assertIn("见[乙的小结](#ch-ch02--小结)、[甲的小结](#小结)与[本章小结](#ch-ch02--小结)。", md)
            if have_pandoc():
                err = pandoc_stderr(staged)
                self.assertNotIn("Duplicate identifier", err)
                self.assertNotIn("dangling", err)


# Indented code blocks: outside lists and footnotes, a run of lines indented by 4+ columns
# after a blank line is code (CommonMark, Pandoc); inside them it continues the item.
INDENTED = """\
# 甲

正文[^1]，见[乙](ch02.md)，公式 $a$。

    正文[^1]。
    [^1]: 代码里的脚注

    见[乙](ch02.md)，$x$ 不是公式。

- 列表项

    列表项的续行[^1]，见[乙](ch02.md)，$b$。

[^1]: 真脚注

    脚注的第二段，见[乙](ch02.md)。

结束 $c$。
"""
INDENTED_CODE = ["    正文[^1]。", "    [^1]: 代码里的脚注", "", "    见[乙](ch02.md)，$x$ 不是公式。"]


class IndentedCodeTest(unittest.TestCase):
    def code_lines(self, mask: list[bool]) -> list[str]:
        return [line for line, hidden in zip(INDENTED.split("\n"), mask) if hidden]

    def test_scanners_agree(self):
        lines = INDENTED.split("\n")
        self.assertEqual(self.code_lines(mdscan.indented_code_lines(lines)), INDENTED_CODE)
        self.assertEqual(self.code_lines(tp._code_mask(lines)), INDENTED_CODE)
        self.assertEqual([line for line, h in zip(lines, math_hidden_lines(INDENTED)) if h and line.strip()],
                         [line for line in INDENTED_CODE if line.strip()])

    def test_other_indentation_is_not_code(self):
        cases = {
            "lazy continuation of a list item": "- item\nlazy\n\n    continued\n",
            "nested list content": "- item\n\n  para\n\n    still the item\n",
            "paragraph continuation": "text\n    more text\n",
            "footnote paragraph": "[^1]: note\n\n    second paragraph\n",
        }
        for name, text in cases.items():
            with self.subTest(name):
                self.assertFalse(any(mdscan.indented_code_lines(text.split("\n"))))
        after_heading = "# T\n    code\n\ntext\n"
        self.assertEqual(mdscan.indented_code_lines(after_heading.split("\n")), [False, True, False, False, False])
        after_fence = "```\nx\n```\n    code\n"
        self.assertEqual(mdscan.indented_code_lines(after_fence.split("\n")),
                         [False, False, False, True, False])

    def test_footnotes_in_indented_code_are_not_scoped(self):
        out = tp.scope_footnotes(INDENTED, "ch-ch01")
        self.assertIn("\n    正文[^1]。\n    [^1]: 代码里的脚注\n", out)
        self.assertIn("正文[^ch-ch01--1]，", out)
        self.assertIn("列表项的续行[^ch-ch01--1]，", out)
        self.assertIn("[^ch-ch01--1]: 真脚注", out)

    def test_links_in_indented_code_are_not_rewritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            staged = stage_chapters(Path(tmp), {"ch01.md": INDENTED, "ch02.md": "# 乙\n"})
            md = staged.book_md.read_text(encoding="utf-8")
        self.assertIn("\n    正文[^1]。\n    [^1]: 代码里的脚注\n\n    见[乙](ch02.md)，$x$ 不是公式。\n", md)
        self.assertIn("正文[^ch-ch01--1]，见[乙](#ch-ch02)，", md)
        self.assertIn("列表项的续行[^ch-ch01--1]，见[乙](#ch-ch02)，", md)
        self.assertIn("脚注的第二段，见[乙](#ch-ch02)。", md)

    def test_math_in_indented_code_is_not_math(self):
        self.assertEqual([s.tex for s in mathrender.find_math(INDENTED)[0]], ["a", "b", "c"])


class HeadingAfterParagraphTest(unittest.TestCase):
    """mdBook reads ``## H`` right under a paragraph line as a heading; Pandoc (with
    ``blank_before_header``) only after a blank line, so one is inserted."""

    MD = "# 甲\n\n段落文字\n## 紧贴标题\n\n正文。\n\n- 列表项\n## 列表后\n"

    def test_blank_line_inserted(self):
        out = tp.restructure_chapter(self.MD, chapter_path="ch01.md", depth=0, chapter_id="ch-ch01", title="甲",
                                     classes=["tr-chapter"], kv={}, linker=None,
                                     heading_ids={3: "紧贴标题", 8: "列表后"})
        self.assertIn("段落文字\n\n## 紧贴标题 {#紧贴标题}\n\n正文。", out)
        self.assertIn("- 列表项\n\n## 列表后 {#列表后}\n", out)
        self.assertTrue(out.startswith("# 甲 {#ch-ch01 .tr-chapter}\n\n段落文字"), out)

    @unittest.skipUnless(have_pandoc(), "pandoc not available")
    def test_pandoc_reads_a_heading(self):
        with tempfile.TemporaryDirectory() as tmp:
            staged = stage_chapters(Path(tmp), {"ch01.md": self.MD})
            html = subprocess.run([tp.pandoc_path(), "book.md", "-f", tp.READER, "-t", "html5"], cwd=staged.dir,
                                  capture_output=True, text=True, check=True).stdout
        self.assertIn('<h2 id="紧贴标题">紧贴标题</h2>', html)
        self.assertIn('<h2 id="列表后">列表后</h2>', html)
        self.assertIn("<p>段落文字</p>", html)
        self.assertNotIn("{#", html)


class MathHeadingSlugTest(unittest.TestCase):
    """mdBook makes a heading's id from the text of the rendered heading, so a formula counts
    as the text KaTeX shows (``$\\beta$`` → ``β``); PDF/EPUB ids and fragments follow it."""

    KATEX = {"\\varphi": "φ", "\\beta": "β", "[0, 1]": "[0,1]", "x^2": "x2"}

    def fake_render(self, items: list[tuple[str, bool]]) -> list[str]:
        return [self.KATEX[tex] for tex, _ in items]

    def test_heading_slugs_use_the_text_katex_shows(self):
        shown = {(tex, False): text for tex, text in self.KATEX.items()}
        self.assertEqual(tp.heading_slugs("黄金比 $\\varphi$ 的性质", shown), ["黄金比-φ-的性质", "黄金比-varphi-的性质"])
        self.assertEqual(tp.heading_slugs("区间 $[0, 1]$ 与 $x^2$", shown)[0], "区间-01-与-x2")
        self.assertEqual(tp.heading_slugs("黄金比 $\\varphi$ 的性质"), ["黄金比-varphi-的性质"])

    def test_ids_and_anchors_follow_mdbook(self):
        chapters = [("ch01.md", "# 甲\n\n## 关于 $\\beta$ 的估计\n\n## 关于 beta 的估计\n"),
                    ("ch02.md", "# 乙\n\n## 关于 $\\beta$ 的估计\n")]
        ids = tp.assign_heading_ids(chapters, {"ch01.md": "ch-ch01", "ch02.md": "ch-ch02"}, {"ch-ch01", "ch-ch02"},
                                    render_math=self.fake_render)
        self.assertEqual(list(ids.by_line["ch01.md"].values()), ["关于-β-的估计", "关于-beta-的估计"])
        self.assertEqual(list(ids.by_line["ch02.md"].values()), ["ch-ch02--关于-β-的估计"])
        # The mdBook id of each heading reaches it; the TeX slug of the first is only Pandoc's.
        self.assertEqual(ids.anchors["ch01.md"]["关于-β-的估计"], "关于-β-的估计")
        self.assertEqual(ids.anchors["ch01.md"]["关于-beta-的估计"], "关于-beta-的估计")
        self.assertEqual(ids.anchors["ch02.md"]["关于-β-的估计"], "ch-ch02--关于-β-的估计")

    def test_without_katex_the_tex_slug_stays(self):
        ids = tp.assign_heading_ids([("ch01.md", "# 甲\n\n## 关于 $\\beta$ 的估计\n")], {"ch01.md": "ch-ch01"},
                                    {"ch-ch01"}, render_math=lambda items: None)
        self.assertEqual(list(ids.by_line["ch01.md"].values()), ["关于-beta-的估计"])

    @unittest.skipUnless(HAVE_KATEX, "node and the katex package are required")
    def test_formula_texts(self):
        items = [("\\varphi", False), ("[0, 1]", False), ("x^2", False), ("\\operatorname{Tr}(A)", False),
                 ("\\norm{x}", False), ("\\frac{", False)]
        self.assertEqual(mathrender.formula_texts(items), ["φ", "[0,1]", "x2", "Tr(A)", "∥x∥", "\\frac{"])

    @unittest.skipUnless(HAVE_KATEX, "node and the katex package are required")
    def test_link_from_another_chapter_resolves(self):
        with tempfile.TemporaryDirectory() as tmp:
            staged = stage_chapters(Path(tmp), {
                "ch01.md": "# 甲\n\n## 关于 $\\beta$ 的估计\n\n正文。\n",
                "ch02.md": "# 乙\n\n见[估计](ch01.md#关于-β-的估计)与[同一处](ch01.md#%E5%85%B3%E4%BA%8E-%CE%B2-%E7%9A%84%E4%BC%B0%E8%AE%A1)。\n",
            })
            md = staged.book_md.read_text(encoding="utf-8")
            self.assertIn("## 关于 $\\beta$ 的估计 {#关于-β-的估计}", md)
            self.assertIn("见[估计](#关于-β-的估计)与[同一处](#关于-β-的估计)。", md)
            if have_pandoc():
                self.assertNotIn("dangling", pandoc_stderr(staged))


# Recorded with mdBook 0.5.4: each chapter's heading ids, in order. mdBook shows a reference to
# a footnote defined in the chapter as its number, and the number is part of the id. Numbers
# follow the first reference to each label as written, in source order (body, headings and
# footnote definitions alike); two references side by side get a space between them; a
# reference without a definition, in code, in a comment or escaped is text.
FOOTNOTE_HEADINGS = [
    ("first reference", "# 甲\n\n正文。\n\n## 注释[^a]\n\n内容。\n\n[^a]: 脚注。\n", ["甲", "注释1"]),
    ("second reference", "# 甲\n\n正文[^x]。\n\n## 注释[^y]\n\n内容。\n\n[^x]: X。\n[^y]: Y。\n", ["甲", "注释2"]),
    ("repeated reference", "# 甲\n\n## 注释[^a]\n\n## 再注[^a]\n\n[^a]: A。\n", ["甲", "注释1", "再注1"]),
    ("referenced in the body first", "# 甲\n\n正文[^a]与[^b]。\n\n## 注释[^b]\n\n[^a]: A。\n[^b]: B。\n",
     ["甲", "注释2"]),
    ("two in one heading", "# 甲\n\n## 注释[^a][^b]\n\n## 又[^b] 与 [^c]\n\n[^a]: A。\n[^b]: B。\n[^c]: C。\n",
     ["甲", "注释1-2", "又2-与-3"]),
    ("side by side", "# 甲\n\n## Notes[^a][^b][^c] end\n\n## [^a][^c]注释\n\n## 注释[^a]  [^b]\n\n"
                     "## 注释[^a]x[^b]\n\n## 注[^a]释\n\n[^a]: A。\n[^b]: B。\n[^c]: C。\n",
     ["甲", "notes1-2-3-end", "1-3注释", "注释1--2", "注释1x2", "注1释"]),
    ("word label", "# 甲\n\n## Notes[^note]\n\n[^note]: N.\n", ["甲", "notes1"]),
    ("numbers are not labels", "# 甲\n\n正文[^2]。\n\n## 注释[^1]\n\n[^1]: one\n[^2]: two\n", ["甲", "注释2"]),
    ("only a footnote", "# 甲\n\n## [^a]\n\n[^a]: A。\n", ["甲", "1"]),
    ("in the title", "# 甲[^a]\n\n## 注释[^a]\n\n[^a]: A。\n", ["甲1", "注释1"]),
    ("nested inline markup", "# 甲\n\n## *强调[^a]* 与 **粗[^b]**\n\n## *x[^a][^b]*[^c] _y_[^d]\n\n"
                             "## <span>注[^c]</span> `码[^d]`\n\n[^a]: A。\n[^b]: B。\n[^c]: C。\n[^d]: D。\n",
     ["甲", "强调1-与-粗2", "x1-23-y4", "注3-码d"]),
    ("definitions first", "# 甲\n\n[^b]: B。\n\n[^a]: A。\n\n## 注释[^a]\n\n正文[^b]。\n", ["甲", "注释1"]),
    ("references in definitions count where they are written",
     "# 甲\n\n[^z]: Z 见[^c]。\n\n## 一[^a]\n\n[^a]: A 见[^b]。\n\n    续行[^d]。\n\n## 二[^e]\n\n"
     "[^b]: B。\n[^c]: C。\n[^d]: D。\n[^e]: E。\n", ["甲", "一2", "二5"]),
    ("code, comments and escapes are not references",
     "# 甲\n\n`正文[^x]` <!-- [^y] -->\n\n```\n[^z]\n```\n\n## 注释[^a] `码[^x]`\n\n## 转义\\[^x] 与 \\\\[^y]\n\n"
     "[^a]: A。\n[^x]: X。\n[^y]: Y。\n[^z]: Z。\n", ["甲", "注释1-码x", "转义x-与-2"]),
    ("no definition", "# 甲\n\n## 注释[^nope]\n\n## 注释[^a][^nope] 与 [^nope][^a]\n\n```\n[^b]: 代码里的定义\n```\n\n"
                      "## 注释[^b]\n\n[^a]: A。\n", ["甲", "注释nope", "注释1nope-与-nope1", "注释b"]),
    ("label case", "# 甲\n\n正文[^a]。\n\n## 注释[^A]\n\n## 再注[^a]\n\n[^a]: A。\n", ["甲", "注释2", "再注1"]),
    ("attributes and setext", "# 甲\n\n## 注释[^a] {.unnumbered}\n\n注释[^b]\n-------\n\n[^a]: A。\n[^b]: B。\n",
     ["甲", "注释1", "注释2"]),
    ("de-duplication", "# 甲\n\n## 注释[^a]\n\n## 注释1\n\n[^a]: A。\n", ["甲", "注释1", "注释1-1"]),
    ("lists, quotes and tables", "# 甲\n\n- 项[^a]\n\n> 引[^b]\n\n| t |\n|---|\n| 表[^c] |\n\n## 注释[^d]\n\n"
                                 "[^a]: A。\n[^b]: B。\n[^c]: C。\n[^d]: D。\n", ["甲", "注释4"]),
]


def footnote_case(name: str) -> str:
    return next(md for n, md, _ in FOOTNOTE_HEADINGS if n == name)


class FootnoteHeadingIdsTest(unittest.TestCase):
    """A footnote reference in a heading is part of mdBook's id as its number in the chapter
    (``## 注释[^a]`` → ``注释1``), so a fragment copied from the HTML page reaches the heading
    in the PDF/EPUB too; Pandoc's own slug keeps the label (``注释a``) and stays a fallback."""

    def test_ids_and_fragments_follow_mdbook(self):
        for name, md, want in FOOTNOTE_HEADINGS:
            with self.subTest(name):
                ids = tp.assign_heading_ids([("ch01.md", md)], {"ch01.md": "ch-ch01"}, {"ch-ch01"})
                self.assertEqual(list(ids.by_line["ch01.md"].values()), want[1:])
                self.assertEqual([ids.anchors["ch01.md"].get(frag) for frag in want], ["ch-ch01", *want[1:]])

    def test_pandoc_slug_keeps_the_label(self):
        ids = tp.assign_heading_ids([("ch01.md", footnote_case("two in one heading"))], {"ch01.md": "ch-ch01"},
                                    {"ch-ch01"})
        self.assertEqual(ids.anchors["ch01.md"]["注释ab"], "注释1-2")
        self.assertEqual(ids.anchors["ch01.md"]["又b-与-c"], "又2-与-3")

    def test_footnote_numbers(self):
        self.assertEqual(tp.footnote_numbers(footnote_case("references in definitions count where they are written")),
                         {"c": 1, "a": 2, "b": 3, "d": 4, "e": 5})
        self.assertEqual(tp.footnote_numbers(footnote_case("label case")), {"a": 1, "A": 2})
        self.assertEqual(tp.footnote_numbers("# 甲\n\n正文[^nope]。\n"), {})

    def test_heading_slugs(self):
        self.assertEqual(tp.heading_slugs("注释[^a][^b]", notes={"a": 1, "b": 2}), ["注释1-2", "注释ab"])
        self.assertEqual(tp.heading_slugs("_x_[^a]", notes={"a": 3}), ["x3", "xa"])
        # Without the chapter's footnotes every reference is text, as for an undefined one.
        self.assertEqual(tp.heading_slugs("注释[^a]"), ["注释a"])
        # mdBook keeps every space; Pandoc reads a run of spaces or tabs as one.
        self.assertEqual(tp.heading_slugs("a  b \t c  d"), ["a--b---c--d", "a-b-c--d"])

    @unittest.skipUnless(have_pandoc(), "pandoc is required")
    def test_fallback_is_pandocs_own_slug(self):
        for name, md, _ in FOOTNOTE_HEADINGS:
            with self.subTest(name):
                out = subprocess.run([tp.pandoc_path(), "-f", tp.READER, "-t", "html"], input=md,
                                     capture_output=True, text=True, check=True).stdout
                used: set[str] = set()
                slugs = [tp._unique(tp._slug_pair(h.text, h.text, None)[1], used)
                         for h in tp.find_headings(tp.normalize_setext(md))]
                self.assertEqual(slugs, re.findall(r'<h[1-6][^>]* id="([^"]+)"', out))

    def test_link_from_another_chapter_resolves(self):
        with tempfile.TemporaryDirectory() as tmp:
            staged = stage_chapters(Path(tmp), {
                "ch01.md": "# 第一章 甲\n\n见[注](ch02.md#注释1)与[又](ch02.md#注释2-3)。\n",
                "ch02.md": "# 第二章 乙\n\n正文。\n\n## 注释[^a]\n\n内容[^b]。\n\n## 注释[^b][^c]\n\n"
                           "[^a]: 脚注。\n[^b]: 又一个。\n[^c]: 第三个。\n",
            })
            md = staged.book_md.read_text(encoding="utf-8")
            self.assertIn("## 注释[^ch-ch02--a] {#注释1}", md)
            self.assertIn("## 注释[^ch-ch02--b][^ch-ch02--c] {#注释2-3}", md)
            self.assertIn("见[注](#注释1)与[又](#注释2-3)。", md)
            if have_pandoc():
                self.assertNotIn("dangling", pandoc_stderr(staged))

    @unittest.skipUnless(MDBOOK, "mdBook is required")
    def test_table_is_what_mdbook_does(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "book.toml").write_text('[book]\ntitle = "t"\n\n[output.html.search]\nenable = false\n',
                                            encoding="utf-8")
            files = [f"c{k:02d}.md" for k in range(len(FOOTNOTE_HEADINGS))]
            (root / "src" / "SUMMARY.md").write_text(
                "# Summary\n\n" + "".join(f"- [{f}]({f})\n" for f in files), encoding="utf-8")
            for f, (_, md, _) in zip(files, FOOTNOTE_HEADINGS):
                (root / "src" / f).write_text(md, encoding="utf-8")
            subprocess.run([MDBOOK, "build", str(root)], check=True, capture_output=True)
            for f, (name, _, want) in zip(files, FOOTNOTE_HEADINGS):
                page = (root / "book" / f.replace(".md", ".html")).read_text(encoding="utf-8")
                main = page[page.index("<main>"):page.index("</main>")]
                self.assertEqual(re.findall(r'<h[1-6][^>]* id="([^"]+)"', main), want, name)


@unittest.skipUnless(HAVE_KATEX and MDBOOK and have_pandoc(), "node, katex, mdBook and pandoc are required")
class FragmentsMatchMdbookTest(unittest.TestCase):
    """Every heading id of the HTML edition, linked from another chapter, reaches the same
    heading in the PDF/EPUB (``{-}``, unparsable tails, math, headings under a paragraph,
    footnote references)."""

    SLUG = "tbook-test-fragments"
    CHAPTERS = {
        "ch01.md": ("# 甲\n\n## 小结 {-}\n\n段落文字\n## 紧贴标题\n\n## 关于 $\\beta$ 的估计\n\n"
                    "## 区间 $[0, 1]$ 与 $x^2$ 和 $\\operatorname{Tr}(A)$\n\n## 结语 {weird stuff}\n\n## 小结\n"),
        "ch02.md": ("# 乙\n\n## 小结\n\n## 关于 $\\beta$ 的估计\n\n## 关于 beta 的估计\n\n## 丁 {.x -}\n\n"
                    "正文[^x]。\n\n## 注释[^a][^b] {-}\n\n## 关于 $x$[^note] 与 `码[^a]`\n\n## 未定义[^nope]\n\n"
                    "[^a]: 甲。\n[^b]: 乙。\n[^x]: 丙。\n[^note]: 丁。\n"),
        "ch03.md": "# 丙\n",
    }

    def tearDown(self):
        shutil.rmtree(paths.BUILD / "stage" / self.SLUG, ignore_errors=True)

    def test_html_ids_resolve_in_the_pdf(self):
        from tbook import html

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ed = write_book(root, self.CHAPTERS, self.SLUG)
            html.build_edition(fixture_site(), ed.book, ed, None, None, root / "html")
            html_ids = {name: re.findall(r'<h[1-6][^>]* id="([^"]+)"', (root / "html" / name.replace(".md", ".html"))
                                         .read_text(encoding="utf-8"))
                        for name in ("ch01.md", "ch02.md")}
            self.assertIn("关于-β-的估计", html_ids["ch01.md"])  # KaTeX's text, as mdBook sees it
            self.assertIn("注释2-3", html_ids["ch02.md"])  # footnote numbers, as mdBook shows them
            links = [f"[{name} {k}]({name}#{frag})" for name, frags in html_ids.items() for k, frag in enumerate(frags)]
            staged = stage_chapters(root / "pdf", {**self.CHAPTERS, "ch03.md": "# 丙\n\n" + "\n".join(links) + "\n"})
            md = staged.book_md.read_text(encoding="utf-8")
            # Heading ids of book.md per chapter, in order (a chapter starts at its .tr-chapter title).
            pdf_ids: dict[str, list[str]] = {}
            chapter = ""
            for line in md.split("\n"):
                h = tp.parse_heading(line)
                if h and h[2] and h[2].id:
                    if "tr-chapter" in h[2].classes:
                        chapter = next((c.path for c in staged.chapters if c.id == h[2].id), "")
                    pdf_ids.setdefault(chapter, []).append(h[2].id)
            all_ids = [i for ids in pdf_ids.values() for i in ids]
            self.assertEqual(len(all_ids), len(set(all_ids)), all_ids)
            for name, frags in html_ids.items():
                self.assertEqual(len(frags), len(pdf_ids[name]), (frags, pdf_ids[name]))
                for k, frag in enumerate(frags):
                    self.assertIn(f"[{name} {k}](#{pdf_ids[name][k]})", md, frag)
            err = pandoc_stderr(staged)
            self.assertNotIn("dangling", err)
            self.assertNotIn("Duplicate identifier", err)


if __name__ == "__main__":
    unittest.main()
