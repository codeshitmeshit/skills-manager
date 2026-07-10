---
name: cosh-before-push
description: 当用户要求 push、推送代码，或要求执行 push 前代码评审、检查未推送 commits、判断代码是否适合推送时使用。只对待推送的本地 commits 运行 Coco、正确性、安全性、注释实现一致性四路独立 CR，输出问题清单和是否同意 push 的代码评审结论；不调用 AIME，不管理具体 Git push 方式，评审通过或用户明确接受风险后由主流程直接执行普通 git push。
---

# Push 前四路代码评审

## 目标

只对待推送的本地 commits 做代码 CR，并输出门禁结论。不要把本 skill 扩展成 Git 推送安全控制器：不管理 push URL、refspec、force、upstream、hook、认证或传输方式。评审结束后立即退出本 skill，将控制权交回主流程；用户已要求或同意推送且评审通过时，主流程直接执行普通 `git push`。

## 必读资源

确定范围后完整读取 [references/review-prompts.md](references/review-prompts.md)。每个 subagent 只接收本路线 prompt、仓库路径、比较基线、HEAD SHA 和 diff 获取命令；不要传入整个 skill、完整 reference、其他路线 prompt 或其他评审意见。

## 工作流

1. 只读检查当前分支、HEAD 和 upstream，确定本地尚未推送的 commit 范围：
   - upstream 存在：使用 `<upstream>..HEAD`。
   - upstream 不存在：使用远端默认主分支作为比较基线；无法可靠识别时要求用户指定评审基线。
2. 计算 `DIFF_BASE=$(git merge-base <BASE_REF> <HEAD_SHA>)`，四路统一审查 `<BASE_REF>..<HEAD_SHA>` 的 commit 列表和 `git diff <DIFF_BASE> <HEAD_SHA>`。
3. 范围为空时输出“无需评审：没有待推送的本地 commits”并结束。未提交、未跟踪内容不属于本次 CR，只在报告中提示。
4. 创建四个相互独立的 Codex subagent：
   - Coco runner：按 `cosh-coco` 规则调用公司内网 Coco；Coco 无效时由该 subagent 使用综合 fallback prompt。
   - Correctness reviewer：检查逻辑、边界、失败路径和兼容性。
   - Security reviewer：检查代码自身的安全性、数据风险和失败关闭。
   - Consistency reviewer：核对注释、文档、命名、用户提示与实现。
5. 主执行者不得直接调用 Coco，不得调用 AIME。受并发槽位限制时分批运行，但必须获得四个独立结果。Coco runner 只向公司内网 Coco 发送本次 CR 的最小必要代码材料；禁止发送到 AIME、互联网服务或其他未授权目标。
6. 每路只读评审真实 diff，禁止修改文件、提交、切换分支或 push。超时、空泛结论、未检查 diff 或执行失败均不算有效结果；Coco 无效时使用 fallback，最终仍不足四路则结论为不同意 push。
7. 主执行者逐条核验、合并和去重意见。证据充分的正确性缺陷、安全/数据风险、明确注释实现不一致为阻断问题；风格偏好、未证实疑点和可选优化为非阻断建议。
8. 输出结论前重新读取 HEAD 和 commit 范围；代码范围变化时旧结论失效，针对最新范围完整重跑四路。
9. 输出统一报告后结束本 skill。不要检查或约束 push URL、remote 配置、refspec、force push、upstream 设置、hook 或实际 push 命令。
10. 用户原始请求包含 push 且结论为“同意 push”或“无需评审”时，主流程直接执行普通 `git push`，不要增加其他推送前检查。结论为不同意时先停下并展示问题；用户随后明确接受风险并同意继续时，主流程同样直接执行普通 `git push`，但不得把它描述为 CR 通过。

## 统一报告

依次输出：

1. `审查范围`：BASE_REF、DIFF_BASE、HEAD_SHA、commit 列表、文件数，以及未提交内容提示。
2. `评审状态`：四个 subagent 的完成状态；Coco runner 标明 Coco 或 fallback。
3. `阻断问题`：严重程度、文件与行号、证据、影响和修复方向；无则写“无”。
4. `非阻断建议`：无则写“无”。
5. `结论`：仅使用“同意 push”“不同意 push：存在阻断问题”“不同意 push：四路评审不完整”“用户接受风险并继续 push”或“无需评审：没有待推送的本地 commits”。

## 质量检查

- 只审查待推送的本地 commits，不评审未提交内容或远端独有 commits。
- 四路由四个独立 Codex subagent 完成；一路使用 Coco，另外三路使用 Codex；完全不调用 AIME。
- 每个 subagent 只收到本路线必要 prompt 和代码范围，没有收到其他路线意见。
- 每一路检查真实 diff；主执行者核验并去重，不以投票覆盖成立问题。
- 结论只反映代码 CR，不代表 Git 推送方式、目标或传输过程已经通过检查。
- skill 本身只输出 CR 结论，不管理 push URL、refspec、force、upstream、hook、认证或传输方式；通过或用户明确覆盖后，主流程直接执行普通 `git push`。
