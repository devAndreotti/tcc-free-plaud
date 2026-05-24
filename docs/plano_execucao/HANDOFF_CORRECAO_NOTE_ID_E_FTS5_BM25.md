# Handoff - Correcao de `note_id`/dedupe e FTS5/BM25 no corpus ask

Criado em 2026-05-24.

Status: implementado na branch `feat/corpus-index-and-ask` em 2026-05-24.

Este arquivo nasceu como plano de implementacao e passa a servir como handoff tecnico da slice.

Objetivo: resolver dois problemas reais medidos no vault Obsidian:

- `note_id` colidindo entre arquivos de mesmo nome em pastas diferentes, gerando perda logica de notas e vetores stale;
- `hybrid` lento porque a parte lexical varre todos os chunks em Python.

## Evidencia real

Fonte medida:

```text
C:\Users\ricar\OneDrive\Documentos\Obsidian Vault\Obsidian-Core
```

Descoberta:

| metrica | valor |
| --- | ---: |
| arquivos totais no vault | 786 |
| arquivos suportados pelo corpus | 470 |
| arquivos ignorados | 317 |
| `note_id` unicos gerados hoje | 448 |
| `note_id` com colisao | 22 |
| arquivos envolvidos em colisao | 44 |

Exemplos de colisao:

| `note_id` atual | arquivos |
| --- | --- |
| `ai` | `AI\AI.md`, `AI\🤖 AI.md` |
| `area-de-ti` | `Área de TI\Área de TI.md`, `Área de TI\🔒📁 Área de TI.md` |
| `arquitetura-do-perssua` | `Excalidraw\Arquitetura do Perssua.md`, `Área de TI\Arquitetura\Arquitetura do Perssua.md` |
| `diario` | `Templates\Diário.md`, `Wiki Pessoal\Diário\Diário.md` |

Timing medido no corpus atual com `3070` chunks, SentenceTransformer CUDA quente:

| etapa | tempo |
| --- | ---: |
| `list_chunks()` | 90-315 ms |
| `lexical_search_hits()` Python | 13.753-14.564 ms |
| `semantic_search()` vector CUDA quente | 234-737 ms |
| `hybrid_search()` total | 14.414-15.234 ms |
| `get_notes_by_id()` | 4-20 ms |

FTS5 esta disponivel no SQLite local:

```text
ENABLE_FTS5=True
CREATE VIRTUAL TABLE ... USING fts5(...) ok
```

Resultado medido apos implementacao no corpus ativo com `3070` chunks:

| etapa | antes | depois | ganho |
| --- | ---: | ---: | ---: |
| lexical | 13.852 ms media | 94,9 ms media | 146x |
| hybrid corpus ask | 14.662 ms media | 1.170 ms media | 12,5x |
| validacao de ids SQLite | 162 ms `list_chunks()` | 5,6 ms `list_chunk_ids()` | 28,8x |

Resultado medido no vault real em banco isolado:

| metrica | antes | depois |
| --- | ---: | ---: |
| arquivos suportados | 470 | 470 |
| `note_id` unicos | 448 | 470 |
| `note_id` duplicados | 22 | 0 |
| notas persistidas apos indexacao | 448 no corpus antigo | 470 |
| chunks SQLite | 3070 no corpus antigo | 3120 |
| chunks FTS | nao existia | 3120 |
| chunks Chroma | 3120 com 50 stale | 3120 com 0 stale |
| status | `inconsistent` | `clean` |

## Causa raiz 1 - `note_id`/dedupe

Arquivo:

```text
pipeline/src/free_plaud/notes/metadata.py
```

Comportamento atual:

```python
def build_note_id(path: Path) -> str:
    normalized = unicodedata.normalize('NFKD', path.stem)
    ascii_only = normalized.encode('ascii', 'ignore').decode('ascii')
    slug = re.sub(r'[^a-zA-Z0-9]+', '-', ascii_only.lower())
    return slug.strip('-') or 'note'
```

Problema:

- usa apenas `path.stem`;
- remove emojis/acentos;
- arquivos diferentes com mesmo titulo viram mesmo `note_id`;
- `notes.note_id` e chave primaria;
- `upsert_note()` sobrescreve a nota anterior;
- `replace_chunks_for_note()` apaga chunks anteriores do mesmo `note_id`;
- `chunk_id` tambem inclui `note_id`, entao a colisao se propaga para Chroma.

Por que gera stale vector:

- no modo atomic, todos os arquivos sao preparados e depois gravados em lote;
- se dois arquivos com mesmo `note_id` estao no mesmo lote, Chroma recebe chunks dos dois;
- SQLite fica apenas com a ultima nota/chunks daquele `note_id`;
- vetores do primeiro arquivo ficam sem chunk correspondente no SQLite;
- `corpus status` mostra `stale_vector_chunks_count`.

Na medicao real:

| modo | stale vectors |
| --- | ---: |
| atomic isolado | 50 |
| microbatch isolado | 26 |
| corpus atual | 50 |

Microbatch reduz alguns stales por acaso quando colisores caem em lotes diferentes, mas nao corrige a causa.

## Causa raiz 2 - `hybrid` lento

Arquivos:

```text
pipeline/src/free_plaud/corpus/ask.py
pipeline/src/free_plaud/retrieval/search.py
pipeline/src/free_plaud/storage/sqlite.py
```

Fluxo atual:

```text
answer_corpus_with_citations()
  -> list_chunks(connection)
  -> hybrid_search(question, chunks, ...)
       -> lexical_search_hits(question, chunks, ...)
            -> for chunk in chunks:
                 match_terms_in_text(...)
       -> semantic_search(...)
```

Problema:

- `hybrid` sempre carrega todos os chunks;
- `lexical_search_hits()` tokeniza e compara todos os chunks em Python;
- cada termo da pergunta testa variações/stem-like contra termos do chunk;
- custo cresce linearmente com corpus;
- no vault real, a parte lexical sozinha custa cerca de `14s`.

Conclusao:

- vetor CUDA nao e gargalo principal do ask quente;
- gargalo atual e lexical Python;
- `hybrid` fica lento porque depende da busca lexical lenta.

## Decisao tecnica

Implementar primeiro `note_id` estavel por caminho. Depois implementar FTS5/BM25.

Motivo:

- FTS antes de corrigir `note_id` indexaria corpus logicamente errado;
- `note_id` novo exige rebuild do corpus;
- rebuild limpo tambem vai popular FTS novo sem precisar migrar dado ruim.

## Comparacao - FTS5/BM25 vs cache lexical

| caminho | ganho esperado | custo | risco | decisao |
| --- | ---: | --- | --- | --- |
| cache em memoria de tokens por chunk | alto apenas no mesmo processo | invalida cache em index/reset/rebuild; TUI e CLI podem divergir | resposta stale se invalidacao falhar | nao escolher como solucao principal |
| cache persistido proprio em SQLite | medio/alto | criar tabela de tokens, manter normalizacao, ranking e invalidacao manual | reimplementar motor lexical ruim | nao vale agora |
| FTS5/BM25 SQLite | alto e persistente | adicionar virtual table e manutencao incremental | query MATCH precisa sanitizacao | escolher |
| Chroma metadata filter + lexical local | baixo/medio | ainda precisa candidatos antes do lexical | pode continuar varrendo demais | fallback apenas |

Escolha: FTS5/BM25 como indice lexical persistido. Cache de recursos pode existir depois para
reduzir overhead pequeno, mas nao substitui indice. Motivo simples: problema medido nao e
alocacao em memoria; e varredura lexical de todos os chunks, custando cerca de `14s`.

Regra de slice: corrigir `note_id`/dedupe antes de acelerar lexical. Acelerar busca sobre
corpus com IDs colididos apenas deixa bug mais rapido.

## Caminho escolhido para `note_id`

Adicionar geracao por caminho relativo quando a origem for corpus:

```text
slug-do-arquivo--hash-relpath
```

Exemplo:

```text
ai--a1b2c3d4
arquitetura-do-perssua--8f13ac20
diario--0c9d31aa
```

Regra:

- `slug` continua humano e curto;
- hash vem do caminho relativo normalizado ao root da indexacao;
- se nao houver root, usar caminho absoluto resolvido como fallback;
- hash curto de 8 ou 10 chars basta para colisao pratica baixa;
- `source_path` continua guardando caminho completo.

Por que nao usar apenas hash de conteudo:

- arquivo duplicado com mesmo conteudo em duas pastas viraria mesmo `note_id`;
- a pergunta sobre fonte/caminho perderia uma das entradas;
- path identifica documento; content hash identifica versao.

Por que nao usar "sufixo so quando colidir":

- adicionar novo arquivo depois mudaria `note_id` de arquivo antigo;
- isso quebra estabilidade e reindexacao incremental.

Tradeoff:

- `note_id` antigo muda depois do rebuild;
- benchmarks/datasets que esperam IDs antigos precisam atualizar fixtures;
- melhor aceitar isso agora do que manter corpus com perda de notas.

## Caminho escolhido para lexical rapido

Adicionar FTS5 persistido em SQLite:

```sql
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
  chunk_id UNINDEXED,
  note_id UNINDEXED,
  chunk_text,
  tokenize = 'unicode61 remove_diacritics 2'
);
```

Fluxo alvo no `hybrid`:

```text
answer_corpus_with_citations()
  -> list_chunk_ids(connection)              # validar stale vetorial
  -> fts_lexical_search_hits(connection)     # BM25 candidates
  -> semantic_search(vector_store, embedder)
  -> fuse lexical + vector
  -> get_notes_by_id()
  -> claims/citations
```

Manter fallback:

- se FTS5 indisponivel;
- se tabela FTS vazia/desatualizada;
- em testes unitarios de single-file sem SQLite.

## Metas numericas

Base real medida:

| metrica | atual |
| --- | ---: |
| lexical Python | 13,7-14,5s |
| hybrid total | 14,4-15,2s |
| vector CUDA quente | 234-737ms |
| stale vectors apos rebuild | 26-50 |

Metas:

| metrica | meta |
| --- | ---: |
| colisao de `note_id` no vault | 0 |
| stale vectors por colisao apos rebuild | 0 |
| FTS lexical em 3070 chunks | <= 150ms |
| hybrid quente em 3070 chunks | <= 1.500ms |
| ask final TUI corpus quente | <= 2.000ms |
| regressao de qualidade no benchmark | 0 queda em `Recall@3` na suite atual |

## Slices de implementacao

### Slice 1 - Testes que reproduzem colisao de `note_id`

Comportamento esperado:

- dois arquivos `AI.md` e `🤖 AI.md` em pastas diferentes geram `note_id` diferentes;
- dois arquivos com mesmo nome em pastas diferentes geram IDs diferentes;
- reindexar o mesmo arquivo gera o mesmo `note_id`;
- `chunk_id` muda junto e permanece deterministico;
- `corpus status` fica `clean` depois de rebuild isolado.

Testes:

```powershell
cd D:\Dev\Repos\Own\tcc-free-plaud\pipeline
uv run pytest --basetemp .pytest-tmp-noteid tests\test_notes_metadata.py tests\test_corpus_service.py -q
```

Arquivos provaveis:

- `pipeline/src/free_plaud/notes/metadata.py`
- `pipeline/src/free_plaud/notes/structurer.py`
- `pipeline/src/free_plaud/corpus/service.py`
- testes de notes/corpus.

### Slice 2 - Implementar `source_root` no fluxo de estruturação

Mudanca:

- `build_note_id(path, root_path=None)` ou novo helper `build_corpus_note_id(path, root_path)`;
- `structure_document(document, source_root=None)`;
- `index_corpus_path()` passa root da descoberta;
- `index_corpus_file()` pode continuar basename ou usar absoluto como fallback configurado.

Aceite:

- corpus de pasta usa relpath;
- single-file continua com comportamento previsivel;
- IDs ficam ASCII, curtos e estaveis.

Ponto de cuidado:

- fixtures antigas que esperam `note_id == "plataforma"` devem ser ajustadas apenas quando chamam corpus path com root;
- testes single-file podem continuar iguais se fallback preservar basename.

### Slice 3 - Deduplicar pending items por `note_id` dentro do lote

Mesmo com `note_id` novo, adicionar protecao defensiva:

- antes de gravar lote, detectar `note_id` duplicado no `pending_items`;
- se duplicado acontecer, marcar lote como `failed` com erro `DUPLICATE_NOTE_ID` ou aplicar politica explicita;
- nunca upsertar dois documentos com mesmo `note_id` no mesmo lote.

Motivo:

- evita stale vectors silenciosos se futura mudanca reintroduzir colisao;
- transforma bug estrutural em falha visivel.

Teste:

- fake structurer retorna dois `_PendingCorpusIndex` com mesmo `note_id`;
- resultado deve ser `partial/failed`;
- Chroma e SQLite nao ficam inconsistentes.

### Slice 4 - Schema FTS5 e manutencao incremental

Adicionar ao schema:

```sql
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(...);
```

Manter FTS em:

- `replace_chunks_for_note()`:
  - apagar linhas FTS do `note_id`;
  - inserir `chunk_id`, `note_id`, `chunk_text` de cada chunk;
- `delete_corpus_notes_and_chunks()`:
  - limpar `chunks_fts`;
- possivel helper:
  - `rebuild_chunks_fts(connection)`;
  - `count_chunks_fts(connection)`.

Aceite:

- SQLite sem chunks continua funcionando;
- reset limpa FTS;
- reindexacao substitui FTS sem duplicar;
- contagem FTS bate com `chunks`.

Testes:

```powershell
uv run pytest --basetemp .pytest-tmp-fts tests\test_storage_sqlite.py -q
```

### Slice 5 - Busca lexical FTS/BM25 para corpus

Adicionar API:

```python
fts_lexical_search_hits(connection, query, top_k, candidate_limit=100) -> list[SearchHit]
```

Contrato:

- usar `normalize_query_terms(query)`;
- montar query FTS segura;
- ordenar por `bm25(chunks_fts)`;
- buscar candidatos via SQLite;
- reconstruir `Chunk`;
- recalcular `matched_terms` e `term_coverage` com a logica atual para preservar gating;
- limitar resultado final por `top_k`.

Fallback:

- se FTS falhar, usar `lexical_search_hits(query, list_chunks(...))`;
- registrar limitation/log em benchmark, nao quebrar ask normal.

Meta:

- `fts_lexical_search_hits()` <= 150ms em 3070 chunks.

### Slice 6 - Trocar `answer_corpus_with_citations()` para caminho indexado

Atual:

```text
chunks = list_chunks(connection)
hybrid_search(question, chunks, ...)
```

Novo:

```text
valid_chunk_ids = list_chunk_ids(connection)
if strategy == lexical:
  hits = fts_lexical_search_hits(...)
if strategy == vector:
  hits = open_semantic_search(...)
if strategy == hybrid:
  lexical_hits = fts_lexical_search_hits(...)
  vector_hits = open_semantic_search(...)
  hits = fuse(...)
```

Preservar:

- stale vector filtering;
- abstention rules;
- citations;
- `used_sources`;
- output `AskResponse`.

Aceite:

- `hybrid` nao deve chamar `list_chunks()` no caminho feliz;
- `lexical` corpus tambem deve usar FTS;
- single-file `retrieval ask` continua usando Python lexical em memoria.

### Slice 7 - Status e diagnostico FTS/note_id

Estender `corpus status`:

- `duplicate_source_note_ids` ou `note_id_collision_count` se possivel diagnosticar no SQLite;
- `fts_chunks_count`;
- `fts_status`: `ready`, `missing`, `stale`, `unavailable`;
- mensagem quando `notes_count < supported_files` em preflight de pasta.

Adicionar comando opcional:

```powershell
uv run free-plaud corpus fts-rebuild
```

Ou manter interno se `ensure_fts_index()` for suficiente.

### Slice 8 - Benchmark antes/depois

Adicionar ao `perf-benchmark`:

- `lexical_ms`;
- `vector_ms`;
- `hybrid_ms`;
- `list_chunks_ms` ou `list_chunk_ids_ms`;
- `fts_ms`;
- `fts_enabled`;
- `note_id_collision_count` quando source path informado.

Smoke real:

```powershell
cd D:\Dev\Repos\Own\tcc-free-plaud\pipeline
$env:FREE_PLAUD_EMBEDDING_MODEL="sentence-transformer:sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
$env:FREE_PLAUD_EMBEDDING_DEVICE="cuda"
uv run free-plaud corpus perf-benchmark --files 100 --repeat 1 --ask-repeat 5 --commit-mode microbatch
```

Smoke no vault real, com DB temporario ou collection isolada:

```powershell
cd D:\Dev\Repos\Own\tcc-free-plaud\pipeline
uv run free-plaud corpus validate-folder "C:\Users\ricar\OneDrive\Documentos\Obsidian Vault\Obsidian-Core" --recursive --compare-retrieval
```

Se `validate-folder` nao existir ainda, criar como comando de diagnostico nao destrutivo ou script de teste interno.

## Ordem recomendada

1. Reproduzir colisao em teste.
2. Corrigir `note_id` por caminho relativo.
3. Adicionar guarda contra duplicata em lote.
4. Adicionar FTS schema/manutencao.
5. Adicionar busca FTS/BM25.
6. Trocar corpus ask/hybrid para usar FTS.
7. Estender status/benchmark.
8. Rebuild real do corpus.

## Validacao obrigatoria

Comandos:

```powershell
cd D:\Dev\Repos\Own\tcc-free-plaud\pipeline
uv run pytest --basetemp .pytest-tmp-noteid-fts -q
git diff --check
```

Validacao operacional:

```powershell
cd D:\Dev\Repos\Own\tcc-free-plaud\pipeline
uv run free-plaud corpus status
uv run free-plaud corpus ask --question "Sobre o que falam minhas notas?" --strategy hybrid --top-k 6
```

Validacao CUDA:

```powershell
cd D:\Dev\Repos\Own\tcc-free-plaud\pipeline
$env:FREE_PLAUD_EMBEDDING_MODEL="sentence-transformer:sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
$env:FREE_PLAUD_EMBEDDING_DEVICE="cuda"
uv run free-plaud corpus embedding-info
uv run free-plaud corpus ask --question "Sobre o que falam minhas notas?" --strategy hybrid --top-k 6
```

Validacao do vault real depois do rebuild:

| metrica | esperado |
| --- | ---: |
| arquivos suportados | 470 |
| notas persistidas | 470 |
| stale vectors | 0 |
| missing vectors | 0 |
| `hybrid` quente | <= 1.500ms alvo, <= 2.000ms aceitavel |

## Riscos

| risco | impacto | mitigacao |
| --- | --- | --- |
| mudar `note_id` quebra fixtures antigas | testes falham | atualizar fixtures e documentar rebuild obrigatorio |
| caminho absoluto torna ID instavel ao mover vault | reindex cria novos IDs | usar relpath quando indexando pasta |
| FTS sem stemming pode mudar ranking | recall pode cair | buscar candidatos por BM25 e recalcular coverage com matcher atual |
| FTS query com caracteres especiais quebra MATCH | erro em pergunta comum | montar query a partir de tokens normalizados, nao string bruta |
| FTS desatualizado | ask errado/lento | `fts_status`, rebuild helper e fallback |
| Chroma stale antigo permanece no corpus atual | status continua inconsistent | rebuild completo apos correcao de `note_id` |

## Definition of done

- vault real gera `470` notas para `470` arquivos suportados;
- `corpus status` fica `clean` apos rebuild;
- `stale_vector_chunks_count == 0`;
- `missing_vector_chunks_count == 0`;
- `hybrid` nao varre todos os chunks em Python;
- `lexical` corpus usa FTS5/BM25;
- `hybrid` quente cai de `~14-15s` para `<=2s`;
- suite completa passa;
- benchmark antes/depois salvo em `data/results/corpus_perf/`.
