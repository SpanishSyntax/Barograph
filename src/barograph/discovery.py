"""Script discovery and path resolution utilities for Barograph."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Sequence

IGNORE_DIRS = {
    ".git",
    ".direnv",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    "node_modules",
    "build",
    "dist",
    "result",
}


def is_ignored(path: Path) -> bool:
    """Check if any parent directory is in IGNORE_DIRS or starts with dot."""
    parts = path.parts
    for part in parts:
        if part in IGNORE_DIRS:
            return True
        if part.startswith(".") and part not in {".", ".."}:
            return True
    return False


def discover_scripts(
    path: str | Path = ".",
    pattern: str = "plot*.py",
    recursive: bool = False,
) -> list[Path]:
    """Discover Python plotting scripts matching pattern in path.

    Args:
        path: Directory to scan or single script file path.
        pattern: Glob pattern to match against (default: 'plot*.py').
        recursive: Whether to scan subdirectories recursively.

    Returns:
        List of absolute, sorted Path objects for matched scripts.
    """
    target = Path(path).resolve()

    if target.is_file():
        return [target]

    if not target.is_dir():
        raise FileNotFoundError(f"Target path does not exist: {target}")

    matched: list[Path] = []
    if recursive:
        for p in target.rglob(pattern):
            if p.is_file() and not is_ignored(p.relative_to(target)):
                matched.append(p.resolve())
    else:
        for p in target.glob(pattern):
            if p.is_file() and not p.name.startswith("."):
                matched.append(p.resolve())

    return sorted(matched)


# Public alias for first-class library API
discover_plot_scripts = discover_scripts


def resolve_target(
    target: str | Path | None = None,
    base_dir: str | Path = ".",
) -> Path:
    """Resolve a target plot script or HTML preview file.

    If target is explicitly provided, verify it exists.
    If target is None, smartly discover default candidates:
      1. `plot.py`
      2. First `plot*.py` script found in directory
      3. `index.html`

    Args:
        target: Optional file path or None.
        base_dir: Directory to search in when target is None.

    Returns:
        Resolved absolute Path to target file.

    Raises:
        FileNotFoundError: If no suitable target can be resolved.
    """
    base = Path(base_dir).resolve()

    if target is not None:
        p = Path(target)
        if not p.is_absolute():
            p = (base / p).resolve()
        if not p.exists():
            raise FileNotFoundError(f"Specified target not found: {p}")
        return p

    # 1. Check for interactive landing page dashboard.py
    candidate_dash = base / "dashboard.py"
    if candidate_dash.is_file():
        return candidate_dash.resolve()

    # 2. Check for standard plot.py
    candidate = base / "plot.py"
    if candidate.is_file():
        return candidate.resolve()

    # 3. Check for any plot*.py in base_dir
    scripts = discover_scripts(base, pattern="plot*.py", recursive=False)
    if scripts:
        return scripts[0]

    # 4. Check for index.html
    candidate_html = base / "index.html"
    if candidate_html.is_file():
        return candidate_html.resolve()

    raise FileNotFoundError(
        f"No plotting script (plot*.py) or HTML dashboard found in {base}."
    )


__all__ = [
    "discover_scripts",
    "discover_plot_scripts",
    "resolve_target",
    "is_ignored",
    "IGNORE_DIRS",
]
