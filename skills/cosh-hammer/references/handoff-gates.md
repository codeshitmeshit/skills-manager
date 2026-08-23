# 接管硬门

## 新任务入口

严格按以下顺序执行，任一步失败都停止：

1. `cosh_hammer_state.py init`：固化 project、work、Hammer 根目录、Meego、worktree 决策和 Hammer prompt。
2. `start_cosh_hammer_dashboard.py`：只允许 `127.0.0.1:57172`；`/healthz` 匹配当前 project/work 并输出 `READY`。
3. `cosh_hammer_state.py preflight`：复核 launch、观察板身份和 prompt，写入 `gates/preflight.json`。
4. 把 `launch.json.hammer_prompt` 原样交给 Hammer。

禁止在第 3 步通过前调用 Hammer，也禁止先调用后补接。

## Plan 到全局编码阶段

Hammer Plan Ready 后运行 `verify-handoff --project <repo> --work <work-id>`，同时确认 Plan/handoff 状态、SHA、全量 lint/review evidence、每个 coding task 的 Cosh 触发语句、活动目录/worktree 与非 stale 观察板。缺一项返回 `BLOCKED`，插件不得改写 `.hammer/plan/**`。

Hammer Execute 到达首个 coding task 后，在读取代码或运行 CodeGraph 前运行：

```bash
python3 <skill-root>/scripts/cosh_hammer_state.py verify-coding \
  --project <repo-absolute-path> \
  --work <work-id> \
  --task "Task <首项>"
```

该门额外确认 Execute session 的 `current_task_ref`、coding stage 和 `next_action: run-step-4`。通过后 Hammer 暂停整个编码阶段。Cosh 必须读取完整父任务顺序，一次性生成覆盖全部预计修改面的 CodeGraph/源码事实、定位、计划和详细任务树，再运行 `activate-coding`。只有 schema v2 `cosh_active + full_coding_stage` 所有权建立后才能修改业务代码。

## 执行与最终交还

每次 `begin-subtask`/`complete-subtask` 都重新确认 Plan SHA、父任务顺序、活动目录、观察板和所有权。`complete-subtask` 通过时只写 `awaiting_commit` 实现证据，不创建 commit、不解锁下一任务。显式 `approve-task-commit` 必须再次确认同一上下文，并满足：暂存区非空、暂存路径只属于当前任务、当前和未来任务无相关未暂存/未跟踪改动。提交成功并把 checkpoint 更新为 `completed` 后才能解锁下一任务；普通“继续”或模式切换不能批准写入。

中间父任务通过不触发 Hammer handoff。全部任务通过后运行：

```bash
python3 <skill-root>/scripts/cosh_hammer_state.py complete-coding \
  --project <repo-absolute-path> \
  --work <work-id>
```

命令拒绝任何 `awaiting_commit` 任务，逐项校验 `completed` checkpoint、commit 可达性、提交文件、提交顺序和最终 HEAD，只写一次 `coding-stage-handoff.json`。Hammer 仅在消费 `DONE + hammer_continue_after_coding_stage` 后恢复并进入编码后 Gate。

## 迟到接入与技术边界

Hammer 已完成 Design/Plan 但插件未初始化时，运行 `attach-existing-hammer`。命令只创建 `.cosh/**`、启动观察板并报告 Plan 修复要求；修复由 Hammer 完成，之后仍须依次通过 `verify-handoff` 与首个 `verify-coding`。

这些门禁只约束经 Cosh 启动和接管的链路。完全绕过 Cosh 的独立 Hammer Execute 需要 Hammer 正式 dispatch hook 或统一 Cosh launcher 才能进程级拦截。
