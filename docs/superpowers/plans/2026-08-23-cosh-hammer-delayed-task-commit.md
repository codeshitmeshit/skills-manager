# Cosh Hammer Delayed Task Commit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Separate implementation completion from Git commit so each Cosh task waits for explicit approval before its independent commit unlocks the next task.

**Architecture:** `complete_subtask()` records an `awaiting_commit` implementation checkpoint without touching Git history. A new `approve_task_commit()` command revalidates the live staged delivery, creates the task commit, promotes the checkpoint to `completed`, and only then applies single/continuous progression. The dashboard exposes this intermediate state and explicit approval action while legacy committed checkpoints remain readable.

**Tech Stack:** Python 3 standard library, Git CLI, unittest, vanilla JavaScript/CSS, JSON state files.

**Spec:** `docs/superpowers/specs/2026-08-23-cosh-hammer-delayed-task-commit-design.md`

## Global Constraints

- Do not modify Hammer, Hammer skills, or `.hammer/**`.
- Keep every task commit independent; this is delayed per-task commit, not one final aggregate commit.
- `awaiting_commit` retains `current_task` and blocks every path to the next task.
- Approval uses the live Git index and rejects empty, out-of-scope, unstaged, or untracked protected delivery.
- Single mode waits for separate next-task authorization after commit; continuous mode starts the next dependency-ready task only after commit.
- Existing schema v2 `passed + commit_sha` checkpoints remain readable as completed tasks; schema v1 remains read-only.
- All state changes fail closed when Plan SHA, active project, ownership, dashboard freshness, checkpoint, or Git evidence is invalid.

---

### Task 1: Split Implementation Completion from Commit Approval

**Files:**
- Modify: `skills/cosh-hammer/scripts/cosh_hammer_state.py:687-1010`
- Modify: `tests/test_cosh_hammer.py:400-1250`

**Interfaces:**
- Consumes: schema v2 task tree, active coding ownership, live Git index, `complete_subtask(project, work_id, task_id, status, evidence)`.
- Produces: `approve_task_commit(project: Path, work_id: str, task_id: str) -> dict[str, Any]`; checkpoint states `awaiting_commit` and `completed`.

- [ ] **Step 1: Replace immediate-commit tests with delayed-commit RED tests**

Add tests that begin a task, stage its initial delivery, call `complete_subtask(..., status="passed")`, and assert HEAD is unchanged, task/checkpoint status is `awaiting_commit`, `current_task` remains the same, and no `commit_sha` exists:

```python
before = self.git("rev-parse", "HEAD")
result = self.state.complete_subtask(
    self.project,
    "delayed-commit",
    "task1-fg",
    status="passed",
    evidence={"acceptance": "passed"},
)
self.assertEqual(result["status"], "awaiting_commit")
self.assertEqual(self.git("rev-parse", "HEAD"), before)
self.assertEqual(result["current_task"], "task1-fg")
self.assertNotIn("commit_sha", result)
```

Add a second test that edits and restages the current file after implementation completion, calls `approve_task_commit`, and asserts the resulting commit contains the later content and checkpoint fields `staged_files`, `snapshot_sha`, and `commit_sha`.

- [ ] **Step 2: Run focused tests and verify RED**

Run:

```bash
python3 -m unittest \
  tests.test_cosh_hammer.CoshHammerStateTest.test_passed_subtask_waits_for_explicit_commit_approval \
  tests.test_cosh_hammer.CoshHammerStateTest.test_commit_approval_uses_latest_staged_delivery -v
```

Expected: FAIL because `complete_subtask` still commits immediately and `approve_task_commit` does not exist.

- [ ] **Step 3: Implement `awaiting_commit` completion**

Change the passed branch of `complete_subtask()` to write only implementation evidence:

```python
checkpoint.update(
    {
        "status": "awaiting_commit",
        "implementation_completed_at": now,
    }
)
selected["status"] = "awaiting_commit"
selected["implementation_completed_at"] = now
selected["evidence"] = dict(evidence)
state["status"] = "awaiting_commit"
state["current_task"] = task_id
```

Do not call `_task_delivery_snapshot()` or `_commit_subtask()` in this function. Persist checkpoint, tasks, ownership, and return `{"status": "awaiting_commit", "completed_task": task_id, "current_task": task_id}`. Keep the blocked branch unchanged except for shared timestamp naming.

- [ ] **Step 4: Implement explicit approval and progression**

Add `approve_task_commit(project: Path, work_id: str, task_id: str) -> dict[str, Any]`. Start it with `_coding_context(project, work_id)`, select `task_id` from `state["tasks"]`, and then perform these exact operations:

- require `state.current_task == task_id` and selected status `awaiting_commit`;
- require checkpoint `task == task_id` and `status == awaiting_commit`;
- call `_task_delivery_snapshot(active_project, selected, raw_tasks)` at approval time;
- call `_commit_subtask()` only after snapshot validation;
- atomically update checkpoint to `completed` with `committed_at`, snapshot, and commit SHA;
- update the task to `completed` with the same commit SHA;
- in single mode clear `authorized_task`, set `current_task` to the next pending task, but leave it pending;
- in continuous mode set the next dependency-ready task to `running` and record `started_at`;
- set whole coding state to `completed` only when no pending task remains, otherwise `running`;
- on validation/commit failure leave the persisted task/checkpoint in `awaiting_commit`.

- [ ] **Step 5: Add hard-gate and retry tests**

Cover empty index, out-of-scope staged path, current/future protected dirty files, forced Git commit failure, and attempts to begin or authorize the next task while current is `awaiting_commit`. Assert every failure keeps HEAD unchanged and current task awaiting approval. Then fix the staged delivery and assert retry succeeds.

- [ ] **Step 6: Update final reconciliation and legacy normalization**

Change `complete_coding()` to require task/checkpoint status `completed`. In `_project_coding_task()` and checkpoint projection, normalize legacy `status == "passed"` with a valid-looking `commit_sha` to `completed` while marking it legacy; never normalize uncommitted `passed` evidence.

- [ ] **Step 7: Run Task 1 tests**

Run:

```bash
python3 -m unittest \
  tests.test_cosh_hammer.CoshHammerStateTest.test_passed_subtask_waits_for_explicit_commit_approval \
  tests.test_cosh_hammer.CoshHammerStateTest.test_commit_approval_uses_latest_staged_delivery \
  tests.test_cosh_hammer.CoshHammerStateTest.test_commit_approval_rejects_invalid_live_delivery_and_retries \
  tests.test_cosh_hammer.CoshHammerStateTest.test_awaiting_commit_blocks_every_next_task_path \
  tests.test_cosh_hammer.CoshHammerStateTest.test_complete_coding_returns_one_global_handoff \
  tests.test_cosh_hammer.CoshHammerStateTest.test_live_status_normalizes_legacy_completed_task_as_read_only_passed -v
```

Expected: PASS.

- [ ] **Step 8: Commit Task 1**

```bash
git add skills/cosh-hammer/scripts/cosh_hammer_state.py tests/test_cosh_hammer.py
git commit -m "feat(cosh-hammer): delay task commits until approval"
```

### Task 2: Expose Approval Through CLI, Control API, and Dashboard

**Files:**
- Modify: `skills/cosh-hammer/scripts/cosh_hammer_state.py:1650-2005`
- Modify: `skills/cosh-hammer/scripts/serve_cosh_hammer_dashboard.py:80-115`
- Modify: `skills/cosh-hammer/assets/dashboard/app.js:360-475`
- Modify: `skills/cosh-hammer/assets/dashboard/styles.css`
- Modify: `tests/test_cosh_hammer.py:1280-2205`

**Interfaces:**
- Consumes: `approve_task_commit()`, live coding projection, `/api/control` plugin-only endpoint.
- Produces: CLI `approve-task-commit --task-id`, control action `{action: "approve-task-commit", task: id}`, dashboard approval button and split progress.

- [ ] **Step 1: Write failing CLI/control/UI contract tests**

Assert the parser exposes:

```text
approve-task-commit --project <path> --work <id> --task-id <id>
```

Assert `apply_control()` accepts only the current awaiting task, calls approval, and still writes only `.cosh/**` plus the authorized Git commit. Assert dashboard JavaScript contains `approve-task-commit`, “批准写入”, and does not reuse next-task authorization for commit approval.

- [ ] **Step 2: Run contract tests and verify RED**

Run:

```bash
python3 -m unittest \
  tests.test_cosh_hammer.CoshHammerStateTest.test_state_cli_exposes_delayed_commit_approval \
  tests.test_cosh_hammer.CoshHammerStateTest.test_control_approves_only_current_awaiting_commit_task \
  tests.test_cosh_hammer.CoshHammerSkillTest.test_dashboard_exposes_explicit_commit_approval -v
```

Expected: FAIL because the action and UI do not exist.

- [ ] **Step 3: Add CLI and control action**

Add the CLI subparser and main dispatch to `approve_task_commit()`. Extend `apply_control()` with `approve-task-commit`; require a non-empty `task`, call the same function, and return its result. Keep stale dashboard and inactive ownership protections unchanged.

- [ ] **Step 4: Project awaiting state and split progress**

Add projection fields:

```json
{
  "progress": {
    "implemented": 2,
    "committed": 1,
    "total": 4
  },
  "next_action": "approve_current_task_commit"
}
```

Count `awaiting_commit` and `completed` as implemented; count only `completed` as committed. Expose staged file names for the current awaiting task only when live Git projection succeeds. On read failure, mark controls disabled and preserve fail-closed status.

- [ ] **Step 5: Add dashboard approval UI**

When the selected current task has `status === "awaiting_commit"`, render:

- badge “实现已完成，待批准写入”;
- live staged file list;
- button “批准写入” posting `{action: "approve-task-commit", task: selectedTask.id}`.

Disable it unless `data.controls_enabled && data.coding.controls_enabled`. Continue showing commit/snapshot only after `completed` checkpoint. Display progress as `实现完成 X / N · 已提交 Y / N`.

- [ ] **Step 6: Verify single and continuous dashboard behavior**

Add integration tests proving single mode shows next-task authorization only after approval succeeds, while continuous mode advances only after approval. Ensure clicking ordinary mode or authorization controls cannot approve the pending commit.

- [ ] **Step 7: Run Task 2 tests**

Run:

```bash
python3 -m unittest \
  tests.test_cosh_hammer.CoshHammerStateTest.test_state_cli_exposes_delayed_commit_approval \
  tests.test_cosh_hammer.CoshHammerStateTest.test_control_approves_only_current_awaiting_commit_task \
  tests.test_cosh_hammer.CoshHammerStateTest.test_dashboard_projects_awaiting_commit_progress \
  tests.test_cosh_hammer.CoshHammerSkillTest.test_dashboard_exposes_explicit_commit_approval \
  tests.test_cosh_hammer.CoshHammerStateTest.test_single_mode_requires_authorization_and_stops_at_each_subtask \
  tests.test_cosh_hammer.CoshHammerStateTest.test_continuous_mode_advances_without_per_task_authorization -v
```

Expected: PASS.

- [ ] **Step 8: Commit Task 2**

```bash
git add skills/cosh-hammer/scripts/cosh_hammer_state.py skills/cosh-hammer/scripts/serve_cosh_hammer_dashboard.py skills/cosh-hammer/assets/dashboard/app.js skills/cosh-hammer/assets/dashboard/styles.css tests/test_cosh_hammer.py
git commit -m "feat(cosh-hammer): add explicit task commit approval"
```

### Task 3: Align Skill Contract and Run Full Verification

**Files:**
- Modify: `skills/cosh-hammer/SKILL.md`
- Modify: `skills/cosh-hammer/references/workflow.md`
- Modify: `skills/cosh-hammer/references/coding-artifacts.md`
- Modify: `skills/cosh-hammer/references/handoff-gates.md`
- Modify: `skills/cosh-hammer/references/hammer-contract.md`
- Modify: `skills/cosh-hammer/references/realtime-dashboard.md`
- Test: `tests/test_cosh_hammer.py`

**Interfaces:**
- Consumes: implemented state/API/UI semantics from Tasks 1-2.
- Produces: one consistent skill contract describing delayed approval, independent per-task commits, and next-task hard gate.

- [ ] **Step 1: Update skill and references**

Replace every “passed task commits immediately” rule with:

```text
实现验收通过后进入 awaiting_commit，不创建 commit；用户批准写入时，以实时暂存区重新校验并创建该任务独立 commit。提交成功是下一任务的共同硬门。
```

Document checkpoint fields before and after approval, single/continuous behavior, legacy normalization, final handoff requirements, and dashboard copy. Keep Hammer boundaries unchanged.

- [ ] **Step 2: Add semantic contract assertions**

Update `test_skill_contract_keeps_hammer_as_unmodified_main_workflow` to assert the skill contains explicit delayed approval and does not promise automatic commit on `complete-subtask`. Keep these assertions semantic and paired with behavior tests rather than matching full paragraphs.

- [ ] **Step 3: Run focused cosh-hammer tests**

```bash
python3 -m unittest tests.test_cosh_hammer -v
```

Expected: all cosh-hammer tests pass.

- [ ] **Step 4: Run repository and syntax validation**

```bash
python3 -m unittest discover -s tests
python3 -m internal.cli check --repo-path /Users/bytedance/cosh/skills-manager
python3 /Users/bytedance/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/cosh-hammer
python3 -m py_compile skills/cosh-hammer/scripts/cosh_hammer_state.py skills/cosh-hammer/scripts/serve_cosh_hammer_dashboard.py
node --check skills/cosh-hammer/assets/dashboard/app.js
git diff --check
```

Expected: all tests, repository checks, skill validation, syntax checks, and diff checks pass.

- [ ] **Step 5: Commit Task 3**

```bash
git add skills/cosh-hammer/SKILL.md skills/cosh-hammer/references tests/test_cosh_hammer.py
git commit -m "docs(cosh-hammer): document delayed task commit gate"
```

- [ ] **Step 6: Report delivery state**

Report the implementation commits, exact test counts, verification commands, remaining untracked user files, and that no push or local skill sync was performed unless separately requested.
