---
name: cosh-info-summary-image
description: 为网站、活动、行情、项目、文章或事件生成 16:9 中文信息摘要图。用户提供 URL、主题、事件描述、行情主题，或要求收集资料、整理摘要、构建生图 prompt、优先用 Codex imagegen 生图、必要时用火山引擎 fallback 并上传 OSS 时使用。
---

# 信息摘要生图

## 核心原则

- 先保证事实，再追求美观；不要虚构数字、日期、名称、Logo、截图或结论。
- 默认中文、16:9、文档/报告插图风格。
- 默认高信息密度，但只使用短标题、短标签、数字、时间线和小模块，不写大段文字。
- 时效性主题、行情、近期事件或用户要求“最新”时，必须联网查证。
- Codex 环境优先用内置 `imagegen`；仅当不可用、失败或用户指定时，使用火山引擎脚本 fallback。
- 上传 OSS 不是生图的前置条件；用户只要图片时，可直接返回本地或生成结果。用户要求 OSS 地址时，再检查上传配置。

## 最小工作流

1. 判断输入类型：网站、事件、行情/主题、文章/文档。无法判断时先问一句。
2. 收集并压缩事实：
   - 网站/产品：定位、目标用户、功能结构、亮点、数据、场景、风险。
   - 事件：背景、时间、地点、参与方、经过、结果、影响、后续。
   - 行情/主题：定义、机制、生态、近期变化、数据状态、机会、风险。
   - 文章/文档：主题、核心论点、结构、关键事实、方法、结论。
3. 形成 6-12 个可视化信息点；资料不足时先说明缺口，不要硬画。
4. 选择视觉方向。用户未指定风格时，按主题自动选择；需要风格细节再读 `references/style-templates.md`。
5. 生成稳定 prompt，再调用生图工具。
6. 如需 OSS 地址，上传图片并返回摘要与地址。

## Prompt 要点

生图 prompt 必须包含：

- `Subject`：图片主题。
- `Chinese visible text`：可见文字使用中文。
- `Facts to show`：6-12 个事实点，压成短标签。
- `Layout`：指定 16:9、标题区、5-8 个信息模块，以及时间线/指标条/流程图/对比区中的一种或多种。
- `Style`：克制、清晰、适合文档报告；避免广告海报感。
- `Do not`：不虚构事实，不使用不可读小字，不造 Logo/截图/水印。

推荐结构：

```text
Create a clean 16:9 Chinese informational summary image for a document/report.
Subject: <主题>
Visible text language: Chinese.
Facts to show: <6-12 个短事实点>
Layout: title area + 5-8 compact modules + <timeline/metrics/flow/compare/risk area>
Style: <视觉风格>
Avoid: fake facts, fake logos, fake screenshots, tiny unreadable text, watermark, ad-poster style.
```

## 资源

- `references/style-templates.md`：只在需要选择或填充视觉风格时读取。
- `scripts/volcengine_generate_image.py`：内置 `imagegen` 不可用或用户指定外部 API 时使用。16:9 推荐 `VOLCENGINE_IMAGE_SIZE=2560x1440`。
- `scripts/upload_oss.py`：用户要求 OSS 地址时使用。需要 `OSS_BUCKET`、标准 `OSS_ENDPOINT`，以及 `ALIBABA_CLOUD_ACCESS_KEY_ID`/`ALIBABA_CLOUD_ACCESS_KEY_SECRET` 或兼容的 `OSS_ACCESS_KEY_ID`/`OSS_ACCESS_KEY_SECRET`。

## 输出

成功时：

```markdown
摘要：
<中文摘要>

图片路径：
<本地路径或 OSS 地址>
```

无法继续时：

```markdown
缺少信息：
- <缺失项>

原因：
<为什么需要它>

请补充：
<需要用户提供的内容>
```
