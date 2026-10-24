"""Rubrics and interview templates, stored as versioned YAML in the repo."""

from __future__ import annotations

import ast
from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, model_validator

CONTENT_DIR = Path(__file__).parent

Level = Literal["junior", "mid"]


class Skill(BaseModel):
    id: str
    name: str
    description: str
    levels: dict[int, str]


class Rubric(BaseModel):
    id: str
    version: int
    role_family: str
    title: str
    scale: dict[int, str]
    level_bars: dict[Level, int]
    skills: list[Skill] = Field(min_length=1)

    @property
    def ref(self) -> str:
        return f"{self.id}@{self.version}"

    def skill(self, skill_id: str) -> Skill:
        for s in self.skills:
            if s.id == skill_id:
                return s
        raise KeyError(skill_id)

    @property
    def skill_ids(self) -> list[str]:
        return [s.id for s in self.skills]


class CodingTest(BaseModel):
    """A visible test: a Python expression run after the candidate's code, and its result."""

    name: str
    expression: str
    expected: str  # a Python literal, compared with ast.literal_eval


class CodingTask(BaseModel):
    language: Literal["python"] = "python"
    starter_code: str
    tests: list[CodingTest] = Field(min_length=1)


class Question(BaseModel):
    id: str
    prompt: str
    look_for: list[str] = Field(default_factory=list)
    coding: CodingTask | None = None


class Section(BaseModel):
    id: str
    title: str
    time_limit_minutes: float = Field(gt=0)
    max_followups: int = Field(ge=0, le=5)
    skills: list[str] = Field(min_length=1)
    questions: list[Question] = Field(min_length=1)


class Template(BaseModel):
    id: str
    version: int
    title: str
    rubric: str
    levels: list[Level]
    intro: str
    sections: list[Section] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique_ids(self) -> Template:
        section_ids = [s.id for s in self.sections]
        question_ids = [q.id for s in self.sections for q in s.questions]
        if len(set(section_ids)) != len(section_ids):
            raise ValueError(f"template {self.id}: duplicate section ids")
        if len(set(question_ids)) != len(question_ids):
            raise ValueError(f"template {self.id}: duplicate question ids")
        for q in (q for s in self.sections for q in s.questions if q.coding):
            assert q.coding is not None
            for test in q.coding.tests:
                try:
                    ast.literal_eval(test.expected)
                    ast.parse(test.expression, mode="eval")
                except (ValueError, SyntaxError) as exc:
                    raise ValueError(f"question {q.id}: bad test {test.name!r}: {exc}") from exc
        return self

    @property
    def ref(self) -> str:
        return f"{self.id}@{self.version}"


class ContentLibrary(BaseModel):
    rubrics: dict[str, Rubric]
    templates: dict[str, Template]

    @model_validator(mode="after")
    def _templates_match_rubrics(self) -> ContentLibrary:
        for t in self.templates.values():
            rubric = self.rubrics.get(t.rubric)
            if rubric is None:
                raise ValueError(f"template {t.id} uses unknown rubric {t.rubric}")
            covered: set[str] = set()
            for section in t.sections:
                for skill_id in section.skills:
                    if skill_id not in rubric.skill_ids:
                        raise ValueError(
                            f"template {t.id} section {section.id}: unknown skill {skill_id}"
                        )
                    covered.add(skill_id)
            missing = set(rubric.skill_ids) - covered
            if missing:
                raise ValueError(f"template {t.id} never assesses: {sorted(missing)}")
        return self

    def rubric_for(self, template: Template) -> Rubric:
        return self.rubrics[template.rubric]


def _load_dir(path: Path) -> list[dict[str, object]]:
    items = []
    for f in sorted(path.glob("*.yaml")):
        with f.open() as fh:
            items.append(yaml.safe_load(fh))
    return items


def load_library(base: Path = CONTENT_DIR) -> ContentLibrary:
    rubrics = [Rubric.model_validate(d) for d in _load_dir(base / "rubrics")]
    templates = [Template.model_validate(d) for d in _load_dir(base / "templates")]
    return ContentLibrary(
        rubrics={r.id: r for r in rubrics},
        templates={t.id: t for t in templates},
    )


@lru_cache(maxsize=1)
def library() -> ContentLibrary:
    return load_library()
