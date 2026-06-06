# 视觉风格模板

## 选择规则

用户指定风格时，优先使用用户指定的风格或最接近的模板。用户未指定时，根据已收集信息自动选择一种，不额外询问：

- 行情、交易、价格、市场分析：`finance-dashboard`
- 正式报告、会议总结、项目说明、政策解读：`clean-report`
- 技术架构、开发流程、开源项目、工程事件：`tech-blueprint`
- 活动、新闻、人物、趋势解读、品牌故事：`editorial-magazine`
- 事件经过、版本发布、路线图、里程碑：`timeline-briefing`
- 指标密集、数字摘要、对比结论：`data-cards`

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

## 通用约束

- 风格只能改变构图、色彩、材质、图表隐喻和视觉层级，不能改变事实。
- 保持中文可见文字少而大，优先标题、短标签和关键数字。
- 不使用难以阅读的装饰字体，不使用密集小字。
- 不生成未经提供的真实 logo、截图、交易所界面、品牌标识或无法验证的图表细节。
- 一张图只选一种主风格，可加入少量辅助元素，不要混搭过多。
