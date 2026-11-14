"""Offline publisher adapter for the existing sdk/catalog projection (stdlib only).

This does not implement catalog schemas, render paper identities, or change receipts.
It imports an already rendered paper tree and adds book integration metadata.
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mathesis_requests import result_requests

ROOT = Path(__file__).resolve().parents[3]
REQUIRED = {"paper.json", "CITATION.cff", "formalization/nodes.json", "paper.pdf", "LICENSES/CC-BY-4.0.txt"}
FRONT_MARKER = b"\n<!-- Mathesis generated repository guide; refresh with paper.py front. -->\n"


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


def catalog_bytes(root, name):
    """The front extends, but never rewrites, the catalog's hashed README."""
    data = (root / name).read_bytes()
    return data.split(FRONT_MARKER, 1)[0] if name == "README.md" else data


def layout_rules():
    text = (ROOT / "docs/layer-mathesis/LAYOUT.md").read_text(encoding="utf-8")
    return json.loads(text.split("```json\n", 1)[1].split("```", 1)[0])


def record_path(name, rules):
    return (name in rules["record_files"] or
            any(name.startswith(d + "/") for d in rules["record_directories"]))


def catalog_path(name, rules):
    return record_path(name, rules) or name in rules["catalog_front"]


def machinery(root):
    """Use the installed ownership contracts, including layer exclusions."""
    # The upstream manifest cannot hash itself. Its config and manifest are
    # canonical machinery metadata even when omitted from the hashed file list.
    configs, entries, metadata = [], {"template.toml", "template-manifest.json"}, set()
    paths = [root / "template.toml", *sorted((root / "template.d").glob("*.toml"))]
    for path in paths:
        cfg = tomllib.loads(path.read_text(encoding="utf-8"))
        managed = cfg["managed"]
        configs.append(managed)
        manifest = (root / "template-manifest.json" if path.name == "template.toml" else
                    path.with_suffix(".manifest.json"))
        if path.name != "template.toml":
            metadata.update((path.relative_to(root).as_posix(), manifest.relative_to(root).as_posix()))
        require(manifest.is_file(), f"{manifest.relative_to(root)}: zone 3 requires its template manifest")
        entries.update(read_json(manifest)["files"])

    def under(name, entry):
        return name.startswith(entry) if entry.endswith("/") else name == entry

    def manages(name):
        return any(any(under(name, p) for p in c["paths"]) and
                   not any(name.startswith(p) for p in c.get("exclude", [])) and
                   not any(under(name, p) for p in c.get("owned", [])) for c in configs)

    entries = {n for n in entries if manages(n)}
    roots = {p.split("/")[0] for c in configs for p in c["paths"]}
    return entries, roots, metadata


def tree_entries(root, rules):
    """Ignore only untracked working output; ignored tracked files still fail."""
    tracked = set()
    result = subprocess.run(["git", "-C", str(root), "ls-files", "--cached", "-z"], capture_output=True)
    if result.returncode == 0:
        tracked = set(result.stdout.decode().split("\0")) - {""}
    for directory, dirs, files in os.walk(root, followlinks=False):
        base = Path(directory).relative_to(root)
        for name in sorted([*dirs, *files]):
            rel = (base / name).as_posix()
            if rel == ".git":
                if name in dirs:
                    dirs.remove(name)
                continue
            local = name in rules["local_only"]
            has_tracked = rel in tracked or any(n.startswith(rel + "/") for n in tracked)
            if local and not has_tracked:
                # These are the only permitted local workspaces. In a git tree
                # require an actual ignore rule, so new unignored output fails.
                ignored = result.returncode != 0 or subprocess.run(
                    ["git", "-C", str(root), "check-ignore", "-q", "--", rel]).returncode == 0
                if ignored:
                    if name in dirs:
                        dirs.remove(name)
                    continue
            yield root / rel, rel


def review_issues(root, mapping):
    paths = [p for p in (root / ".mathesis/REVIEW.md", root / ".mathesis/review.json") if p.exists()]
    if len(paths) > 1:
        return [(".mathesis/review.json", "zone 1 permits only one statement review record")]
    if not mapping["results"]:
        return []
    if not paths:
        return [(".mathesis/REVIEW.md", "zone 1 requires a statement comparison for every mapped result")]
    path = paths[0]
    name = path.relative_to(root).as_posix()
    try:
        if path.suffix == ".json":
            rows = read_json(path)["results"]
            expected = {key: {k: v.get(k) for k in ("comparison_verdict", "compared_public_gid", "comparison_commit")}
                        for key, v in mapping["results"].items()}
            require(set(rows) == set(expected), "review result ids differ from book mapping")
            for key, row in rows.items():
                require(all(row.get(k) == v for k, v in expected[key].items()) and
                        isinstance(row.get("scope"), str) and row["scope"].strip(), f"#{key}: comparison/scope differs")
        else:
            text = path.read_text(encoding="utf-8")
            rows = {}
            for line in text.splitlines():
                cells = [c.strip().strip("`") for c in line.strip().strip("|").split("|")]
                if len(cells) == 5 and cells[0] in mapping["results"]:
                    require(cells[0] not in rows, f"#{cells[0]}: duplicate review row")
                    rows[cells[0]] = cells
            require(set(rows) == set(mapping["results"]), "review result ids differ from book mapping")
            for key, row in mapping["results"].items():
                cells = rows[key]
                require(cells[1:4] == [row["comparison_verdict"], row["compared_public_gid"] or "—", row["comparison_commit"]]
                        and bool(cells[4]), f"#{key}: comparison/scope differs")
    except (ValueError, KeyError, TypeError) as exc:
        return [(name, f"zone 1 statement review: {exc}")]
    return []


def layout_issues(root):
    rules = layout_rules()
    entries, managed_roots, metadata = machinery(root)
    selected = (root / "paper.json").exists()
    paper = read_json(root / "paper.json") if selected else None
    mapping = read_json(root / ".mathesis/book.json") if selected else None
    slug = mapping["book"] if selected else None
    issues = []
    if selected:
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
            issues.append((".mathesis/book.json", "zone 2 has an invalid book slug"))
        reason = mapping.get("short_slug_reason")
        if slug != paper["work"]["work"] and not (isinstance(reason, str) and reason.strip()):
            issues.append((".mathesis/book.json", "zone 2 slug must equal the work id or document short_slug_reason"))
    books = root / "books"
    found = sorted(p.name for p in books.iterdir()) if books.is_dir() else []
    if found != ([slug] if selected else []):
        issues.append(("books", f"zone 2 requires exactly {'one book, ' + str(slug) if selected else 'zero books in an unfilled template'}; found {found}"))
    if selected:
        for name in rules["content"]:
            path = books / slug / name
            if not (path.is_file() if name == "book.toml" else path.is_dir()):
                issues.append((f"books/{slug}/{name}", "zone 2 requires the bilingual content skeleton"))
    allowed_roots = (managed_roots | set(rules["front"]) | {"books", ".mathesis", "formalization"} |
                     set(rules["record_files"]) | set(rules["record_directories"]))
    # record_files may contain a nested path, not a root entry.
    allowed_roots = {n.split("/")[0] for n in allowed_roots}
    manifest = read_json(root / ".mathesis/generated.json") if selected else {}
    hashes = manifest.get("sha256", {})
    if selected:
        names = manifest["generated_paths"]
        if len(names) != len(set(names)) or set(names) != set(hashes):
            issues.append((".mathesis/generated.json", "zone 1 generated paths/hash keys differ or are duplicated"))
        for name in REQUIRED | set(rules["catalog_front"]):
            if name not in hashes:
                issues.append((name, "zone 1 required publisher file is absent from the generated manifest"))
    for path, name in tree_entries(root, rules):
        parts = Path(name).parts
        is_file = path.is_file() or path.is_symlink()
        known_machine = name in entries
        frozen = record_path(name, rules) and name in hashes
        if len(parts) == 1 and name not in allowed_roots:
            issues.append((name, "four zones: unknown root entry"))
        if is_file and not path.is_symlink() and path.stat().st_size > rules["size_limit"] and not (
                name in ("paper.pdf", "source.archive") or name.startswith("manuscript/")):
            issues.append((name, "all zones: exceeds 2 MiB; only paper.pdf and manuscript/ are exempt"))
        if is_file and Path(name).suffix.lower() in rules["built_suffixes"] and not (
                name in ("paper.pdf", "source.archive") or name.startswith("manuscript/")):
            issues.append((name, "all zones: built output must stay outside the repository"))
        if not known_machine and not frozen:
            if any(name == d or name.startswith(d + "/") or d in parts for d in rules["forbidden_directories"]) or any(
                    fnmatch.fnmatchcase(path.name.lower(), p) for p in rules["forbidden_filenames"]):
                issues.append((name, "all zones: preparation debris/run records belong outside the repository"))
        if parts[0] == "books":
            if len(parts) > 1 and parts[1] != slug:
                issues.append((name, "zone 2 forbids extra books, including hidden upstream examples"))
            elif len(parts) > 2 and parts[2] not in rules["content"]:
                issues.append((name, "zone 2 permits only the documented book content entries"))
            elif is_file and path.suffix == ".py" and len(parts) > 2 and parts[2] != "figures":
                issues.append((name, "zone 2 permits Python source only as a reusable figure generator"))
        elif parts[0] == ".mathesis":
            if name != ".mathesis" and name not in rules["record_metadata"]:
                issues.append((name, "zone 1 permits only the manifest, book mapping and sole statement review"))
        elif record_path(name, rules):
            if is_file and name not in hashes:
                issues.append((name, "zone 1 paper-record file is unlisted in .mathesis/generated.json"))
        elif parts[0] == "formalization":
            if len(parts) > 1:
                issues.append((name, "zone 1 permits only formalization/nodes.json"))
        elif parts[0] == "template.d":
            if len(parts) > 1 and name not in metadata:
                issues.append((name, "zone 4 permits only installed layer configs and manifests in template.d/"))
        elif name in rules["front"]:
            if path.is_dir():
                issues.append((name, "zone 4 front entries must be files"))
        elif known_machine or (path.is_dir() and any(n.startswith(name + "/") for n in entries)):
            pass
        elif len(parts) > 1 or parts[0] in managed_roots:
            issues.append((name, "zone 3 path is not listed in an installed template manifest"))
        if path.is_symlink() and not known_machine:
            issues.append((name, "zones 1–2 and 4 require real files/directories, not symlinks"))
    if selected:
        for name in hashes:
            if not catalog_path(name, rules):
                issues.append((name, "zone 1 generated manifest cannot claim content, machinery or unknown paths"))
            else:
                path = safe_file(root, name)
                if not path.is_file() or hashlib.sha256(catalog_bytes(root, name)).hexdigest() != hashes[name]:
                    issues.append((name, "zone 1 generated hash mismatch against .mathesis/generated.json"))
        issues.extend(review_issues(root, mapping))
        if (root / "README.md").is_file() and (root / "README.md").read_bytes() != front_bytes(root):
            issues.append(("README.md", "zone 4 generated repository guide differs; run paper.py front"))
    return sorted(set(issues))


def check_layout(root):
    issues = layout_issues(root)
    require(not issues, "layout violations:\n" + "\n".join(f"  {name}: {rule}" for name, rule in issues))
    print("Mathesis layout: four zones OK")


def front_bytes(root):
    paper = read_json(root / "paper.json")
    work = paper["work"]
    mapping = read_json(root / ".mathesis/book.json")
    slug = mapping["book"]
    site = tomllib.loads((root / "site.toml").read_text())["site"]
    base = site["base_url"].rstrip("/") + "/"
    media = []
    for directory, label, pattern in (("slides", "Slides", "*/deck.toml"), ("films", "Videos", "*/film.json"), ("viz", "Visualizations", "*/index.html")):
        source = root / "books" / slug / directory
        if source.is_dir() and any(p.is_file() for p in source.glob(pattern)):
            media.append(f"[{label}]({base}{slug}/{directory}/) ([sources](books/{slug}/{directory}/))")
    guide = ["", "## Reading and materials", "", f"[Paper site]({base}) · [Frozen PDF](paper.pdf) · [Citation](CITATION.cff)", "",
             f"[中文阅读]({base}{slug}/zh/) · [Read in English]({base}{slug}/en/)", "",
             " · ".join(media) or "Media sources have not been prepared yet.", "",
             "These are publication routes; available built materials are inventoried in "
             f"[mathesis-materials.json]({base}mathesis-materials.json).", "",
             "## Book and formalization", "",
             "Catalog formalization status above is separate from the statement comparisons below. "
             "A nearby declaration does not verify the complete written result.", "",
             "| Book result | Comparison with formal base | Compared declaration |", "|---|---|---|"]
    for key, row in mapping["results"].items():
        gid = row.get("compared_public_gid")
        guide.append(f"| `{key}` | {row.get('comparison_verdict', 'pending')} | " + (f"`{gid}`" if gid else "—") + " |")
    if not mapping["results"]:
        guide.append("| Pending conversion | Not yet compared | — |")
    review = ".mathesis/review.json" if (root / ".mathesis/review.json").exists() else ".mathesis/REVIEW.md"
    guide += ["", f"Book stage: **{mapping['stage']}**; {len(mapping['pending_claims'])} pending claims. "
              + (f"[Statement comparisons]({review})." if mapping["results"] else "Comparisons begin with content preparation."), "",
              "## Repository map", "", "| Zone | Location |", "|---|---|",
              "| Paper record | `paper.json`, `CITATION.cff`, `paper.pdf`, `manuscript/`, `formalization/nodes.json`, `LICENSES/`, `.mathesis/` |",
              f"| Content | `books/{slug}/`: Chinese/English text, figures, visualizations, videos, slides, assets |",
              "| Machinery | Upstream and layer managed paths; update with `tbook template update` |",
              "| Repository front | This README, changelog, contribution guide, licence, project/site/pin configuration, `template.d/` |", "",
              "See [the enforced layout](docs/layer-mathesis/LAYOUT.md). Preparation run records and built outputs stay outside the committed tree.", ""]
    return catalog_bytes(root, "README.md") + FRONT_MARKER + "\n".join(guide).encode("utf-8")


def front(root):
    if not (root / "paper.json").exists():
        (root / "README.md").write_text(
            "# Mathesis paper template\n\nOne repository for one exact Mathesis paper version. "
            "This template has no selected paper and no example books.\n\n"
            "The upstream books template supplies the machinery; Mathesis layer 0.5.0 "
            "supplies the publisher adapter and the [enforced four-zone layout](docs/layer-mathesis/LAYOUT.md).\n\n"
            "Use [the publisher pipeline](docs/layer-mathesis/PIPELINE.md) to import a public projection "
            "with `paper.py fill`. It creates the paper record, one bilingual content skeleton and a generated paper README. "
            "Upgrade with `tbook template update`; keep preparation run records outside the repository.\n", encoding="utf-8")
    else:
        # Validate the frozen prefix before overwriting a generated guide.
        manifest = read_json(root / ".mathesis/generated.json")
        require(hashlib.sha256(catalog_bytes(root, "README.md")).hexdigest() == manifest["sha256"]["README.md"],
                "README.md: catalog prefix hash mismatch; publisher repair required")
        (root / "README.md").write_bytes(front_bytes(root))
    print("Generated README.md repository front")


def tidy(root, apply=False, archive=None):
    rules = layout_rules()
    entries, _, _ = machinery(root)
    mapping_path = root / ".mathesis/book.json"
    slug = read_json(mapping_path)["book"] if mapping_path.exists() else None
    moves, protected = [], []
    for name, rule in layout_issues(root):
        path = root / name
        if not path.exists() and not path.is_symlink():
            protected.append((name, rule))
            continue
        example = (len(path.relative_to(root).parts) >= 2 and
                   path.relative_to(root).parts[0] == "books" and
                   path.relative_to(root).parts[1].startswith("example-") and
                   path.relative_to(root).parts[1] != slug)
        if example:
            path = root / "books" / path.relative_to(root).parts[1]
        elif (name == "books" or name.startswith("books/") or name in rules["record_metadata"] or
              name == ".mathesis" or name.startswith(".mathesis/") or name.startswith("formalization/") or
              record_path(name, rules) or name in entries or name in rules["front"] or
              name.startswith("template.d/")):
            protected.append((name, rule))
            continue
        if not any(path == p or p in path.parents for p in moves):
            moves = [p for p in moves if path not in p.parents]
            moves.append(path)
    # A root violation may contain protected bytes; never move an ancestor of them.
    moves = [p for p in moves if not any((root / n).is_relative_to(p) for n, _ in protected)]
    if archive is not None:
        archive = archive.resolve()
        require(not archive.is_relative_to(root.resolve()), "tidy archive must be outside the repository")
        require(not archive.exists(), "tidy archive already exists; choose a fresh external destination")
    for path in sorted(moves):
        print(f"{'MOVE' if apply else 'WOULD MOVE'} {path.relative_to(root)} -> external archive")
    for name, rule in sorted(set(protected)):
        print(f"PRESERVE {name}: {rule}; owner repair required")
    if apply and moves:
        if archive is None:
            archive = Path(tempfile.mkdtemp(prefix="mathesis-tidy-"))
        else:
            archive.mkdir(parents=True)
        for path in moves:
            dest = archive / path.relative_to(root)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(path), dest)
        print(f"Archived {len(moves)} entries outside the repository: {archive}")
    elif not moves:
        print("Tidy: no movable layout violations")
    return moves, protected


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
        require(catalog_path(name, layout_rules()), f"{name}: zone 1 unexpected catalog output")
        p = safe_file(root, name)
        require(p.is_file() and hashlib.sha256(catalog_bytes(root, name)).hexdigest() == hashes[name], f"generated hash mismatch: {name}")
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


def fill(root, source, slug, title_zh, title_en, repository, short_slug_reason=None):
    paper, nodes, manifest = projection(source)
    work = paper["work"]
    require(re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug), "invalid paper slug")
    require(slug == work["work"] or short_slug_reason and short_slug_reason.strip(),
            "zone 2 slug must equal the work id or provide --short-slug-reason")
    require(repository == f"mathesis-papers/{work['repository_name']}", "repository differs from catalog mapping")
    require(title_zh and title_en == work["title"], "provide the Chinese title and the recorded English title")
    require(not (root / "paper.json").exists() and not (root / "books" / slug).exists(),
            "paper is already populated; import a new publisher projection in a reviewed update")
    require(not [issue for issue in layout_issues(root) if not (
            issue[0] == "books" or issue[0].startswith("books/example-"))],
            "fill requires a clean template layout; run paper.py tidy --dry-run first")
    # Validate the entire input and collision set before writing.
    for name in manifest["generated_paths"]:
        require(catalog_path(name, layout_rules()), f"unexpected catalog output: {name}")
        dest = safe_file(root, name)
        require(not dest.exists() or name in {"README.md", "CONTRIBUTING.md", "CHANGELOG.md", "LICENSES/CC-BY-4.0.txt"},
                f"publisher import would overwrite {name}")
    skeleton = root / "docs/layer-mathesis/skeleton"
    values = {"SITE_BASE": "https://papers.trureturing.org/" + work["repository_name"] + "/",
              "SITE_POST_BUILD": read_json(ROOT / "docs/layer-mathesis/site-hook.json"),
              "REPOSITORY": repository, "SLUG": slug, "TITLE_ZH": title_zh, "TITLE_EN": title_en,
              "VERSION": str(work["current_version"]), "VERSION_NUMBER": work["current_version"],
              "AUTHORS": [a["name"] for a in work["authors"]], "LICENSE": work["license"],
              "DATE": (work["published_on"] or "").split("T")[0], "WORK": work["work"], "SOURCE_TITLE": work["title"]}
    require(re.fullmatch(r"\d{4}-\d{2}-\d{2}", values["DATE"]), "catalog publication date is missing")
    site, book = (render(skeleton / name, values) for name in ("site.toml.in", "book.toml.in"))
    tomllib.loads(site)
    tomllib.loads(book)
    existing_books = list((root / "books").iterdir()) if (root / "books").exists() else []
    require(all(p.is_dir() and not p.is_symlink() and p.name.startswith("example-") for p in existing_books),
            "zone 2 fill refuses existing non-example content; choose an empty paper template")
    # Preserve even locally changed examples outside the repository before removal.
    if existing_books:
        archive = Path(tempfile.mkdtemp(prefix="mathesis-fill-examples-"))
        for path in existing_books:
            shutil.move(str(path), archive / path.name)
        print(f"Moved upstream examples outside the repository: {archive}")
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
    for name in layout_rules()["empty_media"]:
        directory = book_dir / name
        directory.mkdir()
        (directory / ".gitkeep").touch()
    write_json(root / ".mathesis/book.json", {"book": slug, "work": work["work"], "version": work["current_version"],
               "titles": {"zh": title_zh, "en": title_en}, "stage": "skeleton", "results": {},
               "pending_claims": [n["identity"] for n in nodes]})
    if short_slug_reason:
        mapping = read_json(root / ".mathesis/book.json")
        mapping["short_slug_reason"] = short_slug_reason
        write_json(root / ".mathesis/book.json", mapping)
    project = root / "PROJECT.md"
    text = project.read_text(encoding="utf-8") if project.exists() else ""
    include = "@docs/layer-mathesis/PROJECT.md"
    if include not in text:
        project.write_text(text.rstrip() + "\n\n" + include + "\n", encoding="utf-8")
    front(root)
    check_layout(root)
    print(f"Imported {work['work']} version {work['current_version']}: {len(manifest['generated_paths'])} frozen files; "
          f"created zh/en skeleton, {len(nodes)} claims pending conversion")


def check(root, complete=False):
    check_layout(root)
    if not (root / "paper.json").exists():
        require(not complete, "unfilled template cannot prepare a paper release")
        print("Mathesis template: no selected paper")
        return None, None
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
    require(site["books"]["order"] == [slug] and
            site["site"]["title"] == mapping["titles"] and site["site"]["languages"] == ["zh", "en"], "site identity/selection differs")
    require(site["site"]["repo"] == f"mathesis-papers/{work['repository_name']}", "site repository differs")
    ids = {n["identity"] for n in nodes}
    mapped = [v["claim"] for v in mapping["results"].values()]
    pending = mapping["pending_claims"]
    require(len(pending) == len(set(pending)) and not set(mapped) & set(pending) and set(mapped) | set(pending) == ids,
            "claim coverage differs: every node must be mapped or explicitly pending")
    require(all(v["claim"] in ids for v in mapping["results"].values()), "unknown mapped claim")
    result_requests(mapping)
    os.environ["TBOOK_ROOT"] = str(root)
    sys.path.insert(0, str(root / "tools"))
    from tbook import config, model
    require(getattr(model, "WRITTEN_PROOF", None) == "written-proof",
            'Mathesis layer 0.5.0 requires upstream written-proof support '
            '(status="written-proof" with proof="id"). Update the upstream template '
            'to version 0.8.2 or later before checking or publishing this paper.')
    from tbook import site as book_site
    require(callable(getattr(book_site, "post_build", None)),
            "Mathesis layer 0.5.0 requires upstream site.post_build support; update to upstream 0.8.2 or later before publishing")
    require(site["site"].get("post_build") == read_json(ROOT / "docs/layer-mathesis/site-hook.json"),
            "site.post_build must run the Mathesis site postprocessor; apply the layer migration")
    from tbook import check as book_check, lean
    books = config.load_books()
    require([b.slug for b in books] == [slug], "one visible book is required")
    editions = model.load_book_models(books[0])
    parity_issues = []
    book_check.check_parity(books[0], editions, parity_issues)
    require(not parity_issues, "book edition parity: " + "; ".join(i.message for i in parity_issues))
    for lang, edition in editions.items():
        require(not [i for i in edition.issues if i.severity == "error"], f"book parse errors in {lang}")
        policy_issues = []
        book_check.check_env_policy(edition, policy_issues)
        require(not policy_issues, f"{lang} book evidence policy: " + "; ".join(i.message for i in policy_issues))
        result_envs = {env.id: env for env in edition.all_envs()
                       if env.kind in (*model.FORMAL, *model.OPEN) or env.attrs.get("mathesis")}
        require(set(result_envs) == set(mapping["results"]), f"{lang} result ids differ from claim mapping")
        for result_id, env in result_envs.items():
            row = mapping["results"][result_id]
            if row.get("formalization_request") and env.attrs.get("request"):
                require(row["formalization_request"]["url"] == env.attrs["request"],
                        f"{lang} #{result_id}: book mapping and written-proof request differ")
            require(env.attrs.get("mathesis") == row["claim"] and env.lean == row["gids"],
                    f"{lang} #{result_id}: claim/GIDs differ from book mapping")
            require(len(env.lean) == len(set(env.lean)), f"{lang} #{result_id}: duplicate GID")
            verdict = row.get("comparison_verdict")
            require(verdict in ("same", "special case", "variant", "none"),
                    f"{lang} #{result_id}: comparison_verdict must be same / special case / variant / none")
            require("compared_public_gid" in row and "comparison_commit" in row,
                    f"{lang} #{result_id}: record compared_public_gid (or null) and comparison_commit")
            closest = row["compared_public_gid"]
            require(isinstance(row["comparison_commit"], str) and
                    re.fullmatch(r"[a-f0-9]{40}", row["comparison_commit"]),
                    f"{lang} #{result_id}: comparison_commit must be the inspected full commit")
            if verdict == "none":
                require(closest is None, f"{lang} #{result_id}: none requires compared_public_gid=null")
            else:
                require(isinstance(closest, str) and bool(closest),
                        f"{lang} #{result_id}: comparison needs the inspected closest public declaration")
                try:
                    lean.parse_gid(closest)
                except lean.LeanError as exc:
                    raise ValueError(f"{lang} #{result_id}: invalid compared_public_gid: {exc}") from exc
            if verdict == "same":
                require(env.kind in model.FORMAL and env.status == "lean" and closest in env.lean,
                        f"{lang} #{result_id}: same requires a formal result citing that exact declaration")
            else:
                require(not env.lean, f"{lang} #{result_id}: a special case / variant / none must not cite Lean as verification")
                if env.kind in model.FORMAL:
                    require(env.status == model.WRITTEN_PROOF,
                            f"{lang} #{result_id}: manuscript-proved unmatched results require written-proof")
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
        safe_file(root, name)
        dest.write_bytes(catalog_bytes(root, name))
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
    f.add_argument("--short-slug-reason", help="document the short form of the work id, if needed")
    c = sub.add_parser("check")
    c.add_argument("--complete", action="store_true")
    c.add_argument("--layout-only", action="store_true", help="check layout independently of evidence/publication gates")
    sub.add_parser("front", help="regenerate the README guide, preserving the hashed catalog prefix")
    t = sub.add_parser("tidy", help="archive layout violations outside the repository; preserve paper record and content")
    mode = t.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    t.add_argument("--archive", type=Path, help="fresh external archive destination (default: unique temporary directory)")
    z = sub.add_parser("zenodo", help="prepare an artifact only; never deposit")
    z.add_argument("--output", type=Path, required=True)
    z.add_argument("--tag", required=True)
    args = parser.parse_args()
    try:
        root = args.root.resolve()
        if args.command == "fill":
            fill(root, args.input.resolve(), args.slug, args.title_zh, args.title_en, args.repository, args.short_slug_reason)
        elif args.command == "check":
            check_layout(root) if args.layout_only else check(root, args.complete)
        elif args.command == "front":
            front(root)
        elif args.command == "tidy":
            tidy(root, args.apply, args.archive)
        else:
            zenodo(root, args.output.resolve(), args.tag)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(f"Mathesis: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
