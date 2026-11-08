"""Resolve Lean declarations against trureturing's frozen ledger at a pinned commit.

In trureturing, a module's declarations are kernel-verified and frozen exactly when
``Golden/Frozen/state/<module>.lean.json`` exists (CLAUDE.md §1.3, the freeze rule).
Each state file lists ``{statement_id, declarations: [{declaration_name_key, kind}]}``,
where a name key encodes a Lean ``Name`` with length-prefixed components::

    ns(ns(ns(ns(n0,2:D5),2:S1),7:Deficit),20:deficit_three_valued)  ==  D5.S1.Deficit.deficit_three_valued

Books cite declarations by GID, the same address trureturing's Blueprint uses:
``<module path>.<name>``, e.g. ``D5/S1/Deficit/DeficitThreeValued.deficit_three_valued``.
The name part is matched against the module's frozen declarations exactly or as a
dotted suffix; exactly one match is required (as in trureturing's LeanReferenceResolver).

State files are read from, in order: a local trureturing checkout (``$TRURETURING_DIR``
or ``../trureturing``) via ``git show <commit>:<path>``; the cache under
``.cache/trureturing/<commit>/``; ``raw.githubusercontent.com`` at the commit.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from . import paths

GID_RE = re.compile(
    r"^(?P<module>D[0-9]+/S[0-9]+/(?:[A-Za-z_][A-Za-z0-9_]*/)*[A-Za-z_][A-Za-z0-9_]*)"
    r"\.(?P<name>[A-Za-z_][A-Za-z0-9_']*(?:\.[A-Za-z_][A-Za-z0-9_']*)*)$"
)
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
STATE_DIR = "Golden/Frozen/state"
LOCK_SCHEMA = "trureturing-books.lock.v1"
FORMAL_KINDS = {"theorem"}
STD_AXIOMS = ("propext", "Classical.choice", "Quot.sound")


class LeanError(Exception):
    pass


# --------------------------------------------------------------------------- names


def parse_name_key(key: str) -> list[str | int]:
    """Decode a ``declaration_name_key`` into Lean name components."""

    def parse(i: int) -> tuple[list[str | int], int]:
        if key.startswith("n0", i):
            return [], i + 2
        tag = key[i:i + 3]
        if tag not in ("ns(", "nn("):
            raise LeanError(f"bad name key at {i}: {key[i:i + 20]!r}")
        parent, i = parse(i + 3)
        if i >= len(key) or key[i] != ",":
            raise LeanError(f"bad name key at {i}: expected ','")
        i += 1
        if tag == "ns(":
            colon = key.index(":", i)
            length = int(key[i:colon])
            start = colon + 1
            # trureturing writes component lengths in UTF-8 bytes (e.g. ``5:mk₂``).
            raw = key[start:].encode("utf-8")[:length]
            try:
                comp: str | int = raw.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise LeanError(f"bad name key at {start}: length splits a UTF-8 sequence") from exc
            i = start + len(comp)
        else:
            close = key.index(")", i)
            comp = int(key[i:close])
            i = close
        if i >= len(key) or key[i] != ")":
            raise LeanError(f"bad name key at {i}: expected ')'")
        return parent + [comp], i + 1

    comps, end = parse(0)
    if end != len(key):
        raise LeanError(f"trailing characters in name key: {key[end:]!r}")
    return comps


def name_to_str(comps: list[str | int]) -> str:
    out = []
    for c in comps:
        if isinstance(c, int):
            out.append(str(c))
        elif re.match(r"^[A-Za-z_][A-Za-z0-9_'!?]*$", c):
            out.append(c)
        else:
            out.append("«" + c + "»")
    return ".".join(out)


def is_private(comps: list[str | int]) -> bool:
    return "_private" in comps


@dataclass(frozen=True)
class Gid:
    module: str
    name: str

    @property
    def text(self) -> str:
        return f"{self.module}.{self.name}"

    @property
    def lean_module(self) -> str:
        return self.module.replace("/", ".")

    @property
    def state_path(self) -> str:
        return f"{STATE_DIR}/{self.module}.lean.json"

    @property
    def source_path(self) -> str:
        return f"{self.module}.lean"

    @property
    def blueprint_path(self) -> str:
        return f"Blueprint/{self.module}.md"


def parse_gid(text: str) -> Gid:
    m = GID_RE.match(text.strip())
    if not m:
        raise LeanError(
            f"not a declaration GID: {text!r} (expected <module path>.<name>, "
            "e.g. D5/S1/Deficit/DeficitThreeValued.deficit_three_valued)"
        )
    return Gid(m.group("module"), m.group("name"))


def split_gids(value: str) -> list[str]:
    return [p for p in re.split(r"[\s,]+", value.strip()) if p]


# --------------------------------------------------------------------------- sources


class Source:
    label = "source"

    def read(self, commit: str, path: str) -> bytes | None:  # pragma: no cover - interface
        raise NotImplementedError


class GitSource(Source):
    def __init__(self, repo_dir: Path):
        self.dir = repo_dir
        self.label = f"git checkout {repo_dir}"
        self._has: dict[str, bool] = {}

    def has_commit(self, commit: str) -> bool:
        if commit not in self._has:
            r = subprocess.run(["git", "-C", str(self.dir), "cat-file", "-e", f"{commit}^{{commit}}"],
                               capture_output=True)
            self._has[commit] = r.returncode == 0
        return self._has[commit]

    def read(self, commit: str, path: str) -> bytes | None:
        if not self.has_commit(commit):
            return None
        r = subprocess.run(["git", "-C", str(self.dir), "show", f"{commit}:{path}"], capture_output=True)
        return r.stdout if r.returncode == 0 else b""  # b"" = definitely absent at this commit


class CacheSource(Source):
    def __init__(self, cache_dir: Path):
        self.dir = cache_dir
        self.label = f"cache {cache_dir}"

    def _file(self, commit: str, path: str) -> Path:
        return self.dir / commit / path

    def read(self, commit: str, path: str) -> bytes | None:
        f = self._file(commit, path)
        if f.exists():
            return f.read_bytes()
        missing = self._file(commit, path + ".missing")
        return b"" if missing.exists() else None

    def store(self, commit: str, path: str, data: bytes) -> None:
        f = self._file(commit, path if data else path + ".missing")
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(data)


class HttpSource(Source):
    def __init__(self, repo: str, timeout: float = 30.0):
        self.repo = repo
        self.timeout = timeout
        self.label = f"https://raw.githubusercontent.com/{repo}"

    def read(self, commit: str, path: str) -> bytes | None:
        url = f"https://raw.githubusercontent.com/{self.repo}/{commit}/{path}"
        req = urllib.request.Request(url, headers={"User-Agent": "tbook"})
        token = os.environ.get("TRURETURING_TOKEN")
        if token:
            req.add_header("Authorization", f"token {token}")
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    return resp.read()
            except urllib.error.HTTPError as exc:
                if exc.code == 404:
                    return b""
                if attempt == 2:
                    raise LeanError(f"GET {url}: HTTP {exc.code}") from exc
            except (urllib.error.URLError, TimeoutError) as exc:
                if attempt == 2:
                    raise LeanError(f"GET {url}: {exc}") from exc
        return None


class Ledger:
    """Reads frozen state (and Lean sources) of trureturing at a commit."""

    def __init__(self, repo: str, *, offline: bool = False, checkout: Path | None = None):
        self.repo = repo
        self.cache = CacheSource(paths.CACHE / "trureturing")
        self.sources: list[Source] = []
        for cand in [checkout, os.environ.get("TRURETURING_DIR"), paths.ROOT.parent / "trureturing"]:
            if cand and (Path(cand) / ".git").exists():
                self.sources.append(GitSource(Path(cand)))
                break
        self.sources.append(self.cache)
        if not offline:
            self.http = HttpSource(repo)
            self.sources.append(self.http)
        self._json: dict[tuple[str, str], dict | None] = {}

    def read(self, commit: str, path: str) -> bytes | None:
        """File bytes at the commit; b"" if absent there; None if no source could tell."""
        for src in self.sources:
            data = src.read(commit, path)
            if data is None:
                continue
            if isinstance(src, HttpSource):
                self.cache.store(commit, path, data)
            return data
        return None

    def state(self, commit: str, module: str) -> dict | None:
        key = (commit, module)
        if key not in self._json:
            data = self.read(commit, f"{STATE_DIR}/{module}.lean.json")
            if data is None:
                raise LeanError(
                    f"cannot read {STATE_DIR}/{module}.lean.json at {commit[:12]}: no trureturing checkout, "
                    "no cache entry and network disabled"
                )
            self._json[key] = json.loads(data) if data else None
        return self._json[key]


# --------------------------------------------------------------------------- resolution


@dataclass
class Resolution:
    gid: str
    module: str
    name: str  # fully qualified Lean name
    kind: str  # theorem | def | inductive | constructor | recursor | opaque
    statement_id: str  # module statement digest from the state file
    line: int = 0  # line of the declaration in the .lean source (0 = unknown)
    signature: str = ""  # declaration header up to ':=' (best effort, informational)

    def to_lock(self) -> dict:
        d = asdict(self)
        d.pop("gid")
        return d


def resolve(ledger: Ledger, commit: str, gid_text: str) -> Resolution:
    gid = parse_gid(gid_text)
    state = ledger.state(commit, gid.module)
    if state is None:
        raise LeanError(
            f"{gid.text}: module {gid.module} is not frozen at {commit[:12]} "
            f"(no {gid.state_path}); only kernel-verified, frozen declarations may be cited"
        )
    matches: list[tuple[str, str]] = []
    for decl in state.get("declarations", []):
        comps = parse_name_key(decl["declaration_name_key"])
        if is_private(comps):
            continue
        full = name_to_str(comps)
        if full == gid.name or full.endswith("." + gid.name):
            matches.append((full, decl.get("kind", "")))
    if not matches:
        raise LeanError(f"{gid.text}: no frozen declaration named {gid.name!r} in {gid.state_path} at {commit[:12]}")
    if len(matches) > 1:
        names = ", ".join(m[0] for m in matches)
        raise LeanError(f"{gid.text}: ambiguous, matches {names}; write a longer name suffix")
    full, kind = matches[0]
    return Resolution(gid=gid.text, module=gid.module, name=full, kind=kind,
                      statement_id=str(state.get("statement_id", "")))


DECL_KEYWORDS = r"(?:theorem|lemma|def|abbrev|instance|structure|inductive|class|opaque|axiom)"


def locate(ledger: Ledger, commit: str, res: Resolution) -> None:
    """Fill ``line`` and ``signature`` from the Lean source (best effort)."""
    try:
        data = ledger.read(commit, f"{res.module}.lean")
    except LeanError:
        return
    if not data:
        return
    text = data.decode("utf-8", "replace")
    short = res.name.rsplit(".", 1)[-1]
    pat = re.compile(r"^(?:@\[[^\]]*\]\s*)?(?:(?:private|protected|noncomputable|nonrec|partial|unsafe)\s+)*"
                     + DECL_KEYWORDS + r"\s+(?:[\w.']*\.)?" + re.escape(short) + r"(?![\w'])", re.M)
    m = pat.search(text)
    if not m:
        return
    res.line = text.count("\n", 0, m.start()) + 1
    end = text.find(":=", m.start())
    if end < 0 or end - m.start() > 2000:
        end = min(len(text), m.start() + 400)
    sig = re.sub(r"\s+", " ", text[m.start():end]).strip()
    res.signature = sig[:600]


# --------------------------------------------------------------------------- lock file


@dataclass
class Lock:
    repo: str
    branch: str
    commit: str
    pinned_at: str = ""
    declarations: dict[str, dict] = field(default_factory=dict)
    schema: str = LOCK_SCHEMA

    @classmethod
    def load(cls, path: Path | None = None) -> "Lock | None":
        path = path or paths.LOCK_FILE
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("schema") != LOCK_SCHEMA:
            raise LeanError(f"{paths.rel(path)}: unsupported schema {data.get('schema')!r}")
        if not SHA_RE.match(data.get("commit", "")):
            raise LeanError(f"{paths.rel(path)}: commit must be a full 40-hex SHA")
        return cls(repo=data["repo"], branch=data.get("branch", ""), commit=data["commit"],
                   pinned_at=data.get("pinned_at", ""), declarations=data.get("declarations", {}))

    def save(self, path: Path | None = None) -> None:
        path = path or paths.LOCK_FILE
        data = {
            "schema": self.schema,
            "repo": self.repo,
            "branch": self.branch,
            "commit": self.commit,
            "pinned_at": self.pinned_at,
            "declarations": {k: self.declarations[k] for k in sorted(self.declarations)},
        }
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def get(self, gid: str) -> Resolution | None:
        d = self.declarations.get(gid)
        if not d:
            return None
        return Resolution(gid=gid, module=d["module"], name=d["name"], kind=d["kind"],
                          statement_id=d.get("statement_id", ""), line=int(d.get("line", 0) or 0),
                          signature=d.get("signature", ""))

    # Links ------------------------------------------------------------------
    def blob(self, path: str, line: int = 0) -> str:
        url = f"https://github.com/{self.repo}/blob/{self.commit}/{path}"
        return url + (f"#L{line}" if line else "")

    def source_url(self, gid: str) -> str:
        res = self.get(gid)
        g = parse_gid(gid)
        return self.blob(g.source_path, res.line if res else 0)

    def state_url(self, gid: str) -> str:
        return self.blob(parse_gid(gid).state_path)

    def blueprint_url(self, gid: str) -> str:
        return self.blob(parse_gid(gid).blueprint_path)

    @property
    def tree_url(self) -> str:
        return f"https://github.com/{self.repo}/tree/{self.commit}"


def ls_remote(repo: str, ref: str) -> str:
    """Resolve a branch/tag name of the trureturing repository to a commit SHA."""
    if SHA_RE.match(ref):
        return ref
    url = f"https://github.com/{repo}.git"
    for candidate in (f"refs/heads/{ref}", f"refs/tags/{ref}", ref):
        r = subprocess.run(["git", "ls-remote", "--exit-code", url, candidate], capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.split()[0]
    raise LeanError(f"cannot resolve {ref!r} in {url}")


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
