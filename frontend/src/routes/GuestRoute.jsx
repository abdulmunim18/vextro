import {
  Navigate,
  Outlet,
} from "react-router-dom";

import { useAuth } from "../context/AuthContext";

function getAuthenticatedDestination(user) {
  const roles = (user?.roles || []).map((role) =>
    role.toLowerCase(),
  );

  if (roles.includes("admin")) {
    return "/admin";
  }

  return "/dashboard";
}

function GuestRoute() {
  const {
    user,
    isAuthenticated,
    isInitializing,
  } = useAuth();

  if (isInitializing) {
    return (
      <section className="route-loading-section">
        <div className="route-loader" />
        <p>Checking your VEXTRO session...</p>
      </section>
    );
  }

  if (isAuthenticated) {
    return (
      <Navigate
        to={getAuthenticatedDestination(user)}
        replace
      />
    );
  }

  return <Outlet />;
}

export default GuestRoute;