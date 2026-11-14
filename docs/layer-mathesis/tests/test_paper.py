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
UPSTREAM = Path(os.environ.get("MATHESIS_TEST_UPSTREAM", ROOT))


@unittest.skipUnless(SOURCE, "set MATHESIS_TEST_PAPER to an existing sdk/catalog paper projection")
class PaperTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="mathesis-paper-test-")
        self.root = Path(self.tmp.name) / "paper"
        self.root.mkdir()
        for name in ("tools", "theme", "docs/layer-mathesis"):
            shutil.copytree((ROOT if name.startswith("docs/") else UPSTREAM) / name, self.root / name,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        for name in ("template.toml", "template-manifest.json"):
            shutil.copyfile(UPSTREAM / name, self.root / name)
        shutil.copytree(ROOT / "template.d", self.root / "template.d")
        self.work = json.loads((Path(SOURCE) / "paper.json").read_text())["work"]
        self.slug = self.work["repository_name"]
        if self._testMethodName == "test_fill_removes_examples_and_persists_media_skeleton":
            example = self.root / "books/example-monograph/en/README.md"
            example.parent.mkdir(parents=True)
            example.write_text("Upstream example fixture, preserved in external archive.\n")
        # Explicitly use the recorded title for both edition metadata in these tests.
        output = self.run_cli("fill", "--input", SOURCE, "--slug", self.slug,
                     "--title-zh", self.work["title"], "--title-en", self.work["title"],
                     "--repository", "mathesis-papers/" + self.slug)
        for line in output.splitlines():
            if line.startswith("Moved upstream examples outside the repository: "):
                self.example_archive = Path(line.split(": ", 1)[1])
                self.addCleanup(shutil.rmtree, self.example_archive)

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
            actual = (self.root / name).read_bytes()
            if name == "README.md":
                actual = actual.split(b"\n<!-- Mathesis generated repository guide; refresh with paper.py front. -->\n")[0]
            expected = (Path(SOURCE) / name).read_bytes()
            if name == "README.md":
                expected = expected.split(b"\n<!-- Mathesis generated repository guide; refresh with paper.py front. -->\n")[0]
            self.assertEqual(actual, expected, name)
        self.assertIn("stage=skeleton", self.run_cli("check"))
        self.assertIn("pending claims", self.run_cli("check"))
        self.run_cli("fill", "--input", SOURCE, "--slug", self.slug,
                     "--title-zh", self.work["title"], "--title-en", self.work["title"],
                     "--repository", "mathesis-papers/" + self.slug, expected=1)

    def test_fill_removes_examples_and_persists_media_skeleton(self):
        self.assertEqual([p.name for p in (self.root / "books").iterdir()], [self.slug])
        self.assertTrue((self.example_archive / "example-monograph/en/README.md").is_file())
        for name in ("figures", "viz", "slides", "assets"):
            self.assertTrue((self.root / "books" / self.slug / name / ".gitkeep").is_file())
        self.run_cli("check", "--layout-only")

    def test_empty_media_registry_keeps_front_stable_without_promising_outputs(self):
        before = (self.root / "README.md").read_bytes()
        path = self.root / "books" / self.slug / "viz/visualizations.json"
        path.write_text(json.dumps({"version": 1, "visualizations": []}))
        self.run_cli("check")
        self.assertEqual((self.root / "README.md").read_bytes(), before)
        self.assertNotIn(b"[Videos](", before)
        self.assertNotIn(b"[Visualizations](", before)

    def test_academic_pdf_is_the_only_default(self):
        import tomllib
        cfg = tomllib.loads((self.root / "books" / self.slug / "book.toml").read_text())
        self.assertEqual(cfg["outputs"]["pdf"], ["academic"])
        site = tomllib.loads((self.root / "site.toml").read_text())
        self.assertEqual(site["site"]["post_build"], json.loads((ROOT / "docs/layer-mathesis/site-hook.json").read_text()))

    def test_old_upstream_refused_clearly(self):
        path = self.root / "tools/tbook/model.py"
        path.write_text(path.read_text().replace('WRITTEN_PROOF = "written-proof"', 'WRITTEN_PROOF = None'))
        self.assertIn("requires upstream written-proof support", self.run_cli("check", expected=1))

    def test_missing_site_hook_is_refused(self):
        path = self.root / "tools/tbook/site.py"
        path.write_text(path.read_text().replace("def post_build(", "def disabled_post_build("))
        self.assertIn("requires upstream site.post_build support", self.run_cli("check", expected=1))

    def test_written_proof_mapping_and_comparison_verdict(self):
        path = self.root / ".mathesis/book.json"
        mapping = json.loads(path.read_text())
        identity = mapping["pending_claims"].pop(0)
        claim = identity.rsplit(":", 1)[1]
        row = {"claim": identity, "gids": [], "comparison_verdict": "none",
               "compared_public_gid": None,
               "comparison_commit": json.loads((ROOT / "trureturing.lock.json").read_text())["commit"]}
        mapping["results"][claim] = row
        path.write_text(json.dumps(mapping))
        self.refresh_review(mapping)
        for lang in ("zh", "en"):
            page = self.root / "books" / self.slug / lang / "README.md"
            page.write_text(page.read_text() +
                f'\n::: {{.theorem #{claim} status="written-proof" proof="pf-{claim}" mathesis="{identity}" '
                'doi="10.1000/integration.fixture" source="Integration fixture" '
                'request="https://github.com/the-omega-institute/trureturing-requests/issues/1"}\n'
                f'Integration fixture, no mathematical claim.\n:::\n\n::: {{.proof #pf-{claim}}}\nFixture argument.\n:::\n')
        self.run_cli("check")
        row["comparison_verdict"] = "almost"
        path.write_text(json.dumps(mapping))
        self.refresh_review(mapping)
        self.assertIn("comparison_verdict", self.run_cli("check", expected=1))
        row["comparison_verdict"] = "variant"
        path.write_text(json.dumps(mapping))
        self.refresh_review(mapping)
        self.assertIn("closest public declaration", self.run_cli("check", expected=1))
        row["comparison_verdict"] = "same"
        # A real public declaration inspected by the pilot; deliberately NOT a match to this fixture.
        row["compared_public_gid"] = "D5/S1/Recurrence/Algebraic/ChenChenParityPositivity.even_rows_positive"
        path.write_text(json.dumps(mapping))
        self.refresh_review(mapping)
        self.assertIn("same requires", self.run_cli("check", expected=1))
        row["comparison_verdict"] = "special case"
        row["comparison_commit"] = "2a8e85703420116c8f07e1eebebd34fa221c8d55"
        path.write_text(json.dumps(mapping))
        self.refresh_review(mapping)
        self.run_cli("check")
        page = self.root / "books" / self.slug / "en/README.md"
        page.write_text(page.read_text().replace("Fixture argument.", ""))
        self.assertIn("is empty", self.run_cli("check", expected=1))

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
        mapping["results"][claim] = {"claim": identity, "gids": [], "comparison_verdict": "none",
                                               "compared_public_gid": None,
                                               "comparison_commit": json.loads((ROOT / "trureturing.lock.json").read_text())["commit"]}
        path.write_text(json.dumps(mapping))
        self.refresh_review(mapping)
        for lang in ("zh", "en"):
            page = self.root / "books" / self.slug / lang / "README.md"
            page.write_text(page.read_text() + f'\n::: {{.remark #{claim} mathesis="{identity}"}}\nIntegration fixture.\n:::\n')
        self.run_cli("check")
        page = self.root / "books" / self.slug / "en/README.md"
        page.write_text(page.read_text().replace(f'mathesis="{identity}"', ''))
        self.assertIn("result ids differ", self.run_cli("check", expected=1))

    def refresh_review(self, mapping):
        rows = {key: dict(row, scope="Structural integration fixture.") for key, row in mapping["results"].items()}
        (self.root / ".mathesis/review.json").write_text(json.dumps({"results": rows}))
        self.run_cli("front")

    def test_incomplete_release_refused(self):
        self.run_cli("check", "--complete", expected=1)
        output = Path(self.tmp.name) / "zenodo"
        self.run_cli("zenodo", "--tag", "v" + str(self.work["current_version"]), "--output", str(output), expected=1)
        self.assertFalse(output.exists())

    def test_payload_keeps_exact_bytes_after_readiness_gate(self):
        spec = importlib.util.spec_from_file_location("mathesis_paper", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        paper, _, manifest = module.projection(self.root)
        output = Path(self.tmp.name) / "zenodo"
        # Packaging is tested independently of agent-written exposition/readiness.
        with mock.patch.object(module, "check", return_value=(paper, manifest)):
            module.zenodo(self.root, output, "v" + str(self.work["current_version"]))
        files = json.loads((output / "files.json").read_text())["files"]
        self.assertEqual(len(files), len(manifest["generated_paths"]) + 1)
        for row in files:
            name = row["path"][len("files/"):]
            expected = (Path(SOURCE) / name).read_bytes()
            if name == "README.md":
                expected = expected.split(module.FRONT_MARKER)[0]
            self.assertEqual((output / row["path"]).read_bytes(), expected)
            self.assertEqual(hashlib.sha256((output / row["path"]).read_bytes()).hexdigest(), row["sha256"])
        metadata = json.loads((output / "metadata.json").read_text())["metadata"]
        self.assertEqual(metadata["title"], self.work["title"])
        if self.work.get("doi"):
            self.assertEqual(metadata["doi"], self.work["doi"])
        else:
            self.assertNotIn("doi", metadata)
