"""`benchmark compare` com --com-baseline e --cobertura, ponta a ponta com provedores falsos (sem rede).

Cada teste roda o CLI de verdade e confere o JSON que a UI lê: o principal tem de bater com a execução
sem flags, e os blocos novos têm de ter as chaves dos tipos TS de `UI/src/services/bridge.ts`.
"""

import json
import re
from pathlib import Path

import pytest
from benchmark_compare_fakes import (
    ARGUMENTOS_BASE,
    FakeEmbedder,
    FakeReranker,
    criar_suite,
    mascarar,
    settings_para,
)
from typer.testing import CliRunner

from escolio.benchmark.metrics import bootstrap_ci
from escolio.benchmark.runner_models import BenchmarkComparisonResult
from escolio.cli import app

runner = CliRunner()
REPO_ROOT = Path(__file__).resolve().parents[2]
BRIDGE_TS = REPO_ROOT / 'UI' / 'src' / 'services' / 'bridge.ts'
# Blocos que o `compare` grava com as flags novas (faithfulness vem do comando `faithfulness`).
CHAVES_COMPARE = {'reranked', 'baseline_ci', 'coverage'}
ESTRATEGIAS = {'lexical', 'vector', 'hybrid'}


def _rodar(tmp_path: Path, monkeypatch, argumentos: list[str], reranker: FakeReranker | None = None):
    tmp_path.mkdir(parents=True, exist_ok=True)
    settings = settings_para(tmp_path)
    suite_path = criar_suite(tmp_path)
    monkeypatch.setattr('escolio.benchmark.cli.get_settings', lambda: settings)
    monkeypatch.setattr('escolio.benchmark.cli.get_embedder', lambda model_name, **kwargs: FakeEmbedder())
    if reranker is not None:
        monkeypatch.setattr('escolio.benchmark.cli.reranker_from_settings', lambda _settings: reranker)
    resultado = runner.invoke(app, ['benchmark', 'compare', '--suite', str(suite_path), *ARGUMENTOS_BASE, *argumentos])
    return resultado, settings, suite_path


def _payload(tmp_path: Path, monkeypatch, argumentos: list[str], reranker: FakeReranker | None = None) -> dict:
    resultado, _, _ = _rodar(tmp_path, monkeypatch, argumentos, reranker)
    assert resultado.exit_code == 0, resultado.output
    return json.loads(resultado.stdout)


def _campos_ts(nome: str) -> set[str]:
    """Nomes dos campos de uma interface exportada em bridge.ts (interfaces planas, sem objetos aninhados)."""
    texto = BRIDGE_TS.read_text(encoding='utf-8')
    inicio = re.search(rf'export interface {nome}\b[^{{]*\{{', texto)
    assert inicio is not None, f'interface {nome} não encontrada em bridge.ts'
    corpo = texto[inicio.end(): texto.index('\n}', inicio.end())]
    return {encontrado.group(1) for encontrado in re.finditer(r'^\s+(\w+)\??\s*:', corpo, re.MULTILINE)}


def test_com_baseline_sem_rerank_model_falha_antes_de_rodar(monkeypatch, tmp_path: Path) -> None:
    resultado, _, _ = _rodar(tmp_path, monkeypatch, ['--com-baseline'])

    assert resultado.exit_code != 0
    assert '--com-baseline exige --rerank-model' in resultado.output


@pytest.mark.parametrize(('valor', 'mensagem'), [('0', '1 ou mais'), ('3,11', 'profundidade'), ('x', 'inteiros')])
def test_cobertura_com_k_invalido_falha(monkeypatch, tmp_path: Path, valor: str, mensagem: str) -> None:
    resultado, _, _ = _rodar(tmp_path, monkeypatch, ['--cobertura', valor])

    assert resultado.exit_code != 0
    assert mensagem in resultado.output


def test_com_baseline_mantem_o_principal_e_grava_reranked(monkeypatch, tmp_path: Path) -> None:
    sem_flags = _payload(tmp_path / 'sem', monkeypatch, [])
    reranker = FakeReranker()

    com_flags = _payload(
        tmp_path / 'com', monkeypatch, ['--com-baseline', '--rerank-model', 'fake-reranker'], reranker=reranker
    )

    # O principal é a passada sem reranker: igual ao compare sem flags, campo a campo.
    principal = {chave: valor for chave, valor in com_flags.items() if chave not in CHAVES_COMPARE}
    assert mascarar(principal) == mascarar(sem_flags)
    assert reranker.chamadas > 0  # a segunda passada de fato usou o reranker

    assert set(com_flags['reranked']) == {'model', 'summaries', 'ci'}
    assert com_flags['reranked']['model'] == 'fake-reranker'
    assert set(com_flags['reranked']['summaries']) == ESTRATEGIAS
    assert set(com_flags['reranked']['ci']) == ESTRATEGIAS
    assert set(com_flags['baseline_ci']) == ESTRATEGIAS
    assert all(set(intervalo) == {'mrr_lower', 'mrr_upper'} for intervalo in com_flags['baseline_ci'].values())


def test_baseline_ci_bate_com_o_bootstrap_dos_reciprocal_ranks_gravados(monkeypatch, tmp_path: Path) -> None:
    com_flags = _payload(
        tmp_path / 'com', monkeypatch, ['--com-baseline', '--rerank-model', 'fake-reranker'], reranker=FakeReranker()
    )

    for estrategia, linhas in com_flags['corpus']['queries'].items():
        positivas = [linha['reciprocal_rank'] for linha in linhas if linha['category'] != 'negativa']
        ic = bootstrap_ci(positivas)
        assert com_flags['baseline_ci'][estrategia] == {'mrr_lower': ic['lower'], 'mrr_upper': ic['upper']}


def test_cobertura_grava_o_bloco_coverage_com_contagens(monkeypatch, tmp_path: Path) -> None:
    payload = _payload(tmp_path, monkeypatch, ['--cobertura', '3,5,10'])

    bloco = payload['coverage']
    assert set(bloco) == {'k', 'groups'}
    assert bloco['k'] == 10  # a maior profundidade pedida
    grupos = {grupo['id']: grupo for grupo in bloco['groups']}
    assert set(grupos) == {'unica', 'mt-nota', 'todos'}
    # Suíte de teste: duas perguntas `unica-*`, uma `mt-nota-*`; `todos` agrega as três.
    assert (grupos['unica']['n'], grupos['mt-nota']['n'], grupos['todos']['n']) == (2, 1, 3)
    for grupo in bloco['groups']:
        assert set(grupo) == {'id', 'label', 'hint', 'n', 'single_chunk', 'across_chunks'}
        assert 0 <= grupo['single_chunk'] <= grupo['across_chunks'] <= grupo['n']


def test_cobertura_bate_com_o_subcomando_coverage_sobre_o_mesmo_json(monkeypatch, tmp_path: Path) -> None:
    resultado, settings, suite_path = _rodar(tmp_path, monkeypatch, ['--cobertura', '3,5,10', '--export'])
    assert resultado.exit_code == 0, resultado.output
    payload = json.loads(resultado.stdout)
    saida = tmp_path / 'cobertura_subcomando.json'

    subcomando = runner.invoke(
        app,
        [
            'benchmark', 'coverage',
            '--results', payload['json_report_path'],
            '--suite', str(suite_path),
            '--k', '10',
            '--saida', str(saida),
            '--workspace', str(settings.workspace_dir),
        ],
    )

    assert subcomando.exit_code == 0, subcomando.output
    celulas = json.loads(saida.read_text(encoding='utf-8'))['celulas']
    total = next(c for c in celulas if c['strategy'] == 'hybrid' and c['grupo'] == 'todos' and c['k'] == 10)
    across_subcomando = round(total['juncao_completa']['mean'] * total['n'])
    todos = next(grupo for grupo in payload['coverage']['groups'] if grupo['id'] == 'todos')
    assert todos['across_chunks'] == across_subcomando
    assert todos['n'] == total['n']


def test_todas_as_flags_juntas_gravam_as_chaves_no_stdout_e_no_arquivo(monkeypatch, tmp_path: Path) -> None:
    argumentos = ['--com-baseline', '--rerank-model', 'fake-reranker', '--cobertura', '3,5,10', '--export']

    payload = _payload(tmp_path, monkeypatch, argumentos, reranker=FakeReranker())

    exportado = json.loads(Path(payload['json_report_path']).read_text(encoding='utf-8'))
    assert set(exportado) == set(BenchmarkComparisonResult.model_fields) | CHAVES_COMPARE
    assert set(payload) == set(exportado) | {'json_report_path', 'csv_report_path'}
    assert exportado['reranked'] == payload['reranked']
    assert exportado['coverage'] == payload['coverage']
    assert exportado['baseline_ci'] == payload['baseline_ci']


def test_chaves_gravadas_batem_com_os_tipos_ts_da_ui(monkeypatch, tmp_path: Path) -> None:
    payload = _payload(
        tmp_path, monkeypatch, ['--com-baseline', '--rerank-model', 'fake-reranker', '--cobertura', '3,5,10'],
        reranker=FakeReranker(),
    )

    assert set(payload['reranked']) == _campos_ts('BenchmarkReranked')
    intervalo_ts = _campos_ts('BenchmarkMrrInterval')
    assert all(set(intervalo) == intervalo_ts for intervalo in payload['baseline_ci'].values())
    assert all(set(intervalo) == intervalo_ts for intervalo in payload['reranked']['ci'].values())
    assert set(payload['coverage']) == _campos_ts('BenchmarkCoverage')
    assert all(set(grupo) == _campos_ts('BenchmarkCoverageGroup') for grupo in payload['coverage']['groups'])
    # Os quatro campos opcionais de BenchmarkCompareResult; `faithfulness` é gravado pelo comando faithfulness.
    assert {'reranked', 'baseline_ci', 'coverage', 'faithfulness'} <= _campos_ts('BenchmarkCompareResult')
