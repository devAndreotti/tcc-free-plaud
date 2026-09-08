# Contract: Benchmark CLI & Facade Interface

## CLI Command
```bash
fp benchmark run [--dataset <path>] [--k-rrf <int>] [--output <json|markdown>]
```

## Facade API
```python
def run_retrieval_benchmark(
    dataset_path: Path | None = None,
    k_rrf: int = 60,
    top_k: int = 5
) -> dict[str, RetrievalBenchmarkResult]:
    """Executes comparative evaluation across lexical, vector, and hybrid RRF strategies."""
    ...
```
