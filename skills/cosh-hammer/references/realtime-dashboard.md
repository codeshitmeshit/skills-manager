# 实时观察板

观察板固定监听 `127.0.0.1:57172`，入口为 `scripts/start_cosh_hammer_dashboard.py`。启动器确认 `/healthz` 的 project/work 匹配后才输出 `READY` 并打开默认浏览器；其他实例占用端口时 fail closed，不得换端口。不得启动、代理、嵌入或修改 Hammer 自带观察板。

服务通过 SSE 投影只读 `.hammer/` 和插件自有 `.cosh/hammer-plugin/<work-id>/`。导航左侧按 Hammer 主流程组织为总览、需求、设计、三路评审、计划、验证、交付和全部产物；编码不属于 Hammer 阶段标签，作为右侧独立的 Cosh 入口展示。计划页只读展示 Hammer Plan；编码页独立展示 Cosh 全局编码阶段。

文本、Markdown 和 JSON 产物可按需预览；二进制与超大文件只展示元信息。查看器使用文本节点和受控 DOM，不把产物写入 `innerHTML`。路径越界、符号链接和不存在的产物必须拒绝。

## 全局编码页

编码页顶部展示完整阶段所有权、单独/连续模式、实现完成数、已提交数、总数、当前详细任务与下一动作。左侧按 `hammer_task_order` 为每个 Hammer 父任务建立分组，并在组内展示全部详细任务；右侧展示选中任务的说明、文件、符号、步骤、依赖、验收、状态、完成证据、checkpoint commit 与 snapshot。

编码产物区默认折叠，只统计并展示 `code-facts.json`、`change-surface.json`、`locations.json`、`implementation-plan.md` 和生成后的 `coding-stage-handoff.json`。`amendments/`、`checkpoints/`、`control.json`、`tasks.json` 与 `ownership.json` 属于过程状态，不计入编码产物数量，但仍保留在“全部产物”页。

默认单独模式只显示当前 pending 详细任务授权；连续模式不显示逐任务授权。任务处于 `awaiting_commit` 时显示“实现已完成，待批准写入”、实时暂存文件和“批准写入”按钮，且两种模式都禁止提前进入下一任务。批准提交成功后，单独模式等待下一任务授权，连续模式自动启动下一个依赖满足的任务。不存在父任务授权按钮。全部任务提交后显示“编码完成，等待交还 Hammer”；最终 handoff 后禁用控制并等待 Hammer 进入验证阶段。

schema v1 单父任务快照标记为 `legacy_single_parent_readonly`，历史带 commit SHA 的 `passed`/`done` 等状态可归一为 `completed`，但始终禁用控制，不补写或伪造 schema v2 所有权。

## Hammer 投影与安全

总览标识当前/下一步/已完成阶段。三路评审区分 round 原始报告和顶层终态报告：原始报告读取 `status_recommendation` 与 `blocking_issue_count`，Round 1 固定展示 `full`，Round 2–4 固定展示 `closure`；顶层终态报告读取 `status`。原始报告未提供可选的 `max_severity` 或 `unresolved_finding_ids` 时显示“原始报告未提供”，不得伪装成 `none`；阻塞数与显式 `none`、通过状态等字段矛盾时显示“评审证据不一致”并保持 fail closed。缺少权威结论时保持 unknown 并 fail closed。其他 Hammer 阶段页面只读，不出现插件推进控制。

只有合法 `workspace.worktree decision=migrated_away path=...` 事件且目标通过 Git 注册与仓库归属校验后才跟随活动 worktree；插件状态和控制仍位于入口目录。缓存 `dashboard/dashboard-state.json` 只用于恢复显示，不是门禁证据。投影失败时展示 stale 快照并禁用全部控制。

CloudDev 使用固定一对一 SSH 转发：本机 `127.0.0.1:57172` 到远端同端口；远端不使用 `--open`。
