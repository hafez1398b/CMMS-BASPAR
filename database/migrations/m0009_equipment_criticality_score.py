"""Numerical criticality score (مجموع Safety+Product+Cost+Repair از جدول
DegresOFEquipment در Access). سطح بحرانی (کم/متوسط/زیاد/بحرانی) از روی
امتیاز محاسبه می‌شود؛ خود امتیاز هم برای گزارش‌گیری نگه داشته می‌شود."""

from sqlalchemy import inspect, text

VERSION = 9
NAME = "equipment_criticality_score"


def upgrade(conn):
    insp = inspect(conn)
    have = {c["name"] for c in insp.get_columns("equipment")}
    if "criticality_score" not in have:
        conn.execute(text("ALTER TABLE equipment ADD COLUMN criticality_score INTEGER"))
