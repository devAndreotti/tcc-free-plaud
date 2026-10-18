from pathlib import Path

from escolio.corpus.dropped import DroppedFileIndexer
from escolio.corpus.models import CorpusIndexBatchResult, CorpusIndexResult


def _batch(path: Path, status: str, **extra) -> CorpusIndexBatchResult:
    return CorpusIndexBatchResult(
        source_path=str(path),
        recursive=False,
        status='failed' if status == 'failed' else 'success',
        total_found=1,
        indexed_count=int(status == 'success'),
        failed_count=int(status == 'failed'),
        skipped_count=0,
        results=[CorpusIndexResult(source_path=str(path), status=status, **extra)],
    )


def test_indexa_so_o_que_a_ui_confirma_e_reporta_cada_resultado(tmp_path: Path) -> None:
    calls: list[Path] = []

    def runner(path: Path) -> CorpusIndexBatchResult:
        calls.append(path)
        if path.name == 'ruim.md':
            return _batch(path, 'failed', error_code='EMPTY_CONTENT', message='Arquivo vazio.')
        if path.name == 'igual.md':
            return _batch(path, 'unchanged')
        return _batch(path, 'success', chunks_indexed=3)

    indexer = DroppedFileIndexer(runner=runner)
    indexer.stage([str(tmp_path / n) for n in ('nota.md', 'igual.md', 'ruim.md', 'foto.png', 'fora.md')])

    result = indexer.enqueue(['nota.md', 'igual.md', 'ruim.md', 'foto.png', 'sumiu.md'])
    indexer.join()

    assert result.queued == ['nota.md', 'igual.md', 'ruim.md', 'foto.png']
    assert result.missing == ['sumiu.md']
    # fora.md foi solto fora da área: nunca é indexado; png nem chega ao runner.
    assert [p.name for p in calls] == ['nota.md', 'igual.md', 'ruim.md']

    events = {e.name: e for e in indexer.poll_events()}
    assert events['nota.md'].status == 'indexed' and events['nota.md'].chunks == 3
    assert events['igual.md'].status == 'unchanged'
    assert events['ruim.md'].status == 'failed' and events['ruim.md'].error_code == 'EMPTY_CONTENT'
    assert events['foto.png'].error_code == 'UNSUPPORTED_EXTENSION'
    assert indexer.poll_events() == []


def test_excecao_no_runner_vira_falha_e_nao_derruba_a_fila(tmp_path: Path) -> None:
    def runner(path: Path) -> CorpusIndexBatchResult:
        if path.name == 'explode.md':
            raise RuntimeError('embedder caiu')
        return _batch(path, 'success', chunks_indexed=1)

    indexer = DroppedFileIndexer(runner=runner)
    indexer.stage([str(tmp_path / 'explode.md'), str(tmp_path / 'ok.md')])
    indexer.enqueue(['explode.md', 'ok.md'])
    indexer.join()

    events = {e.name: e for e in indexer.poll_events()}
    assert events['explode.md'].status == 'failed'
    assert events['explode.md'].message == 'embedder caiu'
    assert events['ok.md'].status == 'indexed'


def test_regressao_stage_guarda_arquivos_de_mesmo_nome_de_pastas_diferentes(tmp_path: Path) -> None:
    calls: list[Path] = []

    def runner(path: Path) -> CorpusIndexBatchResult:
        calls.append(path)
        return _batch(path, 'success', chunks_indexed=1)

    indexer = DroppedFileIndexer(runner=runner)
    first = tmp_path / 'a' / 'notas.md'
    second = tmp_path / 'b' / 'notas.md'
    indexer.stage([str(first), str(second)])

    result = indexer.enqueue(['notas.md', 'notas.md'])
    indexer.join()

    assert result.queued == ['notas.md', 'notas.md']
    assert result.missing == []
    assert calls == [first, second]
