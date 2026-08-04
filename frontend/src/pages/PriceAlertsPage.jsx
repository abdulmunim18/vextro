import {
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";
import { Link } from "react-router-dom";

import RouteLoadingState from "../components/RouteLoadingState";
import { getProductById } from "../services/catalogService";
import {
  deactivatePriceAlert,
  getPriceAlerts,
  updatePriceAlert,
} from "../services/priceAlertService";
import { getApiErrorMessage } from "../utils/apiError";
import {
  formatDateTime,
  formatPrice,
  toFiniteNumber,
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

function getAlertTargetLabel(alert, productNames) {
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

function PriceAlertsPage() {
  const [alerts, setAlerts] = useState([]);
  const [productNames, setProductNames] = useState(
    new Map(),
  );

  const [draftPrices, setDraftPrices] = useState({});
  const [isLoading, setIsLoading] = useState(true);
  const [processingAlertId, setProcessingAlertId] =
    useState(null);

  const [errorMessage, setErrorMessage] = useState("");
  const [successMessage, setSuccessMessage] =
    useState("");

  const loadAlerts = useCallback(async () => {
    setIsLoading(true);
    setErrorMessage("");

    try {
      const responseData = await getPriceAlerts();
      const responseAlerts = extractAlerts(responseData);

      setAlerts(responseAlerts);

      setDraftPrices(
        Object.fromEntries(
          responseAlerts.map((alert) => [
            alert.id,
            String(alert.target_price),
          ]),
        ),
      );

      const uniqueProductIds = [
        ...new Set(
          responseAlerts
            .map(
              (alert) => alert.canonical_product_id,
            )
            .filter(Boolean),
        ),
      ];

      if (uniqueProductIds.length === 0) {
        setProductNames(new Map());
        return;
      }

      const productResults = await Promise.allSettled(
        uniqueProductIds.map(async (productId) => {
          const product = await getProductById(productId);

          return {
            id: productId,
            name:
              product?.name ||
              `Product #${productId}`,
          };
        }),
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
          "Unable to load your price alerts.",
        ),
      );
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAlerts();
  }, [loadAlerts]);

  const statistics = useMemo(() => {
    const active = alerts.filter(
      (alert) => alert.is_active,
    ).length;

    const paused = alerts.filter(
      (alert) => !alert.is_active,
    ).length;

    const triggered = alerts.filter(
      (alert) => alert.is_triggered,
    ).length;

    const notifications = alerts.reduce(
      (total, alert) =>
        total + (alert.notification_count || 0),
      0,
    );

    return {
      active,
      paused,
      triggered,
      notifications,
    };
  }, [alerts]);

  function handleDraftPriceChange(alertId, value) {
    setDraftPrices((currentPrices) => ({
      ...currentPrices,
      [alertId]: value,
    }));

    setErrorMessage("");
    setSuccessMessage("");
  }

  async function handleTargetPriceUpdate(alert) {
    const nextTargetPrice = toFiniteNumber(
      draftPrices[alert.id],
    );

    if (
      nextTargetPrice === null ||
      nextTargetPrice <= 0
    ) {
      setErrorMessage(
        "Target price must be greater than zero.",
      );

      return;
    }

    setProcessingAlertId(alert.id);
    setErrorMessage("");
    setSuccessMessage("");

    try {
      const updatedAlert = await updatePriceAlert(
        alert.id,
        {
          target_price: nextTargetPrice,
        },
      );

      setAlerts((currentAlerts) =>
        currentAlerts.map((currentAlert) =>
          currentAlert.id === updatedAlert.id
            ? updatedAlert
            : currentAlert,
        ),
      );

      setDraftPrices((currentPrices) => ({
        ...currentPrices,
        [updatedAlert.id]: String(
          updatedAlert.target_price,
        ),
      }));

      setSuccessMessage(
        "Target price updated successfully.",
      );
    } catch (error) {
      setErrorMessage(
        getApiErrorMessage(
          error,
          "Unable to update this alert.",
        ),
      );
    } finally {
      setProcessingAlertId(null);
    }
  }

  async function handleDeactivate(alert) {
    const confirmed = window.confirm(
      "Pause this price alert?",
    );

    if (!confirmed) {
      return;
    }

    setProcessingAlertId(alert.id);
    setErrorMessage("");
    setSuccessMessage("");

    try {
      const updatedAlert =
        await deactivatePriceAlert(alert.id);

      setAlerts((currentAlerts) =>
        currentAlerts.map((currentAlert) =>
          currentAlert.id === updatedAlert.id
            ? updatedAlert
            : currentAlert,
        ),
      );

      setSuccessMessage(
        "Price alert paused successfully.",
      );
    } catch (error) {
      setErrorMessage(
        getApiErrorMessage(
          error,
          "Unable to pause this alert.",
        ),
      );
    } finally {
      setProcessingAlertId(null);
    }
  }

  async function handleReactivate(alert) {
    setProcessingAlertId(alert.id);
    setErrorMessage("");
    setSuccessMessage("");

    try {
      const updatedAlert = await updatePriceAlert(
        alert.id,
        {
          is_active: true,
        },
      );

      setAlerts((currentAlerts) =>
        currentAlerts.map((currentAlert) =>
          currentAlert.id === updatedAlert.id
            ? updatedAlert
            : currentAlert,
        ),
      );

      setSuccessMessage(
        "Price alert reactivated successfully.",
      );
    } catch (error) {
      setErrorMessage(
        getApiErrorMessage(
          error,
          "Unable to reactivate this alert.",
        ),
      );
    } finally {
      setProcessingAlertId(null);
    }
  }

  if (isLoading) {
    return (
      <RouteLoadingState message="Loading your price alerts..." />
    );
  }

  return (
    <section className="relative min-h-[calc(100vh-145px)] overflow-hidden bg-vextro-canvas py-14 sm:py-18 lg:py-20">
      <div className="pointer-events-none absolute -right-48 top-0 size-[460px] rounded-full bg-blue-300/15 blur-3xl" />

      <div className="relative mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="flex flex-col items-start justify-between gap-7 lg:flex-row lg:items-end">
          <div className="max-w-3xl">
            <span className="text-xs font-black uppercase tracking-[0.18em] text-vextro-primary">
              Price Intelligence
            </span>

            <h1 className="mt-4 text-4xl font-black leading-[1.02] tracking-[-0.05em] text-vextro-ink sm:text-5xl lg:text-6xl">
              Manage your price alerts
            </h1>

            <p className="mt-5 max-w-2xl text-sm leading-7 text-vextro-muted sm:text-base">
              Review target prices, pause alerts and reactivate
              them whenever you are ready to continue tracking.
            </p>
          </div>

          <Link
            className="inline-flex min-h-12 items-center justify-center gap-2 rounded-xl bg-vextro-primary px-6 text-sm font-black text-white shadow-lg shadow-blue-500/20 transition hover:-translate-y-0.5 hover:bg-vextro-primary-dark"
            to="/products"
          >
            Find a Product
            <span>→</span>
          </Link>
        </div>

        <div className="mt-10 grid grid-cols-2 gap-4 lg:grid-cols-4">
          <div className="rounded-2xl border border-vextro-border bg-white p-5 shadow-sm">
            <span className="text-xs font-bold text-vextro-muted">
              Active alerts
            </span>

            <strong className="mt-2 block text-3xl font-black text-emerald-600">
              {statistics.active}
            </strong>
          </div>

          <div className="rounded-2xl border border-vextro-border bg-white p-5 shadow-sm">
            <span className="text-xs font-bold text-vextro-muted">
              Paused alerts
            </span>

            <strong className="mt-2 block text-3xl font-black text-vextro-muted">
              {statistics.paused}
            </strong>
          </div>

          <div className="rounded-2xl border border-vextro-border bg-white p-5 shadow-sm">
            <span className="text-xs font-bold text-vextro-muted">
              Triggered alerts
            </span>

            <strong className="mt-2 block text-3xl font-black text-violet-600">
              {statistics.triggered}
            </strong>
          </div>

          <div className="rounded-2xl border border-vextro-border bg-white p-5 shadow-sm">
            <span className="text-xs font-bold text-vextro-muted">
              Notifications
            </span>

            <strong className="mt-2 block text-3xl font-black text-vextro-primary">
              {statistics.notifications}
            </strong>
          </div>
        </div>

        {successMessage ? (
          <div
            className="mt-7 rounded-2xl border border-emerald-200 bg-emerald-50 px-5 py-4 text-sm font-bold text-emerald-700"
            role="status"
          >
            {successMessage}
          </div>
        ) : null}

        {errorMessage ? (
          <div
            className="mt-7 flex flex-col items-start justify-between gap-4 rounded-2xl border border-red-200 bg-red-50 px-5 py-4 text-red-700 sm:flex-row sm:items-center"
            role="alert"
          >
            <span className="text-sm font-bold">
              {errorMessage}
            </span>

            <button
              className="rounded-xl border border-red-200 bg-white px-4 py-2 text-xs font-black"
              type="button"
              onClick={loadAlerts}
            >
              Reload
            </button>
          </div>
        ) : null}

        {alerts.length > 0 ? (
          <div className="mt-8 grid gap-5">
            {alerts.map((alert) => {
              const isProcessing =
                processingAlertId === alert.id;

              return (
                <article
                  className={`overflow-hidden rounded-3xl border bg-white shadow-sm ${
                    alert.is_triggered
                      ? "border-violet-300"
                      : alert.is_active
                        ? "border-vextro-border"
                        : "border-slate-200 opacity-90"
                  }`}
                  key={alert.id}
                >
                  <div className="grid lg:grid-cols-[1fr_360px]">
                    <div className="p-6 sm:p-7">
                      <div className="flex flex-wrap items-center gap-2">
                        <span
                          className={`rounded-full px-3 py-1.5 text-[10px] font-black uppercase tracking-wide ${
                            alert.is_active
                              ? "bg-emerald-50 text-emerald-700"
                              : "bg-slate-100 text-slate-600"
                          }`}
                        >
                          {alert.is_active
                            ? "Active"
                            : "Paused"}
                        </span>

                        {alert.is_triggered ? (
                          <span className="rounded-full bg-violet-100 px-3 py-1.5 text-[10px] font-black uppercase tracking-wide text-violet-700">
                            Target reached
                          </span>
                        ) : null}

                        <span className="rounded-full bg-blue-50 px-3 py-1.5 text-[10px] font-black text-vextro-primary">
                          Alert #{alert.id}
                        </span>
                      </div>

                      <h2 className="mt-5 text-2xl font-black tracking-tight text-vextro-ink">
                        {getAlertTargetLabel(
                          alert,
                          productNames,
                        )}
                      </h2>

                      <p className="mt-2 text-xs text-vextro-muted">
                        {alert.canonical_product_id
                          ? `Product-level alert · Product ID ${alert.canonical_product_id}`
                          : `Listing-level alert · Listing ID ${alert.listing_id}`}
                      </p>

                      <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
                        <div className="rounded-xl bg-vextro-canvas p-4">
                          <span className="text-[9px] font-black uppercase text-vextro-muted">
                            Target
                          </span>

                          <strong className="mt-1 block text-sm font-black text-vextro-ink">
                            {formatPrice(
                              alert.target_price,
                              alert.currency,
                            )}
                          </strong>
                        </div>

                        <div className="rounded-xl bg-vextro-canvas p-4">
                          <span className="text-[9px] font-black uppercase text-vextro-muted">
                            Notifications
                          </span>

                          <strong className="mt-1 block text-sm font-black text-vextro-primary">
                            {alert.notification_count}
                          </strong>
                        </div>

                        <div className="rounded-xl bg-vextro-canvas p-4">
                          <span className="text-[9px] font-black uppercase text-vextro-muted">
                            Last checked
                          </span>

                          <strong className="mt-1 block text-xs font-black text-vextro-ink">
                            {formatDateTime(
                              alert.last_checked_at,
                            )}
                          </strong>
                        </div>

                        <div className="rounded-xl bg-vextro-canvas p-4">
                          <span className="text-[9px] font-black uppercase text-vextro-muted">
                            Created
                          </span>

                          <strong className="mt-1 block text-xs font-black text-vextro-ink">
                            {formatDateTime(
                              alert.created_at,
                            )}
                          </strong>
                        </div>
                      </div>
                    </div>

                    <div className="border-t border-vextro-border bg-slate-50/70 p-6 lg:border-l lg:border-t-0">
                      <label
                        className="text-xs font-black text-vextro-ink"
                        htmlFor={`alert-price-${alert.id}`}
                      >
                        Target price
                      </label>

                      <div className="mt-2 flex min-h-12 overflow-hidden rounded-xl border border-vextro-border bg-white focus-within:border-vextro-primary focus-within:ring-4 focus-within:ring-blue-100">
                        <span className="grid place-items-center border-r border-vextro-border px-4 text-xs font-black text-vextro-muted">
                          {alert.currency}
                        </span>

                        <input
                          id={`alert-price-${alert.id}`}
                          className="min-w-0 flex-1 border-0 px-4 text-sm font-bold text-vextro-ink outline-none"
                          type="number"
                          min="0.01"
                          step="0.01"
                          value={
                            draftPrices[alert.id] ?? ""
                          }
                          onChange={(event) =>
                            handleDraftPriceChange(
                              alert.id,
                              event.target.value,
                            )
                          }
                        />
                      </div>

                      <button
                        className="mt-3 min-h-11 w-full rounded-xl bg-vextro-primary px-4 text-sm font-black text-white transition hover:bg-vextro-primary-dark disabled:cursor-not-allowed disabled:opacity-50"
                        type="button"
                        disabled={isProcessing}
                        onClick={() =>
                          handleTargetPriceUpdate(alert)
                        }
                      >
                        {isProcessing
                          ? "Processing..."
                          : "Update Target Price"}
                      </button>

                      {alert.is_active ? (
                        <button
                          className="mt-3 min-h-11 w-full rounded-xl border border-amber-200 bg-amber-50 px-4 text-sm font-black text-amber-700 transition hover:bg-amber-100 disabled:cursor-not-allowed disabled:opacity-50"
                          type="button"
                          disabled={isProcessing}
                          onClick={() =>
                            handleDeactivate(alert)
                          }
                        >
                          Pause Alert
                        </button>
                      ) : (
                        <button
                          className="mt-3 min-h-11 w-full rounded-xl border border-emerald-200 bg-emerald-50 px-4 text-sm font-black text-emerald-700 transition hover:bg-emerald-100 disabled:cursor-not-allowed disabled:opacity-50"
                          type="button"
                          disabled={isProcessing}
                          onClick={() =>
                            handleReactivate(alert)
                          }
                        >
                          Reactivate Alert
                        </button>
                      )}
                    </div>
                  </div>
                </article>
              );
            })}
          </div>
        ) : (
          <div className="mt-8 grid min-h-96 place-content-center justify-items-center rounded-3xl border border-dashed border-slate-300 bg-white p-8 text-center">
            <span className="grid size-20 place-items-center rounded-3xl bg-blue-50 text-4xl">
              🔔
            </span>

            <h2 className="mt-6 text-2xl font-black text-vextro-ink">
              No price alerts yet
            </h2>

            <p className="mt-3 max-w-lg text-sm leading-7 text-vextro-muted">
              Browse marketplace products and create a target
              price alert from a product comparison page.
            </p>

            <Link
              className="mt-6 inline-flex min-h-12 items-center justify-center rounded-xl bg-vextro-primary px-6 text-sm font-black text-white"
              to="/products"
            >
              Browse Products
            </Link>
          </div>
        )}
      </div>
    </section>
  );
}

export default PriceAlertsPage;