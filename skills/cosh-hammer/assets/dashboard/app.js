const params = new URLSearchParams(window.location.search);
const work = params.get("work");
const tabs = new Set([
  "overview", "requirement", "design", "review", "plan", "coding",
  "validation", "delivery", "artifacts",
]);
let activeTab = tabs.has(params.get("tab")) ? params.get("tab") : "overview";
let currentData = null;
let artifactRaw = "";
let artifactPresentation = null;
let artifactMode = "rendered";
let selectedCodingTaskId = null;

function api(path, extra = {}) {
  const url = new URL(path, window.location.origin);
  if (work) url.searchParams.set("work", work);
  Object.entries(extra).forEach(([key, value]) => url.searchParams.set(key, value));
  return url.toString();
}

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function addDefinition(list, label, value) {
  const row = element("div");
  row.append(element("dt", "", label), element("dd", "", value || "—"));
  list.append(row);
}

function viewHeader(title, description) {
  const header = element("div", "view-header");
  const copy = element("div");
  copy.append(element("p", "eyebrow", "阶段视图"), element("h2", "", title));
  if (description) copy.append(element("p", "muted", description));
  header.append(copy);
  return header;
}

function emptyState(message) {
  return element("div", "empty-state", message);
}

function appendInline(parent, text) {
  const pattern = /(`[^`]+`|\*\*[^*]+\*\*|\*[^*]+\*)/g;
  let cursor = 0;
  text.replace(pattern, (token, _match, offset) => {
    if (offset > cursor) parent.append(document.createTextNode(text.slice(cursor, offset)));
    if (token.startsWith("`")) parent.append(element("code", "inline-code", token.slice(1, -1)));
    else if (token.startsWith("**")) parent.append(element("strong", "", token.slice(2, -2)));
    else parent.append(element("em", "", token.slice(1, -1)));
    cursor = offset + token.length;
    return token;
  });
  if (cursor < text.length) parent.append(document.createTextNode(text.slice(cursor)));
}

function markdownBlock(block) {
  if (block.type === "heading") {
    const heading = element(`h${Math.min(6, Math.max(1, block.level))}`, "md-heading");
    appendInline(heading, block.text);
    return heading;
  }
  if (block.type === "paragraph") {
    const paragraph = element("p", "md-paragraph");
    appendInline(paragraph, block.text);
    return paragraph;
  }
  if (block.type === "list") {
    const list = element(block.ordered ? "ol" : "ul", "md-list");
    block.items.forEach(item => {
      const row = element("li");
      appendInline(row, item);
      list.append(row);
    });
    return list;
  }
  if (block.type === "quote") {
    const quote = element("blockquote", "md-quote");
    appendInline(quote, block.text);
    return quote;
  }
  if (block.type === "code" || block.type === "frontmatter") {
    const wrapper = element("div", `md-code ${block.type}`);
    const label = block.type === "frontmatter" ? "FRONTMATTER" : (block.language || "CODE").toUpperCase();
    wrapper.append(element("span", "code-language", label));
    const pre = element("pre");
    pre.append(element("code", "", block.text));
    wrapper.append(pre);
    return wrapper;
  }
  if (block.type === "table") {
    const wrapper = element("div", "md-table-wrap");
    const table = element("table", "md-table");
    const head = element("thead");
    const headRow = element("tr");
    block.headers.forEach(value => headRow.append(element("th", "", value)));
    head.append(headRow);
    const body = element("tbody");
    block.rows.forEach(values => {
      const row = element("tr");
      values.forEach(value => row.append(element("td", "", value)));
      body.append(row);
    });
    table.append(head, body);
    wrapper.append(table);
    return wrapper;
  }
  if (block.type === "rule") return element("hr", "md-rule");
  return element("p", "md-paragraph", block.text || "");
}

function jsonType(value) {
  if (value === null) return "null";
  if (Array.isArray(value)) return "array";
  return typeof value;
}

function jsonNode(value, key = null, depth = 0) {
  const type = jsonType(value);
  if (type === "object" || type === "array") {
    const entries = type === "array" ? value.map((item, index) => [index, item]) : Object.entries(value);
    const details = element("details", `json-branch ${type}`);
    details.open = depth < 2;
    const summary = element("summary");
    if (key !== null) summary.append(element("span", "json-key", String(key)), document.createTextNode(" "));
    summary.append(
      element("span", "json-type", type),
      element("span", "json-count", `${entries.length} ${type === "array" ? "项" : "个字段"}`),
    );
    details.append(summary);
    const children = element("div", "json-children");
    entries.forEach(([childKey, childValue]) => children.append(jsonNode(childValue, childKey, depth + 1)));
    details.append(children);
    return details;
  }
  const row = element("div", `json-leaf ${type}`);
  if (key !== null) row.append(element("span", "json-key", String(key)), document.createTextNode(" "));
  const display = type === "string" ? `“${value}”` : String(value);
  row.append(element("span", `json-value ${type}`, display), element("span", "json-type", type));
  return row;
}

function renderArtifactContent() {
  const content = document.querySelector("#artifact-content");
  content.replaceChildren();
  content.className = `artifact-content ${artifactMode}`;
  document.querySelectorAll("[data-artifact-mode]").forEach(button => {
    button.classList.toggle("active", button.dataset.artifactMode === artifactMode);
  });
  if (artifactMode === "raw" || !artifactPresentation) {
    content.append(element("pre", "raw-content", artifactRaw));
    return;
  }
  if (artifactPresentation.kind === "markdown") {
    const article = element("article", "markdown-document");
    artifactPresentation.blocks.forEach(block => article.append(markdownBlock(block)));
    content.append(article);
    return;
  }
  if (artifactPresentation.kind === "json") {
    const tree = element("div", "json-tree");
    tree.append(jsonNode(artifactPresentation.value));
    content.append(tree);
    return;
  }
  content.append(element("pre", "raw-content", artifactPresentation.content || artifactRaw));
}

function closeArtifact() {
  document.querySelector("#artifact-viewer").hidden = true;
}

async function postControl(command) {
  const response = await fetch(api("/api/control"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(command),
  });
  if (!response.ok) throw new Error((await response.json()).error || "控制失败");
  await refresh();
}

async function openArtifact(artifact) {
  const viewer = document.querySelector("#artifact-viewer");
  const content = document.querySelector("#artifact-content");
  document.querySelector("#artifact-owner").textContent = artifact.scope === "hammer" ? "HAMMER 产物" : "COSH 编码产物";
  document.querySelector("#artifact-title").textContent = artifact.path;
  artifactRaw = "";
  artifactPresentation = null;
  artifactMode = "rendered";
  content.className = "artifact-content loading";
  content.textContent = "正在读取…";
  viewer.hidden = false;
  try {
    const response = await fetch(api("/api/artifact", { scope: artifact.scope, path: artifact.path }), { cache: "no-store" });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || "读取产物失败");
    if (payload.kind === "binary") {
      artifactRaw = `二进制产物 · ${payload.size} bytes，当前仅展示元信息。`;
      artifactPresentation = { kind: "text", content: artifactRaw };
    } else if (payload.kind === "large") {
      artifactRaw = `产物大小 ${payload.size} bytes，超过在线预览上限。`;
      artifactPresentation = { kind: "text", content: artifactRaw };
    } else {
      artifactRaw = payload.content;
      artifactPresentation = ArtifactFormatters.present(artifact.path, payload.content);
    }
    renderArtifactContent();
  } catch (error) {
    artifactRaw = error.message;
    artifactPresentation = { kind: "text", content: error.message };
    renderArtifactContent();
  }
}

function artifactList(data, category = null) {
  const artifacts = (data.artifacts || []).filter(item => !category || item.category === category);
  if (!artifacts.length) return emptyState("当前阶段尚无可展示产物，观察板会随 Hammer 实时更新。");
  const list = element("div", "artifact-list");
  artifacts.forEach(artifact => {
    const button = element("button", "artifact-row");
    button.type = "button";
    const badge = element("span", `scope ${artifact.scope}`, artifact.scope === "hammer" ? "HAMMER" : "COSH");
    const copy = element("span", "artifact-copy");
    copy.append(element("strong", "", artifact.name), element("small", "", artifact.path));
    button.append(badge, copy, element("span", "artifact-size", `${artifact.size} B`));
    button.addEventListener("click", () => openArtifact(artifact));
    list.append(button);
  });
  return list;
}

function artifactDisclosure(data, category, title) {
  const count = (data.artifacts || []).filter(item => item.category === category).length;
  const disclosure = element("details", "artifact-disclosure");
  const summary = element("summary", "artifact-disclosure-summary");
  summary.append(
    element("strong", "", `${title} · ${count}`),
    element("span", "muted", "点击展开"),
  );
  disclosure.append(summary, artifactList(data, category));
  return disclosure;
}

function renderOverview(data) {
  const fragment = document.createDocumentFragment();
  const header = viewHeader("Hammer 主流程", "Hammer 是唯一状态机；Cosh 只增强编码执行和观察。");
  const progress = data.progress || {};
  const markerLabels = { current: "当前", next: "下一步", complete: "已完成" };
  const progressBadge = element("div", `progress-badge ${progress.marker || "next"}`);
  progressBadge.append(
    element("span", "progress-kind", markerLabels[progress.marker] || "下一步"),
    element("strong", "", progress.label || "等待 Hammer 状态"),
    element("small", "", `${progress.completed || 0} / ${progress.total || data.stages.length}`),
  );
  header.append(progressBadge);
  fragment.append(header);
  const facts = element("dl", "facts");
  addDefinition(facts, "阶段", data.hammer.stage);
  addDefinition(facts, "状态", data.hammer.status);
  addDefinition(facts, "当前任务", data.hammer.current_task);
  addDefinition(facts, "活动目录", data.active_project);
  addDefinition(facts, "工作区", data.workspace?.migrated ? "已跟随 Hammer worktree" : "原目录（未迁移）");
  addDefinition(facts, "Meego", data.launch?.meego?.bound ? data.launch.meego.id : "未绑定（不阻塞）");
  fragment.append(facts);
  const stages = element("div", "stages");
  data.stages.forEach((stage, index) => {
    const known = ["pending", "running", "passed", "blocked", "failed"];
    const marker = stage.progress_marker || "";
    const card = element("article", `stage ${known.includes(stage.status) ? stage.status : "pending"} ${marker}`.trim());
    card.append(element("span", "number", String(index + 1).padStart(2, "0")));
    const copy = element("div");
    copy.append(element("h3", "", stage.label), element("p", "", stage.status));
    card.append(copy);
    if (marker) card.append(element("span", `stage-marker ${marker}`, markerLabels[marker]));
    stages.append(card);
  });
  fragment.append(stages);
  return fragment;
}

function renderStage(data, title, description, category) {
  const fragment = document.createDocumentFragment();
  fragment.append(viewHeader(title, description), artifactList(data, category));
  return fragment;
}

function renderReview(data) {
  const fragment = document.createDocumentFragment();
  fragment.append(viewHeader("三路评审", "按 Hammer review round 展示可行性、安全性和稳定性结果。"));
  const rounds = data.review_results?.rounds || [];
  if (!rounds.length) {
    fragment.append(emptyState("Hammer 尚未生成三路评审结果。"));
  } else {
    const labels = { general: "可行性 / 一致性", security: "安全性", stability: "稳定性" };
    rounds.forEach(round => {
      const section = element("section", "review-round");
      const heading = element("div", "review-round-heading");
      heading.append(element("h3", "", `Round ${round.round}`), element("span", `review-status ${round.status}`, round.status));
      section.append(heading);
      const grid = element("div", "review-grid");
      round.reports.forEach(report => {
        const card = element("article", `review-card ${report.status}`);
        const top = element("div", "review-card-heading");
        top.append(element("h3", "", labels[report.channel] || report.channel), element("span", `review-status ${report.status}`, report.status));
        card.append(top);
        const facts = element("dl", "review-facts");
        addDefinition(facts, "最高级别", report.max_severity || "none");
        addDefinition(facts, "阻塞问题", report.blocking_issue_count === null ? "—" : String(report.blocking_issue_count));
        addDefinition(facts, "评审方式", [report.review_pass, report.review_mode].filter(Boolean).join(" · ") || "—");
        addDefinition(facts, "未闭合 Finding", report.unresolved_finding_ids || "none");
        card.append(facts);
        if (report.artifact_path) {
          const open = element("button", "open-review", "查看评审原文");
          open.type = "button";
          open.addEventListener("click", () => openArtifact({ scope: "hammer", path: report.artifact_path }));
          card.append(open);
        }
        grid.append(card);
      });
      section.append(grid);
      fragment.append(section);
    });
  }
  fragment.append(element("h3", "section-heading", "全部评审产物"), artifactList(data, "review"));
  return fragment;
}

function renderCoding(data) {
  const fragment = document.createDocumentFragment();
  fragment.append(viewHeader("编码执行", "独立展示覆盖全部 Hammer coding task 的 Cosh 全局任务树。"));
  const tasks = data.coding?.tasks || [];
  if (tasks.length) {
    const ownership = data.coding?.ownership || {};
    const ownershipCopy = data.coding?.compatibility === "legacy_single_parent_readonly"
      ? "检测到旧版编码快照，仅兼容展示，不开放推进控制"
      : ownership.status === "cosh_active"
      ? "Hammer 已暂停编码，Cosh 正在执行全局细分任务"
      : ownership.status === "returned_to_hammer"
        ? "编码完成，等待交还 Hammer"
        : "编码所有权尚未确认";
    const ownershipBanner = element("section", `coding-ownership ${ownership.status || "pending"}`);
    ownershipBanner.append(
      element("p", "eyebrow", ownership.status === "cosh_active" ? "COSH 编码接管中" : "编码交接"),
      element("strong", "", ownershipCopy),
      element("span", "muted", ownership.hammer_entry_task || data.hammer.current_task || ""),
    );
    fragment.append(ownershipBanner);
    const progress = data.coding?.progress || {};
    const progressPanel = element("section", "coding-progress");
    const progressCopy = element("div");
    progressCopy.append(
      element("p", "eyebrow", "任务进度"),
      element("strong", "", `实现完成 ${progress.implemented || 0} / ${progress.total || tasks.length} · 已提交 ${progress.committed || 0} / ${progress.total || tasks.length}`),
      element("span", "muted", `下一动作：${data.coding?.next_action || "等待状态"}`),
    );
    const progressTrack = element("div", "task-progress-track");
    const progressValue = element("span", "task-progress-value");
    progressValue.style.width = `${Math.max(0, Math.min(100, progress.percent || 0))}%`;
    progressTrack.append(progressValue);
    progressPanel.append(progressCopy, progressTrack);
    fragment.append(progressPanel);
    const settings = element("section", "coding-settings");
    const settingCopy = element("div");
    settingCopy.append(element("p", "eyebrow", "推进方式"), element("strong", "", data.control?.mode === "continuous" ? "连续推进" : "逐一任务校验"));
    const actions = element("div", "controls");
    [["single", "逐一任务校验"], ["continuous", "连续推进"]].forEach(([mode, label]) => {
      const button = element("button", data.control?.mode === mode ? "active" : "", label);
      button.type = "button";
      button.disabled = !data.controls_enabled || !data.coding?.controls_enabled;
      button.addEventListener("click", () => postControl({ action: "set-mode", mode }).catch(error => alert(error.message)));
      actions.append(button);
    });
    const current = data.coding?.current_task;
    const needsAuthorization = data.control?.mode !== "continuous" && current?.status === "pending" && data.control?.authorized_task !== current.id;
    if (needsAuthorization) {
      const authorize = element("button", "authorize", `授权 ${current.id}`);
      authorize.type = "button";
      authorize.disabled = !data.controls_enabled || !data.coding?.controls_enabled;
      authorize.addEventListener("click", () => postControl({ action: "authorize-task", task: current.id }).catch(error => alert(error.message)));
      actions.append(authorize);
    }
    if (current?.status === "awaiting_commit") {
      const approve = element("button", "approve-commit", "批准写入");
      approve.type = "button";
      approve.disabled = !data.controls_enabled || !data.coding?.controls_enabled;
      approve.addEventListener("click", () => postControl({ action: "approve-task-commit", task: current.id }).catch(error => alert(error.message)));
      actions.append(approve);
    }
    settings.append(settingCopy, actions);
    fragment.append(settings);
    const selectedTask = tasks.find(task => task.id === selectedCodingTaskId)
      || data.coding?.current_task
      || tasks[0];
    selectedCodingTaskId = selectedTask?.id || null;
    const workspace = element("section", "coding-workspace");
    const taskList = element("nav", "coding-task-rail");
    taskList.setAttribute("aria-label", "编码任务列表");
    (data.coding?.parents || []).forEach(parent => {
      const group = element("section", "coding-parent-group");
      const parentHeading = element("div", "coding-parent-heading");
      parentHeading.append(
        element("strong", "", parent.id),
        element("span", "muted", `${parent.completed} / ${parent.total}`),
      );
      group.append(parentHeading);
      parent.tasks.forEach(taskId => {
        const task = tasks.find(item => item.id === taskId);
        if (!task) return;
        const currentClass = data.coding?.current_task?.id === task.id ? " current" : "";
        const selectedClass = selectedCodingTaskId === task.id ? " selected" : "";
        const item = element("button", `coding-task-item ${task.status || "pending"}${currentClass}${selectedClass}`);
        item.type = "button";
        item.append(
          element("span", "task-index", task.id || "TASK"),
          element("strong", "", task.title || task.id),
          element("span", "task-status", task.status || "pending"),
        );
        item.addEventListener("click", () => {
          selectedCodingTaskId = task.id;
          renderView(data);
        });
        group.append(item);
      });
      taskList.append(group);
    });
    const detail = element("article", `coding-task-detail ${selectedTask?.status || "pending"}`);
    if (selectedTask) {
      const heading = element("div", "task-heading");
      const copy = element("div");
      copy.append(
        element("p", "eyebrow", `${selectedTask.id} · ${selectedTask.hammer_parent || "HAMMER TASK"}`),
        element("h3", "", selectedTask.title || selectedTask.id),
        element("p", "task-description", selectedTask.description || (selectedTask.legacy ? "旧版任务未记录详细说明" : "未记录任务说明")),
      );
      heading.append(copy, element("strong", "task-status", selectedTask.status || "pending"));
      detail.append(heading);
      if (selectedTask.status === "awaiting_commit") {
        const pendingCommit = element("section", "task-evidence awaiting-commit");
        pendingCommit.append(
          element("h4", "", "实现已完成，待批准写入"),
          element("p", "muted", "批准时会重新校验当前暂存区，并在提交成功后才允许推进下一任务。"),
        );
        const staged = element("ul");
        (selectedTask.staged_files?.length ? selectedTask.staged_files : ["当前暂存区为空"]).forEach(path => staged.append(element("li", "", path)));
        pendingCommit.append(staged);
        detail.append(pendingCommit);
      }
      const details = element("div", "task-details");
      [
        ["修改文件", selectedTask.expected_files],
        ["关键符号", selectedTask.symbols],
        ["实施步骤", selectedTask.steps],
        ["验收条件", selectedTask.acceptance],
        ["依赖任务", selectedTask.dependencies?.length ? selectedTask.dependencies : ["无"]],
      ].forEach(([label, values]) => {
        const section = element("section", "task-detail");
        section.append(element("h4", "", label));
        const list = element("ul");
        (values || [selectedTask.legacy ? "旧版快照未记录" : "未记录"]).forEach(value => list.append(element("li", "", value)));
        section.append(list);
        details.append(section);
      });
      detail.append(details);
      if (selectedTask.evidence) {
        const evidence = element("section", "task-evidence");
        evidence.append(element("h4", "", "完成证据"));
        Object.entries(selectedTask.evidence).forEach(([key, value]) => {
          evidence.append(element("p", "", `${key}：${typeof value === "string" ? value : JSON.stringify(value)}`));
        });
        detail.append(evidence);
      }
      if (selectedTask.checkpoint?.commit_sha) {
        const checkpoint = element("section", "task-evidence");
        checkpoint.append(
          element("h4", "", "任务提交"),
          element("p", "", `Commit：${selectedTask.checkpoint?.commit_sha}`),
          element("p", "", `Snapshot：${selectedTask.checkpoint?.snapshot_sha || "—"}`),
        );
        detail.append(checkpoint);
      }
    }
    workspace.append(taskList, detail);
    fragment.append(workspace);
  } else {
    fragment.append(emptyState("等待 Hammer Plan 进入编码父任务并生成 Cosh 细分任务。"));
  }
  fragment.append(artifactDisclosure(data, "coding", "编码产物"));
  return fragment;
}

function renderArtifacts(data) {
  const fragment = document.createDocumentFragment();
  fragment.append(viewHeader("全部产物", "活动工作区中的 Hammer 产物和入口目录中的 Cosh 插件产物。"));
  fragment.append(artifactList(data));
  return fragment;
}

function renderView(data) {
  const viewport = document.querySelector("#viewport");
  viewport.replaceChildren();
  const views = {
    overview: () => renderOverview(data),
    requirement: () => renderStage(data, "需求结论", "Hammer Stage 1 与 Cosh 需求入口产物。", "requirement"),
    design: () => renderStage(data, "技术设计", "Hammer 技术方案、发布与设计阶段证据。", "design"),
    review: () => renderReview(data),
    plan: () => renderStage(data, "Hammer 计划", "Hammer 正式计划、会话和交接证据。", "plan"),
    coding: () => renderCoding(data),
    validation: () => renderStage(data, "验证", "远程 UT、CI、CR、E2E 与 Gate 证据。", "validation"),
    delivery: () => renderStage(data, "交付", "Meego、报告、MR、验收与归档产物。", "delivery"),
    artifacts: () => renderArtifacts(data),
  };
  viewport.append(views[activeTab]());
  document.querySelectorAll("[data-tab]").forEach(button => {
    const selected = button.dataset.tab === activeTab;
    button.classList.toggle("active", selected);
    button.setAttribute("aria-selected", selected ? "true" : "false");
  });
}

function render(data) {
  currentData = data;
  document.querySelector("#summary").textContent = `${data.work} · ${data.hammer.stage} · ${data.hammer.status}`;
  document.querySelector("#connection").textContent = data.stale ? "缓存快照" : "实时连接";
  const warning = document.querySelector("#warning");
  warning.hidden = !data.stale;
  warning.textContent = data.stale ? `实时投影失败：${data.projection_error || "未知错误"}` : "";
  renderView(data);
}

async function refresh() {
  const response = await fetch(api("/api/status"), { cache: "no-store" });
  render(await response.json());
}

document.querySelectorAll("[data-tab]").forEach(button => button.addEventListener("click", () => {
  activeTab = button.dataset.tab;
  params.set("tab", activeTab);
  const query = params.toString();
  window.history.replaceState(null, "", `${window.location.pathname}${query ? `?${query}` : ""}`);
  if (currentData) renderView(currentData);
}));
document.querySelector("#close-artifact").addEventListener("click", closeArtifact);
document.querySelector("#artifact-viewer").addEventListener("click", event => {
  if (ArtifactFormatters.isBackdropClick(event.target, event.currentTarget)) closeArtifact();
});
document.querySelectorAll("[data-artifact-mode]").forEach(button => {
  button.addEventListener("click", () => {
    artifactMode = button.dataset.artifactMode;
    renderArtifactContent();
  });
});
document.querySelector("#copy-artifact").addEventListener("click", async event => {
  const button = event.currentTarget;
  try {
    await navigator.clipboard.writeText(artifactRaw);
    button.textContent = "已复制";
  } catch (_error) {
    button.textContent = "复制失败";
  }
  window.setTimeout(() => { button.textContent = "复制原文"; }, 1200);
});
document.addEventListener("keydown", event => {
  if (event.key === "Escape" && !document.querySelector("#artifact-viewer").hidden) closeArtifact();
});

refresh().catch(() => {});
const events = new EventSource(api("/events"));
events.addEventListener("status", event => render(JSON.parse(event.data)));
events.onerror = () => { document.querySelector("#connection").textContent = "正在重连"; };
