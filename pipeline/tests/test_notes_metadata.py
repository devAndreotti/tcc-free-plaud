from pathlib import Path

from free_plaud.notes.metadata import build_note_id


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
