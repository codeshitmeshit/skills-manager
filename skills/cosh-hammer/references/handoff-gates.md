# 接管硬门

## 新任务入口

严格按以下顺序执行，任一步失败都停止：

1. `cosh_hammer_state.py init`：生成 `.cosh/hammer-plugin/<work-id>/launch/launch.json`，固化 project、work、Hammer 根目录、Meego 和 worktree 决策，并生成含编码触发语句的 Hammer prompt。
2. `start_cosh_hammer_dashboard.py`：只允许 `127.0.0.1:57172`，等待 `/healthz` 返回当前 project/work 并输出 `READY`。
3. `cosh_hammer_state.py preflight`：复核 launch、观察板身份和 prompt；成功证据写入 `gates/preflight.json`。
4. 把 `launch.json.hammer_prompt` 原样交给 Hammer。

禁止在第 3 步通过前调用 Hammer，也禁止先调用、稍后补接。

## Plan 到 Execute

Hammer Plan Ready 后运行：

```bash
python3 <skill-root>/scripts/cosh_hammer_state.py verify-handoff \
  --project <repo-absolute-path> \
  --work <work-id>
```

校验必须同时确认：

- `plan.md` 与 `handoff.json` 存在，Plan Ready 状态、SHA 和全量 lint/review evidence 有效；
- 每个 coding task 都原样包含 `Use $cosh-hammer in coding mode for this Hammer parent task.`；
- 当前 Hammer 活动目录与观察板 active project 一致，迁移 worktree 必须通过 Git 注册与仓库归属校验；
- launch 和观察板状态有效且非 stale。

缺一项返回 `BLOCKED`，要求 Hammer 回到 Plan 修正。插件不得改写 `.hammer/plan/**`。

## 编码二次验真

每个 Cosh coding worker 在读取代码、运行 CodeGraph 或创建编码产物前运行：

```bash
python3 <skill-root>/scripts/cosh_hammer_state.py verify-coding \
  --project <repo-absolute-path> \
  --work <work-id> \
  --task "Task <N>"
```

除交接门全部条件外，还必须确认 Execute session 的 `current_task_ref`、coding stage 和 `next_action: run-step-4` 与请求任务一致。成功证据写入 `gates/coding-dispatch.json`。失败时不得开始 CodeGraph 或编码，也不得静默退化为 Hammer 原生 worker。

## 迟到接入

Hammer 已完成 Design/Plan、但 `.cosh/hammer-plugin/<work-id>` 尚未初始化时运行：

```bash
python3 <skill-root>/scripts/cosh_hammer_state.py attach-existing-hammer \
  --project <repo-absolute-path> \
  --work <work-id> \
  --requirement <refined-requirement> \
  --hammer-root <hammer-absolute-path>
```

命令只创建 `.cosh/**`、启动观察板并报告哪些 Plan coding task 缺少触发语句；不修改 `.hammer/**`。修复必须由 Hammer 回到 Plan 完成，之后仍需运行 `verify-handoff` 与 `verify-coding`。

## 技术边界

这些门禁对 Cosh 启动和接管的链路 fail closed。Skill 本身不是常驻 hook，无法拦截完全绕过 Cosh 的独立 Hammer Execute；若需要这种保证，必须由 Hammer 提供正式 task-dispatch hook，或统一通过 Cosh launcher 启动 Hammer。
