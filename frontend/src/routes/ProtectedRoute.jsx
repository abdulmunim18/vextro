import {
  Navigate,
  Outlet,
  useLocation,
} from "react-router-dom";

import RouteLoadingState from "../components/RouteLoadingState";
import { useAuth } from "../context/useAuth";

function ProtectedRoute({ allowedRoles = [] }) {
  const location = useLocation();

  const {
    isAuthenticated,
    isInitializing,
    hasRole,
  } = useAuth();

  if (isInitializing) {
    return (
      <RouteLoadingState message="Restoring your secure VEXTRO session..." />
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

  const requiresSpecificRole =
    allowedRoles.length > 0;

  if (
    requiresSpecificRole &&
    !hasRole(...allowedRoles)
  ) {
    return (
      <Navigate
        to="/forbidden"
        replace
        state={{
          attemptedPath: location.pathname,
        }}
      />
    );
  }

  return <Outlet />;
}

export default ProtectedRoute;
