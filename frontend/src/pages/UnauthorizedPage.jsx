import { Link } from "react-router-dom";

import { useAuth } from "../context/AuthContext";

function UnauthorizedPage() {
  const { user, hasRole } = useAuth();

  const returnPath = hasRole("admin")
    ? "/admin"
    : "/dashboard";

  return (
    <section className="page-section">
      <div className="container">
        <div className="page-card centered-card">
          <span className="error-code">403</span>

          <span className="eyebrow">
            Access Restricted
          </span>

          <h1>You cannot access this page</h1>

          <p>
            Your current account role does not have permission
            to open this VEXTRO resource.
          </p>

          {user?.roles?.length ? (
            <div className="role-information">
              Current role:{" "}
              <strong>{user.roles.join(", ")}</strong>
            </div>
          ) : null}

          <Link
            className="primary-button inline-button"
            to={returnPath}
          >
            Return to Dashboard
          </Link>
        </div>
      </div>
    </section>
  );
}

export default UnauthorizedPage;