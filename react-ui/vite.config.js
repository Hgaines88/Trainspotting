import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath, URL } from 'node:url'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const isEndToEnd = mode === 'e2e'

  return {
    plugins: [react()],
    resolve: isEndToEnd
      ? {
          alias: {
            '@clerk/react': fileURLToPath(
              new URL('./test/e2e/fakeClerk.jsx', import.meta.url),
            ),
          },
        }
      : undefined,
    server: {
      port: 5173,
      proxy: {
        '/api': {
          target: isEndToEnd
            ? 'http://127.0.0.1:8001'
            : 'http://127.0.0.1:8000',
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api/, ''),
        },
      },
    },
  }
})
