---
name: cosh-before-push
description: 当用户要求 push、推送、上传当前分支代码到远端，或要求执行 push 前代码评审、检查未推送 commits、判断代码是否可以推送时使用。必须在真实 git push 前创建四个 Codex subagent，分别承担 Coco runner、正确性、安全性、注释实现一致性四路独立 CR，并输出带问题清单的推送门禁结论；不调用 AIME，评审未通过时不得自动推送。
---

# Push 前四路代码评审

## 目标

在执行真实 `git push` 前，对待推送 commits 建立短时、可复核的四路独立代码评审门禁。评审只读取隔离材料，不修改原仓库。四路不完整、范围变化或存在经核验成立的阻断问题时，不得 push。用户可以明确接受风险后覆盖普通阻断，但不得把覆盖描述为“评审通过”。

## 必读资源

确定范围后完整读取 [references/review-prompts.md](references/review-prompts.md)。每个 subagent 只接收本路线 prompt、必要元数据和隔离评审材料路径；不要传入整个 skill、完整 reference、其他路线 prompt 或其他评审意见。

## 工作流

1. 检查仓库、当前分支、工作区、远端和 upstream。记录 `HEAD_SHA`，解析用户指定的目标 remote/branch；未指定时沿用 upstream，没有 upstream 时使用 `origin` 和当前分支同名目标。仍有歧义时停止并询问。
2. fetch 目标 remote，记录目标 remote URL、目标 ref 是否存在及其 `REMOTE_SHA`。fetch 失败时不得给出同意结论。
3. 确定评审范围：
   - 目标已存在：`BASE_REF=<remote>/<target>`。
   - 目标不存在：使用该 remote 的默认主分支；无法识别时要求用户指定。
   - 计算 `DIFF_BASE=$(git merge-base <BASE_REF> <HEAD_SHA>)`。
   - commit 范围使用 `<BASE_REF>..<HEAD_SHA>`，代码 diff 使用 `git diff <DIFF_BASE> <HEAD_SHA>`。
4. 若用户明确要求覆盖远端历史，额外列出 `<HEAD_SHA>..<BASE_REF>` 的远端独有 commits，并生成 `git diff <BASE_REF> <HEAD_SHA>` 展示覆盖后的净变化；这两部分都属于四路必审材料。用户在普通评审后才提出强推时，旧结论立即失效并按扩展范围重跑。
5. 列出 commit、变更文件和 diff。范围为空时不运行空评审。提示未提交和未跟踪内容不属于本次 push；不得擅自提交。
6. 先在本地扫描待审 diff 中疑似凭据、token、私钥和客户数据；发现疑似敏感内容时失败关闭，不把原文交给评审 subagent。确认无敏感内容后，创建不含 `.git` 的临时评审材料目录：导出 `HEAD_SHA` 的已提交文件快照，并放入 commit 列表、变更文件、待审 diff；强推场景再放入远端独有 commit 列表和覆盖净 diff。材料只包含 CR 必要内容，不包含未提交、ignored 文件或整个 skill 指令。四路只能访问该目录，不得访问原仓库路径。
7. 创建四个相互独立的 Codex subagent：
   - Coco runner：在隔离目录中按 `cosh-coco` 安全规则调用 Coco；Coco 无效时由该 subagent 使用综合 fallback prompt 评审。
   - Correctness reviewer：检查逻辑、边界、失败路径和兼容性。
   - Security reviewer：检查安全边界、数据风险、竞态和失败关闭。
   - Consistency reviewer：专门核对注释、文档、命名、用户提示与实际实现。
8. 主执行者不得直接调用 Coco，不得调用 AIME。受并发槽位限制时分批运行，但必须获得四个独立 subagent 的有效结果。Coco runner 可以把最小必要评审材料发送给公司内网 Coco；除此之外，所有路线都禁止向 AIME、互联网服务或其他未授权目标发送代码。每路禁止修改材料、提交、切换分支或 push。
9. 收集结果。超时、空泛结论、未检查实际 diff 或修改材料均视为无效；Coco 路线 fallback 后仍无效，或任一路缺失时，不同意 push。完成后删除临时材料目录。
10. 主执行者在原仓库只读核验每条意见，合并重复项。证据充分的缺陷、安全/数据风险、明确注释实现不一致为阻断问题；风格偏好、未证实疑点和可选优化为非阻断建议。
11. push 前再次 fetch，并验证 `HEAD_SHA`、待推送 commit 集合、目标 remote URL、目标 ref 存在状态及 `REMOTE_SHA` 都与评审时一致；任何变化都使结论失效并触发完整重评。
12. 使用已评审的不可变 SHA 和明确 refspec：`git push <remote> <HEAD_SHA>:refs/heads/<target>`。不得使用可变化的 `HEAD`，不得依赖 `push.default`，始终禁止裸 `--force`。
13. 用户明确要求覆盖历史且扩展范围已通过四路评审时，只允许 `--force-with-lease=refs/heads/<target>:<reviewed-remote-sha>`；lease 失败即停止，不得改用裸 force 或自动接受新 SHA。
14. 固定 SHA push 成功后，如首次创建分支且需要 upstream，先 fetch，再单独执行 `git branch --set-upstream-to=<remote>/<target> <local-branch>`；不得把 `-u` 与裸 commit SHA refspec 混用。
15. 根据真实命令结果报告推送成功或失败。失败时保留错误，不得把批准或覆盖描述为已经推送。

## 统一报告

依次输出：

1. `审查范围`：目标 remote/branch、BASE_REF、DIFF_BASE、HEAD_SHA、REMOTE_SHA、commits、文件数和工作区提示；强推时列出将删除的远端独有 commits。
2. `评审状态`：四个 subagent 的完成状态；Coco runner 标明 Coco 或 fallback。
3. `阻断问题`：严重程度、文件与行号、证据、影响和修复方向；无则写“无”。
4. `非阻断建议`：无则写“无”。
5. `结论`：仅使用“同意 push”“不同意 push：存在阻断问题”“不同意 push：四路评审不完整”或“用户已覆盖门禁，准备推送”。

## 质量检查

- 四路由四个独立 Codex subagent 完成；只由 Coco runner 调用 Coco，完全不调用 AIME。
- 只允许 Coco runner 向公司内网 Coco 发送最小必要材料；禁止发送到 AIME、互联网服务或其他未授权目标。
- subagent 只能看到隔离材料和本路线 prompt，不能访问原仓库、`.git`、其他 prompt 或意见。
- 普通 push 审查本地新增 commits；强推还审查将删除的远端 commits 与覆盖净变化。
- 每一路检查真实 diff；主执行者核验并去重，不以投票覆盖成立问题。
- push 前 HEAD、commit 范围、remote URL 和远端 SHA 未变化。
- push 使用不可变 HEAD SHA 和明确 refspec；历史覆盖只使用绑定评审 SHA 的 force-with-lease。
