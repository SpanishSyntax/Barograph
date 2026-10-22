"""Dynamic script execution engine and figure detection protocol for Prism."""

from __future__ import annotations

import importlib.util
import os
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any


class FigureNotFoundError(Exception):
    """Raised when an executed script finishes without exporting or exposing a detectable figure."""

    pass


class ScriptExecutionError(Exception):
    """Raised when an executed script raises an unhandled exception."""

    def __init__(self, script_path: Path, original_exc: Exception, tb_text: str | None = None) -> None:
        self.script_path = script_path
        self.original_exc = original_exc
        self.tb_text = tb_text
        super().__init__(f"Error executing {script_path.name}: {original_exc}")


@dataclass
class ExecutionResult:
    """Encapsulates the output of executing a standalone plotting script."""

    script_path: Path
    figure: Any
    backend: str
    execution_time_ms: float
    module: ModuleType


def detect_backend(fig: Any) -> str:
    """Identify the rendering backend for a given figure object."""
    type_name = type(fig).__name__
    mod_name = type(fig).__module__

    if "plotly" in mod_name or hasattr(fig, "write_html") and hasattr(fig, "to_plotly_json"):
        return "plotly"

    if "matplotlib" in mod_name or type_name == "Figure" and hasattr(fig, "savefig"):
        return "matplotlib"

    if "seaborn" in mod_name or "FacetGrid" in type_name or "PairGrid" in type_name:
        return "seaborn"

    # Fallback duck-typing
    if hasattr(fig, "write_html"):
        return "plotly"
    if hasattr(fig, "savefig"):
        return "matplotlib"

    return "generic"


def unwrap_figure(obj: Any) -> Any:
    """Unwrap container objects (Seaborn Grids, Matplotlib Axes, PlotConfigurators) to root Figure."""
    if obj is None:
        return None

    # Handle PlotConfigurator instance (from flaker MathVis template)
    if hasattr(obj, "fig") and not hasattr(obj, "savefig") and hasattr(obj.fig, "write_html"):
        return obj.fig

    # Handle Seaborn FacetGrid, PairGrid, JointGrid
    if hasattr(obj, "figure") and hasattr(obj.figure, "savefig"):
        return obj.figure
    if hasattr(obj, "fig") and hasattr(obj.fig, "savefig"):
        return obj.fig

    # Handle raw Matplotlib Axes
    if hasattr(obj, "get_figure") and callable(obj.get_figure):
        fig = obj.get_figure()
        if fig is not None:
            return fig

    return obj


def inspect_matplotlib_stack() -> Any:
    """Check active matplotlib.pyplot figure stack if imported and non-empty."""
    if "matplotlib.pyplot" not in sys.modules:
        return None

    try:
        import matplotlib.pyplot as plt

        fignums = plt.get_fignums()
        if fignums:
            # Pick the most recently created active figure
            return plt.figure(fignums[-1])
    except Exception:
        pass

    return None


def extract_figure_from_module(module: ModuleType) -> Any:
    """Apply the Prism Figure Detection Protocol in prioritized order.

    Protocol:
      1. Check module.fig or module.figure
      2. Check module.config.fig (PlotConfigurator support)
      3. Check callable module.plot() -> Figure
      4. Check callable module.main() -> Figure
      5. Fallback: inspect active matplotlib.pyplot figure stack (plt.get_fignums())
      6. Inspect module attributes for any figure-like objects with .write_html or .savefig
    """
    # 1. Check module.fig / module.figure
    if hasattr(module, "fig"):
        fig = getattr(module, "fig")
        unwrapped = unwrap_figure(fig)
        if unwrapped is not None:
            return unwrapped

    if hasattr(module, "figure"):
        fig = getattr(module, "figure")
        unwrapped = unwrap_figure(fig)
        if unwrapped is not None:
            return unwrapped

    # 2. Check module.config.fig (standard Frost MathVis PlotConfigurator)
    if hasattr(module, "config") and hasattr(getattr(module, "config"), "fig"):
        unwrapped = unwrap_figure(getattr(module, "config").fig)
        if unwrapped is not None:
            return unwrapped

    # 3. Check callable module.plot()
    if hasattr(module, "plot") and callable(getattr(module, "plot")):
        try:
            fig = module.plot()
            unwrapped = unwrap_figure(fig)
            if unwrapped is not None:
                return unwrapped
        except Exception:
            pass

    # 4. Check callable module.main()
    if hasattr(module, "main") and callable(getattr(module, "main")):
        try:
            fig = module.main()
            unwrapped = unwrap_figure(fig)
            if unwrapped is not None:
                return unwrapped
        except Exception:
            pass

    # 5. Fallback to Matplotlib figure stack
    mpl_fig = inspect_matplotlib_stack()
    if mpl_fig is not None:
        return mpl_fig

    # 6. Scan exported public module symbols for duck-typed figure
    for name, val in vars(module).items():
        if name.startswith("_"):
            continue
        unwrapped = unwrap_figure(val)
        if unwrapped is not None and (hasattr(unwrapped, "write_html") or hasattr(unwrapped, "savefig")):
            return unwrapped

    return None


def run_script(
    script_path: str | Path,
    clear_matplotlib_stack: bool = True,
) -> ExecutionResult:
    """Execute a standalone plotting script in an isolated scope and extract the figure.

    Args:
        script_path: Path to the target Python script.
        clear_matplotlib_stack: Whether to clear matplotlib figures before execution.

    Returns:
        ExecutionResult containing the figure, backend, and timing.

    Raises:
        FileNotFoundError: If script does not exist.
        ScriptExecutionError: If script execution fails with an unhandled exception.
        FigureNotFoundError: If no figure could be detected by the protocol.
    """
    path = Path(script_path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Plot script not found: {path}")

    # Prepare isolated environment
    script_dir = str(path.parent)
    original_sys_path = list(sys.path)
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)

    # Optionally close existing matplotlib figures to isolate stack
    if clear_matplotlib_stack and "matplotlib.pyplot" in sys.modules:
        try:
            import matplotlib.pyplot as plt

            plt.close("all")
        except Exception:
            pass

    module_name = f"_prism_exec_{path.stem}_{uuid.uuid4().hex[:8]}"
    spec = importlib.util.spec_from_file_location(module_name, str(path))
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module spec for {path}")

    module = importlib.util.module_from_spec(spec)
    # Set __file__ and run with standard name
    module.__file__ = str(path)

    start_time = time.perf_counter()
    try:
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
    except Exception as exc:
        import traceback

        tb_text = traceback.format_exc()
        raise ScriptExecutionError(path, exc, tb_text) from exc
    finally:
        # Restore sys.path
        sys.path = original_sys_path

    elapsed_ms = (time.perf_counter() - start_time) * 1000.0

    # Extract figure using protocol
    figure = extract_figure_from_module(module)

    if figure is None:
        raise FigureNotFoundError(
            f"No figure detected in '{path.name}'.\n"
            "Ensure the script satisfies at least one protocol rule:\n"
            "  1. Assigns to `fig` or `figure` (e.g. `fig = go.Figure(...)`)\n"
            "  2. Assigns `config = PlotConfigurator()`\n"
            "  3. Defines a callable `plot() -> Figure` or `main() -> Figure`\n"
            "  4. Calls `plt.plot(...)` or `plt.figure()` in Matplotlib/Seaborn"
        )

    backend = detect_backend(figure)

    return ExecutionResult(
        script_path=path,
        figure=figure,
        backend=backend,
        execution_time_ms=elapsed_ms,
        module=module,
    )
