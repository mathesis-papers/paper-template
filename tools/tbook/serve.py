"""``./tbook serve``: preview the assembled site exactly as GitHub Pages will serve it.

GitHub Pages serves a project site under ``/<repo>/``; every link the build writes is
relative, so a page that works at ``http://127.0.0.1:8765/`` can still break under the real
base path. This server therefore mounts ``directory`` (``_site/`` by default) at the URL path
of ``site.base_url`` (e.g. ``/trureturing-books-template/``; ``/`` when the base URL is
unknown), redirects ``/`` there, and answers everything outside it — and any missing file —
with the site's ``404.html`` and status 404, as Pages does.

Standard library only (``http.server``). Correct MIME types for the files the books ship
(``.mjs``, ``.wasm``, ``.woff2``, ``.epub``, …); no caching, so a rebuild shows up on reload.
Ctrl-C stops the server cleanly.
"""

from __future__ import annotations

import functools
import os
import posixpath
import sys
import urllib.parse
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import config, paths

# Types that Python's mimetypes table gets wrong or lacks on some platforms.
MIME_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".htm": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".map": "application/json; charset=utf-8",
    ".webmanifest": "application/manifest+json",
    ".txt": "text/plain; charset=utf-8",
    ".md": "text/markdown; charset=utf-8",
    ".xml": "application/xml",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".avif": "image/avif",
    ".ico": "image/x-icon",
    ".wasm": "application/wasm",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
    ".ttf": "font/ttf",
    ".otf": "font/otf",
    ".pdf": "application/pdf",
    ".epub": "application/epub+zip",
    ".mp4": "video/mp4",
    ".webm": "video/webm",
    ".vtt": "text/vtt; charset=utf-8",
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
}


def base_path(site: config.Site | None = None) -> str:
    """URL path the site is mounted at: ``/<repo>/`` from ``site.base_url``, else ``/``."""
    if site is None:
        try:
            site = config.load_site()
        except config.ConfigError:
            return "/"
    if not site.base_url:
        return "/"
    path = urllib.parse.urlparse(site.base_url).path or "/"
    path = "/" + path.strip("/") + "/"
    return "/" if path == "//" else path


class PagesHandler(SimpleHTTPRequestHandler):
    """Serves ``directory`` below ``base`` with Pages-like redirects and 404s."""

    base = "/"
    server_version = "tbook-serve"

    def __init__(self, *args, base: str = "/", **kwargs):
        self.base = base
        super().__init__(*args, **kwargs)

    # -- routing ---------------------------------------------------------------
    def _route(self) -> str | None:
        """Path inside the served directory for this request, or None after answering it."""
        raw = self.path
        # Resolve "." and ".." the way browsers and Pages do before matching the base path
        # (translate_path below never leaves the directory either way).
        path = urllib.parse.unquote(urllib.parse.urlsplit(raw).path) or "/"
        trailing = path.endswith("/")
        path = posixpath.normpath(path)
        path = "/" if path in (".", "/", "//") else path + ("/" if trailing else "")
        if self.base != "/":
            if path in ("/", self.base.rstrip("/")):
                query = urllib.parse.urlsplit(raw).query
                self._redirect(self.base + (f"?{query}" if query else ""))
                return None
            if not path.startswith(self.base):
                self._not_found()
                return None
            path = "/" + path[len(self.base):]
        return path

    def _redirect(self, location: str) -> None:
        self.send_response(HTTPStatus.MOVED_PERMANENTLY)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _not_found(self) -> None:
        page = Path(self.directory) / "404.html"
        body = page.read_bytes() if page.is_file() else b"<!doctype html><title>404</title><h1>404</h1>"
        self.send_response(HTTPStatus.NOT_FOUND)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _serve(self, head: bool) -> None:
        self.original_path = self.path
        inner = self._route()
        if inner is None:
            return
        # Hand the path below the base to SimpleHTTPRequestHandler (which maps it into self.directory).
        query = urllib.parse.urlsplit(self.path).query
        self.path = urllib.parse.quote(inner) + (f"?{query}" if query else "")
        fs_path = Path(self.translate_path(self.path))
        if fs_path.is_dir() and not inner.endswith("/"):
            self._redirect(urllib.parse.quote(self.base.rstrip("/") + inner + "/") + (f"?{query}" if query else ""))
            return
        if fs_path.is_dir():
            fs_path = fs_path / "index.html"
        if not fs_path.is_file():
            self._not_found()
            return
        f = self.send_head()
        if f:
            try:
                if not head:
                    self.copyfile(f, self.wfile)
            finally:
                f.close()

    def do_GET(self) -> None:  # noqa: N802 - http.server API
        self._serve(head=False)

    def do_HEAD(self) -> None:  # noqa: N802 - http.server API
        self._serve(head=True)

    def list_directory(self, path):  # never show listings, like Pages
        self._not_found()
        return None

    # -- headers -----------------------------------------------------------------
    def guess_type(self, path) -> str:
        ext = posixpath.splitext(str(path))[1].lower()
        return MIME_TYPES.get(ext) or super().guess_type(path)

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write(f"  {fmt % args}\n")

    def log_request(self, code="-", size="-") -> None:
        if isinstance(code, HTTPStatus):
            code = code.value
        path = urllib.parse.unquote(getattr(self, "original_path", self.path))
        sys.stderr.write(f"  {code} {self.command} {path}\n")


class PagesServer(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address) -> None:
        """Browsers abort requests all the time (navigation, media seeking): not worth a traceback."""
        exc = sys.exc_info()[1]
        if isinstance(exc, (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, TimeoutError)):
            return
        super().handle_error(request, client_address)


def make_server(port: int, directory: str | Path, *, base: str | None = None,
                host: str = "127.0.0.1") -> ThreadingHTTPServer:
    """A ready (not yet serving) server; ``port=0`` picks a free port (``server.server_address``)."""
    base = base if base is not None else base_path()
    if not base.startswith("/") or not base.endswith("/"):
        raise ValueError(f"base path must start and end with '/', got {base!r}")
    handler = functools.partial(PagesHandler, directory=str(Path(directory).resolve()), base=base)
    return PagesServer((host, port), handler)


def serve(port: int = 8765, directory: str = str(paths.SITE_OUT), *, host: str | None = None) -> int:
    """Serve ``directory`` under the Pages base path until Ctrl-C; returns the exit code."""
    root = Path(directory)
    if not (root / "index.html").is_file():
        print(f"serve: {paths.rel(root)}/index.html not found; build the site first: ./tbook build site",
              file=sys.stderr)
        return 1
    host = host or os.environ.get("TBOOK_SERVE_HOST") or "127.0.0.1"
    base = base_path()
    try:
        server = make_server(port, root, base=base, host=host)
    except OSError as exc:
        print(f"serve: cannot listen on {host}:{port}: {exc.strerror or exc}; try --port {port + 1}", file=sys.stderr)
        return 1
    shown_host = "127.0.0.1" if host in ("0.0.0.0", "") else host
    url = f"http://{shown_host}:{server.server_address[1]}{base}"
    print(f"serving {paths.rel(root)} at {url}  (Ctrl-C to stop)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nserve: stopped", flush=True)
    finally:
        server.server_close()
    return 0
