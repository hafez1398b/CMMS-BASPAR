"""Link PM plans to their consumable parts (برنامه نت با قطعات مصرفی).

Client data format:
    | کد PM | عنوان | قطعه مصرفی | تعداد | دوره |
    | B1P01-PM-20 | تعویض روغن هیدرولیک | روغن هیدرولیک | ۵۰ لیتر | سالیانه |

Each PM activity can consume one or more parts (name + quantity + unit).
Loosely links to the inventory `parts` table when a matching Part exists.
"""

from sqlalchemy import inspect, text

VERSION = 8
NAME = "pm_consumables"


def upgrade(conn):
    insp = inspect(conn)
    if "pm_consumables" in insp.get_table_names():
        return
    conn.execute(text(
        """
        CREATE TABLE pm_consumables (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plan_id INTEGER NOT NULL REFERENCES maintenance_plans(id),
            equipment_id INTEGER REFERENCES equipment(id),
            part_id INTEGER REFERENCES parts(id),
            part_name VARCHAR(190) NOT NULL,
            quantity FLOAT,
            unit VARCHAR(32),
            note TEXT,
            created_by INTEGER REFERENCES users(id),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    ))
    conn.execute(text("CREATE INDEX ix_pm_consumables_plan_id ON pm_consumables(plan_id)"))
    conn.execute(text("CREATE INDEX ix_pm_consumables_equipment_id ON pm_consumables(equipment_id)"))
