# Skill CLI 适用范围更新过滤 Todolist

## TODO-001 明确并实现 skill 适用 CLI 元数据读取

- 目标：让系统能从 `SKILL.md` front matter 中读取可选的适用 CLI 范围。
- 涉及区域：`internal/scanner.py`、可能的元数据解析 helper、相关测试。
- 输入：现有 `Skill(name, path)` 模型、`SKILL.md` front matter、需求中“未声明默认通用”和“支持多个 CLI”规则。
- 输出：skill 扫描结果可表达“未声明适用范围”和“声明了多个适用 CLI”。
- 依赖：无。
- 完成标准：未声明字段的 skill 被识别为通用；声明多个 CLI 的 skill 可被后续过滤逻辑读取。
- 关联 checklist：CHK-001、CHK-002、CHK-011。

## TODO-002 增加适用 CLI 过滤逻辑

- 目标：根据当前 `cli_name` 把扫描结果拆分为适用 skill 和被跳过 skill。
- 涉及区域：`internal/update.py` 或新的过滤 helper。
- 输入：扫描得到的 skill 列表、当前 CLI 名称。
- 输出：适用于当前 CLI 的 skill 列表、因 CLI 范围不匹配而跳过的 skill 列表。
- 依赖：TODO-001。
- 完成标准：通用 skill 和当前 CLI 范围内 skill 被保留；其他 CLI 专属或不包含当前 CLI 的 skill 被跳过。
- 关联 checklist：CHK-002、CHK-003、CHK-010。

## TODO-003 将过滤后集合贯穿更新流程

- 目标：确保安装、校验、托管清理和配置写入都只使用适用于当前 CLI 的 skill。
- 涉及区域：`internal/update.py`、`internal/installer.py` 调用点、`internal/verifier.py` 调用点。
- 输入：TODO-002 产出的适用 skill 列表。
- 输出：安装、校验、`managed_skills`、过期托管清理均基于过滤后集合。
- 依赖：TODO-002。
- 完成标准：不适用 skill 不安装、不校验、不写入当前 CLI 的 `managed_skills`，历史托管副本按过期规则清理。
- 关联 checklist：CHK-003、CHK-006、CHK-007、CHK-008。

## TODO-004 增加跳过汇总输出和结果统计

- 目标：更新命令输出跳过汇总，并保证同步数量只统计实际安装的 skill。
- 涉及区域：`internal/update.py`、`UpdateResult` 如需扩展。
- 输入：过滤结果中的跳过 skill 列表、安装结果。
- 输出：面向用户的汇总提示和正确的同步数量。
- 依赖：TODO-002、TODO-003。
- 完成标准：输出包含“已跳过不适用于当前 CLI 的 skill”语义；`synced_count` 和完成文案只统计实际同步数量。
- 关联 checklist：CHK-004、CHK-005。

## TODO-005 校验适用 CLI 字段合法性

- 目标：维护者误写未知 CLI 或非法格式时，命令给出明确反馈。
- 涉及区域：`internal/skill_check.py`、可能复用的元数据解析 helper、相关测试。
- 输入：`SKILL.md` front matter 中的适用 CLI 字段、当前支持的 CLI 列表。
- 输出：标准检查结果中的明确错误或警告。
- 依赖：TODO-001。
- 完成标准：未知 CLI、空列表或非法格式能被检查发现；旧 skill 缺少字段不报错。
- 关联 checklist：CHK-009、CHK-011。

## TODO-006 补充更新流程回归测试

- 目标：用现有 update flow 测试覆盖混合仓库、过滤、清理和严格校验行为。
- 涉及区域：`tests/test_update_flow.py`。
- 输入：临时 skill 仓库、不同 CLI 适用范围的 `SKILL.md`。
- 输出：覆盖过滤后的安装、输出、计数、配置写入、严格校验失败状态保护的测试。
- 依赖：TODO-001、TODO-002、TODO-003、TODO-004。
- 完成标准：新增测试覆盖 CHK-003 到 CHK-008 的核心路径，并能稳定通过。
- 关联 checklist：CHK-003、CHK-004、CHK-005、CHK-006、CHK-007、CHK-008。

## TODO-007 补充 scanner 和 skill check 单测

- 目标：覆盖元数据读取、默认通用、多 CLI 声明和非法字段反馈。
- 涉及区域：`tests/test_scanner.py`、`tests/test_skill_check.py`。
- 输入：包含不同 front matter 的临时 `SKILL.md`。
- 输出：针对元数据解析和标准检查的单测。
- 依赖：TODO-001、TODO-005。
- 完成标准：测试明确覆盖未声明、多个 CLI、未知 CLI、非法格式，且不影响既有检查行为。
- 关联 checklist：CHK-001、CHK-002、CHK-009、CHK-011。

## TODO-008 更新维护者文档

- 目标：说明 skill 适用 CLI 范围的字段语义、默认行为、示例和更新跳过行为。
- 涉及区域：`README.md`、`README-zh.md`、`docs/` 中相关需求或测试说明。
- 输入：最终字段命名和实现行为。
- 输出：维护者可理解的文档说明。
- 依赖：TODO-001、TODO-004、TODO-005。
- 完成标准：文档覆盖未声明默认通用、多 CLI 声明、未知 CLI 检查和跳过汇总语义。
- 关联 checklist：CHK-012。

## TODO-009 执行验收测试并记录结果

- 目标：按确认后的 checklist 执行自动测试和必要人工验证。
- 涉及区域：测试命令、`checklist.md` 或交付说明。
- 输入：已完成实现、确认后的 checklist。
- 输出：测试结果记录和未覆盖风险说明。
- 依赖：TODO-001 到 TODO-008。
- 完成标准：相关自动测试通过；人工验证步骤完成或明确无法执行的原因。
- 关联 checklist：CHK-001、CHK-002、CHK-003、CHK-004、CHK-005、CHK-006、CHK-007、CHK-008、CHK-009、CHK-010、CHK-011、CHK-012。
