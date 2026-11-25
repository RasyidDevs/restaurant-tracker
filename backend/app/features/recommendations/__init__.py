"""Fitur: AI saran tindakan untuk staf, dari data seluruh fitur tim.

  signals.py    gabungkan data tim -> TeamSignals
  rules.py      rule engine (utama, deterministik, mudah dites)
  llm.py        lapisan LLM opsional (ringkasan), jatuh ke rule-based tanpa API key
  providers.py  data reservasi & parkir (mock sampai fitur Micheal tersedia)
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .llm import LLMSummarizer
from .rules import RecRules, generate, rule_summary
from .signals import TeamSignals


class RecommendationEngine:
    def __init__(self, rules: RecRules, llm: LLMSummarizer | None = None):
        self.rules = rules
        self.llm = llm

    def snapshot(self, sig: TeamSignals) -> dict[str, Any]:
        recs = generate(sig, self.rules)
        llm_text = self.llm.summary(sig, recs) if self.llm else None
        return {
            "now": sig.now,
            "engine": "rules+llm" if llm_text else "rules",
            "summary": llm_text or rule_summary(sig, recs),
            "rule_summary": rule_summary(sig, recs),
            "llm": self.llm.status() if self.llm else {"enabled": False, "reason": "dimatikan"},
            "rules": asdict(self.rules),
            "occupancy": round(sig.occupancy, 3),
            "data_sources": sig.data_sources,
            "counts": {p: sum(1 for r in recs if r.priority == p) for p in ("tinggi", "sedang", "rendah")},
            "recommendations": [r.to_dict() for r in recs],
        }
