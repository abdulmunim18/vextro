import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { resendVerification, verifyEmail } from "../services/authService";
import { getApiErrorMessage } from "../utils/apiError";

function VerifyEmailPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const [email, setEmail] = useState(location.state?.email || "");
  const [otp, setOtp] = useState("");
  const [message, setMessage] = useState(location.state?.message || "Enter the 6-digit code sent to your email.");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await verifyEmail({ email: email.trim().toLowerCase(), otp });
      navigate("/login", { replace: true, state: { message: "Email verified. Your account is ready—please log in." } });
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, "Unable to verify this code."));
    } finally {
      setBusy(false);
    }
  }

  async function handleResend() {
    setBusy(true);
    setError("");
    try {
      const response = await resendVerification(email.trim().toLowerCase());
      setMessage(response.message);
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, "Unable to send another code."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="min-h-[calc(100vh-145px)] bg-vextro-canvas px-4 py-16">
      <div className="mx-auto max-w-lg rounded-3xl border border-vextro-border bg-white p-7 shadow-vextro-lg sm:p-10">
        <span className="text-xs font-black uppercase tracking-[0.18em] text-vextro-primary">Secure signup</span>
        <h1 className="mt-3 text-4xl font-black tracking-tight text-vextro-ink">Verify your email</h1>
        <p className="mt-4 text-sm leading-7 text-vextro-muted">{message}</p>
        {error ? <div className="mt-5 rounded-xl border border-red-200 bg-red-50 p-3 text-sm font-semibold text-red-700" role="alert">{error}</div> : null}
        <form className="mt-7 grid gap-5" onSubmit={handleSubmit}>
          <label className="grid gap-2 text-sm font-bold text-vextro-ink">Email address
            <input className="min-h-13 rounded-xl border border-vextro-border px-4 outline-none focus:border-vextro-primary" type="email" value={email} onChange={(event) => setEmail(event.target.value)} autoComplete="email" required />
          </label>
          <label className="grid gap-2 text-sm font-bold text-vextro-ink">6-digit code
            <input className="min-h-14 rounded-xl border border-vextro-border px-4 text-center text-2xl font-black tracking-[0.35em] outline-none focus:border-vextro-primary" value={otp} onChange={(event) => setOtp(event.target.value.replace(/\D/g, "").slice(0, 6))} inputMode="numeric" autoComplete="one-time-code" pattern="\d{6}" required />
          </label>
          <button className="min-h-13 rounded-xl bg-vextro-primary px-5 text-sm font-black text-white disabled:opacity-60" disabled={busy || otp.length !== 6}>{busy ? "Please wait..." : "Verify and create account"}</button>
        </form>
        <button className="mt-4 w-full text-sm font-bold text-vextro-primary disabled:opacity-50" type="button" disabled={busy || !email} onClick={handleResend}>Send another code</button>
        <p className="mt-7 text-center text-sm text-vextro-muted"><Link className="font-black text-vextro-primary" to="/register">Back to signup</Link></p>
      </div>
    </section>
  );
}

export default VerifyEmailPage;
