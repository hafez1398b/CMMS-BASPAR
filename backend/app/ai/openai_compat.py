"""OpenAI-compatible SELEN provider (§62) — any chat-completions endpoint.

Configured purely by environment (SELEN_API_URL / SELEN_API_KEY /
SELEN_MODEL).  On ANY failure the caller falls back to the rule-based
provider so advice is never blocked by provider outages (§32B spirit:
no silent loss of functionality).
"""
from __future__ import annotations

import json
from typing import Any

from .base import AiProvider, DISCLAIMER

_SYSTEM = (
    "شما SELEN، دستیار هوشمند سامانه مدیریت نت بسپار هستید. فقط مشاوره‌دهنده‌اید؛ "
    "هیچ عملیاتی اجرا نمی‌کنید و توصیه شما جایگزین تصمیم انسان مجاز نیست. "
    "پاسخ را فقط با JSON و دقیقاً با این کلیدها بدهید: probable_failures "
    "(آرایه {title, likelihood_pct}), checklist, suggested_actions, probable_parts, "
    "required_tools, safety_notes (آرایه‌های رشته‌ای فارسی)."
)


class OpenAiCompatProvider(AiProvider):
    name = "openai-compat"

    def __init__(self, api_url: str, api_key: str, model: str):
        if not api_url or not api_key:
            raise RuntimeError("SELEN_API_URL / SELEN_API_KEY تنظیم نشده است")
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    def _chat(self, user_prompt: str) -> dict:
        import httpx

        resp = httpx.post(
            f"{self.api_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model,
                "temperature": 0.2,
                "messages": [
                    {"role": "system", "content": _SYSTEM},
                    {"role": "user", "content": user_prompt},
                ],
            },
            timeout=60,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        start, end = content.find("{"), content.rfind("}")
        return json.loads(content[start : end + 1])

    def diagnose(self, ctx: dict[str, Any]) -> dict[str, Any]:
        eq = ctx.get("equipment") or {}
        prompt = (
            f"شرح مشکل: {ctx.get('description') or 'نامشخص'}\n"
            f"تجهیز: {eq.get('name')} (کد {eq.get('code')}) دسته: "
            f"{(eq.get('category') or {}).get('name')}\n"
            f"مشخصات فنی: {json.dumps(eq.get('technical_specs') or {}, ensure_ascii=False)}\n"
            f"سوابق اخیر نت: {ctx.get('recent_history', 0)} مورد\n"
            f"فعالیت‌های PM عقب‌افتاده: {ctx.get('overdue_plans', 0)}\n"
            f"درجه اهمیت تجهیز: {eq.get('criticality')}"
        )
        out = self._chat(prompt)
        out.setdefault("disclaimer", DISCLAIMER)
        out["provider"] = f"{self.name}:{self.model}"
        return out

    def spare_part_advice(self, parts: list[dict], equipment: list[dict]) -> list[dict]:
        # Provider-agnostic scoring stays local; LLM is not needed for §24.
        from .rule_based import RuleBasedProvider

        return RuleBasedProvider().spare_part_advice(parts, equipment)
