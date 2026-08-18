---
name: cosh-byted-superpowers-review-planner
description: 字节专属的强门禁研发流程。用户提供技术方案并要求进行稳定性、安全性、可行性评审，使用 AI-Spec 与 CodeGraph 分析代码，按 Superpowers 生成规格和计划，以最小修改面逐任务编码、执行 BITS 远程 UT、CR、规范提交、push 或查看实时观察板时使用。
---

# 字节 Superpowers 研发流程

## 目标

把技术方案转成可评审、可定位、可实施和可验证的 Superpowers 研发任务。所有入口共用同一套后端状态和证据校验；网站只提供实时观察与可选控制，不是唯一入口。

## 必读资源

- 开始流程或判断阶段前，完整读取 [`references/superpowers-workflow.md`](references/superpowers-workflow.md)。
- 启动 AI-Spec、CodeGraph 或三路评审前，完整读取 [`references/byted-admission-review.md`](references/byted-admission-review.md)。
- 分析仓库和精确定位时，完整读取 [`references/implementation-accuracy.md`](references/implementation-accuracy.md) 与 [`references/codegraph-implementation-location.md`](references/codegraph-implementation-location.md)。
- 生成计划、编码或 CR 前，完整读取 [`references/code-authoring-standards.md`](references/code-authoring-standards.md)。
- 编码或测试前，完整读取 [`references/byted-coding-remote-ut.md`](references/byted-coding-remote-ut.md)。
- 启动或解释观察板前，完整读取 [`references/realtime-dashboard.md`](references/realtime-dashboard.md)。

## 入口启动

- 显式使用本 skill 开始技术方案评审、正式研发或查看进度时，先解析目标仓库并建立当前 `<work-id>` 基础状态，再在 AI-Spec 门禁前启动观察板：

```bash
python3 <skill-root>/scripts/serve_superpowers_dashboard.py \
  --project <目标仓库> \
  --work <work-id> \
  --port 57171 \
  --open
```

- `<skill-root>` 是当前已加载 `SKILL.md` 所在目录；启动前先解析为绝对路径，不能依赖目标仓库的当前工作目录。
- 本地仓库必须组合使用 `--port 57171 --open`；`--open` 调用系统默认浏览器。脚本拒绝 `57171` 以外的端口，冲突时必须失败，不得降级。
- 目标仓库位于 CloudDev 等远端环境时，远端服务固定监听 `127.0.0.1:57171`，本机使用 `ssh -N -o ExitOnForwardFailure=yes -L 127.0.0.1:57171:127.0.0.1:57171 <remote-host>` 建立一对一隧道；隧道成功后在本机系统默认浏览器打开 `http://127.0.0.1:57171/?work=<work-id>`。禁止为任一端选择随机端口，也不能在远端用 `--open` 代替本机打开。
- 保持服务和远端隧道贯穿后续阶段，并向用户输出最终可访问的固定 URL。
- 自动打开失败不阻塞研发流程；保留服务并提供最终 URL 供手动打开。
- 用户仅解释、测试或维护本 skill 及其资源时，不启动观察板，避免递归触发。

## 不可变规则

- 前一阶段没有关联当前技术文档版本与代码 SHA 的有效通过证据时，不得进入后一阶段；缺失、解析失败、版本不符和证据过期一律 `fail closed`。
- 页面、API 和自然语言入口必须调用相同验证器。页面隐藏按钮不代表门禁，后端仍须拒绝越级请求。
- 本流程与 Hammer 在整个研发任务内硬互斥。选择本流程后，只能使用原生 Superpowers；禁止调用 `hammer`、`hammer-design`、`hammer-plan`、`hammer-execute`、`hammer-report`、`hammer-sync`、`hammer-lite`、`hammer-knowledge` 及其他 Hammer 流程，也不得读取、继承或写入 Hammer 状态和产物。
- 接收技术文档后，先完成 AI-Spec 知识门禁、CodeGraph 事实扫描以及稳定性、安全性、可行性三个独立 Subagent 评审；三路不得相互代替或继承过程结论。
- AI-Spec 必须安装或更新成功并完整加载部门知识；不支持通用规则或其他知识源降级，接入失败时直接阻塞。
- 技术文档修改前保留最近一次全量评审通过的冻结文档；修改后按 [`references/byted-admission-review.md`](references/byted-admission-review.md) 比较冻结文档与当前文档。只有可验证的非语义补充允许继承旧知识证据、CodeGraph 快照和三路结论；存在任一语义变化、证据缺失或判断不确定时，旧证据全部失效并重新执行完整评审。
- 未闭合 P0 强制阻塞且不可豁免。P1/P2/P3 只有在用户填写原因后才能通过观察板设为不阻塞；保留 Reviewer 原始证据，把审计记录绑定到当前文档版本、哈希、评审轮次、Reviewer 和 finding ID，绑定变化后自动失效。
- 评审闭环通过后才使用原生 Superpowers 生成规格与计划。保留原生产物格式，不写入字节专属控制字段。
- 修改位置必须明确到仓库、文件、符号、变量或接口。优先复用原有基建；无法复用时新增职责单一的窄函数，不得扩大修改面。
- 核心业务逻辑添加解释原因和边界的中文注释；关键状态、异常和外部调用复用现有日志体系，禁止泄露敏感数据。
- 业务 UT 禁止本地运行，只能使用 `bits-remote-ut`。禁止调用 Hammer、`hammer-*` 或 `test-remote-ut`。
- 全量远程 UT 与最终 CR 必须关联当前 HEAD 并通过，才允许普通 `git push`。不得自动调用 `$cosh-before-push`。
- 连续推进只能取消人工等待，不能跳过范围校验、远程 UT、CR、提交或任何全局门禁。
- `mode=single` 时只有后端 `authorized_task` 指向的任务可以产生代码改动。Task 1 默认授权；后续任务必须由用户当轮明确触发“推进下一个任务”后授权。不得从“继续”“完成全部任务”等历史或宽泛表述推断跨任务授权，Agent 不得代替用户调用推进控制。
- 任务范围校验覆盖 staged、unstaged、untracked 全工作区，而非只检查暂存区。发现未授权任务或范围外文件后立即停止并标记 `scope_violation`；保留改动等待用户决定不等于允许继续其他任务。
- 同一开发任务不得在 Superpowers 与 Hammer 之间切换。检测到 Hammer 引擎、调用记录、状态或产物时立即阻塞；如需改用 Hammer，先终止并归档当前任务，再建立完全独立的新任务。

## 主流程

严格按以下顺序执行：

1. 冻结技术文档来源、版本、SHA-256、目标、范围、非目标和验收标准，建立当前 `<work-id>` 基础状态。
2. 按“入口启动”在 AI-Spec 门禁前启动观察板并自动打开系统默认浏览器。
3. 自动安装或更新 AI-Spec 并记录知识证据；接入、更新、读取或证据校验失败时直接阻塞。
4. 使用 CodeGraph 和当前源码形成代码事实快照，记录文件、符号、变量、接口、调用链、可复用基建和代码 SHA。
5. 同时启动稳定性、安全性、可行性三个独立只读 Subagent，持续记录阶段、未通过风险点、证据和建议修改方式。
6. 汇总结论。存在阻塞时保持在评审阶段，并提供可选的技术文档修改入口；全量评审通过后保存带版本与 SHA-256 的冻结文档快照。
7. 用户修改技术文档时生成新版本和 diff，对比冻结文档并写入 `revision-assessment.json`。判断为 `carry-forward` 时继承冻结版本门禁；判断为 `full-review` 或判断证据无效时，从知识门禁重新执行完整评审。循环直到当前版本三路全部通过。
8. 用户确认评审闭环后，使用 `superpowers:brainstorming` 生成原生规格并完成书面确认。
9. 再次校验文件、符号、变量和接口定位；规格与代码事实冲突时退回评审。
10. 使用 `superpowers:writing-plans` 生成原生实施计划，每个实施子任务声明允许修改范围、验证与完成条件。
11. 按推进模式逐个实施子任务；全部完成后执行完整远程 UT、最终 CR、普通 push 和本地归档。

## 实施子任务

### 逐一任务校验

一次只允许开发一个实施子任务：

1. 锁定当前任务允许修改的文件、符号、变量和接口。
2. 每次写入前确认当前任务等于 `authorized_task`；写入后检查 staged、unstaged、untracked 完整 diff。范围外修改立即阻塞，不继续写其他任务。
3. 使用 `bits-remote-ut` 完成当前任务远程 UT。
4. 远程 UT 通过后完成当前任务 CR；未通过时只修复当前任务并重跑远程 UT 与 CR。
5. CR 通过后只把当前任务置为可完成；没有用户当轮明确推进动作时，下一任务保持 `locked`。
6. 用户触发推进时检查全工作区，拒绝范围外、未暂存、空提交或证据过期状态；只提交当前任务范围内的文件。
7. 记录 commit SHA 和任务授权审计后关闭当前范围，把 `authorized_task` 原子更新为下一任务；否则进入 `awaiting_approval` 并停止。

提交信息固定为：

```text
<type>: <中文摘要>

<work-id>-task<序号>
```

### 连续推进

记录 `mode=continuous` 后移除“推进下一个任务”的人工等待和页面按钮。每个实施子任务仍独立完成范围校验、远程 UT、CR 和规范提交；失败时立即停止。

## 状态与观察板

- 使用 `.superpowers/byted-work/<work-id>/` 保存字节门禁和证据旁路状态。
- 使用 `.superpowers/byted-work/<work-id>/dashboard-state.json` 原子保存最后有效观察板快照；该文件不属于门禁证据，也不参与状态版本计算。实时投影失败或服务重启恢复时只用于展示，并将所有推进动作禁用到真实证据重新可读。
- 使用 `docs/superpowers/specs/`、`docs/superpowers/plans/` 与 `.superpowers/sdd/` 读取原生产物。
- 入口阶段使用 [`scripts/serve_superpowers_dashboard.py`](scripts/serve_superpowers_dashboard.py) 自动启动并打开系统默认浏览器；用户关闭页面时仍按同一流程执行。
- 每次状态或证据变化后确认 SSE 已刷新；页面不一致时修复投影，不手工伪造状态。
- 多个开发任务并存时使用 `work=<work-id>` 切换，不能串写状态。

## 完成与归档

所有子任务完成后：

1. 使用 BITS 默认远程 pipeline 完成全量远程 UT。
2. 对当前 HEAD 完成最终 CR。
3. 两份证据都有效时才允许普通 push。
4. push 成功后自动生成本地复盘；取消或长期阻塞时允许手动归档。
5. 归档总结会话轮数、多轮原因、返工证据与可蒸馏规则。候选规则必须人工采纳，不得自动修改公共 skill。

## 质量检查

- 确认每个阶段的证据、版本、哈希、代码 SHA 和前置门禁有效。
- 确认三个 Reviewer 独立完成且所有阻塞风险点已闭合。
- 确认文档修订存在不可变冻结快照与完整差异判断；继承结论时所有语义变化维度均明确为 `false`。
- 确认计划覆盖规格，实施范围精确到文件、符号和变量。
- 确认只使用 BITS 远程 UT，并保留结构化通过证据。
- 确认每个提交符合中文 Conventional Commits 与任务标识格式。
- 确认观察板实时更新、自然语言可独立推进、本地归档被 gitignore。
