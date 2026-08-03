import { Route, Routes } from "react-router-dom";

import MainLayout from "../layouts/MainLayout";
import HomePage from "../pages/HomePage";
import LoginPage from "../pages/LoginPage";
import NotFoundPage from "../pages/NotFoundPage";
import PlaceholderPage from "../pages/PlaceholderPage";
import ProductDetailPage from "../pages/ProductDetailPage";
import RegisterPage from "../pages/RegisterPage";
import UnauthorizedPage from "../pages/UnauthorizedPage";
import GuestRoute from "./GuestRoute";
import ProtectedRoute from "./ProtectedRoute";

function AppRoutes() {
  return (
    <Routes>
      <Route element={<MainLayout />}>
        <Route index element={<HomePage />} />

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

        <Route
          path="products"
          element={
            <PlaceholderPage
              eyebrow="Product Discovery"
              title="Search marketplace products"
              description="Product search, categories, brands, pagination and marketplace filters will appear here."
            />
          }
        />

        <Route
          path="products/:productId"
          element={<ProductDetailPage />}
        />

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
            element={
              <PlaceholderPage
                eyebrow="Price Intelligence"
                title="Manage your price alerts"
                description="Create, update, deactivate and reactivate your product price alerts here."
              />
            }
          />
        </Route>

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