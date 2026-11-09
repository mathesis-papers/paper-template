"""Fenced code is seen the same way by every scanner: mdscan, the Pandoc stager, the math scanner.

A fence may sit in a block quote or a list item, and a ``> ```…`` line shown inside a
top-level code example is content, not a closing fence (:func:`tbook.mdscan.scan_blocks`).
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
import time
import unittest
import zipfile
from pathlib import Path

from tbook import config, mathrender, mdscan, paths
from tbook import pandoc as tp
from tbook.model import load_edition
from test_pandoc import HAVE_KATEX, fixture_site, have_pandoc, have_typst

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


# Indented code blocks: a run of lines indented by 4+ columns past their container's content after
# a blank line is code (CommonMark, Pandoc); indented less, inside a list item or footnote, it
# continues the item (more cases: test_blocks).
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
    # What mdBook does not read as a reference: raw HTML (blocks, tags, a line that starts with a
    # comment), autolinks, link destinations and titles, "[^b](…)" and "[^b][x]" (links, or text
    # when x is no link reference), and code in a list item.
    ("raw HTML is not read",
     "# 甲\n\n<div class=\"aside\">另见[^b]</div>\n\n<pre>\n[^b]\n</pre>\n\n<custom-el>\n[^b]\n</custom-el>\n\n"
     "<span title=\"[^b]\">悬停</span> <https://e.com/[^b]> [x](y.md \"[^b]\")\n\n<!-- c --> 又[^b]\n\n"
     "> <div>[^b]</div>\n\n## 注释[^a]\n\n[^a]: A。\n[^b]: B。\n", ["甲", "注释1"]),
    ("link forms are not references", "# 甲\n\n某定理[^b](1972)、[^b](<a b>)、[^b]((1)) 与 [^b][x]、[^b][y]、[^b]\\[x]。\n\n"
                                      "[x]: https://e.com\n\n## 注释[^a]\n\n[^a]: A。\n[^b]: B。\n", ["甲", "注释1"]),
    ("indented code in a list item", "# 甲\n\n- 项\n\n      深缩进[^b]\n\n## 注释[^a]\n\n[^a]: A。\n[^b]: B。\n",
     ["甲", "注释1"]),
    ("what is read", "# 甲\n\n某[^b] (1972)、[^c][]、<code>[^d]</code>、[^e](a b)、[^g]\\(1972)。\n\n"
                     "正文\n<custom-el>[^f]</custom-el>\n\n## 注释[^a]\n\n"
                     "[^a]: A。\n[^b]: B。\n[^c]: C。\n[^d]: D。\n[^e]: E。\n[^f]: F。\n[^g]: G。\n", ["甲", "注释7"]),
    ("definitions in block quotes and list items", "# 甲\n\n> [^b]: 引用中的定义。\n\n- [^c]: 列表中的定义。\n\n"
                                                   "正文[^b]与[^c]。\n\n## 注释[^a]\n\n[^a]: A。\n", ["甲", "注释3"]),
    ("a definition right under a paragraph line", "# 甲\n\n正文[^b]\n[^b]: B。\n\n## 注释[^a]\n\n[^a]: A。\n",
     ["甲", "注释2"]),
    ("an indented line under a paragraph line is no definition",
     "# 甲\n\n正文[^b]。\n    [^b]: 不是定义\n\n## 注释[^a]\n\n[^a]: A。\n", ["甲", "注释1"]),
    # An HTML block has no lazy lines: it ends with the block quote or list item it is in, and
    # the text after it is read (also after an unclosed <pre>); inside the container it goes on.
    ("an HTML block ends with its block quote",
     "# 甲\n\n> <div class=\"tip\">\n> 提示。\n> </div>\n正文[^b]。\n\n> > <div>\n> > x\n> 又[^c]。\n\n"
     "## 注释[^a]\n\n[^a]: A。\n[^b]: B。\n[^c]: C。\n", ["甲", "注释3"]),
    ("an HTML block ends with its list item",
     "# 甲\n\n- 第一项\n- <div>第二项</div>\n后文[^b]。\n\n> - <div>x</div>\n> 又[^c]。\n\n1. 项\n2. <p>段</p>\n"
     "再[^d]。\n\n- <span>\n标签后[^e]\n\n## 注释[^a]\n\n[^a]: A。\n[^b]: B。\n[^c]: C。\n[^d]: D。\n[^e]: E。\n",
     ["甲", "注释5"]),
    ("an unclosed HTML block ends with its container",
     "# 甲\n\n> <pre>\n> 代码\n\n后文[^b]。\n\n- <pre>\n  x\n\n正文[^c]。\n\n## 注释[^a]\n\n[^a]: A。\n[^b]: B。\n[^c]: C。\n",
     ["甲", "注释3"]),
    ("an HTML block in a list item opened on an earlier line",
     "# 甲\n\n- 项\n\n  <div>\n  里面[^d]\n正文[^b]。\n\n## 注释[^a]\n\n[^a]: A。\n[^b]: B。\n[^d]: D。\n", ["甲", "注释2"]),
    ("an HTML block goes on in its container",
     "# 甲\n\n> <div>\n> [^b]\n> </div>\n\n> <pre>\n>\n> [^b]\n> </pre>\n\n- <pre>\n  x\n\n  [^b]\n  </pre>\n\n"
     "> <div>\n> > [^b]\n\n## 注释[^a]\n\n[^a]: A。\n[^b]: B。\n", ["甲", "注释1"]),
    # "[ ]" is no link label (a label has a character other than whitespace), "[^c]" no attribute
    # name, "#标签" no heading (so <b> under it is inline HTML in its paragraph); a setext
    # heading ends its paragraph, so a lone tag under it starts an HTML block.
    ("what only looks like a link label, a tag or a heading",
     "# 甲\n\n正文[^b][ ]、若 a <b and [^c] c> 则。\n\n#标签\n<b>\n正文[^d]。\n\n标题\n===\n<img src=\"x.png\">\n"
     "正文[^e]。\n\n## 注释[^a]\n\n[^a]: A。\n[^b]: B。\n[^c]: C。\n[^d]: D。\n[^e]: E。\n", ["甲", "标题", "注释4"]),
    # An HTML comment shows nothing, so it adds nothing to the id; two references with a comment
    # between them are not side by side.
    ("comments", "# 甲\n\n## 注释[^a]<!-- c -->[^b]\n\n## 小结 <!-- 待补 -->\n\n## 前 <!-- x --> 后\n\n"
                 "## 码 `<!-- c -->`\n\n[^a]: A。\n[^b]: B。\n", ["甲", "注释12", "小结", "前--后", "码----c---"]),
]
# mdBook reads "[^a](…)" in a heading as a link (text "^a"); Pandoc's own slug differs, so these
# are not part of test_fallback_is_pandocs_own_slug.
MDBOOK_ONLY_HEADINGS = [
    ("a reference followed by a destination is a link", "# 甲\n\n## 注释[^a](1972)\n\n## 又[^a]\n\n[^a]: A。\n",
     ["甲", "注释a", "又1"]),
]


def footnote_case(name: str) -> str:
    return next(md for n, md, _ in FOOTNOTE_HEADINGS if n == name)


class FootnoteHeadingIdsTest(unittest.TestCase):
    """A footnote reference in a heading is part of mdBook's id as its number in the chapter
    (``## 注释[^a]`` → ``注释1``), so a fragment copied from the HTML page reaches the heading
    in the PDF/EPUB too; Pandoc's own slug keeps the label (``注释a``) and stays a fallback."""

    def test_ids_and_fragments_follow_mdbook(self):
        for name, md, want in FOOTNOTE_HEADINGS + MDBOOK_ONLY_HEADINGS:
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
            table = FOOTNOTE_HEADINGS + MDBOOK_ONLY_HEADINGS
            files = [f"c{k:02d}.md" for k in range(len(table))]
            (root / "src" / "SUMMARY.md").write_text(
                "# Summary\n\n" + "".join(f"- [{f}]({f})\n" for f in files), encoding="utf-8")
            for f, (_, md, _) in zip(files, table):
                (root / "src" / f).write_text(md, encoding="utf-8")
            subprocess.run([MDBOOK, "build", str(root)], check=True, capture_output=True)
            for f, (name, _, want) in zip(files, table):
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


# --------------------------------------------------------------------------- footnotes as mdBook reads them


def pandoc_output(staged: tp.Stage, fmt: str = "html5") -> str:
    """book.md through Pandoc and the book filters (html5 shows what the EPUB shows)."""
    return subprocess.run([tp.pandoc_path(), "book.md", "-f", tp.READER, "-t", fmt, "--wrap", "none",
                           *tp._filter_meta("zh"), *tp._filters()],
                          cwd=staged.dir, capture_output=True, text=True, check=True).stdout


def mdbook_main(chapters: dict[str, str]) -> dict[str, str]:
    """The ``<main>`` of each page that plain mdBook makes of ``chapters`` (file → Markdown)."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "src").mkdir()
        (root / "book.toml").write_text('[book]\ntitle = "t"\n\n[output.html.search]\nenable = false\n',
                                        encoding="utf-8")
        (root / "src" / "SUMMARY.md").write_text("# Summary\n\n" + "".join(f"- [{n}]({n})\n" for n in chapters),
                                                 encoding="utf-8")
        for name, md in chapters.items():
            (root / "src" / name).write_text(md, encoding="utf-8")
        subprocess.run([MDBOOK, "build", str(root)], check=True, capture_output=True)
        pages = {name: (root / "book" / name.replace(".md", ".html")).read_text(encoding="utf-8") for name in chapters}
    return {name: page[page.index("<main>"):page.index("</main>")] for name, page in pages.items()}


class ScopedFootnotesTest(unittest.TestCase):
    """book.md scopes exactly the footnote references that mdBook reads, and the definitions (also in
    block quotes and list items). What the HTML edition shows as text stays as written, so Pandoc
    finds no footnote with that label and shows the same text."""

    def test_escaped_reference_is_text(self):
        out = tp.scope_footnotes("正文\\[^a] 与 [^a]，又 \\\\[^a]。\n\n[^a]: 甲注。\n", "ch-x")
        self.assertEqual(out, "正文\\[^a] 与 [^ch-x--a]，又 \\\\[^ch-x--a]。\n\n[^ch-x--a]: 甲注。\n")

    def test_what_mdbook_shows_as_text_stays(self):
        md = ('::: {.remark title="说明[^b]"}\n一条说明。\n:::\n\n记号 $[^b]$ 与\n$$\n[^b]\n$$\n\n'
              '<div class="aside">另见[^b]</div>\n\n<span title="[^b]">悬停</span> <https://e.com/[^b]> '
              '[x](y.md "[^b]") 某定理[^b](1972)\n\n正文[^b]。\n\n[^b]: 乙注。\n')
        self.assertEqual(tp.scope_footnotes(md, "ch-x"),
                         md.replace("正文[^b]", "正文[^ch-x--b]").replace("[^b]: ", "[^ch-x--b]: "))
        self.assertEqual(tp.footnote_numbers(md), {"b": 1})

    def test_definitions_in_containers(self):
        md = "正文[^q]与[^r]。\n\n> [^q]: 引用中的定义。\n\n- [^r]: 列表中的定义。\n"
        self.assertEqual(tp.scope_footnotes(md, "ch-x"),
                         "正文[^ch-x--q]与[^ch-x--r]。\n\n> [^ch-x--q]: 引用中的定义。\n\n- [^ch-x--r]: 列表中的定义。\n")
        self.assertEqual(tp.footnote_numbers(md), {"q": 1, "r": 2})

    @unittest.skipUnless(have_pandoc(), "pandoc is required")
    def test_pandoc_shows_what_the_html_edition_shows(self):
        with tempfile.TemporaryDirectory() as tmp:
            staged = stage_chapters(Path(tmp), {
                "ch01.md": "# 甲\n\n正文\\[^a] 与 [^a]。\n\n> [^q]: 甲的引用注。\n\n又[^q]。\n\n[^a]: 甲注。\n",
                "ch02.md": "# 乙\n\n乙文[^q]。\n\n- [^q]: 乙的列表注。\n\n记号 $[^q]$。\n",
            })
            html = pandoc_output(staged)
        self.assertIn("正文[^a] 与 <a", html)
        self.assertEqual(html.count('class="footnote-ref"'), 3)
        self.assertIn("甲的引用注。", html)
        self.assertIn("乙的列表注。", html)
        self.assertNotIn("ch-ch0", re.sub(r'(?:id|href)="[^"]*"', "", html))  # no scoped label shows

    @unittest.skipUnless(have_pandoc(), "pandoc is required")
    def test_definition_right_under_a_line_of_text(self):
        # mdBook reads the definition there; Pandoc only after a blank line, so book.md gets one.
        with tempfile.TemporaryDirectory() as tmp:
            staged = stage_chapters(Path(tmp), {
                "ch01.md": "# 甲\n\n正文[^b][^d]\n[^b]: 定义。\n[^c]: 紧随的定义。\n\n> 引[^c]\n> [^d]: 引用中的定义。\n",
            })
            md = staged.book_md.read_text(encoding="utf-8")
            self.assertIn("正文[^ch-ch01--b][^ch-ch01--d]\n\n[^ch-ch01--b]: 定义。\n[^ch-ch01--c]: 紧随的定义。\n", md)
            self.assertIn("> 引[^ch-ch01--c]\n>\n> [^ch-ch01--d]: 引用中的定义。", md)
            html = pandoc_output(staged)
        self.assertEqual(html.count('class="footnote-ref"'), 3)
        self.assertNotIn("[^", html)


class FootnoteCheckTest(unittest.TestCase):
    """``./tbook check`` warns about footnotes that mdBook and Pandoc read differently."""

    MD = ("正文[^A]、[^a]、某定理[^a](1972)、[^a][x]、[^a] (1972)。\n\n[^a]: 甲注。\n[^b c]: 有空格。\n\n"
          "```\n[^B]\n```\n")

    def test_problems(self):
        problems = tp.footnote_problems(self.MD)
        self.assertEqual([line for line, _ in problems], [1, 1, 1, 4], problems)
        self.assertIn("[^A]", problems[0][1])
        self.assertIn("[^a]", problems[0][1])
        self.assertIn("(", problems[1][1])
        self.assertIn("[^b c]", problems[3][1])
        self.assertEqual(tp.footnote_problems("正文[^a]。\n\n[^a]: 甲注。\n"), [])

    def test_check_reports_them(self):
        from tbook import check

        with tempfile.TemporaryDirectory() as tmp:
            model = load_edition(write_book(Path(tmp), {"ch01.md": "# 甲\n\n" + self.MD}))
            issues: list = []
            check.check_footnotes(model, issues)
        self.assertEqual([(i.severity, i.line) for i in issues], [("warning", 3)] * 3 + [("warning", 6)])

    @unittest.skipUnless(MDBOOK and have_pandoc(), "mdBook and pandoc are required")
    def test_the_editions_differ(self):
        # mdBook matches [^A] to [^a] ignoring case, but keys its notes by the label as written:
        # a number that leads nowhere. Pandoc matches case-sensitively: the text [^A].
        md = "正文[^A]。\n\n[^a]: 甲注。\n"
        main = mdbook_main({"c.md": md})["c.md"]
        self.assertIn('<sup class="footnote-reference" id="fr-A-1"><a href="#footnote-A">1</a></sup>', main)
        self.assertNotIn('id="footnote-', main)
        out = subprocess.run([tp.pandoc_path(), "-f", tp.READER, "-t", "html"], input=md,
                             capture_output=True, text=True, check=True).stdout
        self.assertIn("正文[^A]。", out)


class EnvUnderTextTest(unittest.TestCase):
    """A ``:::`` opener right under a line of text opens an environment for tbook (and so for the HTML
    edition); Pandoc only opens a div after a blank line, so book.md gets one. Text right after a
    closing ``:::`` goes on as Markdown in every edition."""

    MD = ("# 甲\n\n正文一行。\n::: {.problem #prob-x}\n问题正文。\n:::\n后文紧接[^a]。\n\n- 列表项\n"
          "::: {.remark #rem-x title=\"列表后\"}\n说明正文。\n:::\n## 小结\n\n> 引文\n::: {.example #exa-x}\n"
          "例子正文。\n:::\n\n[^a]: 甲注。\n")

    def test_blank_line_before_an_opener(self):
        md = "# 甲\n\n正文。\n:::::: {#x .tr-env}\n内容。\n:::: {.y}\n里面。\n::::\n::::::\n后文。\n"
        out = tp.restructure_chapter(md, chapter_path="ch01.md", depth=0, chapter_id="ch-ch01", title="甲",
                                     classes=["tr-chapter"], kv={}, linker=None)
        self.assertIn("正文。\n\n:::::: {#x .tr-env}\n内容。\n\n:::: {.y}\n里面。\n::::\n::::::\n后文。\n", out)

    @unittest.skipUnless(have_pandoc(), "pandoc is required")
    def test_pdf_and_epub_keep_the_environments(self):
        with tempfile.TemporaryDirectory() as tmp:
            staged = stage_chapters(Path(tmp), {"ch01.md": self.MD})
            html = pandoc_output(staged)
            typst = pandoc_output(staged, "typst")
        self.assertNotIn(":::", html)
        for id_, label in (("prob-x", "开放问题1.1"), ("rem-x", "注1.2"), ("exa-x", "例1.3")):
            self.assertIn(f'<section id="{id_}" class="tr-env', html)
            self.assertIn(f'<span class="tr-env-label">{label}</span>', html)
            self.assertIn(f'id: "{id_}")[', typst)
        self.assertIn('class="tr-badge tr-badge-open"', html)
        self.assertIn('badge: "OPEN"', typst)
        self.assertIn("<p>后文紧接<a", html)
        self.assertIn('<h2 id="小结">小结</h2>', html)

    @unittest.skipUnless(HAVE_KATEX and MDBOOK, "node, katex and mdBook are required")
    def test_html_edition_reads_text_after_a_closing_fence(self):
        from tbook import html

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ed = write_book(root, {"ch01.md": self.MD}, "tbook-test-env-under-text")
            try:
                html.build_edition(fixture_site(), ed.book, ed, None, None, root / "html")
            finally:
                shutil.rmtree(paths.BUILD / "stage" / "tbook-test-env-under-text", ignore_errors=True)
            page = (root / "html" / "ch01.html").read_text(encoding="utf-8")
        for id_ in ("prob-x", "rem-x", "exa-x"):
            self.assertIn(f'id="{id_}"', page)
        self.assertRegex(page, r"<p>后文紧接<sup")
        self.assertRegex(page, r'<h2 id="小结">')


@unittest.skipUnless(HAVE_KATEX and MDBOOK and have_pandoc(), "node, katex, mdBook and pandoc are required")
class FootnoteIdsInTheBookTest(unittest.TestCase):
    """The HTML edition's id of a heading with a footnote reference reaches that heading in the
    PDF/EPUB, also when the chapter has ``[^b]`` that mdBook does not read as a reference: in an
    environment title, a formula, raw HTML or a link form (its numbers would shift otherwise)."""

    SLUG = "tbook-test-footnote-ids"
    BODY = "## 注释[^a]\n\n正文[^b]。\n\n[^a]: 甲注。\n[^b]: 乙注。\n"
    CHAPTERS = {
        "ch01.md": "# 甲\n\n" + BODY,
        "ch02.md": "# 乙\n\n::: {.remark title=\"说明[^b]\"}\n一条说明。\n:::\n\n记号 $[^b]$ 表示上标。\n\n" + BODY,
        "ch03.md": ("# 丙\n\n<div class=\"aside\">另见[^b]</div>\n\n某定理[^b](1972)。\n\n> [^c]: 引用中的定义。\n\n"
                    "见[^c]。\n\n" + BODY),
    }

    def tearDown(self):
        shutil.rmtree(paths.BUILD / "stage" / self.SLUG, ignore_errors=True)

    def test_html_ids_reach_their_chapter(self):
        from tbook import html

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ed = write_book(root, self.CHAPTERS, self.SLUG)
            html.build_edition(fixture_site(), ed.book, ed, None, None, root / "html")
            html_ids = {name: re.findall(r'<h2[^>]* id="([^"]+)"', (root / "html" / name.replace(".md", ".html"))
                                         .read_text(encoding="utf-8"))
                        for name in self.CHAPTERS}
            self.assertEqual(html_ids, {"ch01.md": ["注释1"], "ch02.md": ["注释1"], "ch03.md": ["注释2"]})
            links = "\n".join(f"[{name}]({name}#{ids[0]})" for name, ids in html_ids.items())
            staged = stage_chapters(root / "pdf", {**self.CHAPTERS, "ch04.md": "# 丁\n\n" + links + "\n"})
            md = staged.book_md.read_text(encoding="utf-8")
            self.assertIn('tr-title="说明[^b]"', md)
            self.assertIn("记号 $[^b]$ 表示上标。", md)
            self.assertIn("[ch01.md](#注释1)\n[ch02.md](#ch-ch02--注释1)\n[ch03.md](#注释2)", md)
            self.assertIn("## 注释[^ch-ch02--a] {#ch-ch02--注释1}", md)
            self.assertNotIn("dangling", pandoc_stderr(staged))


# --------------------------------------------------------------------------- HTML blocks, setext pairs, fragments


class HtmlBlockContainerTest(unittest.TestCase):
    """An HTML block has no lazy lines: it ends with the block quote or list item it is in (also an
    unclosed ``<pre>``), so a footnote reference right after it is one for mdBook and is scoped."""

    def test_reference_after_the_block_is_scoped(self):
        cases = ["> <div class=\"tip\">\n> 提示内容。\n> </div>\n正文继续[^a]。\n\n[^a]: 甲注。\n",
                 "- 第一项\n- <div>第二项</div>\n后文[^a]。\n\n[^a]: 乙注。\n",
                 "> <pre>\n> 代码\n\n后文[^a]。\n\n[^a]: 丙注。\n",
                 "- <pre>\n  x\n\n正文[^a]。\n\n[^a]: 丁注。\n",
                 "- 项\n\n  <div>\n  里面\n正文[^a]。\n\n[^a]: 戊注。\n"]
        for md in cases:
            with self.subTest(md):
                self.assertEqual(tp.scope_footnotes(md, "P"), md.replace("[^a]", "[^P--a]"))
                self.assertEqual(tp.footnote_numbers(md), {"a": 1})

    def test_block_goes_on_in_its_container(self):
        for md in ("> <div>\n> 里面[^a]\n> </div>\n\n[^a]: A\n", "- <pre>\n  x\n\n  里面[^a]\n  </pre>\n\n[^a]: A\n"):
            with self.subTest(md):
                self.assertEqual(tp.scope_footnotes(md, "P"), md.replace("[^a]: ", "[^P--a]: "))
                self.assertEqual(tp.footnote_numbers(md), {})


class FootnoteGrammarTest(unittest.TestCase):
    """mdBook reads ``[^a][ ]`` (no link label), ``<b and [^a] c>`` (no tag) and ``[^a]`` under
    ``#标签`` + ``<b>`` (no heading, so ``<b>`` is inline HTML) as references (FOOTNOTE_HEADINGS)."""

    MD = ["正文[^a][ ]。\n\n[^a]: A\n", "若 a <b and [^a] c> 则。\n\n[^a]: A\n", "#标签\n<b>\n正文[^a]。\n\n[^a]: A\n"]

    def test_references(self):
        for md in self.MD:
            with self.subTest(md):
                self.assertEqual(tp.footnote_numbers(md), {"a": 1})
                self.assertEqual(tp.scope_footnotes(md, "P"), md.replace("[^a]", "[^P--a]"))
                self.assertEqual(tp.footnote_problems(md), [])

    def test_still_links_and_tags(self):
        self.assertEqual(tp.footnote_numbers("正文[^a][ x ]、<b data-x=\"[^a]\">。\n\n[^a]: A\n"), {})
        # A setext heading ends its paragraph: the lone tag under it starts an HTML block.
        self.assertEqual(tp.footnote_numbers("标题\n---\n<img src=\"x.png\">\n正文[^a]。\n\n[^a]: A\n"), {})


class SetextInFormulaTest(unittest.TestCase):
    """A ``$$`` line followed by ``=`` or ``---`` inside the formula is no setext heading: the
    formula takes the lines up to its end into its paragraph, as for mdscan.scan_blocks."""

    def test_formula_stays(self):
        for md in ("求和：\n\n$$\n=\n$$\n", "式：\n\n$$\n---\n$$\n", "$$\n=\n$$\n"):
            with self.subTest(md):
                self.assertEqual(tp.normalize_setext(md), md)
        self.assertEqual(tp.normalize_setext("标题\n===\n\n$x$\n---\n\n$$\n=\n$$\n"), "# 标题\n\n## $x$\n\n$$\n=\n$$\n")


class ChapterFragmentTest(unittest.TestCase):
    """``other.md#x`` (and ``#x``) resolves within that chapter as its HTML page does: a heading
    slug, an explicit ``{#id}``, an id in raw HTML or an environment id. A fragment the chapter
    lacks leads nowhere, also in the PDF/EPUB: it never lands on another chapter's id."""

    CHAPTERS = [("a.md", "# 甲\n\n## 注释[^a]\n\n[^a]: A\n"),
                ("b.md", "# 乙\n\n正文[^x]。\n\n## 注释[^b]\n\n## 小节 {#sec-own}\n\n<a id=\"raw-x\"></a>锚点。\n\n"
                         "[^x]: X\n[^b]: B\n")]

    def test_anchors_hold_every_id_of_the_page(self):
        ids = tp.assign_heading_ids(self.CHAPTERS, {"a.md": "ch-a", "b.md": "ch-b"}, {"ch-a", "ch-b"})
        self.assertEqual(ids.anchors["a.md"], {"甲": "ch-a", "注释1": "注释1", "注释a": "注释1"})
        self.assertEqual(ids.anchors["b.md"], {"sec-own": "sec-own", "乙": "ch-b", "注释2": "注释2", "注释b": "注释2",
                                               "raw-x": "raw-x"})

    def test_missing_fragment_dangles(self):
        ids = tp.assign_heading_ids(self.CHAPTERS, {"a.md": "ch-a", "b.md": "ch-b"}, {"ch-a", "ch-b"})
        with tempfile.TemporaryDirectory() as tmp:
            ed = write_book(Path(tmp), dict(self.CHAPTERS))
            linker = tp._Linker(Path(tmp) / "stage", ed, {"a.md": "ch-a", "b.md": "ch-b"}, [], set(),
                                anchors=ids.anchors, env_ids={"rem-x"})
            line = ("[错](b.md#注释1) [对](b.md#注释2) [显式](b.md#sec-own) [原始](b.md#raw-x) [环境](b.md#rem-x) "
                    "[甲](a.md#注释1) [章](b.md) [无](<b.md#a b>) [本章](#注释1) [本章对](#注释2)")
            self.assertEqual(linker.rewrite_line(line, "b.md"),
                             "[错](#b.md#注释1) [对](#注释2) [显式](#sec-own) [原始](#raw-x) [环境](#rem-x) "
                             "[甲](#注释1) [章](#ch-b) [无](#b.md#a%20b) [本章](#b.md#注释1) [本章对](#注释2)")
            # Without anchors (no heading ids known) a fragment stays as written.
            bare = tp._Linker(Path(tmp) / "stage", ed, {"a.md": "ch-a", "b.md": "ch-b"}, [], set())
            self.assertEqual(bare.rewrite_line("[x](b.md#注释1)", "a.md"), "[x](#注释1)")


@unittest.skipUnless(have_pandoc() and have_typst(), "pandoc and typst are required")
class EditionsReadTheBookTest(unittest.TestCase):
    """The PDF and EPUB of a book with HTML blocks in containers, a setext-looking pair in a formula
    and links to fragments: every note keeps its text, the formula stays a formula, and a fragment
    the linked chapter lacks is text."""

    CHAPTERS = {
        "ch01.md": "# 一 提示框\n\n> <div class=\"tip\">\n> 提示内容。\n> </div>\n正文继续[^a]。\n\n## 注释[^a]\n\n[^a]: 甲注。\n",
        "ch02.md": "# 二 列表\n\n- 第一项\n- <div>第二项</div>\n后文[^a]。\n\n[^a]: 乙注。\n",
        "ch03.md": "# 三 未闭合\n\n> <pre>\n> 代码\n\n后文[^a]。\n\n[^a]: 丙注。\n",
        "ch04.md": ("# 四 求和\n\n求和：\n\n$$\n=\n$$\n\n正文[^c]。\n\n## 注释[^b]\n\n::: {.remark #rem-x}\n说明。\n:::\n\n"
                    "## 小节 {#sec-own}\n\n[^b]: 丁注。\n[^c]: 戊注。\n"),
        "ch05.md": ("# 五 链接\n\n见[错](ch04.md#注释1)、[对](ch04.md#注释2)、[环境](ch04.md#rem-x)、[显式](ch04.md#sec-own)、"
                    "[甲](ch01.md#注释1)，本章[无](#注释1)。\n\n正文[^a][ ]。\n\n[^a]: 己注。\n"),
    }

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="tbook-test-editions-"))
        ed = write_book(cls.tmp, cls.CHAPTERS, "tbook-test-editions")
        model = load_edition(ed)
        assert not model.issues, [i.format() for i in model.issues]
        old = os.environ.get("TBOOK_EPUBCHECK")
        os.environ["TBOOK_EPUBCHECK"] = "0"
        try:
            epub = tp.build_epub(fixture_site(), ed.book, ed, model, None, cls.tmp / "book.epub",
                                 stage_dir=cls.tmp / "stage-epub")
        finally:
            if old is None:
                os.environ.pop("TBOOK_EPUBCHECK", None)
            else:
                os.environ["TBOOK_EPUBCHECK"] = old
        with zipfile.ZipFile(epub) as z:
            cls.xhtml = {n: z.read(n).decode("utf-8") for n in z.namelist() if re.search(r"text/ch\d+\.xhtml$", n)}
        tp.build_pdf(fixture_site(), ed.book, ed, model, None, "screen", cls.tmp / "book.pdf",
                     stage_dir=cls.tmp / "stage-pdf")
        cls.typst = (cls.tmp / "stage-pdf" / "main.typ").read_text(encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def chapter(self, text: str) -> str:
        return next(t for t in self.xhtml.values() if text in t)

    def test_every_note_keeps_its_text(self):
        for text, note in (("提示内容", "甲注。"), ("第二项", "乙注。"), ("代码", "丙注。"), ("求和", "戊注。"),
                           ("本章", "己注。")):
            with self.subTest(note):
                self.assertIn(note, self.chapter(text))
                self.assertIn(f"#footnote[{note}]", self.typst)
        texts = "".join(self.xhtml.values())
        self.assertNotIn("[^", texts)
        self.assertNotIn("[^", self.typst)

    def test_formula_stays_a_formula(self):
        self.assertIn("$ = $", self.typst)
        self.assertNotIn("$$", self.typst)

    def test_fragments_resolve_in_their_chapter(self):
        links = self.chapter("本章")
        self.assertIn('<span class="tr-dangling">错</span>', links)
        self.assertIn('<span class="tr-dangling">无</span>', links)
        self.assertRegex(links, r'<a href="ch\d+\.xhtml#注释2">对</a>')
        self.assertRegex(links, r'<a href="ch\d+\.xhtml#rem-x">环境</a>')
        self.assertRegex(links, r'<a href="ch\d+\.xhtml#sec-own">显式</a>')
        first = re.search(r'<a href="(ch\d+\.xhtml)#注释1">甲</a>', links)
        self.assertTrue(first and "甲注。" in self.xhtml["EPUB/text/" + first.group(1)], links)
        self.assertIn("#link(<注释2>)[对]", self.typst)
        self.assertNotIn("#link(<注释1>)[错]", self.typst)


class ScanTimeTest(unittest.TestCase):
    """The footnote, HTML block, setext and heading scanners stay linear: a few thousand lines take
    well under a second (the bounds are generous)."""

    def timed(self, fn, *args) -> float:
        start = time.perf_counter()
        fn(*args)
        return time.perf_counter() - start

    def test_footnotes(self):
        md = ("正文[^a] 与 $x$ 与 `c` 与 <span>x</span>。\n\n" * 3000) + "[^a]: A\n"
        self.assertLess(self.timed(tp.footnote_numbers, md), 2.0)
        self.assertLess(self.timed(tp.scope_footnotes, md, "P"), 2.0)

    def test_html_blocks_in_containers(self):
        md = ("- <div>项</div>\n正文[^a]。\n\n> - <p>\n>   x\n>\n- 项\n\n  <div>\n  x\n正文\n\n" * 2000) + "[^a]: A\n"
        lines = md.split("\n")
        scan = mdscan.scan_blocks(lines)
        self.assertLess(self.timed(tp._raw_html_lines, lines, scan), 1.0)
        # Many markers on a line: each is read once.
        lines = ["> " * 3000 + "<div>"] + ["> " * 3000 + "- x"] * 100
        scan = mdscan.scan_blocks(lines)
        self.assertLess(self.timed(tp._raw_html_lines, lines, scan), 1.0)

    def test_setext_and_headings(self):
        self.assertLess(self.timed(tp.normalize_setext, "标题\n===\n\n$$\n=\n$$\n\n正文 `x` 与 $y$。\n\n" * 2000), 2.0)
        self.assertLess(self.timed(tp.heading_slugs, "甲 <!-- c --> 乙" * 5000), 0.5)


if __name__ == "__main__":
    unittest.main()
