from __future__ import annotations

import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
BYTED_DIR = ROOT / "skills" / "cosh-byted-superpowers-review-planner"


class BytedSuperpowersReviewPlannerSkillTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.skill = (BYTED_DIR / "SKILL.md").read_text(encoding="utf-8")
        cls.metadata = (BYTED_DIR / "agents" / "openai.yaml").read_text(
            encoding="utf-8"
        )
        cls.workflow = (
            BYTED_DIR / "references" / "superpowers-workflow.md"
        ).read_text(encoding="utf-8")
        cls.review = (
            BYTED_DIR / "references" / "byted-admission-review.md"
        ).read_text(encoding="utf-8")
        cls.remote_ut = (
            BYTED_DIR / "references" / "byted-coding-remote-ut.md"
        ).read_text(encoding="utf-8")

    def test_identity_uses_native_superpowers(self) -> None:
        self.assertIn("name: cosh-byted-superpowers-review-planner", self.skill)
        self.assertIn("字节", self.skill)
        self.assertIn("Superpowers", self.skill)
        self.assertIn("$cosh-byted-superpowers-review-planner", self.metadata)

    def test_required_references_exist(self) -> None:
        for relative in (
            "references/superpowers-workflow.md",
            "references/byted-admission-review.md",
            "references/byted-coding-remote-ut.md",
            "references/realtime-dashboard.md",
            "references/code-authoring-standards.md",
            "references/codegraph-implementation-location.md",
            "references/implementation-accuracy.md",
        ):
            with self.subTest(path=relative):
                self.assertTrue((BYTED_DIR / relative).is_file(), relative)
                self.assertIn(relative, self.skill)

    def test_frontmatter_name_matches_directory(self) -> None:
        frontmatter = self.skill.split("---", 2)[1]
        match = re.search(r"^name:\s*(.+)$", frontmatter, re.MULTILINE)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1).strip(), BYTED_DIR.name)

    def test_workflow_is_a_fail_closed_ordered_gate(self) -> None:
        ordered_section = self.workflow.split("## 阶段顺序", 1)[1].split("##", 1)[0]
        ordered_terms = (
            "技术文档",
            "AI-Spec",
            "CodeGraph",
            "稳定性",
            "安全性",
            "可行性",
            "评审闭环",
            "Superpowers 规格",
            "Superpowers 计划",
            "远程 UT",
            "最终 CR",
            "push",
            "本地归档",
        )
        positions = [ordered_section.index(term) for term in ordered_terms]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("fail closed", self.skill)
        self.assertIn("前一阶段", self.skill)
        self.assertIn("不得进入后一阶段", self.skill)

    def test_review_uses_three_independent_reviewers(self) -> None:
        self.assertIn("稳定性", self.review)
        self.assertIn("安全性", self.review)
        self.assertIn("可行性", self.review)
        self.assertIn("三个独立", self.review)
        self.assertIn("风险点", self.review)
        self.assertIn("建议修改", self.review)
        self.assertIn("AI-Spec", self.review)
        self.assertNotIn("通用规则降级", self.review)
        self.assertIn("直接阻塞", self.review)

    def test_document_revision_compares_frozen_source_before_rerunning_review(self) -> None:
        self.assertIn("技术文档修改", self.workflow)
        self.assertIn("冻结快照", self.workflow)
        self.assertIn("revision-assessment.json", self.workflow)
        self.assertIn("carry-forward", self.workflow)
        self.assertIn("full-review", self.workflow)
        self.assertIn("从知识门禁执行完整流程", self.workflow)
        self.assertIn("fail closed", self.workflow)

    def test_coding_requires_minimal_surface_chinese_comments_and_logs(self) -> None:
        standards = (
            BYTED_DIR / "references" / "code-authoring-standards.md"
        ).read_text(encoding="utf-8")
        self.assertIn("优先复用", standards)
        self.assertIn("新增", standards)
        self.assertIn("中文注释", standards)
        self.assertIn("日志", standards)
        self.assertIn("不得扩大修改面", self.remote_ut)

    def test_single_mode_requires_explicit_task_authorization_and_full_worktree_scope(self) -> None:
        self.assertIn("authorized_task", self.skill)
        self.assertIn("Agent 不得代替用户调用推进控制", self.skill)
        self.assertIn("staged、unstaged、untracked", self.skill)
        self.assertIn("scope_violation", self.skill)
        self.assertIn("awaiting_approval", self.skill)

    def test_remote_ut_is_the_only_business_unit_test_gate(self) -> None:
        self.assertIn("bits-remote-ut", self.remote_ut)
        self.assertIn("禁止运行本地业务 UT", self.remote_ut)
        self.assertIn("禁止调用 Hammer", self.remote_ut)
        self.assertIn("当前代码 SHA", self.remote_ut)

    def test_hammer_is_mutually_exclusive_with_the_complete_workflow(self) -> None:
        self.assertIn("互斥", self.skill)
        self.assertIn("整个研发任务", self.skill)
        self.assertIn("hammer-design", self.skill)
        self.assertIn("hammer-execute", self.skill)
        self.assertIn("Hammer 状态", self.workflow)
        self.assertIn("不得切换", self.workflow)

    def test_single_task_mode_is_strictly_serial(self) -> None:
        self.assertIn("逐一任务校验", self.workflow)
        self.assertIn("一次只允许开发一个实施子任务", self.workflow)
        self.assertIn("远程 UT", self.workflow)
        self.assertIn("CR", self.workflow)
        self.assertIn("推进下一个任务", self.workflow)
        self.assertIn("暂存区", self.workflow)

    def test_task_commit_contract_is_conventional_and_chinese(self) -> None:
        self.assertIn("<type>: <中文摘要>", self.workflow)
        self.assertIn("<work-id>-task<序号>", self.workflow)
        self.assertIn("feat: 增加内部重试风险判断", self.workflow)

    def test_dashboard_is_optional_and_supports_multiple_works(self) -> None:
        dashboard = (
            BYTED_DIR / "references" / "realtime-dashboard.md"
        ).read_text(encoding="utf-8")
        self.assertIn("观察", dashboard)
        self.assertIn("不是唯一入口", dashboard)
        self.assertIn("多个开发任务", dashboard)
        self.assertIn("work=", dashboard)
        self.assertIn("SSE", dashboard)

    def test_skill_starts_and_opens_dashboard_before_ai_spec(self) -> None:
        dashboard = (
            BYTED_DIR / "references" / "realtime-dashboard.md"
        ).read_text(encoding="utf-8")
        self.assertIn("--port 57171 --open", self.skill)
        self.assertIn("AI-Spec 门禁前", self.skill)
        self.assertIn("系统默认浏览器", self.skill)
        self.assertIn("维护本 skill", self.skill)
        self.assertIn("<skill-root>/scripts/serve_superpowers_dashboard.py", self.skill)
        self.assertIn("--port 57171 --open", dashboard)
        self.assertIn("<skill-root>/scripts/serve_superpowers_dashboard.py", dashboard)
        self.assertIn("自动打开失败不阻塞", dashboard)
        self.assertIn("最终 URL", dashboard)

    def test_archive_is_local_gitignored_and_distills_rules(self) -> None:
        self.assertIn(".superpowers/byted-archive/", self.workflow)
        self.assertIn("gitignore", self.workflow)
        self.assertIn("会话轮数", self.workflow)
        self.assertIn("为什么需要多轮", self.workflow)
        self.assertIn("规则蒸馏", self.workflow)
        self.assertIn("不得自动修改", self.workflow)

    def test_every_direct_markdown_resource_link_exists(self) -> None:
        for relative in re.findall(r"\]\((references/[^)]+|scripts/[^)]+)\)", self.skill):
            with self.subTest(path=relative):
                self.assertTrue((BYTED_DIR / relative).is_file(), relative)


if __name__ == "__main__":
    unittest.main()
