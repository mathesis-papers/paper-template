"""tools/migrations/v0.2.0.py: film.json gets narrated_720p and cover, loses the per-film release keys; notes
for the new film default, hiding the example books and ci.yml callers. Run twice: the second run changes
nothing (tools/migrations/README.md)."""

from __future__ import annotations

import json
import runpy
import shutil
import tempfile
import unittest
from pathlib import Path

from tbook import paths

MIGRATION = paths.ROOT / "tools" / "migrations" / "v0.2.0.py"


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


class MigrationV020Test(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="tbook-mig-020-"))
        self.addCleanup(shutil.rmtree, self.root, True)
        self.migrate = runpy.run_path(str(MIGRATION))["migrate"]

    def old_film(self, slug: str = "my-book", film: str = "001-intro", **extra) -> Path:
        meta = {"id": film, "title": "Intro", "narration": {"language": "en"}, "subtitles": ["zh", "en"],
                "resolution": "1920x1080@30",
                "outputs": {"narrated": f"{slug}_001_narrated_EN_subs_ZH-EN.mp4",
                            "music_only": f"{slug}_001_music_only_subs_ZH-EN.mp4",
                            "cover": f"{slug}_001_cover.jpg"},
                "release_tag": f"film-{slug}-001-v2", "published_tag": f"film-{slug}-001-v1", **extra}
        return write(self.root / "books" / slug / "films" / film / "film.json", json.dumps(meta, indent=2) + "\n")

    def test_old_film_json_is_migrated_once(self):
        path = self.old_film()
        notes = self.migrate(self.root)
        meta = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(meta["outputs"]["narrated_720p"], "my-book_001_720p_narrated.mp4")
        self.assertEqual(meta["outputs"]["cover"], "my-book_001_cover.jpg")  # kept
        self.assertEqual(meta["outputs"]["narrated"], "my-book_001_narrated_EN_subs_ZH-EN.mp4")  # kept
        self.assertNotIn("release_tag", meta)
        self.assertNotIn("published_tag", meta)
        self.assertEqual(meta["resolution"], "1920x1080@30")  # 1080p is still listed
        changed = [n for n in notes if n.startswith("books/my-book/films/001-intro/film.json: outputs.")]
        self.assertEqual(len(changed), 1, notes)
        self.assertIn("removed release_tag; removed published_tag", changed[0])
        self.assertTrue(any("still builds narrated, music_only" in n for n in notes), notes)
        before = path.read_bytes()
        again = self.migrate(self.root)
        self.assertEqual(path.read_bytes(), before, "the second run changes nothing")
        self.assertFalse(any("outputs.narrated_720p =" in n for n in again), again)

    def test_missing_cover_and_new_films(self):
        path = self.old_film(slug="b", film="002-x")
        meta = json.loads(path.read_text(encoding="utf-8"))
        del meta["outputs"]["cover"]
        path.write_text(json.dumps(meta), encoding="utf-8")
        new = write(self.root / "books" / "b" / "films" / "003-y" / "film.json", json.dumps(
            {"id": "003-y", "outputs": {"narrated_720p": "b_003_720p_narrated.mp4", "cover": "b_003_cover.jpg"},
             "resolution": "1280x720@30"}, indent=2) + "\n")
        before_new = new.read_bytes()
        notes = self.migrate(self.root)
        self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["outputs"]["cover"], "b_002_cover.jpg")
        self.assertEqual(new.read_bytes(), before_new, "a film in the new format is left alone")
        self.assertFalse(any("003-y" in n for n in notes), notes)

    def test_unreadable_film_json_is_reported(self):
        write(self.root / "books" / "b" / "films" / "001-z" / "film.json", "{ not json")
        notes = self.migrate(self.root)
        self.assertTrue(any("not readable as JSON" in n for n in notes), notes)

    def test_hide_and_pages_read_notes(self):
        write(self.root / "books" / "example-monograph" / "book.toml", "[book]\n")
        write(self.root / "site.toml", "[site]\n[books]\norder = []\n")
        write(self.root / ".github" / "workflows" / "mine.yml",
              "jobs:\n  ci:\n    uses: ./.github/workflows/ci.yml\n    permissions:\n      contents: read\n")
        notes = self.migrate(self.root)
        self.assertTrue(any('hide = ["example-*"]' in n for n in notes), notes)
        self.assertTrue(any("mine.yml calls ci.yml: grant it pages: read" in n for n in notes), notes)
        write(self.root / "site.toml", '[site]\n[books]\norder = []\nhide = ["example-*"]\n')
        write(self.root / ".github" / "workflows" / "mine.yml",
              "jobs:\n  ci:\n    uses: ./.github/workflows/ci.yml\n    permissions:\n      contents: read\n"
              "      pages: read\n")
        self.assertEqual(self.migrate(self.root), ["nothing to migrate"])


if __name__ == "__main__":
    unittest.main()
