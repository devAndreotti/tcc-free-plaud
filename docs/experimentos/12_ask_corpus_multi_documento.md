# Experimento 12 - Ask corpus multi-documento

## Objetivo

Validar se o backend consegue indexar uma pasta pequena e responder uma pergunta que depende de evidencias
distribuidas entre tres arquivos, mantendo `citations`, `used_sources` e `no_answer`.

## Escopo

- Backend CLI apenas.
- Sem frontend, Tauri, audio, imagem ou LLM real.
- Corpus controlado em `data/results/validation_distributed_corpus`.
- Estrategia testada: `hybrid`.

## Comandos

```powershell
cd D:\Dev\Repos\Own\tcc-free-plaud\pipeline

$smokeRoot = Join-Path $env:TEMP ('free-plaud-corpus-ask-smoke-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $smokeRoot | Out-Null
$env:FREE_PLAUD_WORKSPACE_DIR = $smokeRoot
$env:FREE_PLAUD_DATA_DIR = Join-Path $smokeRoot 'data'
$env:FREE_PLAUD_NOTES_DIR = Join-Path $smokeRoot 'data\corpus\notes'
$env:FREE_PLAUD_DATASETS_DIR = Join-Path $smokeRoot 'data\datasets'
$env:FREE_PLAUD_RESULTS_DIR = Join-Path $smokeRoot 'data\results'
$env:FREE_PLAUD_SQLITE_PATH = Join-Path $smokeRoot 'data\results\free_plaud.sqlite3'
$env:FREE_PLAUD_VECTOR_STORE_DIR = Join-Path $smokeRoot 'data\results\vector_store'
$env:FREE_PLAUD_VECTOR_COLLECTION_NAME = 'corpus_ask_smoke'

uv run free-plaud corpus index "D:\Dev\Repos\Own\tcc-free-plaud\data\results\validation_distributed_corpus" --recursive
uv run free-plaud corpus ask --question "Qual message broker foi adotado, qual equipe ficou responsavel pelo runbook e qual padrao divide o pipeline em Bronze, Silver e Gold?" --strategy hybrid --top-k 6
uv run free-plaud corpus ask --question "Quais tecnologias o candidato domina para desenvolver apps mobile?" --strategy hybrid --top-k 6
```

## Resultado observado

Indexacao:

```json
{
  "index_status": "success",
  "total_found": 3,
  "indexed_count": 3
}
```

Pergunta distribuida:

```json
{
  "ask_status": "answer",
  "no_answer": false,
  "cited_note_count": 3,
  "reason": null
}
```

Resposta sintetizada:

```text
Para analise e consumo posterior, o pipeline deve organizar os dados segundo o padrao Medallion, dividido nas camadas Bronze, Silver e Gold. O pipeline de ingestao orientado a eventos adotou o RabbitMQ como message broker padrao para desacoplar a captura dos estagios de processamento interno. O runbook de operacao do broker ficou sob responsabilidade da equipe de Plataforma.
```

Pergunta irrelevante:

```json
{
  "ask_status": "no_answer",
  "no_answer": true,
  "cited_note_count": 0,
  "reason": "insufficient_hybrid_evidence"
}
```

Corpus vazio:

```json
{
  "ask_status": "no_answer",
  "no_answer": true,
  "reason": "empty_corpus"
}
```

## Decisao tecnica

O fluxo `corpus ask` fica separado de `retrieval ask <arquivo>` para preservar compatibilidade single-file.
O novo fluxo usa chunks persistidos no SQLite, busca vetorial aberta no Chroma e fusao hibrida existente.

## Limitacoes

- Ainda nao ha LLM para reescrita final; a resposta e composicao de claims extraidos.
- Ainda nao ha benchmark agregado dedicado para `corpus ask`.
- Persistencia SQLite e Chroma ainda nao e transacional entre stores.
