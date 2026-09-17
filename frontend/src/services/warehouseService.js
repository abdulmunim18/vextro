import api from "./api";

export async function getWarehouseMetrics() {
  const response = await api.get("/api/v1/warehouse/metrics");
  return response.data;
}

export async function getScrapeRuns(params = {}) {
  const response = await api.get("/api/v1/warehouse/scrape-runs", { params });
  return response.data;
}

export async function triggerWarehouseAudit() {
  const response = await api.post("/api/v1/warehouse/maintenance/audit");
  return response.data;
}
