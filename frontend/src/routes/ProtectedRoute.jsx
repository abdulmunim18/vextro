import {
  Navigate,
  Outlet,
  useLocation,
} from "react-router-dom";

import { useAuth } from "../context/AuthContext";

function ProtectedRoute({ allowedRoles = [] }) {
  const location = useLocation();

  const {
    isAuthenticated,
    isInitializing,
    hasRole,
  } = useAuth();

  if (isInitializing) {
    return (
      <section className="route-loading-section">
        <div className="route-loader" />
        <p>Restoring your VEXTRO session...</p>
      </section>
    );
  }

  if (!isAuthenticated) {
    return (
      <Navigate
        to="/login"
        replace
        state={{
          from: `${location.pathname}${location.search}`,
          message:
            "Please log in to access this page.",
        }}
      />
    );
  }

  const requiresSpecificRole = allowedRoles.length > 0;

  if (
    requiresSpecificRole &&
    !hasRole(...allowedRoles)
  ) {
    return (
      <Navigate
        to="/forbidden"
        replace
      />
    );
  }

  return <Outlet />;
}

export default ProtectedRoute;