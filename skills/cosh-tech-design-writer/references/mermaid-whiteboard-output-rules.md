# Mermaid 飞书画板输出规则

当用户要求“把 Mermaid 转成飞书画板内容”“输出飞书画板 XML”“插入可编辑画板”或“更新已有飞书画板”时，使用本规则。它和图片追加规则不同：本流程优先保留飞书画板的可编辑能力，而不是把图渲染成普通图片。

## 输出路径选择

| 用户意图 | 推荐路径 | 产物 |
| --- | --- | --- |
| 只要输出可放进飞书文档的内容 | 文档 XML 画板块 | `<whiteboard type="mermaid">...</whiteboard>` |
| 创建技术方案文档时直接包含画板 | `lark-cli docs +create/+update` 写入 XML | 文档中的可编辑 Mermaid 画板 |
| 已有画板 token，需要替换/更新内容 | `lark-cli whiteboard +update --input_format mermaid` | 已更新的飞书画板 |
| 用户明确要普通图片 | 读取 `diagram-image-append-rules.md` | PNG/JPEG 图片块 |

没有 doc token 或 whiteboard token 时，不要假装已写入画板；可以输出 XML 画板块供后续插入。

## 必读 CLI 参考

创建或更新文档画板块前，必须使用 `lark-doc` skill 并读取：

```bash
lark-cli skills read lark-doc references/lark-doc-whiteboard.md
lark-cli skills read lark-doc references/lark-doc-xml.md
```

更新已有画板 token 前，必须使用 `lark-whiteboard` skill 并读取：

```bash
lark-cli skills read lark-whiteboard references/lark-whiteboard-update.md
```

## Mermaid 预处理

- 只使用完整 Mermaid 源码，不要省略 `flowchart TD`、`sequenceDiagram` 等图类型声明。
- Mermaid 内容必须与技术方案正文中的调用链、流程或架构描述一致。
- 节点文案使用业务可读名称；复杂图拆成多张小图。
- 如果 Mermaid 语法不确定，先输出源码并标记需要校验，不要写入飞书后声称成功。
- 不要把 Markdown 代码围栏放进 `<whiteboard>` 内，画板块只包含 Mermaid 源码本身。

## 路径 A：输出文档 XML 画板块

当用户只要求“输出飞书画板内容”或没有可写 doc/token 时，返回如下 XML：

```xml
<whiteboard type="mermaid">
flowchart TD
    A["入口"] --> B["参数校验"]
    B --> C["核心处理"]
    C --> D["返回结果"]
</whiteboard>
```

如果有多张图，每张图单独输出一个 `<whiteboard type="mermaid">` 块，并在块前给出来源章节和图名。

## 路径 B：创建或更新飞书文档中的画板块

创建新技术方案文档时，可以把画板块直接放进 `docs +create --content` 的 XML 正文中：

```xml
<h1>三、方案总览：一张图看懂整体设计</h1>
<p>核心调用链如下：</p>
<whiteboard type="mermaid">
sequenceDiagram
    participant Client as 调用方
    participant API as 接口服务
    Client->>API: 发起请求
    API-->>Client: 返回结果
</whiteboard>
```

更新已有文档时，优先用 `docs +update` 的 XML 局部插入能力，把画板块插到目标章节附近；如果只能追加，必须说明实际插入位置。

## 路径 C：更新已有飞书画板

如果用户提供了 `whiteboard-token`，使用 `lark-cli whiteboard +update`：

```bash
lark-cli whiteboard +update \
  --whiteboard-token "<whiteboard_token>" \
  --input_format mermaid \
  --source @/private/tmp/cosh-tech-design-diagrams/flow.mmd \
  --overwrite \
  --as user
```

成功后记录返回结果；最终回复至少包含画板 token、图名、是否覆盖更新、以及 Mermaid 源码是否保留在技术方案正文中。

## 失败与降级

- 缺少写权限、认证失败或 token 无效：不要重试破坏性操作；说明失败原因和需要用户提供的权限/token。
- Mermaid 语法错误：保留源码，问题文档记录语法校验失败和需确认节点。
- 用户原本要求可编辑画板，但当前只能生成图片：必须先说明能力降级，不能把图片说成画板内容。

## 质量检查

- 已明确选择 XML 画板块、文档写入或已有画板更新路径。
- XML 画板块不包含 Markdown 代码围栏。
- 每张图都有图名、来源章节和完整 Mermaid 源码。
- 写入已有画板时使用 `--input_format mermaid`，并记录 token 与更新结果。
- 未修改目标业务代码仓库文件。
