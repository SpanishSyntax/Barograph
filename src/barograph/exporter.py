"""Multi-backend export router and format converter for Barograph."""

from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from barograph.runner import detect_backend


class ExportError(Exception):
    """Raised when figure serialization or export fails."""

    pass


@dataclass
class ExportResult:
    """Details of a completed figure export operation."""

    input_path: Path
    output_path: Path
    requested_format: str
    actual_format: str
    backend: str
    degraded: bool = False
    degraded_reason: str | None = None


def wrap_svg_in_html(svg_content: str, title: str = "Barograph Figure Preview") -> str:
    """Embed an SVG graphic inside a clean, modern, responsive HTML container."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{title}</title>
  <style>
    :root {{
      --bg: #0f141c;
      --card-bg: #161d27;
      --border: #263345;
      --text: #e6edf3;
    }}
    @media (prefers-color-scheme: light) {{
      :root {{
        --bg: #f6f8fa;
        --card-bg: #ffffff;
        --border: #d0d7de;
        --text: #1f2328;
      }}
    }}
    * {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }}
    body {{
      background-color: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
      padding: 1rem;
    }}
    .figure-container {{
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 1.5rem;
      box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
      max-width: 95vw;
      max-height: 90vh;
      display: flex;
      align-items: center;
      justify-content: center;
      overflow: auto;
    }}
    svg {{
      max-width: 100%;
      height: auto;
      display: block;
    }}
  </style>
</head>
<body>
  <div class="figure-container">
    {svg_content}
  </div>
</body>
</html>
"""


def render_to_html_string(figure: Any, title: str = "Barograph Figure Preview") -> str:
    """Render any supported figure object directly to an HTML string.

    For Plotly figures, uses .to_html() with CDN assets and full viewport height.
    For Matplotlib/Seaborn figures, serializes to SVG and wraps in responsive HTML.
    """
    import os
    import tempfile

    backend = detect_backend(figure)

    if backend == "plotly":
        if hasattr(figure, "to_html") and callable(figure.to_html):
            return figure.to_html(
                include_plotlyjs="cdn",
                full_html=True,
                default_height="calc(100vh - 16px)",
            )
        elif hasattr(figure, "write_html"):
            buffer = io.StringIO()
            try:
                figure.write_html(
                    buffer,
                    include_plotlyjs="cdn",
                    full_html=True,
                    default_height="calc(100vh - 16px)",
                )
                val = buffer.getvalue()
                if val:
                    return val
            except (TypeError, OSError):
                pass

            # Fallback using temporary file if write_html requires string path
            with tempfile.NamedTemporaryFile("w+", suffix=".html", delete=False) as tf:
                tname = tf.name
            try:
                figure.write_html(
                    tname,
                    include_plotlyjs="cdn",
                    full_html=True,
                    default_height="calc(100vh - 16px)",
                )
                with open(tname, "r", encoding="utf-8") as rf:
                    return rf.read()
            finally:
                if os.path.exists(tname):
                    os.unlink(tname)

    if backend in {"matplotlib", "seaborn"} or hasattr(figure, "savefig"):
        buf = io.StringIO()
        try:
            figure.savefig(buf, format="svg", bbox_inches="tight")
            svg_str = buf.getvalue()
        except (TypeError, OSError):
            with tempfile.NamedTemporaryFile("w+", suffix=".svg", delete=False) as tf:
                tname = tf.name
            try:
                figure.savefig(tname, format="svg", bbox_inches="tight")
                with open(tname, "r", encoding="utf-8") as rf:
                    svg_str = rf.read()
            finally:
                if os.path.exists(tname):
                    os.unlink(tname)
        return wrap_svg_in_html(svg_str, title=title)

    if backend == "altair" or hasattr(figure, "to_html") or hasattr(figure, "save"):
        if hasattr(figure, "to_html") and callable(figure.to_html):
            return figure.to_html()
        elif hasattr(figure, "save") and callable(figure.save):
            with tempfile.NamedTemporaryFile("w+", suffix=".html", delete=False) as tf:
                tname = tf.name
            try:
                figure.save(tname, format="html")
                with open(tname, "r", encoding="utf-8") as rf:
                    return rf.read()
            finally:
                if os.path.exists(tname):
                    os.unlink(tname)

    # Fallback to string representation if nothing else
    return wrap_svg_in_html(f"<pre>{str(figure)}</pre>", title=title)


def export_figure(
    figure: Any,
    output_path: str | Path,
    source_script: str | Path | None = None,
    target_format: str = "html",
    dpi: int = 300,
) -> ExportResult:
    """Export a figure to disk using the appropriate backend router.

    Args:
        figure: Root figure object (Plotly, Matplotlib, Seaborn).
        output_path: Target output file path.
        source_script: Source Python script path (for logging/metadata).
        target_format: Requested format ('html', 'svg', 'png', 'pdf', 'webp', etc.).
        dpi: Resolution for static Matplotlib raster exports.

    Returns:
        ExportResult describing the outcome.

    Raises:
        ExportError: If backend export fails.
    """
    out_file = Path(output_path).resolve()
    out_file.parent.mkdir(parents=True, exist_ok=True)
    src_path = Path(source_script).resolve() if source_script else out_file

    fmt = target_format.lower().lstrip(".")
    backend = detect_backend(figure)

    degraded = False
    degraded_reason = None
    actual_fmt = fmt

    # Backend routing
    if backend == "plotly":
        if fmt == "html":
            try:
                figure.write_html(
                    str(out_file),
                    include_plotlyjs="cdn",
                    full_html=True,
                    default_height="calc(100vh - 16px)",
                )
            except Exception as e:
                raise ExportError(f"Plotly HTML export failed: {e}") from e
        else:
            try:
                # Requires kaleido
                figure.write_image(str(out_file), format=fmt)
            except Exception as e:
                raise ExportError(
                    f"Plotly static export to '{fmt}' failed: {e}.\n"
                    "Note: Plotly static exports require 'kaleido' (run `pip install kaleido`)."
                ) from e

    elif backend in {"matplotlib", "seaborn"}:
        if fmt == "html":
            # Graceful degradation from HTML to SVG
            degraded = True
            actual_fmt = "svg"
            degraded_reason = (
                "Matplotlib figure does not natively compile to dynamic HTML; "
                "gracefully degraded to SVG vector graphic."
            )
            # Adjust destination path extension if it ended in .html
            if out_file.suffix.lower() == ".html":
                out_file = out_file.with_suffix(".svg")

            try:
                figure.savefig(str(out_file), format="svg", bbox_inches="tight")
            except Exception as e:
                raise ExportError(f"Matplotlib SVG export failed: {e}") from e
        else:
            try:
                figure.savefig(str(out_file), format=fmt, bbox_inches="tight", dpi=dpi)
            except Exception as e:
                raise ExportError(f"Matplotlib export to '{fmt}' failed: {e}") from e

    elif backend == "altair":
        if fmt == "html":
            if hasattr(figure, "save"):
                figure.save(str(out_file), format="html")
            elif hasattr(figure, "to_html"):
                out_file.write_text(figure.to_html(), encoding="utf-8")
        else:
            try:
                figure.save(str(out_file), format=fmt)
            except Exception as e:
                raise ExportError(
                    f"Altair export to '{fmt}' failed: {e}.\n"
                    "Note: Static Altair exports require 'vl-convert-python'."
                ) from e

    elif backend == "bokeh":
        if fmt == "html":
            if hasattr(figure, "to_html"):
                out_file.write_text(figure.to_html(), encoding="utf-8")
            else:
                try:
                    from bokeh.embed import file_html
                    from bokeh.resources import CDN
                    html_str = file_html(figure, CDN, "Bokeh Plot")
                    out_file.write_text(html_str, encoding="utf-8")
                except Exception as e:
                    raise ExportError(f"Bokeh HTML export failed: {e}") from e
        else:
            try:
                from bokeh.io import export_png, export_svg
                if fmt in {"png", "webp"}:
                    export_png(figure, filename=str(out_file))
                elif fmt == "svg":
                    export_svg(figure, filename=str(out_file))
                else:
                    raise ExportError(f"Bokeh does not support '{fmt}' export directly.")
            except Exception as e:
                raise ExportError(f"Bokeh static export failed: {e}") from e

    else:
        # Generic fallback
        if hasattr(figure, "export") and callable(figure.export):
            figure.export(str(out_file))
        elif hasattr(figure, "write_html") and fmt == "html":
            figure.write_html(str(out_file))
        elif hasattr(figure, "to_html") and fmt == "html":
            out_file.write_text(figure.to_html(), encoding="utf-8")
        elif hasattr(figure, "save") and callable(figure.save):
            figure.save(str(out_file))
        elif hasattr(figure, "savefig"):
            figure.savefig(str(out_file), bbox_inches="tight")
        else:
            raise ExportError(
                f"Unknown figure type '{type(figure).__name__}'. Unable to route export."
            )

    return ExportResult(
        input_path=src_path,
        output_path=out_file,
        requested_format=fmt,
        actual_format=actual_fmt,
        backend=backend,
        degraded=degraded,
        degraded_reason=degraded_reason,
    )
