"""Configuration loading, saving, and validation."""

from __future__ import annotations

import copy
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from internal.errors import CoshSkillsError, ExitCode

DEFAULT_CONFIG: dict[str, Any] = {
    "repo_path": None,
    "last_repo_commit": None,
    "cli": {
        "codex": {
            "install_mode": "auto",
            "skills_path": None,
            "last_commit": None,
            "last_updated_at": None,
            "managed_skills": [],
        },
        "claude": {
            "install_mode": "auto",
            "skills_path": None,
            "last_commit": None,
            "last_updated_at": None,
            "managed_skills": [],
        },
        "qwen": {
            "install_mode": "auto",
            "skills_path": None,
            "last_commit": None,
            "last_updated_at": None,
            "managed_skills": [],
        },
    },
}

ALLOWED_CONFIG_KEYS = (
    "repo_path",
    "cli.codex.skills_path",
    "cli.claude.skills_path",
    "cli.qwen.skills_path",
    "cli.codex.install_mode",
    "cli.claude.install_mode",
    "cli.qwen.install_mode",
)
VALID_INSTALL_MODES = ("auto", "copy", "cli", "link")


class ConfigError(CoshSkillsError):
    """Raised when configuration is invalid or cannot be changed."""

    exit_code = ExitCode.USAGE_ERROR


def config_path(*, home: Path | None = None) -> Path:
    base_home = home if home is not None else Path.home()
    return base_home / ".cosh-skills" / "config.json"


def default_config() -> dict[str, Any]:
    return copy.deepcopy(DEFAULT_CONFIG)


def load_config(*, home: Path | None = None, path: Path | None = None) -> dict[str, Any]:
    target = path if path is not None else config_path(home=home)
    if not target.exists():
        return default_config()

    with target.open("r", encoding="utf-8") as config_file:
        loaded = json.load(config_file)

    if not isinstance(loaded, Mapping):
        raise ConfigError("配置文件格式非法：顶层必须是 JSON object。")

    return _merge_defaults(default_config(), loaded)


def save_config(
    config: Mapping[str, Any],
    *,
    home: Path | None = None,
    path: Path | None = None,
) -> None:
    target = path if path is not None else config_path(home=home)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(format_config_json(config), encoding="utf-8")


def format_config_json(config: Mapping[str, Any]) -> str:
    return json.dumps(config, ensure_ascii=False, indent=2) + "\n"


def set_config_value(config: dict[str, Any], key: str, value: str) -> None:
    if key not in ALLOWED_CONFIG_KEYS:
        raise ConfigError(
            "非法配置项：{key}\n\n可用配置项：\n{items}".format(
                key=key,
                items="\n".join(f"- {item}" for item in ALLOWED_CONFIG_KEYS),
            )
        )

    if key.endswith(".install_mode") and value not in VALID_INSTALL_MODES:
        raise ConfigError(
            "非法 install_mode：{value}\n\n允许值：\n{items}".format(
                value=value,
                items="\n".join(f"- {item}" for item in VALID_INSTALL_MODES),
            )
        )

    parts = key.split(".")
    current: dict[str, Any] = config
    for part in parts[:-1]:
        nested = current.setdefault(part, {})
        if not isinstance(nested, dict):
            raise ConfigError(f"配置项路径非法：{key}")
        current = nested
    current[parts[-1]] = value


def _merge_defaults(default: dict[str, Any], loaded: Mapping[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(default)
    for key, value in loaded.items():
        if (
            key in merged
            and isinstance(merged[key], dict)
            and isinstance(value, Mapping)
        ):
            merged[key] = _merge_defaults(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged
