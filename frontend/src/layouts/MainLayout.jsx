import { NavLink, Outlet } from "react-router-dom";

const navigationItems = [
  { label: "Home", path: "/" },
  { label: "Products", path: "/products" },
  { label: "Dashboard", path: "/dashboard" },
  { label: "Price Alerts", path: "/alerts" },
];

function MainLayout() {
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

          <nav className="main-navigation" aria-label="Main navigation">
            {navigationItems.map((item) => (
              <NavLink
                key={item.path}
                className={({ isActive }) =>
                  isActive ? "nav-link nav-link-active" : "nav-link"
                }
                end={item.path === "/"}
                to={item.path}
              >
                {item.label}
              </NavLink>
            ))}
          </nav>

          <div className="header-actions">
            <NavLink className="text-button" to="/login">
              Login
            </NavLink>

            <NavLink className="primary-button small-button" to="/register">
              Get Started
            </NavLink>
          </div>
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