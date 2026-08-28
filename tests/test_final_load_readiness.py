"""آمادگی بارگذاری نهایی داده‌های بسپار — مسیر 6B و نگاشت‌های منبع.

رگرسیون برای: نام فیلدهای واقعی Access، تشخیص بر اساس مقدار،
رمزگشایی کد تجهیز، و زیرساخت‌های ضروری شارژ انبوه.
"""


def test_access_headers_map_correctly(client, admin_headers):
    from backend.app.ai.equipment_codes import suggest_mapping
    headers = [
        "equipmentcode", "equipment name", "equipment location",
        "equipmentcategory", "eqyuipmentModel", "capacity",
        "unit of capacity", "installation date", "Level of automation",
        "equipmentstatus",
    ]
    got = {s["header"].lower(): s["field"] for s in suggest_mapping(headers)}
    assert got["equipmentcode"] == "code"
    assert got["equipment name"] == "name"
    assert got["equipment location"] == "location"
    assert got["equipmentcategory"] == "category"
    assert got["eqyuipmentmodel"] == "model"
    assert got["unit of capacity"] == "capacity_unit"
    assert got["installation date"] == "install_date"
    assert got["level of automation"] == "automation"
    assert got["equipmentstatus"] == "status"


def test_failure_table_headers_map():
    from backend.app.ai.equipment_codes import HEADER_ALIASES
    assert HEADER_ALIASES["day failuer"] == "failure_date"
    assert HEADER_ALIASES["discription"] == "description"
    assert HEADER_ALIASES["repair"] == "repair_action"
    assert HEADER_ALIASES["idmainequipment"] == "parent_code"
    assert HEADER_ALIASES["frequencyid"] == "interval"
    assert HEADER_ALIASES["equipment spar parts"] == "part_code"
    assert HEADER_ALIASES["inventoryminimum"] == "min_stock"
    assert HEADER_ALIASES["spareorder"] == "order_qty"


def test_value_based_detection():
    from backend.app.ai.equipment_codes import guess_field_from_value
    assert guess_field_from_value("فعال") == "status"
    assert guess_field_from_value("اتوماتیک") == "automation"
    assert guess_field_from_value("B") == "criticality_grade"
    assert guess_field_from_value("1394/07/26") == "install_date"
    assert guess_field_from_value("دستگاه تزریق یک") is None


def test_code_decoding_signals(client, admin_headers):
    from backend.app.ai.equipment_codes import decode_code
    from backend.app.db import SessionLocal
    with SessionLocal() as db:
        d = decode_code(db, "B1PT01")
        assert d["factory_name"] == "بسپار۱"
        assert d["area_code"] == "P"
        d2 = decode_code(db, "B3AF2")
        assert d2["factory_name"] == "بسپار۳"
        assert d2["area_code"] == "AF"
        unknown = decode_code(db, "ZZ12")
        assert unknown["unknown_prefix"] is True


def test_bulk_charge_routes_exist(client, admin_headers):
    from backend.app.modules import bulk_charge
    paths = {r.path for r in bulk_charge.router.routes}
    for needed in (
        "/equipment/bulk-charge/template",
        "/equipment/bulk-charge/upload",
        "/equipment/bulk-charge/{batch_id}/mapping",
        "/equipment/bulk-charge/{batch_id}/preview",
        "/equipment/bulk-charge/{batch_id}/commit",
        "/equipment/bulk-charge/{batch_id}/rollback",
    ):
        assert needed in paths


def test_personnel_for_assignment_rules_exist(client, admin_headers):
    """scripts/seed_personnel.py باید همه نفرات قانون نیروی انسانی را بسازد."""
    import importlib.util
    from pathlib import Path

    from backend.app.db import SessionLocal
    from backend.app.models import Role, User
    from backend.app.security import hash_password

    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("seed_personnel", root / "scripts" / "seed_personnel.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    with SessionLocal() as db:
        for username, full_name, roles, _note in mod.PERSONNEL:
            if db.query(User).filter(User.username == username).first():
                continue
            role_objs = db.query(Role).filter(Role.name.in_(roles)).all()
            assert len(role_objs) == len(roles), f"نقش نامعتبر برای {username}"
            db.add(User(username=username, full_name=full_name,
                        password_hash=hash_password("Baspar@1404"), roles=role_objs))
        db.commit()

    users = client.get("/api/users", headers=admin_headers).json()["items"]
    names = {u["username"] for u in users}
    for needed in ("a.jahanmoradi", "n.babaei", "p.moafipour", "e.shahkarami",
                   "m.mahmoudabadi", "a.rezaei", "m.pirayesh", "a.kavousi",
                   "s.shokri", "h.bayramian"):
        assert needed in names, f"کاربر {needed} وجود ندارد"


def test_access_export_headers_map():
    from backend.app.ai.equipment_codes import suggest_mapping
    headers = ["EquipmentCode", "EquipmentName", "Location", "TypeOfEquipment",
               "ProductLine", "Model", "Manufacturer", "InstallationDate",
               "Capacity", "CapacityUnit", "Status", "DailyWorkingHours",
               "Length", "Width", "Height", "Weight", "AutomationLevel"]
    got = {s["header"]: s["field"] for s in suggest_mapping(headers)}
    assert got["EquipmentCode"] == "code"
    assert got["EquipmentName"] == "name"
    assert got["Location"] == "location"
    assert got["TypeOfEquipment"] == "equipment_type"
    assert got["ProductLine"] == "product_line"
    assert got["InstallationDate"] == "install_date"
    assert got["CapacityUnit"] == "capacity_unit"
    assert got["DailyWorkingHours"] == "daily_hours"
    assert got["Length"] == "length" and got["Weight"] == "weight"
    assert got["AutomationLevel"] == "automation"


def test_access_compact_date_parsing():
    from backend.app.modules.bulk_charge import _parse_flexible_date
    d = _parse_flexible_date("13940726")
    assert d is not None and d.year == 2015 and d.month == 10 and d.day == 18
    assert _parse_flexible_date("0") is None
    assert _parse_flexible_date("") is None
    d2 = _parse_flexible_date("14030530")
    assert d2 is not None
