# Quickstart: AutoRAG Rerank Calibration

## Execution Steps
1. Executar suíte de testes de benchmark:
   ```powershell
   cd pipeline
   uv run pytest tests/test_benchmark.py
   ```
2. Rodar calibração via CLI do Free Plaud:
   ```powershell
   cd pipeline
   uv run python -m free_plaud.cli benchmark run
   ```
3. Verificar métricas geradas em `docs/experimentos/`.
