import { useState } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import {
  formatCompactPrice,
  formatDateTime,
  formatPrice,
  toFiniteNumber,
} from "../utils/productDisplay";

const platformColors = {
  daraz: "#ea580c",
  priceoye: "#3157d5",
};

const fallbackColors = ["#0fba83", "#7c3aed", "#0891b2", "#db2777"];

const DAY_IN_MS = 24 * 60 * 60 * 1000;

function readPoints(listing) {
  return (Array.isArray(listing.points) ? listing.points : [])
    .map((point) => ({
      timestamp: new Date(point.captured_at).getTime(),
      price: toFiniteNumber(point.price),
      isAvailable: point.is_available !== false,
    }))
    .filter(
      (point) =>
        point.price !== null && Number.isFinite(point.timestamp),
    )
    .sort((first, second) => first.timestamp - second.timestamp);
}

// VEXTRO stores a price only when it changes, so one offer is a handful of
// points and most offers are a single one. Plotted one line per offer, that
// is a scatter of unconnected dots. What a shopper compares is the best
// price each marketplace had at any moment, so that is what is drawn: at
// every moment a price changed, the lowest price on each marketplace, held
// until the next change and carried through to now.
function buildChartModel(history, now) {
  const listings = (
    Array.isArray(history?.listings) ? history.listings : []
  )
    .map((listing) => ({
      platform:
        listing.platform_name || `Platform ${listing.platform_id}`,
      seller: listing.seller_name || null,
      currency: listing.currency || "PKR",
      points: readPoints(listing),
    }))
    .filter((listing) => listing.points.length > 0);

  if (listings.length === 0) {
    return { data: [], series: [], currency: "PKR" };
  }

  const platforms = [
    ...new Set(listings.map((listing) => listing.platform)),
  ].sort();

  const series = platforms.map((platform, index) => ({
    dataKey: `platform_${index}`,
    name: platform,
    color:
      platformColors[platform.toLowerCase()] ||
      fallbackColors[index % fallbackColors.length],
  }));

  const moments = new Set();
  listings.forEach((listing) =>
    listing.points.forEach((point) => moments.add(point.timestamp)),
  );

  const lastChange = Math.max(...moments);
  if (now > lastChange) {
    // The last known price is still the price; draw it up to the present.
    moments.add(now);
  }

  const data = [...moments]
    .sort((first, second) => first - second)
    .map((timestamp) => {
      const row = {
        timestamp,
        fullDate: formatDateTime(new Date(timestamp).toISOString()),
      };

      series.forEach((item) => {
        const known = listings
          .filter((listing) => listing.platform === item.name)
          .map((listing) => {
            const reached = listing.points.filter(
              (point) => point.timestamp <= timestamp,
            );
            const latest = reached[reached.length - 1];

            return latest
              ? { ...latest, seller: listing.seller }
              : null;
          })
          .filter(Boolean);

        // An offer that is out of stock is not the price to beat, unless
        // nothing on the marketplace is in stock at all.
        const inStock = known.filter((offer) => offer.isAvailable);
        const pool = inStock.length > 0 ? inStock : known;

        if (pool.length === 0) {
          return;
        }

        const best = pool.reduce((lowest, offer) =>
          offer.price < lowest.price ? offer : lowest,
        );

        row[item.dataKey] = best.price;
        row[`${item.dataKey}_seller`] = best.seller;
        row[`${item.dataKey}_inStock`] = inStock.length > 0;
      });

      return row;
    });

  return { data, series, currency: listings[0].currency };
}

function PriceHistoryChart({ history }) {
  // Read once: the chart's right-hand edge must not move on every render.
  const [now] = useState(() => Date.now());
  const { data, series, currency } = buildChartModel(history, now);

  if (data.length === 0 || series.length === 0) {
    return (
      <div className="grid min-h-80 place-content-center justify-items-center rounded-2xl border border-dashed border-slate-300 bg-vextro-canvas p-8 text-center">
        <span className="grid size-16 place-items-center rounded-2xl bg-white text-3xl shadow-sm">
          📈
        </span>

        <h3 className="mt-5 text-xl font-black text-vextro-ink">
          Price history unavailable
        </h3>

        <p className="mt-2 max-w-lg text-sm leading-6 text-vextro-muted">
          Historical snapshots will appear here after marketplace
          price observations are collected.
        </p>
      </div>
    );
  }

  const firstMoment = data[0].timestamp;
  const lastMoment = data[data.length - 1].timestamp;
  const spansDays = lastMoment - firstMoment > 1.5 * DAY_IN_MS;

  const tickFormatter = new Intl.DateTimeFormat(
    "en-PK",
    spansDays
      ? { month: "short", day: "numeric" }
      : {
          day: "numeric",
          month: "short",
          hour: "numeric",
          minute: "2-digit",
        },
  );

  return (
    <div>
      <p className="mb-3 text-xs leading-5 text-vextro-muted">
        The lowest price on each marketplace over time. A price holds
        until VEXTRO sees it change, so flat stretches mean no change.
      </p>

      <div className="h-[390px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart
            data={data}
            margin={{
              top: 20,
              right: 24,
              bottom: 10,
              left: 10,
            }}
          >
            <CartesianGrid
              stroke="#e5eaf2"
              strokeDasharray="4 4"
              vertical={false}
            />

            <XAxis
              dataKey="timestamp"
              type="number"
              scale="time"
              domain={[firstMoment, lastMoment]}
              tickFormatter={(value) => tickFormatter.format(value)}
              tick={{
                fill: "#697386",
                fontSize: 11,
              }}
              axisLine={{
                stroke: "#dfe5ef",
              }}
              tickLine={false}
              minTickGap={48}
            />

            <YAxis
              tick={{
                fill: "#697386",
                fontSize: 11,
              }}
              axisLine={false}
              tickLine={false}
              width={65}
              tickFormatter={formatCompactPrice}
              domain={["auto", "auto"]}
            />

            <Tooltip
              labelFormatter={(_, payload) =>
                payload?.[0]?.payload?.fullDate || "Price snapshot"
              }
              formatter={(value, name, entry) => {
                const seller =
                  entry?.payload?.[`${entry.dataKey}_seller`];
                const inStock =
                  entry?.payload?.[`${entry.dataKey}_inStock`];

                return [
                  [
                    formatPrice(value, currency),
                    seller,
                    inStock === false ? "out of stock" : null,
                  ]
                    .filter(Boolean)
                    .join(" · "),
                  `Lowest on ${name}`,
                ];
              }}
              contentStyle={{
                borderRadius: "16px",
                border: "1px solid #dfe5ef",
                boxShadow: "0 18px 45px rgba(23, 32, 51, 0.12)",
              }}
            />

            <Legend
              wrapperStyle={{
                paddingTop: "18px",
                fontSize: "12px",
              }}
            />

            {series.map((item) => (
              <Line
                key={item.dataKey}
                type="stepAfter"
                dataKey={item.dataKey}
                name={item.name}
                stroke={item.color}
                strokeWidth={3}
                dot={{
                  r: 3,
                  fill: "#ffffff",
                  strokeWidth: 2,
                }}
                activeDot={{
                  r: 6,
                }}
                connectNulls
                isAnimationActive={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export default PriceHistoryChart;
