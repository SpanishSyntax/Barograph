"""Main entry point for running barograph via `python -m barograph`."""

from __future__ import annotations

import sys
from barograph.cli import main

if __name__ == "__main__":
    sys.exit(main())
