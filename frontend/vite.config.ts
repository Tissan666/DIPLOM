import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    chunkSizeWarningLimit: 700,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.indexOf("node_modules") === -1) {
            return undefined;
          }
          if (id.indexOf("recharts") !== -1) {
            return "charts";
          }
          if (id.indexOf("xlsx") !== -1) {
            return "spreadsheet";
          }
          if (id.indexOf("framer-motion") !== -1) {
            return "motion";
          }
          if (id.indexOf("lucide-react") !== -1) {
            return "icons";
          }
          return undefined;
        },
      },
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:5000",
      "/predict": "http://127.0.0.1:5000",
      "/health": "http://127.0.0.1:5000",
    },
  },
  preview: {
    port: 4173,
  },
});
