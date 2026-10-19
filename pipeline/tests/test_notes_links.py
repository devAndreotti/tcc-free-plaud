import sqlite3
from pathlib import Path

import pytest

from escolio.notes.links import extract_wikilinks, note_link_edges
from escolio.storage.sqlite import init_sqlite


@pytest.fixture
def db(tmp_path: Path):
    connection = init_sqlite(tmp_path / 'escolio.sqlite3')
    yield connection
    connection.close()


def _insert(connection: sqlite3.Connection, note_id: str, title: str, source_path: str, raw_text: str) -> None:
    connection.execute(
        'INSERT INTO notes (note_id, note_version, source_type, source_path, source_name, title, summary, '
        'raw_text, normalized_text, structured_markdown, content_hash, provider, model, created_at) '
        "VALUES (?, 1, 'md', ?, ?, ?, '', ?, '', '', '', '', '', '2026-10-18T12:00:00')",
        (note_id, source_path, Path(source_path).name, title, raw_text),
    )


def _pairs(edges: list[dict[str, str]]) -> set[tuple[str, str]]:
    return {(edge['source'], edge['target']) for edge in edges}


@pytest.mark.parametrize(
    ('markdown', 'expected'),
    [
        ('- [[Switch]]', ['Switch']),
        ('[[Nota|apelido]]', ['Nota']),
        ('[[Nota#Seção]]', ['Nota']),
        ('[[Nota#^bloco]] e [[Outra^bloco]]', ['Nota', 'Outra']),
        ('[[Pasta/Nota]]', ['Pasta/Nota']),
        ('![[Nota]]', ['Nota']),
        ('| [[Nota\\|apelido]] |', ['Nota']),
        ('[[]] [[ ]] [[sem fecho', []),
    ],
)
def test_extract_wikilinks_formas_do_obsidian(markdown: str, expected: list[str]) -> None:
    assert extract_wikilinks(markdown) == expected


def test_extract_wikilinks_ignora_anexos_e_codigo() -> None:
    markdown = '![[foto.png]] ![[doc.pdf]] [[Visivel]]\n~~~\n[[Cercado]]\n~~~\n`[[Inline]]` [[Depois]]'
    assert extract_wikilinks(markdown) == ['Visivel', 'Depois']


def test_resolve_apelido_secao_pasta_e_titulo_sem_maiusculas(db: sqlite3.Connection) -> None:
    _insert(db, 'switch', 'Switch', 'V/Redes/Switch.md', '')
    _insert(db, 'vlan', 'VLAN', 'V/Redes/VLAN.md', '')
    _insert(db, 'mac', 'Endereço MAC', 'V/Estudos/MAC.md', '')
    _insert(
        db,
        'ospf',
        'OSPF',
        'V/Redes/OSPF.md',
        '- [[switch|o switch]]\n- [[Redes/VLAN#Área 0]]\n- [[endereço mac]]',
    )

    assert _pairs(note_link_edges(db)) == {('ospf', 'switch'), ('ospf', 'vlan'), ('ospf', 'mac')}


def test_embed_de_imagem_e_codigo_nao_geram_aresta(db: sqlite3.Connection) -> None:
    _insert(db, 'switch', 'Switch', 'V/Switch.md', '')
    _insert(db, 'vlan', 'VLAN', 'V/VLAN.md', '')
    _insert(db, 'nota', 'Nota', 'V/Nota.md', '![[switch.png]]\n```\n[[vlan]]\n```\n`[[vlan]]`')

    assert note_link_edges(db) == []


def test_nao_resolvido_autolink_e_duplicado_ficam_fora(db: sqlite3.Connection) -> None:
    _insert(db, 'switch', 'Switch', 'V/Switch.md', '')
    _insert(db, 'ospf', 'OSPF', 'V/OSPF.md', '[[Inexistente]] [[OSPF]] [[Switch]] [[switch|de novo]] [[SWITCH]]')

    assert note_link_edges(db) == [{'source': 'ospf', 'target': 'switch'}]
