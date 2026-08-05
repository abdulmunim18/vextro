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