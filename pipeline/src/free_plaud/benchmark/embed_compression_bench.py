"""Benchmark comparativo: embeddings float32 (baseline) vs quantizados int8.

Reutiliza `run_benchmark` (mesma engine de MRR/Recall/nDCG/latencia da Sprint 07)
trocando apenas o embedder por `CompressingEmbedder`, isolando o tradeoff de
qualidade de retrieval introduzido pela compressao TurboQuant.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from free_plaud.benchmark.datasets import BenchmarkDataset
from free_plaud.benchmark.runners import BenchmarkRunResult, run_benchmark
from free_plaud.notes.schemas import Note
from free_plaud.providers.embed import Embedder
from free_plaud.providers.embed_compressor import CompressingEmbedder, compression_ratio
from free_plaud.storage.vector import LocalVectorStore


class EmbeddingCompressionComparison(BaseModel):
    """Resultado lado a lado: baseline float32 vs embeddings quantizados int8."""

    baseline: BenchmarkRunResult
    quantized: BenchmarkRunResult
    embedding_dim: int
    compression_ratio: float
    mrr_delta: float = Field(description='quantized.mrr - baseline.mrr (negativo = perda de qualidade)')
    recall_at_5_delta: float
    latency_ms_delta: int = Field(description='quantized.latency_ms - baseline.latency_ms')


def compare_embedding_compression(
    note: Note,
    dataset: BenchmarkDataset,
    *,
    vector_store: LocalVectorStore,
    embedder: Embedder,
    top_k: int = 5,
    chunk_size: int = 800,
    overlap: int = 120,
) -> EmbeddingCompressionComparison:
    """Roda o mesmo benchmark de retrieval vetorial com embedder normal e comprimido."""
    vector_store.reset()
    baseline = run_benchmark(
        note,
        dataset,
        strategy='vector',
        top_k=top_k,
        chunk_size=chunk_size,
        overlap=overlap,
        run_name='embed-compression-baseline-float32',
        vector_store=vector_store,
        embedder=embedder,
    )

    vector_store.reset()
    quantized = run_benchmark(
        note,
        dataset,
        strategy='vector',
        top_k=top_k,
        chunk_size=chunk_size,
        overlap=overlap,
        run_name='embed-compression-quantized-int8',
        vector_store=vector_store,
        embedder=CompressingEmbedder(embedder),
    )

    probe_vector = embedder.embed(['probe'])[0]
    embedding_dim = len(probe_vector)

    return EmbeddingCompressionComparison(
        baseline=baseline,
        quantized=quantized,
        embedding_dim=embedding_dim,
        compression_ratio=compression_ratio(embedding_dim),
        mrr_delta=quantized.metrics['mrr'] - baseline.metrics['mrr'],
        recall_at_5_delta=quantized.metrics['recall_at_5'] - baseline.metrics['recall_at_5'],
        latency_ms_delta=int(quantized.metrics['latency_ms']) - int(baseline.metrics['latency_ms']),
    )
