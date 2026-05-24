# Handoff - Performance CUDA, micro-lotes e UX de indexacao/ask no TUI

## Status

Criado em 2026-05-24.
Implementado na branch `feat/corpus-index-and-ask` em 2026-05-24.

Este arquivo nasceu como plano de implementacao e passa a servir como handoff tecnico das decisoes
adotadas.

Objetivo: reduzir latencia percebida e real no fluxo de uso do TUI:

- iniciar indexacao CUDA sem parecer travado;
- indexar vault grande com dados perguntaveis antes do fim;
- reduzir latencia de perguntas repetidas;
- impedir que `uv run` volte Torch para CPU por acidente;
- manter `corpus status` e `ask` coerentes enquanto a indexacao roda.

## Contexto real medido

Host medido em 2026-05-24:

- GPU: NVIDIA GeForce RTX 2050, 4 GB VRAM.
- Driver informado pelo usuario: 591.86.
- `torch`: `2.11.0+cu128`.
- `torch.version.cuda`: `12.8`.
- `torch.cuda.is_available()`: `True`.
- Modelo testado: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`.
- Dimensao dos embeddings: `384`.

Observacao do usuario no vault Obsidian:

- vault real: `448` notas indexadas;
- antes das otimizacoes anteriores, `180` notas em cerca de `120s`;
- taxa observada aproximada: `1,5 nota/s`;
- problema percebido: TUI parecia travar e `corpus status` via outra aba mostrava zero ate o final.

## Evidencias locais novas

### 1. Cold-start do embedder domina o primeiro uso

Metrica em processos separados, rodando direto pela `.venv`:

| modelo | device | import_ms | init_ms | first_embed_ms | second_embed_ms | total_ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `chroma-default` | cpu | 4404 | 0 | 1352 | 533 | 6290 |
| `sentence-transformer:*` | cpu | 3889 | 39833 | 161 | 31 | 43915 |
| `sentence-transformer:*` | cuda | 5341 | 36748 | 493 | 49 | 42632 |

Conclusoes:

- CUDA nao e "lento" no embedding quente; o custo grande e carregar/importar modelo.
- O primeiro uso do SentenceTransformer custa cerca de `42s`.
- Pergunta/indexacao no TUI nao deve pagar esse custo varias vezes.
- `index_corpus_path()` cria o embedder antes de `started_at` e antes do primeiro `progress`; por isso o TUI pode ficar sem feedback por cerca de `37-43s` em CUDA.
- benchmark futuro deve separar `python/import`, `embedder_init`, `first_embed` e `warm_embed`; misturar tudo esconde onde esta o custo.
- CUDA so deve ser comparado no provider `sentence-transformer:*`; `chroma-default` continua caminho CPU/local do Chroma.

### 2. Ask quente melhora com recursos reaproveitados

Fixture temporaria: `20` notas, `hybrid`, SentenceTransformer CUDA.

| caminho | amostras_ms | media_ms | p50_ms |
| --- | --- | ---: | ---: |
| atual `ask_corpus()` criando recursos por chamada | 310, 187, 156, 122, 151 | 185,2 | 156 |
| recursos compartilhados no processo | 112, 107, 144, 144, 103 | 122,0 | 112 |

Ganho estimado em fixture: `34,1%` na media.

Conclusoes:

- Reusar embedder/vector store no TUI deve reduzir latencia de pergunta repetida.
- SQLite deve continuar por request ou por worker controlado; conexao SQLite atual nao usa `check_same_thread=False`.
- Ganho maior vem de nao pagar cold-start de `42s` no primeiro ask.

### 3. Banco so fica perguntavel no fim no modo atual

Fixture temporaria: `80` arquivos, embedder fake lento, `embedding_batch_size=16`.

Resultado:

```json
{
  "files": 80,
  "embedding_batch_size": 16,
  "embedding_calls": 5,
  "result_status": "success",
  "total_ms": 9191,
  "progress_events": 169,
  "first_nonzero_status_event": {
    "phase": "finished",
    "processed": 80,
    "indexed": 80,
    "elapsed_ms": 8268,
    "notes_count": 80,
    "chunks_count": 80,
    "vectors_count": 80
  }
}
```

Conclusao: mesmo com 169 eventos de progresso, o banco real so saiu de zero no evento
`finished`. Em vault grande, isso significa que `corpus status` e `ask` continuam vazios
ate 100% da indexacao.

## Veredito tecnico

Implementar micro-lotes e cache de recursos e o melhor caminho.

Mas micro-lote nao deve substituir atômico em todos os casos. A escolha correta e modo
automatico:

- corpus pequeno: atômico, simples, menor chance de estado parcial;
- corpus grande/TUI: micro-lote, melhor UX, status real e ask parcial;
- override manual: permitir forcar `atomic` ou `microbatch` para benchmark/debug.

## Comparacao de caminhos

| caminho | ganho | custo | risco | veredito |
| --- | --- | --- | --- | --- |
| manter atômico | consistencia simples | status/ask so no fim | UX ruim em vault grande | nao resolve problema |
| micro-lote sempre | ask/status cedo | pequenos lotes fazem mais writes | falha deixa corpus parcial | bom para TUI, ruim como default universal |
| auto por tamanho/contexto | melhor dos dois | mais testes/config | decisao errada se thresholds ruins | escolhido |
| staging collection + swap | mais atômico | Chroma nao oferece swap barato; complexidade alta | risco de bug maior | futuro, nao agora |

## Arquitetura alvo

### 1. `CorpusIndexMode`

Adicionar configuracao:

```python
corpus_commit_mode: Literal["auto", "atomic", "microbatch"] = "auto"
corpus_micro_batch_chunks: int = Field(default=64, ge=1, le=2048)
corpus_micro_batch_files: int = Field(default=32, ge=1, le=512)
corpus_atomic_max_files: int = Field(default=32, ge=1, le=512)
corpus_atomic_max_chunks: int = Field(default=64, ge=1, le=2048)
```

Variaveis:

```text
FREE_PLAUD_CORPUS_COMMIT_MODE=auto
FREE_PLAUD_CORPUS_MICRO_BATCH_CHUNKS=64
FREE_PLAUD_CORPUS_MICRO_BATCH_FILES=32
FREE_PLAUD_CORPUS_ATOMIC_MAX_FILES=32
FREE_PLAUD_CORPUS_ATOMIC_MAX_CHUNKS=64
```

Regra `auto` proposta:

- arquivo unico: `atomic`;
- diretorio com ate `32` arquivos suportados e ate `64` chunks pendentes: `atomic`;
- TUI + diretorio acima desses limites: `microbatch`;
- CLI `index` acima desses limites: `microbatch`, salvo flag `--commit-mode atomic`;
- CLI/TUI `rebuild` acima desses limites: `microbatch`, com aviso visual forte "rebuild e destrutivo; corpus fica parcial durante execucao";
- benchmark pode testar os tres modos.

Observacao importante: `rebuild_corpus()` atual executa `reset_corpus()` antes de indexar. Portanto, ele ja nao preserva corpus antigo se o processo morrer depois do reset. Micro-lote nao deve ser vendido como atomicidade; ele melhora visibilidade e uso parcial. Swap por collection de staging fica fora desta entrega porque aumenta muito a complexidade.

### 2. Micro-lote ativo

Pipeline alvo:

```text
discover
prepare files/chunks
group pending chunks/files
for each group:
  embed group em batches
  delete vetores antigos dos note_ids do grupo
  upsert Chroma
  upsert SQLite notes/chunks
  emit progress committed
  ask/status ja enxergam grupo
finish
```

Ordem de escrita escolhida:

1. deletar/upsert Chroma do grupo;
2. gravar SQLite notes/chunks do grupo;
3. emitir progresso/status do grupo.

Motivo:

- se crash ocorrer entre Chroma e SQLite, vira vetor stale;
- `corpus ask` ja filtra stale vector hits;
- `corpus status` ja detecta inconsistencia;
- e pior ter SQLite apontando chunks sem vetor para busca vetorial.

Controle concorrente:

- impedir `reset` enquanto `index/rebuild` esta rodando no TUI;
- impedir duas indexacoes concorrentes no mesmo corpus dentro do TUI;
- CLI concorrente continua risco operacional conhecido nesta etapa, mas `status` deve detectar inconsistencia;
- nao compartilhar conexao SQLite entre threads.

### 3. Cache de recursos no TUI/menu

Criar camada de runtime por processo:

```python
class CorpusRuntime:
    def get_embedder(self) -> Embedder: ...
    def get_vector_store(self) -> LocalVectorStore: ...
    def warmup_embedder(self) -> WarmupResult: ...
    def clear(self) -> None: ...
```

Escopo:

- TUI usa runtime compartilhado por app;
- menu terminal interativo usa runtime compartilhado enquanto menu esta aberto;
- CLI one-shot continua sem cache persistente entre processos.

Nao compartilhar conexao SQLite entre threads neste primeiro passo.

### 4. Warmup visivel

TUI deve mostrar imediatamente:

```text
modelo=sentence-transformer...
device=cuda
status=aquecendo embeddings
```

Aceite:

- clique em `Indexar pasta` mostra feedback em ate `500ms`, mesmo se modelo levar `42s` para carregar;
- fase `warmup` aparece antes de `discovering`;
- se warmup ja terminou, index/ask nao recarrega modelo.

### 5. Fix de instalacao GPU com `uv`

Problema atual:

- instalar Torch CUDA manualmente funciona;
- `uv run` normal re-sincroniza pelo lock e volta Torch CPU;
- workaround atual: `uv run --no-sync`.

Caminho escolhido:

- manter CPU como default;
- adicionar extra opcional para CUDA;
- adicionar config `tool.uv.sources` apontando Torch/TorchVision/TorchAudio para indice PyTorch CUDA;
- documentar `uv sync --extra gpu-cu128`;
- adicionar smoke `embedding-info` no README.

Referencias oficiais usadas para a implementacao futura:

- PyTorch Start Locally: https://pytorch.org/get-started/locally/
- uv com PyTorch: https://docs.astral.sh/uv/guides/integration/pytorch/
- uv optional dependencies: https://docs.astral.sh/uv/concepts/projects/dependencies/

## Slices de implementacao

### Slice 1 - Instrumentar tempo por fase

Comportamento:

- `CorpusIndexProgress` ganha campos opcionais:
  - `warmup_ms`
  - `embedding_ms`
  - `writing_ms`
  - `committed_count`
  - `commit_mode`
  - `batch_index`
  - `batch_total`
- `index-benchmark` passa a reportar cold-start quando solicitado.

Teste primeiro:

- fake embedder com sleep mostra `embedding_ms > 0`;
- provider warmup antes de discovery aparece como fase `warmup`;
- campos antigos continuam presentes.

Comando:

```powershell
cd D:\Dev\Repos\Own\tcc-free-plaud\pipeline
uv run --no-sync pytest tests\test_corpus_index_progress.py -q
```

Meta:

- medir warmup explicitamente;
- nao esconder mais os `42s` fora de `elapsed_ms`.

Commit sugerido:

```text
feat: medir fases da indexacao do corpus
```

### Slice 2 - Corrigir contrato GPU no projeto

Comportamento:

- `uv sync --extra gpu-cu128` instala Torch CUDA no Windows/Linux compatível;
- `uv run free-plaud corpus embedding-info` nao volta para CPU depois do sync GPU;
- CPU continua default para quem nao pedir extra.

Arquivos:

- `pipeline/pyproject.toml`
- `pipeline/README.md`
- opcional: `pipeline/scripts/install-gpu.ps1`

Teste/validacao:

```powershell
cd D:\Dev\Repos\Own\tcc-free-plaud\pipeline
uv sync --extra gpu-cu128
uv run python -c "import torch; print(torch.__version__); print(torch.cuda.is_available())"
uv run free-plaud corpus embedding-info
```

Meta:

- remover dependencia de `uv run --no-sync`;
- evitar reinstalacao manual quebrando metadata de `numpy`.

Commit sugerido:

```text
chore: configurar extra opcional para cuda
```

### Slice 3 - Cache e warmup de embedder no TUI/menu

Comportamento:

- TUI cria `CorpusRuntime` no app;
- primeiro warmup ocorre em background quando modelo for `sentence-transformer:*`;
- `ask`, `index` e `benchmark` usam o mesmo embedder dentro do processo;
- menu terminal tambem reaproveita embedder enquanto esta aberto.

Teste primeiro:

- `get_embedder` chamado uma vez em duas perguntas no TUI;
- warmup falho renderiza erro claro;
- trocar env/modelo invalida cache;
- `chroma-default` nao tenta CUDA.

Meta:

- cold-start de `~42s` pago no maximo uma vez por processo TUI/menu;
- ask quente manter p50 proximo de `112ms` em fixture de 20 notas;
- reduzir media atual de `185ms` para ate `130ms` na mesma fixture.

Commit sugerido:

```text
feat: reutilizar embedder no tui
```

### Slice 4 - Micro-lote core com escrita incremental

Comportamento:

- `index_corpus_path()` aceita `commit_mode`;
- em `microbatch`, cada lote faz embed + Chroma + SQLite;
- `corpus status` mostra notas/chunks/vetores antes do fim;
- `ask` responde com parte ja commitada.

Teste primeiro:

- fixture de 80 arquivos com fake embedder lento:
  - antes: primeiro status nonzero so no `finished`;
  - depois: primeiro status nonzero apos primeiro micro-lote;
- simular falha no segundo lote:
  - primeiro lote permanece consistente;
  - segundo lote vira failure;
  - resultado final `partial` ou `failed`, conforme contagem;
- simular cancelamento entre lotes:
  - lotes ja commitados ficam perguntaveis;
  - lote nao commitado nao aparece.

Meta:

- no teste de 80 arquivos, sair de primeira visibilidade em `8,268s / 100%` para `<= 2,0s / <= 25%`;
- em vault de 448 notas com lote 64, primeira parcela perguntavel perto de `14%` do total, nao `100%`;
- overhead total de micro-lote contra atômico: `<= 15%` em fixture de 100 arquivos.

Commit sugerido:

```text
feat: gravar corpus em micro-lotes
```

### Slice 5 - Seletor automatico atomic vs microbatch

Comportamento:

- `auto` escolhe atômico para pequeno;
- `auto` escolhe micro-lote para grande/TUI;
- CLI aceita override:
  - `--commit-mode auto`
  - `--commit-mode atomic`
  - `--commit-mode microbatch`

Teste primeiro:

| entrada | esperado |
| --- | --- |
| 1 arquivo | `atomic` |
| pasta 10 arquivos/10 chunks | `atomic` |
| pasta 80 arquivos/80 chunks | `microbatch` |
| override `atomic` | `atomic` mesmo grande |
| override `microbatch` | `microbatch` mesmo pequeno |

Meta:

- sistema escolhe sem usuario pensar;
- usuario avancado ainda controla.

Commit sugerido:

```text
feat: escolher modo de commit automaticamente
```

### Slice 6 - Status e ask parcial no TUI

Comportamento:

- painel `Notes` mostra:
  - `modo=atomic|microbatch|auto->microbatch`;
  - `commitados=N`;
  - `lote=X/Y`;
  - `ask parcial=sim` durante micro-lote;
  - `corpus parcial durante rebuild` quando aplicavel.
- aba `Ask` mostra aviso discreto se indexacao esta rodando e corpus esta parcial.

Teste primeiro:

- progress fake com `commit_mode=microbatch` renderiza campos;
- durante indexacao, TUI nao chama status pesado a cada evento;
- depois de cada commit, TUI atualiza status real.

Meta:

- usuario entende que pode perguntar antes do fim;
- status visual bate com `free-plaud corpus status` em outra aba depois de cada lote.

Commit sugerido:

```text
feat: mostrar corpus parcial no tui
```

### Slice 7 - Otimizar ask quente

Comportamento:

- TUI usa embedder e vector store compartilhados;
- SQLite continua abrindo conexao por operacao ou por worker seguro;
- `answer_corpus_with_citations` continua puro e testavel.

Teste primeiro:

- duas perguntas seguidas nao recriam embedder;
- vector store pode ser reaproveitado sem stale collection;
- reset/rebuild invalida runtime ou atualiza collection ativa.

Meta:

- fixture de 20 notas:
  - media atual: `185,2ms`;
  - meta: `<= 130ms`;
  - p50 atual: `156ms`;
  - meta: `<= 120ms`.
- primeiro ask com modelo ja aquecido: sem custo de `42s`.

Commit sugerido:

```text
feat: reduzir latencia do ask no tui
```

### Slice 8 - Benchmark comparativo de performance

Comportamento:

Adicionar ou estender comando:

```powershell
uv run free-plaud corpus perf-benchmark `
  --files 100 `
  --repeat 3 `
  --commit-mode auto `
  --ask-repeat 10 `
  --include-cold-start
```

Campos minimos:

- `cold_start_ms`;
- `python_import_ms`;
- `embedder_init_ms`;
- `first_embed_ms`;
- `warm_embed_ms`;
- `first_progress_ms`;
- `first_committed_ms`;
- `first_askable_ms`;
- `total_index_ms`;
- `files_per_second`;
- `chunks_per_second`;
- `embedding_calls`;
- `ask_avg_ms`;
- `ask_p50_ms`;
- `ask_p95_ms`;
- `commit_mode_resolved`;
- `device`;
- `torch_version`;
- `cuda_available`;
- `gpu_name`;
- `peak_vram_mb`, se viavel.

Saida:

- imprimir resumo humano no terminal;
- salvar JSON em `data/results/corpus_perf/`;
- incluir `timestamp`, `git_commit`, `settings`, `dataset_shape` e `environment`;
- permitir comparar dois JSONs em comando separado ou segunda opcao do mesmo comando.

Matriz obrigatoria:

| variavel | valores |
| --- | --- |
| commit mode | `atomic`, `microbatch`, `auto` |
| batch chunks | `32`, `64`, `128`, `256` |
| workers | `1`, `2`, `4` |
| device | `cpu`, `cuda` |

Meta:

- escolher default por evidencia, nao opiniao;
- para RTX 2050 4GB, provar se `128` chunks e melhor que `64`;
- fallback para `64` se `128/256` causar OOM ou perda de estabilidade.
- defaults finais so mudam depois de benchmark salvo; os valores deste handoff sao chute inicial medido, nao verdade final.

Commit sugerido:

```text
feat: comparar performance de indexacao e ask
```

## Tuning inicial recomendado

Antes de benchmark final, usar:

```powershell
FREE_PLAUD_EMBEDDING_MODEL=sentence-transformer:sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
FREE_PLAUD_EMBEDDING_DEVICE=cuda
FREE_PLAUD_CORPUS_COMMIT_MODE=auto
FREE_PLAUD_CORPUS_MICRO_BATCH_CHUNKS=64
FREE_PLAUD_CORPUS_EMBEDDING_BATCH_SIZE=128
FREE_PLAUD_CORPUS_UPSERT_BATCH_SIZE=256
FREE_PLAUD_CORPUS_INDEX_WORKERS=4
```

Por que:

- `64` chunks por micro-lote reduz tempo ate primeira escrita;
- `128` chunks por embedding batch tende a aproveitar melhor GPU de 4 GB sem arriscar tanto OOM;
- `256` upsert reduz overhead de Chroma;
- `4` workers condiz com vault pequeno/medio, mas precisa validar no OneDrive.

## Definition of done

Entrega pronta somente quando:

- `uv run` com extra GPU nao volta para CPU;
- TUI mostra feedback em ate `500ms` ao iniciar indexacao CUDA;
- cold-start SentenceTransformer aparece como fase `warmup`;
- embedder nao e recriado em perguntas repetidas no TUI;
- micro-lote torna `corpus status` nonzero antes do fim;
- ask consegue responder usando lote ja commitado;
- auto escolhe atômico para pequeno e micro-lote para grande;
- cancelamento preserva lotes ja commitados;
- falha no lote N nao corrompe lotes anteriores;
- full suite passa;
- benchmark antes/depois registrado no output do comando.

## Validacao local obrigatoria

Comandos base:

```powershell
cd D:\Dev\Repos\Own\tcc-free-plaud\pipeline
uv run --no-sync pytest --basetemp .pytest-tmp-perf -q
git diff --check
```

Depois da Slice 2, trocar para:

```powershell
cd D:\Dev\Repos\Own\tcc-free-plaud\pipeline
uv sync --extra gpu-cu128
uv run pytest --basetemp .pytest-tmp-perf -q
```

Smoke real controlado:

```powershell
cd D:\Dev\Repos\Own\tcc-free-plaud\pipeline
uv run free-plaud corpus embedding-info
uv run free-plaud corpus perf-benchmark --files 100 --repeat 3 --ask-repeat 10 --include-cold-start
uv run free-plaud-tui
```

Teste no vault real, manual:

```powershell
cd D:\Dev\Repos\Own\tcc-free-plaud\pipeline
uv run free-plaud-tui
```

No TUI:

1. abrir `Notes`;
2. selecionar `C:\Users\ricar\OneDrive\Documentos\Obsidian Vault\Obsidian-Core`;
3. indexar;
4. quando primeiro lote commitado aparecer, abrir outra aba:

```powershell
cd D:\Dev\Repos\Own\tcc-free-plaud\pipeline
uv run free-plaud corpus status
uv run free-plaud corpus ask --question "Sobre o que falam minhas notas?" --strategy hybrid --top-k 6
```

## Tentativas de quebra obrigatorias

- `uv run` sem `--no-sync` depois do extra GPU;
- CUDA indisponivel com `FREE_PLAUD_EMBEDDING_DEVICE=cuda`;
- pasta com 0 arquivos suportados;
- pasta com 500 arquivos pequenos;
- pasta com arquivos grandes que geram muitos chunks;
- cancelamento durante warmup;
- cancelamento durante embedding;
- cancelamento logo apos primeiro commit;
- falha simulada no segundo micro-lote;
- rebuild grande interrompido;
- ask durante rebuild parcial;
- reset enquanto indexacao esta rodando deve ser bloqueado;
- trocar modelo/device com TUI aberto deve invalidar cache ou pedir restart claro;
- OneDrive path com espacos e acentos.

## Riscos e mitigacoes

| risco | impacto | mitigacao |
| --- | --- | --- |
| micro-lote deixa corpus parcial apos falha | usuario pergunta corpus incompleto | TUI/CLI mostrar `partial`, status detectar, rebuild recomendado |
| mais commits reduzem throughput | index total pode subir | benchmark exigir overhead `<= 15%`; ajustar lote |
| cache de embedder segura VRAM | GPU fica ocupada | botao/comando para limpar runtime ou reiniciar TUI; mostrar device |
| CUDA extra quebra maquinas sem GPU | setup ruim | CPU default; GPU so com extra |
| SQLite compartilhado entre threads | bug intermitente | nao compartilhar conexao SQLite na primeira entrega |
| status pesado demais em loop | TUI lento | status completo so apos commit; progresso leve entre commits |

## Ordem recomendada

1. Instrumentar tempo por fase.
2. Corrigir contrato GPU com `uv`.
3. Cache/warmup de embedder no TUI/menu.
4. Micro-lote core.
5. Auto selector.
6. Status/ask parcial no TUI.
7. Otimizar ask quente.
8. Benchmark comparativo.

Motivo:

- primeiro medir;
- depois estabilizar ambiente;
- depois matar cold-start repetido;
- depois mudar semantica de commit;
- depois expor UX e benchmark.

## Prompt para executor

```text
Use caveman:caveman, akita-way e senior-second-pass.

Repo: D:\Dev\Repos\Own\tcc-free-plaud
Projeto Python ativo: pipeline/

Leia:
1. AGENTS.md
2. docs/ORDEM_DE_LEITURA_IA.md
3. docs/arquitetura/Arquitetura_Backend.md
4. docs/plano_execucao/HANDOFF_PERFORMANCE_CUDA_MICROLOTES_TUI.md

Implemente somente a proxima slice.
Siga TDD: teste falhando, patch minimo, teste focado, suite relevante.
Nao use vault Obsidian real como fixture automatizada.
Nao tocar docs/tcc/.
Nao compartilhar SQLite entre threads sem teste especifico.
Antes de finalizar, rode benchmark pequeno, git diff --check e second pass do diff.
```

## Revisao senior aplicada

Verdict: Approved with adjustments.

Findings incorporados neste plano:

- [P1] Micro-lote estava descrito como ganho de velocidade, mas o ganho primario e de visibilidade/ask parcial. Plano agora mede overhead e limita regressao total a `<= 15%`.
- [P1] CUDA cold-start era tratado como problema de embedding, mas o codigo atual tambem mede progresso so depois de `get_embedder`. Plano agora cria fase `warmup`.
- [P1] Reusar SQLite em TUI poderia criar bug de thread. Plano proibe compartilhar conexao SQLite na primeira entrega.
- [P2] `uv run --no-sync` e workaround, nao solucao. Plano adiciona extra GPU via `uv`.
- [P2] Auto mode precisava override. Plano inclui `--commit-mode`.
- [P2] `status` completo em todo evento pode virar gargalo. Plano limita status real a eventos de commit.
- [P2] Benchmark sem artefato persistido vira opiniao de terminal. Plano agora salva JSON comparavel em `data/results/corpus_perf/`.
- [P2] Rebuild parcial podia parecer atomicidade. Plano agora explicita que rebuild atual ja e destrutivo e que micro-lote melhora UX, nao rollback.
