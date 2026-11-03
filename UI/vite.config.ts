import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import { readFileSync } from 'node:fs'

// Versão do app vem do VERSION da raiz (mesma fonte do release desktop).
const appVersion = readFileSync(new URL('../VERSION', import.meta.url), 'utf-8').trim()

// CSP só no build (o app abre dist/index.html por file://). No dev o Vite injeta scripts inline e a política o quebraria.
// 'unsafe-eval' é necessário: o PyWebView devolve cada resultado da API Python com window.evaluate_js, que chama eval().
// Sem ele a ponte pode parar; a política ainda bloqueia script inline, handlers inline e script/imagem/conexão externos.
// Fontes: IBM Plex e Source Serif são embutidas (src/assets/fonts), sem rede. Imagens data: vêm do ícone do grafo.
const CSP = [
  "default-src 'none'",
  "script-src 'self' 'unsafe-eval'",
  "style-src 'self' 'unsafe-inline'",
  "font-src 'self' data:",
  "img-src 'self' data: blob:",
  "connect-src 'self'",
  "object-src 'none'",
  "base-uri 'none'",
  "form-action 'none'",
  "frame-src 'none'",
].join('; ')

const cspPlugin = {
  name: 'escolio-csp',
  apply: 'build' as const,
  transformIndexHtml: () => [
    { tag: 'meta', attrs: { 'http-equiv': 'Content-Security-Policy', content: CSP }, injectTo: 'head-prepend' as const },
  ],
}

// Configuração do Vite para build desktop (PyWebView)
export default defineConfig({
  plugins: [react(), cspPlugin],
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
