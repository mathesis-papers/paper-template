"""Tests for the Pandoc pipeline: staging, Lua filters, metadata, PDF/EPUB builds, covers.

Run: PYTHONPATH=tools .venv/bin/python -m unittest discover -s tools/tests -p 'test_pandoc.py'

A small synthetic book (prefix, parts, a nested chapter, a draft, an appendix without an H1,
setext headings, book and edition images, cross-chapter links) is written to a temporary
directory; every build output goes to temporary directories too. Tests that need pandoc,
typst, Java/epubcheck or the example book's Lean lock skip themselves when unavailable.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path

from tbook import config, cover, lean, paths
from tbook import pandoc as tp
from tbook.model import load_edition

def _png(width: int = 4, height: int = 4) -> bytes:
    """A valid RGB PNG (cyan pixels) built with zlib, so the fixture needs no binary blobs."""
    import struct
    import zlib

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    raw = b"".join(b"\x00" + b"\x19\xf0\xff" * width for _ in range(height))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


PNG_1PX = _png()
SVG = ('<svg xmlns="http://www.w3.org/2000/svg" width="120" height="60" viewBox="0 0 120 60">'
       '<rect width="120" height="60" fill="#888"/><circle cx="60" cy="30" r="20" fill="#fff"/></svg>')

FILES = {
    "book.toml": """
[book]
version = "1.2.3"
authors = ["A. Author", "B. Author"]
license = "CC-BY-4.0"
editions = ["en"]
code = "TEST//BOOK"
date = "2026-01-02"

[book.title]
en = "Test Book"

[book.subtitle]
en = "A fixture"

[book.isbn]
en = "978-3-16-148410-0"

[pdf]
paper = "a5"
""",
    "assets/fig.svg": SVG,
    "en/img/dot.png": PNG_1PX,
    "en/SUMMARY.md": """# Summary

[Preface](README.md)

# Part One

- [Chapter A](a.md)
  - [Section A.1](part/a1.md)
- [Draft]()

# Part Two

- [Chapter B](b.md)

[Appendix](appendix.md)
""",
    "en/README.md": "# Preface\n\nSee [chapter B](b.md#sec-b) and [A](a.md).\n",
    "en/a.md": """Chapter A
=========

Intro with ![a figure](../assets/fig.svg) and a local image:

![dot](img/dot.png)

::: {.definition #def-a title="Size of $x$"}
Define $x$ and see [B](./b.md).
:::

```text
# not a heading [x](b.md)
```

::: {.tr-media .tr-viz}
![media poster](../assets/fig.svg)
:::

## Sub A {#sub-a}

Text.
""",
    "en/part/a1.md": """# Section A.1

Back to [the definition](../a.md#def-a), ![f](../../assets/fig.svg), [missing](../nope.md).

## Deeper

[ref]: ../b.md
""",
    "en/b.md": """# Chapter B

## Section B {#sec-b}

::: remark
See [@def-a] and the [sub section](a.md#sub-a).
:::
""",
    "en/appendix.md": "Text of the appendix with a [dangling](#nowhere) link.\n",
}


def have_pandoc() -> bool:
    try:
        return bool(tp.pandoc_path())
    except tp.PandocError:
        return False


def have_typst() -> bool:
    try:
        import typst  # noqa: F401
        return True
    except ImportError:
        return False


def make_book(root: Path) -> config.Book:
    bdir = root / "test-book"
    for rel, content in FILES.items():
        f = bdir / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            f.write_bytes(content)
        else:
            f.write_text(content.lstrip("\n"), encoding="utf-8")
    return config.load_book(bdir)


def run_filters(md: str, fmt: str, meta: dict[str, str] | None = None) -> str:
    args = [tp.pandoc_path(), "-f", tp.READER, "-t", fmt, "--wrap", "none", *tp._filters()]
    for k, v in (meta or {}).items():
        args += ["--metadata", f"{k}={v}"]
    proc = subprocess.run(args, input=md, capture_output=True, text=True, check=True)
    return proc.stdout


ENV_MD = """\
# Chapter {#ch-x .tr-chapter tr-section="numbered" tr-kicker="§ 01"}

See [the theorem](#thm-x) and [nothing](#missing).

:::::: {#thm-x .tr-env .theorem tr-kind="theorem" tr-status="lean" tr-label="Theorem" tr-number="1.2" tr-ref="Theorem 1.2" tr-title="Bound on $c$" tr-badge="LEAN ✓" tr-lean="D5/S1/X.y" tr-lean-name="D5.S1.X.y" tr-lean-url="https://example.org/X.lean#L3"}
Statement $c \\in \\{0, 1\\}$.
::::::

:::::: {.tr-env .proof tr-kind="proof" tr-status="proof" tr-label="Proof" tr-number="" tr-ref="Proof"}
Easy.
::::::

:::::: {#prob-x .tr-env .problem tr-kind="problem" tr-status="open" tr-label="Open problem" tr-number="1.3" tr-ref="Open problem 1.3" tr-badge="OPEN"}
Is it minimal?
::::::
"""


class StagingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="tbook-test-pandoc-"))
        cls.site = config.load_site()
        cls.book = make_book(cls.tmp)
        cls.ed = cls.book.edition("en")
        cls.model = load_edition(cls.ed)
        cls.stage = tp.stage(cls.site, cls.book, cls.ed, cls.model, None, out_dir=cls.tmp / "stage")
        cls.md = cls.stage.book_md.read_text(encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def heading(self, text: str) -> str:
        for line in self.md.splitlines():
            if re.match(r"^#{1,6} " + re.escape(text) + r"( \{|$)", line):
                return line
        self.fail(f"heading {text!r} not found in book.md:\n{self.md}")

    def test_model_has_no_issues(self):
        self.assertEqual([i.format() for i in self.model.issues], [])

    def test_chapter_order_and_ids(self):
        self.assertEqual([c.path for c in self.stage.chapters],
                         ["README.md", "a.md", "part/a1.md", "b.md", "appendix.md", "verification-ledger.md"])
        self.assertEqual([c.id for c in self.stage.chapters],
                         ["ch-readme", "ch-a", "ch-part-a1", "ch-b", "ch-appendix", "tr-verification-ledger"])

    def test_setext_title_and_attributes(self):
        h = self.heading("Chapter A")
        self.assertTrue(h.startswith("# Chapter A {#ch-a .tr-chapter"), h)
        self.assertIn('tr-section="numbered"', h)
        self.assertIn('tr-kicker="§ 01"', h)
        self.assertNotIn(".unnumbered", h)

    def test_prefix_and_suffix_unnumbered(self):
        pre = self.heading("Preface")
        self.assertIn(".unnumbered", pre)
        self.assertIn('epub:type="preface"', pre)
        app = self.heading("Appendix")  # synthesized from SUMMARY: the file has no H1
        self.assertTrue(app.startswith("# Appendix {#ch-appendix .tr-chapter .unnumbered"), app)
        self.assertIn('tr-section="suffix"', app)
        self.assertIn('tr-kicker="§ A"', app)

    def test_nested_chapter_headings_shift(self):
        self.assertTrue(self.heading("Section A.1").startswith("## Section A.1 {#ch-part-a1 .tr-chapter"))
        self.assertEqual(self.heading("Deeper"), "### Deeper")
        self.assertEqual(self.heading("Sub A"), "## Sub A {#sub-a}")

    def test_parts(self):
        self.assertTrue(self.heading("Part One").startswith("# Part One {#tr-part-1 .tr-part .unnumbered"))
        self.assertTrue(self.heading("Part Two").startswith("# Part Two {#tr-part-2 .tr-part"))
        self.assertLess(self.md.index("# Part One"), self.md.index("# Chapter A"))
        self.assertLess(self.md.index("# Part Two"), self.md.index("# Chapter B"))

    def test_draft_skipped(self):
        self.assertNotIn("Draft", self.md)

    def test_links_between_chapters(self):
        self.assertIn("[chapter B](#sec-b)", self.md)
        self.assertIn("[A](#ch-a)", self.md)
        self.assertIn("[the definition](#def-a)", self.md)
        self.assertIn("[B](#ch-b)", self.md)  # ./b.md inside an environment
        self.assertIn("[sub section](#sub-a)", self.md)
        self.assertIn("[ref]: #ch-b", self.md)  # reference definition rebased
        self.assertIn("[Definition 1.1](#def-a)", self.md)  # [@def-a]

    def test_link_to_non_chapter_dropped(self):
        self.assertIn(", missing.", self.md)
        self.assertTrue(any("nope.md" in w for w in self.stage.warnings), self.stage.warnings)

    def test_images_rebased_and_copied(self):
        self.assertIn("![a figure](_book/assets/fig.svg)", self.md)
        self.assertIn("![f](_book/assets/fig.svg)", self.md)  # nested chapter: ../../assets
        self.assertIn("![dot](_book/en/img/dot.png)", self.md)  # edition-local image
        self.assertIn("_book/assets/fig.svg", self.stage.files)
        self.assertIn("_book/en/img/dot.png", self.stage.files)
        self.assertTrue((self.stage.dir / "_book/assets/fig.svg").is_file())
        self.assertTrue((self.stage.dir / "_book/en/img/dot.png").is_file())

    def test_code_blocks_untouched(self):
        self.assertIn("# not a heading [x](b.md)", self.md)

    def test_ledger_appended_last(self):
        last = self.md.rsplit("\n# ", 1)[1]
        self.assertTrue(last.startswith("Verification ledger {#tr-verification-ledger"), last[:120])
        self.assertIn(".tr-ledger", last.splitlines()[0])
        self.assertIn('tr-section="back"', last.splitlines()[0])
        self.assertIn(".unnumbered", last.splitlines()[0])

    def test_environment_divs_present(self):
        self.assertRegex(self.md, r':{6} \{#def-a \.tr-env \.definition tr-kind="definition"')

    def test_theme_and_meta_staged(self):
        for rel in ("_theme/typst/book.typ", "_theme/typst/cover.typ", "_theme/typst/pandoc-template.typst",
                    "_theme/generated/tokens.typ", "_theme/typst/code-screen.tmTheme", "_theme/typst/code-print.tmTheme"):
            self.assertTrue((self.stage.dir / rel).is_file(), rel)
        meta = json.loads((self.stage.dir / "meta.json").read_text(encoding="utf-8"))
        self.assertEqual(meta["title"], "Test Book")
        self.assertEqual(meta["paper"], "a5")
        self.assertEqual(meta["authors"], ["A. Author", "B. Author"])
        self.assertEqual(meta["formal_count"], 0)
        self.assertEqual(meta["isbn"], "978-3-16-148410-0")
        self.assertEqual(meta["date"], {"year": 2026, "month": 1, "day": 2, "iso": "2026-01-02"})

    def test_restage_is_clean_and_deterministic(self):
        again = tp.stage(self.site, self.book, self.ed, self.model, None, out_dir=self.tmp / "stage2")
        self.assertEqual(again.book_md.read_text(encoding="utf-8"), self.md)


class HeadingHelpersTest(unittest.TestCase):
    def test_parse_heading_attrs_and_closing_hashes(self):
        level, text, attrs = tp.parse_heading("## Title ## {#x .y k=\"v\"}")
        self.assertEqual((level, text, attrs.id, attrs.classes, attrs.kv), (2, "Title", "x", ["y"], {"k": "v"}))
        self.assertIsNone(tp.parse_heading("#hashtag"))
        self.assertIsNone(tp.parse_heading("    # indented code"))

    def test_setext(self):
        self.assertEqual(tp.normalize_setext("Title\n===\n\nSub\n---\n"), "# Title\n\n## Sub\n")
        # a list item followed by --- is not a setext heading
        self.assertEqual(tp.normalize_setext("- item\n---\n"), "- item\n---\n")
        # inside a fence nothing changes
        self.assertEqual(tp.normalize_setext("```\nx\n===\n```\n"), "```\nx\n===\n```\n")

    def test_shift_caps_at_six(self):
        out = tp.restructure_chapter("# T\n\n###### Six\n", chapter_path="x.md", depth=2, chapter_id="ch-x",
                                     title="T", classes=["tr-chapter"], kv={}, linker=None)
        self.assertIn("### T {#ch-x .tr-chapter}", out)
        self.assertIn("###### Six", out)

    def test_chapter_slug(self):
        self.assertEqual(tp.chapter_slug("part 1/Intro.md"), "ch-part-1-intro")


@unittest.skipUnless(have_pandoc(), "pandoc not available")
class LuaFilterTest(unittest.TestCase):
    META = {"tr-punct-open": " (", "tr-punct-close": ")", "tr-lean-label": "Lean", "tr-badge-lean-title": "verified"}

    def test_typst_output(self):
        out = run_filters(ENV_MD, "typst", self.META)
        self.assertIn('#tr-env(kind: "theorem", status: "lean", label: "Theorem", number: "1.2", '
                      'ref: "Theorem 1.2", title: [Bound on $c$], badge: "LEAN ✓", '
                      'lean: ((gid: "D5/S1/X.y", name: "D5.S1.X.y", url: "https://example.org/X.lean#L3"),), '
                      'id: "thm-x")[', out)
        self.assertRegex(out, r"\]\s*<thm-x>")
        self.assertIn("#link(<thm-x>)[the theorem]", out)
        self.assertNotIn("<missing>", out)  # dangling link became text
        self.assertIn('#tr-proof(label: "Proof", id: "")[', out)
        self.assertIn('#tr-proof-label("Proof")', out)
        self.assertIn("#tr-qed()", out)
        self.assertIn('status: "open"', out)
        self.assertIn('#tr-chapter(id: "ch-x", kicker: "§ 01", section: "numbered", outlined: true, title: [Chapter])', out)

    def test_html_output(self):
        out = run_filters(ENV_MD, "html5", self.META)
        self.assertIn('<section id="thm-x" class="tr-env tr-theorem tr-status-lean" data-kind="theorem">', out)
        self.assertIn('<header class="tr-env-head">', out)
        self.assertIn('<span class="tr-env-label">Theorem 1.2</span>', out)
        self.assertRegex(out, r'<span class="tr-env-title"> \(Bound on <span class="math inline">')
        self.assertIn('class="tr-badge tr-badge-lean"', out)
        self.assertIn('title="verified"', out)
        self.assertIn('<footer class="tr-env-lean">', out)
        self.assertIn('<a href="https://example.org/X.lean#L3" class="tr-lean-decl" title="D5/S1/X.y"><code>D5.S1.X.y</code></a>', out)
        self.assertIn('class="tr-env tr-proof tr-status-proof"', out)
        self.assertIn('<span class="tr-qed" aria-hidden="true">∎</span>', out)
        self.assertIn('class="tr-badge tr-badge-open"', out)
        self.assertIn('<span class="tr-dangling">nothing</span>', out)
        self.assertIn('<a href="#thm-x">the theorem</a>', out)

    def test_generic_fallback(self):
        out = run_filters(ENV_MD, "markdown", self.META)
        self.assertIn("**Theorem 1.2** (Bound on $c$)", out)
        self.assertIn("Lean: [`D5.S1.X.y`](https://example.org/X.lean#L3)", out)

    def test_long_code_gets_break_hints(self):
        md = "`D5.S3.ConceptDynamics.Restoration.target_recovery_criterion`\n"
        self.assertIn("#tr-code-break(", run_filters(md, "typst"))
        self.assertIn(".<wbr/>", run_filters(md, "html5"))


class MetadataTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="tbook-test-meta-"))
        cls.book = make_book(cls.tmp)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_identifier(self):
        ed = self.book.edition("en")
        self.assertEqual(tp.edition_identifier(self.book, ed), "urn:isbn:9783161484100")
        self.book.isbn = {}
        try:
            ident = tp.edition_identifier(self.book, ed)
            self.assertRegex(ident, r"^urn:uuid:[0-9a-f-]{36}$")
            self.assertEqual(ident, tp.edition_identifier(self.book, ed))  # deterministic (uuid5)
        finally:
            self.book.isbn = {"en": "978-3-16-148410-0"}

    def test_source_date_epoch(self):
        old = os.environ.pop("SOURCE_DATE_EPOCH", None)
        try:
            self.assertEqual(tp.source_date_epoch(self.book), 1767312000)  # 2026-01-02T00:00:00Z
        finally:
            if old is not None:
                os.environ["SOURCE_DATE_EPOCH"] = old

    def test_strings_fallback(self):
        self.assertEqual(tp.t("zh", "pdf.colophon"), "版权信息")
        self.assertEqual(tp.t("en", "pdf.colophon"), "Colophon")
        self.assertEqual(tp.t("fr", "pdf.colophon"), "Colophon")
        self.assertEqual(tp.t("en", "ui.contents"), "Contents")  # shared i18n wins
        self.assertIn("3", tp.t("en", "pdf.verified_statement", n=3))

    def test_display_options(self):
        self.assertIn('<option name="specified-fonts">false</option>', tp.display_options_xml(False))
        self.assertIn('<option name="specified-fonts">true</option>', tp.display_options_xml(True))

    def test_palette_css_uses_tokens(self):
        css = tp.epub_palette_css()
        tokens = json.loads(paths.TOKENS.read_text(encoding="utf-8"))
        self.assertIn(f"--tr-cyan: {tokens['paper']['cyan']};", css)
        self.assertIn(f"--tr-cyan: {tokens['screen']['cyan']};", css)
        self.assertIn("prefers-color-scheme: dark", css)
        self.assertIn('__ibooks_internal_theme*="Night"', css)

    def test_code_theme_from_tokens(self):
        tokens = json.loads(paths.TOKENS.read_text(encoding="utf-8"))
        xml = tp.code_theme(tokens["screen"], "screen")
        self.assertIn(tokens["screen"]["magenta"], xml)
        self.assertNotIn(tokens["screen"]["ok"], xml)  # green is reserved for Lean-verified

    def test_woff_conversion(self):
        src = paths.ROOT / "node_modules/@fontsource/chakra-petch/files/chakra-petch-latin-400-normal.woff"
        if not src.exists():
            self.skipTest("@fontsource/chakra-petch not installed")
        ttf = tp._woff_to_sfnt(src.read_bytes())
        self.assertEqual(ttf[:4], b"\x00\x01\x00\x00")

    def test_finalize_epub_layout(self):
        raw = self.tmp / "raw.epub"
        with zipfile.ZipFile(raw, "w") as z:
            z.writestr("mimetype", "application/epub+zip")
            z.writestr("META-INF/container.xml", "<container/>")
            z.writestr("META-INF/com.apple.ibooks.display-options.xml", "old")
            z.writestr("EPUB/text/ch001.xhtml", "<html><head><title>ch001.xhtml</title></head>"
                                                "<body><h1 id=\"a\">One <em>two</em></h1></body></html>")
        out = tp.finalize_epub(raw, self.tmp / "out.epub", specified_fonts=False, epoch=1767312000, title="T")
        with zipfile.ZipFile(out) as z:
            infos = z.infolist()
            self.assertEqual(infos[0].filename, "mimetype")
            self.assertEqual(infos[0].compress_type, zipfile.ZIP_STORED)
            self.assertEqual(infos[1].filename, "META-INF/container.xml")
            self.assertEqual(infos[2].filename, tp.DISPLAY_OPTIONS)
            self.assertIn(b"false", z.read(tp.DISPLAY_OPTIONS))
            self.assertIn(b"<title>One two</title>", z.read("EPUB/text/ch001.xhtml"))
            self.assertTrue(all(i.date_time == (2026, 1, 2, 0, 0, 0) for i in infos))


@unittest.skipUnless(have_pandoc() and have_typst(), "pandoc or typst not available")
class BuildTest(unittest.TestCase):
    """End-to-end builds of the synthetic book (PDF both variants, EPUB, covers)."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="tbook-test-build-"))
        cls.site = config.load_site()
        cls.book = make_book(cls.tmp)
        cls.ed = cls.book.edition("en")
        cls.model = load_edition(cls.ed)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_pdf_variants(self):
        for variant in ("screen", "print"):
            out = tp.build_pdf(self.site, self.book, self.ed, self.model, None, variant,
                               self.tmp / f"book-{variant}.pdf", stage_dir=self.tmp / f"stage-{variant}")
            data = out.read_bytes()
            self.assertTrue(data.startswith(b"%PDF-"))
            self.assertGreater(len(data), 20_000)
        main = (self.tmp / "stage-screen" / "main.typ").read_text(encoding="utf-8")
        self.assertIn('#tr-part(id: "tr-part-1"', main)
        self.assertIn('#tr-media(kind: "viz")[', main)
        self.assertNotIn("<nowhere>", main)

    def test_pdf_rejects_unknown_variant(self):
        with self.assertRaises(tp.PandocError):
            tp.build_pdf(self.site, self.book, self.ed, self.model, None, "glossy", self.tmp / "x.pdf")

    def test_epub(self):
        old = os.environ.get("TBOOK_EPUBCHECK")
        os.environ["TBOOK_EPUBCHECK"] = "0"
        try:
            out = tp.build_epub(self.site, self.book, self.ed, self.model, None, self.tmp / "book.epub",
                                stage_dir=self.tmp / "stage-epub")
        finally:
            if old is None:
                os.environ.pop("TBOOK_EPUBCHECK", None)
            else:
                os.environ["TBOOK_EPUBCHECK"] = old
        with zipfile.ZipFile(out) as z:
            names = z.namelist()
            self.assertEqual(names[0], "mimetype")
            opf = z.read("EPUB/content.opf").decode("utf-8")
            css = z.read("EPUB/styles/stylesheet1.css").decode("utf-8")
            texts = "".join(z.read(n).decode("utf-8") for n in names if n.endswith(".xhtml"))
        self.assertIn("<dc:title id=\"epub-title-1\">Test Book</dc:title>", opf)
        self.assertIn('property="title-type">subtitle</meta>', opf)
        self.assertIn("<dc:language>en</dc:language>", opf)
        self.assertIn("9783161484100", opf)
        self.assertIn('<meta property="ibooks:version">1.2.3</meta>', opf)
        self.assertIn("<dc:rights>CC-BY-4.0</dc:rights>", opf)
        self.assertIn("A. Author", opf)
        self.assertIn('properties="cover-image"', opf)
        self.assertIn("2026-01-02T00:00:00Z", opf)  # dcterms:modified from SOURCE_DATE_EPOCH
        self.assertIn("--tr-ok:", css)
        self.assertIn('epub:type="copyright-page"', texts)
        self.assertIn('href="ch', texts)  # cross-file links resolved by the EPUB writer
        self.assertIn('<math', texts)  # MathML
        self.assertIn("tr-dangling", texts)
        self.assertNotIn("<title>ch0", texts)
        if shutil.which("java"):
            report = tp.check_epub(out)
            if not report.skipped:
                self.assertEqual(report.errors, [])

    def test_epub_embedded_fonts(self):
        fonts = [f for f in tp.epub_font_files() if tp._font_face(f) and not tp._font_face(f)[0].endswith(" SC")]
        if not fonts:
            self.skipTest("no Latin font files to embed")
        self.book.epub["embed_fonts"] = True
        os.environ["TBOOK_EPUBCHECK"] = "0"
        try:
            out = tp.build_epub(self.site, self.book, self.ed, self.model, None, self.tmp / "fonts.epub",
                                stage_dir=self.tmp / "stage-fonts")
        finally:
            self.book.epub.pop("embed_fonts", None)
            os.environ.pop("TBOOK_EPUBCHECK", None)
        with zipfile.ZipFile(out) as z:
            names = z.namelist()
            css = z.read("EPUB/styles/stylesheet1.css").decode("utf-8")
            self.assertIn(b"<option name=\"specified-fonts\">true</option>", z.read(tp.DISPLAY_OPTIONS))
        self.assertTrue(any(n.startswith("EPUB/fonts/") for n in names), names)
        self.assertIn("@font-face", css)
        if shutil.which("java"):
            report = tp.check_epub(out)
            if not report.skipped:
                self.assertEqual(report.errors, [])

    def test_epub_deterministic(self):
        os.environ["TBOOK_EPUBCHECK"] = "0"
        try:
            a = tp.build_epub(self.site, self.book, self.ed, self.model, None, self.tmp / "a.epub",
                              stage_dir=self.tmp / "stage-a")
            b = tp.build_epub(self.site, self.book, self.ed, self.model, None, self.tmp / "b.epub",
                              stage_dir=self.tmp / "stage-b")
        finally:
            os.environ.pop("TBOOK_EPUBCHECK", None)
        self.assertEqual(a.read_bytes(), b.read_bytes())

    def test_cover_formats(self):
        png = cover.render_cover(self.site, self.book, self.ed, self.tmp / "c.png", model=self.model, lock=None)
        data = png.read_bytes()
        self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
        width, height = int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")
        self.assertEqual((width, height), (1600, 2560))
        pdf = cover.render_cover(self.site, self.book, self.ed, self.tmp / "c.pdf", fmt="pdf",
                                 variant="print", model=self.model, lock=None)
        self.assertTrue(pdf.read_bytes().startswith(b"%PDF-"))
        svg = cover.render_cover(self.site, self.book, self.ed, self.tmp / "c.svg", fmt="svg", model=self.model, lock=None)
        self.assertIn(b"<svg", svg.read_bytes()[:400])
        with self.assertRaises(ValueError):
            cover.render_cover(self.site, self.book, self.ed, self.tmp / "c.gif", fmt="gif")


@unittest.skipUnless(have_pandoc() and have_typst() and shutil.which("java"), "pandoc, typst or java missing")
class ExampleBookEpubcheckTest(unittest.TestCase):
    """The shipped example book must produce an EPUB that epubcheck accepts with zero errors."""

    def test_example_epub_valid(self):
        try:
            lock = lean.Lock.load()
        except lean.LeanError as exc:
            self.skipTest(str(exc))
        try:
            book = config.load_book("example-monograph")
        except config.ConfigError as exc:
            self.skipTest(str(exc))
        site = config.load_site()
        with tempfile.TemporaryDirectory(prefix="tbook-test-example-") as tmp:
            for ed in book.editions:
                os.environ["TBOOK_EPUBCHECK"] = "0"
                try:
                    out = tp.build_epub(site, book, ed, load_edition(ed), lock, Path(tmp) / f"{ed.lang}.epub",
                                        stage_dir=Path(tmp) / f"stage-{ed.lang}")
                finally:
                    os.environ.pop("TBOOK_EPUBCHECK", None)
                report = tp.check_epub(out)
                if report.skipped:
                    self.skipTest(report.skipped)
                self.assertEqual(report.errors, [], f"{ed.lang}: {report.errors}")


if __name__ == "__main__":
    unittest.main()
