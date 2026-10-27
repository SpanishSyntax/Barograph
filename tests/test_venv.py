"""Unit tests for virtual environment discovery and auto-activation."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from barograph.runner import run_script
from barograph.venv import activate_workspace_venv, find_workspace_venv


def test_find_workspace_venv_none(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VIRTUAL_ENV", raising=False)
    assert find_workspace_venv(tmp_path) is None


def test_find_workspace_venv_from_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VIRTUAL_ENV", raising=False)

    host_ver = f"{sys.version_info.major}.{sys.version_info.minor}"
    venv_dir = tmp_path / ".venv"
    sp = venv_dir / "lib" / f"python{host_ver}" / "site-packages"
    sp.mkdir(parents=True)

    info = find_workspace_venv(tmp_path)
    assert info is not None
    assert info.root == venv_dir
    assert info.site_packages == sp
    assert info.is_compatible is True
    assert info.detected_python_version == host_ver


def test_find_workspace_venv_env_var(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    host_ver = f"{sys.version_info.major}.{sys.version_info.minor}"
    venv_dir = tmp_path / "custom_env"
    sp = venv_dir / "lib" / f"python{host_ver}" / "site-packages"
    sp.mkdir(parents=True)

    monkeypatch.setenv("VIRTUAL_ENV", str(venv_dir))

    info = find_workspace_venv(tmp_path / "sub")
    assert info is not None
    assert info.root == venv_dir
    assert info.site_packages == sp
    assert info.is_compatible is True


def test_find_workspace_venv_mismatched_version(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VIRTUAL_ENV", raising=False)

    venv_dir = tmp_path / ".venv"
    sp = venv_dir / "lib" / "python2.7" / "site-packages"
    sp.mkdir(parents=True)

    info = find_workspace_venv(tmp_path)
    assert info is not None
    assert info.root == venv_dir
    assert info.site_packages == sp
    assert info.is_compatible is False
    assert info.detected_python_version == "2.7"


def test_activate_workspace_venv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VIRTUAL_ENV", raising=False)

    host_ver = f"{sys.version_info.major}.{sys.version_info.minor}"
    venv_dir = tmp_path / ".venv"
    sp = venv_dir / "lib" / f"python{host_ver}" / "site-packages"
    sp.mkdir(parents=True)

    # Create dummy package in mock venv site-packages
    dummy_pkg = sp / "my_mock_module.py"
    dummy_pkg.write_text("MAGIC_NUMBER = 42\n")

    info = activate_workspace_venv(tmp_path)
    assert info is not None
    assert info.is_compatible is True
    assert str(sp) in sys.path

    # Script importing the mock package
    script = tmp_path / "plot_venv_test.py"
    script.write_text(
        "import my_mock_module\n"
        "fig = f'magic_{my_mock_module.MAGIC_NUMBER}'\n"
    )

    res = run_script(script)
    assert res.figure == "magic_42"
