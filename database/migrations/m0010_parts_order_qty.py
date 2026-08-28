"""مقدار سفارش قطعات یدکی (فیلد SpareOrder در Access — بخش ۴.۵ سند
بارگذاری نهایی)."""

from sqlalchemy import inspect, text

VERSION = 10
NAME = "parts_order_qty"


def upgrade(conn):
    insp = inspect(conn)
    have = {c["name"] for c in insp.get_columns("parts")}
    if "order_qty" not in have:
        conn.execute(text("ALTER TABLE parts ADD COLUMN order_qty FLOAT"))
