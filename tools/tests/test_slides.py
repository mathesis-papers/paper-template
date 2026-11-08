"""Tests for tbook.slides (run: PYTHONPATH=tools python -m unittest discover -s tools/tests -p 'test_slides.py').

Most tests are pure Python. Tests that compare with Slidev's own parser, run tools/node/slides-*.mjs or
scaffold a deck need Node and node_modules (``npm ci``) and are skipped otherwise; the end-to-end
``cli new`` test also needs the trureturing checkout ($TRURETURING_DIR or ../trureturing) for
``./tbook check --offline``. Tests on books/example-monograph skip when a books repository has removed
it; the others use scratch books and a fake lock.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from tbook import config, lean, paths, slides

ROOT = paths.ROOT
EXAMPLE = paths.BOOKS / "example-monograph"
DECK = EXAMPLE / "slides" / "overview"
HAVE_EXAMPLE = (DECK / "slides.md").is_file()
needs_example = unittest.skipUnless(HAVE_EXAMPLE, "books/example-monograph (with its overview deck) is not in this repository")
NODE = shutil.which("node")
HAVE_NODE = bool(NODE) and (ROOT / "node_modules" / "@slidev" / "parser").is_dir()
HAVE_UNO = HAVE_NODE and (ROOT / "node_modules" / "unocss").is_dir()
GID_3V = "D5/S1/Deficit/DeficitThreeValued.deficit_three_valued"
GID_INT = "D5/S1/Deficit/DeficitInteger.deficit_integer"
GID_DEF = "D5/S1/Deficit/DeficitInteger.deficit"

# A fake lock for the scratch-book tests: one Lean theorem, one Lean def.
FAKE_THM = "D5/S1/Fake/FakeModule.fake_theorem"
FAKE_DEF = "D5/S1/Fake/FakeModule.fake_def"
FAKE_DECLS = {gid: {"module": "D5/S1/Fake/FakeModule", "name": f"D5.S1.Fake.{gid.rsplit('.', 1)[1]}", "kind": kind,
                    "statement_id": "sha256:0", "line": 1, "signature": ""}
              for gid, kind in ((FAKE_THM, "theorem"), (FAKE_DEF, "def"))}


def fake_lock() -> lean.Lock:
    return lean.Lock(repo="o/trureturing", branch="dev", commit="0" * 40, declarations=dict(FAKE_DECLS))


def make_book(parent: Path, slug: str, editions: list[str]) -> config.Book:
    """A minimal book (book.toml only) at parent/slug."""
    bdir = parent / slug
    bdir.mkdir(parents=True)
    titles = "\n".join(f'{lang} = "Book {lang}"' for lang in editions)
    (bdir / "book.toml").write_text(f'[book]\nversion = "0.1.0"\neditions = {json.dumps(editions)}\ncode = "S//B"\n\n'
                                    f"[book.title]\n{titles}\n", encoding="utf-8")
    return config.load_book(bdir)


def fake_build(book: config.Book, out: Path, *, deck: str = "d1", pdfs: tuple[str, ...] = ()) -> Path:
    """A fake slides build (build/slides/<slug>/ layout and manifest) of `deck`; PDFs only for `pdfs`."""
    base = slides.base_path(config.load_site())
    langs = {}
    for lang in book.languages:
        (out / deck / lang).mkdir(parents=True)
        (out / deck / lang / "index.html").write_text(f"<title>{lang}</title>", encoding="utf-8")
        pdf = slides.build_pdf_name(deck, lang) if lang in pdfs else ""
        if pdf:
            (out / pdf).write_bytes(b"%PDF-1.7 fake")
        langs[lang] = {"dir": f"{deck}/{lang}/", "site_path": slides.site_path(book, deck, lang), "base": base,
                       "pdf": pdf, "pdf_name": slides.pdf_name(book, deck, lang)}
    (out / "manifest.json").write_text(json.dumps({"schema": slides.MANIFEST_SCHEMA, "base": base,
                                                   "decks": {deck: {"langs": langs}}}), encoding="utf-8")
    return out


def deck_head(theme: str, lang: str, **over) -> str:
    """Headmatter of a valid one-slide edition in `lang` (cover layout)."""
    fields = {"theme": theme, "title": f'"T {lang}"', "bcp": f'"{config.bcp47(lang)}"', "version": '"0.1.0"'}
    fields.update(over)
    return (f"---\ntheme: {fields['theme']}\ntitle: {fields['title']}\nhtmlAttrs:\n  lang: {fields['bcp']}\n"
            f"deck:\n  code: \"G//O\"\n  title: \"t\"\n  version: {fields['version']}\nlayout: cover\n---\n\n# cover\n")


def node_parse(text: str) -> list[dict]:
    """Slides of `text` according to @slidev/parser (frontmatter and content of every slide)."""
    script = (
        "import { parseSync } from '@slidev/parser';"
        "import { readFileSync } from 'node:fs';"
        "const md = readFileSync(0, 'utf8');"
        "const out = parseSync(md, 'x.md').slides.map(s => ({ frontmatter: s.frontmatter ?? {}, content: s.content, start: s.start }));"
        "process.stdout.write(JSON.stringify(out));"
    )
    r = subprocess.run([NODE, "--input-type=module", "-e", script], input=text, capture_output=True, text=True,
                       cwd=ROOT, check=True)
    return json.loads(r.stdout)


TRICKY = """---
theme: x
title: "A: b # not a comment"
deck:
  code: 'G//O'
  list: [a, "b, c", 3]
---

# one

```md
---
not a separator
---
```

---
layout: section
chapter: "01"
hide: false
---

<!--
---
in a comment
-->
two

----

three (after a ---- line: no frontmatter)

---

four
<!-- speaker notes -->

---

```yaml
layout: cover
```

five
"""


class SplitTest(unittest.TestCase):
    def test_tricky_counts_and_frontmatter(self):
        got = slides.split_slides(TRICKY)
        self.assertEqual(len(got), 5)
        self.assertEqual(got[0].frontmatter["title"], "A: b # not a comment")
        self.assertEqual(got[0].frontmatter["deck"], {"code": "G//O", "list": ["a", "b, c", 3]})
        self.assertEqual(got[1].frontmatter, {"layout": "section", "chapter": "01", "hide": False})
        self.assertEqual(got[4].frontmatter, {"layout": "cover"})
        self.assertEqual(got[3].content, "four")  # trailing comment = notes

    def test_hidden_slides_are_not_counted(self):
        text = "---\ntitle: t\n---\n\na\n\n---\nhide: true\n---\n\nb\n\n---\n\nc\n"
        self.assertEqual(len(slides.split_slides(text)), 3)
        self.assertEqual(slides.count_slides(text), 2)

    @unittest.skipUnless(HAVE_NODE, "node and node_modules/@slidev/parser needed")
    def test_matches_slidev_parser(self):
        texts = [TRICKY] + [p.read_text(encoding="utf-8").replace("{{THEME}}", "x")
                            for p in sorted((ROOT / "templates" / "slides").glob("slides*.md"))]
        if HAVE_EXAMPLE:
            texts += [(DECK / "slides.md").read_text(encoding="utf-8"), (DECK / "slides.en.md").read_text(encoding="utf-8")]
        for text in texts:
            mine = slides.split_slides(text)
            theirs = node_parse(text)
            self.assertEqual(len(mine), len(theirs))
            for a, b in zip(mine, theirs):
                self.assertEqual(a.frontmatter, b["frontmatter"])
                self.assertEqual(a.content, b["content"].strip())
                self.assertEqual(a.line, b["start"] + 1)


class YamlTest(unittest.TestCase):
    def test_subset(self):
        doc = slides.parse_yaml(
            "# comment\n"
            "a: 1\n"
            "b: 2.5\n"
            "c: true\n"
            "d: ~\n"
            "e: \"x\\\"y\\u00e9\"\n"
            "f: 'it''s'\n"
            "g: plain text # trailing comment\n"
            "h:\n"
            "  i: deep\n"
            "  j:\n"
            "    - one\n"
            "    - two: 2\n"
            "      three: 3\n"
            "k: |\n"
            "  line 1\n"
            "  line 2\n"
            "l: [1, 'b', \"c, d\"]\n"
            "m: {x: 1, y: z}\n"
        )
        self.assertEqual(doc["a"], 1)
        self.assertEqual(doc["b"], 2.5)
        self.assertIs(doc["c"], True)
        self.assertIsNone(doc["d"])
        self.assertEqual(doc["e"], 'x"yé')
        self.assertEqual(doc["f"], "it's")
        self.assertEqual(doc["g"], "plain text")
        self.assertEqual(doc["h"], {"i": "deep", "j": ["one", {"two": 2, "three": 3}]})
        self.assertEqual(doc["k"], "line 1\nline 2\n")
        self.assertEqual(doc["l"], [1, "b", "c, d"])
        self.assertEqual(doc["m"], {"x": 1, "y": "z"})

    def test_errors(self):
        with self.assertRaises(slides.YamlError):
            slides.parse_yaml('a: "unterminated\n')
        with self.assertRaises(slides.YamlError):
            slides.parse_yaml("a: 1\n   b: 2\n")


class ConventionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="tbook-slides-conv-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_files_and_paths(self):
        book = make_book(self.tmp, "zh-first", ["zh", "en", "ja"])
        self.assertEqual(slides.edition_file(book, "zh"), "slides.md")
        self.assertEqual(slides.edition_file(book, "en"), "slides.en.md")
        self.assertEqual(slides.edition_file(book, "ja"), "slides.ja.md")
        self.assertEqual(slides.lang_of_file(book, "slides.md"), "zh")
        self.assertEqual(slides.lang_of_file(book, "slides.en.md"), "en")
        self.assertIsNone(slides.lang_of_file(book, "notes.md"))
        self.assertEqual(slides.site_path(book, "overview", "zh"), "overview/")
        self.assertEqual(slides.site_path(book, "overview", "en"), "overview/en/")
        self.assertEqual(slides.build_pdf_name("overview", "en"), "overview-en.pdf")
        self.assertEqual(slides.pdf_name(book, "overview", "zh"), "zh-first-overview-zh.pdf")
        self.assertEqual(slides.theme_ref(paths.BOOKS / "any-book" / "slides" / "overview"), "../../../../theme/slides")

    def test_first_language_owns_slides_md(self):
        """slides.md is the book's first language, whichever it is; slides.<first>.md is no edition."""
        zh_first = make_book(self.tmp, "zh-first", ["zh", "en"])
        en_first = make_book(self.tmp, "en-first", ["en", "zh"])
        self.assertIsNone(slides.lang_of_file(zh_first, "slides.zh.md"))
        self.assertEqual(slides.edition_file(en_first, "en"), "slides.md")
        self.assertEqual(slides.edition_file(en_first, "zh"), "slides.zh.md")
        self.assertEqual(slides.lang_of_file(en_first, "slides.md"), "en")
        self.assertEqual(slides.lang_of_file(en_first, "slides.zh.md"), "zh")
        self.assertIsNone(slides.lang_of_file(en_first, "slides.en.md"))
        self.assertEqual(slides.site_path(en_first, "overview", "en"), "overview/")
        self.assertEqual(slides.site_path(en_first, "overview", "zh"), "overview/zh/")

    def test_base_path(self):
        site = config.load_site()
        for url, want in [("", "/"), ("https://o.github.io/", "/"), ("https://o.github.io/books/", "/books/"),
                          ("https://o.github.io/books", "/books/"), ("https://example.org/a/b/", "/a/b/")]:
            with mock.patch.object(site, "base_url", url):
                self.assertEqual(slides.base_path(site), want)

    def test_strings_fall_back_to_local_table(self):
        self.assertEqual(slides.t("zh", "pages", n=10), "10 页")
        self.assertEqual(slides.t("en", "pages", n=10), "10 slides")
        self.assertEqual(slides.t("fr", "present"), "Present online")


@needs_example
class ExampleDeckTest(unittest.TestCase):
    def setUp(self):
        self.book = config.load_book("example-monograph")

    def test_page_for_page(self):
        zh = slides.read_edition(self.book, "overview", "zh")
        en = slides.read_edition(self.book, "overview", "en")
        self.assertEqual(zh.count, en.count)
        self.assertTrue(8 <= zh.count <= 10)
        self.assertEqual(zh.head["htmlAttrs"]["lang"], "zh-CN")
        self.assertEqual(en.head["htmlAttrs"]["lang"], "en")
        self.assertEqual(zh.meta["code"], self.book.code)

    def test_check_passes(self):
        self.assertEqual([i.format() for i in slides.check(self.book)], [])

    def test_cited_gids_are_locked(self):
        lock = lean.Lock.load()
        gids = {g for _, _, g in slides.cited_gids(self.book)}
        self.assertIn(GID_3V, gids)
        self.assertIn("D5/S0/Certificates/GreathouseLogTwoFloorRefutation.result", gids)
        self.assertIn("D5/S3/ConceptDynamics/Restoration/TargetRecoveryCriterion.target_recovery_criterion", gids)
        for g in gids:
            self.assertIsNotNone(lock.get(g), g)

    def test_items(self):
        (it,) = slides.items(self.book)
        self.assertEqual(it["id"], "overview")
        self.assertEqual(it["languages"], ["zh", "en"])
        self.assertEqual(it["href"], {"zh": "slides/overview/", "en": "slides/overview/en/"})
        self.assertEqual(it["pdf"]["en"], "slides/overview/example-monograph-overview-en.pdf")
        self.assertEqual(it["title"], {"zh": "概览", "en": "Overview"})
        self.assertEqual(it["slides"], slides.read_edition(self.book, "overview", "zh").count)

    def test_check_ref(self):
        self.assertIsNone(slides.check_ref(self.book, "overview"))
        self.assertIn("not found", slides.check_ref(self.book, "missing-deck"))
        self.assertIn("kebab-case", slides.check_ref(self.book, "../x"))
        self.assertIn("src", slides.check_ref(self.book, ""))


def _ctx(book, lang, target):
    site = config.load_site()
    return SimpleNamespace(site=site, book=book, edition=book.edition(lang), lang=lang, target=target,
                           issues=[], book_files=set(), book_prefix="_book")


@needs_example
class EmbedTest(unittest.TestCase):
    def setUp(self):
        self.book = config.load_book("example-monograph")
        self.env = SimpleNamespace(attrs={"src": "overview"}, kind="slides")

    def test_mdbook_card(self):
        for chapter, up in [("ch02-refutation-observation.md", "../"), ("part/ch.md", "../../")]:
            doc = SimpleNamespace(path=Path("x.md"), chapter=SimpleNamespace(path=chapter))
            out = slides.render_embed(self.env, _ctx(self.book, "en", "mdbook"), "A caption.", doc)
            self.assertIn('<aside class="tr-media tr-slides"', out)
            self.assertIn(f'href="{up}slides/overview/en/"', out)
            self.assertIn(f'href="{up}slides/overview/example-monograph-overview-en.pdf"', out)
            self.assertIn("\n\nA caption.\n\n", out)  # Markdown inside HTML needs blank lines
            self.assertIn("Present online", out)
        zh = slides.render_embed(self.env, _ctx(self.book, "zh", "mdbook"), "",
                                 SimpleNamespace(path=Path("x.md"), chapter=SimpleNamespace(path="ch01.md")))
        self.assertIn('href="../slides/overview/"', zh)
        self.assertIn("在线演示", zh)

    def test_pandoc_block(self):
        ctx = _ctx(self.book, "zh", "pandoc")
        doc = SimpleNamespace(path=Path("x.md"), chapter=SimpleNamespace(path="ch01.md"))
        with mock.patch.object(ctx.site, "base_url", "https://o.github.io/books/"):
            out = slides.render_embed(self.env, ctx, "图注。", doc)
        self.assertTrue(out.startswith("::: {.tr-media .tr-slides}"))
        self.assertIn("<https://o.github.io/books/example-monograph/slides/overview/>", out)
        self.assertIn("图注。", out)
        self.assertTrue(out.rstrip().endswith(":::"))
        with mock.patch.object(ctx.site, "base_url", ""):
            out = slides.render_embed(self.env, _ctx(self.book, "en", "pandoc"), "", doc)
        self.assertIn("`example-monograph/slides/overview/en/`", out)

    def test_unknown_deck_reports(self):
        ctx = _ctx(self.book, "zh", "mdbook")
        doc = SimpleNamespace(path=Path("x.md"), chapter=SimpleNamespace(path="ch01.md"))
        out = slides.render_embed(SimpleNamespace(attrs={"src": "nope"}), ctx, "", doc)
        self.assertIn("tr-slides", out)
        self.assertTrue(ctx.issues)


@needs_example
class BrokenDeckTest(unittest.TestCase):
    """check() on a scratch copy of the example book with deliberately broken decks."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="tbook-slides-"))
        self.bdir = self.tmp / "scratch-book"
        shutil.copytree(EXAMPLE, self.bdir, ignore=shutil.ignore_patterns("slides", "viz", "films"))
        self.deck = self.bdir / "slides" / "d1"
        self.deck.mkdir(parents=True)
        self.theme = slides.theme_ref(self.deck)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def head(self, lang: str, **over) -> str:
        bcp = {"zh": "zh-CN", "en": "en"}[lang]
        fields = {"theme": self.theme, "title": f'"T {lang}"', "bcp": f'"{bcp}"', "version": '"0.1.0"'}
        fields.update(over)
        return (f"---\ntheme: {fields['theme']}\ntitle: {fields['title']}\nhtmlAttrs:\n  lang: {fields['bcp']}\n"
                f"deck:\n  code: \"G//O\"\n  title: \"t\"\n  version: {fields['version']}\nlayout: cover\n---\n\n# cover\n")

    def write(self, lang: str, text: str) -> None:
        (self.deck / slides.edition_file(config.load_book(self.bdir), lang)).write_text(text, encoding="utf-8")

    def issues(self) -> list[str]:
        return [i.message for i in slides.check(config.load_book(self.bdir))]

    def test_good_scratch_deck(self):
        body = f'\n---\nsection: "s"\n---\n\n<TheoremCard label="{{label}}" gid="{GID_3V}" cite="thm-deficit-three-valued">\n\nx\n\n</TheoremCard>\n'
        self.write("zh", self.head("zh") + body.replace("{label}", "定理1.3"))
        self.write("en", self.head("en") + body.replace("{label}", "Theorem 1.3"))
        self.assertEqual(self.issues(), [])

    def test_missing_edition_and_bad_headmatter(self):
        self.write("zh", self.head("zh", theme="../theme/slides", bcp='"zh"', title='"a <b>"'))
        msgs = "\n".join(self.issues())
        self.assertIn("has no slides.en.md", msgs)
        self.assertIn("theme:", msgs)
        self.assertIn('htmlAttrs.lang: "zh-CN"', msgs)
        self.assertIn("must not contain <", msgs)

    def test_parity_and_citations(self):
        self.write("zh", self.head("zh") + f'\n---\n\n<LeanBadge gid="{GID_3V}" />\n\n---\n\nthree\n')
        self.write("en", self.head("en", version='"0.2.0"') + f'\n---\nlayout: section\n---\n\n<LeanBadge gid="{GID_INT}" />\n')
        msgs = "\n".join(self.issues())
        self.assertIn("2 slides, but", msgs)
        self.assertIn("deck.version", msgs)
        self.assertIn("slide 2: layout", msgs)
        self.assertIn(f"cites [{GID_INT}]", msgs)

    def test_lean_rules(self):
        body = (
            '\n---\n\n<LeanBadge gid="D5/S1/Deficit/Nope.missing" />\n'
            f'<TheoremCard label="x" gid="{GID_DEF}">\n\ns\n\n</TheoremCard>\n'
            f'<TheoremCard label="x" status="open" gid="{GID_3V}">\n\ns\n\n</TheoremCard>\n'
            '<LeanBadge />\n<LeanBadge gid="not a gid" />\n'
            '<a href="/abs/path">x</a> [y](/z) <img src="file:///tmp/x.png">\n'
        )
        self.write("zh", self.head("zh") + body)
        self.write("en", self.head("en") + body)
        msgs = "\n".join(self.issues())
        self.assertIn("Nope.missing is not in trureturing.lock.json", msgs)
        self.assertIn("is a Lean def; a TheoremCard must cite a theorem", msgs)
        self.assertIn('status="open"> must not cite Lean', msgs)
        self.assertIn('needs gid="<GID>"', msgs)
        self.assertIn("not a declaration GID", msgs)
        self.assertIn("link /abs/path is absolute", msgs)
        self.assertIn("link /z is absolute", msgs)
        self.assertIn("link file:///tmp/x.png is absolute", msgs)

    def test_cite_must_match_the_book(self):
        zh = (self.head("zh") + f'\n---\n\n<TheoremCard label="定理9.9" gid="{GID_INT}" cite="thm-deficit-three-valued">\n\ns\n\n</TheoremCard>\n'
              '<TheoremCard label="开放问题2.2" cite="prob-greathouse-minimal">\n\ns\n\n</TheoremCard>\n'
              '<TheoremCard label="x" status="open" cite="no-such-env">\n\ns\n\n</TheoremCard>\n')
        self.write("zh", zh)
        self.write("en", zh.replace("zh-CN", "en").replace("T zh", "T en"))
        msgs = [m for m in self.issues() if "slides.md" in m or True]
        joined = "\n".join(msgs)
        self.assertIn("label is '定理9.9' but the book numbers it '定理1.3'", joined)
        self.assertIn(f"cites {GID_INT}, the book cites {GID_3V}", joined)
        self.assertIn('is a problem; use status="open"', joined)
        self.assertIn("no environment #no-such-env", joined)

    def test_stray_files(self):
        self.write("zh", self.head("zh"))
        self.write("en", self.head("en"))
        (self.deck / "slides.fr.md").write_text(self.head("en"), encoding="utf-8")
        (self.deck / "index.html").write_text("<p>x</p>", encoding="utf-8")
        msgs = "\n".join(self.issues())
        self.assertIn("'fr' is not an edition of this book", msgs)
        self.assertIn("index.html", msgs)


@needs_example
class PublishTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="tbook-slides-pub-"))
        self.book = config.load_book("example-monograph")
        self.site = config.load_site()
        self.out = self.tmp / "build"
        base = slides.base_path(self.site)
        langs = {}
        for lang in ("zh", "en"):
            d = self.out / "overview" / lang
            (d / "assets").mkdir(parents=True)
            (d / "index.html").write_text(f"<!doctype html><title>{lang}</title>", encoding="utf-8")
            (d / "assets" / "a.js").write_text("//", encoding="utf-8")
            (self.out / f"overview-{lang}.pdf").write_bytes(b"%PDF-1.7 fake")
            langs[lang] = {"title": lang, "info": "", "blurb": "", "slides": 10, "dir": f"overview/{lang}/",
                           "site_path": slides.site_path(self.book, "overview", lang), "base": base,
                           "pdf": f"overview-{lang}.pdf", "pdf_name": slides.pdf_name(self.book, "overview", lang)}
        (self.out / "manifest.json").write_text(json.dumps(
            {"schema": slides.MANIFEST_SCHEMA, "book": self.book.slug, "base": base, "decks": {"overview": {"langs": langs}}}),
            encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_publish_layout_and_index(self):
        site_dir = self.tmp / "_site" / self.book.slug / "slides"
        (site_dir / "overview" / "stale.txt").parent.mkdir(parents=True)
        (site_dir / "overview" / "stale.txt").write_text("old", encoding="utf-8")
        with mock.patch.object(slides, "build_dir", lambda book: self.out):
            published = slides.publish(self.site, self.book, site_dir, build_missing=False)
        self.assertEqual([p["id"] for p in published], ["overview"])
        self.assertTrue((site_dir / "overview" / "index.html").is_file())
        self.assertTrue((site_dir / "overview" / "assets" / "a.js").is_file())
        self.assertTrue((site_dir / "overview" / "en" / "index.html").is_file())
        self.assertTrue((site_dir / "overview" / "example-monograph-overview-zh.pdf").is_file())
        self.assertTrue((site_dir / "overview" / "example-monograph-overview-en.pdf").is_file())
        self.assertFalse((site_dir / "overview" / "stale.txt").exists())
        index = (site_dir / "index.html").read_text(encoding="utf-8")
        self.assertIn('href="overview/"', index)
        self.assertIn('href="overview/en/"', index)
        self.assertIn('href="overview/example-monograph-overview-en.pdf"', index)
        self.assertIn("在线演示", index)
        self.assertIn("Present online", index)
        self.assertIn("--tr-void", index)  # colours come from the generated tokens
        self.assertNotIn('href="/', index)  # only relative links

    def test_stale_build_is_refused_without_building(self):
        with mock.patch.object(slides, "build_dir", lambda book: self.out), \
                mock.patch.object(self.site, "base_url", "https://o.github.io/other/"):
            with self.assertRaisesRegex(RuntimeError, "built for base"):
                slides.publish(self.site, self.book, self.tmp / "s", build_missing=False)


@needs_example
@unittest.skipUnless(HAVE_NODE, "node and node_modules needed")
class CliNewTest(unittest.TestCase):
    """./tbook slides new in a scratch repository root, then ./tbook check on it."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="tbook-slides-new-"))
        for name in ("theme", "templates", "tools", "node_modules"):
            (self.tmp / name).symlink_to(ROOT / name)
        for name in ("site.toml", "trureturing.lock.json"):
            shutil.copy2(ROOT / name, self.tmp / name)
        (self.tmp / "books").mkdir()
        shutil.copytree(EXAMPLE, self.tmp / "books" / "bk", ignore=shutil.ignore_patterns("slides", "viz", "films"))
        self.env = dict(os.environ, TBOOK_ROOT=str(self.tmp), PYTHONPATH=str(ROOT / "tools"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def tbook(self, *args):
        return subprocess.run([sys.executable, "-m", "tbook", *args], cwd=self.tmp, env=self.env,
                              capture_output=True, text=True)

    def test_new_then_check(self):
        r = self.tbook("slides", "new", "bk", "intro", "入门 \"概览\"", "Getting started")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        zh = (self.tmp / "books" / "bk" / "slides" / "intro" / "slides.md").read_text(encoding="utf-8")
        en = (self.tmp / "books" / "bk" / "slides" / "intro" / "slides.en.md").read_text(encoding="utf-8")
        self.assertIn('title: "入门 \\"概览\\""', zh)
        self.assertIn('lang: "zh-CN"', zh)
        self.assertIn('lang: "en"', en)
        self.assertIn('version: "0.1.0"', en)
        self.assertEqual(slides.count_slides(zh), slides.count_slides(en))
        self.assertNotIn("{{", zh + en)
        r = self.tbook("slides", "new", "bk", "intro", "x", "y")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("already exists", r.stderr)
        r = self.tbook("slides", "new", "bk", "Bad_Name", "x", "y")
        self.assertEqual(r.returncode, 2)
        r = self.tbook("slides", "list")
        self.assertIn("bk/intro", r.stdout)
        if os.environ.get("TRURETURING_DIR") or (ROOT.parent / "trureturing" / ".git").exists():
            r = self.tbook("check", "--offline", "--book", "bk")
            slide_errors = [line for line in r.stdout.splitlines() if "slides/intro" in line]
            self.assertEqual(slide_errors, [], r.stdout)


class ScratchDeckCase(unittest.TestCase):
    """A scratch book with one deck d1 (no example book needed) and the fake lock."""

    EDITIONS = ["zh", "en"]

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="tbook-slides-scratch-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.book = make_book(self.tmp, "scratch-book", self.EDITIONS)
        self.deck = self.book.slides_dir / "d1"
        self.deck.mkdir(parents=True)
        p = mock.patch.object(lean.Lock, "load", return_value=fake_lock())
        p.start()
        self.addCleanup(p.stop)

    def head(self, lang: str, **over) -> str:
        return deck_head(slides.theme_ref(self.deck), lang, **over)

    def write(self, lang: str, text: str) -> None:
        (self.deck / slides.edition_file(self.book, lang)).write_text(text, encoding="utf-8")

    def issues(self) -> list[str]:
        return [i.message for i in slides.check(config.load_book(self.book.dir))]


class FirstLanguageTest(ScratchDeckCase):
    """Finding: slides.md is the book's first language; slides.<first>.md is reported, not shadowed."""

    EDITIONS = ["en", "zh"]

    def write_both(self, body: str = "") -> None:
        self.write("en", self.head("en") + body)
        self.write("zh", self.head("zh") + body)

    def test_english_first_book(self):
        self.write_both(f'\n---\n\n<LeanBadge gid="{FAKE_THM}" />\n')
        self.assertEqual(sorted(p.name for p in self.deck.iterdir()), ["slides.md", "slides.zh.md"])
        self.assertEqual(self.issues(), [])
        self.assertEqual(slides.deck_langs(self.book, "d1"), ["en", "zh"])
        self.assertEqual(slides.read_edition(self.book, "d1", "en").head["htmlAttrs"]["lang"], "en")
        self.assertEqual(slides.read_edition(self.book, "d1", "zh").path.name, "slides.zh.md")
        (it,) = slides.items(self.book)
        self.assertEqual(it["languages"], ["en", "zh"])
        self.assertEqual(it["href"], {"en": "slides/d1/", "zh": "slides/d1/zh/"})
        self.assertIsNone(slides.check_ref(self.book, "d1"))

    def test_first_language_file_is_reported(self):
        self.write_both()
        (self.deck / "slides.en.md").write_text(self.head("en"), encoding="utf-8")
        msgs = self.issues()
        self.assertEqual(len(msgs), 1, msgs)
        self.assertIn("en is the book's first language, whose edition is slides.md", msgs[0])
        self.assertEqual(slides.deck_langs(self.book, "d1"), ["en", "zh"])  # no duplicate, nothing shadowed

    def test_zh_named_file_in_a_chinese_first_book(self):
        zh_first = make_book(self.tmp, "zh-book", ["zh", "en"])
        d = zh_first.slides_dir / "d1"
        d.mkdir(parents=True)
        theme = slides.theme_ref(d)
        (d / "slides.md").write_text(deck_head(theme, "zh"), encoding="utf-8")
        (d / "slides.en.md").write_text(deck_head(theme, "en"), encoding="utf-8")
        (d / "slides.zh.md").write_text(deck_head(theme, "zh"), encoding="utf-8")
        msgs = [i.message for i in slides.check(zh_first)]
        self.assertTrue(any("zh is the book's first language" in m for m in msgs), msgs)
        self.assertEqual(slides.deck_langs(zh_first, "d1"), ["zh", "en"])
        self.assertEqual([it["languages"] for it in slides.items(zh_first)], [["zh", "en"]])

    def test_english_first_publish_layout(self):
        self.write_both()
        out = fake_build(self.book, self.tmp / "build", pdfs=("en",))
        site_dir = self.tmp / "_site" / "slides"
        with mock.patch.object(slides, "build_dir", lambda book: out):
            slides.publish(config.load_site(), self.book, site_dir, build_missing=False)
        self.assertIn("<title>en</title>", (site_dir / "d1" / "index.html").read_text(encoding="utf-8"))
        self.assertIn("<title>zh</title>", (site_dir / "d1" / "zh" / "index.html").read_text(encoding="utf-8"))
        self.assertTrue((site_dir / "d1" / "scratch-book-d1-en.pdf").is_file())
        index = (site_dir / "index.html").read_text(encoding="utf-8")
        self.assertIn('href="d1/"', index)
        self.assertIn('href="d1/zh/"', index)
        self.assertIn("scratch-book-d1-en.pdf", index)
        self.assertNotIn("scratch-book-d1-zh.pdf", index)  # built without the zh PDF


class PublishedPdfLinkTest(ScratchDeckCase):
    """Finding: with a PDF-less slides build (TBOOK_SLIDES_NO_PDF=1), chapter cards must not link PDFs
    that are never published, even when the chapters were built (with the link) before."""

    def test_unpublished_pdf_links_are_removed(self):
        self.write("zh", self.head("zh"))
        self.write("en", self.head("en"))
        out = fake_build(self.book, self.tmp / "build", pdfs=("zh",))  # the en PDF was not built
        book_site = self.tmp / "_site"
        env = SimpleNamespace(attrs={"src": "d1"}, kind="slides")
        pages = {}
        for lang, rel in (("zh", "ch01.html"), ("en", "ch01.html"), ("en", "part/ch02.html"), ("en", "print.html")):
            doc = SimpleNamespace(path=Path("x.md"), chapter=SimpleNamespace(path=rel.replace(".html", ".md")))
            card = slides.render_embed(env, _ctx(self.book, lang, "mdbook"), "", doc)
            card = card.replace(" download>", ' download="">')  # as mdBook writes it
            page = book_site / lang / rel
            page.parent.mkdir(parents=True, exist_ok=True)
            page.write_text(card + '\n<a href="../downloads/book.pdf">book</a>\n', encoding="utf-8")
            pages[(lang, rel)] = page
        with mock.patch.object(slides, "build_dir", lambda book: out):
            slides.publish(config.load_site(), self.book, book_site / "slides", build_missing=False)
        zh = pages[("zh", "ch01.html")].read_text(encoding="utf-8")
        self.assertIn('href="../slides/d1/scratch-book-d1-zh.pdf"', zh)
        self.assertTrue((book_site / "slides" / "d1" / "scratch-book-d1-zh.pdf").is_file())
        for rel in ("ch01.html", "part/ch02.html", "print.html"):
            en = pages[("en", rel)].read_text(encoding="utf-8")
            self.assertNotIn("scratch-book-d1-en.pdf", en, rel)
            self.assertIn("slides/d1/en/", en)  # the other links stay
            self.assertIn("downloads/book.pdf", en)
        self.assertFalse((book_site / "slides" / "d1" / "scratch-book-d1-en.pdf").exists())


class CitationSpellingTest(ScratchDeckCase):
    """Finding: green LEAN ✓ only for Lean theorems; kebab-case component tags are checked too."""

    def test_vue_spellings_resolve_to_the_components(self):
        found, _ = slides.citations(
            '<lean-badge gid="A" /> <leanBadge gid="B"/> <theorem-card label="x" gid="C">s</theorem-card>\n'
            '<Lean-Badge gid="D" /> <lean-badge-x gid="E" /> <LeanBadgeX gid="F" /> <leanbadge gid="G" />')
        self.assertEqual([(c.tag, c.gid) for c in found],
                         [("LeanBadge", "A"), ("LeanBadge", "B"), ("TheoremCard", "C"), ("LeanBadge", "D")])
        self.assertEqual(slides.component("theorem-card"), "TheoremCard")

    def test_kebab_case_and_non_theorems_are_checked(self):
        body = ('\n---\n\n<lean-badge gid="D5/S9/Fake/Nope.not_locked" />\n'
                f'<theorem-card label="x" gid="{FAKE_DEF}">\n\ns\n\n</theorem-card>\n'
                f'<LeanBadge gid="{FAKE_DEF}" />\n'
                f'<leanBadge gid="{FAKE_THM}" />\n'
                f'<lean-badge kind="definition" gid="{FAKE_DEF}" />\n'
                f'<TheoremCard kind="definition" label="d" gid="{FAKE_DEF}">\n\ns\n\n</TheoremCard>\n')
        self.write("zh", self.head("zh") + body)
        self.write("en", self.head("en") + body)
        msgs = self.issues()
        want = {"D5/S9/Fake/Nope.not_locked is not in trureturing.lock.json",
                f'{FAKE_DEF} is a Lean def; a TheoremCard must cite a theorem (or say kind="definition")',
                f'{FAKE_DEF} is a Lean def; a LeanBadge must cite a theorem (or say kind="definition")'}
        self.assertEqual(len(msgs), 6, msgs)  # three per edition
        for w in want:
            self.assertEqual(sum(w in m for m in msgs), 2, (w, msgs))
        self.assertIn("D5/S9/Fake/Nope.not_locked", {g for _, _, g in slides.cited_gids(self.book)})

    def test_slide_imports_are_rejected(self):
        body = "\n---\nsrc: ./more.md\n---\n"
        self.write("zh", self.head("zh") + body)
        self.write("en", self.head("en") + body)
        msgs = self.issues()
        self.assertEqual(len(msgs), 2, msgs)
        self.assertTrue(all("src: imports slides from another file" in m for m in msgs), msgs)


@unittest.skipUnless(HAVE_UNO, "node and node_modules (@slidev/parser, unocss) needed")
class NodeScriptsTest(unittest.TestCase):
    """tools/node/slides-check.mjs and slides-new.mjs in a scratch repository root (TBOOK_ROOT)."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="tbook-slides-node-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        for name in ("theme", "templates", "tools", "node_modules"):
            (self.tmp / name).symlink_to(ROOT / name)
        (self.tmp / "site.toml").write_text('[site]\ntitle = "t"\nlanguages = ["zh", "en"]\n', encoding="utf-8")
        self.env = dict(os.environ, TBOOK_ROOT=str(self.tmp))

    def node(self, script: str, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run([NODE, str(ROOT / "tools" / "node" / script), *args], cwd=self.tmp, env=self.env,
                              capture_output=True, text=True)

    def book(self, editions: list[str]) -> Path:
        (self.tmp / "trureturing.lock.json").write_text(json.dumps(
            {"schema": lean.LOCK_SCHEMA, "repo": "o/trureturing", "branch": "dev", "commit": "0" * 40,
             "declarations": FAKE_DECLS}), encoding="utf-8")
        return make_book(self.tmp / "books", "bk", editions).dir

    def test_check_without_decks_succeeds(self):
        r = self.node("slides-check.mjs")  # no books/, no lock
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("0 deck(s)", r.stdout)
        (self.tmp / "books").mkdir()
        make_book(self.tmp / "books", "plain", ["zh", "en"])
        r = self.node("slides-check.mjs")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_check_first_language_and_citations(self):
        deck = self.book(["en", "zh"]) / "slides" / "d1"
        deck.mkdir(parents=True)
        theme = "../../../../theme/slides"
        good = f'\n---\n\n<leanBadge gid="{FAKE_THM}" />\n<TheoremCard kind="definition" label="d" gid="{FAKE_DEF}">\n\ns\n\n</TheoremCard>\n'
        (deck / "slides.md").write_text(deck_head(theme, "en") + good, encoding="utf-8")
        (deck / "slides.zh.md").write_text(deck_head(theme, "zh") + good, encoding="utf-8")
        r = self.node("slides-check.mjs")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("books/bk/slides/d1/slides.md: en", r.stdout)
        self.assertIn("books/bk/slides/d1/slides.zh.md: zh", r.stdout)

        bad = ('\n---\n\n<lean-badge gid="D5/S9/Fake/Nope.not_locked" />\n'
               f'<theorem-card label="x" gid="{FAKE_DEF}">\n\ns\n\n</theorem-card>\n<LeanBadge gid="{FAKE_DEF}" />\n'
               '\n---\nsrc: ./more.md\n---\n')
        (deck / "slides.md").write_text(deck_head(theme, "en") + bad, encoding="utf-8")
        (deck / "slides.zh.md").write_text(deck_head(theme, "zh") + bad, encoding="utf-8")
        (deck / "slides.en.md").write_text(deck_head(theme, "en"), encoding="utf-8")
        r = self.node("slides-check.mjs")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        for want in ["slides.en.md: en is the book's first language, whose edition is slides.md",
                     "D5/S9/Fake/Nope.not_locked is not in trureturing.lock.json",
                     f'{FAKE_DEF} is a Lean def; a TheoremCard must cite a theorem',
                     f'{FAKE_DEF} is a Lean def; a LeanBadge must cite a theorem',
                     "src: imports slides from another file"]:
            self.assertIn(want, r.stderr)

    def test_new_deck_in_an_english_first_book(self):
        self.book(["en", "zh"])
        r = self.node("slides-new.mjs", "bk", "intro", "入门", "Getting started")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        deck = self.tmp / "books" / "bk" / "slides" / "intro"
        self.assertEqual(sorted(p.name for p in deck.iterdir()), ["slides.md", "slides.zh.md"])
        en = (deck / "slides.md").read_text(encoding="utf-8")
        zh = (deck / "slides.zh.md").read_text(encoding="utf-8")
        self.assertIn('lang: "en"', en)
        self.assertIn("Getting started", en)
        self.assertIn('lang: "zh-CN"', zh)
        self.assertIn("入门", zh)
        r = self.node("slides-check.mjs")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
