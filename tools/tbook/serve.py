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

Files are served with ``Accept-Ranges: bytes`` and honour a single byte range (RFC 9110 §14),
as Pages does: Safari and iOS play a ``<video>`` only from a server that answers range requests
with 206. See ``byte_range`` for which ``Range`` headers are honoured, ignored or refused.
"""

from __future__ import annotations

import datetime
import email.utils
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


class RangeNotSatisfiable(ValueError):
    """A well-formed byte range that selects nothing of the file (answered with 416)."""


_MAX_RANGE_HEADER = 256  # a longer Range header is ignored (players send a few dozen bytes)


def _digits(text: str) -> bool:
    """``text`` is empty or ASCII digits only (no sign, no underscore, no other Unicode digits)."""
    return text == "" or (text.isascii() and text.isdigit())


def byte_range(header: str | None, size: int) -> tuple[int, int] | None:
    """The inclusive ``(first, last)`` bytes a ``Range`` header selects from a ``size``-byte file.

    Returns None when the header is to be ignored, i.e. the whole file is sent with 200: no header,
    a unit other than ``bytes``, a syntactically invalid range set (RFC 9110 §14.2 lets a server
    ignore it), several ranges (honouring only single ranges keeps the server simple; media players
    ask for one range at a time), or an empty file. Raises ``RangeNotSatisfiable`` for a valid
    single range that selects nothing: a first byte at or past the end, or a zero-length suffix.
    """
    if header is None or size <= 0 or len(header) > _MAX_RANGE_HEADER:
        return None
    unit, sep, ranges = header.partition("=")
    if not sep or unit.strip().lower() != "bytes":
        return None
    specs = [spec.strip() for spec in ranges.split(",") if spec.strip()]  # empty list items don't count
    if len(specs) != 1:
        return None
    first, dash, last = specs[0].partition("-")  # string parsing, no regular expression on the header
    if not dash or not (first or last) or not _digits(first) or not _digits(last):
        return None
    if not first:  # suffix range "-n": the last n bytes
        length = int(last)
        if length == 0:
            raise RangeNotSatisfiable(header)
        return max(size - length, 0), size - 1
    first = int(first)
    if last and int(last) < first:
        return None  # invalid, not unsatisfiable
    if first >= size:
        raise RangeNotSatisfiable(header)
    return first, min(int(last), size - 1) if last else size - 1


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
        elif inner.endswith("/"):  # "page.html/" names no file, as on Pages
            self._not_found()
            return
        if not fs_path.is_file():
            self._not_found()
            return
        self._send_file(fs_path, head)

    # -- files -------------------------------------------------------------------
    def _send_file(self, fs_path: Path, head: bool) -> None:
        """Answer with the regular file ``fs_path``: 200, 304, or for a byte range 206 or 416.

        Precedence follows RFC 9110 §13.2.2: If-Modified-Since (304, decided as
        SimpleHTTPRequestHandler does) before Range. Range applies to GET only (§14.2: HEAD
        ignores it and gets the full response's headers). If-Range is honoured when it is
        exactly the Last-Modified date this response carries; anything else (an entity tag,
        since no ETag is sent, or another date) means the file may have changed, so the Range
        is ignored and the whole file is sent with 200.
        """
        try:
            f = open(fs_path, "rb")
        except OSError:
            self._not_found()
            return
        with f:
            st = os.fstat(f.fileno())
            size = st.st_size
            if self._not_modified(st.st_mtime):
                self.send_response(HTTPStatus.NOT_MODIFIED)
                self.end_headers()
                return
            last_modified = self.date_time_string(st.st_mtime)
            span = None
            if not head and self.headers.get("If-Range", last_modified).strip() == last_modified:
                try:
                    span = byte_range(self.headers.get("Range"), size)
                except RangeNotSatisfiable:
                    self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                    self.send_header("Content-Range", f"bytes */{size}")
                    self.send_header("Content-Length", "0")
                    self.send_header("Accept-Ranges", "bytes")
                    self.end_headers()
                    return
            first, last = span or (0, size - 1)
            self.send_response(HTTPStatus.PARTIAL_CONTENT if span else HTTPStatus.OK)
            self.send_header("Content-Type", self.guess_type(str(fs_path)))
            self.send_header("Content-Length", str(last - first + 1))
            if span:
                self.send_header("Content-Range", f"bytes {first}-{last}/{size}")
            self.send_header("Last-Modified", last_modified)
            self.send_header("Accept-Ranges", "bytes")
            self.end_headers()
            if head:
                return
            if not span:
                self.copyfile(f, self.wfile)
                return
            f.seek(first)
            remaining = last - first + 1
            while remaining > 0:
                chunk = f.read(min(remaining, 64 * 1024))
                if not chunk:  # the file shrank while being sent
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)

    def _not_modified(self, mtime: float) -> bool:
        """If-Modified-Since says the client's copy is current (SimpleHTTPRequestHandler's test)."""
        if "If-Modified-Since" not in self.headers or "If-None-Match" in self.headers:
            return False
        try:
            since = email.utils.parsedate_to_datetime(self.headers["If-Modified-Since"])
        except (TypeError, IndexError, OverflowError, ValueError):
            return False  # ill-formed: ignored
        if since.tzinfo is None:  # obsolete format without a zone: GMT (RFC 9110 §5.6.7)
            since = since.replace(tzinfo=datetime.timezone.utc)
        if since.tzinfo is not datetime.timezone.utc:
            return False
        modified = datetime.datetime.fromtimestamp(mtime, datetime.timezone.utc).replace(microsecond=0)
        return modified <= since

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
