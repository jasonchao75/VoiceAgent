import { defineConfig } from "vite";
import { resolve } from "node:path";

export default defineConfig({
  build: {
    rollupOptions: {
      input: {
        app: resolve(import.meta.dirname, "index.html"),
        login: resolve(import.meta.dirname, "login.html"),
      },
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        ws: true,
      },
      "/health": "http://127.0.0.1:8000",
    },
  },
});
