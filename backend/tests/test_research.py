from app.config import REPO_ROOT
from app.llm.base import Citation, SearchResult, WebSource
from app.models import ClaimStatus
from app.research.service import ExtractedClaim, ResearchExtraction, ResearchService, verify_claim
from app.skills.loader import SkillLoader

RETRIEVED = {"https://dev.example/survey", "https://news.example/agents"}
CITES = [
    Citation(url="https://dev.example/survey/", cited_text="76% of all respondents are using or planning to use AI tools in their development process"),
    Citation(url="https://news.example/agents", cited_text="The company said agent adoption doubled among enterprise customers this year"),
]


def _claim(text, urls, ctype="fact", quote=None):
    return ExtractedClaim(text=text, claim_type=ctype, source_urls=urls, supporting_quote=quote)


def test_unretrieved_url_is_unsupported():
    status, kept, reason = verify_claim(_claim("Made-up fact", ["https://invented.example/x"]), RETRIEVED, CITES)
    assert status == ClaimStatus.UNSUPPORTED and kept == []
    assert "invented.example" in reason


def test_no_urls_is_unsupported():
    assert verify_claim(_claim("Bare claim", []), RETRIEVED, CITES)[0] == ClaimStatus.UNSUPPORTED


def test_verbatim_quote_with_matching_number_is_verified():
    c = _claim("76% of developers use or plan to use AI tools", ["https://dev.example/survey"], "statistic",
               quote="76% of all respondents are using or planning to use AI tools")
    status, kept, _ = verify_claim(c, RETRIEVED, CITES)
    assert status == ClaimStatus.VERIFIED
    assert kept == ["https://dev.example/survey"]


def test_overlap_without_quote_is_only_sourced():
    # High word overlap but reversed meaning: overlap must never verify.
    c = _claim("Agent adoption among enterprise customers fell this year", ["https://news.example/agents"])
    status, _, reason = verify_claim(c, RETRIEVED, CITES)
    assert status == ClaimStatus.SOURCED and "no verbatim" in reason


def test_number_not_in_citation_downgrades_to_sourced():
    c = _claim("92% of respondents are using AI tools in development", ["https://dev.example/survey"], "statistic",
               quote="respondents are using or planning to use AI tools")
    status, _, reason = verify_claim(c, RETRIEVED, CITES)
    assert status == ClaimStatus.SOURCED and "numbers" in reason


def test_exact_quote_verifies():
    c = _claim("Enterprise agent adoption grew sharply", ["https://news.example/agents"],
               quote="agent adoption doubled among enterprise customers")
    assert verify_claim(c, RETRIEVED, CITES)[0] == ClaimStatus.VERIFIED


def test_fabricated_quote_does_not_verify():
    c = _claim("Enterprise agent adoption grew sharply", ["https://news.example/agents"],
               quote="agent adoption tripled across every industry worldwide")
    assert verify_claim(c, RETRIEVED, CITES)[0] == ClaimStatus.SOURCED


def test_retrieved_without_citation_is_sourced():
    status, _, reason = verify_claim(_claim("Some claim about agents", ["https://news.example/agents"]),
                                     RETRIEVED, [])
    assert status == ClaimStatus.SOURCED and "no citation" in reason


def _search():
    return SearchResult(
        text="Survey shows broad AI tool use. Enterprise agent adoption doubled.",
        sources=[WebSource("https://dev.example/survey", "Survey", "1 month ago"),
                 WebSource("https://news.example/agents", "Agents news", "3 days ago")],
        citations=CITES,
        model="claude-opus-5-5",
    )


def test_service_end_to_end(session, fake_llm):
    fake_llm.queue_search(_search())
    fake_llm.queue_parse("ResearchExtraction", ResearchExtraction(
        summary="AI tool use is widespread; agent adoption is growing.",
        claims=[
            _claim("76% of respondents are using or planning to use AI tools in development", ["https://dev.example/survey"], "statistic",
                   quote="76% of all respondents are using or planning to use AI tools"),
            _claim("Agent adoption doubled among enterprise customers this year", ["https://news.example/agents"],
                   quote="agent adoption doubled among enterprise customers"),
            _claim("AI tool use is widespread", ["https://dev.example/survey"]),
            _claim("Half of all startups will fail at AI", ["https://made-up.example"], "statistic"),
        ],
        counter_evidence=["Trust in AI output remains low"],
    ))
    brief = ResearchService(fake_llm, SkillLoader(REPO_ROOT / ".claude" / "skills")).run(session, "AI tools adoption")
    assert brief.id is not None
    assert brief.status == "complete"
    assert [c.status for c in brief.claims] == ["verified", "verified", "sourced", "unsupported"]
    assert len(brief.evidence) == 2
    assert brief.evidence[0].cited_texts  # quote linked to evidence row despite trailing slash
    assert brief.stats["claims"] == {"verified": 2, "sourced": 1, "unsupported": 1}

    gather, extract = fake_llm.calls
    assert '<skill name="viral-research">' in gather["system"]
    assert "untrusted data" in extract["system"]
    assert "<sources>" in extract["prompt"] and "https://dev.example/survey" in extract["prompt"]


def test_service_with_no_sources_skips_extraction(session, fake_llm):
    fake_llm.queue_search(SearchResult(text="", sources=[], search_errors=["too_many_requests"]))
    brief = ResearchService(fake_llm, SkillLoader(REPO_ROOT / ".claude" / "skills")).run(session, "obscure topic")
    assert brief.status == "insufficient_evidence"
    assert brief.claims == []
    assert len(fake_llm.calls) == 1
    assert brief.stats["search_errors"] == ["too_many_requests"]
