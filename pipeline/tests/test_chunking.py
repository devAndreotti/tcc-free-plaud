from pathlib import Path

from typer.testing import CliRunner

from escolio.cli import app
from escolio.notes.schemas import Note
from escolio.retrieval.chunking import chunk_text
from escolio.retrieval.indexer import index_note

runner = CliRunner()


def _build_note(**overrides: object) -> Note:
    payload: dict[str, object] = {
        'note_id': 'note-1',
        'note_version': 1,
        'source_type': 'md',
        'source_path': Path('sample.md'),
        'source_name': 'sample.md',
        'title': 'Sample Note',
        'summary': 'Resumo',
        'topics': [],
        'tasks': [],
        'tags': ['md'],
        'raw_text': 'Texto bruto',
        'normalized_text': 'Texto bruto',
        'structured_markdown': '# Sample Note\n\nTexto bruto',
        'content_hash': 'a' * 64,
    }
    payload.update(overrides)
    return Note(**payload)


def test_chunk_text_generates_deterministic_chunks_with_offsets_and_lineage() -> None:
    text = (
        'A recuperação em RAG depende da qualidade do chunking. '
        'Chunks muito grandes diluem tópicos diferentes em um único vetor. '
        'Chunks muito pequenos podem fragmentar evidências relevantes. '
        'Overlap moderado reduz perdas nas fronteiras e offsets absolutos permitem reconstruir a origem exata.'
    )

    chunks = chunk_text(
        note_id='note-1',
        note_version=3,
        text=text,
        chunk_size=120,
        overlap=30,
        normalized_text_sha256='b' * 64,
    )
    chunks_again = chunk_text(
        note_id='note-1',
        note_version=3,
        text=text,
        chunk_size=120,
        overlap=30,
        normalized_text_sha256='b' * 64,
    )

    assert len(chunks) >= 2
    assert chunks[0].note_id == 'note-1'
    assert chunks[0].note_version == 3
    assert chunks[0].chunk_index == 0
    assert chunks[0].char_start == 0
    assert chunks[1].char_start == chunks[0].char_end - 30
    assert chunks[0].chunk_size == 120
    assert chunks[0].overlap == 30
    assert chunks[0].strategy == 'fixed_char_window'
    assert chunks[0].normalized_text_sha256 == 'b' * 64
    assert chunks[0].text_sha256
    assert [chunk.chunk_id for chunk in chunks] == [chunk.chunk_id for chunk in chunks_again]
    assert [(chunk.char_start, chunk.char_end) for chunk in chunks] == [
        (chunk.char_start, chunk.char_end) for chunk in chunks_again
    ]


def test_chunk_text_rejects_invalid_chunking_parameters() -> None:
    text = 'texto qualquer para chunking'

    try:
        chunk_text(
            note_id='note-1',
            note_version=1,
            text=text,
            chunk_size=100,
            overlap=100,
            normalized_text_sha256='c' * 64,
        )
    except ValueError as exc:
        assert 'overlap' in str(exc)
    else:
        raise AssertionError('Era esperado ValueError quando overlap >= chunk_size')


def test_index_note_uses_normalized_text_instead_of_raw_text() -> None:
    note = _build_note(
        raw_text='Linha 1   com   espacos\n\nLinha 2',
        normalized_text='Linha 1 com espacos\nLinha 2',
        content_hash='d' * 64,
    )

    chunks = index_note(note, chunk_size=40, overlap=10)

    assert chunks
    assert chunks[0].chunk_text.startswith('Linha 1 com espacos')
    assert '   ' not in chunks[0].chunk_text
    assert chunks[0].note_version == note.note_version
    assert chunks[0].normalized_text_sha256 == note.content_hash


def test_chunk_ids_include_note_version_and_offsets() -> None:
    chunks = chunk_text(
        note_id='note-xyz',
        note_version=2,
        text='abcdefghij' * 30,
        chunk_size=50,
        overlap=10,
        normalized_text_sha256='e' * 64,
    )

    assert chunks[0].chunk_id.startswith('note-xyz::v2::')
    assert 'ofs-' in chunks[0].chunk_id


def test_index_note_keeps_chunk_text_exactly_aligned_with_offset_span() -> None:
    note = _build_note(
        raw_text='Linha 1  \nLinha 2 com espaco no fim \nLinha 3',
        normalized_text='Linha 1  \nLinha 2 com espaco no fim \nLinha 3',
        content_hash='f' * 64,
    )

    chunks = index_note(note, chunk_size=18, overlap=6)

    assert chunks
    for chunk in chunks:
        assert note.normalized_text[chunk.char_start:chunk.char_end] == chunk.chunk_text


def test_retrieval_chunks_cli_renders_offsets_and_lineage(tmp_path: Path) -> None:
    sample_file = tmp_path / 'doc.md'
    sample_file.write_text(
        '# Documento de Teste\n\n'
        'Este documento existe para validar a saida do comando de chunking.\n'
        'Ele possui texto suficiente para gerar pelo menos um chunk relevante.\n',
        encoding='utf-8',
    )

    result = runner.invoke(app, ['retrieval', 'chunks', str(sample_file), '--chunk-size', '60', '--overlap', '15'])

    assert result.exit_code == 0
    assert 'ofs=' in result.stdout
    assert 'v1' in result.stdout


def test_retrieval_chunks_cli_tolerates_emoji_in_preview(tmp_path: Path) -> None:
    sample_file = tmp_path / 'emoji.md'
    sample_file.write_text(
        '# Documento 🚀\n\n'
        'Texto com emoji 😄 para validar a impressao do preview em ambientes Windows mais restritivos.\n',
        encoding='utf-8',
    )

    result = runner.invoke(app, ['retrieval', 'chunks', str(sample_file), '--chunk-size', '80', '--overlap', '10'])

    assert result.exit_code == 0
    assert 'ofs=' in result.stdout
