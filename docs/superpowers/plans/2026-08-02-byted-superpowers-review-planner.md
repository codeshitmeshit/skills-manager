# ByteDance Superpowers Review Planner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the unused ByteDance OpenSpec workflow with a native Superpowers, hard-gated development workflow and live dashboard while preserving the generic OpenSpec skill.

**Architecture:** Keep Superpowers specs, plans, and SDD progress untouched, and project ByteDance-specific gate evidence from `.superpowers/byted-work/<work-id>/`. Split the old monolithic server into a focused workflow model plus a thin HTTP/SSE adapter; reuse the existing static dashboard structure and safe document reader while changing its domain model from changes/artifacts to development works/stages.

**Tech Stack:** Python 3 standard library, vanilla HTML/CSS/JavaScript, `unittest`/`pytest`, Git CLI, Server-Sent Events, JSON and Markdown.

## Global Constraints

- The ByteDance skill name and directory are `cosh-byted-superpowers-review-planner`.
- Keep `cosh-requirement-review-planner` and its OpenSpec behavior unchanged.
- Use native Superpowers files under `docs/superpowers/specs/`, `docs/superpowers/plans/`, and `.superpowers/sdd/`.
- Store ByteDance workflow evidence under `.superpowers/byted-work/<work-id>/` without adding ByteDance fields to native Superpowers documents.
- Every stage is fail-closed and must validate its predecessor, evidence version, document hash, and code SHA on the backend.
- Review uses three independent stability, security, and feasibility reviewers after the AI-Spec knowledge gate and CodeGraph fact scan.
- A technical document revision invalidates the knowledge gate, CodeGraph snapshot, and all three review results.
- ByteDance business unit tests run remotely through `bits-remote-ut`; the local tests in this plan validate only this skill repository.
- Prefer existing infrastructure, add narrow functions when reuse is impossible, keep changes scoped, add Chinese comments for non-obvious logic, and emit observable logs without secrets.
- In single-task mode, only the current implementation task may change; remote UT, CR, and a successful scoped commit are required before the next task unlocks.
- Task commits use `<type>: <中文摘要>\n\n<work-id>-task<N>`.
- Full remote UT and final CR must pass for the current HEAD before push is allowed.
- Save local retrospectives under `.superpowers/byted-archive/` and gitignore that directory.
- Do not invoke Hammer or `$cosh-before-push` automatically.

---

### Task 1: Establish the ByteDance Superpowers skill contract

**Files:**
- Rename: `skills/cosh-byted-openspec-review-planner/` → `skills/cosh-byted-superpowers-review-planner/`
- Rename: `tests/test_byted_openspec_review_planner_skill.py` → `tests/test_byted_superpowers_review_planner_skill.py`
- Modify: `skills/cosh-byted-superpowers-review-planner/SKILL.md`
- Modify: `skills/cosh-byted-superpowers-review-planner/agents/openai.yaml`
- Create: `skills/cosh-byted-superpowers-review-planner/references/superpowers-workflow.md`
- Rename: `skills/cosh-byted-superpowers-review-planner/references/byted-design-review.md` → `skills/cosh-byted-superpowers-review-planner/references/byted-admission-review.md`
- Modify: `skills/cosh-byted-superpowers-review-planner/references/byted-admission-review.md`
- Modify: `skills/cosh-byted-superpowers-review-planner/references/byted-coding-remote-ut.md`
- Remove: `skills/cosh-byted-superpowers-review-planner/references/openspec-workflow.md`
- Test: `tests/test_byted_superpowers_review_planner_skill.py`

**Interfaces:**
- Consumes: the approved design specification and unchanged generic skill at `skills/cosh-requirement-review-planner/`.
- Produces: a triggerable `$cosh-byted-superpowers-review-planner` skill whose direct references define the hard-gated workflow.

- [ ] **Step 1: Rename the old ByteDance test and write failing identity/resource assertions**

```python
ROOT = pathlib.Path(__file__).resolve().parents[1]
BYTED_DIR = ROOT / "skills" / "cosh-byted-superpowers-review-planner"

def test_identity_uses_native_superpowers(self) -> None:
    skill = (BYTED_DIR / "SKILL.md").read_text(encoding="utf-8")
    metadata = (BYTED_DIR / "agents" / "openai.yaml").read_text(encoding="utf-8")
    self.assertIn("name: cosh-byted-superpowers-review-planner", skill)
    self.assertIn("$cosh-byted-superpowers-review-planner", metadata)
    self.assertNotIn("OpenSpec", skill)
    self.assertNotIn("openspec", skill.lower())

def test_required_references_exist(self) -> None:
    for relative in (
        "references/superpowers-workflow.md",
        "references/byted-admission-review.md",
        "references/byted-coding-remote-ut.md",
        "references/realtime-dashboard.md",
    ):
        self.assertTrue((BYTED_DIR / relative).is_file(), relative)
```

- [ ] **Step 2: Run the contract tests and verify the new path fails**

Run: `python -m pytest tests/test_byted_superpowers_review_planner_skill.py -q`

Expected: FAIL because `skills/cosh-byted-superpowers-review-planner` does not exist.

- [ ] **Step 3: Rename the directory and replace the workflow contract**

The new `SKILL.md` must directly state this ordered hard gate:

```markdown
技术文档 → AI-Spec 知识门禁 → CodeGraph 事实扫描 → 三路独立评审
→ 评审闭环 → Superpowers 规格 → 精确定位 → Superpowers 计划
→ 实施子任务 → 完整远程 UT → 最终 CR → push → 本地归档
```

It must link every retained reference directly, distinguish single-task and continuous modes, and state that the dashboard is optional observation/control rather than the execution source of truth.

- [ ] **Step 4: Run the contract and generic regression tests**

Run: `python -m pytest tests/test_byted_superpowers_review_planner_skill.py tests/test_requirement_review_planner_skill.py -q`

Expected: PASS, and the generic OpenSpec skill remains unchanged.

- [ ] **Step 5: Commit the contract migration**

```bash
git add skills/cosh-byted-superpowers-review-planner tests/test_byted_superpowers_review_planner_skill.py
git commit -m "feat: 建立字节 Superpowers 研发流程契约" -m "byted-superpowers-review-planner-task1"
```

---

### Task 2: Implement the native workflow model and review invalidation

**Files:**
- Create: `skills/cosh-byted-superpowers-review-planner/scripts/workflow_state.py`
- Rename: `tests/test_byted_openspec_dashboard.py` → `tests/test_byted_superpowers_dashboard.py`
- Modify: `tests/test_byted_superpowers_dashboard.py`

**Interfaces:**
- Consumes: `<project>/.superpowers/byted-work/<work-id>/workflow.json`, `source.json`, `reviews/*.json`, and `evidence/*.json`.
- Produces: `resolve_work(project_root: Path, work_id: str | None) -> Path`, `list_works(project_root: Path) -> list[dict[str, Any]]`, `build_status(project_root: Path, work_id: str | None = None) -> dict[str, Any]`, and `validate_transition(status: Mapping[str, Any], target_stage: str) -> None`.

- [ ] **Step 1: Replace the OpenSpec fixture with a native Superpowers work fixture**

```python
def setUp(self) -> None:
    self.temp_dir = tempfile.TemporaryDirectory()
    self.root = pathlib.Path(self.temp_dir.name)
    self.work_id = "optimize-order-risk-check"
    self.work = self.root / ".superpowers" / "byted-work" / self.work_id
    (self.work / "reviews").mkdir(parents=True)
    (self.work / "evidence").mkdir()
    (self.root / "docs" / "superpowers" / "specs").mkdir(parents=True)
    (self.root / "docs" / "superpowers" / "plans").mkdir(parents=True)
```

Write JSON helpers that bind every evidence file to `source_version`, `source_sha256`, and `code_sha`.

- [ ] **Step 2: Add failing tests for work discovery and fail-closed stage ordering**

```python
def test_review_cannot_pass_without_all_three_current_reviewers(self) -> None:
    self.write_workflow(stage="review")
    self.write_knowledge_gate(status="passed")
    self.write_codegraph(status="passed")
    self.write_review("stability", status="passed")
    self.write_review("security", status="passed")
    status = WORKFLOW.build_status(self.root, self.work_id)
    self.assertEqual(status["stages"]["review"]["status"], "blocked")
    self.assertIn("feasibility", status["stages"]["review"]["blockers"])

def test_document_revision_invalidates_gate_codegraph_and_reviews(self) -> None:
    self.write_complete_review_round(source_version=1)
    self.write_source(version=2, content="# revised")
    status = WORKFLOW.build_status(self.root, self.work_id)
    self.assertEqual(status["stages"]["knowledge_gate"]["status"], "blocked")
    self.assertEqual(status["stages"]["codegraph"]["status"], "blocked")
    self.assertEqual(status["stages"]["review"]["status"], "blocked")
```

- [ ] **Step 3: Run the focused tests and verify missing APIs fail**

Run: `python -m pytest tests/test_byted_superpowers_dashboard.py -k 'work or review or revision or transition' -q`

Expected: FAIL because `workflow_state.py` and its interfaces are absent.

- [ ] **Step 4: Implement strict JSON loading, evidence binding, work discovery, and stage projection**

Use explicit stage order:

```python
STAGE_ORDER = (
    "source",
    "knowledge_gate",
    "codegraph",
    "review",
    "review_closure",
    "spec",
    "location",
    "plan",
    "implementation",
    "remote_ut",
    "final_review",
    "push",
    "archive",
)

REQUIRED_REVIEWERS = ("stability", "security", "feasibility")
VALID_STATUSES = {"pending", "running", "blocked", "passed"}
```

`build_status` must downgrade invalid or stale evidence to `blocked`, retain historical review rounds for display, and expose `blockers`, `fix`, `version`, `updated_at`, and `can_advance` for every stage.

- [ ] **Step 5: Add and pass AI-Spec fallback tests**

```python
def test_fallback_requires_failed_onboarding_and_versioned_generic_rules(self) -> None:
    self.write_knowledge_gate(
        status="fallback",
        onboarding_attempted=True,
        onboarding_error="registry unavailable",
        generic_rules_version="2026-08-02",
    )
    status = WORKFLOW.build_status(self.root, self.work_id)
    self.assertEqual(status["knowledge_gate"]["mode"], "fallback")
    self.assertFalse(status["stages"]["spec"]["can_advance"])
```

Run: `python -m pytest tests/test_byted_superpowers_dashboard.py -k 'work or review or revision or transition or fallback' -q`

Expected: PASS.

- [ ] **Step 6: Commit the workflow model**

```bash
git add skills/cosh-byted-superpowers-review-planner/scripts/workflow_state.py tests/test_byted_superpowers_dashboard.py
git commit -m "feat: 实现研发阶段硬门禁与评审闭环" -m "byted-superpowers-review-planner-task2"
```

---

### Task 3: Parse native Superpowers artifacts and enforce scoped task progression

**Files:**
- Modify: `skills/cosh-byted-superpowers-review-planner/scripts/workflow_state.py`
- Create: `skills/cosh-byted-superpowers-review-planner/scripts/task_control.py`
- Modify: `tests/test_byted_superpowers_dashboard.py`

**Interfaces:**
- Consumes: `docs/superpowers/specs/*.md`, `docs/superpowers/plans/*.md`, `.superpowers/sdd/<plan>/progress.md`, Git staged paths, and task evidence JSON.
- Produces: `parse_superpowers_plan(path: Path) -> list[dict[str, Any]]`, `validate_task_scope(project_root: Path, task: Mapping[str, Any]) -> list[str]`, `format_task_commit(work_id: str, task_number: int, commit_type: str, summary: str) -> str`, and `advance_task(project_root: Path, work_id: str, expected_version: str, expected_task: int) -> dict[str, Any]`.

- [ ] **Step 1: Add failing native plan parsing and scope-lock tests**

```python
def test_native_plan_tasks_expose_files_interfaces_and_steps(self) -> None:
    plan = self.write_plan("""
### Task 1: Add retry guard
**Files:**
- Modify: `internal/risk.go:40-70`
**Interfaces:**
- Produces: `shouldSkip(scene RiskScene) bool`
- [ ] **Step 1: Add failing test**
""")
    tasks = TASKS.parse_superpowers_plan(plan)
    self.assertEqual(tasks[0]["number"], 1)
    self.assertEqual(tasks[0]["allowed_files"], ["internal/risk.go"])

def test_scope_rejects_unrelated_staged_file(self) -> None:
    task = {"allowed_files": ["internal/risk.go"]}
    self.git_add("internal/risk.go", "internal/unrelated.go")
    self.assertEqual(
        TASKS.validate_task_scope(self.root, task),
        ["internal/unrelated.go"],
    )
```

- [ ] **Step 2: Add failing hard-gate and commit-message tests**

```python
def test_advance_requires_remote_ut_and_cr_for_current_head(self) -> None:
    with self.assertRaises(WORKFLOW.DashboardConflict):
        TASKS.advance_task(self.root, self.work_id, self.version, 1)

def test_commit_message_is_conventional_chinese_and_task_scoped(self) -> None:
    message = TASKS.format_task_commit(
        "optimize-order-risk-check", 1, "feat", "增加内部重试判断"
    )
    self.assertEqual(
        message,
        "feat: 增加内部重试判断\n\noptimize-order-risk-check-task1",
    )
```

- [ ] **Step 3: Run focused tests and verify they fail**

Run: `python -m pytest tests/test_byted_superpowers_dashboard.py -k 'plan or scope or advance or commit_message' -q`

Expected: FAIL because task parsing and controls are absent.

- [ ] **Step 4: Implement native parsing and the serial task lock**

Parse `### Task N:`, `**Files:**`, `**Interfaces:**`, and checkbox steps without mutating the plan. Merge completion state from SDD progress and evidence. In single mode, expose exactly one current task and reject writes to later tasks. In continuous mode, reuse the same validator and only remove the human click wait.

- [ ] **Step 5: Implement safe staged commit and task unlock**

Before committing, require:

```python
assert control["mode"] == "single"
assert expected_version == status["version"]
assert expected_task == status["current_task"]["number"]
assert remote_ut["status"] == "passed" and remote_ut["code_sha"] == head_sha
assert cr["status"] == "passed" and cr["code_sha"] == head_sha
assert validate_task_scope(project_root, current_task) == []
```

Reject empty commits, invalid commit types, non-Chinese summaries, mismatched task suffixes, and unrelated staged files. Record the successful commit SHA before unlocking the next task.

- [ ] **Step 6: Run task and Git control tests**

Run: `python -m pytest tests/test_byted_superpowers_dashboard.py -k 'plan or task or scope or mode or advance or commit' -q`

Expected: PASS.

- [ ] **Step 7: Commit task control**

```bash
git add skills/cosh-byted-superpowers-review-planner/scripts/workflow_state.py skills/cosh-byted-superpowers-review-planner/scripts/task_control.py tests/test_byted_superpowers_dashboard.py
git commit -m "feat: 实现实施子任务串行校验与规范提交" -m "byted-superpowers-review-planner-task3"
```

---

### Task 4: Migrate the dashboard API, SSE listener, and user interface

**Files:**
- Rename: `skills/cosh-byted-superpowers-review-planner/scripts/serve_openspec_dashboard.py` → `skills/cosh-byted-superpowers-review-planner/scripts/serve_superpowers_dashboard.py`
- Modify: `skills/cosh-byted-superpowers-review-planner/scripts/serve_superpowers_dashboard.py`
- Modify: `skills/cosh-byted-superpowers-review-planner/assets/dashboard/index.html`
- Modify: `skills/cosh-byted-superpowers-review-planner/assets/dashboard/app.js`
- Modify: `skills/cosh-byted-superpowers-review-planner/assets/dashboard/styles.css`
- Modify: `skills/cosh-byted-superpowers-review-planner/references/realtime-dashboard.md`
- Modify: `tests/test_byted_superpowers_dashboard.py`

**Interfaces:**
- Consumes: `workflow_state.build_status`, `workflow_state.list_works`, and `task_control.advance_task`.
- Produces: `GET /api/works`, `GET /api/status?work=`, `GET /api/document?work=&path=`, `GET /events?work=`, and restricted `POST /api/control`.

- [ ] **Step 1: Add failing API and static contract tests**

```python
def test_works_endpoint_and_work_query_replace_changes(self) -> None:
    payload = self.get_json("/api/works")
    self.assertEqual(payload["default_work"], self.work_id)
    status = self.get_json(f"/api/status?work={self.work_id}")
    self.assertEqual(status["work"], self.work_id)

def test_static_dashboard_uses_development_work_copy(self) -> None:
    javascript = (SKILL_DIR / "assets/dashboard/app.js").read_text(encoding="utf-8")
    self.assertIn('new EventSource(apiUrl("/events", { work }))', javascript)
    self.assertIn('fetch("/api/works"', javascript)
    self.assertNotIn("OpenSpec", javascript)
    self.assertNotIn("change-select", javascript)
```

- [ ] **Step 2: Add failing UI behavior tests**

Assert that navigation contains 技术文档、评审、规格、计划、验证 and a final emphasized Tasks tab; the artifact list is absent; review cards say 风险点; single mode renders one advance button in the current task header; continuous mode does not render that button.

- [ ] **Step 3: Run API/UI tests and verify old names fail**

Run: `python -m pytest tests/test_byted_superpowers_dashboard.py -k 'endpoint or static or navigation or render or event' -q`

Expected: FAIL on old `/api/changes`, `change=`, OpenSpec copy, and old server path.

- [ ] **Step 4: Convert the server into a thin adapter**

Retain safe path resolution, JSON response helpers, HTTP error mapping, SSE framing, last-good snapshot behavior, and no-cache headers. Delegate workflow projection and writes to the new modules. Every POST body must include `work`, `expected_version`, and `idempotency_key`; stale or forged writes return HTTP 409.

- [ ] **Step 5: Convert the dashboard domain and layout**

Use `work` throughout sample and live data. Replace the artifact list with tab-specific readers. Put Tasks last and visually emphasize it. Put the mode selector at the top of Tasks. Render the single advance button in the current task header only when `can_advance` is true, and omit its markup entirely in continuous mode.

- [ ] **Step 6: Verify live updates and recovery**

Run: `python -m pytest tests/test_byted_superpowers_dashboard.py -k 'sse or event or reconnect or atomic or malformed' -q`

Expected: initial status and later file changes arrive without reconnect; malformed half-writes preserve the last valid projection and expose a blocked error.

- [ ] **Step 7: Run all ByteDance dashboard tests**

Run: `python -m pytest tests/test_byted_superpowers_dashboard.py -q`

Expected: PASS.

- [ ] **Step 8: Commit the dashboard migration**

```bash
git add skills/cosh-byted-superpowers-review-planner tests/test_byted_superpowers_dashboard.py
git commit -m "feat: 迁移 Superpowers 实时研发观察板" -m "byted-superpowers-review-planner-task4"
```

---

### Task 5: Add local retrospective archiving and rule distillation

**Files:**
- Create: `skills/cosh-byted-superpowers-review-planner/scripts/archive_work.py`
- Modify: `skills/cosh-byted-superpowers-review-planner/scripts/serve_superpowers_dashboard.py`
- Modify: `skills/cosh-byted-superpowers-review-planner/scripts/workflow_state.py`
- Modify: `skills/cosh-byted-superpowers-review-planner/references/superpowers-workflow.md`
- Modify: `.gitignore`
- Modify: `tests/test_byted_superpowers_dashboard.py`

**Interfaces:**
- Consumes: the projected workflow, review history, task evidence, Git history, push evidence, and available conversation coverage metadata.
- Produces: `archive_work(project_root: Path, work_id: str, trigger: Literal["push", "manual"]) -> Path` and `POST /api/control` action `archive`.

- [ ] **Step 1: Add failing archive content and gitignore tests**

```python
def test_archive_is_local_gitignored_and_evidence_based(self) -> None:
    path = ARCHIVE.archive_work(self.root, self.work_id, "manual")
    self.assertEqual(path.parent.parent.name, self.work_id)
    content = path.read_text(encoding="utf-8")
    self.assertIn("## 会话轮次与覆盖范围", content)
    self.assertIn("## 多轮讨论原因分析", content)
    self.assertIn("## 可蒸馏规则候选", content)
    self.assertTrue(ARCHIVE.is_archive_ignored(self.root))

def test_unknown_chat_turns_are_not_estimated(self) -> None:
    content = self.archive_with_conversation(total_turns=None, observed_turns=7)
    self.assertIn("完整轮数：未知", content)
    self.assertIn("已观测轮数：7", content)
```

- [ ] **Step 2: Add failing sanitization and trigger tests**

Verify token-like values, credentials, and sensitive payload fields are redacted; successful push requests automatic archive; manual archive works for blocked or cancelled work; archive failure marks `archive` blocked without reverting a successful push.

- [ ] **Step 3: Run archive tests and verify failure**

Run: `python -m pytest tests/test_byted_superpowers_dashboard.py -k 'archive or retrospective or redact or distill' -q`

Expected: FAIL because the archive module does not exist.

- [ ] **Step 4: Implement one Markdown retrospective per archive event**

Write under `.superpowers/byted-archive/<work-id>/<UTC timestamp>-retrospective.md`. Ensure the project `.gitignore` contains `.superpowers/byted-archive/` without overwriting existing ignore rules. Include evidence-linked causes by category and candidate rules with evidence, expected benefit, scope, confidence, and suggested target. Never apply a candidate rule automatically.

- [ ] **Step 5: Run archive and API tests**

Run: `python -m pytest tests/test_byted_superpowers_dashboard.py -k 'archive or retrospective or redact or distill or control' -q`

Expected: PASS.

- [ ] **Step 6: Commit archiving**

```bash
git add .gitignore skills/cosh-byted-superpowers-review-planner tests/test_byted_superpowers_dashboard.py
git commit -m "feat: 增加本地研发复盘与规则蒸馏" -m "byted-superpowers-review-planner-task5"
```

---

### Task 6: Remove ByteDance OpenSpec residue and run the full regression suite

**Files:**
- Modify: `skills/cosh-byted-superpowers-review-planner/**`
- Modify: `tests/test_byted_superpowers_review_planner_skill.py`
- Modify: `tests/test_byted_superpowers_dashboard.py`
- Verify only: `skills/cosh-requirement-review-planner/**`
- Verify only: `tests/test_requirement_review_planner_skill.py`
- Verify only: `tests/test_requirement_dashboard.py`

**Interfaces:**
- Consumes: all outputs from Tasks 1–5.
- Produces: a clean ByteDance Superpowers skill with fresh regression evidence.

- [ ] **Step 1: Add residue and resource-link assertions**

```python
def test_byted_skill_has_no_openspec_residue(self) -> None:
    for path in BYTED_DIR.rglob("*"):
        if path.is_file():
            text = path.read_text(encoding="utf-8", errors="ignore").lower()
            self.assertNotIn("openspec", text, str(path))

def test_every_direct_skill_reference_exists(self) -> None:
    for relative in extract_markdown_paths((BYTED_DIR / "SKILL.md").read_text()):
        self.assertTrue((BYTED_DIR / relative).exists(), relative)
```

Add a final gate contract that binds both final evidence files to the current HEAD:

```python
def test_push_requires_current_head_remote_ut_and_final_review(self) -> None:
    self.write_final_remote_ut(status="passed", code_sha="stale-sha")
    self.write_final_review(status="passed", code_sha=self.git_head())
    status = WORKFLOW.build_status(self.root, self.work_id)
    self.assertFalse(status["stages"]["push"]["can_advance"])
    self.assertIn("remote_ut", status["stages"]["push"]["blockers"])
```

- [ ] **Step 2: Run syntax and static checks**

Run: `python -m py_compile skills/cosh-byted-superpowers-review-planner/scripts/*.py`

Run: `git diff --check`

Expected: both commands exit 0.

- [ ] **Step 3: Run ByteDance skill and dashboard tests**

Run: `python -m pytest tests/test_byted_superpowers_review_planner_skill.py tests/test_byted_superpowers_dashboard.py -q`

Expected: PASS.

- [ ] **Step 4: Run generic OpenSpec regression tests**

Run: `python -m pytest tests/test_requirement_review_planner_skill.py tests/test_requirement_dashboard.py -q`

Expected: PASS with the generic skill unchanged.

- [ ] **Step 5: Run the complete repository test suite**

Run: `python -m pytest -q`

Expected: all tests PASS.

- [ ] **Step 6: Verify file inventory and inspect the final diff**

Run: `rg --files skills/cosh-byted-superpowers-review-planner | sort`

Run: `git status --short && git diff --stat && git diff --check`

Expected: no obsolete ByteDance skill directory, no untracked debug artifacts, no whitespace errors, and no unintended generic-skill modifications introduced by the migration.

- [ ] **Step 7: Commit final cleanup if files changed in this task**

```bash
git add skills/cosh-byted-superpowers-review-planner tests/test_byted_superpowers_review_planner_skill.py tests/test_byted_superpowers_dashboard.py
git commit -m "test: 完成字节 Superpowers 流程回归验证" -m "byted-superpowers-review-planner-task6"
```
