# Handoff - Slice 10 - Deteccao e selecao de modelos locais

Criado em 2026-05-27.

Este arquivo e plano de implementacao. Nenhuma mudanca funcional faz parte deste handoff.

## Contexto

O projeto ja tem:

- `answer_provider`: `extractive`, `ollama`, `lmstudio`, `openai-compatible`;
- `answer_model` salvo em `user_settings.json`;
- API key salva fora do JSON, em `pipeline/.env`;
- teste de provider LLM via `provider test-answer`;
- TUI, menu terminal e front PyWebView consumindo settings reais;
- Ask RAG com regra correta: sem evidencia recuperada, nao chama LLM.

O gap da Slice 10 e operacional:

- hoje o usuario precisa digitar o nome exato do modelo;
- Ollama e LM Studio normalmente ja conseguem expor a lista de modelos;
- o app ainda nao consulta essa lista nem ajuda a preencher `answer_model`.

## Senior second pass

**Veredito:** approved with adjustments.

**Achados**

- [P1] O plano anterior misturava "descobrir modelos" com "salvar modelo". Isso cria risco de a UI listar algo e gravar automaticamente sem confirmacao. Correcao: `list_models()` apenas descobre; salvar continua passando por settings.
- [P1] Ollama nao lista modelos no mesmo endpoint do chat OpenAI-compatible. O chat usa `/v1/chat/completions`, mas a lista nativa fica em `/api/tags`. Correcao: adapter Ollama deve derivar host nativo e chamar `/api/tags`.
- [P1] Servidor offline nao pode quebrar TUI/front. Correcao: retornar resultado estruturado com `status=offline`, `models=[]`, `message` e `latency_ms`.
- [P2] Cache sem chave correta pode mostrar lista velha depois de trocar provider. Correcao: cache por `(provider, normalized_base_url, api_key_present)`.
- [P2] Provider OpenAI-compatible pode ser remoto e exigir chave. Correcao: se for default OpenAI sem API key, retornar `unauthorized`/mensagem clara sem fazer loop de rede.
- [P2] TUI precisa rodar discovery em worker. Mesmo com timeout curto, chamada HTTP no thread principal parece travamento.

**Gaps que este plano fecha**

- Define schema de discovery.
- Define endpoints por provider.
- Define cache e timeout.
- Define comportamento offline.
- Define como CLI, TUI, menu e front usam o mesmo core.
- Define testes RED e validacao full.

## Objetivo

Permitir que usuario liste e escolha modelos expostos por Ollama, LM Studio ou servidor OpenAI-compatible, sem terminal e sem digitar nome no escuro.

## Fora de escopo

- Baixar modelos automaticamente.
- Gerenciar instalacao de Ollama ou LM Studio.
- Escolher pasta de modelo local.
- Streaming de resposta.
- Testar qualidade do modelo.
- Trocar `answer_model` sem acao explicita do usuario.
- Persistir cache em disco.

## Decisoes de arquitetura

1. Backend continua fonte de verdade.
2. Front nao chama Ollama/LM Studio direto.
3. `providers/model_discovery.py` encapsula endpoints e parsing.
4. `answer_model` continua string manual editavel.
5. Listar modelos nao salva settings.
6. Escolher modelo na UI apenas preenche draft; salvar settings continua sendo passo separado.
7. API key nao aparece em payload, log, erro ou cache key bruta.
8. Discovery nunca chama Ask e nunca usa corpus.

## Contrato backend

Criar:

```text
pipeline/src/free_plaud/providers/model_discovery.py
```

Tipos propostos:

```python
ModelDiscoveryStatus = Literal[
    "ok",
    "not_applicable",
    "offline",
    "unauthorized",
    "error",
]

class ModelInfo(BaseModel):
    id: str
    label: str
    provider: str
    details: dict[str, object] = Field(default_factory=dict)

class ModelDiscoveryResult(BaseModel):
    provider: str
    base_url: str | None
    status: ModelDiscoveryStatus
    models: list[ModelInfo] = Field(default_factory=list)
    latency_ms: int
    cached: bool = False
    message: str | None = None
```

Funcao principal:

```python
def list_answer_models(
    settings: Settings | None = None,
    *,
    timeout_seconds: float = 2.0,
    use_cache: bool = True,
) -> ModelDiscoveryResult:
    ...
```

## Regras por provider

### Extractive

Retorna sem rede:

```json
{
  "provider": "extractive",
  "base_url": null,
  "status": "not_applicable",
  "models": [],
  "message": "Provider extractive nao usa modelo generativo."
}
```

### Ollama

Default:

```text
http://localhost:11434/api/tags
```

Se `answer_base_url` estiver:

- `http://localhost:11434/v1` -> usar `http://localhost:11434/api/tags`;
- `http://localhost:11434/v1/` -> usar `http://localhost:11434/api/tags`;
- `http://localhost:11434` -> usar `http://localhost:11434/api/tags`.

Payload esperado:

```json
{
  "models": [
    {
      "name": "llama3.1:8b",
      "modified_at": "...",
      "size": 123,
      "digest": "...",
      "details": {}
    }
  ]
}
```

Mapeamento:

- `ModelInfo.id = model["name"]`;
- `ModelInfo.label = model["name"]`;
- `details` pode conter `size`, `modified_at`, `digest`, `family`, `parameter_size`, quando existirem.

### LM Studio

Default:

```text
http://localhost:1234/v1/models
```

Payload esperado:

```json
{
  "data": [
    {
      "id": "local-model",
      "object": "model"
    }
  ]
}
```

Mapeamento:

- `ModelInfo.id = item["id"]`;
- `ModelInfo.label = item["id"]`;
- `details` guarda campos extras seguros.

### OpenAI-compatible generico

Default:

```text
https://api.openai.com/v1/models
```

Regras:

- se `answer_base_url` estiver vazio e `answer_api_key` estiver vazio, retornar `unauthorized` sem chamar rede;
- se `answer_base_url` for local/custom, tentar `/models` mesmo sem chave;
- se `answer_api_key` existir, mandar `Authorization: Bearer ...`;
- nunca devolver token em erro.

## Cache

Cache em memoria por processo, TTL curto.

```python
CACHE_TTL_SECONDS = 10
cache_key = (
    provider,
    normalized_base_url,
    bool(api_key),
)
```

Regras:

- cache nao guarda API key;
- resultado retornado do cache deve vir com `cached=True`;
- erro `offline` pode ser cacheado por pouco tempo para evitar spam de clique;
- testes devem conseguir limpar cache.

## Erros e seguranca

Mapeamento de erro:

| Caso | status | message |
| --- | --- | --- |
| provider `extractive` | `not_applicable` | nao usa modelo generativo |
| `URLError`, connection refused, timeout | `offline` | servidor indisponivel |
| HTTP 401/403 | `unauthorized` | credencial ausente/invalida |
| JSON invalido | `error` | payload invalido |
| formato sem lista | `error` | resposta nao contem modelos |
| base_url invalida | `error` | use http:// ou https:// |

Nao retornar corpo bruto de erro remoto quando ele puder conter dado sensivel.

## Superficies

### CLI

Adicionar em `pipeline/src/free_plaud/providers/cli.py`:

```powershell
cd D:\Dev\Repos\Own\tcc-free-plaud\pipeline
uv run free-plaud provider list-models
```

Saida JSON:

```json
{
  "provider": "ollama",
  "base_url": "http://localhost:11434",
  "status": "ok",
  "models": [
    {
      "id": "llama3.1:8b",
      "label": "llama3.1:8b",
      "provider": "ollama",
      "details": {
        "size": 4661224676
      }
    }
  ],
  "latency_ms": 34,
  "cached": false,
  "message": null
}
```

### Menu terminal

Adicionar em `terminal_settings.py` ou menu provider:

```text
[M] Listar modelos do provider
```

Fluxo:

1. mostra provider/base_url/status;
2. se houver modelos, lista numerada;
3. usuario pode escolher numero para salvar `answer_model`;
4. ENTER mantem valor atual;
5. apos salvar, limpar runtime.

Exemplo:

```text
Modelos encontrados em ollama:

[1] llama3.1:8b
[2] mistral:7b

Escolha modelo ou ENTER para manter:
```

### TUI

Na aba `Settings`:

- adicionar botao `Listar modelos`;
- rodar em `@work(thread=True)`;
- painel Estado mostra:
  - provider;
  - base_url;
  - status;
  - latencia;
  - cached;
  - modelos encontrados.

V1 aceitavel:

- lista modelos para copiar;
- usuario salva no campo `answer_model`.

V1 melhor:

- cada modelo vira `ActionCell`;
- clicar preenche `answer_model`;
- nao salva ate clicar `Salvar`.

### Front PyWebView

`UI/main.py`:

```python
def listAnswerModels(self) -> dict:
    return list_answer_models(runtime/settings).model_dump(mode="json")
```

`UI/src/services/bridge.ts`:

```ts
export type ModelDiscoveryStatus =
  | 'ok'
  | 'not_applicable'
  | 'offline'
  | 'unauthorized'
  | 'error'

export interface ModelInfo {
  id: string
  label: string
  provider: string
  details: Record<string, unknown>
}

export interface ModelDiscoveryResult {
  provider: string
  base_url: string | null
  status: ModelDiscoveryStatus
  models: ModelInfo[]
  latency_ms: number
  cached: boolean
  message: string | null
}
```

`SettingsModal.tsx`:

- botao `Listar modelos` perto de `answer_model`;
- loading local;
- lista clicavel;
- clicar em modelo preenche draft de `answer_model`;
- `Salvar backend` continua gravando.

## Arquivos provaveis

Backend:

- `pipeline/src/free_plaud/providers/model_discovery.py`
- `pipeline/src/free_plaud/providers/cli.py`
- `pipeline/src/free_plaud/terminal_settings.py`
- `pipeline/src/free_plaud/tui/app.py`
- `UI/main.py`

Frontend:

- `UI/src/services/bridge.ts`
- `UI/src/components/SettingsModal.tsx`
- `UI/src/components/SettingsModal.test.tsx` se criado

Testes:

- `pipeline/tests/test_model_discovery.py`
- `pipeline/tests/test_cli.py`
- `pipeline/tests/test_terminal_menu.py`
- `pipeline/tests/test_tui_app.py`
- `pipeline/tests/test_ui_bridge.py`
- `UI/src/components/SettingsModal.test.tsx`

Docs:

- `docs/plano_execucao/CONTRATOS_FRONT_BACK.md`
- `docs/arquitetura/Arquitetura_Frontend.md`, se o contrato novo virar permanente

## Testes RED obrigatorios

### Core

```powershell
cd D:\Dev\Repos\Own\tcc-free-plaud\pipeline
uv run pytest --basetemp .pytest-tmp-slice10-core tests/test_model_discovery.py -q
```

Casos:

- provider `extractive` retorna `not_applicable` sem rede;
- Ollama default chama `/api/tags`;
- Ollama com base_url `/v1` chama `/api/tags` no host raiz;
- Ollama payload com `models[].name` vira lista de `ModelInfo`;
- LM Studio chama `/v1/models`;
- OpenAI-compatible custom chama `/models`;
- OpenAI-compatible default sem API key retorna `unauthorized`;
- HTTP 401/403 vira `unauthorized`;
- timeout/connection refused vira `offline`;
- JSON invalido vira `error`;
- cache retorna `cached=True` na segunda chamada;
- trocar provider/base_url nao reaproveita cache antigo;
- erro nao contem API key.

### CLI/menu/TUI/PyWebView

```powershell
cd D:\Dev\Repos\Own\tcc-free-plaud\pipeline
uv run pytest --basetemp .pytest-tmp-slice10-surfaces tests/test_cli.py tests/test_terminal_menu.py tests/test_tui_app.py tests/test_ui_bridge.py -q
```

Casos:

- CLI imprime JSON estruturado;
- menu mostra modelos e permite escolher;
- menu ENTER nao altera `answer_model`;
- TUI renderiza offline sem crash;
- TUI clique em modelo preenche campo, mas nao salva antes de `Salvar`;
- PyWebView expõe `listAnswerModels`;
- API key nao aparece no payload.

### Front

```powershell
cd D:\Dev\Repos\Own\tcc-free-plaud\UI
npm.cmd test
npm.cmd run lint
npm.cmd run build
```

Casos:

- SettingsModal mostra botao `Listar modelos`;
- resultado `ok` renderiza modelos;
- clicar em modelo preenche input de modelo;
- resultado `offline` renderiza mensagem;
- modo dev mock cobre sucesso e offline.

## Validacao full obrigatoria

Antes de PR:

```powershell
cd D:\Dev\Repos\Own\tcc-free-plaud\pipeline
uvx ruff check src tests --output-format=json > ..\coverage\ruff.json
uv run pytest --basetemp .pytest-tmp-slice10-full -q --cov=src --cov-report=json:../coverage/coverage.json --cov-report=xml:../coverage/coverage.xml --cov-report=term-missing
uvx pip-audit --path .venv
```

```powershell
cd D:\Dev\Repos\Own\tcc-free-plaud\UI
npm.cmd test
npm.cmd run lint
npm.cmd run build
```

```powershell
cd D:\Dev\Repos\Own\tcc-free-plaud
qg-chk
qg-doc
git diff --check
git status --short --branch
```

## Smokes manuais recomendados

### Ollama offline

Com Ollama fechado:

```powershell
cd D:\Dev\Repos\Own\tcc-free-plaud\pipeline
uv run free-plaud config set answer_provider ollama
uv run free-plaud provider list-models
```

Esperado:

- `status=offline`;
- exit code 0;
- nenhum traceback.

### Ollama online

Com Ollama aberto:

```powershell
cd D:\Dev\Repos\Own\tcc-free-plaud\pipeline
uv run free-plaud provider list-models
```

Esperado:

- `status=ok`;
- `models.length >= 1`, se houver modelo baixado;
- `latency_ms` reportado.

### LM Studio

Com servidor LM Studio ligado:

```powershell
cd D:\Dev\Repos\Own\tcc-free-plaud\pipeline
uv run free-plaud config set answer_provider lmstudio
uv run free-plaud provider list-models
```

Esperado:

- `status=ok` ou `offline`;
- sem crash.

## Metricas de entrega

Relatorio final da implementacao deve trazer numeros reais:

| Metrica | Como medir |
| --- | --- |
| tempo discovery Ollama offline | `latency_ms` do comando |
| tempo discovery Ollama online | `latency_ms` do comando |
| quantidade de modelos | `len(models)` |
| efeito cache | primeira chamada vs segunda chamada |
| testes backend | total passed |
| testes front | total passed |
| build front | tempo e status |
| Quality Gate | status PR |

Se Ollama/LM Studio nao estiverem instalados na maquina, usar servidor fake nos testes e declarar smoke real como nao aplicavel.

## Ordem de implementacao sugerida

1. Core `model_discovery.py` com testes RED.
2. CLI `provider list-models`.
3. PyWebView bridge `listAnswerModels`.
4. Front `SettingsModal`.
5. Menu terminal.
6. TUI em worker.
7. Docs de contrato.
8. Validacao full.

Motivo: core primeiro evita UI inventar regra; front e TUI so renderizam contrato.

## Riscos e mitigacoes

| Risco | Impacto | Mitigacao |
| --- | --- | --- |
| endpoint Ollama errado | lista sempre vazia/offline | testar `/api/tags` e stripping de `/v1` |
| UI travar com servidor offline | experiencia ruim | timeout curto + worker no TUI |
| vazamento de API key | seguranca | nunca incluir token em result/message/cache |
| cache velho | usuario escolhe modelo errado | cache key por provider/base_url/api_key_present |
| OpenAI remoto sem key | erro confuso | retornar `unauthorized` sem rede quando default OpenAI sem key |
| mock front diverge do real | bug so aparece no PyWebView | testes de bridge + mock com sucesso/offline |

## Definition of done

Slice 10 esta pronta quando:

- `free-plaud provider list-models` existe;
- backend retorna schema estruturado em todos os providers;
- offline nao gera traceback;
- TUI/menu/front conseguem listar modelos;
- usuario consegue preencher `answer_model` a partir da lista;
- salvar modelo ainda passa por settings;
- API key nao aparece em JSON/log;
- testes focados e suites full passam;
- PR abre, Quality Gate passa e mergeState fica `CLEAN`.

