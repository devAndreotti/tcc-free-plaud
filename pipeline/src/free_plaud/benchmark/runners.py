from free_plaud.benchmark.datasets import BenchmarkSample
from free_plaud.benchmark.metrics import recall_at_k
from free_plaud.notes.schemas import Note
from free_plaud.retrieval.indexer import index_note
from free_plaud.retrieval.search import lexical_search


def run_demo_benchmark(note: Note, samples: list[BenchmarkSample]) -> list[dict[str, float | str]]:
    """Executa um benchmark mínimo usando busca lexical sobre os chunks."""
    chunks = index_note(note)
    results: list[dict[str, float | str]] = []
    for sample in samples:
        hits = lexical_search(sample.question, chunks, top_k=3)
        relevant_hits = 0
        for hit in hits:
            text = hit.chunk_text.lower()
            if any(term.lower() in text for term in sample.expected_terms):
                relevant_hits += 1
        results.append(
            {
                'sample_id': sample.sample_id,
                'recall_at_3': recall_at_k(relevant_hits, max(len(sample.expected_terms), 1)),
            }
        )
    return results
