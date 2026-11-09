"""Command line: ``./tbook <command>`` (or ``python3 -m tbook`` with ``PYTHONPATH=tools``)."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys

from . import __version__, config, paths


def _langs_titles(values: list[str] | None) -> dict[str, str]:
    out: dict[str, str] = {}
    for v in values or []:
        if "=" not in v:
            raise SystemExit(f"--title expects LANG=TEXT, got {v!r}")
        lang, text = v.split("=", 1)
        out[lang.strip()] = text.strip()
    return out


def _books(args) -> list[config.Book]:
    return config.load_books(args.book or None)


def cmd_check(args) -> int:
    from . import check

    issues = check.run(_books(args), offline=args.offline)
    gh = os.environ.get("GITHUB_ACTIONS") == "true"
    errors = [i for i in issues if i.severity == "error"]
    warnings = [i for i in issues if i.severity != "error"]
    for issue in errors + warnings:
        print(issue.github() if gh else issue.format())
    n_books = len(_books(args))
    print(f"check: {n_books} book(s), {len(errors)} error(s), {len(warnings)} warning(s)")
    if args.strict and warnings:
        return 1
    return 1 if errors else 0


def cmd_pin(args) -> int:
    from pathlib import Path

    from . import lean, pin

    if args.report:  # before pinning: the lock must not be rewritten when the report cannot be
        try:
            Path(args.report).parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            print(f"pin: cannot write --report {args.report}: {exc}", file=sys.stderr)
            return 1
    try:
        report = pin.pin(args.ref, refresh=args.refresh, offline=args.offline, dry_run=args.dry_run)
    except lean.LeanError as exc:
        print(f"pin: {exc}", file=sys.stderr)
        return 1
    except (KeyError, ValueError) as exc:
        print(f"pin: unreadable {paths.rel(paths.LOCK_FILE)}: {exc!r}; delete it and run ./tbook pin", file=sys.stderr)
        return 1
    text = report.markdown()
    print(text)
    if args.report:
        try:
            Path(args.report).write_text(text + "\n", encoding="utf-8")
        except OSError as exc:
            print(f"pin: cannot write --report {args.report}: {exc}", file=sys.stderr)
            return 1
    if report.errors or report.refused:
        return 1
    if report.written:
        print(f"wrote {paths.rel(paths.LOCK_FILE)} at {report.commit}")
    return 0


def cmd_build(args) -> int:
    from . import build

    result = build.build(args.targets or ["all"], _books(args), args.lang or None, pdf_variants=args.variant or None)
    for f in result.failures:
        print(f"FAILED {f}", file=sys.stderr)
    return 1 if result.failures else 0


def _slides_backdrop(check: bool) -> int:
    """Check (or render again, when stale) the slide theme's print backdrop, which is rendered from
    theme/generated/tokens.css in Chromium (tools/node/slides-backdrop.mjs). 0 when it is up to date or
    there is nothing to do."""
    script = paths.ROOT / "tools" / "node" / "slides-backdrop.mjs"
    if not script.exists() or not (paths.THEME / "slides" / "styles" / "backdrop.css").exists():
        return 0
    node = shutil.which("node")
    if not node:
        print("note: node not found, so the slides' print backdrop (theme/slides/styles/backdrop.jpg) was not "
              "checked; run node tools/node/slides-backdrop.mjs where Node is installed")
        return 0
    r = subprocess.run([node, str(script), *(["--check"] if check else [])], cwd=paths.ROOT, capture_output=True,
                       text=True)
    out = (r.stdout + r.stderr).strip()
    if out and (r.returncode or not out.endswith("is up to date")):
        print(out)
    return r.returncode


def cmd_theme(args) -> int:
    from . import theme

    if args.check:
        stale = theme.stale_outputs()
        for p in stale:
            print(f"stale: {paths.rel(p)}")
        backdrop = _slides_backdrop(check=True)
        return 1 if stale or backdrop else 0
    for p in theme.write():
        print(f"wrote {paths.rel(p)}")
    if _slides_backdrop(check=False):
        print("warning: the slides' print backdrop was not rendered again (see above); slide PDFs would draw "
              "an outdated backdrop until it is")
    return 0


def cmd_new_book(args) -> int:
    from . import newbook

    titles = _langs_titles(args.title)
    langs = args.langs.split(",") if args.langs else None
    path = newbook.new_book(args.slug, titles, langs=langs, author=args.author or "", code=args.code or "",
                            subtitles=_langs_titles(args.subtitle))
    print(f"created {paths.rel(path)}")
    return 0


def cmd_new_chapter(args) -> int:
    from . import newbook

    for p in newbook.new_chapter(args.book, args.name, _langs_titles(args.title)):
        print(f"created {paths.rel(p)}")
    return 0


def cmd_serve(args) -> int:
    from . import serve

    return serve.serve(port=args.port, directory=args.dir)


def cmd_doctor(args) -> int:
    from . import doctor

    return doctor.run()


def cmd_lean_project(args) -> int:
    from . import leanverify

    out = leanverify.generate(args.out)
    print(f"wrote Lean verification project to {paths.rel(out)}")
    return 0


def cmd_template(args) -> int:
    from . import template

    return template.main(args)


def cmd_media(args) -> int:
    """``viz|slides|film new …`` delegate to the Node/Python scaffolders of each media kind."""
    import importlib

    mod = importlib.import_module(f"tbook.{args.kind}")
    return mod.cli(args)


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="tbook", description="Build and verify trureturing monographs.")
    p.add_argument("--version", action="version", version=f"tbook {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("check", help="verify structure, bilingual parity and Lean citations")
    c.add_argument("--book", action="append", help="limit to a book slug (repeatable)")
    c.add_argument("--offline", action="store_true", help="do not fetch trureturing state over the network")
    c.add_argument("--strict", action="store_true", help="fail on warnings too")
    c.set_defaults(fn=cmd_check)

    c = sub.add_parser("pin", help="pin a trureturing commit and resolve cited declarations")
    c.add_argument("ref", nargs="?", help="commit SHA (full or abbreviated), branch or tag; it must be on the "
                                          "site.toml branch (default: that branch's head)")
    c.add_argument("--refresh", action="store_true", help="keep the pinned commit; re-resolve cited GIDs")
    c.add_argument("--offline", action="store_true")
    c.add_argument("--dry-run", action="store_true", help="report changes without writing the lock")
    c.add_argument("--report", help="also write the Markdown report to this file")
    c.set_defaults(fn=cmd_pin)

    c = sub.add_parser("build", help="build html, pdf, epub, viz, slides, films and the site")
    c.add_argument("targets", nargs="*", choices=["all", "html", "pdf", "epub", "viz", "slides", "films", "site"],
                   help="default: all")
    c.add_argument("--book", action="append")
    c.add_argument("--lang", action="append", help="limit to an edition language (repeatable)")
    c.add_argument("--variant", action="append", choices=list(config.PDF_VARIANTS), help="limit PDF variants")
    c.set_defaults(fn=cmd_build)

    c = sub.add_parser("theme", help="regenerate theme/generated/* from theme/tokens.json")
    c.add_argument("--check", action="store_true")
    c.set_defaults(fn=cmd_theme)

    c = sub.add_parser("new-book", help="scaffold books/<slug>")
    c.add_argument("slug")
    c.add_argument("--title", action="append", required=True, help="LANG=TITLE, once per edition")
    c.add_argument("--subtitle", action="append", help="LANG=SUBTITLE")
    c.add_argument("--langs", help="comma-separated editions (default: site languages)")
    c.add_argument("--author")
    c.add_argument("--code", help="cover code such as GOLDEN//OBSERVE")
    c.set_defaults(fn=cmd_new_book)

    c = sub.add_parser("new-chapter", help="add a chapter to every edition of a book")
    c.add_argument("book")
    c.add_argument("name", help="file name without .md, e.g. ch02-deficit")
    c.add_argument("--title", action="append", required=True, help="LANG=TITLE, once per edition")
    c.set_defaults(fn=cmd_new_chapter)

    c = sub.add_parser("serve", help="serve _site locally under the Pages base path")
    c.add_argument("--port", type=int, default=8765)
    c.add_argument("--dir", default=str(paths.SITE_OUT))
    c.set_defaults(fn=cmd_serve)

    c = sub.add_parser("doctor", help="check the local toolchain and print how to fix gaps")
    c.set_defaults(fn=cmd_doctor)

    c = sub.add_parser("lean-project", help="generate a Lake project that re-checks every cited theorem's axioms")
    c.add_argument("--out", default=str(paths.BUILD / "lean-verify"))
    c.set_defaults(fn=cmd_lean_project)

    c = sub.add_parser("template", help="template version: status, update, manifest")
    tsub = c.add_subparsers(dest="template_cmd", required=True)
    t = tsub.add_parser("status", help="show the template version and local changes to managed files")
    t = tsub.add_parser("update", help="update managed files to a template release")
    t.add_argument("--to", help="template version or git ref (default: latest release)")
    t.add_argument("--source", help="local path or git URL of the template (default: template.toml repo)")
    t.add_argument("--dry-run", action="store_true")
    t.add_argument("--force", action="store_true", help="overwrite managed files with local changes")
    t = tsub.add_parser("manifest", help="(template repo) regenerate or check template-manifest.json")
    t.add_argument("--check", action="store_true")
    c.set_defaults(fn=cmd_template)

    for kind in ("viz", "slides", "film"):
        c = sub.add_parser(kind, help=f"{kind} helpers (new, list, …)")
        c.add_argument("action", choices=["new", "list"])
        c.add_argument("rest", nargs=argparse.REMAINDER)
        c.set_defaults(fn=cmd_media, kind=kind)
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        return int(args.fn(args) or 0)
    except config.ConfigError as exc:
        print(f"tbook: {exc}", file=sys.stderr)
        return 2
