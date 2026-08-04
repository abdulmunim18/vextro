import apiClient from "../api/httpClient";

export async function getPriceAlerts() {
  const response = await apiClient.get("/price-alerts");

  return response.data;
}

export async function getPriceAlert(alertId) {
  const response = await apiClient.get(
    `/price-alerts/${alertId}`,
  );

  return response.data;
}

export async function createPriceAlert(payload) {
  const response = await apiClient.post(
    "/price-alerts",
    payload,
  );

  return response.data;
}

export async function updatePriceAlert(
  alertId,
  payload,
) {
  const response = await apiClient.patch(
    `/price-alerts/${alertId}`,
    payload,
  );

  return response.data;
}

export async function deactivatePriceAlert(alertId) {
  const response = await apiClient.delete(
    `/price-alerts/${alertId}`,
  );

  return response.data;
}