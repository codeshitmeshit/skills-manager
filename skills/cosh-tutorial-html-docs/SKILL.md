---
name: cosh-tutorial-html-docs
description: 根据技术笔记、操作步骤、项目说明或学习资料创建或更新精美的静态 HTML 教程文档站点。用户要求生成教程页、指南页、how-to 文档、学习文档、项目手册、工作流说明、部署指南、故障排查指南，或任何需要维护 .cosh-docs/guide.html 目录页、.cosh-docs/learn/ 教程页和 .cosh-docs/asset/ 资源目录的静态 HTML 教程时使用。
---

# 教程 HTML 文档

## 目标

把技术内容、操作步骤、项目说明或学习资料整理成可直接打开阅读的静态 HTML 教程站点。默认输出 HTML，不改用 Markdown、Word、PDF 或其他格式，除非用户明确要求。

输出应像正式教程站点：结构清楚、视觉统一、适合长时间阅读，而不是浏览器默认样式的文字堆叠。

## 默认工作流

1. 理解教程主题、目标读者和内容范围。
2. 在项目根目录创建或复用 `.cosh-docs/`，目录页固定为 `.cosh-docs/guide.html`，教程详情页固定放在 `.cosh-docs/learn/`，图片和图表资源固定放在 `.cosh-docs/asset/`。
3. 使用小写英文短横线命名教程页，例如 `.cosh-docs/learn/websocket-guide.html`。
4. 先检查 `.cosh-docs/guide.html`，不存在则用目录页模板创建，存在则读取并更新入口。
5. 检查已有教程页位置；如果 `.cosh-docs/` 根目录下存在除 `guide.html` 以外的 `.html` 教程页，移动到 `.cosh-docs/learn/` 并同步修正链接和资源路径。
6. 创建或修改教程详情页，优先使用详情页模板，保持独立可打开。
7. 需要流程图、架构图或截图时，创建或复用 `.cosh-docs/asset/`，并用相对路径引用。
8. 同步更新 `.cosh-docs/guide.html` 中的标题、简介、标签和链接，避免重复入口。
9. 检查链接、图片路径、移动端布局、离线打开效果和整体视觉质量。
10. 交付时告诉用户从 `.cosh-docs/guide.html` 开始查看。

## 文件结构

```text
project-root/
└── .cosh-docs/
    ├── guide.html
    ├── learn/
    │   ├── login-guide.html
    │   └── websocket-guide.html
    └── asset/
        ├── login-flow.svg
        └── system-architecture.png
```

资源命名使用英文小写和短横线，例如 `login-flow.svg`、`system-architecture.png`。不要使用 `图片1.png`、`new.png`、`test.svg` 这类名称。

## 模板资源

生成新页面时优先复制模板再替换内容：

- `assets/guide-template.html`：教程目录页模板，对齐 `/home/wo/code/ai-learn/.cosh-docs/guide.html` 的门户样式。
- `assets/tutorial-page-template.html`：教程详情页模板，用于 `.cosh-docs/learn/*.html` 的阅读页。

模板使用规则：

- 最终 HTML 中不能残留 `{{PLACEHOLDER}}`。
- 保持离线可打开，不依赖 CDN CSS、远程字体或远程脚本。
- 保留模板的核心视觉体系：浅色背景、白色卡片、柔和阴影、20px 左右圆角、深色代码块、标签、步骤块、提示块和响应式断点。
- 可按主题调整 `--primary`、`--soft` 或 `--primary-soft`，但不要大幅改动布局、字号、行高和组件间距。
- 详情页保持“返回目录 + hero + 本页目录 + 多个 card 章节”的结构。
- 目录页保持“双栏 hero + guide-card 网格 + roadmap”的结构。

## 目录页规则

每次新增或修改教程前，必须处理 `.cosh-docs/guide.html`。

如果不存在，用 `assets/guide-template.html` 创建，至少包含：

- 教程站点标题和简短说明
- 教程卡片列表
- 每个教程的标题、简介、分类标签和链接
- 必要时加入学习路线或分组说明

如果已存在：

- 判断当前教程是否已经出现，避免重复添加。
- 更新过期的标题、简介、标签和链接。
- 所有详情页入口链接必须指向 `./learn/<page>.html`，不要再链接到 `./<page>.html`。
- 同类教程放在一起；基础教程靠前，进阶教程靠后；部署、排错、FAQ 类内容一般靠后。
- 不破坏原有结构、链接和样式。

目录页必须使用卡片式布局，不要退化成普通 `<ul>` 链接列表。

## 教程页规则

每个主题通常生成一个独立 `.html` 文件，优先从 `assets/tutorial-page-template.html` 改写。根据内容选择章节，不要机械保留无意义模块。

教程详情页必须保存到 `.cosh-docs/learn/`。不要把新的详情页放在 `.cosh-docs/` 根目录。

常见模块：

- 返回目录页链接：`<a href="../guide.html">返回教程目录</a>`
- 主标题、简介、标签
- 前置准备或适用场景
- 本页目录
- 目标、核心概念、操作步骤
- 关键代码或配置
- 流程图、架构图或状态图
- 注意事项、踩坑点、FAQ
- 总结和下一步

步骤优先使用 `.steps` / `.step` / `.step-number` 组件。代码使用 `<pre><code>`，前后要解释代码的作用和运行方式。

## 作图规则

内容涉及系统架构、执行流程、数据流向、模块关系、部署流程、调用链、状态变化或复杂操作步骤时，考虑绘制配图。如果文字足够清楚，不要强制作图。

作图时：

- 优先使用清晰 SVG，必要时使用 PNG。
- 资源保存到 `.cosh-docs/asset/`。
- `.cosh-docs/learn/` 下的 HTML 使用相对路径，例如 `<img src="../asset/websocket-flow.svg" alt="WebSocket 连接流程图" />`。
- 图片放入模板的 `.diagram` 区域，并补充简短说明。

## 旧页面迁移

每次使用本 Skill 前都要检查 `.cosh-docs/` 根目录下的 `.html` 文件：

- `.cosh-docs/guide.html` 保持不动。
- 其他 `.html` 教程页必须移动到 `.cosh-docs/learn/`。
- 移动前先读取目标文件；如果 `.cosh-docs/learn/` 已有同名文件，不要直接覆盖，先比较内容并选择合并、改名或更新目录链接。
- 移动后修正该页面内部相对路径：返回目录从 `./guide.html` 改为 `../guide.html`，图片或图表从 `./asset/...` 改为 `../asset/...`。
- 移动后修正 `.cosh-docs/guide.html` 中对应入口：从 `./<page>.html` 改为 `./learn/<page>.html`。
- 检查旧路径没有被目录页、详情页或图片引用继续使用。

## 修改已有教程

修改已有教程时：

- 先读取目标 HTML 和 `.cosh-docs/guide.html`；目标 HTML 应位于 `.cosh-docs/learn/`。
- 在原有结构基础上修改，不无脑整页重写。
- 保持页面风格与现有教程一致。
- 新增章节、改标题或改简介后，同步判断是否需要更新目录页。
- 新增图片后检查 `.cosh-docs/asset/` 路径引用。

## 内容表达

语言清楚直接，适合初学者阅读。重要步骤解释原因，容易出错的地方给提醒。避免论文腔、空话、无关背景和只贴代码不解释。

## 质量检查

完成前检查：

- `.cosh-docs/guide.html` 可打开并显示完整教程目录。
- 目录项能进入 `.cosh-docs/learn/` 下的对应教程页。
- `.cosh-docs/` 根目录没有除 `guide.html` 以外的 `.html` 教程页。
- 页面标题区、正文区、代码块、提示块和图片区都有明确样式。
- 图片路径正确。
- 移动端没有明显错位或文字溢出。
- 不依赖后端服务或联网资源即可直接打开阅读。

如果结果像默认 HTML 页面，继续按模板美化后再交付。

## 交付总结

完成后说明：

- 创建或修改了哪些 HTML 文件。
- 是否创建或更新了 `.cosh-docs/guide.html`。
- 是否移动或修正了不在 `.cosh-docs/learn/` 下的旧教程页。
- 是否创建或使用了 `.cosh-docs/asset/` 及图片资源。
- 用户可以从 `.cosh-docs/guide.html` 开始查看教程。
