# cosh-skills 一键更新工具需求文档

## 1. 项目目标

开发一个命令行工具 `cosh-skills`，用于统一管理本地 skill 仓库，并将其中的 skill 安装或更新到不同 CLI 工具中。

第一版暂时支持：

```bash
codex
claude
```

核心流程是：

```text
本地 skill 仓库更新 -> 扫描 repo/skills/ -> 同步到指定 CLI 的 skills 目录
```

用户需要先手动 clone skill 仓库，`cosh-skills` 不负责首次 clone。工具只负责记录本地仓库路径、更新该仓库、同步 skill 到指定 CLI。

---

## 2. 基本使用方式

### 2.1 第一次使用

用户已经手动 clone 好 skill 仓库后，第一次执行：

```bash
cosh-skills update --cli codex --repo-path /path/to/cosh-skills
```

工具会将 `repo_path` 写入配置文件：

```bash
~/.cosh-skills/config.json
```

之后用户可以在任意目录执行：

```bash
cosh-skills update --cli codex
```

---

### 2.2 更新 codex skill

```bash
cosh-skills update --cli codex
```

---

### 2.3 更新 claude skill

```bash
cosh-skills update --cli claude
```

---

### 2.4 覆盖前备份

默认覆盖同名 skill 时不备份。

如果用户需要备份，可以执行：

```bash
cosh-skills update --cli codex --backup
```

备份目录：

```bash
~/.cosh-skills/backups/
```

---

### 2.5 安装后校验

默认进行文件级校验。

可选执行 CLI 识别校验：

```bash
cosh-skills update --cli codex --verify
```

如果希望 CLI 识别校验失败时整体失败：

```bash
cosh-skills update --cli codex --strict-verify
```

---

## 3. 命令设计

## 3.1 update 命令

支持：

```bash
cosh-skills update --cli codex
cosh-skills update --cli claude
cosh-skills update --cli codex --repo-path /path/to/cosh-skills
cosh-skills update --cli codex --backup
cosh-skills update --cli codex --verify
cosh-skills update --cli codex --strict-verify
```

### update 参数

| 参数                | 是否必填 | 说明                            |
| ----------------- | ---- | ----------------------------- |
| `--cli`           | 是    | 目标 CLI，只允许 `codex` 或 `claude` |
| `--repo-path`     | 否    | 设置本地 skill 仓库路径，第一次使用时需要      |
| `--backup`        | 否    | 覆盖已有同名 skill 前进行备份            |
| `--verify`        | 否    | 尝试做 CLI 级识别校验                 |
| `--strict-verify` | 否    | CLI 识别校验失败时整体失败               |

第一版不支持：

```bash
--cli all
--branch
--skill
--install-mode
--skills-path
```

其中 `install_mode` 和 `skills_path` 不允许通过 `update` 临时覆盖，只能通过 `config set` 修改。

---

## 3.2 config 命令

第一版支持：

```bash
cosh-skills config get
cosh-skills config set repo_path /path/to/cosh-skills
cosh-skills config set cli.codex.skills_path ~/.codex/skills
cosh-skills config set cli.claude.skills_path ~/.claude/skills
cosh-skills config set cli.codex.install_mode copy
cosh-skills config set cli.claude.install_mode auto
```

### config set 白名单

只允许设置以下字段：

```text
repo_path
cli.codex.skills_path
cli.claude.skills_path
cli.codex.install_mode
cli.claude.install_mode
```

`install_mode` 只允许：

```text
auto
copy
cli
link
```

如果用户设置非法字段，需要报错并输出可用配置项。

---

## 4. 配置文件设计

配置文件位置：

```bash
~/.cosh-skills/config.json
```

示例结构：

```json
{
  "repo_path": "/home/wo/cosh-skills",
  "last_repo_commit": "abc123",
  "cli": {
    "codex": {
      "install_mode": "auto",
      "skills_path": "~/.codex/skills",
      "last_commit": "abc123",
      "last_updated_at": "2026-06-05 10:30:00",
      "managed_skills": [
        "git-helper",
        "doc-helper"
      ]
    },
    "claude": {
      "install_mode": "auto",
      "skills_path": "~/.claude/skills",
      "last_commit": "abc123",
      "last_updated_at": "2026-06-05 10:31:00",
      "managed_skills": [
        "git-helper",
        "doc-helper"
      ]
    }
  }
}
```

默认配置：

```json
{
  "repo_path": null,
  "last_repo_commit": null,
  "cli": {
    "codex": {
      "install_mode": "auto",
      "skills_path": null,
      "last_commit": null,
      "last_updated_at": null,
      "managed_skills": []
    },
    "claude": {
      "install_mode": "auto",
      "skills_path": null,
      "last_commit": null,
      "last_updated_at": null,
      "managed_skills": []
    }
  }
}
```

---

## 5. skill 仓库结构约定

本地 skill 仓库必须包含：

```bash
repo/
└── skills/
    ├── skill-a/
    │   └── SKILL.md
    ├── skill-b/
    │   └── SKILL.md
    └── skill-c/
        └── SKILL.md
```

源目录固定为：

```bash
{repo_path}/skills/
```

如果 `skills/` 目录不存在，直接报错停止。

不自动创建 `skills/`，也不把仓库根目录当作 skill 目录。

---

## 6. skill 扫描规则

扫描规则：

```text
1. 扫描 repo/skills/ 下的一级目录
2. 如果目录下存在 SKILL.md，则认为是合法 skill
3. 如果目录下没有 SKILL.md，则输出 warning
4. warning 不阻断更新
5. 只同步合法 skill
```

示例：

```bash
repo/skills/
├── git-helper/
│   └── SKILL.md
├── docs-helper/
│   └── SKILL.md
└── assets/
    └── logo.png
```

其中：

```text
git-helper 合法
docs-helper 合法
assets 不合法，警告后跳过
```

---

## 7. Git 更新逻辑

更新时只使用远程默认主分支。

主分支通过 `origin/HEAD` 自动识别，例如：

```text
origin/HEAD -> origin/main
```

不提供 `--branch` 参数。

### Git 更新流程

```text
1. 读取 repo_path
2. 检查 repo_path 是否存在
3. 检查 repo_path 是否是合法 git 仓库
4. 检查工作区是否干净
5. 如果有未提交修改，停止更新
6. 自动识别 origin/HEAD 对应的主分支
7. 如果当前不在主分支，自动切换到主分支
8. git fetch origin
9. 比较本地主分支和远程主分支 commit
10. 如果一致，说明 skill 仓库无新提交
11. 如果不一致，执行 git pull
12. 如果 pull 发生冲突，停止更新
13. 无论 git 是否有新提交，都继续同步到目标 CLI
```

### 本地有未提交修改

如果检测到本地仓库有未提交修改，直接停止：

```text
检测到 skill 仓库存在未提交修改，已停止更新。
请先 commit、stash 或手动处理本地修改后再执行 update。
```

不自动 stash，不自动强制覆盖。

### pull 冲突

如果 `git pull` 发生冲突，直接停止：

```text
git pull 发生冲突，已停止更新。
请进入 skill 仓库手动解决冲突。
```

---

## 8. 安装模式设计

配置项：

```json
"install_mode": "auto"
```

支持枚举：

```text
auto
copy
cli
link
```

第一版实际支持：

```text
auto
copy
```

第一版暂不实现：

```text
cli
link
```

---

## 8.1 auto 模式

第一版 `auto` 等同于 `copy`，但要求已经配置对应 CLI 的 `skills_path`。

如果没有配置 `skills_path`，停止并提示用户：

```text
当前 CLI 未配置 skills_path，无法安装 skill。

请执行：
cosh-skills config set cli.codex.skills_path ~/.codex/skills

或：
cosh-skills config set cli.claude.skills_path ~/.claude/skills
```

---

## 8.2 copy 模式

copy 模式会将每个合法 skill 复制到：

```bash
{skills_path}/{skill-name}/
```

例如：

```bash
repo/skills/git-helper/
```

同步到：

```bash
~/.codex/skills/git-helper/
```

或者：

```bash
~/.claude/skills/git-helper/
```

不使用 `cosh/` 这类子目录，因为不能保证 Codex 或 Claude 一定会识别嵌套目录。

---

## 8.3 cli 模式

第一版保留配置项，但暂不实现。

如果用户设置：

```bash
cosh-skills config set cli.codex.install_mode cli
```

再执行：

```bash
cosh-skills update --cli codex
```

提示：

```text
当前版本暂未实现 cli 安装模式，请先使用 auto 或 copy。
```

---

## 8.4 link 模式

第一版保留配置项，但暂不实现。

如果用户设置：

```bash
cosh-skills config set cli.codex.install_mode link
```

再执行 update，提示：

```text
当前版本暂未实现 link 安装模式，请先使用 auto 或 copy。
```

---

## 9. 复制策略

复制时优先使用 `rsync`。

如果系统存在 `rsync`：

```bash
rsync -a --delete source/ target/
```

如果系统不存在 `rsync`，降级为程序内置复制逻辑。

注意：不能对整个 `skills_path` 执行 `--delete`。

错误示例：

```bash
rsync -a --delete repo/skills/ ~/.codex/skills/
```

这个可能误删用户自己的 skill。

正确策略是：

```text
对每个合法 skill 单独同步：
repo/skills/git-helper/ -> skills_path/git-helper/
repo/skills/doc-helper/ -> skills_path/doc-helper/
```

---

## 10. 同名 skill 处理

如果目标 CLI 的 `skills_path` 中已经存在同名 skill，默认覆盖。

例如：

```bash
~/.codex/skills/git-helper/
```

会被：

```bash
repo/skills/git-helper/
```

覆盖。

默认不备份。

如果用户加了：

```bash
--backup
```

则覆盖前备份到：

```bash
~/.cosh-skills/backups/{cli}/{skill-name}/{timestamp}/
```

示例：

```bash
~/.cosh-skills/backups/codex/git-helper/20260605-103000/
```

---

## 11. managed_skills 管理规则

工具需要记录自己管理过的 skill。

记录位置：

```bash
~/.cosh-skills/config.json
```

字段：

```json
"managed_skills": [
  "git-helper",
  "doc-helper"
]
```

同步完成后，将当前成功同步的合法 skill 写入 `managed_skills`。

---

## 12. 删除废弃 skill

如果某个 skill 上次由 `cosh-skills` 安装过，但这次仓库中已经不存在，则认为它是废弃 skill。

删除规则：

```text
1. 只删除 managed_skills 中记录过的 skill
2. 如果该 skill 当前已经不在 repo/skills/ 中，则删除 skills_path/{skill-name}
3. 删除时不备份
4. 不删除用户自己放在 skills_path 中的其他 skill
```

示例：

上次记录：

```text
git-helper
doc-helper
test-helper
```

当前仓库只有：

```text
git-helper
doc-helper
```

则删除：

```bash
skills_path/test-helper/
```

但不会处理：

```bash
skills_path/other-helper/
```

因为它不在 `managed_skills` 中。

---

## 13. 安装后校验

第一版至少做文件级校验。

校验规则：

```text
1. 检查每个合法 skill 是否已经安装到 skills_path/{skill-name}/
2. 检查 skills_path/{skill-name}/SKILL.md 是否存在
3. 如果缺失，认为同步失败
```

如果用户使用：

```bash
--verify
```

则尝试做 CLI 识别校验。

第一版 CLI 识别校验可以先作为预留能力，如果暂时不能可靠识别，则输出提示，不阻断。

如果用户使用：

```bash
--strict-verify
```

则 CLI 识别校验失败时整体失败。

---

## 14. 日志输出风格

第一版使用步骤式日志，便于用户理解当前执行到哪里。

示例：

```text
[1/6] 读取配置...
[2/6] 检查 skill 仓库...
[3/6] 更新 skill 仓库...
[4/6] 扫描合法 skill...
[5/6] 同步到 codex...
[6/6] 校验安装结果...

完成：已同步 5 个 skill 到 codex。
```

建议普通输出保持简洁。

后续可以扩展：

```bash
--verbose
```

但第一版不是必须。

---

## 15. 错误处理要求

### 15.1 未配置 repo_path

如果用户没有传 `--repo-path`，配置里也没有 `repo_path`，报错：

```text
未配置 skill 仓库路径。

第一次使用请执行：
cosh-skills update --cli codex --repo-path /path/to/cosh-skills

或者：
cosh-skills config set repo_path /path/to/cosh-skills
```

---

### 15.2 未配置 skills_path

如果当前 CLI 没有配置 `skills_path`，报错：

```text
未配置 codex 的 skills_path，无法安装 skill。

请执行：
cosh-skills config set cli.codex.skills_path ~/.codex/skills
```

---

### 15.3 不支持的 CLI

如果用户执行：

```bash
cosh-skills update --cli all
```

或其他未知 CLI，报错：

```text
当前版本只支持：
- codex
- claude

暂不支持：
- all
```

---

### 15.4 skills 目录不存在

如果：

```bash
{repo_path}/skills/
```

不存在，报错：

```text
未找到 skills 目录，当前仓库结构不符合要求。

期望路径：
  /path/to/cosh-skills/skills/

请确认 repo_path 是否正确，或检查 skill 仓库结构。
```

---

### 15.5 非法 install_mode

如果配置为非法值，报错：

```text
非法 install_mode：xxx

允许值：
- auto
- copy
- cli
- link
```

---

## 16. 第一版不做的内容

第一版明确不做：

```text
1. 不负责 clone 远程仓库
2. 不支持 --cli all
3. 不支持指定分支
4. 不支持只同步某个 skill
5. 不支持 include / exclude
6. 不实现真实 CLI 官方安装器
7. 不实现 link 模式
8. 不自动 stash 本地修改
9. 不强制覆盖 git 仓库本地修改
10. 不把 skill 安装到 cosh/ 子目录
```

---

## 17. 最终更新流程总览

```text
用户执行：
cosh-skills update --cli codex

执行流程：
1. 读取 ~/.cosh-skills/config.json
2. 校验 --cli 是否为 codex 或 claude
3. 获取 repo_path
4. 检查 repo_path 是否存在
5. 检查 repo_path 是否为 git 仓库
6. 检查工作区是否干净
7. 识别 origin/HEAD 对应的主分支
8. 当前不在主分支时自动切换
9. git fetch origin
10. 判断本地与远程 commit 是否一致
11. 如有更新，执行 git pull
12. 如无更新，继续同步
13. 检查 repo/skills/ 是否存在
14. 扫描 repo/skills/ 下合法 skill
15. 跳过并警告无 SKILL.md 的目录
16. 检查当前 CLI 的 install_mode
17. auto/copy 模式下检查 skills_path
18. 将合法 skill 同步到 skills_path/skill-name/
19. 如有 --backup，覆盖前备份同名 skill
20. 删除 managed_skills 中已经从仓库移除的废弃 skill
21. 做文件级校验
22. 如有 --verify，尝试 CLI 识别校验
23. 更新 config.json 中的 last_commit、last_updated_at、managed_skills
24. 输出完成结果
```

---

## 18. 第一版实现建议

如果你准备快速落地，我建议用 **Python** 写第一版。

原因：

```text
1. 处理 JSON 配置简单
2. 调用 git / rsync 方便
3. 跨平台能力比 shell 好
4. 目录复制、备份、校验逻辑更容易维护
5. 后续扩展 codex / claude adapter 更自然
```

推荐文件结构：

```bash
cosh-skills/
├── cosh_skills/
│   ├── __init__.py
│   ├── cli.py
│   ├── config.py
│   ├── git_ops.py
│   ├── scanner.py
│   ├── installer.py
│   ├── verifier.py
│   └── utils.py
├── pyproject.toml
└── README.md
```

CLI 入口：

```bash
cosh-skills
```

内部模块职责：

```text
cli.py          解析命令行参数
config.py       读取、写入、校验 config.json
git_ops.py      处理 git 检查、fetch、pull、切分支
scanner.py      扫描 repo/skills/ 下的合法 skill
installer.py    执行 copy 安装、废弃 skill 删除、备份
verifier.py     文件级校验和 CLI 级校验预留
utils.py        路径展开、日志输出、命令执行工具
```

