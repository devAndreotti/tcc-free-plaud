# Handoff - RAG generativo local/API e consolidacao Git

Criado em 2026-05-24.

## Senior second pass do plano anterior

**Veredito:** aprovado com ajustes.

**Achados**

- [P1] A branch `origin/feature/VisualInterface` nao pode ser mergeada direto na `main`: o diff remove `pipeline/`, datasets, docs e sprints. Correção: importar seletivamente apenas `UI/` quando chegar na etapa frontend.
- [P1] "Suporte a IA local/API key" precisa de fronteira clara de provider. Correção: criar provider OpenAI-compatible, porque cobre Ollama, LM Studio e OpenAI sem prender o core a um SDK.
- [P1] O RAG nao pode chamar IA sem evidencia. Correção: provider generativo so roda depois de hits, claims e citations validados.
- [P2] API key nao deve entrar em `user_settings.json`. Correção: chave fica somente em `.env` ou variavel `FREE_PLAUD_ANSWER_API_KEY`.
- [P2] Git cleanup e destrutivo para refs remotas. Correção: deletar apenas branches ja incorporadas, depois de main validada e pushada.

## Objetivo

Tornar `corpus ask` um RAG funcional: retrieval primeiro, citacoes obrigatorias, geracao de resposta por IA opcional e segura, com suporte a modelos locais OpenAI-compatible e API key por ambiente.

## Escopo V1

- Provider generativo OpenAI-compatible via HTTP `/chat/completions`.
- Compatibilidade com Ollama, LM Studio e OpenAI/cloud.
- Configuracao por settings:
  - `answer_provider`: `extractive`, `openai-compatible`, `ollama`, `lmstudio`
  - `answer_model`
  - `answer_base_url`
  - `answer_temperature`
  - `answer_timeout_seconds`
  - `answer_api_key` somente via env/.env
- `corpus ask`, TUI Ask e menu terminal usam provider quando configurado.
- Se DB/retrieval nao retornar evidencia citavel, retorna `no_answer` sem chamar IA.
- Manter claims, citations, used_sources e limitations.

## Fora do escopo V1

- Streaming.
- Chat multi-turn.
- Reranker.
- UI React integrada ao backend.
- Merge direto de `feature/VisualInterface`.

## Implementacao

1. Criar testes RED para provider OpenAI-compatible e gate "nao chama IA sem evidencia".
2. Implementar provider em `pipeline/src/free_plaud/providers/answer.py`.
3. Adicionar settings em `pipeline/src/free_plaud/app/config.py`.
4. Integrar provider no `corpus ask`, TUI actions e menu terminal.
5. Atualizar docs de arquitetura e este handoff.
6. Rodar suite completa: `uv run pytest --basetemp .pytest_tmp`.
7. Commitar e pushar backend.
8. Criar branch de integracao a partir da base validada e importar apenas `UI/` de `origin/feature/VisualInterface`.
9. Validar que `pipeline/` permanece intacto.
10. Mergear/pushar `main` apenas apos testes.
11. Deletar branches remotas apenas se `git branch -r --merged origin/main` confirmar incorporacao.

## Comandos esperados

```powershell
cd D:\Dev\Repos\Own\tcc-free-plaud\pipeline
uv run free-plaud config set answer_provider ollama
uv run free-plaud config set answer_model llama3.1:8b
uv run free-plaud config set answer_base_url http://localhost:11434/v1
uv run free-plaud corpus ask --question "Qual message broker foi adotado?" --strategy hybrid
```

Para API externa:

```powershell
cd D:\Dev\Repos\Own\tcc-free-plaud\pipeline
$env:FREE_PLAUD_ANSWER_API_KEY="sua-chave"
uv run free-plaud config set answer_provider openai-compatible
uv run free-plaud config set answer_model gpt-4.1-mini
uv run free-plaud config set answer_base_url https://api.openai.com/v1
```

## Criterios de aceite

- `no_answer` nao chama provider generativo.
- `answer` com citations chama provider quando configurado.
- Falha do provider nao quebra RAG: volta para resposta extrativa e adiciona limitation.
- `user_settings.json` nunca grava API key.
- CLI/TUI/menu continuam funcionando sem IA configurada.
- Suite completa verde antes de commit/push.

## Status de implementacao

- Provider OpenAI-compatible implementado em `pipeline/src/free_plaud/providers/answer.py`.
- Settings adicionados em `pipeline/src/free_plaud/app/config.py`.
- `corpus ask` e TUI Ask passam provider generativo opcional para o core RAG.
- Menu terminal expõe campos `answer_*` editáveis, exceto API key.
- RED/GREEN focado validado:
  - `tests/test_answer_provider.py`
  - `tests/test_corpus_ask.py::test_answer_corpus_calls_answer_provider_only_after_citations`
  - `tests/test_corpus_ask.py::test_answer_corpus_does_not_call_answer_provider_without_hits`
  - `tests/test_corpus_ask.py::test_answer_corpus_falls_back_to_extractive_answer_when_provider_fails`
  - `tests/test_config.py::test_answer_api_key_is_env_only_not_user_settings`
