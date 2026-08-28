"""Bulk Data Charge: upload → validation preview → confirm → rollback."""
import io

from openpyxl import Workbook


def _xlsx(rows):
    wb = Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


HEADER = ["کد تجهیز", "نام تجهیز", "سطح", "کارخانه", "دسته‌بندی", "کد والد",
          "سازنده", "مدل", "سال ساخت", "درجه اهمیت", "وضعیت"]


def test_template_download(client, admin_headers):
    r = client.get("/api/equipment/bulk-import/template", headers=admin_headers)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument")


def test_validation_preview_then_confirm_then_rollback(client, admin_headers):
    rows = [
        HEADER,
        ["IMP-1", "کمپرسور وارداتی ۱", "تجهیز", "بسپار۱", "تأسیسات",
         "", "Siemens", "X200", 2018, "زیاد", "فعال"],
        ["IMP-1-S", "سیستم خنک‌کاری", "زیرسیستم", "", "", "IMP-1", "", "", "", "", ""],
        ["IMP-2", "", "تجهیز", "بسپار۱", "تأسیسات", "", "", "", "", "", ""],  # missing name
        ["IMP-1", "تکراری", "تجهیز", "بسپار۱", "تأسیسات", "", "", "", "", "", ""],  # dup in file
        ["IMP-3", "سطح بد", "پرنده", "بسپار۱", "تأسیسات", "", "", "", "", "", ""],  # bad level
    ]
    files = {"file": ("import.xlsx", _xlsx(rows), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    r = client.post("/api/equipment/bulk-import", headers=admin_headers, files=files)
    assert r.status_code == 200, r.text
    p = r.json()
    assert p["total_rows"] == 5
    assert p["valid_rows"] == 2
    assert p["error_rows"] == 3
    batch_id = p["batch_id"]

    # errors point at the right rows
    by_row = {x["row_number"]: x for x in p["rows"]}
    assert not by_row[4]["is_valid"] and "نام تجهیز الزامی است" in by_row[4]["errors"]
    assert any("تکراری" in e for e in by_row[5]["errors"])

    # confirm creates exactly the 2 valid rows (parent before child)
    r = client.post(f"/api/equipment/bulk-import/{batch_id}/confirm", headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["created"] == 2

    eq = client.get("/api/equipment?level=all&q=IMP-1", headers=admin_headers).json()
    assert eq["total"] >= 1
    child = client.get("/api/equipment?level=all&q=IMP-1-S", headers=admin_headers).json()["items"][0]
    assert child["parent_id"] is not None

    # rollback removes them
    r = client.post(f"/api/equipment/bulk-import/{batch_id}/rollback", headers=admin_headers)
    assert r.status_code == 200 and r.json()["removed"] == 2
    assert client.get("/api/equipment?level=all&q=IMP-1", headers=admin_headers).json()["total"] == 0

    # second rollback refused
    assert client.post(f"/api/equipment/bulk-import/{batch_id}/rollback",
                       headers=admin_headers).status_code == 400


def test_auto_create_lookups(client, admin_headers):
    rows = [HEADER,
            ["IMP-9", "تجهیز کارخانه جدید", "تجهیز", "کارخانه شماره ۹۹", "دسته تستی",
             "", "", "", "", "بحرانی", "فعال"]]
    files = {"file": ("i2.xlsx", _xlsx(rows), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}

    # without auto-create: factory unknown → error
    r = client.post("/api/equipment/bulk-import", headers=admin_headers, files=files)
    p = r.json()
    assert p["valid_rows"] == 0

    # with auto-create: valid
    files = {"file": ("i2.xlsx", _xlsx(rows), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    r = client.post("/api/equipment/bulk-import?auto_create_lookups=true",
                    headers=admin_headers, files=files)
    p = r.json()
    assert p["valid_rows"] == 1
    r = client.post(f"/api/equipment/bulk-import/{p['batch_id']}/confirm", headers=admin_headers)
    assert r.json()["created"] == 1
    client.post(f"/api/equipment/bulk-import/{p['batch_id']}/rollback", headers=admin_headers)


def test_missing_required_columns_rejected(client, admin_headers):
    wb = Workbook(); ws = wb.active
    ws.append(["ستون", "بی‌ربط"]); ws.append(["a", "b"])
    buf = io.BytesIO(); wb.save(buf); buf.seek(0)
    r = client.post("/api/equipment/bulk-import", headers=admin_headers,
                    files={"file": ("bad.xlsx", buf, "application/octet-stream")})
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# Markdown / text import
# ---------------------------------------------------------------------------

MD_TABLE = """# فایل تجهیزات بسپار۳

| کد تجهیز | نام تجهیز | سطح | کارخانه | دسته‌بندی | نوع قطعه | سالن | درجه اهمیت | وضعیت |
|---|---|---|---|---|---|---|---|---|
| MD-1 | پمپ تست مارک‌داون | تجهیز | بسپار۱ | تأسیسات | پمپ | سالن ۱ | زیاد | فعال |
| MD-2 | تابلو برق تست | تجهیز | بسپار۱ | تأسیسات | تابلو برق |  | متوسط |  |
|  | بدون کد | تجهیز | بسپار۱ | تأسیسات |  |  |  |  |
"""


def test_markdown_table_text_import(client, admin_headers):
    r = client.post("/api/equipment/bulk-import/text", headers=admin_headers,
                    json={"text": MD_TABLE, "filename": "test.md"})
    assert r.status_code == 200, r.text
    p = r.json()
    assert p["total_rows"] == 3
    assert p["valid_rows"] == 2 and p["error_rows"] == 1

    r = client.post(f"/api/equipment/bulk-import/{p['batch_id']}/confirm",
                    headers=admin_headers)
    assert r.status_code == 200 and r.json()["created"] == 2

    eq = client.get("/api/equipment?level=all&q=MD-1", headers=admin_headers).json()["items"][0]
    assert eq["component_type"] == "پمپ"
    assert eq["hall"] == "سالن ۱"
    eq2 = client.get("/api/equipment?level=all&q=MD-2", headers=admin_headers).json()["items"][0]
    assert eq2["criticality"] == "medium" and eq2["status"] == "active"

    r = client.post(f"/api/equipment/bulk-import/{p['batch_id']}/rollback",
                    headers=admin_headers)
    assert r.json()["removed"] == 2


MD_SECTIONS = """## MD-9 — پمپ سرفصلی
- کارخانه: بسپار۱
- دسته‌بندی: تأسیسات
- سطح: تجهیز
- درجه اهمیت: بحرانی

## **MD-10** — کمپرسور سرفصلی
* سطح: تجهیز
* کارخانه: بسپار۱
* دسته‌بندی: تأسیسات
"""


def test_markdown_sections_text_import(client, admin_headers):
    r = client.post("/api/equipment/bulk-import/text", headers=admin_headers,
                    json={"text": MD_SECTIONS})
    assert r.status_code == 200, r.text
    p = r.json()
    assert p["total_rows"] == 2 and p["valid_rows"] == 2, p
    by_row = {x["code"]: x for x in p["rows"]}
    assert by_row["MD-9"]["name"] == "پمپ سرفصلی"
    assert by_row["MD-10"]["name"] == "کمپرسور سرفصلی"

    r = client.post(f"/api/equipment/bulk-import/{p['batch_id']}/confirm",
                    headers=admin_headers)
    assert r.json()["created"] == 2
    eq = client.get("/api/equipment?level=all&q=MD-9", headers=admin_headers).json()["items"][0]
    assert eq["criticality"] == "critical"
    client.post(f"/api/equipment/bulk-import/{p['batch_id']}/rollback", headers=admin_headers)


def test_markdown_file_upload(client, admin_headers):
    files = {"file": ("eq.md", MD_TABLE.encode("utf-8"), "text/markdown")}
    r = client.post("/api/equipment/bulk-import", headers=admin_headers, files=files)
    assert r.status_code == 200, r.text
    p = r.json()
    assert p["valid_rows"] == 2
    client.post(f"/api/equipment/bulk-import/{p['batch_id']}/rollback", headers=admin_headers)


def test_markdown_garbage_rejected(client, admin_headers):
    r = client.post("/api/equipment/bulk-import/text", headers=admin_headers,
                    json={"text": "سلام دنیا، این یک متن آزاد بدون ساختار است."})
    assert r.status_code == 400
