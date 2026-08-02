# 通用能力同步基线

- 通用 skill：`skills/cosh-requirement-review-planner/`
- 字节 skill：`skills/cosh-byted-openspec-review-planner/`
- 初始共同基线 commit：`04fc6bd`

通用能力包括 OpenSpec 状态、CodeGraph/源码分析、修改点、Design、Tasks、实时网站、自然语言控制和通用代码规范。修改这些能力时，先在通用 skill 中形成通用实现和测试，再同步共享文件到字节 skill；不得只在字节版修复通用缺陷。

字节专属能力只放在字节 skill 的独立章节或 `byted-*.md` references 中，包括并行稳定性/安全性/可行性三路评审、字节最小修改策略和强制远程 UT。同步通用文件时不得覆盖这些专属入口。

每次同步后比较两版共享 assets、scripts 和非 `byted-*` references；差异必须有明确的字节专属理由，并由测试固定。
