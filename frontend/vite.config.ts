import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

// In dev, the browser calls /api/... on the Vite server, which forwards to FastAPI with /api stripped.
// That mirrors the Nginx setup in production, so the app never needs CORS.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const target = env.API_PROXY_TARGET || "http://localhost:8000";
  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: {
        "/api": {
          target,
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api/, ""),
        },
      },
    },
  };
});
