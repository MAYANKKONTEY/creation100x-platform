"""Claude implementation of LLMClient using the official Anthropic Python SDK.

- Structured output: `beta.messages.parse(output_format=PydanticModel)`.
- Web research: `web_search_20260209` server tool; sources are read from tool-result
  blocks (ground truth), never from model prose.
- Refusals raise LLMRefusal; max_tokens raises LLMTruncated.
- Server-side refusal fallback (`fallbacks="default"`) is on by default and can be disabled.
"""

from __future__ import annotations

import time
from typing import Any

import anthropic

from app.llm.base import (
    Citation,
    LLMError,
    LLMRefusal,
    LLMTruncated,
    SearchResult,
    T,
    Usage,
    UsageCallback,
    WebSource,
)

FALLBACK_BETA = "server-side-fallback-2026-07-01"
WEB_SEARCH_TOOL = "web_search_20260209"
MAX_PAUSE_CONTINUATIONS = 4


def _get(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


class ClaudeClient:
    def __init__(
        self,
        sdk: anthropic.Anthropic,
        *,
        model: str = "claude-opus-5-5",
        effort: str = "high",
        server_fallback: bool = True,
        on_usage: UsageCallback | None = None,
    ):
        self.sdk = sdk
        self.model = model
        self.effort = effort
        self.server_fallback = server_fallback
        self.on_usage = on_usage

    # ---------------------------------------------------------------- helpers
    def _common_kwargs(self) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "thinking": {"type": "adaptive"},
            "output_config": {"effort": self.effort},
        }
        if self.server_fallback:
            kwargs["betas"] = [FALLBACK_BETA]
            kwargs["fallbacks"] = "default"
        return kwargs

    def _record(self, purpose: str, started: float, response: Any = None, error: str | None = None) -> None:
        if not self.on_usage:
            return
        usage = _get(response, "usage") if response is not None else None
        self.on_usage(
            Usage(
                purpose=purpose,
                model=_get(response, "model", self.model) if response is not None else self.model,
                input_tokens=int(_get(usage, "input_tokens", 0) or 0),
                output_tokens=int(_get(usage, "output_tokens", 0) or 0),
                stop_reason=_get(response, "stop_reason") if response is not None else None,
                request_id=_get(response, "_request_id") if response is not None else None,
                latency_ms=int((time.monotonic() - started) * 1000),
                error=error,
            )
        )

    @staticmethod
    def _check_stop(response: Any) -> None:
        stop = _get(response, "stop_reason")
        if stop == "refusal":
            details = _get(response, "stop_details")
            raise LLMRefusal(_get(details, "category"), _get(details, "explanation"))
        if stop == "max_tokens":
            raise LLMTruncated("Response truncated at max_tokens")

    def _call(self, fn, purpose: str, **kwargs: Any) -> Any:
        started = time.monotonic()
        try:
            response = fn(**kwargs)
        except anthropic.APIStatusError as e:  # includes RateLimitError, BadRequestError, ...
            self._record(purpose, started, error=f"{type(e).__name__}: {e.status_code}")
            raise LLMError(f"Claude API error {e.status_code}: {e.message}") from e
        except anthropic.APIConnectionError as e:
            self._record(purpose, started, error="APIConnectionError")
            raise LLMError("Could not reach the Claude API") from e
        self._record(purpose, started, response)
        return response

    # ---------------------------------------------------------------- public
    def parse(self, *, purpose: str, system: str, prompt: str, schema: type[T], max_tokens: int = 16000) -> T:
        response = self._call(
            self.sdk.beta.messages.parse,
            purpose,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
            output_format=schema,
            **self._common_kwargs(),
        )
        self._check_stop(response)
        parsed = _get(response, "parsed_output")
        if parsed is None:
            raise LLMError("Structured output missing from response")
        return parsed

    def web_research(
        self,
        *,
        purpose: str,
        system: str,
        prompt: str,
        max_searches: int = 5,
        allowed_domains: list[str] | None = None,
        blocked_domains: list[str] | None = None,
    ) -> SearchResult:
        tool: dict[str, Any] = {"type": WEB_SEARCH_TOOL, "name": "web_search", "max_uses": max_searches}
        if allowed_domains:
            tool["allowed_domains"] = allowed_domains
        elif blocked_domains:
            tool["blocked_domains"] = blocked_domains

        messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]
        all_blocks: list[Any] = []
        response = None
        for _ in range(MAX_PAUSE_CONTINUATIONS + 1):
            response = self._call(
                self.sdk.beta.messages.create,
                purpose,
                max_tokens=16000,
                system=system,
                messages=messages,
                tools=[tool],
                **self._common_kwargs(),
            )
            all_blocks.extend(_get(response, "content", []) or [])
            if _get(response, "stop_reason") != "pause_turn":
                break
            # Server tool turn paused: send the assistant content back so the server continues.
            messages = [*messages, {"role": "assistant", "content": _get(response, "content")}]
        self._check_stop(response)
        result = extract_search_result(all_blocks)
        result.model = _get(response, "model", self.model)
        return result


def extract_search_result(blocks: list[Any]) -> SearchResult:
    """Pull text, retrieved sources and citations out of response content blocks."""
    texts: list[str] = []
    sources: dict[str, WebSource] = {}
    citations: list[Citation] = []
    errors: list[str] = []
    for block in blocks:
        btype = _get(block, "type")
        if btype == "web_search_tool_result":
            content = _get(block, "content")
            if isinstance(content, list):
                for item in content:
                    url = _get(item, "url")
                    if url and url not in sources:
                        sources[url] = WebSource(url=url, title=_get(item, "title"), page_age=_get(item, "page_age"))
            else:  # error object, not a list
                errors.append(str(_get(content, "error_code", "unknown_error")))
        elif btype == "text":
            texts.append(_get(block, "text", ""))
            for c in _get(block, "citations", None) or []:
                url, cited = _get(c, "url"), _get(c, "cited_text")
                if url and cited:
                    citations.append(Citation(url=url, cited_text=cited, title=_get(c, "title")))
    return SearchResult(text="".join(texts).strip(), sources=list(sources.values()), citations=citations, search_errors=errors)


def build_claude_client(settings, on_usage: UsageCallback | None = None) -> ClaudeClient:
    from app.llm.base import LLMNotConfigured

    if not settings.llm_configured:
        raise LLMNotConfigured("ANTHROPIC_API_KEY is not set")
    sdk = anthropic.Anthropic(api_key=settings.anthropic_api_key.get_secret_value(), max_retries=3)
    return ClaudeClient(
        sdk,
        model=settings.claude_model,
        effort=settings.claude_effort,
        server_fallback=settings.claude_server_fallback,
        on_usage=on_usage,
    )
