import { useEffect, useState } from "react";

function formatPrice(value, currency = "PKR") {
  const numericValue = Number(value);

  if (!Number.isFinite(numericValue)) {
    return "Unavailable";
  }

  try {
    return new Intl.NumberFormat("en-PK", {
      style: "currency",
      currency,
      maximumFractionDigits: 0,
    }).format(numericValue);
  } catch {
    return `${currency} ${numericValue.toLocaleString(
      "en-PK",
    )}`;
  }
}

function formatDate(value) {
  if (!value) {
    return "Not checked yet";
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "Not available";
  }

  return new Intl.DateTimeFormat("en-PK", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

function PriceAlertCard({
  alert,
  productName,
  listingTitle,
  currentPrice,
  onUpdate,
  onDeactivate,
  isBusy,
}) {
  const [targetPrice, setTargetPrice] = useState(
    alert.target_price,
  );

  const [localError, setLocalError] = useState("");

  useEffect(() => {
    setTargetPrice(alert.target_price);
  }, [alert.target_price]);

  async function handleSaveTarget() {
    const numericTarget = Number(targetPrice);

    if (
      !Number.isFinite(numericTarget) ||
      numericTarget <= 0
    ) {
      setLocalError(
        "Target price must be greater than zero.",
      );
      return;
    }

    setLocalError("");

    await onUpdate(alert.id, {
      target_price: numericTarget,
    });
  }

  async function handleStatusChange() {
    setLocalError("");

    if (alert.is_active) {
      await onDeactivate(alert.id);
      return;
    }

    await onUpdate(alert.id, {
      is_active: true,
    });
  }

  const isProductAlert =
    alert.canonical_product_id !== null;

  return (
    <article
      className={`relative flex h-full flex-col rounded-3xl border bg-white p-6 shadow-sm transition duration-300 hover:-translate-y-1 hover:shadow-vextro ${
        alert.is_triggered
          ? "border-emerald-300"
          : alert.is_active
            ? "border-vextro-border"
            : "border-slate-200 opacity-80"
      }`}
    >
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <span
            className={`inline-flex rounded-full px-3 py-1.5 text-[10px] font-black uppercase tracking-wider ${
              isProductAlert
                ? "bg-blue-50 text-vextro-primary"
                : "bg-violet-50 text-violet-700"
            }`}
          >
            {isProductAlert
              ? "Product Alert"
              : "Listing Alert"}
          </span>

          <h2 className="mt-4 text-xl font-black leading-7 tracking-tight text-vextro-ink">
            {productName}
          </h2>

          {listingTitle ? (
            <p className="mt-2 line-clamp-2 text-xs leading-5 text-vextro-muted">
              {listingTitle}
            </p>
          ) : (
            <p className="mt-2 text-xs text-vextro-muted">
              Watches all available marketplace listings.
            </p>
          )}
        </div>

        <div
          className={`rounded-full px-3 py-1.5 text-[10px] font-black uppercase tracking-wider ${
            alert.is_triggered
              ? "bg-emerald-50 text-emerald-700"
              : alert.is_active
                ? "bg-blue-50 text-blue-700"
                : "bg-slate-100 text-slate-500"
          }`}
        >
          {alert.is_triggered
            ? "Target Reached"
            : alert.is_active
              ? "Active"
              : "Inactive"}
        </div>
      </div>

      <div className="mt-6 grid grid-cols-2 gap-3">
        <div className="rounded-2xl bg-vextro-canvas p-4">
          <span className="text-[10px] font-bold uppercase tracking-wide text-vextro-muted">
            Target Price
          </span>

          <strong className="mt-2 block text-lg font-black text-vextro-primary">
            {formatPrice(
              alert.target_price,
              alert.currency,
            )}
          </strong>
        </div>

        <div className="rounded-2xl bg-vextro-canvas p-4">
          <span className="text-[10px] font-bold uppercase tracking-wide text-vextro-muted">
            Current Price
          </span>

          <strong className="mt-2 block text-lg font-black text-vextro-ink">
            {currentPrice
              ? formatPrice(
                  currentPrice,
                  alert.currency,
                )
              : "Unavailable"}
          </strong>
        </div>
      </div>

      <div className="mt-5 rounded-2xl border border-vextro-border p-4">
        <label
          className="text-xs font-black text-vextro-ink"
          htmlFor={`target-price-${alert.id}`}
        >
          Update target price
        </label>

        <div className="mt-2 flex gap-2">
          <input
            id={`target-price-${alert.id}`}
            className="min-h-11 min-w-0 flex-1 rounded-xl border border-vextro-border px-3 text-sm font-semibold text-vextro-ink outline-none transition focus:border-vextro-primary focus:ring-4 focus:ring-blue-100"
            type="number"
            min="0.01"
            step="0.01"
            value={targetPrice}
            onChange={(event) => {
              setTargetPrice(event.target.value);
              setLocalError("");
            }}
            disabled={isBusy}
          />

          <button
            className="rounded-xl bg-vextro-primary px-4 text-xs font-black text-white transition hover:bg-vextro-primary-dark disabled:cursor-not-allowed disabled:opacity-50"
            type="button"
            onClick={handleSaveTarget}
            disabled={isBusy}
          >
            Save
          </button>
        </div>

        {localError ? (
          <p className="mt-2 text-xs font-semibold text-red-600">
            {localError}
          </p>
        ) : null}
      </div>

      <div className="mt-5 grid gap-3 text-xs">
        <div className="flex items-center justify-between gap-4">
          <span className="text-vextro-muted">
            Last checked
          </span>

          <strong className="text-right text-vextro-ink">
            {formatDate(alert.last_checked_at)}
          </strong>
        </div>

        <div className="flex items-center justify-between gap-4">
          <span className="text-vextro-muted">
            Notifications sent
          </span>

          <strong className="text-vextro-ink">
            {alert.notification_count}
          </strong>
        </div>

        <div className="flex items-center justify-between gap-4">
          <span className="text-vextro-muted">
            Created
          </span>

          <strong className="text-right text-vextro-ink">
            {formatDate(alert.created_at)}
          </strong>
        </div>
      </div>

      <button
        className={`mt-auto min-h-11 rounded-xl px-5 pt-0 text-sm font-black transition ${
          alert.is_active
            ? "mt-6 border border-red-200 bg-red-50 text-red-600 hover:bg-red-100"
            : "mt-6 bg-emerald-600 text-white hover:bg-emerald-700"
        } disabled:cursor-not-allowed disabled:opacity-50`}
        type="button"
        onClick={handleStatusChange}
        disabled={isBusy}
      >
        {isBusy
          ? "Updating..."
          : alert.is_active
            ? "Deactivate Alert"
            : "Reactivate Alert"}
      </button>
    </article>
  );
}

export default PriceAlertCard;