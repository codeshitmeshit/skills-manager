# OpenSpec 驱动的需求评审 Skill 改造设计

## 背景

`cosh-requirement-review-planner` 当前使用 `.cosh-docs/requirment/<name>/`、`status.json`、`checklist.md` 和 `todolist.md` 维护独立的需求状态机。这套状态与 OpenSpec 的 artifact 状态重叠，容易出现规格、实现计划和实际进度不一致。

本次改造让 OpenSpec 成为需求状态、规格和变更产物的唯一事实来源。`cosh-requirement-review-planner` 只负责产品澄清衔接、技术评审、人工确认门禁以及对 OpenSpec workflow 的编排。

## 产品决策

- 所有代码变更都进入 OpenSpec，包括小修复、配置修改、新功能和重构。
- 产品澄清结束后，先展示需求总结；用户确认后才进入 OpenSpec。
- 本地缺少 OpenSpec 时，先告知用户，再自动安装并初始化；失败时停止，不降级绕过。
- 规格优先于实现。编码期间出现任何新增或变化要求时，暂停编码，先更新并重新确认规格。
- 规格、技术方案、任务清单、测试结果和最终归档都需要用户分别确认。
- 只有全部规格场景验证通过、任务完成并得到最终确认后，才能归档。

## 信息源优先级

1. 当前项目安装和初始化后生成的 OpenSpec skills、commands 与 schema。
2. OpenSpec 当前版本的官方文档和官方仓库。
3. 当前项目的 `openspec/` 配置、自定义 schema 和已有 artifacts。
4. `technical-review-rubric.md` 等本地评审规则，仅作为补充检查项。
5. Skill 内样例仅用于说明，不得覆盖实际版本规则。

如果来源之间冲突，以更高优先级来源为准。不得在 skill 中硬编码可能随 OpenSpec 版本变化的 artifact 细节。

## 职责边界

### OpenSpec

- 定义 artifact 类型、依赖、状态与合法转换。
- 管理 `proposal`、`specs`、`design`、`tasks`、实现、验证和归档。
- 提供项目当前版本可用的 skills、commands 和 schema。

### cosh-requirement-review-planner

- 判断产品需求是否已经澄清。
- 在进入 OpenSpec 前展示需求总结并等待确认。
- 检查 OpenSpec 可用性，告知并执行必要的安装、初始化或更新。
- 调用当前项目实际提供的 OpenSpec skills/commands 推进 artifacts。
- 使用本地技术评审 rubric 审阅 OpenSpec design。
- 在关键阶段执行人工确认门禁。
- 检测规格变化并阻止实现继续，直到受影响 artifacts 重新确认。

## 状态与产物

OpenSpec 的 change 目录和命令结果是唯一主状态。Skill 不再创建或推进独立的 `status.json`。

旧产物与新职责的映射如下：

| 旧产物 | 改造后 |
| --- | --- |
| `requirement.md` | OpenSpec proposal 与 specs |
| `review.md` | 评审意见直接推动 proposal、specs 或 design 修订 |
| `checklist.md` | OpenSpec scenarios 与验证结果 |
| `todolist.md` | OpenSpec tasks |
| `status.json` | OpenSpec artifact 状态与命令输出 |
| `.cosh-docs/.../archive` | OpenSpec archive workflow |

如需兼容旧项目，只允许把旧状态读取为迁移输入；迁移完成后不得继续双写。

## 主流程

1. 产品澄清结束，整理需求总结。
2. 等待用户确认需求总结。
3. 检查当前项目是否存在可用的 OpenSpec。
4. 如缺失，先告知用户，再安装并初始化；如已存在，读取项目实际 skills、commands、schema 和配置。
5. 使用 OpenSpec workflow 创建或继续 change，并生成需求 artifacts。
6. 等待用户确认规格。
7. 生成或更新技术设计，使用本地 rubric 补充评审。
8. 等待用户确认技术方案。
9. 生成或更新实现任务。
10. 等待用户确认任务清单。
11. 按 OpenSpec workflow 进入编码。
12. 运行 OpenSpec 验证流程，展示场景、任务和测试证据。
13. 等待用户确认测试结果。
14. 等待用户最终确认。
15. 使用 OpenSpec workflow 归档。

每一步应先发现当前项目实际支持的 OpenSpec 操作，再调用对应能力；skill 不假设某个命令在所有版本中都存在。

## 规格变更与回退

实现开始后，只要用户提出新增或变化要求：

1. 立即暂停编码。
2. 使用 OpenSpec workflow 更新 proposal/specs。
3. 等待用户重新确认规格。
4. 检查 design、tasks 和验证场景是否受影响。
5. 更新所有受影响 artifacts，并分别重新执行对应确认门禁。
6. 所有受影响阶段重新确认后，才允许恢复编码。

实现不得先于规格更新，也不得在完成代码后补写规格。

## 安装和异常处理

- 检查应区分“命令未安装”“项目未初始化”“项目配置损坏”“版本需要刷新”和“artifact 状态冲突”。
- 自动安装或初始化前必须告知用户即将发生的动作。
- 安装、初始化、更新或状态读取失败时，报告具体阻塞，不得回退到旧状态机继续编码。
- 不自动覆盖项目已有 OpenSpec 配置或自定义 schema。
- 对可能改变既有 artifacts 的更新操作，应先展示影响并等待确认。

## 样例和参考资料

Skill 可以提供基于实际 OpenSpec 版本生成并脱敏的完整 change 样例，但样例必须明确标记为非权威资料。样例至少覆盖：

- proposal、specs、design 和 tasks 的完整链路。
- 关键阶段的人工确认点。
- 编码期间规格变化导致 design、tasks 和验证重新确认。
- 验证完成后经用户确认再归档。

详细 OpenSpec 操作说明宜放入独立 reference，`SKILL.md` 只保留稳定的编排原则和门禁。

## 现有资源处理

- 保留 `references/technical-review-rubric.md`，用于补充技术设计评审。
- 重写 `SKILL.md` 中的归档结构、状态枚举、工作流、输出规则和质量检查。
- 废弃或改写 `scripts/requirement_status.py`，使其不再读取 `.cosh-docs` 独立状态；如果 OpenSpec 已提供足够的状态查询能力，优先删除该脚本。
- 更新 `agents/openai.yaml`，确保描述与新职责一致。

## 验收标准

- Skill 明确规定 OpenSpec 是唯一主状态和主要信息源。
- 所有代码变更都必须进入 OpenSpec，且没有旧流程降级路径。
- 本地缺少 OpenSpec 时会先告知，再安装和初始化。
- 五个人工确认门禁完整存在，且不得被自动跳过。
- 规格变化会暂停实现，并使受影响阶段重新确认。
- `status.json`、`checklist.md`、`todolist.md` 不再作为平行事实来源。
- 技术评审 rubric 只补充 OpenSpec design，不定义独立状态。
- 安装失败、状态冲突或配置损坏时会停止，不绕过 OpenSpec。
- Skill 不硬编码特定 OpenSpec 版本中不稳定的命令和 artifact 格式。

## 非目标

- 不修改 OpenSpec 自身的 schema 或实现。
- 不为 OpenSpec 创建另一套镜像状态数据库。
- 不在本次改造中修改 `cosh-product-clarifier` 或 `cosh-tech-implementation-planner`。
- 不自动迁移所有历史 `.cosh-docs/requirment/` 数据；只定义未来的兼容原则。
