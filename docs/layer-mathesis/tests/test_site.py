"""Materials and root routing checks using a real selected Mathesis paper."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest

ROOT = Path(__file__).resolve().parents[3]
SOURCE = os.environ.get("MATHESIS_TEST_PAPER")
spec = importlib.util.spec_from_file_location("mathesis_site", ROOT / "docs/layer-mathesis/scripts/site.py")
SCRIPT = ROOT / "docs/layer-mathesis/scripts/site.py"
COMMAND = json.loads((ROOT / "docs/layer-mathesis/site-hook.json").read_text())
site = importlib.util.module_from_spec(spec)
spec.loader.exec_module(site)


@unittest.skipUnless(SOURCE, "set MATHESIS_TEST_PAPER to an existing selected paper")
class SiteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="mathesis-site-test-")
        self.root = Path(self.tmp.name)
        source = Path(SOURCE)
        for name in ("paper.json", ".mathesis/book.json"):
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source / name, path)
        self.work = json.loads((self.root / "paper.json").read_text())["work"]
        self.slug = json.loads((self.root / ".mathesis/book.json").read_text())["book"]
        self.out = self.root / "_site"
        self.book = {"slug": self.slug, "editions": [{"lang": "en", "html": self.slug + "/en/"}, {"lang": "zh", "html": None}],
                     "files": [], "media": {"viz": ["step-triangle"]}}
        self.manifest = {"schema": "trureturing-books.site.v1", "site": {"repo": "mathesis-papers/" + self.work["repository_name"]}, "books": [self.book]}
        self.add(self.slug + "/index.html", b"book landing")
        self.add("manifest.json", json.dumps(self.manifest).encode())

    def add(self, path, data=b"built output fixture"):
        dest = self.out / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)

    def tearDown(self):
        self.tmp.cleanup()

    def test_root_keeps_old_landing_and_only_lists_built_materials(self):
        reading = self.slug + "/en/index.html"
        self.add(reading)
        self.add(self.slug + "/viz/step-triangle/index.html")
        for kind, suffix in (("slides-pdf", ""), ("slides-notes-pdf", "-notes")):
            path = self.slug + "/slides/seminar/seminar-en" + suffix + ".pdf"
            self.add(path)
            self.book["files"].append({"kind": kind, "path": path, "variant": "seminar", "lang": "en"})
        self.add("manifest.json", json.dumps(self.manifest).encode())
        materials = site.emit(self.root, self.out)
        first = (self.out / "mathesis-materials.json").read_bytes()
        self.assertEqual(materials["version"], self.work["current_version"])
        self.assertEqual(list(materials["reading"]), ["en"])
        self.assertTrue(materials["slides"][0]["pdf_url"].endswith("seminar-en.pdf"))
        self.assertTrue(materials["slides"][0]["notes_url"].endswith("seminar-en-notes.pdf"))
        self.assertEqual(len(materials["visualizations"]), 1)
        self.assertIn('0;url=' + self.slug + '/', (self.out / "index.html").read_text())
        self.assertEqual((self.out / self.slug / "index.html").read_bytes(), b"book landing")
        site.emit(self.root, self.out)
        self.assertEqual(first, (self.out / "mathesis-materials.json").read_bytes())
        (self.out / reading).unlink()
        self.assertEqual(site.emit(self.root, self.out)["reading"], {})

    def test_multiple_books_and_traversal_refused(self):
        self.manifest["books"].append(dict(self.book))
        self.add("manifest.json", json.dumps(self.manifest).encode())
        with self.assertRaisesRegex(ValueError, "exactly one"):
            site.emit(self.root, self.out)

        self.manifest["books"].pop()
        self.book["editions"][0]["html"] = "../outside/"
        self.add("manifest.json", json.dumps(self.manifest).encode())
        with self.assertRaisesRegex(ValueError, "invalid published"):
            site.emit(self.root, self.out)

    def test_video_requires_built_registry_and_real_nonempty_mp4(self):
        self.book["media"]["films"] = ["001-parity"]
        registry = {"version": 2, "book": self.slug, "films": [{"id": "001-parity", "title": "Why parity matters", "built": True,
                    "videos": {"wide": "001-parity/film.mp4"}, "poster": "001-parity/poster.jpg"}]}
        self.add(self.slug + "/films/films.json", json.dumps(registry).encode())
        self.add(self.slug + "/films/index.html")
        self.add("manifest.json", json.dumps(self.manifest).encode())
        self.assertEqual(site.emit(self.root, self.out)["videos"], [])
        self.add(self.slug + "/films/001-parity/film.mp4", b"")
        self.assertEqual(site.emit(self.root, self.out)["videos"], [])
        self.add(self.slug + "/films/001-parity/film.mp4", b"\x00\x00\x00\x18ftypmp42")
        videos = site.emit(self.root, self.out)["videos"]
        self.assertEqual(len(videos), 1)
        self.assertEqual(videos[0]["title"], "Why parity matters")
        self.assertIsNone(videos[0]["poster_url"])
        registry["films"][0]["built"] = False
        self.add(self.slug + "/films/films.json", json.dumps(registry).encode())
        self.assertEqual(site.emit(self.root, self.out)["videos"], [])

    def test_requests_are_selected_book_uses_not_completion_receipts(self):
        self.manifest["formalization_requests"] = [
            {"request": "https://github.com/the-omega-institute/trureturing-requests/issues/2", "uses": [
                {"book": self.slug, "id": "paper-thm-main", "source": "Theorem 1 (thm:main)"},
                {"book": "other", "id": "elsewhere", "source": "Lemma 9"}]},
            {"request": "https://github.com/the-omega-institute/trureturing-requests/issues/3", "uses": [
                {"book": "other", "id": "other", "source": "Lemma 2"}]}]
        self.add("manifest.json", json.dumps(self.manifest).encode())
        requests = site.emit(self.root, self.out)["formalization_requests"]
        self.assertEqual(requests, [{"label": "Theorem 1", "url": self.manifest["formalization_requests"][0]["request"]}])
        self.assertNotIn("status", requests[0])
        self.manifest["formalization_requests"][0]["request"] += "?x=1"
        self.add("manifest.json", json.dumps(self.manifest).encode())
        with self.assertRaisesRegex(ValueError, "invalid formalization request"):
            site.emit(self.root, self.out)

    def test_unbadged_paper_requests_survive_without_a_doi_and_do_not_duplicate(self):
        paper = json.loads((self.root / "paper.json").read_text())
        paper["work"]["doi"] = None
        (self.root / "paper.json").write_text(json.dumps(paper))
        path = self.root / ".mathesis/book.json"
        mapping = json.loads(path.read_text())
        row = next(iter(mapping["results"].values()))
        row["comparison_verdict"] = "variant"
        row["formalization_request"] = {"label": "Theorem 1", "url": "https://github.com/the-omega-institute/trureturing-requests/issues/24"}
        path.write_text(json.dumps(mapping))
        result = site.emit(self.root, self.out)
        self.assertIsNone(result["doi"])
        self.assertEqual(result["formalization_requests"], [row["formalization_request"]])
        self.assertEqual(set(result["formalization_requests"][0]), {"label", "url"})
        self.manifest["formalization_requests"] = [{"request": row["formalization_request"]["url"],
            "uses": [{"book": self.slug, "id": "existing-result", "source": "Theorem 1"}]}]
        self.add("manifest.json", json.dumps(self.manifest).encode())
        self.assertEqual(len(site.emit(self.root, self.out)["formalization_requests"]), 1)

    def hook(self, external=False):
        script = self.root / site.SCRIPT_PATH
        script.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(SCRIPT, script)
        shutil.copyfile(SCRIPT.with_name("mathesis_requests.py"), script.with_name("mathesis_requests.py"))
        command = [sys.executable, str(SCRIPT)] if external else [sys.executable, *COMMAND[1:]]
        # A stale TBOOK_ROOT must not override the hook cwd.
        env = dict(os.environ, TBOOK_SITE_OUT=str(self.out), TBOOK_ROOT=str(ROOT), PYTHONDONTWRITEBYTECODE="1")
        return subprocess.run(command, cwd=self.root, env=env, capture_output=True, text=True)

    def output_bytes(self):
        return {p.relative_to(self.out).as_posix(): p.read_bytes() for p in self.out.rglob("*") if p.is_file()}

    def test_no_mapped_book_skips_and_leaves_output_untouched(self):
        self.add("index.html", b"library index")
        self.add("mathesis-materials.json", b"existing materials")
        for books in ([], [dict(self.book, slug="example-primer")]):
            with self.subTest(books=books):
                self.manifest["books"] = books
                self.add("manifest.json", json.dumps(self.manifest).encode())
                before = self.output_bytes()
                result = self.hook()
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(len(result.stdout.splitlines()), 1)
                self.assertIn("Mathesis post-build skipped:", result.stdout)
                self.assertIn("absent from site manifest", result.stdout)
                self.assertEqual(result.stderr, "")
                self.assertEqual(self.output_bytes(), before)

    def test_external_script_uses_built_repository_cwd(self):
        result = self.hook(external=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        materials = json.loads((self.out / "mathesis-materials.json").read_text())
        self.assertEqual(materials["work"], self.work["work"])
        self.assertEqual(materials["version"], self.work["current_version"])
        self.assertNotIn("skipped", result.stdout)
        # Change only this fixture's paper metadata. The external source remains valid.
        paper = json.loads((self.root / "paper.json").read_text())
        paper["work"]["current_version"] = None
        (self.root / "paper.json").write_text(json.dumps(paper))
        before = self.output_bytes()
        result = self.hook(external=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("mapping and paper identity differ", result.stderr)
        self.assertEqual(self.output_bytes(), before)

    def test_matching_paper_inconsistencies_fail_through_bootstrap(self):
        self.add("index.html", b"original index")
        for label in ("extra_book", "schema", "repo", "unsafe_path", "missing_paper", "malformed_mapping", "malformed_manifest", "missing_landing"):
            with self.subTest(inconsistency=label):
                manifest = json.loads(json.dumps(self.manifest))
                mapping_path = self.root / ".mathesis/book.json"
                mapping_bytes = mapping_path.read_bytes()
                paper_path = self.root / "paper.json"
                paper_bytes = paper_path.read_bytes()
                landing = self.out / self.slug / "index.html"
                landing_bytes = landing.read_bytes()
                if label == "extra_book": manifest["books"].append(dict(self.book))
                elif label == "schema": manifest["schema"] = "invalid"
                elif label == "repo": manifest["site"]["repo"] = "invalid"
                elif label == "unsafe_path": manifest["books"][0]["editions"][0]["html"] = "../outside/"
                elif label == "missing_paper": paper_path.unlink()
                elif label == "malformed_mapping": mapping_path.write_text("invalid JSON")
                elif label == "missing_landing": landing.unlink()
                self.add("manifest.json", b"invalid JSON" if label == "malformed_manifest" else json.dumps(manifest).encode())
                before = self.output_bytes()
                result = self.hook()
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn("Mathesis site:", result.stderr)
                self.assertNotIn("skipped", result.stdout)
                self.assertEqual(self.output_bytes(), before)
                mapping_path.write_bytes(mapping_bytes)
                paper_path.write_bytes(paper_bytes)
                landing.write_bytes(landing_bytes)

    def test_bootstrap_migration_is_discoverable_idempotent_and_preserves_settings(self):
        sys.path.insert(0, str(ROOT / "tools"))
        from tbook import template
        migrations = template.find_migrations(ROOT / "docs/layer-mathesis/migrations", "0.3.0", "0.3.1")
        self.assertEqual([m.name for m in migrations], ["v0.3.1.py"])
        spec = importlib.util.spec_from_file_location("mathesis_bootstrap_migration", migrations[0].path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for old_command in ('["python3", "docs/layer-mathesis/scripts/site.py"]', '[\n  "python3",\n  "docs/layer-mathesis/scripts/site.py",\n]'):
            path = self.root / "site.toml"
            original = '[site]\nrepo = "mathesis-papers/' + self.work["repository_name"] + '"\npost_build = ' + old_command + '\nlanguages = ["zh", "en"]\n[site.title]\nen = "Preserved title"\n'
            path.write_text(original)
            before = tomllib.loads(original)
            module.migrate(self.root)
            first = path.read_bytes()
            cfg = tomllib.loads(path.read_text())
            self.assertEqual(cfg["site"].pop("post_build"), COMMAND)
            before["site"].pop("post_build")
            self.assertEqual(cfg, before)
            module.migrate(self.root)
            self.assertEqual(path.read_bytes(), first)
        (self.root / ".mathesis/book.json").unlink()
        path.write_text(original)
        module.migrate(self.root)
        self.assertEqual(tomllib.loads(path.read_text())["site"]["post_build"], COMMAND)
        path.write_text('[site]\nrepo = "mathesis-papers/paper-template"\n')
        before = path.read_bytes()
        module.migrate(self.root)
        self.assertEqual(path.read_bytes(), before)
        path.write_text('[site]\npost_build = ["custom"]\n')
        before = path.read_bytes()
        with self.assertRaisesRegex(ValueError, "customized"):
            module.migrate(self.root)
        self.assertEqual(path.read_bytes(), before)

    def test_migration_is_discoverable_and_idempotent(self):
        import sys
        sys.path.insert(0, str(ROOT / "tools"))
        from tbook import template
        migrations = template.find_migrations(ROOT / "docs/layer-mathesis/migrations", "0.2.1", "0.3.0")
        self.assertEqual([m.name for m in migrations], ["v0.3.0.py"])
        spec = importlib.util.spec_from_file_location("mathesis_migration", migrations[0].path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        path = self.root / "site.toml"
        path.write_text('[site]\nrepo = "mathesis-papers/' + self.work["repository_name"] + '"\nbase_url = "https://mathesis-papers.github.io/' + self.work["repository_name"] + '/"\n')
        module.migrate(self.root)
        first = path.read_bytes()
        cfg = tomllib.loads(path.read_text())["site"]
        self.assertEqual(cfg["post_build"], ["python3", "docs/layer-mathesis/scripts/site.py"])
        self.assertEqual(cfg["base_url"], "https://papers.trureturing.org/" + self.work["repository_name"] + "/")
        module.migrate(self.root)
        self.assertEqual(first, path.read_bytes())


class InheritedHookTests(unittest.TestCase):
    """No paper fixture is needed for absent script/mapping cases."""
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="mathesis-inherited-hook-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.out = self.root / "output"
        self.out.mkdir()
        (self.out / "index.html").write_bytes(b"unchanged index")
        (self.out / "manifest.json").write_bytes(b"not read for these skip cases")
        (self.out / "mathesis-materials.json").write_bytes(b"unchanged materials")

    def run_hook(self):
        before = {p.name: p.read_bytes() for p in self.out.iterdir()}
        result = subprocess.run([sys.executable, *COMMAND[1:]], cwd=self.root, text=True, capture_output=True,
                                env=dict(os.environ, TBOOK_SITE_OUT=str(self.out), TBOOK_ROOT=str(ROOT)))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(result.stdout.splitlines()), 1)
        self.assertEqual(result.stderr, "")
        self.assertEqual({p.name: p.read_bytes() for p in self.out.iterdir()}, before)
        return result.stdout

    def test_absent_layer_script_skips_before_import(self):
        mapping = self.root / ".mathesis/book.json"
        mapping.parent.mkdir()
        mapping.write_text("not read without the layer script")
        self.assertIn("layer script is absent", self.run_hook())

    def test_absent_mapping_skips_before_reading_manifest(self):
        script = self.root / site.SCRIPT_PATH
        script.parent.mkdir(parents=True)
        shutil.copyfile(SCRIPT, script)
        self.assertIn("no .mathesis/book.json", self.run_hook())

    def test_external_script_also_skips_when_local_layer_is_absent(self):
        before = (self.out / "index.html").read_bytes()
        result = subprocess.run([sys.executable, str(SCRIPT)], cwd=self.root, text=True, capture_output=True,
                                env=dict(os.environ, TBOOK_SITE_OUT=str(self.out)))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(result.stdout.splitlines()), 1)
        self.assertIn("layer script is absent", result.stdout)
        self.assertEqual((self.out / "index.html").read_bytes(), before)
