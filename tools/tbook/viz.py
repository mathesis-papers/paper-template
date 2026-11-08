"""Book-local viz support. STUB — to be implemented (see docs/ARCHITECTURE.md §Contracts)."""

from __future__ import annotations

from pathlib import Path


def check_ref(book, src: str) -> str | None:
    """Return an error message if ``src`` does not name a usable viz, else None."""
    return None


def check(book) -> list:
    """Validate the book's viz directory; return a list of model.Issue."""
    return []


def items(book) -> list[dict]:
    """Registry entries shown on the book's landing page."""
    return []


def render_embed(env, ctx, inner: str, doc) -> str:
    """Markdown/HTML that replaces a ``::: {.viz src=…}`` block for ctx.target."""
    src = env.attrs.get("src")
    return f"> **viz: {src}**\n>\n> {inner.strip()}"


def build(site, book, out_dir: Path) -> None:
    """Publish the book's viz pages into ``out_dir`` (``_site/<slug>/viz/``)."""
    raise NotImplementedError
