#!/usr/bin/env python3
"""Launch the anme-cli terminal interface from a source checkout."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from anmecli.app import main


if __name__ == "__main__":
    main()
