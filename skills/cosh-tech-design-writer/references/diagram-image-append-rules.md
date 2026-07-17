# 图表图片追加规则

当用户要求 Mermaid、PlantUML 或 SVG “以图片形式”进入飞书文档，或最终技术方案希望把调用图、流程图、架构图追加为普通图片时，使用本规则。该流程只处理技术方案文档中的图表呈现，不修改目标业务代码仓库。

## 适用边界

- 适用：Mermaid、PlantUML、SVG 源码已经由技术方案正文、程序员复核 subagent 或用户提供。
- 适用：需要在飞书文档末尾追加普通图片，便于直接浏览、复制和下载。
- 不适用：用户明确要求图可在飞书内继续编辑。可编辑图优先走 `lark-doc` 的 `<whiteboard type="mermaid">` / `<whiteboard type="svg">` 或 `lark-whiteboard`。
- 不适用：缺少图表源码且无法从方案内容低风险生成。此时先按确认问题流程追问。

## 必读 CLI 参考

执行飞书写入前必须使用 `lark-doc` skill，并读取 CLI 当前版本的参考：

```bash
lark-cli skills read lark-doc references/lark-doc-media-insert.md
```

如用户改为要求可编辑画板，再读取：

```bash
lark-cli skills read lark-doc references/lark-doc-whiteboard.md
lark-cli skills read lark-whiteboard references/lark-whiteboard-update.md
```

## 推荐流程

1. 为每张图确定标题、来源章节和源码格式：`mermaid`、`plantuml` 或 `svg`。
2. 将源码保存到临时目录，例如 `/private/tmp/cosh-tech-design-diagrams/<safe-name>.mmd`、`.puml` 或 `.svg`。
3. 优先渲染为 PNG。PNG 在飞书图片上传、宽高识别和预览上更稳定。
4. 使用 `lark-cli docs +media-insert` 将图片追加到技术方案文档末尾，并设置居中、标题和合理宽度。
5. 插入后记录返回的 `block_id`、`file_token`、图名和来源章节；必要时在最终回复中说明。

## 渲染方式

### Mermaid

优先使用本机已有的 `mmdc`：

```bash
mmdc -i /private/tmp/cosh-tech-design-diagrams/flow.mmd \
  -o /private/tmp/cosh-tech-design-diagrams/flow.png \
  -b white -s 2
```

如果 `mmdc` 不存在，可在用户允许安装或网络可用时使用 Mermaid CLI；否则不要强行声称已生成图片，保留 Mermaid 代码块并把“缺少 Mermaid 渲染器”写入问题文档或最终回复。

### PlantUML

优先使用本机已有的 `plantuml`：

```bash
plantuml -tpng /private/tmp/cosh-tech-design-diagrams/sequence.puml
```

如果只有 `java -jar plantuml.jar` 可用，也可以渲染为 PNG。若本机没有 PlantUML 渲染器，记录失败原因，不要把 PlantUML 代码块当作已插入图片。

### SVG

SVG 源码优先转换成 PNG 后插入。可用工具包括 `rsvg-convert`、`inkscape` 或系统可用的等价转换器：

```bash
rsvg-convert /private/tmp/cosh-tech-design-diagrams/arch.svg \
  -o /private/tmp/cosh-tech-design-diagrams/arch.png
```

只有确认当前飞书上传链路接受 SVG 图片并能正常预览时，才直接用 SVG 作为图片上传；否则必须转为 PNG。

## 追加到飞书文档

使用 `docs +media-insert` 追加图片。`--doc` 优先使用 `docs +create` 返回的 `doc_id`；如果只有 `/wiki/...` 链接，不要直接传 wiki URL，先取得对应 docx/document id。

```bash
lark-cli docs +media-insert \
  --doc "<doc_id_or_docx_url>" \
  --file /private/tmp/cosh-tech-design-diagrams/flow.png \
  --align center \
  --caption "三、方案总览：核心调用链图" \
  --width 800
```

每张图单独插入；多个图互不依赖时可以顺序插入，便于定位失败图。不要把所有图拼成一张大图，除非用户明确要求。

## 文档正文配合

- 技术方案正文仍保留 Mermaid/PlantUML/SVG 源码或简短说明，方便后续维护。
- 图片追加在文档末尾时，caption 必须包含来源章节，例如 `三、方案总览：核心调用链图`。
- 如果用户要求图片出现在具体章节下，而 `docs +media-insert` 只能追加到末尾，则先说明能力边界；需要精确位置时改用 `docs +update` 的图片 XML 或块级插入能力。
- 插入图片失败时，技术方案正文不要写成“已插入图片”；问题文档记录失败原因、降级方式和下一步。

## 质量检查

- 图表源码语法完整，且与技术方案正文中的调用链或流程一致。
- 每张图都有唯一文件名、caption 和来源章节。
- 图片实际渲染成功，且文件存在、大小非 0。
- `docs +media-insert` 返回成功，并记录 `block_id` 或 `file_token`。
- 未修改目标业务代码仓库文件。
