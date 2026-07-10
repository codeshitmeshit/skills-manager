# OpenSpec Requirement Review Planner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `cosh-requirement-review-planner` 改造成以 OpenSpec 为唯一状态和主要信息源的需求评审与开发门禁编排 skill。

**Architecture:** `SKILL.md` 只保留稳定的编排原则、五个人工确认门禁、规格优先规则和异常停止策略；OpenSpec 的版本相关操作放入独立 reference，并要求执行时先读取当前项目安装生成的 skills、commands 与 schema。删除旧 `.cosh-docs` 状态查询脚本，用内容契约测试防止平行状态机回归。

**Tech Stack:** Markdown skill instructions、YAML agent metadata、Python `unittest` 内容契约测试、OpenSpec 官方 artifact-guided workflow。

---

## 文件结构

- 修改 `skills/cosh-requirement-review-planner/SKILL.md`：定义 OpenSpec 驱动的主流程、人工门禁、规格变更回退和质量检查。
- 新建 `skills/cosh-requirement-review-planner/references/openspec-workflow.md`：记录如何发现、安装、初始化、更新和调用项目实际提供的 OpenSpec 能力，以及信息源优先级。
- 保留 `skills/cosh-requirement-review-planner/references/technical-review-rubric.md`：只用于补充评审 OpenSpec design。
- 修改 `skills/cosh-requirement-review-planner/agents/openai.yaml`：更新 UI 描述和默认提示词。
- 删除 `skills/cosh-requirement-review-planner/scripts/requirement_status.py`：移除旧 `.cosh-docs` 状态读取入口。
- 新建 `tests/test_requirement_review_planner_skill.py`：验证主状态、门禁、安装失败策略、规格优先和旧状态机移除。

### Task 1: 建立 OpenSpec skill 内容契约测试

**Files:**
- Create: `tests/test_requirement_review_planner_skill.py`
- Test: `tests/test_requirement_review_planner_skill.py`

- [ ] **Step 1: 写入失败测试**

```python
from __future__ import annotations

import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skills" / "cosh-requirement-review-planner"


class RequirementReviewPlannerSkillTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.skill = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        cls.workflow = (SKILL_DIR / "references" / "openspec-workflow.md").read_text(
            encoding="utf-8"
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


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `python3 -m unittest tests.test_requirement_review_planner_skill -v`

Expected: FAIL，至少包含 `openspec-workflow.md` 不存在或“OpenSpec 是唯一主状态”缺失。

- [ ] **Step 3: 提交失败测试**

```bash
git add tests/test_requirement_review_planner_skill.py
git commit -m "test: define openspec review planner contract"
```

### Task 2: 新增 OpenSpec workflow 参考规范

**Files:**
- Create: `skills/cosh-requirement-review-planner/references/openspec-workflow.md`
- Test: `tests/test_requirement_review_planner_skill.py`

- [ ] **Step 1: 编写参考规范**

文件必须明确包含以下章节和规则：

```markdown
# OpenSpec 工作流依据

## 信息源优先级

1. 当前项目安装生成的 OpenSpec skills、commands 和 schema。
2. OpenSpec 当前版本官方文档与官方仓库。
3. 当前项目 `openspec/` 配置、自定义 schema 和已有 artifacts。
4. 本 skill 的技术评审规则。
5. 本 skill 的示例。

## 运行时发现

- 先检查当前项目和本地环境，不得假设某个版本专属命令必然存在。
- 优先使用当前项目实际提供的 OpenSpec skill 或 command。
- 读取 artifact 状态时使用 OpenSpec 能力，不解析平行的本地状态文件。

## 准备 OpenSpec

- 未安装：先告知用户，再按官方当前安装说明安装。
- 未初始化：先告知用户，再按当前版本提供的初始化能力初始化。
- 已安装但项目指令过期：展示影响，获得确认后按官方能力刷新。
- 安装、初始化、刷新或状态读取失败：停止流程，不得绕过 OpenSpec 编码。
- 不覆盖已有配置、自定义 schema 或 artifacts。

## Artifact 推进

- 按 OpenSpec 当前 schema 的依赖顺序创建或更新 artifacts。
- 每次推进前读取实际状态；完成后再次读取并报告状态。
- artifact 格式以项目实际 schema 为准，示例不得作为权威格式。

## 规格变化

- 实现期间需求变化时，立即暂停编码。
- 先更新规格并重新确认，再判断 design、tasks 和验证是否需要重做。
- 受影响阶段全部重新确认后才能恢复编码。

## 验证与归档

- 展示 OpenSpec 验证结果及关联测试证据。
- 用户确认测试结果并最终确认后，才调用当前版本提供的归档能力。
```

- [ ] **Step 2: 运行定向测试**

Run: `python3 -m unittest tests.test_requirement_review_planner_skill.RequirementReviewPlannerSkillTest.test_missing_openspec_is_announced_then_prepared tests.test_requirement_review_planner_skill.RequirementReviewPlannerSkillTest.test_runtime_discovery_precedes_version_specific_commands -v`

Expected: PASS。

- [ ] **Step 3: 提交 reference**

```bash
git add skills/cosh-requirement-review-planner/references/openspec-workflow.md
git commit -m "docs: add openspec workflow authority"
```

### Task 3: 重写需求评审 planner 主流程

**Files:**
- Modify: `skills/cosh-requirement-review-planner/SKILL.md`
- Reference: `skills/cosh-requirement-review-planner/references/openspec-workflow.md`
- Reference: `skills/cosh-requirement-review-planner/references/technical-review-rubric.md`
- Test: `tests/test_requirement_review_planner_skill.py`

- [ ] **Step 1: 更新 frontmatter description**

将 description 改为只描述触发场景，不概括内部步骤：

```yaml
description: 在产品需求澄清完成后，需要使用 OpenSpec 评审需求与技术方案、管理规格驱动开发、跟踪变更状态、执行人工确认门禁、处理中途需求变化或完成验证归档时使用。
```

- [ ] **Step 2: 用 OpenSpec 主流程替换旧状态机正文**

正文至少包含以下稳定结构：

```markdown
# OpenSpec 需求方案评审与执行规划

## 核心原则

- OpenSpec 是唯一主状态，也是规格、设计、任务、验证和归档的主要信息源。
- 所有代码变更都必须进入 OpenSpec，不得绕过 OpenSpec 直接编码。
- 本 skill 只增加产品澄清衔接、技术评审和人工确认门禁，不创建平行状态机。
- 执行前必须完整读取 `references/openspec-workflow.md`。

## 人工确认门禁

依次等待用户明确确认：规格、技术方案、任务清单、测试结果、最终归档。

## 工作流

1. 检查产品需求是否澄清；不足时使用 `cosh-product-clarifier`。
2. 展示需求总结，等待用户确认后才进入 OpenSpec。
3. 按 reference 检查并准备 OpenSpec，读取实际状态。
4. 使用当前项目 OpenSpec 能力创建或继续 change，生成并确认规格。
5. 生成或更新 design，读取 `technical-review-rubric.md` 完成补充评审，等待确认。
6. 生成或更新 tasks，等待确认。
7. 确认后才进入实现。
8. 使用 OpenSpec 验证并展示测试证据，等待确认。
9. 等待最终归档确认后，使用 OpenSpec 归档。

## 规格变化

编码期间发生任何需求变化时立即暂停编码，先更新规格并重新确认；受影响的技术方案、任务清单和验证也必须重新确认。

## 阻塞规则

OpenSpec 安装、初始化、更新、状态读取或 artifact 校验失败时停止，不得使用旧流程降级继续。

## 质量检查

- 当前状态来自 OpenSpec。
- 五个确认门禁均未跳过。
- 技术评审意见已反映到 OpenSpec artifacts。
- 实现与已确认规格一致。
- 归档前规格场景、任务和验证均完成。
```

不得保留旧 `.cosh-docs` 目录结构、JSON 阶段枚举、`checklist.md` 或 `todolist.md` 推进规则。

- [ ] **Step 3: 运行内容契约测试**

Run: `python3 -m unittest tests.test_requirement_review_planner_skill -v`

Expected: PASS。

- [ ] **Step 4: 运行仓库 skill 标准检查**

Run: `python3 -m unittest tests.test_skill_check -v`

Expected: PASS。

- [ ] **Step 5: 提交主流程改造**

```bash
git add skills/cosh-requirement-review-planner/SKILL.md tests/test_requirement_review_planner_skill.py
git commit -m "feat: drive requirement reviews with openspec"
```

### Task 4: 移除旧状态脚本并更新 agent metadata

**Files:**
- Delete: `skills/cosh-requirement-review-planner/scripts/requirement_status.py`
- Modify: `skills/cosh-requirement-review-planner/agents/openai.yaml`
- Modify: `tests/test_requirement_review_planner_skill.py`

- [ ] **Step 1: 增加旧脚本不存在的失败测试**

在测试类中加入：

```python
    def test_legacy_status_script_is_removed(self) -> None:
        self.assertFalse((SKILL_DIR / "scripts" / "requirement_status.py").exists())
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `python3 -m unittest tests.test_requirement_review_planner_skill.RequirementReviewPlannerSkillTest.test_legacy_status_script_is_removed -v`

Expected: FAIL，提示旧脚本仍存在。

- [ ] **Step 3: 删除旧状态脚本**

使用补丁删除 `skills/cosh-requirement-review-planner/scripts/requirement_status.py`；若空 `scripts/` 目录没有其他用途，不保留占位文件。

- [ ] **Step 4: 更新 agent metadata**

将 `agents/openai.yaml` 更新为：

```yaml
interface:
  display_name: "OpenSpec 需求方案评审"
  short_description: "用 OpenSpec 评审需求并执行规格驱动开发门禁"
  default_prompt: "Use $cosh-requirement-review-planner to review this clarified requirement with OpenSpec as the source of truth, wait for confirmation at each gate, and drive verification and archive."
```

- [ ] **Step 5: 运行定向测试与 skill 校验**

Run: `python3 -m unittest tests.test_requirement_review_planner_skill tests.test_skill_check -v`

Expected: PASS。

- [ ] **Step 6: 提交清理和 metadata**

```bash
git add skills/cosh-requirement-review-planner/agents/openai.yaml tests/test_requirement_review_planner_skill.py
git rm skills/cosh-requirement-review-planner/scripts/requirement_status.py
git commit -m "chore: remove legacy requirement state tracker"
```

### Task 5: 全量验证与文档一致性检查

**Files:**
- Verify: `skills/cosh-requirement-review-planner/SKILL.md`
- Verify: `skills/cosh-requirement-review-planner/references/openspec-workflow.md`
- Verify: `skills/cosh-requirement-review-planner/references/technical-review-rubric.md`
- Verify: `skills/cosh-requirement-review-planner/agents/openai.yaml`
- Verify: `tests/test_requirement_review_planner_skill.py`

- [ ] **Step 1: 搜索旧状态机残留**

Run:

```bash
rg -n "\.cosh-docs/requirment|status\.json|checklist_draft|checklist_confirmed|todolist_created|requirement_status" skills/cosh-requirement-review-planner
```

Expected: 无输出。

- [ ] **Step 2: 运行全部 Python 测试**

Run: `python3 -m unittest discover -s tests -v`

Expected: 全部 PASS。

- [ ] **Step 3: 运行 skill 快速校验**

Run:

```bash
python3 /Users/bytedance/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/cosh-requirement-review-planner
```

Expected: 输出 `Skill is valid!`。

- [ ] **Step 4: 检查补丁质量和变更范围**

Run:

```bash
git diff --check
git status --short
git diff -- skills/cosh-requirement-review-planner tests/test_requirement_review_planner_skill.py
```

Expected: `git diff --check` 无输出；变更只包含计划文件、目标 skill、新 reference、metadata、测试和旧脚本删除，不包含用户已有的无关修改。

- [ ] **Step 5: 提交最终验证修正（仅在产生修正时）**

```bash
git add skills/cosh-requirement-review-planner tests/test_requirement_review_planner_skill.py
git commit -m "test: verify openspec requirement review workflow"
```

如果验证没有产生新修改，则不创建空提交。
