"""Provider-neutral LLM interface used by pipeline services. Implementations: ClaudeClient, FakeLLM."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMError(Exception):
    """Any failure talking to the model."""


class LLMNotConfigured(LLMError):
    """No API credentials configured."""


class LLMRefusal(LLMError):
    def __init__(self, category: str | None, explanation: str | None):
        self.category = category
        self.explanation = explanation
        super().__init__(f"Model declined (category={category}): {explanation}")


class LLMTruncated(LLMError):
    """Response hit max_tokens before completing."""


@dataclass
class Usage:
    purpose: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    stop_reason: str | None = None
    request_id: str | None = None
    latency_ms: int = 0
    error: str | None = None


UsageCallback = Callable[[Usage], None]


@dataclass(frozen=True)
class WebSource:
    url: str
    title: str | None = None
    page_age: str | None = None


@dataclass(frozen=True)
class Citation:
    url: str
    cited_text: str
    title: str | None = None


@dataclass
class SearchResult:
    text: str
    sources: list[WebSource] = field(default_factory=list)
    citations: list[Citation] = field(default_factory=list)
    search_errors: list[str] = field(default_factory=list)
    model: str | None = None


class LLMClient(Protocol):
    model: str

    def parse(
        self,
        *,
        purpose: str,
        system: str,
        prompt: str,
        schema: type[T],
        max_tokens: int = 16000,
    ) -> T: ...

    def web_research(
        self,
        *,
        purpose: str,
        system: str,
        prompt: str,
        max_searches: int = 5,
        allowed_domains: list[str] | None = None,
        blocked_domains: list[str] | None = None,
    ) -> SearchResult: ...
