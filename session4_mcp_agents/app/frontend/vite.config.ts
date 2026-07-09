import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Build output goes to ../static so server.py can serve it directly.
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "../static",
    emptyOutDir: true,
  },
  server: {
    // Local dev: proxy API calls to the FastAPI backend.
    proxy: {
      "/api": "http://localhost:8080",
    },
  },
});
