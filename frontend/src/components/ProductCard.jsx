import { Link } from "react-router-dom";

function ProductCard({ product }) {
  const productName =
    product.name || "Unnamed product";

  return (
    <article className="group flex h-full flex-col overflow-hidden rounded-3xl border border-vextro-border bg-white shadow-sm transition duration-300 hover:-translate-y-1.5 hover:border-blue-200 hover:shadow-vextro">
      <Link
        className="relative grid h-64 place-items-center overflow-hidden bg-gradient-to-br from-slate-50 via-blue-50/60 to-violet-50/60"
        to={`/products/${product.id}`}
        aria-label={`View ${productName}`}
      >
        <div className="flex flex-col items-center gap-4">
          <span className="grid size-24 place-items-center rounded-[30px] bg-gradient-to-br from-vextro-primary to-violet-600 text-4xl font-black text-white shadow-lg shadow-blue-500/20 transition duration-300 group-hover:scale-105">
            {productName.charAt(0).toUpperCase()}
          </span>

          <small className="text-xs font-bold text-vextro-muted">
            Marketplace comparison product
          </small>
        </div>

        <span
          className={`absolute right-4 top-4 rounded-full px-3 py-1.5 text-[10px] font-black ${
            product.is_active
              ? "bg-emerald-50 text-emerald-700"
              : "bg-red-50 text-red-700"
          }`}
        >
          {product.is_active ? "Active" : "Inactive"}
        </span>
      </Link>

      <div className="flex flex-1 flex-col p-6">
        <div className="flex items-center justify-between gap-4 text-[10px] font-black uppercase tracking-[0.12em] text-vextro-muted">
          <span className="truncate">
            {product.brand_name || "Unbranded"}
          </span>

          <span className="truncate text-right">
            {product.category_name || "General"}
          </span>
        </div>

        <Link
          className="mt-4 line-clamp-2 min-h-14 text-xl font-black leading-7 tracking-tight text-vextro-ink transition hover:text-vextro-primary"
          to={`/products/${product.id}`}
        >
          {productName}
        </Link>

        <p className="mt-2 text-xs font-medium text-vextro-muted">
          {product.model
            ? `Model: ${product.model}`
            : "Standardized canonical product"}
        </p>

        <div className="mt-auto pt-7">
          <div className="rounded-2xl bg-vextro-canvas p-4">
            <span className="block text-[10px] font-black uppercase tracking-wide text-vextro-muted">
              Available intelligence
            </span>

            <div className="mt-3 flex flex-wrap gap-2">
              <span className="rounded-lg bg-white px-3 py-2 text-[10px] font-bold text-vextro-ink">
                Offers
              </span>

              <span className="rounded-lg bg-white px-3 py-2 text-[10px] font-bold text-vextro-ink">
                Price history
              </span>

              <span className="rounded-lg bg-white px-3 py-2 text-[10px] font-bold text-vextro-ink">
                Variants
              </span>
            </div>
          </div>

          <Link
            className="mt-5 flex min-h-11 items-center justify-between rounded-xl bg-blue-50 px-4 text-sm font-black text-vextro-primary transition hover:bg-vextro-primary hover:text-white"
            to={`/products/${product.id}`}
          >
            View marketplace offers

            <span className="text-lg transition group-hover:translate-x-1">
              →
            </span>
          </Link>
        </div>
      </div>
    </article>
  );
}

export default ProductCard;