import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Geliştirme: Vite 5173'te çalışır, /api ve /ws isteklerini PC Agent'a (8000)
// yönlendirir. Üretim: `npm run build` → dist/ klasörünü agent aynen sunar.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/ws": { target: "ws://127.0.0.1:8000", ws: true },
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
});
