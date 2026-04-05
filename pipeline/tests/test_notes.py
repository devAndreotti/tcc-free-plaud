from pathlib import Path

from typer.testing import CliRunner

from free_plaud.cli import app
from free_plaud.ingest.loaders import load_document
from free_plaud.notes.structurer import structure_document

runner = CliRunner()


def test_structure_document_builds_consistent_note_from_markdown(sample_markdown_file: Path) -> None:
    document = load_document(sample_markdown_file)

    note = structure_document(document)

    assert note.note_id == 'sample'
    assert note.source_type == 'md'
    assert note.title == 'Titulo da Nota'
    assert 'Resumo em markdown para validar a estruturacao.' in note.summary
    assert note.raw_text == document.raw_text
    assert note.structured_markdown
    assert note.structured_markdown != note.raw_text


def test_structured_markdown_contains_frontmatter_and_sections(sample_text_file: Path) -> None:
    document = load_document(sample_text_file)

    note = structure_document(document)

    assert note.structured_markdown.startswith('---\n')
    assert 'note_id: sample' in note.structured_markdown
    assert 'source_type: txt' in note.structured_markdown
    assert '## Summary' in note.structured_markdown
    assert '## Raw Text' in note.structured_markdown
    assert 'Arquitetura de benchmark local-first' in note.structured_markdown


def test_notes_build_cli_renders_structured_markdown(sample_markdown_file: Path) -> None:
    result = runner.invoke(app, ['notes', 'build', str(sample_markdown_file)])

    assert result.exit_code == 0
    assert '# Titulo da Nota' in result.stdout
    assert '## Summary' in result.stdout
