# AGENTS.md - Escólio

## Instruction File Status

`AGENTS.md` e o arquivo canonico de instrucao deste repositorio.

Se existir sobreposicao com outros arquivos de instrucao locais, seguir este arquivo como fonte principal.

## Overview

`Escólio` é um projeto de TCC focado em um pipeline de IA para captura multimodal, estruturação automatizada em Markdown e recuperação semântica de conhecimento pessoal em português brasileiro.

O produto final desejado é um app desktop local-first, mas a prioridade do projeto é a validação experimental do pipeline e do módulo de benchmark.

## Current Phase

Fase atual: fundação documental e arquitetura.

Antes de escrever código, ler:

1. `docs/ORDEM_DE_LEITURA_IA.md`

Para trabalho de backend, ler tambem:

1. `docs/arquitetura/Arquitetura_Backend.md`
2. pasta relevante em `Sprints/`

Opcional:

1. `docs/plano_execucao/PLANO_BACKEND_PESSOAL.md` para visao macro
2. `docs/plano_execucao/CONTRATOS_FRONT_BACK.md` se a tarefa tocar integracao com UI

Para trabalho de alinhamento com frontend, ler tambem:

1. `docs/arquitetura/Arquitetura_Frontend.md`
2. `docs/plano_execucao/HANDOFF_FRONTEND_JOAO.md`
3. `docs/plano_execucao/CONTRATOS_FRONT_BACK.md`
4. pasta relevante em `Sprints/`, se houver material especifico

Observacao:

- `docs/referencias_ia/` contem guias e pesquisas de apoio
- por padrao, a IA nao precisa ler `docs/tcc/`
- a fonte de verdade para implementacao continua sendo `docs/arquitetura/`, `docs/planejamento/` e `docs/plano_execucao/`

## Non-Negotiable Rules

1. Não começar pela casca desktop.
2. Não abrir a implementação por Rust/Tauri antes do core experimental.
3. Testes e benchmark antes de expansão de features.
4. Documentação arquitetural deve ser atualizada junto com decisões relevantes.
5. `main` deve ficar estável.
6. Um commit por decisão relevante, não por volume de alteração.
7. Branches curtas e focadas.

## Architecture Strategy

### Phase 1 - Backend and benchmark first

- Python 3.12
- uv
- Typer
- Pydantic
- SQLite
- ChromaDB
- Pytest

Objetivo: provar ingestão, estruturação, indexação e RAG com citação.

### Phase 2 - Local UI

- React
- TypeScript
- Vite
- Tailwind
- Zustand

Objetivo: operar fila, chat, configurações e benchmark de forma visual.

### Phase 3 - Desktop shell

- Tauri

Objetivo: empacotar a interface e integrar monitoramento local com menor custo operacional.

## Planned Repository Structure

```text
Escólio/
├── .agents/
│   ├── inspirations/
│   ├── skills/
│   └── workflows/
├── data/
│   ├── corpus/
│   ├── datasets/
│   └── results/
├── docs/
├── pipeline/
├── src/
├── src-tauri/
├── AGENTS.md
└── README.md
```

## Git and Delivery Rules

### Branching

- `main` = estado estável
- `feat/pipeline-core`
- `feat/rag-benchmark`
- `feat/audio-ingest`
- `feat/desktop-shell`

### Tags

- `v0-core-rag`
- `v0-benchmark`
- `v0-audio`
- `v0-ui`

### Commit discipline

- um commit por decisão relevante
- commits pequenos e legíveis
- sem acumular alterações grandes e desconexas

## What To Avoid

- acoplar provedor de IA diretamente em toda a base
- espalhar lógica de benchmark por múltiplos módulos
- misturar regra de negócio do pipeline com detalhes de UI
- gastar tempo cedo demais com animação, polimento visual ou instaladores
- criar features fora do escopo do TCC antes do benchmark mínimo

## Preferred Documentation Pattern

Quando surgir decisão estrutural nova:

1. atualizar `docs/arquitetura/Arquitetura.md` se afetar o desenho geral
2. atualizar `docs/arquitetura/Arquitetura_Backend.md` ou `docs/arquitetura/Arquitetura_Frontend.md` se afetar detalhe de camada
3. atualizar `docs/tcc/texto/TCC.md` se alterar escopo, pergunta de pesquisa ou contribuição
4. atualizar `README.md` se for algo relevante para entendimento externo do projeto

<!-- ai-memory:start -->
## Long-term memory (ai-memory)

This project uses [ai-memory](https://github.com/akitaonrails/ai-memory)
for cross-session continuity. **Lifecycle hooks already capture every
prompt + tool call automatically.** You never need to manually write
routine notes; the SessionStart hook auto-fetches pending handoffs, and
on session end ai-memory writes a session-summary page and a handoff.
LLM consolidation (compiling observations into topical wiki pages) runs
on PreCompact, on demand via `memory_consolidate`, and at session end
only when the server sets `AI_MEMORY_CONSOLIDATE_ON_SESSION_END`. Only
write a durable wiki page when the user explicitly asks to remember or
annotate something permanently.

### When to reach for each tool

The user can express any of the intents below in plain English —
match the intent to the tool. They do not need to name the tool.

| User says / situation | Tool |
|---|---|
| "have we discussed X?" / "search memory for Y" / before proposing architecture | `memory_query` |
| "what's been going on" / "show recent activity" (light) | `memory_recent` |
| "is ai-memory healthy?" / "how big is the wiki?" | `memory_status` |
| "give me the stats" / structured snapshot for the agent to consume | `memory_briefing` |
| "catch me up" / "I've been away" / "what's important right now?" / open-ended exploration | `memory_explore` |
| "where did we leave off?" — and you see a `📥 ai-memory: pending handoff` block in your context | already done — answer from that block; do NOT re-call `memory_handoff_accept` |
| "where did we leave off?" — and no such block is visible | `memory_handoff_accept` (rare; the SessionStart hook usually got there first) |
| "save context for the next session" / wrapping up | `memory_handoff_begin` (single-use handoff; terse summary; put detail in `open_questions` + `next_steps` bullets) |
| "consolidate this session" / "compile what we learned" (also runs on PreCompact; at session end only if `AI_MEMORY_CONSOLIDATE_ON_SESSION_END` is set) | `memory_consolidate` |
| "remember this permanently" / "save a note" / "add an annotation" / durable project knowledge | `memory_write_page` (write a wiki page; do **not** use handoff for permanent notes) |
| "audit the wiki" / "find contradictions" / "what rules should we add?" | `memory_lint` |
| "prune old pages" / "memory cleanup" | `memory_forget_sweep` |

`memory_explore` is the right default for the "I want to know what's
going on" use case — it returns a prose digest whose verbosity
scales automatically to how long it's been since the last activity
(< 1 h → one line; > 30 days → full catchup).

### When you write a project rule, write it here

If you're about to write a durable project rule ("always X", "never
Y", "all PRs must …"), this rules file (CLAUDE.md for Claude Code;
AGENTS.md for Codex / OpenCode / Cursor / Gemini CLI; whichever
convention your agent uses) is where it belongs. ai-memory's lint
pass surfaces the same hint automatically when a `kind: rule` page
lands in `_rules/`.

### Refreshing this snippet

This block is maintained by ai-memory. Two ways to refresh it with
the latest binary's recommended copy:

- **From the agent** (no terminal needed): ask "refresh the ai-memory
  routing in this project" — the agent calls
  `memory_install_self_routing`, picks the right filename for itself
  (Claude Code → `CLAUDE.md`; Codex / OpenCode / Cursor / Gemini →
  `AGENTS.md`), and uses its Write / Edit tool to land the block.
- **From the CLI**: `ai-memory install-instructions` (defaults to
  `CLAUDE.md`; pass `--target AGENTS.md` for non-Claude agents).

Both are idempotent: re-runs replace the block bracketed by
`<!-- ai-memory:start -->` / `<!-- ai-memory:end -->` markers
without disturbing the rest of the file.
<!-- ai-memory:end -->
