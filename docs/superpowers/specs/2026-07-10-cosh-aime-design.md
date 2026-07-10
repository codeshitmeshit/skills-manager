# cosh-aime Skill 设计

## 目标

当用户明确说“让 AIME”“问 AIME”“用 AIME”或要求 AIME DeepWiki 处理任务时，稳定调用 `bytedcli aime`，而不是只解释操作步骤。

## 范围

- 查询 AIME space 与 session。
- 创建或继续 session，发送文本和本地附件，并取回最终回复。
- 启动交互会话。
- 触发、查询和读取 DeepWiki。
- 支持 `bytedcli` 已公开的站点选项。

不封装 CLI，不维护一份容易过期的完整参数表；命令不确定时以当前 `--help` 为准。

## 行为设计

只读请求直接执行。用户明确要求创建会话、发送内容、上传指定附件或生成 DeepWiki 时，视为已授权对应操作；目标文件、空间、站点或仓库存在实质歧义时才询问。结构化调用使用 `bytedcli --json aime ...`。

附件任务优先用 `session send --upload-file ... --wait` 一步完成。等待失败但消息已提交时，用 `session get-output` 恢复，不重复发送。DeepWiki 只分析远端仓库版本；先识别 remote，查看已有状态，再按需触发，并在读取产物后才宣称分析完成。

## 错误处理与验证

认证失败时依据 CLI 的 `error.hint` 和 `error.auth_command` 处理。跨站点结果异常时检查 `--site`，列表请求处理分页。验证覆盖空间查询、附件会话和 DeepWiki 三类心智用例，并运行仓库 skill 校验。
