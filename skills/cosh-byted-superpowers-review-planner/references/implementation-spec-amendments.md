# 实施期规格附加修正规范

## 适用条件

仅当 Superpowers 规格、定位和计划已经通过，且存在当前已授权实施 Task 时使用。实现过程中修改 `docs/superpowers/specs/` 下的当前规格，默认把变更同步为当前 Task 的附加修正，不重新运行 `superpowers:brainstorming`，不重写原规格证据、定位证据或计划。

只有用户在当前轮明确要求“重新生成 Superpowers 规格/计划”时，才放弃附加修正路径并执行完整重建。历史上的“继续”“调整一下”或规格文件发生变化都不构成重建授权。

若变更无法完整收敛到当前 Task，例如改变任务拆分、影响已完成 Task 或扩大后续 Task 的职责，保持阻塞并询问用户是否重新生成，不得自动重建或静默改写其他 Task。

## 自动同步流程

规格修改后立即完成以下动作，再继续编码：

1. 读取当前 `authorized_task`、原 `spec.json`、`plan.json` 和已有规格附加修正链。
2. 计算上一有效规格 SHA、修正后规格 SHA、修改摘要与完整 diff。
3. 从修正后规格生成当前 Task 的完整有效覆盖，包含标题、允许文件、接口、步骤和验收条件；未变化字段也必须保留，禁止只写局部增量造成隐式继承。
4. 写入 `evidence/spec-amendment-task<N>.json`。同一 Task 再次修正规格时压缩更新同一文件：保留该 Task 首次进入修正时的 `base_spec_sha256`，把 `amended_spec_sha256`、完整 diff 和任务覆盖更新到最新状态；后续 Task 的新修正以上一有效规格 SHA 为基线形成链。
5. 将规格文件与当前 Task 代码一起暂存和提交。原 `spec.json`、`location.json`、`plan.json` 及 Superpowers plan 保持不变。
6. 使用附加修正后的 Task 范围检查 staged、unstaged、untracked；重新运行当前 Task 的远程 UT 和 CR。

## 证据结构

```json
{
  "status": "passed",
  "task": 2,
  "spec_path": "docs/superpowers/specs/YYYY-MM-DD-<work>-design.md",
  "base_spec_sha256": "<上一有效规格 SHA-256>",
  "amended_spec_sha256": "<当前规格 SHA-256>",
  "base_plan_sha256": "<原 Superpowers plan SHA-256>",
  "summary": "<本轮规格修正摘要>",
  "diff": "<相对上一有效规格的完整 diff>",
  "task_override": {
    "title": "<修正后的当前 Task 标题>",
    "allowed_files": ["<完整有效文件范围>"],
    "interfaces": ["<完整有效接口契约>"],
    "steps": ["<完整有效实施步骤>"],
    "acceptance_criteria": ["<完整有效验收条件>"]
  },
  "updated_at": "<RFC 3339 时间>"
}
```

当前 Task 首次修正时，`base_spec_sha256` 取修正链此前最后一个有效 SHA；没有历史修正时取 `spec.json.sha256`。同一 Task 后续修正必须保持这个基线不变，并重新记录从该基线到最新正文的完整 diff。`base_plan_sha256` 始终绑定未重建的原计划。

## 门禁行为

- 规格内容变化但缺少有效附加修正：规格、定位、计划和实施保持阻塞，修复提示为“同步当前 Task 规格附加修正”，不得提示自动重新生成。
- 附加修正有效：规格阶段显示通过及 `amendment_task`；定位和计划继续使用原基线证据；当前 Task 投影使用 `task_override`。
- 历史 Task 的附加修正持续构成有效规格链，但不得覆盖后续 Task。
- 当前 Task 已提交、等待下一 Task 授权或最后一个 Task 已完成时，历史修正链仍持续有效。此时出现未归属的新规格改动，先要求明确修正归属，不得回退为“重新生成”。
- 附加修正、规格文件、原规格 SHA、原计划 SHA、Task 编号或修正链不匹配时 `fail closed`。
- 附加修正改变任务快照，当前 Task 既有远程 UT 和 CR 自动失效；规格文件未完整暂存时不得提交或推进。
