"""Reconciles Phase-1 columns added to pre-existing Phase-0 tables.

Fresh installs get these from m0003's table creation; this migration is a
guarded no-op there.  Exists because m0003 shipped before the final column
set was frozen — versioned history must never be rewritten (§52)."""

from sqlalchemy import inspect, text

VERSION = 4
NAME = "phase1_column_reconcile"

ADD_COLUMNS = {
    "work_requests": {
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
