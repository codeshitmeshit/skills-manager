# 实时观察板

观察板固定监听 `127.0.0.1:57172`，使用系统默认浏览器打开 `http://127.0.0.1:57172/?work=<work-id>`。端口被非当前实例占用时停止，不得换端口。

本机入口统一运行 `scripts/start_cosh_hammer_dashboard.py`。启动器在后台启动服务，轮询 `/healthz`，确认返回的 project/work 与当前任务一致后才输出 `READY` 并打开浏览器；未就绪时不得把需求交给 Hammer。已有同 project/work 实例可复用，其他实例占用固定端口时 fail closed。

不得启动、代理、嵌入或修改 Hammer 自带观察板。本页面是唯一面向用户的观察板，但它不取得 Hammer 流程所有权。

服务通过 SSE 轮询并投影两类事实：

- `.hammer/`：只读展示 Hammer design、review、plan、execute、Gate 和交付状态；
- `.cosh/hammer-plugin/<work-id>/`：展示入口、CodeGraph、预计修改面、定位、编码计划、细分任务与交接状态。

服务只能把控制写入插件目录。缓存 `dashboard/dashboard-state.json` 只用于重启恢复显示，不是 Hammer 或插件门禁证据。实时投影失败时展示最后有效快照并标记 stale，禁用所有控制。

CloudDev 场景仍使用固定一对一 SSH 转发：本机 `127.0.0.1:57172` 到远端 `127.0.0.1:57172`。远端不要使用 `--open`；隧道建立后在本机系统浏览器打开固定 URL。
