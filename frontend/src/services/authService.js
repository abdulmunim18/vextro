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

export async function verifyEmail(payload) {
  const response = await apiClient.post("/auth/verify-email", payload);
  return response.data;
}

export async function resendVerification(email) {
  const response = await apiClient.post("/auth/resend-verification", {
    email,
  });
  return response.data;
}

export async function requestPasswordReset(email) {
  const response = await apiClient.post("/auth/forgot-password", {
    email,
  });
  return response.data;
}

export async function resetPassword(token, newPassword) {
  const response = await apiClient.post("/auth/reset-password", {
    token,
    new_password: newPassword,
  });
  return response.data;
}

export async function exchangeOAuthCode(code) {
  const response = await apiClient.post("/auth/oauth/exchange", {
    code,
  });
  return response.data;
}

export function startOAuthLogin(provider, accountType = "consumer") {
  const apiBase = import.meta.env.VITE_API_BASE_URL || "/api/v1";
  const path = `${apiBase}/auth/oauth/${encodeURIComponent(provider)}/authorize?account_type=${encodeURIComponent(accountType)}`;
  window.location.assign(path);
}
