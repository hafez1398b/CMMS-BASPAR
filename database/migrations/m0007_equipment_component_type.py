"""Add equipment.component_type («نوع قطعه»: پمپ/تابلو برق/دینام…) for
rich reporting filters requested by the client."""

from sqlalchemy import inspect, text

VERSION = 7
NAME = "equipment_component_type"


def upgrade(conn):
    insp = inspect(conn)
    have = {c["name"] for c in insp.get_columns("equipment")}
    if "component_type" not in have:
        conn.execute(text("ALTER TABLE equipment ADD COLUMN component_type VARCHAR(128)"))
