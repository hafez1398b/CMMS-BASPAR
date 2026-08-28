#!/usr/bin/env python3
"""CLI backup (also available from Admin UI). Usage: python scripts/backup.py"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.modules.backup_api import create_backup_archive  # noqa: E402


def main():
    archive = create_backup_archive(user_id=None)
    print(f"backup created: {archive} ({archive.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
