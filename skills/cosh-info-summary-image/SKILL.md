---
name: cosh-info-summary-image
description: 为网站、活动、行情或事件生成 16:9 中文信息摘要图。用户提供网站 URL、活动链接、行情主题、事件描述，或要求收集信息、整理大纲、自动选择美观风格、构建稳定生图 prompt、在 Codex 中优先使用 imagegen 生图、必要时回退到火山引擎 Seedream 生图并上传结果到阿里云 OSS 时使用。
---

# 信息摘要生图

## 目标

根据用户提供的网站、事件或行情主题，尽量收集可核验事实，整理中文高信息密度摘要大纲，生成稳定的生图 prompt，产出一张适合文档/报告插图的 16:9 信息摘要图，并上传到 OSS 后返回摘要与完整 OSS 地址。

## 默认策略

- 默认输出中文。
- 默认图片比例为 16:9。
- 默认图片用途为文档/报告插图，优先生成紧凑、高信息密度的报告页式信息图，同时保证标题、模块标签和关键短语可读。
- 默认尽量多收集信息：只要用户没有明确要求“简洁版”，就不要满足于 3 个要点；应优先覆盖背景、主体、机制、时间线、数据/状态、影响、风险/限制、下一步或关注点。
- 默认使用美观但克制的信息图风格；用户可指定视觉风格，未指定时根据主题自动选择。
- 默认最终只返回摘要与图片路径；不要默认输出完整过程资产包。
- 在 Codex 中执行时，优先使用 `imagegen` skill 的内置 `image_gen` 生图能力；除非用户指定或内置能力不可用，否则不要优先依赖外部生图 API。
- 非 Codex 环境或内置生图不可用时，才使用火山引擎 fallback。
- 任一关键内容、生成配置或上传配置缺失时，停止并询问用户，不做低置信度降级生成。

## 必需信息

网站类输入至少需要：

- 可访问的网站 URL，或用户提供的足够页面内容。
- 网站/页面主题。
- 至少 3 个可用于摘要的关键信息点。

事件类输入至少需要：

- 事件名称或明确事件主题。
- 至少 3 个核心事实，例如时间、地点、参与方、事件经过、结果、影响。
- 可判断的信息来源，来自链接或用户提供内容。

行情/主题类输入至少需要：

- 明确主题，例如 `ETH`、某个产品、行业、项目、公司或技术概念。
- 至少 3 个可核验信息点；如果用户只给出短主题，必须主动检索公开资料补足。
- 对时效敏感的主题必须检索最新资料，并在摘要中区分稳定事实、近期变化和市场/舆论观察。

生成与上传至少需要：

- Agent 生图能力可用，或火山引擎生图所需 key、模型、调用配置完整。
- OSS 上传所需 access key、bucket、endpoint、object path 或 path prefix 完整。当前脚本接受 `ALIBABA_CLOUD_ACCESS_KEY_ID`/`ALIBABA_CLOUD_ACCESS_KEY_SECRET`，也兼容 `OSS_ACCESS_KEY_ID`/`OSS_ACCESS_KEY_SECRET`；只接受 `OSS_ENDPOINT`，并从标准 OSS endpoint 内部推导 SDK 所需 region；加速 endpoint、自定义域名或 CDN 域名无法稳定推导 region，因此不可作为上传配置。

缺失时按以下格式停止：

```markdown
缺少信息：
- <缺失项>

原因：
<为什么这是继续生成或上传的必要条件>

请补充：
<用户需要提供的内容>
```

## 工作流

1. 判断输入类型：网站、事件，或无法判断。无法判断时先询问。
2. 收集信息：
   - 网站类读取页面主题、定位、核心内容、产品/功能结构、目标用户、品牌/视觉线索、重要数据或案例。
   - 事件类整理名称、背景、时间、地点、参与方、经过、结果、影响、争议点、后续进展。
   - 行情/主题类整理定义、背景、关键机制、生态/参与方、时间线、近期变化、数据/状态、机会、风险和不确定性。
   - 只要主题具有时效性或用户要求“最新/行情/今天/近期”，必须联网检索并优先使用官方来源、权威文档、主流新闻或可核验数据源。
   - 信息量目标：常规图至少整理 6-10 个事实点；高信息密度图整理 10-16 个事实点，再压缩成短标签和短句进入 prompt。
3. 校验必需信息和配置。缺少任意关键项就停止询问。
4. 生成中文摘要大纲。
5. 选择视觉风格：读取 `references/style-templates.md`。用户指定时遵循指定风格；未指定时根据摘要事实和主题自动选择最适合的一种，并写入 prompt。
6. 生成海报结构蓝图：先把摘要组织成标题、短副标题、布局模式、分区、卡片类型、色彩节奏，再填入稳定 prompt；不要直接把长摘要塞给生图模型。
7. 用稳定模板生成最终生图 prompt。
8. 在 Codex 中优先调用 `imagegen` skill 的内置 `image_gen` 工具生成图片。
   - 使用 `imagegen` 时，将输出作为项目/上传用资产处理：生成后找到图片文件，复制或移动到 `/tmp` 或工作区中的明确路径，再上传 OSS。
   - 如果内置 `image_gen` 不可用、执行失败，或当前环境不是 Codex，再使用 `scripts/volcengine_generate_image.py`。
9. 使用 `scripts/upload_oss.py` 上传图片到 OSS。
10. 返回中文摘要与完整 OSS 地址。

## 大纲格式

网站类：

```markdown
标题：<网站或页面名称>
主题：<一句话说明网站/页面核心内容>
核心要点：
- <要点 1>
- <要点 2>
- <要点 3>
补充信息：
- <机制、功能、数据、时间线、场景或风险等补充点，尽量 3-8 条>
视觉方向：<适合表达该网站主题的画面方向>
避免内容：<不能虚构或不应出现的内容>
```

事件类：

```markdown
标题：<事件名称>
事件摘要：<一句话说明事件核心>
核心事实：
- <事实 1>
- <事实 2>
- <事实 3>
补充信息：
- <背景、经过、结果、影响、争议、后续或风险等补充点，尽量 3-8 条>
影响或意义：<事件带来的结果、影响或关注点>
视觉方向：<适合表达该事件的画面方向>
避免内容：<不能虚构或不应出现的内容>
```

行情/主题类：

```markdown
标题：<主题名称>
主题摘要：<一句话说明主题核心>
核心事实：
- <事实 1>
- <事实 2>
- <事实 3>
信息模块：
- <模块 1：定义/背景>
- <模块 2：机制/结构>
- <模块 3：生态/参与方>
- <模块 4：近期变化/时间线>
- <模块 5：数据/市场/状态>
- <模块 6：风险/限制/关注点>
视觉方向：<适合表达该主题的紧凑信息图方向>
避免内容：<不能虚构或不应出现的内容>
```

## 稳定 Prompt 模板

用大纲填充下面模板，不要临时改写结构。保留英文 prompt，以提升跨模型稳定性；摘要和可见内容要求中文。

```text
Create a clean 16:9 informational summary illustration for a document or report.

Language:
Chinese for any visible headline or labels.

Subject:
{title}

Summary:
{summary}

Key points to represent:
{key_points}

Visual direction:
{visual_direction}

Style:
{style_preset}

Poster structure:
{poster_structure}

Requirements:
- Use a clean, modern, restrained document/report illustration style.
- Use a landscape 16:9 composition.
- Use a compact, high-information-density layout by default.
- Show one clear title area and 5 to 8 concise information modules when enough facts are available; use 3 to 5 modules only for sparse or explicitly simple inputs.
- Include a small timeline, metric/status strip, flow diagram, comparison row, or risk/watchlist area when supported by facts.
- Keep visible text concise, large enough to read, and in Chinese; use short labels, numbers, dates, and 4-10 character phrases instead of paragraphs.
- Prefer dense but orderly visual metaphors, interface-like panels, timeline elements, diagrams, comparison grids, flow arrows, or simple scene elements that support the summary.
- Do not invent facts, numbers, names, dates, logos, screenshots, UI details, or claims that are not provided.
- Avoid dense paragraphs, tiny unreadable text, watermarks, fake brand marks, misleading UI, and dramatic advertising-poster styling.
- The image should be suitable for embedding in technical documentation, reports, tutorials, or project notes.
```

## 海报结构蓝图

参考 `article-poster` 的结构化海报思路：先生成内容结构，再生成图像。这里不要求渲染 HTML，但必须在 prompt 前整理出结构蓝图，用它约束生图模型的版式。

结构蓝图字段：

```markdown
来源：<来源或主题类别，尽量短>
分类：<报告/行情/技术/事件/产品等>
标题：<主标题，中文建议 8-18 字>
副标题：<一句话摘要，中文建议 20-45 字>
布局：<single | double | dashboard>
分区：
- 编号：1
  色彩：<brown | olive | terracotta | teal | amber | sage | slate | rose>
  标题：<分区标题，中文建议 4-12 字>
  卡片：
  - 类型：<text | highlight | tags | compare | bullets | callout | metric | timeline | flow>
    内容：<短句、标签、对比项、指标或节点>
```

结构规则：

- `single` 适合叙事型、事件型、线性主题；`double` 适合对比、方法论、章节多的文章；`dashboard` 适合行情、数据、技术生态、项目概览。
- 分区数量通常 4-8 个；复杂主题最多 10 个，但一张 16:9 图里必须合并成 5-8 个视觉模块。
- 色彩从 `brown`、`olive`、`terracotta`、`teal`、`amber`、`sage`、`slate`、`rose` 中选择 3-5 个交替使用，形成温和但有层次的卡片色彩，不要单色到底。
- 卡片类型按内容选择：定义用 `text`，关键结论用 `highlight`，角色/阶段/要素用 `tags`，差异用 `compare`，方法清单用 `bullets`，核心洞察用 `callout`，数字状态用 `metric`，版本/事件用 `timeline`，系统关系用 `flow`。
- 中文内容使用全角标点；卡片标题尽量少于 12 个汉字，正文每卡 1-3 个短句，不写长段落。
- 结构蓝图是给模型的版式约束，不需要在最终答复中输出，除非用户要求过程资产。

## 信息密度规则

- 用户没有明确说“简单、少字、极简”时，默认按高信息密度处理。
- 高信息密度不是堆长段落：可见文字应拆成模块标题、短标签、短句、年份、数字、状态词和风险提示。
- 优先用 5-8 个模块承载信息；每个模块 1 个标题加 1-3 个短标签。
- 对复杂主题，prompt 中可以包含 10-16 个事实点，但画面可见文字只保留最关键的 8-14 个短标签。
- 必须显式要求排版紧凑：使用网格、侧栏、底部时间线、顶部状态条、迷你图表、小型流程图等结构提高信息承载量。
- 生成 prompt 前必须先决定卡片类型组合，例如 `metric + timeline + tags + compare + callout`，让画面像由真实设计模板排出来，而不是散乱插画。
- 不要为了信息密度牺牲事实准确性；无法确认的内容只能作为“关注点/风险/待确认”，不能作为确定事实。

## 视觉风格模板

视觉风格模板保存在 `references/style-templates.md`。只有在需要选择或填充风格时读取该文件。

用户可以用自然语言指定风格，例如“金融终端风”“科技蓝图风”“极简白底风”。如果用户没有指定，必须根据已获取的事实和主题自动选择一种，不要额外询问。风格只能改变构图、色彩、材质、图表隐喻和视觉层级，不能改变事实。

## 脚本资源

- `references/style-templates.md`：按需读取的视觉风格模板和自动选择规则。
- `scripts/volcengine_generate_image.py`：仅当 Codex 内置 `imagegen` 不可用、当前环境不是 Codex，或用户明确指定外部 API 时，调用火山引擎兼容 OpenAI 风格的图片生成接口。运行前必须确认所需环境变量已配置；缺失时停止询问用户。`VOLCENGINE_IMAGE_SIZE` 不要填 `16:9` 这类比例字符串；Seedream 5 接受 `WIDTHxHEIGHT`、`2k`、`3k` 或 `4k`，16:9 推荐填 `2560x1440`。
- `scripts/upload_oss.py`：使用 Alibaba Cloud OSS Python SDK V2 上传本地图片并输出完整 OSS 地址，格式为 `https://<bucket>.<endpoint>/<object-key>`。运行前必须确认 OSS 环境变量已配置；脚本只接受 `OSS_ENDPOINT`，并从标准 OSS endpoint 内部推导 SDK 所需 region；缺失必需项或 endpoint 无法推导 region 时停止询问用户。

## 配置指引

火山引擎 fallback：

- 必填：`VOLCENGINE_API_KEY`
- 必填：`VOLCENGINE_IMAGE_MODEL`
- 可选：`VOLCENGINE_BASE_URL`，默认 `https://ark.cn-beijing.volces.com/api/v3/`
- 可选：`VOLCENGINE_IMAGE_SIZE`，默认建议 `2560x1440`；不要使用 `16:9`，该值会被 Seedream 5 拒绝。
- 可选：`VOLCENGINE_TIMEOUT`，默认 `180`

OSS 上传：

- 必填：`ALIBABA_CLOUD_ACCESS_KEY_ID` 和 `ALIBABA_CLOUD_ACCESS_KEY_SECRET`，或 `OSS_ACCESS_KEY_ID` 和 `OSS_ACCESS_KEY_SECRET`
- 必填：`OSS_BUCKET`
- 必填：`OSS_ENDPOINT`，必须是标准 OSS endpoint，例如 `oss-cn-guangzhou.aliyuncs.com`
- 可选：`OSS_PREFIX`，未传 `--key` 时作为对象路径前缀，默认 `generated-images`

## 输出格式

成功时：

```markdown
摘要：
<中文摘要>

图片路径：
<完整 OSS 地址>
```

失败或停止时：

```markdown
摘要：
<如果已经可靠生成摘要，则输出；否则写“未生成”>

图片路径：
未生成或未上传。

原因：
<失败或停止原因>

需要补充：
<用户需要补充的内容>
```

## 质量检查

- 输入类型已判断清楚。
- 摘要和大纲只包含来源中能支撑的信息。
- 对短主题、行情、近期事件或高时效主题，已尽量检索并整理足够事实；若资料不足，已说明不足而不是低信息生成。
- 默认采用高信息密度排版，除非用户明确要求简洁版。
- 已生成海报结构蓝图，并用布局模式、分区、卡片类型和色彩节奏约束最终 prompt。
- 视觉风格来自用户指定或 `references/style-templates.md` 自动选择结果。
- 生图 prompt 使用稳定模板，默认 16:9，默认中文可见文字。
- 在 Codex 中已优先尝试 `imagegen` 内置生图能力；只有不可用或用户指定时才使用外部 API。
- 没有虚构事实、数字、人物、品牌、日期或截图。
- 若使用 fallback，已检查火山引擎所需 key 和模型配置。
- 上传前已检查 OSS key、bucket、endpoint 和对象路径，且 endpoint 可推导 SDK 所需 region。
- 最终只返回摘要与图片路径，除非用户要求更多过程信息。
