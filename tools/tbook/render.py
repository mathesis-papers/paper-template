"""Target-independent chapter transformation shared by the mdBook and Pandoc pipelines.

Given an :class:`~tbook.model.EditionModel`, :func:`chapter_markdown` rewrites a
chapter's Markdown for one target:

* ``[@id]`` → ``[定理2.1](href)`` (``href`` from :attr:`RenderContext.env_href`);
* ``[text](lean:GID)`` → a permalink to the declaration's Lean source at the pinned commit
  (just the text when the lock does not resolve the GID);
* links/images (inline, ``<…>`` destinations, reference definitions) that point into the
  book directory outside the edition (``../assets/x.svg``) → percent-encoded paths into the
  staged copy ``_book/…`` (files collected in ``ctx.book_files``); ``<…>`` destinations are
  written as plain percent-encoded ones, which every target reads the same way;
* for mdBook, links to a ``README.md`` chapter → ``index.md`` (mdBook publishes it as
  ``index.html``);
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
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from . import config, lean, mdscan
from .model import FORMAL, MEDIA, ChapterDoc, EditionModel, Env

# ``url`` is the destination as written: ``<…>`` (may contain spaces) or a plain one.
LINK_RE = re.compile(r"(?P<bang>!?)\[(?P<text>(?:`[^`]*`|\\.|[^\]\\])*)\]\((?P<url><[^<>\n]*>|[^)\s]+)(?P<title>\s+\"[^\"]*\")?\)")
# A link reference definition ``[label]: url "title"`` (footnotes ``[^x]:`` are excluded by the caller).
REFDEF_RE = re.compile(r"^(?P<lead> {0,3}\[(?:[^\]\\]|\\.)+\]:[ \t]*)(?P<url><[^<>\n]*>|\S+)(?P<rest>.*)$")
EXTERNAL_RE = re.compile(r"^(?:[a-z][a-z0-9+.-]*:|#|/)", re.I)
# Characters a plain (non ``<…>``) destination cannot hold, and those a decoded file path
# must also escape to stay one path.
_DEST_UNSAFE_RE = re.compile(r"[\s<>()]")
_PATH_UNSAFE_RE = re.compile(r"[\s<>()%#?\\]")


def _quote(pattern: re.Pattern, text: str) -> str:
    return pattern.sub(lambda m: urllib.parse.quote(m.group(), safe=""), text)


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


def is_readme(path: str) -> bool:
    """mdBook's index preprocessor publishes a chapter ``README.md`` (any case) as ``index.md``."""
    stem, ext = posixpath.splitext(posixpath.basename(path))
    return stem.lower() == "readme" and ext.lower() == ".md"


def mdbook_chapter_path(path: str) -> str:
    """The path mdBook publishes chapter ``path`` under: ``a/README.md`` → ``a/index.md``.

    mdBook does not rewrite links to a README chapter, so every link into one (``[@id]``,
    plain links, the ledger) must use this path or it points at a missing ``README.html``.
    """
    return posixpath.join(posixpath.dirname(path), "index.md") if is_readme(path) else path


def mdbook_env_href(model: EditionModel) -> Callable[[Env, ChapterDoc], str]:
    def href(env: Env, frm: ChapterDoc) -> str:
        target = model.chapter_of(env.id)
        if target is None or target is frm:
            return "#" + env.id
        rel = posixpath.relpath(mdbook_chapter_path(target.chapter.path), posixpath.dirname(frm.chapter.path) or ".")
        return f"{rel}#{env.id}"

    return href


# --------------------------------------------------------------------------- data views


def lean_view(gid: str, lock: lean.Lock | None) -> dict:
    """What the book shows for ``gid``. Links only when the lock resolves it (``resolved``):
    an unresolved GID is shown as text, never as a link that suggests the declaration exists."""
    view = {"gid": gid, "name": "", "kind": "", "url": "", "state_url": "", "blueprint_url": "",
            "line": 0, "signature": "", "statement_id": "", "resolved": False}
    try:
        g = lean.parse_gid(gid)
    except lean.LeanError:
        return view
    view["name"] = g.lean_module + "." + g.name if not g.name.startswith(g.lean_module) else g.name
    res = lock.get(gid) if lock else None
    if res:
        view.update(name=res.name, kind=res.kind, line=res.line, signature=res.signature,
                    statement_id=res.statement_id, resolved=True,
                    url=lock.source_url(gid), state_url=lock.state_url(gid),
                    blueprint_url=lock.blueprint_url(gid))
    return view


def lean_verified(views: list[dict]) -> bool:
    """True when every cited declaration resolves in the lock to a Lean theorem (the green badge)."""
    return bool(views) and all(v["resolved"] and v["kind"] in lean.FORMAL_KINDS for v in views)


def _s(lang: str, key: str, fallback: str, default: str = "") -> str:
    return config.s(lang, key) or config.s(lang, fallback) or default


def unverified_badge(lang: str) -> tuple[str, str]:
    """Badge text and tooltip for a formal result the lock does not back (``check`` rejects it)."""
    return (_s(lang, "badge.unverified", "slides.badge_unverified", "UNVERIFIED"),
            _s(lang, "badge.unverified_title", "slides.badge_unverified_title"))


def env_view(env: Env, ctx: RenderContext) -> dict:
    lang = ctx.lang
    badge = ""
    badge_title = ""
    status = env.status
    leans = [lean_view(g, ctx.lock) for g in env.lean]
    unverified = False
    if env.kind in FORMAL:
        if lean_verified(leans):
            badge, badge_title = config.s(lang, "badge.lean"), config.s(lang, "badge.lean_title")
        else:
            # The build never claims what the lock cannot back: red UNVERIFIED, as the slides do.
            unverified = True
            status = "open"
            badge, badge_title = unverified_badge(lang)
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
        "status": status,
        "unverified": unverified,
        "badge": badge,
        "badge_title": badge_title,
        "lean": leans,
        "attrs": dict(env.attrs.kv),
    }


# --------------------------------------------------------------------------- inline


def _rewrite_links(line: str, doc: ChapterDoc, ctx: RenderContext) -> str:
    book_dir = ctx.book.dir.resolve()
    edition_dir = ctx.edition.dir.resolve()
    chapter_dir = doc.path.parent.resolve()

    def new_url(raw: str) -> str | None:
        """The destination to write for ``raw`` (as written); None drops the link, keeping its text."""
        angle = raw.startswith("<") and raw.endswith(">")
        url = raw[1:-1] if angle else raw
        if url.startswith("lean:"):
            return lean_view(url[5:], ctx.lock)["url"] or None
        plain = _quote(_DEST_UNSAFE_RE, url) if angle else raw
        path_part, _, frag = url.partition("#")
        if EXTERNAL_RE.match(url) or not path_part:
            return plain
        frag = "#" + (_quote(_DEST_UNSAFE_RE, frag) if angle else frag) if frag else ""
        path = urllib.parse.unquote(path_part)
        target = (chapter_dir / path).resolve()
        try:
            inside = target.relative_to(edition_dir).as_posix()
        except ValueError:
            inside = None
        if inside is not None:  # inside the edition: staged as is
            if (ctx.target == "mdbook" and is_readme(inside)
                    and any(posixpath.normpath(d.chapter.path) == inside for d in ctx.model.chapters)):
                return _quote(_PATH_UNSAFE_RE, mdbook_chapter_path(path)) + frag
            return plain
        try:
            inside_book = target.relative_to(book_dir)
        except ValueError:
            ctx.issues.append(f"{doc.path}: link leaves the book directory: {url}")
            return plain
        ctx.book_files.add(target)
        staged_chapter_dir = posixpath.dirname(doc.chapter.path) or "."
        new = posixpath.relpath(posixpath.join(ctx.book_prefix, inside_book.as_posix()), staged_chapter_dir)
        return _quote(_PATH_UNSAFE_RE, new) + frag

    def repl(m: re.Match) -> str:
        new = new_url(m.group("url"))
        if new is None:
            return m.group("text")
        if new == m.group("url"):
            return m.group(0)
        return f"{m.group('bang')}[{m.group('text')}]({new}{m.group('title') or ''})"

    refdef = REFDEF_RE.match(line)
    if refdef and not line.lstrip().startswith("[^"):
        new = new_url(refdef.group("url"))
        return f"{refdef.group('lead')}{refdef.group('url') if new is None else new}{refdef.group('rest')}"
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
    classes = f"tr-env tr-{env.kind} tr-status-{view['status']}" + (" tr-unverified" if view.get("unverified") else "")
    head = [f'<span class="tr-env-label">{esc(view["ref_text"])}</span>']
    if env.kind == "proof":
        head = [f'<span class="tr-env-label">{esc(view["label"])}</span>']
    if view["title"]:
        open_p = config.s(env_lang(view), "punct.title_open")
        head.append(f'<span class="tr-env-title">{esc(open_p)}{esc(view["title"])}'
                    f'{esc(config.s(env_lang(view), "punct.title_close"))}</span>')
    if view["badge"]:
        first = view["lean"][0]["url"] if view["lean"] and not view.get("unverified") else ""
        cls = "tr-badge-lean" if view["status"] == "lean" else "tr-badge-open"
        if view.get("unverified"):
            cls += " tr-badge-unverified"
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
            else:  # not resolved by the lock: no link (``check`` reports it)
                links.append(f'<code class="tr-lean-decl tr-lean-unresolved" title="{esc(lv["gid"])}">{name}</code>')
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
