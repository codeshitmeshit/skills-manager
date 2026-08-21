from __future__ import annotations

import importlib.util
import contextlib
import io
import json
import pathlib
import subprocess
import tempfile
import threading
import unittest
import urllib.request
import urllib.parse
from http.server import ThreadingHTTPServer


ROOT = pathlib.Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skills" / "cosh-hammer"
STATE_SCRIPT = SKILL_DIR / "scripts" / "cosh_hammer_state.py"
SERVER_SCRIPT = SKILL_DIR / "scripts" / "serve_cosh_hammer_dashboard.py"
STARTER_SCRIPT = SKILL_DIR / "scripts" / "start_cosh_hammer_dashboard.py"


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
            "references/coding-artifacts.md",
            "references/realtime-dashboard.md",
            "references/major-decisions.md",
            "scripts/cosh_hammer_state.py",
            "scripts/serve_cosh_hammer_dashboard.py",
            "scripts/start_cosh_hammer_dashboard.py",
            "assets/dashboard/index.html",
            "assets/dashboard/app.js",
            "assets/dashboard/styles.css",
        ):
            self.assertTrue((SKILL_DIR / relative).is_file(), relative)


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
            (design / name).write_text(f"---\nstatus: {status}\n---\n", encoding="utf-8")
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
        authorized = self.state.apply_control(
            self.project,
            "order-risk",
            {"action": "authorize-task", "task": "P1-S1"},
        )
        self.assertEqual(authorized["authorized_task"], "P1-S1")
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
        self.assertIn("textContent", js)
        self.assertNotIn("innerHTML", js)


if __name__ == "__main__":
    unittest.main()
