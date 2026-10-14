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
│   ├── validators.py
│   └── obsidian_cleaner.py
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

Ferramentas auxiliares opcionais desta camada podem preparar staging seguro antes da ingestão
canônica. Na implementação atual do cleaner de Obsidian:

- `ingest/obsidian_cleaner.py` é uma ferramenta explícita, chamada sob demanda
- a fonte Obsidian permanece `read-only`
- o output limpo vai para uma área de staging dentro do repositório
- `dataviewjs` é tratado por parsing estático e heurístico, sem executar JavaScript
- a limpeza não roda automaticamente para Markdown comum do pipeline

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

Na evolução de corpus multi-documento, o SQLite também expõe leitura de `chunks` e `notes`
persistidos para que o fluxo `corpus ask` consiga recuperar evidências do acervo inteiro sem
depender de um único arquivo carregado em memória.

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

Na indexação de pastas de corpus, o `note_id` é derivado do nome do arquivo mais um hash curto
do caminho relativo ao root indexado. Isso evita colisão entre arquivos com o mesmo título em
pastas diferentes, preservando estabilidade de reindexação dentro do mesmo vault. Na indexação
de arquivo isolado, o ID legível baseado no nome do arquivo continua válido por compatibilidade
operacional.

Reindexar uma nota (`reindex_note`) mantém o `note_id`: a raiz da indexação original não é
guardada, então ela é recuperada comparando o hash do caminho relativo com cada pasta acima do
arquivo (`find_note_root`). Sem isso, reindexar trocava o id, refazia todos os embeddings e
deixava a UI apontando para um id que não existia mais.

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

- o provider de embeddings aceita `chroma-default`. O wrapper usa o `ONNXMiniLM_L6_V2` do Chroma
  direto e reaproveita a instância: o `DefaultEmbeddingFunction` cria uma nova a cada chamada e
  recarrega a sessão ONNX (~1,5 s por pergunta e por lote). Um texto só (a pergunta) usa uma
  segunda instância, com a mesma sessão, que não completa a entrada até 256 tokens: o vetor é
  idêntico e a inferência fica ~5x mais rápida
- o app desktop aquece o Chroma e o embedder em segundo plano ao abrir, para a primeira
  pergunta não pagar o carregamento
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

A comparação (`benchmark compare`, TUI e app) roda em `results/benchmark_compare/<suite>/`, com
SQLite (`benchmark.sqlite3`) e Chroma próprios. O histórico (`benchmark_queries`) referencia
notes e chunks, então as notas da suite ficam nesse banco, nunca no corpus do usuário. Antes, as
notas da suite iam para o SQLite principal sem vetores no Chroma principal: apareciam em Notas e
no chat, e o Doctor acusava corpus inconsistente. A rodada híbrida reaproveita os vetores que a
vetorial acabou de gravar (mesmo chunk_id, mesmo embedder), o que não muda nenhuma métrica.

Depois das rodadas por nota, a comparação faz a passada no corpus inteiro (`run_corpus_benchmark`):
todas as notas da suite num corpus só, buscadas com `retrieve_corpus_hits`, a mesma busca do chat,
sem filtro por nota e com profundidade 10 (com o top-k do chat, Recall@5 e @10 repetiriam o @3). Um
trecho só é relevante se for da nota do caso. Cada pergunta passa também por
`answer_corpus_with_citations` sem provedor gerativo, e as perguntas do `negative_dataset_path`
da suite (category `negativa`) medem se o chat se abstém quando o corpus não tem a resposta. O
resumo por estratégia traz MRR e Recall@5 com intervalo bootstrap de 95%, nDCG@10, latência p50/p95
e a decisão de responder ou se abster. A passada por nota continua no relatório como teto.

O `benchmark answer-eval` indexa a nota avaliada em `results/benchmark_compare/answer-eval/`, não
no Chroma do corpus. O Chroma roda com `anonymized_telemetry=False`.

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
- `debug` opcional, apenas quando pedido, com hits recuperados, scores, termos, distância,
  fonte e motivo de abstenção

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

Na evolução de corpus multi-documento, o backend adiciona `Escólio corpus ask` como fluxo
separado de `retrieval ask <arquivo>`. O comando consulta todos os chunks persistidos no SQLite
e no Chroma, permite `lexical`, `vector` e `hybrid`, e retorna o mesmo contrato `AskResponse`
com `citations` e `used_sources` atravessando mais de uma nota quando a pergunta exige
stitching distribuído. O `retrieval ask` continua single-file por compatibilidade experimental.

Antes de buscar, o `corpus ask` se abstém com `query_term_not_in_corpus` quando um termo de
conteúdo da pergunta não casa com nenhuma palavra do corpus (vocabulário do FTS via `fts5vocab`,
em cache até a próxima indexação). Casa pela mesma regra de radical da busca, por raiz comum de 6
letras (responsavel / responsabilidade) e parte a parte em identificadores com `_`. A limitação
diz qual termo faltou. Os anchors nomeados ignoram a maiúscula da primeira palavra ("Quantos",
"Quem") e as interrogativas são stopwords; a limpeza das afirmações mantém o `_` de
identificadores; perguntas de comparação ("diferença entre X e Y") pedem uma afirmação por lado.
No benchmark do corpus inteiro, a híbrida responde 97% das 39 positivas (antes 82%). Nas
negativas, a abstenção foi de 50% para 80% no lote usado no ajuste (`neg-*`, 10 perguntas) e de
42% para 54% num lote escrito depois e medido sem ajuste (`neg2-*`, 24 perguntas). No lote novo, a
regra pega todas as perguntas fora do domínio, mas só 7 de 18 quase-acertos (o assunto está no
corpus, o fato perguntado não): o chat devolve uma frase do assunto sem o tipo de dado pedido
(número, data, versão). Somando os 73, a decisão certa foi de 64% para 81%.

Na evolução operacional do corpus, o backend também passa a expor `corpus status`, `corpus reset`
e `corpus rebuild`. Esses comandos diagnosticam divergência SQLite/Chroma, limpam apenas notas,
chunks e a collection vetorial ativa mediante `--yes`, e reconstroem o acervo a partir de arquivo
ou pasta controlada. O `corpus ask` filtra hits vetoriais cujo `chunk_id` não exista no SQLite antes
de montar `citations`, `used_sources` e `claims`, evitando resposta baseada em vetor obsoleto.

Na evolução de consistência e performance do corpus, o SQLite mantém um índice FTS5/BM25
persistido em `chunks_fts`. O `corpus ask` usa esse índice para a etapa lexical de `lexical` e
`hybrid`, evitando varrer todos os chunks em Python. O índice FTS é atualizado junto com
`replace_chunks_for_note()`, limpo em `reset` e auto-reconstruído quando um banco antigo ainda não
possui FTS sincronizado.

Na evolução de performance do corpus, a indexação de pastas passa a escolher entre commit
`atomic` e `microbatch`. O modo `auto` mantém operação atômica para corpus pequeno e usa
micro-lotes para pastas maiores, gravando Chroma e SQLite por grupos de arquivos/chunks. Isso
torna `corpus status` e `corpus ask` úteis antes do fim da indexação, com o tradeoff explícito
de corpus parcial quando uma indexação ou rebuild grande é interrompido. O TUI e o menu terminal
também passam a reaproveitar embedder e vector store no processo, evitando pagar o cold-start de
SentenceTransformer em cada pergunta.

Na evolução de configuração operacional, o app passa a separar preferências de usuário e overrides
técnicos. Preferências editáveis pelo TUI, menu terminal e `Escólio config` ficam em
`data/results/user_settings.json`; variáveis `ESCOLIO_*` e `.env` continuam tendo precedência.
O V1 cobre device/modelo de embedding, `top_k`, estratégia default do Ask, chunk size/overlap,
modo de commit do corpus, pasta padrão, recursividade, batch de embedding e número de workers.
Ao alterar modelo ou device pelo app, o `CorpusRuntime` limpa cache de embedder/vector store para
evitar reutilizar runtime antigo.

Na evolução atual das configurações, `escolio.app.settings_catalog` vira o catálogo canônico
para UI real, TUI Textual e menu terminal. Ele define rótulo humano, descrição, grupo, tipo,
opções, recomendação, storage (`user_settings.json` ou `.env`) e warnings operacionais. Assim,
`retrieval_top_k=4`, `default_chunk_size=800` e `default_chunk_overlap=120` aparecem de forma
consistente como "Chunks por pergunta", "Tamanho do chunk" e "Sobreposição" em todas as
superfícies. Segredos continuam fora de `user_settings.json`.

Na evolução generativa do RAG, `corpus ask` mantém recuperação e validação de citações como gate
obrigatório antes de qualquer chamada de IA. Se o corpus estiver vazio, se não houver hits, ou se
os hits não gerarem claims citáveis, o fluxo retorna `no_answer` sem chamar provider generativo.
Quando há evidência validada, um provider OpenAI-compatible pode reescrever a resposta final a
partir de contextos citáveis. O mesmo adaptador cobre Ollama, LM Studio e APIs remotas compatíveis
com `/chat/completions`. A API key fica apenas em `.env` ou variável `ESCOLIO_ANSWER_API_KEY`;
`user_settings.json` guarda somente provider, modelo, base URL, temperatura e timeout.

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


## Sprint 09 — captura e transcrição local

A fachada `tui.actions` reexporta as operações de `tui.audio_actions`;
`CorpusRuntime.get_audio_runtime()` fornece o mesmo runtime por diretório.
Captura, download e transcrição não começam ao importar o aplicativo.

`ingest/audio_capture.py` mantém callback limitado à cópia em fila limitada.
Um worker converte mono float32, usa SoXR contínuo a 16 kHz e salva WAV PCM16.
Silero ONNX CPU mantém estado e contadores absolutos: limiares 0,5/0,35, fala
mínima 250 ms, silêncio 300 ms, margem 100 ms e cortes de até 30 segundos.
Parada descarrega amostras pendentes; cancelamento fecha o dispositivo e worker.
Falhas de dispositivo, fila e escrita são explícitas.

`AudioRuntime` serializa inferência e reutiliza os adaptadores. Faster-Whisper
small usa `pt`, CUDA int8_float16 ou CPU int8; auto permite um retry CPU em
falha de GPU. SenseVoice (zh/en/ja/ko/yue) e Moonshine (en) usam sherpa-onnx
CPU. Nenhum dos dois oferece português. GGUF permanece catálogo/download.
O catálogo empacotado fixa revisão, licença, tamanho e SHA-256; download é
explícito e publica o diretório apenas depois de validar todos os artefatos.

Arquivos WAV/MP3/M4A/OGG entram no loader. JSON associado guarda áudio de
origem, hash, modelo/revisão, texto bruto e limpo, decisões de limpeza,
intervalos absolutos e tempos nativos de palavras quando disponíveis.
Sem alinhamento, usa limites VAD sem criar tempos de palavras. A nota mantém
texto bruto e normaliza o limpo. Gravações e resultados ficam no diretório
ignorado `data/results/audio`; arquivos de origem não são sobrescritos.

Comandos (em `pipeline`, após `uv sync --locked --extra audio --dev`):

```powershell
uv run escolio ingest audio models
uv run escolio ingest audio download silero-vad
uv run escolio ingest audio download whisper-small
uv run escolio ingest audio verify whisper-small
uv run escolio ingest audio transcribe caminho.wav --language pt
uv run escolio ingest audio record --seconds 10
uv run escolio ingest audio record --seconds 10 --index
```

Gravação parada entra na fila STT. `--index` solicita indexação do snapshot
limpo associado ao JSON; a opção é explícita. Cancelamento durante inferência
nativa é observado entre segmentos e antes de publicar o resultado.
Avaliação WER/CER e tempo real fica em `benchmark/audio.py`; evidências e
limitações em `docs/spec-kit/AUDIO_VALIDATION.md`. Watcher, dropzone e novas
interfaces permanecem fora desta entrega.
