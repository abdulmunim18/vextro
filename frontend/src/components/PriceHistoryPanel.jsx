import { useMemo, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

function formatPrice(price, currency = "PKR") {
  const numericPrice = Number(price);

  if (!Number.isFinite(numericPrice)) {
    return "Unavailable";
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

function formatCompactPrice(value) {
  const numericValue = Number(value);

  if (!Number.isFinite(numericValue)) {
    return "";
  }

  if (numericValue >= 1000000) {
    return `${(numericValue / 1000000).toFixed(1)}M`;
  }

  if (numericValue >= 1000) {
    return `${Math.round(numericValue / 1000)}K`;
  }

  return numericValue.toString();
}

function formatDate(value) {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "Unknown";
  }

  return new Intl.DateTimeFormat("en-PK", {
    day: "numeric",
    month: "short",
  }).format(date);
}

function PriceTooltip({
  active,
  payload,
  label,
  currency,
}) {
  if (!active || !payload?.length) {
    return null;
  }

  return (
    <div className="rounded-xl border border-vextro-border bg-white p-3 shadow-vextro">
      <span className="block text-[10px] font-bold text-vextro-muted">
        {label}
      </span>

      <strong className="mt-1 block text-sm font-black text-vextro-ink">
        {formatPrice(payload[0]?.value, currency)}
      </strong>
    </div>
  );
}

function PriceHistoryPanel({
  history,
  platformById,
}) {
  const historyListings = Array.isArray(history?.listings)
    ? history.listings
    : [];

  const [selectedListingId, setSelectedListingId] =
    useState(historyListings[0]?.listing_id ?? null);

  const selectedListing =
    historyListings.find(
      (listing) =>
        listing.listing_id === selectedListingId,
    ) || historyListings[0];

  const chartData = useMemo(() => {
    if (!selectedListing?.points) {
      return [];
    }

    return [...selectedListing.points]
      .sort(
        (firstPoint, secondPoint) =>
          new Date(firstPoint.captured_at) -
          new Date(secondPoint.captured_at),
      )
      .map((point) => ({
        capturedAt: point.captured_at,
        date: formatDate(point.captured_at),
        price: Number(point.price),
        available: point.is_available,
      }))
      .filter((point) => Number.isFinite(point.price));
  }, [selectedListing]);

  const statistics = useMemo(() => {
    if (!chartData.length) {
      return null;
    }

    const prices = chartData.map((point) => point.price);
    const firstPrice = prices[0];
    const currentPrice = prices[prices.length - 1];
    const minimumPrice = Math.min(...prices);
    const maximumPrice = Math.max(...prices);

    const averagePrice =
      prices.reduce((total, price) => total + price, 0) /
      prices.length;

    const change = currentPrice - firstPrice;

    const changePercentage =
      firstPrice > 0
        ? (change / firstPrice) * 100
        : 0;

    return {
      currentPrice,
      minimumPrice,
      maximumPrice,
      averagePrice,
      change,
      changePercentage,
    };
  }, [chartData]);

  if (!historyListings.length || history?.total_points === 0) {
    return (
      <div className="grid min-h-80 place-content-center justify-items-center rounded-3xl border border-dashed border-slate-300 bg-white p-8 text-center">
        <span className="grid size-16 place-items-center rounded-2xl bg-blue-50 text-3xl">
          📈
        </span>

        <h3 className="mt-5 text-xl font-black text-vextro-ink">
          Price history is not available yet
        </h3>

        <p className="mt-3 max-w-lg text-sm leading-7 text-vextro-muted">
          Historical snapshots will appear after marketplace
          prices have been collected over multiple refresh cycles.
        </p>
      </div>
    );
  }

  const currency =
    selectedListing?.currency || "PKR";

  const platform =
    platformById[selectedListing?.platform_id];

  const selectedPlatformName =
    selectedListing?.platform_name ||
    platform?.name ||
    `Marketplace #${selectedListing?.platform_id}`;

  return (
    <div className="rounded-3xl border border-vextro-border bg-white p-5 shadow-sm sm:p-7">
      <div className="flex flex-col justify-between gap-5 lg:flex-row lg:items-start">
        <div>
          <span className="text-xs font-black uppercase tracking-[0.16em] text-vextro-primary">
            Historical Intelligence
          </span>

          <h3 className="mt-3 text-2xl font-black tracking-tight text-vextro-ink">
            Marketplace price movement
          </h3>

          <p className="mt-2 text-sm leading-6 text-vextro-muted">
            {history.total_points} snapshots across{" "}
            {history.total_listings} marketplace listing
            {history.total_listings === 1 ? "" : "s"}.
          </p>
        </div>

        {historyListings.length > 1 ? (
          <div className="flex flex-wrap gap-2">
            {historyListings.map((listing) => {
              const listingPlatform =
                platformById[listing.platform_id];

              const platformName =
                listing.platform_name ||
                listingPlatform?.name ||
                `Listing ${listing.listing_id}`;

              const isSelected =
                listing.listing_id ===
                selectedListing?.listing_id;

              return (
                <button
                  className={`rounded-xl px-4 py-2 text-xs font-black transition ${
                    isSelected
                      ? "bg-vextro-primary text-white shadow-lg shadow-blue-500/20"
                      : "border border-vextro-border bg-white text-vextro-muted hover:border-blue-200 hover:bg-blue-50 hover:text-vextro-primary"
                  }`}
                  type="button"
                  key={listing.listing_id}
                  onClick={() =>
                    setSelectedListingId(
                      listing.listing_id,
                    )
                  }
                >
                  {platformName}
                </button>
              );
            })}
          </div>
        ) : null}
      </div>

      <div className="mt-7 rounded-2xl bg-vextro-canvas p-4">
        <span className="text-xs font-black text-vextro-ink">
          {selectedPlatformName}
        </span>

        <p className="mt-1 line-clamp-1 text-xs text-vextro-muted">
          {selectedListing?.listing_title}
        </p>
      </div>

      {statistics ? (
        <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <div className="rounded-2xl border border-vextro-border p-4">
            <span className="text-[10px] font-bold uppercase text-vextro-muted">
              Latest
            </span>

            <strong className="mt-2 block text-lg font-black text-vextro-ink">
              {formatPrice(
                statistics.currentPrice,
                currency,
              )}
            </strong>
          </div>

          <div className="rounded-2xl border border-emerald-200 bg-emerald-50/50 p-4">
            <span className="text-[10px] font-bold uppercase text-emerald-700">
              Historical Low
            </span>

            <strong className="mt-2 block text-lg font-black text-emerald-700">
              {formatPrice(
                statistics.minimumPrice,
                currency,
              )}
            </strong>
          </div>

          <div className="rounded-2xl border border-vextro-border p-4">
            <span className="text-[10px] font-bold uppercase text-vextro-muted">
              Historical High
            </span>

            <strong className="mt-2 block text-lg font-black text-vextro-ink">
              {formatPrice(
                statistics.maximumPrice,
                currency,
              )}
            </strong>
          </div>

          <div className="rounded-2xl border border-vextro-border p-4">
            <span className="text-[10px] font-bold uppercase text-vextro-muted">
              Overall Change
            </span>

            <strong
              className={`mt-2 block text-lg font-black ${
                statistics.change <= 0
                  ? "text-emerald-700"
                  : "text-red-600"
              }`}
            >
              {statistics.change > 0 ? "+" : ""}
              {statistics.changePercentage.toFixed(1)}%
            </strong>
          </div>
        </div>
      ) : null}

      <div className="mt-6 h-80 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart
            data={chartData}
            margin={{
              top: 10,
              right: 15,
              left: 5,
              bottom: 5,
            }}
          >
            <CartesianGrid
              strokeDasharray="4 4"
              vertical={false}
            />

            <XAxis
              dataKey="date"
              tick={{
                fontSize: 11,
              }}
              tickLine={false}
              axisLine={false}
            />

            <YAxis
              tickFormatter={formatCompactPrice}
              tick={{
                fontSize: 11,
              }}
              tickLine={false}
              axisLine={false}
              width={45}
            />

            <Tooltip
              content={
                <PriceTooltip currency={currency} />
              }
            />

            <Line
              type="monotone"
              dataKey="price"
              stroke="#3157d5"
              strokeWidth={3}
              dot={{
                r: 4,
                fill: "#3157d5",
              }}
              activeDot={{
                r: 6,
              }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export default PriceHistoryPanel;