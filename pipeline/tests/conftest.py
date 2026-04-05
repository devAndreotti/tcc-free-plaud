from pathlib import Path

import pytest


@pytest.fixture()
def sample_text_file(tmp_path: Path) -> Path:
    file_path = tmp_path / 'sample.txt'
    file_path.write_text(
        'Arquitetura de benchmark local-first\n'
        'O projeto valida ingestão, notas e recuperação com citação.\n'
        'O benchmark mede recall e latência.\n',
        encoding='utf-8',
    )
    return file_path


@pytest.fixture()
def sample_markdown_file(tmp_path: Path) -> Path:
    file_path = tmp_path / 'sample.md'
    file_path.write_text(
        '# Titulo da Nota\n\n'
        'Resumo em markdown para validar a estruturacao.\n\n'
        '- item 1\n'
        '- item 2\n',
        encoding='utf-8',
    )
    return file_path


def _escape_pdf_text(text: str) -> str:
    return text.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')


def _build_simple_pdf_bytes(text: str) -> bytes:
    escaped_text = _escape_pdf_text(text)
    objects = [
        b'1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n',
        b'2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n',
        b'3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 144] '
        b'/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>\nendobj\n',
    ]
    stream = (
        'BT\n'
        '/F1 12 Tf\n'
        '72 100 Td\n'
        f'({escaped_text}) Tj\n'
        'ET\n'
    ).encode('latin-1')
    objects.append(
        b'4 0 obj\n'
        + f'<< /Length {len(stream)} >>\n'.encode('ascii')
        + b'stream\n'
        + stream
        + b'endstream\nendobj\n'
    )
    objects.append(b'5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n')

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


@pytest.fixture()
def sample_pdf_file(tmp_path: Path) -> Path:
    file_path = tmp_path / 'sample.pdf'
    file_path.write_bytes(
        _build_simple_pdf_bytes(
            'Conteudo PDF de teste para extracao local-first.'
        )
    )
    return file_path
