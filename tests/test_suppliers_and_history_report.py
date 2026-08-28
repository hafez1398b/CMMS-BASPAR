"""تأمین‌کنندگان (بخش ۴.۵) + گزارش سوابق نت (§28)."""


def test_suppliers_crud_and_part_link(client, admin_headers):
    r = client.post("/api/suppliers", headers=admin_headers,
                    json={"name": "گستر اسپاد", "contact": "آقای الف", "phone": "021-123"})
    assert r.status_code == 201, r.text
    sid = r.json()["id"]
    # تکراری
    assert client.post("/api/suppliers", headers=admin_headers,
                       json={"name": "گستر اسپاد"}).status_code == 409
    # ویرایش
    r2 = client.put(f"/api/suppliers/{sid}", headers=admin_headers,
                    json={"name": "گستر اسپاد تهران", "is_active": True})
    assert r2.status_code == 200 and r2.json()["name"] == "گستر اسپاد تهران"

    # ساخت قطعه با نام تأمین‌کننده → اتصال خودکار به رکورد
    r3 = client.post("/api/parts", headers=admin_headers, json={
        "code": "T-SUP-P1", "name": "پک هیدرولیک تست",
        "supplier": "گستر اسپاد تهران", "min_qty": 1, "order_qty": 4})
    assert r3.status_code == 201, r3.text
    assert r3.json()["supplier_id"] == sid
    assert r3.json()["supplier_name"] == "گستر اسپاد تهران"

    # حذف تأمین‌کننده با قطعه مرتبط → خطا
    assert client.delete(f"/api/suppliers/{sid}", headers=admin_headers).status_code == 400
    # جدا کردن قطعه و سپس حذف
    pid = r3.json()["id"]
    client.delete(f"/api/parts/{pid}", headers=admin_headers)
    assert client.delete(f"/api/suppliers/{sid}", headers=admin_headers).status_code == 200


def test_maintenance_history_report_filters(client, admin_headers):
    d = client.get("/api/reports/maintenance-history", headers=admin_headers).json()
    assert "rows" in d and d["total"] >= 1  # سوابق بسپار۳ + تزریق‌ها
    # فیلتر بازه شمسی خیلی قدیمی → خالی
    d2 = client.get("/api/reports/maintenance-history?from_jalali=1300/01/01&to_jalali=1300/12/29",
                    headers=admin_headers).json()
    assert d2["total"] == 0
    # خروجی سی‌اس‌وی
    r = client.get("/api/reports/maintenance-history/export.csv", headers=admin_headers)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
