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

### 逐一任务校验

一次只允许开发一个实施子任务。当前任务的文件、符号、变量和接口形成范围锁；范围外修改阻塞推进。当前任务依次完成编码、远程 UT、CR、暂存区检查和提交，记录 commit SHA 后才解锁下一项。

当前 CR 未通过时，修复仍属于当前任务，重新执行远程 UT 和 CR。页面的“推进下一个任务”只在 CR 与远程 UT 均通过时启用。

### 连续推进

连续模式只取消人工点击等待。范围锁、远程 UT、CR、提交和异常停止仍逐任务执行；页面不得渲染“推进下一个任务”按钮。

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

推进前校验暂存区没有范围外文件、远程 UT 与 CR 绑定当前代码 SHA。完整远程 UT 和最终 CR 绑定当前 HEAD 并通过后，才允许普通 push。

## 本地归档

push 成功自动归档，取消或长期阻塞允许手动归档。产物保存到：

```text
.superpowers/byted-archive/<work-id>/<completed-at>-retrospective.md
```

该目录必须加入 gitignore。归档记录会话轮数和覆盖范围、关键决策、评审与返工证据，并分析为什么需要多轮讨论。规则蒸馏候选包含证据、收益、适用范围、置信度和建议目标；不得自动修改公共 skill。
