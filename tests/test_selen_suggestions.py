"""SELEN suggestions: structure (§3B) and checklist (§5B) — advisor only."""


def test_structure_suggestions_for_pump(client, admin_headers):
    r = client.post("/api/selen/structure-suggestions", headers=admin_headers,
                    json={"name": "پمپ سانتریفیوژ", "category": "تأسیسات",
                          "component_type": "پمپ"})
    assert r.status_code == 200, r.text
    d = r.json()
    names = [s["name"] for s in d["subsystems"]]
    assert "سیستم آب‌بندی" in names
    assert any("مکانیکال سیل" in c for s in d["subsystems"] for c in s["components"])
    assert "§14" in d["note"] or "پیشنهاد" in d["note"]
    assert "پمپ" in d["basis"]


def test_structure_suggestions_generic_fallback(client, admin_headers):
    r = client.post("/api/selen/structure-suggestions", headers=admin_headers,
                    json={"name": "دستگاه ناشناخته ایکس"})
    assert r.status_code == 200
    d = r.json()
    assert d["subsystems"], "generic fallback must still suggest something"
    assert "عمومی" in d["basis"]


def test_structure_suggestions_name_keyword_match(client, admin_headers):
    r = client.post("/api/selen/structure-suggestions", headers=admin_headers,
                    json={"name": "لیفتراک تویوتا ۳ تن"})
    assert r.status_code == 200
    names = [s["name"] for s in r.json()["subsystems"]]
    assert "سیستم هیدرولیک" in names


def test_checklist_suggestions_for_pump(client, admin_headers):
    r = client.post("/api/selen/checklist-suggestions", headers=admin_headers,
                    json={"name": "پمپ شماره ۱", "component_type": "پمپ"})
    assert r.status_code == 200
    d = r.json()
    assert any("مکانیکال سیل" in it for it in d["items"])
    assert "پمپ" in d["basis"]


def test_checklist_suggestions_generic(client, admin_headers):
    r = client.post("/api/selen/checklist-suggestions", headers=admin_headers,
                    json={"name": "تجهیز مبهم"})
    assert r.status_code == 200
    assert r.json()["items"], "generic checklist must not be empty"


def test_selen_requires_auth(client):
    r = client.post("/api/selen/structure-suggestions", json={"name": "x"})
    assert r.status_code in (401, 403)
