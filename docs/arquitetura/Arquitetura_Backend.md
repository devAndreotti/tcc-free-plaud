---
tags:
- tcc
- arquitetura
- backend
- pipeline
---

# Arquitetura Backend

## Papel do backend

O backend é o coração científico do projeto.

Ele precisa:

1. receber entradas multimodais
2. transformar entradas em notas Markdown consistentes
3. indexar as notas em banco vetorial local
4. executar a recuperação semântica
5. rodar o benchmark do TCC

## Estratégia recomendada

### Começar simples

O backend deve nascer como um monólito modular em Python, executável por CLI.

Antes de existir app desktop, o backend precisa funcionar sozinho.

### Stack recomendada

- `Python 3.12`
- `uv` para ambiente e dependências
- `Typer` para CLI
- `Pydantic` / `pydantic-settings` para configuração
- `SQLite` para metadados, logs e execuções de benchmark
- `ChromaDB` como baseline vetorial local
- `Pytest` para testes automatizados

## Módulos recomendados

```text
pipeline/
├── app/
│   ├── config.py
│   ├── logging.py
│   └── paths.py
├── ingest/
│   ├── watcher.py
│   ├── loaders.py
│   └── validators.py
├── providers/
│   ├── transcribe.py
│   ├── vision.py
│   ├── structure.py
│   ├── embed.py
│   └── answer.py
├── notes/
│   ├── schemas.py
│   ├── structurer.py
│   ├── markdown.py
│   └── metadata.py
├── retrieval/
│   ├── chunking.py
│   ├── indexer.py
│   ├── search.py
│   └── rag.py
├── benchmark/
│   ├── datasets.py
│   ├── metrics.py
│   ├── runners.py
│   └── reports.py
├── storage/
│   ├── sqlite.py
│   └── vector.py
└── cli.py
```

## Fronteiras de responsabilidade

### `ingest/`

Responsável por:

- descobrir arquivos
- validar formato
- extrair texto bruto
- decidir qual pipeline aplicar

Não deve:

- montar prompts de LLM
- gravar diretamente no banco vetorial

### `providers/`

Responsável por encapsular chamadas externas.

Cada adaptador deve esconder:

- SDK do provedor
- autenticação
- retries
- formatação de entrada e saída

Isso permite trocar:

- Gemini
- OpenAI
- Anthropic

sem contaminar o resto do sistema.

### `notes/`

Responsável por:

- schema da nota
- regras de estruturação
- montagem do Markdown final
- frontmatter
- persistência local do artefato canônico da nota

Essa camada é central para o TCC, porque a qualidade da estruturação afeta a recuperação depois.

### `retrieval/`

Responsável por:

- chunking
- embeddings
- indexação
- recuperação
- composição do contexto de resposta

Deve conter toda a lógica experimental de:

- chunk size
- overlap
- top-k
- thresholds

### `benchmark/`

Responsável por:

- executar cenários experimentais
- calcular métricas
- salvar resultados
- exportar CSVs e tabelas

Essa camada não deve depender da interface.

### `storage/`

Responsável por:

- persistência de configuração e logs em SQLite
- persistência vetorial

Na implementação atual da Sprint 4.2, o SQLite local passa a sustentar o schema mínimo de
`notes`, `chunks`, `processing_logs`, `benchmark_runs` e `benchmark_queries`.
Essa camada ainda não guarda embeddings reais, mas já preserva a rastreabilidade entre nota,
chunk, processamento e execução de benchmark.

## Banco vetorial

### Escolha atual

Usar `ChromaDB` como baseline.

Motivos:

- simples de integrar
- persiste localmente
- boa ergonomia em Python
- suficiente para a primeira rodada experimental

### Alternativa futura

Se a pergunta de escala ganhar peso, avaliar `LanceDB` como comparativo técnico.

## Modelagem de dados mínima

### Nota

- `note_id`
- `note_version`
- `source_type`
- `source_path`
- `source_name`
- `title`
- `summary`
- `topics`
- `tasks`
- `tags`
- `raw_text`
- `normalized_text`
- `structured_markdown`
- `content_hash`
- `created_at`
- `provider`
- `model`

### Chunk

- `chunk_id`
- `note_id`
- `note_version`
- `chunk_index`
- `char_start`
- `char_end`
- `chunk_size`
- `overlap`
- `chunk_text`
- `token_count`
- `strategy`
- `normalized_text_sha256`
- `text_sha256`
- `pipeline_version`

Na implementação atual da Sprint 4.1, o chunking deve ocorrer sobre `normalized_text`, e não sobre `raw_text`.
Isso existe para manter offsets reproduzíveis e preparar a rastreabilidade `note -> chunk` antes da camada de persistência em SQLite.

### Execução de benchmark

- `experiment_id`
- `dataset_name`
- `embedding_model`
- `chunk_size`
- `overlap`
- `top_k`
- `latency_ms`
- `mrr`
- `recall_at_3`
- `recall_at_5`
- `recall_at_10`

## Ordem de implementação backend

### Sprint 1

- config
- schemas
- ingestão de texto/PDF
- estruturação em Markdown

### Sprint 2

- chunking
- embeddings
- indexação vetorial
- pergunta + resposta com citação

### Sprint 3

- harness de benchmark
- exportação de resultados

### Sprint 4

- áudio
- imagem

## Testes essenciais

### Antes de qualquer UI

1. teste de parsing de texto e PDF
2. teste de schema da nota
3. teste de chunking
4. teste de indexação e recuperação
5. teste de resposta com citação obrigatória
6. teste de runner de benchmark

## Decisões para evitar retrabalho

1. não acoplar benchmark ao fluxo de interface
2. não misturar texto bruto e nota estruturada no mesmo campo
3. não embutir prompts diretamente em módulos de ingestão
4. não fazer Tauri depender de lógica que deveria ficar em Python

## Primeiro objetivo técnico realista

O primeiro marco forte do backend é:

> Receber um PDF, gerar uma nota Markdown estruturada, indexar no banco vetorial e responder uma pergunta com citação da nota.

Se isso estiver funcionando com testes e script de benchmark simples, o projeto já saiu da fase conceitual.
