from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from getter_api.content import CONTENT_DIR, library, load_library


def test_library_has_both_launch_roles() -> None:
    lib = library()
    assert {"backend-junior-mid", "devops-junior-mid"} <= set(lib.templates)
    for template in lib.templates.values():
        rubric = lib.rubric_for(template)
        assert set(template.levels) == {"junior", "mid"}
        assert rubric.level_bars == {"junior": 2, "mid": 3}
        for skill in rubric.skills:
            assert set(skill.levels) == {1, 2, 3, 4}, skill.id
        for section in template.sections:
            for q in section.questions:
                assert q.look_for, f"{q.id} needs look_for points for the interviewer"


def test_template_with_unknown_skill_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "rubrics").mkdir()
    (tmp_path / "templates").mkdir()
    for kind in ("rubrics", "templates"):
        src = CONTENT_DIR / kind / "backend-junior-mid.yaml"
        (tmp_path / kind / src.name).write_text(src.read_text())
    path = tmp_path / "templates" / "backend-junior-mid.yaml"
    data = yaml.safe_load(path.read_text())
    data["sections"][0]["skills"] = ["telepathy"]
    path.write_text(yaml.safe_dump(data))
    with pytest.raises(ValueError, match="unknown skill telepathy"):
        load_library(tmp_path)
