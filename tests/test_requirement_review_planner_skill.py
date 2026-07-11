from __future__ import annotations

import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skills" / "cosh-requirement-review-planner"


class RequirementReviewPlannerSkillTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.skill = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        workflow_path = SKILL_DIR / "references" / "openspec-workflow.md"
        cls.workflow = (
            workflow_path.read_text(encoding="utf-8") if workflow_path.exists() else ""
        )

    def test_openspec_is_the_only_primary_state(self) -> None:
        self.assertIn("OpenSpec 是唯一主状态", self.skill)
        self.assertIn("主要信息源", self.skill)
        self.assertNotIn("所有阶段都通过 `status.json`", self.skill)

    def test_all_code_changes_enter_openspec(self) -> None:
        self.assertIn("所有代码变更", self.skill)
        self.assertIn("不得绕过 OpenSpec", self.skill)

    def test_five_human_confirmation_gates_exist(self) -> None:
        for gate in ("规格", "技术方案", "任务清单", "测试结果", "最终归档"):
            with self.subTest(gate=gate):
                self.assertIn(gate, self.skill)

    def test_spec_changes_pause_implementation(self) -> None:
        self.assertIn("立即暂停编码", self.skill)
        self.assertIn("重新确认", self.skill)

    def test_implementation_defaults_to_one_task_at_a_time(self) -> None:
        self.assertIn("默认一次只实现一个", self.skill)
        self.assertIn("不能视为批量授权", self.skill)
        self.assertIn("等待用户确认继续下一个任务", self.skill)

    def test_each_task_requires_review_and_commit_confirmation(self) -> None:
        self.assertIn("等待用户 CR", self.skill)
        self.assertIn("CR 通过并明确同意提交", self.skill)
        self.assertIn("commit 成功后", self.skill)

    def test_batch_implementation_requires_explicit_authorization(self) -> None:
        self.assertIn("一次全部实现", self.skill)
        self.assertIn("批量实现", self.skill)
        self.assertIn("明确授权", self.skill)
        self.assertIn("不得自行推断", self.workflow)

    def test_task_state_updates_only_after_commit(self) -> None:
        self.assertIn("提交成功后", self.workflow)
        self.assertIn("更新对应 OpenSpec task 状态", self.workflow)
        self.assertIn("未提交", self.workflow)

    def test_missing_openspec_is_announced_then_prepared(self) -> None:
        self.assertIn("先告知用户", self.workflow)
        self.assertIn("安装", self.workflow)
        self.assertIn("初始化", self.workflow)
        self.assertIn("失败", self.workflow)
        self.assertIn("停止", self.workflow)

    def test_runtime_discovery_precedes_version_specific_commands(self) -> None:
        self.assertIn("当前项目", self.workflow)
        self.assertIn("skills", self.workflow)
        self.assertIn("commands", self.workflow)
        self.assertIn("schema", self.workflow)
        self.assertIn("不得假设", self.workflow)

    def test_legacy_parallel_state_artifacts_are_not_prescribed(self) -> None:
        for legacy in (
            ".cosh-docs/requirment/<需求名>",
            '"stage": "checklist_draft"',
            "生成 `todolist.md`",
        ):
            with self.subTest(legacy=legacy):
                self.assertNotIn(legacy, self.skill)

    def test_legacy_status_script_is_removed(self) -> None:
        self.assertFalse((SKILL_DIR / "scripts" / "requirement_status.py").exists())


if __name__ == "__main__":
    unittest.main()
