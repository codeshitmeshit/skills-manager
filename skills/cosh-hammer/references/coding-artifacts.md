# 编码产物

所有文件都位于 `.cosh/hammer-plugin/<work-id>/coding/`。

- `code-facts.json`：CodeGraph 与源码复核后的代码事实、调用关系和证据位置。
- `change-surface.json`：预计修改面，描述文件、符号、接口、数据和测试影响；不是新的 Hammer spec。
- `locations.json`：变量/函数/文件级精准定位。
- `implementation-plan.md`：只针对编码执行的最小改动计划。
- `tasks.json`：Hammer 父任务与细分任务的映射和状态。顶层至少包含 `status`、`current_task` 与 `tasks[]`；每个任务包含稳定 `id`、`hammer_parent`、`title`、`status`、预计文件和验收点。观察板只能授权该数组内的任务。
- `amendments/`：实现过程中对预计修改面的附加修正，不重建 Hammer plan，除非用户明确要求。
- `checkpoints/`：细分任务的快照、验证与授权记录，不冒充 Hammer commit。
- `parent-handoffs/`：返回 Hammer 的父任务 `DONE`/`BLOCKED` 摘要；入口已绑定 Meego 时携带 `launch.json` 中的 Meego ID，未绑定时省略。

预计修改面或细分任务跨越当前 Hammer 父任务边界时，属于重大决策，必须中断询问。
