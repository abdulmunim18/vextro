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

const lineColors = [
  "#3157d5",
  "#0fba83",
  "#7c3aed",
  "#ea580c",
  "#0891b2",
  "#db2777",
];

function buildChartModel(history) {
  const historyListings = Array.isArray(
    history?.listings,
  )
    ? history.listings
    : [];

  const chartRows = new Map();
  const series = [];

  historyListings.forEach(
    (listing, listingIndex) => {
      const dataKey = `listing_${listing.listing_id}`;

      const seriesName = [
        listing.platform_name ||
          `Platform ${listing.platform_id}`,
        listing.seller_name,
      ]
        .filter(Boolean)
        .join(" · ");

      const points = Array.isArray(listing.points)
        ? listing.points
        : [];

      if (points.length === 0) {
        return;
      }

      series.push({
        dataKey,
        name: seriesName,
        color:
          lineColors[listingIndex % lineColors.length],
        currency: listing.currency || "PKR",
      });

      points.forEach((point) => {
        const price = toFiniteNumber(point.price);
        const timestamp = new Date(
          point.captured_at,
        ).getTime();

        if (
          price === null ||
          !Number.isFinite(timestamp)
        ) {
          return;
        }

        const existingRow =
          chartRows.get(timestamp) || {
            timestamp,
            dateLabel: new Intl.DateTimeFormat(
              "en-PK",
              {
                month: "short",
                day: "numeric",
              },
            ).format(timestamp),
            fullDate: formatDateTime(
              point.captured_at,
            ),
          };

        existingRow[dataKey] = price;
        chartRows.set(timestamp, existingRow);
      });
    },
  );

  return {
    data: Array.from(chartRows.values()).sort(
      (firstRow, secondRow) =>
        firstRow.timestamp - secondRow.timestamp,
    ),
    series,
  };
}

function PriceHistoryChart({ history }) {
  const { data, series } = buildChartModel(history);

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

  const defaultCurrency =
    series[0]?.currency || "PKR";

  return (
    <div className="h-[390px] w-full">
      <ResponsiveContainer
        width="100%"
        height="100%"
      >
        <LineChart
          data={data}
          margin={{
            top: 20,
            right: 20,
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
            dataKey="dateLabel"
            tick={{
              fill: "#697386",
              fontSize: 11,
            }}
            axisLine={{
              stroke: "#dfe5ef",
            }}
            tickLine={false}
            minTickGap={28}
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
              payload?.[0]?.payload?.fullDate ||
              "Price snapshot"
            }
            formatter={(value, name) => [
              formatPrice(value, defaultCurrency),
              name,
            ]}
            contentStyle={{
              borderRadius: "16px",
              border: "1px solid #dfe5ef",
              boxShadow:
                "0 18px 45px rgba(23, 32, 51, 0.12)",
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
              type="monotone"
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
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export default PriceHistoryChart;