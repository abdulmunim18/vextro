import { useState } from "react";
import { Link } from "react-router-dom";

import { requestPasswordReset } from "../services/authService";
import { getApiErrorMessage } from "../utils/apiError";

function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const response = await requestPasswordReset(email.trim().toLowerCase());
      setMessage(response.message);
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, "Unable to request a reset link."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="min-h-[calc(100vh-145px)] bg-vextro-canvas px-4 py-16">
      <div className="mx-auto max-w-lg rounded-3xl border border-vextro-border bg-white p-7 shadow-vextro-lg sm:p-10">
        <span className="text-xs font-black uppercase tracking-[0.18em] text-vextro-primary">Account recovery</span>
        <h1 className="mt-3 text-4xl font-black tracking-tight text-vextro-ink">Forgot password?</h1>
        <p className="mt-4 text-sm leading-7 text-vextro-muted">Enter your account email and we’ll send a secure, single-use reset link.</p>
        {message ? <div className="mt-5 rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm font-semibold text-emerald-700" role="status">{message}</div> : null}
        {error ? <div className="mt-5 rounded-xl border border-red-200 bg-red-50 p-3 text-sm font-semibold text-red-700" role="alert">{error}</div> : null}
        <form className="mt-7 grid gap-5" onSubmit={handleSubmit}>
          <label className="grid gap-2 text-sm font-bold text-vextro-ink">Email address
            <input className="min-h-13 rounded-xl border border-vextro-border px-4 outline-none focus:border-vextro-primary" type="email" value={email} onChange={(event) => setEmail(event.target.value)} autoComplete="email" required />
          </label>
          <button className="min-h-13 rounded-xl bg-vextro-primary px-5 text-sm font-black text-white disabled:opacity-60" disabled={busy}>{busy ? "Sending..." : "Send reset link"}</button>
        </form>
        <p className="mt-7 text-center text-sm"><Link className="font-black text-vextro-primary" to="/login">Back to login</Link></p>
      </div>
    </section>
  );
}

export default ForgotPasswordPage;
