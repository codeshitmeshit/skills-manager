#!/usr/bin/env python3
"""Parse native Superpowers plans and advance one scoped implementation task."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import logging
import re
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


LOGGER = logging.getLogger("byted-superpowers-task-control")

ALLOWED_COMMIT_TYPES = {"feat", "fix", "refactor", "test", "docs", "chore"}
VALIDATION_STRATEGIES = {"final", "per_task"}
TASK_HEADING = re.compile(r"^### Task (\d+):\s*(.+?)\s*$")
FILE_LINE = re.compile(
    r"^- (Create|Modify|Test|Delete|Verify only):\s*`([^`]+)`"
)
STEP_LINE = re.compile(r"^- \[([ xX])\] \*\*Step \d+:\s*(.+?)\*\*\s*$")
CHINESE_TEXT = re.compile(r"[\u3400-\u9fff]")
WORK_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
IGNORED_WORKFLOW_PATH_PREFIXES = (
    ".superpowers/",
    "docs/superpowers/specs/",
    "docs/superpowers/plans/",
)


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


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
                "file_entries": [],
                "test_files": [],
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
            role = file_match.group(1)
            relative = _strip_line_range(file_match.group(2))
            if relative not in current["allowed_files"]:
                current["allowed_files"].append(relative)
            entry = {"role": role, "path": relative}
            if entry not in current["file_entries"]:
                current["file_entries"].append(entry)
            if role == "Test" and relative not in current["test_files"]:
                current["test_files"].append(relative)
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


def _staged_deleted_paths(project_root: Path) -> list[str]:
    result = _run_git(
        project_root,
        ["diff", "--cached", "--name-only", "--diff-filter=D", "-z", "HEAD", "--"],
    )
    return sorted(path for path in result.stdout.split("\0") if path)


def _test_files_removed_from_index(
    project_root: Path, required_test_files: list[str]
) -> list[str]:
    removed: list[str] = []
    for path in required_test_files:
        existed_at_head = _run_git(
            project_root, ["cat-file", "-e", f"HEAD:{path}"], check=False
        ).returncode == 0
        exists_in_index = _run_git(
            project_root, ["cat-file", "-e", f":{path}"], check=False
        ).returncode == 0
        if existed_at_head and not exists_in_index:
            removed.append(path)
    return removed


def _is_workflow_metadata(path: str) -> bool:
    return path.startswith(IGNORED_WORKFLOW_PATH_PREFIXES)


def _unstaged_paths(project_root: Path) -> list[str]:
    return [
        path for path in _raw_unstaged_paths(project_root) if not _is_workflow_metadata(path)
    ]


def _raw_unstaged_paths(project_root: Path) -> list[str]:
    tracked = _run_git(project_root, ["diff", "--name-only", "-z"]).stdout
    untracked = _run_git(
        project_root, ["ls-files", "--others", "--exclude-standard", "-z"]
    ).stdout
    return sorted(
        {
            path
            for path in (*tracked.split("\0"), *untracked.split("\0"))
            if path
        }
    )


def changed_paths(project_root: Path) -> list[str]:
    return sorted(
        {
            path
            for path in (*_staged_paths(project_root), *_unstaged_paths(project_root))
            if not _is_workflow_metadata(path)
        }
    )


def validate_task_scope(project_root: Path, task: Mapping[str, Any]) -> list[str]:
    allowed = {str(path) for path in task.get("allowed_files", [])}
    return [path for path in changed_paths(project_root) if path not in allowed]


def current_snapshot_sha(project_root: Path) -> str:
    head = _run_git(project_root, ["rev-parse", "HEAD"]).stdout.strip()
    tracked_diff = _run_git(project_root, ["diff", "HEAD", "--binary"]).stdout
    digest = hashlib.sha256()
    digest.update(head.encode("utf-8"))
    digest.update(b"\0")
    digest.update(tracked_diff.encode("utf-8"))
    for relative in _unstaged_paths(project_root):
        path = project_root / relative
        if not path.is_file() or _run_git(
            project_root, ["ls-files", "--error-unmatch", relative], check=False
        ).returncode == 0:
            continue
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _task_snapshot_sha(
    project_root: Path, amendment: Mapping[str, Any] | list[dict[str, Any]] | None
) -> str:
    base = current_snapshot_sha(project_root)
    if not amendment:
        return base
    digest = hashlib.sha256()
    digest.update(base.encode("utf-8"))
    digest.update(b"\0spec-amendment\0")
    digest.update(
        json.dumps(amendment, ensure_ascii=False, sort_keys=True).encode("utf-8")
    )
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
        if path.name == "dashboard-state.json":
            continue
        digest.update(str(path.relative_to(work_dir)).encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()[:16]


def _checkpoint_commits(project_root: Path, work_id: str) -> dict[int, str]:
    result = _run_git(
        project_root,
        ["log", "--format=%H%x1f%B%x1e"],
        check=False,
    )
    if result.returncode != 0:
        return {}
    checkpoints: dict[int, str] = {}
    trailer = re.compile(rf"^{re.escape(work_id)}-task(\d+)$", re.MULTILINE)
    for record in result.stdout.split("\x1e"):
        if "\x1f" not in record:
            continue
        commit_sha, message = record.strip().split("\x1f", 1)
        for match in trailer.finditer(message):
            task_number = int(match.group(1))
            if task_number in checkpoints:
                raise TaskControlConflict(
                    f"Task {task_number} 存在多个 checkpoint commit"
                )
            checkpoints[task_number] = commit_sha
    return checkpoints


def _completed_tasks(
    project_root: Path, work_dir: Path, work_id: str
) -> set[int]:
    completed: set[int] = set()
    checkpoint_commits = _checkpoint_commits(project_root, work_id)
    evidence_tasks: set[int] = set()
    for path in (work_dir / "evidence").glob("commit-task*.json"):
        match = re.fullmatch(r"commit-task(\d+)\.json", path.name)
        if not match:
            continue
        evidence = _read_json(path)
        task_number = int(match.group(1))
        evidence_tasks.add(task_number)
        commit_sha = evidence.get("commit_sha")
        if (
            evidence.get("status") != "passed"
            or evidence.get("task") != task_number
            or not isinstance(commit_sha, str)
            or not commit_sha
        ):
            raise TaskControlConflict(f"提交证据无效：{path.name}")
        if _run_git(
            project_root, ["cat-file", "-e", f"{commit_sha}^{{commit}}"], check=False
        ).returncode != 0:
            raise TaskControlConflict(f"提交证据指向无效 commit：{path.name}")
        expected_commit = checkpoint_commits.get(task_number)
        if evidence.get("validation_strategy") is not None and expected_commit != commit_sha:
            raise TaskControlConflict(f"提交证据与 checkpoint commit 不一致：{path.name}")
        completed.add(task_number)
    missing_evidence = sorted(set(checkpoint_commits) - evidence_tasks)
    if missing_evidence:
        raise TaskControlConflict(
            "缺少提交证据："
            + ", ".join(f"Task {number}" for number in missing_evidence)
        )
    return completed


def _validation_strategy(
    workflow: Mapping[str, Any], completed: set[int], work_dir: Path
) -> str:
    configured = workflow.get("validation_strategy")
    if configured is not None and configured not in VALIDATION_STRATEGIES:
        raise TaskControlConflict("验证策略必须是 final 或 per_task")
    checkpoint_strategies: set[str] = set()
    for task_number in sorted(completed):
        evidence = _read_json(
            work_dir / "evidence" / f"commit-task{task_number}.json"
        )
        checkpoint_strategy = evidence.get("validation_strategy", "per_task")
        if checkpoint_strategy not in VALIDATION_STRATEGIES:
            raise TaskControlConflict(
                f"Task {task_number} 的提交证据包含非法验证策略"
            )
        checkpoint_strategies.add(str(checkpoint_strategy))
    if len(checkpoint_strategies) > 1:
        raise TaskControlConflict("已提交 Task 的验证策略不一致")
    if checkpoint_strategies:
        locked = next(iter(checkpoint_strategies))
        if configured is not None and configured != locked:
            raise TaskControlConflict("验证策略与已提交 Task 的锁定值不一致")
        return locked
    return str(configured or "final")


def _planned_test_files(task: Mapping[str, Any]) -> list[str]:
    return [str(path) for path in task.get("test_files", [])]


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


def _load_control(work_dir: Path, *, strict: bool = False) -> dict[str, Any]:
    path = work_dir / "control.json"
    if not path.is_file():
        return {}
    try:
        payload = _read_json(path)
    except TaskControlError:
        if strict:
            raise TaskControlConflict("控制状态损坏，拒绝覆盖现有控制记录")
        return {}
    return payload


def _authorized_task(
    work_dir: Path, mode: str, completed: set[int], next_task: int | None
) -> int | None:
    if next_task is None:
        return None
    if mode == "continuous" or not completed:
        return next_task
    authorization = _load_control(work_dir).get("task_authorization", {})
    if not isinstance(authorization, dict):
        return None
    candidate = authorization.get("authorized_task")
    return candidate if candidate == next_task else None


def _normalize_spec_amendment(
    amendment: Mapping[str, Any],
    *,
    task_number: int,
    spec_relative: str,
    base_spec_sha: str,
    plan_sha: str,
) -> dict[str, Any]:
    if amendment.get("status") != "passed":
        raise TaskControlConflict("当前 Task 的规格附加修正尚未确认")
    if amendment.get("task") != task_number:
        raise TaskControlConflict("规格附加修正与文件标识的 Task 不一致")
    if amendment.get("spec_path") != spec_relative:
        raise TaskControlConflict("规格附加修正与规格路径不一致")
    if amendment.get("base_spec_sha256") != base_spec_sha:
        raise TaskControlConflict("规格附加修正与上一版规格 SHA-256 不一致")
    amended_spec_sha = amendment.get("amended_spec_sha256")
    if not isinstance(amended_spec_sha, str) or len(amended_spec_sha) != 64:
        raise TaskControlConflict("规格附加修正缺少有效的修正后 SHA-256")
    if amendment.get("base_plan_sha256") != plan_sha:
        raise TaskControlConflict("规格附加修正与原计划 SHA-256 不一致")
    for field in ("summary", "diff"):
        if not isinstance(amendment.get(field), str) or not amendment[field].strip():
            raise TaskControlConflict(f"规格附加修正缺少 {field}")
    override = amendment.get("task_override")
    if not isinstance(override, dict):
        raise TaskControlConflict("规格附加修正缺少 task_override")
    title = override.get("title")
    allowed_files = override.get("allowed_files")
    interfaces = override.get("interfaces")
    steps = override.get("steps")
    acceptance = override.get("acceptance_criteria")
    test_files = override.get("test_files")
    if not isinstance(title, str) or not title.strip():
        raise TaskControlConflict("Task 附加修正缺少 title")
    for field, values in (
        ("allowed_files", allowed_files),
        ("interfaces", interfaces),
        ("steps", steps),
        ("acceptance_criteria", acceptance),
    ):
        if (
            not isinstance(values, list)
            or not values
            or any(not isinstance(value, str) or not value.strip() for value in values)
        ):
            raise TaskControlConflict(f"Task 附加修正的 {field} 必须是非空字符串数组")
    if test_files is not None and (
        not isinstance(test_files, list)
        or any(not isinstance(value, str) or not value.strip() for value in test_files)
    ):
        raise TaskControlConflict("Task 附加修正的 test_files 必须是字符串数组")
    normalized_allowed_files = list(dict.fromkeys(allowed_files))
    normalized_test_files = list(dict.fromkeys(test_files or []))
    if any(path not in normalized_allowed_files for path in normalized_test_files):
        raise TaskControlConflict("Task 附加修正的 test_files 必须属于 allowed_files")
    normalized = dict(amendment)
    normalized["task_override"] = {
        "title": title.strip(),
        "allowed_files": normalized_allowed_files,
        "interfaces": list(dict.fromkeys(interfaces)),
        "steps": [
            {"done": False, "title": step.strip()}
            for step in dict.fromkeys(steps)
        ],
        "acceptance_criteria": list(dict.fromkeys(acceptance)),
    }
    if test_files is not None:
        normalized["task_override"]["test_files"] = normalized_test_files
    return normalized


def _spec_amendment_chain(
    project_root: Path,
    work_dir: Path,
    current_task_number: int | None,
    completed: set[int],
) -> list[dict[str, Any]]:
    spec_evidence = _read_json(work_dir / "evidence" / "spec.json")
    spec_relative = spec_evidence.get("path")
    base_spec_sha = spec_evidence.get("sha256")
    if not isinstance(spec_relative, str) or not spec_relative:
        raise TaskControlConflict("规格证据缺少 path")
    if not isinstance(base_spec_sha, str) or len(base_spec_sha) != 64:
        raise TaskControlConflict("规格证据缺少有效 SHA-256")
    root = project_root.resolve()
    spec_path = (root / spec_relative).resolve()
    try:
        spec_path.relative_to(root)
    except ValueError as error:
        raise TaskControlConflict("规格产物路径越界") from error
    if not spec_path.is_file():
        raise TaskControlConflict(f"规格产物不存在：{spec_relative}")
    amended_spec_sha = _sha256_file(spec_path)
    if amended_spec_sha == base_spec_sha:
        return []

    plan_evidence = _read_json(work_dir / "evidence" / "plan.json")
    plan_relative = plan_evidence.get("path")
    plan_sha = plan_evidence.get("sha256")
    if not isinstance(plan_sha, str) or len(plan_sha) != 64:
        raise TaskControlConflict("计划证据缺少有效 SHA-256")
    if not isinstance(plan_relative, str) or not (root / plan_relative).is_file():
        raise TaskControlConflict("规格附加修正引用的原计划不存在")
    if _sha256_file(root / plan_relative) != plan_sha:
        raise TaskControlConflict("原计划已变化，不能套用当前 Task 附加修正")
    allowed_tasks = set(completed)
    if current_task_number is not None:
        allowed_tasks.add(current_task_number)
    candidates: list[tuple[int, dict[str, Any]]] = []
    for path in sorted((work_dir / "evidence").glob("spec-amendment-task*.json")):
        match = re.fullmatch(r"spec-amendment-task(\d+)\.json", path.name)
        if not match:
            continue
        task_number = int(match.group(1))
        if task_number not in allowed_tasks:
            continue
        candidates.append((task_number, _read_json(path)))

    chain: list[dict[str, Any]] = []
    current_sha = base_spec_sha
    used_tasks: set[int] = set()
    while current_sha != amended_spec_sha:
        matches = [
            (task_number, amendment)
            for task_number, amendment in candidates
            if amendment.get("base_spec_sha256") == current_sha
            and task_number not in used_tasks
        ]
        if not matches:
            raise TaskControlConflict("缺少当前 Task 的规格附加修正")
        if len(matches) > 1:
            raise TaskControlConflict("规格附加修正链存在分叉，拒绝自动选择")
        task_number, amendment = matches[0]
        normalized = _normalize_spec_amendment(
            amendment,
            task_number=task_number,
            spec_relative=spec_relative,
            base_spec_sha=current_sha,
            plan_sha=plan_sha,
        )
        chain.append(normalized)
        used_tasks.add(task_number)
        current_sha = str(normalized["amended_spec_sha256"])
    return chain


def _apply_task_override(
    task: Mapping[str, Any], amendment: Mapping[str, Any] | None
) -> dict[str, Any]:
    if not amendment:
        return dict(task)
    override = amendment["task_override"]
    allowed_files = [str(path) for path in override["allowed_files"]]
    test_files = override.get("test_files")
    if test_files is None:
        test_files = [
            str(path)
            for path in task.get("test_files", [])
            if str(path) in allowed_files
        ]
    return {
        **task,
        **override,
        "allowed_files": allowed_files,
        "test_files": list(test_files),
        "spec_amendment": {
            key: amendment.get(key)
            for key in (
                "task",
                "spec_path",
                "base_spec_sha256",
                "amended_spec_sha256",
                "base_plan_sha256",
                "summary",
                "diff",
                "updated_at",
            )
        },
    }


def project_task_status(project_root: Path, work_id: str) -> dict[str, Any]:
    work_dir = _work_dir(project_root, work_id)
    tasks = parse_superpowers_plan(find_plan(project_root, work_id))
    workflow = _read_json(work_dir / "workflow.json")
    mode = workflow.get("mode", "single")
    completed = _completed_tasks(project_root, work_dir, work_id)
    validation_strategy = _validation_strategy(workflow, completed, work_dir)
    next_incomplete = next(
        (task for task in tasks if task["number"] not in completed), None
    )
    authorized_task = _authorized_task(
        work_dir,
        mode,
        completed,
        next_incomplete["number"] if next_incomplete else None,
    )
    current = (
        next_incomplete
        if next_incomplete and next_incomplete["number"] == authorized_task
        else None
    )
    spec_amendment_chain: list[dict[str, Any]] = []
    spec_amendment: dict[str, Any] | None = None
    current_spec_amendment: dict[str, Any] | None = None
    spec_amendment_error = ""
    try:
        spec_amendment_chain = _spec_amendment_chain(
            project_root,
            work_dir,
            int(current["number"]) if current is not None else None,
            completed,
        )
        spec_amendment = (
            spec_amendment_chain[-1] if spec_amendment_chain else None
        )
        if current is not None:
            current_spec_amendment = next(
                (
                    amendment
                    for amendment in reversed(spec_amendment_chain)
                    if amendment.get("task") == current["number"]
                ),
                None,
            )
            current = _apply_task_override(current, current_spec_amendment)
    except TaskControlError as error:
        spec_amendment_error = str(error)
    scope_violation_files: list[str] = []
    approval_blockers: list[str] = []
    authorization_check_failed = False
    if next_incomplete is not None and current is None:
        approval_blockers.append(
            f"Task {next_incomplete['number']} 尚未获得用户明确授权"
        )
        try:
            scope_violation_files = changed_paths(project_root)
        except TaskControlError as error:
            authorization_check_failed = True
            approval_blockers.append(f"无法检查完整工作区：{error}")
        if scope_violation_files:
            approval_blockers.append(
                "存在未授权代码改动：" + ", ".join(scope_violation_files)
            )
    snapshot_sha = ""
    staged: list[str] = []
    out_of_scope: list[str] = []
    if current is not None:
        try:
            staged = _staged_paths(project_root)
            changed = changed_paths(project_root)
            snapshot_sha = _task_snapshot_sha(project_root, spec_amendment_chain)
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
        elif next_incomplete is not None and number == next_incomplete["number"]:
            task_status = "locked"
        else:
            task_status = "waiting"
        validation_status = "pending"
        if number in completed:
            try:
                commit_evidence = _read_json(
                    work_dir / "evidence" / f"commit-task{number}.json"
                )
                validation_status = str(
                    commit_evidence.get("validation_status", "passed")
                )
            except TaskControlError:
                validation_status = "unknown"
        projected.append(
            {**task, "status": task_status, "validation_status": validation_status}
        )

    current_projection: dict[str, Any] | None = None
    if current is not None:
        changed = changed_paths(project_root)
        unstaged = _unstaged_paths(project_root)
        amendment_spec_path = (
            str(current_spec_amendment.get("spec_path"))
            if current_spec_amendment
            else ""
        )
        amendment_staged = not amendment_spec_path or amendment_spec_path in staged
        amendment_unstaged = bool(
            amendment_spec_path
            and amendment_spec_path in _raw_unstaged_paths(project_root)
        )
        remote_ut_passed = _evidence_matches_snapshot(
            work_dir, "remote-ut", current["number"], snapshot_sha
        )
        cr_passed = _evidence_matches_snapshot(
            work_dir, "cr", current["number"], snapshot_sha
        )
        required_test_files = _planned_test_files(current)
        deleted_test_files = sorted(
            set(_staged_deleted_paths(project_root))
            & set(required_test_files)
        )
        deleted_test_files = sorted(
            set(deleted_test_files)
            | set(_test_files_removed_from_index(project_root, required_test_files))
        )
        missing_staged_test_files = [
            path for path in required_test_files if path not in staged
        ]
        advance_blockers: list[str] = []
        if not staged:
            advance_blockers.append("当前任务尚无已暂存改动")
        if unstaged:
            advance_blockers.append("仍有尚未暂存的改动：" + ", ".join(unstaged))
        if out_of_scope:
            advance_blockers.append("存在当前任务范围外文件：" + ", ".join(out_of_scope))
        if spec_amendment_error:
            advance_blockers.append(spec_amendment_error)
        if not amendment_staged:
            advance_blockers.append("规格附加修正产物尚未暂存")
        if amendment_unstaged:
            advance_blockers.append("规格附加修正产物仍有尚未暂存的内容")
        if validation_strategy == "final" and not required_test_files:
            advance_blockers.append("当前任务计划未声明测试文件")
        if validation_strategy == "final" and missing_staged_test_files:
            advance_blockers.append(
                "当前任务测试文件尚未暂存："
                + ", ".join(missing_staged_test_files)
            )
        if validation_strategy == "final" and deleted_test_files:
            advance_blockers.append(
                "测试文件不能以删除状态交付："
                + ", ".join(deleted_test_files)
            )
        if validation_strategy == "per_task" and not remote_ut_passed:
            advance_blockers.append(
                "规格附加修正后的当前工作区快照远程 UT 尚未通过"
                if current_spec_amendment
                else "当前工作区快照的远程 UT 尚未通过"
            )
        if validation_strategy == "per_task" and not cr_passed:
            advance_blockers.append(
                "规格附加修正后的当前工作区快照 CR 尚未通过"
                if current_spec_amendment
                else "当前工作区快照的 CR 尚未通过"
            )
        validation_ready = (
            validation_strategy == "final"
            and bool(required_test_files)
            and not missing_staged_test_files
            and not deleted_test_files
        ) or (
            validation_strategy == "per_task"
            and remote_ut_passed
            and cr_passed
        )
        can_advance = (
            mode == "single"
            and bool(staged)
            and not unstaged
            and not out_of_scope
            and not spec_amendment_error
            and amendment_staged
            and not deleted_test_files
            and not amendment_unstaged
            and validation_ready
        )
        current_projection = {
            **current,
            "status": "current",
            "snapshot_sha": snapshot_sha,
            "staged_files": staged,
            "changed_files": changed,
            "unstaged_files": unstaged,
            "out_of_scope_files": out_of_scope,
            "remote_ut_passed": remote_ut_passed,
            "cr_passed": cr_passed,
            "required_test_files": required_test_files,
            "validation_status": (
                "pending_final" if validation_strategy == "final" else "per_task"
            ),
            "can_advance": can_advance,
            "advance_blockers": advance_blockers,
        }
    return {
        "plan": str(
            find_plan(project_root, work_id).relative_to(project_root.resolve())
        ),
        "mode": mode,
        "validation_strategy": validation_strategy,
        "validation_strategy_locked": bool(completed),
        "tasks": projected,
        "tasks_total": len(tasks),
        "tasks_done": len(completed),
        "current_task": current_projection,
        "authorized_task": authorized_task,
        "awaiting_approval_task": next_incomplete["number"]
        if next_incomplete is not None and current is None
        else None,
        "scope_violation_files": scope_violation_files,
        "approval_blockers": approval_blockers,
        "spec_amendment": spec_amendment or {},
        "spec_amendment_chain": spec_amendment_chain,
        "spec_amendment_error": spec_amendment_error,
        "can_authorize": bool(
            mode == "single"
            and next_incomplete is not None
            and current is None
            and not scope_violation_files
            and not authorization_check_failed
        ),
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


def _record_task_authorization(
    work_dir: Path, *, completed_task: int, authorized_task: int | None
) -> None:
    control = _load_control(work_dir, strict=True)
    control["task_authorization"] = {
        "completed_task": completed_task,
        "authorized_task": authorized_task,
        "state": "authorized" if authorized_task is not None else "complete",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    _atomic_write_json(work_dir / "control.json", control)


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


def authorize_next_task(
    project_root: Path,
    work_id: str,
    *,
    expected_version: str,
    expected_task: int,
) -> dict[str, Any]:
    work_dir = _work_dir(project_root, work_id)
    if expected_version != work_state_version(work_dir):
        raise TaskControlConflict("开发任务状态已经变化，请刷新后重试")
    _validate_global_plan_gate(project_root, work_id)
    workflow = _read_json(work_dir / "workflow.json")
    if workflow.get("mode", "single") != "single":
        raise TaskControlConflict("连续推进模式不需要单独授权下一任务")
    tasks = parse_superpowers_plan(find_plan(project_root, work_id))
    completed = _completed_tasks(project_root, work_dir, work_id)
    if not completed:
        raise TaskControlConflict("Task 1 已默认授权，无需重复授权")
    next_task = next(
        (task for task in tasks if task["number"] not in completed), None
    )
    if next_task is None:
        raise TaskControlConflict("所有实施子任务已经完成")
    if next_task["number"] != expected_task:
        raise TaskControlConflict(
            f"下一实施子任务是 Task {next_task['number']}，不是 Task {expected_task}"
        )
    if _authorized_task(work_dir, "single", completed, expected_task) == expected_task:
        raise TaskControlConflict(f"Task {expected_task} 已经获得授权")
    dirty = changed_paths(project_root)
    if dirty:
        raise TaskControlConflict("存在未授权代码改动：" + ", ".join(dirty))
    _record_task_authorization(
        work_dir,
        completed_task=max(completed),
        authorized_task=expected_task,
    )
    return {
        "work": work_id,
        "completed_task": max(completed),
        "authorized_task": expected_task,
    }


def _validate_global_plan_gate(project_root: Path, work_id: str) -> None:
    """复用观察板状态机，确保自然语言入口与页面入口执行同一套硬门禁。"""
    module_path = Path(__file__).with_name("workflow_state.py")
    spec = importlib.util.spec_from_file_location(
        "byted_workflow_advance_guard", module_path
    )
    if spec is None or spec.loader is None:
        raise TaskControlConflict("无法加载全局计划门禁")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    try:
        status = module.build_status(project_root, work_id)
    except module.DashboardError as error:
        raise TaskControlConflict(f"全局计划门禁读取失败：{error}") from error
    plan_stage = status.get("stages", {}).get("plan", {})
    if plan_stage.get("status") != "passed":
        blockers = plan_stage.get("blockers") or ["规格、精确位置或计划尚未通过"]
        raise TaskControlConflict("全局计划门禁未通过：" + "；".join(blockers))


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

    _validate_global_plan_gate(project_root, work_id)

    workflow = _read_json(work_dir / "workflow.json")
    if workflow.get("mode", "single") != "single":
        raise TaskControlConflict("连续推进模式不能手动推进下一个任务")

    tasks = parse_superpowers_plan(find_plan(project_root, work_id))
    completed = _completed_tasks(project_root, work_dir, work_id)
    validation_strategy = _validation_strategy(workflow, completed, work_dir)
    current = next((task for task in tasks if task["number"] not in completed), None)
    if current is None:
        raise TaskControlConflict("所有实施子任务已经完成")
    if _authorized_task(work_dir, "single", completed, current["number"]) != current["number"]:
        raise TaskControlConflict(
            f"Task {current['number']} 尚未获得用户推进授权"
        )
    amendment_chain = _spec_amendment_chain(
        project_root, work_dir, int(current["number"]), completed
    )
    amendment = next(
        (
            item
            for item in reversed(amendment_chain)
            if item.get("task") == current["number"]
        ),
        None,
    )
    current = _apply_task_override(current, amendment)
    if current["number"] != expected_task:
        raise TaskControlConflict(
            f"当前实施子任务是 Task {current['number']}，不是 Task {expected_task}"
        )

    staged = _staged_paths(project_root)
    if not staged:
        raise TaskControlConflict("暂存区为空，不能创建空提交")
    if amendment:
        amendment_spec_path = str(amendment.get("spec_path", ""))
        if amendment_spec_path not in staged:
            raise TaskControlConflict("规格附加修正产物尚未暂存")
        if amendment_spec_path in _raw_unstaged_paths(project_root):
            raise TaskControlConflict("规格附加修正产物仍有尚未暂存的内容")
    out_of_scope = validate_task_scope(project_root, current)
    if out_of_scope:
        raise TaskControlConflict(
            "暂存区包含当前任务范围外文件：" + ", ".join(out_of_scope)
        )
    unstaged = _unstaged_paths(project_root)
    if unstaged:
        raise TaskControlConflict(
            "工作区仍有尚未暂存的改动：" + ", ".join(unstaged)
        )
    required_test_files = _planned_test_files(current)
    if validation_strategy == "final":
        if not required_test_files:
            raise TaskControlConflict("当前任务计划未声明测试文件")
        deleted_test_files = sorted(
            (set(_staged_deleted_paths(project_root)) & set(required_test_files))
            | set(_test_files_removed_from_index(project_root, required_test_files))
        )
        if deleted_test_files:
            raise TaskControlConflict(
                "测试文件不能以删除状态交付："
                + ", ".join(deleted_test_files)
            )
        missing_staged_test_files = [
            path for path in required_test_files if path not in staged
        ]
        if missing_staged_test_files:
            raise TaskControlConflict(
                "当前任务测试文件尚未暂存："
                + ", ".join(missing_staged_test_files)
            )
    snapshot_sha = _task_snapshot_sha(project_root, amendment_chain)
    if validation_strategy == "per_task":
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
            "staged_files": staged,
            "validation_strategy": validation_strategy,
            "validation_status": (
                "pending_final" if validation_strategy == "final" else "passed"
            ),
        },
    )
    next_task = next(
        (task["number"] for task in tasks if task["number"] > expected_task), None
    )
    _record_task_authorization(
        work_dir, completed_task=expected_task, authorized_task=next_task
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
