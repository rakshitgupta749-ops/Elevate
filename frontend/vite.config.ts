import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

// https://vite.dev/config/
export default defineConfig({
  plugins: [tailwindcss(), react()],
  resolve: {
    alias: {
      '@': path.resolve(import.meta.dirname, './src'),
    },
  },
  server: {
    host: true,
    allowedHosts: [
      '.pinggy.net',
      '.pinggy-free.link',
      '.pinggy.link',
      '.free.pinggy.net',
      '.run.pinggy-free.link',
      '.trycloudflare.com',
      '.loca.lt',
      'localhost',
      '127.0.0.1'
    ],
    fs: {
      allow: ['..']
    },
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        ws: true,
        timeout: 120000,
      },
    },
  }
})

