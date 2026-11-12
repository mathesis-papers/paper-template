"""Offline integration checks against an existing sdk/catalog rendered paper.

MATHESIS_TEST_PAPER=/path/to/rendered/paper python3 -m unittest discover -s docs/layer-mathesis/tests
No paper identities or mathematical fixtures are synthesized by this test suite.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "docs/layer-mathesis/scripts/paper.py"
SOURCE = os.environ.get("MATHESIS_TEST_PAPER")


@unittest.skipUnless(SOURCE, "set MATHESIS_TEST_PAPER to an existing sdk/catalog paper projection")
class PaperTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="mathesis-paper-test-")
        self.root = Path(self.tmp.name) / "paper"
        self.root.mkdir()
        for name in ("tools", "theme", "docs/layer-mathesis"):
            shutil.copytree(ROOT / name, self.root / name,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        self.work = json.loads((Path(SOURCE) / "paper.json").read_text())["work"]
        self.slug = self.work["repository_name"]
        # Explicitly use the recorded title for both edition metadata in these tests.
        self.run_cli("fill", "--input", SOURCE, "--slug", self.slug,
                     "--title-zh", self.work["title"], "--title-en", self.work["title"],
                     "--repository", "mathesis-papers/" + self.slug)

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, *args, expected=0):
        result = subprocess.run([sys.executable, str(SCRIPT), "--root", str(self.root), *args],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result.stdout + result.stderr

    def test_fill_preserves_projection_and_reports_pending(self):
        manifest = json.loads((self.root / ".mathesis/generated.json").read_text())
        for name in [*manifest["generated_paths"], ".mathesis/generated.json"]:
            self.assertEqual((self.root / name).read_bytes(), (Path(SOURCE) / name).read_bytes(), name)
        self.assertIn("stage=skeleton", self.run_cli("check"))
        self.assertIn("pending claims", self.run_cli("check"))
        self.run_cli("fill", "--input", SOURCE, "--slug", self.slug,
                     "--title-zh", self.work["title"], "--title-en", self.work["title"],
                     "--repository", "mathesis-papers/" + self.slug, expected=1)

    def test_generated_tamper_refused(self):
        with (self.root / "paper.pdf").open("ab") as f:
            f.write(b"tampered")
        self.assertIn("hash mismatch", self.run_cli("check", expected=1))

    def test_citation_identity_checked_even_with_matching_hash(self):
        cff = self.root / "CITATION.cff"
        cff.write_text(cff.read_text().replace('version: "' + str(self.work["current_version"]) + '"', 'version: ""'))
        path = self.root / ".mathesis/generated.json"
        manifest = json.loads(path.read_text())
        manifest["sha256"]["CITATION.cff"] = hashlib.sha256(cff.read_bytes()).hexdigest()
        path.write_text(json.dumps(manifest))
        self.assertIn("CITATION.cff version differs", self.run_cli("check", expected=1))

    def test_book_authors_checked(self):
        path = self.root / "books" / self.slug / "book.toml"
        text = path.read_text()
        path.write_text("\n".join('authors = []' if line.startswith('authors = ') else line for line in text.splitlines()))
        self.assertIn("book version/authors/license differs", self.run_cli("check", expected=1))

    def test_claim_mapping_checked_in_both_editions(self):
        path = self.root / ".mathesis/book.json"
        mapping = json.loads(path.read_text())
        identity = mapping["pending_claims"].pop(0)
        claim = identity.rsplit(":", 1)[1]
        mapping["results"][claim] = {"claim": identity, "gids": []}
        path.write_text(json.dumps(mapping))
        for lang in ("zh", "en"):
            page = self.root / "books" / self.slug / lang / "README.md"
            page.write_text(page.read_text() + f'\n::: {{.remark #{claim} mathesis="{identity}"}}\nIntegration fixture.\n:::\n')
        self.run_cli("check")
        page = self.root / "books" / self.slug / "en/README.md"
        page.write_text(page.read_text().replace(f'mathesis="{identity}"', ''))
        self.assertIn("result ids differ", self.run_cli("check", expected=1))

    def test_incomplete_release_refused(self):
        self.run_cli("check", "--complete", expected=1)
        output = self.root / "build/zenodo"
        self.run_cli("zenodo", "--tag", "v" + str(self.work["current_version"]), "--output", str(output), expected=1)
        self.assertFalse(output.exists())

    def test_payload_keeps_exact_bytes_after_readiness_gate(self):
        spec = importlib.util.spec_from_file_location("mathesis_paper", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        paper, _, manifest = module.projection(self.root)
        output = self.root / "build/zenodo"
        # Packaging is tested independently of agent-written exposition/readiness.
        with mock.patch.object(module, "check", return_value=(paper, manifest)):
            module.zenodo(self.root, output, "v" + str(self.work["current_version"]))
        files = json.loads((output / "files.json").read_text())["files"]
        self.assertEqual(len(files), len(manifest["generated_paths"]) + 1)
        for row in files:
            name = row["path"][len("files/"):]
            self.assertEqual((output / row["path"]).read_bytes(), (Path(SOURCE) / name).read_bytes())
            self.assertEqual(hashlib.sha256((output / row["path"]).read_bytes()).hexdigest(), row["sha256"])
        metadata = json.loads((output / "metadata.json").read_text())["metadata"]
        self.assertEqual(metadata["title"], self.work["title"])
        self.assertEqual(metadata["doi"], self.work["doi"])
