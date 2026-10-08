import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import { AuthProvider } from "./context/AuthContext";
import ScrollToTop from "./components/ScrollToTop";
import AppRoutes from "./routes/AppRoutes";
import {
  isPushSupported,
  registerServiceWorker,
} from "./services/pushNotificationService";
import "./index.css";

/*
 * Register the push service worker so an already-subscribed browser can
 * receive notifications. This never prompts for permission; that only
 * happens from the explicit button in notification settings.
 */
if (isPushSupported()) {
  window.addEventListener("load", () => {
    registerServiceWorker().catch(() => {
      // Push stays unavailable; the rest of VEXTRO is unaffected.
    });
  });
}

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <BrowserRouter>
      <ScrollToTop />
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>,
);
