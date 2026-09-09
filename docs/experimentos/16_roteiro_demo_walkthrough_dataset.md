# Roteiro de Demonstracao Guiada (Demo Walkthrough) — TCC Free Plaud

Este documento estabelece o roteiro padronizado e cronometrado para apresentacao da banca e demonstracao pratica do **Free Plaud**, utilizando o acervo de validacao contido em `samples/manual validetion` e o corpus indexado em `data/corpus/notes`.

---

## 1. Visao Geral do Roteiro (Tempo Total: 7 a 10 Minutos)

| Bloco | Etapa | Foco da Demonstracao | Tempo Alocado |
|:---:|:---|:---|:---:|
| **1** | Diagnostico & Sanidade Local | Verificacao de integridade dos componentes offline | ~1 min |
| **2** | Ingestao & Notas Canonicas | Transformacao de documentos brutos em Markdown estruturado | ~2 min |
| **3** | Indexacao Dual & Chunking | FTS5 (Lexical) + ChromaDB (Vetorial) com offsets exatos | ~2 min |
| **4** | Consulta RAG & Citacoes Estritas | Resposta estruturada com spans auditaveis e abstinencia | ~2 min |
| **5** | Benchmark Experimental Comparativo | Metricas empiricas (MRR, Recall@k, Latencia) | ~2 min |
| **6** | Interface Desktop & Grafo 3D | Experiencia visual completa (PyWebView + React 19) | ~1 min |

---

## 2. Passo a Passo da Demonstracao

### Bloco 1: Diagnostico e Sanidade do Ambiente (`fp.ps1 doctor`)

* **Acao:** No terminal PowerShell do projeto, executar o verificador de integridade:
  ```powershell
  .\fp.ps1 doctor
  ```
* **Fala do Apresentador:**
  > "O Free Plaud foi construido sob o principio fundamental de Local-First. O comando doctor valida instantaneamente se o SQLite FTS5, o banco vetorial ChromaDB, os modelos de embedding e os provedores de inferencia estao operacionais na maquina local, garantindo privacidade total sem requisicao externa involuntaria."

---

### Bloco 2: Ingestao de Documento Multimodal e Nota Canonica

* **Acao:** Demonstrar a leitura de um documento de validacao real e sua estruturacao canonica:
  ```powershell
  uv run free-plaud ingest show "samples/manual validetion/01_frontmatter_yaml.md"
  uv run free-plaud notes save "samples/manual validetion/01_frontmatter_yaml.md"
  ```
* **Fala do Apresentador:**
  > "O modulo de ingestao analisa o arquivo de entrada (seja audio transcrito pelo Whisper, PDF ou Markdown do Obsidian), sanitiza metadados e gera uma nota canonica enriquecida com esquema Pydantic, gravando o .md e o .meta.json em data/corpus/notes."

---

### Bloco 3: Chunking Deterministico com Offsets de Caracteres

* **Acao:** Exibir os chunks gerados e indexar a pasta de notas no acervo dual:
  ```powershell
  uv run free-plaud retrieval chunks "samples/manual validetion/01_frontmatter_yaml.md"
  uv run free-plaud corpus index "data/corpus/notes"
  ```
* **Fala do Apresentador:**
  > "Diferente de sistemas RAG ingenuos, aqui cada fragmento de texto mantem o registro exato de char_start e char_end. Durante a indexacao, o chunk e persistido simultaneamente no SQLite com indice invertido BM25 e no ChromaDB como embedding denso."

---

### Bloco 4: Recuperacao Hibrida (RRF) e Resposta Fundamentada

* **Acao:** Realizar uma pergunta direta contra o acervo com fusao hibrida e citacoes de span:
  ```powershell
  uv run free-plaud retrieval ask "samples/manual validetion/01_frontmatter_yaml.md" --question "Qual e o papel do versionamento semantico?"
  ```
* **Fala do Apresentador:**
  > "A consulta executa a fusao Reciprocal Rank Fusion (k=60). A resposta e estritamente fundamentada: cada alegacao (claim) possui sua citacao vinculada ao intervalo de caracteres do documento original. Caso o acervo nao possua a informacao, o sistema aciona o guardrail no_answer para prevenir alucinacoes."

---

### Bloco 5: Comparacao Empirica de Metricas de Recuperacao

* **Acao:** Executar a suite automatizada de benchmark com metricas academicas:
  ```powershell
  .\fp.ps1 bench compare --suite "data/datasets/manual_validation/suite.json"
  ```
* **Fala do Apresentador:**
  > "Para a validacao cientifica do TCC, o harness de benchmark executa 16 consultas controladas contra 4 casos reais, comparando Lexico Puro, Vetorial Puro e Hibrido RRF. Na nossa suite, a recuperacao lexica e a hibrida atingem MRR de 0.968 e Recall@3 de 1.0, demonstrando como a persistencia dual supera o RAG vetorial isolado em dados pessoais estruturados."

---

### Bloco 6: Interface Desktop Integrada (React 19 + PyWebView)

* **Acao:** Inicializar o aplicativo desktop compilado ou via launcher:
  ```powershell
  .\fp.ps1 app
  ```
* **Demonstracoes Visuais no App:**
  1. **Aba Chat:** Enviar a mesma pergunta do Bloco 4 e expandir os cards de citacao mostrando os spans de texto com realce em amarelo.
  2. **Aba Grafo:** Alternar para a visualizacao 3D/2D de nos, mostrando as conexoes entre notas estruturadas por tags e similaridade semantica.
  3. **Aba Benchmark / Configuracoes:** Mostrar o painel de metricas em tempo real e a selecao dinamica de providers (Ollama, OpenAI-compatible, Extractive).

---

## 3. Resumo de Comandos Rapidos (Cheatsheet do Apresentador)

```powershell
# 1. Health check
.\fp.ps1 doctor

# 2. Ingestao e salvamento
uv run free-plaud notes save "samples/manual validetion/01_frontmatter_yaml.md"

# 3. Indexacao do corpus
uv run free-plaud corpus index "data/corpus/notes"

# 4. Pergunta com RAG
uv run free-plaud retrieval ask "samples/manual validetion/01_frontmatter_yaml.md" --question "Como aplicar versionamento semantico?"

# 5. Benchmark comparativo
.\fp.ps1 bench compare --suite "data/datasets/manual_validation/suite.json"

# 6. Abrir aplicacao Desktop
.\fp.ps1 app
```
