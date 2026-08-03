import { useState } from "react";
import {
  Link,
  useLocation,
  useNavigate,
} from "react-router-dom";

import { useAuth } from "../context/AuthContext";
import { getApiErrorMessage } from "../utils/apiError";

function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { login } = useAuth();

  const [formData, setFormData] = useState({
    email: "",
    password: "",
  });

  const [errorMessage, setErrorMessage] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const successMessage = location.state?.message || "";

  function handleChange(event) {
    const { name, value } = event.target;

    setFormData((currentData) => ({
      ...currentData,
      [name]: value,
    }));

    setErrorMessage("");
  }

  async function handleSubmit(event) {
    event.preventDefault();

    setErrorMessage("");
    setIsSubmitting(true);

    try {
      const loggedInUser = await login({
        email: formData.email.trim().toLowerCase(),
        password: formData.password,
      });

      const roles = loggedInUser.roles || [];

      const defaultDestination = roles.includes("admin")
        ? "/admin"
        : "/dashboard";

      const destination =
        location.state?.from || defaultDestination;

      navigate(destination, {
        replace: true,
      });
    } catch (error) {
      setErrorMessage(
        getApiErrorMessage(
          error,
          "Unable to log in with these credentials.",
        ),
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <section className="relative min-h-[calc(100vh-145px)] overflow-hidden bg-vextro-canvas py-10 sm:py-16 lg:py-20">
      <div className="pointer-events-none absolute -left-32 top-10 size-80 rounded-full bg-blue-300/20 blur-3xl" />
      <div className="pointer-events-none absolute -right-32 bottom-0 size-96 rounded-full bg-emerald-300/20 blur-3xl" />

      <div className="relative mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="grid overflow-hidden rounded-3xl border border-vextro-border bg-white shadow-vextro-lg lg:grid-cols-[0.9fr_1.1fr]">
          <div className="relative overflow-hidden bg-gradient-to-br from-vextro-primary-dark via-vextro-primary to-violet-700 px-7 py-12 text-white sm:px-10 lg:flex lg:min-h-[650px] lg:flex-col lg:justify-center lg:px-14">
            <div className="pointer-events-none absolute -right-20 -top-20 size-64 rounded-full bg-white/10" />
            <div className="pointer-events-none absolute -bottom-24 -left-24 size-72 rounded-full border-[45px] border-white/5" />

            <div className="relative">
              <span className="inline-flex rounded-full border border-white/20 bg-white/10 px-4 py-2 text-xs font-black uppercase tracking-[0.18em] text-blue-100">
                VEXTRO Intelligence
              </span>

              <h1 className="mt-8 max-w-xl text-4xl font-black leading-[1.03] tracking-[-0.05em] sm:text-5xl lg:text-6xl">
                Welcome back to smarter shopping.
              </h1>

              <p className="mt-6 max-w-lg text-sm leading-7 text-blue-100 sm:text-base">
                Log in to compare marketplace prices, review
                historical changes and manage personalized price
                alerts.
              </p>

              <div className="mt-10 grid gap-4 text-sm font-semibold text-white/90">
                <div className="flex items-center gap-3">
                  <span className="grid size-7 shrink-0 place-items-center rounded-full bg-emerald-400/20 text-emerald-200">
                    ✓
                  </span>
                  Compare Daraz and PriceOye listings
                </div>

                <div className="flex items-center gap-3">
                  <span className="grid size-7 shrink-0 place-items-center rounded-full bg-emerald-400/20 text-emerald-200">
                    ✓
                  </span>
                  Track historical marketplace prices
                </div>

                <div className="flex items-center gap-3">
                  <span className="grid size-7 shrink-0 place-items-center rounded-full bg-emerald-400/20 text-emerald-200">
                    ✓
                  </span>
                  Manage personalized price alerts
                </div>
              </div>
            </div>
          </div>

          <div className="flex flex-col justify-center px-6 py-10 sm:px-10 sm:py-14 lg:px-16">
            <div className="mb-8">
              <span className="text-xs font-black uppercase tracking-[0.18em] text-vextro-primary">
                Welcome Back
              </span>

              <h2 className="mt-3 text-4xl font-black tracking-[-0.045em] text-vextro-ink sm:text-5xl">
                Login to VEXTRO
              </h2>

              <p className="mt-4 text-sm leading-7 text-vextro-muted">
                Enter your account credentials to continue.
              </p>
            </div>

            {successMessage ? (
              <div
                className="mb-6 rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-semibold leading-6 text-emerald-700"
                role="status"
              >
                {successMessage}
              </div>
            ) : null}

            {errorMessage ? (
              <div
                className="mb-6 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-semibold leading-6 text-red-700"
                role="alert"
              >
                {errorMessage}
              </div>
            ) : null}

            <form
              className="grid gap-5"
              onSubmit={handleSubmit}
            >
              <div className="grid gap-2">
                <label
                  className="text-sm font-bold text-vextro-ink"
                  htmlFor="login-email"
                >
                  Email address
                </label>

                <input
                  id="login-email"
                  className="min-h-13 w-full rounded-xl border border-vextro-border bg-white px-4 text-sm text-vextro-ink outline-none transition placeholder:text-slate-400 focus:border-vextro-primary focus:ring-4 focus:ring-blue-100"
                  name="email"
                  type="email"
                  value={formData.email}
                  onChange={handleChange}
                  placeholder="you@example.com"
                  autoComplete="email"
                  required
                />
              </div>

              <div className="grid gap-2">
                <label
                  className="text-sm font-bold text-vextro-ink"
                  htmlFor="login-password"
                >
                  Password
                </label>

                <input
                  id="login-password"
                  className="min-h-13 w-full rounded-xl border border-vextro-border bg-white px-4 text-sm text-vextro-ink outline-none transition placeholder:text-slate-400 focus:border-vextro-primary focus:ring-4 focus:ring-blue-100"
                  name="password"
                  type="password"
                  value={formData.password}
                  onChange={handleChange}
                  placeholder="Enter your password"
                  autoComplete="current-password"
                  required
                />
              </div>

              <button
                className="mt-1 min-h-13 w-full rounded-xl bg-vextro-primary px-5 text-sm font-black text-white shadow-lg shadow-blue-500/20 transition hover:-translate-y-0.5 hover:bg-vextro-primary-dark hover:shadow-xl disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:translate-y-0"
                type="submit"
                disabled={isSubmitting}
              >
                {isSubmitting
                  ? "Logging in..."
                  : "Login to VEXTRO"}
              </button>
            </form>

            <p className="mt-7 text-center text-sm text-vextro-muted">
              New to VEXTRO?{" "}
              <Link
                className="font-black text-vextro-primary transition hover:text-vextro-primary-dark"
                to="/register"
              >
                Create an account
              </Link>
            </p>

            <div className="mt-8 flex items-center justify-center gap-2 border-t border-vextro-border pt-6 text-xs text-vextro-muted">
              <span className="grid size-7 place-items-center rounded-lg bg-blue-50 text-vextro-primary">
                🔒
              </span>
              Secure authentication powered by VEXTRO API
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

export default LoginPage;