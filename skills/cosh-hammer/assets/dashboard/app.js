const params = new URLSearchParams(window.location.search);
const work = params.get("work");
const tabs = new Set([
  "overview", "requirement", "design", "review", "plan", "coding",
  "validation", "delivery", "artifacts",
]);
let activeTab = tabs.has(params.get("tab")) ? params.get("tab") : "overview";
let currentData = null;

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
  content.textContent = "正在读取…";
  viewer.hidden = false;
  try {
    const response = await fetch(api("/api/artifact", { scope: artifact.scope, path: artifact.path }), { cache: "no-store" });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || "读取产物失败");
    if (payload.kind === "binary") {
      content.textContent = `二进制产物 · ${payload.size} bytes，当前仅展示元信息。`;
    } else if (payload.kind === "large") {
      content.textContent = `产物大小 ${payload.size} bytes，超过在线预览上限。`;
    } else if (artifact.path.endsWith(".json")) {
      try {
        content.textContent = JSON.stringify(JSON.parse(payload.content), null, 2);
      } catch (_error) {
        content.textContent = payload.content;
      }
    } else {
      content.textContent = payload.content;
    }
  } catch (error) {
    content.textContent = error.message;
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

function renderOverview(data) {
  const fragment = document.createDocumentFragment();
  fragment.append(viewHeader("Hammer 主流程", "Hammer 是唯一状态机；Cosh 只增强编码执行和观察。"));
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
    const card = element("article", `stage ${known.includes(stage.status) ? stage.status : "pending"}`);
    card.append(element("span", "number", String(index + 1).padStart(2, "0")));
    const copy = element("div");
    copy.append(element("h3", "", stage.label), element("p", "", stage.status));
    card.append(copy);
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

function renderCoding(data) {
  const fragment = document.createDocumentFragment();
  fragment.append(viewHeader("编码执行", "Hammer 父任务下的 Cosh 细分任务、范围与推进控制。"));
  const tasks = data.coding?.tasks || [];
  if (tasks.length) {
    const settings = element("section", "coding-settings");
    const settingCopy = element("div");
    settingCopy.append(element("p", "eyebrow", "推进方式"), element("strong", "", data.control?.mode === "continuous" ? "连续推进" : "逐一任务校验"));
    const actions = element("div", "controls");
    [["single", "逐一任务校验"], ["continuous", "连续推进"]].forEach(([mode, label]) => {
      const button = element("button", data.control?.mode === mode ? "active" : "", label);
      button.type = "button";
      button.disabled = !data.controls_enabled;
      button.addEventListener("click", () => postControl({ action: "set-mode", mode }).catch(error => alert(error.message)));
      actions.append(button);
    });
    const current = data.coding?.current_task;
    const needsAuthorization = data.control?.mode !== "continuous" && current?.status === "pending" && data.control?.authorized_task !== current.id;
    if (needsAuthorization) {
      const authorize = element("button", "authorize", `授权 ${current.id}`);
      authorize.type = "button";
      authorize.disabled = !data.controls_enabled;
      authorize.addEventListener("click", () => postControl({ action: "authorize-task", task: current.id }).catch(error => alert(error.message)));
      actions.append(authorize);
    }
    settings.append(settingCopy, actions);
    fragment.append(settings);
    const taskList = element("div", "task-list");
    tasks.forEach(task => {
      const card = element("article", `task ${task.status || "pending"}`);
      const copy = element("div");
      copy.append(element("p", "eyebrow", task.hammer_parent || "HAMMER TASK"), element("h3", "", task.title || task.id));
      card.append(copy, element("strong", "task-status", task.status || "pending"));
      taskList.append(card);
    });
    fragment.append(taskList);
  } else {
    fragment.append(emptyState("等待 Hammer Plan 进入编码父任务并生成 Cosh 细分任务。"));
  }
  fragment.append(element("h3", "section-heading", "编码产物"), artifactList(data, "coding"));
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
    review: () => renderStage(data, "三路评审", "可行性、安全性和稳定性评审产物。", "review"),
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
document.querySelector("#close-artifact").addEventListener("click", () => {
  document.querySelector("#artifact-viewer").hidden = true;
});

refresh().catch(() => {});
const events = new EventSource(api("/events"));
events.addEventListener("status", event => render(JSON.parse(event.data)));
events.onerror = () => { document.querySelector("#connection").textContent = "正在重连"; };
