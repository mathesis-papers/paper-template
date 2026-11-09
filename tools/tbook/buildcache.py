"""Build cache: a build unit whose inputs did not change is not built again.

A *unit* is what one build step produces: an edition's HTML, one PDF variant or the EPUB of an
edition, a book's slides, a film's videos. Its *key* is the SHA-256 of everything its outputs depend
on (:class:`Inputs`: the source files, theme and tool code, the lock file, site settings, the versions
of the tools that run). :func:`run` looks the key up before building:

1. the local store ``.cache/artifacts/<target>/<unit>/<key>/``. On GitHub Actions the store itself is
   saved and restored with the Actions cache (``.github/actions/build-cache``), from pushes to the
   default branch only;
2. with ``TBOOK_CACHE_REMOTE=1``, the newest published releases of the repository: ``./tbook cache
   export`` writes one tar per unit and ``build-cache.json`` (unit, key, asset name, SHA-256), which
   release.yml attaches to the release of the whole site;
3. on a miss it builds the unit and stores its outputs under the key.

A hit copies the stored outputs to where the build writes them, so the rest of the build cannot tell
the difference. Every stored file's SHA-256 is recorded in ``entry.json`` and checked when it is
restored; a release asset is checked against ``build-cache.json`` and the digest GitHub reports.
Keys are input-addressed: two builds from the same inputs share a key even when their bytes differ
(video encoders, PDF exporters), and a changed input always gives a new key. Each unit keeps its
newest :data:`KEEP` entries; ``./tbook cache prune`` keeps only those of the current inputs.

``TBOOK_CACHE=0`` turns the cache off (every unit is built, nothing is stored).
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import platform
import re
import shutil
import subprocess
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Iterable

from . import config, paths

SCHEMA = "trureturing-books.build-cache.v1"
MANIFEST = "build-cache.json"  # the release asset that lists the release's cache entries
ENTRY = "entry.json"
VERSION = "1"  # part of every key: bump it to rebuild everything once
KEEP = 2  # entries kept per unit in the local store
REMOTE_RELEASES = 5  # newest published releases searched for an entry
TARGETS = ("html", "pdf", "epub", "slides", "films")
# Directories never part of a unit's inputs (when git cannot list the files).
SKIP_DIRS = frozenset({".git", "__pycache__", "node_modules", ".slidev", ".vite", "out", ".cache", "build", "_site"})


def store_root() -> Path:
    return paths.CACHE / "artifacts"


def enabled() -> bool:
    return os.environ.get("TBOOK_CACHE", "1") != "0"


def remote_enabled() -> bool:
    return enabled() and os.environ.get("TBOOK_CACHE_REMOTE") == "1"


def _say(msg: str) -> None:
    print(f"  {msg}", flush=True)


# --------------------------------------------------------------------------- inputs and keys

_DIGESTS: dict[tuple[str, int, int], str] = {}


def file_digest(path: Path) -> str:
    """SHA-256 of a file's content (memoized by path, size and mtime within a process)."""
    st = path.stat()
    memo = (str(path), st.st_size, st.st_mtime_ns)
    if memo not in _DIGESTS:
        h = hashlib.sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        _DIGESTS[memo] = h.hexdigest()
    return _DIGESTS[memo]


@lru_cache(maxsize=None)
def _git_files(root: str) -> frozenset[str] | None:
    """Files git would commit under ``root`` (tracked, or untracked and not ignored), repository-relative;
    None when ``root`` is not in a git work tree."""
    try:
        r = subprocess.run(["git", "-C", root, "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
                           capture_output=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    top = subprocess.run(["git", "-C", root, "rev-parse", "--show-prefix"], capture_output=True, text=True)
    prefix = top.stdout.strip() if top.returncode == 0 else ""
    out = set()
    for name in r.stdout.decode("utf-8", "surrogateescape").split("\0"):
        if name and name.startswith(prefix):
            out.add(name[len(prefix):])
    return frozenset(out)


def _files_under(path: Path) -> list[Path]:
    """The source files under ``path`` (a file or directory): what git would commit when ROOT is a git work
    tree (so build outputs and ignored files never count), otherwise every file outside :data:`SKIP_DIRS`."""
    if path.is_file():
        return [path]
    if not path.is_dir():
        return []
    listed = _git_files(str(paths.ROOT))
    try:
        rel = path.resolve().relative_to(paths.ROOT.resolve()).as_posix()
    except ValueError:
        listed = None
        rel = ""
    if listed is not None:
        head = "" if rel in ("", ".") else rel + "/"
        return [paths.ROOT / name for name in sorted(listed) if name.startswith(head) and (paths.ROOT / name).is_file()]
    found = []
    for dirpath, dirnames, filenames in os.walk(path):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        found += [Path(dirpath) / f for f in sorted(filenames) if not f.endswith(".pyc") and f != ".DS_Store"]
    return found


@dataclass
class Inputs:
    """What a unit's outputs depend on, as (label, digest) pairs; :meth:`key` hashes them in order."""

    parts: list[tuple[str, str]] = field(default_factory=list)

    def files(self, *items: Path, exclude: Iterable[str] = ()) -> "Inputs":
        """Every file under each of ``items`` (files or directories), by repository-relative path and
        content; a missing item counts as missing. ``exclude``: path fragments (``/out/``) to leave out."""
        skip = tuple(exclude)
        for item in items:
            item = Path(item)
            label = paths.rel(item)
            found = _files_under(item)
            if not found:
                self.parts.append((label, "missing"))
                continue
            for f in found:
                name = paths.rel(f)
                if any(s in "/" + name for s in skip):
                    continue
                self.parts.append((name, file_digest(f)))
        return self

    def text(self, label: str, value: Any) -> "Inputs":
        data = value if isinstance(value, str) else json.dumps(value, sort_keys=True, ensure_ascii=False)
        self.parts.append((f"<{label}>", hashlib.sha256(data.encode("utf-8")).hexdigest()))
        return self

    def key(self) -> str:
        h = hashlib.sha256(f"{SCHEMA}\n{VERSION}\n".encode())
        for label, digest in self.parts:
            h.update(f"{label}\t{digest}\n".encode("utf-8", "surrogateescape"))
        return h.hexdigest()


@lru_cache(maxsize=None)
def tool_version(*cmd: str) -> str:
    """First line of ``cmd --version`` (or of ``cmd`` when it already has arguments); 'missing' if it
    cannot run."""
    if not cmd or not cmd[0]:
        return "missing"
    args = list(cmd) if len(cmd) > 1 else [cmd[0], "--version"]
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return "missing"
    text = (r.stdout or r.stderr).strip()
    return text.splitlines()[0] if text else f"exit {r.returncode}"


def node_version() -> str:
    return tool_version(os.environ.get("NODE") or shutil.which("node") or "")


def chromium_version() -> str:
    """The Chromium that Playwright drives: $PW_CHROMIUM_PATH's version, or Playwright's own build (its
    version is fixed by package-lock.json)."""
    exe = os.environ.get("PW_CHROMIUM_PATH")
    return tool_version(exe) if exe else "playwright-chromium (package-lock.json)"


def _python() -> str:
    return ".".join(platform.python_version_tuple()[:2])


def site_inputs(site: config.Site) -> Inputs:
    """What every HTML, PDF, EPUB and slides unit depends on: the tool and theme code, site settings,
    the lock file, the pinned packages, the site's address (links and paths are built from it)."""
    return (Inputs()
            .files(paths.TOOLS / "tbook", paths.TOOLS / "filters", paths.TOOLS / "node", paths.THEME,
                   paths.I18N_LOCAL, paths.SITE_TOML, paths.LOCK_FILE, paths.ROOT / "requirements.txt",
                   paths.ROOT / "package-lock.json")
            .text("base_url", site.base_url or "")
            .text("repo", site.repo or "")
            .text("python", _python()))


# --------------------------------------------------------------------------- units


@dataclass
class Unit:
    target: str  # one of TARGETS
    name: str  # "<slug>/<lang>", "<slug>/<lang>/<variant>", "<slug>", "<slug>/<film id>"
    inputs: Inputs
    outputs: list[Path]  # the files and directories the build writes, under the repository root

    @property
    def key(self) -> str:
        """The inputs' key, specific to this unit (its target and name: language, PDF variant, film)."""
        return hashlib.sha256(f"{self.inputs.key()}\n{self.target}\n{self.name}".encode()).hexdigest()

    @property
    def label(self) -> str:
        return f"{self.target} {self.name}"

    def entry_dir(self, key: str | None = None) -> Path:
        return store_root() / self.target / self.name / (key or self.key)


def html_unit(site: config.Site, book: config.Book, lang: str, out_dir: Path) -> Unit:
    from . import doctor

    inputs = site_inputs(site).files(book.dir).text("mdbook", tool_version(doctor.mdbook_path() or ""))
    return Unit("html", f"{book.slug}/{lang}", inputs.text("node", node_version()), [Path(out_dir)])


def _fonts() -> Inputs:
    return Inputs().files(paths.CACHE / "fonts", paths.CACHE / "fonts-fontsource")


def _pandoc_version() -> str:
    from . import pandoc

    try:
        return tool_version(pandoc.pandoc_path())
    except Exception:  # noqa: BLE001 - no pandoc: the build fails on its own
        return "missing"


def pdf_unit(site: config.Site, book: config.Book, lang: str, variant: str, out_file: Path) -> Unit:
    inputs = site_inputs(site).files(book.dir)
    inputs.parts += _fonts().parts
    inputs.text("pandoc", _pandoc_version()).text("node", node_version())
    return Unit("pdf", f"{book.slug}/{lang}/{variant}", inputs, [Path(out_file)])


def epub_unit(site: config.Site, book: config.Book, lang: str, out_file: Path) -> Unit:
    inputs = site_inputs(site).files(book.dir).text("pandoc", _pandoc_version()).text("node", node_version())
    return Unit("epub", f"{book.slug}/{lang}", inputs, [Path(out_file)])


def slides_unit(site: config.Site, book: config.Book, out_dir: Path) -> Unit:
    """A book's decks (HTML of every language and the PDFs, build/slides/<slug>/): the decks and the book's
    metadata, the slide theme and tools, the lock (cited GIDs), the site's base path, Node and Chromium."""
    from . import slides

    inputs = (Inputs()
              .files(book.dir / "book.toml", book.slides_dir, book.dir / "assets", paths.THEME / "slides",
                     paths.GENERATED, paths.I18N_THEME, paths.I18N_LOCAL, paths.TOOLS / "node",
                     paths.TOOLS / "tbook" / "slides.py", paths.LOCK_FILE, paths.SITE_TOML,
                     paths.ROOT / "package-lock.json")
              .text("base", slides.base_path(site))
              .text("base_url", site.base_url or "")
              .text("no_pdf", os.environ.get("TBOOK_SLIDES_NO_PDF") == "1")
              .text("node", node_version())
              .text("chromium", chromium_version()))
    return Unit("slides", book.slug, inputs, [Path(out_dir)])


def units(site: config.Site, books: Iterable[config.Book]) -> list[Unit]:
    """Every unit of ``books`` that ``./tbook build all`` builds, with its current key."""
    from . import build, film, slides

    out: list[Unit] = []
    for book in books:
        for ed in book.editions:
            if book.outputs_html:
                out.append(html_unit(site, book, ed.lang, build.html_dir(book.slug, ed.lang)))
            for variant in book.outputs_pdf:
                out.append(pdf_unit(site, book, ed.lang, variant,
                                    build.dist_dir(book.slug) / book.artifact(ed.lang, "pdf", variant)))
            if book.outputs_epub:
                out.append(epub_unit(site, book, ed.lang, build.dist_dir(book.slug) / book.artifact(ed.lang, "epub")))
        if slides.deck_names(book):
            out.append(slides_unit(site, book, build.slides_dir(book.slug)))
        out += getattr(film, "units", lambda s, b: [])(site, book)
    return out


# --------------------------------------------------------------------------- local store


def _rel_root(path: Path) -> str:
    rel = Path(path).resolve().relative_to(paths.ROOT.resolve())
    return rel.as_posix()


def _copy(src: Path, dst: Path) -> None:
    if dst.is_dir() and not dst.is_symlink():
        shutil.rmtree(dst)
    elif dst.exists() or dst.is_symlink():
        dst.unlink()
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        shutil.copytree(src, dst)
    else:
        shutil.copy2(src, dst)


def _listing(root: Path) -> dict[str, dict[str, Any]]:
    """{relative path: {sha256, size}} of every file under ``root``."""
    out = {}
    for f in sorted(p for p in root.rglob("*") if p.is_file()):
        out[f.relative_to(root).as_posix()] = {"sha256": file_digest(f), "size": f.stat().st_size}
    return out


def read_entry(entry: Path) -> dict[str, Any] | None:
    try:
        data = json.loads((entry / ENTRY).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if data.get("schema") == SCHEMA else None


def verify(entry: Path) -> str:
    """'' when ``entry`` holds exactly the files its entry.json lists, with those digests; else why not."""
    data = read_entry(entry)
    if data is None:
        return "no valid entry.json"
    files = entry / "files"
    want = data.get("files") or {}
    have = _listing(files) if files.is_dir() else {}
    if set(have) != set(want):
        return "the stored files are not the listed ones"
    for name, info in want.items():
        if have[name]["sha256"] != info.get("sha256"):
            return f"{name} does not match its digest"
    return ""


def store(unit: Unit, key: str | None = None) -> Path:
    """Copy ``unit``'s outputs into the store under ``key`` (default: its current key) and drop all but its
    newest :data:`KEEP` entries. Returns the entry directory."""
    key = key or unit.key
    final = unit.entry_dir(key)
    final.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix=".tmp-", dir=final.parent))
    try:
        outputs = []
        for i, out in enumerate(unit.outputs):
            out = Path(out)
            if not out.exists():
                raise FileNotFoundError(f"{unit.label}: the build did not write {paths.rel(out)}")
            _copy(out, tmp / "files" / str(i))
            outputs.append({"path": _rel_root(out), "kind": "dir" if out.is_dir() else "file"})
        (tmp / ENTRY).write_text(json.dumps({
            "schema": SCHEMA, "target": unit.target, "unit": unit.name, "key": key, "created": int(time.time()),
            "outputs": outputs, "files": _listing(tmp / "files"),
            "inputs": [list(p) for p in unit.inputs.parts],
        }, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        if final.exists():
            shutil.rmtree(final)
        tmp.rename(final)
    finally:
        if tmp.exists():
            shutil.rmtree(tmp, ignore_errors=True)
    os.utime(final)
    _keep_newest(final.parent, KEEP)
    return final


def _keep_newest(unit_dir: Path, keep: int) -> None:
    entries = sorted((d for d in unit_dir.iterdir() if d.is_dir() and not d.name.startswith(".")),
                     key=lambda d: d.stat().st_mtime, reverse=True)
    for old in entries[keep:]:
        shutil.rmtree(old, ignore_errors=True)


def restore_local(unit: Unit, key: str | None = None) -> bool:
    """Copy the stored outputs of ``unit`` (``key``: default its current key) to their places; False when
    the store has no valid entry (a damaged one is removed)."""
    entry = unit.entry_dir(key)
    if not entry.is_dir():
        return False
    why = verify(entry)
    data = read_entry(entry) or {}
    want = [_rel_root(Path(o)) for o in unit.outputs]
    if not why and [o.get("path") for o in data.get("outputs", [])] != want:
        why = "it was stored for other output paths"
    if why:
        _say(f"cache: dropping the stored {unit.label} ({why})")
        shutil.rmtree(entry, ignore_errors=True)
        return False
    for i, out in enumerate(unit.outputs):
        _copy(entry / "files" / str(i), Path(out))
    os.utime(entry)
    return True


# --------------------------------------------------------------------------- releases (remote)


def _token() -> str:
    return os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""


def _http(url: str, *, accept: str = "application/vnd.github+json", api: bool = True) -> bytes:
    headers = {"Accept": accept, "User-Agent": "tbook-build-cache"}
    if api and _token():
        headers["Authorization"] = f"Bearer {_token()}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=300) as resp:  # noqa: S310 - https URLs built below
        return resp.read()


def _asset_bytes(repo: str, asset: dict[str, Any]) -> bytes:
    """An asset's bytes: through the API (works for private repositories with a token), else its public URL."""
    if _token() and asset.get("url"):
        return _http(asset["url"], accept="application/octet-stream")
    return _http(asset["browser_download_url"], accept="application/octet-stream", api=False)


@lru_cache(maxsize=4)
def _remote_index(repo: str) -> dict[tuple[str, str, str], tuple[str, dict[str, Any], dict[str, Any]]]:
    """(target, unit, key) → (release tag, manifest entry, asset) over the newest published releases."""
    index: dict[tuple[str, str, str], tuple[str, dict[str, Any], dict[str, Any]]] = {}
    try:
        releases = json.loads(_http(f"https://api.github.com/repos/{repo}/releases?per_page=20"))
    except (urllib.error.URLError, OSError, ValueError) as exc:
        _say(f"cache: cannot list the releases of {repo} ({exc}); building instead")
        return index
    published = [r for r in releases if not r.get("draft")][:REMOTE_RELEASES]
    for rel in published:
        assets = {a.get("name"): a for a in rel.get("assets") or []}
        manifest_asset = assets.get(MANIFEST)
        if not manifest_asset:
            continue
        try:
            manifest = json.loads(_asset_bytes(repo, manifest_asset))
        except (urllib.error.URLError, OSError, ValueError) as exc:
            _say(f"cache: cannot read {MANIFEST} of release {rel.get('tag_name')} ({exc})")
            continue
        if manifest.get("schema") != SCHEMA:
            continue
        for e in manifest.get("entries") or []:
            asset = assets.get(e.get("asset"))
            k = (e.get("target"), e.get("unit"), e.get("key"))
            if asset and k not in index:
                index[k] = (rel.get("tag_name", ""), e, asset)
    return index


def _safe_extract(data: bytes, dest: Path) -> None:
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:") as tar:
        for m in tar.getmembers():
            name = Path(m.name)
            if name.is_absolute() or ".." in name.parts or not (m.isfile() or m.isdir()):
                raise ValueError(f"unsafe member {m.name!r}")
        tar.extractall(dest, filter="data")


def restore_remote(unit: Unit, repo: str) -> bool:
    """Fetch ``unit``'s entry for its current key from a release into the store and restore it."""
    key = unit.key
    found = _remote_index(repo).get((unit.target, unit.name, key)) if repo else None
    if not found:
        return False
    tag, entry_info, asset = found
    try:
        data = _asset_bytes(repo, asset)
    except (urllib.error.URLError, OSError) as exc:
        _say(f"cache: cannot download {asset.get('name')} from release {tag} ({exc}); building instead")
        return False
    digest = hashlib.sha256(data).hexdigest()
    reported = str(asset.get("digest") or "")
    if digest != entry_info.get("sha256") or (reported.startswith("sha256:") and reported[7:] != digest):
        _say(f"cache: {asset.get('name')} of release {tag} does not match its digest; building instead")
        return False
    final = unit.entry_dir(key)
    final.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix=".tmp-", dir=final.parent))
    try:
        _safe_extract(data, tmp)
        meta = read_entry(tmp) or {}
        why = verify(tmp)
        if why or (meta.get("target"), meta.get("unit"), meta.get("key")) != (unit.target, unit.name, key):
            _say(f"cache: {asset.get('name')} of release {tag} is not the entry it claims ({why or 'other unit'})")
            return False
        if final.exists():
            shutil.rmtree(final)
        tmp.rename(final)
    except (ValueError, tarfile.TarError, OSError) as exc:
        _say(f"cache: cannot unpack {asset.get('name')} of release {tag} ({exc})")
        return False
    finally:
        if tmp.exists():
            shutil.rmtree(tmp, ignore_errors=True)
    _say(f"cache: {unit.label} restored from release {tag}")
    return restore_local(unit, key)


# --------------------------------------------------------------------------- the build step


def run(unit: Unit, build: Callable[[], Any], *, repo: str | None = None) -> str:
    """Build ``unit`` with ``build()`` unless its key is cached. Returns 'cached' (local store), 'release'
    (restored from a release) or 'built'."""
    if not enabled():
        build()
        return "built"
    key = unit.key
    if restore_local(unit, key):
        _say(f"cache: {unit.label} is up to date ({key[:12]})")
        return "cached"
    if remote_enabled():
        if repo is None:
            repo = config.load_site().repo
        if repo and restore_remote(unit, repo):
            return "release"
    build()
    store(unit, key)
    return "built"


# --------------------------------------------------------------------------- whole store


def stored() -> list[tuple[str, str, str, Path]]:
    """(target, unit, key, entry dir) of every entry in the local store."""
    root = store_root()
    out = []
    if not root.is_dir():
        return out
    for entry_file in sorted(root.rglob(ENTRY)):
        entry = entry_file.parent
        data = read_entry(entry)
        if data and not any(part.startswith(".tmp-") for part in entry.relative_to(root).parts):
            out.append((data["target"], data["unit"], data["key"], entry))
    return out


def prune(current: Iterable[Unit]) -> list[Path]:
    """Remove every stored entry that is not the current key of one of ``current``. Returns what it removed."""
    keep = {(u.target, u.name, u.key) for u in current}
    removed = []
    for target, name, key, entry in stored():
        if (target, name, key) not in keep:
            shutil.rmtree(entry, ignore_errors=True)
            removed.append(entry)
    # empty unit directories left behind
    root = store_root()
    if root.is_dir():
        for d in sorted((p for p in root.rglob("*") if p.is_dir()), key=lambda p: len(p.parts), reverse=True):
            if not any(d.iterdir()):
                d.rmdir()
    return removed


def actions_key(prefix: str = "build-cache-v1") -> str:
    """The Actions cache key of the store's content: the same entries give the same key, so an unchanged
    store is not saved again."""
    h = hashlib.sha256()
    for target, name, key, _ in sorted(stored()):
        h.update(f"{target}\t{name}\t{key}\n".encode())
    return f"{prefix}-{h.hexdigest()}"


def asset_name(target: str, unit: str, key: str) -> str:
    return f"cache-{target}-{re.sub(r'[^A-Za-z0-9._-]+', '-', unit)}-{key[:16]}.tar"


def export(dest: Path, current: Iterable[Unit], *, repo: str = "") -> Path:
    """Write one tar per current unit found in the store, and :data:`MANIFEST` listing them, into ``dest``
    (for release.yml to attach). Units not in the store are left out (and named on stdout)."""
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    entries = []
    for unit in current:
        key = unit.key
        entry = unit.entry_dir(key)
        if not entry.is_dir() or verify(entry):
            print(f"cache export: {unit.label} is not in the store; build it first", flush=True)
            continue
        name = asset_name(unit.target, unit.name, key)
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:", format=tarfile.PAX_FORMAT) as tar:
            for f in sorted(entry.rglob("*")):
                info = tar.gettarinfo(str(f), arcname=f.relative_to(entry).as_posix())
                info.uid = info.gid = 0
                info.uname = info.gname = ""
                info.mtime = 0
                if f.is_file():
                    with f.open("rb") as fh:
                        tar.addfile(info, fh)
                else:
                    tar.addfile(info)
        data = buf.getvalue()
        (dest / name).write_bytes(data)
        entries.append({"target": unit.target, "unit": unit.name, "key": key, "asset": name,
                        "sha256": hashlib.sha256(data).hexdigest(), "size": len(data)})
    manifest = dest / MANIFEST
    manifest.write_text(json.dumps({"schema": SCHEMA, "repo": repo, "generated": int(time.time()),
                                    "entries": entries}, indent=1) + "\n", encoding="utf-8")
    return manifest
