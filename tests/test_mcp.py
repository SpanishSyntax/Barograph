"""Unit tests for Barograph native MCP stdio server."""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path
import pytest

from barograph.cli import main
from barograph.mcp import StdioMCPServer, TOOL_DEFINITIONS, execute_tool


def test_mcp_initialize() -> None:
    server = StdioMCPServer()
    req = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test-client", "version": "1.0"},
        },
    }
    resp = server.handle_request(req)
    assert resp is not None
    assert resp["id"] == 1
    assert resp["jsonrpc"] == "2.0"
    assert resp["result"]["protocolVersion"] == "2024-11-05"
    assert resp["result"]["serverInfo"]["name"] == "barograph"
    assert "tools" in resp["result"]["capabilities"]


def test_mcp_notifications_initialized() -> None:
    server = StdioMCPServer()
    req = {
        "jsonrpc": "2.0",
        "method": "notifications/initialized",
    }
    resp = server.handle_request(req)
    assert resp is None


def test_mcp_ping() -> None:
    server = StdioMCPServer()
    req = {"jsonrpc": "2.0", "id": 42, "method": "ping"}
    resp = server.handle_request(req)
    assert resp is not None
    assert resp["id"] == 42
    assert resp["result"] == {}


def test_mcp_tools_list() -> None:
    server = StdioMCPServer()
    req = {"jsonrpc": "2.0", "id": 100, "method": "tools/list"}
    resp = server.handle_request(req)
    assert resp is not None
    tools = resp["result"]["tools"]
    tool_names = [t["name"] for t in tools]
    assert "barograph_build" in tool_names
    assert "barograph_list" in tool_names

    build_def = next(t for t in tools if t["name"] == "barograph_build")
    assert "path" in build_def["inputSchema"]["properties"]
    assert "format" in build_def["inputSchema"]["properties"]
    assert "pattern" in build_def["inputSchema"]["properties"]
    assert "recursive" in build_def["inputSchema"]["properties"]
    assert "all_depths" in build_def["inputSchema"]["properties"]

    list_def = next(t for t in tools if t["name"] == "barograph_list")
    assert "path" in list_def["inputSchema"]["properties"]
    assert "pattern" in list_def["inputSchema"]["properties"]
    assert "recursive" in list_def["inputSchema"]["properties"]
    assert "all_depths" in list_def["inputSchema"]["properties"]


def test_mcp_execute_unknown() -> None:
    res = execute_tool("nonexistent_tool", {})
    assert res["status"] == "error"
    assert "Unknown tool" in res["error"]


def test_mcp_unknown_method() -> None:
    server = StdioMCPServer()
    req = {"jsonrpc": "2.0", "id": 999, "method": "nonexistent_method"}
    resp = server.handle_request(req)
    assert resp is not None
    assert "error" in resp
    assert resp["error"]["code"] == -32601


def test_mcp_list_scripts(tmp_path: Path) -> None:
    (tmp_path / "plot_1.py").write_text("fig = 1")
    (tmp_path / "plot_2.py").write_text("fig = 2")
    (tmp_path / "ignored.py").write_text("fig = 3")

    res = execute_tool("barograph_list", {"path": str(tmp_path), "pattern": "plot*.py"})
    assert res["status"] == "ok"
    assert res["count"] == 2
    names = {s["name"] for s in res["scripts"]}
    assert names == {"plot_1.py", "plot_2.py"}


def test_mcp_list_nonexistent_dir() -> None:
    res = execute_tool("barograph_list", {"path": "/path/does/not/exist/ever"})
    assert res["status"] == "error"
    assert "Path not found" in res["error"]


def test_mcp_build_scripts(tmp_path: Path) -> None:
    plot_file = tmp_path / "plot_test.py"
    plot_file.write_text("""
class MockFig:
    def write_html(self, path, **kwargs):
        with open(path, "w") as f:
            f.write("<html>Test Figure</html>")
    def to_plotly_json(self):
        return {}
fig = MockFig()
""")

    out_dir = tmp_path / "dist"
    res = execute_tool(
        "barograph_build",
        {
            "path": str(tmp_path),
            "out_dir": str(out_dir),
            "format": "html",
            "pattern": "plot*.py",
        },
    )

    assert res["status"] == "ok"
    assert res["succeeded"] == 1
    assert res["failed"] == 0
    assert len(res["artifacts"]) == 1
    artifact = res["artifacts"][0]
    assert artifact["format"] == "html"
    assert Path(artifact["output_file"]).is_file()
    assert "Test Figure" in Path(artifact["output_file"]).read_text()


def test_mcp_build_failure(tmp_path: Path) -> None:
    bad_file = tmp_path / "plot_bad.py"
    bad_file.write_text("raise ValueError('Intentional plot error')")

    res = execute_tool("barograph_build", {"path": str(tmp_path)})
    assert res["status"] == "error"
    assert res["failed"] == 1
    assert len(res["errors"]) == 1
    assert "Intentional plot error" in res["errors"][0]["error"]


def test_mcp_build_empty(tmp_path: Path) -> None:
    res = execute_tool("barograph_build", {"path": str(tmp_path), "pattern": "plot*.py"})
    assert res["status"] == "ok"
    assert res["total"] == 0
    assert res["artifacts"] == []


def test_mcp_build_nonexistent_dir() -> None:
    res = execute_tool("barograph_build", {"path": "/path/does/not/exist/ever"})
    assert res["status"] == "error"
    assert "Path not found" in res["error"]


def test_mcp_tools_call_rpc(tmp_path: Path) -> None:
    (tmp_path / "plot_demo.py").write_text("fig = 'demo'")
    server = StdioMCPServer()
    req = {
        "jsonrpc": "2.0",
        "id": 50,
        "method": "tools/call",
        "params": {
            "name": "barograph_list",
            "arguments": {"path": str(tmp_path)},
        },
    }
    resp = server.handle_request(req)
    assert resp is not None
    assert resp["id"] == 50
    assert resp["result"]["isError"] is False
    content_text = resp["result"]["content"][0]["text"]
    data = json.loads(content_text)
    assert data["status"] == "ok"
    assert data["count"] == 1
    assert data["scripts"][0]["name"] == "plot_demo.py"


def test_mcp_stdio_server_run(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    req = {
        "jsonrpc": "2.0",
        "id": 7,
        "method": "ping",
    }
    stdin_stream = io.StringIO(json.dumps(req) + "\n")
    monkeypatch.setattr(sys, "stdin", stdin_stream)

    server = StdioMCPServer()
    ret = server.run()
    assert ret == 0

    captured = capsys.readouterr()
    lines = [line for line in captured.out.splitlines() if line.strip()]
    assert len(lines) == 1
    resp = json.loads(lines[0])
    assert resp["id"] == 7
    assert resp["result"] == {}


def test_cli_mcp_subcommand(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))
    code = main(["mcp"])
    assert code == 0
