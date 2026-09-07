import { useState } from "react";
import {
  NavLink,
  Outlet,
  useNavigate,
} from "react-router-dom";

import NotificationBell from "../components/NotificationBell";
import { useAuth } from "../context/useAuth";

const footerGroups = [
  {
    title: "EXPLORE",
    links: [
      { label: "All products", to: "/products" },
      { label: "Compare prices", to: "/compare" },
      { label: "Price alerts", to: "/alerts" },
      { label: "AI assistant", to: "/assistant" },
    ],
  },
  {
    title: "COMPANY",
    links: [
      { label: "How it works", to: "/how-it-works" },
      { label: "About VEXTRO", to: "/about" },
      { label: "For businesses", to: "/for-businesses" },
      { label: "Contact us", to: "/contact" },
    ],
  },
  {
    title: "LEGAL",
    links: [
      { label: "Privacy policy", to: "/privacy" },
      { label: "Terms & conditions", to: "/terms" },
      { label: "Price alerts", to: "/price-alerts" },
      { label: "Support", to: "/support" },
    ],
  },
];

const headerCategories = [
  { label: "Smartphones", to: "/products?category=smartphones" },
  { label: "Laptops", to: "/products?category=laptops" },
  { label: "Wearables", to: "/products?category=wearables" },
  { label: "Audio", to: "/products?category=audio" },
  { label: "Home", to: "/products?category=home-appliances" },
  { label: "Beauty", to: "/products?category=health-beauty" },
];

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
  const [headerSearch, setHeaderSearch] = useState("");

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
    navigationItems.push({
      label: "Assistant",
      path: "/assistant",
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

  function handleHeaderSearch(event) {
    event.preventDefault();
    const normalizedQuery = headerSearch.trim();

    navigate(
      normalizedQuery
        ? `/products?q=${encodeURIComponent(normalizedQuery)}`
        : "/products",
    );
    setIsMenuOpen(false);
  }

  return (
    <div className="flex min-h-screen flex-col bg-vextro-canvas text-vextro-ink">
      <header className="sticky top-0 z-50 border-b border-vextro-border bg-white/95 backdrop-blur-xl">
        <div className="mx-auto flex min-h-20 max-w-7xl items-center justify-between gap-4 px-4 sm:px-6 lg:px-8">
          <NavLink
            className="flex shrink-0 items-center gap-3"
            to="/"
            onClick={closeMobileMenu}
          >
            <span className="grid size-11 place-items-center rounded-2xl bg-gradient-to-br from-vextro-primary to-emerald-600 text-lg font-black text-white shadow-lg shadow-emerald-500/20">
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

          <form
            className="hidden min-h-11 max-w-xl flex-1 items-center overflow-hidden rounded-xl border border-vextro-border bg-vextro-canvas transition focus-within:border-vextro-primary focus-within:ring-4 focus-within:ring-emerald-100 md:flex"
            onSubmit={handleHeaderSearch}
          >
            <span className="pl-4 text-vextro-muted" aria-hidden="true">⌕</span>
            <label className="sr-only" htmlFor="header-product-search">Search products</label>
            <input
              id="header-product-search"
              className="min-w-0 flex-1 bg-transparent px-3 text-sm outline-none placeholder:text-slate-400"
              type="search"
              value={headerSearch}
              onChange={(event) => setHeaderSearch(event.target.value)}
              placeholder="Search products, brands and prices..."
            />
            <button className="self-stretch bg-vextro-primary px-5 text-xs font-black text-white hover:bg-vextro-primary-dark" type="submit">
              Search
            </button>
          </form>

          <div className="hidden items-center gap-3 md:flex">
            {!isInitializing && isAuthenticated ? (
              <>
                {hasRole("consumer", "sme", "admin") ? (
                  <NotificationBell />
                ) : null}

                <NavLink
                  className="flex min-w-0 items-center gap-2 rounded-2xl border border-vextro-border bg-white p-1.5 pr-3 transition hover:border-blue-200 hover:bg-blue-50/40"
                  to="/dashboard"
                >
                  <span className="grid size-9 shrink-0 place-items-center rounded-xl bg-gradient-to-br from-vextro-primary to-emerald-600 text-sm font-black text-white">
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

          <div className="ml-auto flex items-center gap-2 md:hidden">
            {!isInitializing &&
            isAuthenticated &&
            hasRole("consumer", "sme", "admin") ? (
              <NotificationBell />
            ) : null}

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
        </div>

        <div className="hidden border-t border-vextro-border md:block">
          <nav
            className="mx-auto flex min-h-12 max-w-7xl items-center gap-1 overflow-x-auto px-6 lg:px-8"
            aria-label="Product categories"
          >
            <NavLink
              className="mr-2 shrink-0 rounded-xl bg-emerald-50 px-3 py-2 text-xs font-black text-vextro-primary hover:bg-emerald-100"
              to="/products"
            >
              ☰ &nbsp; All categories
            </NavLink>

            {headerCategories.map((category) => (
              <NavLink
                key={category.label}
                className="shrink-0 rounded-lg px-3 py-2 text-xs font-bold text-vextro-ink hover:bg-vextro-canvas hover:text-vextro-primary"
                to={category.to}
              >
                {category.label}
              </NavLink>
            ))}

            <span className="mx-2 h-5 w-px shrink-0 bg-vextro-border" />

            {navigationItems
              .filter(
                (item) =>
                  item.path !== "/" && item.path !== "/products",
              )
              .map((item) => (
                <NavLink
                  key={item.path}
                  className={getDesktopNavClass}
                  to={item.path}
                >
                  {item.label}
                </NavLink>
              ))}
          </nav>
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
                      <span className="grid size-11 place-items-center rounded-xl bg-gradient-to-br from-vextro-primary to-emerald-600 font-black text-white">
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
        <section className="border-b border-vextro-border bg-white">
          <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6 sm:py-12 lg:px-8">
            <h2 className="text-lg font-black tracking-tight text-vextro-ink sm:text-xl">
              Compare Smarter Across Pakistan
            </h2>

            <p className="mt-3 max-w-4xl text-sm leading-6 text-vextro-muted">
              VEXTRO brings product listings, marketplace prices and
              ecommerce intelligence together in one place. Compare
              offers, understand price history and make confident buying
              decisions without overpaying.
            </p>
          </div>
        </section>

        <div className="h-8 border-b border-vextro-border bg-vextro-canvas sm:h-10" />

        <section className="border-b border-vextro-border">
          <div className="mx-auto grid max-w-7xl gap-10 px-4 py-10 sm:grid-cols-2 sm:px-6 sm:py-12 lg:grid-cols-[1.5fr_1fr_1fr_1fr] lg:gap-16 lg:px-8">
            <div className="max-w-sm sm:col-span-2 lg:col-span-1">
              <NavLink
                className="inline-flex items-center gap-3"
                to="/"
              >
                <span className="grid size-10 place-items-center rounded-xl bg-gradient-to-br from-vextro-primary to-emerald-600 text-base font-black text-white shadow-lg shadow-emerald-500/15">
                  V
                </span>

                <span className="text-2xl font-black tracking-tight text-vextro-ink">
                  VEXTRO
                </span>
              </NavLink>

              <p className="mt-4 text-sm font-bold text-vextro-primary">
                Compare Better. Decide Smarter.
              </p>

              <p className="mt-3 max-w-xs text-sm leading-6 text-vextro-muted">
                Pakistan&apos;s AI-powered ecommerce intelligence platform
                for shoppers and growing businesses.
              </p>
            </div>

            {footerGroups.map((group) => (
              <nav
                key={group.title}
                aria-label={`${group.title.toLowerCase()} footer links`}
              >
                <h3 className="text-xs font-black tracking-[0.08em] text-vextro-ink">
                  {group.title}
                </h3>

                <ul className="mt-4 space-y-3">
                  {group.links.map((link) => (
                    <li key={`${group.title}-${link.label}`}>
                      <NavLink
                        className="text-sm text-vextro-muted transition-colors hover:text-vextro-primary"
                        to={link.to}
                      >
                        {link.label}
                      </NavLink>
                    </li>
                  ))}
                </ul>
              </nav>
            ))}
          </div>
        </section>

        <div className="mx-auto flex max-w-7xl flex-col gap-2 px-4 py-5 text-xs text-vextro-muted sm:flex-row sm:items-center sm:justify-between sm:px-6 lg:px-8">
          <p>© {new Date().getFullYear()} VEXTRO. All rights reserved.</p>
          <p>
            Built with intelligence in Pakistan <span aria-hidden="true">🇵🇰</span>
          </p>
        </div>
      </footer>
    </div>
  );
}

export default MainLayout;
