"""Guard inherited Mathesis hooks when building another repository or fixture."""
import json
from pathlib import Path
import re
import tomllib


def migrate(root):
    path = root / "site.toml"
    text = path.read_text(encoding="utf-8")
    config = tomllib.loads(text)
    command = json.loads((Path(__file__).resolve().parents[1] / "site-hook.json").read_text(encoding="utf-8"))
    existing = config.get("site", {}).get("post_build")
    if existing == command:
        return ["Mathesis post-build bootstrap is already configured."]
    if existing is None and not (root / ".mathesis/book.json").exists():
        return ["No selected Mathesis paper or inherited hook; publisher fill configures the bootstrap."]
    if existing not in (None, ["python3", "docs/layer-mathesis/scripts/site.py"]):
        raise ValueError("site.post_build is customized; integrate the guarded Mathesis bootstrap manually")
    section = re.search(r"(?m)^\[site\][ \t]*(?:#.*)?$", text)
    if section is None:
        raise ValueError("site.toml has no [site] section")
    start = section.end()
    following = re.search(r"(?m)^\[", text[start:])
    end = start + following.start() if following else len(text)
    body = text[start:end]
    declaration = "post_build = " + json.dumps(command)
    if existing is None:
        body = "\n" + declaration + body
    else:
        body, count = re.subn(r"(?ms)^[ \t]*post_build[ \t]*=[ \t]*\[.*?\][^\n]*", lambda _: declaration, body, count=1)
        if count != 1:
            raise ValueError("could not locate the legacy Mathesis post_build declaration")
    updated = text[:start] + body + text[end:]
    if tomllib.loads(updated)["site"]["post_build"] != command:
        raise ValueError("Mathesis hook migration did not produce the expected command")
    path.write_text(updated, encoding="utf-8")
    return ["Configured the Mathesis bootstrap: absent layer scripts and unrelated builds skip; matching papers remain strict."]
