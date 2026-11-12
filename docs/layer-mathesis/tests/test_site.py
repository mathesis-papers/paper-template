"""Materials and root routing checks using a real selected Mathesis paper."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
SOURCE = os.environ.get("MATHESIS_TEST_PAPER")
spec = importlib.util.spec_from_file_location("mathesis_site", ROOT / "docs/layer-mathesis/scripts/site.py")
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
