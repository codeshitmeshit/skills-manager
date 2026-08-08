from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.util
import io
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request
from unittest import mock


ROOT = pathlib.Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skills" / "cosh-byted-superpowers-review-planner"
WORKFLOW_PATH = SKILL_DIR / "scripts" / "workflow_state.py"
TASK_CONTROL_PATH = SKILL_DIR / "scripts" / "task_control.py"
SERVER_PATH = SKILL_DIR / "scripts" / "serve_superpowers_dashboard.py"
ARCHIVE_PATH = SKILL_DIR / "scripts" / "archive_work.py"


def load_module(name: str, path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


WORKFLOW = load_module("byted_workflow_state", WORKFLOW_PATH)
TASKS = load_module("byted_task_control", TASK_CONTROL_PATH)
SERVER = load_module("byted_superpowers_dashboard", SERVER_PATH)
ARCHIVE = load_module("byted_archive_work", ARCHIVE_PATH)


def read_sse_event(response, expected_event: str = "status") -> dict:
    event = ""
    data_lines: list[str] = []
    deadline = time.time() + 3
    while time.time() < deadline:
        raw = response.readline()
        if not raw:
            break
        line = raw.decode("utf-8").rstrip("\r\n")
        if not line:
            if event == expected_event and data_lines:
                return json.loads("\n".join(data_lines))
            event = ""
            data_lines = []
            continue
        if line.startswith("event: "):
            event = line[7:]
        elif line.startswith("data: "):
            data_lines.append(line[6:])
    raise AssertionError(f"did not receive SSE event {expected_event}")


class BytedSuperpowersWorkflowStateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temp_dir.name)
        self.work_id = "optimize-order-risk-check"
        self.work = self.root / ".superpowers" / "byted-work" / self.work_id
        (self.work / "reviews").mkdir(parents=True)
        (self.work / "evidence").mkdir()
        (self.root / "docs" / "superpowers" / "specs").mkdir(parents=True)
        (self.root / "docs" / "superpowers" / "plans").mkdir(parents=True)
        self.source_text = "# 订单风控优化技术方案\n"
        self.write_source(version=1, content=self.source_text)
        self.write_workflow()

    def tearDown(self) -> None:
        try:
            self.temp_dir.cleanup()
        except OSError:
            # macOS 的 Git 模板 hook 偶尔会短暂持有临时仓库目录。
            shutil.rmtree(self.temp_dir.name, ignore_errors=True)

    @staticmethod
    def sha256(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def write_json(self, path: pathlib.Path, payload: dict) -> pathlib.Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return path

    def write_source(self, version: int, content: str) -> None:
        source_path = self.work / "technical-design.md"
        source_path.write_text(content, encoding="utf-8")
        self.write_json(
            self.work / "source.json",
            {
                "version": version,
                "sha256": self.sha256(content),
                "path": "technical-design.md",
                "updated_at": "2026-08-02T10:00:00+08:00",
            },
        )

    def write_workflow(self, mode: str = "single", engine: str = "superpowers") -> None:
        self.write_json(
            self.work / "workflow.json",
            {
                "work": self.work_id,
                "mode": mode,
                "engine": engine,
                "state_version": 1,
                "updated_at": "2026-08-02T10:00:00+08:00",
            },
        )

    def current_binding(self) -> dict:
        source = json.loads((self.work / "source.json").read_text(encoding="utf-8"))
        return {
            "source_version": source["version"],
            "source_sha256": source["sha256"],
        }

    def write_knowledge_gate(self, status: str = "passed", **extra) -> None:
        payload = {
            **self.current_binding(),
            "status": status,
            "mode": "loaded",
            "version": "1.2.3",
            "sources": [{"role": "stability", "path": "a", "sha256": "a" * 64}],
            "updated_at": "2026-08-02T10:05:00+08:00",
            **extra,
        }
        self.write_json(self.work / "evidence" / "knowledge-gate.json", payload)

    def write_codegraph(self, status: str = "passed", code_sha: str = "code-sha") -> None:
        self.write_json(
            self.work / "evidence" / "codegraph.json",
            {
                **self.current_binding(),
                "status": status,
                "code_sha": code_sha,
                "locations": [
                    {
                        "file": "internal/order/risk.go",
                        "symbol": "shouldSkip",
                        "variable": "riskScene",
                        "type": "model.RiskScene",
                    }
                ],
                "updated_at": "2026-08-02T10:10:00+08:00",
            },
        )

    def write_review(
        self,
        reviewer: str,
        status: str = "passed",
        round_number: int = 1,
        source_version: int | None = None,
        source_sha256: str | None = None,
        code_sha: str = "code-sha",
    ) -> None:
        binding = self.current_binding()
        self.write_json(
            self.work / "reviews" / f"round-{round_number:03d}-{reviewer}.json",
            {
                "reviewer": reviewer,
                "round": round_number,
                "status": status,
                "source_version": source_version or binding["source_version"],
                "source_sha256": source_sha256 or binding["source_sha256"],
                "code_sha": code_sha,
                "stage": "completed",
                "findings": [],
                "updated_at": "2026-08-02T10:20:00+08:00",
            },
        )

    def write_complete_review_round(self) -> None:
        self.write_knowledge_gate()
        self.write_codegraph()
        for reviewer in WORKFLOW.REQUIRED_REVIEWERS:
            self.write_review(reviewer)

    def write_plan(self, content: str) -> pathlib.Path:
        path = (
            self.root
            / "docs"
            / "superpowers"
            / "plans"
            / f"2026-08-02-{self.work_id}.md"
        )
        path.write_text(content.strip() + "\n", encoding="utf-8")
        return path

    def write_global_prerequisites(self, plan: pathlib.Path) -> None:
        self.write_complete_review_round()
        self.write_json(
            self.work / "evidence" / "review-closure.json",
            {
                **self.current_binding(),
                "status": "passed",
                "review_round": 1,
                "updated_at": "2026-08-02T10:30:00+08:00",
            },
        )
        spec_path = (
            self.root
            / "docs"
            / "superpowers"
            / "specs"
            / f"2026-08-02-{self.work_id}-design.md"
        )
        spec_content = "# 订单风控优化规格\n"
        spec_path.write_text(spec_content, encoding="utf-8")
        spec_sha = self.sha256(spec_content)
        self.write_json(
            self.work / "evidence" / "spec.json",
            {
                **self.current_binding(),
                "status": "passed",
                "path": str(spec_path.relative_to(self.root)),
                "sha256": spec_sha,
                "updated_at": "2026-08-02T10:40:00+08:00",
            },
        )
        self.write_json(
            self.work / "evidence" / "location.json",
            {
                **self.current_binding(),
                "status": "passed",
                "spec_sha256": spec_sha,
                "code_sha": "code-sha",
                "locations": [
                    {
                        "file": "internal/order/risk.go",
                        "symbol": "shouldSkip",
                        "variable": "riskScene",
                        "type": "model.RiskScene",
                    }
                ],
                "updated_at": "2026-08-02T10:45:00+08:00",
            },
        )
        plan_content = plan.read_text(encoding="utf-8")
        self.write_json(
            self.work / "evidence" / "plan.json",
            {
                **self.current_binding(),
                "status": "passed",
                "path": str(plan.relative_to(self.root)),
                "sha256": self.sha256(plan_content),
                "code_sha": "code-sha",
                "updated_at": "2026-08-02T10:50:00+08:00",
            },
        )

    def initialize_git(self) -> None:
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)
        subprocess.run(
            ["git", "config", "user.email", "codex@example.com"],
            cwd=self.root,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Codex Test"], cwd=self.root, check=True
        )
        (self.root / "baseline.txt").write_text("baseline\n", encoding="utf-8")
        subprocess.run(["git", "add", "baseline.txt"], cwd=self.root, check=True)
        subprocess.run(
            ["git", "commit", "-q", "-m", "chore: 初始化"],
            cwd=self.root,
            check=True,
        )

    def stage_file(self, relative: str, content: str = "change\n") -> None:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        subprocess.run(["git", "add", relative], cwd=self.root, check=True)

    def git_head(self) -> str:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self.root,
            check=True,
            text=True,
            capture_output=True,
        ).stdout.strip()

    def write_task_evidence(self, task_number: int) -> None:
        snapshot = TASKS.current_snapshot_sha(self.root)
        for prefix in ("remote-ut", "cr"):
            self.write_json(
                self.work / "evidence" / f"{prefix}-task{task_number}.json",
                {
                    "status": "passed",
                    "code_sha": snapshot,
                    "updated_at": "2026-08-02T11:00:00+08:00",
                },
            )

    def start_server(self):
        server = SERVER.ThreadingHTTPServer(
            ("127.0.0.1", 0), SERVER.make_handler(self.root, self.work_id)
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return server

    def get_json(self, server, path: str) -> dict:
        host, port = server.server_address
        with urllib.request.urlopen(f"http://{host}:{port}{path}", timeout=3) as response:
            return json.loads(response.read().decode("utf-8"))

    def post_json(self, server, path: str, payload: dict):
        host, port = server.server_address
        request = urllib.request.Request(
            f"http://{host}:{port}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=3) as response:
            return response.status, json.loads(response.read().decode("utf-8"))

    def test_resolve_work_rejects_path_traversal(self) -> None:
        with self.assertRaises(WORKFLOW.DashboardError):
            WORKFLOW.resolve_work(self.root, "../outside")

    def test_list_works_returns_multiple_development_works(self) -> None:
        another = self.root / ".superpowers" / "byted-work" / "add-audit-log"
        another.mkdir()
        self.write_json(
            another / "source.json",
            {
                "version": 1,
                "sha256": "b" * 64,
                "path": "technical-design.md",
                "updated_at": "2026-08-02T09:00:00+08:00",
            },
        )
        works = WORKFLOW.list_works(self.root)
        self.assertEqual([item["name"] for item in works], ["add-audit-log", self.work_id])

    def test_source_hash_must_match_the_technical_document(self) -> None:
        source = json.loads((self.work / "source.json").read_text(encoding="utf-8"))
        source["sha256"] = "0" * 64
        self.write_json(self.work / "source.json", source)
        status = WORKFLOW.build_status(self.root, self.work_id)
        self.assertEqual(status["stages"]["source"]["status"], "blocked")
        self.assertIn("SHA-256", " ".join(status["stages"]["source"]["blockers"]))

    def test_hammer_engine_blocks_the_complete_superpowers_workflow(self) -> None:
        self.write_workflow(engine="hammer")
        self.write_complete_review_round()

        status = WORKFLOW.build_status(self.root, self.work_id)

        self.assertEqual(status["engine"], "hammer")
        self.assertEqual(status["stages"]["source"]["status"], "blocked")
        self.assertIn(
            "互斥", " ".join(status["stages"]["source"]["blockers"])
        )
        self.assertEqual(status["stages"]["review"]["status"], "blocked")

    def test_review_cannot_pass_without_all_three_current_reviewers(self) -> None:
        self.write_knowledge_gate()
        self.write_codegraph()
        self.write_review("stability")
        self.write_review("security")
        status = WORKFLOW.build_status(self.root, self.work_id)
        self.assertEqual(status["stages"]["review"]["status"], "blocked")
        self.assertIn("feasibility", " ".join(status["stages"]["review"]["blockers"]))

    def test_failed_reviewer_exposes_risk_and_fix(self) -> None:
        self.write_complete_review_round()
        review_path = self.work / "reviews" / "round-001-security.json"
        review = json.loads(review_path.read_text(encoding="utf-8"))
        review["status"] = "blocked"
        review["findings"] = [
            {
                "id": "SEC-1",
                "severity": "P0",
                "blocking": True,
                "title": "日志泄露订单标识",
                "evidence": "internal/order/risk.go:52",
                "recommendation": "复用脱敏函数后再记录",
                "status": "open",
            }
        ]
        self.write_json(review_path, review)
        status = WORKFLOW.build_status(self.root, self.work_id)
        self.assertEqual(status["stages"]["review"]["status"], "blocked")
        self.assertEqual(status["reviews"]["findings"][0]["title"], "日志泄露订单标识")
        self.assertEqual(status["reviews"]["findings"][0]["recommendation"], "复用脱敏函数后再记录")

    def test_review_normalizes_problem_suggestion_and_evidence_list(self) -> None:
        self.write_complete_review_round()
        review_path = self.work / "reviews" / "round-001-security.json"
        review = json.loads(review_path.read_text(encoding="utf-8"))
        review["status"] = "blocked"
        review["findings"] = [
            {
                "id": "SEC-R3-01",
                "severity": "P1",
                "blocking": True,
                "problem": "目标 FG 权限尚未完成验收",
                "evidence": ["technical-design.md:120", "SEC-102"],
                "suggestion": "补齐权限和审计证据",
                "status": "open",
            }
        ]
        self.write_json(review_path, review)

        status = WORKFLOW.build_status(self.root, self.work_id)

        finding = status["reviews"]["findings"][0]
        self.assertEqual(finding["title"], "目标 FG 权限尚未完成验收")
        self.assertEqual(finding["evidence"], ["technical-design.md:120", "SEC-102"])
        self.assertEqual(finding["recommendation"], "补齐权限和审计证据")
        self.assertEqual(finding["schema_errors"], [])

    def test_review_finding_without_evidence_fails_closed(self) -> None:
        self.write_complete_review_round()
        review_path = self.work / "reviews" / "round-001-security.json"
        review = json.loads(review_path.read_text(encoding="utf-8"))
        review["findings"] = [
            {
                "id": "SEC-R3-01",
                "severity": "P1",
                "blocking": False,
                "problem": "目标 FG 权限尚未完成验收",
                "suggestion": "补齐权限和审计证据",
                "status": "pending_confirmation",
            }
        ]
        self.write_json(review_path, review)

        status = WORKFLOW.build_status(self.root, self.work_id)

        self.assertEqual(status["stages"]["review"]["status"], "blocked")
        self.assertIn(
            "SEC-R3-01 缺少 evidence",
            " ".join(status["stages"]["review"]["blockers"]),
        )
        finding = status["reviews"]["findings"][0]
        self.assertEqual(finding["evidence"], "")
        self.assertEqual(finding["schema_errors"], ["缺少 evidence"])
        self.assertEqual(
            status["reviews"]["reviewers"]["security"]["effective_status"],
            "blocked",
        )
        self.assertEqual(status["primary_progress"]["done"], 2)

    def test_review_finding_requires_blocking_and_status_fields(self) -> None:
        self.write_complete_review_round()
        review_path = self.work / "reviews" / "round-001-security.json"
        review = json.loads(review_path.read_text(encoding="utf-8"))
        review["findings"] = [
            {
                "id": "SEC-R3-02",
                "severity": "P2",
                "title": "规则缺少审批证据",
                "evidence": "technical-design.md:220",
                "recommendation": "补充审批记录",
            }
        ]
        self.write_json(review_path, review)

        status = WORKFLOW.build_status(self.root, self.work_id)

        self.assertEqual(status["stages"]["review"]["status"], "blocked")
        errors = status["reviews"]["findings"][0]["schema_errors"]
        self.assertEqual(errors, ["缺少 blocking", "缺少 status"])

    def test_review_stage_reports_reviewer_progress_before_tasks_exist(self) -> None:
        self.write_knowledge_gate()
        self.write_codegraph()
        self.write_review("security")
        self.write_review("feasibility")

        status = WORKFLOW.build_status(self.root, self.work_id)

        self.assertEqual(
            status["primary_progress"],
            {"kind": "reviewers", "label": "Reviewer", "done": 2, "total": 3},
        )

    def test_document_revision_invalidates_gate_codegraph_and_reviews(self) -> None:
        self.write_complete_review_round()
        old = WORKFLOW.build_status(self.root, self.work_id)
        self.assertEqual(old["stages"]["review"]["status"], "passed")
        self.write_source(version=2, content="# 修订后的技术方案\n")
        status = WORKFLOW.build_status(self.root, self.work_id)
        self.assertEqual(status["stages"]["knowledge_gate"]["status"], "blocked")
        self.assertEqual(status["stages"]["codegraph"]["status"], "blocked")
        self.assertEqual(status["stages"]["review"]["status"], "blocked")
        self.assertTrue(status["reviews"]["history"])

    def test_stale_code_sha_invalidates_reviews(self) -> None:
        self.write_complete_review_round()
        self.write_review("feasibility", code_sha="stale-sha")
        status = WORKFLOW.build_status(self.root, self.work_id)
        self.assertEqual(status["stages"]["review"]["status"], "blocked")
        self.assertIn("代码 SHA", " ".join(status["stages"]["review"]["blockers"]))

    def test_fallback_is_blocked_even_with_complete_legacy_evidence(self) -> None:
        self.write_knowledge_gate(
            status="fallback",
            mode="fallback",
            onboarding_attempted=True,
            onboarding_error="registry unavailable",
            generic_rules_version="2026-08-02",
            sources=[],
        )
        self.write_codegraph()
        for reviewer in WORKFLOW.REQUIRED_REVIEWERS:
            self.write_review(reviewer)
        status = WORKFLOW.build_status(self.root, self.work_id)
        self.assertEqual(status["knowledge_gate"]["mode"], "fallback")
        self.assertEqual(status["stages"]["knowledge_gate"]["status"], "blocked")
        self.assertEqual(status["stages"]["review"]["status"], "blocked")
        self.assertIn(
            "AI-Spec",
            " ".join(status["stages"]["knowledge_gate"]["blockers"]),
        )
        self.assertFalse(status["stages"]["spec"]["can_advance"])

    def test_loaded_mode_without_sources_is_blocked(self) -> None:
        self.write_knowledge_gate(
            status="passed",
            mode="loaded",
            version="1.2.3",
            sources=[],
        )
        status = WORKFLOW.build_status(self.root, self.work_id)
        self.assertEqual(status["stages"]["knowledge_gate"]["status"], "blocked")

    def test_malformed_evidence_fails_closed(self) -> None:
        (self.work / "evidence" / "knowledge-gate.json").write_text(
            "{broken", encoding="utf-8"
        )
        status = WORKFLOW.build_status(self.root, self.work_id)
        self.assertEqual(status["stages"]["knowledge_gate"]["status"], "blocked")
        self.assertIn("JSON", " ".join(status["stages"]["knowledge_gate"]["blockers"]))

    def test_native_plan_tasks_expose_files_interfaces_and_steps(self) -> None:
        plan = self.write_plan(
            """
# Plan

### Task 1: 增加重试保护

**Files:**
- Modify: `internal/order/risk.go:40-70`
- Test: `internal/order/risk_test.go`

**Interfaces:**
- Produces: `shouldSkip(scene RiskScene) bool`

- [ ] **Step 1: 增加失败测试**

### Task 2: 增加指标

**Files:**
- Create: `internal/order/metric.go`

**Interfaces:**
- Consumes: `shouldSkip(scene RiskScene) bool`

- [ ] **Step 1: 增加指标**
"""
        )
        tasks = TASKS.parse_superpowers_plan(plan)
        self.assertEqual([task["number"] for task in tasks], [1, 2])
        self.assertEqual(
            tasks[0]["allowed_files"],
            ["internal/order/risk.go", "internal/order/risk_test.go"],
        )
        self.assertIn("shouldSkip", tasks[0]["interfaces"][0])
        self.assertEqual(tasks[0]["steps"][0]["title"], "增加失败测试")

    def test_scope_rejects_unrelated_staged_file(self) -> None:
        self.initialize_git()
        self.stage_file("internal/order/risk.go")
        self.stage_file("internal/order/unrelated.go")
        task = {"allowed_files": ["internal/order/risk.go"]}
        self.assertEqual(
            TASKS.validate_task_scope(self.root, task),
            ["internal/order/unrelated.go"],
        )

    def test_commit_message_is_conventional_chinese_and_task_scoped(self) -> None:
        message = TASKS.format_task_commit(
            self.work_id, 1, "feat", "增加内部重试判断"
        )
        self.assertEqual(
            message,
            "feat: 增加内部重试判断\n\noptimize-order-risk-check-task1",
        )
        with self.assertRaises(TASKS.TaskControlError):
            TASKS.format_task_commit(self.work_id, 1, "feature", "add retry")

    def test_advance_requires_remote_ut_and_cr_for_current_snapshot(self) -> None:
        self.initialize_git()
        plan = self.write_plan(
            """
### Task 1: 增加重试保护
**Files:**
- Modify: `internal/order/risk.go`
**Interfaces:**
- Produces: `shouldSkip(scene RiskScene) bool`
- [ ] **Step 1: 实现保护**
"""
        )
        self.write_global_prerequisites(plan)
        self.stage_file("internal/order/risk.go")
        version = WORKFLOW.build_status(self.root, self.work_id)["version"]
        with self.assertRaises(TASKS.TaskControlConflict):
            TASKS.advance_task(
                self.root,
                self.work_id,
                expected_version=version,
                expected_task=1,
                commit_type="feat",
                summary="增加内部重试判断",
            )

    def test_advance_commits_current_scope_then_unlocks_next_task(self) -> None:
        self.initialize_git()
        plan = self.write_plan(
            """
### Task 1: 增加重试保护
**Files:**
- Modify: `internal/order/risk.go`
**Interfaces:**
- Produces: `shouldSkip(scene RiskScene) bool`
- [ ] **Step 1: 实现保护**

### Task 2: 增加指标
**Files:**
- Create: `internal/order/metric.go`
**Interfaces:**
- Consumes: `shouldSkip(scene RiskScene) bool`
- [ ] **Step 1: 实现指标**
"""
        )
        self.write_global_prerequisites(plan)
        self.stage_file("internal/order/risk.go")
        self.write_task_evidence(1)
        version = WORKFLOW.build_status(self.root, self.work_id)["version"]
        result = TASKS.advance_task(
            self.root,
            self.work_id,
            expected_version=version,
            expected_task=1,
            commit_type="feat",
            summary="增加内部重试判断",
        )
        subject = subprocess.run(
            ["git", "log", "-1", "--pretty=%s"],
            cwd=self.root,
            check=True,
            text=True,
            capture_output=True,
        ).stdout.strip()
        body = subprocess.run(
            ["git", "log", "-1", "--pretty=%b"],
            cwd=self.root,
            check=True,
            text=True,
            capture_output=True,
        ).stdout.strip()
        self.assertEqual(subject, "feat: 增加内部重试判断")
        self.assertEqual(body.splitlines()[0], f"{self.work_id}-task1")
        self.assertEqual(result["completed_task"], 1)
        self.assertEqual(result["next_task"], 2)

    def test_continuous_mode_rejects_manual_advance(self) -> None:
        self.initialize_git()
        self.write_workflow(mode="continuous")
        plan = self.write_plan(
            """
### Task 1: 增加重试保护
**Files:**
- Modify: `internal/order/risk.go`
**Interfaces:**
- Produces: `shouldSkip(scene RiskScene) bool`
- [ ] **Step 1: 实现保护**
"""
        )
        self.write_global_prerequisites(plan)
        self.stage_file("internal/order/risk.go")
        self.write_task_evidence(1)
        version = WORKFLOW.build_status(self.root, self.work_id)["version"]
        with self.assertRaises(TASKS.TaskControlConflict):
            TASKS.advance_task(
                self.root,
                self.work_id,
                expected_version=version,
                expected_task=1,
                commit_type="feat",
                summary="增加内部重试判断",
            )

    def test_status_exposes_current_task_scope_and_advance_gate(self) -> None:
        self.initialize_git()
        plan = self.write_plan(
            """
### Task 1: 增加重试保护
**Files:**
- Modify: `internal/order/risk.go`
**Interfaces:**
- Produces: `shouldSkip(scene RiskScene) bool`
- [ ] **Step 1: 实现保护**

### Task 2: 增加指标
**Files:**
- Create: `internal/order/metric.go`
**Interfaces:**
- Consumes: `shouldSkip(scene RiskScene) bool`
- [ ] **Step 1: 实现指标**
"""
        )
        self.write_global_prerequisites(plan)
        self.stage_file("internal/order/risk.go")
        self.write_task_evidence(1)
        status = WORKFLOW.build_status(self.root, self.work_id)
        self.assertEqual(status["tasks_total"], 2)
        self.assertEqual(status["current_task"]["number"], 1)
        self.assertEqual(
            status["current_task"]["allowed_files"], ["internal/order/risk.go"]
        )
        self.assertTrue(status["current_task"]["can_advance"])

    def test_advance_rejects_when_global_plan_gate_is_blocked(self) -> None:
        self.initialize_git()
        self.write_plan(
            """
# Implementation Plan

### Task 1: 修改风险判断

**Files:**
- Modify: `internal/order/risk.go`

**Interfaces:**
- Produces: `shouldCheckRisk(scene RiskScene) bool`

- [ ] **Step 1: 实现风险判断**
"""
        )
        self.stage_file("internal/order/risk.go")
        self.write_task_evidence(1)
        version = TASKS.work_state_version(self.work)

        with self.assertRaises(TASKS.TaskControlConflict) as context:
            TASKS.advance_task(
                self.root,
                self.work_id,
                expected_version=version,
                expected_task=1,
                commit_type="feat",
                summary="增加风险判断",
            )

        self.assertIn("全局计划门禁", str(context.exception))

    def test_works_endpoint_and_work_query_replace_changes(self) -> None:
        another = self.root / ".superpowers" / "byted-work" / "add-audit-log"
        another.mkdir()
        self.write_json(
            another / "source.json",
            {
                "version": 1,
                "sha256": "b" * 64,
                "path": "technical-design.md",
                "updated_at": "2026-08-02T09:00:00+08:00",
            },
        )
        server = self.start_server()
        catalog = self.get_json(server, "/api/works")
        self.assertEqual(catalog["default_work"], self.work_id)
        self.assertEqual(
            [item["name"] for item in catalog["works"]],
            ["add-audit-log", self.work_id],
        )
        status = self.get_json(server, f"/api/status?work={self.work_id}")
        self.assertEqual(status["work"], self.work_id)

    def test_dashboard_cli_accepts_open_flag(self) -> None:
        with mock.patch.object(
            sys,
            "argv",
            ["serve_superpowers_dashboard.py", "--open", "--port", "0"],
        ):
            args = SERVER.parse_args()

        self.assertTrue(args.open_browser)
        self.assertEqual(args.port, 0)

    def test_dashboard_cli_uses_fixed_port_by_default(self) -> None:
        with mock.patch.object(sys, "argv", ["serve_superpowers_dashboard.py"]):
            args = SERVER.parse_args()
        self.assertEqual(args.port, 57171)

    def test_dashboard_opens_actual_bound_url(self) -> None:
        class FakeServer:
            server_address = ("127.0.0.1", 54321)

            def __init__(self) -> None:
                self.served = False
                self.closed = False

            def serve_forever(self) -> None:
                self.served = True

            def server_close(self) -> None:
                self.closed = True

        fake_server = FakeServer()
        args = argparse.Namespace(
            project=self.root,
            work=self.work_id,
            host="127.0.0.1",
            port=0,
            open_browser=True,
        )
        output = io.StringIO()
        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch.object(SERVER, "parse_args", return_value=args))
            stack.enter_context(
                mock.patch.object(
                    SERVER, "ThreadingHTTPServer", return_value=fake_server
                )
            )
            browser_open = stack.enter_context(
                mock.patch("webbrowser.open", return_value=True)
            )
            stack.enter_context(contextlib.redirect_stdout(output))
            SERVER.main()

        browser_open.assert_called_once_with("http://127.0.0.1:54321/", new=2)
        self.assertIn(
            "Superpowers dashboard: http://127.0.0.1:54321/", output.getvalue()
        )
        self.assertTrue(fake_server.served)
        self.assertTrue(fake_server.closed)

    def test_dashboard_keeps_serving_when_browser_open_fails(self) -> None:
        class FakeServer:
            server_address = ("127.0.0.1", 54322)

            def __init__(self) -> None:
                self.served = False
                self.closed = False

            def serve_forever(self) -> None:
                self.served = True

            def server_close(self) -> None:
                self.closed = True

        fake_server = FakeServer()
        args = argparse.Namespace(
            project=self.root,
            work=self.work_id,
            host="127.0.0.1",
            port=0,
            open_browser=True,
        )
        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch.object(SERVER, "parse_args", return_value=args))
            stack.enter_context(
                mock.patch.object(
                    SERVER, "ThreadingHTTPServer", return_value=fake_server
                )
            )
            stack.enter_context(
                mock.patch("webbrowser.open", side_effect=RuntimeError("no browser"))
            )
            stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            try:
                SERVER.main()
            except RuntimeError as error:
                self.fail(f"browser failure escaped dashboard startup: {error}")

        self.assertTrue(fake_server.served)
        self.assertTrue(fake_server.closed)

    def test_document_endpoint_reads_only_selected_work_artifacts(self) -> None:
        server = self.start_server()
        relative = f".superpowers/byted-work/{self.work_id}/technical-design.md"
        encoded = urllib.parse.quote(relative)
        payload = self.get_json(
            server, f"/api/document?work={self.work_id}&path={encoded}"
        )
        self.assertEqual(payload["content"], self.source_text)
        host, port = server.server_address
        with self.assertRaises(urllib.error.HTTPError) as context:
            urllib.request.urlopen(
                f"http://{host}:{port}/api/document?work={self.work_id}&path=../../outside",
                timeout=3,
            )
        self.assertEqual(context.exception.code, 400)

    def test_control_endpoint_switches_mode_with_state_version(self) -> None:
        server = self.start_server()
        before = self.get_json(server, f"/api/status?work={self.work_id}")
        code, payload = self.post_json(
            server,
            "/api/control",
            {
                "action": "set-mode",
                "work": self.work_id,
                "mode": "continuous",
                "expected_version": before["version"],
                "idempotency_key": "mode-1",
            },
        )
        self.assertEqual(code, 200)
        self.assertEqual(payload["mode"], "continuous")
        self.assertEqual(
            self.get_json(server, f"/api/status?work={self.work_id}")["mode"],
            "continuous",
        )

    def test_control_endpoint_replays_same_idempotency_key_without_conflict(self) -> None:
        server = self.start_server()
        before = self.get_json(server, f"/api/status?work={self.work_id}")
        request = {
            "action": "set-mode",
            "work": self.work_id,
            "mode": "continuous",
            "expected_version": before["version"],
            "idempotency_key": "mode-replay-1",
        }
        first_code, first = self.post_json(server, "/api/control", request)
        second_code, second = self.post_json(server, "/api/control", request)

        self.assertEqual(first_code, 200)
        self.assertEqual(second_code, 200)
        self.assertEqual(second["mode"], "continuous")
        self.assertEqual(second["version"], first["version"])

    def test_stale_control_write_returns_conflict(self) -> None:
        server = self.start_server()
        host, port = server.server_address
        request = urllib.request.Request(
            f"http://{host}:{port}/api/control",
            data=json.dumps(
                {
                    "action": "set-mode",
                    "work": self.work_id,
                    "mode": "continuous",
                    "expected_version": "stale",
                    "idempotency_key": "mode-stale",
                }
            ).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self.assertRaises(urllib.error.HTTPError) as context:
            urllib.request.urlopen(request, timeout=3)
        self.assertEqual(context.exception.code, 409)

    def test_sse_emits_initial_and_updated_work_status(self) -> None:
        server = self.start_server()
        host, port = server.server_address
        response = urllib.request.urlopen(
            f"http://{host}:{port}/events?work={self.work_id}", timeout=4
        )
        self.addCleanup(response.close)
        initial = read_sse_event(response)
        self.assertEqual(initial["work"], self.work_id)
        self.write_source(version=2, content="# 更新后的技术方案\n")
        updated = read_sse_event(response)
        self.assertEqual(updated["source"]["version"], 2)

    def test_event_signature_is_stable_without_source_changes(self) -> None:
        before_signature, _ = SERVER.event_payload(self.root, self.work_id)
        time.sleep(0.01)
        after_signature, _ = SERVER.event_payload(self.root, self.work_id)
        self.assertEqual(before_signature, after_signature)

    def test_static_dashboard_uses_development_work_and_task_navigation(self) -> None:
        javascript = (SKILL_DIR / "assets" / "dashboard" / "app.js").read_text(
            encoding="utf-8"
        )
        html = (SKILL_DIR / "assets" / "dashboard" / "index.html").read_text(
            encoding="utf-8"
        )
        styles = (SKILL_DIR / "assets" / "dashboard" / "styles.css").read_text(
            encoding="utf-8"
        )
        self.assertIn('new EventSource(apiUrl("/events", { work }))', javascript)
        self.assertIn('fetch("/api/works"', javascript)
        self.assertIn("开发任务", javascript)
        self.assertIn("风险点", javascript)
        self.assertIn("推进下一个任务", javascript)
        self.assertIn('data.mode !== "continuous"', javascript)
        self.assertIn('id="work-select"', javascript)
        self.assertIn("task-nav", styles)
        self.assertIn("<title>cosh 验收观察版</title>", html)
        self.assertNotIn("change-select", javascript)

    def test_overview_renders_vertical_stepper_and_switches_details_without_writes(
        self,
    ) -> None:
        javascript = (SKILL_DIR / "assets" / "dashboard" / "app.js").read_text(
            encoding="utf-8"
        )
        runner = (
            """
const appNode = { innerHTML: "" };
let stageClick = null;
globalThis.document = {
  querySelector: selector => selector === "#app" ? appNode : null,
  querySelectorAll: () => [],
};
globalThis.window = {
  location: new URL("file:///dashboard/index.html?tab=overview"),
  history: { replaceState: () => {} },
};
"""
            + javascript
            + """
const initialHtml = appNode.innerHTML;
document.querySelectorAll = selector => selector === "[data-overview-stage]" ? [{
  dataset: { overviewStage: "source" },
  addEventListener: (_event, handler) => { stageClick = handler; },
}] : [];
updateControl = () => { throw new Error("overview selection must remain read-only"); };
render(sampleData);
stageClick();
console.log(JSON.stringify({ initialHtml, selectedHtml: appNode.innerHTML }));
"""
        )
        result = subprocess.run(
            ["node", "-"], input=runner, text=True, capture_output=True, check=False
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        rendered = json.loads(result.stdout)
        self.assertIn('class="overview-workflow"', rendered["initialHtml"])
        self.assertIn('aria-current="step"', rendered["initialHtml"])
        self.assertIn("security Reviewer 未通过", rendered["initialHtml"])
        self.assertIn("技术文档", rendered["selectedHtml"])
        self.assertIn("允许继续", rendered["selectedHtml"])

    def test_overview_uses_stage_progress_until_plan_has_tasks(self) -> None:
        javascript = (SKILL_DIR / "assets" / "dashboard" / "app.js").read_text(
            encoding="utf-8"
        )
        runner = (
            """
const appNode = { innerHTML: "" };
globalThis.document = {
  querySelector: selector => selector === "#app" ? appNode : null,
  querySelectorAll: () => [],
};
globalThis.window = {
  location: new URL("file:///dashboard/index.html?tab=overview"),
  history: { replaceState: () => {} },
};
"""
            + javascript
            + """
const data = {
  ...sampleData,
  tasks_total: 0,
  tasks_done: 0,
  tasks: [],
  current_task: null,
  primary_progress: { kind: "reviewers", label: "Reviewer", done: 2, total: 3 },
};
console.log(renderOverview(data));
"""
        )
        result = subprocess.run(
            ["node", "-"], input=runner, text=True, capture_output=True, check=False
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Reviewer 2 / 3", result.stdout)
        self.assertNotIn("Task 0 / 0", result.stdout)

    def test_review_renders_legacy_fields_and_marks_missing_evidence(self) -> None:
        javascript = (SKILL_DIR / "assets" / "dashboard" / "app.js").read_text(
            encoding="utf-8"
        )
        runner = (
            """
const appNode = { innerHTML: "" };
globalThis.document = {
  querySelector: selector => selector === "#app" ? appNode : null,
  querySelectorAll: () => [],
};
globalThis.window = {
  location: new URL("file:///dashboard/index.html?tab=review"),
  history: { replaceState: () => {} },
};
"""
            + javascript
            + """
const data = {
  ...sampleData,
  reviews: {
    ...sampleData.reviews,
    findings: [{
      reviewer: "security",
      id: "SEC-R3-01",
      severity: "P1",
      problem: "目标 FG 权限尚未完成验收",
      suggestion: "补齐权限和审计证据",
      schema_errors: ["缺少 evidence"],
    }],
  },
};
console.log(renderReview(data));
"""
        )
        result = subprocess.run(
            ["node", "-"], input=runner, text=True, capture_output=True, check=False
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("目标 FG 权限尚未完成验收", result.stdout)
        self.assertIn("补齐权限和审计证据", result.stdout)
        self.assertIn("未提供（评审证据格式不完整）", result.stdout)

    def test_archive_is_local_gitignored_and_evidence_based(self) -> None:
        self.write_json(
            self.work / "evidence" / "conversation.json",
            {
                "total_turns": 18,
                "observed_turns": 18,
                "coverage": "完整任务会话",
                "stage_turns": {"review": 11, "implementation": 7},
            },
        )
        self.write_json(
            self.work / "evidence" / "interaction-events.json",
            {
                "events": [
                    {
                        "category": "需求或技术方案歧义",
                        "round": 3,
                        "evidence": "用户将修改点纠正为风险点",
                    },
                    {
                        "category": "评审发现风险",
                        "round": 8,
                        "evidence": "SEC5 发现日志脱敏缺口",
                    },
                ]
            },
        )
        self.write_json(
            self.work / "evidence" / "rule-candidates.json",
            {
                "rules": [
                    {
                        "rule": "评审问题统一命名为风险点",
                        "evidence": "第 3 轮术语修正",
                        "benefit": "减少领域含义误解",
                        "scope": "字节技术方案评审",
                        "confidence": "high",
                        "target": "references/byted-admission-review.md",
                    }
                ]
            },
        )
        path = ARCHIVE.archive_work(self.root, self.work_id, "manual")
        content = path.read_text(encoding="utf-8")
        self.assertEqual(path.parent.name, self.work_id)
        self.assertIn("## 会话轮次与覆盖范围", content)
        self.assertIn("完整轮数：18", content)
        self.assertIn("## 为什么需要多轮讨论", content)
        self.assertIn("SEC5 发现日志脱敏缺口", content)
        self.assertIn("## 可蒸馏规则候选", content)
        self.assertIn("评审问题统一命名为风险点", content)
        self.assertTrue(ARCHIVE.is_archive_ignored(self.root))

    def test_unknown_chat_turns_are_not_estimated(self) -> None:
        self.write_json(
            self.work / "evidence" / "conversation.json",
            {
                "total_turns": None,
                "observed_turns": 7,
                "coverage": "skill 启动后",
            },
        )
        path = ARCHIVE.archive_work(self.root, self.work_id, "manual")
        content = path.read_text(encoding="utf-8")
        self.assertIn("完整轮数：未知", content)
        self.assertIn("已观测轮数：7", content)
        self.assertIn("覆盖范围：skill 启动后", content)

    def test_archive_redacts_sensitive_values(self) -> None:
        self.write_json(
            self.work / "evidence" / "interaction-events.json",
            {
                "events": [
                    {
                        "category": "测试失败",
                        "round": 9,
                        "evidence": "Authorization: Bearer very-secret-token",
                        "password": "do-not-archive",
                    }
                ]
            },
        )
        path = ARCHIVE.archive_work(self.root, self.work_id, "manual")
        content = path.read_text(encoding="utf-8")
        self.assertNotIn("very-secret-token", content)
        self.assertNotIn("do-not-archive", content)
        self.assertIn("[REDACTED]", content)

    def test_manual_archive_control_returns_archive_document(self) -> None:
        server = self.start_server()
        before = self.get_json(server, f"/api/status?work={self.work_id}")
        _, payload = self.post_json(
            server,
            "/api/control",
            {
                "action": "archive",
                "work": self.work_id,
                "expected_version": before["version"],
                "idempotency_key": "archive-1",
            },
        )
        self.assertEqual(payload["stages"]["archive"]["status"], "passed")
        self.assertTrue(payload["archive"]["path"].endswith("-retrospective.md"))

    def test_push_evidence_triggers_archive_once(self) -> None:
        self.write_json(
            self.work / "evidence" / "push.json",
            {
                "status": "passed",
                "code_sha": "head-sha",
                "remote": "origin",
                "updated_at": "2026-08-02T16:00:00+08:00",
            },
        )
        first = ARCHIVE.archive_after_push(self.root, self.work_id)
        second = ARCHIVE.archive_after_push(self.root, self.work_id)
        self.assertIsNotNone(first)
        self.assertEqual(first, second)
        archives = list(
            (self.root / ".superpowers" / "byted-archive" / self.work_id).glob(
                "*-retrospective.md"
            )
        )
        self.assertEqual(len(archives), 1)

    def prepare_completed_implementation(self) -> str:
        self.initialize_git()
        plan = self.write_plan(
            """
### Task 1: 增加重试保护
**Files:**
- Modify: `internal/order/risk.go`
**Interfaces:**
- Produces: `shouldSkip(scene RiskScene) bool`
- [x] **Step 1: 实现保护**
"""
        )
        self.write_global_prerequisites(plan)
        head = self.git_head()
        self.write_json(
            self.work / "evidence" / "commit-task1.json",
            {"status": "passed", "task": 1, "commit_sha": head},
        )
        return head

    def write_final_remote_ut(self, code_sha: str, prepare_only: bool = False) -> None:
        self.write_json(
            self.work / "evidence" / "remote-ut-final.json",
            {
                "status": "passed",
                "code_sha": code_sha,
                "prepare_only": prepare_only,
                "meta": {"remote": {"run_success": True}},
                "summary": {
                    "has_failures": False,
                    "failed_packages": 0,
                    "failed_tests": 0,
                },
                "updated_at": "2026-08-02T15:00:00+08:00",
            },
        )

    def write_final_review(self, code_sha: str) -> None:
        self.write_json(
            self.work / "evidence" / "final-review.json",
            {
                "status": "passed",
                "code_sha": code_sha,
                "blocking_findings": [],
                "updated_at": "2026-08-02T15:10:00+08:00",
            },
        )

    def test_push_requires_current_head_remote_ut_and_final_review(self) -> None:
        head = self.prepare_completed_implementation()
        self.write_final_remote_ut("stale-sha")
        self.write_final_review(head)
        status = WORKFLOW.build_status(self.root, self.work_id)
        self.assertEqual(status["stages"]["remote_ut"]["status"], "blocked")
        self.assertFalse(status["stages"]["push"]["can_advance"])
        self.assertIn("代码 SHA", " ".join(status["stages"]["remote_ut"]["blockers"]))

    def test_prepare_only_remote_ut_cannot_pass(self) -> None:
        head = self.prepare_completed_implementation()
        self.write_final_remote_ut(head, prepare_only=True)
        status = WORKFLOW.build_status(self.root, self.work_id)
        self.assertEqual(status["stages"]["remote_ut"]["status"], "blocked")
        self.assertIn("PREPARE_ONLY", " ".join(status["stages"]["remote_ut"]["blockers"]))

    def test_push_gate_passes_only_after_current_evidence_and_push_record(self) -> None:
        head = self.prepare_completed_implementation()
        self.write_final_remote_ut(head)
        self.write_final_review(head)
        ready = WORKFLOW.build_status(self.root, self.work_id)
        self.assertTrue(ready["stages"]["push"]["can_advance"])
        self.assertNotEqual(ready["stages"]["push"]["status"], "passed")
        self.write_json(
            self.work / "evidence" / "push.json",
            {
                "status": "passed",
                "code_sha": head,
                "remote": "origin",
                "updated_at": "2026-08-02T15:30:00+08:00",
            },
        )
        pushed = WORKFLOW.build_status(self.root, self.work_id)
        self.assertEqual(pushed["stages"]["push"]["status"], "passed")


if __name__ == "__main__":
    unittest.main()
