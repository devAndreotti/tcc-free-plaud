from escolio.benchmark.datasets import BenchmarkDataset, BenchmarkSample
from escolio.benchmark.embed_compression_bench import compare_embedding_compression
from escolio.notes.schemas import Note
from escolio.providers.embed_compressor import (
    CompressingEmbedder,
    EmbeddingQuantizationError,
    compression_ratio,
    dequantize_batch,
    dequantize_vector,
    float32_size_bytes,
    pack_quantized_vector,
    quantize_batch,
    quantize_vector,
    quantized_size_bytes,
    unpack_quantized_vector,
)
from escolio.storage.vector import LocalVectorStore


class FakeEmbedder:
    model_name = 'fake-embedder'

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[float(index), -float(index) / 2, 0.0, index * 1.5] for index, _ in enumerate(texts, start=1)]


def test_quantize_vector_round_trip_bounds_error() -> None:
    vector = [0.0, 0.25, 0.5, 0.75, 1.0, -1.0, 3.3]
    quantized = quantize_vector(vector)
    restored = dequantize_vector(quantized)

    assert len(restored) == len(vector)
    max_error = max(abs(a - b) for a, b in zip(vector, restored, strict=True))
    span = max(vector) - min(vector)
    assert max_error <= span / 255.0 + 1e-9


def test_quantize_vector_endpoints_are_exact() -> None:
    vector = [-2.0, 0.0, 5.0, 10.0]
    restored = dequantize_vector(quantize_vector(vector))
    assert restored[0] == -2.0
    assert restored[3] == 10.0


def test_quantize_vector_rejects_empty() -> None:
    try:
        quantize_vector([])
    except EmbeddingQuantizationError:
        pass
    else:
        raise AssertionError('Era esperado EmbeddingQuantizationError para vetor vazio.')


def test_quantize_vector_constant_vector_no_division_by_zero() -> None:
    restored = dequantize_vector(quantize_vector([3.0, 3.0, 3.0]))
    assert restored == [3.0, 3.0, 3.0]


def test_batch_helpers_preserve_order() -> None:
    vectors = [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]
    restored = dequantize_batch(quantize_batch(vectors))
    assert len(restored) == 2
    assert restored[0] != restored[1]


def test_pack_unpack_round_trip() -> None:
    quantized = quantize_vector([1.0, 2.0, 3.0, 4.0])
    packed = pack_quantized_vector(quantized)
    restored = unpack_quantized_vector(packed)

    assert restored.dim == quantized.dim
    assert restored.scale == quantized.scale
    assert restored.zero_point == quantized.zero_point
    assert restored.codes == quantized.codes


def test_unpack_rejects_truncated_payload() -> None:
    try:
        unpack_quantized_vector(b'\x00\x01')
    except EmbeddingQuantizationError:
        pass
    else:
        raise AssertionError('Era esperado EmbeddingQuantizationError para payload truncado.')


def test_compression_ratio_is_close_to_4x_for_large_dims() -> None:
    ratio = compression_ratio(768)
    assert 3.8 < ratio < 4.0
    assert float32_size_bytes(768) == 768 * 4
    assert quantized_size_bytes(768) == 768 + 20


def test_compressing_embedder_preserves_dim_and_model_name() -> None:
    inner = FakeEmbedder()
    wrapped = CompressingEmbedder(inner)

    assert wrapped.model_name == inner.model_name

    raw = inner.embed(['a', 'b'])
    compressed = wrapped.embed(['a', 'b'])

    assert len(compressed) == len(raw)
    for raw_vector, compressed_vector in zip(raw, compressed, strict=True):
        assert len(compressed_vector) == len(raw_vector)
        span = max(raw_vector) - min(raw_vector) or 1.0
        for raw_value, compressed_value in zip(raw_vector, compressed_vector, strict=True):
            assert abs(raw_value - compressed_value) <= span / 255.0 + 1e-9


class FakeHashEmbedder:
    model_name = 'fake-hash'

    def embed(self, texts: list[str]) -> list[list[float]]:
        embeddings: list[list[float]] = []
        for text in texts:
            vector = [0.0] * 16
            for token in text.lower().split():
                slot = sum(ord(char) for char in token) % len(vector)
                vector[slot] += 1.0
            embeddings.append(vector)
        return embeddings


def _build_compression_note(tmp_path):
    text = (
        'O benchmark mede recall, latencia e cobertura de citacoes para comparar retrieval. '
        'A recuperacao vetorial usa embeddings persistidos no ChromaDB local. '
        'O SQLite registra execucoes, metricas e consultas avaliadas.'
    )
    return Note(
        note_id='benchmark-note',
        note_version=1,
        source_type='md',
        source_path=tmp_path / 'benchmark.md',
        source_name='benchmark.md',
        title='Benchmark do pipeline RAG',
        summary='Resumo da nota de benchmark.',
        topics=[],
        tasks=[],
        tags=['md'],
        raw_text=text,
        normalized_text=text,
        structured_markdown=f'# Benchmark do pipeline RAG\n\n{text}\n',
        content_hash='a' * 64,
    )


def test_compare_embedding_compression_reports_tradeoffs(tmp_path) -> None:
    note = _build_compression_note(tmp_path)
    dataset = BenchmarkDataset(
        dataset_name='rag-compression',
        samples=[
            BenchmarkSample(
                sample_id='q-1',
                question='O que o benchmark mede?',
                expected_note_id=note.note_id,
                expected_terms=['recall', 'latencia'],
            )
        ],
    )
    vector_store = LocalVectorStore(tmp_path / 'results' / 'vector_store', collection_name='compression_run')

    comparison = compare_embedding_compression(
        note,
        dataset,
        vector_store=vector_store,
        embedder=FakeHashEmbedder(),
        top_k=3,
        chunk_size=120,
        overlap=30,
    )

    assert comparison.baseline.retrieval_strategy == 'vector'
    assert comparison.quantized.retrieval_strategy == 'vector'
    assert comparison.embedding_dim == 16
    assert comparison.compression_ratio > 1.0
    assert comparison.mrr_delta == comparison.quantized.metrics['mrr'] - comparison.baseline.metrics['mrr']
    assert comparison.recall_at_5_delta == (
        comparison.quantized.metrics['recall_at_5'] - comparison.baseline.metrics['recall_at_5']
    )
