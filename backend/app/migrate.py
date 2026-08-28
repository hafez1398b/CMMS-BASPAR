"""Versioned migration runner (§52).

Migrations live in `database/migrations/` as ordered Python modules
(`m0001_name.py`) each exposing `VERSION`, `NAME` and `upgrade(conn)`.
Applied versions are tracked in `schema_migrations`; the runner is
idempotent and safe to run on every deploy.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from sqlalchemy import text

from .db import engine

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "database" / "migrations"


def _load_migrations():
    mods = []
    for p in sorted(MIGRATIONS_DIR.glob("m*.py")):
        spec = importlib.util.spec_from_file_location(p.stem, p)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mods.append(mod)
    return sorted(mods, key=lambda m: m.VERSION)


def _ensure_table(conn):
    conn.execute(text(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        "version INTEGER PRIMARY KEY, name TEXT NOT NULL,"
        " applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
    ))


def applied_versions(conn) -> set[int]:
    rows = conn.execute(text("SELECT version FROM schema_migrations")).fetchall()
    return {r[0] for r in rows}


def run_migrations(verbose: bool = True) -> list[int]:
    applied_now: list[int] = []
    with engine.begin() as conn:
        _ensure_table(conn)
        applied = applied_versions(conn)
        for mod in _load_migrations():
            if mod.VERSION in applied:
                continue
            if verbose:
                print(f"[migrate] applying {mod.VERSION:04d}_{mod.NAME}")
            mod.upgrade(conn)
            conn.execute(
                text("INSERT INTO schema_migrations (version, name) VALUES (:v, :n)"),
                {"v": mod.VERSION, "n": mod.NAME},
            )
            applied_now.append(mod.VERSION)
    return applied_now


def main():
    applied_now = run_migrations()
    if not applied_now:
        print("[migrate] schema already up to date")
    return 0


if __name__ == "__main__":
    sys.exit(main())
