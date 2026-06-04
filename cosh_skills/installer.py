"""Skill installation logic."""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from cosh_skills.config import save_config
from cosh_skills.errors import CoshSkillsError, ExitCode
from cosh_skills.scanner import Skill

VALID_INSTALL_MODES = ("auto", "copy", "cli", "link")


class InstallError(CoshSkillsError):
    """Raised when skills cannot be installed."""

    exit_code = ExitCode.RUNTIME_ERROR


@dataclass(frozen=True)
class InstallResult:
    installed: list[str]
    backups: list[Path]
    removed: list[str] | None = None


def install_skills(
    skills: Iterable[Skill],
    *,
    cli_name: str,
    cli_config: Mapping[str, Any],
    backup: bool = False,
    backup_root: str | Path | None = None,
    timestamp: str | None = None,
    use_rsync: bool = True,
) -> InstallResult:
    mode = cli_config.get("install_mode", "auto")
    if mode not in VALID_INSTALL_MODES:
        raise InstallError(
            "非法 install_mode：{mode}\n\n允许值：\n{items}".format(
                mode=mode,
                items="\n".join(f"- {item}" for item in VALID_INSTALL_MODES),
            )
        )
    if mode in ("cli", "link"):
        raise InstallError(f"当前版本暂未实现 {mode} 安装模式，请先使用 auto 或 copy。")

    skills_path_value = cli_config.get("skills_path")
    if skills_path_value is None or str(skills_path_value).strip() == "":
        raise InstallError(
            f"未配置 {cli_name} 的 skills_path，无法安装 skill。\n\n"
            "请执行：\n"
            f"cosh-skills config set cli.{cli_name}.skills_path ~/.{cli_name}/skills"
        )

    skills_path = Path(str(skills_path_value)).expanduser()
    installed: list[str] = []
    backups: list[Path] = []
    for skill in skills:
        backup_path = backup_skill(
            skill,
            cli_name=cli_name,
            skills_path=skills_path,
            backup_root=backup_root,
            timestamp=timestamp,
        ) if backup else None
        if backup_path is not None:
            backups.append(backup_path)

        sync_skill(skill, skills_path, use_rsync=use_rsync)
        installed.append(skill.name)

    return InstallResult(installed=installed, backups=backups)


def install_managed_skills(
    skills: Iterable[Skill],
    *,
    config: dict[str, Any],
    cli_name: str,
    config_home: Path | None = None,
    config_path: Path | None = None,
    backup: bool = False,
    backup_root: str | Path | None = None,
    timestamp: str | None = None,
    use_rsync: bool = True,
) -> InstallResult:
    skill_list = list(skills)
    cli_config = config["cli"][cli_name]
    result = install_skills(
        skill_list,
        cli_name=cli_name,
        cli_config=cli_config,
        backup=backup,
        backup_root=backup_root,
        timestamp=timestamp,
        use_rsync=use_rsync,
    )

    current_names = [skill.name for skill in skill_list]
    removed = remove_deprecated_managed_skills(
        previous_managed=cli_config.get("managed_skills", []),
        current_managed=current_names,
        skills_path=cli_config["skills_path"],
    )
    cli_config["managed_skills"] = current_names
    save_config(config, home=config_home, path=config_path)
    return InstallResult(
        installed=result.installed,
        backups=result.backups,
        removed=removed,
    )


def remove_deprecated_managed_skills(
    *,
    previous_managed: Iterable[str],
    current_managed: Iterable[str],
    skills_path: str | Path,
) -> list[str]:
    current = set(current_managed)
    removed: list[str] = []
    root = Path(skills_path).expanduser()
    for name in previous_managed:
        if name in current:
            continue

        target = root / name
        if target.exists():
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()
        removed.append(name)
    return removed


def backup_skill(
    skill: Skill,
    *,
    cli_name: str,
    skills_path: str | Path,
    backup_root: str | Path | None = None,
    timestamp: str | None = None,
) -> Path | None:
    source = Path(skills_path).expanduser() / skill.name
    if not source.exists():
        return None

    root = Path(backup_root).expanduser() if backup_root is not None else Path.home() / ".cosh-skills" / "backups"
    stamp = timestamp if timestamp is not None else datetime.now().strftime("%Y%m%d-%H%M%S")
    target = root / cli_name / skill.name / stamp
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)
    return target


def sync_skill(skill: Skill, skills_path: str | Path, *, use_rsync: bool = True) -> None:
    target = Path(skills_path).expanduser() / skill.name
    target.parent.mkdir(parents=True, exist_ok=True)

    rsync = shutil.which("rsync") if use_rsync else None
    if rsync is not None:
        target.mkdir(parents=True, exist_ok=True)
        _rsync(skill.path, target, rsync)
        return

    _copytree_delete_single_skill(skill.path, target)


def _rsync(source: Path, target: Path, rsync: str) -> None:
    result = subprocess.run(
        [rsync, "-a", "--delete", f"{source}/", f"{target}/"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise InstallError(f"rsync 同步失败：{detail}")


def _copytree_delete_single_skill(source: Path, target: Path) -> None:
    if target.exists():
        if not target.is_dir():
            target.unlink()
        else:
            shutil.rmtree(target)
    shutil.copytree(source, target)
