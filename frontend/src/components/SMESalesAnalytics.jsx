import {
  useCallback,
  useEffect,
  useState,
} from "react";

import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { getSalesAnalytics } from "../services/smeService";
import { getApiErrorMessage } from "../utils/apiError";


const EMPTY_SUMMARY = {
  total_revenue: 0,
  total_units_sold: 0,
  total_sales_records: 0,
  average_selling_price: 0,
  products_sold: 0,
};


const formatMoney = (
  value,
  currency = "PKR",
) => {
  const numericValue = Number(value ?? 0);

  return new Intl.NumberFormat(
    "en-PK",
    {
      style: "currency",
      currency,
      maximumFractionDigits: 2,
    },
  ).format(
    Number.isFinite(numericValue)
      ? numericValue
      : 0,
  );
};


const formatNumber = (value) => {
  const numericValue = Number(value ?? 0);

  return new Intl.NumberFormat(
    "en-PK",
  ).format(
    Number.isFinite(numericValue)
      ? numericValue
      : 0,
  );
};


const formatChartDate = (value) => {
  if (!value) {
    return "";
  }

  const dateValue = new Date(
    `${value}T00:00:00`,
  );

  if (Number.isNaN(dateValue.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat(
    "en-PK",
    {
      day: "2-digit",
      month: "short",
    },
  ).format(dateValue);
};


const SummaryCard = ({
  label,
  value,
  description,
}) => (
  <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
    <p className="text-sm font-medium text-slate-500">
      {label}
    </p>

    <p className="mt-2 text-2xl font-bold tracking-tight text-slate-900">
      {value}
    </p>

    <p className="mt-2 text-xs leading-5 text-slate-500">
      {description}
    </p>
  </article>
);


function SMESalesAnalytics({
  organizationId,
  organizationName,
}) {
  const [analytics, setAnalytics] = useState(null);

  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");

  const [appliedStartDate, setAppliedStartDate] =
    useState("");

  const [appliedEndDate, setAppliedEndDate] =
    useState("");

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");


  const loadAnalytics = useCallback(
    async (
      requestedStartDate = "",
      requestedEndDate = "",
    ) => {
      if (!organizationId) {
        return;
      }

      setLoading(true);
      setError("");

      try {
        const params = {};

        if (requestedStartDate) {
          params.start_date = requestedStartDate;
        }

        if (requestedEndDate) {
          params.end_date = requestedEndDate;
        }

        const data = await getSalesAnalytics(
          organizationId,
          params,
        );

        setAnalytics(data);
      } catch (requestError) {
        setError(
          getApiErrorMessage(
            requestError,
            "Sales analytics could not be loaded.",
          ),
        );
      } finally {
        setLoading(false);
      }
    },
    [
      organizationId,
    ],
  );


  useEffect(() => {
    const loadTimeoutId = window.setTimeout(
      () => {
        setAnalytics(null);

        setStartDate("");
        setEndDate("");

        setAppliedStartDate("");
        setAppliedEndDate("");

        loadAnalytics(
          "",
          "",
        );
      },
      0,
    );

    return () => {
      window.clearTimeout(loadTimeoutId);
    };
  }, [
    organizationId,
    loadAnalytics,
  ]);


  const handleApplyFilters = async (event) => {
    event.preventDefault();

    if (
      startDate
      && endDate
      && startDate > endDate
    ) {
      setError(
        "Start date cannot be later than end date.",
      );

      return;
    }

    setError("");

    setAppliedStartDate(startDate);
    setAppliedEndDate(endDate);

    await loadAnalytics(
      startDate,
      endDate,
    );
  };


  const handleResetFilters = async () => {
    setStartDate("");
    setEndDate("");

    setAppliedStartDate("");
    setAppliedEndDate("");

    setError("");

    await loadAnalytics(
      "",
      "",
    );
  };


  const handleRefresh = async () => {
    await loadAnalytics(
      appliedStartDate,
      appliedEndDate,
    );
  };


  const summary = (
    analytics?.summary
    ?? EMPTY_SUMMARY
  );


  const currency = (
    analytics?.currency
    ?? "PKR"
  );


  const revenueTrend = (
    analytics?.revenue_trend
    ?? []
  ).map((item) => ({
    sale_date: item.sale_date,

    revenue: Number(
      item.revenue ?? 0,
    ),

    units_sold: Number(
      item.units_sold ?? 0,
    ),

    sales_records: Number(
      item.sales_records ?? 0,
    ),
  }));
  const productPerformance = (
  analytics?.product_performance
  ?? []
).map((item) => ({
  business_product_id:
    item.business_product_id,

  product_name:
    item.product_name
    ?? "Unnamed Product",

  sku:
    item.sku
    ?? "—",

  revenue: Number(
    item.revenue ?? 0,
  ),

  units_sold: Number(
    item.units_sold ?? 0,
  ),

  sales_records: Number(
    item.sales_records ?? 0,
  ),

  average_selling_price: Number(
    item.average_selling_price ?? 0,
  ),
}));

const totalProductRevenue =
  productPerformance.reduce(
    (total, product) => (
      total + product.revenue
    ),
    0,
  );


  const hasAppliedFilters = Boolean(
    appliedStartDate
    || appliedEndDate,
  );


  return (
    <section className="rounded-3xl border border-slate-200 bg-slate-50 p-5 sm:p-6">

      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">

        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
            Business Intelligence
          </p>

          <h2 className="mt-2 text-2xl font-bold tracking-tight text-slate-950">
            Sales Analytics
          </h2>

          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
            Track sales performance, revenue,
            units sold, and product activity
            using your imported sales data.
          </p>

          {organizationName ? (
            <p className="mt-2 text-sm font-medium text-slate-700">
              Organization: {organizationName}
            </p>
          ) : null}
        </div>


        <button
          type="button"
          onClick={handleRefresh}
          disabled={loading}
          className="inline-flex min-h-10 items-center justify-center rounded-xl border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {loading
            ? "Refreshing..."
            : "Refresh"}
        </button>

      </div>


      <form
        onSubmit={handleApplyFilters}
        className="mt-6 grid gap-4 rounded-2xl border border-slate-200 bg-white p-4 sm:grid-cols-2 lg:grid-cols-[1fr_1fr_auto_auto]"
      >

        <label className="flex flex-col gap-2">
          <span className="text-sm font-semibold text-slate-700">
            Start date
          </span>

          <input
            type="date"
            value={startDate}
            onChange={(event) => {
              setStartDate(
                event.target.value,
              );
            }}
            className="min-h-11 rounded-xl border border-slate-300 bg-white px-3 text-sm text-slate-900 outline-none transition focus:border-slate-500"
          />
        </label>


        <label className="flex flex-col gap-2">
          <span className="text-sm font-semibold text-slate-700">
            End date
          </span>

          <input
            type="date"
            value={endDate}
            onChange={(event) => {
              setEndDate(
                event.target.value,
              );
            }}
            className="min-h-11 rounded-xl border border-slate-300 bg-white px-3 text-sm text-slate-900 outline-none transition focus:border-slate-500"
          />
        </label>


        <button
          type="submit"
          disabled={loading}
          className="min-h-11 self-end rounded-xl bg-slate-950 px-5 py-2 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {loading
            ? "Applying..."
            : "Apply"}
        </button>


        <button
          type="button"
          onClick={handleResetFilters}
          disabled={loading}
          className="min-h-11 self-end rounded-xl border border-slate-300 bg-white px-5 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-60"
        >
          Reset
        </button>

      </form>


      {hasAppliedFilters ? (
        <div className="mt-4 flex flex-wrap items-center gap-2 text-xs font-medium text-slate-600">

          <span className="rounded-full bg-slate-200 px-3 py-1">
            Filtered period
          </span>

          {appliedStartDate ? (
            <span>
              From: {appliedStartDate}
            </span>
          ) : null}

          {appliedEndDate ? (
            <span>
              To: {appliedEndDate}
            </span>
          ) : null}

        </div>
      ) : null}


      {error ? (
        <div className="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      ) : null}


      <div className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-5">

        <SummaryCard
          label="Total Revenue"
          value={formatMoney(
            summary.total_revenue,
            currency,
          )}
          description="Revenue from accepted sales records."
        />


        <SummaryCard
          label="Units Sold"
          value={formatNumber(
            summary.total_units_sold,
          )}
          description="Total quantity sold in the selected period."
        />


        <SummaryCard
          label="Sales Records"
          value={formatNumber(
            summary.total_sales_records,
          )}
          description="Accepted sales rows included in analytics."
        />


        <SummaryCard
          label="Products Sold"
          value={formatNumber(
            summary.products_sold,
          )}
          description="Unique business products with recorded sales."
        />


        <SummaryCard
          label="Average Selling Price"
          value={formatMoney(
            summary.average_selling_price,
            currency,
          )}
          description="Revenue divided by total units sold."
        />

      </div>


      {analytics
  && summary.total_sales_records > 0 ? (
    <div className="relative mt-6 overflow-hidden rounded-3xl border border-indigo-100 bg-gradient-to-br from-white via-indigo-50/40 to-cyan-50/50 p-5 shadow-sm sm:p-6">

      <div className="pointer-events-none absolute -right-20 -top-20 h-52 w-52 rounded-full bg-violet-200/30 blur-3xl" />

      <div className="pointer-events-none absolute -bottom-24 left-1/3 h-56 w-56 rounded-full bg-cyan-200/30 blur-3xl" />


      <div className="-relative">

        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">

          <div>
            <div className="flex items-center gap-2">

              <span className="inline-flex h-8 w-8 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 text-sm text-white shadow-sm">
                ↗
              </span>

              <p className="text-xs font-bold uppercase tracking-[0.16em] text-indigo-600">
                Revenue Performance
              </p>

            </div>

            <h3 className="mt-3 text-xl font-bold tracking-tight text-slate-950">
              Revenue Trend
            </h3>

            <p className="mt-1 max-w-xl text-sm leading-6 text-slate-500">
              Track how your daily revenue and
              units sold change over time.
            </p>
          </div>


          <div className="flex flex-wrap gap-2">

            <div className="rounded-xl border border-indigo-100 bg-white/80 px-3 py-2 shadow-sm backdrop-blur">
              <div className="flex items-center gap-2">

                <span className="h-2.5 w-2.5 rounded-full bg-indigo-500" />

                <span className="text-xs font-semibold text-slate-600">
                  Revenue
                </span>

              </div>
            </div>


            <div className="rounded-xl border border-cyan-100 bg-white/80 px-3 py-2 shadow-sm backdrop-blur">
              <div className="flex items-center gap-2">

                <span className="h-2.5 w-2.5 rounded-full bg-cyan-500" />

                <span className="text-xs font-semibold text-slate-600">
                  Units Sold
                </span>

              </div>
            </div>


            <div className="rounded-xl border border-slate-200 bg-white/80 px-3 py-2 shadow-sm backdrop-blur">

              <span className="text-xs font-semibold text-slate-500">
                {hasAppliedFilters
                  ? "Filtered period"
                  : "All available sales"}
              </span>

            </div>

          </div>

        </div>


        {revenueTrend.length > 0 ? (

          <div className="mt-6">

            <div className="mb-5 grid gap-3 sm:grid-cols-2">

              <div className="rounded-2xl border border-indigo-100 bg-white/75 p-4 shadow-sm backdrop-blur">

                <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                  Period Revenue
                </p>

                <p className="mt-2 text-xl font-bold text-indigo-700">
                  {formatMoney(
                    summary.total_revenue,
                    currency,
                  )}
                </p>

              </div>


              <div className="rounded-2xl border border-cyan-100 bg-white/75 p-4 shadow-sm backdrop-blur">

                <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                  Units Sold
                </p>

                <p className="mt-2 text-xl font-bold text-cyan-700">
                  {formatNumber(
                    summary.total_units_sold,
                  )}
                </p>

              </div>

            </div>


            <div className="h-[360px] w-full rounded-2xl border border-white/80 bg-white/70 p-3 shadow-inner backdrop-blur sm:p-4">

              <ResponsiveContainer
                width="100%"
                height="100%"
              >

                <ComposedChart
                  data={revenueTrend}
                  margin={{
                    top: 15,
                    right: 12,
                    left: 4,
                    bottom: 5,
                  }}
                >

                  <defs>

                    <linearGradient
                      id="revenueGradient"
                      x1="0"
                      y1="0"
                      x2="0"
                      y2="1"
                    >

                      <stop
                        offset="0%"
                        stopColor="#6366f1"
                        stopOpacity={0.45}
                      />

                      <stop
                        offset="55%"
                        stopColor="#8b5cf6"
                        stopOpacity={0.18}
                      />

                      <stop
                        offset="100%"
                        stopColor="#a5b4fc"
                        stopOpacity={0.02}
                      />

                    </linearGradient>

                  </defs>


                  <CartesianGrid
                    stroke="#e2e8f0"
                    strokeDasharray="5 5"
                    vertical={false}
                  />


                  <XAxis
                    dataKey="sale_date"
                    tickFormatter={formatChartDate}
                    tickLine={false}
                    axisLine={false}
                    fontSize={12}
                    tick={{
                      fill: "#64748b",
                    }}
                    tickMargin={12}
                  />


                  <YAxis
                    yAxisId="revenue"
                    tickFormatter={(value) => (
                      new Intl.NumberFormat(
                        "en-PK",
                        {
                          notation: "compact",
                          maximumFractionDigits: 1,
                        },
                      ).format(value)
                    )}
                    tickLine={false}
                    axisLine={false}
                    fontSize={12}
                    width={58}
                    tick={{
                      fill: "#64748b",
                    }}
                  />


                  <YAxis
                    yAxisId="units"
                    orientation="right"
                    tickFormatter={(value) => (
                      formatNumber(value)
                    )}
                    tickLine={false}
                    axisLine={false}
                    fontSize={12}
                    width={42}
                    tick={{
                      fill: "#0891b2",
                    }}
                    allowDecimals={false}
                  />


                  <Tooltip
                    cursor={{
                      stroke: "#c7d2fe",
                      strokeWidth: 1,
                      strokeDasharray: "4 4",
                    }}
                    labelFormatter={(value) => (
                      `Date: ${formatChartDate(value)}`
                    )}
                    formatter={(
                      value,
                      name,
                    ) => {
                      if (name === "Revenue") {
                        return [
                          formatMoney(
                            value,
                            currency,
                          ),
                          "Revenue",
                        ];
                      }

                      return [
                        `${formatNumber(value)} units`,
                        "Units Sold",
                      ];
                    }}
                    contentStyle={{
                      borderRadius: "16px",
                      border:
                        "1px solid #e0e7ff",
                      background:
                        "rgba(255, 255, 255, 0.96)",
                      boxShadow:
                        "0 18px 40px rgba(15, 23, 42, 0.12)",
                      padding: "12px 14px",
                    }}
                    labelStyle={{
                      color: "#475569",
                      fontWeight: 700,
                      marginBottom: "6px",
                    }}
                  />


                  <Area
                    yAxisId="revenue"
                    type="monotone"
                    dataKey="revenue"
                    name="Revenue"
                    stroke="#6366f1"
                    strokeWidth={3}
                    fill="url(#revenueGradient)"
                    activeDot={{
                      r: 7,
                      fill: "#6366f1",
                      stroke: "#ffffff",
                      strokeWidth: 3,
                    }}
                    dot={{
                      r: 4,
                      fill: "#6366f1",
                      stroke: "#ffffff",
                      strokeWidth: 2,
                    }}
                  />


                  <Line
                    yAxisId="units"
                    type="monotone"
                    dataKey="units_sold"
                    name="Units Sold"
                    stroke="#06b6d4"
                    strokeWidth={3}
                    strokeDasharray="7 5"
                    dot={{
                      r: 4,
                      fill: "#06b6d4",
                      stroke: "#ffffff",
                      strokeWidth: 2,
                    }}
                    activeDot={{
                      r: 7,
                      fill: "#06b6d4",
                      stroke: "#ffffff",
                      strokeWidth: 3,
                    }}
                  />

                </ComposedChart>

              </ResponsiveContainer>

            </div>


            <div className="mt-4 flex flex-wrap items-center justify-between gap-3 text-xs text-slate-500">

              <p>
                Hover over any point to inspect
                daily performance.
              </p>

              <p className="font-medium">
                {revenueTrend.length} day
                {revenueTrend.length === 1
                  ? ""
                  : "s"} of sales data
              </p>

            </div>

          </div>

        ) : (

          <div className="mt-6 rounded-2xl border border-dashed border-indigo-200 bg-white/70 p-8 text-center">

            <div className="mx-auto flex h-11 w-11 items-center justify-center rounded-2xl bg-indigo-100 text-lg text-indigo-600">
              ↗
            </div>

            <p className="mt-3 font-semibold text-slate-800">
              No revenue trend available
            </p>

            <p className="mt-1 text-sm text-slate-500">
              Try changing the selected date
              range.
            </p>

          </div>

        )}

      </div>

    </div>
  ) : null}

  {analytics
  && summary.total_sales_records > 0 ? (
    <div className="mt-6 overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm">

      <div className="flex flex-col gap-3 border-b border-slate-200 bg-gradient-to-r from-slate-50 via-white to-violet-50/50 p-5 sm:flex-row sm:items-center sm:justify-between sm:p-6">

        <div>
          <p className="text-xs font-bold uppercase tracking-[0.16em] text-violet-600">
            Product Intelligence
          </p>

          <h3 className="mt-2 text-xl font-bold tracking-tight text-slate-950">
            Product Performance
          </h3>

          <p className="mt-1 text-sm text-slate-500">
            Compare revenue, units sold,
            and selling performance across
            your products.
          </p>
        </div>


        <div className="rounded-xl border border-violet-100 bg-violet-50 px-4 py-2">

          <p className="text-xs font-medium text-violet-600">
            Products with sales
          </p>

          <p className="mt-1 text-lg font-bold text-violet-900">
            {formatNumber(
              productPerformance.length,
            )}
          </p>

        </div>

      </div>


      {productPerformance.length > 0 ? (

        <div className="overflow-x-auto">

          <table className="min-w-[950px] w-full">

            <thead className="bg-slate-50">

              <tr className="border-b border-slate-200">

                <th className="px-5 py-4 text-left text-xs font-bold uppercase tracking-wider text-slate-500">
                  Rank
                </th>

                <th className="px-5 py-4 text-left text-xs font-bold uppercase tracking-wider text-slate-500">
                  Product
                </th>

                <th className="px-5 py-4 text-right text-xs font-bold uppercase tracking-wider text-slate-500">
                  Revenue
                </th>

                <th className="px-5 py-4 text-right text-xs font-bold uppercase tracking-wider text-slate-500">
                  Units Sold
                </th>

                <th className="px-5 py-4 text-right text-xs font-bold uppercase tracking-wider text-slate-500">
                  Records
                </th>

                <th className="px-5 py-4 text-right text-xs font-bold uppercase tracking-wider text-slate-500">
                  Avg. Price
                </th>

                <th className="px-5 py-4 text-left text-xs font-bold uppercase tracking-wider text-slate-500">
                  Revenue Share
                </th>

              </tr>

            </thead>


            <tbody className="divide-y divide-slate-100">

              {productPerformance.map(
                (
                  product,
                  index,
                ) => {
                  const revenueShare = (
                    totalProductRevenue > 0
                      ? (
                        product.revenue
                        / totalProductRevenue
                      ) * 100
                      : 0
                  );

                  return (
                    <tr
                      key={
                        product.business_product_id
                      }
                      className="transition hover:bg-indigo-50/40"
                    >

                      <td className="px-5 py-5">

                        <div
                          className={
                            index === 0
                              ? "flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-amber-400 to-orange-500 text-sm font-bold text-white shadow-sm"
                              : index === 1
                                ? "flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-slate-300 to-slate-500 text-sm font-bold text-white shadow-sm"
                                : index === 2
                                  ? "flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-orange-300 to-amber-600 text-sm font-bold text-white shadow-sm"
                                  : "flex h-9 w-9 items-center justify-center rounded-xl bg-slate-100 text-sm font-bold text-slate-600"
                          }
                        >
                          {index + 1}
                        </div>

                      </td>


                      <td className="px-5 py-5">

                        <div className="max-w-[260px]">

                          <p className="truncate font-semibold text-slate-900">
                            {product.product_name}
                          </p>

                          <div className="mt-1 flex items-center gap-2">

                            <span className="rounded-md bg-slate-100 px-2 py-1 font-mono text-[11px] font-medium text-slate-500">
                              {product.sku}
                            </span>

                            {index === 0 ? (
                              <span className="rounded-full bg-amber-50 px-2 py-1 text-[10px] font-bold uppercase tracking-wide text-amber-700">
                                Top Product
                              </span>
                            ) : null}

                          </div>

                        </div>

                      </td>


                      <td className="px-5 py-5 text-right">

                        <p className="font-bold text-indigo-700">
                          {formatMoney(
                            product.revenue,
                            currency,
                          )}
                        </p>

                      </td>


                      <td className="px-5 py-5 text-right">

                        <p className="font-semibold text-slate-800">
                          {formatNumber(
                            product.units_sold,
                          )}
                        </p>

                        <p className="mt-1 text-xs text-slate-400">
                          units
                        </p>

                      </td>


                      <td className="px-5 py-5 text-right">

                        <p className="font-semibold text-slate-700">
                          {formatNumber(
                            product.sales_records,
                          )}
                        </p>

                      </td>


                      <td className="px-5 py-5 text-right">

                        <p className="font-semibold text-slate-800">
                          {formatMoney(
                            product.average_selling_price,
                            currency,
                          )}
                        </p>

                      </td>


                      <td className="px-5 py-5">

                        <div className="min-w-[150px]">

                          <div className="mb-2 flex items-center justify-between gap-3">

                            <span className="text-xs font-semibold text-slate-700">
                              {revenueShare.toFixed(
                                1,
                              )}
                              %
                            </span>

                            <span className="text-[11px] text-slate-400">
                              of revenue
                            </span>

                          </div>


                          <div className="h-2.5 overflow-hidden rounded-full bg-slate-100">

                            <div
                              className="h-full rounded-full bg-gradient-to-r from-indigo-500 via-violet-500 to-fuchsia-500 transition-all duration-500"
                              style={{
                                width:
                                  `${Math.min(
                                    revenueShare,
                                    100,
                                  )}%`,
                              }}
                            />

                          </div>

                        </div>

                      </td>

                    </tr>
                  );
                },
              )}

            </tbody>

          </table>

        </div>

      ) : (

        <div className="p-8 text-center">

          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-violet-100 text-xl text-violet-600">
            ◫
          </div>

          <p className="mt-3 font-semibold text-slate-800">
            No product performance data
          </p>

          <p className="mt-1 text-sm text-slate-500">
            Product analytics will appear
            after sales records are imported.
          </p>

        </div>

      )}

    </div>
  ) : null}


      {loading && !analytics ? (
        <div className="mt-6 rounded-2xl border border-slate-200 bg-white p-6 text-center text-sm text-slate-500">
          Loading sales analytics...
        </div>
      ) : null}


      {!loading
        && analytics
        && summary.total_sales_records === 0 ? (

          <div className="mt-6 rounded-2xl border border-dashed border-slate-300 bg-white p-6 text-center">

            <p className="font-semibold text-slate-800">
              No sales data found
            </p>

            <p className="mt-2 text-sm text-slate-500">
              Import sales CSV data or change the
              selected date range to view analytics.
            </p>

          </div>

        ) : null}

    </section>
  );
}


export default SMESalesAnalytics;