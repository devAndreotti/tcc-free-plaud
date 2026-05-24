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
 * ─────────────────────────────────────────────────────────────
 */

// Detecta se está rodando dentro do PyWebView (janela desktop)
const isDesktopApp =
  typeof window !== 'undefined' && 'pywebview' in window;

// ─── Declaração de tipos da API Python exposta pelo PyWebView ───────────────
/** Metadados de um arquivo Markdown retornado pelo scanVault */
export interface MarkdownNodeRaw {
  id: string;
  name: string;
  path: string;
  size: number;
  modified: string;
}

export interface IndexVaultResult {
  ok: boolean;
  status: string;
  total_found: number;
  indexed_count: number;
  unchanged_count: number;
  failed_count: number;
  skipped_count: number;
}

export interface BackendSettings {
  answer_provider: string;
  answer_model: string;
  answer_base_url: string | null;
  answer_api_key_configured: boolean;
  local_env_path: string;
  default_ask_strategy: string;
  notes_count: number;
  sqlite_chunks_count: number;
  vector_chunks_count: number;
}

export interface SaveApiKeyResult {
  ok: boolean;
  configured: boolean;
  local_env_path: string;
}

interface PythonApi {
  /**
   * Envia mensagem do usuário para o backend Python.
   * @param message   Texto digitado pelo usuário
   * @param attachment Nome do arquivo anexado (opcional)
   * @returns         Resposta gerada pelo backend
   */
  sendMessage: (message: string, attachment?: string) => Promise<string>;

  /**
   * Abre o seletor nativo de pasta do sistema operacional.
   * @returns Caminho absoluto da pasta selecionada, ou string vazia se cancelado
   */
  selectFolder: () => Promise<string>;

  /**
   * Varre a pasta do vault recursivamente e retorna metadados dos arquivos .md.
   * @param folderPath Caminho absoluto da pasta do vault
   * @returns Lista de objetos com id, name, path, size e modified
   */
  scanVault: (folderPath: string) => Promise<MarkdownNodeRaw[]>;

  /**
   * Persiste o caminho do vault em config.json para restaurar na próxima sessão.
   * @param path Caminho absoluto do vault (string vazia para limpar)
   * @returns true em caso de sucesso
   */
  saveVaultPath: (path: string) => Promise<boolean>;

  /**
   * Carrega o caminho do vault salvo na sessão anterior.
   * @returns Caminho salvo, ou string vazia se nunca foi configurado
   */
  loadVaultPath: () => Promise<string>;

  /** Indexa a pasta selecionada no corpus local do backend. */
  indexVault?: (folderPath: string) => Promise<IndexVaultResult>;

  /** Retorna resumo das configurações/backend para o modal. */
  getBackendSettings?: () => Promise<BackendSettings>;

  /** Salva ou remove FREE_PLAUD_ANSWER_API_KEY em pipeline/.env. */
  saveApiKey?: (apiKey: string) => Promise<SaveApiKeyResult>;
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
  'Modo desenvolvimento no navegador. Para resposta real, rode o app via PyWebView.',
  'Recebi sua mensagem em mock. O backend real responde ao abrir UI/main.py.',
  'Modo mock ativo. Para ver as respostas reais, execute o programa via main.py com PyWebView.',
  'Esta é uma resposta simulada. A integração real usa corpus ask no backend Python.',
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

  /**
   * Abre o seletor nativo de pasta (via Python).
   * Em dev: retorna um caminho de exemplo.
   * Em produção: chama window.pywebview.api.selectFolder().
   */
  selectFolder: async (): Promise<string> => {
    if (isDesktopApp && window.pywebview?.api) {
      return window.pywebview.api.selectFolder();
    }
    // Mock de desenvolvimento: simula delay e retorna caminho fictício
    await new Promise((resolve) => setTimeout(resolve, 600));
    return 'C:\\Users\\usuario\\Documents\\Vault (mock)';
  },

  /**
   * Varre o vault em busca de arquivos .md (via Python).
   * Em dev: retorna lista de arquivos fictícios.
   */
  scanVault: async (folderPath: string): Promise<MarkdownNodeRaw[]> => {
    if (isDesktopApp && window.pywebview?.api) {
      return window.pywebview.api.scanVault(folderPath);
    }
    // Mock de desenvolvimento
    await new Promise((resolve) => setTimeout(resolve, 900));
    const now = new Date().toISOString();
    return [
      { id: 'mock-1', name: 'Introdução',       path: 'Introdução.md',              size: 1240,  modified: now },
      { id: 'mock-2', name: 'Referencial Teórico', path: 'teoria/Referencial Teórico.md', size: 4800,  modified: now },
      { id: 'mock-3', name: 'Metodologia',      path: 'Metodologia.md',             size: 2300,  modified: now },
      { id: 'mock-4', name: 'Resultados',       path: 'resultados/Resultados.md',   size: 3100,  modified: now },
      { id: 'mock-5', name: 'Conclusão',        path: 'Conclusão.md',               size: 980,   modified: now },
    ];
  },

  /**
   * Salva o caminho do vault no config.json (via Python).
   * Em dev: no-op.
   */
  saveVaultPath: async (path: string): Promise<boolean> => {
    if (isDesktopApp && window.pywebview?.api) {
      return window.pywebview.api.saveVaultPath(path);
    }
    // Mock: simula sucesso silencioso
    console.debug(`[Bridge Mock] saveVaultPath: "${path}"`);
    return true;
  },

  /**
   * Carrega o caminho do vault salvo anteriormente (via Python).
   * Em dev: retorna string vazia.
   */
  loadVaultPath: async (): Promise<string> => {
    if (isDesktopApp && window.pywebview?.api) {
      return window.pywebview.api.loadVaultPath();
    }
    // Mock: sem persistência em dev
    return '';
  },

  indexVault: async (folderPath: string): Promise<IndexVaultResult> => {
    if (isDesktopApp && window.pywebview?.api.indexVault) {
      return window.pywebview.api.indexVault(folderPath);
    }
    await new Promise((resolve) => setTimeout(resolve, 700));
    return {
      ok: true,
      status: 'mock',
      total_found: 5,
      indexed_count: 5,
      unchanged_count: 0,
      failed_count: 0,
      skipped_count: 0,
    };
  },

  getBackendSettings: async (): Promise<BackendSettings> => {
    if (isDesktopApp && window.pywebview?.api.getBackendSettings) {
      return window.pywebview.api.getBackendSettings();
    }
    return {
      answer_provider: 'extractive',
      answer_model: 'llama3.1:8b',
      answer_base_url: null,
      answer_api_key_configured: false,
      local_env_path: 'pipeline\\.env',
      default_ask_strategy: 'hybrid',
      notes_count: 0,
      sqlite_chunks_count: 0,
      vector_chunks_count: 0,
    };
  },

  saveApiKey: async (apiKey: string): Promise<SaveApiKeyResult> => {
    if (isDesktopApp && window.pywebview?.api.saveApiKey) {
      return window.pywebview.api.saveApiKey(apiKey);
    }
    console.debug('[Bridge Mock] saveApiKey:', apiKey ? '<redacted>' : '<empty>');
    return {
      ok: true,
      configured: apiKey.trim().length > 0,
      local_env_path: 'pipeline\\.env',
    };
  },

  /** Indica se o app está rodando dentro do PyWebView (desktop) */
  isDesktop: isDesktopApp,
};
