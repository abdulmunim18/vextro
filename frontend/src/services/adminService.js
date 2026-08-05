import apiClient from "../api/httpClient";

export async function getAdminDashboard() {
  const response = await apiClient.get(
    "/admin/dashboard",
  );

  return response.data;
}

export async function getAdminUsers(
  params = {},
) {
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