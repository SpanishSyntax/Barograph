"""Barograph: Pure, fast figure extraction and multi-backend batch export engine."""

from __future__ import annotations

from barograph.discovery import discover_plot_scripts, discover_scripts, resolve_target
from barograph.exporter import ExportError, ExportResult, export_figure, render_to_html_string
from barograph.runner import (
    ExecutionResult,
    FigureNotFoundError,
    ScriptExecutionError,
    detect_backend,
    extract_figure_from_module,
    extract_title_from_figure,
    run_script,
)

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "run_script",
    "extract_figure_from_module",
    "detect_backend",
    "extract_title_from_figure",
    "export_figure",
    "render_to_html_string",
    "discover_plot_scripts",
    "discover_scripts",
    "resolve_target",
    "ExecutionResult",
    "ExportResult",
    "ExportError",
    "FigureNotFoundError",
    "ScriptExecutionError",
]
