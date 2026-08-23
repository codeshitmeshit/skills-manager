# Cosh Hammer 延迟任务提交设计

## 背景

`cosh-hammer` 当前在细分任务验收通过时立即提交暂存区，并把 commit SHA 写入任务 checkpoint。这个行为过早关闭了当前任务：用户在看到实现结果后若还要补充修改，只能额外提交或改写历史。

本次调整把“实现完成”和“提交完成”拆成两个明确阶段。任务实现通过后先停留在待批准写入状态，用户可以继续修改；只有当前任务的最终暂存内容通过校验并创建独立 commit 后，下一任务才允许启动。

## 目标

- 细分任务实现通过后不立即创建 Git commit。
- 当前任务进入可观察的 `awaiting_commit` 状态，并继续持有编码推进权。
- 用户可以在批准写入前继续修改当前任务。
- 批准写入时以当时的 Git 暂存区作为唯一交付物，重新执行范围和工作区完整性校验。
- 每个细分任务仍然生成一个独立 commit/checkpoint。
- 任何模式都不能在前一任务成功提交前启动下一任务。
- 单独推进和连续推进只影响提交成功后的下一步，不绕过提交门禁。

## 非目标

- 不把全部细分任务压缩为一个最终提交。
- 不自动 amend 已经提交的历史任务。
- 不修改 Hammer、Hammer skill 或 `.hammer/**`。
- 不允许观察板缓存替代 Git、checkpoint 或 Cosh 所有权证据。

## 状态模型

每个 schema v2 细分任务使用以下状态：

- `pending`：尚未开始。
- `running`：正在实现。
- `awaiting_commit`：实现验收通过，等待用户批准写入；此时没有 commit SHA。
- `completed`：批准写入成功，任务 commit 与 checkpoint 已完成。
- `blocked`：实现或提交门禁失败，保留阻塞证据。

状态流转：

```text
pending -> running -> awaiting_commit -> completed
                     |                 |
                     +-> blocked       +-> blocked（提交校验失败）
```

`awaiting_commit` 是当前任务的终止边界，不解锁下一任务。任务在该状态下仍是 `current_task`，也仍属于 `ownership.status=cosh_active`。

## 实现完成

`complete-subtask --status passed` 只完成实现验收：

1. 重新验证 Hammer Plan SHA、活动目录、观察板状态和 Cosh 全阶段所有权。
2. 验证当前任务确实为 `running`，依赖均已 `completed`。
3. 写入 `checkpoints/<task-id>.json`，记录：
   - `status: awaiting_commit`
   - `task`
   - 实现验收证据
   - `implementation_completed_at`
4. 把 `tasks.json` 中当前任务更新为 `awaiting_commit`。
5. 保持 `current_task` 不变。
6. 不读取最终 staged snapshot，不创建 commit，不写 `commit_sha`。

`complete-subtask --status blocked` 继续只记录阻塞证据，不提交、不推进。

## 批准写入

新增显式控制动作 `approve-task-commit`，同时提供 CLI 和观察板按钮。该动作只接受当前 `awaiting_commit` 任务，不接受外部 commit SHA。

批准时按顺序执行：

1. 重新验证 Plan SHA、活动目录、观察板和所有权。
2. 确认任务仍是全局任务树的当前任务，状态为 `awaiting_commit`。
3. 读取此刻的 Git 暂存区；暂存区不能为空。
4. 暂存路径必须全部属于当前任务 `expected_files`。
5. 当前任务和所有未来任务涉及的文件不得存在未暂存或未跟踪实现改动。
6. 生成最终 `staged_files` 与 `snapshot_sha`。
7. 创建当前任务独立 commit，并写入任务 trailer。
8. 把 checkpoint 更新为 `status: completed`，并追加 `staged_files`、`snapshot_sha`、`commit_sha`、`committed_at`。
9. 把任务更新为 `completed`，记录同一 commit SHA。
10. 只有上述原子步骤全部成功后才计算下一任务。

如果校验或 commit 失败，任务保持 `awaiting_commit`，记录可操作的失败原因，不启动下一任务。实现验收证据保留，用户修正暂存区后可再次批准写入。

## 任务推进

提交成功是所有推进方式的共同硬门：

- 单独推进：当前任务提交成功后清空 `current_task`，下一个任务保持 `pending`，等待用户显式授权。
- 连续推进：当前任务提交成功后，若下一个任务依赖满足，则自动把它设为 `running`。
- 最后一个任务提交成功后，不再启动任务；此时才允许执行 `complete-coding`。

`begin-subtask`、授权控制和连续调度都必须拒绝存在 `awaiting_commit` 当前任务的状态。自然语言中的“继续”“重新走流程”不能隐式批准写入。

## 最终交还

`complete-coding` 继续执行一次性全局交还，但只接受全部任务均为 `completed`：

- 每个任务必须存在 `status: completed` 的 checkpoint。
- checkpoint 的 staged files、snapshot SHA、commit SHA 必须完整。
- 所有 commit 必须可达、顺序一致，最终 HEAD 必须等于最后任务 commit。
- 交还产物继续包含 `completed_hammer_tasks`、`task_commits` 和 `hammer_continue_after_coding_stage`。

处于 `awaiting_commit` 的任务即使实现验收已通过，也不得计入最终完成数或交还 Hammer。

## 观察板

编码页对当前任务展示独立的两层状态：

- “实现已完成，待批准写入”徽标。
- 实现验收证据。
- 当前暂存文件摘要；读取失败时 fail closed。
- “批准写入”按钮。

按钮仅在实时状态有效、所有权活动且当前任务为 `awaiting_commit` 时启用。点击后调用 `approve-task-commit`；成功时显示 commit SHA，并按单独/连续模式决定是否进入下一任务。

进度统计分别展示：

- 实现完成数：`awaiting_commit + completed`。
- 已提交数：仅 `completed`。
- 总任务数。

任务详情中的 checkpoint 在批准前不显示虚构 commit；批准后展示最终 snapshot 和 commit SHA。

## 兼容与恢复

- 既有 schema v2 checkpoint 中 `status: passed` 且带有效 commit SHA 的任务，读取时规范化为 `completed`。
- 既有 schema v1 状态继续只读，不自动迁移。
- 服务重启后，从 `tasks.json`、checkpoint 与 Git 重新投影 `awaiting_commit` 或 `completed`；观察板缓存不参与判定。
- 若任务状态为 `awaiting_commit` 但 checkpoint 缺失或不一致，状态 fail closed，禁止批准和推进。
- 若任务已经 `completed`，后续工作区修改不会自动改写历史 checkpoint；它属于新的修正动作，必须显式归属当前任务或按重大决策规则处理。

## 测试策略

至少覆盖以下行为：

1. `complete-subtask passed` 不创建 commit，并进入 `awaiting_commit`。
2. `awaiting_commit` 时单独和连续模式均不能启动下一任务。
3. 批准写入以批准时的暂存区为准，包含验收后的修正内容。
4. 空暂存区、越界文件、相关未暂存/未跟踪改动均拒绝提交。
5. 提交失败时保持 `awaiting_commit`，可修复后重试。
6. 单独模式提交后等待下一任务授权。
7. 连续模式提交后自动启动下一任务。
8. 最后任务提交前 `complete-coding` 被拒绝，提交后正常生成一次全局 handoff。
9. 旧 `passed + commit_sha` checkpoint 能只读规范化为 `completed`。
10. 观察板按钮启用条件、进度统计和状态文案正确。

## 验收标准

- 用户完成任务后可以继续修改，系统不会自动提交。
- 下一任务在前一任务 commit 成功前无法开始。
- 每个任务最终仍只有一个由插件创建的独立 commit/checkpoint。
- 暂存范围、未暂存脏文件、Plan SHA、工作区和所有权门禁没有被削弱。
- Hammer 始终暂停到所有细分任务提交完成，之后只接收一次全局 handoff。
