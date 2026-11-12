"""Offline publisher adapter for the existing sdk/catalog projection (stdlib only).

This does not implement catalog schemas, render paper identities, or change receipts.
It imports an already rendered paper tree and adds book integration metadata.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[3]
REQUIRED = {"paper.json", "CITATION.cff", "formalization/nodes.json", "paper.pdf", "LICENSES/CC-BY-4.0.txt"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def safe_file(root, name):
    p = Path(name)
    require(isinstance(name, str) and name and not p.is_absolute() and
            ".." not in p.parts and ".git" not in p.parts and "\\" not in name,
            f"unsafe generated path: {name!r}")
    path = root / p
    require(path.resolve().is_relative_to(root.resolve()) and not path.is_symlink(), f"linked generated path: {name}")
    require(all(not (root / parent).is_symlink() for parent in p.parents), f"linked parent: {name}")
    return path


def projection(root):
    """Check the sdk/catalog generated_paths/sha256 contract without rewriting it."""
    manifest = read_json(root / ".mathesis/generated.json")
    names = manifest["generated_paths"]
    hashes = manifest["sha256"]
    require(len(names) == len(set(names)) and set(names) == set(hashes), "generated paths/hash keys differ")
    require(REQUIRED <= set(names), "generated manifest omits required paper files")
    require(any(n.startswith("manuscript/") for n in names), "frozen manuscript is absent")
    require(manifest["generator_version"] and re.fullmatch(r"[a-f0-9]{64}", manifest["snapshot_identity"]),
            "missing catalog generator/snapshot identity")
    for name in names:
        p = safe_file(root, name)
        require(p.is_file() and digest(p) == hashes[name], f"generated hash mismatch: {name}")
    for directory in ("manuscript", "formalization", "verification", "LICENSES"):
        for p in (root / directory).rglob("*"):
            if p.is_file():
                require(p.relative_to(root).as_posix() in hashes, f"unlisted generated file: {p}")
    paper = read_json(root / "paper.json")
    work = paper["work"]
    require(work["publication"] == "public" and work["license"] == "CC-BY-4.0", "paper is outside publication scope")
    require(isinstance(work["current_version"], int) and work["current_version"] > 0, "paper has no current version")
    require(work["title"] and work["authors"] and all(a.get("name") for a in work["authors"]), "paper identity is incomplete")
    pdf = paper["files"]["pdf"]
    require(pdf["path"] == "paper.pdf", "unexpected PDF path")
    for key in ("sha256", "public_sha256"):
        if pdf.get(key):
            require(pdf[key] == digest(root / "paper.pdf"), f"paper PDF {key} differs")
    if pdf.get("bytes") is not None:
        require(pdf["bytes"] == (root / "paper.pdf").stat().st_size, "paper PDF size differs")
    require(paper["files"]["source"]["path"] == "manuscript/", "unexpected source path")
    # source.sha256/bytes describe the downloaded source.archive, NOT the unpacked directory.
    # Per-file unpacked hashes above remain checkable when the archive is not in the projection.
    cff = citation(root / "CITATION.cff")
    for key, expected in (("title", work["title"]), ("version", str(work["current_version"])),
                          ("license", work["license"]), ("authors", [a["name"] for a in work["authors"]])):
        require(cff.get(key) == expected, f"CITATION.cff {key} differs from paper.json")
    require(cff.get("doi") == work.get("doi"), "CITATION.cff DOI differs")
    nodes = read_json(root / "formalization/nodes.json")["nodes"]
    ids = set()
    for node in nodes:
        identity = f'collected:{work["work"]}:{work["current_version"]}:{node["claim"]}'
        require(node["identity"] == identity and identity not in ids, "node identity is wrong or duplicated")
        ids.add(identity)
        require(node["work"] == work["work"] and node["record"] == work["record"] and
                node["version"] == work["current_version"], f"node belongs to another paper/version: {identity}")
        require(node["title"] == work["title"] and node["authors"] == work["authors"], f"node identity metadata differs: {identity}")
    return paper, nodes, manifest


def citation(path):
    """Read the quoted scalar/name subset emitted by sdk/catalog::render::citation.

    Reject other YAML syntax; do not guess authors or silently accept hand-edited CFF.
    The catalog remains responsible for CFF generation.
    """
    result = {"authors": []}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("  - name: "):
            result["authors"].append(json.loads(line[len("  - name: "):]))
        elif line == "authors:":
            continue
        else:
            key, sep, value = line.partition(": ")
            require(sep and not line.startswith(" "), "CFF is not sdk/catalog scalar/name output")
            result[key] = json.loads(value) if value.startswith('"') else value
    return result


def render(template, values):
    text = template.read_text(encoding="utf-8")
    for key, value in values.items():
        # JSON strings/arrays are a valid subset of TOML; control characters are escaped.
        text = text.replace("{{" + key + "}}", json.dumps(value, ensure_ascii=False))
    require("{{" not in text, f"unfilled parameter in {template.name}")
    return text


def fill(root, source, slug, title_zh, title_en, repository):
    paper, nodes, manifest = projection(source)
    work = paper["work"]
    require(re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug), "invalid paper slug")
    require(repository == f"mathesis-papers/{work['repository_name']}", "repository differs from catalog mapping")
    require(title_zh and title_en == work["title"], "provide the Chinese title and the recorded English title")
    require(not (root / "paper.json").exists() and not (root / "books" / slug).exists(),
            "paper is already populated; import a new publisher projection in a reviewed update")
    # Validate the entire input and collision set before writing.
    for name in manifest["generated_paths"]:
        require(not name.startswith(("tools/", "docs/", "skills/", "template.d/", ".github/", "books/")) and
                (name in REQUIRED or name in {"README.md", "CONTRIBUTING.md", "CHANGELOG.md"} or
                 name.startswith(("manuscript/", "verification/"))), f"unexpected catalog output: {name}")
        dest = safe_file(root, name)
        require(not dest.exists() or name in {"README.md", "CONTRIBUTING.md", "CHANGELOG.md", "LICENSES/CC-BY-4.0.txt"},
                f"publisher import would overwrite {name}")
    skeleton = root / "docs/layer-mathesis/skeleton"
    values = {"REPOSITORY": repository, "SLUG": slug, "TITLE_ZH": title_zh, "TITLE_EN": title_en,
              "VERSION": str(work["current_version"]), "VERSION_NUMBER": work["current_version"],
              "AUTHORS": [a["name"] for a in work["authors"]], "LICENSE": work["license"],
              "DATE": (work["published_on"] or "").split("T")[0], "WORK": work["work"], "SOURCE_TITLE": work["title"]}
    require(re.fullmatch(r"\d{4}-\d{2}-\d{2}", values["DATE"]), "catalog publication date is missing")
    site, book = (render(skeleton / name, values) for name in ("site.toml.in", "book.toml.in"))
    tomllib.loads(site)
    tomllib.loads(book)
    for name in [*manifest["generated_paths"], ".mathesis/generated.json"]:
        dest = safe_file(root, name)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / name, dest)
    (root / "site.toml").write_text(site, encoding="utf-8")
    book_dir = root / "books" / slug
    book_dir.mkdir(parents=True)
    (book_dir / "book.toml").write_text(book, encoding="utf-8")
    for lang, title in (("zh", title_zh), ("en", title_en)):
        edition = book_dir / lang
        edition.mkdir()
        (edition / "README.md").write_text((skeleton / "README.md.in").read_text().replace("{{TITLE}}", title), encoding="utf-8")
        (edition / "SUMMARY.md").write_text("# Summary\n\n[" + title + "](README.md)\n", encoding="utf-8")
    write_json(root / ".mathesis/book.json", {"book": slug, "work": work["work"], "version": work["current_version"],
               "titles": {"zh": title_zh, "en": title_en}, "stage": "skeleton", "results": {},
               "pending_claims": [n["identity"] for n in nodes]})
    project = root / "PROJECT.md"
    text = project.read_text(encoding="utf-8") if project.exists() else ""
    include = "@docs/layer-mathesis/PROJECT.md"
    if include not in text:
        project.write_text(text.rstrip() + "\n\n" + include + "\n", encoding="utf-8")
    print(f"Imported {work['work']} version {work['current_version']}: {len(manifest['generated_paths'])} frozen files; "
          f"created zh/en skeleton, {len(nodes)} claims pending conversion")


def check(root, complete=False):
    paper, nodes, manifest = projection(root)
    work = paper["work"]
    mapping = read_json(root / ".mathesis/book.json")
    require(mapping["work"] == work["work"] and mapping["version"] == work["current_version"], "book mapping version differs")
    require(mapping["stage"] in ("skeleton", "complete"), "unknown book conversion stage")
    slug = mapping["book"]
    require(re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug), "invalid book slug")
    cfg = tomllib.loads((root / "books" / slug / "book.toml").read_text())
    meta = cfg["book"]
    require(meta["version"] == str(work["current_version"]) and meta["authors"] == [a["name"] for a in work["authors"]]
            and meta["license"] == work["license"], "book version/authors/license differs")
    require(meta["title"] == mapping["titles"] and meta["title"]["en"] == work["title"], "book titles differ")
    require(cfg["mathesis"] == {"work": work["work"], "version": work["current_version"], "source_title": work["title"]},
            "book source identity differs")
    require(meta["editions"] == ["zh", "en"], "book editions must be zh, en in order")
    site = tomllib.loads((root / "site.toml").read_text())
    require(site["books"]["order"] == [slug] and "example-*" in site["books"]["hide"] and
            site["site"]["title"] == mapping["titles"] and site["site"]["languages"] == ["zh", "en"], "site identity/selection differs")
    require(site["site"]["repo"] == f"mathesis-papers/{work['repository_name']}", "site repository differs")
    ids = {n["identity"] for n in nodes}
    mapped = [v["claim"] for v in mapping["results"].values()]
    pending = mapping["pending_claims"]
    require(len(pending) == len(set(pending)) and not set(mapped) & set(pending) and set(mapped) | set(pending) == ids,
            "claim coverage differs: every node must be mapped or explicitly pending")
    require(all(v["claim"] in ids for v in mapping["results"].values()), "unknown mapped claim")
    os.environ["TBOOK_ROOT"] = str(root)
    sys.path.insert(0, str(root / "tools"))
    from tbook import config, model
    books = config.load_books()
    require([b.slug for b in books] == [slug], "one visible book is required")
    for lang, edition in model.load_book_models(books[0]).items():
        require(not [i for i in edition.issues if i.severity == "error"], f"book parse errors in {lang}")
        result_envs = {env.id: env for env in edition.all_envs()
                       if env.kind in (*model.FORMAL, *model.OPEN) or env.attrs.get("mathesis")}
        require(set(result_envs) == set(mapping["results"]), f"{lang} result ids differ from claim mapping")
        for result_id, env in result_envs.items():
            row = mapping["results"][result_id]
            require(env.attrs.get("mathesis") == row["claim"] and env.lean == row["gids"],
                    f"{lang} #{result_id}: claim/GIDs differ from book mapping")
            require(len(env.lean) == len(set(env.lean)), f"{lang} #{result_id}: duplicate GID")
        if complete or mapping["stage"] == "complete":
            require("Publisher-created skeleton" not in "\n".join(ch.text for ch in edition.chapters), "book still has a skeleton")
    if complete or mapping["stage"] == "complete":
        require(mapping["stage"] == "complete" and not pending, "book conversion is incomplete; release preparation refused")
    print(f"Mathesis check: {work['work']} version {work['current_version']}; "
          f"{len(manifest['generated_paths'])} generated hashes OK; identity/CFF/book OK; "
          f"{len(mapping['results'])} mapped results, {len(pending)} pending claims; stage={mapping['stage']}")
    return paper, manifest


def zenodo(root, output, tag):
    paper, manifest = check(root, complete=True)
    work = paper["work"]
    require(tag in (f"v{work['current_version']}", f"{work['repository_name']}-v{work['current_version']}"), "release tag/version differs")
    require(not output.exists(), "Zenodo artifact output already exists")
    metadata = {"metadata": {"title": work["title"], "upload_type": "publication", "publication_type": "article",
                "creators": [{"name": a["name"], **({"affiliation": a["affiliation"]} if a.get("affiliation") else {})}
                             for a in work["authors"]], "description": work.get("abstract_text") or work["title"],
                "publication_date": work["published_on"].split("T")[0], "version": str(work["current_version"]),
                "access_right": "open", "license": "cc-by-4.0"}}
    if work.get("doi"):
        metadata["metadata"]["doi"] = work["doi"]
    files = []
    for name in [*manifest["generated_paths"], ".mathesis/generated.json"]:
        dest = output / "files" / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(safe_file(root, name), dest)
        files.append({"path": "files/" + name, "sha256": digest(dest), "bytes": dest.stat().st_size})
    write_json(output / "metadata.json", metadata)
    write_json(output / "files.json", {"files": files, "source_snapshot": manifest["snapshot_identity"],
               "existing_doi": work.get("doi"), "concept_doi": work.get("concept_doi"), "tag": tag})
    print(f"Prepared Zenodo payload: {len(files)} exact files, metadata.json, files.json; no network calls")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    sub = parser.add_subparsers(dest="command", required=True)
    f = sub.add_parser("fill", help="publisher imports an sdk/catalog rendered paper and fills the book skeleton")
    f.add_argument("--input", type=Path, required=True)
    f.add_argument("--slug", required=True)
    f.add_argument("--title-zh", required=True)
    f.add_argument("--title-en", required=True)
    f.add_argument("--repository", required=True)
    c = sub.add_parser("check")
    c.add_argument("--complete", action="store_true")
    z = sub.add_parser("zenodo", help="prepare an artifact only; never deposit")
    z.add_argument("--output", type=Path, required=True)
    z.add_argument("--tag", required=True)
    args = parser.parse_args()
    try:
        root = args.root.resolve()
        if args.command == "fill":
            fill(root, args.input.resolve(), args.slug, args.title_zh, args.title_en, args.repository)
        elif args.command == "check":
            check(root, args.complete)
        else:
            zenodo(root, args.output.resolve(), args.tag)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(f"Mathesis: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
