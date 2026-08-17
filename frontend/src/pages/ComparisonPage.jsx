import {
  useEffect,
  useMemo,
  useState,
} from "react";
import {
  Link,
  useSearchParams,
} from "react-router-dom";

import { getProductComparison } from "../services/catalogService";
import { getApiErrorMessage } from "../utils/apiError";


function parseProductIds(value) {
  const rawIds = value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);

  if (rawIds.length < 2 || rawIds.length > 3) {
    return null;
  }

  const productIds = rawIds.map(Number);

  if (
    productIds.some(
      (productId) =>
        !Number.isInteger(productId) ||
        productId < 1,
    )
  ) {
    return null;
  }

  if (new Set(productIds).size !== productIds.length) {
    return null;
  }

  return productIds;
}


function formatCurrency(value, currency = "PKR") {
  const numericValue = Number(value);

  if (!Number.isFinite(numericValue)) {
    return "—";
  }

  try {
    return new Intl.NumberFormat("en-PK", {
      style: "currency",
      currency,
      maximumFractionDigits: 0,
    }).format(numericValue);
  } catch {
    return `${currency} ${numericValue.toLocaleString()}`;
  }
}


function formatSpecificationValue(value) {
  if (
    value === null ||
    value === undefined ||
    value === ""
  ) {
    return "—";
  }

  if (typeof value === "object") {
    return JSON.stringify(value);
  }

  return String(value);
}


function getLowestListing(item) {
  const listings = Array.isArray(item?.listings?.items)
    ? item.listings.items
    : [];

  if (listings.length === 0) {
    return null;
  }

  return listings.reduce((lowest, listing) =>
    Number(listing.current_price) <
    Number(lowest.current_price)
      ? listing
      : lowest,
  );
}


function getPlatformName(item, platformId) {
  const histories = Array.isArray(
    item?.price_history?.listings,
  )
    ? item.price_history.listings
    : [];

  const matchingHistory = histories.find(
    (history) => history.platform_id === platformId,
  );

  return (
    matchingHistory?.platform_name ||
    `Marketplace ${platformId}`
  );
}


function ComparisonPage() {
  const [searchParams] = useSearchParams();

  const idsParam = searchParams.get("ids") || "";

  const productIds = useMemo(
    () => parseProductIds(idsParam),
    [idsParam],
  );

  const requestKey = productIds
    ? productIds.join(",")
    : "";

  const [requestState, setRequestState] = useState({
    key: "",
    data: null,
    error: "",
  });

  useEffect(() => {
    if (!productIds || !requestKey) {
      return undefined;
    }

    let isCancelled = false;

    getProductComparison(productIds)
      .then((responseData) => {
        if (isCancelled) {
          return;
        }

        setRequestState({
          key: requestKey,
          data: responseData,
          error: "",
        });
      })
      .catch((error) => {
        if (isCancelled) {
          return;
        }

        setRequestState({
          key: requestKey,
          data: null,
          error: getApiErrorMessage(
            error,
            "Unable to load this product comparison.",
          ),
        });
      });

    return () => {
      isCancelled = true;
    };
  }, [productIds, requestKey]);

  const comparison =
    requestState.key === requestKey
      ? requestState.data
      : null;

  const errorMessage =
    requestState.key === requestKey
      ? requestState.error
      : "";

  const isLoading =
    Boolean(requestKey) &&
    requestState.key !== requestKey;

  const items = useMemo(
    () =>
      Array.isArray(comparison?.items)
        ? comparison.items
        : [],
    [comparison],
  );

  const specificationKeys = useMemo(() => {
    const keys = new Set();

    items.forEach((item) => {
      Object.keys(
        item?.product?.specifications || {},
      ).forEach((key) => {
        keys.add(key);
      });
    });

    return Array.from(keys).sort((a, b) =>
      a.localeCompare(b),
    );
  }, [items]);

  if (!productIds) {
    return (
      <section className="min-h-[calc(100vh-120px)] bg-vextro-canvas px-4 py-16">
        <div className="mx-auto max-w-3xl rounded-3xl border border-amber-200 bg-white p-8 text-center shadow-sm sm:p-12">
          <span className="mx-auto grid size-16 place-items-center rounded-2xl bg-amber-50 text-2xl font-black text-amber-700">
            !
          </span>

          <h1 className="mt-6 text-3xl font-black tracking-tight text-vextro-ink">
            Select 2 or 3 products to compare
          </h1>

          <p className="mx-auto mt-4 max-w-xl text-sm leading-7 text-vextro-muted">
            A comparison needs two or three different
            VEXTRO products.
          </p>

          <Link
            className="mt-7 inline-flex min-h-11 items-center rounded-xl bg-vextro-primary px-5 text-sm font-black text-white transition hover:bg-vextro-primary-dark"
            to="/products"
          >
            Browse products
          </Link>
        </div>
      </section>
    );
  }

  if (isLoading) {
    return (
      <section className="min-h-[calc(100vh-120px)] bg-vextro-canvas px-4 py-16">
        <div className="mx-auto max-w-7xl">
          <div className="h-10 w-72 animate-pulse rounded-xl bg-slate-200" />

          <div className="mt-8 grid gap-5 md:grid-cols-2">
            {productIds.map((productId) => (
              <div
                className="h-72 animate-pulse rounded-3xl border border-vextro-border bg-white"
                key={productId}
              />
            ))}
          </div>
        </div>
      </section>
    );
  }

  if (errorMessage || !comparison) {
    return (
      <section className="min-h-[calc(100vh-120px)] bg-vextro-canvas px-4 py-16">
        <div className="mx-auto max-w-3xl rounded-3xl border border-red-200 bg-white p-8 text-center shadow-sm">
          <h1 className="text-3xl font-black text-vextro-ink">
            Comparison could not be loaded
          </h1>

          <p className="mt-4 text-sm leading-7 text-red-700">
            {errorMessage ||
              "Comparison data is unavailable."}
          </p>

          <Link
            className="mt-7 inline-flex min-h-11 items-center rounded-xl bg-vextro-primary px-5 text-sm font-black text-white"
            to="/products"
          >
            Return to products
          </Link>
        </div>
      </section>
    );
  }

  const summary = comparison.summary || {};

  return (
    <section className="min-h-screen bg-vextro-canvas px-4 py-10 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-7xl">
        <div className="flex flex-col justify-between gap-6 lg:flex-row lg:items-end">
          <div>
            <span className="text-xs font-black uppercase tracking-[0.18em] text-vextro-primary">
              Product Comparison
            </span>

            <h1 className="mt-3 text-4xl font-black tracking-[-0.04em] text-vextro-ink sm:text-5xl">
              Compare before you buy
            </h1>

            <p className="mt-4 max-w-2xl text-sm leading-7 text-vextro-muted">
              Compare specifications, current marketplace
              offers and historical price intelligence in
              one place.
            </p>
          </div>

          <Link
            className="inline-flex min-h-11 items-center justify-center rounded-xl border border-vextro-border bg-white px-5 text-sm font-black text-vextro-ink transition hover:border-blue-200 hover:text-vextro-primary"
            to="/products"
          >
            Change products
          </Link>
        </div>

        <div className="mt-8 grid gap-4 md:grid-cols-3">
          <div className="rounded-2xl border border-vextro-border bg-white p-5">
            <span className="text-xs font-bold text-vextro-muted">
              Cheapest option
            </span>

            <strong className="mt-2 block text-lg font-black text-vextro-ink">
              {summary.cheapest_product_name || "No offer"}
            </strong>
          </div>

          <div className="rounded-2xl border border-vextro-border bg-white p-5">
            <span className="text-xs font-bold text-vextro-muted">
              Lowest current price
            </span>

            <strong className="mt-2 block text-2xl font-black text-vextro-primary">
              {formatCurrency(
                summary.lowest_current_price,
                summary.currency,
              )}
            </strong>
          </div>

          <div className="rounded-2xl border border-vextro-border bg-white p-5">
            <span className="text-xs font-bold text-vextro-muted">
              Price difference
            </span>

            <strong className="mt-2 block text-2xl font-black text-vextro-ink">
              {formatCurrency(
                summary.price_gap,
                summary.currency,
              )}
            </strong>

            {summary.price_gap_percentage !== null &&
            summary.price_gap_percentage !== undefined ? (
              <small className="mt-1 block font-bold text-vextro-muted">
                {summary.price_gap_percentage}% difference
              </small>
            ) : null}
          </div>
        </div>

        <div
          className={`mt-8 grid gap-5 ${
            items.length === 3
              ? "lg:grid-cols-3"
              : "md:grid-cols-2"
          }`}
        >
          {items.map((item) => {
            const lowestListing =
              getLowestListing(item);

            const primaryVariant =
              item.product.variants?.[0];

            const isCheapest =
              item.product.id ===
              summary.cheapest_product_id;

            return (
              <article
                className="relative overflow-hidden rounded-3xl border border-vextro-border bg-white shadow-sm"
                key={item.product.id}
              >
                {isCheapest ? (
                  <span className="absolute right-4 top-4 rounded-full bg-emerald-50 px-3 py-1.5 text-[10px] font-black uppercase tracking-wide text-emerald-700">
                    Lowest price
                  </span>
                ) : null}

                <div className="p-6">
                  <small className="font-bold uppercase tracking-wide text-vextro-muted">
                    {item.product.model ||
                      "Canonical product"}
                  </small>

                  <h2 className="mt-3 pr-20 text-2xl font-black leading-tight text-vextro-ink">
                    {item.product.name}
                  </h2>

                  {primaryVariant ? (
                    <div className="mt-4 flex flex-wrap gap-2">
                      {primaryVariant.ram_gb ? (
                        <span className="rounded-lg bg-vextro-canvas px-3 py-2 text-xs font-bold">
                          {primaryVariant.ram_gb} GB RAM
                        </span>
                      ) : null}

                      {primaryVariant.storage_gb ? (
                        <span className="rounded-lg bg-vextro-canvas px-3 py-2 text-xs font-bold">
                          {primaryVariant.storage_gb} GB Storage
                        </span>
                      ) : null}

                      {primaryVariant.color ? (
                        <span className="rounded-lg bg-vextro-canvas px-3 py-2 text-xs font-bold">
                          {primaryVariant.color}
                        </span>
                      ) : null}
                    </div>
                  ) : null}

                  <div className="mt-6 border-t border-vextro-border pt-5">
                    <span className="text-xs font-bold text-vextro-muted">
                      Best available offer
                    </span>

                    <strong className="mt-2 block text-3xl font-black text-vextro-primary">
                      {lowestListing
                        ? formatCurrency(
                            lowestListing.current_price,
                            lowestListing.currency,
                          )
                        : "No offer"}
                    </strong>
                  </div>

                  <Link
                    className="mt-6 inline-flex text-sm font-black text-vextro-primary"
                    to={`/products/${item.product.id}`}
                  >
                    View full product intelligence →
                  </Link>
                </div>
              </article>
            );
          })}
        </div>

        <div className="mt-8 overflow-hidden rounded-3xl border border-vextro-border bg-white shadow-sm">
          <div className="border-b border-vextro-border p-6">
            <h2 className="text-2xl font-black text-vextro-ink">
              Specification comparison
            </h2>

            <p className="mt-2 text-sm text-vextro-muted">
              Differences are shown directly from the
              normalized VEXTRO catalog.
            </p>
          </div>

          <div className="overflow-x-auto">
            <table className="min-w-full border-collapse text-left">
              <thead>
                <tr className="bg-vextro-canvas">
                  <th className="min-w-44 px-5 py-4 text-xs font-black uppercase tracking-wide text-vextro-muted">
                    Specification
                  </th>

                  {items.map((item) => (
                    <th
                      className="min-w-56 px-5 py-4 text-sm font-black text-vextro-ink"
                      key={item.product.id}
                    >
                      {item.product.name}
                    </th>
                  ))}
                </tr>
              </thead>

              <tbody>
                {specificationKeys.map((key) => (
                  <tr
                    className="border-t border-vextro-border"
                    key={key}
                  >
                    <th className="px-5 py-4 text-sm font-black capitalize text-vextro-muted">
                      {key.replaceAll("_", " ")}
                    </th>

                    {items.map((item) => (
                      <td
                        className="px-5 py-4 text-sm font-bold text-vextro-ink"
                        key={item.product.id}
                      >
                        {formatSpecificationValue(
                          item.product.specifications?.[
                            key
                          ],
                        )}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="mt-8">
          <h2 className="text-2xl font-black text-vextro-ink">
            Marketplace offers
          </h2>

          <div
            className={`mt-5 grid gap-5 ${
              items.length === 3
                ? "lg:grid-cols-3"
                : "md:grid-cols-2"
            }`}
          >
            {items.map((item) => (
              <div
                className="rounded-3xl border border-vextro-border bg-white p-6"
                key={item.product.id}
              >
                <h3 className="text-lg font-black text-vextro-ink">
                  {item.product.name}
                </h3>

                <div className="mt-5 grid gap-3">
                  {item.listings.items.length > 0 ? (
                    item.listings.items.map((listing) => (
                      <a
                        className="rounded-2xl border border-vextro-border p-4 transition hover:border-blue-200 hover:bg-blue-50/40"
                        href={listing.product_url}
                        key={listing.id}
                        rel="noreferrer"
                        target="_blank"
                      >
                        <div className="flex items-start justify-between gap-4">
                          <div>
                            <strong className="block text-sm font-black text-vextro-ink">
                              {getPlatformName(
                                item,
                                listing.platform_id,
                              )}
                            </strong>

                            <span className="mt-1 block text-xs text-vextro-muted">
                              {listing.seller?.name ||
                                listing.title}
                            </span>
                          </div>

                          <strong className="shrink-0 text-sm font-black text-vextro-primary">
                            {formatCurrency(
                              listing.current_price,
                              listing.currency,
                            )}
                          </strong>
                        </div>

                        <div className="mt-3 flex flex-wrap gap-2 text-[10px] font-bold text-vextro-muted">
                          {listing.rating ? (
                            <span>
                              ★ {listing.rating}
                            </span>
                          ) : null}

                          {listing.warranty ? (
                            <span>
                              {listing.warranty}
                            </span>
                          ) : null}
                        </div>
                      </a>
                    ))
                  ) : (
                    <p className="text-sm text-vextro-muted">
                      No active marketplace offers found.
                    </p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}


export default ComparisonPage;