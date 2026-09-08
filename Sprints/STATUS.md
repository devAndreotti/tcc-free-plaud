# Status das Sprints

## Panorama

Estado atual do projeto:

- backend totalmente implementado (Sprints 00 a 07 + camada de RRF / AutoRAG)
- integracao de UI desktop e bridge concluidas (Sprints 08.1 e 08.2 operacionais via PyWebView + React 19)
- fase atual: fechamento experimental e consolidacao da monografia do TCC

## Tabela resumida

| Sprint | Status | Foco | Observacao |
| --- | --- | --- | --- |
| 00 | concluida | scaffold e ambiente | schemas e arquitetura base |
| 01 | concluida | base do backend, CLI e estrutura inicial | Typer, Pydantic, uv e Pytest |
| 02 | concluida | ingestao textual e rastreabilidade | pipelines multimodais e extratores |
| 03 | concluida | nota canonica e persistencia local | geracao e sanitizacao de Markdown |
| 04.1 | concluida | chunking com offsets e lineage | spans exatos para citacao sem alucinacao |
| 04.2 | concluida | persistencia baseline em SQLite | SQLite FTS5 (BM25) e metadados |
| 05 | concluida | ask estruturado com citacao e no_answer | baseline lexical operacional |
| 06.1 | concluida | embeddings e indexacao vetorial local | ChromaDB local funcional |
| 06.2 | concluida | ask semantico e estrategia de recuperacao | busca vetorial e comparacao lexical |
| 07 | concluida | benchmark reproduzivel | datasets, metricas (MRR, Recall@k) e runners |
| 08.1 | concluida | contratos e camada de aplicacao para UI | schemas de bridge e adapters de servico |
| 08.2 | concluida | integracao backend frontend | React 19 + PyWebView + Textual TUI |

## Ponto de parada real

O projeto concluiu o ciclo de implementacao completo e calibrou a busca hibrida RRF:

- Experimentos 01 a 14: baseline lexical vs vetorial, span pruning e avaliacao de corpus.
- Experimento 15 (docs/experimentos/15_calibracao_rrf_tcc.md): calibracao de fusao hibrida RRF (k=60).
- Suite E2E Playwright e Textual TUI validados.

## Proximo passo

1. Fechamento das secoes de escrita no TCC (Objetivos, Introducao, Metodologia e Resultados).
2. Manter testes e Quality Gate estaveis.
