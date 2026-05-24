import { defineConfig } from 'vite'
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
})
