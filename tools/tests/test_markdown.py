"""Regression tests for the Markdown layer: mdscan, summary titles, render links/badges, ledger.

Run: PYTHONPATH=tools python -m unittest discover -s tools/tests -p 'test_markdown.py'

Every test that needs a book builds a throwaway books repository (``Repo``): the
``tbook.paths`` attributes the core reads at call time are patched to point into it, and the
cached ``config.load_site`` / ``config.i18n`` are cleared on entry and exit. The lock is an
in-memory ``lean.Lock``; nothing touches the network, mdBook or Pandoc. The i18n tables are
read from this repository's ``theme/`` (read-only). Nothing here depends on
``books/example-monograph``.
"""

from __future__ import annotations

import os
import tempfile
import textwrap
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest import mock

from tbook import config, lean, ledger, mdscan, model, paths, render, summary

REAL_I18N = paths.THEME / "i18n"
TRU = "the-omega-institute/trureturing"
COMMIT = "c" * 40
GID_OK = "D5/S1/Deficit/DeficitThreeValued.deficit_three_valued"
GID_DEF = "D5/S1/Deficit/DeficitInteger.deficit"
GID_MISSING = "D5/S1/Deficit/DeficitThreeValued.riemann_hypothesis"
MOD_OK = "D5/S1/Deficit/DeficitThreeValued"
MOD_INT = "D5/S1/Deficit/DeficitInteger"
SOURCE_OK = f"https://github.com/{TRU}/blob/{COMMIT}/{MOD_OK}.lean#L12"
SOURCE_DEF = f"https://github.com/{TRU}/blob/{COMMIT}/{MOD_INT}.lean#L7"

SITE = """\
[site]
repo = "acme/books"
languages = ["zh", "en"]

[site.title]
zh = "书库"
en = "Library"

[trureturing]
repo = "the-omega-institute/trureturing"
branch = "dev"
"""

SUMMARY = """\
# Summary

[前言](README.md)

- [第一章](ch01.md)
  - [小节](sub/sec.md)

[附录 A：$\\varphi$-边界 \\[x\\] a\\\\b](appendix/app-a.md)
"""

CHAPTERS = {
    "README.md": """\
        # 前言

        ::: {.definition #def-pre title="前言里的定义"}
        定义。
        :::
        """,
    "ch01.md": f"""\
        # 第一章

        ::: {{.theorem #thm-ok title="关于 $\\varphi^n$ 与 $\\{{-1,0,1\\}}$ 的定理" lean="{GID_OK}"}}
        陈述。
        :::

        ::: {{.theorem #thm-missing title="伪定理" lean="{GID_MISSING}"}}
        不在锁文件中。
        :::

        ::: {{.lemma #lem-def lean="{GID_DEF}"}}
        引用的是 def。
        :::

        ::: {{.corollary #cor-none}}
        没有 Lean 引用。
        :::

        见 [@def-pre]；[前言](README.md)；[锚](README.md#def-pre)；[`rh`](lean:{GID_MISSING})；[`ok`](lean:{GID_OK})。

        > ```markdown
        > 写作 [@thm-ok] 引用定理；图片写 ![x](../assets/fig.svg)
        > ```

        - 列表
            - 嵌套

                ```markdown
                写作 [@thm-ok] 与 [@nope] 引用定理
                ```

        ![引用式][fig]

        ![带空格](<../assets/fig two.svg>)

        ![百分号](../assets/fig%20two.svg)

        [fig]: ../assets/fig.svg "Figure"
        [^note]: ../assets/fig.svg
        """,
    "sub/sec.md": """\
        # 小节

        见 [@def-pre] 与 [前言](../README.md#def-pre)。
        """,
    "appendix/app-a.md": """\
        # 附录 A

        [前言](../README.md)，[@def-pre]，[外部](<https://example.org/a b>)。
        """,
}


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(text), encoding="utf-8")
    return path


def make_lock() -> lean.Lock:
    return lean.Lock(repo=TRU, branch="dev", commit=COMMIT, pinned_at="2026-01-01T00:00:00Z", declarations={
        GID_OK: {"module": MOD_OK, "name": "D5.S1.Deficit.deficit_three_valued", "kind": "theorem",
                 "statement_id": "sha256:3v", "line": 12, "signature": ""},
        GID_DEF: {"module": MOD_INT, "name": "D5.S1.Deficit.deficit", "kind": "def",
                  "statement_id": "sha256:def", "line": 7, "signature": ""},
    })


class Repo:
    """A throwaway books repository with one zh edition; ``tbook.paths`` points into it while active."""

    def __enter__(self) -> "Repo":
        self._tmp = tempfile.TemporaryDirectory(prefix="tbook-md-")
        r = self.root = Path(self._tmp.name)
        self.stack = ExitStack()
        for name, value in dict(ROOT=r, BOOKS=r / "books", BUILD=r / "build", SITE_OUT=r / "_site", CACHE=r / ".cache",
                                SITE_TOML=r / "site.toml", TEMPLATE_TOML=r / "template.toml",
                                LOCK_FILE=r / "trureturing.lock.json", I18N_LOCAL=r / "i18n",
                                I18N_THEME=REAL_I18N).items():
            self.stack.enter_context(mock.patch.object(paths, name, value))
        self.stack.enter_context(mock.patch.dict(os.environ))
        for key in ("TBOOK_REPO", "TBOOK_BASE_URL", "GITHUB_REPOSITORY", "TRURETURING_DIR", "TBOOK_ROOT"):
            os.environ.pop(key, None)
        config.load_site.cache_clear()
        config.i18n.cache_clear()
        self.stack.callback(config.i18n.cache_clear)
        self.stack.callback(config.load_site.cache_clear)
        write(r / "site.toml", SITE)
        bdir = r / "books" / "demo"
        write(bdir / "book.toml", """\
            [book]
            version = "1.0.0"
            editions = ["zh"]

            [book.title]
            zh = "示例"
            """)
        write(bdir / "zh" / "SUMMARY.md", SUMMARY)
        for rel, text in CHAPTERS.items():
            write(bdir / "zh" / rel, text)
        write(bdir / "assets" / "fig.svg", "<svg xmlns='http://www.w3.org/2000/svg'/>")
        write(bdir / "assets" / "fig two.svg", "<svg xmlns='http://www.w3.org/2000/svg'/>")
        self.book = config.load_book("demo")
        self.edition = self.book.primary
        self.model = model.load_edition(self.edition)
        return self

    def __exit__(self, *exc) -> None:
        self.stack.close()
        self._tmp.cleanup()

    def ctx(self, target: str = "mdbook", lock: lean.Lock | None | str = "default") -> render.RenderContext:
        return render.RenderContext(site=config.load_site(), book=self.book, edition=self.edition, model=self.model,
                                    lock=make_lock() if lock == "default" else lock, target=target,
                                    env_href=render.mdbook_env_href(self.model) if target == "mdbook" else None)

    def doc(self, path: str) -> model.ChapterDoc:
        return next(d for d in self.model.chapters if d.chapter.path == path)

    def render(self, path: str, target: str = "mdbook", lock: lean.Lock | None | str = "default"):
        ctx = self.ctx(target, lock)
        return render.chapter_markdown(self.doc(path), ctx), ctx

    @property
    def assets(self) -> Path:
        return (self.root / "books" / "demo" / "assets").resolve()


# --------------------------------------------------------------------------- finding 1: TeX in titles


class TitleBackslashTests(unittest.TestCase):
    """Regression: attribute and SUMMARY titles lost every backslash (``$\\varphi$`` → ``$varphi$``)."""

    def test_parse_attrs_keeps_tex(self):
        a = mdscan.parse_attrs(r'''.theorem #thm-x title="关于 $\varphi$ 与 $\{-1,0,1\}$"''')
        self.assertEqual(a.kv["title"], r"关于 $\varphi$ 与 $\{-1,0,1\}$")

    def test_parse_attrs_unescapes_only_quoting(self):
        a = mdscan.parse_attrs(r'''title="say \"hi\" a\\b \alpha" note='it\'s \le' bare=x\y''')
        self.assertEqual(a.kv, {"title": 'say "hi" a\\b \\alpha', "note": "it's \\le", "bare": "x\\y"})
        again = mdscan.parse_attrs(a.to_pandoc()[1:-1])
        self.assertEqual(again.kv, a.kv, "to_pandoc round-trips backslashes")

    def test_div_title_may_contain_braces(self):
        issues: list[mdscan.ScanIssue] = []
        blocks = mdscan.parse_blocks('::: {.theorem #t title="$\\mathbb{N}$ 上 {x}" lean="A/B.c"}\nbody\n:::\n', issues)
        self.assertEqual(issues, [])
        div = blocks[0]
        self.assertIsInstance(div, mdscan.Div)
        self.assertEqual((div.attrs.id, div.attrs.get("title"), div.attrs.get("lean")),
                         ("t", "$\\mathbb{N}$ 上 {x}", "A/B.c"))
        self.assertEqual(div.end, 3)

    def test_unparseable_div_opener_is_reported(self):
        issues: list[mdscan.ScanIssue] = []
        blocks = mdscan.parse_blocks('::: {.theorem #t title="unterminated}\nbody\n:::\n', issues)
        self.assertEqual([i.line for i in issues], [1])
        self.assertIn("cannot parse", issues[0].message)
        self.assertFalse(any(isinstance(b, mdscan.Div) for b in blocks))

    def test_summary_titles_keep_tex(self):
        self.assertEqual(summary._unescape(r"附录 B：$\varphi$-边界 \[x\] a\\b \{"), r"附录 B：$\varphi$-边界 [x] a\b \{")
        with Repo() as repo:
            app = repo.model.summary.chapters[-1]
            self.assertEqual(app.title, "附录 A：$\\varphi$-边界 [x] a\\b")

    def test_env_title_reaches_every_target(self):
        title = "关于 $\\varphi^n$ 与 $\\{-1,0,1\\}$ 的定理"
        with Repo() as repo:
            self.assertEqual(repo.model.envs["thm-ok"].title, title)
            html_out, _ = repo.render("ch01.md")
            self.assertIn('<span class="tr-env-title">（关于 $\\varphi^n$ 与 $\\{-1,0,1\\}$ 的定理）</span>', html_out)
            pandoc_out, _ = repo.render("ch01.md", target="pandoc")
            first = next(line for line in pandoc_out.splitlines() if line.startswith(":::::: {#thm-ok"))
            self.assertEqual(mdscan.parse_attrs(first[len(":::::: {"):-1]).kv["tr-title"], title)
            self.assertIn(f"| {title} |", ledger.ledger_markdown(repo.model, make_lock()))


# --------------------------------------------------------------------------- finding 13: README → index


class ReadmeLinkTests(unittest.TestCase):
    """Regression: links and [@id] into the README.md preface pointed to README.html (mdBook writes index.html)."""

    def test_mdbook_chapter_path(self):
        self.assertEqual(render.mdbook_chapter_path("README.md"), "index.md")
        self.assertEqual(render.mdbook_chapter_path("part/Readme.md"), "part/index.md")
        self.assertEqual(render.mdbook_chapter_path("ch01.md"), "ch01.md")
        self.assertEqual(render.mdbook_chapter_path("readme-notes.md"), "readme-notes.md")

    def test_mdbook_links_into_readme(self):
        with Repo() as repo:
            ch01, ctx = repo.render("ch01.md")
            self.assertIn("见 [定义0.1](index.md#def-pre)；[前言](index.md)；[锚](index.md#def-pre)", ch01)
            sec, _ = repo.render("sub/sec.md")
            self.assertIn("见 [定义0.1](../index.md#def-pre) 与 [前言](../index.md#def-pre)。", sec)
            app, _ = repo.render("appendix/app-a.md")
            self.assertIn("[前言](../index.md)，[定义0.1](../index.md#def-pre)", app)
            self.assertEqual(ctx.issues, [])

    def test_pandoc_links_into_readme_unchanged(self):
        with Repo() as repo:
            ch01, _ = repo.render("ch01.md", target="pandoc")
            self.assertIn("见 [定义0.1](#def-pre)；[前言](README.md)；[锚](README.md#def-pre)", ch01,
                          "the Pandoc linker maps chapter files to ids itself")

    def test_readme_that_is_not_a_chapter_is_left_alone(self):
        with Repo() as repo:
            write(repo.edition.dir / "notes" / "README.md", "# notes\n")
            out = render.transform_line("[n](notes/README.md)", repo.doc("ch01.md"), repo.ctx())
            self.assertEqual(out, "[n](notes/README.md)")


# --------------------------------------------------------------------------- finding 18: asset link forms


class AssetLinkFormTests(unittest.TestCase):
    """Regression: reference-style and ``<…>`` asset links were never rewritten into ``_book/``."""

    def test_reference_definition_angle_and_percent_forms(self):
        with Repo() as repo:
            out, ctx = repo.render("ch01.md")
            self.assertIn('[fig]: _book/assets/fig.svg "Figure"', out)
            self.assertIn("![带空格](_book/assets/fig%20two.svg)", out)
            self.assertIn("![百分号](_book/assets/fig%20two.svg)", out)
            self.assertIn("[^note]: ../assets/fig.svg", out, "footnotes are not reference definitions")
            self.assertEqual(ctx.book_files, {repo.assets / "fig.svg", repo.assets / "fig two.svg"})
            self.assertEqual(ctx.issues, [])

    def test_nested_chapter_and_pandoc_target(self):
        with Repo() as repo:
            doc = repo.doc("sub/sec.md")
            ctx = repo.ctx(target="pandoc")
            self.assertEqual(render.transform_line("[f]: <../../assets/fig two.svg>", doc, ctx),
                             "[f]: ../_book/assets/fig%20two.svg")
            self.assertEqual(render.transform_line("![a](<../../assets/fig two.svg> \"T\")", doc, ctx),
                             '![a](../_book/assets/fig%20two.svg "T")')
            self.assertEqual(ctx.book_files, {repo.assets / "fig two.svg"})

    def test_other_angle_destinations_become_plain(self):
        with Repo() as repo:
            app, ctx = repo.render("appendix/app-a.md")
            self.assertIn("[外部](https://example.org/a%20b)", app)
            out = render.transform_line("[x](<ch01.md#thm-ok>) [y](plain.md)", repo.doc("ch01.md"), ctx)
            self.assertEqual(out, "[x](ch01.md#thm-ok) [y](plain.md)")

    def test_link_leaving_the_book_is_reported(self):
        with Repo() as repo:
            ctx = repo.ctx()
            out = render.transform_line("[o]: <../../../out side.png>", repo.doc("ch01.md"), ctx)
            self.assertEqual(out, "[o]: ../../../out%20side.png")
            self.assertTrue(any("link leaves the book directory" in i for i in ctx.issues), ctx.issues)


# --------------------------------------------------------------------------- finding 20: fences in containers


class ContainerFenceTests(unittest.TestCase):
    """Regression: fences inside block quotes or nested list items were treated as prose."""

    def test_quote_and_list_fences_are_code(self):
        text = textwrap.dedent("""\
            > ```markdown
            > [@a] ![x](../assets/fig.svg)
            > ```

            - item
                - nested

                    ~~~
                    [@b]
                    ~~~

            after [@c]
            """)
        blocks = mdscan.parse_blocks(text)
        codes = [b for b in blocks if isinstance(b, mdscan.Code)]
        self.assertEqual([c.lines[1].strip() for c in codes], ["> [@a] ![x](../assets/fig.svg)", "[@b]"])
        self.assertEqual([line for _, line in mdscan.iter_text_lines(blocks) if "[@" in line], ["after [@c]"])

    def test_fences_shown_inside_a_code_example_do_not_close_it(self):
        text = textwrap.dedent("""\
            ```markdown
            > ```
            > # quoted [@x]
            > ```

                ```
                code [@y]
                ```
            ```
            after [@z]
            """)
        blocks = mdscan.parse_blocks(text)
        self.assertIsInstance(blocks[0], mdscan.Code)
        self.assertEqual(len(blocks[0].lines), 9)
        self.assertEqual([line for _, line in mdscan.iter_text_lines(blocks) if line], ["after [@z]"])

    def test_unclosed_container_fence_ends_with_its_container(self):
        text = "> ```\n> code [@a]\n\nprose [@b]\n\n- a\n    - b\n\n        ```\n        code [@c]\nprose [@d]\n"
        blocks = mdscan.parse_blocks(text)
        prose = [line for _, line in mdscan.iter_text_lines(blocks) if "[@" in line]
        self.assertEqual(prose, ["prose [@b]", "prose [@d]"])
        mask = mdscan.fenced_code_lines(text.split("\n"))
        code = {line for line, hidden in zip(text.split("\n"), mask) if hidden}
        self.assertEqual(code, {"> ```", "> code [@a]", "        ```", "        code [@c]"},
                         "fenced_code_lines agrees with parse_blocks")

    def test_inline_triple_backticks_are_not_a_fence(self):
        blocks = mdscan.parse_blocks("```x``` is inline code\n[@a]\n")
        self.assertEqual([type(b).__name__ for b in blocks], ["Text"])
        self.assertIsNone(mdscan.FENCE_RE.match("```x``` y"))
        self.assertIsNotNone(mdscan.FENCE_RE.match("```python title=x"))
        self.assertIsNone(mdscan.FENCE_RE.match("> ```"), "FENCE_RE stays top-level only")

    def test_render_and_model_leave_fence_contents_alone(self):
        with Repo() as repo:
            doc = repo.doc("ch01.md")
            self.assertNotIn("nope", [ref for _, ref in doc.refs], "no check error for refs inside code")
            out, ctx = repo.render("ch01.md")
            self.assertIn("> 写作 [@thm-ok] 引用定理；图片写 ![x](../assets/fig.svg)", out)
            self.assertIn("        写作 [@thm-ok] 与 [@nope] 引用定理", out)
            self.assertFalse(any("nope" in i for i in ctx.issues), ctx.issues)


# --------------------------------------------------------------------------- finding 33: no unbacked LEAN badge


class UnverifiedBadgeTests(unittest.TestCase):
    """Regression: the green LEAN ✓ badge and ledger links were shown for GIDs the lock does not resolve."""

    def test_env_view(self):
        with Repo() as repo:
            ctx = repo.ctx()
            ok = render.env_view(repo.model.envs["thm-ok"], ctx)
            self.assertEqual((ok["badge"], ok["status"], ok["unverified"]), ("LEAN ✓", "lean", False))
            for env_id in ("thm-missing", "lem-def", "cor-none"):
                view = render.env_view(repo.model.envs[env_id], ctx)
                self.assertEqual((view["badge"], view["status"], view["unverified"]), ("UNVERIFIED", "open", True),
                                 env_id)
            bare = render.env_view(repo.model.envs["thm-ok"], repo.ctx(lock=None))
            self.assertEqual((bare["badge"], bare["unverified"]), ("UNVERIFIED", True), "no lock, no verification")
            missing = render.lean_view(GID_MISSING, make_lock())
            self.assertEqual((missing["resolved"], missing["url"], missing["state_url"]), (False, "", ""))

    def test_mdbook_markup(self):
        with Repo() as repo:
            out, _ = repo.render("ch01.md")
            self.assertIn(f'<a class="tr-badge tr-badge-lean" href="{SOURCE_OK}"', out)
            self.assertEqual(out.count("tr-badge-lean"), 1, "only the resolved theorem is green")
            self.assertIn('<section class="tr-env tr-theorem tr-status-open tr-unverified" id="thm-missing"', out)
            self.assertIn('<span class="tr-badge tr-badge-open tr-badge-unverified" title="', out)
            self.assertIn(f'<code class="tr-lean-decl tr-lean-unresolved" title="{GID_MISSING}">', out)
            self.assertNotIn(f'href="https://github.com/{TRU}/blob/{COMMIT}/{MOD_OK}.lean"', out,
                             "no source link for the unresolved declaration")
            self.assertIn(f'<a class="tr-lean-decl" href="{SOURCE_DEF}"', out, "a locked def still links")
            self.assertIn(f"；`rh`；[`ok`]({SOURCE_OK})。", out, "an unresolved lean: link keeps only its text")

    def test_pandoc_attributes(self):
        with Repo() as repo:
            out, _ = repo.render("ch01.md", target="pandoc")
            first = next(line for line in out.splitlines() if line.startswith(":::::: {#thm-missing"))
            kv = mdscan.parse_attrs(first[len(":::::: {"):-1]).kv
            self.assertEqual((kv["tr-status"], kv["tr-badge"], kv["tr-lean-url"]), ("open", "UNVERIFIED", "-"))

    def test_ledger(self):
        with Repo() as repo:
            text = ledger.ledger_markdown(repo.model, make_lock())
            rows = {line.split("|")[1].strip(): line for line in text.splitlines() if line.startswith("| [")}
            self.assertIn(f"[`D5.S1.Deficit.deficit_three_valued`]({SOURCE_OK})", rows["[定理1.1](#thm-ok)"])
            self.assertIn("[`3v`]", rows["[定理1.1](#thm-ok)"])
            self.assertIn(f"| `{GID_MISSING}` | **UNVERIFIED** |", rows["[定理1.2](#thm-missing)"])
            self.assertIn(f"[`D5.S1.Deficit.deficit`]({SOURCE_DEF}) | **UNVERIFIED** |", rows["[引理1.3](#lem-def)"])
            self.assertIn("| **UNVERIFIED** |", rows["[推论1.4](#cor-none)"])
            bare = ledger.ledger_markdown(repo.model, None)
            self.assertNotIn("https://github.com", bare)
            self.assertEqual(bare.count("**UNVERIFIED**"), 4)


if __name__ == "__main__":
    unittest.main()
