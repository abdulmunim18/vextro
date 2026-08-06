import { Route, Routes } from "react-router-dom";

import MainLayout from "../layouts/MainLayout";
import AdminPage from "../pages/AdminPage";
import DashboardPage from "../pages/DashboardPage";
import HomePage from "../pages/HomePage";
import LoginPage from "../pages/LoginPage";
import NotFoundPage from "../pages/NotFoundPage";
import PriceAlertsPage from "../pages/PriceAlertsPage";
import ProductDetailPage from "../pages/ProductDetailPage";
import ProductsPage from "../pages/ProductsPage";
import RegisterPage from "../pages/RegisterPage";
import SMEPage from "../pages/SMEPage";
import UnauthorizedPage from "../pages/UnauthorizedPage";
import GuestRoute from "./GuestRoute";
import ProtectedRoute from "./ProtectedRoute";

function AppRoutes() {
  return (
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
  );
}

export default AppRoutes;