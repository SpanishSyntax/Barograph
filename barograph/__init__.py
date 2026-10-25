"""Barograph: Universal batch runner, multi-backend export engine, and live-reloading preview server for Python plotting scripts."""

from __future__ import annotations

from barograph.discovery import discover_scripts, resolve_target
from barograph.exporter import export_figure
from barograph.runner import ExecutionResult, FigureNotFoundError, run_script

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "discover_scripts",
    "resolve_target",
    "run_script",
    "export_figure",
    "ExecutionResult",
    "FigureNotFoundError",
]
