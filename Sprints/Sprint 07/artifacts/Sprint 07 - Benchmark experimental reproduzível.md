# Sprint 07 - Benchmark experimental reproduzível

**Autor:** Codex  
**Data:** 2026-04-13

## Resumo

Esta sprint transforma o backend em instrumento experimental de verdade.

Até aqui o projeto já deve ser capaz de:

- ingerir documento
- estruturar nota
- gerar chunks
- persistir metadados
- indexar semanticamente
- responder com citação

Agora o foco é provar, medir e comparar.

## Objetivo

Criar um runner de benchmark reproduzível para comparar estratégias do pipeline e gerar resultados defensáveis no TCC.

## Por que esta sprint existe

Sem benchmark:

- o projeto funciona como produto/protótipo
- mas fica fraco como artefato científico

O benchmark é o que permite responder perguntas como:

- chunking melhorou ou piorou a recuperação?
- retrieval vetorial ficou melhor que lexical?
- qual configuração tem melhor `Recall@k`?
- qual custo de latência cada opção traz?

## Escopo desta sprint

### Entram nesta sprint

- schema de dataset de benchmark
- runner reproduzível
- métricas como `MRR`, `Recall@k` e latência
- persistência das execuções em SQLite
- exportação para CSV e JSON

### Não entram nesta sprint

- dashboard visual final
- análise estatística avançada
- integração forte com frontend

## Entregáveis

### 1. Dataset de benchmark

Definir um formato claro para exemplos de avaliação.

Campos mínimos sugeridos:

- `sample_id`
- `question`
- `expected_note_id`
- `expected_chunk_id`
- `expected_terms`

### 2. Runner reproduzível

O runner deve:

- carregar dataset
- executar retrieval/ask por configuração
- medir métricas
- persistir resultados

### 3. Métricas mínimas

- `MRR`
- `Recall@3`
- `Recall@5`
- `Recall@10`
- `latency_ms`

### 4. Persistência em SQLite

Usar as tabelas já preparadas para:

- `benchmark_runs`
- `benchmark_queries`

### 5. Exportação

Permitir exportar resultados em:

- `CSV`
- `JSON`

## Critérios de aceite

- um conjunto de benchmark pode ser executado fim a fim
- os resultados podem ser reproduzidos
- as execuções ficam registradas
- as métricas podem ser exportadas

## Backlog em ordem Akita

### Etapa 1 - Escrever testes antes do código

Cobrir:

- schema do dataset
- cálculo das métricas
- persistência das execuções
- exportação

### Etapa 2 - Definir dataset e parser

Trabalhar em:

- `pipeline/src/free_plaud/benchmark/datasets.py`

### Etapa 3 - Implementar métricas faltantes

Trabalhar em:

- `pipeline/src/free_plaud/benchmark/metrics.py`

### Etapa 4 - Implementar runner

Trabalhar em:

- `pipeline/src/free_plaud/benchmark/runners.py`

### Etapa 5 - Persistir e exportar

Trabalhar em:

- `pipeline/src/free_plaud/storage/sqlite.py`
- `pipeline/src/free_plaud/benchmark/reports.py`

### Etapa 6 - Expor via CLI

Exemplos:

```powershell
uv run free-plaud benchmark run --dataset "C:\...\dataset.json"
uv run free-plaud benchmark export --run-id "run-001" --format csv
```

## Arquivos que provavelmente entrarão

- `pipeline/src/free_plaud/benchmark/datasets.py`
- `pipeline/src/free_plaud/benchmark/metrics.py`
- `pipeline/src/free_plaud/benchmark/runners.py`
- `pipeline/src/free_plaud/benchmark/reports.py`
- `pipeline/src/free_plaud/benchmark/cli.py`
- `pipeline/tests/test_benchmark.py`

## Limites para não colidir com a Sprint 08

### Relação com a Sprint 08

Esta sprint entrega benchmark operacional, mas não deve:

- depender de UI
- criar dashboard como prioridade
- misturar análise experimental com bridge de frontend

## Definition of Done

Esta sprint estará pronta quando:

- existir um benchmark reproduzível
- as métricas puderem ser comparadas entre estratégias
- as execuções ficarem registradas em SQLite
- os resultados puderem ser exportados para análise e TCC

## Nome recomendado para o commit principal

```text
feat(benchmark): add reproducible experiment runner
```
