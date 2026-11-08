"""Tests for the site assembler, local server, doctor and Lean deep verification.

Run: PYTHONPATH=tools python -m unittest discover -s tools/tests -p 'test_site.py'

Everything runs on temporary books and fake build outputs: no mdBook, Typst, Node or network.
Media modules (viz, film, slides) and covers are replaced by fakes, so these tests do not depend
on the state of those components. The test that reads trureturing's lean-toolchain through the
ledger is skipped without a trureturing checkout ($TRURETURING_DIR or ../trureturing).
"""

from __future__ import annotations

import html.parser
import json
import os
import shutil
import stat
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import tbook
from tbook import config, doctor, lean, leanverify, paths, serve, site

GID_3V = "D5/S1/Deficit/DeficitThreeValued.deficit_three_valued"
GID_INT = "D5/S1/Deficit/DeficitInteger.deficit_integer"
PNG = b"\x89PNG\r\n\x1a\n" + b"\0" * 32  # enough for a file that exists; never decoded


# --------------------------------------------------------------------------- fixtures


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def make_book(root: Path, slug: str = "test-book", *, editions=("zh", "en"), title_zh="测试之书",
              title_en="A Test Book") -> config.Book:
    bdir = root / "books" / slug
    langs = ", ".join(f'"{lang}"' for lang in editions)
    write(bdir / "book.toml", f"""[book]
version = "1.2.3"
authors = ["Ada"]
license = "CC-BY-4.0"
editions = [{langs}]
code = "TEST//BOOK"
date = "2026-01-02"

[book.title]
zh = {json.dumps(title_zh, ensure_ascii=False)}
en = {json.dumps(title_en, ensure_ascii=False)}

[book.subtitle]
zh = "副标题"
en = "Subtitle"

[book.description]
zh = "描述。"
en = "Description."
""")
    chapters = {
        "zh": ("前言", "第一章 开始", "第二章 问题"),
        "en": ("Preface", "Chapter 1 Start", "Chapter 2 Problems"),
    }
    for lang in editions:
        pre, c1, c2 = chapters.get(lang, chapters["en"])
        write(bdir / lang / "SUMMARY.md", f"# Summary\n\n[{pre}](README.md)\n\n- [{c1}](ch01.md)\n- [{c2}](ch02.md)\n")
        write(bdir / lang / "README.md", f"# {pre}\n\nText.\n")
        write(bdir / lang / "ch01.md", f"# {c1}\n\n"
              f'::: {{.theorem #thm-a title="T&A" lean="{GID_3V}"}}\nX\n:::\n\n'
              f'::: {{.theorem #thm-b lean="{GID_INT}"}}\nY\n:::\n')
        write(bdir / lang / "ch02.md", f"# {c2}\n\n::: {{.problem #prob-c title=\"P\"}}\nZ\n:::\n")
    return config.load_book(bdir)


def fake_build(build_root: Path, book: config.Book, *, html_langs=("zh", "en"), dist=True) -> None:
    for lang in html_langs:
        hdir = build_root / "html" / book.slug / lang
        for name in ("index.html", "ch01.html", "ch02.html", "verification-ledger.html", "print.html"):
            write(hdir / name, f"<!doctype html><title>{lang} {name}</title>")
        write(hdir / ".nojekyll", "")
    if dist:
        ddir = build_root / "dist" / book.slug
        ddir.mkdir(parents=True, exist_ok=True)
        (ddir / book.artifact("zh", "pdf", "screen")).write_bytes(b"%PDF-1.7 zh screen")
        (ddir / book.artifact("zh", "epub")).write_bytes(b"PK zh epub")
        (ddir / book.artifact("en", "pdf", "print")).write_bytes(b"%PDF-1.7 en print " * 100)


class LinkCollector(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.links: list[tuple[str, str, str]] = []  # (tag, attr, value)
        self.tags: list[tuple[str, dict]] = []

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        self.tags.append((tag, d))
        for attr in ("href", "src"):
            if d.get(attr) is not None:
                self.links.append((tag, attr, d[attr]))


def parse(text: str) -> LinkCollector:
    p = LinkCollector()
    p.feed(text)
    return p


def fake_media(viz_items=None, slides_items=None, film_items=None, *, viz_build=None, slides_publish=None,
               film_build=None):
    """A _media_module replacement returning fake modules."""
    def default_viz_build(site_, book, dest):
        write(Path(dest) / "index.html", "hub")
        for it in viz_items or []:
            write(Path(dest) / it["id"] / "index.html", "viz")
            (Path(dest) / it["id"] / "thumb.jpg").write_bytes(b"jpg")

    def default_slides_publish(site_, book, dest):
        for it in slides_items or []:
            write(Path(dest) / it["id"] / "index.html", "deck")
            write(Path(dest) / it["id"] / "en" / "index.html", "deck en")
            (Path(dest) / it["id"] / f"{book.slug}-{it['id']}-zh.pdf").write_bytes(b"%PDF deck")

    mods = {
        "viz": SimpleNamespace(items=lambda book: list(viz_items or []), build=viz_build or default_viz_build),
        "slides": SimpleNamespace(items=lambda book: list(slides_items or []), publish=slides_publish or default_slides_publish,
                                  build=lambda *a: (_ for _ in ()).throw(AssertionError("slides.build must not be used"))),
        "films": SimpleNamespace(items=lambda book: list(film_items or []), build=film_build or (lambda *a: None)),
    }
    return lambda part: mods[part]


VIZ_ITEM = {"kind": "viz", "id": "carry", "code": "GOLDEN//CARRY", "title": {"zh": "进位", "en": "Carry"},
            "summary": {"zh": "摘要", "en": "Summary"}, "href": "viz/carry/", "thumb": "viz/carry/thumb.jpg",
            "hub": "viz/", "lean": [{"gid": GID_3V, "label": "deficit_three_valued", "url": "https://example.org/x"}]}
SLIDES_ITEM = {"kind": "slides", "id": "overview", "languages": ["zh", "en"], "title": {"zh": "概览", "en": "Overview"},
               "blurb": {"zh": "简介", "en": "Blurb"}, "slides": 12,
               "href": {"zh": "slides/overview/", "en": "slides/overview/en/"},
               "pdf": {"zh": "slides/overview/test-book-overview-zh.pdf", "en": "slides/overview/test-book-overview-en.pdf"}}


class SiteCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="tbook-site-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.site = config.load_site()
        self.build_root = self.tmp / "build"
        self.out = self.tmp / "out"

    def run_build(self, books, *, media=None, cover_ok=True, only=None):
        def render_cover(site_, book, edition, out_path, *, fmt="png", **kw):
            if not cover_ok:
                raise RuntimeError("no typst here")
            Path(out_path).write_bytes(PNG)
            return Path(out_path)

        cover_mod = SimpleNamespace(render_cover=render_cover)
        # `from . import cover` reads the package attribute when tbook.cover was imported before.
        with mock.patch.object(site, "_media_module", media or fake_media()), \
             mock.patch.dict("sys.modules", {"tbook.cover": cover_mod}), \
             mock.patch.object(tbook, "cover", cover_mod, create=True), \
             mock.patch("tbook.site._warn"):
            return site.build(self.site, books, self.out, only=only, build_root=self.build_root)


# --------------------------------------------------------------------------- site


class SiteHelpersTest(unittest.TestCase):
    def test_chapter_html(self):
        self.assertEqual(site.chapter_html("ch01.md"), "ch01.html")
        self.assertEqual(site.chapter_html("README.md"), "index.html")
        self.assertEqual(site.chapter_html("part/readme.md"), "part/index.html")
        self.assertEqual(site.chapter_html("a/b.md"), "a/b.html")

    def test_human_size(self):
        self.assertEqual(site.human_size(12), "12 B")
        self.assertEqual(site.human_size(2048), "2 KB")
        self.assertEqual(site.human_size(3 * 1024 * 1024 + 1), "3.0 MB")

    def test_logo(self):
        s = SimpleNamespace(raw={"site": {}}, title={"zh": "书库", "en": "trureturing Books"}, languages=["zh", "en"])
        self.assertEqual(site.logo_text(s), "TRURETURING//BOOKS")
        s.raw = {"site": {"logo": "MY//LIB"}}
        self.assertEqual(site.logo_text(s), "MY//LIB")
        self.assertEqual(site.logo_html("A//<B>"), "A<b>//</b><wbr>&lt;B&gt;")

    def test_strings_both_languages(self):
        for key in site.SITE_I18N["en"]:
            self.assertIn(key, site.SITE_I18N["zh"], key)
            self.assertTrue(site.t("zh", key) and site.t("en", key))
        self.assertEqual(site.t("en", "all_theorems", n=3), "All 3 theorems")
        self.assertEqual(site.t("fr", "skip"), "Skip to content")  # unknown language falls back to English

    def test_bi_collapses_identical(self):
        bi = site.Bi(["zh", "en"])
        self.assertEqual(bi.text(lambda lang: "same"), "same")
        both = bi.text(lambda lang: f"<{lang}>")
        self.assertIn('data-l="zh" lang="zh-CN">&lt;zh&gt;', both)
        self.assertIn('data-l="en" lang="en">&lt;en&gt;', both)
        style = site.lang_style(["zh", "en"])
        self.assertIn(':root[data-lang="zh"] [data-l]:not([data-l="zh"])', style)


class SiteBuildTest(SiteCase):
    def test_full_build(self):
        book = make_book(self.tmp)
        fake_build(self.build_root, book)
        media = fake_media(viz_items=[VIZ_ITEM], slides_items=[SLIDES_ITEM])
        out = self.run_build([book], media=media)
        self.assertEqual(out, self.out)
        for rel in ("index.html", "404.html", "manifest.json", ".nojekyll", "assets/site.css", "assets/site.js",
                    "assets/tokens.css", "assets/favicon.svg", "test-book/index.html", "test-book/zh/index.html",
                    "test-book/en/ch01.html", "test-book/cover-zh.png", "test-book/cover-en.png",
                    "test-book/viz/carry/index.html", "test-book/slides/overview/index.html"):
            self.assertTrue((out / rel).exists(), rel)
        self.assertFalse((out / "test-book" / "zh" / ".nojekyll").exists())
        self.assertNotIn("@@", (out / "assets" / "favicon.svg").read_text())

        index = (out / "index.html").read_text()
        self.assertIn('data-lang="zh"', index)
        self.assertIn('data-langs="zh en"', index)
        self.assertIn("测试之书", index)
        self.assertIn("A Test Book", index)
        self.assertIn('href="test-book/zh/"', index)
        self.assertIn(f'href="test-book/downloads/{book.artifact("zh", "pdf", "screen")}"', index)
        self.assertNotIn(book.artifact("zh", "pdf", "print"), index)  # not built → no link
        self.assertIn('src="test-book/cover-zh.png"', index)
        self.assertIn("<dd>2</dd>", index)  # LEAN ✓ count (two formal envs)

        landing = (out / "test-book" / "index.html").read_text()
        self.assertIn('href="../assets/site.css?v=', landing)
        self.assertIn('href="../"', landing)
        self.assertIn('href="zh/ch01.html"', landing)
        self.assertIn('href="zh/index.html"', landing)  # README.md → index.html
        self.assertIn('href="zh/ch02.html#prob-c"', landing)  # open item links into the book
        self.assertIn('href="en/verification-ledger.html"', landing)
        self.assertIn("T&amp;A", landing)
        self.assertIn('href="viz/carry/"', landing)
        self.assertIn('href="slides/overview/en/"', landing)
        self.assertIn('href="slides/overview/test-book-overview-zh.pdf"', landing)
        self.assertNotIn("test-book-overview-en.pdf", landing)  # PDF missing → no link
        self.assertIn("《测试之书》封面", landing)
        lock = lean.Lock.load()
        if lock:
            self.assertIn(lock.commit[:12], landing)

        manifest = json.loads((out / "manifest.json").read_text())
        self.assertEqual(manifest["schema"], "trureturing-books.site.v1")
        b = manifest["books"][0]
        self.assertEqual(b["slug"], "test-book")
        self.assertEqual(b["version"], "1.2.3")
        self.assertEqual(b["title"], {"zh": "测试之书", "en": "A Test Book"})
        self.assertEqual(b["verified"], 2)
        self.assertEqual(b["open"], 1)
        self.assertEqual(b["media"]["viz"], ["carry"])
        files = {f["path"]: f for f in b["files"]}
        pdf = files[f"test-book/downloads/{book.artifact('en', 'pdf', 'print')}"]
        self.assertEqual((pdf["kind"], pdf["lang"], pdf["variant"]), ("pdf", "en", "print"))
        self.assertEqual(pdf["size"], (out / pdf["path"]).stat().st_size)
        import hashlib
        self.assertEqual(pdf["sha256"], hashlib.sha256((out / pdf["path"]).read_bytes()).hexdigest())
        self.assertIn("test-book/slides/overview/test-book-overview-zh.pdf", files)
        self.assertIn("test-book/cover-zh.png", files)

    def test_links_are_relative(self):
        book = make_book(self.tmp)
        fake_build(self.build_root, book)
        out = self.run_build([book], media=fake_media(viz_items=[VIZ_ITEM], slides_items=[SLIDES_ITEM]))
        for page in (out / "index.html", out / "test-book" / "index.html"):
            for tag, attr, value in parse(page.read_text()).links:
                if value.startswith(("https://", "http://", "#")):
                    continue
                self.assertFalse(value.startswith("/"), f"{page.name}: absolute link {value}")
                target = (page.parent / value.split("#")[0].split("?")[0])
                if value.endswith("/"):
                    target = target / "index.html"
                self.assertTrue(target.exists(), f"{page.relative_to(out)}: broken {attr} {value}")

    def test_escaping(self):
        book = make_book(self.tmp, title_zh='<script>alert("x")</script>', title_en="A & B")
        fake_build(self.build_root, book)
        out = self.run_build([book])
        for page in (out / "index.html", out / "test-book" / "index.html"):
            text = page.read_text()
            self.assertNotIn("<script>alert", text)
            self.assertIn("&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;", text)
            self.assertIn("A &amp; B", text)
            scripts = [t for t, a in parse(text).tags if t == "script"]
            self.assertEqual(len(scripts), 1)  # only assets/site.js

    def test_partial_outputs_and_css_cover(self):
        book = make_book(self.tmp)
        fake_build(self.build_root, book, html_langs=("zh",), dist=False)
        out = self.run_build([book], cover_ok=False)
        self.assertFalse((out / "test-book" / "cover-zh.png").exists())
        index = (out / "index.html").read_text()
        self.assertIn('class="cover-css"', index)
        self.assertIn('href="test-book/zh/"', index)
        self.assertNotIn('href="test-book/en/"', index)
        self.assertNotIn("downloads/", index)
        landing = (out / "test-book" / "index.html").read_text()
        self.assertIn('role="img"', landing)  # the CSS cover carries the alt text
        self.assertNotIn('href="en/ch01.html"', landing)  # en not built: plain TOC entries
        self.assertNotIn('id="viz"', landing)
        self.assertFalse((out / "test-book" / "downloads").exists())

    def test_missing_edition_language(self):
        book = make_book(self.tmp, "zh-only", editions=("zh",))
        fake_build(self.build_root, book, html_langs=("zh",), dist=False)
        out = self.run_build([book])
        landing = (out / "zh-only" / "index.html").read_text()
        self.assertIn("This book has no edition in this language", landing)
        self.assertIn('src="cover-zh.png"', landing)

    def test_stub_media_are_skipped(self):
        book = make_book(self.tmp)
        fake_build(self.build_root, book)

        def not_impl(*a, **k):
            raise NotImplementedError

        media = fake_media(viz_items=[VIZ_ITEM], viz_build=not_impl, slides_items=[SLIDES_ITEM], slides_publish=not_impl)
        out = self.run_build([book], media=media)
        landing = (out / "test-book" / "index.html").read_text()
        self.assertNotIn('id="viz"', landing)  # items exist but nothing was published
        self.assertNotIn('id="slides"', landing)

    def test_media_failure_raises_after_writing(self):
        book = make_book(self.tmp)
        fake_build(self.build_root, book)

        def boom(*a, **k):
            raise ValueError("registry broken")

        with self.assertRaises(site.SiteError) as cm:
            self.run_build([book], media=fake_media(viz_items=[VIZ_ITEM], viz_build=boom))
        self.assertIn("registry broken", str(cm.exception))
        self.assertTrue((self.out / "index.html").exists())
        self.assertTrue((self.out / "test-book" / "index.html").exists())

    def test_only_rebuilds_media(self):
        book = make_book(self.tmp)
        fake_build(self.build_root, book)
        self.run_build([book])
        self.assertNotIn('id="viz"', (self.out / "test-book" / "index.html").read_text())
        shutil.rmtree(self.build_root / "html")  # must not be needed for a media-only rebuild
        self.run_build([book], media=fake_media(viz_items=[VIZ_ITEM]), only={"viz"})
        self.assertTrue((self.out / "test-book" / "zh" / "ch01.html").exists())
        self.assertIn('id="viz"', (self.out / "test-book" / "index.html").read_text())
        with self.assertRaises(site.SiteError):
            self.run_build([book], only={"html"})

    def test_refuses_to_wipe_foreign_directory(self):
        self.out.mkdir()
        write(self.out / "precious.txt", "keep me")
        with self.assertRaises(site.SiteError):
            self.run_build([])
        self.assertTrue((self.out / "precious.txt").exists())
        shutil.rmtree(self.out)
        self.run_build([])  # empty library still renders
        self.assertIn("./tbook new-book", (self.out / "index.html").read_text())
        write(self.out / "stale.txt", "old")
        self.run_build([])  # a site built here before may be replaced
        self.assertFalse((self.out / "stale.txt").exists())

    def test_404_is_self_contained(self):
        out = self.run_build([])
        text = (out / "404.html").read_text()
        self.assertIn("SIGNAL LOST", text)
        self.assertIn("--tr-cyan", text)  # tokens inlined
        for _tag, _attr, value in parse(text).links:
            self.assertFalse(value.startswith(("assets/", "../")), value)
        self.assertIn(f'href="{serve.base_path(self.site)}"', text)


# --------------------------------------------------------------------------- serve


class ServeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="tbook-serve-"))
        write(cls.tmp / "index.html", "<!doctype html><title>home</title>")
        write(cls.tmp / "404.html", "<!doctype html><title>SIGNAL LOST</title>")
        write(cls.tmp / "book" / "index.html", "book")
        for name in ("a.mjs", "b.wasm", "c.woff2", "d.epub", "e.json"):
            (cls.tmp / "book" / name).write_bytes(b"x")
        cls.server = serve.make_server(0, cls.tmp, base="/repo/")
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def get(self, path: str):
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *a, **k):
                return None

        opener = urllib.request.build_opener(NoRedirect)
        with mock.patch("sys.stderr"):
            try:
                with opener.open(f"http://127.0.0.1:{self.port}{path}", timeout=5) as r:
                    return r.status, r.headers, r.read()
            except urllib.error.HTTPError as e:
                return e.code, e.headers, e.read()

    def test_redirects_to_base(self):
        for path in ("/", "/repo"):
            code, headers, _ = self.get(path)
            self.assertEqual(code, 301, path)
            self.assertEqual(headers["Location"], "/repo/")
        code, headers, _ = self.get("/repo/book")
        self.assertEqual((code, headers["Location"]), (301, "/repo/book/"))

    def test_serves_under_base(self):
        code, headers, body = self.get("/repo/")
        self.assertEqual(code, 200)
        self.assertIn(b"home", body)
        self.assertTrue(headers["Content-Type"].startswith("text/html"))
        self.assertEqual(self.get("/repo/book/")[2], b"book")

    def test_not_found(self):
        for path in ("/repo/missing.html", "/elsewhere/", "/repo/../index.html"):
            code, _, body = self.get(path)
            self.assertEqual(code, 404, path)
            self.assertIn(b"SIGNAL LOST", body)

    def test_mime_types(self):
        expected = {"a.mjs": "text/javascript", "b.wasm": "application/wasm", "c.woff2": "font/woff2",
                    "d.epub": "application/epub+zip", "e.json": "application/json"}
        for name, mime in expected.items():
            code, headers, _ = self.get(f"/repo/book/{name}")
            self.assertEqual(code, 200)
            self.assertTrue(headers["Content-Type"].startswith(mime), (name, headers["Content-Type"]))

    def test_base_path(self):
        self.assertEqual(serve.base_path(SimpleNamespace(base_url="https://o.github.io/repo/")), "/repo/")
        self.assertEqual(serve.base_path(SimpleNamespace(base_url="https://o.github.io/")), "/")
        self.assertEqual(serve.base_path(SimpleNamespace(base_url="")), "/")

    def test_serve_requires_built_site(self):
        with tempfile.TemporaryDirectory() as empty, mock.patch("sys.stderr"):
            self.assertEqual(serve.serve(port=0, directory=empty), 1)


# --------------------------------------------------------------------------- doctor


class DoctorTest(unittest.TestCase):
    def test_required_classification(self):
        self.assertTrue(doctor.Check("x", False, targets=("html",)).is_required)
        self.assertFalse(doctor.Check("x", False, targets=("slides",)).is_required)
        self.assertFalse(doctor.Check("x", False, targets=("pdf",), required=False).is_required)
        self.assertEqual(doctor.Check("x", False, targets=("viz",)).mark, "!")
        self.assertEqual(doctor.Check("x", False, targets=("check",)).mark, "✗")

    def test_target_gaps(self):
        r = doctor.Report([doctor.Check("mdBook", False, targets=("html",)),
                           doctor.Check("Chromium", False, targets=("slides",)),
                           doctor.Check("ok", True, targets=("pdf",))])
        gaps = r.target_gaps()
        self.assertEqual(gaps["html"], ["mdBook"])
        self.assertEqual(gaps["site"], ["mdBook"])
        self.assertEqual(gaps["slides"], ["Chromium"])
        self.assertEqual(gaps["pdf"], [])
        self.assertEqual([c.label for c in r.blocking()], ["mdBook"])

    def test_mdbook_from_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            exe = Path(tmp) / "mdbook"
            exe.write_text("#!/bin/sh\necho 'mdbook v0.5.4'\n")
            exe.chmod(exe.stat().st_mode | stat.S_IXUSR)
            with mock.patch.dict(os.environ, {"MDBOOK": str(exe)}):
                r = doctor.Report()
                doctor.check_mdbook(r)
                self.assertTrue(r.checks[0].ok, r.checks[0])
                self.assertIn("0.5.4", r.checks[0].label)
            exe.write_text("#!/bin/sh\necho 'mdbook v0.4.40'\n")
            with mock.patch.dict(os.environ, {"MDBOOK": str(exe)}):
                r = doctor.Report()
                doctor.check_mdbook(r)
                self.assertFalse(r.checks[0].ok)
                self.assertIn("cargo install mdbook --version 0.5.4 --locked", r.checks[0].hint)
        with mock.patch.dict(os.environ, {"MDBOOK": "/nonexistent/mdbook"}):
            r = doctor.Report()
            doctor.check_mdbook(r)
            self.assertFalse(r.checks[0].ok)

    def test_run_exit_code(self):
        good = doctor.Report([doctor.Check("a", True, targets=("check",)), doctor.Check("b", False, targets=("films",))])
        bad = doctor.Report([doctor.Check("a", False, targets=("check",), hint="do x")])
        with mock.patch.object(doctor, "collect", return_value=good), mock.patch("builtins.print"):
            self.assertEqual(doctor.run(), 0)
        with mock.patch.object(doctor, "collect", return_value=bad), mock.patch("builtins.print") as p:
            self.assertEqual(doctor.run(), 1)
            printed = "\n".join(str(c.args[0]) for c in p.call_args_list if c.args)
            self.assertIn("fix: do x", printed)

    def test_collect_runs_offline(self):
        with mock.patch.object(doctor, "check_trureturing"):  # avoid the network probe
            report = doctor.collect()
        labels = " ".join(c.label for c in report.checks)
        for needle in ("Python", "Pandoc", "typst", "mdBook", "Node.js", "Chromium", "font"):
            self.assertIn(needle.lower(), labels.lower())


# --------------------------------------------------------------------------- leanverify


def sample_lock() -> lean.Lock:
    return lean.Lock(repo="the-omega-institute/trureturing", branch="dev", commit="a" * 40, pinned_at="2026-01-01T00:00:00Z",
                     declarations={
                         GID_3V: {"module": "D5/S1/Deficit/DeficitThreeValued", "name": "D5.S1.Deficit.deficit_three_valued",
                                  "kind": "theorem", "statement_id": "sha256:x"},
                         "D5/S1/X/Y.«weird name».0": {"module": "D5/S1/X/Y", "name": "D5.S1.X.«weird.na\"me».0",
                                                      "kind": "def"},
                     })


class LeanVerifyTest(unittest.TestCase):
    def test_split_name(self):
        self.assertEqual(leanverify.split_name("D5.S1.Deficit.deficit"), ["D5", "S1", "Deficit", "deficit"])
        self.assertEqual(leanverify.split_name("A.«b.c».x"), ["A", "b.c", "x"])
        self.assertEqual(leanverify.split_name("A.«12».3"), ["A", "12", 3])
        self.assertEqual(leanverify.split_name("v₁.x'"), ["v₁", "x'"])
        for bad in ("", "A..B", "A.", "A.«b", ".A", "A.b»"):
            with self.assertRaises(leanverify.LeanVerifyError, msg=bad):
                leanverify.split_name(bad)

    def test_lean_string_and_name_expr(self):
        self.assertEqual(leanverify.lean_string('a"b\\c\n'), '"a\\"b\\\\c\\n"')
        self.assertEqual(leanverify.name_expr(["A", 2, "b"]),
                         'Lean.Name.mkStr (Lean.Name.mkNum (Lean.Name.mkStr (Lean.Name.anonymous) "A") 2) "b"')

    def test_generate(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = leanverify.generate(Path(tmp) / "lv", lock=sample_lock(), toolchain="leanprover/lean4:v4.35.0")
            self.assertEqual((out / "lean-toolchain").read_text(), "leanprover/lean4:v4.35.0\n")
            lake = (out / "lakefile.toml").read_text()
            self.assertIn('name = "bookverify"', lake)
            self.assertIn('git = "https://github.com/the-omega-institute/trureturing"', lake)
            self.assertIn(f'rev = "{"a" * 40}"', lake)
            self.assertIn('[[lean_lib]]\nname = "BookVerify"', lake)
            import tomllib
            parsed = tomllib.loads(lake)
            self.assertEqual(parsed["require"][0]["name"], "trureturing")
            src = (out / "BookVerify.lean").read_text()
            lines = src.splitlines()
            imports = [ln for ln in lines if ln.startswith("import ")]
            self.assertEqual(imports, ["import Lean", "import D5.S1.Deficit.DeficitThreeValued", "import D5.S1.X.Y"])
            first_code = next(i for i, ln in enumerate(lines) if ln and not ln.startswith(("--", "import")))
            self.assertTrue(all(not ln.startswith("import ") for ln in lines[first_code:]))  # imports come first
            self.assertIn('Lean.Name.mkStr (Lean.Name.mkStr (Lean.Name.mkStr (Lean.Name.mkStr (Lean.Name.anonymous) "D5") "S1") '
                          '"Deficit") "deficit_three_valued"', src)
            self.assertIn('Lean.Name.mkNum (Lean.Name.mkStr (Lean.Name.mkStr (Lean.Name.mkStr (Lean.Name.mkStr '
                          '(Lean.Name.anonymous) "D5") "S1") "X") "weird.na\\"me") 0', src)
            self.assertIn('kind := "def"', src)
            for needle in ("Lean.collectAxioms c.name", "env.getModuleIdxFor? c.name", "env.header.moduleNames",
                           "``propext, ``Classical.choice, ``Quot.sound", "``sorryAx", "run_cmd do", "throwError",
                           "| .thmInfo _ => \"theorem\"", "| .defnInfo _ => \"def\""):
                self.assertIn(needle, src)
            self.assertEqual(src.count("{ gid := "), 2)
            script = out / "verify.sh"
            self.assertTrue(os.access(script, os.X_OK))
            self.assertIn("lake exe cache get || true", script.read_text())
            self.assertIn("lake build BookVerify", script.read_text())
            readme = (out / "README.md").read_text()
            self.assertIn(GID_3V, readme)
            # deterministic
            again = leanverify.generate(Path(tmp) / "lv2", lock=sample_lock(), toolchain="leanprover/lean4:v4.35.0")
            self.assertEqual(src, (again / "BookVerify.lean").read_text())

    def test_errors(self):
        lock = sample_lock()
        lock.declarations[GID_3V]["kind"] = "lemma"
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(leanverify.LeanVerifyError):
            leanverify.generate(tmp, lock=lock, toolchain="leanprover/lean4:v4.35.0")
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(leanverify.LeanVerifyError):
            leanverify.generate(tmp, lock=sample_lock(), toolchain="not a toolchain")
        ledger = SimpleNamespace(read=lambda commit, path: None)
        with self.assertRaises(leanverify.LeanVerifyError):
            leanverify.read_toolchain(sample_lock(), ledger)
        self.assertTrue(issubclass(leanverify.LeanVerifyError, config.ConfigError))

    def test_empty_lock(self):
        lock = sample_lock()
        lock.declarations = {}
        with tempfile.TemporaryDirectory() as tmp:
            src = (leanverify.generate(tmp, lock=lock, toolchain="leanprover/lean4:v4.35.0") / "BookVerify.lean").read_text()
            self.assertIn("def cited : Array Cited := #[]", src)
            self.assertEqual([ln for ln in src.splitlines() if ln.startswith("import ")], ["import Lean"])

    @unittest.skipUnless(paths.LOCK_FILE.exists() and any(
        (Path(p) / ".git").exists() for p in (os.environ.get("TRURETURING_DIR") or "/nonexistent", paths.ROOT.parent / "trureturing")),
        "needs trureturing.lock.json and a trureturing checkout")
    def test_real_lock(self):
        lock = lean.Lock.load()
        with tempfile.TemporaryDirectory() as tmp:
            out = leanverify.generate(tmp)
            toolchain = (out / "lean-toolchain").read_text().strip()
            self.assertRegex(toolchain, r"^leanprover/lean4:v\d+\.\d+")
            src = (out / "BookVerify.lean").read_text()
            for gid, d in lock.declarations.items():
                self.assertIn(f"import {d['module'].replace('/', '.')}", src)
                self.assertIn(f'gid := "{gid}"', src)
            self.assertIn(lock.commit, (out / "lakefile.toml").read_text())


if __name__ == "__main__":
    unittest.main()
