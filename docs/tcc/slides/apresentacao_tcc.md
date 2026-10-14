---
marp: true
theme: default
paginate: true
header: 'TCC — Escólio: Pipeline Local-First de IA para Gestão do Conhecimento'
footer: 'Bacharelado em Engenharia / Ciência da Computação'
backgroundColor: #f8fafc
color: #0f172a
style: |
  section {
    font-family: 'Segoe UI', system-ui, sans-serif;
    padding: 40px 60px;
  }
  h1 {
    color: #1e293b;
  }
  h2 {
    color: #2563eb;
  }
  table {
    font-size: 0.85em;
  }
  code {
    background-color: #e2e8f0;
    color: #0f172a;
  }
---

<!-- _class: lead -->
# Escólio
### Desenvolvimento e Avaliação de um Pipeline de IA para Captura e Recuperação Semântica de Conhecimento Pessoal

**Autor:** Ricardo Andreotti  
**Foco:** Local-First, RAG Híbrido, Preservação Estrita de Citações e Privacidade

---

## 1. Contexto e Motivação

* **Problema do Conhecimento Pessoal (PKM):**
  * Grande volume de dados capturados (áudios, reuniões, PDFs, notas soltas).
  * Informação fica isolada ou exige manutenção manual excessiva.
* **Limitações das Soluções Existentes em Nuvem:**
  * Dependência de servidores de terceiros e risco de privacidade com dados pessoais/sensíveis.
  * Alucinação de modelos generativos sem ancoragem determinística em fontes.
* **Proposta do Escólio:**
  * Arquitetura 100% local-first para ingestão, transcrição, indexação e RAG.
  * Citação auditável com offsets de caracteres exatos e guardrail anti-alucinação.

---

## 2. Perguntas de Pesquisa

* **P1 (Privacidade & Viabilidade Local):**
  * É viável executar todo o ciclo de ingestão multimodal e recuperação vetorial localmente com hardware convencional de consumo?
* **P2 (Estratégia de Recuperação):**
  * Qual o impacto relativo do Retrieval Léxico (BM25 via SQLite FTS5) vs. Vetorial (ChromaDB) vs. Fusão Híbrida (RRF) em notas pessoais em português?
* **P3 (Groundedness & Anti-Alucinação):**
  * A verificação determinística de spans de texto reduz a taxa de alucinações e abstém respostas quando o acervo é insuficiente?

---

## 3. Arquitetura do Sistema

`
  [ Entradas ] ────────► [ Pipeline Core (Local) ] ────────► [ Persistência Dual ]
  • Áudio (Whisper)        • Limpeza e Normalização            • SQLite FTS5 (Lexical)
  • Markdown/Obsidian      • Chunking com Char Offsets         • ChromaDB (Embeddings)
  • PDFs e Textos          • Reciprocal Rank Fusion (k=60)
                                    │
                                    ▼
                         [ Interfaces Unificadas ]
                   • Typer CLI | Textual TUI | React Desktop
`

* **Backend:** Python 3.12, UV, Pydantic v2, SQLite, ChromaDB, SentenceTransformers.
* **Frontend / Desktop:** React 19, Vite, Tailwind CSS, PyWebView (Edge WebView2).

---

## 4. Persistência Dual e AutoRAG Híbrido

* **SQLite FTS5 (BM25):**
  * Busca exata de palavras-chave, nomes de métodos, acrônimos e metadados estruturados.
* **ChromaDB (Embeddings Densos):**
  * Recuperação semântica baseada em proximidade vetorial e intenção conceitual.
* **Reciprocal Rank Fusion (RRF =60$):**
  * Combinação de pontuações ordinais sem viés de normalização de escala:
  RRF\_Score(d) = \sum_{m \in M} \frac{w_m}{k + r_m(d)}

---

## 5. Resultados Experimentais (Benchmark)

Avaliação empírica no corpus de validação real (16 consultas balanceadas):

| Estratégia de Recuperação | MRR | Recall@3 | Recall@5 | Latência Média |
|:---|:---:|:---:|:---:|:---:|
| **Léxica Pura (SQLite FTS5 BM25)** | 0.968 | 1.000 | 1.000 | **~26 ms** |
| **Vetorial Pura (ChromaDB)** | 0.781 | 0.937 | 0.937 | ~937 ms |
| **Híbrida RRF (k=60 - Padrão)** | **0.968** | **1.000** | **1.000** | ~893 ms |

* *Conclusão:* A fusão híbrida mantém a precisão léxica máxima e cobre consultas conceituais sem perda de revocação.

---

## 6. Demonstração Prática do Artefato

* **CLI & TUI:**
  * Diagnóstico de saúde do sistema (p.ps1 doctor).
  * Indexação e benchmark reproduzível (p.ps1 bench compare).
* **Desktop App (React 19 + PyWebView):**
  * Chat em tempo real com citações expansíveis e badges de relevância.
  * Grafo de Conhecimento interativo (ForceGraph 2D/3D).
  * Painel de Benchmark e configurações dinâmicas de modelos e providers.

---

## 7. Conclusões e Contribuições

* **Conclusões:**
  * Modelos de linguagem locais e indexação híbrida são suficientes para PKM sem vazamento de dados.
  * Citações auditáveis com spans determinísticos garantem confiabilidade acadêmica e profissional.
* **Entregáveis do Projeto:**
  * Artigo e Monografia acadêmica em docs/tcc/texto/TCC.md.
  * Pipeline aberto com harness de benchmark automatizado e suite de testes com 100% de aprovação.
  * Aplicativo multiplataforma com instalador standalone e CLI portátil.

---

<!-- _class: lead -->
# Perguntas & Respostas
### Obrigado!

**Repositório:** devAndreotti/tcc-free-plaud
