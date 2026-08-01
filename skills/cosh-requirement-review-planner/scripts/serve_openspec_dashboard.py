#!/usr/bin/env python3
"""Serve live projections of the OpenSpec changes in one project."""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
import subprocess
import tempfile
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse


SKILL_ROOT = Path(__file__).resolve().parents[1]
ASSET_ROOT = SKILL_ROOT / "assets" / "dashboard"
TASK_RE = re.compile(r"^\s*[-*]\s+\[([ xX])\]\s+(.+?)\s*$", re.MULTILINE)
POINT_START_RE = re.compile(r"^\s*修改点 ID[：:]\s*(\S.+?)\s*$", re.MULTILINE)
POINT_FIELD_RE = re.compile(
    r"^\s*(对应 scenario|文件|符号|变量|类型|目标变化|未决假设)[：:]\s*(.*?)\s*$",
    re.MULTILINE,
)
CONTROL_RE = re.compile(r"<!--\s*cosh-dashboard-control\s+(\{.*?\})\s*-->", re.DOTALL)
TEXT_SUFFIXES = {".md", ".markdown", ".yaml", ".yml", ".json", ".txt"}
GATE_NAMES = (
    "规格确认",
    "修改点确认",
    "技术方案确认",
    "任务清单确认",
    "任务 CR 与提交确认",
    "测试结果确认",
    "最终归档确认",
)


class DashboardError(RuntimeError):
    """Raised when a live dashboard cannot identify or read its OpenSpec change."""


class DashboardConflict(DashboardError):
    """Raised when an artifact changed after the page rendered it."""


def iso_time(timestamp: float | None = None) -> str:
    value = datetime.fromtimestamp(timestamp) if timestamp is not None else datetime.now()
    return value.astimezone().isoformat(timespec="seconds")


def resolve_change(project_root: Path, change: str | None) -> Path:
    changes_root = project_root.resolve() / "openspec" / "changes"
    if not changes_root.is_dir():
        raise DashboardError(f"OpenSpec changes 目录不存在：{changes_root}")
    if change:
        candidate = (changes_root / change).resolve()
        if candidate.parent != changes_root.resolve() or not candidate.is_dir():
            raise DashboardError(f"找不到 OpenSpec change：{change}")
        return candidate

    candidates = sorted(
        path
        for path in changes_root.iterdir()
        if path.is_dir() and not path.name.startswith(".") and path.name not in {"archive", "archived"}
    )
    if len(candidates) != 1:
        names = "、".join(path.name for path in candidates) or "无"
        raise DashboardError(f"无法唯一确定活动 change（候选：{names}），请传入 --change")
    return candidates[0]


def list_changes(project_root: Path) -> list[dict[str, Any]]:
    changes_root = project_root.resolve() / "openspec" / "changes"
    if not changes_root.is_dir():
        raise DashboardError(f"OpenSpec changes 目录不存在：{changes_root}")
    candidates = sorted(
        path
        for path in changes_root.iterdir()
        if path.is_dir() and not path.name.startswith(".") and path.name not in {"archive", "archived"}
    )
    if not candidates:
        raise DashboardError(f"没有可用的活动 change：{changes_root}")
    changes: list[dict[str, Any]] = []
    for path in candidates:
        try:
            status = build_status(project_root, path.name)
            changes.append(
                {
                    "name": path.name,
                    "stage": status["stage"],
                    "tasks_done": status["tasks"]["done"],
                    "tasks_total": status["tasks"]["total"],
                    "updated_at": status["source_updated_at"],
                }
            )
        except DashboardError as exc:
            changes.append({"name": path.name, "error": str(exc)})
    return changes


def read_artifacts(change_dir: Path) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    for path in sorted(change_dir.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise DashboardError(f"无法读取 artifact {path}: {exc}") from exc
        stat = path.stat()
        artifacts.append(
            {
                "path": path.relative_to(change_dir).as_posix(),
                "text": text,
                "mtime": stat.st_mtime,
                "version": f"{stat.st_mtime_ns}-{stat.st_size}",
                "updated_at": iso_time(stat.st_mtime),
            }
        )
    if not artifacts:
        raise DashboardError(f"change 中没有可读取的文本 artifact：{change_dir}")
    return artifacts


def contains_role(artifacts: list[dict[str, Any]], *tokens: str) -> bool:
    return any(any(token in item["path"].lower() for token in tokens) for item in artifacts)


def parse_tasks(artifacts: list[dict[str, Any]]) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    source_path = ""
    version = ""
    control = {"mode": "single", "sequence": 0}
    for artifact in artifacts:
        if "task" not in artifact["path"].lower():
            continue
        if not source_path:
            source_path = artifact["path"]
            version = artifact["version"]
            control = parse_execution_control(artifact["text"])
        for match in TASK_RE.finditer(artifact["text"]):
            items.append({"done": match.group(1).lower() == "x", "text": match.group(2)})
    return {
        "total": len(items),
        "done": sum(item["done"] for item in items),
        "items": items,
        "source_path": source_path,
        "version": version,
        "execution_control": control,
    }


def parse_execution_control(text: str) -> dict[str, Any]:
    match = CONTROL_RE.search(text)
    if not match:
        return {"mode": "single", "sequence": 0}
    try:
        value = json.loads(match.group(1))
    except json.JSONDecodeError:
        return {"mode": "single", "sequence": 0, "error": "控制元数据无法解析"}
    if value.get("mode") not in {"single", "continuous"}:
        value["mode"] = "single"
    value["sequence"] = int(value.get("sequence", 0))
    return value


def file_version(path: Path) -> str:
    stat = path.stat()
    return f"{stat.st_mtime_ns}-{stat.st_size}"


def validate_task_context(
    project_root: Path, change: str | None, expected_version: str, expected_task: str
) -> dict[str, Any]:
    status = build_status(project_root, change)
    tasks = status["tasks"]
    if not tasks["source_path"]:
        raise DashboardError("当前 change 没有可写入控制元数据的 tasks artifact")
    if not expected_version or tasks["version"] != expected_version:
        raise DashboardConflict("tasks artifact 已变化，请等待页面刷新后重试")
    pending_items = [item for item in tasks["items"] if not item["done"]]
    if not pending_items:
        raise DashboardError("没有待推进的 task")
    if not expected_task or expected_task != pending_items[0]["text"]:
        raise DashboardConflict("当前 task 已变化，请等待页面刷新后重试")
    return status


def run_git(project_root: Path, arguments: list[str], timeout: int = 15) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", *arguments],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise DashboardError(f"Git 命令执行失败：{exc}") from exc


def commit_staged_changes(
    project_root: Path,
    change: str | None,
    expected_version: str,
    expected_task: str,
) -> dict[str, Any]:
    status = validate_task_context(project_root, change, expected_version, expected_task)
    if status["tasks"]["execution_control"].get("mode", "single") != "single":
        raise DashboardError("连续推进模式不使用“推进下一个任务”")
    repository = run_git(project_root, ["rev-parse", "--show-toplevel"], timeout=10)
    if repository.returncode != 0:
        raise DashboardError("目标项目不是可提交的 Git 工作区")

    staged = run_git(project_root, ["diff", "--cached", "--quiet", "--exit-code"])
    if staged.returncode == 0:
        return {"created": False, "files": []}
    if staged.returncode != 1:
        raise DashboardError("无法读取 Git 暂存区")

    names = run_git(project_root, ["diff", "--cached", "--name-only", "--diff-filter=ACMRD"])
    if names.returncode != 0:
        raise DashboardError("无法读取暂存文件列表")
    files = [line for line in names.stdout.splitlines() if line]
    task_summary = re.sub(r"\s+", " ", expected_task).strip()[:120]
    message = f"openspec({change}): {task_summary}"
    committed = run_git(project_root, ["commit", "-m", message], timeout=120)
    if committed.returncode != 0:
        detail = (committed.stderr or committed.stdout).strip()[-500:]
        raise DashboardError(f"提交暂存区失败；未记录任务放行：{detail}")
    revision = run_git(project_root, ["rev-parse", "--short", "HEAD"], timeout=10)
    return {
        "created": True,
        "commit": revision.stdout.strip() if revision.returncode == 0 else "",
        "files": files,
    }


def update_execution_control(
    project_root: Path,
    change: str | None,
    action: str,
    expected_version: str,
    mode: str | None = None,
    expected_task: str = "",
) -> dict[str, Any]:
    status = validate_task_context(project_root, change, expected_version, expected_task)
    tasks = status["tasks"]
    tasks_path = resolve_change(project_root, change) / tasks["source_path"]
    text = tasks_path.read_text(encoding="utf-8")
    if file_version(tasks_path) != expected_version:
        raise DashboardConflict("tasks artifact 已变化，请等待页面刷新后重试")
    pending_items = [item for item in tasks["items"] if not item["done"]]
    control = dict(tasks["execution_control"])
    now = iso_time()
    if action == "set-mode":
        if mode not in {"single", "continuous"}:
            raise DashboardError("推进模式必须是 single 或 continuous")
        control = {
            "mode": mode,
            "sequence": int(control.get("sequence", 0)) + 1,
            "mode_updated_at": now,
        }
    elif action == "advance-next":
        if control.get("mode", "single") != "single":
            raise DashboardError("连续推进模式不使用“推进下一个任务”")
        pending = [item["text"] for item in pending_items]
        control.update(
            {
                "mode": "single",
                "sequence": int(control.get("sequence", 0)) + 1,
                "approved_task": pending[0],
                "advance_to_task": pending[1] if len(pending) > 1 else "最终验证",
                "advance_requested_at": now,
            }
        )
    else:
        raise DashboardError(f"不支持的控制动作：{action}")

    marker = "<!-- cosh-dashboard-control " + json.dumps(
        control, ensure_ascii=False, separators=(",", ":")
    ) + " -->"
    updated = CONTROL_RE.sub(marker, text, count=1) if CONTROL_RE.search(text) else marker + "\n\n" + text
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=tasks_path.parent, prefix=".dashboard-control-", delete=False
    ) as handle:
        handle.write(updated)
        temporary_path = Path(handle.name)
    try:
        if file_version(tasks_path) != expected_version:
            raise DashboardConflict("tasks artifact 已变化，请等待页面刷新后重试")
        os.replace(temporary_path, tasks_path)
    finally:
        temporary_path.unlink(missing_ok=True)
    return build_status(project_root, change)


def parse_modification_points(artifacts: list[dict[str, Any]]) -> list[dict[str, str]]:
    points: list[dict[str, str]] = []
    for artifact in artifacts:
        text = artifact["text"]
        starts = list(POINT_START_RE.finditer(text))
        for index, start in enumerate(starts):
            end = starts[index + 1].start() if index + 1 < len(starts) else len(text)
            block = text[start.end() : end]
            fields = {match.group(1): match.group(2) for match in POINT_FIELD_RE.finditer(block)}
            points.append(
                {
                    "id": start.group(1),
                    "scenario": fields.get("对应 scenario", ""),
                    "file": fields.get("文件", "未填写"),
                    "symbol": fields.get("符号", "未填写"),
                    "variable": fields.get("变量", "未填写"),
                    "type": fields.get("类型", ""),
                    "target": fields.get("目标变化", "未填写"),
                    "open_questions": fields.get("未决假设", "未填写"),
                    "artifact": artifact["path"],
                }
            )
    return points


def document_category(path: str) -> tuple[str, str]:
    lowered = path.lower()
    if any(token in lowered for token in ("proposal", "requirement", "spec")):
        return "spec", "规格"
    if "design" in lowered:
        return "design", "Design"
    if "task" in lowered:
        return "tasks", "Tasks"
    if any(token in lowered for token in ("validation", "verify", "test-result", "evidence")):
        return "validation", "验证"
    return "analysis", "代码证据"


def build_documents(
    artifacts: list[dict[str, Any]], points: list[dict[str, str]]
) -> list[dict[str, Any]]:
    documents: list[dict[str, Any]] = []
    all_point_ids = [point["id"] for point in points]
    for artifact in artifacts:
        category, category_label = document_category(artifact["path"])
        point_ids = [
            point["id"]
            for point in points
            if point["id"] in artifact["text"]
            or (point["scenario"] and point["scenario"] in artifact["text"])
        ]
        if category == "spec" and not point_ids:
            point_ids = all_point_ids.copy()
        documents.append(
            {
                "path": artifact["path"],
                "category": category,
                "category_label": category_label,
                "point_ids": point_ids,
                "updated_at": artifact["updated_at"],
                "version": artifact["version"],
            }
        )
    return documents


def read_document(project_root: Path, change: str | None, relative_path: str) -> dict[str, str]:
    change_dir = resolve_change(project_root, change)
    candidate = (change_dir / relative_path).resolve()
    try:
        candidate.relative_to(change_dir.resolve())
    except ValueError as exc:
        raise DashboardError("artifact 路径越界") from exc
    if not candidate.is_file() or candidate.suffix.lower() not in TEXT_SUFFIXES:
        raise DashboardError(f"找不到可读取的 artifact：{relative_path}")
    try:
        content = candidate.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise DashboardError(f"无法读取 artifact {relative_path}: {exc}") from exc
    return {"path": candidate.relative_to(change_dir).as_posix(), "content": content}


def progress_state(
    artifacts: list[dict[str, Any]], tasks: dict[str, Any], points: list[dict[str, str]]
) -> tuple[str, str, list[dict[str, str]]]:
    has_spec = contains_role(artifacts, "proposal", "requirement", "spec")
    has_design = contains_role(artifacts, "design")
    has_tasks = contains_role(artifacts, "task")
    has_validation = contains_role(artifacts, "validation", "verify", "test-result", "evidence")
    tasks_done = tasks["total"] > 0 and tasks["done"] == tasks["total"]

    readiness = [
        has_spec,
        bool(points),
        has_design,
        has_tasks,
        tasks_done,
        has_validation,
        False,
    ]
    labels: list[dict[str, str]] = []
    first_pending = next((i for i, ready in enumerate(readiness) if not ready), len(readiness) - 1)
    for index, (name, ready) in enumerate(zip(GATE_NAMES, readiness)):
        if index < first_pending:
            state, label = "done", "流程已越过"
        elif ready:
            state, label = "ready", "已产出 · 待确认"
        elif index == first_pending:
            state, label = "ready", "当前待处理"
        else:
            state, label = "pending", "尚未到达"
        labels.append({"name": name, "state": state, "label": label})

    if not has_spec:
        return "规格准备", "完成规格并请求规格确认", labels
    if not points:
        return "CodeGraph 分析", "确认变量级修改点", labels
    if not has_design:
        return "修改点确认", "基于确认后的修改点创建 design", labels
    if not has_tasks:
        return "Design 评审", "确认 design 并生成 tasks", labels
    if not tasks_done:
        return "任务实现", "完成当前 task 的验证与 CR", labels
    if not has_validation:
        return "整体验证", "补齐验证证据并确认测试结果", labels
    return "归档准备", "确认最终归档", labels


def build_status(project_root: Path, change: str | None = None) -> dict[str, Any]:
    change_dir = resolve_change(project_root, change)
    artifacts = read_artifacts(change_dir)
    tasks = parse_tasks(artifacts)
    points = parse_modification_points(artifacts)
    documents = build_documents(artifacts, points)
    stage, next_gate, gates = progress_state(artifacts, tasks, points)
    source_mtime = max(item["mtime"] for item in artifacts)
    return {
        "change": change_dir.name,
        "source": str(change_dir),
        "read_at": iso_time(),
        "source_updated_at": iso_time(source_mtime),
        "stage": stage,
        "next_gate": next_gate,
        "gates": gates,
        "modification_points": points,
        "documents": documents,
        "tasks": tasks,
        "artifacts": [
            {
                "path": item["path"],
                "updated_at": item["updated_at"],
                "version": item["version"],
            }
            for item in artifacts
        ],
    }


def event_payload(project_root: Path, change: str | None) -> tuple[str, dict[str, Any]]:
    try:
        payload = build_status(project_root, change)
        comparable = {key: value for key, value in payload.items() if key != "read_at"}
        signature = "status:" + json.dumps(comparable, ensure_ascii=False, sort_keys=True)
        return signature, {"event": "status", "data": payload}
    except DashboardError as exc:
        payload = {"error": str(exc), "read_at": iso_time()}
        return "error:" + str(exc), {"event": "read-error", "data": payload}


def make_handler(project_root: Path, default_change: str | None) -> type[BaseHTTPRequestHandler]:
    class DashboardHandler(BaseHTTPRequestHandler):
        def _selected_change(self, parsed: Any) -> str | None:
            values = parse_qs(parsed.query).get("change", [])
            if len(values) > 1:
                raise DashboardError("只能选择一个 change")
            return values[0] if values else default_change

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path == "/api/changes":
                try:
                    changes = list_changes(project_root)
                    selected = default_change or changes[0]["name"]
                    self._send_json(200, {"changes": changes, "default_change": selected})
                except DashboardError as exc:
                    self._send_json(422, {"error": str(exc), "read_at": iso_time()})
                return
            if parsed.path == "/api/status":
                try:
                    payload = build_status(project_root, self._selected_change(parsed))
                    self._send_json(200, payload)
                except DashboardError as exc:
                    self._send_json(422, {"error": str(exc), "read_at": iso_time()})
                return
            if parsed.path == "/api/document":
                paths = parse_qs(parsed.query).get("path", [])
                if len(paths) != 1:
                    self._send_json(400, {"error": "必须提供唯一的 artifact path"})
                    return
                try:
                    self._send_json(
                        200, read_document(project_root, self._selected_change(parsed), paths[0])
                    )
                except DashboardError as exc:
                    self._send_json(422, {"error": str(exc), "read_at": iso_time()})
                return
            if parsed.path == "/events":
                try:
                    selected_change = self._selected_change(parsed)
                    resolve_change(project_root, selected_change)
                    self._send_events(selected_change)
                except DashboardError as exc:
                    self._send_json(422, {"error": str(exc), "read_at": iso_time()})
                return

            asset_name = {"/": "index.html", "/styles.css": "styles.css", "/app.js": "app.js"}.get(
                parsed.path
            )
            if not asset_name:
                self.send_error(404)
                return
            asset = ASSET_ROOT / asset_name
            try:
                content = asset.read_bytes()
            except OSError:
                self.send_error(500)
                return
            mime = mimetypes.guess_type(asset.name)[0] or "application/octet-stream"
            self.send_response(200)
            self.send_header("Content-Type", f"{mime}; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        def do_POST(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path != "/api/control":
                self.send_error(404)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > 4096:
                    raise DashboardError("控制请求体大小无效")
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                staged_commit = None
                if payload.get("action") == "advance-next":
                    staged_commit = commit_staged_changes(
                        project_root,
                        payload.get("change") or default_change,
                        expected_version=payload.get("expected_version", ""),
                        expected_task=payload.get("expected_task", ""),
                    )
                result = update_execution_control(
                    project_root,
                    payload.get("change") or default_change,
                    action=payload.get("action", ""),
                    expected_version=payload.get("expected_version", ""),
                    mode=payload.get("mode"),
                    expected_task=payload.get("expected_task", ""),
                )
                if staged_commit is not None:
                    result["staged_commit"] = staged_commit
                self._send_json(200, result)
            except DashboardConflict as exc:
                self._send_json(409, {"error": str(exc), "read_at": iso_time()})
            except (DashboardError, json.JSONDecodeError, UnicodeError) as exc:
                self._send_json(422, {"error": str(exc), "read_at": iso_time()})

        def _send_json(self, status: int, payload: dict[str, Any]) -> None:
            content = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        def _send_events(self, selected_change: str | None) -> None:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "keep-alive")
            self.end_headers()
            try:
                self.wfile.write(b"retry: 1000\n\n")
                self.wfile.flush()
                previous_signature: str | None = None
                heartbeat_at = time.monotonic()
                while True:
                    signature, message = event_payload(project_root, selected_change)
                    if signature != previous_signature:
                        body = json.dumps(message["data"], ensure_ascii=False)
                        frame = f"event: {message['event']}\ndata: {body}\n\n".encode("utf-8")
                        self.wfile.write(frame)
                        self.wfile.flush()
                        previous_signature = signature
                    if time.monotonic() - heartbeat_at >= 15:
                        self.wfile.write(b": heartbeat\n\n")
                        self.wfile.flush()
                        heartbeat_at = time.monotonic()
                    time.sleep(0.5)
            except (BrokenPipeError, ConnectionResetError):
                return

        def log_message(self, format: str, *args: Any) -> None:
            return

    return DashboardHandler


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--change")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=4173)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    changes = list_changes(args.project_root)
    if args.change:
        resolve_change(args.project_root, args.change)
    default_change = args.change or changes[0]["name"]
    server = ThreadingHTTPServer(
        (args.host, args.port), make_handler(args.project_root.resolve(), default_change)
    )
    host, port = server.server_address[:2]
    print(f"OpenSpec dashboard: http://{host}:{port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
