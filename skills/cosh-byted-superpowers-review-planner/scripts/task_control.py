#!/usr/bin/env python3
"""Parse native Superpowers plans and advance one scoped implementation task."""

from __future__ import annotations

import hashlib
import json
import logging
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Mapping


LOGGER = logging.getLogger("byted-superpowers-task-control")

ALLOWED_COMMIT_TYPES = {"feat", "fix", "refactor", "test", "docs", "chore"}
TASK_HEADING = re.compile(r"^### Task (\d+):\s*(.+?)\s*$")
FILE_LINE = re.compile(r"^- (?:Create|Modify|Test|Delete|Verify only):\s*`([^`]+)`")
STEP_LINE = re.compile(r"^- \[([ xX])\] \*\*Step \d+:\s*(.+?)\*\*\s*$")
CHINESE_TEXT = re.compile(r"[\u3400-\u9fff]")
WORK_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class TaskControlError(RuntimeError):
    """Raised when task metadata or Git input is invalid."""


class TaskControlConflict(TaskControlError):
    """Raised when a task can no longer be advanced safely."""


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise TaskControlConflict(f"缺少证据文件：{path.name}") from error
    except json.JSONDecodeError as error:
        raise TaskControlConflict(f"JSON 解析失败：{path.name}: {error.msg}") from error
    if not isinstance(payload, dict):
        raise TaskControlConflict(f"JSON 顶层必须是对象：{path.name}")
    return payload


def _run_git(
    project_root: Path, arguments: list[str], *, check: bool = True
) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            ["git", *arguments],
            cwd=project_root,
            check=False,
            text=True,
            capture_output=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise TaskControlError(f"Git 命令执行失败：{error}") from error
    if check and result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "未知错误"
        raise TaskControlError(f"git {' '.join(arguments)} 失败：{detail}")
    return result


def _strip_line_range(path: str) -> str:
    return re.sub(r":\d+(?:-\d+)?$", "", path.strip())


def parse_superpowers_plan(path: Path) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise TaskControlError(f"读取 Superpowers 计划失败：{error}") from error

    tasks: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    section = ""
    for line in lines:
        heading = TASK_HEADING.match(line)
        if heading:
            current = {
                "number": int(heading.group(1)),
                "title": heading.group(2).strip(),
                "allowed_files": [],
                "interfaces": [],
                "steps": [],
            }
            tasks.append(current)
            section = ""
            continue
        if current is None:
            continue
        if line.strip() == "**Files:**":
            section = "files"
            continue
        if line.strip() == "**Interfaces:**":
            section = "interfaces"
            continue
        step_match = STEP_LINE.match(line)
        if step_match:
            current["steps"].append(
                {
                    "done": step_match.group(1).lower() == "x",
                    "title": step_match.group(2).strip(),
                }
            )
            section = ""
            continue
        file_match = FILE_LINE.match(line)
        if section == "files" and file_match:
            relative = _strip_line_range(file_match.group(1))
            if relative not in current["allowed_files"]:
                current["allowed_files"].append(relative)
            continue
        if section == "interfaces" and line.startswith("- "):
            current["interfaces"].append(line[2:].strip())
            continue
        if line.startswith("**") and line.endswith("**"):
            section = ""

    if not tasks:
        raise TaskControlError(f"计划中没有 `### Task N:`：{path}")
    numbers = [task["number"] for task in tasks]
    if numbers != list(range(1, len(tasks) + 1)):
        raise TaskControlError("实施子任务必须从 Task 1 开始连续编号")
    for task in tasks:
        if not task["allowed_files"]:
            raise TaskControlError(f"Task {task['number']} 缺少允许修改文件")
        if not task["interfaces"]:
            raise TaskControlError(f"Task {task['number']} 缺少 Interfaces")
        if not task["steps"]:
            raise TaskControlError(f"Task {task['number']} 缺少可执行步骤")
    return tasks


def find_plan(project_root: Path, work_id: str) -> Path:
    plan_root = project_root.resolve() / "docs" / "superpowers" / "plans"
    candidates = sorted(plan_root.glob(f"*-{work_id}.md")) if plan_root.is_dir() else []
    if not candidates:
        raise TaskControlConflict(f"未找到开发任务 {work_id} 的 Superpowers 计划")
    if len(candidates) > 1:
        raise TaskControlConflict(f"开发任务 {work_id} 存在多份 Superpowers 计划")
    return candidates[0]


def _staged_paths(project_root: Path) -> list[str]:
    result = _run_git(project_root, ["diff", "--cached", "--name-only", "-z"])
    return sorted(path for path in result.stdout.split("\0") if path)


def validate_task_scope(project_root: Path, task: Mapping[str, Any]) -> list[str]:
    allowed = {str(path) for path in task.get("allowed_files", [])}
    return [path for path in _staged_paths(project_root) if path not in allowed]


def current_snapshot_sha(project_root: Path) -> str:
    head = _run_git(project_root, ["rev-parse", "HEAD"]).stdout.strip()
    staged = _run_git(project_root, ["diff", "--cached", "--binary"]).stdout
    digest = hashlib.sha256()
    digest.update(head.encode("utf-8"))
    digest.update(b"\0")
    digest.update(staged.encode("utf-8"))
    return digest.hexdigest()


def format_task_commit(
    work_id: str,
    task_number: int,
    commit_type: str,
    summary: str,
) -> str:
    if commit_type not in ALLOWED_COMMIT_TYPES:
        raise TaskControlError(f"不支持的提交类型：{commit_type}")
    if not WORK_ID.fullmatch(work_id):
        raise TaskControlError(f"非法开发任务标识：{work_id}")
    normalized_summary = summary.strip()
    if not normalized_summary or "\n" in normalized_summary:
        raise TaskControlError("提交摘要必须是单行中文文本")
    if not CHINESE_TEXT.search(normalized_summary):
        raise TaskControlError("提交摘要必须包含中文")
    if task_number < 1:
        raise TaskControlError("子任务序号必须大于零")
    return (
        f"{commit_type}: {normalized_summary}\n\n"
        f"{work_id}-task{task_number}"
    )


def _work_dir(project_root: Path, work_id: str) -> Path:
    if not WORK_ID.fullmatch(work_id):
        raise TaskControlConflict(f"非法开发任务标识：{work_id}")
    root = project_root.resolve() / ".superpowers" / "byted-work"
    candidate = (root / work_id).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as error:
        raise TaskControlConflict(f"开发任务路径越界：{work_id}") from error
    if not candidate.is_dir():
        raise TaskControlConflict(f"开发任务不存在：{work_id}")
    return candidate


def work_state_version(work_dir: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in work_dir.rglob("*") if item.is_file()):
        digest.update(str(path.relative_to(work_dir)).encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()[:16]


def _completed_tasks(work_dir: Path) -> set[int]:
    completed: set[int] = set()
    for path in (work_dir / "evidence").glob("commit-task*.json"):
        match = re.fullmatch(r"commit-task(\d+)\.json", path.name)
        if not match:
            continue
        try:
            evidence = _read_json(path)
        except TaskControlError:
            continue
        if evidence.get("status") == "passed" and evidence.get("commit_sha"):
            completed.add(int(match.group(1)))
    return completed


def _evidence_matches_snapshot(
    work_dir: Path, prefix: str, task_number: int, snapshot_sha: str
) -> bool:
    try:
        evidence = _read_json(
            work_dir / "evidence" / f"{prefix}-task{task_number}.json"
        )
    except TaskControlError:
        return False
    return (
        evidence.get("status") == "passed"
        and evidence.get("code_sha") == snapshot_sha
    )


def project_task_status(project_root: Path, work_id: str) -> dict[str, Any]:
    work_dir = _work_dir(project_root, work_id)
    tasks = parse_superpowers_plan(find_plan(project_root, work_id))
    workflow = _read_json(work_dir / "workflow.json")
    mode = workflow.get("mode", "single")
    completed = _completed_tasks(work_dir)
    current = next((task for task in tasks if task["number"] not in completed), None)
    snapshot_sha = ""
    staged: list[str] = []
    out_of_scope: list[str] = []
    if current is not None:
        try:
            staged = _staged_paths(project_root)
            snapshot_sha = current_snapshot_sha(project_root)
            out_of_scope = validate_task_scope(project_root, current)
        except TaskControlError:
            pass

    projected: list[dict[str, Any]] = []
    for task in tasks:
        number = task["number"]
        if number in completed:
            task_status = "completed"
        elif current is not None and number == current["number"]:
            task_status = "current"
        else:
            task_status = "waiting"
        projected.append({**task, "status": task_status})

    current_projection: dict[str, Any] | None = None
    if current is not None:
        remote_ut_passed = _evidence_matches_snapshot(
            work_dir, "remote-ut", current["number"], snapshot_sha
        )
        cr_passed = _evidence_matches_snapshot(
            work_dir, "cr", current["number"], snapshot_sha
        )
        can_advance = (
            mode == "single"
            and bool(staged)
            and not out_of_scope
            and remote_ut_passed
            and cr_passed
        )
        current_projection = {
            **current,
            "status": "current",
            "snapshot_sha": snapshot_sha,
            "staged_files": staged,
            "out_of_scope_files": out_of_scope,
            "remote_ut_passed": remote_ut_passed,
            "cr_passed": cr_passed,
            "can_advance": can_advance,
        }
    return {
        "plan": str(
            find_plan(project_root, work_id).relative_to(project_root.resolve())
        ),
        "mode": mode,
        "tasks": projected,
        "tasks_total": len(tasks),
        "tasks_done": len(completed),
        "current_task": current_projection,
    }


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # 先写同目录临时文件再替换，避免监听器读取到半个 JSON。
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.replace(path)


def _validate_task_evidence(
    work_dir: Path, task_number: int, snapshot_sha: str
) -> None:
    for label, prefix in (("远程 UT", "remote-ut"), ("CR", "cr")):
        evidence = _read_json(
            work_dir / "evidence" / f"{prefix}-task{task_number}.json"
        )
        if evidence.get("status") != "passed":
            raise TaskControlConflict(f"Task {task_number} 的{label}尚未通过")
        if evidence.get("code_sha") != snapshot_sha:
            raise TaskControlConflict(f"Task {task_number} 的{label}证据已过期")


def advance_task(
    project_root: Path,
    work_id: str,
    *,
    expected_version: str,
    expected_task: int,
    commit_type: str,
    summary: str,
) -> dict[str, Any]:
    work_dir = _work_dir(project_root, work_id)
    actual_version = work_state_version(work_dir)
    if expected_version != actual_version:
        raise TaskControlConflict("开发任务状态已经变化，请刷新后重试")

    workflow = _read_json(work_dir / "workflow.json")
    if workflow.get("mode", "single") != "single":
        raise TaskControlConflict("连续推进模式不能手动推进下一个任务")

    tasks = parse_superpowers_plan(find_plan(project_root, work_id))
    completed = _completed_tasks(work_dir)
    current = next((task for task in tasks if task["number"] not in completed), None)
    if current is None:
        raise TaskControlConflict("所有实施子任务已经完成")
    if current["number"] != expected_task:
        raise TaskControlConflict(
            f"当前实施子任务是 Task {current['number']}，不是 Task {expected_task}"
        )

    staged = _staged_paths(project_root)
    if not staged:
        raise TaskControlConflict("暂存区为空，不能创建空提交")
    out_of_scope = validate_task_scope(project_root, current)
    if out_of_scope:
        raise TaskControlConflict(
            "暂存区包含当前任务范围外文件：" + ", ".join(out_of_scope)
        )
    snapshot_sha = current_snapshot_sha(project_root)
    _validate_task_evidence(work_dir, expected_task, snapshot_sha)
    message = format_task_commit(
        work_id, expected_task, commit_type, summary
    )
    subject, body = message.split("\n\n", 1)
    _run_git(project_root, ["commit", "-m", subject, "-m", body])
    commit_sha = _run_git(project_root, ["rev-parse", "HEAD"]).stdout.strip()

    evidence_path = work_dir / "evidence" / f"commit-task{expected_task}.json"
    _atomic_write_json(
        evidence_path,
        {
            "status": "passed",
            "task": expected_task,
            "snapshot_sha": snapshot_sha,
            "commit_sha": commit_sha,
            "message": message,
        },
    )
    next_task = next(
        (task["number"] for task in tasks if task["number"] > expected_task), None
    )
    LOGGER.info(
        "实施子任务已提交：work=%s task=%s commit=%s next=%s",
        work_id,
        expected_task,
        commit_sha,
        next_task,
    )
    return {
        "work": work_id,
        "completed_task": expected_task,
        "commit_sha": commit_sha,
        "next_task": next_task,
    }
