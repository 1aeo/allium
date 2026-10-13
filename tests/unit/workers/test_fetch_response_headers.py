"""_fetch_url_with_total_timeout can report the response Last-Modified header.

The bytes return value is unchanged. A caller that passes response_headers
receives Last-Modified when the server sent it, and an empty dict when it
did not.
"""

import http.server
import threading
from contextlib import contextmanager

from allium.lib.workers import _fetch_url_with_total_timeout


_BODY = b'{"ok": true}'
_LAST_MODIFIED = "Thu, 01 Jan 2026 00:00:00 GMT"


class _QuietHandler(http.server.BaseHTTPRequestHandler):
    """HTTP handler that does not write request logs to stderr."""

    def log_message(self, fmt, *args):
        return


class _HeaderHandler(_QuietHandler):
    """Return a small JSON body, with Last-Modified only on one path."""

    def do_GET(self):
        body = _BODY
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        if self.path == "/with-last-modified":
            self.send_header("Last-Modified", _LAST_MODIFIED)
        self.end_headers()
        self.wfile.write(body)


@contextmanager
def _listening_server():
    """Serve _HeaderHandler on 127.0.0.1 with an ephemeral port."""
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _HeaderHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()


def _url(server, path):
    port = server.server_address[1]
    return "http://127.0.0.1:%d%s" % (port, path)


def test_response_headers_receives_last_modified():
    """A passed dict receives Last-Modified and the body bytes still return."""
    with _listening_server() as server:
        captured = {}
        body = _fetch_url_with_total_timeout(
            _url(server, "/with-last-modified"),
            timeout=5,
            response_headers=captured,
        )
    assert body == _BODY
    assert captured == {"Last-Modified": _LAST_MODIFIED}


def test_response_headers_stays_empty_without_last_modified():
    """A response with no Last-Modified header leaves the dict empty."""
    with _listening_server() as server:
        captured = {}
        body = _fetch_url_with_total_timeout(
            _url(server, "/without-last-modified"),
            timeout=5,
            response_headers=captured,
        )
    assert body == _BODY
    assert captured == {}


def test_fetch_without_response_headers_returns_same_bytes():
    """The original call shape still returns the response body."""
    with _listening_server() as server:
        url = _url(server, "/with-last-modified")
        captured = {}
        with_headers = _fetch_url_with_total_timeout(
            url, timeout=5, response_headers=captured)
        without_headers = _fetch_url_with_total_timeout(url, timeout=5)
    assert with_headers == _BODY
    assert without_headers == with_headers
