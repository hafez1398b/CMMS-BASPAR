"""SELEN built-in deterministic advisor.

A transparent rule engine over the asset context — no external calls,
always available (audit/offline environments), and the reference
implementation of the provider contract.  It encodes common failure
patterns of industrial equipment; LLM providers extend/replace it.
"""
from __future__ import annotations

from typing import Any

from .base import AiProvider

DISCLAIMER = (
    "توصیه SELEN جایگزین تصمیم نهایی نیست (§22)؛ تصمیم با فرد مجاز است. "
    "پیش از هر اقدام، مقررات HSE و Permit را رعایت کنید."
)

# keyword → failure pattern (Persian + English)
_PATTERNS = [
    {
        "keys": ["صدا", "سر و صدا", "صدای غیر", "نویز", "تق تق", "خرخر", "noise", "صوت"],
        "failures": [("خرابی یا سایش یاتاقان‌ها", 45), ("لرزش ناشی از نابالانسی روتور", 25),
                     ("کوپلینگ یا تسمه نامنظم", 15)],
        "checklist": ["بازرسی یاتاقان‌ها از نظر حرارت و صدا", "کنترل ارتعاش در سه محور",
                      "بررسی هم‌محوری کوپلینگ", "کنترل سفتی تسمه‌ها"],
        "actions": ["ثبت ارتعاش و مقایسه با روند قبلی", "روانکاری یاتاقان‌ها طبق برنامه",
                    "در صورت تداوم صدا، توقف و بررسی یاتاقان"],
        "parts": ["یاتاقان", "کوپلینگ", "تسمه"],
        "tools": ["لرزش‌سنج", "دماسنج تماسی", "استتوسکوپ صنعتی"],
        "safety": ["قبل از بازرسی فیزیکی، تجهیز را ایزوله و LOTO کنید"],
    },
    {
        "keys": ["لرزش", "ارتعاش", "vibration"],
        "failures": [("نابالانسی روتور/پروانه", 40), ("یاتاقان فرسوده", 30),
                     ("شلی فونداسیون یا پیچ‌های نگهدارنده", 20)],
        "checklist": ["اندازه‌گیری ارتعاش و تحلیل فرکانس", "بررسی پیچ‌های فونداسیون",
                      "بازرسی کوپلینگ و الاینمنت"],
        "actions": ["آچارکشی اتصالات و فونداسیون", "بالانس روتور در صورت امکان",
                    "برنامه‌ریزی تعویض یاتاقان اگر روند ارتعاش صعودی است"],
        "parts": ["یاتاقان", "الاینمنت کوپلینگ", "پیچ و مهره ضدلرزش"],
        "tools": ["لرزش‌سنج", "آچار ترکمتر"],
        "safety": ["از ایستادن کنار اجزای دوار در حین کار خودداری کنید"],
    },
    {
        "keys": ["نشتی", "نشت", "چکه", "leak", "روغن ریزی", "روغن‌ریزی"],
        "failures": [("خرابی آب‌بند/مکانیکال سیل", 50), ("شل بودن اتصالات یا شیلنگ‌ها", 25),
                     ("ترک بدنه یا پوسته", 10)],
        "checklist": ["شناسایی دقیق نقطه نشت", "بررسی مکانیکال سیل و گسکت‌ها",
                      "کنترل گشتاور اتصالات", "بررسی سطح و کیفیت روغن"],
        "actions": ["تمیزکاری محل برای یافتن نقطه دقیق نشت", "آچارکشی اتصالات",
                    "تعویض مکانیکال سیل/گسکت در اولین توقف برنامه‌ریزی‌شده"],
        "parts": ["مکانیکال سیل", "گسکت", "اورینگ", "شیلنگ"],
        "tools": ["آچار مناسب", "دستگاه نشت‌یاب (در صورت نیاز)"],
        "safety": ["نشت روغن روی سطوح داغ خطر آفرین است؛ محل را تمیز و علامت‌گذاری کنید"],
    },
    {
        "keys": ["داغ", "حرارت", "دمای بالا", "temperature", "overheat", "گرم شدن"],
        "failures": [("کمبود یا آلودگی روانکار", 40), ("بار بیش از حد یا گرفتگی خنک‌کننده", 30),
                     ("خرابی یاتاقان", 20)],
        "checklist": ["اندازه‌گیری دمای یاتاقان‌ها و بدنه", "بررسی سطح/رنگ روانکار",
                      "تمیزی فین‌ها و مسیر خنک‌کاری", "کنترل جریان و بار موتور"],
        "actions": ["روانکاری/تعویض روغن طبق برنامه", "تمیزکاری سیستم خنک‌کننده",
                    "کاهش بار و پایش روند دما"],
        "parts": ["روانکار", "فیلتر روغن", "یاتاقان"],
        "tools": ["دماسنج مادون‌قرمز", "گیج جریان"],
        "safety": ["سطوح داغ؛ از دستکش مقاوم حرارت استفاده کنید"],
    },
    {
        "keys": ["برق", "روشن نمی", "استارت نمی", "trip", "تریپ", "فیوز", "electrical", "نوسان"],
        "failures": [("ایراد مدار تغذیه/کنترل", 35), ("بار مکانیکی گیر کرده (قفل روتور)", 30),
                     ("خرابی موتور یا عایقی سیم‌پیچ", 25)],
        "checklist": ["بررسی ولتاژ و فیوزها", "کنترل رله‌های حفاظتی و تاریخچه تریپ",
                      "تست مقاومت عایقی سیم‌پیچ (میگر)", "بازرسی مکانیکی برای گیرپاژ"],
        "actions": ["ریست ایمن و پایش جریان راه‌اندازی", "رفع گیر مکانیکی در صورت وجود",
                    "ارجاع به برق برای تست عایقی"],
        "parts": ["کنتاکتور", "فیوز", "رله حرارتی"],
        "tools": ["مولتی‌متر", "میگر", "کلمپ متر"],
        "safety": ["کار روی مدار برق فقط با مجوز و فرد ذی‌صلاح؛ LOTO الزامی است"],
    },
    {
        "keys": ["فشار", "pressure", "دبی", "خلأ", "vacuum"],
        "failures": [("افت عملکرد به دلیل سایش داخلی", 35), ("گرفتگی فیلتر/مسیر مکش", 30),
                      ("نشتی در مسیر یا شیرها", 20)],
        "checklist": ["قرائت فشار/دبی و مقایسه با نقطه کار نامی",
                      "بررسی فیلترها و صافی‌ها", "بازرسی شیرهای مسیر"],
        "actions": ["تعویض/تمیزکاری فیلترها", "کنترل و کالیبره سنسورهای فشار",
                    "بررسی رینگ/پروانه در صورت ادامه افت"],
        "parts": ["فیلتر", "رینگ سایشی", "پروانه"],
        "tools": ["مانومتر کالیبره"],
        "safety": ["قبل از باز کردن مسیر تحت فشار، تخلیه و ایزوله کنید"],
    },
    {
        "keys": ["بوی", "بوی سوختگی", "دود", "smoke", "سوختگی"],
        "failures": [("اتصال کوتاه یا اضافه‌بار الکتریکی", 45), ("اصطکاک مکانیکی شدید", 30)],
        "checklist": ["قطع فوری و بررسی چشمی", "بازرسی سیم‌پیچ و ترمینال‌ها",
                      "بررسی نقاط اصطکاک مکانیکی"],
        "actions": ["توقف اضطراری تجهیز", "اطلاع به سرپرست و HSE", "عیب‌یابی قبل از راه‌اندازی مجدد"],
        "parts": ["سیم‌پیچ", "ترمینال", "یاتاقان"],
        "tools": ["میگر", "دوربین حرارتی"],
        "safety": ["خطر آتش‌سوزی؛ کپسول اطفاء در دسترس باشد و تجهیز دیگر روشن نشود"],
    },
]

_GENERIC = {
    "failures": [("نیازمند عیب‌یابی میدانی با داده‌های بیشتر", 50)],
    "checklist": ["ثبت دقیق علائم (صدا، دما، لرزش، نشتی)", "بررسی آخرین سوابق نت تجهیز",
                  "کنترل پارامترهای عملیاتی نسبت به نقطه نامی"],
    "actions": ["جمع‌آوری اطلاعات تکمیلی و شرح علائم برای SELEN",
                "بازرسی چشمی ایمن‌سازی‌شده", "ارجاع به سرپرست در صورت ابهام"],
    "parts": [],
    "tools": ["ابزار عمومی نت"],
    "safety": ["قبل از هر بازرسی، ایزوله‌سازی و LOTO انجام شود"],
}


class RuleBasedProvider(AiProvider):
    name = "rule-based"

    def diagnose(self, ctx: dict[str, Any]) -> dict[str, Any]:
        text = (ctx.get("description") or "").lower()
        matched = [p for p in _PATTERNS if any(k in text for k in p["keys"])]
        if not matched:
            base = _GENERIC
        else:
            # merge matched patterns, keep strongest first
            base = matched[0]

        eq = ctx.get("equipment") or {}
        crit = eq.get("criticality", "medium")
        failures = [{"title": t, "likelihood_pct": pct} for t, pct in base["failures"]]

        checklist = list(base["checklist"])
        actions = list(base["actions"])
        safety = list(base["safety"])

        # context-aware augmentation
        specs = eq.get("technical_specs") or {}
        if specs:
            checklist.append("مقایسه مقادیر فعلی با مشخصات نامی: " +
                             "، ".join(f"{k}: {v}" for k, v in list(specs.items())[:4]))
        if crit in ("critical", "high"):
            safety.insert(0, "این تجهیز بحرانی است؛ پیش از کار، هماهنگی با مدیر فنی الزامی است")
            actions.insert(0, "اعلام فوری به سرپرست/مدیر فنی به دلیل بحرانی بودن تجهیز")
        if ctx.get("recent_history"):
            checklist.append(f"بررسی {ctx['recent_history']} سابقه نت اخیر همین تجهیز (الگوی تکرار خرابی)")
        if ctx.get("overdue_plans"):
            actions.append(f"{ctx['overdue_plans']} فعالیت PM عقب‌افتاده برای این تجهیز وجود دارد؛ ابتدا انجام شود")

        return {
            "probable_failures": failures,
            "checklist": checklist,
            "suggested_actions": actions,
            "probable_parts": base["parts"],
            "required_tools": base["tools"],
            "safety_notes": safety,
            "disclaimer": DISCLAIMER,
            "provider": self.name,
        }

    def spare_part_advice(self, parts: list[dict], equipment: list[dict]) -> list[dict]:
        """§24 scoring: usage/failure proxies + lead time + equipment criticality
        + stock level + alternative availability."""
        eq_crit = {e["id"]: e.get("criticality", "medium") for e in equipment}
        crit_w = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        rows = []
        for p in parts:
            score = 0
            reasons = []
            stock, minq = p.get("stock_qty", 0) or 0, p.get("min_qty", 0) or 0
            if stock <= minq:
                score += 30
                reasons.append("موجودی در/زیر حد سفارش")
            eqc = eq_crit.get(p.get("equipment_id"))
            if eqc:
                w = crit_w.get(eqc, 2)
                score += w * 8
                if w >= 3:
                    reasons.append("تجهیز مرتبط بحرانی/با اهمیت")
            lt = p.get("lead_time_days") or 0
            if lt >= 30:
                score += 15
                reasons.append(f"زمان تأمین طولانی ({lt} روز)")
            if not p.get("alternative_part"):
                score += 8
                reasons.append("بدون قطعه جایگزین")
            if p.get("criticality") == "critical":
                score += 20
                reasons.append("قطعه با درجه اهمیت بحرانی")
            rows.append({**p, "selen_score": min(100, score), "selen_reasons": reasons,
                         "suggested": "بله" if score >= 40 else "خیر"})
        rows.sort(key=lambda r: -r["selen_score"])
        return rows
