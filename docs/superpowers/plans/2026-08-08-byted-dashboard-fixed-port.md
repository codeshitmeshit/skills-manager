# 字节观察板固定端口实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让字节 Superpowers 观察板的正式启动地址固定为 `127.0.0.1:57171`。

**Architecture:** 保留现有 `--port` 参数作为调试入口，将脚本默认值与 Skill 正式启动命令统一为 `57171`。端口绑定沿用 `ThreadingHTTPServer` 的原生失败语义，不增加随机端口降级。

**Tech Stack:** Python 3、`argparse`、`http.server`、`unittest`、Markdown Skill 资源。

## Global Constraints

- 正式 Skill 流程必须使用 `--port 57171 --open`。
- `57171` 被占用时必须启动失败，禁止回退随机端口。
- 多个开发任务继续通过 `?work=<work-id>` 切换。
- 保留显式 `--port <其他端口>` 供测试和调试使用。

---

### Task 1: 统一固定端口

**Files:**
- Modify: `tests/test_byted_superpowers_dashboard.py`
- Modify: `skills/cosh-byted-superpowers-review-planner/scripts/serve_superpowers_dashboard.py`
- Modify: `skills/cosh-byted-superpowers-review-planner/SKILL.md`
- Modify: `skills/cosh-byted-superpowers-review-planner/references/realtime-dashboard.md`

**Interfaces:**
- Consumes: `serve_superpowers_dashboard.parse_args() -> argparse.Namespace`
- Produces: 默认 `args.port == 57171`，正式启动命令固定包含 `--port 57171 --open`

- [ ] **Step 1: 写入默认固定端口的失败测试**

```python
def test_dashboard_cli_uses_fixed_port_by_default(self) -> None:
    with mock.patch.object(sys, "argv", ["serve_superpowers_dashboard.py"]):
        args = SERVER.parse_args()
    self.assertEqual(args.port, 57171)
```

- [ ] **Step 2: 运行测试并确认当前默认值 `8765` 导致失败**

Run: `python3 -m unittest tests.test_byted_superpowers_dashboard.BytedSuperpowersWorkflowStateTest.test_dashboard_cli_uses_fixed_port_by_default`

Expected: FAIL，实际值为 `8765`。

- [ ] **Step 3: 将脚本默认端口及正式启动说明改为 `57171`**

```python
parser.add_argument("--port", type=int, default=57171)
```

同时把 `SKILL.md` 与 `references/realtime-dashboard.md` 中的 `--port 0` 改为 `--port 57171`，明确冲突时失败且不降级。

- [ ] **Step 4: 运行字节专版与全仓库测试**

Run: `python3 -m unittest tests.test_byted_superpowers_dashboard tests.test_byted_superpowers_review_planner_skill`

Expected: 全部通过。

Run: `python3 -m unittest discover -s tests`

Expected: 全部通过。

- [ ] **Step 5: 同步本机安装并提交全部工作区修改**

使用仓库的单 Skill 同步器更新 `~/.codex/skills/cosh-byted-superpowers-review-planner`，逐文件校验后执行：

```bash
git add -A
git commit -m "fix: 修正字节观察板门禁并固定端口"
```
