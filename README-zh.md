# cosh-skills

English: [README.md](README.md)

`cosh-skills` 是一个命令行工具，用于管理本地 skill 仓库，并将其中的 skill 同步到支持的 CLI 工具中。

第一版支持的目标 CLI：

- `codex`
- `claude`
- `qwen`
- `openclaw`
- `hermes`

工具要求你先自行 clone skill 仓库。它会更新这个本地 git 仓库，并从下面的位置扫描有效 skill：

```text
{repo_path}/skills/{skill-name}/SKILL.md
```

然后同步到已配置的目标 CLI skills 目录。

## 安装

不带参数运行本地安装脚本：

```bash
scripts/install.sh
```

该脚本会以 editable 模式安装 Python 包和依赖，然后写入包装脚本 `~/.local/bin/cosh-skills`。这个包装脚本会先切换到当前仓库目录，再执行 Python 模块入口，所以可以从任意目录运行。安装脚本不会询问 `repo_path`、`cli`、`skills_path` 等业务参数。

不要把 `cosh-skills` alias 到 `python3 -m internal.cli`；这个模块命令只有在仓库位于 `PYTHONPATH` 中时才可用。如果 shell 仍然显示 alias，请从 `~/.zshrc` 或 `~/.bashrc` 删除它。如果 shell 找不到 `cosh-skills`，请确认 `~/.local/bin` 在 `PATH` 中。

### 本地 shell 配置

如果使用 zsh，在 `~/.zshrc` 中保留下面这行：

```bash
export PATH="$HOME/.local/bin:$PATH"
```

不要添加 `cosh-skills` alias。如果之前已经添加过下面这行，请删除：

```bash
alias cosh-skills='python3 -m internal.cli'
```

重新加载配置并确认命令来源：

```bash
source ~/.zshrc
unalias cosh-skills 2>/dev/null || true
which cosh-skills
```

期望输出：

```text
/home/wo/.local/bin/cosh-skills
```

验证安装：

```bash
cosh-skills --help
```

初始化 Codex 启动 hook：

```bash
cosh-skills init --cli codex
```

该命令会写入 `~/.codex/hooks.json`，并将 hook 命令设置为当前 Python 解释器的模块入口，避免 Codex 启动 hook 中没有加载 shell alias 或用户 `PATH` 时找不到 `cosh-skills`。它还会写入当前 skill 仓库路径，并在缺省时设置 `cli.codex.skills_path` 为 `~/.codex/skills`。

如果希望启动 hook 在本地 skill 仓库提交领先远程时仍继续同步，可以使用：

```bash
cosh-skills init --cli codex --force
```

Codex 对新增或变更的非托管 hook 需要信任后才会执行。运行 `cosh-skills init --cli codex` 后，在 Codex 里用 `/hooks` 审查并信任该 hook。

初始化 Qwen 启动 hook：

```bash
cosh-skills init --cli qwen
```

## 基本使用

设置本地 skill 仓库路径：

```bash
cosh-skills config set repo_path /path/to/cosh-skills
```

设置目标 skills 路径：

```bash
cosh-skills config set cli.codex.skills_path ~/.codex/skills
cosh-skills config set cli.claude.skills_path ~/.claude/skills
cosh-skills config set cli.qwen.skills_path ~/.qwen/skills
cosh-skills config set cli.openclaw.skills_path ~/.openclaw/skills
cosh-skills config set cli.hermes.skills_path ~/.hermes/skills
```

可选设置安装模式。第一版支持 `auto` 和 `copy`；`cli` 和 `link` 可以写入配置，但 `update` 暂未实现这两种模式。

```bash
cosh-skills config set cli.codex.install_mode copy
cosh-skills config set cli.claude.install_mode auto
cosh-skills config set cli.qwen.install_mode auto
cosh-skills config set cli.openclaw.install_mode auto
cosh-skills config set cli.hermes.install_mode auto
```

查看配置：

```bash
cosh-skills config get
```

更新 skills：

```bash
cosh-skills update --cli codex
cosh-skills update --cli claude
cosh-skills update --cli qwen
cosh-skills update --cli openclaw
cosh-skills update --cli hermes
```

第一次使用时，也可以在 `update` 命令中直接传入 `repo_path`：

```bash
cosh-skills update --cli codex --repo-path /path/to/cosh-skills
```

覆盖同名目标 skill 前先备份：

```bash
cosh-skills update --cli codex --backup
```

运行可选的 CLI 识别校验：

```bash
cosh-skills update --cli codex --verify
```

让 CLI 识别校验失败时阻断本次更新：

```bash
cosh-skills update --cli codex --strict-verify
```

本地 skill 仓库提交领先远程时，确认使用本地提交继续同步：

```bash
cosh-skills update --cli codex --force
```

该参数不会覆盖未提交修改，也不会向远程仓库执行 push。

## Skill 适用 CLI 范围

默认情况下，skill 是通用的。如果 `SKILL.md` 没有声明适用 CLI 范围，`cosh-skills update` 会把它同步到所有支持的目标 CLI。

如果某个 skill 只适用于一个或多个 CLI，可以在该 skill 的 `SKILL.md` front matter 中添加 `cli_scope`：

```markdown
---
name: codex-helper
description: Help Codex workflows.
cli_scope:
  - codex
  - qwen
---
```

更新其他 CLI 时，不包含当前目标 CLI 的 scoped skill 会被预期跳过。更新输出会打印汇总提示，例如：

```text
已跳过 1 个不适用于 codex 的 skill。
```

被跳过的 skill 不会安装、校验，也不会计入该 CLI 的同步数量。`cosh-skills check` 会校验 `cli_scope`；当前支持的值是 `codex`、`claude`、`qwen`、`openclaw` 和 `hermes`。

## 第一版限制

当前版本暂不支持：

- clone skill 仓库
- `--cli all`
- `--branch`
- 只同步单个 skill
- include 或 exclude 过滤
- 官方 CLI 安装器模式
- link 模式
- 自动 stash
- 强制覆盖未提交的本地 git 改动
- 安装到 `cosh/` 子目录

## 开发

运行测试套件：

```bash
python3 -m unittest discover -s tests
```

开发时直接运行 CLI：

```bash
PYTHONPATH=/path/to/cosh-skills python3 -m internal.cli --help
```

检查安装脚本语法：

```bash
bash -n scripts/install.sh
```

当前实现状态见 `docs/development-plan.md`。
