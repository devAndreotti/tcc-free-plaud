# Handoff - Doctor, presets e superficies reais do app

Criado em 2026-05-25.

Este arquivo e plano de implementacao. Nenhuma mudanca funcional faz parte deste handoff.

## Contexto

O projeto ja tem:

- `settings_catalog` como fonte canonica para settings;
- API key fora de `user_settings.json`, salva em `pipeline/.env`;
- TUI, menu terminal e UI PyWebView consumindo settings reais;
- `corpus ask` real no front desktop;
- indexacao de pasta pelo front desktop;
- RAG generativo opcional com provider OpenAI-compatible;
- FTS/BM25, microbatch, progresso e cancelamento no corpus.

O proximo risco nao e "falta de mais campos". O risco e usuario operar configuracao quebrada sem
diagnostico: `fake-hash`, CUDA falsa, provider desligado, corpus inconsistente, modelo local nao
respondendo ou benchmark sem snapshot reproduzivel.

## Senior second pass das ideias anteriores

**Veredito:** approved with adjustments.

**Achados**

- [P1] Doctor/Health Check precisa vir antes de features visuais maiores. Sem diagnostico, o app
  continua permitindo estados invalidos como `embedding_model=fake-hash` e provider local offline.
  Correcao: criar core testavel de diagnostico antes de desenhar telas ricas.
- [P1] Presets precisam ser transacionais. Aplicar "GPU qualidade" e falhar no meio pode deixar
  `user_settings.json` incoerente. Correcao: validar preset inteiro antes de salvar; aplicar em uma
  unica escrita quando possivel; limpar runtime depois.
- [P1] Teste de provider nao pode chamar LLM quando corpus nao tem evidencia. Sao fluxos diferentes:
  "health check do provider" pode mandar prompt sintetico; "Ask RAG" continua com gate de evidencias.
  Correcao: separar `doctor provider` de `corpus ask`.
- [P2] Notes e Benchmark no front podem crescer demais. Correcao: implementar em slices verticais:
  lista minima, detalhe minimo, acao minima, depois polish.
- [P2] "Detectar modelos locais" deve ser adapter por provider, nao regra solta no frontend.
  Correcao: backend expõe `list_models()` para Ollama/LM Studio quando disponivel; front apenas renderiza.
- [P2] Queue de indexacao precisa definir persistencia. Correcao V1: fila em memoria do processo
  PyWebView/TUI; persistencia de jobs fica fora do escopo ate haver necessidade real.
- [P3] Simple/Advanced settings nao deve esconder estado perigoso. Correcao: warnings do Doctor
  sempre visiveis mesmo no modo simples.

## Objetivo

Transformar o app em uma ferramenta operavel por usuario final local:

1. diagnosticar ambiente e configuracao antes de uso;
2. aplicar presets seguros;
3. testar provider LLM e modelos locais;
4. explicar resultados do Ask;
5. operar Notes, Benchmark e indexacao pelo front;
6. salvar snapshots reproduziveis para TCC.

## Fora de escopo

- Tauri.
- Instalador Windows.
- Streaming de resposta.
- Chat multi-turn persistente.
- Trocar ChromaDB por outro vector store.
- Rodar benchmark automatico no vault real do usuario.
- Baixar modelos Ollama automaticamente sem confirmacao explicita.
- Editar ou mover arquivos do vault original.

## Decisoes de arquitetura

1. Backend continua fonte de verdade.
2. Front nao acessa SQLite, Chroma ou `.env` diretamente.
3. Cada superficie chama API PyWebView/CLI/TUI que delega para camada `free_plaud`.
4. Doctor, presets, provider test e model detection ficam em modulo backend novo.
5. Settings continuam em `user_settings.json`; segredos continuam em `.env`.
6. Todo resultado experimental deve salvar snapshot de configuracao.
7. UI real pode ser simples; corretude e rastreabilidade vencem polish.
8. Cada slice deve passar teste focado antes de UI.

## Modulos propostos

```text
pipeline/src/free_plaud/
├── app/
│   ├── settings_catalog.py
│   ├── settings_presets.py        # novo
│   └── doctor.py                  # novo
├── providers/
│   ├── answer.py
│   └── model_discovery.py         # novo
├── corpus/
│   ├── jobs.py                    # novo, fila V1 em memoria
│   └── explain.py                 # novo ou integrado em ask.py
├── notes/
│   └── service.py                 # novo se list/detail/reindex crescer
└── benchmark/
    └── snapshots.py               # novo ou integrado em runners.py
```

Front:

```text
UI/src/
├── services/bridge.ts
├── components/SettingsModal.tsx
├── components/DoctorPanel.tsx      # novo
├── components/NotesPanel.tsx       # novo
├── components/BenchmarkPanel.tsx   # novo
└── components/AskDebugPanel.tsx    # novo
```

## Regra Akita para execucao

Para cada slice:

1. comportamento esperado escrito antes;
2. teste RED minimo;
3. implementacao menor possivel;
4. teste focado verde;
5. diff review senior;
6. suite relevante;
7. docs atualizados somente se decisao duravel mudar;
8. commit pequeno quando usuario pedir.

Nao misturar duas superficies na mesma slice se o core ainda nao tiver teste.

## Ordem recomendada

1. Slice 1 - Doctor/Health Check core.
2. Slice 2 - Doctor nas tres superficies.
3. Slice 3 - Presets transacionais.
4. Slice 4 - Teste de provider LLM.
5. Slice 5 - Simple/Advanced settings.
6. Slice 6 - Ask explain/debug.
7. Slice 7 - Notes no front.
8. Slice 8 - Benchmark no front com snapshots.
9. Slice 9 - Fila de indexacao no front.
10. Slice 10 - Deteccao de modelos locais.

Motivo:

- primeiro impedir configuracao quebrada;
- depois facilitar configuracao boa;
- depois melhorar observabilidade do Ask;
- depois ampliar operacao visual.

## Slice 1 - Doctor/Health Check core

### Comportamento

Criar servico backend que retorna diagnostico estruturado:

- `status`: `ok`, `warning`, `error`;
- checks individuais;
- mensagem humana curta;
- codigo tecnico;
- acao sugerida;
- latencia quando aplicavel.

Checks V1:

| Check | Regra |
| --- | --- |
| `settings.embedding_model` | erro se `fake-hash`; ok para `chroma-default` e `sentence-transformer:*` valido |
| `settings.embedding_device` | warning se `cuda` com `chroma-default`; erro se `cuda` indisponivel para sentence-transformer |
| `sqlite` | arquivo/criacao possivel, schema inicializavel |
| `chroma` | collection acessivel e count possivel |
| `fts` | status `ready`, `missing`, `stale` ou `unavailable` |
| `corpus` | empty/clean/inconsistent conforme status atual |
| `answer_provider` | ok para `extractive`; warning se provider generativo sem modelo/base_url esperado |
| `api_key` | warning se provider remoto sem chave; ok para Ollama/LM Studio sem chave |

### Arquivos provaveis

- `pipeline/src/free_plaud/app/doctor.py`
- `pipeline/src/free_plaud/app/settings_catalog.py`
- `pipeline/src/free_plaud/providers/embed.py`
- `pipeline/src/free_plaud/corpus/service.py`
- `pipeline/tests/test_doctor.py`

### Testes RED

```powershell
cd D:\Dev\Repos\Own\tcc-free-plaud\pipeline
uv run pytest tests\test_doctor.py -q
```

Casos:

- `fake-hash` gera erro.
- `chroma-default + cuda` gera warning, nao erro.
- `sentence-transformer + cuda` sem CUDA gera erro claro.
- provider `extractive` nao exige API key.
- provider `openai-compatible` sem API key gera warning.
- corpus inconsistente aparece no diagnostico.

### Aceite

- Doctor roda sem inicializar modelo pesado desnecessariamente.
- Nenhum segredo e impresso.
- Resultado e serializavel para CLI/TUI/front.

## Slice 2 - Doctor nas tres superficies

### Comportamento

Expor Doctor em:

- `free-plaud doctor`;
- menu terminal opcao `Diagnostico`;
- TUI pane ou card em `Settings`;
- front desktop dentro de Settings.

### UX esperada

Formato curto:

```text
status: warning

- embedding_model: erro - fake-hash e modelo de teste
- embedding_device: warning - CUDA nao se aplica ao chroma-default
- corpus: ok - SQLite e Chroma consistentes
- provider: ok - extractive nao exige chave
```

### Arquivos provaveis

- `pipeline/src/free_plaud/cli.py`
- `pipeline/src/free_plaud/terminal_menu.py`
- `pipeline/src/free_plaud/tui/app.py`
- `UI/main.py`
- `UI/src/services/bridge.ts`
- `UI/src/components/SettingsModal.tsx` ou `DoctorPanel.tsx`
- `pipeline/tests/test_cli.py`
- `pipeline/tests/test_tui_app.py`
- `pipeline/tests/test_ui_bridge.py`

### Testes RED

- CLI imprime status e checks.
- menu terminal mostra "Diagnostico".
- PyWebView API retorna `doctor`.
- TUI renderiza erro fake-hash sem crash.

### Aceite

- Usuario ve problema antes de perguntar/indexar.
- `fake-hash` nao passa despercebido.
- Front dev mock pode mostrar Doctor fake, mas PyWebView usa real.

## Slice 3 - Presets transacionais

### Presets V1

| Preset | Uso | Valores |
| --- | --- | --- |
| `cpu_rapido` | notebook sem GPU | `embedding_model=chroma-default`, `embedding_device=cpu`, `top_k=4`, `hybrid`, `chunk=800`, `overlap=120` |
| `gpu_qualidade` | GPU NVIDIA com torch CUDA | `sentence-transformer:sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, `embedding_device=cuda`, `top_k=5` |
| `vault_grande` | Obsidian grande | `corpus_commit_mode=microbatch`, `batch=64`, `workers=2`, `recursive=true` |
| `tcc_reprodutivel` | benchmark | `hybrid`, `top_k=5`, `chunk=800`, `overlap=120`, provider `extractive` |

### Comportamento

- Listar presets.
- Preview antes de aplicar.
- Validar todos os campos.
- Aplicar com uma escrita de `user_settings.json`.
- Limpar runtime apos aplicar.
- Nao tocar API key.

### Arquivos provaveis

- `pipeline/src/free_plaud/app/settings_presets.py`
- `pipeline/src/free_plaud/app/config.py`
- `pipeline/src/free_plaud/terminal_menu.py`
- `pipeline/src/free_plaud/tui/app.py`
- `UI/main.py`
- `UI/src/services/bridge.ts`
- `UI/src/components/SettingsModal.tsx`
- `pipeline/tests/test_settings_presets.py`

### Testes RED

- Preview nao salva.
- Aplicar `cpu_rapido` grava JSON esperado.
- Preset com campo invalido falha antes de escrever.
- API key nao entra no JSON.
- Runtime clear e chamado nas superficies.

### Aceite

- Usuario troca para config boa em um clique/comando.
- Doctor roda depois e mostra resultado.

## Slice 4 - Teste de provider LLM

### Comportamento

Criar teste operacional separado do RAG:

- `free-plaud provider test-answer`;
- menu terminal opcao "Testar provider";
- TUI/front botao "Testar".

Ele manda prompt sintetico curto:

```text
Responda somente: ok
```

### Regras

- Nao usa corpus.
- Nao usa dados do usuario.
- Nao imprime API key.
- Timeout respeita `answer_timeout_seconds`.
- Retorna provider, model, base_url, status, latencia, erro.

### Arquivos provaveis

- `pipeline/src/free_plaud/providers/answer.py`
- `pipeline/src/free_plaud/providers/model_discovery.py`
- `pipeline/tests/test_answer_provider.py`
- `pipeline/tests/test_cli.py`
- `pipeline/tests/test_ui_bridge.py`

### Testes RED

- provider fake HTTP 200 retorna ok.
- HTTP 401 vira erro com codigo.
- timeout vira erro controlado.
- `extractive` retorna "nao aplicavel".

### Aceite

- Usuario sabe se Ollama/LM Studio/API externa esta funcionando antes de Ask.

## Slice 5 - Simple/Advanced settings

### Comportamento

Settings vira duas camadas:

Simples:

- preset;
- pasta do corpus;
- provider;
- modelo resposta;
- API key;
- device;
- Doctor status.

Avancado:

- `top_k`;
- `chunk_size`;
- `overlap`;
- `commit_mode`;
- batch;
- workers;
- timeout;
- temperature;
- base_url.

### Regras

- Warnings do Doctor aparecem em ambos.
- Campo advanced nao some do backend; apenas UI agrupa.
- Menu terminal tambem agrupa por "Simples" e "Avancado".

### Testes RED

- front renderiza presets e advanced toggle.
- menu terminal mostra grupos.
- TUI mantem acoes visiveis em 80x24 e 120x36.

## Slice 6 - Ask explain/debug

### Comportamento

Adicionar modo debug opcional para Ask:

- chunks recuperados;
- score;
- estrategia que achou;
- termos lexicais;
- distancia vetorial;
- fonte;
- motivo de `no_answer`.

### Contrato

`AskResponse` pode ganhar campo opcional:

```python
debug: AskDebug | None = None
```

Ou endpoint separado:

```python
answer_corpus_with_debug(...)
```

Preferencia: campo opcional desligado por default para nao poluir resposta comum.

### Testes RED

- debug desligado nao muda payload atual.
- debug ligado inclui hits e scores.
- no_answer inclui motivo e hits rejeitados quando houver.

### Aceite

- Ajuda tuning do TCC.
- Nao quebra consumidores atuais.

## Slice 7 - Notes no front

### V1 comportamento

- listar notas indexadas;
- abrir detalhe da nota;
- mostrar `note_id`, titulo, fonte, tags, chunks;
- abrir Markdown estruturado;
- deletar nota do corpus com confirmacao;
- reindexar uma nota.

### Fora do V1

- editor Markdown.
- alterar nota original.
- sincronizacao bidirecional com Obsidian.

### Arquivos provaveis

- `pipeline/src/free_plaud/notes/service.py`
- `pipeline/src/free_plaud/storage/sqlite.py`
- `UI/main.py`
- `UI/src/components/NotesPanel.tsx`
- `pipeline/tests/test_notes_service.py`

### Testes RED

- listar notas retorna resumo.
- detalhe retorna markdown e chunks.
- deletar remove SQLite e Chroma.
- front bridge expõe metodos.

### Aceite

- Usuario consegue auditar o que esta no banco sem terminal.

## Slice 8 - Benchmark no front com snapshots

### Comportamento

- selecionar `suite.json`;
- rodar compare;
- mostrar MRR, Recall@3, latencia media;
- exportar JSON/CSV;
- salvar snapshot de settings junto do resultado.

### Snapshot minimo

```json
{
  "embedding_model": "...",
  "embedding_device": "...",
  "default_ask_strategy": "hybrid",
  "retrieval_top_k": 5,
  "default_chunk_size": 800,
  "default_chunk_overlap": 120,
  "answer_provider": "extractive",
  "created_at": "..."
}
```

### Testes RED

- benchmark salva snapshot.
- export contem metrics e settings.
- front bridge retorna resultado estruturado.

### Aceite

- Resultado pode ser usado no texto/defesa do TCC sem adivinhar config.

## Slice 9 - Fila de indexacao no front

### V1 comportamento

- um job ativo por processo;
- progresso em tempo real;
- cancelar;
- resultado final;
- ultimos erros por arquivo.

### Fora do V1

- fila persistida em disco;
- multiplos jobs paralelos;
- indexacao automatica por watcher.

### Arquivos provaveis

- `pipeline/src/free_plaud/corpus/jobs.py`
- `UI/main.py`
- `UI/src/services/bridge.ts`
- `UI/src/components/QueuePanel.tsx`

### Testes RED

- criar job retorna `job_id`.
- consultar job retorna progresso.
- cancelar job muda status.
- segundo job enquanto um roda retorna erro claro.

### Aceite

- Front deixa de parecer travado ao indexar vault grande.

## Slice 10 - Deteccao de modelos locais

### Comportamento

Backend tenta listar modelos:

- Ollama: `GET /api/tags` ou endpoint compativel disponivel;
- LM Studio: endpoint OpenAI-compatible `/models`, quando servidor suporta;
- OpenAI-compatible generico: `/models`, opcional.

### Regras

- Sem baixar modelo automaticamente.
- Sem travar UI se servidor offline.
- Timeout curto.
- Resultado cacheavel por alguns segundos.

### Testes RED

- Ollama fake retorna lista.
- LM Studio fake retorna lista.
- servidor offline retorna warning.
- provider extractive retorna lista vazia.

### Aceite

- Usuario escolhe modelo por nome quando servidor local expõe lista.
- Nao existe "selecionar pasta do modelo" no app.

## Metricas que devem ser coletadas

Cada entrega deve reportar numeros reais:

| Area | Metrica |
| --- | --- |
| Doctor | tempo total do diagnostico, quantidade de checks ok/warning/error |
| Presets | tempo para aplicar, diff de settings antes/depois |
| Provider test | latencia ms, status HTTP, timeout |
| Ask debug | latencia com debug ligado vs desligado |
| Notes | tempo para listar N notas |
| Benchmark front | tempo da suite, MRR, Recall@3, latencia media |
| Queue/index | arquivos/s, chunks/s, ETA, cancelamento em ms |
| Model discovery | latencia para listar modelos, quantidade encontrada |

## Comandos de validacao

Sempre antes de declarar pronto:

```powershell
cd D:\Dev\Repos\Own\tcc-free-plaud\pipeline
uv run pytest --basetemp .pytest_tmp
```

```powershell
cd D:\Dev\Repos\Own\tcc-free-plaud\UI
npm.cmd run lint
npm.cmd run build
```

```powershell
cd D:\Dev\Repos\Own\tcc-free-plaud
git diff --check
git status --short --branch
```

## Tentativas de quebra obrigatorias

- `embedding_model=fake-hash`;
- provider `openai-compatible` sem API key;
- Ollama offline;
- LM Studio offline;
- CUDA selecionada com torch CPU-only;
- `chroma-default` com CUDA;
- corpus vazio;
- SQLite existe, Chroma vazio;
- Chroma tem vetor stale;
- front dev mode sem PyWebView;
- caminho de suite inexistente;
- cancelar indexacao no meio;
- fechar front durante job em andamento;
- settings com numero invalido (`top_k=abc`);
- reset settings preservando `.env`.

## Definition of done

Plano completo so vira entregue quando:

- Doctor existe no backend e em pelo menos uma superficie visual;
- presets aplicam settings validas sem segredo no JSON;
- provider test prova conexao antes de Ask;
- front consegue operar settings sem terminal;
- testes focados e suite completa passam;
- docs de arquitetura ou handoff sao atualizados;
- entrega final inclui metricas reais, nao estimativa.

## Prompt para executor

```text
Use caveman:caveman, akita-way e senior-second-pass.

Repo: D:\Dev\Repos\Own\tcc-free-plaud
Projeto Python ativo: pipeline/

Leia:
1. AGENTS.md
2. docs/ORDEM_DE_LEITURA_IA.md
3. docs/arquitetura/Arquitetura_Backend.md
4. docs/arquitetura/Arquitetura_Frontend.md
5. docs/plano_execucao/HANDOFF_DOCTOR_PRESETS_FRONT_VALIDACAO.md

Implemente uma slice por vez.
Comece por Doctor/Health Check core.
Use TDD: teste RED, patch minimo, teste focado, suite relevante.
Nao mexa em docs/tcc/.
Nao use vault real em teste automatizado.
Nao salve segredo em user_settings.json.
Ao final, rode senior-second-pass no diff e entregue metricas reais.
```
