"""CLI argument router, command dispatcher, and terminal UX for Barograph."""

from __future__ import annotations

import argparse
import importlib.util
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Sequence

from barograph import __version__
from barograph.discovery import discover_scripts, resolve_target
from barograph.exporter import export_figure
from barograph.runner import FigureNotFoundError, ScriptExecutionError, run_script
from barograph.server import PreviewServer
from barograph.ui import (
    add_color_args,
    apply_color_args,
    handle_color_args,
    render_error_panel,
    render_panel,
    ui,
)
from barograph.venv import activate_workspace_venv, find_workspace_venv


def get_git_status(path: Path) -> str:
    """Return a brief git branch and clean/dirty status string."""
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=path,
            capture_output=True,
            text=True,
            timeout=1.0,
        )
        if res.returncode == 0:
            branch = res.stdout.strip()
            diff_res = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=path,
                capture_output=True,
                text=True,
                timeout=1.0,
            )
            is_clean = len(diff_res.stdout.strip()) == 0
            return f"{branch} ({'clean' if is_clean else 'dirty'})"
    except Exception:
        pass
    return "not a git repo"


def get_installed_backends() -> list[tuple[str, bool]]:
    """Detect available plotting library backends in the active Python environment."""
    return [
        ("plotly", importlib.util.find_spec("plotly") is not None),
        ("matplotlib", importlib.util.find_spec("matplotlib") is not None),
        ("seaborn", importlib.util.find_spec("seaborn") is not None),
        ("altair", importlib.util.find_spec("altair") is not None),
        ("bokeh", importlib.util.find_spec("bokeh") is not None),
    ]


def print_status_dashboard(base_dir: str | Path = ".") -> list[Path]:
    """Display an informative status dashboard panel matching Sled and Borealis."""
    ws = Path(base_dir).resolve()
    try:
        scripts = discover_scripts(ws, pattern="plot*.py", recursive=False)
    except Exception:
        scripts = []

    # Activate workspace virtual environment if available
    venv_info = activate_workspace_venv(ws)
    if venv_info is not None:
        if venv_info.is_compatible:
            env_status = f"{ui.bold_green('✔')} {venv_info.root.name} ({ui.green(f'Python {venv_info.detected_python_version}')})"
        else:
            env_status = f"{ui.bold_yellow('⚠')} {venv_info.root.name} ({ui.yellow(f'Python {venv_info.detected_python_version} - runtime is {platform.python_version()}')})"
    else:
        env_status = ui.dim("host runtime")

    host = platform.node() or "localhost"
    distro = f"{platform.system()} {platform.release()}"
    py_ver = f"Python {platform.python_version()}"
    git_info = get_git_status(ws)

    backends = get_installed_backends()
    backend_badges: list[str] = []
    for name, ok in backends:
        if ok:
            backend_badges.append(f"{ui.bold_green('✔')} {name}")
        else:
            backend_badges.append(f"{ui.dim('·')} {ui.dim(name)}")

    if scripts:
        script_names = ", ".join(s.name for s in scripts[:3])
        if len(scripts) > 3:
            script_names += f" (+{len(scripts) - 3} more)"
        scripts_display = (
            f"{ui.bold_green(str(len(scripts)))} detected ({ui.dim(script_names)})"
        )
    else:
        scripts_display = ui.dim("no plot scripts found (plot*.py)")

    lines = [
        f"{ui.bold('Engine Version:')}   {ui.bold_cyan(f'v{__version__}')} (Interactive Hub & Live Preview)",
        f"{ui.bold('Host & Runtime:')}   {host} — {distro} ({py_ver})",
        f"{ui.bold('Workspace Git:')}   {ws.name} ({ui.dim(git_info)})",
        f"{ui.bold('Environment:')}     {env_status}",
        f"{ui.bold('Plot Backends:')}   {'  '.join(backend_badges)}",
        f"{ui.bold('Target Scripts:')}  {scripts_display}",
        f"{ui.bold('Export Defaults:')} {ui.cyan('./dist')} (Formats: html, svg, png, pdf, webp)",
    ]

    ui.panel("BAROGRAPH PLOT RUNNER & PREVIEW SERVER", lines, border_color="0;35")
    return scripts


def run_interactive_menu(scripts: list[Path]) -> int:
    """Prompt the user with interactive startup actions matching Sled and Snowpack."""
    actions: list[tuple[str, str, str]] = []

    if scripts:
        primary = scripts[0]
        actions.append(
            (
                "serve",
                f"Start Live Preview Server ({primary.name})",
                "Launch live-reloading preview server with browser hot-reload",
            )
        )
        if len(scripts) > 1:
            actions.append(
                (
                    "serve-select",
                    "Select Script for Live Preview...",
                    f"Choose one of {len(scripts)} discovered plot scripts to preview",
                )
            )
        actions.append(
            (
                "build",
                f"Batch Build All Scripts ({len(scripts)} targets)",
                "Execute and export all discovered scripts to ./dist",
            )
        )
        actions.append(
            (
                "build-single",
                "Execute & Export Single Script...",
                "Select an individual script to run and export immediately",
            )
        )
    else:
        actions.append(
            (
                "serve",
                "Start Live Preview Server",
                "Launch preview server on plot.py or index.html",
            )
        )
        actions.append(
            (
                "build",
                "Batch Build All Scripts",
                "Scan workspace and export matching plot*.py scripts",
            )
        )

    actions.append(
        (
            "list",
            "Inspect Discovered Scripts",
            "List discovered plot scripts, file sizes, and paths",
        )
    )
    actions.append(
        ("exit", "Exit", "Close Barograph dashboard")
    )

    try:
        action = ui.select("Quick Actions:", actions)
    except KeyboardInterrupt:
        return 0

    if not action or action == "exit":
        return 0

    if action == "serve":
        target = str(scripts[0]) if scripts else None
        return cmd_serve(
            argparse.Namespace(
                target=target,
                port=0,
                host="127.0.0.1",
                no_open=False,
                verbose=False,
            )
        )

    if action == "serve-select":
        options = [
            (str(s), s.name, f"{s.stat().st_size / 1024.0:.1f} KB")
            for s in scripts
        ]
        chosen = ui.select("Select plot script for live preview:", options)
        if not chosen:
            return 0
        return cmd_serve(
            argparse.Namespace(
                target=chosen,
                port=0,
                host="127.0.0.1",
                no_open=False,
                verbose=False,
            )
        )

    if action == "build":
        return cmd_build(
            argparse.Namespace(
                dir=".",
                out="./dist",
                format="html",
                pattern="plot*.py",
                recursive=False,
                all=False,
                verbose=False,
            )
        )

    if action == "build-single":
        options = [
            (str(s), s.name, f"{s.stat().st_size / 1024.0:.1f} KB")
            for s in scripts
        ]
        chosen = ui.select("Select plot script to export:", options)
        if not chosen:
            return 0
        chosen_path = Path(chosen)
        fmt_options = [
            ("html", "Interactive HTML", "Standalone bundle (Plotly/generic) or SVG fallback"),
            ("svg", "Vector SVG", "Clean scalable vector graphic for papers / slides"),
            ("png", "Raster PNG", "High-resolution raster graphic"),
            ("pdf", "Vector PDF", "Portable Document Format for print / Typst"),
            ("webp", "WebP Image", "Modern compressed web image"),
        ]
        chosen_fmt = ui.select("Select export format:", fmt_options)
        return cmd_build(
            argparse.Namespace(
                dir=str(chosen_path.parent),
                out="./dist",
                format=chosen_fmt or "html",
                pattern=chosen_path.name,
                recursive=False,
                all=False,
                verbose=False,
            )
        )

    if action == "list":
        return cmd_list(
            argparse.Namespace(
                dir=".",
                pattern="plot*.py",
                recursive=False,
                all=False,
            )
        )

    return 0


def print_help() -> None:
    """Print colored usage instructions matching Flaker, Folio, Borealis, Glaze, and Firn."""
    print(f"""{ui.badge()} {ui.bold("Universal Plot Batch-Runner, Multi-Backend Exporter & Preview Server")}

{ui.blue("Usage:")}
  barograph                              Open interactive status dashboard & quick actions
  barograph status                       Display host, runtime, backends & script dashboard
  barograph build [options]              Batch execute and export standalone plotting scripts
  barograph serve [target] [options]     Live-reload preview server with browser sync
  barograph list [options]               Discover and inspect local plotting scripts
  barograph <command> [options]

{ui.blue("Interactive & Dashboard Commands:")}
  status                 Display live host, runtime, plot backends & script dashboard
  menu                   Open the interactive Quick Actions menu

{ui.blue("Build Options:")}
  -d, --dir DIR          Source directory containing plot scripts (default: current directory)
  -o, --out DIR          Target export directory (default: ./dist)
  -f, --format FMT       Target format: html, svg, png, pdf, webp (default: html)
  -p, --pattern PAT      Script filename glob pattern (default: plot*.py)
  -r, --recursive        Scan subdirectories recursively
  --all                  Include all matching scripts regardless of depth

{ui.blue("Serve Options:")}
  [target]               Script (e.g. plot_traj.py) or .html file (default: auto-detected)
  -p, --port PORT        Port to bind HTTP server to (default: 0 for ephemeral port)
  --host HOST            Host to bind HTTP server to (default: 127.0.0.1)
  --no-open              Do not automatically open the dashboard in browser

{ui.blue("General Options:")}
  --color MODE           Color output mode: auto, always, never (default: auto)
  --no-color             Disable colored output
  -v, --verbose          Show detailed error traces and internal execution timings
  -h, --help             Show this help message and exit
  -V, --version          Show version information and exit
""")


def cmd_build(args: argparse.Namespace) -> int:
    """Execute discovered plotting scripts and export to target format."""
    source_dir = Path(args.dir).resolve()
    out_dir = Path(args.out).resolve()
    target_format = args.format.lower().lstrip(".")
    recursive = getattr(args, "recursive", False) or getattr(args, "all", False)
    pattern = getattr(args, "pattern", "plot*.py")
    verbose = getattr(args, "verbose", False)

    try:
        scripts = discover_scripts(source_dir, pattern=pattern, recursive=recursive)
    except Exception as e:
        ui.error(f"Failed to scan directory {source_dir}: {e}")
        return 1

    if not scripts:
        ui.warn(f"No plot scripts matching '{pattern}' found in {source_dir}")
        return 0

    print(f"\n{ui.badge()} {ui.bold('Building Plot Assets')}")
    print(f"   {ui.blue('Source:')}  {source_dir}")
    print(f"   {ui.blue('Output:')}  {out_dir}")
    print(f"   {ui.blue('Format:')}  {ui.cyan(target_format)}")
    print(f"   {ui.blue('Scripts:')} {len(scripts)} detected\n")

    out_dir.mkdir(parents=True, exist_ok=True)

    success_count = 0
    failure_count = 0
    start_total = time.perf_counter()

    for script in scripts:
        rel_name = script.name if script.parent == source_dir else str(script.relative_to(source_dir))
        try:
            # 1. Execute script and extract figure
            res = run_script(script)

            # Determine export filename
            dest_file = out_dir / f"{script.stem}.{target_format}"

            # 2. Export figure via router
            exp = export_figure(
                figure=res.figure,
                output_path=dest_file,
                source_script=script,
                target_format=target_format,
            )

            success_count += 1
            timing_str = ui.dim(f"({res.execution_time_ms:.1f}ms)")
            backend_badge = ui.cyan(f"[{exp.backend}]")

            if exp.degraded:
                # Graceful degradation from HTML to SVG
                ui.warn(
                    f"Matplotlib figure detected in {ui.bold(rel_name)}: "
                    f"gracefully degraded to SVG -> {ui.yellow(exp.output_path.name)}"
                )
                print(
                    f"  \033[32m✓\033[0m {rel_name:<30} {backend_badge} -> {exp.output_path.name} {timing_str}"
                )
            else:
                print(
                    f"  \033[32m✓\033[0m {rel_name:<30} {backend_badge} -> {exp.output_path.name} {timing_str}"
                )

        except ScriptExecutionError as e:
            failure_count += 1
            ui.error(f"Failed executing {ui.bold(rel_name)}: {e.original_exc}")
            if verbose and e.tb_text:
                print(f"\033[31m{e.tb_text}\033[0m", file=sys.stderr)

        except FigureNotFoundError as e:
            failure_count += 1
            ui.error(f"No figure in {ui.bold(rel_name)}: {e}")

        except Exception as e:
            failure_count += 1
            ui.error(f"Error processing {ui.bold(rel_name)}: {e}")
            if verbose:
                import traceback
                traceback.print_exc()

    total_sec = time.perf_counter() - start_total
    print()
    if failure_count == 0:
        ui.success(
            f"Successfully compiled {success_count} plot{'s' if success_count != 1 else ''} to {out_dir} {ui.dim(f'in {total_sec:.2f}s')}"
        )
        return 0
    else:
        ui.warn(
            f"Completed with {failure_count} failure{'s' if failure_count != 1 else ''} ({success_count} succeeded) {ui.dim(f'in {total_sec:.2f}s')}"
        )
        return 1


def cmd_serve(args: argparse.Namespace) -> int:
    """Launch live-reloading preview server on target script or HTML file."""
    try:
        target = resolve_target(args.target)
    except FileNotFoundError as e:
        ui.error(str(e))
        return 1

    server = PreviewServer(
        target_path=target,
        host=args.host,
        port=args.port,
        open_browser=not args.no_open,
    )
    server.start()
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    """List and inspect discovered plot scripts in the target directory."""
    source_dir = Path(args.dir).resolve()
    recursive = getattr(args, "recursive", False) or getattr(args, "all", False)
    pattern = getattr(args, "pattern", "plot*.py")

    try:
        scripts = discover_scripts(source_dir, pattern=pattern, recursive=recursive)
    except Exception as e:
        ui.error(f"Error searching directory {source_dir}: {e}")
        return 1

    if not scripts:
        ui.info(f"No scripts matching '{pattern}' found in {source_dir}")
        return 0

    print(f"\n{ui.badge()} Discovered Plot Scripts in {source_dir}:\n")
    for s in scripts:
        rel = s.name if s.parent == source_dir else str(s.relative_to(source_dir))
        size_kb = s.stat().st_size / 1024.0
        print(f"  • {ui.bold(rel):<35} {ui.dim(f'({size_kb:.1f} KB)')}")
    print()
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Main CLI entrypoint router."""
    raw_argv = list(argv) if argv is not None else sys.argv[1:]

    # Early workspace virtualenv activation
    try:
        activate_workspace_venv()
    except Exception:
        pass

    # Apply color settings from argv
    try:
        handle_color_args(raw_argv)
    except Exception:
        pass

    # Intercept top-level help and version before parser
    if "-h" in raw_argv or "--help" in raw_argv or (len(raw_argv) == 1 and raw_argv[0] == "help"):
        print_help()
        return 0

    if "-V" in raw_argv or "--version" in raw_argv or (len(raw_argv) == 1 and raw_argv[0] in {"-v", "version"}):
        print(f"barograph {__version__}")
        return 0

    # If run without arguments, display status dashboard and interactive menu
    if not raw_argv:
        scripts = print_status_dashboard()
        if sys.stdin.isatty():
            return run_interactive_menu(scripts)
        return 0

    # Build primary parser
    parser = argparse.ArgumentParser(
        prog="barograph",
        description="Universal batch runner, multi-backend export engine, and live-reloading preview server for Python plotting scripts",
        add_help=False,
    )
    add_color_args(parser)
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose error output")
    parser.add_argument("-V", "--version", action="store_true", help="Show version")
    parser.add_argument("-h", "--help", action="store_true", help="Show help")

    subparsers = parser.add_subparsers(dest="command", required=False)

    # Subcommand: status
    p_status = subparsers.add_parser("status", add_help=False, help="Display status dashboard")
    add_color_args(p_status)
    p_status.add_argument("-d", "--dir", default=".", help="Source directory (default: .)")
    p_status.add_argument("-h", "--help", action="store_true", help="Show help")

    # Subcommand: menu / dashboard
    p_menu = subparsers.add_parser("menu", aliases=["dashboard"], add_help=False, help="Open interactive Quick Actions menu")
    add_color_args(p_menu)
    p_menu.add_argument("-d", "--dir", default=".", help="Source directory (default: .)")
    p_menu.add_argument("-h", "--help", action="store_true", help="Show help")

    # Subcommand: build
    p_build = subparsers.add_parser("build", add_help=False)
    add_color_args(p_build)
    p_build.add_argument("-d", "--dir", default=".", help="Source directory (default: .)")
    p_build.add_argument("-o", "--out", default="./dist", help="Output directory (default: ./dist)")
    p_build.add_argument(
        "-f",
        "--format",
        default="html",
        choices=["html", "svg", "png", "pdf", "webp", "jpg", "jpeg"],
        help="Target export format (default: html)",
    )
    p_build.add_argument("-p", "--pattern", default="plot*.py", help="Glob pattern (default: plot*.py)")
    p_build.add_argument("-r", "--recursive", action="store_true", help="Scan recursively")
    p_build.add_argument("-a", "--all", action="store_true", help="Scan recursively")
    p_build.add_argument("-v", "--verbose", action="store_true", help="Verbose error output")
    p_build.add_argument("-h", "--help", action="store_true", help="Show help")

    # Subcommand: serve
    p_serve = subparsers.add_parser("serve", add_help=False)
    add_color_args(p_serve)
    p_serve.add_argument("target", nargs="?", default=None, help="Target script or HTML file")
    p_serve.add_argument("-p", "--port", type=int, default=0, help="Port to bind (default: 0)")
    p_serve.add_argument("--host", default="127.0.0.1", help="Host to bind (default: 127.0.0.1)")
    p_serve.add_argument("--no-open", action="store_true", help="Do not automatically open browser")
    p_serve.add_argument("-v", "--verbose", action="store_true", help="Verbose error output")
    p_serve.add_argument("-h", "--help", action="store_true", help="Show help")

    # Subcommand: list / ls
    p_list = subparsers.add_parser("list", aliases=["ls"], add_help=False)
    add_color_args(p_list)
    p_list.add_argument("-d", "--dir", default=".", help="Source directory (default: .)")
    p_list.add_argument("-p", "--pattern", default="plot*.py", help="Glob pattern (default: plot*.py)")
    p_list.add_argument("-r", "--recursive", action="store_true", help="Scan recursively")
    p_list.add_argument("-a", "--all", action="store_true", help="Scan recursively")
    p_list.add_argument("-h", "--help", action="store_true", help="Show help")

    try:
        args = parser.parse_args(argv)
    except Exception as e:
        ui.error(str(e))
        print_help()
        return 2

    # Handle help flag on subcommands
    if getattr(args, "help", False):
        print_help()
        return 0

    if args.command == "build":
        return cmd_build(args)
    elif args.command == "serve":
        return cmd_serve(args)
    elif args.command in {"list", "ls"}:
        return cmd_list(args)
    elif args.command == "status":
        print_status_dashboard(getattr(args, "dir", "."))
        return 0
    elif args.command in {"menu", "dashboard"}:
        scripts = print_status_dashboard(getattr(args, "dir", "."))
        return run_interactive_menu(scripts)
    else:
        scripts = print_status_dashboard()
        if sys.stdin.isatty():
            return run_interactive_menu(scripts)
        return 0


if __name__ == "__main__":
    sys.exit(main())
