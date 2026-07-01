"""CLI hook initialization helpers."""

from __future__ import annotations

import json
import shlex
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from internal.config import load_config, save_config
from internal.errors import CoshSkillsError, ExitCode

STARTUP_HOOK_CLIS = ("codex", "qwen", "openclaw")


class HookInitError(CoshSkillsError):
    """Raised when a CLI hook cannot be initialized."""

    exit_code = ExitCode.USAGE_ERROR


@dataclass(frozen=True)
class HookInitResult:
    cli_name: str
    hook_path: Path
    command: str
    added: bool
    repo_path: Path
    skills_path: str


def initialize_cli_hook(
    *,
    cli_name: str,
    home: Path | None = None,
    repo_path: Path | None = None,
    python_bin: str | None = None,
    force: bool = False,
) -> HookInitResult:
    base_home = home if home is not None else Path.home()
    effective_repo_path = repo_path if repo_path is not None else Path(__file__).resolve().parents[1]
    command = build_update_command(
        cli_name=cli_name,
        python_bin=python_bin if python_bin is not None else sys.executable,
        repo_path=effective_repo_path,
        force=force,
    )

    if cli_name == "codex":
        hook_path = base_home / ".codex" / "hooks.json"
        added = install_session_start_hook(
            hook_path=hook_path,
            command=command,
            cli_label="Codex",
            loader=_load_json_document,
        )
    elif cli_name == "qwen":
        hook_path = base_home / ".qwen" / "settings.json"
        added = install_session_start_hook(
            hook_path=hook_path,
            command=command,
            cli_label="Qwen Code",
            loader=_load_json_document,
        )
    elif cli_name == "openclaw":
        hook_path = base_home / ".openclaw" / "openclaw.json"
        added = install_session_start_hook(
            hook_path=hook_path,
            command=command,
            cli_label="OpenClaw",
            loader=_load_json_document,
        )
    else:
        raise HookInitError(
            "当前 init hook 暂只支持 {items}。".format(
                items="、".join(STARTUP_HOOK_CLIS)
            )
        )

    config = load_config(home=base_home)
    config["repo_path"] = str(effective_repo_path)
    cli_config = config["cli"][cli_name]
    if not cli_config.get("skills_path"):
        cli_config["skills_path"] = f"~/.{cli_name}/skills"
    save_config(config, home=base_home)

    return HookInitResult(
        cli_name=cli_name,
        hook_path=hook_path,
        command=command,
        added=added,
        repo_path=effective_repo_path,
        skills_path=str(cli_config["skills_path"]),
    )


def build_update_command(
    *,
    cli_name: str,
    python_bin: str,
    repo_path: Path | None = None,
    force: bool = False,
) -> str:
    prefix = ""
    if repo_path is not None:
        prefix = f"PYTHONPATH={shlex.quote(str(repo_path))} "
    force_arg = " --force" if force else ""
    update_command = (
        f"{prefix}{shlex.quote(python_bin)} -m internal.hook_runner "
        f"--cli {shlex.quote(cli_name)}{force_arg}"
    )
    return update_command


def install_codex_session_start_hook(*, hook_path: Path, command: str) -> bool:
    return install_session_start_hook(
        hook_path=hook_path,
        command=command,
        cli_label="Codex",
        loader=_load_json_document,
    )


def install_qwen_session_start_hook(*, hook_path: Path, command: str) -> bool:
    return install_session_start_hook(
        hook_path=hook_path,
        command=command,
        cli_label="Qwen Code",
        loader=_load_json_document,
    )


def install_openclaw_session_start_hook(*, hook_path: Path, command: str) -> bool:
    return install_session_start_hook(
        hook_path=hook_path,
        command=command,
        cli_label="OpenClaw",
        loader=_load_json_document,
    )


def install_session_start_hook(
    *,
    hook_path: Path,
    command: str,
    cli_label: str,
    loader: Callable[..., dict[str, Any]],
) -> bool:
    document = loader(hook_path, cli_label=cli_label)
    hooks = document.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise HookInitError(f"{cli_label} hook 配置格式非法：hooks 必须是 JSON object。")

    session_start = hooks.setdefault("SessionStart", [])
    if not isinstance(session_start, list):
        raise HookInitError(f"{cli_label} hook 配置格式非法：hooks.SessionStart 必须是 array。")

    handler = {
        "type": "command",
        "command": command,
        "statusMessage": "Updating cosh skills",
    }
    for group in session_start:
        if not isinstance(group, dict):
            continue
        group_hooks = group.get("hooks")
        if not isinstance(group_hooks, list):
            continue
        for index, existing in enumerate(group_hooks):
            if not isinstance(existing, dict):
                continue
            existing_command = existing.get("command")
            if existing_command == command:
                return False
            if isinstance(existing_command, str) and _is_cosh_skills_update_command(existing_command):
                group_hooks[index] = handler
                _save_hooks_document(hook_path, document)
                return True

    session_start.append(
        {
            "matcher": "startup|resume",
            "hooks": [handler],
        }
    )
    _save_hooks_document(hook_path, document)
    return True


def _is_cosh_skills_update_command(command: str) -> bool:
    for cli_name in STARTUP_HOOK_CLIS:
        if (
            f"-m internal.cli update --cli {cli_name}" in command
            or f"-m internal.hook_runner --cli {cli_name}" in command
        ):
            return True
    return False


def _load_json_document(hook_path: Path, *, cli_label: str) -> dict[str, Any]:
    if not hook_path.exists():
        return {}
    try:
        loaded = json.loads(hook_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HookInitError(f"{cli_label} hook 配置不是合法 JSON：{exc}") from exc
    if not isinstance(loaded, dict):
        raise HookInitError(f"{cli_label} hook 配置格式非法：顶层必须是 JSON object。")
    return loaded


def _save_hooks_document(hook_path: Path, document: dict[str, Any]) -> None:
    hook_path.parent.mkdir(parents=True, exist_ok=True)
    hook_path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
