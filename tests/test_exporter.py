"""Unit tests for Prism multi-backend export engine."""

from __future__ import annotations

from pathlib import Path
import pytest

from prism.exporter import ExportError, export_figure, render_to_html_string, wrap_svg_in_html
from tests.test_runner import (
    DummyAltairChart,
    DummyBokehPlot,
    DummyMatplotlibFigure,
    DummyPlotlyFigure,
)


def test_wrap_svg_in_html() -> None:
    html = wrap_svg_in_html("<svg><circle r='10'/></svg>", title="Test SVG")
    assert "<!DOCTYPE html>" in html
    assert "<circle r='10'/>" in html
    assert "Test SVG" in html


def test_render_to_html_string_plotly() -> None:
    fig = DummyPlotlyFigure()
    # DummyPlotlyFigure implements write_html
    html = render_to_html_string(fig)
    assert "Mock Plotly" in html


def test_render_to_html_string_matplotlib() -> None:
    fig = DummyMatplotlibFigure()
    html = render_to_html_string(fig)
    assert "<!DOCTYPE html>" in html
    assert "Mock SVG" in html


def test_export_plotly_html(tmp_path: Path) -> None:
    fig = DummyPlotlyFigure()
    out = tmp_path / "plot.html"

    res = export_figure(fig, out, target_format="html")
    assert res.output_path == out
    assert res.requested_format == "html"
    assert res.actual_format == "html"
    assert not res.degraded
    assert out.is_file()
    assert "Mock Plotly" in out.read_text()


def test_export_matplotlib_svg(tmp_path: Path) -> None:
    fig = DummyMatplotlibFigure()
    out = tmp_path / "plot.svg"

    res = export_figure(fig, out, target_format="svg")
    assert res.output_path == out
    assert res.actual_format == "svg"
    assert not res.degraded
    assert out.is_file()
    assert "Mock SVG" in out.read_text()


def test_export_matplotlib_graceful_degrade_to_svg(tmp_path: Path) -> None:
    fig = DummyMatplotlibFigure()
    # User requested .html for a matplotlib figure
    out = tmp_path / "plot.html"

    res = export_figure(fig, out, target_format="html")
    # Must degrade to .svg and rename file
    assert res.requested_format == "html"
    assert res.actual_format == "svg"
    assert res.degraded is True
    assert res.degraded_reason is not None
    assert res.output_path.suffix == ".svg"
    assert res.output_path.is_file()
    assert "Mock SVG" in res.output_path.read_text()


def test_render_to_html_string_altair() -> None:
    chart = DummyAltairChart()
    html = render_to_html_string(chart)
    assert "Altair Chart" in html


def test_export_altair_html(tmp_path: Path) -> None:
    chart = DummyAltairChart()
    out = tmp_path / "chart.html"

    res = export_figure(chart, out, target_format="html")
    assert res.output_path == out
    assert res.actual_format == "html"
    assert out.is_file()
    assert "Altair Chart" in out.read_text()


def test_export_creates_parent_directories(tmp_path: Path) -> None:
    fig = DummyPlotlyFigure()
    nested_out = tmp_path / "deep" / "nested" / "dir" / "plot.html"

    res = export_figure(fig, nested_out, target_format="html")
    assert nested_out.is_file()
