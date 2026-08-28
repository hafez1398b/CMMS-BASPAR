"""Initial schema — Phase 0 plus the Phase 1/2 tables designed upfront
(Master-prompt §1B RULE: later phases must never break the schema)."""

VERSION = 1
NAME = "initial_schema"


def upgrade(conn):
    # Importing here keeps the runner usable even before the app package
    # is fully initialised in odd environments.
    from backend.app.db import Base
    from backend.app import models  # noqa: F401 — registers all tables

    Base.metadata.create_all(bind=conn)
