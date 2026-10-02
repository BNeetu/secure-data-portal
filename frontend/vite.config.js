import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Proxies API + WebSocket calls to the FastAPI backend during local dev.
// In production, the frontend is built as static files and nginx handles
// routing /auth, /data, /audit, /health to the backend (see /nginx/nginx.conf).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/auth': { target: 'http://localhost:8000', changeOrigin: true },
      '/data': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        ws: true, // enables proxying of /data/ws/live WebSocket connections
      },
      '/audit': { target: 'http://localhost:8000', changeOrigin: true },
      '/health': { target: 'http://localhost:8000', changeOrigin: true },
    },
  },
})
