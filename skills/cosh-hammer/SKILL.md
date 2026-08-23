---
name: cosh-hammer
description: 基于 Hammer 主流程提供全局独立编码阶段与实时研发观察板。用户从一段话或文档发起 Hammer 研发流程、要求在 Hammer Plan 后用 CodeGraph 一次性细化全部 coding task 的预计修改面与详细任务树、按单独或连续模式实现，或希望用 Cosh 观察板监听 Hammer 状态时使用；产物写入 .cosh/hammer-plugin，强依赖 Hammer 但不修改 Hammer 或 .hammer。
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

开始前按任务读取：[工作流](references/workflow.md)、[Hammer 契约](references/hammer-contract.md)、[接管硬门](references/handoff-gates.md)、[编码产物](references/coding-artifacts.md)、[实时观察板](references/realtime-dashboard.md) 与 [重大决策](references/major-decisions.md)。

## 两种运行模式

### 入口模式

用户提供一段话或文档时：

1. 只澄清产品目标、范围、约束和验收条件，不提前替 Hammer 作技术设计。
2. 检查 `$hammer` 可用；缺失时停止，不得降级为独立研发流程。
3. 看到 `$cosh-hammer` 后，首个文件系统副作用必须是运行 `scripts/cosh_hammer_state.py init`，生成 `.cosh/hammer-plugin/<work-id>/launch.json`；在此之前不得调用 Hammer。入口澄清的同一轮提示用户可绑定当前需求 Meego ID，也允许跳过。提供时传 `--meego-id <id>`；未提供时继续。默认传 `--worktree skip`；只有用户明确要求 worktree 时才传 `--worktree open`。
4. 运行 `scripts/start_cosh_hammer_dashboard.py`。只有固定端口 `57172` 的 `/healthz` 返回当前 project/work 且启动器输出 `READY` 后才继续。
5. 运行 `scripts/cosh_hammer_state.py preflight`。未生成 launch、观察板不匹配、决策未固化或 Hammer prompt 缺少编码触发语句时立即 `BLOCKED`；禁止先调用 Hammer、稍后补接。
6. 把 `launch.json` 中的 `hammer_prompt` 原样作为 Hammer 输入；其中包含 worktree、Meego 与编码调度契约。随后由 Hammer 接管 design、三路技术评审、上报和 plan。
7. Hammer Plan Ready 后、Execute 分发 coding task 前，必须运行 `scripts/cosh_hammer_state.py verify-handoff`。失败时返回 `BLOCKED` 并要求 Hammer 回到 Plan 修正；本插件不得修改 `.hammer/`，也不得允许 Hammer 静默改派普通 coding worker。首个 coding task 到达后 Hammer 暂停整个编码阶段，只等待 Cosh 的一次最终 handoff。

### 编码模式

仅当 Hammer Execute 已进入编码任务且存在可读 Hammer plan 时运行：

1. 首次 coding task 到达且在读取代码或运行 CodeGraph 前，运行 `scripts/cosh_hammer_state.py verify-coding --task <首个 Hammer Task>`；Execute session、触发语句、work、活动 worktree 或观察板任一不一致时返回 `BLOCKED`。
2. 只读 Hammer design、三路评审结论、plan 和完整 coding parent task 顺序。一次性细化全部 Hammer coding task：统一执行 CodeGraph 与源码复核，覆盖完整预计修改面，并生成代码事实、精准定位、编码计划和全局详细任务树；不得把后续父任务留到前一父任务完成后再分析。
3. 每个细分任务必须包含父任务、说明、修改文件、关键符号、实施步骤、显式依赖和验收条件。运行 `activate-coding` 一次性取得整个编码阶段所有权；只有 `ownership.json` 为 schema v2、`scope: full_coding_stage`、`status: cosh_active` 后才允许修改业务代码。
4. 按观察板选择的单独或连续模式，通过 `begin-subtask` 与 `complete-subtask` 执行全局任务树。默认单独推进并逐项授权当前任务；连续模式可跨父任务组自动推进，但两种模式都不得越过依赖、范围、Plan SHA、活动目录或所有权门禁。
5. `complete-subtask` 验收通过后把当前任务标记为 `awaiting_commit`，只记录实现证据，不创建 commit，也不解锁下一任务。用户可以继续修正当前任务；准备完成后必须显式“批准写入”。批准时以实时 Git 暂存区为唯一交付物，重新校验 `expected_files`、当前/未来任务相关未暂存或未跟踪改动，再创建该任务的独立 commit/checkpoint。提交成功是所有推进模式进入下一任务的共同硬门；`blocked` 只记录证据。
6. 单独模式在提交成功后等待用户授权下一任务；连续模式只在提交成功后自动启动下一个依赖满足的任务。中间父任务完成时 Hammer 继续暂停，不生成父任务 handoff。所有详细任务均已提交后运行无 `--task`/`--commit-sha` 参数的 `complete-coding`；它对账全部 checkpoint、Git 历史与最终 HEAD，只交还一次 `DONE`、`completed_hammer_tasks`、`task_commits` 和 `next_action: hammer_continue_after_coding_stage`。若绑定 Meego 则携带同一 ID。
7. Hammer 消费全局 handoff 后跳过 `completed_hammer_tasks` 对应的全部原生 coding worker，直接进入远程 UT、CI、最终 CR、BOE/E2E、验收、上报、MR 与归档等编码后原生流程。

Hammer 已完成 Design/Plan 但本插件尚未初始化时，使用 `attach-existing-hammer` 迟到接入。它只能创建 `.cosh/**`、启动观察板并输出 Plan 修复要求；不得修改 `.hammer/**`。修复 Hammer Plan 后仍须依次通过 `verify-handoff` 与 `verify-coding`。

## 决策规则

普通实现选择可在已批准范围内自主决定。遇到会改变需求、公共接口、数据模型、兼容策略、发布/回滚策略、安全边界、超出已批准全局修改面，或需要绕过 Hammer Gate 的事项时，立即中断并向用户询问；详见 [重大决策](references/major-decisions.md)。

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

页面以 Hammer 阶段组织为总览、需求、设计、三路评审、计划、编码、验证、交付和全部产物。计划页只读展示 Hammer Plan；独立编码页按 Hammer 父任务分组展示完整全局任务树、实现完成数、已提交数、`awaiting_commit` 待批准状态、checkpoint commit 与单独/连续推进控制。Hammer 与 Cosh 的文本、Markdown、JSON 产物可按需读取；二进制或超大文件只展示元信息。

## 交付检查

- Hammer 安装和 `.hammer/` 与运行前完全一致，除 Hammer 自身写入外，本 skill 没有任何写入。
- 插件产物都位于 `.cosh/hammer-plugin/<work-id>/`。
- 编码结果只在全部任务完成后以一次标准 `DONE` 回到 Hammer；任务阻塞时保留 `BLOCKED` 证据并停止。
- `coding/ownership.json` 在编码期间为 `cosh_active`，交还后为 `returned_to_hammer`；不存在活动所有权时不得执行细分任务。
- 最终测试、CR、E2E 和交付状态来自 Hammer，而不是观察板缓存。
- 以上硬门约束所有从 Cosh 入口启动和由 Cosh 接管的链路；若外部直接绕过本 skill 启动 Hammer Execute，Skill 进程无法充当常驻 hook。要对这种旁路实现进程级绝对拦截，需要 Hammer 提供正式 task-dispatch hook 或统一由 Cosh launcher 启动 Hammer。
