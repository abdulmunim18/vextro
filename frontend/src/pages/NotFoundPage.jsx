import { Link } from "react-router-dom";

function NotFoundPage() {
  return (
    <section className="relative grid min-h-[calc(100vh-145px)] place-items-center overflow-hidden bg-vextro-canvas px-4 py-16">
      <div className="pointer-events-none absolute -left-40 bottom-0 size-96 rounded-full bg-blue-300/20 blur-3xl" />

      <div className="pointer-events-none absolute -right-40 top-0 size-96 rounded-full bg-violet-300/20 blur-3xl" />

      <div className="relative w-full max-w-3xl text-center">
        <div className="relative mx-auto grid size-28 place-items-center">
          <div className="absolute size-28 rotate-6 rounded-[32px] bg-blue-100" />

          <div className="absolute size-24 -rotate-6 rounded-[28px] bg-violet-100" />

          <div className="relative grid size-20 place-items-center rounded-3xl bg-gradient-to-br from-vextro-primary to-violet-600 text-3xl font-black text-white shadow-vextro">
            ?
          </div>
        </div>

        <div className="mt-8 text-[clamp(5rem,18vw,10rem)] font-black leading-none tracking-[-0.09em] text-blue-100">
          404
        </div>

        <span className="mt-2 inline-flex rounded-full border border-blue-200 bg-blue-50 px-4 py-2 text-xs font-black uppercase tracking-[0.18em] text-vextro-primary">
          Page Not Found
        </span>

        <h1 className="mt-6 text-4xl font-black tracking-[-0.05em] text-vextro-ink sm:text-5xl">
          This page does not exist
        </h1>

        <p className="mx-auto mt-5 max-w-xl text-sm leading-7 text-vextro-muted sm:text-base">
          The page may have been removed, renamed or the entered
          address may be incorrect.
        </p>

        <div className="mt-9 flex flex-col justify-center gap-3 sm:flex-row">
          <Link
            className="inline-flex min-h-12 items-center justify-center gap-2 rounded-xl bg-vextro-primary px-6 text-sm font-black text-white shadow-lg shadow-blue-500/20 transition hover:-translate-y-0.5 hover:bg-vextro-primary-dark"
            to="/"
          >
            <span>←</span>
            Return Home
          </Link>

          <Link
            className="inline-flex min-h-12 items-center justify-center rounded-xl border border-vextro-border bg-white px-6 text-sm font-black text-vextro-ink transition hover:border-blue-200 hover:bg-blue-50"
            to="/products"
          >
            Explore Products
          </Link>
        </div>

        <div className="mx-auto mt-12 grid max-w-2xl gap-3 sm:grid-cols-3">
          <Link
            className="rounded-2xl border border-vextro-border bg-white p-4 text-sm font-bold text-vextro-muted transition hover:-translate-y-1 hover:border-blue-200 hover:text-vextro-primary hover:shadow-lg"
            to="/"
          >
            Home
          </Link>

          <Link
            className="rounded-2xl border border-vextro-border bg-white p-4 text-sm font-bold text-vextro-muted transition hover:-translate-y-1 hover:border-blue-200 hover:text-vextro-primary hover:shadow-lg"
            to="/products"
          >
            Products
          </Link>

          <Link
            className="rounded-2xl border border-vextro-border bg-white p-4 text-sm font-bold text-vextro-muted transition hover:-translate-y-1 hover:border-blue-200 hover:text-vextro-primary hover:shadow-lg"
            to="/login"
          >
            Login
          </Link>
        </div>
      </div>
    </section>
  );
}

export default NotFoundPage;