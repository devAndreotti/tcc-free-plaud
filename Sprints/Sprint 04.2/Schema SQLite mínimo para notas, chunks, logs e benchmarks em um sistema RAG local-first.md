# Schema SQLite mínimo para notas, chunks, logs e benchmarks em um sistema RAG local-first

## Visão geral

Para um sistema RAG **local-first** orientado a TCC, laboratório ou produto inicial, o melhor desenho não é o mais sofisticado, mas o que preserva três propriedades ao mesmo tempo: **rastreabilidade**, **reprodutibilidade** e **baixo atrito operacional**. Em termos práticos, isso significa separar a unidade documental canônica da unidade recuperável, registrar o processamento como trilha observável e tratar benchmark como dado de primeira classe, e não como um arquivo solto gerado no final do experimento.

A proposta abaixo assume **SQLite como banco operacional central**, mantendo notas, chunks, logs e benchmarks em um único arquivo. Essa escolha é coerente com stacks locais porque SQLite armazena texto, BLOBs e JSON em um formato simples de distribuir e manter; além disso, filtros por metadados podem ser acelerados com índices por expressão sobre `json_extract`, o que é particularmente útil em busca híbrida [1]. A literatura prática de RAG em produção também recomenda separar explicitamente o workflow offline de indexação do workflow online de recuperação, além de registrar consulta, chunks recuperados e filtros aplicados para diagnosticar falhas de retrieval [2].

> “The most reliable implementation pattern separates two workflows: an offline indexing workflow that prepares data for search, and an online retrieval workflow that answers queries.” [2]

> “Expression indexes on `json_extract` calls allow SQLite's query planner to use index scans when you filter by metadata fields, which is critical for hybrid search.” [1]

## Princípios de modelagem

O schema mínimo que eu realmente recomendaria para uso profissional ou acadêmico tem **cinco tabelas**. Embora seja possível reduzir para quatro, isso geralmente enfraquece o benchmark, porque uma execução agregada sem detalhe por consulta perde valor científico e dificulta depuração. O desenho abaixo procura ser o menor conjunto que ainda sustenta experimentação séria.

| Entidade | Papel no sistema | Motivo para existir separadamente |
|---|---|---|
| `notes` | representa a nota ou documento canônico | preserva a origem e a unidade documental antes do chunking |
| `chunks` | representa os segmentos recuperáveis derivados da nota | permite múltiplos chunks por nota e versionamento do recorte |
| `processing_logs` | registra ingestão, parsing, chunking, embedding e indexação | torna o pipeline auditável e facilita reprocessamento |
| `benchmark_runs` | registra uma execução completa de avaliação | permite comparar configurações de retrieval e chunking |
| `benchmark_queries` | guarda o resultado de cada consulta do benchmark | sustenta métricas como Recall@k, MRR e análise de erro |

A separação entre **nota** e **chunk** é a decisão mais importante. A nota é a fonte de verdade semântica e documental; o chunk é um derivado operacional voltado à recuperação. Em RAG sério, misturar ambos na mesma tabela funciona no começo, mas logo atrapalha deduplicação, atualização incremental, explicabilidade e citação de origem. A separação entre **benchmark agregado** e **benchmark por consulta** é a segunda decisão mais importante. Métricas médias são úteis, mas sozinhas não explicam por que o sistema errou.

## Tabela `notes`

A tabela `notes` deve representar a entidade documental canônica do seu pipeline. No contexto do seu projeto, isso pode corresponder a uma nota em Markdown derivada de áudio, imagem, PDF, texto puro ou web clipping. O ponto central é que a tabela guarda o **documento já estruturado**, e não apenas o arquivo bruto original.

| Coluna | Tipo | Restrição sugerida | Finalidade |
|---|---|---|---|
| `note_id` | `INTEGER` | `PRIMARY KEY` | chave substituta simples e eficiente no SQLite |
| `source_type` | `TEXT` | `NOT NULL` | tipo de origem, como `audio`, `pdf`, `image`, `text`, `web`, `manual` |
| `source_uri` | `TEXT` | opcional | caminho, URL ou identificador externo do artefato original |
| `external_id` | `TEXT` | opcional | id do sistema de origem, se houver |
| `title` | `TEXT` | opcional | título lógico da nota |
| `language_code` | `TEXT` | `NOT NULL DEFAULT 'pt-BR'` | idioma dominante da nota |
| `markdown_content` | `TEXT` | `NOT NULL` | conteúdo canônico já normalizado em Markdown |
| `content_hash` | `TEXT` | `NOT NULL` | hash do conteúdo canônico para deduplicação e sync incremental |
| `metadata_json` | `TEXT` | `NOT NULL DEFAULT '{}'` | metadados flexíveis, com `CHECK (json_valid(...))` |
| `status` | `TEXT` | `NOT NULL DEFAULT 'active'` | estado da nota, como `active`, `archived`, `deleted` |
| `created_at` | `TEXT` | `NOT NULL` | timestamp de criação |
| `updated_at` | `TEXT` | `NOT NULL` | timestamp de última atualização |

O rationale aqui é simples. A nota precisa de um identificador estável, de um conteúdo canônico e de um mecanismo de detecção de mudança. O campo `content_hash` cumpre papel decisivo em pipelines locais porque viabiliza **reprocessamento incremental**; quando o hash muda, você sabe que os chunks e embeddings derivados precisam ser refeitos. O campo `metadata_json`, por sua vez, evita explosão prematura de colunas. Em um TCC, isso ajuda a armazenar atributos como autor, disciplina, tags, data de captura, dispositivo de origem ou permissões sem sobre-normalizar o começo do projeto [1] [2].

## Tabela `chunks`

A tabela `chunks` representa as unidades efetivamente recuperáveis pelo retriever. Cada chunk pertence a exatamente uma nota, mas uma nota pode gerar vários chunks. Essa cardinalidade de **um para muitos** é o motivo técnico pelo qual vale a pena separar `notes` de `chunks` logo no início.

| Coluna | Tipo | Restrição sugerida | Finalidade |
|---|---|---|---|
| `chunk_id` | `INTEGER` | `PRIMARY KEY` | identificador do chunk |
| `note_id` | `INTEGER` | `NOT NULL REFERENCES notes(note_id) ON DELETE CASCADE` | vínculo com a nota de origem |
| `chunk_index` | `INTEGER` | `NOT NULL` | ordem do chunk dentro da nota |
| `section_path` | `TEXT` | opcional | trilha estrutural, como `Introdução > Metodologia` |
| `content` | `TEXT` | `NOT NULL` | texto do chunk |
| `token_count` | `INTEGER` | opcional | contagem de tokens para análise e packing |
| `char_start` | `INTEGER` | opcional | início do recorte no texto canônico |
| `char_end` | `INTEGER` | opcional | fim do recorte no texto canônico |
| `chunk_hash` | `TEXT` | `NOT NULL` | hash do chunk para reindexação e cache |
| `embedding_model` | `TEXT` | opcional | modelo usado para embedding |
| `embedding_ref` | `TEXT` | opcional | referência para store vetorial externo ou artefato local |
| `metadata_json` | `TEXT` | `NOT NULL DEFAULT '{}'` | metadados locais do chunk |
| `created_at` | `TEXT` | `NOT NULL` | timestamp de criação |

A recomendação profissional é manter no chunk tanto a **posição** quanto a **estrutura local**. Os campos `chunk_index`, `char_start`, `char_end` e `section_path` ajudam a explicar por que um trecho foi recuperado e a reconstruir contexto vizinho. Isso é útil em produto, mas é ainda mais importante em pesquisa, pois sustenta inspeção manual de falhas e avaliação de estratégias de chunking. A literatura prática de RAG destaca que chunking deve preservar fronteiras locais de contexto e, quando possível, estrutura de títulos, listas e tabelas [2].

Um ponto importante da proposta é que o schema **não exige** guardar o vetor em SQLite. Em uma arquitetura híbrida, você pode guardar apenas `embedding_model` e `embedding_ref`, deixando o vetor real em ChromaDB, `sqlite-vec` ou outra camada. Se depois você quiser uma versão SQLite-only, pode acrescentar `embedding_blob BLOB` sem mudar o coração do desenho.

## Tabela `processing_logs`

A tabela `processing_logs` é a trilha auditável do pipeline. Em um sistema local-first, ela substitui parte do papel que, em arquiteturas distribuídas, seria cumprido por filas, traces ou plataformas de observabilidade. A proposta aqui é adotar um log **semi-estruturado**, com uma coluna JSON para configuração e colunas explícitas para os campos que você mais consulta.

| Coluna | Tipo | Restrição sugerida | Finalidade |
|---|---|---|---|
| `log_id` | `INTEGER` | `PRIMARY KEY` | identificador do evento de log |
| `process_id` | `TEXT` | `NOT NULL` | agrupa eventos da mesma execução de pipeline |
| `note_id` | `INTEGER` | `REFERENCES notes(note_id) ON DELETE SET NULL` | alvo do processamento em nível de nota |
| `chunk_id` | `INTEGER` | `REFERENCES chunks(chunk_id) ON DELETE SET NULL` | alvo do processamento em nível de chunk |
| `stage` | `TEXT` | `NOT NULL` | estágio como `ingest`, `parse`, `normalize`, `chunk`, `embed`, `index` |
| `status` | `TEXT` | `NOT NULL` | estado como `started`, `success`, `error`, `skipped` |
| `pipeline_version` | `TEXT` | `NOT NULL` | versão lógica do pipeline ou commit/tag |
| `model_name` | `TEXT` | opcional | modelo relevante naquele estágio |
| `config_json` | `TEXT` | `NOT NULL DEFAULT '{}'` | parâmetros efetivos usados na execução |
| `message` | `TEXT` | opcional | mensagem humana curta |
| `error_text` | `TEXT` | opcional | erro expandido, stack trace resumido ou diagnóstico |
| `started_at` | `TEXT` | `NOT NULL` | início do estágio |
| `finished_at` | `TEXT` | opcional | fim do estágio |
| `duration_ms` | `INTEGER` | opcional | duração em milissegundos |

Essa tabela existe porque logs textuais soltos são ruins para consulta analítica. Quando você quiser responder perguntas como “quais notas falharam no embedding com o modelo X?” ou “quanto tempo o chunking levou em média nas últimas cem notas?”, uma tabela indexável resolve em SQL simples. A prática de RAG observável também recomenda guardar consulta, chunks recuperados e filtros aplicados para distinguir falha de recuperação de falha de geração; essa mentalidade de observabilidade deve começar já no pipeline offline [2].

## Tabela `benchmark_runs`

A tabela `benchmark_runs` registra cada execução completa de avaliação. Ela guarda o desenho experimental em nível agregado: qual corpus, qual dataset, qual estratégia de retrieval, qual chunking, qual embedding, qual `top_k` e quais métricas resumidas saíram daquela execução.

| Coluna | Tipo | Restrição sugerida | Finalidade |
|---|---|---|---|
| `benchmark_run_id` | `INTEGER` | `PRIMARY KEY` | identificador da execução de benchmark |
| `run_name` | `TEXT` | `NOT NULL` | nome amigável da execução |
| `dataset_name` | `TEXT` | `NOT NULL` | conjunto de consultas ou casos de teste |
| `corpus_snapshot` | `TEXT` | `NOT NULL` | versão, hash ou tag do corpus/indexado |
| `retrieval_strategy` | `TEXT` | `NOT NULL` | `dense`, `bm25`, `hybrid`, `rerank`, etc. |
| `chunking_strategy` | `TEXT` | `NOT NULL` | estratégia aplicada ao corpus avaliado |
| `embedding_model` | `TEXT` | `NOT NULL` | modelo de embedding usado na execução |
| `reranker_model` | `TEXT` | opcional | reranker, se houver |
| `top_k` | `INTEGER` | `NOT NULL` | profundidade de recuperação |
| `query_count` | `INTEGER` | `NOT NULL` | quantidade de consultas executadas |
| `pipeline_version` | `TEXT` | `NOT NULL` | versão do pipeline avaliado |
| `status` | `TEXT` | `NOT NULL` | `started`, `success`, `error` |
| `config_json` | `TEXT` | `NOT NULL DEFAULT '{}'` | configuração detalhada da execução |
| `metrics_json` | `TEXT` | `NOT NULL DEFAULT '{}'` | métricas agregadas adicionais |
| `started_at` | `TEXT` | `NOT NULL` | início da execução |
| `finished_at` | `TEXT` | opcional | fim da execução |
| `duration_ms` | `INTEGER` | opcional | duração total |
| `notes` | `TEXT` | opcional | observações analíticas |

O campo `corpus_snapshot` é especialmente importante em trabalhos acadêmicos. Benchmark sem identificação clara do corpus avaliado não é realmente reproduzível. Você pode preencher esse campo com um hash do conjunto de `content_hash` das notas indexadas, com uma tag de dataset, com um timestamp versionado ou mesmo com o nome de um diretório imutável de resultados. O importante é que a execução aponte para um estado recuperável do corpus.

## Tabela `benchmark_queries`

Esta é a tabela que transforma benchmark em evidência útil. Em vez de guardar só a média final de desempenho, você registra o resultado de cada consulta avaliada. Isso permite calcular métricas novas sem rerodar tudo, detectar outliers e inspecionar manualmente erros de retrieval.

| Coluna | Tipo | Restrição sugerida | Finalidade |
|---|---|---|---|
| `benchmark_query_id` | `INTEGER` | `PRIMARY KEY` | identificador da consulta avaliada |
| `benchmark_run_id` | `INTEGER` | `NOT NULL REFERENCES benchmark_runs(benchmark_run_id) ON DELETE CASCADE` | vínculo com a execução agregada |
| `query_id` | `TEXT` | opcional | id estável do caso de teste |
| `query_text` | `TEXT` | `NOT NULL` | texto da consulta |
| `expected_note_id` | `INTEGER` | opcional | nota esperada, se o benchmark for mapeado ao corpus |
| `expected_chunk_id` | `INTEGER` | opcional | chunk esperado, se houver granularidade fina |
| `expected_ref` | `TEXT` | opcional | referência esperada em formato livre |
| `retrieved_json` | `TEXT` | `NOT NULL DEFAULT '[]'` | lista JSON com ranks, ids e scores dos recuperados |
| `hit_at_k` | `INTEGER` | `NOT NULL` | indicador binário de acerto dentro do `k` |
| `reciprocal_rank` | `REAL` | opcional | valor individual para MRR |
| `latency_ms` | `INTEGER` | opcional | latência por consulta |
| `notes` | `TEXT` | opcional | comentário qualitativo sobre o caso |

A decisão de armazenar os recuperados em `retrieved_json` é pragmática. Um desenho ainda mais normalizado criaria uma sexta tabela apenas para itens ranqueados, mas isso geralmente é complexidade demais para a fase de fundação. Em um TCC ou MVP técnico, `retrieved_json` já guarda material suficiente para recalcular métricas e investigar erros. Se no futuro você quiser análise estatística mais profunda por posição de ranking, basta extrair isso para uma tabela filha sem quebrar o restante do schema.

## DDL de referência

Abaixo está um DDL de referência já pronto para implementação. Ele é enxuto, explícito e compatível com a estratégia de crescer sem retrabalho excessivo.

```sql
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA temp_store = MEMORY;

CREATE TABLE IF NOT EXISTS notes (
    note_id INTEGER PRIMARY KEY,
    source_type TEXT NOT NULL,
    source_uri TEXT,
    external_id TEXT,
    title TEXT,
    language_code TEXT NOT NULL DEFAULT 'pt-BR',
    markdown_content TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(metadata_json)),
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived', 'deleted')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    UNIQUE (source_type, source_uri)
);

CREATE TABLE IF NOT EXISTS chunks (
    chunk_id INTEGER PRIMARY KEY,
    note_id INTEGER NOT NULL REFERENCES notes(note_id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    section_path TEXT,
    content TEXT NOT NULL,
    token_count INTEGER,
    char_start INTEGER,
    char_end INTEGER,
    chunk_hash TEXT NOT NULL,
    embedding_model TEXT,
    embedding_ref TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(metadata_json)),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    UNIQUE (note_id, chunk_index)
);

CREATE TABLE IF NOT EXISTS processing_logs (
    log_id INTEGER PRIMARY KEY,
    process_id TEXT NOT NULL,
    note_id INTEGER REFERENCES notes(note_id) ON DELETE SET NULL,
    chunk_id INTEGER REFERENCES chunks(chunk_id) ON DELETE SET NULL,
    stage TEXT NOT NULL CHECK (stage IN ('ingest', 'parse', 'normalize', 'chunk', 'embed', 'index', 'delete', 'benchmark')),
    status TEXT NOT NULL CHECK (status IN ('started', 'success', 'error', 'skipped')),
    pipeline_version TEXT NOT NULL,
    model_name TEXT,
    config_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(config_json)),
    message TEXT,
    error_text TEXT,
    started_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    finished_at TEXT,
    duration_ms INTEGER
);

CREATE TABLE IF NOT EXISTS benchmark_runs (
    benchmark_run_id INTEGER PRIMARY KEY,
    run_name TEXT NOT NULL,
    dataset_name TEXT NOT NULL,
    corpus_snapshot TEXT NOT NULL,
    retrieval_strategy TEXT NOT NULL,
    chunking_strategy TEXT NOT NULL,
    embedding_model TEXT NOT NULL,
    reranker_model TEXT,
    top_k INTEGER NOT NULL CHECK (top_k > 0),
    query_count INTEGER NOT NULL CHECK (query_count >= 0),
    pipeline_version TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('started', 'success', 'error')),
    config_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(config_json)),
    metrics_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(metrics_json)),
    started_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    finished_at TEXT,
    duration_ms INTEGER,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS benchmark_queries (
    benchmark_query_id INTEGER PRIMARY KEY,
    benchmark_run_id INTEGER NOT NULL REFERENCES benchmark_runs(benchmark_run_id) ON DELETE CASCADE,
    query_id TEXT,
    query_text TEXT NOT NULL,
    expected_note_id INTEGER REFERENCES notes(note_id) ON DELETE SET NULL,
    expected_chunk_id INTEGER REFERENCES chunks(chunk_id) ON DELETE SET NULL,
    expected_ref TEXT,
    retrieved_json TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(retrieved_json)),
    hit_at_k INTEGER NOT NULL CHECK (hit_at_k IN (0, 1)),
    reciprocal_rank REAL,
    latency_ms INTEGER,
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_notes_source ON notes(source_type, source_uri);
CREATE INDEX IF NOT EXISTS idx_notes_content_hash ON notes(content_hash);
CREATE INDEX IF NOT EXISTS idx_notes_updated_at ON notes(updated_at);
CREATE INDEX IF NOT EXISTS idx_notes_metadata_origin ON notes(json_extract(metadata_json, '$.origin'));

CREATE INDEX IF NOT EXISTS idx_chunks_note_id ON chunks(note_id);
CREATE INDEX IF NOT EXISTS idx_chunks_note_chunk_index ON chunks(note_id, chunk_index);
CREATE INDEX IF NOT EXISTS idx_chunks_embedding_model ON chunks(embedding_model);
CREATE INDEX IF NOT EXISTS idx_chunks_metadata_section ON chunks(json_extract(metadata_json, '$.section_type'));

CREATE INDEX IF NOT EXISTS idx_processing_logs_process_id ON processing_logs(process_id);
CREATE INDEX IF NOT EXISTS idx_processing_logs_stage_status ON processing_logs(stage, status, started_at);
CREATE INDEX IF NOT EXISTS idx_processing_logs_note_id ON processing_logs(note_id);
CREATE INDEX IF NOT EXISTS idx_processing_logs_chunk_id ON processing_logs(chunk_id);

CREATE INDEX IF NOT EXISTS idx_benchmark_runs_dataset ON benchmark_runs(dataset_name, started_at);
CREATE INDEX IF NOT EXISTS idx_benchmark_runs_strategy ON benchmark_runs(retrieval_strategy, embedding_model, chunking_strategy);
CREATE INDEX IF NOT EXISTS idx_benchmark_queries_run_id ON benchmark_queries(benchmark_run_id);
CREATE INDEX IF NOT EXISTS idx_benchmark_queries_hit_at_k ON benchmark_queries(hit_at_k, latency_ms);
```

## Por que essas chaves e restrições fazem sentido

As **primary keys inteiras** são a melhor escolha para SQLite nessa fase porque simplificam joins, reduzem tamanho de índice e evitam carregar UUIDs em todas as relações. O uso de **foreign keys com `ON DELETE CASCADE` em `chunks`** evita lixo órfão quando uma nota é removida ou reconstruída. Já o uso de **`ON DELETE SET NULL` em logs e benchmarks** preserva a trilha histórica mesmo quando a entidade operacional some depois de uma limpeza ou reingestão. Esse detalhe é importante porque, em pesquisa aplicada, o histórico da execução às vezes importa mais do que a permanência do objeto original.

O campo `process_id` em `processing_logs` é outra escolha deliberada. Em vez de criar duas tabelas para `processing_runs` e `processing_events`, o schema mínimo usa um identificador textual agrupador. Isso reduz tabelas sem perder a possibilidade de reconstruir uma execução completa. Para a fase inicial do projeto, esse é um ótimo compromisso entre simplicidade e poder analítico.

## Como usar esse schema da melhor forma

Do ponto de vista profissional, a melhor prática é tratar `notes` e `chunks` como **estado derivável, mas estável**, e `processing_logs` e `benchmark_*` como **estado histórico append-only**. Em outras palavras, você pode recriar chunks quando muda a estratégia de chunking, mas não deve sobrescrever benchmark antigo só porque surgiu um modelo novo. Esse isolamento preserva comparabilidade longitudinal, o que é central em engenharia de ML e em pesquisa experimental [2].

Outra prática importante é manter **configuração detalhada em JSON**, porém apenas para o que muda de experimento para experimento. Parâmetros que você consulta o tempo todo, como `embedding_model`, `chunking_strategy`, `top_k` ou `status`, merecem colunas próprias. Parâmetros raros ou aninhados, como janelas de overlap, pesos de busca híbrida, thresholds de reranking ou flags experimentais, podem ficar em `config_json`. Isso equilibra ergonomia de SQL com flexibilidade.

Em sistemas realmente local-first, a combinação de `WAL` com um banco pequeno e bem indexado tende a funcionar muito bem para vários leitores e um escritor [1]. Ainda assim, vale a pena lembrar que SQLite é melhor quando você mantém o desenho simples, evita concorrência exagerada de escrita e faz operações de reindexação em lotes previsíveis.

## Exemplos profissionais e acadêmicos de uso

### Exemplo 1: cenário profissional de knowledge management pessoal

Imagine um aplicativo desktop que importa PDFs, transcrições de áudio e páginas web para gerar notas pesquisáveis. Cada artefato entra como uma linha em `notes`, com `source_type`, `source_uri`, `markdown_content` e `content_hash`. Depois do chunking, a aplicação grava múltiplas linhas em `chunks`, preservando `chunk_index`, `section_path` e `token_count`. A cada etapa do pipeline, eventos são escritos em `processing_logs`, permitindo que a interface mostre se uma nota falhou no OCR, na estruturação ou no embedding. Nesse cenário, o benchmark é usado internamente para comparar novas versões do retriever antes de promovê-las ao fluxo principal.

### Exemplo 2: cenário acadêmico de TCC ou laboratório

Agora considere um experimento em que você quer comparar três modelos de embedding e duas estratégias de chunking sobre um conjunto fixo de perguntas em português brasileiro. Cada combinação produz uma linha em `benchmark_runs`, identificada por `dataset_name`, `corpus_snapshot`, `embedding_model`, `chunking_strategy` e `top_k`. Os resultados individuais de cada pergunta são gravados em `benchmark_queries`, com `retrieved_json`, `hit_at_k`, `reciprocal_rank` e `latency_ms`. Esse desenho permite calcular médias globais, analisar consultas problemáticas e justificar decisões metodológicas no texto do TCC sem depender de reexecução constante.

## Exemplos de operações SQL

Os exemplos abaixo mostram como o banco seria usado na prática.

```sql
INSERT INTO notes (
    source_type,
    source_uri,
    title,
    markdown_content,
    content_hash,
    metadata_json
) VALUES (
    'pdf',
    'data/corpus/artigo_rag.pdf',
    'Artigo sobre chunking em RAG',
    '# Artigo sobre chunking em RAG\n\nTexto estruturado em Markdown...',
    'sha256:abc123',
    json_object('author', 'Ricardo', 'tags', json_array('rag', 'tcc', 'chunking'))
);
```

```sql
INSERT INTO chunks (
    note_id,
    chunk_index,
    section_path,
    content,
    token_count,
    char_start,
    char_end,
    chunk_hash,
    embedding_model,
    embedding_ref,
    metadata_json
) VALUES (
    1,
    0,
    'Introdução',
    'Chunk inicial sobre motivações de RAG local-first...',
    162,
    0,
    944,
    'sha256:def456',
    'bge-small-pt',
    'chromadb://collection/free-plaud/chunk/1',
    json_object('section_type', 'introduction')
);
```

```sql
INSERT INTO processing_logs (
    process_id,
    note_id,
    stage,
    status,
    pipeline_version,
    model_name,
    config_json,
    message,
    started_at,
    finished_at,
    duration_ms
) VALUES (
    'ingest-2026-04-04-001',
    1,
    'chunk',
    'success',
    'v0.1.0',
    'rules+overlap-128',
    json_object('chunk_size', 800, 'overlap', 128),
    'Chunking concluído com 12 segmentos.',
    '2026-04-04T10:00:00.000Z',
    '2026-04-04T10:00:01.250Z',
    1250
);
```

```sql
INSERT INTO benchmark_runs (
    run_name,
    dataset_name,
    corpus_snapshot,
    retrieval_strategy,
    chunking_strategy,
    embedding_model,
    top_k,
    query_count,
    pipeline_version,
    status,
    config_json,
    metrics_json,
    started_at,
    finished_at,
    duration_ms,
    notes
) VALUES (
    'baseline-bge-small-top5',
    'qa-ptbr-v1',
    'corpus@2026-04-04-sha256:xyz789',
    'dense',
    'markdown-headings-800-128',
    'bge-small-pt',
    5,
    50,
    'v0.1.0',
    'success',
    json_object('rerank', false),
    json_object('recall_at_5', 0.82, 'mrr', 0.71, 'avg_latency_ms', 43.8),
    '2026-04-04T11:00:00.000Z',
    '2026-04-04T11:00:12.400Z',
    12400,
    'Baseline textual para comparação com variantes futuras.'
);
```

```sql
INSERT INTO benchmark_queries (
    benchmark_run_id,
    query_id,
    query_text,
    expected_chunk_id,
    retrieved_json,
    hit_at_k,
    reciprocal_rank,
    latency_ms,
    notes
) VALUES (
    1,
    'q-017',
    'Qual estratégia de chunking melhora a recuperação em PDFs longos?',
    42,
    json('[{"rank":1,"chunk_id":42,"score":0.913},{"rank":2,"chunk_id":88,"score":0.851}]'),
    1,
    1.0,
    39,
    'Consulta respondida corretamente já na primeira posição.'
);
```

## Limites deliberados do schema mínimo

Todo schema mínimo faz concessões. Nesta proposta, a principal concessão é não modelar uma tabela específica para itens ranqueados do benchmark, nem uma tabela separada para `processing_runs`. Essa escolha reduz complexidade inicial, mas ainda deixa caminho claro para evolução. Se o projeto crescer e você quiser análises mais refinadas, os próximos passos naturais são introduzir `benchmark_ranked_items`, `processing_runs` e talvez um índice FTS5 para keyword search local.

Outra concessão é tratar o armazenamento vetorial como **agnóstico à implementação**. Isso é intencionalmente saudável para um projeto em fundação, porque evita acoplamento precoce entre o schema operacional e o store vetorial. Se o experimento mostrar que SQLite puro basta, ótimo; se ChromaDB, `sqlite-vec` ou outra solução se provar melhor, o banco principal continua útil do mesmo jeito.

## Recomendação final

Se eu estivesse iniciando esse projeto hoje, adotaria exatamente este desenho: `notes` como documento canônico, `chunks` como unidade de recuperação, `processing_logs` como trilha observável, `benchmark_runs` como execução agregada e `benchmark_queries` como evidência por consulta. Esse conjunto é pequeno o suficiente para não atrapalhar a implementação inicial e forte o suficiente para sustentar TCC, análise de erro, comparação de embeddings e evolução incremental do pipeline.

Em outras palavras, trata-se de um schema **mínimo, mas não ingênuo**. Ele respeita a natureza local-first do sistema, conversa bem com uma arquitetura modular e suporta tanto o lado de produto quanto o lado metodológico da pesquisa.

## Referências

[1]: https://www.sitepoint.com/local-first-rag-vector-search-in-sqlite-with-hamming-distance/ "Local-First RAG: Vector Search in SQLite with Hamming Distance"
[2]: https://unstructured.io/insights/rag-systems-best-practices-unstructured-data-pipeline "Best Practices for Implementing RAG Systems in Production | Unstructured"
