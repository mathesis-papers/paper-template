"""Tests for byte-range support in ``./tbook serve`` (Safari and iOS play <video> only with 206).

Run: PYTHONPATH=tools python -m unittest discover -s tools/tests -p 'test_serve.py'

The server runs on 127.0.0.1 over a temporary site; requests go through http.client, which never
uses a proxy. The Pages routing itself (redirects, 404 page, MIME types) is tested in test_site.py.
"""

from __future__ import annotations

import http.client
import os
import shutil
import tempfile
import threading
import time
import unittest
from email.utils import formatdate
from pathlib import Path
from unittest import mock

from tbook import serve

DATA = bytes(range(256)) * 4 + b"tail"  # 1028 bytes, every slice distinct
SIZE = len(DATA)


class ByteRangeTest(unittest.TestCase):
    def test_single_ranges(self):
        self.assertEqual(serve.byte_range("bytes=0-3", 10), (0, 3))
        self.assertEqual(serve.byte_range("bytes=5-", 10), (5, 9))
        self.assertEqual(serve.byte_range("bytes=-4", 10), (6, 9))
        self.assertEqual(serve.byte_range("bytes=-40", 10), (0, 9))  # longer suffix: whole file
        self.assertEqual(serve.byte_range("bytes=2-99", 10), (2, 9))  # last clipped to the end
        self.assertEqual(serve.byte_range("bytes=9-9", 10), (9, 9))
        self.assertEqual(serve.byte_range(" Bytes = 1-2 ", 10), (1, 2))
        self.assertEqual(serve.byte_range("bytes=1-2,", 10), (1, 2))  # empty list items don't count

    def test_ignored(self):
        for header in (None, "", "bytes", "bytes=", "bytes=-", "bytes=a-b", "bytes=1-x", "bytes=3-1",
                       "bytes=+1-2", "bytes=1 - 2", "bytes=٣-", "bytes=1_0-", "items=0-3",
                       "bytes=0-1,5-6", "bytes=0-1,99-"):
            self.assertIsNone(serve.byte_range(header, 10), header)
        self.assertIsNone(serve.byte_range("bytes=0-3", 0))  # an empty file is sent whole

    def test_unsatisfiable(self):
        for header in ("bytes=10-", "bytes=10-20", "bytes=99999999999999999999-", "bytes=-0"):
            with self.assertRaises(serve.RangeNotSatisfiable, msg=header):
                serve.byte_range(header, 10)


class RangeServeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="tbook-serve-range-"))
        (cls.tmp / "index.html").write_text("<!doctype html><title>home</title>", encoding="utf-8")
        (cls.tmp / "404.html").write_text("<!doctype html><title>SIGNAL LOST</title>", encoding="utf-8")
        films = cls.tmp / "book" / "films"
        films.mkdir(parents=True)
        (films / "clip.mp4").write_bytes(DATA)
        (films / "empty.mp4").write_bytes(b"")
        (cls.tmp / "book" / "index.html").write_text("book index", encoding="utf-8")
        mtime = time.time() - 3600  # well in the past, so Last-Modified is a stable validator
        os.utime(films / "clip.mp4", (mtime, mtime))
        cls.last_modified = formatdate(mtime, usegmt=True)
        cls.server = serve.make_server(0, cls.tmp, base="/repo/")
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def request(self, path: str, method: str = "GET", **headers: str):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            with mock.patch("sys.stderr"):
                conn.request(method, path, headers={k.replace("_", "-"): v for k, v in headers.items()})
                r = conn.getresponse()
                return r.status, r.headers, r.read()
        finally:
            conn.close()

    CLIP = "/repo/book/films/clip.mp4"

    def test_full_get_advertises_ranges(self):
        code, headers, body = self.request(self.CLIP)
        self.assertEqual(code, 200)
        self.assertEqual(body, DATA)
        self.assertEqual(headers["Accept-Ranges"], "bytes")
        self.assertEqual(headers["Content-Length"], str(SIZE))
        self.assertEqual(headers["Content-Type"], "video/mp4")
        self.assertIsNone(headers["Content-Range"])
        self.assertEqual(headers["Last-Modified"], self.last_modified)

    def test_head(self):
        code, headers, body = self.request(self.CLIP, "HEAD")
        self.assertEqual((code, body), (200, b""))
        self.assertEqual(headers["Accept-Ranges"], "bytes")
        self.assertEqual(headers["Content-Length"], str(SIZE))
        # HEAD ignores Range (RFC 9110 §14.2: ranges are defined for GET only)
        code, headers, body = self.request(self.CLIP, "HEAD", Range="bytes=0-3")
        self.assertEqual((code, body, headers["Content-Length"]), (200, b"", str(SIZE)))
        self.assertIsNone(headers["Content-Range"])

    def test_directory_index_advertises_ranges(self):
        code, headers, body = self.request("/repo/book/")
        self.assertEqual((code, body), (200, b"book index"))
        self.assertEqual(headers["Accept-Ranges"], "bytes")
        self.assertTrue(headers["Content-Type"].startswith("text/html"))
        code, headers, body = self.request("/repo/book/", Range="bytes=0-3")
        self.assertEqual((code, body, headers["Content-Range"]), (206, b"book", "bytes 0-3/10"))

    def assert_partial(self, rng: str, first: int, last: int):
        code, headers, body = self.request(self.CLIP, Range=rng)
        self.assertEqual(code, 206, rng)
        self.assertEqual(body, DATA[first:last + 1], rng)
        self.assertEqual(headers["Content-Range"], f"bytes {first}-{last}/{SIZE}", rng)
        self.assertEqual(headers["Content-Length"], str(last - first + 1), rng)
        self.assertEqual(headers["Content-Type"], "video/mp4", rng)
        self.assertEqual(headers["Accept-Ranges"], "bytes", rng)

    def test_partial(self):
        self.assert_partial("bytes=0-3", 0, 3)
        self.assert_partial("bytes=0-1", 0, 1)  # Safari's first probe
        self.assert_partial("bytes=5-", 5, SIZE - 1)
        self.assert_partial("bytes=-4", SIZE - 4, SIZE - 1)
        self.assert_partial("bytes=1000-99999", 1000, SIZE - 1)
        self.assert_partial(f"bytes={SIZE - 1}-", SIZE - 1, SIZE - 1)

    def test_partial_spans_read_chunks(self):
        big = self.tmp / "book" / "films" / "big.webm"
        data = os.urandom(200 * 1024 + 7)
        big.write_bytes(data)
        code, headers, body = self.request("/repo/book/films/big.webm", Range="bytes=1000-150000")
        self.assertEqual((code, body), (206, data[1000:150001]))
        self.assertEqual(headers["Content-Type"], "video/webm")
        self.assertEqual(headers["Content-Range"], f"bytes 1000-150000/{len(data)}")

    def test_unsatisfiable(self):
        for rng in (f"bytes={SIZE}-", f"bytes={SIZE + 10}-{SIZE + 20}", "bytes=-0"):
            code, headers, body = self.request(self.CLIP, Range=rng)
            self.assertEqual(code, 416, rng)
            self.assertEqual(headers["Content-Range"], f"bytes */{SIZE}", rng)
            self.assertEqual(body, b"", rng)

    def test_ignored_ranges_send_everything(self):
        for rng in ("bytes=a-b", "bytes=3-1", "bytes=", "items=0-3", "bytes=0-1,5-6"):
            code, headers, body = self.request(self.CLIP, Range=rng)
            self.assertEqual((code, body), (200, DATA), rng)
            self.assertEqual(headers["Accept-Ranges"], "bytes", rng)
            self.assertIsNone(headers["Content-Range"], rng)

    def test_empty_file(self):
        code, headers, body = self.request("/repo/book/films/empty.mp4", Range="bytes=0-1")
        self.assertEqual((code, body, headers["Content-Length"]), (200, b"", "0"))

    def test_if_range(self):
        code, _, body = self.request(self.CLIP, Range="bytes=0-3", If_Range=self.last_modified)
        self.assertEqual((code, body), (206, DATA[:4]))
        for stale in ('"some-etag"', formatdate(0, usegmt=True)):
            code, _, body = self.request(self.CLIP, Range="bytes=0-3", If_Range=stale)
            self.assertEqual((code, body), (200, DATA), stale)

    def test_not_modified_before_range(self):
        code, _, body = self.request(self.CLIP, Range="bytes=0-3", If_Modified_Since=self.last_modified)
        self.assertEqual((code, body), (304, b""))
        code, _, body = self.request(self.CLIP, If_Modified_Since=formatdate(0, usegmt=True))
        self.assertEqual((code, body), (200, DATA))

    def test_routing_unchanged(self):
        code, headers, _ = self.request("/repo/book/films/clip.mp4/", Range="bytes=0-3")
        self.assertEqual(code, 404)
        for path in ("/repo/book/films/missing.mp4", "/elsewhere/clip.mp4", "/book/films/clip.mp4"):
            code, headers, body = self.request(path, Range="bytes=0-3")
            self.assertEqual(code, 404, path)
            self.assertIn(b"SIGNAL LOST", body, path)
            self.assertIsNone(headers["Content-Range"], path)
        code, headers, _ = self.request("/repo/book/films", Range="bytes=0-3")
        self.assertEqual((code, headers["Location"]), (301, "/repo/book/films/"))
        code, headers, body = self.request("/repo/book/films/", Range="bytes=0-3")  # no index, no listing
        self.assertEqual(code, 404)
        self.assertIn(b"SIGNAL LOST", body)
        code, headers, _ = self.request("/", Range="bytes=0-3")
        self.assertEqual((code, headers["Location"]), (301, "/repo/"))


if __name__ == "__main__":
    unittest.main()
