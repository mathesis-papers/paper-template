"""Opt single-paper consumers into the Mathesis post-build command."""
import json
import re
import tomllib


def migrate(root):
    mapping = root / ".mathesis/book.json"
    if not mapping.exists():
        return ["No selected Mathesis paper; the publisher skeleton configures the site hook."]
    path = root / "site.toml"
    text = path.read_text(encoding="utf-8")
    config = tomllib.loads(text)
    command = ["python3", "docs/layer-mathesis/scripts/site.py"]
    existing = config["site"].get("post_build")
    if existing is not None and existing != command:
        raise ValueError("site.post_build already exists; integrate the Mathesis site command manually")
    additions = []
    if existing is None:
        additions.append("post_build = " + json.dumps(command))
    repo = config["site"]["repo"].split("/", 1)[1]
    canonical = "https://papers.trureturing.org/" + repo + "/"
    old = config["site"].get("base_url")
    if not old:
        additions.append("base_url = " + json.dumps(canonical))
    elif old.startswith("https://mathesis-papers.github.io/"):
        text = re.sub(r'^base_url\s*=.*$', "base_url = " + json.dumps(canonical), text, count=1, flags=re.M)
    text = text.replace("[site]\n", "[site]\n" + "\n".join(additions) + ("\n" if additions else ""), 1)
    tomllib.loads(text)
    path.write_text(text, encoding="utf-8")
    return ["Configured the Mathesis single-book root redirect and materials manifest; upstream site.post_build support is required."]
