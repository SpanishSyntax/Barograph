"""Terminal UI interface for Prism, powered by Rime with robust fallback support."""

from __future__ import annotations

import sys
from typing import Any, Callable, Sequence

try:
    from rime import (
        UI,
        Spinner,
        add_color_args,
        apply_color_args,
        confirm_input,
        detect_color_support,
        get_terminal_columns,
        handle_color_args,
        multiselect_menu,
        prompt_input,
        render_error_panel,
        render_panel,
        select_menu,
        spinner_context,
        strip_ansi,
        visual_len,
    )

    ui = UI(app_name="prism", icon="💎", badge_color="1;35")
except ImportError:
    # Graceful fallback if rime is not yet installed in bare environments
    def detect_color_support() -> bool:
        return sys.stdout.isatty()

    def strip_ansi(text: str) -> str:
        import re
        return re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", text)

    def visual_len(text: str) -> int:
        return len(strip_ansi(text))

    def get_terminal_columns() -> int:
        import shutil
        return shutil.get_terminal_size((80, 24)).columns

    def add_color_args(parser: Any) -> None:
        parser.add_argument(
            "--color",
            choices=["auto", "always", "never"],
            default="auto",
            help="Color output mode (default: auto)",
        )
        parser.add_argument(
            "--no-color",
            action="store_true",
            help="Disable color output",
        )

    def handle_color_args(args: Any) -> None:
        pass

    def apply_color_args(args: Any) -> None:
        pass

    def render_panel(
        lines: Sequence[str],
        title: str | None = None,
        color: str = "36",
        border_style: str = "rounded",
    ) -> str:
        width = min(max(visual_len(l) for l in lines) + 4, 80) if lines else 40
        top = f"┌─ {title or ''} " + "─" * max(0, width - len(title or "") - 5) + "┐"
        body = [f"│  {l:<{width - 4}}│" for l in lines]
        bot = "└" + "─" * (width - 2) + "┘"
        return "\n".join([top, *body, bot])

    def render_error_panel(error_msg: str, title: str = "ERROR", details: Sequence[str] | None = None) -> str:
        content = [error_msg]
        if details:
            content.extend(details)
        return render_panel(content, title=title, color="31")

    class FallbackUI:
        def __init__(self, app_name: str = "prism", icon: str = "💎") -> None:
            self.app_name = app_name
            self.icon = icon

        def badge(self) -> str:
            return f"\033[1;35m[{self.icon} {self.app_name}]\033[0m"

        def bold(self, text: str) -> str:
            return f"\033[1m{text}\033[0m"

        def dim(self, text: str) -> str:
            return f"\033[2m{text}\033[0m"

        def blue(self, text: str) -> str:
            return f"\033[34m{text}\033[0m"

        def cyan(self, text: str) -> str:
            return f"\033[36m{text}\033[0m"

        def green(self, text: str) -> str:
            return f"\033[32m{text}\033[0m"

        def yellow(self, text: str) -> str:
            return f"\033[33m{text}\033[0m"

        def red(self, text: str) -> str:
            return f"\033[31m{text}\033[0m"

        def magenta(self, text: str) -> str:
            return f"\033[35m{text}\033[0m"

        def success(self, msg: str) -> None:
            print(f"{self.badge()} \033[32m✓\033[0m {msg}")

        def info(self, msg: str) -> None:
            print(f"{self.badge()} \033[36mℹ\033[0m {msg}")

        def warn(self, msg: str) -> None:
            print(f"{self.badge()} \033[33m⚠\033[0m {msg}")

        def error(self, msg: str) -> None:
            print(f"{self.badge()} \033[31m✗\033[0m {msg}", file=sys.stderr)

    ui = FallbackUI()
    Spinner = Any  # type: ignore
    spinner_context = None  # type: ignore
    prompt_input = None  # type: ignore
    confirm_input = None  # type: ignore
    select_menu = None  # type: ignore
    multiselect_menu = None  # type: ignore


__all__ = [
    "ui",
    "add_color_args",
    "apply_color_args",
    "handle_color_args",
    "render_panel",
    "render_error_panel",
    "detect_color_support",
    "strip_ansi",
    "visual_len",
    "get_terminal_columns",
]
