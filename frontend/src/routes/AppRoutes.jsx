import { Route, Routes } from "react-router-dom";

import MainLayout from "../layouts/MainLayout";
import HomePage from "../pages/HomePage";
import LoginPage from "../pages/LoginPage";
import NotFoundPage from "../pages/NotFoundPage";
import PlaceholderPage from "../pages/PlaceholderPage";
import PriceAlertsPage from "../pages/PriceAlertsPage";
import ProductDetailPage from "../pages/ProductDetailPage";
import ProductsPage from "../pages/ProductsPage";
import RegisterPage from "../pages/RegisterPage";
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
            element={
              <PlaceholderPage
                eyebrow="User Dashboard"
                title="Your ecommerce intelligence dashboard"
                description="Saved products, recent searches, price changes and account information will appear here."
              />
            }
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
            element={
              <PlaceholderPage
                eyebrow="Administration"
                title="VEXTRO Admin Panel"
                description="Manage users, products, marketplace listings and system activity."
              />
            }
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