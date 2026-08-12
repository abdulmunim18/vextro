import {
  Link,
  useLocation,
} from "react-router-dom";

import { useAuth } from "../context/useAuth";

function UnauthorizedPage() {
  const location = useLocation();
  const { user, hasRole } = useAuth();

  const returnPath = hasRole("admin")
    ? "/admin"
    : "/dashboard";

  const attemptedPath =
    location.state?.attemptedPath || "this resource";

  return (
    <section className="relative grid min-h-[calc(100vh-145px)] place-items-center overflow-hidden bg-vextro-canvas px-4 py-16">
      <div className="pointer-events-none absolute -left-40 top-10 size-96 rounded-full bg-red-200/25 blur-3xl" />

      <div className="pointer-events-none absolute -right-40 bottom-0 size-96 rounded-full bg-blue-200/25 blur-3xl" />

      <div className="relative w-full max-w-2xl overflow-hidden rounded-3xl border border-vextro-border bg-white p-7 text-center shadow-vextro-lg sm:p-12">
        <div className="mx-auto grid size-20 place-items-center rounded-3xl bg-red-50 text-3xl shadow-inner">
          🔒
        </div>

        <span className="mt-7 inline-flex rounded-full border border-red-200 bg-red-50 px-4 py-2 text-xs font-black uppercase tracking-[0.18em] text-red-600">
          Access Restricted
        </span>

        <div className="mt-6 text-[clamp(4rem,14vw,8rem)] font-black leading-none tracking-[-0.08em] text-red-100">
          403
        </div>

        <h1 className="-mt-2 text-3xl font-black tracking-[-0.04em] text-vextro-ink sm:text-4xl">
          You cannot access this page
        </h1>

        <p className="mx-auto mt-5 max-w-xl text-sm leading-7 text-vextro-muted sm:text-base">
          Your current account role does not have permission to
          access{" "}
          <strong className="font-bold text-vextro-ink">
            {attemptedPath}
          </strong>
          .
        </p>

        {user?.roles?.length ? (
          <div className="mx-auto mt-7 inline-flex items-center gap-2 rounded-xl border border-vextro-border bg-vextro-canvas px-4 py-3 text-sm text-vextro-muted">
            <span>Current role:</span>

            <strong className="capitalize text-vextro-ink">
              {user.roles.join(", ")}
            </strong>
          </div>
        ) : null}

        <div className="mt-9 flex flex-col justify-center gap-3 sm:flex-row">
          <Link
            className="inline-flex min-h-12 items-center justify-center rounded-xl bg-vextro-primary px-6 text-sm font-black text-white shadow-lg shadow-blue-500/20 transition hover:-translate-y-0.5 hover:bg-vextro-primary-dark"
            to={returnPath}
          >
            Return to Dashboard
          </Link>

          <Link
            className="inline-flex min-h-12 items-center justify-center rounded-xl border border-vextro-border bg-white px-6 text-sm font-black text-vextro-ink transition hover:border-blue-200 hover:bg-blue-50"
            to="/products"
          >
            Browse Products
          </Link>
        </div>
      </div>
    </section>
  );
}

export default UnauthorizedPage;
