---
name: cosh-info-summary-image
description: 为网站或活动生成 16:9 中文信息摘要图。用户提供网站 URL、活动链接、活动描述，或要求收集信息、整理大纲、构建稳定生图 prompt、优先使用 Agent 生图工具生成图片、必要时回退到火山引擎 Seedream 生图并上传结果到阿里云 OSS 时使用。
---

# 信息摘要生图

## 目标

根据用户提供的网站或事件信息，收集事实、整理中文摘要大纲、生成稳定的生图 prompt，产出一张适合文档/报告插图的 16:9 信息摘要图，并上传到 OSS 后返回摘要与 OSS 对象路径。

## 默认策略

- 默认输出中文。
- 默认图片比例为 16:9。
- 默认图片用途为文档/报告插图，优先保证信息清晰和文字可读。
- 默认最终只返回摘要与图片路径；不要默认输出完整过程资产包。
- 优先使用 Agent 自带生图能力；除非用户指定，否则仅在 Agent 无可用生图能力时使用火山引擎 fallback。
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
2. 收集信息：网站类读取页面主题、定位、核心内容、品牌/视觉线索；事件类整理名称、背景、时间、地点、参与方、经过、结果和影响。
3. 校验必需信息和配置。缺少任意关键项就停止询问。
4. 生成中文摘要大纲。
5. 用稳定模板生成最终生图 prompt。
6. 优先调用 Agent 自带生图能力生成图片；没有可用能力时，使用 `scripts/volcengine_generate_image.py`。
7. 使用 `scripts/upload_oss.py` 上传图片到 OSS。
8. 返回中文摘要与 OSS 对象路径。

## 大纲格式

网站类：

```markdown
标题：<网站或页面名称>
主题：<一句话说明网站/页面核心内容>
核心要点：
- <要点 1>
- <要点 2>
- <要点 3>
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
影响或意义：<事件带来的结果、影响或关注点>
视觉方向：<适合表达该事件的画面方向>
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

Requirements:
- Use a clean, modern, restrained document/report illustration style.
- Use a landscape 16:9 composition.
- Show one clear title area and 3 to 5 concise information modules.
- Keep visible text minimal, large, and readable in Chinese.
- Prefer visual metaphors, interface-like panels, timeline elements, diagrams, or simple scene elements that support the summary.
- Do not invent facts, numbers, names, dates, logos, screenshots, UI details, or claims that are not provided.
- Avoid dense paragraphs, tiny unreadable text, watermarks, fake brand marks, misleading UI, and dramatic advertising-poster styling.
- The image should be suitable for embedding in technical documentation, reports, tutorials, or project notes.
```

## 脚本资源

- `scripts/volcengine_generate_image.py`：当 Agent 没有可用生图能力时，调用火山引擎兼容 OpenAI 风格的图片生成接口。运行前必须确认所需环境变量已配置；缺失时停止询问用户。`VOLCENGINE_IMAGE_SIZE` 不要填 `16:9` 这类比例字符串；Seedream 5 接受 `WIDTHxHEIGHT`、`2k`、`3k` 或 `4k`，16:9 推荐填 `2560x1440`。
- `scripts/upload_oss.py`：使用 Alibaba Cloud OSS Python SDK V2 上传本地图片并输出 OSS 对象路径。运行前必须确认 OSS 环境变量已配置；脚本只接受 `OSS_ENDPOINT`，并从标准 OSS endpoint 内部推导 SDK 所需 region；缺失必需项或 endpoint 无法推导 region 时停止询问用户。

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
<OSS 对象路径>
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
- 生图 prompt 使用稳定模板，默认 16:9，默认中文可见文字。
- 没有虚构事实、数字、人物、品牌、日期或截图。
- 若使用 fallback，已检查火山引擎所需 key 和模型配置。
- 上传前已检查 OSS key、bucket、endpoint 和对象路径，且 endpoint 可推导 SDK 所需 region。
- 最终只返回摘要与图片路径，除非用户要求更多过程信息。
