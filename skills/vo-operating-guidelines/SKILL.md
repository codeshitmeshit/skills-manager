---
name: vo-operating-guidelines
description: Virtual Office 中任意 CLI 或 agent 需要判断是否处于 VO 环境、选择正确 VO skill、遵守 VO 工作边界、决定普通沟通还是申请 AI 会议、或处理 VO 不可用降级时使用；作为 VO 运行时协作、通信、浏览器和会议申请的总入口准则。
---

# Virtual Office 工作准则

## 目标

作为 Virtual Office 的总入口准则，先判断当前是否在 VO 环境中，再根据任务意图路由到合适的 VO skill，并约束 AI 何时可以申请会议、何时必须降级或等待用户。

本 skill 不替代专用 VO skill；普通通信、Codex 通信和浏览器操作必须路由到对应 skill。

## 工作流

### 1. 探测 Virtual Office

优先做 HTTP 探测，因为 AI 进程可能没有继承完整环境变量。常用端口当前默认多为 `8090`，测试环境可能是 `8038`：

```bash
curl -sS http://127.0.0.1:8090/status
curl -sS http://127.0.0.1:8090/api/agents
curl -sS http://127.0.0.1:8090/api/projects
```

如果 `8090` 不可用，可以尝试 `8038`。当接口返回 JSON，且 `/api/agents` 中存在 `agents` 列表时，基本可认为当前可访问 Virtual Office。

也可以辅助读取环境变量，但不要只依赖它们：

```bash
echo $VO_PORT
echo $VO_STATUS_DIR
echo $VO_GATEWAY_HTTP
```

如果未检测到 VO，明确说明“当前未检测到 Virtual Office”，停止 VO 专属动作，并询问用户是否改用普通协作方式继续。

### 2. 路由到专用 VO Skill

根据任务意图选择：

- 普通跨 agent 沟通、提问、短任务委派、状态转交、复用 `conversationId`：使用 `$vo-agent-communication`。
- 目标是 `codex-local` 或 `providerKind=codex` 的 Codex 协作者：使用 `$vo-codex-communication`。
- 需要访问网页、检索实时信息、读取页面内容或操作共享浏览器：使用 `$vo-browser-control`。
- 需要正式 AI 会议申请、多方同步决策、用户确认会议上下文或产出明确会议结论：继续使用本 skill 的会议判断规则；确定需要申请时读取 [references/meeting-requests.md](references/meeting-requests.md)。

不要把本 skill 当成普通通信或浏览器操作的完整手册；命中专用场景后应切换到对应 skill 的规则。

普通 agent 通信和 Codex 通信保持分开：先查询当前 agent 列表并识别目标的 `providerKind`，再路由。`providerKind=codex` 需要 Codex 专属健康检查和禁用 `sessions_send` 等规则；非 Codex agent 通信则关注 OpenClaw、Hermes 等平台不要绕过 VO 私有通道。不要把两类目标混用到同一个通信流程里。

### 3. 决定是否申请会议

默认先使用普通沟通。只有满足以下条件之一时，才申请 AI 会议：

- 需要另一个 AI 独立评审、补充专业判断或比较方案。
- 需要多方同步决策，而不是单个 agent 的一次性回复。
- 需要形成明确会议产出，例如决策、执行方向、风险结论或下一步责任。
- 会议上下文需要用户确认选择，例如 `selectedContextIds` 或补充上下文。

不要申请会议的场景：

- 普通问答、简单澄清或单轮意见请求。
- 自己卡住但只需要用户输入；此时向用户提问。
- 可以通过 `$vo-agent-communication` 或 `$vo-codex-communication` 完成的普通协作。
- 只是为了通知另一个 AI 或转交信息。

申请前必须说明 `goal`、`expectedOutcome` 和 `reason`。申请后停止等待用户处理，不要假设会议已经开始。

确定需要申请或查询 AI 会议时，读取 [references/meeting-requests.md](references/meeting-requests.md)，按其中流程识别参会者、提交请求、查询状态并处理用户控制面。

### 4. 用户控制面

AI 只能申请和查询会议请求，不要自行调用确认或拒绝接口。

自动推荐的上下文默认不会进入会议。只有用户确认时选择的 `selectedContextIds` 和补充的 `supplementalContext` 才会进入会议。

拒绝原因会写回来源任务评论，AI 后续可以在任务上下文里看到。不要绕过用户决定继续推进会议。

## 降级规则

- VO 不可用：说明当前未检测到 Virtual Office，停止 VO 专属动作，并询问是否改用普通协作方式。
- 会议申请失败：报告真实错误，不宣称已申请成功，不重复提交无幂等保障的请求。
- 无法确认项目或任务来源：说明当前会议接口只支持项目任务来源，向用户请求有效 `projectId` 和 `taskId`，或改用普通 agent 沟通。
- 参会者无法确认：停止申请，列出已发现的候选信息并要求用户确认，不猜测 ID。

## 质量检查

执行 VO 动作前确认：

- 已通过 HTTP 探测确认当前可访问 VO，或已明确降级。
- 已根据任务意图路由到正确 VO skill，没有用本 skill 替代专用通信或浏览器规则。
- 普通通信已先识别目标 `providerKind`，并在 `$vo-agent-communication` 和 `$vo-codex-communication` 之间选择其一。
- 普通协作已优先考虑专用通信 skill，会议只用于正式多方决策或需要用户确认上下文的场景。
- 需要提交或查询会议申请时，已读取 [references/meeting-requests.md](references/meeting-requests.md)。
- 没有自行 confirm/reject 会议，也没有替用户选择最终会议上下文。
