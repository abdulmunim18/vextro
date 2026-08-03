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

      const destination = roles.includes("admin")
        ? "/admin"
        : "/dashboard";

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
    <section className="auth-section">
      <div className="container auth-shell">
        <div className="auth-side">
          <span className="auth-side-label">
            VEXTRO Intelligence
          </span>

          <h1>Welcome back to smarter shopping.</h1>

          <p>
            Log in to compare marketplace prices, review price
            history and manage your personalized price alerts.
          </p>

          <div className="auth-feature-list">
            <span>✓ Compare Daraz and PriceOye listings</span>
            <span>✓ Track historical marketplace prices</span>
            <span>✓ Manage personalized price alerts</span>
          </div>
        </div>

        <div className="auth-panel">
          <div className="auth-heading">
            <span className="eyebrow">Welcome Back</span>
            <h2>Login to VEXTRO</h2>
            <p>
              Enter your account credentials to continue.
            </p>
          </div>

          {successMessage ? (
            <div className="auth-message auth-success">
              {successMessage}
            </div>
          ) : null}

          {errorMessage ? (
            <div className="auth-message auth-error">
              {errorMessage}
            </div>
          ) : null}

          <form className="auth-form" onSubmit={handleSubmit}>
            <div className="form-field">
              <label htmlFor="login-email">
                Email address
              </label>

              <input
                id="login-email"
                className="form-input"
                name="email"
                type="email"
                value={formData.email}
                onChange={handleChange}
                placeholder="you@example.com"
                autoComplete="email"
                required
              />
            </div>

            <div className="form-field">
              <div className="form-label-row">
                <label htmlFor="login-password">
                  Password
                </label>
              </div>

              <input
                id="login-password"
                className="form-input"
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
              className="primary-button auth-submit"
              type="submit"
              disabled={isSubmitting}
            >
              {isSubmitting
                ? "Logging in..."
                : "Login to VEXTRO"}
            </button>
          </form>

          <p className="auth-switch">
            New to VEXTRO?{" "}
            <Link to="/register">Create an account</Link>
          </p>
        </div>
      </div>
    </section>
  );
}

export default LoginPage;