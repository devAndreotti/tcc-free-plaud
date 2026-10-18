from pathlib import Path

from escolio.notes.metadata import build_note_id


def test_build_note_id_preserves_legacy_file_id_without_root() -> None:
    assert build_note_id(Path('Área de TI.md')) == 'area-de-ti'


def test_build_note_id_uses_relative_path_hash_for_corpus_root() -> None:
    root = Path('vault')
    first = root / 'AI' / 'AI.md'
    second = root / 'AI' / '🤖 AI.md'

    first_id = build_note_id(first, root_path=root)
    second_id = build_note_id(second, root_path=root)

    assert first_id.startswith('ai--')
    assert second_id.startswith('ai--')
    assert first_id != second_id
    assert first_id == build_note_id(first, root_path=root)
    assert len(first_id.rsplit('--', maxsplit=1)[1]) == 10


def test_regressao_build_note_id_sem_raiz_distingue_caminhos_com_mesmo_nome() -> None:
    first = build_note_id(Path('/tmp/a/notas.md'), hash_unrooted=True)
    second = build_note_id(Path('/tmp/b/notas.md'), hash_unrooted=True)

    assert first.startswith('notas--')
    assert second.startswith('notas--')
    assert first != second
    assert first == build_note_id(Path('/tmp/a/notas.md'), hash_unrooted=True)
    assert build_note_id(Path('/tmp/A/Notas.md'), hash_unrooted=True) == first
