# CLI & Recipes

Barograph provides subcommands and flags for batch compilation, filesystem discovery, system telemetry, and agent automation.

---

## Command Reference

The primary binary is `barograph`:

```text
Usage:
  barograph                              Open interactive status dashboard & quick actions
  barograph status                       Display host, runtime, backends & script dashboard
  barograph menu                         Open interactive Quick Actions menu
  barograph build [options]              Batch execute and export standalone plotting scripts
  barograph list [options]               Discover and inspect local plotting scripts
  barograph mcp                          Run Model Context Protocol stdio server

Build Options:
  -d, --dir DIR          Source directory containing plot scripts (default: current directory)
  -o, --out DIR          Target export directory (default: ./dist)
  -f, --format FMT       Target format: html, svg, png, pdf, webp (default: html)
  -p, --pattern PAT      Script filename glob pattern (default: plot*.py)
  -r, --recursive        Scan subdirectories recursively
  -a, --all              Include all matching scripts regardless of depth

List Options:
  -d, --dir DIR          Source directory to inspect (default: current directory)
  -p, --pattern PAT      Script filename glob pattern (default: plot*.py)
  -r, --recursive        Scan subdirectories recursively

General Options:
  --color MODE           Color output mode: auto, always, never (default: auto)
  --no-color             Disable colored output
  -v, --verbose          Show detailed error traces and internal execution timings
  -A, --agent            Machine/agent-friendly output mode
  --json                 Output structured JSON payloads
  -h, --help             Show help message and exit
  -V, --version          Show version information and exit
```

---

## Batch Export Recipes

### Export to Interactive HTML

Compile all `plot_*.py` files in the current directory into standalone HTML:

```bash
barograph build -d ./simulations -o ./dist/html -f html
```

### Export to Vector SVG for Snowpack / Typst

Compile scripts to vector SVG format:

```bash
barograph build -d ./simulations -o ./dist/svg -f svg
```

### Export High-Resolution Raster PNGs

Generate 300 DPI raster images for slide decks or presentations:

```bash
barograph build -d ./simulations -o ./dist/png -f png
```

### Recursive Directory Scan

Compile all scripts matching a custom glob pattern across nested experiment folders:

```bash
barograph build -d ./experiments -p "exp_*_plot.py" --recursive -o ./dist
```

---

## Script Inspection

Discover and preview plotting scripts in a project directory without executing them:

```bash
barograph list -d ./experiments
```

Sample output:

```text
╭── Discovered Plot Scripts (3 found) ──────────────────────────────╮
│  Path                           Backend    Title                  │
│ ───────────────────────────────────────────────────────────────── │
│  experiments/plot_loss.py       matplotlib Loss Curve Progression │
│  experiments/plot_surface.py    plotly     Rosenbrock Landscape   │
│  experiments/plot_pareto.py     seaborn    Multi-Objective Front  │
╰───────────────────────────────────────────────────────────────────╯
```

---

## System Telemetry

Inspect Python version, installed plotting libraries, and hardware environment:

```bash
barograph status
```

Machine-readable JSON telemetry:

```bash
barograph status --json
```

---

## Model Context Protocol (MCP)

Barograph exposes an MCP stdio server that enables autonomous agents to discover scripts, execute simulations, and export figures programmatically:

```bash
barograph mcp
```

Exposed MCP tools:
- `discover_plots`: Scans directories for standalone plotting scripts.
- `run_plot`: Executes an isolated script and returns figure metadata.
- `export_plot`: Renders a script to HTML, SVG, PDF, PNG, or WebP.
- `get_telemetry`: Inspects available backends and execution environments.
