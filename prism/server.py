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


def render_error_page(script_name: str, error_msg: str, tb_text: str | None = None) -> str:
    """Generate a clean, Frost-themed in-browser error dashboard."""
    import html
    escaped_err = html.escape(error_msg)
    escaped_tb = html.escape(tb_text or "")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Error in {html.escape(script_name)}</title>
  <style>
    :root {{
      --bg: #0d1117;
      --card: #161b22;
      --border: #30363d;
      --danger: #f85149;
      --text: #c9d1d9;
      --dim: #8b949e;
      --code-bg: #030406;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace;
      padding: 2rem;
      display: flex;
      justify-content: center;
      align-items: flex-start;
      min-height: 100vh;
    }}
    .card {{
      background: var(--card);
      border: 1px solid var(--border);
      border-top: 4px solid var(--danger);
      border-radius: 8px;
      padding: 1.5rem;
      max-width: 900px;
      width: 100%;
      box-shadow: 0 12px 32px rgba(0,0,0,0.4);
    }}
    .header {{
      display: flex;
      align-items: center;
      gap: 0.75rem;
      margin-bottom: 1rem;
    }}
    .badge {{
      background: rgba(248, 81, 73, 0.15);
      color: var(--danger);
      font-size: 0.75rem;
      font-weight: 700;
      padding: 0.2rem 0.5rem;
      border-radius: 4px;
      border: 1px solid rgba(248, 81, 73, 0.3);
      text-transform: uppercase;
    }}
    h1 {{
      font-size: 1.25rem;
      color: #fff;
    }}
    .message {{
      color: var(--danger);
      font-size: 1rem;
      font-weight: 600;
      margin-bottom: 1rem;
      word-break: break-word;
    }}
    pre {{
      background: var(--code-bg);
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 1rem;
      color: #ff7b72;
      font-size: 0.85rem;
      line-height: 1.45;
      overflow-x: auto;
      white-space: pre-wrap;
    }}
    .hint {{
      margin-top: 1rem;
      font-size: 0.85rem;
      color: var(--dim);
    }}
  </style>
</head>
<body>
  <div class="card">
    <div class="header">
      <span class="badge">Prism Compile Error</span>
      <h1>{html.escape(script_name)}</h1>
    </div>
    <div class="message">{escaped_err}</div>
    {f'<pre>{escaped_tb}</pre>' if escaped_tb else ''}
    <div class="hint">Fix the issue in your editor — this page will automatically reload once saved.</div>
  </div>
</body>
</html>
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
        try:
            self._handle_get()
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _handle_get(self) -> None:
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
            tb = getattr(e, "tb_text", None)
            err_html = render_error_page(self.target_path.name, str(e), tb)
            with self._lock:
                self._current_html_bytes = err_html.encode("utf-8")
                self._current_mtime = time.time()
            return False

    def _compute_watch_mtime(self) -> float:
        """Compute the latest modification timestamp among the target script and local directory files."""
        latest = 0.0
        try:
            if self.target_path.exists():
                latest = self.target_path.stat().st_mtime
        except Exception:
            pass

        # Also watch sibling python or data files in target directory
        if self.is_python_script and self.target_path.parent.is_dir():
            try:
                for entry in self.target_path.parent.iterdir():
                    if entry.is_file() and entry.suffix in {".py", ".json", ".csv", ".tsv", ".yaml", ".toml", ".txt"}:
                        if not entry.name.startswith("."):
                            m = entry.stat().st_mtime
                            if m > latest:
                                latest = m
            except Exception:
                pass
        return latest

    def _file_watcher_loop(self) -> None:
        """Poll the target script and local directory for modifications and trigger recompilation."""
        last_mtime = self._compute_watch_mtime()

        while not self._stop_event.is_set():
            time.sleep(0.3)
            try:
                current_mtime = self._compute_watch_mtime()
                if current_mtime > last_mtime:
                    last_mtime = current_mtime
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
