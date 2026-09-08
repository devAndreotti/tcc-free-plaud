# Feature Specification: AutoRAG Rerank Calibration & Evaluation

## Summary
Calibrar os parâmetros de fusão híbrida (Reciprocal Rank Fusion k=60 vs pesos ponderados BM25/vetorial) e padronizar métricas de avaliação de recuperação (MRR, Recall@k e latência) para validação empírica dos experimentos do TCC.

## Motivation & Problem Statement
O TCC investiga como diferentes estratégias de recuperação afetam a relevância semântica e a precisão de citações em notas pessoais em português brasileiro. Para embasar conclusões científicas, o pipeline necessita de:
1. Mecanismo reproduzível de calibração entre busca léxica (FTS5 BM25) e busca vetorial (ChromaDB).
2. Protocolo de benchmark automatizado gerando relatórios de acurácia e tempo de resposta.
3. Garantia de que candidatos fundidos preservem limites de caracteres para verificação estrita de citações.

## Functional Requirements
- **FR-01**: Suportar configuração dinâmica de constantes de fusão RRF (k variando de 10 a 100) via CLI e arquivo de configuração.
- **FR-02**: Executar suíte de benchmark de recuperação comparando 3 estratégias: `lexical-only`, `vector-only` e `hybrid-rrf`.
- **FR-03**: Calcular e persistir métricas de qualidade: Mean Reciprocal Rank (MRR), Recall@3, Recall@5 e latência média (ms).
- **FR-04**: Exportar resultados em formatos consumíveis para o texto do TCC (JSON estruturado e tabela Markdown).
- **FR-05**: Manter compatibilidade com a verificação de span exato das citações do `AnswerService`.

## Non-Functional & Architecture Requirements
- **NFR-01**: Operação estritamente local (`local-first`), sem dependência de rede para benchmarking.
- **NFR-02**: Execução de 50 consultas de teste em menos de 10 segundos no hardware alvo.
- **NFR-03**: Cobertura de testes unitários e de integração >= 85% conforme política do Quality Gate.

## Acceptance Criteria
- [ ] Execução de `fp benchmark run` gera relatório comparativo válido sem erros de runtime.
- [ ] Resultados salvos em `docs/experimentos/` com rastreabilidade de parâmetros.
- [ ] Todos os testes passam no `pytest` e Quality Gate Ratchet se mantém verde.
