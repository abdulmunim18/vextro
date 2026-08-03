import { useState } from "react";
import { Link } from "react-router-dom";

function getRelatedName(value, fallback) {
  if (typeof value === "string" && value.trim()) {
    return value;
  }

  if (
    value &&
    typeof value === "object" &&
    typeof value.name === "string"
  ) {
    return value.name;
  }

  return fallback;
}

function getProductName(product) {
  return (
    product.name ||
    product.title ||
    product.product_name ||
    "Unnamed product"
  );
}

function getProductImage(product) {
  const firstImage = product.images?.[0];

  return (
    product.image_url ||
    product.primary_image_url ||
    firstImage?.url ||
    firstImage?.image_url ||
    ""
  );
}

function getLowestPrice(product) {
  return (
    product.lowest_price ??
    product.minimum_price ??
    product.min_price ??
    product.starting_price ??
    product.current_price ??
    null
  );
}

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
    return `${currency} ${numericPrice.toLocaleString(
      "en-PK",
    )}`;
  }
}

function ProductCard({ product }) {
  const [imageFailed, setImageFailed] = useState(false);

  const productName = getProductName(product);
  const imageUrl = getProductImage(product);
  const lowestPrice = getLowestPrice(product);

  const brandName = getRelatedName(
    product.brand ?? product.brand_name,
    "Unbranded",
  );

  const categoryName = getRelatedName(
    product.category ?? product.category_name,
    "General",
  );

  const marketplaceCount = Number(
    product.platform_count ??
      product.marketplace_count ??
      product.listing_count ??
      0,
  );

  const rating = Number(
    product.average_rating ?? product.rating,
  );

  return (
    <article className="group flex h-full flex-col overflow-hidden rounded-3xl border border-vextro-border bg-white shadow-sm transition duration-300 hover:-translate-y-1.5 hover:border-blue-200 hover:shadow-vextro">
      <Link
        className="relative grid h-64 place-items-center overflow-hidden bg-gradient-to-br from-slate-50 to-blue-50/60"
        to={`/products/${product.id}`}
        aria-label={`View ${productName}`}
      >
        {imageUrl && !imageFailed ? (
          <img
            className="h-full w-full p-7 object-contain transition duration-300 group-hover:scale-105"
            src={imageUrl}
            alt={productName}
            loading="lazy"
            onError={() => setImageFailed(true)}
          />
        ) : (
          <div className="flex flex-col items-center gap-3 text-vextro-muted">
            <span className="grid size-20 place-items-center rounded-3xl bg-gradient-to-br from-vextro-primary to-violet-600 text-3xl font-black text-white shadow-lg shadow-blue-500/20">
              {productName.charAt(0).toUpperCase()}
            </span>

            <small className="text-xs font-semibold">
              Product image unavailable
            </small>
          </div>
        )}

        {marketplaceCount > 1 ? (
          <span className="absolute right-4 top-4 rounded-full border border-emerald-200 bg-emerald-50/95 px-3 py-1.5 text-[10px] font-black text-emerald-700 shadow-sm backdrop-blur">
            {marketplaceCount} marketplaces
          </span>
        ) : null}
      </Link>

      <div className="flex flex-1 flex-col p-6">
        <div className="flex items-center justify-between gap-4 text-[10px] font-black uppercase tracking-[0.12em] text-vextro-muted">
          <span className="truncate">{brandName}</span>
          <span className="truncate text-right">
            {categoryName}
          </span>
        </div>

        <Link
          className="mt-4 line-clamp-2 min-h-14 text-xl font-black leading-7 tracking-tight text-vextro-ink transition hover:text-vextro-primary"
          to={`/products/${product.id}`}
        >
          {productName}
        </Link>

        <p className="mt-2 min-h-5 text-xs font-medium text-vextro-muted">
          {product.model
            ? `Model: ${product.model}`
            : "Standardized marketplace product"}
        </p>

        <div className="mt-6 flex items-end justify-between gap-4 border-t border-vextro-border pt-5">
          <div className="min-w-0">
            <span className="block text-[10px] font-bold uppercase tracking-wide text-vextro-muted">
              Lowest available price
            </span>

            <strong className="mt-1 block truncate text-xl font-black tracking-tight text-vextro-ink">
              {formatPrice(
                lowestPrice,
                product.currency || "PKR",
              )}
            </strong>
          </div>

          {Number.isFinite(rating) ? (
            <div className="flex shrink-0 items-center gap-1 rounded-xl bg-amber-50 px-3 py-2 text-xs font-black text-amber-700">
              <span className="text-amber-500">★</span>
              {rating.toFixed(1)}
            </div>
          ) : null}
        </div>

        <Link
          className="mt-5 flex min-h-11 items-center justify-between rounded-xl bg-blue-50 px-4 text-sm font-black text-vextro-primary transition hover:bg-vextro-primary hover:text-white"
          to={`/products/${product.id}`}
        >
          Compare listings

          <span className="text-lg transition group-hover:translate-x-1">
            →
          </span>
        </Link>
      </div>
    </article>
  );
}

export default ProductCard;