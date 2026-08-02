#!/usr/bin/env python3
"""Project native Superpowers artifacts into a fail-closed ByteDance workflow."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import logging
import subprocess
from pathlib import Path
from typing import Any, Mapping


LOGGER = logging.getLogger("byted-superpowers-workflow")

STAGE_ORDER = (
    "source",
    "knowledge_gate",
    "codegraph",
    "review",
    "review_closure",
    "spec",
    "location",
    "plan",
    "implementation",
    "remote_ut",
    "final_review",
    "push",
    "archive",
)
REQUIRED_REVIEWERS = ("stability", "security", "feasibility")
VALID_STATUSES = {"pending", "running", "blocked", "passed"}


class DashboardError(RuntimeError):
    """Raised when workflow input cannot be resolved safely."""


class DashboardConflict(DashboardError):
    """Raised when a requested transition no longer matches current state."""


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise DashboardError(f"缺少状态文件：{path.name}") from error
    except json.JSONDecodeError as error:
        raise DashboardError(f"JSON 解析失败：{path.name}: {error.msg}") from error
    except OSError as error:
        raise DashboardError(f"读取状态文件失败：{path.name}: {error}") from error
    if not isinstance(payload, dict):
        raise DashboardError(f"JSON 顶层必须是对象：{path.name}")
    return payload


def _safe_child(root: Path, relative: str) -> Path:
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as error:
        raise DashboardError(f"路径越界：{relative}") from error
    return candidate


def resolve_work(project_root: Path, work_id: str | None) -> Path:
    works_root = project_root.resolve() / ".superpowers" / "byted-work"
    if not works_root.is_dir():
        raise DashboardError("未找到 .superpowers/byted-work")

    if work_id:
        if Path(work_id).name != work_id or work_id in {".", ".."}:
            raise DashboardError(f"非法开发任务标识：{work_id}")
        work_dir = _safe_child(works_root, work_id)
        if not work_dir.is_dir():
            raise DashboardError(f"开发任务不存在：{work_id}")
        return work_dir

    candidates = sorted(path for path in works_root.iterdir() if path.is_dir())
    if not candidates:
        raise DashboardError("没有可用的开发任务")
    if len(candidates) > 1:
        raise DashboardError("存在多个开发任务，请显式指定 work")
    return candidates[0]


def list_works(project_root: Path) -> list[dict[str, Any]]:
    works_root = project_root.resolve() / ".superpowers" / "byted-work"
    if not works_root.is_dir():
        return []
    result: list[dict[str, Any]] = []
    for path in sorted(item for item in works_root.iterdir() if item.is_dir()):
        source: dict[str, Any] = {}
        try:
            source = _read_json(path / "source.json")
        except DashboardError as error:
            LOGGER.warning("开发任务 %s 的来源状态不可读：%s", path.name, error)
        result.append(
            {
                "name": path.name,
                "source_version": source.get("version"),
                "updated_at": source.get("updated_at", ""),
            }
        )
    return result


def _stage(
    status: str = "pending",
    blockers: list[str] | None = None,
    *,
    fix: str = "",
    version: Any = None,
    updated_at: str = "",
    can_advance: bool = False,
) -> dict[str, Any]:
    normalized = status if status in VALID_STATUSES else "blocked"
    return {
        "status": normalized,
        "blockers": blockers or [],
        "fix": fix,
        "version": version,
        "updated_at": updated_at,
        "can_advance": can_advance,
    }


def _validate_source(work_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        source = _read_json(work_dir / "source.json")
        version = source.get("version")
        expected_hash = source.get("sha256")
        relative_path = source.get("path")
        if not isinstance(version, int) or version < 1:
            raise DashboardError("source.json 的 version 必须是正整数")
        if not isinstance(expected_hash, str) or len(expected_hash) != 64:
            raise DashboardError("source.json 缺少有效 SHA-256")
        if not isinstance(relative_path, str) or not relative_path:
            raise DashboardError("source.json 缺少技术文档 path")
        source_path = _safe_child(work_dir, relative_path)
        if not source_path.is_file():
            raise DashboardError(f"技术文档不存在：{relative_path}")
        actual_hash = _sha256_file(source_path)
        if actual_hash != expected_hash:
            raise DashboardError("技术文档 SHA-256 与 source.json 不一致")
        return source, _stage(
            "passed",
            version=version,
            updated_at=str(source.get("updated_at", "")),
            can_advance=True,
        )
    except DashboardError as error:
        return {}, _stage(
            "blocked",
            [str(error)],
            fix="修复技术文档来源、版本与 SHA-256 后重试",
        )


def _matches_source(evidence: Mapping[str, Any], source: Mapping[str, Any]) -> bool:
    return (
        evidence.get("source_version") == source.get("version")
        and evidence.get("source_sha256") == source.get("sha256")
    )


def _project_knowledge_gate(
    work_dir: Path, source: Mapping[str, Any], source_stage: Mapping[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    if source_stage["status"] != "passed":
        return {}, _stage("pending", ["技术文档尚未通过"])
    try:
        evidence = _read_json(work_dir / "evidence" / "knowledge-gate.json")
    except DashboardError as error:
        return {}, _stage(
            "blocked",
            [str(error)],
            fix="安装或更新 AI-Spec，并写入当前文档版本的知识证据",
        )
    blockers: list[str] = []
    if not _matches_source(evidence, source):
        blockers.append("知识证据与当前技术文档版本或 SHA-256 不一致")
    mode = evidence.get("mode")
    status = evidence.get("status")
    if mode != "loaded":
        blockers.append("AI-Spec 是唯一允许的知识门禁，必须使用 loaded 模式")
    if status != "passed":
        blockers.append("AI-Spec 尚未通过")
    if not evidence.get("version") or not evidence.get("sources"):
        blockers.append("AI-Spec 版本或来源证据不完整")
    stage_status = "blocked" if blockers else "passed"
    return evidence, _stage(
        stage_status,
        blockers,
        fix="重新执行知识门禁并记录完整证据" if blockers else "",
        version=evidence.get("version"),
        updated_at=str(evidence.get("updated_at", "")),
        can_advance=not blockers,
    )


def _project_codegraph(
    work_dir: Path,
    source: Mapping[str, Any],
    knowledge_stage: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        evidence = _read_json(work_dir / "evidence" / "codegraph.json")
    except DashboardError as error:
        if knowledge_stage["status"] != "passed":
            return {}, _stage("pending", ["知识门禁尚未通过"])
        return {}, _stage(
            "blocked",
            [str(error)],
            fix="使用 CodeGraph 与源码生成当前版本代码事实快照",
        )
    blockers: list[str] = []
    if knowledge_stage["status"] != "passed":
        blockers.append("知识门禁尚未通过，已有 CodeGraph 证据不可继续使用")
    if not _matches_source(evidence, source):
        blockers.append("CodeGraph 证据与当前技术文档版本或 SHA-256 不一致")
    if evidence.get("status") != "passed":
        blockers.append("CodeGraph 代码事实扫描未通过")
    if not evidence.get("code_sha"):
        blockers.append("CodeGraph 证据缺少代码 SHA")
    locations = evidence.get("locations")
    if not isinstance(locations, list) or not locations:
        blockers.append("CodeGraph 证据缺少精确代码位置")
    else:
        required = {"file", "symbol", "variable", "type"}
        if any(not isinstance(item, dict) or not required.issubset(item) for item in locations):
            blockers.append("CodeGraph 位置必须包含文件、符号、变量和类型")
    return evidence, _stage(
        "blocked" if blockers else "passed",
        blockers,
        fix="补齐当前代码 SHA 和变量级位置证据" if blockers else "",
        version=evidence.get("code_sha"),
        updated_at=str(evidence.get("updated_at", "")),
        can_advance=not blockers,
    )


def _read_reviews(work_dir: Path) -> tuple[list[dict[str, Any]], list[str]]:
    reviews: list[dict[str, Any]] = []
    errors: list[str] = []
    review_dir = work_dir / "reviews"
    if not review_dir.is_dir():
        return reviews, ["缺少 reviews 目录"]
    for path in sorted(review_dir.glob("round-*.json")):
        try:
            payload = _read_json(path)
            payload["artifact"] = str(path.relative_to(work_dir))
            reviews.append(payload)
        except DashboardError as error:
            errors.append(str(error))
    return reviews, errors


def _project_reviews(
    work_dir: Path,
    source: Mapping[str, Any],
    codegraph: Mapping[str, Any],
    codegraph_stage: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    reviews, errors = _read_reviews(work_dir)
    history = sorted(reviews, key=lambda item: (int(item.get("round", 0)), str(item.get("reviewer", ""))))
    result: dict[str, Any] = {"round": None, "reviewers": {}, "findings": [], "history": history}
    if codegraph_stage["status"] != "passed" and not reviews:
        return result, _stage("pending", ["CodeGraph 事实扫描尚未通过"])

    current = [item for item in reviews if _matches_source(item, source)]
    if not current:
        blockers = errors + ["当前技术文档版本尚无三路评审，历史结论已经失效"]
        return result, _stage("blocked", blockers, fix="启动三个独立 Reviewer")
    current_round = max(int(item.get("round", 0)) for item in current)
    result["round"] = current_round
    round_reviews = [item for item in current if int(item.get("round", 0)) == current_round]
    by_reviewer = {str(item.get("reviewer")): item for item in round_reviews}
    result["reviewers"] = by_reviewer
    blockers = list(errors)
    if codegraph_stage["status"] != "passed":
        blockers.append("CodeGraph 前置门禁尚未通过，已有评审证据不可继续使用")
    expected_code_sha = codegraph.get("code_sha")
    for reviewer in REQUIRED_REVIEWERS:
        review = by_reviewer.get(reviewer)
        if review is None:
            blockers.append(f"缺少 {reviewer} Reviewer")
            continue
        if review.get("code_sha") != expected_code_sha:
            blockers.append(f"{reviewer} Reviewer 的代码 SHA 已过期")
        if review.get("status") != "passed":
            blockers.append(f"{reviewer} Reviewer 未通过")
        findings = review.get("findings", [])
        if isinstance(findings, list):
            result["findings"].extend(
                {**finding, "reviewer": reviewer, "round": current_round}
                for finding in findings
                if isinstance(finding, dict)
            )
    updated_at = max((str(item.get("updated_at", "")) for item in round_reviews), default="")
    return result, _stage(
        "blocked" if blockers else "passed",
        blockers,
        fix="按风险点修改技术文档或实现证据后重新执行三路完整评审" if blockers else "",
        version=current_round,
        updated_at=updated_at,
        can_advance=not blockers,
    )


def _project_review_closure(
    work_dir: Path,
    source: Mapping[str, Any],
    review: Mapping[str, Any],
    review_stage: Mapping[str, Any],
) -> dict[str, Any]:
    if review_stage["status"] != "passed":
        return _stage("pending", ["三路评审尚未全部通过"])
    try:
        evidence = _read_json(work_dir / "evidence" / "review-closure.json")
    except DashboardError:
        return _stage("pending", [], fix="确认采用当前评审后的技术方案", can_advance=True)
    blockers: list[str] = []
    if not _matches_source(evidence, source):
        blockers.append("评审闭环确认与当前技术文档不一致")
    if evidence.get("review_round") != review.get("round"):
        blockers.append("评审闭环确认与当前评审轮次不一致")
    if evidence.get("status") != "passed":
        blockers.append("评审闭环尚未确认")
    return _stage(
        "blocked" if blockers else "passed",
        blockers,
        fix="重新确认当前技术文档与评审轮次" if blockers else "",
        version=evidence.get("review_round"),
        updated_at=str(evidence.get("updated_at", "")),
        can_advance=not blockers,
    )


def _state_version(work_dir: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in work_dir.rglob("*") if item.is_file()):
        digest.update(str(path.relative_to(work_dir)).encode("utf-8"))
        try:
            digest.update(path.read_bytes())
        except OSError:
            continue
    return digest.hexdigest()[:16]


def _project_tasks(project_root: Path, work_id: str) -> dict[str, Any]:
    module_path = Path(__file__).with_name("task_control.py")
    spec = importlib.util.spec_from_file_location("byted_task_projection", module_path)
    if spec is None or spec.loader is None:
        return {"tasks": [], "tasks_total": 0, "tasks_done": 0, "current_task": None}
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    try:
        return module.project_task_status(project_root, work_id)
    except module.TaskControlError as error:
        LOGGER.info("开发任务 %s 尚无可投影计划：%s", work_id, error)
        return {
            "tasks": [],
            "tasks_total": 0,
            "tasks_done": 0,
            "current_task": None,
            "task_error": str(error),
        }


def _current_head(project_root: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=project_root,
        text=True,
        capture_output=True,
        check=False,
        timeout=15,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def _validate_project_artifact(
    project_root: Path, evidence: Mapping[str, Any]
) -> tuple[Path | None, list[str]]:
    blockers: list[str] = []
    relative = evidence.get("path")
    if not isinstance(relative, str) or not relative:
        return None, ["产物证据缺少 path"]
    root = project_root.resolve()
    path = (root / relative).resolve()
    try:
        path.relative_to(root)
    except ValueError:
        return None, ["产物路径越界"]
    if not path.is_file():
        blockers.append(f"产物不存在：{relative}")
        return path, blockers
    expected = evidence.get("sha256")
    if not isinstance(expected, str) or _sha256_file(path) != expected:
        blockers.append(f"产物 SHA-256 已失效：{relative}")
    return path, blockers


def _project_spec(
    project_root: Path,
    work_dir: Path,
    source: Mapping[str, Any],
    knowledge: Mapping[str, Any],
    closure_stage: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        evidence = _read_json(work_dir / "evidence" / "spec.json")
    except DashboardError as error:
        if closure_stage["status"] != "passed":
            return {}, _stage("pending", ["评审闭环尚未通过"])
        return {}, _stage("blocked", [str(error)], fix="生成并确认 Superpowers 规格")
    blockers: list[str] = []
    if closure_stage["status"] != "passed":
        blockers.append("评审闭环尚未通过，已有规格证据不可使用")
    if knowledge.get("mode") != "loaded":
        blockers.append("AI-Spec 知识证据未完整加载")
    if not _matches_source(evidence, source):
        blockers.append("规格证据与当前技术文档不一致")
    if evidence.get("status") != "passed":
        blockers.append("Superpowers 规格尚未通过书面确认")
    _, artifact_blockers = _validate_project_artifact(project_root, evidence)
    blockers.extend(artifact_blockers)
    return evidence, _stage(
        "blocked" if blockers else "passed",
        blockers,
        fix="重新生成并确认当前版本 Superpowers 规格" if blockers else "",
        version=evidence.get("sha256"),
        updated_at=str(evidence.get("updated_at", "")),
        can_advance=not blockers,
    )


def _project_location(
    work_dir: Path,
    source: Mapping[str, Any],
    spec: Mapping[str, Any],
    spec_stage: Mapping[str, Any],
    codegraph: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        evidence = _read_json(work_dir / "evidence" / "location.json")
    except DashboardError as error:
        if spec_stage["status"] != "passed":
            return {}, _stage("pending", ["Superpowers 规格尚未通过"])
        return {}, _stage("blocked", [str(error)], fix="补齐变量级精确实施位置")
    blockers: list[str] = []
    if spec_stage["status"] != "passed":
        blockers.append("Superpowers 规格尚未通过，已有定位证据不可使用")
    if not _matches_source(evidence, source):
        blockers.append("精确定位与当前技术文档不一致")
    if evidence.get("status") != "passed":
        blockers.append("精确实施定位尚未通过")
    if evidence.get("spec_sha256") != spec.get("sha256"):
        blockers.append("精确定位与当前规格 SHA-256 不一致")
    if evidence.get("code_sha") != codegraph.get("code_sha"):
        blockers.append("精确定位与 CodeGraph 代码 SHA 不一致")
    locations = evidence.get("locations")
    required = {"file", "symbol", "variable", "type"}
    if not isinstance(locations, list) or not locations or any(
        not isinstance(item, dict) or not required.issubset(item) for item in locations
    ):
        blockers.append("精确定位必须包含文件、符号、变量和类型")
    return evidence, _stage(
        "blocked" if blockers else "passed",
        blockers,
        fix="重新执行规格与源码的变量级定位校验" if blockers else "",
        version=evidence.get("code_sha"),
        updated_at=str(evidence.get("updated_at", "")),
        can_advance=not blockers,
    )


def _project_plan(
    project_root: Path,
    work_dir: Path,
    source: Mapping[str, Any],
    location: Mapping[str, Any],
    location_stage: Mapping[str, Any],
    task_projection: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        evidence = _read_json(work_dir / "evidence" / "plan.json")
    except DashboardError as error:
        if location_stage["status"] != "passed":
            return {}, _stage("pending", ["精确实施定位尚未通过"])
        return {}, _stage("blocked", [str(error)], fix="生成并确认 Superpowers 实施计划")
    blockers: list[str] = []
    if location_stage["status"] != "passed":
        blockers.append("精确实施定位尚未通过，已有计划证据不可使用")
    if not _matches_source(evidence, source):
        blockers.append("计划证据与当前技术文档不一致")
    if evidence.get("status") != "passed":
        blockers.append("Superpowers 实施计划尚未确认")
    if evidence.get("code_sha") != location.get("code_sha"):
        blockers.append("计划与精确定位代码 SHA 不一致")
    _, artifact_blockers = _validate_project_artifact(project_root, evidence)
    blockers.extend(artifact_blockers)
    if not task_projection.get("tasks_total"):
        blockers.append("计划没有可执行实施子任务")
    return evidence, _stage(
        "blocked" if blockers else "passed",
        blockers,
        fix="重新生成无占位、可验证的 Superpowers 计划" if blockers else "",
        version=evidence.get("sha256"),
        updated_at=str(evidence.get("updated_at", "")),
        can_advance=not blockers,
    )


def _project_final_delivery(
    project_root: Path,
    work_dir: Path,
    implementation_stage: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    head = _current_head(project_root)
    remote: dict[str, Any] = {}
    remote_blockers: list[str] = []
    try:
        remote = _read_json(work_dir / "evidence" / "remote-ut-final.json")
    except DashboardError as error:
        remote_blockers.append(str(error))
    if implementation_stage["status"] != "passed":
        remote_blockers.append("实施子任务尚未全部通过")
    if remote:
        if remote.get("status") != "passed":
            remote_blockers.append("完整远程 UT 尚未通过")
        if not head or remote.get("code_sha") != head:
            remote_blockers.append("完整远程 UT 的代码 SHA 与当前 HEAD 不一致")
        if remote.get("prepare_only") is True:
            remote_blockers.append("PREPARE_ONLY 不能作为远程 UT 通过证据")
        meta = remote.get("meta", {})
        summary = remote.get("summary", {})
        if not isinstance(meta, dict) or not isinstance(meta.get("remote"), dict) or meta["remote"].get("run_success") is not True:
            remote_blockers.append("远程 UT 缺少 meta.remote.run_success=true")
        if not isinstance(summary, dict) or summary.get("has_failures") is not False:
            remote_blockers.append("远程 UT summary.has_failures 不是 false")
        if summary.get("failed_packages") != 0 or summary.get("failed_tests") != 0:
            remote_blockers.append("远程 UT 仍有失败 package 或测试")
    remote_stage = _stage(
        "blocked" if remote_blockers else "passed",
        remote_blockers,
        fix="对当前 HEAD 重新运行完整 BITS 远程 UT" if remote_blockers else "",
        version=remote.get("code_sha"),
        updated_at=str(remote.get("updated_at", "")),
        can_advance=not remote_blockers,
    )

    final_review: dict[str, Any] = {}
    review_blockers: list[str] = []
    try:
        final_review = _read_json(work_dir / "evidence" / "final-review.json")
    except DashboardError as error:
        review_blockers.append(str(error))
    if remote_stage["status"] != "passed":
        review_blockers.append("完整远程 UT 尚未通过")
    if final_review:
        if final_review.get("status") != "passed":
            review_blockers.append("最终 CR 尚未通过")
        if not head or final_review.get("code_sha") != head:
            review_blockers.append("最终 CR 的代码 SHA 与当前 HEAD 不一致")
        if final_review.get("blocking_findings"):
            review_blockers.append("最终 CR 仍有阻塞问题")
    final_review_stage = _stage(
        "blocked" if review_blockers else "passed",
        review_blockers,
        fix="修复问题后对当前 HEAD 重新执行最终 CR" if review_blockers else "",
        version=final_review.get("code_sha"),
        updated_at=str(final_review.get("updated_at", "")),
        can_advance=not review_blockers,
    )

    push: dict[str, Any] = {}
    try:
        push = _read_json(work_dir / "evidence" / "push.json")
    except DashboardError:
        pass
    push_blockers: list[str] = []
    if final_review_stage["status"] != "passed":
        push_blockers.append("最终 CR 尚未通过")
    if push and (push.get("status") != "passed" or push.get("code_sha") != head):
        push_blockers.append("Push 证据与当前 HEAD 不一致")
    push_passed = bool(push) and not push_blockers
    push_stage = _stage(
        "passed" if push_passed else ("blocked" if push_blockers else "pending"),
        push_blockers,
        fix="完成当前 HEAD 的最终门禁后执行普通 push" if push_blockers else "执行普通 push",
        version=push.get("code_sha"),
        updated_at=str(push.get("updated_at", "")),
        can_advance=not push_blockers and not push_passed,
    )
    return remote_stage, final_review_stage, push_stage


def build_status(project_root: Path, work_id: str | None = None) -> dict[str, Any]:
    work_dir = resolve_work(project_root, work_id)
    workflow: dict[str, Any] = {}
    try:
        workflow = _read_json(work_dir / "workflow.json")
    except DashboardError as error:
        LOGGER.warning("开发任务 %s 的 workflow.json 不可读：%s", work_dir.name, error)

    source, source_stage = _validate_source(work_dir)
    knowledge, knowledge_stage = _project_knowledge_gate(work_dir, source, source_stage)
    codegraph, codegraph_stage = _project_codegraph(work_dir, source, knowledge_stage)
    reviews, review_stage = _project_reviews(
        work_dir, source, codegraph, codegraph_stage
    )
    closure_stage = _project_review_closure(
        work_dir, source, reviews, review_stage
    )
    stages = {name: _stage() for name in STAGE_ORDER}
    stages.update(
        {
            "source": source_stage,
            "knowledge_gate": knowledge_stage,
            "codegraph": codegraph_stage,
            "review": review_stage,
            "review_closure": closure_stage,
        }
    )

    task_projection = _project_tasks(project_root, work_dir.name)
    spec_evidence, spec_stage = _project_spec(
        project_root, work_dir, source, knowledge, closure_stage
    )
    location_evidence, location_stage = _project_location(
        work_dir, source, spec_evidence, spec_stage, codegraph
    )
    plan_evidence, plan_stage = _project_plan(
        project_root,
        work_dir,
        source,
        location_evidence,
        location_stage,
        task_projection,
    )
    stages["spec"] = spec_stage
    stages["location"] = location_stage
    stages["plan"] = plan_stage
    implementation_blockers: list[str] = []
    if plan_stage["status"] != "passed":
        implementation_blockers.append("Superpowers 计划门禁尚未通过")
    if not task_projection["tasks_total"]:
        implementation_status = "pending"
    elif implementation_blockers:
        implementation_status = "blocked"
    elif task_projection["tasks_done"] == task_projection["tasks_total"]:
        implementation_status = "passed"
    else:
        implementation_status = "running"
    local_task_ready = bool(
        task_projection.get("current_task", {}).get("can_advance")
        if task_projection.get("current_task")
        else False
    )
    stages["implementation"] = _stage(
        implementation_status,
        implementation_blockers,
        fix="先闭合规格、定位与计划门禁" if implementation_blockers else "",
        version=f"{task_projection['tasks_done']}/{task_projection['tasks_total']}",
        can_advance=not implementation_blockers and local_task_ready,
    )
    if task_projection.get("current_task") and implementation_blockers:
        task_projection["current_task"]["can_advance"] = False
        task_projection["current_task"]["global_blockers"] = implementation_blockers
    remote_stage, final_review_stage, push_stage = _project_final_delivery(
        project_root, work_dir, stages["implementation"]
    )
    stages["remote_ut"] = remote_stage
    stages["final_review"] = final_review_stage
    stages["push"] = push_stage
    archive: dict[str, Any] = {}
    try:
        archive = _read_json(work_dir / "evidence" / "archive.json")
    except DashboardError:
        pass
    archive_path = archive.get("path")
    archive_exists = bool(
        isinstance(archive_path, str)
        and archive_path
        and (project_root.resolve() / archive_path).is_file()
    )
    if archive.get("status") == "passed" and archive_exists:
        stages["archive"] = _stage(
            "passed",
            version=archive.get("push_sha") or archive_path,
            updated_at=str(archive.get("updated_at", "")),
        )

    return {
        "work": work_dir.name,
        "source": source,
        "mode": workflow.get("mode", "single"),
        "version": _state_version(work_dir),
        "stages": stages,
        "knowledge_gate": {
            "mode": knowledge.get("mode", "missing"),
            "version": knowledge.get("version"),
        },
        "codegraph": codegraph,
        "reviews": reviews,
        "spec_evidence": spec_evidence,
        "location_evidence": location_evidence,
        "plan_evidence": plan_evidence,
        "archive": archive,
        **task_projection,
    }


def validate_transition(status: Mapping[str, Any], target_stage: str) -> None:
    if target_stage not in STAGE_ORDER:
        raise DashboardConflict(f"未知目标阶段：{target_stage}")
    target_index = STAGE_ORDER.index(target_stage)
    stages = status.get("stages", {})
    for predecessor in STAGE_ORDER[:target_index]:
        predecessor_status = stages.get(predecessor, {}).get("status")
        if predecessor_status != "passed":
            raise DashboardConflict(
                f"前置阶段 {predecessor} 未通过，不能进入 {target_stage}"
            )
