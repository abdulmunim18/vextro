import {
  Navigate,
  Outlet,
} from "react-router-dom";

import RouteLoadingState from "../components/RouteLoadingState";
import { useAuth } from "../context/useAuth";

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
      <RouteLoadingState message="Checking your VEXTRO session..." />
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
