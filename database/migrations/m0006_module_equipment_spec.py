"""MODULE EQUIPMENT — BASPAR spec additions (§7/§11/§34/§6B).

Additive only — no data is dropped (§46).  Equipment gains location
properties + archive flag; staging tables gain Bulk-Charge-Center fields.
"""

from sqlalchemy import inspect, text

VERSION = 6
NAME = "module_equipment_spec"

ADD_COLUMNS = {
    "equipment": {
        "hall": "VARCHAR(128)",
        "dept": "VARCHAR(128)",
        "line": "VARCHAR(128)",
        "position": "VARCHAR(190)",
        "location_notes": "TEXT",
        "archived_at": "TIMESTAMP",
    },
    "import_batches": {
        "mapping": "JSON",
        "raw_file_path": "VARCHAR(512)",
    },
    "import_batch_rows": {
        "staging_status": "VARCHAR(16)",
        "matched_equipment_id": "INTEGER",
        "resolution": "TEXT",
    },
}


def upgrade(conn):
    insp = inspect(conn)
    for table, columns in ADD_COLUMNS.items():
        have = {c["name"] for c in insp.get_columns(table)}
        for col, ddl in columns.items():
            if col not in have:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}"))
