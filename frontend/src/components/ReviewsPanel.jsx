import { useEffect, useMemo, useState } from "react";

import {
  getProductReviewAnalysis,
  getProductReviews,
} from "../services/catalogService";
import { formatDate } from "../utils/productDisplay";

// The reviews API only paginates in one direction, so we pull a generous
// first page and split it client-side by platform. 100 is the server's
// maximum page_size — enough to cover ~50 reviews per marketplace for a
// single product without a second request.
const FETCH_PAGE_SIZE = 100;
const REVIEWS_PER_PLATFORM_BOX = 6;
const SUPPORTED_PLATFORM_CODES = ["daraz", "priceoye"];
const MIN_REVIEWS_FOR_RECOMMENDATION = 3;

const SUSPICION_STYLES = {
  low: {
    text: "text-emerald-700",
    bg: "bg-emerald-50",
    border: "border-emerald-200",
    dot: "bg-emerald-500",
    label: "Low suspicion",
  },
  medium: {
    text: "text-amber-700",
    bg: "bg-amber-50",
    border: "border-amber-200",
    dot: "bg-amber-500",
    label: "Medium suspicion",
  },
  high: {
    text: "text-red-700",
    bg: "bg-red-50",
    border: "border-red-200",
    dot: "bg-red-500",
    label: "High suspicion",
  },
};

const PLATFORM_LABELS = {
  daraz: "Daraz",
  priceoye: "PriceOye",
};

function StarRating({ value }) {
  const rounded = Math.round(value ?? 0);

  return (
    <span className="inline-flex items-center gap-0.5 text-amber-500">
      {[1, 2, 3, 4, 5].map((star) => (
        <span
          key={star}
          className={
            star <= rounded ? "text-amber-500" : "text-slate-300"
          }
          aria-hidden="true"
        >
          ★
        </span>
      ))}
    </span>
  );
}

function DistributionBar({ label, count, total }) {
  const percentage = total > 0 ? (count / total) * 100 : 0;

  return (
    <div className="flex items-center gap-2">
      <span className="w-6 text-[10px] font-black text-vextro-muted">
        {label}★
      </span>
      <div className="flex-1 overflow-hidden rounded-full bg-slate-100">
        <div
          className="h-1.5 bg-amber-400"
          style={{ width: `${percentage}%` }}
        />
      </div>
      <span className="w-6 text-right text-[10px] font-bold text-vextro-muted">
        {count}
      </span>
    </div>
  );
}

function dominantLevel(low, medium, high) {
  if (high >= medium && high >= low) return "high";
  if (medium >= low) return "medium";
  return "low";
}

// What the marketplace itself reports for this phone: its star rating and
// how many buyers rated it. VEXTRO can read only some of the review text
// (none of it on Daraz, which closes its review pages to other sites), so
// these figures are the fuller picture of what buyers think.
function summariseMarketplaceRatings(listings) {
  const rated = listings.filter(
    (listing) =>
      Number(listing.review_count) > 0 && Number(listing.rating) > 0,
  );

  if (rated.length === 0) {
    return null;
  }

  // A marketplace that sells the phone itself repeats one product-wide
  // figure on every colour; separate sellers each have their own buyers.
  const bySeller = new Map();
  rated.forEach((listing) => {
    const key = listing.seller?.id ?? "marketplace";
    const count = Number(listing.review_count);
    const current = bySeller.get(key);

    if (listing.seller?.id == null) {
      if (!current || count > current.count) {
        bySeller.set(key, {
          name: null,
          count,
          rating: Number(listing.rating),
          url: listing.product_url,
        });
      }
      return;
    }

    if (!current) {
      bySeller.set(key, {
        name: listing.seller.name,
        count,
        weighted: Number(listing.rating) * count,
        url: listing.product_url,
        topCount: count,
      });
      return;
    }

    current.count += count;
    current.weighted += Number(listing.rating) * count;
    if (count > current.topCount) {
      current.topCount = count;
      current.url = listing.product_url;
    }
  });

  const sources = [...bySeller.values()]
    .map((source) => ({
      name: source.name,
      count: source.count,
      rating:
        source.weighted !== undefined
          ? source.weighted / source.count
          : source.rating,
      url: source.url,
    }))
    .sort((first, second) => second.count - first.count);

  const count = sources.reduce((sum, source) => sum + source.count, 0);
  const rating =
    sources.reduce(
      (sum, source) => sum + source.rating * source.count,
      0,
    ) / count;

  return { count, rating, sources };
}

function MarketplaceRatingSummary({ label, summary }) {
  if (!summary) {
    return null;
  }

  const namedSources = summary.sources.filter((source) => source.name);

  return (
    <div className="rounded-2xl border border-amber-200 bg-amber-50/60 p-4 text-left">
      <div className="text-[10px] font-black uppercase tracking-[0.14em] text-amber-700">
        Rating on {label}
      </div>
      <div className="mt-2 flex flex-wrap items-end gap-2">
        <strong className="text-3xl font-black text-vextro-ink">
          {summary.rating.toFixed(1)}
        </strong>
        <span className="pb-1 text-xs font-bold text-vextro-muted">
          / 5
        </span>
        <div className="pb-1">
          <StarRating value={summary.rating} />
        </div>
        <span className="pb-1 text-xs font-bold text-vextro-muted">
          from {summary.count.toLocaleString()}{" "}
          {summary.count === 1 ? "buyer" : "buyers"}
        </span>
      </div>

      {namedSources.length > 0 ? (
        <ul className="mt-3 space-y-1.5">
          {namedSources.slice(0, 4).map((source) => (
            <li
              key={source.name}
              className="flex flex-wrap items-center justify-between gap-2 text-xs"
            >
              <span className="font-bold text-vextro-ink">
                {source.name}
              </span>
              <span className="text-vextro-muted">
                ★ {source.rating.toFixed(1)} ·{" "}
                {source.count.toLocaleString()}{" "}
                {source.count === 1 ? "review" : "reviews"}
              </span>
            </li>
          ))}
        </ul>
      ) : null}

      {summary.sources[0]?.url ? (
        <a
          className="mt-3 inline-flex text-xs font-black text-vextro-primary hover:underline"
          href={summary.sources[0].url}
          target="_blank"
          rel="noreferrer"
        >
          Read the reviews on {label} ↗
        </a>
      ) : null}
    </div>
  );
}

function EmptyPlatformCard({ label, marketplace, isListed }) {
  return (
    <div className="flex h-full flex-col rounded-3xl border border-dashed border-slate-300 bg-white p-6">
      <div className="flex items-center justify-between gap-2">
        <span className="rounded-full bg-slate-100 px-3 py-1.5 text-[10px] font-black uppercase tracking-[0.14em] text-vextro-muted">
          {label}
        </span>
      </div>

      {marketplace ? (
        <div className="mt-5">
          <MarketplaceRatingSummary label={label} summary={marketplace} />
          <p className="mt-4 text-xs leading-6 text-vextro-muted">
            {label} does not let other sites collect the text of its
            reviews, so VEXTRO shows {label}'s own rating and review
            count. Open {label} to read what buyers wrote.
          </p>
        </div>
      ) : (
        <div className="mt-6 flex flex-1 flex-col items-center justify-center text-center">
          <span className="text-4xl" aria-hidden="true">
            💬
          </span>
          <h4 className="mt-3 text-base font-black text-vextro-ink">
            {isListed
              ? `No buyer has reviewed this phone on ${label} yet`
              : `This phone is not listed on ${label}`}
          </h4>
          <p className="mt-2 text-xs leading-6 text-vextro-muted">
            {isListed
              ? `Reviews will appear here as soon as ${label} shows any.`
              : `There are no ${label} reviews to compare.`}
          </p>
        </div>
      )}
    </div>
  );
}

function PlatformReviewBox({ label, group }) {
  const {
    reviews,
    marketplace,
    total,
    averageRating,
    distribution,
    analyzed,
    low,
    medium,
    high,
    averageSuspicion,
  } = group;

  const trustLevel = analyzed > 0
    ? dominantLevel(low, medium, high)
    : null;
  const trustStyle = trustLevel ? SUSPICION_STYLES[trustLevel] : null;

  return (
    <div className="flex h-full flex-col rounded-3xl border border-vextro-border bg-white p-5 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="rounded-full bg-blue-50 px-3 py-1.5 text-[10px] font-black uppercase tracking-[0.14em] text-vextro-primary">
          {label}
        </span>
        <span className="rounded-full border border-vextro-border bg-white px-3 py-1 text-[10px] font-black text-vextro-muted">
          {total} {total === 1 ? "review" : "reviews"} shown
        </span>
      </div>

      {marketplace && marketplace.count > total ? (
        <div className="mt-4">
          <MarketplaceRatingSummary label={label} summary={marketplace} />
          <p className="mt-3 text-[11px] leading-5 text-vextro-muted">
            Below: the {total === 1 ? "review" : `${total} reviews`}{" "}
            VEXTRO could read from {label}.
          </p>
        </div>
      ) : null}

      <div className="mt-5 flex items-end gap-3">
        <strong className="text-4xl font-black text-vextro-ink">
          {averageRating !== null ? averageRating.toFixed(1) : "-"}
        </strong>
        <span className="pb-1 text-xs font-bold text-vextro-muted">
          / 5
        </span>
        <div className="ml-1 pb-1">
          <StarRating value={averageRating} />
        </div>
      </div>

      <div className="mt-4 space-y-1.5">
        {[5, 4, 3, 2, 1].map((star) => (
          <DistributionBar
            key={star}
            label={star}
            count={distribution[star] ?? 0}
            total={total}
          />
        ))}
      </div>

      {trustStyle ? (
        <div
          className={`mt-5 rounded-2xl border p-3 ${trustStyle.text} ${trustStyle.bg} ${trustStyle.border}`}
        >
          <div className="flex items-center gap-2 text-[10px] font-black uppercase tracking-[0.14em]">
            <span
              className={`inline-block size-2 rounded-full ${trustStyle.dot}`}
            />
            {trustStyle.label} · {analyzed} of {total} analysed
          </div>
          <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[11px] font-bold">
            <span>Low {low}</span>
            <span>Med {medium}</span>
            <span>High {high}</span>
            {averageSuspicion !== null ? (
              <span>Avg score {averageSuspicion.toFixed(1)}</span>
            ) : null}
          </div>
        </div>
      ) : (
        <div className="mt-5 rounded-2xl border border-slate-200 bg-slate-50 p-3 text-[11px] font-bold text-slate-500">
          Review-risk analysis has not run for this platform yet.
        </div>
      )}

      <div className="mt-5 space-y-3">
        {reviews.slice(0, REVIEWS_PER_PLATFORM_BOX).map((review) => (
          <article
            className="rounded-2xl border border-vextro-border bg-vextro-canvas p-4"
            key={review.id}
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="min-w-0">
                <strong className="block truncate text-xs font-black text-vextro-ink">
                  {review.reviewer_display_name || "Anonymous buyer"}
                </strong>
                <div className="mt-1 flex flex-wrap items-center gap-2">
                  <StarRating value={review.rating} />
                  {review.verified_purchase ? (
                    <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-[9px] font-black uppercase tracking-wide text-emerald-700">
                      Verified
                    </span>
                  ) : null}
                </div>
              </div>
              <span className="text-[10px] font-bold text-vextro-muted">
                {formatDate(review.reviewed_at)}
              </span>
            </div>
            {review.review_text ? (
              <p className="mt-3 line-clamp-4 text-xs leading-6 text-vextro-ink">
                {review.review_text}
              </p>
            ) : (
              <p className="mt-3 text-[11px] italic text-vextro-muted">
                (Reviewer left only a rating.)
              </p>
            )}
          </article>
        ))}

        {reviews.length > REVIEWS_PER_PLATFORM_BOX ? (
          <p className="text-center text-[10px] font-bold text-vextro-muted">
            + {reviews.length - REVIEWS_PER_PLATFORM_BOX} more{" "}
            {label} {reviews.length - REVIEWS_PER_PLATFORM_BOX === 1
              ? "review"
              : "reviews"}
          </p>
        ) : null}
      </div>
    </div>
  );
}

function TrustRecommendation({ groups }) {
  // We only recommend once we have enough analysed evidence on at least
  // one side. A single review is easy to fake either way; three is a
  // conservative floor that keeps the recommendation trustworthy.
  const eligible = groups.filter(
    (group) => group.analyzed >= MIN_REVIEWS_FOR_RECOMMENDATION,
  );

  if (eligible.length === 0) {
    const rated = groups.filter((group) => group.marketplace);

    return (
      <div className="mt-6 rounded-3xl border border-slate-200 bg-slate-50 p-5">
        <div className="text-[10px] font-black uppercase tracking-[0.14em] text-vextro-muted">
          How buyers rate it on each marketplace
        </div>
        {rated.length > 0 ? (
          <div className="mt-3 grid gap-2 text-xs md:grid-cols-2">
            {rated.map((group) => (
              <div
                key={group.code}
                className="rounded-xl bg-white p-3"
              >
                <div className="font-black text-vextro-ink">
                  {group.label}
                </div>
                <div className="text-vextro-muted">
                  ★ {group.marketplace.rating.toFixed(1)} / 5 from{" "}
                  {group.marketplace.count.toLocaleString()}{" "}
                  {group.marketplace.count === 1 ? "buyer" : "buyers"}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="mt-2 text-sm font-bold text-vextro-ink">
            No buyer has rated this phone on either marketplace yet.
          </p>
        )}
        <p className="mt-3 text-xs leading-6 text-vextro-muted">
          VEXTRO names a more trustworthy marketplace only once it has
          read and risk-scored at least {MIN_REVIEWS_FOR_RECOMMENDATION}{" "}
          reviews from one. Until then the ratings above are each
          marketplace's own figures, for you to weigh.
        </p>
      </div>
    );
  }

  if (eligible.length === 1) {
    const only = eligible[0];
    return (
      <div className="mt-6 rounded-3xl border border-emerald-200 bg-emerald-50 p-5">
        <div className="text-[10px] font-black uppercase tracking-[0.14em] text-emerald-700">
          Recommended marketplace
        </div>
        <p className="mt-2 text-sm font-black text-emerald-800">
          🏆 Buy from {only.label} — the only platform with reviewed
          evidence for this product right now.
        </p>
        <p className="mt-1 text-xs leading-6 text-emerald-700">
          {only.total} {only.total === 1 ? "review" : "reviews"},
          average {only.averageRating?.toFixed(1) ?? "-"}/5,{" "}
          {only.analyzed} scored ({only.low} low · {only.medium} med
          · {only.high} high suspicion).
        </p>
      </div>
    );
  }

  // Both platforms have enough analysed reviews. Pick the one with the
  // highest share of low-suspicion reviews; tie-break by review count,
  // then by average rating.
  const scored = eligible
    .map((group) => ({
      ...group,
      lowRatio: group.analyzed > 0 ? group.low / group.analyzed : 0,
    }))
    .sort((a, b) => {
      if (b.lowRatio !== a.lowRatio) return b.lowRatio - a.lowRatio;
      if (b.total !== a.total) return b.total - a.total;
      return (b.averageRating ?? 0) - (a.averageRating ?? 0);
    });

  const [winner, runnerUp] = scored;
  const winnerLowPercent = Math.round(winner.lowRatio * 100);
  const runnerUpLowPercent = Math.round(runnerUp.lowRatio * 100);
  const isDecisive = winnerLowPercent - runnerUpLowPercent >= 10;

  return (
    <div
      className={`mt-6 rounded-3xl border p-5 ${
        isDecisive
          ? "border-emerald-200 bg-emerald-50"
          : "border-amber-200 bg-amber-50"
      }`}
    >
      <div
        className={`text-[10px] font-black uppercase tracking-[0.14em] ${
          isDecisive ? "text-emerald-700" : "text-amber-700"
        }`}
      >
        Which platform can you trust?
      </div>
      <p
        className={`mt-2 text-sm font-black ${
          isDecisive ? "text-emerald-800" : "text-amber-800"
        }`}
      >
        {isDecisive
          ? `🏆 ${winner.label} looks more trustworthy for this product.`
          : `Both platforms show similar review quality — check the details before deciding.`}
      </p>
      <div className="mt-3 grid gap-2 text-xs md:grid-cols-2">
        <div className="rounded-xl bg-white/70 p-3">
          <div className="font-black text-vextro-ink">
            {winner.label}
          </div>
          <div className="text-vextro-muted">
            {winnerLowPercent}% low-suspicion · avg{" "}
            {winner.averageRating?.toFixed(1) ?? "-"}/5 ·{" "}
            {winner.total} reviews
          </div>
        </div>
        <div className="rounded-xl bg-white/70 p-3">
          <div className="font-black text-vextro-ink">
            {runnerUp.label}
          </div>
          <div className="text-vextro-muted">
            {runnerUpLowPercent}% low-suspicion · avg{" "}
            {runnerUp.averageRating?.toFixed(1) ?? "-"}/5 ·{" "}
            {runnerUp.total} reviews
          </div>
        </div>
      </div>
      <p className="mt-3 text-[11px] leading-5 text-vextro-muted">
        Score describes patterns in review text and timing, not proof
        of fraud. Higher rating alone doesn't equal higher trust —
        VEXTRO weighs the reviewed evidence beneath each star.
      </p>
    </div>
  );
}

function ReviewsPanel({ productId, listings = [], platformNames }) {
  const [reviewsResponse, setReviewsResponse] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState(null);

  useEffect(() => {
    if (!productId) {
      return undefined;
    }

    let isMounted = true;

    async function loadReviews() {
      // Moving into the task keeps the effect body free of a synchronous
      // setState, which React warns about as a cascading render.
      setIsLoading(true);

      try {
        const [reviewsData, analysisData] = await Promise.all([
          getProductReviews(productId, {
            page: 1,
            page_size: FETCH_PAGE_SIZE,
          }),
          getProductReviewAnalysis(productId, {
            page: 1,
            page_size: FETCH_PAGE_SIZE,
          }).catch(() => null),
        ]);

        if (!isMounted) {
          return;
        }

        setReviewsResponse(reviewsData);
        setAnalysis(analysisData);
        setErrorMessage(null);
      } catch (error) {
        if (!isMounted) {
          return;
        }
        setErrorMessage(
          error?.response?.data?.detail?.message ||
            "Reviews could not be loaded right now.",
        );
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    const timeoutId = window.setTimeout(loadReviews, 0);

    return () => {
      isMounted = false;
      window.clearTimeout(timeoutId);
    };
  }, [productId]);

  const platformGroups = useMemo(() => {
    const reviews = reviewsResponse?.items ?? [];
    const analysisReviews = analysis?.reviews ?? [];

    return SUPPORTED_PLATFORM_CODES.map((code) => {
      const label = PLATFORM_LABELS[code];

      const platformReviews = reviews.filter(
        (review) => review.platform_code === code,
      );
      const total = platformReviews.length;

      const distribution = { 1: 0, 2: 0, 3: 0, 4: 0, 5: 0 };
      let sumRating = 0;
      platformReviews.forEach((review) => {
        const rating = Number(review.rating);
        if (rating >= 1 && rating <= 5) {
          distribution[rating] = (distribution[rating] ?? 0) + 1;
          sumRating += rating;
        }
      });
      const averageRating = total > 0 ? sumRating / total : null;

      // Correlate analysis items to this platform via listing_id ->
      // platform_code from the reviews list, since analysis payload
      // does not include platform_code itself.
      const reviewIdToPlatform = new Map(
        reviews.map((review) => [review.id, review.platform_code]),
      );
      const platformAnalysis = analysisReviews.filter((item) => {
        const platformCode = reviewIdToPlatform.get(item.review_id);
        return platformCode === code;
      });

      const analyzed = platformAnalysis.length;
      let low = 0;
      let medium = 0;
      let high = 0;
      let sumSuspicion = 0;
      platformAnalysis.forEach((item) => {
        if (item.suspicion_level === "low") low += 1;
        else if (item.suspicion_level === "medium") medium += 1;
        else if (item.suspicion_level === "high") high += 1;
        sumSuspicion += Number(item.suspicion_score ?? 0);
      });
      const averageSuspicion = analyzed > 0
        ? sumSuspicion / analyzed
        : null;

      const platformListings = listings.filter(
        (listing) =>
          String(
            platformNames?.get(listing.platform_id) ?? "",
          ).toLowerCase() === code,
      );

      return {
        code,
        label,
        reviews: platformReviews,
        marketplace: summariseMarketplaceRatings(platformListings),
        isListed: platformListings.length > 0,
        total,
        averageRating,
        distribution,
        analyzed,
        low,
        medium,
        high,
        averageSuspicion,
      };
    });
  }, [reviewsResponse, analysis, listings, platformNames]);

  const overallTotal = reviewsResponse?.total ?? 0;
  const marketplaceTotal = platformGroups.reduce(
    (sum, group) =>
      sum + Math.max(group.marketplace?.count ?? 0, group.total),
    0,
  );

  if (isLoading && reviewsResponse === null) {
    return (
      <section className="mt-10 rounded-3xl border border-vextro-border bg-white p-6 shadow-sm sm:p-9">
        <span className="text-xs font-black uppercase tracking-[0.18em] text-vextro-primary">
          Customer Reviews
        </span>
        <p className="mt-4 text-sm text-vextro-muted">
          Loading reviews...
        </p>
      </section>
    );
  }

  if (errorMessage) {
    return (
      <section className="mt-10 rounded-3xl border border-vextro-border bg-white p-6 shadow-sm sm:p-9">
        <span className="text-xs font-black uppercase tracking-[0.18em] text-vextro-primary">
          Customer Reviews
        </span>
        <p className="mt-4 text-sm text-red-600">{errorMessage}</p>
      </section>
    );
  }

  return (
    <section className="mt-10 rounded-3xl border border-vextro-border bg-white p-6 shadow-sm sm:p-9">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <span className="text-xs font-black uppercase tracking-[0.18em] text-vextro-primary">
            Customer Reviews by Marketplace
          </span>
          <h2 className="mt-3 text-3xl font-black tracking-tight text-vextro-ink sm:text-4xl">
            Compare what buyers said
          </h2>
          <p className="mt-3 text-sm leading-7 text-vextro-muted">
            Each marketplace's own rating and review count, with the
            reviews VEXTRO could read and how its review-risk engine
            scored them. Use this to decide which marketplace to buy
            from — not just which one is cheaper.
          </p>
        </div>
        <span className="rounded-full border border-vextro-border bg-white px-4 py-2 text-xs font-black text-vextro-muted">
          {marketplaceTotal.toLocaleString()}{" "}
          {marketplaceTotal === 1 ? "buyer rating" : "buyer ratings"} ·{" "}
          {overallTotal} shown
        </span>
      </div>

      <TrustRecommendation groups={platformGroups} />

      <div className="mt-6 grid gap-5 md:grid-cols-2">
        {platformGroups.map((group) =>
          group.total > 0 ? (
            <PlatformReviewBox
              key={group.code}
              label={group.label}
              group={group}
            />
          ) : (
            <EmptyPlatformCard
              key={group.code}
              label={group.label}
              marketplace={group.marketplace}
              isListed={group.isListed}
            />
          ),
        )}
      </div>

      <p className="mt-6 text-[11px] leading-5 text-vextro-muted">
        Reviews are refreshed automatically as new phones are ingested
        by VEXTRO's marketplace crawlers — no action needed on your
        part.
      </p>
    </section>
  );
}

export default ReviewsPanel;
