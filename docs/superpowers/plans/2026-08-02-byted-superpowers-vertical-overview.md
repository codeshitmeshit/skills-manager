# ByteDance Superpowers Vertical Overview Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the overview stage-card grid with an accessible vertical workflow stepper and a read-only stage detail panel.

**Architecture:** Keep the existing dashboard status payload, SSE refresh, navigation, and control endpoints unchanged. Add small client-side rendering helpers for stage normalization, default selection, stepper markup, and detail markup; bind stage buttons to local selection and rerender without network writes. Add isolated CSS for the two-column desktop layout and single-column mobile layout while preserving `.stage-card` for the validation page.

**Tech Stack:** Vanilla JavaScript, CSS, Python `unittest`/`pytest` static dashboard contract tests.

## Global Constraints

- Do not modify OpenSpec skills, files, state, or workflows.
- Do not modify the Python dashboard server, workflow projection, SSE protocol, or control API.
- Preserve the backend order of `data.stages`.
- Treat unknown statuses visually as pending while displaying the escaped original status text.
- Stage selection is read-only client memory and never writes to the URL or backend.
- Reuse `.stage-card` for the validation page.

---

### Task 1: Vertical workflow stepper and stage details

**Files:**
- Modify: `tests/test_byted_superpowers_dashboard.py`
- Modify: `skills/cosh-byted-superpowers-review-planner/assets/dashboard/app.js`
- Modify: `skills/cosh-byted-superpowers-review-planner/assets/dashboard/styles.css`

**Interfaces:**
- Consumes: `data.stages: Record<string, {status, blockers, fix, version, updated_at, can_advance}>` in existing SSE snapshots.
- Produces: `renderStageStepper(stages, selectedName) -> string`, `renderStageDetail(name, stage) -> string`, and local `selectedOverviewStage` state used only by the overview renderer.

- [x] **Step 1: Write the failing JavaScript rendering behavior test**

Add a test beside `test_static_dashboard_uses_development_work_and_task_navigation`. The test runs the real `app.js` with Node and a minimal DOM boundary, then asserts rendered output and click behavior:

```python
def test_overview_renders_vertical_stepper_and_switches_details_without_writes(self) -> None:
    javascript = (SKILL_DIR / "assets" / "dashboard" / "app.js").read_text(
        encoding="utf-8"
    )
    runner = """
const appNode = { innerHTML: "" };
let stageClick = null;
globalThis.document = {
  querySelector: selector => selector === "#app" ? appNode : null,
  querySelectorAll: () => [],
};
globalThis.window = {
  location: new URL("file:///dashboard/index.html?tab=overview"),
  history: { replaceState: () => {} },
};
""" + javascript + """
const initialHtml = appNode.innerHTML;
document.querySelectorAll = selector => selector === "[data-overview-stage]" ? [{
  dataset: { overviewStage: "source" },
  addEventListener: (_event, handler) => { stageClick = handler; },
}] : [];
updateControl = () => { throw new Error("overview selection must remain read-only"); };
render(sampleData);
stageClick();
console.log(JSON.stringify({ initialHtml, selectedHtml: appNode.innerHTML }));
"""
    result = subprocess.run(
        ["node", "-"], input=runner, text=True, capture_output=True, check=True
    )
    rendered = json.loads(result.stdout)
    self.assertIn('class="overview-workflow"', rendered["initialHtml"])
    self.assertIn('aria-current="step"', rendered["initialHtml"])
    self.assertIn("security Reviewer 未通过", rendered["initialHtml"])
    self.assertIn("技术文档", rendered["selectedHtml"])
    self.assertIn("允许继续", rendered["selectedHtml"])
```

- [x] **Step 2: Run the test and verify RED**

Run:

```bash
python3 -m pytest tests/test_byted_superpowers_dashboard.py::BytedSuperpowersWorkflowStateTest::test_overview_renders_vertical_stepper_and_switches_details_without_writes -q
```

Expected: FAIL because the rendered overview does not yet contain `overview-workflow` or stage-selection buttons.

- [x] **Step 3: Implement the minimal JavaScript behavior**

In `app.js`:

1. Add `let selectedOverviewStage = null;` beside the other local UI state.
2. Add status metadata for `passed`, `running`, `blocked`, and `pending` with labels and symbols.
3. Add helpers that preserve `Object.entries(data.stages)` order, choose the first running/blocked stage by default, render native stage buttons with `aria-current="step"`, and render escaped detail fields.
4. Change `renderOverview` to return the existing Hero followed by `<section class="overview-workflow">` containing the stepper and detail panel.
5. In `bindInteractions`, bind `[data-overview-stage]` buttons only when `tab === "overview"`; update `selectedOverviewStage` and call `render(data)`. Do not call `updateControl`, `fetch`, history, or URL APIs.
6. When an SSE snapshot removes the selected stage, choose the default again. Preserve an existing selected stage while it remains present.

- [x] **Step 4: Implement the minimal responsive CSS**

In `styles.css`:

1. Add `.overview-workflow` as a two-column grid using `minmax(280px, .8fr) minmax(0, 1.2fr)`.
2. Render `.stage-stepper` as a panel-like vertical list and each `.stage-step` as a full-width button.
3. Use `.stage-step::before` for the connecting line and `.stage-status-icon` for the four status symbols.
4. Add distinct selected, focus-visible, passed, running, blocked, and pending states that do not rely only on color.
5. Add `.stage-detail` definitions for status, blocker, fix, version, time, and can-advance fields.
6. Under `@media (max-width: 900px)`, change `.overview-workflow` to one column. Do not remove `.stage-card` or `.validation-list` rules.

- [x] **Step 5: Run focused and full dashboard tests**

Run:

```bash
python3 -m pytest tests/test_byted_superpowers_dashboard.py -k 'vertical_stepper or static_dashboard' -q
python3 -m pytest tests/test_byted_superpowers_dashboard.py -q
```

Expected: all selected tests pass, followed by the complete ByteDance dashboard test file passing with zero failures.

- [x] **Step 6: Verify the live dashboard visually**

Start the existing demo dashboard against the fixture project, reload the overview page, and verify:

- stages appear in one vertical ordered chain;
- the running or blocked stage is selected by default;
- clicking a different stage changes only the detail panel;
- the browser sends no `/api/control` request for stage selection;
- the validation page still uses its existing cards;
- mobile-width layout stacks the detail panel below the stepper.

- [x] **Step 7: Commit the implementation**

```bash
git add tests/test_byted_superpowers_dashboard.py \
  skills/cosh-byted-superpowers-review-planner/assets/dashboard/app.js \
  skills/cosh-byted-superpowers-review-planner/assets/dashboard/styles.css \
  docs/superpowers/plans/2026-08-02-byted-superpowers-vertical-overview.md
git commit -m "feat: 优化研发观察板纵向流程"
```
