---
name: cosh-requirement-review-planner
description: 在产品需求澄清完成后，对需求和技术方案进行评审，必要时继续产品澄清并执行技术澄清；先生成并等待用户确认测试 checklist，再生成 todolist，并把进行中的 requirement.md、review.md、checklist.md、todolist.md 和 status.json 归档到 .cosh-docs/requirment/<需求名>/；标记为 done 后将整个需求目录移动到 .cosh-docs/requirment/archive/<需求名>/。用户要求方案评审、需求归档、断点续做、查看需求进度、从 checklist 推导开发测试或从 todolist 创建执行计划时使用。
---

# 需求方案评审与执行规划

## 目标

在产品需求已经经过初步澄清后，完成从需求归档、方案评审、测试清单确认到任务拆解的闭环。进行中的产物必须保存到 `.cosh-docs/requirment/<需求名>/`，标记为 `done` 后必须将整个需求目录移动到 `.cosh-docs/requirment/archive/<需求名>/`。所有阶段都通过 `status.json` 支持断点续做、人工确认和进度查看。

## 归档结构

每个进行中的需求使用一个独立目录：

```text
.cosh-docs/requirment/<需求名>/
├── requirement.md
├── review.md
├── checklist.md
├── todolist.md
└── status.json
```

完成的需求使用同样的目录结构，但必须整体移动到：

```text
.cosh-docs/requirment/archive/<需求名>/
├── requirement.md
├── review.md
├── checklist.md
├── todolist.md
└── status.json
```

`<需求名>` 使用用户给出的需求名称；如果没有明确名称，先基于需求内容生成一个简短英文需求概括并请用户确认。自动生成的目录名必须使用 kebab-case，也就是小写英文单词用短横线连接，例如 `skill-cli-scope-update-filter`。目录名避免路径分隔符和控制字符，不使用中文、空格、下划线或驼峰。

`status.json` 记录当前阶段，必须在每次阶段推进后更新：

```json
{
  "name": "<需求名>",
  "stage": "checklist_draft",
  "waiting_for_user": true,
  "updated_at": "2026-06-07T00:00:00+08:00",
  "confirmed": {
    "checklist": false,
    "tested": false,
    "done": false
  },
  "confirmations": {
    "checklist": null,
    "tested": null,
    "done": null
  },
  "files": {
    "requirement": "requirement.md",
    "review": "review.md",
    "checklist": "checklist.md",
    "todolist": null
  },
  "notes": []
}
```

阶段枚举按顺序使用：

- `requirement_archived`：需求文档已归档。
- `product_clarifying`：仍需要产品澄清。
- `technical_clarifying`：仍需要技术澄清。
- `reviewed`：方案评审完成，暂无阻塞问题。
- `checklist_draft`：已生成 checklist，等待用户确认。
- `checklist_confirmed`：用户已确认 checklist。
- `todolist_created`：已生成 todolist。
- `plan_created`：已根据 todolist 创建执行 plan。
- `implementation_done`：开发已完成。
- `tested`：已按 checklist 完成测试。
- `done`：需求闭环完成。设置该阶段后，必须把整个需求目录从 `.cosh-docs/requirment/<需求名>/` 移动到 `.cosh-docs/requirment/archive/<需求名>/`。
- `paused`：需求暂停，后续可恢复。
- `cancelled`：需求废弃，默认进度列表中隐藏。

`waiting_for_user` 用于标记当前阶段是否等待用户动作。不要用它替代 `stage`；例如 checklist 待确认时应同时使用 `stage: "checklist_draft"` 和 `waiting_for_user: true`。

必须人工确认的节点：

- checklist 初次确认。
- 方案变更后重新生成的 checklist 再确认。
- checklist 测试通过确认。
- 最终 `done` 确认。

每次人工确认都要同时写入对应 Markdown 文件和 `status.json.confirmations`。确认记录至少包含确认项、确认时间和用户确认摘要。

## 工作流

1. 先读取或创建需求目录。
   - 如果用户要求继续已有需求，先运行或建议运行 `scripts/requirement_status.py` 查看现有归档；默认只展示进行中需求，使用 `--all` 时也展示 `archive/` 下的已完成需求。
   - 如果目录已存在，读取 `status.json` 和已有文档，从当前阶段继续，不重复已确认步骤。
   - 断点续做时恢复到具体文件状态，检查 `requirement.md`、`review.md`、`checklist.md`、`todolist.md` 和 `status.json` 哪些存在、哪些缺失。
   - 如果要恢复已归档的 `done` 需求，先明确告知用户该需求位于 `.cosh-docs/requirment/archive/<需求名>/`，并等待用户确认是否重新打开；重新打开时才移动回 `.cosh-docs/requirment/<需求名>/` 并更新阶段。
2. 整理 `requirement.md`。
   - 记录需求背景、目标用户、目标、范围、非目标、关键约束和当前已知结论。
   - 如果产品信息仍不足，调用或建议使用 `cosh-product-clarifier` 继续产品澄清；不要进入方案评审。
3. 做方案评审并写入 `review.md`。
   - 先检查产品层面是否仍有歧义。
   - 再做技术澄清，检查架构、接口、数据、权限、状态流、异常处理、兼容性、迁移、性能、安全、可观测性和测试可行性。
   - 如果存在阻塞性技术问题，列出问题和建议选项，等待用户补充；不要生成 checklist。
   - 如果没有阻塞问题，记录评审结论并进入 checklist。
4. 生成 `checklist.md`，然后停止等待用户确认。
   - checklist 必须覆盖验收标准、主要流程、边界条件、错误场景、回归点、数据状态、权限或安全点、兼容性、可观测性和人工验证步骤。
   - 每个 checklist 项必须有稳定编号，例如 `CHK-001`。
   - 每个 checklist 项都应说明验证方法、预期结果和关联需求点。
   - 明确写出 `确认状态：待确认`。
   - 将 `status.json` 更新为 `stage: "checklist_draft"`、`waiting_for_user: true`。
   - 在用户明确确认 checklist 前，不得生成 `todolist.md`。
5. 用户确认 checklist 后，更新 `checklist.md` 和 `status.json`。
   - 将 `确认状态：待确认` 改为 `确认状态：已确认`。
   - 在 `checklist.md` 中追加人工确认记录。
   - 设置 `confirmed.checklist` 为 `true`，写入 `confirmations.checklist`，阶段推进到 `checklist_confirmed`，并设置 `waiting_for_user: false`。
6. 生成 `todolist.md`。
   - todolist 必须能让 agent 据此创建执行 plan。
   - 每个任务使用稳定编号，例如 `TODO-001`。
   - 每个任务必须包含目标、涉及区域、输入、输出、依赖、完成标准和关联 checklist 编号。
   - todolist 必须覆盖从实现、测试到文档更新的工作。
7. 后续执行开发时，根据 `todolist.md` 创建 plan。
   - plan 的每一步必须能追溯到一个或多个 `TODO-*`。
   - 开发完成后必须按 `checklist.md` 执行测试，并把测试结果写回 checklist 或交付说明。
   - 测试通过后必须等待用户人工确认，再设置 `confirmed.tested`。
   - 最终闭环必须等待用户人工确认，再设置 `stage: "done"`、`confirmed.done: true`、`waiting_for_user: false`，写入最终确认记录，然后将整个需求目录移动到 `.cosh-docs/requirment/archive/<需求名>/`。
   - 移动前如果 `.cosh-docs/requirment/archive/<需求名>/` 已存在，必须先停止并询问用户如何处理，不能覆盖已有归档。
8. 如果方案在 checklist 确认后发生变化，必须重新生成 checklist 并再次等待人工确认。
   - 将旧 checklist 中受影响项标记为已失效或被替换。
   - 更新 `status.json` 为 `stage: "checklist_draft"`、`waiting_for_user: true`、`confirmed.checklist: false`。

## 进度查看脚本

使用 `scripts/requirement_status.py` 扫描需求归档：

```bash
python3 skills/cosh-requirement-review-planner/scripts/requirement_status.py
python3 skills/cosh-requirement-review-planner/scripts/requirement_status.py --root /path/to/project
python3 skills/cosh-requirement-review-planner/scripts/requirement_status.py --all
python3 skills/cosh-requirement-review-planner/scripts/requirement_status.py --json
```

脚本默认扫描当前项目的 `.cosh-docs/requirment/`，展示未完成且未废弃的进行中需求；`paused` 会默认展示，`done` 和 `cancelled` 默认隐藏。使用 `--all` 查看全部需求，并包含 `.cosh-docs/requirment/archive/` 下的完成归档。如果 `status.json` 缺失，会根据文件存在情况做保守推断，并在输出中标记。

## 输出规则

- 进行中的需求归档路径固定为 `.cosh-docs/requirment/<需求名>/`；标记为 `done` 后路径固定为 `.cosh-docs/requirment/archive/<需求名>/`。
- 未明确提供需求名时，自动生成的 `<需求名>` 必须是英文 kebab-case，格式为 `word-word-word`。
- 先产出 `requirement.md` 和 `review.md`。
- 只有方案评审无阻塞问题后才产出 `checklist.md`。
- 只有用户明确确认 checklist 后才产出 `todolist.md`。
- 每次推进阶段都更新 `status.json`。
- 最终设置 `stage: "done"` 后，必须把整个需求目录移动到 `.cosh-docs/requirment/archive/<需求名>/`，并在交付时说明新的归档路径。
- 暂停需求时使用 `stage: "paused"`；废弃需求时使用 `stage: "cancelled"`。
- 交付时说明当前需求名、当前阶段、已更新文件和下一步动作。

## 质量检查

交付前确认：

- 没有跳过产品澄清或技术澄清中的阻塞问题。
- checklist 未确认前没有创建 todolist。
- checklist 项有编号、验证方法、预期结果和关联需求点。
- todolist 项有编号、依赖、完成标准和关联 checklist 编号。
- 自动生成的需求目录名使用英文 kebab-case，不使用中文、空格、下划线或驼峰。
- `status.json` 的阶段与实际文件一致。
- `stage: "done"` 的需求已经位于 `.cosh-docs/requirment/archive/<需求名>/`，而不是留在进行中目录。
- 等待用户动作时 `waiting_for_user` 为 `true`，但 `stage` 仍保留业务阶段。
- 所有人工确认都同时记录在 Markdown 和 `status.json.confirmations`。
- 用户可以通过脚本查看所有需求和当前进度。
