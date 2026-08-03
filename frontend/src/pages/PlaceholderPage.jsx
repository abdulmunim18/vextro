import { Link } from "react-router-dom";

function PlaceholderPage({
  eyebrow,
  title,
  description,
}) {
  return (
    <section className="relative min-h-[calc(100vh-145px)] overflow-hidden bg-vextro-canvas py-16 sm:py-20">
      <div className="pointer-events-none absolute -left-40 top-10 size-96 rounded-full bg-blue-300/20 blur-3xl" />

      <div className="pointer-events-none absolute -right-40 bottom-0 size-96 rounded-full bg-violet-300/20 blur-3xl" />

      <div className="relative mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="overflow-hidden rounded-3xl border border-vextro-border bg-white shadow-vextro-lg">
          <div className="grid lg:grid-cols-[1fr_0.78fr]">
            <div className="flex min-h-[520px] flex-col justify-center p-7 sm:p-12 lg:p-16">
              <span className="text-xs font-black uppercase tracking-[0.18em] text-vextro-primary">
                {eyebrow}
              </span>

              <h1 className="mt-5 max-w-3xl text-4xl font-black leading-[1.03] tracking-[-0.05em] text-vextro-ink sm:text-5xl lg:text-6xl">
                {title}
              </h1>

              <p className="mt-6 max-w-2xl text-sm leading-7 text-vextro-muted sm:text-base">
                {description}
              </p>

              <div className="mt-9 flex flex-col gap-3 sm:flex-row">
                <Link
                  className="inline-flex min-h-12 items-center justify-center rounded-xl bg-vextro-primary px-6 text-sm font-black text-white shadow-lg shadow-blue-500/20 transition hover:-translate-y-0.5 hover:bg-vextro-primary-dark"
                  to="/products"
                >
                  Browse Products
                </Link>

                <Link
                  className="inline-flex min-h-12 items-center justify-center rounded-xl border border-vextro-border bg-white px-6 text-sm font-black text-vextro-ink transition hover:border-blue-200 hover:bg-blue-50"
                  to="/"
                >
                  Return Home
                </Link>
              </div>

              <div className="mt-10 flex items-center gap-3 rounded-2xl border border-blue-100 bg-blue-50/70 p-4">
                <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-vextro-primary text-sm font-black text-white">
                  V
                </span>

                <div>
                  <strong className="block text-sm font-black text-vextro-ink">
                    Module foundation ready
                  </strong>

                  <p className="mt-1 text-xs leading-5 text-vextro-muted">
                    Authentication, routing and role permissions
                    are already connected.
                  </p>
                </div>
              </div>
            </div>

            <div className="relative hidden overflow-hidden bg-gradient-to-br from-vextro-primary-dark via-vextro-primary to-violet-700 p-12 text-white lg:flex lg:flex-col lg:justify-center">
              <div className="pointer-events-none absolute -right-24 -top-24 size-72 rounded-full bg-white/10" />

              <div className="pointer-events-none absolute -bottom-28 -left-28 size-80 rounded-full border-[55px] border-white/5" />

              <div className="relative">
                <span className="inline-flex rounded-full border border-white/20 bg-white/10 px-4 py-2 text-xs font-black uppercase tracking-[0.16em] text-blue-100">
                  Development Status
                </span>

                <h2 className="mt-7 text-3xl font-black tracking-[-0.04em]">
                  This VEXTRO module is being connected next.
                </h2>

                <div className="mt-9 grid gap-4">
                  {[
                    "Responsive Tailwind interface",
                    "FastAPI data integration",
                    "Loading and error states",
                    "Role-based access protection",
                  ].map((item) => (
                    <div
                      className="flex items-center gap-3 rounded-2xl border border-white/15 bg-white/10 p-4 backdrop-blur-sm"
                      key={item}
                    >
                      <span className="grid size-7 shrink-0 place-items-center rounded-full bg-emerald-400/20 text-sm text-emerald-200">
                        ✓
                      </span>

                      <span className="text-sm font-semibold text-white/90">
                        {item}
                      </span>
                    </div>
                  ))}
                </div>

                <div className="mt-10 h-2 overflow-hidden rounded-full bg-white/15">
                  <div className="h-full w-2/3 rounded-full bg-gradient-to-r from-emerald-300 to-cyan-300" />
                </div>

                <p className="mt-3 text-xs font-semibold text-blue-100">
                  Core engineering foundation completed
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

export default PlaceholderPage;