import { useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { useAuth } from "../context/useAuth";
import { getApiErrorMessage } from "../utils/apiError";

function OAuthCallbackPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { completeOAuthLogin } = useAuth();
  const started = useRef(false);
  const code = searchParams.get("code");
  const [error, setError] = useState(
    code ? "" : "The social login response is incomplete.",
  );

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    if (!code) {
      return;
    }
    completeOAuthLogin(code)
      .then((user) => navigate(user.roles?.includes("admin") ? "/admin" : "/dashboard", { replace: true }))
      .catch((requestError) => setError(getApiErrorMessage(requestError, "Social login could not be completed.")));
  }, [code, completeOAuthLogin, navigate]);

  return (
    <section className="grid min-h-[calc(100vh-145px)] place-items-center bg-vextro-canvas px-4">
      <div className="w-full max-w-md rounded-3xl border border-vextro-border bg-white p-10 text-center shadow-vextro-lg">
        <h1 className="text-3xl font-black text-vextro-ink">Completing login</h1>
        <p className={`mt-4 text-sm ${error ? "text-red-700" : "text-vextro-muted"}`}>{error || "Securely connecting your VEXTRO account..."}</p>
        {error ? <button className="mt-6 font-black text-vextro-primary" onClick={() => navigate("/login", { replace: true })}>Return to login</button> : null}
      </div>
    </section>
  );
}

export default OAuthCallbackPage;
