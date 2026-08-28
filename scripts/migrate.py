#!/usr/bin/env python3
"""CLI: apply database migrations.  Usage: python scripts/migrate.py"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.migrate import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
