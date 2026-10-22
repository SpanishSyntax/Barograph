"""Unit tests for Prism live-reloading preview server and HTTP handler."""

from __future__ import annotations

import time
import urllib.request
from pathlib import Path
import pytest

from prism.server import AUTO_RELOAD_SNIPPET, PreviewServer


def test_preview_server_compile_html(tmp_path: Path) -> None:
    html_file = tmp_path / "dashboard.html"
    html_file.write_text("<!DOCTYPE html><html><body><h1>Test</h1></body></html>")

    server = PreviewServer(target_path=html_file, port=0, open_browser=False)
    assert server.compile_once() is True
    assert b"<h1>Test</h1>" in server.get_html_bytes()


def test_preview_server_compile_py(tmp_path: Path) -> None:
    script = tmp_path / "plot.py"
    script.write_text("""
class MockFig:
    def write_html(self, path, **kwargs):
        if hasattr(path, "write"):
            path.write("<html><body>Interactive Plotly</body></html>")
        else:
            with open(path, "w") as f:
                f.write("<html><body>Interactive Plotly</body></html>")
    def to_plotly_json(self):
        return {}
fig = MockFig()
""")

    server = PreviewServer(target_path=script, port=0, open_browser=False)
    assert server.compile_once() is True
    assert b"Interactive Plotly" in server.get_html_bytes()


def test_preview_server_http_serving(tmp_path: Path) -> None:
    html_file = tmp_path / "index.html"
    html_file.write_text("<!DOCTYPE html><html><body><h1>Hello Prism</h1></body></html>")

    server = PreviewServer(target_path=html_file, host="127.0.0.1", port=0, open_browser=False)
    assert server.compile_once() is True

    # Start HTTP server in thread
    import threading
    from http.server import HTTPServer
    from prism.server import LiveReloadHTTPHandler

    LiveReloadHTTPHandler.html_provider = server.get_html_bytes
    LiveReloadHTTPHandler.mtime_provider = server.get_mtime
    LiveReloadHTTPHandler.target_path = server.target_path

    httpd = HTTPServer(("127.0.0.1", 0), LiveReloadHTTPHandler)
    port = httpd.server_address[1]

    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()

    try:
        # 1. Test / endpoint
        url_root = f"http://127.0.0.1:{port}/"
        with urllib.request.urlopen(url_root) as resp:
            assert resp.status == 200
            content = resp.read()
            assert b"Hello Prism" in content
            assert b"Prism Live Reload Snippet" in content

        # 2. Test /_mtime endpoint
        url_mtime = f"http://127.0.0.1:{port}/_mtime"
        with urllib.request.urlopen(url_mtime) as resp:
            assert resp.status == 200
            mtime_val = float(resp.read().decode())
            assert mtime_val > 0
    finally:
        httpd.shutdown()
        httpd.server_close()
