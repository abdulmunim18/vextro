import { useCallback, useEffect, useState } from "react";
import {
  getWarehouseMetrics,
  getScrapeRuns,
} from "../services/warehouseService";

export default function WarehouseMonitoring() {
  const [metrics, setMetrics] = useState(null);
  const [scrapeRuns, setScrapeRuns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const loadWarehouseData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [mRes, rRes] = await Promise.all([
        getWarehouseMetrics(),
        getScrapeRuns({ limit: 15 }),
      ]);
      setMetrics(mRes);
      setScrapeRuns(rRes || []);
    } catch (err) {
      console.error("Failed to load warehouse metrics:", err);
      setError("Unable to connect to Centralized Data Warehouse API.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const timeoutId = window.setTimeout(loadWarehouseData, 0);
    return () => window.clearTimeout(timeoutId);
  }, [loadWarehouseData]);

  if (loading) {
    return (
      <div className="p-8 text-center text-slate-400">
        <div className="inline-block w-8 h-8 border-4 border-emerald-500 border-t-transparent rounded-full animate-spin mb-3"></div>
        <p className="text-sm font-medium">Connecting to Centralized Data Warehouse...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6 bg-red-900/20 border border-red-500/30 rounded-xl text-red-300">
        <p className="font-semibold">{error}</p>
        <button
          onClick={loadWarehouseData}
          className="mt-3 px-4 py-2 bg-red-600 hover:bg-red-500 text-white rounded-lg text-xs font-semibold"
        >
          Retry Connection
        </button>
      </div>
    );
  }

  const healthStatus = metrics?.data_health?.status || "UNKNOWN";
  const healthIsGood = ["EXCELLENT", "GOOD"].includes(healthStatus);

  return (
    <div className="space-y-6">
      {/* Stat KPI Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="p-5 bg-gradient-to-br from-slate-900 to-slate-950 border border-slate-800 rounded-2xl">
          <div className="text-xs uppercase tracking-wider text-slate-400 font-medium">
            Canonical Products
          </div>
          <div className="text-3xl font-extrabold text-white mt-2">
            {metrics?.canonical_products_count || 0}
          </div>
          <div className="text-xs text-emerald-400 mt-1">
            Normalized Cross-Market Identity
          </div>
        </div>

        <div className="p-5 bg-gradient-to-br from-slate-900 to-slate-950 border border-slate-800 rounded-2xl">
          <div className="text-xs uppercase tracking-wider text-slate-400 font-medium">
            Marketplace Listings
          </div>
          <div className="text-3xl font-extrabold text-white mt-2">
            {metrics?.product_listings_count || 0}
          </div>
          <div className="text-xs text-blue-400 mt-1">
            All stored offers across Daraz, PriceOye & Shophive
          </div>
        </div>

        <div className="p-5 bg-gradient-to-br from-slate-900 to-slate-950 border border-slate-800 rounded-2xl">
          <div className="text-xs uppercase tracking-wider text-slate-400 font-medium">
            Price Observations
          </div>
          <div className="text-3xl font-extrabold text-white mt-2">
            {metrics?.price_history_observations_count || 0}
          </div>
          <div className="text-xs text-purple-400 mt-1">
            Historical Snapshots Logged
          </div>
        </div>

        <div className="p-5 bg-gradient-to-br from-slate-900 to-slate-950 border border-slate-800 rounded-2xl">
          <div className="text-xs uppercase tracking-wider text-slate-400 font-medium">
            Warehouse Health Score
          </div>
          <div className={`text-3xl font-extrabold mt-2 ${healthIsGood ? "text-emerald-400" : "text-amber-400"}`}>
            {metrics?.data_health?.health_score_percentage || 100}%
          </div>
          <div className="text-xs text-slate-400 mt-1">
            Status: <span className={`font-semibold ${healthIsGood ? "text-emerald-300" : "text-amber-300"}`}>{healthStatus}</span>
          </div>
        </div>
      </div>

      {/* Platform Health Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {metrics?.platform_summary?.map((p) => {
          const scrapeSucceeded = p.last_scrape_status === "SUCCESS";
          const scrapeNeverRan = p.last_scrape_status === "NO_RUNS";
          const statusColor = scrapeSucceeded
            ? "text-emerald-400"
            : scrapeNeverRan
              ? "text-slate-400"
              : "text-red-400";
          const dotColor = scrapeSucceeded
            ? "bg-emerald-500"
            : scrapeNeverRan
              ? "bg-slate-500"
              : "bg-red-500";

          return (
          <div
            key={p.id}
            className="p-5 bg-slate-900/90 border border-slate-800 rounded-2xl space-y-3"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className={`w-3 h-3 rounded-full ${dotColor}`}></div>
                <h3 className="font-bold text-white text-base">{p.name} Marketplace</h3>
              </div>
              <span className="text-xs px-2.5 py-1 bg-slate-800 text-slate-300 rounded-lg font-mono">
                {p.domain}
              </span>
            </div>
            <div className="grid grid-cols-3 gap-2 text-xs pt-2 border-t border-slate-800/80">
              <div>
                <span className="text-slate-400 block">Listings</span>
                <span className="font-bold text-white text-sm">{p.listings_count}</span>
              </div>
              <div>
                <span className="text-slate-400 block">Last Scrape Status</span>
                <span className={`font-semibold ${statusColor}`}>
                  {p.last_scrape_status}
                </span>
              </div>
              <div>
                <span className="text-slate-400 block">Items Scraped</span>
                <span className="font-bold text-white text-sm">{p.last_scrape_items}</span>
              </div>
            </div>
            {p.last_scrape_error ? (
              <div className="rounded-lg border border-red-500/20 bg-red-950/30 px-3 py-2 text-[11px] text-red-300">
                Last error: {p.last_scrape_error}
              </div>
            ) : null}
          </div>
          );
        })}
      </div>

      {/* Scrape Run Audit History Log Table */}
      <div className="bg-slate-900/90 border border-slate-800 rounded-2xl overflow-hidden">
        <div className="p-5 border-b border-slate-800 flex items-center justify-between">
          <h3 className="font-bold text-white text-sm">Scrape Run Audit Log</h3>
          <span className="text-xs text-slate-400">
            Showing last {scrapeRuns.length} runs
          </span>
        </div>

        {scrapeRuns.length === 0 ? (
          <div className="p-8 text-center text-xs text-slate-500">
            No scrape execution runs recorded in database yet. Runs will appear automatically when spiders execute.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-300">
              <thead className="bg-slate-950 text-slate-400 uppercase tracking-wider text-[10px]">
                <tr>
                  <th className="p-3.5">Run ID</th>
                  <th className="p-3.5">Platform</th>
                  <th className="p-3.5">Triggered By</th>
                  <th className="p-3.5">Status</th>
                  <th className="p-3.5">Items Scraped</th>
                  <th className="p-3.5">Items Failed</th>
                  <th className="p-3.5">Result / Error</th>
                  <th className="p-3.5">Started At</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 font-mono">
                {scrapeRuns.map((r) => (
                  <tr key={r.id} className="hover:bg-slate-800/40 transition">
                    <td className="p-3.5 font-bold text-white">#{r.id}</td>
                    <td className="p-3.5 font-semibold text-slate-200">{r.platform}</td>
                    <td className="p-3.5 text-slate-400">{r.triggered_by}</td>
                    <td className="p-3.5">
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-bold tracking-wide ${
                          r.status === "SUCCESS"
                            ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                            : r.status === "RUNNING"
                            ? "bg-blue-500/20 text-blue-400 border border-blue-500/30"
                            : "bg-red-500/20 text-red-400 border border-red-500/30"
                        }`}
                      >
                        {r.status}
                      </span>
                    </td>
                    <td className="p-3.5 text-white font-bold">{r.items_scraped}</td>
                    <td className="p-3.5 text-red-400">{r.items_failed}</td>
                    <td className="max-w-sm p-3.5 font-sans text-slate-300">
                      {r.error_message ? (
                        <span className="block whitespace-normal break-words rounded-lg border border-red-500/20 bg-red-950/30 px-3 py-2 text-[11px] leading-5 text-red-300">
                          {r.error_message}
                        </span>
                      ) : (
                        <span className="text-slate-500">
                          {r.status === "SUCCESS"
                            ? "Completed without recorded errors."
                            : "No error detail was recorded."}
                        </span>
                      )}
                    </td>
                    <td className="p-3.5 text-slate-400">
                      {new Date(r.started_at).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
