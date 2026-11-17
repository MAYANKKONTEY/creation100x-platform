"""Load Claude Code skills from .claude/skills so the backend uses the same prompts as Claude Code.

Progressive disclosure: callers load only the skills a pipeline stage needs, and reference
files only when a step asks for them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

REQUIRED_SECTIONS = (
    "Purpose",
    "Instructions",
    "Workflow",
    "Reusable prompts",
    "Examples",
    "Quality checklist",
    "Output structure",
)

_FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n(.*)\Z", re.DOTALL)


class SkillError(ValueError):
    pass


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    body: str
    path: Path

    @property
    def sections(self) -> list[str]:
        return re.findall(r"^## (.+?)\s*$", self.body, flags=re.MULTILINE)

    def references(self) -> list[str]:
        ref_dir = self.path.parent / "references"
        return sorted(p.name for p in ref_dir.glob("*.md")) if ref_dir.is_dir() else []

    def reference(self, filename: str) -> str:
        ref = (self.path.parent / "references" / filename).resolve()
        if ref.parent != (self.path.parent / "references").resolve() or not ref.is_file():
            raise SkillError(f"Unknown reference {filename!r} for skill {self.name}")
        return ref.read_text(encoding="utf-8")


def parse_skill(path: Path) -> Skill:
    text = path.read_text(encoding="utf-8")
    m = _FRONTMATTER.match(text)
    if not m:
        raise SkillError(f"{path}: missing YAML frontmatter")
    meta = yaml.safe_load(m.group(1)) or {}
    name, description = meta.get("name"), meta.get("description")
    if not name or not description:
        raise SkillError(f"{path}: frontmatter needs name and description")
    if name != path.parent.name:
        raise SkillError(f"{path}: name {name!r} does not match folder {path.parent.name!r}")
    return Skill(name=name, description=str(description).strip(), body=m.group(2).strip(), path=path)


def validate_skill(skill: Skill) -> list[str]:
    problems = [f"missing section: {s}" for s in REQUIRED_SECTIONS if s not in skill.sections]
    if "### Good" not in skill.body:
        problems.append("missing good example (### Good)")
    if "### Bad" not in skill.body:
        problems.append("missing bad example (### Bad)")
    return problems


class SkillLoader:
    def __init__(self, skills_dir: Path):
        self.skills_dir = skills_dir
        self._cache: dict[str, Skill] = {}

    def names(self) -> list[str]:
        return sorted(p.parent.name for p in self.skills_dir.glob("*/SKILL.md"))

    def get(self, name: str) -> Skill:
        if name not in self._cache:
            path = self.skills_dir / name / "SKILL.md"
            if not path.is_file():
                raise SkillError(f"Unknown skill {name!r}")
            self._cache[name] = parse_skill(path)
        return self._cache[name]

    def all(self) -> list[Skill]:
        return [self.get(n) for n in self.names()]

    def system_prompt(self, *names: str, preamble: str = "") -> str:
        """Compose a system prompt from the named skills only."""
        parts = [preamble.strip()] if preamble.strip() else []
        for n in names:
            s = self.get(n)
            parts.append(f'<skill name="{s.name}">\n{s.body}\n</skill>')
        return "\n\n".join(parts)
