"""SELEN provider interface (§61). AI advice is advisory only (§21/§22)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class AiProvider(ABC):
    name: str = "base"

    @abstractmethod
    def diagnose(self, ctx: dict[str, Any]) -> dict[str, Any]:
        """Return structured advice for a reported problem.

        Shape (§22):
        {
          "probable_failures": [{"title", "likelihood_pct"}],
          "checklist": [...],            # things to inspect
          "suggested_actions": [...],    # ordered plan
          "probable_parts": [...],
          "required_tools": [...],
          "safety_notes": [...],
          "disclaimer": str,
          "provider": str,
        }
        """

    @abstractmethod
    def spare_part_advice(self, parts: list[dict], equipment: list[dict]) -> list[dict]:
        """Critical spare-part recommendations (§24). Returns scored rows;
        humans may always add/edit/delete/override (§24)."""
