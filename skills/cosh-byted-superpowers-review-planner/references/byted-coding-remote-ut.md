# 字节最小改动与远程 UT

## 最小修改面

按以下顺序实现：

1. 复用当前仓库已有基础设施、组件、类型、helper、配置、鉴权、日志和测试工具。
2. 能组合现有能力时只增加最小调用编排，不复制底层实现。
3. 无法安全复用时，新建职责单一、命名明确的窄函数，保持共享旧函数的输入、输出、副作用和错误语义不变。
4. 只修改调用新函数所需的最少调用点，并用 UT 锁定旧路径行为。

禁止为了本需求重构公共链路、泛化接口、移动无关代码或顺手修复邻近问题，字节编码不得扩大修改面。若必须修改共享函数、公共协议、公共状态或多个调用方，先停止，列出直接/间接调用方、变量流、兼容风险和替代方案，重新完成精确定位、规格与稳定性/安全性/可行性评审。

## UT 设计

每个编码 task 都要尽可能覆盖：

- 正常路径和预期业务结果；
- 空值、零值、上下界、重复请求和非法输入；
- 下游错误、超时、降级、重试与部分失败；
- 状态变化、幂等、并发和顺序问题（适用时）；
- 新函数行为、最小调用接入和原有旧路径不回归；
- 中文注释描述的业务边界和关键日志触发条件。

优先复用仓库已有测试基建、mock 和 fixture。不得为了容易测试而扩大生产代码可见性或引入仅测试使用的业务分支。

## 只允许远程 UT

禁止运行本地业务 UT 命令，也不得用本地 `go test`、IDE 测试或本地覆盖率作为完成证据。必须且只能调用 `bits-remote-ut`；禁止调用 Hammer、`hammer-*` 或 `test-remote-ut`，也不得在 BITS 不可用时降级成本地 UT。

执行前检查：

- 当前 CWD 是目标仓库或正确 worktree；
- 存在 `.codebase/pipelines/ci.yaml`，特殊仓库再显式指定 `JOB_ID`；
- `utd`、Python 及 BITS Remote UT 的 `run_remote_ut.sh`、`utd_analyze.py` 可用；
- `.gitignore` 已忽略 `.utd/` 或实际 BITS 测试产物目录；
- 本次远程范围与 task 修改面对应。
- 结果证据绑定当前代码 SHA；代码变化后旧证据立即失效。

开发阶段按 `file -> package -> directory` 逐步扩大远程范围，使用 `TEST_FILES`、`TEST_PACKAGE_PATH`、`TEST_DIRECTORY` 和 `PATTERN` 精确定位。Task 完成前至少覆盖全部受影响 package；全部 tasks 完成和最终测试确认前运行默认远程 pipeline。若存量失败阻塞全量结果，必须用远程报告区分基线失败与本次回归，不能改跑本地测试绕过。

## 远程结果判定

只在以下条件全部满足时判定通过：

- `run_remote_ut.sh` 退出码为 `0`；
- 本次不是 `PREPARE_ONLY=true`，且确实进入了远程测试执行阶段；
- 本次 `result_dir/report.json` 中 `meta.remote.run_success=true`；
- `summary.has_failures=false`；
- `summary.failed_packages=0` 且 `summary.failed_tests=0`；
- 报告范围覆盖当前 task 或最终 gate 所需范围。

先读 `report.txt` Failure Tree，再用 `report.json` 做结构化判定；只有远程执行异常时再读 `status.json` 和 `utd.log`。失败后根据证据修复代码或 UT，并重跑相同或更大范围。不得关闭远程 gate、忽略失败或把 prepare/build 成功写成 UT 通过。

交付时记录远程任务链接、`result_dir`、测试范围、通过条件、失败摘要与重跑结果，但不得暴露 token 或提交 `.utd/` 等测试产物。
