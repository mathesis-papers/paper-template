"""``./tbook check``: structure, bilingual parity and the Lean verification rule.

The rule this enforces: every theorem / lemma / proposition / corollary cites at least
one Lean declaration (``lean="<GID>"``) that is recorded in ``trureturing.lock.json`` and
that, at the pinned commit, is listed in trureturing's ``Golden/Frozen/state`` with kind
``theorem`` — i.e. kernel-verified and frozen. Conjectures and open problems must not
cite Lean. Editions of a book (zh, en, …) must agree item by item.
"""

from __future__ import annotations

import importlib
from pathlib import Path

from . import config, lean, mdscan, paths
from .model import (DEFINITION, FORMAL, MEDIA, NUMBERED, OPEN, PROOF, EditionModel, Issue, load_book_models,
                    media_cited_gids)


def _err(issues: list[Issue], path: Path | None, line: int, msg: str) -> None:
    issues.append(Issue("error", path, line, msg))


def _warn(issues: list[Issue], path: Path | None, line: int, msg: str) -> None:
    issues.append(Issue("warning", path, line, msg))


def check_env_policy(model: EditionModel, issues: list[Issue]) -> None:
    for ch in model.chapters:
        for env in ch.envs + ch.media:
            where = (ch.path, env.line)
            if env.id and not mdscan.ID_RE.match(env.id):
                _err(issues, *where, f"#{env.id}: ids use letters, digits, '-', '_' or ':' and start with a letter")
            if env.kind in FORMAL + DEFINITION + OPEN and not env.id:
                _err(issues, *where, f"{env.kind} needs an id, e.g. {{.{env.kind} #{env.kind[:3]}-name}}")
            if env.kind in FORMAL and not env.lean:
                _err(issues, *where,
                     f"{env.kind} #{env.id or '?'} cites no Lean declaration. Every {env.kind} must be "
                     "kernel-verified in trureturing: add lean=\"<module path>.<name>\". If it is not proved yet, "
                     "write it as a conjecture or problem instead.")
            if env.kind in OPEN and env.lean:
                _err(issues, *where, f"{env.kind} #{env.id}: open items must not cite Lean; if it is proved, make it a theorem")
            for gid in env.lean:
                try:
                    lean.parse_gid(gid)
                except lean.LeanError as exc:
                    _err(issues, *where, str(exc))
            if env.kind in MEDIA:
                if not env.attrs.get("src"):
                    _err(issues, *where, f"{env.kind} embed needs src=\"…\"")
                    continue
                try:
                    mod = importlib.import_module(f"tbook.{env.kind}")
                    problem = mod.check_ref(model.edition.book, env.attrs.get("src"))
                except Exception as exc:  # noqa: BLE001 - surface any media checker failure
                    problem = f"cannot check {env.kind} src: {exc}"
                if problem:
                    _err(issues, *where, problem)
            if env.title and "\n" in env.title:
                _err(issues, *where, "title must be one line")
        for line, ref in ch.refs:
            if ref not in model.envs:
                _err(issues, ch.path, line, f"[@{ref}] refers to no environment in this edition")
            elif model.envs[ref].kind in MEDIA:
                _err(issues, ch.path, line,
                     f"[@{ref}] points at a {model.envs[ref].kind} embed; references can only target "
                     "numbered environments (theorem, definition, example …)")
        for line, gid in ch.lean_links:
            try:
                lean.parse_gid(gid)
            except lean.LeanError as exc:
                _err(issues, ch.path, line, str(exc))


def check_orphans(model: EditionModel, issues: list[Issue]) -> None:
    ed = model.edition
    if not ed.dir.exists() or model.summary is None:
        return
    listed = {(ed.dir / f).resolve() for f in model.summary.files()}
    for md in sorted(ed.dir.rglob("*.md")):
        if md.name == "SUMMARY.md" or md.resolve() in listed:
            continue
        _warn(issues, md, 0, "not listed in SUMMARY.md (it will not be published)")


def _env_signature(model: EditionModel) -> list[tuple[str, list[tuple[str, str, tuple[str, ...]]]]]:
    sig = []
    for ch in model.chapters:
        items = [(e.kind, e.id, tuple(e.lean)) for e in ch.envs if e.kind in NUMBERED + PROOF]
        items += [(e.kind, e.attrs.get("src"), ()) for e in ch.media]
        sig.append((ch.chapter.path or "", items))
    return sig


def check_parity(book: config.Book, models: dict[str, EditionModel], issues: list[Issue]) -> None:
    if len(models) < 2:
        return
    primary = models[book.languages[0]]
    if primary.summary is None:
        return
    p_files = primary.summary.files()
    p_sig = _env_signature(primary)
    for lang in book.languages[1:]:
        other = models[lang]
        if other.summary is None:
            continue
        o_files = other.summary.files()
        if p_files != o_files:
            missing = [f for f in p_files if f not in o_files]
            extra = [f for f in o_files if f not in p_files]
            detail = []
            if missing:
                detail.append("missing " + ", ".join(missing))
            if extra:
                detail.append("extra " + ", ".join(extra))
            if not detail:
                detail.append("same files in a different order")
            _err(issues, other.summary.path, 0,
                 f"{lang} edition chapters differ from the {book.languages[0]} edition ({'; '.join(detail)}). "
                 "Editions use the same file names in the same order.")
            continue
        o_sig = dict(_env_signature(other))
        for path, items in p_sig:
            o_items = o_sig.get(path, [])
            if items == o_items:
                continue
            ch_path = other.edition.dir / path
            for k in range(max(len(items), len(o_items))):
                a = items[k] if k < len(items) else None
                b = o_items[k] if k < len(o_items) else None
                if a != b:
                    def fmt(x):
                        if x is None:
                            return "nothing"
                        return f"{x[0]} #{x[1]}" + (f" lean={' '.join(x[2])}" if x[2] else "")
                    _err(issues, ch_path, 0,
                         f"item {k + 1} differs between editions: {book.languages[0]} has {fmt(a)}, {lang} has {fmt(b)}")
                    break


def check_lean(models_by_book: dict[str, dict[str, EditionModel]], lock: lean.Lock | None,
               site: config.Site, issues: list[Issue], *, offline: bool,
               extra_cited: list[tuple[Path, int, str]] | None = None) -> None:
    """Re-verify every cited GID against the lock and the frozen state at the pinned commit.

    ``extra_cited`` holds citations outside the chapters (visualizations, films, slides); they are
    verified the same way but do not impose the theorem-kind rule (their modules check that).
    """
    cited: dict[str, list[tuple[Path, int, bool]]] = {}
    for path, line, gid in extra_cited or []:
        try:
            lean.parse_gid(gid)
        except lean.LeanError:
            continue  # reported by the media module's own check
        cited.setdefault(gid, []).append((path, line, False))
    for models in models_by_book.values():
        for model in models.values():
            for path, line, gid, env in model.cited_gids():
                try:
                    lean.parse_gid(gid)
                except lean.LeanError:
                    continue  # reported by the policy check
                cited.setdefault(gid, []).append((path, line, bool(env and env.kind in FORMAL)))
    if not cited:
        return
    if lock is None:
        _err(issues, paths.LOCK_FILE, 0, "trureturing.lock.json is missing; run ./tbook pin")
        return
    if lock.repo != site.trureturing_repo:
        _err(issues, paths.LOCK_FILE, 0,
             f"lock pins {lock.repo} but site.toml uses {site.trureturing_repo}; run ./tbook pin")
    ledger = lean.Ledger(lock.repo, offline=offline)
    for gid, uses in sorted(cited.items()):
        path, line, _ = uses[0]
        res = lock.get(gid)
        if res is None:
            _err(issues, path, line, f"{gid} is not in trureturing.lock.json; run ./tbook pin --refresh")
            continue
        if any(formal for _, _, formal in uses) and res.kind not in lean.FORMAL_KINDS:
            _err(issues, path, line, f"{gid} is a Lean {res.kind}, but theorem-like environments must cite theorems")
        try:
            live = lean.resolve(ledger, lock.commit, gid)
        except lean.LeanError as exc:
            if offline and "network disabled" in str(exc):
                _warn(issues, path, line, f"{gid}: not re-verified offline ({exc})")
            else:
                _err(issues, path, line, str(exc))
            continue
        for fld in ("name", "kind", "module", "statement_id"):
            if getattr(live, fld) != getattr(res, fld):
                _err(issues, paths.LOCK_FILE, 0,
                     f"{gid}: lock says {fld}={getattr(res, fld)!r} but trureturing@{lock.commit[:12]} says "
                     f"{getattr(live, fld)!r}; run ./tbook pin --refresh")
                break
    for gid in sorted(set(lock.declarations) - set(cited)):
        _warn(issues, paths.LOCK_FILE, 0, f"{gid} is locked but no longer cited; ./tbook pin --refresh prunes it")


def check_theme(issues: list[Issue]) -> None:
    from . import theme

    for path in theme.stale_outputs():
        _err(issues, path, 0, "generated from theme/tokens.json but out of date; run ./tbook theme")


def run(books: list[config.Book], *, offline: bool = False) -> list[Issue]:
    site = config.load_site()
    issues: list[Issue] = []
    for lang in site.languages:
        if not config.has_i18n(lang):
            _err(issues, paths.SITE_TOML, 0, f"no i18n table for {lang!r}: add i18n/{lang}.toml (copy theme/i18n/en.toml)")
    try:
        lock = lean.Lock.load()
    except (lean.LeanError, ValueError, KeyError) as exc:
        _err(issues, paths.LOCK_FILE, 0, f"unreadable lock: {exc}")
        lock = None
    models_by_book: dict[str, dict[str, EditionModel]] = {}
    for book in books:
        for lang in book.languages:
            if not config.has_i18n(lang):
                _err(issues, book.dir / "book.toml", 0,
                     f"edition {lang!r} has no i18n table: add i18n/{lang}.toml (copy theme/i18n/en.toml)")
            if lang not in site.languages:
                _warn(issues, book.dir / "book.toml", 0, f"edition {lang!r} is not in site.toml languages")
        models = load_book_models(book)
        models_by_book[book.slug] = models
        for model in models.values():
            issues.extend(model.issues)
            check_env_policy(model, issues)
            check_orphans(model, issues)
            if model.summary is not None and not model.chapters:
                _warn(issues, model.edition.summary, 0, "edition has no chapters yet")
        check_parity(book, models, issues)
        for kind in MEDIA:
            try:
                mod = importlib.import_module(f"tbook.{kind}")
                issues.extend(mod.check(book))
            except NotImplementedError:
                pass
    extra = [c for book in books for c in media_cited_gids(book)]
    check_lean(models_by_book, lock, site, issues, offline=offline, extra_cited=extra)
    check_theme(issues)
    return issues
