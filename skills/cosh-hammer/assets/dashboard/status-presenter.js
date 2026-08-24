(function exposeStatusPresenter(root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.DashboardStatus = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function buildStatusPresenter() {
  const presentations = {
    pending: { label: "待开始", tone: "pending" },
    running: { label: "进行中", tone: "running" },
    awaiting_commit: { label: "待批准写入", tone: "awaiting-commit" },
    completed: { label: "已完成", tone: "completed" },
    passed: { label: "已完成", tone: "completed" },
    blocked: { label: "已阻塞", tone: "blocked" },
    failed: { label: "失败", tone: "blocked" },
  };

  function present(status) {
    const normalized = String(status || "").trim().toLowerCase();
    return presentations[normalized] || { label: "未知状态", tone: "unknown" };
  }

  return Object.freeze({ present });
});
