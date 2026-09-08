import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

// Configuração do Vite para build desktop (PyWebView)
export default defineConfig({
  plugins: [react()],
  base: './', // Caminhos relativos: necessário para carregar via file:// no PyWebView
  build: {
    outDir: 'dist',       // Pasta de saída do build
    assetsDir: 'assets',  // Subpasta de assets dentro do dist
    emptyOutDir: true,    // Limpa o dist antes de cada build
  },
  test: {
    environment: 'jsdom',
    include: ['src/**/*.test.{ts,tsx}'],
    exclude: ['node_modules', 'dist', 'e2e/**'],
    testTimeout: 15000,
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json-summary', 'lcov'],
      reportsDirectory: '../coverage/ui',
    },
  },
})
