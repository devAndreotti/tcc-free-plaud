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
- resposta estruturada com citação obrigatória
- política de `no_answer`

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

Na implementação atual da Sprint 06.1, o armazenamento vetorial local passa a usar `ChromaDB`
como baseline persistente em disco, desacoplado da interface e encapsulado em `storage/vector.py`.

## Banco vetorial

### Escolha atual

Usar `ChromaDB` como baseline.

Motivos:

- simples de integrar
- persiste localmente
- boa ergonomia em Python
- suficiente para a primeira rodada experimental

Na implementação atual da Sprint 06.1:

- o vector store local usa `ChromaDB PersistentClient`
- a coleção baseline é persistida em `data/results/vector_store`
- o backend registra `embedding_model` na indexação vetorial
- a busca semântica inicial já retorna `chunk`, `score` e `strategy`
- a camada de recuperação já prepara terreno para `hybrid` por compartilhamento do mesmo `chunk_id`

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

### Embedding e indexação vetorial

- `embedding_model`
- `vector_collection_name`
- `collection_dir`

Na implementação atual da Sprint 06.1, o fluxo vetorial passa a ser:

`note -> chunks -> embeddings -> ChromaDB -> semantic search`

Esse fluxo ainda não faz reranking nem busca híbrida, mas já substitui o placeholder anterior
por uma base vetorial local real e persistente.

Na evolução atual do backend:

- o provider de embeddings aceita `chroma-default`
- o provider também aceita modelos locais no formato `sentence-transformer:<model_name>`
- o benchmark pode sobrescrever o `embedding_model` por CLI para comparações reproduzíveis

Na evolução atual após o experimento `09_melhoria_ranking_falso_positivo.md`:

- `semantic_search()` continua sendo o path vetorial base e compartilhado
- `open_semantic_search()` passa a concentrar a política de busca aberta sem `note_id`
- reranking lexical-aware e poda leve de falso positivo ficam confinados ao fluxo aberto do CLI
- essa política ainda não deve ser promovida automaticamente para todos os consumidores vetoriais

Essa separação existe porque o problema validado nesta rodada foi:

- ruído em busca aberta multi-file

e não:

- falha do retrieval vetorial base por nota
- falha do `ask`
- falha do benchmark per-note

Se essa política precisar subir para o path compartilhado no futuro, a mudança deve passar por nova rodada
de validação cobrindo:

- `semantic-search --note-id`
- `retrieval ask --strategy vector`
- `retrieval ask --strategy hybrid`
- `benchmark compare`
- queries negativas, positivas e mistas equivalentes às do experimento `09`

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

Na implementação atual da Sprint 07, o benchmark passa a ter um runner reproduzível por CLI.
Ele carrega datasets JSON, executa consultas sobre uma nota canônica, calcula `MRR`,
`Recall@3`, `Recall@5`, `Recall@10` e latência, persiste a execução em SQLite e pode
exportar resultados em JSON e CSV. O runner já compara `lexical`, `vector` e `hybrid`
sem depender de interface gráfica.

Na evolução atual desse benchmark, o backend também passa a aceitar manifestos de suíte
(`suite.json`) para comparar `lexical`, `vector` e `hybrid` sobre múltiplos documentos reais
de forma repetível, gerando um resumo agregado por estratégia sem depender da interface.

### Resposta ask

- `query`
- `status`
- `no_answer`
- `answer`
- `claims`
- `citations`
- `limitations`
- `reason_for_no_answer`
- `used_sources`
- `latency_ms`

Na implementação atual da Sprint 5, a resposta `ask` nasce como um baseline local-first sobre
busca lexical com matching por token inteiro, não por substring. A partir da Sprint 06.2,
o mesmo contrato passa a aceitar estratégia `lexical`, `vector` ou `hybrid`, com abstention
explícita quando a evidência recuperada fica fraca ou mal ancorada. Isso permite:

- devolver payload estruturado para a UI desde cedo
- exigir citação por claim
- registrar abstention explícita quando a cobertura lexical for insuficiente
- registrar abstention explícita quando o retrieval vetorial falha em score, anchors nomeados ou grounding textual
- registrar abstention explícita quando a fusão híbrida não sustenta grounding mínimo
- manter rastreabilidade `note -> chunk -> citation` sem depender ainda de embeddings reais
- preparar o caminho para benchmark comparativo entre estratégias de recuperação

Na evolução atual, `hybrid` combina:

- ranking lexical
- ranking vetorial
- fusão por ranking reprodutível

sem introduzir reranker, LLM ou dependência de frontend.

Após a calibração registrada em `docs/experimentos/07_calibracao_fusao_hibrida.md`, o backend
passa a adotar como baseline default de `hybrid`:

- `lexical_weight = 1.5`
- `vector_weight = 1.0`
- `rank_constant = 60`

Essa configuração foi suficiente para empatar `hybrid` com `lexical` em `MRR` na suíte real
atual, mantendo `Recall@3 = 1.0`, sem precisar abrir reranking ainda.

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
