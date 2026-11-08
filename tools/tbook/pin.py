"""``./tbook pin``: pin a trureturing commit and resolve every cited declaration.

``./tbook pin``            follow the branch in site.toml (default ``dev``) to its head
``./tbook pin <sha|ref>``  pin an explicit commit, branch or tag
``./tbook pin --refresh``  keep the current commit; add newly cited and prune unused GIDs

The lock records, per GID, the fully qualified Lean name, its kind, its module's frozen
``statement_id`` and (best effort) the source line and header. When the commit moves,
the report lists modules whose statement digest changed: re-read those theorems'
statements in trureturing and adjust the book text before merging.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import config, lean
from .model import load_book_models


@dataclass
class PinReport:
    commit: str
    previous: str
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    changed: list[tuple[str, str]] = field(default_factory=list)  # (gid, what)
    errors: list[str] = field(default_factory=list)
    written: bool = False

    def markdown(self) -> str:
        lines = [f"trureturing pin: `{self.previous[:12] or '—'}` → `{self.commit[:12]}`", ""]
        if self.errors:
            lines += ["**Unresolved (lock not written):**", ""] + [f"- {e}" for e in self.errors] + [""]
        for title, items in (("Added", self.added), ("Removed", self.removed)):
            if items:
                lines += [f"**{title}:**", ""] + [f"- `{g}`" for g in items] + [""]
        if self.changed:
            lines += ["**Changed — review the book text for these:**", ""]
            lines += [f"- `{g}`: {what}" for g, what in self.changed] + [""]
        if not (self.errors or self.added or self.removed or self.changed):
            lines.append("No declaration changes.")
        return "\n".join(lines)


def cited_gids(books: list[config.Book]) -> list[str]:
    gids: set[str] = set()
    for book in books:
        for model in load_book_models(book).values():
            for _, _, gid, _ in model.cited_gids():
                try:
                    lean.parse_gid(gid)
                except lean.LeanError:
                    continue
                gids.add(gid)
    return sorted(gids)


def pin(ref: str | None = None, *, refresh: bool = False, offline: bool = False,
        dry_run: bool = False) -> PinReport:
    site = config.load_site()
    old = lean.Lock.load()
    if refresh:
        if old is None:
            raise lean.LeanError("nothing to refresh: trureturing.lock.json does not exist; run ./tbook pin")
        commit = old.commit
    elif ref and lean.SHA_RE.match(ref):
        commit = ref
    else:
        if offline:
            raise lean.LeanError("--offline needs a full 40-hex commit or --refresh")
        commit = lean.ls_remote(site.trureturing_repo, ref or site.trureturing_branch)
    report = PinReport(commit=commit, previous=old.commit if old else "")
    ledger = lean.Ledger(site.trureturing_repo, offline=offline)
    resolved: dict[str, dict] = {}
    for gid in cited_gids(config.load_books()):
        try:
            res = lean.resolve(ledger, commit, gid)
        except lean.LeanError as exc:
            report.errors.append(str(exc))
            continue
        lean.locate(ledger, commit, res)
        resolved[gid] = res.to_lock()
    before = old.declarations if old else {}
    report.added = sorted(set(resolved) - set(before))
    report.removed = sorted(set(before) - set(resolved))
    for gid in sorted(set(resolved) & set(before)):
        a, b = before[gid], resolved[gid]
        diffs = []
        if a.get("name") != b.get("name"):
            diffs.append(f"name {a.get('name')} → {b.get('name')}")
        if a.get("kind") != b.get("kind"):
            diffs.append(f"kind {a.get('kind')} → {b.get('kind')}")
        if a.get("statement_id") != b.get("statement_id"):
            diffs.append("module statement digest changed")
        if diffs:
            report.changed.append((gid, "; ".join(diffs)))
    if report.errors or dry_run:
        return report
    lock = lean.Lock(repo=site.trureturing_repo, branch=site.trureturing_branch, commit=commit,
                     pinned_at=(old.pinned_at if old and refresh and old.commit == commit else lean.now_utc()),
                     declarations=resolved)
    lock.save()
    report.written = True
    return report
