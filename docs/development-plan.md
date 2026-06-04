# cosh-skills 开发计划

本文档以 `docs/test-plan.md` 为准，按测试先行方式推进。每个阶段先提交测试，再提交让测试通过的最小实现。

## 阶段 0：项目骨架

- [x] 建立 Python 包结构：`cosh_skills/`
- [x] 建立 CLI 入口：`cosh-skills`
- [x] 建立测试目录和测试运行命令
- [x] 明确测试隔离策略：所有 home/config/skills/repo 路径都使用临时目录
- [x] 建立基础异常类型和统一退出码处理
- [x] 明确一键安装脚本入口位置，例如 `scripts/install.sh`

交付标准：

- [x] 空命令或 help 命令可以运行
- [x] 测试框架可以执行

## 阶段 1：一键安装脚本

先写测试：

- [x] 安装脚本不要求任何参数即可执行
- [x] 安装脚本会安装项目所需 Python 依赖
- [x] 安装脚本不会要求用户提供 `repo_path`、`cli`、`skills_path` 等业务参数
- [x] 安装脚本输出 zsh alias 提示，指向当前项目的 CLI 入口
- [x] 安装脚本输出 bash alias 提示，指向当前项目的 CLI 入口
- [x] 安装脚本不自动修改 `~/.zshrc` 或 `~/.bashrc`
- [x] 安装脚本重复执行不会破坏已有环境

再实现：

- [x] 新增 `scripts/install.sh`
- [x] 检查 Python 和 pip 是否可用
- [x] 安装 Python 包和依赖，优先使用 `python -m pip install -e .`
- [x] 输出可复制的 alias 示例：
  - `alias cosh-skills='python -m cosh_skills.cli'`
  - 或指向安装后的 `cosh-skills` 可执行入口
- [x] 提示用户根据当前 shell 选择写入 `~/.zshrc` 或 `~/.bashrc`
- [x] 保持脚本无业务参数，业务配置仍通过 `cosh-skills config set ...` 或 `cosh-skills update ...` 完成

交付标准：

- [x] 用户执行一次安装脚本后，可以按提示配置 alias
- [x] 重新打开 shell 或 source rc 文件后，`cosh-skills --help` 可以运行

## 阶段 2：配置模块

先写测试：

- [x] 默认配置结构
- [x] 配置文件读写
- [x] `config get`
- [x] `config set` 白名单
- [x] `install_mode` 枚举校验

再实现：

- [x] `cosh_skills/config.py`
- [x] 配置路径解析，默认使用 `~/.cosh-skills/config.json`
- [x] 默认配置合并，避免旧配置缺字段
- [x] 白名单字段 set 逻辑

## 阶段 3：CLI 参数解析

先写测试：

- [x] `update --cli codex`
- [x] `update --cli claude`
- [x] 不支持 CLI 报错
- [x] 第一版不支持参数不被接受
- [x] `--repo-path`、`--backup`、`--verify`、`--strict-verify`

再实现：

- [x] `cosh_skills/cli.py`
- [x] `update` 命令参数解析
- [x] `config get/set` 命令参数解析
- [x] 错误信息与退出码

## 阶段 4：repo 与 Git 检查

先写测试：

- [x] `repo_path` 缺失
- [x] `repo_path` 不存在
- [x] 非 git 仓库
- [x] 工作区不干净
- [x] `origin/HEAD` 默认分支识别
- [x] fetch、pull、切换主分支行为
- [x] pull 冲突失败

再实现：

- [x] `cosh_skills/git_ops.py`
- [x] repo 存在性检查
- [x] git 仓库检查
- [x] 工作区干净检查
- [x] 默认主分支识别
- [x] fetch / compare / pull 流程

## 阶段 5：skill 扫描

先写测试：

- [x] `skills/` 缺失时报错
- [x] 只扫描一级目录
- [x] 只接受包含 `SKILL.md` 的目录
- [x] 无 `SKILL.md` 的目录 warning 后跳过
- [x] 普通文件和嵌套目录不被当作 skill

再实现：

- [x] `cosh_skills/scanner.py`
- [x] skill 数据结构
- [x] warning 收集和输出

## 阶段 6：copy 安装与备份

先写测试：

- [x] `auto` 等同 `copy`
- [x] 未配置 `skills_path` 失败
- [x] 合法 skill 复制到 `{skills_path}/{skill-name}/`
- [x] 同名 skill 默认覆盖
- [x] 只对单个 skill 做 delete
- [x] `--backup` 覆盖前备份
- [x] `cli` / `link` 模式提示暂未实现

再实现：

- [x] `cosh_skills/installer.py`
- [x] skills_path 检查
- [x] copy 同步逻辑
- [x] rsync 可用性检测和调用
- [x] 内置复制降级逻辑
- [x] 备份逻辑

## 阶段 7：managed_skills 与废弃删除

先写测试：

- [x] 同步成功后写入当前合法 skill
- [x] 删除上次 managed、本次不存在的 skill
- [x] 不删除用户自己的 skill
- [x] 废弃删除不备份
- [x] codex 和 claude 的 managed 状态互不影响

再实现：

- [x] 根据当前合法 skill 更新 `managed_skills`
- [x] 根据旧 `managed_skills` 计算废弃 skill
- [x] 删除废弃目标目录
- [x] 成功后持久化配置

## 阶段 8：安装后校验

先写测试：

- [x] 默认文件级校验
- [x] 缺少 skill 目录时报错
- [x] 缺少 `SKILL.md` 时报错
- [x] `--verify` 失败不阻断
- [x] `--strict-verify` 失败阻断

再实现：

- [x] `cosh_skills/verifier.py`
- [x] 文件级校验
- [x] CLI 级校验预留接口
- [x] strict verify 行为

## 阶段 9：update 总流程集成

先写测试：

- [x] 无 git 更新时仍继续同步
- [x] 有 git 更新时 pull 后同步
- [x] 同步成功后更新 `last_repo_commit`
- [x] 同步成功后更新目标 CLI 的 `last_commit`
- [x] 同步成功后更新 `last_updated_at`
- [x] 失败时不写入成功状态
- [x] 输出步骤式日志

再实现：

- [x] 串联 config、git_ops、scanner、installer、verifier
- [x] 统一日志步骤
- [x] 统一错误处理
- [x] 完成结果输出

## 阶段 10：验收与文档

- [x] 全量测试通过
- [x] 补充 README 基本使用方式
- [x] 补充一键安装脚本使用方式
- [x] 补充 zsh/bash alias 配置示例
- [x] 补充本地开发和测试命令
- [x] 用临时 repo 做一次端到端手动验收
- [x] 检查第一版明确不做的能力没有被误实现
