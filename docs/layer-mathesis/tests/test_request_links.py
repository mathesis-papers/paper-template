"""Request routing is separate from proof badges, DOI evidence and receipts."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("request_links", Path(__file__).resolve().parents[1] / "scripts/mathesis_requests.py")
links = importlib.util.module_from_spec(spec)
spec.loader.exec_module(links)


class RequestLinks(unittest.TestCase):
    def row(self, number, label="Theorem 1"):
        return {"comparison_verdict": "none", "formalization_request": {
            "url": f"https://github.com/the-omega-institute/trureturing-requests/issues/{number}", "label": label}}

    def test_links_do_not_need_or_imply_doi_or_proof_receipts(self):
        mapping = {"results": {"first": self.row(24)}}
        self.assertEqual(links.result_requests(mapping), [mapping["results"]["first"]["formalization_request"]])
        self.assertEqual(links.result_requests({"results": {"first": {}}}), [])

    def test_one_request_can_serve_multiple_results(self):
        mapping = {"results": {"first": self.row(24), "second": self.row(24, "Corollary 2"), "third": self.row(3)}}
        result = links.result_requests(mapping)
        self.assertEqual([r["url"].rsplit("/", 1)[1] for r in result], ["3", "24"])
        self.assertEqual(result[1]["label"], "Corollary 2; Theorem 1")

    def test_exact_coverage_cannot_solicit_a_duplicate_proof(self):
        row = self.row(24)
        row["comparison_verdict"] = "same"
        with self.assertRaisesRegex(ValueError, "exactly covered"):
            links.result_requests({"results": {"first": row}})

    def test_only_canonical_request_links_are_accepted(self):
        for url in ("https://example.org/24", "https://github.com/the-omega-institute/trureturing-requests/pull/24",
                    self.row(24)["formalization_request"]["url"] + "#issuecomment-1"):
            with self.subTest(url=url), self.assertRaisesRegex(ValueError, "invalid formalization request"):
                row = self.row(24)
                row["formalization_request"]["url"] = url
                links.result_requests({"results": {"first": row}})

    def test_missing_or_multiline_labels_are_rejected(self):
        for label in ("", "\nTheorem 1", "Theorem\n1", "x" * 301, None):
            with self.subTest(label=label), self.assertRaisesRegex(ValueError, "readable label"):
                links.result_requests({"results": {"first": self.row(24, label)}})
