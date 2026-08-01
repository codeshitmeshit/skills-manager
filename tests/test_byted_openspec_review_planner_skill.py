from __future__ import annotations

import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
GENERIC_DIR = ROOT / "skills" / "cosh-requirement-review-planner"
BYTED_DIR = ROOT / "skills" / "cosh-byted-openspec-review-planner"


class BytedOpenSpecReviewPlannerSkillTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.generic_skill = (GENERIC_DIR / "SKILL.md").read_text(encoding="utf-8")
        cls.byted_skill = (BYTED_DIR / "SKILL.md").read_text(encoding="utf-8")

    def test_identity_is_kept_for_future_customization(self) -> None:
        self.assertIn("name: cosh-byted-openspec-review-planner", self.byted_skill)
        self.assertIn("当前研发流程与通用版完全一致", self.byted_skill)
        metadata = (BYTED_DIR / "agents" / "openai.yaml").read_text(encoding="utf-8")
        self.assertIn("字节版 OpenSpec 需求方案评审", metadata)
        self.assertIn("$cosh-byted-openspec-review-planner", metadata)

    def test_workflow_body_matches_generic_baseline(self) -> None:
        generic_body = self.generic_skill.split("---", 2)[2]
        byted_body = self.byted_skill.split("---", 2)[2]
        self.assertEqual(byted_body, generic_body)

    def test_all_shared_resources_match_generic_baseline(self) -> None:
        shared_files = (
            "assets/dashboard/app.js",
            "assets/dashboard/index.html",
            "assets/dashboard/styles.css",
            "references/code-authoring-standards.md",
            "references/implementation-accuracy.md",
            "references/codegraph-modification-point.md",
            "references/openspec-workflow.md",
            "references/realtime-dashboard.md",
            "references/technical-review-rubric.md",
            "scripts/serve_openspec_dashboard.py",
        )
        for relative_path in shared_files:
            with self.subTest(path=relative_path):
                self.assertEqual(
                    (BYTED_DIR / relative_path).read_bytes(),
                    (GENERIC_DIR / relative_path).read_bytes(),
                )

    def test_no_byted_specific_development_flow_remains(self) -> None:
        all_text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in BYTED_DIR.rglob("*")
            if path.is_file() and path.suffix in {".md", ".py", ".js", ".html", ".css", ".yaml"}
        )
        for term in (
            "bytedcli ai-dev-pro afs",
            "byted-fg",
            "byted-eeconf",
            "byted-boefeature-deploy",
            "byted-codebase-mr",
            "byted-codebase-ci",
            "BOE 回归",
            "EEConf/TCC",
        ):
            with self.subTest(term=term):
                self.assertNotIn(term, all_text)
        self.assertIn("CodeGraph", all_text)
        self.assertFalse(
            (BYTED_DIR / "references" / "byted-implementation-accuracy.md").exists()
        )

    def test_generic_dashboard_and_natural_language_controls_remain(self) -> None:
        self.assertIn("七个人工门禁", self.byted_skill)
        self.assertIn("网站是实时观察与可选控制界面", self.byted_skill)
        self.assertIn("不是执行流程的前置条件或唯一入口", self.byted_skill)
        self.assertIn("`cosh-dashboard-control`", self.byted_skill)
        self.assertIn("连续推进", self.byted_skill)
        self.assertIn("单独推进", self.byted_skill)


if __name__ == "__main__":
    unittest.main()
