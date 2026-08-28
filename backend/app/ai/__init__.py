"""SELEN AI service layer (§61/§62).

The application only talks to `get_provider()`; concrete providers
(OpenAI-compatible APIs, local models, the built-in rule engine) sit
behind one interface so swapping them never touches business logic.
"""
from __future__ import annotations

import os

from .base import AiProvider
from .rule_based import RuleBasedProvider


def get_provider() -> AiProvider:
    """Provider factory — configured purely by environment (§62).

    SELEN_PROVIDER=rule            → built-in deterministic advisor (default)
    SELEN_PROVIDER=openai_compat   → any OpenAI-compatible chat API
                                      (SELEN_API_URL / SELEN_API_KEY / SELEN_MODEL)
    """
    kind = (os.environ.get("SELEN_PROVIDER") or "rule").strip().lower()
    if kind in ("openai_compat", "openai", "chat"):
        from .openai_compat import OpenAiCompatProvider

        return OpenAiCompatProvider(
            api_url=os.environ.get("SELEN_API_URL", ""),
            api_key=os.environ.get("SELEN_API_KEY", ""),
            model=os.environ.get("SELEN_MODEL", "gpt-4o-mini"),
        )
    return RuleBasedProvider()
