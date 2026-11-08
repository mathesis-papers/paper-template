"""The generated "verification ledger" chapter appended to every edition.

It lists each formal environment with its Lean declaration(s), each linked at the
pinned commit, followed by the explicitly open items. The output is plain Markdown
(pipe tables), rendered by every target.
"""

from __future__ import annotations

from typing import Callable

from . import config, lean
from .model import FORMAL, OPEN, EditionModel, Env

LEDGER_FILE = "verification-ledger.md"
LEDGER_ID = "tr-verification-ledger"


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def ledger_markdown(model: EditionModel, lock: lean.Lock | None,
                    href: Callable[[Env], str] | None = None) -> str:
    """``href(env)`` links an item to its environment (default ``#id``, right for Pandoc)."""
    href = href or (lambda env: "#" + env.id)
    lang = model.lang
    s = lambda key: config.s(lang, key)  # noqa: E731
    out = [f"# {s('ledger.title')} {{#{LEDGER_ID} .unnumbered}}", "", s("ledger.intro"), ""]
    if lock:
        out += [f"{s('ui.pinned_at')} [`{lock.commit[:12]}`]({lock.tree_url}) · `{lock.repo}`", ""]
    formal = [e for e in model.all_envs() if e.kind in FORMAL]
    if formal:
        out += [f"| {s('ledger.col_item')} | {s('ledger.col_title')} | {s('ledger.col_decl')} | {s('ledger.col_state')} |",
                "| --- | --- | --- | --- |"]
        for env in formal:
            decls = []
            states = []
            for gid in env.lean:
                res = lock.get(gid) if lock else None
                name = res.name if res else gid
                url = lock.source_url(gid) if lock else ""
                decls.append(f"[`{_cell(name)}`]({url})" if url else f"`{_cell(name)}`")
                if lock:
                    sid = (res.statement_id.split(":", 1)[-1][:10] if res and res.statement_id else "state")
                    states.append(f"[`{sid}`]({lock.state_url(gid)})")
            item = f"[{env.ref_text(lang)}]({href(env)})" if env.id else env.ref_text(lang)
            out.append(f"| {item} | {_cell(env.title) or '—'} | {' · '.join(decls)} | {' '.join(states) or '—'} |")
        out.append("")
    else:
        out += [s("ledger.none"), ""]
    open_items = [e for e in model.all_envs() if e.kind in OPEN]
    out += [f"## {s('ledger.open_title')} {{.unnumbered}}", "", s("ledger.open_intro"), ""]
    if open_items:
        for env in open_items:
            title = f" — {env.title}" if env.title else ""
            out.append(f"- [{env.ref_text(lang)}]({href(env)}){title}")
    else:
        out.append(s("ledger.none"))
    out.append("")
    return "\n".join(out)
