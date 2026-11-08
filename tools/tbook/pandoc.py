"""PDF (Pandoc → Typst) and EPUB (Pandoc, Apple Books) pipeline. STUB."""

from __future__ import annotations

from pathlib import Path


def build_pdf(site, book, edition, model, lock, variant: str, out_path: Path) -> Path:
    raise NotImplementedError


def build_epub(site, book, edition, model, lock, out_path: Path) -> Path:
    raise NotImplementedError
