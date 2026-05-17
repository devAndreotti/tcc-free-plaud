# Registro de Sprints

## Objetivo

Esta pasta registra as sprints do projeto.

Ela cumpre dois papeis:

- preservar o historico do que foi planejado e executado
- servir como referencia operacional para IA e para o desenvolvimento

## Regra atual

- uma pasta por sprint
- a sprint pode conter documento oficial e artefatos auxiliares
- a sprint nao deve ser tratada como dumping ground para novos arquivos soltos

## Como ler

1. consulte `STATUS.md` para ver o panorama
2. entre apenas na sprint relevante para a tarefa atual
3. trate a sprint como contexto operacional, nao como arquitetura oficial

## Relacao com outras pastas

- `../docs/arquitetura/` = fonte de verdade tecnica
- `../docs/planejamento/` = ordem macro e prioridade
- `../docs/plano_execucao/` = guia operacional consolidado
- `Sprints/` = registro por etapa de execucao

## Observacoes

As sprints mais antigas ainda carregam nomes e artefatos gerados em fases anteriores do projeto.

Isso sera normalizado em um lote posterior, mas por enquanto o objetivo e:

- manter o historico
- deixar claro o que esta concluido
- reduzir ambiguidade sobre o estado atual

## Convencao desejada daqui para frente

Para novas sprints ou reorganizacao futura:

- `README.md` da sprint = documento oficial da sprint
- `artifacts/` = arquivos auxiliares como `.py`, `.sql`, `.mmd`, `.toml`

Enquanto essa normalizacao nao acontece em todas as pastas, usar `STATUS.md` como referencia principal.
