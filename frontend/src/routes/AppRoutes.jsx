import { lazy, Suspense } from "react";
import { Route, Routes } from "react-router-dom";
import MainLayout from "../layouts/MainLayout";
import RouteLoadingState from "../components/RouteLoadingState";
import GuestRoute from "./GuestRoute";
import ProtectedRoute from "./ProtectedRoute";

const AdminPage = lazy(() => import("../pages/AdminPage"));
const AboutPage = lazy(() => import("../pages/AboutPage"));
const AssistantPage = lazy(() => import("../pages/AssistantPage"));
const ComparisonPage = lazy(() => import("../pages/ComparisonPage"));
const ContactPage = lazy(() => import("../pages/ContactPage"));
const DashboardPage = lazy(() => import("../pages/DashboardPage"));
const HomePage = lazy(() => import("../pages/HomePage"));
const HowItWorksPage = lazy(() => import("../pages/HowItWorksPage"));
const LoginPage = lazy(() => import("../pages/LoginPage"));
const NotFoundPage = lazy(() => import("../pages/NotFoundPage"));
const PriceAlertsPage = lazy(() => import("../pages/PriceAlertsPage"));
const PriceAlertsInfoPage = lazy(() => import("../pages/PriceAlertsInfoPage"));
const PrivacyPage = lazy(() => import("../pages/PrivacyPage"));
const ProductDetailPage = lazy(() => import("../pages/ProductDetailPage"));
const ProductsPage = lazy(() => import("../pages/ProductsPage"));
const RegisterPage = lazy(() => import("../pages/RegisterPage"));
const ForBusinessesPage = lazy(() => import("../pages/ForBusinessesPage"));
const SMEPage = lazy(() => import("../pages/SMEPage"));
const TermsPage = lazy(() => import("../pages/TermsPage"));
const SupportPage = lazy(() => import("../pages/SupportPage"));
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
        <Route path="about" element={<AboutPage />} />
        <Route path="how-it-works" element={<HowItWorksPage />} />
        <Route path="for-businesses" element={<ForBusinessesPage />} />
        <Route path="privacy" element={<PrivacyPage />} />
        <Route path="terms" element={<TermsPage />} />
        <Route path="price-alerts" element={<PriceAlertsInfoPage />} />
        <Route path="support" element={<SupportPage />} />
        <Route path="contact" element={<ContactPage />} />

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
