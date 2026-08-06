import { useState } from "react";
import {
  NavLink,
  Outlet,
  useNavigate,
} from "react-router-dom";

import { useAuth } from "../context/AuthContext";

function getDesktopNavClass({ isActive }) {
  const baseClasses =
    "rounded-xl px-3 py-2 text-sm font-semibold transition duration-200";

  return isActive
    ? `${baseClasses} bg-vextro-primary text-white shadow-sm`
    : `${baseClasses} text-vextro-muted hover:bg-slate-100 hover:text-vextro-ink`;
}

function getMobileNavClass({ isActive }) {
  const baseClasses =
    "block rounded-xl px-4 py-3 text-sm font-semibold transition duration-200";

  return isActive
    ? `${baseClasses} bg-vextro-primary text-white`
    : `${baseClasses} text-vextro-muted hover:bg-slate-100 hover:text-vextro-ink`;
}

function MainLayout() {
  const navigate = useNavigate();

  const {
    user,
    isAuthenticated,
    isInitializing,
    logout,
    hasRole,
  } = useAuth();

  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const [isMenuOpen, setIsMenuOpen] = useState(false);

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
  hasRole("sme", "admin")
) {
  navigationItems.push({
    label: "SME Workspace",
    path: "/sme",
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

  const userInitial =
    user?.full_name?.trim().charAt(0).toUpperCase() || "U";

  async function handleLogout() {
    setIsLoggingOut(true);

    try {
      await logout();
    } catch {
      // AuthContext still clears the local session.
    } finally {
      setIsLoggingOut(false);
      setIsMenuOpen(false);

      navigate("/", {
        replace: true,
      });
    }
  }

  function closeMobileMenu() {
    setIsMenuOpen(false);
  }

  return (
    <div className="flex min-h-screen flex-col bg-vextro-canvas text-vextro-ink">
      <header className="sticky top-0 z-50 border-b border-vextro-border bg-white/95 backdrop-blur-xl">
        <div className="mx-auto flex min-h-20 max-w-7xl items-center justify-between gap-6 px-4 sm:px-6 lg:px-8">
          <NavLink
            className="flex shrink-0 items-center gap-3"
            to="/"
            onClick={closeMobileMenu}
          >
            <span className="grid size-11 place-items-center rounded-2xl bg-gradient-to-br from-vextro-primary to-violet-600 text-lg font-black text-white shadow-lg shadow-blue-500/20">
              V
            </span>

            <span className="flex flex-col leading-none">
              <strong className="text-xl font-black tracking-tight text-vextro-ink">
                VEXTRO
              </strong>

              <small className="mt-1 hidden text-[9px] font-bold uppercase tracking-[0.14em] text-vextro-muted sm:block">
                Smarter Ecommerce Decisions
              </small>
            </span>
          </NavLink>

          <nav
            className="hidden items-center gap-1 md:flex"
            aria-label="Main navigation"
          >
            {navigationItems.map((item) => (
              <NavLink
                key={item.path}
                className={getDesktopNavClass}
                end={item.path === "/"}
                to={item.path}
              >
                {item.label}
              </NavLink>
            ))}
          </nav>

          <div className="hidden items-center gap-3 md:flex">
            {!isInitializing && isAuthenticated ? (
              <>
                <NavLink
                  className="flex min-w-0 items-center gap-2 rounded-2xl border border-vextro-border bg-white p-1.5 pr-3 transition hover:border-blue-200 hover:bg-blue-50/40"
                  to="/dashboard"
                >
                  <span className="grid size-9 shrink-0 place-items-center rounded-xl bg-gradient-to-br from-vextro-primary to-violet-600 text-sm font-black text-white">
                    {userInitial}
                  </span>

                  <span className="flex max-w-36 min-w-0 flex-col">
                    <strong className="truncate text-xs font-bold text-vextro-ink">
                      {user?.full_name}
                    </strong>

                    <small className="mt-0.5 truncate text-[9px] font-semibold capitalize text-vextro-muted">
                      {user?.roles?.join(", ") || "User"}
                    </small>
                  </span>
                </NavLink>

                <button
                  className="min-h-10 rounded-xl border border-vextro-border bg-white px-4 text-xs font-bold text-vextro-ink transition hover:border-red-200 hover:bg-red-50 hover:text-red-600 disabled:cursor-not-allowed disabled:opacity-50"
                  type="button"
                  onClick={handleLogout}
                  disabled={isLoggingOut}
                >
                  {isLoggingOut ? "Exiting..." : "Logout"}
                </button>
              </>
            ) : null}

            {!isInitializing && !isAuthenticated ? (
              <>
                <NavLink
                  className="rounded-xl px-4 py-2.5 text-sm font-bold text-vextro-muted transition hover:bg-slate-100 hover:text-vextro-ink"
                  to="/login"
                >
                  Login
                </NavLink>

                <NavLink
                  className="rounded-xl bg-vextro-primary px-5 py-2.5 text-sm font-bold text-white shadow-lg shadow-blue-500/20 transition hover:-translate-y-0.5 hover:bg-vextro-primary-dark"
                  to="/register"
                >
                  Get Started
                </NavLink>
              </>
            ) : null}
          </div>

          <button
            className="grid size-11 place-items-center rounded-xl border border-vextro-border bg-white text-xl font-bold text-vextro-ink transition hover:bg-slate-50 md:hidden"
            type="button"
            aria-label={
              isMenuOpen
                ? "Close navigation menu"
                : "Open navigation menu"
            }
            aria-expanded={isMenuOpen}
            onClick={() =>
              setIsMenuOpen((currentValue) => !currentValue)
            }
          >
            {isMenuOpen ? "×" : "☰"}
          </button>
        </div>

        {isMenuOpen ? (
          <div className="border-t border-vextro-border bg-white px-4 py-5 shadow-xl md:hidden">
            <nav
              className="mx-auto grid max-w-7xl gap-1"
              aria-label="Mobile navigation"
            >
              {navigationItems.map((item) => (
                <NavLink
                  key={item.path}
                  className={getMobileNavClass}
                  end={item.path === "/"}
                  to={item.path}
                  onClick={closeMobileMenu}
                >
                  {item.label}
                </NavLink>
              ))}
            </nav>

            {!isInitializing ? (
              <div className="mx-auto mt-5 max-w-7xl border-t border-vextro-border pt-5">
                {isAuthenticated ? (
                  <div className="grid gap-3">
                    <NavLink
                      className="flex items-center gap-3 rounded-2xl bg-vextro-canvas p-3"
                      to="/dashboard"
                      onClick={closeMobileMenu}
                    >
                      <span className="grid size-11 place-items-center rounded-xl bg-gradient-to-br from-vextro-primary to-violet-600 font-black text-white">
                        {userInitial}
                      </span>

                      <span className="flex min-w-0 flex-col">
                        <strong className="truncate text-sm font-bold">
                          {user?.full_name}
                        </strong>

                        <small className="mt-1 truncate text-xs capitalize text-vextro-muted">
                          {user?.roles?.join(", ") || "User"}
                        </small>
                      </span>
                    </NavLink>

                    <button
                      className="min-h-12 rounded-xl border border-red-200 bg-red-50 px-4 text-sm font-bold text-red-600 disabled:cursor-not-allowed disabled:opacity-50"
                      type="button"
                      onClick={handleLogout}
                      disabled={isLoggingOut}
                    >
                      {isLoggingOut
                        ? "Logging out..."
                        : "Logout"}
                    </button>
                  </div>
                ) : (
                  <div className="grid grid-cols-2 gap-3">
                    <NavLink
                      className="grid min-h-12 place-items-center rounded-xl border border-vextro-border text-sm font-bold text-vextro-ink"
                      to="/login"
                      onClick={closeMobileMenu}
                    >
                      Login
                    </NavLink>

                    <NavLink
                      className="grid min-h-12 place-items-center rounded-xl bg-vextro-primary text-sm font-bold text-white"
                      to="/register"
                      onClick={closeMobileMenu}
                    >
                      Get Started
                    </NavLink>
                  </div>
                )}
              </div>
            ) : null}
          </div>
        ) : null}
      </header>

      <main className="flex-1">
        <Outlet />
      </main>

      <footer className="border-t border-vextro-border bg-white">
        <div className="mx-auto flex max-w-7xl flex-col gap-4 px-4 py-8 text-center sm:px-6 md:flex-row md:items-center md:justify-between md:text-left lg:px-8">
          <div>
            <p className="text-sm font-black tracking-tight text-vextro-ink">
              VEXTRO
            </p>

            <p className="mt-1 text-xs text-vextro-muted">
              Smarter ecommerce decisions through data.
            </p>
          </div>

          <div className="text-xs text-vextro-muted">
            <p>AI-powered ecommerce intelligence platform</p>
            <p className="mt-1">
              © 2026 VEXTRO. Final Year Project.
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}

export default MainLayout;