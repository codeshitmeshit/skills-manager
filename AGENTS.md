# 新建 Skill 规则

本文档定义在本仓库新增或更新 skill 时的统一规范。目标是让每个 skill 都有清晰触发条件、低上下文成本、可复用资源和可验证的产出。

## Push 前强制门禁

- 用户提出 push、推送、同步到远端或任何会执行 `git push` 的请求时，必须先调用 `$cosh-before-push`；“推送吧”“直接推”“提交并推送”等简短表达同样触发。
- 不得把 `$cosh-before-push` 理解为 Git hook、仓库脚本或 bytedcli 流程，也不得先执行 `git push` 再补做评审。
- 门禁必须完成 Coco runner、正确性、安全性、注释实现一致性四路 CR，并由主执行者汇总结论。
- 优先评审尚未推送的 commits；仅当没有未推送 commit 时才评审暂存区文件，两者都为空时返回无需评审。
- 默认当前任务独占评审期间的工作区，不考虑其他进程并发创建 commit 或修改暂存区的假设场景；不要因此扩大门禁。
- 门禁只对结论输出时选定的代码快照负责；结论之后用户或主流程再修改、暂存或创建 commit 属于范围外风险，本 skill 不负责追踪或补审。
- 用户最初提出 push 只授权启动 CR，不授权最终推送。展示完整门禁报告后，必须等待用户再次明确确认；不得在同一轮自动执行 `git push`。
- 结论为“同意 push”或“无需评审”时也必须等待最终确认。用户在报告后明确回复推送、继续或同意，才执行普通 `git push`。
- 结论为不同意时先展示问题；只有用户在看到问题后明确接受风险并要求继续，才允许执行普通 `git push`，且不得声称 CR 通过。
- 本门禁只约束代码 CR，不扩展检查 push URL、refspec、force、upstream、hook、认证或传输方式。

## 基本原则

- 默认在 `skills/cosh-<skill-name>/` 下创建 skill，目录名必须和 frontmatter 的 `name` 完全一致。
- 新建 skill 名称必须以 `cosh-` 开头，例如 `cosh-tutorial-html-docs`。
- Virtual Office 基础设施专用 skill 可以使用 `vo-` 前缀；该例外仅用于明确服务 Virtual Office 通信、路由或运行时协作的 skill。
- skill 名称只使用小写字母、数字和短横线。
- 只写 Codex 执行任务所需的知识，不写 README、安装说明、变更日志或过程复盘。
- `SKILL.md` 保持精简，复杂细节放入 `references/`，可复用文件放入 `assets/`，确定性操作放入 `scripts/`。
- 先沉淀可复用资源，再写长篇说明；不要把大段模板、脚本或参考资料塞进 `SKILL.md`。
- 优先让 skill 服务具体任务，不创建“泛泛而谈”的知识库型 skill。

## 推荐结构

```text
skills/
└── cosh-<skill-name>/
    ├── SKILL.md
    ├── agents/
    │   └── openai.yaml
    ├── assets/
    ├── references/
    └── scripts/
```

只有确实需要时才创建 `assets/`、`references/`、`scripts/`。不要留下空目录或占位示例文件。

## SKILL.md 规范

`SKILL.md` 必须包含 YAML frontmatter 和正文。

frontmatter 默认只放两个字段；仅当 skill 只适用于部分 CLI 时，额外添加仓库支持的 `cli_scope`：

```yaml
---
name: cosh-<skill-name>
description: <用中文说明 skill 能做什么以及何时使用>
# 可选：cli_scope: [openclaw, hermes]
---
```

`description` 是触发 skill 的主要依据，必须同时说明：

- skill 能做什么。
- 用户怎么问时应该触发。
- 涉及哪些文件类型、工具、任务场景或产出形式。
- 必须使用中文撰写；以后新增或更新本仓库的 skill 描述都使用中文。

不要在正文里写“何时使用此 skill”作为主要触发说明，因为正文只有触发后才会被读取。

正文应使用命令式、流程化写法，建议包含：

- 目标：skill 要稳定完成什么任务。
- 工作流：执行任务的步骤顺序。
- 资源说明：什么时候读取 `references/`，什么时候复制或改写 `assets/`，什么时候运行 `scripts/`。
- 输出规则：文件放哪里、命名规则、格式要求、用户最终从哪里查看结果。
- 质量检查：交付前必须验证的事项。

## 资源放置规则

`assets/` 用于输出时会被复制、改写或引用的资源，例如 HTML 模板、前端工程模板、图标、字体、示例配置。

`references/` 用于需要按需读取的知识，例如 API 文档摘要、数据表结构、业务规则、格式规范。每个 reference 都应从 `SKILL.md` 直接链接，不要多层嵌套引用。超过 100 行的 reference 顶部应有简短目录。

`scripts/` 用于重复、易错或需要确定性的操作，例如文件转换、校验、批处理生成。新增脚本后必须实际运行代表性测试。

资源和说明不要重复维护：如果模板已经在 `assets/`，`SKILL.md` 只说明何时使用模板和关键约束，不内联完整模板。

## agents/openai.yaml 规范

推荐为每个可正式使用的 skill 创建 `agents/openai.yaml`：

```yaml
interface:
  display_name: "<人类可读名称>"
  short_description: "<一句话说明用途>"
  default_prompt: "Use $cosh-<skill-name> to ..."
```

要求：

- `display_name` 面向用户，简短清楚。
- `short_description` 说明 skill 的实际产出。
- `default_prompt` 使用英文，包含 `Use $cosh-<skill-name>`，并描述一个典型任务。
- 不添加未明确需要的额外字段。

## 新建流程

1. 明确 skill 的具体使用场景，至少能说出 2 到 3 个用户会怎么请求。
2. 为每个使用场景判断是否需要 `scripts/`、`references/` 或 `assets/`。
3. 创建 `skills/cosh-<skill-name>/SKILL.md`，写入合法 frontmatter。
4. 添加必要资源；删除所有无用占位文件。
5. 创建或更新 `agents/openai.yaml`。
6. 检查 `SKILL.md` 是否过长；如果超过约 300 行，优先拆到 `references/` 或 `assets/`。
7. 用一个真实任务心智演练该 skill：只读 frontmatter 能否触发，读正文后能否完成任务。
8. 运行可用的校验或测试；没有脚本时至少检查文件结构、frontmatter、链接路径和资源引用。

如果可以使用 `skill-creator` 自带脚本，优先用其初始化和校验流程；如果当前仓库没有这些脚本，则按本文件手动创建并核对。

## 更新已有 Skill

- 先读取现有 `SKILL.md`、`agents/openai.yaml` 和相关资源。
- 保持已有触发语义，除非用户明确要求重定位 skill。
- 如果新增大段模板、示例或规范，优先放入 `assets/` 或 `references/`，再精简 `SKILL.md`。
- 不删除用户已有资源，除非确认它们不再被引用且属于当前修改范围。
- 修改后检查 `agents/openai.yaml` 是否仍匹配 skill 的用途。

## 质量检查清单

交付前确认：

- `skills/cosh-<skill-name>/SKILL.md` 存在。
- frontmatter 包含 `name` 和 `description`，且 `name` 等于目录名；仅按需额外包含合法的 `cli_scope`。
- `name` 和目录名都以 `cosh-` 开头；明确属于 Virtual Office 基础设施的 skill 可以改用 `vo-` 前缀。
- `description` 足以让 Codex 判断触发时机。
- `SKILL.md` 没有塞入可外置的大段模板、脚本或参考资料。
- 所有从 `SKILL.md` 提到的资源路径都真实存在。
- `agents/openai.yaml` 与 skill 名称和用途一致。
- 没有无用 README、占位文件、空目录或调试产物。
- 若新增脚本，已运行代表性测试并记录结果。
