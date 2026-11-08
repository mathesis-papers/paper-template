"""Well-known locations inside a books repository."""

from __future__ import annotations

import os
from pathlib import Path

# tools/tbook/paths.py -> repository root
ROOT = Path(os.environ.get("TBOOK_ROOT") or Path(__file__).resolve().parents[2])

TOOLS = ROOT / "tools"
THEME = ROOT / "theme"
TEMPLATES = ROOT / "templates"
BOOKS = ROOT / "books"
BUILD = ROOT / "build"
SITE_OUT = ROOT / "_site"
CACHE = ROOT / ".cache"

SITE_TOML = ROOT / "site.toml"
TEMPLATE_TOML = ROOT / "template.toml"
LOCK_FILE = ROOT / "trureturing.lock.json"
TOKENS = THEME / "tokens.json"
GENERATED = THEME / "generated"
I18N_THEME = THEME / "i18n"
I18N_LOCAL = ROOT / "i18n"


def rel(path: Path) -> str:
    """Repository-relative POSIX path for messages."""
    try:
        return Path(path).resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)
