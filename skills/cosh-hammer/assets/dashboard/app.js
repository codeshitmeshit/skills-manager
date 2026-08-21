const params = new URLSearchParams(window.location.search);
const work = params.get("work");

function api(path) {
  const url = new URL(path, window.location.origin);
  if (work) url.searchParams.set("work", work);
  return url.toString();
}

function addDefinition(list, label, value) {
  const row = document.createElement("div");
  const term = document.createElement("dt");
  const detail = document.createElement("dd");
  term.textContent = label;
  detail.textContent = value || "—";
  row.append(term, detail);
  list.append(row);
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

function render(data) {
  document.querySelector("#summary").textContent = `${data.work} · Hammer 是唯一主流程`;
  document.querySelector("#connection").textContent = data.stale ? "缓存快照" : "实时连接";
  const warning = document.querySelector("#warning");
  warning.hidden = !data.stale;
  warning.textContent = data.stale ? `实时投影失败：${data.projection_error || "未知错误"}` : "";
  const hammer = document.querySelector("#hammer");
  hammer.replaceChildren();
  addDefinition(hammer, "阶段", data.hammer.stage);
  addDefinition(hammer, "状态", data.hammer.status);
  addDefinition(hammer, "当前任务", data.hammer.current_task);
  document.querySelector("#mode").textContent = data.control?.mode === "continuous" ? "连续推进" : "单独推进";
  const stages = document.querySelector("#stages");
  stages.replaceChildren();
  data.stages.forEach((stage, index) => {
    const card = document.createElement("article");
    card.className = `stage ${["pending", "running", "passed", "blocked", "failed"].includes(stage.status) ? stage.status : "pending"}`;
    const number = document.createElement("span");
    number.className = "number";
    number.textContent = String(index + 1).padStart(2, "0");
    const copy = document.createElement("div");
    const title = document.createElement("h3");
    const status = document.createElement("p");
    title.textContent = stage.label;
    status.textContent = stage.status;
    copy.append(title, status);
    card.append(number, copy);
    stages.append(card);
  });
  document.querySelectorAll("#controls button").forEach(button => { button.disabled = !data.controls_enabled; });
  document.querySelector("#authorize").dataset.task = data.coding?.current_task?.id || "";
}

async function refresh() {
  const response = await fetch(api("/api/status"), { cache: "no-store" });
  render(await response.json());
}

refresh().catch(() => {});
const events = new EventSource(api("/events"));
events.addEventListener("status", event => render(JSON.parse(event.data)));
events.onerror = () => { document.querySelector("#connection").textContent = "正在重连"; };

document.querySelectorAll("[data-mode]").forEach(button => button.addEventListener("click", () => {
  postControl({ action: "set-mode", mode: button.dataset.mode }).catch(error => alert(error.message));
}));
document.querySelector("#authorize").addEventListener("click", event => {
  const task = event.currentTarget.dataset.task;
  if (!task) return alert("Hammer 当前没有可授权任务");
  postControl({ action: "authorize-task", task }).catch(error => alert(error.message));
});
