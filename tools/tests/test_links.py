"""Regression tests for links and link reference definitions in every form CommonMark allows.

Run: PYTHONPATH=tools:tools/tests python -m unittest test_links

* ``[n]: text`` lines (not definitions) inside a list item or block quote vanished from PDF/EPUB:
  Pandoc's Markdown read them as definitions; the stager escaped only those at the left margin.
* A definition whose title holds backslash escapes (``"…\\"…"``) was not recognised: HTML shipped a
  dead ``../assets/…`` image and PDF/EPUB printed the definition as text.
* ``lean:`` links in other valid forms (a definition in a list item or block quote, ``'…'`` and
  ``(…)`` titles, nested brackets in the link text, the autolink ``<lean:GID>``) were neither checked
  nor pinned and shipped a raw ``lean:`` href; one written across lines still cannot be read, so
  ``./tbook check`` reports it and no target writes its ``lean:`` destination.
* ``<lean:GID>`` as the destination of a link or definition begun on an earlier line was read as an
  autolink: check passed, HTML shipped ``href="[GID](https://…)"`` and the EPUB build failed.
* Indented code (top level, list items, quotes, footnotes) stays as written and is not checked.
* A link or image with an empty destination made Typst fail ("URL must not be empty") and an empty
  image source failed epubcheck; ``[x]:`` with no destination vanished from PDF/EPUB (Pandoc read an
  empty definition) while HTML showed it.
* A definition cannot interrupt a paragraph: ``para\\n[fig]: a.svg`` was rewritten, cited or reported
  as one; ``[1]: <lean:GID> 文字`` (also ``<lean:GID>，文字``) was a definition or a false stray; a
  ``[0,1]:`` line in a formula over lines was escaped for Pandoc; a destination on the line after its
  label was neither read nor reported.

The fixtures are those of ``test_markdown`` (a throwaway repository, an in-memory lock); the
Pandoc tests are skipped when Pandoc is missing.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from tbook import check, config, lean, mdscan, model, render
from test_core import FakeLedger
from test_markdown import GID_DEF, GID_MISSING, GID_OK, SOURCE_DEF, SOURCE_OK, Repo, make_lock, write
from test_pandoc import fixture_site, have_pandoc, have_typst, make_book, run_filters

FIG = "_book/assets/fig.svg"


def pandoc_plain(md: str) -> str:
    from tbook import pandoc

    return subprocess.run([pandoc.pandoc_path(), "-f", pandoc.READER, "-t", "plain", "--wrap", "none"], input=md,
                          capture_output=True, text=True, check=True).stdout


MDBOOK = os.environ.get("MDBOOK") or shutil.which("mdbook")


def mdbook_html(md: str) -> str:
    """The ``<main>`` of the page real mdBook makes of ``md`` (a chapter as render writes it)."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "src").mkdir()
        (root / "book.toml").write_text('[book]\ntitle = "t"\n', encoding="utf-8")
        (root / "src" / "SUMMARY.md").write_text("# Summary\n\n- [c](c.md)\n", encoding="utf-8")
        (root / "src" / "c.md").write_text(md, encoding="utf-8")
        subprocess.run([MDBOOK, "build"], cwd=root, capture_output=True, check=True)
        page = (root / "book" / "c.html").read_text(encoding="utf-8")
    return page[page.index("<main>"):page.index("</main>")]


# --------------------------------------------------------------------------- finding 2


class ContainerParagraphTests(unittest.TestCase):
    """``[n]: text`` that is no definition stays text in PDF/EPUB inside block quotes and list items too."""

    LINES = {
        "- [1]: Knuth, The Art of Computer Programming.": "- \\[1]: Knuth, The Art of Computer Programming.",
        "1. [2]: Zeckendorf, 1972.": "1. \\[2]: Zeckendorf, 1972.",
        "> [3]: Lamport, LaTeX.": "> \\[3]: Lamport, LaTeX.",
        "    [4]: continued in a list item.": "    \\[4]: continued in a list item.",
        "> - [5]: nested, in a quote.": "> - \\[5]: nested, in a quote.",
        "  * [6]: 见 ![fig](../assets/fig.svg)。": f"  * \\[6]: 见 ![fig]({FIG})。",
        "[7 [x] y]: a label with brackets": "\\[7 [x] y]: a label with brackets",
    }

    def test_pandoc_target_escapes_them(self):
        with Repo() as repo:
            ctx, doc = repo.ctx(target="pandoc"), repo.doc("ch01.md")
            for line, out in self.LINES.items():
                self.assertIsNone(mdscan.refdef(line), line)
                self.assertEqual(render.transform_line(line, doc, ctx), out)
            mctx = repo.ctx()
            for line in self.LINES:
                self.assertNotIn("\\[", render.transform_line(line, doc, mctx), "mdBook reads them as text already")

    def test_definitions_in_containers_stay_definitions(self):
        with Repo() as repo:
            for target in ("mdbook", "pandoc"):
                ctx, doc = repo.ctx(target=target), repo.doc("ch01.md")
                for line, out in (("- [f]: ../assets/fig.svg", f"- [f]: {FIG}"),
                                  ("> [f]: ../assets/fig.svg 'T'", f"> [f]: {FIG} 'T'"),
                                  ("    [f]: <../assets/fig two.svg>", "    [f]: _book/assets/fig%20two.svg"),
                                  ("> 1. [f]: ../assets/fig.svg", f"> 1. [f]: {FIG}"),
                                  ("- [^n]: 脚注 [fig](../assets/fig.svg)", f"- [^n]: 脚注 [fig]({FIG})")):
                    self.assertEqual(render.transform_line(line, doc, ctx), out, (target, line))

    @unittest.skipUnless(have_pandoc(), "pandoc not installed")
    def test_pdf_and_epub_show_them(self):
        """Through the real stager: the lines are in book.md escaped, and Pandoc keeps their text."""
        from tbook import pandoc

        body = "\n\n".join(self.LINES) + "\n\n> [q]: ../assets/fig.svg\n\n![引][q]\n"
        with Repo() as repo, tempfile.TemporaryDirectory() as tmp:
            write(repo.edition.dir / "ch01.md", "# 第一章\n\n## 参考文献\n\n" + body)
            st = pandoc.stage(config.load_site(), repo.book, repo.edition, None, make_lock(), out_dir=Path(tmp))
            book_md = st.book_md.read_text(encoding="utf-8")
            staged_fig = (Path(tmp) / FIG).is_file()
        plain = pandoc_plain(book_md)
        for text in ("[1]: Knuth, The Art of Computer Programming.", "[2]: Zeckendorf, 1972.", "[3]: Lamport, LaTeX.",
                     "[4]: continued in a list item.", "[5]: nested, in a quote.", "[6]: 见", "[7 [x] y]: a label"):
            self.assertIn(text, plain)
        self.assertIn(f"![引][q]", book_md)
        self.assertIn(f"> [q]: {FIG}", book_md, "a definition in a quote is a definition")
        self.assertTrue(staged_fig)


# --------------------------------------------------------------------------- finding 4


class EscapedTitleTests(unittest.TestCase):
    """A definition's title may hold backslash escapes, as in CommonMark and Pandoc."""

    TITLES = (' "Knuth 的 \\"进位\\" 图"', " 'it\\'s'", " (a \\) b)", ' "a \\\\"')

    def test_recognised_and_rewritten(self):
        with Repo() as repo:
            for target in ("mdbook", "pandoc"):
                ctx, doc = repo.ctx(target=target), repo.doc("ch01.md")
                for title in self.TITLES:
                    line = f"[fig]: ../assets/fig.svg{title}"
                    self.assertIsNotNone(mdscan.refdef(line), line)
                    self.assertEqual(render.transform_line(line, doc, ctx), f"[fig]: {FIG}{title}")
                self.assertEqual(ctx.book_files, {repo.assets / "fig.svg"})
        for line in ('[x]: url "a \\" b" c', "[x]: url 'a' 'b'", "[x]: url (a) b"):
            self.assertIsNone(mdscan.refdef(line), line)

    @unittest.skipUnless(have_pandoc(), "pandoc not installed")
    def test_pandoc_reads_the_title(self):
        with Repo() as repo:
            ctx, doc = repo.ctx(target="pandoc"), repo.doc("ch01.md")
            line = render.transform_line(f"[fig]: ../assets/fig.svg{self.TITLES[0]}", doc, ctx)
        html = run_filters(f"![图][fig]\n\n{line}\n", "html")
        self.assertIn(f'src="{FIG}"', html)
        self.assertIn('title="Knuth 的 &quot;进位&quot; 图"', html)
        self.assertNotIn("[fig]:", html)


# --------------------------------------------------------------------------- finding 6


class LeanLinkEveryFormTests(unittest.TestCase):
    """Every valid way to write a ``lean:`` link is checked, pinned and rendered; what the tools cannot
    read is reported and never shipped as a ``lean:`` URL."""

    TEXT = (f"# 第一章\n\n"
            f"1.  第一点，见 [该定理][lt]。\n\n"  # 3
            f"    [lt]: lean:{GID_OK}\n\n"  # 5
            f"> 引文中的 [另一个][lq]。\n"  # 7
            f">\n"
            f"> [lq]: lean:{GID_MISSING}\n\n"  # 9
            f"[甲](lean:{GID_DEF} '说明') 与 [乙](lean:{GID_OK} (括号)) 与 [x [y] z](lean:{GID_MISSING})\n\n"  # 11
            f"自动链接 <lean:{GID_OK}> 与 <lean:{GID_MISSING}>，[![图](../assets/fig.svg)](lean:{GID_DEF})\n\n"  # 13
            f"- [ld]: <lean:{GID_DEF}> \"T\"\n")  # 15

    def test_lean_link_gids(self):
        self.assertEqual(mdscan.lean_link_gids(f"    [lt]: lean:{GID_OK}"), [GID_OK])
        self.assertEqual(mdscan.lean_link_gids(f"> [lq]: lean:{GID_OK}"), [GID_OK])
        self.assertEqual(mdscan.lean_link_gids(f"- [ld]: <lean:{GID_OK}> 'T'"), [GID_OK])
        self.assertEqual(mdscan.lean_link_gids(f"- [^n]: lean:{GID_OK}"), [], "a footnote")
        self.assertEqual(mdscan.lean_link_gids(f"[a](lean:{GID_OK} 'x') [b](lean:{GID_DEF} (y)) [c [d] e](lean:X/Y.z)"),
                         [GID_OK, GID_DEF, "X/Y.z"])
        self.assertEqual(mdscan.lean_link_gids(f"<lean:{GID_OK}> [![i](lean:X/Y.img)](lean:X/Y.out) "
                                               f"`<lean:X/Y.code>` [z](<lean:X/Y.angle>)"),
                         [GID_OK, "X/Y.img", "X/Y.out", "X/Y.angle"])

    def test_model_check_and_pin(self):
        from tbook import pin

        with Repo() as repo:
            write(repo.edition.dir / "ch01.md", self.TEXT)
            m = model.load_edition(repo.edition)
            self.assertEqual(m.issues, [])
            self.assertEqual(m.chapters[1].lean_links, [
                (5, GID_OK), (9, GID_MISSING), (11, GID_DEF), (11, GID_OK), (11, GID_MISSING),
                (13, GID_OK), (13, GID_MISSING), (13, GID_DEF), (15, GID_DEF)])
            self.assertEqual(set(pin.cited_gids([repo.book])), {GID_OK, GID_DEF, GID_MISSING})

    def test_check_reports_each_form(self):
        """Each form cites its own declaration that the lock lacks: check names every one (it said
        nothing for the first five), and pin --refresh would record them."""
        from tbook import pin

        missing = [f"D5/S1/Deficit/DeficitThreeValued.no_such_{k}" for k in range(7)]
        text = (f"# 第一章\n\n1.  第一点，见 [该定理][a]。\n\n    [a]: lean:{missing[0]}\n\n"
                f"> 引文中的 [另一个][b]。\n>\n> [b]: lean:{missing[1]}\n\n"
                f"[甲](lean:{missing[2]} '说明') [乙](lean:{missing[3]} (括号)) [x [y] z](lean:{missing[4]})\n\n"
                f"<lean:{missing[5]}> [![图](../assets/fig.svg)](lean:{missing[6]})\n")
        with Repo() as repo:
            write(repo.edition.dir / "ch01.md", text)
            m = model.load_edition(repo.edition)
            self.assertEqual(sorted(g for _, g in m.chapters[1].lean_links), missing)
            self.assertTrue(set(missing) <= set(pin.cited_gids([repo.book])))
            issues: list[model.Issue] = []
            with mock.patch.object(lean, "Ledger", lambda r, **kw: FakeLedger()):
                check.check_lean({"demo": {"zh": m}}, make_lock(), config.load_site(), issues, offline=True)
            reported = sorted((i.line, i.message) for i in issues if i.severity == "error" and i.path.name == "ch01.md")
            self.assertEqual(reported, sorted(
                (line, f"{gid} is not in trureturing.lock.json; run ./tbook pin --refresh")
                for line, gid in zip((5, 9, 11, 11, 11, 13, 13), missing)))

    def test_no_target_writes_a_lean_url(self):
        with Repo() as repo:
            write(repo.edition.dir / "ch01.md", self.TEXT)
            repo.model = model.load_edition(repo.edition)
            for target in ("mdbook", "pandoc"):
                out, ctx = repo.render("ch01.md", target=target)
                self.assertNotIn("lean:", out, target)
                self.assertIn(f"    [lt]: {SOURCE_OK}", out)
                self.assertIn("> [lq]: #", out)
                self.assertIn(f'[甲]({SOURCE_DEF} "说明") 与 [乙]({SOURCE_OK} "括号") 与 x [y] z', out)
                gid = mdscan.escape_markdown(GID_OK)
                self.assertIn(f"自动链接 [{gid}]({SOURCE_OK}) 与 {mdscan.escape_markdown(GID_MISSING)}，"
                              f"[![图]({FIG})]({SOURCE_DEF})", out)
                self.assertIn(f'- [ld]: {SOURCE_DEF} "T"', out)
                self.assertEqual(ctx.issues, [])

    def test_link_titles_read_alike(self):
        self.assertEqual(mdscan.quoted_title(" 'it\\'s \"q\"'"), ' "it\\\'s \\"q\\""')
        self.assertEqual(mdscan.quoted_title(" (a \\) b)"), ' "a \\) b"')
        with Repo() as repo:
            ctx, doc = repo.ctx(target="pandoc"), repo.doc("ch01.md")
            self.assertEqual(render.transform_line("[x](https://example.org (t))", doc, ctx),
                             '[x](https://example.org "t")', "Pandoc reads (…) as part of the destination")
            self.assertEqual(render.transform_line("[x](https://example.org 't')", doc, ctx),
                             "[x](https://example.org 't')")

    def test_link_text_cannot_hang_the_scanner(self):
        for line in ("[" + "`a` " * 200 + "end", "[" * 400 + "x", "[a [b " * 200):
            t = time.monotonic()
            mdscan.lean_link_gids(line)
            self.assertLess(time.monotonic() - t, 1.0)

    @unittest.skipUnless(have_pandoc(), "pandoc not installed")
    def test_pandoc_reads_the_rewritten_links(self):
        with Repo() as repo:
            write(repo.edition.dir / "ch01.md", self.TEXT)
            repo.model = model.load_edition(repo.edition)
            out, _ = repo.render("ch01.md", target="pandoc")
        html = run_filters(out, "html")
        self.assertNotIn("lean:", html)
        self.assertIn(f'<a href="{SOURCE_DEF}" title="说明">甲</a>', html)
        self.assertIn(f'<a href="{SOURCE_OK}" title="括号">乙</a>', html)
        self.assertIn(f'<a href="{SOURCE_OK}">该定理</a>', html)
        self.assertIn(f'<a href="{SOURCE_DEF}"><img src="{FIG}"', html)


class StrayLeanLinkTests(unittest.TestCase):
    """A ``lean:`` link the line scanner cannot read is an error in ``./tbook check``, and no target
    writes its destination: a link keeps its text, a definition gets ``#``, raw HTML gets ``#``."""

    TEXT = (f"# 第一章\n\n"
            f"见 [跨行的\n链接文字](lean:{GID_OK}) 与 [地址在下一行](\n  lean:{GID_DEF} \"T\")。\n\n"  # 3-5
            f"[ml]:\n  lean:{GID_MISSING}\n\n"  # 7-8
            f"> [跨行\n> 引文](lean:{GID_OK})\n\n"  # 10-11
            f"<a href=\"lean:{GID_OK}\">原始 HTML</a>\n\n"  # 13
            f"不是链接：](lean:{GID_OK}) 与 `[代码\n跨行](lean:x)` 与 [^n]: lean:{GID_OK}\n")

    def test_found(self):
        lines = self.TEXT.split("\n")
        strays = mdscan.stray_lean_links(lines)
        self.assertEqual([s.line + 1 for s in strays], [4, 5, 8, 11, 13])
        out, _ = mdscan.without_stray_lean(lines)
        text = "\n".join(out)
        self.assertIn("见 跨行的\n链接文字 与 地址在下一行。", text)
        self.assertIn("[ml]: #\n", text, "on the label's line: a '#' opening a line is an ATX heading")
        self.assertIn("> 跨行\n> 引文", text)
        self.assertIn('<a href="#">原始 HTML</a>', text)
        self.assertIn(f"不是链接：](lean:{GID_OK})", text, "no '[' opens it: not a link")
        self.assertEqual(mdscan.stray_lean_links([f"[a](lean:{GID_OK}) [b]: lean:x", f"[c]: lean:{GID_OK}"]), [])
        nested = [f'见 [<a href="lean:{GID_DEF}">内</a>', f"外](lean:{GID_OK})"]
        out, strays = mdscan.without_stray_lean(nested)
        self.assertEqual(out, ['见 <a href="#">内</a>', "外"])
        self.assertEqual(sorted(s.line for s in strays), [0, 1])

    def test_check_reports_them(self):
        with Repo() as repo:
            write(repo.edition.dir / "ch01.md", self.TEXT)
            m = model.load_edition(repo.edition)
            self.assertEqual([(i.severity, i.line, i.message) for i in m.issues],
                             [("error", n, model.STRAY_LEAN) for n in (4, 5, 8, 11, 13)])

    def test_builds_drop_the_destination(self):
        with Repo() as repo:
            write(repo.edition.dir / "ch01.md", self.TEXT[:self.TEXT.index("不是链接")])  # only the strays
            repo.model = model.load_edition(repo.edition)
            for target in ("mdbook", "pandoc"):
                out, ctx = repo.render("ch01.md", target=target)
                self.assertNotIn("](lean:", out)
                self.assertNotIn("lean:" + GID_MISSING, out)
                self.assertNotIn('href="lean:', out)
                self.assertEqual(len(ctx.issues), 5, ctx.issues)
                self.assertTrue(all("loses its lean: destination" in i for i in ctx.issues))

    def test_titles_never_link_to_lean(self):
        with Repo() as repo:
            write(repo.edition.dir / "ch01.md", f"# 第一章\n\n::: {{.theorem #thm-t title=\"见 [x](lean:{GID_OK}) 与 "
                                                f"<lean:{GID_DEF}>\" lean=\"{GID_OK}\"}}\n陈述。\n:::\n")
            m = model.load_edition(repo.edition)
            env = m.envs["thm-t"]
            self.assertEqual(m.title_markdown(env), f"见 x 与 {mdscan.escape_markdown(GID_DEF)}")
            self.assertEqual(m.title_text(env), f"见 x 与 {GID_DEF}")
            issues: list[model.Issue] = []
            check.check_env_policy(m, issues)
            self.assertEqual([(i.line, i.message.split(" (")[0]) for i in issues],
                             [(3, "a title cannot link to Lean")])

    @unittest.skipUnless(have_pandoc(), "pandoc not installed")
    def test_pandoc_reads_the_neutralised_text(self):
        """No empty heading (an empty EPUB nav entry) and no empty link (Typst refuses it)."""
        with Repo() as repo:
            write(repo.edition.dir / "ch01.md", self.TEXT[:self.TEXT.index("不是链接")] + "\n[用][ml]\n")
            repo.model = model.load_edition(repo.edition)
            out, _ = repo.render("ch01.md", target="pandoc")
        html = run_filters(out, "html")
        self.assertNotIn("lean:", html)
        self.assertNotIn('href=""', html)
        self.assertEqual(html.count("<h1"), 1, html)
        self.assertIn("跨行的 链接文字 与 地址在下一行", html.replace("\n", ""))
        self.assertIn('<span class="tr-dangling">用</span>', html)

    @unittest.skipUnless(have_pandoc(), "pandoc not installed")
    def test_pandoc_filter_backstop(self):
        html = run_filters(f"[a\nb](lean:{GID_OK}) ![c](lean:{GID_DEF})\n\n[x][d]\n\n[d]:\n  lean:{GID_OK}\n", "html")
        self.assertNotIn("lean:", html)
        self.assertIn("a b", html)


class AngleDestinationAcrossLinesTests(unittest.TestCase):
    """``<lean:GID>`` that is the destination of a link or definition begun on an earlier line is that
    link's destination (CommonMark), not an autolink. It was read as an autolink: check passed, HTML
    shipped ``href="[GID](https://…)"`` and the EPUB build failed. Now it is a stray like any other."""

    TEXT = (f"# 第一章\n\n"
            f"见 [三值\n亏量定理](<lean:{GID_OK}>) 一行。\n\n"  # 3-4
            f"见 [该定理][dt]。\n\n"  # 6
            f"[dt]:\n  <lean:{GID_DEF}>\n\n"  # 8-9
            f"[跨行\n标签]: <lean:{GID_OK}>\n\n"  # 11-12
            f"[标题在下一行](<lean:{GID_DEF}>\n \"T\")\n\n"  # 14-15
            f"> [引文\n> 链接](<lean:{GID_OK}>)\n\n"  # 17-18
            f"段落\n<lean:{GID_MISSING}> 是自动链接，foo](<lean:{GID_DEF}>) 也是。\n")  # 20-21
    STRAYS = [4, 9, 12, 14, 18]

    def test_found_and_not_read_as_autolinks(self):
        lines = self.TEXT.split("\n")
        self.assertEqual([s.line + 1 for s in mdscan.stray_lean_links(lines)], self.STRAYS)
        cited = [(n, g) for n, line in mdscan.iter_text_lines(mdscan.parse_blocks(self.TEXT))
                 for g in mdscan.lean_link_gids(line)]
        self.assertEqual(cited, [(21, GID_MISSING), (21, GID_DEF)], "only the real autolinks")

    def test_check_reports_them(self):
        with Repo() as repo:
            write(repo.edition.dir / "ch01.md", self.TEXT)
            m = model.load_edition(repo.edition)
            self.assertEqual([(i.severity, i.line, i.message) for i in m.issues],
                             [("error", n, model.STRAY_LEAN) for n in self.STRAYS])
            self.assertEqual(m.chapters[1].lean_links, [(21, GID_MISSING), (21, GID_DEF)])

    def test_builds_drop_the_destination(self):
        with Repo() as repo:
            write(repo.edition.dir / "ch01.md", self.TEXT)
            repo.model = model.load_edition(repo.edition)
            for target in ("mdbook", "pandoc"):
                out, ctx = repo.render("ch01.md", target=target)
                self.assertNotIn("lean:", out, target)
                self.assertNotIn("](<", out, target)
                self.assertNotIn("]([", out[:out.index("段落")], target)
                self.assertIn("见 三值\n亏量定理 一行。", out)
                self.assertIn("[dt]: #\n", out)
                self.assertIn("[跨行\n标签]: #\n", out)
                self.assertIn("标题在下一行\n", out)
                self.assertIn("> 引文\n> 链接\n", out)
                self.assertIn(f"段落\n{mdscan.escape_markdown(GID_MISSING)} 是自动链接，"
                              f"foo]([{mdscan.escape_markdown(GID_DEF)}]({SOURCE_DEF})) 也是。", out)
                self.assertEqual(len(ctx.issues), len(self.STRAYS), ctx.issues)
                self.assertTrue(all("loses its lean: destination" in i for i in ctx.issues))
                self.assertFalse(any("\ue000" in i for i in ctx.issues))

    @unittest.skipUnless(have_pandoc(), "pandoc not installed")
    def test_pandoc_reads_plain_text(self):
        with Repo() as repo:
            write(repo.edition.dir / "ch01.md", self.TEXT)
            repo.model = model.load_edition(repo.edition)
            out, _ = repo.render("ch01.md", target="pandoc")
        html = run_filters(out, "html")
        self.assertNotIn("lean:", html)
        self.assertNotIn('href="[', html)
        self.assertNotIn('href="%5B', html)


# --------------------------------------------------------------------------- indented code


class IndentedCodeTests(unittest.TestCase):
    """Indented code is shown as written by every target and neither checked nor cited: at the top
    level, in a list item (also a nested one), a block quote or a footnote, or indented with a tab."""

    CODE = ("[1]: Knuth, TAOCP.", "[fig]: ../assets/fig.svg", f'<a href="lean:{GID_OK}">x</a>', "[跨行的",
            f"链接](lean:{GID_OK})", f"见 <lean:{GID_MISSING}> 与 [@nope] 与 ![坏](../assets/missing.svg)")

    BLOCKS = (("段落：\n", "    "), ("- 项目\n", "        "), ("- a\n  - b\n", "        "), ("> 引文\n>", ">     "),
              ("脚注[^c]。\n\n[^c]: 正文\n", "        "), ("制表符：\n", "\t"))

    @classmethod
    def text(cls) -> tuple[str, list[str]]:
        parts, code = ["# 第一章\n"], []
        for lead, indent in cls.BLOCKS:
            lines = [indent + line for line in cls.CODE]
            code += lines
            parts.append(lead + "\n" + "\n".join(lines) + "\n\n结束。\n")
        return "\n".join(parts), code

    def test_not_checked(self):
        text, _ = self.text()
        with Repo() as repo:
            write(repo.edition.dir / "ch01.md", text)
            m = model.load_edition(repo.edition)
            self.assertEqual(m.issues, [])
            doc = m.chapters[1]
            self.assertEqual((doc.refs, doc.lean_links), ([], []))
            issues: list[model.Issue] = []
            check.check_links(m, config.load_site(), issues)
            check.check_env_policy(m, issues)
            self.assertEqual(issues, [])

    def test_shown_as_written(self):
        text, code = self.text()
        with Repo() as repo:
            write(repo.edition.dir / "ch01.md", text)
            repo.model = model.load_edition(repo.edition)
            for target in ("mdbook", "pandoc"):
                out, ctx = repo.render("ch01.md", target=target)
                for line in code:
                    self.assertIn("\n" + line + "\n", out, (target, line))
                self.assertEqual(ctx.issues, [], target)


# --------------------------------------------------------------------------- empty destinations


class EmptyDestinationTests(unittest.TestCase):
    """A link or image with an empty destination: HTML (mdBook) links to the page itself or shows a
    broken image, Typst refuses an empty URL and epubcheck an empty image source. PDF/EPUB show its
    text, ``./tbook check`` warns. ``[x]:`` with no destination is text in every target."""

    LINES = ("见 [甲]() 与 ![乙]() 与 [丙](<>) 与 [丁]( )。", "[空址]: <>")

    def test_rendered_as_written_and_reported(self):
        with Repo() as repo:
            for target in ("mdbook", "pandoc"):
                ctx, doc = repo.ctx(target=target), repo.doc("ch01.md")
                for line in self.LINES:
                    self.assertEqual(render.transform_line(line, doc, ctx), line, (target, line))
                self.assertEqual(len(ctx.issues), 5, ctx.issues)
                self.assertTrue(all("empty link destination" in i for i in ctx.issues), ctx.issues)

    def test_check_warns(self):
        with Repo() as repo:
            write(repo.edition.dir / "ch01.md", "# 第一章\n\n" + "\n\n".join(self.LINES) + "\n\n见 [空址]。\n")
            m = model.load_edition(repo.edition)
            issues: list[model.Issue] = []
            check.check_links(m, config.load_site(), issues)
            self.assertEqual([(i.severity, i.line) for i in issues], [("warning", 3)] * 4 + [("warning", 5)])

    LABELS = (
        ("[空]:", "", "\\[空]:"),  # a blank line: no destination
        ("> [q]:  ", ">", "> \\[q]:  "),
        ("- [l]:", "", "- \\[l]:"),
        ("[h]:", "# 标题", "\\[h]:"),  # a heading is no destination
        ("[w]:", "some text here", "\\[w]:"),  # nor are words
        ("[d]:", "  ../assets/fig.svg 'T'", "[d]:"),  # the destination on the next line: a definition
        ("> [e]:", "> <>", "> [e]:"),
    )

    def test_label_without_destination_is_text_for_pandoc(self):
        with Repo() as repo:
            for line, after, want in self.LABELS:
                write(repo.edition.dir / "ch01.md", f"# 第一章\n\n{line}\n{after}\n")
                repo.model = model.load_edition(repo.edition)
                for target in ("mdbook", "pandoc"):
                    out, _ = repo.render("ch01.md", target=target)
                    self.assertEqual(out.split("\n")[2], want if target == "pandoc" else line, (target, line, after))
            write(repo.edition.dir / "ch01.md", "# 第一章\n\n[末]:")
            repo.model = model.load_edition(repo.edition)
            self.assertTrue(repo.render("ch01.md", target="pandoc")[0].endswith("\n\\[末]:"))

    @unittest.skipUnless(have_pandoc(), "pandoc not installed")
    def test_pandoc_shows_the_label_like_mdbook(self):
        with Repo() as repo:
            write(repo.edition.dir / "ch01.md", "# 第一章\n\n[空]:\n\n见 [空]。\n\n> [q]:\n>\n> 见 [q]。\n")
            repo.model = model.load_edition(repo.edition)
            out, _ = repo.render("ch01.md", target="pandoc")
        plain = pandoc_plain(out)
        for text in ("[空]:", "见 [空]。", "[q]:", "见 [q]。"):
            self.assertIn(text, plain)

    @unittest.skipUnless(have_pandoc(), "pandoc not installed")
    def test_filter_turns_them_into_text(self):
        md = "见 [甲]() 与 ![乙]() 与 [丙](<>)。\n\n见 [空址]。\n\n[空址]: <>\n"
        for fmt in ("typst", "html"):
            out = run_filters(md, fmt)
            self.assertNotIn('link("")', out, fmt)
            self.assertNotIn('href=""', out, fmt)
            self.assertNotIn('src=""', out, fmt)
            for text in ("甲", "乙", "丙", "空址"):
                self.assertIn(text, out, fmt)

    @unittest.skipUnless(have_pandoc() and have_typst(), "pandoc or typst not available")
    def test_pdf_builds(self):
        """A real PDF build of a book whose chapter has every form (Typst failed: URL must not be empty)."""
        from tbook import pandoc

        with tempfile.TemporaryDirectory(prefix="tbook-test-empty-") as tmp:
            book = make_book(Path(tmp))
            ed = book.edition("en")
            with (ed.dir / "b.md").open("a", encoding="utf-8") as f:
                f.write("\nSee [a]() and ![b]() and [c](<>).\n\n[x]:\n\nSee [x].\n\n[y]: <>\n\nSee [y].\n")
            out = pandoc.build_pdf(fixture_site(), book, ed, model.load_edition(ed), None, "screen",
                                   Path(tmp) / "book.pdf", stage_dir=Path(tmp) / "stage")
            self.assertTrue(out.read_bytes().startswith(b"%PDF-"))
            main = (Path(tmp) / "stage" / "main.typ").read_text(encoding="utf-8")
            self.assertNotIn('link("")', main)
            self.assertIn("\\[x\\]:", main)


# --------------------------------------------------------------------------- where a definition may begin


class DefinitionStartTests(unittest.TestCase):
    """A link reference definition cannot interrupt a paragraph, in mdBook and in Pandoc: ``para\\n[fig]: a.svg``
    is text (it was rewritten, cited or reported as a definition), and ``<lean:GID>`` after a ``[label]:``
    line that goes on with a paragraph is an autolink (it was reported as a stray and shown as ``[注]: #``).
    Definitions in a row, also after a title over lines, stay definitions."""

    TEXT = (f"# 第一章\n\n"
            f"A12 段落续行：先写一句\n[注]:\n<lean:{GID_OK}>\n\n"  # 3-5
            f"段落\n[fig]: ../assets/fig.svg\n\n"  # 7-8
            f"段落\n    [lt]: lean:{GID_DEF}\n\n"  # 10-11
            f"> 引文\n> [lq]: <lean:{GID_DEF}>\n\n"  # 13-14
            f"[a]: ../assets/fig.svg\n[b]: lean:{GID_OK}\n\n"  # 16-17
            f"[t]: ../assets/fig.svg \"多行\n标题\"\n[c]: lean:{GID_OK}\n\n"  # 19-21
            f"[l]:\n  ../assets/fig.svg\n[m]: lean:{GID_OK}\n")  # 23-25
    CITED = [(5, GID_OK), (14, GID_DEF), (17, GID_OK), (21, GID_OK), (25, GID_OK)]

    def test_roles(self):
        roles = {n: role for n, _, role in mdscan.iter_text(mdscan.parse_blocks(self.TEXT)) if role}
        S, D = mdscan.DEF_START, mdscan.DEF_DEST
        self.assertEqual(roles, {1: S, 2: S, 3: S, 6: S, 7: S, 9: S, 10: S, 12: S, 13: S, 15: S, 16: S, 17: S,
                                 18: S, 19: S, 21: S, 22: S, 23: S, 24: D, 25: S, 26: S})
        self.assertEqual(mdscan.stray_lean_links(self.TEXT.split("\n")), [])

    def test_model_and_check(self):
        with Repo() as repo:
            write(repo.edition.dir / "ch01.md", self.TEXT)
            m = model.load_edition(repo.edition)
            self.assertEqual(m.issues, [])
            self.assertEqual(m.chapters[1].lean_links, self.CITED)
            issues: list[model.Issue] = []
            check.check_links(m, config.load_site(), issues)
            self.assertEqual([(i.line, i.message[:19]) for i in issues], [(24, "'../assets/fig.svg'")])

    def test_render(self):
        with Repo() as repo:
            write(repo.edition.dir / "ch01.md", self.TEXT)
            repo.model = model.load_edition(repo.edition)
            for target in ("mdbook", "pandoc"):
                out, ctx = repo.render("ch01.md", target=target)
                self.assertIn(f"[注]:\n[{mdscan.escape_markdown(GID_OK)}]({SOURCE_OK})\n", out, target)
                self.assertIn("段落\n[fig]: ../assets/fig.svg\n", out, target)
                self.assertIn(f"段落\n    [lt]: lean:{GID_DEF}\n", out, target)
                self.assertIn(f"> 引文\n> [lq]: [{mdscan.escape_markdown(GID_DEF)}]({SOURCE_DEF})\n", out, target)
                self.assertIn(f"[a]: {FIG}\n[b]: {SOURCE_OK}\n", out, target)
                self.assertIn(f"[t]: {FIG} \"多行\n标题\"\n[c]: {SOURCE_OK}\n", out, target)
                self.assertIn(f"[l]:\n  ../assets/fig.svg\n[m]: {SOURCE_OK}\n", out, target)
                self.assertNotIn("#\n", out, target)
                self.assertEqual(len(ctx.issues), 1, ctx.issues)

    @unittest.skipUnless(have_pandoc(), "pandoc not installed")
    def test_pandoc_shows_the_text(self):
        with Repo() as repo:
            write(repo.edition.dir / "ch01.md", self.TEXT)
            repo.model = model.load_edition(repo.edition)
            out, _ = repo.render("ch01.md", target="pandoc")
        plain = pandoc_plain(out)
        for text in ("[注]:", GID_OK, "[fig]: ../assets/fig.svg", f"[lt]: lean:{GID_DEF}", "[lq]:", GID_DEF):
            self.assertIn(text, plain)

    def test_linear(self):
        lines = ["段落"] + [f"[x{k}]: <lean:{GID_OK}>" for k in range(3000)] + [""]
        lines += [f"[d{k}]: lean:{GID_OK}" for k in range(3000)] + [""]
        lines += [f'[t{k}]: a.svg "多行' if k % 2 == 0 else '标题"' for k in range(3000)]
        start = time.perf_counter()
        for node in mdscan.walk(mdscan.parse_blocks("\n".join(lines))):
            if isinstance(node, mdscan.Text):
                mdscan.stray_lean_links(node.lines, node.cont)
                mdscan.text_views(node)
                mdscan.text_roles(node)
        self.assertLess(time.perf_counter() - start, 2.0)


class DefinitionAfterTitleLineTests(unittest.TestCase):
    """Findings: a definition after one whose title stands on the next line, and a definition on a line of an
    HTML block (Pandoc reads Markdown there), were read as text: their ``lean:`` GIDs were not checked, the HTML
    linked ``lean:…`` and ``[1]: Knuth`` vanished from the PDF. A ``[a`b]:`` line whose autolink was rewritten
    crashed check and the build."""

    TEXT = (f"# 第一章\n\n见 [一][t1]、[二][t2]、[三][t3]、[四][t4]。\n\n"
            f"[p]: https://example.com/paper.pdf\n  \"原始论文\"\n[t1]: lean:{GID_OK}\n\n"  # 5-7
            f"[q]:\nhttps://example.com/q\n'标题'\n[t2]: lean:{GID_DEF}\n\n"  # 9-12
            f"> [r]: https://example.com/r\n> (多行\n> 标题)\n> [t3]: lean:{GID_OK}\n\n"  # 14-17
            f"<div class=\"note\">\n[t4]: lean:{GID_OK}\n[1]: Knuth, TAOCP.\n</div>\n\n"  # 19-22
            f"[a`b]: <lean:{GID_OK}>，``c``\n\n"  # 24
            f"[s]: https://example.com/s\n\"标题\" 之后有字\n[u]: lean:{GID_MISSING}\n")  # 26-28
    CITED = [(7, GID_OK), (12, GID_DEF), (17, GID_OK), (20, GID_OK), (24, GID_OK)]

    def test_roles(self):
        S, D = mdscan.DEF_START, mdscan.DEF_DEST
        self.assertEqual(mdscan.definition_roles(['[p]: u', '  "标题"', '[t]: v']), [S, "", S])
        self.assertEqual(mdscan.definition_roles(['[p]:', 'u', "'标题'", '[t]: v']), [S, D, "", S])
        self.assertEqual(mdscan.definition_roles(['> [p]: u', '> (多行', '> 标题)', '> [t]: v']), [S, "", "", S])
        # a title with words after it is none: the definition ends before it, and a paragraph begins
        self.assertEqual(mdscan.definition_roles(['[p]: u', '"标题" 字', '[t]: v']), [S, S, ""])
        scan = mdscan.scan_blocks(['<div>', '[t]: v', '[1]: Knuth', '</div>'])
        self.assertEqual(mdscan.definition_roles(scan.lines, scan.cont), [S] * 4)

    def test_model_and_render(self):
        with Repo() as repo:
            write(repo.edition.dir / "ch01.md", self.TEXT)
            m = model.load_edition(repo.edition)
            self.assertEqual(m.chapters[1].lean_links, self.CITED)
            repo.model = m
            for target in ("mdbook", "pandoc"):
                out, _ = repo.render("ch01.md", target=target)
                self.assertNotIn("lean:", out.replace(f"lean:{GID_MISSING}", ""), target)
                self.assertIn(f"\n[t1]: {SOURCE_OK}\n", out, target)
                self.assertIn(f"\n[t2]: {SOURCE_DEF}\n", out, target)
                self.assertIn(f"\n> [t3]: {SOURCE_OK}\n", out, target)
                self.assertIn(f"\n[t4]: {SOURCE_OK}\n", out, target)
                self.assertIn(f"\\[a`b]: [{mdscan.escape_markdown(GID_OK)}]({SOURCE_OK})，``c``", out, target)
            self.assertIn("\n\\[1]: Knuth, TAOCP.\n", out)  # Pandoc's last: text, as in mdBook

class DefinitionLikeParagraphTests(unittest.TestCase):
    """``[1]: <lean:GID> 文字`` is no definition (words follow the destination, or ``，`` right after the
    ``>``: a plain destination cannot start with ``<``) but a paragraph with an autolink: it was a false
    STRAY_LEAN error (HTML ``[1]: # 文字``) or a definition with ``href="lean:…"``. On two lines too."""

    TEXT = (f"# 第一章\n\n## 参考\n\n[1]: <lean:{GID_OK}> 三值亏量定理\n\n"  # 5
            f"- [2]: <lean:{GID_OK}> 三值亏量定理（列表）\n\n"  # 7
            f"> [3]: <lean:{GID_OK}>，引用中\n\n"  # 9
            f"[4]:\n<lean:{GID_DEF}> 两行\n")  # 11-12
    LINK = f"[{mdscan.escape_markdown(GID_OK)}]({SOURCE_OK})"

    def test_scanners(self):
        lines = self.TEXT.split("\n")
        for k in (4, 6, 8):
            self.assertIsNone(mdscan.refdef(lines[k]), lines[k])
            self.assertEqual(mdscan.lean_link_gids(lines[k]), [GID_OK])
        self.assertEqual(mdscan.stray_lean_links(lines), [])

    def test_model_check_and_render(self):
        with Repo() as repo:
            write(repo.edition.dir / "ch01.md", self.TEXT)
            m = model.load_edition(repo.edition)
            self.assertEqual(m.issues, [])
            self.assertEqual(m.chapters[1].lean_links, [(5, GID_OK), (7, GID_OK), (9, GID_OK), (12, GID_DEF)])
            issues: list[model.Issue] = []
            check.check_links(m, config.load_site(), issues)
            self.assertEqual(issues, [])
            repo.model = m
            for target in ("mdbook", "pandoc"):
                out, ctx = repo.render("ch01.md", target=target)
                self.assertNotIn("lean:", out, target)
                self.assertIn(f"1]: {self.LINK} 三值亏量定理\n", out, target)
                self.assertIn(f"2]: {self.LINK} 三值亏量定理（列表）\n", out, target)
                self.assertIn(f"> \\[3]: {self.LINK}，引用中\n", out, "rewritten, it would be a definition")
                self.assertIn(f"[4]:\n[{mdscan.escape_markdown(GID_DEF)}]({SOURCE_DEF}) 两行", out, target)
                self.assertEqual(ctx.issues, [], target)

    @unittest.skipUnless(MDBOOK and (shutil.which(MDBOOK) or os.path.exists(MDBOOK)), "mdBook needed")
    def test_mdbook_shows_every_line(self):
        with Repo() as repo:
            write(repo.edition.dir / "ch01.md", self.TEXT)
            repo.model = model.load_edition(repo.edition)
            out, _ = repo.render("ch01.md", target="mdbook")
        html = mdbook_html(out)
        for gid, text in ((GID_OK, " 三值亏量定理"), (GID_OK, " 三值亏量定理（列表）"), (GID_OK, "，引用中"),
                          (GID_DEF, " 两行")):
            self.assertIn(f'">{gid}</a>{text}', html)


class DestinationOnTheNextLineTests(unittest.TestCase):
    """A definition whose destination is on the line after its label is a definition for mdBook and Pandoc,
    but the builds do not read it there (its file was neither checked nor staged: a dead HTML link and a
    failing EPUB build while check passed): check and the builds say so. One with a scheme works."""

    TEXT = ("# 第一章\n\n见 [图九][九]、[图十][十] 与 [外][外]。\n\n[九]:\n../assets/fig.svg\n\n"  # 5-6
            "> [十]:\n> ../assets/missing.svg 'T'\n\n[外]:\n  https://example.org/x.svg\n\n"  # 8-9, 11-12
            "[文]:\nIntroduction\n")  # 14-15: a word is a destination too (the EPUB failed on it)

    def test_check_warns(self):
        with Repo() as repo:
            write(repo.edition.dir / "ch01.md", self.TEXT)
            m = model.load_edition(repo.edition)
            self.assertEqual(m.issues, [])
            issues: list[model.Issue] = []
            check.check_links(m, config.load_site(), issues)
            self.assertEqual([(i.severity, i.line) for i in issues], [("warning", 6), ("warning", 9), ("warning", 15)])
            self.assertTrue(issues[0].message.startswith("'../assets/fig.svg' is the destination of the reference "
                                                         "definition whose label ends the line before"), issues[0])
            self.assertIn("'../assets/missing.svg'", issues[1].message)
            self.assertIn("'Introduction'", issues[2].message)
            repo.model = m
            for target in ("mdbook", "pandoc"):
                out, ctx = repo.render("ch01.md", target=target)
                self.assertIn("[九]:\n../assets/fig.svg\n", out, target)
                self.assertEqual(len(ctx.issues), 3, ctx.issues)


# --------------------------------------------------------------------------- formulas over lines


class LabelInFormulaTests(unittest.TestCase):
    """A ``[0,1]:`` line inside a formula over lines goes on with its paragraph: the Pandoc target must not
    escape its ``[`` (``\\[0,1]`` broke the math in PDF/EPUB)."""

    TEXT = ("# 第一章\n\n$$\nf\\colon\n[0,1]:\n\\to \\mathbb{R}\n$$\n\n"
            "L7 行内公式跨行 $x \\in\n[0,1]:\ny$ 结束。\n\n"
            "$$\ng\\colon\n[0,1]: \\to \\mathbb{R}\n$$\n")

    def test_not_escaped(self):
        with Repo() as repo:
            write(repo.edition.dir / "ch01.md", self.TEXT)
            repo.model = model.load_edition(repo.edition)
            for target in ("mdbook", "pandoc"):
                out, ctx = repo.render("ch01.md", target=target)
                self.assertNotIn("\\[0,1]", out, target)
                self.assertEqual(out.count("\n[0,1]:"), 3, target)
                self.assertEqual(ctx.issues, [], target)

    @unittest.skipUnless(have_pandoc(), "pandoc not installed")
    def test_pandoc_reads_math(self):
        from tbook import pandoc

        with Repo() as repo:
            write(repo.edition.dir / "ch01.md", self.TEXT)
            repo.model = model.load_edition(repo.edition)
            out, _ = repo.render("ch01.md", target="pandoc")
        proc = subprocess.run([pandoc.pandoc_path(), "-f", pandoc.READER, "-t", "native"], input=out,
                              capture_output=True, text=True, check=True)
        self.assertEqual(proc.stdout.count("Math DisplayMath"), 2, proc.stdout)
        self.assertEqual(proc.stdout.count("Math InlineMath"), 1, proc.stdout)
        self.assertNotIn("$", pandoc_plain(out))


# --------------------------------------------------------------------------- the PDF/EPUB stager


class StagerLinkTests(unittest.TestCase):
    """The Pandoc stager reads links like the renderer: an image inside a link is still staged, and a
    definition in a block quote or list item is rewritten."""

    def test_image_inside_a_link_and_definitions_in_containers(self):
        from tbook import pandoc

        with Repo() as repo, tempfile.TemporaryDirectory() as tmp:
            write(repo.edition.dir / "img" / "p.png", "png")
            files: set[str] = set()
            linker = pandoc._Linker(Path(tmp), repo.edition, {"ch01.md": "ch-01"}, [], files, online="")
            self.assertEqual(linker.rewrite_line("[![p](img/p.png)](https://example.org (t))", "sub/x.md"),
                             '[![p](img/p.png)](https://example.org "t")', "not an edition file from sub/")
            self.assertEqual(linker.rewrite_line("[![p](img/p.png)](https://example.org)", "ch01.md"),
                             "[![p](_book/zh/img/p.png)](https://example.org)")
            self.assertEqual(linker.rewrite_line("> - [p]: img/p.png 'T'", "ch01.md"), "> - [p]: _book/zh/img/p.png 'T'")
            self.assertEqual(files, {"_book/zh/img/p.png"})


if __name__ == "__main__":
    unittest.main()
