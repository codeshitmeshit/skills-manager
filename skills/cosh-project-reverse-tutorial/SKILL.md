---
name: cosh-project-reverse-tutorial
description: Use when the user wants to reverse-analyze a complete software repository, especially an open-source project, with mandatory Subagent collaboration and generate a 7:3 static HTML tutorial site. Triggers include requests to read an unfamiliar project, explain its architecture and Happy Path, trace real Git evolution, or produce .cosh-docs HTML project learning documentation using cosh-tutorial-html-docs.
---

# 项目逆向拆解与 HTML 教程

## 强制前置条件

本 Skill 必须使用 Subagent / 多 Agent 协作能力。主 Agent 不得单独完成全部分析，也不得只用文字模拟多 Agent。

执行任何项目分析或文件写入前，按顺序检查：

1. **Subagent 能力**
   - 存在：启动 Subagent 并行分析。
   - 不存在：提示用户启用或安装 Subagent 能力，并停止。
2. **`cosh-tutorial-html-docs` Skill**
   - 存在：读取该 Skill，并用它创建或更新 HTML 教程站点。
   - 不存在：提示用户安装 `cosh-tutorial-html-docs`，并停止。

缺少 Subagent 时使用提示：

```text
当前环境未检测到 Subagent / 多 Agent 协作能力，无法按本 Skill 要求完成项目逆向拆解。请先启用或安装支持 Subagent 的能力后再继续；在此之前，我不会继续分析项目或生成 HTML 教程。
```

缺少 `cosh-tutorial-html-docs` 时使用提示：

```text
当前环境未检测到 cosh-tutorial-html-docs Skill，无法生成 HTML 教程文档。请先安装该 Skill 后再继续；在安装完成前，我不会继续进行教程生成或文件写入。
```

## 目标

帮助个人开发者快速读懂陌生开源项目，并生成可直接打开阅读的 `.cosh-docs/` 静态 HTML 教程站点。

教程遵循 **7:3 黄金法则**：

- **70% 现状静态拆解**：当前目录、模块边界、入口、核心 Happy Path、关键抽象。
- **30% 真实历史演进**：只基于 Git commit、tag、blame、diff 解释主流程相关复杂设计的来源。

7:3 是认知重心，不是机械字数比例。无真实 Git 证据时，不得编造演进叙事，必须标注不可验证或要求用户补充历史材料。

## 主 Agent 职责

主 Agent 是协调者、监督者和最终汇总者，负责：

- 检查 Subagent 能力和 `cosh-tutorial-html-docs` 是否可用。
- 分派并行分析任务，控制每个 Subagent 的输入范围。
- 汇总结构、链路、历史三类证据。
- 处理 Subagent 结论冲突，优先保证架构完整性。
- 确保教程主线围绕最核心 Happy Path。
- 使用 `cosh-tutorial-html-docs` 将各 Subagent 的 HTML-ready 素材汇总成教程站点。
- 监督 HTML 教程生成质量和 `.cosh-docs/guide.html` 入口更新。

## Subagent 分工

### 结构分析 Subagent

职责：

- 扫描目录树、README、配置文件和模块入口。
- 识别核心目录职责、模块边界、依赖方向和整体架构模式。
- 输出项目全景、目录职能说明和架构图建议。
- 输出可直接进入 HTML 教程的章节素材，包括标题、摘要、证据清单和图表建议。

目标：回答“这个项目由哪些部分组成，各自承担什么角色”。

### 主流程链路 Subagent

职责：

- 从启动入口、命令入口、路由入口或任务调度入口出发。
- 追踪最核心的 Happy Path。
- 找出关键调用栈、核心函数、枢纽类和必要配置。
- 输出可直接进入 HTML 教程的主流程走读、调用栈、关键代码证据和读者提示。

目标：回答“项目最核心的功能是怎么跑起来的”。

### Git 历史溯源 Subagent

职责：

- 基于真实 Git 历史分析主流程相关文件。
- 追踪关键 commit、tag、blame 和 diff。
- 解释复杂设计、重构、缓存、状态机、防御性代码的真实引入原因。
- 输出可直接进入 HTML 教程的演进章节、diff 摘要、证据引用和不可验证声明。

目标：回答“当前复杂设计为什么会变成现在这样”。

每个 Subagent 都要把结论整理成可被 HTML 教程直接吸收的内容块。不要设置独立的 HTML 生成 Subagent；HTML 站点生成由主 Agent 在汇总后统一调用 `cosh-tutorial-html-docs` 完成。

## 工作流

1. **能力检查**
   - 检查 Subagent 能力；不存在则停止。
   - 检查 `cosh-tutorial-html-docs`；不存在则停止。

2. **并行分析**
   - 结构分析 Subagent 分析项目全景和模块边界。
   - 主流程链路 Subagent 追踪核心 Happy Path。
   - Git 历史溯源 Subagent 只追踪主流程相关关键历史。
   - 每个 Subagent 同步产出 HTML-ready 章节素材，而不是只给分析结论。

3. **交叉对齐**
   - 对齐模块结构、调用链和历史证据。
   - 每个复杂设计都要说明当前职责和真实历史来源。
   - 冲突时优先使用代码、配置、调用链和 Git diff 证据。

4. **教程大纲**
   - 先形成高证据密度大纲。
   - 大项目只展开最核心主流程，其余模块列为延伸阅读。
   - 明确需要的架构图、调用链图或演进图。

5. **HTML 生成**
   - 主 Agent 使用 `cosh-tutorial-html-docs` 创建或更新 `.cosh-docs/guide.html`。
   - 主 Agent 将三个 Subagent 的 HTML-ready 素材融合为统一教程，不保留割裂的 Agent 报告结构。
   - 创建一个项目拆解教程 HTML 页，使用小写英文短横线命名。
   - 图表资源放入 `.cosh-docs/asset/`，使用相对路径引用。

6. **最终验收**
   - 检查目录页入口、详情页链接、图片路径、移动端布局和离线可读性。
   - 向用户说明创建或修改的文件，并提示从 `.cosh-docs/guide.html` 开始阅读。

## 教程结构

默认输出双层结构。

### 30 分钟快速总览

包含：

- 项目一句话定位。
- 技术栈与启动入口。
- 核心目录地图。
- 最重要的 1 条 Happy Path。
- 2 到 3 个必须先理解的核心抽象。
- 当前最值得注意的复杂设计。
- 后续深入阅读路径。

### 系统课程正文

包含：

1. 项目全景：系统解决的问题、数据或请求流向、整体结构图。
2. 目录与模块职责：解释核心目录的架构角色，避免逐文件流水账。
3. 核心主流程走读：从入口追踪 Happy Path，给出调用栈和关键代码证据。
4. 关键抽象与设计模式：解释最值得学习的 2 到 3 个抽象及其位置。
5. 真实历史演进：基于主流程相关 commit、tag、diff 讲清设计变化。
6. 复杂设计来龙去脉：对缓存、状态机、插件机制、并发控制、防御性代码进行现状与历史交叉解释。
7. 延伸阅读：列出非主流程模块、建议文件和后续 commit，不默认展开全部细节。

## 证据要求

关键判断必须尽量引用：

- 文件路径。
- 函数名、类名、模块名。
- 调用链。
- 配置项。
- commit hash、tag、blame 或 diff 摘要。
- README 或项目文档中的说明。

禁止用没有证据的空泛判断替代分析。历史演进只能基于真实 Git 证据；无法验证时写明“未能从历史验证”。

## 范围边界

应做：

- 项目结构解读。
- 主流程代码走读。
- 核心抽象解释。
- 真实 Git 演进分析。
- `.cosh-docs/` HTML 教程站点生成。

不应做：

- 全量 API 文档生成。
- 所有文件逐个解释。
- 架构优劣评审。
- 代码修改方案。
- 性能优化方案。
- 没有证据的历史故事化推演。

## 质量检查

交付前确认：

- 已实际使用 Subagent 能力并由主 Agent 汇总监督。
- 已使用 `cosh-tutorial-html-docs` 创建或更新 HTML 教程。
- `.cosh-docs/guide.html` 存在并包含教程入口。
- 教程详情页可从目录页进入。
- 图表和图片资源路径正确。
- 页面可离线打开，不依赖后端服务或联网资源。
- 关键判断有文件、调用链或 Git 历史证据。
- 大项目没有失焦为全仓库百科，主线仍围绕核心 Happy Path。
