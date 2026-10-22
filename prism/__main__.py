"""Main entry point for running prism via `python -m prism`."""

from __future__ import annotations

import sys
from prism.cli import main

if __name__ == "__main__":
    sys.exit(main())
