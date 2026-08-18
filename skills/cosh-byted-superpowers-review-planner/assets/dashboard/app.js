const app = document.querySelector("#app");
let latestData = null;
let availableWorks = [];
let connectionState = "live";
let feedback = "";
let selectedOverviewStage = null;
let projectionError = "";

const stageLabels = {
  source: "技术文档",
  knowledge_gate: "知识门禁",
  codegraph: "代码事实",
  review: "三路评审",
  review_closure: "评审闭环",
  spec: "规格",
  location: "精确定位",
  plan: "计划",
  implementation: "任务实现",
  remote_ut: "完整远程 UT",
  final_review: "最终 CR",
  push: "Push",
  archive: "归档",
};

const tabs = [
  ["overview", "总览"],
  ["source", "技术文档"],
  ["review", "评审"],
  ["spec", "规格"],
  ["plan", "计划"],
  ["validation", "验证"],
  ["tasks", "Tasks"],
];

const stageStatusMeta = {
  passed: { label: "已通过", icon: "✓" },
  running: { label: "进行中", icon: "●" },
  blocked: { label: "已阻塞", icon: "×" },
  pending: { label: "等待中", icon: "○" },
};

const sampleData = {
  work: "optimize-order-risk-check",
  version: "sample-v1",
  mode: "single",
  read_at: new Date().toISOString(),
  source: { version: 2, path: "technical-design.md" },
  knowledge_gate: { mode: "loaded", version: "AI-Spec 2026.08" },
  stages: {
    source: { status: "passed", blockers: [], fix: "" },
    knowledge_gate: { status: "passed", blockers: [], fix: "" },
    codegraph: { status: "passed", blockers: [], fix: "" },
    review: { status: "blocked", blockers: ["security Reviewer 未通过"], fix: "修改技术文档后重新评审" },
    review_closure: { status: "pending", blockers: ["三路评审尚未全部通过"], fix: "" },
    spec: { status: "pending", blockers: ["评审闭环尚未通过"], fix: "" },
    location: { status: "pending", blockers: [], fix: "" },
    plan: { status: "passed", blockers: [], fix: "" },
    implementation: { status: "running", blockers: [], fix: "" },
    remote_ut: { status: "pending", blockers: [], fix: "" },
    final_review: { status: "pending", blockers: [], fix: "" },
    push: { status: "pending", blockers: [], fix: "" },
    archive: { status: "pending", blockers: [], fix: "" },
  },
  reviews: {
    round: 2,
    reviewers: {
      stability: { status: "passed", stage: "ST9", updated_at: "14:20" },
      security: { status: "blocked", stage: "SEC5", updated_at: "14:32" },
      feasibility: { status: "passed", stage: "F8", updated_at: "14:25" },
    },
    findings: [{ reviewer: "security", id: "SEC-1", severity: "P0", title: "日志可能泄露订单标识", evidence: "internal/order/risk.go:52", recommendation: "复用脱敏函数后再记录" }],
    history: [],
  },
  tasks_total: 2,
  tasks_done: 0,
  tasks: [
    { number: 1, title: "增加内部重试判断", allowed_files: ["internal/order/risk.go"], status: "current" },
    { number: 2, title: "增加风险指标", allowed_files: ["internal/order/metric.go"], status: "waiting" },
  ],
  current_task: { number: 1, title: "增加内部重试判断", allowed_files: ["internal/order/risk.go"], remote_ut_passed: true, cr_passed: false, can_advance: false },
  documents: [
    { category: "source", label: "技术文档", path: ".superpowers/byted-work/optimize-order-risk-check/technical-design.md", content: "# 技术方案\n\n优化内部重试风险判断。" },
    { category: "spec", label: "规格", path: "docs/superpowers/specs/2026-08-02-optimize-order-risk-check-design.md", content: "# 规格\n\n当前为示例内容。" },
    { category: "plan", label: "计划", path: "docs/superpowers/plans/2026-08-02-optimize-order-risk-check.md", content: "# Plan\n\n### Task 1: 增加内部重试判断" },
  ],
};

const sampleWorks = [
  { name: "optimize-order-risk-check", source_version: 2 },
  { name: "add-order-audit-log", source_version: 1 },
];

function escapeHtml(value = "") {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function apiUrl(path, params = {}) {
  const url = new URL(path, window.location.href);
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") url.searchParams.set(key, value);
  });
  return `${url.pathname}${url.search}`;
}

function activeTab() {
  const value = new URL(window.location.href).searchParams.get("tab") || "overview";
  return tabs.some(([id]) => id === value) ? value : "overview";
}

function pageHref(tab, work = latestData?.work) {
  const url = new URL(window.location.href);
  url.searchParams.set("work", work);
  url.searchParams.set("tab", tab);
  url.searchParams.delete("document");
  return url.href;
}

function renderWorkSwitcher(data) {
  const works = availableWorks.length ? availableWorks : [{ name: data.work }];
  return `<label class="work-switcher"><span>开发任务</span><select id="work-select" aria-label="切换开发任务">${works.map(item => `<option value="${escapeHtml(item.name)}" ${item.name === data.work ? "selected" : ""}>${escapeHtml(item.name)}${item.source_version ? ` · v${item.source_version}` : ""}</option>`).join("")}</select></label>`;
}

function renderNavigation(data) {
  const current = activeTab();
  return `<nav class="main-nav" aria-label="研发产物导航">${tabs.map(([id, label]) => `<a class="nav-link ${id === current ? "active" : ""} ${id === "tasks" ? "task-nav" : ""}" href="${escapeHtml(pageHref(id, data.work))}">${label}</a>`).join("")}</nav>`;
}

function renderHeader(data) {
  const stale = data.stale === true || connectionState === "stale";
  const connection = data.sample ? "模板示例" : stale ? "持久化快照" : connectionState === "live" ? "实时连接" : "正在重连";
  const issue = data.projection_error || projectionError;
  return `<header class="top"><div>${renderWorkSwitcher(data)}<p class="eyebrow">BYTEDANCE · SUPERPOWERS</p><h1>${escapeHtml(data.work)}</h1></div><div class="connection ${stale ? "stale" : connectionState}"><strong>${connection}</strong><span>源版本 v${escapeHtml(data.source?.version || "-")}</span><span>${escapeHtml(data.read_at || "")}</span></div></header>${renderNavigation(data)}${issue ? `<p class="projection-warning" role="status">实时数据暂不可用，正在展示最后有效快照：${escapeHtml(issue)}</p>` : ""}`;
}

function stageCard(name, stage) {
  const value = stage || { status: "pending", blockers: [] };
  return `<article class="stage-card ${escapeHtml(value.status)}"><span>${escapeHtml(stageLabels[name] || name)}</span><strong>${escapeHtml(value.status)}</strong>${(value.blockers || []).length ? `<small>${escapeHtml(value.blockers[0])}</small>` : ""}</article>`;
}

function normalizedStageStatus(stage) {
  const status = stage?.status || "pending";
  return stageStatusMeta[status] ? status : "pending";
}

function defaultOverviewStage(stages) {
  if (!stages.length) return null;
  const requested = new URL(window.location.href).searchParams.get("stage");
  if (requested && stages.some(([name]) => name === requested)) selectedOverviewStage = requested;
  if (selectedOverviewStage && stages.some(([name]) => name === selectedOverviewStage)) return selectedOverviewStage;
  const active = stages.find(([, stage]) => stage?.status === "running" || stage?.status === "blocked");
  const incomplete = stages.find(([, stage]) => stage?.status !== "passed");
  selectedOverviewStage = (active || incomplete || stages[stages.length - 1])[0];
  return selectedOverviewStage;
}

function renderStageStepper(stages, selectedName) {
  if (!stages.length) return '<section class="stage-stepper panel"><p class="empty">尚无阶段数据</p></section>';
  return `<ol class="stage-stepper" aria-label="研发流程阶段">${stages.map(([name, stage]) => {
    const status = normalizedStageStatus(stage);
    const meta = stageStatusMeta[status];
    const selected = name === selectedName;
    const summary = stage?.blockers?.[0] || stage?.fix || meta.label;
    return `<li class="stage-step-item"><button type="button" class="stage-step ${escapeHtml(status)} ${selected ? "selected" : ""}" data-overview-stage="${escapeHtml(name)}" ${selected ? 'aria-current="step"' : ""}><span class="stage-status-icon" aria-hidden="true">${meta.icon}</span><span class="stage-step-copy"><strong>${escapeHtml(stageLabels[name] || name)}</strong><small>${escapeHtml(summary)}</small></span><span class="stage-status-text">${escapeHtml(stage?.status || "pending")}</span></button></li>`;
  }).join("")}</ol>`;
}

function stageDetailRow(label, value, className = "") {
  return `<div class="stage-detail-row ${className}"><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value || "未记录")}</dd></div>`;
}

function renderStageDetail(name, stage) {
  if (!name || !stage) return '<aside class="stage-detail panel"><p class="empty">选择一个阶段查看详情</p></aside>';
  const status = normalizedStageStatus(stage);
  const meta = stageStatusMeta[status];
  const rawStatus = stage.status || "pending";
  const canAdvance = stage.can_advance === true ? "是" : stage.can_advance === false ? "否" : "未记录";
  const blocker = stage.blockers?.[0] || (status === "passed" ? "无阻塞" : "未记录");
  const fix = stage.fix || (status === "passed" ? "无需修复" : "未记录");
  return `<aside class="stage-detail panel ${escapeHtml(status)}"><div class="stage-detail-heading"><div><p class="eyebrow">阶段详情</p><h2>${escapeHtml(stageLabels[name] || name)}</h2></div><span class="stage-detail-status"><i aria-hidden="true">${meta.icon}</i>${escapeHtml(rawStatus)}</span></div><dl>${stageDetailRow("阻塞原因", blocker, "blocker")}${stageDetailRow("修复建议", fix, "fix")}${stageDetailRow("证据版本", stage.version)}${stageDetailRow("更新时间", stage.updated_at)}${stageDetailRow("允许继续", canAdvance)}</dl></aside>`;
}

function renderOverview(data) {
  const stages = Object.entries(data.stages || {});
  const current = stages.find(([, stage]) => stage.status === "running" || stage.status === "blocked") || stages.find(([, stage]) => stage.status !== "passed");
  const selectedName = defaultOverviewStage(stages);
  const selectedStage = stages.find(([name]) => name === selectedName)?.[1];
  const progress = data.primary_progress || { label: "Task", done: data.tasks_done || 0, total: data.tasks_total || 0 };
  const progressPercent = progress.total ? Math.round(progress.done / progress.total * 100) : 0;
  return `<section class="panel hero"><div><p class="eyebrow">当前阶段</p><h2>${escapeHtml(current ? stageLabels[current[0]] : "已完成")}</h2><p>${escapeHtml(current?.[1]?.fix || current?.[1]?.blockers?.[0] || "等待下一项状态更新")}</p></div><div><strong>${escapeHtml(progress.label)} ${escapeHtml(progress.done)} / ${escapeHtml(progress.total)}</strong><div class="progress"><i style="width:${progressPercent}%"></i></div></div></section><section class="overview-workflow">${renderStageStepper(stages, selectedName)}${renderStageDetail(selectedName, selectedStage)}</section>`;
}

function reviewerLabel(name) {
  return ({ stability: "稳定性", security: "安全性", feasibility: "可行性" })[name] || name;
}

function reviewFindingView(finding) {
  const title = finding.title || finding.problem || "未提供风险描述";
  const recommendation = finding.recommendation || finding.suggestion || "未提供修改建议";
  const evidenceItems = Array.isArray(finding.evidence) ? finding.evidence.filter(Boolean) : [finding.evidence].filter(Boolean);
  const evidence = evidenceItems.length ? evidenceItems.join("\n") : "未提供（评审证据格式不完整）";
  const schemaErrors = Array.isArray(finding.schema_errors) ? finding.schema_errors.filter(Boolean) : [];
  return { title, recommendation, evidence, schemaErrors };
}

function findingSeverityClass(finding) {
  const severity = String(finding.severity || "").toLowerCase();
  return ["p0", "p1", "p2", "p3"].includes(severity) ? `severity-${severity}` : "severity-unknown";
}

function findingBlockingControl(finding, stale) {
  const active = ["open", "pending", "pending_confirmation"].includes(finding.status);
  if (!active) return '<span class="finding-state resolved">已闭合</span>';
  if (finding.severity === "P0") return '<span class="finding-state forced">强制阻塞</span>';
  if (finding.waiver) {
    return `<div class="finding-waiver"><span class="finding-state waived">已设为不阻塞</span><small>原因：${escapeHtml(finding.waiver.reason)}</small><button class="finding-action" data-restore-finding="${escapeHtml(finding.finding_key)}" ${stale ? "disabled" : ""}>恢复阻塞</button></div>`;
  }
  if (finding.can_override) {
    return `<button class="finding-action" data-waive-finding="${escapeHtml(finding.finding_key)}" ${stale ? "disabled" : ""}>设为不阻塞</button>`;
  }
  return `<span class="finding-state ${finding.effective_blocking ? "forced" : "waived"}">${finding.effective_blocking ? "阻塞" : "不阻塞"}</span>`;
}

function renderReview(data) {
  const reviews = data.reviews || { reviewers: {}, findings: [], history: [] };
  return `<section class="panel"><div class="section-title"><div><p class="eyebrow">REVIEW ROUND ${escapeHtml(reviews.round || "-")}</p><h2>稳定性、安全性与可行性评审</h2></div><span class="knowledge-mode">${escapeHtml(data.knowledge_gate?.mode || "missing")} · ${escapeHtml(data.knowledge_gate?.version || "")}</span></div><p class="feedback" aria-live="polite">${escapeHtml(feedback)}</p><div class="review-grid">${Object.entries(reviews.reviewers || {}).map(([name, review]) => {
    const status = review.effective_status || review.status;
    return `<article class="review-track ${escapeHtml(status)}"><strong>${reviewerLabel(name)}</strong><span>${escapeHtml(status)}</span><small>${escapeHtml(review.stage || "")}</small></article>`;
  }).join("") || '<p class="empty">等待三路评审</p>'}</div><div class="risk-list"><h3>风险点</h3>${(reviews.findings || []).map(finding => {
    const view = reviewFindingView(finding);
    const severityClass = findingSeverityClass(finding);
    return `<article class="risk ${severityClass} ${view.schemaErrors.length ? "schema-invalid" : ""}"><div><strong>${escapeHtml(finding.id)} · ${escapeHtml(view.title)}</strong><span class="severity-badge ${severityClass}">${escapeHtml(finding.severity || "")}</span></div>${view.schemaErrors.length ? `<p class="schema-warning">硬门禁：${escapeHtml(view.schemaErrors.join("；"))}</p>` : ""}<dl><dt>证据</dt><dd><code>${escapeHtml(view.evidence)}</code></dd><dt>应该怎么修改</dt><dd>${escapeHtml(view.recommendation)}</dd></dl><div class="finding-control">${findingBlockingControl(finding, data.stale)}</div></article>`;
  }).join("") || '<p class="empty">当前没有未关闭风险点</p>'}</div><button class="secondary-button" id="request-revision" ${data.stale ? "disabled" : ""}>修改技术文档并重新评审</button></section>`;
}

function documentsFor(data, category) {
  return (data.documents || []).filter(document => document.category === category);
}

function renderDocumentTab(data, category) {
  const documents = documentsFor(data, category);
  const requested = new URL(window.location.href).searchParams.get("document");
  const selected = documents.find(document => document.path === requested) || documents[0];
  return `<section class="panel document-layout"><aside>${documents.map(document => `<button class="document-link ${document === selected ? "active" : ""}" data-document="${escapeHtml(document.path)}">${escapeHtml(document.label)}<small>${escapeHtml(document.path)}</small></button>`).join("") || '<p class="empty">当前阶段尚无产物</p>'}</aside><article><div class="document-heading"><code>${escapeHtml(selected?.path || "未选择文件")}</code><span>实时只读</span></div><pre id="document-content">${selected ? "正在读取…" : "尚无内容"}</pre></article></section>`;
}

function renderValidation(data) {
  const items = ["remote_ut", "final_review", "push", "archive"];
  return `<section class="panel"><div class="section-title"><h2>验证与交付</h2><button class="secondary-button" id="archive-work" ${data.stale ? "disabled" : ""}>手动归档</button></div><div class="validation-list">${items.map(name => stageCard(name, data.stages?.[name])).join("")}</div></section>`;
}

function modeControl(data) {
  const disabled = data.stale ? "disabled" : "";
  return `<div class="mode-control"><div><p class="eyebrow">推进方式</p><strong>${data.mode === "continuous" ? "连续推进" : "逐一任务校验"}</strong></div><div class="segmented"><button data-mode="single" ${disabled} class="${data.mode === "single" ? "active" : ""}">逐一任务校验</button><button data-mode="continuous" ${disabled} class="${data.mode === "continuous" ? "active" : ""}">连续推进</button></div></div>`;
}

function renderTasks(data) {
  return `<section class="panel task-panel">${modeControl(data)}<p class="feedback" aria-live="polite">${escapeHtml(feedback)}</p><div class="task-list">${(data.tasks || []).map(task => { const current = data.current_task?.number === task.number; const advance = current && data.mode !== "continuous" ? `<button id="advance-next" class="advance-button" ${data.current_task.can_advance ? "" : "disabled"}>推进下一个任务</button>` : `<span class="task-state">${task.status === "completed" ? "已完成" : task.status === "current" ? "当前任务" : "等待中"}</span>`; return `<article class="task-row ${escapeHtml(task.status)}"><span class="task-index">TASK ${task.number}</span><div><strong>${escapeHtml(task.title)}</strong><small>${(task.allowed_files || []).map(escapeHtml).join(" · ")}</small></div>${advance}</article>`; }).join("") || '<p class="empty">尚未生成实施子任务</p>'}</div></section>`;
}

function render(data) {
  latestData = data;
  const tab = activeTab();
  let content = "";
  if (tab === "overview") content = renderOverview(data);
  else if (tab === "review") content = renderReview(data);
  else if (tab === "tasks") content = renderTasks(data);
  else if (tab === "validation") content = renderValidation(data);
  else content = renderDocumentTab(data, tab);
  app.innerHTML = `${renderHeader(data)}<main class="content">${content}</main>`;
  bindInteractions(data, tab);
}

function bindInteractions(data, tab) {
  document.querySelector("#work-select")?.addEventListener("change", event => {
    window.location.href = pageHref(activeTab(), event.target.value);
  });
  document.querySelectorAll("[data-mode]").forEach(button => button.addEventListener("click", () => {
    if (button.dataset.mode !== data.mode) updateControl(data, "set-mode", { mode: button.dataset.mode });
  }));
  document.querySelector("#advance-next")?.addEventListener("click", () => {
    const task = data.current_task;
    updateControl(data, "advance-next", { expected_task: task.number, commit_type: guessCommitType(task.title), summary: task.title });
  });
  document.querySelector("#request-revision")?.addEventListener("click", () => updateControl(data, "request-source-revision"));
  document.querySelectorAll("[data-waive-finding]").forEach(button => button.addEventListener("click", () => {
    const reason = window.prompt("请输入设为不阻塞的原因（必填）", "")?.trim();
    if (!reason) {
      feedback = "未设置：设为不阻塞必须填写原因";
      render(data);
      return;
    }
    updateControl(data, "set-finding-blocking", { finding_key: button.dataset.waiveFinding, blocking: false, reason });
  }));
  document.querySelectorAll("[data-restore-finding]").forEach(button => button.addEventListener("click", () => {
    updateControl(data, "set-finding-blocking", { finding_key: button.dataset.restoreFinding, blocking: true });
  }));
  document.querySelector("#archive-work")?.addEventListener("click", () => updateControl(data, "archive"));
  document.querySelectorAll("[data-document]").forEach(button => button.addEventListener("click", () => {
    const url = new URL(window.location.href);
    url.searchParams.set("document", button.dataset.document);
    window.history.replaceState(null, "", url.href);
    render(data);
  }));
  if (tab === "overview") document.querySelectorAll("[data-overview-stage]").forEach(button => button.addEventListener("click", () => {
    selectedOverviewStage = button.dataset.overviewStage;
    const url = new URL(window.location.href);
    url.searchParams.set("stage", selectedOverviewStage);
    window.history.replaceState(null, "", url.href);
    render(data);
  }));
  if (["source", "spec", "plan"].includes(tab)) loadSelectedDocument(data, tab);
}

function guessCommitType(title = "") {
  if (title.includes("修复")) return "fix";
  if (title.includes("重构")) return "refactor";
  if (title.includes("测试")) return "test";
  if (title.includes("文档")) return "docs";
  return "feat";
}

function idempotencyKey() {
  return globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random()}`;
}

async function updateControl(data, action, extra = {}) {
  if (data.stale) {
    feedback = "实时证据不可用，已禁止修改状态";
    render(data);
    return;
  }
  if (data.sample) {
    feedback = "模板模式不会写入仓库";
    render(data);
    return;
  }
  feedback = "正在校验门禁并更新状态…";
  render(data);
  try {
    const response = await fetch("/api/control", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action, work: data.work, expected_version: data.version, idempotency_key: idempotencyKey(), ...extra }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
    feedback = "状态已更新";
    render(payload);
  } catch (error) {
    feedback = `更新失败：${error.message}`;
    render(data);
  }
}

async function loadSelectedDocument(data, category) {
  const documents = documentsFor(data, category);
  const requested = new URL(window.location.href).searchParams.get("document");
  const selected = documents.find(document => document.path === requested) || documents[0];
  const target = document.querySelector("#document-content");
  if (!selected || !target) return;
  if (data.sample) {
    target.textContent = selected.content || "模板内容";
    return;
  }
  try {
    const response = await fetch(apiUrl("/api/document", { work: data.work, path: selected.path }), { cache: "no-store" });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
    target.textContent = payload.content;
  } catch (error) {
    target.textContent = `读取失败：${error.message}`;
  }
}

function renderError(message) {
  app.innerHTML = `<section class="error"><strong>观察板读取失败</strong><p>${escapeHtml(message)}</p></section>`;
}

async function fetchWorks() {
  const response = await fetch("/api/works", { cache: "no-store" });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
  availableWorks = payload.works || [];
  return payload;
}

function connectLive(work) {
  const source = new EventSource(apiUrl("/events", { work }));
  source.addEventListener("open", () => { if (!latestData?.stale) connectionState = "live"; if (latestData) render(latestData); });
  source.addEventListener("status", event => {
    const data = JSON.parse(event.data);
    projectionError = data.projection_error || "";
    connectionState = data.stale ? "stale" : "live";
    render(data);
  });
  source.addEventListener("read-error", event => {
    projectionError = JSON.parse(event.data).error;
    connectionState = "stale";
    if (latestData) render({ ...latestData, stale: true, projection_error: projectionError });
    else renderError(projectionError);
  });
  source.addEventListener("error", () => { connectionState = "reconnecting"; if (latestData) render(latestData); });
}

async function initialize() {
  try {
    const catalog = await fetchWorks();
    const url = new URL(window.location.href);
    const requested = url.searchParams.get("work");
    const work = availableWorks.some(item => item.name === requested) ? requested : catalog.default_work;
    url.searchParams.set("work", work);
    if (!url.searchParams.get("tab")) url.searchParams.set("tab", "overview");
    window.history.replaceState(null, "", url.href);
    connectLive(work);
  } catch (error) {
    renderError(error.message);
  }
}

if (window.location.protocol === "file:") {
  sampleData.sample = true;
  availableWorks = sampleWorks;
  const url = new URL(window.location.href);
  if (!url.searchParams.get("work")) url.searchParams.set("work", sampleData.work);
  if (!url.searchParams.get("tab")) url.searchParams.set("tab", "overview");
  window.history.replaceState(null, "", url.href);
  render(sampleData);
} else {
  initialize();
}
