import {
  formatDate,
  formatPrice,
  toFiniteNumber,
} from "../utils/productDisplay";

function MarketplaceListingCard({
  listing,
  platformName,
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

  const sellerName =
    listing.seller?.name || "Marketplace seller";

  const imageUrl =
    listing.images?.find(
      (image) => image.is_primary,
    )?.image_url ||
    listing.images?.[0]?.image_url ||
    "";

  return (
    <article
      className={`relative overflow-hidden rounded-3xl border bg-white transition duration-300 ${
        isLowest
          ? "border-2 border-emerald-300 shadow-lg shadow-emerald-500/10"
          : "border-vextro-border shadow-sm hover:border-blue-200 hover:shadow-lg"
      }`}
    >
      {isLowest ? (
        <span className="absolute right-4 top-4 z-10 rounded-full bg-emerald-500 px-3 py-1.5 text-[10px] font-black uppercase tracking-wide text-white shadow-lg shadow-emerald-500/20">
          Lowest price
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

          <h3 className="mt-4 line-clamp-2 text-lg font-black leading-6 text-vextro-ink">
            {listing.title}
          </h3>

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

            {rating !== null ? (
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
                    {listing.warranty || "Not listed"}
                  </strong>
                </span>

                <span>
                  Updated:{" "}
                  <strong className="text-vextro-ink">
                    {formatDate(listing.last_seen_at)}
                  </strong>
                </span>
              </div>
            </div>

            <a
              className={`inline-flex min-h-11 shrink-0 items-center justify-center gap-2 rounded-xl px-5 text-sm font-black transition ${
                listing.is_available
                  ? "bg-vextro-primary text-white shadow-lg shadow-blue-500/20 hover:-translate-y-0.5 hover:bg-vextro-primary-dark"
                  : "pointer-events-none bg-slate-100 text-slate-400"
              }`}
              href={listing.product_url}
              target="_blank"
              rel="noreferrer"
              aria-disabled={!listing.is_available}
            >
              Visit {platformName}
              <span>↗</span>
            </a>
          </div>
        </div>
      </div>
    </article>
  );
}

export default MarketplaceListingCard;