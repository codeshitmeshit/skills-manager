"""End-to-end update orchestration."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TextIO

from internal.config import load_config, save_config
from internal.git_ops import ensure_repo_path, update_repo
from internal.installer import install_skills, remove_deprecated_managed_skills
from internal.scanner import Skill, scan_skills
from internal.verifier import verify_installation


@dataclass(frozen=True)
class UpdateResult:
    cli_name: str
    commit: str
    git_updated: bool
    synced_count: int
    skipped_count: int
    warnings: list[str]


def run_update(
    *,
    cli_name: str,
    repo_path: str | Path | None = None,
    home: Path | None = None,
    output: TextIO | None = None,
    backup: bool = False,
    verify_cli: bool = False,
    strict_verify: bool = False,
    force: bool = False,
    use_rsync: bool = True,
) -> UpdateResult:
    out = output if output is not None else sys.stdout

    _log(out, "[1/6] 读取配置...")
    config = load_config(home=home)
    if repo_path is not None:
        configured_repo_path = ensure_repo_path(repo_path)
        config["repo_path"] = str(configured_repo_path)
        save_config(config, home=home)
    effective_repo_path = config.get("repo_path")

    _log(out, "[2/6] 检查 skill 仓库...")
    _log(out, "[3/6] 更新 skill 仓库...")
    git_result = update_repo(effective_repo_path, force=force)

    _log(out, "[4/6] 扫描合法 skill...")
    scan_result = scan_skills(effective_repo_path)
    for warning in scan_result.warnings:
        _log(out, warning)
    skills_to_sync, skipped_skills = _filter_skills_for_cli(scan_result.skills, cli_name)
    if skipped_skills:
        _log(out, f"已跳过 {len(skipped_skills)} 个不适用于 {cli_name} 的 skill。")

    cli_config = config["cli"][cli_name]
    _log(out, f"[5/6] 同步到 {cli_name}...")
    install_result = install_skills(
        skills_to_sync,
        cli_name=cli_name,
        cli_config=cli_config,
        backup=backup,
        backup_root=(home / ".cosh-skills" / "backups") if home is not None else None,
        use_rsync=use_rsync,
    )

    _log(out, "[6/6] 校验安装结果...")
    verify_result = verify_installation(
        skills_to_sync,
        cli_config["skills_path"],
        cli_name=cli_name,
        verify_cli=verify_cli,
        strict_verify=strict_verify,
    )
    for warning in verify_result.warnings:
        _log(out, warning)

    current_names = [skill.name for skill in skills_to_sync]
    remove_deprecated_managed_skills(
        previous_managed=cli_config.get("managed_skills", []),
        current_managed=current_names,
        skills_path=cli_config["skills_path"],
    )
    cli_config["managed_skills"] = current_names
    cli_config["last_commit"] = git_result.after_commit
    cli_config["last_updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    config["last_repo_commit"] = git_result.after_commit
    save_config(config, home=home)

    _log(out, "")
    _log(out, f"完成：已同步 {len(install_result.installed)} 个 skill 到 {cli_name}。")
    return UpdateResult(
        cli_name=cli_name,
        commit=git_result.after_commit,
        git_updated=git_result.updated,
        synced_count=len(install_result.installed),
        skipped_count=len(skipped_skills),
        warnings=[*scan_result.warnings, *verify_result.warnings],
    )


def _log(output: TextIO, message: str) -> None:
    output.write(message + "\n")


def _filter_skills_for_cli(skills: list[Skill], cli_name: str) -> tuple[list[Skill], list[Skill]]:
    eligible: list[Skill] = []
    skipped: list[Skill] = []
    for skill in skills:
        if skill.cli_scope is None or cli_name in skill.cli_scope:
            eligible.append(skill)
        else:
            skipped.append(skill)
    return eligible, skipped
