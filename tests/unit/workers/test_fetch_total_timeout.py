"""Downloads must survive a pause that is shorter than the total timeout.

_fetch_url_with_total_timeout used to cap each read at 5 seconds and retry
on socket.timeout. socket.SocketIO records the timeout and every later read
raises OSError("cannot read from timed out object"), so a brief stall failed
the whole request.
"""

import http.server
import threading
import time
from contextlib import contextmanager

import pytest

from allium.lib.workers import TotalTimeoutError, _fetch_url_with_total_timeout


# Larger than the 64 KB read chunk so the pause lands mid-body.
_PAUSE_BODY = b"a" * (200 * 1024)


class _QuietHandler(http.server.BaseHTTPRequestHandler):
    """HTTP handler that does not write request logs to stderr."""

    def log_message(self, fmt, *args):
        return


class _PauseHandler(_QuietHandler):
    """Send half of a body, pause 6 seconds, then send the rest."""

    def do_GET(self):
        body = _PAUSE_BODY
        half = len(body) // 2
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body[:half])
            self.wfile.flush()
            time.sleep(6)
            self.wfile.write(body[half:])
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            return


class _StallHandler(_QuietHandler):
    """Send headers and a few bytes, then stall longer than any test timeout."""

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", "100000")
        self.end_headers()
        try:
            self.wfile.write(b"partial")
            self.wfile.flush()
            time.sleep(30)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            return


@contextmanager
def _listening_server(handler):
    """Serve `handler` on 127.0.0.1 with an ephemeral port.

    ThreadingHTTPServer lets shutdown() return while a handler is still
    inside its stall sleep. The accept loop runs on a daemon thread.
    """
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()


def test_pause_shorter_than_total_timeout_still_succeeds():
    with _listening_server(_PauseHandler) as server:
        port = server.server_address[1]
        url = "http://127.0.0.1:%d/pause" % port
        body = _fetch_url_with_total_timeout(url, timeout=20)
    assert body == _PAUSE_BODY


def test_stall_past_total_timeout_raises():
    with _listening_server(_StallHandler) as server:
        port = server.server_address[1]
        url = "http://127.0.0.1:%d/stall" % port
        started = time.monotonic()
        with pytest.raises(TotalTimeoutError):
            _fetch_url_with_total_timeout(url, timeout=3)
        elapsed = time.monotonic() - started
    assert elapsed < 6
