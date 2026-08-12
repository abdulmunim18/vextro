import {
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";
import { Link } from "react-router-dom";

import RouteLoadingState from "../components/RouteLoadingState";
import { useAuth } from "../context/useAuth";
import { getProductById } from "../services/catalogService";
import { getPriceAlerts } from "../services/priceAlertService";
import { getApiErrorMessage } from "../utils/apiError";
import {
  formatDateTime,
  formatPrice,
} from "../utils/productDisplay";

function extractAlerts(responseData) {
  if (Array.isArray(responseData)) {
    return responseData;
  }

  if (Array.isArray(responseData?.items)) {
    return responseData.items;
  }

  return [];
}

function getAlertTitle(alert, productNames) {
  if (alert.canonical_product_id) {
    return (
      productNames.get(alert.canonical_product_id) ||
      `Product #${alert.canonical_product_id}`
    );
  }

  if (alert.listing_id) {
    return `Marketplace Listing #${alert.listing_id}`;
  }

  return "Unknown alert target";
}

function DashboardPage() {
  const {
    user,
    hasRole,
  } = useAuth();

  const canUsePriceAlerts = hasRole(
    "consumer",
    "admin",
  );
const isAdmin = hasRole("admin");

const canUseSmeWorkspace = hasRole(
  "sme",
  "admin",
);

  const [alerts, setAlerts] = useState([]);
  const [productNames, setProductNames] = useState(
    new Map(),
  );

  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] =
    useState("");

  const loadDashboard = useCallback(async () => {
    setIsLoading(true);
    setErrorMessage("");

    if (!canUsePriceAlerts) {
      setAlerts([]);
      setProductNames(new Map());
      setIsLoading(false);
      return;
    }

    try {
      const responseData = await getPriceAlerts();
      const responseAlerts = extractAlerts(responseData);

      setAlerts(responseAlerts);

      const uniqueProductIds = [
        ...new Set(
          responseAlerts
            .map(
              (alert) =>
                alert.canonical_product_id,
            )
            .filter(Boolean),
        ),
      ];

      if (uniqueProductIds.length === 0) {
        setProductNames(new Map());
        return;
      }

      const productResults =
        await Promise.allSettled(
          uniqueProductIds.map(
            async (productId) => {
              const product =
                await getProductById(productId);

              return {
                id: productId,
                name:
                  product?.name ||
                  `Product #${productId}`,
              };
            },
          ),
        );

      const nextProductNames = new Map();

      productResults.forEach((result) => {
        if (result.status === "fulfilled") {
          nextProductNames.set(
            result.value.id,
            result.value.name,
          );
        }
      });

      setProductNames(nextProductNames);
    } catch (error) {
      setErrorMessage(
        getApiErrorMessage(
          error,
          "Unable to load dashboard information.",
        ),
      );
    } finally {
      setIsLoading(false);
    }
  }, [canUsePriceAlerts]);

  useEffect(() => {
    const timeoutId = window.setTimeout(loadDashboard, 0);
    return () => window.clearTimeout(timeoutId);
  }, [loadDashboard]);

  const statistics = useMemo(() => {
    const activeAlerts = alerts.filter(
      (alert) => alert.is_active,
    ).length;

    const pausedAlerts = alerts.filter(
      (alert) => !alert.is_active,
    ).length;

    const triggeredAlerts = alerts.filter(
      (alert) => alert.is_triggered,
    ).length;

    const notificationCount = alerts.reduce(
      (total, alert) =>
        total + (alert.notification_count || 0),
      0,
    );

    const linkedProductCount = new Set(
      alerts
        .map(
          (alert) =>
            alert.canonical_product_id,
        )
        .filter(Boolean),
    ).size;

    return {
      activeAlerts,
      pausedAlerts,
      triggeredAlerts,
      notificationCount,
      linkedProductCount,
    };
  }, [alerts]);

  const recentAlerts = useMemo(
    () =>
      alerts
        .slice()
        .sort(
          (firstAlert, secondAlert) =>
            new Date(secondAlert.created_at) -
            new Date(firstAlert.created_at),
        )
        .slice(0, 4),
    [alerts],
  );

  const primaryRole =
    user?.roles?.[0] || "user";

  const accountStatus =
    user?.is_active === false
      ? "Inactive"
      : "Active";

  const verificationStatus =
    user?.is_verified
      ? "Verified"
      : "Standard account";

  if (isLoading) {
    return (
      <RouteLoadingState message="Preparing your VEXTRO dashboard..." />
    );
  }

  return (
    <section className="relative min-h-[calc(100vh-145px)] overflow-hidden bg-vextro-canvas py-14 sm:py-16 lg:py-20">
      <div className="pointer-events-none absolute -left-48 top-20 size-[430px] rounded-full bg-blue-300/15 blur-3xl" />

      <div className="pointer-events-none absolute -right-48 top-0 size-[460px] rounded-full bg-violet-300/15 blur-3xl" />

      <div className="relative mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="flex flex-col items-start justify-between gap-7 lg:flex-row lg:items-end">
          <div className="max-w-3xl">
            <span className="text-xs font-black uppercase tracking-[0.18em] text-vextro-primary">
              VEXTRO Dashboard
            </span>

            <h1 className="mt-4 text-4xl font-black leading-[1.02] tracking-[-0.05em] text-vextro-ink sm:text-5xl lg:text-6xl">
              Welcome back,{" "}
              {user?.full_name?.split(" ")[0] ||
                "User"}
            </h1>

            <p className="mt-5 max-w-2xl text-sm leading-7 text-vextro-muted sm:text-base">
              Review your account, marketplace activity
              and available ecommerce intelligence from
              one workspace.
            </p>
          </div>

          <div className="flex w-full flex-col gap-3 sm:w-auto sm:flex-row">
            <Link
              className="inline-flex min-h-12 items-center justify-center gap-2 rounded-xl bg-vextro-primary px-6 text-sm font-black text-white shadow-lg shadow-blue-500/20 transition hover:-translate-y-0.5 hover:bg-vextro-primary-dark"
              to="/products"
            >
              Explore Products
              <span>→</span>
            </Link>

            {canUsePriceAlerts ? (
              <Link
                className="inline-flex min-h-12 items-center justify-center rounded-xl border border-vextro-border bg-white px-6 text-sm font-black text-vextro-ink transition hover:border-blue-200 hover:bg-blue-50"
                to="/alerts"
              >
                Manage Alerts
              </Link>
            ) : null}
            {canUseSmeWorkspace ? (
  <Link
    className="inline-flex min-h-12 items-center justify-center rounded-xl border border-violet-200 bg-violet-50 px-6 text-sm font-black text-violet-700 transition hover:-translate-y-0.5 hover:border-violet-300 hover:bg-violet-100"
    to="/sme"
  >
    SME Workspace
  </Link>
) : null}
          </div>
        </div>

        {errorMessage ? (
          <div
            className="mt-8 flex flex-col items-start justify-between gap-4 rounded-2xl border border-red-200 bg-red-50 p-5 text-red-700 sm:flex-row sm:items-center"
            role="alert"
          >
            <div>
              <strong className="block text-sm font-black">
                Dashboard data could not be loaded
              </strong>

              <p className="mt-1 text-xs leading-5">
                {errorMessage}
              </p>
            </div>

            <button
              className="min-h-10 rounded-xl border border-red-200 bg-white px-4 text-xs font-black transition hover:bg-red-100"
              type="button"
              onClick={loadDashboard}
            >
              Try Again
            </button>
          </div>
        ) : null}

        {canUsePriceAlerts ? (
          <div className="mt-10 grid grid-cols-2 gap-4 lg:grid-cols-4">
            <article className="rounded-2xl border border-vextro-border bg-white p-5 shadow-sm">
              <div className="flex items-center justify-between gap-4">
                <span className="text-xs font-bold text-vextro-muted">
                  Active alerts
                </span>

                <span className="grid size-9 place-items-center rounded-xl bg-emerald-50 text-lg">
                  🔔
                </span>
              </div>

              <strong className="mt-4 block text-3xl font-black tracking-tight text-emerald-600">
                {statistics.activeAlerts}
              </strong>

              <p className="mt-1 text-[11px] text-vextro-muted">
                Currently monitoring prices
              </p>
            </article>

            <article className="rounded-2xl border border-vextro-border bg-white p-5 shadow-sm">
              <div className="flex items-center justify-between gap-4">
                <span className="text-xs font-bold text-vextro-muted">
                  Triggered
                </span>

                <span className="grid size-9 place-items-center rounded-xl bg-violet-50 text-lg">
                  🎯
                </span>
              </div>

              <strong className="mt-4 block text-3xl font-black tracking-tight text-violet-600">
                {statistics.triggeredAlerts}
              </strong>

              <p className="mt-1 text-[11px] text-vextro-muted">
                Alerts that reached the target
              </p>
            </article>

            <article className="rounded-2xl border border-vextro-border bg-white p-5 shadow-sm">
              <div className="flex items-center justify-between gap-4">
                <span className="text-xs font-bold text-vextro-muted">
                  Notifications
                </span>

                <span className="grid size-9 place-items-center rounded-xl bg-blue-50 text-lg">
                  ✉️
                </span>
              </div>

              <strong className="mt-4 block text-3xl font-black tracking-tight text-vextro-primary">
                {statistics.notificationCount}
              </strong>

              <p className="mt-1 text-[11px] text-vextro-muted">
                Total alert notifications
              </p>
            </article>

            <article className="rounded-2xl border border-vextro-border bg-white p-5 shadow-sm">
              <div className="flex items-center justify-between gap-4">
                <span className="text-xs font-bold text-vextro-muted">
                  Alert products
                </span>

                <span className="grid size-9 place-items-center rounded-xl bg-amber-50 text-lg">
                  🛍️
                </span>
              </div>

              <strong className="mt-4 block text-3xl font-black tracking-tight text-amber-600">
                {statistics.linkedProductCount}
              </strong>

              <p className="mt-1 text-[11px] text-vextro-muted">
                Unique tracked products
              </p>
            </article>
          </div>
        ) : (
          <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <article className="rounded-2xl border border-vextro-border bg-white p-5 shadow-sm">
              <span className="text-xs font-bold text-vextro-muted">
                Account role
              </span>

              <strong className="mt-3 block text-2xl font-black capitalize text-vextro-primary">
                {primaryRole}
              </strong>
            </article>

            <article className="rounded-2xl border border-vextro-border bg-white p-5 shadow-sm">
              <span className="text-xs font-bold text-vextro-muted">
                Account status
              </span>

              <strong className="mt-3 block text-2xl font-black text-emerald-600">
                {accountStatus}
              </strong>
            </article>

            <article className="rounded-2xl border border-vextro-border bg-white p-5 shadow-sm">
              <span className="text-xs font-bold text-vextro-muted">
                Marketplaces
              </span>

              <strong className="mt-3 block text-2xl font-black text-vextro-ink">
                2
              </strong>

              <p className="mt-1 text-[11px] text-vextro-muted">
                Daraz and PriceOye
              </p>
            </article>

            <article className="rounded-2xl border border-vextro-border bg-white p-5 shadow-sm">
              <span className="text-xs font-bold text-vextro-muted">
                Workspace
              </span>

              <strong className="mt-3 block text-2xl font-black text-violet-600">
                Ready
              </strong>

              <p className="mt-1 text-[11px] text-vextro-muted">
                SME foundation connected
              </p>
            </article>
          </div>
        )}

        <div className="mt-8 grid gap-6 lg:grid-cols-[1.15fr_0.85fr]">
          <section className="rounded-3xl border border-vextro-border bg-white p-6 shadow-sm sm:p-8">
            <div className="flex items-center justify-between gap-5">
              <div>
                <span className="text-xs font-black uppercase tracking-[0.16em] text-vextro-primary">
                  Recent Activity
                </span>

                <h2 className="mt-2 text-2xl font-black tracking-tight text-vextro-ink">
                  {canUsePriceAlerts
                    ? "Recent price alerts"
                    : "SME workspace status"}
                </h2>
              </div>

              {canUsePriceAlerts &&
              alerts.length > 0 ? (
                <Link
                  className="text-xs font-black text-vextro-primary transition hover:text-vextro-primary-dark"
                  to="/alerts"
                >
                  View all →
                </Link>
              ) : null}
            </div>

            {canUsePriceAlerts ? (
              recentAlerts.length > 0 ? (
                <div className="mt-6 grid gap-4">
                  {recentAlerts.map((alert) => (
                    <article
                      className="flex flex-col justify-between gap-5 rounded-2xl border border-vextro-border bg-vextro-canvas p-5 sm:flex-row sm:items-center"
                      key={alert.id}
                    >
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <span
                            className={`rounded-full px-3 py-1 text-[9px] font-black uppercase ${
                              alert.is_active
                                ? "bg-emerald-100 text-emerald-700"
                                : "bg-slate-200 text-slate-600"
                            }`}
                          >
                            {alert.is_active
                              ? "Active"
                              : "Paused"}
                          </span>

                          {alert.is_triggered ? (
                            <span className="rounded-full bg-violet-100 px-3 py-1 text-[9px] font-black uppercase text-violet-700">
                              Triggered
                            </span>
                          ) : null}
                        </div>

                        <h3 className="mt-3 truncate text-base font-black text-vextro-ink">
                          {getAlertTitle(
                            alert,
                            productNames,
                          )}
                        </h3>

                        <p className="mt-1 text-xs text-vextro-muted">
                          Created{" "}
                          {formatDateTime(
                            alert.created_at,
                          )}
                        </p>
                      </div>

                      <div className="shrink-0 sm:text-right">
                        <span className="block text-[9px] font-black uppercase tracking-wide text-vextro-muted">
                          Target price
                        </span>

                        <strong className="mt-1 block text-lg font-black text-vextro-primary">
                          {formatPrice(
                            alert.target_price,
                            alert.currency,
                          )}
                        </strong>

                        {alert.canonical_product_id ? (
                          <Link
                            className="mt-2 inline-flex text-xs font-black text-vextro-muted transition hover:text-vextro-primary"
                            to={`/products/${alert.canonical_product_id}`}
                          >
                            View product →
                          </Link>
                        ) : (
                          <Link
                            className="mt-2 inline-flex text-xs font-black text-vextro-muted transition hover:text-vextro-primary"
                            to="/alerts"
                          >
                            Manage alert →
                          </Link>
                        )}
                      </div>
                    </article>
                  ))}
                </div>
              ) : (
                <div className="mt-6 grid min-h-64 place-content-center justify-items-center rounded-2xl border border-dashed border-slate-300 bg-vextro-canvas p-8 text-center">
                  <span className="grid size-16 place-items-center rounded-2xl bg-white text-3xl shadow-sm">
                    🔔
                  </span>

                  <h3 className="mt-5 text-xl font-black text-vextro-ink">
                    No alert activity yet
                  </h3>

                  <p className="mt-2 max-w-md text-sm leading-6 text-vextro-muted">
                    Open a product comparison page and
                    create your first target-price alert.
                  </p>

                  <Link
                    className="mt-5 inline-flex min-h-11 items-center justify-center rounded-xl bg-vextro-primary px-5 text-sm font-black text-white"
                    to="/products"
                  >
                    Find Products
                  </Link>
                </div>
              )
            ) : (
              <div className="mt-6 grid gap-4">
                {[
                  {
                    title:
                      "Marketplace Product Discovery",
                    description:
                      "Search the normalized Daraz and PriceOye catalog.",
                    status: "Available",
                  },
                  {
                  title:
                    "Competitor Monitoring",
                 description:
                   "Manage business products and tracked marketplace competitors from your SME workspace.",
                  status: "Available",
                },
                  {
                    title:
                      "Demand and Inventory Forecasting",
                    description:
                      "Forecasting will become available after sales-import integration.",
                    status: "Planned",
                  },
                ].map((item) => (
                  <article
                    className="flex flex-col justify-between gap-4 rounded-2xl border border-vextro-border bg-vextro-canvas p-5 sm:flex-row sm:items-center"
                    key={item.title}
                  >
                    <div>
                      <h3 className="text-sm font-black text-vextro-ink">
                        {item.title}
                      </h3>

                      <p className="mt-2 text-xs leading-5 text-vextro-muted">
                        {item.description}
                      </p>
                    </div>

                    <span className="shrink-0 rounded-full bg-white px-3 py-2 text-[10px] font-black text-vextro-primary">
                      {item.status}
                    </span>
                  </article>
                ))}
              </div>
            )}
          </section>

          <div className="grid gap-6">
            <section className="rounded-3xl border border-vextro-border bg-white p-6 shadow-sm sm:p-7">
              <span className="text-xs font-black uppercase tracking-[0.16em] text-vextro-primary">
                Account
              </span>

              <h2 className="mt-2 text-2xl font-black tracking-tight text-vextro-ink">
                Profile information
              </h2>

              <dl className="mt-6 grid gap-4">
                <div className="rounded-xl bg-vextro-canvas p-4">
                  <dt className="text-[10px] font-black uppercase tracking-wide text-vextro-muted">
                    Full name
                  </dt>

                  <dd className="mt-1 text-sm font-black text-vextro-ink">
                    {user?.full_name ||
                      "Not available"}
                  </dd>
                </div>

                <div className="rounded-xl bg-vextro-canvas p-4">
                  <dt className="text-[10px] font-black uppercase tracking-wide text-vextro-muted">
                    Email address
                  </dt>

                  <dd className="mt-1 break-all text-sm font-black text-vextro-ink">
                    {user?.email ||
                      "Not available"}
                  </dd>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div className="rounded-xl bg-vextro-canvas p-4">
                    <dt className="text-[10px] font-black uppercase tracking-wide text-vextro-muted">
                      Role
                    </dt>

                    <dd className="mt-1 text-sm font-black capitalize text-vextro-ink">
                      {user?.roles?.join(", ") ||
                        "User"}
                    </dd>
                  </div>

                  <div className="rounded-xl bg-vextro-canvas p-4">
                    <dt className="text-[10px] font-black uppercase tracking-wide text-vextro-muted">
                      Status
                    </dt>

                    <dd className="mt-1 text-sm font-black text-emerald-600">
                      {accountStatus}
                    </dd>
                  </div>
                </div>

                <div className="rounded-xl bg-vextro-canvas p-4">
                  <dt className="text-[10px] font-black uppercase tracking-wide text-vextro-muted">
                    Account created
                  </dt>

                  <dd className="mt-1 text-sm font-black text-vextro-ink">
                    {formatDateTime(
                      user?.created_at,
                    )}
                  </dd>
                </div>

                <div className="rounded-xl border border-blue-100 bg-blue-50 p-4">
                  <dt className="text-[10px] font-black uppercase tracking-wide text-vextro-primary">
                    Verification
                  </dt>

                  <dd className="mt-1 text-sm font-black text-vextro-ink">
                    {verificationStatus}
                  </dd>
                </div>
              </dl>
            </section>

            <section className="rounded-3xl border border-vextro-border bg-vextro-ink p-6 text-white shadow-sm sm:p-7">
              <span className="text-xs font-black uppercase tracking-[0.16em] text-blue-300">
                Quick Actions
              </span>

              <div className="mt-5 grid gap-3">
                <Link
                  className="flex min-h-12 items-center justify-between rounded-xl bg-white/10 px-4 text-sm font-black transition hover:bg-white/15"
                  to="/products"
                >
                  Browse Products
                  <span>→</span>
                </Link>

                {canUsePriceAlerts ? (
                  <Link
                    className="flex min-h-12 items-center justify-between rounded-xl bg-white/10 px-4 text-sm font-black transition hover:bg-white/15"
                    to="/alerts"
                  >
                    Manage Price Alerts
                    <span>→</span>
                  </Link>
                ) : null}

                {isAdmin ? (
                  <Link
                    className="flex min-h-12 items-center justify-between rounded-xl bg-white/10 px-4 text-sm font-black transition hover:bg-white/15"
                    to="/admin"
                  >
                    Open Admin Panel
                    <span>→</span>
                  </Link>
                ) : null}

               {canUseSmeWorkspace ? (
  <Link
    className="flex min-h-12 items-center justify-between rounded-xl bg-violet-500/20 px-4 text-sm font-black text-violet-100 transition hover:bg-violet-500/30"
    to="/sme"
  >
    Open SME Workspace
    <span>→</span>
  </Link>
) : null}
              </div>
            </section>
          </div>
        </div>
      </div>
    </section>
  );
}

export default DashboardPage;
