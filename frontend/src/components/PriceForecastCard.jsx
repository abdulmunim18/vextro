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

function buildForecastChart(history, forecast) {
  const rows = new Map();

  (history?.listings || []).forEach((listing) => {
    (listing.points || []).forEach((point) => {
      if (!point.is_available) {
        return;
      }

      const price = toFiniteNumber(point.price);
      const date = new Date(point.captured_at);

      if (price === null || Number.isNaN(date.getTime())) {
        return;
      }

      const key = date.toISOString().slice(0, 10);
      const existing = rows.get(key);

      rows.set(key, {
        key,
        timestamp: date.getTime(),
        label: new Intl.DateTimeFormat("en-PK", {
          month: "short",
          day: "numeric",
        }).format(date),
        fullDate: formatDateTime(point.captured_at),
        historical:
          existing?.historical === undefined
            ? price
            : Math.min(existing.historical, price),
      });
    });
  });

  (forecast?.forecast || []).forEach((point) => {
    const price = toFiniteNumber(point.predicted_price);
    const date = new Date(`${point.forecast_date}T00:00:00Z`);

    if (price === null || Number.isNaN(date.getTime())) {
      return;
    }

    const key = point.forecast_date;
    const existing = rows.get(key) || {};

    rows.set(key, {
      ...existing,
      key,
      timestamp: date.getTime(),
      label: new Intl.DateTimeFormat("en-PK", {
        month: "short",
        day: "numeric",
      }).format(date),
      fullDate: new Intl.DateTimeFormat("en-PK", {
        dateStyle: "medium",
      }).format(date),
      predicted: price,
    });
  });

  return Array.from(rows.values()).sort(
    (first, second) => first.timestamp - second.timestamp,
  );
}

function Metric({ label, value, suffix = "" }) {
  return (
    <div className="rounded-xl bg-vextro-canvas p-3 text-center">
      <span className="block text-[9px] font-black uppercase tracking-wide text-vextro-muted">
        {label}
      </span>
      <strong className="mt-1 block text-xs font-black text-vextro-ink">
        {value ?? "Not reported"}
        {value !== null && value !== undefined ? suffix : ""}
      </strong>
    </div>
  );
}

function PriceForecastCard({ history, forecast }) {
  const isAvailable = forecast?.status === "available";
  const currency = forecast?.currency || "PKR";
  const chartData = isAvailable
    ? buildForecastChart(history, forecast)
    : [];
  const firstPrediction = forecast?.forecast?.[0];
  const finalPrediction = forecast?.forecast?.at(-1);

  return (
    <section className="mt-10 rounded-3xl border border-vextro-border bg-white p-6 shadow-sm sm:p-9">
      <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-start">
        <div>
          <span className="text-xs font-black uppercase tracking-[0.18em] text-vextro-primary">
            Price Forecast
          </span>
          <h2 className="mt-3 text-3xl font-black tracking-tight text-vextro-ink">
            Historical vs predicted price
          </h2>
          <p className="mt-3 max-w-2xl text-sm leading-7 text-vextro-muted">
            Forecasts are published by the versioned ML pipeline and
            remain separate from observed marketplace prices.
          </p>
        </div>

        {isAvailable ? (
          <span className="w-fit rounded-full bg-blue-50 px-4 py-2 text-xs font-black capitalize text-vextro-primary">
            {forecast.confidence} confidence
          </span>
        ) : null}
      </div>

      {!isAvailable ? (
        <div className="mt-7 rounded-2xl border border-dashed border-slate-300 bg-vextro-canvas p-7">
          <h3 className="text-lg font-black text-vextro-ink">
            Insufficient forecast data
          </h3>
          <p className="mt-2 text-sm leading-6 text-vextro-muted">
            A validated model output has not been published for this
            product. VEXTRO will not manufacture a prediction.
          </p>
        </div>
      ) : (
        <>
          <div className="mt-7 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            <Metric
              label="First prediction"
              value={formatPrice(firstPrediction?.predicted_price, currency)}
            />
            <Metric
              label="Final prediction"
              value={formatPrice(finalPrediction?.predicted_price, currency)}
            />
            <Metric label="MAE" value={forecast.mae} />
            <Metric label="RMSE" value={forecast.rmse} />
            <Metric label="MAPE" value={forecast.mape} suffix="%" />
          </div>

          <div className="mt-8 h-[390px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData} margin={{ top: 20, right: 20, bottom: 10, left: 10 }}>
                <CartesianGrid stroke="#e5eaf2" strokeDasharray="4 4" vertical={false} />
                <XAxis dataKey="label" tick={{ fill: "#697386", fontSize: 11 }} tickLine={false} minTickGap={24} />
                <YAxis tick={{ fill: "#697386", fontSize: 11 }} tickLine={false} axisLine={false} width={65} tickFormatter={formatCompactPrice} domain={["auto", "auto"]} />
                <Tooltip
                  labelFormatter={(_, payload) => payload?.[0]?.payload?.fullDate || "Price point"}
                  formatter={(value, name) => [formatPrice(value, currency), name]}
                  contentStyle={{ borderRadius: "16px", border: "1px solid #dfe5ef" }}
                />
                <Legend wrapperStyle={{ paddingTop: "18px", fontSize: "12px" }} />
                <Line type="monotone" dataKey="historical" name="Observed lowest price" stroke="#0fba83" strokeWidth={3} dot={{ r: 3 }} connectNulls />
                <Line type="monotone" dataKey="predicted" name="ML forecast" stroke="#3157d5" strokeWidth={3} strokeDasharray="8 5" dot={{ r: 4 }} connectNulls />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div className="mt-7 grid gap-4 lg:grid-cols-2">
            <div className="rounded-2xl bg-vextro-canvas p-5">
              <span className="text-[10px] font-black uppercase tracking-wide text-vextro-muted">Model provenance</span>
              <p className="mt-2 text-sm font-black text-vextro-ink">
                {forecast.model_name} / {forecast.model_version}
              </p>
              <p className="mt-1 text-xs leading-5 text-vextro-muted">
                {forecast.training_observation_count} observations · {forecast.horizon_days}-day horizon · generated {formatDateTime(forecast.generated_at)}
              </p>
            </div>
            <div className="rounded-2xl bg-amber-50 p-5">
              <span className="text-[10px] font-black uppercase tracking-wide text-amber-700">Limitations</span>
              <ul className="mt-2 space-y-1 text-xs leading-5 text-amber-900">
                {(forecast.limitations || []).map((limitation) => (
                  <li key={limitation}>• {limitation}</li>
                ))}
                <li>• Forecasts are estimates, not guaranteed future prices.</li>
              </ul>
            </div>
          </div>
        </>
      )}
    </section>
  );
}

export default PriceForecastCard;
