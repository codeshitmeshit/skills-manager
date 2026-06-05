"""Codex hook initialization helpers."""

from __future__ import annotations

import json
import shlex
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from internal.config import load_config, save_config
from internal.errors import CoshSkillsError, ExitCode


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
) -> HookInitResult:
    if cli_name != "codex":
        raise HookInitError("当前 init hook 暂只支持 codex。")

    base_home = home if home is not None else Path.home()
    effective_repo_path = repo_path if repo_path is not None else Path(__file__).resolve().parents[1]
    command = build_update_command(
        cli_name=cli_name,
        python_bin=python_bin if python_bin is not None else sys.executable,
        repo_path=effective_repo_path,
    )
    hook_path = base_home / ".codex" / "hooks.json"
    added = install_codex_session_start_hook(hook_path=hook_path, command=command)

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


def build_update_command(*, cli_name: str, python_bin: str, repo_path: Path | None = None) -> str:
    prefix = ""
    if repo_path is not None:
        prefix = f"PYTHONPATH={shlex.quote(str(repo_path))} "
    update_command = f"{prefix}{shlex.quote(python_bin)} -m internal.cli update --cli {shlex.quote(cli_name)}"
    log_path = "$HOME/.cosh-skills/codex-hook.log"
    return (
        "mkdir -p \"$HOME/.cosh-skills\" && "
        "{ "
        "printf '[%s] codex hook start\\n' \"$(date '+%Y-%m-%d %H:%M:%S')\"; "
        f"{update_command}; "
        "status=$?; "
        "printf '[%s] codex hook exit %s\\n' \"$(date '+%Y-%m-%d %H:%M:%S')\" \"$status\"; "
        "exit \"$status\"; "
        f"}} >> {log_path} 2>&1"
    )


def install_codex_session_start_hook(*, hook_path: Path, command: str) -> bool:
    document = _load_hooks_document(hook_path)
    hooks = document.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise HookInitError("Codex hooks.json 格式非法：hooks 必须是 JSON object。")

    session_start = hooks.setdefault("SessionStart", [])
    if not isinstance(session_start, list):
        raise HookInitError("Codex hooks.json 格式非法：hooks.SessionStart 必须是 array。")

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
    return "-m internal.cli update --cli codex" in command


def _load_hooks_document(hook_path: Path) -> dict[str, Any]:
    if not hook_path.exists():
        return {}
    try:
        loaded = json.loads(hook_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HookInitError(f"Codex hooks.json 不是合法 JSON：{exc}") from exc
    if not isinstance(loaded, dict):
        raise HookInitError("Codex hooks.json 格式非法：顶层必须是 JSON object。")
    return loaded


def _save_hooks_document(hook_path: Path, document: dict[str, Any]) -> None:
    hook_path.parent.mkdir(parents=True, exist_ok=True)
    hook_path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
