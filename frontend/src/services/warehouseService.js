import apiClient from "../api/httpClient";

export async function getWarehouseMetrics() {
  const response = await apiClient.get("/warehouse/metrics");
  return response.data;
}

export async function getScrapeRuns(params = {}) {
  const response = await apiClient.get("/warehouse/scrape-runs", { params });
  return response.data;
}

export async function triggerWarehouseAudit() {
  const response = await apiClient.post("/warehouse/maintenance/audit");
  return response.data;
}
