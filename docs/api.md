# Configuration & API Reference

Barograph is designed as both a command-line tool and an in-process Python library for conductors like Glaze and Lantern.

---

## Python Library API

Import Barograph directly inside Python workflows:

```python
from pathlib import Path
from barograph import (
    run_script,
    export_figure,
    discover_plot_scripts,
    extract_figure_from_module,
    detect_backend,
    ExecutionResult,
    ExportResult,
)
```

### `run_script`

Executes a standalone plotting script in an isolated namespace and extracts the figure.

```python
def run_script(
    script_path: Path | str,
    timeout_seconds: float = 30.0,
) -> ExecutionResult:
    """Executes a Python plotting script and extracts the generated figure.
    
    Args:
        script_path: Absolute or relative path to the Python script.
        timeout_seconds: Maximum allowed runtime before aborting.
        
    Returns:
        ExecutionResult: Dataclass containing the figure, backend, timing, and metadata.
        
    Raises:
        FileNotFoundError: If script does not exist.
        FigureNotFoundError: If no figure could be detected.
        ScriptExecutionError: If script raises an unhandled exception.
    """
```

### `export_figure`

Exports an extracted figure object to a target format.

```python
def export_figure(
    figure: any,
    output_path: Path | str,
    source_script: Path | str | None = None,
    target_format: str = "html",
    title: str | None = None,
    dpi: int = 300,
) -> ExportResult:
    """Exports a figure object to HTML, SVG, PDF, PNG, or WebP.
    
    Args:
        figure: The root figure object (Plotly Figure, Matplotlib Figure, etc.).
        output_path: Destination file path.
        source_script: Optional source script path for error reporting.
        target_format: Desired format: 'html', 'svg', 'pdf', 'png', or 'webp'.
        title: Optional plot title to embed in HTML or metadata.
        dpi: Resolution for raster output.
        
    Returns:
        ExportResult: Dataclass containing output path, format, file size, and degradation status.
    """
```

### `discover_plot_scripts`

Scans a directory for matching plotting scripts.

```python
def discover_plot_scripts(
    directory: Path | str,
    pattern: str = "plot*.py",
    recursive: bool = False,
) -> list[Path]:
    """Scans filesystem for plotting scripts matching the pattern."""
```

---

## Structured Types and Dataclasses

### `ExecutionResult`

```python
@dataclass
class ExecutionResult:
    script_path: Path
    figure: any
    backend: str              # 'plotly', 'matplotlib', 'seaborn', 'altair', 'bokeh'
    execution_time_ms: float
    metadata: dict[str, any]  # 'title', 'description', 'docstring'
    stdout: str
    stderr: str
```

### `ExportResult`

```python
@dataclass
class ExportResult:
    output_path: Path
    target_format: str
    file_size_bytes: int
    degraded: bool            # True if e.g. Matplotlib was degraded from HTML to SVG
    backend: str
```

---

## Nix and Home Manager

### Flake Input Declaration

```nix
{
  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
    barograph.url = "github:SpanishSyntax/Barograph";
    barograph.inputs.nixpkgs.follows = "nixpkgs";
  };
}
```

### Home Manager Configuration

```nix
{
  programs.barograph = {
    enable = true;
  };
}
```
