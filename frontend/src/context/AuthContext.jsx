import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  getCurrentUser,
  loginUser,
  logoutUser,
  registerUser,
} from "../services/authService";

const AuthContext = createContext(null);

const STORAGE_KEYS = {
  accessToken: "vextro_access_token",
  refreshToken: "vextro_refresh_token",
  user: "vextro_user",
};

function readStoredUser() {
  const storedUser = localStorage.getItem(STORAGE_KEYS.user);

  if (!storedUser) {
    return null;
  }

  try {
    return JSON.parse(storedUser);
  } catch {
    localStorage.removeItem(STORAGE_KEYS.user);
    return null;
  }
}

function storeSession(session) {
  localStorage.setItem(
    STORAGE_KEYS.accessToken,
    session.access_token,
  );

  localStorage.setItem(
    STORAGE_KEYS.refreshToken,
    session.refresh_token,
  );

  localStorage.setItem(
    STORAGE_KEYS.user,
    JSON.stringify(session.user),
  );
}

function clearStoredSession() {
  localStorage.removeItem(STORAGE_KEYS.accessToken);
  localStorage.removeItem(STORAGE_KEYS.refreshToken);
  localStorage.removeItem(STORAGE_KEYS.user);
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(readStoredUser);
  const [isInitializing, setIsInitializing] = useState(true);

  const clearSession = useCallback(() => {
    clearStoredSession();
    setUser(null);
  }, []);

  useEffect(() => {
    let isMounted = true;

    async function restoreSession() {
      const accessToken = localStorage.getItem(
        STORAGE_KEYS.accessToken,
      );

      if (!accessToken) {
        if (isMounted) {
          setIsInitializing(false);
        }

        return;
      }

      try {
        const currentUser = await getCurrentUser();

        if (!isMounted) {
          return;
        }

        localStorage.setItem(
          STORAGE_KEYS.user,
          JSON.stringify(currentUser),
        );

        setUser(currentUser);
      } catch {
        if (isMounted) {
          clearSession();
        }
      } finally {
        if (isMounted) {
          setIsInitializing(false);
        }
      }
    }

    restoreSession();

    return () => {
      isMounted = false;
    };
  }, [clearSession]);

  const login = useCallback(async (credentials) => {
    const session = await loginUser(credentials);

    storeSession(session);
    setUser(session.user);

    return session.user;
  }, []);

  const register = useCallback(async (payload) => {
    return registerUser(payload);
  }, []);

  const logout = useCallback(async () => {
    const refreshToken = localStorage.getItem(
      STORAGE_KEYS.refreshToken,
    );

    try {
      if (refreshToken) {
        await logoutUser(refreshToken);
      }
    } finally {
      clearSession();
    }
  }, [clearSession]);

  const hasRole = useCallback(
    (...allowedRoles) => {
      if (!user?.roles || allowedRoles.length === 0) {
        return false;
      }

      const normalizedUserRoles = user.roles.map((role) =>
        role.toLowerCase(),
      );

      return allowedRoles.some((role) =>
        normalizedUserRoles.includes(role.toLowerCase()),
      );
    },
    [user],
  );

  const value = useMemo(
    () => ({
      user,
      isAuthenticated: Boolean(user),
      isInitializing,
      login,
      register,
      logout,
      hasRole,
    }),
    [
      user,
      isInitializing,
      login,
      register,
      logout,
      hasRole,
    ],
  );

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error(
      "useAuth must be used inside AuthProvider.",
    );
  }

  return context;
}