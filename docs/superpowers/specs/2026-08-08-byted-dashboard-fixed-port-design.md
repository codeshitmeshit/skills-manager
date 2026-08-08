# 字节观察板固定端口设计

## 目标

字节 Superpowers 观察板每次启动都使用 `127.0.0.1:57171`，让用户能够复用固定书签、转发规则和访问地址。

## 行为

- `serve_superpowers_dashboard.py` 的默认端口改为 `57171`。
- Skill 与实时观察板参考命令显式使用 `--port 57171 --open`。
- 多个开发任务仍由同一个服务承载，通过 `?work=<work-id>` 切换，不为每个任务分配端口。
- `57171` 已被占用时启动失败并报告端口冲突；禁止静默回退到随机端口。
- 显式传入其他 `--port` 仅保留为脚本调试能力，正式 Skill 流程固定传入 `57171`。

## 修改范围

- `skills/cosh-byted-superpowers-review-planner/SKILL.md`
- `skills/cosh-byted-superpowers-review-planner/references/realtime-dashboard.md`
- `skills/cosh-byted-superpowers-review-planner/scripts/serve_superpowers_dashboard.py`
- `tests/test_byted_superpowers_dashboard.py`

## 验证

- 参数解析在没有 `--port` 时返回 `57171`。
- 正式启动说明不再包含 `--port 0`。
- 已有自动打开、SSE、控制接口和完整仓库测试继续通过。
