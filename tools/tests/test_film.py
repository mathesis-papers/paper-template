"""Tests for tbook.film (book-local films) and the stdlib parts of the pipeline in theme/film/.

Run: PYTHONPATH=tools .venv/bin/python -m unittest discover -s tools/tests -p 'test_film.py'
Node-dependent tests are skipped when ``node`` is not on PATH. Rendering (Chromium, ffmpeg) and the
audio steps (Kokoro, numpy) are not run here; see theme/film/film.sh.
"""

from __future__ import annotations

import io
import json
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace

from tbook import config, film, lean, mdscan, paths, render

NODE = film.node_executable()
EXAMPLE = paths.BOOKS / "example-monograph"
EXAMPLE_FILM = EXAMPLE / "films" / "001-golden-deficit"
GID3 = "D5/S1/Deficit/DeficitThreeValued.deficit_three_valued"
GIDI = "D5/S1/Deficit/DeficitInteger.deficit_integer"
THEME_FILM = paths.THEME / "film"


def example_book() -> config.Book:
    return config.load_book("example-monograph")


def temp_book(root: Path, slug: str = "film-fixture") -> config.Book:
    """A real (loadable) book in a temporary directory, with an empty films/ directory."""
    bdir = root / slug
    (bdir / "films").mkdir(parents=True)
    (bdir / "book.toml").write_text('[book]\ncode = "FIX//FILM"\neditions = ["zh", "en"]\n'
                                    '[book.title]\nzh = "测试书"\nen = "Test Book"\n', encoding="utf-8")
    return config.load_book(bdir)


def copy_example(book: config.Book, name: str = "001-golden-deficit") -> Path:
    """Copy the example film's sources into ``book`` with the book's release tag and asset names."""
    dst = book.films_dir / name
    shutil.copytree(EXAMPLE_FILM, dst, ignore=shutil.ignore_patterns("out"))
    meta = json.loads((dst / "film.json").read_text(encoding="utf-8"))
    num = name[:3]
    meta["id"] = name
    meta["release_tag"] = film.default_tag(book.slug, num)
    outs = film.default_outputs(book.slug, num)
    meta["outputs"] = {k: outs[k] for k in film.REQUIRED_OUTPUTS + film.OPTIONAL_OUTPUTS}
    (dst / "film.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return dst


def errors(issues) -> list[str]:
    return [i.message for i in issues if i.severity == "error"]


def ctx_for(book: config.Book, lang: str, target: str) -> render.RenderContext:
    site = config.load_site()
    return render.RenderContext(site=site, book=book, edition=book.edition(lang), model=None,
                                lock=lean.Lock.load(), target=target)


def env_for(src: str):
    return SimpleNamespace(attrs=mdscan.Attrs(classes=["film"], kv={"src": src}), kind="film")


def doc_for(book: config.Book, lang: str, chapter: str = "ch01-golden-deficit.md"):
    return SimpleNamespace(path=book.dir / lang / chapter, chapter=SimpleNamespace(path=chapter))


class ExampleFilmTest(unittest.TestCase):
    def test_example_film_is_valid(self):
        book = example_book()
        issues = film.check(book)
        self.assertEqual(errors(issues), [], [i.format() for i in issues])

    def test_example_cites_locked_theorems(self):
        f = film.get(example_book(), "001-golden-deficit")
        self.assertIsNotNone(f)
        self.assertEqual(sorted(f.lean), sorted([GID3, GIDI]))
        lock = lean.Lock.load()
        self.assertTrue(lock.commit.startswith(f.meta["subject_commit"]))
        for gid in f.lean:
            self.assertEqual(lock.get(gid).kind, "theorem")

    def test_example_poster_is_small(self):
        poster = EXAMPLE_FILM / "poster.jpg"
        self.assertTrue(poster.is_file())
        self.assertLess(poster.stat().st_size, film.POSTER_MAX_BYTES)
        self.assertEqual(poster.read_bytes()[:3], b"\xff\xd8\xff")

    def test_example_duration_matches_provisional_timing(self):
        f = film.get(example_book(), "001-golden-deficit")
        tl = film.provisional_timeline(f.script)
        self.assertEqual(film.format_duration(tl["duration"]), f.meta["duration"])

    def test_cited_gids(self):
        gids = [g for _, _, g in film.cited_gids(example_book())]
        self.assertIn(GID3, gids)


class CheckRefTest(unittest.TestCase):
    def setUp(self):
        self.book = example_book()

    def test_local(self):
        self.assertIsNone(film.check_ref(self.book, "001-golden-deficit"))

    def test_missing_local(self):
        msg = film.check_ref(self.book, "009-nothing-here")
        self.assertIn("not found", msg)
        self.assertIn("001-golden-deficit", msg)

    def test_bad_names(self):
        for src in ("golden-deficit", "1-golden", "001_golden", "../001-golden-deficit"):
            self.assertIsNotNone(film.check_ref(self.book, src), src)
        self.assertIn("needs src", film.check_ref(self.book, ""))

    def test_external(self):
        self.assertIsNone(film.check_ref(self.book, "trureturing-film:film-001-v1"))
        self.assertIsNone(film.check_ref(self.book, "trureturing-film:film-129-v12"))
        for src in ("trureturing-film:001", "trureturing-film:film-1-v1", "trureturing-film:film-001-v0",
                    "trureturing-film:film-001"):
            self.assertIn("trureturing-film:film-<NNN>-v<k>", film.check_ref(self.book, src), src)


class ValidationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.book = temp_book(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_copied_example_is_valid(self):
        copy_example(self.book)
        self.assertEqual(errors(film.check(self.book)), [])

    def test_meta_errors(self):
        d = copy_example(self.book)
        meta = json.loads((d / "film.json").read_text(encoding="utf-8"))
        meta.update(id="002-other", duration="57s", resolution="1280x720@30", subtitles=["fr"],
                    lean=["D5/S1/Deficit/DeficitInteger.not_a_locked_name", "not a gid"],
                    release_tag="film-another-book-001-v1", subject_commit="XYZ")
        meta["outputs"]["cover"] = "cover.png"
        del meta["title_zh"]
        (d / "film.json").write_text(json.dumps(meta), encoding="utf-8")
        msgs = "\n".join(errors(film.check(self.book)))
        for needle in ("id must equal the directory name", "duration must look like m:ss", "1920x1080",
                       "subtitles", "not in trureturing.lock.json", "not a declaration GID",
                       "must start with film-film-fixture-001-", "subject_commit", "outputs.cover", "title_zh"):
            self.assertIn(needle, msgs)

    def test_stale_subject_commit_is_a_warning(self):
        d = copy_example(self.book)
        meta = json.loads((d / "film.json").read_text(encoding="utf-8"))
        meta["subject_commit"] = "0123456789abcdef"
        (d / "film.json").write_text(json.dumps(meta), encoding="utf-8")
        issues = film.check(self.book)
        self.assertEqual(errors(issues), [])
        self.assertTrue(any("not the pinned commit" in i.message for i in issues if i.severity == "warning"))

    def test_script_errors(self):
        d = copy_example(self.book)
        script = {"voice": "", "speed": 5, "scenes": [
            {"id": "Bad-Id", "lead": 1, "tail": 1, "lines": [["only english"]]},
            {"id": "ok", "lead": -1, "tail": 1, "lines": [["a", "甲"]], "music": [1, 2],
             "cues": [{"line": 4, "at": 1, "kind": "boom"}]},
            {"id": "ok", "lead": 0, "tail": 0, "lines": []},
        ]}
        (d / "script.json").write_text(json.dumps(script), encoding="utf-8")
        msgs = "\n".join(errors(film.check(self.book)))
        for needle in ("voice is required", "speed must be", "lowercase identifier", "two non-empty strings",
                       "lead must be", "music must list 5 levels", "cue", "duplicate scene id", "non-empty list"):
            self.assertIn(needle, msgs)

    def test_invalid_json_and_layout(self):
        d = copy_example(self.book)
        (d / "script.json").write_text("{not json", encoding="utf-8")
        (d / "notes.txt").write_text("x", encoding="utf-8")
        (self.book.films_dir / "stray.md").write_text("x", encoding="utf-8")
        (self.book.films_dir / "001-twin").mkdir()
        issues = film.check(self.book)
        msgs = "\n".join(i.message for i in issues)
        self.assertIn("invalid JSON", msgs)
        self.assertIn("not a film source file", msgs)
        self.assertIn("films/ holds film directories", msgs)
        self.assertIn("film number 001 is used twice", msgs)

    def test_missing_scene_definition_warns(self):
        d = copy_example(self.book)
        script = json.loads((d / "script.json").read_text(encoding="utf-8"))
        script["scenes"].append({"id": "extra", "lead": 0.5, "tail": 0.5, "lines": [["More.", "更多。"]]})
        (d / "script.json").write_text(json.dumps(script, ensure_ascii=False), encoding="utf-8")
        issues = film.check(self.book)
        self.assertTrue(any("SCENES.extra" in i.message for i in issues if i.severity == "warning"))

    @unittest.skipUnless(NODE, "node not available")
    def test_scene_syntax_error(self):
        d = copy_example(self.book)
        (d / "scenes.js").write_text("SCENES.zeck = S => { txt('x', 1, 2 ;\n", encoding="utf-8")
        self.assertTrue(any("JavaScript syntax error" in m for m in errors(film.check(self.book))))

    def test_scene_ids_defined(self):
        js = "SCENES.a = S => {};\nSCENES['b-c'] = S => {};\nif (SCENES.d === 1) {}\nSCENES . e=x"
        self.assertEqual(film.scene_ids_defined(js), {"a", "b-c", "e"})


class TimelineTest(unittest.TestCase):
    SCRIPT = {"voice": "af_heart", "speed": 1.0, "scenes": [
        {"id": "one", "lead": 1.5, "tail": 0.5, "lines": [["One two three four five six.", "一"], ["Hi.", "二"]]},
        {"id": "two", "lead": 0.25, "tail": 2.0, "lines": [["Seven eight nine ten eleven twelve thirteen.", "三"]]},
    ]}

    def test_accounting(self):
        tl = film.provisional_timeline(self.SCRIPT, wps=2.0)
        self.assertTrue(tl["provisional"])
        l0, l1, l2 = tl["lines"]
        self.assertEqual(l0["start"], 1.5)
        self.assertAlmostEqual(l0["end"] - l0["start"], 6 / 2.0 + film.LINE_PAD_SECONDS, places=3)
        self.assertAlmostEqual(l1["start"], l0["end"] + film.LINE_GAP_SECONDS, places=3)
        self.assertAlmostEqual(l1["end"] - l1["start"], film.MIN_LINE_SECONDS, places=3)  # short lines get a floor
        s0, s1 = tl["scenes"]
        self.assertEqual(s0["start"], 0.0)
        self.assertAlmostEqual(s0["end"], l1["end"] + 0.5, places=3)
        self.assertAlmostEqual(l2["start"], s1["start"] + 0.25, places=3)
        self.assertAlmostEqual(tl["duration"], s1["end"], places=3)
        self.assertAlmostEqual(s1["end"], l2["end"] + 2.0, places=3)
        self.assertEqual([ln["i"] for ln in tl["lines"]], [0, 1, 2])
        self.assertEqual([ln["scene"] for ln in tl["lines"]], ["one", "one", "two"])

    def test_rate_and_matches(self):
        slow, fast = film.provisional_timeline(self.SCRIPT, 1.0), film.provisional_timeline(self.SCRIPT, 4.0)
        self.assertGreater(slow["duration"], fast["duration"])
        self.assertIsNone(film.timeline_matches(slow, self.SCRIPT))
        changed = json.loads(json.dumps(self.SCRIPT))
        changed["scenes"][1]["lines"][0][0] = "Different words now."
        self.assertIn("line 2 differs", film.timeline_matches(slow, changed))
        changed["scenes"][1]["id"] = "renamed"
        self.assertIn("scene ids", film.timeline_matches(slow, changed))
        with self.assertRaises(ValueError):
            film.provisional_timeline(self.SCRIPT, 0)

    def test_durations(self):
        self.assertEqual(film.format_duration(56.992), "0:57")
        self.assertEqual(film.format_duration(414.4), "6:54")
        self.assertEqual(film.parse_duration("6:54"), 414)
        self.assertIsNone(film.parse_duration("6:61"))


class NamesTest(unittest.TestCase):
    def test_tags_and_assets(self):
        self.assertEqual(film.parse_tag("film-example-monograph-001-v2"), ("example-monograph", "001", 2))
        self.assertIsNone(film.parse_tag("film-001-v1"))
        self.assertIsNone(film.parse_tag("film-x-01-v1"))
        outs = film.default_outputs("example-monograph", "001")
        self.assertEqual(outs["narrated"], "example-monograph_001_narrated_EN_subs_ZH-EN.mp4")
        self.assertEqual(outs["cover"], "example-monograph_001_cover.jpg")
        self.assertEqual(film.release_asset_url("o/r", "t", "a.mp4"), "https://github.com/o/r/releases/download/t/a.mp4")
        self.assertEqual(film.release_asset_url("", "t", "a.mp4"), "")

    def test_external(self):
        ext = film.external_ref("trureturing-film:film-010-v1")
        self.assertEqual(ext["narrated"], "https://github.com/the-omega-institute/trureturing-film/releases/download/"
                                          "film-010-v1/TRURETURING_010_narrated_EN_subs_ZH-EN.mp4")
        self.assertEqual(ext["cover"], "https://github.com/the-omega-institute/trureturing-film/releases/download/"
                                       "film-010-v1/TRURETURING_010_cover.jpg")
        self.assertIsNone(film.external_ref("001-golden-deficit"))


class EmbedTest(unittest.TestCase):
    def setUp(self):
        self.book = example_book()
        self.site = config.load_site()

    def test_mdbook_local(self):
        ctx = ctx_for(self.book, "zh", "mdbook")
        out = film.render_embed(env_for("001-golden-deficit"), ctx, "\n图注 **加粗**。\n", doc_for(self.book, "zh"))
        self.assertIn('<figure class="tr-media tr-film" data-film="001-golden-deficit">', out)
        self.assertIn('<video class="tr-film-player" controls preload="none" playsinline '
                      'poster="../films/001-golden-deficit/poster.jpg"', out)
        if self.site.repo:
            url = (f"https://github.com/{self.site.repo}/releases/download/film-example-monograph-001-v1/"
                   "example-monograph_001_narrated_EN_subs_ZH-EN.mp4")
            self.assertIn(f'<source src="{url}" type="video/mp4">', out)
            self.assertIn(f'<a href="{url}" target="_blank" rel="noopener">▶ 观看</a>', out)
            self.assertIn("/releases/tag/film-example-monograph-001-v1", out)
        self.assertIn('<figcaption class="tr-media-caption">\n\n图注 **加粗**。\n\n<div class="tr-media-links">', out)
        self.assertIn('href="../films/index.html?lang=zh#001-golden-deficit">视频页</a>', out)
        self.assertEqual(ctx.issues, [])

    def test_mdbook_nested_chapter_and_default_caption(self):
        ctx = ctx_for(self.book, "en", "mdbook")
        out = film.render_embed(env_for("001-golden-deficit"), ctx, "", doc_for(self.book, "en", "part/ch.md"))
        self.assertIn('poster="../../films/001-golden-deficit/poster.jpg"', out)
        self.assertIn("Film 001 · The Golden Deficit · 0:57", out)
        self.assertIn(">Film page</a>", out)

    def test_mdbook_external(self):
        ctx = ctx_for(self.book, "en", "mdbook")
        out = film.render_embed(env_for("trureturing-film:film-001-v1"), ctx, "", doc_for(self.book, "en"))
        base = "https://github.com/the-omega-institute/trureturing-film/releases/download/film-001-v1/"
        self.assertIn(f'poster="{base}TRURETURING_001_cover.jpg"', out)
        self.assertIn(f'<source src="{base}TRURETURING_001_narrated_EN_subs_ZH-EN.mp4"', out)
        self.assertIn("Film from trureturing-film · film-001-v1", out)

    def test_mdbook_bad_src_is_reported(self):
        ctx = ctx_for(self.book, "zh", "mdbook")
        out = film.render_embed(env_for("404-missing"), ctx, "", doc_for(self.book, "zh"))
        self.assertIn("tr-film", out)
        self.assertTrue(any("not found" in m for m in ctx.issues))

    def test_pandoc_local(self):
        ctx = ctx_for(self.book, "zh", "pandoc")
        out = film.render_embed(env_for("001-golden-deficit"), ctx, "图注。", doc_for(self.book, "zh"))
        lines = out.splitlines()
        self.assertEqual(lines[0], "::: {.tr-media .tr-film}")
        self.assertEqual(lines[-1], ":::")
        self.assertIn("![视频 001 · 黄金亏量 · 0:57](_book/films/001-golden-deficit/poster.jpg){width=100%}", out)
        self.assertIn((EXAMPLE_FILM / "poster.jpg").resolve(), ctx.book_files)
        self.assertIn("图注。", out)
        self.assertIn("视频见\\", out)
        if self.site.base_url:
            self.assertIn(f"<{self.site.base_url}example-monograph/films/#001-golden-deficit>", out)

    def test_pandoc_nested_and_external(self):
        ctx = ctx_for(self.book, "en", "pandoc")
        out = film.render_embed(env_for("001-golden-deficit"), ctx, "", doc_for(self.book, "en", "part/ch.md"))
        self.assertIn("](../_book/films/001-golden-deficit/poster.jpg)", out)
        self.assertIn("**Film 001 · The Golden Deficit · 0:57**", out)
        self.assertIn("Film:\\", out)
        ctx = ctx_for(self.book, "en", "pandoc")
        out = film.render_embed(env_for("trureturing-film:film-003-v1"), ctx, "Caption.", doc_for(self.book, "en"))
        self.assertNotIn("![", out)
        self.assertIn("**Film from trureturing-film · film-003-v1**", out)
        self.assertIn("<https://github.com/the-omega-institute/trureturing-film/releases/tag/film-003-v1>", out)
        self.assertEqual(ctx.book_files, set())


class PublishTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_items(self):
        items = film.items(example_book())
        self.assertEqual(len(items), 1)
        it = items[0]
        self.assertEqual((it["kind"], it["id"], it["number"]), ("film", "001-golden-deficit", "001"))
        self.assertEqual(it["title"]["zh"], "黄金亏量")
        self.assertEqual(it["title"]["en"], "The Golden Deficit")
        self.assertEqual(it["poster"], "films/001-golden-deficit/poster.jpg")
        self.assertEqual(it["href"], "films/index.html#001-golden-deficit")
        self.assertEqual({r["gid"] for r in it["lean"]}, {GID3, GIDI})
        self.assertTrue(all(r["url"].startswith("https://github.com/the-omega-institute/trureturing/blob/") for r in it["lean"]))

    def test_build(self):
        out = self.tmp / "films"
        film.build(config.load_site(), example_book(), out)
        page = (out / "index.html").read_text(encoding="utf-8")
        for needle in ("黄金亏量", "The Golden Deficit", 'id="001-golden-deficit"', "LEAN ✓",
                       "D5.S1.Deficit.deficit_three_valued", 'href="assets/films.css"', "data-lang-set"):
            self.assertIn(needle, page)
        self.assertTrue((out / "001-golden-deficit" / "poster.jpg").is_file())
        for name in ("tokens.css", "films.css", "films.js"):
            self.assertTrue((out / "assets" / name).is_file())
        data = json.loads((out / "films.json").read_text(encoding="utf-8"))
        self.assertEqual(data["films"][0]["release_tag"], "film-example-monograph-001-v1")
        self.assertEqual(data["trureturing"]["commit"], lean.Lock.load().commit)

    def test_build_refuses_errors(self):
        book = temp_book(self.tmp / "books")
        d = copy_example(book)
        (d / "film.json").write_text("{}", encoding="utf-8")
        with self.assertRaises(film.FilmError):
            film.build(config.load_site(), book, self.tmp / "out")

    def test_release_notes(self):
        notes = film.release_notes(film.get(example_book(), "001-golden-deficit"), "abc123")
        self.assertIn("The Golden Deficit", notes)
        self.assertIn("LEAN ✓", notes)
        self.assertIn(GID3, notes)
        self.assertIn("at abc123", notes)
        self.assertIn("example-monograph_001_cover.jpg", notes)


class ScaffoldTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.book = temp_book(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_new_film_is_valid(self):
        created = film.scaffold(self.book, "002-carry-rules", "进位规则", "The Carry Rules", released="2026-11-08")
        self.assertEqual([p.name for p in created], ["film.json", "script.json", "scenes.js"])
        meta = json.loads(created[0].read_text(encoding="utf-8"))
        self.assertEqual(meta["release_tag"], "film-film-fixture-002-v1")
        self.assertEqual(meta["title_zh"], "进位规则")
        self.assertEqual(meta["subject_commit"], lean.Lock.load().commit)
        issues = film.check(self.book)
        self.assertEqual(errors(issues), [], [i.format() for i in issues])
        self.assertNotIn("@@", "".join(p.read_text(encoding="utf-8") for p in created))

    def test_scaffold_rejects(self):
        film.scaffold(self.book, "002-carry-rules", "进位", "Carry")
        for args in (("002-other", "甲", "A"), ("002-carry-rules", "甲", "A"), ("carry", "甲", "A"),
                     ("003-x", "", "A"), ("003-y", '引"号', "A")):
            with self.assertRaises(film.FilmError, msg=str(args)):
                film.scaffold(self.book, *args)

    def test_cli(self):
        args = SimpleNamespace(action="new", rest=[str(self.book.dir), "004-cli-made", "命令行", "From the CLI"])
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            self.assertEqual(film.cli(args), 0)
        self.assertTrue((self.book.films_dir / "004-cli-made" / "scenes.js").is_file())
        with redirect_stdout(io.StringIO()), redirect_stderr(err):
            self.assertEqual(film.cli(SimpleNamespace(action="new", rest=["only-one"])), 2)
            self.assertEqual(film.cli(SimpleNamespace(action="list", rest=["example-monograph"])), 0)
            self.assertEqual(film.cli(SimpleNamespace(action="list", rest=["no-such-book"])), 1)


class PipelineTest(unittest.TestCase):
    """The stdlib parts of theme/film: tokens, page assembly (without fonts), JavaScript syntax."""

    @classmethod
    def setUpClass(cls):
        import importlib.util

        # theme/film/build.py imports its sibling common.py; load it under a private name.
        sys.path.insert(0, str(THEME_FILM))
        try:
            spec = importlib.util.spec_from_file_location("tbook_test_film_build", THEME_FILM / "build.py")
            cls.build = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(cls.build)
        finally:
            sys.path.remove(str(THEME_FILM))

    def test_tokens_from_generated_mjs(self):
        tok = self.build.film_tokens()
        tokens = json.loads(paths.TOKENS.read_text(encoding="utf-8"))
        self.assertEqual(tok["film"], tokens["film"])
        self.assertEqual(tok["sem"]["lean"], tokens["film"]["green"])
        self.assertEqual(tok["sem"]["open"], tokens["film"]["red"])
        self.assertEqual(tok["sem"]["argued"], tokens["film"]["vio"])
        self.assertEqual(tok["sem"]["now"], tokens["film"]["gold"])
        self.assertEqual(tok["font"]["film-display"][0], "Orbitron")

    def test_unicode_ranges(self):
        self.assertEqual(self.build._ranges("U+0000-00FF, U+0131,U+4??"), [(0, 255), (0x131, 0x131), (0x400, 0x4FF)])

    def test_assemble_page(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            book = temp_book(tmp)
            d = copy_example(book)
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                page = self.build.build(d)
            html = page.read_text(encoding="utf-8")
            self.assertIn("window.FILM_TOKENS=", html)
            self.assertIn('"provisional":true', html)
            self.assertIn("SCENES.zeck", html)
            self.assertIn("window.ready = boot()", html)
            self.assertNotIn("</script>\n<script>\n</script>", html)
            self.assertTrue((d / "out" / "timeline.provisional.json").is_file())
            data = json.loads(html.split("window.DATA=", 1)[1].split(";</script>", 1)[0].replace("<\\/", "</"))
            self.assertEqual(data["book"]["title"]["en"], "Test Book")
            self.assertEqual({r["short"] for r in data["lean"]}, {"deficit_three_valued", "deficit_integer"})
            self.assertIn("黄", data["fontText"])
            if (paths.ROOT / "node_modules" / "@fontsource" / "noto-sans-sc").is_dir():
                self.assertIn(["Noto Sans SC", 700], data["fonts"])
                self.assertTrue(any((d / "out" / "fonts" / "noto-sans-sc").iterdir()))
            with self.assertRaises(SystemExit):  # --strict refuses provisional timing
                with redirect_stderr(io.StringIO()), redirect_stdout(io.StringIO()):
                    self.build.build(d, strict=True)
        finally:
            shutil.rmtree(tmp)

    @unittest.skipUnless(NODE, "node not available")
    def test_javascript_syntax(self):
        files = [THEME_FILM / "engine.js", EXAMPLE_FILM / "scenes.js", paths.TEMPLATES / "film" / "scenes.js"]
        self.assertEqual(film.js_syntax_errors(files), {})
        import subprocess

        for name in ("lib.js", "render.js", "poster.js", "shot.js", "site/films.js"):
            r = subprocess.run([NODE, "--check", str(THEME_FILM / name)], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, f"{name}: {r.stderr}")

    def test_scripts_are_executable(self):
        import os

        for name in ("film.sh", "render_all.sh", "mux.sh", "small.sh", "setup.sh"):
            self.assertTrue(os.access(THEME_FILM / name, os.X_OK), name)


if __name__ == "__main__":
    unittest.main()
