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

### market-analyst-team-agent

- agentId：`market-analyst-team-agent`
- 角色：市场分析团队 agent；整合行情、基本面、新闻、社交情绪和中国市场分析，形成面向投资决策的结构化分析材料。
- 适用场景：用户请求基于 TradingAgents-CN 风格进行股票、指数、行业、公司或市场主题分析；需要汇总市场数据、基本面信息、新闻事件、舆情情绪、A股/港股/美股市场差异，并输出证据优先的分析结论。
- 不适用场景：需要内部多空辩论时不直接指定本 agent，应优先指定 `market-research-team-agent`；需要最终投资策略或组合管理判断时指定 `market-management-team-agent`；需要交易执行计划时指定 `market-trader-agent`；需要最终风险裁决时指定 `market-risk-management-team-agent`；非金融市场分析任务回退 `main`。
- 输入要求：标的名称/代码/市场、分析时间范围、用户关注问题、已知数据来源或限制、是否允许联网获取实时数据、期望分析维度、输出语言和格式要求；如果数据不可得，应明确要求说明缺口而不是编造。
- 输出期望：结构化市场分析报告，包括行情概览、基本面要点、新闻/事件影响、情绪判断、市场规则差异、关键证据、明确不确定性、初步倾向和后续需要交给研究/管理/交易/风险 agent 的事项。
- 优先级关系：作为金融分析链路的前置分析 agent；当任务只要求事实分析和材料整理时优先使用本 agent；涉及投资结论辩论、策略、交易或风险裁决时，应按职责转交后续专业 agent；不确定时回退 `main`。
- 维护备注：该 agent 来源于 TradingAgents-CN 压缩后的五团队架构，保留真实数据优先、中文金融语境和多维分析特征。

### market-research-team-agent

- agentId：`market-research-team-agent`
- 角色：市场研究团队 agent；合并多头研究员与空头研究员，围绕投资观点进行证据驱动的内部辩论。
- 适用场景：用户需要对某个标的或投资主题进行多空对比、牛熊观点辩论、投资假设检验、利好利空拆解、核心分歧识别，或需要在分析材料基础上形成研究层面的倾向判断。
- 不适用场景：仅需收集行情/基本面/新闻/情绪材料时优先指定 `market-analyst-team-agent`；需要组合层面策略和最终投资建议时指定 `market-management-team-agent`；需要交易执行参数时指定 `market-trader-agent`；需要风险边界和最终风险裁决时指定 `market-risk-management-team-agent`；非投资研究辩论任务回退 `main`。
- 输入要求：标的名称/代码/市场、已有分析材料或数据摘要、用户关注的投资命题、时间周期、关键假设、风险偏好、需要辩论的争议点、不可编造数据的约束、期望输出格式。
- 输出期望：多头观点、空头观点、证据列表、反驳与再反驳、核心分歧、关键验证指标、研究结论倾向、置信度和需要管理团队进一步裁定的事项。
- 优先级关系：位于分析团队之后、管理团队之前；当任务重点是观点对抗和研究判断时优先使用本 agent；若缺少基础数据，应先由 `market-analyst-team-agent` 补充或回退 `main` 协调；不确定时回退 `main`。
- 维护备注：该 agent 保留 TradingAgents-CN 的 bull/bear debate 特征，要求证据先行、显式不确定性和禁止虚构数据。

### market-management-team-agent

- agentId：`market-management-team-agent`
- 角色：市场管理团队 agent；作为投资组合/研究经理，将分析和研究辩论转化为明确投资策略。
- 适用场景：用户需要最终或阶段性的投资策略判断，包括买入/持有/卖出建议、仓位方向、投资逻辑摘要、组合层面取舍、研究辩论后的管理裁决，或需要把多方材料压缩成可执行的策略框架。
- 不适用场景：只需要原始数据分析时指定 `market-analyst-team-agent`；只需要多空辩论时指定 `market-research-team-agent`；需要具体下单计划、入场价、止损止盈和执行节奏时指定 `market-trader-agent`；需要最终风险审查或风险裁决时指定 `market-risk-management-team-agent`；非投资管理策略任务回退 `main`。
- 输入要求：标的名称/代码/市场、分析团队结论、研究团队多空辩论摘要、用户投资周期、风险偏好、资金/仓位约束、禁止事项、目标输出形式、是否需要明确买入/持有/卖出结论。
- 输出期望：清晰投资策略，包括买入/持有/卖出结论、核心理由、适用条件、仓位建议或区间、目标价/估值区间的依据和不确定性、失效条件、后续交给交易或风险 agent 的要求。
- 优先级关系：位于研究团队之后、交易和风险团队之前；当任务需要策略裁决而非单纯分析时优先使用本 agent；若基础证据不足，应要求补充分析/研究或回退 `main` 协调；不确定时回退 `main`。
- 维护备注：该 agent 对应 TradingAgents-CN 中 manager/research manager 的压缩角色，强调把辩论结果变成可执行策略但不替代最终风险裁决。

### market-trader-agent

- agentId：`market-trader-agent`
- 角色：市场交易员 agent；把投资策略转化为可执行交易计划。
- 适用场景：用户需要交易执行方案，包括入场条件、目标价、止损位、止盈位、仓位分批、交易节奏、风险收益比、信心分数、风险分数和操作注意事项。
- 不适用场景：缺少投资策略或研究结论时不应直接指定本 agent，应先指定 `market-management-team-agent` 或回退 `main`；仅需市场材料分析时指定 `market-analyst-team-agent`；仅需多空辩论时指定 `market-research-team-agent`；需要最终风险裁决时指定 `market-risk-management-team-agent`；非交易执行任务回退 `main`。
- 输入要求：标的名称/代码/市场、管理团队策略结论、投资周期、可承受亏损、仓位限制、交易市场规则、资金规模或相对仓位、价格数据时点、用户偏好的保守/中性/激进执行风格、输出格式。
- 输出期望：可执行交易计划，包括操作方向、入场触发条件、目标价/区间、止损/止盈、分批执行方案、仓位建议、风险收益比、信心评分、风险评分、失效条件和需要风险团队复核的事项。
- 优先级关系：位于管理团队之后、风险团队之前；当任务已经有明确策略且需要落地交易时优先使用本 agent；如果策略未定或风险未审，应回退 `main` 或转交相应 agent；不确定时回退 `main`。
- 维护备注：该 agent 保留 TradingAgents-CN 的 trader 特征，输出必须行动化，同时明确价格数据时点和风险控制边界。

### market-risk-management-team-agent

- agentId：`market-risk-management-team-agent`
- 角色：市场风险管理团队 agent；合并激进、中性、保守和风险裁判视角，对投资/交易方案进行最终风险审查和裁决。
- 适用场景：用户需要风险评估、风险裁决、仓位上限、止损合理性、黑天鹅/流动性/政策/市场结构风险审查，或需要在激进/中性/保守观点之间形成最终风险建议。
- 不适用场景：只需要基础市场分析时指定 `market-analyst-team-agent`；只需要多空研究辩论时指定 `market-research-team-agent`；只需要策略管理结论时指定 `market-management-team-agent`；只需要交易执行细节草案时指定 `market-trader-agent`；非金融风险管理任务回退 `main`。
- 输入要求：标的名称/代码/市场、分析/研究/管理/交易阶段的结论或草案、用户风险偏好、投资期限、仓位限制、止损止盈方案、已知风险事件、数据时点、需要裁决的问题和输出格式。
- 输出期望：最终风险审查报告，包括激进/中性/保守视角、主要风险清单、风险等级、仓位和止损调整建议、是否通过/谨慎通过/不通过的裁决、触发复核条件、风险失效边界和用户需确认的关键事项。
- 优先级关系：作为金融分析链路的最终风控 agent；当任务涉及最终风险裁决或交易前审查时优先使用本 agent；若输入缺少策略或交易计划，应要求补充或回退 `main` 协调；不确定时回退 `main`。
- 维护备注：该 agent 对应 TradingAgents-CN 风险管理压缩团队，必须把风险控制作为核心输出，不得只给方向性乐观/悲观判断。

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
