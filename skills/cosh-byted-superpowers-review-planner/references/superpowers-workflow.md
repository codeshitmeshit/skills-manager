# Superpowers 强门禁研发流程

## 目录

- 状态事实源
- 研发引擎互斥
- 阶段顺序
- 技术文档修改闭环
- 原生产物
- 实施子任务
- 提交、测试与 Push
- 本地归档

## 状态事实源

原生 Superpowers 文件保存规格、计划和执行进度；`.superpowers/byted-work/<work-id>/` 保存字节知识、评审和控制证据。页面、API 和自然语言只调用同一个状态投影与转换验证器。

所有状态仅允许 `pending`、`running`、`blocked`、`passed`。前一阶段不是当前版本的 `passed` 时，后一阶段不得启动。文件存在、口头确认、隐藏按钮或旧版本结论都不是通过证据。

## 研发引擎互斥

创建开发任务时在 `workflow.json` 固定记录 `engine: superpowers`。该字段缺失、被改为 `hammer` 或其他值时，从技术文档入口直接阻塞，后续评审、规格、计划、实施、测试和 push 均不得继续。

同一开发任务只能由一个研发引擎拥有。从接收技术方案到本地归档，禁止调用任何 Hammer skill 或命令，禁止读取、继承或写入任何 Hammer 状态和产物，也不得把 Hammer 的 design、plan、execute、report、sync、knowledge、lite 或测试结果转换成本流程证据。启动本流程后不得切换到 Hammer；已经由 Hammer 启动的任务也不得接入本流程。

如需更换研发引擎，先停止并归档当前任务，再使用新的任务标识从零开始。两个任务的文档版本、评审证据、计划、提交授权和测试结果不得复用。

## 阶段顺序

必须按首次出现顺序推进：技术文档 → AI-Spec 知识门禁 → CodeGraph 事实扫描 → 稳定性评审 → 安全性评审 → 可行性评审 → 评审闭环 → Superpowers 规格 → 精确定位 → Superpowers 计划 → 实施子任务 → 远程 UT → 最终 CR → push → 本地归档。

任一证据缺失、损坏、过期或与文档版本、知识哈希、代码 SHA 不匹配时 `fail closed`。

## 技术文档修改闭环

存在阻塞风险点时，可以保持阻塞，也可以选择技术文档修改。全量评审完成后，把当时的技术文档复制为不可变冻结快照，记录版本与 SHA-256。再次修改时：

1. 生成新版本、SHA-256、修改摘要和相对冻结文档的 diff；
2. 按准入评审规则写入 `evidence/revision-assessment.json`；
3. `carry-forward` 判断有效时，把冻结版本的知识门禁、CodeGraph、三路评审、闭环和后续派生产物视为当前文档的继承证据；原始证据文件保持不变；
4. `full-review`、判断证据缺失、过期、格式错误、冻结文件哈希不符或任一语义维度变化时，将旧证据标记为历史并从知识门禁执行完整流程；
5. 全量评审通过后刷新冻结基线；始终保留历史轮次供观察和追溯。

循环次数不设上限。当前版本未全部通过时不能生成规格。

## 原生产物

```text
docs/superpowers/specs/YYYY-MM-DD-<work>-design.md
docs/superpowers/plans/YYYY-MM-DD-<work>.md
.superpowers/sdd/<plan>/progress.md
```

不得往这些文件写字节专属 JSON 控制字段。计划按 `### Task N:`、`**Files:**`、`**Interfaces:**` 和 checkbox 步骤解析。

## 实施子任务

### 实施期规格修正

规格、定位和计划通过后，规格文件变更不再默认回退并重建 Superpowers。存在当前授权 Task 时，按 [`implementation-spec-amendments.md`](implementation-spec-amendments.md) 写入 `evidence/spec-amendment-task<N>.json`，以完整 `task_override` 替代原计划中当前 Task 的执行契约；原规格证据、定位证据、计划文件及计划证据保持不变。

附加修正进入当前 Task 快照，使旧远程 UT 和 CR 失效。规格文件必须随当前 Task 完整暂存和提交。已完成 Task 的修正只作为有效规格链历史，不得覆盖后续 Task。只有用户当轮明确要求重新生成 Superpowers，或变更无法收敛到当前 Task 且用户确认重建时，才使原生规格、定位和计划失效。

### 逐一任务校验

一次只允许开发一个实施子任务。Task 1 初始授权；后续任务必须由 `control.json.task_authorization.authorized_task` 明确授权。当前任务的文件、符号、变量和接口形成范围锁；每次写入前读取授权，写入后检查 staged、unstaged、untracked 全工作区。范围外或未授权任务改动立即阻塞，不能先保留改动再继续其他任务。

Tasks 全局设置把验证策略持久化到 `workflow.json.validation_strategy`：

- `final`（默认）：每个 Task 的计划必须用 `- Test: \`<path>\`` 显式声明测试交付物，不根据目录或文件名猜测。全部 `Test:` 文件必须与实现一起暂存，且不得以删除状态交付。推进不要求逐 Task 远程 UT/CR；commit 记录暂存文件清单和 `validation_status=pending_final`。全部 Task checkpoint 后统一验证累计 HEAD。
- `per_task`：保持逐 Task 远程 UT 和 CR，证据必须绑定当前任务快照，随后才能提交。

首个 Task 提交后验证策略锁定；`commit-taskN.json.validation_strategy` 是权威锁定证据，并必须与 Git 历史中 `<work-id>-taskN` checkpoint trailer 双向对账。与 `workflow.json` 冲突、checkpoint 之间不一致、commit 不可解析、证据损坏或删除时必须 `fail closed`。历史 checkpoint 没有该字段时按 `per_task` 兼容。页面的“推进下一个任务”只在完整工作区快照满足范围、全部交付物已暂存且满足所选验证策略时启用；置灰时必须展示全部 blocker。用户当轮明确触发推进后，后端只提交当前暂存区交付物并原子记录下一任务授权。Agent 不得自行调用推进动作，也不得用历史“继续全部任务”等话术替代本轮授权。

### 连续推进

连续模式必须由用户显式切换，只取消人工点击等待。范围锁、全工作区校验、测试文件交付、提交和异常停止仍逐任务执行；远程 UT/CR 的时机服从全局验证策略，页面不得渲染“推进下一个任务”按钮。

## 提交、测试与 Push

提交格式：

```text
<type>: <中文摘要>

<work-id>-task<序号>
```

例如：

```text
feat: 增加内部重试风险判断

optimize-order-risk-check-task1
```

推进前校验暂存区非空且没有范围外文件；存在规格附加修正时同时校验规格文件已完整暂存。`final` 策略还必须确认当前 Task 计划声明的全部测试文件均在暂存区，checkpoint 只代表“已实现，待统一验证”。`per_task` 策略的远程 UT 与 CR 绑定包含有效规格修正链的当前任务快照。无论采用哪种策略，完整远程 UT 和最终 CR 都必须绑定全部 Task 完成后的当前 HEAD 并通过，才允许普通 push。

## 本地归档

push 成功自动归档，取消或长期阻塞允许手动归档。产物保存到：

```text
.superpowers/byted-archive/<work-id>/<completed-at>-retrospective.md
```

该目录必须加入 gitignore。归档记录会话轮数和覆盖范围、关键决策、评审与返工证据，并分析为什么需要多轮讨论。规则蒸馏候选包含证据、收益、适用范围、置信度和建议目标；不得自动修改公共 skill。
