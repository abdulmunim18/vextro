import { useEffect, useMemo, useState } from "react";
import { Link, useLocation } from "react-router-dom";

import { useAuth } from "../context/AuthContext";
import { createPriceAlert } from "../services/priceAlertService";
import { getApiErrorMessage } from "../utils/apiError";
import {
  formatPrice,
  toFiniteNumber,
} from "../utils/productDisplay";

function CreatePriceAlertCard({
  product,
  listings,
  platformNames,
  lowestListing,
}) {
  const location = useLocation();

  const {
    isAuthenticated,
    isInitializing,
    hasRole,
  } = useAuth();

  const [targetType, setTargetType] =
    useState("product");

  const [selectedListingId, setSelectedListingId] =
    useState("");

  const [targetPrice, setTargetPrice] = useState("");

  const [currency, setCurrency] = useState(
    lowestListing?.currency || "PKR",
  );

  const [isSubmitting, setIsSubmitting] =
    useState(false);

  const [errorMessage, setErrorMessage] =
    useState("");

  const [createdAlert, setCreatedAlert] =
    useState(null);

  const normalizedListings = useMemo(
    () =>
      Array.isArray(listings)
        ? listings
        : [],
    [listings],
  );

  useEffect(() => {
    const preferredListing =
      lowestListing || normalizedListings[0];

    if (preferredListing) {
      setSelectedListingId(
        String(preferredListing.id),
      );

      setCurrency(
        preferredListing.currency || "PKR",
      );
    }
  }, [lowestListing, normalizedListings]);

  const selectedListing =
    normalizedListings.find(
      (listing) =>
        listing.id === Number(selectedListingId),
    ) || null;

  function handleTargetTypeChange(event) {
    const nextTargetType = event.target.value;

    setTargetType(nextTargetType);
    setErrorMessage("");
    setCreatedAlert(null);

    if (
      nextTargetType === "listing" &&
      selectedListing
    ) {
      setCurrency(
        selectedListing.currency || "PKR",
      );
    }
  }

  function handleListingChange(event) {
    const nextListingId = event.target.value;

    setSelectedListingId(nextListingId);
    setErrorMessage("");
    setCreatedAlert(null);

    const nextListing = normalizedListings.find(
      (listing) =>
        listing.id === Number(nextListingId),
    );

    if (nextListing?.currency) {
      setCurrency(nextListing.currency);
    }
  }

  async function handleSubmit(event) {
    event.preventDefault();

    setErrorMessage("");
    setCreatedAlert(null);

    const numericTargetPrice =
      toFiniteNumber(targetPrice);

    if (
      numericTargetPrice === null ||
      numericTargetPrice <= 0
    ) {
      setErrorMessage(
        "Target price must be greater than zero.",
      );

      return;
    }

    if (
      targetType === "listing" &&
      !selectedListingId
    ) {
      setErrorMessage(
        "Please select a marketplace listing.",
      );

      return;
    }

    setIsSubmitting(true);

    const payload = {
      target_price: numericTargetPrice,
      currency: currency
        .trim()
        .toUpperCase(),
    };

    if (targetType === "product") {
      payload.canonical_product_id = product.id;
    } else {
      payload.listing_id = Number(
        selectedListingId,
      );
    }

    try {
      const responseData =
        await createPriceAlert(payload);

      setCreatedAlert(responseData);
      setTargetPrice("");
    } catch (error) {
      setErrorMessage(
        getApiErrorMessage(
          error,
          "Unable to create this price alert.",
        ),
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  if (isInitializing) {
    return (
      <div className="mt-6 animate-pulse rounded-2xl border border-vextro-border bg-vextro-canvas p-5">
        <div className="h-4 w-2/5 rounded-full bg-slate-200" />
        <div className="mt-4 h-12 rounded-xl bg-slate-200" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <div className="mt-6 rounded-2xl border border-blue-200 bg-blue-50 p-5">
        <span className="text-[10px] font-black uppercase tracking-[0.14em] text-vextro-primary">
          Price Alert
        </span>

        <h2 className="mt-2 text-lg font-black text-vextro-ink">
          Track this product automatically
        </h2>

        <p className="mt-2 text-xs leading-6 text-vextro-muted">
          Log in to choose a target price and receive an
          alert when the marketplace price reaches it.
        </p>

        <Link
          className="mt-5 inline-flex min-h-11 w-full items-center justify-center rounded-xl bg-vextro-primary px-5 text-sm font-black text-white shadow-lg shadow-blue-500/20 transition hover:bg-vextro-primary-dark"
          to="/login"
          state={{
            from: `${location.pathname}${location.search}`,
            message:
              "Please log in to create a price alert.",
          }}
        >
          Login to Create Alert
        </Link>
      </div>
    );
  }

  if (!hasRole("consumer", "admin")) {
    return (
      <div className="mt-6 rounded-2xl border border-amber-200 bg-amber-50 p-5">
        <span className="text-[10px] font-black uppercase tracking-[0.14em] text-amber-700">
          Consumer Feature
        </span>

        <h2 className="mt-2 text-lg font-black text-vextro-ink">
          Price alerts are not available for this role
        </h2>

        <p className="mt-2 text-xs leading-6 text-amber-800">
          Your current account is configured for SME
          intelligence tools.
        </p>
      </div>
    );
  }

  return (
    <div className="mt-6 rounded-2xl border border-blue-200 bg-blue-50/70 p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <span className="text-[10px] font-black uppercase tracking-[0.14em] text-vextro-primary">
            Personalized Alert
          </span>

          <h2 className="mt-2 text-lg font-black text-vextro-ink">
            Create a price alert
          </h2>

          <p className="mt-2 text-xs leading-6 text-vextro-muted">
            Select what you want to track and enter your
            preferred target price.
          </p>
        </div>

        <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-white text-xl shadow-sm">
          🔔
        </span>
      </div>

      {createdAlert ? (
        <div
          className="mt-5 rounded-xl border border-emerald-200 bg-emerald-50 p-4"
          role="status"
        >
          <strong className="block text-sm font-black text-emerald-700">
            Price alert created successfully
          </strong>

          <p className="mt-1 text-xs leading-5 text-emerald-700">
            Target:{" "}
            {formatPrice(
              createdAlert.target_price,
              createdAlert.currency,
            )}
          </p>

          <Link
            className="mt-3 inline-flex text-xs font-black text-emerald-800 underline"
            to="/alerts"
          >
            View all price alerts →
          </Link>
        </div>
      ) : null}

      {errorMessage ? (
        <div
          className="mt-5 rounded-xl border border-red-200 bg-red-50 p-4 text-xs font-bold leading-5 text-red-700"
          role="alert"
        >
          {errorMessage}
        </div>
      ) : null}

      <form
        className="mt-5 grid gap-4"
        onSubmit={handleSubmit}
      >
        <div className="grid gap-2">
          <label
            className="text-xs font-black text-vextro-ink"
            htmlFor="alert-target-type"
          >
            Alert target
          </label>

          <select
            id="alert-target-type"
            className="min-h-12 w-full cursor-pointer rounded-xl border border-vextro-border bg-white px-4 text-sm font-bold text-vextro-ink outline-none transition focus:border-vextro-primary focus:ring-4 focus:ring-blue-100"
            value={targetType}
            onChange={handleTargetTypeChange}
          >
            <option value="product">
              Any marketplace offer for this product
            </option>

            <option
              value="listing"
              disabled={
                normalizedListings.length === 0
              }
            >
              One specific marketplace listing
            </option>
          </select>
        </div>

        {targetType === "listing" ? (
          <div className="grid gap-2">
            <label
              className="text-xs font-black text-vextro-ink"
              htmlFor="alert-listing"
            >
              Marketplace listing
            </label>

            <select
              id="alert-listing"
              className="min-h-12 w-full cursor-pointer rounded-xl border border-vextro-border bg-white px-4 text-sm font-bold text-vextro-ink outline-none transition focus:border-vextro-primary focus:ring-4 focus:ring-blue-100"
              value={selectedListingId}
              onChange={handleListingChange}
              required
            >
              <option value="">
                Select a listing
              </option>

              {normalizedListings.map((listing) => {
                const platformName =
                  platformNames.get(
                    listing.platform_id,
                  ) ||
                  `Platform ${listing.platform_id}`;

                const sellerName =
                  listing.seller?.name ||
                  "Marketplace seller";

                return (
                  <option
                    key={listing.id}
                    value={listing.id}
                  >
                    {platformName} — {sellerName} —{" "}
                    {formatPrice(
                      listing.current_price,
                      listing.currency,
                    )}
                  </option>
                );
              })}
            </select>

            {selectedListing ? (
              <p className="text-[11px] leading-5 text-vextro-muted">
                Current listing price:{" "}
                <strong className="text-vextro-ink">
                  {formatPrice(
                    selectedListing.current_price,
                    selectedListing.currency,
                  )}
                </strong>
              </p>
            ) : null}
          </div>
        ) : (
          <div className="rounded-xl border border-blue-100 bg-white/80 p-4">
            <span className="block text-[10px] font-black uppercase tracking-wide text-vextro-muted">
              Current lowest offer
            </span>

            <strong className="mt-1 block text-lg font-black text-emerald-700">
              {lowestListing
                ? formatPrice(
                    lowestListing.current_price,
                    lowestListing.currency,
                  )
                : "No available offer"}
            </strong>
          </div>
        )}

        <div className="grid grid-cols-[90px_1fr] gap-3">
          <div className="grid gap-2">
            <label
              className="text-xs font-black text-vextro-ink"
              htmlFor="alert-currency"
            >
              Currency
            </label>

            <input
              id="alert-currency"
              className="min-h-12 w-full rounded-xl border border-vextro-border bg-white px-3 text-center text-sm font-black uppercase text-vextro-ink outline-none transition focus:border-vextro-primary focus:ring-4 focus:ring-blue-100"
              type="text"
              value={currency}
              onChange={(event) => {
                setCurrency(event.target.value);
                setErrorMessage("");
                setCreatedAlert(null);
              }}
              minLength={3}
              maxLength={3}
              required
            />
          </div>

          <div className="grid gap-2">
            <label
              className="text-xs font-black text-vextro-ink"
              htmlFor="alert-target-price"
            >
              Target price
            </label>

            <input
              id="alert-target-price"
              className="min-h-12 w-full rounded-xl border border-vextro-border bg-white px-4 text-sm font-bold text-vextro-ink outline-none transition placeholder:text-slate-400 focus:border-vextro-primary focus:ring-4 focus:ring-blue-100"
              type="number"
              value={targetPrice}
              onChange={(event) => {
                setTargetPrice(event.target.value);
                setErrorMessage("");
                setCreatedAlert(null);
              }}
              min="0.01"
              step="0.01"
              placeholder="Enter preferred price"
              required
            />
          </div>
        </div>

        <button
          className="min-h-12 w-full rounded-xl bg-vextro-primary px-5 text-sm font-black text-white shadow-lg shadow-blue-500/20 transition hover:-translate-y-0.5 hover:bg-vextro-primary-dark disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:translate-y-0"
          type="submit"
          disabled={isSubmitting}
        >
          {isSubmitting
            ? "Creating Alert..."
            : "Create Price Alert"}
        </button>
      </form>
    </div>
  );
}

export default CreatePriceAlertCard;