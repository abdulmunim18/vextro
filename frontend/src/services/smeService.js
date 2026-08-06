import apiClient from "../api/httpClient";
export async function getOrganizations() {
  const response = await apiClient.get(
    "/sme/organizations",
  );

  return response.data;
}

export async function createOrganization(payload) {
  const response = await apiClient.post(
    "/sme/organizations",
    payload,
  );

  return response.data;
}

export async function getOrganization(
  organizationId,
) {
  const response = await apiClient.get(
    `/sme/organizations/${organizationId}`,
  );

  return response.data;
}

export async function updateOrganization(
  organizationId,
  payload,
) {
  const response = await apiClient.patch(
    `/sme/organizations/${organizationId}`,
    payload,
  );

  return response.data;
}

export async function getBusinessProducts(
  organizationId,
  params = {},
) {
  const response = await apiClient.get(
    `/sme/organizations/${organizationId}/products`,
    {
      params,
    },
  );

  return response.data;
}

export async function createBusinessProduct(
  organizationId,
  payload,
) {
  const response = await apiClient.post(
    `/sme/organizations/${organizationId}/products`,
    payload,
  );

  return response.data;
}

export async function getBusinessProduct(
  organizationId,
  productId,
) {
  const response = await apiClient.get(
    `/sme/organizations/${organizationId}/products/${productId}`,
  );

  return response.data;
}

export async function updateBusinessProduct(
  organizationId,
  productId,
  payload,
) {
  const response = await apiClient.patch(
    `/sme/organizations/${organizationId}/products/${productId}`,
    payload,
  );

  return response.data;
}

export async function getCompetitorWatchlist(
  organizationId,
  params = {},
) {
  const response = await apiClient.get(
    `/sme/organizations/${organizationId}/competitors`,
    {
      params,
    },
  );

  return response.data;
}

export async function createCompetitorWatchlistEntry(
  organizationId,
  payload,
) {
  const response = await apiClient.post(
    `/sme/organizations/${organizationId}/competitors`,
    payload,
  );

  return response.data;
}

export async function updateCompetitorWatchlistStatus(
  organizationId,
  watchlistId,
  isActive,
) {
  const response = await apiClient.patch(
    `/sme/organizations/${organizationId}/competitors/${watchlistId}/status`,
    {
      is_active: isActive,
    },
  );

  return response.data;
}