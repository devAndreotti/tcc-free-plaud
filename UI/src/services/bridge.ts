/**
 * bridge.ts
 * ─────────────────────────────────────────────────────────────
 * Camada de comunicação entre o React e o backend Python.
 *
 * Em produção (dentro do PyWebView):
 *   - window.pywebview.api estará disponível
 *   - As chamadas vão direto para métodos da classe Api em main.py
 *
 * Em desenvolvimento (npm run dev no navegador):
 *   - window.pywebview NÃO existe
 *   - As funções retornam respostas simuladas (mock)
 *
 * Para integrar o backend no futuro, edite apenas main.py (Python).
 * Este arquivo não precisará ser alterado.
 * ─────────────────────────────────────────────────────────────
 */

// Detecta se está rodando dentro do PyWebView (janela desktop)
const isDesktopApp =
  typeof window !== 'undefined' && 'pywebview' in window;

// ─── Declaração de tipos da API Python exposta pelo PyWebView ───────────────
interface PythonApi {
  /**
   * Envia mensagem do usuário para o backend Python.
   * @param message   Texto digitado pelo usuário
   * @param attachment Nome do arquivo anexado (opcional)
   * @returns         Resposta gerada pelo backend
   */
  sendMessage: (message: string, attachment?: string) => Promise<string>;
}

declare global {
  interface Window {
    pywebview?: {
      api: PythonApi;
    };
  }
}

// ─── Mock de desenvolvimento (substitui o backend em dev mode) ───────────────
const MOCK_RESPONSES = [
  'Olá! Estou em modo de desenvolvimento. O backend Python será integrado futuramente.',
  'Recebi sua mensagem! Quando conectado ao backend, a IA processará sua solicitação aqui.',
  'Modo mock ativo. Para ver as respostas reais, execute o programa via main.py com PyWebView.',
  'Esta é uma resposta simulada. O backend Python será responsável pelo processamento real.',
];

let mockIndex = 0;

const mockSendMessage = async (message: string): Promise<string> => {
  // Simula delay de rede/processamento
  const delay = 1000 + Math.random() * 800;
  await new Promise((resolve) => setTimeout(resolve, delay));

  console.debug(`[Bridge Mock] Mensagem enviada: "${message}"`);
  const response = MOCK_RESPONSES[mockIndex % MOCK_RESPONSES.length];
  mockIndex += 1;
  return response;
};

// ─── Serviço de bridge exportado ─────────────────────────────────────────────
export const bridge = {
  /**
   * Envia uma mensagem ao backend Python.
   * Em dev: retorna resposta mock.
   * Em produção: chama window.pywebview.api.sendMessage().
   */
  sendMessage: async (
    message: string,
    attachmentName?: string
  ): Promise<string> => {
    if (isDesktopApp && window.pywebview?.api) {
      // Produção: delega ao backend Python via PyWebView
      return window.pywebview.api.sendMessage(message, attachmentName);
    }
    // Desenvolvimento: usa mock local
    return mockSendMessage(message);
  },

  /** Indica se o app está rodando dentro do PyWebView (desktop) */
  isDesktop: isDesktopApp,
};
