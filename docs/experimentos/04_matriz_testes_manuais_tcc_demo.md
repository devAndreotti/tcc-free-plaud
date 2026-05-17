# 04 - Matriz de Testes Manuais para TCC e Demo

## Objetivo

Este arquivo consolida uma bateria curta de testes manuais para:

- demonstrar o backend em reuniao, orientacao ou banca
- validar rapidamente se o fluxo principal continua funcional
- registrar evidencias de comportamento observavel do sistema

## Escopo

Esta matriz cobre o estado atual do backend ate a Sprint 07:

- ingestao
- nota canonica
- persistencia local
- chunking com offsets
- persistencia em SQLite
- retrieval lexical
- retrieval vetorial
- ask estruturado com citacao
- benchmark reproduzivel

## Pre-condicoes

Executar antes:

```powershell
cd D:\Dev\Repos\Own\tcc-free-plaud
cd pipeline
uv sync
```

Arquivo base que sempre existe no repositorio:

- `D:\Dev\Repos\Own\tcc-free-plaud\docs\arquitetura\Arquitetura_Backend.md`

Arquivos opcionais para benchmark real:

- `D:\Dev\Repos\Own\tcc-free-plaud\samples\manual validetion\...`

Observacao:

- a suite `data/datasets/manual_validation/suite.json` depende desses arquivos em `samples/`

## Matriz curta

| ID | Feature | Comando | Entrada | Resultado esperado |
| --- | --- | --- | --- | --- |
| T01 | Smoke do ambiente | `uv run free-plaud doctor` | nenhuma | mostra `workspace_dir`, `notes_dir`, `vector_store_dir`, `sqlite_path`, `embedding_model` |
| T02 | Estrutura do workspace | `uv run free-plaud tree` | nenhuma | lista `data`, `docs`, `pipeline`, `samples`, `Sprints` |
| T03 | Ingestao basica | `uv run free-plaud ingest show "D:\Dev\Repos\Own\tcc-free-plaud\docs\arquitetura\Arquitetura_Backend.md"` | markdown real do projeto | retorna `ingestion_id`, `source`, `media_type`, `sha256`, `preview` |
| T04 | Estruturacao de nota | `uv run free-plaud notes build "D:\Dev\Repos\Own\tcc-free-plaud\docs\arquitetura\Arquitetura_Backend.md"` | markdown real do projeto | imprime frontmatter + `# titulo` + `## Summary` + `## Raw Text` |
| T05 | Persistencia da nota | `uv run free-plaud notes save "D:\Dev\Repos\Own\tcc-free-plaud\docs\arquitetura\Arquitetura_Backend.md"` | markdown real do projeto | mostra `note_id`, `note_path`, `meta_path`; artefatos aparecem em `data/corpus/notes/` |
| T06 | Chunking com offsets | `uv run free-plaud retrieval chunks "D:\Dev\Repos\Own\tcc-free-plaud\docs\arquitetura\Arquitetura_Backend.md"` | markdown real do projeto | lista chunks com `chunk_id`, `v1`, `ofs=inicio:fim`, `tokens` |
| T07 | SQLite + vector store | `uv run free-plaud storage init` | nenhuma | mostra `sqlite_ok: True` e `vector_store_ok: True` |
| T08 | Ask lexical | `uv run free-plaud retrieval ask "D:\Dev\Repos\Own\tcc-free-plaud\docs\arquitetura\Arquitetura_Backend.md" --question "Qual e o papel do backend?"` | markdown real do projeto | retorna JSON com `status`, `answer`, `claims`, `citations`, `latency_ms` |
| T09 | Indexacao vetorial | `uv run free-plaud retrieval index "D:\Dev\Repos\Own\tcc-free-plaud\docs\arquitetura\Arquitetura_Backend.md"` | markdown real do projeto | retorna JSON com `note_id`, `chunks_indexed`, `embedding_model`, `vector_entries_count` |
| T10 | Busca vetorial | `uv run free-plaud retrieval semantic-search --query "papel do backend" --note-id "arquitetura-backend"` | vector store persistido | retorna JSON com `chunk_id`, `score`, `distance`, `matched_terms`, `term_coverage`, `snippet` |
| T11 | Ask vetorial | `uv run free-plaud retrieval ask "D:\Dev\Repos\Own\tcc-free-plaud\docs\arquitetura\Arquitetura_Backend.md" --question "Qual e o papel do backend?" --strategy vector` | markdown real do projeto | retorna JSON com citacoes e, quando necessario, `limitations` ou `reason_for_no_answer` |
| T12 | Benchmark demo | `uv run free-plaud benchmark run-demo "D:\Dev\Repos\Own\tcc-free-plaud\docs\arquitetura\Arquitetura_Backend.md"` | markdown real do projeto | retorna JSON com `benchmark_run_id`, `metrics` e `queries` |
| T13 | Benchmark por documento real | `uv run free-plaud benchmark run "D:\Dev\Repos\Own\tcc-free-plaud\samples\manual validetion\07_pdf_tecnico_estruturado.md" --dataset "D:\Dev\Repos\Own\tcc-free-plaud\data\datasets\manual_validation\07_pdf_tecnico_estruturado.json" --strategy lexical --export` | sample local + dataset versionado | retorna metricas e caminhos de exportacao JSON/CSV |
| T14 | Comparacao de estrategias | `uv run free-plaud benchmark compare --suite "D:\Dev\Repos\Own\tcc-free-plaud\data\datasets\manual_validation\suite.json"` | suite real local | retorna `summaries.lexical` e `summaries.vector` com `MRR`, `Recall@3`, `Recall@5`, `Recall@10`, `avg_query_latency_ms` |

## Gate de aceitacao minimo

Para considerar o backend demonstravel:

1. `T01` a `T07` devem passar sem erro
2. `T08` ou `T11` devem retornar JSON valido com citacoes ou abstention explicita
3. `T14` deve rodar fim a fim se a pasta `samples/` estiver presente

## O que observar na demo

### Ingestao e nota

- o sistema aceita `.md`, `.txt` e `.pdf`
- a nota gerada vira artefato persistido
- existe rastreabilidade via `note_id`, `source_path`, `content_hash`

### Retrieval

- lexical tende a ser mais forte no corpus real atual
- vector existe de verdade, mas ainda e baseline experimental
- o `ask` nao precisa responder sempre; `no_answer` e parte do comportamento correto

### Benchmark

- a comparacao entre estrategias ja e reproduzivel
- o sistema registra numeros uteis para o TCC
- o benchmark nao depende da UI

## Numeros baseline atuais da suite real

Rodando:

```powershell
uv run free-plaud benchmark compare --suite "D:\Dev\Repos\Own\tcc-free-plaud\data\datasets\manual_validation\suite.json"
```

O baseline observado foi:

- `lexical`: `MRR 0.96875`, `Recall@3 1.0`
- `vector`: `MRR 0.7916666666666666`, `Recall@3 0.9375`

Leitura:

- o pipeline vetorial existe e funciona
- o baseline vetorial atual ainda nao supera o lexical na suite real

## Teste automatizado recomendado

No ambiente Windows atual, usar `basetemp` unico por execucao:

```powershell
$tmp = "D:\Dev\Repos\Own\tcc-free-plaud\.pytest-tmp-$([guid]::NewGuid().ToString())"
uv run pytest --basetemp $tmp -q
```

Resultado observado nesta rodada:

- `81 passed`

## Uso no TCC

Esta matriz pode ser reutilizada para:

- descrever protocolo de validacao manual
- relatar comportamento observavel do sistema
- separar demonstracao funcional de avaliacao experimental

## Proximo passo recomendado

Depois desta matriz:

1. usar `T14` como checkpoint fixo antes de qualquer mudanca grande em retrieval
2. registrar novos ciclos em `docs/experimentos/05_...`, `06_...`
3. so depois abrir a trilha de integracao com UI
