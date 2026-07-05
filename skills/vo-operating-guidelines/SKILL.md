---
name: vo-operating-guidelines
description: Virtual Office 中任意 CLI 或 agent 需要判断是否处于 VO 环境、读取 VO 本地权威 skill、选择正确 VO 工作流或处理 VO 不可用降级时使用；本 skill 只作为入口，不维护具体 VO API 指南。
---

# Virtual Office Skill 入口

## 目标

本 skill 只作为 Virtual Office 的入口。完整 VO 系 skill 由当前 Virtual Office 实例维护，必须优先读取当前本地 VO 暴露的 skill 文件，不要在 skill management 中维护或复述具体 VO API 操作细节。

不要硬编码、输出或传播任何生产域名、外部部署 URL、token、cookie、密钥或非本地配置。所有 VO 操作依据都应来自当前可访问的本地 VO 实例。

## 探测当前 VO

按以下顺序确定本地 `VO_BASE_URL`：

1. 如果环境变量已有 `VO_BASE_URL`，直接使用。
2. 如果环境变量已有 `VO_PORT`，使用 `http://127.0.0.1:$VO_PORT`。
3. 如果能访问当前 VO 项目本地 `.env`，读取其中的 `VO_PORT` 后使用 `http://127.0.0.1:$VO_PORT`。
4. 最后尝试默认地址 `http://127.0.0.1:8090`。

可使用下面的本地探测片段：

```bash
if [ -z "${VO_BASE_URL:-}" ] && [ -z "${VO_PORT:-}" ] && [ -f /home/wo/code/my-virtual-office/.env ]; then
  VO_PORT="$(awk -F= '$1=="VO_PORT"{print $2; exit}' /home/wo/code/my-virtual-office/.env)"
fi
VO_BASE_URL="${VO_BASE_URL:-http://127.0.0.1:${VO_PORT:-8090}}"
curl -sS "$VO_BASE_URL/vo-config"
```

如果当前运行环境不是 VO 本机环境，`127.0.0.1` 可能指向调用方自身。此时不要猜测公网地址；应停止 VO 专属动作，并要求提供当前可访问的本地 VO 地址。

## 读取本地权威 Skill

读取当前 VO 实例的 skill 总入口：

```bash
curl -sS "$VO_BASE_URL/skills/index.md"
```

`/skills/index.md` 由当前 VO 实例映射到本地 `vo-operating-guidelines` 权威 skill。根据该总入口的路由说明，按需读取对应 skill：

```text
/skills/vo-agent-communication/SKILL.md
/skills/vo-codex-communication/SKILL.md
/skills/vo-browser-control/SKILL.md
/skills/vo-agent-workspace/SKILL.md
/skills/vo-project-workflow/SKILL.md
/skills/vo-meeting-execution/SKILL.md
```

如果本地 VO skill 文件不可访问，不要继续执行 VO 专属动作，也不要使用 skill management 中的旧知识补全。报告实际失败地址和错误，并要求用户确认 VO 是否已启动或当前 agent 是否能访问该本地实例。

## 安全规则

- 只把当前本地 VO 实例暴露的 `/skills/.../SKILL.md` 作为 VO 操作指南的权威来源。
- 不使用生产域名或外部 URL 作为 agent 操作依据。
- 不输出生产域名、外部部署 URL、token、cookie、密钥或敏感配置。
- 不在本 skill 中复述或维护具体 VO API 细节；读取本地 VO skill 后再执行。
- 不绕过本地 VO 的通信、项目、会议、workspace 或浏览器边界。
- 本地 VO 不可访问时，停止 VO 专属动作并明确降级。

## 质量检查

执行任何 VO 动作前确认：

- 已确定当前可访问的本地 `VO_BASE_URL`。
- 已读取 `$VO_BASE_URL/skills/index.md`。
- 已按本地 VO skill 指南选择具体工作流。
- 没有依赖 skill management 中的旧 VO API 说明。
- 没有泄露或固化任何非本地地址与敏感信息。
