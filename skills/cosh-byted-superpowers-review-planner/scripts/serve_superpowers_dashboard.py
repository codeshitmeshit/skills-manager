#!/usr/bin/env python3
"""Serve the ByteDance Superpowers workflow projection over HTTP and SSE."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import logging
import mimetypes
import os
import sys
import tempfile
import threading
import time
import webbrowser
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import parse_qs, urlparse


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import task_control  # noqa: E402
import workflow_state  # noqa: E402
import archive_work  # noqa: E402


LOGGER = logging.getLogger("byted-superpowers-dashboard")
ASSET_DIR = SCRIPT_DIR.parent / "assets" / "dashboard"
MAX_REQUEST_BYTES = 1024 * 1024
CONTROL_LOCK = threading.Lock()
FIXED_PORT = 57171
DASHBOARD_STATE_FILENAME = "dashboard-state.json"


def _json_bytes(payload: Mapping[str, Any]) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n").encode(
        "utf-8"
    )


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.replace(path)


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_work(project_root: Path, configured: str | None) -> str | None:
    works = workflow_state.list_works(project_root)
    names = [item["name"] for item in works]
    if configured in names:
        return configured
    return names[0] if names else None


def _documents(project_root: Path, work_id: str) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    work_dir = workflow_state.resolve_work(project_root, work_id)
    try:
        source = json.loads((work_dir / "source.json").read_text(encoding="utf-8"))
        source_path = work_dir / str(source.get("path", "technical-design.md"))
        if source_path.is_file():
            result.append(
                {
                    "category": "source",
                    "label": "技术文档",
                    "path": str(source_path.relative_to(project_root.resolve())),
                }
            )
    except (OSError, json.JSONDecodeError, ValueError):
        pass

    for category, root in (
        ("spec", project_root / "docs" / "superpowers" / "specs"),
        ("plan", project_root / "docs" / "superpowers" / "plans"),
    ):
        if not root.is_dir():
            continue
        for path in sorted(root.glob(f"*-{work_id}*.md")):
            result.append(
                {
                    "category": category,
                    "label": "规格" if category == "spec" else "计划",
                    "path": str(path.resolve().relative_to(project_root.resolve())),
                }
            )
    evidence_dir = work_dir / "evidence"
    if evidence_dir.is_dir():
        for path in sorted(evidence_dir.glob("*.json")):
            result.append(
                {
                    "category": "validation",
                    "label": "验证",
                    "path": str(path.resolve().relative_to(project_root.resolve())),
                }
            )
    return result


def _dashboard_state_path(project_root: Path, work_id: str) -> Path:
    return workflow_state.resolve_work(project_root, work_id) / DASHBOARD_STATE_FILENAME


def _persist_dashboard_state(project_root: Path, status: Mapping[str, Any]) -> None:
    work_id = str(status.get("work", ""))
    if not work_id:
        return
    snapshot = {
        key: value
        for key, value in status.items()
        if key not in {"read_at", "projection_error"}
    }
    snapshot["stale"] = False
    path = _dashboard_state_path(project_root, work_id)
    try:
        if path.is_file() and json.loads(path.read_text(encoding="utf-8")) == snapshot:
            return
    except (OSError, json.JSONDecodeError):
        pass
    try:
        _atomic_write_json(path, snapshot)
    except OSError as error:
        LOGGER.warning("观察板状态快照写入失败：work=%s error=%s", work_id, error)


def _restore_dashboard_state(
    project_root: Path, work_id: str | None, error: Exception
) -> dict[str, Any]:
    work_dir = workflow_state.resolve_work(project_root, work_id)
    snapshot = json.loads(
        (work_dir / DASHBOARD_STATE_FILENAME).read_text(encoding="utf-8")
    )
    if not isinstance(snapshot, dict):
        raise workflow_state.DashboardError("观察板持久化快照格式无效")
    restored = copy.deepcopy(snapshot)
    restored["stale"] = True
    restored["can_authorize"] = False
    restored["projection_error"] = str(error)
    restored["read_at"] = _iso_now()
    for stage in restored.get("stages", {}).values():
        if isinstance(stage, dict):
            stage["can_advance"] = False
    current_task = restored.get("current_task")
    if isinstance(current_task, dict):
        current_task["can_advance"] = False
    return restored


def build_status(project_root: Path, work_id: str | None) -> dict[str, Any]:
    try:
        status = workflow_state.build_status(project_root, work_id)
        status["documents"] = _documents(project_root, status["work"])
        status["stale"] = False
        status["read_at"] = _iso_now()
        _persist_dashboard_state(project_root, status)
        return status
    except Exception as error:
        try:
            restored = _restore_dashboard_state(project_root, work_id, error)
        except Exception:
            raise error
        LOGGER.warning(
            "观察板实时投影失败，恢复最后有效快照：work=%s error=%s",
            restored.get("work"),
            error,
        )
        return restored


def event_payload(project_root: Path, work_id: str | None) -> tuple[str, dict[str, Any]]:
    payload = build_status(project_root, work_id)
    # 读取时间只用于页面显示，不能触发无意义的 SSE 增量事件。
    signed_payload = {key: value for key, value in payload.items() if key != "read_at"}
    signature = hashlib.sha256(_json_bytes(signed_payload)).hexdigest()
    return signature, payload


def _allowed_document(project_root: Path, work_id: str, relative_path: str) -> Path:
    if not relative_path:
        raise workflow_state.DashboardError("缺少文档 path")
    root = project_root.resolve()
    candidate = (root / relative_path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as error:
        raise workflow_state.DashboardError("文档路径越界") from error
    allowed = {item["path"] for item in _documents(root, work_id)}
    normalized = str(candidate.relative_to(root))
    if normalized not in allowed:
        raise workflow_state.DashboardError("文档不属于当前开发任务")
    if not candidate.is_file():
        raise workflow_state.DashboardError("文档不存在")
    return candidate


def read_document(project_root: Path, work_id: str, relative_path: str) -> dict[str, str]:
    path = _allowed_document(project_root, work_id, relative_path)
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise workflow_state.DashboardError(f"文档读取失败：{error}") from error
    return {
        "path": relative_path,
        "content": content,
        "version": hashlib.sha256(content.encode("utf-8")).hexdigest()[:16],
    }


def _set_mode(
    project_root: Path,
    work_id: str,
    expected_version: str,
    mode: str,
) -> dict[str, Any]:
    if mode not in {"single", "continuous"}:
        raise workflow_state.DashboardError("推进模式必须是 single 或 continuous")
    before = workflow_state.build_status(project_root, work_id)
    if before["version"] != expected_version:
        raise workflow_state.DashboardConflict("开发任务状态已经变化，请刷新后重试")
    work_dir = workflow_state.resolve_work(project_root, work_id)
    path = work_dir / "workflow.json"
    try:
        workflow = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise workflow_state.DashboardError(f"workflow.json 不可读：{error}") from error
    workflow["mode"] = mode
    workflow["state_version"] = int(workflow.get("state_version", 0)) + 1
    workflow["updated_at"] = _iso_now()
    _atomic_write_json(path, workflow)
    LOGGER.info("推进模式已更新：work=%s mode=%s", work_id, mode)
    return build_status(project_root, work_id)


def _request_source_revision(
    project_root: Path, work_id: str, expected_version: str
) -> dict[str, Any]:
    before = workflow_state.build_status(project_root, work_id)
    if before["version"] != expected_version:
        raise workflow_state.DashboardConflict("开发任务状态已经变化，请刷新后重试")
    work_dir = workflow_state.resolve_work(project_root, work_id)
    control_path = work_dir / "control.json"
    payload: dict[str, Any] = {}
    if control_path.is_file():
        try:
            payload = json.loads(control_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload = {}
    payload["source_revision_requested"] = True
    payload["updated_at"] = _iso_now()
    _atomic_write_json(control_path, payload)
    LOGGER.info("已请求修改技术文档：work=%s", work_id)
    return build_status(project_root, work_id)


def _control_request_hash(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        dict(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _load_control(work_dir: Path) -> dict[str, Any]:
    path = work_dir / "control.json"
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise workflow_state.DashboardConflict("控制状态损坏，拒绝继续写入") from error
    if not isinstance(value, dict):
        raise workflow_state.DashboardConflict("控制状态格式无效，拒绝继续写入")
    return value


def _record_idempotency(
    work_dir: Path, key: str, action: str, request_hash: str
) -> None:
    control = _load_control(work_dir)
    records = control.setdefault("idempotency", {})
    if not isinstance(records, dict):
        raise workflow_state.DashboardConflict("幂等状态格式无效，拒绝继续写入")
    records[key] = {
        "action": action,
        "request_hash": request_hash,
        "recorded_at": _iso_now(),
    }
    control["updated_at"] = _iso_now()
    _atomic_write_json(work_dir / "control.json", control)


def _set_finding_blocking(
    project_root: Path,
    work_id: str,
    expected_version: str,
    finding_key: Any,
    blocking: Any,
    reason: Any,
) -> None:
    before = workflow_state.build_status(project_root, work_id)
    if before["version"] != expected_version:
        raise workflow_state.DashboardConflict("开发任务状态已经变化，请刷新后重试")
    if not isinstance(finding_key, str) or not finding_key:
        raise workflow_state.DashboardError("缺少 finding_key")
    if not isinstance(blocking, bool):
        raise workflow_state.DashboardError("blocking 必须是布尔值")
    findings = before.get("reviews", {}).get("findings", [])
    finding = next(
        (item for item in findings if item.get("finding_key") == finding_key), None
    )
    if finding is None:
        raise workflow_state.DashboardConflict("风险点已经变化，请刷新后重试")
    if finding.get("status") not in workflow_state.ACTIVE_FINDING_STATUSES:
        raise workflow_state.DashboardError("只能调整尚未闭合的风险点")
    if not blocking:
        if finding.get("severity") == "P0":
            raise workflow_state.DashboardError("P0 风险强制阻塞，不允许设为不阻塞")
        if not isinstance(reason, str) or not reason.strip():
            raise workflow_state.DashboardError("设为不阻塞时必须填写原因")
        if finding.get("raw_blocking") is not True:
            raise workflow_state.DashboardError("该风险点的 Reviewer 原始结论并非阻塞")

    work_dir = workflow_state.resolve_work(project_root, work_id)
    control = _load_control(work_dir)
    overrides = control.setdefault("finding_overrides", {})
    history = control.setdefault("finding_override_history", [])
    if not isinstance(overrides, dict) or not isinstance(history, list):
        raise workflow_state.DashboardConflict("风险点控制状态格式无效，拒绝继续写入")
    now = _iso_now()
    audit = {
        "finding_key": finding_key,
        "blocking": blocking,
        "reason": reason.strip() if isinstance(reason, str) else "",
        "source_version": before.get("source", {}).get("version"),
        "source_sha256": before.get("source", {}).get("sha256"),
        "review_round": finding.get("round"),
        "reviewer": finding.get("reviewer"),
        "finding_id": finding.get("id"),
        "updated_at": now,
    }
    if blocking:
        overrides.pop(finding_key, None)
    else:
        overrides[finding_key] = audit
    history.append(audit)
    control["updated_at"] = now
    _atomic_write_json(work_dir / "control.json", control)
    LOGGER.info(
        "已调整风险点阻塞状态：work=%s finding=%s blocking=%s",
        work_id,
        finding_key,
        blocking,
    )


def _apply_control_locked(
    project_root: Path, payload: Mapping[str, Any]
) -> dict[str, Any]:
    action = payload.get("action")
    work_id = payload.get("work")
    expected_version = payload.get("expected_version")
    idempotency_key = payload.get("idempotency_key")
    if not isinstance(work_id, str) or not work_id:
        raise workflow_state.DashboardError("缺少 work")
    if not isinstance(expected_version, str) or not expected_version:
        raise workflow_state.DashboardError("缺少 expected_version")
    if not isinstance(idempotency_key, str) or not idempotency_key:
        raise workflow_state.DashboardError("缺少 idempotency_key")
    work_dir = workflow_state.resolve_work(project_root, work_id)
    request_hash = _control_request_hash(payload)
    control = _load_control(work_dir)
    records = control.get("idempotency", {})
    if records and not isinstance(records, dict):
        raise workflow_state.DashboardConflict("幂等状态格式无效，拒绝继续写入")
    previous = records.get(idempotency_key) if isinstance(records, dict) else None
    if previous is not None:
        if not isinstance(previous, dict) or previous.get("request_hash") != request_hash:
            raise workflow_state.DashboardConflict("幂等键已被其他控制请求使用")
        LOGGER.info("复用控制请求结果：work=%s action=%s", work_id, action)
        return build_status(project_root, work_id)

    if action == "set-mode":
        _set_mode(project_root, work_id, expected_version, str(payload.get("mode")))
    elif action == "advance-next":
        task_number = payload.get("expected_task")
        if not isinstance(task_number, int):
            raise workflow_state.DashboardError("expected_task 必须是整数")
        task_control.advance_task(
            project_root,
            work_id,
            expected_version=expected_version,
            expected_task=task_number,
            commit_type=str(payload.get("commit_type", "feat")),
            summary=str(payload.get("summary", "")),
        )
    elif action == "authorize-next":
        task_number = payload.get("expected_task")
        if not isinstance(task_number, int):
            raise workflow_state.DashboardError("expected_task 必须是整数")
        task_control.authorize_next_task(
            project_root,
            work_id,
            expected_version=expected_version,
            expected_task=task_number,
        )
    elif action == "request-source-revision":
        _request_source_revision(project_root, work_id, expected_version)
    elif action == "set-finding-blocking":
        _set_finding_blocking(
            project_root,
            work_id,
            expected_version,
            payload.get("finding_key"),
            payload.get("blocking"),
            payload.get("reason"),
        )
    elif action == "archive":
        before = workflow_state.build_status(project_root, work_id)
        if before["version"] != expected_version:
            raise workflow_state.DashboardConflict("开发任务状态已经变化，请刷新后重试")
        archive_work.archive_work(project_root, work_id, "manual")
    else:
        raise workflow_state.DashboardError(f"不支持的控制动作：{action}")

    # 只在动作成功后落盘，网络重试不会重复提交或重复归档。
    _record_idempotency(work_dir, idempotency_key, str(action), request_hash)
    return build_status(project_root, work_id)


def apply_control(project_root: Path, payload: Mapping[str, Any]) -> dict[str, Any]:
    with CONTROL_LOCK:
        return _apply_control_locked(project_root, payload)


def make_handler(
    project_root: Path, default_work: str | None
) -> type[BaseHTTPRequestHandler]:
    root = project_root.resolve()

    class DashboardHandler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, format_string: str, *args: Any) -> None:
            LOGGER.info("%s - %s", self.client_address[0], format_string % args)

        def _send_bytes(
            self,
            body: bytes,
            content_type: str,
            status: HTTPStatus = HTTPStatus.OK,
        ) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(body)
            self.close_connection = True

        def _send_json(
            self, payload: Mapping[str, Any], status: HTTPStatus = HTTPStatus.OK
        ) -> None:
            self._send_bytes(_json_bytes(payload), "application/json; charset=utf-8", status)

        def _error(self, error: Exception) -> None:
            if isinstance(
                error,
                (workflow_state.DashboardConflict, task_control.TaskControlConflict),
            ):
                status = HTTPStatus.CONFLICT
            elif isinstance(
                error, (workflow_state.DashboardError, task_control.TaskControlError)
            ):
                status = HTTPStatus.BAD_REQUEST
            else:
                LOGGER.exception("观察板请求失败")
                status = HTTPStatus.INTERNAL_SERVER_ERROR
            self._send_json({"error": str(error)}, status)

        def _selected_work(self, query: Mapping[str, list[str]]) -> str:
            requested = query.get("work", [None])[0]
            selected = requested or _default_work(root, default_work)
            if not selected:
                raise workflow_state.DashboardError("没有可用的开发任务")
            return selected

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)
            try:
                if parsed.path == "/api/works":
                    self._send_json(
                        {
                            "default_work": _default_work(root, default_work),
                            "works": workflow_state.list_works(root),
                        }
                    )
                    return
                if parsed.path == "/api/status":
                    self._send_json(build_status(root, self._selected_work(query)))
                    return
                if parsed.path == "/api/document":
                    selected = self._selected_work(query)
                    relative = query.get("path", [""])[0]
                    self._send_json(read_document(root, selected, relative))
                    return
                if parsed.path == "/events":
                    self._serve_events(self._selected_work(query))
                    return
                self._serve_static(parsed.path)
            except Exception as error:  # HTTP boundary converts typed errors.
                self._error(error)

        def do_POST(self) -> None:  # noqa: N802
            if urlparse(self.path).path != "/api/control":
                self._send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > MAX_REQUEST_BYTES:
                    raise workflow_state.DashboardError("请求体大小无效")
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                if not isinstance(payload, dict):
                    raise workflow_state.DashboardError("请求体必须是 JSON 对象")
                self._send_json(apply_control(root, payload))
            except json.JSONDecodeError as error:
                self._error(workflow_state.DashboardError(f"JSON 解析失败：{error.msg}"))
            except Exception as error:
                self._error(error)

        def _serve_static(self, request_path: str) -> None:
            relative = "index.html" if request_path in {"", "/"} else request_path.lstrip("/")
            if relative not in {"index.html", "app.js", "styles.css"}:
                self._send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
                return
            path = ASSET_DIR / relative
            body = path.read_bytes()
            content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            if content_type.startswith("text/") or content_type == "application/javascript":
                content_type += "; charset=utf-8"
            self._send_bytes(body, content_type)

        def _serve_events(self, work_id: str) -> None:
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.send_header("X-Accel-Buffering", "no")
            self.end_headers()
            previous = ""
            while True:
                try:
                    archive_work.archive_after_push(root, work_id)
                    signature, payload = event_payload(root, work_id)
                    if signature != previous:
                        frame = (
                            "event: status\n"
                            f"id: {payload['version']}\n"
                            f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                        )
                        self.wfile.write(frame.encode("utf-8"))
                        self.wfile.flush()
                        previous = signature
                    time.sleep(0.2)
                except (BrokenPipeError, ConnectionResetError):
                    self.close_connection = True
                    return
                except Exception as error:
                    frame = (
                        "event: read-error\n"
                        f"data: {json.dumps({'error': str(error)}, ensure_ascii=False)}\n\n"
                    )
                    try:
                        self.wfile.write(frame.encode("utf-8"))
                        self.wfile.flush()
                    except (BrokenPipeError, ConnectionResetError):
                        self.close_connection = True
                        return
                    time.sleep(0.5)

    return DashboardHandler


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serve a ByteDance Superpowers dashboard")
    parser.add_argument("--project", type=Path, default=Path.cwd())
    parser.add_argument("--work")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, choices=(FIXED_PORT,), default=FIXED_PORT)
    parser.add_argument(
        "--open",
        action="store_true",
        dest="open_browser",
        help="Open the dashboard in the system default browser after binding",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
    server = ThreadingHTTPServer(
        (args.host, args.port), make_handler(args.project, args.work)
    )
    host, port = server.server_address
    dashboard_url = f"http://{host}:{port}/"
    print(f"Superpowers dashboard: {dashboard_url}", flush=True)
    if getattr(args, "open_browser", False):
        try:
            if not webbrowser.open(dashboard_url, new=2):
                LOGGER.warning("系统默认浏览器未接受观察板地址：%s", dashboard_url)
        except Exception as error:
            LOGGER.warning(
                "自动打开系统默认浏览器失败：%s；请手动打开 %s",
                error,
                dashboard_url,
            )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
