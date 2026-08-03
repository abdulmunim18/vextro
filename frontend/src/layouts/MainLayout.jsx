import { useState } from "react";
import {
  NavLink,
  Outlet,
  useNavigate,
} from "react-router-dom";

import { useAuth } from "../context/AuthContext";



function MainLayout() {
  const navigate = useNavigate();
  
  const {
  user,
  isAuthenticated,
  isInitializing,
  logout,
  hasRole,
} = useAuth();
const navigationItems = [
  {
    label: "Home",
    path: "/",
  },
  {
    label: "Products",
    path: "/products",
  },
];

if (isAuthenticated) {
  navigationItems.push({
    label: "Dashboard",
    path: "/dashboard",
  });
}

if (
  isAuthenticated &&
  hasRole("consumer", "admin")
) {
  navigationItems.push({
    label: "Price Alerts",
    path: "/alerts",
  });
}

if (
  isAuthenticated &&
  hasRole("admin")
) {
  navigationItems.push({
    label: "Admin",
    path: "/admin",
  });
}

  const [isLoggingOut, setIsLoggingOut] = useState(false);

  async function handleLogout() {
    setIsLoggingOut(true);

    try {
      await logout();
    } catch {
      // The local session is still cleared by AuthContext.
    } finally {
      setIsLoggingOut(false);

      navigate("/", {
        replace: true,
      });
    }
  }

  const userInitial =
    user?.full_name?.trim().charAt(0).toUpperCase() || "U";

  return (
    <div className="app-shell">
      <header className="main-header">
        <div className="container header-content">
          <NavLink className="brand" to="/">
            <span className="brand-mark">V</span>

            <span className="brand-text">
              VEXTRO
              <small>Smarter Ecommerce Decisions</small>
            </span>
          </NavLink>

          <nav
            className="main-navigation"
            aria-label="Main navigation"
          >
            {navigationItems.map((item) => (
              <NavLink
                key={item.path}
                className={({ isActive }) =>
                  isActive
                    ? "nav-link nav-link-active"
                    : "nav-link"
                }
                end={item.path === "/"}
                to={item.path}
              >
                {item.label}
              </NavLink>
            ))}
          </nav>

          {!isInitializing ? (
            <div className="header-actions">
              {isAuthenticated ? (
                <>
                  <NavLink
                    className="user-chip"
                    to="/dashboard"
                  >
                    <span className="user-avatar">
                      {userInitial}
                    </span>

                    <span className="user-chip-text">
                      <strong>{user.full_name}</strong>
                      <small>
                        {user.roles?.join(", ") || "User"}
                      </small>
                    </span>
                  </NavLink>

                  <button
                    className="logout-button"
                    type="button"
                    onClick={handleLogout}
                    disabled={isLoggingOut}
                  >
                    {isLoggingOut ? "Exiting..." : "Logout"}
                  </button>
                </>
              ) : (
                <>
                  <NavLink
                    className="text-button"
                    to="/login"
                  >
                    Login
                  </NavLink>

                  <NavLink
                    className="primary-button small-button"
                    to="/register"
                  >
                    Get Started
                  </NavLink>
                </>
              )}
            </div>
          ) : null}
        </div>
      </header>

      <main className="main-content">
        <Outlet />
      </main>

      <footer className="main-footer">
        <div className="container footer-content">
          <p>© 2026 VEXTRO</p>
          <p>AI-powered ecommerce intelligence platform</p>
        </div>
      </footer>
    </div>
  );
}

export default MainLayout;