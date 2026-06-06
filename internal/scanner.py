"""Skill repository scanner."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from internal.errors import CoshSkillsError, ExitCode
from internal.skill_metadata import parse_cli_scope, parse_frontmatter


class ScanError(CoshSkillsError):
    """Raised when the skill repository structure is invalid."""

    exit_code = ExitCode.RUNTIME_ERROR


@dataclass(frozen=True)
class Skill:
    name: str
    path: Path
    cli_scope: tuple[str, ...] | None = None


@dataclass(frozen=True)
class ScanResult:
    skills: list[Skill]
    warnings: list[str]


def scan_skills(repo_path: str | Path) -> ScanResult:
    repo = Path(repo_path).expanduser()
    skills_dir = repo / "skills"
    if not skills_dir.is_dir():
        raise ScanError(
            "未找到 skills 目录，当前仓库结构不符合要求。\n\n"
            "期望路径：\n"
            f"  {skills_dir}\n\n"
            "请确认 repo_path 是否正确，或检查 skill 仓库结构。"
        )

    skills: list[Skill] = []
    warnings: list[str] = []
    for entry in sorted(skills_dir.iterdir(), key=lambda item: item.name):
        if not entry.is_dir():
            continue

        skill_file = entry / "SKILL.md"
        if skill_file.is_file():
            metadata, metadata_errors = parse_frontmatter(skill_file.read_text(encoding="utf-8"))
            cli_scope, scope_errors = parse_cli_scope(metadata)
            errors = [*metadata_errors, *scope_errors]
            if errors:
                raise ScanError(
                    "{name}: SKILL.md 元数据非法：\n{items}".format(
                        name=entry.name,
                        items="\n".join(f"- {item}" for item in errors),
                    )
                )
            skills.append(Skill(name=entry.name, path=entry, cli_scope=cli_scope))
        else:
            warnings.append(f"warning: {entry.name} 缺少 SKILL.md，已跳过。")

    return ScanResult(skills=skills, warnings=warnings)
