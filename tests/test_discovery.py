"""Unit tests for script discovery and target resolution."""

from __future__ import annotations

from pathlib import Path
import pytest

from prism.discovery import discover_scripts, is_ignored, resolve_target


def test_is_ignored() -> None:
    assert is_ignored(Path(".git/config"))
    assert is_ignored(Path("sub/.venv/bin/python"))
    assert is_ignored(Path(".direnv/bin"))
    assert not is_ignored(Path("src/plot_sim.py"))
    assert not is_ignored(Path("plot.py"))


def test_discover_scripts_flat(tmp_path: Path) -> None:
    # Setup test files
    (tmp_path / "plot_a.py").write_text("fig = 1")
    (tmp_path / "plot_b.py").write_text("fig = 2")
    (tmp_path / "helper.py").write_text("x = 10")
    (tmp_path / ".hidden_plot.py").write_text("fig = 3")

    results = discover_scripts(tmp_path)
    assert len(results) == 2
    assert [p.name for p in results] == ["plot_a.py", "plot_b.py"]


def test_discover_scripts_recursive(tmp_path: Path) -> None:
    (tmp_path / "plot_top.py").write_text("fig = 1")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "plot_nested.py").write_text("fig = 2")
    git = tmp_path / ".git"
    git.mkdir()
    (git / "plot_ignored.py").write_text("fig = 3")

    non_rec = discover_scripts(tmp_path, recursive=False)
    assert len(non_rec) == 1
    assert non_rec[0].name == "plot_top.py"

    rec = discover_scripts(tmp_path, recursive=True)
    assert len(rec) == 2
    names = {p.name for p in rec}
    assert names == {"plot_top.py", "plot_nested.py"}


def test_discover_scripts_single_file(tmp_path: Path) -> None:
    f = tmp_path / "plot_custom.py"
    f.write_text("fig = 1")
    results = discover_scripts(f)
    assert results == [f.resolve()]


def test_resolve_target_explicit(tmp_path: Path) -> None:
    f = tmp_path / "my_plot.py"
    f.write_text("fig = 1")

    resolved = resolve_target(f)
    assert resolved == f.resolve()

    with pytest.raises(FileNotFoundError):
        resolve_target(tmp_path / "non_existent.py")


def test_resolve_target_auto(tmp_path: Path) -> None:
    # 1. Default plot.py takes highest precedence
    plot_py = tmp_path / "plot.py"
    plot_py.write_text("fig = 1")
    plot_traj = tmp_path / "plot_traj.py"
    plot_traj.write_text("fig = 2")
    index_html = tmp_path / "index.html"
    index_html.write_text("<html></html>")

    assert resolve_target(base_dir=tmp_path) == plot_py.resolve()

    # 2. When plot.py is removed, plot_traj.py is selected
    plot_py.unlink()
    assert resolve_target(base_dir=tmp_path) == plot_traj.resolve()

    # 3. When scripts are removed, index.html is selected
    plot_traj.unlink()
    assert resolve_target(base_dir=tmp_path) == index_html.resolve()

    # 4. When nothing is present, FileNotFoundError is raised
    index_html.unlink()
    with pytest.raises(FileNotFoundError):
        resolve_target(base_dir=tmp_path)
