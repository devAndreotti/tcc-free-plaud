import json
from pathlib import Path

from typer.testing import CliRunner

from free_plaud.app.config import Settings
from free_plaud.cli import app
from free_plaud.ingest.loaders import load_document
from free_plaud.notes.metadata import build_note_id
from free_plaud.notes.repository import save_note_locally
from free_plaud.notes.structurer import structure_document

runner = CliRunner()


def test_build_note_id_normalizes_accents_and_trailing_spaces() -> None:
    path = Path('Requisitos funcionais e requisitos de negócio do projeto .md')

    note_id = build_note_id(path)

    assert note_id == 'requisitos-funcionais-e-requisitos-de-negocio-do-projeto'


def test_structure_document_builds_consistent_note_from_markdown(sample_markdown_file: Path) -> None:
    document = load_document(sample_markdown_file)

    note = structure_document(document)

    assert note.note_id == 'sample'
    assert note.note_version == 1
    assert note.source_type == 'md'
    assert note.source_name == 'sample.md'
    assert note.title == 'Titulo da Nota'
    assert 'Resumo em markdown para validar a estruturacao.' in note.summary
    assert note.raw_text == document.raw_text
    assert note.normalized_text == document.raw_text.strip()
    assert len(note.content_hash) == 64
    assert note.structured_markdown
    assert note.structured_markdown != note.raw_text


def test_structured_markdown_contains_frontmatter_and_sections(sample_text_file: Path) -> None:
    document = load_document(sample_text_file)

    note = structure_document(document)

    assert note.structured_markdown.startswith('---\n')
    assert 'note_id: sample' in note.structured_markdown
    assert 'note_version: 1' in note.structured_markdown
    assert 'source_type: txt' in note.structured_markdown
    assert 'source_name: sample.txt' in note.structured_markdown
    assert '## Summary' in note.structured_markdown
    assert '## Normalized Text' in note.structured_markdown
    assert '## Raw Text' in note.structured_markdown
    assert 'Arquitetura de benchmark local-first' in note.structured_markdown


def test_structure_document_uses_first_real_paragraph_as_summary(tmp_path: Path) -> None:
    sample_file = tmp_path / 'doc.md'
    sample_file.write_text(
        '# Documento\n\n'
        '## Objetivo deste documento\n\n'
        '| Coluna | Valor |\n'
        '| --- | --- |\n'
        '| A | B |\n\n'
        '- item solto\n\n'
        'Este paragrafo deve virar o resumo inicial da nota.\n\n'
        'Outro paragrafo complementar.\n',
        encoding='utf-8',
    )

    document = load_document(sample_file)

    note = structure_document(document)

    assert note.summary == 'Este paragrafo deve virar o resumo inicial da nota.'


def test_notes_build_cli_renders_structured_markdown(sample_markdown_file: Path) -> None:
    result = runner.invoke(app, ['notes', 'build', str(sample_markdown_file)])

    assert result.exit_code == 0
    assert '# Titulo da Nota' in result.stdout
    assert '## Summary' in result.stdout


def test_notes_build_cli_accepts_unquoted_path_with_spaces(tmp_path: Path) -> None:
    sample_file = tmp_path / 'nota com espacos.md'
    sample_file.write_text('# Nota com espacos\n\nConteudo.\n', encoding='utf-8')

    result = runner.invoke(app, ['notes', 'build', *str(sample_file).split(' ')])

    assert result.exit_code == 0
    assert '# Nota com espacos' in result.stdout


def test_save_note_locally_persists_markdown_and_manifest(sample_markdown_file: Path, tmp_path: Path) -> None:
    document = load_document(sample_markdown_file)
    note = structure_document(document)
    settings = Settings(
        workspace_dir=tmp_path,
        data_dir=tmp_path / 'data',
        notes_dir=tmp_path / 'data' / 'corpus' / 'notes',
        datasets_dir=tmp_path / 'data' / 'datasets',
        results_dir=tmp_path / 'data' / 'results',
        sqlite_path=tmp_path / 'data' / 'results' / 'free_plaud.sqlite3',
        vector_store_dir=tmp_path / 'data' / 'results' / 'vector_store',
    )

    artifact = save_note_locally(note, settings.notes_dir)

    assert artifact.note_path == settings.notes_dir / 'sample.md'
    assert artifact.meta_path == settings.notes_dir / 'sample.meta.json'
    assert artifact.note_path.exists()
    assert artifact.meta_path.exists()
    assert artifact.note_path.read_text(encoding='utf-8').startswith('---\n')
    metadata = json.loads(artifact.meta_path.read_text(encoding='utf-8'))
    assert metadata['note_id'] == 'sample'
    assert metadata['source_name'] == 'sample.md'
    assert metadata['content_hash'] == note.content_hash
    assert len(metadata['structured_hash']) == 64


def test_notes_save_cli_persists_note_using_configured_notes_dir(
    sample_markdown_file: Path,
    monkeypatch,
    tmp_path: Path,
) -> None:
    settings = Settings(
        workspace_dir=tmp_path,
        data_dir=tmp_path / 'data',
        notes_dir=tmp_path / 'data' / 'corpus' / 'notes',
        datasets_dir=tmp_path / 'data' / 'datasets',
        results_dir=tmp_path / 'data' / 'results',
        sqlite_path=tmp_path / 'data' / 'results' / 'free_plaud.sqlite3',
        vector_store_dir=tmp_path / 'data' / 'results' / 'vector_store',
    )
    monkeypatch.setattr('free_plaud.notes.cli.get_settings', lambda: settings)

    result = runner.invoke(app, ['notes', 'save', str(sample_markdown_file)])

    assert result.exit_code == 0
    assert 'note_path' in result.stdout
    assert 'meta_path' in result.stdout
    assert (settings.notes_dir / 'sample.md').exists()
    assert (settings.notes_dir / 'sample.meta.json').exists()
