import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

const popularSearches = [
  "iPhone 16 Pro Max",
  "Samsung Galaxy S25",
  "AirPods Pro",
  "Gaming laptop",
];

const categoryLinks = [
  { icon: "📱", label: "Smartphones", slug: "smartphones" },
  { icon: "💻", label: "Laptops", slug: "laptops" },
  { icon: "🎧", label: "Audio", slug: "audio" },
  { icon: "⌚", label: "Wearables", slug: "wearables" },
  { icon: "🏠", label: "Home", slug: "home-appliances" },
  { icon: "✨", label: "Beauty", slug: "health-beauty" },
];

const howItWorks = [
  {
    number: "01",
    title: "Search once",
    description:
      "Find a normalized product instead of checking every marketplace separately.",
  },
  {
    number: "02",
    title: "Compare every offer",
    description:
      "Review prices, seller details, availability and ratings side by side.",
  },
  {
    number: "03",
    title: "Buy with confidence",
    description:
      "Use price history and alerts to choose the right store and the right time.",
  },
];

function HomePage() {
  const navigate = useNavigate();
  const [query, setQuery] = useState("");

  function goToSearch(searchQuery) {
    const normalizedQuery = searchQuery.trim();
    const search = normalizedQuery
      ? `?q=${encodeURIComponent(normalizedQuery)}`
      : "";

    navigate(`/products${search}`);
  }

  function handleSearch(event) {
    event.preventDefault();
    goToSearch(query);
  }

  return (
    <>
      <section className="overflow-hidden border-b border-vextro-border bg-white">
        <div className="relative mx-auto grid min-h-[590px] max-w-7xl items-center gap-14 px-4 py-16 sm:px-6 lg:grid-cols-[1.08fr_0.92fr] lg:px-8 lg:py-20">
          <div className="pointer-events-none absolute -right-52 top-10 size-[520px] rounded-full bg-emerald-100/70 blur-3xl" />

          <div className="relative z-10">
            <div className="inline-flex items-center gap-2 rounded-full border border-emerald-200 bg-emerald-50 px-3.5 py-2 text-[11px] font-black uppercase tracking-[0.12em] text-emerald-700">
              <span className="size-2 rounded-full bg-emerald-500" />
              Fresh marketplace intelligence
            </div>

            <h1 className="mt-6 max-w-3xl text-4xl font-black leading-[1.03] tracking-[-0.055em] text-vextro-ink sm:text-5xl lg:text-[3.65rem]">
              Compare prices.
              <span className="block text-vextro-primary">
                Save more. Decide better.
              </span>
            </h1>

            <p className="mt-5 max-w-2xl text-base leading-7 text-vextro-muted sm:text-lg sm:leading-8">
              Search products across Daraz and PriceOye, spot the lowest
              price and track the deals that matter to you.
            </p>

            <form
              className="mt-8 flex max-w-2xl items-center gap-2 rounded-2xl border-2 border-vextro-primary bg-white p-1.5 shadow-[0_12px_35px_rgba(8,121,91,0.12)]"
              onSubmit={handleSearch}
            >
              <label className="sr-only" htmlFor="home-product-search">
                Search products, brands and prices
              </label>

              <svg
                className="ml-3 size-5 shrink-0 text-vextro-muted"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                aria-hidden="true"
              >
                <circle cx="11" cy="11" r="7" />
                <path d="m20 20-3.5-3.5" />
              </svg>

              <input
                id="home-product-search"
                className="min-w-0 flex-1 border-0 bg-transparent px-2 py-3 text-sm text-vextro-ink outline-none placeholder:text-slate-400 sm:text-base"
                type="search"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search products, brands and prices..."
              />

              <button
                className="min-h-12 shrink-0 rounded-xl bg-vextro-primary px-5 text-sm font-black text-white transition hover:bg-vextro-primary-dark sm:px-8"
                type="submit"
              >
                Compare
              </button>
            </form>

            <div className="mt-4 flex max-w-2xl flex-wrap items-center gap-2">
              <span className="mr-1 text-[10px] font-black uppercase tracking-[0.12em] text-vextro-muted">
                Popular
              </span>

              {popularSearches.map((item) => (
                <button
                  key={item}
                  className="rounded-full border border-vextro-border bg-vextro-canvas px-3 py-2 text-xs font-semibold text-vextro-ink transition hover:border-emerald-300 hover:bg-emerald-50 hover:text-vextro-primary"
                  type="button"
                  onClick={() => goToSearch(item)}
                >
                  {item}
                </button>
              ))}
            </div>
          </div>

          <div className="relative z-10 mx-auto w-full max-w-md lg:ml-auto">
            <div className="absolute -left-12 top-8 h-[88%] w-full rounded-[34px] border border-emerald-100 bg-emerald-50/50" />

            <div className="relative rounded-[28px] border border-vextro-border bg-white p-5 shadow-[0_25px_70px_rgba(23,32,51,0.16)] sm:p-6">
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-2 text-[10px] font-black uppercase tracking-[0.14em] text-vextro-primary">
                  <span className="size-2 rounded-full bg-emerald-500" />
                  Live comparison
                </span>
                <span className="text-[10px] font-bold text-vextro-muted">
                  Best available offer
                </span>
              </div>

              <div className="mt-5 flex items-center gap-4">
                <div className="grid size-12 shrink-0 place-items-center rounded-2xl bg-slate-100 text-2xl">
                  🎧
                </div>
                <div>
                  <h2 className="font-black tracking-tight text-vextro-ink">
                    Premium Wireless Earbuds
                  </h2>
                  <p className="mt-1 text-xs text-vextro-muted">
                    Active noise cancellation · USB-C
                  </p>
                </div>
              </div>

              <div className="mt-5 rounded-2xl bg-emerald-50 p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <strong className="text-sm font-black text-emerald-700">
                      ↓ 12% this month
                    </strong>
                    <p className="mt-1 text-[10px] text-vextro-muted">
                      Near its 90-day low
                    </p>
                  </div>

                  <svg className="h-10 w-28" viewBox="0 0 112 40" aria-hidden="true">
                    <path d="M2 8 20 13 38 10 56 20 74 19 92 29 110 32" fill="none" stroke="#0a9b72" strokeWidth="2.5" />
                    <path d="M2 8 20 13 38 10 56 20 74 19 92 29 110 32V40H2Z" fill="rgba(10,155,114,.10)" />
                    <circle cx="110" cy="32" r="3" fill="#0a9b72" />
                  </svg>
                </div>
              </div>

              <div className="mt-4 grid gap-2.5">
                {[
                  { store: "PriceOye", price: "PKR 49,999", best: true },
                  { store: "Daraz", price: "PKR 52,490" },
                ].map((offer) => (
                  <div
                    key={offer.store}
                    className={`flex items-center justify-between rounded-xl border p-3.5 ${
                      offer.best
                        ? "border-emerald-400 bg-emerald-50/70"
                        : "border-vextro-border bg-vextro-canvas"
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <span className="grid size-8 place-items-center rounded-lg bg-white text-[10px] font-black text-vextro-ink shadow-sm">
                        {offer.store.slice(0, 2)}
                      </span>
                      <span className="text-sm font-bold text-vextro-ink">
                        {offer.store}
                      </span>
                      {offer.best ? (
                        <span className="hidden text-[9px] font-black uppercase text-emerald-700 sm:inline">
                          Lowest
                        </span>
                      ) : null}
                    </div>
                    <strong className="text-sm font-black text-vextro-ink">
                      {offer.price}
                    </strong>
                  </div>
                ))}
              </div>

              <div className="mt-4 flex items-center justify-between border-t border-vextro-border pt-4 text-xs">
                <span className="text-vextro-muted">Price-drop tracking ready</span>
                <strong className="text-vextro-primary">You save PKR 2,491</strong>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="border-b border-vextro-border bg-vextro-canvas py-7">
        <div className="mx-auto grid max-w-7xl grid-cols-2 gap-5 px-4 sm:px-6 md:grid-cols-4 lg:px-8">
          {[
            ["2", "Daraz + PriceOye"],
            ["One", "Normalized catalog"],
            ["24/7", "Price-drop monitoring"],
            ["PKR", "Local price intelligence"],
          ].map(([value, label]) => (
            <div key={label} className="text-center">
              <strong className="block text-xl font-black text-vextro-ink">{value}</strong>
              <span className="mt-1 block text-[10px] font-bold uppercase tracking-[0.1em] text-vextro-muted">{label}</span>
            </div>
          ))}
        </div>
      </section>

      <section className="bg-white py-16 sm:py-20">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
            <div>
              <span className="text-xs font-black uppercase tracking-[0.14em] text-vextro-primary">Browse quickly</span>
              <h2 className="mt-3 text-3xl font-black tracking-[-0.04em] text-vextro-ink sm:text-4xl">Shop by category</h2>
            </div>
            <Link className="text-sm font-black text-vextro-primary hover:text-vextro-primary-dark" to="/products">View all products →</Link>
          </div>

          <div className="mt-9 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
            {categoryLinks.map((category) => (
              <Link
                key={category.label}
                className="group rounded-2xl border border-vextro-border bg-white p-5 transition hover:-translate-y-1 hover:border-emerald-300 hover:shadow-lg"
                to={`/products?category=${category.slug}`}
              >
                <span className="grid size-11 place-items-center rounded-xl bg-vextro-canvas text-xl transition group-hover:bg-emerald-50">{category.icon}</span>
                <strong className="mt-4 block text-sm text-vextro-ink">{category.label}</strong>
              </Link>
            ))}
          </div>
        </div>
      </section>

      <section id="how-it-works" className="scroll-mt-36 border-y border-vextro-border bg-vextro-canvas py-16 sm:py-20">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="mx-auto max-w-2xl text-center">
            <span className="text-xs font-black uppercase tracking-[0.14em] text-vextro-primary">Simple by design</span>
            <h2 className="mt-3 text-3xl font-black tracking-[-0.04em] text-vextro-ink sm:text-4xl">From search to the right decision</h2>
            <p className="mt-4 leading-7 text-vextro-muted">VEXTRO organizes scattered marketplace information into one clear buying journey.</p>
          </div>

          <div className="mt-10 grid gap-4 md:grid-cols-3">
            {howItWorks.map((step) => (
              <article key={step.number} className="rounded-2xl border border-vextro-border bg-white p-6 shadow-sm">
                <span className="grid size-10 place-items-center rounded-xl bg-emerald-50 text-xs font-black text-vextro-primary">{step.number}</span>
                <h3 className="mt-5 text-lg font-black text-vextro-ink">{step.title}</h3>
                <p className="mt-3 text-sm leading-6 text-vextro-muted">{step.description}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="bg-vextro-ink py-14 text-white sm:py-16">
        <div className="mx-auto flex max-w-7xl flex-col justify-between gap-7 px-4 sm:px-6 lg:flex-row lg:items-center lg:px-8">
          <div>
            <span className="text-xs font-black uppercase tracking-[0.14em] text-emerald-300">Start comparing today</span>
            <h2 className="mt-3 max-w-2xl text-3xl font-black tracking-[-0.04em] sm:text-4xl">A better price is only one search away.</h2>
          </div>
          <div className="flex flex-col gap-3 sm:flex-row">
            <Link className="inline-flex min-h-12 items-center justify-center rounded-xl bg-vextro-primary px-6 text-sm font-black text-white hover:bg-vextro-primary-dark" to="/products">Browse products</Link>
            <Link className="inline-flex min-h-12 items-center justify-center rounded-xl border border-white/25 px-6 text-sm font-black text-white hover:bg-white/10" to="/register">Create free account</Link>
          </div>
        </div>
      </section>
    </>
  );
}

export default HomePage;
