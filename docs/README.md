<p align="center">
  <img src="assets/banner.png" alt="Antique precision barograph instrument with rotating recording chart drum and pen linkage" width="100%" />
</p>

# Barograph 📈

> Pure Figure Extraction & Multi-Backend Batch Export Engine

Barograph is a lean, Unix-focused plot execution and figure export engine designed for the Frost ecosystem. It executes standalone Python plotting scripts (`plot_*.py`), detects figure objects across multiple rendering backends without boilerplate, batch-exports to interactive HTML and publication-grade vector/raster formats, and exposes a clean, first-class Python library interface for conductor tools.

---

## Why "Barograph"? (The Lore)

> **barograph** (`/ˈbær.ə.ɡræf/`) — *noun:* A recording barometer that continuously charts atmospheric pressure variations on a revolving drum, alerting polar navigators to incoming arctic fronts and pressure drops before the blizzard hits.

On polar expeditions, weather changes violently and without warning. Navigators cannot afford to guess at atmospheric gradients; they rely on the barograph's needle to register microscopic pressure fluctuations before the whiteout descends.

Barograph acts as the plotting and telemetry needle:
- **Pure Recording**: Executes standalone plotting scripts without runtime ceremony, capturing figures across Matplotlib, Seaborn, Plotly, Altair, and Bokeh backends.
- **Storm-Proof Export**: Batch-exports figures to publication-grade vector formats and interactive HTML canvases with deterministic, repeatable precision.

---

## Core Features

- **Zero-Boilerplate Figure Detection**: Automatically extracts target figures from standalone scripts:
  - `fig` / `figure` module-level attributes
  - `config.fig` (`flaker` `PlotConfigurator` native integration)
  - `plot()` / `main()` callable functions
  - Active `matplotlib.pyplot` figure stack (`plt.get_fignums()`)
  - Duck-typed exported module symbols
- **Multi-Backend Support**:
  - **Plotly**: Standalone HTML compilation with CDN runtime and static vector/raster export via Kaleido.
  - **Matplotlib**: Vector SVG/PDF and high-resolution raster PNG/WebP exports.
  - **Seaborn**: Unwraps `Axes`, `FacetGrid`, and `PairGrid` objects to root figures.
  - **Altair & Bokeh**: Interactive HTML and static image export support.
- **Multi-Backend Batch Rendering**: Compiles entire directories of standalone plotting scripts in a single fast pass with format degradation fallbacks.
- **First-Class Python Library API**: Direct in-process execution and extraction without shelling out, returning structured `ExecutionResult` dataclasses with execution timing and extracted metadata.
- **Model Context Protocol (MCP)**: Native stdio server exposing plot execution, batch compilation, and figure discovery tools to AI agents.

---

## Supported Backends

| Backend | Primary Artifacts | Dynamic Detection | Fallback Behavior |
| :--- | :--- | :--- | :--- |
| **Plotly** | HTML, SVG, PDF, PNG, WebP | `plotly.graph_objects.Figure` | Uses Kaleido for vector/raster export |
| **Matplotlib** | SVG, PDF, PNG, WebP | `matplotlib.figure.Figure`, `plt.gcf()` | Degrades from HTML to SVG |
| **Seaborn** | SVG, PDF, PNG, WebP | `FacetGrid`, `PairGrid`, `AxesSubplot` | Automatically extracts root canvas |
| **Altair / Bokeh** | HTML, SVG, PNG | Top-level Chart / Model objects | Generates standalone HTML runtime |

---

## Quick Navigation

- [Getting Started](getting-started.md): Installation options via Nix or pip, environment setup, and first figure export.
- [Architecture & Pipeline](architecture.md): Deep-dive into execution scoping, figure detection priority, and exporter backends.
- [CLI Reference & Recipes](usage.md): Command flags, batch export recipes, script discovery, and telemetry.
- [Configuration & API Reference](api.md): Programmatic Python API, dataclass specifications, and Nix modules.
