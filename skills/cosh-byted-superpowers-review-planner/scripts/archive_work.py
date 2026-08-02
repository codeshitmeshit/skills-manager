#!/usr/bin/env python3
"""Create a local, gitignored retrospective for one development work."""

from __future__ import annotations

import json
import logging
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Mapping


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import workflow_state  # noqa: E402


LOGGER = logging.getLogger("byted-superpowers-archive")
ARCHIVE_IGNORE = ".superpowers/byted-archive/"
SENSITIVE_KEY = re.compile(
    r"password|passwd|token|secret|authorization|cookie|credential|private[_-]?key",
    re.IGNORECASE,
)
BEARER_VALUE = re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+")
NAMED_VALUE = re.compile(
    r"(?i)(password|passwd|token|secret|authorization|cookie|credential)\s*[:=]\s*[^\s,;]+"
)


class ArchiveError(RuntimeError):
    """Raised when a retrospective cannot be created safely."""


def _read_json(path: Path, default: Mapping[str, Any] | None = None) -> dict[str, Any]:
    if not path.is_file():
        return dict(default or {})
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ArchiveError(f"归档来源不可读：{path.name}: {error}") from error
    if not isinstance(payload, dict):
        raise ArchiveError(f"归档来源必须是 JSON 对象：{path.name}")
    return payload


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    temporary.replace(path)


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    _atomic_write_text(
        path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    )


def ensure_archive_ignored(project_root: Path) -> None:
    path = project_root.resolve() / ".gitignore"
    existing = path.read_text(encoding="utf-8") if path.is_file() else ""
    lines = {line.strip() for line in existing.splitlines()}
    if ARCHIVE_IGNORE in lines:
        return
    suffix = "" if not existing or existing.endswith("\n") else "\n"
    _atomic_write_text(path, f"{existing}{suffix}{ARCHIVE_IGNORE}\n")


def is_archive_ignored(project_root: Path) -> bool:
    path = project_root.resolve() / ".gitignore"
    if not path.is_file():
        return False
    return ARCHIVE_IGNORE in {line.strip() for line in path.read_text(encoding="utf-8").splitlines()}


def _sanitize_text(value: str) -> str:
    value = BEARER_VALUE.sub(r"\1[REDACTED]", value)
    return NAMED_VALUE.sub(lambda match: f"{match.group(1)}: [REDACTED]", value)


def _sanitize(value: Any, key: str = "") -> Any:
    if key and SENSITIVE_KEY.search(key):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {name: _sanitize(item, str(name)) for name, item in value.items()}
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    if isinstance(value, str):
        return _sanitize_text(value)
    return value


def _git_commits(project_root: Path, work_id: str) -> list[str]:
    result = subprocess.run(
        ["git", "log", "--format=%H%x09%s%x09%b", "--grep", f"{work_id}-task"],
        cwd=project_root,
        text=True,
        capture_output=True,
        check=False,
        timeout=15,
    )
    if result.returncode != 0:
        return []
    return [line for line in result.stdout.splitlines() if line.strip()]


def _conversation_section(conversation: Mapping[str, Any]) -> str:
    total = conversation.get("total_turns")
    observed = conversation.get("observed_turns")
    coverage = conversation.get("coverage", "未提供会话观测信息")
    total_text = str(total) if isinstance(total, int) else "未知"
    observed_text = str(observed) if isinstance(observed, int) else "未知"
    stage_turns = conversation.get("stage_turns", {})
    stage_lines = "\n".join(
        f"- {name}：{count} 轮"
        for name, count in stage_turns.items()
        if isinstance(count, int)
    ) if isinstance(stage_turns, dict) else ""
    return (
        f"- 完整轮数：{total_text}\n"
        f"- 已观测轮数：{observed_text}\n"
        f"- 覆盖范围：{coverage}\n"
        + (f"\n阶段分布：\n\n{stage_lines}\n" if stage_lines else "")
    )


def _cause_section(events: list[Mapping[str, Any]]) -> str:
    if not events:
        return "当前没有足够的结构化交互证据，不能推断多轮原因。\n"
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for event in events:
        category = str(event.get("category", "未分类"))
        grouped.setdefault(category, []).append(event)
    parts: list[str] = []
    for category, items in grouped.items():
        parts.append(f"### {category}（{len(items)} 次）")
        for item in items:
            round_number = item.get("round", "未知")
            evidence = item.get("evidence", "缺少证据")
            parts.append(f"- 第 {round_number} 轮：{evidence}")
    return "\n\n".join(parts) + "\n"


def _rules_section(rules: list[Mapping[str, Any]]) -> str:
    if not rules:
        return "当前没有证据充分的候选规则，不自动生成泛化结论。\n"
    parts: list[str] = []
    for index, rule in enumerate(rules, 1):
        parts.extend(
            [
                f"### 候选规则 {index}：{rule.get('rule', '未命名规则')}",
                f"- 证据：{rule.get('evidence', '缺失')}",
                f"- 预期收益：{rule.get('benefit', '缺失')}",
                f"- 适用范围：{rule.get('scope', '缺失')}",
                f"- 置信度：{rule.get('confidence', 'unknown')}",
                f"- 建议更新位置：{rule.get('target', '待人工选择')}",
                "- 采纳状态：等待人工确认，不得自动修改公共 skill",
                "",
            ]
        )
    return "\n".join(parts)


def _archive_markdown(
    work_id: str,
    trigger: str,
    status: Mapping[str, Any],
    conversation: Mapping[str, Any],
    events: list[Mapping[str, Any]],
    rules: list[Mapping[str, Any]],
    commits: list[str],
) -> str:
    snapshot = json.dumps(_sanitize(status), ensure_ascii=False, indent=2)
    commit_lines = "\n".join(f"- {_sanitize_text(line)}" for line in commits)
    if not commit_lines:
        commit_lines = "- 没有发现带当前任务标识的提交"
    content = f"""# {work_id} 研发复盘

- 归档触发：{trigger}
- 生成时间：{datetime.now(timezone.utc).isoformat()}
- 状态版本：{status.get('version', 'unknown')}

## 会话轮次与覆盖范围

{_conversation_section(conversation)}
## 为什么需要多轮讨论

{_cause_section(events)}
## 实施提交

{commit_lines}

## 可蒸馏规则候选

{_rules_section(rules)}
## 最终状态快照

```json
{snapshot}
```
"""
    return _sanitize_text(content)


def archive_work(
    project_root: Path,
    work_id: str,
    trigger: Literal["push", "manual"],
) -> Path:
    if trigger not in {"push", "manual"}:
        raise ArchiveError(f"不支持的归档触发方式：{trigger}")
    root = project_root.resolve()
    work_dir = workflow_state.resolve_work(root, work_id)
    ensure_archive_ignored(root)
    status = workflow_state.build_status(root, work_id)
    conversation = _read_json(work_dir / "evidence" / "conversation.json")
    event_payload = _read_json(
        work_dir / "evidence" / "interaction-events.json", {"events": []}
    )
    rule_payload = _read_json(
        work_dir / "evidence" / "rule-candidates.json", {"rules": []}
    )
    events = event_payload.get("events", [])
    rules = rule_payload.get("rules", [])
    if not isinstance(events, list) or not isinstance(rules, list):
        raise ArchiveError("交互事件或候选规则格式无效")
    safe_events = [item for item in _sanitize(events) if isinstance(item, dict)]
    safe_rules = [item for item in _sanitize(rules) if isinstance(item, dict)]
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = (
        root
        / ".superpowers"
        / "byted-archive"
        / work_id
        / f"{timestamp}-retrospective.md"
    )
    content = _archive_markdown(
        work_id,
        trigger,
        status,
        _sanitize(conversation),
        safe_events,
        safe_rules,
        _git_commits(root, work_id),
    )
    _atomic_write_text(path, content)
    push = _read_json(work_dir / "evidence" / "push.json")
    evidence = {
        "status": "passed",
        "trigger": trigger,
        "path": str(path.relative_to(root)),
        "push_sha": push.get("code_sha"),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    _atomic_write_json(work_dir / "evidence" / "archive.json", evidence)
    LOGGER.info("开发任务已归档：work=%s path=%s", work_id, path)
    return path


def archive_after_push(project_root: Path, work_id: str) -> Path | None:
    root = project_root.resolve()
    work_dir = workflow_state.resolve_work(root, work_id)
    push = _read_json(work_dir / "evidence" / "push.json")
    if push.get("status") != "passed" or not push.get("code_sha"):
        return None
    archive = _read_json(work_dir / "evidence" / "archive.json")
    if (
        archive.get("status") == "passed"
        and archive.get("trigger") == "push"
        and archive.get("push_sha") == push.get("code_sha")
        and archive.get("path")
    ):
        existing = root / str(archive["path"])
        if existing.is_file():
            return existing
    return archive_work(root, work_id, "push")
