---
name: cosh-hammer
description: 基于 Hammer 主流程提供独立编码插件与实时研发观察板。用户从一段话或文档发起 Hammer 研发流程、要求在 Hammer Plan 后用 CodeGraph 细化预计修改面与编码任务、按单独或连续模式实现，或希望只用 Cosh 观察板监听 Hammer 状态时使用；产物写入 .cosh/hammer-plugin，强依赖 Hammer 但不修改 Hammer 或 .hammer。
---

# Cosh Hammer

## 目标

把本 skill 当作 Hammer 的编码插件。Hammer 是唯一主流程、唯一阶段状态机和最终交付门禁；本 skill 只补充需求入口、编码任务细化及独立观察板。

始终遵守以下边界：

- 不得修改 Hammer 的 skill、脚本、安装目录、协议或运行时。
- 不得写入 `.hammer/`；只读 Hammer 的会话和证据。
- 不得启动、嵌入或依赖 Hammer 自带观察板，只使用本 skill 的观察板。
- 只把插件状态写入 `.cosh/hammer-plugin/<work-id>/`。
- 不得用插件状态伪造或替代 Hammer Gate 证据。
- Hammer 不可用、状态不合法或投影失败时 fail closed。

开始前按任务读取：[工作流](references/workflow.md)、[Hammer 契约](references/hammer-contract.md)、[编码产物](references/coding-artifacts.md)、[实时观察板](references/realtime-dashboard.md) 与 [重大决策](references/major-decisions.md)。

## 两种运行模式

### 入口模式

用户提供一段话或文档时：

1. 只澄清产品目标、范围、约束和验收条件，不提前替 Hammer 作技术设计。
2. 检查 `$hammer` 可用；缺失时停止，不得降级为独立研发流程。
3. 用 `scripts/cosh_hammer_state.py init` 固化需求和结构化 Hammer prompt。默认传入 `--worktree skip`；只有用户在本次请求中明确要求使用 worktree 时才传入 `--worktree open`，不得根据实现复杂度自行开启。
4. 在调用 `$hammer` 前运行 `scripts/start_cosh_hammer_dashboard.py`；只有它完成 `/healthz` 校验并输出 `READY` 后才继续。启动器固定使用端口 `57172`，随后通过系统默认浏览器打开。
5. 把 `launch.json` 中的 `hammer_prompt` 原样作为 Hammer 输入；其中包含用户的 worktree 决策，由 Hammer 自己按 Stage 1 schema 写入 `.hammer/`。该 prompt 还要求 Hammer 在每个 coding task 执行说明中保留 `Use $cosh-hammer in coding mode for this Hammer parent task.`，确保标准 task-dispatch 仍能触发本插件。随后由 Hammer 接管 design、三路技术评审、上报、plan 与 execute。

### 编码模式

仅当 Hammer Execute 已进入编码任务且存在可读 Hammer plan 时运行：

1. 只读 Hammer design、三路评审结论、plan 和当前父任务。
2. 首次进入时按顺序生成 CodeGraph 代码事实、预计修改面、精准定位、编码计划和细分任务。
3. 按用户在观察板选择的单独推进或连续推进方式实现当前 Hammer 父任务下的细分任务。
4. 细分任务只记录 checkpoint；完成当前 Hammer 父任务的全部细分任务后，才创建一个符合 Hammer 契约的父任务 commit。
5. 向 Hammer 返回标准 `DONE` 或 `BLOCKED`，不得新增 Hammer 状态或自行推进 Hammer Gate。
6. 编码结束后回归 Hammer；远程 UT、CI、最终 CR、BOE/E2E、验收、上报、MR 与归档全部继续使用 Hammer 原生流程。

## 决策规则

普通实现选择可在已批准范围内自主决定。遇到会改变需求、公共接口、数据模型、兼容策略、发布/回滚策略、安全边界、跨 Hammer 父任务修改面，或需要绕过 Hammer Gate 的事项时，立即中断并向用户询问；详见 [重大决策](references/major-decisions.md)。

## 观察板

运行：

```bash
python3 <skill-root>/scripts/start_cosh_hammer_dashboard.py \
  --project <repo-absolute-path> \
  --work <work-id> \
  --hammer-root <hammer-absolute-path> \
  --host 127.0.0.1 \
  --port 57172
```

端口冲突时直接报告并停止，不得随机换端口。观察板通过 SSE 实时读取 `.hammer/` 与 `.cosh/hammer-plugin/`，但所有控制只允许修改插件状态。

## 交付检查

- Hammer 安装和 `.hammer/` 与运行前完全一致，除 Hammer 自身写入外，本 skill 没有任何写入。
- 插件产物都位于 `.cosh/hammer-plugin/<work-id>/`。
- 编码结果以标准 `DONE`/`BLOCKED` 回到 Hammer。
- 最终测试、CR、E2E 和交付状态来自 Hammer，而不是观察板缓存。
