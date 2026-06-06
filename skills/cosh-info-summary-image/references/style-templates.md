# 视觉风格模板

## 选择规则

用户指定风格时，优先使用用户指定的风格或最接近的模板。用户未指定时，根据已收集信息自动选择一种，不额外询问：

- 行情、交易、价格、市场分析：`finance-dashboard`
- 正式报告、会议总结、项目说明、政策解读：`clean-report`
- 技术架构、开发流程、开源项目、工程事件：`tech-blueprint`
- 活动、新闻、人物、趋势解读、品牌故事：`editorial-magazine`
- 事件经过、版本发布、路线图、里程碑：`timeline-briefing`
- 指标密集、数字摘要、对比结论：`data-cards`
- 文章、博客、长文本摘要、方法论拆解、需要章节化讲解：`article-poster-cards`
- 短主题但信息维度很多、需要紧凑多模块说明：`dense-card-poster`

如果一个主题同时命中多个模板，选择最能提升阅读效率的模板，而不是最炫目的模板。

## 模板

### finance-dashboard

Use a premium dark financial dashboard style. Deep charcoal background, subtle grid, restrained amber and cyan accents, large readable BTC/market headline area, clean metric cards, simplified candlestick or trend line motif, no real exchange UI, no fake logos, no dense trading screen details.

### clean-report

Use a polished light report infographic style. White or very light gray background, clear typography hierarchy, thin dividers, muted blue and green accents, spacious layout, 3 to 5 modular cards, document/report feel, minimal decoration, strong readability.

### tech-blueprint

Use a modern technical blueprint style. Deep navy background, fine blueprint lines, node-and-flow diagrams, soft cyan highlights, clean technical labels, structured panels, precise but not cluttered, suitable for engineering documentation.

### editorial-magazine

Use a refined editorial magazine style. Strong headline composition, elegant grid, restrained illustration or photo-like editorial atmosphere, tasteful contrast, minimal captions, premium publication feel, no sensational poster effects.

### timeline-briefing

Use a timeline briefing style. Horizontal 16:9 timeline, clear milestone nodes, compact cards, directional flow, limited color palette, readable event sequence, no crowded paragraphs.

### data-cards

Use a data-card infographic style. Three to five large metric cards, prominent numbers, compact labels, small supporting icons or mini charts, strong alignment, high contrast, easy scanning, no tiny footnotes or dense tables.

### article-poster-cards

Use a structured article-poster card layout. Clean off-white or soft warm background, strong editorial title block, concise subtitle, numbered sections, modular cards, gentle accent colors selected from brown, olive, terracotta, teal, amber, sage, slate, and rose. Use card types visually: text cards, highlight cards with left accent border, tag-list cards, compare cards, bullet cards, and callout cards. Prefer single or double column composition depending on content. The design should feel like a polished rendered poster template, not a loose illustration.

### dense-card-poster

Use a compact high-density card poster layout. 16:9 dashboard-like canvas, clear title and subtitle, 5 to 8 tightly aligned modules, mixed card types such as metrics, tags, timeline, flow, compare, and callout. Use multiple muted accent colors from brown, olive, terracotta, teal, amber, sage, slate, and rose to separate sections. Keep card radii small, spacing disciplined, text short and readable, and visual hierarchy obvious. Avoid a single-color dashboard and avoid decorative clutter.

## 通用约束

- 风格只能改变构图、色彩、材质、图表隐喻和视觉层级，不能改变事实。
- 保持中文可见文字短而清晰，优先标题、短标签、关键数字、年份、状态词和 1-3 个短句。
- 不使用难以阅读的装饰字体，不使用密集小字。
- 不生成未经提供的真实 logo、截图、交易所界面、品牌标识或无法验证的图表细节。
- 一张图只选一种主风格，可加入少量辅助元素，不要混搭过多。
- 卡片化风格必须看起来像有固定模板约束：统一对齐、清楚分区、有限色彩、稳定间距、明确标题层级。
