"""Deterministic in-memory LLM for tests and offline development."""

from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Callable
from typing import Any

from app.llm.base import SearchResult, T, Usage, UsageCallback


class FakeLLM:
    model = "fake-llm"

    def __init__(self, on_usage: UsageCallback | None = None):
        self._parse: dict[str, deque] = defaultdict(deque)
        self._search: deque[SearchResult] = deque()
        self.calls: list[dict[str, Any]] = []
        self.on_usage = on_usage

    def queue_parse(self, schema_name: str, value: Any | Callable[[str], Any]) -> None:
        self._parse[schema_name].append(value)

    def queue_search(self, result: SearchResult) -> None:
        self._search.append(result)

    def _usage(self, purpose: str) -> None:
        if self.on_usage:
            self.on_usage(Usage(purpose=purpose, model=self.model, input_tokens=10, output_tokens=5, stop_reason="end_turn"))

    def parse(self, *, purpose: str, system: str, prompt: str, schema: type[T], max_tokens: int = 16000) -> T:
        self.calls.append({"kind": "parse", "purpose": purpose, "system": system, "prompt": prompt})
        queue = self._parse[schema.__name__]
        if not queue:
            raise AssertionError(f"FakeLLM: no queued response for {schema.__name__}")
        value = queue.popleft()
        value = value(prompt) if callable(value) else value
        self._usage(purpose)
        return value if isinstance(value, schema) else schema.model_validate(value)

    def web_research(self, *, purpose: str, system: str, prompt: str, max_searches: int = 5,
                     allowed_domains=None, blocked_domains=None) -> SearchResult:
        self.calls.append({"kind": "search", "purpose": purpose, "system": system, "prompt": prompt})
        if not self._search:
            raise AssertionError("FakeLLM: no queued search result")
        self._usage(purpose)
        return self._search.popleft()
