#!/usr/bin/env python3
"""Persist plugin-owned state and project Hammer state without writing `.hammer`."""

from __future__ import annotations

import argparse
import copy
import json
import re
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


WORK_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}$")
WORKTREE_MIGRATION_RE = re.compile(
    r"workspace\.worktree\s+decision=migrated_away\s+path=(.+?)"
    r"(?:\s+tool=\S+)?\s*$"
)
PLUGIN_RELATIVE = Path(".cosh") / "hammer-plugin"
STAGE_DEFINITIONS = (
    ("launch", "需求入口", "launch/launch.json"),
    ("hammer_design", "Hammer 设计", None),
    ("hammer_review", "Hammer 三路评审", None),
    ("hammer_plan", "Hammer 计划", None),
    ("code_facts", "CodeGraph 代码事实", "coding/code-facts.json"),
    ("change_surface", "预计修改面", "coding/change-surface.json"),
    ("locations", "精准定位", "coding/locations.json"),
    ("coding_plan", "编码计划", "coding/implementation-plan.md"),
    ("implementation", "细分任务实现", "coding/tasks.json"),
    ("hammer_validation", "Hammer 验证", None),
    ("delivery", "Hammer 交付", None),
)


class CoshHammerError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _validate_work(work_id: str) -> str:
    if not WORK_RE.fullmatch(work_id):
        raise CoshHammerError("work-id 只能包含字母、数字、点、下划线和短横线")
    return work_id


def plugin_root(project: Path, work_id: str) -> Path:
    project = project.resolve()
    relative_parts = (Path(".cosh"), Path(".cosh") / "hammer-plugin")
    for relative in relative_parts:
        candidate = project / relative
        if candidate.is_symlink():
            raise CoshHammerError(f"插件状态目录不得是符号链接：{candidate}")
    root = project / PLUGIN_RELATIVE / _validate_work(work_id)
    if root.is_symlink():
        raise CoshHammerError(f"work 状态目录不得是符号链接：{root}")
    return root


def _assert_plugin_destination(owner_root: Path, path: Path) -> None:
    owner = owner_root.resolve(strict=False)
    candidate = path.resolve(strict=False)
    try:
        candidate.relative_to(owner)
    except ValueError as error:
        raise CoshHammerError(f"插件写入路径越界：{path}") from error
    current = owner_root
    if current.is_symlink():
        raise CoshHammerError(f"插件状态目录不得是符号链接：{current}")
    try:
        relative = path.relative_to(owner_root)
    except ValueError as error:
        raise CoshHammerError(f"插件写入路径不属于当前 work：{path}") from error
    for part in relative.parts[:-1]:
        current = current / part
        if current.is_symlink():
            raise CoshHammerError(f"插件状态子目录不得是符号链接：{current}")


def _atomic_json(
    path: Path, payload: Mapping[str, Any], *, owner_root: Path
) -> None:
    _assert_plugin_destination(owner_root, path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.replace(path)


def _write_text(owner_root: Path, path: Path, content: str) -> None:
    _assert_plugin_destination(owner_root, path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CoshHammerError(f"无法读取 {path}: {error}") from error
    if not isinstance(value, dict):
        raise CoshHammerError(f"{path} 必须是 JSON 对象")
    return value


def validate_hammer_root(hammer_root: Path) -> Path:
    resolved = hammer_root.expanduser().resolve()
    skill = resolved / "SKILL.md"
    if not skill.is_file():
        raise CoshHammerError(f"Hammer 不可用：缺少 {skill}")
    try:
        text = skill.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise CoshHammerError(f"Hammer 不可用：无法读取 {skill}") from error
    frontmatter = re.match(r"\A---\s*\n(.*?)\n---(?:\s*\n|\Z)", text, re.DOTALL)
    if not frontmatter or not re.search(
        r"(?m)^name:\s*[\"']?hammer[\"']?\s*$", frontmatter.group(1)
    ):
        raise CoshHammerError(f"Hammer 不可用：{skill} 的 name 不是 hammer")
    return resolved


def initialize_launch(
    project: Path,
    *,
    work_id: str,
    refined_requirement: str,
    source: Mapping[str, Any],
    hammer_root: Path,
    worktree_policy: str = "skip",
) -> dict[str, Any]:
    project = project.resolve()
    if not project.is_dir():
        raise CoshHammerError(f"项目目录不存在：{project}")
    hammer = validate_hammer_root(hammer_root)
    if not refined_requirement.strip():
        raise CoshHammerError("澄清后的需求不能为空")
    if worktree_policy not in {"skip", "open"}:
        raise CoshHammerError("worktree 策略只能是 skip 或 open")
    root = plugin_root(project, work_id)
    launch_dir = root / "launch"
    launch_dir.mkdir(parents=True, exist_ok=True)
    request = {
        "work": work_id,
        "source": dict(source),
        "refined_requirement": refined_requirement.strip(),
        "updated_at": _now(),
    }
    _atomic_json(launch_dir / "request.json", request, owner_root=root)
    _write_text(
        root,
        launch_dir / "request.md",
        f"# {work_id}\n\n{refined_requirement.strip()}\n",
    )
    if worktree_policy == "open":
        worktree_reason = "用户在本次 cosh-hammer 请求中明确要求使用 worktree"
    else:
        worktree_reason = (
            "用户通过 cosh-hammer 明确选择默认关闭 worktree；本次未明确指定开启"
        )
    worktree_decision = (
        "本次工作区隔离决策来自用户，请由 Hammer 自己在 Stage 1 产物中按以下合法 "
        "schema 记录；插件不得写入 `.hammer/`，也不要再次询问：\n\n"
        "## 工作区隔离决策\n"
        f"- decision: {worktree_policy}\n"
        "- source: user\n"
        f"- reason: {worktree_reason}\n\n"
    )
    hammer_prompt = (
        "$hammer\n\n"
        f"{worktree_decision}"
        "请以 Hammer 作为唯一主流程处理以下需求。设计、三路技术评审、上报、计划、"
        "最终 UT/CI/CR/E2E 与交付均使用 Hammer 原生流程；进入 Execute 编码任务时，"
        "使用 $cosh-hammer 编码模式细化并实现当前 Hammer 父任务。为了让标准 task-dispatch "
        "稳定传递该约束，请在 .hammer/plan/plan.md 的每个 coding task 执行说明中原样保留："
        "`Use $cosh-hammer in coding mode for this Hammer parent task.`；该计划文件仍只能由 "
        "Hammer 生成和维护。\n\n"
        f"需求：\n{refined_requirement.strip()}"
    )
    launch = {
        "schema_version": 1,
        "work": work_id,
        "project": str(project),
        "hammer": {"required": True, "root": str(hammer)},
        "worktree": {"policy": worktree_policy, "source": "user"},
        "hammer_prompt": hammer_prompt,
        "dashboard_url": f"http://127.0.0.1:57172/?work={work_id}",
        "created_at": _now(),
    }
    _atomic_json(launch_dir / "launch.json", launch, owner_root=root)
    return launch


def _artifact_status(path: Path) -> str:
    if not path.is_file():
        return "pending"
    if path.suffix == ".json":
        value = _read_json(path)
        status = str(value.get("status", "passed")).lower()
        return status if status in {"pending", "running", "passed", "blocked", "failed"} else "running"
    return "passed" if path.stat().st_size else "pending"


def _markdown_field(text: str, name: str) -> str | None:
    match = re.search(
        rf"(?m)^\s*(?:[-*]\s*)?{re.escape(name)}\s*:\s*`?([^`\n]+?)`?\s*$",
        text,
    )
    return match.group(1).strip() if match else None


def _hammer_state(project: Path) -> dict[str, Any]:
    hammer_dir = project / ".hammer"
    if not hammer_dir.is_dir():
        return {
            "stage": "design",
            "status": "pending",
            "current_task": None,
            "source": None,
        }

    execute_session = hammer_dir / "execute" / "session.md"
    plan_session = hammer_dir / "plan" / "session.md"
    plan = hammer_dir / "plan" / "plan.md"
    design_session = hammer_dir / "design" / "session.md"
    design = hammer_dir / "design" / "design.md"
    source: Path | None = None
    current_task: str | None = None

    if execute_session.is_file():
        source = execute_session
        text = execute_session.read_text(encoding="utf-8")
        next_action = _markdown_field(text, "next_action")
        if not next_action:
            raise CoshHammerError("Hammer execute/session.md 缺少 next_action")
        current_task = _markdown_field(text, "current_task_ref") or _markdown_field(
            text, "current_task"
        )
        blocker = (_markdown_field(text, "blocker") or "").lower()
        if next_action == "finalize-done":
            stage, status = "done", "passed"
        elif next_action in {"await-user-acceptance-finalize", "blocked-finalize"} or next_action == "run-step-7":
            stage = "delivery"
            status = "blocked" if next_action == "blocked-finalize" else "running"
        elif next_action in {"run-step-5", "run-step-6", "await-user-decision-ci"}:
            stage = "validation"
            status = "blocked" if next_action == "await-user-decision-ci" else "running"
        else:
            stage, status = "execute", "running"
        if blocker not in {"", "none", "无", "-"}:
            status = "blocked"
    elif plan.is_file():
        source = plan
        stage, status = "plan", "running"
        handoff = hammer_dir / "plan" / "handoff.json"
        if handoff.is_file():
            handoff_status = str(_read_json(handoff).get("status", "")).lower()
            if handoff_status == "passed":
                status = "passed"
            elif handoff_status in {"blocked", "failed"}:
                status = "blocked"
    elif plan_session.is_file():
        source = plan_session
        text = plan_session.read_text(encoding="utf-8")
        if not _markdown_field(text, "current_stage"):
            raise CoshHammerError("Hammer plan/session.md 缺少 current_stage")
        stage, status = "plan", "running"
    elif design.is_file():
        source = design
        reports = tuple(
            hammer_dir / "design" / name
            for name in ("review.md", "security-review.md", "stability-review.md")
        )
        stage = "review"
        report_statuses = []
        for report in reports:
            if not report.is_file():
                report_statuses.append("missing")
                continue
            text = report.read_text(encoding="utf-8")
            report_statuses.append((_markdown_field(text, "status") or "unknown").lower())
        terminal = {"pass", "passed", "skipped_after_limit"}
        failures = {"block", "blocked", "fail", "failed"}
        if all(item in terminal for item in report_statuses):
            status = "passed"
        elif any(item in failures for item in report_statuses):
            status = "blocked"
        else:
            status = "running"
    elif design_session.is_file() or (hammer_dir / "design").is_dir():
        source = design_session if design_session.is_file() else None
        stage, status = "design", "running"
    else:
        stage, status = "design", "pending"
    return {
        "stage": stage,
        "status": status,
        "current_task": current_task,
        "source": str(source.relative_to(project)) if source else None,
    }


def _git_output(project: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(project), *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip() or "未知 Git 错误"
        raise CoshHammerError(f"无法校验 Hammer worktree：{detail}")
    return result.stdout.strip()


def _git_common_dir(project: Path) -> Path:
    value = Path(_git_output(project, "rev-parse", "--git-common-dir"))
    return (value if value.is_absolute() else project / value).resolve()


def _validate_migration_target(origin: Path, target: Path) -> Path:
    candidate = target.expanduser().resolve()
    if not candidate.is_dir():
        raise CoshHammerError(f"Hammer worktree 迁移目标不存在：{candidate}")
    if not (candidate / ".hammer" / "design" / "session.md").is_file():
        raise CoshHammerError(f"Hammer worktree 迁移目标缺少 design/session.md：{candidate}")
    try:
        top_level = Path(_git_output(candidate, "rev-parse", "--show-toplevel")).resolve()
        registered = {
            Path(line.removeprefix("worktree ")).resolve()
            for line in _git_output(
                candidate, "worktree", "list", "--porcelain"
            ).splitlines()
            if line.startswith("worktree ")
        }
    except CoshHammerError as error:
        raise CoshHammerError(
            f"Hammer 迁移目标不是已注册的 Git worktree：{candidate}"
        ) from error
    if top_level != candidate or candidate not in registered:
        raise CoshHammerError(f"Hammer 迁移目标不是已注册的 Git worktree：{candidate}")
    origin_common = _git_common_dir(origin)
    candidate_common = _git_common_dir(candidate)
    try:
        candidate_common.relative_to(origin_common)
    except ValueError as error:
        raise CoshHammerError(f"Hammer 迁移目标不是当前仓库的 Git worktree：{candidate}") from error
    return candidate


def _last_worktree_migration(project: Path) -> Path | None:
    session = project / ".hammer" / "design" / "session.md"
    if not session.is_file():
        return None
    matches = [
        match.group(1).strip()
        for line in session.read_text(encoding="utf-8").splitlines()
        if (match := WORKTREE_MIGRATION_RE.search(line))
    ]
    if not matches:
        return None
    path = Path(matches[-1])
    return path if path.is_absolute() else project / path


def _active_project_root(project: Path) -> tuple[Path, list[str]]:
    origin = project.resolve()
    current = origin
    chain: list[str] = []
    visited = {origin}
    for _ in range(8):
        target = _last_worktree_migration(current)
        if target is None:
            return current, chain
        current = _validate_migration_target(origin, target)
        if current in visited:
            raise CoshHammerError("Hammer worktree 迁移链存在循环")
        visited.add(current)
        chain.append(str(current))
    raise CoshHammerError("Hammer worktree 迁移链超过 8 层")


def _hammer_stage_status(hammer: Mapping[str, Any], stage_id: str) -> str:
    stage = str(hammer.get("stage", "")).lower()
    status = str(hammer.get("status", "")).lower()
    order = {"design": 1, "review": 2, "plan": 3, "execute": 4, "validation": 5, "delivery": 6, "done": 7}
    current = next((value for key, value in order.items() if key in stage), 0)
    target = {
        "hammer_design": 1,
        "hammer_review": 2,
        "hammer_plan": 3,
        "hammer_validation": 5,
        "delivery": 6,
    }[stage_id]
    if current > target or status in {"passed", "done", "completed"} and current == target:
        return "passed"
    if current == target:
        return "blocked" if status in {"blocked", "failed"} else "running"
    return "pending"


def _live_status(project: Path, work_id: str) -> dict[str, Any]:
    project = project.resolve()
    root = plugin_root(project, work_id)
    launch = _read_json(root / "launch" / "launch.json")
    hammer_config = launch.get("hammer")
    if not isinstance(hammer_config, dict) or not hammer_config.get("required"):
        raise CoshHammerError("launch.json 缺少强制 Hammer 依赖")
    configured_root = hammer_config.get("root")
    if not isinstance(configured_root, str) or not configured_root:
        raise CoshHammerError("launch.json 缺少 Hammer 根目录")
    validate_hammer_root(Path(configured_root))
    active_project, migration_chain = _active_project_root(project)
    hammer = _hammer_state(active_project)
    stages = []
    for stage_id, label, relative in STAGE_DEFINITIONS:
        if relative:
            status = _artifact_status(root / relative)
        else:
            status = _hammer_stage_status(hammer, stage_id)
        stages.append({"id": stage_id, "label": label, "status": status})
    control_path = root / "coding" / "control.json"
    control = _read_json(control_path) if control_path.is_file() else {"mode": "single"}
    tasks_path = root / "coding" / "tasks.json"
    coding_tasks: list[dict[str, Any]] = []
    current_coding_task: dict[str, Any] | None = None
    if tasks_path.is_file():
        task_state = _read_json(tasks_path)
        raw_tasks = task_state.get("tasks", [])
        if not isinstance(raw_tasks, list) or not all(isinstance(item, dict) for item in raw_tasks):
            raise CoshHammerError("coding/tasks.json 的 tasks 必须是对象数组")
        coding_tasks = [dict(item) for item in raw_tasks]
        current_id = task_state.get("current_task")
        current_coding_task = next(
            (item for item in coding_tasks if item.get("id") == current_id), None
        )
        if current_coding_task is None:
            current_coding_task = next(
                (
                    item
                    for item in coding_tasks
                    if str(item.get("status", "pending")) in {"pending", "running"}
                ),
                None,
            )
    return {
        "schema_version": 1,
        "work": work_id,
        "project": str(project),
        "active_project": str(active_project),
        "workspace": {
            "migrated": bool(migration_chain),
            "migration_chain": migration_chain,
        },
        "hammer": hammer,
        "launch": {"dashboard_url": launch.get("dashboard_url")},
        "stages": stages,
        "control": control,
        "coding": {"current_task": current_coding_task, "tasks": coding_tasks},
        "stale": False,
        "controls_enabled": True,
        "read_at": _now(),
    }


def _cache_path(project: Path, work_id: str) -> Path:
    return plugin_root(project, work_id) / "dashboard" / "dashboard-state.json"


def build_status(project: Path, work_id: str) -> dict[str, Any]:
    cache = _cache_path(project, work_id)
    try:
        status = _live_status(project, work_id)
        persisted = {key: value for key, value in status.items() if key != "read_at"}
        _atomic_json(cache, persisted, owner_root=plugin_root(project, work_id))
        return status
    except Exception as error:
        if not cache.is_file():
            raise
        restored = copy.deepcopy(_read_json(cache))
        restored["stale"] = True
        restored["controls_enabled"] = False
        restored["projection_error"] = str(error)
        restored["read_at"] = _now()
        return restored


def apply_control(
    project: Path, work_id: str, command: Mapping[str, Any]
) -> dict[str, Any]:
    root = plugin_root(project, work_id)
    if not (root / "launch" / "launch.json").is_file():
        raise CoshHammerError("work 尚未初始化")
    # 控制 API 也必须重新验证 Hammer；页面 disabled 不是安全边界。
    live = _live_status(project.resolve(), work_id)
    if live.get("stale"):
        raise CoshHammerError("Hammer 实时状态不可用，禁止修改插件控制")
    action = command.get("action")
    path = root / "coding" / "control.json"
    state = _read_json(path) if path.is_file() else {"mode": "single"}
    if action == "set-mode":
        mode = command.get("mode")
        if mode not in {"single", "continuous"}:
            raise CoshHammerError("mode 只能是 single 或 continuous")
        state["mode"] = mode
    elif action == "authorize-task":
        task = command.get("task")
        if not isinstance(task, str) or not task.strip():
            raise CoshHammerError("缺少 task")
        tasks_path = root / "coding" / "tasks.json"
        if not tasks_path.is_file():
            raise CoshHammerError("尚未生成细分任务，不能授权")
        task_state = _read_json(tasks_path)
        raw_tasks = task_state.get("tasks")
        if not isinstance(raw_tasks, list):
            raise CoshHammerError("coding/tasks.json 的 tasks 无效")
        known = {
            str(item.get("id"))
            for item in raw_tasks
            if isinstance(item, dict) and item.get("id") is not None
        }
        if task.strip() not in known:
            raise CoshHammerError("授权目标不是当前 work 的细分任务")
        state["authorized_task"] = task.strip()
    else:
        raise CoshHammerError("不支持的插件控制动作")
    state["updated_at"] = _now()
    _atomic_json(path, state, owner_root=root)
    return state


def record_dashboard_runtime(
    project: Path, work_id: str, runtime: Mapping[str, Any]
) -> None:
    root = plugin_root(project, work_id)
    _atomic_json(
        root / "dashboard" / "runtime.json", runtime, owner_root=root
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init", help="固化澄清需求并生成 Hammer prompt")
    init.add_argument("--project", type=Path, required=True)
    init.add_argument("--work", required=True)
    init.add_argument("--requirement", required=True)
    init.add_argument("--source-kind", choices=("text", "file"), default="text")
    init.add_argument("--source", required=True)
    init.add_argument("--hammer-root", type=Path, required=True)
    init.add_argument(
        "--worktree",
        choices=("skip", "open"),
        default="skip",
        help="工作区隔离策略；默认关闭，仅在用户明确要求时使用 open",
    )
    status = sub.add_parser("status", help="输出观察板投影")
    status.add_argument("--project", type=Path, required=True)
    status.add_argument("--work", required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.command == "init":
            payload = initialize_launch(
                args.project,
                work_id=args.work,
                refined_requirement=args.requirement,
                source={"kind": args.source_kind, "value": args.source},
                hammer_root=args.hammer_root,
                worktree_policy=args.worktree,
            )
        else:
            payload = build_status(args.project, args.work)
    except CoshHammerError as error:
        raise SystemExit(str(error)) from error
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
