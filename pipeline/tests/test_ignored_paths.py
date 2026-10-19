"""Arquivos ignorados na indexação (Fila: "Ignorar", "Voltar a indexar", "Tentar de novo")."""

import importlib.util
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

from escolio.app.config import Settings
from escolio.corpus.service import index_corpus_file, index_corpus_path
from escolio.storage.sqlite import (
    count_notes,
    ignore_paths,
    init_sqlite,
    list_ignored_paths,
    split_ignored,
    unignore_paths,
)


class FakeHashEmbedder:
    model_name = 'fake-hash'

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            vector = [0.0] * 16
            for token in text.lower().split():
                vector[sum(ord(char) for char in token) % 16] += 1.0
            vectors.append(vector)
        return vectors


def _settings(root: Path) -> Settings:
    data = root / 'data'
    return Settings(
        data_dir=data,
        results_dir=data / 'results',
        sqlite_path=data / 'results' / 'escolio.sqlite3',
        vector_store_dir=data / 'results' / 'vector_store',
        notes_dir=data / 'corpus' / 'notes',
        embedding_model='fake-hash',
    )


def _vault(root: Path) -> Path:
    vault = root / 'vault'
    (vault / 'Templates').mkdir(parents=True)
    (vault / 'nota.md').write_text('# Nota\n\nTexto que pode ser pesquisado.\n', encoding='utf-8')
    (vault / 'Templates' / 'Mensal.md').write_text('---\ntags: [mensal]\n---\n', encoding='utf-8')
    return vault


def test_ignore_list_e_case_insensitive_e_reversivel(tmp_path: Path) -> None:
    connection = init_sqlite(tmp_path / 'db.sqlite3')
    try:
        a, b = tmp_path / 'A.md', tmp_path / 'b.md'
        assert ignore_paths(connection, [a]) == 1
        kept, skipped = split_ignored(connection, [Path(str(a).upper()) if sys.platform == 'win32' else a, b])
        assert kept == [b] and len(skipped) == 1
        assert [row['path'] for row in list_ignored_paths(connection)] == [str(a)]

        assert unignore_paths(connection, [a]) == 1
        assert list_ignored_paths(connection) == []
    finally:
        connection.close()


def test_indexacao_de_pasta_pula_ignorados_e_conta_como_pulados(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    vault = _vault(tmp_path)
    connection = init_sqlite(settings.sqlite_path)
    try:
        ignore_paths(connection, [vault / 'Templates' / 'Mensal.md'])
    finally:
        connection.close()

    result = index_corpus_path(vault, settings=settings, embedder=FakeHashEmbedder(), recursive=True)

    assert result.failed_count == 0  # o template vazio não aparece mais como falha
    assert result.indexed_count == 1
    assert any(item.reason == 'ignored_by_user' for item in result.skipped)


def test_arquivo_ignorado_nao_e_indexado_pelo_watcher_ou_tentar_de_novo(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    vault = _vault(tmp_path)
    connection = init_sqlite(settings.sqlite_path)
    try:
        ignore_paths(connection, [vault / 'nota.md'])
    finally:
        connection.close()

    result = index_corpus_file(vault / 'nota.md', settings=settings, embedder=FakeHashEmbedder())

    assert result.status == 'unchanged'
    assert result.message == 'Arquivo ignorado na indexação.'
    connection = init_sqlite(settings.sqlite_path)
    try:
        assert count_notes(connection) == 0
    finally:
        connection.close()


def _load_ui_main(monkeypatch, root: Path):
    monkeypatch.setitem(sys.modules, 'webview', SimpleNamespace(create_window=lambda *a, **k: None, start=lambda *a, **k: None))
    path = Path(__file__).resolve().parents[2] / 'UI' / 'main.py'
    spec = importlib.util.spec_from_file_location('escolio_ui_main_ignored_test', path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # Api() lê o registro de vaults: isola em diretório temporário, nunca no data/ real.
    module.base_settings = lambda: _settings(root)
    return module


def test_api_ignorar_tira_do_indice_e_voltar_a_indexar_enfileira(tmp_path: Path, monkeypatch) -> None:
    module = _load_ui_main(monkeypatch, Path(tempfile.mkdtemp(prefix='escolio-ignored-', dir=tmp_path)))
    api = module.Api()
    api.runtime.get_embedder = lambda: FakeHashEmbedder()
    vault = _vault(tmp_path)
    note = vault / 'nota.md'

    first = api.retryIndexPaths([str(note)])['results'][0]
    assert first['status'] == 'indexed'

    result = api.ignoreIndexPaths([str(note)])
    assert result == {'ok': True, 'ignored': 1, 'removed_notes': 1}
    assert [row['path'] for row in api.listIgnoredPaths()] == [str(note)]
    assert api.retryIndexPaths([str(note)])['results'][0]['status'] == 'unchanged'

    queued = []
    api.dropped_files.enqueue_paths = lambda paths: queued.extend(paths)
    assert api.unignoreIndexPaths([str(note)]) == {'ok': True, 'restored': 1, 'queued': 1}
    assert queued == [note]
    assert api.listIgnoredPaths() == []


def test_api_abrir_so_aceita_tipos_indexaveis_e_caminhos_que_existem(tmp_path: Path, monkeypatch) -> None:
    module = _load_ui_main(monkeypatch, tmp_path)
    api = module.Api()
    programa = tmp_path / 'instalar.exe'
    programa.write_bytes(b'MZ')

    assert api.openIndexPath(str(programa))['ok'] is False
    assert api.openIndexPath(str(tmp_path / 'sumiu.md'))['ok'] is False
    assert api.openIndexPath('')['ok'] is False
