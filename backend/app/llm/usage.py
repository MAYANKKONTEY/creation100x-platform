"""Persist LLM usage to the LLMCall table with an estimated cost from config/pricing.yaml."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from sqlalchemy import inspect

from app.llm.base import Usage
from app.models import LLMCall


@lru_cache
def load_pricing(path: Path) -> dict[str, dict[str, float]]:
    if not path.exists():
        return {}
    return (yaml.safe_load(path.read_text()) or {}).get("models", {})


def estimate_cost(usage: Usage, pricing: dict[str, dict[str, float]]) -> float | None:
    price = pricing.get(usage.model)
    if not price:
        return None
    return round(usage.input_tokens / 1e6 * price["input"] + usage.output_tokens / 1e6 * price["output"], 6)


class UsageRecorder:
    """Callback that adds each LLM call to the caller's session (committed with the unit of work).

    Failed calls are recorded too; the caller should commit even when the pipeline step fails
    (the jobs helper does this) so cost and errors remain visible.
    """

    def __init__(self, session, pricing_path: Path):
        self.session = session
        self.pricing = load_pricing(pricing_path)
        self.rows: list[LLMCall] = []

    def __call__(self, usage: Usage) -> None:
        row = self.to_row(usage)
        self.rows.append(row)
        self.session.add(row)

    def to_row(self, usage: Usage) -> LLMCall:
        return LLMCall(
            purpose=usage.purpose,
            model=usage.model,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            stop_reason=usage.stop_reason,
            request_id=usage.request_id,
            latency_ms=usage.latency_ms,
            est_cost_usd=estimate_cost(usage, self.pricing),
            error=usage.error,
        )

    def readd_after_rollback(self) -> None:
        """A rollback discards pending rows; re-add them so spend on failed jobs stays visible."""
        for row in self.rows:
            if not inspect(row).has_identity:  # never committed
                self.session.add(row)
