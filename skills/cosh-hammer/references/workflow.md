# 工作流

## 总体顺序

1. Cosh 入口：澄清需求并启动观察板。
2. Hammer Design：技术设计、稳定性/安全性/可行性三路评审及上报。
3. Hammer Plan：生成 Hammer 的正式执行计划。
4. Cosh 编码插件：CodeGraph → 代码事实 → 预计修改面 → 精准定位 → 编码计划 → 细分任务实现。
5. Hammer Execute：接收父任务 `DONE`/`BLOCKED`，继续原生 Gate。
6. Hammer 交付：远程 UT、CI、最终 CR、BOE/E2E、验收、上报、MR 与归档。

不得将第 4 步提升为新的主流程阶段。它只是 Hammer Execute 当前编码父任务的 worker 实现方式。

## 入口交接

把用户原始输入与澄清后的需求分别保存在 `launch/request.json`、`launch/request.md`。创建 work 时在同一轮提示可选绑定当前需求 Meego ID；绑定结果保存在 `launch/launch.json` 并注入 Hammer prompt，跳过时不阻塞，也不由插件创建 Meego。`launch.json` 同时保存 Hammer 依赖位置、worktree 策略和观察板 URL。入口默认 `--worktree skip`；只有当前请求明确要求 worktree 时使用 `--worktree open`。观察板启动成功后才调用 `$hammer`。

## 编码交接

首次编码父任务到达时生成全局代码事实与预计修改面；再将 Hammer 父任务细化为插件任务。单独推进模式需用户授权下一个细分任务，连续模式可在当前父任务范围内连续执行。

插件 checkpoint 不等于 Hammer commit。当前父任务的细分任务全部完成后，按 Hammer 当前任务协议形成一个父任务 commit，并返回 `DONE`；无法满足 Hammer 契约时返回 `BLOCKED`。若入口绑定了 Meego，所有返回 Hammer 的父任务交接摘要携带同一 Meego ID；未绑定时省略，不改变交接结果。
