# Handoff - Consistencia, reset e rebuild do corpus local

## Status

Criado em 2026-05-22.

Este plano corrige os riscos encontrados depois da validacao exaustiva do `corpus ask` multi-documento.

## Leitura obrigatoria antes de executar

1. `AGENTS.md`
2. `docs/ORDEM_DE_LEITURA_IA.md`
3. `docs/arquitetura/Arquitetura_Backend.md`
4. `docs/plano_execucao/HANDOFF_CORPUS_INDEX_E_ASK_MULTI_DOCUMENTO.md`
5. `docs/experimentos/12_ask_corpus_multi_documento.md`
6. `docs/experimentos/13_validacao_exaustiva_ask_corpus.md`
7. Este arquivo

Nao ler `docs/tcc/` salvo necessidade academica explicita.

## Skills obrigatorias

- `caveman:caveman` para comunicacao curta, conforme `AGENTS.md`
- `senior-second-pass` para revisar diagnostico, plano, diff e entrega
- `akita-way` para TDD, slices pequenas, commits limpos e gates antes de push
- `adversarial-delivery-auditor` antes de aceitar a feature como pronta

## Senior second pass do diagnostico

### Veredito

Blocked para considerar `corpus ask` pronto para demo em banco persistente real.

Approved with adjustments para a linha de correcao: status, filtro anti-stale, reset, rebuild e depois TUI.

### Findings

- [P1] O diagnostico "vector sozinho falha multi-fonte" estava incompleto. Parte do comportamento ruim vem de corpus misturado e Chroma stale, nao apenas de fraqueza semantica. Fix: medir e corrigir consistencia antes de recalibrar ranking.
- [P1] SQLite e Chroma podem divergir. Evidencia local em 2026-05-22: SQLite tinha `53` chunks, Chroma tinha `122` vetores; `102` vetores apontavam para `note_id` inexistente no SQLite. Fix: adicionar status/consistency check e filtrar hits por `chunk_id` persistido.
- [P1] Reindexar nota pode trocar `chunk_id` quando tamanho/overlap/texto muda, mas `upsert_chunks` nao remove vetores antigos. Fix: apagar vetores antigos da nota antes de upsert, ou reconstruir collection em rebuild.
- [P1] `corpus ask` hoje usa acervo unico global. Se o usuario indexa samples, validacoes e Obsidian juntos, a resposta pode usar todos. Isso e esperado pelo modelo atual, mas ruim para demo e para projetos separados. Fix imediato: `reset`/`rebuild`; fix futuro: `corpus_id`/namespace.
- [P2] Reset e destrutivo. Botao ou CLI sem preview pode apagar corpus por engano. Fix: `--dry-run` por padrao e exigir `--yes` para executar.
- [P2] TUI nao deve vir antes do contrato backend. Fix: CLI + testes primeiro; botao TUI so depois dos comandos verdes.

## Decisao tecnica

1. `hybrid` continua default para `corpus ask`.
2. `vector` continua strategy experimental, nao default de demo.
3. `corpus ask` deve consultar todo o corpus persistido, mas apenas chunks coerentes entre SQLite e Chroma.
4. Banco "sujo" deve ser operavel por CLI: status, reset, rebuild.
5. Reset nao deve apagar benchmark por padrao.
6. Botao TUI de limpar banco fica fora da primeira slice de backend.

## Fora de escopo nesta slice

- Frontend web
- Tauri
- LLM real
- OCR/imagem/audio
- `corpus_id`/multi-acervo persistente
- Limpeza Obsidian/Dataview/JS
- Recalibracao de ranking sem antes fechar consistencia
- Apagar `samples/` ou mexer no vault Obsidian

## Objetivo

Tornar o corpus local operacionalmente confiavel:

1. diagnosticar divergencia SQLite/Chroma;
2. impedir que hits vetoriais stale entrem em resposta;
3. permitir limpar corpus com seguranca;
4. permitir rebuild reproduzivel a partir de arquivo/pasta;
5. validar que respostas multi-documento usam apenas o corpus reconstruido.

## Modelo mental correto

### O que `corpus ask` deve fazer

Se um arquivo foi indexado no corpus ativo, seus chunks podem ser recuperados por `ask`.

Isso nao significa que todo arquivo indexado deve aparecer em toda resposta. Retrieval deve selecionar evidencias relevantes.

### O que `corpus ask` ainda nao faz

Ele nao separa projetos/acervos. Enquanto nao existir `corpus_id`, tudo que estiver no SQLite/Chroma da collection ativa faz parte do mesmo acervo.

### Quando reset e necessario

Reset e util quando:

- a demo precisa partir de corpus limpo;
- testes deixaram samples no banco;
- Chroma tem vetores sem nota/chunk correspondente;
- usuario quer reconstruir acervo a partir de uma pasta fonte.

## Slices de implementacao

## Slice 1 - Status e consistencia do corpus

### Comportamento esperado

Adicionar:

```powershell
uv run free-plaud corpus status
```

Saida JSON:

```json
{
  "sqlite_path": "...",
  "vector_store_dir": "...",
  "vector_collection_name": "free_plaud_chunks",
  "notes_count": 7,
  "sqlite_chunks_count": 53,
  "vector_chunks_count": 122,
  "stale_vector_chunks_count": 102,
  "missing_vector_chunks_count": 0,
  "orphan_vector_note_ids": ["..."],
  "status": "inconsistent"
}
```

### Regras

- `status=clean` se SQLite e Chroma estiverem coerentes.
- `status=inconsistent` se houver vetores sem `chunk_id` no SQLite.
- `status=sqlite_only` se SQLite tem chunks, mas Chroma esta vazio.
- `status=empty` se ambos vazios.
- Nao modificar nada no status.

### Arquivos provaveis

- `pipeline/src/free_plaud/corpus/models.py`
- `pipeline/src/free_plaud/corpus/service.py`
- `pipeline/src/free_plaud/corpus/cli.py`
- `pipeline/src/free_plaud/storage/vector.py`
- `pipeline/tests/test_corpus_status.py`
- `pipeline/tests/test_cli.py`

### Testes primeiro

```powershell
cd D:\Dev\Repos\Own\tcc-free-plaud\pipeline
uv run pytest tests\test_corpus_status.py -q
```

Casos:

| Caso | Esperado |
| --- | --- |
| SQLite e Chroma vazios | `status=empty` |
| Mesmos chunks em SQLite/Chroma | `status=clean` |
| Chroma com vetor sem SQLite | `status=inconsistent`, `stale_vector_chunks_count > 0` |
| SQLite com chunk sem Chroma | `missing_vector_chunks_count > 0` |
| CLI `corpus status` | JSON valido |

### Commit esperado

```text
feat: adicionar status de consistencia do corpus
```

## Slice 2 - Filtrar hits vetoriais stale no `corpus ask`

### Comportamento esperado

`corpus ask --strategy vector|hybrid` nao pode usar chunk que nao existe no SQLite.

Se Chroma retornar hit stale:

1. descartar o hit;
2. registrar limitação em resposta quando aplicavel;
3. manter `no_answer` se so restarem hits fracos ou nenhum hit.

### Regra importante

Filtro deve ocorrer antes de:

- `_summarize_corpus_sources`
- `_build_corpus_claims`
- citations
- grounding

### Arquivos provaveis

- `pipeline/src/free_plaud/corpus/ask.py`
- `pipeline/src/free_plaud/storage/sqlite.py`
- `pipeline/tests/test_corpus_ask.py`

### Testes primeiro

Criar cenário:

1. SQLite tem nota A.
2. Chroma tem nota A e nota stale B.
3. Pergunta recupera B com score alto.
4. Resposta nao pode citar B.

Comando:

```powershell
uv run pytest tests\test_corpus_ask.py -q
```

Critérios:

- nenhuma citation com `note_id` ausente no SQLite;
- nenhuma source path `None` causada por hit stale;
- pergunta que antes puxava lixo vira resposta correta ou `no_answer`.

### Commit esperado

```text
fix: ignorar vetores stale no ask do corpus
```

## Slice 3 - Reset seguro do corpus

### Comportamento esperado

Adicionar:

```powershell
uv run free-plaud corpus reset --dry-run
uv run free-plaud corpus reset --yes
```

`--dry-run` deve ser default implicito.

Saida JSON:

```json
{
  "dry_run": true,
  "would_delete_notes": 7,
  "would_delete_chunks": 53,
  "would_delete_vectors": 122,
  "deleted_notes": 0,
  "deleted_chunks": 0,
  "deleted_vectors": 0,
  "status": "preview"
}
```

Com `--yes`:

```json
{
  "dry_run": false,
  "deleted_notes": 7,
  "deleted_chunks": 53,
  "deleted_vectors": 122,
  "status": "reset"
}
```

### Regras de seguranca

- Sem `--yes`, nao apagar nada.
- Nao apagar `benchmark_runs` nem `benchmark_queries` por padrao.
- Nao apagar arquivos fonte.
- Nao apagar `samples/`.
- Nao apagar vault Obsidian.
- Resetar apenas tabelas `notes` e `chunks` e collection vetorial ativa.
- Se futuramente quiser apagar benchmark, criar flag explicita separada.

### Arquivos provaveis

- `pipeline/src/free_plaud/corpus/models.py`
- `pipeline/src/free_plaud/corpus/service.py`
- `pipeline/src/free_plaud/corpus/cli.py`
- `pipeline/src/free_plaud/storage/sqlite.py`
- `pipeline/src/free_plaud/storage/vector.py`
- `pipeline/tests/test_corpus_reset.py`
- `pipeline/tests/test_cli.py`

### Testes primeiro

```powershell
uv run pytest tests\test_corpus_reset.py tests\test_cli.py -q
```

Casos:

| Caso | Esperado |
| --- | --- |
| reset dry-run | contagens previstas, dados permanecem |
| reset `--yes` | `notes/chunks/vector_count = 0` |
| benchmark existente | permanece depois do reset |
| collection inexistente | comando nao quebra |
| reset duas vezes | idempotente |

### Commit esperado

```text
feat: adicionar reset seguro do corpus
```

## Slice 4 - Rebuild reproduzivel do corpus

### Comportamento esperado

Adicionar:

```powershell
uv run free-plaud corpus rebuild "D:\caminho\pasta" --recursive --yes
```

Fluxo:

1. status antes;
2. reset com `--yes`;
3. indexacao com `corpus index`;
4. status depois;
5. JSON unico com tudo.

Sem `--yes`, deve apenas simular:

```powershell
uv run free-plaud corpus rebuild "D:\caminho\pasta" --recursive --dry-run
```

### Regras

- `rebuild` deve reaproveitar `reset_corpus` e `index_corpus_path`.
- Se indexacao falhar parcialmente, reportar `status=partial`.
- Se reset falhar, nao iniciar indexacao.
- Rebuild nao deve aceitar path inexistente como sucesso.

### Testes primeiro

```powershell
uv run pytest tests\test_corpus_rebuild.py tests\test_corpus_service.py tests\test_cli.py -q
```

Casos:

| Caso | Esperado |
| --- | --- |
| rebuild dry-run | nao altera contagens |
| rebuild `--yes` com pasta valida | corpus limpo e reindexado |
| rebuild path inexistente | falha estruturada |
| rebuild com `.docx` e `.md` | `.docx` skipped, `.md` indexado |
| rebuild duas vezes | contagens estaveis |

### Commit esperado

```text
feat: reconstruir corpus local por cli
```

## Slice 5 - Experimento de consistencia e regressao

### Comportamento esperado

Criar novo experimento:

```text
docs/experimentos/14_consistencia_reset_rebuild_corpus.md
```

Deve registrar:

- estado sujo inicial observado;
- comandos `status`, `reset --dry-run`, `rebuild --yes`;
- pergunta multi-fonte antes/depois;
- contagens SQLite/Chroma antes/depois;
- conclusao tecnica.

### Validacao manual obrigatoria

Usar pasta temporaria ou data controlada. Nao usar o vault diretamente.

```powershell
cd D:\Dev\Repos\Own\tcc-free-plaud\pipeline
uv run free-plaud corpus status
uv run free-plaud corpus reset --dry-run
uv run free-plaud corpus rebuild "D:\Dev\Repos\Own\tcc-free-plaud\data\results\validation_distributed_corpus" --recursive --yes
uv run free-plaud corpus status
uv run free-plaud corpus ask --question "Qual message broker foi adotado, qual equipe ficou responsavel pelo runbook e qual padrao divide o pipeline em Bronze, Silver e Gold?" --strategy hybrid --top-k 6
uv run free-plaud corpus ask --question "Quais tecnologias o candidato domina para desenvolver apps mobile?" --strategy hybrid --top-k 6
```

Esperado depois do rebuild:

- `status=clean`;
- SQLite chunks = Chroma vectors;
- resposta distribuida cita apenas arquivos da pasta reconstruida;
- pergunta irrelevante retorna `no_answer`;
- nenhum source de `samples/` aparece quando rebuild usa apenas `validation_distributed_corpus`.

### Commit esperado

```text
docs: registrar consistencia e rebuild do corpus
```

## Slice 6 - Preparar botao TUI depois do backend

Executar somente depois das slices 1 a 5 estarem verdes.

### Comportamento esperado

Na TUI:

- mostrar contagem do corpus e status `clean/inconsistent/empty`;
- botao `Limpar corpus`;
- modal/confirmacao forte antes de apagar;
- botao `Rebuild` opcional, somente se path informado;
- mostrar resultado JSON/resumo.

### Fora da primeira implementacao

Nao criar botao antes de `corpus reset` e `corpus status` estarem testados por CLI.

### Commit esperado

```text
feat: adicionar controles de corpus na tui
```

## Gate final da feature

Antes de considerar pronta:

```powershell
cd D:\Dev\Repos\Own\tcc-free-plaud\pipeline
uv run pytest -q
uv run free-plaud --help
uv run free-plaud corpus --help
uv run free-plaud corpus status
uv run free-plaud corpus reset --dry-run
uv run free-plaud corpus rebuild "D:\Dev\Repos\Own\tcc-free-plaud\data\results\validation_distributed_corpus" --recursive --yes
uv run free-plaud corpus status
uv run free-plaud corpus ask --question "Qual message broker foi adotado, qual equipe ficou responsavel pelo runbook e qual padrao divide o pipeline em Bronze, Silver e Gold?" --strategy hybrid --top-k 6
uv run free-plaud corpus ask --question "Qual message broker foi adotado, qual equipe ficou responsavel pelo runbook e qual padrao divide o pipeline em Bronze, Silver e Gold?" --strategy vector --top-k 6
uv run free-plaud corpus ask --question "Quais tecnologias o candidato domina para desenvolver apps mobile?" --strategy hybrid --top-k 6
git diff --check
git status --short --branch
```

## Criterios de aceite

- `corpus status` detecta divergencia SQLite/Chroma.
- `corpus ask` nao cita chunk inexistente no SQLite.
- `corpus reset --dry-run` nao altera dados.
- `corpus reset --yes` limpa notas/chunks/vetores da collection ativa.
- `corpus rebuild --yes` deixa corpus limpo, indexado e coerente.
- Rebuild da pasta controlada nao puxa `samples/`.
- Pergunta multi-documento em `hybrid` cita fontes corretas.
- Pergunta irrelevante continua `no_answer`.
- Suite completa passa.
- Experimento 14 registra evidencia.

## Riscos e mitigacoes

| Risco | Impacto | Mitigacao |
| --- | --- | --- |
| Reset apagar dados inesperados | perda de corpus local | `--dry-run` default, `--yes` obrigatorio, nao apagar benchmark por padrao |
| Chroma continuar com vetores stale | resposta cita lixo | filtro por `chunk_id` SQLite e status inconsistente |
| Rebuild mascarar bug de indexacao | falso verde | testes unitarios + smoke CLI + status antes/depois |
| Usuario esperar acervos separados | resposta mistura projetos | documentar acervo unico; planejar `corpus_id` futuro |
| Botao TUI vir cedo demais | risco visual sobre backend instavel | backend CLI primeiro |

## Ordem recomendada

1. Implementar Slice 1.
2. Implementar Slice 2.
3. Implementar Slice 3.
4. Implementar Slice 4.
5. Rodar gates e registrar Slice 5.
6. Somente depois decidir Slice 6 na TUI.

## Nota sobre `vector`

`vector` nao precisa superar `hybrid` para o produto ser valido. Mas precisa ser honesto:

- se retornar evidencias suficientes, pode responder;
- se nao retornar multi-fonte suficiente, deve abster ou responder parcial com limitacao;
- nao pode usar vetor stale;
- nao deve ser default de demo enquanto `hybrid` for mais robusto.

O problema prioritario nao e "forcar vector a acertar tudo". O problema prioritario e garantir que qualquer strategy use apenas corpus coerente.
