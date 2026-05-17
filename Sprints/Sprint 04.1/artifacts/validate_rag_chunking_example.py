from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import List


@dataclass
class Chunk:
    chunk_id: str
    note_id: str
    note_version_id: str
    chunk_index: int
    char_start: int
    char_end: int
    chunk_size: int
    overlap: int
    token_count: int
    text: str
    text_sha256: str
    pipeline_version: str


def stable_chunk_id(
    note_id: str,
    note_version_id: str,
    char_start: int,
    char_end: int,
    strategy: str,
    normalized_text_sha256: str,
) -> str:
    raw = f"{note_id}|{note_version_id}|{char_start}|{char_end}|{strategy}|{normalized_text_sha256}"
    digest = sha256(raw.encode("utf-8")).hexdigest()[:10]
    return f"{note_version_id}::ofs-{char_start:06d}-{char_end:06d}::{digest}"


def chunk_text(
    note_id: str,
    note_version_id: str,
    text: str,
    *,
    chunk_size: int,
    overlap: int,
    strategy: str = "fixed_char_window",
    pipeline_version: str = "ingest-2026.04",
) -> List[Chunk]:
    if chunk_size <= 0:
        raise ValueError("chunk_size deve ser positivo")
    if overlap < 0:
        raise ValueError("overlap não pode ser negativo")
    if overlap >= chunk_size:
        raise ValueError("overlap deve ser menor que chunk_size")

    normalized_text = " ".join(text.split())
    normalized_text_sha256 = sha256(normalized_text.encode("utf-8")).hexdigest()

    chunks: List[Chunk] = []
    start = 0
    chunk_index = 0

    while start < len(normalized_text):
        end = min(start + chunk_size, len(normalized_text))
        chunk_text_value = normalized_text[start:end]
        chunk_id = stable_chunk_id(
            note_id=note_id,
            note_version_id=note_version_id,
            char_start=start,
            char_end=end,
            strategy=strategy,
            normalized_text_sha256=normalized_text_sha256,
        )
        chunks.append(
            Chunk(
                chunk_id=chunk_id,
                note_id=note_id,
                note_version_id=note_version_id,
                chunk_index=chunk_index,
                char_start=start,
                char_end=end,
                chunk_size=chunk_size,
                overlap=overlap,
                token_count=len(chunk_text_value.split()),
                text=chunk_text_value,
                text_sha256=sha256(chunk_text_value.encode("utf-8")).hexdigest(),
                pipeline_version=pipeline_version,
            )
        )
        if end == len(normalized_text):
            break
        start = end - overlap
        chunk_index += 1

    return chunks


def run_tests() -> None:
    text = (
        "A recuperação em RAG depende da qualidade do chunking. "
        "Chunks muito grandes diluem tópicos diferentes em um único vetor. "
        "Chunks muito pequenos podem fragmentar evidências relevantes. "
        "Overlap moderado reduz perdas nas fronteiras e offsets absolutos permitem reconstruir a origem exata de cada citação."
    )

    chunks = chunk_text(
        note_id="NOTE-001",
        note_version_id="NOTE-001::v1",
        text=text,
        chunk_size=120,
        overlap=30,
    )

    assert len(chunks) >= 2
    assert chunks[0].note_id == "NOTE-001"
    assert chunks[0].note_version_id == "NOTE-001::v1"
    assert chunks[0].char_start == 0
    assert chunks[1].char_start == chunks[0].char_end - 30
    assert chunks[0].chunk_id != chunks[1].chunk_id
    assert chunks[0].text_sha256 == sha256(chunks[0].text.encode("utf-8")).hexdigest()

    # determinismo
    chunks_again = chunk_text(
        note_id="NOTE-001",
        note_version_id="NOTE-001::v1",
        text=text,
        chunk_size=120,
        overlap=30,
    )
    assert [c.chunk_id for c in chunks] == [c.chunk_id for c in chunks_again]
    assert [(c.char_start, c.char_end) for c in chunks] == [
        (c.char_start, c.char_end) for c in chunks_again
    ]

    print("OK")
    for c in chunks:
        print(c.chunk_index, c.chunk_id, c.char_start, c.char_end, c.text[:40])


if __name__ == "__main__":
    run_tests()
