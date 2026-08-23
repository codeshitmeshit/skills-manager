# 工作流

## 总体顺序

1. Cosh 入口：澄清需求，先初始化插件，再启动观察板并通过 `preflight`。
2. Hammer Design：技术设计、稳定性/安全性/可行性三路评审及上报。
3. Hammer Plan：生成正式计划和完整 coding parent task 顺序。
4. Plan→Execute 交接：`verify-handoff` 通过后，Hammer 才能分发首个 coding task。
5. Cosh 全局编码阶段：`verify-coding` → CodeGraph/源码复核 → 全局代码事实与预计修改面 → 精准定位 → 编码计划 → 完整详细任务树 → 逐任务实现验收 → 用户批准写入 → 独立提交。
6. 全局交还：全部详细任务通过后，Cosh 只交还一次；Hammer 跳过全部原生 coding worker，进入编码后 Gate。
7. Hammer 交付：远程 UT、CI、最终 CR、BOE/E2E、验收、上报、MR 与归档。

第 4–6 步仍属于 Hammer Execute 的编码实现方式，不是新的主流程状态机。Hammer 是唯一主流程和最终门禁。

## 入口交接

把原始输入与澄清需求保存在 `launch/request.json`、`launch/request.md`。创建 work 时可选绑定当前需求 Meego ID；绑定结果写入 `launch/launch.json` 并注入 Hammer prompt，跳过不阻塞，也不由插件创建 Meego。入口默认 `--worktree skip`，只有用户明确要求时使用 `--worktree open`。

`init` 必须是首个文件系统副作用。观察板固定端口 READY 且 `preflight` 通过后，才把 `launch.json.hammer_prompt` 原样交给 Hammer。

## 全局编码交接

Hammer Plan Ready 后运行一次 `verify-handoff`。首个 coding task 到达后，Hammer 暂停整个编码阶段；Cosh 在 CodeGraph 前运行一次 `verify-coding`，然后读取全部 Hammer coding parent tasks，一次性分析完整预计修改面并生成 schema v2 全局任务树。后续父任务不得延迟细化。

`activate-coding` 只允许从首个 Hammer coding task 激活，取得 `full_coding_stage` 所有权。单独模式逐项授权当前详细任务；连续模式按全局依赖顺序自动推进。实现验收通过后任务进入 `awaiting_commit`，不创建 commit、不解锁下一任务；用户仍可修改当前任务。显式批准写入时以实时暂存区为唯一交付快照，重新完成范围/脏文件校验并形成独立 commit/checkpoint。提交成功后单独模式等待下一任务授权，连续模式才自动启动下一任务。任何 blocked、stale、Plan 变化、活动目录变化或所有权变化都立即停止。

中间父任务完成不释放所有权、不生成 handoff。全部任务提交完成后，无参数父任务语义的 `complete-coding` 对账所有 `completed` checkpoint 与 Git 历史，生成一次 `DONE + hammer_continue_after_coding_stage`。Hammer 消费后把 `completed_hammer_tasks` 全部视为已完成，直接进入编码后原生 Gate。Meego 仅在已绑定时附加到最终摘要。
