# Getting Started

Barograph executes standalone Python plot scripts and exports publication-grade figures without requiring framework boilerplate or proprietary base classes.

---

## Installation

### Nix Flake (Recommended)

Barograph is natively packaged as a Nix Flake bundling Python 3.12, Matplotlib, Plotly, and Prism styling:

```bash
# Run Barograph directly without installation
nix run github:SpanishSyntax/Barograph -- status

# Enter an interactive dev shell
nix shell github:SpanishSyntax/Barograph
```

To add Barograph to your system flake inputs:

```nix
{
  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
    barograph = {
      url = "github:SpanishSyntax/Barograph";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = { self, nixpkgs, barograph, ... }: {
    homeConfigurations."usurper" = home-manager.lib.homeManagerConfiguration {
      modules = [
        barograph.homeManagerModules.default
        {
          programs.barograph.enable = true;
        }
      ];
    };
  };
}
```

### Python Package (pip / uv)

Barograph can also be installed as a standard Python package:

```bash
# Install with uv
uv tool install git+https://github.com/SpanishSyntax/Barograph.git

# Install with pip
pip install git+https://github.com/SpanishSyntax/Barograph.git
```

---

## Prerequisites and Environments

Barograph requires Python 3.10 or higher. For rendering static vector formats from Plotly (`svg`, `pdf`), `kaleido` is recommended:

| Backend | Core Requirement | Optional Exporter Extras |
| :--- | :--- | :--- |
| **Plotly** | `plotly >= 5.0` | `kaleido >= 0.2.1` for SVG/PDF vector output |
| **Matplotlib** | `matplotlib >= 3.6` | `Pillow` for PNG/WebP raster export |
| **Seaborn** | `seaborn >= 0.12` | Unwraps to underlying Matplotlib |

To verify detected backends and Python environment:

```bash
barograph status
```

---

## Quick Start

### 1. Write a Standalone Plot Script

Create `plot_trajectory.py`. Notice there is zero framework ceremony—define a figure or assign `fig`:

```python
"""Optimal Descent Trajectory Simulation."""

import numpy as np
import plotly.graph_objects as go

t = np.linspace(0, 10, 200)
altitude = 100 * np.exp(-0.25 * t) * np.cos(t)

fig = go.Figure()
fig.add_trace(go.Scatter(x=t, y=altitude, mode="lines", name="Altitude (m)"))
fig.update_layout(
    title="Descent Trajectory Under Linear Drag",
    xaxis_title="Time (s)",
    yaxis_title="Altitude (m)",
    template="plotly_dark",
)
```

### 2. Export Figures via CLI

Export to standalone interactive HTML:

```bash
barograph build -d . -f html -o dist/
```

Or export to vector SVG for inclusion in Snowpack reports or academic papers:

```bash
barograph build -d . -f svg -o dist/figures/
```

---

## Figure Detection Protocol

Barograph finds your figure automatically by checking:
1. Module attributes `fig` or `figure`
2. Configuration object `config.fig`
3. Callables `plot()` or `main()` returning a figure
4. Open Matplotlib figures (`plt.get_fignums()`)
5. Duck-typed module exports matching common figure interfaces
