import { useState } from "react";
import { Link } from "react-router-dom";

import { formatPrice } from "../utils/productDisplay";

function RelatedProductCard({ product }) {
  const [imageFailed, setImageFailed] = useState(false);
  const productName = product.name || "Unnamed product";

  return (
    <article className="group flex h-full flex-col overflow-hidden rounded-2xl border border-vextro-border bg-white transition duration-300 hover:-translate-y-1 hover:border-emerald-200 hover:shadow-vextro">
      <Link
        className="grid h-48 place-items-center overflow-hidden border-b border-vextro-border bg-white p-5"
        to={`/products/${product.id}`}
        aria-label={`View ${productName}`}
      >
        {product.primary_image_url && !imageFailed ? (
          <img
            className="h-full w-full object-contain transition duration-300 group-hover:scale-105"
            src={product.primary_image_url}
            alt={productName}
            loading="lazy"
            referrerPolicy="no-referrer"
            onError={() => setImageFailed(true)}
          />
        ) : (
          <span className="grid size-20 place-items-center rounded-3xl bg-emerald-50 text-3xl font-black text-vextro-primary">
            {productName.charAt(0).toUpperCase()}
          </span>
        )}
      </Link>

      <div className="flex flex-1 flex-col p-4">
        <span className="text-[10px] font-black uppercase tracking-[0.12em] text-vextro-muted">
          {product.brand_name || "Unbranded"}
        </span>

        <Link
          className="mt-2 line-clamp-2 min-h-12 text-sm font-black leading-6 text-vextro-ink transition hover:text-vextro-primary"
          to={`/products/${product.id}`}
        >
          {productName}
        </Link>

        <strong className="mt-auto pt-4 text-lg font-black text-emerald-700">
          {formatPrice(product.lowest_price)}
        </strong>
      </div>
    </article>
  );
}

export default RelatedProductCard;
