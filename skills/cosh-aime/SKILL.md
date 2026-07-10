---
name: cosh-aime
description: 当用户要求“让 AIME”“问 AIME”“用 AIME”完成 AI 对话、空间或会话查询、发送文本或本地附件、获取回复，或使用 AIME DeepWiki 生成和读取仓库文档时使用。
---

# AIME 任务

## 目标

通过 `bytedcli aime` 实际完成用户交给 AIME 的任务，并把结果整理后返回。不要只给出命令教程。

## 工作流

1. 确认 `bytedcli` 可用；鉴权异常时运行 `bytedcli --json auth status`，按 `error.hint` 或 `error.auth_command` 处理。
2. 从用户意图选择 `space`、`session`、`chat`、`interactive` 或 `deepwiki`。参数不确定时先运行对应层级的 `--help`，不要猜命令或选项。
3. 机器可读调用把 `--json` 放在命令域前：`bytedcli --json aime ...`。需要面向终端持续流式交互时不要强制 JSON。
4. 执行任务，解析结果；向用户返回结论、关键 ID 和后续继续操作所需的信息，不倾倒无关原始 JSON。

## 操作规则

### Space 与 session

- 查询空间使用 `space list/get`；查询会话使用 `session list/get/get-output`。
- “我有哪些空间/会话”等枚举请求默认视为要求完整结果；列表存在 `next_id` 时继续翻页。
- 用户未指定 space 时沿用 CLI 的个人空间默认值；若名称匹配多个空间，先列出候选，不猜 ID。
- 用户明确要求创建会话、发送消息或让 AIME 处理内容，即视为授权对应操作。目标空间、会话或内容存在实质歧义时再询问。

### 对话与附件

- 普通文本对话可用 `chat --auto-session --message ...`；需要稳定等待完整结果时加 `--no-stream`。
- 附件或非流式任务优先单步调用 `session send --content ... --upload-file ... --wait`；省略 session ID 会自动创建会话，不要无故先调用 `session create`。
- 上传前确认用户所指文件路径唯一、文件存在且是普通文件。用户明确指定附件并要求交给 AIME 时无需重复确认；不要自行扩大上传范围。
- 未指定模式时保留 `auto`，不要臆测 `chat` 或 `agent`。
- 如果消息已提交但等待失败或超时，记录 session ID，调用 `session get-output` 获取结果；不要重复发送同一消息。
- `interactive` 只用于用户明确要求进入交互模式且当前环境支持 TTY 的场景。

### DeepWiki

1. 获取用户指定仓库；“当前仓库”先只读检查 Git remote，并规范化为 `org/repo`。存在多个可能目标时询问。
2. 明确告知 DeepWiki 分析远端仓库版本，不包含未推送的本地改动。
3. 先运行 `deepwiki status` 检查已有版本。只有用户明确要求生成、更新或分析且没有可用结果时，才运行 `deepwiki trigger`。
4. 触发后有限轮询 `status`。生成完成后用 `list-files` 和 `get` 读取相关内容；需要本地完整副本时才用 `download`。
5. “触发成功”只表示任务已创建。读取到生成产物后才能声称分析完成；超出合理等待时间则报告当前状态和仓库标识。

## 站点与错误

- 默认沿用 `BYTEDCLI_CLOUD_SITE` 或 CLI 的 `cn`。用户明确提到 TikTok ROW 等站点时传对应 `--site`。
- 空列表、找不到个人资源或认证域不匹配时，检查站点和 `--auth-site`，不要直接断言资源不存在。
- 写操作失败时区分“请求未提交”和“已提交但等待结果失败”，避免重复创建 session、消息或 DeepWiki 任务。

## 质量检查

- 命令来自当前 `--help`，未猜测参数。
- 只上传用户明确指定的文件。
- 最终回复说明实际调用结果，并保留 space、session 或 repo 等必要标识。
- 异步任务未完成时如实报告状态，不把受理成功描述成任务完成。
