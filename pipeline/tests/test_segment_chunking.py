import hashlib
import json
import sqlite3
from pathlib import Path

import pytest

from escolio.app import audio_service
from escolio.corpus.ask import _citation_from_corpus_hit
from escolio.ingest.loaders import load_document
from escolio.ingest.models import IngestedDocument
from escolio.notes.schemas import Note
from escolio.notes.structurer import structure_document
from escolio.providers.audio_models import (
    AudioOptions,
    TranscriptionResult,
    TranscriptSegment,
)
from escolio.retrieval.chunking import (
    SEGMENT_STRATEGY,
    build_segment_text,
    chunk_segments,
    chunk_text,
)
from escolio.retrieval.indexer import index_note
from escolio.retrieval.models import Chunk, SearchHit
from escolio.storage.sqlite import (
    init_sqlite,
    list_chunks,
    replace_chunks_for_note,
    search_chunks_fts,
    upsert_note,
)
from escolio.storage.vector import LocalVectorStore

SHA = 'd' * 64

# Digest do chunk_text e da nota de texto calculado no código anterior a esta mudança (HEAD 4e18932).
# Os campos t_start/t_end são removidos antes do hash porque são novos e opcionais.
TEXT_GOLDEN_SHA256 = '898afb564924befc2d3fcd503d4635eff39ca715e9e7ce7283e169b4518985e8'


class FakeEmbedder:
    """Mesmo comportamento do embedder falso de test_vector_store.py: vetor hash, sem rede."""

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


def seg(start: float, end: float, text: str) -> TranscriptSegment:
    return TranscriptSegment(start=start, end=end, raw_text=text, text=text)


def _audio_document(segments: list[TranscriptSegment], source: str = 'aula.wav') -> IngestedDocument:
    text = ' '.join(s.text.strip() for s in segments if s.text.strip())
    return IngestedDocument(
        source_path=Path(source),
        source_type='wav',
        raw_text=text,
        cleaned_text=text,
        segments=segments,
    )


def _audio_note(segments: list[TranscriptSegment]) -> Note:
    return structure_document(_audio_document(segments), hash_unrooted=True)


def _text_digest() -> str:
    """Mesma receita do probe usado para fixar o golden: chunks de texto + nota de markdown."""
    texts = [
        'A recuperação em RAG depende da qualidade do chunking. ' * 30,
        '# Título\n\nParágrafo um com acentuação e números 123.\n\n- item a\n- item b\n' * 12,
        'Linha única sem quebras ' * 90,
    ]
    payload: list[dict[str, object]] = []
    for text in texts:
        for chunk in chunk_text('n1', 2, text, chunk_size=800, overlap=120, normalized_text_sha256='c' * 64):
            dumped = chunk.model_dump()
            dumped.pop('t_start')
            dumped.pop('t_end')
            payload.append(dumped)
    doc = IngestedDocument(source_path=Path('/tmp/nota-de-teste.md'), source_type='md', raw_text=texts[1].strip())
    note = structure_document(doc, hash_unrooted=True)
    payload.append(
        {
            'title': note.title,
            'summary': note.summary,
            'normalized_text': note.normalized_text,
            'content_hash': note.content_hash,
            'note_id': note.note_id,
            'md': note.structured_markdown,
        }
    )
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()


# --- agrupamento, pausa e tamanho -------------------------------------------------------------------------


def test_groups_consecutive_speech_without_cutting_a_segment() -> None:
    segments = [
        seg(0, 3, 'Primeira fala curta.'),
        seg(3, 6, 'Segunda fala curta.'),
        seg(6, 9, 'Terceira fala.'),
    ]

    chunks = chunk_segments('aula', 1, segments, normalized_text_sha256=SHA, target_chars=40, max_chars=200)

    assert [c.chunk_text for c in chunks] == [
        'Primeira fala curta. Segunda fala curta.',
        'Terceira fala.',
    ]
    assert (chunks[0].t_start, chunks[0].t_end) == (0, 6)
    assert (chunks[1].t_start, chunks[1].t_end) == (6, 9)
    assert all(c.strategy == SEGMENT_STRATEGY for c in chunks)
    assert [c.chunk_index for c in chunks] == [0, 1]


def test_long_pause_closes_chunk_even_below_target() -> None:
    segments = [
        seg(0, 2, 'Oi tudo bem.'),
        seg(2, 4, 'Tudo certo aqui.'),
        seg(10, 12, 'Depois de uma pausa.'),
    ]

    chunks = chunk_segments('aula', 1, segments, normalized_text_sha256=SHA, pause_seconds=2.0)

    assert [c.chunk_text for c in chunks] == [
        'Oi tudo bem. Tudo certo aqui.',
        'Depois de uma pausa.',
    ]
    assert chunks[1].t_start == 10


def test_pause_at_threshold_does_not_split() -> None:
    segments = [seg(0, 2, 'Um.'), seg(4, 6, 'Dois.')]

    chunks = chunk_segments('aula', 1, segments, normalized_text_sha256=SHA, pause_seconds=2.0)

    assert len(chunks) == 1


def test_segment_longer_than_max_is_split_by_sentence_within_limit() -> None:
    sentences = [f'Frase número {i} do trecho longo.' for i in range(60)]
    text = ' '.join(sentences)
    segments = [seg(0, 120, text)]

    chunks = chunk_segments('aula', 1, segments, normalized_text_sha256=SHA, target_chars=100, max_chars=200)

    assert len(chunks) > 1
    assert all(len(c.chunk_text) <= 200 for c in chunks)
    assert all(c.chunk_text.endswith('.') for c in chunks)
    # Nada se perde nem se repete: os pedaços, unidos por espaço, reconstroem a fala original.
    assert ' '.join(c.chunk_text for c in chunks) == text
    starts = [c.t_start for c in chunks]
    assert starts == sorted(starts)
    assert chunks[-1].t_end == pytest.approx(120)


def test_segment_without_punctuation_is_hard_split_at_spaces() -> None:
    text = ' '.join(['palavra'] * 300)
    segments = [seg(0, 60, text)]

    chunks = chunk_segments('aula', 1, segments, normalized_text_sha256=SHA, target_chars=100, max_chars=150)

    assert all(len(c.chunk_text) <= 150 for c in chunks)
    assert ' '.join(c.chunk_text for c in chunks) == text


def test_blank_segments_are_ignored() -> None:
    segments = [seg(0, 1, '   '), seg(1, 2, 'Fala real.'), seg(2, 3, '')]

    chunks = chunk_segments('aula', 1, segments, normalized_text_sha256=SHA)

    assert [c.chunk_text for c in chunks] == ['Fala real.']
    assert build_segment_text(segments) == 'Fala real.'


def test_empty_segments_produce_no_chunks() -> None:
    assert chunk_segments('aula', 1, [], normalized_text_sha256=SHA) == []


def test_invalid_limits_are_rejected() -> None:
    with pytest.raises(ValueError):
        chunk_segments('aula', 1, [seg(0, 1, 'x')], normalized_text_sha256=SHA, target_chars=0)
    with pytest.raises(ValueError):
        chunk_segments('aula', 1, [seg(0, 1, 'x')], normalized_text_sha256=SHA, target_chars=500, max_chars=400)
    with pytest.raises(ValueError):
        chunk_segments('aula', 1, [seg(0, 1, 'x')], normalized_text_sha256=SHA, pause_seconds=-1)


# --- offsets, determinismo, nota ----------------------------------------------------------------------------


def test_offsets_match_normalized_text_slices() -> None:
    segments = [
        seg(0, 4, 'Bom dia a todos, vamos começar a reunião.'),
        seg(4, 7, 'A pauta de hoje tem três itens.'),
        seg(9, 15, 'Primeiro, revisar o cronograma do projeto. Depois, discutir o orçamento.'),
        seg(15, 18, 'Último ponto: definir responsáveis.'),
    ]
    note = _audio_note(segments)

    chunks = index_note(note, chunk_size=800, overlap=120)

    assert note.normalized_text == build_segment_text(segments)
    assert chunks
    for chunk in chunks:
        assert note.normalized_text[chunk.char_start : chunk.char_end] == chunk.chunk_text
        assert chunk.strategy == SEGMENT_STRATEGY
        assert chunk.normalized_text_sha256 == note.content_hash


def test_offsets_match_text_with_long_segment_and_repeated_utterances() -> None:
    segments = [seg(i, i + 1, 'Sim.') for i in range(5)]
    segments.append(seg(5, 80, ' '.join(f'Trecho {i} com algum conteúdo.' for i in range(40))))
    segments.append(seg(80, 81, 'Sim.'))
    note = _audio_note(segments)

    chunks = index_note(note, chunk_size=800, overlap=120)

    assert len(chunks) >= 2
    for chunk in chunks:
        assert note.normalized_text[chunk.char_start : chunk.char_end] == chunk.chunk_text
    # "Sim." repetido não é removido, ao contrário do normalize_text de texto.
    assert note.normalized_text.count('Sim.') == 6


def test_chunk_ids_are_deterministic() -> None:
    segments = [seg(0, 2, 'Primeira.'), seg(2, 4, 'Segunda.'), seg(9, 10, 'Terceira.')]

    first = chunk_segments('aula', 2, segments, normalized_text_sha256=SHA, target_chars=10)
    second = chunk_segments('aula', 2, segments, normalized_text_sha256=SHA, target_chars=10)
    other_hash = chunk_segments('aula', 2, segments, normalized_text_sha256='e' * 64, target_chars=10)

    assert [c.model_dump() for c in first] == [c.model_dump() for c in second]
    assert [c.chunk_id for c in first] != [c.chunk_id for c in other_hash]
    assert first[0].chunk_id.startswith('aula::v2::ofs-000000-')


def test_structure_document_keeps_segments_in_memory_only() -> None:
    segments = [seg(0, 2, 'Oi.'), seg(2, 4, 'Tudo bem.')]

    note = _audio_note(segments)

    assert note.segments == segments
    assert note.normalized_text == 'Oi. Tudo bem.'
    assert 'segments' not in note.model_dump()


def test_index_note_rejects_segments_that_do_not_match_normalized_text() -> None:
    note = _audio_note([seg(0, 2, 'Oi.'), seg(2, 4, 'Tudo bem.')])
    note.normalized_text = 'texto diferente'

    with pytest.raises(ValueError):
        index_note(note)


def test_index_note_without_segments_still_uses_char_windows() -> None:
    note = structure_document(
        IngestedDocument(source_path=Path('nota.txt'), source_type='txt', raw_text='Texto simples. ' * 80),
        hash_unrooted=True,
    )

    chunks = index_note(note, chunk_size=200, overlap=40)

    assert note.segments is None
    assert chunks == chunk_text(
        note.note_id,
        note.note_version,
        note.normalized_text,
        chunk_size=200,
        overlap=40,
        normalized_text_sha256=note.content_hash,
    )
    assert all(c.t_start is None and c.t_end is None for c in chunks)


# --- regressão de texto e PDF -----------------------------------------------------------------------------------


def test_text_chunking_and_note_are_unchanged() -> None:
    assert _text_digest() == TEXT_GOLDEN_SHA256


def test_text_chunks_have_no_timestamps() -> None:
    chunks = chunk_text('n', 1, 'Frase de teste. ' * 100, normalized_text_sha256=SHA)

    assert chunks
    for chunk in chunks:
        assert chunk.t_start is None
        assert chunk.t_end is None
        assert 't_start' in chunk.model_dump()


def test_text_and_pdf_loaders_do_not_carry_segments(tmp_path: Path) -> None:
    text_file = tmp_path / 'nota.txt'
    text_file.write_text('Conteúdo de texto.', encoding='utf-8')

    document = load_document(text_file)

    assert document.segments is None


# --- carregador de áudio -----------------------------------------------------------------------------------------


class _FakeAudioRuntime:
    def __init__(self, result: TranscriptionResult) -> None:
        self._result = result

    def transcribe_result(self, source_path: Path, options: AudioOptions) -> TranscriptionResult:
        return self._result


def test_load_document_passes_segments_for_audio(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    audio = tmp_path / 'reuniao.wav'
    audio.write_bytes(b'RIFF')
    segments = [seg(0, 2, 'Abertura da reunião.'), seg(2, 5, 'Próximo assunto.')]
    result = TranscriptionResult(
        source_path=audio,
        source_sha256='0' * 64,
        model_id='fake',
        model_revision='test',
        language='pt',
        device='cpu',
        duration_seconds=5,
        raw_text='Abertura da reunião. Próximo assunto.',
        text='Abertura da reunião. Próximo assunto.',
        segments=segments,
    )
    monkeypatch.setattr(audio_service, 'audio_runtime', lambda *a, **k: _FakeAudioRuntime(result))
    monkeypatch.setattr(audio_service, 'audio_options', lambda *a, **k: AudioOptions())

    document = load_document(audio)

    assert document.segments == segments
    assert document.cleaned_text == result.text
    assert document.source_type == 'wav'


# --- persistência -------------------------------------------------------------------------------------------------

OLD_NOTES_DDL = """
CREATE TABLE notes (
    note_id TEXT PRIMARY KEY,
    note_version INTEGER NOT NULL,
    source_type TEXT NOT NULL,
    source_path TEXT NOT NULL,
    source_name TEXT NOT NULL,
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    raw_text TEXT NOT NULL,
    normalized_text TEXT NOT NULL,
    structured_markdown TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""

# Schema do chunks antes desta mudança: sem t_start/t_end.
OLD_CHUNKS_DDL = """
CREATE TABLE chunks (
    chunk_id TEXT PRIMARY KEY,
    note_id TEXT NOT NULL REFERENCES notes(note_id) ON DELETE CASCADE,
    note_version INTEGER NOT NULL,
    chunk_index INTEGER NOT NULL,
    char_start INTEGER NOT NULL,
    char_end INTEGER NOT NULL,
    chunk_size INTEGER NOT NULL,
    overlap INTEGER NOT NULL,
    chunk_text TEXT NOT NULL,
    token_count INTEGER NOT NULL,
    strategy TEXT NOT NULL,
    normalized_text_sha256 TEXT NOT NULL,
    text_sha256 TEXT NOT NULL,
    pipeline_version TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    UNIQUE (note_id, note_version, chunk_index)
);
"""


def _columns(path: Path, table: str) -> set[str]:
    connection = sqlite3.connect(path)
    try:
        return {str(row[1]) for row in connection.execute(f'PRAGMA table_info({table})').fetchall()}
    finally:
        connection.close()


def test_init_sqlite_migrates_old_database_and_keeps_rows(tmp_path: Path) -> None:
    db_path = tmp_path / 'antigo.sqlite3'
    old = sqlite3.connect(db_path)
    old.executescript(OLD_NOTES_DDL + OLD_CHUNKS_DDL)
    old.execute(
        'INSERT INTO notes VALUES (?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
        ('old-note', 'md', '/x/old.md', 'old.md', 'Antiga', 'Resumo', 'raw', 'texto antigo', '# Antiga',
         'h' * 64, 'local', 'rule-based', '2026-01-01T00:00:00+00:00'),
    )
    old.execute(
        'INSERT INTO chunks (chunk_id, note_id, note_version, chunk_index, char_start, char_end, chunk_size, overlap, '
        'chunk_text, token_count, strategy, normalized_text_sha256, text_sha256, pipeline_version) '
        'VALUES (?, ?, 1, 0, 0, 11, 800, 120, ?, 2, ?, ?, ?, ?)',
        ('old-note::v1::ofs-000000-000011::abc', 'old-note', 'texto antigo', 'fixed_char_window',
         'h' * 64, 't' * 64, 'pipeline-0.4.0'),
    )
    old.commit()
    old.close()
    assert 't_start' not in _columns(db_path, 'chunks')

    connection = init_sqlite(db_path)
    try:
        assert {'t_start', 't_end'} <= _columns(db_path, 'chunks')
        old_chunks = list_chunks(connection)
        assert [c.chunk_text for c in old_chunks] == ['texto antigo']
        assert old_chunks[0].t_start is None and old_chunks[0].t_end is None
    finally:
        connection.close()

    # Abrir de novo (migração já aplicada) não pode falhar nem duplicar colunas.
    reopened = init_sqlite(db_path)
    reopened.close()
    assert len(_columns(db_path, 'chunks') & {'t_start', 't_end'}) == 2


def test_sqlite_round_trip_keeps_timestamps_in_chunks_and_fts(tmp_path: Path) -> None:
    segments = [seg(0, 3, 'O orçamento foi aprovado.'), seg(3, 7, 'A equipe começa na segunda.')]
    note = _audio_note(segments)
    chunks = index_note(note)
    connection = init_sqlite(tmp_path / 'rt.sqlite3')
    try:
        upsert_note(connection, note)
        replace_chunks_for_note(connection, note.note_id, chunks)

        stored = list_chunks(connection)
        hits = search_chunks_fts(connection, 'orçamento', limit=5)
    finally:
        connection.close()

    assert [(c.t_start, c.t_end) for c in stored] == [(0, 7)]
    assert hits and hits[0][0].t_start == 0 and hits[0][0].t_end == 7


def test_chroma_round_trip_keeps_timestamps_only_when_present(tmp_path: Path) -> None:
    embedder = FakeEmbedder()
    segments = [seg(0, 3, 'Revisar o cronograma do projeto.'), seg(20, 24, 'Definir o orçamento anual.')]
    note = _audio_note(segments)
    audio_chunks = chunk_segments(
        note.note_id, note.note_version, segments, normalized_text_sha256=note.content_hash, target_chars=10
    )
    text_chunks = chunk_text(
        'texto-note', 1, 'Trecho de texto simples sobre o cronograma.', normalized_text_sha256=SHA
    )
    store = LocalVectorStore(tmp_path / 'vs', collection_name='segment_chunks')
    all_chunks = [*audio_chunks, *text_chunks]
    store.upsert_chunks(all_chunks, embedder.embed([c.chunk_text for c in all_chunks]), embedding_model='fake-hash')

    records = dict(store.list_records())
    audio_meta = records[audio_chunks[0].chunk_id]
    text_meta = records[text_chunks[0].chunk_id]
    assert audio_meta['t_start'] == 0 and audio_meta['t_end'] == 3
    assert 't_start' not in text_meta and 't_end' not in text_meta

    hits = store.query(embedder.embed(['cronograma projeto'])[0], top_k=10)
    by_id = {hit.chunk.chunk_id: hit.chunk for hit in hits}
    assert by_id[audio_chunks[0].chunk_id].t_start == 0
    assert by_id[audio_chunks[0].chunk_id].t_end == 3
    assert by_id[audio_chunks[1].chunk_id].t_start == 20
    assert by_id[text_chunks[0].chunk_id].t_start is None
    assert by_id[text_chunks[0].chunk_id].t_end is None


# --- citação ----------------------------------------------------------------------------------------------------------


def test_citation_carries_timestamps_from_segment_chunk() -> None:
    note = _audio_note([seg(12.5, 15, 'Decisão tomada na reunião.')])
    chunk = index_note(note)[0]

    citation = _citation_from_corpus_hit(SearchHit(chunk=chunk, score=1.0), {note.note_id: note})

    assert citation.t_start == 12.5
    assert citation.t_end == 15
    assert citation.char_start == chunk.char_start
    assert citation.char_end == chunk.char_end
    assert citation.chunk_id == chunk.chunk_id


def test_citation_for_text_chunk_has_no_timestamps() -> None:
    chunk: Chunk = chunk_text('nota', 1, 'Texto comum de nota.', normalized_text_sha256=SHA)[0]

    citation = _citation_from_corpus_hit(SearchHit(chunk=chunk, score=1.0), {})

    assert citation.t_start is None
    assert citation.t_end is None
