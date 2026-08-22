# 工作流

## 总体顺序

1. Cosh 入口：澄清需求，先初始化插件，再启动观察板并通过 `preflight`。
2. Hammer Design：技术设计、稳定性/安全性/可行性三路评审及上报。
3. Hammer Plan：生成 Hammer 的正式执行计划。
4. Plan→Execute 交接：`verify-handoff` 通过后，Hammer 才能把 coding task 分发给本插件。
5. Cosh 编码插件：`verify-coding` → CodeGraph → 代码事实 → 预计修改面 → 精准定位 → 编码计划 → 细分任务实现。
6. Hammer Execute：接收父任务 `DONE`/`BLOCKED`，继续原生 Gate。
7. Hammer 交付：远程 UT、CI、最终 CR、BOE/E2E、验收、上报、MR 与归档。

不得将第 4、5 步提升为新的主流程阶段。它们只是 Hammer Execute 当前编码父任务的交接门与 worker 实现方式。

## 入口交接

把用户原始输入与澄清后的需求分别保存在 `launch/request.json`、`launch/request.md`。创建 work 时在同一轮提示可选绑定当前需求 Meego ID；绑定结果保存在 `launch/launch.json` 并注入 Hammer prompt，跳过时不阻塞，也不由插件创建 Meego。`launch.json` 同时保存 Hammer 依赖位置、worktree 策略和观察板 URL。入口默认 `--worktree skip`；只有当前请求明确要求 worktree 时使用 `--worktree open`。`init` 必须是首个文件系统副作用；观察板 READY 后还必须通过 `preflight`，之后才能调用 `$hammer`。

## 编码交接

Hammer Plan Ready 后先运行 `verify-handoff`；编码父任务到达后，Hammer 暂停原生 coding worker，CodeGraph 前运行 `verify-coding`。首次合法进入时生成全局代码事实与预计修改面，再将 Hammer 父任务细化为包含文件、符号、步骤、依赖和验收条件的插件任务，并运行 `activate-coding` 取得临时编码所有权。单独推进模式需用户逐项授权当前细分任务，并在父任务完成后再次授权紧邻的下一个 Hammer 父任务；连续模式才可自动推进细分任务和父任务边界。任何未授权的父任务即使已被 Hammer 提前设为当前任务，`verify-coding` 也必须 fail closed。

插件 checkpoint 不等于 Hammer commit。当前父任务的细分任务全部完成后，按 Hammer 当前任务协议形成一个父任务 commit，通过 `complete-coding` 返回 `DONE` 和 `hammer_continue_after_coding`；无法满足 Hammer 契约时返回 `BLOCKED`。Hammer 消费该 handoff 后继续下一个 coding task，全部 coding task 完成后进入编码后的原生 Gate。若入口绑定了 Meego，所有返回 Hammer 的父任务交接摘要携带同一 Meego ID；未绑定时省略，不改变交接结果。
