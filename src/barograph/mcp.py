"""Model Context Protocol (MCP) server for Barograph."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from barograph import __version__
from barograph.discovery import discover_scripts
from barograph.exporter import export_figure
from barograph.runner import FigureNotFoundError, ScriptExecutionError, run_script
from barograph.venv import activate_workspace_venv

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "barograph_build",
        "description": "Batch executes standalone Python plotting scripts and exports figures to HTML, SVG, PNG, PDF, or WebP via Barograph.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory containing plotting scripts or single script path (default: '.').",
                    "default": ".",
                },
                "out_dir": {
                    "type": "string",
                    "description": "Target output directory for exported assets (default: './dist').",
                },
                "format": {
                    "type": "string",
                    "description": "Export format: html (default), svg, png, pdf, webp.",
                    "default": "html",
                },
                "pattern": {
                    "type": "string",
                    "description": "Script filename glob pattern (default: 'plot*.py').",
                    "default": "plot*.py",
                },
                "recursive": {
                    "type": "boolean",
                    "description": "Recursively search subdirectories for plot scripts (default: true).",
                    "default": True,
                },
                "all_depths": {
                    "type": "boolean",
                    "description": "Scan across all directory depths; alias for recursive (default: false).",
                    "default": False,
                },
            },
        },
    },
    {
        "name": "barograph_list",
        "description": "Lists and discovers Python plotting scripts in a directory matching a pattern via Barograph.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory to inspect (default: '.').",
                    "default": ".",
                },
                "pattern": {
                    "type": "string",
                    "description": "Script filename glob pattern (default: 'plot*.py').",
                    "default": "plot*.py",
                },
                "recursive": {
                    "type": "boolean",
                    "description": "Recursively search subdirectories (default: true).",
                    "default": True,
                },
                "all_depths": {
                    "type": "boolean",
                    "description": "Scan across all directory depths; alias for recursive (default: false).",
                    "default": False,
                },
            },
        },
    },
]


def execute_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Execute a Barograph MCP tool call and return JSON-serializable results."""
    try:
        if name == "barograph_build":
            path_str = arguments.get("path", ".")
            target = Path(path_str).resolve()
            if not target.exists():
                return {"status": "error", "error": f"Path not found: {target}"}

            pattern = arguments.get("pattern", "plot*.py")
            recursive = bool(
                arguments.get("recursive", True) or arguments.get("all_depths", False)
            )
            target_format = str(arguments.get("format", "html")).lower().lstrip(".")

            base_dir = target if target.is_dir() else target.parent
            try:
                activate_workspace_venv(base_dir)
            except Exception:
                pass

            scripts = discover_scripts(target, pattern=pattern, recursive=recursive)

            out_dir_val = arguments.get("out_dir")
            if out_dir_val:
                out_dir = Path(out_dir_val)
                if not out_dir.is_absolute():
                    out_dir = (base_dir / out_dir).resolve()
            else:
                out_dir = (base_dir / "dist").resolve()

            if not scripts:
                return {
                    "status": "ok",
                    "source_path": str(target),
                    "output_dir": str(out_dir),
                    "format": target_format,
                    "succeeded": 0,
                    "failed": 0,
                    "total": 0,
                    "artifacts": [],
                    "errors": [],
                    "message": f"No plot scripts matching '{pattern}' found in {target}",
                }

            out_dir.mkdir(parents=True, exist_ok=True)
            artifacts: list[dict[str, Any]] = []
            errors: list[dict[str, Any]] = []
            success_count = 0
            failure_count = 0

            for script in scripts:
                try:
                    res = run_script(script)
                    dest_file = out_dir / f"{script.stem}.{target_format}"
                    exp = export_figure(
                        figure=res.figure,
                        output_path=dest_file,
                        source_script=script,
                        target_format=target_format,
                        title=res.metadata.get("title"),
                    )
                    success_count += 1
                    artifacts.append(
                        {
                            "script": str(script),
                            "output_file": str(exp.output_path),
                            "format": exp.actual_format,
                            "backend": exp.backend,
                            "degraded": exp.degraded,
                            "degraded_reason": exp.degraded_reason,
                            "execution_time_ms": round(res.execution_time_ms, 2),
                        }
                    )
                except ScriptExecutionError as e:
                    failure_count += 1
                    errors.append(
                        {
                            "script": str(script),
                            "error": str(e.original_exc),
                        }
                    )
                except FigureNotFoundError as e:
                    failure_count += 1
                    errors.append(
                        {
                            "script": str(script),
                            "error": str(e),
                        }
                    )
                except Exception as e:
                    failure_count += 1
                    errors.append(
                        {
                            "script": str(script),
                            "error": str(e),
                        }
                    )

            status = "ok" if failure_count == 0 else "error"
            return {
                "status": status,
                "source_path": str(target),
                "output_dir": str(out_dir),
                "format": target_format,
                "succeeded": success_count,
                "failed": failure_count,
                "total": len(scripts),
                "artifacts": artifacts,
                "errors": errors,
            }

        elif name == "barograph_list":
            path_str = arguments.get("path", ".")
            target = Path(path_str).resolve()
            if not target.exists():
                return {"status": "error", "error": f"Path not found: {target}"}

            pattern = arguments.get("pattern", "plot*.py")
            recursive = bool(
                arguments.get("recursive", True) or arguments.get("all_depths", False)
            )

            scripts = discover_scripts(target, pattern=pattern, recursive=recursive)
            base_dir = target if target.is_dir() else target.parent
            items = [
                {
                    "file": str(s),
                    "name": s.name,
                    "relative": str(s.relative_to(base_dir))
                    if s.parent != base_dir
                    else s.name,
                    "size_bytes": s.stat().st_size,
                }
                for s in scripts
            ]
            return {
                "status": "ok",
                "target_dir": str(target),
                "count": len(items),
                "scripts": items,
            }

        else:
            return {"status": "error", "error": f"Unknown tool: {name}"}

    except Exception as e:
        return {"status": "error", "error": str(e)}


class StdioMCPServer:
    """JSON-RPC 2.0 stdio server implementing the Model Context Protocol."""

    def __init__(self) -> None:
        self.server_info = {"name": "barograph", "version": __version__}

    def handle_request(self, req: dict[str, Any]) -> dict[str, Any] | None:
        method = req.get("method")
        msg_id = req.get("id")

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "serverInfo": self.server_info,
                    "capabilities": {"tools": {}},
                },
            }

        elif method == "notifications/initialized":
            return None

        elif method == "ping":
            return {"jsonrpc": "2.0", "id": msg_id, "result": {}}

        elif method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {"tools": TOOL_DEFINITIONS},
            }

        elif method == "tools/call":
            params = req.get("params", {})
            name = params.get("name", "")
            args = params.get("arguments", {})
            res = execute_tool(name, args)
            is_error = res.get("status") == "error"

            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps(res, indent=2)}],
                    "isError": is_error,
                },
            }

        else:
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"},
            }

    def run(self) -> int:
        """Run JSON-RPC event loop reading lines from sys.stdin."""
        for line in sys.stdin:
            line_str = line.strip()
            if not line_str:
                continue
            try:
                req = json.loads(line_str)
                resp = self.handle_request(req)
                if resp is not None:
                    sys.stdout.write(json.dumps(resp) + "\n")
                    sys.stdout.flush()
            except Exception as e:
                err_resp = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": f"Parse error: {e}"},
                }
                sys.stdout.write(json.dumps(err_resp) + "\n")
                sys.stdout.flush()
        return 0


def main() -> int:
    """Entrypoint for barograph mcp command."""
    return StdioMCPServer().run()
