#!/usr/bin/env python3
"""Mathesis single-paper site postprocessor. Called by tbook's site.post_build."""
import html
import json
import os
from pathlib import Path
import re
import sys

SCRIPT_PATH = Path("docs/layer-mathesis/scripts/site.py")


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def emit(root, out):
    mapping = load(root / ".mathesis/book.json")
    work = load(root / "paper.json")["work"]
    manifest = load(out / "manifest.json")
    slug = mapping["book"]
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
        raise ValueError("invalid Mathesis book slug")
    books = manifest["books"]
    if manifest["schema"] != "trureturing-books.site.v1" or len(books) != 1 or books[0]["slug"] != slug:
        raise ValueError("Mathesis requires exactly one published book")
    if mapping["work"] != work["work"] or mapping["version"] != work["current_version"]:
        raise ValueError("Mathesis mapping and paper identity differ")
    repo = "mathesis-papers/" + work["repository_name"]
    if manifest["site"]["repo"] != repo:
        raise ValueError("site repository differs from paper")
    base = "https://papers.trureturing.org/" + work["repository_name"] + "/"

    def url(path):
        # Advertise only actual output, never a promised reading or missing PDF.
        if not isinstance(path, str) or path.startswith("/") or "\\" in path or any(p in (".", "..") for p in path.split("/")):
            raise ValueError("invalid published material path")
        target = out / path
        if not target.resolve().is_relative_to(out.resolve()):
            raise ValueError("published material escapes site")
        target = target / "index.html" if path.endswith("/") else target
        return base + path if target.is_file() and target.stat().st_size else None

    book = books[0]
    reading = {}
    for edition in book["editions"]:
        path = edition.get("html")
        if path and (value := url(path)):
            reading[edition["lang"]] = value
    slides = {}
    for file in book["files"]:
        kind = file["kind"]
        if kind not in ("slides-pdf", "slides-notes-pdf"):
            continue
        value = url(file["path"])
        if not value:
            continue
        key = (file["variant"], file["lang"])
        row = slides.setdefault(key, {"id": key[0], "language": key[1], "pdf_url": None, "notes_url": None})
        row["pdf_url" if kind == "slides-pdf" else "notes_url"] = value
    viz = []
    for identity in sorted(book["media"].get("viz", [])):
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", identity):
            raise ValueError("invalid visualization id")
        if value := url(f"{slug}/viz/{identity}/"):
            viz.append({"id": identity, "url": value})
    videos = []
    registry = out / slug / "films/films.json"
    if registry.is_file():
        films = load(registry)
        if films.get("book") != slug:
            raise ValueError("film registry differs from selected book")
        for film in films["films"]:
            if not film.get("built") or film["id"] not in book["media"].get("films", []):
                continue
            if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", film["id"]):
                raise ValueError("invalid film id")
            for variant, path in sorted(film.get("videos", {}).items()):
                if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", variant) or not path.endswith(".mp4"):
                    raise ValueError("invalid film output")
                mp4 = url(f"{slug}/films/{path}")
                page = url(f"{slug}/films/")
                if mp4 and page:
                    poster = url(f"{slug}/films/{film['poster']}") if film.get("poster") else None
                    videos.append({"id": film["id"] + "-" + variant, "title": film.get("title") or film["id"],
                                   "url": page + "#" + film["id"], "mp4_url": mp4, "poster_url": poster})
    requests = []
    seen = set()
    for request in manifest.get("formalization_requests", []):
        uses = [use for use in request["uses"] if use["book"] == slug]
        if not uses:
            continue
        address = request["request"]
        if not re.fullmatch(r"https://github.com/the-omega-institute/trureturing-requests/issues/[1-9][0-9]{0,19}", address):
            raise ValueError("invalid formalization request URL")
        if address in seen:
            raise ValueError("duplicate formalization request")
        seen.add(address)
        labels = sorted({re.sub(r"\s*\((?:thm|lem|cor|prop):[^)]+\)", "", use["source"]) for use in uses})
        requests.append({"url": address, "label": "; ".join(labels)})
    materials = {"schema": "mathesis.materials.v1", "work": work["work"], "version": work["current_version"],
                 "repository_url": "https://github.com/" + repo, "site_url": base, "doi": work.get("doi"),
                 "reading": reading, "slides": [slides[k] for k in sorted(slides)], "visualizations": viz,
                 "videos": videos, "formalization_requests": sorted(requests, key=lambda r: int(r['url'].rsplit('/', 1)[1]))}
    if not (out / slug / "index.html").is_file():
        raise ValueError("book landing page is missing")
    # Keep the nested landing and every reader/media URL intact.
    target = html.escape(slug + "/", quote=True)
    (out / "index.html").write_text(
        '<!doctype html>\n<html lang="en"><meta charset="utf-8">'
        f'<meta http-equiv="refresh" content="0;url={target}">'
        f'<link rel="canonical" href="{html.escape(base + slug + "/", quote=True)}">'
        '<title>Mathesis paper</title><p><a href="' + target + '">Open the paper</a></p></html>\n', encoding="utf-8")
    (out / "mathesis-materials.json").write_text(json.dumps(materials, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(f"Mathesis site: root → {slug}/; {len(reading)} readings, {len(slides)} slide editions, {len(viz)} visualizations")
    return materials


def post_build(root, out):
    """Apply paper policy only when this build contains the selected Mathesis book.

    The hook's cwd is the repository being built. Inherited site settings and an
    externally invoked copy of this script must not select the script's repository.
    Keep emit strict: once the mapped book is present, every inconsistency fails.
    """
    if not (root / SCRIPT_PATH).is_file():
        print("Mathesis post-build skipped: layer script is absent from repository being built")
        return
    mapping_path = root / ".mathesis/book.json"
    if not mapping_path.exists() and not mapping_path.is_symlink():
        print("Mathesis post-build skipped: no .mathesis/book.json in repository being built")
        return
    mapping = load(mapping_path)
    manifest = load(out / "manifest.json")
    if not any(book["slug"] == mapping["book"] for book in manifest["books"]):
        print(f"Mathesis post-build skipped: mapped book {mapping['book']!r} is absent from site manifest")
        return
    return emit(root, out)


if __name__ == "__main__":
    try:
        post_build(Path.cwd(), Path(os.environ["TBOOK_SITE_OUT"]))
    except (KeyError, ValueError, OSError, TypeError) as exc:
        sys.exit(f"Mathesis site: {exc}")
