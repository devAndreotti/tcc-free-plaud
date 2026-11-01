"""E2E da Fila: job real (thread, indexador, snapshot em JSON como a interface recebe) com a lista "Agora".

Só o embedder é falso, para não baixar modelo; SQLite, Chroma, descoberta, hash e commit são os de verdade.
Regressão do redesenho da Fila: a tela mostra recent_files, então eles precisam chegar no snapshot do job.
"""

from __future__ import annotations

from pathlib import Path
from time import monotonic, sleep

from escolio.corpus.jobs import IndexJobManager
from escolio.corpus.service import index_corpus_path
from tests.test_corpus_service import FakeEmbedder, _settings


def _run_job(manager: IndexJobManager, folder: Path) -> list[dict]:
    """Inicia o job e lê o snapshot como a Fila faz (JSON), até terminar."""
    snapshots = [manager.start(folder).model_dump(mode='json')]
    job_id = snapshots[0]['job_id']
    deadline = monotonic() + 60
    while snapshots[-1]['status'] == 'running':
        assert monotonic() < deadline, 'o job não terminou em 60 s'
        sleep(0.05)
        snapshots.append(manager.get(job_id).model_dump(mode='json'))
    return snapshots


def test_fila_recebe_os_arquivos_reais_processados_pelo_job(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    vault = tmp_path / 'vault'
    (vault / 'Redes').mkdir(parents=True)
    notes = {'Redes/OSPF.md': 'OSPF usa estado de enlace.', 'Redes/BGP.md': 'BGP troca rotas entre sistemas.', 'Diario.md': 'Hoje estudei roteamento.'}
    for name, text in notes.items():
        (vault / name).write_text(f'# {Path(name).stem}\n\n{text}\n', encoding='utf-8')

    def runner(path, *, progress, cancel_token, runtime, rebuild=False):
        return index_corpus_path(path, settings=settings, embedder=FakeEmbedder(), recursive=True, progress=progress, cancel_token=cancel_token)

    manager = IndexJobManager(runner=runner)

    first = _run_job(manager, vault)
    final = first[-1]
    assert final['status'] == 'success'
    recent = final['progress']['recent_files']
    assert sorted(Path(item['source_path']).relative_to(vault).as_posix() for item in recent) == sorted(notes)
    assert all(item['status'] == 'success' and item['chunks'] > 0 for item in recent)
    assert final['progress']['indexed_count'] == 3

    # Reindexar a mesma vault: nada mudou, então a lista "Agora" mostra os arquivos como inalterados.
    second = _run_job(manager, vault)[-1]
    assert second['status'] == 'success'
    assert {item['status'] for item in second['progress']['recent_files']} == {'unchanged'}
    assert second['progress']['unchanged_count'] == 3
