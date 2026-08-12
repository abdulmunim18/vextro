import { useCallback, useEffect, useState } from "react";
import {
  downloadCompetitorReport,
  getCompetitorIntelligence,
} from "../services/smeService";
import { getApiErrorMessage } from "../utils/apiError";
import { formatPrice } from "../utils/productDisplay";

function SMECompetitorIntelligence({ organizationId }) {
  const [data, setData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [downloadFormat, setDownloadFormat] = useState("");
  const [error, setError] = useState("");

  const loadData = useCallback(async () => {
    setIsLoading(true);
    setError("");

    try {
      setData(await getCompetitorIntelligence(organizationId));
    } catch (requestError) {
      setError(getApiErrorMessage(requestError));
    } finally {
      setIsLoading(false);
    }
  }, [organizationId]);

  useEffect(() => {
    const timeoutId = window.setTimeout(loadData, 0);
    return () => window.clearTimeout(timeoutId);
  }, [loadData]);

  async function handleDownload(format) {
    setDownloadFormat(format);
    setError("");

    try {
      const response = await downloadCompetitorReport(
        organizationId,
        format,
      );
      const url = URL.createObjectURL(response.data);
      const link = document.createElement("a");
      link.href = url;
      link.download = `vextro-competitor-report.${format}`;
      link.click();
      URL.revokeObjectURL(url);
    } catch (requestError) {
      setError(getApiErrorMessage(requestError));
    } finally {
      setDownloadFormat("");
    }
  }

  const summary = data?.summary;

  return (
    <section className="mt-8 rounded-3xl border border-slate-200 bg-white p-7 shadow-sm sm:p-9">
      <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <p className="text-xs font-black uppercase tracking-[0.18em] text-violet-600">
            Competitor intelligence
          </p>
          <h2 className="mt-3 text-3xl font-black tracking-tight text-slate-950">
            Price gaps, risk and market position
          </h2>
          <p className="mt-3 max-w-3xl text-sm leading-7 text-slate-600">
            Active watchlist entries are evaluated against your selling price. Market share is explicitly labelled as a price-based estimate.
          </p>
        </div>
        <div className="flex flex-wrap gap-3">
          {[
            ["pdf", "Export PDF"],
            ["xlsx", "Export Excel"],
          ].map(([format, label]) => (
            <button key={format} type="button" onClick={() => handleDownload(format)} disabled={Boolean(downloadFormat)} className="min-h-11 rounded-xl border border-violet-200 bg-violet-50 px-4 text-sm font-black text-violet-700 disabled:opacity-50">
              {downloadFormat === format ? "Preparing..." : label}
            </button>
          ))}
        </div>
      </div>

      {error ? <div className="mt-5 rounded-xl border border-red-200 bg-red-50 p-4 text-sm font-semibold text-red-700" role="alert">{error}</div> : null}
      {isLoading ? <div className="mt-7 h-40 animate-pulse rounded-2xl bg-slate-100" /> : null}

      {!isLoading && summary ? (
        <>
          <div className="mt-7 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
            {[
              ["Competitors", summary.tracked_competitors],
              ["Products", summary.tracked_products],
              ["Average gap", formatPrice(summary.average_price_gap, "PKR")],
              ["At risk", summary.products_at_risk],
              ["Est. own share", summary.estimated_average_market_share_percentage == null ? "N/A" : `${summary.estimated_average_market_share_percentage}%`],
            ].map(([label, value]) => (
              <div key={label} className="rounded-2xl bg-slate-50 p-5">
                <span className="text-xs font-bold text-slate-500">{label}</span>
                <strong className="mt-2 block text-xl font-black text-slate-950">{value}</strong>
              </div>
            ))}
          </div>
          <p className="mt-4 text-xs leading-6 text-slate-500">{summary.estimation_note}</p>

          {data.items.length === 0 ? (
            <div className="mt-7 rounded-2xl border border-dashed border-slate-300 p-8 text-center text-sm text-slate-600">
              Add active competitor listings to generate intelligence.
            </div>
          ) : (
            <div className="mt-7 overflow-x-auto rounded-2xl border border-slate-200">
              <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
                <thead className="bg-slate-950 text-white">
                  <tr>{["Product", "Platform", "Own price", "Competitor", "Gap", "Risk", "Est. share"].map((heading) => <th key={heading} className="px-4 py-3 text-xs font-black uppercase tracking-wide">{heading}</th>)}</tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {data.items.map((item) => (
                    <tr key={item.watchlist_id}>
                      <td className="px-4 py-4 font-bold text-slate-950">{item.own_product_name}</td>
                      <td className="px-4 py-4 text-slate-600">{item.platform_name}<span className="block text-xs">{item.seller_name || "Seller unavailable"}</span></td>
                      <td className="px-4 py-4">{formatPrice(item.own_price, item.currency)}</td>
                      <td className="px-4 py-4">{formatPrice(item.competitor_price, item.currency)}</td>
                      <td className="px-4 py-4 font-bold">{item.price_gap_percentage == null ? "N/A" : `${item.price_gap_percentage}%`}</td>
                      <td className="px-4 py-4"><span className={`rounded-full px-3 py-1 text-xs font-black uppercase ${item.risk_level === "high" ? "bg-red-100 text-red-700" : item.risk_level === "medium" ? "bg-amber-100 text-amber-700" : "bg-emerald-100 text-emerald-700"}`}>{item.risk_level}</span></td>
                      <td className="px-4 py-4">{item.estimated_own_market_share_percentage == null ? "N/A" : `${item.estimated_own_market_share_percentage}%`}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      ) : null}
    </section>
  );
}

export default SMECompetitorIntelligence;
