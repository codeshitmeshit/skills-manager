# Cosh Hammer 全局编码阶段设计

## 目标

Hammer 继续负责需求、设计、三路评审、计划、验证和交付。Hammer Plan Ready 后，Cosh 一次性读取全部 coding parent tasks，基于 CodeGraph 与源码事实生成完整编码任务树，并在独立编码阶段完成所有业务代码。全部编码任务完成后，Cosh 只交还一次，Hammer 直接进入编码后的原生 Gate。

本设计替换现有“逐个 Hammer 父任务接管、拆分、交还、再接管”的模型。

## 不变边界

- 不修改 Hammer skill、运行时或 `.hammer/**`。
- Hammer 仍是唯一主流程、阶段状态机和最终交付门禁。
- Cosh 只写 `.cosh/hammer-plugin/<work-id>/**`。
- Hammer Plan、Design 和 Review 产物保持只读。
- 观察板固定使用 Cosh Hammer 观察板与端口 `57172`。
- 状态不一致、计划变化、活动目录变化或观察板 stale 时 fail closed。

## 阶段模型

1. Hammer 完成 Plan Ready，`verify-handoff` 验证全部 coding parent tasks 及触发语句。
2. Hammer Execute 到达第一个 coding parent task 后暂停原生编码 worker。
3. Cosh 运行一次 `verify-coding`，确认入口 task、Plan SHA、Execute session 和活动目录一致。
4. Cosh 对全部 Hammer coding parent tasks 统一执行 CodeGraph、源码复核和依赖分析。
5. Cosh 一次性生成全局代码事实、预计修改面、精准定位、编码计划和完整细分任务树。
6. `activate-coding` 一次性取得整个编码阶段的所有权；Hammer 在此期间保持暂停。
7. Cosh 按全局顺序执行细分任务。单独模式逐任务等待授权，连续模式自动推进；两者都不能越过依赖、范围或状态门禁。
8. 每个细分任务通过时，以当前暂存区为交付物，完成范围校验并创建独立 commit/checkpoint。
9. 所有细分任务通过后，`complete-coding` 生成一次全局 `DONE` handoff，声明全部 Hammer coding parent tasks 已由 Cosh 完成。
10. Hammer 消费全局 handoff，跳过剩余原生 coding worker，进入远程 UT、CI、最终 CR、E2E 和交付。

## 全局任务树

`coding/tasks.json` 一次性包含所有父任务的细分任务：

```json
{
  "schema_version": 2,
  "status": "running",
  "current_task": "task1-fg",
  "hammer_task_order": ["Task 1", "Task 2", "Task 3"],
  "tasks": [
    {
      "id": "task1-fg",
      "hammer_parent": "Task 1",
      "title": "...",
      "description": "...",
      "expected_files": ["..."],
      "symbols": ["..."],
      "steps": ["..."],
      "dependencies": [],
      "acceptance": ["..."],
      "status": "pending"
    },
    {
      "id": "task2-query",
      "hammer_parent": "Task 2",
      "dependencies": ["task1-fg"],
      "status": "pending"
    }
  ]
}
```

约束：

- 每个 Hammer coding parent task 至少映射一个 Cosh 细分任务。
- `hammer_parent` 必须属于 Plan Handoff 的完整父任务顺序。
- 任务在全局列表中按父任务顺序排列；同一父任务内保持实现顺序。
- 跨父任务依赖必须显式写入 `dependencies`，不得依赖隐含顺序。
- 后续任务的预计文件、符号和步骤必须来自同一轮 CodeGraph 与源码复核，不得只复制 Hammer 标题。
- 实现期事实变化使用 amendment 更新受影响任务及依赖，不重新生成整套 Hammer Plan，除非用户明确要求。

## 编码所有权

`coding/ownership.json` 表示完整编码阶段所有权：

```json
{
  "status": "cosh_active",
  "scope": "full_coding_stage",
  "owner": "cosh",
  "hammer_status": "paused_for_cosh",
  "hammer_entry_task": "Task 1",
  "hammer_task_order": ["Task 1", "Task 2", "Task 3"],
  "plan_sha256": "..."
}
```

取得所有权后不再在父任务边界交还 Hammer，也不需要 `authorize-hammer-task`。单独/连续模式只控制全局 Cosh 细分任务。只有所有细分任务和 commit 证据完整后，所有权才能变为 `returned_to_hammer`。

## 单独推进与连续推进

默认使用单独推进：

- 观察板只允许授权当前 pending 任务。
- 依赖未通过、任务范围不完整或工作区存在越界改动时禁止授权或提交。
- 当前任务通过并提交后停在下一任务，等待新的用户授权。

连续推进：

- 仍按同一全局任务顺序和依赖图执行。
- 每个任务仍独立形成 commit/checkpoint。
- 任一任务 blocked、范围越界、计划失效、所有权丢失或需要重大决策时立即停止。

## 任务提交门禁

每个任务完成时，以 Git 暂存区为唯一交付快照：

- 暂存区不能为空。
- 暂存路径必须属于任务 `expected_files`；删除或重命名同样参与范围校验。
- 工作区中不得存在属于未来任务的未暂存或未跟踪实现改动。
- 验收证据必须绑定提交前的暂存快照。
- 门禁通过后由 Cosh 创建一个任务 commit，并在 checkpoint 中记录 `commit_sha`、文件清单、快照哈希和证据。
- commit 成功后才能把任务标为 `passed` 并解锁下一任务。

## 全局交还

最后一个任务通过后，`complete-coding` 校验：

- `tasks.json` 中所有任务均为 `passed`。
- 每个任务都有与 Git 历史一致的 checkpoint 和 commit。
- Plan SHA、活动目录和 Hammer Execute 入口状态仍与接管时一致。
- 当前 HEAD 等于最后一个任务 checkpoint。

成功后写入 `coding/coding-stage-handoff.json`：

```json
{
  "status": "DONE",
  "completed_hammer_tasks": ["Task 1", "Task 2", "Task 3"],
  "task_commits": [{"task": "task1-fg", "commit_sha": "..."}],
  "next_action": "hammer_continue_after_coding_stage"
}
```

Hammer prompt 必须要求控制器把该 handoff 视为全部 coding parent tasks 已完成，并直接进入编码后 Gate。Cosh 不写 Hammer session 或任务状态。

## 观察板

- “计划”页只展示 Hammer Plan 与 Handoff 产物。
- “编码”页独立展示完整 Cosh 全局任务树，而不是当前 Hammer 父任务的局部列表。
- 左侧按父任务分组展示全部细分任务；右侧展示选中任务详情。
- 顶部展示全局完成数、当前任务、推进模式和编码所有权。
- 单独模式只显示当前细分任务授权按钮；不再显示父任务授权按钮。
- 全部任务通过后显示“编码完成，等待交还 Hammer”。

## 兼容与迁移

- `schema_version: 1`、只有单一 `hammer_parent` 的旧任务状态继续只读展示，不允许自动升级或继续推进。
- 新 work 只生成 `schema_version: 2` 全局任务树。
- 旧 work 如需继续，必须从 Hammer Plan Ready 重新执行全局细化；不得拼接旧局部任务冒充完整计划。

## 验证

- 全局激活拒绝遗漏任一 Hammer coding parent task。
- 支持跨父任务依赖，但拒绝未知依赖和逆序依赖。
- 单独模式在每个细分任务后停止；连续模式可跨父任务组推进。
- 未来任务的未暂存或未跟踪改动阻塞当前任务提交。
- 每个任务生成独立 commit/checkpoint。
- 中间父任务完成不会生成 Hammer handoff，也不会释放所有权。
- 全部任务完成后只生成一次全局 handoff。
- 旧 schema 只读、Plan SHA 变化和 stale 状态均 fail closed。
