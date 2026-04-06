import json
from pathlib import Path

from typer.testing import CliRunner

from free_plaud.cli import app
from free_plaud.notes.schemas import Note
from free_plaud.retrieval.indexer import index_note
from free_plaud.retrieval.rag import answer_with_citations
from free_plaud.retrieval.search import lexical_search_hits

runner = CliRunner()


def _build_note(**overrides: object) -> Note:
    payload: dict[str, object] = {
        'note_id': 'note-rag',
        'note_version': 1,
        'source_type': 'md',
        'source_path': Path('rag.md'),
        'source_name': 'rag.md',
        'title': 'Nota sobre benchmark e retrieval',
        'summary': 'Resumo da nota.',
        'topics': [],
        'tasks': [],
        'tags': ['md'],
        'raw_text': (
            'O benchmark mede recall, latencia e cobertura de citacoes. '
            'A recuperacao usa chunks com offsets reproduziveis. '
            'O SQLite persiste notas, chunks e logs de processamento.'
        ),
        'normalized_text': (
            'O benchmark mede recall, latencia e cobertura de citacoes. '
            'A recuperacao usa chunks com offsets reproduziveis. '
            'O SQLite persiste notas, chunks e logs de processamento.'
        ),
        'structured_markdown': (
            '# Nota sobre benchmark e retrieval\n\n'
            'O benchmark mede recall, latencia e cobertura de citacoes.\n\n'
            'A recuperacao usa chunks com offsets reproduziveis.\n\n'
            'O SQLite persiste notas, chunks e logs de processamento.\n'
        ),
        'content_hash': 'a' * 64,
    }
    payload.update(overrides)
    return Note(**payload)


def test_lexical_search_hits_expose_score_and_term_coverage() -> None:
    note = _build_note()
    chunks = index_note(note)

    hits = lexical_search_hits('O que o benchmark mede?', chunks, top_k=3)

    assert hits
    assert hits[0].score >= 2
    assert 0 < hits[0].term_coverage <= 1
    assert {'benchmark', 'mede'} <= set(hits[0].matched_terms)


def test_answer_with_citations_returns_structured_answer_with_claims_and_citations() -> None:
    note = _build_note()

    response = answer_with_citations(note, 'O que o benchmark mede?', top_k=3)

    assert response.status == 'answer'
    assert response.no_answer is False
    assert response.answer is not None
    assert 'benchmark' in response.answer.lower()
    assert response.claims
    assert response.citations
    assert response.claims[0].citations
    assert response.claims[0].citations[0].note_id == note.note_id
    assert response.claims[0].citations[0].chunk_id
    assert response.used_sources[0].doc_id == note.note_id
    assert response.reason_for_no_answer is None
    assert response.latency_ms >= 0


def test_answer_with_citations_returns_no_answer_when_there_is_no_evidence() -> None:
    note = _build_note()

    response = answer_with_citations(note, 'Como fazer OCR de imagens escaneadas?', top_k=3)

    assert response.status == 'no_answer'
    assert response.no_answer is True
    assert response.answer is None
    assert response.claims == []
    assert response.citations == []
    assert response.reason_for_no_answer == 'no_retrieval_hits'


def test_answer_with_citations_abstains_on_low_term_coverage_even_with_generic_match() -> None:
    note = _build_note(
        raw_text='O sistema opera localmente e persiste notas em SQLite.',
        normalized_text='O sistema opera localmente e persiste notas em SQLite.',
        structured_markdown='# Sistema local\n\nO sistema opera localmente e persiste notas em SQLite.\n',
        content_hash='b' * 64,
    )

    response = answer_with_citations(note, 'Como o sistema gera embeddings vetoriais?', top_k=3)

    assert response.status == 'no_answer'
    assert response.no_answer is True
    assert response.answer is None
    assert response.reason_for_no_answer == 'insufficient_term_coverage'
    assert response.used_sources


def test_answer_with_citations_does_not_treat_substring_matches_as_evidence() -> None:
    note = _build_note(
        raw_text='Existe um processo interno com revisoes periodicas.',
        normalized_text='Existe um processo interno com revisoes periodicas.',
        structured_markdown='# Processo interno\n\nExiste um processo interno com revisoes periodicas.\n',
        content_hash='c' * 64,
    )

    response = answer_with_citations(note, 'OCR juridico', top_k=3)

    assert response.status == 'no_answer'
    assert response.no_answer is True
    assert response.reason_for_no_answer == 'no_retrieval_hits'


def test_retrieval_ask_cli_renders_structured_json_response(tmp_path: Path) -> None:
    sample_file = tmp_path / 'ask.md'
    sample_file.write_text(
        '# Nota de teste\n\n'
        'O benchmark mede recall e latencia para comparar estrategias de recuperacao.\n',
        encoding='utf-8',
    )

    result = runner.invoke(
        app,
        [
            'retrieval',
            'ask',
            str(sample_file),
            '--question',
            'O que o benchmark mede?',
            '--top-k',
            '3',
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload['status'] == 'answer'
    assert payload['no_answer'] is False
    assert payload['citations']


def test_retrieval_ask_cli_keeps_json_parseable_with_unicode_source_paths(tmp_path: Path) -> None:
    sample_file = tmp_path / '📚 nota unicode.md'
    sample_file.write_text(
        '# Nota unicode\n\n'
        'O benchmark mede recall e latencia para comparar estrategias de recuperacao.\n',
        encoding='utf-8',
    )

    result = runner.invoke(
        app,
        [
            'retrieval',
            'ask',
            str(sample_file),
            '--question',
            'O que o benchmark mede?',
            '--top-k',
            '3',
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload['status'] == 'answer'
    assert payload['citations'][0]['source_path']
