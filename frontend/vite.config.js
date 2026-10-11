import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const backendTarget = process.env.API_PROXY_TARGET || 'http://localhost:8000'

// Proxies API + WebSocket calls to the FastAPI backend during local dev.
// In production, the frontend is built as static files and nginx handles
// routing /auth, /data, /audit, /health to the backend (see /nginx/nginx.conf).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/auth': { target: backendTarget, changeOrigin: true },
      '/data': {
        target: backendTarget,
        changeOrigin: true,
        ws: true, // enables proxying of /data/ws/live WebSocket connections
      },
      '/audit': { target: backendTarget, changeOrigin: true },
      '/health': { target: backendTarget, changeOrigin: true },
    },
  },
})
