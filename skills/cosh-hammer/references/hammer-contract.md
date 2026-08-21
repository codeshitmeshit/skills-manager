# Hammer 集成契约

## 所有权

Hammer 独占以下内容：

- `.hammer/**` 的所有写入；
- design、review、plan、execute 与 Gate 的状态转换；
- 三路技术评审、上报、远程 UT、CI、最终 CR、E2E、验收和交付证据；
- Hammer 父任务 commit 及其 trailer 规则。

本插件只能读取这些产物。不得修补、迁移、格式化或补写 `.hammer` 文件，即使这样看似能恢复流程。

## 强依赖

入口必须能定位 Hammer 根目录及其 `SKILL.md`。Hammer 缺失时 fail closed，不得退回本插件原有流程，也不得复制 Hammer 逻辑。

## Worker 返回

编码模式只返回 Hammer 已接受的 `DONE` 或 `BLOCKED`。返回内容应包含当前 Hammer 父任务、代码快照/commit、插件 checkpoint 摘要和阻塞原因；不得发明新的 Hammer 状态。

## Dispatch 透传

入口 prompt 明确要求 Hammer 在它生成的每个 coding task 执行说明中保留 `Use $cosh-hammer in coding mode for this Hammer parent task.`。这由 Hammer 在正常 plan 产出过程中写入，不是插件修改 `.hammer/plan/plan.md`。若当前父任务没有该指令，插件不得假定自己已被 Hammer 合法调度，应返回 `BLOCKED` 要求回到 Hammer plan 修正。

## Worktree 决策透传

通过 Cosh 入口调用 Hammer 时默认关闭 worktree。入口把 `decision: skip`、`source: user` 和用户默认关闭的原因写入结构化 Hammer prompt；只有当前请求明确要求隔离 worktree 时才改为 `decision: open`。该 prompt 只是用户决策的透传，Stage 1 决策块仍必须由 Hammer 自己生成和维护，插件不得写入 `.hammer/`。

## 兼容策略

对 Hammer 的读取采用容错投影：未知字段可以展示，但无法确认关键阶段或当前任务时必须阻塞写控制。默认读取入口目录；仅在 Hammer 写出合法的 `migrated_away` 事件且目标通过 Git worktree 注册与仓库归属校验后跟随迁移。没有迁移事件时不得因其他 worktree 存在而切换。兼容适配只修改本插件，不反向修改 Hammer。
