"""Phase 2 — SELEN-ready schema: checklists (§15), risks (§28),
calibration (§29), parts/inventory (§23/§24), consultation (§32).

Additive only; creates whatever is still missing (fresh installs already
have these from metadata)."""

VERSION = 5
NAME = "phase2_modules"


def upgrade(conn):
    from sqlalchemy import inspect
    from backend.app.db import Base
    from backend.app import models  # noqa: F401

    insp = inspect(conn)
    existing = set(insp.get_table_names())
    for name, table in Base.metadata.tables.items():
        if name not in existing:
            table.create(bind=conn)
