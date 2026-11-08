"""Target-independent chapter transformation shared by the mdBook and Pandoc pipelines.

Given an :class:`~tbook.model.EditionModel`, :func:`chapter_markdown` rewrites a
chapter's Markdown for one target:

* ``[@id]`` → ``[定理 2.1](href)`` (``href`` from :attr:`RenderContext.env_href`);
* ``[text](lean:GID)`` → a permalink to the declaration's Lean source at the pinned commit;
* links/images that point into the book directory outside the edition (``../assets/x.svg``)
  → paths into the staged copy ``_book/…`` (files collected in ``ctx.book_files``);
* environment divs → target markup (HTML ``<section>`` for mdBook; an enriched fenced div
  for Pandoc, which ``tools/filters/tr-env.lua`` renders to Typst or EPUB XHTML);
* media divs (``viz``/``film``/``slides``) → whatever ``tbook.<kind>.render_embed`` returns.

Every renderer uses :func:`env_view`, so numbering, labels, badges and Lean links agree
across HTML, PDF and EPUB.
"""

from __future__ import annotations

import html
import importlib
import posixpath
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from . import config, lean, mdscan
from .model import FORMAL, MEDIA, ChapterDoc, EditionModel, Env

LINK_RE = re.compile(r"(?P<bang>!?)\[(?P<text>(?:`[^`]*`|\\.|[^\]\\])*)\]\((?P<url>[^)\s]+)(?P<title>\s+\"[^\"]*\")?\)")
EXTERNAL_RE = re.compile(r"^(?:[a-z][a-z0-9+.-]*:|#|/)", re.I)


@dataclass
class RenderContext:
    site: config.Site
    book: config.Book
    edition: config.Edition
    model: EditionModel
    lock: lean.Lock | None
    target: str  # "mdbook" | "pandoc"
    # href to an environment from a chapter (mdBook needs relative chapter paths).
    env_href: Callable[[Env, ChapterDoc], str] | None = None
    # where the staged edition puts files from the book directory (relative to the edition root)
    book_prefix: str = "_book"
    book_files: set[Path] = field(default_factory=set)
    issues: list[str] = field(default_factory=list)

    @property
    def lang(self) -> str:
        return self.edition.lang

    def href(self, env: Env, frm: ChapterDoc) -> str:
        if self.env_href:
            return self.env_href(env, frm)
        return "#" + env.id


def mdbook_env_href(model: EditionModel) -> Callable[[Env, ChapterDoc], str]:
    def href(env: Env, frm: ChapterDoc) -> str:
        target = model.chapter_of(env.id)
        if target is None or target is frm:
            return "#" + env.id
        rel = posixpath.relpath(target.chapter.path, posixpath.dirname(frm.chapter.path) or ".")
        return f"{rel}#{env.id}"

    return href


# --------------------------------------------------------------------------- data views


def lean_view(gid: str, lock: lean.Lock | None) -> dict:
    view = {"gid": gid, "name": "", "kind": "", "url": "", "state_url": "", "blueprint_url": "",
            "line": 0, "signature": "", "statement_id": ""}
    try:
        g = lean.parse_gid(gid)
    except lean.LeanError:
        return view
    view["name"] = g.lean_module + "." + g.name if not g.name.startswith(g.lean_module) else g.name
    if lock:
        res = lock.get(gid)
        if res:
            view.update(name=res.name, kind=res.kind, line=res.line, signature=res.signature,
                        statement_id=res.statement_id)
        view["url"] = lock.source_url(gid)
        view["state_url"] = lock.state_url(gid)
        view["blueprint_url"] = lock.blueprint_url(gid)
    return view


def env_view(env: Env, ctx: RenderContext) -> dict:
    lang = ctx.lang
    badge = ""
    badge_title = ""
    if env.kind in FORMAL:
        badge, badge_title = config.s(lang, "badge.lean"), config.s(lang, "badge.lean_title")
    elif env.status == "open":
        badge, badge_title = config.s(lang, "badge.open"), config.s(lang, "badge.open_title")
    return {
        "kind": env.kind,
        "id": env.id,
        "number": env.number,
        "label": env.label(lang),
        "ref_text": env.ref_text(lang),
        "heading": env.heading(lang),
        "title": env.title,
        "status": env.status,
        "badge": badge,
        "badge_title": badge_title,
        "lean": [lean_view(g, ctx.lock) for g in env.lean],
        "attrs": dict(env.attrs.kv),
    }


# --------------------------------------------------------------------------- inline


def _rewrite_links(line: str, doc: ChapterDoc, ctx: RenderContext) -> str:
    book_dir = ctx.book.dir.resolve()
    edition_dir = ctx.edition.dir.resolve()
    chapter_dir = doc.path.parent.resolve()

    def repl(m: re.Match) -> str:
        url = m.group("url")
        if url.startswith("lean:"):
            gid = url[5:]
            target = lean_view(gid, ctx.lock)["url"] or url
            return f"{m.group('bang')}[{m.group('text')}]({target}{m.group('title') or ''})"
        if EXTERNAL_RE.match(url):
            return m.group(0)
        path_part, _, frag = url.partition("#")
        if not path_part:
            return m.group(0)
        target = (chapter_dir / path_part).resolve()
        try:
            target.relative_to(edition_dir)
            return m.group(0)  # inside the edition: staged as is
        except ValueError:
            pass
        try:
            inside_book = target.relative_to(book_dir)
        except ValueError:
            ctx.issues.append(f"{doc.path}: link leaves the book directory: {url}")
            return m.group(0)
        ctx.book_files.add(target)
        staged_chapter_dir = posixpath.dirname(doc.chapter.path) or "."
        new = posixpath.relpath(posixpath.join(ctx.book_prefix, inside_book.as_posix()), staged_chapter_dir)
        if frag:
            new += "#" + frag
        return f"{m.group('bang')}[{m.group('text')}]({new}{m.group('title') or ''})"

    return mdscan.sub_outside_code(LINK_RE, repl, line)


def _rewrite_refs(line: str, doc: ChapterDoc, ctx: RenderContext) -> str:
    def repl(m: re.Match) -> str:
        env = ctx.model.envs.get(m.group("id"))
        if env is None:
            ctx.issues.append(f"{doc.path}: unknown reference [@{m.group('id')}]")
            return f"**[@{m.group('id')}?]**"
        return f"[{env.ref_text(ctx.lang)}]({ctx.href(env, doc)})"

    return mdscan.sub_outside_code(mdscan.REF_RE, repl, line)


def transform_line(line: str, doc: ChapterDoc, ctx: RenderContext) -> str:
    return _rewrite_refs(_rewrite_links(line, doc, ctx), doc, ctx)


# --------------------------------------------------------------------------- environments


def esc(text: str) -> str:
    return html.escape(text, quote=True)


def mdbook_env(env: Env, view: dict, inner: str) -> str:
    """HTML wrapper understood by theme/mdbook/tr-book.css (blank lines keep Markdown inside)."""
    classes = f"tr-env tr-{env.kind} tr-status-{env.status}"
    head = [f'<span class="tr-env-label">{esc(view["ref_text"])}</span>']
    if env.kind == "proof":
        head = [f'<span class="tr-env-label">{esc(view["label"])}</span>']
    if view["title"]:
        open_p = config.s(env_lang(view), "punct.title_open")
        head.append(f'<span class="tr-env-title">{esc(open_p)}{esc(view["title"])}'
                    f'{esc(config.s(env_lang(view), "punct.title_close"))}</span>')
    if view["badge"]:
        first = view["lean"][0]["url"] if view["lean"] else ""
        cls = "tr-badge-lean" if view["status"] == "lean" else "tr-badge-open"
        if first:
            head.append(f'<a class="tr-badge {cls}" href="{esc(first)}" title="{esc(view["badge_title"])}">{esc(view["badge"])}</a>')
        else:
            head.append(f'<span class="tr-badge {cls}" title="{esc(view["badge_title"])}">{esc(view["badge"])}</span>')
    parts = [f'<section class="{classes}" id="{esc(env.id)}" data-kind="{env.kind}">' if env.id
             else f'<section class="{classes}" data-kind="{env.kind}">',
             f'<header class="tr-env-head">{"".join(head)}</header>', "", inner.strip("\n"), ""]
    if view["lean"]:
        links = []
        for lv in view["lean"]:
            name = esc(lv["name"] or lv["gid"])
            if lv["url"]:
                links.append(f'<a class="tr-lean-decl" href="{esc(lv["url"])}" title="{esc(lv["gid"])}"><code>{name}</code></a>')
            else:
                links.append(f'<code class="tr-lean-decl">{name}</code>')
        parts.append(f'<footer class="tr-env-lean">{" ".join(links)}</footer>')
    if env.kind == "proof":
        parts.append('<span class="tr-qed" aria-hidden="true">∎</span>')
    parts.append("</section>")
    return "\n".join(parts)


def env_lang(view: dict) -> str:
    return view.get("_lang", "en")


def pandoc_env(env: Env, view: dict, inner: str) -> str:
    """Fenced div with ``tr-*`` attributes; tools/filters/tr-env.lua renders it per format."""
    attrs = mdscan.Attrs(id=env.id, classes=["tr-env", env.kind])
    kv = attrs.kv
    kv["tr-kind"] = env.kind
    kv["tr-status"] = view["status"]
    kv["tr-label"] = view["label"]
    kv["tr-number"] = view["number"]
    kv["tr-ref"] = view["ref_text"]
    if view["title"]:
        kv["tr-title"] = view["title"]
    if view["badge"]:
        kv["tr-badge"] = view["badge"]
    if view["lean"]:
        kv["tr-lean"] = " ".join(lv["gid"] for lv in view["lean"])
        kv["tr-lean-name"] = " ".join(lv["name"] or lv["gid"] for lv in view["lean"])
        kv["tr-lean-url"] = " ".join(lv["url"] or "-" for lv in view["lean"])
    fence = ":" * 6
    return f"{fence} {attrs.to_pandoc()}\n{inner.strip(chr(10))}\n{fence}"


def render_media(env: Env, ctx: RenderContext, inner: str, doc: ChapterDoc) -> str:
    """Delegate to ``tbook.viz`` / ``tbook.film`` / ``tbook.slides`` ``render_embed``."""
    mod = importlib.import_module(f"tbook.{env.kind}")
    return mod.render_embed(env, ctx, inner, doc)


def chapter_markdown(doc: ChapterDoc, ctx: RenderContext) -> str:
    """The chapter's Markdown, transformed for ``ctx.target``."""
    envs_by_div = {id(e.div): e for e in doc.envs + doc.media if e.div is not None}

    def text_fn(node: mdscan.Text) -> str:
        return "\n".join(transform_line(line, doc, ctx) for line in node.lines)

    def div_fn(div: mdscan.Div, inner: str) -> str:
        env = envs_by_div.get(id(div))
        if env is None:
            if ctx.target == "mdbook":
                cls = " ".join(div.classes)
                ident = f' id="{esc(div.attrs.id)}"' if div.attrs.id else ""
                return f'<div class="{esc(cls)}"{ident}>\n\n{inner}\n\n</div>'
            return f"{div.fence} {div.attrs.to_pandoc()}\n{inner}\n{div.fence}"
        if env.kind in MEDIA:
            return render_media(env, ctx, inner, doc)
        view = env_view(env, ctx)
        view["_lang"] = ctx.lang
        if ctx.target == "mdbook":
            return mdbook_env(env, view, inner)
        return pandoc_env(env, view, inner)

    return mdscan.render_blocks(doc.blocks, div_fn=div_fn, text_fn=text_fn)
