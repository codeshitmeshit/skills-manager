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

编码模式只返回 Hammer 已接受的 `DONE` 或 `BLOCKED`。返回内容应包含当前 Hammer 父任务、代码快照/commit、插件 checkpoint 摘要和阻塞原因；入口已绑定 Meego 时还应从 `launch.json` 原样携带 Meego ID，未绑定时省略且不得阻塞。不得发明新的 Hammer 状态。

Hammer 分发 coding task 后暂停其原生编码 worker，只保留主流程控制器等待 Cosh。Cosh 通过 `activate-coding` 取得当前父任务的临时编码所有权；`complete-coding` 返回 `status: DONE` 与 `next_action: hammer_continue_after_coding` 后，Hammer 才把该 coding task 视为完成并继续。Cosh 不直接写 Hammer session，也不自行推进 Hammer Gate。

## Meego 弱绑定

创建插件 work 时提示用户可选绑定当前需求 Meego ID。绑定后，入口 prompt 透传 Hammer 合法的 `decision: existing`、`source: user` 和规范化 URL，由 Hammer 自己写 Stage 1 决策及后续产物；插件不得写 `.hammer/execute/meego.md`。用户跳过时不阻塞 cosh-hammer、不创建事项，也不伪造 `skip` 等 Hammer 不支持的第三种决策，后续由 Hammer 原生 Meego 流程决定。

## Dispatch 透传

入口 prompt 明确要求 Hammer 在它生成的每个 coding task 执行说明中保留 `Use $cosh-hammer in coding mode for this Hammer parent task.`。这由 Hammer 在正常 plan 产出过程中写入，不是插件修改 `.hammer/plan/plan.md`。若当前父任务没有该指令，插件不得假定自己已被 Hammer 合法调度，应返回 `BLOCKED` 要求回到 Hammer plan 修正。

Plan Ready 后必须执行插件的 `verify-handoff`，Execute worker 在 CodeGraph 前必须执行 `verify-coding`。这两次验真都只读 Hammer 状态；失败时本插件返回 `BLOCKED`，不得通过修改 `.hammer/**` 自愈，也不得把普通 Hammer coding worker 当作降级路径。具体检查见 [接管硬门](handoff-gates.md)。

## Worktree 决策透传

通过 Cosh 入口调用 Hammer 时默认关闭 worktree。入口把 `decision: skip`、`source: user` 和用户默认关闭的原因写入结构化 Hammer prompt；只有当前请求明确要求隔离 worktree 时才改为 `decision: open`。该 prompt 只是用户决策的透传，Stage 1 决策块仍必须由 Hammer 自己生成和维护，插件不得写入 `.hammer/`。

## 兼容策略

对 Hammer 的读取采用容错投影：未知字段可以展示，但无法确认关键阶段或当前任务时必须阻塞写控制。默认读取入口目录；仅在 Hammer 写出合法的 `migrated_away` 事件且目标通过 Git worktree 注册与仓库归属校验后跟随迁移。没有迁移事件时不得因其他 worktree 存在而切换。兼容适配只修改本插件，不反向修改 Hammer。

本契约只能约束经 Cosh 初始化、校验和接管的调用链。Skill 不是常驻拦截器；外部若完全绕过 Cosh 直接启动 Hammer Execute，只有 Hammer 的正式 dispatch hook 或统一 Cosh launcher 才能提供进程级绝对拦截。
