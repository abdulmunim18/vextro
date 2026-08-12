import { Link } from "react-router-dom";

import { formatPrice } from "../utils/productDisplay";

const suggestionLabels = {
  buy_now: "Buy now",
  wait: "Wait for a better price",
  price_stable: "Price is stable",
  insufficient_data: "More data needed",
};

const suggestionStyles = {
  buy_now: "border-emerald-200 bg-emerald-50 text-emerald-800",
  wait: "border-amber-200 bg-amber-50 text-amber-800",
  price_stable: "border-blue-200 bg-blue-50 text-blue-800",
  insufficient_data: "border-slate-200 bg-slate-50 text-slate-700",
};

function BuyTimeGuidanceCard({ guidance }) {
  if (!guidance) {
    return null;
  }

  return (
    <section className={`mt-8 rounded-3xl border p-7 sm:p-9 ${suggestionStyles[guidance.suggestion] || suggestionStyles.insufficient_data}`}>
      <div className="flex flex-col gap-5 md:flex-row md:items-start md:justify-between">
        <div>
          <p className="text-xs font-black uppercase tracking-[0.18em]">
            {guidance.is_personalized
              ? "Personalized best-time-to-buy guidance"
              : "Best-time-to-buy guidance"}
          </p>
          <h2 className="mt-3 text-3xl font-black tracking-tight">
            {suggestionLabels[guidance.suggestion] || "Price guidance"}
          </h2>
          <p className="mt-3 max-w-2xl text-sm leading-7">
            {guidance.reasons?.[0]}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {guidance.is_personalized ? (
            <span className="rounded-full bg-white/80 px-4 py-2 text-xs font-black uppercase tracking-wide">
              Saved target applied
            </span>
          ) : null}
          <span className="rounded-full bg-white/80 px-4 py-2 text-xs font-black uppercase tracking-wide">
            {guidance.confidence} confidence
          </span>
        </div>
      </div>

      <div className={`mt-7 grid gap-3 sm:grid-cols-2 ${guidance.is_personalized ? "lg:grid-cols-4" : "lg:grid-cols-3"}`}>
        <div className="rounded-2xl bg-white/80 p-4">
          <span className="text-xs font-bold opacity-70">Current low</span>
          <strong className="mt-2 block text-lg font-black">
            {formatPrice(guidance.current_lowest_price, "PKR")}
          </strong>
        </div>
        <div className="rounded-2xl bg-white/80 p-4">
          <span className="text-xs font-bold opacity-70">Observed low</span>
          <strong className="mt-2 block text-lg font-black">
            {formatPrice(guidance.recent_lowest_price, "PKR")}
          </strong>
        </div>
        {guidance.is_personalized ? (
          <div className="rounded-2xl bg-white/80 p-4">
            <span className="text-xs font-bold opacity-70">
              Your target
            </span>
            <strong className="mt-2 block text-lg font-black">
              {formatPrice(
                guidance.target_price,
                guidance.target_currency || "PKR",
              )}
            </strong>
            <span className="mt-1 block text-[11px] font-semibold opacity-70">
              {guidance.alert_target_type === "listing"
                ? "Specific listing alert"
                : "Any marketplace offer"}
            </span>
          </div>
        ) : null}
        <div className="rounded-2xl bg-white/80 p-4">
          <span className="text-xs font-bold opacity-70">Data coverage</span>
          <strong className="mt-2 block text-lg font-black">
            {guidance.observation_count} points / {guidance.coverage_days} days
          </strong>
        </div>
      </div>

      {guidance.is_personalized ? (
        <div className="mt-5 flex flex-col gap-3 rounded-2xl bg-white/70 p-4 text-xs sm:flex-row sm:items-center sm:justify-between">
          <p className="font-bold leading-6">
            {guidance.target_reached === null
              ? "The tracked offer is currently unavailable, so your target cannot be evaluated yet."
              : guidance.target_reached
                ? "Your saved buying target has been reached."
                : `${formatPrice(
                    guidance.target_gap_amount,
                    guidance.target_currency || "PKR",
                  )} (${guidance.target_gap_percentage ?? 0}%) remains before your target.`}
          </p>
          <Link
            className="shrink-0 font-black underline"
            to="/alerts"
          >
            Manage {guidance.active_alert_count} active alert{guidance.active_alert_count === 1 ? "" : "s"}
          </Link>
        </div>
      ) : guidance.personalization_source === "no_active_alert" ? (
        <div className="mt-5 rounded-2xl bg-white/70 p-4 text-xs font-bold leading-6">
          Set a target price above to turn this general signal into guidance based on your own buying preference.
        </div>
      ) : null}

      <p className="mt-5 text-xs leading-6 opacity-75">
        {guidance.limitations?.join(" ")}
      </p>
    </section>
  );
}

export default BuyTimeGuidanceCard;
