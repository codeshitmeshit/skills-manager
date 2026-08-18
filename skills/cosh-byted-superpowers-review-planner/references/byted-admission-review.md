# 字节技术方案准入评审

## 知识门禁

AI-Spec 是部门强制知识库。评审前检查 Node.js 与 `ai_spec --version`；CLI 缺失时执行 `npm install -g @lark/ai_spec@latest --registry=https://bnpm.byted.org`，随后按仓库状态执行 `ai_spec init .` 或 `ai_spec update .`。

loaded 模式记录版本、七个必需来源角色、实际文件路径、SHA-256、读取时间和 Reviewer 映射。任一来源缺失、为空、越界或哈希变化时更新并重新读取。

自动接入、安装、更新或读取失败时直接阻塞，并记录执行命令、退出状态、脱敏错误和最终原因。禁止用通用规则、历史缓存或其他知识源替代 AI-Spec；只有当前版本的完整 loaded 证据能够通过知识门禁。

## CodeGraph 事实包

在启动 Reviewer 前读取当前 commit，形成包含文件、符号、变量、接口、调用链、当前行为、上下游、可复用基建和代码 SHA 的只读事实包。CodeGraph 结果必须由源码复核；索引与源码不一致时以源码为准。

## 三个独立 Reviewer

三个独立 Subagent 读取同一技术文档版本、知识快照和事实包：

- 稳定性：基线、依赖与重试、容量、缓存、一致性、异步、发布回滚、监控和业务稳定性；
- 安全性：身份、授权、敏感数据、输入、日志、凭证、数据扩散和安全降级；
- 可行性：方案闭环、代码事实、基建复用、兼容性、依赖所有权、远程测试、发布回滚和任务可拆分性。

每路输出当前阶段、通过状态、风险点、严重级别、证据、影响和建议修改。证据不足的问题标记待确认，不能伪装成阻塞结论。不得让一个 Reviewer 代替另一个。

每个 `findings[]` 必须输出统一字段：`id`、`severity`、`blocking`、`title`、`evidence`、`recommendation` 和 `status`。`evidence` 使用非空字符串或每个元素均为非空字符串的数组，必须指向实际代码、技术文档章节、运行数据或知识规则；混合对象、空白元素和全非法数组都是格式错误并阻塞评审门禁。`status` 只能是未闭合的 `open`、`pending`、`pending_confirmation`，或已闭合的 `resolved`、`closed`；`blocking: true` 且未闭合时必须阻塞 Reviewer，即使 Reviewer 顶层状态误报为通过。`assessment`、`rules`、`section` 只能作为补充，不能代替证据。历史产物中的 `problem` 和 `suggestion` 分别兼容映射为 `title` 和 `recommendation`，但任一必填字段缺失时观察板必须显示格式错误并阻塞评审门禁。

未闭合 P0 永远按有效阻塞处理，即使 Reviewer 原始 `blocking` 误写为 `false`，也不能人工豁免。未闭合且原始 `blocking: true` 的 P1、P2、P3 可由用户在观察板选择“设为不阻塞”，但必须填写非空原因；该操作只写入 `control.json` 的独立审计记录，不得修改 Reviewer 原始证据。豁免必须绑定技术文档版本与 SHA、评审轮次、Reviewer 和 finding ID；任一绑定变化即自动失效。用户可随时恢复阻塞。格式错误、过期代码 SHA、缺失 Reviewer 和 P0 不受豁免影响，继续 fail closed。

## 修改与复评

任一路存在阻塞时展示风险点、证据和建议修改。用户选择技术文档修改后，只修改明确关联章节，生成新版本，并与最近一次全量评审通过的冻结文档比较。冻结文件保存到当前 work 的 `sources/`，文件内容与记录的 SHA-256 必须一致；不能拿可变的当前文档或任意历史版本冒充冻结基线。

把判断写入 `evidence/revision-assessment.json`，至少包含 `frozen_version`、`frozen_sha256`、`frozen_path`、`current_version`、`current_sha256`、`decision`、`semantic_changes`、`changed_sections`、`rationale` 和 `updated_at`。`semantic_changes` 必须逐项给出布尔值：`goals`、`scope`、`api_contracts`、`data_model`、`runtime_behavior`、`dependency_topology`、`security_boundary`、`stability_strategy`、`rollout_rollback`、`acceptance_criteria`。

只有以下条件同时成立时才能写 `decision: carry-forward`：修改仅为解释、例子、格式、错别字或对既有代码事实的澄清；上述十个语义维度全部为 `false`；冻结与当前版本、路径、哈希均可验证；`changed_sections` 和 `rationale` 非空。例如，把已经由 `UpdaterGateway` 注入的旧库 Repo 补写进文档，且不改变真实依赖链、运行行为和验收标准，可继承旧结论。

只要任一语义维度变化，或无法证明变更与既有代码事实一致，就写 `decision: full-review`。此时新版本重新进入知识门禁、CodeGraph 和三路完整评审，不能只复审未通过 Reviewer。缺失或伪造判断证据必须 fail closed。继承只改变门禁投影，不修改旧 Reviewer、知识、CodeGraph 或闭环原始证据；非 P0 豁免仍绑定当前文档版本，不能跨修订自动继承。
