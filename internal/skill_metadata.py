"""Shared SKILL.md metadata parsing helpers."""

from __future__ import annotations

from typing import Any

SUPPORTED_CLIS = ("codex", "claude", "qwen", "openclaw", "hermes")


def parse_frontmatter(text: str) -> tuple[dict[str, Any], list[str]]:
    if not text.startswith("---\n"):
        return {}, []

    end = text.find("\n---\n", 4)
    if end == -1:
        return {}, ["SKILL.md 缺少 YAML front matter 结束标记。"]

    metadata: dict[str, Any] = {}
    errors: list[str] = []
    lines = text[4:end]
    split_lines = lines.splitlines()
    index = 0
    while index < len(split_lines):
        raw_line = split_lines[index]
        line_number = index + 2
        line = raw_line.strip()
        if not line:
            index += 1
            continue
        if raw_line[:1].isspace():
            errors.append(f"front matter 第 {line_number} 行格式非法。")
            index += 1
            continue
        if ":" not in line:
            errors.append(f"front matter 第 {line_number} 行格式非法。")
            index += 1
            continue

        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            errors.append(f"front matter 第 {line_number} 行缺少 key。")
            index += 1
            continue

        if value == "":
            items: list[str] = []
            lookahead = index + 1
            while lookahead < len(split_lines):
                item_line = split_lines[lookahead]
                stripped = item_line.strip()
                if not stripped:
                    lookahead += 1
                    continue
                if not item_line[:1].isspace():
                    break
                if not stripped.startswith("- "):
                    errors.append(f"front matter 第 {lookahead + 2} 行列表格式非法。")
                    lookahead += 1
                    continue
                items.append(_unquote(stripped[2:].strip()))
                lookahead += 1
            metadata[key] = items
            index = lookahead
            continue

        metadata[key] = _parse_scalar_or_inline_list(value)
        index += 1

    return metadata, errors


def parse_cli_scope(metadata: dict[str, Any]) -> tuple[tuple[str, ...] | None, list[str]]:
    if "cli_scope" not in metadata:
        return None, []

    value = metadata["cli_scope"]
    if not isinstance(value, list):
        return None, ["cli_scope 必须是 CLI 名称列表，例如：cli_scope: [codex, claude]。"]
    if not value:
        return None, ["cli_scope 不能为空；如需通用 skill，请省略该字段。"]

    errors: list[str] = []
    normalized: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str) or item.strip() == "":
            errors.append("cli_scope 中的每一项都必须是非空 CLI 名称。")
            continue
        cli_name = item.strip()
        if cli_name not in SUPPORTED_CLIS:
            errors.append(
                "cli_scope 包含不支持的 CLI：{name}。当前支持：{items}。".format(
                    name=cli_name,
                    items=", ".join(SUPPORTED_CLIS),
                )
            )
            continue
        if cli_name not in seen:
            seen.add(cli_name)
            normalized.append(cli_name)

    if errors:
        return None, errors
    return tuple(normalized), []


def _parse_scalar_or_inline_list(value: str) -> str | list[str]:
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if inner == "":
            return []
        return [_unquote(item.strip()) for item in inner.split(",")]
    return _unquote(value)


def _unquote(value: str) -> str:
    return value.strip().strip("\"'")
