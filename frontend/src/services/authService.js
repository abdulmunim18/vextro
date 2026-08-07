import apiClient from "../api/httpClient";

export async function registerUser(payload) {
  const response = await apiClient.post(
    "/auth/register",
    payload,
  );

  return response.data;
}

export async function loginUser(credentials) {
  const response = await apiClient.post(
    "/auth/login",
    credentials,
  );

  return response.data;
}

export async function getCurrentUser() {
  const response = await apiClient.get("/auth/me");
  return response.data;
}

export async function refreshSession(refreshToken) {
  const response = await apiClient.post(
    "/auth/refresh",
    {
      refresh_token: refreshToken,
    },
  );

  return response.data;
}

export async function logoutUser(refreshToken) {
  await apiClient.post(
    "/auth/logout",
    {
      refresh_token: refreshToken,
    },
  );
}