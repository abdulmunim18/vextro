import { useState } from "react";

// Built from Daraz's own rating and review count per offer; see
// utils/darazRatings.js for why there is no review text.
const SELLERS_SHOWN = 5;

function Stars({ value }) {
  const rounded = Math.round(Number(value) || 0);

  return (
    <span className="inline-flex items-center gap-0.5" aria-hidden="true">
      {[1, 2, 3, 4, 5].map((star) => (
        <span
          key={star}
          className={star <= rounded ? "text-amber-500" : "text-slate-300"}
        >
          ★
        </span>
      ))}
    </span>
  );
}

function DarazRatingBox({ summary }) {
  const [showAll, setShowAll] = useState(false);
  const sellers = showAll
    ? summary.sellers
    : summary.sellers.slice(0, SELLERS_SHOWN);

  return (
    <div className="flex h-full flex-col rounded-3xl border border-vextro-border bg-white p-5 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="rounded-full bg-orange-50 px-3 py-1.5 text-[10px] font-black uppercase tracking-[0.14em] text-orange-700">
          Daraz
        </span>
        <span className="rounded-full border border-vextro-border bg-white px-3 py-1 text-[10px] font-black text-vextro-muted">
          {summary.sellers.length}{" "}
          {summary.sellers.length === 1 ? "seller" : "sellers"}
        </span>
      </div>

      <div className="mt-5 rounded-2xl border border-amber-200 bg-amber-50/60 p-4">
        <div className="text-[10px] font-black uppercase tracking-[0.14em] text-amber-700">
          Buyer rating on Daraz
        </div>
        {summary.rating !== null ? (
          <>
            <div className="mt-2 flex flex-wrap items-end gap-2">
              <strong className="text-4xl font-black text-vextro-ink">
                {summary.rating.toFixed(1)}
              </strong>
              <span className="pb-1 text-xs font-bold text-vextro-muted">
                / 5
              </span>
              <span className="pb-1">
                <Stars value={summary.rating} />
              </span>
            </div>
            <div className="mt-1 text-xs font-bold text-vextro-muted">
              from {summary.count.toLocaleString()}{" "}
              {summary.count === 1 ? "review" : "reviews"} across{" "}
              {summary.ratedSellers}{" "}
              {summary.ratedSellers === 1 ? "seller" : "sellers"}
            </div>
          </>
        ) : (
          <p className="mt-2 text-sm font-bold text-vextro-ink">
            No buyer has rated this phone on Daraz yet.
          </p>
        )}
      </div>

      <div className="mt-5">
        <div className="text-[10px] font-black uppercase tracking-[0.14em] text-vextro-muted">
          Rating by seller
        </div>
        <ul className="mt-2 divide-y divide-vextro-border rounded-2xl border border-vextro-border">
          {sellers.map((seller) => (
            <li
              key={seller.key}
              className="flex flex-wrap items-center justify-between gap-2 px-3 py-2.5 text-xs"
            >
              <span className="flex min-w-0 flex-wrap items-center gap-1.5">
                <span className="truncate font-bold text-vextro-ink">
                  {seller.name}
                </span>
                {seller.verified ? (
                  <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-[9px] font-black uppercase text-emerald-700">
                    Daraz Mall
                  </span>
                ) : null}
                {!seller.inStock ? (
                  <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[9px] font-black uppercase text-slate-500">
                    Out of stock
                  </span>
                ) : null}
              </span>
              <span className="text-vextro-muted">
                {seller.rating !== null ? (
                  <>
                    <span className="text-amber-500">★</span>{" "}
                    <strong className="text-vextro-ink">
                      {seller.rating.toFixed(1)}
                    </strong>{" "}
                    · {seller.count.toLocaleString()}{" "}
                    {seller.count === 1 ? "review" : "reviews"}
                  </>
                ) : (
                  "Not rated yet"
                )}
              </span>
            </li>
          ))}
        </ul>
        {summary.sellers.length > SELLERS_SHOWN ? (
          <button
            type="button"
            onClick={() => setShowAll((current) => !current)}
            className="mt-2 text-xs font-black text-vextro-primary hover:underline"
          >
            {showAll
              ? "Show fewer sellers"
              : `Show all ${summary.sellers.length} sellers`}
          </button>
        ) : null}
      </div>

      <p className="mt-4 text-[11px] leading-5 text-vextro-muted">
        Daraz shows the text of its reviews only on its own site, so
        VEXTRO shows Daraz's own rating for each seller here.
      </p>

      {summary.url ? (
        <a
          className="mt-4 inline-flex items-center justify-center rounded-full bg-orange-600 px-4 py-2.5 text-xs font-black text-white hover:bg-orange-700"
          href={summary.url}
          target="_blank"
          rel="noreferrer"
        >
          Read all reviews on Daraz ↗
        </a>
      ) : null}
    </div>
  );
}

export default DarazRatingBox;
