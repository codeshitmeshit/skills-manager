# Hammer 集成契约

## 所有权

Hammer 独占 `.hammer/**` 写入、design/review/plan/execute/Gate 状态转换，以及三路评审、上报、远程 UT、CI、最终 CR、E2E、验收和交付证据。本插件只能读取这些产物，不得修补、迁移、格式化或补写 `.hammer` 文件。

Cosh 只在首个 coding task 到达后取得 `scope: full_coding_stage` 的临时所有权。Hammer 在整个编码阶段保持暂停；Cosh 不写 Hammer session、不自行推进 Hammer Gate。每个详细任务的代码 commit 属于 Cosh 编码交付证据，最终验证和交付仍由 Hammer 负责。

## 强依赖与 Dispatch

入口必须定位 Hammer 根目录及 `SKILL.md`。Hammer 缺失时 fail closed，不得退回独立研发流程或复制 Hammer 逻辑。

入口 prompt 要求 Hammer 在每个 coding task 中保留 `Use $cosh-hammer in coding mode for this Hammer parent task.`。该语句由 Hammer 写入 Plan；插件不得修改 `.hammer/plan/plan.md`。`verify-handoff` 校验全部 coding task，`verify-coding` 只在首个 Execute coding dispatch、CodeGraph 前校验入口状态。失败时返回 `BLOCKED`，不得改派普通 coding worker。

## 全局返回

`activate-coding` 必须一次性接收完整 Hammer 父任务顺序及其详细任务映射。任务执行期间不按父任务边界返回 Hammer。每个详细任务通过时由插件提交暂存快照并记录 checkpoint。

全部详细任务通过后，`complete-coding` 只生成一次 `coding-stage-handoff.json`：`status: DONE`、`completed_hammer_tasks`、`task_commits`、`next_action: hammer_continue_after_coding_stage`。Hammer 将列出的 coding task 全部视为已完成，跳过对应原生 worker 并进入编码后 Gate。Cosh 不发明 Hammer 状态。

## Meego 与 Worktree

Meego 为弱绑定：用户绑定时入口透传 Hammer 合法的 `decision: existing`、`source: user` 和规范化 URL，最终全局 handoff 携带同一 ID；跳过不阻塞、不创建事项、不写 `.hammer/execute/meego.md`。

入口默认透传 worktree `decision: skip`、`source: user`；只有用户明确要求隔离时使用 `open`。Stage 1 决策仍由 Hammer 自己维护。

## 兼容与边界

读取 Hammer 时允许展示未知字段，但无法确认关键阶段、Plan SHA、活动目录或当前任务时禁止控制。只有合法 `migrated_away` 事件且目标通过 Git worktree 注册与仓库归属校验后才跟随迁移。

schema v1 单父任务状态只读展示，不自动升级或继续推进；新 work 只生成 schema v2。Skill 不是常驻拦截器；完全绕过 Cosh 的 Hammer Execute 只能由 Hammer 正式 dispatch hook 或统一 launcher 阻止。
