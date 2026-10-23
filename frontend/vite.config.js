import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
  ],

  server: {
    port: 5173,
    // The backend allows requests from port 5173 only (CORS_ORIGINS). On
    // another port every request is refused and the site reads "Unable to
    // connect", so a busy 5173 is reported instead of quietly moving on.
    strictPort: true,

    proxy: {
      "/api": {
        target: process.env.VITE_API_PROXY_TARGET || "http://127.0.0.1:8001",
        changeOrigin: true,
      },
    },
  },
});
