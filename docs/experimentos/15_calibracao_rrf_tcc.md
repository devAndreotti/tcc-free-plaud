# Experimento 15: Calibração de RRF e Avaliação Multi-Estratégia no AutoRAG

## Objetivo
Avaliar empiricamente o impacto da constante de suavização $k$ no Reciprocal Rank Fusion (RRF) em comparação com as estratégias isoladas léxica (SQLite FTS5 BM25) e vetorial (ChromaDB + SentenceTransformers).

## Metodologia & Dataset
- **Coleção de Teste**: Suite de benchmark com notas pessoais estruturadas em português brasileiro (PT-BR).
- **Métricas Analisadas**: Mean Reciprocal Rank (MRR), Recall@3, Recall@5 e Latência Média (ms).
- **Configurações Avaliadas**:
  1. `Lexical-Only` (BM25 FTS5 puro)
  2. `Vector-Only` (ChromaDB cosine similarity)
  3. `Hybrid RRF (k=10)`
  4. `Hybrid RRF (k=60)` (Baseline padrão)
  5. `Hybrid RRF (k=100)`

## Resultados Obtidos

| Estratégia | MRR | Recall@3 | Recall@5 | Latência Média (ms) |
|---|---|---|---|---|
| **Lexical-Only (BM25)** | 0.812 | 0.840 | 0.880 | ~8.4 ms |
| **Vector-Only (Chroma)** | 0.795 | 0.820 | 0.865 | ~34.2 ms |
| **Hybrid RRF (k=10)** | 0.865 | 0.890 | 0.930 | ~42.5 ms |
| **Hybrid RRF (k=60)** | **0.884** | **0.915** | **0.950** | ~41.8 ms |
| **Hybrid RRF (k=100)** | 0.871 | 0.900 | 0.940 | ~42.0 ms |

## Análise e Conclusões para o TCC
1. **Superioridade do Híbrido**: A fusão RRF com $k=60$ superou tanto a busca puramente léxica (+7.2% MRR) quanto a puramente semântica (+8.9% MRR).
2. **Robustez do $k=60$**: O amortecimento $k=60$ mitiga termos com alta pontuação vetorial espúria sem desfavorecer palavras-chave exatas de notas técnicas.
3. **Viabilidade Local-First**: A sobrecarga de latência adicional do RRF em memória foi de < 1 ms sobre o tempo de embedding do ChromaDB, mantendo a resposta total interativa.
