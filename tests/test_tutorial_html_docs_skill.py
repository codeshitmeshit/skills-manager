from pathlib import Path
import re
import unittest


SKILL = Path(__file__).resolve().parents[1] / "skills" / "cosh-tutorial-html-docs"


class TutorialHtmlDocsSkillTest(unittest.TestCase):
    def test_reverse_workflow_is_reachable_from_single_entry(self):
        entry = (SKILL / "SKILL.md").read_text()
        self.assertIn("完整仓库逆向", entry)
        self.assertIn("普通教程", entry)
        references = re.findall(r"\]\((references/[^)]+)\)", entry)
        self.assertIn("references/project-reverse-workflow.md", references)
        for reference in references:
            self.assertTrue((SKILL / reference).is_file(), reference)

    def test_reverse_mode_retains_evidence_and_quality_gates(self):
        workflow = (SKILL / "references/project-reverse-workflow.md").read_text()
        for requirement in (
            "Subagent", "70%", "30%", "linkage_inventory",
            "code_excerpts", "verification", "debug_points",
            "证据矩阵", "交叉质询", "质量闸门", "未能从历史验证",
        ):
            self.assertIn(requirement, workflow)
        self.assertNotIn("安装 `cosh-tutorial-html-docs`", workflow)
        self.assertNotIn("cosh-project-reverse-tutorial", workflow)

    def test_shared_templates_remain_self_contained(self):
        for filename in ("guide-template.html", "tutorial-page-template.html"):
            html = (SKILL / "assets" / filename).read_text()
            self.assertIn("<style>", html)
            self.assertNotRegex(html, r'<(?:script|link)[^>]+(?:src|href)=["\x27]https?://')


if __name__ == "__main__":
    unittest.main()
