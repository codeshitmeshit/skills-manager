# cosh-skills

English: [README.md](README.md)

`cosh-skills` 是一个命令行工具，用于管理本地 skill 仓库，并将其中的 skill 同步到支持的 CLI 工具中。

第一版支持的目标 CLI：

- `codex`
- `claude`

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

该脚本会以 editable 模式安装 Python 包和依赖。它不会询问 `repo_path`、`cli`、`skills_path` 等业务参数。

安装后，为你的 shell 添加 alias。

如果使用 zsh，将下面内容加入 `~/.zshrc`：

```bash
alias cosh-skills='python3 -m internal.cli'
```

如果使用 bash，将下面内容加入 `~/.bashrc`：

```bash
alias cosh-skills='python3 -m internal.cli'
```

重新加载 shell 配置：

```bash
source ~/.zshrc
```

或：

```bash
source ~/.bashrc
```

验证安装：

```bash
cosh-skills --help
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
```

可选设置安装模式。第一版支持 `auto` 和 `copy`；`cli` 和 `link` 可以写入配置，但 `update` 暂未实现这两种模式。

```bash
cosh-skills config set cli.codex.install_mode copy
cosh-skills config set cli.claude.install_mode auto
```

查看配置：

```bash
cosh-skills config get
```

更新 skills：

```bash
cosh-skills update --cli codex
cosh-skills update --cli claude
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
- 强制覆盖本地 git 改动
- 安装到 `cosh/` 子目录

## 开发

运行测试套件：

```bash
python3 -m unittest discover -s tests
```

开发时直接运行 CLI：

```bash
python3 -m internal.cli --help
```

检查安装脚本语法：

```bash
bash -n scripts/install.sh
```

当前实现状态见 `docs/development-plan.md`。
