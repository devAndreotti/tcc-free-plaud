# Handoff - Corpus indexado e ask multi-documento

## Status

Criado em 2026-05-22.

Este plano ainda nao foi implementado. Ele existe para guiar uma nova slice tecnica depois do fechamento ou decisao sobre a branch `feat/tui-textual`.

## Leitura obrigatoria antes de executar

1. `AGENTS.md`
2. `docs/ORDEM_DE_LEITURA_IA.md`
3. `docs/arquitetura/Arquitetura_Backend.md`
4. `Sprints/STATUS.md`
5. `docs/experimentos/08_validacao_retrieval_distribuido.md`
6. Este arquivo

Nao ler `docs/tcc/` salvo necessidade academica explicita.

## Skills obrigatorias

- `caveman:caveman` para comunicacao curta, conforme `AGENTS.md`
- `akita-way` para execucao em slices pequenas, TDD e commits limpos
- `senior-second-pass` no fim de cada slice para revisar plano, diff e validacao
- `adversarial-delivery-auditor` antes de aceitar feature como pronta

## Senior second pass do diagnostico anterior

### Veredito

Approved with adjustments.

### Achados

- [P1] O diagnostico anterior estava correto ao separar retrieval multi-file de answer multi-file, mas ainda estava incompleto como plano de produto. Faltava definir contrato de corpus, persistencia, idempotencia, comandos e criterio de aceite. Corrigir com slices abaixo.
- [P1] `retrieval ask <arquivo>` hoje e single-file por desenho. Em `rag.py`, `vector` e `hybrid` usam `note_id=note.note_id`, entao nao existe stitching real entre notas. Corrigir criando fluxo separado para corpus, sem quebrar `ask <arquivo>`.
- [P1] A indexacao atual persiste embeddings no Chroma, mas nem todo caminho persiste nota/chunks no SQLite. Corrigir com uma camada de aplicacao que sempre sincronize `notes`, `chunks` e vector store.
- [P2] A busca aberta (`semantic-search`) ja recupera multi-file, mas nao monta resposta com claims/citations multi-documento. Corrigir desacoplando answer de uma unica `Note`.
- [P2] Pasta existe apenas como helper raso em `ingest/watcher.py`. Corrigir com descoberta recursiva controlada, extensoes suportadas, ignores e relatorio.
- [P2] O plano precisa de testes de falso positivo e reindexacao. Sem isso, o corpus pode parecer funcional mas duplicar chunks ou responder lixo.

## Estado de branches em 2026-05-22

Comando usado:

```powershell
cd D:\Dev\Repos\Own\tcc-free-plaud
git branch -vv
git branch --merged main
git branch --no-merged main
git worktree list --porcelain
git status --short --branch
```

Resultado observado:

| Branch | Estado | Leitura |
| --- | --- | --- |
| `main` | estavel em `origin/main` | contem as slices backend ate poda de span |
| `feat/hybrid-retrieval` | mergeada em `main` | sobra local/remota de trabalho antigo |
| `feat/obsidian-cleaner` | mergeada em `main` | sobra local/remota de trabalho antigo |
| `feat/ask-claim-quality` | mergeada em `main` | sobra local/remota de trabalho antigo |
| `feat/tui-textual` | nao mergeada em `main` | contem TUI textual e refinamentos visuais recentes |
| `test/visualinterface` | nao mergeada em `main`; worktree separado | rastreia `origin/feature/VisualInterface`, provavel branch de frontend |

Conclusao:

- Nao ha alteracao TUI nao commitada na branch atual.
- A TUI textual esta commitada em `feat/tui-textual`.
- O unico item untracked no repo atual e `samples/`, com arquivos de validacao/manual.
- As tres branches antigas ficaram porque foram mergeadas em `main`, mas nao apagadas depois.
- `test/visualinterface` nao deve ser apagada sem confirmar com o responsavel do frontend, pois esta presa ao worktree `D:/Dev/Repos/Own/tcc-free-plaud-visualinterface`.

Antes de iniciar esta nova feature:

1. Decidir se `feat/tui-textual` entra em `main` ou fica pausada.
2. Nao iniciar `feat/corpus-index-and-ask` em cima de `feat/tui-textual`, salvo decisao explicita.
3. Preferir branch nova a partir de `main` atualizado.
4. Nao mexer em `test/visualinterface`.
5. Nao commitar `samples/` sem decisao explicita.

## Objetivo da nova feature

Transformar o backend de "ask sobre um arquivo" em "ask sobre um acervo local indexado".

Contrato desejado:

1. Usuario adiciona um arquivo suportado (`.txt`, `.md`, `.pdf`) ou uma pasta.
2. Sistema estrutura cada documento como `Note`.
3. Sistema persiste nota e chunks no SQLite.
4. Sistema persiste embeddings no Chroma.
5. Usuario pergunta contra o corpus inteiro.
6. Sistema recupera chunks relevantes de um ou mais arquivos.
7. Sistema monta resposta com claims, citations, used_sources e `no_answer` quando faltar evidencia.

## Fora de escopo

- Frontend web
- Tauri
- LLM real
- Audio
- Imagem/OCR novo
- Suporte a `.docx`
- Monitoramento automatico de pasta em background
- Delecao destrutiva de corpus

## Branch sugerida

Depois de fechar estado atual:

```powershell
cd D:\Dev\Repos\Own\tcc-free-plaud
git checkout main
git pull --ff-only
git checkout -b feat/corpus-index-and-ask
```

## Slice 0 - Higiene de branch antes da feature

### Comportamento esperado

Repo deve estar em estado previsivel antes de qualquer codigo novo.

### Checklist

```powershell
cd D:\Dev\Repos\Own\tcc-free-plaud
git fetch --prune
git status --short --branch
git branch --merged main
git branch --no-merged main
git worktree list --porcelain
```

### Decisao

- Se `feat/tui-textual` deve entrar em `main`, mergear e validar antes desta feature.
- Se nao deve entrar, criar branch nova a partir de `main`, nao da TUI.
- Branches mergeadas antigas podem ser removidas localmente depois de confirmacao:

```powershell
git branch -d feat/hybrid-retrieval
git branch -d feat/obsidian-cleaner
git branch -d feat/ask-claim-quality
```

Nao remover remotas sem pedido explicito.

### Commit esperado

Sem commit se for apenas limpeza local de branch.

## Slice 1 - Contrato de corpus e camada de aplicacao

### Comportamento esperado

Criar uma camada de aplicacao para indexar documentos sem depender da CLI diretamente.

Entrada:

- `Path` de arquivo
- configuracao de chunking
- settings

Saida:

- `note_id`
- `source_path`
- `chunks_indexed`
- `embedding_model`
- `vector_collection_name`
- `vector_entries_count`
- status e erro estruturado quando falhar

### Arquivos provaveis

- `pipeline/src/free_plaud/corpus/__init__.py`
- `pipeline/src/free_plaud/corpus/service.py`
- `pipeline/src/free_plaud/corpus/models.py`
- `pipeline/tests/test_corpus_service.py`

### Regras

- Reusar `load_document`, `structure_document`, `index_note`, `upsert_note`, `replace_chunks_for_note`, `LocalVectorStore.upsert_chunks`.
- Persistir SQLite e Chroma no mesmo fluxo.
- Nao duplicar chunks no SQLite ao reindexar o mesmo arquivo.
- Manter idempotencia por `note_id` e `chunk_id`.
- Nao apagar collection inteira para reindexar um arquivo.

### Testes primeiro

Criar testes que falham antes da implementacao:

```powershell
cd D:\Dev\Repos\Own\tcc-free-plaud\pipeline
uv run pytest tests\test_corpus_service.py -q
```

Casos minimos:

| Caso | Esperado |
| --- | --- |
| indexar `.md` simples | nota, chunks e embeddings persistidos |
| reindexar mesmo arquivo | contagens estaveis, sem duplicacao SQLite |
| arquivo inexistente | erro estruturado, sem escrita parcial |
| extensao nao suportada | erro estruturado |
| conteudo vazio | erro estruturado |

### Validacao

```powershell
uv run pytest tests\test_corpus_service.py tests\test_storage_sqlite.py tests\test_vector_store.py -q
```

### Commit esperado

```text
feat: adicionar servico de indexacao de corpus
```

## Slice 2 - CLI `corpus index`

### Comportamento esperado

Adicionar comando dedicado:

```powershell
uv run free-plaud corpus index "D:\caminho\arquivo.md"
```

JSON de saida deve ser estavel e facil de consumir por IA/UI.

### Arquivos provaveis

- `pipeline/src/free_plaud/corpus/cli.py`
- `pipeline/src/free_plaud/cli.py`
- `pipeline/tests/test_cli.py`
- `pipeline/tests/test_corpus_service.py`

### Regras

- Nao reaproveitar `retrieval index` como interface oficial de produto.
- Manter `retrieval index` funcionando por compatibilidade experimental.
- `corpus index` deve inicializar SQLite e vector store.
- Saida deve incluir failures, mesmo em erro parcial futuro.

### Testes primeiro

```powershell
uv run pytest tests\test_cli.py tests\test_corpus_service.py -q
```

Casos:

| Caso | Esperado |
| --- | --- |
| `free-plaud corpus --help` | aparece no CLI principal |
| `corpus index arquivo.md` | JSON com `status=success` |
| path com espaco | aceito via `compose_path` ou equivalente |
| erro de arquivo | exit code != 0 e JSON/erro claro |

### Validacao manual

```powershell
$env:FREE_PLAUD_VECTOR_STORE_DIR = "$env:TEMP\free-plaud-corpus-smoke"
$env:FREE_PLAUD_VECTOR_COLLECTION_NAME = "corpus_smoke"
uv run free-plaud corpus index "D:\Dev\Repos\Own\tcc-free-plaud\data\results\validation_distributed_corpus\01_contexto_base.md"
uv run free-plaud retrieval semantic-search --query "Qual message broker foi adotado?" --top-k 3
Remove-Item -Recurse -Force "$env:TEMP\free-plaud-corpus-smoke"
```

### Commit esperado

```text
feat: expor indexacao de corpus na cli
```

## Slice 3 - Indexacao de pasta

### Comportamento esperado

Permitir:

```powershell
uv run free-plaud corpus index "D:\minha-pasta" --recursive
```

Saida:

- total encontrado
- total indexado
- total ignorado
- total com erro
- lista de resultados por arquivo

### Arquivos provaveis

- `pipeline/src/free_plaud/corpus/discovery.py`
- `pipeline/src/free_plaud/corpus/service.py`
- `pipeline/src/free_plaud/corpus/cli.py`
- `pipeline/tests/test_corpus_discovery.py`
- `pipeline/tests/test_corpus_service.py`

### Regras

- Suportar `.txt`, `.md`, `.pdf`.
- Ignorar diretórios comuns: `.git`, `.venv`, `__pycache__`, `node_modules`, `data/results/vector_store`.
- `--recursive` desligado por padrao para evitar varredura acidental gigante.
- Ordenacao deterministica por path.
- Falha em um arquivo nao deve impedir indexacao dos demais.

### Testes primeiro

```powershell
uv run pytest tests\test_corpus_discovery.py tests\test_corpus_service.py -q
```

Casos:

| Caso | Esperado |
| --- | --- |
| pasta com 2 `.md` e 1 `.pdf` | todos indexados |
| pasta com `.docx` | ignorado com motivo |
| subpasta sem `--recursive` | ignorada |
| subpasta com `--recursive` | indexada |
| `.git` e `node_modules` | sempre ignorados |

### Break attempt

Rodar com pasta contendo:

- arquivo vazio
- arquivo sem permissao, se praticavel
- arquivo grande
- nome com acento e emoji
- path com espaco

### Commit esperado

```text
feat: indexar pastas no corpus local
```

## Slice 4 - `ask-corpus` sem stitching sofisticado

### Comportamento esperado

Adicionar pergunta contra acervo inteiro, inicialmente com resposta composta a partir de hits multi-file.

Comando:

```powershell
uv run free-plaud corpus ask --question "Qual message broker foi adotado e qual padrao divide o pipeline em Bronze, Silver e Gold?" --strategy hybrid --top-k 6
```

Contrato de resposta:

- mesmo formato de `AskResponse`
- `used_sources` pode conter mais de um `note_id`
- `citations` pode conter chunks de notas diferentes
- `no_answer` se evidencia for insuficiente

### Arquivos provaveis

- `pipeline/src/free_plaud/corpus/ask.py`
- `pipeline/src/free_plaud/corpus/cli.py`
- `pipeline/src/free_plaud/retrieval/rag.py`
- `pipeline/tests/test_corpus_ask.py`
- `pipeline/tests/test_rag.py`

### Design recomendado

Nao modificar `answer_with_citations(note, ...)` para tentar fazer tudo.

Criar funcao nova, por exemplo:

```python
answer_corpus_with_citations(question, hits, note_lookup, strategy, ...)
```

Ela deve:

1. receber hits ja recuperados do corpus inteiro
2. construir claims por hit/chunk
3. montar citations usando metadados do chunk e note lookup
4. aplicar os filtros atuais de grounding/no_answer

### Busca por estrategia

| Strategy | Recuperacao |
| --- | --- |
| `vector` | `open_semantic_search` no Chroma compartilhado |
| `hybrid` | lexical sobre chunks SQLite + vector aberto + rank fusion |
| `lexical` | lexical sobre chunks SQLite |

Para `hybrid`, sera necessario buscar chunks do SQLite. Se nao existir repositorio para isso, criar funcoes pequenas:

- `list_chunks(connection)`
- `get_notes_by_id(connection, note_ids)`

### Testes primeiro

```powershell
uv run pytest tests\test_corpus_ask.py tests\test_rag.py -q
```

Casos obrigatorios:

| Caso | Pergunta | Esperado |
| --- | --- | --- |
| multi-file controlado | broker + runbook + Bronze/Silver/Gold | answer com 3 fontes |
| single-file dentro do corpus | broker adotado | answer com 1 fonte |
| irrelevante | tecnologias mobile inexistentes | `no_answer` |
| anchor nomeado ausente | pergunta cita entidade inexistente | `missing_named_anchor` ou equivalente |
| top_k baixo | pergunta multi-parte com `top_k=1` | limitacao clara ou resposta parcial segura |

### Validacao manual

```powershell
$env:FREE_PLAUD_VECTOR_STORE_DIR = "$env:TEMP\free-plaud-corpus-ask-smoke"
$env:FREE_PLAUD_VECTOR_COLLECTION_NAME = "corpus_ask_smoke"
uv run free-plaud corpus index "D:\Dev\Repos\Own\tcc-free-plaud\data\results\validation_distributed_corpus" --recursive
uv run free-plaud corpus ask --question "Qual message broker foi adotado, qual equipe ficou responsavel pelo runbook e qual padrao divide o pipeline em Bronze, Silver e Gold?" --strategy hybrid --top-k 6
uv run free-plaud corpus ask --question "Quais tecnologias o candidato domina para desenvolver apps mobile?" --strategy hybrid --top-k 6
Remove-Item -Recurse -Force "$env:TEMP\free-plaud-corpus-ask-smoke"
```

### Commit esperado

```text
feat: responder perguntas contra corpus indexado
```

## Slice 5 - Benchmark de retrieval distribuido

### Comportamento esperado

Adicionar suite de benchmark que prova o novo comportamento, nao apenas retrieval aberto.

### Arquivos provaveis

- `data/datasets/distributed_validation/`
- `pipeline/tests/test_corpus_ask.py`
- `pipeline/tests/test_benchmark_real_datasets.py`
- `docs/experimentos/12_ask_corpus_multi_documento.md`

### Dataset minimo

Corpus controlado:

- `01_contexto_base.md`: broker adotado
- `02_detalhe_operacional.md`: equipe e prazo do runbook
- `03_restricao_arquitetural.md`: Bronze/Silver/Gold

Queries:

| ID | Tipo | Esperado |
| --- | --- | --- |
| dist-01 | multi-file 2 fontes | citations de 2 notas |
| dist-02 | multi-file 3 fontes | citations de 3 notas |
| dist-03 | single-file | 1 nota |
| dist-04 | irrelevante | `no_answer` |
| dist-05 | falso positivo sem anchor | `no_answer` |

### Validacao

```powershell
uv run pytest tests\test_corpus_ask.py tests\test_benchmark_real_datasets.py -q
uv run pytest -q
```

### Registro experimental

Criar `docs/experimentos/12_ask_corpus_multi_documento.md` com:

- objetivo
- corpus
- comandos
- resultados JSON resumidos
- casos de falha
- decisao tecnica

### Commit esperado

```text
test: adicionar validacao de ask multi-documento
```

## Slice 6 - TUI minima para corpus

Executar somente depois do backend/CLI estar verde.

### Comportamento esperado

TUI deve deixar claro dois fluxos:

1. Ask local em arquivo, se ainda fizer sentido como demo rapida.
2. Corpus: indexar arquivo/pasta e perguntar contra acervo.

### Arquivos provaveis

- `pipeline/src/free_plaud/tui/app.py`
- `pipeline/src/free_plaud/tui/app.tcss`
- `pipeline/tests/test_tui_app.py`

### Regras

- Nao chamar lógica de ingest/retrieval diretamente espalhada no widget.
- TUI chama servico de corpus.
- Mostrar contagens de indexacao.
- Mostrar fontes usadas multi-file.
- Nao travar UI durante indexacao.

### Testes

```powershell
uv run pytest tests\test_tui_app.py tests\test_corpus_ask.py -q
```

Casos:

| Caso | Esperado |
| --- | --- |
| indexar arquivo pela TUI | estado volta para pronto |
| indexar pasta pela TUI | contagem renderizada |
| ask corpus | resposta mostra multiplas fontes |
| erro operacional | painel de erro, botoes reabilitados |
| resize | controles nao cortam |

### Validacao visual

Usar screenshot/export Textual ou Playwright quando aplicavel:

```powershell
uv run pytest tests\test_tui_app.py -q
```

Evidencia visual deve cobrir:

- tela larga
- tela estreita
- estado clicado/foco
- erro
- resposta multi-file

### Commit esperado

```text
feat: adicionar fluxo de corpus na tui
```

## Slice 7 - Documentacao operacional

### Comportamento esperado

Atualizar docs de uso sem inflar `docs/tcc/`.

### Arquivos provaveis

- `README.md`
- `pipeline/README.md`
- `docs/arquitetura/Arquitetura_Backend.md`
- `docs/README.md`
- `Sprints/STATUS.md`, somente se a sprint/status realmente mudar

### Comandos documentados

```powershell
cd D:\Dev\Repos\Own\tcc-free-plaud\pipeline
uv sync
uv run free-plaud storage init
uv run free-plaud corpus index "D:\caminho\pasta" --recursive
uv run free-plaud corpus ask --question "pergunta" --strategy hybrid --top-k 6
uv run free-plaud-tui
uv run pytest -q
```

### Commit esperado

```text
docs: documentar fluxo de corpus local
```

## Gate final da feature

Antes de merge:

```powershell
cd D:\Dev\Repos\Own\tcc-free-plaud\pipeline
uv run pytest -q
uv run free-plaud --help
uv run free-plaud corpus --help
uv run free-plaud corpus index "D:\Dev\Repos\Own\tcc-free-plaud\data\results\validation_distributed_corpus" --recursive
uv run free-plaud corpus ask --question "Qual message broker foi adotado, qual equipe ficou responsavel pelo runbook e qual padrao divide o pipeline em Bronze, Silver e Gold?" --strategy hybrid --top-k 6
uv run free-plaud corpus ask --question "Quais tecnologias o candidato domina para desenvolver apps mobile?" --strategy hybrid --top-k 6
```

Tambem rodar:

```powershell
git diff --check
git status --short --branch
```

Critérios de aceite:

- Multi-file answer retorna `status=answer`.
- `used_sources` tem pelo menos 2 notas no caso distribuido.
- `citations` apontam para chunks reais.
- Pergunta irrelevante retorna `no_answer`.
- Reindexar mesma pasta nao duplica registros.
- Suite completa passa.
- Experimento 12 registra comandos e resultados.

## Riscos e decisoes abertas

| Risco | Impacto | Mitigacao |
| --- | --- | --- |
| SQLite e Chroma ficarem inconsistentes | ask corpus cita chunk sem nota correspondente | persistir ambos no mesmo service e testar falha parcial |
| `note_id` por filename causar colisao | arquivo diferente sobrescreve nota | revisar regra em `notes/structurer.py` antes de indexar corpus real |
| pasta grande indexar coisa demais | lentidao e lixo no acervo | `--recursive` desligado por padrao, ignores e resumo antes/depois |
| `.docx` aparecer em samples | usuario espera suporte | declarar fora de escopo ou criar slice propria futura |
| resposta multi-file virar colagem ruim | baixa qualidade percebida | começar com claims citaveis pequenos, depois calibrar stitching |
| TUI entrar antes do core | retrabalho visual | TUI somente depois de CLI/testes verdes |

## Ordem recomendada agora

1. Decidir destino de `feat/tui-textual`.
2. Limpar branches mergeadas locais se desejado.
3. Criar `feat/corpus-index-and-ask` a partir de `main`.
4. Executar Slice 1 a Slice 5 backend-only.
5. Registrar Experimento 12.
6. So entao aplicar Slice 6 na TUI.
