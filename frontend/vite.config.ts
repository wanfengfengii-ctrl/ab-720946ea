import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// 开发环境通过代理把 /api 转发到本地 FastAPI；容器内由 nginx 代理
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
