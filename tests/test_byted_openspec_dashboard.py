from __future__ import annotations

import importlib.util
import json
import pathlib
import subprocess
import tempfile
import threading
import time
import unittest
import urllib.request
import urllib.error
from http.server import ThreadingHTTPServer


ROOT = pathlib.Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skills" / "cosh-byted-openspec-review-planner"
SCRIPT_PATH = SKILL_DIR / "scripts" / "serve_openspec_dashboard.py"
SPEC = importlib.util.spec_from_file_location("openspec_dashboard", SCRIPT_PATH)
assert SPEC and SPEC.loader
DASHBOARD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DASHBOARD)


def read_sse_event(response, expected_event: str = "status") -> dict:
    event_name = "message"
    data_lines: list[str] = []
    while True:
        raw_line = response.readline()
        if not raw_line:
            raise AssertionError("SSE connection closed before the expected event")
        line = raw_line.decode("utf-8").rstrip("\r\n")
        if not line:
            if event_name == expected_event and data_lines:
                return json.loads("\n".join(data_lines))
            event_name = "message"
            data_lines = []
            continue
        if line.startswith(":") or line.startswith("retry:"):
            continue
        if line.startswith("event:"):
            event_name = line.removeprefix("event:").strip()
        elif line.startswith("data:"):
            data_lines.append(line.removeprefix("data:").lstrip())


class BytedOpenSpecDashboardTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temp.name)
        self.change = self.root / "openspec" / "changes" / "live-change"
        self.change.mkdir(parents=True)
        (self.change / "proposal.md").write_text("# Proposal\n", encoding="utf-8")
        (self.change / "analysis.md").write_text(
            """修改点 ID：MP-1
对应 scenario：create request rejects empty request id
文件：internal/service.go
符号：Service.Create
变量：requestID
类型：string
目标变化：为空时返回参数错误
未决假设：

修改点 ID：MP-2
对应 scenario：create request records rejection reason
文件：internal/metrics.go
符号：emitCreateMetric
变量：rejectReason
类型：string
目标变化：记录有界的拒绝原因
未决假设：
""",
            encoding="utf-8",
        )
        (self.change / "design.md").write_text("# Design\nMP-1\nMP-2\n", encoding="utf-8")
        self.tasks_path = self.change / "tasks.md"
        self.tasks_path.write_text("- [x] add test\n- [ ] implement guard\n", encoding="utf-8")

    def tearDown(self) -> None:
        for attempt in range(5):
            try:
                self.temp.cleanup()
                return
            except OSError:
                if attempt == 4:
                    raise
                time.sleep(0.05)

    def initialize_git_repository(self) -> None:
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.name", "Dashboard Test"], cwd=self.root, check=True)
        subprocess.run(
            ["git", "config", "user.email", "dashboard-test@example.com"],
            cwd=self.root,
            check=True,
        )
        subprocess.run(["git", "config", "gc.auto", "0"], cwd=self.root, check=True)
        subprocess.run(
            ["git", "config", "maintenance.auto", "false"], cwd=self.root, check=True
        )
        subprocess.run(["git", "add", "."], cwd=self.root, check=True)
        subprocess.run(
            ["git", "commit", "-q", "-m", "initial"], cwd=self.root, check=True
        )

    def test_status_reads_change_tasks_and_variable_point(self) -> None:
        status = DASHBOARD.build_status(self.root, "live-change")
        self.assertEqual(status["change"], "live-change")
        self.assertEqual(status["tasks"]["total"], 2)
        self.assertEqual(status["tasks"]["done"], 1)
        self.assertEqual(status["modification_points"][0]["variable"], "requestID")
        self.assertEqual(len(status["modification_points"]), 2)
        self.assertEqual(status["stage"], "任务实现")

    def test_documents_are_mapped_to_each_modification_page(self) -> None:
        status = DASHBOARD.build_status(self.root, "live-change")
        proposal = next(doc for doc in status["documents"] if doc["path"] == "proposal.md")
        design = next(doc for doc in status["documents"] if doc["path"] == "design.md")
        self.assertEqual(proposal["category"], "spec")
        self.assertEqual(proposal["point_ids"], ["MP-1", "MP-2"])
        self.assertEqual(design["point_ids"], ["MP-1", "MP-2"])

    def test_status_reflects_task_change_without_cache(self) -> None:
        before = DASHBOARD.build_status(self.root, "live-change")
        self.tasks_path.write_text("- [x] add test\n- [x] implement guard\n", encoding="utf-8")
        after = DASHBOARD.build_status(self.root, "live-change")
        self.assertEqual(before["tasks"]["done"], 1)
        self.assertEqual(after["tasks"]["done"], 2)
        self.assertEqual(after["stage"], "整体验证")

    def test_multiple_changes_require_explicit_selection(self) -> None:
        (self.root / "openspec" / "changes" / "another-change").mkdir()
        with self.assertRaises(DASHBOARD.DashboardError):
            DASHBOARD.build_status(self.root)

    def test_change_catalog_lists_multiple_active_changes(self) -> None:
        another = self.root / "openspec" / "changes" / "another-change"
        another.mkdir()
        (another / "proposal.md").write_text("# Another\n", encoding="utf-8")
        changes = DASHBOARD.list_changes(self.root)
        self.assertEqual([item["name"] for item in changes], ["another-change", "live-change"])
        self.assertIn("stage", changes[0])

    def test_status_endpoint_can_select_a_change_by_query(self) -> None:
        another = self.root / "openspec" / "changes" / "another-change"
        another.mkdir()
        (another / "proposal.md").write_text("# Another\n", encoding="utf-8")
        server = ThreadingHTTPServer(
            ("127.0.0.1", 0), DASHBOARD.make_handler(self.root, "live-change")
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = server.server_address[:2]
            with urllib.request.urlopen(
                f"http://{host}:{port}/api/status?change=another-change"
            ) as response:
                payload = json.loads(response.read().decode("utf-8"))
            self.assertEqual(payload["change"], "another-change")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_changes_endpoint_returns_switcher_catalog(self) -> None:
        another = self.root / "openspec" / "changes" / "another-change"
        another.mkdir()
        (another / "proposal.md").write_text("# Another\n", encoding="utf-8")
        server = ThreadingHTTPServer(
            ("127.0.0.1", 0), DASHBOARD.make_handler(self.root, "live-change")
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = server.server_address[:2]
            with urllib.request.urlopen(f"http://{host}:{port}/api/changes") as response:
                payload = json.loads(response.read().decode("utf-8"))
            self.assertEqual(payload["default_change"], "live-change")
            self.assertEqual(
                [item["name"] for item in payload["changes"]],
                ["another-change", "live-change"],
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_dashboard_has_only_restricted_control_write(self) -> None:
        html = (SKILL_DIR / "assets" / "dashboard" / "index.html").read_text(encoding="utf-8")
        javascript = (SKILL_DIR / "assets" / "dashboard" / "app.js").read_text(encoding="utf-8")
        stylesheet = (SKILL_DIR / "assets" / "dashboard" / "styles.css").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("<form", html)
        self.assertNotIn("<input", html)
        self.assertNotIn("localStorage", javascript)
        self.assertIn('method: "POST"', javascript)
        self.assertIn('fetch("/api/control"', javascript)
        self.assertNotIn('method: "PUT"', javascript)
        self.assertNotIn('method: "DELETE"', javascript)
        self.assertIn('window.location.protocol === "file:"', javascript)
        self.assertIn("模板示例", javascript)
        self.assertIn('new EventSource(apiUrl("/events", { change }))', javascript)
        self.assertIn('fetch("/api/changes"', javascript)
        self.assertIn("setInterval(refreshChangeCatalog, 2000)", javascript)
        self.assertIn('id="change-select"', javascript)
        self.assertIn("change: data.change", javascript)
        self.assertIn("正在重连", javascript)
        self.assertIn('params.get("point")', javascript)
        self.assertIn('params.get("artifact")', javascript)
        self.assertIn('aria-label="OpenSpec 产物导航"', javascript)
        self.assertIn('["proposal", "spec", "analysis", "design", "validation", "tasks"]', javascript)
        self.assertIn('section === "tasks" ? "task-primary"', javascript)
        self.assertIn(".artifact-nav-link.task-primary", stylesheet)
        self.assertIn("margin-left: auto", stylesheet)
        self.assertIn("Proposal", javascript)
        self.assertIn("renderArtifactPage", javascript)
        self.assertIn("artifact: doc.path", javascript)
        self.assertNotIn('<h2>Artifacts</h2>', javascript)
        self.assertIn("规格", javascript)
        self.assertIn("Design", javascript)
        self.assertIn('apiUrl("/api/document"', javascript)
        self.assertIn("连续推进", javascript)
        self.assertIn("单独推进", javascript)
        self.assertIn("推进下一个任务", javascript)
        self.assertIn('class="card tasks-card task-page-board"', javascript)
        self.assertNotIn('class="task-control"', javascript)
        overview_source = javascript.split("function renderOverview", 1)[1].split(
            "function renderTaskBoard", 1
        )[0]
        self.assertNotIn("tasks-card", overview_source)
        self.assertIn('selectedSection === "tasks" ? renderTaskBoard(data)', javascript)
        self.assertIn('selectedSection === "tasks") bindExecutionControls(data)', javascript)
        task_rows_source = javascript.split("function renderTasks", 1)[1].split(
            "function bindExecutionControls", 1
        )[0]
        self.assertIn('current && control.mode !== "continuous"', task_rows_source)
        self.assertIn("task-row-action", task_rows_source)
        self.assertNotIn("function renderTaskControls", javascript)
        self.assertIn('selectedSection === "tasks" ? "" : renderDocumentReader', javascript)
        self.assertIn('else loadDocument(data, selectedDocument)', javascript)
        self.assertNotIn("renderExecutionControls", javascript)
        self.assertIn("expected_task: expectedTask", javascript)

    def test_execution_control_defaults_to_single_mode(self) -> None:
        status = DASHBOARD.build_status(self.root, "live-change")
        self.assertEqual(status["tasks"]["execution_control"]["mode"], "single")

    def test_continuous_mode_updates_only_control_marker(self) -> None:
        before = DASHBOARD.build_status(self.root, "live-change")
        updated = DASHBOARD.update_execution_control(
            self.root,
            "live-change",
            action="set-mode",
            mode="continuous",
            expected_version=before["tasks"]["version"],
            expected_task="implement guard",
        )
        text = self.tasks_path.read_text(encoding="utf-8")
        self.assertEqual(updated["tasks"]["execution_control"]["mode"], "continuous")
        self.assertIn("cosh-dashboard-control", text)
        self.assertIn("- [x] add test", text)
        self.assertIn("- [ ] implement guard", text)

    def test_single_mode_advance_records_approved_and_next_task(self) -> None:
        before = DASHBOARD.build_status(self.root, "live-change")
        updated = DASHBOARD.update_execution_control(
            self.root,
            "live-change",
            action="advance-next",
            expected_version=before["tasks"]["version"],
            expected_task="implement guard",
        )
        control = updated["tasks"]["execution_control"]
        self.assertEqual(control["approved_task"], "implement guard")
        self.assertEqual(control["advance_to_task"], "最终验证")
        self.assertEqual(updated["tasks"]["done"], 1)

    def test_stale_control_write_is_rejected(self) -> None:
        before = DASHBOARD.build_status(self.root, "live-change")
        self.tasks_path.write_text("- [x] add test\n- [ ] changed task\n", encoding="utf-8")
        with self.assertRaises(DASHBOARD.DashboardConflict):
            DASHBOARD.update_execution_control(
                self.root,
                "live-change",
                action="set-mode",
                mode="continuous",
                expected_version=before["tasks"]["version"],
                expected_task="implement guard",
            )

    def test_control_rejects_a_task_that_is_no_longer_current(self) -> None:
        before = DASHBOARD.build_status(self.root, "live-change")
        with self.assertRaises(DASHBOARD.DashboardConflict):
            DASHBOARD.update_execution_control(
                self.root,
                "live-change",
                action="advance-next",
                expected_version=before["tasks"]["version"],
                expected_task="add test",
            )

    def test_http_status_endpoint_serves_live_projection(self) -> None:
        server = ThreadingHTTPServer(
            ("127.0.0.1", 0), DASHBOARD.make_handler(self.root, "live-change")
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = server.server_address[:2]
            with urllib.request.urlopen(f"http://{host}:{port}/api/status") as response:
                payload = response.read().decode("utf-8")
            self.assertIn('"change": "live-change"', payload)
            self.assertIn('"variable": "requestID"', payload)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_document_endpoint_reads_only_change_artifacts(self) -> None:
        server = ThreadingHTTPServer(
            ("127.0.0.1", 0), DASHBOARD.make_handler(self.root, "live-change")
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = server.server_address[:2]
            with urllib.request.urlopen(
                f"http://{host}:{port}/api/document?path=design.md"
            ) as response:
                payload = response.read().decode("utf-8")
            self.assertIn('"path": "design.md"', payload)
            self.assertIn("MP-2", payload)
            with self.assertRaises(urllib.error.HTTPError) as context:
                urllib.request.urlopen(
                    f"http://{host}:{port}/api/document?path=../../outside.md"
                )
            self.assertEqual(context.exception.code, 422)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_control_endpoint_switches_execution_mode(self) -> None:
        server = ThreadingHTTPServer(
            ("127.0.0.1", 0), DASHBOARD.make_handler(self.root, "live-change")
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = server.server_address[:2]
            status = DASHBOARD.build_status(self.root, "live-change")
            body = json.dumps(
                {
                    "action": "set-mode",
                    "mode": "continuous",
                    "expected_version": status["tasks"]["version"],
                    "expected_task": "implement guard",
                }
            ).encode("utf-8")
            request = urllib.request.Request(
                f"http://{host}:{port}/api/control",
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request) as response:
                payload = response.read().decode("utf-8")
            self.assertIn('"mode": "continuous"', payload)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_control_endpoint_writes_only_the_selected_change(self) -> None:
        another = self.root / "openspec" / "changes" / "another-change"
        another.mkdir()
        another_tasks = another / "tasks.md"
        another_tasks.write_text("- [ ] second change task\n", encoding="utf-8")
        server = ThreadingHTTPServer(
            ("127.0.0.1", 0), DASHBOARD.make_handler(self.root, "live-change")
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = server.server_address[:2]
            status = DASHBOARD.build_status(self.root, "another-change")
            body = json.dumps(
                {
                    "action": "set-mode",
                    "mode": "continuous",
                    "change": "another-change",
                    "expected_task": "second change task",
                    "expected_version": status["tasks"]["version"],
                }
            ).encode("utf-8")
            request = urllib.request.Request(
                f"http://{host}:{port}/api/control",
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request) as response:
                payload = json.loads(response.read().decode("utf-8"))
            self.assertEqual(payload["change"], "another-change")
            self.assertIn("cosh-dashboard-control", another_tasks.read_text(encoding="utf-8"))
            self.assertNotIn("cosh-dashboard-control", self.tasks_path.read_text(encoding="utf-8"))
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_advance_endpoint_commits_the_staged_snapshot(self) -> None:
        self.initialize_git_repository()
        code_path = self.root / "service.go"
        code_path.write_text("package service\n", encoding="utf-8")
        subprocess.run(["git", "add", "service.go"], cwd=self.root, check=True)
        status = DASHBOARD.build_status(self.root, "live-change")
        server = ThreadingHTTPServer(
            ("127.0.0.1", 0), DASHBOARD.make_handler(self.root, "live-change")
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = server.server_address[:2]
            body = json.dumps(
                {
                    "action": "advance-next",
                    "change": "live-change",
                    "expected_task": "implement guard",
                    "expected_version": status["tasks"]["version"],
                }
            ).encode("utf-8")
            request = urllib.request.Request(
                f"http://{host}:{port}/api/control",
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request) as response:
                payload = json.loads(response.read().decode("utf-8"))
            self.assertTrue(payload["staged_commit"]["created"])
            self.assertEqual(payload["staged_commit"]["files"], ["service.go"])
            subject = subprocess.run(
                ["git", "log", "-1", "--pretty=%s"],
                cwd=self.root,
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            self.assertEqual(subject, "openspec(live-change): implement guard")
            self.assertIn("cosh-dashboard-control", self.tasks_path.read_text(encoding="utf-8"))
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_advance_endpoint_does_not_create_an_empty_commit(self) -> None:
        self.initialize_git_repository()
        before = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            cwd=self.root,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        status = DASHBOARD.build_status(self.root, "live-change")
        server = ThreadingHTTPServer(
            ("127.0.0.1", 0), DASHBOARD.make_handler(self.root, "live-change")
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = server.server_address[:2]
            body = json.dumps(
                {
                    "action": "advance-next",
                    "change": "live-change",
                    "expected_task": "implement guard",
                    "expected_version": status["tasks"]["version"],
                }
            ).encode("utf-8")
            request = urllib.request.Request(
                f"http://{host}:{port}/api/control",
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request) as response:
                payload = json.loads(response.read().decode("utf-8"))
            self.assertFalse(payload["staged_commit"]["created"])
            after = subprocess.run(
                ["git", "rev-list", "--count", "HEAD"],
                cwd=self.root,
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            self.assertEqual(after, before)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_advance_cannot_commit_while_continuous_mode_is_active(self) -> None:
        self.initialize_git_repository()
        before = DASHBOARD.build_status(self.root, "live-change")
        DASHBOARD.update_execution_control(
            self.root,
            "live-change",
            action="set-mode",
            mode="continuous",
            expected_version=before["tasks"]["version"],
            expected_task="implement guard",
        )
        code_path = self.root / "service.go"
        code_path.write_text("package service\n", encoding="utf-8")
        subprocess.run(["git", "add", "service.go"], cwd=self.root, check=True)
        status = DASHBOARD.build_status(self.root, "live-change")
        commit_before = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self.root,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        with self.assertRaises(DASHBOARD.DashboardError):
            DASHBOARD.commit_staged_changes(
                self.root,
                "live-change",
                expected_version=status["tasks"]["version"],
                expected_task="implement guard",
            )
        commit_after = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self.root,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        self.assertEqual(commit_after, commit_before)

    def test_failed_staged_commit_does_not_record_task_authorization(self) -> None:
        self.initialize_git_repository()
        code_path = self.root / "service.go"
        code_path.write_text("package service\n", encoding="utf-8")
        subprocess.run(["git", "add", "service.go"], cwd=self.root, check=True)
        hook = self.root / ".git" / "hooks" / "pre-commit"
        hook.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        hook.chmod(0o755)
        status = DASHBOARD.build_status(self.root, "live-change")
        server = ThreadingHTTPServer(
            ("127.0.0.1", 0), DASHBOARD.make_handler(self.root, "live-change")
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = server.server_address[:2]
            body = json.dumps(
                {
                    "action": "advance-next",
                    "change": "live-change",
                    "expected_task": "implement guard",
                    "expected_version": status["tasks"]["version"],
                }
            ).encode("utf-8")
            request = urllib.request.Request(
                f"http://{host}:{port}/api/control",
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with self.assertRaises(urllib.error.HTTPError) as context:
                urllib.request.urlopen(request)
            self.assertEqual(context.exception.code, 422)
            self.assertNotIn(
                "cosh-dashboard-control", self.tasks_path.read_text(encoding="utf-8")
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_event_payload_changes_when_task_changes(self) -> None:
        before_signature, before = DASHBOARD.event_payload(self.root, "live-change")
        time.sleep(0.01)
        self.tasks_path.write_text("- [x] add test\n- [x] implement guard\n", encoding="utf-8")
        after_signature, after = DASHBOARD.event_payload(self.root, "live-change")
        self.assertNotEqual(before_signature, after_signature)
        self.assertEqual(before["event"], "status")
        self.assertEqual(after["data"]["tasks"]["done"], 2)

    def test_event_payload_changes_when_design_content_changes(self) -> None:
        before_signature, _ = DASHBOARD.event_payload(self.root, "live-change")
        (self.change / "design.md").write_text("# Design\nMP-1\nMP-2\nnew decision\n", encoding="utf-8")
        after_signature, after = DASHBOARD.event_payload(self.root, "live-change")
        self.assertNotEqual(before_signature, after_signature)
        design = next(doc for doc in after["data"]["documents"] if doc["path"] == "design.md")
        self.assertTrue(design["version"])

    def test_event_stream_emits_initial_status(self) -> None:
        server = ThreadingHTTPServer(
            ("127.0.0.1", 0), DASHBOARD.make_handler(self.root, "live-change")
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        response = None
        try:
            host, port = server.server_address[:2]
            response = urllib.request.urlopen(f"http://{host}:{port}/events", timeout=2)
            lines = [response.readline().decode("utf-8") for _ in range(4)]
            joined = "".join(lines)
            self.assertIn("retry: 1000", joined)
            self.assertIn("event: status", joined)
            self.assertIn('"change": "live-change"', joined)
        finally:
            if response is not None:
                response.close()
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_running_listener_pushes_task_change_without_reconnect(self) -> None:
        server = ThreadingHTTPServer(
            ("127.0.0.1", 0), DASHBOARD.make_handler(self.root, "live-change")
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        response = None
        try:
            host, port = server.server_address[:2]
            response = urllib.request.urlopen(f"http://{host}:{port}/events", timeout=3)
            initial = read_sse_event(response)
            self.assertEqual(initial["tasks"]["done"], 1)

            self.tasks_path.write_text("- [x] add test\n- [x] implement guard\n", encoding="utf-8")
            updated = read_sse_event(response)
            self.assertEqual(updated["tasks"]["done"], 2)
            self.assertEqual(updated["stage"], "整体验证")
        finally:
            if response is not None:
                response.close()
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_running_listener_tracks_the_selected_change(self) -> None:
        another = self.root / "openspec" / "changes" / "another-change"
        another.mkdir()
        another_tasks = another / "tasks.md"
        another_tasks.write_text("- [ ] second change task\n", encoding="utf-8")
        server = ThreadingHTTPServer(
            ("127.0.0.1", 0), DASHBOARD.make_handler(self.root, "live-change")
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        response = None
        try:
            host, port = server.server_address[:2]
            response = urllib.request.urlopen(
                f"http://{host}:{port}/events?change=another-change", timeout=3
            )
            initial = read_sse_event(response)
            self.assertEqual(initial["change"], "another-change")
            self.assertEqual(initial["tasks"]["done"], 0)

            another_tasks.write_text("- [x] second change task\n", encoding="utf-8")
            updated = read_sse_event(response)
            self.assertEqual(updated["change"], "another-change")
            self.assertEqual(updated["tasks"]["done"], 1)
        finally:
            if response is not None:
                response.close()
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_running_listener_pushes_design_change_with_same_task_progress(self) -> None:
        server = ThreadingHTTPServer(
            ("127.0.0.1", 0), DASHBOARD.make_handler(self.root, "live-change")
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        response = None
        try:
            host, port = server.server_address[:2]
            response = urllib.request.urlopen(f"http://{host}:{port}/events", timeout=3)
            initial = read_sse_event(response)
            initial_design = next(
                doc for doc in initial["documents"] if doc["path"] == "design.md"
            )

            (self.change / "design.md").write_text(
                "# Design\nMP-1\nMP-2\nlistener update\n", encoding="utf-8"
            )
            updated = read_sse_event(response)
            updated_design = next(
                doc for doc in updated["documents"] if doc["path"] == "design.md"
            )
            self.assertNotEqual(initial_design["version"], updated_design["version"])
            self.assertEqual(initial["tasks"]["done"], updated["tasks"]["done"])
        finally:
            if response is not None:
                response.close()
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
