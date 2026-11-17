"""ClaudeClient against a fake SDK object (no network, no API key)."""

from types import SimpleNamespace as NS

import anthropic
import httpx
import pytest
from pydantic import BaseModel

from app.llm.base import LLMError, LLMRefusal, LLMTruncated
from app.llm.claude import FALLBACK_BETA, WEB_SEARCH_TOOL, ClaudeClient, extract_search_result


class Topic(BaseModel):
    title: str


def _resp(**kw):
    base = dict(model="claude-opus-5-5", stop_reason="end_turn", stop_details=None,
                usage=NS(input_tokens=100, output_tokens=20), content=[], parsed_output=None, _request_id="req_1")
    base.update(kw)
    return NS(**base)


class FakeMessages:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def _next(self, **kwargs):
        self.calls.append(kwargs)
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r

    parse = _next
    create = _next


def make_client(responses, **kw):
    msgs = FakeMessages(responses)
    sdk = NS(beta=NS(messages=msgs))
    usages = []
    client = ClaudeClient(sdk, on_usage=usages.append, **kw)
    return client, msgs, usages


def test_parse_sends_expected_request_and_records_usage():
    client, msgs, usages = make_client([_resp(parsed_output=Topic(title="x"))])
    out = client.parse(purpose="t", system="sys", prompt="hi", schema=Topic)
    assert out.title == "x"
    call = msgs.calls[0]
    assert call["model"] == "claude-opus-5-5"
    assert call["thinking"] == {"type": "adaptive"}
    assert call["output_config"] == {"effort": "high"}
    assert call["output_format"] is Topic
    assert call["betas"] == [FALLBACK_BETA] and call["fallbacks"] == "default"
    assert "temperature" not in call
    assert usages[0].input_tokens == 100 and usages[0].request_id == "req_1" and usages[0].purpose == "t"


def test_fallback_can_be_disabled():
    client, msgs, _ = make_client([_resp(parsed_output=Topic(title="x"))], server_fallback=False)
    client.parse(purpose="t", system="s", prompt="p", schema=Topic)
    assert "betas" not in msgs.calls[0] and "fallbacks" not in msgs.calls[0]


def test_refusal_and_truncation_raise():
    client, _, _ = make_client([
        _resp(stop_reason="refusal", stop_details=NS(category="cyber", explanation="nope")),
        _resp(stop_reason="max_tokens"),
    ])
    with pytest.raises(LLMRefusal) as e:
        client.parse(purpose="t", system="s", prompt="p", schema=Topic)
    assert e.value.category == "cyber"
    with pytest.raises(LLMTruncated):
        client.parse(purpose="t", system="s", prompt="p", schema=Topic)


def test_api_errors_are_wrapped_and_logged():
    req = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    err = anthropic.RateLimitError("slow down", response=httpx.Response(429, request=req), body=None)
    client, _, usages = make_client([err])
    with pytest.raises(LLMError, match="429"):
        client.parse(purpose="t", system="s", prompt="p", schema=Topic)
    assert usages[0].error.startswith("RateLimitError")


def _search_blocks():
    return [
        NS(type="server_tool_use", name="web_search"),
        NS(type="web_search_tool_result", content=[
            NS(type="web_search_result", url="https://a.example/1", title="A", page_age="2 days ago"),
            NS(type="web_search_result", url="https://b.example/2", title="B", page_age=None),
        ]),
        NS(type="text", text="Finding one. ", citations=[
            NS(type="web_search_result_location", url="https://a.example/1", title="A", cited_text="quoted text"),
        ]),
    ]


def test_web_research_continues_after_pause_turn_and_extracts_sources():
    first = _resp(stop_reason="pause_turn", content=_search_blocks())
    second = _resp(content=[
        NS(type="web_search_tool_result", content=NS(type="web_search_tool_result_error", error_code="max_uses_exceeded")),
        NS(type="text", text="Finding two.", citations=None),
    ])
    client, msgs, usages = make_client([first, second])
    result = client.web_research(purpose="r", system="s", prompt="topic", max_searches=3, allowed_domains=["a.example"])
    assert len(msgs.calls) == 2
    tool = msgs.calls[0]["tools"][0]
    assert tool == {"type": WEB_SEARCH_TOOL, "name": "web_search", "max_uses": 3, "allowed_domains": ["a.example"]}
    # paused content is sent back as the assistant turn
    assert msgs.calls[1]["messages"][-1]["role"] == "assistant"
    assert [s.url for s in result.sources] == ["https://a.example/1", "https://b.example/2"]
    assert result.citations[0].cited_text == "quoted text"
    assert result.search_errors == ["max_uses_exceeded"]
    assert result.text == "Finding one. Finding two."
    assert len(usages) == 2


def test_extract_search_result_dedupes_sources():
    blocks = _search_blocks() + _search_blocks()
    assert len(extract_search_result(blocks).sources) == 2
