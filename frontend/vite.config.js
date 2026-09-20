import { defineConfig } from "vite";
import { resolve } from "node:path";

export default defineConfig({
  build: {
    rollupOptions: {
      input: {
        app: resolve(import.meta.dirname, "index.html"),
        evaluation: resolve(import.meta.dirname, "evaluation.html"),
        login: resolve(import.meta.dirname, "login.html"),
      },
      output: {
        manualChunks(id) {
          if (id.includes("@pipecat-ai/websocket-transport")) {
            return "pipecat-transport";
          }
          if (id.includes("@pipecat-ai/client-js")) {
            return "pipecat-client";
          }
          return undefined;
        },
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
