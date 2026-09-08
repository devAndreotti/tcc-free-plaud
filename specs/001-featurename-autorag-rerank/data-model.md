# Data Model: AutoRAG Rerank & Benchmark Metrics

## Entities & Schemas

### 1. RerankConfig
- `k: int = 60` (constante de suavização RRF, range 1-100)
- `bm25_weight: float = 1.0` (peso da recuperação léxica)
- `vector_weight: float = 1.0` (peso da recuperação vetorial)
- `top_k: int = 5` (quantidade de chunks preservados para o prompt)

### 2. RetrievalBenchmarkQuery
- `query_id: str`
- `query_text: str`
- `expected_chunk_ids: list[str]` (ground truth de relevância)
- `expected_note_title: str | None`

### 3. RetrievalBenchmarkResult
- `strategy: str` (`lexical`, `vector`, `hybrid_rrf`)
- `mrr: float` (0.0 a 1.0)
- `recall_at_3: float` (0.0 a 1.0)
- `recall_at_5: float` (0.0 a 1.0)
- `avg_latency_ms: float`
- `query_details: list[dict]`
