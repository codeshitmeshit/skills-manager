# 字节研发观察板自动启动设计

## 目标

显式使用 `cosh-byted-superpowers-review-planner` 或正式进入该研发流程时，自动启动“cosh 验收观察版”，并在服务成功监听后使用系统默认浏览器打开页面。

## 启动契约

- 显式调用 skill 时必须启动观察板；正式研发流程在建立当前 `<work-id>` 基础状态后、执行 AI-Spec 门禁前启动。
- 仅解释或维护该 skill 自身时不递归启动观察板。
- 使用现有 `serve_superpowers_dashboard.py`，增加 `--open` 参数；使用 `--port 0` 时由系统选择空闲端口。
- 先成功创建 HTTP 服务，再根据实际绑定的 host 与 port 生成 URL 并调用系统默认浏览器。
- 自动打开失败时保持服务运行，记录警告并输出 URL，研发流程继续执行。
- 页面仍是可选控制界面，不替代自然语言入口或后端门禁。

## 实现范围

- `scripts/serve_superpowers_dashboard.py`：解析 `--open`，在监听成功后调用标准库 `webbrowser.open(url, new=2)`。
- `SKILL.md`：将观察板启动提升为流程入口的强制步骤，并明确维护 skill 自身时的递归例外。
- `references/realtime-dashboard.md`：记录自动打开命令、失败处理和最终 URL 输出规则。
- `tests/test_byted_superpowers_dashboard.py`：验证参数解析、实际随机端口 URL 和浏览器打开调用。
- `tests/test_byted_superpowers_review_planner_skill.py`：验证 skill 入口契约。

## 非目标

- 不增加 PID 文件、后台守护进程或重复实例发现。
- 不修改 OpenSpec skill、OpenSpec 观察板或任何 OpenSpec 状态。
- 不强制使用 Codex 内置浏览器。
- 不改变观察板 API、SSE 或研发门禁状态机。

## 验证

- 先运行失败测试，确认旧服务没有 `--open` 行为。
- 实现后运行字节观察板和 skill 契约测试。
- 使用 mock 浏览器控制器验证 URL，不在自动化测试中实际弹出浏览器。
- 手动使用 `--port 0 --open` 启动一次，确认系统默认浏览器收到实际监听地址。
