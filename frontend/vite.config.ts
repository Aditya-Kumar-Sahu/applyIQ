import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  plugins: [vue()],
  server: {
    host: "0.0.0.0",
    port: 3000,
    allowedHosts: true,
    proxy: {
      "/api/v1": {
        target: "http://backend-test:8000",
        changeOrigin: true,
      },
    },
  },
  preview: {
    host: "0.0.0.0",
    port: 3000,
  },
});
