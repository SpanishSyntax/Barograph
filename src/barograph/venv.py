"""Virtual environment detection and auto-activation protocol for Barograph."""

from __future__ import annotations

import importlib
import os
from dataclasses import dataclass
from pathlib import Path
import site
import sys


@dataclass
class VenvInfo:
    """Encapsulates information about a discovered virtual environment."""

    root: Path
    site_packages: Path | None
    detected_python_version: str | None
    is_compatible: bool
    is_active: bool = False


def _parse_pyvenv_version(cfg_path: Path) -> str | None:
    """Attempt to parse Python version from pyvenv.cfg."""
    try:
        if not cfg_path.is_file():
            return None
        text = cfg_path.read_text(encoding="utf-8", errors="replace")
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("version_info"):
                parts = line.split("=", 1)
                if len(parts) == 2:
                    return parts[1].strip()
            elif line.startswith("version"):
                parts = line.split("=", 1)
                if len(parts) == 2:
                    return parts[1].strip()
    except Exception:
        pass
    return None


def find_workspace_venv(start_path: str | Path = ".") -> VenvInfo | None:
    """Discover a virtual environment relative to start_path or via VIRTUAL_ENV.

    Checks:
      1. os.environ['VIRTUAL_ENV']
      2. Walking up from start_path checking for .venv or venv directories.
    """
    candidates: list[Path] = []

    # 1. Check environment variable
    env_venv = os.environ.get("VIRTUAL_ENV")
    if env_venv:
        p = Path(env_venv).resolve()
        if p.is_dir():
            candidates.append(p)

    # 2. Walk up directory hierarchy
    try:
        resolved_start = Path(start_path).resolve()
        if resolved_start.is_file():
            curr = resolved_start.parent
        else:
            curr = resolved_start

        while True:
            for venv_name in (".venv", "venv"):
                v_path = curr / venv_name
                if v_path.is_dir() and v_path not in candidates:
                    candidates.append(v_path)
            parent = curr.parent
            if parent == curr:
                break
            curr = parent
    except Exception:
        pass

    host_major = sys.version_info.major
    host_minor = sys.version_info.minor
    host_ver = f"{host_major}.{host_minor}"

    for venv_root in candidates:
        pyvenv_cfg = venv_root / "pyvenv.cfg"
        cfg_ver = _parse_pyvenv_version(pyvenv_cfg)

        # Look for site-packages
        target_sp: Path | None = None
        detected_ver: str | None = cfg_ver
        is_compatible = False

        # POSIX layout
        lib_dir = venv_root / "lib"
        if lib_dir.is_dir():
            matching_lib = lib_dir / f"python{host_ver}" / "site-packages"
            if matching_lib.is_dir():
                target_sp = matching_lib
                is_compatible = True
                detected_ver = host_ver
            else:
                # Find other pythonX.Y dirs
                for sub in lib_dir.iterdir():
                    if sub.is_dir() and sub.name.startswith("python"):
                        sp = sub / "site-packages"
                        if sp.is_dir():
                            target_sp = sp
                            detected_ver = sub.name.replace("python", "")
                            is_compatible = (detected_ver == host_ver)
                            break

        # Windows layout fallback
        if target_sp is None:
            win_sp = venv_root / "Lib" / "site-packages"
            if win_sp.is_dir():
                target_sp = win_sp
                # If cfg_ver matches host minor or is empty, assume compatible
                if cfg_ver:
                    is_compatible = cfg_ver.startswith(host_ver)
                else:
                    is_compatible = True

        if target_sp is not None:
            return VenvInfo(
                root=venv_root,
                site_packages=target_sp,
                detected_python_version=detected_ver,
                is_compatible=is_compatible,
            )

    return None


def activate_workspace_venv(start_path: str | Path = ".") -> VenvInfo | None:
    """Discover and activate a compatible workspace virtualenv into sys.path.

    Uses site.addsitedir() to ensure .pth files and package directories are
    properly hooked. Invalidates importlib caches so newly exposed packages
    are immediately visible.
    """
    info = find_workspace_venv(start_path)
    if info is None or not info.is_compatible or info.site_packages is None:
        return info

    sp_str = str(info.site_packages)
    if sp_str not in sys.path:
        site.addsitedir(sp_str)
        # Position site-packages ahead of standard library / host packages
        if sp_str in sys.path:
            sys.path.remove(sp_str)
            # Insert after current directory or script directory (index 0)
            sys.path.insert(1 if len(sys.path) > 1 else 0, sp_str)
        importlib.invalidate_caches()

    if "VIRTUAL_ENV" not in os.environ:
        os.environ["VIRTUAL_ENV"] = str(info.root)

    info.is_active = True
    return info
