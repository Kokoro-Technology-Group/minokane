import { defineConfig } from "astro/config";

export default defineConfig({
  server: { port: 4321 },
  vite: {
    server: {
      proxy: {
        "/api": {
          target: "http://localhost:8000",
          changeOrigin: true,
        },
      },
    },
  },
});
