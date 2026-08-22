from __future__ import annotations

import importlib.util
import contextlib
import hashlib
import io
import json
import pathlib
import subprocess
import tempfile
import threading
import unittest
import urllib.request
import urllib.parse
from unittest import mock
from http.server import ThreadingHTTPServer


ROOT = pathlib.Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skills" / "cosh-hammer"
STATE_SCRIPT = SKILL_DIR / "scripts" / "cosh_hammer_state.py"
SERVER_SCRIPT = SKILL_DIR / "scripts" / "serve_cosh_hammer_dashboard.py"
STARTER_SCRIPT = SKILL_DIR / "scripts" / "start_cosh_hammer_dashboard.py"
FORMATTER_SCRIPT = SKILL_DIR / "assets" / "dashboard" / "artifact-formatters.js"


def load_module(name: str, path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CoshHammerSkillTest(unittest.TestCase):
    def test_skill_contract_keeps_hammer_as_unmodified_main_workflow(self) -> None:
        skill = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        metadata = (SKILL_DIR / "agents" / "openai.yaml").read_text(encoding="utf-8")
        self.assertIn("name: cosh-hammer", skill)
        self.assertIn("$cosh-hammer", metadata)
        self.assertIn("Hammer 是唯一主流程", skill)
        self.assertIn("不得修改 Hammer", skill)
        self.assertIn("不得写入 `.hammer/`", skill)
        self.assertIn("不得启动、嵌入或依赖 Hammer 自带观察板", skill)
        self.assertIn("入口模式", skill)
        self.assertIn("编码模式", skill)
        self.assertIn("CodeGraph", skill)
        self.assertIn("预计修改面", skill)
        self.assertIn("DONE", skill)
        self.assertIn("BLOCKED", skill)
        self.assertIn("远程 UT", skill)
        self.assertIn("E2E", skill)

    def test_direct_resources_exist(self) -> None:
        for relative in (
            "references/workflow.md",
            "references/hammer-contract.md",
            "references/handoff-gates.md",
            "references/coding-artifacts.md",
            "references/realtime-dashboard.md",
            "references/major-decisions.md",
            "scripts/cosh_hammer_state.py",
            "scripts/serve_cosh_hammer_dashboard.py",
            "scripts/start_cosh_hammer_dashboard.py",
            "assets/dashboard/index.html",
            "assets/dashboard/artifact-formatters.js",
            "assets/dashboard/app.js",
            "assets/dashboard/styles.css",
        ):
            self.assertTrue((SKILL_DIR / relative).is_file(), relative)

    def run_formatter(self, expression: str):
        script = (
            f"const formatter = require({json.dumps(str(FORMATTER_SCRIPT))});"
            f"process.stdout.write(JSON.stringify({expression}));"
        )
        result = subprocess.run(
            ["node", "-e", script],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_markdown_formatter_returns_structured_reading_blocks(self) -> None:
        value = self.run_formatter(
            "formatter.present('design.md', '# 标题\\n\\n- 第一项\\n- 第二项\\n\\n```go\\nfmt.Println(1)\\n```')"
        )

        self.assertEqual(value["kind"], "markdown")
        self.assertEqual(
            value["blocks"],
            [
                {"type": "heading", "level": 1, "text": "标题"},
                {"type": "list", "ordered": False, "items": ["第一项", "第二项"]},
                {"type": "code", "language": "go", "text": "fmt.Println(1)"},
            ],
        )

    def test_markdown_formatter_recognizes_frontmatter_quotes_and_tables(self) -> None:
        value = self.run_formatter(
            "formatter.present('review.md', '---\\nstatus: passed\\n---\\n\\n> 风险已闭环\\n\\n| 项目 | 结果 |\\n| --- | --- |\\n| UT | passed |')"
        )

        self.assertEqual(
            value["blocks"],
            [
                {"type": "frontmatter", "text": "status: passed"},
                {"type": "quote", "text": "风险已闭环"},
                {
                    "type": "table",
                    "headers": ["项目", "结果"],
                    "rows": [["UT", "passed"]],
                },
            ],
        )

    def test_json_formatter_preserves_value_types_for_tree_view(self) -> None:
        value = self.run_formatter(
            "formatter.present('state.json', '{\"ok\":true,\"count\":2,\"items\":[null,\"x\"]}')"
        )

        self.assertEqual(value["kind"], "json")
        self.assertEqual(
            value["value"],
            {"ok": True, "count": 2, "items": [None, "x"]},
        )

    def test_artifact_overlay_only_closes_for_backdrop_click(self) -> None:
        value = self.run_formatter(
            "[formatter.isBackdropClick('overlay', 'overlay'), formatter.isBackdropClick('panel', 'overlay')]"
        )

        self.assertEqual(value, [True, False])


class CoshHammerStateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.state = load_module("cosh_hammer_state", STATE_SCRIPT)
        cls.server = load_module("serve_cosh_hammer_dashboard", SERVER_SCRIPT)
        cls.starter = load_module("start_cosh_hammer_dashboard", STARTER_SCRIPT)

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.project = pathlib.Path(self.temp.name) / "repo"
        self.project.mkdir()
        self.hammer_root = pathlib.Path(self.temp.name) / "hammer"
        self.hammer_root.mkdir()
        (self.hammer_root / "SKILL.md").write_text("---\nname: hammer\n---\n", encoding="utf-8")
        plan = self.project / ".hammer" / "plan"
        plan.mkdir(parents=True)
        (plan / "session.md").write_text(
            "# Hammer Plan Session\n\n- current_stage: plan-orchestration\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def hammer_snapshot(self) -> dict[str, bytes]:
        root = self.project / ".hammer"
        return {
            str(path.relative_to(root)): path.read_bytes()
            for path in root.rglob("*")
            if path.is_file()
        }

    def create_linked_worktree(self, name: str) -> pathlib.Path:
        subprocess.run(["git", "init", "-q", str(self.project)], check=True)
        subprocess.run(
            ["git", "-C", str(self.project), "config", "user.name", "Cosh Test"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(self.project), "config", "user.email", "cosh@example.com"],
            check=True,
        )
        (self.project / "tracked.txt").write_text("base\n", encoding="utf-8")
        subprocess.run(
            ["git", "-C", str(self.project), "add", "tracked.txt"], check=True
        )
        subprocess.run(
            ["git", "-C", str(self.project), "commit", "-qm", "base"], check=True
        )
        target = pathlib.Path(self.temp.name) / name
        subprocess.run(
            [
                "git",
                "-C",
                str(self.project),
                "worktree",
                "add",
                "-qb",
                name,
                str(target),
            ],
            check=True,
        )
        return target

    def dashboard_payload(self, *, active_project: pathlib.Path | None = None, stale: bool = False):
        return {
            "healthz": {
                "status": "ready",
                "project": str(self.project.resolve()),
                "work": "handoff-work",
                "port": 57172,
            },
            "status": {
                "stale": stale,
                "project": str(self.project.resolve()),
                "work": "handoff-work",
                "active_project": str((active_project or self.project).resolve()),
            },
        }

    def write_ready_plan(
        self,
        root: pathlib.Path,
        *,
        include_trigger: bool = True,
        task_count: int = 1,
    ) -> pathlib.Path:
        plan_dir = root / ".hammer" / "plan"
        plan_dir.mkdir(parents=True, exist_ok=True)
        trigger = (
            "\nUse $cosh-hammer in coding mode for this Hammer parent task.\n"
            if include_trigger
            else "\n"
        )
        plan = plan_dir / "plan.md"
        blocks = []
        for number in range(1, task_count + 1):
            blocks.append(
                f"## {number}. 实现订单校验 {number}（默认能力，coding）\n"
                f"{trigger}"
                "### Checklist\n\n- [ ] 实现代码与测试\n"
            )
        plan.write_text("# Plan\n\n" + "\n".join(blocks), encoding="utf-8")
        digest = hashlib.sha256(plan.read_bytes()).hexdigest()
        (plan_dir / "handoff.json").write_text(
            json.dumps(
                {
                    "status": "passed",
                    "plan_sha256": digest,
                    "mode": "inline",
                    "review_triggers": [],
                    "evidence": {
                        "plan_lint": "passed",
                        "inline_checks": {
                            name: {"status": "passed", "evidence": ["fixture evidence"]}
                            for name in (
                                "ac_task_test_mapping",
                                "external_dependencies",
                                "task_dependencies",
                                "task_executability",
                                "risk_classification",
                            )
                        },
                        "review": None,
                    },
                }
            ),
            encoding="utf-8",
        )
        return plan

    def initialize_coding_work(self, work_id: str = "coding-work") -> pathlib.Path:
        self.state.initialize_launch(
            self.project,
            work_id=work_id,
            refined_requirement="由 Cosh 接管 Hammer 编码任务。",
            source={"kind": "text", "value": "接管编码"},
            hammer_root=self.hammer_root,
        )
        coding = self.project / ".cosh" / "hammer-plugin" / work_id / "coding"
        coding.mkdir(parents=True, exist_ok=True)
        for name in ("code-facts.json", "change-surface.json", "locations.json"):
            (coding / name).write_text('{"status":"passed"}\n', encoding="utf-8")
        (coding / "implementation-plan.md").write_text(
            "# Implementation Plan\n\n拆分并实现当前 Hammer 父任务。\n",
            encoding="utf-8",
        )
        return coding

    def coding_task_spec(self) -> dict:
        return {
            "tasks": [
                {
                    "id": "H1-S1",
                    "hammer_parent": "Task 1",
                    "title": "实现核心逻辑",
                    "description": "按现有调用链实现核心逻辑并保持兼容。",
                    "expected_files": ["service.go"],
                    "symbols": ["OrderService.Check"],
                    "steps": ["核对现状", "实现最小改动", "记录验证证据"],
                    "dependencies": [],
                    "acceptance": ["核心路径通过"],
                },
                {
                    "id": "H1-S2",
                    "hammer_parent": "Task 1",
                    "title": "补齐测试",
                    "description": "补齐核心路径和失败路径的测试。",
                    "expected_files": ["service_test.go"],
                    "symbols": ["TestOrderServiceCheck"],
                    "steps": ["补测试用例", "运行目标测试", "记录结果"],
                    "dependencies": ["H1-S1"],
                    "acceptance": ["测试覆盖通过"],
                },
            ]
        }

    def detailed_task(
        self,
        task_id: str,
        hammer_parent: str,
        *,
        dependencies: list[str],
        expected_file: str | None = None,
    ) -> dict:
        return {
            "id": task_id,
            "hammer_parent": hammer_parent,
            "title": f"实现 {task_id}",
            "description": f"基于源码事实完成 {task_id} 并保持现有行为兼容。",
            "expected_files": [expected_file or f"{task_id}.go"],
            "symbols": [f"{task_id}.Run"],
            "steps": ["核对源码事实", "实现最小改动", "运行验收测试"],
            "dependencies": dependencies,
            "acceptance": [f"{task_id} 验收通过"],
        }

    def global_coding_task_spec(self) -> dict:
        return {
            "tasks": [
                self.detailed_task("task1-fg", "Task 1", dependencies=[]),
                self.detailed_task(
                    "task1-tcc", "Task 1", dependencies=["task1-fg"]
                ),
                self.detailed_task(
                    "task2-query", "Task 2", dependencies=["task1-tcc"]
                ),
                self.detailed_task(
                    "task3-consumer", "Task 3", dependencies=["task2-query"]
                ),
            ]
        }

    def initialize_git_repository(self) -> str:
        subprocess.run(["git", "init", "-q", str(self.project)], check=True)
        subprocess.run(
            ["git", "-C", str(self.project), "config", "user.name", "Cosh Test"],
            check=True,
        )
        subprocess.run(
            [
                "git",
                "-C",
                str(self.project),
                "config",
                "user.email",
                "cosh@example.com",
            ],
            check=True,
        )
        (self.project / "base.txt").write_text("base\n", encoding="utf-8")
        subprocess.run(
            ["git", "-C", str(self.project), "add", "base.txt"], check=True
        )
        subprocess.run(
            ["git", "-C", str(self.project), "commit", "-qm", "base"], check=True
        )
        return self.git("rev-parse", "HEAD")

    def git(self, *args: str) -> str:
        return subprocess.run(
            ["git", "-C", str(self.project), *args],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

    def activate_global_delivery_work(self, work_id: str) -> pathlib.Path:
        coding = self.initialize_coding_work(work_id)
        gate = {
            "status": "passed",
            "plan_sha256": "plan-sha",
            "coding_tasks": ["Task 1", "Task 2", "Task 3"],
            "active_project": str(self.project.resolve()),
        }
        with mock.patch.object(self.state, "verify_coding", return_value=gate):
            self.state.activate_coding(
                self.project, work_id, "Task 1", self.global_coding_task_spec()
            )
        (coding / "control.json").write_text(
            json.dumps({"mode": "continuous"}), encoding="utf-8"
        )
        return coding

    def complete_global_delivery_tasks(self, work_id: str) -> tuple[pathlib.Path, list[str]]:
        coding = self.activate_global_delivery_work(work_id)
        gate = {
            "status": "passed",
            "plan_sha256": "plan-sha",
            "coding_tasks": ["Task 1", "Task 2", "Task 3"],
            "active_project": str(self.project.resolve()),
        }
        commits = []
        with mock.patch.object(self.state, "verify_handoff", return_value=gate):
            for task in self.global_coding_task_spec()["tasks"]:
                task_id = task["id"]
                self.state.begin_subtask(self.project, work_id, task_id)
                delivery = self.project / task["expected_files"][0]
                delivery.write_text(
                    f"package delivery\n// {work_id}:{task_id}\n", encoding="utf-8"
                )
                self.git("add", task["expected_files"][0])
                result = self.state.complete_subtask(
                    self.project,
                    work_id,
                    task_id,
                    status="passed",
                    evidence={"acceptance": "passed"},
                )
                commits.append(result["commit_sha"])
        return coding, commits

    def test_preflight_fails_closed_when_dashboard_is_unavailable(self) -> None:
        self.assertTrue(hasattr(self.state, "run_preflight"), "缺少 preflight 硬门")
        self.state.initialize_launch(
            self.project,
            work_id="handoff-work",
            refined_requirement="接管 Hammer 编码任务。",
            source={"kind": "text", "value": "接管编码任务"},
            hammer_root=self.hammer_root,
        )
        with mock.patch.object(
            self.state, "_dashboard_payload", side_effect=OSError("connection refused")
        ):
            with self.assertRaisesRegex(self.state.CoshHammerError, "观察板"):
                self.state.run_preflight(self.project, "handoff-work")

    def test_preflight_rejects_project_or_work_mismatch(self) -> None:
        self.state.initialize_launch(
            self.project,
            work_id="handoff-work",
            refined_requirement="接管 Hammer 编码任务。",
            source={"kind": "text", "value": "接管编码任务"},
            hammer_root=self.hammer_root,
        )
        payload = self.dashboard_payload()
        payload["healthz"]["work"] = "another-work"
        with mock.patch.object(
            self.state, "_dashboard_payload", side_effect=lambda _project, _work, endpoint: payload[endpoint]
        ):
            with self.assertRaisesRegex(self.state.CoshHammerError, "project/work"):
                self.state.run_preflight(self.project, "handoff-work")

    def test_preflight_fails_closed_without_initialized_cosh_work(self) -> None:
        with self.assertRaisesRegex(self.state.CoshHammerError, "launch"):
            self.state.run_preflight(self.project, "missing-cosh-work")

    def test_verify_handoff_blocks_plan_missing_cosh_trigger(self) -> None:
        self.assertTrue(hasattr(self.state, "verify_handoff"), "缺少 Plan→Execute 硬门")
        self.state.initialize_launch(
            self.project,
            work_id="handoff-work",
            refined_requirement="接管 Hammer 编码任务。",
            source={"kind": "text", "value": "接管编码任务"},
            hammer_root=self.hammer_root,
        )
        self.write_ready_plan(self.project, include_trigger=False)
        payload = self.dashboard_payload()
        with mock.patch.object(
            self.state, "_dashboard_payload", side_effect=lambda _project, _work, endpoint: payload[endpoint]
        ):
            with self.assertRaisesRegex(self.state.CoshHammerError, "触发语句"):
                self.state.verify_handoff(self.project, "handoff-work")

    def test_verify_handoff_rejects_incomplete_plan_ready_evidence(self) -> None:
        self.state.initialize_launch(
            self.project,
            work_id="handoff-work",
            refined_requirement="接管 Hammer 编码任务。",
            source={"kind": "text", "value": "接管编码任务"},
            hammer_root=self.hammer_root,
        )
        self.write_ready_plan(self.project)
        handoff = self.project / ".hammer" / "plan" / "handoff.json"
        value = json.loads(handoff.read_text(encoding="utf-8"))
        value["evidence"] = {"plan_lint": "passed"}
        handoff.write_text(json.dumps(value), encoding="utf-8")
        payload = self.dashboard_payload()
        with mock.patch.object(
            self.state, "_dashboard_payload", side_effect=lambda _project, _work, endpoint: payload[endpoint]
        ):
            with self.assertRaisesRegex(self.state.CoshHammerError, "evidence"):
                self.state.verify_handoff(self.project, "handoff-work")

    def test_verify_handoff_follows_registered_hammer_worktree(self) -> None:
        self.assertTrue(hasattr(self.state, "verify_handoff"), "缺少 Plan→Execute 硬门")
        self.state.initialize_launch(
            self.project,
            work_id="handoff-work",
            refined_requirement="接管迁移后的 Hammer 编码任务。",
            source={"kind": "text", "value": "接管迁移后的编码任务"},
            hammer_root=self.hammer_root,
            worktree_policy="open",
        )
        target = self.create_linked_worktree("handoff-target")
        self.write_ready_plan(target)
        target_design = target / ".hammer" / "design"
        target_design.mkdir(parents=True)
        (target_design / "session.md").write_text(
            "# Design\n\n- current_stage: complete\n", encoding="utf-8"
        )
        design = self.project / ".hammer" / "design"
        design.mkdir(parents=True, exist_ok=True)
        (design / "session.md").write_text(
            "# Design\n\n## 审计日志\n\n"
            f"- 2026-08-21 10:00:00 +0800 | workspace.worktree decision=migrated_away path={target}\n",
            encoding="utf-8",
        )
        payload = self.dashboard_payload(active_project=target)
        with mock.patch.object(
            self.state, "_dashboard_payload", side_effect=lambda _project, _work, endpoint: payload[endpoint]
        ):
            result = self.state.verify_handoff(self.project, "handoff-work")

        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["active_project"], str(target.resolve()))
        self.assertEqual(result["coding_tasks"], ["Task 1"])

    def test_verify_coding_rejects_execute_task_mismatch(self) -> None:
        self.assertTrue(hasattr(self.state, "verify_coding"), "缺少编码模式二次验真")
        self.state.initialize_launch(
            self.project,
            work_id="handoff-work",
            refined_requirement="接管 Hammer 编码任务。",
            source={"kind": "text", "value": "接管编码任务"},
            hammer_root=self.hammer_root,
        )
        self.write_ready_plan(self.project)
        execute = self.project / ".hammer" / "execute"
        execute.mkdir()
        (execute / "session.md").write_text(
            "# Execute\n\n- current_stage: Coding Tasks\n"
            "- current_task_ref: Task 2\n- next_action: run-step-4\n- blocker: none\n",
            encoding="utf-8",
        )
        payload = self.dashboard_payload()
        with mock.patch.object(
            self.state, "_dashboard_payload", side_effect=lambda _project, _work, endpoint: payload[endpoint]
        ):
            with self.assertRaisesRegex(self.state.CoshHammerError, "不一致"):
                self.state.verify_coding(self.project, "handoff-work", "Task 1")

    def test_verify_coding_rejects_stale_dashboard(self) -> None:
        self.assertTrue(hasattr(self.state, "verify_coding"), "缺少编码模式二次验真")
        self.state.initialize_launch(
            self.project,
            work_id="handoff-work",
            refined_requirement="接管 Hammer 编码任务。",
            source={"kind": "text", "value": "接管编码任务"},
            hammer_root=self.hammer_root,
        )
        self.write_ready_plan(self.project)
        execute = self.project / ".hammer" / "execute"
        execute.mkdir()
        (execute / "session.md").write_text(
            "# Execute\n\n- current_stage: Coding Tasks\n"
            "- current_task_ref: Task 1\n- next_action: run-step-4\n- blocker: none\n",
            encoding="utf-8",
        )
        payload = self.dashboard_payload(stale=True)
        with mock.patch.object(
            self.state, "_dashboard_payload", side_effect=lambda _project, _work, endpoint: payload[endpoint]
        ):
            with self.assertRaisesRegex(self.state.CoshHammerError, "stale"):
                self.state.verify_coding(self.project, "handoff-work", "Task 1")

    def test_verify_coding_passes_only_for_current_dispatched_task(self) -> None:
        self.assertTrue(hasattr(self.state, "verify_coding"), "缺少编码模式二次验真")
        self.state.initialize_launch(
            self.project,
            work_id="handoff-work",
            refined_requirement="接管 Hammer 编码任务。",
            source={"kind": "text", "value": "接管编码任务"},
            hammer_root=self.hammer_root,
        )
        self.write_ready_plan(self.project)
        execute = self.project / ".hammer" / "execute"
        execute.mkdir()
        (execute / "session.md").write_text(
            "# Execute\n\n- current_stage: Coding Tasks\n"
            "- current_task_ref: Task 1\n- next_action: run-step-4\n- blocker: none\n",
            encoding="utf-8",
        )
        payload = self.dashboard_payload()
        with mock.patch.object(
            self.state, "_dashboard_payload", side_effect=lambda _project, _work, endpoint: payload[endpoint]
        ):
            result = self.state.verify_coding(self.project, "handoff-work", "TASK-1")

        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["hammer_task"], "Task 1")
        self.assertEqual(result["next_action"], "run-step-4")

    def test_activate_coding_requires_artifacts_and_creates_cosh_task_engine(self) -> None:
        self.assertTrue(hasattr(self.state, "activate_coding"), "缺少 Cosh 编码接管入口")
        coding = self.initialize_coding_work()
        (coding / "locations.json").unlink()
        with mock.patch.object(
            self.state,
            "verify_coding",
            return_value={
                "status": "passed",
                "plan_sha256": "plan-sha",
                "coding_tasks": ["Task 1"],
            },
        ):
            with self.assertRaisesRegex(self.state.CoshHammerError, "locations"):
                self.state.activate_coding(
                    self.project, "coding-work", "Task 1", self.coding_task_spec()
                )
            (coding / "locations.json").write_text(
                '{"status":"passed"}\n', encoding="utf-8"
            )
            result = self.state.activate_coding(
                self.project, "coding-work", "Task 1", self.coding_task_spec()
            )

        self.assertEqual(result["status"], "cosh_active")
        self.assertEqual(result["current_task"], "H1-S1")
        ownership = json.loads((coding / "ownership.json").read_text(encoding="utf-8"))
        tasks = json.loads((coding / "tasks.json").read_text(encoding="utf-8"))
        self.assertEqual(ownership["hammer_entry_task"], "Task 1")
        self.assertEqual(ownership["scope"], "full_coding_stage")
        self.assertEqual(tasks["schema_version"], 2)
        self.assertEqual([item["status"] for item in tasks["tasks"]], ["pending", "pending"])

    def test_activate_coding_builds_one_global_task_tree(self) -> None:
        coding = self.initialize_coding_work("global-coding")
        gate = {
            "status": "passed",
            "plan_sha256": "plan-sha",
            "coding_tasks": ["Task 1", "Task 2", "Task 3"],
        }

        with mock.patch.object(self.state, "verify_coding", return_value=gate):
            result = self.state.activate_coding(
                self.project,
                "global-coding",
                "Task 1",
                self.global_coding_task_spec(),
            )

        tasks = json.loads((coding / "tasks.json").read_text(encoding="utf-8"))
        ownership = json.loads(
            (coding / "ownership.json").read_text(encoding="utf-8")
        )
        self.assertEqual(result["task_count"], 4)
        self.assertEqual(result["hammer_task_count"], 3)
        self.assertEqual(tasks["schema_version"], 2)
        self.assertEqual(
            tasks["hammer_task_order"], ["Task 1", "Task 2", "Task 3"]
        )
        self.assertEqual(ownership["scope"], "full_coding_stage")
        self.assertEqual(ownership["hammer_entry_task"], "Task 1")

    def test_activate_coding_rejects_incomplete_or_invalid_parent_mapping(self) -> None:
        gate = {
            "status": "passed",
            "plan_sha256": "plan-sha",
            "coding_tasks": ["Task 1", "Task 2", "Task 3"],
        }
        invalid_specs = []

        missing_parent = self.global_coding_task_spec()
        missing_parent["tasks"] = missing_parent["tasks"][:-1]
        invalid_specs.append((missing_parent, "尚未全部细化"))

        unknown_parent = self.global_coding_task_spec()
        unknown_parent["tasks"][-1]["hammer_parent"] = "Task 4"
        invalid_specs.append((unknown_parent, "不属于 Hammer coding task"))

        duplicate_id = self.global_coding_task_spec()
        duplicate_id["tasks"][-1]["id"] = "task2-query"
        invalid_specs.append((duplicate_id, "id 无效或重复"))

        unknown_dependency = self.global_coding_task_spec()
        unknown_dependency["tasks"][-1]["dependencies"] = ["missing-task"]
        invalid_specs.append((unknown_dependency, "未知依赖"))

        later_parent_dependency = self.global_coding_task_spec()
        later_parent_dependency["tasks"][0]["dependencies"] = ["task2-query"]
        invalid_specs.append((later_parent_dependency, "不能依赖后续 Hammer 父任务"))

        for index, (task_spec, message) in enumerate(invalid_specs):
            work_id = f"invalid-global-{index}"
            self.initialize_coding_work(work_id)
            with self.subTest(message=message):
                with mock.patch.object(
                    self.state, "verify_coding", return_value=gate
                ):
                    with self.assertRaisesRegex(self.state.CoshHammerError, message):
                        self.state.activate_coding(
                            self.project, work_id, "Task 1", task_spec
                        )

    def test_activate_coding_rejects_tasks_without_byte_style_execution_details(self) -> None:
        self.initialize_coding_work()
        incomplete = {
            "tasks": [
                {
                    "id": "H1-S1",
                    "hammer_parent": "Task 1",
                    "title": "实现核心逻辑",
                    "expected_files": ["service.go"],
                    "acceptance": ["核心路径通过"],
                }
            ]
        }
        with mock.patch.object(
            self.state,
            "verify_coding",
            return_value={
                "status": "passed",
                "plan_sha256": "plan-sha",
                "coding_tasks": ["Task 1"],
            },
        ):
            with self.assertRaisesRegex(
                self.state.CoshHammerError, "任务说明|实施步骤|修改符号"
            ):
                self.state.activate_coding(
                    self.project, "coding-work", "Task 1", incomplete
                )

    def test_passed_subtask_commits_only_its_staged_delivery(self) -> None:
        self.initialize_git_repository()
        coding = self.activate_global_delivery_work("global-coding")
        gate = {
            "status": "passed",
            "plan_sha256": "plan-sha",
            "coding_tasks": ["Task 1", "Task 2", "Task 3"],
            "active_project": str(self.project.resolve()),
        }
        (self.project / "task1-fg.go").write_text("package task1fg\n", encoding="utf-8")
        self.git("add", "task1-fg.go")

        with mock.patch.object(self.state, "verify_handoff", return_value=gate):
            self.state.begin_subtask(self.project, "global-coding", "task1-fg")
            result = self.state.complete_subtask(
                self.project,
                "global-coding",
                "task1-fg",
                status="passed",
                evidence={"acceptance": "passed"},
            )

        checkpoint = json.loads(
            (coding / "checkpoints" / "task1-fg.json").read_text(encoding="utf-8")
        )
        tasks = json.loads((coding / "tasks.json").read_text(encoding="utf-8"))
        self.assertRegex(result["commit_sha"], r"^[0-9a-f]{40}$")
        self.assertEqual(self.git("show", "--name-only", "--format=", "HEAD"), "task1-fg.go")
        self.assertEqual(checkpoint["staged_files"], ["task1-fg.go"])
        self.assertEqual(checkpoint["commit_sha"], result["commit_sha"])
        self.assertRegex(checkpoint["snapshot_sha"], r"^[0-9a-f]{64}$")
        self.assertEqual(tasks["current_task"], "task1-tcc")

    def test_subtask_commit_rejects_empty_dirty_or_future_task_delivery(self) -> None:
        self.initialize_git_repository()
        gate = {
            "status": "passed",
            "plan_sha256": "plan-sha",
            "coding_tasks": ["Task 1", "Task 2", "Task 3"],
            "active_project": str(self.project.resolve()),
        }
        scenarios = (
            ("empty", None, None, "暂存区为空"),
            ("out-of-scope", "other.go", "staged", "超出当前任务范围"),
            ("current-dirty", "task1-fg.go", "staged-then-dirty", "当前或未来任务"),
            ("future-dirty", "task1-tcc.go", "unstaged-with-current", "当前或未来任务"),
        )
        for name, path, setup, message in scenarios:
            work_id = f"delivery-{name}"
            self.activate_global_delivery_work(work_id)
            if path:
                (self.project / path).write_text(f"package {name.replace('-', '')}\n", encoding="utf-8")
            if setup == "staged":
                self.git("add", str(path))
            elif setup == "staged-then-dirty":
                self.git("add", str(path))
                (self.project / str(path)).write_text(
                    "package task1fg\n// unstaged follow-up\n", encoding="utf-8"
                )
            elif setup == "unstaged-with-current":
                (self.project / "task1-fg.go").write_text(
                    "package task1fg\n", encoding="utf-8"
                )
                self.git("add", "task1-fg.go")
            with self.subTest(name=name):
                with mock.patch.object(self.state, "verify_handoff", return_value=gate):
                    self.state.begin_subtask(self.project, work_id, "task1-fg")
                    with self.assertRaisesRegex(self.state.CoshHammerError, message):
                        self.state.complete_subtask(
                            self.project,
                            work_id,
                            "task1-fg",
                            status="passed",
                            evidence={"acceptance": "passed"},
                        )
            self.git("reset", "--hard", "HEAD")
            for candidate in ("other.go", "task1-fg.go", "task1-tcc.go"):
                target = self.project / candidate
                if target.exists():
                    target.unlink()

        coding = self.activate_global_delivery_work("delivery-blocked")
        before = self.git("rev-parse", "HEAD")
        with mock.patch.object(self.state, "verify_handoff", return_value=gate):
            self.state.begin_subtask(self.project, "delivery-blocked", "task1-fg")
            result = self.state.complete_subtask(
                self.project,
                "delivery-blocked",
                "task1-fg",
                status="blocked",
                evidence={"reason": "dependency unavailable"},
            )
        checkpoint = json.loads(
            (coding / "checkpoints" / "task1-fg.json").read_text(encoding="utf-8")
        )
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(checkpoint["evidence"]["reason"], "dependency unavailable")
        self.assertEqual(self.git("rev-parse", "HEAD"), before)
        self.assertNotIn("commit_sha", checkpoint)

    def test_live_status_projects_detailed_task_progress_and_next_action(self) -> None:
        self.initialize_coding_work()
        detailed = self.coding_task_spec()
        for task in detailed["tasks"]:
            task.update(
                {
                    "description": f"完成 {task['title']} 的最小改动",
                    "symbols": ["OrderService.Check"],
                    "steps": ["读取现状", "实现改动", "记录验证证据"],
                    "dependencies": [],
                }
            )
        with mock.patch.object(
            self.state,
            "verify_coding",
            return_value={"status": "passed", "plan_sha256": "plan-sha"},
        ):
            self.state.activate_coding(
                self.project, "coding-work", "Task 1", detailed
            )
            status = self.state.build_status(self.project, "coding-work")

        self.assertEqual(status["coding"]["progress"]["total"], 2)
        self.assertEqual(status["coding"]["progress"]["completed"], 0)
        self.assertEqual(status["coding"]["next_action"], "await_task_authorization")
        self.assertEqual(status["coding"]["current_task"]["symbols"], ["OrderService.Check"])

    def test_dashboard_projects_global_coding_tree_by_hammer_parent(self) -> None:
        coding = self.initialize_coding_work("global-dashboard")
        spec = self.global_coding_task_spec()
        for index, task in enumerate(spec["tasks"]):
            task["status"] = "passed" if index < 2 else "pending"
        (coding / "tasks.json").write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "status": "running",
                    "hammer_task_order": ["Task 1", "Task 2", "Task 3"],
                    "current_task": "task2-query",
                    "tasks": spec["tasks"],
                }
            ),
            encoding="utf-8",
        )
        (coding / "ownership.json").write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "status": "cosh_active",
                    "scope": "full_coding_stage",
                    "hammer_entry_task": "Task 1",
                    "hammer_task_order": ["Task 1", "Task 2", "Task 3"],
                }
            ),
            encoding="utf-8",
        )
        checkpoints = coding / "checkpoints"
        checkpoints.mkdir()
        for index, task_id in enumerate(("task1-fg", "task1-tcc"), start=1):
            (checkpoints / f"{task_id}.json").write_text(
                json.dumps(
                    {
                        "task": task_id,
                        "status": "passed",
                        "commit_sha": str(index) * 40,
                        "staged_files": [f"{task_id}.go"],
                    }
                ),
                encoding="utf-8",
            )

        status = self.state.build_status(self.project, "global-dashboard")

        self.assertEqual(
            [parent["id"] for parent in status["coding"]["parents"]],
            ["Task 1", "Task 2", "Task 3"],
        )
        self.assertEqual(status["coding"]["parents"][0]["completed"], 2)
        self.assertEqual(status["coding"]["progress"]["total"], 4)
        self.assertEqual(status["coding"]["current_task"]["id"], "task2-query")
        self.assertEqual(
            status["coding"]["tasks"][0]["checkpoint"]["commit_sha"], "1" * 40
        )
        self.assertNotIn("next_hammer_task", status["coding"])

    def test_live_status_normalizes_legacy_completed_task_as_read_only_passed(self) -> None:
        coding = self.initialize_coding_work()
        (coding / "tasks.json").write_text(
            json.dumps(
                {
                    "status": "running",
                    "current_task": "TASK1-CONFIG-CONTROL-PLANE",
                    "tasks": [
                        {
                            "id": "TASK1-CONFIG-CONTROL-PLANE",
                            "hammer_parent": "Task 1",
                            "title": "Implement control plane",
                            "status": "completed",
                            "acceptance": ["request path never calls TCC Getter"],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        status = self.state.build_status(self.project, "coding-work")

        self.assertEqual(status["coding"]["progress"]["completed"], 1)
        self.assertEqual(status["coding"]["progress"]["total"], 1)
        self.assertEqual(status["coding"]["tasks"][0]["status"], "passed")
        self.assertEqual(status["coding"]["tasks"][0]["source_status"], "completed")
        self.assertEqual(status["coding"]["next_action"], "legacy_snapshot_readonly")
        self.assertEqual(
            status["coding"]["compatibility"],
            "legacy_single_parent_readonly",
        )
        self.assertFalse(status["coding"]["controls_enabled"])

    def test_single_mode_requires_authorization_and_stops_at_each_subtask(self) -> None:
        coding = self.initialize_coding_work()
        self.initialize_git_repository()
        gate = {
            "status": "passed",
            "plan_sha256": "plan-sha",
            "coding_tasks": ["Task 1"],
            "active_project": str(self.project.resolve()),
        }
        with mock.patch.object(
            self.state, "verify_coding", return_value=gate
        ), mock.patch.object(self.state, "verify_handoff", return_value=gate):
            self.state.activate_coding(
                self.project, "coding-work", "Task 1", self.coding_task_spec()
            )
            with self.assertRaisesRegex(self.state.CoshHammerError, "授权"):
                self.state.begin_subtask(self.project, "coding-work", "H1-S1")
            self.state.apply_control(
                self.project,
                "coding-work",
                {"action": "authorize-task", "task": "H1-S1"},
            )
            self.state.begin_subtask(self.project, "coding-work", "H1-S1")
            (self.project / "service.go").write_text(
                "package service\n", encoding="utf-8"
            )
            self.git("add", "service.go")
            result = self.state.complete_subtask(
                self.project,
                "coding-work",
                "H1-S1",
                status="passed",
                evidence={"summary": "核心逻辑完成"},
            )

        self.assertEqual(result["current_task"], "H1-S2")
        control = json.loads((coding / "control.json").read_text(encoding="utf-8"))
        self.assertNotIn("authorized_task", control)

    def test_single_mode_cannot_authorize_a_future_subtask(self) -> None:
        self.initialize_coding_work()
        with mock.patch.object(
            self.state,
            "verify_coding",
            return_value={"status": "passed", "plan_sha256": "plan-sha"},
        ):
            self.state.activate_coding(
                self.project, "coding-work", "Task 1", self.coding_task_spec()
            )
            with self.assertRaisesRegex(self.state.CoshHammerError, "当前"):
                self.state.apply_control(
                    self.project,
                    "coding-work",
                    {"action": "authorize-task", "task": "H1-S2"},
                )

    def test_subtask_cannot_start_before_dependencies_pass(self) -> None:
        coding = self.initialize_coding_work()
        spec = self.coding_task_spec()
        spec["tasks"] = [spec["tasks"][1], spec["tasks"][0]]
        with mock.patch.object(
            self.state,
            "verify_coding",
            return_value={"status": "passed", "plan_sha256": "plan-sha"},
        ):
            self.state.activate_coding(
                self.project, "coding-work", "Task 1", spec
            )
            self.state.apply_control(
                self.project, "coding-work", {"action": "set-mode", "mode": "continuous"}
            )
            with self.assertRaisesRegex(self.state.CoshHammerError, "依赖"):
                self.state.begin_subtask(self.project, "coding-work", "H1-S2")

        state = json.loads((coding / "tasks.json").read_text(encoding="utf-8"))
        self.assertEqual(state["current_task"], "H1-S2")

    def test_task_authorization_requires_active_cosh_ownership(self) -> None:
        coding = self.initialize_coding_work()
        (coding / "tasks.json").write_text(
            json.dumps(
                {
                    "status": "running",
                    "current_task": "H1-S1",
                    "tasks": [
                        {
                            "id": "H1-S1",
                            "hammer_parent": "Task 1",
                            "status": "pending",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        with mock.patch.object(
            self.state,
            "verify_coding",
            return_value={"status": "passed", "plan_sha256": "plan-sha"},
        ):
            with self.assertRaisesRegex(self.state.CoshHammerError, "所有权"):
                self.state.apply_control(
                    self.project,
                    "coding-work",
                    {"action": "authorize-task", "task": "H1-S1"},
                )

    def test_continuous_mode_advances_without_per_task_authorization(self) -> None:
        self.initialize_coding_work()
        self.initialize_git_repository()
        gate = {
            "status": "passed",
            "plan_sha256": "plan-sha",
            "coding_tasks": ["Task 1"],
            "active_project": str(self.project.resolve()),
        }
        with mock.patch.object(
            self.state, "verify_coding", return_value=gate
        ), mock.patch.object(self.state, "verify_handoff", return_value=gate):
            self.state.activate_coding(
                self.project, "coding-work", "Task 1", self.coding_task_spec()
            )
            self.state.apply_control(
                self.project,
                "coding-work",
                {"action": "set-mode", "mode": "continuous"},
            )
            self.state.begin_subtask(self.project, "coding-work", "H1-S1")
            (self.project / "service.go").write_text(
                "package service\n", encoding="utf-8"
            )
            self.git("add", "service.go")
            first = self.state.complete_subtask(
                self.project,
                "coding-work",
                "H1-S1",
                status="passed",
                evidence={"summary": "核心逻辑完成"},
            )
            second = self.state.begin_subtask(
                self.project, "coding-work", "H1-S2"
            )

        self.assertEqual(first["current_task"], "H1-S2")
        self.assertEqual(second["task"]["status"], "running")

    def test_blocked_subtask_does_not_advance_to_next_task(self) -> None:
        self.initialize_coding_work()
        with mock.patch.object(
            self.state,
            "verify_coding",
            return_value={"status": "passed", "plan_sha256": "plan-sha"},
        ):
            self.state.activate_coding(
                self.project, "coding-work", "Task 1", self.coding_task_spec()
            )
            self.state.apply_control(
                self.project, "coding-work", {"action": "set-mode", "mode": "continuous"}
            )
            self.state.begin_subtask(self.project, "coding-work", "H1-S1")
            result = self.state.complete_subtask(
                self.project,
                "coding-work",
                "H1-S1",
                status="blocked",
                evidence={"reason": "依赖缺失"},
            )

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["current_task"], "H1-S1")

    def test_complete_coding_returns_one_global_handoff(self) -> None:
        self.initialize_git_repository()
        self.activate_global_delivery_work("global-coding")
        gate = {
            "status": "passed",
            "plan_sha256": "plan-sha",
            "coding_tasks": ["Task 1", "Task 2", "Task 3"],
            "active_project": str(self.project.resolve()),
        }
        with mock.patch.object(self.state, "verify_handoff", return_value=gate):
            with self.assertRaisesRegex(self.state.CoshHammerError, "尚未全部通过"):
                self.state.complete_coding(self.project, "global-coding")

        coding, commits = self.complete_global_delivery_tasks("completed-global")
        with mock.patch.object(self.state, "verify_handoff", return_value=gate):
            done = self.state.complete_coding(self.project, "completed-global")

        self.assertEqual(done["status"], "DONE")
        self.assertEqual(
            done["completed_hammer_tasks"], ["Task 1", "Task 2", "Task 3"]
        )
        self.assertEqual(done["next_action"], "hammer_continue_after_coding_stage")
        self.assertEqual(
            done["task_commits"],
            [
                {"task": task["id"], "commit_sha": commit}
                for task, commit in zip(self.global_coding_task_spec()["tasks"], commits)
            ],
        )
        self.assertTrue((coding / "coding-stage-handoff.json").is_file())
        self.assertFalse((coding / "parent-handoffs" / "task-1.json").exists())
        ownership = json.loads((coding / "ownership.json").read_text(encoding="utf-8"))
        self.assertEqual(ownership["status"], "returned_to_hammer")

    def test_complete_coding_reconciles_every_task_checkpoint(self) -> None:
        self.initialize_git_repository()
        gate = {
            "status": "passed",
            "plan_sha256": "plan-sha",
            "coding_tasks": ["Task 1", "Task 2", "Task 3"],
            "active_project": str(self.project.resolve()),
        }

        coding, _commits = self.complete_global_delivery_tasks("missing-checkpoint")
        (coding / "checkpoints" / "task2-query.json").unlink()
        with mock.patch.object(self.state, "verify_handoff", return_value=gate):
            with self.assertRaisesRegex(self.state.CoshHammerError, "缺少 checkpoint"):
                self.state.complete_coding(self.project, "missing-checkpoint")

        coding, commits = self.complete_global_delivery_tasks("mismatched-checkpoint")
        checkpoint_path = coding / "checkpoints" / "task3-consumer.json"
        checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        checkpoint["commit_sha"] = commits[-2]
        checkpoint_path.write_text(json.dumps(checkpoint), encoding="utf-8")
        with mock.patch.object(self.state, "verify_handoff", return_value=gate):
            with self.assertRaisesRegex(self.state.CoshHammerError, "checkpoint.*commit"):
                self.state.complete_coding(self.project, "mismatched-checkpoint")

        coding, _commits = self.complete_global_delivery_tasks("unreachable-commit")
        orphan = self.git("commit-tree", "HEAD^{tree}", "-m", "orphan")
        checkpoint_path = coding / "checkpoints" / "task3-consumer.json"
        checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        checkpoint["commit_sha"] = orphan
        checkpoint_path.write_text(json.dumps(checkpoint), encoding="utf-8")
        tasks_path = coding / "tasks.json"
        tasks = json.loads(tasks_path.read_text(encoding="utf-8"))
        tasks["tasks"][-1]["commit_sha"] = orphan
        tasks_path.write_text(json.dumps(tasks), encoding="utf-8")
        with mock.patch.object(self.state, "verify_handoff", return_value=gate):
            with self.assertRaisesRegex(self.state.CoshHammerError, "Git 历史"):
                self.state.complete_coding(self.project, "unreachable-commit")

        self.complete_global_delivery_tasks("stale-plan")
        stale_gate = dict(gate, plan_sha256="changed-plan-sha")
        with mock.patch.object(self.state, "verify_handoff", return_value=stale_gate):
            with self.assertRaisesRegex(self.state.CoshHammerError, "Plan 已变化"):
                self.state.complete_coding(self.project, "stale-plan")

        self.complete_global_delivery_tasks("head-mismatch")
        self.git("commit", "--allow-empty", "-m", "unrelated commit")
        with mock.patch.object(self.state, "verify_handoff", return_value=gate):
            with self.assertRaisesRegex(self.state.CoshHammerError, "HEAD"):
                self.state.complete_coding(self.project, "head-mismatch")

    def test_attach_existing_hammer_initializes_only_cosh_and_reports_plan_repair(self) -> None:
        self.assertTrue(
            hasattr(self.state, "attach_existing_hammer"), "缺少迟到接入恢复命令"
        )
        self.write_ready_plan(self.project, include_trigger=False)
        before = self.hammer_snapshot()

        result = self.state.attach_existing_hammer(
            self.project,
            work_id="late-attach",
            refined_requirement="接入已经完成 Plan 的 Hammer 任务。",
            hammer_root=self.hammer_root,
        )

        self.assertEqual(before, self.hammer_snapshot())
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["missing_trigger_tasks"], ["Task 1"])
        self.assertIn("Hammer Plan", result["repair_required"])
        launch = (
            self.project
            / ".cosh"
            / "hammer-plugin"
            / "late-attach"
            / "launch"
            / "launch.json"
        )
        self.assertTrue(launch.is_file())

    def test_state_cli_exposes_all_fail_closed_handoff_commands(self) -> None:
        parser = self.state.build_parser()
        common = ["--project", str(self.project), "--work", "handoff-work"]

        self.assertEqual(parser.parse_args(["preflight", *common]).command, "preflight")
        self.assertEqual(
            parser.parse_args(["verify-handoff", *common]).command,
            "verify-handoff",
        )
        coding = parser.parse_args(["verify-coding", *common, "--task", "Task 1"])
        self.assertEqual(coding.task, "Task 1")
        attached = parser.parse_args(
            [
                "attach-existing-hammer",
                *common,
                "--requirement",
                "接入现有 Hammer",
                "--hammer-root",
                str(self.hammer_root),
                "--no-open",
            ]
        )
        self.assertEqual(attached.command, "attach-existing-hammer")
        activated = parser.parse_args(
            [
                "activate-coding",
                *common,
                "--task",
                "Task 1",
                "--tasks-file",
                str(self.project / "tasks.json"),
            ]
        )
        self.assertEqual(activated.command, "activate-coding")
        self.assertEqual(
            parser.parse_args(
                ["begin-subtask", *common, "--task-id", "H1-S1"]
            ).command,
            "begin-subtask",
        )
        self.assertEqual(
            parser.parse_args(
                [
                    "complete-subtask",
                    *common,
                    "--task-id",
                    "H1-S1",
                    "--status",
                    "passed",
                    "--evidence-file",
                    str(self.project / "evidence.json"),
                ]
            ).command,
            "complete-subtask",
        )
        self.assertEqual(
            parser.parse_args(["complete-coding", *common]).command,
            "complete-coding",
        )
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                parser.parse_args(
                    ["complete-coding", *common, "--task", "Task 1"]
                )

    def test_dashboard_projects_cosh_ownership_and_only_enables_coding_controls_when_active(self) -> None:
        self.initialize_coding_work()
        with mock.patch.object(
            self.state,
            "verify_coding",
            return_value={"status": "passed", "plan_sha256": "plan-sha"},
        ):
            self.state.activate_coding(
                self.project, "coding-work", "Task 1", self.coding_task_spec()
            )
        active = self.state.build_status(self.project, "coding-work")
        self.assertEqual(active["coding"]["ownership"]["status"], "cosh_active")
        self.assertTrue(active["coding"]["controls_enabled"])

        ownership = (
            self.project
            / ".cosh"
            / "hammer-plugin"
            / "coding-work"
            / "coding"
            / "ownership.json"
        )
        value = json.loads(ownership.read_text(encoding="utf-8"))
        value["status"] = "returned_to_hammer"
        ownership.write_text(json.dumps(value), encoding="utf-8")
        returned = self.state.build_status(self.project, "coding-work")
        self.assertFalse(returned["coding"]["controls_enabled"])

    def test_initialize_launch_requires_hammer_and_writes_only_plugin_state(self) -> None:
        before = self.hammer_snapshot()
        launch = self.state.initialize_launch(
            self.project,
            work_id="order-risk",
            refined_requirement="限制重复下单，并给出可验收条件。",
            source={"kind": "text", "value": "限制重复下单"},
            hammer_root=self.hammer_root,
        )
        self.assertEqual(before, self.hammer_snapshot())
        self.assertEqual(launch["work"], "order-risk")
        self.assertEqual(launch["hammer"]["required"], True)
        self.assertEqual(
            launch["worktree"], {"policy": "skip", "source": "user"}
        )
        self.assertEqual(launch["meego"], {"bound": False})
        self.assertIn("$hammer", launch["hammer_prompt"])
        self.assertIn("- decision: skip", launch["hammer_prompt"])
        self.assertIn("- source: user", launch["hammer_prompt"])
        self.assertIn(
            "Use $cosh-hammer in coding mode for this Hammer parent task.",
            launch["hammer_prompt"],
        )
        self.assertIn("verify-handoff", launch["hammer_prompt"])
        self.assertIn("verify-coding", launch["hammer_prompt"])
        self.assertIn("暂停 Hammer 的原生编码执行", launch["hammer_prompt"])
        self.assertIn("hammer_continue_after_coding_stage", launch["hammer_prompt"])
        state_root = self.project / ".cosh" / "hammer-plugin" / "order-risk"
        self.assertTrue((state_root / "launch" / "request.md").is_file())
        self.assertTrue((state_root / "launch" / "launch.json").is_file())
        self.assertFalse((self.project / ".hammer" / "cosh-hammer.json").exists())

        missing = pathlib.Path(self.temp.name) / "missing-hammer"
        with self.assertRaises(self.state.CoshHammerError):
            self.state.initialize_launch(
                self.project,
                work_id="missing",
                refined_requirement="x",
                source={"kind": "text", "value": "x"},
                hammer_root=missing,
            )
        wrong = pathlib.Path(self.temp.name) / "wrong-skill"
        wrong.mkdir()
        (wrong / "SKILL.md").write_text(
            "---\nname: not-hammer\n---\n", encoding="utf-8"
        )
        with self.assertRaises(self.state.CoshHammerError):
            self.state.initialize_launch(
                self.project,
                work_id="wrong",
                refined_requirement="x",
                source={"kind": "text", "value": "x"},
                hammer_root=wrong,
            )

    def test_initialize_launch_only_opens_worktree_when_explicitly_requested(self) -> None:
        launch = self.state.initialize_launch(
            self.project,
            work_id="isolated-order-risk",
            refined_requirement="在隔离 worktree 中限制重复下单。",
            source={"kind": "text", "value": "明确使用 worktree"},
            hammer_root=self.hammer_root,
            worktree_policy="open",
        )
        self.assertEqual(
            launch["worktree"], {"policy": "open", "source": "user"}
        )
        self.assertIn("- decision: open", launch["hammer_prompt"])
        self.assertIn("- source: user", launch["hammer_prompt"])
        self.assertNotIn("- decision: skip", launch["hammer_prompt"])

        with self.assertRaises(self.state.CoshHammerError):
            self.state.initialize_launch(
                self.project,
                work_id="invalid-worktree-policy",
                refined_requirement="x",
                source={"kind": "text", "value": "x"},
                hammer_root=self.hammer_root,
                worktree_policy="auto",
            )

    def test_initialize_launch_optionally_binds_meego_for_hammer(self) -> None:
        launch = self.state.initialize_launch(
            self.project,
            work_id="meego-order-risk",
            refined_requirement="限制重复下单。",
            source={"kind": "text", "value": "限制重复下单"},
            hammer_root=self.hammer_root,
            meego_id="7092608674",
        )
        self.assertEqual(
            launch["meego"],
            {
                "bound": True,
                "id": "7092608674",
                "url": "https://meego.larkoffice.com/larksuite/story/detail/7092608674",
            },
        )
        self.assertIn("## Meego 处理决策", launch["hammer_prompt"])
        self.assertIn("- decision: existing", launch["hammer_prompt"])
        self.assertIn("- source: user", launch["hammer_prompt"])
        self.assertIn("detail/7092608674", launch["hammer_prompt"])
        status = self.state.build_status(self.project, "meego-order-risk")
        self.assertEqual(status["launch"]["meego"], launch["meego"])

        with self.assertRaises(self.state.CoshHammerError):
            self.state.initialize_launch(
                self.project,
                work_id="invalid-meego",
                refined_requirement="x",
                source={"kind": "text", "value": "x"},
                hammer_root=self.hammer_root,
                meego_id="story-7092608674",
            )

    def test_init_cli_defaults_to_skip_and_accepts_explicit_open(self) -> None:
        parser = self.state.build_parser()
        common = [
            "init",
            "--project",
            str(self.project),
            "--work",
            "order-risk",
            "--requirement",
            "限制重复下单",
            "--source",
            "限制重复下单",
            "--hammer-root",
            str(self.hammer_root),
        ]
        self.assertEqual(parser.parse_args(common).worktree, "skip")
        self.assertIsNone(parser.parse_args(common).meego_id)
        self.assertEqual(
            parser.parse_args([*common, "--worktree", "open"]).worktree,
            "open",
        )
        self.assertEqual(
            parser.parse_args([*common, "--meego-id", "7092608674"]).meego_id,
            "7092608674",
        )

    def test_descendant_symlink_cannot_redirect_plugin_writes_into_hammer(self) -> None:
        work = self.project / ".cosh" / "hammer-plugin" / "redirected"
        work.mkdir(parents=True)
        (work / "launch").symlink_to(self.project / ".hammer", target_is_directory=True)
        before = self.hammer_snapshot()
        with self.assertRaises(self.state.CoshHammerError):
            self.state.initialize_launch(
                self.project,
                work_id="redirected",
                refined_requirement="不能写入 Hammer。",
                source={"kind": "text", "value": "x"},
                hammer_root=self.hammer_root,
            )
        self.assertEqual(before, self.hammer_snapshot())

    def test_projection_combines_read_only_hammer_and_plugin_artifacts(self) -> None:
        self.state.initialize_launch(
            self.project,
            work_id="order-risk",
            refined_requirement="限制重复下单。",
            source={"kind": "text", "value": "限制重复下单"},
            hammer_root=self.hammer_root,
        )
        coding = self.project / ".cosh" / "hammer-plugin" / "order-risk" / "coding"
        coding.mkdir(parents=True, exist_ok=True)
        (coding / "code-facts.json").write_text('{"status":"passed"}\n', encoding="utf-8")
        (coding / "change-surface.json").write_text('{"status":"running"}\n', encoding="utf-8")
        before = self.hammer_snapshot()
        status = self.state.build_status(self.project, "order-risk")
        self.assertEqual(before, self.hammer_snapshot())
        self.assertEqual(status["hammer"]["stage"], "plan")
        self.assertEqual(status["hammer"]["status"], "running")
        stages = {item["id"]: item["status"] for item in status["stages"]}
        self.assertEqual(stages["code_facts"], "passed")
        self.assertEqual(stages["change_surface"], "running")
        self.assertIn("hammer_validation", stages)
        self.assertFalse(status["stale"])

    def test_artifact_inventory_and_reader_expose_hammer_and_cosh_outputs(self) -> None:
        self.state.initialize_launch(
            self.project,
            work_id="artifact-work",
            refined_requirement="展示全部研发产物。",
            source={"kind": "text", "value": "展示全部研发产物"},
            hammer_root=self.hammer_root,
        )
        design = self.project / ".hammer" / "design"
        drafts = design / "drafts"
        drafts.mkdir(parents=True)
        (drafts / "stage1-change.md").write_text(
            "# 需求结论\n", encoding="utf-8"
        )
        (design / "design.md").write_text("# 技术设计\n", encoding="utf-8")
        (design / "security-review.md").write_text(
            "# 安全评审\n", encoding="utf-8"
        )
        coding = (
            self.project
            / ".cosh"
            / "hammer-plugin"
            / "artifact-work"
            / "coding"
        )
        coding.mkdir(parents=True)
        (coding / "implementation-plan.md").write_text(
            "# 编码计划\n", encoding="utf-8"
        )

        status = self.state.build_status(self.project, "artifact-work")
        artifacts = {
            (item["scope"], item["path"]): item for item in status["artifacts"]
        }

        self.assertEqual(
            artifacts[("hammer", "design/drafts/stage1-change.md")]["category"],
            "requirement",
        )
        self.assertEqual(
            artifacts[("hammer", "design/design.md")]["category"], "design"
        )
        self.assertEqual(
            artifacts[("hammer", "design/security-review.md")]["category"],
            "review",
        )
        self.assertEqual(
            artifacts[("cosh", "coding/implementation-plan.md")]["category"],
            "coding",
        )
        artifact = self.state.read_artifact(
            self.project,
            "artifact-work",
            scope="hammer",
            relative_path="design/design.md",
        )
        self.assertEqual(artifact["content"], "# 技术设计\n")
        self.assertEqual(artifact["kind"], "text")
        self.assertNotIn(
            ("cosh", "dashboard/dashboard-state.json"), artifacts
        )

    def test_review_round_outputs_are_classified_and_projected_as_results(self) -> None:
        self.state.initialize_launch(
            self.project,
            work_id="review-rounds",
            refined_requirement="展示三路评审结果。",
            source={"kind": "text", "value": "展示三路评审结果"},
            hammer_root=self.hammer_root,
        )
        round_dir = self.project / ".hammer" / "design" / "reviews" / "2"
        round_dir.mkdir(parents=True)
        reports = {
            "general.md": ("pass", "none", 0, "GEN-1"),
            "security.md": ("blocked", "P0", 1, "SEC-1"),
            "stability.md": ("pass", "P2", 0, "none"),
        }
        for name, (status, severity, count, unresolved) in reports.items():
            (round_dir / name).write_text(
                "---\n"
                f"status: {status}\n"
                "review_mode: subagent\n"
                "review_pass: closure\n"
                "review_attempt: 2\n"
                f"blocking_issue_count: {count}\n"
                f"unresolved_finding_ids: {unresolved}\n"
                f"max_severity: {severity}\n"
                "fallback_stage: none\n"
                "---\n\n# Review\n",
                encoding="utf-8",
            )
        (round_dir / "design.md").write_text("# Review Snapshot\n", encoding="utf-8")
        (round_dir / "routing.json").write_text(
            '{"review_attempt":2}\n', encoding="utf-8"
        )

        status = self.state.build_status(self.project, "review-rounds")
        artifacts = {
            item["path"]: item["category"] for item in status["artifacts"]
        }
        latest = status["review_results"]["rounds"][0]
        channels = {item["channel"]: item for item in latest["reports"]}

        self.assertEqual(artifacts["design/reviews/2/security.md"], "review")
        self.assertEqual(artifacts["design/reviews/2/stability.md"], "review")
        self.assertEqual(artifacts["design/reviews/2/design.md"], "review")
        self.assertEqual(artifacts["design/reviews/2/routing.json"], "review")
        self.assertEqual(status["review_results"]["latest_round"], 2)
        self.assertEqual(latest["status"], "blocked")
        self.assertEqual(channels["security"]["status"], "blocked")
        self.assertEqual(channels["security"]["blocking_issue_count"], 1)
        self.assertEqual(channels["security"]["max_severity"], "P0")
        self.assertEqual(channels["security"]["unresolved_finding_ids"], "SEC-1")
        self.assertEqual(channels["general"]["artifact_path"], "design/reviews/2/general.md")

    def test_review_round_accepts_hammer_recommendation_and_kind_aliases(self) -> None:
        self.state.initialize_launch(
            self.project,
            work_id="review-aliases",
            refined_requirement="兼容 Hammer 三路评审字段。",
            source={"kind": "text", "value": "兼容 Hammer 三路评审字段"},
            hammer_root=self.hammer_root,
        )
        reviews = self.project / ".hammer" / "design" / "reviews"
        round_one = reviews / "1"
        round_two = reviews / "2"
        round_one.mkdir(parents=True)
        round_two.mkdir()
        for channel in ("general", "security", "stability"):
            status = "blocked" if channel == "stability" else "pass"
            count = 2 if channel == "stability" else 0
            severity = "P0" if channel == "stability" else "none"
            (round_one / f"{channel}.md").write_text(
                "---\n"
                f"status_recommendation: {status}\n"
                f"blocking_issue_count: {count}\n"
                f"max_severity: {severity}\n"
                "---\n",
                encoding="utf-8",
            )
            (round_two / f"{channel}.md").write_text(
                "---\n"
                "status: blocked\n"
                "status_recommendation: pass\n"
                "blocking_issue_count: 0\n"
                "max_severity: none\n"
                "---\n",
                encoding="utf-8",
            )

        status = self.state.build_status(self.project, "review-aliases")
        rounds = status["review_results"]["rounds"]
        latest = rounds[0]
        previous = rounds[1]

        self.assertEqual(status["review_results"]["latest_round"], 2)
        self.assertEqual(latest["status"], "passed")
        self.assertTrue(all(report["status"] == "pass" for report in latest["reports"]))
        self.assertTrue(
            all(report["review_pass"] == "closure" for report in latest["reports"])
        )
        self.assertEqual(previous["status"], "blocked")
        self.assertTrue(
            all(report["review_pass"] == "full" for report in previous["reports"])
        )
        stability = next(
            report for report in previous["reports"] if report["channel"] == "stability"
        )
        self.assertEqual(stability["blocking_issue_count"], 2)
        self.assertEqual(stability["max_severity"], "P0")

    def test_progress_marks_plan_as_next_after_review_has_passed(self) -> None:
        self.state.initialize_launch(
            self.project,
            work_id="progress-marker",
            refined_requirement="展示当前流程位置。",
            source={"kind": "text", "value": "展示当前流程位置"},
            hammer_root=self.hammer_root,
        )
        plan = self.project / ".hammer" / "plan"
        for path in plan.iterdir():
            path.unlink()
        plan.rmdir()
        design = self.project / ".hammer" / "design"
        design.mkdir(parents=True)
        (design / "design.md").write_text("# Design\n", encoding="utf-8")
        for name in ("review.md", "security-review.md", "stability-review.md"):
            (design / name).write_text("status: passed\n", encoding="utf-8")

        status = self.state.build_status(self.project, "progress-marker")
        stages = {item["id"]: item for item in status["stages"]}

        self.assertEqual(
            status["progress"],
            {
                "stage_id": "hammer_plan",
                "label": "Hammer 计划",
                "marker": "next",
                "completed": 3,
                "total": 11,
                "percent": 27,
            },
        )
        self.assertEqual(stages["hammer_plan"]["progress_marker"], "next")
        self.assertFalse(
            any(
                item.get("progress_marker")
                for item in status["stages"]
                if item["id"] != "hammer_plan"
            )
        )

    def test_progress_marks_running_hammer_stage_as_current(self) -> None:
        self.state.initialize_launch(
            self.project,
            work_id="current-progress-marker",
            refined_requirement="展示当前流程位置。",
            source={"kind": "text", "value": "展示当前流程位置"},
            hammer_root=self.hammer_root,
        )

        status = self.state.build_status(self.project, "current-progress-marker")
        plan_stage = next(
            item for item in status["stages"] if item["id"] == "hammer_plan"
        )

        self.assertEqual(status["progress"]["stage_id"], "hammer_plan")
        self.assertEqual(status["progress"]["marker"], "current")
        self.assertEqual(plan_stage["progress_marker"], "current")

    def test_artifact_reader_rejects_traversal_and_symlink_escape(self) -> None:
        self.state.initialize_launch(
            self.project,
            work_id="artifact-security",
            refined_requirement="安全查看产物。",
            source={"kind": "text", "value": "安全查看产物"},
            hammer_root=self.hammer_root,
        )
        outside = pathlib.Path(self.temp.name) / "secret.txt"
        outside.write_text("secret\n", encoding="utf-8")
        (self.project / ".hammer" / "secret-link").symlink_to(outside)

        with self.assertRaises(self.state.CoshHammerError):
            self.state.read_artifact(
                self.project,
                "artifact-security",
                scope="hammer",
                relative_path="../secret.txt",
            )
        with self.assertRaises(self.state.CoshHammerError):
            self.state.read_artifact(
                self.project,
                "artifact-security",
                scope="hammer",
                relative_path="secret-link",
            )

    def test_projection_stays_on_original_project_without_migration_event(self) -> None:
        self.state.initialize_launch(
            self.project,
            work_id="no-migration",
            refined_requirement="默认不使用工作树。",
            source={"kind": "text", "value": "默认不使用工作树"},
            hammer_root=self.hammer_root,
        )
        target = self.create_linked_worktree("unused-worktree")
        execute = target / ".hammer" / "execute"
        execute.mkdir(parents=True)
        (execute / "session.md").write_text(
            "# Execute\n\n- next_action: run-step-5\n- blocker: none\n",
            encoding="utf-8",
        )

        status = self.state.build_status(self.project, "no-migration")

        self.assertEqual(status["hammer"]["stage"], "plan")
        self.assertEqual(status["active_project"], str(self.project.resolve()))
        self.assertFalse(status["workspace"]["migrated"])

    def test_projection_follows_valid_hammer_worktree_migration_event(self) -> None:
        self.state.initialize_launch(
            self.project,
            work_id="migrated-work",
            refined_requirement="显式使用工作树。",
            source={"kind": "text", "value": "使用工作树"},
            hammer_root=self.hammer_root,
            worktree_policy="open",
        )
        target = self.create_linked_worktree("active-worktree")
        target_hammer = target / ".hammer"
        target_design = target_hammer / "design"
        target_design.mkdir(parents=True)
        (target_design / "session.md").write_text(
            "# Design\n\n## 审计日志\n\n"
            f"- 2026-08-21 10:00:01 +0800 | workspace.worktree "
            f"decision=created path={target} tool=git\n",
            encoding="utf-8",
        )
        execute = target_hammer / "execute"
        execute.mkdir(parents=True)
        (execute / "session.md").write_text(
            "# Execute\n\n"
            "- current_task_ref: TASK-2\n"
            "- next_action: run-step-5\n"
            "- blocker: none\n",
            encoding="utf-8",
        )
        design = self.project / ".hammer" / "design"
        design.mkdir(exist_ok=True)
        (design / "session.md").write_text(
            "# Design\n\n## 审计日志\n\n"
            f"- 2026-08-21 10:00:00 +0800 | workspace.worktree "
            f"decision=migrated_away path={target}\n",
            encoding="utf-8",
        )

        status = self.state.build_status(self.project, "migrated-work")

        self.assertEqual(status["hammer"]["stage"], "validation")
        self.assertEqual(status["hammer"]["current_task"], "TASK-2")
        self.assertEqual(status["active_project"], str(target.resolve()))
        self.assertTrue(status["workspace"]["migrated"])
        self.assertEqual(status["workspace"]["migration_chain"], [str(target.resolve())])
        artifact = self.state.read_artifact(
            self.project,
            "migrated-work",
            scope="hammer",
            relative_path="execute/session.md",
        )
        self.assertIn("TASK-2", artifact["content"])

    def test_projection_fails_closed_for_unregistered_migration_target(self) -> None:
        self.state.initialize_launch(
            self.project,
            work_id="invalid-migration",
            refined_requirement="观察迁移。",
            source={"kind": "text", "value": "观察迁移"},
            hammer_root=self.hammer_root,
        )
        self.state.build_status(self.project, "invalid-migration")
        target = pathlib.Path(self.temp.name) / "not-a-worktree"
        (target / ".hammer" / "design").mkdir(parents=True)
        (target / ".hammer" / "design" / "session.md").write_text(
            "# fake\n", encoding="utf-8"
        )
        design = self.project / ".hammer" / "design"
        design.mkdir(exist_ok=True)
        (design / "session.md").write_text(
            "# Design\n\n## 审计日志\n\n"
            f"- 2026-08-21 10:00:00 +0800 | workspace.worktree "
            f"decision=migrated_away path={target}\n",
            encoding="utf-8",
        )

        status = self.state.build_status(self.project, "invalid-migration")

        self.assertTrue(status["stale"])
        self.assertFalse(status["controls_enabled"])
        self.assertIn("不是已注册的 Git worktree", status["projection_error"])

    def test_real_hammer_execute_markdown_projects_validation_state(self) -> None:
        self.state.initialize_launch(
            self.project,
            work_id="order-risk",
            refined_requirement="限制重复下单。",
            source={"kind": "text", "value": "限制重复下单"},
            hammer_root=self.hammer_root,
        )
        execute = self.project / ".hammer" / "execute"
        execute.mkdir()
        (execute / "session.md").write_text(
            "# Execute\n\n"
            "## 状态总览\n\n"
            "- current_task_ref: TASK-4\n"
            "- next_action: run-step-5\n"
            "- blocker: none\n",
            encoding="utf-8",
        )
        status = self.state.build_status(self.project, "order-risk")
        self.assertEqual(status["hammer"]["stage"], "validation")
        self.assertEqual(status["hammer"]["current_task"], "TASK-4")
        stages = {item["id"]: item["status"] for item in status["stages"]}
        self.assertEqual(stages["hammer_validation"], "running")
        self.assertEqual(stages["delivery"], "pending")

    def test_real_hammer_review_frontmatter_is_fail_closed(self) -> None:
        self.state.initialize_launch(
            self.project,
            work_id="review-work",
            refined_requirement="评审一个方案。",
            source={"kind": "text", "value": "评审一个方案"},
            hammer_root=self.hammer_root,
        )
        plan = self.project / ".hammer" / "plan"
        for path in plan.iterdir():
            path.unlink()
        plan.rmdir()
        design = self.project / ".hammer" / "design"
        design.mkdir()
        (design / "design.md").write_text("# Design\n", encoding="utf-8")
        for name, status in (
            ("review.md", "pass"),
            ("security-review.md", "blocked"),
            ("stability-review.md", "skipped_after_limit"),
        ):
            recommendation = "pass" if status == "blocked" else "blocked"
            (design / name).write_text(
                f"---\nstatus: {status}\nstatus_recommendation: {recommendation}\n---\n",
                encoding="utf-8",
            )
        blocked = self.state.build_status(self.project, "review-work")
        self.assertEqual(blocked["hammer"]["stage"], "review")
        self.assertEqual(blocked["hammer"]["status"], "blocked")
        (design / "security-review.md").write_text("---\nstatus: pass\n---\n", encoding="utf-8")
        passed = self.state.build_status(self.project, "review-work")
        self.assertEqual(passed["hammer"]["status"], "passed")

    def test_dashboard_can_start_before_hammer_creates_project_state(self) -> None:
        self.state.initialize_launch(
            self.project,
            work_id="new-work",
            refined_requirement="新增一个查询能力。",
            source={"kind": "text", "value": "新增一个查询能力"},
            hammer_root=self.hammer_root,
        )
        for path in sorted((self.project / ".hammer").rglob("*"), reverse=True):
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                path.rmdir()
        (self.project / ".hammer").rmdir()
        status = self.state.build_status(self.project, "new-work")
        self.assertEqual(status["hammer"]["stage"], "design")
        self.assertEqual(status["hammer"]["status"], "pending")
        self.assertFalse(status["stale"])

    def test_control_is_plugin_only_and_fixed_port_is_enforced(self) -> None:
        self.state.initialize_launch(
            self.project,
            work_id="order-risk",
            refined_requirement="限制重复下单。",
            source={"kind": "text", "value": "限制重复下单"},
            hammer_root=self.hammer_root,
        )
        before = self.hammer_snapshot()
        control = self.state.apply_control(
            self.project,
            "order-risk",
            {"action": "set-mode", "mode": "continuous"},
        )
        self.assertEqual(control["mode"], "continuous")
        self.assertEqual(before, self.hammer_snapshot())
        tasks = self.project / ".cosh" / "hammer-plugin" / "order-risk" / "coding" / "tasks.json"
        tasks.write_text(
            json.dumps(
                {
                    "status": "running",
                    "current_task": "P1-S1",
                    "tasks": [
                        {"id": "P1-S1", "hammer_parent": "P1", "status": "pending"}
                    ],
                }
            ),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(self.state.CoshHammerError, "Hammer"):
            self.state.apply_control(
                self.project,
                "order-risk",
                {"action": "authorize-task", "task": "P1-S1"},
            )
        with self.assertRaises(self.state.CoshHammerError):
            self.state.apply_control(
                self.project,
                "order-risk",
                {"action": "authorize-task", "task": "P2-S1"},
            )
        with self.assertRaises(self.state.CoshHammerError):
            self.state.apply_control(
                self.project, "order-risk", {"action": "advance-hammer"}
            )
        self.assertEqual(self.server.FIXED_PORT, 57172)
        parser = self.server.build_parser()
        self.assertEqual(parser.parse_args(["--project", str(self.project)]).port, 57172)
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            parser.parse_args(["--project", str(self.project), "--port", "49999"])

    def test_stale_cache_never_becomes_hammer_evidence(self) -> None:
        self.state.initialize_launch(
            self.project,
            work_id="order-risk",
            refined_requirement="限制重复下单。",
            source={"kind": "text", "value": "限制重复下单"},
            hammer_root=self.hammer_root,
        )
        live = self.state.build_status(self.project, "order-risk")
        cache = (
            self.project
            / ".cosh"
            / "hammer-plugin"
            / "order-risk"
            / "dashboard"
            / "dashboard-state.json"
        )
        self.assertTrue(cache.is_file())
        execute = self.project / ".hammer" / "execute"
        execute.mkdir()
        (execute / "session.md").write_text("{broken", encoding="utf-8")
        stale = self.state.build_status(self.project, "order-risk")
        self.assertTrue(stale["stale"])
        self.assertFalse(stale["controls_enabled"])
        self.assertIn("projection_error", stale)
        self.assertEqual(stale["work"], live["work"])
        self.assertNotIn("dashboard-state.json", self.hammer_snapshot())

    def test_hammer_dependency_is_rechecked_after_launch(self) -> None:
        self.state.initialize_launch(
            self.project,
            work_id="order-risk",
            refined_requirement="限制重复下单。",
            source={"kind": "text", "value": "限制重复下单"},
            hammer_root=self.hammer_root,
        )
        self.state.build_status(self.project, "order-risk")
        (self.hammer_root / "SKILL.md").unlink()
        status = self.state.build_status(self.project, "order-risk")
        self.assertTrue(status["stale"])
        self.assertFalse(status["controls_enabled"])
        self.assertIn("Hammer 不可用", status["projection_error"])

    def test_http_status_and_sse_emit_live_projection(self) -> None:
        self.state.initialize_launch(
            self.project,
            work_id="order-risk",
            refined_requirement="限制重复下单。",
            source={"kind": "text", "value": "限制重复下单"},
            hammer_root=self.hammer_root,
        )
        server = ThreadingHTTPServer(
            ("127.0.0.1", 0),
            self.server.make_handler(self.project, "order-risk"),
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = server.server_address[:2]
            with urllib.request.urlopen(f"http://{host}:{port}/api/status") as response:
                payload = json.loads(response.read().decode("utf-8"))
            self.assertEqual(payload["hammer"]["stage"], "plan")
            ready = self.starter.wait_until_ready(
                f"http://{host}:{port}/healthz",
                project=self.project,
                work="order-risk",
                timeout=1,
            )
            self.assertEqual(ready["work"], "order-risk")
            with urllib.request.urlopen(f"http://{host}:{port}/events") as response:
                lines = []
                while True:
                    line = response.readline().decode("utf-8").strip()
                    if not line:
                        if lines:
                            break
                        continue
                    lines.append(line)
            self.assertIn("event: status", lines)
            data = next(line.removeprefix("data: ") for line in lines if line.startswith("data: "))
            self.assertEqual(json.loads(data)["work"], "order-risk")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_http_artifact_endpoint_reads_projected_output(self) -> None:
        self.state.initialize_launch(
            self.project,
            work_id="artifact-http",
            refined_requirement="查看 Hammer 计划。",
            source={"kind": "text", "value": "查看 Hammer 计划"},
            hammer_root=self.hammer_root,
        )
        plan = self.project / ".hammer" / "plan" / "plan.md"
        plan.write_text("# Hammer Plan\n", encoding="utf-8")
        server = ThreadingHTTPServer(
            ("127.0.0.1", 0),
            self.server.make_handler(self.project, "artifact-http"),
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = server.server_address[:2]
            query = urllib.parse.urlencode(
                {
                    "work": "artifact-http",
                    "scope": "hammer",
                    "path": "plan/plan.md",
                }
            )
            with urllib.request.urlopen(
                f"http://{host}:{port}/api/artifact?{query}"
            ) as response:
                artifact = json.loads(response.read().decode("utf-8"))
            self.assertEqual(artifact["content"], "# Hammer Plan\n")
            self.assertEqual(artifact["scope"], "hammer")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_dashboard_assets_use_sse_and_our_observation_board(self) -> None:
        html = (SKILL_DIR / "assets" / "dashboard" / "index.html").read_text(encoding="utf-8")
        js = (SKILL_DIR / "assets" / "dashboard" / "app.js").read_text(encoding="utf-8")
        self.assertIn("Cosh Hammer 研发观察板", html)
        for tab in (
            "overview",
            "requirement",
            "design",
            "review",
            "plan",
            "coding",
            "validation",
            "delivery",
            "artifacts",
        ):
            self.assertIn(f'data-tab="{tab}"', html)
        self.assertNotIn('id="controls"', html)
        self.assertIn("EventSource", js)
        self.assertIn("/events", js)
        self.assertIn("/api/status", js)
        self.assertIn("/api/artifact", js)
        self.assertNotIn("localStorage", js)
        self.assertIn("set-mode", js)
        self.assertIn("authorize-task", js)
        self.assertNotIn("authorize-hammer-task", js)
        self.assertIn("coding-parent-group", js)
        self.assertIn("checkpoint?.commit_sha", js)
        self.assertIn("data.coding?.controls_enabled", js)
        self.assertIn("Hammer 已暂停编码，Cosh 正在执行全局细分任务", js)
        for detail in ("修改文件", "关键符号", "实施步骤", "验收条件", "任务进度"):
            self.assertIn(detail, js)
        for layout in ("coding-workspace", "coding-task-rail", "coding-task-detail"):
            self.assertIn(layout, js)
        self.assertIn('data.coding?.next_action', js)
        self.assertIn("textContent", js)
        self.assertNotIn("innerHTML", js)


if __name__ == "__main__":
    unittest.main()
