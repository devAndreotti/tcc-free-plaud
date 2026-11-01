import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import './appearance.css'
import { applyTheme, readThemeChoice } from './theme'
import { applyAppearance, readAppearance } from './appearance'

applyTheme(readThemeChoice())
applyAppearance(readAppearance())

// Arquivo solto fora da área de soltar não pode abrir no WebView e derrubar o app.
for (const type of ['dragover', 'drop'] as const) {
  window.addEventListener(type, (event) => event.preventDefault())
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
