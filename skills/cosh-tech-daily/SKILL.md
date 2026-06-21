---
name: cosh-tech-daily
description: 生成 AI 与开发者技术日报的中文 Markdown 简报。用户要求技术日报、AI 日报、开发者日报、每日技术简报、收集 Product Hunt/GitHub Trending/AI 新闻并整理成可分发内容，或明确调用 cosh-tech-daily 时使用；优先运行内置 prefetch 脚本收集可自动化来源，再补充实时搜索、筛选、去重和点评。
---

# Cosh Tech Daily

## 目标

生成一份适合社群、飞书、Notion、公众号草稿或聊天群分发的中文 AI/开发者技术日报。参考 Pulse 的思路：先用脚本并行预抓取稳定来源，再由 Codex 做事实核验、重要性判断、去重、中文点评和 Markdown 组装。

## 工作流

1. 判断日期、时区和场景。默认使用用户当前日期；如果用户指定“早报、晚报、昨天、某日期”，标题中明确写出实际日期。
2. 读取默认参数 `config.json`。用户自然语言里的临时要求优先级高于配置文件，例如“今天只看 GitHub，不要 Product Hunt”“短版”“国内优先”。
3. 按最终参数决定栏目开关、条目数量、信息源偏好和输出风格。
4. 优先运行预抓取脚本：

   ```bash
   python3 skills/cosh-tech-daily/scripts/prefetch.py
   ```

   如果当前工作目录不是 skills-manager 仓库，先定位本 skill 目录，再运行 `scripts/prefetch.py`。

5. 阅读脚本输出 JSON。可用字段包括：
   - `config`：脚本读取到的默认参数。
   - `product_hunt`：Product Hunt 今日产品线索。
   - `github_trending`：GitHub Trending 开发者项目线索。
   - `news`：AI、开发者工具、开源、模型、云服务、技术商业新闻 RSS 线索。
   - `search_cosh`：来自 `search.cosh.fun` 的关键词搜索结果，用于提高新闻发现准确度和交叉验证置信度。
   - `search_queries`：建议补充搜索的查询词。
   - `errors`：各来源失败原因。
6. 对失败来源或高风险事实进行补充搜索。涉及“今天、最新、刚发布、涨跌、融资、政策、版本发布”等易变化信息时必须联网核验。
7. 严格筛选，只保留对 AI/开发者读者有明确价值的条目。宁可少，不要凑数。
8. 去重并合并同一事件。若一个新闻同时出现在产品、GitHub、新闻中，只保留在最合适的栏目。
9. 用中文输出 Markdown。除非用户另有要求，最终回答必须直接从日报标题开始，不要添加“已整理如下”等前言。

## 参数

默认参数保存在 `config.json`。修改长期偏好时编辑配置文件；单次生成时按用户自然语言临时覆盖。

- `profile`：默认 `standard`。支持 `short`、`standard`、`long`；当前默认使用标准版。
- `source_bias`：默认 `mixed`。支持 `international`、`mixed`、`china`；当前默认中英混合。
- `style`：默认 `editorial`。每条保留一句“为什么值得看”的编辑精选点评。
- `interests.max_generated_queries`：根据关注偏好自动生成的额外搜索词数量上限，默认 8，避免搜索过慢或结果过散。
- `interests.topics`：长期关注的主题，例如 AI agents、coding agents、developer tools。
- `interests.keywords`：长期关注的关键词，例如 Codex、Claude Code、MCP、RAG。
- `interests.companies`：长期关注的公司或机构，例如 OpenAI、Anthropic、阿里、字节。
- `interests.models_or_projects`：长期关注的模型、产品或开源项目，例如 GPT、Claude、Qwen、Kimi。
- `interests.preferred_domains`：优先信任和优先搜索的域名，例如官方博客、GitHub、Hugging Face、arXiv。
- `interests.exclude_keywords`：排除关键词，例如 SEO、代发、博彩。
- `interests.exclude_domains`：排除域名，例如低质量社媒或不想看的来源。
- `sections.*.enabled`：控制栏目是否输出。
- `sections.*.limit`：控制栏目条目数量。
- `search_cosh.enabled`：是否使用 `search.cosh.fun` 做关键词补充搜索。
- `search_cosh.time_range`：默认 `day`，用于优先发现当天新闻。
- `search_cosh.limit_per_query`：每个关键词保留的搜索结果数量。
- `news_queries`：预抓取新闻用的搜索词；中英混合默认包含国际 AI 公司、开发者工具和国内大厂 AI 动态。
- `fallback_search_queries`：用于 `search.cosh.fun` 的基础搜索词；脚本会自动追加 `interests` 生成的关注查询。

自然语言覆盖示例：

- “生成短版，只保留 GitHub 和重要新闻。”
- “今天国内优先，重点看阿里、字节、腾讯、百度、智谱、月之暗面。”
- “今天重点关注 MCP、Claude Code 和开源 coding agent，不看融资新闻。”
- “不要今日观察，每个栏目最多 3 条。”

## 栏目与筛选

### AI 产品与工具

- 来源优先级：Product Hunt、厂商博客、官方发布、Hacker News、可靠媒体。
- 标准版默认 3-6 条，以 `config.json` 为准。
- 只收录和 AI、开发者工具、自动化、设计/创作生产力、数据分析、工程效率明显相关的产品。
- 每条写清楚“做什么”和“为什么值得看”，不要只翻译 slogan。

### GitHub Trending

- 来源优先级：预抓取的 GitHub Trending、GitHub 仓库页面、README。
- 标准版默认 5 条，以 `config.json` 为准。
- 优先收录 AI agent、LLM 应用、开发工具、基础设施、数据工程、安全、前端/后端高价值项目。
- 必须包含仓库链接；能获取 star、今日新增 star、语言时写上。

### 重要新闻

- 来源优先级：官方博客、研究机构、监管机构、主流科技媒体、可靠中文科技媒体。
- 标准版默认 3-8 条，以 `config.json` 为准。
- 只保留今天或最近 24 小时内仍值得关注的新闻；如果是周末或安静日，可以更少。
- 优先级：重大模型/产品发布、开源项目重要版本、云与开发平台变化、AI 公司融资/并购、监管政策、影响开发者的安全事件。
- 不收录软文、重复转载、轻微功能更新、无明确影响的传闻。
- 使用 `search_cosh` 结果做交叉验证：同一事件若同时出现在 Google News RSS、`search.cosh.fun` 或官方来源中，置信度更高；如果只出现在单个低权重转载源，需要继续核验或降级表述。
- 优先选择命中 `interests` 的条目；命中排除关键词或排除域名的条目默认剔除，除非它是不可忽略的重大事件。

### 今日观察

- 标准版默认 1-3 条短点评，以 `config.json` 为准。
- 从当天信息中提炼趋势、机会、风险或值得跟进的问题。
- 明确区分事实和判断，不要把推测写成事实。

## 输出模板

```markdown
# Cosh Tech Daily | {YYYY年M月D日}

## 🚀 AI 产品与工具

- **[Name](URL)** {votes/stars if available}
  一句话说明产品做什么。简短点评为什么值得开发者或 AI 用户关注。

## 🔥 GitHub Trending

- **[owner/repo](URL)** ⭐ {stars if available} {(+today) if available} · {language if available}
  项目说明。简短点评适合谁关注。

## 📰 重要新闻

- **[Headline](URL)**
  1-2 句中文摘要，说明影响。

## 🧭 今日观察

- 观察 1：基于今天条目的趋势或判断。
- 观察 2：可选。

---

> 来源以标题内链接为准；实时信息请以官方页面为最终准绳。
```

## 格式规则

- 最终日报必须以 `# Cosh Tech Daily | ...` 开头；不要在标题前输出解释。
- 中文正文使用全角标点。英文产品名、仓库名、模型名保留原文。
- 产品、仓库、新闻标题必须用 Markdown 内联链接，不要放裸 URL。
- 每个条目控制在 1-2 句，整篇适合 2 分钟内扫读。
- 如果某栏目没有足够高质量条目，写“今天暂无值得单列的重大更新”，不要填充低价值内容。
- 如果使用了脚本输出，优先相信脚本的链接和标题，但对重大新闻、日期和数字做联网核验。
- 如果 `search_cosh.unresponsive_engines` 显示多个搜索引擎不可用，降低搜索覆盖置信度，不要把“未搜到”当成“没有发生”。
- 如果联网不可用，明确标注“以下基于预抓取结果，未完成实时核验”，并避免使用“最新、今日已确认”等强表述。
- 如果用户关闭某栏目，不要输出该栏目标题。

## 质量检查

交付前确认：

- 是否运行了 `scripts/prefetch.py`，或说明了无法运行的原因。
- 是否读取了 `config.json` 并应用用户临时覆盖。
- 是否查看了 `search_cosh` 结果和 `unresponsive_engines`，并据此调整新闻置信度。
- 是否按 `interests` 提升关注内容优先级，并过滤排除项。
- 是否对失败来源进行了降级搜索或保守处理。
- 是否删除了重复新闻和低价值填充项。
- 是否所有产品、仓库、新闻标题都有链接。
- 是否没有把未经核验的推测写成事实。
- 是否直接以日报标题开头，没有前言。
