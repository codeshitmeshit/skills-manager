---
name: vo-operating-guidelines
description: Virtual Office 引导入口。任意 CLI 或 agent 需要判断是否处于本地 VO/VU、按本地端口拼接 HTTP 地址、读取当前 VO 实例的权威 skill、选择通信/项目/workspace/浏览器/会议工作流，或在 VO 不可达时安全降级时使用；不在 skill-manager 中维护具体 VO API 细节。
---

# Virtual Office Skill 入口

## 目标

定位当前可访问的 Virtual Office，读取该实例提供的权威 skill 总入口，再按实例规则选择工作流。

本 skill 只负责发现和引导。不要在 skill-manager 中复制 VO 的具体 API、业务规则或专用工作流；这些内容由当前 VO 实例维护。

## 工作流

### 1. 判断运行位置

先判断当前 CLI 或 agent 是否运行在 VO/VU 本地项目环境中：

- 能访问当前 VO 项目目录，或当前进程已有 `VO_PORT`：按本地环境处理。
- 明确运行在其他机器或隔离环境：按非本地环境处理。
- 无法判断：先尝试本地探测；失败后停止 VO 专属动作，不猜测外部地址。

能读取本地项目文件只证明文件可见；如果运行环境明确存在独立网络边界，不要假设它与 VO 服务共享 `127.0.0.1`。

### 2. 拼接本地地址

本地环境不需要获取、询问或暴露外部 Base URL。按以下顺序确定端口：

1. 使用当前进程的 `VO_PORT`。
2. 从当前 VO 项目 `.env` 读取 `VO_PORT`。
3. 回退到默认端口 `8090`。

把端口拼成 `http://127.0.0.1:$VO_PORT`，再追加 skill 接口路径：

```bash
VO_PROJECT_ROOT="${VO_PROJECT_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
if [ -z "${VO_PORT:-}" ] && [ -f "$VO_PROJECT_ROOT/.env" ]; then
  VO_PORT="$(awk -F= '$1=="VO_PORT"{print $2; exit}' "$VO_PROJECT_ROOT/.env")"
fi
VO_LOCAL_URL="http://127.0.0.1:${VO_PORT:-8090}"
curl -sS "$VO_LOCAL_URL/skills/index.md"
```

只有调用方明确不在当前 VO/VU 本地运行环境中时，才使用用户或运行环境显式提供的 `VO_BASE_URL`。不要自行猜测、搜索或传播生产域名和外部部署地址。

### 3. 读取实例权威 Skill

完整读取当前实例返回的 `/skills/index.md`，再根据其中的路由说明读取所需专用 skill。以当前 VO 实例暴露的 `/skills/...` 内容为唯一权威来源。

不要使用 skill-manager 中的历史知识补全具体接口，也不要绕过当前实例定义的通信、项目、workspace、浏览器或会议边界。

### 4. 处理不可达

如果本地 skill 总入口不可访问：

- 报告尝试过的本地地址和原始错误。
- 检查 `VO_PORT` 与项目 `.env`，不要只重复尝试默认端口。
- 如果当前 provider runtime 访问不到 localhost，优先判断为 sandbox/container 与宿主机隔离；可以主动申请一次宿主侧只读 VO skill 访问，用于读取同一个 `http://127.0.0.1:<port>/skills/index.md`。
- 该申请只能覆盖 `GET /skills/index.md`、`GET /skills/vo-*/SKILL.md`、`GET /skills/vo-*/references/*.md`，不能扩大到 VO API、项目数据、数据写入或任意 shell 操作。
- 如果沙箱外/宿主侧读取也失败，停止 VO 专属动作并报告访问失败；不要为了读取 skill 入口继续要求用户提供 bridge。
- 停止 VO 专属动作，不回退到直接读取仓库模块来替代 HTTP 权威入口。
- 只有确认调用方属于非本地环境时，才请求提供其可访问的 `VO_BASE_URL`。

## 安全规则

- 不硬编码或输出生产域名、外部部署 URL、token、cookie、密钥或敏感配置。
- 不把外部 Base URL 当作本地 VO/VU agent 的必需配置。
- 不因能读取本地文件就忽略已知的网络隔离边界。
- 不在本入口维护具体 VO API 和下游工作流副本。

## 质量检查

执行 VO 动作前确认：

- 已判断当前调用方属于本地还是非本地运行环境。
- 本地环境已通过 `VO_PORT` 或项目 `.env` 拼出 loopback 地址。
- 已完整读取当前实例的 `/skills/index.md`。
- 已按实例权威 skill 路由，没有依赖 skill-manager 中的旧接口知识。
- 不可达时已明确降级，没有猜测或泄露外部地址。
