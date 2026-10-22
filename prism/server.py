"""Live-reloading HTTP preview server and file watcher for Prism."""

from __future__ import annotations

import os
import signal
import sys
import tempfile
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

from prism.exporter import render_to_html_string
from prism.runner import run_script
from prism.ui import ui

AUTO_RELOAD_SNIPPET = b"""
<!-- Prism Live Reload Snippet -->
<script>
  (function() {
    let lastMtime = null;
    setInterval(() => {
      fetch('/_mtime')
        .then(response => {
          if (!response.ok) return;
          return response.text();
        })
        .then(mtime => {
          if (mtime === undefined) return;
          if (lastMtime === null) {
            lastMtime = mtime;
          } else if (lastMtime !== mtime) {
            console.log("[prism] Plot script changed. Reloading dashboard...");
            location.reload();
          }
        })
        .catch(() => {});
    }, 500);
  })();
</script>
"""


class LiveReloadHTTPHandler(BaseHTTPRequestHandler):
    """Custom HTTP request handler serving the compiled plot with auto-reload injection."""

    # These class-level variables are configured before server starts
    html_provider: Any = None
    mtime_provider: Any = None
    target_path: Path | None = None

    def log_message(self, format: str, *args: Any) -> None:
        # Suppress standard noisy access logging; prism outputs clean colored logs
        pass

    def do_GET(self) -> None:
        if self.path == "/_mtime":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.end_headers()
            mtime_str = str(self.mtime_provider())
            self.wfile.write(mtime_str.encode("utf-8"))
            return

        # Serve primary HTML dashboard
        if self.path in {"/", "/index.html"}:
            try:
                html_bytes = self.html_provider()
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                err_html = f"<html><body><h2>500 Error Rendering Plot</h2><pre>{e}</pre></body></html>"
                self.wfile.write(err_html.encode("utf-8"))
                return

            # Inject the auto-reload script
            if b"</body>" in html_bytes:
                content = html_bytes.replace(b"</body>", AUTO_RELOAD_SNIPPET + b"</body>")
            else:
                content = html_bytes + AUTO_RELOAD_SNIPPET

            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.end_headers()
            self.wfile.write(content)
            return

        # 404 for unknown routes
        self.send_response(404)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"404 Not Found")


class PreviewServer:
    """Manages compilation, live file watching, and HTTP preview serving."""

    def __init__(
        self,
        target_path: str | Path,
        host: str = "127.0.0.1",
        port: int = 0,
        open_browser: bool = True,
    ) -> None:
        self.target_path = Path(target_path).resolve()
        self.host = host
        self.requested_port = port
        self.open_browser = open_browser

        self.is_python_script = self.target_path.suffix.lower() == ".py"
        self._current_html_bytes: bytes = b""
        self._current_mtime: float = 0.0
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._watcher_thread: threading.Thread | None = None
        self._httpd: HTTPServer | None = None
        self.actual_port: int = 0

    def compile_once(self) -> bool:
        """Compile the target script or read HTML file into memory."""
        if not self.target_path.exists():
            ui.error(f"Target does not exist: {self.target_path}")
            return False

        try:
            if self.is_python_script:
                result = run_script(self.target_path)
                html_str = render_to_html_string(
                    result.figure,
                    title=f"Prism Preview - {self.target_path.name}",
                )
                raw_bytes = html_str.encode("utf-8")
                with self._lock:
                    self._current_html_bytes = raw_bytes
                    self._current_mtime = time.time()
                return True
            else:
                # Existing HTML file
                with open(self.target_path, "rb") as f:
                    raw_bytes = f.read()
                file_mtime = self.target_path.stat().st_mtime
                with self._lock:
                    self._current_html_bytes = raw_bytes
                    self._current_mtime = file_mtime
                return True
        except Exception as e:
            ui.error(f"Failed to render {self.target_path.name}: {e}")
            return False

    def _file_watcher_loop(self) -> None:
        """Poll the target file for modifications and trigger recompilation."""
        last_stat_mtime = 0.0
        try:
            if self.target_path.exists():
                last_stat_mtime = self.target_path.stat().st_mtime
        except Exception:
            pass

        while not self._stop_event.is_set():
            time.sleep(0.3)
            if not self.target_path.exists():
                continue

            try:
                current_stat_mtime = self.target_path.stat().st_mtime
                if current_stat_mtime > last_stat_mtime:
                    last_stat_mtime = current_stat_mtime
                    start_t = time.perf_counter()
                    success = self.compile_once()
                    elapsed_ms = (time.perf_counter() - start_t) * 1000.0
                    if success:
                        ui.success(
                            f"Recompiled {ui.bold(self.target_path.name)} {ui.dim(f'({elapsed_ms:.1f}ms)')}"
                        )
            except Exception:
                pass

    def get_html_bytes(self) -> bytes:
        with self._lock:
            return self._current_html_bytes

    def get_mtime(self) -> float:
        with self._lock:
            return self._current_mtime

    def start(self) -> None:
        """Launch compilation, start HTTP listener, open browser, and serve forever."""
        # Initial compilation
        ui.info(f"Preparing preview for {ui.bold(self.target_path.name)}...")
        if not self.compile_once():
            ui.warn("Initial compilation had errors; server will continue waiting for file fixes.")

        # Configure HTTP handler
        LiveReloadHTTPHandler.html_provider = self.get_html_bytes
        LiveReloadHTTPHandler.mtime_provider = self.get_mtime
        LiveReloadHTTPHandler.target_path = self.target_path

        # Bind HTTP server
        try:
            self._httpd = HTTPServer((self.host, self.requested_port), LiveReloadHTTPHandler)
        except OSError as e:
            ui.error(f"Failed to bind HTTP server to {self.host}:{self.requested_port} - {e}")
            sys.exit(1)

        self.actual_port = self._httpd.server_address[1]
        url = f"http://{self.host}:{self.actual_port}"

        # Start watcher thread
        self._watcher_thread = threading.Thread(
            target=self._file_watcher_loop,
            name="prism-file-watcher",
            daemon=True,
        )
        self._watcher_thread.start()

        # Banner output matching Frost conventions
        print()
        print(f" {ui.badge()} {ui.bold('Live-Reloading Preview Server Active')}")
        print(f"   {ui.blue('Target:')}  {self.target_path}")
        print(f"   {ui.blue('URL:')}     {ui.cyan(url)}")
        print(f"   {ui.dim('Press Ctrl+C to stop.')}")
        print()

        # Open browser
        if self.open_browser:
            try:
                webbrowser.open(url)
            except Exception:
                pass

        # Clean shutdown handler
        def _handle_shutdown(signum: int, frame: Any) -> None:
            self.stop()
            print()
            ui.info("Preview server shut down cleanly.")
            sys.exit(0)

        signal.signal(signal.SIGINT, _handle_shutdown)
        signal.signal(signal.SIGTERM, _handle_shutdown)

        try:
            self._httpd.serve_forever()
        except KeyboardInterrupt:
            _handle_shutdown(0, None)

    def stop(self) -> None:
        """Stop watcher thread and shut down HTTP server."""
        self._stop_event.set()
        if self._httpd:
            # shutdown() must be called from a different thread or before close
            threading.Thread(target=self._httpd.shutdown, daemon=True).start()
            self._httpd.server_close()
