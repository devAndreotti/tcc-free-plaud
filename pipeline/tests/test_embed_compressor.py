from free_plaud.providers.embed_compressor import (
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
