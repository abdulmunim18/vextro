function formatPrice(price, currency = "PKR") {
  const numericPrice = Number(price);

  if (!Number.isFinite(numericPrice)) {
    return "Price unavailable";
  }

  try {
    return new Intl.NumberFormat("en-PK", {
      style: "currency",
      currency,
      maximumFractionDigits: 0,
    }).format(numericPrice);
  } catch {
    return `${currency} ${numericPrice.toLocaleString("en-PK")}`;
  }
}

function formatDate(value) {
  if (!value) {
    return "Not available";
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "Not available";
  }

  return new Intl.DateTimeFormat("en-PK", {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(date);
}

function getSellerName(listing) {
  return (
    listing.seller?.name ||
    listing.seller?.display_name ||
    listing.seller?.business_name ||
    (listing.seller_id
      ? `Seller #${listing.seller_id}`
      : "Marketplace seller")
  );
}

function getPrimaryImage(listing) {
  const images = Array.isArray(listing.images)
    ? listing.images
    : [];

  const primaryImage =
    images.find((image) => image.is_primary) || images[0];

  return primaryImage?.image_url || "";
}

function getPlatformStyles(platformCode = "") {
  const normalizedCode = platformCode.toLowerCase();

  if (normalizedCode.includes("daraz")) {
    return {
      badge:
        "border-orange-200 bg-orange-50 text-orange-700",
      icon: "bg-orange-100 text-orange-700",
    };
  }

  if (normalizedCode.includes("priceoye")) {
    return {
      badge:
        "border-blue-200 bg-blue-50 text-blue-700",
      icon: "bg-blue-100 text-blue-700",
    };
  }

  return {
    badge:
      "border-slate-200 bg-slate-50 text-slate-700",
    icon: "bg-slate-100 text-slate-700",
  };
}

function MarketplaceListingCard({
  listing,
  platform,
  isLowestPrice = false,
}) {
  const currentPrice = Number(listing.current_price);
  const originalPrice = Number(listing.original_price);

  const hasDiscount =
    Number.isFinite(originalPrice) &&
    Number.isFinite(currentPrice) &&
    originalPrice > currentPrice;

  const discountPercentage = hasDiscount
    ? Math.round(
        ((originalPrice - currentPrice) / originalPrice) * 100,
      )
    : 0;

  const sellerName = getSellerName(listing);
  const imageUrl = getPrimaryImage(listing);

  const platformName =
    platform?.name ||
    `Marketplace #${listing.platform_id}`;

  const platformCode =
    platform?.code || platformName;

  const platformStyles =
    getPlatformStyles(platformCode);

  const rating = Number(listing.rating);

  return (
    <article
      className={`relative flex h-full flex-col overflow-hidden rounded-3xl bg-white p-6 shadow-sm transition duration-300 hover:-translate-y-1 hover:shadow-vextro ${
        isLowestPrice
          ? "border-2 border-emerald-300"
          : "border border-vextro-border"
      }`}
    >
      {isLowestPrice ? (
        <span className="absolute right-5 top-0 rounded-b-xl bg-emerald-500 px-4 py-2 text-[10px] font-black uppercase tracking-wider text-white shadow-lg shadow-emerald-500/20">
          Lowest Price
        </span>
      ) : null}

      <div className="flex items-start gap-4">
        <div
          className={`grid size-13 shrink-0 place-items-center rounded-2xl text-lg font-black ${platformStyles.icon}`}
        >
          {platformName.charAt(0).toUpperCase()}
        </div>

        <div className="min-w-0 flex-1">
          <span
            className={`inline-flex rounded-full border px-3 py-1 text-[10px] font-black uppercase tracking-wider ${platformStyles.badge}`}
          >
            {platformName}
          </span>

          <h3 className="mt-3 line-clamp-2 text-lg font-black leading-6 text-vextro-ink">
            {listing.title}
          </h3>

          <p className="mt-2 truncate text-xs font-semibold text-vextro-muted">
            {sellerName}
          </p>
        </div>
      </div>

      {imageUrl ? (
        <div className="mt-5 grid h-44 place-items-center rounded-2xl bg-vextro-canvas">
          <img
            className="h-full w-full p-5 object-contain"
            src={imageUrl}
            alt={listing.title}
            loading="lazy"
          />
        </div>
      ) : null}

      <div className="mt-6">
        <span className="text-[10px] font-black uppercase tracking-wide text-vextro-muted">
          Current marketplace price
        </span>

        <div className="mt-2 flex flex-wrap items-end gap-3">
          <strong
            className={`text-3xl font-black tracking-[-0.04em] ${
              isLowestPrice
                ? "text-emerald-700"
                : "text-vextro-ink"
            }`}
          >
            {formatPrice(
              listing.current_price,
              listing.currency,
            )}
          </strong>

          {hasDiscount ? (
            <>
              <span className="pb-1 text-sm font-semibold text-vextro-muted line-through">
                {formatPrice(
                  listing.original_price,
                  listing.currency,
                )}
              </span>

              <span className="mb-1 rounded-full bg-red-50 px-2.5 py-1 text-[10px] font-black text-red-600">
                {discountPercentage}% OFF
              </span>
            </>
          ) : null}
        </div>
      </div>

      <div className="mt-6 grid grid-cols-2 gap-3">
        <div className="rounded-2xl bg-vextro-canvas p-4">
          <span className="block text-[10px] font-bold uppercase text-vextro-muted">
            Rating
          </span>

          <strong className="mt-1 block text-sm font-black text-vextro-ink">
            {Number.isFinite(rating)
              ? `★ ${rating.toFixed(1)}`
              : "Not rated"}
          </strong>

          <small className="mt-1 block text-[10px] text-vextro-muted">
            {listing.review_count || 0} reviews
          </small>
        </div>

        <div className="rounded-2xl bg-vextro-canvas p-4">
          <span className="block text-[10px] font-bold uppercase text-vextro-muted">
            Availability
          </span>

          <strong
            className={`mt-1 block text-sm font-black ${
              listing.is_available
                ? "text-emerald-700"
                : "text-red-600"
            }`}
          >
            {listing.is_available
              ? "In Stock"
              : "Unavailable"}
          </strong>

          <small className="mt-1 block text-[10px] text-vextro-muted">
            Updated {formatDate(listing.last_seen_at)}
          </small>
        </div>
      </div>

      <div className="mt-4 rounded-2xl border border-vextro-border p-4">
        <div className="flex items-center justify-between gap-4 text-xs">
          <span className="font-semibold text-vextro-muted">
            Warranty
          </span>

          <strong className="text-right font-black text-vextro-ink">
            {listing.warranty || "Not specified"}
          </strong>
        </div>
      </div>

      <a
        className={`mt-5 inline-flex min-h-12 items-center justify-center gap-2 rounded-xl px-5 text-sm font-black transition ${
          listing.is_available
            ? "bg-vextro-primary text-white shadow-lg shadow-blue-500/20 hover:-translate-y-0.5 hover:bg-vextro-primary-dark"
            : "pointer-events-none bg-slate-200 text-slate-500"
        }`}
        href={listing.product_url}
        target="_blank"
        rel="noreferrer"
        aria-disabled={!listing.is_available}
      >
        View on {platformName}
        <span>↗</span>
      </a>
    </article>
  );
}

export default MarketplaceListingCard;