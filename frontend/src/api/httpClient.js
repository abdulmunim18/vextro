import axios from "axios";

const STORAGE_KEYS = {
  accessToken: "vextro_access_token",
  refreshToken: "vextro_refresh_token",
  user: "vextro_user",
};

export const SESSION_CLEARED_EVENT = "vextro:session-cleared";
export const SESSION_REFRESHED_EVENT = "vextro:session-refreshed";

const baseURL = import.meta.env.VITE_API_BASE_URL || "/api/v1";

const apiClient = axios.create({
  baseURL,
  timeout: 15000,
  headers: {
    Accept: "application/json",
    "Content-Type": "application/json",
  },
});

// Refresh requests use a separate client so a rejected refresh cannot invoke
// this response interceptor recursively.
const sessionClient = axios.create({
  baseURL,
  timeout: 15000,
  headers: {
    Accept: "application/json",
    "Content-Type": "application/json",
  },
});

let refreshPromise = null;

function clearStoredSession() {
  localStorage.removeItem(STORAGE_KEYS.accessToken);
  localStorage.removeItem(STORAGE_KEYS.refreshToken);
  localStorage.removeItem(STORAGE_KEYS.user);
  window.dispatchEvent(new Event(SESSION_CLEARED_EVENT));
}

function storeRefreshedSession(session) {
  localStorage.setItem(STORAGE_KEYS.accessToken, session.access_token);
  localStorage.setItem(STORAGE_KEYS.refreshToken, session.refresh_token);
  localStorage.setItem(STORAGE_KEYS.user, JSON.stringify(session.user));

  window.dispatchEvent(
    new CustomEvent(SESSION_REFRESHED_EVENT, {
      detail: session.user,
    }),
  );
}

function refreshAccessToken() {
  if (refreshPromise) {
    return refreshPromise;
  }

  const refreshToken = localStorage.getItem(STORAGE_KEYS.refreshToken);

  if (!refreshToken) {
    clearStoredSession();
    return Promise.reject(new Error("No refresh token is available."));
  }

  refreshPromise = sessionClient
    .post("/auth/refresh", {
      refresh_token: refreshToken,
    })
    .then((response) => {
      storeRefreshedSession(response.data);
      return response.data.access_token;
    })
    .catch((error) => {
      clearStoredSession();
      throw error;
    })
    .finally(() => {
      refreshPromise = null;
    });

  return refreshPromise;
}

function canRetryWithRefresh(config) {
  const requestPath = config?.url || "";

  return (
    !config?._retry &&
    requestPath !== "/auth/login" &&
    requestPath !== "/auth/register" &&
    requestPath !== "/auth/refresh" &&
    requestPath !== "/auth/oauth/exchange" &&
    requestPath !== "/auth/logout"
  );
}

apiClient.interceptors.request.use(
  (config) => {
    const accessToken = localStorage.getItem(
      "vextro_access_token",
    );

    if (accessToken) {
      config.headers.Authorization = `Bearer ${accessToken}`;
    }

    return config;
  },
  (error) => Promise.reject(error),
);

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    if (
      error.response?.status === 401 &&
      canRetryWithRefresh(originalRequest)
    ) {
      originalRequest._retry = true;

      try {
        const accessToken = await refreshAccessToken();

        originalRequest.headers = originalRequest.headers || {};
        originalRequest.headers.Authorization = `Bearer ${accessToken}`;

        return apiClient(originalRequest);
      } catch {
        return Promise.reject(error);
      }
    }

    if (error.response?.status === 401) {
      clearStoredSession();
    }

    return Promise.reject(error);
  },
);

export default apiClient;
