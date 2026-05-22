# Handoff - Otimizacao de indexacao e feedback visual no TUI

## Status

Criado em 2026-05-22.

Este arquivo e um plano de implementacao. Nenhuma mudanca de codigo faz parte
deste handoff.

Contexto observado:

- O usuario indexou `C:\Users\ricar\OneDrive\Documentos\Obsidian Vault\Obsidian-Core` pelo TUI.
- A execucao terminou com `448` notas.
- Durante a execucao, o TUI parecia travado porque nao havia progresso parcial.
- O caso real envolve um vault em OneDrive, com centenas de arquivos e possivel variacao de timestamps.

## Leitura obrigatoria antes de executar

1. `AGENTS.md`
2. `docs/ORDEM_DE_LEITURA_IA.md`
3. `docs/arquitetura/Arquitetura_Backend.md`
4. `docs/plano_execucao/HANDOFF_CORPUS_CONSISTENCIA_RESET.md`
5. `docs/plano_execucao/HANDOFF_TCC_TUI_TEXTUAL.md`
6. `Sprints/Sprint 06.1/README.md`
7. `Sprints/Sprint 06.2/README.md`
8. `Sprints/Sprint 07/README.md`
9. Este arquivo

Nao ler `docs/tcc/` salvo tarefa academica explicita.

## Skills obrigatorias

- `caveman:caveman` para comunicacao curta, conforme `AGENTS.md`.
- `akita-way` para TDD, slices pequenas, gates e diff review.
- `senior-second-pass` para revisar plano, diff e entrega.
- `adversarial-delivery-auditor` antes de declarar a feature pronta, porque ha risco de apagar/indexar corpus errado.

## Veredito senior do diagnostico

Approved with adjustments.

O diagnostico anterior estava correto na direcao geral, mas faltavam dois pontos criticos:

- [P0] Campo de pasta vazio no TUI pode virar `Path('')`, que resolve para `.`. Impacto: clicar `Indexar` sem pasta pode indexar o diretorio atual do processo. Fix: validar string vazia antes de criar `Path` e bloquear a acao no TUI e na camada `tui/actions.py`.
- [P1] O gargalo nao e apenas embedding. A implementacao atual tambem chama `delete_by_note_id`, que lista todos os vetores para achar chunks da nota, e isso pode crescer como custo quadratico em corpus grande. Fix: remover vetores por ids vindos do SQLite ou por filtro Chroma, e evitar `count()` por arquivo.

## Decisoes de arquitetura

1. TUI nao deve acessar SQLite/Chroma diretamente.
2. TUI deve chamar uma camada de aplicacao com eventos de progresso.
3. Chroma write continua serial nesta fase.
4. Paralelismo, quando entrar, fica limitado a load/structure/chunk.
5. Skip de arquivo inalterado usa `content_hash`, nao `mtime`.
6. OneDrive real nao deve ser fixture de teste automatizado.
7. Benchmark de performance deve usar fixture sintetica e uma pasta temporaria.
8. Cada slice deve ser comitada separadamente quando o usuario pedir commit.

## Fora de escopo

- Reescrever pipeline inteiro.
- Multiprocessing.
- Escrita paralela no ChromaDB.
- Trocar ChromaDB por outro vector store.
- Editar o vault Obsidian original.
- Limpeza semantica de Obsidian/Dataview.
- Tauri/frontend web.
- Otimizacao de ranking/RAG fora da indexacao.

## Objetivo

Tornar indexacao de pastas grandes operavel pelo TUI:

1. impedir acao perigosa quando pasta esta vazia ou invalida;
2. mostrar progresso real durante indexacao;
3. permitir cancelamento controlado;
4. pular arquivos ja indexados e inalterados;
5. reduzir custo crescente do Chroma;
6. acelerar indexacao com batches;
7. medir antes/depois com dados reproduziveis.

## Mapa atual do codigo

Arquivos relevantes:

- `pipeline/src/free_plaud/tui/app.py`
- `pipeline/src/free_plaud/tui/actions.py`
- `pipeline/src/free_plaud/corpus/service.py`
- `pipeline/src/free_plaud/corpus/discovery.py`
- `pipeline/src/free_plaud/corpus/models.py`
- `pipeline/src/free_plaud/storage/sqlite.py`
- `pipeline/src/free_plaud/storage/vector.py`
- `pipeline/src/free_plaud/providers/embed.py`
- `pipeline/tests/test_tui_app.py`
- `pipeline/tests/test_cli.py`

Gargalos e riscos atuais:

- `index_corpus_path()` processa diretorios em loop serial.
- `index_corpus_file()` faz load, structure, chunk, embed e persistencia por arquivo.
- `delete_by_note_id()` varre registros vetoriais para cada nota.
- `CorpusIndexBatchResult` so existe no final da operacao.
- TUI nao recebe eventos enquanto a operacao roda.
- `chroma-default` e o embedding default; CUDA nao entra nesse caminho.

## Regra Akita para esta entrega

Cada slice abaixo deve seguir:

1. declarar comportamento esperado;
2. escrever/ajustar teste primeiro;
3. implementar menor mudanca possivel;
4. rodar teste focado;
5. rodar suite relevante;
6. fazer second pass do diff;
7. so entao considerar commit.

Nao misturar otimizacao de performance com mudanca visual sem teste que prove o contrato.

## Slice 1 - Guard rail para pasta vazia e preflight

### Problema

Campo `Pasta` vazio nao deve indexar `.`.

### Comportamento esperado

- Se `Pasta` estiver vazia, `Indexar pasta` e `Rebuild pasta` mostram erro no painel `Notes`.
- Nenhum worker inicia.
- Nenhum acesso a SQLite/Chroma ocorre.
- Se path nao existir, erro e renderizado antes de iniciar indexacao.
- Se path existe mas nao e diretorio, erro e renderizado antes de iniciar indexacao.
- Preflight mostra total de arquivos suportados e ignorados antes de indexar.

### Arquivos provaveis

- `pipeline/src/free_plaud/tui/app.py`
- `pipeline/src/free_plaud/tui/actions.py`
- `pipeline/src/free_plaud/corpus/discovery.py`
- `pipeline/src/free_plaud/corpus/models.py`
- `pipeline/tests/test_tui_app.py`

### Testes primeiro

Casos:

| Caso | Esperado |
| --- | --- |
| pasta vazia no TUI | erro, zero chamada a `index_corpus_folder` |
| path inexistente | erro, zero worker real |
| arquivo no lugar de pasta | erro claro |
| pasta valida com 2 md e 1 png | preflight conta 2 suportados e 1 ignorado |

### Comandos

```powershell
cd D:\Dev\Repos\Own\tcc-free-plaud\pipeline
uv run pytest tests\test_tui_app.py -q
```

### Criterio de aceite

- Clicar `Indexar pasta` sem pasta nao indexa nada.
- Mensagem de erro aparece em menos de 1 segundo.
- Botao volta ao estado normal.

### Commit sugerido

```text
fix: bloquear indexacao sem pasta no tui
```

## Slice 2 - Progresso visual em tempo real

### Problema

Indexacao longa parece travada.

### Comportamento esperado

Durante indexacao, painel `Notes` deve mostrar:

- fase atual: `descobrindo`, `carregando`, `estruturando`, `embedando`, `gravando`, `finalizando`;
- `processados/total`;
- `indexados`;
- `inalterados`;
- `falhas`;
- `ignorados`;
- arquivo atual abreviado;
- tempo decorrido;
- taxa aproximada;
- ETA quando total for conhecido;
- ultimas 10 mensagens.

### Contrato tecnico proposto

Criar modelos de progresso em `corpus/models.py` ou modulo dedicado:

```python
class CorpusIndexProgress(BaseModel):
    phase: Literal[
        "discovering",
        "loading",
        "structuring",
        "embedding",
        "writing",
        "finished",
        "cancelled",
        "failed",
    ]
    current_path: str | None = None
    total_found: int = 0
    processed_count: int = 0
    indexed_count: int = 0
    unchanged_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0
    elapsed_ms: int = 0
    message: str | None = None
```

Servico aceita callback:

```python
def index_corpus_path(..., progress: Callable[[CorpusIndexProgress], None] | None = None):
    ...
```

No TUI, callback usa `self.app.call_from_thread(...)` para renderizar sem violar thread da UI.

### Arquivos provaveis

- `pipeline/src/free_plaud/corpus/models.py`
- `pipeline/src/free_plaud/corpus/service.py`
- `pipeline/src/free_plaud/tui/actions.py`
- `pipeline/src/free_plaud/tui/app.py`
- `pipeline/tests/test_corpus_index_progress.py`
- `pipeline/tests/test_tui_app.py`

### Testes primeiro

Casos:

| Caso | Esperado |
| --- | --- |
| indexa 3 arquivos | callback recebe progresso monotonicamente |
| arquivo falha | progresso incrementa `failed_count` |
| pasta com ignorados | progresso inclui `skipped_count` |
| TUI recebe progresso fake | painel atualiza sem terminar worker |

### Comandos

```powershell
cd D:\Dev\Repos\Own\tcc-free-plaud\pipeline
uv run pytest tests\test_corpus_index_progress.py tests\test_tui_app.py -q
```

### Criterio de aceite

- Em vault grande, usuario ve mudanca a cada arquivo ou batch.
- Estado `Executando...` nao fica sem contexto.
- Resultado final mantem tabela de status e notas.

### Commit sugerido

```text
feat: exibir progresso da indexacao no tui
```

## Slice 3 - Cancelamento cooperativo

### Problema

Usuario nao consegue parar indexacao longa pelo TUI.

### Comportamento esperado

- Enquanto indexa, botao `Cancelar` fica visivel/habilitado.
- Cancelamento nao mata processo abruptamente.
- Worker para no proximo ponto seguro.
- Resultado final informa `cancelled`.
- Banco fica consistente para itens ja gravados.

### Contrato tecnico proposto

Criar token simples:

```python
class CancellationToken:
    def cancel(self) -> None: ...
    def is_cancelled(self) -> bool: ...
    def raise_if_cancelled(self) -> None: ...
```

Servico aceita:

```python
cancel_token: CancellationToken | None = None
```

Pontos seguros de checagem:

- depois de discovery;
- antes de cada arquivo;
- depois de load/structure;
- antes de embedding;
- entre batches de embedding;
- antes de write.

### Arquivos provaveis

- `pipeline/src/free_plaud/corpus/models.py`
- `pipeline/src/free_plaud/corpus/service.py`
- `pipeline/src/free_plaud/tui/actions.py`
- `pipeline/src/free_plaud/tui/app.py`
- `pipeline/tests/test_corpus_index_cancel.py`
- `pipeline/tests/test_tui_app.py`

### Testes primeiro

Casos:

| Caso | Esperado |
| --- | --- |
| token cancelado antes de iniciar | zero arquivo processado, `cancelled` |
| token cancela apos 2 arquivos | 2 persistidos, final `cancelled` |
| cancelamento no TUI | botao volta, mensagem clara |

### Criterio de aceite

- Cancelar nao corrompe SQLite/Chroma.
- Nova indexacao pode rodar depois sem reiniciar TUI.

### Commit sugerido

```text
feat: permitir cancelar indexacao pelo tui
```

## Slice 4 - Skip por `content_hash`

### Problema

Reindexar o mesmo vault recalcula tudo.

### Comportamento esperado

- Se `note_id` existe e `content_hash` e igual, arquivo vira `unchanged`.
- Arquivo inalterado nao chama embedding.
- Arquivo inalterado nao chama upsert no Chroma.
- Resultado final reporta `unchanged_count`.
- OneDrive nao usa `mtime` como fonte de verdade.

### Detalhe importante

Para saber `content_hash`, ainda sera necessario carregar e estruturar o documento, porque hash atual vem de `normalized_text` em `notes/structurer.py`.

O ganho inicial vem de evitar:

- chunking redundante;
- embedding;
- delete/upsert no Chroma;
- writes no SQLite.

Otimizar hash antes da estrutura pode ficar para futuro, se medicao provar necessidade.

### Arquivos provaveis

- `pipeline/src/free_plaud/storage/sqlite.py`
- `pipeline/src/free_plaud/corpus/models.py`
- `pipeline/src/free_plaud/corpus/service.py`
- `pipeline/tests/test_corpus_index_skip.py`

### API sugerida

```python
def get_note_content_hash(connection, note_id: str) -> str | None:
    ...
```

`CorpusIndexResult.status` deve aceitar:

```python
Literal["success", "failed", "unchanged", "cancelled"]
```

`CorpusIndexBatchResult` deve ganhar:

```python
unchanged_count: int = 0
cancelled_count: int = 0
```

### Testes primeiro

Casos:

| Caso | Esperado |
| --- | --- |
| primeiro index | `success`, embedding chamado |
| segundo index sem mudanca | `unchanged`, embedding nao chamado |
| arquivo mudou | `success`, embedding chamado |
| vetor ausente mas hash igual | reindexa ou repara, nao marca unchanged |

### Criterio de aceite

- Segunda indexacao de fixture grande tem tempo muito menor.
- Relatorio mostra quantos arquivos foram pulados.

### Commit sugerido

```text
feat: pular arquivos inalterados na indexacao
```

## Slice 5 - Remover custo quadratico no Chroma

### Problema

`delete_by_note_id()` lista todos os vetores para cada nota. Em corpus grande, isso cresce mal.

### Comportamento esperado

- Reindexar uma nota nao lista toda collection repetidamente.
- Vetores antigos da nota continuam sendo removidos com seguranca.
- `vector_entries_count` nao chama `count()` por arquivo.

### Caminhos possiveis

Opcao A, preferida:

- obter chunk ids antigos do SQLite antes de `replace_chunks_for_note`;
- deletar esses ids diretamente no Chroma;
- depois upsert novos chunks.

Opcao B:

- usar delete com filtro `where={"note_id": note_id}` se Chroma suportar de forma estavel na versao instalada;
- cobrir com teste real.

### Arquivos provaveis

- `pipeline/src/free_plaud/storage/sqlite.py`
- `pipeline/src/free_plaud/storage/vector.py`
- `pipeline/src/free_plaud/corpus/service.py`
- `pipeline/tests/test_corpus_index_vector_cleanup.py`

### API sugerida

```python
def list_chunk_ids_for_note(connection, note_id: str) -> list[str]:
    ...

def delete_chunks_by_ids(self, chunk_ids: list[str]) -> int:
    ...
```

### Testes primeiro

Casos:

| Caso | Esperado |
| --- | --- |
| reindexa nota com chunks antigos | chunks antigos somem |
| ids vazios | delete no-op |
| 100 notas fake | nao chama `list_records()` por nota |

### Criterio de aceite

- Reindexacao de 448 notas nao faz varredura global por nota.
- `get_corpus_status` continua detectando divergencia.

### Commit sugerido

```text
fix: evitar varredura global ao reindexar vetores
```

## Slice 6 - Batch embedding cross-arquivo

### Problema

Hoje embedding roda por arquivo. Isso desperdicara overhead em centenas de notas.

### Comportamento esperado

- Arquivos alterados viram uma lista de chunks pendentes.
- Embedding roda em batches configuraveis.
- Upsert roda em batches.
- Progresso mostra fase `embedding` com chunks processados.
- Resultado por arquivo continua preservado.

### Configuracao sugerida

Adicionar em `Settings`:

```python
corpus_embedding_batch_size: int = Field(default=64, ge=1, le=512)
corpus_upsert_batch_size: int = Field(default=128, ge=1, le=1000)
```

Variaveis:

```text
FREE_PLAUD_CORPUS_EMBEDDING_BATCH_SIZE=64
FREE_PLAUD_CORPUS_UPSERT_BATCH_SIZE=128
```

### Arquivos provaveis

- `pipeline/src/free_plaud/app/config.py`
- `pipeline/src/free_plaud/corpus/service.py`
- `pipeline/src/free_plaud/corpus/models.py`
- `pipeline/tests/test_corpus_index_batch_embedding.py`

### Testes primeiro

Casos:

| Caso | Esperado |
| --- | --- |
| 5 arquivos alterados | embed chamado por batch, nao por arquivo |
| batch size 2 | chamadas com tamanhos 2,2,resto |
| uma falha antes de embedding | falha isolada, demais seguem |
| embedding retorna tamanho errado | erro controlado |

### Criterio de aceite

- Mesmo resultado funcional de antes.
- Menos chamadas a `embedder.embed`.
- Progresso continua correto.

### Commit sugerido

```text
feat: processar embeddings do corpus em batch
```

## Slice 7 - Paralelismo controlado para load/structure

### Problema

Load e structure por arquivo sao independentes. Parte do custo pode ser paralelizavel.

### Comportamento esperado

- Worker pool opcional para load/structure/chunk.
- Escrita SQLite/Chroma continua serial.
- Ordem de resultado continua deterministica.
- Falha de um arquivo nao derruba lote inteiro.

### Configuracao sugerida

```python
corpus_index_workers: int = Field(default=1, ge=1, le=16)
```

Variavel:

```text
FREE_PLAUD_CORPUS_INDEX_WORKERS=4
```

Default inicial deve ser `1` para reduzir risco. Depois de medir, pode subir.

### Arquivos provaveis

- `pipeline/src/free_plaud/app/config.py`
- `pipeline/src/free_plaud/corpus/service.py`
- `pipeline/tests/test_corpus_index_parallel.py`

### Testes primeiro

Casos:

| Caso | Esperado |
| --- | --- |
| workers=1 | comportamento atual |
| workers=4 | mesmos resultados, ordem final estavel |
| um arquivo quebra | resultado parcial com falha |
| cancelamento durante pool | para sem novos writes |

### Criterio de aceite

- Sem write paralelo no SQLite/Chroma.
- Resultado deterministico em duas execucoes.

### Commit sugerido

```text
feat: paralelizar preparo de arquivos do corpus
```

## Slice 8 - Diagnostico de device/GPU para embeddings

### Problema

Falar em GPU sem diagnostico pode virar falsa expectativa. Config atual usa `chroma-default`.

### Comportamento esperado

- CLI/TUI mostram qual embedder esta ativo.
- Se `sentence-transformer:*`, permitir `cpu`, `cuda` ou `auto`.
- Se CUDA indisponivel e usuario pediu `cuda`, erro claro.
- Se `chroma-default`, informar que device CUDA nao se aplica.

### Configuracao sugerida

```python
embedding_device: Literal["cpu", "cuda", "auto"] = "cpu"
```

Variavel:

```text
FREE_PLAUD_EMBEDDING_DEVICE=auto
```

### Arquivos provaveis

- `pipeline/src/free_plaud/app/config.py`
- `pipeline/src/free_plaud/providers/embed.py`
- `pipeline/src/free_plaud/corpus/service.py`
- `pipeline/src/free_plaud/tui/app.py`
- `pipeline/tests/test_embedder_config.py`

### Testes primeiro

Casos:

| Caso | Esperado |
| --- | --- |
| chroma-default + cuda | mensagem "nao aplicavel" ou ignora com aviso |
| sentence-transformer + cpu | instancia em CPU |
| sentence-transformer + cuda indisponivel | erro claro |
| auto | escolhe device disponivel sem crash |

### Criterio de aceite

- Usuario sabe se esta usando CPU/GPU.
- Nenhuma dependencia CUDA nova e exigida por default.

### Commit sugerido

```text
feat: diagnosticar device de embedding
```

## Slice 9 - Benchmark operacional de indexacao

### Problema

Sem medicao, otimizacao vira chute.

### Comportamento esperado

Adicionar teste/CLI operacional nao destrutivo para medir:

- tempo total;
- arquivos por segundo;
- chunks por segundo;
- chamadas de embedding;
- contagem de unchanged;
- memoria aproximada se viavel.

### Fixture sugerida

Gerar em temp dir:

- 50 arquivos `.md` pequenos;
- 10 arquivos `.md` medios;
- 5 arquivos `.txt`;
- 3 arquivos `.pdf` pequenos se fixture PDF ja existir;
- arquivos ignorados `.png`, `.docx`, `.canvas`.

Nao usar o vault real no teste automatizado.

### Arquivos provaveis

- `pipeline/src/free_plaud/corpus/cli.py`
- `pipeline/src/free_plaud/corpus/service.py`
- `pipeline/tests/test_corpus_index_performance.py`

### Comandos

```powershell
cd D:\Dev\Repos\Own\tcc-free-plaud\pipeline
uv run pytest tests\test_corpus_index_performance.py -q
```

Comando manual opcional, depois de implementar:

```powershell
cd D:\Dev\Repos\Own\tcc-free-plaud\pipeline
uv run free-plaud corpus index-benchmark --files 100 --repeat 2
```

### Criterio de aceite

- Antes/depois fica mensuravel.
- Resultado nao depende de OneDrive.

### Commit sugerido

```text
feat: medir desempenho da indexacao do corpus
```

## Plano de validacao integrado

Rodar por slice:

```powershell
cd D:\Dev\Repos\Own\tcc-free-plaud\pipeline
uv run pytest tests\test_tui_app.py -q
```

Rodar antes de fechar feature:

```powershell
cd D:\Dev\Repos\Own\tcc-free-plaud\pipeline
uv run pytest --basetemp D:\p -q
```

Smoke manual com pasta pequena:

```powershell
cd D:\Dev\Repos\Own\tcc-free-plaud\pipeline
uv run free-plaud-tui
```

Smoke manual com menu terminal:

```powershell
cd D:\Dev\Repos\Own\tcc-free-plaud\pipeline
uv run free-plaud menu
```

Validacao real controlada no vault Obsidian, somente depois de P0/P1:

```powershell
cd D:\Dev\Repos\Own\tcc-free-plaud\pipeline
uv run free-plaud-tui
```

No TUI:

1. abrir `Notes`;
2. selecionar `C:\Users\ricar\OneDrive\Documentos\Obsidian Vault\Obsidian-Core`;
3. rodar preflight;
4. indexar;
5. observar progresso;
6. cancelar em uma execucao de teste;
7. rodar novamente e confirmar `unchanged_count` alto.

## Tentativas de quebra obrigatorias

Antes de chamar pronto:

- clicar `Indexar` com pasta vazia;
- clicar `Rebuild` com pasta vazia;
- informar `C:\nao-existe`;
- informar caminho de arquivo em vez de pasta;
- informar pasta com 0 arquivos suportados;
- cancelar durante discovery;
- cancelar durante embedding;
- reindexar mesma pasta duas vezes;
- reindexar depois de alterar 1 arquivo;
- apagar vetor manualmente em fixture e reindexar;
- simular erro de embedding em um batch;
- usar path com espacos e acentos;
- usar pasta dentro de OneDrive em modo leitura;
- fechar TUI depois de cancelamento e reabrir.

## Definition of done

Feature so esta pronta quando:

- pasta vazia nao dispara indexacao;
- TUI mostra progresso real em operacao longa;
- usuario consegue cancelar sem corromper corpus;
- segunda indexacao pula arquivos inalterados;
- Chroma nao e varrido inteiro por nota;
- batch embedding reduz chamadas ao embedder;
- testes focados passam;
- suite completa passa;
- second pass do diff nao encontra blocker;
- comportamento e documentado no README ou handoff relevante.

## Ordem recomendada

1. Slice 1 - Guard rail para pasta vazia e preflight.
2. Slice 2 - Progresso visual em tempo real.
3. Slice 3 - Cancelamento cooperativo.
4. Slice 4 - Skip por `content_hash`.
5. Slice 5 - Remover custo quadratico no Chroma.
6. Slice 9 - Benchmark operacional de indexacao.
7. Slice 6 - Batch embedding cross-arquivo.
8. Slice 7 - Paralelismo controlado.
9. Slice 8 - Diagnostico de device/GPU.

Motivo da ordem:

- Primeiro remove risco operacional.
- Depois melhora UX.
- Depois melhora reingestao.
- Depois mede.
- So entao acelera.

## Prompt para executor

```text
Use caveman:caveman, akita-way, senior-second-pass e adversarial-delivery-auditor.

Repo: D:\Dev\Repos\Own\tcc-free-plaud
Projeto Python ativo: pipeline/

Leia:
1. AGENTS.md
2. docs/ORDEM_DE_LEITURA_IA.md
3. docs/arquitetura/Arquitetura_Backend.md
4. docs/plano_execucao/HANDOFF_OTIMIZACAO_INDEXACAO_OBSIDIAN_TUI.md

Implemente apenas a proxima slice marcada neste handoff.
Siga TDD: teste primeiro, menor patch, teste focado, suite relevante.
Nao mexa em docs/tcc/.
Nao mexa em Sprints/.
Nao use o vault Obsidian real como teste automatizado.
Nao escreva no Chroma/SQLite real fora de temp dirs nos testes.
Antes de finalizar, faca second pass do diff e tentativa de quebra listada.
```

