# Cosh Hammer Global Coding Stage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace per-Hammer-parent coding takeover with one global Cosh coding stage that refines every Hammer coding task up front, commits each detailed task independently, and returns one final handoff to Hammer.

**Architecture:** `verify-handoff` remains the source of the complete Hammer parent order. The first Hammer coding dispatch opens one `schema_version: 2` ownership session containing every detailed Cosh task; subsequent progress is driven only by the global Cosh task engine. Each passed task atomically validates and commits the staged snapshot, while `complete-coding` produces a single coding-stage handoff after every task checkpoint is consistent with Git history.

The implementation must 一次性读取全部 Hammer coding parent tasks before activating the global task tree; it must not defer Task 2 or later refinement until a previous parent returns to Hammer.

**Tech Stack:** Python 3 standard library, JSON/Markdown state files, Git CLI, vanilla JavaScript dashboard, `unittest`.

**Spec:** `docs/superpowers/specs/2026-08-22-cosh-hammer-global-coding-stage-design.md`

## Global Constraints

- Do not modify Hammer skills, runtime, or `.hammer/**`.
- Cosh may write only `.cosh/hammer-plugin/<work-id>/**` and task-scoped Git commits in the business repository.
- Hammer stays paused for the complete global coding stage and resumes only after one final `DONE` handoff.
- New work uses `schema_version: 2`; old single-parent state is read-only and fail closed for controls.
- The default mode is single; continuous mode never bypasses dependency, scope, snapshot, or ownership checks.
- Preserve the unrelated untracked file `docs/superpowers/plans/2026-08-21-cosh-hammer-coding-ownership.md`.

---

### Task 1: Global Task Tree and Full-Stage Ownership

**Files:**
- Modify: `skills/cosh-hammer/scripts/cosh_hammer_state.py:439-667`
- Test: `tests/test_cosh_hammer.py`

**Interfaces:**
- Consumes: `verify_handoff(project: Path, work_id: str) -> dict` with ordered `coding_tasks` and `plan_sha256`.
- Produces: `_normalized_global_coding_tasks(task_spec: Mapping[str, Any], hammer_task_order: list[str]) -> list[dict[str, Any]]` and `activate_coding(project, work_id, entry_task, task_spec) -> dict` writing schema v2 global state.

- [ ] **Step 1: Write failing global activation tests**

Add tests that provide Hammer `Task 1`, `Task 2`, and `Task 3`, then submit one task spec containing detailed tasks for all three parents:

```python
result = self.state.activate_coding(
    self.project,
    "global-coding",
    "Task 1",
    {
        "tasks": [
            detailed_task("task1-fg", "Task 1", dependencies=[]),
            detailed_task("task1-tcc", "Task 1", dependencies=["task1-fg"]),
            detailed_task("task2-query", "Task 2", dependencies=["task1-tcc"]),
            detailed_task("task3-consumer", "Task 3", dependencies=["task2-query"]),
        ]
    },
)
self.assertEqual(result["task_count"], 4)
self.assertEqual(result["hammer_task_count"], 3)
self.assertEqual(read_json(root / "coding/tasks.json")["schema_version"], 2)
self.assertEqual(
    read_json(root / "coding/ownership.json")["scope"],
    "full_coding_stage",
)
```

Also assert activation rejects a missing Hammer parent, an unknown parent, duplicate IDs, unknown dependencies, and a dependency pointing from an earlier parent to a later parent.

- [ ] **Step 2: Run the activation tests and verify RED**

Run:

```bash
python3 -m unittest \
  tests.test_cosh_hammer.CoshHammerStateTest.test_activate_coding_builds_one_global_task_tree \
  tests.test_cosh_hammer.CoshHammerStateTest.test_activate_coding_rejects_incomplete_or_invalid_parent_mapping -v
```

Expected: FAIL because `_normalized_coding_tasks` currently rejects every task outside the entry parent and ownership is single-parent.

- [ ] **Step 3: Implement schema v2 normalization and ownership**

Replace the single-parent normalizer with a global normalizer shaped as follows:

```python
def _normalized_global_coding_tasks(
    task_spec: Mapping[str, Any], hammer_task_order: list[str]
) -> list[dict[str, Any]]:
    parent_indexes = {task: index for index, task in enumerate(hammer_task_order)}
    raw_tasks = task_spec.get("tasks")
    if not isinstance(raw_tasks, list) or not raw_tasks:
        raise CoshHammerError("Cosh 全局编码任务树不能为空")
    normalized = [_normalize_coding_task(raw, parent_indexes) for raw in raw_tasks]
    mapped = {task["hammer_parent"] for task in normalized}
    missing = [parent for parent in hammer_task_order if parent not in mapped]
    if missing:
        raise CoshHammerError("Hammer coding task 尚未全部细化：" + ", ".join(missing))
    by_id = {task["id"]: task for task in normalized}
    for task in normalized:
        for dependency in task["dependencies"]:
            if dependency not in by_id:
                raise CoshHammerError(f"Cosh 任务 {task['id']} 引用了未知依赖：{dependency}")
            if parent_indexes[by_id[dependency]["hammer_parent"]] > parent_indexes[task["hammer_parent"]]:
                raise CoshHammerError(f"Cosh 任务 {task['id']} 不能依赖后续 Hammer 父任务")
    return normalized
```

Extract `_normalize_coding_task(raw, parent_indexes)` from the current per-task field checks without changing their accepted types: it must validate `id`, `title`, `description`, non-empty `expected_files`, non-empty `symbols`, non-empty `steps`, string-list `dependencies`, non-empty `acceptance`, and a normalized `hammer_parent` present in `parent_indexes`.

Write `tasks.json` with `schema_version`, `hammer_task_order`, one global `current_task`, and the complete task list. Write ownership as:

```python
ownership = {
    "schema_version": 2,
    "status": "cosh_active",
    "scope": "full_coding_stage",
    "owner": "cosh",
    "hammer_status": "paused_for_cosh",
    "hammer_entry_task": entry,
    "hammer_task_order": task_order,
    "plan_sha256": gate["plan_sha256"],
}
```

Only `Task 1` (the first ordered coding task) may activate a new global stage. Remove per-parent authorization consumption from activation.

- [ ] **Step 4: Run the activation tests and the existing activation tests**

Run:

```bash
python3 -m unittest tests.test_cosh_hammer.CoshHammerStateTest.test_activate_coding_builds_one_global_task_tree tests.test_cosh_hammer.CoshHammerStateTest.test_activate_coding_rejects_incomplete_or_invalid_parent_mapping tests.test_cosh_hammer.CoshHammerStateTest.test_activate_coding_requires_artifacts_and_creates_cosh_task_engine -v
```

Expected: PASS with no `.hammer/**` writes.

- [ ] **Step 5: Commit Task 1**

```bash
git add skills/cosh-hammer/scripts/cosh_hammer_state.py tests/test_cosh_hammer.py
git commit -m "feat(cosh-hammer): 一次性激活全局编码任务树"
```

### Task 2: Global Progression and Independent Task Commits

**Files:**
- Modify: `skills/cosh-hammer/scripts/cosh_hammer_state.py:648-789`
- Test: `tests/test_cosh_hammer.py`

**Interfaces:**
- Consumes: schema v2 `ownership.json`, `tasks.json`, current task `expected_files`, and Git staged/unstaged state.
- Produces: `_task_delivery_snapshot(project: Path, task: Mapping[str, Any], all_tasks: list[dict[str, Any]]) -> dict`, `_commit_subtask(project: Path, work_id: str, task: Mapping[str, Any], evidence: Mapping[str, Any]) -> dict`, and checkpoints containing `snapshot_sha`, `commit_sha`, and `staged_files`.

- [ ] **Step 1: Write failing Git delivery tests**

Create a temporary Git repository with three global tasks and assert:

```python
result = self.state.complete_subtask(
    project,
    "global-coding",
    "task1-fg",
    status="passed",
    evidence={"acceptance": "passed"},
)
self.assertRegex(result["commit_sha"], r"^[0-9a-f]{40}$")
self.assertEqual(git("show", "--name-only", "--format=", "HEAD"), "fg.go")
self.assertEqual(read_json(checkpoint)["staged_files"], ["fg.go"])
self.assertEqual(read_json(tasks_path)["current_task"], "task1-tcc")
```

Add rejection cases for an empty index, staged out-of-scope paths, unstaged current-task changes, and unstaged/untracked files declared by future tasks. Verify `blocked` completion records evidence without committing.

- [ ] **Step 2: Run the delivery tests and verify RED**

Run:

```bash
python3 -m unittest \
  tests.test_cosh_hammer.CoshHammerStateTest.test_passed_subtask_commits_only_its_staged_delivery \
  tests.test_cosh_hammer.CoshHammerStateTest.test_subtask_commit_rejects_empty_dirty_or_future_task_delivery -v
```

Expected: FAIL because `complete_subtask` currently marks state passed without creating or validating a commit.

- [ ] **Step 3: Implement staged snapshot and task commit helpers**

Use Git plumbing through the existing subprocess pattern:

```python
def _staged_paths(project: Path) -> list[str]:
    output = _git_output(project, ["diff", "--cached", "--name-only", "-z"])
    return sorted(path for path in output.split("\0") if path)

def _unstaged_and_untracked_paths(project: Path) -> list[str]:
    tracked = _git_output(project, ["diff", "--name-only", "-z"])
    untracked = _git_output(
        project, ["ls-files", "--others", "--exclude-standard", "-z"]
    )
    return sorted({path for path in (*tracked.split("\0"), *untracked.split("\0")) if path})

def _staged_snapshot_sha(project: Path) -> str:
    head = _git_output(project, ["rev-parse", "HEAD"])
    patch = _git_bytes(project, ["diff", "--cached", "--binary", "HEAD", "--"])
    return hashlib.sha256(head.encode() + b"\0" + patch).hexdigest()
```

For `status="passed"`, require a non-empty index, restrict staged paths to `expected_files`, reject any unstaged/untracked path belonging to the current or future task set, compute the snapshot, run `git commit`, then atomically write the checkpoint before advancing state. Use a deterministic Chinese conventional subject such as `feat(cosh-hammer): 完成 task1-fg` and include work/task/parent trailers in the body.

- [ ] **Step 4: Make `_coding_context` validate frozen global ownership**

Stop calling `verify_coding` for every detailed task because Hammer remains on the entry task. Instead validate:

```python
handoff = verify_handoff(project, work_id)
if handoff["plan_sha256"] != ownership["plan_sha256"]:
    raise CoshHammerError("Hammer Plan 已变化，Cosh 全局编码所有权失效")
if handoff["coding_tasks"] != ownership["hammer_task_order"]:
    raise CoshHammerError("Hammer coding task 顺序已变化")
```

Also validate the active project, dashboard non-stale state, schema version, `scope`, and `cosh_active` status without requiring Hammer to advance its current task.

- [ ] **Step 5: Run progression, single-mode, and continuous-mode tests**

Run:

```bash
python3 -m unittest \
  tests.test_cosh_hammer.CoshHammerStateTest.test_passed_subtask_commits_only_its_staged_delivery \
  tests.test_cosh_hammer.CoshHammerStateTest.test_subtask_commit_rejects_empty_dirty_or_future_task_delivery \
  tests.test_cosh_hammer.CoshHammerStateTest.test_single_mode_requires_authorization_and_stops_at_each_subtask \
  tests.test_cosh_hammer.CoshHammerStateTest.test_continuous_mode_advances_without_per_task_authorization -v
```

Expected: PASS; both modes use identical commit/scope gates.

- [ ] **Step 6: Commit Task 2**

```bash
git add skills/cosh-hammer/scripts/cosh_hammer_state.py tests/test_cosh_hammer.py
git commit -m "feat(cosh-hammer): 按细分任务提交全局编码快照"
```

### Task 3: Single Global Handoff Back to Hammer

**Files:**
- Modify: `skills/cosh-hammer/scripts/cosh_hammer_state.py:790-860,1710-1990`
- Test: `tests/test_cosh_hammer.py`

**Interfaces:**
- Consumes: all-passed schema v2 tasks and task checkpoints reconciled with Git history.
- Produces: `complete_coding(project, work_id) -> dict` and `coding/coding-stage-handoff.json` with `completed_hammer_tasks`, `task_commits`, and `hammer_continue_after_coding_stage`.

- [ ] **Step 1: Write failing final handoff tests**

Assert intermediate parent completion never returns ownership and final completion returns one aggregate handoff:

```python
with self.assertRaisesRegex(self.state.CoshHammerError, "尚未全部通过"):
    self.state.complete_coding(project, "global-coding")

done = self.state.complete_coding(project, "global-coding")
self.assertEqual(done["status"], "DONE")
self.assertEqual(done["completed_hammer_tasks"], ["Task 1", "Task 2", "Task 3"])
self.assertEqual(done["next_action"], "hammer_continue_after_coding_stage")
self.assertEqual(len(done["task_commits"]), 4)
self.assertFalse((root / "coding/parent-handoffs/task-1.json").exists())
```

Add fail-closed cases for a missing checkpoint, checkpoint/commit mismatch, a commit absent from reachable Git history, stale Plan SHA, and HEAD not equal to the final checkpoint commit.

- [ ] **Step 2: Run the final handoff tests and verify RED**

Run:

```bash
python3 -m unittest \
  tests.test_cosh_hammer.CoshHammerStateTest.test_complete_coding_returns_one_global_handoff \
  tests.test_cosh_hammer.CoshHammerStateTest.test_complete_coding_reconciles_every_task_checkpoint -v
```

Expected: FAIL because `complete_coding` currently requires a parent task and writes one handoff per parent.

- [ ] **Step 3: Implement checkpoint reconciliation and aggregate handoff**

Change the API and CLI so `complete-coding` no longer accepts `--task` or `--commit-sha`. Load each checkpoint in global task order and validate:

```python
task_commits = []
for task in tasks:
    checkpoint = _read_json(checkpoint_path(task["id"]))
    if checkpoint["status"] != "passed" or checkpoint["task"] != task["id"]:
        raise CoshHammerError("Cosh 任务提交证据无效")
    _validate_commit(project, checkpoint["commit_sha"])
    task_commits.append({"task": task["id"], "commit_sha": checkpoint["commit_sha"]})
```

Require final `HEAD` to equal the last commit, write only `coding-stage-handoff.json`, include optional Meego, then set ownership to `returned_to_hammer` and tasks to `passed`.

- [ ] **Step 4: Remove obsolete parent-boundary controls**

Delete `_next_hammer_task`, `_parent_handoff_name`, `authorized_hammer_task`, and the `authorize-hammer-task` control branch. Keep only detailed-task authorization. Update the launch Hammer prompt so its Execute controller waits for one `hammer_continue_after_coding_stage` result and skips every coding parent worker listed in `completed_hammer_tasks`.

- [ ] **Step 5: Run final handoff and CLI tests**

Run:

```bash
python3 -m unittest \
  tests.test_cosh_hammer.CoshHammerStateTest.test_complete_coding_returns_one_global_handoff \
  tests.test_cosh_hammer.CoshHammerStateTest.test_complete_coding_reconciles_every_task_checkpoint \
  tests.test_cosh_hammer.CoshHammerStateTest.test_state_cli_exposes_all_fail_closed_handoff_commands -v
```

Expected: PASS and no parent handoff files.

- [ ] **Step 6: Commit Task 3**

```bash
git add skills/cosh-hammer/scripts/cosh_hammer_state.py tests/test_cosh_hammer.py
git commit -m "feat(cosh-hammer): 编码完成后一次性交还 Hammer"
```

### Task 4: Global Coding Dashboard

**Files:**
- Modify: `skills/cosh-hammer/scripts/cosh_hammer_state.py:1450-1590`
- Modify: `skills/cosh-hammer/assets/dashboard/app.js:321-430`
- Modify: `skills/cosh-hammer/assets/dashboard/styles.css`
- Test: `tests/test_cosh_hammer.py`

**Interfaces:**
- Consumes: schema v2 global tasks, ownership, control mode, task commit checkpoints.
- Produces: dashboard projection with `coding.parents`, `coding.tasks`, global progress, current detailed task, and only detailed-task controls.

- [ ] **Step 1: Write failing projection and UI contract tests**

Assert status projects all three parents and four detailed tasks, groups them in parent order, shows commit SHA evidence, and never emits `next_hammer_task` or `authorize-hammer-task`:

```python
self.assertEqual([parent["id"] for parent in status["coding"]["parents"]], ["Task 1", "Task 2", "Task 3"])
self.assertEqual(status["coding"]["progress"]["total"], 4)
self.assertEqual(status["coding"]["current_task"]["id"], "task2-query")
self.assertNotIn("next_hammer_task", status["coding"])
self.assertNotIn("authorize-hammer-task", dashboard_js)
```

- [ ] **Step 2: Run projection/UI tests and verify RED**

Run:

```bash
python3 -m unittest \
  tests.test_cosh_hammer.CoshHammerStateTest.test_dashboard_projects_global_coding_tree_by_hammer_parent \
  tests.test_cosh_hammer.CoshHammerStateTest.test_dashboard_assets_use_sse_and_our_observation_board -v
```

Expected: FAIL because projection and controls are still parent-local.

- [ ] **Step 3: Implement global projection**

Build parent summaries from `hammer_task_order` and the full task list:

```python
parents = [
    {
        "id": parent,
        "tasks": [task["id"] for task in coding_tasks if task["hammer_parent"] == parent],
        "completed": sum(
            1 for task in coding_tasks
            if task["hammer_parent"] == parent and task["status"] == "passed"
        ),
        "total": sum(1 for task in coding_tasks if task["hammer_parent"] == parent),
    }
    for parent in hammer_task_order
]
```

For schema v1 state, set `compatibility: legacy_single_parent_readonly`, disable controls, and preserve display without synthesizing missing tasks.

- [ ] **Step 4: Implement the separate coding-page layout**

Keep the Hammer Plan tab read-only. On the Coding tab, render one rail section per Hammer parent with its detailed tasks beneath it; keep selected task details on the right. Remove the parent authorization button and wording. Show global mode, global progress, ownership, and checkpoint commit SHA.

- [ ] **Step 5: Run dashboard tests**

Run:

```bash
python3 -m unittest \
  tests.test_cosh_hammer.CoshHammerStateTest.test_dashboard_projects_global_coding_tree_by_hammer_parent \
  tests.test_cosh_hammer.CoshHammerStateTest.test_dashboard_assets_use_sse_and_our_observation_board \
  tests.test_cosh_hammer.CoshHammerStateTest.test_live_status_normalizes_legacy_completed_task_as_read_only_passed -v
```

Expected: PASS with schema v1 controls disabled.

- [ ] **Step 6: Commit Task 4**

```bash
git add skills/cosh-hammer/scripts/cosh_hammer_state.py skills/cosh-hammer/assets/dashboard/app.js skills/cosh-hammer/assets/dashboard/styles.css tests/test_cosh_hammer.py
git commit -m "feat(cosh-hammer): 展示全局编码任务树"
```

### Task 5: Skill Contract, Installation Safety, and Full Verification

**Files:**
- Modify: `skills/cosh-hammer/SKILL.md`
- Modify: `skills/cosh-hammer/references/workflow.md`
- Modify: `skills/cosh-hammer/references/hammer-contract.md`
- Modify: `skills/cosh-hammer/references/handoff-gates.md`
- Modify: `skills/cosh-hammer/references/coding-artifacts.md`
- Modify: `skills/cosh-hammer/references/realtime-dashboard.md`
- Verify: `skills/cosh-hammer/agents/openai.yaml`
- Test: `tests/test_cosh_hammer.py`

**Interfaces:**
- Consumes: completed global coding-stage implementation.
- Produces: one consistent public skill contract and validated installable package.

- [ ] **Step 1: Write failing skill-contract assertions**

Update the contract test to require all-up-front refinement, full-stage ownership, per-detailed-task commits, and one final Hammer handoff. Assert obsolete phrases and controls are absent:

```python
self.assertIn("一次性细化全部 Hammer coding task", skill_text)
self.assertIn("整个编码阶段", skill_text)
self.assertNotIn("交还当前 Hammer 父任务", skill_text)
self.assertNotIn("authorize-hammer-task", skill_text + reference_text)
```

- [ ] **Step 2: Run the skill-contract test and verify RED**

Run:

```bash
python3 -m unittest tests.test_cosh_hammer.CoshHammerSkillTest.test_skill_contract_keeps_hammer_as_unmodified_main_workflow -v
```

Expected: FAIL because current documentation describes per-parent takeover.

- [ ] **Step 3: Rewrite the contract documents consistently**

State that Hammer Plan is refined once, Hammer remains paused for the full coding stage, all detailed tasks are visible before coding, each detailed task commits independently, and Hammer resumes once after all tasks. Preserve no-write `.hammer/**`, optional Meego, fixed port, worktree migration, review protocol, and stale-state rules. Keep `agents/openai.yaml` unchanged unless its description contradicts the final behavior.

- [ ] **Step 4: Run focused and full verification**

Run:

```bash
python3 -m unittest tests.test_cosh_hammer -v
python3 -m unittest discover -s tests -v
python3 -m internal.cli check --repo-path /Users/bytedance/cosh/skills-manager
python3 -m py_compile \
  skills/cosh-hammer/scripts/cosh_hammer_state.py \
  skills/cosh-hammer/scripts/serve_cosh_hammer_dashboard.py \
  skills/cosh-hammer/scripts/start_cosh_hammer_dashboard.py
git diff --check
```

Expected: all tests pass, all 16 skills pass standards, Python compilation succeeds, and `git diff --check` emits no output.

- [ ] **Step 5: Verify repository scope**

Run:

```bash
git status --short
git diff --name-only HEAD~5..HEAD
```

Expected: only the spec, this plan, `cosh-hammer` files, and `tests/test_cosh_hammer.py` are part of this implementation; `docs/superpowers/plans/2026-08-21-cosh-hammer-coding-ownership.md` remains untouched and untracked.

- [ ] **Step 6: Commit Task 5**

```bash
git add skills/cosh-hammer tests/test_cosh_hammer.py docs/superpowers/plans/2026-08-22-cosh-hammer-global-coding-stage.md
git commit -m "docs(cosh-hammer): 对齐全局独立编码阶段契约"
```
