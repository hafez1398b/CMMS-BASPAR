"""موجودیت تأمین‌کننده (بخش ۴.۵ سند بارگذاری نهایی — جدول 40 رکوردی
supplier در Access). قطعات یدکی به‌جای متن آزاد، به تأمین‌کننده لینک
می‌شوند؛ فیلد متنی قبلی برای سازگاری حفظ می‌شود."""

from sqlalchemy import inspect, text

VERSION = 11
NAME = "suppliers"


def upgrade(conn):
    insp = inspect(conn)
    if "suppliers" not in insp.get_table_names():
        conn.execute(text(
            """
            CREATE TABLE suppliers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(190) NOT NULL,
                contact VARCHAR(190),
                phone VARCHAR(64),
                notes TEXT,
                is_active BOOLEAN DEFAULT 1,
                created_by INTEGER REFERENCES users(id),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        ))
        conn.execute(text(
            "CREATE UNIQUE INDEX uq_suppliers_name ON suppliers(name)"))
    have = {c["name"] for c in insp.get_columns("parts")}
    if "supplier_id" not in have:
        conn.execute(text(
            "ALTER TABLE parts ADD COLUMN supplier_id INTEGER REFERENCES suppliers(id)"))
