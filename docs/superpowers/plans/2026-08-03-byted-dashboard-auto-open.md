# ByteDance Dashboard Auto-Open Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automatically start the ByteDance Superpowers dashboard and open its actual listening URL in the system default browser whenever the workflow formally starts.

**Architecture:** Extend the existing dashboard server with an opt-in `--open` flag backed by Python's standard `webbrowser` module. Keep browser launching inside the server so it occurs only after the socket binds and knows the real port. Make the skill entry contract invoke `--port 0 --open` before AI-Spec while excluding skill maintenance to prevent recursive launches.

**Tech Stack:** Python standard library, `unittest`, Markdown skill instructions.

## Global Constraints

- Do not modify any OpenSpec skill, dashboard, or state.
- Do not change the dashboard API, SSE protocol, or workflow state machine.
- Open the system default browser, not the Codex in-app browser.
- Browser launch failure must not stop the HTTP service or development workflow.
- Use an OS-assigned free port with `--port 0` in the skill entry command.

---

### Task 1: Open the bound dashboard URL in the system browser

**Files:**
- Modify: `tests/test_byted_superpowers_dashboard.py`
- Modify: `skills/cosh-byted-superpowers-review-planner/scripts/serve_superpowers_dashboard.py`

**Interfaces:**
- Consumes: CLI flag `--open` and the `ThreadingHTTPServer.server_address` tuple.
- Produces: `args.open_browser: bool` and one `webbrowser.open(url, new=2)` call after successful bind.

- [x] **Step 1: Write failing tests**

Add tests that patch `sys.argv` to verify `--open` parses as `open_browser=True`, and run `SERVER.main()` with a fake bound server at `127.0.0.1:54321`. Assert the browser opener receives exactly `http://127.0.0.1:54321/`. Make the fake server return from `serve_forever` and assert `server_close` still runs.

- [x] **Step 2: Verify RED**

Run:

```bash
python3 -m unittest \
  tests.test_byted_superpowers_dashboard.BytedSuperpowersWorkflowStateTest.test_dashboard_cli_accepts_open_flag \
  tests.test_byted_superpowers_dashboard.BytedSuperpowersWorkflowStateTest.test_dashboard_opens_actual_bound_url
```

Expected: FAIL because `--open` is unrecognized and the module has no `webbrowser` opener.

- [x] **Step 3: Implement minimal server behavior**

Import `webbrowser`, add `parser.add_argument("--open", action="store_true", dest="open_browser")`, build the URL from `server.server_address`, and call `webbrowser.open(url, new=2)` after printing the URL. Catch exceptions and log a warning; also log a warning when the opener returns false. Continue into `serve_forever` in both failure cases.

- [x] **Step 4: Verify GREEN**

Run the two focused tests, then:

```bash
python3 -m unittest tests.test_byted_superpowers_dashboard
```

Expected: all ByteDance dashboard tests pass.

---

### Task 2: Make auto-start a skill entry contract

**Files:**
- Modify: `tests/test_byted_superpowers_review_planner_skill.py`
- Modify: `skills/cosh-byted-superpowers-review-planner/SKILL.md`
- Modify: `skills/cosh-byted-superpowers-review-planner/references/realtime-dashboard.md`

**Interfaces:**
- Consumes: `scripts/serve_superpowers_dashboard.py --project <目标仓库> --work <work-id> --port 0 --open`.
- Produces: an imperative skill entry rule that starts and keeps the dashboard running before AI-Spec.

- [x] **Step 1: Write the failing skill contract test**

Assert `SKILL.md` contains `--port 0 --open`, `AI-Spec 门禁前`, `系统默认浏览器`, and a maintenance recursion exception. Assert `realtime-dashboard.md` documents browser failure as non-blocking and requires outputting the final URL.

- [x] **Step 2: Verify RED**

Run:

```bash
python3 -m unittest tests.test_byted_superpowers_review_planner_skill
```

Expected: FAIL because the current skill only describes manual dashboard startup.

- [x] **Step 3: Update the skill and reference**

Add a concise `入口启动` section to `SKILL.md`, insert dashboard startup after work state creation and before AI-Spec in the main workflow, and keep the service alive through all phases. Update `realtime-dashboard.md` with the exact command, final URL behavior, browser failure fallback, and the skill-maintenance exception.

- [x] **Step 4: Validate and test the skill**

Run:

```bash
python3 -m unittest \
  tests.test_byted_superpowers_review_planner_skill \
  tests.test_byted_superpowers_dashboard
python3 /Users/bytedance/.codex/skills/.system/skill-creator/scripts/quick_validate.py \
  skills/cosh-byted-superpowers-review-planner
```

Expected: tests and skill validation pass.

- [x] **Step 5: Commit**

Stage only the two docs, two test files, server script, and this plan. Commit with:

```text
feat: 自动启动研发观察板
```
