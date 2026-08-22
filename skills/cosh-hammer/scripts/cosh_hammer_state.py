#!/usr/bin/env python3
"""Persist plugin-owned state and project Hammer state without writing `.hammer`."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


WORK_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}$")
WORKTREE_MIGRATION_RE = re.compile(
    r"workspace\.worktree\s+decision=migrated_away\s+path=(.+?)"
    r"(?:\s+tool=\S+)?\s*$"
)
MAX_ARTIFACT_BYTES = 2 * 1024 * 1024
FIXED_DASHBOARD_PORT = 57172
CODING_TRIGGER = "Use $cosh-hammer in coding mode for this Hammer parent task."
PLAN_HANDOFF_CHECKS = (
    "ac_task_test_mapping",
    "external_dependencies",
    "task_dependencies",
    "task_executability",
    "risk_classification",
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
    meego_id: str | None = None,
) -> dict[str, Any]:
    project = project.resolve()
    if not project.is_dir():
        raise CoshHammerError(f"项目目录不存在：{project}")
    hammer = validate_hammer_root(hammer_root)
    if not refined_requirement.strip():
        raise CoshHammerError("澄清后的需求不能为空")
    if worktree_policy not in {"skip", "open"}:
        raise CoshHammerError("worktree 策略只能是 skip 或 open")
    normalized_meego_id = meego_id.strip() if meego_id is not None else ""
    if normalized_meego_id and not re.fullmatch(r"[1-9][0-9]*", normalized_meego_id):
        raise CoshHammerError("Meego ID 必须是正整数")
    if normalized_meego_id:
        meego = {
            "bound": True,
            "id": normalized_meego_id,
            "url": (
                "https://meego.larkoffice.com/larksuite/story/detail/"
                f"{normalized_meego_id}"
            ),
        }
        meego_decision = (
            "用户已通过 cosh-hammer 绑定当前需求 Meego。请由 Hammer 自己在 Stage 1 "
            "产物中按以下合法 schema 记录，插件不得写入 `.hammer/`：\n\n"
            "## Meego 处理决策\n"
            "- decision: existing\n"
            "- source: user\n"
            f"- url: {meego['url']}\n"
            f"- reason: 用户绑定 Meego ID {normalized_meego_id}\n\n"
        )
    else:
        meego = {"bound": False}
        meego_decision = ""
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
        f"{meego_decision}"
        "请以 Hammer 作为唯一主流程处理以下需求。设计、三路技术评审、上报、计划、"
        "最终 UT/CI/CR/E2E 与交付均使用 Hammer 原生流程；进入 Execute 编码任务时，"
        "使用 $cosh-hammer 编码模式细化并实现当前 Hammer 父任务。为了让标准 task-dispatch "
        "稳定传递该约束，请在 .hammer/plan/plan.md 的每个 coding task 执行说明中原样保留："
        "`Use $cosh-hammer in coding mode for this Hammer parent task.`；该计划文件仍只能由 "
        "Hammer 生成和维护。Hammer Plan Ready 后、进入 Execute 分发任何 coding task 前，"
        "必须先运行 Cosh 的 `verify-handoff`；校验失败时返回 `BLOCKED` 并回到 Plan 修正，"
        "不得改派普通 coding worker。Cosh 编码 worker 在 CodeGraph 前还必须运行 "
        "`verify-coding --task <当前 Hammer Task>`，失败时不得开始编码。校验通过后必须暂停 "
        "Hammer 的原生编码执行，由 Cosh 依次生成编码产物和细分任务，并取得当前父任务的"
        "临时编码所有权。Hammer 只等待 Cosh handoff；收到 `status: DONE` 且 "
        "`next_action: hammer_continue_after_coding` 后，将当前 coding task 视为已由 Cosh 完成，"
        "继续下一个 Hammer task；全部 coding task 完成后进入编码后的原生 Gate。\n\n"
        f"需求：\n{refined_requirement.strip()}"
    )
    launch = {
        "schema_version": 1,
        "work": work_id,
        "project": str(project),
        "hammer": {"required": True, "root": str(hammer)},
        "worktree": {"policy": worktree_policy, "source": "user"},
        "meego": meego,
        "hammer_prompt": hammer_prompt,
        "dashboard_url": f"http://127.0.0.1:57172/?work={work_id}",
        "created_at": _now(),
    }
    _atomic_json(launch_dir / "launch.json", launch, owner_root=root)
    return launch


def _dashboard_payload(project: Path, work_id: str, endpoint: str) -> dict[str, Any]:
    if endpoint not in {"healthz", "status"}:
        raise CoshHammerError("不支持的观察板探测端点")
    path = "/healthz" if endpoint == "healthz" else "/api/status"
    query = urllib.parse.urlencode({"work": work_id})
    url = f"http://127.0.0.1:{FIXED_DASHBOARD_PORT}{path}?{query}"
    try:
        with urllib.request.urlopen(url, timeout=1) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, ValueError, urllib.error.URLError, json.JSONDecodeError) as error:
        raise CoshHammerError(f"观察板不可用：{error}") from error
    if not isinstance(payload, dict):
        raise CoshHammerError("观察板返回值不是 JSON 对象")
    return payload


def _validate_launch_contract(project: Path, work_id: str, launch: Mapping[str, Any]) -> None:
    if launch.get("work") != work_id or launch.get("project") != str(project.resolve()):
        raise CoshHammerError("launch.json 的 project/work 与当前入口不一致")
    worktree = launch.get("worktree")
    if not isinstance(worktree, dict) or worktree.get("policy") not in {"skip", "open"} or worktree.get("source") != "user":
        raise CoshHammerError("launch.json 未固化合法 worktree 用户决策")
    meego = launch.get("meego")
    if not isinstance(meego, dict) or not isinstance(meego.get("bound"), bool):
        raise CoshHammerError("launch.json 未固化 Meego 绑定决策")
    if meego.get("bound") and (
        not isinstance(meego.get("id"), str) or not isinstance(meego.get("url"), str)
    ):
        raise CoshHammerError("launch.json 的 Meego 绑定信息不完整")
    prompt = launch.get("hammer_prompt")
    if not isinstance(prompt, str) or CODING_TRIGGER not in prompt:
        raise CoshHammerError("hammer_prompt 缺少 Cosh 编码触发语句")


def run_preflight(project: Path, work_id: str) -> dict[str, Any]:
    project = project.resolve()
    root, launch, active_project, _migration_chain = _launch_context(project, work_id)
    _validate_launch_contract(project, work_id, launch)
    try:
        health = _dashboard_payload(project, work_id, "healthz")
    except CoshHammerError:
        raise
    except OSError as error:
        raise CoshHammerError(f"观察板不可用：{error}") from error
    if (
        health.get("status") != "ready"
        or health.get("project") != str(project)
        or health.get("work") != work_id
        or health.get("port") != FIXED_DASHBOARD_PORT
    ):
        raise CoshHammerError("观察板 healthz 的 project/work/port 不匹配")
    result = {
        "status": "passed",
        "gate": "preflight",
        "work": work_id,
        "project": str(project),
        "active_project": str(active_project),
        "dashboard": health,
        "checked_at": _now(),
    }
    _atomic_json(root / "gates" / "preflight.json", result, owner_root=root)
    return result


def _plan_coding_tasks(plan_text: str) -> list[dict[str, str]]:
    headings = list(
        re.finditer(r"(?m)^##\s+(\d+(?:\.\d+)*)\.\s+(.+?)\s*$", plan_text)
    )
    tasks: list[dict[str, str]] = []
    for index, heading in enumerate(headings):
        title = heading.group(2).strip()
        if "默认能力" not in title:
            continue
        end = headings[index + 1].start() if index + 1 < len(headings) else len(plan_text)
        block = plan_text[heading.start():end]
        tasks.append(
            {
                "ref": f"Task {heading.group(1)}",
                "title": title,
                "block": block,
            }
        )
    return tasks


def _validate_plan_handoff_evidence(handoff: Mapping[str, Any]) -> None:
    evidence = handoff.get("evidence")
    if not isinstance(evidence, dict) or evidence.get("plan_lint") != "passed":
        raise CoshHammerError("Hammer Plan Handoff evidence.plan_lint 未通过")
    mode = handoff.get("mode")
    if mode in {"inline", "lite-inline"}:
        checks = evidence.get("inline_checks")
        if not isinstance(checks, dict):
            raise CoshHammerError("Hammer Plan Handoff evidence.inline_checks 缺失")
        for name in PLAN_HANDOFF_CHECKS:
            check = checks.get(name)
            if (
                not isinstance(check, dict)
                or check.get("status") != "passed"
                or not isinstance(check.get("evidence"), list)
                or not check["evidence"]
            ):
                raise CoshHammerError(f"Hammer Plan Handoff evidence.{name} 未闭合")
        return
    if mode == "reviewer":
        review = evidence.get("review")
        if not isinstance(review, dict) or review.get("verdict") not in {
            "pass",
            "pass_with_risks",
        }:
            raise CoshHammerError("Hammer Plan Handoff evidence.review 未通过")
        checks = review.get("checks")
        if not isinstance(checks, dict) or any(
            checks.get(name) != "passed" for name in PLAN_HANDOFF_CHECKS
        ):
            raise CoshHammerError("Hammer Plan Handoff reviewer checks 未闭合")
        return
    raise CoshHammerError("Hammer Plan Handoff mode 无效")


def verify_handoff(project: Path, work_id: str) -> dict[str, Any]:
    project = project.resolve()
    preflight = run_preflight(project, work_id)
    root, _launch, active_project, _migration_chain = _launch_context(project, work_id)
    dashboard = _dashboard_payload(project, work_id, "status")
    if (
        dashboard.get("stale")
        or dashboard.get("project") != str(project)
        or dashboard.get("work") != work_id
        or dashboard.get("active_project") != str(active_project)
    ):
        raise CoshHammerError("观察板状态 stale 或监听目标与当前 Hammer worktree 不一致")
    plan_path = active_project / ".hammer" / "plan" / "plan.md"
    handoff_path = active_project / ".hammer" / "plan" / "handoff.json"
    if not plan_path.is_file() or not handoff_path.is_file():
        raise CoshHammerError("Hammer Plan Ready 未完成：缺少 plan.md 或 handoff.json")
    handoff = _read_json(handoff_path)
    plan_sha = hashlib.sha256(plan_path.read_bytes()).hexdigest()
    if (
        handoff.get("status") != "passed"
        or handoff.get("plan_sha256") != plan_sha
    ):
        raise CoshHammerError("Hammer Plan Ready 未通过或 handoff 已过期")
    _validate_plan_handoff_evidence(handoff)
    tasks = _plan_coding_tasks(plan_path.read_text(encoding="utf-8"))
    if not tasks:
        raise CoshHammerError("Hammer Plan 没有可接管的 coding task")
    missing = [task["ref"] for task in tasks if CODING_TRIGGER not in task["block"]]
    if missing:
        raise CoshHammerError(
            "Hammer coding task 缺少 Cosh 触发语句：" + ", ".join(missing)
        )
    result = {
        "status": "passed",
        "gate": "plan-execute-handoff",
        "work": work_id,
        "project": str(project),
        "active_project": str(active_project),
        "plan_sha256": plan_sha,
        "coding_tasks": [task["ref"] for task in tasks],
        "preflight_checked_at": preflight["checked_at"],
        "checked_at": _now(),
    }
    _atomic_json(root / "gates" / "plan-handoff.json", result, owner_root=root)
    return result


def _normalize_task_ref(value: str) -> str:
    match = re.fullmatch(r"(?i)\s*task[-_\s]*(\d+(?:\.\d+)*)\s*", value)
    if not match:
        raise CoshHammerError(f"Hammer task ID 格式无效：{value}")
    return f"Task {match.group(1)}"


def verify_coding(project: Path, work_id: str, task_ref: str) -> dict[str, Any]:
    project = project.resolve()
    requested = _normalize_task_ref(task_ref)
    handoff = verify_handoff(project, work_id)
    root, _launch, active_project, _migration_chain = _launch_context(project, work_id)
    if requested not in handoff["coding_tasks"]:
        raise CoshHammerError("请求的 Hammer task 不是当前 Plan 中的 coding task")
    session_path = active_project / ".hammer" / "execute" / "session.md"
    if not session_path.is_file():
        raise CoshHammerError("Hammer Execute 尚未创建 session，禁止进入 Cosh 编码")
    session = session_path.read_text(encoding="utf-8")
    current_raw = _markdown_field(session, "current_task_ref")
    current_stage = _markdown_field(session, "current_stage")
    next_action = _markdown_field(session, "next_action")
    if not current_raw:
        raise CoshHammerError("Hammer Execute session 缺少 current_task_ref")
    current = _normalize_task_ref(current_raw)
    if current != requested:
        raise CoshHammerError(
            f"Cosh 请求 task 与 Hammer Execute 当前 task 不一致：{requested} != {current}"
        )
    if not current_stage or "coding" not in current_stage.lower() or next_action != "run-step-4":
        raise CoshHammerError("Hammer Execute 当前不处于 coding task 调度阶段")
    result = {
        "status": "passed",
        "gate": "coding-dispatch",
        "work": work_id,
        "project": str(project),
        "active_project": str(active_project),
        "hammer_task": current,
        "next_action": next_action,
        "plan_sha256": handoff["plan_sha256"],
        "checked_at": _now(),
    }
    _atomic_json(root / "gates" / "coding-dispatch.json", result, owner_root=root)
    return result


def _validated_coding_artifacts(root: Path) -> None:
    for relative in (
        "coding/code-facts.json",
        "coding/change-surface.json",
        "coding/locations.json",
    ):
        path = root / relative
        if not path.is_file() or _read_json(path).get("status") != "passed":
            raise CoshHammerError(f"Cosh 编码接管缺少已通过产物：{Path(relative).name}")
    plan = root / "coding" / "implementation-plan.md"
    if not plan.is_file() or not plan.read_text(encoding="utf-8").strip():
        raise CoshHammerError("Cosh 编码接管缺少 implementation-plan.md")


def _normalized_coding_tasks(
    task_spec: Mapping[str, Any], hammer_task: str
) -> list[dict[str, Any]]:
    raw_tasks = task_spec.get("tasks")
    if not isinstance(raw_tasks, list) or not raw_tasks:
        raise CoshHammerError("Cosh 编码接管至少需要一个细分任务")
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in raw_tasks:
        if not isinstance(raw, dict):
            raise CoshHammerError("Cosh 细分任务必须是 JSON 对象")
        task_id = raw.get("id")
        if (
            not isinstance(task_id, str)
            or not WORK_RE.fullmatch(task_id)
            or task_id in seen
        ):
            raise CoshHammerError("Cosh 细分任务 id 无效或重复")
        parent = raw.get("hammer_parent")
        if not isinstance(parent, str) or _normalize_task_ref(parent) != hammer_task:
            raise CoshHammerError("Cosh 细分任务跨越当前 Hammer 父任务")
        title = raw.get("title")
        description = raw.get("description")
        expected_files = raw.get("expected_files")
        symbols = raw.get("symbols")
        steps = raw.get("steps")
        dependencies = raw.get("dependencies", [])
        acceptance = raw.get("acceptance")
        if not isinstance(title, str) or not title.strip():
            raise CoshHammerError(f"Cosh 细分任务 {task_id} 缺少标题")
        if not isinstance(description, str) or not description.strip():
            raise CoshHammerError(f"Cosh 细分任务 {task_id} 缺少任务说明")
        if not isinstance(expected_files, list) or not expected_files or not all(
            isinstance(item, str) and item.strip() for item in expected_files
        ):
            raise CoshHammerError(f"Cosh 细分任务 {task_id} 缺少预计文件")
        if not isinstance(symbols, list) or not symbols or not all(
            isinstance(item, str) and item.strip() for item in symbols
        ):
            raise CoshHammerError(f"Cosh 细分任务 {task_id} 缺少修改符号")
        if not isinstance(steps, list) or not steps or not all(
            isinstance(item, str) and item.strip() for item in steps
        ):
            raise CoshHammerError(f"Cosh 细分任务 {task_id} 缺少实施步骤")
        if not isinstance(dependencies, list) or not all(
            isinstance(item, str) and WORK_RE.fullmatch(item) for item in dependencies
        ):
            raise CoshHammerError(f"Cosh 细分任务 {task_id} 的依赖无效")
        if not isinstance(acceptance, list) or not acceptance or not all(
            isinstance(item, str) and item.strip() for item in acceptance
        ):
            raise CoshHammerError(f"Cosh 细分任务 {task_id} 缺少验收点")
        task = dict(raw)
        task.update(
            {
                "id": task_id,
                "hammer_parent": hammer_task,
                "title": title.strip(),
                "description": description.strip(),
                "expected_files": [item.strip() for item in expected_files],
                "symbols": [item.strip() for item in symbols],
                "steps": [item.strip() for item in steps],
                "dependencies": list(dependencies),
                "acceptance": [item.strip() for item in acceptance],
                "status": "pending",
            }
        )
        normalized.append(task)
        seen.add(task_id)
    for task in normalized:
        unknown = [item for item in task["dependencies"] if item not in seen]
        if unknown:
            raise CoshHammerError(
                f"Cosh 细分任务 {task['id']} 引用了未知依赖：{', '.join(unknown)}"
            )
    return normalized


def activate_coding(
    project: Path,
    work_id: str,
    hammer_task: str,
    task_spec: Mapping[str, Any],
) -> dict[str, Any]:
    project = project.resolve()
    parent = _normalize_task_ref(hammer_task)
    gate = verify_coding(project, work_id, parent)
    root = plugin_root(project, work_id)
    _validated_coding_artifacts(root)
    tasks = _normalized_coding_tasks(task_spec, parent)
    ownership_path = root / "coding" / "ownership.json"
    if ownership_path.is_file():
        existing = _read_json(ownership_path)
        if existing.get("status") == "cosh_active":
            raise CoshHammerError("当前 Hammer 编码任务已由 Cosh 接管")
    now = _now()
    task_state = {
        "status": "running",
        "hammer_parent": parent,
        "current_task": tasks[0]["id"],
        "tasks": tasks,
        "updated_at": now,
    }
    control_path = root / "coding" / "control.json"
    if control_path.is_file():
        control = _read_json(control_path)
        control.pop("authorized_task", None)
    else:
        control = {"mode": "single"}
    control["updated_at"] = now
    ownership = {
        "status": "cosh_active",
        "owner": "cosh",
        "hammer_status": "paused_for_cosh",
        "hammer_task": parent,
        "plan_sha256": gate.get("plan_sha256"),
        "started_at": now,
        "updated_at": now,
    }
    _atomic_json(root / "coding" / "tasks.json", task_state, owner_root=root)
    _atomic_json(control_path, control, owner_root=root)
    _atomic_json(ownership_path, ownership, owner_root=root)
    return {
        "status": "cosh_active",
        "hammer_task": parent,
        "current_task": tasks[0]["id"],
        "task_count": len(tasks),
    }


def _coding_context(
    project: Path, work_id: str
) -> tuple[Path, dict[str, Any], dict[str, Any], dict[str, Any]]:
    project = project.resolve()
    root = plugin_root(project, work_id)
    ownership_path = root / "coding" / "ownership.json"
    tasks_path = root / "coding" / "tasks.json"
    if not ownership_path.is_file() or not tasks_path.is_file():
        raise CoshHammerError("当前 Hammer 编码任务尚未交给 Cosh")
    ownership = _read_json(ownership_path)
    if ownership.get("status") != "cosh_active":
        raise CoshHammerError("当前 Hammer 编码任务不处于 Cosh 活动所有权")
    hammer_task = ownership.get("hammer_task")
    if not isinstance(hammer_task, str):
        raise CoshHammerError("Cosh 编码所有权缺少 Hammer 父任务")
    verify_coding(project, work_id, hammer_task)
    tasks = _read_json(tasks_path)
    control_path = root / "coding" / "control.json"
    control = _read_json(control_path) if control_path.is_file() else {"mode": "single"}
    return root, ownership, tasks, control


def begin_subtask(project: Path, work_id: str, task_id: str) -> dict[str, Any]:
    root, ownership, state, control = _coding_context(project, work_id)
    if state.get("current_task") != task_id:
        raise CoshHammerError("只能开始当前 Cosh 细分任务")
    raw_tasks = state.get("tasks")
    if not isinstance(raw_tasks, list):
        raise CoshHammerError("coding/tasks.json 的 tasks 无效")
    selected = next(
        (item for item in raw_tasks if isinstance(item, dict) and item.get("id") == task_id),
        None,
    )
    if selected is None or selected.get("status") != "pending":
        raise CoshHammerError("当前 Cosh 细分任务不是 pending")
    status_by_id = {
        str(item.get("id")): str(item.get("status"))
        for item in raw_tasks
        if isinstance(item, dict)
    }
    unmet_dependencies = [
        dependency
        for dependency in selected.get("dependencies", [])
        if status_by_id.get(str(dependency)) != "passed"
    ]
    if unmet_dependencies:
        raise CoshHammerError(
            "当前 Cosh 细分任务依赖尚未通过：" + ", ".join(unmet_dependencies)
        )
    mode = control.get("mode", "single")
    if mode == "single" and control.get("authorized_task") != task_id:
        raise CoshHammerError("逐一任务模式需要用户授权当前 Cosh 细分任务")
    if mode not in {"single", "continuous"}:
        raise CoshHammerError("Cosh 编码推进模式无效")
    selected["status"] = "running"
    selected["started_at"] = _now()
    state["status"] = "running"
    state["updated_at"] = _now()
    ownership["updated_at"] = state["updated_at"]
    _atomic_json(root / "coding" / "tasks.json", state, owner_root=root)
    _atomic_json(root / "coding" / "ownership.json", ownership, owner_root=root)
    return {"status": "running", "task": dict(selected), "mode": mode}


def complete_subtask(
    project: Path,
    work_id: str,
    task_id: str,
    *,
    status: str,
    evidence: Mapping[str, Any],
) -> dict[str, Any]:
    if status not in {"passed", "blocked"}:
        raise CoshHammerError("Cosh 细分任务结果只能是 passed 或 blocked")
    if not isinstance(evidence, Mapping) or not evidence:
        raise CoshHammerError("Cosh 细分任务完成必须提供证据")
    root, ownership, state, control = _coding_context(project, work_id)
    if state.get("current_task") != task_id:
        raise CoshHammerError("只能完成当前 Cosh 细分任务")
    raw_tasks = state.get("tasks")
    if not isinstance(raw_tasks, list):
        raise CoshHammerError("coding/tasks.json 的 tasks 无效")
    selected = next(
        (item for item in raw_tasks if isinstance(item, dict) and item.get("id") == task_id),
        None,
    )
    if selected is None or selected.get("status") != "running":
        raise CoshHammerError("当前 Cosh 细分任务尚未开始")
    now = _now()
    selected["status"] = status
    selected["completed_at"] = now
    selected["evidence"] = dict(evidence)
    if status == "blocked":
        next_task = None
        state["current_task"] = task_id
        state["status"] = "blocked"
    else:
        next_task = next(
            (
                item
                for item in raw_tasks
                if isinstance(item, dict) and item.get("status") == "pending"
            ),
            None,
        )
        state["current_task"] = next_task.get("id") if next_task else None
        state["status"] = "passed" if next_task is None else "running"
    state["updated_at"] = now
    ownership["updated_at"] = now
    if control.get("mode", "single") == "single":
        control.pop("authorized_task", None)
        control["updated_at"] = now
        _atomic_json(root / "coding" / "control.json", control, owner_root=root)
    checkpoint = {
        "task": task_id,
        "hammer_parent": ownership["hammer_task"],
        "status": status,
        "evidence": dict(evidence),
        "completed_at": now,
    }
    _atomic_json(root / "coding" / "checkpoints" / f"{task_id}.json", checkpoint, owner_root=root)
    _atomic_json(root / "coding" / "tasks.json", state, owner_root=root)
    _atomic_json(root / "coding" / "ownership.json", ownership, owner_root=root)
    return {
        "status": state["status"],
        "completed_task": task_id,
        "current_task": state["current_task"],
    }


def _validate_commit(project: Path, commit_sha: str) -> str:
    value = commit_sha.strip()
    if not re.fullmatch(r"[0-9a-fA-F]{40}", value):
        raise CoshHammerError("Hammer 父任务 commit SHA 无效")
    result = subprocess.run(
        ["git", "-C", str(project), "cat-file", "-e", f"{value}^{{commit}}"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise CoshHammerError("Hammer 父任务 commit 不存在")
    return value.lower()


def complete_coding(
    project: Path,
    work_id: str,
    hammer_task: str,
    *,
    commit_sha: str,
) -> dict[str, Any]:
    project = project.resolve()
    parent = _normalize_task_ref(hammer_task)
    root, ownership, state, _control = _coding_context(project, work_id)
    if ownership.get("hammer_task") != parent:
        raise CoshHammerError("交还目标与当前 Hammer 父任务不一致")
    raw_tasks = state.get("tasks")
    if not isinstance(raw_tasks, list) or not raw_tasks or any(
        not isinstance(item, dict) or item.get("status") != "passed"
        for item in raw_tasks
    ):
        raise CoshHammerError("Cosh 细分任务尚未全部通过，不能交还 Hammer")
    commit = _validate_commit(project, commit_sha)
    now = _now()
    launch = _read_json(root / "launch" / "launch.json")
    result: dict[str, Any] = {
        "status": "DONE",
        "hammer_task": parent,
        "commit_sha": commit,
        "cosh_checkpoints": [item["id"] for item in raw_tasks],
        "next_action": "hammer_continue_after_coding",
        "completed_at": now,
    }
    meego = launch.get("meego")
    if isinstance(meego, dict) and meego.get("bound"):
        result["meego_id"] = meego.get("id")
    handoff_name = parent.lower().replace(" ", "-") + ".json"
    _atomic_json(root / "coding" / "parent-handoffs" / handoff_name, result, owner_root=root)
    ownership.update(
        {
            "status": "returned_to_hammer",
            "owner": "hammer",
            "hammer_status": "resume_after_coding",
            "commit_sha": commit,
            "completed_at": now,
            "updated_at": now,
        }
    )
    state["status"] = "passed"
    state["current_task"] = None
    state["updated_at"] = now
    _atomic_json(root / "coding" / "tasks.json", state, owner_root=root)
    _atomic_json(root / "coding" / "ownership.json", ownership, owner_root=root)
    return result


def attach_existing_hammer(
    project: Path,
    *,
    work_id: str,
    refined_requirement: str,
    hammer_root: Path,
    meego_id: str | None = None,
) -> dict[str, Any]:
    project = project.resolve()
    root = plugin_root(project, work_id)
    if (root / "launch" / "launch.json").exists():
        raise CoshHammerError("当前 work 已初始化，不需要迟到接入")
    active_project, migration_chain = _active_project_root(project)
    plan_path = active_project / ".hammer" / "plan" / "plan.md"
    if not plan_path.is_file():
        raise CoshHammerError("迟到接入要求 Hammer 已生成 plan.md")
    worktree_policy = "open" if migration_chain else "skip"
    launch = initialize_launch(
        project,
        work_id=work_id,
        refined_requirement=refined_requirement,
        source={"kind": "hammer-existing", "value": str(plan_path)},
        hammer_root=hammer_root,
        worktree_policy=worktree_policy,
        meego_id=meego_id,
    )
    tasks = _plan_coding_tasks(plan_path.read_text(encoding="utf-8"))
    missing = [task["ref"] for task in tasks if CODING_TRIGGER not in task["block"]]
    repair = (
        "Hammer Plan 必须回到 plan owner，为每个 coding task 补充 Cosh 触发语句后重跑 Plan Lint 与 Handoff；Cosh 不修改 .hammer。"
        if missing
        else "Hammer Plan 已包含 Cosh 触发语句；启动观察板后运行 verify-handoff。"
    )
    launch["entry_mode"] = "attached-existing"
    launch["hammer_prompt"] = (
        "$hammer\n\n当前 Hammer 已完成 Design/Plan，Cosh 正在迟到接入。"
        f"{repair}\n触发语句必须原样为：`{CODING_TRIGGER}`"
    )
    _atomic_json(root / "launch" / "launch.json", launch, owner_root=root)
    result = {
        "status": "blocked" if missing else "ready_for_handoff",
        "work": work_id,
        "project": str(project),
        "active_project": str(active_project),
        "missing_trigger_tasks": missing,
        "repair_required": repair,
        "dashboard_command": (
            "python3 scripts/start_cosh_hammer_dashboard.py "
            f"--project {project} --work {work_id} --hammer-root {validate_hammer_root(hammer_root)}"
        ),
        "created_at": _now(),
    }
    _atomic_json(root / "launch" / "attach.json", result, owner_root=root)
    return result


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


def _launch_context(
    project: Path, work_id: str
) -> tuple[Path, dict[str, Any], Path, list[str]]:
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
    return root, launch, active_project, migration_chain


def _artifact_category(scope: str, relative: Path) -> str:
    parts = relative.parts
    lowered = "/".join(parts).lower()
    name = relative.name.lower()
    if scope == "cosh":
        return "coding" if parts and parts[0] == "coding" else "requirement"
    if lowered.startswith("design/drafts/stage1-"):
        return "requirement"
    if lowered.startswith("design/reviews/"):
        return "review"
    if lowered.startswith("design/") and "review" in name:
        return "review"
    if lowered.startswith("design/"):
        return "design"
    if lowered.startswith("plan/"):
        return "plan"
    if lowered.startswith("execute/"):
        if any(
            token in name
            for token in ("meego", "mr.", "report", "finalize", "archive")
        ):
            return "delivery"
        if any(
            token in lowered
            for token in ("remote-ut", "test", "e2e", "ci", "review", "gate")
        ):
            return "validation"
        return "coding"
    return "delivery"


def _review_report(
    path: Path, *, channel: str, artifact_path: str
) -> dict[str, Any]:
    if not path.is_file():
        return {
            "channel": channel,
            "status": "pending",
            "review_mode": None,
            "review_pass": None,
            "review_attempt": None,
            "blocking_issue_count": None,
            "unresolved_finding_ids": None,
            "max_severity": None,
            "fallback_stage": None,
            "artifact_path": None,
        }
    text = path.read_text(encoding="utf-8")
    raw_count = _markdown_field(text, "blocking_issue_count")
    try:
        count = int(raw_count) if raw_count is not None else None
    except ValueError:
        count = None
    raw_attempt = _markdown_field(text, "review_attempt")
    try:
        attempt = int(raw_attempt) if raw_attempt is not None else None
    except ValueError:
        attempt = None
    return {
        "channel": channel,
        "status": (_markdown_field(text, "status") or "unknown").lower(),
        "review_mode": _markdown_field(text, "review_mode"),
        "review_pass": _markdown_field(text, "review_pass"),
        "review_attempt": attempt,
        "blocking_issue_count": count,
        "unresolved_finding_ids": _markdown_field(text, "unresolved_finding_ids"),
        "max_severity": _markdown_field(text, "max_severity"),
        "fallback_stage": _markdown_field(text, "fallback_stage"),
        "artifact_path": artifact_path,
    }


def _review_round_status(reports: list[dict[str, Any]]) -> str:
    statuses = {str(report.get("status", "unknown")).lower() for report in reports}
    if statuses & {"blocked", "reject_stage1", "reject_stage2", "failed", "unknown"}:
        return "blocked"
    if statuses and statuses <= {"pass", "passed", "skipped_after_limit"}:
        return "passed"
    return "running"


def _review_results(active_project: Path) -> dict[str, Any]:
    reviews_root = active_project / ".hammer" / "design" / "reviews"
    rounds: list[dict[str, Any]] = []
    if reviews_root.is_dir():
        round_dirs = sorted(
            (
                path
                for path in reviews_root.iterdir()
                if path.is_dir() and path.name.isdigit() and not path.is_symlink()
            ),
            key=lambda path: int(path.name),
            reverse=True,
        )
        for round_dir in round_dirs:
            reports = [
                _review_report(
                    round_dir / f"{channel}.md",
                    channel=channel,
                    artifact_path=f"design/reviews/{round_dir.name}/{channel}.md",
                )
                for channel in ("general", "security", "stability")
            ]
            rounds.append(
                {
                    "round": int(round_dir.name),
                    "status": _review_round_status(reports),
                    "reports": reports,
                }
            )
    if not rounds:
        design = active_project / ".hammer" / "design"
        legacy = (
            ("general", "review.md"),
            ("security", "security-review.md"),
            ("stability", "stability-review.md"),
        )
        if any((design / name).is_file() for _channel, name in legacy):
            reports = [
                _review_report(
                    design / name,
                    channel=channel,
                    artifact_path=f"design/{name}",
                )
                for channel, name in legacy
            ]
            attempts = [
                report["review_attempt"]
                for report in reports
                if report["review_attempt"] is not None
            ]
            rounds.append(
                {
                    "round": max(attempts) if attempts else 1,
                    "status": _review_round_status(reports),
                    "reports": reports,
                }
            )
    return {
        "latest_round": rounds[0]["round"] if rounds else None,
        "rounds": rounds,
    }


def _safe_artifact_path(root: Path, relative_path: str) -> tuple[Path, Path]:
    relative = Path(relative_path)
    if (
        not relative_path
        or relative.is_absolute()
        or ".." in relative.parts
        or "." in relative.parts
    ):
        raise CoshHammerError("产物路径无效")
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise CoshHammerError(f"产物路径不得包含符号链接：{relative_path}")
    candidate = (root / relative).resolve(strict=False)
    try:
        candidate.relative_to(root.resolve())
    except ValueError as error:
        raise CoshHammerError("产物路径越界") from error
    if not candidate.is_file():
        raise CoshHammerError(f"产物不存在：{relative_path}")
    return candidate, relative


def list_artifacts(project: Path, work_id: str) -> list[dict[str, Any]]:
    plugin, _launch, active_project, _chain = _launch_context(project, work_id)
    roots = (("hammer", active_project / ".hammer"), ("cosh", plugin))
    artifacts: list[dict[str, Any]] = []
    for scope, root in roots:
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.is_symlink():
                continue
            relative = path.relative_to(root)
            if scope == "cosh" and relative.parts[0] == "dashboard":
                continue
            try:
                candidate, relative = _safe_artifact_path(root, relative.as_posix())
            except CoshHammerError:
                continue
            stat = candidate.stat()
            artifacts.append(
                {
                    "scope": scope,
                    "path": relative.as_posix(),
                    "name": relative.name,
                    "category": _artifact_category(scope, relative),
                    "size": stat.st_size,
                    "updated_at_ns": stat.st_mtime_ns,
                }
            )
    return sorted(
        artifacts,
        key=lambda item: (item["category"], item["scope"], item["path"]),
    )


def read_artifact(
    project: Path,
    work_id: str,
    *,
    scope: str,
    relative_path: str,
) -> dict[str, Any]:
    plugin, _launch, active_project, _chain = _launch_context(project, work_id)
    if scope == "hammer":
        root = active_project / ".hammer"
    elif scope == "cosh":
        root = plugin
    else:
        raise CoshHammerError("产物 scope 只能是 hammer 或 cosh")
    candidate, relative = _safe_artifact_path(root, relative_path)
    size = candidate.stat().st_size
    if size > MAX_ARTIFACT_BYTES:
        return {
            "scope": scope,
            "path": relative.as_posix(),
            "category": _artifact_category(scope, relative),
            "kind": "large",
            "size": size,
            "content": None,
        }
    data = candidate.read_bytes()
    try:
        content = data.decode("utf-8")
        kind = "text"
    except UnicodeDecodeError:
        content = None
        kind = "binary"
    return {
        "scope": scope,
        "path": relative.as_posix(),
        "category": _artifact_category(scope, relative),
        "kind": kind,
        "size": size,
        "content": content,
    }


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


def _stage_progress(stages: list[dict[str, Any]]) -> dict[str, Any]:
    completed = sum(1 for stage in stages if stage["status"] == "passed")
    active = next(
        (
            stage
            for stage in stages
            if stage["status"] in {"running", "blocked", "failed"}
        ),
        None,
    )
    marker = "current"
    if active is None:
        active = next(
            (stage for stage in stages if stage["status"] == "pending"), None
        )
        marker = "next" if active is not None else "complete"
    for stage in stages:
        stage["progress_marker"] = marker if stage is active else None
    total = len(stages)
    return {
        "stage_id": active["id"] if active is not None else None,
        "label": active["label"] if active is not None else "全部完成",
        "marker": marker,
        "completed": completed,
        "total": total,
        "percent": round(completed / total * 100) if total else 100,
    }


def _live_status(project: Path, work_id: str) -> dict[str, Any]:
    project = project.resolve()
    root, launch, active_project, migration_chain = _launch_context(project, work_id)
    hammer = _hammer_state(active_project)
    stages = []
    for stage_id, label, relative in STAGE_DEFINITIONS:
        if relative:
            status = _artifact_status(root / relative)
        else:
            status = _hammer_stage_status(hammer, stage_id)
        stages.append({"id": stage_id, "label": label, "status": status})
    progress = _stage_progress(stages)
    control_path = root / "coding" / "control.json"
    control = _read_json(control_path) if control_path.is_file() else {"mode": "single"}
    tasks_path = root / "coding" / "tasks.json"
    ownership_path = root / "coding" / "ownership.json"
    ownership = _read_json(ownership_path) if ownership_path.is_file() else None
    coding_tasks: list[dict[str, Any]] = []
    current_coding_task: dict[str, Any] | None = None
    coding_state: dict[str, Any] = {}
    if tasks_path.is_file():
        coding_state = _read_json(tasks_path)
        raw_tasks = coding_state.get("tasks", [])
        if not isinstance(raw_tasks, list) or not all(isinstance(item, dict) for item in raw_tasks):
            raise CoshHammerError("coding/tasks.json 的 tasks 必须是对象数组")
        coding_tasks = [dict(item) for item in raw_tasks]
        current_id = coding_state.get("current_task")
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
    completed_tasks = sum(
        1 for item in coding_tasks if str(item.get("status")) == "passed"
    )
    blocked_tasks = sum(
        1 for item in coding_tasks if str(item.get("status")) == "blocked"
    )
    mode = control.get("mode", "single")
    if isinstance(ownership, dict) and ownership.get("status") == "returned_to_hammer":
        coding_next_action = "hammer_continue_after_coding"
    elif blocked_tasks:
        coding_next_action = "resolve_current_blocker"
    elif coding_tasks and completed_tasks == len(coding_tasks):
        coding_next_action = "create_parent_commit"
    elif current_coding_task and current_coding_task.get("status") == "running":
        coding_next_action = "execute_current_task"
    elif current_coding_task and mode == "single" and control.get(
        "authorized_task"
    ) != current_coding_task.get("id"):
        coding_next_action = "await_task_authorization"
    elif current_coding_task:
        coding_next_action = "begin_current_task"
    else:
        coding_next_action = "await_coding_handoff"
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
        "launch": {
            "dashboard_url": launch.get("dashboard_url"),
            "meego": launch.get("meego", {"bound": False}),
        },
        "stages": stages,
        "progress": progress,
        "control": control,
        "coding": {
            "current_task": current_coding_task,
            "tasks": coding_tasks,
            "ownership": ownership,
            "status": coding_state.get("status", "pending"),
            "next_action": coding_next_action,
            "progress": {
                "completed": completed_tasks,
                "blocked": blocked_tasks,
                "total": len(coding_tasks),
                "percent": round(completed_tasks / len(coding_tasks) * 100)
                if coding_tasks
                else 0,
            },
            "controls_enabled": bool(
                isinstance(ownership, dict)
                and ownership.get("status") == "cosh_active"
            ),
        },
        "review_results": _review_results(active_project),
        "artifacts": list_artifacts(project, work_id),
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
        ownership = live.get("coding", {}).get("ownership")
        if not isinstance(ownership, dict) or ownership.get("status") != "cosh_active":
            raise CoshHammerError("当前 Hammer 编码任务没有 Cosh 活动所有权")
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
        selected = next(
            (
                item
                for item in raw_tasks
                if isinstance(item, dict) and str(item.get("id")) == task.strip()
            ),
            None,
        )
        if selected is None:
            raise CoshHammerError("授权目标不是当前 work 的细分任务")
        if task_state.get("current_task") != task.strip():
            raise CoshHammerError("只能授权当前 Cosh 细分任务")
        if selected.get("status") != "pending":
            raise CoshHammerError("只能授权 pending 的当前 Cosh 细分任务")
        hammer_parent = selected.get("hammer_parent")
        if not isinstance(hammer_parent, str) or not hammer_parent.strip():
            raise CoshHammerError("细分任务缺少 Hammer 父任务引用")
        verify_coding(project, work_id, hammer_parent)
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
    init.add_argument(
        "--meego-id",
        help="可选的当前需求 Meego ID；未提供时不阻塞 cosh-hammer",
    )
    status = sub.add_parser("status", help="输出观察板投影")
    status.add_argument("--project", type=Path, required=True)
    status.add_argument("--work", required=True)
    preflight = sub.add_parser("preflight", help="调用 Hammer 前执行入口硬门")
    preflight.add_argument("--project", type=Path, required=True)
    preflight.add_argument("--work", required=True)
    handoff = sub.add_parser(
        "verify-handoff", help="Hammer Plan Ready 后验证 Cosh 接管契约"
    )
    handoff.add_argument("--project", type=Path, required=True)
    handoff.add_argument("--work", required=True)
    coding = sub.add_parser("verify-coding", help="CodeGraph 前验证当前 Hammer coding task")
    coding.add_argument("--project", type=Path, required=True)
    coding.add_argument("--work", required=True)
    coding.add_argument("--task", required=True)
    activate = sub.add_parser(
        "activate-coding", help="校验编码产物并由 Cosh 接管当前 Hammer task"
    )
    activate.add_argument("--project", type=Path, required=True)
    activate.add_argument("--work", required=True)
    activate.add_argument("--task", required=True)
    activate.add_argument("--tasks-file", type=Path, required=True)
    begin = sub.add_parser("begin-subtask", help="开始当前 Cosh 细分任务")
    begin.add_argument("--project", type=Path, required=True)
    begin.add_argument("--work", required=True)
    begin.add_argument("--task-id", required=True)
    complete = sub.add_parser("complete-subtask", help="完成当前 Cosh 细分任务")
    complete.add_argument("--project", type=Path, required=True)
    complete.add_argument("--work", required=True)
    complete.add_argument("--task-id", required=True)
    complete.add_argument("--status", choices=("passed", "blocked"), required=True)
    complete.add_argument("--evidence-file", type=Path, required=True)
    finish = sub.add_parser("complete-coding", help="交还当前 Hammer 父任务")
    finish.add_argument("--project", type=Path, required=True)
    finish.add_argument("--work", required=True)
    finish.add_argument("--task", required=True)
    finish.add_argument("--commit-sha", required=True)
    attach = sub.add_parser(
        "attach-existing-hammer", help="为已到 Plan 的 Hammer 任务迟到接入 Cosh"
    )
    attach.add_argument("--project", type=Path, required=True)
    attach.add_argument("--work", required=True)
    attach.add_argument("--requirement", required=True)
    attach.add_argument("--hammer-root", type=Path, required=True)
    attach.add_argument("--meego-id")
    attach.add_argument("--no-open", action="store_true")
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
                meego_id=args.meego_id,
            )
        elif args.command == "status":
            payload = build_status(args.project, args.work)
        elif args.command == "preflight":
            payload = run_preflight(args.project, args.work)
        elif args.command == "verify-handoff":
            payload = verify_handoff(args.project, args.work)
        elif args.command == "verify-coding":
            payload = verify_coding(args.project, args.work, args.task)
        elif args.command == "activate-coding":
            payload = activate_coding(
                args.project, args.work, args.task, _read_json(args.tasks_file)
            )
        elif args.command == "begin-subtask":
            payload = begin_subtask(args.project, args.work, args.task_id)
        elif args.command == "complete-subtask":
            payload = complete_subtask(
                args.project,
                args.work,
                args.task_id,
                status=args.status,
                evidence=_read_json(args.evidence_file),
            )
        elif args.command == "complete-coding":
            payload = complete_coding(
                args.project,
                args.work,
                args.task,
                commit_sha=args.commit_sha,
            )
        else:
            payload = attach_existing_hammer(
                args.project,
                work_id=args.work,
                refined_requirement=args.requirement,
                hammer_root=args.hammer_root,
                meego_id=args.meego_id,
            )
            command = [
                sys.executable,
                str(Path(__file__).resolve().parent / "start_cosh_hammer_dashboard.py"),
                "--project",
                str(args.project.resolve()),
                "--work",
                args.work,
                "--hammer-root",
                str(args.hammer_root.resolve()),
            ]
            if args.no_open:
                command.append("--no-open")
            try:
                started = subprocess.run(
                    command, check=True, capture_output=True, text=True
                )
            except subprocess.CalledProcessError as error:
                detail = (error.stderr or error.stdout or str(error)).strip()
                raise CoshHammerError(f"迟到接入观察板启动失败：{detail}") from error
            payload["dashboard"] = started.stdout.strip()
    except CoshHammerError as error:
        raise SystemExit(str(error)) from error
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
