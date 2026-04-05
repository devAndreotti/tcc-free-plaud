# Sprint 03 - Nota canônica e persistência local

**Autor:** Codex  
**Data:** 2026-04-05

## Resumo

Esta sprint prepara o backend para as próximas etapas de chunking com offsets, persistência em SQLite e RAG com citação, sem antecipar essas implementações. O foco aqui é transformar a nota gerada atualmente em um artefato canônico, reproduzível e persistível localmente.

Hoje o projeto já consegue:

- ingerir arquivos `.txt`, `.md` e `.pdf`
- extrair `raw_text`
- gerar uma `Note`
- renderizar `structured_markdown`
- exibir a nota no terminal via CLI

O que ainda falta é a camada que torna essa nota confiável como base do pipeline:

- identidade estável da nota
- separação entre texto bruto e texto canônico
- persistência local em disco
- manifesto mínimo de rastreabilidade

## Objetivo

Sair de um fluxo de preview:

`arquivo -> Note -> print no terminal`

para um fluxo canônico:

`arquivo -> ingestão -> Note canônica -> persistência local -> manifesto mínimo`

## Por que esta sprint existe

As sprints seguintes dependem de uma nota mais estável do que a atual:

- a Sprint 04.1 vai precisar de `normalized_text` e identidade estável para offsets e lineage
- a Sprint 04.2 vai precisar de uma representação persistível que migre com pouco atrito para SQLite
- a Sprint 05 vai precisar de uma cadeia auditável entre nota, chunk e evidência

Sem esta camada intermediária, o projeto corre o risco de implementar retrieval, persistência e citação em cima de um artefato ainda frágil e muito dependente de heurísticas simples.

## Escopo desta sprint

### Entram nesta sprint

- revisão do schema da nota
- identidade estável da nota
- normalização textual mínima
- melhoria do resumo inicial
- persistência local da nota
- manifesto mínimo da nota
- CLI para salvar nota em disco
- testes automatizados cobrindo esse fluxo

### Não entram nesta sprint

- `char_start` e `char_end`
- `chunk_id` avançado com lineage
- chunking com offsets
- ChromaDB
- SQLite real
- `ask` com citação
- `no_answer`
- benchmark experimental completo

## Estado atual do código

O backend atual já tem as bases das sprints anteriores:

- ingestão em `pipeline/src/free_plaud/ingest/`
- estruturação de nota em `pipeline/src/free_plaud/notes/`
- CLI principal em `pipeline/src/free_plaud/cli.py`
- testes em `pipeline/tests/`

Pontos que justificam esta sprint:

- `note_id` atual ainda é frágil para nomes com acentos, espaços sobrando e casos de slug ruim
- `summary` atual pode capturar headings em vez de um parágrafo real
- a nota hoje é mais um artefato temporário de terminal do que uma unidade persistida do pipeline
- ainda não existe distinção clara entre `raw_text`, `normalized_text` e artefato salvo

## Entregáveis

### 1. Schema de nota reforçado

A `Note` deve continuar simples, mas precisa carregar os campos necessários para funcionar como unidade canônica local.

Campos recomendados:

- `note_id`
- `note_version`
- `source_type`
- `source_path`
- `source_name`
- `title`
- `summary`
- `topics`
- `tasks`
- `tags`
- `raw_text`
- `normalized_text`
- `structured_markdown`
- `content_hash`
- `created_at`
- `provider`
- `model`

### 2. `note_id` estável e limpo

O identificador da nota deve:

- derivar do nome base do arquivo
- remover acentos
- trocar separadores por `-`
- colapsar sequências repetidas de separadores
- remover `-` no início e no fim
- manter previsibilidade entre execuções

O objetivo não é criar um ID global perfeito ainda, e sim um slug estável o bastante para persistência local e futura rastreabilidade.

### 3. `normalized_text`

Deve existir uma etapa explícita de normalização textual com regras mínimas e determinísticas, por exemplo:

- padronizar quebras de linha
- colapsar espaços redundantes
- remover ruído simples de borda
- preservar o conteúdo sem reescrever semanticamente o texto

Esta etapa existe para preparar o terreno para offsets e chunking reprodutível nas sprints seguintes.

### 4. Resumo inicial melhorado

O resumo ainda será heurístico e sem IA, mas deve ser menos frágil do que hoje.

Regras sugeridas:

- ignorar linhas vazias
- ignorar headings Markdown na escolha do resumo
- ignorar linhas de tabela como resumo
- ignorar bullets isolados como primeira opção
- selecionar o primeiro parágrafo textual útil

### 5. Persistência local da nota

Deve existir um comando para salvar a nota em disco, por exemplo:

```powershell
uv run free-plaud notes save "C:\caminho\arquivo.md"
```

Saída esperada:

- um arquivo Markdown em `data/corpus/notes/`
- um manifesto associado com metadados mínimos

Formato sugerido:

- `data/corpus/notes/<note_id>.md`
- `data/corpus/notes/<note_id>.meta.json`

### 6. Manifesto mínimo da nota

O manifesto não substitui o banco futuro. Ele serve como persistência operacional mínima e preparação conceitual para SQLite.

Campos mínimos sugeridos:

- `note_id`
- `note_version`
- `source_path`
- `source_type`
- `source_name`
- `content_hash`
- `structured_hash`
- `created_at`

## Critérios de aceite

- o comando `notes save` salva a nota em disco
- o arquivo salvo tem nome estável e reproduzível
- o `summary` não usa heading como resumo quando houver parágrafo melhor disponível
- `raw_text`, `normalized_text` e `structured_markdown` têm papéis separados
- reprocessar o mesmo arquivo gera o mesmo `note_id`
- a sprint continua sem depender de UI, SQLite e vector store real

## Backlog em ordem Akita

### Etapa 1 - Escrever testes antes do código

Criar ou expandir testes para cobrir:

- geração de `note_id` com acentos e espaços sobrando
- comportamento do `summary` em Markdown com headings, tabelas e listas
- criação de `normalized_text`
- persistência da nota em disco
- conteúdo do manifesto
- idempotência básica de `notes save`

### Etapa 2 - Fortalecer identidade da nota

Trabalhar em `notes/metadata.py` para:

- gerar slug limpo
- normalizar casos com acento
- evitar hífen sobrando
- manter comportamento determinístico

### Etapa 3 - Introduzir normalização textual

Criar um módulo dedicado, por exemplo `notes/normalizer.py`, para:

- receber `raw_text`
- produzir `normalized_text`
- manter regras pequenas e explícitas

### Etapa 4 - Melhorar a estruturação mínima

Refinar `notes/structurer.py` para:

- usar `normalized_text`
- gerar `summary` mais útil
- preencher `source_name`
- preencher `content_hash`
- inicializar `note_version`

### Etapa 5 - Criar persistência local

Adicionar um writer local, por exemplo em `notes/repository.py` ou `notes/storage.py`, responsável por:

- salvar o Markdown
- salvar o manifesto
- retornar os caminhos gerados

### Etapa 6 - Expor o fluxo por CLI

Expandir `notes/cli.py` com um comando como `save` para:

- construir a nota
- persisti-la em disco
- exibir o caminho final dos artefatos

### Etapa 7 - Validar com a suíte completa

Executar:

```powershell
uv run pytest
```

e testar manualmente:

```powershell
uv run free-plaud notes save "C:\caminho\arquivo.md"
```

## Arquivos que provavelmente entrarão

- `pipeline/src/free_plaud/notes/schemas.py`
- `pipeline/src/free_plaud/notes/metadata.py`
- `pipeline/src/free_plaud/notes/structurer.py`
- `pipeline/src/free_plaud/notes/markdown.py`
- `pipeline/src/free_plaud/notes/cli.py`
- `pipeline/src/free_plaud/notes/normalizer.py`
- `pipeline/src/free_plaud/notes/repository.py`
- `pipeline/tests/test_notes.py`

## Limites para não colidir com as próximas sprints

### Relação com a Sprint 04.1

Esta sprint pode preparar `normalized_text`, mas não deve implementar:

- offsets absolutos
- `char_start`
- `char_end`
- `section_path`
- `chunk_id` com lineage

### Relação com a Sprint 04.2

Esta sprint pode criar manifesto local, mas não deve implementar:

- schema SQLite real
- tabelas `notes`, `chunks`, `processing_logs` e `benchmark_runs`
- camada persistente relacional

### Relação com a Sprint 05

Esta sprint pode fortalecer o artefato base, mas não deve implementar:

- `AskResponse`
- política de `no_answer`
- resposta com citação
- validação de grounding

## Definition of Done

Esta sprint estará pronta quando:

- a nota deixar de ser apenas saída de terminal
- existir um artefato Markdown persistido localmente
- existir um manifesto mínimo coerente
- a estrutura da nota estiver mais estável e previsível
- o projeto ficar preparado para chunking com offsets e persistência futura sem retrabalho grande

## Nome recomendado para o commit principal

```text
feat(notes): add canonical note persistence flow
```
