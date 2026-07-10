---
name: cosh-before-push
description: 当用户要求 push、推送、上传当前分支代码到远端，或要求执行 push 前代码评审、检查未推送 commits、判断代码是否可以推送时使用。必须在真实 git push 前对待推送的本地 commits 完成 Coco、AIME 和两路 Codex subagent 四路独立 CR，检查实现合理性、安全性、注释与实现一致性，并输出带问题清单的推送门禁结论；评审未通过时不得自动推送。
---

# Push 前四路代码评审

## 目标

在执行任何真实 `git push` 前，对本次待推送 commits 建立可复核的四路独立代码评审门禁。只评审并报告，不修改代码。除非四路评审完整、待推送范围未变化且结论为同意，否则不得执行 push；用户可以明确接受风险后覆盖阻断，但不得把覆盖描述为“评审通过”。

## 必读资源

确定待评审范围后，完整读取 [references/review-prompts.md](references/review-prompts.md)，把其中对应 prompt 分别交给四路评审者。不要让评审者共享彼此的意见。

## 工作流

1. 检查 Git 仓库、当前分支、工作区状态、远端和 upstream。记录开始评审时的 `HEAD`，解析用户本次指定的目标 remote 和目标 branch。用户未指定目标时才沿用 upstream；没有 upstream 时使用 `origin` 和当前分支同名目标。目标仍有歧义时停止询问，不得猜测。
2. 在不改变工作树的前提下 fetch 目标 remote，记录目标 remote-tracking ref 的 SHA。fetch 失败时不得使用可能过期的引用给出“同意 push”结论。
3. 确定比较基线和待推送范围：
   - 目标 remote branch 已存在：使用该目标 remote-tracking ref 作为基线，而不是无条件使用当前 upstream。
   - 目标 remote branch 不存在：识别该 remote 的默认主分支，使用 `<remote-default>..HEAD`。
   - 无法可靠识别默认主分支：停止并要求用户指定基线，不得猜测。
   - commit 范围统一使用 `<base>..HEAD`，代码 diff 统一使用 `git diff <base> <HEAD_SHA>`；四路不得混用三点 diff。
4. 列出待推送 commit、文件和完整 diff。范围为空时说明没有本地 commit 需要推送，不运行空评审，也不声称已 push。
5. 检查未提交和未跟踪内容。它们不属于本次 CR 范围，但必须在报告中提示不会随本次 commit push；不得擅自提交或纳入评审。
6. 启动四路相互独立的只读评审：
   - Coco：按 `cosh-coco` 的安全调用规则在当前仓库运行 Coco 评审。
   - AIME：按 `cosh-aime` 的调用规则发送 AIME 评审并等待完整结果。
   - Codex correctness subagent：侧重正确性、边界条件和注释一致性。
   - Codex security subagent：侧重安全性、数据边界和失败处理。
7. Coco 不存在或无法产出有效评审时，用 `fallback-correctness` Codex subagent 替代；AIME 不存在、鉴权失败或无法产出有效评审时，用 `fallback-security` Codex subagent 替代。不得用同一份 prompt 替代两路，也不得减少到少于四路有效意见。
8. 并行执行可并行的评审；受并发槽位限制时分批执行。每一路只获得仓库路径、基线、commit 范围、diff 与自己的 prompt，不得获得其他评审结论。明确要求只读，禁止修改文件、提交、push 或执行破坏性命令。
9. 收集四路结果。超时、空泛结论、未检查实际 diff 或执行失败均不算有效评审；尝试对应降级后仍不足四路时，结论必须为不同意 push。
10. 主执行者逐条核验意见，定位到实际 diff 和仓库上下文，合并重复问题并纠正误报。只有证据充分的缺陷、安全风险或注释与实现明确不一致才是阻断问题；纯风格偏好、未证实疑点和优化建议放入非阻断建议。
11. 输出统一报告前重新读取 `HEAD` 和待推送 commit 集合。只要范围发生变化，旧结论立即失效，必须对最新范围重新执行完整四路评审。
12. 存在任一经核验成立的阻断问题，或四路评审不完整时，结论为不同意 push，不得执行 `git push`。
13. 用户修复代码后，必须重新执行全部四路评审，不得只复查旧问题。
14. 用户明确要求接受列出的风险并继续时，将状态标记为“用户已覆盖门禁，准备推送”，保留未解决问题，不得改写为“CR 通过”。用户未明确覆盖时不要反复询问，直接停在评审报告。
15. 真正 push 前再次 fetch 目标 remote，并验证 `HEAD`、待推送 commit 集合和目标 remote branch SHA 均与评审时一致；任一变化都使结论失效并触发完整重评。使用明确 refspec 推送已评审的 HEAD，例如 `git push <remote> HEAD:refs/heads/<target>`；首次创建目标分支且需要跟踪时才加 `-u`。不得根据 `push.default` 隐式改变目标，不得自行使用 force push。
16. push 完成后根据真实命令结果报告“推送成功”或“推送失败”。失败时保留错误，不得把已批准或已覆盖描述成已经推送。

## 统一报告

按以下顺序输出：

1. `审查范围`：目标 remote/branch、基线及其 SHA、HEAD、commit 列表、文件数量，以及未提交内容提示。
2. `评审状态`：Coco、AIME、Codex correctness、Codex security 的成功或降级状态；列明替代关系。
3. `阻断问题`：按严重程度列出文件与行号、证据、影响和建议修复方向；无问题时明确写“无”。
4. `非阻断建议`：只保留有实际价值的建议；无建议时明确写“无”。
5. `结论`：只能使用以下一种：
   - `同意 push：四路评审完整，未发现经核验成立的阻断问题。`
   - `不同意 push：存在阻断问题。`
   - `不同意 push：未获得四路有效评审。`
   - `用户已覆盖门禁，准备推送：以下风险仍未解决。`

push 命令执行后另行报告真实结果，不把门禁结论写成推送结果。

## 质量检查

- 真实 push 前已触发本 skill，且评审对象只包含待推送 commits。
- 四路评审相互独立，Coco/AIME 降级时使用了两份侧重点不同的 prompt。
- 每一路都检查了真实 diff，没有用空泛总结凑足数量。
- 主执行者核验并去重问题，没有用投票覆盖单路发现的严重问题。
- 评审后 HEAD、commit 范围和目标远端 SHA 均未变化；变化时已完整重跑。
- 任一成立问题都阻断 push；建议和风格偏好不冒充阻断问题。
- 用户覆盖前没有 push；覆盖后没有声称 CR 通过。
- push 使用明确的 remote、目标 branch 和 refspec，没有隐式改变目标或自行 force push。
