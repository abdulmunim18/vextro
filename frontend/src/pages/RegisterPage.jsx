import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useAuth } from "../context/AuthContext";
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
    <section className="auth-section">
      <div className="container auth-shell">
        <div className="auth-side">
          <span className="auth-side-label">
            Start with VEXTRO
          </span>

          <h1>Make every marketplace decision smarter.</h1>

          <p>
            Create an account to search products, compare
            marketplace listings and receive price-drop alerts.
          </p>

          <div className="auth-feature-list">
            <span>✓ Free consumer account</span>
            <span>✓ Dedicated SME account option</span>
            <span>✓ Secure FastAPI authentication</span>
          </div>
        </div>

        <div className="auth-panel">
          <div className="auth-heading">
            <span className="eyebrow">Create Account</span>
            <h2>Join VEXTRO</h2>
            <p>
              Enter your details and select the account type that
              matches your needs.
            </p>
          </div>

          {errorMessage ? (
            <div className="auth-message auth-error">
              {errorMessage}
            </div>
          ) : null}

          <form className="auth-form" onSubmit={handleSubmit}>
            <div className="form-field">
              <label htmlFor="register-name">
                Full name
              </label>

              <input
                id="register-name"
                className="form-input"
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

            <div className="form-field">
              <label htmlFor="register-email">
                Email address
              </label>

              <input
                id="register-email"
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
              <label htmlFor="account-type">
                Account type
              </label>

              <select
                id="account-type"
                className="form-input"
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
            </div>

            <div className="form-row">
              <div className="form-field">
                <label htmlFor="register-password">
                  Password
                </label>

                <input
                  id="register-password"
                  className="form-input"
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

              <div className="form-field">
                <label htmlFor="confirm-password">
                  Confirm password
                </label>

                <input
                  id="confirm-password"
                  className="form-input"
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

            <p className="form-help">
              Your password must contain at least 8 characters.
            </p>

            <button
              className="primary-button auth-submit"
              type="submit"
              disabled={isSubmitting}
            >
              {isSubmitting
                ? "Creating account..."
                : "Create VEXTRO Account"}
            </button>
          </form>

          <p className="auth-switch">
            Already registered?{" "}
            <Link to="/login">Login to your account</Link>
          </p>
        </div>
      </div>
    </section>
  );
}

export default RegisterPage;