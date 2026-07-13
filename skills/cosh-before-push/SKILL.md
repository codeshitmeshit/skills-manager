---
name: cosh-before-push
description: 任何即将执行 git push 的请求都必须使用，包括“push”“推送”“推送吧”“直接推”“提交并推送”“同步到远端”等表达；也用于单独要求 push 前 CR、检查未推送 commits、暂存文件或判断代码是否适合推送。必须在 git push 之前完成 Coco 与 Codex 两路独立 CR；优先审查未推送 commits，仅当没有未推送 commit 时审查暂存区文件。完整报告后必须等待用户再次明确确认，禁止自动 push 或先 push 后补评审；不调用 AIME。
---

# Push 前两路代码评审

## 目标

对未推送的本地 commits 做代码 CR；没有未推送 commit 时，改为对暂存区文件做 CR，并输出门禁结论。任何 `git push` 都必须先完成本 skill；不得跳过、静默省略、先 push 后评审，也不得把本 skill 误解为 Git hook、仓库脚本或 bytedcli 流程。不要扩展成 Git 推送安全控制器：不管理 push URL、refspec、force、upstream、hook、认证或传输方式。用户最初提出 push 只授权启动 CR；即使评审通过，也必须在完整报告之后等待用户再次明确确认，不能自动 push。

默认当前任务独占评审期间的工作区。不要考虑其他进程并发创建 commit、切换 HEAD 或修改暂存区的假设场景，也不要为这类场景增加阻断规则。

本 skill 只对门禁结论输出时选定的代码快照负责。结论输出后，用户或主流程再修改文件、改变暂存区或创建 commit，属于评审范围外的用户操作风险；不要追踪、补审或因此阻断当前结论。

## 必读资源

确定范围后完整读取 [references/review-prompts.md](references/review-prompts.md)。每个 subagent 只接收本路线 prompt、仓库路径、`REVIEW_MODE` 及该模式对应的最小范围元数据和 diff 命令；不要传入整个 skill、完整 reference、其他路线 prompt 或其他评审意见。

## 工作流

1. 只读检查当前分支、HEAD 和 upstream，确定本地尚未推送的 commit 范围：
   - upstream 存在：使用 `<upstream>..HEAD`。
   - upstream 不存在：使用远端默认主分支作为比较基线；无法可靠识别时要求用户指定评审基线。
2. 未推送 commit 范围非空时，设置 `REVIEW_MODE=commits`，计算 `DIFF_BASE=$(git merge-base <BASE_REF> <HEAD_SHA>)`，两路统一审查 `<BASE_REF>..<HEAD_SHA>` 的 commit 列表和 `git diff <DIFF_BASE> <HEAD_SHA>`；不要同时纳入暂存区。
3. 未推送 commit 范围为空时检查暂存区：
   - `git diff --cached` 非空：设置 `REVIEW_MODE=staged`，将 `git diff --cached --binary` 输出的 SHA-256 记录为 fingerprint，两路统一审查 `git diff --cached`。
   - 暂存区也为空：输出“无需评审，等待用户最终确认”，并在范围说明中写明没有未推送 commits 或暂存文件，然后结束本轮。
   - 未暂存和未跟踪内容不属于本次 CR，只在报告中提示。
4. 创建两个相互独立的 Codex subagent：
   - Coco runner：按 `cosh-coco` 规则调用公司内网 Coco；Coco 无效时由该 subagent 使用综合 fallback prompt。
   - Codex reviewer：综合检查实现合理性、正确性、安全性、数据风险，以及注释、文档、命名和用户提示与实现的一致性。
5. 主执行者不得直接调用 Coco，不得调用 AIME。必须获得两个独立结果。Coco runner 只向公司内网 Coco 发送本次 CR 的最小必要代码材料；禁止发送到 AIME、互联网服务或其他未授权目标。
6. 每路只读评审真实 diff，禁止修改文件、提交、切换分支或 push。超时、空泛结论、未检查 diff 或执行失败均不算有效结果；Coco 无效时使用 fallback，最终仍不足两路则结论为不同意 push。
7. 主执行者逐条核验、合并和去重意见。证据充分的正确性缺陷、安全/数据风险、明确注释实现不一致为阻断问题；风格偏好、未证实疑点和可选优化为非阻断建议。
8. 输出结论前只复核当前模式的评审对象：commit 模式重新读取 HEAD 和 commit 范围，staged 模式重新计算暂存 diff fingerprint；当前对象变化时旧结论失效并完整重跑。不要因为假设存在并发进程而重新选择模式或扩大范围。
9. 输出统一报告后结束本轮，不执行 push。明确询问用户是否最终确认推送；用户最初的 push 请求不算这次最终确认。不要检查或约束 push URL、remote 配置、refspec、force push、upstream 设置、hook 或实际 push 命令。
10. 只有用户在报告之后另行明确回复“推送”“继续”“同意”等确认，主流程才执行普通 `git push`，不增加其他推送前检查。该回复是同一任务、同一已评审快照的续接状态，视为已经完成本 skill，不得再次触发 CR；其他新的 push 请求仍必须重新触发。
11. 结论为不同意时，用户可以回复“接受上述风险，继续推送”等明确表达来人工覆盖门禁。人工覆盖不等于 Git `--force`，也不得描述为 CR 通过；确认后直接执行普通 `git push`。

## 统一报告

依次输出：

1. `审查范围`：REVIEW_MODE；commit 模式列出 BASE_REF、DIFF_BASE、HEAD_SHA、commits 和文件数，staged 模式列出暂存 diff fingerprint 和暂存文件数；两种模式都提示范围外的未暂存/未跟踪内容。
2. `评审状态`：两个 subagent 的完成状态；Coco runner 标明 Coco 或 fallback。
3. `阻断问题`：严重程度、文件与行号、证据、影响和修复方向；无则写“无”。
4. `非阻断建议`：无则写“无”。
5. `结论`：仅使用“同意 push，等待用户最终确认”“不同意 push：存在阻断问题，等待用户决定是否接受风险”“不同意 push：两路评审不完整，等待用户决定是否接受风险”或“无需评审，等待用户最终确认”。

## 质量检查

- 实际 `git push` 之前已经显式运行本 skill，并在最终回复中展示两路评审状态和门禁结论；不能仅在内部声称已检查。
- 完整报告后已停止并等待用户再次确认；用户最初的 push 请求没有被当成最终确认，也没有在报告同一轮自动 push。
- 报告后的确认作为同一快照的续接状态，没有重复触发 CR；只有新的 push 请求才重新触发。
- 用户可以明确接受问题并人工覆盖门禁；覆盖后执行普通 `git push`，不使用“强制提交”暗示 Git `--force`，也不声称 CR 通过。
- 没有把本 skill 当作 Git hook、项目脚本或其他工具流程，也没有先 push 后补评审。
- 优先审查待推送的本地 commits；仅当没有未推送 commit 时审查暂存区文件。未暂存、未跟踪和远端独有内容不在范围内。
- 两路由两个独立 Codex subagent 完成；一路使用 Coco，一路使用 Codex；完全不调用 AIME。
- 每个 subagent 只收到本路线必要 prompt 和代码范围，没有收到其他路线意见。
- 每一路检查真实 diff；主执行者核验并去重，不以投票覆盖成立问题。
- 结论只反映代码 CR，不代表 Git 推送方式、目标或传输过程已经通过检查。
- 结论只覆盖报告中的代码快照；结论后产生的修改、暂存变化或新 commit 不属于本 skill 的责任范围。
- skill 本身只输出 CR 结论，不管理 push URL、refspec、force、upstream、hook、认证或传输方式；报告后获得用户最终确认，主流程才执行普通 `git push`。
