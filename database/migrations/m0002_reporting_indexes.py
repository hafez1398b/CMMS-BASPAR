"""Secondary indexes for reporting / dashboard hot paths (§27, §9)."""

from sqlalchemy import text

VERSION = 2
NAME = "reporting_indexes"

INDEXES = [
    "CREATE INDEX IF NOT EXISTS ix_equipment_criticality ON equipment (criticality)",
    "CREATE INDEX IF NOT EXISTS ix_equipment_status ON equipment (status)",
    "CREATE INDEX IF NOT EXISTS ix_equipment_factory ON equipment (factory_id)",
    "CREATE INDEX IF NOT EXISTS ix_equipment_category ON equipment (category_id)",
    "CREATE INDEX IF NOT EXISTS ix_plans_next_due ON maintenance_plans (next_due)",
    "CREATE INDEX IF NOT EXISTS ix_plans_equipment ON maintenance_plans (equipment_id)",
    "CREATE INDEX IF NOT EXISTS ix_files_entity ON files (entity_type, entity_id)",
]


def upgrade(conn):
    for stmt in INDEXES:
        conn.execute(text(stmt))
