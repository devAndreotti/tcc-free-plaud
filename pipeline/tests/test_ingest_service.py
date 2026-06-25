from pathlib import Path

from typer.testing import CliRunner

from free_plaud.cli import app
from free_plaud.ingest.service import ingest_file

runner = CliRunner()


def _blank_pdf_bytes() -> bytes:
    objects = [
        b'1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n',
        b'2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n',
        b'3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 144] /Resources << >> /Contents 4 0 R >>\nendobj\n',
        b'4 0 obj\n<< /Length 0 >>\nstream\n\nendstream\nendobj\n',
    ]
    header = b'%PDF-1.4\n'
    body = bytearray(header)
    offsets = [0]
    for obj in objects:
        offsets.append(len(body))
        body.extend(obj)
    xref_offset = len(body)
    xref = [b'xref\n', f'0 {len(offsets)}\n'.encode('ascii'), b'0000000000 65535 f \n']
    for offset in offsets[1:]:
        xref.append(f'{offset:010d} 00000 n \n'.encode('ascii'))
    trailer = (
        b'trailer\n'
        + f'<< /Size {len(offsets)} /Root 1 0 R >>\n'.encode('ascii')
        + b'startxref\n'
        + f'{xref_offset}\n'.encode('ascii')
        + b'%%EOF\n'
    )
    return bytes(body) + b''.join(xref) + trailer


def test_ingest_file_returns_traceable_result_for_text(sample_text_file: Path, caplog) -> None:
    with caplog.at_level('INFO', logger='free_plaud.ingest'):
        result = ingest_file(sample_text_file, correlation_id='corr-001')

    assert result.status == 'success'
    assert result.correlation_id == 'corr-001'
    assert result.source_path == sample_text_file
    assert result.source_type == 'txt'
    assert result.size_bytes > 0
    assert len(result.content_sha256) == 64
    assert 'Arquitetura de benchmark local-first' in result.raw_text
    assert any('ingestion.started' in message for message in caplog.messages)
    assert any('ingestion.completed' in message for message in caplog.messages)


def test_ingest_file_returns_failure_for_missing_file(caplog, tmp_path: Path) -> None:
    missing = tmp_path / 'missing.txt'

    with caplog.at_level('INFO', logger='free_plaud.ingest'):
        result = ingest_file(missing, correlation_id='corr-missing')

    assert result.status == 'failed'
    assert result.error_code == 'INPUT_NOT_FOUND'
    assert result.source_path == missing
    assert any('ingestion.failed' in message for message in caplog.messages)


def test_ingest_file_rejects_empty_content(empty_text_file: Path, caplog) -> None:
    with caplog.at_level('INFO', logger='free_plaud.ingest'):
        result = ingest_file(empty_text_file, correlation_id='corr-empty')

    assert result.status == 'failed'
    assert result.error_code == 'EMPTY_CONTENT'
    assert result.source_type == 'txt'
    assert any('ingestion.failed' in message for message in caplog.messages)


def test_ingest_file_rejects_blank_pdf_as_empty_content(tmp_path: Path) -> None:
    blank_pdf = tmp_path / 'blank.pdf'
    blank_pdf.write_bytes(_blank_pdf_bytes())

    result = ingest_file(blank_pdf, correlation_id='corr-empty-pdf')

    assert result.status == 'failed'
    assert result.error_code == 'EMPTY_CONTENT'
    assert result.source_type == 'pdf'


def test_ingest_file_returns_structured_failure_for_corrupted_pdf(tmp_path: Path, caplog) -> None:
    corrupted_pdf = tmp_path / 'corrupted.pdf'
    corrupted_pdf.write_bytes(b'%PDF-1.4\nconteudo quebrado sem xref')

    with caplog.at_level('INFO', logger='free_plaud.ingest'):
        result = ingest_file(corrupted_pdf, correlation_id='corr-corrupted-pdf')

    assert result.status == 'failed'
    assert result.error_code == 'PDF_PARSE_FAILED'
    assert result.source_type == 'pdf'
    assert any('error_code=PDF_PARSE_FAILED' in message for message in caplog.messages)


def test_ingest_show_cli_renders_traceable_summary(sample_pdf_file: Path) -> None:
    result = runner.invoke(app, ['ingest', 'show', str(sample_pdf_file)])

    assert result.exit_code == 0
    assert 'ingestion_id' in result.stdout
    assert 'source_type' in result.stdout
    assert 'content_sha256' in result.stdout
    assert 'Conteudo PDF de teste para extracao local-first.' in result.stdout


def test_ingest_show_cli_accepts_unquoted_path_with_spaces(tmp_path: Path) -> None:
    sample_file = tmp_path / 'documento com espacos.md'
    sample_file.write_text('# Nota\n\nConteudo com espacos.\n', encoding='utf-8')

    result = runner.invoke(app, ['ingest', 'show', *str(sample_file).split(' ')])

    assert result.exit_code == 0
    assert 'ingestion_id' in result.stdout
    assert 'documento com espacos.md' in result.stdout
