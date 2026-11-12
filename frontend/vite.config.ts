import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

// El proxy sirve frontend y API desde el mismo origen en desarrollo:
// /api -> backend FastAPI. Asi la cookie SameSite=Strict del refresh funciona
// igual que en produccion detras de Nginx.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://localhost:3000', changeOrigin: true },
      '/health': { target: 'http://localhost:3000', changeOrigin: true },
    },
  },
});
