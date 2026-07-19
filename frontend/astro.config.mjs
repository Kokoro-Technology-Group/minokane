import { defineConfig } from "astro/config";

export default defineConfig({
  // host:true → bind all interfaces (127.0.0.1 + ::1), not IPv6-only, so the
  // HMR websocket (ws://localhost:4321) connects regardless of how `localhost`
  // resolves.
  server: { port: 4321, host: true },
  vite: {
    server: {
      host: true,
      // Pin the HMR client to localhost:4321 so the ws URL is unambiguous even
      // when the server is exposed on 0.0.0.0.
      hmr: { host: "localhost", protocol: "ws", clientPort: 4321 },
      proxy: {
        "/api": {
          target: "http://localhost:8000",
          changeOrigin: true,
        },
      },
    },
  },
});
