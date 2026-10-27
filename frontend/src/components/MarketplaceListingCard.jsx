import {
  formatDate,
  formatPrice,
  formatWarranty,
  toFiniteNumber,
} from "../utils/productDisplay";
import { getMarketplaceDestination } from "../utils/marketplaceDestination";
import {
  formatCapacity,
  variantIdentityDetails,
} from "../utils/variantIdentity";

const TRUST_STYLES = {
  high: "border-emerald-200 bg-emerald-50 text-emerald-700",
  moderate: "border-amber-200 bg-amber-50 text-amber-700",
  low: "border-red-200 bg-red-50 text-red-700",
};

const TRUST_LABELS = { high: "High", moderate: "Moderate", low: "Low" };

// A trust score exists only when VEXTRO has analysed enough of the seller's
// reviews; otherwise the reason it is missing is shown on hover.
function SellerTrustBadge({ trust }) {
  if (!trust) {
    return null;
  }

  if (trust.status !== "available" || trust.trust_score === null) {
    const reason =
      trust.reasons?.[0] || "Not enough analysed reviews for this seller yet.";
    // The API also says when a score exists but is out of date, or was
    // never calculated; that is not the same as too little evidence.
    const notCalculated = /recalculate|has not been run/i.test(reason);

    return (
      <span
        className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-0.5 text-[10px] font-bold text-slate-500"
        title={reason}
      >
        Seller trust:{" "}
        {notCalculated ? "not calculated yet" : "not enough evidence"}
      </span>
    );
  }

  return (
    <span
      className={`rounded-full border px-2.5 py-0.5 text-[10px] font-black ${
        TRUST_STYLES[trust.trust_level] ?? TRUST_STYLES.moderate
      }`}
      title={[
        `${trust.analyzed_reviews} of ${trust.total_reviews} reviews analysed`,
        `confidence ${trust.confidence_level}`,
        ...(trust.reasons ?? []).slice(0, 2),
      ].join(" · ")}
    >
      Seller trust: {TRUST_LABELS[trust.trust_level] ?? trust.trust_level} ·{" "}
      {trust.trust_score}/100
    </span>
  );
}

function MarketplaceListingCard({
  listing,
  productName,
  platformName,
  sellerTrust = null,
  isLowest,
}) {
  const currentPrice = toFiniteNumber(
    listing.current_price,
  );

  const originalPrice = toFiniteNumber(
    listing.original_price,
  );

  const rating = toFiniteNumber(listing.rating);

  const discountPercentage =
    currentPrice !== null &&
    originalPrice !== null &&
    originalPrice > currentPrice
      ? Math.round(
          ((originalPrice - currentPrice) /
            originalPrice) *
            100,
        )
      : null;

  // A marketplace that sells the phone itself (PriceOye, Shophive) names
  // no separate seller; the marketplace is the seller.
  const sellerName =
    listing.seller?.name || platformName || "Marketplace seller";

  const imageUrl =
    listing.images?.find(
      (image) => image.is_primary,
    )?.image_url ||
    listing.images?.[0]?.image_url ||
    "";

  const marketplaceDestination =
    getMarketplaceDestination(listing, platformName);

  const isUnavailable = !listing.is_available;

  const variant = listing.product_variant;

  const offerDetails = [
    {
      label: "Colour",
      value: variant?.color || "",
      missing: "Not stated by seller",
    },
    {
      label: "Storage",
      value: variant?.storage_gb
        ? formatCapacity(variant.storage_gb)
        : "",
      missing: "Not stated",
    },
    {
      label: "RAM",
      value: variant?.ram_gb ? `${variant.ram_gb}GB` : "",
      missing: "Not stated",
    },
    // A tablet's screen and Wi-Fi or cellular model, a watch's case size:
    // shown only where the category has them.
    ...variantIdentityDetails(variant)
      .filter(({ key }) => key !== "ram_gb" && key !== "storage_gb")
      .map(({ label, value }) => ({ label, value, missing: "" })),
  ];

  return (
    <article
      className={`relative overflow-hidden rounded-3xl border bg-white transition duration-300 ${
        isUnavailable
          ? "border-red-200 opacity-75 saturate-50"
          : isLowest
            ? "border-2 border-emerald-300 shadow-lg shadow-emerald-500/10"
            : "border-vextro-border shadow-sm hover:border-blue-200 hover:shadow-lg"
      }`}
    >
      {isLowest && !isUnavailable ? (
        <span className="absolute right-4 top-4 z-10 rounded-full bg-emerald-500 px-3 py-1.5 text-[10px] font-black uppercase tracking-wide text-white shadow-lg shadow-emerald-500/20">
          Lowest price
        </span>
      ) : null}
      {isUnavailable ? (
        <span className="absolute right-4 top-4 z-10 rounded-full bg-red-500 px-3 py-1.5 text-[10px] font-black uppercase tracking-wide text-white shadow-lg shadow-red-500/20">
          Out of stock
        </span>
      ) : null}

      <div className="grid sm:grid-cols-[150px_1fr]">
        <div className="grid min-h-44 place-items-center bg-gradient-to-br from-slate-50 to-blue-50/60 p-5">
          {imageUrl ? (
            <img
              className="h-32 w-full object-contain"
              src={imageUrl}
              alt={listing.title}
              loading="lazy"
            />
          ) : (
            <div className="grid size-20 place-items-center rounded-3xl bg-white text-3xl shadow-sm">
              🛍️
            </div>
          )}
        </div>

        <div className="p-5 sm:p-6">
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full bg-blue-50 px-3 py-1.5 text-[10px] font-black uppercase tracking-[0.12em] text-vextro-primary">
              {platformName}
            </span>

            <span
              className={`rounded-full px-3 py-1.5 text-[10px] font-black ${
                listing.is_available
                  ? "bg-emerald-50 text-emerald-700"
                  : "bg-red-50 text-red-700"
              }`}
            >
              {listing.is_available
                ? "In stock"
                : "Unavailable"}
            </span>

            {discountPercentage ? (
              <span className="rounded-full bg-amber-50 px-3 py-1.5 text-[10px] font-black text-amber-700">
                {discountPercentage}% off
              </span>
            ) : null}
          </div>

          {/* The phone's own name. A seller's title repeats the memory and
              selling points that are shown as separate details below; it
              stays available on hover for anyone who wants the original. */}
          <h3
            className="mt-4 line-clamp-2 text-lg font-black leading-6 text-vextro-ink"
            title={listing.title}
          >
            {productName || listing.title}
          </h3>

          {/* Which option this price is for. Two offers of one phone differ
              by colour and memory, and the title alone often says neither. */}
          <dl className="mt-3 flex flex-wrap gap-2">
            {offerDetails.map((detail) => (
              <div
                key={detail.label}
                className={`flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs ${
                  detail.value
                    ? "border-vextro-border bg-slate-50"
                    : "border-dashed border-vextro-border bg-white"
                }`}
              >
                <dt className="font-semibold text-vextro-muted">
                  {detail.label}
                </dt>
                <dd
                  className={
                    detail.value
                      ? "font-black text-vextro-ink"
                      : "font-semibold text-vextro-muted"
                  }
                >
                  {detail.value || detail.missing}
                </dd>
              </div>
            ))}
          </dl>

          <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-vextro-muted">
            <span>
              Seller:{" "}
              <strong className="text-vextro-ink">
                {sellerName}
              </strong>
            </span>

            {listing.seller?.is_verified ? (
              <span className="font-bold text-emerald-600">
                ✓ Verified seller
              </span>
            ) : null}

            <SellerTrustBadge trust={sellerTrust} />

            {/* Stars run from 1 to 5, so a zero means nobody has rated
                the offer yet, not that it was rated badly. */}
            {rating !== null && rating > 0 ? (
              <span>
                <strong className="text-amber-500">
                  ★
                </strong>{" "}
                {rating.toFixed(1)} (
                {listing.review_count || 0} reviews)
              </span>
            ) : null}
          </div>

          <div className="mt-6 flex flex-col justify-between gap-5 border-t border-vextro-border pt-5 sm:flex-row sm:items-end">
            <div>
              <span className="text-[10px] font-black uppercase tracking-wide text-vextro-muted">
                Marketplace price
              </span>

              <div className="mt-1 flex flex-wrap items-center gap-3">
                <strong
                  className={`text-2xl font-black tracking-tight ${
                    isLowest
                      ? "text-emerald-700"
                      : "text-vextro-ink"
                  }`}
                >
                  {formatPrice(
                    listing.current_price,
                    listing.currency,
                  )}
                </strong>

                {originalPrice !== null &&
                originalPrice > currentPrice ? (
                  <del className="text-sm font-semibold text-vextro-muted">
                    {formatPrice(
                      originalPrice,
                      listing.currency,
                    )}
                  </del>
                ) : null}
              </div>

              <div className="mt-3 flex flex-wrap gap-x-5 gap-y-2 text-xs text-vextro-muted">
                <span>
                  Warranty:{" "}
                  <strong className="text-vextro-ink">
                    {formatWarranty(listing)}
                  </strong>
                </span>

                {/* Two different questions: when VEXTRO last confirmed this
                    offer exists, and when the stored row last changed. */}
                <span>
                  Last checked:{" "}
                  <strong className="text-vextro-ink">
                    {formatDate(listing.last_seen_at)}
                  </strong>
                </span>

                {listing.updated_at ? (
                  <span>
                    Updated:{" "}
                    <strong className="text-vextro-ink">
                      {formatDate(listing.updated_at)}
                    </strong>
                  </span>
                ) : null}
              </div>
            </div>

            <a
              className={`inline-flex min-h-11 shrink-0 items-center justify-center gap-2 rounded-xl px-5 text-sm font-black transition hover:-translate-y-0.5 ${
                isUnavailable
                  ? "border border-red-200 bg-white text-red-600 hover:border-red-300 hover:bg-red-50"
                  : "bg-vextro-primary text-white shadow-lg shadow-blue-500/20 hover:bg-vextro-primary-dark"
              }`}
              href={marketplaceDestination.url}
              target="_blank"
              rel="noreferrer"
            >
              {isUnavailable
                ? `See on ${platformName} (out of stock)`
                : marketplaceDestination.isSearchFallback
                  ? `Search on ${platformName}`
                  : `View on ${platformName}`}
              <span>↗</span>
            </a>
          </div>
        </div>
      </div>
    </article>
  );
}

export default MarketplaceListingCard;
