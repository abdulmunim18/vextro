import { useCallback, useEffect, useState } from "react";

import {
  deletePendingProductMatch,
  getPendingProductMatches,
  getProductVariantOptions,
  replayPendingProductMatch,
  resolvePendingProductMatch,
} from "../services/adminService";
import { getApiErrorMessage } from "../utils/apiError";
import { formatDateTime } from "../utils/productDisplay";

const PAGE_SIZE = 20;

function variantLabel(variant) {
  const details = [
    variant.ram_gb ? `${variant.ram_gb} GB RAM` : "",
    variant.storage_gb ? `${variant.storage_gb} GB` : "",
    variant.color || "",
  ].filter(Boolean);
  return `${variant.product_name}${details.length ? ` — ${details.join(" / ")}` : ""} — variant #${variant.id}`;
}

export default function AdminPendingProductMatches({ onSuccess }) {
  const [items, setItems] = useState([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(0);
  const [query, setQuery] = useState("");
  const [appliedQuery, setAppliedQuery] = useState("");
  const [status, setStatus] = useState("pending");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [activeId, setActiveId] = useState(null);
  const [variantQuery, setVariantQuery] = useState("");
  const [variantOptions, setVariantOptions] = useState([]);
  const [selectedVariantId, setSelectedVariantId] = useState("");
  const [processing, setProcessing] = useState(false);
  const [confirmDeleteId, setConfirmDeleteId] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const params = { page, page_size: PAGE_SIZE };
      if (status) params.status = status;
      if (appliedQuery) params.q = appliedQuery;
      const data = await getPendingProductMatches(params);
      setItems(Array.isArray(data?.items) ? data.items : []);
      setTotalPages(Number(data?.total_pages) || 0);
    } catch (requestError) {
      setItems([]);
      setError(getApiErrorMessage(requestError, "Unable to load pending product matches."));
    } finally {
      setLoading(false);
    }
  }, [appliedQuery, page, status]);

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      load();
    }, 0);

    return () => window.clearTimeout(timeoutId);
  }, [load]);

  async function searchVariants(event) {
    event.preventDefault();
    if (variantQuery.trim().length < 2) return;
    setProcessing(true);
    setError("");
    try {
      const data = await getProductVariantOptions(variantQuery.trim());
      setVariantOptions(Array.isArray(data?.items) ? data.items : []);
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, "Unable to search catalog variants."));
    } finally {
      setProcessing(false);
    }
  }

  async function resolve(match) {
    const variantId = Number(selectedVariantId || match.suggested_product_variant_id);
    if (!Number.isInteger(variantId) || variantId < 1) {
      setError("Search for and select a catalog variant first.");
      return;
    }
    setProcessing(true);
    setError("");
    try {
      await resolvePendingProductMatch(match.id, variantId);
      setSelectedVariantId("");
      setVariantOptions([]);
      setActiveId(null);
      onSuccess?.("Product mapping saved. It can now be replayed safely.");
      await load();
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, "Unable to resolve this product match."));
    } finally {
      setProcessing(false);
    }
  }

  async function replay(match) {
    setProcessing(true);
    setError("");
    try {
      const data = await replayPendingProductMatch(match.id);
      onSuccess?.(`Listing replayed successfully (${data?.ingestion?.status || "ingested"}).`);
      await load();
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, "Unable to replay this listing."));
    } finally {
      setProcessing(false);
    }
  }

  async function remove(match) {
    setProcessing(true);
    setError("");
    try {
      await deletePendingProductMatch(match.id);
      setConfirmDeleteId(null);
      if (items.length === 1 && page > 1) {
        setPage((value) => value - 1);
      } else {
        await load();
      }
      onSuccess?.("Pending marketplace item deleted permanently.");
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, "Unable to delete this queue item."));
    } finally {
      setProcessing(false);
    }
  }

  return (
    <section className="mt-8 overflow-hidden rounded-3xl border border-vextro-border bg-white shadow-sm">
      <div className="border-b border-vextro-border p-6 sm:p-8">
        <span className="text-xs font-black uppercase tracking-[0.16em] text-vextro-primary">Acquisition recovery</span>
        <h2 className="mt-2 text-3xl font-black tracking-tight text-vextro-ink">Pending product matches</h2>
        <p className="mt-3 max-w-3xl text-sm leading-7 text-vextro-muted">Unmatched marketplace listings remain here instead of being discarded. Assign the correct catalog variant, then replay the stored listing into ingestion.</p>
        <form className="mt-6 flex flex-col gap-3 sm:flex-row" onSubmit={(event) => { event.preventDefault(); setPage(1); setAppliedQuery(query.trim()); }}>
          <input className="min-h-12 flex-1 rounded-xl border border-vextro-border px-4 text-sm outline-none focus:border-vextro-primary" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search title or external ID" />
          <select className="min-h-12 rounded-xl border border-vextro-border px-4 text-sm font-bold" value={status} onChange={(event) => { setPage(1); setStatus(event.target.value); }}>
            <option value="pending">Pending</option>
            <option value="resolved">Resolved</option>
            <option value="replayed">Replayed</option>
            <option value="">All statuses</option>
          </select>
          <button className="min-h-12 rounded-xl bg-vextro-primary px-6 text-sm font-black text-white" type="submit">Search</button>
        </form>
      </div>

      {error ? <div className="m-6 rounded-xl border border-red-200 bg-red-50 p-4 text-sm font-bold text-red-700" role="alert">{error}</div> : null}
      {loading ? <div className="p-8 text-sm font-bold text-vextro-muted">Loading pending matches...</div> : null}
      {!loading && items.length === 0 ? <div className="p-10 text-center"><strong className="text-lg text-vextro-ink">No matching queue items</strong><p className="mt-2 text-sm text-vextro-muted">No unresolved marketplace products match the selected filter.</p></div> : null}

      {!loading && items.length > 0 ? (
        <div className="divide-y divide-vextro-border">
          {items.map((match) => (
            <article className="p-6 sm:p-8" key={match.id}>
              <div className="flex flex-col justify-between gap-5 lg:flex-row lg:items-start">
                <div className="max-w-3xl">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="rounded-full bg-blue-50 px-3 py-1 text-[10px] font-black uppercase text-vextro-primary">{match.platform_code}</span>
                    <span className="rounded-full bg-amber-50 px-3 py-1 text-[10px] font-black uppercase text-amber-700">{match.status}</span>
                    <span className="text-xs font-bold text-vextro-muted">Confidence {match.match_confidence}%</span>
                  </div>
                  <h3 className="mt-3 text-lg font-black text-vextro-ink">{match.title}</h3>
                  <p className="mt-2 text-xs text-vextro-muted">External ID: {match.external_id} · Updated {formatDateTime(match.updated_at)}</p>
                  <p className="mt-3 text-sm leading-6 text-amber-800">{match.match_reason}</p>
                  {match.assigned_product_name ? <p className="mt-3 rounded-xl bg-emerald-50 p-3 text-sm font-bold text-emerald-800">Assigned: {match.assigned_product_name} — {match.assigned_variant_label}</p> : null}
                </div>
                <div className="flex flex-wrap gap-2">
                  <a className="inline-flex min-h-11 items-center rounded-xl border border-vextro-border px-4 text-xs font-black text-vextro-primary" href={match.product_url} target="_blank" rel="noreferrer">Open source</a>
                  {match.status === "resolved" ? <button className="min-h-11 rounded-xl bg-emerald-600 px-4 text-xs font-black text-white disabled:opacity-50" disabled={processing} type="button" onClick={() => replay(match)}>Replay listing</button> : null}
                  {match.status === "pending" ? <button className="min-h-11 rounded-xl bg-vextro-primary px-4 text-xs font-black text-white" type="button" onClick={() => { setActiveId(activeId === match.id ? null : match.id); setSelectedVariantId(match.suggested_product_variant_id || ""); setVariantOptions([]); setVariantQuery(match.title); }}>Resolve match</button> : null}
                  {confirmDeleteId === match.id ? (
                    <>
                      <button className="min-h-11 rounded-xl bg-red-600 px-4 text-xs font-black text-white disabled:opacity-50" disabled={processing} type="button" onClick={() => remove(match)}>Confirm delete</button>
                      <button className="min-h-11 rounded-xl border border-vextro-border px-4 text-xs font-black text-vextro-muted disabled:opacity-50" disabled={processing} type="button" onClick={() => setConfirmDeleteId(null)}>Cancel</button>
                    </>
                  ) : (
                    <button className="min-h-11 rounded-xl border border-red-200 px-4 text-xs font-black text-red-700 disabled:opacity-50" disabled={processing} type="button" onClick={() => setConfirmDeleteId(match.id)}>Delete</button>
                  )}
                </div>
              </div>

              {activeId === match.id ? (
                <div className="mt-5 rounded-2xl border border-blue-100 bg-blue-50/50 p-5">
                  <form className="flex flex-col gap-3 sm:flex-row" onSubmit={searchVariants}>
                    <input className="min-h-11 flex-1 rounded-xl border border-vextro-border bg-white px-4 text-sm" value={variantQuery} onChange={(event) => setVariantQuery(event.target.value)} placeholder="Search canonical product, model, brand or SKU" />
                    <button className="min-h-11 rounded-xl border border-blue-200 bg-white px-5 text-xs font-black text-vextro-primary" disabled={processing} type="submit">Find variants</button>
                  </form>
                  {match.suggested_product_variant_id ? <p className="mt-3 text-xs font-bold text-vextro-muted">Automatic suggestion: variant #{match.suggested_product_variant_id}</p> : null}
                  {variantOptions.length > 0 ? <select className="mt-3 min-h-12 w-full rounded-xl border border-vextro-border bg-white px-4 text-sm" value={selectedVariantId} onChange={(event) => setSelectedVariantId(event.target.value)}><option value="">Select a variant</option>{variantOptions.map((variant) => <option key={variant.id} value={variant.id}>{variantLabel(variant)}</option>)}</select> : null}
                  <button className="mt-4 min-h-11 rounded-xl bg-vextro-primary px-5 text-xs font-black text-white disabled:opacity-50" disabled={processing || !(selectedVariantId || match.suggested_product_variant_id)} type="button" onClick={() => resolve(match)}>Save mapping</button>
                </div>
              ) : null}
            </article>
          ))}
        </div>
      ) : null}

      {totalPages > 1 ? <div className="flex items-center justify-between border-t border-vextro-border p-5"><button className="rounded-lg border px-4 py-2 text-xs font-black disabled:opacity-40" disabled={page <= 1} onClick={() => setPage((value) => value - 1)} type="button">Previous</button><span className="text-xs font-bold text-vextro-muted">Page {page} of {totalPages}</span><button className="rounded-lg border px-4 py-2 text-xs font-black disabled:opacity-40" disabled={page >= totalPages} onClick={() => setPage((value) => value + 1)} type="button">Next</button></div> : null}
    </section>
  );
}
