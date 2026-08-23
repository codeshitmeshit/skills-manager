# 编码产物

所有插件产物位于 `.cosh/hammer-plugin/<work-id>/coding/`：

- `code-facts.json`：一次 CodeGraph 与源码复核得到的全局代码事实、调用关系和证据位置。
- `change-surface.json`：覆盖全部 Hammer coding parent tasks 的预计修改面；不是新 Hammer spec。
- `locations.json`：完整修改面的变量/函数/文件级定位。
- `implementation-plan.md`：全局编码阶段的最小改动顺序与依赖。
- `tasks.json`：schema v2 全局任务树。顶层包含 `schema_version`、`status`、`current_task`、`hammer_task_order`、`tasks[]`；每个任务包含稳定 `id`、`hammer_parent`、`title`、`description`、`expected_files`、`symbols`、`steps`、显式 `dependencies`、`acceptance` 与 `status`。每个 Hammer 父任务至少映射一项，并按父任务/实现顺序排列。
- `ownership.json`：schema v2 全阶段所有权。活动期为 `cosh_active`、`scope: full_coding_stage`、`hammer_status: paused_for_cosh`；最终变为 `returned_to_hammer`。
- `amendments/`：事实变化时只修正受影响任务、依赖和修改面；不重建 Hammer Plan，除非用户明确要求。
- `checkpoints/<task-id>.json`：实现验收通过时先写 `status: awaiting_commit`、实现证据和完成时间，不创建 commit；用户批准写入后更新为 `status: completed`，追加实时 staged files、snapshot SHA、commit SHA 和提交时间。`blocked` checkpoint 不含 commit。
- `coding-stage-handoff.json`：全部任务完成后唯一的全局 `DONE` 摘要；可选携带入口已绑定的 Meego ID。

前四类分析产物和完整任务树生成后调用一次 `activate-coding`。缺少父任务映射、执行细节、依赖目标，或依赖后续父任务时拒绝激活。schema v1 单父任务状态只读，不能拼接或自动升级。

单独模式只授权当前 pending 详细任务；连续模式按同一全局顺序自动推进。两者都使用同一依赖、暂存范围、未来任务脏文件、Plan SHA、活动目录和所有权门禁。

`complete-subtask` 只把通过的任务置为 `awaiting_commit`，保持当前任务和所有权。显式 `approve-task-commit` 以批准时的暂存区重新执行范围与脏文件校验，成功后创建该任务独立 commit 并把 checkpoint 置为 `completed`；不接受外部 commit SHA。只有全部任务已提交、与 Git 历史一致且 HEAD 等于最后 checkpoint 时，`complete-coding` 才生成全局 handoff。中间父任务不产生 handoff或释放所有权。
