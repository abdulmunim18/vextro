import { lazy, Suspense } from "react";
import { Route, Routes } from "react-router-dom";
import MainLayout from "../layouts/MainLayout";
import RouteLoadingState from "../components/RouteLoadingState";
import GuestRoute from "./GuestRoute";
import ProtectedRoute from "./ProtectedRoute";

const AdminPage = lazy(() => import("../pages/AdminPage"));
const AssistantPage = lazy(() => import("../pages/AssistantPage"));
const ComparisonPage = lazy(() => import("../pages/ComparisonPage"));
const DashboardPage = lazy(() => import("../pages/DashboardPage"));
const HomePage = lazy(() => import("../pages/HomePage"));
const LoginPage = lazy(() => import("../pages/LoginPage"));
const NotFoundPage = lazy(() => import("../pages/NotFoundPage"));
const PriceAlertsPage = lazy(() => import("../pages/PriceAlertsPage"));
const ProductDetailPage = lazy(() => import("../pages/ProductDetailPage"));
const ProductsPage = lazy(() => import("../pages/ProductsPage"));
const RegisterPage = lazy(() => import("../pages/RegisterPage"));
const SMEPage = lazy(() => import("../pages/SMEPage"));
const UnauthorizedPage = lazy(() => import("../pages/UnauthorizedPage"));

function AppRoutes() {
  return (
    <Suspense fallback={<RouteLoadingState message="Loading VEXTRO..." />}>
    <Routes>
      <Route element={<MainLayout />}>
        {/* Public routes */}
        <Route index element={<HomePage />} />

        <Route
          path="products"
          element={<ProductsPage />}
        />

        <Route
          path="products/:productId"
          element={<ProductDetailPage />}
        />
        <Route
          path="compare"
          element={<ComparisonPage />}
        />

        {/* Guest-only routes */}
        <Route element={<GuestRoute />}>
          <Route
            path="login"
            element={<LoginPage />}
          />

          <Route
            path="register"
            element={<RegisterPage />}
          />
        </Route>

        {/* Consumer, SME and Admin routes */}
        <Route
          element={
            <ProtectedRoute
              allowedRoles={[
                "consumer",
                "sme",
                "admin",
              ]}
            />
          }
        >
          <Route
            path="dashboard"
            element={<DashboardPage />}
          />
        </Route>

        {/* Consumer and Admin routes */}
        <Route
          element={
            <ProtectedRoute
              allowedRoles={[
                "consumer",
                "admin",
              ]}
            />
          }
        >
          <Route
            path="alerts"
            element={<PriceAlertsPage />}
          />
          <Route
            path="assistant"
            element={<AssistantPage />}
          />
        </Route>

        {/* SME and Admin routes */}
        <Route
          element={
            <ProtectedRoute
              allowedRoles={[
                "sme",
                "admin",
              ]}
            />
          }
        >
          <Route
            path="sme"
            element={<SMEPage />}
          />
        </Route>

        {/* Admin-only routes */}
        <Route
          element={
            <ProtectedRoute
              allowedRoles={["admin"]}
            />
          }
        >
          <Route
            path="admin"
            element={<AdminPage />}
          />
        </Route>

        {/* Error routes */}
        <Route
          path="forbidden"
          element={<UnauthorizedPage />}
        />

        <Route
          path="*"
          element={<NotFoundPage />}
        />
      </Route>
    </Routes>
    </Suspense>
  );
}

export default AppRoutes;
