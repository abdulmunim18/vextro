import {
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  getPlatforms,
  getProductListings,
} from "../services/catalogService";
import {
  createCompetitorWatchlistEntry,
  getBusinessProducts,
  getCompetitorWatchlist,
  updateCompetitorWatchlistStatus,
} from "../services/smeService";
import { getApiErrorMessage } from "../utils/apiError";
import { formatPrice } from "../utils/productDisplay";

function extractItems(responseData) {
  if (Array.isArray(responseData)) {
    return responseData;
  }

  if (Array.isArray(responseData?.items)) {
    return responseData.items;
  }

  return [];
}

function getListingSellerName(listing) {
  return (
    listing?.seller?.name ||
    "Marketplace seller"
  );
}

function getPriceGapText(
  businessProduct,
  listing,
) {
  const ownPrice = Number(
    businessProduct?.selling_price,
  );

  const competitorPrice = Number(
    listing?.current_price,
  );

  if (
    !Number.isFinite(ownPrice) ||
    !Number.isFinite(competitorPrice)
  ) {
    return null;
  }

  const difference = ownPrice - competitorPrice;

  if (difference === 0) {
    return "Your price matches this competitor.";
  }

  const formattedDifference = formatPrice(
    Math.abs(difference),
    businessProduct.currency ||
      listing.currency ||
      "PKR",
  );

  if (difference > 0) {
    return `Your price is ${formattedDifference} higher.`;
  }

  return `Your price is ${formattedDifference} lower.`;
}

function CompetitorCard({
  entry,
  businessProduct,
  listing,
  platformName,
  isUpdating,
  onToggleStatus,
}) {
  const priceGapText = getPriceGapText(
    businessProduct,
    listing,
  );

  return (
    <article className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm transition hover:-translate-y-1 hover:border-violet-200 hover:shadow-lg">
      <div className="flex flex-col justify-between gap-5 lg:flex-row lg:items-start">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={[
                "rounded-full px-3 py-1 text-[10px] font-black uppercase",
                entry.is_active
                  ? "bg-emerald-100 text-emerald-700"
                  : "bg-slate-200 text-slate-600",
              ].join(" ")}
            >
              {entry.is_active
                ? "Monitoring active"
                : "Monitoring paused"}
            </span>

            {listing ? (
              <span
                className={[
                  "rounded-full px-3 py-1 text-[10px] font-black uppercase",
                  listing.is_available
                    ? "bg-blue-100 text-blue-700"
                    : "bg-red-100 text-red-700",
                ].join(" ")}
              >
                {listing.is_available
                  ? "In stock"
                  : "Unavailable"}
              </span>
            ) : null}

            <span className="rounded-full bg-violet-100 px-3 py-1 text-[10px] font-black uppercase text-violet-700">
              {platformName}
            </span>
          </div>

          <p className="mt-5 text-xs font-black uppercase tracking-[0.14em] text-slate-400">
            Your business product
          </p>

          <h3 className="mt-2 text-xl font-black tracking-tight text-slate-950">
            {businessProduct?.name ||
              `Business product #${entry.business_product_id}`}
          </h3>

          <p className="mt-2 text-sm font-semibold text-slate-500">
            SKU:{" "}
            {businessProduct?.sku ||
              "Not assigned"}
          </p>
        </div>

        <button
          type="button"
          disabled={isUpdating}
          onClick={onToggleStatus}
          className={[
            "inline-flex min-h-11 shrink-0 items-center justify-center rounded-xl border px-5 text-xs font-black transition disabled:cursor-not-allowed disabled:opacity-60",
            entry.is_active
              ? "border-red-200 bg-red-50 text-red-700 hover:bg-red-100"
              : "border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-100",
          ].join(" ")}
        >
          {isUpdating
            ? "Updating..."
            : entry.is_active
              ? "Pause monitoring"
              : "Resume monitoring"}
        </button>
      </div>

      <div className="mt-6 rounded-2xl border border-slate-200 bg-slate-50 p-5">
        <div className="flex flex-col justify-between gap-5 sm:flex-row sm:items-start">
          <div className="min-w-0">
            <p className="text-xs font-black uppercase tracking-[0.14em] text-violet-600">
              Competitor listing
            </p>

            <h4 className="mt-2 line-clamp-2 text-base font-black leading-6 text-slate-900">
              {listing?.title ||
                `Marketplace listing #${entry.listing_id}`}
            </h4>

            <p className="mt-2 text-xs font-semibold text-slate-500">
              Seller:{" "}
              <strong className="text-slate-700">
                {getListingSellerName(listing)}
              </strong>
            </p>
          </div>

          <div className="shrink-0 sm:text-right">
            <p className="text-[10px] font-black uppercase tracking-wide text-slate-400">
              Competitor price
            </p>

            <p className="mt-2 text-xl font-black text-violet-700">
              {listing
                ? formatPrice(
                    listing.current_price,
                    listing.currency,
                  )
                : "Price unavailable"}
            </p>
          </div>
        </div>

        <div className="mt-5 grid gap-3 sm:grid-cols-2">
          <div className="rounded-xl bg-white p-4">
            <p className="text-[10px] font-black uppercase tracking-wide text-slate-400">
              Your selling price
            </p>

            <p className="mt-2 text-sm font-black text-slate-900">
              {formatPrice(
                businessProduct?.selling_price,
                businessProduct?.currency ||
                  "PKR",
              )}
            </p>
          </div>

          <div className="rounded-xl bg-white p-4">
            <p className="text-[10px] font-black uppercase tracking-wide text-slate-400">
              Price comparison
            </p>

            <p
              className={[
                "mt-2 text-sm font-black",
                priceGapText?.includes("higher")
                  ? "text-red-700"
                  : "text-emerald-700",
              ].join(" ")}
            >
              {priceGapText ||
                "Add both prices to calculate the gap."}
            </p>
          </div>
        </div>

        {listing?.product_url ? (
          <a
            className="mt-5 inline-flex min-h-11 items-center justify-center rounded-xl bg-slate-950 px-5 text-xs font-black text-white transition hover:bg-slate-800"
            href={listing.product_url}
            target="_blank"
            rel="noreferrer"
          >
            View marketplace listing ↗
          </a>
        ) : null}
      </div>
    </article>
  );
}

function SMECompetitorWatchlist({
  organizationId,
  organizationName,
}) {
  const [businessProducts, setBusinessProducts] =
    useState([]);

  const [watchlistEntries, setWatchlistEntries] =
    useState([]);

  const [
    listingsByCanonicalProduct,
    setListingsByCanonicalProduct,
  ] = useState({});

  const [listingDetails, setListingDetails] =
    useState({});

  const [platformNames, setPlatformNames] =
    useState({});

  const [
    selectedBusinessProductId,
    setSelectedBusinessProductId,
  ] = useState("");

  const [selectedListingId, setSelectedListingId] =
    useState("");

  const [isLoading, setIsLoading] =
    useState(true);

  const [isCreating, setIsCreating] =
    useState(false);

  const [updatingEntryId, setUpdatingEntryId] =
    useState(null);

  const [loadError, setLoadError] =
    useState("");

  const [formError, setFormError] =
    useState("");

  const [actionError, setActionError] =
    useState("");

  const [successMessage, setSuccessMessage] =
    useState("");

  const loadWatchlistWorkspace =
    useCallback(async () => {
      if (!organizationId) {
        setBusinessProducts([]);
        setWatchlistEntries([]);
        setIsLoading(false);
        return;
      }

      setIsLoading(true);
      setLoadError("");
      setActionError("");

      try {
        const [
          productsResponse,
          watchlistResponse,
          platformsResponse,
        ] = await Promise.all([
          getBusinessProducts(
            organizationId,
            {
              page: 1,
              page_size: 100,
            },
          ),
          getCompetitorWatchlist(
            organizationId,
          ),
          getPlatforms(),
        ]);

        const loadedProducts =
          extractItems(productsResponse);

        const loadedEntries =
          extractItems(watchlistResponse);

        const loadedPlatforms =
          extractItems(platformsResponse);

        setBusinessProducts(loadedProducts);
        setWatchlistEntries(loadedEntries);

        setSelectedBusinessProductId(
          (currentId) => {
            const currentProductExists =
              loadedProducts.some(
                (product) =>
                  String(product.id) ===
                  String(currentId),
              );

            if (currentProductExists) {
              return currentId;
            }

            return loadedProducts[0]?.id
              ? String(loadedProducts[0].id)
              : "";
          },
        );

        setPlatformNames(
          Object.fromEntries(
            loadedPlatforms.map(
              (platform) => [
                platform.id,
                platform.name,
              ],
            ),
          ),
        );

        const canonicalProductIds = [
          ...new Set(
            loadedProducts
              .map(
                (product) =>
                  product.canonical_product_id,
              )
              .filter(Boolean),
          ),
        ];

        const listingResults =
          await Promise.allSettled(
            canonicalProductIds.map(
              async (canonicalProductId) => {
                const response =
                  await getProductListings(
                    canonicalProductId,
                  );

                return {
                  canonicalProductId,
                  listings:
                    extractItems(response),
                };
              },
            ),
          );

        const nextListingsByProduct = {};
        const nextListingDetails = {};

        listingResults.forEach((result) => {
          if (result.status !== "fulfilled") {
            return;
          }

          const {
            canonicalProductId,
            listings,
          } = result.value;

          nextListingsByProduct[
            canonicalProductId
          ] = listings;

          listings.forEach((listing) => {
            nextListingDetails[listing.id] =
              listing;
          });
        });

        setListingsByCanonicalProduct(
          nextListingsByProduct,
        );

        setListingDetails(
          nextListingDetails,
        );
      } catch (error) {
        setLoadError(
          getApiErrorMessage(
            error,
            "Competitor workspace could not be loaded.",
          ),
        );
      } finally {
        setIsLoading(false);
      }
    }, [organizationId]);

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      setSelectedListingId("");
      setSuccessMessage("");
      loadWatchlistWorkspace();
    }, 0);

    return () => window.clearTimeout(timeoutId);
  }, [loadWatchlistWorkspace]);

  const businessProductMap = useMemo(
    () =>
      new Map(
        businessProducts.map((product) => [
          product.id,
          product,
        ]),
      ),
    [businessProducts],
  );

  const selectedBusinessProduct =
    useMemo(
      () =>
        businessProducts.find(
          (product) =>
            String(product.id) ===
            String(
              selectedBusinessProductId,
            ),
        ) || null,
      [
        businessProducts,
        selectedBusinessProductId,
      ],
    );

  const selectedProductListings =
    useMemo(() => {
      const canonicalProductId =
        selectedBusinessProduct
          ?.canonical_product_id;

      if (!canonicalProductId) {
        return [];
      }

      return (
        listingsByCanonicalProduct[
          canonicalProductId
        ] || []
      );
    }, [
      listingsByCanonicalProduct,
      selectedBusinessProduct,
    ]);

  const alreadyWatchedListingIds =
    useMemo(
      () =>
        new Set(
          watchlistEntries
            .filter(
              (entry) =>
                String(
                  entry.business_product_id,
                ) ===
                String(
                  selectedBusinessProductId,
                ),
            )
            .map((entry) => entry.listing_id),
        ),
      [
        selectedBusinessProductId,
        watchlistEntries,
      ],
    );

  const availableListings = useMemo(
    () =>
      selectedProductListings.filter(
        (listing) =>
          !alreadyWatchedListingIds.has(
            listing.id,
          ),
      ),
    [
      alreadyWatchedListingIds,
      selectedProductListings,
    ],
  );

  const statistics = useMemo(() => {
    const activeEntries =
      watchlistEntries.filter(
        (entry) => entry.is_active,
      ).length;

    const monitoredProducts = new Set(
      watchlistEntries.map(
        (entry) =>
          entry.business_product_id,
      ),
    ).size;

    const availableCompetitors =
      watchlistEntries.filter(
        (entry) =>
          listingDetails[entry.listing_id]
            ?.is_available,
      ).length;

    return {
      activeEntries,
      monitoredProducts,
      availableCompetitors,
    };
  }, [listingDetails, watchlistEntries]);

  function handleBusinessProductChange(
    event,
  ) {
    setSelectedBusinessProductId(
      event.target.value,
    );

    setSelectedListingId("");
    setFormError("");
    setSuccessMessage("");
  }

  async function handleCreateEntry(event) {
    event.preventDefault();

    if (!selectedBusinessProductId) {
      setFormError(
        "Select a business product.",
      );
      return;
    }

    if (!selectedListingId) {
      setFormError(
        "Select a marketplace competitor listing.",
      );
      return;
    }

    setIsCreating(true);
    setFormError("");
    setSuccessMessage("");

    try {
      const createdEntry =
        await createCompetitorWatchlistEntry(
          organizationId,
          {
            business_product_id: Number(
              selectedBusinessProductId,
            ),
            listing_id: Number(
              selectedListingId,
            ),
          },
        );

      setWatchlistEntries(
        (currentEntries) => [
          createdEntry,
          ...currentEntries,
        ],
      );

      setSelectedListingId("");

      setSuccessMessage(
        "Competitor listing is now being monitored.",
      );
    } catch (error) {
      setFormError(
        getApiErrorMessage(
          error,
          "Competitor listing could not be added.",
        ),
      );
    } finally {
      setIsCreating(false);
    }
  }

  async function handleToggleStatus(entry) {
    setUpdatingEntryId(entry.id);
    setActionError("");
    setSuccessMessage("");

    try {
      const updatedEntry =
        await updateCompetitorWatchlistStatus(
          organizationId,
          entry.id,
          !entry.is_active,
        );

      setWatchlistEntries(
        (currentEntries) =>
          currentEntries.map(
            (currentEntry) =>
              currentEntry.id === entry.id
                ? updatedEntry
                : currentEntry,
          ),
      );
    } catch (error) {
      setActionError(
        getApiErrorMessage(
          error,
          "Competitor monitoring status could not be updated.",
        ),
      );
    } finally {
      setUpdatingEntryId(null);
    }
  }

  return (
    <section className="mt-8">
      <div className="rounded-3xl border border-slate-200 bg-slate-950 p-7 text-white shadow-xl sm:p-9">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-xs font-black uppercase tracking-[0.18em] text-violet-300">
              Market monitoring
            </p>

            <h2 className="mt-3 text-3xl font-black tracking-[-0.04em]">
              Competitor Watchlist
            </h2>

            <p className="mt-3 max-w-2xl text-sm leading-7 text-slate-300">
              Track Daraz and PriceOye listings
              against products managed by{" "}
              <strong className="text-white">
                {organizationName}
              </strong>
              .
            </p>
          </div>

          <button
            type="button"
            onClick={loadWatchlistWorkspace}
            disabled={isLoading}
            className="inline-flex min-h-11 items-center justify-center rounded-xl border border-white/15 bg-white/10 px-5 text-sm font-black text-white transition hover:bg-white/15 disabled:opacity-60"
          >
            {isLoading
              ? "Refreshing..."
              : "Refresh watchlist"}
          </button>
        </div>

        <div className="mt-7 grid grid-cols-2 gap-4 lg:grid-cols-4">
          <div className="rounded-2xl border border-white/10 bg-white/5 p-5">
            <p className="text-xs font-bold text-slate-400">
              Total competitors
            </p>

            <p className="mt-3 text-3xl font-black">
              {watchlistEntries.length}
            </p>
          </div>

          <div className="rounded-2xl border border-white/10 bg-white/5 p-5">
            <p className="text-xs font-bold text-slate-400">
              Active monitoring
            </p>

            <p className="mt-3 text-3xl font-black text-emerald-300">
              {statistics.activeEntries}
            </p>
          </div>

          <div className="rounded-2xl border border-white/10 bg-white/5 p-5">
            <p className="text-xs font-bold text-slate-400">
              Tracked products
            </p>

            <p className="mt-3 text-3xl font-black text-violet-300">
              {statistics.monitoredProducts}
            </p>
          </div>

          <div className="rounded-2xl border border-white/10 bg-white/5 p-5">
            <p className="text-xs font-bold text-slate-400">
              Available offers
            </p>

            <p className="mt-3 text-3xl font-black text-blue-300">
              {statistics.availableCompetitors}
            </p>
          </div>
        </div>
      </div>

      <section className="mt-6 rounded-3xl border border-slate-200 bg-white p-7 shadow-sm sm:p-9">
        <p className="text-xs font-black uppercase tracking-[0.18em] text-violet-600">
          Add competitor
        </p>

        <h3 className="mt-3 text-2xl font-black text-slate-950">
          Select a marketplace listing
        </h3>

        <form
          className="mt-7"
          onSubmit={handleCreateEntry}
        >
          <div className="grid gap-5 lg:grid-cols-2">
            <div>
              <label
                className="mb-2 block text-sm font-black text-slate-800"
                htmlFor="competitor-business-product"
              >
                Business product
              </label>

              <select
                id="competitor-business-product"
                value={
                  selectedBusinessProductId
                }
                onChange={
                  handleBusinessProductChange
                }
                disabled={
                  isLoading ||
                  businessProducts.length === 0
                }
                className="min-h-12 w-full rounded-xl border border-slate-300 bg-white px-4 text-sm font-semibold text-slate-900 outline-none transition focus:border-violet-500 focus:ring-4 focus:ring-violet-100 disabled:bg-slate-100"
              >
                {businessProducts.length === 0 ? (
                  <option value="">
                    No business products available
                  </option>
                ) : null}

                {businessProducts.map(
                  (product) => (
                    <option
                      key={product.id}
                      value={product.id}
                    >
                      {product.name}
                      {product.sku
                        ? ` — ${product.sku}`
                        : ""}
                    </option>
                  ),
                )}
              </select>
            </div>

            <div>
              <label
                className="mb-2 block text-sm font-black text-slate-800"
                htmlFor="competitor-listing"
              >
                Marketplace listing
              </label>

              <select
                id="competitor-listing"
                value={selectedListingId}
                onChange={(event) => {
                  setSelectedListingId(
                    event.target.value,
                  );
                  setFormError("");
                  setSuccessMessage("");
                }}
                disabled={
                  !selectedBusinessProduct
                    ?.canonical_product_id ||
                  availableListings.length === 0
                }
                className="min-h-12 w-full rounded-xl border border-slate-300 bg-white px-4 text-sm font-semibold text-slate-900 outline-none transition focus:border-violet-500 focus:ring-4 focus:ring-violet-100 disabled:bg-slate-100"
              >
                <option value="">
                  Select competitor listing
                </option>

                {availableListings.map(
                  (listing) => (
                    <option
                      key={listing.id}
                      value={listing.id}
                    >
                      {platformNames[
                        listing.platform_id
                      ] ||
                        `Platform ${listing.platform_id}`}
                      {" — "}
                      {listing.title}
                      {" — "}
                      {formatPrice(
                        listing.current_price,
                        listing.currency,
                      )}
                    </option>
                  ),
                )}
              </select>
            </div>
          </div>

          {selectedBusinessProduct &&
          !selectedBusinessProduct
            .canonical_product_id ? (
            <div className="mt-5 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm font-semibold leading-6 text-amber-800">
              Is business product ke saath
              Catalog Product ID connected nahi hai.
              Product ko edit karke valid catalog ID
              add karo.
            </div>
          ) : null}

          {selectedBusinessProduct
            ?.canonical_product_id &&
          selectedProductListings.length === 0 ? (
            <div className="mt-5 rounded-xl border border-blue-200 bg-blue-50 px-4 py-3 text-sm font-semibold leading-6 text-blue-800">
              Is catalog product ke liye abhi koi
              Daraz ya PriceOye listing available
              nahi hai.
            </div>
          ) : null}

          {selectedProductListings.length > 0 &&
          availableListings.length === 0 ? (
            <div className="mt-5 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-semibold leading-6 text-emerald-800">
              Is product ki tamam available
              listings already watchlist mein hain.
            </div>
          ) : null}

          {formError ? (
            <div
              className="mt-5 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-semibold text-red-700"
              role="alert"
            >
              {formError}
            </div>
          ) : null}

          {successMessage ? (
            <div
              className="mt-5 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-semibold text-emerald-700"
              role="status"
            >
              {successMessage}
            </div>
          ) : null}

          <button
            type="submit"
            disabled={
              isCreating ||
              !selectedBusinessProductId ||
              !selectedListingId
            }
            className="mt-6 inline-flex min-h-12 w-full items-center justify-center rounded-xl bg-violet-600 px-5 text-sm font-black text-white shadow-lg shadow-violet-600/20 transition hover:bg-violet-700 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isCreating
              ? "Adding competitor..."
              : "Add to competitor watchlist"}
          </button>
        </form>
      </section>

      <section className="mt-6">
        <p className="text-xs font-black uppercase tracking-[0.18em] text-violet-600">
          Monitored listings
        </p>

        <h3 className="mt-2 text-3xl font-black text-slate-950">
          Your competitor intelligence
        </h3>

        {actionError ? (
          <div
            className="mt-5 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-semibold text-red-700"
            role="alert"
          >
            {actionError}
          </div>
        ) : null}

        {isLoading ? (
          <div className="mt-6 grid gap-5">
            {[1, 2].map((item) => (
              <div
                key={item}
                className="h-72 animate-pulse rounded-3xl border border-slate-200 bg-white"
              />
            ))}
          </div>
        ) : null}

        {!isLoading && loadError ? (
          <div className="mt-6 rounded-3xl border border-red-200 bg-white p-8 text-center">
            <h4 className="text-xl font-black text-slate-950">
              Watchlist could not be loaded
            </h4>

            <p className="mt-3 text-sm text-red-700">
              {loadError}
            </p>

            <button
              type="button"
              onClick={loadWatchlistWorkspace}
              className="mt-5 rounded-xl bg-slate-950 px-5 py-3 text-sm font-black text-white"
            >
              Try again
            </button>
          </div>
        ) : null}

        {!isLoading &&
        !loadError &&
        watchlistEntries.length === 0 ? (
          <div className="mt-6 rounded-3xl border border-dashed border-slate-300 bg-white p-10 text-center">
            <h4 className="text-xl font-black text-slate-950">
              No competitors monitored yet
            </h4>

            <p className="mt-3 text-sm leading-7 text-slate-600">
              Upar se business product aur
              marketplace listing select karke apna
              pehla competitor add karo.
            </p>
          </div>
        ) : null}

        {!isLoading &&
        !loadError &&
        watchlistEntries.length > 0 ? (
          <div className="mt-6 grid gap-5">
            {watchlistEntries.map((entry) => {
              const listing =
                listingDetails[
                  entry.listing_id
                ];

              const businessProduct =
                businessProductMap.get(
                  entry.business_product_id,
                );

              const platformName =
                platformNames[
                  listing?.platform_id
                ] ||
                (listing
                  ? `Platform ${listing.platform_id}`
                  : "Marketplace");

              return (
                <CompetitorCard
                  key={entry.id}
                  entry={entry}
                  businessProduct={
                    businessProduct
                  }
                  listing={listing}
                  platformName={platformName}
                  isUpdating={
                    updatingEntryId ===
                    entry.id
                  }
                  onToggleStatus={() =>
                    handleToggleStatus(entry)
                  }
                />
              );
            })}
          </div>
        ) : null}
      </section>
    </section>
  );
}

export default SMECompetitorWatchlist;
