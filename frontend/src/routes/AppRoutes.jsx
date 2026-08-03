import { Route, Routes } from "react-router-dom";

import LoginPage from "../pages/LoginPage";
import RegisterPage from "../pages/RegisterPage";
import MainLayout from "../layouts/MainLayout";
import HomePage from "../pages/HomePage";
import NotFoundPage from "../pages/NotFoundPage";
import PlaceholderPage from "../pages/PlaceholderPage";
import ProductDetailPage from "../pages/ProductDetailPage";

function AppRoutes() {
  return (
    <Routes>
      <Route element={<MainLayout />}>
        <Route index element={<HomePage />} />

        <Route path="login" element={<LoginPage />} />

        <Route path="register" element={<RegisterPage />} />

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
          path="dashboard"
          element={
            <PlaceholderPage
              eyebrow="Consumer Dashboard"
              title="Your ecommerce intelligence dashboard"
              description="Saved products, recent searches, price changes and account information will appear here."
            />
          }
        />

        <Route
          path="alerts"
          element={
            <PlaceholderPage
              eyebrow="Price Intelligence"
              title="Manage your price alerts"
              description="Users will create, update, deactivate and reactivate product price alerts here."
            />
          }
        />

        <Route
          path="admin"
          element={
            <PlaceholderPage
              eyebrow="Administration"
              title="VEXTRO Admin Panel"
              description="The admin dashboard will provide users, products, listings and system monitoring tools."
            />
          }
        />

        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}

export default AppRoutes;