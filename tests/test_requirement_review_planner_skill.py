from __future__ import annotations

import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skills" / "cosh-requirement-review-planner"


class RequirementReviewPlannerSkillTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.skill = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        cls.accuracy = (
            SKILL_DIR / "references" / "implementation-accuracy.md"
        ).read_text(encoding="utf-8")
        cls.codegraph = (
            SKILL_DIR / "references" / "codegraph-modification-point.md"
        ).read_text(encoding="utf-8")
        cls.workflow = (
            SKILL_DIR / "references" / "openspec-workflow.md"
        ).read_text(encoding="utf-8")
        cls.dashboard = (
            SKILL_DIR / "references" / "realtime-dashboard.md"
        ).read_text(encoding="utf-8")
        cls.authoring = (
            SKILL_DIR / "references" / "code-authoring-standards.md"
        ).read_text(encoding="utf-8")

    def test_identity_and_chinese_trigger_description(self) -> None:
        self.assertIn("name: cosh-requirement-review-planner", self.skill)
        self.assertIn("在产品需求澄清后", self.skill)
        self.assertIn("按 task 实现和 CR", self.skill)

    def test_generic_flow_has_no_byted_technical_review_gate(self) -> None:
        self.assertIn("不启动 AI-Spec 或稳定性、安全性、可行性评审", self.skill)
        self.assertNotIn("技术评审前完整读取", self.skill)
        self.assertNotIn("technical-review-rubric.md", self.skill)

    def test_openspec_remains_the_only_primary_state(self) -> None:
        self.assertIn("OpenSpec 是规格、设计、任务、验证和归档的唯一主状态", self.skill)
        self.assertIn("不创建平行状态机", self.skill)

    def test_implementation_requires_dual_evidence(self) -> None:
        self.assertIn("规格事实 + 仓库事实", self.skill)
        self.assertIn("修改点证据卡", self.accuracy)
        self.assertIn("任一关键答案缺失时先补取证", self.accuracy)

    def test_source_and_generated_code_boundary_is_explicit(self) -> None:
        self.assertIn("只修改源文件", self.skill)
        self.assertIn("仓库原生协议定位", self.skill)
        self.assertIn("不直接修改 `gen`、`kitex_gen`", self.accuracy)

    def test_tasks_map_scenarios_code_and_tests(self) -> None:
        self.assertIn("scenario -> 文件/符号/变量 -> 测试", self.skill)
        for field in ("对应 scenario", "仓库证据", "精确文件/符号/变量", "验证命令"):
            with self.subTest(field=field):
                self.assertIn(field, self.skill)

    def test_codegraph_precedes_modification_point_and_design(self) -> None:
        self.assertIn(
            "CodeGraph 分析先于修改点确认，修改点确认先于 design 创建",
            self.skill,
        )
        self.assertIn(
            "CodeGraph 发现 -> 源码复核 -> 变量流确认 -> 修改点选择 -> 用户确认 -> 创建 design",
            self.codegraph,
        )
        self.assertIn("确认前不得创建或填写 design", self.skill)

    def test_modification_point_is_variable_level(self) -> None:
        for field in (
            "仓库与基线",
            "文件",
            "符号",
            "变量",
            "类型",
            "当前值来源",
            "相关读取行",
            "相关写入行",
        ):
            with self.subTest(field=field):
                self.assertIn(field, self.codegraph)

    def test_codegraph_results_require_source_verification(self) -> None:
        self.assertIn("当前 commit 的源码", self.skill)
        self.assertIn("不直接替代当前 commit 的源码", self.codegraph)
        self.assertIn("索引可能过期", self.skill)

    def test_design_cannot_expand_beyond_confirmed_points(self) -> None:
        self.assertIn("只基于已确认修改点创建 OpenSpec design", self.skill)
        self.assertIn("退回 CodeGraph 分析和修改点确认", self.codegraph)

    def test_realtime_dashboard_keeps_controls_inside_openspec(self) -> None:
        self.assertIn("除受控执行授权外只读消费 OpenSpec", self.skill)
        self.assertIn("不修改 checkbox、规格、design 或代码", self.skill)
        self.assertIn("scripts/serve_openspec_dashboard.py", self.skill)
        self.assertIn("Server-Sent Events 长连接", (
            SKILL_DIR / "references" / "realtime-dashboard.md"
        ).read_text(encoding="utf-8"))

    def test_each_modification_has_page_and_artifact_tabs(self) -> None:
        dashboard_reference = (
            SKILL_DIR / "references" / "realtime-dashboard.md"
        ).read_text(encoding="utf-8")
        self.assertIn("每个修改点链接到独立 URL", dashboard_reference)
        self.assertIn("规格、Design、Tasks、验证、代码证据", dashboard_reference)
        self.assertIn("/api/document?path=...", dashboard_reference)

    def test_dashboard_supports_single_and_continuous_execution(self) -> None:
        dashboard_reference = (
            SKILL_DIR / "references" / "realtime-dashboard.md"
        ).read_text(encoding="utf-8")
        self.assertIn("连续推进", dashboard_reference)
        self.assertIn("单独推进", dashboard_reference)
        self.assertIn("推进下一个任务", dashboard_reference)
        self.assertIn("CR 通过和提交授权", dashboard_reference)
        self.assertIn("不修改 task checkbox", dashboard_reference)

    def test_natural_language_control_does_not_require_page_interaction(self) -> None:
        self.assertIn("网站是实时观察与可选控制界面", self.skill)
        self.assertIn("页面不是唯一控制入口", self.workflow)
        self.assertIn("网站未打开或用户不操作页面时也能正常执行", self.dashboard)
        self.assertIn("与 `advance-next` 相同", self.dashboard)

    def test_natural_language_advance_preserves_commit_safety(self) -> None:
        for rule in (
            "只提交整个暂存区",
            "不执行 `git add`",
            "不创建空提交",
            "commit 或 hook 失败时不记录授权",
        ):
            with self.subTest(rule=rule):
                self.assertIn(rule, self.dashboard)

    def test_natural_language_mode_changes_share_dashboard_state(self) -> None:
        self.assertIn("`set-mode continuous`", self.dashboard)
        self.assertIn("`set-mode single`", self.dashboard)
        self.assertIn("`cosh-dashboard-control` 元数据", self.dashboard)
        self.assertIn("通过 SSE 自动显示新模式", self.dashboard)

    def test_baseline_and_diff_checks_precede_completion(self) -> None:
        self.assertIn("修改前行为", self.skill)
        self.assertIn("修改后立即检查 diff", self.skill)
        self.assertIn("基线失败、环境问题还是本次回归", self.skill)

    def test_code_prefers_reuse_before_minimal_addition(self) -> None:
        self.assertIn("优先复用仓库已有能力", self.skill)
        self.assertIn("不能复用的证据", self.skill)
        self.assertIn("只有以上方案都无法安全满足", self.authoring)
        self.assertIn("避免无关重构、提前抽象", self.authoring)

    def test_core_logic_requires_chinese_comments(self) -> None:
        self.assertIn("核心业务逻辑必须有", self.skill)
        self.assertIn("中文注释", self.skill)
        self.assertIn("为什么需要该逻辑", self.authoring)
        self.assertIn("不要逐行翻译代码", self.authoring)

    def test_key_paths_require_safe_observable_logs(self) -> None:
        self.assertIn("关键分支、状态变化和失败路径", self.skill)
        self.assertIn("复用项目现有日志框架", self.authoring)
        self.assertIn("禁止记录密码、令牌、密钥", self.authoring)
        self.assertIn("采样、聚合或限频", self.authoring)

    def test_task_and_human_gates_are_preserved(self) -> None:
        self.assertIn("缺失或无效时默认为**单独推进**", self.skill)
        self.assertIn("当前 task CR 通过及提交授权", self.skill)
        self.assertIn("对剩余 tasks 的批量授权", self.skill)
        self.assertIn("最终归档确认", self.skill)

    def test_generic_baseline_has_no_byted_tool_binding(self) -> None:
        for tool in (
            "bytedcli ai-dev-pro afs",
            "byted-fg",
            "byted-eeconf",
            "byted-boefeature-deploy",
            "byted-codebase-ci",
            "EEConf/TCC",
        ):
            with self.subTest(tool=tool):
                self.assertNotIn(tool, self.skill)


if __name__ == "__main__":
    unittest.main()
