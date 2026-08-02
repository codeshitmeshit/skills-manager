# OpenSpec 实时进度网站

## 目标与边界

为一个项目中的多个 OpenSpec change 提供本地实时网站，展示当前进度，并提供范围受限的任务推进授权。OpenSpec artifacts 始终是唯一数据源；网站不维护平行状态。

除执行授权外，页面禁止：

- 勾选或修改 task；
- 修改规格、design、验证结果或最终归档门禁；
- 编辑 proposal、spec、design 或验证证据；
- 把状态写入浏览器存储、数据库或额外 JSON 文件；
- 用上一次成功结果掩盖当前读取错误。

允许的写操作只有：更新当前 tasks artifact 中的 `<!-- cosh-dashboard-control {...} -->` 注释，以及用户在单独推进模式点击“推进下一个任务”后提交目标 Git 工作区已经暂存的内容。不得自动暂存文件、创建空提交或写入其他状态文件。

## 任务推进控制

完整任务列表和控制区必须只放在顶部导航的 Tasks 产物页，不在 Change 总览重复展示。推进模式切换器放在 Tasks 页顶部；单独推进时，用“推进下一个任务”按钮替换当前 task 行右侧的“当前任务”文字，不增加卡片底部控制区。连续推进模式下必须从 DOM 移除该按钮并恢复状态文字，不得仅置灰。Tasks 页直接呈现 `tasks.md` 的结构化解析结果，不再重复显示原始文件阅读器。控制请求必须携带页面所见的当前 task，服务端校验它仍是第一个未完成 task，避免实时更新后误放行其他任务。

1. **连续推进**：用户在当前 task 下点击后，记录 `mode=continuous`。该点击是对当前及剩余 tasks 的明确批量授权；agent 每项仍执行测试、自检、独立 commit 和 task 状态更新，但无需逐项等待人工 CR。
2. **单独推进**：默认模式，记录 `mode=single`。agent 完成当前 task、验证并展示 CR 材料后暂停。
3. **推进下一个任务**：仅在单独推进模式使用。该点击表示 CR 通过和提交授权。服务端先重新校验 change、tasks 版本和当前 task；若 Git 暂存区非空，以 `openspec(<change>): <task>` 提交整个暂存区，提交失败则不记录放行。暂存区为空时不创建空提交。随后记录当前获批 task 和下一 task；agent 更新当前 task 后才进入下一 task。

### 自然语言等价控制

页面不是唯一控制入口，网站未打开或用户不操作页面时也能正常执行 OpenSpec 流程。自然语言控制必须与页面动作共用校验、Git 提交规则和 tasks artifact 中的 `cosh-dashboard-control` 元数据，不允许建立仅存在于对话上下文中的平行授权状态。

- 开始实现前的“继续”“开始实现”只授权当前一个 task。
- 已展示 CR 材料并明确等待 CR 时，“CR 没问题，推进下一个任务”“提交当前任务并继续”或上下文明确的“继续”，与 `advance-next` 相同：重新读取 OpenSpec、校验当前 task、只提交整个暂存区、不执行 `git add`、不创建空提交；commit 或 hook 失败时不记录授权。
- “连续推进剩余任务”与 `set-mode continuous` 相同；“切回单独推进”与 `set-mode single` 相同。两者都写入受控元数据，不触发 Git commit。
- 控制元数据写入后，已打开的页面通过 SSE 自动显示新模式、授权和 task 状态，不要求用户手动刷新。

控制接口必须：

- 只接受同源 `POST /api/control` 的固定动作 `set-mode` 与 `advance-next`；
- 要求页面提交当前 tasks 文件版本，版本变化时返回冲突并等待实时页面刷新，不覆盖新内容；
- 只替换受控注释，不修改 task checkbox 或正文；
- 将默认模式视为 `single`；
- 在没有待执行 task 时拒绝推进；
- 只有 `advance-next` 可以触发 Git commit，`set-mode` 不得提交；只提交已暂存内容，不执行 `git add`；
- Git commit 或 hook 失败时返回错误，并保持当前 task 未放行；
- 不把连续推进解释为允许跳过测试、失败处理、最终测试确认或归档确认。

## 启动

从 skill 目录运行：

```bash
python3 scripts/serve_openspec_dashboard.py \
  --project-root <目标仓库绝对路径> \
  --port 4173
```

- 服务扫描 `openspec/changes/` 下全部活动 change，并允许在页面切换；`--change <change-id>` 仅用于指定首次打开的默认 change。
- 默认监听 `127.0.0.1`。端口被占用时选择新的明确端口，不扫描端口范围。
- 必须使用命令输出的实际 URL，不根据默认端口猜地址。
- 服务应贯穿 OpenSpec 工作流；任务结束或用户要求停止时再终止。

## 数据读取

### 评审状态协议

评审状态直接写在当前 schema 允许的 OpenSpec artifact 中，页面只读投影，不建立额外状态文件。每路评审用 `cosh-review-state` JSON 注释记录 `reviewer`、`required_reviewers`、`status`、`stage`、`completed`、`total`、`summary` 和 `updated_at`；`reviewer` 支持 `stability`、`security` 和 `feasibility`，`required_reviewers` 声明当前流程必须完成的评审集合。每条未通过结论用 `cosh-review-finding` 记录 `id`、`reviewer`、`check`、`status=failed`、`severity`、`blocking`、`title`、`evidence`、`location`、`recommendation`、`closure` 和 `updated_at`。`location` 必须精确到文件、符号或变量，`recommendation` 必须是可执行修改方式。问题闭环后保留 finding 并把 `closure` 改为 `closed`。

页面识别的评审状态为 `not_started`、`running`、`blocked`、`passed`、`failed`；阶段或结论变化时立即更新 marker，使 SSE 在下一次监听周期推送，不得等整轮评审结束后补写。

字节三路评审使用 `cosh-ai-spec-evidence` 记录部门 AI-Spec 门禁。`status=loaded` 时，服务校验版本、七个必需来源角色、项目内相对路径、64 位 SHA-256 和三路 Reviewer 引用映射，并实时重新计算文件哈希。`status=fallback` 时，服务强制校验确实尝试过自动安装/更新/初始化、每次命令结果、最终失败原因及 ST/SEC/F 三套通用规则。两种状态都可进入评审，但 fallback 必须持续显示黄色降级提示；没有证据、静默跳过或证据不完整时返回 blocked。通用流程不声明三路 `required_reviewers` 时只兼容展示，不强制启用该门禁。

脚本递归读取 `openspec/changes/<change-id>/` 下的文本 artifacts，并从真实内容计算：

- artifact 是否存在及最后修改时间；
- Markdown task checkbox 的总数、完成数和条目；
- 修改点 ID、文件、符号、变量、类型和未决假设；
- proposal/spec/design/tasks/validation 的阶段就绪度；
- 当前门禁和下一步；
- 最近更新的 artifact。
- 每个 artifact 所属标签（规格、Design、Tasks、验证、代码证据）及其关联修改点。
- 各路评审的当前检查项、完成度、状态和更新时间，缺失的必需 Reviewer，以及每条未闭环 finding 的证据、修改位置和修改建议。
- AI-Spec 版本、知识门禁状态、已校验知识源数量、缺失角色和失效文件。

## 多 Change 切换

- 页面顶部提供 Change 切换器，列出 change 名称、阶段和 task 进度；选择结果写入 URL 的 `change` 参数，不写浏览器存储。
- `GET /api/changes` 返回活动 change 目录；页面定期刷新目录，使新增或移除的 change 无需重启服务即可反映。归档目录和隐藏目录不得出现在列表中。
- `/api/status`、`/events` 和 `/api/document` 使用 `change` 查询参数；`POST /api/control` 在请求体携带 `change`。
- 切换 change 时清除旧的 `point` 与 `artifact` 参数，并为新 change 建立独立 SSE 连接。
- 服务端必须对每个请求重新执行 change 目录边界校验。任务推进只能修改请求所指 change 的 tasks artifact，不得依赖上一次页面状态推断目标。

## 多修改点与文件标签页

- 总览页列出全部修改点，每个修改点链接到独立 URL：`?point=<修改点 ID>`。
- 修改点详情页只展示该修改点的文件、符号、变量、目标变化及相关 documents。
- 详情页提供“规格、Design、Tasks、验证、代码证据”标签；标签内列出对应 artifact 文件。
- 文件内容只在用户打开对应标签或文件时，通过只读 `/api/document?path=...` 按需获取。
- proposal/spec 在无法细分时可作为所有修改点的共同规格；design、tasks、验证和代码证据必须包含修改点 ID 或对应 scenario 才能关联。
- URL 中的修改点不存在时显示明确错误，不回退到第一个修改点。
- artifact 路径必须限制在当前 change 目录内，拒绝路径穿越。

页面不得把文件存在等同于人工确认。只有当前 OpenSpec schema 明确记录了确认事实时才显示“已确认”；否则显示“已产出，待确认”。

若项目 OpenSpec schema 与默认文件识别不同，优先读取项目实际 schema 并扩展脚本的只读映射；不得改动项目 artifacts 来迎合页面解析。

## 实时刷新

- 浏览器通过 `/events` 建立 Server-Sent Events 长连接；连接建立后立即接收完整状态。
- 服务端每 0.5 秒检查 OpenSpec 内容，只在状态变化时推送新快照；不写磁盘缓存。
- 监听覆盖文件新增、删除、正文变化、task checkbox、修改点、执行控制和验证证据；不能只监听 tasks 数量。
- 连接断开时页面显示“正在重连”，并使用浏览器原生 EventSource 自动重连；恢复后立即更新。
- `/api/status` 保留为一次性诊断接口，不作为正常实时更新路径。
- 页面显示最后成功读取时间和数据源最近修改时间。
- 读取失败时立即显示错误横幅，并保留错误发生时间；不得继续显示“实时”绿灯。

## 页面信息架构

首屏优先展示当前决策，而不是通用管理后台：

1. change 名称、当前阶段、实时连接状态、最后更新时间；
2. 贯穿总览与详情页的产物导航栏，按“总览、Proposal、规格、修改点、Design、评审、验证”展示当前已有产物，并把 Tasks 固定在最右侧作为高亮的开发主入口；
3. 总体 task 进度和下一人工门禁；
4. 七个门禁的状态轨迹；
5. 当前修改点的文件、符号、变量、类型和变化；
6. design 与修改点映射；
7. 总览仅显示 task 总体进度；完整 tasks 和推进控制放在 Tasks 产物页，验证证据、风险和未决假设放在对应产物页。

评审开始后，总览必须出现各路评审的实时进度卡片，并在原代码修改点卡片所在区域展示“风险点”；风险点只来自尚未闭环的评审 finding，显示严重级别、阻断状态、风险位置和处理建议，不得把代码修改点改名后冒充风险点。代码修改点继续通过导航和独立详情页查看。评审产物页展示完整评审中心，并额外展示 finding 证据。必需 Reviewer 未启动时显示等待状态，不得把部分 Reviewer 通过显示为整体通过；finding 闭环后从“风险点”列表移除，但仍保留在 OpenSpec 原文供追溯。

导航项只在对应产物存在时出现。点击产物后进入统一只读阅读页；同类有多个文件时必须列出文件路径，不得只展示第一个。产物正文继续通过 `/api/document` 从当前 change 读取，并随 SSE 快照中的版本变化实时更新。

Tasks 导航必须使用独立的高识别度颜色，在未选中和选中状态下都与普通产物区分；桌面宽度下使用自动间距贴齐导航栏最右侧，窄屏仍保持最后一项并可横向滚动访问。

使用清晰文字、颜色和布局；状态不能只依赖颜色。页面需适配桌面和窄屏，并提供可读的空状态与错误状态。

## 验证

启动后至少验证：

1. `/api/status` 返回目标 change，且 `source` 指向目标 `openspec/changes/...`。
2. 页面能加载，且除了受限 `/api/control` 外不存在写状态的 API 或表单编辑能力；`advance-next` 只提交暂存区，`set-mode` 不触发提交。
3. 修改一个测试 fixture 中的 task checkbox 后，`/events` 推送的新快照反映新进度，无需刷新页面。
4. 删除或破坏 change 后，API 与页面显示读取错误而非旧成功状态。
5. 服务只绑定预期地址，没有将内部需求内容意外暴露到公网。
6. 多个修改点分别有独立 URL，详情页标签只显示与当前修改点关联的 artifacts。
7. `/api/document` 只读返回 change 内文件，并拒绝 `../` 等越界路径。
8. 切换模式只更新 tasks 内控制注释，不改变 checkbox；陈旧版本请求返回冲突。
9. 单独推进的“推进下一个任务”记录当前获批 task；连续推进时该按钮不渲染。
10. 在 SSE 已连接且不重连的前提下修改 task checkbox，下一事件必须反映新进度。
11. 在 task 进度不变时修改 design 正文，下一事件必须带有新的 document version。
12. 导航栏覆盖当前已有的所有产物类型；点击任一产物可读取正文，同类多个文件均可选择。
13. 同一项目存在多个 change 时，切换后状态、SSE、文件读取和任务控制均只作用于所选 change。
14. 在临时 Git 仓库暂存文件后点击“推进下一个任务”，生成一次包含该暂存快照的 commit；暂存区为空时不生成空 commit，提交失败时不记录放行。
15. 更新任一路 `cosh-review-state` 的 stage 或 completed 后，现有 SSE 连接收到新状态；新增、修改或闭环 `cosh-review-finding` 后，页面同步更新未通过数量、阻断数量、证据、修改位置和修改建议。
16. 字节三路评审缺少 `cosh-ai-spec-evidence`、任一必需角色、Reviewer 引用或文件哈希不一致时，API 和页面显示 AI-Spec 知识门禁未通过；合法 fallback 显示“通用规则降级”并允许继续，修复为 loaded 后由同一 SSE 连接实时恢复。
