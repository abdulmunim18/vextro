import apiClient from "../api/httpClient";


export async function getAdminDashboard() {
  const response = await apiClient.get(
    "/admin/dashboard",
  );

  return response.data;
}


export async function getAdminUsers(params = {}) {
  const response = await apiClient.get(
    "/admin/users",
    {
      params,
    },
  );

  return response.data;
}


export async function updateAdminUserStatus(
  userId,
  isActive,
) {
  const response = await apiClient.patch(
    `/admin/users/${userId}/status`,
    {
      is_active: isActive,
    },
  );

  return response.data;
}


export async function getAdminProducts(params = {}) {
  const response = await apiClient.get(
    "/admin/products",
    {
      params,
    },
  );

  return response.data;
}


export async function updateAdminProductStatus(
  productId,
  isActive,
) {
  const response = await apiClient.patch(
    `/admin/products/${productId}/status`,
    {
      is_active: isActive,
    },
  );

  return response.data;
}


export async function getAdminListings(params = {}) {
  const response = await apiClient.get(
    "/admin/listings",
    {
      params,
    },
  );

  return response.data;
}


export async function getPendingProductMatches(params = {}) {
  const response = await apiClient.get(
    "/admin/pending-product-matches",
    { params },
  );

  return response.data;
}


export async function getProductVariantOptions(query) {
  const response = await apiClient.get(
    "/admin/product-variant-options",
    { params: { q: query } },
  );

  return response.data;
}


export async function resolvePendingProductMatch(
  matchId,
  productVariantId,
) {
  const response = await apiClient.patch(
    `/admin/pending-product-matches/${matchId}/resolve`,
    { product_variant_id: productVariantId },
  );

  return response.data;
}


export async function replayPendingProductMatch(matchId) {
  const response = await apiClient.post(
    `/admin/pending-product-matches/${matchId}/replay`,
  );

  return response.data;
}


export async function deletePendingProductMatch(matchId) {
  await apiClient.delete(
    `/admin/pending-product-matches/${matchId}`,
  );
}
