"""Phase 1 — Request/Work-Order workflow tables (§17–§20B, §25).

Additive only: existing Phase-0 data is untouched.  Reconciles the two
pre-existing tables with their Phase-1 models (adds missing columns) and
creates the new tables.  Safe on fresh databases too.
"""

from sqlalchemy import inspect, text

VERSION = 3
NAME = "phase1_workflow"

# Explicit SQLite-compatible fragments for columns added to existing tables.
ADD_COLUMNS = {
    "work_requests": {
        "priority": "VARCHAR(16) NOT NULL DEFAULT 'normal'",
        "decision_note": "TEXT",
    },
    "work_orders": {
        "description": "TEXT",
        "execution_mode": "VARCHAR(16) NOT NULL DEFAULT 'internal'",
        "permit_required": "BOOLEAN NOT NULL DEFAULT 0",
        "completed_at": "TIMESTAMP",
    },
}


def upgrade(conn):
    insp = inspect(conn)

    for table, columns in ADD_COLUMNS.items():
        have = {c["name"] for c in insp.get_columns(table)}
        for col, ddl in columns.items():
            if col not in have:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}"))

    # create any tables not present yet (covers all Phase-1 additions)
    from backend.app.db import Base
    from backend.app import models  # noqa: F401 — register mappers

    insp = inspect(conn)  # re-inspect after ALTERs
    existing = set(insp.get_table_names())
    for name, table in Base.metadata.tables.items():
        if name not in existing:
            table.create(bind=conn)
