from pathlib import Path

import pytest

from escolio.app.config import Settings
from escolio.tui.actions import ask_corpus, index_corpus_folder, preflight_corpus_folder


def test_preflight_corpus_folder_rejects_empty_path() -> None:
    with pytest.raises(ValueError, match='Informe uma pasta'):
        preflight_corpus_folder('   ')


def test_preflight_corpus_folder_counts_supported_and_skipped_files(tmp_path: Path) -> None:
    nested = tmp_path / 'nested'
    nested.mkdir()
    (tmp_path / 'nota.md').write_text('# Nota\n\nTexto.', encoding='utf-8')
    (nested / 'aula.txt').write_text('Aula.', encoding='utf-8')
    (tmp_path / 'image.png').write_text('bin', encoding='utf-8')

    result = preflight_corpus_folder(str(tmp_path))

    assert result.root_path == str(tmp_path)
    assert result.recursive is True
    assert {path.name for path in result.files} == {'nota.md', 'aula.txt'}
    assert result.skipped[0].reason == 'unsupported_extension'


def test_index_corpus_folder_rejects_empty_path_before_settings(monkeypatch) -> None:
    def fail_get_settings():
        raise AssertionError('settings nao deve ser lido para pasta vazia')

    monkeypatch.setattr('escolio.tui.actions.get_settings', fail_get_settings)

    with pytest.raises(ValueError, match='Informe uma pasta'):
        index_corpus_folder('')


def test_ask_corpus_repassa_on_answer_delta_ao_fluxo_de_resposta(monkeypatch, tmp_path: Path) -> None:
    recebido: dict[str, object] = {}

    def fake_answer(question, **kwargs):
        recebido['callback'] = kwargs.get('on_answer_delta')
        return 'resposta-fake'

    monkeypatch.setattr('escolio.tui.actions.answer_corpus_with_citations', fake_answer)
    settings = Settings(
        workspace_dir=tmp_path,
        data_dir=tmp_path / 'data',
        notes_dir=tmp_path / 'data' / 'corpus' / 'notes',
        results_dir=tmp_path / 'data' / 'results',
        sqlite_path=tmp_path / 'data' / 'results' / 'escolio.sqlite3',
        vector_store_dir=tmp_path / 'data' / 'results' / 'vector_store',
    )

    def callback(piece: str) -> None:
        return None

    assert ask_corpus('Pergunta?', 'lexical', settings=settings, on_answer_delta=callback) == 'resposta-fake'
    assert recebido['callback'] is callback
