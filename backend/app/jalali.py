"""Jalali (Persian / Shamsi) calendar utilities.

Canonical storage in the backend is ISO-8601 Gregorian; the UI always
displays and receives Jalali dates (Master-prompt §30).

Conversion is the standard, battle-tested *jalaali-js* algorithm
(Behrang Noraei / Behrouz Babakhani implementation), ported to Python.
Covers Jalali years -61..3177 which is far beyond any practical use.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

JALALI_MONTHS = [
    "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
]

# Week starts on Saturday in Iran.
WEEKDAYS_FA = ["شنبه", "یکشنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه"]

_BREAKS = [
    -61, 9, 38, 199, 426, 686, 756, 818, 1111, 1181, 1210,
    1635, 2060, 2097, 2192, 2262, 2324, 2394, 2456, 3178,
]


def _div(a: int, b: int) -> int:
    """Truncated integer division (jalaali-js semantics)."""
    q = a // b
    if (a % b != 0) and ((a < 0) != (b < 0)):
        q += 1
    return q


def _mod(a: int, b: int) -> int:
    return a - _div(a, b) * b


def _jal_cal(jy: int) -> dict:
    """jalaali-js `jalCal`: leap indicator, Gregorian year and March day of Nowruz."""
    gy = jy + 621
    leap_j = -14
    jp = _BREAKS[0]
    jump = 0
    for i in range(1, len(_BREAKS)):
        jm = _BREAKS[i]
        jump = jm - jp
        if jy < jm:
            break
        leap_j = leap_j + _div(jump, 33) * 8 + _div(_mod(jump, 33), 4)
        jp = jm
    n = jy - jp

    leap_j = leap_j + _div(n, 33) * 8 + _div(_mod(n, 33) + 3, 4)
    if _mod(jump, 33) == 4 and (jump - n) == 4:
        leap_j += 1

    leap_g = _div(gy, 4) - _div((_div(gy, 100) + 1) * 3, 4) - 150
    march = 20 + leap_j - leap_g

    if jump - n < 6:
        n = n - jump + _div(jump + 4, 33) * 33
    leap = _mod(_mod(n + 1, 33) - 1, 4)
    if leap == -1:
        leap = 4

    return {"leap": leap, "gy": gy, "march": march}


def _g2d(gy: int, gm: int, gd: int) -> int:
    """Gregorian date -> Julian-day style serial (jalaali-js `g2d`)."""
    d = _div((gy + _div(gm - 8, 6) + 100100) * 1461, 4) + _div(
        153 * _mod(gm + 9, 12) + 2, 5
    ) + gd - 34840408
    d = d - _div(_div(gy + 100100 + _div(gm - 8, 6), 100) * 3, 4) + 752
    return d


def _d2g(jdn: int) -> tuple[int, int, int]:
    """Julian-day style serial -> Gregorian date (jalaali-js `d2g`)."""
    j = 4 * jdn + 139361631
    j = j + _div(_div(4 * jdn + 183187720, 146097) * 3, 4) * 4 - 3908
    i = _div(_mod(j, 1461), 4) * 5 + 308
    gd = _div(_mod(i, 153), 5) + 1
    gm = _mod(_div(i, 153), 12) + 1
    gy = _div(j, 1461) - 100100 + _div(8 - gm, 6)
    return gy, gm, gd


def _j2d(jy: int, jm: int, jd: int) -> int:
    r = _jal_cal(jy)
    return _g2d(r["gy"], 3, r["march"]) + (jm - 1) * 31 - _div(jm, 7) * (jm - 7) + jd - 1


def _d2j(jdn: int) -> tuple[int, int, int]:
    gy = _d2g(jdn)[0]
    jy = gy - 621
    r = _jal_cal(jy)
    jdn1f = _g2d(gy, 3, r["march"])
    k = jdn - jdn1f
    if k >= 0:
        if k <= 185:
            return jy, 1 + _div(k, 31), _mod(k, 31) + 1
        k -= 186
    else:
        jy -= 1
        k += 179
        if r["leap"] == 1:
            k += 1
    return jy, 7 + _div(k, 30), _mod(k, 30) + 1


def jalali_is_leap(jy: int) -> bool:
    """True when Jalali year `jy` is a leap year (Esfand has 30 days)."""
    return _jal_cal(jy)["leap"] == 0


def jalali_month_length(jy: int, jm: int) -> int:
    if jm <= 6:
        return 31
    if jm <= 11:
        return 30
    return 30 if jalali_is_leap(jy) else 29


def jalali_to_gregorian(jy: int, jm: int, jd: int) -> date:
    """Convert a Jalali date to a Gregorian `datetime.date`."""
    if not (1 <= jm <= 12):
        raise ValueError("ماه شمسی نامعتبر است")
    if jd < 1 or jd > jalali_month_length(jy, jm):
        raise ValueError("روز شمسی نامعتبر است")
    gy, gm, gd = _d2g(_j2d(jy, jm, jd))
    return date(gy, gm, gd)


def gregorian_to_jalali(d: date) -> tuple[int, int, int]:
    """Convert a Gregorian date to Jalali `(jy, jm, jd)`."""
    return _d2j(_g2d(d.year, d.month, d.day))


def parse_jalali(s: str) -> date:
    """Parse a `1404/05/26`-style Jalali string into a Gregorian date."""
    s = (s or "").strip().replace("-", "/").replace(".", "/")
    parts = s.split("/")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        raise ValueError("قالب تاریخ شمسی نامعتبر است (نمونه: ۱۴۰۴/۰۵/۲۶)")
    return jalali_to_gregorian(int(parts[0]), int(parts[1]), int(parts[2]))


def format_jalali(d: date | datetime | None, with_time: bool = False) -> str:
    """Format a stored Gregorian date/datetime as a Persian Jalali string."""
    if d is None:
        return "—"
    if isinstance(d, datetime) and d.tzinfo is not None:
        d = d.astimezone(timezone.utc)
    jy, jm, jd = gregorian_to_jalali(d.date() if isinstance(d, datetime) else d)
    txt = f"{jy:04d}/{jm:02d}/{jd:02d}"
    if with_time and isinstance(d, datetime):
        txt += f" — {d.hour:02d}:{d.minute:02d} UTC"
    return txt


def today_jalali() -> tuple[int, int, int]:
    return gregorian_to_jalali(datetime.now(timezone.utc).date())
