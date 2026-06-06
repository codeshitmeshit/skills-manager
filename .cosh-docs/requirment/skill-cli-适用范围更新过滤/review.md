# Skill CLI 适用范围更新过滤评审

## 评审结论

暂无阻塞性产品或技术问题，可以进入 checklist 确认阶段。

本需求边界清楚：维护者通过 skill 元数据声明适用 CLI 范围；更新指定 CLI 时，只处理通用 skill 和适用于当前 CLI 的 skill；其他 skill 被跳过并汇总提示。

## 产品评审

### 清晰点

- 目标用户明确：主要是 skill 维护者。
- 默认行为明确：未声明适用范围的 skill 为通用，兼容历史数据。
- 用户体验明确：跳过不适用 skill 是预期过滤，使用汇总提示。
- 规则边界明确：显式指定不适用 skill 时也跳过。

### 产品风险

- “独有”一词容易和“多个 CLI 适用”冲突。建议对外命名为“适用 CLI 范围”。
- 汇总提示如果只显示数量，排查时可能不够。建议默认输出数量和原因，必要时可以在后续版本补充详细模式。
- 如果未来新增 CLI，旧的已声明范围不会自动包含新 CLI，这是合理行为，但需要文档说明。

## 技术评审

### 现状观察

- `internal/scanner.py` 当前只返回 `Skill(name, path)`，不读取 `SKILL.md` front matter。
- `internal/update.py` 当前把 `scan_result.skills` 原样传给安装和校验。
- `internal/installer.py` 会把当前传入的 skill 名称写入 `managed_skills`，并移除不在当前集合里的历史托管 skill。
- `internal/verifier.py` 会校验传入 skill 都已安装到目标 CLI。
- `internal/skill_check.py` 当前有简单 front matter 解析，但只支持单行 key/value，不支持 YAML list。

### 关键技术要求

- 需要为 skill 增加可读取的适用 CLI 元数据，例如产品语义为 `适用 CLI 范围`。具体字段命名可在实现中确定，但必须能表达多个 CLI。
- 元数据解析需要支持“未声明”和“显式列表”两类状态。未声明表示通用。
- 更新流程应先扫描所有 skill，再得到“适用于当前 CLI”的 skill 列表和“因 CLI 范围跳过”的 skill 列表。
- 安装、校验、`managed_skills` 写入、过期托管 skill 清理都必须使用过滤后的 skill 列表。
- 跳过汇总应在更新输出中出现，且不计入失败。
- 严格校验失败时，不应写入成功状态；这条现有行为需要保持。

### 兼容性

- 旧 `SKILL.md` 未声明适用范围时继续通过检查并参与所有 CLI 更新。
- 已有 `managed_skills` 配置需要谨慎处理：如果某 skill 过去被当前 CLI 托管，但现在声明不适用于当前 CLI，本次更新后应从当前 CLI 的托管集合移除，并清理已安装副本。这符合“不再由当前 CLI 更新”的目标。
- 如果某 skill 元数据声明了未知 CLI，建议标准检查报错或至少给出明确错误，避免维护者误拼写后导致所有目标 CLI 都跳过。

### 测试可行性

现有测试结构适合补充以下测试：

- scanner 或新 metadata 解析单测。
- update flow 中通用 skill 与限定 CLI skill 的过滤测试。
- `managed_skills` 清理测试。
- 输出汇总提示测试。
- skill 标准检查中适用 CLI 字段合法性测试。

## 建议方案边界

- 保持默认通用，不迁移旧 skill。
- 过滤逻辑尽量集中在更新流程或清晰的 helper 中，避免安装、校验、清理各自重复判断。
- 对外文案使用“已跳过不适用于当前 CLI 的 skill”，避免“未更新”造成失败感。

## 阻塞项

无。
