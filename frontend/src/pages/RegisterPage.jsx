import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useAuth } from "../context/useAuth";
import { getApiErrorMessage } from "../utils/apiError";

function RegisterPage() {
  const navigate = useNavigate();
  const { register } = useAuth();

  const [formData, setFormData] = useState({
    full_name: "",
    email: "",
    account_type: "consumer",
    password: "",
    confirm_password: "",
  });

  const [errorMessage, setErrorMessage] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

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

    if (formData.password !== formData.confirm_password) {
      setErrorMessage("Passwords do not match.");
      return;
    }

    if (formData.password.length < 8) {
      setErrorMessage(
        "Password must contain at least 8 characters.",
      );
      return;
    }

    setIsSubmitting(true);

    try {
      await register({
        full_name: formData.full_name.trim(),
        email: formData.email.trim().toLowerCase(),
        password: formData.password,
        account_type: formData.account_type,
      });

      navigate("/login", {
        replace: true,
        state: {
          message:
            "Account created successfully. Please log in.",
        },
      });
    } catch (error) {
      setErrorMessage(
        getApiErrorMessage(
          error,
          "Unable to create your account.",
        ),
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <section className="relative min-h-[calc(100vh-145px)] overflow-hidden bg-vextro-canvas py-10 sm:py-16 lg:py-20">
      <div className="pointer-events-none absolute -left-32 bottom-0 size-96 rounded-full bg-violet-300/20 blur-3xl" />
      <div className="pointer-events-none absolute -right-32 top-0 size-96 rounded-full bg-emerald-300/20 blur-3xl" />

      <div className="relative mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="grid overflow-hidden rounded-3xl border border-vextro-border bg-white shadow-vextro-lg lg:grid-cols-[0.9fr_1.1fr]">
          <div className="relative overflow-hidden bg-gradient-to-br from-violet-800 via-vextro-primary to-cyan-600 px-7 py-12 text-white sm:px-10 lg:flex lg:min-h-[760px] lg:flex-col lg:justify-center lg:px-14">
            <div className="pointer-events-none absolute -right-24 top-12 size-72 rounded-full bg-white/10 blur-sm" />
            <div className="pointer-events-none absolute -bottom-28 -left-24 size-80 rounded-full border-[55px] border-white/5" />

            <div className="relative">
              <span className="inline-flex rounded-full border border-white/20 bg-white/10 px-4 py-2 text-xs font-black uppercase tracking-[0.18em] text-blue-100">
                Start with VEXTRO
              </span>

              <h1 className="mt-8 max-w-xl text-4xl font-black leading-[1.03] tracking-[-0.05em] sm:text-5xl lg:text-6xl">
                Make every marketplace decision smarter.
              </h1>

              <p className="mt-6 max-w-lg text-sm leading-7 text-blue-100 sm:text-base">
                Create an account to search products, compare
                marketplace listings and receive price-drop
                alerts.
              </p>

              <div className="mt-10 grid gap-4 text-sm font-semibold text-white/90">
                <div className="flex items-center gap-3">
                  <span className="grid size-7 shrink-0 place-items-center rounded-full bg-white/15 text-white">
                    ✓
                  </span>
                  Free consumer comparison account
                </div>

                <div className="flex items-center gap-3">
                  <span className="grid size-7 shrink-0 place-items-center rounded-full bg-white/15 text-white">
                    ✓
                  </span>
                  Dedicated SME intelligence option
                </div>

                <div className="flex items-center gap-3">
                  <span className="grid size-7 shrink-0 place-items-center rounded-full bg-white/15 text-white">
                    ✓
                  </span>
                  Secure role-based access control
                </div>
              </div>

              <div className="mt-12 grid grid-cols-3 gap-3">
                <div className="rounded-2xl border border-white/15 bg-white/10 p-4 backdrop-blur-sm">
                  <strong className="block text-xl font-black">
                    2
                  </strong>
                  <span className="mt-1 block text-[10px] font-bold uppercase tracking-wider text-blue-100">
                    Marketplaces
                  </span>
                </div>

                <div className="rounded-2xl border border-white/15 bg-white/10 p-4 backdrop-blur-sm">
                  <strong className="block text-xl font-black">
                    3
                  </strong>
                  <span className="mt-1 block text-[10px] font-bold uppercase tracking-wider text-blue-100">
                    User Roles
                  </span>
                </div>

                <div className="rounded-2xl border border-white/15 bg-white/10 p-4 backdrop-blur-sm">
                  <strong className="block text-xl font-black">
                    24/7
                  </strong>
                  <span className="mt-1 block text-[10px] font-bold uppercase tracking-wider text-blue-100">
                    Access
                  </span>
                </div>
              </div>
            </div>
          </div>

          <div className="flex flex-col justify-center px-6 py-10 sm:px-10 sm:py-14 lg:px-16">
            <div className="mb-8">
              <span className="text-xs font-black uppercase tracking-[0.18em] text-vextro-primary">
                Create Account
              </span>

              <h2 className="mt-3 text-4xl font-black tracking-[-0.045em] text-vextro-ink sm:text-5xl">
                Join VEXTRO
              </h2>

              <p className="mt-4 text-sm leading-7 text-vextro-muted">
                Enter your information and select the account
                type that matches your needs.
              </p>
            </div>

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
                  htmlFor="register-name"
                >
                  Full name
                </label>

                <input
                  id="register-name"
                  className="min-h-13 w-full rounded-xl border border-vextro-border bg-white px-4 text-sm text-vextro-ink outline-none transition placeholder:text-slate-400 focus:border-vextro-primary focus:ring-4 focus:ring-blue-100"
                  name="full_name"
                  type="text"
                  value={formData.full_name}
                  onChange={handleChange}
                  placeholder="Enter your full name"
                  autoComplete="name"
                  minLength={2}
                  maxLength={120}
                  required
                />
              </div>

              <div className="grid gap-2">
                <label
                  className="text-sm font-bold text-vextro-ink"
                  htmlFor="register-email"
                >
                  Email address
                </label>

                <input
                  id="register-email"
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
                  htmlFor="account-type"
                >
                  Account type
                </label>

                <select
                  id="account-type"
                  className="min-h-13 w-full cursor-pointer rounded-xl border border-vextro-border bg-white px-4 text-sm text-vextro-ink outline-none transition focus:border-vextro-primary focus:ring-4 focus:ring-blue-100"
                  name="account_type"
                  value={formData.account_type}
                  onChange={handleChange}
                >
                  <option value="consumer">
                    Consumer — Compare and track products
                  </option>

                  <option value="sme">
                    SME — Ecommerce business intelligence
                  </option>
                </select>

                <p className="text-xs leading-5 text-vextro-muted">
                  Consumers track products and alerts. SMEs access
                  business intelligence tools.
                </p>
              </div>

              <div className="grid gap-5 sm:grid-cols-2">
                <div className="grid gap-2">
                  <label
                    className="text-sm font-bold text-vextro-ink"
                    htmlFor="register-password"
                  >
                    Password
                  </label>

                  <input
                    id="register-password"
                    className="min-h-13 w-full rounded-xl border border-vextro-border bg-white px-4 text-sm text-vextro-ink outline-none transition placeholder:text-slate-400 focus:border-vextro-primary focus:ring-4 focus:ring-blue-100"
                    name="password"
                    type="password"
                    value={formData.password}
                    onChange={handleChange}
                    placeholder="Minimum 8 characters"
                    autoComplete="new-password"
                    minLength={8}
                    maxLength={128}
                    required
                  />
                </div>

                <div className="grid gap-2">
                  <label
                    className="text-sm font-bold text-vextro-ink"
                    htmlFor="confirm-password"
                  >
                    Confirm password
                  </label>

                  <input
                    id="confirm-password"
                    className="min-h-13 w-full rounded-xl border border-vextro-border bg-white px-4 text-sm text-vextro-ink outline-none transition placeholder:text-slate-400 focus:border-vextro-primary focus:ring-4 focus:ring-blue-100"
                    name="confirm_password"
                    type="password"
                    value={formData.confirm_password}
                    onChange={handleChange}
                    placeholder="Repeat password"
                    autoComplete="new-password"
                    minLength={8}
                    maxLength={128}
                    required
                  />
                </div>
              </div>

              <div className="flex items-start gap-3 rounded-xl bg-blue-50 px-4 py-3 text-xs leading-5 text-blue-700">
                <span className="mt-0.5">ⓘ</span>
                Password must contain at least 8 characters.
              </div>

              <button
                className="mt-1 min-h-13 w-full rounded-xl bg-vextro-primary px-5 text-sm font-black text-white shadow-lg shadow-blue-500/20 transition hover:-translate-y-0.5 hover:bg-vextro-primary-dark hover:shadow-xl disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:translate-y-0"
                type="submit"
                disabled={isSubmitting}
              >
                {isSubmitting
                  ? "Creating account..."
                  : "Create VEXTRO Account"}
              </button>
            </form>

            <p className="mt-7 text-center text-sm text-vextro-muted">
              Already registered?{" "}
              <Link
                className="font-black text-vextro-primary transition hover:text-vextro-primary-dark"
                to="/login"
              >
                Login to your account
              </Link>
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}

export default RegisterPage;
