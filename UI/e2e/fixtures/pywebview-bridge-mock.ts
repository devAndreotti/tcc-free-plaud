export interface MockBridgeOptions {
  askLatencyMs?: number;
  simulateLlmTimeout?: boolean;
}

export function createPyWebViewMockScript(options: MockBridgeOptions = {}) {
  return `
    (function() {
      window.pywebview = {
        api: {
          loadVaultPath: async function() {
            return "/mock/vault";
          },
          saveVaultPath: async function(path) {
            return { ok: true, path: path };
          },
          selectFolder: async function() {
            return "/mock/vault";
          },
          scanVault: async function(folderPath) {
            return [
              { id: "note-01", name: "Arquitetura.md", path: "/mock/vault/Arquitetura.md", size: 1024, modified: "2026-09-08" },
              { id: "note-02", name: "RRF.md", path: "/mock/vault/RRF.md", size: 2048, modified: "2026-09-08" }
            ];
          },
          sendMessage: async function(message, attachmentName) {
            if (${options.simulateLlmTimeout || false}) {
              await new Promise(r => setTimeout(r, 500));
              throw new Error("Timeout de conexao com LLM.");
            }
            await new Promise(r => setTimeout(r, ${options.askLatencyMs || 50}));
            return "Resposta sintetizada para: " + message + "\\n\\n- Recuperação híbrida via BM25 e ChromaDB.\\n- Citações obrigatórias e verificadas.";
          },
          listNotes: async function() {
            return [
              { id: "note-01", title: "Arquitetura do Escólio", filename: "Arquitetura.md", path: "/mock/vault/Arquitetura.md", size: 1024, modified: "2026-09-08", tags: ["tcc", "rag"] },
              { id: "note-02", title: "Decisões de RRF", filename: "RRF.md", path: "/mock/vault/RRF.md", size: 2048, modified: "2026-09-08", tags: ["benchmark"] }
            ];
          },
          getNoteDetail: async function(noteId) {
            return {
              id: noteId,
              title: "Nota " + noteId,
              content: "# Detalhes da Nota\\n\\nConteúdo estruturado para o TCC.",
              tags: ["tcc"]
            };
          },
          getBackendSettings: async function() {
            return {
              embedding_model: "chroma-default",
              embedding_device: "cpu",
              retrieval_top_k: 5,
              answer_provider: "ollama",
              answer_model: "llama3:latest"
            };
          },
          getDoctor: async function() {
            return {
              status: "ok",
              checks: [
                { name: "sqlite", status: "ok", message: "SQLite ok" },
                { name: "chroma", status: "ok", message: "ChromaDB ok" }
              ]
            };
          },
          listSettingsPresets: async function() {
            return [
              { key: "cpu_rapido", label: "CPU Rapido" }
            ];
          },
          previewSettingsPreset: async function(key) {
            return { preset: key, changes: {} };
          },
          applySettingsPreset: async function(key) {
            return { ok: true, preset: key };
          },
          startIndexJob: async function(folderPath, rebuild) {
            return { job_id: "job-123", status: "started" };
          },
          getIndexJob: async function(jobId) {
            return { job_id: jobId, status: "completed", processed_count: 2, total_found: 2 };
          },
          cancelIndexJob: async function(jobId) {
            return { job_id: jobId, status: "cancelled" };
          },
          runBenchmarkCompare: async function(suitePath) {
            return {
              suite_name: "tcc_suite",
              strategies: {
                lexical: { mrr: 0.81, recall_at_3: 0.84 },
                vector: { mrr: 0.79, recall_at_3: 0.82 },
                hybrid: { mrr: 0.88, recall_at_3: 0.91 }
              }
            };
          }
        }
      };
    })();
  `;
}
