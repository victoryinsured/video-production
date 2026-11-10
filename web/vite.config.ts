import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Proxies /api to the Express server in development so there is never a cross-origin request to
// allow — the same reason the server itself runs with no CORS middleware (see server/src/index.ts).
// In production the same Express app serves this app's built files directly, same-origin again.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: process.env.VITE_API_PROXY_TARGET ?? "http://localhost:4000",
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: "dist",
  },
});
