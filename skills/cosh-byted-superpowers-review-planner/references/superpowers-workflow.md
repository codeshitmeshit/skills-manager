# Superpowers 强门禁研发流程

## 目录

- 状态事实源
- 阶段顺序
- 技术文档修改闭环
- 原生产物
- 实施子任务
- 提交、测试与 Push
- 本地归档

## 状态事实源

原生 Superpowers 文件保存规格、计划和执行进度；`.superpowers/byted-work/<work-id>/` 保存字节知识、评审和控制证据。页面、API 和自然语言只调用同一个状态投影与转换验证器。

所有状态仅允许 `pending`、`running`、`blocked`、`passed`。前一阶段不是当前版本的 `passed` 时，后一阶段不得启动。文件存在、口头确认、隐藏按钮或旧版本结论都不是通过证据。

## 阶段顺序

必须按首次出现顺序推进：技术文档 → AI-Spec 知识门禁 → CodeGraph 事实扫描 → 稳定性评审 → 安全性评审 → 可行性评审 → 评审闭环 → Superpowers 规格 → 精确定位 → Superpowers 计划 → 实施子任务 → 远程 UT → 最终 CR → push → 本地归档。

任一证据缺失、损坏、过期或与文档版本、知识哈希、代码 SHA 不匹配时 `fail closed`。

## 技术文档修改闭环

存在阻塞风险点时，可以保持阻塞，也可以选择技术文档修改。修改时：

1. 生成新版本、SHA-256、修改摘要和 diff；
2. 将旧知识门禁、代码快照与三路结论标记为旧版本；
3. 重新进入知识门禁；
4. 重新执行 CodeGraph 与三路完整评审，不能只复审上次未通过项；
5. 保留历史轮次供观察和追溯。

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
