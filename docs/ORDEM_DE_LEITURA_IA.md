# Ordem de Leitura para IA

## Objetivo deste arquivo

Este arquivo organiza a ordem minima de leitura recomendada para IA e agentes de codigo, reduzindo confusao entre documentacao canonica, plano operacional e material de apoio.

## Regra principal

A IA deve ler apenas o necessario para a tarefa atual.

Por padrao, nao precisa ler `docs/tcc/`.

`docs/tcc/` deve ser consultado apenas quando a tarefa envolver:

- escopo academico
- pergunta de pesquisa
- texto do TCC
- contribuicoes cientificas

## Leitura minima para backend

Ler nesta ordem:

1. `AGENTS.md`
2. `docs/arquitetura/Arquitetura_Backend.md`
3. pasta relevante em `Sprints/`

Ler `docs/plano_execucao/PLANO_BACKEND_PESSOAL.md` apenas quando:

- a tarefa atravessar varias sprints
- houver duvida de ordem entre entregas
- for necessario lembrar a visao macro do backend

Ler `docs/plano_execucao/CONTRATOS_FRONT_BACK.md` apenas quando a tarefa tocar integracao com a interface.

## Leitura minima para frontend

Ler nesta ordem:

1. `AGENTS.md`
2. `docs/arquitetura/Arquitetura_Frontend.md`
3. `docs/plano_execucao/CONTRATOS_FRONT_BACK.md`
4. `docs/plano_execucao/HANDOFF_FRONTEND_JOAO.md`
5. pasta relevante em `Sprints/`, se houver material especifico da tarefa

## Quando ler arquitetura geral

Ler `docs/arquitetura/Arquitetura.md` apenas quando:

- a tarefa afetar backend e frontend ao mesmo tempo
- houver duvida de fronteira entre camadas
- surgir decisao estrutural nova

## Quando ler planejamento

Ler `docs/planejamento/Plano_de_Arranque.md` apenas quando:

- a tarefa envolver ordem de execucao
- houver duvida sobre prioridades
- for necessario validar se algo entrou cedo demais no cronograma

`docs/planejamento/Metodologia_Akita_Git.md` so precisa ser lido quando a tarefa envolver branch, entrega, merge ou politica de commit.

## Como usar a pasta `Sprints`

Depois da leitura minima, a IA deve consultar somente a sprint relevante em `Sprints/`.

Exemplo:

- trabalho de scaffold inicial -> ler `Sprints/Sprint 01/`
- trabalho de ingestao -> ler `Sprints/Sprint 02/`
- trabalho de chunking -> ler `Sprints/Sprint 04.1/`
- trabalho de schema SQLite -> ler `Sprints/Sprint 04.2/`
- trabalho de RAG com citacao -> ler `Sprints/Sprint 05/`

## Material de apoio

Arquivos em `docs/referencias_ia/` servem como apoio tecnico, pesquisa ou guias de implementacao.

Eles nao substituem a arquitetura oficial nem o plano operacional.

## Regra pratica

Se houver conflito entre um guia de apoio e a arquitetura oficial:

1. seguir `docs/arquitetura/`
2. seguir `docs/plano_execucao/`
3. atualizar a documentacao oficial se a decisao mudar
