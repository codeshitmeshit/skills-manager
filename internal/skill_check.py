"""Skill standard checks for repository CI."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from internal.errors import CoshSkillsError, ExitCode

SKILL_NAME_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")


class SkillCheckError(CoshSkillsError):
    """Raised when skills do not satisfy repository standards."""

    exit_code = ExitCode.RUNTIME_ERROR


@dataclass(frozen=True)
class SkillCheckResult:
    checked: int
    errors: list[str]

    @property
    def ok(self) -> bool:
        return not self.errors


def check_skills(repo_path: str | Path = ".") -> SkillCheckResult:
    repo = Path(repo_path).expanduser()
    skills_dir = repo / "skills"
    errors: list[str] = []

    if not skills_dir.is_dir():
        return SkillCheckResult(
            checked=0,
            errors=[f"未找到 skills 目录：{skills_dir}"],
        )

    checked = 0
    for entry in sorted(skills_dir.iterdir(), key=lambda item: item.name):
        if not entry.is_dir():
            continue

        checked += 1
        errors.extend(_check_skill_dir(entry))

    if checked == 0:
        errors.append(f"skills 目录下没有可检查的 skill：{skills_dir}")

    return SkillCheckResult(checked=checked, errors=errors)


def check_skills_or_raise(repo_path: str | Path = ".") -> SkillCheckResult:
    result = check_skills(repo_path)
    if result.ok:
        return result

    raise SkillCheckError(
        "skill 标准检查失败：\n{items}".format(
            items="\n".join(f"- {item}" for item in result.errors)
        )
    )


def _check_skill_dir(skill_dir: Path) -> list[str]:
    errors: list[str] = []
    skill_name = skill_dir.name

    if not SKILL_NAME_PATTERN.fullmatch(skill_name):
        errors.append(
            f"{skill_name}: skill 目录名只能使用小写字母、数字和连字符，且不能以连字符开头或结尾。"
        )

    skill_file = skill_dir / "SKILL.md"
    if not skill_file.is_file():
        return [*errors, f"{skill_name}: 缺少 SKILL.md。"]

    text = skill_file.read_text(encoding="utf-8")
    metadata, body_errors = _parse_frontmatter(skill_name, text)
    errors.extend(body_errors)

    name = metadata.get("name")
    if name != skill_name:
        errors.append(f"{skill_name}: front matter 中的 name 必须等于目录名。")

    description = metadata.get("description")
    if description is None or description.strip() == "":
        errors.append(f"{skill_name}: front matter 中必须提供非空 description。")

    body = _body_after_frontmatter(text)
    if not body.strip():
        errors.append(f"{skill_name}: SKILL.md 必须包含正文说明。")
    elif not any(line.startswith("# ") for line in body.splitlines()):
        errors.append(f"{skill_name}: SKILL.md 正文必须包含一级标题。")

    return errors


def _parse_frontmatter(skill_name: str, text: str) -> tuple[dict[str, str], list[str]]:
    if not text.startswith("---\n"):
        return {}, [f"{skill_name}: SKILL.md 必须以 YAML front matter 开头。"]

    end = text.find("\n---\n", 4)
    if end == -1:
        return {}, [f"{skill_name}: SKILL.md 缺少 YAML front matter 结束标记。"]

    metadata: dict[str, str] = {}
    errors: list[str] = []
    raw_frontmatter = text[4:end]
    for line_number, raw_line in enumerate(raw_frontmatter.splitlines(), start=2):
        line = raw_line.strip()
        if not line:
            continue
        if ":" not in line:
            errors.append(f"{skill_name}: front matter 第 {line_number} 行格式非法。")
            continue

        key, value = line.split(":", 1)
        key = key.strip()
        if not key:
            errors.append(f"{skill_name}: front matter 第 {line_number} 行缺少 key。")
            continue
        metadata[key] = value.strip().strip("\"'")

    return metadata, errors


def _body_after_frontmatter(text: str) -> str:
    if not text.startswith("---\n"):
        return text

    end = text.find("\n---\n", 4)
    if end == -1:
        return ""

    return text[end + len("\n---\n") :]
