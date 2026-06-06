#!/usr/bin/env python3
"""List archived requirement progress under .cosh-docs/requirment."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


STAGE_LABELS = {
    "requirement_archived": "需求已归档",
    "product_clarifying": "产品澄清中",
    "technical_clarifying": "技术澄清中",
    "reviewed": "方案已评审",
    "checklist_draft": "测试清单待确认",
    "checklist_confirmed": "测试清单已确认",
    "todolist_created": "任务清单已创建",
    "plan_created": "执行计划已创建",
    "implementation_done": "开发已完成",
    "tested": "测试已完成",
    "done": "已完成",
    "paused": "已暂停",
    "cancelled": "已废弃",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="项目根目录，默认当前目录。")
    parser.add_argument("--all", action="store_true", help="显示全部需求，包含已完成和已废弃。")
    parser.add_argument("--json", action="store_true", help="以 JSON 格式输出。")
    args = parser.parse_args()

    archive_root = Path(args.root).resolve() / ".cosh-docs" / "requirment"
    records = scan_requirements(archive_root)
    if not args.all:
        records = [item for item in records if item["stage"] not in {"done", "cancelled"}]

    if args.json:
        print(json.dumps(records, ensure_ascii=False, indent=2))
        return 0

    if not archive_root.exists():
        print(f"未找到需求归档目录：{archive_root}")
        return 0

    if not records:
        print(f"暂无进行中需求：{archive_root}")
        return 0

    name_width = max(len("需求"), *(display_width(item["name"]) for item in records))
    stage_width = max(len("阶段"), *(display_width(stage_text(item)) for item in records))
    print(f"{pad('需求', name_width)}  {pad('阶段', stage_width)}  更新时间  路径")
    print(f"{'-' * name_width}  {'-' * stage_width}  --------  ----")
    for item in records:
        print(
            f"{pad(item['name'], name_width)}  "
            f"{pad(stage_text(item), stage_width)}  "
            f"{item['updated_at'] or '-'}  "
            f"{item['path']}"
        )
    return 0


def scan_requirements(archive_root: Path) -> list[dict[str, Any]]:
    if not archive_root.is_dir():
        return []
    records = []
    for requirement_dir in sorted(item for item in archive_root.iterdir() if item.is_dir()):
        records.append(read_record(requirement_dir))
    return records


def read_record(requirement_dir: Path) -> dict[str, Any]:
    status_path = requirement_dir / "status.json"
    if status_path.is_file():
        try:
            status = json.loads(status_path.read_text(encoding="utf-8"))
            stage = str(status.get("stage") or infer_stage(requirement_dir))
            return {
                "name": str(status.get("name") or requirement_dir.name),
                "stage": stage,
                "stage_label": STAGE_LABELS.get(stage, stage),
                "waiting_for_user": bool(status.get("waiting_for_user", False)),
                "updated_at": status.get("updated_at"),
                "confirmed": status.get("confirmed", {}),
                "confirmations": status.get("confirmations", {}),
                "path": str(requirement_dir),
                "inferred": False,
            }
        except (OSError, json.JSONDecodeError):
            pass

    stage = infer_stage(requirement_dir)
    return {
        "name": requirement_dir.name,
        "stage": stage,
        "stage_label": STAGE_LABELS.get(stage, stage),
        "waiting_for_user": stage in {"checklist_draft"},
        "updated_at": None,
        "confirmed": {},
        "confirmations": {},
        "path": str(requirement_dir),
        "inferred": True,
    }


def infer_stage(requirement_dir: Path) -> str:
    if (requirement_dir / "todolist.md").is_file():
        return "todolist_created"
    checklist = requirement_dir / "checklist.md"
    if checklist.is_file():
        try:
            text = checklist.read_text(encoding="utf-8")
        except OSError:
            text = ""
        if "确认状态：已确认" in text:
            return "checklist_confirmed"
        return "checklist_draft"
    if (requirement_dir / "review.md").is_file():
        return "reviewed"
    if (requirement_dir / "requirement.md").is_file():
        return "requirement_archived"
    return "unknown"


def display_width(text: str) -> int:
    return sum(2 if ord(char) > 127 else 1 for char in text)


def pad(text: str, width: int) -> str:
    return text + " " * max(width - display_width(text), 0)


def stage_text(item: dict[str, Any]) -> str:
    markers = []
    if item.get("waiting_for_user"):
        markers.append("等待用户")
    if item.get("inferred"):
        markers.append("推断")
    if not markers:
        return str(item["stage_label"])
    return f"{item['stage_label']}（{'，'.join(markers)}）"


if __name__ == "__main__":
    raise SystemExit(main())
