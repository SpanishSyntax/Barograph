"""Unit tests for Barograph CLI commands and argument routing."""

from __future__ import annotations

from pathlib import Path
import pytest

from barograph.cli import main


def test_cli_help(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["--help"])
    assert code == 0
    captured = capsys.readouterr()
    assert "Usage:" in captured.out
    assert "barograph build" in captured.out


def test_cli_version(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["--version"])
    assert code == 0
    captured = capsys.readouterr()
    assert "barograph 0.1.0" in captured.out


def test_cli_list(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "plot_alpha.py").write_text("fig = 1")
    (tmp_path / "plot_beta.py").write_text("fig = 2")

    code = main(["list", "-d", str(tmp_path)])
    assert code == 0
    captured = capsys.readouterr()
    assert "plot_alpha.py" in captured.out
    assert "plot_beta.py" in captured.out


def test_cli_build_success(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    # Create two valid plotting scripts
    (tmp_path / "plot_one.py").write_text("""
class MockFig:
    def write_html(self, path, **kwargs):
        with open(path, "w") as f:
            f.write("<html>Plot 1</html>")
    def to_plotly_json(self):
        return {}
fig = MockFig()
""")

    dist_dir = tmp_path / "dist"
    code = main(["build", "-d", str(tmp_path), "-o", str(dist_dir), "-f", "html"])
    assert code == 0
    assert (dist_dir / "plot_one.html").is_file()
    assert "Plot 1" in (dist_dir / "plot_one.html").read_text()


def test_cli_build_matplotlib_graceful_degradation(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Matplotlib script
    (tmp_path / "plot_mpl.py").write_text("""
class MockFig:
    def savefig(self, path, **kwargs):
        with open(path, "w") as f:
            f.write("<svg>Plot Matplotlib</svg>")
fig = MockFig()
""")

    dist_dir = tmp_path / "dist"
    code = main(["build", "-d", str(tmp_path), "-o", str(dist_dir), "-f", "html"])
    assert code == 0
    # Must degrade to .svg
    assert (dist_dir / "plot_mpl.svg").is_file()
    captured = capsys.readouterr()
    assert "gracefully degraded to SVG" in captured.out


def test_cli_build_with_failure(tmp_path: Path) -> None:
    (tmp_path / "plot_broken.py").write_text("raise RuntimeError('Boom!')")
    dist_dir = tmp_path / "dist"
    code = main(["build", "-d", str(tmp_path), "-o", str(dist_dir)])
    assert code == 1
