import pytest

from app.config import REPO_ROOT
from app.skills.loader import SkillError, SkillLoader, validate_skill

EXPECTED = {
    "linkedin-writing", "viral-research", "hook-engineering", "controversial-angle", "storytelling",
    "technical-explainer", "business-analysis", "linkedin-seo", "visual-design", "carousel-design",
    "content-distribution", "content-quality", "linkedin-analytics",
}


@pytest.fixture(scope="module")
def loader():
    return SkillLoader(REPO_ROOT / ".claude" / "skills")


def test_all_thirteen_skills_present(loader):
    assert set(loader.names()) == EXPECTED


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_skill_meets_contract(loader, name):
    skill = loader.get(name)
    assert skill.name == name
    assert len(skill.description) > 60, "description should say what and when"
    assert validate_skill(skill) == []


def test_system_prompt_includes_only_requested_skills(loader):
    prompt = loader.system_prompt("hook-engineering", preamble="You write hooks.")
    assert prompt.startswith("You write hooks.")
    assert '<skill name="hook-engineering">' in prompt
    assert "linkedin-seo" not in prompt
    assert "---\nname:" not in prompt  # frontmatter stripped


def test_reference_loading_and_traversal_guard(loader):
    skill = loader.get("hook-engineering")
    assert "hook-types.md" in skill.references()
    assert "Scoring rubric" in skill.reference("hook-types.md")
    with pytest.raises(SkillError):
        skill.reference("../SKILL.md")


def test_unknown_skill(loader):
    with pytest.raises(SkillError):
        loader.get("nope")
