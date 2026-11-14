"""Old collection downloads remain exact bytes, never a current proof receipt."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("collection_history", Path(__file__).resolve().parents[1] / "scripts/collection_history.py")
history = importlib.util.module_from_spec(spec)
spec.loader.exec_module(history)


class History(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.name = "versions/v1/paper.pdf"
        p = self.root / self.name
        p.parent.mkdir(parents=True)
        p.write_bytes(b"original published PDF")
        self.record = {"schema": "mathesis.collection-history.v1", "work": "example", "source_commit": "a" * 40,
                       "sha256": {self.name: hashlib.sha256(p.read_bytes()).hexdigest()}}
        self.marker = self.root / history.HISTORY
        self.marker.parent.mkdir()
        self.save()

    def save(self):
        self.marker.write_text(json.dumps(self.record))

    def test_exact_snapshots_are_copied_idempotently(self):
        out = self.root / "_site"
        for _ in range(2):
            history.emit_history(self.root, out, "example")
            self.assertEqual((out / self.name).read_bytes(), b"original published PDF")

    def test_untracked_changed_or_missing_snapshots_are_rejected(self):
        extra = self.root / "versions/v1/new.lean"
        extra.write_text("unpublished addition")
        with self.assertRaisesRegex(ValueError, "unlisted"):
            history.history_files(self.root, "example")
        extra.unlink()
        (self.root / self.name).write_bytes(b"edited PDF")
        with self.assertRaisesRegex(ValueError, "bytes differ"):
            history.history_files(self.root, "example")
        (self.root / self.name).unlink()
        with self.assertRaisesRegex(ValueError, "bytes differ"):
            history.history_files(self.root, "example")

    def test_identity_paths_and_linked_files_cannot_escape_the_snapshot(self):
        with self.assertRaisesRegex(ValueError, "identity"):
            history.history_files(self.root, "another-work")
        for name in ("versions/v1/../../../private", "/private", "versions/current/paper.pdf"):
            self.record["sha256"] = {name: "a" * 64}
            self.save()
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "invalid"):
                history.history_files(self.root, "example")
        self.record["sha256"] = {self.name: "a" * 64}
        self.save()
        p = self.root / self.name
        p.unlink()
        p.symlink_to("/etc/passwd")
        with self.assertRaisesRegex(ValueError, "bytes differ"):
            history.history_files(self.root, "example")

    def test_a_site_collision_does_not_replace_prior_or_new_content(self):
        out = self.root / "_site"
        p = out / self.name
        p.parent.mkdir(parents=True)
        p.write_bytes(b"unrelated built content")
        with self.assertRaisesRegex(ValueError, "conflicts"):
            history.emit_history(self.root, out, "example")
        self.assertEqual(p.read_bytes(), b"unrelated built content")

    def test_unmigrated_papers_need_no_history_but_unowned_versions_are_rejected(self):
        self.marker.unlink()
        with self.assertRaisesRegex(ValueError, "require a publisher"):
            history.history_files(self.root, "example")
        (self.root / self.name).unlink()
        (self.root / "versions/v1").rmdir()
        (self.root / "versions").rmdir()
        self.assertEqual(history.history_files(self.root, "example"), {})


if __name__ == "__main__":
    unittest.main()
