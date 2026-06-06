---
name: cosh-openclaw-agent-guide
description: Hermes 已决定调用 OpenClaw，但需要选择或理解 OpenClaw 内部 agent 时使用；提供 OpenClaw agent 的角色说明、agentId、适用场景、输入输出和兜底调用规则。
cli_scope:
  - openclaw
  - hermes
---

# OpenClaw Agent 调用指南

## 目标

帮助 Hermes 在调用 OpenClaw 时选择正确的 OpenClaw 内部 agent。

本指南不是判断“是否应该调用 OpenClaw”的总开关，也不是普通 skill 路由器。它只在 Hermes 已经决定调用 OpenClaw 后使用，用来理解 OpenClaw 内部各 agent 的角色、适用场景、调用输入、输出期望和优先级关系。

## 核心规则

Hermes 调用 OpenClaw 时必须明确指定目标 agent：

1. 如果 Hermes 能确定最合适的 OpenClaw agent，直接使用该 agent 的 `agentId`。
2. 如果 Hermes 不确定应该调用哪个 agent，指定 `main`。
3. 如果目标 agent 不在当前可用 agent 清单里，指定 `main`，并在任务中说明原本想指定的 agent 和原因。
4. 如果任务跨多个 agent 角色，指定 `main`，由 `main` 判断是自己处理还是继续分派。
5. 不要使用 `recommended_agent`、`preferred_agent` 或类似软推荐字段作为 OpenClaw 原生能力假设。

`main` 是固定兜底协调 agent。Hermes 不确定时，不应自行猜测相近 agent，也不应停止在选择阶段；应把任务交给 `main`，由 `main` 决定后续处理方式。

## 什么时候使用本指南

当以下条件同时成立时，Hermes 应使用本指南：

1. Hermes 已经决定调用 OpenClaw。
2. Hermes 需要选择 OpenClaw 内部 agent，或需要理解某个 OpenClaw agent 的职责。
3. Hermes 需要知道调用某个 agent 前应提供什么信息，以及调用后应期待什么结果。

典型场景：

1. 用户请求需要交给 OpenClaw 内部某个专业 agent。
2. Hermes 需要在多个 OpenClaw agent 之间做选择。
3. Hermes 不确定目标 agent，需要确认是否回退到 `main`。
4. OpenClaw agent 清单更新后，Hermes 需要按最新角色说明进行调用。

## 什么时候不要使用本指南

当以下任一条件成立时，不使用本指南：

1. Hermes 还没有决定是否调用 OpenClaw。
2. 用户只是要求选择普通 skill，而不是选择 OpenClaw 内部 agent。
3. 用户已经明确要求使用某个非 OpenClaw skill。
4. 任务可以由 Hermes 当前能力直接完成，不需要进入 OpenClaw。
5. 任务需要更新本指南本身；此时应按用户要求直接维护本 skill，而不是把它当作调用依据。

## 调用决策流程

Hermes 调用 OpenClaw 前，按以下流程选择 agent：

1. 查看“OpenClaw Agent 清单”。
2. 找出适用场景与任务最匹配的 agent。
3. 确认可用清单中存在该 agent 的 `agentId`。
4. 如果匹配明确且 `agentId` 可用，指定该 `agentId`。
5. 如果匹配不明确、多个 agent 都可能适用、任务跨多个角色，或目标 `agentId` 不可用，指定 `main`。
6. 指定 `main` 时，在任务中说明不确定点、候选 agent、原始用户目标和希望 `main` 判断的事项。

## 调用输入要求

Hermes 调用 OpenClaw agent 时，应尽量提供：

1. 用户原始目标。
2. Hermes 对任务的简短理解。
3. 指定的 `agentId`。
4. 选择该 agent 的原因。
5. 已知约束、边界和不能做的事。
6. 期望输出格式或交付物。
7. 如果指定 `main`，说明为什么没有直接指定专业 agent。

不要把 agent 选择写成模糊建议。确定目标 agent 时，直接指定 `agentId`；不确定时，明确指定 `main`。

## OpenClaw Agent 清单

以下清单由 OpenClaw 在本 skill 创建后维护和更新。Hermes 在选择具体 OpenClaw agent 时，应优先参考本节。

### main

- agentId：`main`
- 角色：固定兜底协调 agent。
- 适用场景：Hermes 不确定应该调用哪个 agent；目标 agent 不在可用清单里；任务跨多个 agent 角色；需要 OpenClaw 内部继续判断或分派。
- 不适用场景：Hermes 已能明确选择某个可用专业 agent，且任务不需要协调。
- 输入要求：用户原始目标、Hermes 的任务理解、不确定点、候选 agent 或原本想指定的 agent、希望 main 判断或分派的事项。
- 输出期望：由 main 自行处理，或说明其分派给了哪个 agent，以及返回处理结果、分派理由或继续澄清的问题。
- 优先级关系：作为兜底优先级最高；只有在专业 agent 明确可用且匹配时，才优先指定专业 agent。
- 维护备注：该条目是本指南的固定规则，OpenClaw 更新 agent 清单时不应删除。

### Agent 条目模板

OpenClaw 后续补充 agent 时，必须使用以下结构。每个 agent 条目都必须包含 `agentId`，Hermes 不应根据名称猜测调用目标。

```markdown
### <agent-name>

- agentId：`<agent-id>`
- 角色：<该 agent 在 OpenClaw 内部负责什么>
- 适用场景：<Hermes 在什么任务下应指定该 agentId>
- 不适用场景：<哪些相似任务不应该指定该 agentId>
- 输入要求：<Hermes 调用前需要提供哪些信息>
- 输出期望：<Hermes 调用后应期待什么结果>
- 优先级关系：<与其他 agent 冲突时如何选择；不确定时是否回退 main>
- 维护备注：<由 OpenClaw 更新的补充说明>
```

### 待 OpenClaw 更新

OpenClaw 应在后续维护中补充当前可调用 agent 的实际条目，包括每个 agent 的 `agentId`、角色、适用场景、不适用场景、输入要求、输出期望和优先级关系。

## Hermes 调用格式

Hermes 调用明确 agent 时，任务上下文应包含：

```markdown
OpenClaw agentId：<target-agent-id>

任务目标：
<用户原始目标和 Hermes 的简短理解>

选择原因：
<为什么该 agent 最适合处理>

约束和期望：
- <约束 1>
- <期望输出 1>
```

Hermes 回退到 `main` 时，任务上下文应包含：

```markdown
OpenClaw agentId：main

任务目标：
<用户原始目标和 Hermes 的简短理解>

回退原因：
<为什么 Hermes 无法明确指定专业 agent，或为什么目标 agent 不可用>

候选 agent：
- <候选 agent 或原本想指定的 agent>：<原因>

希望 main 判断：
- 由 main 自己处理，或分派给合适的 OpenClaw agent。
- 如果需要分派，请在结果中说明分派对象和理由。
```

## 质量检查

Hermes 使用本指南时，应确认：

- 已经决定调用 OpenClaw，而不是还在判断是否调用 OpenClaw。
- 已优先查看 OpenClaw Agent 清单。
- 明确 agent 可用时，直接指定对应 `agentId`。
- 不确定、不可用或跨角色任务时，指定 `main`。
- 没有把 `recommended_agent` 当作 OpenClaw 原生字段。
- 没有靠 agent 名称猜测 `agentId`。
- 给 OpenClaw 的任务上下文包含用户目标、选择原因、约束和输出期望。
