from pathlib import Path

import pytest

from escolio.ingest.loaders import load_document


def test_load_document_reads_text_file(sample_text_file: Path) -> None:
    document = load_document(sample_text_file)

    assert document.source_type == 'txt'
    assert 'Arquitetura de benchmark local-first' in document.raw_text
    assert document.raw_text.endswith('latência.')


def test_load_document_reads_markdown_file(sample_markdown_file: Path) -> None:
    document = load_document(sample_markdown_file)

    assert document.source_type == 'md'
    assert '# Titulo da Nota' in document.raw_text
    assert '- item 2' in document.raw_text


def test_load_document_extracts_text_from_pdf(sample_pdf_file: Path) -> None:
    document = load_document(sample_pdf_file)

    assert document.source_type == 'pdf'
    assert 'Conteudo PDF de teste para extracao local-first.' in document.raw_text


def test_load_document_rejects_corrupted_pdf(tmp_path: Path) -> None:
    corrupted = tmp_path / 'corrupted.pdf'
    corrupted.write_bytes(b'%PDF-1.4\nconteudo quebrado sem xref')

    with pytest.raises(ValueError, match='PDF_PARSE_FAILED'):
        load_document(corrupted)


def test_load_document_rejects_unsupported_extension(tmp_path: Path) -> None:
    unsupported = tmp_path / 'sample.docx'
    unsupported.write_text('arquivo nao suportado', encoding='utf-8')

    with pytest.raises(ValueError, match='Extensão não suportada'):
        load_document(unsupported)
