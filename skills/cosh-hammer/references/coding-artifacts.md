# 编码产物

所有文件都位于 `.cosh/hammer-plugin/<work-id>/coding/`。

- `code-facts.json`：CodeGraph 与源码复核后的代码事实、调用关系和证据位置。
- `change-surface.json`：预计修改面，描述文件、符号、接口、数据和测试影响；不是新的 Hammer spec。
- `locations.json`：变量/函数/文件级精准定位。
- `implementation-plan.md`：只针对编码执行的最小改动计划。
- `tasks.json`：Hammer 父任务与细分任务的映射和状态。顶层至少包含 `status`、`current_task` 与 `tasks[]`；每个任务必须包含稳定 `id`、`hammer_parent`、`title`、`description`、`expected_files`、`symbols`、`steps`、`dependencies`、`acceptance` 与 `status`。缺少任一执行细节时 `activate-coding` 必须拒绝，避免退化成只有标题的粗粒度 Hammer task。观察板只能授权当前任务，且依赖未全部通过时不得开始。
- `ownership.json`：当前编码所有权。`cosh_active` 表示 Hammer 已暂停编码并由 Cosh 独占当前父任务；`returned_to_hammer` 表示 Cosh 已交还标准 handoff，禁止继续修改该父任务。
- `amendments/`：实现过程中对预计修改面的附加修正，不重建 Hammer plan，除非用户明确要求。
- `checkpoints/`：细分任务的快照、验证与授权记录，不冒充 Hammer commit。
- `parent-handoffs/`：返回 Hammer 的父任务 `DONE`/`BLOCKED` 摘要；入口已绑定 Meego 时携带 `launch.json` 中的 Meego ID，未绑定时省略。

生成前四类产物和细分任务后必须调用 `activate-coding`。每个细分任务通过 `begin-subtask`/`complete-subtask` 改变状态；不得直接手改 `tasks.json` 冒充推进。单独模式每项都等待观察板授权；父任务全部通过且仍有下一个 Hammer 父任务时，还必须执行 `authorize-hammer-task`，且只能授权紧邻下一项。连续模式根据实时投影的 `coding.next_action` 自动消费细分任务与父任务边界，遇到 blocked 或所有权变化即停止。全部通过后形成父任务 commit，再调用 `complete-coding` 生成 `DONE` handoff。

预计修改面或细分任务跨越当前 Hammer 父任务边界时，属于重大决策，必须中断询问。
