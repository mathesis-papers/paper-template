"""Enable film source directories and refresh the generated paper front."""
import importlib.util
import json
from pathlib import Path


def migrate(root):
    root = Path(root)
    mapping = root / ".mathesis/book.json"
    if not mapping.is_file():
        return []
    slug = json.loads(mapping.read_text())["book"]
    directory = root / "books" / slug / "films"
    directory.mkdir(exist_ok=True)
    if not any(directory.iterdir()):
        (directory / ".gitkeep").touch()
    spec = importlib.util.spec_from_file_location("mathesis_paper", root / "docs/layer-mathesis/scripts/paper.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.front(root)
    return ["Enabled film sources and refreshed the paper repository guide."]
