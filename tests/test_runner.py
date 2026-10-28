"""Unit tests for Barograph dynamic runner and figure extraction protocol."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import pytest

from barograph.runner import (
    FigureNotFoundError,
    ScriptExecutionError,
    detect_backend,
    run_script,
    unwrap_figure,
)


class DummyPlotlyFigure:
    """Mock plotly figure for zero-dependency test environments."""

    def __init__(self) -> None:
        self.__module__ = "plotly.graph_objects"

    def write_html(self, path: Any, **kwargs) -> None:
        if hasattr(path, "write"):
            path.write("<html><body>Mock Plotly</body></html>")
        else:
            with open(path, "w") as f:
                f.write("<html><body>Mock Plotly</body></html>")

    def to_plotly_json(self) -> dict:
        return {"data": [], "layout": {}}


class DummyMatplotlibFigure:
    """Mock matplotlib figure for zero-dependency test environments."""

    def __init__(self) -> None:
        self.__module__ = "matplotlib.figure"

    def savefig(self, path: Any, **kwargs) -> None:
        if hasattr(path, "write"):
            path.write("<svg>Mock SVG</svg>")
        else:
            with open(path, "w") as f:
                f.write("<svg>Mock SVG</svg>")


class DummyAxes:
    def __init__(self, fig: DummyMatplotlibFigure) -> None:
        self.figure = fig

    def get_figure(self) -> DummyMatplotlibFigure:
        return self.figure


class DummyFacetGrid:
    def __init__(self, fig: DummyMatplotlibFigure) -> None:
        self.fig = fig


class DummyPlotConfigurator:
    def __init__(self) -> None:
        self.fig = DummyPlotlyFigure()


class DummyAltairChart:
    def __init__(self) -> None:
        self.__class__.__name__ = "Chart"
        self.__module__ = "altair.vegalite"

    def to_html(self) -> str:
        return "<html><body>Altair Chart</body></html>"

    def save(self, path: str, **kwargs) -> None:
        with open(path, "w") as f:
            f.write("<html>Altair Chart</html>")


class DummyBokehPlot:
    def __init__(self) -> None:
        self.__module__ = "bokeh.plotting"
        self.renderers = []

    def to_html(self) -> str:
        return "<html><body>Bokeh Plot</body></html>"


def test_detect_backend() -> None:
    assert detect_backend(DummyPlotlyFigure()) == "plotly"
    assert detect_backend(DummyMatplotlibFigure()) == "matplotlib"
    assert detect_backend(DummyFacetGrid(DummyMatplotlibFigure())) == "seaborn"
    assert detect_backend(DummyAltairChart()) == "altair"
    assert detect_backend(DummyBokehPlot()) == "bokeh"


def test_unwrap_figure() -> None:
    mpl = DummyMatplotlibFigure()
    axes = DummyAxes(mpl)
    assert unwrap_figure(axes) is mpl

    grid = DummyFacetGrid(mpl)
    assert unwrap_figure(grid) is mpl

    config = DummyPlotConfigurator()
    assert unwrap_figure(config) is config.fig


def test_run_script_module_fig(tmp_path: Path) -> None:
    script = tmp_path / "plot_fig.py"
    script.write_text("""
class MockFig:
    def write_html(self, path, **kwargs):
        pass
    def to_plotly_json(self):
        return {}
fig = MockFig()
""")
    res = run_script(script)
    assert res.figure is not None
    assert res.backend == "plotly"
    assert res.execution_time_ms > 0


def test_run_script_module_config_fig(tmp_path: Path) -> None:
    script = tmp_path / "plot_config.py"
    script.write_text("""
class MockFig:
    def write_html(self, path, **kwargs):
        pass
    def to_plotly_json(self):
        return {}

class Configurator:
    def __init__(self):
        self.fig = MockFig()

config = Configurator()
""")
    res = run_script(script)
    assert res.figure is not None
    assert res.backend == "plotly"


def test_run_script_callable_plot(tmp_path: Path) -> None:
    script = tmp_path / "plot_fn.py"
    script.write_text("""
class MockFig:
    def savefig(self, path, **kwargs):
        pass

def plot():
    return MockFig()
""")
    res = run_script(script)
    assert res.figure is not None
    assert res.backend == "matplotlib"


def test_run_script_callable_main(tmp_path: Path) -> None:
    script = tmp_path / "plot_main.py"
    script.write_text("""
class MockFig:
    def savefig(self, path, **kwargs):
        pass

def main():
    return MockFig()
""")
    res = run_script(script)
    assert res.figure is not None
    assert res.backend == "matplotlib"


def test_run_script_with_plt_show_does_not_block(tmp_path: Path) -> None:
    script = tmp_path / "plot_show.py"
    script.write_text("""
class MockFig:
    def savefig(self, path, **kwargs):
        pass

fig = MockFig()
# Simulating a legacy script that calls plt.show()
try:
    import matplotlib.pyplot as plt
    plt.show()
except Exception:
    pass
""")
    res = run_script(script)
    assert res.figure is not None


def test_run_script_figure_not_found(tmp_path: Path) -> None:
    script = tmp_path / "plot_empty.py"
    script.write_text("""
x = [1, 2, 3]
y = [4, 5, 6]
# No figure exposed
""")
    with pytest.raises(FigureNotFoundError):
        run_script(script)


def test_run_script_execution_error(tmp_path: Path) -> None:
    script = tmp_path / "plot_error.py"
    script.write_text("""
raise ValueError("Intentional script failure")
""")
    with pytest.raises(ScriptExecutionError) as exc_info:
        run_script(script)
    assert "Intentional script failure" in str(exc_info.value)
    assert exc_info.value.tb_text is not None


def test_run_script_metadata_and_title(tmp_path: Path) -> None:
    script = tmp_path / "plot_meta.py"
    script.write_text('''"""SC42056 Algorithm: Feasible Polytope.

Detailed explanation of the optimization geometry.
Second line of description.
"""
class MockLayout:
    class Title:
        text = "Polytope Geometry Plot"
    title = Title()

class MockFig:
    layout = MockLayout()
    def write_html(self, path, **kwargs):
        pass
    def to_plotly_json(self):
        return {}

fig = MockFig()
''')
    res = run_script(script)
    assert res.figure is not None
    assert res.backend == "plotly"
    assert res.execution_time_ms > 0
    assert isinstance(res.metadata, dict)
    assert res.metadata["title"] == "Polytope Geometry Plot"
    assert "Detailed explanation" in res.metadata["description"]
    assert "SC42056 Algorithm: Feasible Polytope" in res.metadata["docstring"]
