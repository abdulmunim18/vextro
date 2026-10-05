import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { resetPassword } from "../services/authService";
import { getApiErrorMessage } from "../utils/apiError";

function ResetPasswordPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const token = searchParams.get("token") || "";
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    if (password !== confirmation) {
      setError("Passwords do not match.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await resetPassword(token, password);
      navigate("/login", { replace: true, state: { message: "Password changed successfully. You can now log in." } });
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, "Unable to reset your password."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="min-h-[calc(100vh-145px)] bg-vextro-canvas px-4 py-16">
      <div className="mx-auto max-w-lg rounded-3xl border border-vextro-border bg-white p-7 shadow-vextro-lg sm:p-10">
        <span className="text-xs font-black uppercase tracking-[0.18em] text-vextro-primary">Account recovery</span>
        <h1 className="mt-3 text-4xl font-black tracking-tight text-vextro-ink">Choose a new password</h1>
        <p className="mt-4 text-sm leading-7 text-vextro-muted">Use at least 8 characters with uppercase, lowercase, a number, and a special character.</p>
        {!token ? <div className="mt-5 rounded-xl border border-red-200 bg-red-50 p-3 text-sm font-semibold text-red-700">This reset link is incomplete.</div> : null}
        {error ? <div className="mt-5 rounded-xl border border-red-200 bg-red-50 p-3 text-sm font-semibold text-red-700" role="alert">{error}</div> : null}
        <form className="mt-7 grid gap-5" onSubmit={handleSubmit}>
          <label className="grid gap-2 text-sm font-bold text-vextro-ink">New password
            <input className="min-h-13 rounded-xl border border-vextro-border px-4 outline-none focus:border-vextro-primary" type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="new-password" minLength={8} required />
          </label>
          <label className="grid gap-2 text-sm font-bold text-vextro-ink">Confirm password
            <input className="min-h-13 rounded-xl border border-vextro-border px-4 outline-none focus:border-vextro-primary" type="password" value={confirmation} onChange={(event) => setConfirmation(event.target.value)} autoComplete="new-password" minLength={8} required />
          </label>
          <button className="min-h-13 rounded-xl bg-vextro-primary px-5 text-sm font-black text-white disabled:opacity-60" disabled={busy || !token}>{busy ? "Updating..." : "Change password"}</button>
        </form>
        <p className="mt-7 text-center text-sm"><Link className="font-black text-vextro-primary" to="/login">Back to login</Link></p>
      </div>
    </section>
  );
}

export default ResetPasswordPage;
