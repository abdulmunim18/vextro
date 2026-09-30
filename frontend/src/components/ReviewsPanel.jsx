import { useEffect, useMemo, useState } from "react";

import {
  getProductReviewAnalysis,
  getProductReviews,
} from "../services/catalogService";
import { formatDate } from "../utils/productDisplay";

const PAGE_SIZE = 10;

// Distinct hue per suspicion level so the trust panel reads at a glance.
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
    <div className="flex items-center gap-3">
      <span className="w-6 text-xs font-black text-vextro-muted">
        {label}★
      </span>
      <div className="flex-1 overflow-hidden rounded-full bg-slate-100">
        <div
          className="h-2 bg-amber-400"
          style={{ width: `${percentage}%` }}
        />
      </div>
      <span className="w-8 text-right text-xs font-bold text-vextro-muted">
        {count}
      </span>
    </div>
  );
}

function ReviewsPanel({ productId }) {
  const [reviewsResponse, setReviewsResponse] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [page, setPage] = useState(1);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState(null);

  useEffect(() => {
    if (!productId) {
      return undefined;
    }

    let isMounted = true;
    setIsLoading(true);

    async function loadReviews() {
      try {
        const [reviewsData, analysisData] = await Promise.all([
          getProductReviews(productId, {
            page,
            page_size: PAGE_SIZE,
          }),
          // Review-analysis is a best-effort supplement; if it errors
          // the page still shows the review list.
          getProductReviewAnalysis(productId, {
            page: 1,
            page_size: 1,
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

    loadReviews();

    return () => {
      isMounted = false;
    };
  }, [productId, page]);

  const reviews = reviewsResponse?.items ?? [];
  const total = reviewsResponse?.total ?? 0;
  const totalPages = reviewsResponse?.total_pages ?? 0;
  const averageRating = reviewsResponse?.average_rating ?? null;
  const distribution = useMemo(
    () => reviewsResponse?.rating_distribution ?? {},
    [reviewsResponse],
  );

  const trustSummary = useMemo(() => {
    if (!analysis) {
      return null;
    }
    const analyzed = analysis.analyzed_reviews ?? 0;
    if (analyzed === 0) {
      return null;
    }
    const dominant =
      analysis.high >= analysis.medium && analysis.high >= analysis.low
        ? "high"
        : analysis.medium >= analysis.low
          ? "medium"
          : "low";
    return {
      analyzed,
      total: analysis.total_reviews ?? 0,
      high: analysis.high ?? 0,
      medium: analysis.medium ?? 0,
      low: analysis.low ?? 0,
      averageSuspicion:
        typeof analysis.average_suspicion_score === "number"
          ? analysis.average_suspicion_score
          : null,
      dominantLevel: dominant,
      style: SUSPICION_STYLES[dominant],
    };
  }, [analysis]);

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

  if (total === 0) {
    return (
      <section className="mt-10 rounded-3xl border border-dashed border-slate-300 bg-white p-10 text-center">
        <span className="text-xs font-black uppercase tracking-[0.18em] text-vextro-primary">
          Customer Reviews
        </span>
        <h3 className="mt-4 text-xl font-black text-vextro-ink">
          No reviews collected yet
        </h3>
        <p className="mt-2 text-sm text-vextro-muted">
          Marketplace reviews will appear here once VEXTRO ingests them
          for this product.
        </p>
      </section>
    );
  }

  return (
    <section className="mt-10 rounded-3xl border border-vextro-border bg-white p-6 shadow-sm sm:p-9">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <span className="text-xs font-black uppercase tracking-[0.18em] text-vextro-primary">
            Customer Reviews
          </span>
          <h2 className="mt-3 text-3xl font-black tracking-tight text-vextro-ink sm:text-4xl">
            What buyers are saying
          </h2>
          <p className="mt-3 text-sm leading-7 text-vextro-muted">
            Reviews are aggregated from the same marketplaces VEXTRO
            monitors for prices, so the rating you see here reflects
            real captured feedback rather than a merchant-supplied
            summary.
          </p>
        </div>
        <span className="rounded-full border border-vextro-border bg-white px-4 py-2 text-xs font-black text-vextro-muted">
          {total} {total === 1 ? "review" : "reviews"}
        </span>
      </div>

      <div className="mt-6 grid gap-5 md:grid-cols-[minmax(220px,280px)_1fr]">
        <div className="rounded-3xl border border-vextro-border bg-vextro-canvas p-5">
          <div className="flex items-end gap-2">
            <strong className="text-4xl font-black text-vextro-ink">
              {averageRating !== null
                ? averageRating.toFixed(1)
                : "-"}
            </strong>
            <span className="pb-1 text-sm font-bold text-vextro-muted">
              / 5
            </span>
          </div>
          <div className="mt-2">
            <StarRating value={averageRating} />
          </div>
          <p className="mt-3 text-xs font-bold text-vextro-muted">
            Based on {total} captured{" "}
            {total === 1 ? "review" : "reviews"}
          </p>

          <div className="mt-5 space-y-2">
            {[5, 4, 3, 2, 1].map((star) => (
              <DistributionBar
                key={star}
                label={star}
                count={Number(distribution[String(star)] ?? 0)}
                total={total}
              />
            ))}
          </div>
        </div>

        <div className="rounded-3xl border border-vextro-border bg-vextro-canvas p-5">
          {trustSummary ? (
            <>
              <span className="text-[10px] font-black uppercase tracking-[0.16em] text-vextro-muted">
                Review Trust Signals
              </span>
              <div
                className={`mt-3 inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-black ${trustSummary.style.text} ${trustSummary.style.bg} ${trustSummary.style.border}`}
              >
                <span
                  className={`inline-block size-2 rounded-full ${trustSummary.style.dot}`}
                />
                {trustSummary.style.label} · rule-based
              </div>
              <p className="mt-3 text-xs leading-6 text-vextro-muted">
                {trustSummary.analyzed} of {trustSummary.total}{" "}
                reviews were scored by the deterministic
                <span className="mx-1 font-black text-vextro-ink">
                  review-risk v1
                </span>
                engine. Averages and duplicate counts are computed
                from those; scores describe patterns, not proof of
                review fraud.
              </p>

              <div className="mt-4 grid grid-cols-3 gap-2 text-center">
                <div className="rounded-xl bg-white p-3">
                  <div className="text-[10px] font-black uppercase text-emerald-600">
                    Low
                  </div>
                  <strong className="text-lg font-black text-vextro-ink">
                    {trustSummary.low}
                  </strong>
                </div>
                <div className="rounded-xl bg-white p-3">
                  <div className="text-[10px] font-black uppercase text-amber-600">
                    Medium
                  </div>
                  <strong className="text-lg font-black text-vextro-ink">
                    {trustSummary.medium}
                  </strong>
                </div>
                <div className="rounded-xl bg-white p-3">
                  <div className="text-[10px] font-black uppercase text-red-600">
                    High
                  </div>
                  <strong className="text-lg font-black text-vextro-ink">
                    {trustSummary.high}
                  </strong>
                </div>
              </div>
            </>
          ) : (
            <>
              <span className="text-[10px] font-black uppercase tracking-[0.16em] text-vextro-muted">
                Review Trust Signals
              </span>
              <p className="mt-3 text-sm leading-6 text-vextro-muted">
                No review-risk analysis has run yet for this product.
                Once analyses are stored, this panel will show the
                low / medium / high suspicion breakdown alongside the
                review list.
              </p>
            </>
          )}
        </div>
      </div>

      <div className="mt-8 space-y-4">
        {reviews.map((review) => (
          <article
            className="rounded-2xl border border-vextro-border bg-white p-5"
            key={review.id}
          >
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="min-w-0">
                <strong className="block truncate text-sm font-black text-vextro-ink">
                  {review.reviewer_display_name || "Anonymous buyer"}
                </strong>
                <div className="mt-1 flex flex-wrap items-center gap-3">
                  <StarRating value={review.rating} />
                  {review.verified_purchase ? (
                    <span className="rounded-full bg-emerald-50 px-2.5 py-0.5 text-[10px] font-black uppercase tracking-wide text-emerald-700">
                      Verified
                    </span>
                  ) : null}
                  <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-[10px] font-black uppercase tracking-wide text-slate-600">
                    {review.platform_code}
                  </span>
                </div>
              </div>
              <span className="text-xs font-bold text-vextro-muted">
                {formatDate(review.reviewed_at)}
              </span>
            </div>
            {review.review_text ? (
              <p className="mt-4 text-sm leading-7 text-vextro-ink">
                {review.review_text}
              </p>
            ) : (
              <p className="mt-4 text-xs italic text-vextro-muted">
                (Reviewer left only a rating.)
              </p>
            )}
          </article>
        ))}
      </div>

      {totalPages > 1 ? (
        <div className="mt-6 flex flex-wrap items-center justify-between gap-3">
          <span className="text-xs font-bold text-vextro-muted">
            Page {reviewsResponse.page} of {totalPages}
          </span>
          <div className="flex gap-2">
            <button
              type="button"
              className="rounded-xl border border-vextro-border bg-white px-4 py-2 text-xs font-black text-vextro-ink transition hover:border-blue-200 disabled:cursor-not-allowed disabled:opacity-50"
              onClick={() => setPage((current) => Math.max(1, current - 1))}
              disabled={reviewsResponse.page <= 1}
            >
              ← Newer
            </button>
            <button
              type="button"
              className="rounded-xl border border-vextro-border bg-white px-4 py-2 text-xs font-black text-vextro-ink transition hover:border-blue-200 disabled:cursor-not-allowed disabled:opacity-50"
              onClick={() =>
                setPage((current) =>
                  Math.min(totalPages, current + 1),
                )
              }
              disabled={reviewsResponse.page >= totalPages}
            >
              Older →
            </button>
          </div>
        </div>
      ) : null}
    </section>
  );
}

export default ReviewsPanel;
