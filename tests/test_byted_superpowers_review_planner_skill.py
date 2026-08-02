from __future__ import annotations

import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
GENERIC_DIR = ROOT / "skills" / "cosh-requirement-review-planner"
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
        self.assertNotIn("OpenSpec", self.skill)
        self.assertNotIn("openspec", self.skill.lower())

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
        self.assertIn("通用规则降级", self.review)

    def test_document_revision_restarts_the_complete_review(self) -> None:
        self.assertIn("技术文档修改", self.workflow)
        self.assertIn("重新进入知识门禁", self.workflow)
        self.assertIn("三路完整评审", self.workflow)
        self.assertIn("旧版本", self.workflow)
        self.assertIn("不能只复审", self.workflow)

    def test_coding_requires_minimal_surface_chinese_comments_and_logs(self) -> None:
        standards = (
            BYTED_DIR / "references" / "code-authoring-standards.md"
        ).read_text(encoding="utf-8")
        self.assertIn("优先复用", standards)
        self.assertIn("新增", standards)
        self.assertIn("中文注释", standards)
        self.assertIn("日志", standards)
        self.assertIn("不得扩大修改面", self.remote_ut)

    def test_remote_ut_is_the_only_business_unit_test_gate(self) -> None:
        self.assertIn("bits-remote-ut", self.remote_ut)
        self.assertIn("禁止运行本地业务 UT", self.remote_ut)
        self.assertIn("禁止调用 Hammer", self.remote_ut)
        self.assertIn("当前代码 SHA", self.remote_ut)

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

    def test_archive_is_local_gitignored_and_distills_rules(self) -> None:
        self.assertIn(".superpowers/byted-archive/", self.workflow)
        self.assertIn("gitignore", self.workflow)
        self.assertIn("会话轮数", self.workflow)
        self.assertIn("为什么需要多轮", self.workflow)
        self.assertIn("规则蒸馏", self.workflow)
        self.assertIn("不得自动修改", self.workflow)

    def test_generic_skill_keeps_its_original_identity(self) -> None:
        generic_skill = (GENERIC_DIR / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("name: cosh-requirement-review-planner", generic_skill)
        self.assertIn("OpenSpec", generic_skill)
        self.assertNotIn("cosh-byted-superpowers-review-planner", generic_skill)

    def test_byted_skill_has_no_legacy_framework_residue(self) -> None:
        for path in BYTED_DIR.rglob("*"):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            content = path.read_text(encoding="utf-8", errors="ignore").lower()
            self.assertNotIn("openspec", content, str(path))

    def test_every_direct_markdown_resource_link_exists(self) -> None:
        for relative in re.findall(r"\]\((references/[^)]+|scripts/[^)]+)\)", self.skill):
            with self.subTest(path=relative):
                self.assertTrue((BYTED_DIR / relative).is_file(), relative)


if __name__ == "__main__":
    unittest.main()
