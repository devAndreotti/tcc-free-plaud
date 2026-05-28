# Handoff - Qualidade do RAG local e Ask grounded

Criado em 2026-05-28.

Este arquivo e plano de implementacao. Nenhuma mudanca funcional faz parte deste handoff.

## Contexto real validado

Teste manual feito contra runtime local, nao mock:

- Corpus: 470 notas, 3120 chunks SQLite, 3120 chunks FTS, 3120 chunks Chroma.
- `corpus status`: `clean`.
- Provider: Ollama local.
- Modelo instalado: `llama3.2:3b`.
- `provider list-models`: `ok`, encontrou `llama3.2:3b`, latencia 2163 ms.
- `provider test-answer`: `error`, latencia 13064 ms, erro `Provider respondeu diferente de ok.`
- Resposta crua do modelo para `Responda somente: ok`: `Ok. Voce gostaria de discutir algo em particular ou apenas comecar uma conversa?`
- `doctor`: `error`, porque `embedding_model=fake-hash`.
- Ask `lexical` com Ollama funciona sem embedding.
- Ask `hybrid` funciona quando `FREE_PLAUD_EMBEDDING_MODEL=chroma-default` e `FREE_PLAUD_EMBEDDING_DEVICE=cpu`.
- Pergunta inexistente retornou `no_answer` com motivo `missing_named_anchor`, comportamento correto.

## Problemas observados

### P0 - Config real permite `fake-hash`

`fake-hash` e fixture de teste, mas apareceu em `data/results/user_settings.json`.

Efeito:

- TUI/CLI em `hybrid` quebram com `Embedding model nao suportado: fake-hash`.
- `corpus status` fica `clean`, mas Ask real nao esta pronto.
- `doctor` detecta, mas o usuario so ve depois de rodar diagnostico.

### P1 - Teste do provider gera falso negativo

`provider test-answer` exige resposta exatamente `ok`.

O Ollama respondeu com texto contendo `Ok`, mas com frase extra. Endpoint esta vivo, modelo respondeu, contrato HTTP esta correto, mas o teste marcou erro.

### P1 - Prompt generativo nao segura alucinacao

O provider ja diz para usar somente contexto, mas o modelo ainda inventou conteudo:

- Em `Estrutura Disco D`, citou "blocos de 64 KB", "indices de arquivo", "mapeamento de diretorios", sem evidencia visivel no chunk recuperado.
- Em pergunta sobre TCC, respondeu que nao tinha dados suficientes e depois sugeriu perguntas genericas, mesmo com citacao recuperada.

### P1 - Contexto enviado ao LLM e fraco

Hoje `_contexts_for_answer_provider()` envia:

- claim extrativo;
- snippets truncados de citations;
- ids de chunks.

Isso pode deixar o LLM com pouca evidencia concreta. Quando o chunk citado contem frontmatter e titulo, o modelo recebe pouco conteudo util.

### P1 - Status final aceita resposta generativa ruim

Depois de chamar provider, o sistema troca `answer` pelo texto do LLM e mantem `status=answer`.

Nao ha validacao pos-geracao para detectar:

- resposta dizendo "nao consegui recuperar";
- resposta generica fora do corpus;
- termos ausentes nas evidencias;
- resposta sem vinculo lexical com claims/citations.

### P2 - Ranking tem anchor fraco

Na pergunta `O que e Estrutura Disco D?`, `Estrutura Disco C` apareceu antes de `Estrutura Disco D` em alguns hits.

Motivo provavel:

- token curto `D` nao pesa como anchor nomeado;
- titulo/source_path nao entram forte no score final;
- pergunta com entidade curta perde especificidade.

### P2 - GPU/latencia nao esta clara

`nvidia-smi` mostrou GPU ocupada, mas nao mostrou processo Ollama claramente.

Latencias medidas:

- provider list: 2163 ms;
- provider test: 13064 ms;
- Ask lexical com LLM: 5229 ms a 12647 ms;
- Ask hybrid com LLM: 17910 ms a 20307 ms;
- no_answer sem chamar LLM: 4479 ms.

Precisa separar latencia de retrieval, prompt, provider e validacao.

## Auditoria adversarial - evidencias reproduzidas

Modo usado: `audit` + `fix-plan`, somente alvo local/autorizado. Checks destrutivos, carga agressiva, alteracao de corpus real e uso de vault real em teste automatizado ficam fora.

### Prova A - `fake-hash` e raiz do crash em Ask hybrid

Comando:

```powershell
cd D:\Dev\Repos\Own\tcc-free-plaud\pipeline
uv run free-plaud corpus ask -q "O que é Estrutura Disco D?" --strategy hybrid --top-k 4
```

Resultado observado:

```text
ValueError: Embedding model nao suportado: fake-hash
```

Controle:

```powershell
uv run free-plaud corpus ask -q "O que é Estrutura Disco D?" --strategy lexical --top-k 4
```

Resultado observado:

- `status=answer`;
- `latency_ms=18316`;
- provider Ollama foi chamado;
- sem carregar embedder.

Conclusao:

- causa raiz do crash nao e Ollama, corpus, SQLite, FTS ou Chroma;
- e configuracao de embedding invalida sendo aceita ate o ponto de execucao;
- Slice 1 deve mexer em validacao/UX de settings antes de mexer em retrieval.

### Prova B - `provider test-answer` mede obediencia literal, nao disponibilidade

Comando:

```powershell
uv run free-plaud provider test-answer
```

Resultado observado:

```json
{
  "provider": "ollama",
  "model": "llama3.2:3b",
  "status": "error",
  "error": "Provider respondeu diferente de ok."
}
```

Controle direto contra Ollama:

```python
POST http://localhost:11434/v1/chat/completions
{"model":"llama3.2:3b","messages":[{"role":"user","content":"Responda somente: ok"}],"temperature":0}
```

Resultado observado:

```json
{
  "content": "Ok.",
  "contains_ok": true,
  "length": 3
}
```

Conclusao:

- provider esta vivo;
- contrato HTTP esta OK;
- teste falha porque compara `ok.` contra `ok`;
- Slice 2 deve mudar o criterio para "payload valido + content nao vazio" e tratar divergencia literal como aviso.

### Prova C - contexto enviado ao LLM e pequeno/fraco

Probe local com provider fake capturando `_contexts_for_answer_provider()`:

```json
{
  "status": "answer",
  "claim_texts": [
    "💾 Estrutura Disco D: Organização Recomendada"
  ],
  "contexts_count": 1,
  "context_chars": 356,
  "context_preview": "[1] chunks=estrutura-disco-d--3fbdccb1be::v1::ofs-000000-000800::cc9d9b5352\nClaim: 💾 Estrutura Disco D: Organização Recomendada\nTrecho: --- type: nota area: ti topic: estrutura-disco-d status: em-andamento created: 2026-03-25 updated: 2026-04-18 tags: - area/ti - tema/windows - tipo/nota --- # 💾 Estrutura Disco D: Organização Recomendada ## Ideia prin...",
  "probe_terms_present_in_context": {
    "blocos de dados": false,
    "índice de blocos": false,
    "mecanismos de segurança": false,
    "64 KB": false
  }
}
```

Resposta real do LLM no mesmo tema inventou:

- "blocos de dados";
- "indice de blocos";
- "mecanismos de seguranca";
- "64 KB" em rodada anterior.

Conclusao:

- raiz nao e so "modelo local pequeno";
- o contexto entregue esta pobre e permite o modelo completar lacunas;
- Slice 3 e Slice 4 atacam entrada/prompt;
- Slice 5 precisa validar saida, porque prompt sozinho nao e garantia.

### Prova D - ranking nao respeita anchor curto `D`

Probe `hybrid` com override seguro:

```powershell
$env:FREE_PLAUD_EMBEDDING_MODEL='chroma-default'
$env:FREE_PLAUD_EMBEDDING_DEVICE='cpu'
uv run free-plaud corpus ask -q "O que é Estrutura Disco D?" --strategy hybrid --top-k 6 --debug
```

Top hits observados:

| ordem | note_id | score | termos |
| --- | --- | ---: | --- |
| 1 | `estrutura-disco-c--cf0af4dc3c` | 0.040719 | `estrutura`, `disco` |
| 2 | `estrutura-disco-d--3fbdccb1be` | 0.040587 | `estrutura`, `disco` |
| 3 | `docker-vs-maquinas-virtuais--58c2d93784` | 0.038228 | `estrutura`, `disco` |
| 4 | `estrutura-disco-d--3fbdccb1be` | 0.035759 | `disco` |

Conclusao:

- `D` nao esta entrando como evidencia discriminante;
- titulo/source_path nao recebem boost suficiente;
- Slice 6 deve ser rerank pequeno, testavel, nao reescrita de retrieval.

## Root-cause matrix

| Sintoma | Causa raiz confirmada | Arquivos provaveis | Patch minimo | Teste de regressao |
| --- | --- | --- | --- | --- |
| Hybrid quebra com `fake-hash` | Setting de teste aceita em runtime vetorial | `providers/embed.py`, `corpus/cli.py`, `tui/actions.py`, `terminal_menu.py` | validar antes de carregar embedder e retornar erro acionavel | CLI/TUI/menu com `fake-hash` nao geram traceback |
| Provider test falha com Ollama vivo | comparacao literal `content.casefold() != "ok"` | `providers/answer.py`, `tests/test_answer_provider.py` | aceitar content nao vazio; divergencia vira warning/preview | resposta `Ok.` passa |
| LLM inventa fatos | contexto pobre + prompt permissivo + sem pos-validacao | `corpus/ask.py`, `providers/answer.py` | contexto maior/limpo + prompt hard + validator | termos ausentes no contexto causam fallback/no_answer |
| `D` perde para `C` | anchor curto ignorado no score | `corpus/ask.py`, `retrieval/search.py` | rerank por titulo/source_path/anchor adjacente | `Estrutura Disco D` ranqueia D antes de C |
| Latencia opaca | debug nao separa etapas | `corpus/ask.py`, `retrieval/debug.py` | timings por retrieval/context/provider/validation | `--debug` inclui tempos |

## Objetivo

Tornar Ask com IA local confiavel o bastante para uso real:

1. impedir config de teste em runtime;
2. testar provider local sem falso negativo;
3. mandar contexto melhor ao LLM;
4. instruir o modelo a nao sair da evidencia;
5. validar resposta gerada antes de marcar `status=answer`;
6. melhorar ranking para anchors curtos;
7. medir latencia por etapa.

## Akita Way - contrato de execucao

Este plano deve ser executado como XP + IA, nao como "vibe coding".

### Esqueleto antes de codigo

- Produto: Ask local-first com RAG citavel e LLM opcional.
- Stack: Python 3.12, Typer, Pydantic, SQLite, FTS5, ChromaDB, Ollama/OpenAI-compatible.
- Fronteiras:
  - `providers/answer.py`: transporte, prompt base e parsing de provider;
  - `corpus/ask.py`: retrieval, contexto, policy de `no_answer`, pos-validacao;
  - `providers/embed.py`: validacao e instanciacao de embedder;
  - UI/TUI/menu: exibem estado e erros, nao decidem policy de RAG.
- Never do:
  - nao usar vault real em teste automatizado;
  - nao baixar modelo automaticamente;
  - nao salvar segredo em `user_settings.json`;
  - nao chamar LLM quando nao ha evidencia citavel;
  - nao marcar `status=answer` quando LLM diz que nao encontrou;
  - nao reindexar corpus automaticamente ao trocar embedding.

### Loop por slice

1. Definir comportamento em uma frase.
2. Escrever teste RED minimo.
3. Provar que falha pelo motivo esperado.
4. Implementar menor patch.
5. Rodar teste focado.
6. Rodar gate local quando a slice tocar caminho critico.
7. Revisar diff: escopo, fronteira, segredo, fallback, UX de erro.
8. Abrir PR pequeno.

### Definition of Done por slice

- Pelo menos um teste cobre o bug reproduzido.
- Erro externo vira mensagem controlada.
- Fallback extrativo continua funcionando.
- `extractive` continua sem chamar provider.
- `lexical` continua sem exigir embedder.
- `hybrid/vector` falham cedo se embedding invalido.
- Debug nao vaza API key.
- Documento/contrato atualizado se payload mudar.

## Fora de escopo

- Streaming de resposta.
- Chat multi-turn.
- Troca de ChromaDB por outro vector store.
- Download automatico de modelos.
- Fine-tuning.
- Uso de vault real em teste automatizado.
- Qualidade academica final do texto do TCC.

## Contrato desejado

### Resposta generativa grounded

O LLM deve receber instrucao mais dura:

```text
Voce e uma camada de redacao sobre evidencias recuperadas.
Use somente fatos presentes nos contextos.
Nao use conhecimento externo.
Nao complete lacunas.
Nao escreva exemplos genericos.
Se a evidencia nao responder diretamente, responda exatamente:
NAO_ENCONTRADO: os dados recuperados nao sustentam resposta.

Cada frase factual deve ser suportada por pelo menos um contexto.
Preserve nomes, caminhos, numeros e termos tecnicos como aparecem.
Nao explique alem do que esta nos contextos.
```

### Saida recomendada V1

Manter texto livre, mas com sentinela obrigatoria para insuficiencia:

```text
NAO_ENCONTRADO: os dados recuperados nao sustentam resposta.
```

Razao: JSON estruturado seria melhor, mas aumenta risco de quebra com modelos pequenos. Sentinela e suficiente para V1.

### Pos-validacao obrigatoria

Depois do LLM responder:

- se resposta comecar com `NAO_ENCONTRADO`, retornar `no_answer`;
- se resposta contem frases genericas de insuficiencia e tambem sugestoes, retornar `no_answer`;
- se resposta nao compartilha termos informativos minimos com claims/citations, descartar e voltar para answer extrativa;
- se resposta contem numeros/termos fortes que nao aparecem em nenhum contexto, adicionar limitation ou descartar;
- se provider falhar ou resposta for invalida, manter fallback extrativo atual.

## Plano por slices

### Slice 1 - Bloquear `fake-hash` em runtime

Objetivo:

- impedir que TUI/CLI Ask tentem carregar `fake-hash`;
- deixar erro acionavel antes do stack trace.

Mudancas:

- Criar helper `validate_runtime_embedding_settings(settings)`.
- Usar no `corpus ask`, TUI Ask, menu terminal e benchmark quando strategy usa vetor.
- Mensagem:
  - `fake-hash e modelo de teste. Use chroma-default ou sentence-transformer:<modelo>. Rode: uv run free-plaud config preset apply cpu_rapido`
- Avaliar se `corpus status` deve incluir `runtime_ready=false` quando embedding invalido.

Testes RED:

- `corpus ask --strategy hybrid` com `fake-hash` retorna erro controlado sem traceback.
- `doctor` continua apontando P0.
- `corpus status` continua validando DB, mas payload novo mostra warning de settings se implementado.

Validacao:

```powershell
cd D:\Dev\Repos\Own\tcc-free-plaud\pipeline
uv run pytest --basetemp .pytest-tmp-rag-quality -q tests/test_cli.py tests/test_tui_app.py tests/test_terminal_menu.py
```

Aceite:

- usuario nao ve `ValueError` cru;
- TUI mostra acao concreta;
- `fake-hash` fica permitido apenas em testes com settings injetado.

### Slice 2 - Corrigir `provider test-answer`

Objetivo:

- testar disponibilidade do modelo, nao obediencia perfeita ao prompt.

Mudancas:

- Trocar criterio de sucesso:
  - status `ok` se endpoint responde payload valido e content nao vazio;
  - adicionar campo opcional `content_preview` redigido/truncado;
  - manter warning interno se resposta nao contem `ok`, mas nao falhar conectividade.
- Alternativa sem mudar schema: manter `status=ok` e `error=None` quando content nao vazio.

Testes RED:

- provider retorna `Ok. ...` -> `status=ok`.
- provider retorna content vazio -> `status=error`.
- payload invalido -> `status=error`.
- HTTP 401 nao vaza segredo.

Aceite:

- Ollama `llama3.2:3b` passa no teste real;
- UI/TUI/menu deixam claro que provider esta vivo.

### Slice 3 - Context builder com evidencia suficiente

Objetivo:

- mandar ao LLM contexto mais completo e menos frontmatter-only.

Mudancas:

- Substituir `_contexts_for_answer_provider(claims)` por builder que recebe `claims`, `hits`, `note_lookup`.
- Para cada citacao, incluir:
  - source_path;
  - title/note_id;
  - chunk_id;
  - claim extrativo;
  - trecho limpo do chunk;
  - opcional: chunk anterior/proximo se mesmo note_id e budget permitir.
- Remover ou reduzir frontmatter no contexto de LLM.
- Limitar budget por caracteres, exemplo:
  - max 6000 chars total;
  - max 1500 chars por contexto;
  - top contexts por score/citation.

Testes RED:

- contexto inclui fonte e chunk_id;
- contexto remove frontmatter repetitivo;
- contexto nao excede budget;
- pergunta que recupera titulo + conteudo manda conteudo real, nao so metadata.

Aceite:

- prompt fica menor que timeout normal;
- LLM tem evidencia suficiente para responder sem inventar.

### Slice 4 - Prompt grounded hard

Objetivo:

- reduzir alucinacao do modelo local pequeno.

Mudancas:

- Extrair prompt para constante/fn testavel em `providers/answer.py`.
- Instruir:
  - usar somente contextos;
  - nao usar conhecimento externo;
  - nao gerar exemplos;
  - retornar sentinela `NAO_ENCONTRADO` quando evidencia insuficiente;
  - responder curto;
  - preservar nomes e numeros exatamente.
- Usuario pediu: "n fale nada fora o que esta aqui". Isso vira regra explicita de prompt.

Prompt V1 proposto:

```text
Voce deve responder em portugues brasileiro usando exclusivamente os CONTEXTOS.
Nao use conhecimento externo.
Nao complete lacunas.
Nao crie exemplos, listas ou explicacoes que nao estejam nos CONTEXTOS.
Se os CONTEXTOS nao responderem diretamente a PERGUNTA, responda exatamente:
NAO_ENCONTRADO: os dados recuperados nao sustentam resposta.
Cada frase factual precisa estar suportada por um CONTEXTO.
Preserve numeros, nomes e termos tecnicos exatamente como aparecem.
```

Testes RED:

- corpo do request contem as regras acima;
- prompt inclui sentinela;
- temperatura default continua baixa.

Aceite:

- pergunta com contexto fraco tende a `NAO_ENCONTRADO`;
- resposta nao deve conter sugestoes genericas.

### Slice 5 - Pos-validador de resposta generativa

Objetivo:

- nao aceitar texto bonito se ele viola evidencia.

Mudancas:

- Criar `validate_generated_answer(question, answer, contexts, claims)`.
- Resultado:
  - `accept`;
  - `no_answer`;
  - `fallback_extractive`.
- Regras V1:
  - sentinela `NAO_ENCONTRADO` -> `no_answer`;
  - frases tipo "nao consegui recuperar" + conteudo generico -> `no_answer`;
  - numeros presentes na resposta e ausentes no contexto -> fallback;
  - termos capitalizados/anchors fortes ausentes no contexto -> fallback;
  - baixa sobreposicao lexical com claims -> fallback.

Testes RED:

- resposta inventando `64 KB` quando contexto nao contem `64 KB` -> fallback extrativo;
- resposta com `NAO_ENCONTRADO` -> `no_answer`;
- resposta generica com sugestoes -> `no_answer`;
- resposta fiel curta -> aceita.

Aceite:

- status final nao fica `answer` quando o proprio LLM diz que nao achou;
- answer generativa so substitui extrativa quando passa validacao.

### Slice 6 - Ranking por anchors e titulo/source_path

Objetivo:

- `Estrutura Disco D` deve ganhar de `Estrutura Disco C` quando pergunta tem `D`.

Mudancas:

- Revisar `extract_named_query_terms` para capturar anchors curtos quando fazem parte de frase/titulo.
- Adicionar feature de score:
  - match exato da frase no titulo/source_path;
  - match de token curto adjacente a termos fortes;
  - penalizar documento similar que troca anchor curto (`C` vs `D`) quando pergunta especifica `D`.
- Aplicar em lexical e hybrid antes de `fuse_hits_by_rank` ou como rerank pos-fusion.

Testes RED:

- corpus pequeno com notas `Estrutura Disco C` e `Estrutura Disco D`;
- pergunta `O que e Estrutura Disco D?`;
- primeiro hit deve ser D.

Aceite:

- melhora ranking sem quebrar perguntas sem anchor curto;
- nao cria falso `no_answer` para pergunta ampla.

### Slice 7 - Metricas e debug por etapa

Objetivo:

- medir onde o tempo vai.

Mudancas:

- Expandir `AskDebug` ou adicionar timings em payload debug:
  - `retrieval_ms`;
  - `context_build_ms`;
  - `provider_ms`;
  - `validation_ms`;
  - `total_ms`;
  - `provider_model`;
  - `answer_provider`.
- TUI pode consumir depois, mas esta slice backend primeiro.

Testes RED:

- `--debug` inclui timings;
- sem provider, `provider_ms=0` ou ausente de forma documentada;
- com provider fake, provider_ms aparece.

Aceite:

- comparacao antes/depois possivel;
- latencia nao vira chute.

### Slice 8 - Smoke real opcional para Ollama

Objetivo:

- criar teste manual padronizado sem depender de vault real em CI.

Mudancas:

- Criar doc/roteiro ou comando `provider smoke-local` opcional?
- Usar dataset temporario pequeno gerado em teste manual:
  - nota `Estrutura Disco D`;
  - nota `Estrutura Disco C`;
  - pergunta conhecida;
  - pergunta inexistente.
- Nao rodar no CI por default.

Aceite manual:

```powershell
cd D:\Dev\Repos\Own\tcc-free-plaud\pipeline
uv run free-plaud config preset apply cpu_rapido
uv run free-plaud config set answer_provider ollama
uv run free-plaud config set answer_model llama3.2:3b
uv run free-plaud provider list-models
uv run free-plaud provider test-answer
uv run free-plaud corpus ask -q "O que e Estrutura Disco D?" --strategy hybrid --top-k 6 --debug
uv run free-plaud corpus ask -q "Existe algo sobre quantum banana inexistente?" --strategy hybrid --top-k 4 --debug
```

## Ordem recomendada

1. Slice 1 - `fake-hash` controlado.
2. Slice 2 - provider test sem falso negativo.
3. Slice 3 - contexto melhor.
4. Slice 4 - prompt hard.
5. Slice 5 - pos-validador.
6. Slice 6 - anchors/ranking.
7. Slice 7 - timings.
8. Slice 8 - smoke manual.

Razao:

- Primeiro remove quebra operacional.
- Depois separa "modelo vivo" de "modelo obediente".
- Depois melhora entrada do LLM.
- Depois endurece prompt.
- Depois valida saida.
- Ranking e metrica entram depois para nao misturar causa.

## Contratos detalhados por slice

### Slice 1 - Contrato `runtime embedding guard`

Comportamento:

- Dado `embedding_model=fake-hash`;
- quando usuario executar Ask com `strategy=vector` ou `strategy=hybrid`;
- entao o app deve falhar antes de inicializar Chroma/SentenceTransformer;
- e deve retornar erro operacional com comando de correcao;
- e nao deve imprimir traceback em fluxo CLI normal.

Teste RED sugerido:

```python
def test_corpus_ask_hybrid_rejects_fake_hash_with_actionable_error(...):
    ...
```

Superficies:

- CLI: `free-plaud corpus ask`;
- TUI: `ask_corpus`;
- menu terminal: `_ask`;
- benchmark: somente quando tenta strategy vetorial.

Patch minimo:

- helper em `providers/embed.py` ou novo `app/runtime_validation.py`;
- usar helper antes de `get_embedder()`;
- erro tipado ou mensagem padrao.

Anti-regressao adversarial:

- `strategy=lexical` com `fake-hash` deve continuar funcionando;
- settings de teste injetadas com `fake-hash` em testes unitarios existentes nao devem quebrar suites que nao instanciam embedder real.

### Slice 2 - Contrato `provider health`

Comportamento:

- `provider test-answer` testa conectividade, auth, payload e content nao vazio;
- nao testa aderencia perfeita do modelo a instrucao curta;
- se o modelo responder `Ok.`, `ok`, `OK`, `servico pronto`, status deve ser `ok`;
- se content vazio, status `error`;
- se HTTP 401, status `error` sem segredo.

Teste RED sugerido:

```python
def test_provider_test_accepts_non_empty_model_response(...):
    ...

def test_provider_test_rejects_empty_content(...):
    ...
```

Patch minimo:

- alterar criterio no final de `test_answer_provider()`;
- opcional: incluir `content_preview` truncado em schema, mas isso muda contrato front/TUI;
- se evitar mudanca de schema, usar apenas `status=ok`.

Decisao recomendada:

- V1 sem mudar schema: menor risco.
- V2 pode adicionar `warning`/`content_preview` no contrato.

### Slice 3 - Contrato `evidence context builder`

Comportamento:

- contexto enviado ao LLM deve ter evidencia real suficiente;
- nao pode ser apenas titulo/frontmatter;
- deve preservar `chunk_id` e `source_path`;
- deve respeitar budget.

Entrada:

- `question`;
- `claims`;
- `hits`;
- `note_lookup`;
- budget.

Saida:

```python
list[str]
```

Formato proposto:

```text
[1]
source_path: ...
chunk_id: ...
claim_extrativo: ...
trecho:
...
```

Teste RED sugerido:

```python
def test_answer_provider_context_includes_clean_chunk_text_not_only_frontmatter(...):
    ...

def test_answer_provider_context_respects_total_budget(...):
    ...
```

Patch minimo:

- criar `build_answer_contexts(...)` em `corpus/ask.py` ou modulo novo `corpus/context.py`;
- trocar chamada atual.

Anti-regressao adversarial:

- chunk com frontmatter enorme nao pode consumir todo budget;
- chunk sem texto util deve cair para claim/source, nao quebrar.

### Slice 4 - Contrato `hard grounded prompt`

Comportamento:

- LLM recebe regra explicita: "nao fale nada fora dos contextos";
- sentinela `NAO_ENCONTRADO` vira contrato;
- prompt deve ser testavel por unidade.

Teste RED sugerido:

```python
def test_answer_provider_prompt_forbids_external_knowledge_and_examples(...):
    ...
```

Patch minimo:

- extrair prompt system para constante `GROUNDED_SYSTEM_PROMPT`;
- manter user prompt separado;
- incluir sentinela literal.

Anti-regressao adversarial:

- prompt nao deve conter instrucao contraditoria tipo "seja criativo";
- prompt nao deve pedir exemplos se contexto nao traz exemplos.

### Slice 5 - Contrato `generated answer validator`

Comportamento:

- resposta do LLM passa por validator antes de substituir answer extrativa;
- validator pode aceitar, converter para `no_answer`, ou fallback extrativo.

API proposta:

```python
class GeneratedAnswerValidation(BaseModel):
    action: Literal["accept", "no_answer", "fallback_extractive"]
    reason: str | None = None
    limitations: list[str] = []

def validate_generated_answer(
    question: str,
    answer: str,
    contexts: list[str],
    claims: list[AnswerClaim],
) -> GeneratedAnswerValidation:
    ...
```

Regras V1:

- `answer.strip().startswith("NAO_ENCONTRADO")` -> `no_answer`;
- resposta contem "nao consegui recuperar" e tambem lista generica -> `no_answer`;
- numero em answer ausente em contexts -> `fallback_extractive`;
- anchor capitalizado forte ausente em contexts -> `fallback_extractive`;
- sobreposicao lexical minima com claims baixa -> `fallback_extractive`.

Teste RED sugerido:

```python
def test_generated_answer_validator_rejects_unsupported_numbers(...):
    ...

def test_generated_answer_validator_turns_sentinel_into_no_answer(...):
    ...

def test_answer_corpus_falls_back_when_generated_answer_is_unsupported(...):
    ...
```

Anti-regressao adversarial:

- resposta fiel curta nao pode ser rejeitada por ser curta;
- sinonimos simples nao devem quebrar quando claims ainda cobrem anchors.

### Slice 6 - Contrato `short anchor rerank`

Comportamento:

- se pergunta contem entidade composta com token curto (`Disco D`, `Drive C`, `IPv4`, `P3a`);
- e titulo/source_path/chunk contem a entidade completa;
- esse hit recebe boost;
- documentos com entidade parecida mas anchor diferente nao devem passar na frente.

Teste RED sugerido:

```python
def test_hybrid_rerank_prefers_exact_short_anchor_in_title(...):
    ...
```

Fixture minima:

- nota A: `Estrutura Disco C`;
- nota B: `Estrutura Disco D`;
- pergunta: `O que e Estrutura Disco D?`;
- esperado: primeiro hit/note B.

Patch minimo:

- função pequena de `anchor_boost(question, hit, note)`;
- aplicar depois de FTS/vector fusion;
- nao trocar algoritmo inteiro.

Anti-regressao adversarial:

- pergunta ampla `estrutura de disco` nao deve favorecer letra aleatoria;
- boost so vale quando token curto esta adjacente a termo forte ou aparece em titulo/path.

### Slice 7 - Contrato `ask timings`

Comportamento:

- `--debug` deve mostrar tempos por etapa;
- sem `--debug`, payload normal continua limpo;
- tempos nao precisam ser perfeitos, mas devem orientar gargalo.

Campos propostos:

```json
{
  "timings": {
    "retrieval_ms": 0,
    "claim_build_ms": 0,
    "context_build_ms": 0,
    "provider_ms": 0,
    "validation_ms": 0,
    "total_ms": 0
  }
}
```

Teste RED sugerido:

```python
def test_ask_debug_includes_stage_timings(...):
    ...
```

Anti-regressao adversarial:

- timings nao devem vazar prompt completo, API key ou path sensivel alem do que debug ja mostra.

## Metricas de sucesso

Baseline observado:

| Caso | Resultado atual |
| --- | --- |
| `provider list-models` | ok, 2163 ms |
| `provider test-answer` | error falso, 13064 ms |
| `Estrutura Disco D` lexical | answer, 12647 ms, alucinacao parcial |
| `Estrutura Disco D` hybrid | answer, 17910 ms, alucinacao forte |
| `Perguntas de pesquisa do TCC` hybrid | answer ruim, 20307 ms |
| pergunta inexistente | no_answer, 4479 ms |

Meta pos-implementacao:

| Caso | Meta |
| --- | --- |
| `provider test-answer` com Ollama local | `ok` se content valido |
| `fake-hash` em Ask hybrid | erro controlado sem traceback |
| resposta com numero nao citado | fallback extrativo ou no_answer |
| resposta `NAO_ENCONTRADO` | status `no_answer` |
| pergunta inexistente | continua `no_answer`, sem chamar LLM |
| `Estrutura Disco D` | hit D antes de C |
| debug | mostra retrieval/provider/validation ms |

## Validacao obrigatoria por PR

Backend:

```powershell
cd D:\Dev\Repos\Own\tcc-free-plaud\pipeline
uvx ruff check src tests --output-format=json > ..\coverage\ruff.json
uv run pytest --basetemp .pytest-tmp-rag-quality -q --cov=src --cov-report=json:../coverage/coverage.json --cov-report=xml:../coverage/coverage.xml --cov-report=term-missing
uvx pip-audit --path .venv
```

Repo:

```powershell
cd D:\Dev\Repos\Own\tcc-free-plaud
qg-chk
qg-doc
git diff --check
git status --short --branch
```

UI quando tocar front:

```powershell
cd D:\Dev\Repos\Own\tcc-free-plaud\UI
npm.cmd test
npm.cmd run lint
npm.cmd run build
```

## Riscos

- Prompt hard pode reduzir respostas uteis demais e aumentar `no_answer`.
- Pos-validador lexical pode rejeitar sinonimos bons.
- Modelo pequeno local pode seguir mal instrucoes; por isso precisa fallback extrativo.
- Contexto maior aumenta latencia.
- Anchor curto pode causar overfitting em letras soltas se nao for condicionado a frase/titulo.

## Decisoes que nao devem ser tomadas no chute

- Trocar formato de resposta para JSON obrigatorio.
- Mudar default global de `answer_provider`.
- Fazer rebuild automatico do corpus ao trocar embedding.
- Instalar ou baixar modelo automaticamente.
- Usar vault real em teste automatizado.

## Entrega esperada

Cada slice deve virar PR proprio:

- branch `codex/rag-quality-N-nome-curto`;
- teste RED primeiro quando viavel;
- patch minimo;
- validacao local;
- PR com babysit ate ficar verde;
- merge so com required checks verdes.
