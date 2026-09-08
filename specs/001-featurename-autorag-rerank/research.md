# Research: AutoRAG Rerank Calibration & Metrics

## Decisions & Findings

### Decision 1: Hybrid Fusion Strategy
- **Choice**: Reciprocal Rank Fusion (RRF) com constante `k` configurável (padrão `k=60`) e suporte a ponderação linear opcional.
- **Rationale**: RRF independe da calibração de escala entre scores de BM25 e similaridade por cosseno do ChromaDB, oferecendo maior estabilidade em coleções pequenas/médias.
- **Alternatives considered**: Normalização Min-Max dos scores (rejeitada por instabilidade com outliers).

### Decision 2: Avaliação de Métricas de Recuperação
- **Choice**: Mean Reciprocal Rank (MRR), Recall@3, Recall@5 e tempo de execução por query.
- **Rationale**: MRR avalia precisão no primeiro candidato retornado; Recall@3/5 afere se a nota fonte necessária está dentro do contexto injetado no prompt.
- **Alternatives considered**: NDCG (desnecessário para tarefas com ground-truth binário de relevância por chunk).

### Decision 3: Persistência de Resultados
- **Choice**: Exportação em JSON (`data/benchmarks/`) e geração de tabela Markdown para inclusão direta em `docs/experimentos/`.
- **Rationale**: Reprodutibilidade científica e integração contínua com a documentação do TCC.
