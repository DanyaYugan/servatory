import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  plugins: [vue()],
  // приложение отдаётся по /ui/, поэтому все ассеты тоже с этим префиксом
  base: "/ui/",
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8090",
      "/health": "http://127.0.0.1:8090",
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
});
