# Status das Sprints

## Panorama

Estado atual do projeto:

- backend implementado ate a Sprint 07
- Sprint 08.1 e 08.2 ainda nao iniciadas
- fase atual: calibracao experimental do retrieval antes da integracao com UI

## Tabela resumida

| Sprint | Status | Foco | Observacao |
| --- | --- | --- | --- |
| 00 | concluida | scaffold e ambiente | documentacao legada, ainda sem normalizacao |
| 01 | concluida | base do backend, CLI e estrutura inicial | pasta mistura documento e artefatos auxiliares |
| 02 | concluida | ingestao textual e rastreabilidade | pasta ainda precisa de normalizacao interna |
| 03 | concluida | nota canonica e persistencia local | marco claro do artefato da nota |
| 04.1 | concluida | chunking com offsets e lineage | retrieval preparado para citacao |
| 04.2 | concluida | persistencia baseline em SQLite | notas, chunks, logs e benchmark records |
| 05 | concluida | ask estruturado com citacao e no_answer | baseline lexical operacional |
| 06.1 | concluida | embeddings e indexacao vetorial local | ChromaDB local funcional |
| 06.2 | concluida | ask semantico e estrategia de recuperacao | `lexical` e `vector` comparaveis |
| 07 | concluida | benchmark reproduzivel | datasets, metricas, exportacao e comparacao |
| 08.1 | planejada | contratos e camada de aplicacao para UI | nao iniciada |
| 08.2 | planejada | integracao inicial backend frontend | nao iniciada |

## Ponto de parada real

O projeto parou formalmente depois da Sprint 07.

Depois disso, entrou em uma trilha experimental registrada em:

- `../docs/experimentos/01_lexical_vs_vector_suite_baseline.md`
- `../docs/experimentos/02_calibracao_retrieval_vetorial.md`
- `../docs/experimentos/03_embeddings_alternativos_suite_baseline.md`
- `../docs/experimentos/04_matriz_testes_manuais_tcc_demo.md`
- `../docs/experimentos/05_roteiro_demo_5_minutos.md`
- `../docs/experimentos/06_cola_demo_1_minuto.md`

## Proximo passo tecnico

Antes de qualquer prioridade de UI:

1. manter `800/120 + chroma-default` como baseline vetorial atual
2. abrir ciclo de busca hibrida ou reranking
3. comparar o novo ciclo contra `lexical` e contra o baseline vetorial atual

## Uso desta pasta

Se a pergunta for:

- "o que foi feito?" -> comecar por este arquivo
- "em qual sprint paramos?" -> resposta: Sprint 07, com fase experimental posterior
- "qual sprint devo ler agora?" -> ler apenas a sprint relevante para a tarefa atual
