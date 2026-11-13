"""Introduce the four-zone contract without deleting publisher or author work."""
import importlib.util


def migrate(root):
    spec = importlib.util.spec_from_file_location("mathesis_layout_migration", root / "docs/layer-mathesis/scripts/paper.py")
    paper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(paper)
    paper.front(root)
    moves, protected = paper.tidy(root, apply=False)
    return [f"Four-zone layout: {len(moves)} legacy entries can be archived outside the repository; "
            f"{len(protected)} owner repairs reported. Condense any statement review into .mathesis/REVIEW.md, "
            "then run paper.py tidy --dry-run and --apply, paper.py front, and paper.py check. "
            "Migration preserved all paper-record and content bytes."]
