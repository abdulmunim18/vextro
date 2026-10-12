import { useMemo, useState } from "react";

import { formatDate, formatPrice } from "../utils/productDisplay";

const POSTS_SHOWN = 6;

// The three kinds VEXTRO's opinion scorer sorts a post into. Only the first
// says anything about the phone, so it is the tab a reader lands on.
const KINDS = [
  {
    code: "opinion",
    tab: "Opinions",
    countKey: "genuine_opinion_count",
    empty: "No visitor has given a view of this phone yet.",
  },
  {
    code: "question",
    tab: "Questions",
    countKey: "question_count",
    empty: "No visitor has asked about this phone.",
  },
  {
    code: "advert",
    tab: "Sale adverts",
    countKey: "advert_count",
    empty: "No buy-and-sell adverts were found.",
  },
];

const RISK_STYLES = {
  low: "border-emerald-200 bg-emerald-50 text-emerald-700",
  medium: "border-amber-200 bg-amber-50 text-amber-700",
  high: "border-red-200 bg-red-50 text-red-700",
};

const KIND_BADGES = {
  opinion: "Opinion",
  question: "Question",
  advert: "Sale advert",
};

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

function Post({ post }) {
  const isAdvert = post.opinion_kind === "advert";
  const riskStyle = RISK_STYLES[post.suspicion_level] ?? RISK_STYLES.low;

  return (
    <article
      className={`rounded-2xl border p-4 ${
        isAdvert
          ? "border-red-100 bg-red-50/40"
          : "border-vextro-border bg-vextro-canvas"
      }`}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <strong className="min-w-0 truncate text-xs font-black text-vextro-ink">
          {post.author_display_name || "Anonymous visitor"}
        </strong>
        <span className="text-[10px] font-bold text-vextro-muted">
          {post.posted_at ? formatDate(post.posted_at) : "Date not given"}
        </span>
      </div>

      <p className="mt-3 text-xs leading-6 text-vextro-ink">
        {post.opinion_text}
      </p>

      {isAdvert ? (
        <div className="mt-3">
          <span
            className={`inline-flex rounded-full border px-2.5 py-1 text-[9px] font-black uppercase tracking-wide ${riskStyle}`}
          >
            {KIND_BADGES.advert} · {post.suspicion_level} risk · score{" "}
            {post.suspicion_score}
          </span>
          {post.analysis_reasons?.length > 0 ? (
            <ul className="mt-2 list-disc space-y-0.5 pl-4 text-[11px] leading-5 text-vextro-muted">
              {post.analysis_reasons.map((reason) => (
                <li key={reason}>{reason}</li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : post.suspicion_level && post.suspicion_level !== "low" ? (
        <div className="mt-3">
          <span
            className={`inline-flex rounded-full border px-2.5 py-1 text-[9px] font-black uppercase tracking-wide ${riskStyle}`}
          >
            {post.suspicion_level} risk · score {post.suspicion_score}
          </span>
          <ul className="mt-2 list-disc space-y-0.5 pl-4 text-[11px] leading-5 text-vextro-muted">
            {(post.analysis_reasons ?? []).map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </article>
  );
}

// One guide site's rating, listed price and visitor posts for a phone.
// Rendered beside the marketplace review boxes.
function SourceBox({ source }) {
  const [activeKind, setActiveKind] = useState("opinion");
  const [showAll, setShowAll] = useState(false);

  const postsByKind = useMemo(() => {
    const groups = { opinion: [], question: [], advert: [] };
    source.opinions.forEach((post) => {
      (groups[post.opinion_kind] ?? groups.opinion).push(post);
    });
    return groups;
  }, [source.opinions]);

  const active = KINDS.find((kind) => kind.code === activeKind);
  const posts = postsByKind[activeKind];
  const visible = showAll ? posts : posts.slice(0, POSTS_SHOWN);
  const rating = source.rating !== null ? Number(source.rating) : null;

  return (
    <div className="flex h-full flex-col rounded-3xl border border-vextro-border bg-white p-5 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="rounded-full bg-violet-50 px-3 py-1.5 text-[10px] font-black uppercase tracking-[0.14em] text-violet-700">
          {source.source_name}
        </span>
        <a
          className="text-xs font-black text-vextro-primary hover:underline"
          href={source.opinions_url || source.source_url}
          target="_blank"
          rel="noreferrer"
        >
          Open on {source.source_name} ↗
        </a>
      </div>

      <div className="mt-5 grid gap-3 sm:grid-cols-2">
        <div className="rounded-2xl border border-amber-200 bg-amber-50/60 p-4">
          <div className="text-[10px] font-black uppercase tracking-[0.14em] text-amber-700">
            Visitor rating
          </div>
          {rating !== null && source.rating_count > 0 ? (
            <>
              <div className="mt-2 flex items-end gap-2">
                <strong className="text-3xl font-black text-vextro-ink">
                  {rating.toFixed(1)}
                </strong>
                <span className="pb-1 text-xs font-bold text-vextro-muted">
                  / 5
                </span>
                <span className="pb-1">
                  <Stars value={rating} />
                </span>
              </div>
              <div className="mt-1 text-xs font-bold text-vextro-muted">
                from {source.rating_count.toLocaleString()}{" "}
                {source.rating_count === 1 ? "vote" : "votes"}
              </div>
            </>
          ) : (
            <div className="mt-2 text-sm font-bold text-vextro-muted">
              Not rated yet
            </div>
          )}
        </div>

        <div className="rounded-2xl border border-vextro-border bg-vextro-canvas p-4">
          <div className="text-[10px] font-black uppercase tracking-[0.14em] text-vextro-muted">
            Price on {source.source_name}
          </div>
          <div className="mt-2 text-2xl font-black text-vextro-ink">
            {source.reference_price !== null
              ? formatPrice(source.reference_price)
              : "Not stated"}
          </div>
          <div className="mt-1 text-[11px] leading-5 text-vextro-muted">
            The official price {source.source_name} lists, not a shop offer.
          </div>
        </div>
      </div>

      <div className="mt-6 flex flex-wrap gap-2" role="tablist">
        {KINDS.map((kind) => (
          <button
            key={kind.code}
            type="button"
            role="tab"
            aria-selected={activeKind === kind.code}
            onClick={() => {
              setActiveKind(kind.code);
              setShowAll(false);
            }}
            className={`rounded-full border px-4 py-2 text-xs font-black transition ${
              activeKind === kind.code
                ? "border-vextro-primary bg-vextro-primary text-white"
                : "border-vextro-border bg-white text-vextro-muted hover:text-vextro-ink"
            }`}
          >
            {kind.tab} · {source[kind.countKey] ?? 0}
          </button>
        ))}
      </div>

      {activeKind === "advert" && posts.length > 0 ? (
        <p className="mt-4 rounded-2xl border border-red-100 bg-red-50/60 p-3 text-[11px] leading-5 text-red-800">
          Buy-and-sell posts, kept apart from opinions. Phone numbers were
          removed.
        </p>
      ) : null}

      <div className="mt-4 space-y-3">
        {visible.map((post) => (
          <Post key={post.id} post={post} />
        ))}
      </div>

      {posts.length === 0 ? (
        <p className="mt-4 text-sm text-vextro-muted">{active.empty}</p>
      ) : null}

      {posts.length > POSTS_SHOWN ? (
        <button
          type="button"
          onClick={() => setShowAll((current) => !current)}
          className="mt-4 text-xs font-black text-vextro-primary hover:underline"
        >
          {showAll
            ? "Show fewer"
            : `Show all ${posts.length} ${active.tab.toLowerCase()}`}
        </button>
      ) : null}
    </div>
  );
}

export default SourceBox;
