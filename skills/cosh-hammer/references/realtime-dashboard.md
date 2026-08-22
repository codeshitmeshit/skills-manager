# 实时观察板

观察板固定监听 `127.0.0.1:57172`，使用系统默认浏览器打开 `http://127.0.0.1:57172/?work=<work-id>`。端口被非当前实例占用时停止，不得换端口。

本机入口统一运行 `scripts/start_cosh_hammer_dashboard.py`。启动器在后台启动服务，轮询 `/healthz`，确认返回的 project/work 与当前任务一致后才输出 `READY` 并打开浏览器；未就绪时不得把需求交给 Hammer。已有同 project/work 实例可复用，其他实例占用固定端口时 fail closed。

不得启动、代理、嵌入或修改 Hammer 自带观察板。本页面是唯一面向用户的观察板，但它不取得 Hammer 流程所有权。

服务通过 SSE 轮询并投影两类事实：

- `.hammer/`：只读展示 Hammer design、review、plan、execute、Gate 和交付状态；
- `.cosh/hammer-plugin/<work-id>/`：展示入口、CodeGraph、预计修改面、定位、编码计划、细分任务与交接状态。

页面导航按 Hammer 主流程组织：总览、需求、设计、三路评审、计划、编码、验证、交付和全部产物。各阶段页展示对应 Hammer/Cosh 产物；“全部产物”列出活动 `.hammer/**` 与入口插件目录中的全部普通文件，并按需读取内容。UTF-8 文本、Markdown 和 JSON 直接预览，二进制与超过读取上限的文件仅展示元信息。路径越界、符号链接和不存在的产物必须拒绝。

产物查看器默认把 Markdown 渲染为安全的阅读视图，把 JSON 渲染为按层级折叠的类型化树；同时提供原文切换和复制原文。渲染必须使用文本节点和受控 DOM，不得把产物内容直接写入 `innerHTML`。点击遮罩空白区域或按 Escape 可关闭查看器，点击查看器正文不得误关闭。

总览必须明确标识流程位置：`running`、`blocked` 或 `failed` 的阶段标为“当前”；没有活动阶段时，首个 `pending` 阶段标为“下一步”；全部通过后标为“已完成”。标题区同步展示阶段名称、已完成阶段数和总阶段数，阶段卡片展示同一标识，不得让前一阶段已通过、后一阶段待开始的间隙看起来像仍停留在前一阶段。

三路评审页必须识别 `.hammer/design/reviews/<round>/` 下的 `general.md`、`security.md` 与 `stability.md`，按最新轮次优先展示每路 `status`、`review_pass`、`review_mode`、`blocking_issue_count`、`max_severity`、`unresolved_finding_ids` 和原文入口。该 round 目录中的设计快照与 `routing.json` 也归为评审产物，不得误放在设计页。兼容旧版 `.hammer/design/{review,security-review,stability-review}.md`。

编码推进设置不是全局时间线控件：只在“编码”页、已经生成细分任务且 `ownership.status=cosh_active` 时可操作，并明确展示“Hammer 已暂停编码，Cosh 正在执行细分任务”。编码区采用与字节流程一致的主从布局：左侧为紧凑任务轨迹，右侧固定展示选中或当前任务的完整详情。页面必须实时展示任务总数、已完成数、进度条、下一动作，以及每项任务的说明、修改文件、关键符号、实施步骤、依赖、验收条件、状态和完成证据；当前任务需突出标识。逐一任务模式仅在当前 pending 任务尚未授权时显示授权按钮，且不能提前授权未来任务；连续模式不显示授权按钮，并由编码 worker 按持久化 `next_action` 连续消费当前父任务内的下一项。`returned_to_hammer` 后所有推进控件禁用并提示等待 Hammer 进入下一阶段。其他 Hammer 阶段页面只读，不得出现插件推进控制。

旧版 `tasks.json` 仅做兼容投影：`completed`、`done` 等历史状态可归一显示为 `passed` 并参与进度计算，缺失的详细字段明确标记为“旧版快照未记录”。若同时缺少 `ownership.json`，页面必须标记旧版只读快照、禁用推进控制并输出 `legacy_snapshot_readonly`；不得据此补写或伪造 `cosh_active`。

入口目录默认保持为活动目录，不因发现其他 Git worktree 而自行迁移。只有 Hammer 在当前 `.hammer/design/session.md` 写入合法的 `workspace.worktree decision=migrated_away path=...` 事件后，服务才校验目标属于当前仓库的已注册 Git worktree，并沿迁移链读取目标 `.hammer/`；无事件时始终继续监听原目录，非法或循环迁移时 fail closed。插件状态和控制仍留在入口目录的 `.cosh/hammer-plugin/<work-id>/`。

服务只能把控制写入插件目录。缓存 `dashboard/dashboard-state.json` 只用于重启恢复显示，不是 Hammer 或插件门禁证据。实时投影失败时展示最后有效快照并标记 stale，禁用所有控制。

CloudDev 场景仍使用固定一对一 SSH 转发：本机 `127.0.0.1:57172` 到远端 `127.0.0.1:57172`。远端不要使用 `--open`；隧道建立后在本机系统浏览器打开固定 URL。
