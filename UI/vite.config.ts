import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import { readFileSync } from 'node:fs'

// Versão do app vem do VERSION da raiz (mesma fonte do release desktop).
const appVersion = readFileSync(new URL('../VERSION', import.meta.url), 'utf-8').trim()

// Configuração do Vite para build desktop (PyWebView)
export default defineConfig({
  plugins: [react()],
  define: { __APP_VERSION__: JSON.stringify(appVersion) },
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
    testTimeout: 60000,
    setupFiles: ['src/test/setup.ts'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json-summary', 'lcov'],
      reportsDirectory: '../coverage/ui',
    },
  },
})
