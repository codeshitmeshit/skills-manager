# cosh-skills 测试计划

本文档基于 `docs/requiement.md` 整理，遵循测试先行原则。实现前应先确认并补齐这些测试用例。

## 1. CLI 参数与命令入口

- [ ] `cosh-skills update --cli codex` 可被解析
- [ ] `cosh-skills update --cli claude` 可被解析
- [ ] `--cli all` 报错，提示仅支持 `codex` / `claude`
- [ ] 未传 `--cli` 报错
- [ ] `update` 不接受第一版不支持参数：`--branch`、`--skill`、`--install-mode`、`--skills-path`
- [ ] `--verify` 和 `--strict-verify` 可解析
- [ ] `--backup` 可解析

## 2. 配置文件

- [ ] 无配置文件时返回默认配置结构
- [ ] 第一次 `update --repo-path /path` 会写入 `~/.cosh-skills/config.json`
- [ ] `config get` 输出当前配置
- [ ] `config set repo_path /path/to/repo` 成功
- [ ] `config set cli.codex.skills_path ~/.codex/skills` 成功
- [ ] `config set cli.claude.skills_path ~/.claude/skills` 成功
- [ ] `config set cli.codex.install_mode auto|copy|cli|link` 成功
- [ ] 非白名单配置项报错，并输出可用配置项
- [ ] 非法 `install_mode` 报错，并输出允许值

## 3. repo_path 校验

- [ ] 未传 `--repo-path` 且配置无 `repo_path` 时失败
- [ ] `repo_path` 不存在时失败
- [ ] `repo_path` 不是 git 仓库时失败
- [ ] `{repo_path}/skills/` 不存在时失败
- [ ] 不把 repo 根目录当作 skills 目录

## 4. Git 更新逻辑

- [ ] 工作区干净时允许继续
- [ ] 有未提交修改时停止，不执行同步
- [ ] 可通过 `origin/HEAD` 识别默认主分支
- [ ] 当前不在主分支时切换到主分支
- [ ] `git fetch origin` 被执行
- [ ] 本地与远程 commit 一致时不 pull，但继续同步
- [ ] 本地落后远程时执行 `git pull`
- [ ] `git pull` 冲突时停止，并提示手动解决
- [ ] 不自动 stash
- [ ] 不强制覆盖本地 git 修改

## 5. skill 扫描

- [ ] 只扫描 `{repo_path}/skills/` 下一级目录
- [ ] 有 `SKILL.md` 的目录识别为合法 skill
- [ ] 无 `SKILL.md` 的目录输出 warning
- [ ] 无 `SKILL.md` 的目录不阻断更新
- [ ] 无 `SKILL.md` 的目录不会被同步
- [ ] 普通文件不会被当作 skill
- [ ] 嵌套目录不会被递归当作独立 skill

## 6. 安装模式

- [ ] `auto` 模式第一版等同 `copy`
- [ ] `auto` 模式未配置当前 CLI 的 `skills_path` 时失败
- [ ] `copy` 模式未配置当前 CLI 的 `skills_path` 时失败
- [ ] `cli` 模式 update 时报“暂未实现”
- [ ] `link` 模式 update 时报“暂未实现”
- [ ] 非法 `install_mode` update 时报错

## 7. copy 同步策略

- [ ] 合法 skill 被复制到 `{skills_path}/{skill-name}/`
- [ ] 不安装到 `{skills_path}/cosh/{skill-name}/`
- [ ] 同名 skill 默认覆盖
- [ ] 覆盖单个 skill 时删除目标内源端已不存在的文件
- [ ] 不对整个 `skills_path` 执行 delete，避免删除用户自己的 skill
- [ ] 没有 `rsync` 时使用内置复制逻辑
- [ ] 有 `rsync` 时按单个 skill 执行 `rsync -a --delete source/ target/`

## 8. 备份

- [ ] 默认覆盖同名 skill 不备份
- [ ] `--backup` 时覆盖前备份已有同名 skill
- [ ] 备份路径为 `~/.cosh-skills/backups/{cli}/{skill-name}/{timestamp}/`
- [ ] 只备份将被覆盖的同名 skill
- [ ] 不存在同名目标时不创建无意义备份
- [ ] 删除废弃 skill 时不备份

## 9. managed_skills 与废弃删除

- [ ] 同步成功后写入当前合法 skill 到 `managed_skills`
- [ ] 上次 managed、本次 repo 已不存在的 skill 会从 `skills_path` 删除
- [ ] 只删除 `managed_skills` 中记录过的废弃 skill
- [ ] 不删除用户自己放在 `skills_path` 的其他 skill
- [ ] 删除废弃 skill 后更新 `managed_skills`

## 10. 安装后校验

- [ ] 文件级校验默认执行
- [ ] 检查 `{skills_path}/{skill-name}/` 存在
- [ ] 检查 `{skills_path}/{skill-name}/SKILL.md` 存在
- [ ] 文件级校验失败时 update 失败
- [ ] `--verify` 触发 CLI 识别校验预留逻辑，失败不阻断
- [ ] `--strict-verify` 下 CLI 识别校验失败会导致整体失败

## 11. 配置更新

- [ ] update 成功后更新 `last_repo_commit`
- [ ] update 成功后更新目标 CLI 的 `last_commit`
- [ ] update 成功后更新目标 CLI 的 `last_updated_at`
- [ ] update 失败时不写入误导性的成功状态
- [ ] 同步到 codex 不影响 claude 的 managed 状态，反之亦然

## 12. 日志与错误信息

- [ ] update 输出步骤式日志 `[1/6] ... [6/6]`
- [ ] 成功时输出同步数量和目标 CLI
- [ ] 未配置 `repo_path` 的错误信息包含首次使用提示
- [ ] 未配置 `skills_path` 的错误信息包含对应 CLI 的 config set 命令
- [ ] 不支持 CLI 的错误信息包含支持项和不支持项
- [ ] `skills/` 缺失错误信息包含期望路径
- [ ] warning 不使用失败退出码
- [ ] 真正错误使用非 0 退出码

## 建议执行优先级

第一批优先覆盖配置、扫描、copy 安装、managed 删除、错误处理。

第二批覆盖 Git 更新逻辑，因为需要构造 fixture git repo，测试成本更高。
