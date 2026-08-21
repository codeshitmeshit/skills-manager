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

## 兼容策略

对 Hammer 的读取采用容错投影：未知字段可以展示，但无法确认关键阶段或当前任务时必须阻塞写控制。兼容适配只修改本插件，不反向修改 Hammer。
