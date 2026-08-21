# 实时观察板

观察板固定监听 `127.0.0.1:57172`，使用系统默认浏览器打开 `http://127.0.0.1:57172/?work=<work-id>`。端口被非当前实例占用时停止，不得换端口。

本机入口统一运行 `scripts/start_cosh_hammer_dashboard.py`。启动器在后台启动服务，轮询 `/healthz`，确认返回的 project/work 与当前任务一致后才输出 `READY` 并打开浏览器；未就绪时不得把需求交给 Hammer。已有同 project/work 实例可复用，其他实例占用固定端口时 fail closed。

不得启动、代理、嵌入或修改 Hammer 自带观察板。本页面是唯一面向用户的观察板，但它不取得 Hammer 流程所有权。

服务通过 SSE 轮询并投影两类事实：

- `.hammer/`：只读展示 Hammer design、review、plan、execute、Gate 和交付状态；
- `.cosh/hammer-plugin/<work-id>/`：展示入口、CodeGraph、预计修改面、定位、编码计划、细分任务与交接状态。

页面导航按 Hammer 主流程组织：总览、需求、设计、三路评审、计划、编码、验证、交付和全部产物。各阶段页展示对应 Hammer/Cosh 产物；“全部产物”列出活动 `.hammer/**` 与入口插件目录中的全部普通文件，并按需读取内容。UTF-8 文本、Markdown 和 JSON 直接预览，二进制与超过读取上限的文件仅展示元信息。路径越界、符号链接和不存在的产物必须拒绝。

编码推进设置不是全局时间线控件：只在“编码”页且已经生成细分任务时展示。逐一任务模式仅在当前 pending 任务尚未授权时显示授权按钮；连续模式不显示授权按钮。其他 Hammer 阶段页面只读，不得出现插件推进控制。

入口目录默认保持为活动目录，不因发现其他 Git worktree 而自行迁移。只有 Hammer 在当前 `.hammer/design/session.md` 写入合法的 `workspace.worktree decision=migrated_away path=...` 事件后，服务才校验目标属于当前仓库的已注册 Git worktree，并沿迁移链读取目标 `.hammer/`；无事件时始终继续监听原目录，非法或循环迁移时 fail closed。插件状态和控制仍留在入口目录的 `.cosh/hammer-plugin/<work-id>/`。

服务只能把控制写入插件目录。缓存 `dashboard/dashboard-state.json` 只用于重启恢复显示，不是 Hammer 或插件门禁证据。实时投影失败时展示最后有效快照并标记 stale，禁用所有控制。

CloudDev 场景仍使用固定一对一 SSH 转发：本机 `127.0.0.1:57172` 到远端 `127.0.0.1:57172`。远端不要使用 `--open`；隧道建立后在本机系统浏览器打开固定 URL。
