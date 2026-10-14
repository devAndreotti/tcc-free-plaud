"""Quantizacao escalar int8 para embeddings, reduzindo footprint antes de persistir.

Compressao extrema (4x vs float32) via affine scalar quantization por vetor.
Round-trip float32 -> int8 -> float32 mantem compatibilidade total com o
LocalVectorStore/ChromaDB e a busca hibrida RRF: nenhuma outra camada precisa
mudar, pois o resultado de `CompressingEmbedder.embed` ainda e list[list[float]].
"""

from __future__ import annotations

import array
import struct
from dataclasses import dataclass

from escolio.providers.embed import Embedder

_CODE_MIN, _CODE_MAX = -128, 127
_HEADER = struct.Struct('<ddI')  # zero_point(f64), scale(f64), dim(u32)


class EmbeddingQuantizationError(ValueError):
    """Erro de quantizacao/serializacao de embeddings."""


@dataclass(frozen=True)
class QuantizedVector:
    """Vetor comprimido: 1 byte por dimensao + escala/offset para reconstrucao."""

    codes: bytes
    scale: float
    zero_point: float
    dim: int


def quantize_vector(vector: list[float]) -> QuantizedVector:
    """Comprime um vetor float para int8 via min-max affine quantization."""
    if not vector:
        raise EmbeddingQuantizationError('Vetor vazio nao pode ser quantizado.')
    lo, hi = min(vector), max(vector)
    scale = (hi - lo) / (_CODE_MAX - _CODE_MIN) if hi > lo else 1.0
    codes = array.array(
        'b',
        (max(_CODE_MIN, min(_CODE_MAX, round((value - lo) / scale) + _CODE_MIN)) for value in vector),
    )
    return QuantizedVector(codes=codes.tobytes(), scale=scale, zero_point=lo, dim=len(vector))


def dequantize_vector(quantized: QuantizedVector) -> list[float]:
    """Reconstroi o vetor float aproximado a partir dos codigos int8."""
    codes = array.array('b')
    codes.frombytes(quantized.codes)
    return [quantized.zero_point + (code - _CODE_MIN) * quantized.scale for code in codes]


def quantize_batch(vectors: list[list[float]]) -> list[QuantizedVector]:
    return [quantize_vector(vector) for vector in vectors]


def dequantize_batch(quantized: list[QuantizedVector]) -> list[list[float]]:
    return [dequantize_vector(item) for item in quantized]


def pack_quantized_vector(quantized: QuantizedVector) -> bytes:
    """Serializa um QuantizedVector em bytes para persistencia (ex.: BLOB SQLite)."""
    return _HEADER.pack(quantized.zero_point, quantized.scale, quantized.dim) + quantized.codes


def unpack_quantized_vector(data: bytes) -> QuantizedVector:
    """Desserializa bytes produzidos por `pack_quantized_vector`."""
    if len(data) < _HEADER.size:
        raise EmbeddingQuantizationError('Payload de embedding comprimido invalido ou truncado.')
    zero_point, scale, dim = _HEADER.unpack_from(data)
    codes = data[_HEADER.size : _HEADER.size + dim]
    if len(codes) != dim:
        raise EmbeddingQuantizationError('Payload de embedding comprimido com tamanho inconsistente.')
    return QuantizedVector(codes=codes, scale=scale, zero_point=zero_point, dim=dim)


def quantized_size_bytes(dim: int) -> int:
    """Tamanho em bytes do payload comprimido (header + 1 byte/dimensao)."""
    return _HEADER.size + dim


def float32_size_bytes(dim: int) -> int:
    """Tamanho em bytes do vetor float32 nao comprimido, para comparacao."""
    return dim * 4


def compression_ratio(dim: int) -> float:
    """Razao de reducao de footprint (float32 / int8 comprimido)."""
    return float32_size_bytes(dim) / quantized_size_bytes(dim)


class CompressingEmbedder:
    """Embedder decorator: aplica quantizacao int8 (round-trip) antes de persistir.

    Mantem compatibilidade total com `LocalVectorStore.upsert_chunks` e a busca
    hibrida RRF pois `embed()` continua retornando `list[list[float]]`; a perda
    de precisao introduzida pela quantizacao e o tradeoff avaliado no benchmark.
    """

    def __init__(self, inner: Embedder) -> None:
        self._inner = inner
        self.model_name = inner.model_name

    def embed(self, texts: list[str]) -> list[list[float]]:
        raw_embeddings = self._inner.embed(texts)
        return dequantize_batch(quantize_batch(raw_embeddings))
