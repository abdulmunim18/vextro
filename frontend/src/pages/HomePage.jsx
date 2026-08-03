import { Link } from "react-router-dom";

import SystemStatus from "../components/SystemStatus";

const intelligenceFeatures = [
  {
    icon: "⌕",
    title: "Product Discovery",
    description:
      "Search normalized products by title, brand or model across supported ecommerce marketplaces.",
  },
  {
    icon: "↔",
    title: "Marketplace Comparison",
    description:
      "Compare Daraz and PriceOye listings using price, seller, rating, warranty and availability.",
  },
  {
    icon: "↗",
    title: "Price Intelligence",
    description:
      "Review historical price changes and receive alerts when products reach your preferred target.",
  },
];

const platformSteps = [
  {
    number: "01",
    title: "Search",
    description:
      "Enter a product, brand or model into the VEXTRO product catalog.",
  },
  {
    number: "02",
    title: "Compare",
    description:
      "Review normalized marketplace listings in one clear comparison experience.",
  },
  {
    number: "03",
    title: "Decide",
    description:
      "Use price history, alerts and intelligence to make a more informed decision.",
  },
];

function HomePage() {
  return (
    <>
      <section className="relative overflow-hidden bg-vextro-canvas">
        <div className="pointer-events-none absolute -left-40 top-24 size-[430px] rounded-full bg-blue-300/20 blur-3xl" />
        <div className="pointer-events-none absolute -right-40 top-10 size-[480px] rounded-full bg-violet-300/20 blur-3xl" />

        <div className="relative mx-auto grid min-h-[720px] max-w-7xl items-center gap-14 px-4 py-20 sm:px-6 lg:grid-cols-[1.05fr_0.95fr] lg:px-8 lg:py-24">
          <div>
            <SystemStatus />

            <div className="mt-8 inline-flex items-center gap-2 rounded-full border border-blue-200 bg-blue-50 px-4 py-2 text-xs font-black uppercase tracking-[0.16em] text-vextro-primary">
              <span className="size-2 rounded-full bg-vextro-primary" />
              AI-Powered Ecommerce Intelligence
            </div>

            <h1 className="mt-7 max-w-3xl text-5xl font-black leading-[0.98] tracking-[-0.06em] text-vextro-ink sm:text-6xl lg:text-7xl">
              Compare smarter.
              <span className="block bg-gradient-to-r from-vextro-primary via-violet-600 to-cyan-500 bg-clip-text text-transparent">
                Buy with confidence.
              </span>
            </h1>

            <p className="mt-7 max-w-2xl text-base leading-8 text-vextro-muted sm:text-lg">
              VEXTRO brings product listings, marketplace prices,
              historical changes and personalized intelligence
              into one clear platform for consumers and SMEs.
            </p>

            <div className="mt-9 flex flex-col gap-3 sm:flex-row">
              <Link
                className="inline-flex min-h-13 items-center justify-center gap-3 rounded-xl bg-vextro-primary px-6 text-sm font-black text-white shadow-lg shadow-blue-500/20 transition hover:-translate-y-0.5 hover:bg-vextro-primary-dark hover:shadow-xl"
                to="/products"
              >
                Explore Products
                <span className="text-lg">→</span>
              </Link>

              <Link
                className="inline-flex min-h-13 items-center justify-center rounded-xl border border-vextro-border bg-white px-6 text-sm font-black text-vextro-ink shadow-sm transition hover:-translate-y-0.5 hover:border-blue-200 hover:bg-blue-50"
                to="/register"
              >
                Create Free Account
              </Link>
            </div>

            <div className="mt-10 flex flex-wrap items-center gap-x-8 gap-y-4 text-xs font-bold text-vextro-muted">
              <span className="flex items-center gap-2">
                <span className="text-emerald-500">✓</span>
                Public product search
              </span>

              <span className="flex items-center gap-2">
                <span className="text-emerald-500">✓</span>
                Cross-platform comparison
              </span>

              <span className="flex items-center gap-2">
                <span className="text-emerald-500">✓</span>
                Personalized alerts
              </span>
            </div>
          </div>

          <div className="relative mx-auto w-full max-w-xl">
            <div className="absolute -inset-7 rounded-[42px] bg-gradient-to-br from-blue-200/40 via-violet-200/30 to-emerald-200/40 blur-2xl" />

            <div className="relative overflow-hidden rounded-[32px] border border-white/80 bg-white/90 p-5 shadow-vextro-lg backdrop-blur-xl sm:p-7">
              <div className="flex items-center justify-between border-b border-vextro-border pb-5">
                <div>
                  <span className="text-[10px] font-black uppercase tracking-[0.18em] text-vextro-muted">
                    Live Comparison Preview
                  </span>

                  <h2 className="mt-2 text-xl font-black tracking-tight text-vextro-ink">
                    Samsung Galaxy Example
                  </h2>
                </div>

                <div className="grid size-11 place-items-center rounded-2xl bg-blue-50 text-xl">
                  📱
                </div>
              </div>

              <div className="mt-6 grid gap-4">
                <div className="rounded-2xl border border-orange-200 bg-orange-50/70 p-5">
                  <div className="flex items-start justify-between gap-5">
                    <div>
                      <span className="inline-flex rounded-full bg-orange-100 px-3 py-1 text-[10px] font-black uppercase tracking-wider text-orange-700">
                        Daraz
                      </span>

                      <p className="mt-3 text-sm font-bold text-vextro-ink">
                        Official Marketplace Seller
                      </p>

                      <div className="mt-2 flex items-center gap-3 text-xs text-vextro-muted">
                        <span>★ 4.5</span>
                        <span>Available</span>
                      </div>
                    </div>

                    <div className="text-right">
                      <span className="text-[10px] font-bold uppercase text-vextro-muted">
                        Current price
                      </span>

                      <strong className="mt-1 block text-xl font-black tracking-tight text-vextro-ink">
                        PKR 109,999
                      </strong>
                    </div>
                  </div>
                </div>

                <div className="relative rounded-2xl border-2 border-emerald-300 bg-emerald-50/70 p-5">
                  <span className="absolute -top-3 right-4 rounded-full bg-emerald-500 px-3 py-1 text-[9px] font-black uppercase tracking-wider text-white shadow-lg shadow-emerald-500/20">
                    Lowest Price
                  </span>

                  <div className="flex items-start justify-between gap-5">
                    <div>
                      <span className="inline-flex rounded-full bg-blue-100 px-3 py-1 text-[10px] font-black uppercase tracking-wider text-blue-700">
                        PriceOye
                      </span>

                      <p className="mt-3 text-sm font-bold text-vextro-ink">
                        Verified Online Retailer
                      </p>

                      <div className="mt-2 flex items-center gap-3 text-xs text-vextro-muted">
                        <span>★ 4.7</span>
                        <span>Available</span>
                      </div>
                    </div>

                    <div className="text-right">
                      <span className="text-[10px] font-bold uppercase text-vextro-muted">
                        Current price
                      </span>

                      <strong className="mt-1 block text-xl font-black tracking-tight text-emerald-700">
                        PKR 104,999
                      </strong>
                    </div>
                  </div>
                </div>
              </div>

              <div className="mt-6 grid grid-cols-3 gap-3">
                <div className="rounded-2xl bg-vextro-canvas p-4 text-center">
                  <strong className="block text-lg font-black text-vextro-ink">
                    2
                  </strong>
                  <span className="mt-1 block text-[9px] font-bold uppercase tracking-wider text-vextro-muted">
                    Platforms
                  </span>
                </div>

                <div className="rounded-2xl bg-vextro-canvas p-4 text-center">
                  <strong className="block text-lg font-black text-emerald-600">
                    5,000
                  </strong>
                  <span className="mt-1 block text-[9px] font-bold uppercase tracking-wider text-vextro-muted">
                    PKR Saved
                  </span>
                </div>

                <div className="rounded-2xl bg-vextro-canvas p-4 text-center">
                  <strong className="block text-lg font-black text-vextro-primary">
                    4.6
                  </strong>
                  <span className="mt-1 block text-[9px] font-bold uppercase tracking-wider text-vextro-muted">
                    Avg. Rating
                  </span>
                </div>
              </div>

              <p className="mt-5 text-center text-[10px] leading-5 text-vextro-muted">
                Preview data demonstrates the final comparison
                experience. Actual catalog results come from the
                VEXTRO API.
              </p>
            </div>
          </div>
        </div>
      </section>

      <section className="border-y border-vextro-border bg-white py-20 sm:py-24">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="mx-auto max-w-3xl text-center">
            <span className="text-xs font-black uppercase tracking-[0.18em] text-vextro-primary">
              Core Intelligence
            </span>

            <h2 className="mt-4 text-4xl font-black tracking-[-0.045em] text-vextro-ink sm:text-5xl">
              Everything needed for a smarter decision
            </h2>

            <p className="mt-5 text-base leading-8 text-vextro-muted">
              VEXTRO separates real products from
              marketplace-specific listings so users can compare
              equivalent offers accurately.
            </p>
          </div>

          <div className="mt-14 grid gap-6 md:grid-cols-3">
            {intelligenceFeatures.map((feature) => (
              <article
                className="group rounded-3xl border border-vextro-border bg-white p-7 shadow-sm transition duration-300 hover:-translate-y-2 hover:border-blue-200 hover:shadow-vextro"
                key={feature.title}
              >
                <div className="grid size-13 place-items-center rounded-2xl bg-blue-50 text-2xl font-black text-vextro-primary transition group-hover:bg-vextro-primary group-hover:text-white">
                  {feature.icon}
                </div>

                <h3 className="mt-7 text-xl font-black tracking-tight text-vextro-ink">
                  {feature.title}
                </h3>

                <p className="mt-3 text-sm leading-7 text-vextro-muted">
                  {feature.description}
                </p>

                <Link
                  className="mt-6 inline-flex items-center gap-2 text-sm font-black text-vextro-primary"
                  to="/products"
                >
                  Learn more
                  <span className="transition group-hover:translate-x-1">
                    →
                  </span>
                </Link>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="bg-vextro-canvas py-20 sm:py-24">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="grid items-center gap-14 lg:grid-cols-[0.85fr_1.15fr]">
            <div>
              <span className="text-xs font-black uppercase tracking-[0.18em] text-vextro-primary">
                Simple Consumer Journey
              </span>

              <h2 className="mt-4 text-4xl font-black tracking-[-0.045em] text-vextro-ink sm:text-5xl">
                From product search to confident decision
              </h2>

              <p className="mt-5 max-w-xl text-base leading-8 text-vextro-muted">
                The complete user journey remains simple while
                VEXTRO performs catalog normalization and price
                intelligence behind the scenes.
              </p>

              <Link
                className="mt-8 inline-flex min-h-12 items-center justify-center rounded-xl bg-vextro-ink px-6 text-sm font-black text-white transition hover:-translate-y-0.5 hover:bg-slate-800"
                to="/products"
              >
                Start Comparing Products
              </Link>
            </div>

            <div className="grid gap-4">
              {platformSteps.map((step) => (
                <article
                  className="flex gap-5 rounded-3xl border border-vextro-border bg-white p-6 shadow-sm transition hover:border-blue-200 hover:shadow-lg"
                  key={step.number}
                >
                  <span className="grid size-12 shrink-0 place-items-center rounded-2xl bg-vextro-primary text-sm font-black text-white shadow-lg shadow-blue-500/20">
                    {step.number}
                  </span>

                  <div>
                    <h3 className="text-lg font-black text-vextro-ink">
                      {step.title}
                    </h3>

                    <p className="mt-2 text-sm leading-7 text-vextro-muted">
                      {step.description}
                    </p>
                  </div>
                </article>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="bg-vextro-ink py-18 text-white sm:py-20">
        <div className="mx-auto flex max-w-7xl flex-col items-start justify-between gap-8 px-4 sm:px-6 lg:flex-row lg:items-center lg:px-8">
          <div>
            <span className="text-xs font-black uppercase tracking-[0.18em] text-blue-300">
              Start Using VEXTRO
            </span>

            <h2 className="mt-3 max-w-2xl text-3xl font-black tracking-[-0.04em] sm:text-4xl">
              Turn scattered marketplace data into one clear
              decision.
            </h2>
          </div>

          <div className="flex w-full flex-col gap-3 sm:w-auto sm:flex-row">
            <Link
              className="inline-flex min-h-12 items-center justify-center rounded-xl bg-white px-6 text-sm font-black text-vextro-ink transition hover:-translate-y-0.5 hover:bg-blue-50"
              to="/products"
            >
              Browse Products
            </Link>

            <Link
              className="inline-flex min-h-12 items-center justify-center rounded-xl border border-white/25 px-6 text-sm font-black text-white transition hover:border-white hover:bg-white/10"
              to="/register"
            >
              Create Account
            </Link>
          </div>
        </div>
      </section>
    </>
  );
}

export default HomePage;