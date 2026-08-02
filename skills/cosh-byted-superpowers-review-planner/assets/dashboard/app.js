const app = document.querySelector("#app");
let connectionState = "live";
let latestData = null;
let activeCategory = null;
let activeDocumentPath = null;
let controlFeedback = "";
let availableChanges = [];
const documentCache = new Map();
const categoryOrder = ["spec", "review", "design", "tasks", "validation", "analysis"];
const artifactSectionOrder = ["proposal", "spec", "analysis", "design", "review", "validation", "tasks"];
const artifactSectionLabels = {
  proposal: "Proposal",
  spec: "规格",
  analysis: "修改点",
  design: "Design",
  review: "评审",
  tasks: "Tasks",
  validation: "验证",
};

const sampleData = {
  change: "optimize-order-risk-check",
  source: "示例数据 · openspec/changes/optimize-order-risk-check",
  read_at: "刚刚",
  source_updated_at: "14:32:08",
  stage: "任务实现",
  next_gate: "完成当前 Task 的 BITS 远程 UT，并在 Tasks 页等待 CR 放行",
  sample: true,
  gates: [
    { name: "技术文档准入", kind: "manual", state: "done", label: "技术文档快照已冻结" },
    { name: "AI-Spec 知识加载", kind: "automatic", state: "done", label: "自动校验通过" },
    { name: "三路独立评审", kind: "review", state: "blocked", label: "3 条未通过" },
    { name: "评审闭环确认", kind: "manual", state: "pending", label: "等待阻塞项闭环" },
    { name: "OpenSpec 规格", kind: "manual", state: "done", label: "人工决策已完成" },
    { name: "CodeGraph 修改点", kind: "manual", state: "done", label: "人工决策已完成" },
    { name: "Design 与 Tasks", kind: "manual", state: "done", label: "人工决策已完成" },
    { name: "BITS 远程 UT", kind: "automatic", state: "ready", label: "当前待处理" },
    { name: "交付与归档", kind: "manual", state: "pending", label: "等待远程验证" },
  ],
  modification_points: [
    {
      id: "MP-1",
      scenario: "内部重试跳过重复风控",
      file: "internal/order/risk_checker.go:128",
      symbol: "(*RiskChecker).ShouldSkip",
      variable: "riskScene",
      type: "model.RiskScene",
      target: "仅在 SceneInternalRetry 时跳过重复风控；其他场景保持原行为",
    },
    {
      id: "MP-2",
      scenario: "记录跳过风控的可观测原因",
      file: "internal/order/risk_metrics.go:46",
      symbol: "emitRiskDecision",
      variable: "skipReason",
      type: "string",
      target: "为内部重试写入稳定原因枚举，并保持指标基数有界",
    },
  ],
  reviews: {
    status: "blocked",
    stage: "稳定性评审 · ST4 缓存与数据生命周期；安全性评审 · SEC3 数据安全；可行性评审 · F3 基建复用",
    required_reviewers: ["stability", "security", "feasibility"],
    missing_reviewers: [],
    failed_count: 3,
    blocking_count: 1,
    tracks: [
      { reviewer: "stability", name: "稳定性评审", status: "running", round: 2, document_version: "tech-design-a61f9c2", review_scope: "closure", stage: "ST4 缓存与数据生命周期", completed: 3, total: 9, summary: "正在复评重试状态的过期与回收策略", updated_at: "14:31:22", artifact: "reviews/stability.md" },
      { reviewer: "security", name: "安全性评审", status: "blocked", round: 2, document_version: "tech-design-a61f9c2", review_scope: "closure", stage: "SEC3 数据安全", completed: 3, total: 8, summary: "复评后日志字段仍存在敏感信息风险", updated_at: "14:32:08", artifact: "reviews/security.md" },
      { reviewer: "feasibility", name: "可行性评审", status: "passed", round: 1, document_version: "tech-design-9e7b130", review_scope: "full", stage: "F8 任务可实施性", completed: 8, total: 8, summary: "第 1 轮已通过，本轮修改未影响可行性边界", updated_at: "14:10:18", artifact: "reviews/feasibility.md" },
    ],
    open_failed: [
      { id: "SEC-SEC5-001", reviewer: "security", reviewer_name: "安全性", check: "SEC5", status: "failed", severity: "P0", blocking: true, title: "日志可能记录原始订单标识", evidence: "emitRiskDecision 直接写入 request.OrderID", location: "internal/order/risk_metrics.go:52 · orderID", recommendation: "复用现有脱敏函数 MaskOrderID，并只记录脱敏后的有界值", closure: "open", updated_at: "14:32:08", artifact: "reviews/security.md" },
      { id: "STAB-ST3-002", reviewer: "stability", reviewer_name: "稳定性", check: "ST3", status: "failed", severity: "P1", blocking: false, title: "新增指标缺少基数上限证据", evidence: "skipReason 当前接受任意 string", location: "internal/order/risk_metrics.go:46 · skipReason", recommendation: "将 skipReason 收敛为已有原因枚举并补充未知值兜底", closure: "open", updated_at: "14:30:41", artifact: "reviews/stability.md" },
      { id: "FEAS-F3-001", reviewer: "feasibility", reviewer_name: "可行性", check: "F3", status: "failed", severity: "P1", blocking: false, title: "方案重复实现现有场景判断能力", evidence: "riskpolicy 包已提供 IsInternalRetry", location: "internal/order/risk_checker.go:128 · riskScene", recommendation: "复用 riskpolicy.IsInternalRetry，仅新增最小调用接入", closure: "open", updated_at: "14:32:18", artifact: "reviews/feasibility.md" },
    ],
    findings: [],
    round: 2,
    document_version: "tech-design-a61f9c2",
    retry_reviewers: ["stability", "security"],
    revision_available: true,
  },
  ai_spec: {
    status: "loaded",
    version: "AI-Spec 2026.08",
    message: "AI-Spec 知识门禁已通过",
    missing_roles: [],
    invalid_sources: [],
    sources: [
      { role: "stability_skill", path: ".trae/skills/ai_spec_stability/SKILL.md" },
      { role: "stability_spec", path: ".ai_spec/specification/stability.md" },
      { role: "security_skill", path: ".trae/skills/ai_spec_security/SKILL.md" },
      { role: "security_spec", path: ".ai_spec/specification/security.md" },
      { role: "general_components", path: ".trae/skills/ai_spec_general_components/SKILL.md" },
      { role: "lark_general_knowledge", path: ".trae/skills/ai_spec_lark_general_knowledge/SKILL.md" },
      { role: "code_review", path: ".ai_spec/specification/code_review.md" },
    ],
  },
  tasks: {
    total: 6,
    done: 4,
    source_path: "tasks.md",
    version: "sample-tasks-1",
    execution_control: { mode: "single", sequence: 1 },
    items: [
      { done: true, text: "补充 ShouldSkip 当前行为基线测试" },
      { done: true, text: "增加 SceneInternalRetry 场景常量" },
      { done: true, text: "调整 riskScene 分支判断" },
      { done: true, text: "增加 skipReason 指标维度" },
      { done: false, text: "运行 package 定点单测并整理 CR 证据" },
      { done: false, text: "执行回归验证并确认监控指标" },
    ],
  },
  artifacts: [
    { path: "proposal.md", updated_at: "今天 10:18" },
    { path: "specs/order-risk/spec.md", updated_at: "今天 10:42" },
    { path: "analysis/modification-points.md", updated_at: "今天 11:26" },
    { path: "design.md", updated_at: "今天 12:05" },
    { path: "reviews/stability.md", updated_at: "今天 14:31" },
    { path: "reviews/security.md", updated_at: "今天 14:32" },
    { path: "reviews/feasibility.md", updated_at: "今天 14:32" },
    { path: "tasks.md", updated_at: "今天 14:32" },
    { path: "validation/targeted-test.md", updated_at: "今天 14:35" },
  ],
  documents: [
    { path: "proposal.md", category: "spec", category_label: "规格", point_ids: ["MP-1", "MP-2"], updated_at: "今天 10:18", version: "sample-1", content: "# Proposal\n\n为内部重试增加明确的风控跳过语义，并补充可观测原因。" },
    { path: "specs/order-risk/spec.md", category: "spec", category_label: "规格", point_ids: ["MP-1", "MP-2"], updated_at: "今天 10:42", version: "sample-2", content: "# Order Risk Specification\n\n## Scenario: 内部重试跳过重复风控\n\nGiven riskScene = SceneInternalRetry..." },
    { path: "analysis/modification-points.md", category: "analysis", category_label: "代码证据", point_ids: ["MP-1", "MP-2"], updated_at: "今天 11:26", version: "sample-3", content: "修改点 ID：MP-1\n文件：internal/order/risk_checker.go:128\n变量：riskScene\n\n修改点 ID：MP-2\n文件：internal/order/risk_metrics.go:46\n变量：skipReason" },
    { path: "design.md", category: "design", category_label: "Design", point_ids: ["MP-1", "MP-2"], updated_at: "今天 12:05", version: "sample-4", content: "# Design\n\n## MP-1\n在 ShouldSkip 内收窄跳过条件。\n\n## MP-2\n使用有界原因枚举补充指标。" },
    { path: "reviews/stability.md", category: "review", category_label: "评审", point_ids: ["MP-1", "MP-2"], updated_at: "今天 14:31", version: "sample-review-1", content: "# 稳定性评审\n\n当前检查：ST4 缓存与数据生命周期\n\n未通过：新增指标缺少基数上限证据。" },
    { path: "reviews/security.md", category: "review", category_label: "评审", point_ids: ["MP-2"], updated_at: "今天 14:32", version: "sample-review-2", content: "# 安全性评审\n\n当前检查：SEC3 数据安全\n\n未通过：日志可能记录原始订单标识。" },
    { path: "reviews/feasibility.md", category: "review", category_label: "评审", point_ids: ["MP-1"], updated_at: "今天 14:32", version: "sample-review-3", content: "# 可行性评审\n\n当前检查：F3 基建复用\n\n未通过：方案重复实现现有场景判断能力。" },
    { path: "tasks.md", category: "tasks", category_label: "Tasks", point_ids: ["MP-1", "MP-2"], updated_at: "今天 14:32", version: "sample-5", content: "- [x] 调整 riskScene 分支判断\n- [x] 增加 skipReason 指标维度\n- [ ] 运行定点单测\n- [ ] 回归验证" },
    { path: "validation/targeted-test.md", category: "validation", category_label: "验证", point_ids: ["MP-1", "MP-2"], updated_at: "今天 14:35", version: "sample-6", content: "# 定点验证\n\n状态：等待执行\n\n范围：risk_checker package 单测与 skipReason 指标断言。" },
  ],
};

const secondSampleData = JSON.parse(JSON.stringify(sampleData));
secondSampleData.change = "add-order-audit-log";
secondSampleData.source = "示例数据 · openspec/changes/add-order-audit-log";
secondSampleData.stage = "技术文档准入评审";
secondSampleData.next_gate = "处理审计日志字段与脱敏策略的阻塞结论";
secondSampleData.tasks.done = 1;
secondSampleData.tasks.execution_control = { mode: "single", sequence: 0 };
secondSampleData.tasks.items = secondSampleData.tasks.items.map((task, index) => ({
  ...task,
  done: index === 0,
  text: ["补充审计日志规格测试", "定义 auditEvent 结构", "接入订单创建调用链", "增加敏感字段脱敏", "运行定点单测并整理 CR 证据", "执行回归验证"][index],
}));

const sampleStatuses = {
  [sampleData.change]: sampleData,
  [secondSampleData.change]: secondSampleData,
};
const sampleChanges = Object.values(sampleStatuses).map(status => ({
  name: status.change,
  stage: status.stage,
  tasks_done: status.tasks.done,
  tasks_total: status.tasks.total,
}));

const escapeHtml = (value = "") => String(value)
  .replaceAll("&", "&amp;")
  .replaceAll("<", "&lt;")
  .replaceAll(">", "&gt;")
  .replaceAll('"', "&quot;")
  .replaceAll("'", "&#039;");

const list = (items, renderItem, empty) => items.length
  ? items.map(renderItem).join("")
  : `<p class="empty">${escapeHtml(empty)}</p>`;

function pageHref({ point = null, artifact = null } = {}) {
  const url = new URL(window.location.href);
  url.searchParams.delete("point");
  url.searchParams.delete("artifact");
  if (point) url.searchParams.set("point", point);
  if (artifact) url.searchParams.set("artifact", artifact);
  return url.href;
}

function artifactSection(documentMeta) {
  const path = documentMeta.path.toLowerCase();
  if (path.includes("proposal")) return "proposal";
  if (documentMeta.category === "spec") return "spec";
  return documentMeta.category;
}

function renderArtifactNav(data, activeSection = "overview") {
  const documents = data.documents || [];
  const sections = artifactSectionOrder.map(section => ({
    section,
    documents: documents.filter(doc => artifactSection(doc) === section),
  })).filter(item => item.documents.length);
  return `<nav class="artifact-nav" aria-label="OpenSpec 产物导航">
    <a class="artifact-nav-link ${activeSection === "overview" ? "active" : ""}" href="${escapeHtml(pageHref())}">总览</a>
    ${sections.map(({ section, documents: items }) => `<a class="artifact-nav-link ${section === "tasks" ? "task-primary" : ""} ${activeSection === section ? "active" : ""}" href="${escapeHtml(pageHref({ artifact: items[0].path }))}"><span>${artifactSectionLabels[section]}</span>${items.length > 1 ? `<small>${items.length}</small>` : ""}</a>`).join("")}
  </nav>`;
}

function renderChangeSwitcher(data) {
  const choices = availableChanges.length ? availableChanges : [{ name: data.change }];
  return `<label class="change-switcher">
    <span>Active Change</span>
    <select id="change-select" aria-label="切换 OpenSpec change">
      ${choices.map(item => `<option value="${escapeHtml(item.name)}" ${item.name === data.change ? "selected" : ""}>${escapeHtml(item.name)}${item.stage ? ` · ${escapeHtml(item.stage)}` : ""}${Number.isInteger(item.tasks_total) ? ` · ${item.tasks_done}/${item.tasks_total}` : ""}</option>`).join("")}
    </select>
  </label>`;
}

function bindChangeSwitcher() {
  const select = document.querySelector("#change-select");
  if (!select) return;
  select.addEventListener("change", () => {
    const url = new URL(window.location.href);
    url.searchParams.set("change", select.value);
    url.searchParams.delete("point");
    url.searchParams.delete("artifact");
    window.location.href = url.href;
  });
}

function apiUrl(path, params = {}) {
  const url = new URL(path, window.location.href);
  Object.entries(params).forEach(([key, value]) => {
    if (value) url.searchParams.set(key, value);
  });
  return `${url.pathname}${url.search}`;
}

function connectionMarkup(data) {
  const label = data.sample ? "模板示例" : connectionState === "live" ? "实时连接" : "正在重连";
  const state = data.sample ? "sample" : connectionState;
  return `<div class="meta"><span class="live ${state}">${label}</span><br>页面读取：${escapeHtml(data.read_at)}<br>源更新：${escapeHtml(data.source_updated_at || "暂无")}</div>`;
}

function render(data) {
  latestData = data;
  const params = new URL(window.location.href).searchParams;
  const selectedArtifact = params.get("artifact");
  if (selectedArtifact) {
    const documentMeta = (data.documents || []).find(item => item.path === selectedArtifact);
    if (!documentMeta) {
      renderError(`找不到产物：${selectedArtifact}`);
      return;
    }
    renderArtifactPage(data, documentMeta);
    return;
  }
  const selectedId = params.get("point");
  if (selectedId) {
    const point = data.modification_points.find(item => item.id === selectedId);
    if (!point) {
      renderError(`找不到修改点：${selectedId}`);
      return;
    }
    renderPointPage(data, point);
    return;
  }
  renderOverview(data);
}

function renderOverview(data) {
  const percent = data.tasks.total ? Math.round(data.tasks.done / data.tasks.total * 100) : 0;
  const reviewRisks = data.reviews?.open_failed || [];
  const reviewDocument = (data.documents || []).find(doc => artifactSection(doc) === "review");
  app.innerHTML = `
    <header class="top">
      <div>${renderChangeSwitcher(data)}<p class="eyebrow">OpenSpec · Change Overview</p><h1>${escapeHtml(data.change)}</h1></div>
      ${connectionMarkup(data)}
    </header>
    ${renderArtifactNav(data)}
    <section class="grid">
      <article class="card hero-card">
        <div><div class="stage">当前阶段 · ${escapeHtml(data.stage)}</div><p class="next">下一步：${escapeHtml(data.next_gate)}</p></div>
        <div><strong>Task 进度 ${percent}%</strong><div class="progress-track"><div class="progress-fill" style="width:${percent}%"></div></div><div class="progress-copy">${data.tasks.done} / ${data.tasks.total} 已完成</div></div>
      </article>
      ${renderReviewCenter(data, true)}
      <article class="card"><h2>研发流程检查点</h2><p class="checkpoint-note">人工决策、自动门禁与独立评审分别判定；逐 Task CR 仅在 Tasks 页处理。</p><div class="gates">${data.gates.map((gate, i) => `<div class="gate"><span class="gate-index">${String(i + 1).padStart(2, "0")}</span><span class="gate-name">${escapeHtml(gate.name)}<small class="gate-kind ${escapeHtml(gate.kind || "manual")}">${escapeHtml(({ manual: "人工决策", automatic: "自动门禁", review: "独立评审" })[gate.kind] || "人工决策")}</small></span><span class="status ${escapeHtml(gate.state)}">${escapeHtml(gate.label)}</span></div>`).join("")}</div></article>
      <article class="card risk-card"><h2>风险点 · ${reviewRisks.length}</h2><div class="risk-points">${list(reviewRisks, risk => `<article class="risk-point ${risk.blocking ? "blocking" : ""}"><div class="risk-point-title"><strong>${escapeHtml(risk.id)} · ${escapeHtml(risk.title)}</strong><span>${escapeHtml(risk.severity)}${risk.blocking ? " · 阻断" : ""}</span></div><div class="kv"><b>评审项</b><span>${escapeHtml(risk.reviewer_name)} · ${escapeHtml(risk.check)}</span><b>风险位置</b><code>${escapeHtml(risk.location)}</code><b>处理建议</b><span>${escapeHtml(risk.recommendation)}</span></div>${reviewDocument ? `<a class="open-point" href="${escapeHtml(pageHref({ artifact: reviewDocument.path }))}">查看评审详情 →</a>` : ""}</article>`, data.reviews?.status === "passed" ? "评审已通过，目前没有未闭环风险" : "评审暂未发现需要处理的风险")}</div></article>
      <article class="card wide"><h2>数据源</h2><code>${escapeHtml(data.source)}</code></article>
    </section>`;
  bindChangeSwitcher();
}

function reviewStatusLabel(status) {
  return ({ not_started: "未开始", running: "进行中", blocked: "有未通过项", passed: "已通过", failed: "未通过" })[status] || status;
}

function renderReviewCenter(data, compact = false) {
  const reviews = data.reviews || { status: "not_started", tracks: [], open_failed: [], failed_count: 0, blocking_count: 0, stage: "等待评审启动" };
  const aiSpec = data.ai_spec || { status: "missing", version: "", message: "尚未记录 AI-Spec 知识加载证据", missing_roles: [], invalid_sources: [], sources: [] };
  const tracks = reviews.tracks || [];
  const findings = reviews.open_failed || [];
  const reviewerNames = { stability: "稳定性", security: "安全性", feasibility: "可行性" };
  const retryNames = (reviews.retry_reviewers || []).map(item => reviewerNames[item] || item).join("、");
  const aiSpecLabel = aiSpec.status === "loaded" ? "已通过" : aiSpec.status === "fallback" ? "通用规则降级" : "未通过";
  const aiSpecDetail = aiSpec.status === "loaded"
    ? `已校验 ${aiSpec.sources?.length || 0} 个知识源及文件哈希`
    : aiSpec.status === "fallback"
      ? `自动接入失败：${aiSpec.failure_reason || "原因未记录"}`
      : [...(aiSpec.missing_roles || []), ...(aiSpec.invalid_sources || [])].join("；") || "评审不得启动";
  return `<section class="card review-center ${compact ? "wide" : ""}">
    <div class="review-heading">
      <div><p class="eyebrow">Live Review · 第 ${escapeHtml(reviews.round || 1)} 轮</p><h2>稳定性、安全性与可行性评审</h2><p class="review-current">${escapeHtml(reviews.stage)}</p><small class="review-version">技术方案版本：${escapeHtml(reviews.document_version || "未记录")}</small></div>
      <div class="review-summary"><strong>${reviews.failed_count || 0}</strong><span>未通过</span><strong>${reviews.blocking_count || 0}</strong><span>阻断</span></div>
    </div>
    <div class="ai-spec-gate ${escapeHtml(aiSpec.status)}"><div><strong>AI-Spec 知识门禁 · ${aiSpecLabel}</strong><span>${escapeHtml(aiSpec.version || "未发现版本")}</span></div><p>${escapeHtml(aiSpec.message)}</p><small>${escapeHtml(aiSpecDetail)}</small></div>
    <div class="review-tracks">${list(tracks, track => {
      const percent = track.total ? Math.round(track.completed / track.total * 100) : 0;
      return `<article class="review-track ${escapeHtml(track.status)}"><div class="review-track-title"><strong>${escapeHtml(track.name)}</strong><span>${escapeHtml(reviewStatusLabel(track.status))}</span></div><p>${escapeHtml(track.stage)}</p><div class="review-progress"><i style="width:${percent}%"></i></div><small>${track.completed} / ${track.total} · ${escapeHtml(track.summary || "等待结论")}</small></article>`;
    }, "尚未写入评审状态")}</div>
    ${reviews.revision_available ? `<div class="review-revision"><strong>可选操作 · 修改技术方案后继续复评</strong><p>根据未通过结论修改对应章节；完成后进入第 ${(reviews.round || 1) + 1} 轮，默认复评：${escapeHtml(retryNames || "存在未通过项的 Reviewer")}。如修改影响其他评审边界，会自动扩大复评范围。</p></div>` : ""}
    ${compact ? "" : `<div class="review-findings"><h3>未通过结论与修改方式</h3>${list(findings, finding => `<article class="review-finding ${finding.blocking ? "blocking" : ""}">
      <div class="finding-title"><span>${escapeHtml(finding.id)} · ${escapeHtml(finding.reviewer_name)} ${escapeHtml(finding.check)}</span><b>${escapeHtml(finding.severity)}${finding.blocking ? " · 阻断" : ""}</b></div>
      <h4>${escapeHtml(finding.title)}</h4>
      <dl><dt>证据</dt><dd>${escapeHtml(finding.evidence)}</dd><dt>修改位置</dt><dd><code>${escapeHtml(finding.location)}</code></dd><dt>应该怎么改</dt><dd>${escapeHtml(finding.recommendation)}</dd></dl>
    </article>`, reviews.status === "passed" ? "全部必需评审均已通过，没有待修改结论" : "当前没有未通过结论")}</div>`}
  </section>`;
}

function renderTaskBoard(data) {
  const control = data.tasks.execution_control || { mode: "single" };
  const continuous = control.mode === "continuous";
  return `<section class="card tasks-card task-page-board">
    <div class="task-board-heading">
      <div><p class="eyebrow">Execution</p><h2>任务执行</h2><p class="task-board-progress">${data.tasks.done} / ${data.tasks.total} 已完成</p></div>
      <div class="task-mode-setting">
        <span>推进方式</span>
        <div class="mode-switch" aria-label="任务推进模式">
          <button class="mode-button ${continuous ? "active" : ""}" data-mode="continuous" data-task="${escapeHtml(data.tasks.items.find(task => !task.done)?.text || "")}" aria-pressed="${continuous}">连续推进</button>
          <button class="mode-button ${!continuous ? "active" : ""}" data-mode="single" data-task="${escapeHtml(data.tasks.items.find(task => !task.done)?.text || "")}" aria-pressed="${!continuous}">单独推进</button>
        </div>
      </div>
    </div>
    <p class="task-board-feedback" aria-live="polite">${escapeHtml(controlFeedback)}</p>
    <div class="tasks">${renderTasks(data)}</div>
  </section>`;
}

function renderTasks(data) {
  if (!data.tasks.items.length) return '<p class="empty">尚未生成 task</p>';
  const currentIndex = data.tasks.items.findIndex(task => !task.done);
  const control = data.tasks.execution_control || { mode: "single" };
  return data.tasks.items.map((task, index) => {
    const current = index === currentIndex;
    const state = task.done ? "已完成" : current ? "当前任务" : "等待中";
    return `<section class="task ${task.done ? "done" : ""} ${current ? "current" : ""}">
      <div class="task-head">
        <span class="task-mark">${task.done ? "✓" : current ? "→" : "○"}</span>
        <div class="task-identity"><span class="task-number">Task ${index + 1}</span><strong>${escapeHtml(task.text)}</strong></div>
        ${current && control.mode !== "continuous"
          ? `<button class="advance-button task-row-action" id="advance-next" data-task="${escapeHtml(task.text)}" title="CR 通过后提交 Git 暂存区并推进">推进下一个任务</button>`
          : `<span class="task-state">${state}</span>`}
      </div>
    </section>`;
  }).join("");
}

function bindExecutionControls(data) {
  document.querySelectorAll("[data-mode]").forEach(button => {
    button.addEventListener("click", () => {
      if (button.dataset.mode !== data.tasks.execution_control.mode) {
        updateControl(data, "set-mode", button.dataset.mode, button.dataset.task);
      }
    });
  });
  const advance = document.querySelector("#advance-next");
  if (advance) advance.addEventListener("click", () => updateControl(data, "advance-next", null, advance.dataset.task));
}

async function updateControl(data, action, mode = null, expectedTask = "") {
  controlFeedback = action === "advance-next" ? "正在提交暂存区并更新推进授权…" : "正在更新推进授权…";
  if (data.sample) {
    const control = data.tasks.execution_control;
    control.sequence = (control.sequence || 0) + 1;
    if (action === "set-mode") {
      data.tasks.execution_control = { mode, sequence: control.sequence };
      controlFeedback = mode === "continuous" ? "已授权剩余任务连续推进" : "已切换为逐任务 CR";
    } else {
      const pending = data.tasks.items.filter(item => !item.done);
      control.approved_task = pending[0]?.text || "";
      control.advance_to_task = pending[1]?.text || "最终验证";
      controlFeedback = "示例模式：将提交暂存区并进入下一任务";
    }
    render(data);
    return;
  }
  render(data);
  try {
    const response = await fetch("/api/control", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        action,
        mode,
        change: data.change,
        expected_task: expectedTask,
        expected_version: data.tasks.version,
      }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
    controlFeedback = action === "set-mode"
      ? mode === "continuous" ? "已授权剩余任务连续推进" : "已切换为逐任务 CR"
      : payload.staged_commit?.created
        ? `已提交暂存区 ${payload.staged_commit.commit || ""}，允许进入下一任务`
        : "暂存区为空，无需创建提交；允许进入下一任务";
    render(payload);
  } catch (error) {
    controlFeedback = `更新失败：${error.message}`;
    render(data);
  }
}

function renderPointPage(data, point) {
  const documents = (data.documents || []).filter(doc => doc.point_ids.includes(point.id));
  const availableCategories = categoryOrder.filter(category => documents.some(doc => doc.category === category));
  if (!activeCategory || !availableCategories.includes(activeCategory)) activeCategory = availableCategories[0] || null;
  const categoryDocuments = documents.filter(doc => doc.category === activeCategory);
  if (!activeDocumentPath || !categoryDocuments.some(doc => doc.path === activeDocumentPath)) {
    activeDocumentPath = categoryDocuments[0]?.path || null;
  }
  app.innerHTML = `
    <header class="top detail-top">
      <div>${renderChangeSwitcher(data)}<a class="back-link" href="${escapeHtml(pageHref())}">← 返回 Change 总览</a><p class="eyebrow">${escapeHtml(data.change)} · Modification</p><h1>${escapeHtml(point.id)}</h1><p class="detail-subtitle">${escapeHtml(point.scenario || point.target)}</p></div>
      ${connectionMarkup(data)}
    </header>
    ${renderArtifactNav(data, "analysis")}
    <section class="point-summary card">
      <div class="kv detail-kv"><b>文件</b><code>${escapeHtml(point.file)}</code><b>符号</b><code>${escapeHtml(point.symbol)}</code><b>变量</b><code>${escapeHtml(point.variable)} · ${escapeHtml(point.type)}</code><b>目标变化</b><span>${escapeHtml(point.target)}</span></div>
    </section>
    <section class="document-shell card">
      <div class="tabs" role="tablist" aria-label="修改点文件分类">${availableCategories.map(category => {
        const doc = documents.find(item => item.category === category);
        const count = documents.filter(item => item.category === category).length;
        return `<button class="tab ${category === activeCategory ? "active" : ""}" role="tab" aria-selected="${category === activeCategory}" data-category="${escapeHtml(category)}">${escapeHtml(doc.category_label)} <span>${count}</span></button>`;
      }).join("")}</div>
      <div class="document-layout">
        <nav class="file-list" aria-label="文件列表">${list(categoryDocuments, doc => `<button class="file-button ${doc.path === activeDocumentPath ? "active" : ""}" data-path="${escapeHtml(doc.path)}"><code>${escapeHtml(doc.path)}</code><small>${escapeHtml(doc.updated_at)}</small></button>`, "此标签暂无关联文件")}</nav>
        <article class="document-view"><div class="document-title"><code>${escapeHtml(activeDocumentPath || "未选择文件")}</code><span>只读</span></div><pre id="document-content">正在读取文件…</pre></article>
      </div>
    </section>`;
  bindDetailInteractions(data, point, documents);
  bindChangeSwitcher();
}

function renderArtifactPage(data, selectedDocument) {
  const documents = data.documents || [];
  const selectedSection = artifactSection(selectedDocument);
  const sectionDocuments = documents.filter(doc => artifactSection(doc) === selectedSection);
  app.innerHTML = `
    <header class="top detail-top">
      <div>${renderChangeSwitcher(data)}<p class="eyebrow">${escapeHtml(data.change)} · OpenSpec Artifact</p><h1>${escapeHtml(artifactSectionLabels[selectedSection] || selectedSection)}</h1><p class="detail-subtitle">直接读取当前 change 中的产物，内容变化后自动更新。</p></div>
      ${connectionMarkup(data)}
    </header>
    ${renderArtifactNav(data, selectedSection)}
    ${selectedSection === "tasks" ? renderTaskBoard(data) : ""}
    ${selectedSection === "review" ? renderReviewCenter(data) : ""}
    ${selectedSection === "tasks" ? "" : renderDocumentReader(selectedSection, sectionDocuments, selectedDocument)}
  `;
  activeDocumentPath = selectedDocument.path;
  bindChangeSwitcher();
  if (selectedSection === "tasks") bindExecutionControls(data);
  else loadDocument(data, selectedDocument);
}

function renderDocumentReader(selectedSection, sectionDocuments, selectedDocument) {
  return `<section class="document-shell card artifact-reader">
      <div class="artifact-context"><span>${escapeHtml(artifactSectionLabels[selectedSection] || selectedSection)}</span><strong>${sectionDocuments.length} 个文件</strong></div>
      <div class="document-layout">
        <nav class="file-list" aria-label="${escapeHtml(artifactSectionLabels[selectedSection] || selectedSection)} 文件列表">${sectionDocuments.map(doc => `<a class="file-button ${doc.path === selectedDocument.path ? "active" : ""}" href="${escapeHtml(pageHref({ artifact: doc.path }))}"><code>${escapeHtml(doc.path)}</code><small>${escapeHtml(doc.updated_at)}</small></a>`).join("")}</nav>
        <article class="document-view"><div class="document-title"><code>${escapeHtml(selectedDocument.path)}</code><span>实时只读</span></div><pre id="document-content">正在读取文件…</pre></article>
      </div>
    </section>`;
}

function bindDetailInteractions(data, point, documents) {
  document.querySelectorAll("[data-category]").forEach(button => {
    button.addEventListener("click", () => {
      activeCategory = button.dataset.category;
      activeDocumentPath = null;
      renderPointPage(data, point);
    });
  });
  document.querySelectorAll("[data-path]").forEach(button => {
    button.addEventListener("click", () => {
      activeDocumentPath = button.dataset.path;
      renderPointPage(data, point);
    });
  });
  const selected = documents.find(doc => doc.path === activeDocumentPath);
  if (selected) loadDocument(data, selected);
  else setDocumentContent("此标签暂无关联文件");
}

async function loadDocument(data, documentMeta) {
  const cacheKey = `${documentMeta.path}@${documentMeta.version || documentMeta.updated_at}`;
  if (documentCache.has(cacheKey)) {
    setDocumentContent(documentCache.get(cacheKey));
    return;
  }
  try {
    let content;
    if (data.sample) {
      content = documentMeta.content || "示例文件暂无内容";
    } else {
      const response = await fetch(apiUrl("/api/document", { path: documentMeta.path, change: data.change }), { cache: "no-store" });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
      content = payload.content;
    }
    documentCache.set(cacheKey, content);
    if (activeDocumentPath === documentMeta.path) setDocumentContent(content);
  } catch (error) {
    setDocumentContent(`文件读取失败：${error.message}`);
  }
}

function setDocumentContent(content) {
  const target = document.querySelector("#document-content");
  if (target) target.textContent = content;
}

function renderError(message) {
  const selected = new URL(window.location.href).searchParams.get("change") || latestData?.change || availableChanges[0]?.name;
  app.innerHTML = `<section class="error">${selected ? renderChangeSwitcher({ change: selected }) : ""}<strong>OpenSpec 读取失败</strong><p>${escapeHtml(message)}</p><a class="back-link" href="${escapeHtml(pageHref())}">返回总览</a><small>${new Date().toLocaleTimeString()}</small></section>`;
  bindChangeSwitcher();
}

async function refresh(change) {
  try {
    const response = await fetch(apiUrl("/api/status", { change }), { cache: "no-store" });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
    render(payload);
  } catch (error) {
    renderError(error.message);
  }
}

function connectLive(change) {
  if (!("EventSource" in window)) {
    refresh(change);
    setInterval(() => refresh(change), 1000);
    return;
  }
  const source = new EventSource(apiUrl("/events", { change }));
  source.addEventListener("open", () => {
    connectionState = "live";
    if (latestData) render(latestData);
  });
  source.addEventListener("status", event => {
    connectionState = "live";
    render(JSON.parse(event.data));
  });
  source.addEventListener("read-error", event => {
    const payload = JSON.parse(event.data);
    renderError(payload.error || "OpenSpec 读取失败");
  });
  source.addEventListener("error", () => {
    connectionState = "reconnecting";
    if (latestData) render(latestData);
  });
}

async function initializeLive() {
  try {
    const payload = await fetchChangeCatalog();
    const requested = new URL(window.location.href).searchParams.get("change");
    const selected = availableChanges.some(item => item.name === requested)
      ? requested
      : payload.default_change;
    const url = new URL(window.location.href);
    if (url.searchParams.get("change") !== selected) {
      url.searchParams.set("change", selected);
      window.history.replaceState(null, "", url.href);
    }
    connectLive(selected);
    setInterval(refreshChangeCatalog, 2000);
  } catch (error) {
    renderError(error.message);
  }
}

async function fetchChangeCatalog() {
  const response = await fetch("/api/changes", { cache: "no-store" });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
  availableChanges = payload.changes || [];
  return payload;
}

async function refreshChangeCatalog() {
  const previous = JSON.stringify(availableChanges);
  try {
    await fetchChangeCatalog();
    if (latestData && JSON.stringify(availableChanges) !== previous) render(latestData);
  } catch (error) {
    if (!latestData) renderError(error.message);
  }
}

if (window.location.protocol === "file:") {
  availableChanges = sampleChanges;
  const requested = new URL(window.location.href).searchParams.get("change");
  const selected = sampleStatuses[requested] ? requested : sampleData.change;
  if (!requested) {
    const url = new URL(window.location.href);
    url.searchParams.set("change", selected);
    window.history.replaceState(null, "", url.href);
  }
  render(sampleStatuses[selected]);
  setInterval(() => {
    sampleStatuses[selected].read_at = new Date().toLocaleTimeString();
    render(sampleStatuses[selected]);
  }, 1000);
} else {
  initializeLive();
}
