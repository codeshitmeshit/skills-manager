"""Post-install verification."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

from cosh_skills.errors import CoshSkillsError, ExitCode
from cosh_skills.scanner import Skill

CliRecognizer = Callable[[str, list[str]], tuple[bool, str]]


class VerificationError(CoshSkillsError):
    """Raised when installed skills fail verification."""

    exit_code = ExitCode.RUNTIME_ERROR


@dataclass(frozen=True)
class CliVerificationResult:
    recognized: bool
    message: str


@dataclass(frozen=True)
class VerificationResult:
    file_verified: bool
    cli_verified: bool
    warnings: list[str]


def verify_installation(
    skills: Iterable[Skill],
    skills_path: str | Path,
    *,
    cli_name: str | None = None,
    verify_cli: bool = False,
    strict_verify: bool = False,
    cli_recognizer: CliRecognizer | None = None,
) -> VerificationResult:
    skill_list = list(skills)
    root = Path(skills_path).expanduser()
    for skill in skill_list:
        installed_dir = root / skill.name
        if not installed_dir.is_dir():
            raise VerificationError(f"同步失败：未找到已安装 skill 目录：{installed_dir}")

        skill_file = installed_dir / "SKILL.md"
        if not skill_file.is_file():
            raise VerificationError(f"同步失败：未找到已安装文件：{skill_file}")

    warnings: list[str] = []
    cli_verified = False
    if verify_cli:
        if cli_name is None:
            raise VerificationError("CLI 识别校验失败：未指定目标 CLI。")

        if cli_recognizer is None:
            cli_result = verify_cli_recognition(cli_name, [skill.name for skill in skill_list])
        else:
            recognized, message = cli_recognizer(cli_name, [skill.name for skill in skill_list])
            cli_result = CliVerificationResult(recognized=recognized, message=message)

        cli_verified = cli_result.recognized
        if not cli_result.recognized:
            if strict_verify:
                raise VerificationError(f"CLI 识别校验失败：{cli_result.message}")
            warnings.append(f"CLI 识别校验未通过：{cli_result.message}")

    return VerificationResult(
        file_verified=True,
        cli_verified=cli_verified,
        warnings=warnings,
    )


def verify_cli_recognition(cli_name: str, skill_names: list[str]) -> CliVerificationResult:
    return CliVerificationResult(
        recognized=False,
        message=f"{cli_name} CLI 识别校验暂未实现，已跳过可靠识别。",
    )
