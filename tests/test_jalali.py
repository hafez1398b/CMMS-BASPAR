"""Jalali conversion correctness — dates are business-critical (§30)."""
from datetime import date

import pytest

from backend.app.jalali import (
    format_jalali, gregorian_to_jalali, jalali_is_leap, jalali_to_gregorian,
    parse_jalali,
)

KNOWN_PAIRS = [
    ((1404, 1, 1), date(2025, 3, 21)),
    ((1403, 12, 30), date(2025, 3, 20)),   # 1403 is leap
    ((1402, 1, 1), date(2023, 3, 21)),
    ((1399, 1, 1), date(2020, 3, 20)),     # 1399 is leap
    ((1400, 1, 1), date(2021, 3, 21)),
    ((1405, 5, 26), date(2026, 8, 17)),
    ((1370, 6, 15), date(1991, 9, 6)),
]


@pytest.mark.parametrize("j,g", KNOWN_PAIRS)
def test_jalali_to_gregorian(j, g):
    assert jalali_to_gregorian(*j) == g


@pytest.mark.parametrize("j,g", KNOWN_PAIRS)
def test_gregorian_to_jalali(j, g):
    assert gregorian_to_jalali(g) == j


def test_roundtrip_many_years():
    d = date(1980, 1, 1)
    from datetime import timedelta
    for _ in range(0, 20000, 7):  # ~55 years, weekly steps
        j = gregorian_to_jalali(d)
        assert jalali_to_gregorian(*j) == d
        d += timedelta(days=7)


def test_leap_years():
    assert jalali_is_leap(1399)
    assert jalali_is_leap(1403)
    assert not jalali_is_leap(1402)
    assert not jalali_is_leap(1404)


def test_parse_and_format():
    assert parse_jalali("1404/05/26") == date(2025, 8, 17)
    assert parse_jalali("1405/05/26") == date(2026, 8, 17)
    assert format_jalali(date(2026, 8, 17)) == "1405/05/26"
    with pytest.raises(ValueError):
        parse_jalali("1404/13/01")
    with pytest.raises(ValueError):
        parse_jalali("not-a-date")
