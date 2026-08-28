#!/usr/bin/env python3
"""CLI: idempotent seed of roles/permissions/admin/lookups/base data.

Usage:  python scripts/seed.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.db import SessionLocal  # noqa: E402
from backend.app.migrate import run_migrations  # noqa: E402
from backend.app.seeds import seed  # noqa: E402


def main():
    run_migrations()
    with SessionLocal() as db:
        seed(db)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
