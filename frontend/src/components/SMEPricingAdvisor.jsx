import { useCallback, useEffect, useState } from "react";
import {
  getBusinessProducts,
  simulatePricingScenarios,
} from "../services/smeService";
import { getApiErrorMessage } from "../utils/apiError";
import { formatPrice } from "../utils/productDisplay";

function SMEPricingAdvisor({ organizationId }) {
  const [products, setProducts] = useState([]);
  const [productId, setProductId] = useState("");
  const [baselineUnits, setBaselineUnits] = useState("100");
  const [sensitivity, setSensitivity] = useState("1");
  const [result, setResult] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");

  const loadProducts = useCallback(async () => {
    setIsLoading(true);
    setError("");

    try {
      const data = await getBusinessProducts(
        organizationId,
        { page: 1, page_size: 100, is_active: true },
      );
      const items = Array.isArray(data?.items) ? data.items : [];
      setProducts(items);
      setProductId((current) => current || String(items[0]?.id || ""));
    } catch (requestError) {
      setError(getApiErrorMessage(requestError));
    } finally {
      setIsLoading(false);
    }
  }, [organizationId]);

  useEffect(() => {
    const timeoutId = window.setTimeout(loadProducts, 0);
    return () => window.clearTimeout(timeoutId);
  }, [loadProducts]);

  async function handleSubmit(event) {
    event.preventDefault();
    setIsSubmitting(true);
    setError("");

    try {
      setResult(await simulatePricingScenarios(organizationId, {
        business_product_id: Number(productId),
        baseline_units: Number(baselineUnits),
        demand_sensitivity: Number(sensitivity),
      }));
    } catch (requestError) {
      setResult(null);
      setError(getApiErrorMessage(requestError));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <section className="mt-8 overflow-hidden rounded-3xl border border-slate-200 bg-slate-950 text-white shadow-xl">
      <div className="grid lg:grid-cols-[0.8fr_1.2fr]">
        <div className="p-7 sm:p-9">
          <p className="text-xs font-black uppercase tracking-[0.18em] text-blue-300">Dynamic pricing advisor</p>
          <h2 className="mt-3 text-3xl font-black tracking-tight">Simulate before changing price</h2>
          <p className="mt-4 text-sm leading-7 text-slate-300">Compare -5%, unchanged and +5% scenarios using cost, monitored competitor price and an explicit demand-sensitivity assumption.</p>

          <form className="mt-7 space-y-5" onSubmit={handleSubmit}>
            <div>
              <label className="mb-2 block text-sm font-bold" htmlFor="pricing-product">Business product</label>
              <select id="pricing-product" value={productId} onChange={(event) => setProductId(event.target.value)} disabled={isLoading || products.length === 0} className="min-h-12 w-full rounded-xl border border-white/15 bg-white px-4 text-sm font-semibold text-slate-950">
                {products.length === 0 ? <option value="">No products available</option> : null}
                {products.map((product) => <option key={product.id} value={product.id}>{product.name}</option>)}
              </select>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="mb-2 block text-sm font-bold" htmlFor="baseline-units">Expected units</label>
                <input id="baseline-units" type="number" min="1" step="1" value={baselineUnits} onChange={(event) => setBaselineUnits(event.target.value)} className="min-h-12 w-full rounded-xl border border-white/15 px-4 text-sm text-slate-950" />
              </div>
              <div>
                <label className="mb-2 block text-sm font-bold" htmlFor="demand-sensitivity">Sensitivity</label>
                <input id="demand-sensitivity" type="number" min="0" max="5" step="0.1" value={sensitivity} onChange={(event) => setSensitivity(event.target.value)} className="min-h-12 w-full rounded-xl border border-white/15 px-4 text-sm text-slate-950" />
              </div>
            </div>
            {error ? <div className="rounded-xl border border-red-300/30 bg-red-500/10 p-4 text-sm font-semibold text-red-200" role="alert">{error}</div> : null}
            <button type="submit" disabled={isSubmitting || !productId} className="min-h-12 w-full rounded-xl bg-blue-600 px-5 text-sm font-black text-white disabled:opacity-50">{isSubmitting ? "Simulating..." : "Run pricing scenarios"}</button>
          </form>
        </div>

        <div className="bg-slate-50 p-7 text-slate-950 sm:p-9">
          {!result ? (
            <div className="grid min-h-80 place-items-center rounded-2xl border border-dashed border-slate-300 bg-white p-8 text-center text-sm leading-7 text-slate-500">Select a product with cost, selling price and an active competitor, then run the advisory simulation.</div>
          ) : (
            <>
              <p className="text-xs font-black uppercase tracking-[0.18em] text-blue-600">Recommendation</p>
              <h3 className="mt-3 text-2xl font-black">{result.product_name}</h3>
              <p className="mt-3 text-sm leading-7 text-slate-600">{result.recommendation}</p>
              <div className="mt-6 grid gap-4 xl:grid-cols-3">
                {result.scenarios.map((scenario) => (
                  <article key={scenario.price_change_percentage} className={`rounded-2xl border bg-white p-5 ${scenario.price_change_percentage === result.recommended_change_percentage ? "border-blue-500 ring-4 ring-blue-100" : "border-slate-200"}`}>
                    <span className="text-xs font-black uppercase text-slate-500">{Number(scenario.price_change_percentage) > 0 ? "+" : ""}{scenario.price_change_percentage}%</span>
                    <strong className="mt-2 block text-xl font-black">{formatPrice(scenario.proposed_price, result.currency)}</strong>
                    <dl className="mt-4 space-y-2 text-xs">
                      <div className="flex justify-between gap-3"><dt className="text-slate-500">Units</dt><dd className="font-bold">{scenario.expected_units}</dd></div>
                      <div className="flex justify-between gap-3"><dt className="text-slate-500">Gross profit</dt><dd className="font-bold">{formatPrice(scenario.gross_profit, result.currency)}</dd></div>
                      <div className="flex justify-between gap-3"><dt className="text-slate-500">Competitor gap</dt><dd className="font-bold">{scenario.competitor_gap_percentage}%</dd></div>
                    </dl>
                    <span className={`mt-4 inline-flex rounded-full px-3 py-1 text-[10px] font-black uppercase ${scenario.risk_level === "high" ? "bg-red-100 text-red-700" : scenario.risk_level === "medium" ? "bg-amber-100 text-amber-700" : "bg-emerald-100 text-emerald-700"}`}>{scenario.risk_level} risk</span>
                  </article>
                ))}
              </div>
              <p className="mt-5 text-xs leading-6 text-slate-500">{result.disclaimer}</p>
            </>
          )}
        </div>
      </div>
    </section>
  );
}

export default SMEPricingAdvisor;
