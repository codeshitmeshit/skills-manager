---
name: cosh-tutorial-html-docs
description: Create or update polished static HTML tutorial documentation sites from technical notes, operation steps, project explanations, or learning material. Use when the user asks to generate tutorial pages, guide pages, how-to documentation, learning docs, project manuals, workflow explanations, deployment guides, troubleshooting guides, or any static HTML tutorial that should maintain a .cosh-docs/guide.html index and .cosh-docs/asset/ folder.
---

# 教程 HTML 文档

## 目标

将用户提供的技术内容、操作步骤、项目说明或学习资料整理成结构清晰、视觉美观、可直接打开阅读的 HTML 静态教程页面。不要只堆砌文字；输出应像正式教程站点，而不是默认浏览器样式页面。

默认生成静态 HTML。除非用户明确要求 Markdown、Word、PDF 或其他格式，不要改用其他格式。

## 默认工作流

1. 理解教程主题、目标读者和内容范围。
2. 在项目根目录下创建或复用 `.cosh-docs/` 文件夹，所有教程文档、目录页和资源都必须放在这里。
3. 判断教程文件名，使用小写英文和短横线，例如 `websocket-guide.html`。
4. 先检查 `.cosh-docs/guide.html` 是否存在。
5. 如果不存在，创建美观的教程目录页。
6. 如果存在，读取并判断是否需要新增或更新对应条目，避免重复入口。
7. 编写或修改 `.cosh-docs/` 内的教程 HTML 页面，保持独立可打开。
8. 判断是否需要作图；需要时创建或复用 `.cosh-docs/asset/` 文件夹。
9. 将图片资源保存到 `.cosh-docs/asset/`，并使用相对路径引用。
10. 同步更新 `.cosh-docs/guide.html` 中的标题、简介、分类标签和链接。
11. 检查链接、图片路径、移动端布局和整体视觉质量。
12. 总结创建或修改的文件，并告诉用户从 `.cosh-docs/guide.html` 开始查看。

## 文件结构

推荐结构：

```text
project-root/
└── .cosh-docs/
    ├── guide.html
    ├── login-guide.html
    ├── websocket-guide.html
    ├── deployment-guide.html
    └── asset/
        ├── login-flow.svg
        ├── websocket-process.svg
        └── system-architecture.png
```

所有教程 HTML 文件、`guide.html` 和教程相关图片、流程图、架构图等资源都放入 `.cosh-docs/`。资源统一放在 `.cosh-docs/asset/` 文件夹。图片命名使用英文小写和短横线，例如 `login-flow.svg`、`system-architecture.svg`，不要使用 `图片1.png`、`new.png`、`test.svg`。

## .cosh-docs/guide.html 规则

每次新增或修改教程前，必须处理 `.cosh-docs/guide.html`。

如果 `.cosh-docs/guide.html` 不存在，创建教程门户页，至少包含：

- 教程站点标题和简短说明
- 教程卡片列表
- 每个教程的标题、简介、分类标签和链接
- 统一且现代的页面样式

如果 `.cosh-docs/guide.html` 已存在，读取后判断：

- 当前教程是否已经出现，避免重复添加
- 标题、简介、分类标签和链接是否需要更新
- 新条目应插入到哪个分类或位置

插入原则：

- 同类教程放在一起
- 基础教程靠前，进阶教程靠后
- 部署、排错、FAQ 类内容一般靠后
- 不破坏原有结构、链接和样式
- 没有分类结构时追加到教程列表末尾

目录页应使用卡片式布局，不要只是普通 `<ul>` 链接列表。

## 教程页面规则

每个主题通常生成一个独立 `.html` 文件。页面必须包含完整 HTML 结构：

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>教程标题</title>
  <style>
    /* 页面样式 */
  </style>
</head>
<body>
  <!-- 教程内容 -->
</body>
</html>
```

根据内容合理组织模块，不要机械套模板。常见模块包括：

- 返回目录页链接，例如 `<a href="./guide.html">返回教程目录</a>`；教程页和 `guide.html` 同在 `.cosh-docs/` 下，因此链接保持相对路径
- 主标题和教程简介
- 适用场景
- 前置准备
- 操作步骤
- 关键代码或配置
- 注意事项和提示块
- 流程图或架构图
- 常见问题
- 总结和下一步

步骤不要只写成普通段落。优先使用序号卡片或步骤块：

```html
<div class="step">
  <div class="step-number">01</div>
  <div>
    <h3>建立连接</h3>
    <p>设备端先访问 WebSocket 接口，并携带 token 和设备认证信息。</p>
  </div>
</div>
```

代码使用 `<pre><code>` 展示，前后要有解释：

```html
<pre><code>npm install
npm run dev</code></pre>
```

## UI 标准

生成的页面必须具备完整 CSS，不能依赖浏览器默认样式，也不要依赖必须联网才能显示的 CDN 样式。

整体风格要求：

- 简洁、美观、大气，适合长时间阅读
- 正文宽度建议控制在 `960px` 到 `1120px`
- 页面居中，两侧留白充足
- 使用清晰的标题层级、舒适行高和合理分区
- 使用卡片、提示块、步骤块、代码块、标签和按钮区分内容
- 图片区域有边框、圆角或阴影
- 移动端不明显错位，文字不溢出容器
- 目录页和详情页风格统一

可使用浅色背景、白色或半透明卡片、柔和阴影、圆角、有限的色彩点缀和现代文档站点布局。避免刺眼、杂乱、过度花哨或像临时测试页。

## 推荐 CSS 基础

可按主题调整，但要保持统一、现代、可读：

```css
:root {
  --bg: #f5f7fb;
  --card: #ffffff;
  --text: #1f2937;
  --muted: #6b7280;
  --primary: #2563eb;
  --primary-soft: #dbeafe;
  --border: #e5e7eb;
  --shadow: 0 18px 45px rgba(15, 23, 42, 0.08);
  --radius: 20px;
}

* { box-sizing: border-box; }

body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", sans-serif;
  background:
    radial-gradient(circle at top left, rgba(37, 99, 235, 0.16), transparent 32%),
    linear-gradient(180deg, #f8fbff 0%, #eef2f7 100%);
  color: var(--text);
  line-height: 1.8;
}

.container {
  max-width: 1080px;
  margin: 0 auto;
  padding: 40px 24px 64px;
}

.hero, .card, .guide-card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
}

pre {
  overflow-x: auto;
  padding: 20px;
  border-radius: 16px;
  background: #0f172a;
  color: #e5e7eb;
  font-size: 14px;
  line-height: 1.7;
}

code {
  font-family: "JetBrains Mono", "Fira Code", Consolas, monospace;
}

img {
  max-width: 100%;
  border-radius: 18px;
  border: 1px solid var(--border);
  box-shadow: 0 12px 28px rgba(15, 23, 42, 0.08);
}

@media (max-width: 768px) {
  .hero { padding: 32px 24px; }
  .card { padding: 22px; }
  .step { flex-direction: column; }
}
```

## 作图规则

内容涉及系统架构、执行流程、数据流向、模块关系、页面结构、部署流程、调用链、状态变化或复杂操作步骤时，考虑绘制配图。如果文字足够清楚，不要强制作图。

作图时：

- 创建或复用 `.cosh-docs/asset/` 文件夹
- 优先用清晰 SVG 流程图或架构图，必要时使用 PNG
- HTML 中使用相对路径，例如 `<img src="./asset/websocket-flow.svg" alt="WebSocket 连接流程图" />`
- 图片区域需要有标题、说明和样式化容器

## 修改已有教程

修改已有教程时：

- 先判断 `.cosh-docs/` 下的目标教程文件是否存在
- 在原有结构基础上修改，不要无脑重写整页
- 保持页面风格一致
- 新增章节后判断是否要同步更新 `.cosh-docs/guide.html` 中的标题或简介
- 新增图片后保存到 `.cosh-docs/asset/` 并检查引用路径
- 不破坏已有链接、样式和目录结构

## 内容表达

教程语言要清楚直接，适合初学者阅读。重要步骤解释原因，容易出错的地方给提醒。避免论文腔、空话、无关背景和只贴代码不解释。

示例语气：

```text
这一步的作用是启动本地服务。启动成功后，浏览器才能访问对应的页面。
如果这里报端口占用，可以先检查是否已经有其他程序使用了该端口。
```

## 质量检查

完成前检查：

- `.cosh-docs/guide.html` 可打开并显示完整教程目录
- 目录项可以进入对应教程页面
- 页面第一眼不显得简陋
- 标题区、正文区、代码块、提示块和图片区都有明确样式
- 目录页使用卡片布局
- 图片路径正确
- 移动端没有明显错位或文字溢出
- 不依赖后端服务即可直接打开阅读

如果结果像默认 HTML 页面，继续美化后再交付。

## 交付总结

完成后明确说明：

- 创建或修改了哪些 HTML 文件
- 是否创建或更新了 `.cosh-docs/guide.html`
- 是否创建或使用了 `.cosh-docs/asset/` 文件夹
- 新增了哪些图片资源
- 用户可以从 `.cosh-docs/guide.html` 开始查看教程
